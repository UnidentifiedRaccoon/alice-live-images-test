#!/usr/bin/env python3
"""Run the PROMOPAGES-9930 Clipmaker Lite one-new-image extension batch.

The existing PROMOPAGES-9910 manifest and UI remain immutable.  This
orchestrator deterministically selects the first post-cover image in each of 20
articles whose SHA-256 is absent from every already processed cover and every
earlier selection. It delegates the 20x2 matrix to the locked Lite runner and
native provider bridge, without route discovery or fallback to Wan 2.2.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
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

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
BATCH_ID = "promopages-9930-lite20-new-images-20260726-v2"
AGENT_ID = "clipmaker-lite"
MODEL_IDS = (native.WAN_27_MODEL_ID, native.VEO_31_MODEL_ID)

EXPECTED_ARTICLES = 20
EXPECTED_SOURCE_ROWS = 125
EXPECTED_SELECTED_IMAGES = 20
EXPECTED_SOURCE_DUPLICATES = 6
EXPECTED_IMAGES = 20
EXPECTED_OUTPUTS = EXPECTED_IMAGES * len(MODEL_IDS)
BASE_ESTIMATED_COST_USD = 14.0
HARD_BUDGET_CAP_USD = 20.0
ESTIMATED_COST_PER_OUTPUT_USD = BASE_ESTIMATED_COST_USD / EXPECTED_OUTPUTS
MAX_PAID_SUBMISSIONS = EXPECTED_OUTPUTS

SOURCE_IMAGE_ROOT = Path("PROMOPAGES-9857/articles")
SOURCE_CONTEXT_ROOT = Path("PROMOPAGES-9884/articles")
SOURCE_MANIFEST_REL = SOURCE_IMAGE_ROOT / "manifest.csv"
BASE_MANIFEST_REL = Path("clipmaker-lite-test/manifest.json")
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
INVENTORY_MANIFEST_REL = BATCH_ROOT_REL / "inventory.json"
GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"
VERIFICATION_REPORT_REL = BATCH_ROOT_REL / "verification-report.json"
FINAL_MANIFEST_REL = Path("clipmaker-lite-test/promopages-9930-manifest.json")
CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")


class PipelineError(RuntimeError):
    """A fail-closed PROMOPAGES-9930 orchestration error."""


@contextmanager
def manifest_run_lock(manifest_path: Path):
    """Allow only one real planning/generation coordinator for this batch."""

    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PipelineError(f"Batch inventory cannot be locked: {manifest_path}")
    with manifest_path.open("rb") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError(
                "another PROMOPAGES-9930 process already holds the batch run lock"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@dataclass(frozen=True)
class Article:
    slug: str
    number: str
    title: str
    lead: str
    context_path: str
    context_sha256: str
    selected_image: dict[str, Any]
    images: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Source:
    article_slug: str
    article_number: str
    context_path: str
    image: dict[str, Any]

    @property
    def sample_id(self) -> str:
        return f"{self.article_slug}-{self.image['image_id']}"

    @property
    def planning_run_id(self) -> str:
        return f"{BATCH_ID}-{self.sample_id}"

    @property
    def sample(self) -> native.Sample:
        return native.Sample(
            sample_id=self.sample_id,
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
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PipelineError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PipelineError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in {path}: {exc}") from exc


def relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise PipelineError(f"Path escapes workspace: {path}") from exc


def _source_rows(root: Path) -> dict[str, dict[str, str]]:
    path = root / SOURCE_MANIFEST_REL
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise PipelineError(f"Cannot read {path}: {exc}") from exc
    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise PipelineError(
            f"Expected {EXPECTED_SOURCE_ROWS} source rows, found {len(rows)}"
        )
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        file_path = row.get("file_path", "")
        if not file_path or file_path in indexed:
            raise PipelineError(
                f"Invalid or duplicate source manifest file_path: {file_path!r}"
            )
        indexed[file_path] = row
    duplicate_count = sum(bool(row.get("duplicate_of")) for row in rows)
    if duplicate_count != EXPECTED_SOURCE_DUPLICATES:
        raise PipelineError(
            f"Expected {EXPECTED_SOURCE_DUPLICATES} duplicate_of rows, "
            f"found {duplicate_count}"
        )
    return indexed


def _image_record(
    *,
    root: Path,
    slug: str,
    order: int,
    block: dict[str, Any],
    row: dict[str, str],
) -> dict[str, Any]:
    image_id = block.get("image_id")
    filename = block.get("file")
    manifest_path = block.get("manifest_file_path")
    expected_manifest_path = f"articles/{slug}/{filename}"
    if (
        not isinstance(image_id, str)
        or not image_id
        or not isinstance(filename, str)
        or not filename
        or manifest_path != expected_manifest_path
    ):
        raise PipelineError(f"Invalid image binding for {slug}: {block}")
    if row.get("image_number") != image_id:
        raise PipelineError(
            f"Image number mismatch for {expected_manifest_path}: "
            f"{row.get('image_number')!r} != {image_id!r}"
        )
    duplicate_of = row.get("duplicate_of") or None
    if (block.get("duplicate_of") or None) != duplicate_of:
        raise PipelineError(f"duplicate_of mismatch for {expected_manifest_path}")
    source_path = root / "PROMOPAGES-9857" / expected_manifest_path
    digest = sha256_file(source_path)
    if digest != row.get("sha256"):
        raise PipelineError(f"Source digest mismatch: {source_path}")
    try:
        width = int(row["actual_width"])
        height = int(row["actual_height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"Invalid dimensions for {source_path}") from exc
    return {
        "order": order,
        "image_id": image_id,
        "file": filename,
        "role": block.get("role"),
        "caption": block.get("caption") or "",
        "source_path": f"PROMOPAGES-9857/{expected_manifest_path}",
        "copy_path": (
            Path("clipmaker-lite-test/PROMOPAGES-9857") / expected_manifest_path
        ).as_posix(),
        "manifest_file_path": expected_manifest_path,
        "sha256": digest,
        "width": width,
        "height": height,
        "duplicate_of": duplicate_of,
    }


def discover(root: Path = ROOT) -> tuple[tuple[Article, ...], tuple[Source, ...]]:
    """Select one deterministic post-cover image for each of 20 articles."""

    rows = _source_rows(root)
    cover_sha256s = {
        row["sha256"] for row in rows.values() if row.get("image_role") == "cover"
    }
    if len(cover_sha256s) != EXPECTED_SELECTED_IMAGES:
        raise PipelineError(
            f"Expected {EXPECTED_SELECTED_IMAGES} unique processed cover digests, "
            f"found {len(cover_sha256s)}"
        )
    context_files = sorted((root / SOURCE_CONTEXT_ROOT).glob("*/content.json"))
    if len(context_files) != EXPECTED_ARTICLES:
        raise PipelineError(
            f"Expected {EXPECTED_ARTICLES} article contexts, found {len(context_files)}"
        )

    articles: list[Article] = []
    sources: list[Source] = []
    seen_manifest_paths: set[str] = set()
    previously_selected_sha256s: set[str] = set()
    for article_index, context_path in enumerate(context_files, start=1):
        value = read_json(context_path)
        if not isinstance(value, dict) or not isinstance(value.get("blocks"), list):
            raise PipelineError(f"Article blocks are missing: {context_path}")
        slug = context_path.parent.name
        number = slug.split("-", 1)[0]
        if number != f"{article_index:02d}":
            raise PipelineError(f"Unexpected article order: {slug}")
        image_blocks = [
            block
            for block in value["blocks"]
            if isinstance(block, dict) and block.get("type") == "image"
        ]
        if not image_blocks:
            raise PipelineError(f"Article has no image blocks: {context_path}")

        source_dir = root / SOURCE_IMAGE_ROOT / slug
        disk_images = {
            path.name
            for path in source_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".jpeg", ".jpg", ".png", ".webp"}
        }
        block_files = {str(block.get("file", "")) for block in image_blocks}
        if disk_images != block_files:
            raise PipelineError(
                f"Image inventory mismatch for {slug}: "
                f"disk={sorted(disk_images)}, blocks={sorted(block_files)}"
            )

        records: list[dict[str, Any]] = []
        for order, block in enumerate(image_blocks, start=1):
            manifest_path = block.get("manifest_file_path")
            row = rows.get(manifest_path) if isinstance(manifest_path, str) else None
            if row is None:
                raise PipelineError(
                    f"Image is absent from {SOURCE_MANIFEST_REL}: {manifest_path!r}"
                )
            record = _image_record(
                root=root,
                slug=slug,
                order=order,
                block=block,
                row=row,
            )
            if record["manifest_file_path"] in seen_manifest_paths:
                raise PipelineError(
                    f"Image appears in multiple article contexts: "
                    f"{record['manifest_file_path']}"
                )
            seen_manifest_paths.add(record["manifest_file_path"])
            records.append(record)

        selected = records[0]
        if selected["duplicate_of"] is not None:
            raise PipelineError(f"First selected image is unexpectedly a duplicate: {slug}")
        if selected["sha256"] not in cover_sha256s:
            raise PipelineError(f"Article cover is absent from processed covers: {slug}")
        chosen = next(
            (
                record
                for record in records[1:]
                if record["sha256"] not in cover_sha256s
                and record["sha256"] not in previously_selected_sha256s
            ),
            None,
        )
        if chosen is None:
            raise PipelineError(
                f"Article has no fresh post-cover image after SHA filtering: {slug}"
            )
        previously_selected_sha256s.add(chosen["sha256"])
        sources.append(
            Source(
                article_slug=slug,
                article_number=number,
                context_path=relative(context_path, root),
                image=chosen,
            )
        )
        articles.append(
            Article(
                slug=slug,
                number=number,
                title=str(value.get("title") or ""),
                lead=str(value.get("lead") or ""),
                context_path=relative(context_path, root),
                context_sha256=sha256_file(context_path),
                selected_image=selected,
                images=(chosen,),
            )
        )

    if seen_manifest_paths != set(rows):
        missing = sorted(set(rows) - seen_manifest_paths)
        extra = sorted(seen_manifest_paths - set(rows))
        raise PipelineError(
            f"Article contexts do not cover the source manifest: "
            f"missing={missing}, extra={extra}"
        )
    if len(articles) != EXPECTED_ARTICLES:
        raise PipelineError(
            f"Expected {EXPECTED_ARTICLES} articles, found {len(articles)}"
        )
    if len(sources) != EXPECTED_IMAGES:
        raise PipelineError(
            f"Expected {EXPECTED_IMAGES} selected new images, found {len(sources)}"
        )
    if any(len(article.images) != 1 for article in articles):
        raise PipelineError("Every article must contain exactly one selected new image")
    if len({source.sample_id for source in sources}) != EXPECTED_IMAGES:
        raise PipelineError("Fresh image sample IDs are not unique")
    if len({source.image["source_path"] for source in sources}) != EXPECTED_IMAGES:
        raise PipelineError("Fresh source paths are not unique")
    if len({source.image["sha256"] for source in sources}) != EXPECTED_IMAGES:
        raise PipelineError("Fresh source image digests are not unique")
    return tuple(articles), tuple(sources)


def inventory_document(
    articles: Iterable[Article], sources: Iterable[Source]
) -> dict[str, Any]:
    articles = tuple(articles)
    sources = tuple(sources)
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "models": list(MODEL_IDS),
        "article_count": len(articles),
        "source_manifest_row_count": EXPECTED_SOURCE_ROWS,
        "processed_cover_count": EXPECTED_SELECTED_IMAGES,
        "source_duplicate_row_count": EXPECTED_SOURCE_DUPLICATES,
        "image_count": len(sources),
        "expected_outputs": len(sources) * len(MODEL_IDS),
        "selection_rule": (
            "for each article in numeric order, select the first image block "
            "after the cover whose SHA-256 matches neither any processed cover "
            "nor any image selected for an earlier article"
        ),
        "cost": cost_metadata(),
        "articles": [
            {
                "article_number": article.number,
                "article_slug": article.slug,
                "title": article.title,
                "lead": article.lead,
                "context": {
                    "path": article.context_path,
                    "copy_path": (
                        Path("clipmaker-lite-test") / article.context_path
                    ).as_posix(),
                    "sha256": article.context_sha256,
                },
                "selected_image": article.selected_image,
                "new_unique_image_count": len(article.images),
                "images": list(article.images),
            }
            for article in articles
        ],
    }


def cost_metadata() -> dict[str, Any]:
    maximum_estimated_cost = round(
        ESTIMATED_COST_PER_OUTPUT_USD * MAX_PAID_SUBMISSIONS, 2
    )
    if maximum_estimated_cost > HARD_BUDGET_CAP_USD:
        raise PipelineError(
            f"Estimated maximum cost ${maximum_estimated_cost:.2f} exceeds "
            f"the hard ${HARD_BUDGET_CAP_USD:.2f} cap"
        )
    return {
        "currency": "USD",
        "base_estimate_usd": BASE_ESTIMATED_COST_USD,
        "hard_budget_cap_usd": HARD_BUDGET_CAP_USD,
        "accounting_cost_per_output_usd": round(
            ESTIMATED_COST_PER_OUTPUT_USD, 4
        ),
        "planned_paid_submissions": EXPECTED_OUTPUTS,
        "maximum_paid_submissions": MAX_PAID_SUBMISSIONS,
        "maximum_estimated_cost_usd": maximum_estimated_cost,
        "cap_headroom_usd": round(HARD_BUDGET_CAP_USD - maximum_estimated_cost, 2),
        "automatic_paid_retries": False,
        "retry_policy": (
            "immutable entries may submit at most once; resume only polls an "
            "already submitted job, and any paid retry requires a separately "
            "budgeted namespace"
        ),
    }


def write_inventory(
    articles: Iterable[Article], sources: Iterable[Source], root: Path = ROOT
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
    """Bind the tested native bridge to this exact immutable 20x2 matrix."""

    sources = tuple(sources)
    if len(sources) != EXPECTED_IMAGES:
        raise PipelineError(
            f"Native bridge requires all {EXPECTED_IMAGES} frozen sources"
        )
    for model_id in MODEL_IDS:
        route = transport.route_for_model(model_id)
        if int(route.get("capacity", 0)) != 3:
            raise PipelineError(f"Expected route capacity 3 for {model_id}")
    native.BATCH_ID = BATCH_ID
    native.PLANNING_BATCH_ID = BATCH_ID
    native.MODEL_IDS = MODEL_IDS
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = GENERATION_MANIFEST_REL
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = None
    native.SAMPLES = tuple(source.sample for source in sources)
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


def runner_command(root: Path, *parts: str) -> list[str]:
    return [sys.executable, str(root / "scripts/clipmaker_lite_runner.py"), *parts]


def _planning_state(source: Source, root: Path) -> str | None:
    result_path = root / ARTIFACT_NAMESPACE / source.planning_run_id / "result.json"
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
            item.get("model_id") for item in selection.get("selected_models", [])
        ]
        if selected_ids != list(MODEL_IDS):
            raise PipelineError(
                f"Existing planning model set differs: {source.planning_run_id}"
            )
        return "prepared"
    return None


def select_sources(
    sources: Iterable[Source],
    *,
    sample_ids: Iterable[str] = (),
    article_slugs: Iterable[str] = (),
    planning_run_ids: Iterable[str] = (),
) -> tuple[Source, ...]:
    sources = tuple(sources)
    sample_ids = tuple(sample_ids)
    article_slugs = tuple(article_slugs)
    planning_run_ids = tuple(planning_run_ids)
    known_sample_ids = {source.sample_id for source in sources}
    known_articles = {source.article_slug for source in sources}
    known_runs = {source.planning_run_id for source in sources}
    unknown_samples = set(sample_ids) - known_sample_ids
    unknown_articles = set(article_slugs) - known_articles
    unknown_runs = set(planning_run_ids) - known_runs
    if unknown_samples:
        raise PipelineError(
            f"Unknown sample IDs: {', '.join(sorted(unknown_samples))}"
        )
    if unknown_articles:
        raise PipelineError(
            f"Unknown article slugs: {', '.join(sorted(unknown_articles))}"
        )
    if unknown_runs:
        raise PipelineError(
            f"Unknown planning run IDs: {', '.join(sorted(unknown_runs))}"
        )
    selected = tuple(
        source
        for source in sources
        if (not sample_ids or source.sample_id in sample_ids)
        and (not article_slugs or source.article_slug in article_slugs)
        and (not planning_run_ids or source.planning_run_id in planning_run_ids)
    )
    if not selected:
        raise PipelineError("Planning filters selected no fresh images")
    return selected


def prepare_planning_runs(
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> dict[str, int]:
    counts = {"verified": 0, "prepared": 0, "pending": 0}
    for source in sources:
        state = _planning_state(source, root)
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
        command = runner_command(
            root,
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
            MODEL_IDS[0],
            "--model",
            MODEL_IDS[1],
        )
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
        if _planning_state(source, root) != "prepared":
            raise PipelineError(
                f"Runner did not create a valid planning job: {source.planning_run_id}"
            )
        counts["prepared"] += 1
        print(f"planning prepare {source.planning_run_id} -> prepared", flush=True)
    return counts


def _run_one_planning(
    source: Source,
    *,
    root: Path,
    timeout: int,
    author_model: str | None,
) -> tuple[str, str, str | None]:
    run_id = source.planning_run_id
    try:
        if _planning_state(source, root) == "verified":
            return run_id, "existing", None
    except Exception as exc:
        return run_id, "failed", transport.safe_error(exc)
    command = runner_command(
        root,
        "run",
        "--run-id",
        run_id,
        "--timeout",
        str(timeout),
        "--allow-external-processing",
    )
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
        return run_id, "failed", f"planning subprocess timed out: {exc}"
    if completed.returncode:
        return (
            run_id,
            "failed",
            transport.safe_error(completed.stderr or completed.stdout),
        )
    try:
        state = _planning_state(source, root)
    except Exception as exc:
        return run_id, "failed", transport.safe_error(exc)
    if state != "verified":
        return run_id, "failed", "runner provenance is not verified"
    return run_id, "completed", None


def run_planning_runs(
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    concurrency: int,
    timeout: int,
    dry_run: bool,
    allow_external_processing: bool,
    author_model: str | None = None,
) -> int:
    sources = tuple(sources)
    if concurrency < 1:
        raise PipelineError("Planning concurrency must be at least 1")
    if dry_run:
        prepare_planning_runs(sources, root=root, dry_run=True)
        for source in sources:
            state = _planning_state(source, root)
            print(
                f"planning run {source.planning_run_id} -> "
                f"{'existing' if state == 'verified' else 'would-run'}",
                flush=True,
            )
        return 0
    if not allow_external_processing:
        raise PipelineError(
            "Real planning requires --allow-external-processing because images "
            "and article context are sent to Codex"
        )
    failures: list[str] = []
    completed_count = 0
    with manifest_run_lock(root / INVENTORY_MANIFEST_REL):
        # Keep preparation under the same cross-process coordinator lock as the
        # isolated executions; otherwise two run-plans processes could race to
        # create the same immutable job before either reached the run phase.
        prepare_planning_runs(sources, root=root, dry_run=False)
        with ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="lite20-new-image-plan"
        ) as executor:
            futures: dict[Future[tuple[str, str, str | None]], Source] = {
                executor.submit(
                    _run_one_planning,
                    source,
                    root=root,
                    timeout=timeout,
                    author_model=author_model,
                ): source
                for source in sources
            }
            for future in as_completed(futures):
                run_id, status, error = future.result()
                completed_count += 1
                suffix = f": {error}" if error else ""
                print(
                    f"planning [{completed_count}/{len(sources)}] "
                    f"{run_id} -> {status}{suffix}",
                    flush=True,
                )
                if error:
                    failures.append(f"{run_id}: {error}")
    if failures:
        detail = "; ".join(failures[:5])
        if len(failures) > 5:
            detail += f"; and {len(failures) - 5} more"
        raise PipelineError(
            f"{len(failures)} planning run(s) failed: {detail}"
        )
    return 0


def materialize_generation(
    sources: Iterable[Source], *, root: Path = ROOT, dry_run: bool = False
) -> int:
    sources = tuple(sources)
    configure_native(sources, root)
    if dry_run:
        for entry in native.matrix():
            native.load_lite_job(entry, root)
        print(
            f"PASS: validated {EXPECTED_OUTPUTS} provider jobs; no files written"
        )
        return 0
    rows = native.materialize(root)
    if len(rows) != EXPECTED_OUTPUTS:
        raise PipelineError(
            f"Expected {EXPECTED_OUTPUTS} provider jobs, materialized {len(rows)}"
        )
    print(
        f"PASS: materialized {len(rows)} provider jobs from "
        f"{len(sources)} verified Lite planning runs"
    )
    return 0


def run_generation(
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    wan27_concurrency: int,
    veo31_concurrency: int,
    timeout: int,
    poll_interval: float,
    dry_run: bool,
    allow_external_processing: bool,
    fail_fast: bool,
    run_ids: Iterable[str] = (),
    models: Iterable[str] = (),
) -> int:
    sources = tuple(sources)
    # Fail before materialization or provider work if the immutable one-submit
    # matrix can no longer be proven to stay below the operator budget cap.
    cost_metadata()
    models = tuple(models) or MODEL_IDS
    unknown_models = set(models) - set(MODEL_IDS)
    if unknown_models:
        raise PipelineError(
            "Unsupported models (Wan 2.2 is intentionally excluded): "
            + ", ".join(sorted(unknown_models))
        )
    if wan27_concurrency < 1 or wan27_concurrency > 3:
        raise PipelineError("Wan 2.7 concurrency must be between 1 and 3")
    if veo31_concurrency < 1 or veo31_concurrency > 3:
        raise PipelineError("Veo 3.1 Lite concurrency must be between 1 and 3")
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real generation requires --allow-external-processing because images "
            "and Lite prompts are sent to providers"
        )
    configure_native(sources, root)
    argv = [
        "run",
        "--wan27-concurrency",
        str(wan27_concurrency),
        "--veo31-concurrency",
        str(veo31_concurrency),
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
    ]
    argv.append("--dry-run" if dry_run else "--allow-external-processing")
    if fail_fast:
        argv.append("--fail-fast")
    for run_id in run_ids:
        argv.extend(("--run-id", run_id))
    for model_id in models:
        argv.extend(("--model", model_id))
    # native.main owns materialization and every aggregate-manifest write. Its
    # provider workers only return row outcomes to the coordinator thread.
    if dry_run:
        return native.main(argv, root)
    with manifest_run_lock(root / INVENTORY_MANIFEST_REL):
        return native.main(argv, root)


def _planning_record(source: Source, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = runner.provenance_summary(root, source.planning_run_id)
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("models") != list(MODEL_IDS)
        or summary.get("source_image_sha256") != source.image["sha256"]
    ):
        raise PipelineError(f"Planning provenance failed: {source.planning_run_id}")
    expected_result_path = (
        ARTIFACT_NAMESPACE / source.planning_run_id / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result_path:
        raise PipelineError(
            f"Unexpected planning result path: {source.planning_run_id}"
        )
    result = read_json(root / expected_result_path)
    if result.get("job_id") != source.planning_run_id:
        raise PipelineError(f"Planning result identity mismatch: {source.planning_run_id}")
    models = result.get("models")
    if (
        not isinstance(models, list)
        or [model.get("model_id") for model in models if isinstance(model, dict)]
        != list(MODEL_IDS)
    ):
        raise PipelineError(f"Planning result model set differs: {source.planning_run_id}")
    return summary, result


def build_final_manifest(
    articles: Iterable[Article],
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    updated_at: str | None = None,
    allow_contract_warnings: bool = False,
) -> dict[str, Any]:
    articles = tuple(articles)
    sources = tuple(sources)
    configure_native(sources, root)
    native.materialize(root)
    generation = read_json(root / GENERATION_MANIFEST_REL)
    generation_outputs = generation.get("outputs")
    if not isinstance(generation_outputs, list) or len(generation_outputs) != EXPECTED_OUTPUTS:
        raise PipelineError(
            f"Generation manifest must contain {EXPECTED_OUTPUTS} outputs"
        )
    provider_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for output in generation_outputs:
        if not isinstance(output, dict):
            raise PipelineError("Generation manifest output is not an object")
        key = (str(output.get("source_path")), str(output.get("model_id")))
        if key in provider_by_key:
            raise PipelineError(f"Duplicate generation output key: {key}")
        provider_by_key[key] = output

    source_by_article: dict[str, list[Source]] = {
        article.slug: [] for article in articles
    }
    for source in sources:
        source_by_article[source.article_slug].append(source)

    article_records: list[dict[str, Any]] = []
    all_outputs: list[dict[str, Any]] = []
    for article in articles:
        image_records: list[dict[str, Any]] = []
        for source in source_by_article[article.slug]:
            summary, result = _planning_record(source, root)
            model_map = {
                model.get("model_id"): model
                for model in result["models"]
                if isinstance(model, dict)
            }
            outputs: list[dict[str, Any]] = []
            for model_id in MODEL_IDS:
                key = (source.image["source_path"], model_id)
                provider = provider_by_key.get(key)
                model = model_map.get(model_id)
                if provider is None or model is None:
                    raise PipelineError(
                        f"Missing output binding: {source.sample_id}/{model_id}"
                    )
                entry = native.Entry(source.sample, model_id)
                if provider.get("provider_run_id") != entry.provider_run_id:
                    raise PipelineError(
                        f"Provider run identity mismatch: {source.sample_id}/{model_id}"
                    )
                record = {
                    "article_slug": article.slug,
                    "image_id": source.image["image_id"],
                    "source_path": source.image["source_path"],
                    "sample_id": source.sample_id,
                    "lite_run_id": source.planning_run_id,
                    "provider_run_id": provider.get("provider_run_id"),
                    "model_id": model_id,
                    "scene_plan": model.get("scene_plan"),
                    "positive_prompt": model.get("positive_prompt"),
                    "negative_prompt": model.get("negative_prompt"),
                    "status": provider.get("status"),
                    "recorded_status": provider.get("recorded_status"),
                    "prompt_path": provider.get("prompt_path"),
                    "run_path": provider.get("run_path"),
                    "video_path": provider.get("video_path"),
                    "media": provider.get("media"),
                    "contract_check": provider.get("contract_check"),
                    "error": provider.get("error"),
                }
                outputs.append(record)
                all_outputs.append(record)
            image_records.append(
                {
                    "image": source.image,
                    "lite_planning": {
                        "run_id": source.planning_run_id,
                        "result_path": summary.get("result_path"),
                        "structured_intent": result.get("analysis", {}).get(
                            "structured_intent"
                        ),
                        "provenance": summary,
                    },
                    "outputs": outputs,
                }
            )
        article_records.append(
            {
                "article_number": article.number,
                "article_slug": article.slug,
                "title": article.title,
                "context_path": article.context_path,
                "selected_image": article.selected_image,
                "new_unique_image_count": len(image_records),
                "images": image_records,
            }
        )

    if len(article_records) != EXPECTED_ARTICLES:
        raise PipelineError(
            f"Expected {EXPECTED_ARTICLES} final articles, got {len(article_records)}"
        )
    if sum(len(article["images"]) for article in article_records) != EXPECTED_IMAGES:
        raise PipelineError(f"Final manifest must contain {EXPECTED_IMAGES} images")
    if len(all_outputs) != EXPECTED_OUTPUTS:
        raise PipelineError(f"Final manifest must contain {EXPECTED_OUTPUTS} outputs")
    keys = {
        (output["article_slug"], output["image_id"], output["model_id"])
        for output in all_outputs
    }
    if len(keys) != EXPECTED_OUTPUTS:
        raise PipelineError("Final output merge keys are not unique")
    status_summary: dict[str, int] = {}
    for output in all_outputs:
        status = str(output.get("status") or "missing")
        status_summary[status] = status_summary.get(status, 0) + 1
    acceptance_audit = output_acceptance_audit(
        all_outputs,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    return {
        "schema_version": 1,
        "manifest_role": "one-new-image-per-article-extension",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "extends_manifest": BASE_MANIFEST_REL.as_posix(),
        "merge_contract": {
            "article_key": ["article_slug"],
            "image_key": ["article_slug", "image_id"],
            "output_key": ["article_slug", "image_id", "model_id"],
            "target_field": "articles[].images[]",
            "preserve_base_selected_image": True,
            "preserve_base_outputs": True,
        },
        "models": list(MODEL_IDS),
        "article_count": len(article_records),
        "image_count": EXPECTED_IMAGES,
        "new_unique_image_count": EXPECTED_IMAGES,
        "expected_outputs": EXPECTED_OUTPUTS,
        "cost": cost_metadata(),
        "status_summary": status_summary,
        "acceptance_policy": {
            "allow_contract_warnings": allow_contract_warnings,
            "accepted_complete_statuses": (
                ["succeeded", "verification-failed"]
                if allow_contract_warnings
                else ["succeeded"]
            ),
            "preserve_recorded_status": True,
            "requires_mp4_and_media": True,
        },
        **acceptance_audit,
        "inventory_manifest": INVENTORY_MANIFEST_REL.as_posix(),
        "generation_manifest": GENERATION_MANIFEST_REL.as_posix(),
        "articles": article_records,
        "outputs": all_outputs,
    }


def final_output_acceptance_error(
    output: Any,
    *,
    root: Path = ROOT,
    allow_contract_warnings: bool,
) -> str | None:
    """Validate a complete output without rewriting warning statuses."""

    if not isinstance(output, dict):
        return "final output is not an object"
    label = output.get("provider_run_id") or "unknown output"
    status = output.get("status")
    if status not in {"succeeded", "verification-failed"}:
        return f"{label}: status {status!r} is not a generated final output"
    video_path = output.get("video_path")
    if not isinstance(video_path, str) or not video_path:
        return f"{label}: video_path is missing"
    relative_video = Path(video_path)
    if relative_video.is_absolute() or ".." in relative_video.parts:
        return f"{label}: video_path is not workspace-relative"
    if not (root / relative_video).is_file():
        return f"{label}: MP4 is missing"
    if not isinstance(output.get("media"), dict):
        return f"{label}: measured media metadata is missing"
    check = output.get("contract_check")
    if not isinstance(check, dict):
        return f"{label}: media contract check is missing"
    if status == "succeeded":
        if check.get("conforms") is not True:
            return f"{label}: succeeded output does not conform"
        return None
    if not allow_contract_warnings:
        return f"{label}: media contract failed and warnings were not allowed"
    warnings = check.get("warnings")
    if (
        check.get("conforms") is not False
        or not isinstance(warnings, list)
        or not warnings
        or any(not isinstance(warning, str) or not warning for warning in warnings)
    ):
        return f"{label}: verification failure has no explicit contract violations"
    return None


def output_acceptance_audit(
    outputs: Iterable[dict[str, Any]],
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> dict[str, Any]:
    """Summarize conformance separately from explicitly accepted raw files."""

    outputs = tuple(outputs)
    conforming = 0
    accepted = 0
    warning_outputs = 0
    warnings_by_name: dict[str, int] = {}
    warnings_by_model: dict[str, int] = {}
    for output in outputs:
        check = output.get("contract_check")
        if (
            output.get("status") == "succeeded"
            and isinstance(check, dict)
            and check.get("conforms") is True
        ):
            conforming += 1
        if (
            final_output_acceptance_error(
                output,
                root=root,
                allow_contract_warnings=allow_contract_warnings,
            )
            is None
        ):
            accepted += 1
        if isinstance(check, dict) and check.get("conforms") is False:
            warning_outputs += 1
            model_id = str(output.get("model_id") or "unknown")
            warnings_by_model[model_id] = warnings_by_model.get(model_id, 0) + 1
            warnings = check.get("warnings")
            if isinstance(warnings, list):
                for warning in warnings:
                    if isinstance(warning, str) and warning:
                        warnings_by_name[warning] = warnings_by_name.get(warning, 0) + 1
    return {
        "accepted_output_count": accepted,
        "conforming_output_count": conforming,
        "contract_warning_summary": {
            "output_count": warning_outputs,
            "by_model": warnings_by_model,
            "by_warning": warnings_by_name,
        },
    }


def final_output_acceptance_errors(
    document: Any,
    *,
    root: Path = ROOT,
    allow_contract_warnings: bool,
) -> list[str]:
    if not isinstance(document, dict):
        return ["Final manifest is not an object"]
    outputs = document.get("outputs")
    if not isinstance(outputs, list):
        return ["Final manifest outputs are missing"]
    errors: list[str] = []
    if document.get("article_count") != EXPECTED_ARTICLES:
        errors.append("Final manifest article_count is not 20")
    if document.get("image_count") != EXPECTED_IMAGES:
        errors.append("Final manifest image_count is not 20")
    if document.get("expected_outputs") != EXPECTED_OUTPUTS:
        errors.append("Final manifest expected_outputs is not 40")
    if len(outputs) != EXPECTED_OUTPUTS:
        errors.append(
            f"Final manifest output count mismatch: expected {EXPECTED_OUTPUTS}, "
            f"got {len(outputs)}"
        )
    keys: set[tuple[Any, Any, Any]] = set()
    for output in outputs:
        if isinstance(output, dict):
            key = (
                output.get("article_slug"),
                output.get("image_id"),
                output.get("model_id"),
            )
            if key in keys:
                errors.append(f"Duplicate final output key: {key}")
            keys.add(key)
        error = final_output_acceptance_error(
            output,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        if error:
            errors.append(error)
    policy = document.get("acceptance_policy")
    if not isinstance(policy, dict) or policy.get(
        "allow_contract_warnings"
    ) is not allow_contract_warnings:
        errors.append("Final manifest acceptance policy does not match verification")
    if all(isinstance(output, dict) for output in outputs):
        expected_audit = output_acceptance_audit(
            outputs,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        for key, expected in expected_audit.items():
            if document.get(key) != expected:
                errors.append(f"Final manifest {key} does not match output artifacts")
    return errors


def finalize(
    articles: Iterable[Article],
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    allow_contract_warnings: bool = False,
) -> dict[str, Any]:
    document = build_final_manifest(
        articles,
        sources,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    errors = final_output_acceptance_errors(
        document,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    if errors:
        detail = "; ".join(errors[:5])
        if len(errors) > 5:
            detail += f"; and {len(errors) - 5} more"
        raise PipelineError(
            f"Cannot finalize: {len(errors)} output acceptance error(s): {detail}"
        )
    transport.atomic_write_json(root / FINAL_MANIFEST_REL, document)
    return document


def verify_all(
    articles: Iterable[Article],
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    allow_incomplete: bool,
    allow_contract_warnings: bool,
) -> tuple[bool, list[str]]:
    articles = tuple(articles)
    sources = tuple(sources)
    errors: list[str] = []
    expected_inventory = inventory_document(articles, sources)
    inventory_path = root / INVENTORY_MANIFEST_REL
    if not inventory_path.is_file() or read_json(inventory_path) != expected_inventory:
        errors.append("Inventory manifest does not match the frozen 20x1 selection")

    configure_native(sources, root)
    native_ok, native_errors = native.verify(
        root,
        allow_incomplete=allow_incomplete,
        allow_contract_warnings=allow_contract_warnings,
    )
    if not native_ok:
        errors.extend(native_errors)

    final_path = root / FINAL_MANIFEST_REL
    if not final_path.is_file():
        if not allow_incomplete:
            errors.append(f"Missing final manifest: {FINAL_MANIFEST_REL}")
    else:
        actual = read_json(final_path)
        updated_at = actual.get("updated_at") if isinstance(actual, dict) else None
        rebuilt = (
            build_final_manifest(
                articles,
                sources,
                root=root,
                updated_at=updated_at,
                allow_contract_warnings=allow_contract_warnings,
            )
            if isinstance(updated_at, str)
            else None
        )
        if rebuilt is None or actual != rebuilt:
            errors.append("Final manifest does not match current Lite/provider artifacts")
        if not allow_incomplete and rebuilt is not None:
            errors.extend(
                final_output_acceptance_errors(
                    rebuilt,
                    root=root,
                    allow_contract_warnings=allow_contract_warnings,
                )
            )

    report = {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "passed": not errors,
        "allow_incomplete": allow_incomplete,
        "allow_contract_warnings": allow_contract_warnings,
        "article_count": len(articles),
        "image_count": len(sources),
        "expected_outputs": len(sources) * len(MODEL_IDS),
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


def route_concurrency(value: str) -> int:
    parsed = positive_int(value)
    if parsed > 3:
        raise argparse.ArgumentTypeError("route concurrency must not exceed 3")
    return parsed


def _add_planning_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sample-id", action="append", default=[])
    parser.add_argument("--article", action="append", default=[])
    parser.add_argument("--planning-run-id", action="append", default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser(
        "inventory", help="validate and freeze one new image for each of 20 articles"
    )
    inventory.add_argument("--dry-run", action="store_true")

    prepare = subparsers.add_parser(
        "prepare-plans", help="prepare or resume the 20 immutable Lite jobs"
    )
    prepare.add_argument("--dry-run", action="store_true")
    _add_planning_selection(prepare)

    run_plans = subparsers.add_parser(
        "run-plans", help="run or resume isolated Lite planning jobs"
    )
    run_plans.add_argument("--concurrency", type=positive_int, default=3)
    run_plans.add_argument("--timeout", type=positive_int, default=1800)
    run_plans.add_argument("--author-model")
    run_plans.add_argument("--dry-run", action="store_true")
    run_plans.add_argument("--allow-external-processing", action="store_true")
    _add_planning_selection(run_plans)

    plan_generation = subparsers.add_parser(
        "plan-generation", help="materialize the 40 native provider jobs"
    )
    plan_generation.add_argument("--dry-run", action="store_true")

    generate = subparsers.add_parser(
        "generate", help="generate or resume the independent 3+3 route pools"
    )
    generate.add_argument("--run-id", action="append", default=[])
    generate.add_argument(
        "--model", action="append", choices=MODEL_IDS, default=[]
    )
    generate.add_argument(
        "--wan27-concurrency", type=route_concurrency, default=3
    )
    generate.add_argument(
        "--veo31-concurrency", type=route_concurrency, default=3
    )
    generate.add_argument("--timeout", type=positive_int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--fail-fast", action="store_true")

    finalize_parser = subparsers.add_parser(
        "finalize", help="build the separate 20-image manifest extension"
    )
    finalize_parser.add_argument(
        "--allow-contract-warnings",
        action="store_true",
        help=(
            "accept complete raw MP4s while preserving verification-failed "
            "status and explicit media-contract violations"
        ),
    )

    verify = subparsers.add_parser(
        "verify", help="verify inventory, provenance, requests, MP4s, and extension"
    )
    verify.add_argument("--allow-incomplete", action="store_true")
    verify.add_argument(
        "--allow-contract-warnings",
        action="store_true",
        help=(
            "accept complete raw MP4s while preserving verification-failed "
            "status and explicit media-contract violations"
        ),
    )
    return parser


def _selected_from_args(
    sources: Sequence[Source], args: argparse.Namespace
) -> tuple[Source, ...]:
    return select_sources(
        sources,
        sample_ids=getattr(args, "sample_id", ()),
        article_slugs=getattr(args, "article", ()),
        planning_run_ids=getattr(args, "planning_run_id", ()),
    )


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        articles, sources = discover(root)
        if args.command == "inventory":
            document = inventory_document(articles, sources)
            if not args.dry_run:
                write_inventory(articles, sources, root)
            print(
                f"PASS: {document['article_count']} articles, "
                f"{document['image_count']} selected new unique images, "
                f"{document['expected_outputs']} planned outputs"
            )
            return 0

        # Every stateful command is anchored to one immutable inventory. Dry
        # planning previews remain write-free.
        if not getattr(args, "dry_run", False):
            write_inventory(articles, sources, root)

        if args.command == "prepare-plans":
            selected = _selected_from_args(sources, args)
            counts = prepare_planning_runs(
                selected, root=root, dry_run=args.dry_run
            )
            print(
                f"PASS: planning prepare selection={len(selected)} "
                f"verified={counts['verified']} prepared={counts['prepared']} "
                f"pending={counts['pending']}"
            )
            return 0
        if args.command == "run-plans":
            selected = _selected_from_args(sources, args)
            return run_planning_runs(
                selected,
                root=root,
                concurrency=args.concurrency,
                timeout=args.timeout,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                author_model=args.author_model,
            )
        if args.command == "plan-generation":
            return materialize_generation(
                sources, root=root, dry_run=args.dry_run
            )
        if args.command == "generate":
            return run_generation(
                sources,
                root=root,
                wan27_concurrency=args.wan27_concurrency,
                veo31_concurrency=args.veo31_concurrency,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                fail_fast=args.fail_fast,
                run_ids=args.run_id,
                models=args.model,
            )
        if args.command == "finalize":
            document = finalize(
                articles,
                sources,
                root=root,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            print(
                f"PASS: extension contains {document['article_count']} articles, "
                f"{document['image_count']} images, and "
                f"{document['expected_outputs']} outputs"
            )
            return 0
        if args.command == "verify":
            passed, errors = verify_all(
                articles,
                sources,
                root=root,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: PROMOPAGES-9930 Clipmaker Lite 20x2 extension is valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except (
        PipelineError,
        native.BatchPipelineError,
        runner.LiteRunnerError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
