#!/usr/bin/env python3
"""Merge the final Tune review set from v4, v5 and the immutable v6 retry.

The merger is deterministic and performs no provider, S3 or GitHub call.  It
reads the byte-frozen v4 manifest snapshot, the SHA-bound review export, the
verified planning manifests and the immutable v5/v6 generation receipts.
Helped v4 videos are reused byte-for-byte; v6 supersedes only its exact eight
retry targets.  Every reviewable MP4 is served from an immutable raw GitHub
URL pinned to the operator-supplied media commit.  Provider failures and the
Wan 2.2 route-safety withholding remain explicit unavailable I2V attempts and
never receive a compositor fallback.
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
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
REVIEW_BATCH_ID = "promopages-10060-tune-review-20260811-v6"
V4_SNAPSHOT_REL = planning.V4_SNAPSHOT_REL
PROMPT_MANIFEST_REL = generation.PROMPT_MANIFEST_REL
GENERATION_MANIFEST_REL = generation.GENERATION_MANIFEST_REL
RETRY_GENERATION_MANIFEST_REL = retry_generation.GENERATION_MANIFEST_REL
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
        ):
            raise TuneV5OverlayError(f"v6 retry receipt binding changed: {key}")
        withheld_status = retry_generation.ROUTE_SAFETY_WITHHELD_STATUSES.get(key)
        if withheld_status is not None:
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
        if (
            run.get("request") != request
            or run.get("request_sha256") != request_sha256
            or run.get("request_fingerprint_version")
            != transport.REQUEST_FINGERPRINT_VERSION
            or run.get("provider_may_be_active") is not False
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
        elif status in {"provider-failed", "failed-pre-submit"}:
            if (
                run.get("submission_count") not in {0, 1}
                or output.get("media") is not None
                or output.get("contract_check") is not None
                or (root / safe_relative(output.get("video_path"), label=f"{key} video_path")).exists()
                or not isinstance(output.get("error"), str)
                or not output["error"].strip()
                or run.get("completed_at") is None
            ):
                raise TuneV5OverlayError(f"v6 retry terminal failure audit is invalid: {key}")
        else:
            raise TuneV5OverlayError(f"v6 retry output is not terminal: {key} / {status}")
        by_key[key] = output
        model_counts[entry.model_id] += 1
    if set(by_key) != retry_generation.EXPECTED_KEYS or dict(model_counts) != retry_generation.EXPECTED_BY_MODEL:
        raise TuneV5OverlayError("v6 retry terminal output matrix changed")
    return by_key, entries, sha256_file(path)


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
    return _reviewable_video(
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
    return _reviewable_video(
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
    }
    withheld_status = retry_generation.ROUTE_SAFETY_WITHHELD_STATUSES.get(
        entry.evaluation_id
    )
    if withheld_status is not None:
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
    if status in {"provider-failed", "failed-pre-submit"}:
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
                "submission_count": run.get("submission_count"),
                "error": output["error"],
                "automatic_paid_retry": False,
                "fallback": None,
                "prior_attempt": copy.deepcopy(entry.prior_attempt),
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


def build_live_manifest(
    evaluation_path: Path,
    media_commit_sha: str,
    *,
    root: Path = ROOT,
    prompt_manifest_path: Path | None = None,
    generation_manifest_path: Path | None = None,
    retry_generation_manifest_path: Path | None = None,
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
    generation_manifest_path = generation_manifest_path or (root / GENERATION_MANIFEST_REL)
    generation_document = read_json(generation_manifest_path)
    outputs, generation_sha256 = validate_generation_manifest(
        generation_document,
        path=generation_manifest_path,
        prompt_sha256=prompt_sha256,
        prompt_targets=prompt_targets,
        root=root,
        superseded_keys=(
            retry_generation.EXPECTED_KEYS if retry_outputs else frozenset()
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
                if retry_entry is not None:
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
            "retry_target_count": len(retry_outputs),
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
            "media_commit_sha": media_commit_sha,
        },
        "summary": {
            "iteration_action_counts": {
                "reused-helped": 37,
                "regenerated-v5": 28,
            },
            "model_counts": dict(model_counts),
            "video_method_counts": dict(method_counts),
            "generation_batch_counts": {
                "reused-helped-v4": 37,
                generation.BATCH_ID: 28 - len(retry_outputs),
                **(
                    {retry_generation.BATCH_ID: len(retry_outputs)}
                    if retry_outputs
                    else {}
                ),
            },
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
