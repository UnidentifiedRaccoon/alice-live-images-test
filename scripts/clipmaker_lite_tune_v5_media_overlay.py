#!/usr/bin/env python3
"""Merge the final Tune review set through immutable v6, v7 and v8 retries.

The merger is deterministic and performs no provider, S3 or GitHub call.  It
reads the byte-frozen v4 manifest snapshot, the SHA-bound review export, the
verified planning manifests and immutable generation receipts. Helped v4
videos are reused byte-for-byte; each later batch supersedes only its exact
logical target. Every reviewable MP4 is served from an immutable raw GitHub
URL pinned to the operator-supplied media commit. Provider failures remain
explicit unavailable I2V attempts and never receive a compositor fallback.
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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_tune_v5_pipeline as planning  # noqa: E402
from scripts import clipmaker_lite_tune_v5_retry_video_pipeline as retry_generation  # noqa: E402
from scripts import clipmaker_lite_tune_v5_video_pipeline as generation  # noqa: E402
from scripts import clipmaker_lite_tune_v7_filter_retry_planning as v7_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v7_veo_filter_retry_video_pipeline as v7_generation  # noqa: E402
from scripts import clipmaker_lite_tune_v8_veo_prompt_experiment_planning as v8_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v8_veo_prompt_experiment_video_pipeline as v8_generation  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
REVIEW_BATCH_ID = "promopages-10060-tune-review-20260812-v8"
V4_SNAPSHOT_REL = planning.V4_SNAPSHOT_REL
PROMPT_MANIFEST_REL = generation.PROMPT_MANIFEST_REL
GENERATION_MANIFEST_REL = generation.GENERATION_MANIFEST_REL
RETRY_GENERATION_MANIFEST_REL = retry_generation.GENERATION_MANIFEST_REL
V7_FILTER_BATCH_ID = v7_generation.BATCH_ID
V7_FILTER_GENERATION_MANIFEST_REL = v7_generation.GENERATION_MANIFEST_REL
V7_FILTER_PROMPT_MANIFEST_REL = v7_generation.PROMPT_MANIFEST_REL
V7_FILTER_EXPECTED_PROMPT_SHA256 = v7_generation.PROMPT_MANIFEST_SHA256
V7_FILTER_EXPECTED_KEY = v7_generation.EXPECTED_KEY
V8_EXPERIMENT_BATCH_ID = v8_generation.BATCH_ID
V8_EXPERIMENT_GENERATION_MANIFEST_REL = v8_generation.GENERATION_MANIFEST_REL
V8_EXPERIMENT_PROMPT_MANIFEST_REL = v8_generation.PROMPT_MANIFEST_REL
V8_EXPERIMENT_EXPECTED_PROMPT_SHA256 = v8_generation.PROMPT_MANIFEST_SHA256
V8_EXPERIMENT_EXPECTED_GENERATION_SHA256 = (
    "fcb71618ce83d8ad5bd9c678b2fcfc7bcd094ccb82d4a4bb235f38327779e130"
)
V6_VISUAL_QA: dict[str, dict[str, Any]] = {
    "17#11::alibaba/wan-2.2": {
        "status": "visual-review-failed",
        "verified": False,
        "reviewable": True,
        "reviewer": "codex-visual-qa",
        "video_sha256": (
            "bac0e01c8512a7e8e16d73ce478b201b74abe56ebf08c8c6cb8539bd32622264"
        ),
        "automatic_rejection": False,
        "scope": "strict-visual-fidelity",
        "summary": (
            "Counts, copy and the woman are mostly stable, but the product cluster "
            "does not preserve rigid image-space relationships during the push."
        ),
        "findings": [
            "The product cluster independently enlarges and moves instead of following one uniform camera push.",
            "Package overlap and spacing change during the shot.",
            "Small labels and glyphs deform or flicker.",
        ],
    },
    "18#06::alibaba/wan-2.2": {
        "status": "visual-review-failed",
        "verified": False,
        "reviewable": True,
        "reviewer": "codex-visual-qa",
        "video_sha256": (
            "f6918a5638fcafa8b8c9621dcb020e7f7a1e24967ff1cdfd20c5a43fed4c8717"
        ),
        "automatic_rejection": False,
        "scope": "strict-visual-fidelity",
        "summary": (
            "Camera, floor, adhesive, guides and detached trowel remain rigid, but "
            "the worker exceeds the requested head-shoulder-torso microshift."
        ),
        "findings": [
            "The hips, knees, feet and whole body translate or reform during the shot.",
            "The worker shows visible morphology drift beyond the bounded microshift.",
        ],
    },
}
LIVE_MANIFEST_REL = Path("clipmaker-lite-test/tune-manifest.json")
RAW_OWNER = "UnidentifiedRaccoon"
RAW_REPOSITORY = "alice-live-images-test"
MAX_GITHUB_FILE_BYTES = 100_000_000
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TuneV5OverlayError(RuntimeError):
    """The v5 review merge failed a lineage or local-media binding."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TuneV5OverlayError(f"Required JSON is missing: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TuneV5OverlayError(f"Invalid JSON: {path}") from exc


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError as exc:
        raise TuneV5OverlayError(f"Required file is missing: {path}") from exc


def safe_relative(value: Any, *, label: str, suffix: str | None = None) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TuneV5OverlayError(f"{label} must be a canonical relative path")
    path = Path(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or (suffix is not None and path.suffix.lower() != suffix)
    ):
        raise TuneV5OverlayError(f"Unsafe {label}: {value!r}")
    return value


def confined_file(
    root: Path,
    relative_path: str,
    *,
    label: str,
    expected_sha256: str,
    expected_bytes: int,
) -> Path:
    path = root / safe_relative(relative_path, label=label)
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise TuneV5OverlayError(f"{label} is missing or outside workspace") from exc
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise TuneV5OverlayError(f"{label} must be a regular non-symlink file")
    if (
        info.st_size != expected_bytes
        or info.st_size <= 0
        or info.st_size >= MAX_GITHUB_FILE_BYTES
        or sha256_file(path) != expected_sha256
    ):
        raise TuneV5OverlayError(f"{label} SHA/size binding changed")
    return path


def confined_json(root: Path, relative_path: str, *, label: str) -> tuple[Path, dict[str, Any]]:
    path = root / safe_relative(relative_path, label=label, suffix=".json")
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise TuneV5OverlayError(f"{label} is missing or outside workspace") from exc
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise TuneV5OverlayError(f"{label} must be a regular non-symlink file")
    document = read_json(path)
    if not isinstance(document, dict):
        raise TuneV5OverlayError(f"{label} must contain a JSON object")
    return path, document


def validate_commit_sha(value: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise TuneV5OverlayError("media commit SHA must be 40 lowercase hex characters")
    return value


def raw_url(commit_sha: str, repository_path: str) -> str:
    return (
        f"https://raw.githubusercontent.com/{RAW_OWNER}/{RAW_REPOSITORY}/"
        f"{commit_sha}/{repository_path}"
    )


def _flatten_cases(document: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    flattened: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for case in document.get("cases", []):
        case_id = str(case.get("case_id"))
        for target in case.get("targets", []):
            key = f"{case_id}::{target.get('model_id')}"
            if key in flattened:
                raise TuneV5OverlayError(f"Duplicate target: {key}")
            flattened[key] = (case, target)
    return flattened


def _validated_v4_and_evaluations(
    root: Path,
    evaluation_path: Path,
    *,
    expected_v4_sha256: str = planning.EXPECTED_V4_MANIFEST_SHA256,
    expected_evaluation_sha256: str = planning.EXPECTED_EVALUATION_SHA256,
) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], dict[str, Any]]], dict[str, dict[str, Any]]]:
    snapshot_path = root / V4_SNAPSHOT_REL
    if sha256_file(snapshot_path) != expected_v4_sha256:
        raise TuneV5OverlayError("Historical v4 snapshot SHA-256 changed")
    v4 = read_json(snapshot_path)
    try:
        v4_targets = planning.validate_v4_manifest(
            v4,
            manifest_sha256=expected_v4_sha256,
        )
        _export, evaluations = planning.load_evaluation_export(
            evaluation_path,
            v4_targets=v4_targets,
            expected_sha256=expected_evaluation_sha256,
        )
    except planning.TuneV5PipelineError as exc:
        raise TuneV5OverlayError(str(exc)) from exc
    helped = {key for key, value in evaluations.items() if value.get("outcome") == "helped"}
    if len(helped) != 37 or helped & planning.EXPECTED_REGENERATE_KEYS:
        raise TuneV5OverlayError("Historical helped target set changed")
    return v4, v4_targets, evaluations


def validate_prompt_manifest(
    document: Any,
    *,
    path: Path,
) -> tuple[dict[str, tuple[dict[str, Any], dict[str, Any]]], str]:
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-planning"
        or document.get("ticket") != TICKET
        or document.get("batch_id") != planning.REPAIR_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or document.get("contract_version") != planning.EXPECTED_CONTRACT_VERSION
        or document.get("scope", {}).get("target_count") != 28
        or document.get("scope", {}).get("required_execution_mode") != "i2v"
        or document.get("scope", {}).get("fallback") is not False
        or not isinstance(document.get("cases"), list)
        or len(document["cases"]) != 17
    ):
        raise TuneV5OverlayError("Unexpected v5 prompt manifest")
    flattened = _flatten_cases(document)
    if set(flattened) != planning.EXPECTED_REGENERATE_KEYS:
        raise TuneV5OverlayError("v5 prompt target set changed")
    for key, (_case, target) in flattened.items():
        tuned = target.get("tuned")
        if (
            not isinstance(tuned, dict)
            or tuned.get("execution_mode") != "i2v"
            or not isinstance(tuned.get("positive_prompt"), str)
            or not tuned["positive_prompt"].strip()
            or tuned.get("negative_prompt") is not None
        ):
            raise TuneV5OverlayError(f"v5 prompt target is not I2V: {key}")
    return flattened, sha256_file(path)


def validate_generation_manifest(
    document: Any,
    *,
    path: Path,
    prompt_sha256: str,
    prompt_targets: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    root: Path,
    superseded_keys: frozenset[str] = frozenset(),
) -> tuple[dict[str, dict[str, Any]], str]:
    scope = document.get("scope") if isinstance(document, dict) else None
    scheduling = document.get("scheduling") if isinstance(document, dict) else None
    outputs = document.get("outputs") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-video-generation"
        or document.get("ticket") != TICKET
        or document.get("batch_id") != generation.BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(scope, dict)
        or scope.get("planning_batch_id") != planning.REPAIR_BATCH_ID
        or scope.get("prompt_manifest_sha256") != prompt_sha256
        or scope.get("prompt_manifest_path") != PROMPT_MANIFEST_REL.as_posix()
        or scope.get("contract_sha256") != sha256_file(root / generation.CONTRACT_REL)
        or scope.get("generation_routes_sha256") != sha256_file(root / generation.ROUTES_REL)
        or scope.get("expected_i2v_outputs") != 28
        or scope.get("compositor_outputs") != 0
        or scope.get("fallback_outputs") != 0
        or scope.get("s3_upload") is not False
        or not isinstance(scheduling, dict)
        or scheduling.get("route_capacities") != generation.EXPECTED_ROUTE_CAPACITIES
        or scheduling.get("one_paid_submission_per_provider_run_id") is not True
        or scheduling.get("automatic_paid_retry") is not False
        or scheduling.get("fallback") is not False
        or document.get("budget") != generation.budget_document("9.80")
        or not isinstance(outputs, list)
        or len(outputs) != 28
    ):
        raise TuneV5OverlayError("Unexpected v5 generation manifest")
    by_key: dict[str, dict[str, Any]] = {}
    model_counts: Counter[str] = Counter()
    for output in outputs:
        key = f"{output.get('case_id')}::{output.get('model_id')}" if isinstance(output, dict) else ""
        prompt_pair = prompt_targets.get(key)
        if (
            not isinstance(output, dict)
            or prompt_pair is None
            or key in by_key
            or output.get("execution_mode") != "i2v"
            or output.get("fallback") is not None
        ):
            raise TuneV5OverlayError(f"Invalid/duplicate v5 generation output: {key}")
        prompt_case, prompt_target = prompt_pair
        source = prompt_case.get("source")
        tuned = prompt_target.get("tuned")
        planning_record = prompt_case.get("planning")
        if not isinstance(source, dict) or not isinstance(tuned, dict) or not isinstance(planning_record, dict):
            raise TuneV5OverlayError(f"v5 prompt entry shape changed: {key}")
        entry = generation.Entry(
            case_id=prompt_case["case_id"],
            sheet_row=prompt_target["sheet_row"],
            article_slug=prompt_case["article_slug"],
            image_id=str(source["image_id"]),
            model_id=prompt_target["model_id"],
            source_path=source["path"],
            source_url=source["url"],
            source_sha256=source["sha256"],
            width=int(source["width"]),
            height=int(source["height"]),
            planning_run_id=planning_record["run_id"],
            result_path=planning_record["result_path"],
            result_sha256=planning_record["result_sha256"],
            prompt_manifest_sha256=prompt_sha256,
            route_registry_sha256=scope["generation_routes_sha256"],
            repair_feedback_path=planning_record["repair_feedback_path"],
            repair_feedback_sha256=planning_record["repair_feedback_sha256"],
            scene_plan=tuned["scene_plan"],
            positive_prompt=tuned["positive_prompt"],
            runtime=copy.deepcopy(tuned["runtime"]),
            provenance=copy.deepcopy(planning_record["provenance"]),
        )
        expected_paths = generation.artifact_paths(entry, root)
        expected_path_values = {
            name: relative_path(expected_paths[name], root)
            for name in ("prompt", "run", "video")
        }
        if (
            output.get("provider_run_id") != entry.provider_run_id
            or output.get("case_id") != entry.case_id
            or output.get("sheet_row") != entry.sheet_row
            or output.get("article_slug") != entry.article_slug
            or str(output.get("image_id")) != entry.image_id
            or output.get("model_id") != entry.model_id
            or output.get("prompt_path") != expected_path_values["prompt"]
            or output.get("run_path") != expected_path_values["run"]
            or output.get("video_path") != expected_path_values["video"]
        ):
            raise TuneV5OverlayError(f"v5 generation target binding changed: {key}")
        _prompt_path, prompt_receipt = confined_json(
            root,
            output["prompt_path"],
            label=f"v5 provider prompt {key}",
        )
        _run_path, run = confined_json(
            root,
            output["run_path"],
            label=f"v5 provider run {key}",
        )
        expected_run = generation._initial_run(entry, expected_paths, root)  # noqa: SLF001
        immutable_run_keys = (
            "manifest_role", "ticket", "batch_id", "agent_id", "provider_run_id",
            "planning_run_id", "case_id", "sheet_row", "model_id", "execution_mode",
            "adapter", "prompt_path", "output_path", "automatic_paid_retry", "fallback",
            "s3_upload",
        )
        request = transport.build_request_preview(
            generation.provider_sample(entry),
            generation.provider_prompt(entry),
        )
        request_sha256 = transport.request_fingerprint(
            request,
            generation.provider_sample(entry),
        )
        status = output.get("status")
        if (
            prompt_receipt != generation.prompt_artifact(entry)
            or any(run.get(name) != expected_run[name] for name in immutable_run_keys)
            or run.get("status") != status
            or run.get("media") != output.get("media")
            or run.get("contract_check") != output.get("contract_check")
            or run.get("error") != output.get("error")
            or run.get("request") != request
            or run.get("request_sha256") != request_sha256
            or run.get("request_fingerprint_version")
            != transport.REQUEST_FINGERPRINT_VERSION
            or (
                key not in superseded_keys
                and run.get("provider_may_be_active") is not False
            )
        ):
            raise TuneV5OverlayError(f"v5 provider receipt binding changed: {key}")
        if key in superseded_keys:
            expected_status = retry_generation.EXPECTED_SOURCE_STATUSES.get(key)
            expected_active = expected_status == "submit-unknown"
            if (
                status != expected_status
                or output.get("media") is not None
                or output.get("contract_check") is not None
                or (root / safe_relative(output.get("video_path"), label=f"{key} video_path")).exists()
                or run.get("provider_may_be_active") is not expected_active
                or run.get("fallback") is not None
                or run.get("automatic_paid_retry") is not False
            ):
                raise TuneV5OverlayError(f"Superseded v5 attempt audit changed: {key}")
            by_key[key] = output
            model_counts[str(output["model_id"])] += 1
            continue
        if status in {"succeeded", "verification-failed"}:
            media = output.get("media")
            check = output.get("contract_check")
            if (
                not isinstance(media, dict)
                or not isinstance(media.get("sha256"), str)
                or SHA256_RE.fullmatch(media["sha256"]) is None
                or not isinstance(media.get("bytes"), int)
                or not isinstance(check, dict)
                or (status == "succeeded" and check.get("conforms") is not True)
                or (status == "verification-failed" and check.get("conforms") is not False)
            ):
                raise TuneV5OverlayError(f"v5 media receipt is invalid: {key}")
            confined_file(
                root,
                output["video_path"],
                label=f"v5 MP4 {key}",
                expected_sha256=media["sha256"],
                expected_bytes=media["bytes"],
            )
        elif status == "provider-failed":
            if (
                output.get("media") is not None
                or output.get("contract_check") is not None
                or (root / safe_relative(output.get("video_path"), label=f"{key} video_path")).exists()
                or not isinstance(output.get("error"), str)
                or not output["error"].strip()
                or run.get("completed_at") is None
            ):
                raise TuneV5OverlayError(f"v5 provider failure audit is invalid: {key}")
        else:
            raise TuneV5OverlayError(f"v5 output is not terminal: {key} / {status}")
        by_key[key] = output
        model_counts[str(output["model_id"])] += 1
    if set(by_key) != planning.EXPECTED_REGENERATE_KEYS or dict(model_counts) != generation.EXPECTED_BY_MODEL:
        raise TuneV5OverlayError("v5 terminal output matrix changed")
    return by_key, sha256_file(path)


def validate_retry_generation_manifest(
    document: Any,
    *,
    path: Path,
    root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, retry_generation.Entry], str]:
    """Validate all eight terminal v6 attempts and their immutable lineage."""

    inventory = retry_generation.load_inventory(root=root)
    entries = {entry.evaluation_id: entry for entry in inventory.entries}
    scope = document.get("scope") if isinstance(document, dict) else None
    scheduling = document.get("scheduling") if isinstance(document, dict) else None
    outputs = document.get("outputs") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role")
        != "clipmaker-lite-tune-v6-retry-video-generation"
        or document.get("ticket") != TICKET
        or document.get("batch_id") != retry_generation.BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(scope, dict)
        or scope.get("expected_i2v_outputs") != 8
        or scope.get("model_counts") != retry_generation.EXPECTED_BY_MODEL
        or scope.get("new_veo_prompt_batch_id") != retry_generation.VEO_PROMPT_BATCH_ID
        or scope.get("source_wan_prompt_batch_id")
        != retry_generation.SOURCE_PROMPT_BATCH_ID
        or scope.get("source_video_batch_id") != retry_generation.SOURCE_VIDEO_BATCH_ID
        or scope.get("source_prompt_manifest_sha256")
        != inventory.source_prompt_manifest_sha256
        or scope.get("veo_prompt_manifest_sha256")
        != inventory.veo_prompt_manifest_sha256
        or scope.get("source_generation_manifest_sha256")
        != inventory.source_generation_manifest_sha256
        or scope.get("contract_sha256") != inventory.contract_sha256
        or scope.get("generation_routes_sha256") != inventory.route_registry_sha256
        or scope.get("normalized_wan_2_7_sources") != 2
        or scope.get("compositor_outputs") != 0
        or scope.get("fallback_outputs") != 0
        or scope.get("s3_upload") is not False
        or document.get("budget") != retry_generation.aggregate_budget_document()
        or not isinstance(scheduling, dict)
        or scheduling.get("route_capacities")
        != retry_generation.EXPECTED_ROUTE_CAPACITIES
        or scheduling.get("subset_execution_supported") is not True
        or scheduling.get("one_paid_submission_per_new_provider_run_id") is not True
        or scheduling.get("automatic_paid_retry") is not False
        or scheduling.get("fallback") is not False
        or not isinstance(outputs, list)
        or len(outputs) != 8
    ):
        raise TuneV5OverlayError("Unexpected v6 retry generation manifest")
    by_key: dict[str, dict[str, Any]] = {}
    model_counts: Counter[str] = Counter()
    for output in outputs:
        key = str(output.get("evaluation_id")) if isinstance(output, dict) else ""
        entry = entries.get(key)
        if (
            not isinstance(output, dict)
            or entry is None
            or key in by_key
            or output.get("execution_mode") != "i2v"
            or output.get("retry_reason") != entry.retry_reason
            or output.get("prior_attempt") != entry.prior_attempt
            or output.get("prompt_lineage_kind") != entry.prompt_lineage_kind
            or output.get("automatic_paid_retry") is not False
            or output.get("fallback") is not None
        ):
            raise TuneV5OverlayError(f"Invalid/duplicate v6 retry output: {key}")
        paths = retry_generation.artifact_paths(entry, root)
        expected_path_values = {
            name: relative_path(paths[name], root) for name in ("prompt", "run", "video")
        }
        if (
            output.get("provider_run_id") != entry.provider_run_id
            or output.get("case_id") != entry.case_id
            or output.get("sheet_row") != entry.sheet_row
            or output.get("article_slug") != entry.article_slug
            or str(output.get("image_id")) != entry.image_id
            or output.get("model_id") != entry.model_id
            or output.get("prompt_path") != expected_path_values["prompt"]
            or output.get("run_path") != expected_path_values["run"]
            or output.get("video_path") != expected_path_values["video"]
        ):
            raise TuneV5OverlayError(f"v6 retry target binding changed: {key}")
        _prompt_path, prompt_receipt = confined_json(
            root, output["prompt_path"], label=f"v6 provider prompt {key}"
        )
        _run_path, run = confined_json(
            root, output["run_path"], label=f"v6 provider run {key}"
        )
        expected_run = retry_generation._initial_run(entry, paths, root)  # noqa: SLF001
        immutable_run_keys = (
            "manifest_role",
            "ticket",
            "batch_id",
            "agent_id",
            "provider_run_id",
            "case_id",
            "sheet_row",
            "model_id",
            "execution_mode",
            "adapter",
            "retry_reason",
            "prior_attempt",
            "prompt_path",
            "output_path",
            "budget_reservation_usd",
            "new_immutable_provider_run",
            "automatic_paid_retry",
            "fallback",
            "s3_upload",
        )
        request = transport.build_request_preview(
            retry_generation.provider_sample(entry),
            retry_generation.provider_prompt(entry),
        )
        request_sha256 = transport.request_fingerprint(
            request, retry_generation.provider_sample(entry)
        )
        status = output.get("status")
        if (
            prompt_receipt != retry_generation.prompt_artifact(entry)
            or any(run.get(name) != expected_run[name] for name in immutable_run_keys)
            or run.get("status") != status
            or run.get("media") != output.get("media")
            or run.get("contract_check") != output.get("contract_check")
            or run.get("error") != output.get("error")
            or run.get("submission_count") != output.get("submission_count")
            or run.get("duplicate_risk_acceptance")
            != output.get("duplicate_risk_acceptance")
        ):
            raise TuneV5OverlayError(f"v6 retry receipt binding changed: {key}")
        withheld_status = retry_generation.ROUTE_SAFETY_WITHHELD_STATUSES.get(key)
        is_route_safety_withheld = (
            withheld_status is not None
            and status == withheld_status
            and output.get("duplicate_risk_acceptance") is None
        )
        if is_route_safety_withheld:
            request_is_valid = (
                run.get("request") is None
                and run.get("request_sha256") is None
                and run.get("request_fingerprint_version") is None
            ) if withheld_status == "pending" else (
                run.get("request") == request
                and run.get("request_sha256") == request_sha256
                and run.get("request_fingerprint_version")
                == transport.REQUEST_FINGERPRINT_VERSION
            )
            barrier = entries[retry_generation.SUBMIT_UNKNOWN_KEY].prior_attempt
            if (
                status != withheld_status
                or run.get("submission_count") != 0
                or run.get("provider_job_id") is not None
                or run.get("provider_may_be_active") is not False
                or not request_is_valid
                or output.get("media") is not None
                or output.get("contract_check") is not None
                or (root / safe_relative(output.get("video_path"), label=f"{key} video_path")).exists()
                or barrier.get("status") != "submit-unknown"
                or barrier.get("provider_may_be_active") is not True
                or not isinstance(barrier.get("run_path"), str)
                or barrier.get("run_sha256") != sha256_file(root / barrier["run_path"])
                or barrier.get("automatic_paid_retry") is not False
                or barrier.get("fallback") is not None
            ):
                raise TuneV5OverlayError(f"v6 route-safety withholding audit is invalid: {key}")
            by_key[key] = output
            model_counts[entry.model_id] += 1
            continue
        duplicate_risk_acceptance = output.get("duplicate_risk_acceptance")
        if entry.model_id == "alibaba/wan-2.2":
            barrier = entries[retry_generation.SUBMIT_UNKNOWN_KEY].prior_attempt
            if (
                not isinstance(duplicate_risk_acceptance, dict)
                or duplicate_risk_acceptance.get("authorization_kind")
                != "explicit-operator-duplicate-risk-acceptance"
                or duplicate_risk_acceptance.get("prior_inactive_not_confirmed") is not True
                or duplicate_risk_acceptance.get("source_evaluation_id")
                != retry_generation.SUBMIT_UNKNOWN_KEY
                or duplicate_risk_acceptance.get("source_provider_run_id")
                != barrier.get("provider_run_id")
                or duplicate_risk_acceptance.get("source_status") != "submit-unknown"
                or duplicate_risk_acceptance.get("source_provider_job_id") is not None
                or duplicate_risk_acceptance.get("source_run_path") != barrier.get("run_path")
                or duplicate_risk_acceptance.get("source_run_sha256")
                != barrier.get("run_sha256")
                or duplicate_risk_acceptance.get("maximum_possible_duplicate_charge_usd")
                != float(retry_generation.MAXIMUM_POSSIBLE_DUPLICATE_CHARGE_USD)
                or duplicate_risk_acceptance.get("automatic_paid_retry") is not False
                or duplicate_risk_acceptance.get("fallback") is not None
                or duplicate_risk_acceptance.get("authorized_evaluation_id") != key
            ):
                raise TuneV5OverlayError(
                    f"v6 Wan 2.2 duplicate-risk receipt changed: {key}"
                )
        elif duplicate_risk_acceptance is not None:
            raise TuneV5OverlayError(
                f"v6 non-Wan-2.2 output has duplicate-risk receipt: {key}"
            )
        if (
            run.get("request") != request
            or run.get("request_sha256") != request_sha256
            or run.get("request_fingerprint_version")
            != transport.REQUEST_FINGERPRINT_VERSION
        ):
            raise TuneV5OverlayError(f"v6 retry request binding changed: {key}")
        if status in {"succeeded", "verification-failed"}:
            media = output.get("media")
            check = output.get("contract_check")
            if (
                run.get("submission_count") != 1
                or not isinstance(media, dict)
                or not isinstance(media.get("sha256"), str)
                or SHA256_RE.fullmatch(media["sha256"]) is None
                or not isinstance(media.get("bytes"), int)
                or not isinstance(check, dict)
                or run.get("provider_may_be_active") is not False
                or (status == "succeeded" and check.get("conforms") is not True)
                or (status == "verification-failed" and check.get("conforms") is not False)
            ):
                raise TuneV5OverlayError(f"v6 retry media receipt is invalid: {key}")
            confined_file(
                root,
                output["video_path"],
                label=f"v6 retry MP4 {key}",
                expected_sha256=media["sha256"],
                expected_bytes=media["bytes"],
            )
        elif status in {"provider-failed", "failed-pre-submit", "submit-unknown"}:
            expected_active = status == "submit-unknown"
            expected_submission_counts = (
                {1} if status == "submit-unknown" else {0, 1}
            )
            if (
                run.get("submission_count") not in expected_submission_counts
                or run.get("provider_may_be_active") is not expected_active
                or (
                    status == "submit-unknown"
                    and run.get("provider_job_id") is not None
                )
                or output.get("media") is not None
                or output.get("contract_check") is not None
                or (root / safe_relative(output.get("video_path"), label=f"{key} video_path")).exists()
                or not isinstance(output.get("error"), str)
                or not output["error"].strip()
                or (
                    status == "submit-unknown"
                    and run.get("completed_at") is not None
                )
                or (
                    status != "submit-unknown"
                    and run.get("completed_at") is None
                )
            ):
                raise TuneV5OverlayError(f"v6 retry terminal failure audit is invalid: {key}")
        else:
            raise TuneV5OverlayError(f"v6 retry output is not terminal: {key} / {status}")
        by_key[key] = output
        model_counts[entry.model_id] += 1
    if set(by_key) != retry_generation.EXPECTED_KEYS or dict(model_counts) != retry_generation.EXPECTED_BY_MODEL:
        raise TuneV5OverlayError("v6 retry terminal output matrix changed")
    return by_key, entries, sha256_file(path)


def _load_v7_filter_prompt(*, root: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Load the one provenance-verified neutral Veo prompt used by v7."""

    path = root / V7_FILTER_PROMPT_MANIFEST_REL
    digest = sha256_file(path)
    document = read_json(path)
    scope = document.get("scope") if isinstance(document, dict) else None
    cases = document.get("cases") if isinstance(document, dict) else None
    if (
        digest != V7_FILTER_EXPECTED_PROMPT_SHA256
        or not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role")
        != "clipmaker-lite-tune-v7-filter-retry-planning"
        or document.get("ticket") != TICKET
        or document.get("batch_id") != v7_planning.BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or document.get("contract_version") != planning.EXPECTED_CONTRACT_VERSION
        or not isinstance(scope, dict)
        or scope.get("target_count") != 1
        or scope.get("required_execution_mode") != "i2v"
        or scope.get("required_rendering_strategy") != "camera-only"
        or scope.get("canonical_full_source_only") is not True
        or scope.get("source_transform") is not None
        or scope.get("disable_provider_safety_filters") is not False
        or scope.get("fallback") is not False
        or scope.get("compositor") is not False
        or scope.get("s3_upload") is not False
        or not isinstance(cases, list)
        or len(cases) != 1
    ):
        raise TuneV5OverlayError("Unexpected v7 filter-retry prompt manifest")
    case = cases[0]
    targets = case.get("targets") if isinstance(case, dict) else None
    source = case.get("source") if isinstance(case, dict) else None
    planning_record = case.get("planning") if isinstance(case, dict) else None
    if (
        not isinstance(case, dict)
        or case.get("case_id") != v7_planning.CASE_ID
        or case.get("retry_reason")
        != "repeated-provider-filter-neutral-source-bound-repair"
        or not isinstance(source, dict)
        or source.get("sha256") != v7_planning.CANONICAL_SOURCE_SHA256
        or source.get("width") != 2400
        or source.get("height") != 1600
        or not isinstance(planning_record, dict)
        or not isinstance(targets, list)
        or len(targets) != 1
        or not isinstance(targets[0], dict)
        or targets[0].get("evaluation_id") != V7_FILTER_EXPECTED_KEY
        or targets[0].get("model_id") != v7_planning.MODEL_ID
        or targets[0].get("tuned", {}).get("execution_mode") != "i2v"
        or targets[0].get("tuned", {}).get("positive_prompt")
        != v7_planning.EXACT_POSITIVE_PROMPT
        or targets[0].get("tuned", {}).get("negative_prompt") is not None
        or not v7_planning.result_is_verified(case, root=root)
    ):
        raise TuneV5OverlayError("V7 filter-retry Lite prompt binding changed")
    return case, targets[0], digest


def _validate_v7_filter_diagnostics(value: Any, *, required: bool) -> None:
    if value is None and not required:
        return
    allowed = {
        "id",
        "generation_id",
        "request_id",
        "status",
        "error",
        "support_code",
        "raiFilteredReason",
        "blockedReason",
        "diagnostics_unavailable_upstream",
    }
    if (
        not isinstance(value, dict)
        or not set(value).issubset(allowed)
        or any(
            item is not None and not isinstance(item, (str, bool))
            for item in value.values()
        )
        or (
            value.get("diagnostics_unavailable_upstream") is not True
            and not any(value.get(name) for name in allowed - {"diagnostics_unavailable_upstream"})
        )
    ):
        raise TuneV5OverlayError("V7 provider terminal diagnostics are invalid")


def validate_v7_filter_generation_manifest(
    document: Any,
    *,
    path: Path,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    """Validate the optional one-target v7 attempt without accepting a fallback."""

    case, target, prompt_manifest_sha256 = _load_v7_filter_prompt(root=root)
    try:
        entry = v7_generation.load_inventory(root=root)
    except v7_generation.TuneV7VeoRetryError as exc:
        raise TuneV5OverlayError(str(exc)) from exc
    scope = document.get("scope") if isinstance(document, dict) else None
    scheduling = document.get("scheduling") if isinstance(document, dict) else None
    outputs = document.get("outputs") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != v7_generation.MANIFEST_ROLE
        or document.get("ticket") != TICKET
        or document.get("batch_id") != V7_FILTER_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(scope, dict)
        or scope.get("expected_i2v_outputs") != 1
        or scope.get("model_counts") != {v7_generation.MODEL_ID: 1}
        or scope.get("prompt_batch_id") != v7_planning.BATCH_ID
        or scope.get("prompt_manifest_sha256") != prompt_manifest_sha256
        or scope.get("canonical_full_source_only") is not True
        or scope.get("source_transform") is not None
        or scope.get("disable_provider_safety_filters") is not False
        or scope.get("compositor_outputs") != 0
        or scope.get("fallback_outputs") != 0
        or scope.get("s3_upload") is not False
        or not isinstance(scheduling, dict)
        or scheduling.get("one_paid_submission_per_new_provider_run_id") is not True
        or scheduling.get("automatic_paid_retry") is not False
        or scheduling.get("fallback") is not False
        or not isinstance(outputs, list)
        or len(outputs) != 1
    ):
        raise TuneV5OverlayError("Unexpected v7 filter-retry generation manifest")
    output = outputs[0]
    artifact_paths = v7_generation.artifact_paths(entry, root)
    expected_paths = {
        name: relative_path(artifact_paths[name], root)
        for name in ("prompt", "run", "video")
    }
    if (
        not isinstance(output, dict)
        or output.get("evaluation_id") != V7_FILTER_EXPECTED_KEY
        or output.get("provider_run_id") != entry.provider_run_id
        or output.get("case_id") != entry.case_id
        or output.get("sheet_row") != entry.sheet_row
        or output.get("article_slug") != entry.article_slug
        or str(output.get("image_id")) != entry.image_id
        or output.get("model_id") != v7_generation.MODEL_ID
        or output.get("execution_mode") != "i2v"
        or output.get("prompt_path") != expected_paths["prompt"]
        or output.get("run_path") != expected_paths["run"]
        or output.get("video_path") != expected_paths["video"]
        or output.get("automatic_paid_retry") is not False
        or output.get("fallback") is not None
        or output.get("s3_upload") is not False
    ):
        raise TuneV5OverlayError("V7 filter-retry output binding changed")
    _prompt_path, prompt_receipt = confined_json(
        root, output["prompt_path"], label="v7 provider prompt"
    )
    _run_path, run = confined_json(root, output["run_path"], label="v7 provider run")
    if prompt_receipt != v7_generation.prompt_artifact(entry):
        raise TuneV5OverlayError("V7 provider prompt receipt changed")
    expected_request = v7_generation.provider_request(entry)
    expected_request_sha256 = transport.request_fingerprint(
        expected_request, v7_generation.provider_sample(entry)
    )
    initial_run = v7_generation._initial_run(entry, artifact_paths, root)  # noqa: SLF001
    immutable_run_keys = (
        "manifest_role",
        "ticket",
        "batch_id",
        "agent_id",
        "provider_run_id",
        "evaluation_id",
        "case_id",
        "sheet_row",
        "model_id",
        "execution_mode",
        "adapter",
        "prompt_path",
        "output_path",
        "budget_reservation_usd",
        "new_immutable_provider_run",
        "automatic_paid_retry",
        "fallback",
        "compositor",
        "source_transform",
        "disable_provider_safety_filters",
        "s3_upload",
    )
    status = output.get("status")
    if (
        any(run.get(name) != initial_run[name] for name in immutable_run_keys)
        or run.get("status") != status
        or run.get("request") != expected_request
        or run.get("request_sha256") != expected_request_sha256
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
        or run.get("submission_count") != output.get("submission_count")
        or run.get("media") != output.get("media")
        or run.get("contract_check") != output.get("contract_check")
        or run.get("error") != output.get("error")
        or run.get("provider_terminal_diagnostics")
        != output.get("provider_terminal_diagnostics")
        or run.get("diagnostics_unavailable_upstream")
        != output.get("diagnostics_unavailable_upstream")
        or (
            isinstance(output.get("provider_terminal_diagnostics"), dict)
            and output["provider_terminal_diagnostics"].get(
                "diagnostics_unavailable_upstream"
            )
            is not output.get("diagnostics_unavailable_upstream")
        )
        or run.get("terminal_no_output_stop_applied")
        != output.get("terminal_no_output_stop_applied")
        or run.get("automatic_paid_retry") is not False
        or run.get("fallback") is not None
        or run.get("s3_upload") is not False
    ):
        raise TuneV5OverlayError("V7 provider run receipt changed")
    if status in {"succeeded", "verification-failed"}:
        media = output.get("media")
        check = output.get("contract_check")
        _validate_v7_filter_diagnostics(
            output.get("provider_terminal_diagnostics"), required=False
        )
        if (
            run.get("submission_count") != 1
            or run.get("provider_may_be_active") is not False
            or not isinstance(media, dict)
            or not isinstance(media.get("sha256"), str)
            or SHA256_RE.fullmatch(media["sha256"]) is None
            or not isinstance(media.get("bytes"), int)
            or not isinstance(check, dict)
            or (status == "succeeded" and check.get("conforms") is not True)
            or (status == "verification-failed" and check.get("conforms") is not False)
            or output.get("terminal_no_output_stop_applied") is not False
        ):
            raise TuneV5OverlayError("V7 retry media receipt is invalid")
        confined_file(
            root,
            output["video_path"],
            label="v7 retry MP4",
            expected_sha256=media["sha256"],
            expected_bytes=media["bytes"],
        )
    elif status in {"provider-failed", "failed-pre-submit", "submit-unknown"}:
        expected_active = status == "submit-unknown"
        expected_counts = {1} if status in {"provider-failed", "submit-unknown"} else {0}
        terminal_no_output = "no output" in str(output.get("error", "")).lower()
        _validate_v7_filter_diagnostics(
            output.get("provider_terminal_diagnostics"),
            required=status == "provider-failed",
        )
        if (
            run.get("submission_count") not in expected_counts
            or run.get("provider_may_be_active") is not expected_active
            or output.get("media") is not None
            or output.get("contract_check") is not None
            or (root / output["video_path"]).exists()
            or not isinstance(output.get("error"), str)
            or not output["error"].strip()
            or (
                output.get("terminal_no_output_stop_applied") is not terminal_no_output
            )
        ):
            raise TuneV5OverlayError("V7 retry failure receipt is invalid")
    else:
        raise TuneV5OverlayError(f"V7 retry output is not publishable: {status}")
    return output, case, target, sha256_file(path), prompt_manifest_sha256


def validate_v8_experiment_generation_manifest(
    document: Any,
    *,
    path: Path,
    root: Path,
    expected_generation_sha256: str = V8_EXPERIMENT_EXPECTED_GENERATION_SHA256,
) -> tuple[list[dict[str, Any]], list[v8_generation.Entry], dict[str, Any], str, str]:
    """Validate all three immutable terminal V8 prompt experiments."""

    generation_sha256 = sha256_file(path)
    if generation_sha256 != expected_generation_sha256:
        raise TuneV5OverlayError("V8 experiment generation manifest digest changed")
    try:
        entries = v8_generation.load_inventory(root=root)
    except v8_generation.TuneV8VideoError as exc:
        raise TuneV5OverlayError(str(exc)) from exc
    prompt_path = root / V8_EXPERIMENT_PROMPT_MANIFEST_REL
    prompt_sha256 = sha256_file(prompt_path)
    prompt_document = read_json(prompt_path)
    prompt_cases = (
        prompt_document.get("cases") if isinstance(prompt_document, dict) else None
    )
    if (
        prompt_sha256 != V8_EXPERIMENT_EXPECTED_PROMPT_SHA256
        or not isinstance(prompt_document, dict)
        or prompt_document.get("manifest_role")
        != "clipmaker-lite-tune-v8-veo-prompt-experiment-planning"
        or prompt_document.get("batch_id") != v8_planning.BATCH_ID
        or not isinstance(prompt_cases, list)
        or len(prompt_cases) != 1
    ):
        raise TuneV5OverlayError("Unexpected V8 experiment prompt manifest")
    prompt_case = prompt_cases[0]
    scope = document.get("scope") if isinstance(document, dict) else None
    design = document.get("experiment_design") if isinstance(document, dict) else None
    budget = document.get("budget") if isinstance(document, dict) else None
    policy = document.get("policy") if isinstance(document, dict) else None
    scheduling = document.get("scheduling") if isinstance(document, dict) else None
    invocation = document.get("last_invocation") if isinstance(document, dict) else None
    outputs = document.get("outputs") if isinstance(document, dict) else None
    expected_experiment_ids = [entry.experiment_id for entry in entries]
    expected_variants = [entry.variant_id for entry in entries]
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != v8_generation.MANIFEST_ROLE
        or document.get("ticket") != TICKET
        or document.get("batch_id") != V8_EXPERIMENT_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(scope, dict)
        or scope.get("expected_i2v_outputs") != 3
        or scope.get("experiment_count") != 3
        or scope.get("model_counts") != {v8_generation.MODEL_ID: 3}
        or scope.get("prompt_batch_id") != v8_planning.BATCH_ID
        or scope.get("prompt_manifest_path")
        != V8_EXPERIMENT_PROMPT_MANIFEST_REL.as_posix()
        or scope.get("prompt_manifest_sha256") != prompt_sha256
        or scope.get("canonical_full_source_only") is not True
        or scope.get("source_transform") is not None
        or scope.get("disable_provider_safety_filters") is not False
        or scope.get("compositor_outputs") != 0
        or scope.get("fallback_outputs") != 0
        or scope.get("s3_upload") is not False
        or scope.get("delivery") != "repository-files"
        or design
        != {
            "shared_seed": v8_planning.SHARED_PROVIDER_SEED,
            "fixed_source_sha256": v8_planning.CANONICAL_SOURCE_SHA256,
            "changed_factor": "motion-only positive-prompt formulation",
            "variant_order": expected_variants,
        }
        or budget
        != {
            "currency": "USD",
            "hard_incremental_budget_cap_usd": 1.05,
            "reserved_output_count": 3,
            "accounting_cost_per_output_usd": 0.35,
            "maximum_estimated_cost_usd": 1.05,
            "provider_unit_costs_asserted": False,
            "one_submit_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
        }
        or policy
        != {
            "terminal_no_output_stops_same_experiment_retry": True,
            "automatic_paid_retry": False,
            "fallback": False,
            "compositor": False,
            "source_transform": None,
            "disable_provider_safety_filters": False,
        }
        or scheduling
        != {
            "route_capacity": 3,
            "worker_count": 3,
            "start_together": True,
            "coordinator_only_writes_aggregate_manifest": True,
            "one_paid_submission_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
            "fallback": False,
        }
        or invocation
        != {
            "mode": "generate",
            "selected_experiment_ids": expected_experiment_ids,
            "budget_cap_usd": 1.05,
            "one_paid_submit_per_provider_run_id": True,
            "automatic_paid_retry": False,
        }
        or document.get("summary") != {"provider-failed": 3}
        or not isinstance(outputs, list)
        or len(outputs) != 3
    ):
        raise TuneV5OverlayError("Unexpected terminal V8 experiment manifest")
    validated: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    immutable_run_keys = (
        "manifest_role",
        "ticket",
        "batch_id",
        "agent_id",
        "provider_run_id",
        "evaluation_id",
        "experiment_id",
        "variant_id",
        "case_id",
        "sheet_row",
        "model_id",
        "execution_mode",
        "adapter",
        "prompt_path",
        "output_path",
        "budget_reservation_usd",
        "new_immutable_provider_run",
        "automatic_paid_retry",
        "fallback",
        "compositor",
        "source_transform",
        "disable_provider_safety_filters",
        "s3_upload",
    )
    for output, entry in zip(outputs, entries, strict=True):
        artifact_paths = v8_generation.artifact_paths(entry, root)
        expected_paths = {
            name: relative_path(artifact_paths[name], root)
            for name in ("prompt", "run", "video")
        }
        if (
            not isinstance(output, dict)
            or output.get("provider_run_id") != entry.provider_run_id
            or output.get("evaluation_id") != entry.evaluation_id
            or output.get("experiment_id") != entry.experiment_id
            or output.get("variant_id") != entry.variant_id
            or output.get("controlled_factor") != entry.controlled_factor
            or output.get("case_id") != entry.case_id
            or output.get("sheet_row") != entry.sheet_row
            or output.get("article_slug") != entry.article_slug
            or str(output.get("image_id")) != entry.image_id
            or output.get("model_id") != v8_generation.MODEL_ID
            or output.get("execution_mode") != "i2v"
            or output.get("status") != "provider-failed"
            or output.get("prompt_path") != expected_paths["prompt"]
            or output.get("run_path") != expected_paths["run"]
            or output.get("video_path") != expected_paths["video"]
            or output.get("submission_count") != 1
            or output.get("media") is not None
            or output.get("contract_check") is not None
            or not isinstance(output.get("error"), str)
            or "no output" not in output["error"].lower()
            or output.get("terminal_no_output_stop_applied") is not True
            or output.get("automatic_paid_retry") is not False
            or output.get("fallback") is not None
            or output.get("s3_upload") is not False
        ):
            raise TuneV5OverlayError(
                f"V8 experiment output binding changed: {entry.variant_id}"
            )
        _prompt_file, prompt_receipt = confined_json(
            root,
            output["prompt_path"],
            label=f"V8 experiment prompt {entry.variant_id}",
        )
        _run_file, run = confined_json(
            root,
            output["run_path"],
            label=f"V8 experiment run {entry.variant_id}",
        )
        expected_initial = v8_generation._initial_run(  # noqa: SLF001
            entry, artifact_paths, root
        )
        request = v8_generation.provider_request(entry)
        fingerprint = transport.request_fingerprint(
            request, v8_generation.provider_sample(entry)
        )
        diagnostics = output.get("provider_terminal_diagnostics")
        _validate_v7_filter_diagnostics(diagnostics, required=True)
        if (
            prompt_receipt != v8_generation.prompt_artifact(entry)
            or any(
                run.get(name) != expected_initial[name]
                for name in immutable_run_keys
            )
            or run.get("status") != "provider-failed"
            or run.get("request") != request
            or run.get("request_sha256") != fingerprint
            or run.get("request_fingerprint_version")
            != transport.REQUEST_FINGERPRINT_VERSION
            or run.get("submission_count") != 1
            or not isinstance(run.get("provider_job_id"), str)
            or not run["provider_job_id"].strip()
            or run.get("provider_may_be_active") is not False
            or not isinstance(run.get("completed_at"), str)
            or not run["completed_at"].strip()
            or run.get("media") is not None
            or run.get("contract_check") is not None
            or run.get("error") != output["error"]
            or run.get("provider_terminal_diagnostics") != diagnostics
            or diagnostics.get("status") not in v8_generation.TERMINAL_FAILURES
            or run.get("diagnostics_unavailable_upstream")
            != output.get("diagnostics_unavailable_upstream")
            or diagnostics.get("diagnostics_unavailable_upstream")
            is not output.get("diagnostics_unavailable_upstream")
            or run.get("terminal_no_output_stop_applied") is not True
            or artifact_paths["video"].exists()
        ):
            raise TuneV5OverlayError(
                f"V8 terminal receipt changed: {entry.variant_id}"
            )
        for value in expected_paths.values():
            if value in seen_paths:
                raise TuneV5OverlayError("V8 experiment artifact paths overlap")
            seen_paths.add(value)
        validated.append(output)
    return validated, entries, prompt_case, generation_sha256, prompt_sha256


def _reviewable_video(
    *,
    root: Path,
    media_commit_sha: str,
    method: str,
    status: str,
    repository_path: str,
    media: dict[str, Any],
    contract_check: dict[str, Any],
    generation_record: dict[str, Any],
) -> dict[str, Any]:
    if method != "eliza-i2v":
        raise TuneV5OverlayError("v5 active manifest permits only eliza-i2v")
    confined_file(
        root,
        repository_path,
        label=f"review MP4 {repository_path}",
        expected_sha256=media["sha256"],
        expected_bytes=media["bytes"],
    )
    return {
        "state": "available",
        "status": status,
        "method": "eliza-i2v",
        "prompt_evaluated": True,
        "delivery": "repository-raw",
        "url": raw_url(media_commit_sha, repository_path),
        "repository_video_path": repository_path,
        "sha256": media["sha256"],
        "bytes": media["bytes"],
        "media": copy.deepcopy(media),
        "contract_check": copy.deepcopy(contract_check),
        "generation": copy.deepcopy(generation_record),
        "provider_attempt": None,
    }


def _reused_video(
    target: dict[str, Any],
    *,
    root: Path,
    media_commit_sha: str,
) -> dict[str, Any]:
    old = target.get("tuned", {}).get("video")
    if (
        not isinstance(old, dict)
        or old.get("method") != "eliza-i2v"
        or old.get("status") not in {"succeeded", "verification-failed"}
        or not isinstance(old.get("media"), dict)
        or not isinstance(old.get("contract_check"), dict)
    ):
        raise TuneV5OverlayError("A helped v4 target is not reusable Eliza I2V")
    path = safe_relative(old.get("repository_video_path"), label="v4 reused video", suffix=".mp4")
    media = old["media"]
    if media.get("sha256") != old.get("sha256") or media.get("bytes") != old.get("bytes"):
        raise TuneV5OverlayError("v4 helped media binding changed")
    video = _reviewable_video(
        root=root,
        media_commit_sha=media_commit_sha,
        method="eliza-i2v",
        status=old["status"],
        repository_path=path,
        media=media,
        contract_check=old["contract_check"],
        generation_record={
            "origin": "reused-helped-v4",
            "source_media_commit_sha": old.get("generation", {}).get("media_commit_sha"),
            "source_url": old.get("url"),
        },
    )
    return video


def _new_video(
    output: dict[str, Any],
    *,
    root: Path,
    media_commit_sha: str,
) -> dict[str, Any]:
    status = output["status"]
    if status == "provider-failed":
        run_path = safe_relative(output.get("run_path"), label="failed run path", suffix=".json")
        prompt_path = safe_relative(output.get("prompt_path"), label="failed prompt path", suffix=".json")
        run = read_json(root / run_path)
        if (
            run.get("status") != "provider-failed"
            or run.get("fallback") is not None
            or run.get("automatic_paid_retry") is not False
            or run.get("error") != output.get("error")
        ):
            raise TuneV5OverlayError("Provider-failed run receipt changed")
        return {
            "state": "unavailable",
            "status": "provider-failed",
            "method": "eliza-i2v",
            "prompt_evaluated": False,
            "delivery": "unavailable",
            "url": None,
            "repository_video_path": None,
            "sha256": None,
            "bytes": None,
            "media": None,
            "contract_check": None,
            "generation": {
                "origin": "regenerated-v5",
                "batch_id": generation.BATCH_ID,
                "provider_run_id": output["provider_run_id"],
                "prompt_path": prompt_path,
                "run_path": run_path,
            },
            "provider_attempt": {
                "status": "provider-failed",
                "run_path": run_path,
                "run_sha256": sha256_file(root / run_path),
                "prompt_path": prompt_path,
                "prompt_sha256": sha256_file(root / prompt_path),
                "provider_job_id": run.get("provider_job_id"),
                "error": output["error"],
                "automatic_paid_retry": False,
                "fallback": None,
            },
        }
    video = _reviewable_video(
        root=root,
        media_commit_sha=media_commit_sha,
        method="eliza-i2v",
        status=status,
        repository_path=output["video_path"],
        media=output["media"],
        contract_check=output["contract_check"],
        generation_record={
            "origin": "regenerated-v5",
            "batch_id": generation.BATCH_ID,
            "provider_run_id": output["provider_run_id"],
            "prompt_path": output["prompt_path"],
            "run_path": output["run_path"],
        },
    )
    return video


def _retry_video(
    output: dict[str, Any],
    entry: retry_generation.Entry,
    *,
    root: Path,
    media_commit_sha: str,
    route_barrier: dict[str, Any],
) -> dict[str, Any]:
    status = output["status"]
    generation_record = {
        "origin": "regenerated-v6-retry",
        "batch_id": retry_generation.BATCH_ID,
        "provider_run_id": output["provider_run_id"],
        "retry_reason": entry.retry_reason,
        "prompt_lineage_kind": entry.prompt_lineage_kind,
        "prompt_path": output["prompt_path"],
        "run_path": output["run_path"],
        "prior_attempt": copy.deepcopy(entry.prior_attempt),
        "duplicate_risk_acceptance": copy.deepcopy(
            output.get("duplicate_risk_acceptance")
        ),
    }
    withheld_status = retry_generation.ROUTE_SAFETY_WITHHELD_STATUSES.get(
        entry.evaluation_id
    )
    is_route_safety_withheld = (
        withheld_status is not None
        and status == withheld_status
        and output.get("duplicate_risk_acceptance") is None
    )
    if is_route_safety_withheld:
        run_path = safe_relative(output.get("run_path"), label="withheld run", suffix=".json")
        prompt_path = safe_relative(
            output.get("prompt_path"), label="withheld prompt", suffix=".json"
        )
        run = read_json(root / run_path)
        is_ambiguous_source = entry.evaluation_id == retry_generation.SUBMIT_UNKNOWN_KEY
        unavailable_reason = (
            "Исходная Wan 2.2 попытка завершилась как submit-unknown без job ID; "
            "провайдер всё ещё может выполнять запрос, поэтому новый запуск не делался."
            if is_ambiguous_source
            else "Новый Wan 2.2 запуск не делался: route capacity=1 удерживается "
            "исходной submit-unknown попыткой 17#11."
        )
        barrier_receipt = {
            "model_id": "alibaba/wan-2.2",
            "route_capacity": 1,
            "reason": retry_generation.ROUTE_SAFETY_REASON,
            "source_provider_attempt": copy.deepcopy(route_barrier),
        }
        return {
            "state": "unavailable",
            "status": "provider-unavailable",
            "recorded_status": (
                route_barrier["status"] if is_ambiguous_source else withheld_status
            ),
            "method": "eliza-i2v",
            "prompt_evaluated": None if is_ambiguous_source else False,
            "delivery": "unavailable",
            "url": None,
            "repository_video_path": None,
            "sha256": None,
            "bytes": None,
            "media": None,
            "contract_check": None,
            "unavailable_reason": unavailable_reason,
            "safety_barrier": barrier_receipt,
            "generation": {
                **generation_record,
                "origin": "withheld-v6-route-safety",
                "run_status": withheld_status,
            },
            "provider_attempt": {
                "status": (
                    "submit-unknown"
                    if is_ambiguous_source
                    else "not-attempted-route-safety"
                ),
                "run_path": run_path,
                "run_sha256": sha256_file(root / run_path),
                "prompt_path": prompt_path,
                "prompt_sha256": sha256_file(root / prompt_path),
                "provider_job_id": None,
                "provider_may_be_active": (
                    True if is_ambiguous_source else False
                ),
                "submission_count": 0,
                "error": unavailable_reason,
                "automatic_paid_retry": False,
                "fallback": None,
                "source_attempt": copy.deepcopy(entry.prior_attempt),
                "safety_barrier": barrier_receipt,
            },
        }
    if status in {"provider-failed", "failed-pre-submit", "submit-unknown"}:
        run_path = safe_relative(output.get("run_path"), label="retry failed run", suffix=".json")
        prompt_path = safe_relative(
            output.get("prompt_path"), label="retry failed prompt", suffix=".json"
        )
        run = read_json(root / run_path)
        return {
            "state": "unavailable",
            "status": "provider-unavailable",
            "recorded_status": status,
            "method": "eliza-i2v",
            "prompt_evaluated": False,
            "delivery": "unavailable",
            "url": None,
            "repository_video_path": None,
            "sha256": None,
            "bytes": None,
            "media": None,
            "contract_check": None,
            "unavailable_reason": output["error"],
            "safety_barrier": None,
            "generation": generation_record,
            "provider_attempt": {
                "status": status,
                "run_path": run_path,
                "run_sha256": sha256_file(root / run_path),
                "prompt_path": prompt_path,
                "prompt_sha256": sha256_file(root / prompt_path),
                "provider_job_id": run.get("provider_job_id"),
                "provider_may_be_active": run.get("provider_may_be_active"),
                "submission_count": run.get("submission_count"),
                "error": output["error"],
                "automatic_paid_retry": False,
                "fallback": None,
                "prior_attempt": copy.deepcopy(entry.prior_attempt),
                "duplicate_risk_acceptance": copy.deepcopy(
                    output.get("duplicate_risk_acceptance")
                ),
            },
        }
    video = _reviewable_video(
        root=root,
        media_commit_sha=media_commit_sha,
        method="eliza-i2v",
        status=status,
        repository_path=output["video_path"],
        media=output["media"],
        contract_check=output["contract_check"],
        generation_record=generation_record,
    )
    qa = V6_VISUAL_QA.get(entry.evaluation_id)
    if qa is not None:
        if (
            status != "succeeded"
            or output["media"].get("sha256") != qa["video_sha256"]
        ):
            raise TuneV5OverlayError(
                f"Manual visual QA media binding changed: {entry.evaluation_id}"
            )
        video["qa"] = copy.deepcopy(qa)
    return video


def _retry_planning_record(
    entry: retry_generation.Entry,
    *,
    root: Path,
) -> dict[str, Any]:
    result_path = root / safe_relative(
        entry.result_path, label=f"retry result {entry.evaluation_id}", suffix=".json"
    )
    if sha256_file(result_path) != entry.result_sha256:
        raise TuneV5OverlayError(f"Retry planning result changed: {entry.evaluation_id}")
    result = read_json(result_path)
    analysis = result.get("analysis") if isinstance(result, dict) else None
    if not isinstance(analysis, dict):
        raise TuneV5OverlayError(f"Retry planning analysis missing: {entry.evaluation_id}")
    return {
        "run_id": entry.planning_run_id,
        "result_path": entry.result_path,
        "result_sha256": entry.result_sha256,
        "provenance": copy.deepcopy(entry.provenance),
        "structured_intent": copy.deepcopy(analysis.get("structured_intent")),
        "image_reading": analysis.get("image_reading"),
        "article_context": analysis.get("article_context"),
        "repair_feedback_path": entry.repair_feedback_path,
        "repair_feedback_sha256": entry.repair_feedback_sha256,
    }


def _v7_filter_video(
    output: dict[str, Any],
    case: dict[str, Any],
    *,
    root: Path,
    media_commit_sha: str,
) -> dict[str, Any]:
    status = output["status"]
    generation_record = {
        "origin": "regenerated-v7-filter-retry",
        "batch_id": V7_FILTER_BATCH_ID,
        "provider_run_id": output["provider_run_id"],
        "retry_reason": case["retry_reason"],
        "prompt_lineage_kind": "new-provenance-verified-lite-neutral-camera-only",
        "prompt_path": output["prompt_path"],
        "run_path": output["run_path"],
        "prior_attempt": copy.deepcopy(case["source_provider_attempt"]),
        "terminal_no_output_stop_applied": output.get(
            "terminal_no_output_stop_applied"
        ),
        "provider_terminal_diagnostics": copy.deepcopy(
            output.get("provider_terminal_diagnostics")
        ),
        "diagnostics_unavailable_upstream": output.get(
            "diagnostics_unavailable_upstream"
        ),
    }
    if status in {"provider-failed", "failed-pre-submit", "submit-unknown"}:
        run_path = safe_relative(
            output["run_path"], label="v7 failed run", suffix=".json"
        )
        prompt_path = safe_relative(
            output["prompt_path"], label="v7 failed prompt", suffix=".json"
        )
        run = read_json(root / run_path)
        return {
            "state": "unavailable",
            "status": "provider-unavailable",
            "recorded_status": status,
            "method": "eliza-i2v",
            "prompt_evaluated": False,
            "delivery": "unavailable",
            "url": None,
            "repository_video_path": None,
            "sha256": None,
            "bytes": None,
            "media": None,
            "contract_check": None,
            "unavailable_reason": output["error"],
            "safety_barrier": None,
            "generation": generation_record,
            "provider_attempt": {
                "status": status,
                "run_path": run_path,
                "run_sha256": sha256_file(root / run_path),
                "prompt_path": prompt_path,
                "prompt_sha256": sha256_file(root / prompt_path),
                "provider_job_id": run.get("provider_job_id"),
                "provider_may_be_active": run.get("provider_may_be_active"),
                "submission_count": run.get("submission_count"),
                "error": output["error"],
                "provider_terminal_diagnostics": copy.deepcopy(
                    output.get("provider_terminal_diagnostics")
                ),
                "diagnostics_unavailable_upstream": output.get(
                    "diagnostics_unavailable_upstream"
                ),
                "terminal_no_output_stop_applied": output.get(
                    "terminal_no_output_stop_applied"
                ),
                "automatic_paid_retry": False,
                "fallback": None,
                "prior_attempt": copy.deepcopy(case["source_provider_attempt"]),
            },
        }
    return _reviewable_video(
        root=root,
        media_commit_sha=media_commit_sha,
        method="eliza-i2v",
        status=status,
        repository_path=output["video_path"],
        media=output["media"],
        contract_check=output["contract_check"],
        generation_record=generation_record,
    )


def _v7_filter_planning_record(case: dict[str, Any]) -> dict[str, Any]:
    planning_record = case["planning"]
    return {
        "run_id": planning_record["run_id"],
        "result_path": planning_record["result_path"],
        "result_sha256": planning_record["result_sha256"],
        "provenance": copy.deepcopy(planning_record["provenance"]),
        "structured_intent": copy.deepcopy(planning_record["structured_intent"]),
        "image_reading": planning_record["image_reading"],
        "article_context": planning_record["article_context"],
        "repair_feedback_path": planning_record["repair_feedback_path"],
        "repair_feedback_sha256": planning_record["repair_feedback_sha256"],
    }


V8_UNAVAILABLE_REASON = (
    "3/3 additional Veo prompt experiments completed with no output "
    "(content may have been filtered)"
)


def _v8_experiment_video(
    outputs: list[dict[str, Any]],
    entries: list[v8_generation.Entry],
    prompt_case: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for output, entry in zip(outputs, entries, strict=True):
        run_path = safe_relative(
            output["run_path"],
            label=f"V8 run {entry.variant_id}",
            suffix=".json",
        )
        prompt_path = safe_relative(
            output["prompt_path"],
            label=f"V8 prompt {entry.variant_id}",
            suffix=".json",
        )
        run = read_json(root / run_path)
        attempts.append(
            {
                "experiment_id": entry.experiment_id,
                "variant_id": entry.variant_id,
                "controlled_factor": entry.controlled_factor,
                "rationale": entry.rationale,
                "positive_prompt": entry.positive_prompt,
                "provider_run_id": entry.provider_run_id,
                "status": "provider-failed",
                "run_path": run_path,
                "run_sha256": sha256_file(root / run_path),
                "prompt_path": prompt_path,
                "prompt_sha256": sha256_file(root / prompt_path),
                "provider_job_id": run["provider_job_id"],
                "provider_may_be_active": False,
                "submission_count": 1,
                "error": output["error"],
                "provider_terminal_diagnostics": copy.deepcopy(
                    output["provider_terminal_diagnostics"]
                ),
                "diagnostics_unavailable_upstream": output[
                    "diagnostics_unavailable_upstream"
                ],
                "terminal_no_output_stop_applied": True,
                "automatic_paid_retry": False,
                "fallback": None,
                "s3_upload": False,
            }
        )
    return {
        "state": "unavailable",
        "status": "provider-unavailable",
        "recorded_status": "provider-failed",
        "method": "eliza-i2v",
        "prompt_evaluated": False,
        "delivery": "unavailable",
        "url": None,
        "repository_video_path": None,
        "sha256": None,
        "bytes": None,
        "media": None,
        "contract_check": None,
        "unavailable_reason": V8_UNAVAILABLE_REASON,
        "safety_barrier": None,
        "generation": {
            "origin": "regenerated-v8-veo-prompt-experiment",
            "batch_id": V8_EXPERIMENT_BATCH_ID,
            "planning_batch_id": v8_planning.BATCH_ID,
            "prompt_manifest_path": V8_EXPERIMENT_PROMPT_MANIFEST_REL.as_posix(),
            "provider_run_ids": [entry.provider_run_id for entry in entries],
            "experiment_count": 3,
            "shared_seed": v8_planning.SHARED_PROVIDER_SEED,
            "changed_factor": "motion-only positive-prompt formulation",
            "displayed_tuned_prompt_is_prior_baseline": True,
            "prior_attempt": copy.deepcopy(prompt_case["source_provider_attempt"]),
        },
        "provider_attempt": {
            "status": "all-provider-failed",
            "attempt_count": 3,
            "terminal_no_output_count": 3,
            "attempts": attempts,
            "automatic_paid_retry": False,
            "fallback": None,
        },
    }


def _v8_prompt_experiment_record(
    prompt_case: dict[str, Any],
    entries: list[v8_generation.Entry],
) -> dict[str, Any]:
    experiments = prompt_case.get("experiments")
    if not isinstance(experiments, list) or len(experiments) != 3:
        raise TuneV5OverlayError("V8 prompt experiment case changed")
    return {
        "planning_batch_id": v8_planning.BATCH_ID,
        "generation_batch_id": V8_EXPERIMENT_BATCH_ID,
        "prompt_manifest_path": V8_EXPERIMENT_PROMPT_MANIFEST_REL.as_posix(),
        "prompt_manifest_sha256": V8_EXPERIMENT_EXPECTED_PROMPT_SHA256,
        "shared_seed": v8_planning.SHARED_PROVIDER_SEED,
        "fixed_source_sha256": v8_planning.CANONICAL_SOURCE_SHA256,
        "changed_factor": "motion-only positive-prompt formulation",
        "variant_order": [entry.variant_id for entry in entries],
        "displayed_tuned_prompt_is_prior_baseline": True,
        "experiments": copy.deepcopy(experiments),
    }


def build_live_manifest(
    evaluation_path: Path,
    media_commit_sha: str,
    *,
    root: Path = ROOT,
    prompt_manifest_path: Path | None = None,
    generation_manifest_path: Path | None = None,
    retry_generation_manifest_path: Path | None = None,
    v7_filter_generation_manifest_path: Path | None = None,
    v8_experiment_generation_manifest_path: Path | None = None,
    expected_v4_sha256: str = planning.EXPECTED_V4_MANIFEST_SHA256,
    expected_evaluation_sha256: str = planning.EXPECTED_EVALUATION_SHA256,
) -> dict[str, Any]:
    root = root.resolve()
    media_commit_sha = validate_commit_sha(media_commit_sha)
    v4, v4_targets, evaluations = _validated_v4_and_evaluations(
        root,
        evaluation_path,
        expected_v4_sha256=expected_v4_sha256,
        expected_evaluation_sha256=expected_evaluation_sha256,
    )
    prompt_manifest_path = prompt_manifest_path or (root / PROMPT_MANIFEST_REL)
    prompt_document = read_json(prompt_manifest_path)
    prompt_targets, prompt_sha256 = validate_prompt_manifest(
        prompt_document,
        path=prompt_manifest_path,
    )
    if retry_generation_manifest_path is None:
        candidate = root / RETRY_GENERATION_MANIFEST_REL
        retry_generation_manifest_path = candidate if candidate.is_file() else None
    retry_outputs: dict[str, dict[str, Any]] = {}
    retry_entries: dict[str, retry_generation.Entry] = {}
    retry_generation_sha256: str | None = None
    if retry_generation_manifest_path is not None:
        retry_document = read_json(retry_generation_manifest_path)
        retry_outputs, retry_entries, retry_generation_sha256 = (
            validate_retry_generation_manifest(
                retry_document,
                path=retry_generation_manifest_path,
                root=root,
            )
        )
    if v7_filter_generation_manifest_path is None:
        candidate = root / V7_FILTER_GENERATION_MANIFEST_REL
        if candidate.is_file():
            candidate_document = read_json(candidate)
            candidate_outputs = (
                candidate_document.get("outputs")
                if isinstance(candidate_document, dict)
                else None
            )
            candidate_status = (
                candidate_outputs[0].get("status")
                if isinstance(candidate_outputs, list)
                and len(candidate_outputs) == 1
                and isinstance(candidate_outputs[0], dict)
                else None
            )
            if candidate_status not in {
                "pending",
                "dry-run",
                "submitting",
                "submitted",
                "running",
            }:
                v7_filter_generation_manifest_path = candidate
    v7_filter_output: dict[str, Any] | None = None
    v7_filter_case: dict[str, Any] | None = None
    v7_filter_target: dict[str, Any] | None = None
    v7_filter_generation_sha256: str | None = None
    v7_filter_prompt_sha256: str | None = None
    if v7_filter_generation_manifest_path is not None:
        v7_filter_document = read_json(v7_filter_generation_manifest_path)
        (
            v7_filter_output,
            v7_filter_case,
            v7_filter_target,
            v7_filter_generation_sha256,
            v7_filter_prompt_sha256,
        ) = validate_v7_filter_generation_manifest(
            v7_filter_document,
            path=v7_filter_generation_manifest_path,
            root=root,
        )
    if v8_experiment_generation_manifest_path is None:
        candidate = root / V8_EXPERIMENT_GENERATION_MANIFEST_REL
        v8_experiment_generation_manifest_path = (
            candidate if candidate.is_file() else None
        )
    v8_experiment_outputs: list[dict[str, Any]] = []
    v8_experiment_entries: list[v8_generation.Entry] = []
    v8_experiment_prompt_case: dict[str, Any] | None = None
    v8_experiment_generation_sha256: str | None = None
    v8_experiment_prompt_sha256: str | None = None
    if v8_experiment_generation_manifest_path is not None:
        if (
            v7_filter_output is None
            or v7_filter_case is None
            or v7_filter_target is None
        ):
            raise TuneV5OverlayError(
                "V8 prompt experiment requires the validated V7 baseline attempt"
            )
        v8_experiment_document = read_json(v8_experiment_generation_manifest_path)
        (
            v8_experiment_outputs,
            v8_experiment_entries,
            v8_experiment_prompt_case,
            v8_experiment_generation_sha256,
            v8_experiment_prompt_sha256,
        ) = validate_v8_experiment_generation_manifest(
            v8_experiment_document,
            path=v8_experiment_generation_manifest_path,
            root=root,
        )
    generation_manifest_path = generation_manifest_path or (root / GENERATION_MANIFEST_REL)
    generation_document = read_json(generation_manifest_path)
    outputs, generation_sha256 = validate_generation_manifest(
        generation_document,
        path=generation_manifest_path,
        prompt_sha256=prompt_sha256,
        prompt_targets=prompt_targets,
        root=root,
        superseded_keys=(
            (
                set(retry_generation.EXPECTED_KEYS if retry_outputs else ())
                | ({V7_FILTER_EXPECTED_KEY} if v7_filter_output else set())
            )
        ),
    )
    retry_route_barrier = (
        retry_entries[retry_generation.SUBMIT_UNKNOWN_KEY].prior_attempt
        if retry_outputs
        else None
    )
    final_cases: list[dict[str, Any]] = []
    reused_count = 0
    regenerated_count = 0
    unavailable_count = 0
    method_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    generation_batch_counts: Counter[str] = Counter()
    for v4_case in v4["cases"]:
        case_id = str(v4_case["case_id"])
        final_targets: list[dict[str, Any]] = []
        planning_variants: dict[str, Any] = {}
        for v4_target in v4_case["targets"]:
            model_id = str(v4_target["model_id"])
            key = f"{case_id}::{model_id}"
            evaluation = evaluations.get(key)
            if key in planning.EXPECTED_REGENERATE_KEYS:
                prompt_case, prompt_target = prompt_targets[key]
                retry_entry = retry_entries.get(key)
                prompt_experiment_record: dict[str, Any] | None = None
                if key == V7_FILTER_EXPECTED_KEY and v8_experiment_outputs:
                    assert (
                        v7_filter_case is not None
                        and v7_filter_target is not None
                        and v8_experiment_prompt_case is not None
                    )
                    tuned = copy.deepcopy(v7_filter_target["tuned"])
                    tuned["video"] = _v8_experiment_video(
                        v8_experiment_outputs,
                        v8_experiment_entries,
                        v8_experiment_prompt_case,
                        root=root,
                    )
                    active_planning = _v7_filter_planning_record(v7_filter_case)
                    active_planning_batch_id = v7_planning.BATCH_ID
                    active_generation_batch_id = V8_EXPERIMENT_BATCH_ID
                    prompt_experiment_record = _v8_prompt_experiment_record(
                        v8_experiment_prompt_case,
                        v8_experiment_entries,
                    )
                    retry_iteration = {
                        "reason": (
                            "Three controlled motion-only prompt variants were "
                            "submitted after the V7 terminal no-output result."
                        ),
                        "prompt_lineage_kind": (
                            "v8-controlled-veo-motion-only-prompt-experiment"
                        ),
                        "prior_attempt": copy.deepcopy(
                            v8_experiment_prompt_case["source_provider_attempt"]
                        ),
                        "diagnosis": copy.deepcopy(
                            read_json(
                                root / V8_EXPERIMENT_PROMPT_MANIFEST_REL
                            ).get("diagnosis")
                        ),
                        "experiment_count": len(v8_experiment_outputs),
                    }
                elif key == V7_FILTER_EXPECTED_KEY and v7_filter_output is not None:
                    assert v7_filter_case is not None and v7_filter_target is not None
                    tuned = copy.deepcopy(v7_filter_target["tuned"])
                    tuned["video"] = _v7_filter_video(
                        v7_filter_output,
                        v7_filter_case,
                        root=root,
                        media_commit_sha=media_commit_sha,
                    )
                    active_planning = _v7_filter_planning_record(v7_filter_case)
                    active_planning_batch_id = v7_planning.BATCH_ID
                    active_generation_batch_id = V7_FILTER_BATCH_ID
                    retry_iteration = {
                        "reason": v7_filter_case["retry_reason"],
                        "prompt_lineage_kind": (
                            "new-provenance-verified-lite-neutral-camera-only"
                        ),
                        "prior_attempt": copy.deepcopy(
                            v7_filter_case["source_provider_attempt"]
                        ),
                        "diagnosis": copy.deepcopy(
                            read_json(root / V7_FILTER_PROMPT_MANIFEST_REL).get(
                                "diagnosis"
                            )
                        ),
                    }
                elif retry_entry is not None:
                    output = retry_outputs[key]
                    tuned = {
                        "execution_mode": "i2v",
                        "scene_plan": retry_entry.scene_plan,
                        "positive_prompt": retry_entry.positive_prompt,
                        "negative_prompt": None,
                        "runtime": copy.deepcopy(retry_entry.runtime),
                    }
                    tuned["video"] = _retry_video(
                        output,
                        retry_entry,
                        root=root,
                        media_commit_sha=media_commit_sha,
                        route_barrier=copy.deepcopy(retry_route_barrier),
                    )
                    active_planning = _retry_planning_record(retry_entry, root=root)
                    active_planning_batch_id = retry_entry.planning_batch_id
                    active_generation_batch_id = retry_generation.BATCH_ID
                    retry_iteration = {
                        "reason": retry_entry.retry_reason,
                        "prompt_lineage_kind": retry_entry.prompt_lineage_kind,
                        "prior_attempt": copy.deepcopy(retry_entry.prior_attempt),
                    }
                else:
                    output = outputs[key]
                    tuned = copy.deepcopy(prompt_target["tuned"])
                    tuned["video"] = _new_video(
                        output,
                        root=root,
                        media_commit_sha=media_commit_sha,
                    )
                    active_planning = copy.deepcopy(prompt_case["planning"])
                    active_planning_batch_id = planning.REPAIR_BATCH_ID
                    active_generation_batch_id = generation.BATCH_ID
                    retry_iteration = None
                target = {
                    key_name: copy.deepcopy(value)
                    for key_name, value in v4_target.items()
                    if key_name != "tuned"
                }
                target.update(
                    {
                        key_name: copy.deepcopy(prompt_target[key_name])
                        for key_name in (
                            "evaluation_id",
                            "selection_outcome",
                            "original_sheet_comment",
                            "review_note",
                        )
                        if key_name in prompt_target
                    }
                )
                target["tuned"] = tuned
                target["previous_tuned"] = copy.deepcopy(v4_target["tuned"])
                target["planning"] = active_planning
                if prompt_experiment_record is not None:
                    target["prompt_experiment"] = prompt_experiment_record
                iteration = {
                    "action": "regenerated-v5",
                    "review_scope": True,
                    "source_evaluation": {
                        "evaluation_id": key,
                        "outcome": prompt_target["selection_outcome"],
                        "note": prompt_target.get("review_note"),
                        "updated_at": evaluation.get("updated_at") if evaluation else None,
                    },
                    "planning_batch_id": active_planning_batch_id,
                    "generation_batch_id": active_generation_batch_id,
                }
                if retry_iteration is not None:
                    iteration["retry"] = retry_iteration
                target["iteration"] = iteration
                planning_variants[model_id] = copy.deepcopy(active_planning)
                regenerated_count += 1
            else:
                if not isinstance(evaluation, dict) or evaluation.get("outcome") != "helped":
                    raise TuneV5OverlayError(f"Non-selected target is not helped: {key}")
                target = {
                    key_name: copy.deepcopy(value)
                    for key_name, value in v4_target.items()
                    if key_name != "tuned"
                }
                tuned = copy.deepcopy(v4_target["tuned"])
                if tuned.get("execution_mode") != "i2v":
                    raise TuneV5OverlayError(f"Helped target is not I2V: {key}")
                tuned["video"] = _reused_video(
                    v4_target,
                    root=root,
                    media_commit_sha=media_commit_sha,
                )
                target["tuned"] = tuned
                target["planning"] = copy.deepcopy(v4_case["planning"])
                target["iteration"] = {
                    "action": "reused-helped",
                    "review_scope": False,
                    "source_evaluation": {
                        "evaluation_id": key,
                        "outcome": "helped",
                        "note": evaluation.get("note"),
                        "updated_at": evaluation.get("updated_at"),
                    },
                    "planning_batch_id": planning.V4_BATCH_ID,
                    "generation_batch_id": tuned["video"].get("generation", {}).get("batch_id"),
                }
                planning_variants[model_id] = copy.deepcopy(v4_case["planning"])
                reused_count += 1
            video = target["tuned"]["video"]
            method_counts[video["method"]] += 1
            model_counts[model_id] += 1
            if video["state"] == "unavailable":
                unavailable_count += 1
            generation_receipt = video.get("generation", {})
            generation_origin = generation_receipt.get("origin")
            if not isinstance(generation_origin, str) or not generation_origin:
                raise TuneV5OverlayError(f"Missing generation origin: {key}")
            generation_batch_id = generation_receipt.get("batch_id")
            generation_batch_counts[
                generation_batch_id
                if isinstance(generation_batch_id, str) and generation_batch_id
                else generation_origin
            ] += 1
            final_targets.append(target)
        final_case = {
            key_name: copy.deepcopy(value)
            for key_name, value in v4_case.items()
            if key_name not in {
                "planning",
                "accepted_sibling_model_ids",
                "hypothesis",
                "targets",
            }
        }
        final_case["planning_by_model"] = planning_variants
        final_case["targets"] = final_targets
        final_cases.append(final_case)
    if (
        reused_count != 37
        or regenerated_count != 28
        or sum(len(case["targets"]) for case in final_cases) != 65
        or method_counts != Counter({"eliza-i2v": 65})
        or model_counts != Counter({
            "alibaba/wan-2.2": 24,
            "alibaba/wan-2.7": 16,
            "google/veo-3.1-lite": 25,
        })
    ):
        raise TuneV5OverlayError("Final v5 review matrix changed")
    return {
        "schema_version": 2,
        "manifest_role": "clipmaker-lite-tune-review",
        "ticket": TICKET,
        "batch_id": REVIEW_BATCH_ID,
        "agent_id": AGENT_ID,
        "contract_versions": ["2.2.0", planning.EXPECTED_CONTRACT_VERSION],
        "generated_at": transport.utc_now(),
        "scope": {
            "case_count": 36,
            "target_count": 65,
            "review_target_count": 28,
            "reused_helped_target_count": 37,
            "regenerated_target_count": 28,
            "retry_target_count": len(
                set(retry_outputs)
                | (
                    {V7_FILTER_EXPECTED_KEY}
                    if v7_filter_output is not None or v8_experiment_outputs
                    else set()
                )
            ),
            "retry_attempt_count": (
                len(retry_outputs)
                + int(v7_filter_output is not None)
                + len(v8_experiment_outputs)
            ),
            "available_video_count": 65 - unavailable_count,
            "unavailable_video_count": unavailable_count,
            "execution_mode_counts": {"i2v": 65},
            "video_method_counts": {"eliza-i2v": 65},
            "new_video_generation": True,
            "new_s3_upload": False,
            "generated_video_delivery": "repository-raw",
            "media_commit_sha": media_commit_sha,
        },
        "lineage": {
            "evaluation_export": {
                "source_name": evaluation_path.name,
                "sha256": expected_evaluation_sha256,
            },
            "v4_manifest": {
                "path": V4_SNAPSHOT_REL.as_posix(),
                "sha256": expected_v4_sha256,
                "current_runner_reverification": False,
            },
            "v5_prompt_manifest": {
                "path": relative_path(prompt_manifest_path, root),
                "sha256": prompt_sha256,
            },
            "v5_generation_manifest": {
                "path": relative_path(generation_manifest_path, root),
                "sha256": generation_sha256,
            },
            **(
                {
                    "v7_retry_prompt_manifest": {
                        "path": retry_generation.VEO_PROMPT_MANIFEST_REL.as_posix(),
                        "sha256": sha256_file(
                            root / retry_generation.VEO_PROMPT_MANIFEST_REL
                        ),
                    },
                    "v6_retry_generation_manifest": {
                        "path": relative_path(retry_generation_manifest_path, root),
                        "sha256": retry_generation_sha256,
                        "superseded_v5_target_count": len(retry_outputs),
                    },
                }
                if retry_outputs and retry_generation_manifest_path is not None
                else {}
            ),
            **(
                {
                    "v7_filter_retry_prompt_manifest": {
                        "path": V7_FILTER_PROMPT_MANIFEST_REL.as_posix(),
                        "sha256": v7_filter_prompt_sha256,
                    },
                    "v7_filter_retry_generation_manifest": {
                        "path": relative_path(
                            v7_filter_generation_manifest_path, root
                        ),
                        "sha256": v7_filter_generation_sha256,
                        "superseded_v6_target_count": 1,
                    },
                }
                if v7_filter_output is not None
                and v7_filter_generation_manifest_path is not None
                else {}
            ),
            **(
                {
                    "v8_prompt_experiment_manifest": {
                        "path": V8_EXPERIMENT_PROMPT_MANIFEST_REL.as_posix(),
                        "sha256": v8_experiment_prompt_sha256,
                        "experiment_count": len(v8_experiment_outputs),
                    },
                    "v8_generation_manifest": {
                        "path": relative_path(
                            v8_experiment_generation_manifest_path, root
                        ),
                        "sha256": v8_experiment_generation_sha256,
                        "experiment_count": len(v8_experiment_outputs),
                        "superseded_v7_target_count": 1,
                    },
                }
                if v8_experiment_outputs
                and v8_experiment_generation_manifest_path is not None
                else {}
            ),
            "media_commit_sha": media_commit_sha,
        },
        "summary": {
            "iteration_action_counts": {
                "reused-helped": 37,
                "regenerated-v5": 28,
            },
            "model_counts": dict(model_counts),
            "video_method_counts": dict(method_counts),
            "generation_batch_counts": dict(generation_batch_counts),
            "unavailable_video_count": unavailable_count,
        },
        "cases": final_cases,
    }


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneV5OverlayError(f"Path is outside workspace: {path}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--media-commit-sha", required=True)
    parser.add_argument("--output", type=Path, default=LIVE_MANIFEST_REL)
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = build_live_manifest(
            args.evaluation,
            args.media_commit_sha,
            root=root,
        )
        output = args.output if args.output.is_absolute() else root / args.output
        relative_path(output, root)
        transport.atomic_write_json(output, manifest)
        print(relative_path(output, root), flush=True)
        return 0
    except TuneV5OverlayError as exc:
        print(f"Tune v5 media overlay error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
