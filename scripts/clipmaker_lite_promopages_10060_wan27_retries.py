#!/usr/bin/env python3
"""Run three immutable, untuned Wan 2.7 retries for PROMOPAGES-10060 image 03.

The experiment reuses the exact historical Clipmaker Lite plan and provider
request for ``09-m2-risk-vtorichki/03``.  It creates three new provider
identities, submits each identity at most once, and records every attempt as an
explicit retry of the original provider run.  No prompt, seed, image, runtime,
route, or provider option is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
MODEL_ID = "alibaba/wan-2.7"
MODEL_IDS = (MODEL_ID,)
ORIGINAL_MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)

EXPERIMENT_ID = (
    "promopages-10060-m2-risk-vtorichki-03-wan27-retries-20260814-v1"
)
PROVIDER_BATCH_ID = f"{EXPERIMENT_ID}-provider"
EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / EXPERIMENT_ID
INVENTORY_PATH = EXPERIMENT_ROOT / "inventory.json"
GENERATION_MANIFEST_PATH = EXPERIMENT_ROOT / "generation-manifest.json"
EXPERIMENT_MANIFEST_PATH = EXPERIMENT_ROOT / "experiment-manifest.json"

PLANNING_RUN_ID = (
    "promopages-10060-lite-all-images-20260805-v2-"
    "09-m2-risk-vtorichki-03"
)
ORIGINAL_PROVIDER_RUN_ID = f"{PLANNING_RUN_ID}-wan-2-7"
SOURCE_PATH = Path(
    "PROMOPAGES-9857/PROMOPAGES-10060/articles/"
    "09-m2-risk-vtorichki/03.jpeg"
)
CONTEXT_PATH = Path(
    "PROMOPAGES-9884/PROMOPAGES-10060/articles/"
    "09-m2-risk-vtorichki/content.json"
)
PLANNING_RESULT_PATH = (
    Path("artifacts/clipmaker-lite/v1") / PLANNING_RUN_ID / "result.json"
)
ORIGINAL_PROMPT_PATH = Path(
    "clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/"
    "videos/09-m2-risk-vtorichki/wan-2.7/03.prompt.json"
)
ORIGINAL_RUN_PATH = ORIGINAL_PROMPT_PATH.with_name("03.run.json")
ORIGINAL_VIDEO_PATH = ORIGINAL_PROMPT_PATH.with_name("03.mp4")
CURRENT_CONTRACT_PATH = Path("docs/agents/clipmaker-lite/contract.json")

SOURCE_URL = (
    "https://avatars.mds.yandex.net/get-promoarticles/4956602/"
    "pub_6a1046c4295ec11571710766_6a1046e84c8868120c0a67cb/orig"
)
SOURCE_SHA256 = "93f3715f7525b61e25d5ffc588929d04103652ab6991f07a5b869874338a7071"
CONTEXT_SHA256 = "d3c0fdd67223e79a3b078b758c7e6d66fbb50ed9c501ebd9d9e300dd2428d2e1"
SOURCE_WIDTH = 1500
SOURCE_HEIGHT = 1001

POSITIVE_PROMPT = (
    "Fixed shot as the man’s attention settles on the laptop, his expression "
    "becoming more intent. End with him quietly focused on the screen, "
    "maintaining a concerned, analytical mood."
)
EXPECTED_REQUEST: dict[str, Any] = {
    "model": MODEL_ID,
    "prompt": POSITIVE_PROMPT,
    "duration": 5,
    "resolution": "1080p",
    "aspect_ratio": "4:3",
    "seed": 9681,
    "generate_audio": False,
    "frame_images": [
        {
            "type": "image_url",
            "image_url": {"url": SOURCE_URL},
            "frame_type": "first_frame",
        }
    ],
    "provider": {
        "options": {"atlas-cloud": {"parameters": {"prompt_extend": True}}}
    },
}
EXPECTED_REQUEST_BODY_SHA256 = (
    "d07dd3824a48a4130f9bdfda40ab7adb058fca41f33814031e2e7cd39f76e934"
)
EXPECTED_REQUEST_FINGERPRINT = (
    "08db01dfbcba65a9ff27c31bf1a8b69057ad1875a9d615a9ccee685e1f0e87aa"
)

HISTORICAL_COMMIT = "ca9ba5cb53c8d6290dcc350c1b3b28da5e1fadac"
HISTORICAL_CONTRACT_VERSION = "2.0.6"
EXPECTED_HISTORICAL_PROVENANCE: dict[str, Any] = {
    "verified": True,
    "verification_scope": "trusted-workspace-route",
    "cryptographically_signed": False,
    "result_path": PLANNING_RESULT_PATH.as_posix(),
    "agent_id": AGENT_ID,
    "contract_version": HISTORICAL_CONTRACT_VERSION,
    "contract_fingerprint": (
        "sha256:e6925c11163c02899ea6001ee23bd8b70f5184f0aa6d7dc477ee763e7c4ed51a"
    ),
    "instruction_bundle_sha256": (
        "688db98f5cf83306f6ff966a531a3bc4c544259c98cc9f0ecde5fd70d3a7ec63"
    ),
    "runner": {
        "path": "scripts/clipmaker_lite_runner.py",
        "sha256": (
            "c12e836ee5f3105397aa9e9430ff0850880e12d884a14752786a4b870b3d1d1d"
        ),
    },
    "execution": {
        "executor_id": "codex-exec",
        "binary_path": "/Applications/ChatGPT.app/Contents/Resources/codex",
        "binary_sha256": (
            "d96ae1ca1ff6fc8587842fa04c92d3ee4d31651a811c2f89b65fcfd9c28473e2"
        ),
        "version": "codex-cli 0.146.0-alpha.9.2",
        "requested_model": "gpt-5.6-terra",
        "thread_id": "019fcef7-d0ce-7b12-9aae-9a3488078969",
    },
    "models": list(ORIGINAL_MODEL_IDS),
    "source_image_sha256": SOURCE_SHA256,
    "article_context_sha256": CONTEXT_SHA256,
}

BASE_RECEIPTS_SHA256: dict[str, str] = {
    SOURCE_PATH.as_posix(): SOURCE_SHA256,
    CONTEXT_PATH.as_posix(): CONTEXT_SHA256,
    (
        f"artifacts/clipmaker-lite/v1/{PLANNING_RUN_ID}/job.json"
    ): "c52a7a92a8f69aede0132bb83bc2316d8aed1cf94ca03bb17108e7e953d1e709",
    (
        f"artifacts/clipmaker-lite/v1/{PLANNING_RUN_ID}/instruction-bundle.md"
    ): "688db98f5cf83306f6ff966a531a3bc4c544259c98cc9f0ecde5fd70d3a7ec63",
    (
        f"artifacts/clipmaker-lite/v1/{PLANNING_RUN_ID}/draft.json"
    ): "9b9099e807b17ac07c4716b68030977ed368d6ae27b25612b2bf646bf61be66a",
    (
        f"artifacts/clipmaker-lite/v1/{PLANNING_RUN_ID}/execution.json"
    ): "8a327917972b4bcf2fa6c15d237609d58d67b993db3dbb93e891b6d77fc7148e",
    PLANNING_RESULT_PATH.as_posix(): (
        "2e02fbbe22d472503c3626ca667c1f165e5e4792daf78fffb793a9afa5269894"
    ),
    ORIGINAL_PROMPT_PATH.as_posix(): (
        "8e9e32727b1e31d95f525a6f04b4ddc63df361eab4e905e8f0f5ebe3b59e3fb1"
    ),
    ORIGINAL_RUN_PATH.as_posix(): (
        "13c4a860bc15b9b93f04db35054b6f582cfa273a4e9ddcfb80e5c354e0ca479f"
    ),
    ORIGINAL_VIDEO_PATH.as_posix(): (
        "2a08bc9f1febda3c7c60028a66bf91ec486d4af03a48fadebcc16506c6fd9dcb"
    ),
}

RETRY_COUNT = 3
RETRY_RESERVED_USD = Decimal("0.35")
AGGREGATE_RESERVED_USD = Decimal("1.05")
HARD_BUDGET_CAP_USD = Decimal("1.05")


class RetryExperimentError(RuntimeError):
    """A fail-closed error for this exact qualitative retry experiment."""


@dataclass(frozen=True)
class RetrySample(native.Sample):
    attempt_index: int
    variant_id: str
    historical_planning_run_id: str

    @property
    def source_path(self) -> str:
        return SOURCE_PATH.as_posix()

    @property
    def context_path(self) -> str:
        return CONTEXT_PATH.as_posix()

    @property
    def planning_run_id(self) -> str:
        return self.historical_planning_run_id


SAMPLES = tuple(
    RetrySample(
        sample_id=f"09-m2-risk-vtorichki-03-retry-{index:02d}",
        article_slug="09-m2-risk-vtorichki",
        image_id="03",
        filename="03.jpeg",
        source_sha256=SOURCE_SHA256,
        width=SOURCE_WIDTH,
        height=SOURCE_HEIGHT,
        attempt_index=index,
        variant_id=f"retry-{index:02d}",
        historical_planning_run_id=PLANNING_RUN_ID,
    )
    for index in range(1, RETRY_COUNT + 1)
)
ENTRIES = tuple(native.Entry(sample, MODEL_ID) for sample in SAMPLES)

_NATIVE_PROVIDER_REQUEST_PREVIEW = native.provider_request_preview
_NATIVE_PROMPT_ARTIFACT = native.prompt_artifact
_NATIVE_INITIAL_RUN = native.initial_run


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RetryExperimentError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RetryExperimentError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RetryExperimentError(f"Cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_extract(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, "r") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            try:
                target.relative_to(destination.resolve())
            except ValueError as exc:
                raise RetryExperimentError(
                    f"Historical archive contains an unsafe path: {member.name}"
                ) from exc
        archive.extractall(destination)  # noqa: S202 - trusted, path-checked git archive


@lru_cache(maxsize=4)
def _historical_provenance_cached(root_value: str) -> dict[str, Any]:
    root = Path(root_value).resolve()
    with tempfile.TemporaryDirectory(prefix="clipmaker-lite-2.0.6-") as directory:
        overlay = Path(directory)
        archive_path = overlay / "historical-lite.tar"
        command = [
            "git",
            "archive",
            "--format=tar",
            f"--output={archive_path}",
            HISTORICAL_COMMIT,
            "scripts/clipmaker_lite_runner.py",
            "docs/agents/clipmaker-lite",
        ]
        try:
            subprocess.run(
                command,
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RetryExperimentError(
                "Cannot restore the exact historical Clipmaker Lite verifier"
            ) from exc
        _safe_extract(archive_path, overlay)

        for relative_path in (SOURCE_PATH, CONTEXT_PATH):
            source = root / relative_path
            destination = overlay / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        source_artifacts = root / PLANNING_RESULT_PATH.parent
        destination_artifacts = overlay / PLANNING_RESULT_PATH.parent
        destination_artifacts.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_artifacts, destination_artifacts)

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/clipmaker_lite_runner.py",
                    "provenance",
                    "--run-id",
                    PLANNING_RUN_ID,
                ],
                cwd=overlay,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            summary = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise RetryExperimentError(
                "Historical Clipmaker Lite provenance verification failed"
            ) from exc
    if summary != EXPECTED_HISTORICAL_PROVENANCE:
        raise RetryExperimentError(
            "Historical Clipmaker Lite provenance differs from the verified receipt"
        )
    return summary


def historical_provenance_summary(root: Path = ROOT) -> dict[str, Any]:
    return dict(_historical_provenance_cached(str(root.resolve())))


def validate_base_receipts(root: Path = ROOT) -> dict[str, str]:
    observed: dict[str, str] = {}
    for relative_path, expected in BASE_RECEIPTS_SHA256.items():
        path = root / relative_path
        if not path.is_file() or path.is_symlink():
            raise RetryExperimentError(f"Immutable base receipt is missing: {relative_path}")
        actual = sha256_file(path)
        if actual != expected:
            raise RetryExperimentError(f"Immutable base receipt changed: {relative_path}")
        observed[relative_path] = actual
    historical_provenance_summary(root)

    original_run = read_json(root / ORIGINAL_RUN_PATH)
    if (
        original_run.get("provider_run_id") != ORIGINAL_PROVIDER_RUN_ID
        or original_run.get("model_id") != MODEL_ID
        or original_run.get("status") != "verification-failed"
        or original_run.get("request") != EXPECTED_REQUEST
        or original_run.get("request_sha256") != EXPECTED_REQUEST_FINGERPRINT
        or original_run.get("media", {}).get("sha256")
        != BASE_RECEIPTS_SHA256[ORIGINAL_VIDEO_PATH.as_posix()]
    ):
        raise RetryExperimentError("Original Wan 2.7 provider receipt changed")
    if sha256_json(original_run["request"]) != EXPECTED_REQUEST_BODY_SHA256:
        raise RetryExperimentError("Original Wan 2.7 request body changed")
    return observed


def validate_route() -> dict[str, Any]:
    route = transport.route_for_model(MODEL_ID)
    if (
        route.get("adapter") != "eliza-openrouter"
        or route.get("transport") != "eliza-video-jobs"
        or route.get("provider_key") != "atlas-cloud"
        or route.get("capacity") != 3
        or route.get("paths")
        != {
            "submit": "/videos",
            "status_template": "/videos/{job_id}",
            "content_template": "/videos/{job_id}/content?index=0",
        }
    ):
        raise RetryExperimentError("The exact local Wan 2.7 generation route changed")
    return route


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        budget = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise RetryExperimentError(f"Invalid USD budget: {value!r}") from exc
    if budget != HARD_BUDGET_CAP_USD:
        raise RetryExperimentError(
            f"This fixed three-retry experiment requires exactly ${HARD_BUDGET_CAP_USD:.2f}"
        )
    return budget


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RetryExperimentError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _entry_for_sample(sample: RetrySample) -> native.Entry:
    return ENTRIES[SAMPLES.index(sample)]


def provider_run_id(sample: RetrySample) -> str:
    return (
        f"{PROVIDER_BATCH_ID}-{sample.sample_id}-"
        f"{native.MODEL_SUFFIXES[MODEL_ID]}"
    )


def artifact_paths(entry: native.Entry, root: Path = ROOT) -> dict[str, Path]:
    sample = entry.sample
    if not isinstance(sample, RetrySample) or entry not in ENTRIES:
        raise RetryExperimentError("Retry coordinator received an unknown entry")
    base = (
        root
        / EXPERIMENT_ROOT
        / "videos"
        / sample.variant_id
        / native.MODEL_DIRECTORIES[MODEL_ID]
    )
    return {
        "directory": base,
        "prompt": base / "03.prompt.json",
        "run": base / "03.run.json",
        "video": base / "03.mp4",
    }


def provider_sample(entry: native.Entry) -> dict[str, Any]:
    sample = entry.sample
    if not isinstance(sample, RetrySample) or entry not in ENTRIES:
        raise RetryExperimentError("Retry coordinator received an unknown sample")
    return {
        "sample_id": sample.sample_id,
        "article_slug": sample.article_slug,
        "image_id": sample.image_id,
        "image_number": sample.image_id,
        "source_path": SOURCE_PATH.as_posix(),
        "source_url": SOURCE_URL,
        "sha256": SOURCE_SHA256,
        "width": SOURCE_WIDTH,
        "height": SOURCE_HEIGHT,
    }


def load_retry_job(entry: native.Entry, root: Path = ROOT) -> native.LiteJob:
    sample = entry.sample
    if not isinstance(sample, RetrySample) or entry not in ENTRIES:
        raise RetryExperimentError("Retry coordinator received an unknown Lite entry")
    validate_base_receipts(root)
    summary = historical_provenance_summary(root)
    result = read_json(root / PLANNING_RESULT_PATH)
    producer = result.get("producer") if isinstance(result, dict) else None
    inputs = result.get("inputs") if isinstance(result, dict) else None
    source = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    models = result.get("models") if isinstance(result, dict) else None
    if (
        result.get("job_id") != PLANNING_RUN_ID
        or not isinstance(producer, dict)
        or producer.get("agent_id") != AGENT_ID
        or producer.get("contract_version") != HISTORICAL_CONTRACT_VERSION
        or not isinstance(source, dict)
        or source.get("path") != SOURCE_PATH.as_posix()
        or source.get("sha256") != SOURCE_SHA256
        or not isinstance(context, dict)
        or context.get("path") != CONTEXT_PATH.as_posix()
        or context.get("sha256") != CONTEXT_SHA256
        or not isinstance(models, list)
        or [model.get("model_id") for model in models if isinstance(model, dict)]
        != list(ORIGINAL_MODEL_IDS)
    ):
        raise RetryExperimentError("Historical Lite result binding changed")
    model = models[1]
    current_contract = read_json(root / CURRENT_CONTRACT_PATH)
    expected_runtime = current_contract["models"][MODEL_ID]["runtime"]
    if (
        model.get("model_id") != MODEL_ID
        or model.get("positive_prompt") != POSITIVE_PROMPT
        or model.get("negative_prompt") is not None
        or model.get("runtime") != expected_runtime
    ):
        raise RetryExperimentError("Historical Wan 2.7 Lite prompt/runtime changed")
    analysis = result.get("analysis")
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    expected_intent_keys = {
        "editorial_meaning",
        "primary_action",
        "terminal_state",
        "semantic_invariant",
    }
    if (
        not isinstance(intent, dict)
        or set(intent) != expected_intent_keys
        or any(not isinstance(value, str) or not value.strip() for value in intent.values())
    ):
        raise RetryExperimentError("Historical Lite structured intent changed")
    return native.LiteJob(
        entry=entry,
        structured_intent={key: intent[key].strip() for key in intent},
        positive_prompt=POSITIVE_PROMPT,
        negative_prompt=None,
        result_path=PLANNING_RESULT_PATH.as_posix(),
        result_sha256=BASE_RECEIPTS_SHA256[PLANNING_RESULT_PATH.as_posix()],
        provenance=summary,
        runtime=expected_runtime,
    )


def retry_provider_prompt(job: native.LiteJob) -> dict[str, Any]:
    sample = job.entry.sample
    if not isinstance(sample, RetrySample) or job.entry not in ENTRIES:
        raise RetryExperimentError("Retry prompt uses an unknown entry")
    return {
        "sample_id": sample.sample_id,
        "model_id": MODEL_ID,
        "target_duration_seconds": 5,
        "positive_prompt": POSITIVE_PROMPT,
        "negative_prompt": None,
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
        "prompt_extend": True,
    }


def exact_provider_request_preview(
    sample: dict[str, Any], prompt: dict[str, Any]
) -> dict[str, Any]:
    request = _NATIVE_PROVIDER_REQUEST_PREVIEW(sample, prompt)
    if request != EXPECTED_REQUEST:
        raise RetryExperimentError("An explicit retry no longer matches the original request")
    if sha256_json(request) != EXPECTED_REQUEST_BODY_SHA256:
        raise RetryExperimentError("An explicit retry request digest changed")
    fingerprint = transport.request_fingerprint(request, sample)
    if fingerprint != EXPECTED_REQUEST_FINGERPRINT:
        raise RetryExperimentError("An explicit retry request fingerprint changed")
    return request


def retry_prompt_artifact(job: native.LiteJob) -> dict[str, Any]:
    sample = job.entry.sample
    if not isinstance(sample, RetrySample):
        raise RetryExperimentError("Retry prompt artifact has an unknown sample")
    artifact = _NATIVE_PROMPT_ARTIFACT(job)
    artifact["explicit_retry"] = {
        "retry_of": ORIGINAL_PROVIDER_RUN_ID,
        "attempt_index": sample.attempt_index,
        "variant_id": sample.variant_id,
        "request_unchanged": True,
        "tuning_applied": False,
    }
    return artifact


def retry_initial_run(
    job: native.LiteJob,
    paths: dict[str, Path],
    root: Path = ROOT,
) -> dict[str, Any]:
    sample = job.entry.sample
    if not isinstance(sample, RetrySample):
        raise RetryExperimentError("Retry run artifact has an unknown sample")
    run = _NATIVE_INITIAL_RUN(job, paths, root)
    run["explicit_retry"] = {
        "retry_of": ORIGINAL_PROVIDER_RUN_ID,
        "attempt_index": sample.attempt_index,
        "variant_id": sample.variant_id,
        "request_unchanged": True,
        "tuning_applied": False,
    }
    return run


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
        "provider_request_preview",
        "prompt_artifact",
        "initial_run",
        "matrix",
        "load_lite_job",
    )
    saved = {name: getattr(native, name) for name in names}
    try:
        native.BATCH_ID = PROVIDER_BATCH_ID
        native.PLANNING_BATCH_ID = PLANNING_RUN_ID
        native.MODEL_IDS = MODEL_IDS
        native.PLANNING_MODEL_IDS = ORIGINAL_MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = GENERATION_MANIFEST_PATH
        native.CONTRACT_PATH = root / CURRENT_CONTRACT_PATH
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = None
        native.SAMPLES = SAMPLES
        native.WAN_SUBMIT_MODE = None
        native.artifact_paths = lambda entry, workspace=root: artifact_paths(
            entry, workspace
        )
        native.provider_sample = provider_sample
        native.provider_prompt = retry_provider_prompt
        native.provider_request_preview = exact_provider_request_preview
        native.prompt_artifact = retry_prompt_artifact
        native.initial_run = retry_initial_run
        native.matrix = lambda: ENTRIES
        native.load_lite_job = lambda entry, workspace=root: load_retry_job(
            entry, workspace
        )
        actual_ids = tuple(entry.provider_run_id for entry in ENTRIES)
        expected_ids = tuple(provider_run_id(sample) for sample in SAMPLES)
        if actual_ids != expected_ids or len(set(actual_ids)) != RETRY_COUNT:
            raise RetryExperimentError("Explicit retry provider identities changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def request_for_sample(sample: RetrySample, root: Path = ROOT) -> dict[str, Any]:
    entry = _entry_for_sample(sample)
    job = load_retry_job(entry, root)
    return exact_provider_request_preview(
        provider_sample(entry),
        retry_provider_prompt(job),
    )


def cost_document(budget: str | Decimal) -> dict[str, Any]:
    parsed = parse_budget(budget)
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "explicit_retry_entry_count": RETRY_COUNT,
        "reservation_per_retry_usd": float(RETRY_RESERVED_USD),
        "aggregate_reserved_usd": float(AGGREGATE_RESERVED_USD),
        "maximum_submissions_per_provider_identity": 1,
        "automatic_paid_retries": False,
        "actual_billing_available": False,
    }


def inventory_document(
    budget: str | Decimal = HARD_BUDGET_CAP_USD,
    root: Path = ROOT,
) -> dict[str, Any]:
    route = validate_route()
    base_receipts = validate_base_receipts(root)
    provenance = historical_provenance_summary(root)
    entries: list[dict[str, Any]] = []
    for sample in SAMPLES:
        request = request_for_sample(sample, root)
        sample_record = provider_sample(_entry_for_sample(sample))
        entries.append(
            {
                "variant_id": sample.variant_id,
                "attempt_index": sample.attempt_index,
                "sample_id": sample.sample_id,
                "provider_run_id": provider_run_id(sample),
                "planning_run_id": PLANNING_RUN_ID,
                "model_id": MODEL_ID,
                "retry_of": ORIGINAL_PROVIDER_RUN_ID,
                "request_unchanged": True,
                "tuning_applied": False,
                "request_body_sha256": sha256_json(request),
                "request_sha256": transport.request_fingerprint(
                    request, sample_record
                ),
                "reservation_usd": float(RETRY_RESERVED_USD),
            }
        )
    if len({entry["provider_run_id"] for entry in entries}) != RETRY_COUNT:
        raise RetryExperimentError("Explicit retries do not have distinct identities")
    if {entry["request_body_sha256"] for entry in entries} != {
        EXPECTED_REQUEST_BODY_SHA256
    }:
        raise RetryExperimentError("Explicit retries do not share the original request")
    return {
        "schema_version": 1,
        "manifest_role": "wan27-qualitative-explicit-retries-inventory",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": AGENT_ID,
        "model_id": MODEL_ID,
        "retry_of": ORIGINAL_PROVIDER_RUN_ID,
        "source": {
            "path": SOURCE_PATH.as_posix(),
            "sha256": SOURCE_SHA256,
            "url": SOURCE_URL,
            "context_path": CONTEXT_PATH.as_posix(),
            "context_sha256": CONTEXT_SHA256,
            "width": SOURCE_WIDTH,
            "height": SOURCE_HEIGHT,
        },
        "planning": {
            "planning_run_id": PLANNING_RUN_ID,
            "result_path": PLANNING_RESULT_PATH.as_posix(),
            "result_sha256": BASE_RECEIPTS_SHA256[
                PLANNING_RESULT_PATH.as_posix()
            ],
            "historical_contract_commit": HISTORICAL_COMMIT,
            "historical_provenance_reverified": True,
            "provenance": provenance,
        },
        "original_provider_receipts_sha256": base_receipts,
        "original_request": {
            "body_sha256": EXPECTED_REQUEST_BODY_SHA256,
            "request_sha256": EXPECTED_REQUEST_FINGERPRINT,
            "prompt": POSITIVE_PROMPT,
            "seed": 9681,
        },
        "cost": cost_document(budget),
        "generation_policy": {
            "exact_model_id": MODEL_ID,
            "exact_route_only": True,
            "route": route,
            "normal_run_discovery": False,
            "automatic_fallback": False,
            "automatic_paid_retries": False,
            "force_allowed": False,
            "wan27_capacity": 3,
            "first_frame_only": True,
            "maximum_submissions_per_provider_identity": 1,
            "request_changes_allowed": [],
        },
        "expected_outputs": RETRY_COUNT,
        "entries": entries,
    }


def write_inventory(
    budget: str | Decimal = HARD_BUDGET_CAP_USD,
    root: Path = ROOT,
) -> dict[str, Any]:
    document = inventory_document(budget, root)
    path = root / INVENTORY_PATH
    if path.is_file():
        if read_json(path) != document:
            raise RetryExperimentError(f"Immutable retry inventory differs: {path}")
        return document
    if path.exists():
        raise RetryExperimentError(f"Unsafe retry inventory target: {path}")
    transport.atomic_write_json(path, document)
    return document


def _validate_inventory(
    budget: str | Decimal,
    root: Path,
) -> dict[str, Any]:
    expected = inventory_document(budget, root)
    actual = read_json(root / INVENTORY_PATH)
    if actual != expected:
        raise RetryExperimentError("Explicit retry inventory is missing or changed")
    return actual


def materialize(
    budget: str | Decimal = HARD_BUDGET_CAP_USD,
    *,
    root: Path = ROOT,
    dry_run: bool = False,
) -> int:
    document = inventory_document(budget, root)
    if dry_run:
        if document["expected_outputs"] != RETRY_COUNT:
            raise RetryExperimentError("Dry-run retry count changed")
        print("PASS: three exact untuned retry requests validated; no files written")
        return 0
    write_inventory(budget, root)
    with configured_native(root):
        rows = native.materialize(root)
    if len(rows) != RETRY_COUNT:
        raise RetryExperimentError("Expected exactly three materialized retry entries")
    write_experiment_manifest(budget, root)
    print("PASS: materialized three immutable explicit Wan 2.7 retries")
    return 0


def _generation_outputs(root: Path) -> list[dict[str, Any]]:
    path = root / GENERATION_MANIFEST_PATH
    if not path.is_file():
        return []
    generation = read_json(path)
    outputs = generation.get("outputs") if isinstance(generation, dict) else None
    expected_ids = [provider_run_id(sample) for sample in SAMPLES]
    if (
        generation.get("ticket") != TICKET
        or generation.get("batch_id") != PROVIDER_BATCH_ID
        or generation.get("agent_id") != AGENT_ID
        or generation.get("expected_outputs") != RETRY_COUNT
        or not isinstance(outputs, list)
        or [output.get("provider_run_id") for output in outputs] != expected_ids
    ):
        raise RetryExperimentError("Explicit retry generation manifest changed")
    return outputs


def _experiment_document(
    budget: str | Decimal,
    root: Path = ROOT,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    inventory = inventory_document(budget, root)
    raw_outputs = _generation_outputs(root)
    outputs: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    review_ready = 0
    contract_warnings = 0
    for raw, sample in zip(raw_outputs, SAMPLES):
        output = {
            **raw,
            "variant_id": sample.variant_id,
            "attempt_index": sample.attempt_index,
            "retry_of": ORIGINAL_PROVIDER_RUN_ID,
            "request_unchanged": True,
            "tuning_applied": False,
        }
        status = str(output.get("status"))
        summary[status] = summary.get(status, 0) + 1
        video_path = root / str(output.get("video_path", ""))
        if status in {"succeeded", "verification-failed"} and video_path.is_file():
            review_ready += 1
        check = output.get("contract_check")
        if isinstance(check, dict) and check.get("conforms") is False:
            contract_warnings += 1
        outputs.append(output)
    return {
        "schema_version": 1,
        "manifest_role": "wan27-qualitative-explicit-retries",
        "ticket": TICKET,
        "experiment_id": EXPERIMENT_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "retry_of": ORIGINAL_PROVIDER_RUN_ID,
        "request_unchanged": True,
        "tuning_applied": False,
        "cost": inventory["cost"],
        "planning": inventory["planning"],
        "generation_policy": inventory["generation_policy"],
        "expected_outputs": RETRY_COUNT,
        "summary": summary,
        "quality_review_ready_outputs": review_ready,
        "contract_warning_outputs": contract_warnings,
        "inventory_path": INVENTORY_PATH.as_posix(),
        "generation_manifest_path": GENERATION_MANIFEST_PATH.as_posix(),
        "outputs": outputs,
    }


def write_experiment_manifest(
    budget: str | Decimal = HARD_BUDGET_CAP_USD,
    root: Path = ROOT,
) -> dict[str, Any]:
    path = root / EXPERIMENT_MANIFEST_PATH
    if path.is_file():
        current = read_json(path)
        timestamp = current.get("updated_at") if isinstance(current, dict) else None
        if isinstance(timestamp, str):
            unchanged = _experiment_document(budget, root, updated_at=timestamp)
            if current == unchanged:
                return unchanged
    document = _experiment_document(budget, root)
    transport.atomic_write_json(path, document)
    return document


def run_generation(
    budget: str | Decimal = HARD_BUDGET_CAP_USD,
    *,
    root: Path = ROOT,
    timeout: int = 1800,
    poll_interval: float = 10.0,
    dry_run: bool = False,
    allow_external_processing: bool = False,
) -> int:
    _validate_inventory(budget, root)
    if dry_run:
        for sample in SAMPLES:
            request_for_sample(sample, root)
        print("PASS: three paid retry submissions validated; no provider calls or writes")
        return 0
    if not allow_external_processing:
        raise RetryExperimentError(
            "Real retry generation requires --allow-external-processing"
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
        "--allow-external-processing",
    ]
    with configured_native(root):
        native_result = native.main(argv, root)
    if validate_base_receipts(root) != before:
        raise RetryExperimentError("Original Lite/provider receipts changed during retries")
    experiment = write_experiment_manifest(budget, root)
    ready = experiment["quality_review_ready_outputs"]
    if ready == RETRY_COUNT:
        if experiment["contract_warning_outputs"]:
            print(
                "PASS: three retry MP4s are ready for quality review; "
                "media-contract warnings remain recorded"
            )
        else:
            print("PASS: three retry MP4s generated and verified")
        return 0
    return native_result or 1


def verify_all(
    budget: str | Decimal = HARD_BUDGET_CAP_USD,
    *,
    root: Path = ROOT,
    allow_contract_warnings: bool = False,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        _validate_inventory(budget, root)
        validate_base_receipts(root)
        with configured_native(root):
            passed, native_errors = native.verify(
                root,
                allow_incomplete=False,
                allow_contract_warnings=allow_contract_warnings,
            )
        if not passed:
            errors.extend(native_errors)
        actual = read_json(root / EXPERIMENT_MANIFEST_PATH)
        timestamp = actual.get("updated_at") if isinstance(actual, dict) else None
        if not isinstance(timestamp, str):
            errors.append("Experiment manifest has no updated_at")
        elif actual != _experiment_document(budget, root, updated_at=timestamp):
            errors.append("Experiment manifest does not match retry receipts")
        if actual.get("quality_review_ready_outputs") != RETRY_COUNT:
            errors.append("Not all three retry MP4s are ready for quality review")
    except (
        RetryExperimentError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        errors.append(str(exc))
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
        help="fixed accounting cap for exactly three retries (default: 1.05)",
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
    verify = commands.add_parser("verify")
    verify.add_argument("--allow-contract-warnings", action="store_true")
    _add_budget(verify)
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
                f"${document['cost']['aggregate_reserved_usd']:.2f} for "
                "three exact explicit retries"
            )
            return 0
        if args.command == "plan":
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
            passed, errors = verify_all(
                args.budget_cap_usd,
                root=root,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: three explicit Wan 2.7 retry receipts are valid")
            return 0
        raise RetryExperimentError(f"Unknown command: {args.command}")
    except (
        RetryExperimentError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
