#!/usr/bin/env python3
"""Bind all 65 Tune MP4s to the Step 8 review manifest.

The merge is deliberately a separate, deterministic step after generation.
It validates the prompt-only Tune manifest, all 43 immutable Eliza I2V provider
attempts (41 reviewable MP4s plus two terminal no-output failures), the 22-output
deterministic-compositor manifest, the two explicit local compositor fallbacks,
and every local MP4 SHA/size binding.  It then attaches repository-raw URLs
pinned to one exact 40-hex media commit SHA.  No video is copied to GitHub Pages
or uploaded to S3.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import stat
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_tune_compositor as compositor_renderer  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TUNE_MANIFEST_REL = Path("clipmaker-lite-test/tune-manifest.json")
I2V_MANIFEST_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-tune-videos-20260811-v1/generation-manifest.json"
)
COMPOSITOR_MANIFEST_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-tune-compositor-20260811-v1/manifest.json"
)
COMPOSITOR_PLAN_REL = Path("clipmaker-lite-test/tune-compositor-plans.json")
FALLBACK_MANIFEST_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-tune-compositor-fallback-20260811-v1/manifest.json"
)
FALLBACK_PLAN_REL = Path("clipmaker-lite-test/tune-compositor-fallback-plans.json")

TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
PLANNING_BATCH_ID = "promopages-10060-tune-prompts-20260811-v4"
I2V_BATCH_ID = "promopages-10060-tune-videos-20260811-v1"
COMPOSITOR_BATCH_ID = "promopages-10060-tune-compositor-20260811-v1"
FALLBACK_BATCH_ID = "promopages-10060-tune-compositor-fallback-20260811-v1"
EXPECTED_CASES = 36
EXPECTED_TARGETS = 65
EXPECTED_I2V = 43
EXPECTED_ELIZA_I2V = 41
EXPECTED_COMPOSITOR = 22
EXPECTED_FALLBACK = 2
EXPECTED_I2V_BY_MODEL = {
    "alibaba/wan-2.2": 14,
    "alibaba/wan-2.7": 12,
    "google/veo-3.1-lite": 17,
}
EXPECTED_COMPOSITOR_BY_MODEL = {
    "alibaba/wan-2.2": 10,
    "alibaba/wan-2.7": 4,
    "google/veo-3.1-lite": 8,
}
EXPECTED_ELIZA_I2V_BY_MODEL = {
    "alibaba/wan-2.2": 14,
    "alibaba/wan-2.7": 12,
    "google/veo-3.1-lite": 15,
}
EXPECTED_FALLBACK_BY_MODEL = {"google/veo-3.1-lite": 2}
EXPECTED_FALLBACK_KEYS = {
    ("07#06", "google/veo-3.1-lite"),
    ("10#07", "google/veo-3.1-lite"),
}
METHOD_BY_MODE = {
    "i2v": "eliza-i2v",
    "deterministic-compositor": "deterministic-compositor",
}
RAW_OWNER = "UnidentifiedRaccoon"
RAW_REPOSITORY = "alice-live-images-test"
MAX_GITHUB_FILE_BYTES = 100 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_PRIMITIVES = {"camera_push", "glint", "highlight", "pan", "pulse"}
FALLBACK_PRIMITIVES = {"camera_push", "pan"}
COMPOSITOR_CHECKS = {
    "codec_h264",
    "pixel_format_yuv420p",
    "dimensions_exact",
    "fps_exact",
    "frames_exact",
    "duration_exact",
    "no_audio",
    "source_sha256_bound",
    "source_dimensions_bound",
}
GENERATED_SCOPE_KEYS = {
    "generated_video_count",
    "generated_video_delivery",
    "generated_video_method_counts",
    "media_commit_sha",
}


class TuneMediaOverlayError(RuntimeError):
    """A fail-closed Tune media merge error."""


@dataclass(frozen=True)
class TuneTarget:
    case: dict[str, Any]
    target: dict[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        return str(self.case["case_id"]), str(self.target["model_id"])

    @property
    def execution_mode(self) -> str:
        return str(self.target["tuned"]["execution_mode"])


@dataclass(frozen=True)
class ValidatedMedia:
    i2v: dict[tuple[str, str], dict[str, Any]]
    compositor: dict[tuple[str, str], dict[str, Any]]
    fallback: dict[tuple[str, str], dict[str, Any]]
    i2v_manifest_sha256: str
    compositor_manifest_sha256: str
    compositor_plan_sha256: str
    fallback_manifest_sha256: str
    fallback_plan_sha256: str


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise TuneMediaOverlayError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TuneMediaOverlayError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise TuneMediaOverlayError(f"Required file does not exist: {path}") from exc
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_exact_keys(value: Any, expected: set[str], *, label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise TuneMediaOverlayError(f"{label} keys changed")


def safe_relative(value: Any, *, label: str, suffix: str | None = None) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TuneMediaOverlayError(f"{label} must be a canonical relative path")
    path = Path(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or (suffix is not None and path.suffix.lower() != suffix)
    ):
        raise TuneMediaOverlayError(f"Unsafe {label}: {value!r}")
    return value


def confined_file(
    root: Path,
    relative_path: str,
    *,
    label: str,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
) -> Path:
    path = root / safe_relative(relative_path, label=label)
    try:
        file_stat = path.lstat()
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise TuneMediaOverlayError(f"{label} is missing or outside the workspace") from exc
    if not stat.S_ISREG(file_stat.st_mode) or path.is_symlink():
        raise TuneMediaOverlayError(f"{label} must be a regular non-symlink file")
    if expected_bytes is not None and file_stat.st_size != expected_bytes:
        raise TuneMediaOverlayError(f"{label} byte size mismatch")
    if expected_sha256 is not None and sha256_file(path) != expected_sha256:
        raise TuneMediaOverlayError(f"{label} SHA-256 mismatch")
    return path


def validate_commit_sha(value: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise TuneMediaOverlayError("media commit SHA must be exactly 40 lowercase hex characters")
    return value


def raw_url(commit_sha: str, repository_path: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{RAW_OWNER}/{RAW_REPOSITORY}/"
        f"{commit_sha}/{repository_path}"
    )


def _validate_common_media(
    media: Any,
    *,
    video_path: str,
    root: Path,
    label: str,
) -> dict[str, Any]:
    if not isinstance(media, dict):
        raise TuneMediaOverlayError(f"{label} media must be an object")
    sha256 = media.get("sha256")
    byte_count = media.get("bytes")
    if (
        not isinstance(sha256, str)
        or SHA256_RE.fullmatch(sha256) is None
        or not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or byte_count <= 0
        or byte_count >= MAX_GITHUB_FILE_BYTES
        or not isinstance(media.get("duration_seconds"), (int, float))
        or isinstance(media.get("duration_seconds"), bool)
        or media["duration_seconds"] <= 0
        or not isinstance(media.get("width"), int)
        or isinstance(media.get("width"), bool)
        or media["width"] <= 0
        or not isinstance(media.get("height"), int)
        or isinstance(media.get("height"), bool)
        or media["height"] <= 0
        or not isinstance(media.get("fps"), (int, float))
        or isinstance(media.get("fps"), bool)
        or media["fps"] <= 0
        or not isinstance(media.get("frames"), int)
        or isinstance(media.get("frames"), bool)
        or media["frames"] <= 0
    ):
        raise TuneMediaOverlayError(f"{label} common media contract is invalid")
    safe_relative(video_path, label=f"{label} video_path", suffix=".mp4")
    confined_file(
        root,
        video_path,
        label=f"{label} MP4",
        expected_sha256=sha256,
        expected_bytes=byte_count,
    )
    return media


def _prompt_base(manifest: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None]:
    """Return the prompt-only shape and any existing media commit/source hash."""

    base = copy.deepcopy(manifest)
    scope = base.get("scope")
    if not isinstance(scope, dict):
        raise TuneMediaOverlayError("Tune manifest scope is invalid")
    generated = scope.get("new_video_generation")
    if generated not in {True, False}:
        raise TuneMediaOverlayError("Tune new_video_generation must be boolean")
    existing_commit: str | None = None
    source_manifest_sha256: str | None = None
    media_generation = base.get("media_generation")
    if generated:
        if not isinstance(media_generation, dict):
            raise TuneMediaOverlayError("Generated Tune manifest has no media_generation binding")
        existing_commit = media_generation.get("media_commit_sha")
        source_manifest_sha256 = media_generation.get("source_tune_manifest_sha256")
        validate_commit_sha(existing_commit)
        if scope.get("media_commit_sha") != existing_commit:
            raise TuneMediaOverlayError("Tune scope/media_generation commit SHA mismatch")
        if not isinstance(source_manifest_sha256, str) or SHA256_RE.fullmatch(source_manifest_sha256) is None:
            raise TuneMediaOverlayError("Generated Tune source manifest SHA is invalid")
        base.pop("media_generation", None)
        scope["new_video_generation"] = False
        for key in GENERATED_SCOPE_KEYS:
            scope.pop(key, None)
    elif media_generation is not None:
        raise TuneMediaOverlayError("Prompt-only Tune manifest must not have media_generation")

    cases = base.get("cases")
    if not isinstance(cases, list):
        raise TuneMediaOverlayError("Tune manifest cases are invalid")
    for case in cases:
        targets = case.get("targets") if isinstance(case, dict) else None
        if not isinstance(targets, list):
            raise TuneMediaOverlayError("Tune case targets are invalid")
        for target in targets:
            tuned = target.get("tuned") if isinstance(target, dict) else None
            if not isinstance(tuned, dict):
                raise TuneMediaOverlayError("Tune target plan is invalid")
            video = tuned.pop("video", None)
            if not generated and video is not None:
                raise TuneMediaOverlayError("Prompt-only Tune target already contains video")
            if generated and not isinstance(video, dict):
                raise TuneMediaOverlayError("Generated Tune target has no video object")
    return base, existing_commit, source_manifest_sha256


def validate_tune_manifest(manifest: Any) -> tuple[dict[str, Any], dict[tuple[str, str], TuneTarget], str | None, str | None]:
    if not isinstance(manifest, dict):
        raise TuneMediaOverlayError("Tune manifest must be an object")
    base, existing_commit, source_manifest_sha256 = _prompt_base(manifest)
    scope = base.get("scope")
    cases = base.get("cases")
    summary = base.get("summary")
    if (
        base.get("schema_version") != 1
        or base.get("manifest_role") != "clipmaker-lite-tune-review"
        or base.get("ticket") != TICKET
        or base.get("batch_id") != PLANNING_BATCH_ID
        or base.get("agent_id") != AGENT_ID
        or base.get("contract_version") != "2.2.0"
        or not isinstance(scope, dict)
        or scope.get("case_count") != EXPECTED_CASES
        or scope.get("target_count") != EXPECTED_TARGETS
        or scope.get("new_video_generation") is not False
        or scope.get("new_s3_upload") is not False
        or scope.get("baseline_video_delivery") != "existing-yastatic"
        or not isinstance(cases, list)
        or len(cases) != EXPECTED_CASES
        or not isinstance(summary, dict)
        or summary.get("execution_mode_counts")
        != {"i2v": EXPECTED_I2V, "deterministic-compositor": EXPECTED_COMPOSITOR}
    ):
        raise TuneMediaOverlayError("Tune prompt manifest identity/scope changed")
    targets: dict[tuple[str, str], TuneTarget] = {}
    rows: set[int] = set()
    modes: Counter[str] = Counter()
    for case in cases:
        case_id = case.get("case_id") if isinstance(case, dict) else None
        planning = case.get("planning") if isinstance(case, dict) else None
        source = case.get("source") if isinstance(case, dict) else None
        case_targets = case.get("targets") if isinstance(case, dict) else None
        if (
            not isinstance(case_id, str)
            or not isinstance(planning, dict)
            or not isinstance(source, dict)
            or not isinstance(case_targets, list)
        ):
            raise TuneMediaOverlayError("Tune case identity is invalid")
        for target in case_targets:
            model_id = target.get("model_id") if isinstance(target, dict) else None
            sheet_row = target.get("sheet_row") if isinstance(target, dict) else None
            tuned = target.get("tuned") if isinstance(target, dict) else None
            key = (case_id, str(model_id))
            mode = tuned.get("execution_mode") if isinstance(tuned, dict) else None
            if (
                not isinstance(model_id, str)
                or not isinstance(sheet_row, int)
                or isinstance(sheet_row, bool)
                or sheet_row in rows
                or not isinstance(tuned, dict)
                or mode not in METHOD_BY_MODE
                or key in targets
            ):
                raise TuneMediaOverlayError(f"Tune target identity is invalid: {key}")
            rows.add(sheet_row)
            modes[mode] += 1
            targets[key] = TuneTarget(case=case, target=target)
    if len(targets) != EXPECTED_TARGETS or modes != Counter(
        {"i2v": EXPECTED_I2V, "deterministic-compositor": EXPECTED_COMPOSITOR}
    ):
        raise TuneMediaOverlayError("Tune target execution matrix changed")
    return base, targets, existing_commit, source_manifest_sha256


def _validate_i2v_contract(
    output: dict[str, Any],
    *,
    target: TuneTarget,
    root: Path,
) -> dict[str, Any]:
    label = f"I2V {target.key[0]} / {target.key[1]}"
    status_value = output.get("status")
    video_path = output.get("video_path")
    media = _validate_common_media(
        output.get("media"),
        video_path=safe_relative(video_path, label=f"{label} video_path", suffix=".mp4"),
        root=root,
        label=label,
    )
    contract_check = output.get("contract_check")
    requested = contract_check.get("requested") if isinstance(contract_check, dict) else None
    if (
        output.get("execution_mode") != "i2v"
        or status_value not in {"succeeded", "verification-failed"}
        or not video_path.startswith(
            f"clipmaker-lite-test/runs/{I2V_BATCH_ID}/videos/"
        )
        or not isinstance(media.get("container"), str)
        or not media["container"].strip()
        or not isinstance(media.get("codec"), str)
        or not media["codec"].strip()
        or not isinstance(media.get("has_audio"), bool)
        or not isinstance(contract_check, dict)
        or not isinstance(requested, dict)
        or not isinstance(contract_check.get("checks"), dict)
        or not contract_check["checks"]
        or any(not isinstance(value, bool) for value in contract_check["checks"].values())
        or not isinstance(contract_check.get("warnings"), list)
        or any(
            not isinstance(value, str) or not value.strip()
            for value in contract_check["warnings"]
        )
    ):
        raise TuneMediaOverlayError(f"{label} method-specific schema is invalid")
    if status_value == "succeeded":
        if (
            contract_check.get("conforms") is not True
            or not all(contract_check["checks"].values())
            or media.get("has_audio") is not False
        ):
            raise TuneMediaOverlayError(f"{label} succeeded contract is invalid")
    elif (
        contract_check.get("conforms") is not False
        or all(contract_check["checks"].values())
        or not contract_check["warnings"]
    ):
        raise TuneMediaOverlayError(f"{label} verification-failed contract is invalid")
    if (
        status_value == "verification-failed"
        and media.get("has_audio") is True
        and (
            requested.get("generate_audio") is not False
            or contract_check["checks"].get("audio") is not False
            or not any(
                "has_audio=True" in warning
                for warning in contract_check["warnings"]
            )
        )
    ):
        raise TuneMediaOverlayError(
            f"{label} audio-warning provenance is invalid"
        )
    return {
        "status": status_value,
        "method": "eliza-i2v",
        "repository_video_path": video_path,
        "sha256": media["sha256"],
        "bytes": media["bytes"],
        "media": media,
        "contract_check": contract_check,
        "generation": {
            "batch_id": I2V_BATCH_ID,
            "provider_run_id": output.get("provider_run_id"),
            "prompt_path": output.get("prompt_path"),
            "run_path": output.get("run_path"),
        },
    }


def _validate_provider_failure(
    output: dict[str, Any],
    *,
    target: TuneTarget,
    root: Path,
) -> dict[str, Any]:
    """Freeze one terminal no-output provider attempt for fallback provenance."""

    label = f"I2V provider failure {target.key[0]} / {target.key[1]}"
    run_path = safe_relative(
        output.get("run_path"), label=f"{label} run_path", suffix=".json"
    )
    prompt_path = safe_relative(
        output.get("prompt_path"), label=f"{label} prompt_path", suffix=".json"
    )
    video_path = safe_relative(
        output.get("video_path"), label=f"{label} video_path", suffix=".mp4"
    )
    expected_prefix = f"clipmaker-lite-test/runs/{I2V_BATCH_ID}/videos/"
    if (
        output.get("execution_mode") != "i2v"
        or output.get("status") != "provider-failed"
        or output.get("media") is not None
        or output.get("contract_check") is not None
        or not isinstance(output.get("provider_run_id"), str)
        or not output["provider_run_id"].strip()
        or not isinstance(output.get("error"), str)
        or not output["error"].strip()
        or not run_path.startswith(expected_prefix)
        or not prompt_path.startswith(expected_prefix)
        or not video_path.startswith(expected_prefix)
        or (root / video_path).exists()
    ):
        raise TuneMediaOverlayError(f"{label} is not a terminal no-output attempt")

    run_file = confined_file(root, run_path, label=f"{label} run receipt")
    prompt_file = confined_file(root, prompt_path, label=f"{label} prompt receipt")
    run_sha256 = sha256_file(run_file)
    prompt_sha256 = sha256_file(prompt_file)
    run = read_json(run_file)
    prompt = read_json(prompt_file)
    provider_job_id = run.get("provider_job_id") if isinstance(run, dict) else None
    request = run.get("request") if isinstance(run, dict) else None
    if (
        not isinstance(run, dict)
        or run.get("manifest_role") != "clipmaker-lite-tune-video-run"
        or run.get("batch_id") != I2V_BATCH_ID
        or run.get("agent_id") != AGENT_ID
        or run.get("provider_run_id") != output.get("provider_run_id")
        or run.get("case_id") != target.key[0]
        or run.get("model_id") != target.key[1]
        or run.get("execution_mode") != "i2v"
        or run.get("status") != "provider-failed"
        or run.get("prompt_path") != prompt_path
        or run.get("output_path") != video_path
        or run.get("provider_may_be_active") is not False
        or run.get("automatic_paid_retry") is not False
        or run.get("media") is not None
        or run.get("contract_check") is not None
        or run.get("error") != output.get("error")
        or not isinstance(run.get("completed_at"), str)
        or not isinstance(provider_job_id, str)
        or not provider_job_id.strip()
        or not isinstance(request, dict)
        or request.get("model") != target.key[1]
        or request.get("duration")
        != target.target.get("tuned", {}).get("runtime", {}).get("duration_seconds")
        or request.get("generate_audio") is not False
    ):
        raise TuneMediaOverlayError(f"{label} run receipt is not a frozen terminal failure")
    prompt_payload = prompt.get("prompt") if isinstance(prompt, dict) else None
    if (
        not isinstance(prompt, dict)
        or prompt.get("manifest_role") != "clipmaker-lite-tune-video-prompt"
        or prompt.get("batch_id") != I2V_BATCH_ID
        or prompt.get("agent_id") != AGENT_ID
        or prompt.get("provider_run_id") != output.get("provider_run_id")
        or prompt.get("case_id") != target.key[0]
        or prompt.get("model_id") != target.key[1]
        or prompt.get("execution_mode") != "i2v"
        or not isinstance(prompt_payload, dict)
        or prompt_payload.get("positive")
        != target.target.get("tuned", {}).get("positive_prompt")
        or prompt_payload.get("negative")
        != target.target.get("tuned", {}).get("negative_prompt")
        or prompt_payload.get("rewritten") is not False
    ):
        raise TuneMediaOverlayError(f"{label} prompt receipt changed")
    return {
        "provider_run_id": output["provider_run_id"],
        "run_path": run_path,
        "run_sha256": run_sha256,
        "prompt_path": prompt_path,
        "prompt_sha256": prompt_sha256,
        "status": "provider-failed",
        "provider_job_id": provider_job_id,
        "terminal_error": output["error"],
        "canonical_provider_video_path": video_path,
    }


def validate_i2v_manifest(
    document: Any,
    *,
    manifest_path: Path,
    prompt_manifest_sha256: str,
    targets: dict[tuple[str, str], TuneTarget],
    root: Path,
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    str,
]:
    if not isinstance(document, dict):
        raise TuneMediaOverlayError("I2V generation manifest must be an object")
    scope = document.get("scope")
    scheduling = document.get("scheduling")
    outputs = document.get("outputs")
    exclusions = document.get("compositor_exclusions")
    if (
        document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-video-generation"
        or document.get("ticket") != TICKET
        or document.get("batch_id") != I2V_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(scope, dict)
        or scope.get("planning_batch_id") != PLANNING_BATCH_ID
        or scope.get("tune_manifest_path") != TUNE_MANIFEST_REL.as_posix()
        or scope.get("tune_manifest_sha256") != prompt_manifest_sha256
        or scope.get("expected_i2v_outputs") != EXPECTED_I2V
        or scope.get("compositor_provider_outputs") != 0
        or scope.get("s3_upload") is not False
        or scope.get("delivery") != "repository-files"
        or not isinstance(scheduling, dict)
        or scheduling.get("route_capacities")
        != {
            "alibaba/wan-2.2": 1,
            "alibaba/wan-2.7": 3,
            "google/veo-3.1-lite": 3,
        }
        or scheduling.get("one_paid_submission_per_provider_run_id") is not True
        or scheduling.get("automatic_paid_retry") is not False
        or not isinstance(outputs, list)
        or len(outputs) != EXPECTED_I2V
        or not isinstance(exclusions, list)
        or len(exclusions) != EXPECTED_COMPOSITOR
    ):
        raise TuneMediaOverlayError("I2V generation manifest identity/scope is invalid")
    expected_keys = {key for key, target in targets.items() if target.execution_mode == "i2v"}
    expected_exclusions = {
        key for key, target in targets.items() if target.execution_mode == "deterministic-compositor"
    }
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    failures: dict[tuple[str, str], dict[str, Any]] = {}
    status_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    paths: set[str] = set()
    for output in outputs:
        if not isinstance(output, dict):
            raise TuneMediaOverlayError("I2V output must be an object")
        key = (str(output.get("case_id")), str(output.get("model_id")))
        target = targets.get(key)
        if target is None or target.execution_mode != "i2v" or key in by_key:
            raise TuneMediaOverlayError(f"Unexpected/duplicate I2V output: {key}")
        if (
            output.get("sheet_row") != target.target.get("sheet_row")
            or output.get("article_slug") != target.case.get("article_slug")
            or output.get("image_id") != target.case.get("source", {}).get("image_id")
        ):
            raise TuneMediaOverlayError(f"I2V target binding mismatch: {key}")
        status_value = output.get("status")
        if status_value == "provider-failed":
            if key not in EXPECTED_FALLBACK_KEYS:
                raise TuneMediaOverlayError(f"Unexpected I2V provider failure: {key}")
            failure = _validate_provider_failure(
                output,
                target=target,
                root=root,
            )
            failures[key] = failure
        else:
            video = _validate_i2v_contract(output, target=target, root=root)
            if video["repository_video_path"] in paths:
                raise TuneMediaOverlayError("I2V repository video paths must be unique")
            paths.add(video["repository_video_path"])
            by_key[key] = video
        status_counts[str(status_value)] += 1
        model_counts[key[1]] += 1
    exclusion_keys = {
        (str(value.get("case_id")), str(value.get("model_id")))
        for value in exclusions
        if isinstance(value, dict)
        and value.get("execution_mode") == "deterministic-compositor"
        and value.get("status") == "abstained"
        and value.get("provider_artifact") is None
    }
    if (
        set(by_key) | set(failures) != expected_keys
        or set(by_key) & set(failures)
        or set(failures) != EXPECTED_FALLBACK_KEYS
        or len(by_key) != EXPECTED_ELIZA_I2V
        or exclusion_keys != expected_exclusions
        or model_counts != Counter(EXPECTED_I2V_BY_MODEL)
        or Counter(key[1] for key in by_key) != Counter(EXPECTED_ELIZA_I2V_BY_MODEL)
        or dict(sorted(status_counts.items())) != document.get("summary")
    ):
        raise TuneMediaOverlayError("I2V output/exclusion matrix is incomplete or inconsistent")
    return by_key, failures, sha256_file(manifest_path)


def _validate_compositor_plan_document(
    plan: Any,
    *,
    targets: dict[tuple[str, str], TuneTarget],
) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(plan, dict):
        raise TuneMediaOverlayError("Compositor plan document must be an object")
    rows = plan.get("targets")
    contract = plan.get("render_contract")
    if (
        plan.get("schema_version") != 1
        or plan.get("manifest_role") != "clipmaker-lite-tune-compositor-plans"
        or plan.get("batch_id") != COMPOSITOR_BATCH_ID
        or plan.get("agent_id") != AGENT_ID
        or not isinstance(contract, dict)
        or contract.get("video_codec") != "h264"
        or contract.get("pixel_format") != "yuv420p"
        or contract.get("audio") is not False
        or contract.get("network") is not False
        or contract.get("source_mutation") is not False
        or set(contract.get("allowlisted_primitives", [])) != ALLOWED_PRIMITIVES
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_COMPOSITOR
    ):
        raise TuneMediaOverlayError("Compositor plan identity/render contract is invalid")
    expected_keys = {
        key for key, target in targets.items() if target.execution_mode == "deterministic-compositor"
    }
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TuneMediaOverlayError("Compositor plan target must be an object")
        key = (str(row.get("case_id")), str(row.get("model_id")))
        target = targets.get(key)
        primitive = (row.get("plan") or {}).get("primitive")
        source = target.case.get("source") if target else None
        planning = target.case.get("planning") if target else None
        tuned = target.target.get("tuned") if target else None
        if (
            target is None
            or target.execution_mode != "deterministic-compositor"
            or key in by_key
            or primitive not in ALLOWED_PRIMITIVES
            or row.get("source")
            != {
                key_name: source.get(key_name)
                for key_name in ("path", "sha256", "width", "height")
            }
            or row.get("planning")
            != {
                "run_id": planning.get("run_id"),
                "result_path": planning.get("result_path"),
            }
            or row.get("duration_seconds") != tuned.get("runtime", {}).get("duration_seconds")
            or row.get("scene_plan_sha256") != sha256_text(str(tuned.get("scene_plan")))
        ):
            raise TuneMediaOverlayError(f"Compositor plan target binding is invalid: {key}")
        by_key[key] = row
    if set(by_key) != expected_keys:
        raise TuneMediaOverlayError("Compositor plan matrix is incomplete")
    return by_key


def _validate_compositor_contract(
    output: dict[str, Any],
    *,
    target: TuneTarget,
    plan_row: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    label = f"Compositor {target.key[0]} / {target.key[1]}"
    video_path = safe_relative(
        output.get("video_path"),
        label=f"{label} video_path",
        suffix=".mp4",
    )
    media = _validate_common_media(
        output.get("media"),
        video_path=video_path,
        root=root,
        label=label,
    )
    checks = output.get("contract_check")
    planning = output.get("planning")
    source = output.get("source")
    if (
        output.get("execution_mode") != "deterministic-compositor"
        or output.get("status") != "succeeded"
        or not video_path.startswith(
            f"clipmaker-lite-test/runs/{COMPOSITOR_BATCH_ID}/videos/"
        )
        or media.get("video_codec") != "h264"
        or media.get("pixel_format") != "yuv420p"
        or media.get("audio_streams") != 0
        or not isinstance(checks, dict)
        or set(checks) != COMPOSITOR_CHECKS
        or any(checks.get(key) is not True for key in COMPOSITOR_CHECKS)
        or output.get("plan") != plan_row.get("plan")
        or video_path != plan_row.get("output_path")
        or not isinstance(planning, dict)
        or planning.get("run_id") != target.case.get("planning", {}).get("run_id")
        or planning.get("result_path") != target.case.get("planning", {}).get("result_path")
        or planning.get("scene_plan_sha256")
        != sha256_text(str(target.target.get("tuned", {}).get("scene_plan")))
        or not isinstance(source, dict)
        or source.get("path") != target.case.get("source", {}).get("path")
        or source.get("sha256") != target.case.get("source", {}).get("sha256")
        or source.get("mutated") is not False
    ):
        raise TuneMediaOverlayError(f"{label} method-specific schema is invalid")
    return {
        "status": "succeeded",
        "method": "deterministic-compositor",
        "repository_video_path": video_path,
        "sha256": media["sha256"],
        "bytes": media["bytes"],
        "media": media,
        "contract_check": checks,
        "compositor": {
            "batch_id": COMPOSITOR_BATCH_ID,
            "planning": planning,
            "primitive": output["plan"]["primitive"],
            "plan": output["plan"],
        },
    }


def validate_compositor_manifest(
    document: Any,
    *,
    manifest_path: Path,
    plan_path: Path,
    targets: dict[tuple[str, str], TuneTarget],
    root: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], str, str]:
    if not isinstance(document, dict):
        raise TuneMediaOverlayError("Compositor generation manifest must be an object")
    producer = document.get("producer")
    input_plan = document.get("input_plan")
    render_contract = document.get("render_contract")
    scope = document.get("scope")
    outputs = document.get("outputs")
    plan_sha256 = sha256_file(plan_path)
    if (
        document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-compositor-generation"
        or document.get("batch_id") != COMPOSITOR_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(producer, dict)
        or producer.get("script_path") != "scripts/clipmaker_lite_tune_compositor.py"
        or producer.get("script_sha256")
        != sha256_file(root / producer["script_path"])
        or not isinstance(input_plan, dict)
        or input_plan.get("path") != COMPOSITOR_PLAN_REL.as_posix()
        or input_plan.get("sha256") != plan_sha256
        or not isinstance(scope, dict)
        or scope.get("targets") != EXPECTED_COMPOSITOR
        or scope.get("provider_calls") != 0
        or scope.get("network") is not False
        or scope.get("s3_upload") is not False
        or scope.get("tune_manifest_mutation") is not False
        or not isinstance(outputs, list)
        or len(outputs) != EXPECTED_COMPOSITOR
        or document.get("summary") != {"succeeded": EXPECTED_COMPOSITOR}
        or not isinstance(render_contract, dict)
    ):
        raise TuneMediaOverlayError("Compositor generation manifest identity/scope is invalid")
    plan = read_json(plan_path)
    plan_rows = _validate_compositor_plan_document(plan, targets=targets)
    if render_contract != plan.get("render_contract"):
        raise TuneMediaOverlayError("Compositor generation/plan render contracts differ")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    model_counts: Counter[str] = Counter()
    paths: set[str] = set()
    for output in outputs:
        if not isinstance(output, dict):
            raise TuneMediaOverlayError("Compositor output must be an object")
        key = (str(output.get("case_id")), str(output.get("model_id")))
        target = targets.get(key)
        plan_row = plan_rows.get(key)
        if (
            target is None
            or target.execution_mode != "deterministic-compositor"
            or plan_row is None
            or key in by_key
        ):
            raise TuneMediaOverlayError(f"Unexpected/duplicate compositor output: {key}")
        video = _validate_compositor_contract(
            output,
            target=target,
            plan_row=plan_row,
            root=root,
        )
        if video["repository_video_path"] in paths:
            raise TuneMediaOverlayError("Compositor repository video paths must be unique")
        paths.add(video["repository_video_path"])
        by_key[key] = video
        model_counts[key[1]] += 1
    if (
        set(by_key) != set(plan_rows)
        or model_counts != Counter(EXPECTED_COMPOSITOR_BY_MODEL)
        or document.get("model_summary") != dict(sorted(EXPECTED_COMPOSITOR_BY_MODEL.items()))
        or document.get("bytes_total") != sum(video["bytes"] for video in by_key.values())
    ):
        raise TuneMediaOverlayError("Compositor output matrix/accounting is inconsistent")
    return by_key, sha256_file(manifest_path), plan_sha256


def _fallback_projection(
    targets: dict[tuple[str, str], TuneTarget],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(EXPECTED_FALLBACK_KEYS):
        target = targets.get(key)
        if target is None:
            raise TuneMediaOverlayError(f"Missing frozen fallback target: {key}")
        planning = target.case.get("planning") or {}
        provenance = planning.get("provenance") or {}
        tuned = target.target.get("tuned") or {}
        rows.append(
            {
                "case_id": key[0],
                "model_id": key[1],
                "source": target.case.get("source"),
                "planning_run_id": planning.get("run_id"),
                "planning_result_path": planning.get("result_path"),
                "planning_provenance": {
                    "verified": provenance.get("verified"),
                    "agent_id": provenance.get("agent_id"),
                    "result_path": provenance.get("result_path"),
                    "source_image_sha256": provenance.get("source_image_sha256"),
                    "models": provenance.get("models"),
                },
                "execution_mode": tuned.get("execution_mode"),
                "scene_plan": tuned.get("scene_plan"),
                "positive_prompt": tuned.get("positive_prompt"),
                "negative_prompt": tuned.get("negative_prompt"),
                "runtime": tuned.get("runtime"),
            }
        )
    return rows


def _fallback_render_contract() -> dict[str, Any]:
    return {
        "fps": 30,
        "video_codec": "h264",
        "pixel_format": "yuv420p",
        "duration_seconds": 4,
        "frames": 120,
        "audio": False,
        "network": False,
        "source_mutation": False,
        "allowlisted_primitives": ["camera_push", "pan"],
        "maximum_output": {"width": 1920, "height": 1080, "upscale": False},
    }


def _plan_provider_failure(failure: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in failure.items()
        if key != "canonical_provider_video_path"
    }


def _validate_fallback_plan_document(
    plan: Any,
    *,
    targets: dict[tuple[str, str], TuneTarget],
    provider_failures: dict[tuple[str, str], dict[str, Any]],
    i2v_manifest_sha256: str,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(plan, dict):
        raise TuneMediaOverlayError("Fallback plan document must be an object")
    require_exact_keys(
        plan,
        {
            "schema_version",
            "manifest_role",
            "batch_id",
            "agent_id",
            "method",
            "source_manifest",
            "provider_generation",
            "render_contract",
            "targets",
        },
        label="fallback plan document",
    )
    source_manifest = plan.get("source_manifest")
    provider_generation = plan.get("provider_generation")
    rows = plan.get("targets")
    if not isinstance(source_manifest, dict) or not isinstance(provider_generation, dict):
        raise TuneMediaOverlayError("Fallback plan input bindings are invalid")
    require_exact_keys(
        source_manifest,
        {"path", "batch_id", "selection_sha256"},
        label="fallback source_manifest",
    )
    require_exact_keys(
        provider_generation,
        {"path", "batch_id", "sha256"},
        label="fallback provider_generation",
    )
    projection = _fallback_projection(targets)
    if (
        plan.get("schema_version") != 1
        or plan.get("manifest_role")
        != "clipmaker-lite-tune-compositor-fallback-plans"
        or plan.get("batch_id") != FALLBACK_BATCH_ID
        or plan.get("agent_id") != AGENT_ID
        or plan.get("method") != "deterministic-compositor-fallback"
        or source_manifest
        != {
            "path": TUNE_MANIFEST_REL.as_posix(),
            "batch_id": PLANNING_BATCH_ID,
            "selection_sha256": canonical_json_sha256(projection),
        }
        or provider_generation
        != {
            "path": I2V_MANIFEST_REL.as_posix(),
            "batch_id": I2V_BATCH_ID,
            "sha256": i2v_manifest_sha256,
        }
        or plan.get("render_contract") != _fallback_render_contract()
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_FALLBACK
    ):
        raise TuneMediaOverlayError("Fallback plan identity/input contract changed")

    row_keys = {
        "case_id",
        "model_id",
        "original_execution_mode",
        "method",
        "duration_seconds",
        "source",
        "planning",
        "scene_plan_sha256",
        "provider_failure",
        "output_path",
        "plan",
    }
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, row in enumerate(rows):
        require_exact_keys(row, row_keys, label=f"fallback target {index}")
        key = (str(row.get("case_id")), str(row.get("model_id")))
        target = targets.get(key)
        failure = provider_failures.get(key)
        tuned = target.target.get("tuned") if target else None
        source = target.case.get("source") if target else None
        planning = target.case.get("planning") if target else None
        plan_value = row.get("plan")
        try:
            validated_plan = compositor_renderer.validate_plan(
                plan_value,
                duration=4,
                label=f"fallback target {key} plan",
            )
        except compositor_renderer.TuneCompositorError as exc:
            raise TuneMediaOverlayError(str(exc)) from exc
        output_path = safe_relative(
            row.get("output_path"),
            label=f"fallback target {key} output_path",
            suffix=".mp4",
        )
        if (
            target is None
            or target.execution_mode != "i2v"
            or failure is None
            or key in by_key
            or key not in EXPECTED_FALLBACK_KEYS
            or row.get("original_execution_mode") != "i2v"
            or row.get("method") != "deterministic-compositor-fallback"
            or row.get("duration_seconds") != 4
            or not isinstance(tuned, dict)
            or tuned.get("runtime", {}).get("duration_seconds") != 4
            or tuned.get("negative_prompt") is not None
            or not isinstance(tuned.get("positive_prompt"), str)
            or row.get("source")
            != {
                name: source.get(name)
                for name in ("path", "sha256", "width", "height")
            }
            or row.get("planning")
            != {
                "run_id": planning.get("run_id"),
                "result_path": planning.get("result_path"),
            }
            or row.get("scene_plan_sha256") != sha256_text(str(tuned.get("scene_plan")))
            or row.get("provider_failure") != _plan_provider_failure(failure)
            or not output_path.startswith(
                f"clipmaker-lite-test/runs/{FALLBACK_BATCH_ID}/videos/"
            )
            or validated_plan.get("primitive") not in FALLBACK_PRIMITIVES
        ):
            raise TuneMediaOverlayError(f"Fallback plan target binding is invalid: {key}")
        by_key[key] = row
    if set(by_key) != EXPECTED_FALLBACK_KEYS:
        raise TuneMediaOverlayError("Fallback plan target matrix is incomplete")
    return by_key


def _validate_fallback_contract(
    output: dict[str, Any],
    *,
    target: TuneTarget,
    plan_row: dict[str, Any],
    provider_failure: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    label = f"Fallback {target.key[0]} / {target.key[1]}"
    video_path = safe_relative(
        output.get("video_path"), label=f"{label} video_path", suffix=".mp4"
    )
    media = _validate_common_media(
        output.get("media"),
        video_path=video_path,
        root=root,
        label=label,
    )
    checks = output.get("contract_check")
    planning = output.get("planning")
    source = output.get("source")
    plan_failure = _plan_provider_failure(provider_failure)
    if (
        output.get("execution_mode") != "i2v"
        or output.get("original_execution_mode") != "i2v"
        or output.get("method") != "deterministic-compositor-fallback"
        or output.get("status") != "succeeded"
        or output.get("fallback_reason") != "terminal-provider-failure"
        or output.get("provider_failure") != plan_failure
        or output.get("canonical_provider_video_path")
        != provider_failure["canonical_provider_video_path"]
        or video_path != plan_row.get("output_path")
        or media.get("video_codec") != "h264"
        or media.get("pixel_format") != "yuv420p"
        or media.get("audio_streams") != 0
        or not isinstance(checks, dict)
        or set(checks) != COMPOSITOR_CHECKS
        or any(checks.get(key) is not True for key in COMPOSITOR_CHECKS)
        or output.get("plan") != plan_row.get("plan")
        or planning
        != {
            **plan_row["planning"],
            "scene_plan_sha256": plan_row["scene_plan_sha256"],
        }
        or source != {**plan_row["source"], "mutated": False}
    ):
        raise TuneMediaOverlayError(f"{label} method-specific schema is invalid")
    return {
        "status": "succeeded",
        "method": "deterministic-compositor-fallback",
        "prompt_evaluated": False,
        "provider_attempt": {
            "status": "provider-failed",
            "prompt_evaluated": False,
            "run_path": provider_failure["run_path"],
            "run_sha256": provider_failure["run_sha256"],
            "provider_job_id": provider_failure["provider_job_id"],
            "error": provider_failure["terminal_error"],
        },
        "repository_video_path": video_path,
        "sha256": media["sha256"],
        "bytes": media["bytes"],
        "media": media,
        "contract_check": checks,
        "compositor_fallback": {
            "batch_id": FALLBACK_BATCH_ID,
            "fallback_reason": "terminal-provider-failure",
            "original_execution_mode": "i2v",
            "provider_failure": plan_failure,
            "planning": planning,
            "primitive": output["plan"]["primitive"],
            "plan": output["plan"],
        },
    }


def validate_fallback_manifest(
    document: Any,
    *,
    manifest_path: Path,
    plan_path: Path,
    targets: dict[tuple[str, str], TuneTarget],
    provider_failures: dict[tuple[str, str], dict[str, Any]],
    i2v_manifest_sha256: str,
    root: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], str, str]:
    if not isinstance(document, dict):
        raise TuneMediaOverlayError("Fallback generation manifest must be an object")
    plan_sha256 = sha256_file(plan_path)
    plan = read_json(plan_path)
    plan_rows = _validate_fallback_plan_document(
        plan,
        targets=targets,
        provider_failures=provider_failures,
        i2v_manifest_sha256=i2v_manifest_sha256,
    )
    producer = document.get("producer")
    input_plan = document.get("input_plan")
    scope = document.get("scope")
    outputs = document.get("outputs")
    provider_generation = document.get("provider_generation")
    if not isinstance(producer, dict):
        raise TuneMediaOverlayError("Fallback producer binding is invalid")
    require_exact_keys(
        producer,
        {"script_path", "script_sha256", "renderer_path", "renderer_sha256"},
        label="fallback producer",
    )
    script_path = safe_relative(
        producer.get("script_path"), label="fallback producer script"
    )
    renderer_path = safe_relative(
        producer.get("renderer_path"), label="fallback renderer script"
    )
    if (
        document.get("schema_version") != 1
        or document.get("manifest_role")
        != "clipmaker-lite-tune-compositor-fallback-generation"
        or document.get("batch_id") != FALLBACK_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or document.get("method") != "deterministic-compositor-fallback"
        or not isinstance(document.get("generated_at"), str)
        or not document["generated_at"].strip()
        or script_path != "scripts/clipmaker_lite_tune_compositor_fallback.py"
        or producer.get("script_sha256") != sha256_file(root / script_path)
        or renderer_path != "scripts/clipmaker_lite_tune_compositor.py"
        or producer.get("renderer_sha256") != sha256_file(root / renderer_path)
        or input_plan
        != {"path": FALLBACK_PLAN_REL.as_posix(), "sha256": plan_sha256}
        or provider_generation != plan.get("provider_generation")
        or provider_generation.get("sha256") != i2v_manifest_sha256
        or document.get("render_contract") != _fallback_render_contract()
        or scope
        != {
            "targets": EXPECTED_FALLBACK,
            "original_execution_mode": "i2v",
            "provider_calls": 0,
            "network": False,
            "s3_upload": False,
            "tune_manifest_mutation": False,
            "canonical_compositor_manifest_mutation": False,
        }
        or document.get("summary") != {"succeeded": EXPECTED_FALLBACK}
        or not isinstance(outputs, list)
        or len(outputs) != EXPECTED_FALLBACK
    ):
        raise TuneMediaOverlayError("Fallback generation manifest identity/scope is invalid")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    model_counts: Counter[str] = Counter()
    paths: set[str] = set()
    for output in outputs:
        if not isinstance(output, dict):
            raise TuneMediaOverlayError("Fallback output must be an object")
        key = (str(output.get("case_id")), str(output.get("model_id")))
        target = targets.get(key)
        plan_row = plan_rows.get(key)
        provider_failure = provider_failures.get(key)
        if (
            target is None
            or plan_row is None
            or provider_failure is None
            or key in by_key
        ):
            raise TuneMediaOverlayError(f"Unexpected/duplicate fallback output: {key}")
        video = _validate_fallback_contract(
            output,
            target=target,
            plan_row=plan_row,
            provider_failure=provider_failure,
            root=root,
        )
        if video["repository_video_path"] in paths:
            raise TuneMediaOverlayError("Fallback repository video paths must be unique")
        paths.add(video["repository_video_path"])
        by_key[key] = video
        model_counts[key[1]] += 1
    if (
        set(by_key) != EXPECTED_FALLBACK_KEYS
        or model_counts != Counter(EXPECTED_FALLBACK_BY_MODEL)
        or document.get("bytes_total") != sum(video["bytes"] for video in by_key.values())
    ):
        raise TuneMediaOverlayError("Fallback output matrix/accounting is inconsistent")
    return by_key, sha256_file(manifest_path), plan_sha256


def validate_media_inputs(
    *,
    root: Path,
    prompt_manifest_sha256: str,
    targets: dict[tuple[str, str], TuneTarget],
    i2v_manifest_rel: Path = I2V_MANIFEST_REL,
    compositor_manifest_rel: Path = COMPOSITOR_MANIFEST_REL,
    compositor_plan_rel: Path = COMPOSITOR_PLAN_REL,
    fallback_manifest_rel: Path = FALLBACK_MANIFEST_REL,
    fallback_plan_rel: Path = FALLBACK_PLAN_REL,
) -> ValidatedMedia:
    i2v_path = root / safe_relative(i2v_manifest_rel.as_posix(), label="I2V manifest")
    compositor_path = root / safe_relative(
        compositor_manifest_rel.as_posix(), label="compositor manifest"
    )
    plan_path = root / safe_relative(compositor_plan_rel.as_posix(), label="compositor plan")
    fallback_path = root / safe_relative(
        fallback_manifest_rel.as_posix(), label="fallback manifest"
    )
    fallback_plan_path = root / safe_relative(
        fallback_plan_rel.as_posix(), label="fallback plan"
    )
    i2v, provider_failures, i2v_sha = validate_i2v_manifest(
        read_json(i2v_path),
        manifest_path=i2v_path,
        prompt_manifest_sha256=prompt_manifest_sha256,
        targets=targets,
        root=root,
    )
    compositor, compositor_sha, plan_sha = validate_compositor_manifest(
        read_json(compositor_path),
        manifest_path=compositor_path,
        plan_path=plan_path,
        targets=targets,
        root=root,
    )
    fallback, fallback_sha, fallback_plan_sha = validate_fallback_manifest(
        read_json(fallback_path),
        manifest_path=fallback_path,
        plan_path=fallback_plan_path,
        targets=targets,
        provider_failures=provider_failures,
        i2v_manifest_sha256=i2v_sha,
        root=root,
    )
    partitions = (set(i2v), set(compositor), set(fallback))
    if (
        any(partitions[left] & partitions[right] for left in range(3) for right in range(left + 1, 3))
        or len(i2v) + len(compositor) + len(fallback) != EXPECTED_TARGETS
    ):
        raise TuneMediaOverlayError("I2V/compositor/fallback media partitions overlap or are incomplete")
    all_paths = {
        video["repository_video_path"]
        for video in [*i2v.values(), *compositor.values(), *fallback.values()]
    }
    if len(all_paths) != EXPECTED_TARGETS:
        raise TuneMediaOverlayError("All 65 repository video paths must be unique")
    return ValidatedMedia(
        i2v=i2v,
        compositor=compositor,
        fallback=fallback,
        i2v_manifest_sha256=i2v_sha,
        compositor_manifest_sha256=compositor_sha,
        compositor_plan_sha256=plan_sha,
        fallback_manifest_sha256=fallback_sha,
        fallback_plan_sha256=fallback_plan_sha,
    )


def build_merged_manifest(
    media_commit_sha: str,
    *,
    root: Path = ROOT,
    tune_manifest_rel: Path = TUNE_MANIFEST_REL,
    i2v_manifest_rel: Path = I2V_MANIFEST_REL,
    compositor_manifest_rel: Path = COMPOSITOR_MANIFEST_REL,
    compositor_plan_rel: Path = COMPOSITOR_PLAN_REL,
    fallback_manifest_rel: Path = FALLBACK_MANIFEST_REL,
    fallback_plan_rel: Path = FALLBACK_PLAN_REL,
) -> tuple[dict[str, Any], str | None]:
    root = root.resolve()
    commit_sha = validate_commit_sha(media_commit_sha)
    tune_path = root / safe_relative(tune_manifest_rel.as_posix(), label="Tune manifest")
    source_document = read_json(tune_path)
    base, targets, existing_commit, recorded_source_sha = validate_tune_manifest(source_document)
    if existing_commit is not None and existing_commit != commit_sha:
        raise TuneMediaOverlayError(
            f"Tune manifest is already pinned to a different media commit: {existing_commit}"
        )
    prompt_manifest_sha256 = (
        recorded_source_sha if existing_commit is not None else sha256_file(tune_path)
    )
    media = validate_media_inputs(
        root=root,
        prompt_manifest_sha256=prompt_manifest_sha256,
        targets=targets,
        i2v_manifest_rel=i2v_manifest_rel,
        compositor_manifest_rel=compositor_manifest_rel,
        compositor_plan_rel=compositor_plan_rel,
        fallback_manifest_rel=fallback_manifest_rel,
        fallback_plan_rel=fallback_plan_rel,
    )
    merged = copy.deepcopy(base)
    merged_scope = merged["scope"]
    merged_scope.update(
        {
            "new_video_generation": True,
            "generated_video_count": EXPECTED_TARGETS,
            "generated_video_delivery": "repository-raw",
            "generated_video_method_counts": {
                "eliza-i2v": EXPECTED_ELIZA_I2V,
                "deterministic-compositor": EXPECTED_COMPOSITOR,
                "deterministic-compositor-fallback": EXPECTED_FALLBACK,
            },
            "media_commit_sha": commit_sha,
            "new_s3_upload": False,
        }
    )
    for case in merged["cases"]:
        for target in case["targets"]:
            key = (str(case["case_id"]), str(target["model_id"]))
            video = (
                media.i2v.get(key)
                or media.compositor.get(key)
                or media.fallback.get(key)
            )
            if video is None:
                raise TuneMediaOverlayError(f"No validated Tune video for {key}")
            bound = copy.deepcopy(video)
            bound["delivery"] = "repository-raw"
            bound["url"] = raw_url(commit_sha, bound["repository_video_path"])
            if bound["method"] == "eliza-i2v":
                bound["generation"].update(
                    {
                        "manifest_path": i2v_manifest_rel.as_posix(),
                        "manifest_sha256": media.i2v_manifest_sha256,
                    }
                )
            elif bound["method"] == "deterministic-compositor":
                bound["compositor"].update(
                    {
                        "manifest_path": compositor_manifest_rel.as_posix(),
                        "manifest_sha256": media.compositor_manifest_sha256,
                        "plan_path": compositor_plan_rel.as_posix(),
                        "plan_sha256": media.compositor_plan_sha256,
                    }
                )
            else:
                bound["compositor_fallback"].update(
                    {
                        "manifest_path": fallback_manifest_rel.as_posix(),
                        "manifest_sha256": media.fallback_manifest_sha256,
                        "plan_path": fallback_plan_rel.as_posix(),
                        "plan_sha256": media.fallback_plan_sha256,
                    }
                )
            target["tuned"]["video"] = bound
    merged["media_generation"] = {
        "schema_version": 1,
        "media_commit_sha": commit_sha,
        "delivery": "repository-raw",
        "source_tune_manifest_sha256": prompt_manifest_sha256,
        "generated_video_count": EXPECTED_TARGETS,
        "method_counts": {
            "eliza-i2v": EXPECTED_ELIZA_I2V,
            "deterministic-compositor": EXPECTED_COMPOSITOR,
            "deterministic-compositor-fallback": EXPECTED_FALLBACK,
        },
        "i2v_generation": {
            "batch_id": I2V_BATCH_ID,
            "manifest_path": i2v_manifest_rel.as_posix(),
            "manifest_sha256": media.i2v_manifest_sha256,
            "provider_attempts": EXPECTED_I2V,
            "repository_videos": EXPECTED_ELIZA_I2V,
            "terminal_provider_failures": EXPECTED_FALLBACK,
        },
        "deterministic_compositor": {
            "batch_id": COMPOSITOR_BATCH_ID,
            "manifest_path": compositor_manifest_rel.as_posix(),
            "manifest_sha256": media.compositor_manifest_sha256,
            "plan_path": compositor_plan_rel.as_posix(),
            "plan_sha256": media.compositor_plan_sha256,
            "outputs": EXPECTED_COMPOSITOR,
        },
        "deterministic_compositor_fallback": {
            "batch_id": FALLBACK_BATCH_ID,
            "manifest_path": fallback_manifest_rel.as_posix(),
            "manifest_sha256": media.fallback_manifest_sha256,
            "plan_path": fallback_plan_rel.as_posix(),
            "plan_sha256": media.fallback_plan_sha256,
            "outputs": EXPECTED_FALLBACK,
            "prompt_evaluated": False,
        },
        "s3_upload": False,
        "pages_media_copy": False,
    }
    if existing_commit is not None and merged != source_document:
        raise TuneMediaOverlayError(
            "Existing same-commit Tune media overlay differs from validated deterministic output"
        )
    return merged, existing_commit


def merge_manifest(
    media_commit_sha: str,
    *,
    root: Path = ROOT,
    tune_manifest_rel: Path = TUNE_MANIFEST_REL,
    output_rel: Path | None = None,
    i2v_manifest_rel: Path = I2V_MANIFEST_REL,
    compositor_manifest_rel: Path = COMPOSITOR_MANIFEST_REL,
    compositor_plan_rel: Path = COMPOSITOR_PLAN_REL,
    fallback_manifest_rel: Path = FALLBACK_MANIFEST_REL,
    fallback_plan_rel: Path = FALLBACK_PLAN_REL,
) -> tuple[dict[str, Any], bool]:
    root = root.resolve()
    output_rel = output_rel or tune_manifest_rel
    output_path = root / safe_relative(output_rel.as_posix(), label="output manifest")
    merged, existing_commit = build_merged_manifest(
        media_commit_sha,
        root=root,
        tune_manifest_rel=tune_manifest_rel,
        i2v_manifest_rel=i2v_manifest_rel,
        compositor_manifest_rel=compositor_manifest_rel,
        compositor_plan_rel=compositor_plan_rel,
        fallback_manifest_rel=fallback_manifest_rel,
        fallback_plan_rel=fallback_plan_rel,
    )
    if output_path.is_file():
        existing_output = read_json(output_path)
        if existing_output == merged:
            return merged, False
        output_scope = existing_output.get("scope") if isinstance(existing_output, dict) else None
        output_commit = (
            output_scope.get("media_commit_sha") if isinstance(output_scope, dict) else None
        )
        if output_commit is not None and output_commit != media_commit_sha:
            raise TuneMediaOverlayError(
                f"Output manifest is pinned to a different media commit: {output_commit}"
            )
        if output_path != (root / tune_manifest_rel) or existing_commit is not None:
            raise TuneMediaOverlayError("Refusing to overwrite a different existing output manifest")
    transport.atomic_write_json(output_path, merged)
    return merged, True


def summary(document: dict[str, Any], *, wrote: bool | None = None) -> dict[str, Any]:
    methods = Counter(
        target["tuned"]["video"]["method"]
        for case in document["cases"]
        for target in case["targets"]
    )
    statuses = Counter(
        target["tuned"]["video"]["status"]
        for case in document["cases"]
        for target in case["targets"]
    )
    result: dict[str, Any] = {
        "valid": True,
        "media_commit_sha": document["media_generation"]["media_commit_sha"],
        "videos": sum(methods.values()),
        "methods": dict(sorted(methods.items())),
        "statuses": dict(sorted(statuses.items())),
        "delivery": "repository-raw",
        "s3_upload": False,
    }
    if wrote is not None:
        result["written"] = wrote
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--tune-manifest", type=Path, default=TUNE_MANIFEST_REL)
    parser.add_argument("--i2v-manifest", type=Path, default=I2V_MANIFEST_REL)
    parser.add_argument(
        "--compositor-manifest", type=Path, default=COMPOSITOR_MANIFEST_REL
    )
    parser.add_argument("--compositor-plan", type=Path, default=COMPOSITOR_PLAN_REL)
    parser.add_argument(
        "--fallback-manifest", type=Path, default=FALLBACK_MANIFEST_REL
    )
    parser.add_argument("--fallback-plan", type=Path, default=FALLBACK_PLAN_REL)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate all 65 inputs without writing")
    validate.add_argument("--media-commit-sha", required=True)
    merge = subparsers.add_parser("merge", help="atomically emit/update the Tune manifest")
    merge.add_argument("--media-commit-sha", required=True)
    merge.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            document, _ = build_merged_manifest(
                args.media_commit_sha,
                root=args.root,
                tune_manifest_rel=args.tune_manifest,
                i2v_manifest_rel=args.i2v_manifest,
                compositor_manifest_rel=args.compositor_manifest,
                compositor_plan_rel=args.compositor_plan,
                fallback_manifest_rel=args.fallback_manifest,
                fallback_plan_rel=args.fallback_plan,
            )
            result = summary(document)
        else:
            document, wrote = merge_manifest(
                args.media_commit_sha,
                root=args.root,
                tune_manifest_rel=args.tune_manifest,
                output_rel=args.output,
                i2v_manifest_rel=args.i2v_manifest,
                compositor_manifest_rel=args.compositor_manifest,
                compositor_plan_rel=args.compositor_plan,
                fallback_manifest_rel=args.fallback_manifest,
                fallback_plan_rel=args.fallback_plan,
            )
            result = summary(document, wrote=wrote)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except TuneMediaOverlayError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
