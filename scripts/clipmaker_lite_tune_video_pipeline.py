#!/usr/bin/env python3
"""Generate the immutable PROMOPAGES-10060 Tune I2V comparison batch.

This coordinator is intentionally separate from the prompt-only Tune pipeline.
It consumes the committed Tune manifest and the verified Clipmaker Lite v4
results without rewriting their prompts.  Only targets whose locked
``execution_mode`` is ``i2v`` are admitted to a video provider.  Compositor
targets remain explicit abstentions and can never be materialized as provider
jobs.

The normal run resolves transports only from
``docs/agents/clipmaker-lite/generation-routes.json``.  It never performs model
discovery, uploads generated videos to S3, or automatically creates a second
paid attempt.  Intentional retries require a new immutable batch namespace.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
PLANNING_BATCH_ID = "promopages-10060-tune-prompts-20260811-v4"
BATCH_ID = "promopages-10060-tune-videos-20260811-v1"
TUNE_MANIFEST_REL = Path("clipmaker-lite-test/tune-manifest.json")
CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")
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
EXPECTED_I2V_BY_MODEL = {
    "alibaba/wan-2.2": 14,
    "alibaba/wan-2.7": 12,
    "google/veo-3.1-lite": 17,
}
EXPECTED_COMPOSITOR_BY_MODEL = {
    "alibaba/wan-2.2": 10,
    "alibaba/wan-2.7": 4,
    "google/veo-3.1-lite": 8,
}
EXPECTED_I2V_COUNT = 43
EXPECTED_COMPOSITOR_COUNT = 22
EXPECTED_LOCAL_MEDIA_COUNT = 41
EXPECTED_PROVIDER_FAILURE_KEYS = frozenset(
    {
        ("07#06", "google/veo-3.1-lite"),
        ("10#07", "google/veo-3.1-lite"),
    }
)
ACCOUNTING_COST_PER_OUTPUT_USD = Decimal("0.35")
REQUIRED_BUDGET_CAP_USD = Decimal("15.05")
EXPECTED_ROUTE_CAPACITIES = {
    "alibaba/wan-2.2": 1,
    "alibaba/wan-2.7": 3,
    "google/veo-3.1-lite": 3,
}
NORMALIZED_INPUT_ASSET_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-lite-all-images-20260805-v2/"
    "normalized-input-assets-v1/2bdd38fc20a3d0edc595/asset.json"
)
NORMALIZED_INPUT_ASSET_SHA256 = (
    "b0f523dd03aa95681a44ab04d1830cec5efc43b21a714bbdb82df3bb5f21810b"
)
NORMALIZED_INPUT_CASE_ID = "12#08"
NORMALIZED_INPUT_MODEL_IDS = frozenset({"alibaba/wan-2.2", "alibaba/wan-2.7"})
NORMALIZED_INPUT_URL = (
    "https://avatars.mds.yandex.net/get-promoarticles/6165752/"
    "pub_6a59e32a3a302a69aec403c2_6a5a036cb1afef7284d68d17/scale_1200"
)
NORMALIZED_INPUT_SHA256 = (
    "66bfa65fd8c8c81d5d2e83be831f946ab1572082ecebf9d468a027d9b2bac691"
)
NORMALIZED_INPUT_BYTES = 386709
NORMALIZED_INPUT_WIDTH = 1200
NORMALIZED_INPUT_HEIGHT = 801
STRICT_MEDIA_QA_PROFILE = "clipmaker-lite-tune-strict-media-v1"
WAN_22_PIXEL_BUDGET = 1280 * 720
WAN_22_PIXEL_TOLERANCE = 0.03
WAN_22_SOURCE_ASPECT_TOLERANCE = 0.02
OPENROUTER_1080P_TARGET_PIXELS = 1920 * 1080
OPENROUTER_1080P_MIN_PIXELS = 1_900_000
OPENROUTER_1080P_MAX_PIXELS = 2_200_000
OPENROUTER_ASPECT_TOLERANCE = 0.03
BLOCKED_STATUSES = {
    "stale",
    "submit-unknown",
    "provider-failed",
    "verification-failed",
    "failed",
}


class TuneVideoPipelineError(RuntimeError):
    """A fail-closed Tune video coordinator error."""


@dataclass(frozen=True)
class TuneEntry:
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
    request_source_url: str
    request_source_sha256: str
    request_width: int
    request_height: int
    normalized_input_overlay: dict[str, Any] | None
    context_path: str
    planning_run_id: str
    result_path: str
    result_sha256: str
    tune_manifest_sha256: str
    route_registry_sha256: str
    execution_mode: str
    scene_plan: str
    positive_prompt: str | None
    negative_prompt: str | None
    structured_intent: dict[str, str]
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
        """Compatibility name consumed by the shared pool coordinator."""

        return self.provider_run_id


@dataclass(frozen=True)
class CompositorExclusion:
    case_id: str
    sheet_row: int
    article_slug: str
    image_id: str
    model_id: str
    planning_run_id: str
    execution_mode: str

    @property
    def provider_run_id(self) -> str:
        return (
            f"{BATCH_ID}-{self.article_slug}-{self.image_id}-"
            f"{MODEL_SUFFIXES[self.model_id]}"
        )


@dataclass(frozen=True)
class Inventory:
    entries: tuple[TuneEntry, ...]
    compositor_exclusions: tuple[CompositorExclusion, ...]
    tune_manifest_sha256: str
    route_registry_sha256: str
    contract_sha256: str
    budget: dict[str, Any]


@dataclass(frozen=True)
class ProviderOperations:
    """Network seams used only by the real generation command."""

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
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise TuneVideoPipelineError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TuneVideoPipelineError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise TuneVideoPipelineError(f"Required file does not exist: {path}") from exc
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneVideoPipelineError(
            f"Artifact is outside the output workspace: {path}"
        ) from exc


def safe_relative(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TuneVideoPipelineError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise TuneVideoPipelineError(f"Unsafe {label}: {value!r}")
    return value


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise TuneVideoPipelineError("--budget-cap-usd must be a decimal amount") from exc
    if parsed != REQUIRED_BUDGET_CAP_USD:
        raise TuneVideoPipelineError(
            "This immutable 43-output batch requires --budget-cap-usd 15.05 "
            "exactly (43 local accounting reservations at $0.35 each)"
        )
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except TuneVideoPipelineError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def budget_document(value: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(value)
    reserved = ACCOUNTING_COST_PER_OUTPUT_USD * EXPECTED_I2V_COUNT
    if reserved != parsed:
        raise TuneVideoPipelineError("Tune accounting reservation does not equal the cap")
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(REQUIRED_BUDGET_CAP_USD),
        "accounting_cost_per_output_usd": float(ACCOUNTING_COST_PER_OUTPUT_USD),
        "reserved_output_count": EXPECTED_I2V_COUNT,
        "maximum_estimated_cost_usd": float(reserved),
        "provider_unit_costs_asserted": False,
        "basis": (
            "local frozen accounting evidence only; each admitted immutable "
            "provider job reserves $0.35 and may submit at most once"
        ),
        "automatic_paid_retry": False,
    }


def _validate_routes(root: Path) -> tuple[dict[str, Any], str]:
    route_path = root / ROUTES_REL
    try:
        document = transport._load_generation_routes(route_path)  # noqa: SLF001
    except Exception as exc:
        raise TuneVideoPipelineError(
            f"Generation route registry is invalid: {transport.safe_error(exc)}"
        ) from exc
    if tuple(document.get("models", {}).keys()) != MODEL_IDS:
        raise TuneVideoPipelineError("Generation routes must contain the exact three Lite models")
    for model_id, expected in EXPECTED_ROUTE_CAPACITIES.items():
        route = document["models"][model_id]
        if route.get("capacity") != expected:
            raise TuneVideoPipelineError(
                f"Exact route capacity changed for {model_id}: {route.get('capacity')!r}"
            )
        if root.resolve() == ROOT.resolve() and route != transport.route_for_model(model_id):
            raise TuneVideoPipelineError(
                f"Loaded transport route differs from the committed registry: {model_id}"
            )
    return document, sha256_file(route_path)


def _validate_contract(root: Path) -> tuple[dict[str, Any], str]:
    path = root / CONTRACT_REL
    contract = read_json(path)
    if (
        not isinstance(contract, dict)
        or contract.get("agent_id") != AGENT_ID
        or contract.get("contract_version") != "2.2.0"
        or tuple((contract.get("models") or {}).keys()) != MODEL_IDS
    ):
        raise TuneVideoPipelineError("Unexpected Clipmaker Lite 2.2.0 contract")
    return contract, sha256_file(path)


def _provenance_summary(root: Path, run_id: str) -> dict[str, Any]:
    try:
        summary = clipmaker_lite_runner.provenance_summary(root.resolve(), run_id)
    except Exception as exc:
        raise TuneVideoPipelineError(
            f"Lite provenance failed for {run_id}: {transport.safe_error(exc)}"
        ) from exc
    if not isinstance(summary, dict) or summary.get("verified") is not True:
        raise TuneVideoPipelineError(f"Lite provenance is not verified: {run_id}")
    return summary


def _model_map(result: dict[str, Any], run_id: str) -> dict[str, dict[str, Any]]:
    models = result.get("models")
    if not isinstance(models, list) or any(not isinstance(value, dict) for value in models):
        raise TuneVideoPipelineError(f"Lite models are invalid: {run_id}")
    model_ids = [value.get("model_id") for value in models]
    if (
        any(model_id not in MODEL_IDS for model_id in model_ids)
        or len(model_ids) != len(set(model_ids))
    ):
        raise TuneVideoPipelineError(f"Lite model IDs are invalid: {run_id}")
    return {str(value["model_id"]): value for value in models}


def _normalized_input_overlay(
    *,
    root: Path,
    case_id: str,
    model_id: str,
    source_path: str,
    source_url: str,
    source_sha256: str,
) -> dict[str, Any] | None:
    """Return the single frozen, target-scoped >20 MiB input overlay.

    This is deliberately not a generic image mutation path.  Only the two Wan
    targets for case 12#08 may use the already committed MDS ``/scale_1200``
    receipt.  Planning provenance remains bound to the original source.
    """

    if case_id != NORMALIZED_INPUT_CASE_ID or model_id not in NORMALIZED_INPUT_MODEL_IDS:
        return None
    asset_path = root / NORMALIZED_INPUT_ASSET_REL
    asset_sha256 = sha256_file(asset_path)
    if asset_sha256 != NORMALIZED_INPUT_ASSET_SHA256:
        raise TuneVideoPipelineError("Frozen case 12#08 normalized-input receipt bytes changed")
    asset = read_json(asset_path)
    original = asset.get("original") if isinstance(asset, dict) else None
    normalized = asset.get("normalized") if isinstance(asset, dict) else None
    if (
        asset.get("manifest_role") != "promopages-10060-normalized-input-asset"
        or asset.get("strategy") != "frozen-page-variant"
        or asset.get("maximum_provider_input_bytes") != 20 * 1024 * 1024
        or not isinstance(original, dict)
        or original.get("path") != source_path
        or original.get("url") != source_url
        or original.get("sha256") != source_sha256
        or original.get("bytes") != 23472383
        or not isinstance(normalized, dict)
        or normalized.get("url") != NORMALIZED_INPUT_URL
        or normalized.get("sha256") != NORMALIZED_INPUT_SHA256
        or normalized.get("bytes") != NORMALIZED_INPUT_BYTES
        or normalized.get("width") != NORMALIZED_INPUT_WIDTH
        or normalized.get("height") != NORMALIZED_INPUT_HEIGHT
        or normalized.get("format") != "JPEG"
    ):
        raise TuneVideoPipelineError("Frozen case 12#08 normalized-input receipt changed")
    return {
        "scope": {
            "case_id": NORMALIZED_INPUT_CASE_ID,
            "model_ids": sorted(NORMALIZED_INPUT_MODEL_IDS),
        },
        "strategy": "frozen-page-variant",
        "asset_receipt_path": NORMALIZED_INPUT_ASSET_REL.as_posix(),
        "asset_receipt_sha256": asset_sha256,
        "original": {
            "path": source_path,
            "url": source_url,
            "sha256": source_sha256,
            "bytes": original["bytes"],
            "width": original["width"],
            "height": original["height"],
        },
        "provider_input": {
            "url": NORMALIZED_INPUT_URL,
            "sha256": NORMALIZED_INPUT_SHA256,
            "bytes": NORMALIZED_INPUT_BYTES,
            "width": NORMALIZED_INPUT_WIDTH,
            "height": NORMALIZED_INPUT_HEIGHT,
            "format": "JPEG",
        },
        "planning_provenance_uses_original": True,
        "prompt_changed": False,
    }


def load_inventory(
    budget_cap_usd: str | Decimal,
    root: Path = ROOT,
) -> Inventory:
    """Load and fail-closed validate all 65 Tune targets.

    The returned executable matrix contains exactly the 43 I2V targets.  The
    other 22 records remain explicit compositor exclusions.
    """

    root = root.resolve()
    budget = budget_document(budget_cap_usd)
    routes, route_sha256 = _validate_routes(root)
    contract, contract_sha256 = _validate_contract(root)
    manifest_path = root / TUNE_MANIFEST_REL
    manifest = read_json(manifest_path)
    manifest_sha256 = sha256_file(manifest_path)
    if not isinstance(manifest, dict):
        raise TuneVideoPipelineError("Tune manifest must be a JSON object")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("manifest_role") != "clipmaker-lite-tune-review"
        or manifest.get("ticket") != TICKET
        or manifest.get("batch_id") != PLANNING_BATCH_ID
        or manifest.get("agent_id") != AGENT_ID
        or manifest.get("contract_version") != contract.get("contract_version")
    ):
        raise TuneVideoPipelineError("Unexpected committed Tune manifest identity")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 36:
        raise TuneVideoPipelineError("Tune manifest must contain exactly 36 cases")

    entries: list[TuneEntry] = []
    exclusions: list[CompositorExclusion] = []
    seen_targets: set[tuple[str, str]] = set()
    verified_runs: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}

    for case in cases:
        if not isinstance(case, dict):
            raise TuneVideoPipelineError("Tune case must be a JSON object")
        case_id = case.get("case_id")
        article_slug = case.get("article_slug")
        source = case.get("source")
        planning = case.get("planning")
        targets = case.get("targets")
        if (
            not isinstance(case_id, str)
            or not isinstance(article_slug, str)
            or not isinstance(source, dict)
            or not isinstance(planning, dict)
            or not isinstance(targets, list)
        ):
            raise TuneVideoPipelineError("Tune case fields are invalid")
        source_path = safe_relative(source.get("path"), label="source.path")
        context_path = safe_relative(case.get("context_path"), label="context_path")
        source_url = source.get("url")
        source_sha256 = source.get("sha256")
        image_id = source.get("image_id")
        width = source.get("width")
        height = source.get("height")
        if (
            not isinstance(source_url, str)
            or not source_url.startswith("https://")
            or not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or not isinstance(image_id, str)
            or not isinstance(width, int)
            or width <= 0
            or not isinstance(height, int)
            or height <= 0
        ):
            raise TuneVideoPipelineError(f"Tune source metadata is invalid: {case_id}")
        if sha256_file(root / source_path) != source_sha256:
            raise TuneVideoPipelineError(f"Current source image mismatch: {source_path}")

        run_id = planning.get("run_id")
        result_path_value = planning.get("result_path")
        recorded_provenance = planning.get("provenance")
        expected_result_path = (
            ARTIFACT_NAMESPACE / str(run_id) / "result.json"
        ).as_posix()
        if (
            not isinstance(run_id, str)
            or not run_id.startswith(f"{PLANNING_BATCH_ID}-")
            or result_path_value != expected_result_path
            or not isinstance(recorded_provenance, dict)
        ):
            raise TuneVideoPipelineError(f"Tune planning identity is invalid: {case_id}")
        if run_id not in verified_runs:
            summary = _provenance_summary(root, run_id)
            if summary != recorded_provenance:
                raise TuneVideoPipelineError(
                    f"Committed Tune provenance differs from current verification: {run_id}"
                )
            result = read_json(root / expected_result_path)
            result_sha256 = sha256_file(root / expected_result_path)
            verified_runs[run_id] = (summary, result, result_sha256)
        summary, result, result_sha256 = verified_runs[run_id]
        if (
            result.get("job_id") != run_id
            or (result.get("producer") or {}).get("agent_id") != AGENT_ID
            or summary.get("agent_id") != AGENT_ID
            or summary.get("contract_version") != contract.get("contract_version")
            or summary.get("result_path") != expected_result_path
            or summary.get("source_image_sha256") != source_sha256
        ):
            raise TuneVideoPipelineError(f"Lite result identity mismatch: {run_id}")
        inputs = result.get("inputs")
        result_source = inputs.get("source_image") if isinstance(inputs, dict) else None
        result_context = inputs.get("article_context") if isinstance(inputs, dict) else None
        if (
            not isinstance(result_source, dict)
            or result_source.get("path") != source_path
            or result_source.get("sha256") != source_sha256
            or not isinstance(result_context, dict)
            or result_context.get("path") != context_path
        ):
            raise TuneVideoPipelineError(f"Lite input binding mismatch: {run_id}")
        context_sha256 = result_context.get("sha256")
        if not isinstance(context_sha256, str) or sha256_file(root / context_path) != context_sha256:
            raise TuneVideoPipelineError(f"Current article context mismatch: {context_path}")
        structured_intent = (result.get("analysis") or {}).get("structured_intent")
        if (
            not isinstance(structured_intent, dict)
            or structured_intent != planning.get("structured_intent")
            or set(structured_intent) != set(clipmaker_lite_runner.STRUCTURED_INTENT_KEYS)
            or any(not isinstance(value, str) or not value.strip() for value in structured_intent.values())
        ):
            raise TuneVideoPipelineError(f"Structured intent mismatch: {run_id}")
        result_models = _model_map(result, run_id)
        if summary.get("models") != list(result_models):
            raise TuneVideoPipelineError(f"Provenance model set mismatch: {run_id}")

        for target in targets:
            if not isinstance(target, dict):
                raise TuneVideoPipelineError(f"Tune target is invalid: {case_id}")
            model_id = target.get("model_id")
            sheet_row = target.get("sheet_row")
            tuned = target.get("tuned")
            key = (case_id, str(model_id))
            if (
                model_id not in MODEL_IDS
                or not isinstance(sheet_row, int)
                or not isinstance(tuned, dict)
                or key in seen_targets
                or model_id not in result_models
            ):
                raise TuneVideoPipelineError(f"Tune target identity is invalid: {case_id}")
            seen_targets.add(key)
            model = result_models[model_id]
            expected_runtime = contract["models"][model_id]["runtime"]
            if model.get("runtime") != expected_runtime or tuned.get("runtime") != expected_runtime:
                raise TuneVideoPipelineError(
                    f"Lite runtime differs from the locked contract: {case_id} / {model_id}"
                )
            for field in (
                "execution_mode",
                "scene_plan",
                "positive_prompt",
                "negative_prompt",
            ):
                if tuned.get(field) != model.get(field):
                    raise TuneVideoPipelineError(
                        f"Tune manifest rewrites {field}: {case_id} / {model_id}"
                    )
            execution_mode = model.get("execution_mode")
            if model.get("negative_prompt") is not None:
                raise TuneVideoPipelineError(
                    f"Authored negative_prompt must stay null: {case_id} / {model_id}"
                )
            if execution_mode == "deterministic-compositor":
                if model.get("positive_prompt") is not None:
                    raise TuneVideoPipelineError(
                        f"Compositor target has a provider prompt: {case_id} / {model_id}"
                    )
                exclusions.append(
                    CompositorExclusion(
                        case_id=case_id,
                        sheet_row=sheet_row,
                        article_slug=article_slug,
                        image_id=image_id,
                        model_id=model_id,
                        planning_run_id=run_id,
                        execution_mode=execution_mode,
                    )
                )
                continue
            if execution_mode != "i2v":
                raise TuneVideoPipelineError(
                    f"Unsupported execution_mode: {case_id} / {model_id} / {execution_mode!r}"
                )
            positive_prompt = model.get("positive_prompt")
            if not isinstance(positive_prompt, str) or not positive_prompt.strip():
                raise TuneVideoPipelineError(
                    f"I2V target has no positive prompt: {case_id} / {model_id}"
                )
            # Resolve the exact committed route while loading every executable
            # target. There is deliberately no catalog lookup or fallback.
            if routes["models"].get(model_id) is None:
                raise TuneVideoPipelineError(f"No exact generation route for {model_id}")
            normalized_overlay = _normalized_input_overlay(
                root=root,
                case_id=case_id,
                model_id=model_id,
                source_path=source_path,
                source_url=source_url,
                source_sha256=source_sha256,
            )
            request_source = (
                normalized_overlay["provider_input"]
                if normalized_overlay is not None
                else {
                    "url": source_url,
                    "sha256": source_sha256,
                    "width": width,
                    "height": height,
                }
            )
            entries.append(
                TuneEntry(
                    case_id=case_id,
                    sheet_row=sheet_row,
                    article_slug=article_slug,
                    image_id=image_id,
                    model_id=model_id,
                    source_path=source_path,
                    source_url=source_url,
                    source_sha256=source_sha256,
                    width=width,
                    height=height,
                    request_source_url=str(request_source["url"]),
                    request_source_sha256=str(request_source["sha256"]),
                    request_width=int(request_source["width"]),
                    request_height=int(request_source["height"]),
                    normalized_input_overlay=normalized_overlay,
                    context_path=context_path,
                    planning_run_id=run_id,
                    result_path=expected_result_path,
                    result_sha256=result_sha256,
                    tune_manifest_sha256=manifest_sha256,
                    route_registry_sha256=route_sha256,
                    execution_mode=execution_mode,
                    scene_plan=str(model["scene_plan"]),
                    positive_prompt=positive_prompt,
                    negative_prompt=None,
                    structured_intent=dict(structured_intent),
                    runtime=dict(expected_runtime),
                    provenance=dict(summary),
                )
            )

    i2v_counts = {model_id: 0 for model_id in MODEL_IDS}
    compositor_counts = {model_id: 0 for model_id in MODEL_IDS}
    for entry in entries:
        i2v_counts[entry.model_id] += 1
    for exclusion in exclusions:
        compositor_counts[exclusion.model_id] += 1
    if len(entries) != EXPECTED_I2V_COUNT or i2v_counts != EXPECTED_I2V_BY_MODEL:
        raise TuneVideoPipelineError(
            f"Tune I2V matrix changed: count={len(entries)}, models={i2v_counts}"
        )
    if (
        len(exclusions) != EXPECTED_COMPOSITOR_COUNT
        or compositor_counts != EXPECTED_COMPOSITOR_BY_MODEL
    ):
        raise TuneVideoPipelineError(
            "Tune compositor exclusions changed: "
            f"count={len(exclusions)}, models={compositor_counts}"
        )
    manifest_counts = (manifest.get("summary") or {}).get("execution_mode_counts")
    if manifest_counts != {
        "i2v": EXPECTED_I2V_COUNT,
        "deterministic-compositor": EXPECTED_COMPOSITOR_COUNT,
    }:
        raise TuneVideoPipelineError("Tune manifest execution-mode summary changed")
    return Inventory(
        entries=tuple(entries),
        compositor_exclusions=tuple(exclusions),
        tune_manifest_sha256=manifest_sha256,
        route_registry_sha256=route_sha256,
        contract_sha256=contract_sha256,
        budget=budget,
    )


def provider_sample(entry: TuneEntry) -> dict[str, Any]:
    return {
        "sample_id": f"{entry.article_slug}-{entry.image_id}",
        "article_slug": entry.article_slug,
        "image_id": entry.image_id,
        "image_number": entry.image_id,
        "source_path": entry.source_path,
        "source_url": entry.request_source_url,
        "sha256": entry.request_source_sha256,
        "width": entry.request_width,
        "height": entry.request_height,
    }


def provider_prompt(entry: TuneEntry) -> dict[str, Any]:
    if entry.execution_mode != "i2v":
        raise TuneVideoPipelineError(
            "Deterministic-compositor Tune targets must not be sent to a video provider: "
            f"{entry.provider_run_id}"
        )
    if not isinstance(entry.positive_prompt, str) or not entry.positive_prompt.strip():
        raise TuneVideoPipelineError(f"I2V positive prompt is empty: {entry.provider_run_id}")
    if entry.negative_prompt is not None:
        raise TuneVideoPipelineError(
            f"Clipmaker Lite negative_prompt must be null: {entry.provider_run_id}"
        )
    prompt: dict[str, Any] = {
        "sample_id": f"{entry.article_slug}-{entry.image_id}",
        "model_id": entry.model_id,
        "target_duration_seconds": entry.runtime["duration_seconds"],
        # Exact authored bytes are passed through unchanged.
        "positive_prompt": entry.positive_prompt,
        "negative_prompt": None,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
    }
    if entry.model_id == "alibaba/wan-2.7":
        if entry.runtime.get("prompt_expansion") != {
            "parameter": "prompt_extend",
            "value": True,
        }:
            raise TuneVideoPipelineError(
                f"Unexpected Wan 2.7 prompt expansion: {entry.provider_run_id}"
            )
        prompt["prompt_extend"] = True
    return prompt


def artifact_paths(entry: TuneEntry, output_root: Path = ROOT) -> dict[str, Path]:
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


def _safe_provenance(entry: TuneEntry) -> dict[str, Any]:
    summary = entry.provenance
    return {
        "verified": True,
        "verification_scope": summary.get("verification_scope"),
        "cryptographically_signed": summary.get("cryptographically_signed"),
        "agent_id": summary.get("agent_id"),
        "contract_version": summary.get("contract_version"),
        "contract_fingerprint": summary.get("contract_fingerprint"),
        "instruction_bundle_sha256": summary.get("instruction_bundle_sha256"),
        "source_image_sha256": summary.get("source_image_sha256"),
        "article_context_sha256": summary.get("article_context_sha256"),
        "models": summary.get("models"),
    }


def prompt_artifact(entry: TuneEntry) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-video-prompt",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": entry.model_id,
        "execution_mode": entry.execution_mode,
        "source": {
            "path": entry.source_path,
            "url": entry.source_url,
            "sha256": entry.source_sha256,
            "width": entry.width,
            "height": entry.height,
        },
        "provider_input": {
            "url": entry.request_source_url,
            "sha256": entry.request_source_sha256,
            "width": entry.request_width,
            "height": entry.request_height,
            "normalized_overlay": entry.normalized_input_overlay,
        },
        "structured_intent": entry.structured_intent,
        "scene_plan": entry.scene_plan,
        "prompt": {
            "positive": entry.positive_prompt,
            "negative": entry.negative_prompt,
            "rewritten": False,
        },
        "runtime": entry.runtime,
        "planning": {
            "batch_id": PLANNING_BATCH_ID,
            "run_id": entry.planning_run_id,
            "result_path": entry.result_path,
            "result_sha256": entry.result_sha256,
            "provenance": _safe_provenance(entry),
        },
        "bindings": {
            "tune_manifest_path": TUNE_MANIFEST_REL.as_posix(),
            "tune_manifest_sha256": entry.tune_manifest_sha256,
            "generation_routes_path": ROUTES_REL.as_posix(),
            "generation_routes_sha256": entry.route_registry_sha256,
        },
    }


def _initial_run(
    entry: TuneEntry,
    paths: dict[str, Path],
    output_root: Path,
) -> dict[str, Any]:
    route = transport.route_for_model(entry.model_id)
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-video-run",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "provider_run_id": entry.provider_run_id,
        "planning_run_id": entry.planning_run_id,
        "lite_result_sha256": entry.result_sha256,
        "tune_manifest_sha256": entry.tune_manifest_sha256,
        "route_registry_sha256": entry.route_registry_sha256,
        "case_id": entry.case_id,
        "sheet_row": entry.sheet_row,
        "model_id": entry.model_id,
        "execution_mode": entry.execution_mode,
        "adapter": route["adapter"],
        "status": "pending",
        "prompt_path": relative(paths["prompt"], output_root),
        "output_path": relative(paths["video"], output_root),
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
    }


def revalidate_entry(entry: TuneEntry, root: Path = ROOT) -> None:
    """Recheck immutable source, route, provenance, result and prompt bindings."""

    root = root.resolve()
    if sha256_file(root / TUNE_MANIFEST_REL) != entry.tune_manifest_sha256:
        raise TuneVideoPipelineError("Committed Tune manifest changed after inventory load")
    if sha256_file(root / ROUTES_REL) != entry.route_registry_sha256:
        raise TuneVideoPipelineError("Generation route registry changed after inventory load")
    if sha256_file(root / entry.source_path) != entry.source_sha256:
        raise TuneVideoPipelineError(f"Source image changed: {entry.source_path}")
    if sha256_file(root / entry.result_path) != entry.result_sha256:
        raise TuneVideoPipelineError(f"Lite result changed: {entry.result_path}")
    if entry.normalized_input_overlay is not None:
        fresh_overlay = _normalized_input_overlay(
            root=root,
            case_id=entry.case_id,
            model_id=entry.model_id,
            source_path=entry.source_path,
            source_url=entry.source_url,
            source_sha256=entry.source_sha256,
        )
        if fresh_overlay != entry.normalized_input_overlay:
            raise TuneVideoPipelineError(
                f"Normalized provider input changed: {entry.provider_run_id}"
            )
    elif (
        entry.request_source_url != entry.source_url
        or entry.request_source_sha256 != entry.source_sha256
        or entry.request_width != entry.width
        or entry.request_height != entry.height
    ):
        raise TuneVideoPipelineError(
            f"Unexpected provider-input overlay: {entry.provider_run_id}"
        )
    summary = _provenance_summary(root, entry.planning_run_id)
    if summary != entry.provenance:
        raise TuneVideoPipelineError(
            f"Lite provenance changed: {entry.planning_run_id}"
        )
    result = read_json(root / entry.result_path)
    model = _model_map(result, entry.planning_run_id).get(entry.model_id)
    if not isinstance(model, dict):
        raise TuneVideoPipelineError(
            f"Lite result lost model {entry.model_id}: {entry.planning_run_id}"
        )
    if (
        model.get("execution_mode") != "i2v"
        or model.get("positive_prompt") != entry.positive_prompt
        or model.get("negative_prompt") is not None
        or model.get("scene_plan") != entry.scene_plan
        or model.get("runtime") != entry.runtime
    ):
        raise TuneVideoPipelineError(
            f"Lite model plan changed: {entry.provider_run_id}"
        )


def _validate_existing_run_document(
    entry: TuneEntry,
    sample: dict[str, Any],
    prompt: dict[str, Any],
    paths: dict[str, Path],
    output_root: Path,
    run: Any,
) -> dict[str, Any]:
    """Validate an already materialized run without changing local files."""

    if not isinstance(run, dict):
        raise TuneVideoPipelineError(f"Tune run is not an object: {paths['run']}")
    expected_run = _initial_run(entry, paths, output_root)
    immutable = (
        "manifest_role",
        "ticket",
        "batch_id",
        "agent_id",
        "provider_run_id",
        "planning_run_id",
        "lite_result_sha256",
        "tune_manifest_sha256",
        "route_registry_sha256",
        "case_id",
        "sheet_row",
        "model_id",
        "execution_mode",
        "adapter",
        "prompt_path",
        "output_path",
        "automatic_paid_retry",
    )
    if any(run.get(key) != expected_run.get(key) for key in immutable):
        raise TuneVideoPipelineError(
            f"Immutable Tune provider run identity changed: {paths['run']}"
        )
    expected_request = transport.build_request_preview(sample, prompt)
    expected_fingerprint = transport.request_fingerprint(expected_request, sample)
    if run.get("request") is not None and run.get("request") != expected_request:
        raise TuneVideoPipelineError(
            f"Immutable Tune provider request changed: {paths['run']}"
        )
    if run.get("request") is not None and (
        run.get("request_sha256") != expected_fingerprint
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        raise TuneVideoPipelineError(
            f"Tune provider request fingerprint mismatch: {paths['run']}"
        )
    return run


def materialize_entry(
    entry: TuneEntry,
    root: Path = ROOT,
    output_root: Path | None = None,
) -> dict[str, Any]:
    output_root = (output_root or root).resolve()
    revalidate_entry(entry, root)
    sample = provider_sample(entry)
    prompt = provider_prompt(entry)
    paths = artifact_paths(entry, output_root)
    paths["directory"].mkdir(parents=True, exist_ok=True)
    expected_prompt = prompt_artifact(entry)
    if paths["prompt"].is_file():
        if read_json(paths["prompt"]) != expected_prompt:
            raise TuneVideoPipelineError(
                f"Immutable Tune provider prompt changed: {paths['prompt']}"
            )
    else:
        transport.atomic_write_json(paths["prompt"], expected_prompt)
    if paths["run"].is_file():
        _validate_existing_run_document(
            entry,
            sample,
            prompt,
            paths,
            output_root,
            read_json(paths["run"]),
        )
    else:
        transport.atomic_write_json(
            paths["run"],
            _initial_run(entry, paths, output_root),
        )
    return {
        "entry": entry,
        "sample": sample,
        "prompt": prompt,
        "paths": paths,
    }


def existing_materialized_rows(
    inventory: Inventory,
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Load the immutable request matrix without materializing missing files."""

    output_root = (output_root or root).resolve()
    missing: list[str] = []
    for entry in inventory.entries:
        paths = artifact_paths(entry, output_root)
        for name in ("prompt", "run"):
            if not paths[name].is_file():
                missing.append(relative(paths[name], output_root))
    if missing:
        raise TuneVideoPipelineError(
            "Local verification cannot materialize missing provider artifacts: "
            + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    for entry in inventory.entries:
        revalidate_entry(entry, root)
        sample = provider_sample(entry)
        prompt = provider_prompt(entry)
        paths = artifact_paths(entry, output_root)
        if read_json(paths["prompt"]) != prompt_artifact(entry):
            raise TuneVideoPipelineError(
                f"Immutable Tune provider prompt changed: {paths['prompt']}"
            )
        _validate_existing_run_document(
            entry,
            sample,
            prompt,
            paths,
            output_root,
            read_json(paths["run"]),
        )
        rows.append(
            {
                "entry": entry,
                "sample": sample,
                "prompt": prompt,
                "paths": paths,
            }
        )
    return rows


def materialize(
    inventory: Inventory,
    root: Path = ROOT,
    output_root: Path | None = None,
) -> list[dict[str, Any]]:
    return [
        materialize_entry(entry, root, output_root)
        for entry in inventory.entries
    ]


def _persist_run(path: Path, run: dict[str, Any]) -> None:
    transport.atomic_write_json(path, run)


def _append_unique_warning(warnings: list[str], value: str) -> None:
    if value not in warnings:
        warnings.append(value)


def _positive_media_dimension(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _ratio_parts(label: str) -> tuple[int, int]:
    try:
        left_value, right_value = label.split(":", 1)
        left = int(left_value)
        right = int(right_value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise TuneVideoPipelineError(
            f"Invalid requested aspect ratio: {label!r}"
        ) from exc
    if left <= 0 or right <= 0:
        raise TuneVideoPipelineError(f"Invalid requested aspect ratio: {label!r}")
    return left, right


def _relative_aspect_drift(
    width: int,
    height: int,
    expected_width: int,
    expected_height: int,
) -> float:
    actual = width / height
    expected = expected_width / expected_height
    return abs(actual / expected - 1.0)


def assess_tune_media_contract(
    row: dict[str, Any],
    media: dict[str, Any],
    *,
    prior_contract_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply deterministic model-aware Tune QA on top of shared checks.

    The shared transport assessment owns duration/audio and the Wan 2.2
    frame/fps checks.  Tune adds the resolution-area and aspect checks that the
    shared helper deliberately does not perform.  Advisory provider
    quantization warnings may therefore coexist with ``conforms: true``.
    """

    entry = row.get("entry")
    prompt = row.get("prompt")
    sample = row.get("sample")
    if (
        not isinstance(entry, TuneEntry)
        or not isinstance(prompt, dict)
        or not isinstance(sample, dict)
        or not isinstance(media, dict)
    ):
        raise TuneVideoPipelineError("Strict Tune media assessment row is invalid")
    target_duration = prompt.get("target_duration_seconds")
    expected_request = transport.build_request_preview(sample, prompt)
    base = transport.assess_contract(entry.model_id, media, target_duration)
    if not isinstance(base, dict):
        raise TuneVideoPipelineError("Shared media assessment is invalid")

    prior_requested: dict[str, Any] = {}
    prior_checks: dict[str, bool] = {}
    prior_warnings: list[str] = []
    if prior_contract_check is not None:
        if not isinstance(prior_contract_check, dict):
            raise TuneVideoPipelineError("Prior Tune contract check must be an object")
        raw_requested = prior_contract_check.get("requested")
        raw_checks = prior_contract_check.get("checks")
        raw_warnings = prior_contract_check.get("warnings")
        if raw_requested is not None and not isinstance(raw_requested, dict):
            raise TuneVideoPipelineError("Prior Tune requested media contract is invalid")
        if raw_checks is not None and (
            not isinstance(raw_checks, dict)
            or any(not isinstance(value, bool) for value in raw_checks.values())
        ):
            raise TuneVideoPipelineError("Prior Tune media checks are invalid")
        if raw_warnings is not None and (
            not isinstance(raw_warnings, list)
            or any(not isinstance(value, str) or not value for value in raw_warnings)
        ):
            raise TuneVideoPipelineError("Prior Tune media warnings are invalid")
        prior_requested = copy.deepcopy(raw_requested or {})
        prior_checks = dict(raw_checks or {})
        prior_warnings = list(raw_warnings or [])

    base_requested = base.get("requested")
    base_checks = base.get("checks")
    base_warnings = base.get("warnings")
    if (
        not isinstance(base_requested, dict)
        or not isinstance(base_checks, dict)
        or any(not isinstance(value, bool) for value in base_checks.values())
        or not isinstance(base_warnings, list)
        or any(not isinstance(value, str) or not value for value in base_warnings)
    ):
        raise TuneVideoPipelineError("Shared media assessment schema is invalid")

    requested = {**prior_requested, **copy.deepcopy(base_requested)}
    checks = {**prior_checks, **base_checks}
    warnings = list(prior_warnings)
    for warning in base_warnings:
        _append_unique_warning(warnings, warning)

    width = _positive_media_dimension(media.get("width"))
    height = _positive_media_dimension(media.get("height"))
    pixels = width * height if width is not None and height is not None else None
    requested["qa_profile"] = STRICT_MEDIA_QA_PROFILE

    if entry.model_id == "alibaba/wan-2.2":
        if (
            entry.runtime.get("resolution") != "720p"
            or entry.runtime.get("duration_seconds") != target_duration
            or entry.runtime.get("generate_audio") is not False
            or entry.runtime.get("frames") != 150
            or entry.runtime.get("fps") != 30
            or entry.runtime.get("aspect_ratios") != ["source"]
            or expected_request.get("input", {}).get("resolution") != "720p"
        ):
            raise TuneVideoPipelineError(
                f"Wan 2.2 strict media request/spec changed: {entry.provider_run_id}"
            )
        requested.update(
            {
                "pixel_budget": WAN_22_PIXEL_BUDGET,
                "pixel_tolerance_fraction": WAN_22_PIXEL_TOLERANCE,
                "aspect_ratio": "source",
                "source_width": entry.request_width,
                "source_height": entry.request_height,
                "aspect_tolerance_fraction": WAN_22_SOURCE_ASPECT_TOLERANCE,
            }
        )
        pixel_drift = (
            abs(pixels - WAN_22_PIXEL_BUDGET) / WAN_22_PIXEL_BUDGET
            if pixels is not None
            else math.inf
        )
        checks["pixels"] = pixel_drift <= WAN_22_PIXEL_TOLERANCE
        if not checks["pixels"]:
            actual_label = str(pixels) if pixels is not None else "unavailable"
            _append_unique_warning(
                warnings,
                "actual pixel count "
                f"{actual_label} falls outside the 720p target "
                f"{WAN_22_PIXEL_BUDGET} +/- {WAN_22_PIXEL_TOLERANCE * 100:.0f}%",
            )

        aspect_drift = (
            _relative_aspect_drift(
                width,
                height,
                entry.request_width,
                entry.request_height,
            )
            if width is not None and height is not None
            else math.inf
        )
        checks["source_aspect"] = aspect_drift <= WAN_22_SOURCE_ASPECT_TOLERANCE
        if width is None or height is None:
            _append_unique_warning(warnings, "actual source-aspect dimensions are unavailable")
        elif width * entry.request_height != height * entry.request_width:
            if checks["source_aspect"]:
                _append_unique_warning(
                    warnings,
                    "provider aspect quantization: actual "
                    f"{width}x{height} differs from source "
                    f"{entry.request_width}x{entry.request_height} by "
                    f"{aspect_drift * 100:.3f}% within the "
                    f"{WAN_22_SOURCE_ASPECT_TOLERANCE * 100:.0f}% tolerance",
                )
            else:
                _append_unique_warning(
                    warnings,
                    f"actual aspect {width}x{height} differs from source "
                    f"{entry.request_width}x{entry.request_height} by "
                    f"{aspect_drift * 100:.3f}%, beyond the "
                    f"{WAN_22_SOURCE_ASPECT_TOLERANCE * 100:.0f}% provider "
                    "quantization tolerance",
                )
    else:
        aspect_label = expected_request.get("aspect_ratio")
        resolution = expected_request.get("resolution")
        generate_audio = expected_request.get("generate_audio")
        request_duration = expected_request.get("duration")
        left, right = _ratio_parts(aspect_label)
        if (
            resolution != "1080p"
            or generate_audio is not False
            or request_duration != target_duration
        ):
            raise TuneVideoPipelineError(
                f"OpenRouter strict media request changed: {entry.provider_run_id}"
            )
        requested.update(
            {
                "pixel_budget": OPENROUTER_1080P_TARGET_PIXELS,
                "pixel_area_min": OPENROUTER_1080P_MIN_PIXELS,
                "pixel_area_max": OPENROUTER_1080P_MAX_PIXELS,
                "aspect_ratio": aspect_label,
                "aspect_tolerance_fraction": OPENROUTER_ASPECT_TOLERANCE,
            }
        )
        checks["pixels"] = (
            pixels is not None
            and OPENROUTER_1080P_MIN_PIXELS
            <= pixels
            <= OPENROUTER_1080P_MAX_PIXELS
        )
        if not checks["pixels"]:
            actual_label = str(pixels) if pixels is not None else "unavailable"
            _append_unique_warning(
                warnings,
                "actual pixel count "
                f"{actual_label} falls outside the 1080p constant-area band "
                f"{OPENROUTER_1080P_MIN_PIXELS}..{OPENROUTER_1080P_MAX_PIXELS}",
            )

        aspect_drift = (
            _relative_aspect_drift(width, height, left, right)
            if width is not None and height is not None
            else math.inf
        )
        checks["requested_aspect"] = aspect_drift <= OPENROUTER_ASPECT_TOLERANCE
        if width is None or height is None:
            _append_unique_warning(
                warnings,
                "actual requested-aspect dimensions are unavailable",
            )
        elif width * right != height * left:
            if checks["requested_aspect"]:
                _append_unique_warning(
                    warnings,
                    "provider aspect quantization: actual "
                    f"{width}x{height} differs from requested {aspect_label} by "
                    f"{aspect_drift * 100:.3f}% within the "
                    f"{OPENROUTER_ASPECT_TOLERANCE * 100:.0f}% tolerance",
                )
            else:
                _append_unique_warning(
                    warnings,
                    f"actual aspect {width}x{height} differs from requested "
                    f"{aspect_label} by {aspect_drift * 100:.3f}%, beyond the "
                    f"{OPENROUTER_ASPECT_TOLERANCE * 100:.0f}% provider "
                    "quantization tolerance",
                )

    return {
        "requested": requested,
        "checks": checks,
        "conforms": all(checks.values()),
        "warnings": warnings,
    }


def _worker_result(
    row: dict[str, Any],
    *,
    failed: bool,
    status: str,
    error: str | None = None,
    holds_provider_slot: bool = False,
) -> native.WorkerResult:
    return native.WorkerResult(
        row=row,
        failed=failed,
        status=status,
        error=error,
        holds_provider_slot=holds_provider_slot,
    )


def _verify_output(
    row: dict[str, Any],
    run: dict[str, Any],
    operations: ProviderOperations,
) -> native.WorkerResult:
    paths = row["paths"]
    entry = row["entry"]
    try:
        media = operations.media_probe(paths["video"])
        check = assess_tune_media_contract(row, media)
    except Exception as exc:
        error = transport.safe_error(exc)
        run.update(
            {
                "status": "verification-failed",
                "completed_at": transport.utc_now(),
                "provider_may_be_active": False,
                "media": None,
                "contract_check": None,
                "error": error,
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status="verification-failed",
            error=error,
        )
    status = "succeeded" if check.get("conforms") is True else "verification-failed"
    warnings = check.get("warnings") if isinstance(check, dict) else None
    error = None
    if status == "verification-failed":
        error = "Media contract warnings: " + "; ".join(
            str(value) for value in (warnings or ["unknown contract mismatch"])
        )
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
    _persist_run(paths["run"], run)
    return _worker_result(
        row,
        failed=status != "succeeded",
        status=status,
        error=error,
    )


def _eliza_failure(
    row: dict[str, Any],
    run: dict[str, Any],
    exc: BaseException,
    *,
    phase: str,
) -> native.WorkerResult:
    error = transport.safe_error(exc)
    if isinstance(exc, (transport.PreSubmitNetworkError, transport.PreSubmitRejectedError)):
        status = "failed-pre-submit"
        holds = False
        run.update(
            {
                "provider_job_id": None,
                "submitted_at": None,
                "completed_at": None,
            }
        )
    elif isinstance(exc, transport.ProviderTerminalError):
        status = "provider-failed"
        holds = False
        run["completed_at"] = transport.utc_now()
    elif run.get("provider_job_id"):
        # Poll/download can be resumed with the exact provider identity.  The
        # paid job may still be active, so its route slot remains reserved for
        # this launch.
        status = "submitted"
        holds = True
        run["completed_at"] = None
    else:
        # Any untyped failure once the paid POST started is ambiguous.  This
        # immutable namespace will never submit it again automatically.
        status = "submit-unknown"
        holds = True
        run["completed_at"] = None
    run.update(
        {
            "status": status,
            "provider_may_be_active": holds,
            "error": f"{phase}: {error}",
        }
    )
    _persist_run(row["paths"]["run"], run)
    return _worker_result(
        row,
        failed=True,
        status=status,
        error=run["error"],
        holds_provider_slot=holds,
    )


def _run_openrouter(
    row: dict[str, Any],
    run: dict[str, Any],
    args: argparse.Namespace,
    operations: ProviderOperations,
    root: Path,
    *,
    resume: bool,
) -> native.WorkerResult:
    entry = row["entry"]
    paths = row["paths"]
    try:
        headers = operations.eliza_headers()
    except Exception as exc:
        error = transport.safe_error(exc)
        status = "submitted" if resume else "failed-pre-submit"
        holds = resume
        run.update(
            {
                "status": status,
                "provider_may_be_active": holds,
                "error": f"credential resolution: {error}",
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status=status,
            error=run["error"],
            holds_provider_slot=holds,
        )

    job_id = run.get("provider_job_id") if resume else None
    if not resume:
        # Revalidate after credential resolution and immediately before the
        # sole paid POST. Persisting ``submitting`` makes a process crash
        # fail-closed instead of duplicating the charge.
        revalidate_entry(entry, root)
        run.update(
            {
                "status": "submitting",
                "provider_may_be_active": True,
                "provider_job_id": None,
                "submitted_at": None,
                "completed_at": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
        try:
            response = operations.http_json(
                "POST",
                transport.generation_route_url(
                    args.eliza_base_url,
                    entry.model_id,
                    "submit",
                ),
                run["request"],
                headers=headers,
                timeout=120,
            )
            job_id = transport.find_job_id(response)
            if not job_id:
                raise transport.PipelineError(
                    "Eliza/OpenRouter submit response did not contain a job ID"
                )
        except Exception as exc:
            return _eliza_failure(row, run, exc, phase="provider submit")
        run.update(
            {
                "status": "submitted",
                "provider_job_id": str(job_id),
                "submitted_at": transport.utc_now(),
                "provider_may_be_active": True,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)

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
        return _eliza_failure(row, run, exc, phase="provider poll/download")
    return _verify_output(row, run, operations)


def _run_segmind(
    row: dict[str, Any],
    run: dict[str, Any],
    args: argparse.Namespace,
    operations: ProviderOperations,
    root: Path,
) -> native.WorkerResult:
    entry = row["entry"]
    paths = row["paths"]

    def on_submitting(source_preflight: dict[str, Any]) -> None:
        # Segmind has already fetched and hashed the exact provider-input URL.
        # Recheck all immutable planning and normalized-overlay bindings before
        # its single non-idempotent POST.
        revalidate_entry(entry, root)
        current_request = transport.build_request_preview(
            provider_sample(entry), provider_prompt(entry)
        )
        if current_request != run["request"]:
            raise TuneVideoPipelineError(
                f"Wan 2.2 request changed after source preflight: {entry.provider_run_id}"
            )
        run.update(
            {
                "status": "submitting",
                "source_preflight": source_preflight,
                "provider_may_be_active": True,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)

    run.update(
        {
            "status": "preparing",
            "provider_may_be_active": False,
            "error": None,
        }
    )
    _persist_run(paths["run"], run)
    try:
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
            raise transport.PipelineError(
                "Eliza/Segmind completed without a provider request ID"
            )
    except Exception as exc:
        error = transport.safe_error(exc)
        if isinstance(exc, (transport.PreSubmitNetworkError, transport.PreSubmitRejectedError)):
            status = "failed-pre-submit"
            holds = False
        elif isinstance(exc, transport.SegmindProviderTaskFailedError):
            status = "provider-failed"
            holds = False
        elif run.get("status") == "preparing":
            # Failure occurred during remote source preflight, before the
            # durable callback and paid POST.
            status = "failed-pre-submit"
            holds = False
        else:
            status = "submit-unknown"
            holds = True
        run.update(
            {
                "status": status,
                "provider_may_be_active": holds,
                "completed_at": transport.utc_now() if status == "provider-failed" else None,
                "error": f"provider submit: {error}",
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status=status,
            error=run["error"],
            holds_provider_slot=holds,
        )
    run.update(
        {
            "status": "running",
            "provider_job_id": request_id,
            "provider_response": response,
            "provider_may_be_active": False,
            "submitted_at": transport.utc_now(),
            "error": None,
        }
    )
    _persist_run(paths["run"], run)
    return _verify_output(row, run, operations)


def run_provider_worker(
    original: dict[str, Any],
    args: argparse.Namespace,
    root: Path = ROOT,
    output_root: Path | None = None,
    operations: ProviderOperations | None = None,
) -> native.WorkerResult:
    """Run one exact provider job with no automatic paid retry."""

    output_root = (output_root or root).resolve()
    operations = operations or default_provider_operations()
    try:
        row = materialize_entry(original["entry"], root, output_root)
    except Exception as exc:
        error = transport.safe_error(exc)
        return _worker_result(
            original,
            failed=True,
            status="revalidation-failed",
            error=error,
        )
    entry = row["entry"]
    paths = row["paths"]
    run = read_json(paths["run"])
    request = transport.build_request_preview(row["sample"], row["prompt"])
    fingerprint = transport.request_fingerprint(request, row["sample"])
    status = run.get("status")
    dry_run = bool(getattr(args, "dry_run", False))

    if status == "succeeded":
        if paths["video"].is_file():
            return _worker_result(row, failed=False, status="succeeded")
        run.update(
            {
                "status": "stale",
                "provider_may_be_active": False,
                "error": "Succeeded run has no MP4; automatic resubmit is blocked",
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status="stale",
            error=run["error"],
        )
    if status == "submitting":
        if dry_run:
            return _worker_result(
                row,
                failed=True,
                status="submitting",
                error="Ambiguous submitting state is preserved by dry-run",
                holds_provider_slot=True,
            )
        run.update(
            {
                "status": "submit-unknown",
                "provider_may_be_active": True,
                "error": "Previous paid submit outcome is unknown; automatic retry is blocked",
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status="submit-unknown",
            error=run["error"],
            holds_provider_slot=True,
        )
    if status in BLOCKED_STATUSES:
        holds = status == "submit-unknown" or run.get("provider_may_be_active") is True
        return _worker_result(
            row,
            failed=True,
            status=str(status),
            error=f"Run status {status!r} blocks automatic paid retry",
            holds_provider_slot=holds,
        )
    resume = status in {"submitted", "running"}
    if resume and (
        not run.get("provider_job_id")
        or run.get("request") != request
        or run.get("request_sha256") != fingerprint
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        run.update(
            {
                "status": "stale",
                "provider_may_be_active": True,
                "error": "Active provider job lost its exact immutable request binding",
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(
            row,
            failed=True,
            status="stale",
            error=run["error"],
            holds_provider_slot=True,
        )
    if dry_run:
        if resume:
            return _worker_result(row, failed=False, status=str(status))
        run.update(
            {
                "status": "dry-run",
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": None,
                "submitted_at": None,
                "completed_at": None,
                "provider_may_be_active": False,
                "media": None,
                "contract_check": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
        return _worker_result(row, failed=False, status="dry-run")

    if not resume:
        run.update(
            {
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": None,
                "submitted_at": None,
                "completed_at": None,
                "provider_may_be_active": False,
                "media": None,
                "contract_check": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
    adapter = transport.route_for_model(entry.model_id)["adapter"]
    if adapter == "eliza-segmind":
        if resume:
            return _worker_result(
                row,
                failed=True,
                status=str(status),
                error="Synchronous Segmind jobs cannot resume or automatically resubmit",
            )
        return _run_segmind(row, run, args, operations, root)
    if adapter == "eliza-openrouter":
        return _run_openrouter(
            row,
            run,
            args,
            operations,
            root,
            resume=resume,
        )
    return _worker_result(
        row,
        failed=True,
        status="failed-pre-submit",
        error=f"Unsupported exact route adapter: {adapter}",
    )


def _effective_status(run: dict[str, Any]) -> str:
    status = str(run.get("status", "missing"))
    if (
        status == "succeeded"
        and isinstance(run.get("contract_check"), dict)
        and run["contract_check"].get("conforms") is False
    ):
        return "verification-failed"
    return status


def generation_manifest_document(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    output_root: Path = ROOT,
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    outputs: list[dict[str, Any]] = []
    for row in rows:
        paths = row["paths"]
        run = read_json(paths["run"]) if paths["run"].is_file() else {"status": "missing"}
        status = _effective_status(run)
        counts[status] = counts.get(status, 0) + 1
        entry = row["entry"]
        outputs.append(
            {
                "provider_run_id": entry.provider_run_id,
                "case_id": entry.case_id,
                "sheet_row": entry.sheet_row,
                "article_slug": entry.article_slug,
                "image_id": entry.image_id,
                "model_id": entry.model_id,
                "execution_mode": entry.execution_mode,
                "status": status,
                "prompt_path": relative(paths["prompt"], output_root),
                "run_path": relative(paths["run"], output_root),
                "video_path": relative(paths["video"], output_root),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
            }
        )
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-video-generation",
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": transport.utc_now(),
        "scope": {
            "planning_batch_id": PLANNING_BATCH_ID,
            "tune_manifest_path": TUNE_MANIFEST_REL.as_posix(),
            "tune_manifest_sha256": inventory.tune_manifest_sha256,
            "generation_routes_path": ROUTES_REL.as_posix(),
            "generation_routes_sha256": inventory.route_registry_sha256,
            "contract_path": CONTRACT_REL.as_posix(),
            "contract_sha256": inventory.contract_sha256,
            "expected_i2v_outputs": EXPECTED_I2V_COUNT,
            "compositor_provider_outputs": 0,
            "s3_upload": False,
            "delivery": "repository-files",
        },
        "budget": inventory.budget,
        "scheduling": {
            "independent_route_pools": True,
            "route_capacities": EXPECTED_ROUTE_CAPACITIES,
            "one_paid_submission_per_provider_run_id": True,
            "automatic_paid_retry": False,
        },
        "summary": counts,
        "outputs": outputs,
        "compositor_exclusions": [
            {
                "case_id": value.case_id,
                "sheet_row": value.sheet_row,
                "article_slug": value.article_slug,
                "image_id": value.image_id,
                "model_id": value.model_id,
                "planning_run_id": value.planning_run_id,
                "execution_mode": value.execution_mode,
                "status": "abstained",
                "provider_artifact": None,
            }
            for value in inventory.compositor_exclusions
        ],
    }


def write_generation_manifest(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    output_root: Path = ROOT,
) -> dict[str, Any]:
    document = generation_manifest_document(inventory, rows, output_root)
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
    segmind_base_url: str | None = None,
    eliza_base_url: str | None = None,
    root: Path = ROOT,
    output_root: Path | None = None,
    operations: ProviderOperations | None = None,
) -> int:
    """Materialize and execute/dry-run the immutable 43-job matrix."""

    if not dry_run and not allow_external_processing:
        raise TuneVideoPipelineError(
            "Real generation requires --allow-external-processing because "
            "source image URLs and exact Lite prompts are sent to Eliza providers"
        )
    output_root = (output_root or root).resolve()
    inventory = load_inventory(budget_cap_usd, root)
    rows = materialize(inventory, root, output_root)
    write_generation_manifest(inventory, rows, output_root)
    args = argparse.Namespace(
        dry_run=dry_run,
        timeout=timeout,
        poll_interval=poll_interval,
        fail_fast=fail_fast,
        segmind_base_url=(
            segmind_base_url
            or transport.route_for_model("alibaba/wan-2.2")["default_base_url"]
        ),
        eliza_base_url=(
            eliza_base_url
            or transport.route_for_model("alibaba/wan-2.7")["default_base_url"]
        ),
    )
    operations = operations or default_provider_operations()
    completed = 0

    def worker(row: dict[str, Any]) -> native.WorkerResult:
        return run_provider_worker(
            row,
            args,
            root,
            output_root,
            operations,
        )

    def on_complete(result: native.WorkerResult) -> None:
        nonlocal completed
        completed += 1
        for index, existing in enumerate(rows):
            if existing["entry"].provider_run_id == result.row["entry"].provider_run_id:
                rows[index] = result.row
                break
        write_generation_manifest(inventory, rows, output_root)
        detail = f": {result.error}" if result.error else ""
        stream = sys.stderr if result.failed else sys.stdout
        print(
            f"Tune [{completed}/{len(rows)}] {result.row['entry'].provider_run_id} "
            f"-> {result.status}{detail}",
            file=stream,
            flush=True,
        )

    limits = native.ProviderPoolLimits()
    if {
        model_id: limits.for_model(model_id) for model_id in MODEL_IDS
    } != EXPECTED_ROUTE_CAPACITIES:
        raise TuneVideoPipelineError("Shared provider pool capacities changed")
    return native.run_provider_pools(
        rows,
        limits,
        worker,
        on_complete,
        fail_fast=fail_fast,
    )


def _validate_generation_manifest_snapshot(
    inventory: Inventory,
    rows: list[dict[str, Any]],
    output_root: Path,
) -> tuple[dict[str, Any], str]:
    path = output_root / GENERATION_MANIFEST_REL
    if not path.is_file():
        raise TuneVideoPipelineError(
            "Local verification requires the existing generation manifest"
        )
    current = read_json(path)
    expected = generation_manifest_document(inventory, rows, output_root)
    if not isinstance(current, dict) or not isinstance(current.get("updated_at"), str):
        raise TuneVideoPipelineError("Existing generation manifest is invalid")
    current_comparable = copy.deepcopy(current)
    expected_comparable = copy.deepcopy(expected)
    current_comparable.pop("updated_at", None)
    expected_comparable.pop("updated_at", None)
    if current_comparable != expected_comparable:
        raise TuneVideoPipelineError(
            "Existing generation manifest differs from its bound local run files"
        )
    return current, sha256_file(path)


def refresh_local_verification(
    budget_cap_usd: str | Decimal,
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
    media_probe: Callable[[Path], dict[str, Any]] = transport.ffprobe_media,
) -> dict[str, Any]:
    """Recheck the 41 downloaded MP4s without entering a provider code path.

    All probes and immutable-binding checks complete before any write.  The 41
    terminal downloaded run records and the aggregate generation manifest are
    then replaced through the shared atomic JSON writer.  The two terminal
    provider failures are required to match their frozen keys and remain byte
    for byte untouched.
    """

    output_root = (output_root or root).resolve()
    inventory = load_inventory(budget_cap_usd, root)
    rows = existing_materialized_rows(
        inventory,
        root=root,
        output_root=output_root,
    )
    _generation, generation_sha256 = _validate_generation_manifest_snapshot(
        inventory,
        rows,
        output_root,
    )

    local_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    failure_keys: set[tuple[str, str]] = set()
    run_snapshots: dict[Path, str] = {}
    video_snapshots: dict[Path, str] = {}
    for row in rows:
        entry = row["entry"]
        paths = row["paths"]
        run = read_json(paths["run"])
        status = _effective_status(run)
        key = (entry.case_id, entry.model_id)
        run_snapshots[paths["run"]] = sha256_file(paths["run"])
        if status == "provider-failed":
            failure_keys.add(key)
            if (
                paths["video"].exists()
                or run.get("provider_may_be_active") is not False
                or not isinstance(run.get("provider_job_id"), str)
                or not run["provider_job_id"]
                or not isinstance(run.get("error"), str)
                or not run["error"]
                or run.get("media") is not None
                or run.get("contract_check") is not None
            ):
                raise TuneVideoPipelineError(
                    f"Terminal provider failure changed: {entry.provider_run_id}"
                )
            continue
        if status not in {"succeeded", "verification-failed"}:
            raise TuneVideoPipelineError(
                f"Local verification found non-terminal run: "
                f"{entry.provider_run_id} / {status}"
            )
        if (
            run.get("provider_may_be_active") is not False
            or not isinstance(run.get("provider_job_id"), str)
            or not run["provider_job_id"]
            or not paths["video"].is_file()
            or not isinstance(run.get("media"), dict)
        ):
            raise TuneVideoPipelineError(
                f"Downloaded Tune run is not locally recheckable: {entry.provider_run_id}"
            )
        recorded_media = run["media"]
        if (
            sha256_file(paths["video"]) != recorded_media.get("sha256")
            or paths["video"].stat().st_size != recorded_media.get("bytes")
        ):
            raise TuneVideoPipelineError(
                f"Local MP4 binding changed before recheck: {entry.provider_run_id}"
            )
        video_snapshots[paths["video"]] = recorded_media["sha256"]
        local_rows.append((row, run))

    if len(local_rows) != EXPECTED_LOCAL_MEDIA_COUNT:
        raise TuneVideoPipelineError(
            f"Local verification requires exactly {EXPECTED_LOCAL_MEDIA_COUNT} MP4s; "
            f"found {len(local_rows)}"
        )
    if failure_keys != EXPECTED_PROVIDER_FAILURE_KEYS:
        raise TuneVideoPipelineError(
            f"Terminal provider failure set changed: {sorted(failure_keys)}"
        )

    updates: list[tuple[Path, dict[str, Any]]] = []
    for row, run in local_rows:
        entry = row["entry"]
        paths = row["paths"]
        try:
            media = media_probe(paths["video"])
        except Exception as exc:
            raise TuneVideoPipelineError(
                f"{entry.provider_run_id}: local ffprobe failed: "
                f"{transport.safe_error(exc)}"
            ) from exc
        if media != run.get("media"):
            raise TuneVideoPipelineError(
                f"{entry.provider_run_id}: recorded media differs from local MP4"
            )
        check = assess_tune_media_contract(
            row,
            media,
            prior_contract_check=run.get("contract_check"),
        )
        prior_status = _effective_status(run)
        status = (
            "verification-failed"
            if prior_status == "verification-failed" or check.get("conforms") is not True
            else "succeeded"
        )
        warnings = check.get("warnings") or []
        error: str | None = None
        if status == "verification-failed":
            if warnings:
                error = "Media contract warnings: " + "; ".join(warnings)
            elif isinstance(run.get("error"), str) and run["error"]:
                error = run["error"]
            else:
                error = "Media contract verification failed without a warning"
        updated = copy.deepcopy(run)
        updated.update(
            {
                "status": status,
                "media": media,
                "contract_check": check,
                "error": error,
                "local_media_verification": {
                    "profile": STRICT_MEDIA_QA_PROFILE,
                    "source": "local-mp4-ffprobe",
                    "media_sha256": media.get("sha256"),
                    "provider_calls": False,
                    "paid_submission": False,
                    "automatic_paid_retry": False,
                },
            }
        )
        updates.append((paths["run"], updated))

    generation_path = output_root / GENERATION_MANIFEST_REL
    if sha256_file(generation_path) != generation_sha256:
        raise TuneVideoPipelineError("Generation manifest changed during local recheck")
    for path, expected_sha256 in run_snapshots.items():
        if sha256_file(path) != expected_sha256:
            raise TuneVideoPipelineError(f"Run changed during local recheck: {path}")
    for path, expected_sha256 in video_snapshots.items():
        if sha256_file(path) != expected_sha256:
            raise TuneVideoPipelineError(f"MP4 changed during local recheck: {path}")

    try:
        for path, document in updates:
            transport.atomic_write_json(path, document)
        refreshed = write_generation_manifest(inventory, rows, output_root)
    except Exception as exc:
        raise TuneVideoPipelineError(
            f"Atomic local verification update failed: {transport.safe_error(exc)}"
        ) from exc
    return refreshed


def verify(
    budget_cap_usd: str | Decimal,
    *,
    allow_incomplete: bool = False,
    allow_contract_warnings: bool = False,
    root: Path = ROOT,
    output_root: Path | None = None,
    media_probe: Callable[[Path], dict[str, Any]] = transport.ffprobe_media,
) -> tuple[bool, list[str]]:
    output_root = (output_root or root).resolve()
    inventory = load_inventory(budget_cap_usd, root)
    rows = existing_materialized_rows(
        inventory,
        root=root,
        output_root=output_root,
    )
    _validate_generation_manifest_snapshot(inventory, rows, output_root)
    errors: list[str] = []
    verified_media = 0
    provider_failures: set[tuple[str, str]] = set()
    for row in rows:
        entry = row["entry"]
        paths = row["paths"]
        run = read_json(paths["run"])
        status = _effective_status(run)
        if status == "provider-failed":
            key = (entry.case_id, entry.model_id)
            if key not in EXPECTED_PROVIDER_FAILURE_KEYS:
                errors.append(
                    f"{entry.provider_run_id}: unexpected terminal provider failure"
                )
                continue
            if (
                paths["video"].exists()
                or run.get("provider_may_be_active") is not False
                or not isinstance(run.get("provider_job_id"), str)
                or not run["provider_job_id"]
                or not isinstance(run.get("error"), str)
                or not run["error"]
                or run.get("media") is not None
                or run.get("contract_check") is not None
            ):
                errors.append(
                    f"{entry.provider_run_id}: terminal provider failure audit is invalid"
                )
                continue
            provider_failures.add(key)
            continue
        if status not in {"succeeded", "verification-failed"}:
            if not allow_incomplete:
                errors.append(f"{entry.provider_run_id}: status={status}")
            continue
        if not paths["video"].is_file():
            errors.append(f"{entry.provider_run_id}: MP4 is missing")
            continue
        try:
            media = media_probe(paths["video"])
        except Exception as exc:
            errors.append(
                f"{entry.provider_run_id}: ffprobe failed: {transport.safe_error(exc)}"
            )
            continue
        if media != run.get("media"):
            errors.append(f"{entry.provider_run_id}: recorded media differs from MP4")
            continue
        expected_check = assess_tune_media_contract(
            row,
            media,
            prior_contract_check=run.get("contract_check"),
        )
        if expected_check != run.get("contract_check"):
            errors.append(f"{entry.provider_run_id}: contract check changed")
            continue
        verified_media += 1
        if expected_check.get("conforms") is not True and not allow_contract_warnings:
            errors.append(
                f"{entry.provider_run_id}: media contract warnings require "
                "--allow-contract-warnings"
            )
    if not allow_incomplete and verified_media != EXPECTED_LOCAL_MEDIA_COUNT:
        errors.append(
            f"verified local MP4 outputs={verified_media}; "
            f"expected={EXPECTED_LOCAL_MEDIA_COUNT}"
        )
    if not allow_incomplete and provider_failures != EXPECTED_PROVIDER_FAILURE_KEYS:
        errors.append(
            "terminal provider failure set changed: "
            f"{sorted(provider_failures)}"
        )
    return not errors, errors


def export_tune_video_overlay(
    media_commit_sha: str,
    *,
    root: Path = ROOT,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Reject the obsolete provider-only overlay contract.

    The final Tune matrix contains provider videos, canonical compositor
    videos, and two audited compositor fallbacks.  Only the dedicated media
    overlay coordinator can bind that complete 65-target matrix.
    """

    del media_commit_sha, root, output_root
    raise TuneVideoPipelineError(
        "export-overlay is superseded by "
        "scripts/clipmaker_lite_tune_media_overlay.py; the legacy 43-provider "
        "overlay omits compositor and terminal-failure fallback provenance"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry = subparsers.add_parser(
        "dry-run",
        help="validate and materialize all 43 requests without provider calls",
    )
    dry.add_argument("--budget-cap-usd", type=budget_arg, required=True)

    generate = subparsers.add_parser(
        "generate",
        help="run the immutable 43-job Tune batch through exact Eliza routes",
    )
    generate.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--timeout", type=int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--fail-fast", action="store_true")
    generate.add_argument(
        "--segmind-base-url",
        default=os.environ.get(
            "ELIZA_SEGMIND_BASE_URL",
            transport.route_for_model("alibaba/wan-2.2")["default_base_url"],
        ),
    )
    generate.add_argument(
        "--eliza-base-url",
        default=os.environ.get(
            "ELIZA_OPENROUTER_BASE_URL",
            transport.route_for_model("alibaba/wan-2.7")["default_base_url"],
        ),
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="verify local MP4 bindings and strict/accepted media contracts",
    )
    verify_parser.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    verify_parser.add_argument("--allow-contract-warnings", action="store_true")

    refresh_parser = subparsers.add_parser(
        "refresh-local-verification",
        aliases=["recheck-local"],
        help=(
            "ffprobe and atomically refresh strict QA for the 41 existing local "
            "MP4s; never submit or retry provider jobs"
        ),
    )
    refresh_parser.add_argument("--budget-cap-usd", type=budget_arg, required=True)

    export = subparsers.add_parser(
        "export-overlay",
        help="reject the superseded provider-only overlay command",
    )
    export.add_argument("--media-commit-sha", required=True)
    export.add_argument(
        "--output",
        type=Path,
        default=BATCH_ROOT_REL / "tune-video-overlay.json",
    )
    return parser


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            failures = run_batch(
                args.budget_cap_usd,
                dry_run=True,
                root=root,
            )
            if failures:
                print(f"FAIL: Tune dry-run has {failures} failure(s)", file=sys.stderr)
                return 1
            print(
                "PASS: 43 exact Tune I2V requests validated under $15.05; "
                "22 compositor targets abstained; no provider or S3 call",
                flush=True,
            )
            return 0
        if args.command == "generate":
            failures = run_batch(
                args.budget_cap_usd,
                dry_run=False,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                fail_fast=args.fail_fast,
                segmind_base_url=args.segmind_base_url,
                eliza_base_url=args.eliza_base_url,
                root=root,
            )
            return 1 if failures else 0
        if args.command == "verify":
            ok, errors = verify(
                args.budget_cap_usd,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
                root=root,
            )
            for error in errors:
                print(f"FAIL: {error}", file=sys.stderr)
            if ok:
                print("PASS: Tune video artifacts verified", flush=True)
            return 0 if ok else 1
        if args.command in {"refresh-local-verification", "recheck-local"}:
            refreshed = refresh_local_verification(
                args.budget_cap_usd,
                root=root,
            )
            summary = refreshed.get("summary") or {}
            print(
                "PASS: refreshed strict local QA for 41 MP4s without provider "
                f"calls or paid retries; summary={json.dumps(summary, sort_keys=True)}",
                flush=True,
            )
            return 0
        if args.command == "export-overlay":
            overlay = export_tune_video_overlay(args.media_commit_sha, root=root)
            output = args.output
            if not output.is_absolute():
                output = root / output
            safe_relative(output.resolve().relative_to(root.resolve()).as_posix(), label="output")
            transport.atomic_write_json(output, overlay)
            print(relative(output, root), flush=True)
            return 0
        raise TuneVideoPipelineError(f"Unsupported command: {args.command}")
    except TuneVideoPipelineError as exc:
        print(f"FAIL: {transport.safe_error(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
