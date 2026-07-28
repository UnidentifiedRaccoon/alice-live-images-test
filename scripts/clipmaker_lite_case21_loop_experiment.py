#!/usr/bin/env python3
"""Fail-closed Wan 2.7 loop-closure experiment for case 21 / image 04.

Eight independently attested Clipmaker Lite plans are mapped to eight immutable
provider entries.  Planning remains canonical Lite v1; provider transport is
explicitly non-canonical because it repeats the exact source image as both the
first and last frame.  Paid generation is staged: three canaries must produce
terminal MP4s before a separate command may submit the remaining five entries.
"""

from __future__ import annotations

import argparse
import hashlib
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
from scripts import clipmaker_lite_case21_pipeline as case21  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
EXPERIMENT_ID = "promopages-9930-case21-wan27-loop-20260728-v1"
PROVIDER_BATCH_ID = "promopages-9930-case21-wan27-loop-provider-20260728-v1"
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

HARD_BUDGET_CAP_USD = Decimal("5.00")
RESERVATION_PER_ENTRY_USD = Decimal("0.50")
INITIAL_ENTRY_COUNT = 8
INITIAL_RESERVED_USD = Decimal("4.00")
CONTINGENCY_SLOT_COUNT = 2
MAXIMUM_PROVIDER_ENTRIES = 10
REQUEST_FINGERPRINT_VERSION = 2

CANARY_VARIANT_IDS = ("sync-cycle", "local-icons", "endpoint-first")
MAIN_VARIANT_IDS = (
    "mirror-midpoint",
    "kinetic-compact",
    "staggered-wave",
    "simultaneous-microloops",
    "preservation-repair",
)
STAGE_VARIANTS = {
    "canary": CANARY_VARIANT_IDS,
    "main": MAIN_VARIANT_IDS,
}

CONTROL_PATHS = {
    "primary": case21.BATCH_ROOT,
    "retry": case21.RETRY_BATCH_ROOT,
    "prompt_research": (
        Path("clipmaker-lite-test/experiments")
        / "promopages-9930-case21-prompt-research-20260727-v1"
    ),
    "opacity_stage2": (
        Path("clipmaker-lite-test/experiments")
        / "promopages-9930-case21-opacity-only-stage2-20260727-v1"
    ),
}

TRANSPORT_EXPERIMENT = {
    "profile": "non-canonical-loop-closure",
    "canonical_lite_planning": True,
    "canonical_lite_provider_runtime": False,
    "reason": (
        "The locked Lite v1 runtime contains only first_frame; this research "
        "transport repeats the exact source URL as last_frame to test loop closure."
    ),
    "last_frame_is_source": True,
    "first_and_last_frame_urls_must_match": True,
}


class LoopExperimentError(RuntimeError):
    """A fail-closed, user-actionable loop experiment failure."""


@dataclass(frozen=True)
class Variant:
    variant_id: str
    planning_run_id: str
    strategy: str
    negative_policy: str
    result_sha256: str


VARIANTS = (
    Variant(
        "sync-cycle",
        "promopages-9930-case21-wan27-loop-sync-cycle-20260728-v1",
        "synchronized full infographic cycle",
        "required-observed-repair",
        "0e46fd047b53ff0d94d128f8ea4a504a625fef2cdae768ee3c7027763e7337e9",
    ),
    Variant(
        "mirror-midpoint",
        "promopages-9930-case21-wan27-loop-mirror-midpoint-20260728-v1",
        "time-symmetric motion around the midpoint",
        "must-be-null",
        "e7aa41fb1fad600f82814cb38f445fd683055c33edab5aacf6cfc027b3d50100",
    ),
    Variant(
        "local-icons",
        "promopages-9930-case21-wan27-loop-local-icons-20260728-v1",
        "strict local icon masks and fixed layout",
        "must-be-null",
        "daee71fa697df600352442b8a681ea0a6aa26647ebcc54496853b6b82e72b881",
    ),
    Variant(
        "kinetic-compact",
        "promopages-9930-case21-wan27-loop-kinetic-compact-20260728-v1",
        "compact kinetic choreography",
        "required-observed-repair",
        "ee4eac56d7d675cee8ea6d11a7f8c0b176e56e8b3cd976f22b3b5bb41b8ea3f2",
    ),
    Variant(
        "staggered-wave",
        "promopages-9930-case21-wan27-loop-staggered-wave-20260728-v1",
        "staggered wave across existing elements",
        "must-be-null",
        "f6b53836018916e65219da47f4e5abb641ed934c2ae340a30d42e4d14450b462",
    ),
    Variant(
        "simultaneous-microloops",
        "promopages-9930-case21-wan27-loop-simultaneous-microloops-20260728-v1",
        "simultaneous local microloops",
        "must-be-null",
        "54e3e0c60ce5a3b3cf2c043b185b7c55e514170d4004f1ae87c3a4e956f28596",
    ),
    Variant(
        "endpoint-first",
        "promopages-9930-case21-wan27-loop-endpoint-first-20260728-v1",
        "explicit source-matching endpoint",
        "required-observed-repair",
        "f4e4081fc3b1a6878cacced576c170e9e01c15c8b2f8b869db3c8984732d60ae",
    ),
    Variant(
        "preservation-repair",
        "promopages-9930-case21-wan27-loop-preservation-repair-20260728-v1",
        "observed-fidelity preservation repair",
        "required-observed-repair",
        "3c5f975909f00b1332ecd7c8de5b7d2efe8912baa30f44d6c67a4fb9770b0398",
    ),
)
VARIANT_BY_ID = {variant.variant_id: variant for variant in VARIANTS}


@dataclass(frozen=True)
class LoopSample(native.Sample):
    variant_id: str
    lite_run_id: str

    @property
    def planning_run_id(self) -> str:
        return self.lite_run_id


def _sample(variant: Variant) -> LoopSample:
    return LoopSample(
        sample_id=f"21-maier-04-loop-{variant.variant_id}",
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
SAMPLE_BY_VARIANT = {sample.variant_id: sample for sample in SAMPLES}
ENTRIES = tuple(native.Entry(sample, MODEL_ID) for sample in SAMPLES)
ENTRY_BY_VARIANT = {entry.sample.variant_id: entry for entry in ENTRIES}


_NATIVE_PROVIDER_PROMPT = native.provider_prompt
_NATIVE_PROMPT_ARTIFACT = native.prompt_artifact
_NATIVE_INITIAL_RUN = native.initial_run


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise LoopExperimentError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LoopExperimentError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LoopExperimentError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def content_tree_digest(relative: Path, root: Path = ROOT) -> str:
    """Hash path names and bytes so an inventory can freeze existing controls."""

    root = root.resolve()
    base = root / relative
    if not base.exists() or base.is_symlink():
        raise LoopExperimentError(f"Control path is missing or unsafe: {base}")
    files = [base] if base.is_file() else sorted(item for item in base.rglob("*") if item.is_file())
    lines: list[str] = []
    for item in files:
        if item.is_symlink():
            raise LoopExperimentError(f"Control path contains a symlink: {item}")
        try:
            label = item.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise LoopExperimentError(f"Control path escapes workspace: {item}") from exc
        lines.append(f"{sha256_file(item)}  {label}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def control_snapshots(root: Path = ROOT) -> dict[str, dict[str, str]]:
    return {
        name: {"path": path.as_posix(), "sha256": content_tree_digest(path, root)}
        for name, path in CONTROL_PATHS.items()
    }


def validate_route() -> dict[str, Any]:
    policy = transport.GENERATION_ROUTE_DOCUMENT.get("policy")
    if policy != {
        "resolution": "exact-model-id",
        "automatic_fallback": False,
        "normal_run_discovery": False,
        "forbidden_discovery_paths": ["/videos/models", "/gradio_api/info", "/config"],
    }:
        raise LoopExperimentError("Generation route policy changed")
    route = transport.route_for_model(MODEL_ID)
    expected = {
        "adapter": "eliza-openrouter",
        "transport": "eliza-video-jobs",
        "default_base_url": "https://api.eliza.yandex.net/openrouter/v1",
        "capacity": 3,
        "provider_key": "atlas-cloud",
        "paths": {
            "submit": "/videos",
            "status_template": "/videos/{job_id}",
            "content_template": "/videos/{job_id}/content?index=0",
        },
    }
    if route != expected:
        raise LoopExperimentError(f"Exact Wan 2.7 route changed: {route!r}")
    if transport.REQUEST_FINGERPRINT_VERSION != REQUEST_FINGERPRINT_VERSION:
        raise LoopExperimentError("Request fingerprint version changed")
    return route


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise LoopExperimentError(f"Invalid USD budget: {value!r}") from exc
    if budget < INITIAL_RESERVED_USD:
        raise LoopExperimentError(
            f"Budget ${budget:.2f} is below the ${INITIAL_RESERVED_USD:.2f} initial reservation"
        )
    if budget > HARD_BUDGET_CAP_USD:
        raise LoopExperimentError(
            f"Budget ${budget:.2f} exceeds the ${HARD_BUDGET_CAP_USD:.2f} hard cap"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except LoopExperimentError as exc:
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
        "contingency_slot_count": CONTINGENCY_SLOT_COUNT,
        "contingency_reserved_usd": float(
            CONTINGENCY_SLOT_COUNT * RESERVATION_PER_ENTRY_USD
        ),
        "maximum_provider_entries": MAXIMUM_PROVIDER_ENTRIES,
        "admitted_provider_entries": INITIAL_ENTRY_COUNT,
        "contingency_entries_materialized": 0,
        "maximum_submissions_per_entry": 1,
        "automatic_paid_retries": False,
        "provider_unit_costs_asserted": False,
        "actual_billing_available": False,
        "note": (
            "Eight immutable entries reserve $4.00. Two $0.50 contingency slots "
            "remain unmaterialized and require a new explicit namespace."
        ),
    }


def _variant(entry: native.Entry) -> Variant:
    sample = entry.sample
    if not isinstance(sample, LoopSample):
        raise LoopExperimentError("Loop entry uses an unexpected sample type")
    variant = VARIANT_BY_ID.get(sample.variant_id)
    if variant is None or entry.model_id != MODEL_ID:
        raise LoopExperimentError("Loop entry is outside the exact eight-entry Wan 2.7 matrix")
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
    summary = runner.provenance_summary(root, variant.planning_run_id)
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != case21.AGENT_ID
        or summary.get("contract_version") != "2.0.2"
        or summary.get("models") != [MODEL_ID]
        or summary.get("source_image_sha256") != SOURCE_SHA256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
    ):
        raise LoopExperimentError(f"Lite provenance changed for {variant.planning_run_id}")
    expected_result = (
        case21.ARTIFACT_NAMESPACE / variant.planning_run_id / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result:
        raise LoopExperimentError(f"Unexpected result path for {variant.planning_run_id}")
    result_path = root / expected_result
    if sha256_file(result_path) != variant.result_sha256:
        raise LoopExperimentError(f"Lite result changed for {variant.planning_run_id}")
    result = read_json(result_path)
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
        raise LoopExperimentError(f"Lite result binding changed for {variant.planning_run_id}")
    model = models[0]
    expected_runtime = read_json(root / case21.CONTRACT_PATH)["models"][MODEL_ID]["runtime"]
    positive = model.get("positive_prompt")
    negative = model.get("negative_prompt")
    if model.get("runtime") != expected_runtime or not isinstance(positive, str) or not positive.strip():
        raise LoopExperimentError(f"Lite prompt/runtime changed for {variant.planning_run_id}")
    if variant.negative_policy == "must-be-null" and negative is not None:
        raise LoopExperimentError(f"Unexpected negative prompt for {variant.variant_id}")
    if variant.negative_policy == "required-observed-repair" and (
        not isinstance(negative, str) or not negative.strip()
    ):
        raise LoopExperimentError(f"Observed-failure repair is missing for {variant.variant_id}")
    if isinstance(negative, str) and len(negative) > 500:
        raise LoopExperimentError(f"Negative prompt exceeds 500 characters: {variant.variant_id}")
    analysis = result.get("analysis") if isinstance(result, dict) else None
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(not isinstance(intent.get(key), str) or not intent[key].strip() for key in intent)
    ):
        raise LoopExperimentError(f"Structured intent changed for {variant.planning_run_id}")
    source_path = root / case21.SOURCE_PATH
    if not source_path.is_file() or sha256_file(source_path) != SOURCE_SHA256:
        raise LoopExperimentError("Current case-21 source image changed")
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


def loop_provider_prompt(job: native.LiteJob) -> dict[str, Any]:
    if job.entry.model_id != MODEL_ID:
        raise LoopExperimentError("Loop transport accepts only alibaba/wan-2.7")
    expansion = job.runtime.get("prompt_expansion")
    if expansion != {"parameter": "prompt_extend", "value": True}:
        raise LoopExperimentError("Wan 2.7 prompt expansion changed")
    return {
        "sample_id": job.entry.sample.sample_id,
        "model_id": MODEL_ID,
        "target_duration_seconds": job.runtime["duration_seconds"],
        "positive_prompt": job.positive_prompt,
        "negative_prompt": job.negative_prompt,
        "embed_negative_in_positive": False,
        "last_frame_is_source": True,
        "prompt_extend": True,
    }


def loop_prompt_artifact(job: native.LiteJob) -> dict[str, Any]:
    artifact = _NATIVE_PROMPT_ARTIFACT(job)
    artifact["provider_transport_experiment"] = dict(TRANSPORT_EXPERIMENT)
    return artifact


def loop_initial_run(job: native.LiteJob, paths: dict[str, Path], root: Path = ROOT) -> dict[str, Any]:
    run = _NATIVE_INITIAL_RUN(job, paths, root)
    run["provider_transport_experiment"] = dict(TRANSPORT_EXPERIMENT)
    return run


def assert_loop_request(
    entry: native.Entry,
    request: dict[str, Any],
    job: native.LiteJob,
) -> None:
    _variant(entry)
    frames = request.get("frame_images")
    expected_frame = {
        "type": "image_url",
        "image_url": {"url": SOURCE_URL},
        "frame_type": "first_frame",
    }
    expected_last = {**expected_frame, "frame_type": "last_frame"}
    expected_parameters: dict[str, Any] = {"prompt_extend": True}
    if job.negative_prompt:
        expected_parameters["negative_prompt"] = job.negative_prompt
    if (
        request.get("model") != MODEL_ID
        or request.get("prompt") != job.positive_prompt
        or request.get("duration") != 5
        or request.get("resolution") != "1080p"
        or request.get("aspect_ratio") != "1:1"
        or request.get("seed") != 9681
        or request.get("generate_audio") is not False
        or frames != [expected_frame, expected_last]
        or request.get("provider")
        != {"options": {"atlas-cloud": {"parameters": expected_parameters}}}
        or "loop" in request
    ):
        raise LoopExperimentError(f"Non-exact loop request: {entry.provider_run_id}")


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
        native.provider_prompt = loop_provider_prompt
        native.prompt_artifact = loop_prompt_artifact
        native.initial_run = loop_initial_run
        native.matrix = lambda: ENTRIES
        native.load_lite_job = lambda entry, workspace=root: load_experiment_job(entry, workspace)
        if len(native.matrix()) != INITIAL_ENTRY_COUNT or any(
            entry.provider_run_id != _provider_run_id(entry) for entry in native.matrix()
        ):
            raise LoopExperimentError("Native loop matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def _request_for_entry(entry: native.Entry, root: Path) -> tuple[native.LiteJob, dict[str, Any]]:
    job = load_experiment_job(entry, root)
    request = native.provider_request_preview(provider_sample(entry), loop_provider_prompt(job))
    assert_loop_request(entry, request, job)
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
        raise LoopExperimentError("Case-21 provider source URL changed")
    entries: list[dict[str, Any]] = []
    with configured_native(root):
        for entry in ENTRIES:
            variant = _variant(entry)
            job, request = _request_for_entry(entry, root)
            entries.append(
                {
                    "variant_id": variant.variant_id,
                    "stage": "canary" if variant.variant_id in CANARY_VARIANT_IDS else "main",
                    "planning_run_id": variant.planning_run_id,
                    "planning_result_sha256": variant.result_sha256,
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
                    "first_frame_url": SOURCE_URL,
                    "last_frame_url": SOURCE_URL,
                }
            )
    return {
        "schema_version": 1,
        "manifest_role": "case-21-wan27-loop-inventory",
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
        "provider_transport_experiment": dict(TRANSPORT_EXPERIMENT),
        "generation_policy": {
            "exact_model_id": MODEL_ID,
            "exact_route_only": True,
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "force_allowed": False,
            "automatic_paid_retries": False,
            "wan27_capacity": 3,
            "staged_paid_generation": True,
            "canary_variant_ids": list(CANARY_VARIANT_IDS),
            "main_variant_ids": list(MAIN_VARIANT_IDS),
            "main_requires_three_terminal_canary_mp4s": True,
        },
        "expected_outputs": INITIAL_ENTRY_COUNT,
        "entries": entries,
    }


def write_inventory(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    document = inventory_document(budget, root)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise LoopExperimentError(f"Immutable loop inventory differs: {path}")
        return document
    if path.exists():
        raise LoopExperimentError(f"Unsafe inventory target: {path}")
    transport.atomic_write_json(path, document)
    return document


def _validate_inventory(budget: str | Decimal, root: Path) -> dict[str, Any]:
    expected = inventory_document(budget, root)
    actual = read_json(root / INVENTORY_PATH)
    if actual != expected:
        raise LoopExperimentError("Loop inventory is missing, changed, or controls were modified")
    return actual


def materialize(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    expected = inventory_document(budget, root)
    if not dry_run and read_json(root / INVENTORY_PATH) != expected:
        raise LoopExperimentError("Loop inventory is missing or differs")
    with configured_native(root):
        if dry_run:
            for entry in ENTRIES:
                job = native.load_lite_job(entry, root)
                request = native.provider_request_preview(
                    native.provider_sample(entry), native.provider_prompt(job)
                )
                assert_loop_request(entry, request, job)
            print("PASS: eight loop requests validated; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != INITIAL_ENTRY_COUNT:
        raise LoopExperimentError("Expected eight materialized loop entries")
    write_experiment_manifest(budget, root)
    print("PASS: materialized eight immutable non-canonical loop entries")
    return 0


def _canary_gate(root: Path) -> None:
    errors: list[str] = []
    completed_mp4s = 0
    terminal_statuses = {"succeeded", "verification-failed", "provider-failed"}
    request_rejection_markers = (
        "last_frame",
        "last frame",
        "frame_images",
        "invalid_request",
        "invalid request",
        "schema",
        "unsupported",
        "validation",
    )
    with configured_native(root):
        for variant_id in CANARY_VARIANT_IDS:
            entry = ENTRY_BY_VARIANT[variant_id]
            paths = artifact_paths(entry, root)
            if not paths["run"].is_file():
                errors.append(f"{variant_id}: run receipt missing")
                continue
            run = read_json(paths["run"])
            status = run.get("status")
            error = str(run.get("error") or "").lower()
            download_only_failure = (
                status == "submitted"
                and bool(run.get("provider_job_id"))
                and (
                    "download failed" in error
                    or "download interrupted" in error
                    or "content download" in error
                )
            )
            if status not in terminal_statuses and not download_only_failure:
                errors.append(f"{variant_id}: non-terminal status {status!r}")
                continue
            job = load_experiment_job(entry, root)
            expected_request = native.provider_request_preview(
                provider_sample(entry), loop_provider_prompt(job)
            )
            assert_loop_request(entry, expected_request, job)
            expected_fingerprint = transport.request_fingerprint(
                expected_request, provider_sample(entry)
            )
            if (
                run.get("request") != expected_request
                or run.get("request_sha256") != expected_fingerprint
                or run.get("request_fingerprint_version") != REQUEST_FINGERPRINT_VERSION
            ):
                errors.append(f"{variant_id}: exact loop request receipt mismatch")
            if status in {"succeeded", "verification-failed"}:
                if paths["video"].is_file():
                    completed_mp4s += 1
                else:
                    errors.append(f"{variant_id}: completed run has no MP4")
            elif status == "provider-failed":
                if any(marker in error for marker in request_rejection_markers):
                    errors.append(
                        f"{variant_id}: provider rejected the loop request schema: {error[:240]}"
                    )
    if completed_mp4s < 1:
        errors.append("canary wave produced no MP4 proving same-source last_frame acceptance")
    if errors:
        raise LoopExperimentError(
            "Main wave is blocked until all three canaries are terminal, at least one "
            "MP4 exists, and no last-frame request rejection is recorded: "
            + "; ".join(errors)
        )


def run_generation(
    stage: str,
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    dry_run: bool = False,
    allow_external_processing: bool = False,
) -> int:
    if stage not in STAGE_VARIANTS:
        raise LoopExperimentError(f"Unknown paid stage: {stage}")
    _validate_inventory(budget, root)
    if not dry_run and not allow_external_processing:
        raise LoopExperimentError(
            "Real loop generation requires --allow-external-processing because the "
            "source image and prompts are sent to Atlas Cloud"
        )
    if stage == "main":
        _canary_gate(root)
    before = control_snapshots(root)
    run_ids = [_provider_run_id(ENTRY_BY_VARIANT[item]) for item in STAGE_VARIANTS[stage]]
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
    for run_id in run_ids:
        argv.extend(("--run-id", run_id))

    def invoke() -> int:
        with configured_native(root):
            result = native.main(argv, root)
        after = control_snapshots(root)
        if after != before:
            raise LoopExperimentError("Existing case-21 control trees changed during generation")
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
    path = root / GENERATION_MANIFEST_PATH
    outputs: list[dict[str, Any]] = []
    if path.is_file():
        generation = read_json(path)
        raw_outputs = generation.get("outputs") if isinstance(generation, dict) else None
        if (
            generation.get("ticket") != TICKET
            or generation.get("batch_id") != PROVIDER_BATCH_ID
            or generation.get("agent_id") != case21.AGENT_ID
            or generation.get("expected_outputs") != INITIAL_ENTRY_COUNT
            or not isinstance(raw_outputs, list)
            or len(raw_outputs) != INITIAL_ENTRY_COUNT
        ):
            raise LoopExperimentError("Loop generation manifest identity changed")
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
                raise LoopExperimentError("Loop generation output identity changed")
            seen.add(str(sample_id))
            variant_id = entry.sample.variant_id
            outputs.append(
                {
                    **output,
                    "variant_id": variant_id,
                    "stage": "canary" if variant_id in CANARY_VARIANT_IDS else "main",
                    "provider_transport_experiment": dict(TRANSPORT_EXPERIMENT),
                }
            )
        if seen != set(by_sample):
            raise LoopExperimentError("Loop generation output matrix changed")
    summary: dict[str, int] = {}
    for output in outputs:
        status = str(output.get("status"))
        summary[status] = summary.get(status, 0) + 1
    return {
        "schema_version": 1,
        "manifest_role": "case-21-wan27-loop-experiment",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": case21.AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "source": inventory["source"],
        "controls": inventory["controls"],
        "cost": inventory["cost"],
        "provider_transport_experiment": dict(TRANSPORT_EXPERIMENT),
        "generation_policy": inventory["generation_policy"],
        "expected_outputs": INITIAL_ENTRY_COUNT,
        "summary": summary,
        "planning_variants": [
            {
                "variant_id": variant.variant_id,
                "stage": "canary" if variant.variant_id in CANARY_VARIANT_IDS else "main",
                "strategy": variant.strategy,
                "negative_policy": variant.negative_policy,
                "planning_run_id": variant.planning_run_id,
                "result_sha256": variant.result_sha256,
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
        candidate = current.get("updated_at") if isinstance(current, dict) else None
        if isinstance(candidate, str):
            unchanged = _experiment_document(budget, root, updated_at=candidate)
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
                assert_loop_request(entry, expected_request, job)
                if run.get("request") != expected_request:
                    errors.append(f"Loop request mismatch: {entry.provider_run_id}")
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
                errors.append("Loop experiment manifest differs from current receipts")
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Loop experiment manifest is missing")
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
        help="operator cap for this experiment (4.00 through 5.00; default: 5.00)",
    )


def _add_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-external-processing", action="store_true")
    parser.add_argument("--timeout", type=positive_int, default=1800)
    parser.add_argument("--poll-interval", type=positive_float, default=10.0)
    _add_budget(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--dry-run", action="store_true")
    _add_budget(inventory)
    plan = commands.add_parser("plan")
    plan.add_argument("--dry-run", action="store_true")
    _add_budget(plan)
    _add_generation_options(commands.add_parser("generate-canary"))
    _add_generation_options(commands.add_parser("generate-main"))
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
                f"${document['cost']['initial_reserved_usd']:.2f} for eight entries; "
                "two contingency slots remain unmaterialized"
            )
            return 0
        if args.command == "plan":
            if not args.dry_run:
                write_inventory(args.budget_cap_usd, root)
            return materialize(args.budget_cap_usd, root=root, dry_run=args.dry_run)
        if args.command in {"generate-canary", "generate-main"}:
            stage = "canary" if args.command == "generate-canary" else "main"
            return run_generation(
                stage,
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
            print("PASS: case-21 Wan 2.7 loop experiment is valid")
            return 0
        raise LoopExperimentError(f"Unknown command: {args.command}")
    except (
        LoopExperimentError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
