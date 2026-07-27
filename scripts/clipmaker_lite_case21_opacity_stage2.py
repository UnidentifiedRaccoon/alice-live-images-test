#!/usr/bin/env python3
"""Run one fail-closed Clipmaker Lite case-21 opacity-only stage-2 generation.

This coordinator binds one verified Lite planning result to one immutable
Wan 2.7 provider entry.  It protects the primary batch, retry batch, and the
completed stage-1 prompt experiment; admits the entry only inside the aggregate
$3 operator envelope; and never discovers, falls back, forces, or retries.
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
EXPERIMENT_ID = "promopages-9930-case21-opacity-only-stage2-20260727-v1"
PLANNING_RUN_ID = "promopages-9930-case21-opacity-only-20260727-v1"
PROVIDER_BATCH_ID = "promopages-9930-case21-opacity-only-stage2-20260727-v1"
PLANNING_RESULT_SHA256 = (
    "57caec79fa7390a07101fbe314dc66b11f448291e271adc5eca8d447332187db"
)

EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / EXPERIMENT_ID
INVENTORY_PATH = EXPERIMENT_ROOT / "inventory.json"
GENERATION_MANIFEST_PATH = EXPERIMENT_ROOT / "generation-manifest.json"
EXPERIMENT_MANIFEST_PATH = EXPERIMENT_ROOT / "experiment-manifest.json"
STAGE1_EXPERIMENT_ROOT = (
    Path("clipmaker-lite-test/experiments")
    / "promopages-9930-case21-prompt-research-20260727-v1"
)

SOURCE_SHA256 = case21.EXPECTED_SOURCE_SHA256
CONTEXT_SHA256 = case21.EXPECTED_CONTEXT_SHA256
SOURCE_URL = case21.EXPECTED_ORIG_URL
SOURCE_WIDTH = 1024
SOURCE_HEIGHT = 1024

MODEL_IDS = (native.WAN_27_MODEL_ID,)
EXPECTED_OUTPUTS = 1
STAGE1_RESERVED_USD = Decimal("2.20")
STAGE2_RESERVED_USD = Decimal("0.50")
AGGREGATE_RESERVED_USD = STAGE1_RESERVED_USD + STAGE2_RESERVED_USD
HARD_AGGREGATE_BUDGET_CAP_USD = Decimal("3.00")

PRIMARY_TREE_DIGEST = (
    "0e7dc0d0fe9461a6c91d91df56aec4a1e49562929c756dc7913fab21e7cfe7a8"
)
RETRY_TREE_DIGEST = (
    "54967ca5b10ef079a21deca6ab0de9835a0b0105da032d57e9364718c914e53b"
)
STAGE1_EXPERIMENT_CORE_DIGEST = (
    "bbb230607f881491635dfab3e9a9d970d49eafdaabdbc1f2582d405076004f51"
)


class Stage2Error(RuntimeError):
    """A fail-closed case-21 stage-2 orchestration error."""


@dataclass(frozen=True)
class OpacitySample(native.Sample):
    lite_run_id: str

    @property
    def planning_run_id(self) -> str:
        return self.lite_run_id


SAMPLE = OpacitySample(
    sample_id="21-maier-04-opacity-only",
    article_slug=case21.ARTICLE_SLUG,
    image_id=case21.IMAGE_ID,
    filename=case21.IMAGE_FILENAME,
    source_sha256=SOURCE_SHA256,
    width=SOURCE_WIDTH,
    height=SOURCE_HEIGHT,
    lite_run_id=PLANNING_RUN_ID,
)
SAMPLES = (SAMPLE,)
ENTRY = native.Entry(SAMPLE, native.WAN_27_MODEL_ID)
ENTRIES = (ENTRY,)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise Stage2Error(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Stage2Error(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise Stage2Error(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tree_digest(
    path: Path,
    root: Path = ROOT,
    *,
    excluded_top_levels: tuple[str, ...] = (),
    excluded_name_suffixes: tuple[str, ...] = (),
) -> str:
    """Hash a control tree, including identities and explicit exclusions."""

    base = root / path
    if not base.is_dir() or base.is_symlink():
        raise Stage2Error(f"Control tree is missing or unsafe: {base}")
    lines: list[str] = []
    for file_path in sorted(item for item in base.rglob("*") if item.is_file()):
        relative_to_base = file_path.relative_to(base)
        if (
            relative_to_base.parts
            and relative_to_base.parts[0] in excluded_top_levels
        ):
            continue
        if any(file_path.name.endswith(suffix) for suffix in excluded_name_suffixes):
            continue
        relative = file_path.relative_to(root).as_posix()
        lines.append(f"{sha256_file(file_path)}  {relative}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def validate_control_trees(root: Path = ROOT) -> dict[str, str]:
    measured = {
        "primary": tree_digest(case21.BATCH_ROOT, root),
        "retry": tree_digest(case21.RETRY_BATCH_ROOT, root),
        "stage1_generation_core": tree_digest(
            STAGE1_EXPERIMENT_ROOT,
            root,
            excluded_top_levels=("review",),
            excluded_name_suffixes=(".review.json",),
        ),
    }
    expected = {
        "primary": PRIMARY_TREE_DIGEST,
        "retry": RETRY_TREE_DIGEST,
        "stage1_generation_core": STAGE1_EXPERIMENT_CORE_DIGEST,
    }
    if measured != expected:
        raise Stage2Error(
            f"Case-21 control trees changed: expected {expected}, got {measured}"
        )
    return measured


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise Stage2Error(f"Invalid aggregate USD budget: {value!r}") from exc
    if budget < AGGREGATE_RESERVED_USD:
        raise Stage2Error(
            f"Budget ${budget:.2f} is below the ${AGGREGATE_RESERVED_USD:.2f} "
            "aggregate stage-1 plus stage-2 reservation"
        )
    if budget > HARD_AGGREGATE_BUDGET_CAP_USD:
        raise Stage2Error(
            f"Budget ${budget:.2f} exceeds the "
            f"${HARD_AGGREGATE_BUDGET_CAP_USD:.2f} aggregate cap"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except Stage2Error as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def cost_document(budget: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(budget)
    return {
        "currency": "USD",
        "operator_aggregate_budget_cap_usd": float(parsed),
        "hard_aggregate_budget_cap_usd": float(HARD_AGGREGATE_BUDGET_CAP_USD),
        "reserved_stage1_usd": float(STAGE1_RESERVED_USD),
        "reserved_stage2_usd": float(STAGE2_RESERVED_USD),
        "reserved_aggregate_usd": float(AGGREGATE_RESERVED_USD),
        "unreserved_after_stage2_usd": float(parsed - AGGREGATE_RESERVED_USD),
        "stage2_model_id": native.WAN_27_MODEL_ID,
        "stage2_maximum_provider_entries": EXPECTED_OUTPUTS,
        "maximum_submissions_per_stage2_entry": 1,
        "automatic_paid_retries": False,
        "provider_unit_costs_asserted": False,
        "actual_billing_available": False,
        "note": (
            "The $0.50 stage-2 reservation is conservative operator metadata. "
            "Provider receipts do not expose actual billing."
        ),
    }


def _provider_run_id(entry: native.Entry = ENTRY) -> str:
    if entry != ENTRY:
        raise Stage2Error("Stage-2 provider identity is restricted to one entry")
    return (
        f"{PROVIDER_BATCH_ID}-{SAMPLE.sample_id}-"
        f"{native.MODEL_SUFFIXES[native.WAN_27_MODEL_ID]}"
    )


def artifact_paths(entry: native.Entry, root: Path = ROOT) -> dict[str, Path]:
    if entry != ENTRY:
        raise Stage2Error("Stage-2 artifact path requested for an unknown entry")
    base = root / EXPERIMENT_ROOT / "videos" / native.MODEL_DIRECTORIES[entry.model_id]
    return {
        "directory": base,
        "prompt": base / f"{case21.IMAGE_ID}.prompt.json",
        "run": base / f"{case21.IMAGE_ID}.run.json",
        "video": base / f"{case21.IMAGE_ID}.mp4",
    }


def provider_sample(entry: native.Entry) -> dict[str, Any]:
    if entry != ENTRY:
        raise Stage2Error("Stage-2 provider sample requested for an unknown entry")
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


def load_stage2_job(
    entry: native.Entry,
    root: Path = ROOT,
) -> native.LiteJob:
    if entry != ENTRY or entry.model_id != native.WAN_27_MODEL_ID:
        raise Stage2Error("Stage-2 loader accepts only the exact Wan 2.7 entry")
    summary = runner.provenance_summary(root, PLANNING_RUN_ID)
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != case21.AGENT_ID
        or summary.get("contract_version") != "2.0.2"
        or summary.get("models") != [native.WAN_27_MODEL_ID]
        or summary.get("source_image_sha256") != SOURCE_SHA256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
    ):
        raise Stage2Error(f"Lite provenance changed for {PLANNING_RUN_ID}")
    expected_result = (
        case21.ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result:
        raise Stage2Error(f"Unexpected Lite result path for {PLANNING_RUN_ID}")
    result_path = root / expected_result
    if sha256_file(result_path) != PLANNING_RESULT_SHA256:
        raise Stage2Error(f"Lite result changed for {PLANNING_RUN_ID}")
    result = read_json(result_path)
    if not isinstance(result, dict):
        raise Stage2Error("Stage-2 Lite result is not a JSON object")
    producer = result.get("producer")
    inputs = result.get("inputs")
    source = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    models = result.get("models")
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
        or models[0].get("model_id") != native.WAN_27_MODEL_ID
    ):
        raise Stage2Error("Stage-2 Lite result binding changed")
    model = models[0]
    runtime = model.get("runtime")
    expected_runtime = read_json(root / case21.CONTRACT_PATH)["models"][
        native.WAN_27_MODEL_ID
    ]["runtime"]
    positive = model.get("positive_prompt")
    negative = model.get("negative_prompt")
    if runtime != expected_runtime:
        raise Stage2Error("Stage-2 Wan 2.7 runtime changed")
    if not isinstance(positive, str) or not positive.strip():
        raise Stage2Error("Stage-2 positive prompt is missing")
    if not isinstance(negative, str) or not negative.strip():
        raise Stage2Error("Stage-2 observed-failure negative repair is missing")
    if len(negative) > 500:
        raise Stage2Error("Stage-2 negative repair exceeds the 500-character limit")
    analysis = result.get("analysis")
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(
            not isinstance(intent.get(key), str) or not intent[key].strip()
            for key in runner.STRUCTURED_INTENT_KEYS
        )
    ):
        raise Stage2Error("Stage-2 structured intent changed")
    if sha256_file(root / case21.SOURCE_PATH) != SOURCE_SHA256:
        raise Stage2Error("Current case-21 source image changed")
    if sha256_file(root / case21.CONTEXT_PATH) != CONTEXT_SHA256:
        raise Stage2Error("Current case-21 article context changed")
    return native.LiteJob(
        entry=entry,
        structured_intent={
            key: intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS
        },
        positive_prompt=positive.strip(),
        negative_prompt=negative.strip(),
        result_path=expected_result,
        result_sha256=PLANNING_RESULT_SHA256,
        provenance=summary,
        runtime=runtime,
    )


@contextmanager
def configured_native(root: Path = ROOT) -> Iterator[None]:
    """Scope the native bridge to one immutable Wan 2.7 stage-2 entry."""

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
        native.PLANNING_BATCH_ID = PLANNING_RUN_ID
        native.MODEL_IDS = MODEL_IDS
        native.PLANNING_MODEL_IDS = MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = GENERATION_MANIFEST_PATH
        native.CONTRACT_PATH = root / case21.CONTRACT_PATH
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = None
        native.SAMPLES = SAMPLES
        native.WAN_SUBMIT_MODE = None
        native.artifact_paths = (
            lambda entry, workspace=root: artifact_paths(entry, workspace)
        )
        native.provider_sample = provider_sample
        native.matrix = lambda: ENTRIES
        native.load_lite_job = (
            lambda entry, workspace=root: load_stage2_job(entry, workspace)
        )
        matrix = native.matrix()
        if (
            matrix != ENTRIES
            or len(matrix) != EXPECTED_OUTPUTS
            or matrix[0].model_id != native.WAN_27_MODEL_ID
            or matrix[0].provider_run_id != _provider_run_id()
        ):
            raise Stage2Error("Native stage-2 matrix identity changed")
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
    with configured_native(root):
        entry = native.matrix()[0]
        job = native.load_lite_job(entry, root)
        sample = native.provider_sample(entry)
        request = native.provider_request_preview(
            sample,
            native.provider_prompt(job),
        )
    frame_images = request.get("frame_images")
    if (
        request.get("model") != native.WAN_27_MODEL_ID
        or not isinstance(frame_images, list)
        or len(frame_images) != 1
        or frame_images[0].get("image_url", {}).get("url") != SOURCE_URL
    ):
        raise Stage2Error("Wan 2.7 request lost the exact MDS /orig first frame")
    return {
        "schema_version": 1,
        "manifest_role": "case-21-opacity-only-stage2",
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
            "stage2_maximum_submissions": 1,
            "route_capacity": 1,
        },
        "expected_outputs": EXPECTED_OUTPUTS,
        "entries": [
            {
                "planning_run_id": PLANNING_RUN_ID,
                "planning_result_sha256": PLANNING_RESULT_SHA256,
                "provider_run_id": _provider_run_id(),
                "sample_id": SAMPLE.sample_id,
                "model_id": native.WAN_27_MODEL_ID,
                "positive_prompt_sha256": sha256_text(job.positive_prompt),
                "negative_prompt_sha256": sha256_text(job.negative_prompt or ""),
                "reservation_usd": float(STAGE2_RESERVED_USD),
                "provider_source": SOURCE_URL,
                "request_sha256": transport.request_fingerprint(request, sample),
            }
        ],
    }


def write_inventory(budget: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    document = inventory_document(budget, root)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise Stage2Error(f"Immutable stage-2 inventory differs: {path}")
        return document
    if path.exists():
        raise Stage2Error(f"Unsafe stage-2 inventory target: {path}")
    transport.atomic_write_json(path, document)
    return document


def _experiment_document(
    budget: str | Decimal,
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    generation = read_json(root / GENERATION_MANIFEST_PATH)
    outputs = generation.get("outputs") if isinstance(generation, dict) else None
    if not isinstance(outputs, list) or len(outputs) != EXPECTED_OUTPUTS:
        raise Stage2Error("Stage-2 generation manifest must contain one output")
    output = outputs[0]
    if (
        not isinstance(output, dict)
        or output.get("sample_id") != SAMPLE.sample_id
        or output.get("model_id") != native.WAN_27_MODEL_ID
        or output.get("provider_run_id") != _provider_run_id()
    ):
        raise Stage2Error("Stage-2 output identity changed")
    status = str(output.get("status"))
    inventory = inventory_document(budget, root)
    return {
        "schema_version": 1,
        "manifest_role": "case-21-opacity-only-stage2-result",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "updated_at": updated_at or transport.utc_now(),
        "source": inventory["source"],
        "cost": cost_document(budget),
        "expected_outputs": EXPECTED_OUTPUTS,
        "summary": {status: 1},
        "planning": {
            "run_id": PLANNING_RUN_ID,
            "result_sha256": PLANNING_RESULT_SHA256,
            "model_ids": [native.WAN_27_MODEL_ID],
            "negative_policy": "required-observed-failure-repair",
        },
        "controls": validate_control_trees(root),
        "inventory_path": INVENTORY_PATH.as_posix(),
        "generation_manifest_path": GENERATION_MANIFEST_PATH.as_posix(),
        "outputs": outputs,
    }


def write_experiment_manifest(
    budget: str | Decimal,
    root: Path = ROOT,
) -> dict[str, Any]:
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
        raise Stage2Error("Stage-2 inventory is missing or differs")
    with configured_native(root):
        if dry_run:
            entry = native.matrix()[0]
            job = native.load_lite_job(entry, root)
            native.provider_request_preview(
                native.provider_sample(entry),
                native.provider_prompt(job),
            )
            print("PASS: exact opacity-only stage-2 request validated; no files written")
            return 0
        rows = native.materialize(root)
    if len(rows) != EXPECTED_OUTPUTS:
        raise Stage2Error("Expected one materialized opacity-only entry")
    write_experiment_manifest(budget, root)
    print("PASS: materialized one immutable opacity-only stage-2 entry")
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
        raise Stage2Error("Stage-2 inventory is missing or differs")
    if not dry_run and not allow_external_processing:
        raise Stage2Error(
            "Real stage-2 generation requires --allow-external-processing because "
            "the exact source image and opacity-only prompt are sent to Wan 2.7"
        )
    argv = [
        "run",
        "--wan27-concurrency",
        "1",
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
            raise Stage2Error("Control trees changed during stage 2")
        write_experiment_manifest(budget, root)
        return result

    if dry_run:
        return invoke()
    with case21.batch_run_lock(root / INVENTORY_PATH):
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
            errors.append("Stage-2 inventory differs from its exact binding")
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
                errors.append("Stage-2 experiment manifest differs from receipts")
        except Exception as exc:
            errors.append(transport.safe_error(exc))
    elif not allow_incomplete:
        errors.append("Stage-2 experiment manifest is missing")
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
        help="aggregate operator cap for stages 1 and 2 (2.70 through 3.00)",
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
                "PASS: opacity-only stage 2 reserves "
                f"${document['cost']['reserved_aggregate_usd']:.2f} aggregate"
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
            print("PASS: case-21 opacity-only stage 2 is valid")
            return 0
        raise Stage2Error(f"Unknown command: {args.command}")
    except (
        Stage2Error,
        native.BatchPipelineError,
        case21.PipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
