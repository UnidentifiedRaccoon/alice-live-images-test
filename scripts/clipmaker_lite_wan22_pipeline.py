#!/usr/bin/env python3
"""Plan, run, and verify the PROMOPAGES-9891 Wan 2.2 control jobs.

This is deliberately not a Clipmaker Lite model route.  It consumes prompts
from verified ``alibaba/wan-2.7`` Lite results and sends them unchanged to the
wan-streamlit Gradio queue as a separate, resumable control.  Generated
artifacts are therefore always stamped with ``attested_lite_model: false``.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


SCHEMA_VERSION = 1
EXPECTED_JOB_COUNT = 5
TARGET_MODEL_ID = "alibaba/wan-2.2"
PROMPT_SOURCE_MODEL_ID = "alibaba/wan-2.7"
PROVIDER_ROUTE = "wan-streamlit"
ATTESTED_LITE_MODEL = False
OUTPUT_SUBDIRECTORY = Path("clipmaker-lite/wan-streamlit-wan-2.2")
DEFAULT_CONTROL_MANIFEST = Path(
    "artifacts/clipmaker-lite-controls/promopages-9891-wan-streamlit-wan-2.2.json"
)
DEFAULT_SOURCE_GLOB = (
    "artifacts/clipmaker-lite/v1/"
    "promopages-9891-schemafix-*-wan-2-7/result.json"
)
WAN_BASE_URL = "https://wan-streamlit.dod.yandex.net"
WAN_STREAM_BASE_URL = "http://wan-streamlit.dod.yandex.net"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

EXPECTED_SOURCE_PATHS = (
    "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/02.jpeg",
    "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/05.png",
    "PROMOPAGES-9857/articles/06-4lapy-koshachii-napolnitel/03.jpeg",
    "PROMOPAGES-9857/articles/13-ilinka-elitnyi-zhk/09.png",
    "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/04.png",
)

RUNTIME = {
    "resolution": "720p",
    "frames": 97,
    "fps": 30,
    "seed": 1,
    "loop": False,
    "last_frame": None,
}

ProvenanceVerifier = Callable[[Path, str], dict[str, Any]]
MediaProbe = Callable[[Path], dict[str, Any]]
ProviderSubmitter = Callable[[Path, str, dict[str, Any], int], tuple[str, str]]
ProviderWaiter = Callable[[str, str, int, Callable[[], None]], str]
ProviderDownloader = Callable[[str, Path, int], None]


class Wan22ControlError(RuntimeError):
    """A fail-closed validation or execution error."""


class ResumableProviderError(Wan22ControlError):
    """A submitted provider job can be resumed with its persisted queue IDs."""


class ProviderSessionLostError(Wan22ControlError):
    """The provider explicitly discarded a persisted queue session."""


@contextmanager
def manifest_run_lock(manifest_path: Path):
    """Hold one fail-fast advisory run lock on the immutable manifest inode."""

    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise Wan22ControlError(f"control manifest cannot be locked: {manifest_path}")
    with manifest_path.open("rb") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Wan22ControlError(
                "another Wan 2.2 control process already holds this manifest run lock"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Wan22ControlError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> Any:
    if not path.is_file() or path.is_symlink():
        raise Wan22ControlError(f"{label} is missing, not a file, or a symlink: {path}")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                Wan22ControlError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Wan22ControlError(f"could not read {label}: {path}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_immutable_json(path: Path, value: Any, label: str) -> None:
    payload = canonical_json_bytes(value)
    if path.exists():
        if not path.is_file() or path.is_symlink():
            raise Wan22ControlError(f"existing {label} is not a regular file: {path}")
        if path.read_bytes() != payload:
            raise Wan22ControlError(f"existing {label} differs; refusing to overwrite: {path}")
        return
    atomic_write_json(path, value)


def workspace_relative(root: Path, path: Path, label: str) -> str:
    root = root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise Wan22ControlError(f"{label} escapes the workspace: {path}") from exc


def resolve_workspace_path(root: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise Wan22ControlError(f"{label} must be a non-empty workspace-relative path")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise Wan22ControlError(f"{label} must be workspace-relative")
    resolved = (root / candidate).resolve()
    workspace_relative(root, resolved, label)
    return resolved


def safe_error(value: Any) -> str:
    """Return a short diagnostic without provider URLs or credential values."""

    message = str(value)
    message = re.sub(r"https?://[^\s\]\[{}<>'\"]+", "[REDACTED_URL]", message)
    message = re.sub(
        r"(?i)\bauthorization\b\s*[:=]\s*(?:(?:oauth|bearer)\s+)?[^\s,;]+",
        "Authorization=[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?i)\b(authorization|oauth|bearer|api[-_]?key|token|signature|sig)\b"
        r"\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?i)([?&](?:token|signature|sig|key)=)[^&\s]+",
        r"\1[REDACTED]",
        message,
    )
    return " ".join(message.split())[:500]


def default_provenance_verifier(root: Path, run_id: str) -> dict[str, Any]:
    runner = root / "scripts/clipmaker_lite_runner.py"
    if not runner.is_file() or runner.is_symlink():
        raise Wan22ControlError("the locked Clipmaker Lite runner is unavailable")
    process = subprocess.run(
        [sys.executable, str(runner), "provenance", "--run-id", run_id],
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        detail = safe_error(process.stderr)
        suffix = f": {detail}" if detail else ""
        raise Wan22ControlError(f"Lite provenance verification failed for {run_id}{suffix}")
    try:
        summary = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise Wan22ControlError(
            f"Lite provenance verifier returned invalid JSON for {run_id}"
        ) from exc
    if not isinstance(summary, dict):
        raise Wan22ControlError(f"Lite provenance summary is not an object for {run_id}")
    return summary


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Wan22ControlError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Wan22ControlError(f"{label} must be a non-empty string")
    return value


def _source_result_job(
    root: Path,
    result_path: Path,
    provenance_verifier: ProvenanceVerifier,
) -> dict[str, Any]:
    result_path = result_path.resolve()
    result_relative = workspace_relative(root, result_path, "Lite result")
    run_id = result_path.parent.name
    if result_path.name != "result.json" or not run_id.startswith(
        "promopages-9891-schemafix-"
    ) or not run_id.endswith("-wan-2-7"):
        raise Wan22ControlError(
            f"prompt source is not a PROMOPAGES-9891 Wan 2.7 schemafix result: {result_relative}"
        )

    summary = provenance_verifier(root, run_id)
    if summary.get("verified") is not True:
        raise Wan22ControlError(f"Lite provenance is not verified for {run_id}")
    if summary.get("models") != [PROMPT_SOURCE_MODEL_ID]:
        raise Wan22ControlError(f"Lite provenance has the wrong model for {run_id}")
    if summary.get("result_path") != result_relative:
        raise Wan22ControlError(f"Lite provenance points at another result for {run_id}")

    result = _require_mapping(read_json(result_path, "Lite result"), "Lite result")
    if result.get("schema_version") != 1 or result.get("job_id") != run_id:
        raise Wan22ControlError(f"Lite result identity is invalid for {run_id}")
    inputs = _require_mapping(result.get("inputs"), f"{run_id}.inputs")
    source_record = _require_mapping(
        inputs.get("source_image"), f"{run_id}.inputs.source_image"
    )
    source_relative = _require_string(
        source_record.get("path"), f"{run_id}.inputs.source_image.path"
    )
    source_path = resolve_workspace_path(root, source_relative, "source image")
    source_parts = Path(source_relative).parts
    if (
        len(source_parts) != 4
        or source_parts[:2] != ("PROMOPAGES-9857", "articles")
        or source_path.suffix.lower() not in IMAGE_SUFFIXES
    ):
        raise Wan22ControlError(f"source image is not an article image: {source_relative}")
    if not source_path.is_file() or source_path.is_symlink():
        raise Wan22ControlError(f"source image is missing or not a regular file: {source_relative}")
    source_sha256 = sha256_file(source_path)
    if source_record.get("sha256") != source_sha256:
        raise Wan22ControlError(f"source image changed after Lite analysis: {source_relative}")
    if summary.get("source_image_sha256") != source_sha256:
        raise Wan22ControlError(f"Lite provenance source digest mismatch for {run_id}")

    models = result.get("models")
    if not isinstance(models, list) or len(models) != 1:
        raise Wan22ControlError(f"Lite result must contain exactly one model for {run_id}")
    model = _require_mapping(models[0], f"{run_id}.models[0]")
    if model.get("model_id") != PROMPT_SOURCE_MODEL_ID:
        raise Wan22ControlError(f"Lite result has the wrong prompt source model for {run_id}")
    positive_prompt = _require_string(
        model.get("positive_prompt"), f"{run_id}.models[0].positive_prompt"
    )
    negative_prompt = model.get("negative_prompt")
    if negative_prompt is not None and not isinstance(negative_prompt, str):
        raise Wan22ControlError(f"{run_id}.models[0].negative_prompt must be text or null")

    article_directory = source_path.parent
    output_directory = article_directory / OUTPUT_SUBDIRECTORY
    stem = source_path.stem
    job_id = f"{source_parts[2]}-{stem}-wan-streamlit-wan-2-2"
    provenance_record = {
        "verified": True,
        "verification_scope": summary.get("verification_scope"),
        "cryptographically_signed": summary.get("cryptographically_signed"),
        "agent_id": summary.get("agent_id"),
        "contract_version": summary.get("contract_version"),
        "contract_fingerprint": summary.get("contract_fingerprint"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "source_image": {
            "path": source_relative,
            "sha256": source_sha256,
            "bytes": source_path.stat().st_size,
        },
        "target_model_id": TARGET_MODEL_ID,
        "prompt_source_model_id": PROMPT_SOURCE_MODEL_ID,
        "provider_route": PROVIDER_ROUTE,
        "attested_lite_model": ATTESTED_LITE_MODEL,
        "runtime": dict(RUNTIME),
        "prompt": {
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "scene_plan": model.get("scene_plan"),
        },
        "prompt_source": {
            "result_path": result_relative,
            "result_sha256": sha256_file(result_path),
            "result_job_id": run_id,
            "lite_provenance": provenance_record,
        },
        "artifacts": {
            "video": workspace_relative(root, output_directory / f"{stem}.mp4", "video"),
            "prompt": workspace_relative(
                root, output_directory / f"{stem}.prompt.json", "prompt metadata"
            ),
            "run": workspace_relative(
                root, output_directory / f"{stem}.run.json", "run metadata"
            ),
        },
    }


def prompt_metadata(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job["job_id"],
        "source_image": job["source_image"],
        "target_model_id": TARGET_MODEL_ID,
        "prompt_source_model_id": PROMPT_SOURCE_MODEL_ID,
        "provider_route": PROVIDER_ROUTE,
        "attested_lite_model": ATTESTED_LITE_MODEL,
        "runtime": dict(RUNTIME),
        "positive_prompt": job["prompt"]["positive_prompt"],
        "negative_prompt": job["prompt"]["negative_prompt"],
        "scene_plan": job["prompt"].get("scene_plan"),
        "prompt_source": job["prompt_source"],
    }


def initial_run_metadata(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job["job_id"],
        "target_model_id": TARGET_MODEL_ID,
        "prompt_source_model_id": PROMPT_SOURCE_MODEL_ID,
        "provider_route": PROVIDER_ROUTE,
        "attested_lite_model": ATTESTED_LITE_MODEL,
        "runtime": dict(RUNTIME),
        "status": "pending",
        "attempts": 0,
        "provider_event_id": None,
        "provider_session_hash": None,
        "submitted_at": None,
        "started_at": None,
        "output": None,
        "media": None,
        "error": None,
        "updated_at": utc_now(),
    }


def build_control_plan(
    root: Path,
    result_paths: Iterable[Path],
    manifest_path: Path,
    provenance_verifier: ProvenanceVerifier = default_provenance_verifier,
) -> dict[str, Any]:
    root = root.resolve()
    resolved_results = sorted({path.resolve() for path in result_paths})
    if len(resolved_results) != EXPECTED_JOB_COUNT:
        raise Wan22ControlError(
            f"expected exactly {EXPECTED_JOB_COUNT} verified prompt results, got {len(resolved_results)}"
        )
    jobs = [
        _source_result_job(root, result_path, provenance_verifier)
        for result_path in resolved_results
    ]
    actual_sources = tuple(sorted(job["source_image"]["path"] for job in jobs))
    if actual_sources != tuple(sorted(EXPECTED_SOURCE_PATHS)):
        raise Wan22ControlError("verified prompt results do not map to the five locked source images")
    artifact_paths = [
        artifact
        for job in jobs
        for artifact in job["artifacts"].values()
    ]
    if len(artifact_paths) != len(set(artifact_paths)):
        raise Wan22ControlError("two control jobs map to the same output artifact")

    manifest_path = manifest_path.resolve()
    manifest_relative = workspace_relative(root, manifest_path, "control manifest")
    plan = {
        "schema_version": SCHEMA_VERSION,
        "control_id": "promopages-9891-wan-streamlit-wan-2.2",
        "target_model_id": TARGET_MODEL_ID,
        "prompt_source_model_id": PROMPT_SOURCE_MODEL_ID,
        "provider_route": PROVIDER_ROUTE,
        "attested_lite_model": ATTESTED_LITE_MODEL,
        "runtime": dict(RUNTIME),
        "job_count": EXPECTED_JOB_COUNT,
        "jobs": jobs,
    }
    for job in jobs:
        prompt_path = resolve_workspace_path(root, job["artifacts"]["prompt"], "prompt metadata")
        run_path = resolve_workspace_path(root, job["artifacts"]["run"], "run metadata")
        write_immutable_json(prompt_path, prompt_metadata(job), "prompt metadata")
        if not run_path.exists():
            atomic_write_json(run_path, initial_run_metadata(job))
        else:
            _validate_run_metadata(read_json(run_path, "run metadata"), job)
    write_immutable_json(manifest_path, plan, "control manifest")
    print(f"planned {len(jobs)} jobs in {manifest_relative}")
    return plan


def _validate_plan(plan: Any) -> dict[str, Any]:
    plan = _require_mapping(plan, "control manifest")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "target_model_id": TARGET_MODEL_ID,
        "prompt_source_model_id": PROMPT_SOURCE_MODEL_ID,
        "provider_route": PROVIDER_ROUTE,
        "attested_lite_model": ATTESTED_LITE_MODEL,
        "runtime": RUNTIME,
        "job_count": EXPECTED_JOB_COUNT,
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            raise Wan22ControlError(f"control manifest has invalid {key}")
    jobs = plan.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != EXPECTED_JOB_COUNT:
        raise Wan22ControlError(f"control manifest must contain {EXPECTED_JOB_COUNT} jobs")
    for job in jobs:
        job = _require_mapping(job, "control job")
        for key, value in expected.items():
            if key in {"job_count", "schema_version"}:
                continue
            if job.get(key) != value:
                raise Wan22ControlError(f"control job {job.get('job_id')} has invalid {key}")
        _require_string(job.get("job_id"), "control job.job_id")
        _require_mapping(job.get("source_image"), "control job.source_image")
        _require_mapping(job.get("prompt"), "control job.prompt")
        _require_mapping(job.get("prompt_source"), "control job.prompt_source")
        _require_mapping(job.get("artifacts"), "control job.artifacts")
    return plan


def _validate_run_metadata(value: Any, job: dict[str, Any]) -> dict[str, Any]:
    run = _require_mapping(value, "run metadata")
    expected = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job["job_id"],
        "target_model_id": TARGET_MODEL_ID,
        "prompt_source_model_id": PROMPT_SOURCE_MODEL_ID,
        "provider_route": PROVIDER_ROUTE,
        "attested_lite_model": ATTESTED_LITE_MODEL,
        "runtime": RUNTIME,
    }
    for key, expected_value in expected.items():
        if run.get(key) != expected_value:
            raise Wan22ControlError(f"run metadata has invalid {key} for {job['job_id']}")
    if run.get("status") not in {
        "pending",
        "preparing",
        "submitted",
        "running",
        "failed",
        "generated",
        "verified",
    }:
        raise Wan22ControlError(f"run metadata has invalid status for {job['job_id']}")
    attempts = run.get("attempts")
    if not isinstance(attempts, int) or attempts < 0:
        raise Wan22ControlError(f"run metadata has invalid attempts for {job['job_id']}")
    return run


def _revalidate_job_inputs(root: Path, job: dict[str, Any]) -> None:
    source = _require_mapping(job.get("source_image"), "source image record")
    source_path = resolve_workspace_path(root, source.get("path"), "source image")
    if not source_path.is_file() or source_path.is_symlink():
        raise Wan22ControlError(f"source image is missing: {source.get('path')}")
    if sha256_file(source_path) != source.get("sha256"):
        raise Wan22ControlError(f"source image changed: {source.get('path')}")
    prompt_source = _require_mapping(job.get("prompt_source"), "prompt source")
    result_path = resolve_workspace_path(
        root, prompt_source.get("result_path"), "prompt source result"
    )
    if not result_path.is_file() or result_path.is_symlink():
        raise Wan22ControlError(f"prompt source result is missing: {result_path}")
    if sha256_file(result_path) != prompt_source.get("result_sha256"):
        raise Wan22ControlError(f"prompt source result changed: {result_path}")
    prompt_path = resolve_workspace_path(root, job["artifacts"]["prompt"], "prompt metadata")
    prompt = read_json(prompt_path, "prompt metadata")
    if canonical_json_bytes(prompt) != canonical_json_bytes(prompt_metadata(job)):
        raise Wan22ControlError(f"prompt metadata changed for {job['job_id']}")


def combine_prompt(positive_prompt: str, negative_prompt: str | None) -> str:
    """Match the demo transport without inventing a Lite negative prompt."""

    positive = positive_prompt.strip()
    if not positive:
        raise Wan22ControlError("positive prompt is empty")
    negative = (negative_prompt or "").strip()
    return f"{positive}\n\nAvoid: {negative}" if negative else positive


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise Wan22ControlError(
            safe_error(f"Wan queue request failed: {exc}")
        ) from exc
    if not isinstance(result, dict):
        raise Wan22ControlError("Wan queue request returned an unexpected payload")
    return result


def _upload_wan_image(image_path: Path, timeout: int) -> str:
    boundary = f"----promopages9891-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{image_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    body = prefix + image_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = Request(
        f"{WAN_BASE_URL}/gradio_api/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise Wan22ControlError(safe_error(f"Wan image upload failed: {exc}")) from exc
    if not isinstance(result, list) or not result or not isinstance(result[0], str):
        raise Wan22ControlError("Wan image upload returned an unexpected payload")
    return result[0]


def submit_wan_job(
    image_path: Path,
    combined_prompt: str,
    runtime: dict[str, Any],
    timeout: int,
) -> tuple[str, str]:
    """Upload the first frame and submit one exact Gradio queue payload."""

    server_path = _upload_wan_image(image_path, timeout)
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    file_data = {
        "path": server_path,
        "orig_name": image_path.name,
        "mime_type": mime_type,
        "is_stream": False,
        "meta": {"_type": "gradio.FileData"},
    }
    session_hash = f"promopages-9891-{uuid.uuid4().hex[:12]}"
    payload = {
        "data": [
            combined_prompt,
            file_data,
            runtime["resolution"],
            runtime["seed"],
            runtime["loop"],
            runtime["last_frame"],
            runtime["frames"],
            runtime["fps"],
        ],
        "event_data": None,
        "fn_index": 0,
        "trigger_id": 19,
        "session_hash": session_hash,
    }
    response = _post_json(
        f"{WAN_BASE_URL}/gradio_api/queue/join",
        payload,
        timeout,
    )
    event_id = response.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise Wan22ControlError("Wan queue/join did not return an event ID")
    return event_id, session_hash


def _parse_sse_data(event_lines: list[str]) -> dict[str, Any] | None:
    data_lines = [line[5:].strip() for line in event_lines if line.startswith("data:")]
    if not data_lines or data_lines == ["null"]:
        return None
    try:
        value = json.loads("\n".join(data_lines))
    except json.JSONDecodeError as exc:
        raise Wan22ControlError("Wan SSE returned invalid JSON") from exc
    return value if isinstance(value, dict) else None


def wait_wan_job(
    session_hash: str,
    event_id: str,
    timeout: int,
    on_started: Callable[[], None],
    *,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Reconnect to one persisted Gradio session until its result is available."""

    query = urlencode({"session_hash": session_hash})
    stream_url = f"{WAN_STREAM_BASE_URL}/gradio_api/queue/data?{query}"
    deadline = time.monotonic() + timeout
    reconnects = 0
    started = False
    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        request = Request(stream_url, method="GET")
        try:
            with opener(request, timeout=min(120, remaining)) as response:
                event_lines: list[str] = []
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if line:
                        event_lines.append(line)
                        continue
                    if not event_lines:
                        continue
                    data = _parse_sse_data(event_lines)
                    event_lines = []
                    if not data:
                        continue
                    encoded = json.dumps(data, ensure_ascii=False).lower()
                    if "session_not_found" in encoded:
                        raise ProviderSessionLostError("Wan provider session was discarded")
                    message = data.get("msg")
                    if message == "process_starts" and not started:
                        started = True
                        on_started()
                    if message == "process_completed" and data.get("event_id") == event_id:
                        if not data.get("success"):
                            detail = (data.get("output") or {}).get("error") or data
                            raise Wan22ControlError(
                                safe_error(f"Wan generation failed: {detail}")
                            )
                        output_data = (data.get("output") or {}).get("data") or []
                        result = output_data[0] if output_data else None
                        if not isinstance(result, dict):
                            raise Wan22ControlError("Wan completed without a video result")
                        if isinstance(result.get("url"), str) and result["url"]:
                            return result["url"]
                        if isinstance(result.get("path"), str) and result["path"]:
                            return urljoin(
                                WAN_STREAM_BASE_URL.rstrip("/") + "/",
                                f"gradio_api/file={result['path']}",
                            )
                        raise Wan22ControlError("Wan result has neither URL nor path")
                    if message == "unexpected_error":
                        raise Wan22ControlError(
                            safe_error(f"Wan stream reported an error: {data}")
                        )
                    if message == "close_stream":
                        break
        except (ProviderSessionLostError, Wan22ControlError):
            raise
        except (HTTPError, URLError, OSError) as exc:
            reconnects += 1
            if time.monotonic() >= deadline:
                raise ResumableProviderError(
                    safe_error(
                        f"Wan SSE remains interrupted after {reconnects} connection(s): {exc}"
                    )
                ) from exc
            print(
                f"  stream interrupted; reconnecting same provider session ({reconnects})",
                flush=True,
            )
            sleeper(min(5, reconnects))
            continue
        reconnects += 1
        print(
            f"  stream closed; reconnecting same provider session ({reconnects})",
            flush=True,
        )
        sleeper(min(5, reconnects))
    raise ResumableProviderError(
        f"Wan job is still resumable after the {timeout}-second wait window"
    )


def download_wan_video(
    url: str,
    destination: Path,
    timeout: int,
    *,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> None:
    """Download to a sibling temporary file and publish with one atomic replace."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: BaseException | None = None
    for attempt in range(1, 4):
        temporary: Path | None = None
        try:
            request = Request(url, method="GET")
            with opener(request, timeout=timeout) as response, tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".download",
                dir=destination.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.stat().st_size == 0:
                raise OSError("provider returned an empty video")
            os.replace(temporary, destination)
            return
        except (HTTPError, URLError, OSError) as exc:
            last_error = exc
            if attempt < 3:
                sleeper(attempt)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    raise ResumableProviderError(
        safe_error(f"Wan video download remains incomplete after 3 attempts: {last_error}")
    )


def _concurrent_completion(
    run_path: Path,
    video_path: Path,
    job: dict[str, Any],
) -> dict[str, Any] | None:
    """Recognize only a newer, fully bound generated/verified disk state."""

    try:
        current = _validate_run_metadata(read_json(run_path, "run metadata"), job)
    except Wan22ControlError:
        return None
    if current["status"] not in {"generated", "verified"}:
        return None
    output = current.get("output")
    if not isinstance(output, dict) or output.get("path") != job["artifacts"]["video"]:
        return None
    expected_sha256 = output.get("sha256")
    expected_bytes = output.get("bytes")
    if (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
        or not isinstance(expected_bytes, int)
        or expected_bytes <= 0
        or not video_path.is_file()
        or video_path.is_symlink()
        or video_path.stat().st_size != expected_bytes
        or sha256_file(video_path) != expected_sha256
    ):
        return None
    return current


def run_jobs(
    root: Path,
    manifest_path: Path,
    *,
    allow_external_processing: bool,
    retry_failed: bool = False,
    timeout: int = 7200,
    submitter: ProviderSubmitter = submit_wan_job,
    waiter: ProviderWaiter = wait_wan_job,
    downloader: ProviderDownloader = download_wan_video,
) -> dict[str, int]:
    manifest_path = manifest_path.resolve()
    with manifest_run_lock(manifest_path):
        return _run_jobs_locked(
            root,
            manifest_path,
            allow_external_processing=allow_external_processing,
            retry_failed=retry_failed,
            timeout=timeout,
            submitter=submitter,
            waiter=waiter,
            downloader=downloader,
        )


def _run_jobs_locked(
    root: Path,
    manifest_path: Path,
    *,
    allow_external_processing: bool,
    retry_failed: bool = False,
    timeout: int = 7200,
    submitter: ProviderSubmitter = submit_wan_job,
    waiter: ProviderWaiter = wait_wan_job,
    downloader: ProviderDownloader = download_wan_video,
) -> dict[str, int]:
    if not allow_external_processing:
        raise Wan22ControlError(
            "provider execution requires --allow-external-processing"
        )
    root = root.resolve()
    plan = _validate_plan(read_json(manifest_path.resolve(), "control manifest"))
    counts = {"generated": 0, "skipped": 0}

    for job in plan["jobs"]:
        _revalidate_job_inputs(root, job)
        video_path = resolve_workspace_path(root, job["artifacts"]["video"], "video")
        run_path = resolve_workspace_path(root, job["artifacts"]["run"], "run metadata")
        run = _validate_run_metadata(read_json(run_path, "run metadata"), job)
        status = run["status"]
        if status in {"generated", "verified"}:
            output = _require_mapping(run.get("output"), "completed run output")
            if not video_path.is_file() or video_path.is_symlink():
                raise Wan22ControlError(f"completed video is missing for {job['job_id']}")
            if sha256_file(video_path) != output.get("sha256"):
                raise Wan22ControlError(f"completed video changed for {job['job_id']}")
            counts["skipped"] += 1
            continue
        if status == "failed" and not retry_failed:
            raise Wan22ControlError(
                f"{job['job_id']} previously failed; pass --retry-failed for an explicit retry"
            )
        if video_path.exists():
            raise Wan22ControlError(
                f"unattested output already exists; refusing to overwrite: {video_path}"
            )

        event_id = run.get("provider_event_id")
        session_hash = run.get("provider_session_hash")
        resumable = status in {"submitted", "running"}
        if resumable and (
            not isinstance(event_id, str)
            or not event_id
            or not isinstance(session_hash, str)
            or not session_hash
        ):
            raise Wan22ControlError(
                f"{job['job_id']} has active state without both provider IDs; refusing a duplicate job"
            )
        if status == "preparing" and bool(event_id) != bool(session_hash):
            raise Wan22ControlError(
                f"{job['job_id']} has only one provider ID; refusing a duplicate job"
            )

        if status in {"pending", "failed"}:
            working = {
                **run,
                "status": "preparing",
                "attempts": run["attempts"] + 1,
                "provider_event_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "started_at": None,
                "error": None,
                "updated_at": utc_now(),
            }
            event_id = None
            session_hash = None
        else:
            working = {**run, "error": None, "updated_at": utc_now()}
        atomic_write_json(run_path, working)
        video_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not event_id or not session_hash:
                source_path = resolve_workspace_path(
                    root, job["source_image"]["path"], "source image"
                )
                combined_prompt = combine_prompt(
                    job["prompt"]["positive_prompt"],
                    job["prompt"]["negative_prompt"],
                )
                event_id, session_hash = submitter(
                    source_path,
                    combined_prompt,
                    dict(RUNTIME),
                    min(timeout, 120),
                )
                if not event_id or not session_hash:
                    raise Wan22ControlError("Wan submitter returned incomplete provider IDs")
                working = {
                    **working,
                    "status": "submitted",
                    "provider_event_id": event_id,
                    "provider_session_hash": session_hash,
                    "submitted_at": utc_now(),
                    "updated_at": utc_now(),
                }
                atomic_write_json(run_path, working)
                print(f"  submitted {job['job_id']}", flush=True)

            def on_started() -> None:
                nonlocal working
                if working["status"] == "running":
                    return
                working = {
                    **working,
                    "status": "running",
                    "started_at": working.get("started_at") or utc_now(),
                    "updated_at": utc_now(),
                }
                atomic_write_json(run_path, working)

            video_url = waiter(session_hash, event_id, timeout, on_started)
            downloader(video_url, video_path, min(timeout, 600))
            if (
                not video_path.is_file()
                or video_path.is_symlink()
                or video_path.stat().st_size == 0
            ):
                raise ResumableProviderError(
                    "provider result was not atomically published as a non-empty MP4"
                )
        except ResumableProviderError as exc:
            if _concurrent_completion(run_path, video_path, job) is not None:
                counts["skipped"] += 1
                print(
                    f"concurrent completion preserved for {job['job_id']}",
                    flush=True,
                )
                continue
            resumable_run = {
                **working,
                "error": {
                    "type": type(exc).__name__,
                    "summary": safe_error(exc),
                    "retryable": True,
                },
                "updated_at": utc_now(),
            }
            atomic_write_json(run_path, resumable_run)
            raise Wan22ControlError(
                f"{job['job_id']} remains submitted and resumable: {safe_error(exc)}"
            ) from exc
        except (OSError, Wan22ControlError) as exc:
            if _concurrent_completion(run_path, video_path, job) is not None:
                counts["skipped"] += 1
                print(
                    f"concurrent completion preserved for {job['job_id']}",
                    flush=True,
                )
                continue
            failed = {
                **working,
                "status": "failed",
                "error": {
                    "type": type(exc).__name__,
                    "summary": safe_error(exc),
                },
                "updated_at": utc_now(),
            }
            atomic_write_json(run_path, failed)
            raise Wan22ControlError(f"{job['job_id']} failed: {safe_error(exc)}") from exc

        generated = {
            **working,
            "status": "generated",
            "output": {
                "path": job["artifacts"]["video"],
                "sha256": sha256_file(video_path),
                "bytes": video_path.stat().st_size,
            },
            "media": None,
            "error": None,
            "updated_at": utc_now(),
        }
        atomic_write_json(run_path, generated)
        counts["generated"] += 1
        print(f"generated {job['job_id']}")
    return counts


def recover_generated_job(
    root: Path,
    manifest_path: Path,
    job_id: str,
    expected_sha256: str,
    expected_bytes: int,
) -> dict[str, Any]:
    """Recover one raced completion only from an explicit SHA-256/size receipt."""

    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise Wan22ControlError("recovery requires a lowercase 64-character SHA-256")
    if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes <= 0:
        raise Wan22ControlError("recovery requires a positive expected byte count")
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    with manifest_run_lock(manifest_path):
        plan = _validate_plan(read_json(manifest_path, "control manifest"))
        matches = [job for job in plan["jobs"] if job.get("job_id") == job_id]
        if len(matches) != 1:
            raise Wan22ControlError(f"recovery job ID is unknown or ambiguous: {job_id}")
        job = matches[0]
        _revalidate_job_inputs(root, job)
        run_path = resolve_workspace_path(root, job["artifacts"]["run"], "run metadata")
        video_path = resolve_workspace_path(root, job["artifacts"]["video"], "video")
        run = _validate_run_metadata(read_json(run_path, "run metadata"), job)
        if run["status"] in {"generated", "verified"}:
            completed = _concurrent_completion(run_path, video_path, job)
            if (
                completed is not None
                and completed["output"]["sha256"] == expected_sha256
                and completed["output"]["bytes"] == expected_bytes
            ):
                return completed
            raise Wan22ControlError("existing completed receipt differs from recovery evidence")
        if run["status"] not in {"failed", "submitted", "running"} or run["attempts"] < 1:
            raise Wan22ControlError(
                "recovery is limited to an attempted failed/submitted/running job"
            )
        if run.get("output") is not None:
            raise Wan22ControlError("incomplete run already contains conflicting output metadata")
        if not video_path.is_file() or video_path.is_symlink():
            raise Wan22ControlError("recovery video is missing or not a regular file")
        actual_bytes = video_path.stat().st_size
        actual_sha256 = sha256_file(video_path)
        if actual_bytes != expected_bytes or actual_sha256 != expected_sha256:
            raise Wan22ControlError("recovery video does not match the explicit SHA-256/size receipt")
        recovered_at = utc_now()
        recovered = {
            **run,
            "status": "generated",
            "output": {
                "path": job["artifacts"]["video"],
                "sha256": expected_sha256,
                "bytes": expected_bytes,
            },
            "media": None,
            "error": None,
            "recovery": {
                "method": "explicit-sha256-and-size",
                "expected_sha256": expected_sha256,
                "expected_bytes": expected_bytes,
                "recovered_at": recovered_at,
            },
            "updated_at": recovered_at,
        }
        atomic_write_json(run_path, recovered)
        print(f"recovered generated receipt for {job_id}", flush=True)
        return recovered


def default_media_probe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,nb_frames,duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        process = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Wan22ControlError(f"ffprobe could not inspect {path.name}: {exc}") from exc
    if process.returncode != 0:
        raise Wan22ControlError(
            f"ffprobe failed for {path.name}: {safe_error(process.stderr)}"
        )
    try:
        payload = json.loads(process.stdout)
        streams = payload["streams"]
        stream = streams[0]
        return {
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "fps": float(Fraction(stream["r_frame_rate"])),
            "frames": int(stream["nb_frames"]),
            "duration_seconds": float(stream["duration"]),
        }
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise Wan22ControlError(f"ffprobe returned incomplete media data for {path.name}") from exc


def image_dimensions(path: Path) -> tuple[int, int]:
    """Read PNG/JPEG dimensions without decoding or changing the source image."""

    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if width > 0 and height > 0:
            return width, height
    if data.startswith(b"\xff\xd8"):
        position = 2
        sof_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        while position + 4 <= len(data):
            while position < len(data) and data[position] != 0xFF:
                position += 1
            while position < len(data) and data[position] == 0xFF:
                position += 1
            if position >= len(data):
                break
            marker = data[position]
            position += 1
            if marker in {0x01, *range(0xD0, 0xDA)}:
                continue
            if position + 2 > len(data):
                break
            segment_length = int.from_bytes(data[position : position + 2], "big")
            if segment_length < 2 or position + segment_length > len(data):
                break
            if marker in sof_markers and segment_length >= 7:
                height = int.from_bytes(data[position + 3 : position + 5], "big")
                width = int.from_bytes(data[position + 5 : position + 7], "big")
                if width > 0 and height > 0:
                    return width, height
            position += segment_length
    raise Wan22ControlError(f"could not read source image dimensions: {path.name}")


def _validate_media(
    media: dict[str, Any],
    job_id: str,
    source_dimensions: tuple[int, int],
) -> None:
    if media.get("fps") != 30.0:
        raise Wan22ControlError(f"{job_id} has {media.get('fps')} fps instead of 30")
    if media.get("frames") != 97:
        raise Wan22ControlError(f"{job_id} has {media.get('frames')} frames instead of 97")
    duration = media.get("duration_seconds")
    if not isinstance(duration, (int, float)) or abs(duration - (97 / 30)) > 0.15:
        raise Wan22ControlError(f"{job_id} has unexpected duration: {duration}")
    width = media.get("width")
    height = media.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise Wan22ControlError(f"{job_id} has invalid dimensions: {width}x{height}")
    pixel_area = width * height
    if not 800_000 <= pixel_area <= 1_050_000:
        raise Wan22ControlError(
            f"{job_id} is not 720p-class: {width}x{height} ({pixel_area} pixels)"
        )
    source_width, source_height = source_dimensions
    source_aspect = source_width / source_height
    output_aspect = width / height
    aspect_error = abs(output_aspect - source_aspect) / source_aspect
    if aspect_error > 0.03:
        raise Wan22ControlError(
            f"{job_id} changed source aspect ratio by {aspect_error:.1%}"
        )


def verify_jobs(
    root: Path,
    manifest_path: Path,
    probe: MediaProbe = default_media_probe,
) -> dict[str, int]:
    root = root.resolve()
    plan = _validate_plan(read_json(manifest_path.resolve(), "control manifest"))
    counts = {"verified": 0, "already_verified": 0}
    for job in plan["jobs"]:
        _revalidate_job_inputs(root, job)
        video_path = resolve_workspace_path(root, job["artifacts"]["video"], "video")
        run_path = resolve_workspace_path(root, job["artifacts"]["run"], "run metadata")
        source_path = resolve_workspace_path(
            root, job["source_image"]["path"], "source image"
        )
        source_size = image_dimensions(source_path)
        run = _validate_run_metadata(read_json(run_path, "run metadata"), job)
        if run["status"] not in {"generated", "verified"}:
            raise Wan22ControlError(
                f"{job['job_id']} is {run['status']}, so it cannot be verified"
            )
        output = _require_mapping(run.get("output"), "generated output")
        if not video_path.is_file() or video_path.is_symlink():
            raise Wan22ControlError(f"video is missing for {job['job_id']}")
        if sha256_file(video_path) != output.get("sha256"):
            raise Wan22ControlError(f"video digest mismatch for {job['job_id']}")
        if run["status"] == "verified":
            _validate_media(
                _require_mapping(run.get("media"), "verified media"),
                job["job_id"],
                source_size,
            )
            counts["already_verified"] += 1
            continue
        media = probe(video_path)
        _validate_media(media, job["job_id"], source_size)
        media = {
            **media,
            "source_width": source_size[0],
            "source_height": source_size[1],
            "source_aspect_ratio": source_size[0] / source_size[1],
        }
        verified = {
            **run,
            "status": "verified",
            "media": media,
            "updated_at": utc_now(),
        }
        atomic_write_json(run_path, verified)
        counts["verified"] += 1
        print(f"verified {job['job_id']}")
    return counts


def _default_results(root: Path) -> list[Path]:
    return sorted(root.glob(DEFAULT_SOURCE_GLOB))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="validate five Lite results and write control metadata")
    plan.add_argument("--manifest", type=Path, default=DEFAULT_CONTROL_MANIFEST)
    plan.add_argument(
        "--result",
        type=Path,
        action="append",
        help="verified Wan 2.7 result.json (repeat exactly five times)",
    )

    run = subparsers.add_parser("run", help="run only pending Wan 2.2 provider jobs")
    run.add_argument("--manifest", type=Path, default=DEFAULT_CONTROL_MANIFEST)
    run.add_argument("--allow-external-processing", action="store_true")
    run.add_argument("--retry-failed", action="store_true")
    run.add_argument("--timeout", type=int, default=7200)

    verify = subparsers.add_parser("verify", help="verify generated MP4 contracts")
    verify.add_argument("--manifest", type=Path, default=DEFAULT_CONTROL_MANIFEST)

    recover = subparsers.add_parser(
        "recover",
        help="recover one raced completion from an explicit SHA-256/size receipt",
    )
    recover.add_argument("--manifest", type=Path, default=DEFAULT_CONTROL_MANIFEST)
    recover.add_argument("--job-id", required=True)
    recover.add_argument("--expected-sha256", required=True)
    recover.add_argument("--expected-bytes", required=True, type=int)
    return parser


def _rooted(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.workspace.resolve()
    try:
        if args.command == "plan":
            results = (
                [_rooted(root, path) for path in args.result]
                if args.result
                else _default_results(root)
            )
            build_control_plan(
                root,
                results,
                _rooted(root, args.manifest),
            )
        elif args.command == "run":
            run_jobs(
                root,
                _rooted(root, args.manifest),
                allow_external_processing=args.allow_external_processing,
                retry_failed=args.retry_failed,
                timeout=args.timeout,
            )
        elif args.command == "verify":
            verify_jobs(root, _rooted(root, args.manifest))
        elif args.command == "recover":
            recover_generated_job(
                root,
                _rooted(root, args.manifest),
                args.job_id,
                args.expected_sha256,
                args.expected_bytes,
            )
        else:  # pragma: no cover - argparse enforces the command set.
            raise Wan22ControlError(f"unsupported command: {args.command}")
    except Wan22ControlError as exc:
        print(f"error: {safe_error(exc)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
