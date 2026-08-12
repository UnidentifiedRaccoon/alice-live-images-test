#!/usr/bin/env python3
"""Prepare one immutable Clipmaker Lite repair prompt for filtered Tune 07#06.

The provider receives the canonical full source image and a provenance-verified
Lite prompt.  Historical background-only/cropped/composited successes are
forensic evidence only and are never used as generation inputs or fallbacks.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import clipmaker_lite_tune_v5_retry_planning as previous_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v5_retry_video_pipeline as previous_generation  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
BATCH_ID = "promopages-10060-tune-prompts-20260812-v5-r8"
EXPECTED_CONTRACT_VERSION = "2.3.0"
CASE_ID = "07#06"
MODEL_ID = "google/veo-3.1-lite"
EVALUATION_ID = f"{CASE_ID}::{MODEL_ID}"
EXACT_POSITIVE_PROMPT = (
    "Slow, gentle centered dolly in on the existing scene. By the final frame, "
    "the same composition appears about 5% closer."
)
CANONICAL_SOURCE_SHA256 = (
    "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12"
)
BACKGROUND_ONLY_EVIDENCE_SHA256 = (
    "31672c5832458e9698f2a5710a159b10cbb99febf55c7f1b0906393f977cb88e"
)
FAILED_SOURCE_VARIANTS = (
    {
        "sha256": CANONICAL_SOURCE_SHA256,
        "dimensions": {"width": 2400, "height": 1600},
        "observed_failed_seeds": [9681, 27183],
    },
    {
        "sha256": "f3eac13ca2c71c7cec3a1a860c701caea68728a3f9dc9e77c1d05b2455143ce9",
        "dimensions": {"width": 1920, "height": 1080},
        "observed_failed_seeds": [9681],
    },
    {
        "sha256": "74764f50e6a2b6c307817c2862df40c8ed50367aa9f5e191106f22772397bb88",
        "dimensions": {"width": 1920, "height": 1080},
        "observed_failed_seeds": [9681],
    },
)
SOURCE_PROMPT_BATCH_ID = previous_planning.BATCH_ID
SOURCE_VIDEO_BATCH_ID = previous_generation.BATCH_ID
SOURCE_PROMPT_MANIFEST_REL = previous_planning.PROMPT_MANIFEST_REL
SOURCE_GENERATION_MANIFEST_REL = previous_generation.GENERATION_MANIFEST_REL
FORENSIC_MANIFEST_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-femibion-veo-recovery-20260810-v7/"
    "all-attempts-selection-manifest.json"
)
FORENSIC_MANIFEST_SHA256 = (
    "df471ab6fa5a530ca690b40ce9791aae9bcb56b1893a0f25b80ef777072dac0d"
)
ADDITIONAL_FAILURE_RUN_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-tune-videos-20260811-v1/"
    "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"
)
ADDITIONAL_FAILURE_RUN_SHA256 = (
    "bf9bafc04cb2eae3467355696026706582c38f1b6f0cd67536e43dd172b8ca82"
)
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
SELECTION_REL = BATCH_ROOT_REL / "selection.json"
PROMPT_MANIFEST_REL = BATCH_ROOT_REL / "prompt-manifest.json"
REPAIR_FEEDBACK_REL = BATCH_ROOT_REL / "repair-feedback/07-06.json"


class TuneV7FilterPlanningError(RuntimeError):
    """The single-target filter-repair lineage failed a binding or semantic gate."""


read_json = previous_planning.read_json
sha256_file = previous_planning.sha256_file
canonical_sha256 = previous_planning.canonical_sha256
atomic_create_json = previous_planning.atomic_create_json
relative = previous_planning.relative
utc_now = previous_planning.utc_now


def repair_feedback() -> dict[str, Any]:
    return {
        MODEL_ID: {
            "evaluation_id": EVALUATION_ID,
            "outcome": "worse",
            "review_note": (
                "Repeated provider no-output receipts indicate a suspected source-image "
                "safety false positive, not a known prompt-policy violation. Author the "
                "positive_prompt exactly as supplied in the preservation rule below. Keep "
                "the treatment camera-only and do not name or describe any visible subject, "
                "body part, device, activity, relationship, health topic, or brand."
            ),
            "evidence_strength": "explicit",
            "failure_codes": ["provider_no_output"],
            "required_execution_mode": "i2v",
            "fallback_policy": "none",
            "camera_repair": {
                "move": "push-in",
                "focal_target": "the complete existing scene",
                "target_retention": "continuously-visible",
                "max_screen_travel_percent": 5,
                "reveal_unseen_space": False,
            },
            "preservation": {
                "entity_counts": [
                    "Keep the complete source composition unchanged."
                ],
                "topology_anchors": [
                    f'The positive_prompt must be exactly: "{EXACT_POSITIVE_PROMPT}"'
                ],
                "rigid_regions": ["the complete existing scene"],
                "contacts": ["Do not animate any source element."],
                "must_remain_visible": ["the complete existing scene"],
            },
        }
    }


def _source_case(document: Any) -> dict[str, Any]:
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-retry-planning"
        or document.get("batch_id") != SOURCE_PROMPT_BATCH_ID
        or document.get("contract_version") != EXPECTED_CONTRACT_VERSION
        or not isinstance(document.get("cases"), list)
    ):
        raise TuneV7FilterPlanningError("Unexpected r7 source prompt manifest")
    matches = [case for case in document["cases"] if case.get("case_id") == CASE_ID]
    if len(matches) != 1:
        raise TuneV7FilterPlanningError("The r7 source prompt case changed")
    case = matches[0]
    source = case.get("source")
    if (
        not isinstance(source, dict)
        or source.get("sha256") != CANONICAL_SOURCE_SHA256
        or source.get("width") != 2400
        or source.get("height") != 1600
    ):
        raise TuneV7FilterPlanningError("Canonical 07#06 source binding changed")
    return case


def _source_output(document: Any, *, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role")
        != "clipmaker-lite-tune-v6-retry-video-generation"
        or document.get("batch_id") != SOURCE_VIDEO_BATCH_ID
        or not isinstance(document.get("outputs"), list)
        or len(document["outputs"]) != 8
    ):
        raise TuneV7FilterPlanningError("Unexpected v6 source generation manifest")
    matches = [
        output
        for output in document["outputs"]
        if output.get("evaluation_id") == EVALUATION_ID
    ]
    if len(matches) != 1:
        raise TuneV7FilterPlanningError("The v6 source output changed")
    output = matches[0]
    run = read_json(root / output["run_path"])
    if (
        output.get("status") != "provider-failed"
        or output.get("submission_count") != 1
        or output.get("fallback") is not None
        or output.get("media") is not None
        or run.get("status") != "provider-failed"
        or run.get("submission_count") != 1
        or run.get("provider_may_be_active") is not False
        or run.get("provider_response") is not None
        or not isinstance(run.get("provider_job_id"), str)
        or not run["provider_job_id"]
        or "no output" not in str(run.get("error", "")).lower()
        or output.get("prior_attempt", {}).get("status") != "provider-failed"
        or output.get("prior_attempt", {}).get("provider_may_be_active") is not False
    ):
        raise TuneV7FilterPlanningError("The terminal v6 filter receipt changed")
    return output, run


def _validate_forensic_evidence(document: Any) -> None:
    if (
        not isinstance(document, dict)
        or document.get("ticket") != TICKET
        or not isinstance(document.get("failed_attempt_chain"), list)
        or len(document["failed_attempt_chain"]) < 10
        or not isinstance(document.get("attempt_evidence"), list)
    ):
        raise TuneV7FilterPlanningError("Filter forensic evidence changed")
    relevant = [
        item
        for item in document["failed_attempt_chain"]
        if item.get("logical_key", {}).get("article_slug")
        == "07-femibion-gotovites-k-beremennosti"
        and item.get("logical_key", {}).get("image_id") == "06"
        and item.get("status") == "provider-filtered"
    ]
    if len(relevant) < 8:
        raise TuneV7FilterPlanningError("Historical person-preserving failures changed")
    for item in relevant:
        if item.get("provider_job_id") is None or item.get("provider_may_be_active") is True:
            raise TuneV7FilterPlanningError("Historical terminal filter evidence changed")


def _validate_additional_failure(root: Path) -> None:
    path = root / ADDITIONAL_FAILURE_RUN_REL
    if sha256_file(path) != ADDITIONAL_FAILURE_RUN_SHA256:
        raise TuneV7FilterPlanningError("Additional terminal filter receipt changed")
    run = read_json(path)
    request = run.get("request")
    if (
        run.get("status") != "provider-failed"
        or run.get("provider_may_be_active") is not False
        or run.get("provider_response") is not None
        or not isinstance(run.get("provider_job_id"), str)
        or "no output" not in str(run.get("error", "")).lower()
        or not isinstance(request, dict)
        or request.get("seed") != 9681
    ):
        raise TuneV7FilterPlanningError("Additional terminal filter evidence changed")


def build_selection_document(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    source_prompt_path = root / SOURCE_PROMPT_MANIFEST_REL
    source_generation_path = root / SOURCE_GENERATION_MANIFEST_REL
    forensic_path = root / FORENSIC_MANIFEST_REL
    if sha256_file(forensic_path) != FORENSIC_MANIFEST_SHA256:
        raise TuneV7FilterPlanningError("Frozen filter forensic manifest changed")
    _validate_forensic_evidence(read_json(forensic_path))
    _validate_additional_failure(root)
    source_case = _source_case(read_json(source_prompt_path))
    source_output, source_run = _source_output(
        read_json(source_generation_path), root=root
    )
    source_target = next(
        (
            target
            for target in source_case.get("targets", [])
            if target.get("evaluation_id") == EVALUATION_ID
        ),
        None,
    )
    if not isinstance(source_target, dict):
        raise TuneV7FilterPlanningError("The r7 source target changed")
    feedback = repair_feedback()
    try:
        normalized = runner.validate_repair_feedback_models(
            feedback, [MODEL_ID], "07#06 repeated-filter repair feedback"
        )
    except runner.LiteRunnerError as exc:
        raise TuneV7FilterPlanningError(str(exc)) from exc
    if normalized != feedback:
        raise TuneV7FilterPlanningError("Repair feedback normalization changed")
    run_id = (
        f"{BATCH_ID}-{source_case['article_slug']}-"
        f"{source_case['source']['image_id']}"
    )
    published = {
        "case_id": CASE_ID,
        "sheet_row": source_target["sheet_row"],
        "article_slug": source_case["article_slug"],
        "brand": source_case.get("brand"),
        "title": source_case.get("title"),
        "publication_id": source_case.get("publication_id"),
        "content_class": source_case.get("content_class"),
        "source": copy.deepcopy(source_case["source"]),
        "context_path": source_case["context_path"],
        "context_binding": copy.deepcopy(source_case["context_binding"]),
        "selected_model_ids": [MODEL_ID],
        "repair_feedback_path": REPAIR_FEEDBACK_REL.as_posix(),
        "repair_feedback_sha256": canonical_sha256(feedback),
        "repair_feedback": feedback,
        "run_id": run_id,
        "retry_reason": "repeated-provider-filter-neutral-source-bound-repair",
        "source_prompt": {
            "batch_id": SOURCE_PROMPT_BATCH_ID,
            "planning_run_id": source_case["planning"]["run_id"],
            "result_path": source_case["planning"]["result_path"],
            "result_sha256": source_case["planning"]["result_sha256"],
            "positive_prompt_sha256": hashlib.sha256(
                source_target["tuned"]["positive_prompt"].encode("utf-8")
            ).hexdigest(),
        },
        "source_provider_attempt": {
            "batch_id": SOURCE_VIDEO_BATCH_ID,
            "provider_run_id": source_output["provider_run_id"],
            "status": "provider-failed",
            "prompt_path": source_output["prompt_path"],
            "prompt_sha256": sha256_file(root / source_output["prompt_path"]),
            "run_path": source_output["run_path"],
            "run_sha256": sha256_file(root / source_output["run_path"]),
            "provider_job_id": source_run["provider_job_id"],
            "error": source_run["error"],
            "provider_may_be_active": False,
            "submission_count": 1,
            "automatic_paid_retry": False,
            "fallback": None,
        },
        "targets": [
            {
                "evaluation_id": EVALUATION_ID,
                "case_id": CASE_ID,
                "sheet_row": source_target["sheet_row"],
                "model_id": MODEL_ID,
                "repair_feedback": copy.deepcopy(feedback[MODEL_ID]),
            }
        ],
    }
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v7-filter-retry-selection",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "policy": {
            "selection": "one repeated terminal Veo provider-no-output target",
            "required_execution_mode": "i2v",
            "required_rendering_strategy": "camera-only",
            "prompt_author": "clipmaker-lite",
            "hand_authored_provider_prompt": False,
            "canonical_full_source_only": True,
            "disable_provider_safety_filters": False,
            "source_transform": None,
            "fallback": False,
            "compositor": False,
            "s3_upload": False,
            "one_new_paid_attempt_only": True,
            "terminal_no_output_stop": (
                "no-further-prompt-retries-on-the-same-canonical-full-source"
            ),
            "capture_provider_safety_diagnostics_if_present": True,
        },
        "diagnosis": {
            "type": "suspected_source_filter",
            "classification": "suspected-source-image-safety-false-positive",
            "evidence_strength": "strong-indirect",
            "provider_support_code_available": False,
            "prior_provider_response_present": False,
            "person_preserving_provider_failures_at_least": 11,
            "observed_failed_seeds": [9681, 27183],
            "failed_source_variants": copy.deepcopy(list(FAILED_SOURCE_VARIANTS)),
            "background_only_success_is_evidence_only": True,
            "background_only_source_sha256": BACKGROUND_ONLY_EVIDENCE_SHA256,
            "active_source_sha256": CANONICAL_SOURCE_SHA256,
            "active_source_transform": None,
        },
        "lineage": {
            "source_prompt_manifest": {
                "path": SOURCE_PROMPT_MANIFEST_REL.as_posix(),
                "sha256": sha256_file(source_prompt_path),
                "batch_id": SOURCE_PROMPT_BATCH_ID,
            },
            "source_generation_manifest": {
                "path": SOURCE_GENERATION_MANIFEST_REL.as_posix(),
                "sha256": sha256_file(source_generation_path),
                "batch_id": SOURCE_VIDEO_BATCH_ID,
                "receipts_mutated": False,
            },
            "filter_forensics": {
                "path": FORENSIC_MANIFEST_REL.as_posix(),
                "sha256": FORENSIC_MANIFEST_SHA256,
                "used_as_generation_input": False,
            },
            "additional_terminal_filter_receipt": {
                "path": ADDITIONAL_FAILURE_RUN_REL.as_posix(),
                "sha256": ADDITIONAL_FAILURE_RUN_SHA256,
                "used_as_generation_input": False,
            },
        },
        "summary": {
            "case_count": 1,
            "target_count": 1,
            "model_counts": {MODEL_ID: 1},
            "source_status_counts": {"provider-failed": 1},
        },
        "cases": [published],
    }


def write_selection(document: dict[str, Any], *, root: Path = ROOT) -> Path:
    root = root.resolve()
    case = document["cases"][0]
    atomic_create_json(root / REPAIR_FEEDBACK_REL, case["repair_feedback"])
    if canonical_sha256(read_json(root / REPAIR_FEEDBACK_REL)) != case["repair_feedback_sha256"]:
        raise TuneV7FilterPlanningError("Repair feedback digest changed")
    atomic_create_json(root / SELECTION_REL, document)
    return root / SELECTION_REL


def load_selection(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    document = read_json(root / SELECTION_REL)
    if (
        not isinstance(document, dict)
        or document.get("manifest_role")
        != "clipmaker-lite-tune-v7-filter-retry-selection"
        or document.get("batch_id") != BATCH_ID
        or document.get("summary")
        != {
            "case_count": 1,
            "target_count": 1,
            "model_counts": {MODEL_ID: 1},
            "source_status_counts": {"provider-failed": 1},
        }
        or document.get("policy", {}).get("canonical_full_source_only") is not True
        or document.get("policy", {}).get("disable_provider_safety_filters") is not False
        or document.get("policy", {}).get("fallback") is not False
        or document.get("policy", {}).get("compositor") is not False
        or document.get("policy", {}).get("one_new_paid_attempt_only") is not True
        or document.get("diagnosis", {}).get("type") != "suspected_source_filter"
        or document.get("diagnosis", {}).get("failed_source_variants")
        != list(FAILED_SOURCE_VARIANTS)
        or len(document.get("cases", [])) != 1
    ):
        raise TuneV7FilterPlanningError("Unexpected v7 filter selection identity")
    case = document["cases"][0]
    feedback = read_json(root / case["repair_feedback_path"])
    if (
        case.get("case_id") != CASE_ID
        or case.get("run_id")
        != f"{BATCH_ID}-{case.get('article_slug')}-{case.get('source', {}).get('image_id')}"
        or case.get("selected_model_ids") != [MODEL_ID]
        or feedback != case.get("repair_feedback")
        or canonical_sha256(feedback) != case.get("repair_feedback_sha256")
        or sha256_file(root / FORENSIC_MANIFEST_REL) != FORENSIC_MANIFEST_SHA256
    ):
        raise TuneV7FilterPlanningError("V7 filter selection binding changed")
    return document


def _inputs_match_case(inputs: Any, case: dict[str, Any]) -> bool:
    if not isinstance(inputs, dict):
        return False
    source = inputs.get("source_image")
    context = inputs.get("article_context")
    return (
        isinstance(source, dict)
        and source.get("path") == case["source"]["path"]
        and source.get("sha256") == CANONICAL_SOURCE_SHA256
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
            or repair.get("path") != case["repair_feedback_path"]
            or repair.get("canonical_sha256") != case["repair_feedback_sha256"]
        ):
            raise TuneV7FilterPlanningError("Prepared v7 filter job changed")
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
        and repair.get("path") == case["repair_feedback_path"]
        and repair.get("canonical_sha256") == case["repair_feedback_sha256"]
    )


def validate_result(result: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    models = result.get("models")
    intent = result.get("analysis", {}).get("structured_intent")
    if (
        not isinstance(models, list)
        or len(models) != 1
        or models[0].get("model_id") != MODEL_ID
        or models[0].get("execution_mode") != "i2v"
        or models[0].get("positive_prompt") != EXACT_POSITIVE_PROMPT
        or models[0].get("negative_prompt") is not None
        or not isinstance(intent, dict)
        or intent.get("rendering_strategy") != "camera-only"
    ):
        raise TuneV7FilterPlanningError(
            f"V7 Lite result is not the exact neutral camera-only prompt: {case['case_id']}"
        )
    runtime = models[0].get("runtime")
    if (
        not isinstance(runtime, dict)
        or runtime.get("duration_seconds") != 4
        or runtime.get("resolution") != "1080p"
        or runtime.get("generate_audio") is not False
        or runtime.get("provider") != "google-vertex"
        or runtime.get("prompt_expansion")
        != {"parameter": "enhancePrompt", "value": True}
    ):
        raise TuneV7FilterPlanningError("V7 Veo runtime changed")
    return models[0]


def run_case(
    case: dict[str, Any],
    *,
    root: Path = ROOT,
    author_model: str | None = None,
    timeout: int = 900,
) -> str:
    result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
    if result_is_verified(case, root=root):
        validate_result(read_json(result_path), case)
        return "already-complete"
    runner.run_agent(
        root,
        case["run_id"],
        author_model=author_model,
        timeout=timeout,
        external_processing_approved=True,
    )
    if not result_is_verified(case, root=root):
        raise TuneV7FilterPlanningError("V7 Lite provenance failed")
    validate_result(read_json(result_path), case)
    return "completed"


def build_prompt_manifest(selection: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    case = selection["cases"][0]
    if not result_is_verified(case, root=root):
        raise TuneV7FilterPlanningError("V7 filter result is not verified")
    result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
    result = read_json(result_path)
    model = validate_result(result, case)
    target = copy.deepcopy(case["targets"][0])
    target["tuned"] = {
        "execution_mode": "i2v",
        "scene_plan": model["scene_plan"],
        "positive_prompt": model["positive_prompt"],
        "negative_prompt": None,
        "runtime": copy.deepcopy(model["runtime"]),
    }
    existing_path = root / PROMPT_MANIFEST_REL
    generated_at = utc_now()
    if existing_path.exists():
        existing = read_json(existing_path)
        if existing.get("batch_id") != BATCH_ID or not isinstance(existing.get("generated_at"), str):
            raise TuneV7FilterPlanningError("Existing v7 prompt manifest identity changed")
        generated_at = existing["generated_at"]
    published_case = {
        **{
            key: copy.deepcopy(value)
            for key, value in case.items()
            if key not in {"repair_feedback", "targets"}
        },
        "planning": {
            "run_id": case["run_id"],
            "result_path": relative(result_path, root),
            "result_sha256": sha256_file(result_path),
            "provenance": runner.provenance_summary(root, case["run_id"]),
            "structured_intent": copy.deepcopy(result["analysis"]["structured_intent"]),
            "image_reading": result["analysis"]["image_reading"],
            "article_context": result["analysis"]["article_context"],
            "repair_feedback_path": case["repair_feedback_path"],
            "repair_feedback_sha256": case["repair_feedback_sha256"],
        },
        "targets": [target],
    }
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v7-filter-retry-planning",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "contract_version": EXPECTED_CONTRACT_VERSION,
        "generated_at": generated_at,
        "scope": {
            "selection_path": SELECTION_REL.as_posix(),
            "selection_sha256": sha256_file(root / SELECTION_REL),
            "case_count": 1,
            "target_count": 1,
            "required_execution_mode": "i2v",
            "required_rendering_strategy": "camera-only",
            "canonical_full_source_only": True,
            "source_transform": None,
            "disable_provider_safety_filters": False,
            "fallback": False,
            "compositor": False,
            "video_generation": False,
            "s3_upload": False,
        },
        "diagnosis": copy.deepcopy(selection["diagnosis"]),
        "lineage": copy.deepcopy(selection["lineage"]),
        "summary": copy.deepcopy(selection["summary"]),
        "cases": [published_case],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "prepare", "run", "build", "all"))
    parser.add_argument("--author-model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--allow-external-processing", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"plan", "all"}:
            print(relative(write_selection(build_selection_document(root=root), root=root), root))
        selection = load_selection(root=root)
        case = selection["cases"][0]
        if args.command in {"prepare", "all"}:
            print(f"{CASE_ID}: {prepare_case(case, root=root)}")
        if args.command in {"run", "all"}:
            if not args.allow_external_processing:
                raise TuneV7FilterPlanningError("run/all requires --allow-external-processing")
            print(
                f"{CASE_ID}: {run_case(case, root=root, author_model=args.author_model, timeout=args.timeout)}"
            )
        if args.command in {"build", "all"}:
            manifest = build_prompt_manifest(selection, root=root)
            atomic_create_json(root / PROMPT_MANIFEST_REL, manifest)
            print(PROMPT_MANIFEST_REL.as_posix())
        return 0
    except (TuneV7FilterPlanningError, runner.LiteRunnerError) as exc:
        print(f"Tune v7 filter planning error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
