#!/usr/bin/env python3
"""Run the PROMOPAGES-9929 case-14 cross-model prompt experiment.

This is deliberately an experimental generation bridge, not a canonical
Clipmaker Lite authoring run.  It verifies the existing attested case-14 Lite
result, extracts the exact Wan 2.2 positive prompt, and sends that unchanged
input prompt to Wan 2.7 and Veo 3.1 Lite through their fixed generation routes.
Provider-side prompt expansion remains enabled because both target routes
require it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9929"
EXPERIMENT_ID = "promopages-9929-case14-wan22-prompt-v1"
PLANNING_RUN_ID = "promopages-9910-lite20-20260724-r2-14-miuz-modnye-sergi"
SOURCE_MODEL_ID = "alibaba/wan-2.2"
TARGET_MODEL_IDS = ("alibaba/wan-2.7", "google/veo-3.1-lite")
MODEL_DIRECTORIES = {
    "alibaba/wan-2.7": "wan-2.7",
    "google/veo-3.1-lite": "veo-3.1-lite",
}
MODEL_SUFFIXES = {
    "alibaba/wan-2.7": "wan-2-7",
    "google/veo-3.1-lite": "veo-3-1-lite",
}
ARTICLE_NUMBER = "14"
ARTICLE_SLUG = "14-miuz-modnye-sergi"
IMAGE_ID = "01"
SOURCE_PATH = f"PROMOPAGES-9857/articles/{ARTICLE_SLUG}/01.jpeg"
SOURCE_SHA256 = "7405154161aca78078f95474813f1927d0e203f80873077a5b8600bc21776dd6"
SOURCE_WIDTH = 1200
SOURCE_HEIGHT = 675
EXPECTED_PROMPT_SHA256 = "71352fa20f1bbba882c9900a9656aafd0764fc93d71ca5c6a4cf06c02b82a5ad"
PUBLIC_SOURCE_BASE = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/main/"
)
OUTPUT_ROOT = (
    Path("clipmaker-lite-test/videos") / EXPERIMENT_ID / ARTICLE_SLUG
)
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
SHOWCASE_MANIFEST_PATH = Path("clipmaker-lite-test/manifest.json")
COMPLETE_STATUSES = {"succeeded", "verification-failed"}
ALLOWED_WAN_AUDIO_WARNING = (
    "provider returned has_audio=True despite generate_audio=False"
)


class ExperimentError(RuntimeError):
    """A fail-closed, user-actionable experiment error."""


@dataclass(frozen=True)
class PromptSource:
    positive_prompt: str
    scene_plan: str
    result_path: str
    result_sha256: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class ExperimentRow:
    model_id: str
    provider_run_id: str
    source: PromptSource
    sample: dict[str, Any]
    prompt: dict[str, Any]
    runtime: dict[str, Any]
    paths: dict[str, Path]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise ExperimentError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExperimentError(f"Invalid JSON in {path}: {exc}") from exc


def relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ExperimentError(f"Path escapes workspace: {path}") from exc


def load_prompt_source(root: Path = ROOT) -> PromptSource:
    """Verify the canonical Lite run before extracting the Wan 2.2 prompt."""

    try:
        provenance = clipmaker_lite_runner.provenance_summary(root, PLANNING_RUN_ID)
    except Exception as exc:
        raise ExperimentError(
            f"Clipmaker Lite provenance failed: {transport.safe_error(exc)}"
        ) from exc
    if provenance.get("verified") is not True:
        raise ExperimentError("Clipmaker Lite provenance is not verified")
    if provenance.get("agent_id") != "clipmaker-lite":
        raise ExperimentError("Unexpected prompt source agent")
    if provenance.get("models") != [
        "alibaba/wan-2.2",
        "alibaba/wan-2.7",
        "google/veo-3.1-lite",
    ]:
        raise ExperimentError("Unexpected model set in the prompt source")
    if provenance.get("source_image_sha256") != SOURCE_SHA256:
        raise ExperimentError("Prompt source image digest does not match case 14")

    expected_result = (
        Path("artifacts/clipmaker-lite/v1") / PLANNING_RUN_ID / "result.json"
    )
    if provenance.get("result_path") != expected_result.as_posix():
        raise ExperimentError("Unexpected prompt source result path")
    result_path = root / expected_result
    result = read_json(result_path)
    inputs = result.get("inputs") if isinstance(result, dict) else None
    source_image = inputs.get("source_image") if isinstance(inputs, dict) else None
    if not isinstance(source_image, dict):
        raise ExperimentError("Prompt source image binding is missing")
    if (
        source_image.get("path") != SOURCE_PATH
        or source_image.get("sha256") != SOURCE_SHA256
    ):
        raise ExperimentError("Prompt source image binding changed")

    models = result.get("models")
    if not isinstance(models, list):
        raise ExperimentError("Prompt source models are missing")
    source_model = next(
        (
            model
            for model in models
            if isinstance(model, dict) and model.get("model_id") == SOURCE_MODEL_ID
        ),
        None,
    )
    if not isinstance(source_model, dict):
        raise ExperimentError("Wan 2.2 prompt source is missing")
    positive = source_model.get("positive_prompt")
    scene_plan = source_model.get("scene_plan")
    if not isinstance(positive, str) or not positive.strip():
        raise ExperimentError("Wan 2.2 positive prompt is empty")
    if not isinstance(scene_plan, str) or not scene_plan.strip():
        raise ExperimentError("Wan 2.2 scene plan is empty")
    if source_model.get("negative_prompt") is not None:
        raise ExperimentError("Case-14 Wan 2.2 negative prompt must remain null")
    if sha256_text(positive) != EXPECTED_PROMPT_SHA256:
        raise ExperimentError("Case-14 Wan 2.2 prompt changed")
    source_file = root / SOURCE_PATH
    if not source_file.is_file() or transport.sha256_file(source_file) != SOURCE_SHA256:
        raise ExperimentError("Current case-14 source image changed")

    return PromptSource(
        positive_prompt=positive,
        scene_plan=scene_plan,
        result_path=expected_result.as_posix(),
        result_sha256=transport.sha256_file(result_path),
        provenance=provenance,
    )


def provider_sample() -> dict[str, Any]:
    return {
        "sample_id": "14-miuz-wan22-prompt-replay",
        "article_slug": ARTICLE_SLUG,
        "image_id": IMAGE_ID,
        "image_number": IMAGE_ID,
        "source_path": SOURCE_PATH,
        "source_url": PUBLIC_SOURCE_BASE + quote(SOURCE_PATH, safe="/"),
        "sha256": SOURCE_SHA256,
        "width": SOURCE_WIDTH,
        "height": SOURCE_HEIGHT,
    }


def provider_prompt(model_id: str, source: PromptSource) -> dict[str, Any]:
    runtime = runtime_for_model(model_id)
    prompt: dict[str, Any] = {
        "sample_id": "14-miuz-wan22-prompt-replay",
        "model_id": model_id,
        "target_duration_seconds": runtime["duration_seconds"],
        "positive_prompt": source.positive_prompt,
        "negative_prompt": None,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
        "prompt_source_model_id": SOURCE_MODEL_ID,
    }
    if model_id == "alibaba/wan-2.7":
        prompt["prompt_extend"] = True
    return prompt


def runtime_for_model(model_id: str, root: Path = ROOT) -> dict[str, Any]:
    contract = read_json(root / "docs/agents/clipmaker-lite/contract.json")
    models = contract.get("models") if isinstance(contract, dict) else None
    model = models.get(model_id) if isinstance(models, dict) else None
    runtime = model.get("runtime") if isinstance(model, dict) else None
    if not isinstance(runtime, dict):
        raise ExperimentError(f"Missing locked runtime for {model_id}")
    return runtime


def artifact_paths(model_id: str, root: Path = ROOT) -> dict[str, Path]:
    try:
        directory_name = MODEL_DIRECTORIES[model_id]
    except KeyError as exc:
        raise ExperimentError(f"Unsupported experiment model: {model_id}") from exc
    base = root / OUTPUT_ROOT / directory_name
    return {
        "directory": base,
        "prompt": base / f"{IMAGE_ID}.prompt.json",
        "run": base / f"{IMAGE_ID}.run.json",
        "video": base / f"{IMAGE_ID}.mp4",
    }


def request_preview(row: ExperimentRow) -> dict[str, Any]:
    request = transport.build_request_preview(row.sample, row.prompt)
    if request.get("model") != row.model_id:
        raise ExperimentError(f"Provider request model mismatch: {row.model_id}")
    if request.get("prompt") != row.source.positive_prompt:
        raise ExperimentError(f"Provider request changed the replay prompt: {row.model_id}")
    parameters = (
        request.get("provider", {})
        .get("options", {})
        .get(transport.route_for_model(row.model_id)["provider_key"], {})
        .get("parameters")
    )
    if row.model_id == "alibaba/wan-2.7" and parameters != {"prompt_extend": True}:
        raise ExperimentError("Wan 2.7 prompt expansion must remain enabled")
    if row.model_id == "google/veo-3.1-lite" and parameters != {"enhancePrompt": True}:
        raise ExperimentError("Veo prompt enhancement must remain enabled")
    return request


def prompt_artifact(row: ExperimentRow) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "canonical_lite_artifact": False,
        "target_model_id": row.model_id,
        "source": {
            "path": SOURCE_PATH,
            "sha256": SOURCE_SHA256,
            "width": SOURCE_WIDTH,
            "height": SOURCE_HEIGHT,
        },
        "prompt_source": {
            "agent_id": "clipmaker-lite",
            "lite_run_id": PLANNING_RUN_ID,
            "model_id": SOURCE_MODEL_ID,
            "result_path": row.source.result_path,
            "result_sha256": row.source.result_sha256,
            "positive_prompt_sha256": EXPECTED_PROMPT_SHA256,
            "provenance_verified": True,
        },
        "scene_plan": row.source.scene_plan,
        "prompt": {
            "positive": row.source.positive_prompt,
            "negative": None,
        },
        "runtime": row.runtime,
    }


def initial_run(row: ExperimentRow, root: Path = ROOT) -> dict[str, Any]:
    run = transport.initial_run_artifact(row.sample, row.model_id, row.paths, root)
    run.update(
        {
            "ticket": TICKET,
            "experiment_id": EXPERIMENT_ID,
            "canonical_lite_artifact": False,
            "provider_run_id": row.provider_run_id,
            "prompt_source_model_id": SOURCE_MODEL_ID,
            "prompt_source_run_id": PLANNING_RUN_ID,
        }
    )
    return run


def materialize_row(model_id: str, source: PromptSource, root: Path = ROOT) -> ExperimentRow:
    if model_id not in TARGET_MODEL_IDS:
        raise ExperimentError(f"Unsupported experiment target: {model_id}")
    sample = provider_sample()
    runtime = runtime_for_model(model_id, root)
    paths = artifact_paths(model_id, root)
    row = ExperimentRow(
        model_id=model_id,
        provider_run_id=f"{EXPERIMENT_ID}-{MODEL_SUFFIXES[model_id]}",
        source=source,
        sample=sample,
        prompt=provider_prompt(model_id, source),
        runtime=runtime,
        paths=paths,
    )
    request_preview(row)
    paths["directory"].mkdir(parents=True, exist_ok=True)
    expected_prompt = prompt_artifact(row)
    if paths["prompt"].is_file():
        if read_json(paths["prompt"]) != expected_prompt:
            raise ExperimentError(f"Immutable prompt artifact changed: {paths['prompt']}")
    else:
        transport.atomic_write_json(paths["prompt"], expected_prompt)
    expected_run = initial_run(row, root)
    if paths["run"].is_file():
        current = read_json(paths["run"])
        identity_keys = (
            "ticket",
            "experiment_id",
            "canonical_lite_artifact",
            "provider_run_id",
            "prompt_source_model_id",
            "prompt_source_run_id",
            "model_id",
            "prompt_path",
            "output_path",
        )
        if any(current.get(key) != expected_run.get(key) for key in identity_keys):
            raise ExperimentError(f"Immutable run identity changed: {paths['run']}")
    else:
        transport.atomic_write_json(paths["run"], expected_run)
    return row


def materialize(root: Path = ROOT) -> list[ExperimentRow]:
    source = load_prompt_source(root)
    rows = [materialize_row(model_id, source, root) for model_id in TARGET_MODEL_IDS]
    write_manifest(rows, root)
    return rows


def manifest_output(row: ExperimentRow, root: Path = ROOT) -> dict[str, Any]:
    run = read_json(row.paths["run"])
    request = request_preview(row)
    provider_key = transport.route_for_model(row.model_id)["provider_key"]
    parameters = request["provider"]["options"][provider_key]["parameters"]
    return {
        "provider_run_id": row.provider_run_id,
        "model_id": row.model_id,
        "comparison_variant": "wan-2.2-prompt-replay",
        "canonical_lite_artifact": False,
        "prompt_source_model_id": SOURCE_MODEL_ID,
        "prompt_source_run_id": PLANNING_RUN_ID,
        "runtime_prompt_sha256": EXPECTED_PROMPT_SHA256,
        "provider_prompt_expansion": parameters,
        "scene_plan": row.source.scene_plan,
        "positive_prompt": row.source.positive_prompt,
        "negative_prompt": None,
        "status": run.get("status", "missing"),
        "prompt_path": relative(row.paths["prompt"], root),
        "run_path": relative(row.paths["run"], root),
        "video_path": relative(row.paths["video"], root),
        "media": run.get("media"),
        "contract_check": run.get("contract_check"),
        "error": run.get("error"),
    }


def write_manifest(rows: list[ExperimentRow], root: Path = ROOT) -> dict[str, Any]:
    outputs = [manifest_output(row, root) for row in rows]
    counts: dict[str, int] = {}
    for output in outputs:
        status = str(output["status"])
        counts[status] = counts.get(status, 0) + 1
    manifest = {
        "schema_version": 1,
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "canonical_lite_artifact": False,
        "article_number": ARTICLE_NUMBER,
        "article_slug": ARTICLE_SLUG,
        "source_path": SOURCE_PATH,
        "prompt_source": {
            "agent_id": "clipmaker-lite",
            "lite_run_id": PLANNING_RUN_ID,
            "model_id": SOURCE_MODEL_ID,
            "positive_prompt_sha256": EXPECTED_PROMPT_SHA256,
        },
        "expected_outputs": len(TARGET_MODEL_IDS),
        "summary": counts,
        "outputs": outputs,
    }
    transport.atomic_write_json(root / MANIFEST_PATH, manifest)
    return manifest


def sync_showcase(rows: list[ExperimentRow], root: Path = ROOT) -> dict[str, Any]:
    """Attach the two complete experiment outputs to case 14 without changing 20x3."""

    passed, errors = verify(rows, allow_contract_warnings=True, root=root)
    if not passed:
        raise ExperimentError(
            "Experiment verification failed before showcase sync: " + "; ".join(errors)
        )
    for row in rows:
        run = read_json(row.paths["run"])
        contract_check = run.get("contract_check") or {}
        warnings = contract_check.get("warnings")
        if contract_check.get("conforms") is True and warnings == []:
            continue
        if (
            row.model_id == "alibaba/wan-2.7"
            and contract_check.get("conforms") is False
            and warnings == [ALLOWED_WAN_AUDIO_WARNING]
        ):
            continue
        raise ExperimentError(
            f"Unsupported media contract warning for showcase sync: {row.model_id}"
        )

    showcase_path = root / SHOWCASE_MANIFEST_PATH
    showcase = read_json(showcase_path)
    articles = showcase.get("articles") if isinstance(showcase, dict) else None
    if (
        not isinstance(articles, list)
        or showcase.get("article_count") != 20
        or showcase.get("expected_outputs") != 60
        or not isinstance(showcase.get("outputs"), list)
        or len(showcase["outputs"]) != 60
    ):
        raise ExperimentError("Showcase manifest is not the canonical 20x3 dataset")
    case14 = next(
        (
            article
            for article in articles
            if isinstance(article, dict) and article.get("article_number") == ARTICLE_NUMBER
        ),
        None,
    )
    if not isinstance(case14, dict):
        raise ExperimentError("Showcase case 14 is missing")
    baseline = case14.get("outputs")
    if not isinstance(baseline, list) or len(baseline) != 3:
        raise ExperimentError("Showcase case 14 is not a canonical three-model row")
    reference = next(
        (output for output in baseline if output.get("model_id") == SOURCE_MODEL_ID),
        None,
    )
    if (
        not isinstance(reference, dict)
        or reference.get("positive_prompt") != rows[0].source.positive_prompt
    ):
        raise ExperimentError("Showcase Wan 2.2 reference prompt changed")

    extras = [manifest_output(row, root) for row in rows]
    if [output["model_id"] for output in extras] != list(TARGET_MODEL_IDS):
        raise ExperimentError("Experiment outputs are in the wrong model order")
    for row, output in zip(rows, extras, strict=True):
        if output["status"] not in COMPLETE_STATUSES or not row.paths["video"].is_file():
            raise ExperimentError(
                f"Experiment output is not ready for the showcase: {row.model_id}"
            )

    for article in articles:
        if not isinstance(article, dict):
            raise ExperimentError("Showcase article entry is invalid")
        if article is not case14:
            article.pop("comparison_outputs", None)
    case14["comparison_outputs"] = extras
    showcase["comparison_output_count"] = len(extras)
    transport.atomic_write_json(showcase_path, showcase)
    return showcase


def _run_row(row: ExperimentRow, args: argparse.Namespace, root: Path = ROOT) -> str:
    run = read_json(row.paths["run"])
    request = request_preview(row)
    fingerprint = transport.request_fingerprint(request, row.sample)
    if (
        run.get("status") in COMPLETE_STATUSES
        and row.paths["video"].is_file()
        and not args.force
    ):
        return f"{row.model_id}: already complete"
    if args.dry_run:
        run.update(
            {
                "status": "dry-run",
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "error": None,
            }
        )
        transport.atomic_write_json(row.paths["run"], run)
        return f"{row.model_id}: dry-run request validated"

    resume = run if run.get("status") in {"submitted", "running"} and not args.force else None
    run.update(
        {
            "status": "running" if resume else "prepared",
            "request": request,
            "request_sha256": fingerprint,
            "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
            "media": None,
            "contract_check": None,
            "error": None,
        }
    )
    if not resume:
        run.update(
            {
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
            }
        )
    transport.atomic_write_json(row.paths["run"], run)

    def on_submitted(job_id: str, session_hash: str | None) -> None:
        run.update(
            {
                "status": "submitted",
                "provider_job_id": job_id,
                "provider_session_hash": session_hash,
                "submitted_at": transport.utc_now(),
            }
        )
        transport.atomic_write_json(row.paths["run"], run)
        print(f"  {row.model_id}: submitted as {job_id}", flush=True)

    try:
        transport.eliza_generate(
            row.sample,
            row.prompt,
            row.paths["video"],
            args.eliza_base_url,
            args.timeout,
            args.poll_interval,
            resume,
            on_submitted,
        )
        media = transport.ffprobe_media(row.paths["video"])
        contract_check = transport.assess_contract(
            row.model_id,
            media,
            row.prompt["target_duration_seconds"],
        )
        status = "succeeded" if contract_check["conforms"] else "verification-failed"
        run.update(
            {
                "status": status,
                "completed_at": transport.utc_now(),
                "media": media,
                "contract_check": contract_check,
                "error": None if contract_check["conforms"] else "Media contract verification failed",
            }
        )
        transport.atomic_write_json(row.paths["run"], run)
        return (
            f"{row.model_id}: {status}; {media['width']}x{media['height']}, "
            f"{media['duration_seconds']}s, {media['bytes']} bytes"
        )
    except Exception as exc:
        error = transport.safe_error(exc)
        resumable = bool(run.get("provider_job_id")) and not any(
            marker in error.lower()
            for marker in ("failed with status", "cancelled", "canceled", "expired")
        )
        run.update(
            {
                "status": "submitted" if resumable else "failed",
                "completed_at": None if resumable else transport.utc_now(),
                "error": error,
            }
        )
        transport.atomic_write_json(row.paths["run"], run)
        raise ExperimentError(f"{row.model_id}: {error}") from exc


def run(rows: list[ExperimentRow], args: argparse.Namespace, root: Path = ROOT) -> int:
    if not args.dry_run and not args.allow_external_processing:
        raise ExperimentError(
            "Real generation requires --allow-external-processing because the image "
            "and prompt are sent to the two video providers"
        )
    failures = 0
    with ThreadPoolExecutor(max_workers=len(rows)) as executor:
        futures = {executor.submit(_run_row, row, args, root): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                print(future.result(), flush=True)
            except Exception as exc:
                failures += 1
                print(transport.safe_error(exc), file=sys.stderr, flush=True)
    write_manifest(rows, root)
    return failures


def verify(
    rows: list[ExperimentRow],
    *,
    allow_incomplete: bool = False,
    allow_contract_warnings: bool = False,
    root: Path = ROOT,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    prompt_hashes: set[str] = set()
    video_paths: set[str] = set()
    completed = 0
    for row in rows:
        label = row.model_id
        expected_prompt = prompt_artifact(row)
        if read_json(row.paths["prompt"]) != expected_prompt:
            errors.append(f"Prompt artifact changed: {label}")
        prompt_hashes.add(sha256_text(row.prompt["positive_prompt"]))
        request = request_preview(row)
        expected_fingerprint = transport.request_fingerprint(request, row.sample)
        run = read_json(row.paths["run"])
        status = run.get("status")
        if status not in COMPLETE_STATUSES:
            if not allow_incomplete:
                errors.append(f"Not complete ({status}): {label}")
            continue
        completed += 1
        if run.get("request") != request:
            errors.append(f"Recorded request changed: {label}")
        if run.get("request_sha256") != expected_fingerprint:
            errors.append(f"Recorded request fingerprint changed: {label}")
        if run.get("request_fingerprint_version") != transport.REQUEST_FINGERPRINT_VERSION:
            errors.append(f"Recorded request fingerprint version changed: {label}")
        if not row.paths["video"].is_file():
            errors.append(f"Generated MP4 is missing: {label}")
            continue
        video_path = relative(row.paths["video"], root)
        if video_path in video_paths:
            errors.append(f"Generated MP4 path is duplicated: {video_path}")
        video_paths.add(video_path)
        try:
            media = transport.ffprobe_media(row.paths["video"])
        except Exception as exc:
            errors.append(transport.safe_error(exc))
            continue
        recorded_media = run.get("media") or {}
        if (
            media.get("sha256") != recorded_media.get("sha256")
            or media.get("bytes") != recorded_media.get("bytes")
        ):
            errors.append(f"Recorded media digest/size changed: {label}")
        expected_contract = transport.assess_contract(
            row.model_id, media, row.prompt["target_duration_seconds"]
        )
        if run.get("contract_check") != expected_contract:
            errors.append(f"Recorded contract check changed: {label}")
        if not expected_contract["conforms"] and not allow_contract_warnings:
            errors.append(
                f"Media contract warnings for {label}: "
                + ", ".join(expected_contract["warnings"])
            )
    if prompt_hashes != {EXPECTED_PROMPT_SHA256}:
        errors.append("Target models do not share the exact Wan 2.2 prompt")
    if not allow_incomplete and completed != len(TARGET_MODEL_IDS):
        errors.append(f"Expected {len(TARGET_MODEL_IDS)} completed outputs, got {completed}")
    manifest = write_manifest(rows, root)
    if manifest.get("canonical_lite_artifact") is not False:
        errors.append("Experiment manifest incorrectly claims canonical Lite identity")
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="verify the source prompt and materialize two jobs")
    commands.add_parser(
        "sync-showcase",
        help="attach the two complete experiment outputs to showcase case 14",
    )

    run_parser = commands.add_parser("run", help="run or resume both target providers")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--allow-external-processing", action="store_true")
    run_parser.add_argument("--timeout", type=int, default=1800)
    run_parser.add_argument("--poll-interval", type=float, default=10.0)
    run_parser.add_argument(
        "--eliza-base-url",
        default=os.environ.get(
            "ELIZA_OPENROUTER_BASE_URL", transport.DEFAULT_ELIZA_BASE_URL
        ),
    )

    verify_parser = commands.add_parser("verify", help="verify prompt, requests, and MP4s")
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    verify_parser.add_argument("--allow-contract-warnings", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = materialize()
        if args.command == "plan":
            print(f"PASS: materialized {len(rows)} case-14 experiment jobs")
            return 0
        if args.command == "run":
            failures = run(rows, args)
            if failures:
                print(f"FAIL: {failures} generation(s) failed", file=sys.stderr)
                return 1
            print(f"PASS: processed {len(rows)} case-14 experiment jobs")
            return 0
        if args.command == "sync-showcase":
            sync_showcase(rows)
            print("PASS: attached two experiment outputs to showcase case 14")
            return 0
        if args.command == "verify":
            passed, errors = verify(
                rows,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print("PASS: case-14 cross-model prompt experiment is valid")
            return 0
        raise ExperimentError(f"Unknown command: {args.command}")
    except ExperimentError as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
