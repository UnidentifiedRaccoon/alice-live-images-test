#!/usr/bin/env python3
"""Deterministically review case-21 loop seams and requested ROI activity.

The helper is intentionally independent from generation, showcase, and
finalization code.  It reads one or more existing MP4 files, decodes a fixed
set of RGB frames with ffmpeg, and emits a derived JSON report.  No network
access is used and no generation receipt is modified.

The measurements are diagnostics rather than semantic video understanding:
they can establish that a named region moved, that supposedly frozen pixels
also moved, and that the loop boundary is positionally and temporally close.
They cannot prove that a scale rocked in the correct direction or that the
battery passed through yellow before green; those details still need visual
review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "clipmaker-lite.case21-loop-review.v1"

DEFAULT_SAMPLE_COUNT = 17
DEFAULT_NORMALIZED_SIZE = 256

CHANGED_PIXEL_THRESHOLD_RGB = 12
ROI_ACTIVE_PAIR_MIN_MAE_RGB = 1.0
ROI_ACTIVE_PAIR_MIN_CHANGED_RATIO = 0.01
ROI_MIN_ACTIVE_TRANSITIONS = 2

SEAM_MAX_MAE_RGB = 4.0
SEAM_MAX_CHANGED_RATIO = 0.03
SEAM_MAX_SIGNED_VELOCITY_GAP_RGB = 8.0
SEAM_MAX_EDGE_MOTION_MAGNITUDE_DELTA_RGB = 4.0
SEAM_MAX_DIRECTION_CONFLICT_RATIO = 0.35
VELOCITY_DIRECTION_THRESHOLD_RGB = 3

COLLATERAL_MAX_MAE_RGB = 4.0
COLLATERAL_MAX_CHANGED_RATIO = 0.05
SQUARE_ASPECT_RATIO_TOLERANCE = 0.01


class LoopAnalysisError(RuntimeError):
    """A deterministic case-21 loop-analysis error."""


@dataclass(frozen=True)
class RegionSpec:
    region_id: str
    label: str
    expected_motion: str
    x0: float
    y0: float
    x1: float
    y1: float

    def normalized_roi(self) -> dict[str, float]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass(frozen=True)
class VideoSpec:
    video_id: str
    path: Path


# Coordinates are relative to the complete square case-21 source image.  They
# deliberately avoid most labels and connector lines so activity outside their
# union remains a useful collateral-redraw signal.
REGIONS = (
    RegionSpec(
        "ovaries",
        "Ovaries",
        "soft local pulse",
        0.025,
        0.255,
        0.325,
        0.515,
    ),
    RegionSpec(
        "progesterone_formula",
        "Progesterone formula and aura",
        "existing purple-aura swell and recede pulse",
        0.335,
        0.235,
        0.655,
        0.555,
    ),
    RegionSpec(
        "antique_balance",
        "Antique balance",
        "small rocking motion",
        0.660,
        0.245,
        0.945,
        0.555,
    ),
    RegionSpec(
        "bathroom_scale",
        "Bathroom scale",
        "dial needle rotation",
        0.035,
        0.605,
        0.305,
        0.895,
    ),
    RegionSpec(
        "water_drops",
        "Water drops",
        "repeating downward rain motion",
        0.315,
        0.610,
        0.515,
        0.900,
    ),
    RegionSpec(
        "irritability_lines",
        "Irritability lines",
        "irregular local jitter above the head",
        0.505,
        0.595,
        0.725,
        0.905,
    ),
    RegionSpec(
        "battery",
        "Battery",
        "fill through yellow and green, then return to source state",
        0.715,
        0.620,
        0.950,
        0.875,
    ),
)


VIDEO_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _run(command: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise LoopAnalysisError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise LoopAnalysisError(
            f"Command failed ({exc.returncode}): {' '.join(command)}\n{detail}"
        ) from exc
    return completed.stdout


def _tool_version(executable: str) -> str:
    output = _run((executable, "-version")).decode("utf-8", errors="replace")
    return output.splitlines()[0].strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LoopAnalysisError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    raw = _run(
        (
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            (
                "stream=codec_type,codec_name,width,height,pix_fmt,"
                "avg_frame_rate,nb_frames,nb_read_frames:"
                "format=duration,format_name,size"
            ),
            "-of",
            "json",
            str(path),
        )
    )
    try:
        document = json.loads(raw)
        streams = document["streams"]
        stream = next(item for item in streams if item.get("codec_type") == "video")
        width = int(stream["width"])
        height = int(stream["height"])
        frame_rate = Fraction(stream["avg_frame_rate"])
        raw_frame_count = stream.get("nb_read_frames") or stream.get("nb_frames")
        frame_count = int(raw_frame_count)
        duration = float(document["format"]["duration"])
        format_size = int(document["format"]["size"])
        codec = str(stream["codec_name"])
        pixel_format = str(stream["pix_fmt"])
        format_name = str(document["format"]["format_name"])
        has_audio = any(item.get("codec_type") == "audio" for item in streams)
    except (KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as exc:
        raise LoopAnalysisError(f"Incomplete ffprobe metadata for {path}") from exc
    if (
        width <= 0
        or height <= 0
        or frame_rate <= 0
        or frame_count < 4
        or duration <= 0
        or format_size <= 0
    ):
        raise LoopAnalysisError(f"Invalid video geometry or timing for {path}")
    return {
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "container": format_name,
        "codec": codec,
        "pixel_format": pixel_format,
        "has_audio": has_audio,
        "bytes": format_size,
    }


def evenly_spaced_frame_indices(frame_count: int, sample_count: int) -> list[int]:
    if sample_count < 5:
        raise LoopAnalysisError("sample_count must be at least 5")
    if frame_count < sample_count:
        raise LoopAnalysisError(
            f"Cannot take {sample_count} unique samples from {frame_count} frames"
        )
    last = frame_count - 1
    indices = [round(last * index / (sample_count - 1)) for index in range(sample_count)]
    if len(set(indices)) != sample_count:
        raise LoopAnalysisError("evenly spaced sampling produced duplicate frame indices")
    return indices


def analysis_frame_indices(frame_count: int, sample_count: int) -> list[int]:
    indices = set(evenly_spaced_frame_indices(frame_count, sample_count))
    indices.update((0, 1, frame_count - 2, frame_count - 1))
    return sorted(indices)


def extract_normalized_frames(
    path: Path,
    indices: Sequence[int],
    *,
    ffmpeg: str,
    size: int,
) -> dict[int, bytes]:
    select = "+".join(f"eq(n\\,{index})" for index in indices)
    filter_graph = f"select={select},scale={size}:{size}:flags=lanczos,setsar=1"
    raw = _run(
        (
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-an",
            "-sn",
            "-vf",
            filter_graph,
            "-fps_mode",
            "passthrough",
            "-frames:v",
            str(len(indices)),
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        )
    )
    frame_bytes = size * size * 3
    expected_bytes = len(indices) * frame_bytes
    if len(raw) != expected_bytes:
        raise LoopAnalysisError(
            f"Expected {expected_bytes} normalized bytes from {path}, got {len(raw)}"
        )
    frames = {}
    for position, frame_index in enumerate(indices):
        offset = position * frame_bytes
        frames[frame_index] = raw[offset : offset + frame_bytes]
    return frames


def pixel_roi(region: RegionSpec, size: int) -> dict[str, int]:
    roi = {
        "x0": round(region.x0 * size),
        "y0": round(region.y0 * size),
        "x1": round(region.x1 * size),
        "y1": round(region.y1 * size),
    }
    if not (0 <= roi["x0"] < roi["x1"] <= size):
        raise LoopAnalysisError(f"Invalid horizontal ROI for {region.region_id}")
    if not (0 <= roi["y0"] < roi["y1"] <= size):
        raise LoopAnalysisError(f"Invalid vertical ROI for {region.region_id}")
    return roi


def pixel_offsets_for_roi(roi: dict[str, int], size: int) -> tuple[int, ...]:
    return tuple(
        (y * size + x) * 3
        for y in range(roi["y0"], roi["y1"])
        for x in range(roi["x0"], roi["x1"])
    )


def build_region_offsets(
    size: int,
) -> tuple[dict[str, tuple[int, ...]], tuple[int, ...]]:
    region_offsets: dict[str, tuple[int, ...]] = {}
    covered = bytearray(size * size)
    for region in REGIONS:
        roi = pixel_roi(region, size)
        offsets = pixel_offsets_for_roi(roi, size)
        region_offsets[region.region_id] = offsets
        for offset in offsets:
            covered[offset // 3] = 1
    outside = tuple(index * 3 for index, value in enumerate(covered) if value == 0)
    if not outside:
        raise LoopAnalysisError("Requested regions unexpectedly cover the complete frame")
    return region_offsets, outside


def validate_frame(frame: bytes, size: int) -> None:
    expected = size * size * 3
    if len(frame) != expected:
        raise LoopAnalysisError(
            f"Normalized RGB frame has {len(frame)} bytes instead of {expected}"
        )


def pair_metrics(
    first: bytes,
    second: bytes,
    offsets: Iterable[int],
) -> dict[str, float | int]:
    absolute_sum = 0
    changed_pixels = 0
    pixel_count = 0
    for offset in offsets:
        red = abs(second[offset] - first[offset])
        green = abs(second[offset + 1] - first[offset + 1])
        blue = abs(second[offset + 2] - first[offset + 2])
        absolute_sum += red + green + blue
        changed_pixels += max(red, green, blue) >= CHANGED_PIXEL_THRESHOLD_RGB
        pixel_count += 1
    if pixel_count == 0:
        raise LoopAnalysisError("Cannot measure an empty pixel selection")
    return {
        "pixel_count": pixel_count,
        "mean_absolute_rgb_difference": round(
            absolute_sum / (pixel_count * 3.0), 6
        ),
        "changed_pixel_ratio": round(changed_pixels / pixel_count, 8),
    }


def motion_continuity_metrics(
    first: bytes,
    second: bytes,
    penultimate: bytes,
    last: bytes,
) -> dict[str, Any]:
    before_abs_sum = 0
    after_abs_sum = 0
    signed_gap_sum = 0
    active_direction_channels = 0
    conflicting_direction_channels = 0
    channel_count = len(first)
    for index in range(channel_count):
        before = last[index] - penultimate[index]
        after = second[index] - first[index]
        before_abs_sum += abs(before)
        after_abs_sum += abs(after)
        signed_gap_sum += abs(before - after)
        if (
            abs(before) >= VELOCITY_DIRECTION_THRESHOLD_RGB
            and abs(after) >= VELOCITY_DIRECTION_THRESHOLD_RGB
        ):
            active_direction_channels += 1
            conflicting_direction_channels += (before > 0) != (after > 0)
    before_mae = before_abs_sum / channel_count
    after_mae = after_abs_sum / channel_count
    signed_gap = signed_gap_sum / channel_count
    direction_conflict = (
        conflicting_direction_channels / active_direction_channels
        if active_direction_channels
        else 0.0
    )
    active_direction_ratio = active_direction_channels / channel_count
    # A handful of opposing channel deltas is common codec noise near a static
    # bookend.  Treat direction disagreement as material only when at least one
    # percent of all RGB channels carries measurable edge motion.
    direction_conflict_material = (
        active_direction_ratio >= 0.01
        and direction_conflict > SEAM_MAX_DIRECTION_CONFLICT_RATIO
    )
    magnitude_delta = abs(before_mae - after_mae)
    continuous = (
        signed_gap <= SEAM_MAX_SIGNED_VELOCITY_GAP_RGB
        and magnitude_delta <= SEAM_MAX_EDGE_MOTION_MAGNITUDE_DELTA_RGB
        and not direction_conflict_material
    )
    return {
        "before_seam_mean_absolute_rgb_motion": round(before_mae, 6),
        "after_seam_mean_absolute_rgb_motion": round(after_mae, 6),
        "edge_motion_magnitude_delta_rgb": round(magnitude_delta, 6),
        "signed_velocity_gap_mae_rgb": round(signed_gap, 6),
        "active_direction_channel_count": active_direction_channels,
        "active_direction_channel_ratio": round(active_direction_ratio, 8),
        "direction_conflict_ratio": round(direction_conflict, 8),
        "direction_conflict_material": direction_conflict_material,
        "motion_continuous": continuous,
    }


def seam_metrics(
    first: bytes,
    second: bytes,
    penultimate: bytes,
    last: bytes,
    *,
    size: int,
) -> dict[str, Any]:
    for frame in (first, second, penultimate, last):
        validate_frame(frame, size)
    all_pixels = range(0, size * size * 3, 3)
    closure = pair_metrics(first, last, all_pixels)
    position_closed = (
        closure["mean_absolute_rgb_difference"] <= SEAM_MAX_MAE_RGB
        and closure["changed_pixel_ratio"] <= SEAM_MAX_CHANGED_RATIO
    )
    continuity = motion_continuity_metrics(first, second, penultimate, last)
    failed_checks = []
    if not position_closed:
        failed_checks.append("first-last-position")
    if not continuity["motion_continuous"]:
        failed_checks.append("boundary-motion-continuity")
    return {
        "first_vs_last": closure,
        "position_closed": position_closed,
        "motion_discontinuity_proxy": continuity,
        "failed_checks": failed_checks,
        "seam_status": "pass" if not failed_checks else "fail",
    }


def region_activity(
    region: RegionSpec,
    offsets: Sequence[int],
    ordered_frames: Sequence[bytes],
    *,
    size: int,
) -> dict[str, Any]:
    for frame in ordered_frames:
        validate_frame(frame, size)
    transitions = [
        pair_metrics(previous, current, offsets)
        for previous, current in zip(ordered_frames, ordered_frames[1:])
    ]
    active = [
        item
        for item in transitions
        if item["mean_absolute_rgb_difference"] >= ROI_ACTIVE_PAIR_MIN_MAE_RGB
        and item["changed_pixel_ratio"] >= ROI_ACTIVE_PAIR_MIN_CHANGED_RATIO
    ]
    mean_mae = sum(item["mean_absolute_rgb_difference"] for item in transitions) / len(
        transitions
    )
    mean_changed = sum(item["changed_pixel_ratio"] for item in transitions) / len(
        transitions
    )
    detected = len(active) >= ROI_MIN_ACTIVE_TRANSITIONS
    return {
        "region_id": region.region_id,
        "label": region.label,
        "expected_motion": region.expected_motion,
        "normalized_roi": region.normalized_roi(),
        "pixel_roi": pixel_roi(region, size),
        "transition_count": len(transitions),
        "active_transition_count": len(active),
        "detected_motion": detected,
        "activity": {
            "mean_pair_mae_rgb": round(mean_mae, 6),
            "max_pair_mae_rgb": max(
                item["mean_absolute_rgb_difference"] for item in transitions
            ),
            "mean_changed_pixel_ratio": round(mean_changed, 8),
            "max_changed_pixel_ratio": max(
                item["changed_pixel_ratio"] for item in transitions
            ),
        },
        "fidelity_status": "pass" if detected else "fail",
    }


def collateral_activity(
    first: bytes,
    remaining_frames: Sequence[bytes],
    outside_offsets: Sequence[int],
    *,
    size: int,
) -> dict[str, Any]:
    validate_frame(first, size)
    measurements = []
    for frame in remaining_frames:
        validate_frame(frame, size)
        measurements.append(pair_metrics(first, frame, outside_offsets))
    maximum_mae = max(item["mean_absolute_rgb_difference"] for item in measurements)
    maximum_changed = max(item["changed_pixel_ratio"] for item in measurements)
    passed = (
        maximum_mae <= COLLATERAL_MAX_MAE_RGB
        and maximum_changed <= COLLATERAL_MAX_CHANGED_RATIO
    )
    return {
        "outside_requested_region_pixel_count": len(outside_offsets),
        "max_mae_rgb_from_first": maximum_mae,
        "max_changed_pixel_ratio_from_first": maximum_changed,
        "fidelity_status": "pass" if passed else "fail",
    }


def analyze_decoded_frames(
    metadata: dict[str, Any],
    frame_indices: Sequence[int],
    frames: dict[int, bytes],
    *,
    size: int,
) -> dict[str, Any]:
    frame_count = metadata["frame_count"]
    required = {0, 1, frame_count - 2, frame_count - 1}
    if not required.issubset(frames):
        raise LoopAnalysisError("Decoded frames omit a required seam-neighbor frame")
    if sorted(frame_indices) != list(frame_indices) or len(set(frame_indices)) != len(
        frame_indices
    ):
        raise LoopAnalysisError("frame_indices must be unique and sorted")
    if set(frame_indices) != set(frames):
        raise LoopAnalysisError("Decoded frame keys do not match frame_indices")

    ordered_frames = [frames[index] for index in frame_indices]
    region_offsets, outside_offsets = build_region_offsets(size)
    seam = seam_metrics(
        frames[0],
        frames[1],
        frames[frame_count - 2],
        frames[frame_count - 1],
        size=size,
    )
    regions = [
        region_activity(
            region,
            region_offsets[region.region_id],
            ordered_frames,
            size=size,
        )
        for region in REGIONS
    ]
    collateral = collateral_activity(
        ordered_frames[0],
        ordered_frames[1:],
        outside_offsets,
        size=size,
    )
    square = (
        abs(metadata["width"] / metadata["height"] - 1.0)
        <= SQUARE_ASPECT_RATIO_TOLERANCE
    )
    missing_motion = [
        region["region_id"] for region in regions if not region["detected_motion"]
    ]
    failed_checks = []
    if seam["seam_status"] != "pass":
        failed_checks.append("loop-seam")
    failed_checks.extend(f"missing-motion:{region_id}" for region_id in missing_motion)
    if collateral["fidelity_status"] != "pass":
        failed_checks.append("collateral-motion")
    if not square:
        failed_checks.append("non-square-output")
    return {
        "sampled_frame_indices": list(frame_indices),
        "seam": seam,
        "seam_status": seam["seam_status"],
        "regions": regions,
        "requested_region_count": len(regions),
        "regions_with_detected_motion": len(regions) - len(missing_motion),
        "missing_motion_regions": missing_motion,
        "collateral_activity": collateral,
        "square_output": square,
        "failed_checks": failed_checks,
        "fidelity_status": "pass" if not failed_checks else "fail",
    }


def analyze_video(
    spec: VideoSpec,
    *,
    ffmpeg: str,
    ffprobe: str,
    sample_count: int,
    size: int,
    root: Path = ROOT,
) -> dict[str, Any]:
    path = root / spec.path
    if not path.is_file():
        raise LoopAnalysisError(f"Expected video is missing: {spec.path}")
    metadata = probe_video(path, ffprobe)
    indices = analysis_frame_indices(metadata["frame_count"], sample_count)
    frames = extract_normalized_frames(path, indices, ffmpeg=ffmpeg, size=size)
    analysis = analyze_decoded_frames(metadata, indices, frames, size=size)
    frame_rate = metadata["frame_rate"]
    return {
        "video_id": spec.video_id,
        "path": spec.path.as_posix(),
        "sha256": sha256_file(path),
        "media": {
            "width": metadata["width"],
            "height": metadata["height"],
            "frame_rate": str(frame_rate),
            "frame_count": metadata["frame_count"],
            "duration_seconds": round(metadata["duration_seconds"], 6),
            "container": metadata["container"],
            "codec": metadata["codec"],
            "pixel_format": metadata["pixel_format"],
            "has_audio": metadata["has_audio"],
            "bytes": metadata["bytes"],
        },
        "sampling": {
            "normalized_width": size,
            "normalized_height": size,
            "normalization": "full-frame Lanczos scale to square RGB24",
            "frame_indices": indices,
            "timestamps_seconds": [
                round(float(Fraction(index, 1) / frame_rate), 6) for index in indices
            ],
        },
        **analysis,
    }


def build_report(
    videos: Sequence[VideoSpec],
    *,
    ffmpeg: str,
    ffprobe: str,
    sample_count: int,
    size: int,
    root: Path = ROOT,
) -> dict[str, Any]:
    if not videos:
        raise LoopAnalysisError("At least one --video is required")
    analyzed = [
        analyze_video(
            video,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            sample_count=sample_count,
            size=size,
            root=root,
        )
        for video in videos
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "case": {
            "article_number": "21",
            "article_slug": "21-maier-doctor-zolotoe-vremia",
            "image_id": "04",
            "model_id": "alibaba/wan-2.7",
        },
        "analyzer": {
            "script": "scripts/analyze_clipmaker_lite_case21_loop.py",
            "analysis_version": 1,
            "python": sys.version.split()[0],
            "ffmpeg": _tool_version(ffmpeg),
            "ffprobe": _tool_version(ffprobe),
            "third_party_python_dependencies": [],
        },
        "method": {
            "sample_count_requested": sample_count,
            "normalized_size": size,
            "exact_seam_neighbor_frames": ["first", "second", "penultimate", "last"],
            "changed_pixel_threshold_rgb": CHANGED_PIXEL_THRESHOLD_RGB,
            "roi_motion_thresholds": {
                "active_pair_min_mae_rgb": ROI_ACTIVE_PAIR_MIN_MAE_RGB,
                "active_pair_min_changed_ratio": ROI_ACTIVE_PAIR_MIN_CHANGED_RATIO,
                "min_active_transitions": ROI_MIN_ACTIVE_TRANSITIONS,
            },
            "seam_thresholds": {
                "max_first_last_mae_rgb": SEAM_MAX_MAE_RGB,
                "max_first_last_changed_ratio": SEAM_MAX_CHANGED_RATIO,
                "max_signed_velocity_gap_mae_rgb": SEAM_MAX_SIGNED_VELOCITY_GAP_RGB,
                "max_edge_motion_magnitude_delta_rgb": (
                    SEAM_MAX_EDGE_MOTION_MAGNITUDE_DELTA_RGB
                ),
                "max_direction_conflict_ratio": SEAM_MAX_DIRECTION_CONFLICT_RATIO,
            },
            "collateral_thresholds": {
                "max_mae_rgb_from_first": COLLATERAL_MAX_MAE_RGB,
                "max_changed_pixel_ratio_from_first": COLLATERAL_MAX_CHANGED_RATIO,
            },
            "requested_regions": [
                {
                    "region_id": region.region_id,
                    "label": region.label,
                    "expected_motion": region.expected_motion,
                    "normalized_roi": region.normalized_roi(),
                }
                for region in REGIONS
            ],
        },
        "video_count": len(analyzed),
        "seam_pass_count": sum(item["seam_status"] == "pass" for item in analyzed),
        "fidelity_pass_count": sum(
            item["fidelity_status"] == "pass" for item in analyzed
        ),
        "videos": analyzed,
        "limitations": [
            (
                "ROI activity detects pixel motion, not the semantic direction, "
                "rotation count, battery color order, or visual appeal."
            ),
            (
                "The signed boundary-velocity comparison is a discontinuity proxy; "
                "compression noise and motion blur can affect it."
            ),
            (
                "A matching first and last frame can still look non-looping when an "
                "object pauses unnaturally near the seam."
            ),
            (
                "Full visual review remains required before any result is accepted."
            ),
        ],
    }


def parse_video_spec(value: str) -> VideoSpec:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--video must use VIDEO_ID=workspace/path.mp4")
    video_id, raw_path = value.split("=", 1)
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise argparse.ArgumentTypeError(f"Invalid video id: {video_id!r}")
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".mp4":
        raise argparse.ArgumentTypeError(
            "Video path must be a workspace-relative .mp4 path without '..'"
        )
    return VideoSpec(video_id=video_id, path=path)


def write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
        stream.flush()
    try:
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--video",
        action="append",
        type=parse_video_spec,
        required=True,
        help="repeatable VIDEO_ID=workspace/path.mp4",
    )
    result.add_argument(
        "--output",
        type=Path,
        default=Path("clipmaker-lite-test/case-21-loop-review.json"),
    )
    result.add_argument("--samples", type=int, default=DEFAULT_SAMPLE_COUNT)
    result.add_argument("--size", type=int, default=DEFAULT_NORMALIZED_SIZE)
    result.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    result.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    result.add_argument(
        "--stdout",
        action="store_true",
        help="print the report instead of writing it",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.size < 64:
        raise LoopAnalysisError("normalized size must be at least 64")
    output = args.output
    if output.is_absolute() or ".." in output.parts:
        raise LoopAnalysisError("--output must be a workspace-relative path")
    video_ids = [video.video_id for video in args.video]
    if len(set(video_ids)) != len(video_ids):
        raise LoopAnalysisError("--video ids must be unique")
    document = build_report(
        args.video,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        sample_count=args.samples,
        size=args.size,
    )
    if args.stdout:
        print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        write_json_atomic(ROOT / output, document)
        print(output.as_posix())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoopAnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
