#!/usr/bin/env python3
"""Generate the immutable 28-output PROMOPAGES-10060 Tune v5 I2V batch.

The coordinator consumes only the verified v5 prompt manifest.  Every admitted
target must be Clipmaker Lite I2V with a non-empty prompt.  It resolves the
transport by exact model ID from the committed route registry, starts the three
independent route pools together (1/3/3), reserves exactly $9.80 at the frozen
$0.35 accounting rate, and permits at most one paid submit per immutable
provider run ID.  There is no compositor, fallback, cross-route retry or S3
path.  A downloaded MP4 remains reviewable when media QA marks it
``verification-failed``.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as pools  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import clipmaker_lite_tune_v5_pipeline as tune_planning  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
PLANNING_BATCH_ID = tune_planning.REPAIR_BATCH_ID
BATCH_ID = "promopages-10060-tune-videos-20260811-v5"
EXPECTED_CONTRACT_VERSION = "2.3.0"
PROMPT_MANIFEST_REL = Path(
    "clipmaker-lite-test/runs/"
    f"{PLANNING_BATCH_ID}/prompt-manifest.json"
)
CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"

MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
MODEL_SUFFIXES = {
    "alibaba/wan-2.2": "wan-2-2",
    "alibaba/wan-2.7": "wan-2-7",
    "google/veo-3.1-lite": "veo-3-1-lite",
}
MODEL_DIRECTORIES = {
    "alibaba/wan-2.2": "wan-2.2",
    "alibaba/wan-2.7": "wan-2.7",
    "google/veo-3.1-lite": "veo-3.1-lite",
}
EXPECTED_BY_MODEL = {
    "alibaba/wan-2.2": 11,
    "alibaba/wan-2.7": 5,
    "google/veo-3.1-lite": 12,
}
EXPECTED_TARGETS = 28
EXPECTED_ROUTE_CAPACITIES = {
    "alibaba/wan-2.2": 1,
    "alibaba/wan-2.7": 3,
    "google/veo-3.1-lite": 3,
}
ACCOUNTING_COST_PER_OUTPUT_USD = Decimal("0.35")
REQUIRED_BUDGET_CAP_USD = Decimal("9.80")
MAX_PROVIDER_SOURCE_BYTES = 20 * 1024 * 1024
BLOCKED_PAID_STATUSES = {
    "submitting",
    "submit-unknown",
    "provider-failed",
    "verification-failed",
    "stale",
    "failed",
}


class TuneV5VideoError(RuntimeError):
    """The v5 generation batch failed a frozen binding or provider guard."""


@dataclass(frozen=True)
class Entry:
    case_id: str
    sheet_row: int
    article_slug: str
    image_id: str
    model_id: str
    source_path: str
    source_url: str
    source_sha256: str
    width: int
    height: int
    planning_run_id: str
    result_path: str
    result_sha256: str
    prompt_manifest_sha256: str
    route_registry_sha256: str
    repair_feedback_path: str
    repair_feedback_sha256: str
    scene_plan: str
    positive_prompt: str
    runtime: dict[str, Any]
    provenance: dict[str, Any]

    @property
    def provider_run_id(self) -> str:
        return (
            f"{BATCH_ID}-{self.article_slug}-{self.image_id}-"
            f"{MODEL_SUFFIXES[self.model_id]}"
        )

    @property
    def run_id(self) -> str:
        return self.provider_run_id


@dataclass(frozen=True)
class Inventory:
    entries: tuple[Entry, ...]
    prompt_manifest_sha256: str
    contract_sha256: str
    route_registry_sha256: str
    budget: dict[str, Any]


@dataclass(frozen=True)
class ProviderOperations:
    eliza_headers: Callable[[], dict[str, str]]
    http_json: Callable[..., Any]
    eliza_poll: Callable[..., dict[str, Any]]
    http_download: Callable[..., None]
    segmind_generate: Callable[..., dict[str, Any]]
    media_probe: Callable[[Path], dict[str, Any]]


def default_provider_operations() -> ProviderOperations:
    return ProviderOperations(
        eliza_headers=transport.eliza_headers,
        http_json=transport.http_json,
        eliza_poll=transport.eliza_poll,
        http_download=transport.http_download,
        segmind_generate=transport.segmind_generate,
        media_probe=transport.ffprobe_media,
    )


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TuneV5VideoError(f"Required JSON is missing: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TuneV5VideoError(f"Invalid JSON: {path}") from exc


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError as exc:
        raise TuneV5VideoError(f"Required file is missing: {path}") from exc


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneV5VideoError(f"Artifact is outside the workspace: {path}") from exc


def safe_relative(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TuneV5VideoError(f"{label} must be a canonical relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise TuneV5VideoError(f"Unsafe {label}: {value!r}")
    return value


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise TuneV5VideoError("--budget-cap-usd must be decimal") from exc
    if parsed != REQUIRED_BUDGET_CAP_USD:
        raise TuneV5VideoError(
            "This immutable 28-output batch requires --budget-cap-usd 9.80 exactly"
        )
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except TuneV5VideoError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def budget_document(value: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(value)
    reserved = ACCOUNTING_COST_PER_OUTPUT_USD * EXPECTED_TARGETS
    if reserved != parsed:
        raise TuneV5VideoError("Frozen output reservations do not equal budget cap")
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(REQUIRED_BUDGET_CAP_USD),
        "accounting_cost_per_output_usd": float(ACCOUNTING_COST_PER_OUTPUT_USD),
        "reserved_output_count": EXPECTED_TARGETS,
        "maximum_estimated_cost_usd": float(reserved),
        "provider_unit_costs_asserted": False,
        "basis": "frozen local accounting; one paid submit per immutable provider run",
        "automatic_paid_retry": False,
    }


def _validate_routes(root: Path) -> tuple[dict[str, Any], str]:
    path = root / ROUTES_REL
    document = read_json(path)
    if (
        not isinstance(document, dict)
        or document.get("policy", {}).get("automatic_fallback") is not False
        or document.get("policy", {}).get("normal_run_discovery") is not False
        or tuple(document.get("models", {})) != MODEL_IDS
    ):
        raise TuneV5VideoError("Generation route registry identity changed")
    for model_id, capacity in EXPECTED_ROUTE_CAPACITIES.items():
        route = document["models"][model_id]
        if route.get("capacity") != capacity:
            raise TuneV5VideoError(f"Route capacity changed: {model_id}")
        if root.resolve() == ROOT.resolve() and route != transport.route_for_model(model_id):
            raise TuneV5VideoError(f"Transport route differs from registry: {model_id}")
    return document, sha256_file(path)


def _validate_contract(root: Path) -> tuple[dict[str, Any], str]:
    path = root / CONTRACT_REL
    contract = read_json(path)
    if (
        not isinstance(contract, dict)
        or contract.get("agent_id") != AGENT_ID
        or contract.get("contract_version") != EXPECTED_CONTRACT_VERSION
        or tuple(contract.get("models", {})) != MODEL_IDS
    ):
        raise TuneV5VideoError("Unexpected Clipmaker Lite 2.3 contract")
    return contract, sha256_file(path)


def _provenance(root: Path, run_id: str) -> dict[str, Any]:
    try:
        summary = runner.provenance_summary(root, run_id)
    except Exception as exc:
        raise TuneV5VideoError(
            f"Lite provenance failed for {run_id}: {transport.safe_error(exc)}"
        ) from exc
    if summary.get("verified") is not True or summary.get("contract_version") != EXPECTED_CONTRACT_VERSION:
        raise TuneV5VideoError(f"Lite 2.3 provenance is not verified: {run_id}")
    return summary


def load_inventory(
    budget_cap_usd: str | Decimal,
    *,
    root: Path = ROOT,
    prompt_manifest_path: Path | None = None,
) -> Inventory:
    root = root.resolve()
    budget = budget_document(budget_cap_usd)
    routes, route_sha256 = _validate_routes(root)
    contract, contract_sha256 = _validate_contract(root)
    manifest_path = prompt_manifest_path or (root / PROMPT_MANIFEST_REL)
    manifest = read_json(manifest_path)
    manifest_sha256 = sha256_file(manifest_path)
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("manifest_role") != "clipmaker-lite-tune-v5-planning"
        or manifest.get("ticket") != TICKET
        or manifest.get("batch_id") != PLANNING_BATCH_ID
        or manifest.get("agent_id") != AGENT_ID
        or manifest.get("contract_version") != EXPECTED_CONTRACT_VERSION
        or manifest.get("scope", {}).get("target_count") != EXPECTED_TARGETS
        or manifest.get("scope", {}).get("required_execution_mode") != "i2v"
        or manifest.get("scope", {}).get("fallback") is not False
        or not isinstance(manifest.get("cases"), list)
        or len(manifest["cases"]) != 17
    ):
        raise TuneV5VideoError("Unexpected v5 prompt manifest identity")

    entries: list[Entry] = []
    seen: set[tuple[str, str]] = set()
    provider_run_ids: set[str] = set()
    verified: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}
    counts = {model_id: 0 for model_id in MODEL_IDS}
    for case in manifest["cases"]:
        case_id = case.get("case_id")
        article_slug = case.get("article_slug")
        source = case.get("source")
        planning = case.get("planning")
        context_binding = case.get("context_binding")
        repair_revision = case.get("repair_revision")
        targets = case.get("targets")
        if (
            not isinstance(case_id, str)
            or not isinstance(article_slug, str)
            or not isinstance(source, dict)
            or not isinstance(planning, dict)
            or not isinstance(context_binding, dict)
            or not isinstance(targets, list)
            or repair_revision != tune_planning.planning_revision_for_case(str(case_id))
        ):
            raise TuneV5VideoError("v5 prompt case shape is invalid")
        source_path = safe_relative(source.get("path"), label="source.path")
        source_file = root / source_path
        if (
            sha256_file(source_file) != source.get("sha256")
            or source_file.stat().st_size > MAX_PROVIDER_SOURCE_BYTES
        ):
            raise TuneV5VideoError(f"Canonical source binding changed: {case_id}")
        if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
            raise TuneV5VideoError(f"Canonical source URL is invalid: {case_id}")
        run_id = planning.get("run_id")
        result_path = safe_relative(planning.get("result_path"), label="planning.result_path")
        expected_planning_batch = tune_planning.planning_batch_id_for_case(case_id)
        if not isinstance(run_id, str) or not run_id.startswith(f"{expected_planning_batch}-"):
            raise TuneV5VideoError(f"v5 planning run ID is invalid: {case_id}")
        if run_id not in verified:
            provenance = _provenance(root, run_id)
            result = read_json(root / result_path)
            result_sha256 = sha256_file(root / result_path)
            if (
                planning.get("result_sha256") != result_sha256
                or planning.get("provenance") != provenance
                or result.get("producer", {}).get("contract_version") != EXPECTED_CONTRACT_VERSION
                or provenance.get("source_image_sha256") != source.get("sha256")
                or provenance.get("article_context_sha256") != context_binding.get("sha256")
            ):
                raise TuneV5VideoError(f"v5 result binding changed: {run_id}")
            verified[run_id] = (provenance, result, result_sha256)
        provenance, result, result_sha256 = verified[run_id]
        result_models = {
            model.get("model_id"): model
            for model in result.get("models", [])
            if isinstance(model, dict)
        }
        repair_input = result.get("inputs", {}).get("repair_feedback")
        source_input = result.get("inputs", {}).get("source_image")
        context_input = result.get("inputs", {}).get("article_context")
        if (
            not isinstance(repair_input, dict)
            or repair_input.get("path") != planning.get("repair_feedback_path")
            or repair_input.get("canonical_sha256") != planning.get("repair_feedback_sha256")
            or not isinstance(source_input, dict)
            or source_input.get("path") != source_path
            or source_input.get("sha256") != source.get("sha256")
            or not isinstance(context_input, dict)
            or context_input.get("path") != context_binding.get("path")
            or context_input.get("sha256") != context_binding.get("sha256")
            or context_input.get("locator") != context_binding.get("locator")
        ):
            raise TuneV5VideoError(f"v5 result input binding changed: {case_id}")
        for target in targets:
            model_id = target.get("model_id")
            tuned = target.get("tuned")
            key = (case_id, str(model_id))
            model = result_models.get(model_id)
            if (
                model_id not in MODEL_IDS
                or key in seen
                or not isinstance(target.get("sheet_row"), int)
                or not isinstance(tuned, dict)
                or not isinstance(model, dict)
                or tuned.get("execution_mode") != "i2v"
                or model.get("execution_mode") != "i2v"
                or tuned.get("positive_prompt") != model.get("positive_prompt")
                or tuned.get("scene_plan") != model.get("scene_plan")
                or not isinstance(model.get("positive_prompt"), str)
                or not model["positive_prompt"].strip()
                or tuned.get("negative_prompt") is not None
                or model.get("negative_prompt") is not None
                or tuned.get("runtime") != contract["models"][model_id]["runtime"]
                or model.get("runtime") != contract["models"][model_id]["runtime"]
            ):
                raise TuneV5VideoError(f"v5 target is not exact I2V: {key}")
            if routes["models"].get(model_id) is None:
                raise TuneV5VideoError(f"No exact generation route: {model_id}")
            seen.add(key)
            counts[model_id] += 1
            entries.append(
                Entry(
                    case_id=case_id,
                    sheet_row=target["sheet_row"],
                    article_slug=article_slug,
                    image_id=str(source["image_id"]),
                    model_id=model_id,
                    source_path=source_path,
                    source_url=source["url"],
                    source_sha256=source["sha256"],
                    width=int(source["width"]),
                    height=int(source["height"]),
                    planning_run_id=run_id,
                    result_path=result_path,
                    result_sha256=result_sha256,
                    prompt_manifest_sha256=manifest_sha256,
                    route_registry_sha256=route_sha256,
                    repair_feedback_path=planning["repair_feedback_path"],
                    repair_feedback_sha256=planning["repair_feedback_sha256"],
                    scene_plan=model["scene_plan"],
                    positive_prompt=model["positive_prompt"],
                    runtime=copy.deepcopy(model["runtime"]),
                    provenance=copy.deepcopy(provenance),
                )
            )
            provider_run_id = entries[-1].provider_run_id
            if provider_run_id in provider_run_ids:
                raise TuneV5VideoError(f"Duplicate immutable provider run ID: {provider_run_id}")
            provider_run_ids.add(provider_run_id)
    seen_evaluation_ids = {f"{case_id}::{model_id}" for case_id, model_id in seen}
    if (
        len(entries) != EXPECTED_TARGETS
        or counts != EXPECTED_BY_MODEL
        or seen_evaluation_ids != tune_planning.EXPECTED_REGENERATE_KEYS
        or len(provider_run_ids) != EXPECTED_TARGETS
    ):
        raise TuneV5VideoError(f"v5 I2V matrix changed: count={len(entries)}, models={counts}")
    return Inventory(
        entries=tuple(entries),
        prompt_manifest_sha256=manifest_sha256,
        contract_sha256=contract_sha256,
        route_registry_sha256=route_sha256,
        budget=budget,
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
    prompt: dict[str, Any] = {
        "sample_id": f"{entry.article_slug}-{entry.image_id}",
        "model_id": entry.model_id,
        "target_duration_seconds": entry.runtime["duration_seconds"],
        "positive_prompt": entry.positive_prompt,
        "negative_prompt": None,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
    }
    if entry.model_id == "alibaba/wan-2.7":
        prompt["prompt_extend"] = True
    return prompt


def artifact_paths(entry: Entry, output_root: Path = ROOT) -> dict[str, Path]:
    base = (
        output_root
        / BATCH_ROOT_REL
        / "videos"
        / entry.article_slug
        / MODEL_DIRECTORIES[entry.model_id]
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
        "manifest_role": "clipmaker-lite-tune-v5-video-prompt",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": entry.model_id,
        "execution_mode": "i2v",
        "source": {
            "path": entry.source_path,
            "url": entry.source_url,
            "sha256": entry.source_sha256,
            "width": entry.width,
            "height": entry.height,
            "normalized_overlay": None,
        },
        "scene_plan": entry.scene_plan,
        "prompt": {
            "positive": entry.positive_prompt,
            "negative": None,
            "rewritten": False,
        },
        "runtime": entry.runtime,
        "planning": {
            "batch_id": PLANNING_BATCH_ID,
            "run_id": entry.planning_run_id,
            "result_path": entry.result_path,
            "result_sha256": entry.result_sha256,
            "repair_feedback_path": entry.repair_feedback_path,
            "repair_feedback_sha256": entry.repair_feedback_sha256,
            "provenance": entry.provenance,
        },
        "bindings": {
            "prompt_manifest_path": PROMPT_MANIFEST_REL.as_posix(),
            "prompt_manifest_sha256": entry.prompt_manifest_sha256,
            "generation_routes_path": ROUTES_REL.as_posix(),
            "generation_routes_sha256": entry.route_registry_sha256,
        },
    }


def _initial_run(entry: Entry, paths: dict[str, Path], output_root: Path) -> dict[str, Any]:
    route = transport.route_for_model(entry.model_id)
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-video-run",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "planning_run_id": entry.planning_run_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": entry.model_id,
        "execution_mode": "i2v",
        "adapter": route["adapter"],
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
        "media": None,
        "contract_check": None,
        "error": None,
        "automatic_paid_retry": False,
        "fallback": None,
        "s3_upload": False,
    }


def materialize_entry(entry: Entry, *, output_root: Path = ROOT) -> dict[str, Any]:
    paths = artifact_paths(entry, output_root)
    paths["directory"].mkdir(parents=True, exist_ok=True)
    expected_prompt = prompt_artifact(entry)
    if paths["prompt"].exists():
        if read_json(paths["prompt"]) != expected_prompt:
            raise TuneV5VideoError(f"Immutable prompt changed: {paths['prompt']}")
    else:
        transport.atomic_write_json(paths["prompt"], expected_prompt)
    expected_run = _initial_run(entry, paths, output_root)
    if paths["run"].exists():
        run = read_json(paths["run"])
        immutable = {
            key: expected_run[key]
            for key in (
                "manifest_role", "ticket", "batch_id", "agent_id",
                "provider_run_id", "planning_run_id", "case_id", "sheet_row",
                "model_id", "execution_mode", "adapter", "prompt_path",
                "output_path", "automatic_paid_retry", "fallback", "s3_upload",
            )
        }
        if any(run.get(key) != value for key, value in immutable.items()):
            raise TuneV5VideoError(f"Immutable run identity changed: {paths['run']}")
    else:
        transport.atomic_write_json(paths["run"], expected_run)
    return {
        "entry": entry,
        "sample": provider_sample(entry),
        "prompt": provider_prompt(entry),
        "paths": paths,
    }


def _worker_result(
    row: dict[str, Any],
    *,
    failed: bool,
    status: str,
    error: str | None = None,
    holds_provider_slot: bool = False,
) -> pools.WorkerResult:
    return pools.WorkerResult(
        row=row,
        failed=failed,
        status=status,
        error=error,
        holds_provider_slot=holds_provider_slot,
    )


def _persist(path: Path, run: dict[str, Any]) -> None:
    transport.atomic_write_json(path, run)


def _verify_media(
    row: dict[str, Any],
    run: dict[str, Any],
    operations: ProviderOperations,
) -> pools.WorkerResult:
    try:
        media = operations.media_probe(row["paths"]["video"])
        check = transport.assess_contract(
            row["entry"].model_id,
            media,
            row["prompt"]["target_duration_seconds"],
        )
    except Exception as exc:
        error = transport.safe_error(exc)
        run.update(
            {
                "status": "verification-failed",
                "completed_at": transport.utc_now(),
                "provider_may_be_active": False,
                "error": error,
            }
        )
        _persist(row["paths"]["run"], run)
        return _worker_result(row, failed=True, status="verification-failed", error=error)
    status = "succeeded" if check.get("conforms") is True else "verification-failed"
    warnings = check.get("warnings") or []
    error = None if status == "succeeded" else "Media contract warnings: " + "; ".join(warnings)
    run.update(
        {
            "status": status,
            "completed_at": transport.utc_now(),
            "provider_may_be_active": False,
            "media": media,
            "contract_check": check,
            "error": error,
        }
    )
    _persist(row["paths"]["run"], run)
    # A verification-failed MP4 is intentionally retained for human review.
    return _worker_result(row, failed=status != "succeeded", status=status, error=error)


def _provider_failure(
    row: dict[str, Any],
    run: dict[str, Any],
    exc: BaseException,
    *,
    phase: str,
) -> pools.WorkerResult:
    error = f"{phase}: {transport.safe_error(exc)}"
    if isinstance(exc, (transport.PreSubmitNetworkError, transport.PreSubmitRejectedError)):
        status, holds = "failed-pre-submit", False
    elif isinstance(exc, (transport.ProviderTerminalError, transport.SegmindProviderTaskFailedError)):
        status, holds = "provider-failed", False
    elif run.get("provider_job_id"):
        status, holds = "submitted", True
    else:
        status, holds = "submit-unknown", True
    run.update(
        {
            "status": status,
            "provider_may_be_active": holds,
            "completed_at": transport.utc_now() if status == "provider-failed" else None,
            "error": error,
        }
    )
    _persist(row["paths"]["run"], run)
    return _worker_result(
        row,
        failed=True,
        status=status,
        error=error,
        holds_provider_slot=holds,
    )


def run_provider_worker(
    original: dict[str, Any],
    args: argparse.Namespace,
    *,
    output_root: Path = ROOT,
    operations: ProviderOperations | None = None,
) -> pools.WorkerResult:
    operations = operations or default_provider_operations()
    row = materialize_entry(original["entry"], output_root=output_root)
    entry: Entry = row["entry"]
    paths = row["paths"]
    run = read_json(paths["run"])
    request = transport.build_request_preview(row["sample"], row["prompt"])
    fingerprint = transport.request_fingerprint(request, row["sample"])
    status = str(run.get("status"))
    if status in {"succeeded", "verification-failed"}:
        if (
            run.get("request") != request
            or run.get("request_sha256") != fingerprint
            or run.get("request_fingerprint_version")
            != transport.REQUEST_FINGERPRINT_VERSION
        ):
            error = "Terminal provider receipt lost immutable request binding"
            run.update(
                {
                    "status": "stale",
                    "provider_may_be_active": False,
                    "error": error,
                }
            )
            _persist(paths["run"], run)
            return _worker_result(row, failed=True, status="stale", error=error)
        if not paths["video"].is_file():
            error = "Terminal provider receipt references a missing MP4"
            run.update(
                {
                    "status": "stale",
                    "provider_may_be_active": False,
                    "error": error,
                }
            )
            _persist(paths["run"], run)
            return _worker_result(row, failed=True, status="stale", error=error)
        if status == "succeeded":
            return _worker_result(row, failed=False, status="succeeded")
    if status in BLOCKED_PAID_STATUSES:
        holds = status in {"submitting", "submit-unknown"} or run.get("provider_may_be_active") is True
        return _worker_result(
            row,
            failed=True,
            status=status,
            error=f"Run status {status!r} blocks automatic paid retry and fallback",
            holds_provider_slot=holds,
        )
    resume = status in {"submitted", "running"}
    if resume and (
        not run.get("provider_job_id")
        or run.get("request") != request
        or run.get("request_sha256") != fingerprint
    ):
        run.update({"status": "stale", "error": "Active provider job lost immutable request binding"})
        _persist(paths["run"], run)
        return _worker_result(row, failed=True, status="stale", error=run["error"])
    dimension_preflight: dict[str, Any] | None = None
    if not resume:
        try:
            dimension_preflight = pools.provider_input_dimension_preflight(
                row["sample"],
                entry.model_id,
            )
        except pools.ProviderInputDimensionError as exc:
            error = transport.safe_error(exc)
            run.update(
                {
                    "status": "failed-pre-submit",
                    "request": request,
                    "request_sha256": fingerprint,
                    "request_fingerprint_version": (
                        transport.REQUEST_FINGERPRINT_VERSION
                    ),
                    "provider_job_id": None,
                    "submitted_at": None,
                    "completed_at": None,
                    "provider_may_be_active": False,
                    "source_preflight": exc.evidence,
                    "error": error,
                }
            )
            _persist(paths["run"], run)
            return _worker_result(
                row,
                failed=True,
                status="failed-pre-submit",
                error=error,
                holds_provider_slot=False,
            )
    if args.dry_run:
        if not resume:
            run.update(
                {
                    "status": "dry-run",
                    "request": request,
                    "request_sha256": fingerprint,
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                    "provider_may_be_active": False,
                    "source_preflight": dimension_preflight,
                    "error": None,
                }
            )
            _persist(paths["run"], run)
        return _worker_result(row, failed=False, status="dry-run")
    if not resume:
        run.update(
            {
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "source_preflight": dimension_preflight,
                "error": None,
            }
        )
        _persist(paths["run"], run)
    adapter = transport.route_for_model(entry.model_id)["adapter"]
    if adapter == "eliza-segmind":
        if resume:
            return _worker_result(
                row,
                failed=True,
                status=status,
                error="Synchronous Segmind cannot resume or resubmit",
            )

        def on_submitting(preflight: dict[str, Any]) -> None:
            run.update(
                {
                    "status": "submitting",
                    "source_preflight": preflight,
                    "provider_may_be_active": True,
                }
            )
            _persist(paths["run"], run)

        try:
            run.update({"status": "preparing", "provider_may_be_active": False})
            _persist(paths["run"], run)
            response = operations.segmind_generate(
                row["sample"],
                row["prompt"],
                paths["video"],
                args.segmind_base_url,
                args.timeout,
                on_submitting,
            )
            request_id = response.get("request_id") if isinstance(response, dict) else None
            if not isinstance(request_id, str) or not request_id:
                raise transport.PipelineError("Segmind response has no request ID")
        except Exception as exc:
            return _provider_failure(row, run, exc, phase="provider submit")
        run.update(
            {
                "status": "running",
                "provider_job_id": request_id,
                "provider_response": response,
                "provider_may_be_active": False,
                "submitted_at": transport.utc_now(),
            }
        )
        _persist(paths["run"], run)
        return _verify_media(row, run, operations)
    if adapter != "eliza-openrouter":
        return _worker_result(row, failed=True, status="failed-pre-submit", error=f"Unsupported adapter: {adapter}")
    try:
        headers = operations.eliza_headers()
    except Exception as exc:
        return _provider_failure(row, run, exc, phase="credential resolution")
    job_id = run.get("provider_job_id") if resume else None
    if not resume:
        run.update({"status": "submitting", "provider_may_be_active": True})
        _persist(paths["run"], run)
        try:
            response = operations.http_json(
                "POST",
                transport.generation_route_url(args.eliza_base_url, entry.model_id, "submit"),
                request,
                headers=headers,
                timeout=120,
            )
            job_id = transport.find_job_id(response)
            if not job_id:
                raise transport.PipelineError("OpenRouter submit response has no job ID")
        except Exception as exc:
            return _provider_failure(row, run, exc, phase="provider submit")
        run.update(
            {
                "status": "submitted",
                "provider_job_id": str(job_id),
                "submitted_at": transport.utc_now(),
                "provider_may_be_active": True,
            }
        )
        _persist(paths["run"], run)
    try:
        operations.eliza_poll(
            args.eliza_base_url,
            str(job_id),
            headers,
            args.timeout,
            args.poll_interval,
            model_id=entry.model_id,
        )
        operations.http_download(
            transport.generation_route_url(
                args.eliza_base_url,
                entry.model_id,
                "content_template",
                job_id=str(job_id),
            ),
            paths["video"],
            headers=headers,
            timeout=600,
        )
    except Exception as exc:
        return _provider_failure(row, run, exc, phase="provider poll/download")
    return _verify_media(row, run, operations)


def generation_manifest_document(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    *,
    output_root: Path = ROOT,
) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    for row in rows:
        entry: Entry = row["entry"]
        paths = row["paths"]
        run = read_json(paths["run"])
        status = str(run.get("status", "missing"))
        summary[status] = summary.get(status, 0) + 1
        outputs.append(
            {
                "provider_run_id": entry.provider_run_id,
                "case_id": entry.case_id,
                "sheet_row": entry.sheet_row,
                "article_slug": entry.article_slug,
                "image_id": entry.image_id,
                "model_id": entry.model_id,
                "execution_mode": "i2v",
                "status": status,
                "prompt_path": relative(paths["prompt"], output_root),
                "run_path": relative(paths["run"], output_root),
                "video_path": relative(paths["video"], output_root),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
                "fallback": None,
            }
        )
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-video-generation",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": transport.utc_now(),
        "scope": {
            "planning_batch_id": PLANNING_BATCH_ID,
            "prompt_manifest_path": PROMPT_MANIFEST_REL.as_posix(),
            "prompt_manifest_sha256": inventory.prompt_manifest_sha256,
            "contract_sha256": inventory.contract_sha256,
            "generation_routes_sha256": inventory.route_registry_sha256,
            "expected_i2v_outputs": EXPECTED_TARGETS,
            "compositor_outputs": 0,
            "fallback_outputs": 0,
            "s3_upload": False,
            "delivery": "repository-files",
        },
        "budget": inventory.budget,
        "scheduling": {
            "independent_route_pools": True,
            "route_capacities": EXPECTED_ROUTE_CAPACITIES,
            "one_paid_submission_per_provider_run_id": True,
            "automatic_paid_retry": False,
            "fallback": False,
        },
        "summary": dict(sorted(summary.items())),
        "outputs": outputs,
    }


def write_generation_manifest(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    *,
    output_root: Path = ROOT,
) -> dict[str, Any]:
    document = generation_manifest_document(inventory, rows, output_root=output_root)
    transport.atomic_write_json(output_root / GENERATION_MANIFEST_REL, document)
    return document


def run_batch(
    budget_cap_usd: str | Decimal,
    *,
    dry_run: bool,
    allow_external_processing: bool = False,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    fail_fast: bool = False,
    root: Path = ROOT,
    output_root: Path | None = None,
    operations: ProviderOperations | None = None,
) -> int:
    if not dry_run and not allow_external_processing:
        raise TuneV5VideoError("Real generation requires --allow-external-processing")
    output_root = (output_root or root).resolve()
    inventory = load_inventory(budget_cap_usd, root=root)
    rows = [materialize_entry(entry, output_root=output_root) for entry in inventory.entries]
    write_generation_manifest(inventory, rows, output_root=output_root)
    args = argparse.Namespace(
        dry_run=dry_run,
        timeout=timeout,
        poll_interval=poll_interval,
        fail_fast=fail_fast,
        segmind_base_url=transport.route_for_model("alibaba/wan-2.2")["default_base_url"],
        eliza_base_url=transport.route_for_model("alibaba/wan-2.7")["default_base_url"],
    )
    operations = operations or default_provider_operations()

    def worker(row: dict[str, Any]) -> pools.WorkerResult:
        return run_provider_worker(row, args, output_root=output_root, operations=operations)

    def on_complete(result: pools.WorkerResult) -> None:
        for index, row in enumerate(rows):
            if row["entry"].provider_run_id == result.row["entry"].provider_run_id:
                rows[index] = result.row
                break
        write_generation_manifest(inventory, rows, output_root=output_root)

    limits = pools.ProviderPoolLimits()
    actual_limits = {model_id: limits.for_model(model_id) for model_id in MODEL_IDS}
    if actual_limits != EXPECTED_ROUTE_CAPACITIES:
        raise TuneV5VideoError("Shared provider pool capacities changed")
    return pools.run_provider_pools(
        rows,
        limits,
        worker,
        on_complete,
        fail_fast=fail_fast,
    )


def verify(
    budget_cap_usd: str | Decimal,
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
    allow_incomplete: bool = False,
) -> tuple[bool, list[str]]:
    output_root = (output_root or root).resolve()
    inventory = load_inventory(budget_cap_usd, root=root)
    errors: list[str] = []
    for entry in inventory.entries:
        paths = artifact_paths(entry, output_root)
        if not paths["prompt"].is_file() or not paths["run"].is_file():
            if not allow_incomplete:
                errors.append(f"{entry.provider_run_id}: missing provider artifacts")
            continue
        if read_json(paths["prompt"]) != prompt_artifact(entry):
            errors.append(f"{entry.provider_run_id}: prompt binding changed")
            continue
        run = read_json(paths["run"])
        status = run.get("status")
        if status in {"succeeded", "verification-failed", "provider-failed"}:
            expected_request = transport.build_request_preview(
                provider_sample(entry),
                provider_prompt(entry),
            )
            expected_fingerprint = transport.request_fingerprint(
                expected_request,
                provider_sample(entry),
            )
            if (
                run.get("request") != expected_request
                or run.get("request_sha256") != expected_fingerprint
                or run.get("request_fingerprint_version")
                != transport.REQUEST_FINGERPRINT_VERSION
            ):
                errors.append(f"{entry.provider_run_id}: immutable request binding changed")
                continue
        if status in {"succeeded", "verification-failed"}:
            if not paths["video"].is_file():
                errors.append(f"{entry.provider_run_id}: MP4 missing")
                continue
            media = transport.ffprobe_media(paths["video"])
            if media != run.get("media"):
                errors.append(f"{entry.provider_run_id}: media receipt changed")
        elif status == "provider-failed":
            if paths["video"].exists() or run.get("fallback") is not None:
                errors.append(f"{entry.provider_run_id}: provider failure has forbidden fallback/media")
        elif not allow_incomplete:
            errors.append(f"{entry.provider_run_id}: status={status}")
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--timeout", type=int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--fail-fast", action="store_true")
    check = subparsers.add_parser("verify")
    check.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    check.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            failures = run_batch(args.budget_cap_usd, dry_run=True, root=root)
            return 1 if failures else 0
        if args.command == "generate":
            failures = run_batch(
                args.budget_cap_usd,
                dry_run=False,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                fail_fast=args.fail_fast,
                root=root,
            )
            return 1 if failures else 0
        ok, errors = verify(
            args.budget_cap_usd,
            root=root,
            allow_incomplete=args.allow_incomplete,
        )
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 0 if ok else 1
    except TuneV5VideoError as exc:
        print(f"Tune v5 video error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
