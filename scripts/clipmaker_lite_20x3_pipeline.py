#!/usr/bin/env python3
"""Build, run, and verify the PROMOPAGES-9910 Clipmaker Lite 20x3 batch.

The planning route remains the locked ``clipmaker_lite_runner.py`` execution.
This module only discovers the first image in each article, mirrors all article
materials into ``clipmaker-lite-test/``, delegates provider work to the tested
native batch bridge, and builds the review manifest required by the ticket.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9910"
BATCH_ID = "promopages-9910-lite20-20260724-r2"
PLANNING_BATCH_ID = BATCH_ID
WAN_RETRY1_BATCH_ID = f"{BATCH_ID}-wan-named-retry1"
WAN_RETRY2_BATCH_ID = f"{BATCH_ID}-wan-named-retry2"
WAN_RETRY3_BATCH_ID = f"{BATCH_ID}-wan-named-retry3"
WAN_LEGACY_RETRY5_BATCH_ID = f"{BATCH_ID}-wan-legacy-retry5"
TEST_ROOT_REL = Path("clipmaker-lite-test")
TEST_ROOT = ROOT / TEST_ROOT_REL
GENERATION_MANIFEST_REL = TEST_ROOT_REL / "generation-manifest.json"
WAN_RETRY1_MANIFEST_REL = TEST_ROOT_REL / "wan-named-retry-manifest.json"
WAN_RETRY2_MANIFEST_REL = TEST_ROOT_REL / "wan-named-retry2-manifest.json"
WAN_RETRY3_MANIFEST_REL = TEST_ROOT_REL / "wan-named-retry3-manifest.json"
WAN_LEGACY_RETRY5_MANIFEST_REL = TEST_ROOT_REL / "wan-legacy-retry5-manifest.json"
FINAL_MANIFEST_REL = TEST_ROOT_REL / "manifest.json"
DATASET_MANIFEST_REL = TEST_ROOT_REL / "dataset-manifest.json"
VERIFICATION_REPORT_REL = TEST_ROOT_REL / "verification-report.json"
SOURCE_IMAGE_ROOT = Path("PROMOPAGES-9857/articles")
SOURCE_CONTEXT_ROOT = Path("PROMOPAGES-9884/articles")
SOURCE_MANIFEST = SOURCE_IMAGE_ROOT / "manifest.csv"
EXPECTED_ARTICLES = 20
MODEL_IDS = native.MODEL_IDS
WAN_RETRY_SAMPLE_IDS = (
    "01-pharmocean-magiia-magniia",
    "04-graceface-antivozrastnaia-syvorotka",
    "05-5ka-zhaloba-na-magazin",
    "06-4lapy-koshachii-napolnitel",
    "07-aquadetrim-deficit-vitamina-d",
    "08-tochka-ooo-ili-ip",
    "09-dream-island-semeinye-vyhodnye",
    "10-exeed-rx",
    "11-ostin-vesenniaia-kapsula",
    "12-mars-podarki-na-8-marta",
    "13-ilinka-elitnyi-zhk",
    "14-miuz-modnye-sergi",
    "15-ozon-gruzoperevozki",
    "16-ekonika-letnie-trendy",
    "17-level-michurinskiy-kvartira",
    "18-dalan-sredstva-dlia-volos",
    "19-level-travel-otpusk-v-turcii",
    "20-sravni-kreditnyi-reiting",
)
WAN_RETRY3_CANARY_SAMPLE_ID = WAN_RETRY_SAMPLE_IDS[0]


class PipelineError(RuntimeError):
    """A fail-closed error in the PROMOPAGES-9910 orchestration layer."""


@dataclass(frozen=True)
class Article:
    slug: str
    number: str
    title: str
    lead: str
    context_path: str
    context_sha256: str
    images: tuple[dict[str, Any], ...]

    @property
    def selected(self) -> dict[str, Any]:
        return self.images[0]

    @property
    def sample(self) -> native.Sample:
        image = self.selected
        return native.Sample(
            sample_id=self.slug,
            article_slug=self.slug,
            image_id=image["image_id"],
            filename=image["file"],
            source_sha256=image["sha256"],
            width=image["width"],
            height=image["height"],
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


def source_rows(root: Path = ROOT) -> dict[str, dict[str, str]]:
    path = root / SOURCE_MANIFEST
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise PipelineError(f"Cannot read {path}: {exc}") from exc
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        file_path = row.get("file_path", "")
        if not file_path or file_path in indexed:
            raise PipelineError(f"Invalid or duplicate manifest file_path: {file_path!r}")
        indexed[file_path] = row
    return indexed


def discover_articles(root: Path = ROOT) -> tuple[Article, ...]:
    rows = source_rows(root)
    context_files = sorted((root / SOURCE_CONTEXT_ROOT).glob("*/content.json"))
    if len(context_files) != EXPECTED_ARTICLES:
        raise PipelineError(
            f"Expected {EXPECTED_ARTICLES} article contexts, found {len(context_files)}"
        )
    articles: list[Article] = []
    for context_path in context_files:
        slug = context_path.parent.name
        value = read_json(context_path)
        blocks = value.get("blocks") if isinstance(value, dict) else None
        if not isinstance(blocks, list):
            raise PipelineError(f"Article blocks are missing: {context_path}")
        image_blocks = [block for block in blocks if isinstance(block, dict) and block.get("type") == "image"]
        if not image_blocks:
            raise PipelineError(f"Article has no image blocks: {context_path}")
        source_dir = root / SOURCE_IMAGE_ROOT / slug
        disk_images = {
            path.name
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpeg", ".jpg", ".png", ".webp"}
        }
        block_files = {str(block.get("file", "")) for block in image_blocks}
        if disk_images != block_files:
            raise PipelineError(
                f"Image inventory mismatch for {slug}: disk={sorted(disk_images)}, blocks={sorted(block_files)}"
            )
        images: list[dict[str, Any]] = []
        for order, block in enumerate(image_blocks, start=1):
            image_id = block.get("image_id")
            filename = block.get("file")
            manifest_path = block.get("manifest_file_path")
            expected_manifest_path = f"articles/{slug}/{filename}"
            if (
                not isinstance(image_id, str)
                or not isinstance(filename, str)
                or manifest_path != expected_manifest_path
            ):
                raise PipelineError(f"Invalid image binding in {context_path}: {block}")
            row = rows.get(expected_manifest_path)
            if row is None:
                raise PipelineError(f"Image is absent from {SOURCE_MANIFEST}: {expected_manifest_path}")
            source_path = root / "PROMOPAGES-9857" / expected_manifest_path
            digest = sha256_file(source_path)
            if digest != row.get("sha256"):
                raise PipelineError(f"Source digest mismatch: {source_path}")
            try:
                width = int(row["actual_width"])
                height = int(row["actual_height"])
            except (KeyError, TypeError, ValueError) as exc:
                raise PipelineError(f"Invalid dimensions for {source_path}") from exc
            images.append(
                {
                    "order": order,
                    "image_id": image_id,
                    "file": filename,
                    "role": block.get("role"),
                    "caption": block.get("caption") or "",
                    "source_path": f"PROMOPAGES-9857/{expected_manifest_path}",
                    "copy_path": (
                        TEST_ROOT_REL / "PROMOPAGES-9857" / expected_manifest_path
                    ).as_posix(),
                    "sha256": digest,
                    "width": width,
                    "height": height,
                }
            )
        number = slug.split("-", 1)[0]
        if number != f"{len(articles) + 1:02d}":
            raise PipelineError(f"Unexpected article order: {slug}")
        articles.append(
            Article(
                slug=slug,
                number=number,
                title=str(value.get("title") or ""),
                lead=str(value.get("lead") or ""),
                context_path=relative(context_path, root),
                context_sha256=sha256_file(context_path),
                images=tuple(images),
            )
        )
    return tuple(articles)


def copy_exact(source: Path, destination: Path) -> None:
    if destination.is_file():
        if sha256_file(destination) != sha256_file(source):
            raise PipelineError(f"Immutable copy differs: {destination}")
        return
    if destination.exists():
        raise PipelineError(f"Copy target is not a regular file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def dataset_document(articles: Iterable[Article]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    total_images = 0
    for article in articles:
        total_images += len(article.images)
        selected = article.selected
        records.append(
            {
                "article_number": article.number,
                "article_slug": article.slug,
                "title": article.title,
                "lead": article.lead,
                "context": {
                    "source_path": article.context_path,
                    "copy_path": (
                        TEST_ROOT_REL / article.context_path
                    ).as_posix(),
                    "sha256": article.context_sha256,
                },
                "selected_image": {
                    "selection_rule": "first image block in content.json",
                    **selected,
                },
                "images": list(article.images),
            }
        )
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "dataset_root": TEST_ROOT_REL.as_posix(),
        "article_count": len(records),
        "image_count": total_images,
        "selection_rule": "first image block in each article content.json",
        "articles": records,
    }


def write_readme() -> None:
    value = """# Clipmaker Lite test — PROMOPAGES-9910

Self-contained test set for 20 PromoPages articles. Each article is mirrored
under the original contract paths in `PROMOPAGES-9857/` (all source images) and
`PROMOPAGES-9884/` (`content.json`). Only the first image block from each article
is generated in this run.

The 20 planning artifacts live under `artifacts/clipmaker-lite/v1/`; each one
contains one shared structured intent and independent plans for all three exact
model IDs. Provider prompts, run receipts, and MP4s live under `videos/`.

Use `manifest.json` as the review entry point. `dataset-manifest.json` records
the complete article/image inventory, and `generation-manifest.json` is the
resumable provider state. `visual-qa.md` records the frame-level visual review
separately from the machine media contract. `sandbox-resource.json` records the
published 60-file review bundle. The copied locked runner can re-check a
planning run:

```bash
python3 scripts/clipmaker_lite_runner.py provenance --run-id <run-id>
```
"""
    path = TEST_ROOT / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") != value:
        raise PipelineError(f"Immutable README differs: {path}")
    if not path.is_file():
        path.write_text(value, encoding="utf-8")


def prepare_dataset(root: Path = ROOT) -> tuple[Article, ...]:
    articles = discover_articles(root)
    for article in articles:
        source_context = root / article.context_path
        copy_exact(source_context, TEST_ROOT / article.context_path)
        for image in article.images:
            copy_exact(root / image["source_path"], root / image["copy_path"])
    supporting_files = (
        SOURCE_MANIFEST,
        Path("PROMOPAGES-9857/README.md"),
        Path("PROMOPAGES-9884/README.md"),
        Path("scripts/clipmaker_lite_runner.py"),
        Path("docs/agents/clipmaker-lite/README.md"),
        Path("docs/agents/clipmaker-lite/contract.json"),
        Path("docs/agents/clipmaker-lite/generation-routes.json"),
        Path("docs/agents/clipmaker-lite/models/alibaba-wan-2.2.md"),
        Path("docs/agents/clipmaker-lite/models/alibaba-wan-2.7.md"),
        Path("docs/agents/clipmaker-lite/models/google-veo-3.1-lite.md"),
    )
    for source_rel in supporting_files:
        copy_exact(root / source_rel, TEST_ROOT / source_rel)
    write_readme()
    transport.atomic_write_json(root / DATASET_MANIFEST_REL, dataset_document(articles))
    return articles


def configure_native(
    articles: Iterable[Article],
    root: Path = ROOT,
    *,
    provider_batch_id: str = BATCH_ID,
    provider_model_ids: Iterable[str] = MODEL_IDS,
    manifest_path: Path = GENERATION_MANIFEST_REL,
    wan_submit_mode: str = "legacy",
) -> None:
    provider_model_ids = tuple(provider_model_ids)
    if not provider_model_ids or not set(provider_model_ids).issubset(MODEL_IDS):
        raise PipelineError(f"Invalid provider model set: {provider_model_ids}")
    if wan_submit_mode not in {"legacy", "named"}:
        raise PipelineError(f"Invalid Wan submit mode: {wan_submit_mode}")
    native.BATCH_ID = provider_batch_id
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = provider_model_ids
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = manifest_path
    native.CONTRACT_PATH = root / "docs/agents/clipmaker-lite/contract.json"
    native.SAMPLES = tuple(article.sample for article in articles)
    # Route overrides are isolated to this historical batch bridge.  The
    # shared transport remains immutable and normal runs use registry routes.
    native.WAN_SUBMIT_MODE = wan_submit_mode

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        base = (
            workspace
            / TEST_ROOT_REL
            / "videos"
            / provider_batch_id
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


def runner_command(*parts: str) -> list[str]:
    return [sys.executable, str(ROOT / "scripts/clipmaker_lite_runner.py"), *parts]


def prepare_planning_runs(articles: Iterable[Article]) -> None:
    for article in articles:
        sample = article.sample
        run_id = sample.planning_run_id
        job_path = ROOT / native.ARTIFACT_NAMESPACE / run_id / "job.json"
        if job_path.is_file():
            print(f"planning prepare {run_id} -> existing", flush=True)
            continue
        command = runner_command(
            "prepare",
            "--run-id",
            run_id,
            "--image",
            sample.source_path,
            "--context",
            sample.context_path,
            "--image-id",
            sample.image_id,
        )
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            detail = transport.safe_error(completed.stderr or completed.stdout)
            raise PipelineError(f"Planning prepare failed for {run_id}: {detail}")
        print(f"planning prepare {run_id} -> prepared", flush=True)


def run_one_planning(article: Article, timeout: int) -> tuple[str, str, str | None]:
    run_id = article.sample.planning_run_id
    try:
        summary = runner.provenance_summary(ROOT, run_id)
        if summary.get("verified") is True:
            return run_id, "existing", None
    except Exception:
        pass
    try:
        completed = subprocess.run(
            runner_command(
                "run",
                "--run-id",
                run_id,
                "--timeout",
                str(timeout),
                "--allow-external-processing",
            ),
            cwd=ROOT,
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
        summary = runner.provenance_summary(ROOT, run_id)
    except Exception as exc:
        return run_id, "failed", transport.safe_error(exc)
    if summary.get("verified") is not True:
        return run_id, "failed", "runner provenance is not verified"
    return run_id, "completed", None


def run_planning_runs(articles: Iterable[Article], concurrency: int, timeout: int) -> None:
    if concurrency < 1:
        raise PipelineError("Planning concurrency must be at least 1")
    articles = tuple(articles)
    failures: list[str] = []
    completed_count = 0
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="lite-plan") as executor:
        futures: dict[Future[tuple[str, str, str | None]], Article] = {
            executor.submit(run_one_planning, article, timeout): article
            for article in articles
        }
        for future in as_completed(futures):
            run_id, status, error = future.result()
            completed_count += 1
            suffix = f": {error}" if error else ""
            print(
                f"planning [{completed_count}/{len(articles)}] {run_id} -> {status}{suffix}",
                flush=True,
            )
            if error:
                failures.append(f"{run_id}: {error}")
    if failures:
        raise PipelineError(f"{len(failures)} planning run(s) failed: {'; '.join(failures)}")


def sync_planning_artifacts(articles: Iterable[Article]) -> None:
    for article in articles:
        run_id = article.sample.planning_run_id
        summary = runner.provenance_summary(ROOT, run_id)
        if summary.get("verified") is not True:
            raise PipelineError(f"Canonical planning provenance failed: {run_id}")
        source_dir = ROOT / native.ARTIFACT_NAMESPACE / run_id
        destination_dir = TEST_ROOT / native.ARTIFACT_NAMESPACE / run_id
        for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            copy_exact(source, destination_dir / source.relative_to(source_dir))
        copied = runner.provenance_summary(TEST_ROOT, run_id)
        if copied.get("verified") is not True:
            raise PipelineError(f"Self-contained planning provenance failed: {run_id}")


def materialize_generation(articles: Iterable[Article]) -> int:
    configure_native(articles)
    rows = native.materialize(ROOT)
    print(
        f"PASS: materialized {len(rows)} provider jobs from {len(native.SAMPLES)} verified Lite planning runs"
    )
    return 0


def run_generation(
    articles: Iterable[Article],
    *,
    concurrency: int,
    wan22_concurrency: int | None = None,
    wan27_concurrency: int | None = None,
    veo31_concurrency: int | None = None,
    timeout: int,
    poll_interval: float,
    dry_run: bool,
    fail_fast: bool,
    run_ids: Iterable[str] = (),
    models: Iterable[str] = (),
) -> int:
    models = tuple(models) or MODEL_IDS
    configure_native(articles)
    argv = [
        "run",
        "--concurrency",
        str(concurrency),
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
    ]
    for flag, value in (
        ("--wan22-concurrency", wan22_concurrency),
        ("--wan27-concurrency", wan27_concurrency),
        ("--veo31-concurrency", veo31_concurrency),
    ):
        if value is not None:
            argv.extend((flag, str(value)))
    if dry_run:
        argv.append("--dry-run")
    else:
        argv.append("--allow-external-processing")
    if fail_fast:
        argv.append("--fail-fast")
    for run_id in run_ids:
        argv.extend(("--run-id", run_id))
    for model_id in models:
        argv.extend(("--model", model_id))
    return native.main(argv, ROOT)


def revalidate_primary_wan_downloads(articles: Iterable[Article]) -> int:
    """Re-probe downloaded legacy outputs without any provider resubmit."""

    articles = tuple(articles)
    configure_native(articles)
    revalidated = 0
    for article in articles:
        entry = native.Entry(article.sample, native.WAN_MODEL_ID)
        paths = native.artifact_paths(entry, ROOT)
        if not paths["video"].is_file() or not paths["run"].is_file():
            continue
        job = native.load_lite_job(entry, ROOT)
        if read_json(paths["prompt"]) != native.prompt_artifact(job):
            raise PipelineError(f"Prompt differs from verified Lite result: {entry.run_id}")
        run = read_json(paths["run"])
        request = run.get("request")
        if not isinstance(request, dict):
            raise PipelineError(f"Downloaded Wan run has no request: {entry.run_id}")
        expected_fingerprint = transport.request_fingerprint(request, native.provider_sample(entry))
        if run.get("request_sha256") != expected_fingerprint:
            raise PipelineError(f"Downloaded Wan request fingerprint mismatch: {entry.run_id}")
        media = transport.ffprobe_media(paths["video"])
        check = native.strict_media_contract(entry, media)
        run.update(
            {
                "status": "succeeded" if check["conforms"] else "verification-failed",
                "completed_at": run.get("completed_at") or transport.utc_now(),
                "media": media,
                "contract_check": check,
                "provider_may_be_active": False,
                "last_worker_failure": None,
                "error": None if check["conforms"] else "; ".join(check["warnings"]),
            }
        )
        transport.atomic_write_json(paths["run"], run)
        revalidated += 1
    native.materialize(ROOT)
    return revalidated


def primary_wan_succeeded(article: Article) -> bool:
    entry = native.Entry(article.sample, native.WAN_MODEL_ID)
    paths = native.artifact_paths(entry, ROOT)
    if not paths["run"].is_file() or not paths["video"].is_file():
        return False
    run = read_json(paths["run"])
    check = run.get("contract_check")
    return run.get("status") == "succeeded" and isinstance(check, dict) and check.get("conforms") is True


def wan_retry_articles(articles: Iterable[Article]) -> tuple[Article, ...]:
    articles = tuple(articles)
    configure_native(articles)
    return tuple(article for article in articles if not primary_wan_succeeded(article))


def run_wan_retry(
    articles: Iterable[Article],
    *,
    timeout: int,
    poll_interval: float,
    dry_run: bool,
    fail_fast: bool,
) -> int:
    articles = tuple(articles)
    revalidate_primary_wan_downloads(articles)
    retry_articles = wan_retry_articles(articles)
    if not retry_articles:
        print("PASS: all primary Wan outputs already conform; no retry jobs needed")
        return 0
    configure_native(
        retry_articles,
        provider_batch_id=WAN_RETRY1_BATCH_ID,
        provider_model_ids=(native.WAN_MODEL_ID,),
        manifest_path=WAN_RETRY1_MANIFEST_REL,
        wan_submit_mode="named",
    )
    rows = native.materialize(ROOT)
    argv = [
        "run",
        "--concurrency",
        "1",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
    ]
    argv.append("--dry-run" if dry_run else "--allow-external-processing")
    if fail_fast:
        argv.append("--fail-fast")
    failures = native.run_selected(rows, native.build_parser().parse_args(argv), ROOT)
    native.write_manifest(rows, ROOT)
    if failures:
        print(f"FAIL: {failures} Wan retry generation(s) failed", file=sys.stderr)
        return 1
    print(
        "PASS: named-endpoint Wan retry requests validated"
        if dry_run
        else "PASS: named-endpoint Wan retry generations completed"
    )
    return 0


def frozen_wan_retry_articles(articles: Iterable[Article]) -> tuple[Article, ...]:
    """Return the frozen 18-item Wan retry matrix in its canonical order."""

    by_sample_id = {article.sample.sample_id: article for article in articles}
    missing = [
        sample_id
        for sample_id in WAN_RETRY_SAMPLE_IDS
        if sample_id not in by_sample_id
    ]
    if missing:
        raise PipelineError(
            "Frozen Wan retry set is missing article(s): " + ", ".join(missing)
        )
    if len(set(WAN_RETRY_SAMPLE_IDS)) != len(WAN_RETRY_SAMPLE_IDS):
        raise PipelineError("Frozen Wan retry set contains duplicate IDs")
    return tuple(by_sample_id[sample_id] for sample_id in WAN_RETRY_SAMPLE_IDS)


def configure_wan_retry3(articles: Iterable[Article]) -> tuple[Article, ...]:
    """Bind the native bridge to the isolated, immutable retry3 namespace."""

    retry_articles = frozen_wan_retry_articles(articles)
    configure_native(
        retry_articles,
        provider_batch_id=WAN_RETRY3_BATCH_ID,
        provider_model_ids=(native.WAN_MODEL_ID,),
        manifest_path=WAN_RETRY3_MANIFEST_REL,
        wan_submit_mode="named",
    )
    return retry_articles


def wan_row_succeeded(row: dict[str, Any]) -> bool:
    paths = row["paths"]
    if not paths["run"].is_file() or not paths["video"].is_file():
        return False
    run = read_json(paths["run"])
    check = run.get("contract_check")
    return (
        run.get("status") == "succeeded"
        and isinstance(check, dict)
        and check.get("conforms") is True
    )


def wan_row_may_be_active(row: dict[str, Any]) -> bool:
    run_path = row["paths"]["run"]
    if not run_path.is_file():
        return False
    run = read_json(run_path)
    return (
        run.get("status")
        in {"submitting", "submitted", "running", "submit-unknown"}
        or run.get("provider_may_be_active") is True
    )


def run_wan_retry3(
    articles: Iterable[Article],
    *,
    canary_only: bool,
    timeout: int,
    poll_interval: float,
    dry_run: bool,
    fail_fast: bool,
) -> int:
    """Run retry3 without consulting or mutating retry1/retry2 receipts."""

    configure_wan_retry3(tuple(articles))
    rows = native.materialize(ROOT)
    canary_rows = [
        row
        for row in rows
        if row["entry"].sample.sample_id == WAN_RETRY3_CANARY_SAMPLE_ID
    ]
    if len(canary_rows) != 1:
        raise PipelineError(
            f"Retry3 must contain exactly one canary {WAN_RETRY3_CANARY_SAMPLE_ID}"
        )
    canary = canary_rows[0]

    if canary_only:
        if wan_row_succeeded(canary):
            native.write_manifest(rows, ROOT)
            print("PASS: retry3 canary already conforms; no provider call needed")
            return 0
        active_others = [
            row["entry"].run_id
            for row in rows
            if row is not canary and wan_row_may_be_active(row)
        ]
        if active_others:
            raise PipelineError(
                "Cannot run the retry3 canary while other retry3 jobs may be active: "
                + ", ".join(active_others)
            )
        selected = [canary]
    else:
        if not dry_run and not wan_row_succeeded(canary):
            raise PipelineError(
                "Retry3 canary must have a conforming succeeded MP4 before the "
                "remaining 17 jobs may be submitted"
            )
        # A successful canary (and any successful partial full-run outputs) is
        # excluded at the filter level, so run_selected cannot submit it again.
        selected = [row for row in rows if not wan_row_succeeded(row)]

    if not selected:
        native.write_manifest(rows, ROOT)
        print("PASS: all retry3 Wan outputs already conform; no provider calls needed")
        return 0

    argv = [
        "run",
        "--concurrency",
        "1",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
    ]
    for row in selected:
        argv.extend(("--run-id", row["entry"].run_id))
    argv.append("--dry-run" if dry_run else "--allow-external-processing")
    if fail_fast or canary_only:
        argv.append("--fail-fast")
    failures = native.run_selected(
        rows,
        native.build_parser().parse_args(argv),
        ROOT,
    )
    native.write_manifest(rows, ROOT)
    if failures:
        scope = "canary" if canary_only else "remaining batch"
        print(
            f"FAIL: {failures} retry3 Wan {scope} generation(s) failed",
            file=sys.stderr,
        )
        return 1
    if canary_only:
        print(
            "PASS: retry3 canary request validated"
            if dry_run
            else "PASS: retry3 canary generated and verified"
        )
    else:
        print(
            "PASS: retry3 full request set validated"
            if dry_run
            else "PASS: retry3 remaining Wan generations completed"
        )
    return 0


def select_wan_attempt(
    *,
    primary: Any,
    retry1: Any,
    retry2: Any,
    retry3: Any,
    legacy_retry5: Any,
) -> dict[str, Any] | None:
    """Select a generated Wan result without hiding immutable attempt history."""

    # The normal legacy queue is the canonical Wan 2.2 route. Keep successful
    # primary outputs first, then prefer the final legacy retry over diagnostic
    # named-endpoint attempts when both happen to contain a usable MP4.
    attempts = (primary, legacy_retry5, retry3, retry2, retry1)
    return next(
        (
            attempt
            for attempt in attempts
            if isinstance(attempt, dict) and attempt.get("status") == "succeeded"
        ),
        None,
    ) or next(
        (attempt for attempt in attempts[1:] + attempts[:1] if isinstance(attempt, dict)),
        None,
    )


def build_final_manifest(articles: Iterable[Article], updated_at: str | None = None) -> dict[str, Any]:
    articles = tuple(articles)
    configure_native(articles)
    native.materialize(ROOT)
    generation = read_json(ROOT / GENERATION_MANIFEST_REL)
    primary_outputs = {
        (output.get("article_slug"), output.get("model_id")): output
        for output in generation.get("outputs", [])
        if isinstance(output, dict)
    }
    retry1_path = ROOT / WAN_RETRY1_MANIFEST_REL
    retry1_generation = (
        read_json(retry1_path) if retry1_path.is_file() else {"outputs": []}
    )
    retry1_outputs = {
        (output.get("article_slug"), output.get("model_id")): output
        for output in retry1_generation.get("outputs", [])
        if isinstance(output, dict)
    }
    retry2_path = ROOT / WAN_RETRY2_MANIFEST_REL
    retry2_generation = (
        read_json(retry2_path) if retry2_path.is_file() else {"outputs": []}
    )
    retry2_outputs = {
        (output.get("article_slug"), output.get("model_id")): output
        for output in retry2_generation.get("outputs", [])
        if isinstance(output, dict)
    }
    retry3_path = ROOT / WAN_RETRY3_MANIFEST_REL
    retry3_generation = (
        read_json(retry3_path) if retry3_path.is_file() else {"outputs": []}
    )
    retry3_outputs = {
        (output.get("article_slug"), output.get("model_id")): output
        for output in retry3_generation.get("outputs", [])
        if isinstance(output, dict)
    }
    legacy_retry5_path = ROOT / WAN_LEGACY_RETRY5_MANIFEST_REL
    legacy_retry5_generation = (
        read_json(legacy_retry5_path)
        if legacy_retry5_path.is_file()
        else {"outputs": []}
    )
    legacy_retry5_outputs = {
        (output.get("article_slug"), output.get("model_id")): output
        for output in legacy_retry5_generation.get("outputs", [])
        if isinstance(output, dict)
    }
    article_records: list[dict[str, Any]] = []
    all_outputs: list[dict[str, Any]] = []
    for article in articles:
        sample = article.sample
        run_id = sample.planning_run_id
        canonical_summary = runner.provenance_summary(ROOT, run_id)
        copied_summary = runner.provenance_summary(TEST_ROOT, run_id)
        if canonical_summary.get("verified") is not True or copied_summary.get("verified") is not True:
            raise PipelineError(f"Planning provenance failed: {run_id}")
        result_path = ROOT / native.ARTIFACT_NAMESPACE / run_id / "result.json"
        result = read_json(result_path)
        models = result.get("models")
        if not isinstance(models, list):
            raise PipelineError(f"Planning models are missing: {run_id}")
        model_map = {model.get("model_id"): model for model in models if isinstance(model, dict)}
        outputs: list[dict[str, Any]] = []
        for model_id in MODEL_IDS:
            entry = native.Entry(sample, model_id)
            primary = primary_outputs.get((article.slug, model_id))
            retry1 = retry1_outputs.get((article.slug, model_id))
            retry2 = retry2_outputs.get((article.slug, model_id))
            retry3 = retry3_outputs.get((article.slug, model_id))
            legacy_retry5 = legacy_retry5_outputs.get((article.slug, model_id))
            output = primary
            if model_id == native.WAN_MODEL_ID:
                output = select_wan_attempt(
                    primary=primary,
                    retry1=retry1,
                    retry2=retry2,
                    retry3=retry3,
                    legacy_retry5=legacy_retry5,
                )
            model = model_map.get(model_id)
            if output is None or model is None:
                raise PipelineError(f"Missing model output binding: {entry.provider_run_id}")
            attempts = [
                {
                    "provider_run_id": attempt.get("provider_run_id"),
                    "status": attempt.get("status"),
                    "run_path": attempt.get("run_path"),
                    "video_path": attempt.get("video_path"),
                    "error": attempt.get("error"),
                }
                for attempt in (
                    primary,
                    retry1,
                    retry2,
                    retry3,
                    legacy_retry5,
                )
                if isinstance(attempt, dict)
            ]
            record = {
                "provider_run_id": output.get("provider_run_id"),
                "model_id": model_id,
                "scene_plan": model.get("scene_plan"),
                "positive_prompt": model.get("positive_prompt"),
                "negative_prompt": model.get("negative_prompt"),
                "status": output.get("status"),
                "prompt_path": output.get("prompt_path"),
                "run_path": output.get("run_path"),
                "video_path": output.get("video_path"),
                "media": output.get("media"),
                "contract_check": output.get("contract_check"),
                "error": output.get("error"),
                "attempts": attempts,
            }
            outputs.append(record)
            all_outputs.append({"article_slug": article.slug, **record})
        article_records.append(
            {
                "article_number": article.number,
                "article_slug": article.slug,
                "title": article.title,
                "context_path": (TEST_ROOT_REL / article.context_path).as_posix(),
                "selected_image": article.selected,
                "lite_planning": {
                    "run_id": run_id,
                    "canonical_result_path": relative(result_path),
                    "self_contained_result_path": (
                        TEST_ROOT_REL / native.ARTIFACT_NAMESPACE / run_id / "result.json"
                    ).as_posix(),
                    "structured_intent": result.get("analysis", {}).get("structured_intent"),
                    "provenance": canonical_summary,
                    "self_contained_provenance": copied_summary,
                },
                "outputs": outputs,
            }
        )
    status_summary: dict[str, int] = {}
    for output in all_outputs:
        status = str(output.get("status") or "missing")
        status_summary[status] = status_summary.get(status, 0) + 1
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": native.AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "article_count": len(article_records),
        "models": list(MODEL_IDS),
        "expected_outputs": len(article_records) * len(MODEL_IDS),
        "status_summary": status_summary,
        "dataset_manifest": DATASET_MANIFEST_REL.as_posix(),
        "generation_manifests": [
            GENERATION_MANIFEST_REL.as_posix(),
            *([WAN_RETRY1_MANIFEST_REL.as_posix()] if retry1_path.is_file() else []),
            *([WAN_RETRY2_MANIFEST_REL.as_posix()] if retry2_path.is_file() else []),
            *([WAN_RETRY3_MANIFEST_REL.as_posix()] if retry3_path.is_file() else []),
            *(
                [WAN_LEGACY_RETRY5_MANIFEST_REL.as_posix()]
                if legacy_retry5_path.is_file()
                else []
            ),
        ],
        "articles": article_records,
        "outputs": all_outputs,
    }


def final_output_acceptance_error(
    output: Any,
    *,
    allow_contract_warnings: bool,
    root: Path | None = None,
) -> str | None:
    """Return why a selected final output is not an acceptable complete file.

    Contract-warning acceptance is deliberately narrower than
    ``allow_incomplete``: the raw MP4 and its measured media contract must both
    exist, while the receipt remains visibly ``verification-failed``.
    """

    root = ROOT if root is None else root
    if not isinstance(output, dict):
        return "final output is not an object"
    run_id = output.get("provider_run_id")
    label = run_id if isinstance(run_id, str) and run_id else "unknown output"
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
    conforms = check.get("conforms")
    if status == "succeeded":
        if conforms is not True:
            return f"{label}: succeeded output does not conform"
        return None
    if not allow_contract_warnings:
        return f"{label}: media contract failed and warnings were not allowed"
    warnings = check.get("warnings")
    if conforms is not False or not isinstance(warnings, list) or not warnings:
        return f"{label}: verification failure has no explicit contract violations"
    if any(not isinstance(warning, str) or not warning for warning in warnings):
        return f"{label}: media contract violations are invalid"
    return None


def final_output_acceptance_errors(
    document: Any,
    *,
    allow_contract_warnings: bool,
    root: Path | None = None,
) -> list[str]:
    if not isinstance(document, dict):
        return ["Final manifest is not an object"]
    outputs = document.get("outputs")
    expected = document.get("expected_outputs")
    if not isinstance(outputs, list):
        return ["Final manifest outputs are missing"]
    errors: list[str] = []
    if not isinstance(expected, int) or len(outputs) != expected:
        errors.append(
            f"Final manifest output count mismatch: expected {expected}, got {len(outputs)}"
        )
    for output in outputs:
        error = final_output_acceptance_error(
            output,
            allow_contract_warnings=allow_contract_warnings,
            root=root,
        )
        if error:
            errors.append(error)
    return errors


def finalize(
    articles: Iterable[Article],
    *,
    allow_contract_warnings: bool = False,
) -> dict[str, Any]:
    sync_planning_artifacts(articles)
    document = build_final_manifest(articles)
    errors = final_output_acceptance_errors(
        document,
        allow_contract_warnings=allow_contract_warnings,
    )
    if errors:
        detail = "; ".join(errors[:5])
        if len(errors) > 5:
            detail += f"; and {len(errors) - 5} more"
        raise PipelineError(
            f"Cannot finalize: {len(errors)} selected output(s) are not acceptable: {detail}"
        )
    transport.atomic_write_json(ROOT / FINAL_MANIFEST_REL, document)
    return document


def verify_dataset(articles: Iterable[Article]) -> list[str]:
    errors: list[str] = []
    expected = dataset_document(articles)
    path = ROOT / DATASET_MANIFEST_REL
    if not path.is_file() or read_json(path) != expected:
        errors.append("Dataset manifest does not match the 20 article inventories")
    for article in articles:
        context_copy = TEST_ROOT / article.context_path
        if not context_copy.is_file() or sha256_file(context_copy) != article.context_sha256:
            errors.append(f"Context copy mismatch: {article.slug}")
        for image in article.images:
            copy_path = ROOT / image["copy_path"]
            if not copy_path.is_file() or sha256_file(copy_path) != image["sha256"]:
                errors.append(f"Image copy mismatch: {image['copy_path']}")
    return errors


def verify_all(
    articles: Iterable[Article],
    *,
    allow_incomplete: bool,
    allow_contract_warnings: bool,
) -> tuple[bool, list[str]]:
    articles = tuple(articles)
    configure_native(articles)
    errors = verify_dataset(articles)
    for article in articles:
        run_id = article.sample.planning_run_id
        for workspace, label in ((ROOT, "canonical"), (TEST_ROOT, "self-contained")):
            try:
                summary = runner.provenance_summary(workspace, run_id)
            except Exception as exc:
                errors.append(f"{label} provenance failed for {run_id}: {transport.safe_error(exc)}")
                continue
            if summary.get("verified") is not True:
                errors.append(f"{label} provenance is not verified: {run_id}")
    retry1_manifest_exists = (ROOT / WAN_RETRY1_MANIFEST_REL).is_file()
    retry2_manifest_exists = (ROOT / WAN_RETRY2_MANIFEST_REL).is_file()
    retry3_manifest_exists = (ROOT / WAN_RETRY3_MANIFEST_REL).is_file()
    legacy_retry5_manifest_exists = (
        ROOT / WAN_LEGACY_RETRY5_MANIFEST_REL
    ).is_file()
    batch_ok, batch_errors = native.verify(
        ROOT,
        allow_incomplete=(
            allow_incomplete
            or retry1_manifest_exists
            or retry2_manifest_exists
            or retry3_manifest_exists
            or legacy_retry5_manifest_exists
        ),
        allow_contract_warnings=allow_contract_warnings,
    )
    if not batch_ok:
        errors.extend(batch_errors)
    retry_articles = frozen_wan_retry_articles(articles)
    if retry1_manifest_exists:
        configure_native(
            retry_articles,
            provider_batch_id=WAN_RETRY1_BATCH_ID,
            provider_model_ids=(native.WAN_MODEL_ID,),
            manifest_path=WAN_RETRY1_MANIFEST_REL,
            wan_submit_mode="named",
        )
        retry1_ok, retry1_errors = native.verify(
            ROOT,
            # Retry1 is immutable history once a later retry exists; its terminal
            # failures remain auditable but no longer gate the final batch.
            allow_incomplete=(
                allow_incomplete
                or retry2_manifest_exists
                or retry3_manifest_exists
                or legacy_retry5_manifest_exists
            ),
            allow_contract_warnings=allow_contract_warnings,
        )
        if not retry1_ok:
            errors.extend(f"Wan retry1: {error}" for error in retry1_errors)
    if retry2_manifest_exists:
        configure_native(
            retry_articles,
            provider_batch_id=WAN_RETRY2_BATCH_ID,
            provider_model_ids=(native.WAN_MODEL_ID,),
            manifest_path=WAN_RETRY2_MANIFEST_REL,
            wan_submit_mode="named",
        )
        retry2_ok, retry2_errors = native.verify(
            ROOT,
            allow_incomplete=(
                allow_incomplete
                or retry3_manifest_exists
                or legacy_retry5_manifest_exists
            ),
            allow_contract_warnings=allow_contract_warnings,
        )
        if not retry2_ok:
            errors.extend(f"Wan retry2: {error}" for error in retry2_errors)
    if retry3_manifest_exists:
        configure_wan_retry3(articles)
        retry3_ok, retry3_errors = native.verify(
            ROOT,
            allow_incomplete=allow_incomplete or legacy_retry5_manifest_exists,
            allow_contract_warnings=allow_contract_warnings,
        )
        if not retry3_ok:
            errors.extend(f"Wan retry3: {error}" for error in retry3_errors)
    if legacy_retry5_manifest_exists:
        configure_native(
            retry_articles,
            provider_batch_id=WAN_LEGACY_RETRY5_BATCH_ID,
            provider_model_ids=(native.WAN_MODEL_ID,),
            manifest_path=WAN_LEGACY_RETRY5_MANIFEST_REL,
            wan_submit_mode="legacy",
        )
        legacy_retry5_ok, legacy_retry5_errors = native.verify(
            ROOT,
            allow_incomplete=allow_incomplete,
            allow_contract_warnings=allow_contract_warnings,
        )
        if not legacy_retry5_ok:
            errors.extend(
                f"Wan legacy retry5: {error}"
                for error in legacy_retry5_errors
            )
    manifest_path = ROOT / FINAL_MANIFEST_REL
    if not manifest_path.is_file():
        errors.append(f"Missing final manifest: {FINAL_MANIFEST_REL}")
    else:
        manifest = read_json(manifest_path)
        updated_at = manifest.get("updated_at") if isinstance(manifest, dict) else None
        rebuilt_manifest = (
            build_final_manifest(articles, updated_at)
            if isinstance(updated_at, str)
            else None
        )
        if rebuilt_manifest is None or manifest != rebuilt_manifest:
            errors.append("Final manifest does not match planning and provider artifacts")
        if not allow_incomplete and rebuilt_manifest is not None:
            errors.extend(
                final_output_acceptance_errors(
                    rebuilt_manifest,
                    allow_contract_warnings=allow_contract_warnings,
                )
            )
    report = {
        "schema_version": 1,
        "ticket": TICKET,
        "passed": not errors,
        "allow_incomplete": allow_incomplete,
        "allow_contract_warnings": allow_contract_warnings,
        "article_count": len(articles),
        "expected_outputs": len(articles) * len(MODEL_IDS),
        "errors": errors,
    }
    transport.atomic_write_json(ROOT / VERIFICATION_REPORT_REL, report)
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
    subparsers.add_parser("prepare-dataset", help="mirror all 20 articles and locked Lite files")
    subparsers.add_parser("prepare-plans", help="prepare 20 immutable shared Lite planning jobs")
    run_plans = subparsers.add_parser("run-plans", help="run or resume 20 isolated Lite analyses")
    run_plans.add_argument("--concurrency", type=positive_int, default=3)
    run_plans.add_argument("--timeout", type=positive_int, default=1800)
    subparsers.add_parser("plan-generation", help="materialize the 60 provider jobs")
    generate = subparsers.add_parser("generate", help="run or resume the 60 provider jobs")
    generate.add_argument(
        "--concurrency",
        type=positive_int,
        default=3,
        help="deprecated fallback applied independently to both Eliza routes",
    )
    generate.add_argument(
        "--wan22-concurrency",
        type=positive_int,
        help="Gradio / Wan 2.2 route limit (default and maximum: 1)",
    )
    generate.add_argument(
        "--wan27-concurrency",
        type=positive_int,
        help="Eliza / Wan 2.7 route limit (default and maximum: 3)",
    )
    generate.add_argument(
        "--veo31-concurrency",
        type=positive_int,
        help="Eliza / Veo 3.1 Lite route limit (default and maximum: 3)",
    )
    generate.add_argument("--timeout", type=positive_int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--fail-fast", action="store_true")
    generate.add_argument("--run-id", action="append", default=[])
    generate.add_argument("--model", action="append", default=[])
    subparsers.add_parser(
        "revalidate-wan",
        help="re-probe already downloaded legacy Wan MP4s without provider calls",
    )
    wan_retry = subparsers.add_parser(
        "generate-wan-retry",
        help="disabled immutable retry1 command retained for explicit diagnostics",
    )
    wan_retry.add_argument("--timeout", type=positive_int, default=1800)
    wan_retry.add_argument("--poll-interval", type=float, default=10.0)
    wan_retry.add_argument("--dry-run", action="store_true")
    wan_retry.add_argument("--fail-fast", action="store_true")
    for command, help_text in (
        (
            "generate-wan-retry3-canary",
            f"run only retry3 canary {WAN_RETRY3_CANARY_SAMPLE_ID}",
        ),
        (
            "generate-wan-retry3",
            "resume retry3 after its canary succeeds, excluding all succeeded runs",
        ),
    ):
        retry3 = subparsers.add_parser(command, help=help_text)
        retry3.add_argument("--timeout", type=positive_int, default=1800)
        retry3.add_argument("--poll-interval", type=float, default=10.0)
        retry3.add_argument("--dry-run", action="store_true")
        retry3.add_argument("--fail-fast", action="store_true")
    finalize_parser = subparsers.add_parser(
        "finalize",
        help="copy planning artifacts and build the review manifest",
    )
    finalize_parser.add_argument(
        "--allow-contract-warnings",
        action="store_true",
        help="accept complete raw MP4s while preserving explicit media-contract violations",
    )
    verify = subparsers.add_parser("verify", help="verify dataset, provenance, and all 60 MP4s")
    verify.add_argument("--allow-incomplete", action="store_true")
    verify.add_argument(
        "--allow-contract-warnings",
        action="store_true",
        help="accept complete raw MP4s while preserving explicit media-contract violations",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        articles = prepare_dataset(ROOT)
        configure_native(articles)
        if args.command == "prepare-dataset":
            print(
                f"PASS: mirrored {len(articles)} articles and "
                f"{sum(len(article.images) for article in articles)} source images"
            )
            return 0
        if args.command == "prepare-plans":
            prepare_planning_runs(articles)
            return 0
        if args.command == "run-plans":
            prepare_planning_runs(articles)
            run_planning_runs(articles, args.concurrency, args.timeout)
            return 0
        if args.command == "plan-generation":
            sync_planning_artifacts(articles)
            return materialize_generation(articles)
        if args.command == "generate":
            sync_planning_artifacts(articles)
            return run_generation(
                articles,
                concurrency=args.concurrency,
                wan22_concurrency=args.wan22_concurrency,
                wan27_concurrency=args.wan27_concurrency,
                veo31_concurrency=args.veo31_concurrency,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                dry_run=args.dry_run,
                fail_fast=args.fail_fast,
                run_ids=args.run_id,
                models=args.model,
            )
        if args.command == "revalidate-wan":
            count = revalidate_primary_wan_downloads(articles)
            print(f"PASS: revalidated {count} downloaded primary Wan MP4(s)")
            return 0
        if args.command == "generate-wan-retry":
            raise PipelineError(
                "retry1 is immutable after its terminal failures; use "
                "generate-wan-retry3-canary followed by generate-wan-retry3"
            )
        if args.command in {
            "generate-wan-retry3-canary",
            "generate-wan-retry3",
        }:
            sync_planning_artifacts(articles)
            return run_wan_retry3(
                articles,
                canary_only=args.command == "generate-wan-retry3-canary",
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                dry_run=args.dry_run,
                fail_fast=args.fail_fast,
            )
        if args.command == "finalize":
            document = finalize(
                articles,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            print(
                f"PASS: final manifest contains {document['article_count']} articles and "
                f"{document['expected_outputs']} outputs"
            )
            return 0
        if args.command == "verify":
            passed, errors = verify_all(
                articles,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: PROMOPAGES-9910 Clipmaker Lite 20x3 batch is valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except (PipelineError, native.BatchPipelineError, transport.PipelineError, OSError) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
