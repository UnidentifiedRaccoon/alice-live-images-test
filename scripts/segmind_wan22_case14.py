#!/usr/bin/env python3
"""Run the single PROMOPAGES-9935 Eliza -> Segmind Wan 2.2 test.

The generation endpoint is synchronous and non-idempotent.  A durable attempt
receipt is written before the request and blocks every later generation call,
including calls made after a transport failure.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parents[1]
TICKET = "PROMOPAGES-9935"
ENDPOINT = "https://api.eliza.yandex.net/segmind/v1/wan-2.2-i2v-flash"
SOURCE_PATH = Path("PROMOPAGES-9857/articles/14-miuz-modnye-sergi/01.jpeg")
SOURCE_SHA256 = "7405154161aca78078f95474813f1927d0e203f80873077a5b8600bc21776dd6"
SOURCE_WIDTH = 1200
SOURCE_HEIGHT = 675
SOURCE_URL = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/77a13a75506331588ca2246531f92c25d33d692a/"
    "PROMOPAGES-9857/articles/14-miuz-modnye-sergi/01.jpeg"
)
OUTPUT_DIR = Path("PROMOPAGES-9935/14-miuz-modnye-sergi")
VIDEO_PATH = OUTPUT_DIR / "01.mp4"
RUN_PATH = OUTPUT_DIR / "01.run.json"
PROMPT_PATH = OUTPUT_DIR / "01.prompt.json"
SEED = 220214
ACCEPT_HEADER = "video/mp4, application/octet-stream"
ACCEPTED_VIDEO_CONTENT_TYPES = {"video/mp4", "application/octet-stream"}

POSITIVE_PROMPT = (
    "Only the two isolated lower-center teardrop pearl earrings move. Each pearl "
    "begins a small, even pendulum swing, slightly out of phase, with highlights "
    "sliding naturally across the curved surfaces. The camera remains completely "
    "fixed. The two fashion portraits, faces, bodies, clothing, upper jewelry pair, "
    "white background, and collage layout remain unchanged and still. The swing "
    "gradually loses amplitude; by the final frames both pearls return close to "
    "vertical with only a faint residual sway."
)
NEGATIVE_PROMPT = (
    "camera movement, zoom, pan, tilt, crop, reframing, scene cuts, morphing, "
    "duplicated or missing jewelry, extra earrings or pearls, deformed pearls, "
    "warped metal, changing faces or bodies, blinking, head movement, moving "
    "clothing, changing background or collage layout, text, logos, watermark, "
    "flicker, jitter, blur, low detail"
)

SECRET_RE = re.compile(
    r"(?i)([\"']?authorization[\"']?\s*[:=]\s*[\"']?(?:bearer|oauth)\s+)"
    r"[^\"'\s,;}]+|"
    r"([\"']?(?:access[_-]?token|api[_-]?key|token)[\"']?\s*[:=]\s*[\"']?)"
    r"[^\"'\s,;}]+"
)


class Case14Error(RuntimeError):
    """A fail-closed, user-actionable test error."""


class RejectRedirects(HTTPRedirectHandler):
    """Prevent a redirect from becoming a second non-idempotent POST."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_error(error: BaseException | str) -> str:
    message = str(error)
    for name in (
        "ELIZA_OAUTH_TOKEN",
        "ELIZA_TOKEN",
        "ANTHROPIC_AUTH_TOKEN",
    ):
        secret = os.environ.get(name)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = SECRET_RE.sub(
        lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", message
    )
    return message[:2000]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise Case14Error(f"JSON file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Case14Error(f"Invalid JSON in {path}: {exc}") from exc


def relative(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise Case14Error(f"Path escapes workspace: {path}") from exc


def resolve_token() -> str:
    token = (
        os.environ.get("ELIZA_OAUTH_TOKEN")
        or os.environ.get("ELIZA_TOKEN")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )
    if not token:
        raise Case14Error(
            "Set ELIZA_OAUTH_TOKEN, ELIZA_TOKEN, or the configured "
            "ANTHROPIC_AUTH_TOKEN before generation"
        )
    return token


def resolve_pool() -> str | None:
    return os.environ.get("ELIZA_POOL") or os.environ.get("YA_POOL") or None


def sanitized_request_headers(pool: str | None) -> dict[str, str | None]:
    return {
        "Content-Type": "application/json",
        "Accept": ACCEPT_HEADER,
        "X-Retries": "1",
        "X-Include-Cost": "true",
        "Ya-Pool": pool,
        "Authorization": "[REDACTED]",
    }


def request_parameters() -> dict[str, Any]:
    return {
        "image": SOURCE_URL,
        "prompt": POSITIVE_PROMPT,
        "negative_prompt": NEGATIVE_PROMPT,
        "resolution": "720p",
        "prompt_extend": False,
        "watermark": False,
        "seed": SEED,
    }


def public_prompt_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "route": "eliza-segmind",
        "model": "wan-2.2-i2v-flash",
        "source": {
            "path": SOURCE_PATH.as_posix(),
            "url": SOURCE_URL,
            "sha256": SOURCE_SHA256,
            "width": SOURCE_WIDTH,
            "height": SOURCE_HEIGHT,
            "content_review": (
                "Public PromoPages editorial image; no NDA, credentials, logins, "
                "private customer data, or private user data. The fashion portraits "
                "already appear in the public source material."
            ),
        },
        "motion": {
            "object": "two isolated lower-center teardrop pearl earrings",
            "camera": "fixed",
            "invariants": (
                "portraits, faces, bodies, clothing, upper jewelry, background, "
                "and collage layout remain unchanged"
            ),
            "terminal_state": (
                "both pearls are close to vertical with faint residual sway"
            ),
        },
        "prompt": {
            "positive": POSITIVE_PROMPT,
            "negative": NEGATIVE_PROMPT,
        },
        "parameters": {
            "resolution": "720p",
            "prompt_extend": False,
            "watermark": False,
            "seed": SEED,
        },
    }


def prepared_run_document(root: Path = ROOT) -> dict[str, Any]:
    prompt_path = root / PROMPT_PATH
    prompt_sha256 = sha256_file(prompt_path) if prompt_path.is_file() else None
    return {
        "schema_version": 1,
        "ticket": TICKET,
        "status": "prepared",
        "route": {
            "provider": "segmind",
            "gateway": "eliza",
            "model": "wan-2.2-i2v-flash",
            "endpoint": ENDPOINT,
            "synchronous": True,
            "automatic_retry": False,
        },
        "source": public_prompt_document()["source"],
        "prompt_path": relative(prompt_path, root),
        "prompt_sha256": prompt_sha256,
        "request": {
            "parameters": request_parameters(),
            "headers": sanitized_request_headers(resolve_pool()),
        },
        "attempt": None,
        "response": None,
        "artifact": None,
        "media": None,
    }


@contextmanager
def generation_lock(root: Path):
    lock_key = sha256_bytes(str(root.resolve()).encode("utf-8"))[:20]
    lock_path = Path(tempfile.gettempdir()) / f"alice-live-{TICKET.lower()}-{lock_key}.lock"
    with lock_path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def verify_prompt_binding(root: Path, run: dict[str, Any]) -> None:
    expected_prompt = public_prompt_document()
    prompt_path = root / PROMPT_PATH
    if run.get("prompt_path") != PROMPT_PATH.as_posix():
        raise Case14Error("Run receipt points to an unexpected prompt path")
    if not prompt_path.is_file():
        raise Case14Error("Prompt document is missing")
    if read_json(prompt_path) != expected_prompt:
        raise Case14Error("Prompt document changed after preparation")
    prompt_sha256 = sha256_file(prompt_path)
    if run.get("prompt_sha256") != prompt_sha256:
        raise Case14Error("Prompt SHA-256 does not match the run receipt")
    if run.get("source") != expected_prompt["source"]:
        raise Case14Error("Source binding changed after preparation")
    if (run.get("request") or {}).get("parameters") != request_parameters():
        raise Case14Error("Request parameters changed after preparation")
    recorded_headers = (run.get("request") or {}).get("headers")
    if not isinstance(recorded_headers, dict):
        raise Case14Error("Sanitized request headers are missing from the receipt")
    recorded_pool = recorded_headers.get("Ya-Pool")
    if recorded_pool is not None and (
        not isinstance(recorded_pool, str) or not recorded_pool
    ):
        raise Case14Error("Recorded Ya-Pool must be a non-empty string or null")
    if recorded_headers != sanitized_request_headers(recorded_pool):
        raise Case14Error("Sanitized request headers changed after preparation")
    expected_route = {
        "provider": "segmind",
        "gateway": "eliza",
        "model": "wan-2.2-i2v-flash",
        "endpoint": ENDPOINT,
        "synchronous": True,
        "automatic_retry": False,
    }
    if run.get("route") != expected_route:
        raise Case14Error("Generation route changed after preparation")


def _prepare_locked(root: Path) -> dict[str, Any]:
    source = root / SOURCE_PATH
    if not source.is_file():
        raise Case14Error(f"Source image does not exist: {source}")
    if sha256_file(source) != SOURCE_SHA256:
        raise Case14Error("Case-14 source image SHA-256 changed")
    prompt_path = root / PROMPT_PATH
    prompt_document = public_prompt_document()
    if prompt_path.exists():
        if read_json(prompt_path) != prompt_document:
            raise Case14Error("Existing prompt document is immutable and no longer matches")
    else:
        write_json(prompt_path, prompt_document)
    run_path = root / RUN_PATH
    if run_path.exists():
        run = read_json(run_path)
        verify_prompt_binding(root, run)
        return run
    run = prepared_run_document(root)
    write_json(run_path, run)
    return run


def prepare(root: Path = ROOT) -> dict[str, Any]:
    with generation_lock(root):
        return _prepare_locked(root)


def verify_public_source(
    opener: Callable[..., Any] = urlopen,
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    parsed = urlparse(SOURCE_URL)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise Case14Error("Source URL must be commit-pinned HTTPS raw.githubusercontent.com")
    request = Request(SOURCE_URL, headers={"Accept": "image/jpeg"}, method="GET")
    try:
        with opener(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            payload = response.read()
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        raise Case14Error(f"Public source URL returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise Case14Error(f"Public source URL is unavailable: {safe_error(exc.reason)}") from exc
    if status != 200:
        raise Case14Error(f"Public source URL returned HTTP {status}")
    if content_type not in {"image/jpeg", "image/jpg"}:
        raise Case14Error(f"Public source URL returned unexpected Content-Type: {content_type}")
    if sha256_bytes(payload) != SOURCE_SHA256:
        raise Case14Error("Public source URL bytes do not match the local case-14 image")
    return {
        "status": status,
        "content_type": content_type,
        "bytes": len(payload),
        "sha256": SOURCE_SHA256,
        "immutable_commit_url": True,
    }


def parse_rate(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return round(float(Fraction(value)), 6)
    except (ValueError, ZeroDivisionError):
        return None


def ffprobe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-show_streams",
        "-show_format",
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
        )
    except FileNotFoundError as exc:
        raise Case14Error("ffprobe is required for generation verification") from exc
    if process.returncode != 0:
        raise Case14Error(safe_error(f"ffprobe failed: {process.stderr.strip()}"))
    try:
        probe = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise Case14Error("ffprobe returned invalid JSON") from exc
    streams = probe.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if not isinstance(video, dict):
        raise Case14Error("Generated response has no video stream")
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    format_data = probe.get("format") or {}
    try:
        duration = float(format_data.get("duration"))
    except (TypeError, ValueError) as exc:
        raise Case14Error("Generated response has no readable format.duration") from exc
    try:
        frames = int(video.get("nb_read_frames"))
    except (TypeError, ValueError) as exc:
        raise Case14Error("ffprobe did not return exact nb_read_frames") from exc
    return {
        "container": format_data.get("format_name"),
        "duration_seconds": round(duration, 6),
        "size_bytes": path.stat().st_size,
        "bit_rate_bps": int(format_data["bit_rate"]) if format_data.get("bit_rate") else None,
        "video": {
            "codec": video.get("codec_name"),
            "profile": video.get("profile"),
            "width": video.get("width"),
            "height": video.get("height"),
            "avg_frame_rate": video.get("avg_frame_rate"),
            "avg_fps": parse_rate(video.get("avg_frame_rate")),
            "r_frame_rate": video.get("r_frame_rate"),
            "r_fps": parse_rate(video.get("r_frame_rate")),
            "nb_read_frames": frames,
            "bit_rate_bps": int(video["bit_rate"]) if video.get("bit_rate") else None,
        },
        "has_audio": isinstance(audio, dict),
        "audio": (
            {
                "codec": audio.get("codec_name"),
                "channels": audio.get("channels"),
                "channel_layout": audio.get("channel_layout"),
                "sample_rate_hz": (
                    int(audio["sample_rate"]) if audio.get("sample_rate") else None
                ),
                "bit_rate_bps": int(audio["bit_rate"]) if audio.get("bit_rate") else None,
            }
            if isinstance(audio, dict)
            else None
        ),
    }


def verify_media_contract(media: dict[str, Any]) -> None:
    def close_to(value: Any, expected: float, tolerance: float) -> bool:
        try:
            return abs(float(value) - expected) <= tolerance
        except (TypeError, ValueError):
            return False

    video = media.get("video") or {}
    checks = {
        "container": "mp4" in str(media.get("container") or ""),
        "codec": video.get("codec") == "h264",
        "resolution": (video.get("width"), video.get("height")) == (1280, 720),
        "duration": close_to(media.get("duration_seconds"), 5.0, 0.05),
        "avg_fps": close_to(video.get("avg_fps"), 30.0, 0.001),
        "r_fps": close_to(video.get("r_fps"), 30.0, 0.001),
        "frames": video.get("nb_read_frames") == 150,
        "audio": media.get("has_audio") is False and media.get("audio") is None,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise Case14Error(
            "Generated media failed the fixed contract: " + ", ".join(failed)
        )


def response_cost(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except ValueError:
        numeric = None
    return {"raw": value, "numeric": numeric, "currency": "USD"}


def generate(
    root: Path = ROOT,
    *,
    opener: Any | None = None,
    source_opener: Callable[..., Any] = urlopen,
    timeout: int = 1800,
    probe: Callable[[Path], dict[str, Any]] = ffprobe_media,
) -> dict[str, Any]:
    run = prepare(root)
    if run.get("attempt") is not None or run.get("status") != "prepared":
        raise Case14Error(
            "Generation is permanently blocked because this run already has an attempt receipt"
        )
    if (root / VIDEO_PATH).exists():
        raise Case14Error("Generation is blocked because the output MP4 already exists")

    source_check = verify_public_source(source_opener)
    token = resolve_token()
    pool = resolve_pool()
    attempt_started = utc_now()
    started_monotonic = time.monotonic()
    run_path = root / RUN_PATH
    with generation_lock(root):
        run = read_json(run_path)
        verify_prompt_binding(root, run)
        if run.get("attempt") is not None or run.get("status") != "prepared":
            raise Case14Error(
                "Generation is permanently blocked because this run already has an attempt receipt"
            )
        if (root / VIDEO_PATH).exists():
            raise Case14Error("Generation is blocked because the output MP4 already exists")
        recorded_pool = run["request"]["headers"]["Ya-Pool"]
        if pool != recorded_pool:
            raise Case14Error(
                "Ya-Pool changed after preparation; restore the recorded environment "
                "before generation"
            )
        pool = recorded_pool
        run["status"] = "running"
        run["attempt"] = {
            "started_at": attempt_started,
            "request_dispatched": False,
            "single_attempt_guard": True,
            "source_preflight": source_check,
        }
        write_json(run_path, run)

    headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
        "Accept": ACCEPT_HEADER,
        "X-Retries": "1",
        "X-Include-Cost": "true",
    }
    if pool:
        headers["Ya-Pool"] = pool
    body = json.dumps(request_parameters(), ensure_ascii=False).encode("utf-8")
    request = Request(ENDPOINT, data=body, method="POST")
    for name, value in headers.items():
        request.add_unredirected_header(name, value)
    client = opener or build_opener(RejectRedirects())
    video_path = root / VIDEO_PATH
    video_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        run["attempt"]["request_dispatched"] = True
        write_json(run_path, run)
        with client.open(request, timeout=timeout) as response, tempfile.NamedTemporaryFile(
            "wb", dir=video_path.parent, prefix=f".{video_path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                stream.write(chunk)
            status = getattr(response, "status", 200)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            request_id = response.headers.get("X-Segmind-Request-Id")
            cost = response.headers.get("X-Response-Cost")
        run["response"] = {
            "http_status": status,
            "content_type": content_type,
            "x_segmind_request_id": request_id,
            "x_response_cost": response_cost(cost),
        }
        if status < 200 or status >= 300:
            raise Case14Error(f"Generation returned unexpected HTTP {status}")
        if content_type not in ACCEPTED_VIDEO_CONTENT_TYPES:
            raise Case14Error(
                f"Generation returned unexpected Content-Type: {content_type or '[missing]'}"
            )
        if temporary.stat().st_size == 0:
            raise Case14Error("Generation returned an empty response body")
        temporary.replace(video_path)
        temporary = None
        latency = round(time.monotonic() - started_monotonic, 3)
        run["artifact"] = {
            "path": relative(video_path, root),
            "bytes": video_path.stat().st_size,
            "sha256": sha256_file(video_path),
        }
        verification_error: Case14Error | None = None
        try:
            run["media"] = probe(video_path)
            verify_media_contract(run["media"])
            run["status"] = "succeeded"
        except Exception as exc:
            run["status"] = "verification_failed"
            run["error"] = {"stage": "ffprobe", "message": safe_error(exc)}
            verification_error = Case14Error(
                f"Generated artifact failed verification: {safe_error(exc)}"
            )
        run["attempt"].update(
            {
                "finished_at": utc_now(),
                "latency_seconds": latency,
            }
        )
        write_json(run_path, run)
        if verification_error is not None:
            raise verification_error
        return run
    except HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        request_id = exc.headers.get("X-Segmind-Request-Id") if exc.headers else None
        cost = exc.headers.get("X-Response-Cost") if exc.headers else None
        error = Case14Error(
            safe_error(f"Generation failed with HTTP {exc.code}: {detail}")
        )
        run["response"] = {
            "http_status": exc.code,
            "content_type": (
                exc.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if exc.headers
                else None
            ),
            "x_segmind_request_id": request_id,
            "x_response_cost": response_cost(cost),
        }
        run["status"] = "failed"
        run["error"] = {"stage": "generation", "message": safe_error(error)}
        run["attempt"].update(
            {
                "finished_at": utc_now(),
                "latency_seconds": round(time.monotonic() - started_monotonic, 3),
            }
        )
        write_json(run_path, run)
        raise error from exc
    except Exception as exc:
        if run.get("status") == "verification_failed":
            if isinstance(exc, Case14Error):
                raise
            raise Case14Error(
                f"Generated artifact failed verification: {safe_error(exc)}"
            ) from exc
        run["status"] = "failed"
        run["error"] = {"stage": "generation", "message": safe_error(exc)}
        run["attempt"].update(
            {
                "finished_at": utc_now(),
                "latency_seconds": round(time.monotonic() - started_monotonic, 3),
            }
        )
        write_json(run_path, run)
        if isinstance(exc, Case14Error):
            raise
        if isinstance(exc, URLError):
            raise Case14Error(f"Generation transport failed: {safe_error(exc.reason)}") from exc
        raise Case14Error(f"Generation failed: {safe_error(exc)}") from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def verify(root: Path = ROOT) -> dict[str, Any]:
    run_path = root / RUN_PATH
    run = read_json(run_path)
    if run.get("status") != "succeeded":
        raise Case14Error(f"Run is not successful: {run.get('status')}")
    verify_prompt_binding(root, run)
    video_path = root / VIDEO_PATH
    artifact = run.get("artifact") or {}
    if artifact.get("path") != VIDEO_PATH.as_posix():
        raise Case14Error("Generated MP4 path does not match the receipt")
    if not video_path.is_file():
        raise Case14Error("Generated MP4 is missing")
    if artifact.get("sha256") != sha256_file(video_path):
        raise Case14Error("Generated MP4 SHA-256 does not match the receipt")
    if artifact.get("bytes") != video_path.stat().st_size:
        raise Case14Error("Generated MP4 size does not match the receipt")
    current_media = ffprobe_media(video_path)
    verify_media_contract(current_media)
    if current_media != run.get("media"):
        raise Case14Error("Current ffprobe metadata does not match the receipt")
    if (run.get("response") or {}).get("http_status") != 200:
        raise Case14Error("Successful run must record HTTP 200")
    if (run.get("response") or {}).get("content_type") not in ACCEPTED_VIDEO_CONTENT_TYPES:
        raise Case14Error("Successful run has an invalid video Content-Type")
    if not (run.get("response") or {}).get("x_segmind_request_id"):
        raise Case14Error("Successful run is missing X-Segmind-Request-Id")
    response_cost_data = (run.get("response") or {}).get("x_response_cost") or {}
    if response_cost_data.get("numeric") != 0.18 or response_cost_data.get("currency") != "USD":
        raise Case14Error("Successful run has an invalid X-Response-Cost")
    source_preflight = (run.get("attempt") or {}).get("source_preflight") or {}
    if (
        (run.get("attempt") or {}).get("request_dispatched") is not True
        or source_preflight.get("sha256") != SOURCE_SHA256
        or source_preflight.get("immutable_commit_url") is not True
    ):
        raise Case14Error("Successful run has an invalid source preflight receipt")
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare", help="write prompt and a no-network prepared receipt")
    generate_parser = subparsers.add_parser(
        "generate", help="perform the one allowed paid generation request"
    )
    generate_parser.add_argument("--timeout", type=int, default=1800)
    subparsers.add_parser("verify", help="re-run ffprobe and verify the saved receipt")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            run = prepare()
        elif args.command == "generate":
            run = generate(timeout=args.timeout)
        else:
            run = verify()
    except Case14Error as exc:
        print(f"ERROR: {safe_error(exc)}", file=os.sys.stderr)
        return 1
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
