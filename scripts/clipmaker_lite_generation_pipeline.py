#!/usr/bin/env python3
"""Plan, run, resume, and verify the fixed Clipmaker Lite video matrix.

This bridge consumes only stamped ``clipmaker-lite`` results.  It never reads
the classic prompt catalog and writes exclusively below each article's
``clipmaker-lite/<model>/`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner  # noqa: E402
from scripts import video_generation_pipeline as provider_transport  # noqa: E402


TICKET = "PROMOPAGES-9891"
AGENT_ID = "clipmaker-lite"
MANIFEST_RELATIVE_PATH = Path("PROMOPAGES-9857/clipmaker-lite-native-generation-manifest.json")
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")
PUBLIC_SOURCE_BASE = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/main/"
)
DEFAULT_ELIZA_BASE_URL = provider_transport.DEFAULT_ELIZA_BASE_URL
REQUEST_FINGERPRINT_VERSION = 1
TERMINAL_PROVIDER_FAILURE_MARKERS = (
    "failed with status",
    "cancelled",
    "canceled",
    "expired",
)
ACTIVE_STATUSES = {"submitted", "running"}
BLOCKED_STATUSES = {"stale", "submitting", "submit-unknown", "provider-failed"}
DNS_PRE_SUBMIT_MARKERS = (
    "nodename nor servname provided, or not known",
    "name or service not known",
    "temporary failure in name resolution",
    "getaddrinfo failed",
)


class LiteGenerationError(RuntimeError):
    """A fail-closed, user-actionable Lite generation failure."""


@dataclass(frozen=True)
class MatrixEntry:
    run_id: str
    sample_id: str
    source_path: str
    source_sha256: str
    width: int
    height: int
    model_id: str

    @property
    def article_slug(self) -> str:
        return Path(self.source_path).parent.name

    @property
    def stem(self) -> str:
        return Path(self.source_path).stem


@dataclass(frozen=True)
class LiteJob:
    entry: MatrixEntry
    positive_prompt: str
    negative_prompt: str | None
    result_path: str
    result_sha256: str
    provenance: dict[str, Any]


def _entry(
    sample_number: str,
    sample_name: str,
    article_slug: str,
    filename: str,
    source_sha256: str,
    width: int,
    height: int,
    model_id: str,
) -> MatrixEntry:
    provider_suffix = {
        "alibaba/wan-2.7": "wan-2-7",
        "google/veo-3.1-lite": "veo-3-1-lite",
    }[model_id]
    sample_id = f"{sample_number}-{sample_name}"
    return MatrixEntry(
        run_id=f"promopages-9891-schemafix-{sample_id}-{provider_suffix}",
        sample_id=sample_id,
        source_path=f"PROMOPAGES-9857/articles/{article_slug}/{filename}",
        source_sha256=source_sha256,
        width=width,
        height=height,
        model_id=model_id,
    )


def _pair(
    sample_number: str,
    sample_name: str,
    article_slug: str,
    filename: str,
    source_sha256: str,
    width: int,
    height: int,
) -> tuple[MatrixEntry, MatrixEntry]:
    return tuple(  # type: ignore[return-value]
        _entry(
            sample_number,
            sample_name,
            article_slug,
            filename,
            source_sha256,
            width,
            height,
            model_id,
        )
        for model_id in ("alibaba/wan-2.7", "google/veo-3.1-lite")
    )


MATRIX: tuple[MatrixEntry, ...] = (
    *_pair(
        "01",
        "portrait-hands",
        "01-pharmocean-magiia-magniia",
        "02.jpeg",
        "dac18b13cd08c2403ca22b41b428eb1293acd6b0e35a02f8a7082ad00a77c68f",
        2400,
        1600,
    ),
    *_pair(
        "02",
        "product-dropper",
        "04-graceface-antivozrastnaia-syvorotka",
        "05.png",
        "d8f32e5b4953b00d118abfe53468b4359ba56dd31d2aa69b935c10d76f310835",
        1280,
        800,
    ),
    *_pair(
        "03",
        "animal-step",
        "06-4lapy-koshachii-napolnitel",
        "03.jpeg",
        "f31d778c510ed4bc9601667c4a40810e8e79d46db7cb624d263fa1fa5f7517c3",
        1000,
        450,
    ),
    *_pair(
        "04",
        "interior-water",
        "13-ilinka-elitnyi-zhk",
        "09.png",
        "10dd4f44ea0e4d5cf66f0c297840e802aaad7fcd675aeb5bcb24436cf59fa053",
        1600,
        900,
    ),
    *_pair(
        "05",
        "finance-ui",
        "20-sravni-kreditnyi-reiting",
        "04.png",
        "531a18c9baf3bd63c53ee1edce03042009e8f5ade9023a015ac8a235320105ed",
        1098,
        659,
    ),
)


MODEL_CONFIGS: dict[str, dict[str, Any]] = {
    "alibaba/wan-2.7": {
        "directory": "wan-2.7",
        "duration_seconds": 5,
        "resolution": "1080p",
        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
        "generate_audio": False,
        "provider": "atlas-cloud",
        "prompt_expansion": {"parameter": "prompt_extend", "value": True},
        "negative_parameter": "negative_prompt",
    },
    "google/veo-3.1-lite": {
        "directory": "veo-3.1-lite",
        "duration_seconds": 4,
        "resolution": "1080p",
        "aspect_ratios": ["16:9", "9:16"],
        "generate_audio": False,
        "provider": "google-vertex",
        "prompt_expansion": {"parameter": "enhancePrompt", "value": True},
        "negative_parameter": "negativePrompt",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise LiteGenerationError(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LiteGenerationError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LiteGenerationError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise LiteGenerationError(f"Path escapes workspace: {path}") from exc


def safe_error(error: BaseException | str) -> str:
    message = provider_transport.safe_error(error)
    message = re.sub(r"https?://[^\s\]\[<>{}\"']+", "[REDACTED_URL]", message)
    message = re.sub(
        r"(?i)\b(?:authorization|proxy-authorization|x-api-key)\s*[:=]\s*[^\s,;]+",
        "[REDACTED_CREDENTIAL]",
        message,
    )
    message = re.sub(r"(?i)\b(?:x-goog-signature|signature|sig)=[^&\s]+", "signature=[REDACTED]", message)
    return message[:2000]


def is_definitive_dns_pre_submit_failure(error: BaseException | str) -> bool:
    """Return true only for DNS failures that occur before an HTTP connection.

    HTTP responses are deliberately excluded even if their body happens to
    contain a DNS-looking phrase: once a response exists, submit outcome is no
    longer provably pre-submit.
    """

    message = str(error).strip().lower()
    return (
        message.startswith("post ")
        and " failed: " in message
        and " failed with http " not in message
        and any(marker in message for marker in DNS_PRE_SUBMIT_MARKERS)
    )


def expected_runtime(model_id: str) -> dict[str, Any]:
    config = MODEL_CONFIGS[model_id]
    return {
        "duration_seconds": config["duration_seconds"],
        "resolution": config["resolution"],
        "aspect_ratios": config["aspect_ratios"],
        "generate_audio": config["generate_audio"],
        "frame_inputs": ["first_frame"],
        "provider": config["provider"],
        "prompt_expansion": config["prompt_expansion"],
    }


def choose_aspect_ratio(width: int, height: int, ratios: Iterable[str]) -> str:
    if width <= 0 or height <= 0:
        raise LiteGenerationError(f"Invalid source dimensions: {width}x{height}")
    target = width / height

    def distance(label: str) -> float:
        left, right = label.split(":", 1)
        return abs(math.log(target / (float(left) / float(right))))

    return min(ratios, key=distance)


def artifact_paths(root: Path, entry: MatrixEntry) -> dict[str, Path]:
    config = MODEL_CONFIGS[entry.model_id]
    base = (
        root
        / "PROMOPAGES-9857/articles"
        / entry.article_slug
        / "clipmaker-lite"
        / config["directory"]
    )
    return {
        "directory": base,
        "prompt": base / f"{entry.stem}.prompt.json",
        "run": base / f"{entry.stem}.run.json",
        "video": base / f"{entry.stem}.mp4",
    }


def _validate_provenance(root: Path, entry: MatrixEntry) -> dict[str, Any]:
    try:
        summary = clipmaker_lite_runner.provenance_summary(root, entry.run_id)
    except Exception as exc:
        raise LiteGenerationError(
            f"Lite provenance failed for {entry.run_id}: {safe_error(exc)}"
        ) from exc
    if summary.get("verified") is not True:
        raise LiteGenerationError(f"Lite provenance is not verified: {entry.run_id}")
    if summary.get("agent_id") != AGENT_ID:
        raise LiteGenerationError(
            f"Unexpected Lite producer for {entry.run_id}: {summary.get('agent_id')!r}"
        )
    if summary.get("models") != [entry.model_id]:
        raise LiteGenerationError(
            f"Lite provenance model mismatch for {entry.run_id}: {summary.get('models')!r}"
        )
    if summary.get("source_image_sha256") != entry.source_sha256:
        raise LiteGenerationError(f"Lite provenance source mismatch for {entry.run_id}")
    return summary


def load_lite_job(root: Path, entry: MatrixEntry) -> LiteJob:
    """Verify runner provenance, then consume the exact stamped model prompt."""

    root = root.resolve()
    summary = _validate_provenance(root, entry)
    expected_result_path = (ARTIFACT_NAMESPACE / entry.run_id / "result.json").as_posix()
    if summary.get("result_path") != expected_result_path:
        raise LiteGenerationError(f"Unexpected result path for {entry.run_id}")
    result_path = root / expected_result_path
    result = read_json(result_path)
    if not isinstance(result, dict) or result.get("job_id") != entry.run_id:
        raise LiteGenerationError(f"Stamped result identity mismatch: {entry.run_id}")
    producer = result.get("producer")
    if not isinstance(producer, dict) or producer.get("agent_id") != AGENT_ID:
        raise LiteGenerationError(f"Stamped result producer mismatch: {entry.run_id}")
    inputs = result.get("inputs")
    source = inputs.get("source_image") if isinstance(inputs, dict) else None
    if not isinstance(source, dict):
        raise LiteGenerationError(f"Stamped result source is missing: {entry.run_id}")
    if source.get("path") != entry.source_path or source.get("sha256") != entry.source_sha256:
        raise LiteGenerationError(f"Stamped result source does not match the fixed matrix: {entry.run_id}")
    source_path = root / entry.source_path
    if not source_path.is_file():
        raise LiteGenerationError(f"Fixed source image is missing: {entry.source_path}")

    models = result.get("models")
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise LiteGenerationError(f"Stamped result must contain exactly one model: {entry.run_id}")
    model = models[0]
    if model.get("model_id") != entry.model_id:
        raise LiteGenerationError(f"Stamped result model mismatch: {entry.run_id}")
    if model.get("runtime") != expected_runtime(entry.model_id):
        raise LiteGenerationError(f"Stamped Lite runtime mismatch: {entry.run_id}")
    positive = model.get("positive_prompt")
    if not isinstance(positive, str) or not positive.strip():
        raise LiteGenerationError(f"Stamped positive prompt is empty: {entry.run_id}")
    negative: str | None = None
    if "negative_prompt" in model:
        candidate = model["negative_prompt"]
        if not isinstance(candidate, str):
            raise LiteGenerationError(f"Stamped negative prompt must be a string: {entry.run_id}")
        if candidate.strip():
            negative = candidate

    return LiteJob(
        entry=entry,
        positive_prompt=positive,
        negative_prompt=negative,
        result_path=expected_result_path,
        result_sha256=sha256_file(result_path),
        provenance=summary,
    )


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
    }


def prompt_artifact(job: LiteJob) -> dict[str, Any]:
    entry = job.entry
    config = MODEL_CONFIGS[entry.model_id]
    prompt: dict[str, Any] = {"positive": job.positive_prompt}
    if job.negative_prompt:
        prompt["negative"] = job.negative_prompt
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "agent_id": AGENT_ID,
        "lite_run_id": entry.run_id,
        "model_id": entry.model_id,
        "source": {
            "path": entry.source_path,
            "sha256": entry.source_sha256,
            "width": entry.width,
            "height": entry.height,
        },
        "prompt": prompt,
        "target": {
            "duration_seconds": config["duration_seconds"],
            "resolution": config["resolution"],
            "aspect_ratio": choose_aspect_ratio(entry.width, entry.height, config["aspect_ratios"]),
            "generate_audio": False,
            "frame_inputs": ["first_frame"],
            "provider": config["provider"],
            "prompt_expansion": config["prompt_expansion"],
        },
        "lite_result": {
            "path": job.result_path,
            "sha256": job.result_sha256,
            "provenance": safe_provenance(job),
        },
    }


def sanitized_request(job: LiteJob) -> dict[str, Any]:
    entry = job.entry
    config = MODEL_CONFIGS[entry.model_id]
    parameters: dict[str, Any] = {
        config["prompt_expansion"]["parameter"]: config["prompt_expansion"]["value"]
    }
    if job.negative_prompt:
        parameters[config["negative_parameter"]] = job.negative_prompt
    return {
        "model": entry.model_id,
        "prompt": job.positive_prompt,
        "duration": config["duration_seconds"],
        "resolution": config["resolution"],
        "aspect_ratio": choose_aspect_ratio(entry.width, entry.height, config["aspect_ratios"]),
        "generate_audio": False,
        "frame_images": [
            {
                "source_path": entry.source_path,
                "source_sha256": entry.source_sha256,
                "frame_type": "first_frame",
            }
        ],
        "provider": {
            "options": {
                config["provider"]: {
                    "parameters": parameters,
                }
            }
        },
    }


def provider_request(job: LiteJob) -> dict[str, Any]:
    """Build the live request; its source URL is deliberately never persisted."""

    payload = sanitized_request(job)
    payload["frame_images"] = [
        {
            "type": "image_url",
            "image_url": {
                "url": PUBLIC_SOURCE_BASE + quote(job.entry.source_path, safe="/"),
            },
            "frame_type": "first_frame",
        }
    ]
    return payload


def request_sha256(job: LiteJob) -> str:
    return canonical_sha256(
        {
            "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
            "request": sanitized_request(job),
            "lite_result_sha256": job.result_sha256,
        }
    )


def initial_run_artifact(root: Path, job: LiteJob, paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "agent_id": AGENT_ID,
        "lite_run_id": job.entry.run_id,
        "model_id": job.entry.model_id,
        "status": "pending",
        "prompt_path": relative(paths["prompt"], root),
        "output_path": relative(paths["video"], root),
        "request": sanitized_request(job),
        "request_sha256": request_sha256(job),
        "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
        "provider_job_id": None,
        "submitted_at": None,
        "completed_at": None,
        "media": None,
        "contract_check": None,
        "error": None,
    }


FORBIDDEN_METADATA_KEYS = {
    "authorization",
    "headers",
    "header",
    "token",
    "access_token",
    "api_key",
    "signed_url",
    "download_url",
    "content_url",
    "source_url",
    "url",
}


def assert_sanitized_metadata(value: Any, label: str = "metadata") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_METADATA_KEYS:
                raise LiteGenerationError(f"Forbidden metadata key {key!r} in {label}")
            assert_sanitized_metadata(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_sanitized_metadata(child, f"{label}[{index}]")
    elif isinstance(value, str):
        if re.search(r"https?://", value, flags=re.I):
            raise LiteGenerationError(f"URL leaked into {label}")
        if re.search(r"(?i)\b(?:bearer|oauth)\s+[A-Za-z0-9._~+/=-]+", value):
            raise LiteGenerationError(f"Credential leaked into {label}")
        if re.search(r"(?i)[?&](?:token|key|signature|sig|auth)=", value):
            raise LiteGenerationError(f"Signed query leaked into {label}")


def write_json(path: Path, value: Any) -> None:
    assert_sanitized_metadata(value)
    provider_transport.atomic_write_json(path, value)


def _reconcile_run(root: Path, job: LiteJob, paths: dict[str, Path]) -> dict[str, Any]:
    expected = initial_run_artifact(root, job, paths)
    if not paths["run"].exists():
        return expected
    run = read_json(paths["run"])
    if not isinstance(run, dict):
        raise LiteGenerationError(f"Run artifact is not an object: {paths['run']}")
    assert_sanitized_metadata(run, relative(paths["run"], root))
    identity_keys = ("ticket", "agent_id", "lite_run_id", "model_id", "prompt_path", "output_path")
    identity_matches = all(run.get(key) == expected[key] for key in identity_keys)
    request_matches = (
        run.get("request") == expected["request"]
        and run.get("request_sha256") == expected["request_sha256"]
        and run.get("request_fingerprint_version") == REQUEST_FINGERPRINT_VERSION
    )
    if not identity_matches or not request_matches:
        run["status"] = "stale"
        run["error"] = (
            "Lite result, source binding, or runtime request changed; automatic submit is blocked"
        )
        return run
    if (
        run.get("status") == "submit-unknown"
        and "provider_job_id" in run
        and run["provider_job_id"] is None
        and isinstance(run.get("error"), str)
        and is_definitive_dns_pre_submit_failure(run["error"])
    ):
        run["status"] = "failed-pre-submit"
    return run


def materialize_plan(root: Path = ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in MATRIX:
        job = load_lite_job(root, entry)
        paths = artifact_paths(root, entry)
        paths["directory"].mkdir(parents=True, exist_ok=True)
        prompt = prompt_artifact(job)
        write_json(paths["prompt"], prompt)
        run = _reconcile_run(root, job, paths)
        write_json(paths["run"], run)
        rows.append({"entry": entry, "job": job, "paths": paths})
    write_aggregate_manifest(rows, root)
    return rows


def select_rows(
    rows: list[dict[str, Any]],
    run_ids: list[str],
    model_ids: list[str],
) -> list[dict[str, Any]]:
    known_runs = {entry.run_id for entry in MATRIX}
    unknown_runs = set(run_ids) - known_runs
    unknown_models = set(model_ids) - set(MODEL_CONFIGS)
    if unknown_runs:
        raise LiteGenerationError(f"Unknown fixed run IDs: {', '.join(sorted(unknown_runs))}")
    if unknown_models:
        raise LiteGenerationError(f"Unsupported model IDs: {', '.join(sorted(unknown_models))}")
    return [
        row
        for row in rows
        if (not run_ids or row["entry"].run_id in run_ids)
        and (not model_ids or row["entry"].model_id in model_ids)
    ]


def _media_contract(job: LiteJob, media: dict[str, Any]) -> dict[str, Any]:
    config = MODEL_CONFIGS[job.entry.model_id]
    duration = float(media.get("duration_seconds") or 0)
    width = int(media.get("width") or 0)
    height = int(media.get("height") or 0)
    expected_ratio = choose_aspect_ratio(
        job.entry.width,
        job.entry.height,
        config["aspect_ratios"],
    )
    left, right = expected_ratio.split(":", 1)
    expected_numeric_ratio = float(left) / float(right)
    actual_ratio = width / height if width > 0 and height > 0 else 0
    checks = {
        "duration": abs(duration - float(config["duration_seconds"])) <= 0.1,
        "audio": bool(media.get("has_audio")) is False,
        "resolution": min(width, height) == 1080,
        "aspect_ratio": actual_ratio > 0
        and abs(math.log(actual_ratio / expected_numeric_ratio)) <= 0.03,
    }
    warnings: list[str] = []
    for key, passed in checks.items():
        if not passed:
            warnings.append(f"{key} does not match the Lite request")
    return {
        "requested": {
            "duration_seconds": config["duration_seconds"],
            "resolution": config["resolution"],
            "aspect_ratio": expected_ratio,
            "generate_audio": False,
        },
        "checks": checks,
        "conforms": all(checks.values()),
        "warnings": warnings,
    }


def _persist_run(path: Path, run: dict[str, Any]) -> None:
    if run.get("error") is not None:
        run["error"] = safe_error(run["error"])
    write_json(path, run)


def _run_one(
    root: Path,
    row: dict[str, Any],
    *,
    dry_run: bool,
    base_url: str,
    timeout: int,
    poll_interval: float,
    external_processing_approved: bool = False,
) -> None:
    entry: MatrixEntry = row["entry"]
    paths: dict[str, Path] = row["paths"]

    # Required immediately before every provider job: re-run the trusted Lite
    # attestation and rebuild the request from the immutable result.json.
    job = load_lite_job(root, entry)
    expected_prompt = prompt_artifact(job)
    if read_json(paths["prompt"]) != expected_prompt:
        raise LiteGenerationError(f"Materialized prompt is stale: {entry.run_id}")
    run = _reconcile_run(root, job, paths)
    if run.get("status") == "stale":
        _persist_run(paths["run"], run)
        raise LiteGenerationError(f"Stale request is blocked: {entry.run_id}")

    if run.get("status") == "succeeded":
        if not paths["video"].is_file():
            raise LiteGenerationError(f"Succeeded run has no MP4: {entry.run_id}")
        return

    if dry_run:
        if not run.get("provider_job_id"):
            run.update(
                {
                    "status": "dry-run",
                    "request": sanitized_request(job),
                    "request_sha256": request_sha256(job),
                    "request_fingerprint_version": REQUEST_FINGERPRINT_VERSION,
                    "completed_at": None,
                    "media": None,
                    "contract_check": None,
                    "error": None,
                }
            )
            _persist_run(paths["run"], run)
        return

    if not external_processing_approved:
        raise LiteGenerationError(
            "Real run requires --allow-external-processing because the image and prompt "
            "are sent to the video provider"
        )

    status = run.get("status")
    provider_job_id = run.get("provider_job_id")
    if status in BLOCKED_STATUSES:
        raise LiteGenerationError(
            f"Run status {status!r} requires manual reconciliation; paid submit will not repeat: {entry.run_id}"
        )
    if provider_job_id and status not in ACTIVE_STATUSES:
        raise LiteGenerationError(
            f"Existing provider job is not automatically replaceable ({status!r}): {entry.run_id}"
        )

    try:
        headers = provider_transport.eliza_headers()
    except Exception as exc:
        run.update({"status": "failed-pre-submit", "error": safe_error(exc)})
        _persist_run(paths["run"], run)
        raise LiteGenerationError(run["error"]) from exc

    if not provider_job_id:
        run.update(
            {
                "status": "submitting",
                "provider_job_id": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
        try:
            response = provider_transport.http_json(
                "POST",
                f"{base_url.rstrip('/')}/videos",
                provider_request(job),
                headers=headers,
                timeout=120,
            )
            provider_job_id = provider_transport.find_job_id(response)
            if not provider_job_id:
                raise LiteGenerationError("Provider submit response did not contain a job ID")
        except Exception as exc:
            error = safe_error(exc)
            definitely_pre_submit = is_definitive_dns_pre_submit_failure(error)
            run.update(
                {
                    "status": "failed-pre-submit" if definitely_pre_submit else "submit-unknown",
                    "error": error,
                }
            )
            _persist_run(paths["run"], run)
            if definitely_pre_submit:
                raise LiteGenerationError(
                    "Provider DNS resolution failed before submit; this run is safe to retry"
                ) from exc
            raise LiteGenerationError(
                "Provider submit outcome is unknown; automatic retry is blocked to avoid duplicate billing"
            ) from exc
        run.update(
            {
                "status": "submitted",
                "provider_job_id": provider_job_id,
                "submitted_at": utc_now(),
                "error": None,
            }
        )
        _persist_run(paths["run"], run)

    run.update({"status": "running", "error": None})
    _persist_run(paths["run"], run)
    try:
        provider_transport.eliza_poll(base_url, provider_job_id, headers, timeout, poll_interval)
        provider_transport.http_download(
            f"{base_url.rstrip('/')}/videos/{provider_job_id}/content?index=0",
            paths["video"],
            headers=headers,
            timeout=600,
        )
        media = provider_transport.ffprobe_media(paths["video"])
        contract_check = _media_contract(job, media)
        run.update(
            {
                "status": "succeeded",
                "completed_at": utc_now(),
                "media": media,
                "contract_check": contract_check,
                "error": None,
            }
        )
        _persist_run(paths["run"], run)
    except Exception as exc:
        error = safe_error(exc)
        terminal_failure = any(marker in error.lower() for marker in TERMINAL_PROVIDER_FAILURE_MARKERS)
        run.update(
            {
                "status": "provider-failed" if terminal_failure else "submitted",
                "completed_at": utc_now() if terminal_failure else None,
                "error": error,
            }
        )
        _persist_run(paths["run"], run)
        raise LiteGenerationError(error) from exc


def run_rows(
    root: Path,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    base_url: str,
    timeout: int,
    poll_interval: float,
    fail_fast: bool,
    external_processing_approved: bool = False,
) -> int:
    if not dry_run and not external_processing_approved:
        raise LiteGenerationError(
            "Real run requires --allow-external-processing because the image and prompt "
            "are sent to the video provider"
        )
    failures = 0
    for index, row in enumerate(rows, start=1):
        entry: MatrixEntry = row["entry"]
        print(f"[{index}/{len(rows)}] {entry.run_id}", flush=True)
        try:
            _run_one(
                root,
                row,
                dry_run=dry_run,
                base_url=base_url,
                timeout=timeout,
                poll_interval=poll_interval,
                external_processing_approved=external_processing_approved,
            )
            print("  request validated; no network call" if dry_run else "  complete", flush=True)
        except LiteGenerationError as exc:
            failures += 1
            print(f"  failed: {safe_error(exc)}", file=sys.stderr, flush=True)
            if fail_fast:
                break
        finally:
            write_aggregate_manifest(materialized_rows(root), root)
    return failures


def materialized_rows(root: Path = ROOT) -> list[dict[str, Any]]:
    return [
        {
            "entry": entry,
            "paths": artifact_paths(root, entry),
        }
        for entry in MATRIX
    ]


def aggregate_manifest(rows: list[dict[str, Any]], root: Path, updated_at: str | None = None) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    for row in rows:
        entry: MatrixEntry = row["entry"]
        paths: dict[str, Path] = row["paths"]
        run = read_json(paths["run"]) if paths["run"].is_file() else {"status": "missing"}
        assert_sanitized_metadata(run, relative(paths["run"], root))
        status = run.get("status", "missing")
        summary[status] = summary.get(status, 0) + 1
        outputs.append(
            {
                "lite_run_id": entry.run_id,
                "sample_id": entry.sample_id,
                "article_slug": entry.article_slug,
                "source_path": entry.source_path,
                "model_id": entry.model_id,
                "status": status,
                "prompt_path": relative(paths["prompt"], root),
                "run_path": relative(paths["run"], root),
                "video_path": relative(paths["video"], root),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
            }
        )
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or utc_now(),
        "expected_outputs": len(MATRIX),
        "summary": summary,
        "outputs": outputs,
    }


def write_aggregate_manifest(rows: list[dict[str, Any]], root: Path = ROOT) -> dict[str, Any]:
    manifest = aggregate_manifest(rows, root)
    write_json(root / MANIFEST_RELATIVE_PATH, manifest)
    return manifest


def verify_materialized(root: Path = ROOT, allow_incomplete: bool = False) -> tuple[bool, list[str]]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    succeeded = 0
    for entry in MATRIX:
        paths = artifact_paths(root, entry)
        rows.append({"entry": entry, "paths": paths})
        try:
            job = load_lite_job(root, entry)
        except LiteGenerationError as exc:
            errors.append(str(exc))
            continue
        label = entry.run_id
        if not paths["prompt"].is_file() or not paths["run"].is_file():
            errors.append(f"Missing prompt/run artifact: {label}")
            continue
        try:
            prompt = read_json(paths["prompt"])
            run = read_json(paths["run"])
            assert_sanitized_metadata(prompt, relative(paths["prompt"], root))
            assert_sanitized_metadata(run, relative(paths["run"], root))
        except LiteGenerationError as exc:
            errors.append(str(exc))
            continue
        if prompt != prompt_artifact(job):
            errors.append(f"Materialized prompt differs from stamped Lite result: {label}")
        expected_run = initial_run_artifact(root, job, paths)
        for key in (
            "ticket",
            "agent_id",
            "lite_run_id",
            "model_id",
            "prompt_path",
            "output_path",
            "request",
            "request_sha256",
            "request_fingerprint_version",
        ):
            if run.get(key) != expected_run[key]:
                errors.append(f"Run artifact field mismatch ({key}): {label}")
        status = run.get("status")
        if status != "succeeded":
            if status == "stale":
                errors.append(f"Stale run artifact: {label}")
            elif not allow_incomplete:
                errors.append(f"Not succeeded ({status}): {label}")
            continue
        succeeded += 1
        if not paths["video"].is_file():
            errors.append(f"Succeeded run has no MP4: {label}")
            continue
        try:
            media = provider_transport.ffprobe_media(paths["video"])
        except Exception as exc:
            errors.append(safe_error(exc))
            continue
        recorded_media = run.get("media") or {}
        if media.get("sha256") != recorded_media.get("sha256") or media.get("bytes") != recorded_media.get("bytes"):
            errors.append(f"Recorded media digest or size mismatch: {label}")
        expected_contract = _media_contract(job, media)
        if run.get("contract_check") != expected_contract:
            errors.append(f"Recorded media contract mismatch: {label}")
        if not expected_contract["conforms"]:
            errors.append(f"Generated MP4 does not conform to Lite runtime: {label}")

    manifest_path = root / MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file():
        errors.append(f"Missing aggregate manifest: {MANIFEST_RELATIVE_PATH.as_posix()}")
    else:
        try:
            manifest = read_json(manifest_path)
            assert_sanitized_metadata(manifest, MANIFEST_RELATIVE_PATH.as_posix())
            updated_at = manifest.get("updated_at") if isinstance(manifest, dict) else None
            if not isinstance(updated_at, str) or manifest != aggregate_manifest(rows, root, updated_at):
                errors.append("Aggregate Lite manifest does not match materialized run artifacts")
        except LiteGenerationError as exc:
            errors.append(str(exc))
    if not allow_incomplete and succeeded != len(MATRIX):
        errors.append(f"Expected {len(MATRIX)} succeeded outputs, got {succeeded}")
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan", help="verify Lite provenance and materialize the fixed 10-job matrix")

    run_parser = subparsers.add_parser("run", help="generate or resume the fixed Lite matrix")
    run_parser.add_argument("--run-id", action="append", default=[], help="fixed schemafix run ID; repeatable")
    run_parser.add_argument("--model", action="append", default=[], help="exact Lite model ID; repeatable")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and write sanitized requests without network calls",
    )
    run_parser.add_argument(
        "--allow-external-processing",
        action="store_true",
        help="explicitly allow the source image and prompt to be sent to the video provider",
    )
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument("--timeout", type=int, default=1800, help="per-job wait timeout in seconds")
    run_parser.add_argument("--poll-interval", type=float, default=10.0)
    run_parser.add_argument("--eliza-base-url", default=DEFAULT_ELIZA_BASE_URL)

    verify_parser = subparsers.add_parser("verify", help="verify provenance, artifacts, and generated MP4s")
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            rows = materialize_plan(root)
            print(f"PASS: materialized {len(rows)} Clipmaker Lite prompt/run pairs")
            return 0
        if args.command == "run":
            rows = materialize_plan(root)
            selected = select_rows(rows, args.run_id, args.model)
            if not selected:
                raise LiteGenerationError("Filters selected no fixed matrix entries")
            failures = run_rows(
                root,
                selected,
                dry_run=args.dry_run,
                base_url=args.eliza_base_url,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                fail_fast=args.fail_fast,
                external_processing_approved=args.allow_external_processing,
            )
            write_aggregate_manifest(materialized_rows(root), root)
            if failures:
                print(f"FAIL: {failures} generation(s) failed", file=sys.stderr)
                return 1
            print(f"PASS: processed {len(selected)} Clipmaker Lite generation(s)")
            return 0
        if args.command == "verify":
            passed, errors = verify_materialized(root, allow_incomplete=args.allow_incomplete)
            if not passed:
                for error in errors:
                    print(f"FAIL: {safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: Clipmaker Lite generation artifacts are valid")
            return 0
        raise LiteGenerationError(f"Unknown command: {args.command}")
    except LiteGenerationError as exc:
        print(f"error: {safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
