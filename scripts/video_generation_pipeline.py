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
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = ROOT / "PROMOPAGES-9857/video-samples.json"
DEFAULT_PROMPTS = ROOT / "PROMOPAGES-9857/video-prompts.json"
DEFAULT_MANIFEST = ROOT / "PROMOPAGES-9857/video-generation-manifest.json"
DEFAULT_WAN_BASE_URL = "https://wan-streamlit.dod.yandex.net"
DEFAULT_WAN_STREAM_BASE_URL = "http://wan-streamlit.dod.yandex.net"
DEFAULT_ELIZA_BASE_URL = "https://api.eliza.yandex.net/openrouter/v1"

MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "alibaba/wan-2.2": {
        "directory": "wan-2.2",
        "adapter": "wan-demo",
        "duration": 3.2,
        "durations": [3.2],
        "resolution": "720p",
        "aspect_ratios": ["source"],
        "seed": 1,
        "frames": 97,
        "fps": 30,
        "generate_audio": False,
    },
    "alibaba/wan-2.7": {
        "directory": "wan-2.7",
        "adapter": "eliza-openrouter",
        "duration": 3,
        "durations": list(range(2, 11)),
        "resolution": "1080p",
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "seed": 9681,
        "generate_audio": False,
        "provider": "atlas-cloud",
        "negative_limit": 500,
    },
    "google/veo-3.1-lite": {
        "directory": "veo-3.1-lite",
        "adapter": "eliza-openrouter",
        "duration": 4,
        "durations": [4, 6, 8],
        "resolution": "1080p",
        "aspect_ratios": ["16:9", "9:16"],
        "seed": 9681,
        "generate_audio": False,
        "provider": "google-vertex",
    },
}

EXPECTED_SAMPLE_COUNT = 5
EXPECTED_RESULT_COUNT = EXPECTED_SAMPLE_COUNT * len(MODEL_CONFIGS)
REQUEST_FINGERPRINT_VERSION = 2
TERMINAL_SUCCESS = {"completed", "succeeded", "success", "done"}
TERMINAL_FAILURE = {"failed", "error", "cancelled", "canceled", "expired"}
SECRET_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*(?:bearer|oauth)\s+)[^\s,;]+|"
    r"((?:access[_-]?token|api[_-]?key|token)\s*[:=]\s*)[^\s,;]+"
)
EXPERIMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class PipelineError(RuntimeError):
    """A user-actionable pipeline failure."""


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
        temp_path = Path(handle.name)
    temp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_error(error: BaseException | str) -> str:
    message = str(error)
    message = SECRET_RE.sub(lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", message)
    message = re.sub(r"([?&](?:token|key|signature|sig|auth)=)[^&\s]+", r"\1[REDACTED]", message, flags=re.I)
    return message[:2000]


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


def build_request_preview(sample: dict, prompt: dict) -> dict[str, Any]:
    model_id = prompt["model_id"]
    config = MODEL_CONFIGS[model_id]
    if config["adapter"] == "wan-demo":
        return {
            "endpoint": "/gradio_api/queue/join",
            "model": model_id,
            "input": {
                "source_path": sample["source_path"],
                "prompt": f"{prompt['positive_prompt']}\n\nAvoid: {prompt['negative_prompt']}",
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
    if prompt.get("embed_negative_in_positive"):
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
    if model_id == "alibaba/wan-2.7":
        parameters: dict[str, Any] = {"prompt_extend": prompt.get("prompt_extend", False)}
        if not prompt.get("embed_negative_in_positive"):
            parameters["negative_prompt"] = prompt["negative_prompt"]
        payload["provider"] = {
            "options": {
                "atlas-cloud": {
                    "parameters": parameters
                }
            }
        }
    elif model_id == "google/veo-3.1-lite":
        parameters = {"enhancePrompt": True}
        if not prompt.get("embed_negative_in_positive"):
            parameters["negativePrompt"] = prompt["negative_prompt"]
        payload["provider"] = {
            "options": {
                "google-vertex": {
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
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PipelineError(safe_error(f"{method} {url} failed with HTTP {exc.code}: {detail[:1000]}")) from exc
    except URLError as exc:
        raise PipelineError(safe_error(f"{method} {url} failed: {exc.reason}")) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PipelineError(f"{method} {url} returned invalid JSON") from exc


def http_download(url: str, destination: Path, headers: dict[str, str] | None = None, timeout: int = 600) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: BaseException | None = None
    for attempt in range(1, 4):
        request = Request(url, headers=headers or {}, method="GET")
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


def upload_wan_image(base_url: str, image_path: Path, timeout: int = 120) -> str:
    boundary = f"----promopages-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{image_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    body = prefix + image_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = Request(
        f"{base_url.rstrip('/')}/gradio_api/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
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
    stream_url = f"{stream_base_url.rstrip('/')}/gradio_api/queue/data?{query}"
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
                            raise PipelineError(safe_error((data.get("output") or {}).get("error") or data))
                        output_data = (data.get("output") or {}).get("data") or []
                        result = output_data[0] if output_data else None
                        if not isinstance(result, dict):
                            raise PipelineError("Wan completed without a video result")
                        if result.get("url"):
                            return result["url"]
                        if result.get("path"):
                            return urljoin(stream_base_url.rstrip("/") + "/", f"gradio_api/file={result['path']}")
                        raise PipelineError("Wan result has neither url nor path")
                    if message in {"unexpected_error", "close_stream"}:
                        raise PipelineError(safe_error(f"Wan stream ended before completion: {data}"))
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


def wan_generate(
    sample: dict,
    prompt: dict,
    destination: Path,
    base_url: str,
    stream_base_url: str,
    timeout: int,
    resume: dict[str, Any] | None,
    on_submitted: Callable[[str, str], None],
) -> None:
    event_id = (resume or {}).get("provider_job_id")
    session_hash = (resume or {}).get("provider_session_hash")
    resubmitted_after_missing_session = False
    while True:
        if not event_id or not session_hash:
            image_path = ROOT / sample["source_path"]
            server_path = upload_wan_image(base_url, image_path)
            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
            config = MODEL_CONFIGS[prompt["model_id"]]
            file_data = {
                "path": server_path,
                "orig_name": image_path.name,
                "mime_type": mime_type,
                "is_stream": False,
                "meta": {"_type": "gradio.FileData"},
            }
            combined_prompt = f"{prompt['positive_prompt']}\n\nAvoid: {prompt['negative_prompt']}"
            session_hash = f"promopages9856-{uuid.uuid4().hex[:12]}"
            payload = {
                "data": [
                    combined_prompt,
                    file_data,
                    config["resolution"],
                    config["seed"],
                    False,
                    None,
                    config["frames"],
                    config["fps"],
                ],
                "event_data": None,
                "fn_index": 0,
                "trigger_id": 19,
                "session_hash": session_hash,
            }
            response = http_json("POST", f"{base_url.rstrip('/')}/gradio_api/queue/join", payload, timeout=120)
            event_id = response.get("event_id") if isinstance(response, dict) else None
            if not event_id:
                raise PipelineError("Wan queue/join did not return event_id")
            on_submitted(event_id, session_hash)
        try:
            video_url = wan_wait_for_result(stream_base_url, session_hash, event_id, timeout)
            break
        except PipelineError as exc:
            if "session_not_found" not in str(exc).lower() or resubmitted_after_missing_session:
                raise
            print("  Wan session was dropped; resubmitting this item once", flush=True)
            resubmitted_after_missing_session = True
            event_id = None
            session_hash = None
    http_download(video_url, destination, timeout=600)


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


def eliza_poll(
    base_url: str,
    job_id: str,
    headers: dict[str, str],
    timeout: int,
    interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    status_url = f"{base_url.rstrip('/')}/videos/{job_id}"
    while time.monotonic() < deadline:
        response = http_json("GET", status_url, headers=headers, timeout=120)
        status = find_status(response)
        print(f"  Eliza/OpenRouter job {job_id}: {status or 'unknown'}", flush=True)
        if status in TERMINAL_SUCCESS or (find_video_url(response) and status not in TERMINAL_FAILURE):
            return response
        if status in TERMINAL_FAILURE:
            detail = find_error_detail(response)
            suffix = f": {detail}" if detail else ""
            raise PipelineError(
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
    job_id = (resume or {}).get("provider_job_id")
    if not job_id:
        payload = build_request_preview(sample, prompt)
        response = http_json("POST", f"{base_url.rstrip('/')}/videos", payload, headers=headers, timeout=120)
        job_id = find_job_id(response)
        if not job_id:
            raise PipelineError("Eliza/OpenRouter submit response did not contain a job ID")
        on_submitted(job_id, None)
    eliza_poll(base_url, job_id, headers, timeout, poll_interval)
    content_url = f"{base_url.rstrip('/')}/videos/{job_id}/content?index=0"
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
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
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
                "status": "running" if resume else "prepared",
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

        try:
            adapter = MODEL_CONFIGS[prompt["model_id"]]["adapter"]
            if adapter == "wan-demo":
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
            resumable = bool(run.get("provider_job_id")) and not any(
                marker in error.lower() for marker in ("failed with status", "cancelled", "canceled", "expired")
            )
            run.update(
                {
                    "status": "submitted" if resumable else "failed",
                    "completed_at": None if resumable else utc_now(),
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
        succeeded += 1
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
    run_parser.add_argument("--wan-base-url", default=os.environ.get("WAN_DEMO_BASE_URL", DEFAULT_WAN_BASE_URL))
    run_parser.add_argument(
        "--wan-stream-base-url", default=os.environ.get("WAN_DEMO_STREAM_BASE_URL", DEFAULT_WAN_STREAM_BASE_URL)
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
