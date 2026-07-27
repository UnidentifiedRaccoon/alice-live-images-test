#!/usr/bin/env python3
"""Complete PROMOPAGES-9930 with 20 independently planned Wan 2.2 videos.

The original PROMOPAGES-9930 batch is immutable and contains the same twenty
additional images planned independently for Wan 2.7 and Veo 3.1 Lite.  This
add-on creates a separate singleton-model Lite planning namespace and a
separate provider namespace, then derives the stable three-model showcase
manifest from the two components.

Routine generation resolves only the exact ``alibaba/wan-2.2`` route from the
locked local registry.  It never performs model discovery, never falls back to
the diagnostic named endpoint, uses the route's single slot, and never
resubmits an ambiguous or terminal paid run.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_all_images_pipeline as original  # noqa: E402
from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
AGENT_ID = "clipmaker-lite"
MODEL_ID = native.WAN_MODEL_ID
MODEL_IDS = (MODEL_ID,)
ALL_MODEL_IDS = (
    native.WAN_MODEL_ID,
    native.WAN_27_MODEL_ID,
    native.VEO_31_MODEL_ID,
)

PLANNING_BATCH_ID = "promopages-9930-lite20-wan22-plans-20260727-v1"
BATCH_ID = "promopages-9930-lite20-wan22-runs-20260727-v2"
FAILED_CANARY_BATCH_ID = "promopages-9930-lite20-wan22-runs-20260727-v1"
AGGREGATE_BATCH_ID = "promopages-9930-lite20-all-models-20260727-v1"
ORIGINAL_BATCH_ID = original.BATCH_ID

EXPECTED_ARTICLES = 20
EXPECTED_IMAGES = 20
EXPECTED_OUTPUTS = 20
EXPECTED_AGGREGATE_OUTPUTS = 60
MAX_PAID_SUBMISSIONS = 21

# The user authorized $14-$20 for the whole operation.  The completed 20x2
# component accounts for $14, so this add-on reserves the remaining $6.  The
# provider's exact USD unit price is not asserted: the local operator-facing
# model card displays 8-10 RUB per output.
ORIGINAL_ESTIMATE_USD = 14.0
ADDON_BUDGET_RESERVATION_USD = 6.0
HARD_BUDGET_CAP_USD = 20.0
LOCAL_DISPLAY_ESTIMATE_RUB = (8, 10)

ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")
CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ORIGINAL_INVENTORY_REL = (
    Path("clipmaker-lite-test/runs") / ORIGINAL_BATCH_ID / "inventory.json"
)
ORIGINAL_COMPONENT_REL = (
    Path("clipmaker-lite-test/runs")
    / BATCH_ID
    / "components"
    / "promopages-9930-20x2-manifest.json"
)
ORIGINAL_INVENTORY_SHA256 = (
    "56def783885e1e82401694b8a562ba61985a10cde82758f3936822c44a5891ef"
)
ORIGINAL_STABLE_MANIFEST_SHA256 = (
    "3f77dea1e6f6c687324a45127a2cc4a666348660204b1c9ab6b9ad135aafb9f7"
)

BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
INVENTORY_MANIFEST_REL = BATCH_ROOT_REL / "inventory.json"
GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"
VERIFICATION_REPORT_REL = BATCH_ROOT_REL / "verification-report.json"
SIDECAR_MANIFEST_REL = Path("clipmaker-lite-test/promopages-9930-wan22-manifest.json")
STABLE_MANIFEST_REL = Path("clipmaker-lite-test/promopages-9930-manifest.json")


class PipelineError(RuntimeError):
    """A fail-closed error in the Wan 2.2 add-on coordinator."""


@dataclass(frozen=True)
class Source:
    """The frozen original selection with a new planning identity."""

    original_source: original.Source

    @property
    def article_slug(self) -> str:
        return self.original_source.article_slug

    @property
    def article_number(self) -> str:
        return self.original_source.article_number

    @property
    def context_path(self) -> str:
        return self.original_source.context_path

    @property
    def image(self) -> dict[str, Any]:
        return self.original_source.image

    @property
    def sample_id(self) -> str:
        return self.original_source.sample_id

    @property
    def planning_run_id(self) -> str:
        return f"{PLANNING_BATCH_ID}-{self.sample_id}"

    @property
    def sample(self) -> native.Sample:
        return self.original_source.sample


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PipelineError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise PipelineError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in {path}: {exc}") from exc


def cost_metadata() -> dict[str, Any]:
    combined = ORIGINAL_ESTIMATE_USD + ADDON_BUDGET_RESERVATION_USD
    if combined > HARD_BUDGET_CAP_USD:
        raise PipelineError(
            f"Reserved total ${combined:.2f} exceeds ${HARD_BUDGET_CAP_USD:.2f}"
        )
    return {
        "currency": "USD",
        "original_20x2_estimate_usd": ORIGINAL_ESTIMATE_USD,
        "wan22_addon_budget_reservation_usd": ADDON_BUDGET_RESERVATION_USD,
        "hard_budget_cap_usd": HARD_BUDGET_CAP_USD,
        "maximum_reserved_total_usd": combined,
        "wan22_exact_usd_unit_cost_known": False,
        "wan22_local_display_estimate_rub_per_output": list(
            LOCAL_DISPLAY_ESTIMATE_RUB
        ),
        "wan22_planned_paid_submissions": EXPECTED_OUTPUTS,
        "wan22_maximum_paid_submissions": MAX_PAID_SUBMISSIONS,
        "wan22_intentional_retry_allowance": 1,
        "failed_canary_batch_id": FAILED_CANARY_BATCH_ID,
        "automatic_paid_retries": False,
        "retry_policy": (
            "each immutable Wan 2.2 entry may submit at most once; resume only "
            "polls its recorded legacy session, and any intentional paid retry "
            "requires a new separately budgeted namespace"
        ),
    }


def _source_binding(source: Source, article: original.Article) -> dict[str, Any]:
    return {
        "article_number": article.number,
        "article_slug": article.slug,
        "context_path": article.context_path,
        "context_sha256": article.context_sha256,
        "image_id": source.image["image_id"],
        "source_path": source.image["source_path"],
        "source_sha256": source.image["sha256"],
    }


def discover(
    root: Path = ROOT,
) -> tuple[tuple[original.Article, ...], tuple[Source, ...]]:
    """Re-resolve and compare all sources with the immutable 20x2 inventory."""

    inventory_path = root / ORIGINAL_INVENTORY_REL
    if sha256_file(inventory_path) != ORIGINAL_INVENTORY_SHA256:
        raise PipelineError(f"Original inventory bytes changed: {inventory_path}")
    inventory = read_json(inventory_path)
    if (
        inventory.get("batch_id") != ORIGINAL_BATCH_ID
        or inventory.get("article_count") != EXPECTED_ARTICLES
        or inventory.get("image_count") != EXPECTED_IMAGES
    ):
        raise PipelineError("Original inventory identity or counts changed")

    articles, base_sources = original.discover(root)
    sources = tuple(Source(source) for source in base_sources)
    frozen_articles = inventory.get("articles")
    if not isinstance(frozen_articles, list) or len(frozen_articles) != len(articles):
        raise PipelineError("Original inventory articles are missing")

    for article, source, frozen in zip(articles, sources, frozen_articles):
        images = frozen.get("images") if isinstance(frozen, dict) else None
        context = frozen.get("context") if isinstance(frozen, dict) else None
        if not isinstance(images, list) or len(images) != 1 or not isinstance(
            context, dict
        ):
            raise PipelineError(f"Invalid frozen source record: {article.slug}")
        expected = _source_binding(source, article)
        actual = {
            "article_number": frozen.get("article_number"),
            "article_slug": frozen.get("article_slug"),
            "context_path": context.get("path"),
            "context_sha256": context.get("sha256"),
            "image_id": images[0].get("image_id"),
            "source_path": images[0].get("source_path"),
            "source_sha256": images[0].get("sha256"),
        }
        if actual != expected:
            raise PipelineError(f"Frozen source binding changed: {article.slug}")
    return articles, sources


def inventory_document(
    articles: Iterable[original.Article], sources: Iterable[Source]
) -> dict[str, Any]:
    articles = tuple(articles)
    sources = tuple(sources)
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "planning_batch_id": PLANNING_BATCH_ID,
        "agent_id": AGENT_ID,
        "models": list(MODEL_IDS),
        "article_count": len(articles),
        "image_count": len(sources),
        "expected_outputs": len(sources),
        "source_inventory": ORIGINAL_INVENTORY_REL.as_posix(),
        "source_inventory_sha256": ORIGINAL_INVENTORY_SHA256,
        "supersedes_failed_canary_batch_id": FAILED_CANARY_BATCH_ID,
        "selection_rule": "exact immutable PROMOPAGES-9930 20x2 inventory binding",
        "cost": cost_metadata(),
        "sources": [
            {
                **_source_binding(source, article),
                "sample_id": source.sample_id,
                "planning_run_id": source.planning_run_id,
            }
            for article, source in zip(articles, sources)
        ],
    }


def write_inventory(
    articles: Iterable[original.Article],
    sources: Iterable[Source],
    root: Path = ROOT,
) -> dict[str, Any]:
    document = inventory_document(articles, sources)
    path = root / INVENTORY_MANIFEST_REL
    if path.is_file():
        if read_json(path) != document:
            raise PipelineError(f"Immutable inventory differs: {path}")
        return document
    if path.exists():
        raise PipelineError(f"Inventory target is not a regular file: {path}")
    transport.atomic_write_json(path, document)
    return document


def configure_native(sources: Iterable[Source], root: Path = ROOT) -> None:
    sources = tuple(sources)
    if len(sources) != EXPECTED_IMAGES:
        raise PipelineError(f"Expected {EXPECTED_IMAGES} frozen Wan 2.2 sources")
    route = transport.route_for_model(MODEL_ID)
    if (
        route.get("adapter") != "wan-demo"
        or route.get("transport") != "gradio-legacy-queue"
        or int(route.get("capacity", 0)) != 1
    ):
        raise PipelineError("Locked Wan 2.2 route registry entry changed")

    native.BATCH_ID = BATCH_ID
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = MODEL_IDS
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = GENERATION_MANIFEST_REL
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = None
    native.SAMPLES = tuple(source.sample for source in sources)
    # None means the normal registry transport.  The diagnostic named endpoint
    # is never selected by this coordinator.
    native.WAN_SUBMIT_MODE = None

    def artifact_paths(
        entry: native.Entry, workspace: Path = root
    ) -> dict[str, Path]:
        base = (
            workspace
            / BATCH_ROOT_REL
            / "videos"
            / entry.sample.article_slug
            / native.MODEL_DIRECTORIES[entry.model_id]
        )
        stem = entry.sample.image_id
        return {
            "directory": base,
            "prompt": base / f"{stem}.prompt.json",
            "run": base / f"{stem}.run.json",
            "video": base / f"{stem}.mp4",
        }

    native.artifact_paths = artifact_paths


@contextmanager
def original_bindings():
    """Temporarily reuse the tested generic validation/finalization helpers."""

    replacements = {
        "BATCH_ID": BATCH_ID,
        "MODEL_IDS": MODEL_IDS,
        "EXPECTED_ARTICLES": EXPECTED_ARTICLES,
        "EXPECTED_IMAGES": EXPECTED_IMAGES,
        "EXPECTED_OUTPUTS": EXPECTED_OUTPUTS,
        "BATCH_ROOT_REL": BATCH_ROOT_REL,
        "INVENTORY_MANIFEST_REL": INVENTORY_MANIFEST_REL,
        "GENERATION_MANIFEST_REL": GENERATION_MANIFEST_REL,
        "VERIFICATION_REPORT_REL": VERIFICATION_REPORT_REL,
        "FINAL_MANIFEST_REL": SIDECAR_MANIFEST_REL,
        "cost_metadata": cost_metadata,
        "configure_native": configure_native,
        "prepare_planning_runs": prepare_planning_runs,
    }
    previous = {name: getattr(original, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(original, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(original, name, value)


def planning_state(source: Source, root: Path = ROOT) -> str | None:
    """Validate one prepared/result artifact without mutating shared globals."""

    result_path = (
        root / ARTIFACT_NAMESPACE / source.planning_run_id / "result.json"
    )
    job_path = result_path.parent / "job.json"
    if result_path.is_file():
        summary = runner.provenance_summary(root, source.planning_run_id)
        if (
            summary.get("verified") is not True
            or summary.get("agent_id") != AGENT_ID
            or summary.get("models") != list(MODEL_IDS)
            or summary.get("source_image_sha256") != source.image["sha256"]
        ):
            raise PipelineError(
                f"Existing planning provenance differs: {source.planning_run_id}"
            )
        return "verified"
    if job_path.is_file():
        _job, selection, _directory = runner.validate_prepared_job(
            root, source.planning_run_id
        )
        selected_ids = [
            item.get("model_id")
            for item in selection.get("selected_models", [])
            if isinstance(item, dict)
        ]
        if selected_ids != list(MODEL_IDS):
            raise PipelineError(
                f"Existing planning model set differs: {source.planning_run_id}"
            )
        return "prepared"
    return None


def prepare_planning_runs(
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> dict[str, int]:
    counts = {"verified": 0, "prepared": 0, "pending": 0}
    for source in sources:
        state = planning_state(source, root)
        if state is not None:
            counts[state] += 1
            print(
                f"planning prepare {source.planning_run_id} -> existing-{state}",
                flush=True,
            )
            continue
        if dry_run:
            counts["pending"] += 1
            print(
                f"planning prepare {source.planning_run_id} -> would-prepare",
                flush=True,
            )
            continue
        command = [
            sys.executable,
            str(root / "scripts/clipmaker_lite_runner.py"),
            "prepare",
            "--run-id",
            source.planning_run_id,
            "--image",
            source.image["source_path"],
            "--context",
            source.context_path,
            "--image-id",
            source.image["image_id"],
            "--model",
            MODEL_ID,
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            detail = transport.safe_error(completed.stderr or completed.stdout)
            raise PipelineError(
                f"Planning prepare failed for {source.planning_run_id}: {detail}"
            )
        if planning_state(source, root) != "prepared":
            raise PipelineError(
                f"Runner did not create a valid planning job: {source.planning_run_id}"
            )
        counts["prepared"] += 1
        print(f"planning prepare {source.planning_run_id} -> prepared", flush=True)
    return counts


def _run_one_plan(
    source: Source,
    *,
    root: Path,
    timeout: int,
    author_model: str | None,
) -> tuple[str, str, str | None]:
    if planning_state(source, root) == "verified":
        return source.planning_run_id, "existing", None
    command = [
        sys.executable,
        str(root / "scripts/clipmaker_lite_runner.py"),
        "run",
        "--run-id",
        source.planning_run_id,
        "--timeout",
        str(timeout),
        "--allow-external-processing",
    ]
    if author_model:
        command.extend(("--author-model", author_model))
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return source.planning_run_id, "failed", f"planning timed out: {exc}"
    if completed.returncode:
        return (
            source.planning_run_id,
            "failed",
            transport.safe_error(completed.stderr or completed.stdout),
        )
    if planning_state(source, root) != "verified":
        return source.planning_run_id, "failed", "runner provenance is not verified"
    return source.planning_run_id, "completed", None


def run_planning_runs(
    sources: Iterable[Source],
    *,
    root: Path,
    concurrency: int,
    timeout: int,
    dry_run: bool,
    allow_external_processing: bool,
    author_model: str | None,
) -> int:
    sources = tuple(sources)
    if concurrency < 1:
        raise PipelineError("Planning concurrency must be at least 1")
    if dry_run:
        prepare_planning_runs(sources, root=root, dry_run=True)
        for source in sources:
            print(
                f"planning run {source.planning_run_id} -> "
                f"{'existing' if planning_state(source, root) == 'verified' else 'would-run'}"
            )
        return 0
    if not allow_external_processing:
        raise PipelineError(
            "Real planning requires --allow-external-processing because images "
            "and article context are sent to isolated Codex executions"
        )
    failures: list[str] = []
    with original.manifest_run_lock(root / INVENTORY_MANIFEST_REL):
        prepare_planning_runs(sources, root=root)
        with ThreadPoolExecutor(
            max_workers=concurrency,
            thread_name_prefix="promopages-9930-wan22-plan",
        ) as executor:
            futures: dict[Future[tuple[str, str, str | None]], Source] = {
                executor.submit(
                    _run_one_plan,
                    source,
                    root=root,
                    timeout=timeout,
                    author_model=author_model,
                ): source
                for source in sources
            }
            completed_count = 0
            for future in as_completed(futures):
                run_id, status, error = future.result()
                completed_count += 1
                print(
                    f"planning [{completed_count}/{len(sources)}] {run_id} -> "
                    f"{status}{f': {error}' if error else ''}",
                    flush=True,
                )
                if error:
                    failures.append(f"{run_id}: {error}")
    if failures:
        detail = "; ".join(failures[:5])
        raise PipelineError(
            f"{len(failures)} planning run(s) failed: {detail}"
        )
    return 0


def materialize_generation(
    sources: Iterable[Source], *, root: Path, dry_run: bool
) -> int:
    sources = tuple(sources)
    configure_native(sources, root)
    if dry_run:
        for entry in native.matrix():
            native.load_lite_job(entry, root)
        print(f"PASS: validated {EXPECTED_OUTPUTS} Wan 2.2 jobs; no files written")
        return 0
    rows = native.materialize(root)
    if len(rows) != EXPECTED_OUTPUTS:
        raise PipelineError(f"Expected {EXPECTED_OUTPUTS} materialized Wan 2.2 jobs")
    print(f"PASS: materialized {len(rows)} Wan 2.2 provider jobs")
    return 0


def _canary_is_conforming(sources: Iterable[Source], root: Path) -> bool:
    configure_native(sources, root)
    entry = native.matrix()[0]
    paths = native.artifact_paths(entry, root)
    if not paths["run"].is_file() or not paths["video"].is_file():
        return False
    run = read_json(paths["run"])
    try:
        media = transport.ffprobe_media(paths["video"])
        expected_contract = native.strict_media_contract(entry, media)
    except (OSError, transport.PipelineError):
        return False
    check = run.get("contract_check") if isinstance(run, dict) else None
    return (
        run.get("status") == "succeeded"
        and run.get("media") == media
        and isinstance(check, dict)
        and check == expected_contract
        and expected_contract.get("conforms") is True
    )


def run_generation(
    sources: Iterable[Source],
    *,
    root: Path,
    timeout: int,
    poll_interval: float,
    dry_run: bool,
    allow_external_processing: bool,
    canary: bool,
    fail_fast: bool,
) -> int:
    sources = tuple(sources)
    cost_metadata()
    configure_native(sources, root)
    entries = native.matrix()
    if len(entries) != EXPECTED_OUTPUTS:
        raise PipelineError("Wan 2.2 matrix exceeds the 20-submit budget envelope")
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real generation requires --allow-external-processing because images "
            "and prompts are sent to the fixed Wan 2.2 provider route"
        )
    if not canary and not dry_run and not _canary_is_conforming(sources, root):
        raise PipelineError(
            "Full generation is gated on one succeeded, conforming canary"
        )
    argv = [
        "run",
        "--wan22-concurrency",
        "1",
        "--wan-base-url",
        str(transport.route_for_model(MODEL_ID)["default_base_url"]),
        "--wan-stream-base-url",
        str(transport.route_for_model(MODEL_ID)["default_stream_base_url"]),
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
        "--model",
        MODEL_ID,
    ]
    if canary:
        argv.extend(("--run-id", entries[0].provider_run_id))
    if fail_fast:
        argv.append("--fail-fast")
    argv.append("--dry-run" if dry_run else "--allow-external-processing")
    if dry_run:
        return native.main(argv, root)
    with original.manifest_run_lock(root / INVENTORY_MANIFEST_REL):
        result = native.main(argv, root)
    if canary and result == 0 and not _canary_is_conforming(sources, root):
        raise PipelineError("Wan 2.2 canary completed without strict conformance")
    return result


def _sidecar_document(
    articles: Iterable[original.Article],
    sources: Iterable[Source],
    *,
    root: Path,
    updated_at: str | None = None,
) -> dict[str, Any]:
    with original_bindings():
        document = original.build_final_manifest(
            articles,
            sources,
            root=root,
            updated_at=updated_at,
            allow_contract_warnings=False,
        )
    document["manifest_role"] = "missing-model-extension"
    document["batch_id"] = BATCH_ID
    document["planning_batch_id"] = PLANNING_BATCH_ID
    document["extends_manifest"] = ORIGINAL_COMPONENT_REL.as_posix()
    document["models"] = list(MODEL_IDS)
    document["cost"] = cost_metadata()
    document["inventory_manifest"] = INVENTORY_MANIFEST_REL.as_posix()
    document["generation_manifest"] = GENERATION_MANIFEST_REL.as_posix()
    document["supersedes_failed_canary_batch_id"] = FAILED_CANARY_BATCH_ID
    return document


def _validate_original_component(document: Any) -> None:
    if not isinstance(document, dict):
        raise PipelineError("Original PROMOPAGES-9930 component is not an object")
    if (
        document.get("batch_id") != ORIGINAL_BATCH_ID
        or document.get("article_count") != EXPECTED_ARTICLES
        or document.get("image_count") != EXPECTED_IMAGES
        or document.get("expected_outputs") != 40
        or document.get("models")
        != [native.WAN_27_MODEL_ID, native.VEO_31_MODEL_ID]
        or not isinstance(document.get("outputs"), list)
        or len(document["outputs"]) != 40
    ):
        raise PipelineError("Original PROMOPAGES-9930 component changed")


def ensure_original_component(root: Path) -> dict[str, Any]:
    component_path = root / ORIGINAL_COMPONENT_REL
    if component_path.is_file():
        if sha256_file(component_path) != ORIGINAL_STABLE_MANIFEST_SHA256:
            raise PipelineError("Original 20x2 component bytes changed")
        document = read_json(component_path)
        _validate_original_component(document)
        return document
    stable_path = root / STABLE_MANIFEST_REL
    if sha256_file(stable_path) != ORIGINAL_STABLE_MANIFEST_SHA256:
        raise PipelineError(
            "Stable manifest is no longer the expected immutable 20x2 component"
        )
    document = read_json(stable_path)
    _validate_original_component(document)
    component_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = component_path.with_name(f".{component_path.name}.tmp")
    temporary.write_bytes(stable_path.read_bytes())
    temporary.replace(component_path)
    if sha256_file(component_path) != ORIGINAL_STABLE_MANIFEST_SHA256:
        raise PipelineError("Failed to preserve exact original component bytes")
    return document


def aggregate_document(
    original_component: dict[str, Any],
    sidecar: dict[str, Any],
    *,
    root: Path,
    updated_at: str | None = None,
) -> dict[str, Any]:
    _validate_original_component(original_component)
    if (
        sidecar.get("batch_id") != BATCH_ID
        or sidecar.get("models") != list(MODEL_IDS)
        or sidecar.get("expected_outputs") != EXPECTED_OUTPUTS
        or sidecar.get("accepted_output_count") != EXPECTED_OUTPUTS
        or sidecar.get("conforming_output_count") != EXPECTED_OUTPUTS
    ):
        raise PipelineError("Wan 2.2 sidecar is incomplete or non-conforming")

    wan_articles = {
        article["article_slug"]: article for article in sidecar.get("articles", [])
    }
    aggregate = copy.deepcopy(original_component)
    all_outputs: list[dict[str, Any]] = []
    for article in aggregate["articles"]:
        wan_article = wan_articles.get(article.get("article_slug"))
        if not isinstance(wan_article, dict):
            raise PipelineError(
                f"Missing Wan 2.2 article: {article.get('article_slug')}"
            )
        old_images = article.get("images")
        wan_images = wan_article.get("images")
        if (
            not isinstance(old_images, list)
            or len(old_images) != 1
            or not isinstance(wan_images, list)
            or len(wan_images) != 1
        ):
            raise PipelineError("Aggregate components have incompatible image sets")
        old_image = old_images[0]
        wan_image = wan_images[0]
        if (
            old_image.get("image", {}).get("sha256")
            != wan_image.get("image", {}).get("sha256")
        ):
            raise PipelineError("Aggregate source image binding changed")
        old_outputs = old_image.get("outputs")
        wan_outputs = wan_image.get("outputs")
        if not isinstance(old_outputs, list) or not isinstance(wan_outputs, list):
            raise PipelineError("Aggregate component outputs are missing")
        ordered = wan_outputs + old_outputs
        if [output.get("model_id") for output in ordered] != list(ALL_MODEL_IDS):
            raise PipelineError("Aggregate model order or identity changed")
        old_image["wan22_lite_planning"] = wan_image.get("lite_planning")
        old_image["outputs"] = ordered
        all_outputs.extend(ordered)

    if len(all_outputs) != EXPECTED_AGGREGATE_OUTPUTS:
        raise PipelineError("Aggregate does not contain 60 outputs")
    keys = {
        (row.get("article_slug"), row.get("image_id"), row.get("model_id"))
        for row in all_outputs
    }
    if len(keys) != EXPECTED_AGGREGATE_OUTPUTS:
        raise PipelineError("Aggregate output keys are not unique")
    audit = original.output_acceptance_audit(
        all_outputs,
        root=root,
        allow_contract_warnings=True,
    )
    if audit["accepted_output_count"] != EXPECTED_AGGREGATE_OUTPUTS:
        raise PipelineError("Aggregate contains unaccepted outputs")
    status_summary: dict[str, int] = {}
    for output in all_outputs:
        status = str(output.get("status") or "missing")
        status_summary[status] = status_summary.get(status, 0) + 1

    aggregate.update(
        {
            "schema_version": 1,
            "manifest_role": "one-new-image-per-article-extension",
            "ticket": TICKET,
            "batch_id": AGGREGATE_BATCH_ID,
            "agent_id": AGENT_ID,
            "updated_at": updated_at or transport.utc_now(),
            "models": list(ALL_MODEL_IDS),
            "article_count": EXPECTED_ARTICLES,
            "image_count": EXPECTED_IMAGES,
            "new_unique_image_count": EXPECTED_IMAGES,
            "expected_outputs": EXPECTED_AGGREGATE_OUTPUTS,
            "cost": cost_metadata(),
            "status_summary": status_summary,
            "acceptance_policy": {
                "allow_contract_warnings": True,
                "accepted_complete_statuses": [
                    "succeeded",
                    "verification-failed",
                ],
                "preserve_recorded_status": True,
                "requires_mp4_and_media": True,
                "wan22_requires_strict_conformance": True,
            },
            **audit,
            "component_manifests": [
                ORIGINAL_COMPONENT_REL.as_posix(),
                SIDECAR_MANIFEST_REL.as_posix(),
            ],
            "planning_batch_ids": [
                ORIGINAL_BATCH_ID,
                PLANNING_BATCH_ID,
            ],
            "generation_batch_ids": [
                ORIGINAL_BATCH_ID,
                BATCH_ID,
            ],
            "inventory_manifest": ORIGINAL_INVENTORY_REL.as_posix(),
            "generation_manifests": [
                (
                    Path("clipmaker-lite-test/runs")
                    / ORIGINAL_BATCH_ID
                    / "generation-manifest.json"
                ).as_posix(),
                GENERATION_MANIFEST_REL.as_posix(),
            ],
            "outputs": all_outputs,
        }
    )
    return aggregate


def finalize(
    articles: Iterable[original.Article],
    sources: Iterable[Source],
    *,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    original_component = ensure_original_component(root)
    sidecar = _sidecar_document(articles, sources, root=root)
    with original_bindings():
        sidecar_errors = original.final_output_acceptance_errors(
            sidecar,
            root=root,
            allow_contract_warnings=False,
        )
    if sidecar_errors:
        raise PipelineError(
            f"Cannot finalize Wan 2.2 sidecar: {sidecar_errors[0]}"
        )
    transport.atomic_write_json(root / SIDECAR_MANIFEST_REL, sidecar)
    aggregate = aggregate_document(original_component, sidecar, root=root)
    transport.atomic_write_json(root / STABLE_MANIFEST_REL, aggregate)
    return sidecar, aggregate


def verify_all(
    articles: Iterable[original.Article],
    sources: Iterable[Source],
    *,
    root: Path,
    allow_incomplete: bool,
) -> tuple[bool, list[str]]:
    articles = tuple(articles)
    sources = tuple(sources)
    errors: list[str] = []
    if not (root / INVENTORY_MANIFEST_REL).is_file() or read_json(
        root / INVENTORY_MANIFEST_REL
    ) != inventory_document(articles, sources):
        errors.append("Wan 2.2 inventory does not match the frozen selection")

    configure_native(sources, root)
    native_ok, native_errors = native.verify(
        root,
        allow_incomplete=allow_incomplete,
        allow_contract_warnings=False,
    )
    if not native_ok:
        errors.extend(native_errors)

    sidecar_path = root / SIDECAR_MANIFEST_REL
    stable_path = root / STABLE_MANIFEST_REL
    component_path = root / ORIGINAL_COMPONENT_REL
    if not allow_incomplete:
        if not sidecar_path.is_file():
            errors.append(f"Missing sidecar manifest: {SIDECAR_MANIFEST_REL}")
        if not component_path.is_file():
            errors.append(f"Missing original component: {ORIGINAL_COMPONENT_REL}")
        if not stable_path.is_file():
            errors.append(f"Missing aggregate manifest: {STABLE_MANIFEST_REL}")
    if sidecar_path.is_file() and component_path.is_file() and stable_path.is_file():
        actual_sidecar = read_json(sidecar_path)
        sidecar_updated = actual_sidecar.get("updated_at")
        rebuilt_sidecar = (
            _sidecar_document(
                articles,
                sources,
                root=root,
                updated_at=sidecar_updated,
            )
            if isinstance(sidecar_updated, str)
            else None
        )
        if rebuilt_sidecar is None or actual_sidecar != rebuilt_sidecar:
            errors.append("Wan 2.2 sidecar does not match current artifacts")
        actual_aggregate = read_json(stable_path)
        aggregate_updated = actual_aggregate.get("updated_at")
        rebuilt_aggregate = (
            aggregate_document(
                read_json(component_path),
                actual_sidecar,
                root=root,
                updated_at=aggregate_updated,
            )
            if isinstance(aggregate_updated, str)
            else None
        )
        if rebuilt_aggregate is None or actual_aggregate != rebuilt_aggregate:
            errors.append("Stable aggregate does not match both components")

    report = {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "passed": not errors,
        "allow_incomplete": allow_incomplete,
        "article_count": len(articles),
        "image_count": len(sources),
        "expected_outputs": EXPECTED_OUTPUTS,
        "aggregate_expected_outputs": EXPECTED_AGGREGATE_OUTPUTS,
        "errors": errors,
    }
    transport.atomic_write_json(root / VERIFICATION_REPORT_REL, report)
    return not errors, errors


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--dry-run", action="store_true")

    prepare = subparsers.add_parser("prepare-plans")
    prepare.add_argument("--dry-run", action="store_true")

    run_plans = subparsers.add_parser("run-plans")
    run_plans.add_argument("--concurrency", type=positive_int, default=3)
    run_plans.add_argument("--timeout", type=positive_int, default=1800)
    run_plans.add_argument("--author-model")
    run_plans.add_argument("--dry-run", action="store_true")
    run_plans.add_argument("--allow-external-processing", action="store_true")

    plan_generation = subparsers.add_parser("plan-generation")
    plan_generation.add_argument("--dry-run", action="store_true")

    generate = subparsers.add_parser("generate")
    generate.add_argument("--canary", action="store_true")
    generate.add_argument("--timeout", type=positive_int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--fail-fast", action="store_true")

    subparsers.add_parser("finalize")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        articles, sources = discover(root)
        if args.command == "inventory":
            document = inventory_document(articles, sources)
            if not args.dry_run:
                write_inventory(articles, sources, root)
            print(
                f"PASS: {document['image_count']} frozen images, "
                f"{document['expected_outputs']} Wan 2.2 outputs"
            )
            return 0

        if not getattr(args, "dry_run", False):
            write_inventory(articles, sources, root)

        if args.command == "prepare-plans":
            counts = prepare_planning_runs(sources, root=root, dry_run=args.dry_run)
            print(
                "PASS: "
                + " ".join(f"{key}={value}" for key, value in counts.items())
            )
            return 0
        if args.command == "run-plans":
            return run_planning_runs(
                sources,
                root=root,
                concurrency=args.concurrency,
                timeout=args.timeout,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                author_model=args.author_model,
            )
        if args.command == "plan-generation":
            return materialize_generation(
                sources,
                root=root,
                dry_run=args.dry_run,
            )
        if args.command == "generate":
            return run_generation(
                sources,
                root=root,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                canary=args.canary,
                fail_fast=args.fail_fast,
            )
        if args.command == "finalize":
            sidecar, aggregate = finalize(articles, sources, root=root)
            print(
                f"PASS: Wan sidecar={sidecar['expected_outputs']}; "
                f"aggregate={aggregate['expected_outputs']}"
            )
            return 0
        if args.command == "verify":
            passed, errors = verify_all(
                articles,
                sources,
                root=root,
                allow_incomplete=args.allow_incomplete,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: PROMOPAGES-9930 Wan 2.2 add-on and aggregate are valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except (
        PipelineError,
        original.PipelineError,
        native.BatchPipelineError,
        runner.LiteRunnerError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
