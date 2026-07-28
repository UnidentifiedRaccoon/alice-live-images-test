#!/usr/bin/env python3
"""Fail-closed non-loop Wan 2.7 smooth-motion experiment for case 21.

The coordinator binds four independently attested Clipmaker Lite planning runs
to four immutable Atlas Cloud entries.  It deliberately keeps the canonical
Wan 2.7 transport: one first frame, no last frame, and no loop field.  Two
additional $0.50 attempts are budgeted only as explicit contingency namespaces;
they are never materialized or submitted by this coordinator.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_case21_loop_experiment as loop  # noqa: E402
from scripts import clipmaker_lite_case21_pipeline as case21  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
EXPERIMENT_ID = "promopages-9930-case21-wan27-smooth-20260728-v1"
PROVIDER_BATCH_ID = "promopages-9930-case21-wan27-smooth-provider-20260728-v1"
EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / EXPERIMENT_ID
INVENTORY_PATH = EXPERIMENT_ROOT / "inventory.json"
GENERATION_MANIFEST_PATH = EXPERIMENT_ROOT / "generation-manifest.json"
EXPERIMENT_MANIFEST_PATH = EXPERIMENT_ROOT / "experiment-manifest.json"

MODEL_ID = native.WAN_27_MODEL_ID
MODEL_IDS = (MODEL_ID,)
SOURCE_URL = case21.EXPECTED_ORIG_URL
SOURCE_SHA256 = case21.EXPECTED_SOURCE_SHA256
CONTEXT_SHA256 = case21.EXPECTED_CONTEXT_SHA256
SOURCE_WIDTH = 1024
SOURCE_HEIGHT = 1024
REQUEST_FINGERPRINT_VERSION = 2

HARD_BUDGET_CAP_USD = Decimal("3.00")
RESERVATION_PER_ENTRY_USD = Decimal("0.50")
INITIAL_ENTRY_COUNT = 4
INITIAL_RESERVED_USD = Decimal("2.00")
CONTINGENCY_ATTEMPT_COUNT = 2
CONTINGENCY_RESERVED_USD = Decimal("1.00")
MAXIMUM_PROVIDER_ENTRIES = 6

CONTROL_PATHS = {
    **loop.CONTROL_PATHS,
    "loop_experiment": loop.EXPERIMENT_ROOT,
}

TRANSPORT_PROFILE = {
    "profile": "non-loop-smooth-motion",
    "canonical_lite_planning": True,
    "canonical_lite_provider_runtime": True,
    "first_frame_only": True,
    "last_frame_is_source": False,
    "loop": False,
}


class SmoothExperimentError(RuntimeError):
    """A fail-closed, user-actionable smooth experiment failure."""


@dataclass(frozen=True)
class Variant:
    variant_id: str
    planning_run_id: str
    strategy: str
    negative_policy: str
    result_sha256: str


VARIANTS = (
    Variant(
        "low-amplitude-continuous",
        "promopages-9930-case21-wan27-smooth-low-amplitude-continuous-20260728-v3",
        "continuous low-amplitude motion",
        "required-observed-repair",
        "441894fee34c64eee91529f3f98039adf180f257092cc2207a69f7180440157e",
    ),
    Variant(
        "staggered-ease",
        "promopages-9930-case21-wan27-smooth-staggered-ease-20260728-v4",
        "staggered eased motion",
        "must-be-null",
        "ac773559abba5386897ef830fbbf1ec186d3c58e3149d2b4f605c026bca7a5aa",
    ),
    Variant(
        "left-to-right-flow",
        "promopages-9930-case21-wan27-smooth-left-to-right-flow-20260728-v3",
        "left-to-right visual flow",
        "must-be-null",
        "6ee108f3cfbeda317ecc861288ce5a6148049f87e2eb4807cf4b6ca995682f8b",
    ),
    Variant(
        "preservation-smooth-repair",
        "promopages-9930-case21-wan27-smooth-preservation-smooth-repair-20260728-v3",
        "smooth motion with observed-fidelity preservation repair",
        "required-observed-repair",
        "e5a115bb7aeaaee815f5656adde2144a6b0453e72e09128b91deadbfc3a71d3b",
    ),
)
VARIANT_BY_ID = {variant.variant_id: variant for variant in VARIANTS}


@dataclass(frozen=True)
class SmoothSample(native.Sample):
    variant_id: str
    lite_run_id: str

    @property
    def planning_run_id(self) -> str:
        return self.lite_run_id


def _sample(variant: Variant) -> SmoothSample:
    return SmoothSample(
        sample_id=f"21-maier-04-smooth-{variant.variant_id}",
        article_slug=case21.ARTICLE_SLUG,
        image_id=case21.IMAGE_ID,
        filename=case21.IMAGE_FILENAME,
        source_sha256=SOURCE_SHA256,
        width=SOURCE_WIDTH,
        height=SOURCE_HEIGHT,
        variant_id=variant.variant_id,
        lite_run_id=variant.planning_run_id,
    )


SAMPLES = tuple(_sample(variant) for variant in VARIANTS)
ENTRIES = tuple(native.Entry(sample, MODEL_ID) for sample in SAMPLES)
ENTRY_BY_VARIANT = {entry.sample.variant_id: entry for entry in ENTRIES}

_NATIVE_PROMPT_ARTIFACT = native.prompt_artifact
_NATIVE_INITIAL_RUN = native.initial_run


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SmoothExperimentError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SmoothExperimentError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    try:
        return loop.sha256_file(path)
    except Exception as exc:
        raise SmoothExperimentError(str(exc)) from exc


def sha256_text(value: str) -> str:
    return loop.sha256_text(value)


def control_snapshots(root: Path = ROOT) -> dict[str, dict[str, str]]:
    snapshots: dict[str, dict[str, str]] = {}
    for name, path in CONTROL_PATHS.items():
        try:
            digest = loop.content_tree_digest(path, root)
        except Exception as exc:
            raise SmoothExperimentError(str(exc)) from exc
        snapshots[name] = {"path": path.as_posix(), "sha256": digest}
    return snapshots


def validate_route() -> dict[str, Any]:
    try:
        route = loop.validate_route()
    except Exception as exc:
        raise SmoothExperimentError(str(exc)) from exc
    if route.get("capacity") != 3 or route.get("provider_key") != "atlas-cloud":
        raise SmoothExperimentError("Exact Wan 2.7 route changed")
    if transport.REQUEST_FINGERPRINT_VERSION != REQUEST_FINGERPRINT_VERSION:
        raise SmoothExperimentError("Request fingerprint version changed")
    return route


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise SmoothExperimentError(f"Invalid USD budget: {value!r}") from exc
    if budget < INITIAL_RESERVED_USD:
        raise SmoothExperimentError(
            f"Budget ${budget:.2f} is below the ${INITIAL_RESERVED_USD:.2f} initial reservation"
        )
    if budget > HARD_BUDGET_CAP_USD:
        raise SmoothExperimentError(
            f"Budget ${budget:.2f} exceeds the ${HARD_BUDGET_CAP_USD:.2f} hard cap"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except SmoothExperimentError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def cost_document(budget: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(budget)
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "reservation_per_wan27_entry_usd": float(RESERVATION_PER_ENTRY_USD),
        "initial_entry_count": INITIAL_ENTRY_COUNT,
        "initial_reserved_usd": float(INITIAL_RESERVED_USD),
        "contingency_attempt_count": CONTINGENCY_ATTEMPT_COUNT,
        "contingency_reserved_usd": float(CONTINGENCY_RESERVED_USD),
        "maximum_provider_entries": MAXIMUM_PROVIDER_ENTRIES,
        "admitted_provider_entries": INITIAL_ENTRY_COUNT,
        "contingency_entries_materialized": 0,
        "maximum_submissions_per_entry": 1,
        "automatic_paid_retries": False,
        "provider_unit_costs_asserted": False,
        "actual_billing_available": False,
        "note": (
            "Four immutable initial jobs reserve $2.00. Up to two explicit $0.50 "
            "contingency attempts require new provider identities and are not "
            "materialized or submitted by this coordinator."
        ),
    }


def _variant(entry: native.Entry) -> Variant:
    sample = entry.sample
    if not isinstance(sample, SmoothSample):
        raise SmoothExperimentError("Smooth entry uses an unexpected sample type")
    variant = VARIANT_BY_ID.get(sample.variant_id)
    if variant is None or entry.model_id != MODEL_ID:
        raise SmoothExperimentError("Entry is outside the exact four-entry Wan 2.7 matrix")
    return variant


def _provider_run_id(entry: native.Entry) -> str:
    _variant(entry)
    return f"{PROVIDER_BATCH_ID}-{entry.sample.sample_id}-{native.MODEL_SUFFIXES[MODEL_ID]}"


def artifact_paths(entry: native.Entry, root: Path = ROOT) -> dict[str, Path]:
    variant = _variant(entry)
    base = EXPERIMENT_ROOT / "videos" / variant.variant_id / native.MODEL_DIRECTORIES[MODEL_ID]
    return {
        "directory": root / base,
        "prompt": root / base / f"{case21.IMAGE_ID}.prompt.json",
        "run": root / base / f"{case21.IMAGE_ID}.run.json",
        "video": root / base / f"{case21.IMAGE_ID}.mp4",
    }


def provider_sample(entry: native.Entry) -> dict[str, Any]:
    _variant(entry)
    return {
        "sample_id": entry.sample.sample_id,
        "article_slug": case21.ARTICLE_SLUG,
        "image_id": case21.IMAGE_ID,
        "image_number": case21.IMAGE_ID,
        "source_path": case21.SOURCE_PATH.as_posix(),
        "source_url": SOURCE_URL,
        "sha256": SOURCE_SHA256,
        "width": SOURCE_WIDTH,
        "height": SOURCE_HEIGHT,
    }


def load_experiment_job(entry: native.Entry, root: Path = ROOT) -> native.LiteJob:
    variant = _variant(entry)
    try:
        summary = runner.provenance_summary(root, variant.planning_run_id)
    except Exception as exc:
        raise SmoothExperimentError(
            f"Verified Lite planning result is not ready: {variant.planning_run_id}"
        ) from exc
    contract = read_json(root / case21.CONTRACT_PATH)
    contract_version = contract.get("contract_version")
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != case21.AGENT_ID
        or summary.get("contract_version") != contract_version
        or summary.get("models") != [MODEL_ID]
        or summary.get("source_image_sha256") != SOURCE_SHA256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
    ):
        raise SmoothExperimentError(f"Lite provenance changed for {variant.planning_run_id}")
    expected_result = (
        case21.ARTIFACT_NAMESPACE / variant.planning_run_id / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result:
        raise SmoothExperimentError(f"Unexpected result path for {variant.planning_run_id}")
    result_path = root / expected_result
    result = read_json(result_path)
    result_sha256 = sha256_file(result_path)
    if result_sha256 != variant.result_sha256:
        raise SmoothExperimentError(
            f"Planning result digest changed for {variant.planning_run_id}"
        )
    producer = result.get("producer") if isinstance(result, dict) else None
    inputs = result.get("inputs") if isinstance(result, dict) else None
    source = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    models = result.get("models") if isinstance(result, dict) else None
    if (
        result.get("job_id") != variant.planning_run_id
        or not isinstance(producer, dict)
        or producer.get("agent_id") != case21.AGENT_ID
        or not isinstance(source, dict)
        or source.get("path") != case21.SOURCE_PATH.as_posix()
        or source.get("sha256") != SOURCE_SHA256
        or not isinstance(context, dict)
        or context.get("path") != case21.CONTEXT_PATH.as_posix()
        or context.get("sha256") != CONTEXT_SHA256
        or not isinstance(models, list)
        or len(models) != 1
        or not isinstance(models[0], dict)
        or models[0].get("model_id") != MODEL_ID
    ):
        raise SmoothExperimentError(f"Lite result binding changed for {variant.planning_run_id}")
    model = models[0]
    expected_runtime = contract["models"][MODEL_ID]["runtime"]
    positive = model.get("positive_prompt")
    negative = model.get("negative_prompt")
    if (
        model.get("runtime") != expected_runtime
        or expected_runtime.get("frame_inputs") != ["first_frame"]
        or not isinstance(positive, str)
        or not positive.strip()
        or len(positive) > 480
    ):
        raise SmoothExperimentError(f"Lite prompt/runtime changed for {variant.planning_run_id}")
    if variant.negative_policy == "must-be-null" and negative is not None:
        raise SmoothExperimentError(f"Unexpected negative prompt for {variant.variant_id}")
    if variant.negative_policy == "required-observed-repair" and (
        not isinstance(negative, str) or not negative.strip()
    ):
        raise SmoothExperimentError(f"Observed-failure repair is missing for {variant.variant_id}")
    if isinstance(negative, str) and len(negative) > 500:
        raise SmoothExperimentError(f"Negative prompt exceeds 500 characters: {variant.variant_id}")
    analysis = result.get("analysis") if isinstance(result, dict) else None
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(not isinstance(intent.get(key), str) or not intent[key].strip() for key in intent)
    ):
        raise SmoothExperimentError(f"Structured intent changed for {variant.planning_run_id}")
    current_source = root / case21.SOURCE_PATH
    if not current_source.is_file() or sha256_file(current_source) != SOURCE_SHA256:
        raise SmoothExperimentError("Current case-21 source image changed")
    return native.LiteJob(
        entry=entry,
        structured_intent={key: intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS},
        positive_prompt=positive.strip(),
        negative_prompt=negative.strip() if isinstance(negative, str) else None,
        result_path=expected_result,
        result_sha256=variant.result_sha256,
        provenance=summary,
        runtime=expected_runtime,
    )


def smooth_provider_prompt(job: native.LiteJob) -> dict[str, Any]:
    if job.entry.model_id != MODEL_ID:
        raise SmoothExperimentError("Smooth transport accepts only alibaba/wan-2.7")
    if job.runtime.get("frame_inputs") != ["first_frame"]:
        raise SmoothExperimentError("Smooth transport requires first_frame only")
    if job.runtime.get("prompt_expansion") != {
        "parameter": "prompt_extend",
        "value": True,
    }:
        raise SmoothExperimentError("Wan 2.7 prompt expansion changed")
    return {
        "sample_id": job.entry.sample.sample_id,
        "model_id": MODEL_ID,
        "target_duration_seconds": job.runtime["duration_seconds"],
        "positive_prompt": job.positive_prompt,
        "negative_prompt": job.negative_prompt,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
        "prompt_extend": True,
    }


def smooth_prompt_artifact(job: native.LiteJob) -> dict[str, Any]:
    artifact = _NATIVE_PROMPT_ARTIFACT(job)
    artifact["provider_transport_experiment"] = dict(TRANSPORT_PROFILE)
    return artifact


def smooth_initial_run(
    job: native.LiteJob,
    paths: dict[str, Path],
    root: Path = ROOT,
) -> dict[str, Any]:
    run = _NATIVE_INITIAL_RUN(job, paths, root)
    run["provider_transport_experiment"] = dict(TRANSPORT_PROFILE)
    return run


def assert_smooth_request(
    entry: native.Entry,
    request: dict[str, Any],
    job: native.LiteJob,
) -> None:
    _variant(entry)
    expected_parameters: dict[str, Any] = {"prompt_extend": True}
    if job.negative_prompt:
        expected_parameters["negative_prompt"] = job.negative_prompt
    expected_frames = [
        {
            "type": "image_url",
            "image_url": {"url": SOURCE_URL},
            "frame_type": "first_frame",
        }
    ]
    if (
        request.get("model") != MODEL_ID
        or request.get("prompt") != job.positive_prompt
        or request.get("duration") != 5
        or request.get("resolution") != "1080p"
        or request.get("aspect_ratio") != "1:1"
        or request.get("seed") != 9681
        or request.get("generate_audio") is not False
        or request.get("frame_images") != expected_frames
        or request.get("provider")
        != {"options": {"atlas-cloud": {"parameters": expected_parameters}}}
        or "loop" in request
        or any(
            frame.get("frame_type") == "last_frame"
            for frame in request.get("frame_images", [])
            if isinstance(frame, dict)
        )
    ):
        raise SmoothExperimentError(f"Non-exact smooth request: {entry.provider_run_id}")


@contextmanager
def configured_native(root: Path = ROOT) -> Iterator[None]:
    validate_route()
    names = (
        "BATCH_ID",
        "PLANNING_BATCH_ID",
        "MODEL_IDS",
        "PLANNING_MODEL_IDS",
        "TICKET",
        "MANIFEST_PATH",
        "CONTRACT_PATH",
        "PLANNING_WORKSPACE",
        "PLANNING_PROVENANCE_VERIFIER",
        "SAMPLES",
        "WAN_SUBMIT_MODE",
        "artifact_paths",
        "provider_sample",
        "provider_prompt",
        "prompt_artifact",
        "initial_run",
        "matrix",
        "load_lite_job",
    )
    saved = {name: getattr(native, name) for name in names}
    try:
        native.BATCH_ID = PROVIDER_BATCH_ID
        native.PLANNING_BATCH_ID = EXPERIMENT_ID
        native.MODEL_IDS = MODEL_IDS
        native.PLANNING_MODEL_IDS = MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = GENERATION_MANIFEST_PATH
        native.CONTRACT_PATH = root / case21.CONTRACT_PATH
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = None
        native.SAMPLES = SAMPLES
        native.WAN_SUBMIT_MODE = None
        native.artifact_paths = lambda entry, workspace=root: artifact_paths(entry, workspace)
        native.provider_sample = provider_sample
        native.provider_prompt = smooth_provider_prompt
        native.prompt_artifact = smooth_prompt_artifact
        native.initial_run = smooth_initial_run
        native.matrix = lambda: ENTRIES
        native.load_lite_job = lambda entry, workspace=root: load_experiment_job(entry, workspace)
        if len(native.matrix()) != INITIAL_ENTRY_COUNT or any(
            entry.provider_run_id != _provider_run_id(entry) for entry in native.matrix()
        ):
            raise SmoothExperimentError("Native smooth matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def _request_for_entry(
    entry: native.Entry,
    root: Path,
) -> tuple[native.LiteJob, dict[str, Any]]:
    job = load_experiment_job(entry, root)
    request = native.provider_request_preview(provider_sample(entry), smooth_provider_prompt(job))
    assert_smooth_request(entry, request, job)
    return job, request


def inventory_document(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    validate_route()
    source = case21.discover_case(root)
    case21.validate_public_orig_url(
        source.provider_source_url,
        source_image_id=source.image.get("source_image_id"),
        source_sha256=source.image.get("sha256"),
    )
    if source.provider_source_url != SOURCE_URL:
        raise SmoothExperimentError("Case-21 provider source URL changed")
    entries: list[dict[str, Any]] = []
    with configured_native(root):
        for entry in ENTRIES:
            variant = _variant(entry)
            job, request = _request_for_entry(entry, root)
            entries.append(
                {
                    "variant_id": variant.variant_id,
                    "planning_run_id": variant.planning_run_id,
                    "planning_result_sha256": job.result_sha256,
                    "provider_run_id": _provider_run_id(entry),
                    "sample_id": entry.sample.sample_id,
                    "model_id": MODEL_ID,
                    "positive_prompt_sha256": sha256_text(job.positive_prompt),
                    "negative_prompt_sha256": (
                        sha256_text(job.negative_prompt) if job.negative_prompt else None
                    ),
                    "reservation_usd": float(RESERVATION_PER_ENTRY_USD),
                    "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
                    "request_sha256": transport.request_fingerprint(
                        request, provider_sample(entry)
                    ),
                    "frame_inputs": ["first_frame"],
                    "source_url": SOURCE_URL,
                }
            )
    return {
        "schema_version": 1,
        "manifest_role": "case-21-wan27-smooth-inventory",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": case21.AGENT_ID,
        "source": {
            "path": case21.SOURCE_PATH.as_posix(),
            "sha256": SOURCE_SHA256,
            "provider_url": SOURCE_URL,
            "context_path": case21.CONTEXT_PATH.as_posix(),
            "context_sha256": CONTEXT_SHA256,
        },
        "controls": control_snapshots(root),
        "cost": cost_document(budget),
        "provider_transport_experiment": dict(TRANSPORT_PROFILE),
        "generation_policy": {
            "exact_model_id": MODEL_ID,
            "exact_route_only": True,
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "force_allowed": False,
            "automatic_paid_retries": False,
            "wan27_capacity": 3,
            "first_frame_only": True,
            "last_frame_allowed": False,
            "loop_allowed": False,
            "contingency_requires_new_explicit_provider_identity": True,
        },
        "expected_outputs": INITIAL_ENTRY_COUNT,
        "entries": entries,
    }


def write_inventory(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    document = inventory_document(budget, root)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise SmoothExperimentError(f"Immutable smooth inventory differs: {path}")
        return document
    if path.exists():
        raise SmoothExperimentError(f"Unsafe inventory target: {path}")
    transport.atomic_write_json(path, document)
    return document


def _validate_inventory(budget: str | Decimal, root: Path) -> dict[str, Any]:
    expected = inventory_document(budget, root)
    actual = read_json(root / INVENTORY_PATH)
    if actual != expected:
        raise SmoothExperimentError("Smooth inventory is missing, changed, or controls changed")
    return actual


def materialize(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    expected = inventory_document(budget, root)
    if not dry_run and read_json(root / INVENTORY_PATH) != expected:
        raise SmoothExperimentError("Smooth inventory is missing or differs")
    with configured_native(root):
        if dry_run:
            for entry in ENTRIES:
                job = native.load_lite_job(entry, root)
                request = native.provider_request_preview(
                    native.provider_sample(entry), native.provider_prompt(job)
                )
                assert_smooth_request(entry, request, job)
            print("PASS: four first-frame-only smooth requests validated; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != INITIAL_ENTRY_COUNT:
        raise SmoothExperimentError("Expected four materialized smooth entries")
    write_experiment_manifest(budget, root)
    print("PASS: materialized four immutable smooth entries")
    return 0


def run_generation(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    dry_run: bool = False,
    allow_external_processing: bool = False,
) -> int:
    _validate_inventory(budget, root)
    if not dry_run and not allow_external_processing:
        raise SmoothExperimentError(
            "Real smooth generation requires --allow-external-processing because "
            "the source image and prompts are sent to Atlas Cloud"
        )
    before = control_snapshots(root)
    argv = [
        "run",
        "--wan27-concurrency",
        "3",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
        "--dry-run" if dry_run else "--allow-external-processing",
    ]
    for entry in ENTRIES:
        argv.extend(("--run-id", _provider_run_id(entry)))

    def invoke() -> int:
        with configured_native(root):
            result = native.main(argv, root)
        if control_snapshots(root) != before:
            raise SmoothExperimentError("Existing case-21 controls changed during generation")
        write_experiment_manifest(budget, root)
        return result

    if dry_run:
        return invoke()
    with case21.batch_run_lock(root / INVENTORY_PATH):
        return invoke()


def _experiment_document(
    budget: str | Decimal,
    root: Path = ROOT,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    inventory = inventory_document(budget, root)
    generation_path = root / GENERATION_MANIFEST_PATH
    outputs: list[dict[str, Any]] = []
    if generation_path.is_file():
        generation = read_json(generation_path)
        raw_outputs = generation.get("outputs") if isinstance(generation, dict) else None
        if (
            generation.get("ticket") != TICKET
            or generation.get("batch_id") != PROVIDER_BATCH_ID
            or generation.get("agent_id") != case21.AGENT_ID
            or generation.get("expected_outputs") != INITIAL_ENTRY_COUNT
            or not isinstance(raw_outputs, list)
            or len(raw_outputs) != INITIAL_ENTRY_COUNT
        ):
            raise SmoothExperimentError("Smooth generation manifest identity changed")
        by_sample = {entry.sample.sample_id: entry for entry in ENTRIES}
        seen: set[str] = set()
        for output in raw_outputs:
            sample_id = output.get("sample_id") if isinstance(output, dict) else None
            entry = by_sample.get(str(sample_id))
            if (
                entry is None
                or str(sample_id) in seen
                or output.get("model_id") != MODEL_ID
                or output.get("lite_run_id") != entry.planning_run_id
                or output.get("provider_run_id") != _provider_run_id(entry)
            ):
                raise SmoothExperimentError("Smooth generation output identity changed")
            seen.add(str(sample_id))
            outputs.append(
                {
                    **output,
                    "variant_id": entry.sample.variant_id,
                    "provider_transport_experiment": dict(TRANSPORT_PROFILE),
                }
            )
        if seen != set(by_sample):
            raise SmoothExperimentError("Smooth generation output matrix changed")
    summary: dict[str, int] = {}
    for output in outputs:
        status = str(output.get("status"))
        summary[status] = summary.get(status, 0) + 1
    return {
        "schema_version": 1,
        "manifest_role": "case-21-wan27-smooth-experiment",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": case21.AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "source": inventory["source"],
        "controls": inventory["controls"],
        "cost": inventory["cost"],
        "provider_transport_experiment": dict(TRANSPORT_PROFILE),
        "generation_policy": inventory["generation_policy"],
        "expected_outputs": INITIAL_ENTRY_COUNT,
        "summary": summary,
        "planning_variants": [
            {
                "variant_id": variant.variant_id,
                "strategy": variant.strategy,
                "negative_policy": variant.negative_policy,
                "planning_run_id": variant.planning_run_id,
                "result_sha256": next(
                    row["planning_result_sha256"]
                    for row in inventory["entries"]
                    if row["variant_id"] == variant.variant_id
                ),
            }
            for variant in VARIANTS
        ],
        "inventory_path": INVENTORY_PATH.as_posix(),
        "generation_manifest_path": GENERATION_MANIFEST_PATH.as_posix(),
        "outputs": outputs,
    }


def write_experiment_manifest(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    path = root / EXPERIMENT_MANIFEST_PATH
    if path.is_file():
        current = read_json(path)
        updated_at = current.get("updated_at") if isinstance(current, dict) else None
        if isinstance(updated_at, str):
            unchanged = _experiment_document(budget, root, updated_at=updated_at)
            if current == unchanged:
                return unchanged
    document = _experiment_document(budget, root)
    transport.atomic_write_json(path, document)
    return document


def verify(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    allow_incomplete: bool = False,
    allow_contract_warnings: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        _validate_inventory(budget, root)
        with configured_native(root):
            passed, native_errors = native.verify(
                root,
                allow_incomplete=allow_incomplete,
                allow_contract_warnings=allow_contract_warnings,
            )
        if not passed:
            errors.extend(native_errors)
        for entry in ENTRIES:
            paths = artifact_paths(entry, root)
            if not paths["run"].is_file():
                continue
            run = read_json(paths["run"])
            if run.get("request") is not None:
                job, expected_request = _request_for_entry(entry, root)
                assert_smooth_request(entry, expected_request, job)
                if run.get("request") != expected_request:
                    errors.append(f"Smooth request mismatch: {entry.provider_run_id}")
                if run.get("request_fingerprint_version") != REQUEST_FINGERPRINT_VERSION:
                    errors.append(f"Fingerprint version mismatch: {entry.provider_run_id}")
    except Exception as exc:
        errors.append(transport.safe_error(exc))
        return False, errors
    manifest_path = root / EXPERIMENT_MANIFEST_PATH
    if manifest_path.is_file():
        try:
            actual = read_json(manifest_path)
            updated_at = actual.get("updated_at") if isinstance(actual, dict) else None
            rebuilt = _experiment_document(
                budget,
                root,
                updated_at=updated_at if isinstance(updated_at, str) else None,
            )
            if actual != rebuilt:
                errors.append("Smooth experiment manifest differs from current receipts")
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Smooth experiment manifest is missing")
    return not errors, errors


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least one")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be numeric") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _add_budget(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--budget-cap-usd",
        type=budget_arg,
        default=HARD_BUDGET_CAP_USD,
        metavar="USD",
        help="operator cap for this experiment (2.00 through 3.00; default: 3.00)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--dry-run", action="store_true")
    _add_budget(inventory)
    plan = commands.add_parser("plan")
    plan.add_argument("--dry-run", action="store_true")
    _add_budget(plan)
    generate = commands.add_parser("generate")
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--timeout", type=positive_int, default=1800)
    generate.add_argument("--poll-interval", type=positive_float, default=10.0)
    _add_budget(generate)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    verify_parser.add_argument("--allow-contract-warnings", action="store_true")
    _add_budget(verify_parser)
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        parse_budget(args.budget_cap_usd)
        if args.command == "inventory":
            document = inventory_document(args.budget_cap_usd, root)
            if not args.dry_run:
                write_inventory(args.budget_cap_usd, root)
            print(
                "PASS: reserved "
                f"${document['cost']['initial_reserved_usd']:.2f} for four entries; "
                "two contingency attempts remain explicit and unmaterialized"
            )
            return 0
        if args.command == "plan":
            if not args.dry_run:
                write_inventory(args.budget_cap_usd, root)
            return materialize(args.budget_cap_usd, root=root, dry_run=args.dry_run)
        if args.command == "generate":
            return run_generation(
                args.budget_cap_usd,
                root=root,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
            )
        if args.command == "verify":
            passed, errors = verify(
                args.budget_cap_usd,
                root=root,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: case-21 Wan 2.7 smooth experiment is valid")
            return 0
        raise SmoothExperimentError(f"Unknown command: {args.command}")
    except (
        SmoothExperimentError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
