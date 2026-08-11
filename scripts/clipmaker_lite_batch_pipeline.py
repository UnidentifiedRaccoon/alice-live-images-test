#!/usr/bin/env python3
"""Run and verify the PROMOPAGES-9909 5x3 native Clipmaker Lite video batch.

Each source image has one current, verified ``clipmaker-lite`` planning result
containing the shared structured intent and all three model plans.  The bridge
expands those five planning results into 15 provider runs, selecting only the
matching model plan without authoring, rewriting, or borrowing prompts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


BATCH_ID = "promopages-9909-lite1-20260723"
TICKET = "PROMOPAGES-9909"
AGENT_ID = "clipmaker-lite"
CONTRACT_PATH = ROOT / "docs/agents/clipmaker-lite/contract.json"
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")
MANIFEST_PATH = Path("PROMOPAGES-9857/clipmaker-lite-runs") / BATCH_ID / "manifest.json"
# Normally planning and provider artifacts share ``root``. Historical frozen
# batches may bind planning provenance/results to a read-only workspace while
# keeping provider receipts and MP4s in the current workspace.
PLANNING_WORKSPACE: Path | None = None
PLANNING_PROVENANCE_VERIFIER: Callable[[Path, str], dict[str, Any]] | None = None
PUBLIC_SOURCE_BASE = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/main/"
)
MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
PLANNING_BATCH_ID = BATCH_ID
PLANNING_MODEL_IDS = MODEL_IDS
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
WAN_MODEL_ID = "alibaba/wan-2.2"
WAN_27_MODEL_ID = "alibaba/wan-2.7"
VEO_31_MODEL_ID = "google/veo-3.1-lite"
WAN_27_MIN_SOURCE_DIMENSION_PX = 240
ELIZA_MODEL_IDS = {WAN_27_MODEL_ID, VEO_31_MODEL_ID}
DEFAULT_WAN_22_CONCURRENCY = int(
    transport.route_for_model(WAN_MODEL_ID)["capacity"]
)
DEFAULT_WAN_27_CONCURRENCY = int(
    transport.route_for_model(WAN_27_MODEL_ID)["capacity"]
)
DEFAULT_VEO_31_CONCURRENCY = int(
    transport.route_for_model(VEO_31_MODEL_ID)["capacity"]
)
DEFAULT_ELIZA_CONCURRENCY = DEFAULT_WAN_27_CONCURRENCY
# Only isolated historical/diagnostic wrappers may override this.  Normal
# batches leave it unset and therefore use the registry's legacy Wan route.
WAN_SUBMIT_MODE: str | None = None
# Programmatic-only terminal scheduling exclusions. A higher-level coordinator
# may populate this scoped set only after it has independently verified a
# terminal logical-output overlay. The rows remain in the immutable matrix and
# aggregate manifest; they are merely withheld from provider workers and from
# automatic unresolved-job widening for that invocation.
SCHEDULING_EXCLUDED_RUN_IDS: frozenset[str] = frozenset()
BLOCKED_STATUSES = {
    "stale",
    "failed",
    "revalidation-failed",
    "worker-failed",
    "submit-unknown",
    "provider-failed",
    "verification-failed",
}
TERMINAL_PROVIDER_FAILURE_MARKERS = (
    "failed with status",
    "cancelled",
    "canceled",
    "expired",
    "session_not_found",
)
LEGACY_ELIZA_DNS_PRE_SUBMIT_ERROR = (
    "POST https://api.eliza.yandex.net/openrouter/v1/videos failed: "
    "[Errno 8] nodename nor servname provided, or not known"
)
# One receipt written before PreSubmitRejectedError existed. Hashing the exact
# dynamic error avoids embedding quota-account metadata in source while keeping
# this migration scoped to that receipt and request only.
LEGACY_SEGMIND_QUOTA_ERROR_SHA256 = (
    "fa3dfebe3283a1ac3e9cc32f2973e2d1006ac39ee246cd5a098b8b6f10194df2"
)
LEGACY_SEGMIND_QUOTA_REQUEST_SHA256 = (
    "6d148c413381576069d9964a34805cfa1a9dccda881ec7aa5cb0646fc1e5bd34"
)


class BatchPipelineError(RuntimeError):
    """A fail-closed error in the native Clipmaker Lite batch bridge."""


class ProviderInputDimensionError(BatchPipelineError):
    """A locally provable provider input rejection before any paid submit."""

    def __init__(self, message: str, evidence: dict[str, Any]) -> None:
        super().__init__(message)
        self.evidence = dict(evidence)


@dataclass(frozen=True)
class Sample:
    sample_id: str
    article_slug: str
    image_id: str
    filename: str
    source_sha256: str
    width: int
    height: int

    @property
    def source_path(self) -> str:
        return f"PROMOPAGES-9857/articles/{self.article_slug}/{self.filename}"

    @property
    def context_path(self) -> str:
        return f"PROMOPAGES-9884/articles/{self.article_slug}/content.json"

    @property
    def planning_run_id(self) -> str:
        """The single Clipmaker Lite planning run shared by all model entries."""

        return f"{PLANNING_BATCH_ID}-{self.sample_id}"


@dataclass(frozen=True)
class Entry:
    sample: Sample
    model_id: str

    @property
    def provider_run_id(self) -> str:
        """The provider-specific generation identity used by queue filters."""

        return f"{BATCH_ID}-{self.sample.sample_id}-{MODEL_SUFFIXES[self.model_id]}"

    @property
    def planning_run_id(self) -> str:
        return self.sample.planning_run_id

    @property
    def run_id(self) -> str:
        """Backward-compatible alias for the provider generation identity."""

        return self.provider_run_id


@dataclass(frozen=True)
class LiteJob:
    entry: Entry
    structured_intent: dict[str, str]
    execution_mode: str
    positive_prompt: str
    negative_prompt: str | None
    result_path: str
    result_sha256: str
    provenance: dict[str, Any]
    runtime: dict[str, Any]


@dataclass(frozen=True)
class WorkerResult:
    """One provider worker outcome returned to the coordinator thread."""

    row: dict[str, Any]
    failed: bool
    status: str
    error: str | None = None
    holds_provider_slot: bool = False


@dataclass(frozen=True)
class ProviderPoolLimits:
    """Independent local capacities for the three paid provider routes."""

    wan_22: int = DEFAULT_WAN_22_CONCURRENCY
    wan_27: int = DEFAULT_WAN_27_CONCURRENCY
    veo_31: int = DEFAULT_VEO_31_CONCURRENCY

    def for_model(self, model_id: str) -> int:
        if model_id == WAN_MODEL_ID:
            return self.wan_22
        if model_id == WAN_27_MODEL_ID:
            return self.wan_27
        if model_id == VEO_31_MODEL_ID:
            return self.veo_31
        raise BatchPipelineError(f"Unsupported provider route: {model_id}")

    @property
    def total(self) -> int:
        return self.wan_22 + self.wan_27 + self.veo_31


@dataclass(frozen=True)
class ProviderOperations:
    """Synchronous provider seams, replaceable by network-free tests."""

    eliza_headers: Callable[[], dict[str, str]]
    http_json: Callable[..., Any]
    eliza_poll: Callable[..., dict[str, Any]]
    http_download: Callable[..., None]
    segmind_generate: Callable[..., dict[str, Any]]
    wan_generate: Callable[..., None]
    media_probe: Callable[[Path], dict[str, Any]]


SAMPLES = (
    Sample(
        "01-portrait-hands",
        "01-pharmocean-magiia-magniia",
        "02",
        "02.jpeg",
        "dac18b13cd08c2403ca22b41b428eb1293acd6b0e35a02f8a7082ad00a77c68f",
        2400,
        1600,
    ),
    Sample(
        "02-product-dropper",
        "04-graceface-antivozrastnaia-syvorotka",
        "05",
        "05.png",
        "d8f32e5b4953b00d118abfe53468b4359ba56dd31d2aa69b935c10d76f310835",
        1280,
        800,
    ),
    Sample(
        "03-animal-step",
        "06-4lapy-koshachii-napolnitel",
        "03",
        "03.jpeg",
        "f31d778c510ed4bc9601667c4a40810e8e79d46db7cb624d263fa1fa5f7517c3",
        1000,
        450,
    ),
    Sample(
        "04-interior-water",
        "13-ilinka-elitnyi-zhk",
        "09",
        "09.png",
        "10dd4f44ea0e4d5cf66f0c297840e802aaad7fcd675aeb5bcb24436cf59fa053",
        1600,
        900,
    ),
    Sample(
        "05-finance-ui",
        "20-sravni-kreditnyi-reiting",
        "04",
        "04.png",
        "531a18c9baf3bd63c53ee1edce03042009e8f5ade9023a015ac8a235320105ed",
        1098,
        659,
    ),
)


def matrix() -> tuple[Entry, ...]:
    return tuple(Entry(sample, model_id) for sample in SAMPLES for model_id in MODEL_IDS)


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("concurrency must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("concurrency must be at least 1")
    return parsed


def capped_concurrency(value: str, maximum: int, route: str) -> int:
    parsed = positive_int(value)
    if parsed > maximum:
        raise argparse.ArgumentTypeError(
            f"{route} concurrency must not exceed {maximum}"
        )
    return parsed


def provider_pool_limits(args: argparse.Namespace) -> ProviderPoolLimits:
    """Resolve route-local limits, retaining ``--concurrency`` as a fallback."""

    legacy_eliza = getattr(args, "concurrency", DEFAULT_ELIZA_CONCURRENCY)
    if legacy_eliza is None:
        legacy_eliza = DEFAULT_ELIZA_CONCURRENCY
    limits = ProviderPoolLimits(
        wan_22=(
            getattr(args, "wan22_concurrency", None)
            or DEFAULT_WAN_22_CONCURRENCY
        ),
        wan_27=getattr(args, "wan27_concurrency", None) or legacy_eliza,
        veo_31=getattr(args, "veo31_concurrency", None) or legacy_eliza,
    )
    maximums = ProviderPoolLimits()
    for model_id in MODEL_IDS:
        limit = limits.for_model(model_id)
        maximum = maximums.for_model(model_id)
        if limit < 1 or limit > maximum:
            raise BatchPipelineError(
                f"{model_id} concurrency must be between 1 and {maximum}"
            )
    return limits


def default_provider_operations() -> ProviderOperations:
    return ProviderOperations(
        eliza_headers=transport.eliza_headers,
        http_json=transport.http_json,
        eliza_poll=transport.eliza_poll,
        http_download=transport.http_download,
        segmind_generate=transport.segmind_generate,
        wan_generate=transport.wan_generate,
        media_probe=transport.ffprobe_media,
    )


def adapter_for(row: dict[str, Any]) -> str:
    return transport.route_for_model(row["entry"].model_id)["adapter"]


def provider_request_preview(sample: dict[str, Any], prompt: dict[str, Any]) -> dict[str, Any]:
    """Materialize the normal route, or an explicit isolated diagnostic route."""

    return transport.build_request_preview(
        sample,
        prompt,
        wan_submit_mode=WAN_SUBMIT_MODE,
    )


def provider_input_dimension_preflight(
    sample: dict[str, Any],
    model_id: str,
) -> dict[str, Any]:
    """Reject known Wan 2.7 minimum-dimension failures without a paid POST.

    Source normalization is deliberately outside this helper: changing image
    bytes or the provider URL requires a new immutable batch identity and a
    provenance-bound normalized asset.  The normal worker must never invent a
    pad/upscale transform or silently fall back after this check.
    """

    if model_id not in MODEL_IDS:
        raise BatchPipelineError(f"Unsupported provider route: {model_id}")
    width = sample.get("width")
    height = sample.get("height")
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
    ):
        raise ProviderInputDimensionError(
            f"{model_id} source dimensions must be positive integers; "
            f"got {width!r}x{height!r}",
            {
                "check": "source-dimensions",
                "model_id": model_id,
                "width": width,
                "height": height,
                "minimum_dimension_px": (
                    WAN_27_MIN_SOURCE_DIMENSION_PX
                    if model_id == WAN_27_MODEL_ID
                    else None
                ),
                "conforms": False,
                "normalization_applied": False,
            },
        )

    evidence = {
        "check": "source-dimensions",
        "model_id": model_id,
        "width": width,
        "height": height,
        "minimum_dimension_px": (
            WAN_27_MIN_SOURCE_DIMENSION_PX
            if model_id == WAN_27_MODEL_ID
            else None
        ),
        "conforms": True,
        "normalization_applied": False,
    }
    if (
        model_id == WAN_27_MODEL_ID
        and min(width, height) < WAN_27_MIN_SOURCE_DIMENSION_PX
    ):
        evidence["conforms"] = False
        raise ProviderInputDimensionError(
            f"{WAN_27_MODEL_ID} source preflight rejected {width}x{height}: "
            f"each side must be at least {WAN_27_MIN_SOURCE_DIMENSION_PX} px. "
            "Create a new immutable batch with a provenance-bound normalized "
            "source; automatic padding, upscale, retry, and fallback are disabled.",
            evidence,
        )
    return evidence


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise BatchPipelineError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BatchPipelineError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise BatchPipelineError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise BatchPipelineError(f"Path escapes workspace: {path}") from exc


def contract() -> dict[str, Any]:
    value = read_json(CONTRACT_PATH)
    if not isinstance(value, dict) or value.get("agent_id") != AGENT_ID:
        raise BatchPipelineError("Unexpected Clipmaker Lite contract")
    return value


def load_lite_job(entry: Entry, root: Path = ROOT) -> LiteJob:
    planning_run_id = entry.planning_run_id
    planning_root = (PLANNING_WORKSPACE or root).resolve()
    provenance_verifier = (
        PLANNING_PROVENANCE_VERIFIER
        or clipmaker_lite_runner.provenance_summary
    )
    try:
        summary = provenance_verifier(planning_root, planning_run_id)
    except Exception as exc:
        raise BatchPipelineError(
            f"Lite provenance failed for {planning_run_id}: {transport.safe_error(exc)}"
        ) from exc
    if summary.get("verified") is not True:
        raise BatchPipelineError(f"Lite provenance is not verified: {planning_run_id}")
    if summary.get("agent_id") != AGENT_ID or summary.get("models") != list(
        PLANNING_MODEL_IDS
    ):
        raise BatchPipelineError(
            f"Lite producer/model set mismatch: {planning_run_id}"
        )
    if summary.get("source_image_sha256") != entry.sample.source_sha256:
        raise BatchPipelineError(f"Lite source digest mismatch: {planning_run_id}")

    expected_result = (
        ARTIFACT_NAMESPACE / planning_run_id / "result.json"
    ).as_posix()
    if summary.get("result_path") != expected_result:
        raise BatchPipelineError(f"Unexpected Lite result path: {planning_run_id}")
    result_path = planning_root / expected_result
    result = read_json(result_path)
    if not isinstance(result, dict) or result.get("job_id") != planning_run_id:
        raise BatchPipelineError(f"Lite result identity mismatch: {planning_run_id}")
    producer = result.get("producer")
    if not isinstance(producer, dict) or producer.get("agent_id") != AGENT_ID:
        raise BatchPipelineError(f"Lite result producer mismatch: {planning_run_id}")
    inputs = result.get("inputs")
    source = inputs.get("source_image") if isinstance(inputs, dict) else None
    article = inputs.get("article_context") if isinstance(inputs, dict) else None
    if not isinstance(source, dict) or not isinstance(article, dict):
        raise BatchPipelineError(f"Lite result inputs are missing: {planning_run_id}")
    if source.get("path") != entry.sample.source_path or source.get("sha256") != entry.sample.source_sha256:
        raise BatchPipelineError(f"Lite source binding mismatch: {planning_run_id}")
    if article.get("path") != entry.sample.context_path:
        raise BatchPipelineError(f"Lite article binding mismatch: {planning_run_id}")

    planning_source_path = planning_root / entry.sample.source_path
    if (
        not planning_source_path.is_file()
        or sha256_file(planning_source_path) != entry.sample.source_sha256
    ):
        raise BatchPipelineError(f"Current source image mismatch: {entry.sample.source_path}")
    provider_source_path = root.resolve() / entry.sample.source_path
    if (
        provider_source_path != planning_source_path
        and (
            not provider_source_path.is_file()
            or sha256_file(provider_source_path) != entry.sample.source_sha256
        )
    ):
        raise BatchPipelineError(
            f"Provider source image mismatch: {entry.sample.source_path}"
        )
    models = result.get("models")
    if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
        raise BatchPipelineError(f"Lite result models are invalid: {planning_run_id}")
    result_model_ids = [model.get("model_id") for model in models]
    if result_model_ids != list(PLANNING_MODEL_IDS):
        raise BatchPipelineError(
            f"Lite result must contain all canonical models: {planning_run_id}"
        )
    model = models[result_model_ids.index(entry.model_id)]
    runtime = model.get("runtime")
    expected_runtime = contract()["models"][entry.model_id]["runtime"]
    if runtime != expected_runtime:
        raise BatchPipelineError(f"Lite runtime mismatch: {entry.provider_run_id}")
    execution_mode = model.get("execution_mode", "i2v")
    if execution_mode != "i2v":
        raise BatchPipelineError(
            "Deterministic-compositor Lite results must not be sent to a video provider: "
            f"{entry.provider_run_id}"
        )
    positive = model.get("positive_prompt")
    if not isinstance(positive, str) or not positive.strip():
        raise BatchPipelineError(f"Lite positive prompt is empty: {entry.provider_run_id}")
    analysis = result.get("analysis")
    structured_intent = (
        analysis.get("structured_intent") if isinstance(analysis, dict) else None
    )
    current_intent_keys = tuple(clipmaker_lite_runner.STRUCTURED_INTENT_KEYS)
    legacy_intent_key_sets = (
        (
            "editorial_meaning",
            "primary_action",
            "terminal_state",
            "semantic_invariant",
        ),
        (
            "editorial_meaning",
            "initial_state",
            "primary_action",
            "terminal_state",
            "geometry_invariant",
            "semantic_invariant",
        ),
    )
    structured_keys = set(structured_intent) if isinstance(structured_intent, dict) else set()
    if (
        not isinstance(structured_intent, dict)
        or (
            structured_keys != set(current_intent_keys)
            and all(
                structured_keys != set(legacy_keys)
                for legacy_keys in legacy_intent_key_sets
            )
        )
    ):
        raise BatchPipelineError(f"Lite structured intent is invalid: {planning_run_id}")
    intent_keys = current_intent_keys
    if structured_keys != set(current_intent_keys):
        intent_keys = next(
            legacy_keys
            for legacy_keys in legacy_intent_key_sets
            if structured_keys == set(legacy_keys)
        )
    if any(
        not isinstance(structured_intent[key], str)
        or not structured_intent[key].strip()
        for key in intent_keys
    ):
        raise BatchPipelineError(f"Lite structured intent is empty: {planning_run_id}")
    negative = model.get("negative_prompt")
    if negative is not None:
        raise BatchPipelineError(
            "PROMOPAGES-9909 baseline negative_prompt must be null: "
            f"{entry.provider_run_id}"
        )
    return LiteJob(
        entry=entry,
        structured_intent={
            key: structured_intent[key].strip()
            for key in intent_keys
        },
        execution_mode=execution_mode,
        positive_prompt=positive,
        negative_prompt=negative,
        result_path=expected_result,
        result_sha256=sha256_file(result_path),
        provenance=summary,
        runtime=runtime,
    )


def provider_sample(entry: Entry) -> dict[str, Any]:
    sample = entry.sample
    return {
        "sample_id": sample.sample_id,
        "article_slug": sample.article_slug,
        "image_id": sample.image_id,
        "image_number": sample.image_id,
        "source_path": sample.source_path,
        "source_url": PUBLIC_SOURCE_BASE + quote(sample.source_path, safe="/"),
        "sha256": sample.source_sha256,
        "width": sample.width,
        "height": sample.height,
    }


def provider_prompt(job: LiteJob) -> dict[str, Any]:
    if job.execution_mode != "i2v":
        raise BatchPipelineError(
            "Deterministic-compositor Lite results must not be materialized as provider prompts: "
            f"{job.entry.provider_run_id}"
        )
    if job.negative_prompt is not None:
        raise BatchPipelineError(
            "Clipmaker Lite negative_prompt must be null before provider submit: "
            f"{job.entry.provider_run_id}"
        )
    prompt: dict[str, Any] = {
        "sample_id": job.entry.sample.sample_id,
        "model_id": job.entry.model_id,
        "target_duration_seconds": job.runtime["duration_seconds"],
        "positive_prompt": job.positive_prompt,
        "negative_prompt": job.negative_prompt,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
    }
    if job.entry.model_id == "alibaba/wan-2.7":
        expansion = job.runtime["prompt_expansion"]
        if expansion != {"parameter": "prompt_extend", "value": True}:
            raise BatchPipelineError(f"Unexpected Wan 2.7 expansion: {job.entry.run_id}")
        prompt["prompt_extend"] = True
    return prompt


def artifact_paths(entry: Entry, root: Path = ROOT) -> dict[str, Path]:
    base = (
        root
        / "PROMOPAGES-9857/articles"
        / entry.sample.article_slug
        / "clipmaker-lite/runs"
        / BATCH_ID
        / MODEL_DIRECTORIES[entry.model_id]
    )
    stem = entry.sample.image_id
    return {
        "directory": base,
        "prompt": base / f"{stem}.prompt.json",
        "run": base / f"{stem}.run.json",
        "video": base / f"{stem}.mp4",
    }


def safe_provenance(job: LiteJob) -> dict[str, Any]:
    summary = job.provenance
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


def prompt_artifact(job: LiteJob) -> dict[str, Any]:
    prompt: dict[str, Any] = {"positive": job.positive_prompt, "negative": job.negative_prompt}
    return {
        "schema_version": 2,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "lite_run_id": job.entry.planning_run_id,
        "provider_run_id": job.entry.provider_run_id,
        "model_id": job.entry.model_id,
        "source": {
            "path": job.entry.sample.source_path,
            "sha256": job.entry.sample.source_sha256,
            "width": job.entry.sample.width,
            "height": job.entry.sample.height,
        },
        "structured_intent": job.structured_intent,
        "prompt": prompt,
        "runtime": job.runtime,
        "lite_result": {
            "path": job.result_path,
            "sha256": job.result_sha256,
            "provenance": safe_provenance(job),
        },
    }


def initial_run(job: LiteJob, paths: dict[str, Path], root: Path = ROOT) -> dict[str, Any]:
    run = transport.initial_run_artifact(
        provider_sample(job.entry), job.entry.model_id, paths, root
    )
    run.update(
        {
            "ticket": TICKET,
            "batch_id": BATCH_ID,
            "agent_id": AGENT_ID,
            "lite_run_id": job.entry.planning_run_id,
            "provider_run_id": job.entry.provider_run_id,
            "lite_result_sha256": job.result_sha256,
            "provider_may_be_active": False,
            "last_worker_failure": None,
        }
    )
    return run


def materialize_entry(entry: Entry, root: Path = ROOT) -> dict[str, Any]:
    job = load_lite_job(entry, root)
    sample = provider_sample(entry)
    prompt = provider_prompt(job)
    paths = artifact_paths(entry, root)
    paths["directory"].mkdir(parents=True, exist_ok=True)
    expected_prompt = prompt_artifact(job)
    if paths["prompt"].is_file() and read_json(paths["prompt"]) != expected_prompt:
        raise BatchPipelineError(f"Immutable batch prompt changed: {paths['prompt']}")
    if not paths["prompt"].is_file():
        transport.atomic_write_json(paths["prompt"], expected_prompt)

    expected_run = initial_run(job, paths, root)
    expected_request = provider_request_preview(sample, prompt)
    expected_fingerprint = transport.request_fingerprint(expected_request, sample)
    if not paths["run"].is_file():
        transport.atomic_write_json(paths["run"], expected_run)
    else:
        run = read_json(paths["run"])
        identity = (
            "ticket",
            "batch_id",
            "agent_id",
            "lite_run_id",
            "provider_run_id",
            "lite_result_sha256",
            "model_id",
        )
        if any(run.get(key) != expected_run.get(key) for key in identity):
            raise BatchPipelineError(f"Immutable batch run identity changed: {paths['run']}")
        if run.get("request") is not None and run.get("request") != expected_request:
            raise BatchPipelineError(f"Immutable provider request changed: {paths['run']}")
        if run.get("request") is not None and run.get("request_sha256") != expected_fingerprint:
            raise BatchPipelineError(f"Provider request fingerprint mismatch: {paths['run']}")
    return {"entry": entry, "job": job, "sample": sample, "prompt": prompt, "paths": paths}


def materialize(root: Path = ROOT) -> list[dict[str, Any]]:
    rows = [materialize_entry(entry, root) for entry in matrix()]
    write_manifest(rows, root)
    return rows


def choose_aspect_ratio(entry: Entry) -> str:
    ratios = entry_runtime(entry)["aspect_ratios"]
    if ratios == ["source"]:
        return "source"
    return transport.choose_aspect_ratio(entry.sample.width, entry.sample.height, ratios)


def entry_runtime(entry: Entry) -> dict[str, Any]:
    return contract()["models"][entry.model_id]["runtime"]


def strict_media_contract(entry: Entry, media: dict[str, Any]) -> dict[str, Any]:
    runtime = entry_runtime(entry)
    duration = float(media.get("duration_seconds") or 0)
    width = int(media.get("width") or 0)
    height = int(media.get("height") or 0)
    checks: dict[str, bool] = {
        "duration": abs(duration - float(runtime["duration_seconds"])) <= (0.15 if entry.model_id == "alibaba/wan-2.2" else 0.1),
        "audio": media.get("has_audio") is False,
    }
    if entry.model_id == "alibaba/wan-2.2":
        output_ratio = width / height if width > 0 and height > 0 else 0
        source_ratio = entry.sample.width / entry.sample.height
        checks.update(
            {
                "frames": media.get("frames") == runtime["frames"],
                "fps": abs(float(media.get("fps") or 0) - float(runtime["fps"])) <= 0.01,
                "resolution": 800_000 <= width * height <= 1_050_000,
                "aspect_ratio": output_ratio > 0 and abs(output_ratio - source_ratio) / source_ratio <= 0.03,
            }
        )
    else:
        ratio_label = choose_aspect_ratio(entry)
        left, right = ratio_label.split(":", 1)
        expected_ratio = float(left) / float(right)
        actual_ratio = width / height if width > 0 and height > 0 else 0
        checks.update(
            {
                "resolution": min(width, height) == 1080,
                "aspect_ratio": actual_ratio > 0 and abs(math.log(actual_ratio / expected_ratio)) <= 0.03,
            }
        )
    warnings = [name for name, passed in checks.items() if not passed]
    return {
        "requested": {
            "duration_seconds": runtime["duration_seconds"],
            "resolution": runtime["resolution"],
            "aspect_ratio": choose_aspect_ratio(entry),
            "generate_audio": False,
            "frames": runtime.get("frames"),
            "fps": runtime.get("fps"),
        },
        "checks": checks,
        "conforms": all(checks.values()),
        "warnings": warnings,
    }


def _persist_run(path: Path, run: dict[str, Any]) -> None:
    if isinstance(run.get("error"), str):
        run["error"] = transport.safe_error(run["error"])
    transport.atomic_write_json(path, run)


def _status_may_hold_provider_slot(status: Any) -> bool:
    return status in {"submitting", "submitted", "running", "submit-unknown"}


def _persist_worker_failure(
    row: dict[str, Any],
    status: str,
    exc: BaseException | str,
) -> WorkerResult:
    """Record coordinator-visible failure state when a worker cannot proceed."""

    error = transport.safe_error(exc)
    run_path = row.get("paths", {}).get("run")
    holds_provider_slot = False
    if isinstance(run_path, Path) and run_path.is_file():
        try:
            run = read_json(run_path)
            if isinstance(run, dict):
                prior_status = run.get("status")
                holds_provider_slot = (
                    run.get("provider_may_be_active") is True
                    or _status_may_hold_provider_slot(prior_status)
                )
                if prior_status in {"submitting", "submit-unknown"} or (
                    prior_status in {"submitted", "running"}
                    and not run.get("provider_job_id")
                ):
                    persisted_status = "submit-unknown"
                elif prior_status in {"submitted", "running"}:
                    persisted_status = "submitted"
                else:
                    persisted_status = status
                run.update(
                    {
                        "status": persisted_status,
                        "completed_at": None,
                        "provider_may_be_active": holds_provider_slot,
                        "last_worker_failure": status,
                        "error": error,
                    }
                )
                _persist_run(run_path, run)
                status = persisted_status
        except (BatchPipelineError, OSError):
            # The returned result still reports the failure even when the
            # broken run file itself is not writable.
            pass
    return _result(
        row,
        failed=True,
        status=status,
        error=error,
        holds_provider_slot=holds_provider_slot,
    )


def _result(
    row: dict[str, Any],
    *,
    failed: bool,
    status: str,
    error: str | None = None,
    holds_provider_slot: bool = False,
) -> WorkerResult:
    return WorkerResult(
        row=row,
        failed=failed,
        status=status,
        error=error,
        holds_provider_slot=holds_provider_slot,
    )


def _active_request_is_exact(
    run: dict[str, Any],
    request: dict[str, Any],
    fingerprint: str,
) -> bool:
    return (
        run.get("request") == request
        and run.get("request_sha256") == fingerprint
        and run.get("request_fingerprint_version") == transport.REQUEST_FINGERPRINT_VERSION
    )


def _is_exact_legacy_eliza_dns_pre_submit_failure(
    run: dict[str, Any],
    request: dict[str, Any],
    fingerprint: str,
    adapter: str,
) -> bool:
    """Recognize only the one historical DNS failure proven pre-submit."""

    return (
        adapter == "eliza-openrouter"
        and run.get("status") == "submit-unknown"
        and "provider_job_id" in run
        and run["provider_job_id"] is None
        and "submitted_at" in run
        and run["submitted_at"] is None
        and run.get("completed_at") is None
        and run.get("provider_may_be_active") is True
        and run.get("error") == LEGACY_ELIZA_DNS_PRE_SUBMIT_ERROR
        and _active_request_is_exact(run, request, fingerprint)
    )


def _is_exact_legacy_segmind_quota_pre_submit_failure(
    run: dict[str, Any],
    request: dict[str, Any],
    fingerprint: str,
    adapter: str,
) -> bool:
    """Recognize only the current Segmind HTTP 429 quota receipt."""

    error = run.get("error")
    return (
        adapter == "eliza-segmind"
        and run.get("status") == "submit-unknown"
        and "provider_job_id" in run
        and run["provider_job_id"] is None
        and "submitted_at" in run
        and run["submitted_at"] is None
        and run.get("completed_at") is None
        and run.get("provider_may_be_active") is True
        and fingerprint == LEGACY_SEGMIND_QUOTA_REQUEST_SHA256
        and isinstance(error, str)
        and hashlib.sha256(error.encode("utf-8")).hexdigest()
        == LEGACY_SEGMIND_QUOTA_ERROR_SHA256
        and _active_request_is_exact(run, request, fingerprint)
    )


def _verification_result(
    row: dict[str, Any],
    run: dict[str, Any],
    operations: ProviderOperations,
) -> WorkerResult:
    paths = row["paths"]
    try:
        media = operations.media_probe(paths["video"])
    except Exception as exc:
        error = transport.safe_error(exc)
        run.update(
            {
                "status": "verification-failed",
                "completed_at": transport.utc_now(),
                "media": None,
                "contract_check": None,
                "provider_may_be_active": False,
                "last_worker_failure": None,
                "error": error,
            }
        )
        _persist_run(paths["run"], run)
        return _result(row, failed=True, status="verification-failed", error=error)

    contract_check = strict_media_contract(row["entry"], media)
    status = "succeeded" if contract_check["conforms"] else "verification-failed"
    error = None
    if status == "verification-failed":
        error = "Media contract verification failed: " + ", ".join(
            contract_check["warnings"]
        )
    run.update(
        {
            "status": status,
            "completed_at": transport.utc_now(),
            "media": media,
            "contract_check": contract_check,
            "provider_may_be_active": False,
            "last_worker_failure": None,
            "error": error,
        }
    )
    _persist_run(paths["run"], run)
    return _result(
        row,
        failed=status != "succeeded",
        status=status,
        error=error,
    )


def _provider_failure(
    row: dict[str, Any],
    run: dict[str, Any],
    exc: BaseException | str,
) -> WorkerResult:
    error = transport.safe_error(exc)
    if isinstance(exc, transport.SegmindProviderTaskFailedError):
        # This typed HTTP 400 response proves that Segmind created the task and
        # that the task is already terminal, even though no success response
        # supplied the usual request ID header.
        evidence = dict(exc.evidence)
        provider_task_id = exc.provider_task_id
        run.update(
            {
                "provider_job_id": provider_task_id,
                "provider_task_id": provider_task_id,
                "provider_failure": evidence,
            }
        )
    has_provider_id = bool(run.get("provider_job_id"))
    definitive_pre_submit = isinstance(
        exc,
        (transport.PreSubmitNetworkError, transport.PreSubmitRejectedError),
    )
    terminal = isinstance(exc, transport.ProviderTerminalError) or any(
        marker in error.lower() for marker in TERMINAL_PROVIDER_FAILURE_MARKERS
    )
    if has_provider_id:
        status = "provider-failed" if terminal else "submitted"
    elif definitive_pre_submit:
        status = "failed-pre-submit"
    else:
        status = "submit-unknown" if run.get("status") == "submitting" else "failed-pre-submit"
    run.update(
        {
            "status": status,
            "completed_at": transport.utc_now() if status in {"provider-failed"} else None,
            "provider_may_be_active": _status_may_hold_provider_slot(status),
            "error": error,
        }
    )
    _persist_run(row["paths"]["run"], run)
    return _result(
        row,
        failed=True,
        status=status,
        error=error,
        holds_provider_slot=_status_may_hold_provider_slot(status),
    )


def _run_eliza_worker(
    row: dict[str, Any],
    run: dict[str, Any],
    args: argparse.Namespace,
    operations: ProviderOperations,
    *,
    resume: bool,
) -> WorkerResult:
    paths = row["paths"]
    model_id = row["entry"].model_id
    request = provider_request_preview(row["sample"], row["prompt"])
    try:
        headers = operations.eliza_headers()
    except Exception as exc:
        error = transport.safe_error(exc)
        # Credential resolution happens before POST, so this is a known
        # pre-submit failure, not an ambiguous paid submit. A resumed provider
        # identity remains durable and resumable.
        status = "submitted" if resume else "failed-pre-submit"
        run.update(
            {
                "status": status,
                "completed_at": None,
                "provider_may_be_active": _status_may_hold_provider_slot(status),
                "error": error,
            }
        )
        _persist_run(paths["run"], run)
        return _result(
            row,
            failed=True,
            status=status,
            error=error,
            holds_provider_slot=_status_may_hold_provider_slot(status),
        )

    job_id = run.get("provider_job_id") if resume else None
    if not resume:
        try:
            response = operations.http_json(
                "POST",
                transport.generation_route_url(
                    args.eliza_base_url,
                    model_id,
                    "submit",
                ),
                request,
                headers=headers,
                timeout=120,
            )
            job_id = transport.find_job_id(response)
            if not job_id:
                raise transport.PipelineError(
                    "Eliza/OpenRouter submit response did not contain a job ID"
                )
        except (
            transport.PreSubmitNetworkError,
            transport.PreSubmitRejectedError,
        ) as exc:
            # A typed DNS failure happened before a connection, or the provider
            # definitively rejected the HTTP request before creating a job.
            run.update(
                {
                    "status": "failed-pre-submit",
                    "provider_job_id": None,
                    "submitted_at": None,
                    "completed_at": None,
                    "provider_may_be_active": False,
                    "error": transport.safe_error(exc),
                }
            )
            _persist_run(paths["run"], run)
            return _result(
                row,
                failed=True,
                status="failed-pre-submit",
                error=run["error"],
                holds_provider_slot=False,
            )
        except Exception as exc:
            # Once POST starts, its outcome is ambiguous unless a provider ID was
            # durably observed. Never repeat this paid submit automatically.
            run.update(
                {
                    "status": "submit-unknown",
                    "provider_job_id": None,
                    "completed_at": None,
                    "provider_may_be_active": True,
                    "error": transport.safe_error(exc),
                }
            )
            _persist_run(paths["run"], run)
            return _result(
                row,
                failed=True,
                status="submit-unknown",
                error=run["error"],
                holds_provider_slot=True,
            )
        run.update(
            {
                "status": "submitted",
                "provider_job_id": job_id,
                "provider_session_hash": None,
                "submitted_at": transport.utc_now(),
                "provider_may_be_active": True,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)

    run.update(
        {
            "status": "running",
            "provider_may_be_active": True,
            "last_worker_failure": None,
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
            model_id=model_id,
        )
        operations.http_download(
            transport.generation_route_url(
                args.eliza_base_url,
                model_id,
                "content_template",
                job_id=str(job_id),
            ),
            paths["video"],
            headers=headers,
            timeout=600,
        )
    except Exception as exc:
        return _provider_failure(row, run, exc)
    return _verification_result(row, run, operations)


def _run_segmind_worker(
    row: dict[str, Any],
    run: dict[str, Any],
    args: argparse.Namespace,
    operations: ProviderOperations,
    root: Path,
    *,
    resume: bool,
) -> WorkerResult:
    """Run the canonical synchronous Wan 2.2 route exactly once."""

    paths = row["paths"]
    if resume:
        # A synchronous response has no poll/download endpoint. A crash after
        # the response may resume local verification only when the MP4 and the
        # provider request identity were already persisted.
        if not paths["video"].is_file():
            error = "Synchronous Eliza/Segmind response has no resumable MP4; resubmit is blocked"
            run.update(
                {
                    "status": "stale",
                    "provider_may_be_active": False,
                    "completed_at": None,
                    "error": error,
                }
            )
            _persist_run(paths["run"], run)
            return _result(row, failed=True, status="stale", error=error)
        run.update(
            {
                "status": "running",
                "provider_may_be_active": False,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
        return _verification_result(row, run, operations)

    def on_submitting(source_preflight: dict[str, Any]) -> None:
        # Revalidate the immutable Lite request after the remote source digest
        # check and immediately before the one non-idempotent paid POST.
        fresh = materialize_entry(row["entry"], root)
        fresh_request = provider_request_preview(fresh["sample"], fresh["prompt"])
        current_request = provider_request_preview(row["sample"], row["prompt"])
        if fresh_request != current_request:
            raise BatchPipelineError(
                "Eliza/Segmind provider request changed after source preflight"
            )
        run.update(
            {
                "status": "submitting",
                "provider_may_be_active": True,
                "source_preflight": source_preflight,
                "last_worker_failure": None,
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
            raise BatchPipelineError(
                "Eliza/Segmind completed without a provider request ID"
            )
        run.update(
            {
                "status": "running",
                "provider_job_id": request_id,
                "provider_session_hash": None,
                "submitted_at": transport.utc_now(),
                "provider_response": response,
                "provider_may_be_active": False,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
    except Exception as exc:
        return _provider_failure(row, run, exc)
    return _verification_result(row, run, operations)


def _run_wan_worker(
    row: dict[str, Any],
    run: dict[str, Any],
    args: argparse.Namespace,
    operations: ProviderOperations,
    root: Path,
    *,
    resume: bool,
) -> WorkerResult:
    paths = row["paths"]

    def on_submitting() -> None:
        # Upload can be slow. Revalidate the complete immutable Lite binding
        # again after upload and immediately before the paid fixed-route POST.
        fresh = materialize_entry(row["entry"], root)
        fresh_request = provider_request_preview(fresh["sample"], fresh["prompt"])
        current_request = provider_request_preview(row["sample"], row["prompt"])
        if fresh_request != current_request:
            raise BatchPipelineError("Wan provider request changed after source upload")
        run.update(
            {
                "status": "submitting",
                "provider_may_be_active": True,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)

    def on_submitted(job_id: str, session_hash: str | None) -> None:
        run.update(
            {
                "status": "submitted",
                "provider_job_id": job_id,
                "provider_session_hash": session_hash,
                "submitted_at": transport.utc_now(),
                "provider_may_be_active": True,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
        run["status"] = "running"
        _persist_run(paths["run"], run)

    if resume:
        run.update(
            {
                "status": "running",
                "provider_may_be_active": True,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
    try:
        operations.wan_generate(
            row["sample"],
            row["prompt"],
            paths["video"],
            args.wan_base_url,
            args.wan_stream_base_url,
            args.timeout,
            run if resume else None,
            on_submitted,
            allow_resubmit_after_missing_session=False,
            on_submitting=on_submitting,
            submit_mode=getattr(args, "wan_submit_mode", WAN_SUBMIT_MODE),
        )
    except Exception as exc:
        return _provider_failure(row, run, exc)
    return _verification_result(row, run, operations)


def run_provider_worker(
    original: dict[str, Any],
    args: argparse.Namespace,
    root: Path = ROOT,
    operations: ProviderOperations | None = None,
) -> WorkerResult:
    """Run one provider lifecycle without ever writing the aggregate manifest."""

    operations = operations or default_provider_operations()
    try:
        # This rechecks provenance, exact model/source/result bindings, prompt
        # artifact, and any already materialized provider request immediately
        # before a potential submit.
        row = materialize_entry(original["entry"], root)
    except Exception as exc:
        return _persist_worker_failure(original, "revalidation-failed", exc)

    paths = row["paths"]
    run = read_json(paths["run"])
    if not isinstance(run, dict):
        return _result(
            row,
            failed=True,
            status="revalidation-failed",
            error="Run artifact is not a JSON object",
        )
    request = provider_request_preview(row["sample"], row["prompt"])
    fingerprint = transport.request_fingerprint(request, row["sample"])
    status = run.get("status")
    force = bool(getattr(args, "force", False))
    dry_run = bool(getattr(args, "dry_run", False))
    adapter = adapter_for(row)

    if force:
        error = (
            "--force is disabled for native Clipmaker Lite batches; "
            "use a new batch namespace for any intentional paid rerun"
        )
        return _result(row, failed=True, status=str(status), error=error)

    legacy_recovery: str | None = None
    if _is_exact_legacy_eliza_dns_pre_submit_failure(
        run, request, fingerprint, adapter
    ):
        legacy_recovery = "reclassified-pre-submit-dns"
    elif _is_exact_legacy_segmind_quota_pre_submit_failure(
        run, request, fingerprint, adapter
    ):
        legacy_recovery = "reclassified-pre-submit-http-429"

    if legacy_recovery is not None:
        # Older http_json versions erased socket.gaierror's type and therefore
        # recorded DNS resolution as ambiguous; the Segmind transport likewise
        # used to erase a definitive quota rejection. Exact receipt bindings
        # allow only those two proven pre-submit failures to be recovered.
        run.update(
            {
                "status": "failed-pre-submit",
                "provider_may_be_active": False,
                "last_worker_failure": legacy_recovery,
            }
        )
        _persist_run(paths["run"], run)
        status = "failed-pre-submit"

    if status == "succeeded" and paths["video"].is_file() and not force:
        effective_status = effective_run_status(run)
        if effective_status == "verification-failed":
            check = run.get("contract_check")
            warnings = check.get("warnings", []) if isinstance(check, dict) else []
            error = "Recorded media contract verification failed: " + ", ".join(warnings)
            return _result(
                row,
                failed=not dry_run,
                status=effective_status,
                error=error,
            )
        return _result(row, failed=False, status="succeeded")
    if status == "succeeded" and not paths["video"].is_file() and not force:
        error = "Succeeded run has no MP4; automatic resubmit is blocked"
        run.update({"status": "stale", "provider_may_be_active": False, "error": error})
        _persist_run(paths["run"], run)
        return _result(row, failed=True, status="stale", error=error)

    if status == "submitting":
        if dry_run:
            return _result(
                row,
                failed=True,
                status="submitting",
                error="Ambiguous submitting state is preserved by dry-run",
            )
        error = "Previous submit outcome is unknown; automatic retry is blocked"
        run.update(
            {"status": "submit-unknown", "provider_may_be_active": True, "error": error}
        )
        _persist_run(paths["run"], run)
        return _result(
            row,
            failed=True,
            status="submit-unknown",
            error=error,
            holds_provider_slot=True,
        )

    if status in BLOCKED_STATUSES:
        return _result(
            row,
            failed=True,
            status=str(status),
            error=f"Run status {status!r} blocks automatic submit",
            holds_provider_slot=(
                run.get("provider_may_be_active") is True
                or _status_may_hold_provider_slot(status)
            ),
        )

    resume = status in {"submitted", "running"}
    if resume:
        provider_id = run.get("provider_job_id")
        wan_session = run.get("provider_session_hash")
        active_is_valid = bool(provider_id) and _active_request_is_exact(
            run, request, fingerprint
        )
        if adapter == "wan-demo":
            active_is_valid = active_is_valid and bool(wan_session)
        if not active_is_valid:
            error = "Active provider job is missing its exact request, fingerprint, or provider identity"
            run.update({"status": "stale", "provider_may_be_active": True, "error": error})
            _persist_run(paths["run"], run)
            return _result(
                row,
                failed=True,
                status="stale",
                error=error,
                holds_provider_slot=True,
            )

    dimension_preflight: dict[str, Any] | None = None
    if not resume:
        try:
            dimension_preflight = provider_input_dimension_preflight(
                row["sample"],
                row["entry"].model_id,
            )
        except ProviderInputDimensionError as exc:
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
                    "provider_session_hash": None,
                    "submitted_at": None,
                    "completed_at": None,
                    "provider_may_be_active": False,
                    "source_preflight": exc.evidence,
                    "last_worker_failure": "provider-input-dimension",
                    "error": error,
                }
            )
            _persist_run(paths["run"], run)
            return _result(
                row,
                failed=True,
                status="failed-pre-submit",
                error=error,
                holds_provider_slot=False,
            )

    if dry_run:
        if resume:
            return _result(row, failed=False, status=str(status))
        run.update(
            {
                "status": "dry-run",
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "provider_may_be_active": False,
                "source_preflight": dimension_preflight,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
        return _result(row, failed=False, status="dry-run")

    if not resume:
        pre_submit_status = (
            "preparing"
            if adapter in {"wan-demo", "eliza-segmind"}
            else "submitting"
        )
        run.update(
            {
                "status": pre_submit_status,
                "request": request,
                "request_sha256": fingerprint,
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "provider_may_be_active": pre_submit_status == "submitting",
                "source_preflight": dimension_preflight,
                "last_worker_failure": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)

    if adapter == "eliza-segmind":
        return _run_segmind_worker(row, run, args, operations, root, resume=resume)
    if adapter == "wan-demo":
        return _run_wan_worker(row, run, args, operations, root, resume=resume)
    if adapter == "eliza-openrouter":
        return _run_eliza_worker(row, run, args, operations, resume=resume)
    error = f"Unsupported adapter: {adapter}"
    run.update({"status": "failed-pre-submit", "error": error})
    _persist_run(paths["run"], run)
    return _result(row, failed=True, status="failed-pre-submit", error=error)


def effective_run_status(run: dict[str, Any]) -> str:
    """Expose recorded strict-contract failures without rewriting old runs."""

    status = str(run.get("status", "missing"))
    check = run.get("contract_check")
    if status == "succeeded" and isinstance(check, dict) and check.get("conforms") is False:
        return "verification-failed"
    return status


def complete_media_is_accepted(
    status: Any,
    contract_check: Any,
    *,
    allow_contract_warnings: bool,
) -> bool:
    """Accept only a conforming success or an explicitly allowed raw MP4.

    This is an acceptance policy for verification, not a status rewrite.  A
    provider file that violates the requested media contract remains
    ``verification-failed`` with ``conforms: false`` in every receipt and
    manifest.
    """

    if not isinstance(contract_check, dict):
        return False
    conforms = contract_check.get("conforms")
    if status == "succeeded" and conforms is True:
        return True
    return (
        allow_contract_warnings
        and status in {"succeeded", "verification-failed"}
        and conforms is False
    )


def manifest_document(
    rows: list[dict[str, Any]],
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    conforming = 0
    for row in rows:
        paths = row["paths"]
        run = read_json(paths["run"]) if paths["run"].is_file() else {"status": "missing"}
        recorded_status = run.get("status", "missing")
        status = effective_run_status(run)
        summary[status] = summary.get(status, 0) + 1
        check = run.get("contract_check")
        if isinstance(check, dict) and check.get("conforms") is True:
            conforming += 1
        outputs.append(
            {
                "lite_run_id": row["entry"].planning_run_id,
                "provider_run_id": row["entry"].provider_run_id,
                "sample_id": row["entry"].sample.sample_id,
                "article_slug": row["entry"].sample.article_slug,
                "source_path": row["entry"].sample.source_path,
                "model_id": row["entry"].model_id,
                "status": status,
                "recorded_status": recorded_status,
                "provider_may_be_active": run.get("provider_may_be_active"),
                "prompt_path": relative(paths["prompt"], root),
                "run_path": relative(paths["run"], root),
                "video_path": relative(paths["video"], root),
                "media": run.get("media"),
                "contract_check": check,
                "error": (
                    run.get("error")
                    or (
                        "Recorded media contract verification failed: "
                        + ", ".join(check.get("warnings", []))
                        if status == "verification-failed" and isinstance(check, dict)
                        else None
                    )
                ),
            }
        )
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "expected_outputs": len(matrix()),
        "summary": summary,
        "conforming_outputs": conforming,
        "outputs": outputs,
    }


def write_manifest(rows: list[dict[str, Any]], root: Path = ROOT) -> None:
    path = root / MANIFEST_PATH
    if path.is_file():
        existing = read_json(path)
        updated_at = existing.get("updated_at") if isinstance(existing, dict) else None
        if isinstance(updated_at, str) and existing == manifest_document(
            rows,
            root,
            updated_at,
        ):
            return
    transport.atomic_write_json(path, manifest_document(rows, root))


def select_rows(rows: list[dict[str, Any]], run_ids: Iterable[str], models: Iterable[str]) -> list[dict[str, Any]]:
    run_ids = list(run_ids)
    models = list(models)
    known_runs = {entry.run_id for entry in matrix()}
    unknown_runs = set(run_ids) - known_runs
    unknown_models = set(models) - set(MODEL_IDS)
    if unknown_runs:
        raise BatchPipelineError(f"Unknown run IDs: {', '.join(sorted(unknown_runs))}")
    if unknown_models:
        raise BatchPipelineError(f"Unknown models: {', '.join(sorted(unknown_models))}")
    return [
        row
        for row in rows
        if (not run_ids or row["entry"].run_id in run_ids)
        and (not models or row["entry"].model_id in models)
    ]


Worker = Callable[[dict[str, Any]], WorkerResult]
CompletionHandler = Callable[[WorkerResult], None]


def _uncaught_worker_failure(row: dict[str, Any], exc: BaseException) -> WorkerResult:
    return _persist_worker_failure(row, "worker-failed", exc)


def run_serial_queue(
    rows: Iterable[dict[str, Any]],
    worker: Worker,
    on_complete: CompletionHandler,
    *,
    fail_fast: bool,
) -> int:
    """Run the Wan queue one item at a time and report from one coordinator."""

    failures = 0
    for row in rows:
        try:
            result = worker(row)
        except Exception as exc:  # Keep unrelated jobs resumable by default.
            result = _uncaught_worker_failure(row, exc)
        on_complete(result)
        if result.failed:
            failures += 1
            if fail_fast:
                break
        if result.holds_provider_slot:
            # Wan has a fixed capacity of one. An unresolved prior job must
            # block every later Wan submit in this launch.
            break
    return failures


def run_matrix_order_serial(
    rows: Iterable[dict[str, Any]],
    worker: Worker,
    on_complete: CompletionHandler,
    *,
    fail_fast: bool,
) -> int:
    """Preserve the legacy matrix order when Eliza concurrency is one."""

    failures = 0
    blocked_routes: set[str] = set()
    for row in rows:
        route = "wan" if row["entry"].model_id == WAN_MODEL_ID else "eliza"
        if route in blocked_routes:
            continue
        try:
            result = worker(row)
        except Exception as exc:
            result = _uncaught_worker_failure(row, exc)
        on_complete(result)
        if result.failed:
            failures += 1
        if result.holds_provider_slot:
            blocked_routes.add(route)
        if result.failed and fail_fast:
            break
    return failures


def run_bounded_queue(
    rows: Iterable[dict[str, Any]],
    concurrency: int,
    worker: Worker,
    on_complete: CompletionHandler,
    *,
    fail_fast: bool,
) -> int:
    """Run a rolling global Eliza window without eagerly queuing every job."""

    if concurrency < 1:
        raise BatchPipelineError("Eliza/OpenRouter concurrency must be at least 1")
    iterator = iter(rows)
    pending: dict[Future[WorkerResult], dict[str, Any]] = {}
    failures = 0
    stop_scheduling = False
    reserved_slots = 0

    def fill(executor: ThreadPoolExecutor) -> None:
        while (
            not stop_scheduling
            and len(pending) + reserved_slots < concurrency
        ):
            try:
                row = next(iterator)
            except StopIteration:
                return
            pending[executor.submit(worker, row)] = row

    with ThreadPoolExecutor(
        max_workers=concurrency,
        thread_name_prefix="clipmaker-lite-eliza",
    ) as executor:
        fill(executor)
        while pending:
            done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            completed: list[WorkerResult] = []
            batch_failed = False
            for future in done:
                original = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:  # Keep other workers alive by default.
                    result = _uncaught_worker_failure(original, exc)
                completed.append(result)
                batch_failed = batch_failed or result.failed

            # Only this coordinator thread writes the aggregate manifest.
            for result in completed:
                on_complete(result)
                if result.failed:
                    failures += 1
                if result.holds_provider_slot:
                    # An ambiguous or transient outcome may still represent a
                    # live paid job. Keep its capacity reserved for the rest of
                    # this launch instead of risking a fourth active job.
                    reserved_slots += 1
            if batch_failed and fail_fast:
                stop_scheduling = True
            fill(executor)
    return failures


def run_provider_pools(
    rows: Iterable[dict[str, Any]],
    limits: ProviderPoolLimits,
    worker: Worker,
    on_complete: CompletionHandler,
    *,
    fail_fast: bool,
) -> int:
    """Run Wan 2.2, Wan 2.7 and Veo in independent rolling windows.

    Provider workers run concurrently, but this function remains the only
    coordinator: completion callbacks (and therefore aggregate-manifest
    writes) always happen on the thread that called this function.  An
    ambiguous result reserves capacity only in the route that produced it.
    """

    maximums = ProviderPoolLimits()
    route_rows: dict[str, list[dict[str, Any]]] = {
        model_id: [] for model_id in MODEL_IDS
    }
    for row in rows:
        model_id = row["entry"].model_id
        if model_id not in route_rows:
            raise BatchPipelineError(f"Unsupported provider route: {model_id}")
        route_rows[model_id].append(row)
    for model_id in MODEL_IDS:
        limit = limits.for_model(model_id)
        maximum = maximums.for_model(model_id)
        if limit < 1 or limit > maximum:
            raise BatchPipelineError(
                f"{model_id} concurrency must be between 1 and {maximum}"
            )

    states: dict[str, dict[str, Any]] = {
        model_id: {
            "iterator": iter(route_rows[model_id]),
            "active": 0,
            "reserved": 0,
            "exhausted": False,
        }
        for model_id in MODEL_IDS
    }
    pending: dict[Future[WorkerResult], tuple[str, dict[str, Any], int]] = {}
    failures = 0
    stop_scheduling = False
    sequence = 0

    def fill_route(executor: ThreadPoolExecutor, model_id: str) -> None:
        nonlocal sequence
        state = states[model_id]
        capacity = limits.for_model(model_id)
        while (
            not stop_scheduling
            and not state["exhausted"]
            and state["active"] + state["reserved"] < capacity
        ):
            try:
                row = next(state["iterator"])
            except StopIteration:
                state["exhausted"] = True
                return
            future = executor.submit(worker, row)
            pending[future] = (model_id, row, sequence)
            sequence += 1
            state["active"] += 1

    with ThreadPoolExecutor(
        max_workers=limits.total,
        thread_name_prefix="clipmaker-lite-provider",
    ) as executor:
        for model_id in MODEL_IDS:
            fill_route(executor, model_id)
        while pending:
            done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            completed: list[tuple[int, str, WorkerResult]] = []
            batch_failed = False
            for future in done:
                model_id, original, submitted_order = pending.pop(future)
                states[model_id]["active"] -= 1
                try:
                    result = future.result()
                except Exception as exc:  # Keep unrelated routes resumable.
                    result = _uncaught_worker_failure(original, exc)
                completed.append((submitted_order, model_id, result))
                batch_failed = batch_failed or result.failed

            # A set of futures has no stable order. Preserve submission order
            # within each observed completion batch for deterministic receipts.
            for _, model_id, result in sorted(completed):
                on_complete(result)
                if result.failed:
                    failures += 1
                if result.holds_provider_slot:
                    states[model_id]["reserved"] += 1
            if batch_failed and fail_fast:
                # Existing paid jobs still complete; no new provider submits
                # are admitted in any route after the first observed failure.
                stop_scheduling = True
            if not stop_scheduling:
                for model_id in MODEL_IDS:
                    fill_route(executor, model_id)
    return failures


def _provider_queue_priority(row: dict[str, Any]) -> int:
    """Account for ambiguous/active jobs before any new paid submit."""

    path = row["paths"]["run"]
    if not path.is_file():
        return 2
    try:
        run = read_json(path)
    except (BatchPipelineError, AttributeError):
        return 2
    status = run.get("status")
    if status in {"submitting", "submit-unknown"}:
        return 0
    if (
        status in {"submitted", "running"}
        or run.get("provider_may_be_active") is True
    ):
        return 1
    return 2


def _row_has_unresolved_provider(row: dict[str, Any]) -> bool:
    if row["entry"].run_id in SCHEDULING_EXCLUDED_RUN_IDS:
        return False
    path = row["paths"]["run"]
    if not path.is_file():
        return False
    try:
        run = read_json(path)
    except (BatchPipelineError, AttributeError):
        return False
    return (
        _status_may_hold_provider_slot(run.get("status"))
        or run.get("provider_may_be_active") is True
    )


def run_selected(
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
    root: Path = ROOT,
    operations: ProviderOperations | None = None,
) -> int:
    if getattr(args, "force", False):
        raise BatchPipelineError(
            "--force is disabled for native Clipmaker Lite batches; "
            "use a new batch namespace for any intentional paid rerun"
        )
    if not args.dry_run and not args.allow_external_processing:
        raise BatchPipelineError(
            "Real generation requires --allow-external-processing because images and Lite prompts are sent to providers"
        )
    selected = select_rows(rows, args.run_id, args.model)
    known_run_ids = {row["entry"].run_id for row in rows}
    unknown_exclusions = set(SCHEDULING_EXCLUDED_RUN_IDS) - known_run_ids
    if unknown_exclusions:
        raise BatchPipelineError(
            "Unknown scheduling exclusions: "
            + ", ".join(sorted(unknown_exclusions))
        )
    selected = [
        row
        for row in selected
        if row["entry"].run_id not in SCHEDULING_EXCLUDED_RUN_IDS
    ]
    if not selected:
        raise BatchPipelineError("Filters selected no executable batch entries")
    selected_entries = {row["entry"] for row in selected}
    unresolved = [
        row
        for row in rows
        if row["entry"] not in selected_entries and _row_has_unresolved_provider(row)
    ]
    if unresolved:
        print(
            f"including {len(unresolved)} unresolved provider job(s) outside filters",
            flush=True,
        )
        selected = unresolved + selected

    all_rows = rows
    operations = operations or default_provider_operations()
    completed = 0

    def worker(row: dict[str, Any]) -> WorkerResult:
        return run_provider_worker(row, args, root, operations)

    def on_complete(result: WorkerResult) -> None:
        nonlocal completed
        completed += 1
        for position, existing in enumerate(all_rows):
            if existing["entry"] == result.row["entry"]:
                all_rows[position] = result.row
                break
        write_manifest(all_rows, root)
        detail = f": {result.error}" if result.error else ""
        stream = sys.stderr if result.failed else sys.stdout
        print(
            f"batch [{completed}/{len(selected)}] {result.row['entry'].run_id} "
            f"-> {result.status}{detail}",
            file=stream,
            flush=True,
        )

    supported_models = {WAN_MODEL_ID, *ELIZA_MODEL_IDS}
    unsupported = [
        row for row in selected if row["entry"].model_id not in supported_models
    ]
    if unsupported:
        raise BatchPipelineError(
            "Selected rows contain unsupported model routes: "
            + ", ".join(row["entry"].model_id for row in unsupported)
        )

    # Stable sort promotes resumable jobs within their own provider route;
    # new jobs retain matrix order.  The three routes start together.
    selected.sort(
        key=lambda row: (
            MODEL_IDS.index(row["entry"].model_id),
            _provider_queue_priority(row),
        )
    )
    return run_provider_pools(
        selected,
        provider_pool_limits(args),
        worker,
        on_complete,
        fail_fast=args.fail_fast,
    )


def verify(
    root: Path = ROOT,
    allow_incomplete: bool = False,
    allow_contract_warnings: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    accepted_complete = 0
    for entry in matrix():
        try:
            row = materialize_entry(entry, root)
        except (BatchPipelineError, transport.PipelineError) as exc:
            errors.append(str(exc))
            continue
        rows.append(row)
        paths = row["paths"]
        run = read_json(paths["run"])
        if read_json(paths["prompt"]) != prompt_artifact(row["job"]):
            errors.append(f"Prompt differs from verified Lite result: {entry.run_id}")
        expected_request = provider_request_preview(row["sample"], row["prompt"])
        expected_fingerprint = transport.request_fingerprint(expected_request, row["sample"])
        if run.get("request") is not None and run.get("request") != expected_request:
            errors.append(f"Provider request mismatch: {entry.run_id}")
        if run.get("request") is not None and run.get("request_sha256") != expected_fingerprint:
            errors.append(f"Provider request fingerprint mismatch: {entry.run_id}")
        status = run.get("status")
        if status not in {"succeeded", "verification-failed"}:
            if not allow_incomplete:
                errors.append(f"Not succeeded ({status}): {entry.run_id}")
            continue
        if not paths["video"].is_file():
            if status == "succeeded" or not allow_incomplete:
                errors.append(f"{status} run has no MP4: {entry.run_id}")
            continue
        try:
            media = transport.ffprobe_media(paths["video"])
        except transport.PipelineError as exc:
            errors.append(str(exc))
            continue
        recorded_media_matches = run.get("media") == media
        if not recorded_media_matches:
            errors.append(f"Recorded media mismatch: {entry.run_id}")
        expected_contract = strict_media_contract(entry, media)
        recorded_contract_matches = run.get("contract_check") == expected_contract
        if not recorded_contract_matches:
            errors.append(f"Recorded contract check mismatch: {entry.run_id}")
        if status == "verification-failed" and expected_contract["conforms"]:
            errors.append(f"Failed verification now conforms: {entry.run_id}")
        elif complete_media_is_accepted(
            status,
            expected_contract,
            allow_contract_warnings=allow_contract_warnings,
        ):
            if recorded_media_matches and recorded_contract_matches:
                accepted_complete += 1
        elif not allow_incomplete and not expected_contract["conforms"]:
            errors.append(
                f"Media contract failed ({', '.join(expected_contract['warnings'])}): {entry.run_id}"
            )
        elif not allow_incomplete:
            errors.append(f"Not succeeded ({status}): {entry.run_id}")
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.is_file():
        errors.append(f"Missing batch manifest: {MANIFEST_PATH}")
    else:
        manifest = read_json(manifest_path)
        updated_at = manifest.get("updated_at") if isinstance(manifest, dict) else None
        if not isinstance(updated_at, str) or manifest != manifest_document(rows, root, updated_at):
            errors.append("Batch manifest does not match the materialized run artifacts")
    if not allow_incomplete and accepted_complete != len(matrix()):
        errors.append(
            f"Expected {len(matrix())} accepted complete outputs, got {accepted_complete}"
        )
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "plan",
        help="verify 5 shared Lite results and materialize 15 provider entries",
    )
    run = subparsers.add_parser("run", help="generate or resume the native 5x3 batch")
    run.add_argument(
        "--run-id",
        action="append",
        default=[],
        help="provider run ID; repeatable",
    )
    run.add_argument("--model", action="append", default=[])
    run.add_argument("--dry-run", action="store_true")
    run.add_argument(
        "--force",
        action="store_true",
        help="disabled for Lite batches; intentional reruns require a new batch namespace",
    )
    run.add_argument("--fail-fast", action="store_true")
    run.add_argument(
        "--concurrency",
        type=lambda value: capped_concurrency(
            value,
            DEFAULT_ELIZA_CONCURRENCY,
            "Eliza route",
        ),
        default=DEFAULT_ELIZA_CONCURRENCY,
        metavar="N",
        help=(
            "deprecated shared fallback for each Eliza route (default: 3); "
            "use --wan27-concurrency and --veo31-concurrency for independent limits"
        ),
    )
    run.add_argument(
        "--wan22-concurrency",
        type=lambda value: capped_concurrency(
            value,
            DEFAULT_WAN_22_CONCURRENCY,
            "Wan 2.2",
        ),
        default=None,
        metavar="N",
        help="Wan 2.2 / Gradio route limit (default and maximum: 1)",
    )
    run.add_argument(
        "--wan27-concurrency",
        type=lambda value: capped_concurrency(
            value,
            DEFAULT_WAN_27_CONCURRENCY,
            "Wan 2.7",
        ),
        default=None,
        metavar="N",
        help="Wan 2.7 / atlas-cloud route limit (default and maximum: 3)",
    )
    run.add_argument(
        "--veo31-concurrency",
        type=lambda value: capped_concurrency(
            value,
            DEFAULT_VEO_31_CONCURRENCY,
            "Veo 3.1 Lite",
        ),
        default=None,
        metavar="N",
        help="Veo 3.1 Lite / google-vertex route limit (default and maximum: 3)",
    )
    run.add_argument("--timeout", type=int, default=1800)
    run.add_argument("--poll-interval", type=float, default=10.0)
    run.add_argument("--allow-external-processing", action="store_true")
    run.add_argument(
        "--segmind-base-url",
        default=os.environ.get(
            "ELIZA_SEGMIND_BASE_URL",
            transport.DEFAULT_SEGMIND_BASE_URL,
        ),
        help="Wan 2.2 / Segmind base URL (normal route is fixed by the registry)",
    )
    # Retained only for isolated historical Gradio wrappers. The canonical
    # alibaba/wan-2.2 adapter never reads these options.
    run.add_argument(
        "--wan-base-url",
        default=os.environ.get("WAN_DEMO_BASE_URL"),
        help="historical Gradio wrapper only; canonical Wan 2.2 does not use it",
    )
    run.add_argument(
        "--wan-stream-base-url",
        default=os.environ.get("WAN_DEMO_STREAM_BASE_URL"),
        help="historical Gradio wrapper only; canonical Wan 2.2 does not use it",
    )
    run.add_argument(
        "--eliza-base-url",
        default=os.environ.get("ELIZA_OPENROUTER_BASE_URL", transport.DEFAULT_ELIZA_BASE_URL),
    )
    verify_parser = subparsers.add_parser("verify", help="verify provenance and all generated MP4s")
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    verify_parser.add_argument(
        "--allow-contract-warnings",
        action="store_true",
        help="accept complete provider files while retaining runtime deviations in the manifest",
    )
    return parser


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            rows = materialize(root)
            print(
                f"PASS: materialized {len(rows)} provider jobs from "
                f"{len(SAMPLES)} verified Lite planning runs for {BATCH_ID}"
            )
            return 0
        if args.command == "run":
            rows = materialize(root)
            failures = run_selected(rows, args, root)
            write_manifest(rows, root)
            if failures:
                print(f"FAIL: {failures} generation(s) failed", file=sys.stderr)
                return 1
            if args.dry_run:
                print("PASS: selected native Lite requests validated; no provider calls")
            else:
                print("PASS: selected native Lite generations completed")
            return 0
        if args.command == "verify":
            passed, errors = verify(root, args.allow_incomplete, args.allow_contract_warnings)
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: native Clipmaker Lite 5x3 batch is valid")
            return 0
        raise BatchPipelineError(f"Unknown command: {args.command}")
    except (BatchPipelineError, transport.PipelineError, OSError) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
