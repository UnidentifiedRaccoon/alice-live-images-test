#!/usr/bin/env python3
"""Prepare the immutable two-prompt Veo repair lineage for Tune retry v6.

The original v5 provider receipts are evidence and are never rewritten.  The
two Veo attempts that ended in a terminal provider ``no output`` state receive
new Clipmaker Lite 2.3 runs with neutral, source-consistent camera-only repair
feedback.  This module prepares and verifies those Lite runs; it never calls a
video provider, uploads to S3, or supplies a hand-authored provider prompt.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import clipmaker_lite_tune_v5_pipeline as v5_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v5_video_pipeline as v5_generation  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
BATCH_ID = "promopages-10060-tune-prompts-20260811-v5-r7"
PREVIOUS_BATCH_ID = "promopages-10060-tune-prompts-20260811-v5-r6"
EXPECTED_CONTRACT_VERSION = "2.3.0"
SOURCE_PROMPT_BATCH_ID = v5_planning.REPAIR_BATCH_ID
SOURCE_VIDEO_BATCH_ID = v5_generation.BATCH_ID
SOURCE_PROMPT_MANIFEST_REL = v5_generation.PROMPT_MANIFEST_REL
SOURCE_GENERATION_MANIFEST_REL = v5_generation.GENERATION_MANIFEST_REL
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
SELECTION_REL = BATCH_ROOT_REL / "selection.json"
PROMPT_MANIFEST_REL = BATCH_ROOT_REL / "prompt-manifest.json"
REPAIR_ROOT_REL = BATCH_ROOT_REL / "repair-feedback"
PREVIOUS_BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / PREVIOUS_BATCH_ID
PREVIOUS_SELECTION_REL = PREVIOUS_BATCH_ROOT_REL / "selection.json"
PREVIOUS_PROMPT_MANIFEST_REL = PREVIOUS_BATCH_ROOT_REL / "prompt-manifest.json"

MODEL_ID = "google/veo-3.1-lite"
CASE_IDS = ("07#06", "10#07")
REPAIR_CASE_IDS = frozenset({"07#06"})
EXPECTED_TARGET_KEYS = frozenset(f"{case_id}::{MODEL_ID}" for case_id in CASE_IDS)
EXPECTED_SOURCE_STATUSES = {key: "provider-failed" for key in EXPECTED_TARGET_KEYS}


class TuneV5RetryPlanningError(RuntimeError):
    """The immutable retry prompt lineage failed a binding or semantic gate."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TuneV5RetryPlanningError(f"Required JSON is missing: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TuneV5RetryPlanningError(f"Invalid JSON: {path}") from exc


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError as exc:
        raise TuneV5RetryPlanningError(f"Required file is missing: {path}") from exc


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneV5RetryPlanningError(f"Artifact is outside workspace: {path}") from exc


def atomic_create_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == payload:
            return
        raise TuneV5RetryPlanningError(f"Immutable artifact already differs: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise TuneV5RetryPlanningError(
            f"Immutable artifact appeared concurrently: {path}"
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _key(case_id: str) -> str:
    return f"{case_id}::{MODEL_ID}"


def _feedback(case_id: str) -> dict[str, Any]:
    if case_id == "07#06":
        focal_target = "the complete existing sofa scene with the visible person and phone"
        identity = (
            "Preserve exactly one visible adult, the existing hands, red phone, clothing, sofa, and room; "
            "nothing appears, disappears, or changes identity."
        )
        geometry = (
            "Keep the existing pose, hand-to-phone contacts, phone geometry, facial expression, "
            "and all room geometry source-locked."
        )
    elif case_id == "10#07":
        focal_target = "the complete existing dining scene and all visible people"
        identity = (
            "Preserve exactly four visible people and every existing limb, garment, dish, utensil, cup, food item, and piece "
            "of furniture; nothing appears, disappears, or changes owner."
        )
        geometry = (
            "Keep every pose and hand-to-object contact, the table arrangement, sofa, mirror, and "
            "room geometry source-locked."
        )
    else:
        raise TuneV5RetryPlanningError(f"Unsupported retry case: {case_id}")
    return {
        "evaluation_id": _key(case_id),
        "outcome": "worse",
        "review_note": (
            "The prior Veo provider attempt ended terminally with no output. Author a neutral "
            "camera-only I2V shot: one gentle centered push-in. Do not script gestures, gaze or "
            "expression changes, interpersonal actions, speech, or any inferred relationship. "
            + (
                'The positive_prompt must include the exact phrase "within a 5% screen-travel cap".'
                if case_id == "07#06"
                else ""
            )
        ),
        "evidence_strength": "explicit",
        "failure_codes": ["provider_no_output"],
        "required_execution_mode": "i2v",
        "fallback_policy": "none",
        "camera_repair": {
            "move": "push-in",
            "focal_target": focal_target,
            "target_retention": "continuously-visible",
            "max_screen_travel_percent": 5 if case_id == "07#06" else 3,
            "reveal_unseen_space": False,
        },
        "preservation": {
            "entity_counts": [identity],
            "topology_anchors": [
                geometry,
                *(
                    ['The positive_prompt must include the exact phrase "within a 5% screen-travel cap".']
                    if case_id == "07#06"
                    else []
                ),
            ],
            "rigid_regions": [focal_target],
            "contacts": [geometry],
            "must_remain_visible": [focal_target],
        },
    }


def _source_generation_outputs(document: Any) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-video-generation"
        or document.get("batch_id") != SOURCE_VIDEO_BATCH_ID
        or document.get("ticket") != TICKET
        or not isinstance(document.get("outputs"), list)
        or len(document["outputs"]) != 28
    ):
        raise TuneV5RetryPlanningError("Unexpected source v5 generation manifest")
    by_key: dict[str, dict[str, Any]] = {}
    for output in document["outputs"]:
        if not isinstance(output, dict):
            raise TuneV5RetryPlanningError("Source v5 output must be an object")
        key = f"{output.get('case_id')}::{output.get('model_id')}"
        if key in by_key:
            raise TuneV5RetryPlanningError(f"Duplicate source output: {key}")
        by_key[key] = output
    for key, expected_status in EXPECTED_SOURCE_STATUSES.items():
        output = by_key.get(key)
        if (
            not isinstance(output, dict)
            or output.get("status") != expected_status
            or output.get("fallback") is not None
            or output.get("media") is not None
            or output.get("contract_check") is not None
        ):
            raise TuneV5RetryPlanningError(f"Source failure evidence changed: {key}")
    return by_key


def _source_cases(document: Any) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-planning"
        or document.get("batch_id") != SOURCE_PROMPT_BATCH_ID
        or document.get("contract_version") != EXPECTED_CONTRACT_VERSION
        or not isinstance(document.get("cases"), list)
        or len(document["cases"]) != 17
    ):
        raise TuneV5RetryPlanningError("Unexpected source v5 prompt manifest")
    by_id = {str(case.get("case_id")): case for case in document["cases"] if isinstance(case, dict)}
    if len(by_id) != 17 or any(case_id not in by_id for case_id in CASE_IDS):
        raise TuneV5RetryPlanningError("Source v5 prompt case set changed")
    return by_id


def build_selection_document(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    # Full inventory validation proves every source prompt came from a verified
    # Lite 2.3 result before selecting the two failed Veo attempts.
    inventory = v5_generation.load_inventory("9.80", root=root)
    inventory_by_key = {
        f"{entry.case_id}::{entry.model_id}": entry for entry in inventory.entries
    }
    prompt_path = root / SOURCE_PROMPT_MANIFEST_REL
    generation_path = root / SOURCE_GENERATION_MANIFEST_REL
    prompt_document = read_json(prompt_path)
    source_cases = _source_cases(prompt_document)
    source_outputs = _source_generation_outputs(read_json(generation_path))
    previous_selection = read_json(root / PREVIOUS_SELECTION_REL)
    previous_prompt = read_json(root / PREVIOUS_PROMPT_MANIFEST_REL)
    if (
        not isinstance(previous_selection, dict)
        or previous_selection.get("batch_id") != PREVIOUS_BATCH_ID
        or not isinstance(previous_selection.get("cases"), list)
        or not isinstance(previous_prompt, dict)
        or previous_prompt.get("batch_id") != PREVIOUS_BATCH_ID
        or not isinstance(previous_prompt.get("cases"), list)
    ):
        raise TuneV5RetryPlanningError("Unexpected previous r6 retry lineage")
    previous_selection_by_id = {
        str(case.get("case_id")): case
        for case in previous_selection["cases"]
        if isinstance(case, dict)
    }
    previous_prompt_by_id = {
        str(case.get("case_id")): case
        for case in previous_prompt["cases"]
        if isinstance(case, dict)
    }
    published: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        key = _key(case_id)
        entry = inventory_by_key.get(key)
        source_case = source_cases[case_id]
        source_target = next(
            (target for target in source_case["targets"] if target.get("model_id") == MODEL_ID),
            None,
        )
        output = source_outputs[key]
        if entry is None or not isinstance(source_target, dict):
            raise TuneV5RetryPlanningError(f"Source Lite prompt missing: {key}")
        run_path = root / str(output["run_path"])
        run = read_json(run_path)
        if (
            run.get("status") != "provider-failed"
            or run.get("provider_may_be_active") is not False
            or run.get("automatic_paid_retry") is not False
            or run.get("fallback") is not None
            or not isinstance(run.get("provider_job_id"), str)
            or not run["provider_job_id"]
            or not isinstance(run.get("error"), str)
            or "no output" not in run["error"].lower()
        ):
            raise TuneV5RetryPlanningError(f"Source terminal receipt changed: {key}")
        if case_id in REPAIR_CASE_IDS:
            feedback = {MODEL_ID: _feedback(case_id)}
            feedback_path = (
                REPAIR_ROOT_REL / f"{case_id.replace('#', '-')}.json"
            ).as_posix()
            run_id = f"{BATCH_ID}-{source_case['article_slug']}-{source_case['source']['image_id']}"
            source_prompt_record = {
                "batch_id": SOURCE_PROMPT_BATCH_ID,
                "planning_run_id": entry.planning_run_id,
                "result_path": entry.result_path,
                "result_sha256": entry.result_sha256,
                "positive_prompt_sha256": hashlib.sha256(
                    entry.positive_prompt.encode("utf-8")
                ).hexdigest(),
            }
            retry_reason = "r7-numeric-cap-repair-after-r6-semantic-gate"
        else:
            previous_case = previous_selection_by_id.get(case_id)
            previous_prompt_case = previous_prompt_by_id.get(case_id)
            if not isinstance(previous_case, dict) or not isinstance(previous_prompt_case, dict):
                raise TuneV5RetryPlanningError(f"Previous r6 case missing: {case_id}")
            feedback = copy.deepcopy(previous_case["repair_feedback"])
            feedback_path = previous_case["repair_feedback_path"]
            run_id = previous_prompt_case["planning"]["run_id"]
            source_prompt_record = {
                "batch_id": PREVIOUS_BATCH_ID,
                "planning_run_id": run_id,
                "result_path": previous_prompt_case["planning"]["result_path"],
                "result_sha256": previous_prompt_case["planning"]["result_sha256"],
                "positive_prompt_sha256": hashlib.sha256(
                    previous_prompt_case["targets"][0]["tuned"]["positive_prompt"].encode("utf-8")
                ).hexdigest(),
            }
            retry_reason = "reused-provenance-verified-r6-neutral-prompt"
        try:
            normalized = runner.validate_repair_feedback_models(
                feedback, [MODEL_ID], f"retry feedback {case_id}"
            )
        except runner.LiteRunnerError as exc:
            raise TuneV5RetryPlanningError(str(exc)) from exc
        if normalized != feedback:
            raise TuneV5RetryPlanningError(f"Retry feedback normalization changed: {case_id}")
        article_slug = str(source_case["article_slug"])
        image_id = str(source_case["source"]["image_id"])
        published.append(
            {
                "case_id": case_id,
                "sheet_row": source_target["sheet_row"],
                "article_slug": article_slug,
                "brand": source_case.get("brand"),
                "title": source_case.get("title"),
                "publication_id": source_case.get("publication_id"),
                "content_class": source_case.get("content_class"),
                "source": copy.deepcopy(source_case["source"]),
                "context_path": source_case["context_path"],
                "context_binding": copy.deepcopy(source_case["context_binding"]),
                "selected_model_ids": [MODEL_ID],
                "repair_feedback_path": feedback_path,
                "repair_feedback_sha256": canonical_sha256(feedback),
                "repair_feedback": feedback,
                "run_id": run_id,
                "retry_reason": retry_reason,
                "source_prompt": source_prompt_record,
                "source_provider_attempt": {
                    "batch_id": SOURCE_VIDEO_BATCH_ID,
                    "provider_run_id": output["provider_run_id"],
                    "status": "provider-failed",
                    "prompt_path": output["prompt_path"],
                    "prompt_sha256": sha256_file(root / output["prompt_path"]),
                    "run_path": output["run_path"],
                    "run_sha256": sha256_file(run_path),
                    "provider_job_id": run["provider_job_id"],
                    "error": run["error"],
                    "provider_may_be_active": False,
                    "automatic_paid_retry": False,
                    "fallback": None,
                },
                "targets": [
                    {
                        "evaluation_id": key,
                        "case_id": case_id,
                        "sheet_row": source_target["sheet_row"],
                        "model_id": MODEL_ID,
                        "repair_feedback": copy.deepcopy(feedback[MODEL_ID]),
                    }
                ],
            }
        )
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-retry-selection",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "policy": {
            "selection": "two terminal Veo provider-no-output attempts",
            "required_execution_mode": "i2v",
            "required_rendering_strategy": "camera-only",
            "prompt_author": "clipmaker-lite",
            "hand_authored_provider_prompt": False,
            "fallback": False,
            "s3_upload": False,
        },
        "lineage": {
            "source_prompt_manifest": {
                "path": SOURCE_PROMPT_MANIFEST_REL.as_posix(),
                "sha256": sha256_file(prompt_path),
                "batch_id": SOURCE_PROMPT_BATCH_ID,
            },
            "source_generation_manifest": {
                "path": SOURCE_GENERATION_MANIFEST_REL.as_posix(),
                "sha256": sha256_file(generation_path),
                "batch_id": SOURCE_VIDEO_BATCH_ID,
                "receipts_mutated": False,
            },
            "previous_retry_prompt_manifest": {
                "path": PREVIOUS_PROMPT_MANIFEST_REL.as_posix(),
                "sha256": sha256_file(root / PREVIOUS_PROMPT_MANIFEST_REL),
                "batch_id": PREVIOUS_BATCH_ID,
                "reused_case_ids": ["10#07"],
            },
        },
        "summary": {
            "case_count": 2,
            "target_count": 2,
            "model_counts": {MODEL_ID: 2},
            "source_status_counts": {"provider-failed": 2},
            "new_repair_case_count": 1,
            "reused_previous_case_count": 1,
        },
        "cases": published,
    }


def write_selection(document: dict[str, Any], *, root: Path = ROOT) -> Path:
    root = root.resolve()
    for case in document["cases"]:
        path = root / case["repair_feedback_path"]
        atomic_create_json(path, case["repair_feedback"])
        if canonical_sha256(read_json(path)) != case["repair_feedback_sha256"]:
            raise TuneV5RetryPlanningError(f"Feedback digest changed: {path}")
    output = root / SELECTION_REL
    atomic_create_json(output, document)
    return output


def load_selection(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    document = read_json(root / SELECTION_REL)
    if (
        not isinstance(document, dict)
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-retry-selection"
        or document.get("batch_id") != BATCH_ID
        or document.get("summary")
        != {
            "case_count": 2,
            "target_count": 2,
            "model_counts": {MODEL_ID: 2},
            "source_status_counts": {"provider-failed": 2},
            "new_repair_case_count": 1,
            "reused_previous_case_count": 1,
        }
        or document.get("policy", {}).get("required_rendering_strategy") != "camera-only"
        or document.get("policy", {}).get("fallback") is not False
        or document.get("policy", {}).get("s3_upload") is not False
        or not isinstance(document.get("cases"), list)
        or tuple(case.get("case_id") for case in document["cases"]) != CASE_IDS
    ):
        raise TuneV5RetryPlanningError("Unexpected retry selection identity")
    lineage = document.get("lineage", {})
    for key, expected_path in (
        ("source_prompt_manifest", SOURCE_PROMPT_MANIFEST_REL),
        ("source_generation_manifest", SOURCE_GENERATION_MANIFEST_REL),
        ("previous_retry_prompt_manifest", PREVIOUS_PROMPT_MANIFEST_REL),
    ):
        record = lineage.get(key)
        if (
            not isinstance(record, dict)
            or record.get("path") != expected_path.as_posix()
            or record.get("sha256") != sha256_file(root / expected_path)
        ):
            raise TuneV5RetryPlanningError(f"Retry lineage changed: {key}")
    for case in document["cases"]:
        feedback = read_json(root / case["repair_feedback_path"])
        try:
            normalized = runner.validate_repair_feedback_models(
                feedback, [MODEL_ID], f"retry feedback {case['case_id']}"
            )
        except runner.LiteRunnerError as exc:
            raise TuneV5RetryPlanningError(str(exc)) from exc
        expected_batch_id = BATCH_ID if case["case_id"] in REPAIR_CASE_IDS else PREVIOUS_BATCH_ID
        expected_run_id = (
            f"{expected_batch_id}-{case['article_slug']}-{case['source']['image_id']}"
        )
        if (
            case.get("run_id") != expected_run_id
            or case.get("selected_model_ids") != [MODEL_ID]
            or feedback != normalized
            or feedback != case.get("repair_feedback")
            or canonical_sha256(feedback) != case.get("repair_feedback_sha256")
            or len(case.get("targets", [])) != 1
            or case["targets"][0].get("evaluation_id") != _key(case["case_id"])
        ):
            raise TuneV5RetryPlanningError(f"Retry case binding changed: {case.get('case_id')}")
    return document


def _inputs_match_case(inputs: Any, case: dict[str, Any]) -> bool:
    if not isinstance(inputs, dict):
        return False
    source = inputs.get("source_image")
    context = inputs.get("article_context")
    return (
        isinstance(source, dict)
        and source.get("path") == case["source"]["path"]
        and source.get("sha256") == case["source"]["sha256"]
        and isinstance(context, dict)
        and context.get("path") == case["context_binding"]["path"]
        and context.get("sha256") == case["context_binding"]["sha256"]
        and context.get("locator") == case["context_binding"]["locator"]
    )


def prepare_case(case: dict[str, Any], *, root: Path = ROOT) -> str:
    run_id = case["run_id"]
    directory = root / runner.OUTPUT_NAMESPACE / run_id
    if directory.exists():
        job, selection, _directory = runner.validate_prepared_job(root, run_id)
        repair = job.get("inputs", {}).get("repair_feedback")
        if (
            [item["model_id"] for item in selection["selected_models"]] != [MODEL_ID]
            or not _inputs_match_case(job.get("inputs"), case)
            or not isinstance(repair, dict)
            or repair.get("path") != case["repair_feedback_path"]
            or repair.get("canonical_sha256") != case["repair_feedback_sha256"]
        ):
            raise TuneV5RetryPlanningError(f"Prepared retry job changed: {run_id}")
        return "already-prepared"
    runner.prepare_run(
        root,
        run_id,
        case["source"]["path"],
        case["context_path"],
        image_id=case["source"]["image_id"],
        model_ids=[MODEL_ID],
        user_direction=None,
        repair_feedback_path=case["repair_feedback_path"],
    )
    return "prepared"


def result_is_verified(case: dict[str, Any], *, root: Path = ROOT) -> bool:
    result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
    if not result_path.is_file() or result_path.is_symlink():
        return False
    summary = runner.provenance_summary(root, case["run_id"])
    result = read_json(result_path)
    repair = result.get("inputs", {}).get("repair_feedback")
    return (
        summary.get("verified") is True
        and summary.get("contract_version") == EXPECTED_CONTRACT_VERSION
        and summary.get("models") == [MODEL_ID]
        and _inputs_match_case(result.get("inputs"), case)
        and isinstance(repair, dict)
        and repair.get("path") == case["repair_feedback_path"]
        and repair.get("canonical_sha256") == case["repair_feedback_sha256"]
    )


def validate_neutral_result(result: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    models = result.get("models")
    intent = result.get("analysis", {}).get("structured_intent")
    if (
        not isinstance(models, list)
        or len(models) != 1
        or not isinstance(models[0], dict)
        or models[0].get("model_id") != MODEL_ID
        or models[0].get("execution_mode") != "i2v"
        or not isinstance(models[0].get("positive_prompt"), str)
        or not models[0]["positive_prompt"].strip()
        or models[0].get("negative_prompt") is not None
        or not isinstance(intent, dict)
        or intent.get("rendering_strategy") != "camera-only"
    ):
        raise TuneV5RetryPlanningError(
            f"Retry Lite result is not neutral camera-only I2V: {case['case_id']}"
        )
    combined = f"{models[0].get('scene_plan', '')} {models[0]['positive_prompt']}".lower()
    if "camera" not in combined or not any(token in combined for token in ("push-in", "push in")):
        raise TuneV5RetryPlanningError(
            f"Retry Lite result lacks the requested gentle push-in: {case['case_id']}"
        )
    if (
        case["case_id"] == "07#06"
        and "within a 5% screen-travel cap" not in models[0]["positive_prompt"]
    ):
        raise TuneV5RetryPlanningError(
            "07#06 positive_prompt must include the exact numeric 5% screen-travel cap"
        )
    return models[0]


def run_case(
    case: dict[str, Any],
    *,
    root: Path = ROOT,
    author_model: str | None = None,
    timeout: int = 900,
) -> str:
    if result_is_verified(case, root=root):
        validate_neutral_result(
            read_json(root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"),
            case,
        )
        return "already-complete"
    runner.run_agent(
        root,
        case["run_id"],
        author_model=author_model,
        timeout=timeout,
        external_processing_approved=True,
    )
    if not result_is_verified(case, root=root):
        raise TuneV5RetryPlanningError(f"Lite provenance failed: {case['run_id']}")
    validate_neutral_result(
        read_json(root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"), case
    )
    return "completed"


def run_cases(
    cases: Iterable[dict[str, Any]],
    *,
    root: Path,
    jobs: int,
    author_model: str | None,
    timeout: int,
) -> None:
    cases = list(cases)
    if not 1 <= jobs <= 2:
        raise TuneV5RetryPlanningError("--jobs must be 1 or 2")
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(
                run_case,
                case,
                root=root,
                author_model=author_model,
                timeout=timeout,
            ): case
            for case in cases
        }
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            try:
                print(f"{case['case_id']}: {future.result()}", flush=True)
            except Exception as exc:  # noqa: BLE001 - report both immutable runs
                failures.append(f"{case['case_id']}: {exc}")
    if failures:
        raise TuneV5RetryPlanningError("Retry planning failures:\n" + "\n".join(failures))


def build_prompt_manifest(selection: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for case in selection["cases"]:
        if not result_is_verified(case, root=root):
            raise TuneV5RetryPlanningError(f"Retry result is not verified: {case['run_id']}")
        result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
        result = read_json(result_path)
        model = validate_neutral_result(result, case)
        provenance = runner.provenance_summary(root, case["run_id"])
        target = copy.deepcopy(case["targets"][0])
        target["tuned"] = {
            "execution_mode": "i2v",
            "scene_plan": model["scene_plan"],
            "positive_prompt": model["positive_prompt"],
            "negative_prompt": None,
            "runtime": copy.deepcopy(model["runtime"]),
        }
        cases.append(
            {
                **{
                    key: copy.deepcopy(value)
                    for key, value in case.items()
                    if key not in {"repair_feedback", "targets"}
                },
                "planning": {
                    "run_id": case["run_id"],
                    "result_path": relative(result_path, root),
                    "result_sha256": sha256_file(result_path),
                    "provenance": provenance,
                    "structured_intent": copy.deepcopy(result["analysis"]["structured_intent"]),
                    "image_reading": result["analysis"]["image_reading"],
                    "article_context": result["analysis"]["article_context"],
                    "repair_feedback_path": case["repair_feedback_path"],
                    "repair_feedback_sha256": case["repair_feedback_sha256"],
                },
                "targets": [target],
            }
        )
    existing_path = root / PROMPT_MANIFEST_REL
    generated_at = utc_now()
    if existing_path.exists():
        existing = read_json(existing_path)
        if (
            not isinstance(existing, dict)
            or existing.get("batch_id") != BATCH_ID
            or not isinstance(existing.get("generated_at"), str)
        ):
            raise TuneV5RetryPlanningError("Existing retry prompt manifest identity changed")
        generated_at = existing["generated_at"]
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-retry-planning",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "contract_version": EXPECTED_CONTRACT_VERSION,
        "generated_at": generated_at,
        "scope": {
            "selection_path": SELECTION_REL.as_posix(),
            "selection_sha256": sha256_file(root / SELECTION_REL),
            "case_count": 2,
            "target_count": 2,
            "required_execution_mode": "i2v",
            "required_rendering_strategy": "camera-only",
            "fallback": False,
            "video_generation": False,
            "s3_upload": False,
        },
        "lineage": copy.deepcopy(selection["lineage"]),
        "summary": copy.deepcopy(selection["summary"]),
        "cases": cases,
    }


def _filtered_cases(selection: dict[str, Any], requested: list[str]) -> list[dict[str, Any]]:
    if not requested:
        return list(selection["cases"])
    by_id = {case["case_id"]: case for case in selection["cases"]}
    if set(requested) - set(by_id):
        raise TuneV5RetryPlanningError("Unknown retry case requested")
    return [by_id[case_id] for case_id in requested]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "prepare", "run", "build", "all"))
    parser.add_argument("--case", action="append", default=[], dest="case_ids")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--author-model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--allow-external-processing", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"plan", "all"}:
            output = write_selection(build_selection_document(root=root), root=root)
            print(relative(output, root), flush=True)
        selection = load_selection(root=root)
        cases = _filtered_cases(selection, args.case_ids)
        if args.command in {"prepare", "all"}:
            for case in cases:
                print(f"{case['case_id']}: {prepare_case(case, root=root)}", flush=True)
        if args.command in {"run", "all"}:
            if not args.allow_external_processing:
                raise TuneV5RetryPlanningError("run/all requires --allow-external-processing")
            run_cases(
                cases,
                root=root,
                jobs=args.jobs,
                author_model=args.author_model,
                timeout=args.timeout,
            )
        if args.command in {"build", "all"}:
            manifest = build_prompt_manifest(selection, root=root)
            atomic_create_json(root / PROMPT_MANIFEST_REL, manifest)
            print(PROMPT_MANIFEST_REL.as_posix(), flush=True)
        return 0
    except (TuneV5RetryPlanningError, runner.LiteRunnerError) as exc:
        print(f"Tune v5 retry planning error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
