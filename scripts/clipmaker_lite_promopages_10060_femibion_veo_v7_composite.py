#!/usr/bin/env python3
"""Reproduce and validate the deterministic Femibion V7 video composite.

The composite is derived media.  It combines the immutable V4 base JPEG with
one masked patch from the successful raw V7 Veo output.  It is not a new
provider output and this helper never calls a provider, uploads media, or edits
the canonical aggregate/demo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_promopages_10060_pipeline as pipeline  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
MODEL_ID = "google/veo-3.1-lite"
ARTICLE_SLUG = "07-femibion-gotovites-k-beremennosti"
IMAGE_ID = "06"
SAMPLE_ID = f"{ARTICLE_SLUG}-{IMAGE_ID}"
V7_RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v7"
V7_PROVIDER_BATCH_ID = f"{V7_RECOVERY_ID}-provider"
V7_PLANNING_RUN_ID = f"{V7_RECOVERY_ID}-{SAMPLE_ID}"
V7_PROVIDER_RUN_ID = f"{V7_PROVIDER_BATCH_ID}-{SAMPLE_ID}-veo-3-1-lite"
V7_PROVIDER_JOB_ID = "c4pO6Fw8YaEz0vPon3wH"
V7_REQUEST_SHA256 = (
    "e6c5a3b9586df1f116846afcae103e9475de69883add0330e7a4804922daf522"
)

V7_ROOT_REL = Path("clipmaker-lite-test/runs") / V7_RECOVERY_ID
BASE_V4_REL = Path(
    "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v4/articles/"
    f"{ARTICLE_SLUG}/06.jpeg"
)
RAW_VIDEO_REL = V7_ROOT_REL / f"videos/{ARTICLE_SLUG}/veo-3.1-lite/06.mp4"
RAW_PROMPT_REL = V7_ROOT_REL / f"videos/{ARTICLE_SLUG}/veo-3.1-lite/06.prompt.json"
RAW_RUN_REL = V7_ROOT_REL / f"videos/{ARTICLE_SLUG}/veo-3.1-lite/06.run.json"
RAW_GENERATION_MANIFEST_REL = V7_ROOT_REL / "generation-manifest.json"
PLANNING_RESULT_REL = (
    Path("artifacts/clipmaker-lite/v1") / V7_PLANNING_RUN_ID / "result.json"
)
COMPOSITE_VIDEO_REL = (
    V7_ROOT_REL / f"composite/videos/{ARTICLE_SLUG}/veo-3.1-lite/06.mp4"
)
RECEIPT_REL = (
    V7_ROOT_REL / f"composite/videos/{ARTICLE_SLUG}/veo-3.1-lite/06.receipt.json"
)

BASE_V4_SHA256 = (
    "f3eac13ca2c71c7cec3a1a860c701caea68728a3f9dc9e77c1d05b2455143ce9"
)
BASE_V4_BYTES = 449309
RAW_VIDEO_SHA256 = (
    "b07cb490b963d0e8b0718a08e1e579039cf0dcb9e75a241f3090c117658f6f45"
)
RAW_VIDEO_BYTES = 2146714
RAW_PROMPT_SHA256 = (
    "3bcac53a27768f16fd640ae79b6f6229ad8baea6e3a6170a234ec95cba70a208"
)
RAW_RUN_SHA256 = (
    "dff03db2df123899a9990f915b4eb993de47865a6e93e1d8a01eeeea94f636d7"
)
RAW_GENERATION_MANIFEST_SHA256 = (
    "1c449be1e1438d181909db15ed571b51ccf0edc35cd0b942da68efeb04c779b6"
)
PLANNING_RESULT_SHA256 = (
    "73f878a18d9f063a4ed674efd6601c140ff5e406700f619bbc4acb065f75d1b0"
)
COMPOSITE_SHA256 = (
    "d058fe8556e2f3badaa436745b1aa6e30ff0e726ef1648134225508e5917e13c"
)
COMPOSITE_BYTES = 552368

FFMPEG_REAL_PATH = Path("/opt/homebrew/Cellar/ffmpeg/8.1.2_1/bin/ffmpeg")
FFPROBE_REAL_PATH = Path("/opt/homebrew/Cellar/ffmpeg/8.1.2_1/bin/ffprobe")
FFMPEG_SHA256 = (
    "dad4b30b36a1a999bfa4b6ffbde138bd17ee496c69e12eef638227dff2c6415c"
)
FFPROBE_SHA256 = (
    "cfeefcc9207eb3fa424679228fe3848db2921b15537d26c1ccc4a7a61de95d00"
)
FFMPEG_VERSION = "ffmpeg version 8.1.2 Copyright (c) 2000-2026 the FFmpeg developers"
FFPROBE_VERSION = "ffprobe version 8.1.2 Copyright (c) 2007-2026 the FFmpeg developers"

FILTERGRAPH = (
    "[1:v]scale=800:450:flags=lanczos,format=rgba[patch];"
    "color=c=black:s=800x450:r=24:d=4,format=gray,"
    "drawbox=x=55:y=150:w=300:h=230:color=0xD0D0D0:t=fill,"
    "gblur=sigma=32[mask];"
    "[patch][mask]alphamerge[patcha];"
    "[0:v]format=rgba[base];"
    "[base][patcha]overlay=x=1120:y=250:format=auto,"
    "scale=in_range=pc:out_range=tv,format=yuv420p,"
    "setparams=range=tv[out]"
)

EXPECTED_PLANNING_PROVENANCE = {
    "verified": True,
    "verification_scope": "trusted-workspace-route",
    "cryptographically_signed": False,
    "result_path": PLANNING_RESULT_REL.as_posix(),
    "agent_id": AGENT_ID,
    "contract_version": "2.0.8",
    "contract_fingerprint": (
        "sha256:68bb2b26b16b65814182b883e425955559a8fd034e1835ceb0a68a22a50ca50a"
    ),
    "instruction_bundle_sha256": (
        "7a2d6d51289b14580cf93abbbb8d03ccec5853a3256137f68a15a150f489b531"
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
            "e4432c0c085e4a2e5b9cf982e4dd2ebdb44ed33c422827b6e6c64353778e773b"
        ),
        "version": "codex-cli 0.147.0-alpha.6.5",
        "requested_model": None,
        "thread_id": "019feb2c-0378-7790-aee3-a211f76a371e",
    },
    "models": [MODEL_ID],
    "source_image_sha256": (
        "31672c5832458e9698f2a5710a159b10cbb99febf55c7f1b0906393f977cb88e"
    ),
    "article_context_sha256": (
        "3db3fbc0a8ad5d263fd445df6add5ad5343e9eaf67529aba787ebc6e096452f8"
    ),
}

RAW_MEDIA = {
    "container": "mov,mp4,m4a,3gp,3g2,mj2",
    "codec": "h264",
    "profile": "High",
    "level": 40,
    "duration_seconds": 4.0,
    "width": 1920,
    "height": 1080,
    "pixel_format": "yuv420p",
    "fps": 24.0,
    "frames": 96,
    "has_audio": False,
    "bytes": RAW_VIDEO_BYTES,
    "sha256": RAW_VIDEO_SHA256,
}

COMPOSITE_MEDIA = {
    "container": "mov,mp4,m4a,3gp,3g2,mj2",
    "codec": "h264",
    "profile": "High",
    "level": 50,
    "duration_seconds": 4.0,
    "width": 1920,
    "height": 1080,
    "pixel_format": "yuv420p",
    "fps": 24.0,
    "frames": 96,
    "has_audio": False,
    "bytes": COMPOSITE_BYTES,
    "sha256": COMPOSITE_SHA256,
}

FRAME_CHECKSUMS = {
    "algorithm": "md5-decoded-yuv420p",
    "decoded_frame_bytes": 3110400,
    "unique_frame_checksums": 96,
    "samples": {
        "0": "845e82049b5973588d963dcd0ea528ac",
        "48": "507f6a95cb510929bf77669c189b84bf",
        "95": "9d2e8c895c66aed1567e8a4e1b01ef71",
    },
}


class CompositeError(RuntimeError):
    """A fail-closed V7 composite validation/reproduction error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CompositeError(f"Cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise CompositeError(f"Cannot read JSON {path}: {exc}") from exc


def _require_file(root: Path, relative: Path, sha256: str, size: int | None = None) -> Path:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise CompositeError(f"Missing or unsafe immutable file: {path}")
    if sha256_file(path) != sha256:
        raise CompositeError(f"Immutable file digest changed: {path}")
    if size is not None and path.stat().st_size != size:
        raise CompositeError(f"Immutable file size changed: {path}")
    return path


def _run(command: list[str], *, cwd: Path) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise CompositeError(f"Command failed: {detail.strip()}") from exc
    return completed.stdout


def _validate_tool(name: str, expected_path: Path, expected_sha: str, version: str) -> Path:
    resolved_name = shutil.which(name)
    if resolved_name is None:
        raise CompositeError(f"Required tool is unavailable: {name}")
    resolved = Path(resolved_name).resolve()
    if resolved != expected_path or sha256_file(resolved) != expected_sha:
        raise CompositeError(f"Frozen {name} binary changed: {resolved}")
    actual_version = _run([str(resolved), "-version"], cwd=ROOT).splitlines()[0]
    if actual_version != version:
        raise CompositeError(f"Frozen {name} version changed: {actual_version}")
    return resolved


def validate_tools() -> tuple[Path, Path]:
    return (
        _validate_tool("ffmpeg", FFMPEG_REAL_PATH, FFMPEG_SHA256, FFMPEG_VERSION),
        _validate_tool("ffprobe", FFPROBE_REAL_PATH, FFPROBE_SHA256, FFPROBE_VERSION),
    )


def _fraction(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    return float(numerator) / float(denominator)


def probe_video(path: Path, ffprobe: Path, *, root: Path = ROOT) -> dict[str, Any]:
    payload = _run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            (
                "stream=index,codec_type,codec_name,profile,level,width,height,"
                "pix_fmt,r_frame_rate,avg_frame_rate,nb_frames,duration:"
                "format=format_name,duration,size"
            ),
            "-of",
            "json",
            str(path),
        ],
        cwd=root,
    )
    document = json.loads(payload)
    streams = document.get("streams")
    video = [item for item in streams or [] if item.get("codec_type") == "video"]
    audio = [item for item in streams or [] if item.get("codec_type") == "audio"]
    if len(video) != 1 or audio:
        raise CompositeError(f"Expected one video stream and no audio: {path}")
    stream = video[0]
    media_format = document.get("format", {})
    fps = _fraction(stream["avg_frame_rate"])
    return {
        "container": media_format.get("format_name"),
        "codec": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "level": stream.get("level"),
        "duration_seconds": float(media_format.get("duration")),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "pixel_format": stream.get("pix_fmt"),
        "fps": fps,
        "frames": int(stream.get("nb_frames")),
        "has_audio": False,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def probe_image(path: Path, ffprobe: Path, *, root: Path = ROOT) -> dict[str, Any]:
    payload = _run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        cwd=root,
    )
    streams = json.loads(payload).get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise CompositeError(f"Cannot identify base image stream: {path}")
    return {
        "width": streams[0].get("width"),
        "height": streams[0].get("height"),
        "pixel_format": streams[0].get("pix_fmt"),
    }


def mp4_atoms(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    offset = 0
    atoms: list[dict[str, Any]] = []
    while offset + 8 <= len(data):
        size = int.from_bytes(data[offset : offset + 4], "big")
        atom_type = data[offset + 4 : offset + 8].decode("ascii", errors="strict")
        header = 8
        if size == 1:
            if offset + 16 > len(data):
                raise CompositeError(f"Truncated extended MP4 atom: {path}")
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            raise CompositeError(f"Invalid MP4 atom layout: {path}")
        atoms.append({"type": atom_type, "offset": offset, "bytes": size})
        offset += size
    if offset != len(data):
        raise CompositeError(f"MP4 has trailing bytes outside atoms: {path}")
    by_type = {item["type"]: item for item in atoms}
    if "moov" not in by_type or "mdat" not in by_type:
        raise CompositeError(f"MP4 lacks moov/mdat atoms: {path}")
    return {
        "top_level": atoms,
        "faststart": by_type["moov"]["offset"] < by_type["mdat"]["offset"],
        "moov_offset": by_type["moov"]["offset"],
        "mdat_offset": by_type["mdat"]["offset"],
    }


def frame_checksums(path: Path, ffmpeg: Path, *, root: Path = ROOT) -> dict[str, Any]:
    output = _run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-f",
            "framemd5",
            "-",
        ],
        cwd=root,
    )
    checksums: list[str] = []
    sizes: set[int] = set()
    for line in output.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 6:
            raise CompositeError("Unexpected framemd5 output")
        sizes.add(int(fields[4]))
        checksums.append(fields[5])
    if len(checksums) != 96 or sizes != {3110400}:
        raise CompositeError("Decoded composite frame geometry/count changed")
    return {
        "algorithm": "md5-decoded-yuv420p",
        "decoded_frame_bytes": 3110400,
        "unique_frame_checksums": len(set(checksums)),
        "samples": {
            "0": checksums[0],
            "48": checksums[48],
            "95": checksums[95],
        },
    }


def ffmpeg_arguments(output: str) -> list[str]:
    return [
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        "24",
        "-i",
        BASE_V4_REL.as_posix(),
        "-i",
        RAW_VIDEO_REL.as_posix(),
        "-filter_complex",
        FILTERGRAPH,
        "-map",
        "[out]",
        "-t",
        "4",
        "-r",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        "-an",
        output,
    ]


def receipt_document() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_role": "clipmaker-lite-deterministic-video-composite",
        "ticket": TICKET,
        "composite_id": f"{V7_RECOVERY_ID}-base-v4-patch-v1",
        "logical_key": {
            "article_slug": ARTICLE_SLUG,
            "image_id": IMAGE_ID,
            "model_id": MODEL_ID,
        },
        "classification": {
            "artifact_kind": "deterministic-composite",
            "provider_output": False,
            "derived_from_provider_output": True,
            "new_provider_submission": False,
            "provider_model_lineage": MODEL_ID,
            "eligible_as_derived_demo_media": True,
        },
        "inputs": {
            "base_v4_jpeg": {
                "path": BASE_V4_REL.as_posix(),
                "sha256": BASE_V4_SHA256,
                "bytes": BASE_V4_BYTES,
                "width": 1920,
                "height": 1080,
                "pixel_format": "yuvj444p",
            },
            "raw_v7_provider_video": {
                "path": RAW_VIDEO_REL.as_posix(),
                "sha256": RAW_VIDEO_SHA256,
                "bytes": RAW_VIDEO_BYTES,
                "provider_run_id": V7_PROVIDER_RUN_ID,
                "provider_job_id": V7_PROVIDER_JOB_ID,
                "request_sha256": V7_REQUEST_SHA256,
                "media": RAW_MEDIA,
            },
            "raw_v7_receipts": {
                "generation_manifest": {
                    "path": RAW_GENERATION_MANIFEST_REL.as_posix(),
                    "sha256": RAW_GENERATION_MANIFEST_SHA256,
                },
                "prompt": {
                    "path": RAW_PROMPT_REL.as_posix(),
                    "sha256": RAW_PROMPT_SHA256,
                },
                "run": {
                    "path": RAW_RUN_REL.as_posix(),
                    "sha256": RAW_RUN_SHA256,
                },
            },
            "verified_lite_planning": {
                "planning_run_id": V7_PLANNING_RUN_ID,
                "result_path": PLANNING_RESULT_REL.as_posix(),
                "result_sha256": PLANNING_RESULT_SHA256,
                "provenance": EXPECTED_PLANNING_PROVENANCE,
            },
        },
        "derivation": {
            "kind": "deterministic-composite",
            "provider_output": False,
            "helper_path": (
                "scripts/clipmaker_lite_promopages_10060_femibion_veo_v7_composite.py"
            ),
            "patch": {
                "source": "raw_v7_provider_video",
                "scale": {"width": 800, "height": 450, "flags": "lanczos"},
            },
            "alpha_mask": {
                "canvas": {"width": 800, "height": 450, "color": "black"},
                "drawbox": {
                    "x": 55,
                    "y": 150,
                    "width": 300,
                    "height": 230,
                    "color": "0xD0D0D0",
                    "mode": "fill",
                },
                "gaussian_blur_sigma": 32,
            },
            "overlay": {"x": 1120, "y": 250, "format": "auto"},
            "color_range_conversion": {
                "filter": "scale=in_range=pc:out_range=tv",
                "pixel_format": "yuv420p",
                "setparams_range": "tv",
            },
            "filtergraph": FILTERGRAPH,
            "encoder": {
                "codec": "libx264",
                "preset": "slow",
                "crf": 18,
                "fps": 24,
                "duration_seconds": 4,
                "audio": False,
                "movflags": "+faststart",
            },
            "toolchain": {
                "ffmpeg": {
                    "path": str(FFMPEG_REAL_PATH),
                    "sha256": FFMPEG_SHA256,
                    "version": FFMPEG_VERSION,
                },
                "ffprobe": {
                    "path": str(FFPROBE_REAL_PATH),
                    "sha256": FFPROBE_SHA256,
                    "version": FFPROBE_VERSION,
                },
            },
            "ffmpeg_arguments": ffmpeg_arguments("<output>"),
        },
        "output": {
            "path": COMPOSITE_VIDEO_REL.as_posix(),
            "sha256": COMPOSITE_SHA256,
            "bytes": COMPOSITE_BYTES,
            "media": COMPOSITE_MEDIA,
            "mp4_atoms": {
                "top_level": [
                    {"type": "ftyp", "offset": 0, "bytes": 32},
                    {"type": "moov", "offset": 32, "bytes": 2441},
                    {"type": "free", "offset": 2473, "bytes": 8},
                    {"type": "mdat", "offset": 2481, "bytes": 549887},
                ],
                "faststart": True,
                "moov_offset": 32,
                "mdat_offset": 2481,
            },
            "decoded_frame_checksums": FRAME_CHECKSUMS,
        },
        "verification": {
            "byte_identical_reproduction": True,
            "technical_invariants_verified": True,
            "visual_samples_inspected": [0, 48, 95],
            "visual_result": (
                "base composition and person remain intact; only the softly masked "
                "right-side illumination patch changes"
            ),
        },
    }


def validate_inputs(root: Path = ROOT) -> tuple[Path, Path]:
    ffmpeg, ffprobe = validate_tools()
    base = _require_file(root, BASE_V4_REL, BASE_V4_SHA256, BASE_V4_BYTES)
    raw_video = _require_file(root, RAW_VIDEO_REL, RAW_VIDEO_SHA256, RAW_VIDEO_BYTES)
    _require_file(root, RAW_PROMPT_REL, RAW_PROMPT_SHA256)
    _require_file(root, RAW_RUN_REL, RAW_RUN_SHA256)
    _require_file(
        root,
        RAW_GENERATION_MANIFEST_REL,
        RAW_GENERATION_MANIFEST_SHA256,
    )
    _require_file(root, PLANNING_RESULT_REL, PLANNING_RESULT_SHA256)
    if probe_image(base, ffprobe, root=root) != {
        "width": 1920,
        "height": 1080,
        "pixel_format": "yuvj444p",
    }:
        raise CompositeError("Base V4 JPEG geometry/pixel format changed")
    if probe_video(raw_video, ffprobe, root=root) != RAW_MEDIA:
        raise CompositeError("Raw V7 provider media probe changed")

    run = read_json(root / RAW_RUN_REL)
    if (
        run.get("ticket") != TICKET
        or run.get("agent_id") != AGENT_ID
        or run.get("model_id") != MODEL_ID
        or run.get("sample_id") != SAMPLE_ID
        or run.get("status") != "succeeded"
        or run.get("provider_run_id") != V7_PROVIDER_RUN_ID
        or run.get("provider_job_id") != V7_PROVIDER_JOB_ID
        or run.get("request_sha256") != V7_REQUEST_SHA256
        or run.get("output_path") != RAW_VIDEO_REL.as_posix()
        or run.get("provider_may_be_active") is not False
        or run.get("media", {}).get("sha256") != RAW_VIDEO_SHA256
        or run.get("media", {}).get("bytes") != RAW_VIDEO_BYTES
        or run.get("contract_check", {}).get("conforms") is not True
        or run.get("error") is not None
    ):
        raise CompositeError("Raw V7 provider run receipt changed")
    prompt = read_json(root / RAW_PROMPT_REL)
    if (
        prompt.get("ticket") != TICKET
        or prompt.get("agent_id") != AGENT_ID
        or prompt.get("lite_run_id") != V7_PLANNING_RUN_ID
        or prompt.get("provider_run_id") != V7_PROVIDER_RUN_ID
        or prompt.get("model_id") != MODEL_ID
        or prompt.get("lite_result", {}).get("sha256") != PLANNING_RESULT_SHA256
        or prompt.get("lite_result", {}).get("provenance", {}).get("verified") is not True
        or prompt.get("lite_result", {}).get("provenance", {}).get("contract_version")
        != "2.0.8"
    ):
        raise CompositeError("Raw V7 prompt/planning receipt changed")
    generation = read_json(root / RAW_GENERATION_MANIFEST_REL)
    outputs = generation.get("outputs") if isinstance(generation, dict) else None
    if (
        generation.get("ticket") != TICKET
        or generation.get("batch_id") != V7_PROVIDER_BATCH_ID
        or generation.get("agent_id") != AGENT_ID
        or generation.get("expected_outputs") != 1
        or generation.get("summary") != {"succeeded": 1}
        or not isinstance(outputs, list)
        or len(outputs) != 1
        or outputs[0].get("provider_run_id") != V7_PROVIDER_RUN_ID
        or outputs[0].get("media", {}).get("sha256") != RAW_VIDEO_SHA256
    ):
        raise CompositeError("Raw V7 generation manifest changed")
    provenance = pipeline.planning_provenance_summary(root, V7_PLANNING_RUN_ID)
    if provenance != EXPECTED_PLANNING_PROVENANCE:
        raise CompositeError("Verified V7 Lite planning provenance changed")
    return ffmpeg, ffprobe


def validate_composite(root: Path = ROOT) -> dict[str, Any]:
    ffmpeg, ffprobe = validate_inputs(root)
    video = _require_file(
        root,
        COMPOSITE_VIDEO_REL,
        COMPOSITE_SHA256,
        COMPOSITE_BYTES,
    )
    if probe_video(video, ffprobe, root=root) != COMPOSITE_MEDIA:
        raise CompositeError("Composite technical media invariants changed")
    expected_atoms = receipt_document()["output"]["mp4_atoms"]
    if mp4_atoms(video) != expected_atoms:
        raise CompositeError("Composite MP4 faststart atom layout changed")
    if frame_checksums(video, ffmpeg, root=root) != FRAME_CHECKSUMS:
        raise CompositeError("Composite decoded frame checksums changed")
    receipt_path = root / RECEIPT_REL
    actual_receipt = read_json(receipt_path)
    expected_receipt = receipt_document()
    if actual_receipt != expected_receipt:
        raise CompositeError(f"Immutable composite receipt changed: {receipt_path}")
    return actual_receipt


def reproduce(output: Path, root: Path = ROOT) -> dict[str, Any]:
    ffmpeg, ffprobe = validate_inputs(root)
    if output.exists() or output.is_symlink():
        raise CompositeError(f"Refusing to overwrite reproduction output: {output}")
    parent = output.parent
    if not parent.is_dir() or parent.is_symlink():
        raise CompositeError(f"Reproduction parent must be an existing directory: {parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".femibion-v7-composite-",
        suffix=".mp4",
        dir=parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        _run(
            [str(ffmpeg), *ffmpeg_arguments(str(temporary))],
            cwd=root,
        )
        if (
            sha256_file(temporary) != COMPOSITE_SHA256
            or temporary.stat().st_size != COMPOSITE_BYTES
            or probe_video(temporary, ffprobe, root=root) != COMPOSITE_MEDIA
            or mp4_atoms(temporary) != receipt_document()["output"]["mp4_atoms"]
            or frame_checksums(temporary, ffmpeg, root=root) != FRAME_CHECKSUMS
        ):
            raise CompositeError("Reproduction is not byte-identical to the receipt")
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "path": str(output),
        "sha256": COMPOSITE_SHA256,
        "bytes": COMPOSITE_BYTES,
    }


def _safe_output(value: str) -> Path:
    parsed = PurePosixPath(value)
    if not value or any(part in {"", ".", ".."} for part in parsed.parts):
        raise argparse.ArgumentTypeError("output must not contain empty, dot, or parent parts")
    return Path(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    reproduce_parser = commands.add_parser("reproduce")
    reproduce_parser.add_argument("--output", required=True, type=_safe_output)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            receipt = validate_composite(ROOT)
            print(
                f"PASS: {receipt['output']['path']} sha256="
                f"{receipt['output']['sha256']} bytes={receipt['output']['bytes']}",
                flush=True,
            )
            return 0
        result = reproduce(args.output, ROOT)
        print(
            f"PASS: reproduced {result['path']} sha256={result['sha256']} "
            f"bytes={result['bytes']}",
            flush=True,
        )
        return 0
    except (CompositeError, pipeline.PipelineError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
