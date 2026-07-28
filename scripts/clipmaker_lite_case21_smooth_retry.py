#!/usr/bin/env python3
"""Fail-closed explicit Wan 2.7 retry for case-21 staggered smooth motion.

This coordinator consumes exactly one of the two contingency reservations from
the immutable four-entry smooth experiment.  The retry has a new planning run,
provider batch, provider run ID and artifact namespace.  It never resubmits an
existing identity and keeps the aggregate reservation at $2.50 under the
operator's $3.00 cap.
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
from scripts import clipmaker_lite_case21_pipeline as case21  # noqa: E402
from scripts import clipmaker_lite_case21_smooth_experiment as smooth  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
RETRY_ID = (
    "promopages-9930-case21-wan27-smooth-staggered-ease-retry1-20260728-v1"
)
PROVIDER_BATCH_ID = (
    "promopages-9930-case21-wan27-smooth-staggered-ease-retry1-provider-20260728-v1"
)
PLANNING_RUN_ID = RETRY_ID
PLANNING_RESULT_SHA256 = (
    "a5c5da332d3bd46634928b517083fb0bf35fe8b4261ef388b5ca267d501a0ef6"
)
RETRY_OF_PROVIDER_RUN_ID = (
    "promopages-9930-case21-wan27-smooth-provider-20260728-v1-"
    "21-maier-04-smooth-staggered-ease-wan-2-7"
)
SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID = RETRY_OF_PROVIDER_RUN_ID

RETRY_ROOT = Path("clipmaker-lite-test/experiments") / RETRY_ID
INVENTORY_PATH = RETRY_ROOT / "inventory.json"
GENERATION_MANIFEST_PATH = RETRY_ROOT / "generation-manifest.json"
EXPERIMENT_MANIFEST_PATH = RETRY_ROOT / "experiment-manifest.json"

MODEL_ID = smooth.MODEL_ID
MODEL_IDS = (MODEL_ID,)
SOURCE_URL = smooth.SOURCE_URL
SOURCE_SHA256 = smooth.SOURCE_SHA256
CONTEXT_SHA256 = smooth.CONTEXT_SHA256
SOURCE_WIDTH = smooth.SOURCE_WIDTH
SOURCE_HEIGHT = smooth.SOURCE_HEIGHT
REQUEST_FINGERPRINT_VERSION = smooth.REQUEST_FINGERPRINT_VERSION

HARD_BUDGET_CAP_USD = Decimal("3.00")
BASE_RESERVED_USD = Decimal("2.00")
RETRY_RESERVED_USD = Decimal("0.50")
AGGREGATE_RESERVED_USD = Decimal("2.50")
REMAINING_CONTINGENCY_USD = Decimal("0.50")
REMAINING_CONTINGENCY_ATTEMPTS = 1

TRANSPORT_PROFILE = {
    **smooth.TRANSPORT_PROFILE,
    "profile": "non-loop-smooth-motion-explicit-retry",
    "explicit_retry": True,
    "retry_of": RETRY_OF_PROVIDER_RUN_ID,
    "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
}

# These are the exact aggregate and per-entry receipts of the original four
# paid jobs.  A retry cannot be planned or submitted if any one of them moves.
BASE_RECEIPT_SHA256 = {
    (
        smooth.EXPERIMENT_ROOT / "inventory.json"
    ).as_posix(): "bd44775f0ef841171f485b5624d3336f9df17de8230366115ec55f16ff951157",
    (
        smooth.EXPERIMENT_ROOT / "generation-manifest.json"
    ).as_posix(): "407c67ed2002afb5df5d2c066f578150a364163dd8e954213fb78c900d68a691",
    (
        smooth.EXPERIMENT_ROOT / "experiment-manifest.json"
    ).as_posix(): "a838c480da5792b072db3fc107ef991fc14fe6c9185d97d7f884a84a44e98dc6",
    (
        smooth.EXPERIMENT_ROOT / "videos/left-to-right-flow/wan-2.7/04.prompt.json"
    ).as_posix(): "ea00b2e89e097ddad11595fe0703746e3289c884e2ac03fd8de42cf30aa383b7",
    (
        smooth.EXPERIMENT_ROOT
        / "videos/low-amplitude-continuous/wan-2.7/04.prompt.json"
    ).as_posix(): "93c36050b93b93aee53d69530cc45105a74ef5e8e89545ef76c8d342fc3d0a9d",
    (
        smooth.EXPERIMENT_ROOT
        / "videos/preservation-smooth-repair/wan-2.7/04.prompt.json"
    ).as_posix(): "cba7705a1110f668843f12c864e7fb9a45681fa82f77a05db0972a809313e95b",
    (
        smooth.EXPERIMENT_ROOT / "videos/staggered-ease/wan-2.7/04.prompt.json"
    ).as_posix(): "2e19665863a0250acc1a7e9a3076fcae7896d7e65997a8485d720353b6ba4ef9",
    (
        smooth.EXPERIMENT_ROOT / "videos/left-to-right-flow/wan-2.7/04.run.json"
    ).as_posix(): "135b83e378c8ddeacbc52a360de8c44b20b9c65e4c5dac0c2a5760e1c85f36b2",
    (
        smooth.EXPERIMENT_ROOT / "videos/low-amplitude-continuous/wan-2.7/04.run.json"
    ).as_posix(): "497fa23afba68b96e879410ac66cfa34bcaa10c0b032742e69a6272898697ae0",
    (
        smooth.EXPERIMENT_ROOT
        / "videos/preservation-smooth-repair/wan-2.7/04.run.json"
    ).as_posix(): "4112ba65b5b0f19bc6b34732e8dd0e7eb57b34c39cf124dc869e28294f932bcf",
    (
        smooth.EXPERIMENT_ROOT / "videos/staggered-ease/wan-2.7/04.run.json"
    ).as_posix(): "e3e98183f6cb2b3deb52c83af02863a43f6311f0494263208f5c9b4108380c86",
    (
        smooth.EXPERIMENT_ROOT / "videos/left-to-right-flow/wan-2.7/04.mp4"
    ).as_posix(): "22fd794ce1bbdcf1b87ce7622f4a607b68203d0e7b09aee27fc0a266473c060a",
    (
        smooth.EXPERIMENT_ROOT / "videos/low-amplitude-continuous/wan-2.7/04.mp4"
    ).as_posix(): "416279e81eddc4c291c697487203bc61929ff6c1c983dfa071955d52ed7db774",
    (
        smooth.EXPERIMENT_ROOT
        / "videos/preservation-smooth-repair/wan-2.7/04.mp4"
    ).as_posix(): "16cca5d55e0f06e994feba5389791cc64cb0024d786c5b9c9c90fe0bc74e0fd3",
    (
        smooth.EXPERIMENT_ROOT / "videos/staggered-ease/wan-2.7/04.mp4"
    ).as_posix(): "cde9e047a24fc74bd50f12b76e8576cae4ddf45328d0b352a3789a4e4b8fdf71",
}


class SmoothRetryError(RuntimeError):
    """A fail-closed, user-actionable explicit retry failure."""


@dataclass(frozen=True)
class RetrySample(native.Sample):
    variant_id: str
    lite_run_id: str

    @property
    def planning_run_id(self) -> str:
        return self.lite_run_id


SAMPLE = RetrySample(
    sample_id="21-maier-04-smooth-staggered-ease-retry1",
    article_slug=case21.ARTICLE_SLUG,
    image_id=case21.IMAGE_ID,
    filename=case21.IMAGE_FILENAME,
    source_sha256=SOURCE_SHA256,
    width=SOURCE_WIDTH,
    height=SOURCE_HEIGHT,
    variant_id="staggered-ease-retry1",
    lite_run_id=PLANNING_RUN_ID,
)
ENTRY = native.Entry(SAMPLE, MODEL_ID)
ENTRIES = (ENTRY,)

_NATIVE_PROMPT_ARTIFACT = native.prompt_artifact
_NATIVE_INITIAL_RUN = native.initial_run


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SmoothRetryError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SmoothRetryError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    try:
        return smooth.sha256_file(path)
    except Exception as exc:
        raise SmoothRetryError(str(exc)) from exc


def sha256_text(value: str) -> str:
    return smooth.sha256_text(value)


def validate_route() -> dict[str, Any]:
    try:
        route = smooth.validate_route()
    except Exception as exc:
        raise SmoothRetryError(str(exc)) from exc
    if route.get("capacity") != 3 or route.get("provider_key") != "atlas-cloud":
        raise SmoothRetryError("Exact Wan 2.7 route changed")
    return route


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise SmoothRetryError(f"Invalid USD budget: {value!r}") from exc
    if budget < AGGREGATE_RESERVED_USD:
        raise SmoothRetryError(
            f"Budget ${budget:.2f} is below the ${AGGREGATE_RESERVED_USD:.2f} "
            "aggregate reservation"
        )
    if budget > HARD_BUDGET_CAP_USD:
        raise SmoothRetryError(
            f"Budget ${budget:.2f} exceeds the ${HARD_BUDGET_CAP_USD:.2f} hard cap"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except SmoothRetryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def cost_document(budget: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(budget)
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "base_initial_entry_count": smooth.INITIAL_ENTRY_COUNT,
        "base_reserved_usd": float(BASE_RESERVED_USD),
        "explicit_retry_entry_count": 1,
        "explicit_retry_reserved_usd": float(RETRY_RESERVED_USD),
        "aggregate_paid_entry_count": smooth.INITIAL_ENTRY_COUNT + 1,
        "aggregate_reserved_usd": float(AGGREGATE_RESERVED_USD),
        "remaining_contingency_attempt_count": REMAINING_CONTINGENCY_ATTEMPTS,
        "remaining_contingency_reserved_usd": float(REMAINING_CONTINGENCY_USD),
        "maximum_submissions_for_this_identity": 1,
        "automatic_paid_retries": False,
        "actual_billing_available": False,
        "note": (
            "The immutable four-entry series reserved $2.00. This new explicit "
            "identity reserves $0.50, bringing the aggregate to $2.50 under the "
            "$3.00 cap; one unmaterialized $0.50 contingency attempt remains."
        ),
    }


def validate_base_receipts(root: Path = ROOT) -> dict[str, str]:
    try:
        smooth._validate_inventory(HARD_BUDGET_CAP_USD, root)  # noqa: SLF001
        for entry in smooth.ENTRIES:
            smooth.load_experiment_job(entry, root)
    except Exception as exc:
        raise SmoothRetryError("Initial four-entry smooth receipts changed") from exc

    observed: dict[str, str] = {}
    for relative_path, expected_sha256 in BASE_RECEIPT_SHA256.items():
        path = root / relative_path
        if not path.is_file() or path.is_symlink():
            raise SmoothRetryError(f"Initial smooth receipt is missing: {relative_path}")
        observed_sha256 = sha256_file(path)
        if observed_sha256 != expected_sha256:
            raise SmoothRetryError(f"Initial smooth receipt changed: {relative_path}")
        observed[relative_path] = observed_sha256

    generation = read_json(root / smooth.GENERATION_MANIFEST_PATH)
    outputs = generation.get("outputs") if isinstance(generation, dict) else None
    if (
        generation.get("batch_id") != smooth.PROVIDER_BATCH_ID
        or generation.get("expected_outputs") != smooth.INITIAL_ENTRY_COUNT
        or not isinstance(outputs, list)
        or len(outputs) != smooth.INITIAL_ENTRY_COUNT
        or any(output.get("provider_may_be_active") is not False for output in outputs)
    ):
        raise SmoothRetryError("Initial smooth generation receipt changed")
    by_provider_id = {
        output.get("provider_run_id"): output
        for output in outputs
        if isinstance(output, dict)
    }
    replaced = by_provider_id.get(RETRY_OF_PROVIDER_RUN_ID)
    if (
        len(by_provider_id) != smooth.INITIAL_ENTRY_COUNT
        or not isinstance(replaced, dict)
        or replaced.get("status") not in {"succeeded", "verification-failed"}
        or replaced.get("video_path")
        != (
            smooth.EXPERIMENT_ROOT
            / "videos/staggered-ease/wan-2.7/04.mp4"
        ).as_posix()
    ):
        raise SmoothRetryError("Exact staggered-ease receipt to supersede changed")
    return observed


def _provider_run_id(entry: native.Entry = ENTRY) -> str:
    if entry != ENTRY:
        raise SmoothRetryError("Retry coordinator accepts exactly one entry")
    return f"{PROVIDER_BATCH_ID}-{SAMPLE.sample_id}-{native.MODEL_SUFFIXES[MODEL_ID]}"


def artifact_paths(entry: native.Entry = ENTRY, root: Path = ROOT) -> dict[str, Path]:
    if entry != ENTRY:
        raise SmoothRetryError("Retry coordinator accepts exactly one entry")
    base = RETRY_ROOT / "videos/staggered-ease-retry1" / native.MODEL_DIRECTORIES[MODEL_ID]
    return {
        "directory": root / base,
        "prompt": root / base / f"{case21.IMAGE_ID}.prompt.json",
        "run": root / base / f"{case21.IMAGE_ID}.run.json",
        "video": root / base / f"{case21.IMAGE_ID}.mp4",
    }


def provider_sample(entry: native.Entry = ENTRY) -> dict[str, Any]:
    if entry != ENTRY:
        raise SmoothRetryError("Retry coordinator accepts exactly one entry")
    return {
        "sample_id": SAMPLE.sample_id,
        "article_slug": case21.ARTICLE_SLUG,
        "image_id": case21.IMAGE_ID,
        "image_number": case21.IMAGE_ID,
        "source_path": case21.SOURCE_PATH.as_posix(),
        "source_url": SOURCE_URL,
        "sha256": SOURCE_SHA256,
        "width": SOURCE_WIDTH,
        "height": SOURCE_HEIGHT,
    }


def load_retry_job(entry: native.Entry = ENTRY, root: Path = ROOT) -> native.LiteJob:
    if entry != ENTRY:
        raise SmoothRetryError("Retry coordinator accepts exactly one entry")
    try:
        summary = runner.provenance_summary(root, PLANNING_RUN_ID)
    except Exception as exc:
        raise SmoothRetryError(
            f"Verified Lite planning result is not ready: {PLANNING_RUN_ID}"
        ) from exc
    contract = read_json(root / case21.CONTRACT_PATH)
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != case21.AGENT_ID
        or summary.get("contract_version") != contract.get("contract_version")
        or summary.get("models") != [MODEL_ID]
        or summary.get("source_image_sha256") != SOURCE_SHA256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
    ):
        raise SmoothRetryError("Retry Lite provenance changed")
    expected_result = (
        case21.ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result:
        raise SmoothRetryError("Unexpected retry planning result path")
    result_path = root / expected_result
    if sha256_file(result_path) != PLANNING_RESULT_SHA256:
        raise SmoothRetryError("Retry planning result digest changed")
    result = read_json(result_path)
    producer = result.get("producer") if isinstance(result, dict) else None
    inputs = result.get("inputs") if isinstance(result, dict) else None
    source = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    models = result.get("models") if isinstance(result, dict) else None
    if (
        result.get("job_id") != PLANNING_RUN_ID
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
        raise SmoothRetryError("Retry Lite result binding changed")
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
        or not isinstance(negative, str)
        or not negative.strip()
        or len(negative) > 500
    ):
        raise SmoothRetryError("Retry prompt/runtime changed")
    analysis = result.get("analysis") if isinstance(result, dict) else None
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(
            not isinstance(intent.get(key), str) or not intent[key].strip()
            for key in intent
        )
    ):
        raise SmoothRetryError("Retry structured intent changed")
    source_path = root / case21.SOURCE_PATH
    if not source_path.is_file() or sha256_file(source_path) != SOURCE_SHA256:
        raise SmoothRetryError("Current case-21 source image changed")
    return native.LiteJob(
        entry=entry,
        structured_intent={key: intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS},
        positive_prompt=positive.strip(),
        negative_prompt=negative.strip(),
        result_path=expected_result,
        result_sha256=PLANNING_RESULT_SHA256,
        provenance=summary,
        runtime=expected_runtime,
    )


def retry_provider_prompt(job: native.LiteJob) -> dict[str, Any]:
    if job.entry != ENTRY:
        raise SmoothRetryError("Retry prompt uses an unexpected entry")
    try:
        return smooth.smooth_provider_prompt(job)
    except Exception as exc:
        raise SmoothRetryError(str(exc)) from exc


def retry_prompt_artifact(job: native.LiteJob) -> dict[str, Any]:
    artifact = _NATIVE_PROMPT_ARTIFACT(job)
    artifact["provider_transport_experiment"] = dict(TRANSPORT_PROFILE)
    artifact["explicit_retry"] = {
        "retry_of": RETRY_OF_PROVIDER_RUN_ID,
        "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
    }
    return artifact


def retry_initial_run(
    job: native.LiteJob,
    paths: dict[str, Path],
    root: Path = ROOT,
) -> dict[str, Any]:
    run = _NATIVE_INITIAL_RUN(job, paths, root)
    run["provider_transport_experiment"] = dict(TRANSPORT_PROFILE)
    run["explicit_retry"] = {
        "retry_of": RETRY_OF_PROVIDER_RUN_ID,
        "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
    }
    return run


def assert_retry_request(
    entry: native.Entry,
    request: dict[str, Any],
    job: native.LiteJob,
) -> None:
    if entry != ENTRY:
        raise SmoothRetryError("Retry request uses an unexpected entry")
    expected_frames = [
        {
            "type": "image_url",
            "image_url": {"url": SOURCE_URL},
            "frame_type": "first_frame",
        }
    ]
    expected_parameters = {
        "prompt_extend": True,
        "negative_prompt": job.negative_prompt,
    }
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
        raise SmoothRetryError(f"Non-exact explicit retry request: {_provider_run_id(entry)}")


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
        native.PLANNING_BATCH_ID = RETRY_ID
        native.MODEL_IDS = MODEL_IDS
        native.PLANNING_MODEL_IDS = MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = GENERATION_MANIFEST_PATH
        native.CONTRACT_PATH = root / case21.CONTRACT_PATH
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = None
        native.SAMPLES = (SAMPLE,)
        native.WAN_SUBMIT_MODE = None
        native.artifact_paths = lambda entry, workspace=root: artifact_paths(entry, workspace)
        native.provider_sample = provider_sample
        native.provider_prompt = retry_provider_prompt
        native.prompt_artifact = retry_prompt_artifact
        native.initial_run = retry_initial_run
        native.matrix = lambda: ENTRIES
        native.load_lite_job = lambda entry, workspace=root: load_retry_job(entry, workspace)
        if native.matrix() != ENTRIES or ENTRY.provider_run_id != _provider_run_id():
            raise SmoothRetryError("Native retry matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def _request(root: Path = ROOT) -> tuple[native.LiteJob, dict[str, Any]]:
    job = load_retry_job(ENTRY, root)
    request = native.provider_request_preview(
        provider_sample(ENTRY), retry_provider_prompt(job)
    )
    assert_retry_request(ENTRY, request, job)
    return job, request


def inventory_document(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    route = validate_route()
    base_receipts = validate_base_receipts(root)
    job, request = _request(root)
    sample = provider_sample(ENTRY)
    return {
        "schema_version": 1,
        "manifest_role": "case-21-wan27-smooth-explicit-retry-inventory",
        "ticket": TICKET,
        "retry_id": RETRY_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": case21.AGENT_ID,
        "retry_of": RETRY_OF_PROVIDER_RUN_ID,
        "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
        "initial_four_receipts_immutable": True,
        "base_receipts_sha256": base_receipts,
        "source": {
            "path": case21.SOURCE_PATH.as_posix(),
            "sha256": SOURCE_SHA256,
            "provider_url": SOURCE_URL,
            "context_path": case21.CONTEXT_PATH.as_posix(),
            "context_sha256": CONTEXT_SHA256,
        },
        "cost": cost_document(budget),
        "provider_transport_experiment": dict(TRANSPORT_PROFILE),
        "generation_policy": {
            "exact_model_id": MODEL_ID,
            "exact_route_only": True,
            "route": route,
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "force_allowed": False,
            "automatic_paid_retries": False,
            "wan27_capacity": 3,
            "first_frame_only": True,
            "last_frame_allowed": False,
            "loop_allowed": False,
            "maximum_submissions_for_provider_identity": 1,
        },
        "expected_outputs": 1,
        "entries": [
            {
                "variant_id": SAMPLE.variant_id,
                "planning_run_id": PLANNING_RUN_ID,
                "planning_result_sha256": PLANNING_RESULT_SHA256,
                "provider_run_id": _provider_run_id(),
                "retry_of": RETRY_OF_PROVIDER_RUN_ID,
                "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
                "sample_id": SAMPLE.sample_id,
                "model_id": MODEL_ID,
                "positive_prompt_sha256": sha256_text(job.positive_prompt),
                "negative_prompt_sha256": sha256_text(job.negative_prompt),
                "reservation_usd": float(RETRY_RESERVED_USD),
                "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
                "request_sha256": transport.request_fingerprint(request, sample),
                "frame_inputs": ["first_frame"],
                "source_url": SOURCE_URL,
            }
        ],
    }


def write_inventory(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    document = inventory_document(budget, root)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise SmoothRetryError(f"Immutable explicit retry inventory differs: {path}")
        return document
    if path.exists():
        raise SmoothRetryError(f"Unsafe retry inventory target: {path}")
    transport.atomic_write_json(path, document)
    return document


def _validate_inventory(budget: str | Decimal, root: Path) -> dict[str, Any]:
    expected = inventory_document(budget, root)
    actual = read_json(root / INVENTORY_PATH)
    if actual != expected:
        raise SmoothRetryError("Explicit retry inventory or base receipts changed")
    return actual


def materialize(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    expected = inventory_document(budget, root)
    if not dry_run and read_json(root / INVENTORY_PATH) != expected:
        raise SmoothRetryError("Explicit retry inventory is missing or differs")
    with configured_native(root):
        if dry_run:
            job, request = _request(root)
            assert_retry_request(ENTRY, request, job)
            print("PASS: one explicit first-frame-only retry request validated; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != 1:
        raise SmoothRetryError("Expected one materialized explicit retry entry")
    write_experiment_manifest(budget, root)
    print("PASS: materialized one immutable explicit retry entry")
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
        raise SmoothRetryError(
            "Real explicit retry generation requires --allow-external-processing"
        )
    before = validate_base_receipts(root)
    argv = [
        "run",
        "--wan27-concurrency",
        "3",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
        "--run-id",
        _provider_run_id(),
        "--dry-run" if dry_run else "--allow-external-processing",
    ]
    def invoke() -> int:
        with configured_native(root):
            return native.main(argv, root)

    if dry_run:
        result = invoke()
    else:
        with case21.batch_run_lock(root / INVENTORY_PATH):
            result = invoke()
    if validate_base_receipts(root) != before:
        raise SmoothRetryError("Initial four receipts changed during explicit retry")
    write_experiment_manifest(budget, root)
    return result


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
            or generation.get("expected_outputs") != 1
            or not isinstance(raw_outputs, list)
            or len(raw_outputs) != 1
            or raw_outputs[0].get("provider_run_id") != _provider_run_id()
            or raw_outputs[0].get("lite_run_id") != PLANNING_RUN_ID
            or raw_outputs[0].get("model_id") != MODEL_ID
        ):
            raise SmoothRetryError("Explicit retry generation manifest identity changed")
        outputs = [
            {
                **raw_outputs[0],
                "variant_id": SAMPLE.variant_id,
                "retry_of": RETRY_OF_PROVIDER_RUN_ID,
                "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
                "provider_transport_experiment": dict(TRANSPORT_PROFILE),
            }
        ]
    summary: dict[str, int] = {}
    for output in outputs:
        status = str(output.get("status"))
        summary[status] = summary.get(status, 0) + 1
    return {
        "schema_version": 1,
        "manifest_role": "case-21-wan27-smooth-explicit-retry",
        "ticket": TICKET,
        "retry_id": RETRY_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": case21.AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "retry_of": RETRY_OF_PROVIDER_RUN_ID,
        "supersedes_for_demo": SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
        "initial_four_receipts_immutable": True,
        "base_receipts_sha256": inventory["base_receipts_sha256"],
        "source": inventory["source"],
        "cost": inventory["cost"],
        "provider_transport_experiment": dict(TRANSPORT_PROFILE),
        "generation_policy": inventory["generation_policy"],
        "expected_outputs": 1,
        "summary": summary,
        "planning": {
            "planning_run_id": PLANNING_RUN_ID,
            "result_sha256": PLANNING_RESULT_SHA256,
        },
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
        help="aggregate smooth cap (2.50 through 3.00; default: 3.00)",
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
                "PASS: aggregate reservation "
                f"${document['cost']['aggregate_reserved_usd']:.2f}; "
                "one explicit retry entry"
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
        raise SmoothRetryError(f"Unknown command: {args.command}")
    except (
        SmoothRetryError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
