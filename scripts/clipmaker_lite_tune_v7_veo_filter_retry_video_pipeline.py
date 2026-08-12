#!/usr/bin/env python3
"""Run one immutable, policy-compliant Veo retry for Tune case 07#06.

The retry uses the canonical full source and a provenance-verified Clipmaker
Lite motion-only prompt.  It does not crop, blur, composite, disable provider
safety, or fall back to another model.  One new provider run ID may submit at
most once; a terminal no-output result permanently stops same-run retries.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as pools  # noqa: E402
from scripts import clipmaker_lite_tune_v7_filter_retry_planning as planning  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
BATCH_ID = "promopages-10060-tune-videos-20260812-v7"
MANIFEST_ROLE = "clipmaker-lite-tune-v7-filter-retry-video-generation"
PROMPT_MANIFEST_REL = planning.PROMPT_MANIFEST_REL
PROMPT_MANIFEST_SHA256 = (
    "71bf815a44e88a0f7cf08dfa25f7f46ad54e5de36f12f85e738d74917a9f6c08"
)
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
MODEL_ID = "google/veo-3.1-lite"
MODEL_DIRECTORY = "veo-3.1-lite"
EXPECTED_KEY = "07#06::google/veo-3.1-lite"
SEED = 967732034
ACCOUNTING_BUDGET_USD = Decimal("0.35")
TERMINAL_FAILURES = frozenset(transport.TERMINAL_FAILURE)
TERMINAL_SUCCESSES = frozenset(transport.TERMINAL_SUCCESS)
BLOCKED_STATUSES = {
    "submitting",
    "submit-unknown",
    "provider-failed",
    "failed-pre-submit",
    "verification-failed",
    "stale",
    "failed",
}
DIAGNOSTIC_FIELDS = (
    "id",
    "generation_id",
    "request_id",
    "status",
    "error",
    "support_code",
    "raiFilteredReason",
    "blockedReason",
)


class TuneV7VeoRetryError(RuntimeError):
    """The single-target retry failed an immutable or paid-safety guard."""


@dataclass(frozen=True)
class Entry:
    case_id: str
    sheet_row: int
    article_slug: str
    image_id: str
    source_path: str
    source_url: str
    source_sha256: str
    width: int
    height: int
    planning_run_id: str
    result_path: str
    result_sha256: str
    repair_feedback_path: str
    repair_feedback_sha256: str
    scene_plan: str
    positive_prompt: str
    runtime: dict[str, Any]
    provenance: dict[str, Any]
    diagnosis: dict[str, Any]
    prior_attempt: dict[str, Any]

    @property
    def evaluation_id(self) -> str:
        return EXPECTED_KEY

    @property
    def provider_run_id(self) -> str:
        return (
            f"{BATCH_ID}-{self.article_slug}-{self.image_id}-veo-3-1-lite"
        )


@dataclass(frozen=True)
class ProviderOperations:
    eliza_headers: Callable[[], dict[str, str]]
    http_json: Callable[..., Any]
    http_download: Callable[..., None]
    media_probe: Callable[[Path], dict[str, Any]]
    sleep: Callable[[float], None] = time.sleep


def default_provider_operations() -> ProviderOperations:
    return ProviderOperations(
        eliza_headers=transport.eliza_headers,
        http_json=transport.http_json,
        http_download=transport.http_download,
        media_probe=transport.ffprobe_media,
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TuneV7VeoRetryError(f"Invalid or missing JSON: {path}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise TuneV7VeoRetryError(f"Required file is missing: {path}") from exc
    return digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneV7VeoRetryError(f"Artifact is outside workspace: {path}") from exc


def load_inventory(*, root: Path = ROOT) -> Entry:
    root = root.resolve()
    path = root / PROMPT_MANIFEST_REL
    if sha256_file(path) != PROMPT_MANIFEST_SHA256:
        raise TuneV7VeoRetryError("V7 prompt manifest digest changed")
    document = read_json(path)
    if (
        document.get("schema_version") != 1
        or document.get("manifest_role")
        != "clipmaker-lite-tune-v7-filter-retry-planning"
        or document.get("batch_id") != planning.BATCH_ID
        or document.get("contract_version") != planning.EXPECTED_CONTRACT_VERSION
        or document.get("scope", {}).get("target_count") != 1
        or document.get("scope", {}).get("canonical_full_source_only") is not True
        or document.get("scope", {}).get("source_transform") is not None
        or document.get("scope", {}).get("disable_provider_safety_filters") is not False
        or document.get("scope", {}).get("fallback") is not False
        or document.get("scope", {}).get("compositor") is not False
        or not isinstance(document.get("cases"), list)
        or len(document["cases"]) != 1
    ):
        raise TuneV7VeoRetryError("Unexpected V7 prompt manifest")
    case = document["cases"][0]
    targets = case.get("targets")
    source = case.get("source")
    planning_record = case.get("planning")
    if (
        case.get("case_id") != planning.CASE_ID
        or not isinstance(targets, list)
        or len(targets) != 1
        or targets[0].get("evaluation_id") != EXPECTED_KEY
        or targets[0].get("model_id") != MODEL_ID
        or not isinstance(source, dict)
        or source.get("sha256") != planning.CANONICAL_SOURCE_SHA256
        or source.get("width") != 2400
        or source.get("height") != 1600
        or not isinstance(planning_record, dict)
        or not planning.result_is_verified(case, root=root)
    ):
        raise TuneV7VeoRetryError("V7 case/source/provenance binding changed")
    result = read_json(root / planning_record["result_path"])
    model = planning.validate_result(result, case)
    target = targets[0]
    tuned = target.get("tuned")
    if (
        not isinstance(tuned, dict)
        or tuned.get("execution_mode") != "i2v"
        or tuned.get("positive_prompt") != planning.EXACT_POSITIVE_PROMPT
        or tuned.get("positive_prompt") != model.get("positive_prompt")
        or tuned.get("negative_prompt") is not None
        or tuned.get("runtime") != model.get("runtime")
    ):
        raise TuneV7VeoRetryError("V7 provider prompt binding changed")
    diagnosis = document.get("diagnosis")
    if (
        not isinstance(diagnosis, dict)
        or diagnosis.get("type") != "suspected_source_filter"
        or diagnosis.get("active_source_sha256") != planning.CANONICAL_SOURCE_SHA256
        or diagnosis.get("active_source_transform") is not None
        or diagnosis.get("person_preserving_provider_failures_at_least", 0) < 11
    ):
        raise TuneV7VeoRetryError("V7 filter diagnosis changed")
    prior = case.get("source_provider_attempt")
    if (
        not isinstance(prior, dict)
        or prior.get("status") != "provider-failed"
        or prior.get("provider_may_be_active") is not False
        or not isinstance(prior.get("provider_job_id"), str)
        or not prior["provider_job_id"]
        or sha256_file(root / prior["run_path"]) != prior.get("run_sha256")
    ):
        raise TuneV7VeoRetryError("V7 prior terminal attempt changed")
    return Entry(
        case_id=case["case_id"],
        sheet_row=int(target["sheet_row"]),
        article_slug=case["article_slug"],
        image_id=str(source["image_id"]),
        source_path=source["path"],
        source_url=source["url"],
        source_sha256=source["sha256"],
        width=int(source["width"]),
        height=int(source["height"]),
        planning_run_id=planning_record["run_id"],
        result_path=planning_record["result_path"],
        result_sha256=planning_record["result_sha256"],
        repair_feedback_path=planning_record["repair_feedback_path"],
        repair_feedback_sha256=planning_record["repair_feedback_sha256"],
        scene_plan=model["scene_plan"],
        positive_prompt=model["positive_prompt"],
        runtime=copy.deepcopy(model["runtime"]),
        provenance=copy.deepcopy(planning_record["provenance"]),
        diagnosis=copy.deepcopy(diagnosis),
        prior_attempt=copy.deepcopy(prior),
    )


def provider_sample(entry: Entry) -> dict[str, Any]:
    return {
        "sample_id": f"{entry.article_slug}-{entry.image_id}",
        "article_slug": entry.article_slug,
        "image_id": entry.image_id,
        "image_number": entry.image_id,
        "source_path": entry.source_path,
        "source_url": entry.source_url,
        "sha256": entry.source_sha256,
        "width": entry.width,
        "height": entry.height,
    }


def provider_prompt(entry: Entry) -> dict[str, Any]:
    return {
        "sample_id": f"{entry.article_slug}-{entry.image_id}",
        "model_id": MODEL_ID,
        "target_duration_seconds": 4,
        "positive_prompt": entry.positive_prompt,
        "negative_prompt": None,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
    }


def provider_request(entry: Entry) -> dict[str, Any]:
    request = transport.build_request_preview(
        provider_sample(entry), provider_prompt(entry)
    )
    request["seed"] = SEED
    expected = {
        "model": MODEL_ID,
        "prompt": planning.EXACT_POSITIVE_PROMPT,
        "duration": 4,
        "resolution": "1080p",
        "aspect_ratio": "16:9",
        "seed": SEED,
        "generate_audio": False,
        "frame_images": [
            {
                "type": "image_url",
                "image_url": {"url": entry.source_url},
                "frame_type": "first_frame",
            }
        ],
        "provider": {
            "options": {
                "google-vertex": {"parameters": {"enhancePrompt": True}}
            }
        },
    }
    if request != expected:
        raise TuneV7VeoRetryError("V7 wire request changed")
    return request


def artifact_paths(entry: Entry, output_root: Path = ROOT) -> dict[str, Path]:
    base = (
        output_root
        / BATCH_ROOT_REL
        / "videos"
        / entry.article_slug
        / MODEL_DIRECTORY
    )
    return {
        "directory": base,
        "prompt": base / f"{entry.image_id}.prompt.json",
        "run": base / f"{entry.image_id}.run.json",
        "video": base / f"{entry.image_id}.mp4",
    }


def prompt_artifact(entry: Entry) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v7-filter-retry-video-prompt",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "evaluation_id": entry.evaluation_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": MODEL_ID,
        "execution_mode": "i2v",
        "canonical_source": {
            "path": entry.source_path,
            "url": entry.source_url,
            "sha256": entry.source_sha256,
            "width": entry.width,
            "height": entry.height,
            "transform": None,
        },
        "scene_plan": entry.scene_plan,
        "prompt": {
            "positive": entry.positive_prompt,
            "positive_utf8_sha256": hashlib.sha256(
                entry.positive_prompt.encode("utf-8")
            ).hexdigest(),
            "negative": None,
            "rewritten_by_provider_coordinator": False,
        },
        "runtime": copy.deepcopy(entry.runtime),
        "wire_request": provider_request(entry),
        "planning": {
            "batch_id": planning.BATCH_ID,
            "run_id": entry.planning_run_id,
            "result_path": entry.result_path,
            "result_sha256": entry.result_sha256,
            "prompt_manifest_path": PROMPT_MANIFEST_REL.as_posix(),
            "prompt_manifest_sha256": PROMPT_MANIFEST_SHA256,
            "repair_feedback_path": entry.repair_feedback_path,
            "repair_feedback_sha256": entry.repair_feedback_sha256,
            "provenance": copy.deepcopy(entry.provenance),
        },
        "diagnosis": copy.deepcopy(entry.diagnosis),
        "prior_attempt": copy.deepcopy(entry.prior_attempt),
        "policy": {
            "new_immutable_provider_run": True,
            "one_paid_submit": True,
            "terminal_no_output_stops_same_source_prompt_retry": True,
            "automatic_paid_retry": False,
            "fallback": None,
            "compositor": False,
            "source_transform": None,
            "disable_provider_safety_filters": False,
            "s3_upload": False,
        },
        "bindings": {
            "generation_routes_path": ROUTES_REL.as_posix(),
            "generation_routes_sha256": sha256_file(ROOT / ROUTES_REL),
        },
    }


def _initial_run(entry: Entry, paths: dict[str, Path], output_root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v7-filter-retry-video-run",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "evaluation_id": entry.evaluation_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": MODEL_ID,
        "execution_mode": "i2v",
        "adapter": "eliza-openrouter",
        "prompt_path": relative(paths["prompt"], output_root),
        "output_path": relative(paths["video"], output_root),
        "status": "pending",
        "request": None,
        "request_sha256": None,
        "request_fingerprint_version": None,
        "provider_job_id": None,
        "submitted_at": None,
        "completed_at": None,
        "provider_may_be_active": False,
        "source_preflight": None,
        "provider_response": None,
        "provider_terminal_diagnostics": None,
        "diagnostics_unavailable_upstream": None,
        "terminal_no_output_stop_applied": False,
        "media": None,
        "contract_check": None,
        "error": None,
        "submission_count": 0,
        "budget_reservation_usd": 0.35,
        "new_immutable_provider_run": True,
        "automatic_paid_retry": False,
        "fallback": None,
        "compositor": False,
        "source_transform": None,
        "disable_provider_safety_filters": False,
        "s3_upload": False,
    }


def materialize_entry(entry: Entry, *, output_root: Path = ROOT) -> dict[str, Any]:
    paths = artifact_paths(entry, output_root)
    paths["directory"].mkdir(parents=True, exist_ok=True)
    expected_prompt = prompt_artifact(entry)
    if paths["prompt"].exists():
        if read_json(paths["prompt"]) != expected_prompt:
            raise TuneV7VeoRetryError("Immutable V7 prompt artifact changed")
    else:
        transport.atomic_write_json(paths["prompt"], expected_prompt)
    expected_run = _initial_run(entry, paths, output_root)
    immutable_keys = (
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
    if paths["run"].exists():
        run = read_json(paths["run"])
        if any(run.get(key) != expected_run[key] for key in immutable_keys):
            raise TuneV7VeoRetryError("Immutable V7 run identity changed")
        if run.get("submission_count") not in {0, 1}:
            raise TuneV7VeoRetryError("Invalid V7 submission count")
    else:
        transport.atomic_write_json(paths["run"], expected_run)
    return {
        "entry": entry,
        "sample": provider_sample(entry),
        "prompt": provider_prompt(entry),
        "paths": paths,
    }


def _sanitize_terminal_response(payload: Any) -> dict[str, Any]:
    outer = payload if isinstance(payload, dict) else {}
    nested = outer.get("response") if isinstance(outer.get("response"), dict) else outer
    values = {key: nested.get(key) for key in DIAGNOSTIC_FIELDS if nested.get(key) is not None}
    if outer.get("request_id") is not None:
        values["request_id"] = outer.get("request_id")
    sanitized = {
        key: transport.safe_error(value) if isinstance(value, str) else value
        for key, value in values.items()
    }
    safety_fields = ("support_code", "raiFilteredReason", "blockedReason")
    sanitized["diagnostics_unavailable_upstream"] = not any(
        sanitized.get(key) not in {None, ""} for key in safety_fields
    )
    return sanitized


def _persist(path: Path, run: dict[str, Any]) -> None:
    transport.atomic_write_json(path, run)


def _verify_media(row: dict[str, Any], run: dict[str, Any], operations: ProviderOperations) -> int:
    try:
        media = operations.media_probe(row["paths"]["video"])
        check = transport.assess_contract(MODEL_ID, media, 4)
    except Exception as exc:  # noqa: BLE001
        run.update(
            {
                "status": "verification-failed",
                "completed_at": transport.utc_now(),
                "provider_may_be_active": False,
                "error": transport.safe_error(exc),
            }
        )
        _persist(row["paths"]["run"], run)
        return 1
    status = "succeeded" if check.get("conforms") is True else "verification-failed"
    warnings = check.get("warnings") or []
    run.update(
        {
            "status": status,
            "completed_at": transport.utc_now(),
            "provider_may_be_active": False,
            "media": media,
            "contract_check": check,
            "error": None
            if status == "succeeded"
            else "Media contract warnings: " + "; ".join(warnings),
        }
    )
    _persist(row["paths"]["run"], run)
    return 0 if status == "succeeded" else 1


def run_provider_worker(
    entry: Entry,
    *,
    dry_run: bool,
    timeout: int,
    poll_interval: float,
    output_root: Path = ROOT,
    operations: ProviderOperations | None = None,
) -> int:
    operations = operations or default_provider_operations()
    row = materialize_entry(entry, output_root=output_root)
    paths = row["paths"]
    run = read_json(paths["run"])
    request = provider_request(entry)
    fingerprint = transport.request_fingerprint(request, row["sample"])
    status = str(run.get("status"))
    if status in {"succeeded", "verification-failed"}:
        if (
            run.get("request") != request
            or run.get("request_sha256") != fingerprint
            or run.get("submission_count") != 1
            or not paths["video"].is_file()
        ):
            raise TuneV7VeoRetryError("Terminal V7 media binding changed")
        return 0 if status == "succeeded" else 1
    if status in BLOCKED_STATUSES:
        return 1
    resume = status in {"submitted", "running"}
    if resume and (
        run.get("submission_count") != 1
        or not run.get("provider_job_id")
        or run.get("request") != request
        or run.get("request_sha256") != fingerprint
    ):
        raise TuneV7VeoRetryError("Active V7 job lost immutable request binding")
    if not resume and run.get("submission_count") != 0:
        raise TuneV7VeoRetryError("V7 provider run already consumed its submit")
    if not resume:
        try:
            preflight = pools.provider_input_dimension_preflight(row["sample"], MODEL_ID)
        except pools.ProviderInputDimensionError as exc:
            run.update(
                {
                    "status": "failed-pre-submit",
                    "request": request,
                    "request_sha256": fingerprint,
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                    "source_preflight": exc.evidence,
                    "completed_at": transport.utc_now(),
                    "provider_may_be_active": False,
                    "error": transport.safe_error(exc),
                }
            )
            _persist(paths["run"], run)
            return 1
        run.update(
            {
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "source_preflight": preflight,
                "error": None,
            }
        )
        if dry_run:
            run.update({"status": "dry-run", "provider_may_be_active": False})
            _persist(paths["run"], run)
            return 0
        run.update(
            {
                "status": "submitting",
                "submission_count": 1,
                "provider_may_be_active": True,
            }
        )
        _persist(paths["run"], run)
        try:
            headers = operations.eliza_headers()
            response = operations.http_json(
                "POST",
                transport.generation_route_url(
                    transport.route_for_model(MODEL_ID)["default_base_url"],
                    MODEL_ID,
                    "submit",
                ),
                request,
                headers=headers,
                timeout=120,
            )
            job_id = transport.find_job_id(response)
            if not job_id:
                raise transport.PipelineError("OpenRouter submit response has no job ID")
        except transport.PreSubmitRejectedError as exc:
            run.update(
                {
                    "status": "failed-pre-submit",
                    "completed_at": transport.utc_now(),
                    "provider_may_be_active": False,
                    "error": f"provider submit: {transport.safe_error(exc)}",
                }
            )
            _persist(paths["run"], run)
            return 1
        except Exception as exc:  # noqa: BLE001 - POST outcome is ambiguous
            run.update(
                {
                    "status": "submit-unknown",
                    "completed_at": None,
                    "provider_may_be_active": True,
                    "error": f"provider submit: {transport.safe_error(exc)}",
                }
            )
            _persist(paths["run"], run)
            return 1
        run.update(
            {
                "status": "submitted",
                "provider_job_id": str(job_id),
                "submitted_at": transport.utc_now(),
                "provider_may_be_active": True,
                "provider_response": _sanitize_terminal_response(response),
            }
        )
        _persist(paths["run"], run)
    else:
        headers = operations.eliza_headers()
        job_id = str(run["provider_job_id"])

    base_url = transport.route_for_model(MODEL_ID)["default_base_url"]
    deadline = time.monotonic() + timeout
    terminal_payload: Any = None
    try:
        while time.monotonic() < deadline:
            payload = operations.http_json(
                "GET",
                transport.generation_route_url(
                    base_url, MODEL_ID, "status_template", job_id=str(job_id)
                ),
                headers=headers,
                timeout=120,
            )
            provider_status = transport.find_status(payload)
            if provider_status in TERMINAL_FAILURES:
                terminal_payload = payload
                break
            if provider_status in TERMINAL_SUCCESSES or (
                transport.find_video_url(payload)
                and provider_status not in TERMINAL_FAILURES
            ):
                terminal_payload = payload
                break
            run.update({"status": "running", "provider_may_be_active": True})
            _persist(paths["run"], run)
            operations.sleep(poll_interval)
        if terminal_payload is None:
            raise transport.PipelineError(
                f"Eliza/OpenRouter job {job_id} did not finish within {timeout} seconds"
            )
    except Exception as exc:  # noqa: BLE001 - same submitted job remains resumable
        run.update(
            {
                "status": "submitted",
                "provider_may_be_active": True,
                "error": f"provider poll: {transport.safe_error(exc)}",
            }
        )
        _persist(paths["run"], run)
        return 1

    diagnostics = _sanitize_terminal_response(terminal_payload)
    provider_status = transport.find_status(terminal_payload)
    if provider_status in TERMINAL_FAILURES:
        detail = transport.find_error_detail(terminal_payload) or "provider terminal failure"
        no_output = "no output" in str(detail).lower()
        run.update(
            {
                "status": "provider-failed",
                "completed_at": transport.utc_now(),
                "provider_may_be_active": False,
                "provider_terminal_diagnostics": diagnostics,
                "diagnostics_unavailable_upstream": diagnostics[
                    "diagnostics_unavailable_upstream"
                ],
                "terminal_no_output_stop_applied": no_output,
                "error": f"provider terminal: {transport.safe_error(detail)}",
            }
        )
        _persist(paths["run"], run)
        return 1

    run.update(
        {
            "status": "running",
            "provider_may_be_active": True,
            "provider_terminal_diagnostics": diagnostics,
            "diagnostics_unavailable_upstream": diagnostics[
                "diagnostics_unavailable_upstream"
            ],
        }
    )
    _persist(paths["run"], run)
    try:
        operations.http_download(
            transport.generation_route_url(
                base_url, MODEL_ID, "content_template", job_id=str(job_id)
            ),
            paths["video"],
            headers=headers,
            timeout=600,
        )
    except Exception as exc:  # noqa: BLE001 - submitted job may still be downloadable
        run.update(
            {
                "status": "submitted",
                "provider_may_be_active": True,
                "error": f"provider download: {transport.safe_error(exc)}",
            }
        )
        _persist(paths["run"], run)
        return 1
    return _verify_media(row, run, operations)


def generation_manifest_document(
    entry: Entry,
    *,
    output_root: Path,
    invocation: dict[str, Any] | None,
) -> dict[str, Any]:
    paths = artifact_paths(entry, output_root)
    run = read_json(paths["run"])
    status = str(run.get("status"))
    return {
        "schema_version": 1,
        "manifest_role": MANIFEST_ROLE,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": transport.utc_now(),
        "scope": {
            "expected_i2v_outputs": 1,
            "model_counts": {MODEL_ID: 1},
            "prompt_batch_id": planning.BATCH_ID,
            "prompt_manifest_path": PROMPT_MANIFEST_REL.as_posix(),
            "prompt_manifest_sha256": PROMPT_MANIFEST_SHA256,
            "canonical_full_source_only": True,
            "source_transform": None,
            "disable_provider_safety_filters": False,
            "compositor_outputs": 0,
            "fallback_outputs": 0,
            "s3_upload": False,
            "delivery": "repository-files",
        },
        "budget": {
            "currency": "USD",
            "hard_incremental_budget_cap_usd": 0.35,
            "reserved_output_count": 1,
            "accounting_cost_per_output_usd": 0.35,
            "maximum_estimated_cost_usd": 0.35,
            "provider_unit_costs_asserted": False,
            "one_submit_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
        },
        "policy": {
            "terminal_no_output_stops_same_source_prompt_retry": True,
            "automatic_paid_retry": False,
            "fallback": False,
            "compositor": False,
            "disable_provider_safety_filters": False,
        },
        "scheduling": {
            "one_paid_submission_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
            "fallback": False,
        },
        "last_invocation": copy.deepcopy(invocation),
        "summary": {status: 1},
        "outputs": [
            {
                "provider_run_id": entry.provider_run_id,
                "evaluation_id": entry.evaluation_id,
                "case_id": entry.case_id,
                "sheet_row": entry.sheet_row,
                "article_slug": entry.article_slug,
                "image_id": entry.image_id,
                "model_id": MODEL_ID,
                "execution_mode": "i2v",
                "status": status,
                "prompt_path": relative(paths["prompt"], output_root),
                "run_path": relative(paths["run"], output_root),
                "video_path": relative(paths["video"], output_root),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
                "submission_count": run.get("submission_count"),
                "provider_terminal_diagnostics": copy.deepcopy(
                    run.get("provider_terminal_diagnostics")
                ),
                "diagnostics_unavailable_upstream": run.get(
                    "diagnostics_unavailable_upstream"
                ),
                "terminal_no_output_stop_applied": run.get(
                    "terminal_no_output_stop_applied"
                ),
                "automatic_paid_retry": False,
                "fallback": None,
                "s3_upload": False,
            }
        ],
    }


def write_generation_manifest(
    entry: Entry,
    *,
    output_root: Path,
    invocation: dict[str, Any] | None,
) -> dict[str, Any]:
    document = generation_manifest_document(
        entry, output_root=output_root, invocation=invocation
    )
    transport.atomic_write_json(output_root / GENERATION_MANIFEST_REL, document)
    return document


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise TuneV7VeoRetryError("--budget-cap-usd must be decimal") from exc
    if parsed != ACCOUNTING_BUDGET_USD:
        raise TuneV7VeoRetryError("The single V7 retry requires exact budget cap 0.35")
    return parsed


def run_batch(
    budget_cap_usd: str | Decimal,
    *,
    dry_run: bool,
    allow_external_processing: bool = False,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    root: Path = ROOT,
    output_root: Path | None = None,
    operations: ProviderOperations | None = None,
) -> int:
    parse_budget(budget_cap_usd)
    if not dry_run and not allow_external_processing:
        raise TuneV7VeoRetryError("Real generation requires --allow-external-processing")
    output_root = (output_root or root).resolve()
    entry = load_inventory(root=root)
    materialize_entry(entry, output_root=output_root)
    invocation = {
        "mode": "dry-run" if dry_run else "generate",
        "selected_evaluation_ids": [EXPECTED_KEY],
        "budget_cap_usd": 0.35,
        "one_paid_submit": True,
        "automatic_paid_retry": False,
    }
    write_generation_manifest(entry, output_root=output_root, invocation=invocation)
    failures = run_provider_worker(
        entry,
        dry_run=dry_run,
        timeout=timeout,
        poll_interval=poll_interval,
        output_root=output_root,
        operations=operations,
    )
    write_generation_manifest(entry, output_root=output_root, invocation=invocation)
    return failures


def verify(
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
    allow_incomplete: bool = False,
) -> tuple[bool, list[str]]:
    output_root = (output_root or root).resolve()
    entry = load_inventory(root=root)
    paths = artifact_paths(entry, output_root)
    errors: list[str] = []
    if not paths["prompt"].is_file() or not paths["run"].is_file():
        return (allow_incomplete, [] if allow_incomplete else ["missing V7 artifacts"])
    if read_json(paths["prompt"]) != prompt_artifact(entry):
        errors.append("V7 prompt binding changed")
        return False, errors
    run = read_json(paths["run"])
    request = provider_request(entry)
    fingerprint = transport.request_fingerprint(request, provider_sample(entry))
    status = str(run.get("status"))
    if status not in {"pending"} and (
        run.get("request") != request
        or run.get("request_sha256") != fingerprint
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        errors.append("V7 immutable request binding changed")
    if status in {"succeeded", "verification-failed"}:
        if run.get("submission_count") != 1 or not paths["video"].is_file():
            errors.append("V7 terminal media binding changed")
        else:
            media = transport.ffprobe_media(paths["video"])
            if media != run.get("media"):
                errors.append("V7 media receipt changed")
    elif status == "provider-failed":
        diagnostics = run.get("provider_terminal_diagnostics")
        if (
            run.get("submission_count") != 1
            or run.get("provider_may_be_active") is not False
            or paths["video"].exists()
            or not isinstance(diagnostics, dict)
            or diagnostics.get("status") not in TERMINAL_FAILURES
            or run.get("terminal_no_output_stop_applied") is not True
        ):
            errors.append("V7 terminal no-output receipt changed")
    elif status in {"submit-unknown", "submitted", "running", "submitting"}:
        if run.get("submission_count") != 1 or run.get("provider_may_be_active") is not True:
            errors.append("V7 active/ambiguous receipt changed")
    elif status in {"pending", "dry-run", "failed-pre-submit"}:
        if not allow_incomplete and status in {"pending", "dry-run"}:
            errors.append(f"V7 run is incomplete: {status}")
    else:
        errors.append(f"Unexpected V7 status: {status}")
    manifest_path = output_root / GENERATION_MANIFEST_REL
    if manifest_path.is_file():
        document = read_json(manifest_path)
        if (
            document.get("manifest_role") != MANIFEST_ROLE
            or document.get("batch_id") != BATCH_ID
            or len(document.get("outputs", [])) != 1
            or document["outputs"][0].get("provider_run_id") != entry.provider_run_id
        ):
            errors.append("V7 generation manifest binding changed")
    elif not allow_incomplete:
        errors.append("V7 generation manifest missing")
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--budget-cap-usd", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--budget-cap-usd", required=True)
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--timeout", type=int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            return run_batch(args.budget_cap_usd, dry_run=True, root=root)
        if args.command == "generate":
            return run_batch(
                args.budget_cap_usd,
                dry_run=False,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                root=root,
            )
        ok, errors = verify(
            root=root, allow_incomplete=args.allow_incomplete
        )
        if not ok:
            for error in errors:
                print(error, file=sys.stderr)
            return 2
        return 0
    except (TuneV7VeoRetryError, transport.PipelineError) as exc:
        print(f"Tune V7 Veo retry error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
