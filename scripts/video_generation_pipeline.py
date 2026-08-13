#!/usr/bin/env python3
"""Plan, run, resume, and verify the PROMOPAGES-9856 video matrix.

The checked-in sample and prompt catalogs are the source of truth.  Generated
artifacts live next to their source article under ``video/<model>/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import mimetypes
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]


class PipelineError(RuntimeError):
    """A user-actionable pipeline failure."""


class ProviderTerminalError(PipelineError):
    """The provider reported a definitive terminal job failure."""


class SegmindProviderTaskFailedError(ProviderTerminalError):
    """Segmind created a task and returned its exact terminal failure evidence."""

    def __init__(self, message: str, evidence: dict[str, Any]) -> None:
        super().__init__(message)
        self.evidence = dict(evidence)
        self.http_status = evidence["http_status"]
        self.provider_task_id = evidence["provider_task_id"]


class PreSubmitNetworkError(PipelineError):
    """A transport failure proven to have happened before request submission."""


class PreSubmitRejectedError(PipelineError):
    """A definitive HTTP rejection received before a provider job was created."""

    def __init__(self, message: str, http_status: int) -> None:
        super().__init__(message)
        self.http_status = http_status


PRE_SUBMIT_REJECTED_HTTP_STATUSES = frozenset({429})
SEGMIND_OVERSIZE_ERROR_MESSAGE = "Image size is too large than 20.0 mb"
SEGMIND_UNDERSIZE_ERROR_MESSAGE = "Image height or width is too small than 240"
SEGMIND_PROVIDER_FAILURE_PREFIX = "the provider task failed: "
SEGMIND_PROVIDER_FAILURE_REQUIRED_KEYS = frozenset(
    {"task_id", "task_status", "video_url", "code", "message"}
)
SEGMIND_PROVIDER_FAILURE_OPTIONAL_TIME_KEYS = (
    "submit_time",
    "scheduled_time",
    "end_time",
)


def _parse_segmind_known_terminal_task_failure(
    http_status: int,
    detail: str,
    *,
    expected_error_message: str,
) -> dict[str, Any] | None:
    """Return exact terminal evidence for one known Segmind input rejection.

    A synchronous POST may return HTTP 400 after Segmind has already created and
    terminally failed a provider task.  Only the fully nested, known response is
    safe to classify that way; malformed bodies and all near matches remain
    ambiguous submit failures.
    """

    if http_status != 400 or not isinstance(detail, str):
        return None
    try:
        outer = json.loads(detail)
    except json.JSONDecodeError:
        return None
    if not isinstance(outer, dict) or set(outer) != {"error"}:
        return None
    outer_error = outer.get("error")
    if (
        not isinstance(outer_error, str)
        or not outer_error.startswith(SEGMIND_PROVIDER_FAILURE_PREFIX)
    ):
        return None
    nested_detail = outer_error[len(SEGMIND_PROVIDER_FAILURE_PREFIX) :]
    try:
        provider = json.loads(nested_detail)
    except json.JSONDecodeError:
        return None
    if not isinstance(provider, dict):
        return None

    optional_time_keys = set(SEGMIND_PROVIDER_FAILURE_OPTIONAL_TIME_KEYS)
    provider_keys = set(provider)
    if not (
        SEGMIND_PROVIDER_FAILURE_REQUIRED_KEYS <= provider_keys
        and provider_keys
        <= SEGMIND_PROVIDER_FAILURE_REQUIRED_KEYS | optional_time_keys
    ):
        return None
    task_id = provider.get("task_id")
    if (
        not isinstance(task_id, str)
        or not task_id
        or task_id.strip() != task_id
        or provider.get("task_status") != "FAILED"
        or provider.get("video_url") != ""
        or provider.get("code") != "InvalidParameter"
        or provider.get("message") != expected_error_message
    ):
        return None
    for key in SEGMIND_PROVIDER_FAILURE_OPTIONAL_TIME_KEYS:
        if key in provider and (
            not isinstance(provider[key], str)
            or not provider[key]
            or provider[key].strip() != provider[key]
        ):
            return None

    evidence: dict[str, Any] = {
        "http_status": 400,
        "provider_task_id": task_id,
        "provider_task_status": "FAILED",
        "provider_error_code": "InvalidParameter",
        "provider_error_message": expected_error_message,
    }
    for key in SEGMIND_PROVIDER_FAILURE_OPTIONAL_TIME_KEYS:
        if key in provider:
            evidence[key] = provider[key]
    return evidence


def parse_segmind_oversize_task_failure(
    http_status: int,
    detail: str,
) -> dict[str, Any] | None:
    """Return exact terminal evidence for Segmind's known >20 MiB rejection."""

    return _parse_segmind_known_terminal_task_failure(
        http_status,
        detail,
        expected_error_message=SEGMIND_OVERSIZE_ERROR_MESSAGE,
    )


def parse_segmind_undersize_task_failure(
    http_status: int,
    detail: str,
) -> dict[str, Any] | None:
    """Return exact terminal evidence for Segmind's known <240 px rejection."""

    return _parse_segmind_known_terminal_task_failure(
        http_status,
        detail,
        expected_error_message=SEGMIND_UNDERSIZE_ERROR_MESSAGE,
    )


GENERATION_ROUTES_PATH = ROOT / "docs/agents/clipmaker-lite/generation-routes.json"
OUTPUT_ACCEPTANCE_PATH = ROOT / "docs/agents/clipmaker-lite/output-acceptance.json"


def _load_generation_routes(path: Path = GENERATION_ROUTES_PATH) -> dict[str, Any]:
    """Load and validate the fixed normal-run routes without network discovery."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError as exc:
        raise PipelineError(f"Generation route registry does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid generation route registry {path}: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise PipelineError("Generation route registry must use schema_version 1")
    policy = document.get("policy")
    if not isinstance(policy, dict) or policy.get("resolution") != "exact-model-id":
        raise PipelineError("Generation routes must resolve by exact model_id")
    if policy.get("automatic_fallback") is not False:
        raise PipelineError("Generation routes must disable automatic fallback")
    if policy.get("normal_run_discovery") is not False:
        raise PipelineError("Generation routes must disable normal-run discovery")
    routes = document.get("models")
    if not isinstance(routes, dict) or not routes:
        raise PipelineError("Generation route registry must contain a non-empty models object")
    for model_id, route in routes.items():
        if not isinstance(model_id, str) or not isinstance(route, dict):
            raise PipelineError("Generation route entries must map model IDs to objects")
        if route.get("adapter") not in {
            "eliza-segmind",
            "wan-demo",
            "eliza-openrouter",
        }:
            raise PipelineError(f"Unsupported adapter in generation route for {model_id}")
        paths = route.get("paths")
        if not isinstance(paths, dict) or not paths:
            raise PipelineError(f"Generation route for {model_id} has no paths")
        for name, value in paths.items():
            if not isinstance(value, str) or not value.startswith("/"):
                raise PipelineError(
                    f"Generation route path {model_id}.{name} must start with /"
                )
    return document


GENERATION_ROUTE_DOCUMENT = _load_generation_routes()
GENERATION_ROUTES: dict[str, dict[str, Any]] = GENERATION_ROUTE_DOCUMENT["models"]


def route_for_model(model_id: str) -> dict[str, Any]:
    """Return the one configured route; never discover or substitute a model."""

    route = GENERATION_ROUTES.get(model_id)
    if route is None:
        raise PipelineError(f"No exact generation route for model_id: {model_id}")
    return route


def _load_output_acceptance_policy(
    path: Path = OUTPUT_ACCEPTANCE_PATH,
) -> tuple[dict[str, Any], str]:
    """Load the versioned output-only exceptions without changing generation."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except FileNotFoundError as exc:
        raise PipelineError(f"Output acceptance policy does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid output acceptance policy {path}: {exc}") from exc
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("contract") != "clipmaker-lite-output-acceptance/v1"
    ):
        raise PipelineError("Output acceptance policy must use contract v1")
    policies = document.get("policies")
    if not isinstance(policies, list) or not policies:
        raise PipelineError("Output acceptance policy must contain policies")
    expected_keys = {
        "policy_id",
        "model_id",
        "adapter",
        "target_generate_audio",
        "observed_has_audio",
        "waived_warnings",
        "require_all_other_checks",
    }
    seen_ids: set[str] = set()
    seen_routes: set[tuple[str, str]] = set()
    for policy in policies:
        if not isinstance(policy, dict) or set(policy) != expected_keys:
            raise PipelineError("Output acceptance policy entry has invalid keys")
        policy_id = policy.get("policy_id")
        model_id = policy.get("model_id")
        adapter = policy.get("adapter")
        if (
            not isinstance(policy_id, str)
            or not policy_id
            or not isinstance(model_id, str)
            or not isinstance(adapter, str)
        ):
            raise PipelineError("Output acceptance policy identity is invalid")
        if policy_id in seen_ids or (model_id, adapter) in seen_routes:
            raise PipelineError("Output acceptance policy identities must be unique")
        seen_ids.add(policy_id)
        seen_routes.add((model_id, adapter))
        if model_id not in GENERATION_ROUTES:
            raise PipelineError(f"Output acceptance policy has unknown model: {model_id}")
        if route_for_model(model_id)["adapter"] != adapter:
            raise PipelineError(f"Output acceptance policy adapter mismatch: {model_id}")
        if (
            policy.get("target_generate_audio") is not False
            or policy.get("observed_has_audio") is not True
            or policy.get("waived_warnings") != ["audio"]
            or policy.get("require_all_other_checks") is not True
        ):
            raise PipelineError("Only the exact no-audio target/audio-output exception is supported")
    canonical = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return document, hashlib.sha256(canonical).hexdigest()


OUTPUT_ACCEPTANCE_POLICY_DOCUMENT, OUTPUT_ACCEPTANCE_POLICY_SHA256 = (
    _load_output_acceptance_policy()
)


def _contract_failed_checks(contract_check: dict[str, Any]) -> list[str] | None:
    checks = contract_check.get("checks")
    if not isinstance(checks, dict) or not checks:
        return None
    if any(not isinstance(name, str) or not isinstance(value, bool) for name, value in checks.items()):
        return None
    return [name for name, passed in checks.items() if not passed]


def _warnings_are_exact_audio(contract_check: dict[str, Any]) -> bool:
    warnings = contract_check.get("warnings")
    if warnings == ["audio"]:
        return True
    return (
        isinstance(warnings, list)
        and len(warnings) == 1
        and warnings[0]
        == "provider returned has_audio=True despite generate_audio=False"
    )


def media_acceptance(
    model_id: str,
    media: dict[str, Any],
    contract_check: dict[str, Any],
) -> dict[str, Any]:
    """Return an auditable strict or exact route-exception decision."""

    adapter = route_for_model(model_id)["adapter"]
    requested = contract_check.get("requested")
    target_audio = requested.get("generate_audio") if isinstance(requested, dict) else None
    observed_audio = media.get("has_audio")
    base = {
        "accepted": False,
        "mode": "strict-contract",
        "policy_id": None,
        "policy_sha256": None,
        "model_id": model_id,
        "adapter": adapter,
        "target_generate_audio": target_audio,
        "observed_has_audio": observed_audio,
        "waived_warnings": [],
    }
    failed_checks = _contract_failed_checks(contract_check)
    if (
        contract_check.get("conforms") is True
        and failed_checks == []
        and contract_check.get("warnings") == []
        and isinstance(target_audio, bool)
        and observed_audio is target_audio
    ):
        return {**base, "accepted": True}
    for policy in OUTPUT_ACCEPTANCE_POLICY_DOCUMENT["policies"]:
        if policy["model_id"] != model_id or policy["adapter"] != adapter:
            continue
        if (
            contract_check.get("conforms") is False
            and failed_checks == policy["waived_warnings"]
            and _warnings_are_exact_audio(contract_check)
            and target_audio is policy["target_generate_audio"]
            and observed_audio is policy["observed_has_audio"]
        ):
            return {
                **base,
                "accepted": True,
                "mode": "route-exception",
                "policy_id": policy["policy_id"],
                "policy_sha256": OUTPUT_ACCEPTANCE_POLICY_SHA256,
                "waived_warnings": list(policy["waived_warnings"]),
            }
    return base


def validate_media_acceptance(
    model_id: str,
    media: dict[str, Any],
    contract_check: dict[str, Any],
    acceptance: Any,
) -> bool:
    """Validate an externally stored acceptance overlay by exact recomputation."""

    return isinstance(acceptance, dict) and acceptance == media_acceptance(
        model_id,
        media,
        contract_check,
    )


DEFAULT_SAMPLES = ROOT / "PROMOPAGES-9857/video-samples.json"
DEFAULT_PROMPTS = ROOT / "PROMOPAGES-9857/video-prompts.json"
DEFAULT_MANIFEST = ROOT / "PROMOPAGES-9857/video-generation-manifest.json"
_WAN_ROUTE = route_for_model("alibaba/wan-2.2")
DEFAULT_SEGMIND_BASE_URL = _WAN_ROUTE["default_base_url"]
SEGMIND_SUBMIT_ENDPOINT = _WAN_ROUTE["paths"]["submit"]
SEGMIND_ACCEPT = _WAN_ROUTE["request_headers"]["accept"]
SEGMIND_CONTENT_TYPES = frozenset(_WAN_ROUTE["response"]["content_types"])
SEGMIND_REQUEST_ID_HEADER = _WAN_ROUTE["response"]["request_id_header"]
SEGMIND_COST_HEADER = _WAN_ROUTE["response"]["cost_header"]

# Historical explicit Gradio helpers remain import-compatible for frozen old
# receipts. The canonical alibaba/wan-2.2 route above never selects them.
WAN_UPLOAD_ENDPOINT = "/gradio_api/upload"
WAN_LEGACY_ENDPOINT = "/gradio_api/queue/join"
WAN_STREAM_ENDPOINT = "/gradio_api/queue/data"
WAN_FILE_PREFIX = "/gradio_api/file="
WAN_NAMED_ENDPOINT = "/gradio_api/call/text2video"
WAN_NAMED_SESSION_MARKER = "named-api:text2video"
WAN_DOD_HOST_SUFFIX = ".dod.yandex.net"
DEFAULT_ELIZA_BASE_URL = route_for_model("alibaba/wan-2.7")["default_base_url"]

_MODEL_RUNTIME_CONFIGS: dict[str, dict[str, Any]] = {
    "alibaba/wan-2.2": {
        "directory": "wan-2.2",
        "duration": 5,
        "durations": [5],
        "resolution": "720p",
        "aspect_ratios": ["source"],
        "seed": 220214,
        "frames": 150,
        "fps": 30,
        "generate_audio": False,
        "prompt_extend": False,
        "watermark": False,
    },
    "alibaba/wan-2.7": {
        "directory": "wan-2.7",
        "duration": 3,
        "durations": list(range(2, 11)),
        "resolution": "1080p",
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "seed": 9681,
        "generate_audio": False,
        "negative_limit": 500,
    },
    "google/veo-3.1-lite": {
        "directory": "veo-3.1-lite",
        "duration": 4,
        "durations": [4, 6, 8],
        "resolution": "1080p",
        "aspect_ratios": ["16:9", "9:16"],
        "seed": 9681,
        "generate_audio": False,
    },
}

if set(_MODEL_RUNTIME_CONFIGS) != set(GENERATION_ROUTES):
    raise PipelineError(
        "Runtime model configs and exact generation routes must contain the same model IDs"
    )
MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    model_id: {
        **runtime,
        "adapter": route_for_model(model_id)["adapter"],
        **(
            {"provider": route_for_model(model_id)["provider_key"]}
            if "provider_key" in route_for_model(model_id)
            else {}
        ),
    }
    for model_id, runtime in _MODEL_RUNTIME_CONFIGS.items()
}

EXPECTED_SAMPLE_COUNT = 5
EXPECTED_RESULT_COUNT = EXPECTED_SAMPLE_COUNT * len(MODEL_CONFIGS)
REQUEST_FINGERPRINT_VERSION = 2
TERMINAL_SUCCESS = {"completed", "succeeded", "success", "done"}
TERMINAL_FAILURE = {"failed", "error", "cancelled", "canceled", "expired"}
SECRET_RE = re.compile(
    r"(?i)([\"']?authorization[\"']?\s*[:=]\s*[\"']?(?:bearer|oauth)\s+)"
    r"[^\"'\s,;}]+|"
    r"([\"']?(?:access[_-]?token|api[_-]?key|token)[\"']?\s*[:=]\s*[\"']?)"
    r"[^\"'\s,;}]+"
)
EXPERIMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PipelineError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in {path}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    temp_path.replace(path)
    # The synchronous Segmind transport relies on the ``submitting`` receipt
    # surviving a process/host crash before its non-idempotent POST.  Fsync the
    # containing directory so the atomic rename is durable as well.
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_error(error: BaseException | str) -> str:
    message = str(error)
    for env_name in (
        "DOD_TOKEN",
        "YA_TOKEN",
        "ELIZA_OAUTH_TOKEN",
        "ELIZA_TOKEN",
        "ANTHROPIC_AUTH_TOKEN",
    ):
        secret = os.environ.get(env_name)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = SECRET_RE.sub(lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", message)
    message = re.sub(r"([?&](?:token|key|signature|sig|auth)=)[^&\s]+", r"\1[REDACTED]", message, flags=re.I)
    return message[:2000]


def _url_origin(url: str) -> tuple[str, str, int] | None:
    """Return a normalized HTTP origin, rejecting malformed URLs."""

    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, parsed.hostname.lower(), port


def is_trusted_wan_dod_url(url: str) -> bool:
    """Allow OAuth only over TLS to the internal DOD host namespace."""

    origin = _url_origin(url)
    if origin is None:
        return False
    scheme, hostname, port = origin
    return scheme == "https" and port == 443 and hostname.endswith(WAN_DOD_HOST_SUFFIX)


def wan_named_headers(base_url: str) -> dict[str, str]:
    """Build ephemeral headers for the authenticated Wan named API."""

    if not is_trusted_wan_dod_url(base_url):
        raise PipelineError(
            "Wan named API credentials may only be sent to HTTPS *.dod.yandex.net"
        )
    token = os.environ.get("DOD_TOKEN") or os.environ.get("YA_TOKEN")
    if not token:
        raise PipelineError("Set DOD_TOKEN or YA_TOKEN before a real Wan named API run")
    return {
        "Authorization": f"OAuth {token}",
        "X-Dod-Autostart": "true",
        "X-Requested-With": "bot",
    }


def _request_with_scoped_headers(
    url: str,
    *,
    method: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> Request:
    """Create a request whose supplied headers are not copied on redirects."""

    request = Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_unredirected_header(key, value)
    return request


def _same_origin(first_url: str, second_url: str) -> bool:
    first = _url_origin(first_url)
    return first is not None and first == _url_origin(second_url)


def relative(path: Path, root: Path = ROOT) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def validate_catalogs(samples_path: Path, prompts_path: Path, root: Path = ROOT) -> tuple[list[dict], list[dict]]:
    sample_doc = read_json(samples_path)
    prompt_doc = read_json(prompts_path)
    samples = sample_doc.get("samples") if isinstance(sample_doc, dict) else None
    prompts = prompt_doc.get("prompts") if isinstance(prompt_doc, dict) else None
    if not isinstance(samples, list) or not isinstance(prompts, list):
        raise PipelineError("Sample and prompt catalogs must contain arrays named samples and prompts")
    if len(samples) != EXPECTED_SAMPLE_COUNT:
        raise PipelineError(f"Expected exactly {EXPECTED_SAMPLE_COUNT} samples, got {len(samples)}")

    unique_fields = ("sample_id", "image_id", "article_slug", "primary_class")
    for field in unique_fields:
        values = [sample.get(field) for sample in samples]
        if any(not value for value in values) or len(set(values)) != EXPECTED_SAMPLE_COUNT:
            raise PipelineError(f"Samples must have {EXPECTED_SAMPLE_COUNT} unique non-empty {field} values")

    sample_by_id = {sample["sample_id"]: sample for sample in samples}
    for sample in samples:
        source = root / sample.get("source_path", "")
        try:
            source.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise PipelineError(f"Source path escapes the repository root: {source}") from exc
        if not source.is_file():
            raise PipelineError(f"Source image does not exist: {source}")
        expected_sha = sample.get("sha256")
        if not expected_sha or sha256_file(source) != expected_sha:
            raise PipelineError(f"Source SHA-256 mismatch: {source}")
        if not str(sample.get("source_url", "")).startswith("https://"):
            raise PipelineError(f"Source URL must be public HTTPS: {sample.get('sample_id')}")

    if len(prompts) != EXPECTED_RESULT_COUNT:
        raise PipelineError(f"Expected exactly {EXPECTED_RESULT_COUNT} prompt records, got {len(prompts)}")
    seen: set[tuple[str, str]] = set()
    for prompt in prompts:
        sample_id = prompt.get("sample_id")
        model_id = prompt.get("model_id")
        key = (sample_id, model_id)
        if sample_id not in sample_by_id:
            raise PipelineError(f"Prompt references unknown sample_id: {sample_id}")
        if model_id not in MODEL_CONFIGS:
            raise PipelineError(f"Prompt references unsupported model_id: {model_id}")
        if key in seen:
            raise PipelineError(f"Duplicate prompt record: {sample_id} / {model_id}")
        seen.add(key)
        config = MODEL_CONFIGS[model_id]
        target_duration = float(prompt.get("target_duration_seconds", -1))
        allowed_durations = {float(value) for value in config.get("durations", [config["duration"]])}
        if target_duration not in allowed_durations:
            raise PipelineError(f"Wrong target duration for {sample_id} / {model_id}")
        if prompt.get("camera_state") not in {"A", "B", "C", "D", "E"}:
            raise PipelineError(f"Missing camera state A-E for {sample_id} / {model_id}")
        if prompt.get("primary_class") != sample_by_id[sample_id].get("primary_class"):
            raise PipelineError(f"Primary class mismatch for {sample_id} / {model_id}")
        if prompt.get("graphic_kind") != sample_by_id[sample_id].get("graphic_kind"):
            raise PipelineError(f"Active graphic kind mismatch for {sample_id} / {model_id}")
        if prompt.get("graphic_kinds", []) != sample_by_id[sample_id].get("graphic_kinds", []):
            raise PipelineError(f"Visible graphic kinds mismatch for {sample_id} / {model_id}")
        if prompt.get("motion_plan_id") != sample_by_id[sample_id].get("motion_plan_id"):
            raise PipelineError(f"Motion plan mismatch for {sample_id} / {model_id}")
        if float(prompt.get("action_complete_by_seconds", -1)) != float(
            sample_by_id[sample_id].get("action_complete_by_seconds", -2)
        ):
            raise PipelineError(f"Action completion deadline mismatch for {sample_id} / {model_id}")
        if float(prompt["action_complete_by_seconds"]) > target_duration:
            raise PipelineError(f"Action completion deadline exceeds target duration for {sample_id} / {model_id}")
        if not isinstance(prompt.get("last_frame_is_source", False), bool):
            raise PipelineError(f"last_frame_is_source must be boolean for {sample_id} / {model_id}")
        if prompt.get("last_frame_is_source") and config["adapter"] != "eliza-openrouter":
            raise PipelineError(f"last_frame_is_source is unsupported for {sample_id} / {model_id}")
        if not isinstance(prompt.get("embed_negative_in_positive", False), bool):
            raise PipelineError(f"embed_negative_in_positive must be boolean for {sample_id} / {model_id}")
        if prompt.get("embed_negative_in_positive") and config["adapter"] != "eliza-openrouter":
            raise PipelineError(f"embed_negative_in_positive is unsupported for {sample_id} / {model_id}")
        for field in ("positive_prompt", "negative_prompt"):
            if not isinstance(prompt.get(field), str) or not prompt[field].strip():
                raise PipelineError(f"Missing {field} for {sample_id} / {model_id}")
        limit = config.get("negative_limit")
        if limit and not prompt.get("embed_negative_in_positive") and len(prompt["negative_prompt"]) > limit:
            raise PipelineError(
                f"Negative prompt is {len(prompt['negative_prompt'])} characters; "
                f"{model_id} allows at most {limit}: {sample_id}"
            )
    expected = {(sample["sample_id"], model_id) for sample in samples for model_id in MODEL_CONFIGS}
    if seen != expected:
        raise PipelineError("Prompt matrix is not the complete 5 x 3 Cartesian product")
    prompt_by_key = {(prompt["sample_id"], prompt["model_id"]): prompt for prompt in prompts}
    for prompt in prompts:
        source_model_id = prompt.get("prompt_source_model_id")
        if not source_model_id:
            continue
        if source_model_id == prompt["model_id"]:
            raise PipelineError(
                f"Prompt source model must differ from target: {prompt['sample_id']} / {prompt['model_id']}"
            )
        if not prompt.get("embed_negative_in_positive"):
            raise PipelineError(
                f"Copied prompt must preserve the combined positive/Avoid transport: "
                f"{prompt['sample_id']} / {prompt['model_id']}"
            )
        source = prompt_by_key.get((prompt["sample_id"], source_model_id))
        if not source:
            raise PipelineError(
                f"Prompt source model is missing for {prompt['sample_id']} / {prompt['model_id']}"
            )
        prompt_matches_source = (
            prompt["positive_prompt"] == source["positive_prompt"]
            and prompt["negative_prompt"] == source["negative_prompt"]
        )
        if not prompt_matches_source:
            raise PipelineError(
                f"Copied prompt differs from {source_model_id}: {prompt['sample_id']} / {prompt['model_id']}"
            )
    return samples, prompts


def choose_aspect_ratio(width: int, height: int, supported: Iterable[str]) -> str:
    ratios = list(supported)
    if ratios == ["source"]:
        return "source"
    if width <= 0 or height <= 0:
        raise PipelineError(f"Invalid source dimensions: {width}x{height}")
    target = width / height

    def distance(label: str) -> float:
        left, right = label.split(":", 1)
        return abs(math.log(target / (float(left) / float(right))))

    return min(ratios, key=distance)


def artifact_paths(
    root: Path,
    sample: dict,
    model_id: str,
    experiment_id: str | None = None,
) -> dict[str, Path]:
    if model_id not in MODEL_CONFIGS:
        raise PipelineError(f"Unsupported model_id: {model_id}")
    video_root = root / "PROMOPAGES-9857/articles" / sample["article_slug"] / "video"
    if experiment_id is not None:
        if not EXPERIMENT_ID_RE.fullmatch(experiment_id):
            raise PipelineError(f"Unsafe experiment_id: {experiment_id}")
        video_root = video_root / "experiments" / experiment_id
    base = video_root / MODEL_CONFIGS[model_id]["directory"]
    stem = sample["image_number"]
    return {
        "directory": base,
        "prompt": base / f"{stem}.prompt.json",
        "run": base / f"{stem}.run.json",
        "video": base / f"{stem}.mp4",
    }


def prompt_artifact(
    sample: dict,
    prompt: dict,
    root: Path,
    source_catalog: str = "PROMOPAGES-9857/video-prompts.json",
    experiment_id: str | None = None,
) -> dict[str, Any]:
    config = MODEL_CONFIGS[prompt["model_id"]]
    artifact = {
        "schema_version": 1,
        "ticket": "PROMOPAGES-9856",
        "sample_id": sample["sample_id"],
        "image_id": sample["image_id"],
        "model_id": prompt["model_id"],
        "source": {
            "path": sample["source_path"],
            "url": sample["source_url"],
            "sha256": sample["sha256"],
            "width": sample["width"],
            "height": sample["height"],
        },
        "routing": {
            "primary_class": prompt["primary_class"],
            "graphic_kind": prompt.get("graphic_kind"),
            "graphic_kinds": prompt.get("graphic_kinds", []),
            "camera_state": prompt["camera_state"],
        },
        "motion": {
            "plan_id": prompt["motion_plan_id"],
            "action_complete_by_seconds": prompt["action_complete_by_seconds"],
        },
        "prompt": {
            "positive": prompt["positive_prompt"],
            "negative": prompt["negative_prompt"],
            "source_model_id": prompt.get("prompt_source_model_id"),
            "embed_negative_in_positive": prompt.get("embed_negative_in_positive", False),
        },
        "target": {
            "duration_seconds": prompt["target_duration_seconds"],
            "resolution": config["resolution"],
            "aspect_ratio": choose_aspect_ratio(sample["width"], sample["height"], config["aspect_ratios"]),
            "generate_audio": config["generate_audio"],
            "seed": config["seed"],
            "last_frame_is_source": prompt.get("last_frame_is_source", False),
        },
        "generator": "project clipmaker agent",
        "source_catalog": source_catalog,
    }
    if "prompt_extend" in prompt:
        artifact["target"]["prompt_extend"] = prompt["prompt_extend"]
    if experiment_id is not None:
        artifact["experiment_id"] = experiment_id
    return artifact


def request_fingerprint(request_preview: dict[str, Any], sample: dict[str, Any]) -> str:
    envelope = {
        "request": request_preview,
        "source_sha256": sample.get("sha256"),
        "adapter": MODEL_CONFIGS[request_preview["model"]]["adapter"],
    }
    canonical = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def initial_run_artifact(sample: dict, model_id: str, paths: dict[str, Path], root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ticket": "PROMOPAGES-9856",
        "sample_id": sample["sample_id"],
        "image_id": sample["image_id"],
        "model_id": model_id,
        "adapter": MODEL_CONFIGS[model_id]["adapter"],
        "status": "pending",
        "prompt_path": relative(paths["prompt"], root),
        "output_path": relative(paths["video"], root),
        "request": None,
        "request_sha256": None,
        "request_fingerprint_version": None,
        "provider_job_id": None,
        "provider_session_hash": None,
        "submitted_at": None,
        "completed_at": None,
        "media": None,
        "contract_check": None,
        "error": None,
    }


def materialize_plan(
    samples_path: Path = DEFAULT_SAMPLES,
    prompts_path: Path = DEFAULT_PROMPTS,
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    samples, prompts = validate_catalogs(samples_path, prompts_path, root)
    sample_by_id = {sample["sample_id"]: sample for sample in samples}
    rows: list[dict[str, Any]] = []
    for prompt in sorted(prompts, key=lambda value: (value["sample_id"], value["model_id"])):
        sample = sample_by_id[prompt["sample_id"]]
        model_id = prompt["model_id"]
        paths = artifact_paths(root, sample, model_id)
        paths["directory"].mkdir(parents=True, exist_ok=True)
        atomic_write_json(paths["prompt"], prompt_artifact(sample, prompt, root))
        if not paths["run"].exists():
            atomic_write_json(paths["run"], initial_run_artifact(sample, model_id, paths, root))
        else:
            existing_run = read_json(paths["run"])
            expected_request = build_request_preview(sample, prompt)
            expected_fingerprint = request_fingerprint(expected_request, sample)
            if existing_run.get("status") == "succeeded":
                recorded_version = existing_run.get("request_fingerprint_version")
                if existing_run.get("request") == expected_request and (
                    recorded_version is None
                    or (
                        recorded_version == REQUEST_FINGERPRINT_VERSION
                        and existing_run.get("request_sha256") == expected_fingerprint
                    )
                ):
                    existing_run["request_sha256"] = expected_fingerprint
                    existing_run["request_fingerprint_version"] = REQUEST_FINGERPRINT_VERSION
                else:
                    existing_run["status"] = "stale"
                    existing_run["error"] = (
                        "Prompt or runtime request changed after this output was generated; "
                        "review the diff and rerun with --force"
                    )
            if existing_run.get("status") == "succeeded" and existing_run.get("media"):
                existing_run["contract_check"] = assess_contract(
                    model_id,
                    existing_run["media"],
                    prompt["target_duration_seconds"],
                )
            if existing_run.get("status") in {"submitted", "running"}:
                recorded_fingerprint = existing_run.get("request_sha256")
                recorded_version = existing_run.get("request_fingerprint_version")
                if (
                    existing_run.get("request") != expected_request
                    or recorded_version != REQUEST_FINGERPRINT_VERSION
                    or recorded_fingerprint != expected_fingerprint
                ):
                    existing_run["status"] = "stale"
                    existing_run["error"] = (
                        "Request changed while a provider job was active; inspect that job and rerun with --force"
                    )
            if existing_run.get("status") != "stale" and existing_run.get("request") == expected_request:
                existing_run["request_sha256"] = expected_fingerprint
                existing_run["request_fingerprint_version"] = REQUEST_FINGERPRINT_VERSION
            if existing_run.get("status") != "stale" and (existing_run.get("error") or "").startswith(
                "Prompt or runtime request changed"
            ):
                existing_run["error"] = None
            atomic_write_json(paths["run"], existing_run)
        rows.append({"sample": sample, "prompt": prompt, "paths": paths})
    write_aggregate_manifest(rows, root)
    return rows


def segmind_request_payload(sample: dict, prompt: dict) -> dict[str, Any]:
    """Build the exact synchronous Eliza -> Segmind JSON body."""

    route = route_for_model("alibaba/wan-2.2")
    if route.get("adapter") != "eliza-segmind":
        raise PipelineError("Canonical alibaba/wan-2.2 route is not Eliza/Segmind")
    fixed = route.get("submit_payload", {}).get("fixed")
    if not isinstance(fixed, dict):
        raise PipelineError("Eliza/Segmind route has no fixed submit payload")
    negative_prompt = prompt.get("negative_prompt")
    if negative_prompt is None:
        # The Lite authoring contract intentionally permits null.  Segmind's
        # proven request shape requires a string field, so null has one locked
        # wire representation rather than being sent as unverified JSON null.
        negative_prompt = ""
    elif not isinstance(negative_prompt, str):
        raise PipelineError("Eliza/Segmind negative_prompt must be a string or null")
    payload = {
        "image": sample["source_url"],
        "prompt": prompt["positive_prompt"],
        "negative_prompt": negative_prompt,
        **fixed,
    }
    expected_fields = route.get("submit_payload", {}).get("fields")
    if list(payload) != expected_fields:
        raise PipelineError("Eliza/Segmind request fields differ from the fixed route")
    return payload


def build_request_preview(
    sample: dict,
    prompt: dict,
    *,
    wan_submit_mode: str | None = None,
) -> dict[str, Any]:
    model_id = prompt["model_id"]
    config = MODEL_CONFIGS[model_id]
    route = route_for_model(model_id)
    if config["adapter"] == "eliza-segmind":
        if wan_submit_mode is not None:
            raise PipelineError(
                "alibaba/wan-2.2 uses only the canonical Eliza/Segmind route; "
                "Gradio submit modes are disabled"
            )
        return {
            "endpoint": route["paths"]["submit"],
            "model": model_id,
            "provider": route["provider_key"],
            "provider_model_id": route["provider_model_id"],
            "input": segmind_request_payload(sample, prompt),
        }
    if config["adapter"] == "wan-demo":
        if wan_submit_mode not in {None, "legacy", "named"}:
            raise PipelineError(
                f"Unsupported explicit Wan preview mode: {wan_submit_mode}"
            )
        runtime_prompt = prompt["positive_prompt"]
        if prompt.get("negative_prompt"):
            runtime_prompt = f"{runtime_prompt}\n\nAvoid: {prompt['negative_prompt']}"
        return {
            "endpoint": (
                route["diagnostic_only"]["submit_path"]
                if wan_submit_mode == "named"
                else route["paths"]["submit"]
            ),
            "model": model_id,
            "input": {
                "source_path": sample["source_path"],
                "prompt": runtime_prompt,
            },
            "runtime": {
                "resolution": config["resolution"],
                "seed": config["seed"],
                "loop": False,
                "frames": config["frames"],
                "fps": config["fps"],
            },
        }

    runtime_prompt = prompt["positive_prompt"]
    if prompt.get("embed_negative_in_positive") and prompt.get("negative_prompt"):
        runtime_prompt = f"{runtime_prompt}\n\nAvoid: {prompt['negative_prompt']}"

    payload: dict[str, Any] = {
        "model": model_id,
        "prompt": runtime_prompt,
        "duration": prompt.get("target_duration_seconds", config["duration"]),
        "resolution": config["resolution"],
        "aspect_ratio": choose_aspect_ratio(sample["width"], sample["height"], config["aspect_ratios"]),
        "seed": config["seed"],
        "generate_audio": config["generate_audio"],
        "frame_images": [
            {
                "type": "image_url",
                "image_url": {"url": sample["source_url"]},
                "frame_type": "first_frame",
            }
        ],
    }
    if prompt.get("last_frame_is_source"):
        payload["frame_images"].append(
            {
                "type": "image_url",
                "image_url": {"url": sample["source_url"]},
                "frame_type": "last_frame",
            }
        )
    provider_key = route["provider_key"]
    if model_id == "alibaba/wan-2.7":
        parameters: dict[str, Any] = {"prompt_extend": prompt.get("prompt_extend", False)}
        if not prompt.get("embed_negative_in_positive") and prompt.get("negative_prompt"):
            parameters["negative_prompt"] = prompt["negative_prompt"]
        payload["provider"] = {
            "options": {
                provider_key: {
                    "parameters": parameters
                }
            }
        }
    elif model_id == "google/veo-3.1-lite":
        parameters = {"enhancePrompt": True}
        if not prompt.get("embed_negative_in_positive") and prompt.get("negative_prompt"):
            parameters["negativePrompt"] = prompt["negative_prompt"]
        payload["provider"] = {
            "options": {
                provider_key: {
                    # The live Eliza/Google route rejects enhancePrompt=false.
                    "parameters": parameters
                }
            }
        }
    return payload


def http_json(
    method: str,
    url: str,
    payload: Any | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    for key, value in (headers or {}).items():
        request.add_unredirected_header(key, value)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        finally:
            exc.close()
        error = safe_error(
            f"{method} {url} failed with HTTP {exc.code}: {detail[:1000]}"
        )
        if (
            method.upper() == "POST"
            and exc.code in PRE_SUBMIT_REJECTED_HTTP_STATUSES
        ):
            # A quota rejection is a completed HTTP exchange: unlike a timeout,
            # it definitively rejected this request and created no provider job.
            raise PreSubmitRejectedError(error, exc.code) from exc
        raise PipelineError(error) from exc
    except URLError as exc:
        error = safe_error(f"{method} {url} failed: {exc.reason}")
        if isinstance(exc.reason, socket.gaierror):
            # getaddrinfo failed before a socket connection existed, so no
            # request bytes could have reached the non-idempotent endpoint.
            raise PreSubmitNetworkError(error) from exc
        raise PipelineError(error) from exc
    except socket.gaierror as exc:
        # urllib normally wraps this in URLError, but preserve the same strong
        # pre-submit guarantee for injected/custom openers as well.
        raise PreSubmitNetworkError(
            safe_error(f"{method} {url} failed: {exc}")
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PipelineError(f"{method} {url} returned invalid JSON") from exc


def http_download(url: str, destination: Path, headers: dict[str, str] | None = None, timeout: int = 600) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: BaseException | None = None
    for attempt in range(1, 4):
        request = _request_with_scoped_headers(
            url,
            method="GET",
            headers=headers,
        )
        temp_path: Path | None = None
        try:
            with urlopen(request, timeout=timeout) as response, tempfile.NamedTemporaryFile(
                "wb", dir=destination.parent, prefix=f".{destination.name}.", delete=False
            ) as handle:
                temp_path = Path(handle.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            if temp_path.stat().st_size == 0:
                raise PipelineError("Provider returned an empty video")
            temp_path.replace(destination)
            return
        except (HTTPError, URLError, OSError, PipelineError) as exc:
            last_error = exc
            if attempt < 3:
                print(f"  download interrupted; retrying ({attempt}/3)", flush=True)
                time.sleep(attempt)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()
    raise PipelineError(safe_error(f"Download failed after 3 attempts: {last_error}"))


def upload_wan_image(
    base_url: str,
    image_path: Path,
    timeout: int = 120,
    *,
    expected_sha256: str | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    boundary = f"----promopages-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{image_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    image_bytes = image_path.read_bytes()
    if expected_sha256 is not None:
        uploaded_sha256 = hashlib.sha256(image_bytes).hexdigest()
        if uploaded_sha256 != expected_sha256:
            raise PipelineError(
                f"Wan upload source digest changed: expected {expected_sha256}, got {uploaded_sha256}"
            )
    body = prefix + image_bytes + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = _request_with_scoped_headers(
        f"{base_url.rstrip('/')}{WAN_UPLOAD_ENDPOINT}",
        data=body,
        headers=headers,
        method="POST",
    )
    request.add_header(
        "Content-Type",
        f"multipart/form-data; boundary={boundary}",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise PipelineError(safe_error(f"Wan upload failed: {exc}")) from exc
    if not isinstance(result, list) or not result or not isinstance(result[0], str):
        raise PipelineError("Wan upload returned an unexpected payload")
    return result[0]


def parse_sse_data(event_block: str) -> dict[str, Any] | None:
    data_lines = [line[5:].strip() for line in event_block.splitlines() if line.startswith("data:")]
    if not data_lines or data_lines == ["null"]:
        return None
    try:
        value = json.loads("\n".join(data_lines))
    except json.JSONDecodeError as exc:
        raise PipelineError("Wan SSE returned invalid JSON") from exc
    return value if isinstance(value, dict) else None


def wan_wait_for_result(stream_base_url: str, session_hash: str, event_id: str, timeout: int) -> str:
    query = urlencode({"session_hash": session_hash})
    stream_url = f"{stream_base_url.rstrip('/')}{WAN_STREAM_ENDPOINT}?{query}"
    deadline = time.monotonic() + timeout
    reconnects = 0
    while time.monotonic() < deadline:
        request = Request(stream_url, method="GET")
        try:
            with urlopen(request, timeout=max(1, int(deadline - time.monotonic()))) as response:
                event_lines: list[str] = []
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        event_lines.append(line)
                        continue
                    if not event_lines:
                        continue
                    data = parse_sse_data("\n".join(event_lines))
                    event_lines = []
                    if not data:
                        continue
                    message = data.get("msg")
                    if message == "process_starts":
                        print(f"  Wan started; eta={data.get('eta')}", flush=True)
                    if message == "process_completed" and data.get("event_id") == event_id:
                        if not data.get("success"):
                            raise ProviderTerminalError(
                                safe_error((data.get("output") or {}).get("error") or data)
                            )
                        output_data = (data.get("output") or {}).get("data") or []
                        result = output_data[0] if output_data else None
                        if not isinstance(result, dict):
                            raise ProviderTerminalError("Wan completed without a video result")
                        if result.get("url"):
                            return result["url"]
                        if result.get("path"):
                            return urljoin(
                                stream_base_url.rstrip("/") + "/",
                                f"{WAN_FILE_PREFIX.lstrip('/')}{result['path']}",
                            )
                        raise ProviderTerminalError("Wan result has neither url nor path")
                    if message in {"unexpected_error", "close_stream"}:
                        raise ProviderTerminalError(
                            safe_error(f"Wan stream ended before completion: {data}")
                        )
        except PipelineError:
            raise
        except (HTTPError, URLError, OSError) as exc:
            reconnects += 1
            if time.monotonic() >= deadline:
                raise PipelineError(safe_error(f"Wan SSE failed after {reconnects} connection(s): {exc}")) from exc
            print(f"  Wan stream interrupted; reconnecting to the same session ({reconnects})", flush=True)
            time.sleep(min(5, reconnects))
            continue
        reconnects += 1
        print(f"  Wan stream closed; reconnecting to the same session ({reconnects})", flush=True)
        time.sleep(min(5, reconnects))
    raise PipelineError(f"Wan job did not finish within {timeout} seconds")


def _named_file_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if isinstance(value.get("url"), str) or isinstance(value.get("path"), str):
            return value
        for nested in value.values():
            result = _named_file_result(nested)
            if result is not None:
                return result
    if isinstance(value, list):
        for nested in value:
            result = _named_file_result(nested)
            if result is not None:
                return result
    return None


def wan_wait_for_named_result(
    base_url: str,
    event_id: str,
    timeout: int,
    *,
    headers: dict[str, str] | None = None,
) -> str:
    """Wait for the documented Gradio named-endpoint SSE result."""

    if not is_trusted_wan_dod_url(base_url):
        raise PipelineError(
            "Wan named API credentials may only be sent to HTTPS *.dod.yandex.net"
        )
    request_headers = wan_named_headers(base_url) if headers is None else headers
    result_path = "/gradio_api/call/text2video/{event_id}".format(
        event_id=quote(str(event_id), safe="")
    )
    result_url = f"{base_url.rstrip('/')}{result_path}"
    deadline = time.monotonic() + timeout
    reconnects = 0
    while time.monotonic() < deadline:
        request = _request_with_scoped_headers(
            result_url,
            method="GET",
            headers=request_headers,
        )
        try:
            with urlopen(
                request,
                timeout=max(1, int(deadline - time.monotonic())),
            ) as response:
                event_lines: list[str] = []

                def consume(lines: list[str]) -> str | None:
                    event_name = next(
                        (
                            line[6:].strip()
                            for line in lines
                            if line.startswith("event:")
                        ),
                        "",
                    )
                    data_lines = [
                        line[5:].strip()
                        for line in lines
                        if line.startswith("data:")
                    ]
                    payload: Any = None
                    if data_lines and data_lines != ["null"]:
                        try:
                            payload = json.loads("\n".join(data_lines))
                        except json.JSONDecodeError as exc:
                            raise PipelineError("Wan named SSE returned invalid JSON") from exc
                    if event_name in {"error", "unexpected_error"}:
                        raise ProviderTerminalError(
                            safe_error(
                                f"Wan named endpoint failed: "
                                f"{payload if payload is not None else 'no error detail'}"
                            )
                        )
                    if event_name == "complete" and payload is None:
                        raise ProviderTerminalError(
                            "Wan named endpoint completed without a video result"
                        )
                    if payload is None:
                        return None
                    if event_name != "complete":
                        return None
                    result = _named_file_result(payload)
                    if result is None:
                        raise ProviderTerminalError(
                            "Wan named endpoint completed without a video result"
                        )
                    if isinstance(result.get("url"), str) and result["url"]:
                        video_url = urljoin(
                            base_url.rstrip("/") + "/",
                            result["url"],
                        )
                        if _url_origin(video_url) is None:
                            raise ProviderTerminalError(
                                "Wan named result URL is not HTTP(S)"
                            )
                        return video_url
                    path = result.get("path")
                    if isinstance(path, str) and path:
                        return urljoin(
                            base_url.rstrip("/") + "/",
                            f"gradio_api/file={quote(path, safe='/')}",
                        )
                    raise ProviderTerminalError(
                        "Wan named result has neither url nor path"
                    )

                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        event_lines.append(line)
                        continue
                    if not event_lines:
                        continue
                    video_url = consume(event_lines)
                    event_lines = []
                    if video_url:
                        return video_url
                if event_lines:
                    video_url = consume(event_lines)
                    if video_url:
                        return video_url
        except PipelineError:
            raise
        except (HTTPError, URLError, OSError) as exc:
            reconnects += 1
            if time.monotonic() >= deadline:
                raise PipelineError(
                    safe_error(
                        f"Wan named SSE failed after {reconnects} connection(s): {exc}"
                    )
                ) from exc
            print(
                "  Wan named stream interrupted; reconnecting to the same event "
                f"({reconnects})",
                flush=True,
            )
            time.sleep(min(5, reconnects))
            continue
        reconnects += 1
        print(
            f"  Wan named stream closed; reconnecting to the same event ({reconnects})",
            flush=True,
        )
        time.sleep(min(5, reconnects))
    raise PipelineError(f"Wan named job did not finish within {timeout} seconds")


def wan_generate(
    sample: dict,
    prompt: dict,
    destination: Path,
    base_url: str,
    stream_base_url: str,
    timeout: int,
    resume: dict[str, Any] | None,
    on_submitted: Callable[[str, str], None],
    *,
    allow_resubmit_after_missing_session: bool = True,
    on_submitting: Callable[[], None] | None = None,
    submit_mode: str | None = None,
) -> None:
    if submit_mode not in {None, "legacy", "named"}:
        raise PipelineError(f"Unsupported explicit Wan submit mode: {submit_mode}")
    event_id = (resume or {}).get("provider_job_id")
    session_hash = (resume or {}).get("provider_session_hash")
    resumed_named_job = session_hash == WAN_NAMED_SESSION_MARKER
    if event_id and session_hash and submit_mode is not None:
        resumed_mode = "named" if resumed_named_job else "legacy"
        if submit_mode != resumed_mode:
            raise PipelineError(
                f"Wan resume route is {resumed_mode}, not requested {submit_mode}; "
                "automatic route fallback is disabled"
            )
    # New normal runs always use the registry's proven legacy queue.  The named
    # endpoint remains available only through an explicit diagnostic opt-in or
    # to finish a receipt that was already submitted there.
    named_api = resumed_named_job or (not event_id and submit_mode == "named")
    named_request_headers = wan_named_headers(base_url) if named_api else None
    resubmitted_after_missing_session = False
    while True:
        if not event_id or not session_hash:
            image_path = ROOT / sample["source_path"]
            server_path = upload_wan_image(
                base_url,
                image_path,
                expected_sha256=sample.get("sha256"),
                headers=named_request_headers,
            )
            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
            # Frozen compatibility for historical Gradio receipts only.  The
            # canonical alibaba/wan-2.2 route is Segmind and never reaches this
            # helper or inherits these retired parameters.
            config = {
                "resolution": "720p",
                "seed": 1,
                "frames": 97,
                "fps": 30,
            }
            file_data = {
                "path": server_path,
                "orig_name": image_path.name,
                "mime_type": mime_type,
                "is_stream": False,
                "meta": {"_type": "gradio.FileData"},
            }
            combined_prompt = prompt["positive_prompt"]
            if prompt.get("negative_prompt"):
                combined_prompt = f"{combined_prompt}\n\nAvoid: {prompt['negative_prompt']}"
            values = {
                "prompt": combined_prompt,
                "image_file_data": file_data,
                "resolution": config["resolution"],
                "seed": config["seed"],
                "loop": False,
                "last_frame": None,
                "frames": config["frames"],
                "fps": config["fps"],
            }
            data = [
                values[name]
                for name in (
                    "prompt",
                    "image_file_data",
                    "resolution",
                    "seed",
                    "loop",
                    "last_frame",
                    "frames",
                    "fps",
                )
            ]
            if on_submitting is not None:
                on_submitting()
            if named_api:
                payload = {"data": data}
                submit_url = f"{base_url.rstrip('/')}{WAN_NAMED_ENDPOINT}"
                session_hash = WAN_NAMED_SESSION_MARKER
            else:
                session_hash = f"promopages9856-{uuid.uuid4().hex[:12]}"
                payload = {
                    "data": data,
                    "event_data": None,
                    "fn_index": 0,
                    "trigger_id": 19,
                    "session_hash": session_hash,
                }
                submit_url = f"{base_url.rstrip('/')}{WAN_LEGACY_ENDPOINT}"
            response = http_json(
                "POST",
                submit_url,
                payload,
                headers=named_request_headers,
                timeout=120,
            )
            event_id = response.get("event_id") if isinstance(response, dict) else None
            if not event_id:
                route = "named endpoint" if named_api else "queue/join"
                raise PipelineError(f"Wan {route} did not return event_id")
            on_submitted(event_id, session_hash)
        try:
            if named_api:
                video_url = wan_wait_for_named_result(
                    base_url,
                    event_id,
                    timeout,
                    headers=named_request_headers,
                )
            else:
                # Preserve resumability for receipts created by the legacy
                # queue/join route before the named endpoint was exposed.
                video_url = wan_wait_for_result(
                    stream_base_url,
                    session_hash,
                    event_id,
                    timeout,
                )
            break
        except PipelineError as exc:
            if (
                named_api
                or
                "session_not_found" not in str(exc).lower()
                or resubmitted_after_missing_session
                or not allow_resubmit_after_missing_session
            ):
                raise
            print("  Wan session was dropped; resubmitting this item once", flush=True)
            resubmitted_after_missing_session = True
            event_id = None
            session_hash = None
    download_headers = (
        named_request_headers
        if named_api and _same_origin(base_url, video_url)
        else None
    )
    http_download(
        video_url,
        destination,
        headers=download_headers,
        timeout=600,
    )


def find_status(value: Any) -> str | None:
    if isinstance(value, dict):
        direct = value.get("status") or value.get("state")
        if isinstance(direct, str):
            return direct.lower()
        for key in ("response", "data", "result", "job", "video"):
            nested = find_status(value.get(key))
            if nested:
                return nested
    return None


def find_error_detail(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("error", "error_message", "message", "detail"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            nested = find_error_detail(candidate)
            if nested:
                return nested
        for key in ("response", "data", "result", "job", "video"):
            nested = find_error_detail(value.get(key))
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = find_error_detail(item)
            if nested:
                return nested
    return None


def find_job_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("id", "job_id", "jobId", "generation_id"):
            if isinstance(value.get(key), str) and value[key]:
                return value[key]
        for key in ("response", "data", "result", "job"):
            nested = find_job_id(value.get(key))
            if nested:
                return nested
    return None


def find_video_url(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("video_url", "videoUrl", "download_url", "downloadUrl"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                return candidate
        candidate = value.get("url")
        if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
            path = urlparse(candidate).path.lower()
            if any(suffix in path for suffix in (".mp4", "/content", "/download")):
                return candidate
        for key in (
            "response",
            "data",
            "result",
            "output",
            "outputs",
            "videos",
            "video",
            "unsigned_urls",
        ):
            nested = find_video_url(value.get(key))
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = find_video_url(item)
            if nested:
                return nested
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        path = urlparse(value).path.lower()
        if any(suffix in path for suffix in (".mp4", "/content", "/download")):
            return value
    return None


def eliza_headers(token: str | None = None) -> dict[str, str]:
    resolved = (
        token
        or os.environ.get("ELIZA_OAUTH_TOKEN")
        or os.environ.get("ELIZA_TOKEN")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if not resolved:
        raise PipelineError(
            "Set ELIZA_OAUTH_TOKEN, ELIZA_TOKEN, or the configured "
            "ANTHROPIC_AUTH_TOKEN before a real Eliza run"
        )
    return {"Authorization": f"OAuth {resolved}", "X-Retries": "1"}


def segmind_headers(token: str | None = None) -> dict[str, str]:
    """Return the exact single-attempt headers for synchronous Segmind."""

    route_headers = route_for_model("alibaba/wan-2.2")["request_headers"]
    headers = {
        **eliza_headers(token),
        "Accept": route_headers["accept"],
        "X-Retries": route_headers["x_retries"],
        "X-Include-Cost": route_headers["x_include_cost"],
    }
    pool = os.environ.get("ELIZA_POOL") or os.environ.get("YA_POOL")
    if pool:
        headers["Ya-Pool"] = pool
    return headers


def verify_remote_source_digest(
    source_url: str,
    expected_sha256: str,
    *,
    timeout: int = 120,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Read the public source once and prove the bytes bound to the request."""

    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise PipelineError("Eliza/Segmind source URL must be absolute HTTPS")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise PipelineError("Eliza/Segmind source SHA-256 is invalid")
    request = Request(source_url, headers={"Accept": "image/*"}, method="GET")
    digest = hashlib.sha256()
    size = 0
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
    except HTTPError as exc:
        raise PipelineError(f"Eliza/Segmind source preflight failed with HTTP {exc.code}") from exc
    except (URLError, OSError) as exc:
        raise PipelineError(safe_error(f"Eliza/Segmind source preflight failed: {exc}")) from exc
    if status != 200:
        raise PipelineError(f"Eliza/Segmind source preflight returned HTTP {status}")
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise PipelineError(
            "Eliza/Segmind source preflight digest changed: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    return {"http_status": status, "bytes": size, "sha256": actual_sha256}


class RejectNonIdempotentRedirects(HTTPRedirectHandler):
    """Never replay the synchronous paid POST at a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def segmind_generate(
    sample: dict,
    prompt: dict,
    destination: Path,
    base_url: str,
    timeout: int,
    on_submitting: Callable[[dict[str, Any]], None],
    *,
    source_opener: Callable[..., Any] = urlopen,
    post_opener: Any | None = None,
) -> dict[str, Any]:
    """Perform the one synchronous Eliza -> Segmind request without retries."""

    if prompt.get("model_id") != "alibaba/wan-2.2":
        raise PipelineError("Segmind transport only accepts canonical alibaba/wan-2.2")
    route = route_for_model("alibaba/wan-2.2")
    if (
        route.get("adapter") != "eliza-segmind"
        or route.get("automatic_retry") is not False
        or route.get("synchronous") is not True
    ):
        raise PipelineError("Canonical Eliza/Segmind route contract changed")

    headers = segmind_headers()
    preflight = verify_remote_source_digest(
        sample["source_url"],
        sample["sha256"],
        timeout=min(timeout, 120),
        opener=source_opener,
    )
    payload = segmind_request_payload(sample, prompt)
    on_submitting(preflight)

    submit_url = generation_route_url(base_url, "alibaba/wan-2.2", "submit")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = _request_with_scoped_headers(
        submit_url,
        method="POST",
        headers=headers,
        data=body,
    )
    request.add_header("Content-Type", "application/json")
    client = post_opener or build_opener(RejectNonIdempotentRedirects())
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with client.open(request, timeout=timeout) as response, tempfile.NamedTemporaryFile(
            "wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
            status = int(getattr(response, "status", 200))
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            request_id = response.headers.get(SEGMIND_REQUEST_ID_HEADER)
            response_cost = response.headers.get(SEGMIND_COST_HEADER)
        if status != 200:
            error = f"Eliza/Segmind returned HTTP {status}"
            if status in PRE_SUBMIT_REJECTED_HTTP_STATUSES:
                raise PreSubmitRejectedError(error, status)
            raise PipelineError(error)
        if content_type not in SEGMIND_CONTENT_TYPES:
            raise PipelineError(
                "Eliza/Segmind returned unexpected Content-Type: "
                f"{content_type or '[missing]'}"
            )
        if not request_id:
            raise PipelineError(f"Eliza/Segmind response has no {SEGMIND_REQUEST_ID_HEADER}")
        if temporary.stat().st_size == 0:
            raise PipelineError("Eliza/Segmind returned an empty MP4")
        temporary.replace(destination)
        temporary = None
        return {
            "http_status": status,
            "content_type": content_type,
            "request_id": request_id,
            "response_cost": response_cost,
            "automatic_retry": False,
        }
    except HTTPError as exc:
        try:
            raw_detail = exc.read(65537)
        finally:
            exc.close()
        detail = raw_detail[:1000].decode("utf-8", errors="replace")
        error = safe_error(
            f"Eliza/Segmind POST failed with HTTP {exc.code}: {detail}"
        )
        if exc.code in PRE_SUBMIT_REJECTED_HTTP_STATUSES:
            raise PreSubmitRejectedError(error, exc.code) from exc
        exact_detail = None
        if len(raw_detail) <= 65536:
            try:
                exact_detail = raw_detail.decode("utf-8")
            except UnicodeDecodeError:
                pass
        evidence = None
        if exact_detail is not None:
            evidence = parse_segmind_oversize_task_failure(
                exc.code, exact_detail
            ) or parse_segmind_undersize_task_failure(exc.code, exact_detail)
        if evidence is not None:
            raise SegmindProviderTaskFailedError(error, evidence) from exc
        raise PipelineError(error) from exc
    except (URLError, OSError) as exc:
        raise PipelineError(safe_error(f"Eliza/Segmind POST failed: {exc}")) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def generation_route_url(
    base_url: str,
    model_id: str,
    path_name: str,
    *,
    job_id: str | None = None,
) -> str:
    """Build one URL from the exact route registry, never by endpoint probing."""

    route = route_for_model(model_id)
    paths = route["paths"]
    if path_name not in paths:
        raise PipelineError(f"Route {model_id} has no path named {path_name}")
    path = paths[path_name]
    if "{job_id}" in path:
        if job_id is None:
            raise PipelineError(f"Route path {model_id}.{path_name} requires job_id")
        path = path.format(job_id=quote(str(job_id), safe=""))
    elif job_id is not None:
        raise PipelineError(f"Route path {model_id}.{path_name} does not accept job_id")
    return f"{base_url.rstrip('/')}{path}"


def eliza_poll(
    base_url: str,
    job_id: str,
    headers: dict[str, str],
    timeout: int,
    interval: float,
    *,
    model_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    status_url = generation_route_url(
        base_url,
        model_id,
        "status_template",
        job_id=job_id,
    )
    while time.monotonic() < deadline:
        response = http_json("GET", status_url, headers=headers, timeout=120)
        status = find_status(response)
        print(f"  Eliza/OpenRouter job {job_id}: {status or 'unknown'}", flush=True)
        if status in TERMINAL_SUCCESS or (find_video_url(response) and status not in TERMINAL_FAILURE):
            return response
        if status in TERMINAL_FAILURE:
            detail = find_error_detail(response)
            suffix = f": {detail}" if detail else ""
            raise ProviderTerminalError(
                safe_error(f"Eliza/OpenRouter job {job_id} failed with status {status}{suffix}")
            )
        time.sleep(interval)
    raise PipelineError(f"Eliza/OpenRouter job {job_id} did not finish within {timeout} seconds")


def eliza_generate(
    sample: dict,
    prompt: dict,
    destination: Path,
    base_url: str,
    timeout: int,
    poll_interval: float,
    resume: dict[str, Any] | None,
    on_submitted: Callable[[str, str | None], None],
) -> None:
    headers = eliza_headers()
    model_id = prompt["model_id"]
    job_id = (resume or {}).get("provider_job_id")
    if not job_id:
        payload = build_request_preview(sample, prompt)
        response = http_json(
            "POST",
            generation_route_url(base_url, model_id, "submit"),
            payload,
            headers=headers,
            timeout=120,
        )
        job_id = find_job_id(response)
        if not job_id:
            raise PipelineError("Eliza/OpenRouter submit response did not contain a job ID")
        on_submitted(job_id, None)
    eliza_poll(
        base_url,
        job_id,
        headers,
        timeout,
        poll_interval,
        model_id=model_id,
    )
    content_url = generation_route_url(
        base_url,
        model_id,
        "content_template",
        job_id=job_id,
    )
    http_download(content_url, destination, headers=headers, timeout=600)


def ffprobe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        process = subprocess.run(command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise PipelineError("ffprobe is required to validate generated MP4 files") from exc
    if process.returncode != 0:
        raise PipelineError(safe_error(f"ffprobe failed for {path}: {process.stderr.strip()}"))
    try:
        probe = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise PipelineError(f"ffprobe returned invalid JSON for {path}") from exc
    streams = probe.get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video:
        raise PipelineError(f"Generated file has no video stream: {path}")
    duration_value = video.get("duration") or (probe.get("format") or {}).get("duration")
    try:
        duration = round(float(duration_value), 3)
    except (TypeError, ValueError) as exc:
        raise PipelineError(f"Generated file has no readable duration: {path}") from exc
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    try:
        fps = round(float(Fraction(rate)), 3)
    except (ValueError, ZeroDivisionError):
        fps = None
    return {
        "container": (probe.get("format") or {}).get("format_name"),
        "codec": video.get("codec_name"),
        "duration_seconds": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": fps,
        "frames": int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else None,
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def assess_contract(
    model_id: str,
    media: dict[str, Any],
    target_duration_seconds: float | int | None = None,
) -> dict[str, Any]:
    config = MODEL_CONFIGS[model_id]
    requested_duration = config["duration"] if target_duration_seconds is None else target_duration_seconds
    target_duration = float(requested_duration)
    actual_duration = float(media.get("duration_seconds") or 0)
    checks: dict[str, bool] = {
        "duration": abs(actual_duration - target_duration) <= 0.1,
        "audio": bool(media.get("has_audio")) == bool(config["generate_audio"]),
    }
    if model_id == "alibaba/wan-2.2":
        checks["frames"] = media.get("frames") == config["frames"]
        checks["fps"] = abs(float(media.get("fps") or 0) - float(config["fps"])) <= 0.01
    warnings: list[str] = []
    if not checks["duration"]:
        warnings.append(
            f"actual duration {actual_duration}s differs from requested {target_duration}s"
        )
    if not checks["audio"]:
        warnings.append(
            f"provider returned has_audio={bool(media.get('has_audio'))} despite generate_audio={config['generate_audio']}"
        )
    if checks.get("frames") is False:
        warnings.append(f"actual frame count {media.get('frames')} differs from requested {config['frames']}")
    if checks.get("fps") is False:
        warnings.append(f"actual fps {media.get('fps')} differs from requested {config['fps']}")
    return {
        "requested": {
            "duration_seconds": requested_duration,
            "resolution": config["resolution"],
            "generate_audio": config["generate_audio"],
            "frames": config.get("frames"),
            "fps": config.get("fps"),
        },
        "checks": checks,
        "conforms": all(checks.values()),
        "warnings": warnings,
    }


def write_aggregate_manifest(rows: list[dict[str, Any]], root: Path = ROOT) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for row in rows:
        run_path = row["paths"]["run"]
        run = read_json(run_path) if run_path.exists() else {"status": "missing"}
        status = run.get("status", "missing")
        counts[status] = counts.get(status, 0) + 1
        media = run.get("media")
        contract_check = run.get("contract_check")
        acceptance = (
            media_acceptance(row["prompt"]["model_id"], media, contract_check)
            if isinstance(media, dict) and isinstance(contract_check, dict)
            else None
        )
        outputs.append(
            {
                "sample_id": row["sample"]["sample_id"],
                "article_slug": row["sample"]["article_slug"],
                "image_id": row["sample"]["image_id"],
                "model_id": row["prompt"]["model_id"],
                "status": status,
                "prompt_path": relative(row["paths"]["prompt"], root),
                "run_path": relative(run_path, root),
                "video_path": relative(row["paths"]["video"], root),
                "media": media,
                "contract_check": contract_check,
                "media_acceptance": acceptance,
                "error": run.get("error"),
            }
        )
    manifest = {
        "schema_version": 1,
        "ticket": "PROMOPAGES-9856",
        "updated_at": utc_now(),
        "expected_outputs": EXPECTED_RESULT_COUNT,
        "summary": counts,
        "outputs": outputs,
    }
    atomic_write_json(root / "PROMOPAGES-9857/video-generation-manifest.json", manifest)
    return manifest


def select_rows(rows: list[dict[str, Any]], sample_ids: list[str], model_ids: list[str]) -> list[dict[str, Any]]:
    unknown_samples = set(sample_ids) - {row["sample"]["sample_id"] for row in rows}
    unknown_models = set(model_ids) - set(MODEL_CONFIGS)
    if unknown_samples:
        raise PipelineError(f"Unknown sample filters: {', '.join(sorted(unknown_samples))}")
    if unknown_models:
        raise PipelineError(f"Unknown model filters: {', '.join(sorted(unknown_models))}")
    return [
        row
        for row in rows
        if (not sample_ids or row["sample"]["sample_id"] in sample_ids)
        and (not model_ids or row["prompt"]["model_id"] in model_ids)
    ]


def run_rows(
    rows: list[dict[str, Any]],
    args: argparse.Namespace,
    root: Path = ROOT,
    manifest_writer: Callable[[], None] | None = None,
) -> int:
    failures = 0
    for index, row in enumerate(rows, start=1):
        sample, prompt, paths = row["sample"], row["prompt"], row["paths"]
        run = read_json(paths["run"])
        adapter = MODEL_CONFIGS[prompt["model_id"]]["adapter"]
        label = f"{sample['sample_id']} / {prompt['model_id']}"
        print(f"[{index}/{len(rows)}] {label}", flush=True)
        request_preview = build_request_preview(sample, prompt)
        request_sha256 = request_fingerprint(request_preview, sample)
        if run.get("status") == "succeeded" and paths["video"].is_file() and not args.force:
            print("  already succeeded; skipping", flush=True)
            continue
        if run.get("status") == "stale" and not args.force:
            failures += 1
            print("  stale output; review the request diff and rerun with --force", file=sys.stderr, flush=True)
            continue
        if adapter == "eliza-segmind" and run.get("status") in {
            "submitting",
            "submit-unknown",
        }:
            failures += 1
            if run.get("status") == "submitting":
                run.update(
                    {
                        "status": "submit-unknown",
                        "provider_may_be_active": True,
                        "error": "Previous synchronous submit outcome is unknown; automatic retry is blocked",
                    }
                )
                atomic_write_json(paths["run"], run)
            print(
                "  synchronous submit outcome is unknown; automatic retry is blocked",
                file=sys.stderr,
                flush=True,
            )
            continue
        if args.dry_run:
            run.update(
                {
                    "status": "dry-run",
                    "request": request_preview,
                    "request_sha256": request_sha256,
                    "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
                    "provider_job_id": None,
                    "provider_session_hash": None,
                    "submitted_at": None,
                    "completed_at": None,
                    "media": None,
                    "contract_check": None,
                    "error": None,
                }
            )
            atomic_write_json(paths["run"], run)
            print("  request validated; no network call", flush=True)
            continue

        resume = run if run.get("status") in {"submitted", "running"} and not args.force else None
        run.update(
            {
                "status": (
                    "running"
                    if resume
                    else "preparing"
                    if adapter == "eliza-segmind"
                    else "prepared"
                ),
                "request": request_preview,
                "request_sha256": request_sha256,
                "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
                "error": None,
                "media": None,
            }
        )
        if not resume:
            run.update(
                {
                    "provider_job_id": None,
                    "provider_session_hash": None,
                    "submitted_at": None,
                    "completed_at": None,
                }
            )
        atomic_write_json(paths["run"], run)

        def on_submitted(job_id: str, session_hash: str | None) -> None:
            run.update(
                {
                    "status": "submitted",
                    "provider_job_id": job_id,
                    "provider_session_hash": session_hash,
                    "submitted_at": utc_now(),
                }
            )
            atomic_write_json(paths["run"], run)
            print(f"  submitted as {job_id}", flush=True)

        def on_segmind_submitting(source_preflight: dict[str, Any]) -> None:
            run.update(
                {
                    "status": "submitting",
                    "source_preflight": source_preflight,
                    "provider_may_be_active": True,
                    "error": None,
                }
            )
            atomic_write_json(paths["run"], run)

        try:
            if adapter == "eliza-segmind":
                if resume:
                    if not paths["video"].is_file():
                        raise PipelineError(
                            "Synchronous Eliza/Segmind response has no resumable MP4; resubmit is blocked"
                        )
                else:
                    response = segmind_generate(
                        sample,
                        prompt,
                        paths["video"],
                        args.segmind_base_url,
                        args.timeout,
                        on_segmind_submitting,
                    )
                    request_id = response.get("request_id")
                    if not isinstance(request_id, str) or not request_id:
                        raise PipelineError(
                            "Eliza/Segmind completed without a provider request ID"
                        )
                    run.update(
                        {
                            "status": "running",
                            "provider_job_id": request_id,
                            "provider_session_hash": None,
                            "provider_response": response,
                            "provider_may_be_active": False,
                            "submitted_at": utc_now(),
                        }
                    )
                    atomic_write_json(paths["run"], run)
            elif adapter == "wan-demo":
                wan_generate(
                    sample,
                    prompt,
                    paths["video"],
                    args.wan_base_url,
                    args.wan_stream_base_url,
                    args.timeout,
                    resume,
                    on_submitted,
                )
            elif adapter == "eliza-openrouter":
                eliza_generate(
                    sample,
                    prompt,
                    paths["video"],
                    args.eliza_base_url,
                    args.timeout,
                    args.poll_interval,
                    resume,
                    on_submitted,
                )
            else:
                raise PipelineError(f"Unsupported adapter: {adapter}")
            media = ffprobe_media(paths["video"])
            run.update(
                {
                    "status": "succeeded",
                    "completed_at": utc_now(),
                    "media": media,
                    "contract_check": assess_contract(
                        prompt["model_id"],
                        media,
                        prompt["target_duration_seconds"],
                    ),
                    "error": None,
                }
            )
            atomic_write_json(paths["run"], run)
            print(
                f"  saved {relative(paths['video'], root)} "
                f"({media['width']}x{media['height']}, {media['duration_seconds']}s, {media['bytes']} bytes)",
                flush=True,
            )
        except Exception as exc:  # Keep the rest of the 15-item matrix resumable.
            failures += 1
            error = safe_error(exc)
            if adapter == "eliza-segmind" and run.get("status") == "submitting":
                failure_status = "submit-unknown"
                resumable = False
            elif adapter == "eliza-segmind" and not run.get("provider_job_id"):
                failure_status = "failed-pre-submit"
                resumable = False
            else:
                resumable = bool(run.get("provider_job_id")) and not any(
                    marker in error.lower() for marker in ("failed with status", "cancelled", "canceled", "expired")
                )
                failure_status = "submitted" if resumable else "failed"
            run.update(
                {
                    "status": failure_status,
                    "completed_at": (
                        None
                        if resumable or failure_status == "submit-unknown"
                        else utc_now()
                    ),
                    "provider_may_be_active": failure_status == "submit-unknown",
                    "error": error,
                }
            )
            atomic_write_json(paths["run"], run)
            print(f"  failed: {run['error']}", file=sys.stderr, flush=True)
            if args.fail_fast:
                break
        finally:
            if manifest_writer is None:
                write_aggregate_manifest(materialized_rows_without_rewrite(root), root)
            else:
                manifest_writer()
    return failures


def materialized_rows_without_rewrite(root: Path = ROOT) -> list[dict[str, Any]]:
    samples, prompts = validate_catalogs(
        root / "PROMOPAGES-9857/video-samples.json",
        root / "PROMOPAGES-9857/video-prompts.json",
        root,
    )
    sample_by_id = {sample["sample_id"]: sample for sample in samples}
    return [
        {
            "sample": sample_by_id[prompt["sample_id"]],
            "prompt": prompt,
            "paths": artifact_paths(root, sample_by_id[prompt["sample_id"]], prompt["model_id"]),
        }
        for prompt in sorted(prompts, key=lambda value: (value["sample_id"], value["model_id"]))
    ]


def verify_materialized(root: Path = ROOT, allow_incomplete: bool = False) -> tuple[bool, list[str]]:
    rows = materialized_rows_without_rewrite(root)
    errors: list[str] = []
    succeeded = 0
    for row in rows:
        paths = row["paths"]
        label = f"{row['sample']['sample_id']} / {row['prompt']['model_id']}"
        if not paths["prompt"].is_file() or not paths["run"].is_file():
            errors.append(f"Missing prompt/run artifact: {label}")
            continue
        expected_prompt = prompt_artifact(row["sample"], row["prompt"], root)
        if read_json(paths["prompt"]) != expected_prompt:
            errors.append(f"Materialized prompt does not match its catalog record: {label}")
        run = read_json(paths["run"])
        if run.get("status") != "succeeded":
            if not allow_incomplete:
                errors.append(f"Not succeeded ({run.get('status')}): {label}")
            continue
        expected_request = build_request_preview(row["sample"], row["prompt"])
        expected_request_sha256 = request_fingerprint(expected_request, row["sample"])
        if run.get("request") != expected_request:
            errors.append(f"Recorded request does not match current prompt/runtime: {label}")
        if run.get("request_sha256") != expected_request_sha256:
            errors.append(f"Recorded request fingerprint mismatch: {label}")
        if run.get("request_fingerprint_version") != REQUEST_FINGERPRINT_VERSION:
            errors.append(f"Recorded request fingerprint version mismatch: {label}")
        if not paths["video"].is_file():
            errors.append(f"Succeeded run has no MP4: {label}")
            continue
        try:
            media = ffprobe_media(paths["video"])
        except PipelineError as exc:
            errors.append(str(exc))
            continue
        recorded = run.get("media") or {}
        if media["sha256"] != recorded.get("sha256") or media["bytes"] != recorded.get("bytes"):
            errors.append(f"Recorded media digest/size mismatch: {label}")
        expected_contract = assess_contract(
            row["prompt"]["model_id"],
            media,
            row["prompt"]["target_duration_seconds"],
        )
        if run.get("contract_check") != expected_contract:
            errors.append(f"Recorded contract check mismatch: {label}")
        acceptance = media_acceptance(
            row["prompt"]["model_id"],
            media,
            expected_contract,
        )
        if not acceptance["accepted"]:
            warnings = expected_contract.get("warnings") or ["unknown contract failure"]
            errors.append(f"Media contract failed ({', '.join(warnings)}): {label}")
        elif run.get("contract_check") == expected_contract:
            succeeded += 1
    if not allow_incomplete and succeeded != EXPECTED_RESULT_COUNT:
        errors.append(f"Expected {EXPECTED_RESULT_COUNT} succeeded outputs, got {succeeded}")
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan", help="validate catalogs and materialize 15 prompt/run artifacts")

    run_parser = subparsers.add_parser("run", help="generate or resume video outputs")
    run_parser.add_argument("--sample", action="append", default=[], help="sample_id filter; repeatable")
    run_parser.add_argument("--model", action="append", default=[], help="exact model_id filter; repeatable")
    run_parser.add_argument("--dry-run", action="store_true", help="materialize sanitized requests without network calls")
    run_parser.add_argument("--force", action="store_true", help="regenerate outputs that already succeeded")
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument("--timeout", type=int, default=1800, help="per-job wait timeout in seconds")
    run_parser.add_argument("--poll-interval", type=float, default=10.0)
    run_parser.add_argument(
        "--segmind-base-url",
        default=os.environ.get("ELIZA_SEGMIND_BASE_URL", DEFAULT_SEGMIND_BASE_URL),
        help="Wan 2.2 / Segmind base URL (normal route is fixed by the registry)",
    )
    run_parser.add_argument(
        "--wan-base-url",
        default=os.environ.get("WAN_DEMO_BASE_URL"),
        help="historical Gradio wrapper only; canonical Wan 2.2 does not use it",
    )
    run_parser.add_argument(
        "--wan-stream-base-url",
        default=os.environ.get("WAN_DEMO_STREAM_BASE_URL"),
        help="historical Gradio wrapper only; canonical Wan 2.2 does not use it",
    )
    run_parser.add_argument(
        "--eliza-base-url", default=os.environ.get("ELIZA_OPENROUTER_BASE_URL", DEFAULT_ELIZA_BASE_URL)
    )

    verify_parser = subparsers.add_parser("verify", help="verify catalogs, run artifacts, and generated MP4 files")
    verify_parser.add_argument("--allow-incomplete", action="store_true", help="allow pending/dry-run/failed matrix entries")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            rows = materialize_plan()
            print(f"PASS: materialized {len(rows)} prompt/run pairs")
            return 0
        if args.command == "run":
            rows = materialize_plan()
            selected = select_rows(rows, args.sample, args.model)
            if not selected:
                raise PipelineError("Filters selected no matrix entries")
            failures = run_rows(selected, args)
            write_aggregate_manifest(materialized_rows_without_rewrite())
            if failures:
                print(f"FAIL: {failures} generation(s) failed", file=sys.stderr)
                return 1
            print(f"PASS: processed {len(selected)} generation(s)")
            return 0
        if args.command == "verify":
            validate_catalogs(DEFAULT_SAMPLES, DEFAULT_PROMPTS)
            passed, errors = verify_materialized(allow_incomplete=args.allow_incomplete)
            if not passed:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print("PASS: video pipeline artifacts are valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except PipelineError as exc:
        print(f"error: {safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
