#!/usr/bin/env python3
"""Prepare three immutable Clipmaker Lite prompt experiments for Tune 07#06.

The three runs use the same canonical full source, model, runtime and provider
seed.  Only the short motion-only positive prompt changes.  Every prompt is
authored and stamped by an isolated Clipmaker Lite runner run; this module does
not call a video provider.
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
from scripts import clipmaker_lite_tune_v7_filter_retry_planning as v7_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v7_veo_filter_retry_video_pipeline as v7_video  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
BATCH_ID = "promopages-10060-tune-prompts-20260812-v5-r9"
EXPECTED_CONTRACT_VERSION = "2.3.0"
CASE_ID = "07#06"
MODEL_ID = "google/veo-3.1-lite"
EVALUATION_ID = f"{CASE_ID}::{MODEL_ID}"
CANONICAL_SOURCE_SHA256 = v7_planning.CANONICAL_SOURCE_SHA256
SHARED_PROVIDER_SEED = 20260812

SOURCE_PROMPT_MANIFEST_REL = v7_planning.PROMPT_MANIFEST_REL
SOURCE_PROMPT_MANIFEST_SHA256 = v7_video.PROMPT_MANIFEST_SHA256
SOURCE_GENERATION_MANIFEST_REL = v7_video.GENERATION_MANIFEST_REL
SOURCE_GENERATION_MANIFEST_SHA256 = (
    "937d447c2df3f5f6dd985a9e3493650d9f500faa6dc7892a2c02285609b8c80a"
)
SOURCE_RUN_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-tune-videos-20260812-v7/"
    "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"
)
SOURCE_RUN_SHA256 = (
    "6cfe970fc11bdf2cd55cb9248f8a8435e94742bb3aa658ec622082ab7cfc31b7"
)

# The semantics stay intentionally close: each prompt requests one smooth,
# centered inward camera treatment.  The lexical form is the controlled factor.
VARIANTS: tuple[dict[str, str], ...] = (
    {
        "variant_id": "minimal-zoom",
        "positive_prompt": "Slow centered zoom in.",
        "rationale": (
            "Minimal lexical baseline: inward motion only, with no scene nouns, "
            "subject references, preservation prose, or numeric endpoint."
        ),
        "controlled_factor": "minimal imperative wording",
    },
    {
        "variant_id": "camera-forward",
        "positive_prompt": (
            "The camera moves slowly straight forward, centered and steady "
            "throughout the shot."
        ),
        "rationale": (
            "Physical-camera formulation: names a steady trajectory but no source "
            "entity, scene meaning, body, device, health topic, or brand."
        ),
        "controlled_factor": "explicit physical camera trajectory",
    },
    {
        "variant_id": "framing-endpoint",
        "positive_prompt": (
            "Smoothly tighten the centered framing by about 5% from start to finish."
        ),
        "rationale": (
            "Image-space formulation: states the same small inward endpoint without "
            "naming a camera path or any source entity."
        ),
        "controlled_factor": "image-space endpoint wording",
    },
)

BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
SELECTION_REL = BATCH_ROOT_REL / "selection.json"
PROMPT_MANIFEST_REL = BATCH_ROOT_REL / "prompt-manifest.json"


class TuneV8PlanningError(RuntimeError):
    """The three-prompt experiment failed an immutable or provenance gate."""


read_json = v7_planning.read_json
sha256_file = v7_planning.sha256_file
canonical_sha256 = v7_planning.canonical_sha256
atomic_create_json = v7_planning.atomic_create_json
relative = v7_planning.relative
utc_now = v7_planning.utc_now


def _variant(variant_id: str) -> dict[str, str]:
    matches = [item for item in VARIANTS if item["variant_id"] == variant_id]
    if len(matches) != 1:
        raise TuneV8PlanningError(f"Unknown Veo prompt variant: {variant_id}")
    return matches[0]


def _feedback_path(variant_id: str) -> Path:
    return BATCH_ROOT_REL / "repair-feedback" / f"07-06-{variant_id}.json"


def repair_feedback(variant: dict[str, str]) -> dict[str, Any]:
    prompt = variant["positive_prompt"]
    return {
        MODEL_ID: {
            "evaluation_id": EVALUATION_ID,
            "outcome": "worse",
            "review_note": (
                "This is one controlled, policy-compliant prompt experiment after "
                "repeated terminal provider no-output receipts. Author the "
                "positive_prompt exactly as supplied below. Keep it camera-only and "
                "do not name or describe any visible subject, body part, device, "
                "activity, relationship, health topic, or brand."
            ),
            "evidence_strength": "explicit",
            "failure_codes": ["provider_no_output"],
            "required_execution_mode": "i2v",
            "fallback_policy": "none",
            "camera_repair": {
                "move": "push-in",
                "focal_target": "the current framing",
                "target_retention": "centered",
                "max_screen_travel_percent": 5,
                "reveal_unseen_space": False,
            },
            "preservation": {
                "entity_counts": ["Keep source entity counts unchanged."],
                "topology_anchors": [
                    f'The positive_prompt must be exactly: "{prompt}"'
                ],
                "rigid_regions": ["all source-defined rigid regions"],
                "contacts": ["Do not introduce or change source contacts."],
                "must_remain_visible": ["the current framing"],
            },
        }
    }


def _load_source_case(*, root: Path) -> dict[str, Any]:
    path = root / SOURCE_PROMPT_MANIFEST_REL
    if sha256_file(path) != SOURCE_PROMPT_MANIFEST_SHA256:
        raise TuneV8PlanningError("Frozen V7 prompt manifest changed")
    document = read_json(path)
    if (
        not isinstance(document, dict)
        or document.get("manifest_role")
        != "clipmaker-lite-tune-v7-filter-retry-planning"
        or document.get("batch_id") != v7_planning.BATCH_ID
        or document.get("contract_version") != EXPECTED_CONTRACT_VERSION
        or len(document.get("cases", [])) != 1
    ):
        raise TuneV8PlanningError("Unexpected V7 prompt lineage")
    case = document["cases"][0]
    source = case.get("source")
    if (
        case.get("case_id") != CASE_ID
        or not isinstance(source, dict)
        or source.get("sha256") != CANONICAL_SOURCE_SHA256
        or source.get("width") != 2400
        or source.get("height") != 1600
        or len(case.get("targets", [])) != 1
    ):
        raise TuneV8PlanningError("Canonical V7 source binding changed")
    return case


def _load_source_failure(*, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = root / SOURCE_GENERATION_MANIFEST_REL
    run_path = root / SOURCE_RUN_REL
    if sha256_file(manifest_path) != SOURCE_GENERATION_MANIFEST_SHA256:
        raise TuneV8PlanningError("Frozen V7 generation manifest changed")
    if sha256_file(run_path) != SOURCE_RUN_SHA256:
        raise TuneV8PlanningError("Frozen V7 terminal receipt changed")
    manifest = read_json(manifest_path)
    run = read_json(run_path)
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    if (
        manifest.get("manifest_role") != v7_video.MANIFEST_ROLE
        or manifest.get("batch_id") != v7_video.BATCH_ID
        or not isinstance(outputs, list)
        or len(outputs) != 1
        or outputs[0].get("status") != "provider-failed"
        or outputs[0].get("run_path") != SOURCE_RUN_REL.as_posix()
        or run.get("status") != "provider-failed"
        or run.get("submission_count") != 1
        or run.get("provider_may_be_active") is not False
        or run.get("terminal_no_output_stop_applied") is not True
        or not isinstance(run.get("provider_job_id"), str)
        or not run["provider_job_id"]
        or "no output" not in str(run.get("error", "")).lower()
        or run.get("request", {}).get("seed") != v7_video.SEED
        or run.get("request", {}).get("frame_images", [{}])[0]
        .get("image_url", {})
        .get("url")
        is None
    ):
        raise TuneV8PlanningError("V7 terminal no-output evidence changed")
    return outputs[0], run


def build_selection_document(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    source_case = _load_source_case(root=root)
    source_output, source_run = _load_source_failure(root=root)
    source_target = source_case["targets"][0]
    experiments: list[dict[str, Any]] = []
    for variant in VARIANTS:
        feedback = repair_feedback(variant)
        try:
            normalized = runner.validate_repair_feedback_models(
                feedback,
                [MODEL_ID],
                f"07#06 Veo experiment {variant['variant_id']}",
            )
        except runner.LiteRunnerError as exc:
            raise TuneV8PlanningError(str(exc)) from exc
        if normalized != feedback:
            raise TuneV8PlanningError("Repair feedback normalization changed")
        feedback_path = _feedback_path(variant["variant_id"])
        experiments.append(
            {
                "experiment_id": f"{EVALUATION_ID}::{variant['variant_id']}",
                "variant_id": variant["variant_id"],
                "controlled_factor": variant["controlled_factor"],
                "rationale": variant["rationale"],
                "positive_prompt": variant["positive_prompt"],
                "shared_provider_seed": SHARED_PROVIDER_SEED,
                "run_id": (
                    f"{BATCH_ID}-{source_case['article_slug']}-"
                    f"{source_case['source']['image_id']}-{variant['variant_id']}"
                ),
                "repair_feedback_path": feedback_path.as_posix(),
                "repair_feedback_sha256": canonical_sha256(feedback),
                "repair_feedback": feedback,
            }
        )
    published_case = {
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
        "source_provider_attempt": {
            "batch_id": v7_video.BATCH_ID,
            "provider_run_id": source_output["provider_run_id"],
            "status": "provider-failed",
            "run_path": SOURCE_RUN_REL.as_posix(),
            "run_sha256": SOURCE_RUN_SHA256,
            "provider_job_id": source_run["provider_job_id"],
            "provider_may_be_active": False,
            "submission_count": 1,
            "terminal_no_output_stop_applied": True,
        },
        "experiments": experiments,
    }
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v8-veo-prompt-experiment-selection",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "policy": {
            "selection": "three user-authorized controlled Veo prompt experiments",
            "required_execution_mode": "i2v",
            "required_rendering_strategy": "camera-only",
            "prompt_author": "clipmaker-lite",
            "hand_authored_provider_prompt": False,
            "canonical_full_source_only": True,
            "source_transform": None,
            "disable_provider_safety_filters": False,
            "fallback": False,
            "compositor": False,
            "s3_upload": False,
            "one_paid_submit_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
            "terminal_no_output_stop_per_experiment": True,
            "capture_provider_safety_diagnostics_if_present": True,
        },
        "experiment_design": {
            "hypothesis": (
                "If wording contributes to the terminal no-output result, one or more "
                "semantically similar motion-only phrasings may differ while source, "
                "runtime, seed, and safety settings remain fixed."
            ),
            "inference_limit": (
                "Three outcomes cannot identify a safety category and cannot prove that "
                "the prompt, rather than the source-image classifier, caused filtering."
            ),
            "fixed_factors": [
                "canonical source SHA-256",
                "google/veo-3.1-lite route",
                "4 second 1080p runtime",
                "enhancePrompt=true",
                f"seed={SHARED_PROVIDER_SEED}",
                "provider safety enabled",
            ],
            "changed_factor": "motion-only positive-prompt formulation",
            "variant_order": [item["variant_id"] for item in VARIANTS],
        },
        "diagnosis": {
            "type": "suspected_source_filter",
            "classification": "suspected-source-image-safety-false-positive",
            "evidence_strength": "strong-indirect",
            "person_preserving_provider_failures_at_least": 12,
            "provider_support_code_available": False,
            "active_source_sha256": CANONICAL_SOURCE_SHA256,
            "active_source_transform": None,
        },
        "lineage": {
            "source_prompt_manifest": {
                "path": SOURCE_PROMPT_MANIFEST_REL.as_posix(),
                "sha256": SOURCE_PROMPT_MANIFEST_SHA256,
                "batch_id": v7_planning.BATCH_ID,
            },
            "source_generation_manifest": {
                "path": SOURCE_GENERATION_MANIFEST_REL.as_posix(),
                "sha256": SOURCE_GENERATION_MANIFEST_SHA256,
                "batch_id": v7_video.BATCH_ID,
                "receipts_mutated": False,
            },
            "source_terminal_run": {
                "path": SOURCE_RUN_REL.as_posix(),
                "sha256": SOURCE_RUN_SHA256,
            },
        },
        "summary": {
            "case_count": 1,
            "experiment_count": 3,
            "provider_request_count": 3,
            "model_counts": {MODEL_ID: 3},
        },
        "cases": [published_case],
    }


def write_selection(document: dict[str, Any], *, root: Path = ROOT) -> Path:
    root = root.resolve()
    for experiment in document["cases"][0]["experiments"]:
        path = root / experiment["repair_feedback_path"]
        atomic_create_json(path, experiment["repair_feedback"])
        if canonical_sha256(read_json(path)) != experiment["repair_feedback_sha256"]:
            raise TuneV8PlanningError("Repair feedback digest changed")
    atomic_create_json(root / SELECTION_REL, document)
    return root / SELECTION_REL


def load_selection(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    document = read_json(root / SELECTION_REL)
    cases = document.get("cases") if isinstance(document, dict) else None
    if (
        document.get("manifest_role")
        != "clipmaker-lite-tune-v8-veo-prompt-experiment-selection"
        or document.get("batch_id") != BATCH_ID
        or document.get("summary", {}).get("experiment_count") != 3
        or document.get("policy", {}).get("canonical_full_source_only") is not True
        or document.get("policy", {}).get("source_transform") is not None
        or document.get("policy", {}).get("disable_provider_safety_filters") is not False
        or document.get("policy", {}).get("fallback") is not False
        or document.get("policy", {}).get("compositor") is not False
        or not isinstance(cases, list)
        or len(cases) != 1
        or len(cases[0].get("experiments", [])) != 3
    ):
        raise TuneV8PlanningError("Unexpected V8 prompt experiment selection")
    case = cases[0]
    if (
        case.get("case_id") != CASE_ID
        or case.get("source", {}).get("sha256") != CANONICAL_SOURCE_SHA256
        or [item.get("variant_id") for item in case["experiments"]]
        != [item["variant_id"] for item in VARIANTS]
    ):
        raise TuneV8PlanningError("V8 case or variant binding changed")
    for experiment in case["experiments"]:
        variant = _variant(experiment["variant_id"])
        feedback = read_json(root / experiment["repair_feedback_path"])
        if (
            experiment.get("positive_prompt") != variant["positive_prompt"]
            or experiment.get("shared_provider_seed") != SHARED_PROVIDER_SEED
            or feedback != experiment.get("repair_feedback")
            or canonical_sha256(feedback) != experiment.get("repair_feedback_sha256")
        ):
            raise TuneV8PlanningError("V8 experiment binding changed")
    return document


def _inputs_match(inputs: Any, case: dict[str, Any]) -> bool:
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


def prepare_experiment(
    case: dict[str, Any], experiment: dict[str, Any], *, root: Path = ROOT
) -> str:
    run_id = experiment["run_id"]
    directory = root / runner.OUTPUT_NAMESPACE / run_id
    if directory.exists():
        job, selection, _directory = runner.validate_prepared_job(root, run_id)
        repair = job.get("inputs", {}).get("repair_feedback")
        if (
            [item["model_id"] for item in selection["selected_models"]] != [MODEL_ID]
            or not _inputs_match(job.get("inputs"), case)
            or repair.get("path") != experiment["repair_feedback_path"]
            or repair.get("canonical_sha256")
            != experiment["repair_feedback_sha256"]
        ):
            raise TuneV8PlanningError("Prepared V8 Lite job changed")
        return "already-prepared"
    runner.prepare_run(
        root,
        run_id,
        case["source"]["path"],
        case["context_path"],
        image_id=case["source"]["image_id"],
        model_ids=[MODEL_ID],
        user_direction=None,
        repair_feedback_path=experiment["repair_feedback_path"],
    )
    return "prepared"


def result_is_verified(
    case: dict[str, Any], experiment: dict[str, Any], *, root: Path = ROOT
) -> bool:
    result_path = root / runner.OUTPUT_NAMESPACE / experiment["run_id"] / "result.json"
    if not result_path.is_file() or result_path.is_symlink():
        return False
    summary = runner.provenance_summary(root, experiment["run_id"])
    result = read_json(result_path)
    repair = result.get("inputs", {}).get("repair_feedback")
    return (
        summary.get("verified") is True
        and summary.get("contract_version") == EXPECTED_CONTRACT_VERSION
        and summary.get("models") == [MODEL_ID]
        and _inputs_match(result.get("inputs"), case)
        and repair.get("path") == experiment["repair_feedback_path"]
        and repair.get("canonical_sha256") == experiment["repair_feedback_sha256"]
    )


def validate_result(
    result: dict[str, Any], experiment: dict[str, Any]
) -> dict[str, Any]:
    models = result.get("models")
    intent = result.get("analysis", {}).get("structured_intent")
    if (
        not isinstance(models, list)
        or len(models) != 1
        or models[0].get("model_id") != MODEL_ID
        or models[0].get("execution_mode") != "i2v"
        or models[0].get("positive_prompt") != experiment["positive_prompt"]
        or models[0].get("negative_prompt") is not None
        or not isinstance(intent, dict)
        or intent.get("rendering_strategy") != "camera-only"
    ):
        raise TuneV8PlanningError(
            f"Lite did not preserve exact V8 prompt: {experiment['variant_id']}"
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
        raise TuneV8PlanningError("V8 Veo runtime changed")
    return models[0]


def run_experiment(
    case: dict[str, Any],
    experiment: dict[str, Any],
    *,
    root: Path = ROOT,
    author_model: str | None = None,
    timeout: int = 900,
) -> str:
    result_path = root / runner.OUTPUT_NAMESPACE / experiment["run_id"] / "result.json"
    if result_is_verified(case, experiment, root=root):
        validate_result(read_json(result_path), experiment)
        return "already-complete"
    runner.run_agent(
        root,
        experiment["run_id"],
        author_model=author_model,
        timeout=timeout,
        external_processing_approved=True,
    )
    if not result_is_verified(case, experiment, root=root):
        raise TuneV8PlanningError("V8 Lite provenance failed")
    validate_result(read_json(result_path), experiment)
    return "completed"


def build_prompt_manifest(
    selection: dict[str, Any], *, root: Path = ROOT
) -> dict[str, Any]:
    case = selection["cases"][0]
    published_experiments: list[dict[str, Any]] = []
    for experiment in case["experiments"]:
        if not result_is_verified(case, experiment, root=root):
            raise TuneV8PlanningError("V8 Lite result is not provenance-verified")
        result_path = root / runner.OUTPUT_NAMESPACE / experiment["run_id"] / "result.json"
        result = read_json(result_path)
        model = validate_result(result, experiment)
        published_experiments.append(
            {
                **{
                    key: copy.deepcopy(value)
                    for key, value in experiment.items()
                    if key != "repair_feedback"
                },
                "planning": {
                    "run_id": experiment["run_id"],
                    "result_path": relative(result_path, root),
                    "result_sha256": sha256_file(result_path),
                    "provenance": runner.provenance_summary(
                        root, experiment["run_id"]
                    ),
                    "structured_intent": copy.deepcopy(
                        result["analysis"]["structured_intent"]
                    ),
                    "image_reading": copy.deepcopy(result["analysis"]["image_reading"]),
                    "article_context": result["analysis"]["article_context"],
                    "repair_feedback_path": experiment["repair_feedback_path"],
                    "repair_feedback_sha256": experiment["repair_feedback_sha256"],
                },
                "tuned": {
                    "execution_mode": "i2v",
                    "scene_plan": model["scene_plan"],
                    "positive_prompt": model["positive_prompt"],
                    "negative_prompt": None,
                    "runtime": copy.deepcopy(model["runtime"]),
                },
            }
        )
    existing_path = root / PROMPT_MANIFEST_REL
    generated_at = utc_now()
    if existing_path.exists():
        existing = read_json(existing_path)
        if (
            existing.get("batch_id") != BATCH_ID
            or not isinstance(existing.get("generated_at"), str)
        ):
            raise TuneV8PlanningError("Existing V8 prompt manifest changed")
        generated_at = existing["generated_at"]
    published_case = {
        **{
            key: copy.deepcopy(value)
            for key, value in case.items()
            if key != "experiments"
        },
        "experiments": published_experiments,
    }
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v8-veo-prompt-experiment-planning",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "contract_version": EXPECTED_CONTRACT_VERSION,
        "generated_at": generated_at,
        "scope": {
            "selection_path": SELECTION_REL.as_posix(),
            "selection_sha256": sha256_file(root / SELECTION_REL),
            "case_count": 1,
            "experiment_count": 3,
            "provider_request_count": 3,
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
        "experiment_design": copy.deepcopy(selection["experiment_design"]),
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
            print(
                relative(
                    write_selection(build_selection_document(root=root), root=root),
                    root,
                )
            )
        selection = load_selection(root=root)
        case = selection["cases"][0]
        if args.command in {"prepare", "all"}:
            for experiment in case["experiments"]:
                print(
                    f"{experiment['variant_id']}: "
                    f"{prepare_experiment(case, experiment, root=root)}"
                )
        if args.command in {"run", "all"}:
            if not args.allow_external_processing:
                raise TuneV8PlanningError("run/all requires --allow-external-processing")
            for experiment in case["experiments"]:
                print(
                    f"{experiment['variant_id']}: "
                    f"{run_experiment(case, experiment, root=root, author_model=args.author_model, timeout=args.timeout)}"
                )
        if args.command in {"build", "all"}:
            manifest = build_prompt_manifest(selection, root=root)
            atomic_create_json(root / PROMPT_MANIFEST_REL, manifest)
            print(PROMPT_MANIFEST_REL.as_posix())
        return 0
    except (TuneV8PlanningError, runner.LiteRunnerError) as exc:
        print(f"Tune V8 Veo prompt planning error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
