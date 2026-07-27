#!/usr/bin/env python3
"""Run the isolated Clipmaker Lite case 21 / image 04 experiment.

This coordinator is intentionally separate from the historical 20x3 and 20x2
manifests.  It binds one collected PromoPages image to its full article
context, prepares one shared three-model Lite planning run, delegates provider
work to the native bridge, and writes ``clipmaker-lite-test/case-21-manifest.json``.

Normal runs use only the exact local generation-route registry.  The three
provider pools start together with capacities 1/3/3, automatic fallback and
route discovery stay disabled, and every immutable provider entry may submit
at most once.  Images or prompts leave the workspace only when the operator
passes ``--allow-external-processing``.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
AGENT_ID = "clipmaker-lite"
CASE_NUMBER = "21"
ARTICLE_SLUG = "21-maier-doctor-zolotoe-vremia"
ARTICLE_URL = (
    "https://maier-doctor.promo.page/media/"
    "35-vashe-zolotoe-vremia-chtoby-sohranit-molodost-"
    "6a6328e396062011505ab621_0_0"
)
IMAGE_ID = "04"
IMAGE_FILENAME = "04.png"
SOURCE_BLOCK_INDEX = 33
SOURCE_PATH = (
    Path("PROMOPAGES-9857/articles") / ARTICLE_SLUG / IMAGE_FILENAME
)
CONTEXT_PATH = (
    Path("PROMOPAGES-9884/articles") / ARTICLE_SLUG / "content.json"
)
SOURCE_MANIFEST_PATH = Path("PROMOPAGES-9857/articles/manifest.csv")
EXPECTED_SOURCE_SHA256 = (
    "c42c39e7fd2243c37abe014acc8d901ea5e8751dedd82273cf409cc4b2591b6b"
)
EXPECTED_SOURCE_IMAGE_ID = "6a6328f345a595396555e61a"
EXPECTED_ORIG_URL = (
    "https://avatars.mds.yandex.net/get-promoarticles/7545082/"
    "pub_6a6328e396062011505ab621_6a6328f345a595396555e61a/orig"
)
EXPECTED_CONTEXT_SHA256 = (
    "a95143fb2ab46087a51ac734465618a34eaab5abb022c3f753caefdefa7c44ce"
)
EXPECTED_IMAGE_COUNT = 8

MODEL_IDS = (
    native.WAN_MODEL_ID,
    native.WAN_27_MODEL_ID,
    native.VEO_31_MODEL_ID,
)
PLANNING_RUN_ID = "promopages-9930-case21-maier-20260727-v4"
PROVIDER_BATCH_ID = "promopages-9930-case21-maier-runs-20260727-v1"
RETRY_PROVIDER_BATCH_ID = (
    "promopages-9930-case21-maier-retry-wan27-veo-20260727-v1"
)
SAMPLE_ID = f"{ARTICLE_SLUG}-{IMAGE_ID}"
RETRY_MODEL_IDS = (
    native.WAN_27_MODEL_ID,
    native.VEO_31_MODEL_ID,
)

ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")
CONTRACT_PATH = Path("docs/agents/clipmaker-lite/contract.json")
ROUTES_PATH = Path("docs/agents/clipmaker-lite/generation-routes.json")
BATCH_ROOT = Path("clipmaker-lite-test/runs") / PROVIDER_BATCH_ID
INVENTORY_PATH = BATCH_ROOT / "inventory.json"
GENERATION_MANIFEST_PATH = BATCH_ROOT / "generation-manifest.json"
RETRY_BATCH_ROOT = Path("clipmaker-lite-test/runs") / RETRY_PROVIDER_BATCH_ID
RETRY_INVENTORY_PATH = RETRY_BATCH_ROOT / "inventory.json"
RETRY_GENERATION_MANIFEST_PATH = RETRY_BATCH_ROOT / "generation-manifest.json"
FINAL_MANIFEST_PATH = Path("clipmaker-lite-test/case-21-manifest.json")

ROUTE_CAPACITIES = {
    native.WAN_MODEL_ID: 1,
    native.WAN_27_MODEL_ID: 3,
    native.VEO_31_MODEL_ID: 3,
}
HARD_BUDGET_CAP_USD = Decimal("1.50")
RETRY_HARD_BUDGET_CAP_USD = Decimal("1.00")
EXPECTED_OUTPUTS = len(MODEL_IDS)
MAX_PAID_SUBMISSIONS = EXPECTED_OUTPUTS
RETRY_EXPECTED_OUTPUTS = len(RETRY_MODEL_IDS)
RETRY_MAX_PAID_SUBMISSIONS = RETRY_EXPECTED_OUTPUTS
PUBLIC_RAW_BASE = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/main/"
)


class PipelineError(RuntimeError):
    """A fail-closed case-21 orchestration error."""


@contextmanager
def batch_run_lock(inventory_path: Path) -> Iterator[None]:
    """Admit only one real planning/provider coordinator for this namespace."""

    if not inventory_path.is_file() or inventory_path.is_symlink():
        raise PipelineError(f"Case-21 inventory cannot be locked: {inventory_path}")
    with inventory_path.open("rb") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError(
                "another case-21 coordinator already holds the immutable batch lock"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class CaseSample(native.Sample):
    """Native sample with the exact shared Lite planning identity."""

    @property
    def planning_run_id(self) -> str:
        return PLANNING_RUN_ID


@dataclass(frozen=True)
class CaseSource:
    article_number: str
    article_slug: str
    title: str
    lead: str
    url: str
    context_path: str
    context_sha256: str
    context_bytes: int
    provider_source_url: str
    image: dict[str, Any]
    images: tuple[dict[str, Any], ...]

    @property
    def sample(self) -> CaseSample:
        return CaseSample(
            sample_id=SAMPLE_ID,
            article_slug=self.article_slug,
            image_id=self.image["image_id"],
            filename=self.image["file"],
            source_sha256=self.image["sha256"],
            width=self.image["width"],
            height=self.image["height"],
        )


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


def _safe_relative(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value:
        raise PipelineError(f"{label} must be a non-empty workspace-relative path")
    return path


def validate_public_orig_url(
    value: Any,
    *,
    source_image_id: Any,
    source_sha256: Any,
) -> str:
    """Bind the provider-fetchable MDS URL to the exact collected image 04."""

    if (
        source_image_id != EXPECTED_SOURCE_IMAGE_ID
        or source_sha256 != EXPECTED_SOURCE_SHA256
    ):
        raise PipelineError("MDS /orig URL is not bound to the exact image-04 source")
    if not isinstance(value, str) or value != EXPECTED_ORIG_URL:
        raise PipelineError("Case-21 image 04 must use its exact manifest MDS /orig URL")
    parsed = urlsplit(value)
    expected_path = (
        "/get-promoarticles/7545082/"
        f"pub_6a6328e396062011505ab621_{EXPECTED_SOURCE_IMAGE_ID}/orig"
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname != "avatars.mds.yandex.net"
        or parsed.netloc != "avatars.mds.yandex.net"
        or parsed.path != expected_path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
    ):
        raise PipelineError("Case-21 provider source URL is not a trusted MDS /orig URL")
    return value


def _manifest_rows(root: Path) -> tuple[dict[str, str], ...]:
    path = root / SOURCE_MANIFEST_PATH
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = tuple(
                row
                for row in csv.DictReader(stream)
                if row.get("article_number") == CASE_NUMBER
            )
    except OSError as exc:
        raise PipelineError(f"Cannot read source manifest {path}: {exc}") from exc
    if len(rows) != EXPECTED_IMAGE_COUNT:
        raise PipelineError(
            f"Case 21 must contain {EXPECTED_IMAGE_COUNT} manifest images; "
            f"found {len(rows)}"
        )
    image_numbers = [row.get("image_number") for row in rows]
    expected_numbers = [f"{index:02d}" for index in range(1, 9)]
    if image_numbers != expected_numbers:
        raise PipelineError(
            f"Case 21 manifest image order changed: {image_numbers!r}"
        )
    return rows


def _image_record(root: Path, row: dict[str, str]) -> dict[str, Any]:
    image_id = row.get("image_number")
    expected_path = f"articles/{ARTICLE_SLUG}/{image_id}.png"
    if (
        row.get("article_number") != CASE_NUMBER
        or row.get("article_url") != ARTICLE_URL
        or row.get("file_path") != expected_path
        or row.get("download_status") != "ok"
        or row.get("actual_format") != "PNG"
    ):
        raise PipelineError(f"Invalid case-21 manifest binding: {row!r}")
    try:
        width = int(row["actual_width"])
        height = int(row["actual_height"])
        byte_size = int(row["byte_size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"Invalid image metadata for {expected_path}") from exc
    if width < 1 or height < 1 or byte_size < 1:
        raise PipelineError(f"Non-positive image metadata for {expected_path}")
    source_path = root / "PROMOPAGES-9857" / expected_path
    if not source_path.is_file() or source_path.is_symlink():
        raise PipelineError(f"Source image is missing or unsafe: {source_path}")
    digest = sha256_file(source_path)
    if digest != row.get("sha256") or source_path.stat().st_size != byte_size:
        raise PipelineError(f"Source image bytes differ from manifest: {source_path}")
    return {
        "image_id": image_id,
        "file": f"{image_id}.png",
        "role": row.get("image_role"),
        "source_block_index": int(row["block_index"]) if row.get("block_index") else None,
        "source_image_id": row.get("image_id"),
        "manifest_file_path": expected_path,
        "source_path": f"PROMOPAGES-9857/{expected_path}",
        "sha256": digest,
        "bytes": byte_size,
        "width": width,
        "height": height,
        "duplicate_of": row.get("duplicate_of") or None,
    }


def discover_case(root: Path = ROOT) -> CaseSource:
    """Validate all collected case-21 materials and bind exact image 04."""

    root = root.resolve()
    manifest_rows = _manifest_rows(root)
    images = tuple(_image_record(root, row) for row in manifest_rows)
    context_path = root / CONTEXT_PATH
    if not context_path.is_file() or context_path.is_symlink():
        raise PipelineError(f"Article context is missing or unsafe: {context_path}")
    context_sha256 = sha256_file(context_path)
    if context_sha256 != EXPECTED_CONTEXT_SHA256:
        raise PipelineError(
            f"Case-21 article context digest changed: {context_sha256}"
        )
    document = read_json(context_path)
    if not isinstance(document, dict) or not isinstance(document.get("blocks"), list):
        raise PipelineError("Case-21 content.json must contain an ordered blocks array")
    if (
        document.get("article_id") != ARTICLE_SLUG
        or str(document.get("article_number")) != CASE_NUMBER
        or document.get("canonical_url") != ARTICLE_URL
        or not isinstance(document.get("title"), str)
        or not document["title"].strip()
        or not isinstance(document.get("lead"), str)
        or not document["lead"].strip()
    ):
        raise PipelineError("Case-21 article identity or editorial context changed")

    blocks = [
        block
        for block in document["blocks"]
        if isinstance(block, dict) and block.get("type") == "image"
    ]
    if len(blocks) != EXPECTED_IMAGE_COUNT:
        raise PipelineError(
            f"Case-21 content must bind {EXPECTED_IMAGE_COUNT} image blocks"
        )
    by_id = {image["image_id"]: image for image in images}
    if len(by_id) != EXPECTED_IMAGE_COUNT:
        raise PipelineError("Case-21 manifest image IDs are not unique")
    for block, image in zip(blocks, images):
        expected = {
            "image_id": image["image_id"],
            "file": image["file"],
            "manifest_file_path": image["manifest_file_path"],
            "role": image["role"],
            "source_image_id": image["source_image_id"],
            "source_block_index": image["source_block_index"],
            "duplicate_of": image["duplicate_of"],
        }
        actual = {key: block.get(key) for key in expected}
        if actual != expected:
            raise PipelineError(
                f"Case-21 content/manifest image binding changed for "
                f"{image['image_id']}: {actual!r}"
            )

    selected = by_id.get(IMAGE_ID)
    if selected is None:
        raise PipelineError("Case-21 image 04 is absent")
    if (
        selected["source_path"] != SOURCE_PATH.as_posix()
        or selected["source_block_index"] != SOURCE_BLOCK_INDEX
        or selected["role"] != "article_image"
        or selected["source_image_id"] != EXPECTED_SOURCE_IMAGE_ID
        or selected["sha256"] != EXPECTED_SOURCE_SHA256
    ):
        raise PipelineError("Case-21 image 04 source binding changed")
    selected_row = next(
        row for row in manifest_rows if row.get("image_number") == IMAGE_ID
    )
    provider_source_url = validate_public_orig_url(
        selected_row.get("orig_url"),
        source_image_id=selected.get("source_image_id"),
        source_sha256=selected.get("sha256"),
    )
    return CaseSource(
        article_number=CASE_NUMBER,
        article_slug=ARTICLE_SLUG,
        title=document["title"].strip(),
        lead=document["lead"].strip(),
        url=ARTICLE_URL,
        context_path=CONTEXT_PATH.as_posix(),
        context_sha256=context_sha256,
        context_bytes=context_path.stat().st_size,
        provider_source_url=provider_source_url,
        image=selected,
        images=images,
    )


def validate_routes() -> dict[str, dict[str, Any]]:
    policy = transport.GENERATION_ROUTE_DOCUMENT.get("policy")
    if policy != {
        "resolution": "exact-model-id",
        "automatic_fallback": False,
        "normal_run_discovery": False,
        "forbidden_discovery_paths": [
            "/videos/models",
            "/gradio_api/info",
            "/config",
        ],
    }:
        raise PipelineError("Generation route policy changed")
    expected = {
        native.WAN_MODEL_ID: {
            "adapter": "wan-demo",
            "transport": "gradio-legacy-queue",
            "capacity": 1,
        },
        native.WAN_27_MODEL_ID: {
            "adapter": "eliza-openrouter",
            "transport": "eliza-video-jobs",
            "capacity": 3,
            "provider_key": "atlas-cloud",
        },
        native.VEO_31_MODEL_ID: {
            "adapter": "eliza-openrouter",
            "transport": "eliza-video-jobs",
            "capacity": 3,
            "provider_key": "google-vertex",
        },
    }
    routes: dict[str, dict[str, Any]] = {}
    for model_id in MODEL_IDS:
        route = transport.route_for_model(model_id)
        for key, value in expected[model_id].items():
            if route.get(key) != value:
                raise PipelineError(
                    f"Exact route changed for {model_id}: {key}={route.get(key)!r}"
                )
        routes[model_id] = route
    return routes


def parse_budget(value: str | float | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise PipelineError(f"Invalid USD budget: {value!r}") from exc
    if budget <= 0:
        raise PipelineError("Budget cap must be positive")
    if budget > HARD_BUDGET_CAP_USD:
        raise PipelineError(
            f"Configured ${budget:.2f} budget exceeds the hard "
            f"${HARD_BUDGET_CAP_USD:.2f} cap"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except PipelineError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_retry_budget(value: str | float | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise PipelineError(f"Invalid retry USD budget: {value!r}") from exc
    if budget <= 0:
        raise PipelineError("Retry budget cap must be positive")
    if budget > RETRY_HARD_BUDGET_CAP_USD:
        raise PipelineError(
            f"Configured retry ${budget:.2f} budget exceeds the hard "
            f"${RETRY_HARD_BUDGET_CAP_USD:.2f} retry cap"
        )
    return budget


def retry_budget_arg(value: str) -> Decimal:
    try:
        return parse_retry_budget(value)
    except PipelineError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def cost_metadata(budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD) -> dict[str, Any]:
    budget = parse_budget(budget_cap_usd)
    return {
        "currency": "USD",
        "configured_budget_cap_usd": float(budget),
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "planned_paid_submissions": EXPECTED_OUTPUTS,
        "maximum_paid_submissions": MAX_PAID_SUBMISSIONS,
        "automatic_paid_retries": False,
        "provider_unit_costs_asserted": False,
        "enforcement": (
            "one immutable provider entry per exact model; terminal, stale, "
            "ambiguous, or failed entries cannot resubmit in this namespace"
        ),
    }


def retry_cost_metadata(
    budget_cap_usd: str | float | Decimal,
) -> dict[str, Any]:
    budget = parse_retry_budget(budget_cap_usd)
    return {
        "currency": "USD",
        "configured_budget_cap_usd": float(budget),
        "hard_budget_cap_usd": float(RETRY_HARD_BUDGET_CAP_USD),
        "planned_paid_submissions": RETRY_EXPECTED_OUTPUTS,
        "maximum_paid_submissions": RETRY_MAX_PAID_SUBMISSIONS,
        "automatic_paid_retries": False,
        "provider_unit_costs_asserted": False,
        "authorization_scope": (
            "one explicit submit each for alibaba/wan-2.7 and "
            "google/veo-3.1-lite in the retry namespace only"
        ),
        "enforcement": (
            "two immutable retry entries; terminal, stale, ambiguous, or "
            "failed entries cannot resubmit in this namespace"
        ),
    }


def inventory_document(
    source: CaseSource,
    budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD,
) -> dict[str, Any]:
    routes = validate_routes()
    return {
        "schema_version": 1,
        "manifest_role": "case-21-source-binding",
        "ticket": TICKET,
        "case_number": CASE_NUMBER,
        "batch_id": PROVIDER_BATCH_ID,
        "planning_run_id": PLANNING_RUN_ID,
        "agent_id": AGENT_ID,
        "models": list(MODEL_IDS),
        "expected_outputs": EXPECTED_OUTPUTS,
        "cost": cost_metadata(budget_cap_usd),
        "generation_policy": {
            "route_resolution": "exact-model-id",
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "automatic_retries": False,
            "route_capacities": {
                model_id: int(routes[model_id]["capacity"])
                for model_id in MODEL_IDS
            },
        },
        "article": {
            "article_number": source.article_number,
            "article_slug": source.article_slug,
            "title": source.title,
            "lead": source.lead,
            "url": source.url,
            "context": {
                "path": source.context_path,
                "sha256": source.context_sha256,
                "bytes": source.context_bytes,
            },
            "collected_image_count": len(source.images),
            "images": list(source.images),
            "selected_image": source.image,
            "selection_rule": "exact collected image_id 04 at source block 33",
        },
    }


def write_inventory(
    source: CaseSource,
    root: Path = ROOT,
    budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD,
) -> dict[str, Any]:
    document = inventory_document(source, budget_cap_usd)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise PipelineError(f"Immutable case-21 inventory differs: {path}")
        return document
    if path.exists():
        raise PipelineError(f"Inventory target is not a regular file: {path}")
    transport.atomic_write_json(path, document)
    return document


def planning_prepare_command(root: Path = ROOT) -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts/clipmaker_lite_runner.py"),
        "prepare",
        "--run-id",
        PLANNING_RUN_ID,
        "--image",
        SOURCE_PATH.as_posix(),
        "--context",
        CONTEXT_PATH.as_posix(),
        "--image-id",
        IMAGE_ID,
    ]
    for model_id in MODEL_IDS:
        command.extend(("--model", model_id))
    return command


def _validate_prepared(source: CaseSource, root: Path) -> None:
    job, selection, _directory = runner.validate_prepared_job(root, PLANNING_RUN_ID)
    selected_ids = [
        item.get("model_id") for item in selection.get("selected_models", [])
    ]
    if selected_ids != list(MODEL_IDS):
        raise PipelineError("Prepared case-21 Lite model order changed")
    inputs = job.get("inputs")
    image = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    locator = context.get("locator") if isinstance(context, dict) else None
    if (
        not isinstance(image, dict)
        or image.get("path") != source.image["source_path"]
        or image.get("sha256") != source.image["sha256"]
        or not isinstance(context, dict)
        or context.get("path") != source.context_path
        or context.get("sha256") != source.context_sha256
        or not isinstance(locator, dict)
        or locator.get("article_id") != ARTICLE_SLUG
        or locator.get("image_id") != IMAGE_ID
        or locator.get("block_index") != 34
        or locator.get("manifest_file_path")
        != f"articles/{ARTICLE_SLUG}/{IMAGE_FILENAME}"
    ):
        raise PipelineError("Prepared case-21 Lite source/context binding changed")


def _validated_planning(source: CaseSource, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = runner.provenance_summary(root, PLANNING_RUN_ID)
    expected_result_path = (
        ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
    ).as_posix()
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("models") != list(MODEL_IDS)
        or summary.get("source_image_sha256") != source.image["sha256"]
        or summary.get("article_context_sha256") != source.context_sha256
        or summary.get("result_path") != expected_result_path
    ):
        raise PipelineError("Case-21 Lite provenance does not match the bound run")
    result = read_json(root / expected_result_path)
    if result.get("job_id") != PLANNING_RUN_ID:
        raise PipelineError("Case-21 Lite result identity changed")
    analysis = result.get("analysis")
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(not isinstance(intent.get(key), str) or not intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS)
    ):
        raise PipelineError("Case-21 shared structured_intent is invalid")
    models = result.get("models")
    if (
        not isinstance(models, list)
        or [model.get("model_id") for model in models if isinstance(model, dict)]
        != list(MODEL_IDS)
    ):
        raise PipelineError("Case-21 Lite result model order changed")
    return summary, result


def planning_state(source: CaseSource, root: Path = ROOT) -> str | None:
    directory = root / ARTIFACT_NAMESPACE / PLANNING_RUN_ID
    result_path = directory / "result.json"
    job_path = directory / "job.json"
    if result_path.is_file():
        _validated_planning(source, root)
        return "verified"
    if job_path.is_file():
        _validate_prepared(source, root)
        return "prepared"
    if directory.exists() or directory.is_symlink():
        raise PipelineError(f"Incomplete or unsafe immutable Lite run: {directory}")
    return None


def prepare_planning_run(
    source: CaseSource,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> str:
    state = planning_state(source, root)
    if state is not None:
        return state
    if dry_run:
        return "would-prepare"
    completed = subprocess.run(
        planning_prepare_command(root),
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        detail = transport.safe_error(completed.stderr or completed.stdout)
        raise PipelineError(f"Case-21 Lite prepare failed: {detail}")
    if planning_state(source, root) != "prepared":
        raise PipelineError("Runner did not create the exact combined Lite job")
    return "prepared"


def run_planning(
    source: CaseSource,
    *,
    root: Path = ROOT,
    timeout: int = 1800,
    author_model: str | None = None,
    dry_run: bool = False,
    allow_external_processing: bool = False,
) -> int:
    state = planning_state(source, root)
    if state == "verified":
        print(f"planning {PLANNING_RUN_ID} -> existing-verified")
        return 0
    if dry_run:
        prepare_state = prepare_planning_run(source, root=root, dry_run=True)
        print(f"planning {PLANNING_RUN_ID} -> {prepare_state}; would-run")
        return 0
    if not allow_external_processing:
        raise PipelineError(
            "Real Lite planning requires --allow-external-processing because "
            "image 04 and the article context are sent to isolated Codex"
        )
    with batch_run_lock(root / INVENTORY_PATH):
        # Recheck after acquiring the cross-process lock: another coordinator
        # may have completed this immutable planning job while we waited.
        if planning_state(source, root) == "verified":
            print(f"planning {PLANNING_RUN_ID} -> existing-verified")
            return 0
        prepare_planning_run(source, root=root, dry_run=False)
        command = [
            sys.executable,
            str(root / "scripts/clipmaker_lite_runner.py"),
            "run",
            "--run-id",
            PLANNING_RUN_ID,
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
            raise PipelineError(f"Case-21 Lite planning timed out: {exc}") from exc
        if completed.returncode:
            detail = transport.safe_error(completed.stderr or completed.stdout)
            raise PipelineError(
                "Case-21 Lite planning failed; the immutable namespace will not "
                f"be retried automatically: {detail}"
            )
        if planning_state(source, root) != "verified":
            raise PipelineError("Case-21 Lite planning provenance is not verified")
    print(f"planning {PLANNING_RUN_ID} -> verified")
    return 0


def _artifact_paths(entry: native.Entry, root: Path) -> dict[str, Path]:
    base = (
        root
        / BATCH_ROOT
        / "videos"
        / ARTICLE_SLUG
        / native.MODEL_DIRECTORIES[entry.model_id]
    )
    return {
        "directory": base,
        "prompt": base / f"{IMAGE_ID}.prompt.json",
        "run": base / f"{IMAGE_ID}.run.json",
        "video": base / f"{IMAGE_ID}.mp4",
    }


def _retry_artifact_paths(entry: native.Entry, root: Path) -> dict[str, Path]:
    if entry.model_id not in RETRY_MODEL_IDS:
        raise PipelineError(
            f"Model {entry.model_id!r} is forbidden in the case-21 retry namespace"
        )
    base = (
        root
        / RETRY_BATCH_ROOT
        / "videos"
        / ARTICLE_SLUG
        / native.MODEL_DIRECTORIES[entry.model_id]
    )
    return {
        "directory": base,
        "prompt": base / f"{IMAGE_ID}.prompt.json",
        "run": base / f"{IMAGE_ID}.run.json",
        "video": base / f"{IMAGE_ID}.mp4",
    }


def _provider_run_id(batch_id: str, model_id: str) -> str:
    try:
        suffix = native.MODEL_SUFFIXES[model_id]
    except KeyError as exc:
        raise PipelineError(f"Unsupported case-21 model: {model_id}") from exc
    return f"{batch_id}-{SAMPLE_ID}-{suffix}"


def _manifest_artifact_paths(
    batch_root: Path,
    model_id: str,
) -> dict[str, Path]:
    if model_id not in MODEL_IDS:
        raise PipelineError(f"Unsupported case-21 model: {model_id}")
    base = (
        batch_root
        / "videos"
        / ARTICLE_SLUG
        / native.MODEL_DIRECTORIES[model_id]
    )
    return {
        "prompt": base / f"{IMAGE_ID}.prompt.json",
        "run": base / f"{IMAGE_ID}.run.json",
        "video": base / f"{IMAGE_ID}.mp4",
        "review": base / f"{IMAGE_ID}.review.json",
    }


@contextmanager
def configured_native(source: CaseSource, root: Path = ROOT) -> Iterator[None]:
    """Temporarily bind the native bridge to the one-image three-model case."""

    validate_routes()
    names = (
        "BATCH_ID",
        "PLANNING_BATCH_ID",
        "MODEL_IDS",
        "PLANNING_MODEL_IDS",
        "TICKET",
        "MANIFEST_PATH",
        "CONTRACT_PATH",
        "PLANNING_WORKSPACE",
        "PLANNING_PROVENANCE_VERIFIER",
        "SAMPLES",
        "WAN_SUBMIT_MODE",
        "artifact_paths",
    )
    saved = {name: getattr(native, name) for name in names}
    try:
        native.BATCH_ID = PROVIDER_BATCH_ID
        native.PLANNING_BATCH_ID = PLANNING_RUN_ID
        native.MODEL_IDS = MODEL_IDS
        native.PLANNING_MODEL_IDS = MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = GENERATION_MANIFEST_PATH
        native.CONTRACT_PATH = root / CONTRACT_PATH
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = None
        native.SAMPLES = (source.sample,)
        native.WAN_SUBMIT_MODE = None

        def paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
            return _artifact_paths(entry, workspace)

        native.artifact_paths = paths
        matrix = native.matrix()
        if (
            len(matrix) != EXPECTED_OUTPUTS
            or [entry.model_id for entry in matrix] != list(MODEL_IDS)
            or any(entry.planning_run_id != PLANNING_RUN_ID for entry in matrix)
        ):
            raise PipelineError("Native case-21 matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


@contextmanager
def configured_retry_native(
    source: CaseSource,
    root: Path = ROOT,
) -> Iterator[None]:
    """Bind the native bridge to a new two-model, MDS-backed retry namespace."""

    validate_routes()
    trusted_orig_url = validate_public_orig_url(
        source.provider_source_url,
        source_image_id=source.image.get("source_image_id"),
        source_sha256=source.image.get("sha256"),
    )
    names = (
        "BATCH_ID",
        "PLANNING_BATCH_ID",
        "MODEL_IDS",
        "PLANNING_MODEL_IDS",
        "TICKET",
        "MANIFEST_PATH",
        "CONTRACT_PATH",
        "PLANNING_WORKSPACE",
        "PLANNING_PROVENANCE_VERIFIER",
        "SAMPLES",
        "WAN_SUBMIT_MODE",
        "artifact_paths",
        "provider_sample",
    )
    saved = {name: getattr(native, name) for name in names}
    try:
        native.BATCH_ID = RETRY_PROVIDER_BATCH_ID
        native.PLANNING_BATCH_ID = PLANNING_RUN_ID
        native.MODEL_IDS = RETRY_MODEL_IDS
        # The verified Lite planning result remains the canonical three-model
        # result. Only provider generation is narrowed to the two retry models.
        native.PLANNING_MODEL_IDS = MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = RETRY_GENERATION_MANIFEST_PATH
        native.CONTRACT_PATH = root / CONTRACT_PATH
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = None
        native.SAMPLES = (source.sample,)
        native.WAN_SUBMIT_MODE = None

        def paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
            return _retry_artifact_paths(entry, workspace)

        def provider_sample(entry: native.Entry) -> dict[str, Any]:
            if (
                entry.model_id not in RETRY_MODEL_IDS
                or entry.sample.sample_id != SAMPLE_ID
                or entry.sample.source_sha256 != EXPECTED_SOURCE_SHA256
            ):
                raise PipelineError("Retry provider sample identity changed")
            return {
                "sample_id": entry.sample.sample_id,
                "article_slug": entry.sample.article_slug,
                "image_id": entry.sample.image_id,
                "image_number": entry.sample.image_id,
                "source_path": entry.sample.source_path,
                "source_url": trusted_orig_url,
                "sha256": entry.sample.source_sha256,
                "width": entry.sample.width,
                "height": entry.sample.height,
            }

        native.artifact_paths = paths
        native.provider_sample = provider_sample
        matrix = native.matrix()
        if (
            len(matrix) != RETRY_EXPECTED_OUTPUTS
            or [entry.model_id for entry in matrix] != list(RETRY_MODEL_IDS)
            or any(entry.planning_run_id != PLANNING_RUN_ID for entry in matrix)
            or any(
                entry.provider_run_id
                != _provider_run_id(RETRY_PROVIDER_BATCH_ID, entry.model_id)
                for entry in matrix
            )
            or any(entry.model_id == native.WAN_MODEL_ID for entry in matrix)
        ):
            raise PipelineError("Native case-21 retry matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def materialize_generation(
    source: CaseSource,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    _validated_planning(source, root)
    with configured_native(source, root):
        if dry_run:
            for entry in native.matrix():
                native.load_lite_job(entry, root)
            print("PASS: validated 3 case-21 provider jobs; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != EXPECTED_OUTPUTS:
        raise PipelineError(f"Expected 3 provider jobs, materialized {len(rows)}")
    print("PASS: materialized 3 provider jobs from one shared Lite plan")
    return 0


def _retry_state_errors(source: CaseSource, root: Path) -> list[str]:
    errors: list[str] = []
    with configured_native(source, root):
        for entry in native.matrix():
            path = native.artifact_paths(entry, root)["run"]
            if not path.is_file():
                continue
            run = read_json(path)
            if not isinstance(run, dict):
                errors.append(f"Run receipt is not an object: {path}")
                continue
            if any(run.get(key) for key in ("retry_of", "retry_count", "attempts")):
                errors.append(f"Retry metadata is forbidden: {path}")
            if run.get("provider_run_id") != entry.provider_run_id:
                errors.append(f"Provider run identity changed: {path}")
    return errors


def _generation_outputs_by_model(
    generation: Any,
    *,
    batch_id: str,
    model_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(generation, dict):
        raise PipelineError(f"Generation manifest {batch_id} is not an object")
    outputs = generation.get("outputs")
    if (
        generation.get("batch_id") != batch_id
        or generation.get("agent_id") != AGENT_ID
        or generation.get("expected_outputs") != len(model_ids)
        or not isinstance(outputs, list)
        or len(outputs) != len(model_ids)
    ):
        raise PipelineError(f"Generation manifest identity changed: {batch_id}")
    result: dict[str, dict[str, Any]] = {}
    for output in outputs:
        if not isinstance(output, dict):
            raise PipelineError(f"Generation output is not an object: {batch_id}")
        model_id = output.get("model_id")
        if model_id not in model_ids or model_id in result:
            raise PipelineError(
                f"Generation manifest has an unexpected/duplicate model: {model_id}"
            )
        result[str(model_id)] = output
    if list(result) != list(model_ids):
        raise PipelineError(f"Generation model order changed: {batch_id}")
    return result


def _first_frame_url(request: Any, label: str) -> str:
    frames = request.get("frame_images") if isinstance(request, dict) else None
    if not isinstance(frames, list) or len(frames) != 1:
        raise PipelineError(f"{label}: expected exactly one first-frame image")
    frame = frames[0]
    image_url = frame.get("image_url") if isinstance(frame, dict) else None
    value = image_url.get("url") if isinstance(image_url, dict) else None
    if (
        frame.get("type") != "image_url"
        or frame.get("frame_type") != "first_frame"
        or not isinstance(value, str)
    ):
        raise PipelineError(f"{label}: invalid first-frame request")
    return value


def _validated_attempt(
    output: dict[str, Any],
    *,
    root: Path,
    batch_id: str,
    batch_root: Path,
    expected_source_url: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    model_id = output.get("model_id")
    if model_id not in MODEL_IDS:
        raise PipelineError(f"Attempt has unsupported model: {model_id}")
    expected_paths = _manifest_artifact_paths(batch_root, str(model_id))
    expected_provider_run_id = _provider_run_id(batch_id, str(model_id))
    expected_values = {
        "lite_run_id": PLANNING_RUN_ID,
        "provider_run_id": expected_provider_run_id,
        "sample_id": SAMPLE_ID,
        "article_slug": ARTICLE_SLUG,
        "source_path": SOURCE_PATH.as_posix(),
        "prompt_path": expected_paths["prompt"].as_posix(),
        "run_path": expected_paths["run"].as_posix(),
        "video_path": expected_paths["video"].as_posix(),
    }
    for key, value in expected_values.items():
        if output.get(key) != value:
            raise PipelineError(
                f"{expected_provider_run_id}: output {key} binding changed"
            )
    run_path = root / expected_paths["run"]
    prompt_path = root / expected_paths["prompt"]
    if (
        not run_path.is_file()
        or run_path.is_symlink()
        or not prompt_path.is_file()
        or prompt_path.is_symlink()
    ):
        raise PipelineError(f"{expected_provider_run_id}: receipt is missing or unsafe")
    run = read_json(run_path)
    prompt = read_json(prompt_path)
    if not isinstance(run, dict):
        raise PipelineError(f"{expected_provider_run_id}: run receipt is not an object")
    if not isinstance(prompt, dict):
        raise PipelineError(f"{expected_provider_run_id}: prompt receipt is not an object")
    planning_result_path = (
        root / ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
    )
    planning_result = read_json(planning_result_path)
    planning_models = planning_result.get("models")
    if not isinstance(planning_models, list):
        raise PipelineError(f"{expected_provider_run_id}: Lite models are missing")
    planning_model = next(
        (
            item
            for item in planning_models
            if isinstance(item, dict) and item.get("model_id") == model_id
        ),
        None,
    )
    analysis = planning_result.get("analysis")
    structured_intent = (
        analysis.get("structured_intent") if isinstance(analysis, dict) else None
    )
    if (
        not isinstance(planning_model, dict)
        or prompt.get("schema_version") != 2
        or prompt.get("ticket") != TICKET
        or prompt.get("batch_id") != batch_id
        or prompt.get("agent_id") != AGENT_ID
        or prompt.get("lite_run_id") != PLANNING_RUN_ID
        or prompt.get("provider_run_id") != expected_provider_run_id
        or prompt.get("model_id") != model_id
        or prompt.get("source")
        != {
            "path": SOURCE_PATH.as_posix(),
            "sha256": EXPECTED_SOURCE_SHA256,
            "width": 1024,
            "height": 1024,
        }
        or prompt.get("structured_intent") != structured_intent
        or prompt.get("prompt")
        != {
            "positive": planning_model.get("positive_prompt"),
            "negative": planning_model.get("negative_prompt"),
        }
        or prompt.get("runtime") != planning_model.get("runtime")
        or prompt.get("lite_result", {}).get("sha256")
        != sha256_file(planning_result_path)
    ):
        raise PipelineError(
            f"{expected_provider_run_id}: prompt differs from verified Lite result"
        )
    run_identity = {
        "ticket": TICKET,
        "batch_id": batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": PLANNING_RUN_ID,
        "provider_run_id": expected_provider_run_id,
        "sample_id": SAMPLE_ID,
        "image_id": IMAGE_ID,
        "model_id": model_id,
        "lite_result_sha256": sha256_file(
            root / ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
        ),
    }
    for key, value in run_identity.items():
        if run.get(key) != value:
            raise PipelineError(
                f"{expected_provider_run_id}: run receipt {key} binding changed"
            )
    recorded_status = run.get("status")
    effective_status = native.effective_run_status(run)
    if (
        output.get("recorded_status") != recorded_status
        or output.get("status") != effective_status
        or output.get("provider_may_be_active")
        != run.get("provider_may_be_active")
        or output.get("media") != run.get("media")
        or output.get("contract_check") != run.get("contract_check")
        or output.get("error") != run.get("error")
    ):
        raise PipelineError(
            f"{expected_provider_run_id}: aggregate output differs from receipt"
        )
    if any(run.get(key) for key in ("retry_of", "retry_count", "attempts")):
        raise PipelineError(
            f"{expected_provider_run_id}: mutable retry metadata is forbidden"
        )
    request = run.get("request")
    positive_prompt = planning_model.get("positive_prompt")
    request_prompt = (
        request.get("input", {}).get("prompt")
        if model_id == native.WAN_MODEL_ID and isinstance(request, dict)
        else request.get("prompt") if isinstance(request, dict) else None
    )
    if request_prompt != positive_prompt:
        raise PipelineError(
            f"{expected_provider_run_id}: provider prompt differs from Lite result"
        )
    if expected_source_url is not None:
        if _first_frame_url(request, expected_provider_run_id) != expected_source_url:
            raise PipelineError(
                f"{expected_provider_run_id}: provider source URL changed"
            )
    sample = {
        "sample_id": SAMPLE_ID,
        "article_slug": ARTICLE_SLUG,
        "image_id": IMAGE_ID,
        "image_number": IMAGE_ID,
        "source_path": SOURCE_PATH.as_posix(),
        "source_url": expected_source_url
        or PUBLIC_RAW_BASE + quote(SOURCE_PATH.as_posix(), safe="/"),
        "sha256": EXPECTED_SOURCE_SHA256,
        "width": 1024,
        "height": 1024,
    }
    if (
        run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
        or run.get("request_sha256")
        != transport.request_fingerprint(request, sample)
    ):
        raise PipelineError(
            f"{expected_provider_run_id}: provider request fingerprint changed"
        )
    return run, expected_paths


def _parsed_veo_404_rejection(error: Any, expected_url: str) -> dict[str, Any]:
    if not isinstance(error, str) or " failed with HTTP 400: " not in error:
        raise PipelineError("Primary Veo receipt lacks the expected HTTP 400 rejection")
    raw_payload = error.split(" failed with HTTP 400: ", 1)[1]
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise PipelineError("Primary Veo HTTP 400 payload is not valid JSON") from exc
    response = payload.get("response") if isinstance(payload, dict) else None
    provider_error = response.get("error") if isinstance(response, dict) else None
    expected_message = (
        "Received 404 status code when fetching image from URL: " + expected_url
    )
    if (
        not isinstance(provider_error, dict)
        or provider_error.get("code") != 400
        or provider_error.get("message") != expected_message
        or payload.get("attempt_count") != 1
    ):
        raise PipelineError("Primary Veo receipt is not the exact raw-URL 404 rejection")
    return {
        "http_status": 400,
        "source_fetch_status": 404,
        "attempt_count": 1,
        "provider_job_created": False,
    }


def validate_primary_retry_eligibility(
    source: CaseSource,
    root: Path = ROOT,
) -> dict[str, dict[str, Any]]:
    """Prove the immutable v1 outcomes before admitting a separate retry."""

    if source.image["sha256"] != EXPECTED_SOURCE_SHA256:
        raise PipelineError("Primary retry eligibility source binding changed")
    generation = read_json(root / GENERATION_MANIFEST_PATH)
    outputs = _generation_outputs_by_model(
        generation,
        batch_id=PROVIDER_BATCH_ID,
        model_ids=MODEL_IDS,
    )
    raw_url = PUBLIC_RAW_BASE + quote(source.image["source_path"], safe="/")
    receipts: dict[str, dict[str, Any]] = {}
    paths_by_model: dict[str, dict[str, Path]] = {}
    for model_id in MODEL_IDS:
        expected_url = None if model_id == native.WAN_MODEL_ID else raw_url
        receipt, paths = _validated_attempt(
            outputs[model_id],
            root=root,
            batch_id=PROVIDER_BATCH_ID,
            batch_root=BATCH_ROOT,
            expected_source_url=expected_url,
        )
        receipts[model_id] = receipt
        paths_by_model[model_id] = paths

    wan22 = receipts[native.WAN_MODEL_ID]
    wan22_output = outputs[native.WAN_MODEL_ID]
    if (
        wan22.get("status") != "succeeded"
        or wan22.get("provider_may_be_active") is not False
        or _output_acceptance_error(
            wan22_output,
            root=root,
            allow_contract_warnings=False,
        )
        is not None
    ):
        raise PipelineError("Primary Wan 2.2 must remain a conforming success")

    wan27 = receipts[native.WAN_27_MODEL_ID]
    if (
        wan27.get("status") != "provider-failed"
        or wan27.get("provider_may_be_active") is not False
        or not isinstance(wan27.get("provider_job_id"), str)
        or not wan27["provider_job_id"]
        or not isinstance(wan27.get("submitted_at"), str)
        or not isinstance(wan27.get("completed_at"), str)
        or "failed with status failed: Failed to download" not in str(wan27.get("error"))
    ):
        raise PipelineError("Primary Wan 2.7 is not the exact terminal download failure")

    veo = receipts[native.VEO_31_MODEL_ID]
    rejection = _parsed_veo_404_rejection(veo.get("error"), raw_url)
    if (
        veo.get("status") != "submit-unknown"
        or veo.get("provider_may_be_active") is not True
        or veo.get("provider_job_id") is not None
        or veo.get("submitted_at") is not None
        or veo.get("completed_at") is not None
    ):
        raise PipelineError("Primary Veo state is not the exact pre-job 404 rejection")

    return {
        native.WAN_MODEL_ID: {
            "output": wan22_output,
            "receipt": wan22,
            "paths": paths_by_model[native.WAN_MODEL_ID],
            "eligibility": "reuse-primary-success; never retry",
        },
        native.WAN_27_MODEL_ID: {
            "output": outputs[native.WAN_27_MODEL_ID],
            "receipt": wan27,
            "paths": paths_by_model[native.WAN_27_MODEL_ID],
            "eligibility": "explicit-retry-after-terminal-provider-download-failure",
        },
        native.VEO_31_MODEL_ID: {
            "output": outputs[native.VEO_31_MODEL_ID],
            "receipt": veo,
            "paths": paths_by_model[native.VEO_31_MODEL_ID],
            "eligibility": "explicit-retry-after-pre-job-raw-url-404",
            "rejection_proof": rejection,
        },
    }


def run_generation(
    source: CaseSource,
    *,
    root: Path = ROOT,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD,
    dry_run: bool = False,
    allow_external_processing: bool = False,
) -> int:
    cost_metadata(budget_cap_usd)
    validate_routes()
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real generation requires --allow-external-processing because "
            "image 04 and Lite prompts are sent to the three exact providers"
        )
    argv = [
        "run",
        "--wan22-concurrency",
        "1",
        "--wan27-concurrency",
        "3",
        "--veo31-concurrency",
        "3",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
    ]
    argv.append("--dry-run" if dry_run else "--allow-external-processing")

    def invoke() -> int:
        _validated_planning(source, root)
        retry_errors = _retry_state_errors(source, root)
        if retry_errors:
            raise PipelineError("; ".join(retry_errors))
        with configured_native(source, root):
            # native.main owns every aggregate generation-manifest write;
            # provider workers only report outcomes to that one coordinator.
            return native.main(argv, root)

    if dry_run:
        return invoke()
    with batch_run_lock(root / INVENTORY_PATH):
        return invoke()


def _attempt_snapshot(
    model_id: str,
    *,
    batch_id: str,
    output: dict[str, Any],
    receipt: dict[str, Any],
    selected: bool,
    attempt_number: int,
) -> dict[str, Any]:
    return {
        "attempt_number": attempt_number,
        "batch_id": batch_id,
        "provider_run_id": output.get("provider_run_id"),
        "model_id": model_id,
        "status": output.get("status"),
        "recorded_status": output.get("recorded_status"),
        "provider_may_be_active": output.get("provider_may_be_active"),
        "request_sha256": receipt.get("request_sha256"),
        "provider_job_id": receipt.get("provider_job_id"),
        "submitted_at": receipt.get("submitted_at"),
        "completed_at": receipt.get("completed_at"),
        "prompt_path": output.get("prompt_path"),
        "run_path": output.get("run_path"),
        "video_path": output.get("video_path"),
        "selected_for_delivery": selected,
        "error": output.get("error"),
    }


def retry_inventory_document(
    source: CaseSource,
    *,
    root: Path = ROOT,
    retry_budget_cap_usd: str | float | Decimal,
) -> dict[str, Any]:
    validate_routes()
    if read_json(root / INVENTORY_PATH) != inventory_document(
        source,
        HARD_BUDGET_CAP_USD,
    ):
        raise PipelineError("Primary case-21 inventory differs from exact binding")
    primary = validate_primary_retry_eligibility(source, root)
    source_url = validate_public_orig_url(
        source.provider_source_url,
        source_image_id=source.image.get("source_image_id"),
        source_sha256=source.image.get("sha256"),
    )
    primary_attempts = [
        _attempt_snapshot(
            model_id,
            batch_id=PROVIDER_BATCH_ID,
            output=primary[model_id]["output"],
            receipt=primary[model_id]["receipt"],
            selected=model_id == native.WAN_MODEL_ID,
            attempt_number=1,
        )
        for model_id in MODEL_IDS
    ]
    return {
        "schema_version": 1,
        "manifest_role": "case-21-explicit-provider-retry",
        "ticket": TICKET,
        "case_number": CASE_NUMBER,
        "agent_id": AGENT_ID,
        "primary_batch_id": PROVIDER_BATCH_ID,
        "retry_batch_id": RETRY_PROVIDER_BATCH_ID,
        "planning_run_id": PLANNING_RUN_ID,
        "models": list(RETRY_MODEL_IDS),
        "expected_outputs": RETRY_EXPECTED_OUTPUTS,
        "excluded_models": [native.WAN_MODEL_ID],
        "cost": retry_cost_metadata(retry_budget_cap_usd),
        "source": {
            "image_id": IMAGE_ID,
            "source_image_id": source.image["source_image_id"],
            "path": source.image["source_path"],
            "sha256": source.image["sha256"],
            "bytes": source.image["bytes"],
            "width": source.image["width"],
            "height": source.image["height"],
            "provider_url": source_url,
            "provider_url_policy": {
                "scheme": "https",
                "hostname": "avatars.mds.yandex.net",
                "variant": "orig",
                "query_allowed": False,
                "fragment_allowed": False,
            },
        },
        "retry_policy": {
            "operator_initiated": True,
            "requires_allow_external_processing": True,
            "route_resolution": "exact-model-id",
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "automatic_retries": False,
            "maximum_submissions_per_model_in_namespace": 1,
            "primary_namespace_is_read_only": True,
            "wan22_resubmit_forbidden": True,
        },
        "primary_attempts": primary_attempts,
        "eligibility": {
            native.WAN_27_MODEL_ID: primary[native.WAN_27_MODEL_ID]["eligibility"],
            native.VEO_31_MODEL_ID: primary[native.VEO_31_MODEL_ID]["eligibility"],
            "veo_rejection_proof": primary[native.VEO_31_MODEL_ID][
                "rejection_proof"
            ],
        },
    }


def write_retry_inventory(
    source: CaseSource,
    *,
    root: Path = ROOT,
    retry_budget_cap_usd: str | float | Decimal,
) -> dict[str, Any]:
    document = retry_inventory_document(
        source,
        root=root,
        retry_budget_cap_usd=retry_budget_cap_usd,
    )
    path = root / RETRY_INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise PipelineError(f"Immutable case-21 retry inventory differs: {path}")
        return document
    if path.exists():
        raise PipelineError(f"Retry inventory target is not a regular file: {path}")
    transport.atomic_write_json(path, document)
    return document


def _retry_namespace_errors(source: CaseSource, root: Path) -> list[str]:
    errors: list[str] = []
    trusted_url = validate_public_orig_url(
        source.provider_source_url,
        source_image_id=source.image.get("source_image_id"),
        source_sha256=source.image.get("sha256"),
    )
    with configured_retry_native(source, root):
        matrix = native.matrix()
        if [entry.model_id for entry in matrix] != list(RETRY_MODEL_IDS):
            errors.append("Retry matrix does not contain exactly Wan 2.7 and Veo")
        for entry in matrix:
            path = native.artifact_paths(entry, root)["run"]
            if not path.is_file():
                continue
            run = read_json(path)
            if not isinstance(run, dict):
                errors.append(f"Retry receipt is not an object: {path}")
                continue
            if run.get("batch_id") != RETRY_PROVIDER_BATCH_ID:
                errors.append(f"Retry batch identity changed: {path}")
            if run.get("provider_run_id") != entry.provider_run_id:
                errors.append(f"Retry provider run identity changed: {path}")
            if any(run.get(key) for key in ("retry_of", "retry_count", "attempts")):
                errors.append(f"Mutable retry metadata is forbidden: {path}")
            request = run.get("request")
            if request is not None:
                try:
                    request_url = _first_frame_url(request, entry.provider_run_id)
                except PipelineError as exc:
                    errors.append(str(exc))
                else:
                    if request_url != trusted_url:
                        errors.append(
                            f"Retry request does not use exact MDS /orig: {path}"
                        )
    primary_wan22 = (
        root
        / _manifest_artifact_paths(BATCH_ROOT, native.WAN_MODEL_ID)["run"]
    )
    if not primary_wan22.is_file():
        errors.append("Primary Wan 2.2 receipt is missing")
    forbidden_retry_wan22 = (
        root
        / RETRY_BATCH_ROOT
        / "videos"
        / ARTICLE_SLUG
        / native.MODEL_DIRECTORIES[native.WAN_MODEL_ID]
    )
    if forbidden_retry_wan22.exists():
        errors.append("Wan 2.2 artifacts are forbidden in the retry namespace")
    return errors


def materialize_retry_generation(
    source: CaseSource,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    _validated_planning(source, root)
    validate_primary_retry_eligibility(source, root)
    errors = _retry_namespace_errors(source, root)
    if errors:
        raise PipelineError("; ".join(errors))
    with configured_retry_native(source, root):
        if dry_run:
            for entry in native.matrix():
                job = native.load_lite_job(entry, root)
                sample = native.provider_sample(entry)
                request = native.provider_request_preview(
                    sample,
                    native.provider_prompt(job),
                )
                if _first_frame_url(request, entry.provider_run_id) != EXPECTED_ORIG_URL:
                    raise PipelineError("Dry-run retry request lost exact MDS /orig")
            print("PASS: validated 2 MDS-backed retry jobs; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != RETRY_EXPECTED_OUTPUTS:
        raise PipelineError("Expected exactly 2 materialized retry provider jobs")
    print("PASS: materialized Wan 2.7 and Veo retry jobs in a new namespace")
    return 0


def run_retry_generation(
    source: CaseSource,
    *,
    root: Path = ROOT,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    retry_budget_cap_usd: str | float | Decimal,
    dry_run: bool = False,
    allow_external_processing: bool = False,
) -> int:
    """Run at most one explicit MDS-backed submit for each retry model."""

    retry_cost_metadata(retry_budget_cap_usd)
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real case-21 retry requires --allow-external-processing because "
            "image 04 and Lite prompts are sent to Wan 2.7 and Veo"
        )
    validate_routes()
    argv = [
        "run",
        "--wan22-concurrency",
        "1",
        "--wan27-concurrency",
        "3",
        "--veo31-concurrency",
        "3",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
        "--dry-run" if dry_run else "--allow-external-processing",
    ]

    def invoke() -> int:
        _validated_planning(source, root)
        errors = _retry_namespace_errors(source, root)
        if errors:
            raise PipelineError("; ".join(errors))
        with configured_retry_native(source, root):
            return native.main(argv, root)

    if dry_run:
        validate_primary_retry_eligibility(source, root)
        errors = _retry_namespace_errors(source, root)
        if errors:
            raise PipelineError("; ".join(errors))
        return invoke()

    # Lock the already-immutable primary inventory before first creating the
    # retry inventory. Locking a retry file created via atomic replace would
    # allow two simultaneous first runs to hold different inodes and submit
    # the same paid jobs twice.
    with batch_run_lock(root / INVENTORY_PATH):
        validate_primary_retry_eligibility(source, root)
        write_retry_inventory(
            source,
            root=root,
            retry_budget_cap_usd=retry_budget_cap_usd,
        )
        errors = _retry_namespace_errors(source, root)
        if errors:
            raise PipelineError("; ".join(errors))
        return invoke()


def _output_acceptance_error(
    output: Any,
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> str | None:
    if not isinstance(output, dict):
        return "generation output is not an object"
    label = str(output.get("provider_run_id") or "unknown output")
    status = output.get("status")
    accepted_statuses = (
        {"succeeded", "verification-failed"}
        if allow_contract_warnings
        else {"succeeded"}
    )
    if status not in accepted_statuses:
        return f"{label}: status {status!r} is not accepted"
    video_value = output.get("video_path")
    if not isinstance(video_value, str):
        return f"{label}: video_path is missing"
    video_path = root / _safe_relative(video_value, f"{label} video_path")
    if not video_path.is_file() or video_path.is_symlink():
        return f"{label}: MP4 is missing or unsafe"
    media = output.get("media")
    check = output.get("contract_check")
    if not isinstance(media, dict) or not isinstance(check, dict):
        return f"{label}: media or contract_check is missing"
    if media.get("sha256") != sha256_file(video_path):
        return f"{label}: MP4 digest differs from measured media"
    if media.get("bytes") != video_path.stat().st_size:
        return f"{label}: MP4 byte size differs from measured media"
    if status == "succeeded" and check.get("conforms") is not True:
        return f"{label}: succeeded output is non-conforming"
    if status == "verification-failed":
        warnings = check.get("warnings")
        if (
            check.get("conforms") is not False
            or not isinstance(warnings, list)
            or not warnings
        ):
            return f"{label}: contract warning details are missing"
    return None


def _validate_visual_review(
    output: dict[str, Any],
    *,
    source: CaseSource,
    root: Path,
) -> tuple[dict[str, Any], str]:
    model_id = output.get("model_id")
    provider_run_id = output.get("provider_run_id")
    video_value = output.get("video_path")
    if not isinstance(video_value, str):
        raise PipelineError(f"{provider_run_id}: video_path is missing")
    video_path = root / _safe_relative(video_value, "visual review video_path")
    review_path = video_path.with_name(f"{IMAGE_ID}.review.json")
    if not review_path.is_file() or review_path.is_symlink():
        raise PipelineError(
            f"{provider_run_id}: required visual review is missing or unsafe"
        )
    review = read_json(review_path)
    expected_top_level = {
        "schema_version",
        "ticket",
        "model_id",
        "provider_run_id",
        "lite_run_id",
        "source",
        "artifact",
        "review_method",
        "observations",
        "verdict",
    }
    if not isinstance(review, dict) or set(review) != expected_top_level:
        raise PipelineError(f"{provider_run_id}: visual review schema changed")
    if (
        review.get("schema_version") != 1
        or review.get("ticket") != TICKET
        or review.get("model_id") != model_id
        or review.get("provider_run_id") != provider_run_id
        or review.get("lite_run_id") != PLANNING_RUN_ID
        or review.get("source")
        != {
            "path": source.image["source_path"],
            "sha256": source.image["sha256"],
        }
        or review.get("artifact")
        != {
            "path": video_value,
            "sha256": sha256_file(video_path),
        }
    ):
        raise PipelineError(f"{provider_run_id}: visual review identity changed")
    review_method = review.get("review_method")
    if (
        not isinstance(review_method, dict)
        or set(review_method) != {"source_comparison", "technical_verification"}
        or any(
            not isinstance(review_method.get(key), str)
            or not review_method[key].strip()
            for key in review_method
        )
    ):
        raise PipelineError(f"{provider_run_id}: visual review method is invalid")
    observations = review.get("observations")
    if (
        not isinstance(observations, dict)
        or set(observations)
        != {
            "requested_motion",
            "camera",
            "stable_elements",
            "invariant_failures",
        }
        or not isinstance(observations.get("requested_motion"), str)
        or not observations["requested_motion"].strip()
        or not isinstance(observations.get("camera"), str)
        or not observations["camera"].strip()
        or not isinstance(observations.get("stable_elements"), list)
        or not observations["stable_elements"]
        or any(
            not isinstance(item, str) or not item.strip()
            for item in observations["stable_elements"]
        )
        or not isinstance(observations.get("invariant_failures"), list)
        or any(
            not isinstance(item, str) or not item.strip()
            for item in observations["invariant_failures"]
        )
    ):
        raise PipelineError(f"{provider_run_id}: visual review observations are invalid")
    verdict = review.get("verdict")
    if (
        not isinstance(verdict, dict)
        or set(verdict) != {"status", "summary"}
        or verdict.get("status") not in {"fidelity-passed", "fidelity-failed"}
        or not isinstance(verdict.get("summary"), str)
        or not verdict["summary"].strip()
    ):
        raise PipelineError(f"{provider_run_id}: visual review verdict is invalid")
    try:
        relative_review = review_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise PipelineError(f"{provider_run_id}: visual review escaped workspace") from exc
    return verdict, relative_review


def validate_retry_generation(
    source: CaseSource,
    generation: Any,
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> dict[str, dict[str, Any]]:
    outputs = _generation_outputs_by_model(
        generation,
        batch_id=RETRY_PROVIDER_BATCH_ID,
        model_ids=RETRY_MODEL_IDS,
    )
    trusted_url = validate_public_orig_url(
        source.provider_source_url,
        source_image_id=source.image.get("source_image_id"),
        source_sha256=source.image.get("sha256"),
    )
    result: dict[str, dict[str, Any]] = {}
    for model_id in RETRY_MODEL_IDS:
        output = outputs[model_id]
        receipt, paths = _validated_attempt(
            output,
            root=root,
            batch_id=RETRY_PROVIDER_BATCH_ID,
            batch_root=RETRY_BATCH_ROOT,
            expected_source_url=trusted_url,
        )
        acceptance_error = _output_acceptance_error(
            output,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        if acceptance_error:
            raise PipelineError(acceptance_error)
        if output.get("provider_may_be_active") is not False:
            raise PipelineError(
                f"{output.get('provider_run_id')}: completed retry still holds a slot"
            )
        result[model_id] = {
            "output": output,
            "receipt": receipt,
            "paths": paths,
        }
    forbidden = (
        root
        / RETRY_BATCH_ROOT
        / "videos"
        / ARTICLE_SLUG
        / native.MODEL_DIRECTORIES[native.WAN_MODEL_ID]
    )
    if forbidden.exists():
        raise PipelineError("Wan 2.2 artifacts are forbidden in the retry namespace")
    return result


def build_final_manifest(
    source: CaseSource,
    *,
    planning_summary: dict[str, Any],
    planning_result: dict[str, Any],
    primary_generation: dict[str, Any],
    retry_generation: dict[str, Any],
    root: Path = ROOT,
    budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD,
    retry_budget_cap_usd: str | float | Decimal,
    allow_contract_warnings: bool = False,
    updated_at: str | None = None,
) -> dict[str, Any]:
    expected_result_path = (
        ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
    ).as_posix()
    if (
        planning_summary.get("verified") is not True
        or planning_summary.get("agent_id") != AGENT_ID
        or planning_summary.get("models") != list(MODEL_IDS)
        or planning_summary.get("source_image_sha256") != source.image["sha256"]
        or planning_summary.get("article_context_sha256") != source.context_sha256
        or planning_summary.get("result_path") != expected_result_path
        or planning_result.get("job_id") != PLANNING_RUN_ID
    ):
        raise PipelineError("Case-21 final planning provenance binding changed")
    if read_json(root / GENERATION_MANIFEST_PATH) != primary_generation:
        raise PipelineError("Primary generation manifest argument differs from disk")
    if read_json(root / RETRY_GENERATION_MANIFEST_PATH) != retry_generation:
        raise PipelineError("Retry generation manifest argument differs from disk")
    primary = validate_primary_retry_eligibility(source, root)
    retry = validate_retry_generation(
        source,
        retry_generation,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    models = planning_result.get("models")
    if (
        not isinstance(models, list)
        or [model.get("model_id") for model in models if isinstance(model, dict)]
        != list(MODEL_IDS)
    ):
        raise PipelineError("Case-21 planning result models are missing")
    model_map = {
        item.get("model_id"): item for item in models if isinstance(item, dict)
    }
    provider_map = {
        native.WAN_MODEL_ID: primary[native.WAN_MODEL_ID]["output"],
        native.WAN_27_MODEL_ID: retry[native.WAN_27_MODEL_ID]["output"],
        native.VEO_31_MODEL_ID: retry[native.VEO_31_MODEL_ID]["output"],
    }
    attempt_history_by_model: dict[str, list[dict[str, Any]]] = {
        native.WAN_MODEL_ID: [
            _attempt_snapshot(
                native.WAN_MODEL_ID,
                batch_id=PROVIDER_BATCH_ID,
                output=primary[native.WAN_MODEL_ID]["output"],
                receipt=primary[native.WAN_MODEL_ID]["receipt"],
                selected=True,
                attempt_number=1,
            )
        ],
        native.WAN_27_MODEL_ID: [
            _attempt_snapshot(
                native.WAN_27_MODEL_ID,
                batch_id=PROVIDER_BATCH_ID,
                output=primary[native.WAN_27_MODEL_ID]["output"],
                receipt=primary[native.WAN_27_MODEL_ID]["receipt"],
                selected=False,
                attempt_number=1,
            ),
            _attempt_snapshot(
                native.WAN_27_MODEL_ID,
                batch_id=RETRY_PROVIDER_BATCH_ID,
                output=retry[native.WAN_27_MODEL_ID]["output"],
                receipt=retry[native.WAN_27_MODEL_ID]["receipt"],
                selected=True,
                attempt_number=2,
            ),
        ],
        native.VEO_31_MODEL_ID: [
            _attempt_snapshot(
                native.VEO_31_MODEL_ID,
                batch_id=PROVIDER_BATCH_ID,
                output=primary[native.VEO_31_MODEL_ID]["output"],
                receipt=primary[native.VEO_31_MODEL_ID]["receipt"],
                selected=False,
                attempt_number=1,
            ),
            _attempt_snapshot(
                native.VEO_31_MODEL_ID,
                batch_id=RETRY_PROVIDER_BATCH_ID,
                output=retry[native.VEO_31_MODEL_ID]["output"],
                receipt=retry[native.VEO_31_MODEL_ID]["receipt"],
                selected=True,
                attempt_number=2,
            ),
        ],
    }

    final_outputs: list[dict[str, Any]] = []
    warning_count = 0
    conforming_count = 0
    fidelity_passed = 0
    fidelity_failed = 0
    for model_id in MODEL_IDS:
        model = model_map.get(model_id)
        output = provider_map.get(model_id)
        if not isinstance(model, dict) or not isinstance(output, dict):
            raise PipelineError(f"Missing case-21 output binding for {model_id}")
        expected_batch = (
            PROVIDER_BATCH_ID
            if model_id == native.WAN_MODEL_ID
            else RETRY_PROVIDER_BATCH_ID
        )
        if (
            output.get("lite_run_id") != PLANNING_RUN_ID
            or output.get("provider_run_id")
            != _provider_run_id(expected_batch, model_id)
            or output.get("sample_id") != SAMPLE_ID
            or output.get("article_slug") != ARTICLE_SLUG
            or output.get("source_path") != source.image["source_path"]
        ):
            raise PipelineError(f"Case-21 provider identity changed for {model_id}")
        acceptance_error = _output_acceptance_error(
            output,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        if acceptance_error:
            raise PipelineError(acceptance_error)
        check = output["contract_check"]
        if check.get("conforms") is True:
            conforming_count += 1
        else:
            warning_count += 1
        video_path = str(output["video_path"])
        visual_review, review_path = _validate_visual_review(
            output,
            source=source,
            root=root,
        )
        if visual_review["status"] == "fidelity-passed":
            fidelity_passed += 1
        else:
            fidelity_failed += 1
        route = transport.route_for_model(model_id)
        final_outputs.append(
            {
                "article_slug": ARTICLE_SLUG,
                "image_id": IMAGE_ID,
                "source_path": source.image["source_path"],
                "sample_id": SAMPLE_ID,
                "lite_run_id": PLANNING_RUN_ID,
                "provider_run_id": output["provider_run_id"],
                "model_id": model_id,
                "scene_plan": model.get("scene_plan"),
                "positive_prompt": model.get("positive_prompt"),
                "negative_prompt": model.get("negative_prompt"),
                "status": output.get("status"),
                "recorded_status": output.get("recorded_status"),
                "prompt_path": output.get("prompt_path"),
                "run_path": output.get("run_path"),
                "video_path": video_path,
                "delivery": "repository-raw",
                "repository_raw_url": PUBLIC_RAW_BASE + quote(video_path, safe="/"),
                "route": {
                    "adapter": route["adapter"],
                    "transport": route["transport"],
                    "provider": route.get("provider_key") or "wan-streamlit",
                    "capacity": int(route["capacity"]),
                    "fallback": None,
                },
                "media": output.get("media"),
                "contract_check": check,
                "visual_review": visual_review,
                "review_path": review_path,
                "attempt_history": attempt_history_by_model[model_id],
                "error": output.get("error"),
            }
        )

    analysis = planning_result.get("analysis")
    structured_intent = (
        analysis.get("structured_intent") if isinstance(analysis, dict) else None
    )
    if not isinstance(structured_intent, dict):
        raise PipelineError("Case-21 shared structured_intent is missing")
    return {
        "schema_version": 1,
        "manifest_role": "case-21-extension",
        "ticket": TICKET,
        "case_number": CASE_NUMBER,
        "batch_id": PROVIDER_BATCH_ID,
        "retry_batch_id": RETRY_PROVIDER_BATCH_ID,
        "agent_id": AGENT_ID,
        "delivery": "repository-raw",
        "updated_at": updated_at or transport.utc_now(),
        "models": list(MODEL_IDS),
        "article_count": 1,
        "image_count": 1,
        "expected_outputs": EXPECTED_OUTPUTS,
        "accepted_output_count": len(final_outputs),
        "conforming_output_count": conforming_count,
        "contract_warning_output_count": warning_count,
        "visual_fidelity_passed_count": fidelity_passed,
        "visual_fidelity_failed_count": fidelity_failed,
        "cost": cost_metadata(budget_cap_usd),
        "retry_cost": retry_cost_metadata(retry_budget_cap_usd),
        "generation_policy": {
            "route_resolution": "exact-model-id",
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "automatic_retries": False,
            "explicit_retry_models": list(RETRY_MODEL_IDS),
            "wan22_retry_forbidden": True,
            "route_capacities": dict(ROUTE_CAPACITIES),
        },
        "acceptance_policy": {
            "allow_contract_warnings": allow_contract_warnings,
            "requires_repository_mp4": True,
            "requires_measured_sha256_and_bytes": True,
        },
        "inventory_manifest": INVENTORY_PATH.as_posix(),
        "generation_manifest": GENERATION_MANIFEST_PATH.as_posix(),
        "retry_inventory_manifest": RETRY_INVENTORY_PATH.as_posix(),
        "retry_generation_manifest": RETRY_GENERATION_MANIFEST_PATH.as_posix(),
        "attempt_history": [
            attempt
            for model_id in MODEL_IDS
            for attempt in attempt_history_by_model[model_id]
        ],
        "planning": {
            "run_id": PLANNING_RUN_ID,
            "result_path": planning_summary.get("result_path"),
            "shared_structured_intent": structured_intent,
            "provenance": planning_summary,
        },
        "articles": [
            {
                "article_number": source.article_number,
                "article_slug": source.article_slug,
                "title": source.title,
                "lead": source.lead,
                "url": source.url,
                "context_path": source.context_path,
                "collected_image_count": len(source.images),
                "images": [
                    {
                        "image": {
                            **source.image,
                            "delivery": "repository-raw",
                        },
                        "delivery": "repository-raw",
                        "repository_raw_url": PUBLIC_RAW_BASE
                        + quote(source.image["source_path"], safe="/"),
                        "outputs": final_outputs,
                    }
                ],
            }
        ],
        "outputs": final_outputs,
    }


def finalize(
    source: CaseSource,
    *,
    root: Path = ROOT,
    budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD,
    retry_budget_cap_usd: str | float | Decimal,
    allow_contract_warnings: bool = False,
) -> dict[str, Any]:
    planning_summary, planning_result = _validated_planning(source, root)
    expected_retry_inventory = retry_inventory_document(
        source,
        root=root,
        retry_budget_cap_usd=retry_budget_cap_usd,
    )
    if read_json(root / RETRY_INVENTORY_PATH) != expected_retry_inventory:
        raise PipelineError("Case-21 retry inventory differs from exact binding")
    primary_generation = read_json(root / GENERATION_MANIFEST_PATH)
    retry_generation = read_json(root / RETRY_GENERATION_MANIFEST_PATH)
    document = build_final_manifest(
        source,
        planning_summary=planning_summary,
        planning_result=planning_result,
        primary_generation=primary_generation,
        retry_generation=retry_generation,
        root=root,
        budget_cap_usd=budget_cap_usd,
        retry_budget_cap_usd=retry_budget_cap_usd,
        allow_contract_warnings=allow_contract_warnings,
    )
    transport.atomic_write_json(root / FINAL_MANIFEST_PATH, document)
    return document


def verify(
    source: CaseSource,
    *,
    root: Path = ROOT,
    budget_cap_usd: str | float | Decimal = HARD_BUDGET_CAP_USD,
    retry_budget_cap_usd: str | float | Decimal = RETRY_HARD_BUDGET_CAP_USD,
    allow_incomplete: bool = False,
    allow_contract_warnings: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    expected_inventory = inventory_document(source, budget_cap_usd)
    inventory_path = root / INVENTORY_PATH
    if inventory_path.is_file() and read_json(inventory_path) != expected_inventory:
        errors.append("Case-21 inventory differs from current exact binding")
    elif not inventory_path.is_file() and not allow_incomplete:
        errors.append("Case-21 inventory is missing")

    try:
        state = planning_state(source, root)
    except Exception as exc:
        errors.append(transport.safe_error(exc))
        state = None
    if state != "verified" and not allow_incomplete:
        errors.append("Combined case-21 Lite planning run is not verified")

    primary_generation_path = root / GENERATION_MANIFEST_PATH
    if state == "verified" and primary_generation_path.is_file():
        try:
            validate_primary_retry_eligibility(source, root)
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif state == "verified" and not allow_incomplete:
        errors.append("Case-21 primary generation manifest is missing")

    retry_inventory_path = root / RETRY_INVENTORY_PATH
    if retry_inventory_path.is_file():
        try:
            expected_retry_inventory = retry_inventory_document(
                source,
                root=root,
                retry_budget_cap_usd=retry_budget_cap_usd,
            )
            if read_json(retry_inventory_path) != expected_retry_inventory:
                errors.append("Case-21 retry inventory differs from current binding")
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Case-21 retry inventory is missing")

    retry_generation_path = root / RETRY_GENERATION_MANIFEST_PATH
    if retry_generation_path.is_file():
        try:
            validate_retry_generation(
                source,
                read_json(retry_generation_path),
                root=root,
                allow_contract_warnings=allow_contract_warnings,
            )
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Case-21 retry generation manifest is missing")

    final_path = root / FINAL_MANIFEST_PATH
    if final_path.is_file():
        try:
            actual = read_json(final_path)
            planning_summary, planning_result = _validated_planning(source, root)
            primary_generation = read_json(root / GENERATION_MANIFEST_PATH)
            retry_generation = read_json(root / RETRY_GENERATION_MANIFEST_PATH)
            updated_at = actual.get("updated_at") if isinstance(actual, dict) else None
            rebuilt = build_final_manifest(
                source,
                planning_summary=planning_summary,
                planning_result=planning_result,
                primary_generation=primary_generation,
                retry_generation=retry_generation,
                root=root,
                budget_cap_usd=budget_cap_usd,
                retry_budget_cap_usd=retry_budget_cap_usd,
                allow_contract_warnings=allow_contract_warnings,
                updated_at=updated_at if isinstance(updated_at, str) else None,
            )
            if actual != rebuilt:
                errors.append("Case-21 final manifest differs from current artifacts")
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Case-21 final manifest is missing")
    return not errors, errors


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be numeric") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _add_budget(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--budget-cap-usd",
        type=budget_arg,
        default=HARD_BUDGET_CAP_USD,
        metavar="USD",
        help="operator cap for this immutable 3-output namespace (maximum: 1.50)",
    )


def _add_retry_budget(
    parser: argparse.ArgumentParser,
    *,
    required: bool = True,
) -> None:
    parser.add_argument(
        "--retry-budget-cap-usd",
        type=retry_budget_arg,
        required=required,
        metavar="USD",
        help=(
            "separate operator cap for the immutable Wan 2.7 + Veo retry "
            "namespace (maximum: 1.00)"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser(
        "inventory", help="validate and freeze all case-21 materials plus image 04"
    )
    inventory.add_argument("--dry-run", action="store_true")
    _add_budget(inventory)

    prepare = subparsers.add_parser(
        "prepare-plans", help="prepare the one shared three-model Lite job"
    )
    prepare.add_argument("--dry-run", action="store_true")
    _add_budget(prepare)

    run_plans = subparsers.add_parser(
        "run-plans", help="run the isolated combined Lite planning job once"
    )
    run_plans.add_argument("--timeout", type=positive_int, default=1800)
    run_plans.add_argument("--author-model")
    run_plans.add_argument("--dry-run", action="store_true")
    run_plans.add_argument("--allow-external-processing", action="store_true")
    _add_budget(run_plans)

    plan_generation = subparsers.add_parser(
        "plan-generation", help="materialize the three native provider jobs"
    )
    plan_generation.add_argument("--dry-run", action="store_true")
    _add_budget(plan_generation)

    generate = subparsers.add_parser(
        "generate", help="run the exact Wan 2.2 / Wan 2.7 / Veo route pools"
    )
    generate.add_argument("--timeout", type=positive_int, default=1800)
    generate.add_argument("--poll-interval", type=positive_float, default=10.0)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--allow-external-processing", action="store_true")
    _add_budget(generate)

    retry_inventory = subparsers.add_parser(
        "retry-inventory",
        help=(
            "validate primary outcomes and freeze the explicit Wan 2.7 + Veo "
            "retry namespace"
        ),
    )
    retry_inventory.add_argument("--dry-run", action="store_true")
    _add_retry_budget(retry_inventory)

    retry_plan = subparsers.add_parser(
        "retry-plan-generation",
        help="materialize only the two MDS-backed retry provider jobs",
    )
    retry_plan.add_argument("--dry-run", action="store_true")
    _add_retry_budget(retry_plan)

    retry_generate = subparsers.add_parser(
        "retry-generate",
        help=(
            "explicitly submit Wan 2.7 and Veo once each in the retry namespace"
        ),
    )
    retry_generate.add_argument("--timeout", type=positive_int, default=1800)
    retry_generate.add_argument(
        "--poll-interval", type=positive_float, default=10.0
    )
    retry_generate.add_argument("--dry-run", action="store_true")
    retry_generate.add_argument(
        "--allow-external-processing",
        action="store_true",
    )
    _add_retry_budget(retry_generate)

    finalize_parser = subparsers.add_parser(
        "finalize", help="write clipmaker-lite-test/case-21-manifest.json"
    )
    finalize_parser.add_argument("--allow-contract-warnings", action="store_true")
    _add_budget(finalize_parser)
    _add_retry_budget(finalize_parser)

    verify_parser = subparsers.add_parser(
        "verify", help="verify exact source, planning, provider, and delivery bindings"
    )
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    verify_parser.add_argument("--allow-contract-warnings", action="store_true")
    _add_budget(verify_parser)
    _add_retry_budget(verify_parser)
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        source = discover_case(root)
        validate_routes()
        if hasattr(args, "budget_cap_usd"):
            cost_metadata(args.budget_cap_usd)
        if hasattr(args, "retry_budget_cap_usd"):
            retry_cost_metadata(args.retry_budget_cap_usd)

        if args.command == "inventory":
            document = inventory_document(source, args.budget_cap_usd)
            if not args.dry_run:
                write_inventory(source, root, args.budget_cap_usd)
            print(
                "PASS: case 21 binds 8 collected images, image 04, "
                f"and {document['expected_outputs']} planned outputs"
            )
            return 0

        if (
            args.command
            not in {
                "verify",
                "retry-inventory",
                "retry-plan-generation",
                "retry-generate",
            }
            and not getattr(args, "dry_run", False)
        ):
            write_inventory(source, root, args.budget_cap_usd)

        if args.command == "prepare-plans":
            state = prepare_planning_run(source, root=root, dry_run=args.dry_run)
            print(f"PASS: {PLANNING_RUN_ID} -> {state}")
            return 0
        if args.command == "run-plans":
            return run_planning(
                source,
                root=root,
                timeout=args.timeout,
                author_model=args.author_model,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
            )
        if args.command == "plan-generation":
            return materialize_generation(source, root=root, dry_run=args.dry_run)
        if args.command == "generate":
            return run_generation(
                source,
                root=root,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                budget_cap_usd=args.budget_cap_usd,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
            )
        if args.command == "retry-inventory":
            document = retry_inventory_document(
                source,
                root=root,
                retry_budget_cap_usd=args.retry_budget_cap_usd,
            )
            if not args.dry_run:
                write_retry_inventory(
                    source,
                    root=root,
                    retry_budget_cap_usd=args.retry_budget_cap_usd,
                )
            print(
                "PASS: retry namespace binds exact MDS /orig and "
                f"{document['expected_outputs']} explicit provider entries"
            )
            return 0
        if args.command == "retry-plan-generation":
            if not args.dry_run:
                write_retry_inventory(
                    source,
                    root=root,
                    retry_budget_cap_usd=args.retry_budget_cap_usd,
                )
            return materialize_retry_generation(
                source,
                root=root,
                dry_run=args.dry_run,
            )
        if args.command == "retry-generate":
            return run_retry_generation(
                source,
                root=root,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                retry_budget_cap_usd=args.retry_budget_cap_usd,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
            )
        if args.command == "finalize":
            document = finalize(
                source,
                root=root,
                budget_cap_usd=args.budget_cap_usd,
                retry_budget_cap_usd=args.retry_budget_cap_usd,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            print(
                f"PASS: {FINAL_MANIFEST_PATH} contains "
                f"{document['accepted_output_count']} repository-raw outputs"
            )
            return 0
        if args.command == "verify":
            passed, errors = verify(
                source,
                root=root,
                budget_cap_usd=args.budget_cap_usd,
                retry_budget_cap_usd=args.retry_budget_cap_usd,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: case-21 Clipmaker Lite pipeline is valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except (
        PipelineError,
        runner.LiteRunnerError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
