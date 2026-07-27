#!/usr/bin/env python3
"""Run the fail-closed Clipmaker Lite case-21 prompt-repair experiment.

The experiment keeps the original and first retry batches read-only, binds five
new provider entries to three independently attested Lite planning runs, and
reserves a conservative operator budget before any provider submit.  It never
discovers routes, falls back, forces, or automatically retries an entry.
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
EXPERIMENT_ID = "promopages-9930-case21-prompt-research-20260727-v1"
PROVIDER_BATCH_ID = "promopages-9930-case21-prompt-research-stage1-20260727-v1"
EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / EXPERIMENT_ID
INVENTORY_PATH = EXPERIMENT_ROOT / "inventory.json"
GENERATION_MANIFEST_PATH = EXPERIMENT_ROOT / "generation-manifest.json"
EXPERIMENT_MANIFEST_PATH = EXPERIMENT_ROOT / "experiment-manifest.json"

SOURCE_SHA256 = case21.EXPECTED_SOURCE_SHA256
CONTEXT_SHA256 = case21.EXPECTED_CONTEXT_SHA256
SOURCE_URL = case21.EXPECTED_ORIG_URL
SOURCE_WIDTH = 1024
SOURCE_HEIGHT = 1024

HARD_BUDGET_CAP_USD = Decimal("3.00")
RESERVATION_BY_MODEL = {
    native.WAN_MODEL_ID: Decimal("0.50"),
    native.WAN_27_MODEL_ID: Decimal("0.50"),
    native.VEO_31_MODEL_ID: Decimal("0.20"),
}

PRIMARY_TREE_DIGEST = "0e7dc0d0fe9461a6c91d91df56aec4a1e49562929c756dc7913fab21e7cfe7a8"
RETRY_TREE_DIGEST = "54967ca5b10ef079a21deca6ab0de9835a0b0105da032d57e9364718c914e53b"


class ExperimentError(RuntimeError):
    """A fail-closed case-21 prompt experiment error."""


@dataclass(frozen=True)
class Variant:
    variant_id: str
    planning_run_id: str
    model_ids: tuple[str, ...]
    strategy: str
    negative_policy: str
    result_sha256: str


VARIANTS = (
    Variant(
        variant_id="monotonic-positive",
        planning_run_id="promopages-9930-case21-monotonic-positive-20260727-v1",
        model_ids=(native.WAN_MODEL_ID, native.WAN_27_MODEL_ID),
        strategy="first-frame-maximum with monotonic area and opacity decrease",
        negative_policy="must-be-null",
        result_sha256="addacbc3ef88d516b1a9d4ae564713ed71be5a16cb41623bc8256ec68d9c062a",
    ),
    Variant(
        variant_id="erosion-negative",
        planning_run_id="promopages-9930-case21-erosion-negative-20260727-v1",
        model_ids=(native.WAN_MODEL_ID, native.WAN_27_MODEL_ID),
        strategy="outside-in erosion with observed-failure negative repair",
        negative_policy="required-observed-repair",
        result_sha256="a2934ffa723151b82b869d835934407dbbcea7ac384a270412e3adbe3fc71664",
    ),
    Variant(
        variant_id="veo-motion-only",
        planning_run_id="promopages-9930-case21-veo-motion-only-20260727-v1",
        model_ids=(native.VEO_31_MODEL_ID,),
        strategy="benign literal motion-only diagnostic",
        negative_policy="must-be-null",
        result_sha256="df820159b155a45012f16d43d24c544dc8782882ed6118023118399989c03506",
    ),
)
VARIANT_BY_ID = {variant.variant_id: variant for variant in VARIANTS}


@dataclass(frozen=True)
class ExperimentSample(native.Sample):
    variant_id: str
    lite_run_id: str

    @property
    def planning_run_id(self) -> str:
        return self.lite_run_id


def _sample(variant: Variant) -> ExperimentSample:
    return ExperimentSample(
        sample_id=f"21-maier-04-{variant.variant_id}",
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
ENTRIES = tuple(
    native.Entry(SAMPLE_BY_VARIANT[variant.variant_id], model_id)
    for variant in VARIANTS
    for model_id in variant.model_ids
)
MODEL_IDS = (
    native.WAN_MODEL_ID,
    native.WAN_27_MODEL_ID,
    native.VEO_31_MODEL_ID,
)
EXPECTED_OUTPUTS = 5
RESERVED_COST_USD = sum(
    (RESERVATION_BY_MODEL[entry.model_id] for entry in ENTRIES),
    Decimal("0.00"),
)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise ExperimentError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExperimentError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ExperimentError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tree_digest(path: Path, root: Path = ROOT) -> str:
    """Match ``find | sort | shasum | shasum`` without shell state."""

    base = root / path
    if not base.is_dir() or base.is_symlink():
        raise ExperimentError(f"Control tree is missing or unsafe: {base}")
    lines: list[str] = []
    for file_path in sorted(item for item in base.rglob("*") if item.is_file()):
        relative = file_path.relative_to(root).as_posix()
        lines.append(f"{sha256_file(file_path)}  {relative}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def validate_control_trees(root: Path = ROOT) -> dict[str, str]:
    measured = {
        "primary": tree_digest(case21.BATCH_ROOT, root),
        "retry": tree_digest(case21.RETRY_BATCH_ROOT, root),
    }
    expected = {
        "primary": PRIMARY_TREE_DIGEST,
        "retry": RETRY_TREE_DIGEST,
    }
    if measured != expected:
        raise ExperimentError(
            f"Case-21 control batches changed: expected {expected}, got {measured}"
        )
    return measured


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ExperimentError(f"Invalid USD budget: {value!r}") from exc
    if budget < RESERVED_COST_USD:
        raise ExperimentError(
            f"Budget ${budget:.2f} is below the ${RESERVED_COST_USD:.2f} "
            "stage-1 reservation"
        )
    if budget > HARD_BUDGET_CAP_USD:
        raise ExperimentError(
            f"Budget ${budget:.2f} exceeds the ${HARD_BUDGET_CAP_USD:.2f} cap"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except ExperimentError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def cost_document(budget: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(budget)
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "reserved_stage1_usd": float(RESERVED_COST_USD),
        "unreserved_after_stage1_usd": float(parsed - RESERVED_COST_USD),
        "reservation_basis": {
            model_id: float(value)
            for model_id, value in RESERVATION_BY_MODEL.items()
        },
        "maximum_provider_entries": EXPECTED_OUTPUTS,
        "maximum_submissions_per_entry": 1,
        "automatic_paid_retries": False,
        "provider_unit_costs_asserted": False,
        "actual_billing_available": False,
        "note": (
            "Conservative operator reservations limit admitted entries; providers "
            "do not return actual billing metadata in these receipts."
        ),
    }


def _variant(entry: native.Entry) -> Variant:
    sample = entry.sample
    if not isinstance(sample, ExperimentSample):
        raise ExperimentError("Experiment entry uses an unexpected sample type")
    try:
        variant = VARIANT_BY_ID[sample.variant_id]
    except KeyError as exc:
        raise ExperimentError(f"Unknown prompt variant: {sample.variant_id}") from exc
    if entry.model_id not in variant.model_ids:
        raise ExperimentError(
            f"Model {entry.model_id} is forbidden for variant {variant.variant_id}"
        )
    return variant


def _provider_run_id(entry: native.Entry) -> str:
    return (
        f"{PROVIDER_BATCH_ID}-{entry.sample.sample_id}-"
        f"{native.MODEL_SUFFIXES[entry.model_id]}"
    )


def artifact_paths(entry: native.Entry, root: Path = ROOT) -> dict[str, Path]:
    variant = _variant(entry)
    base = (
        root
        / EXPERIMENT_ROOT
        / "videos"
        / variant.variant_id
        / native.MODEL_DIRECTORIES[entry.model_id]
    )
    return {
        "directory": base,
        "prompt": base / f"{case21.IMAGE_ID}.prompt.json",
        "run": base / f"{case21.IMAGE_ID}.run.json",
        "video": base / f"{case21.IMAGE_ID}.mp4",
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


def load_experiment_job(
    entry: native.Entry,
    root: Path = ROOT,
) -> native.LiteJob:
    variant = _variant(entry)
    summary = runner.provenance_summary(root, variant.planning_run_id)
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != case21.AGENT_ID
        or summary.get("contract_version") != "2.0.2"
        or summary.get("models") != list(variant.model_ids)
        or summary.get("source_image_sha256") != SOURCE_SHA256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
    ):
        raise ExperimentError(
            f"Lite provenance changed for {variant.planning_run_id}"
        )
    expected_result = (
        case21.ARTIFACT_NAMESPACE / variant.planning_run_id / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result:
        raise ExperimentError(f"Unexpected result path for {variant.planning_run_id}")
    result_path = root / expected_result
    if sha256_file(result_path) != variant.result_sha256:
        raise ExperimentError(f"Lite result changed for {variant.planning_run_id}")
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
        or [model.get("model_id") for model in models if isinstance(model, dict)]
        != list(variant.model_ids)
    ):
        raise ExperimentError(f"Lite result binding changed for {variant.planning_run_id}")
    model = next(
        item
        for item in models
        if isinstance(item, dict) and item.get("model_id") == entry.model_id
    )
    runtime = model.get("runtime")
    expected_runtime = read_json(root / case21.CONTRACT_PATH)["models"][entry.model_id][
        "runtime"
    ]
    positive = model.get("positive_prompt")
    negative = model.get("negative_prompt")
    if runtime != expected_runtime or not isinstance(positive, str) or not positive.strip():
        raise ExperimentError(f"Lite prompt/runtime changed for {entry.provider_run_id}")
    if variant.negative_policy == "must-be-null" and negative is not None:
        raise ExperimentError(f"Unexpected negative prompt for {variant.variant_id}")
    if variant.negative_policy == "required-observed-repair" and (
        not isinstance(negative, str) or not negative.strip()
    ):
        raise ExperimentError(f"Observed-failure repair is missing for {entry.model_id}")
    if entry.model_id == native.WAN_27_MODEL_ID and isinstance(negative, str) and len(negative) > 500:
        raise ExperimentError("Wan 2.7 repair exceeds the locked 500-character limit")
    analysis = result.get("analysis")
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(not isinstance(intent.get(key), str) or not intent[key].strip() for key in intent)
    ):
        raise ExperimentError(f"Structured intent changed for {variant.planning_run_id}")
    current_source = root / case21.SOURCE_PATH
    if not current_source.is_file() or sha256_file(current_source) != SOURCE_SHA256:
        raise ExperimentError("Current case-21 source image changed")
    return native.LiteJob(
        entry=entry,
        structured_intent={key: intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS},
        positive_prompt=positive.strip(),
        negative_prompt=negative.strip() if isinstance(negative, str) else None,
        result_path=expected_result,
        result_sha256=variant.result_sha256,
        provenance=summary,
        runtime=runtime,
    )


@contextmanager
def configured_native(root: Path = ROOT) -> Iterator[None]:
    """Bind the native bridge to the exact heterogeneous five-entry matrix."""

    case21.validate_routes()
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
        native.matrix = lambda: ENTRIES
        native.load_lite_job = lambda entry, workspace=root: load_experiment_job(
            entry, workspace
        )
        matrix = native.matrix()
        if (
            len(matrix) != EXPECTED_OUTPUTS
            or [entry.model_id for entry in matrix].count(native.VEO_31_MODEL_ID) != 1
            or any(entry.provider_run_id != _provider_run_id(entry) for entry in matrix)
        ):
            raise ExperimentError("Native experiment matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def inventory_document(
    budget: str | Decimal,
    root: Path = ROOT,
) -> dict[str, Any]:
    controls = validate_control_trees(root)
    source = case21.discover_case(root)
    case21.validate_public_orig_url(
        source.provider_source_url,
        source_image_id=source.image.get("source_image_id"),
        source_sha256=source.image.get("sha256"),
    )
    entries: list[dict[str, Any]] = []
    with configured_native(root):
        for entry in native.matrix():
            job = load_experiment_job(entry, root)
            request = native.provider_request_preview(
                native.provider_sample(entry), native.provider_prompt(job)
            )
            frame_url = (
                request.get("frame_images", [{}])[0]
                .get("image_url", {})
                .get("url")
                if entry.model_id != native.WAN_MODEL_ID
                else None
            )
            if entry.model_id != native.WAN_MODEL_ID and frame_url != SOURCE_URL:
                raise ExperimentError("Provider request lost the exact MDS /orig URL")
            entries.append(
                {
                    "variant_id": _variant(entry).variant_id,
                    "planning_run_id": entry.planning_run_id,
                    "planning_result_sha256": job.result_sha256,
                    "provider_run_id": entry.provider_run_id,
                    "sample_id": entry.sample.sample_id,
                    "model_id": entry.model_id,
                    "positive_prompt_sha256": sha256_text(job.positive_prompt),
                    "negative_prompt_sha256": (
                        sha256_text(job.negative_prompt)
                        if job.negative_prompt is not None
                        else None
                    ),
                    "reservation_usd": float(RESERVATION_BY_MODEL[entry.model_id]),
                    "provider_source": "local-upload" if entry.model_id == native.WAN_MODEL_ID else SOURCE_URL,
                    "request_sha256": transport.request_fingerprint(
                        request, native.provider_sample(entry)
                    ),
                }
            )
    return {
        "schema_version": 1,
        "manifest_role": "case-21-prompt-research-stage1",
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
        "controls": controls,
        "cost": cost_document(budget),
        "generation_policy": {
            "exact_model_routes": True,
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "automatic_retries": False,
            "force_allowed": False,
            "route_capacities": {
                native.WAN_MODEL_ID: 1,
                native.WAN_27_MODEL_ID: 3,
                native.VEO_31_MODEL_ID: 3,
            },
            "veo_policy": "one benign diagnostic submit; stop on rejection",
        },
        "expected_outputs": EXPECTED_OUTPUTS,
        "entries": entries,
    }


def write_inventory(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    document = inventory_document(budget, root)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise ExperimentError(f"Immutable experiment inventory differs: {path}")
        return document
    if path.exists():
        raise ExperimentError(f"Unsafe inventory target: {path}")
    transport.atomic_write_json(path, document)
    return document


def _experiment_document(
    budget: str | Decimal,
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    generation = read_json(root / GENERATION_MANIFEST_PATH)
    outputs = generation.get("outputs") if isinstance(generation, dict) else None
    if (
        not isinstance(generation, dict)
        or generation.get("ticket") != TICKET
        or generation.get("batch_id") != PROVIDER_BATCH_ID
        or generation.get("agent_id") != case21.AGENT_ID
        or generation.get("expected_outputs") != EXPECTED_OUTPUTS
        or not isinstance(outputs, list)
        or len(outputs) != EXPECTED_OUTPUTS
    ):
        raise ExperimentError("Experiment generation manifest must contain five outputs")
    by_identity = {
        (entry.sample.sample_id, entry.model_id): entry for entry in ENTRIES
    }
    enriched: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for output in outputs:
        if not isinstance(output, dict):
            raise ExperimentError("Experiment output identity changed")
        identity = (str(output.get("sample_id")), str(output.get("model_id")))
        entry = by_identity.get(identity)
        if (
            entry is None
            or identity in seen
            or output.get("lite_run_id") != entry.planning_run_id
            or output.get("provider_run_id") != _provider_run_id(entry)
        ):
            raise ExperimentError("Experiment output identity changed")
        seen.add(identity)
        enriched.append({**output, "variant_id": _variant(entry).variant_id})
    if seen != set(by_identity):
        raise ExperimentError("Experiment output identity changed")
    summary: dict[str, int] = {}
    for output in enriched:
        status = str(output.get("status"))
        summary[status] = summary.get(status, 0) + 1
    return {
        "schema_version": 1,
        "manifest_role": "case-21-prompt-research",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "updated_at": updated_at or transport.utc_now(),
        "source": inventory_document(budget, root)["source"],
        "cost": cost_document(budget),
        "expected_outputs": EXPECTED_OUTPUTS,
        "summary": summary,
        "planning_variants": [
            {
                "variant_id": variant.variant_id,
                "strategy": variant.strategy,
                "planning_run_id": variant.planning_run_id,
                "model_ids": list(variant.model_ids),
                "negative_policy": variant.negative_policy,
                "result_sha256": variant.result_sha256,
            }
            for variant in VARIANTS
        ],
        "controls": validate_control_trees(root),
        "inventory_path": INVENTORY_PATH.as_posix(),
        "generation_manifest_path": GENERATION_MANIFEST_PATH.as_posix(),
        "outputs": enriched,
    }


def write_experiment_manifest(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    document = _experiment_document(budget, root)
    transport.atomic_write_json(root / EXPERIMENT_MANIFEST_PATH, document)
    return document


def materialize(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    expected_inventory = inventory_document(budget, root)
    if not dry_run and read_json(root / INVENTORY_PATH) != expected_inventory:
        raise ExperimentError("Experiment inventory is missing or differs")
    with configured_native(root):
        if dry_run:
            for entry in native.matrix():
                job = native.load_lite_job(entry, root)
                native.provider_request_preview(
                    native.provider_sample(entry), native.provider_prompt(job)
                )
            print("PASS: five exact prompt-experiment requests validated; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != EXPECTED_OUTPUTS:
        raise ExperimentError("Expected five materialized experiment entries")
    write_experiment_manifest(budget, root)
    print("PASS: materialized five immutable prompt-experiment entries")
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
    expected_inventory = inventory_document(budget, root)
    if read_json(root / INVENTORY_PATH) != expected_inventory:
        raise ExperimentError("Experiment inventory is missing or differs")
    if not dry_run and not allow_external_processing:
        raise ExperimentError(
            "Real experiment requires --allow-external-processing because the "
            "source image and five prompts are sent to exact providers"
        )
    argv = [
        "run",
        "--wan22-concurrency",
        "1",
        "--wan27-concurrency",
        "3",
        "--veo31-concurrency",
        "3",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
        "--dry-run" if dry_run else "--allow-external-processing",
    ]

    def invoke() -> int:
        before = validate_control_trees(root)
        with configured_native(root):
            result = native.main(argv, root)
        after = validate_control_trees(root)
        if before != after:
            raise ExperimentError("Control batches changed during the experiment")
        write_experiment_manifest(budget, root)
        return result

    if dry_run:
        return invoke()
    with case21.batch_run_lock(root / case21.INVENTORY_PATH):
        return invoke()


def verify(
    budget: str | Decimal,
    *,
    root: Path = ROOT,
    allow_incomplete: bool = False,
    allow_contract_warnings: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        expected_inventory = inventory_document(budget, root)
        if read_json(root / INVENTORY_PATH) != expected_inventory:
            errors.append("Experiment inventory differs from exact stage-1 binding")
    except Exception as exc:
        errors.append(transport.safe_error(exc))
        return False, errors
    try:
        with configured_native(root):
            passed, native_errors = native.verify(
                root,
                allow_incomplete=allow_incomplete,
                allow_contract_warnings=allow_contract_warnings,
            )
        if not passed:
            errors.extend(native_errors)
    except Exception as exc:
        errors.append(transport.safe_error(exc))
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
                errors.append("Experiment manifest differs from current receipts")
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Experiment manifest is missing")
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
        required=True,
        metavar="USD",
        help="operator cap for this five-entry stage (2.20 through 3.00)",
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
                "PASS: prompt experiment reserves "
                f"${document['cost']['reserved_stage1_usd']:.2f} for five entries"
            )
            return 0
        if args.command == "plan":
            if not args.dry_run:
                write_inventory(args.budget_cap_usd, root)
            return materialize(
                args.budget_cap_usd,
                root=root,
                dry_run=args.dry_run,
            )
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
            print("PASS: case-21 prompt experiment is valid")
            return 0
        raise ExperimentError(f"Unknown command: {args.command}")
    except (ExperimentError, native.BatchPipelineError, transport.PipelineError, OSError) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
