#!/usr/bin/env python3
"""Generate the immutable eight-output Tune v6 I2V retry batch.

This is an operator-authorized *new* batch, never an automatic retry of v5.
It binds two new provenance-verified neutral Veo prompts, reuses the exact
verified r4 Wan prompt text bytes, and uses commit-pinned uniform-scale inputs
only for the two Wan 2.7 minimum-dimension failures.  Every new provider run ID
permits at most one submit, with no compositor, fallback, S3 upload, or paid
retry.  Subsets reserve exactly $0.35 per selected target so the two four-item
route groups can be run separately under hard $1.40 caps; the union is capped
at $2.80.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as pools  # noqa: E402
from scripts import clipmaker_lite_tune_v5_pipeline as v5_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v5_retry_planning as retry_planning  # noqa: E402
from scripts import clipmaker_lite_tune_v5_video_pipeline as v5_generation  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
BATCH_ID = "promopages-10060-tune-videos-20260811-v6"
SOURCE_VIDEO_BATCH_ID = v5_generation.BATCH_ID
SOURCE_PROMPT_BATCH_ID = v5_planning.REPAIR_BATCH_ID
VEO_PROMPT_BATCH_ID = retry_planning.BATCH_ID
SOURCE_PROMPT_MANIFEST_REL = v5_generation.PROMPT_MANIFEST_REL
SOURCE_GENERATION_MANIFEST_REL = v5_generation.GENERATION_MANIFEST_REL
VEO_PROMPT_MANIFEST_REL = retry_planning.PROMPT_MANIFEST_REL
CONTRACT_REL = v5_generation.CONTRACT_REL
ROUTES_REL = v5_generation.ROUTES_REL
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"

MODEL_IDS = v5_generation.MODEL_IDS
MODEL_SUFFIXES = v5_generation.MODEL_SUFFIXES
MODEL_DIRECTORIES = v5_generation.MODEL_DIRECTORIES
EXPECTED_ROUTE_CAPACITIES = v5_generation.EXPECTED_ROUTE_CAPACITIES
ACCOUNTING_COST_PER_OUTPUT_USD = Decimal("0.35")
EXPECTED_TARGETS = 8
REQUIRED_AGGREGATE_BUDGET_CAP_USD = Decimal("2.80")
EXPECTED_BY_MODEL = {
    "alibaba/wan-2.2": 4,
    "alibaba/wan-2.7": 2,
    "google/veo-3.1-lite": 2,
}


def _key(case_id: str, model_id: str) -> str:
    return f"{case_id}::{model_id}"


EXPECTED_KEYS = frozenset(
    {
        _key("07#06", "google/veo-3.1-lite"),
        _key("10#07", "google/veo-3.1-lite"),
        _key("17#11", "alibaba/wan-2.2"),
        _key("18#05", "alibaba/wan-2.2"),
        _key("18#05", "alibaba/wan-2.7"),
        _key("18#06", "alibaba/wan-2.2"),
        _key("18#07", "alibaba/wan-2.2"),
        _key("18#07", "alibaba/wan-2.7"),
    }
)
EXPECTED_SOURCE_STATUSES = {
    _key("07#06", "google/veo-3.1-lite"): "provider-failed",
    _key("10#07", "google/veo-3.1-lite"): "provider-failed",
    _key("17#11", "alibaba/wan-2.2"): "submit-unknown",
    _key("18#05", "alibaba/wan-2.2"): "dry-run",
    _key("18#05", "alibaba/wan-2.7"): "provider-failed",
    _key("18#06", "alibaba/wan-2.2"): "dry-run",
    _key("18#07", "alibaba/wan-2.2"): "dry-run",
    _key("18#07", "alibaba/wan-2.7"): "provider-failed",
}
RETRY_REASONS = {
    _key("07#06", "google/veo-3.1-lite"): "terminal-provider-no-output-new-lite-prompt",
    _key("10#07", "google/veo-3.1-lite"): "terminal-provider-no-output-new-lite-prompt",
    _key("17#11", "alibaba/wan-2.2"): "prior-submit-unknown-operator-authorized-new-run",
    _key("18#05", "alibaba/wan-2.2"): "prior-dry-run-never-submitted-new-run",
    _key("18#05", "alibaba/wan-2.7"): "provider-minimum-dimension-rejection-normalized-source",
    _key("18#06", "alibaba/wan-2.2"): "prior-dry-run-never-submitted-new-run",
    _key("18#07", "alibaba/wan-2.2"): "prior-dry-run-never-submitted-new-run",
    _key("18#07", "alibaba/wan-2.7"): "provider-minimum-dimension-rejection-normalized-source",
}
SUBMIT_UNKNOWN_KEY = _key("17#11", "alibaba/wan-2.2")
ROUTE_SAFETY_WITHHELD_STATUSES = {
    SUBMIT_UNKNOWN_KEY: "pending",
    _key("18#05", "alibaba/wan-2.2"): "dry-run",
    _key("18#06", "alibaba/wan-2.2"): "dry-run",
    _key("18#07", "alibaba/wan-2.2"): "dry-run",
}
ROUTE_SAFETY_REASON = (
    "Wan 2.2 route capacity is 1 and the source 17#11 submit-unknown receipt "
    "still has provider_may_be_active=true; no new Wan 2.2 submit is allowed."
)
MAXIMUM_POSSIBLE_DUPLICATE_CHARGE_USD = Decimal("0.35")

NORMALIZED_ASSETS = {
    "18#05": {
        "audit_path": (
            "clipmaker-lite-test/runs/promopages-10060-campaigns-20260805-v1/"
            "normalized-input-assets-v1/660c32c4d1331cb3a82d/asset.json"
        ),
        "audit_sha256": "9c15789fad15c0418ec4eef4d223e66177621d7f274b3b4122066440c1cbcedc",
        "original_sha256": "95a38e9469f6055c7eab934ab7173af57d5445112e835e200a83964f74938543",
        "path": (
            "clipmaker-lite-test/runs/promopages-10060-campaigns-20260805-v1/"
            "normalized-input-assets-v1/660c32c4d1331cb3a82d/normalized.png"
        ),
        "url": (
            "https://raw.githubusercontent.com/UnidentifiedRaccoon/alice-live-images-test/"
            "25995ee6ea168d2ae7025e5a416bc008ae17a908/clipmaker-lite-test/runs/"
            "promopages-10060-campaigns-20260805-v1/normalized-input-assets-v1/"
            "660c32c4d1331cb3a82d/normalized.png"
        ),
        "sha256": "4ad98c730c783a63bce382ecffe640d51c936b3ccaec019b637861f8ddbf5b23",
        "bytes": 46883,
        "width": 882,
        "height": 256,
        "source_commit_sha": "25995ee6ea168d2ae7025e5a416bc008ae17a908",
    },
    "18#07": {
        "audit_path": (
            "clipmaker-lite-test/runs/promopages-10060-campaigns-20260805-v1/"
            "normalized-input-assets-v1/0535f187b92384618210/asset.json"
        ),
        "audit_sha256": "f748a9609ab2610bfacce0c521d8542fca195a143f9ae9cea462025d105dc080",
        "original_sha256": "07fd4373396697d3078265a72337a759d591449deb6cafe9869e9d2f92fb43e8",
        "path": (
            "clipmaker-lite-test/runs/promopages-10060-campaigns-20260805-v1/"
            "normalized-input-assets-v1/0535f187b92384618210/normalized.png"
        ),
        "url": (
            "https://raw.githubusercontent.com/UnidentifiedRaccoon/alice-live-images-test/"
            "25995ee6ea168d2ae7025e5a416bc008ae17a908/clipmaker-lite-test/runs/"
            "promopages-10060-campaigns-20260805-v1/normalized-input-assets-v1/"
            "0535f187b92384618210/normalized.png"
        ),
        "sha256": "7f71227971a99ca0f204eccadb89a706128eabfb6022657bf8718e952fca70e4",
        "bytes": 57771,
        "width": 828,
        "height": 256,
        "source_commit_sha": "25995ee6ea168d2ae7025e5a416bc008ae17a908",
    },
}

BLOCKED_STATUSES = {
    "submitting",
    "submit-unknown",
    "provider-failed",
    "failed-pre-submit",
    "verification-failed",
    "stale",
    "failed",
}


class TuneV5RetryVideoError(RuntimeError):
    """The retry provider batch failed an immutable or paid-safety guard."""


@dataclass(frozen=True)
class Entry:
    case_id: str
    sheet_row: int
    article_slug: str
    image_id: str
    model_id: str
    canonical_source_path: str
    canonical_source_url: str
    canonical_source_sha256: str
    canonical_width: int
    canonical_height: int
    provider_source_path: str
    provider_source_url: str
    provider_source_sha256: str
    provider_width: int
    provider_height: int
    normalized_source: dict[str, Any] | None
    planning_batch_id: str
    planning_run_id: str
    result_path: str
    result_sha256: str
    prompt_manifest_path: str
    prompt_manifest_sha256: str
    prompt_lineage_kind: str
    prompt_text_sha256: str
    scene_plan_sha256: str
    repair_feedback_path: str
    repair_feedback_sha256: str
    scene_plan: str
    positive_prompt: str
    runtime: dict[str, Any]
    provenance: dict[str, Any]
    prior_attempt: dict[str, Any]
    retry_reason: str

    @property
    def provider_run_id(self) -> str:
        return (
            f"{BATCH_ID}-{self.article_slug}-{self.image_id}-"
            f"{MODEL_SUFFIXES[self.model_id]}"
        )

    @property
    def evaluation_id(self) -> str:
        return _key(self.case_id, self.model_id)


@dataclass(frozen=True)
class Inventory:
    entries: tuple[Entry, ...]
    source_prompt_manifest_sha256: str
    veo_prompt_manifest_sha256: str
    source_generation_manifest_sha256: str
    contract_sha256: str
    route_registry_sha256: str


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
        raise TuneV5RetryVideoError(f"Required JSON is missing: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TuneV5RetryVideoError(f"Invalid JSON: {path}") from exc


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError as exc:
        raise TuneV5RetryVideoError(f"Required file is missing: {path}") from exc


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneV5RetryVideoError(f"Artifact is outside workspace: {path}") from exc


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise TuneV5RetryVideoError("--budget-cap-usd must be decimal") from exc
    if parsed <= 0 or parsed > REQUIRED_AGGREGATE_BUDGET_CAP_USD:
        raise TuneV5RetryVideoError("Subset budget must be positive and no greater than 2.80")
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except TuneV5RetryVideoError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def validate_subset_budget(value: str | Decimal, selected_count: int) -> dict[str, Any]:
    parsed = parse_budget(value)
    required = ACCOUNTING_COST_PER_OUTPUT_USD * selected_count
    if parsed != required:
        raise TuneV5RetryVideoError(
            f"Selected {selected_count} targets require exact --budget-cap-usd {required:.2f}"
        )
    return {
        "currency": "USD",
        "operator_subset_budget_cap_usd": float(parsed),
        "selected_output_count": selected_count,
        "accounting_cost_per_output_usd": float(ACCOUNTING_COST_PER_OUTPUT_USD),
        "maximum_estimated_cost_usd": float(required),
        "provider_unit_costs_asserted": False,
        "one_submit_per_new_provider_run_id": True,
        "automatic_paid_retry": False,
    }


def aggregate_budget_document() -> dict[str, Any]:
    return {
        "currency": "USD",
        "hard_incremental_budget_cap_usd": 2.8,
        "reserved_output_count": EXPECTED_TARGETS,
        "accounting_cost_per_output_usd": 0.35,
        "maximum_estimated_cost_usd": 2.8,
        "provider_unit_costs_asserted": False,
        "basis": "eight new immutable provider run IDs; one submit each",
        "automatic_paid_retry": False,
    }


def _validate_png(path: Path, *, width: int, height: int, byte_size: int, digest: str) -> None:
    payload = path.read_bytes()
    if len(payload) != byte_size or hashlib.sha256(payload).hexdigest() != digest:
        raise TuneV5RetryVideoError(f"Normalized source bytes changed: {path}")
    if len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise TuneV5RetryVideoError(f"Normalized source is not PNG: {path}")
    actual_width, actual_height = struct.unpack(">II", payload[16:24])
    if (actual_width, actual_height) != (width, height):
        raise TuneV5RetryVideoError(f"Normalized source dimensions changed: {path}")


def _normalized_source(case_id: str, source: dict[str, Any], root: Path) -> dict[str, Any]:
    expected = copy.deepcopy(NORMALIZED_ASSETS[case_id])
    audit_path = root / expected["audit_path"]
    asset_path = root / expected["path"]
    audit = read_json(audit_path)
    if sha256_file(audit_path) != expected["audit_sha256"]:
        raise TuneV5RetryVideoError(f"Normalized audit digest changed: {case_id}")
    if (
        source.get("sha256") != expected["original_sha256"]
        or audit.get("manifest_role")
        != "promopages-10060-campaign-extension-normalized-input-asset"
        or audit.get("strategy") != "deterministic-uniform-upscale"
        or audit.get("original", {}).get("path") != source.get("path")
        or audit.get("original", {}).get("sha256") != source.get("sha256")
        or audit.get("normalized", {}).get("repository_path") != expected["path"]
        or audit.get("normalized", {}).get("url") != expected["url"]
        or audit.get("normalized", {}).get("sha256") != expected["sha256"]
        or audit.get("normalized", {}).get("bytes") != expected["bytes"]
        or audit.get("normalized", {}).get("width") != expected["width"]
        or audit.get("normalized", {}).get("height") != expected["height"]
        or audit.get("normalized", {}).get("source_commit_sha")
        != expected["source_commit_sha"]
        or audit.get("transform")
        != {
            "operation": "uniform-scale",
            "target_height": 256,
            "resampler": "lanczos",
            "crop": False,
            "local_reencode": True,
        }
        or audit.get("minimum_provider_input_dimension") != 240
    ):
        raise TuneV5RetryVideoError(f"Normalized source audit changed: {case_id}")
    _validate_png(
        asset_path,
        width=expected["width"],
        height=expected["height"],
        byte_size=expected["bytes"],
        digest=expected["sha256"],
    )
    return {
        "strategy": "uniform-scale-source",
        "audit_path": expected["audit_path"],
        "audit_sha256": expected["audit_sha256"],
        "source_commit_sha": expected["source_commit_sha"],
        "transform": copy.deepcopy(audit["transform"]),
        "original": copy.deepcopy(audit["original"]),
        "normalized": copy.deepcopy(audit["normalized"]),
    }


def _source_outputs(document: Any) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-video-generation"
        or document.get("batch_id") != SOURCE_VIDEO_BATCH_ID
        or not isinstance(document.get("outputs"), list)
        or len(document["outputs"]) != 28
    ):
        raise TuneV5RetryVideoError("Unexpected source v5 generation manifest")
    by_key: dict[str, dict[str, Any]] = {}
    for output in document["outputs"]:
        if not isinstance(output, dict):
            raise TuneV5RetryVideoError("Source v5 output is not an object")
        key = _key(str(output.get("case_id")), str(output.get("model_id")))
        if key in by_key:
            raise TuneV5RetryVideoError(f"Duplicate source output: {key}")
        by_key[key] = output
    for key, status in EXPECTED_SOURCE_STATUSES.items():
        output = by_key.get(key)
        if not isinstance(output, dict) or output.get("status") != status:
            raise TuneV5RetryVideoError(f"Source output status changed: {key}")
    return by_key


def _prior_attempt(root: Path, output: dict[str, Any], expected_status: str) -> dict[str, Any]:
    run_path = str(output["run_path"])
    prompt_path = str(output["prompt_path"])
    run = read_json(root / run_path)
    if (
        run.get("status") != expected_status
        or run.get("provider_run_id") != output.get("provider_run_id")
        or run.get("automatic_paid_retry") is not False
        or run.get("fallback") is not None
        or (expected_status != "submit-unknown" and run.get("provider_may_be_active") is not False)
        or (expected_status == "submit-unknown" and run.get("provider_may_be_active") is not True)
    ):
        raise TuneV5RetryVideoError(
            f"Source provider receipt changed: {output.get('provider_run_id')}"
        )
    return {
        "batch_id": SOURCE_VIDEO_BATCH_ID,
        "provider_run_id": output["provider_run_id"],
        "status": expected_status,
        "prompt_path": prompt_path,
        "prompt_sha256": sha256_file(root / prompt_path),
        "run_path": run_path,
        "run_sha256": sha256_file(root / run_path),
        "provider_job_id": run.get("provider_job_id"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "error": run.get("error"),
        "automatic_paid_retry": False,
        "fallback": None,
        "receipts_mutated": False,
    }


def _entry_from_v5(
    source_entry: v5_generation.Entry,
    *,
    root: Path,
    source_output: dict[str, Any],
) -> Entry:
    key = _key(source_entry.case_id, source_entry.model_id)
    normalized = None
    provider_path = source_entry.source_path
    provider_url = source_entry.source_url
    provider_sha = source_entry.source_sha256
    provider_width = source_entry.width
    provider_height = source_entry.height
    if source_entry.model_id == "alibaba/wan-2.7":
        normalized = _normalized_source(source_entry.case_id, {
            "path": source_entry.source_path,
            "url": source_entry.source_url,
            "sha256": source_entry.source_sha256,
            "width": source_entry.width,
            "height": source_entry.height,
        }, root)
        provider = normalized["normalized"]
        provider_path = provider["repository_path"]
        provider_url = provider["url"]
        provider_sha = provider["sha256"]
        provider_width = provider["width"]
        provider_height = provider["height"]
    return Entry(
        case_id=source_entry.case_id,
        sheet_row=source_entry.sheet_row,
        article_slug=source_entry.article_slug,
        image_id=source_entry.image_id,
        model_id=source_entry.model_id,
        canonical_source_path=source_entry.source_path,
        canonical_source_url=source_entry.source_url,
        canonical_source_sha256=source_entry.source_sha256,
        canonical_width=source_entry.width,
        canonical_height=source_entry.height,
        provider_source_path=provider_path,
        provider_source_url=provider_url,
        provider_source_sha256=provider_sha,
        provider_width=provider_width,
        provider_height=provider_height,
        normalized_source=normalized,
        planning_batch_id=SOURCE_PROMPT_BATCH_ID,
        planning_run_id=source_entry.planning_run_id,
        result_path=source_entry.result_path,
        result_sha256=source_entry.result_sha256,
        prompt_manifest_path=SOURCE_PROMPT_MANIFEST_REL.as_posix(),
        prompt_manifest_sha256=source_entry.prompt_manifest_sha256,
        prompt_lineage_kind="exact-verified-r4-prompt-bytes",
        prompt_text_sha256=hashlib.sha256(source_entry.positive_prompt.encode("utf-8")).hexdigest(),
        scene_plan_sha256=hashlib.sha256(source_entry.scene_plan.encode("utf-8")).hexdigest(),
        repair_feedback_path=source_entry.repair_feedback_path,
        repair_feedback_sha256=source_entry.repair_feedback_sha256,
        scene_plan=source_entry.scene_plan,
        positive_prompt=source_entry.positive_prompt,
        runtime=copy.deepcopy(source_entry.runtime),
        provenance=copy.deepcopy(source_entry.provenance),
        prior_attempt=_prior_attempt(root, source_output, EXPECTED_SOURCE_STATUSES[key]),
        retry_reason=RETRY_REASONS[key],
    )


def _veo_entries(root: Path, source_outputs: dict[str, dict[str, Any]]) -> list[Entry]:
    retry_planning.load_selection(root=root)
    path = root / VEO_PROMPT_MANIFEST_REL
    document = read_json(path)
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-retry-planning"
        or document.get("batch_id") != VEO_PROMPT_BATCH_ID
        or document.get("contract_version") != retry_planning.EXPECTED_CONTRACT_VERSION
        or document.get("scope", {}).get("target_count") != 2
        or document.get("scope", {}).get("required_rendering_strategy") != "camera-only"
        or not isinstance(document.get("cases"), list)
        or len(document["cases"]) != 2
    ):
        raise TuneV5RetryVideoError("Unexpected Veo retry prompt manifest")
    manifest_sha = sha256_file(path)
    entries: list[Entry] = []
    for case in document["cases"]:
        targets = case.get("targets")
        planning = case.get("planning")
        source = case.get("source")
        if (
            not isinstance(targets, list)
            or len(targets) != 1
            or not isinstance(targets[0], dict)
            or targets[0].get("model_id") != "google/veo-3.1-lite"
            or not isinstance(planning, dict)
            or not isinstance(source, dict)
            or not retry_planning.result_is_verified(case, root=root)
        ):
            raise TuneV5RetryVideoError(f"Veo retry prompt binding changed: {case.get('case_id')}")
        result = retry_planning.read_json(root / planning["result_path"])
        model = retry_planning.validate_neutral_result(result, case)
        target = targets[0]
        tuned = target.get("tuned")
        if not isinstance(tuned, dict) or tuned.get("positive_prompt") != model["positive_prompt"]:
            raise TuneV5RetryVideoError(f"Veo retry prompt text changed: {case.get('case_id')}")
        key = _key(case["case_id"], "google/veo-3.1-lite")
        entries.append(
            Entry(
                case_id=case["case_id"],
                sheet_row=target["sheet_row"],
                article_slug=case["article_slug"],
                image_id=str(source["image_id"]),
                model_id="google/veo-3.1-lite",
                canonical_source_path=source["path"],
                canonical_source_url=source["url"],
                canonical_source_sha256=source["sha256"],
                canonical_width=int(source["width"]),
                canonical_height=int(source["height"]),
                provider_source_path=source["path"],
                provider_source_url=source["url"],
                provider_source_sha256=source["sha256"],
                provider_width=int(source["width"]),
                provider_height=int(source["height"]),
                normalized_source=None,
                planning_batch_id=VEO_PROMPT_BATCH_ID,
                planning_run_id=planning["run_id"],
                result_path=planning["result_path"],
                result_sha256=planning["result_sha256"],
                prompt_manifest_path=VEO_PROMPT_MANIFEST_REL.as_posix(),
                prompt_manifest_sha256=manifest_sha,
                prompt_lineage_kind="new-provenance-verified-lite-camera-only",
                prompt_text_sha256=hashlib.sha256(model["positive_prompt"].encode("utf-8")).hexdigest(),
                scene_plan_sha256=hashlib.sha256(model["scene_plan"].encode("utf-8")).hexdigest(),
                repair_feedback_path=planning["repair_feedback_path"],
                repair_feedback_sha256=planning["repair_feedback_sha256"],
                scene_plan=model["scene_plan"],
                positive_prompt=model["positive_prompt"],
                runtime=copy.deepcopy(model["runtime"]),
                provenance=copy.deepcopy(planning["provenance"]),
                prior_attempt=_prior_attempt(root, source_outputs[key], EXPECTED_SOURCE_STATUSES[key]),
                retry_reason=RETRY_REASONS[key],
            )
        )
    return entries


def load_inventory(*, root: Path = ROOT) -> Inventory:
    root = root.resolve()
    source_inventory = v5_generation.load_inventory("9.80", root=root)
    source_by_key = {
        _key(entry.case_id, entry.model_id): entry for entry in source_inventory.entries
    }
    source_generation_path = root / SOURCE_GENERATION_MANIFEST_REL
    source_outputs = _source_outputs(read_json(source_generation_path))
    entries = _veo_entries(root, source_outputs)
    for key in sorted(EXPECTED_KEYS):
        if key.endswith("::google/veo-3.1-lite"):
            continue
        source_entry = source_by_key.get(key)
        if source_entry is None:
            raise TuneV5RetryVideoError(f"Verified r4 source prompt missing: {key}")
        entries.append(
            _entry_from_v5(source_entry, root=root, source_output=source_outputs[key])
        )
    entries.sort(key=lambda entry: (entry.sheet_row, MODEL_IDS.index(entry.model_id)))
    keys = {entry.evaluation_id for entry in entries}
    counts = Counter(entry.model_id for entry in entries)
    run_ids = {entry.provider_run_id for entry in entries}
    if (
        len(entries) != EXPECTED_TARGETS
        or keys != EXPECTED_KEYS
        or dict(counts) != EXPECTED_BY_MODEL
        or len(run_ids) != EXPECTED_TARGETS
        or any(entry.provider_run_id.startswith(SOURCE_VIDEO_BATCH_ID) for entry in entries)
    ):
        raise TuneV5RetryVideoError("Retry target/run matrix changed")
    return Inventory(
        entries=tuple(entries),
        source_prompt_manifest_sha256=source_inventory.prompt_manifest_sha256,
        veo_prompt_manifest_sha256=sha256_file(root / VEO_PROMPT_MANIFEST_REL),
        source_generation_manifest_sha256=sha256_file(source_generation_path),
        contract_sha256=sha256_file(root / CONTRACT_REL),
        route_registry_sha256=sha256_file(root / ROUTES_REL),
    )


def provider_sample(entry: Entry) -> dict[str, Any]:
    return {
        "sample_id": f"{entry.article_slug}-{entry.image_id}",
        "article_slug": entry.article_slug,
        "image_id": entry.image_id,
        "image_number": entry.image_id,
        "source_path": entry.provider_source_path,
        "source_url": entry.provider_source_url,
        "sha256": entry.provider_source_sha256,
        "width": entry.provider_width,
        "height": entry.provider_height,
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
        "manifest_role": "clipmaker-lite-tune-v6-retry-video-prompt",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": entry.model_id,
        "execution_mode": "i2v",
        "retry_reason": entry.retry_reason,
        "canonical_source": {
            "path": entry.canonical_source_path,
            "url": entry.canonical_source_url,
            "sha256": entry.canonical_source_sha256,
            "width": entry.canonical_width,
            "height": entry.canonical_height,
        },
        "provider_source": {
            "path": entry.provider_source_path,
            "url": entry.provider_source_url,
            "sha256": entry.provider_source_sha256,
            "width": entry.provider_width,
            "height": entry.provider_height,
            "normalized_source": copy.deepcopy(entry.normalized_source),
        },
        "scene_plan": entry.scene_plan,
        "prompt": {
            "positive": entry.positive_prompt,
            "positive_utf8_sha256": entry.prompt_text_sha256,
            "scene_plan_utf8_sha256": entry.scene_plan_sha256,
            "negative": None,
            "rewritten_by_provider_coordinator": False,
        },
        "runtime": copy.deepcopy(entry.runtime),
        "planning": {
            "lineage_kind": entry.prompt_lineage_kind,
            "batch_id": entry.planning_batch_id,
            "run_id": entry.planning_run_id,
            "result_path": entry.result_path,
            "result_sha256": entry.result_sha256,
            "prompt_manifest_path": entry.prompt_manifest_path,
            "prompt_manifest_sha256": entry.prompt_manifest_sha256,
            "repair_feedback_path": entry.repair_feedback_path,
            "repair_feedback_sha256": entry.repair_feedback_sha256,
            "provenance": copy.deepcopy(entry.provenance),
        },
        "prior_attempt": copy.deepcopy(entry.prior_attempt),
        "policy": {
            "new_immutable_provider_run": True,
            "automatic_paid_retry": False,
            "fallback": None,
            "s3_upload": False,
        },
        "bindings": {
            "generation_routes_path": ROUTES_REL.as_posix(),
            "generation_routes_sha256": sha256_file(ROOT / ROUTES_REL),
        },
    }


def _initial_run(entry: Entry, paths: dict[str, Path], output_root: Path) -> dict[str, Any]:
    route = transport.route_for_model(entry.model_id)
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v6-retry-video-run",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": entry.model_id,
        "execution_mode": "i2v",
        "adapter": route["adapter"],
        "retry_reason": entry.retry_reason,
        "prior_attempt": copy.deepcopy(entry.prior_attempt),
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
        "submission_count": 0,
        "budget_reservation_usd": 0.35,
        "new_immutable_provider_run": True,
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
            raise TuneV5RetryVideoError(f"Immutable prompt changed: {paths['prompt']}")
    else:
        transport.atomic_write_json(paths["prompt"], expected_prompt)
    expected_run = _initial_run(entry, paths, output_root)
    immutable_keys = (
        "manifest_role",
        "ticket",
        "batch_id",
        "agent_id",
        "provider_run_id",
        "case_id",
        "sheet_row",
        "model_id",
        "execution_mode",
        "adapter",
        "retry_reason",
        "prior_attempt",
        "prompt_path",
        "output_path",
        "budget_reservation_usd",
        "new_immutable_provider_run",
        "automatic_paid_retry",
        "fallback",
        "s3_upload",
    )
    if paths["run"].exists():
        run = read_json(paths["run"])
        if any(run.get(key) != expected_run[key] for key in immutable_keys):
            raise TuneV5RetryVideoError(f"Immutable run identity changed: {paths['run']}")
        count = run.get("submission_count")
        if isinstance(count, bool) or count not in {0, 1}:
            raise TuneV5RetryVideoError(f"Invalid submission count: {paths['run']}")
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
    row: dict[str, Any], run: dict[str, Any], operations: ProviderOperations
) -> pools.WorkerResult:
    try:
        media = operations.media_probe(row["paths"]["video"])
        check = transport.assess_contract(
            row["entry"].model_id,
            media,
            row["prompt"]["target_duration_seconds"],
        )
    except Exception as exc:  # noqa: BLE001 - terminal verification receipt
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
    return _worker_result(row, failed=status != "succeeded", status=status, error=error)


def _provider_failure(
    row: dict[str, Any], run: dict[str, Any], exc: BaseException, *, phase: str
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
            "completed_at": transport.utc_now() if status in {"provider-failed", "failed-pre-submit"} else None,
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
    duplicate_risk_acceptance = original.get("duplicate_risk_acceptance")
    if duplicate_risk_acceptance is not None:
        if entry.model_id != "alibaba/wan-2.2":
            raise TuneV5RetryVideoError(
                "Duplicate-risk acceptance may bind only a Wan 2.2 run"
            )
        existing_acceptance = run.get("duplicate_risk_acceptance")
        if existing_acceptance is not None and existing_acceptance != duplicate_risk_acceptance:
            raise TuneV5RetryVideoError(
                f"Duplicate-risk acceptance changed: {entry.provider_run_id}"
            )
        if existing_acceptance is None:
            run["duplicate_risk_acceptance"] = copy.deepcopy(
                duplicate_risk_acceptance
            )
            _persist(paths["run"], run)
    request = transport.build_request_preview(row["sample"], row["prompt"])
    fingerprint = transport.request_fingerprint(request, row["sample"])
    status = str(run.get("status"))
    if status in {"succeeded", "verification-failed"}:
        if (
            run.get("request") != request
            or run.get("request_sha256") != fingerprint
            or run.get("request_fingerprint_version") != transport.REQUEST_FINGERPRINT_VERSION
            or run.get("submission_count") != 1
            or not paths["video"].is_file()
        ):
            error = "Terminal receipt lost immutable request/media binding"
            run.update({"status": "stale", "provider_may_be_active": False, "error": error})
            _persist(paths["run"], run)
            return _worker_result(row, failed=True, status="stale", error=error)
        if status == "succeeded":
            return _worker_result(row, failed=False, status="succeeded")
    if status in BLOCKED_STATUSES:
        holds = status in {"submitting", "submit-unknown"} or run.get("provider_may_be_active") is True
        return _worker_result(
            row,
            failed=True,
            status=status,
            error=f"Run status {status!r} blocks resubmit, paid retry, and fallback",
            holds_provider_slot=holds,
        )
    resume = status in {"submitted", "running"}
    if resume and (
        run.get("submission_count") != 1
        or not run.get("provider_job_id")
        or run.get("request") != request
        or run.get("request_sha256") != fingerprint
    ):
        run.update({"status": "stale", "error": "Active job lost immutable request binding"})
        _persist(paths["run"], run)
        return _worker_result(row, failed=True, status="stale", error=run["error"])
    if not resume and run.get("submission_count") != 0:
        error = "Provider run ID has already consumed its single submit allowance"
        run.update({"status": "stale", "error": error, "provider_may_be_active": False})
        _persist(paths["run"], run)
        return _worker_result(row, failed=True, status="stale", error=error)
    dimension_preflight: dict[str, Any] | None = None
    if not resume:
        try:
            dimension_preflight = pools.provider_input_dimension_preflight(
                row["sample"], entry.model_id
            )
        except pools.ProviderInputDimensionError as exc:
            error = transport.safe_error(exc)
            run.update(
                {
                    "status": "failed-pre-submit",
                    "request": request,
                    "request_sha256": fingerprint,
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                    "provider_may_be_active": False,
                    "source_preflight": exc.evidence,
                    "completed_at": transport.utc_now(),
                    "error": error,
                }
            )
            _persist(paths["run"], run)
            return _worker_result(row, failed=True, status="failed-pre-submit", error=error)
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
                row, failed=True, status=status, error="Synchronous Segmind cannot resume or resubmit"
            )

        def on_submitting(preflight: dict[str, Any]) -> None:
            if run.get("submission_count") != 0:
                raise TuneV5RetryVideoError("Segmind submit allowance already consumed")
            run.update(
                {
                    "status": "submitting",
                    "submission_count": 1,
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
        except Exception as exc:  # noqa: BLE001 - auditable provider receipt
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
        return _worker_result(
            row, failed=True, status="failed-pre-submit", error=f"Unsupported adapter: {adapter}"
        )
    try:
        headers = operations.eliza_headers()
    except Exception as exc:  # noqa: BLE001 - no paid submit occurred
        error = f"credential resolution: {transport.safe_error(exc)}"
        run.update(
            {
                "status": "failed-pre-submit",
                "provider_may_be_active": False,
                "completed_at": transport.utc_now(),
                "error": error,
            }
        )
        _persist(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status="failed-pre-submit",
            error=error,
        )
    job_id = run.get("provider_job_id") if resume else None
    if not resume:
        run.update(
            {
                "status": "submitting",
                "submission_count": 1,
                "provider_may_be_active": True,
            }
        )
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
        except Exception as exc:  # noqa: BLE001 - auditable provider receipt
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
    except Exception as exc:  # noqa: BLE001 - auditable provider receipt
        return _provider_failure(row, run, exc, phase="provider poll/download")
    return _verify_media(row, run, operations)


def select_entries(
    entries: tuple[Entry, ...],
    *,
    model_ids: list[str],
    exclude_models: list[str],
    targets: list[str],
) -> tuple[Entry, ...]:
    if model_ids and exclude_models:
        raise TuneV5RetryVideoError("--model-id and --exclude-model are mutually exclusive")
    unknown_targets = set(targets) - EXPECTED_KEYS
    if unknown_targets:
        raise TuneV5RetryVideoError("Unknown --target: " + ", ".join(sorted(unknown_targets)))
    selected = list(entries)
    if model_ids:
        selected = [entry for entry in selected if entry.model_id in set(model_ids)]
    if exclude_models:
        selected = [entry for entry in selected if entry.model_id not in set(exclude_models)]
    if targets:
        selected = [entry for entry in selected if entry.evaluation_id in set(targets)]
    if not selected:
        raise TuneV5RetryVideoError("Subset selection is empty")
    return tuple(selected)


def generation_manifest_document(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    *,
    invocation: dict[str, Any] | None,
    output_root: Path,
) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    summary: Counter[str] = Counter()
    for row in rows:
        entry: Entry = row["entry"]
        paths = row["paths"]
        run = read_json(paths["run"])
        status = str(run.get("status", "missing"))
        summary[status] += 1
        outputs.append(
            {
                "provider_run_id": entry.provider_run_id,
                "evaluation_id": entry.evaluation_id,
                "case_id": entry.case_id,
                "sheet_row": entry.sheet_row,
                "article_slug": entry.article_slug,
                "image_id": entry.image_id,
                "model_id": entry.model_id,
                "execution_mode": "i2v",
                "retry_reason": entry.retry_reason,
                "prior_attempt": copy.deepcopy(entry.prior_attempt),
                "prompt_lineage_kind": entry.prompt_lineage_kind,
                "status": status,
                "prompt_path": relative(paths["prompt"], output_root),
                "run_path": relative(paths["run"], output_root),
                "video_path": relative(paths["video"], output_root),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
                "submission_count": run.get("submission_count"),
                "duplicate_risk_acceptance": copy.deepcopy(
                    run.get("duplicate_risk_acceptance")
                ),
                "automatic_paid_retry": False,
                "fallback": None,
            }
        )
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v6-retry-video-generation",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": transport.utc_now(),
        "scope": {
            "expected_i2v_outputs": EXPECTED_TARGETS,
            "model_counts": EXPECTED_BY_MODEL,
            "new_veo_prompt_batch_id": VEO_PROMPT_BATCH_ID,
            "source_wan_prompt_batch_id": SOURCE_PROMPT_BATCH_ID,
            "source_video_batch_id": SOURCE_VIDEO_BATCH_ID,
            "source_prompt_manifest_sha256": inventory.source_prompt_manifest_sha256,
            "veo_prompt_manifest_sha256": inventory.veo_prompt_manifest_sha256,
            "source_generation_manifest_sha256": inventory.source_generation_manifest_sha256,
            "contract_sha256": inventory.contract_sha256,
            "generation_routes_sha256": inventory.route_registry_sha256,
            "normalized_wan_2_7_sources": 2,
            "compositor_outputs": 0,
            "fallback_outputs": 0,
            "s3_upload": False,
            "delivery": "repository-files",
        },
        "budget": aggregate_budget_document(),
        "scheduling": {
            "independent_route_pools": True,
            "route_capacities": EXPECTED_ROUTE_CAPACITIES,
            "subset_execution_supported": True,
            "one_paid_submission_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
            "fallback": False,
        },
        "last_invocation": copy.deepcopy(invocation),
        "summary": dict(sorted(summary.items())),
        "outputs": outputs,
    }


def write_generation_manifest(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    *,
    invocation: dict[str, Any] | None,
    output_root: Path,
) -> dict[str, Any]:
    document = generation_manifest_document(
        inventory, rows, invocation=invocation, output_root=output_root
    )
    transport.atomic_write_json(output_root / GENERATION_MANIFEST_REL, document)
    return document


def run_batch(
    budget_cap_usd: str | Decimal,
    *,
    dry_run: bool,
    model_ids: list[str] | None = None,
    exclude_models: list[str] | None = None,
    targets: list[str] | None = None,
    allow_external_processing: bool = False,
    acknowledge_prior_submit_unknown_inactive: bool = False,
    authorize_wan22_despite_unresolved_submit_unknown: bool = False,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    fail_fast: bool = False,
    root: Path = ROOT,
    output_root: Path | None = None,
    operations: ProviderOperations | None = None,
) -> int:
    if not dry_run and not allow_external_processing:
        raise TuneV5RetryVideoError("Real generation requires --allow-external-processing")
    output_root = (output_root or root).resolve()
    inventory = load_inventory(root=root)
    selected = select_entries(
        inventory.entries,
        model_ids=model_ids or [],
        exclude_models=exclude_models or [],
        targets=targets or [],
    )
    subset_budget = validate_subset_budget(budget_cap_usd, len(selected))
    selected_keys = [entry.evaluation_id for entry in selected]
    selects_wan_22 = any(entry.model_id == "alibaba/wan-2.2" for entry in selected)
    if (
        acknowledge_prior_submit_unknown_inactive
        and authorize_wan22_despite_unresolved_submit_unknown
    ):
        raise TuneV5RetryVideoError(
            "Choose either confirmed inactivity or explicit duplicate-risk acceptance, not both"
        )
    if (
        not dry_run
        and selects_wan_22
        and not acknowledge_prior_submit_unknown_inactive
        and not authorize_wan22_despite_unresolved_submit_unknown
    ):
        raise TuneV5RetryVideoError(
            "The Wan 2.2 route has capacity 1 and the prior 17#11 submit-unknown receipt "
            "still holds that route slot. No Wan 2.2 target may submit until out-of-band "
            "evidence confirms the prior request is inactive; only then pass "
            "--acknowledge-prior-submit-unknown-inactive. If an operator instead accepts "
            "the bounded duplicate-charge risk without claiming inactivity, pass "
            "--authorize-wan22-despite-unresolved-submit-unknown."
        )
    rows = [materialize_entry(entry, output_root=output_root) for entry in inventory.entries]
    selected_ids = {entry.provider_run_id for entry in selected}
    selected_rows = [row for row in rows if row["entry"].provider_run_id in selected_ids]
    duplicate_risk_receipt: dict[str, Any] | None = None
    if selects_wan_22 and authorize_wan22_despite_unresolved_submit_unknown:
        barrier_entry = next(
            entry for entry in inventory.entries if entry.evaluation_id == SUBMIT_UNKNOWN_KEY
        )
        barrier = barrier_entry.prior_attempt
        if (
            barrier.get("status") != "submit-unknown"
            or barrier.get("provider_job_id") is not None
            or barrier.get("provider_may_be_active") is not True
            or barrier.get("run_sha256") != sha256_file(root / barrier["run_path"])
        ):
            raise TuneV5RetryVideoError(
                "The duplicate-risk authorization source receipt changed"
            )
        duplicate_risk_receipt = {
            "authorization_kind": "explicit-operator-duplicate-risk-acceptance",
            "prior_inactive_not_confirmed": True,
            "source_evaluation_id": SUBMIT_UNKNOWN_KEY,
            "source_provider_run_id": barrier["provider_run_id"],
            "source_status": "submit-unknown",
            "source_provider_job_id": None,
            "source_run_path": barrier["run_path"],
            "source_run_sha256": barrier["run_sha256"],
            "maximum_possible_duplicate_charge_usd": float(
                MAXIMUM_POSSIBLE_DUPLICATE_CHARGE_USD
            ),
            "automatic_paid_retry": False,
            "fallback": None,
        }
        for row in selected_rows:
            if row["entry"].model_id == "alibaba/wan-2.2":
                row["duplicate_risk_acceptance"] = {
                    **copy.deepcopy(duplicate_risk_receipt),
                    "authorized_evaluation_id": row["entry"].evaluation_id,
                }
    invocation = {
        "mode": "dry-run" if dry_run else "generate",
        "selected_evaluation_ids": selected_keys,
        "selected_model_counts": dict(Counter(entry.model_id for entry in selected)),
        "budget": subset_budget,
        "prior_submit_unknown_acknowledged_inactive": (
            acknowledge_prior_submit_unknown_inactive if selects_wan_22 else None
        ),
        "duplicate_risk_acceptance": copy.deepcopy(duplicate_risk_receipt),
    }
    write_generation_manifest(
        inventory, rows, invocation=invocation, output_root=output_root
    )
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
        write_generation_manifest(
            inventory, rows, invocation=invocation, output_root=output_root
        )

    limits = pools.ProviderPoolLimits()
    actual_limits = {model_id: limits.for_model(model_id) for model_id in MODEL_IDS}
    if actual_limits != EXPECTED_ROUTE_CAPACITIES:
        raise TuneV5RetryVideoError("Shared provider pool capacities changed")
    return pools.run_provider_pools(
        selected_rows,
        limits,
        worker,
        on_complete,
        fail_fast=fail_fast,
    )


def verify(
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
    allow_incomplete: bool = False,
) -> tuple[bool, list[str]]:
    output_root = (output_root or root).resolve()
    inventory = load_inventory(root=root)
    errors: list[str] = []
    for entry in inventory.entries:
        paths = artifact_paths(entry, output_root)
        if not paths["prompt"].is_file() or not paths["run"].is_file():
            if not allow_incomplete:
                errors.append(f"{entry.provider_run_id}: missing artifacts")
            continue
        if read_json(paths["prompt"]) != prompt_artifact(entry):
            errors.append(f"{entry.provider_run_id}: prompt binding changed")
            continue
        run = read_json(paths["run"])
        status = run.get("status")
        request = transport.build_request_preview(provider_sample(entry), provider_prompt(entry))
        fingerprint = transport.request_fingerprint(request, provider_sample(entry))
        if status not in {"pending"} and (
            run.get("request") != request
            or run.get("request_sha256") != fingerprint
            or run.get("request_fingerprint_version") != transport.REQUEST_FINGERPRINT_VERSION
        ):
            errors.append(f"{entry.provider_run_id}: immutable request binding changed")
            continue
        if status in {"succeeded", "verification-failed"}:
            if run.get("submission_count") != 1 or not paths["video"].is_file():
                errors.append(f"{entry.provider_run_id}: terminal media receipt changed")
                continue
            try:
                media = transport.ffprobe_media(paths["video"])
            except Exception as exc:  # noqa: BLE001 - verification report
                errors.append(f"{entry.provider_run_id}: {transport.safe_error(exc)}")
                continue
            if media != run.get("media"):
                errors.append(f"{entry.provider_run_id}: media receipt changed")
        elif status in {"provider-failed", "failed-pre-submit"}:
            if paths["video"].exists() or run.get("fallback") is not None:
                errors.append(f"{entry.provider_run_id}: terminal failure has media/fallback")
        elif status in {"submit-unknown", "submitting", "submitted", "running"}:
            if not allow_incomplete:
                errors.append(f"{entry.provider_run_id}: provider may still be active ({status})")
        elif status in {"pending", "dry-run"}:
            if not allow_incomplete:
                errors.append(f"{entry.provider_run_id}: status={status}")
        else:
            errors.append(f"{entry.provider_run_id}: invalid status={status}")
        if run.get("submission_count") not in {0, 1}:
            errors.append(f"{entry.provider_run_id}: submission_count is not 0/1")
    return not errors, errors


def _add_subset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-id", action="append", choices=MODEL_IDS, default=[])
    parser.add_argument("--exclude-model", action="append", choices=MODEL_IDS, default=[])
    parser.add_argument("--target", action="append", choices=sorted(EXPECTED_KEYS), default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    _add_subset_arguments(dry)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--acknowledge-prior-submit-unknown-inactive", action="store_true")
    generate.add_argument(
        "--authorize-wan22-despite-unresolved-submit-unknown",
        action="store_true",
        help=(
            "Explicitly accept at most $0.35 possible duplicate spend without claiming "
            "that the prior submit-unknown request is inactive"
        ),
    )
    generate.add_argument("--timeout", type=int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--fail-fast", action="store_true")
    _add_subset_arguments(generate)
    check = subparsers.add_parser("verify")
    check.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            failures = run_batch(
                args.budget_cap_usd,
                dry_run=True,
                model_ids=args.model_id,
                exclude_models=args.exclude_model,
                targets=args.target,
                root=root,
            )
            return 1 if failures else 0
        if args.command == "generate":
            failures = run_batch(
                args.budget_cap_usd,
                dry_run=False,
                model_ids=args.model_id,
                exclude_models=args.exclude_model,
                targets=args.target,
                allow_external_processing=args.allow_external_processing,
                acknowledge_prior_submit_unknown_inactive=(
                    args.acknowledge_prior_submit_unknown_inactive
                ),
                authorize_wan22_despite_unresolved_submit_unknown=(
                    args.authorize_wan22_despite_unresolved_submit_unknown
                ),
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                fail_fast=args.fail_fast,
                root=root,
            )
            return 1 if failures else 0
        ok, errors = verify(root=root, allow_incomplete=args.allow_incomplete)
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 0 if ok else 1
    except (TuneV5RetryVideoError, retry_planning.TuneV5RetryPlanningError) as exc:
        print(f"Tune v5 retry video error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
