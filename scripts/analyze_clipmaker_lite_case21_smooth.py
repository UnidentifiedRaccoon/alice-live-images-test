#!/usr/bin/env python3
"""Deterministically measure case-21 non-loop motion smoothness proxies.

The analyzer reads existing MP4 files only.  It decodes every video frame at a
fixed normalized size, measures motion coverage in the seven case-21 regions,
and reports temporal proxies for uneven motion: motion-energy spikes, RGB
second differences, and abrupt transitions.  It does not modify generation
receipts and it deliberately does not make semantic or visual-quality
acceptance decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from statistics import median
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import analyze_clipmaker_lite_case21_loop as loop  # noqa: E402


SCHEMA_VERSION = "clipmaker-lite.case21-smooth-review.v1"
ANALYSIS_VERSION = 1

EXPERIMENT_ID = "promopages-9930-case21-wan27-smooth-20260728-v1"
EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / EXPERIMENT_ID
RETRY_EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / (
    "promopages-9930-case21-wan27-smooth-staggered-ease-retry1-20260728-v1"
)
DEFAULT_OUTPUT = EXPERIMENT_ROOT / "smooth-review.json"

DEFAULT_NORMALIZED_SIZE = 96
DEFAULT_COVERAGE_SAMPLE_COUNT = 17
MIN_NORMALIZED_SIZE = 64

ENERGY_SPIKE_MEDIAN_MULTIPLIER = 2.5
ENERGY_SPIKE_MAD_MULTIPLIER = 6.0
ENERGY_SPIKE_ABSOLUTE_FLOOR_RGB = 1.0

ABRUPT_MEDIAN_MULTIPLIER = 2.5
ABRUPT_MAD_MULTIPLIER = 6.0
ABRUPT_ABSOLUTE_FLOOR_RGB = 1.0

SQUARE_ASPECT_RATIO_TOLERANCE = loop.SQUARE_ASPECT_RATIO_TOLERANCE


class SmoothAnalysisError(RuntimeError):
    """A deterministic case-21 smooth-analysis error."""


@dataclass(frozen=True)
class VideoSpec:
    video_id: str
    path: Path


VARIANT_IDS = (
    "low-amplitude-continuous",
    "staggered-ease",
    "left-to-right-flow",
    "preservation-smooth-repair",
    "staggered-ease-retry1",
)

EXPECTED_MOTION_BY_REGION = {
    "ovaries": "one soft local pulse",
    "progesterone_formula": (
        "fixed formula while the existing purple aura slowly recedes and dims"
    ),
    "antique_balance": "small eased rocking motion",
    "bathroom_scale": "one smooth dial-needle sweep",
    "water_drops": "continuous downward rain motion",
    "irritability_lines": (
        "continuous irregular local motion without framewise jitter"
    ),
    "battery": "monotonic fill through yellow to green, staying green",
}


DEFAULT_VIDEO_PATHS = {
    video_id: EXPERIMENT_ROOT / "videos" / video_id / "wan-2.7" / "04.mp4"
    for video_id in VARIANT_IDS[:-1]
}
DEFAULT_VIDEO_PATHS["staggered-ease-retry1"] = (
    RETRY_EXPERIMENT_ROOT
    / "videos"
    / "staggered-ease-retry1"
    / "wan-2.7"
    / "04.mp4"
)

DEFAULT_VIDEO_SHA256 = {
    "low-amplitude-continuous": (
        "416279e81eddc4c291c697487203bc61929ff6c1c983dfa071955d52ed7db774"
    ),
    "staggered-ease": (
        "cde9e047a24fc74bd50f12b76e8576cae4ddf45328d0b352a3789a4e4b8fdf71"
    ),
    "left-to-right-flow": (
        "22fd794ce1bbdcf1b87ce7622f4a607b68203d0e7b09aee27fc0a266473c060a"
    ),
    "preservation-smooth-repair": (
        "16cca5d55e0f06e994feba5389791cc64cb0024d786c5b9c9c90fe0bc74e0fd3"
    ),
    "staggered-ease-retry1": (
        "a5a8bcf4f1ea388ef7a8117d98509662c5ed2c251fc97e7ff7e6365a88360572"
    ),
}

DEFAULT_VIDEOS = tuple(
    VideoSpec(video_id, DEFAULT_VIDEO_PATHS[video_id]) for video_id in VARIANT_IDS
)


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
        raise SmoothAnalysisError(
            f"Required executable is missing: {command[0]}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise SmoothAnalysisError(
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
        raise SmoothAnalysisError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def verify_default_video_digest(spec: VideoSpec, digest: str) -> None:
    expected_path = DEFAULT_VIDEO_PATHS.get(spec.video_id)
    expected_digest = DEFAULT_VIDEO_SHA256.get(spec.video_id)
    if spec.path != expected_path:
        return
    if expected_digest is None or digest != expected_digest:
        raise SmoothAnalysisError(
            f"Immutable default video digest changed for {spec.video_id}: {digest}"
        )


def extract_all_normalized_frames(
    path: Path,
    *,
    ffmpeg: str,
    size: int,
    expected_frame_count: int,
) -> list[bytes]:
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
            f"scale={size}:{size}:flags=lanczos,setsar=1",
            "-fps_mode",
            "passthrough",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        )
    )
    frame_bytes = size * size * 3
    if len(raw) % frame_bytes:
        raise SmoothAnalysisError(
            f"Decoded RGB byte count is not frame-aligned for {path}: {len(raw)}"
        )
    decoded_count = len(raw) // frame_bytes
    if decoded_count != expected_frame_count:
        raise SmoothAnalysisError(
            f"Expected {expected_frame_count} frames from {path}, got {decoded_count}"
        )
    return [
        raw[index * frame_bytes : (index + 1) * frame_bytes]
        for index in range(decoded_count)
    ]


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise SmoothAnalysisError("Cannot calculate a percentile of no values")
    if not 0.0 <= quantile <= 1.0:
        raise SmoothAnalysisError(f"Invalid quantile: {quantile}")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def median_absolute_deviation(values: Sequence[float]) -> float:
    if not values:
        raise SmoothAnalysisError("Cannot calculate MAD of no values")
    center = float(median(values))
    return float(median(abs(value - center) for value in values))


def robust_threshold(
    values: Sequence[float],
    *,
    median_multiplier: float,
    mad_multiplier: float,
    absolute_floor: float,
) -> float:
    center = float(median(values))
    mad = median_absolute_deviation(values)
    return max(
        absolute_floor,
        center * median_multiplier,
        center + mad * mad_multiplier,
    )


def second_difference_mae_rgb(
    previous: bytes,
    current: bytes,
    following: bytes,
    offsets: Sequence[int],
) -> float:
    if not offsets:
        raise SmoothAnalysisError("Cannot measure an empty pixel selection")
    absolute_sum = 0
    for offset in offsets:
        absolute_sum += abs(following[offset] - 2 * current[offset] + previous[offset])
        absolute_sum += abs(
            following[offset + 1] - 2 * current[offset + 1] + previous[offset + 1]
        )
        absolute_sum += abs(
            following[offset + 2] - 2 * current[offset + 2] + previous[offset + 2]
        )
    return absolute_sum / (len(offsets) * 3.0)


def _distribution(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean": round(sum(values) / len(values), 6),
        "median": round(float(median(values)), 6),
        "p90": round(percentile(values, 0.90), 6),
        "p95": round(percentile(values, 0.95), 6),
        "max": round(max(values), 6),
        "mad": round(median_absolute_deviation(values), 6),
    }


def temporal_smoothness(
    frames: Sequence[bytes],
    offsets: Sequence[int],
) -> dict[str, Any]:
    if len(frames) < 3:
        raise SmoothAnalysisError("At least three decoded frames are required")
    energy = [
        float(loop.pair_metrics(previous, current, offsets)["mean_absolute_rgb_difference"])
        for previous, current in zip(frames, frames[1:])
    ]
    acceleration = [
        second_difference_mae_rgb(previous, current, following, offsets)
        for previous, current, following in zip(frames, frames[1:], frames[2:])
    ]
    energy_threshold = robust_threshold(
        energy,
        median_multiplier=ENERGY_SPIKE_MEDIAN_MULTIPLIER,
        mad_multiplier=ENERGY_SPIKE_MAD_MULTIPLIER,
        absolute_floor=ENERGY_SPIKE_ABSOLUTE_FLOOR_RGB,
    )
    acceleration_threshold = robust_threshold(
        acceleration,
        median_multiplier=ABRUPT_MEDIAN_MULTIPLIER,
        mad_multiplier=ABRUPT_MAD_MULTIPLIER,
        absolute_floor=ABRUPT_ABSOLUTE_FLOOR_RGB,
    )
    spike_indices = [
        index + 1 for index, value in enumerate(energy) if value > energy_threshold
    ]
    abrupt_indices = [
        index + 2
        for index, value in enumerate(acceleration)
        if value > acceleration_threshold
    ]
    energy_distribution = _distribution(energy)
    acceleration_distribution = _distribution(acceleration)
    energy_distribution.update(
        {
            "spike_threshold": round(energy_threshold, 6),
            "spike_count": len(spike_indices),
            "spike_ratio": round(len(spike_indices) / len(energy), 8),
            "spike_frame_indices": spike_indices,
        }
    )
    acceleration_distribution.update(
        {
            "sample_count": len(acceleration),
            "abrupt_threshold": round(acceleration_threshold, 6),
            "abrupt_transition_count": len(abrupt_indices),
            "abrupt_transition_ratio": round(
                len(abrupt_indices) / len(acceleration), 8
            ),
            "abrupt_frame_indices": abrupt_indices,
            "normalized_p95_by_motion_p95": round(
                acceleration_distribution["p95"]
                / max(energy_distribution["p95"], 1e-9),
                6,
            ),
        }
    )
    return {
        "transition_count": len(energy),
        "motion_energy_mae_rgb": energy_distribution,
        "acceleration_proxy_mae_rgb": acceleration_distribution,
    }


def _requested_union_offsets(
    region_offsets: dict[str, tuple[int, ...]],
) -> tuple[int, ...]:
    return tuple(
        sorted({offset for offsets in region_offsets.values() for offset in offsets})
    )


def _coverage_region(
    region: loop.RegionSpec,
    offsets: Sequence[int],
    coverage_frames: Sequence[bytes],
    all_frames: Sequence[bytes],
    *,
    size: int,
) -> dict[str, Any]:
    measured = loop.region_activity(
        region,
        offsets,
        coverage_frames,
        size=size,
    )
    measured.pop("fidelity_status", None)
    measured["expected_motion"] = EXPECTED_MOTION_BY_REGION[region.region_id]
    measured["temporal_smoothness"] = temporal_smoothness(all_frames, offsets)
    return measured


def analyze_decoded_frames(
    metadata: dict[str, Any],
    frames: Sequence[bytes],
    *,
    size: int,
    coverage_sample_count: int,
) -> dict[str, Any]:
    frame_count = int(metadata["frame_count"])
    if len(frames) != frame_count:
        raise SmoothAnalysisError(
            f"Decoded {len(frames)} frames but metadata reports {frame_count}"
        )
    for frame in frames:
        try:
            loop.validate_frame(frame, size)
        except loop.LoopAnalysisError as exc:
            raise SmoothAnalysisError(str(exc)) from exc
    try:
        coverage_indices = loop.evenly_spaced_frame_indices(
            frame_count, coverage_sample_count
        )
        region_offsets, outside_offsets = loop.build_region_offsets(size)
    except loop.LoopAnalysisError as exc:
        raise SmoothAnalysisError(str(exc)) from exc
    coverage_frames = [frames[index] for index in coverage_indices]
    regions = [
        _coverage_region(
            region,
            region_offsets[region.region_id],
            coverage_frames,
            frames,
            size=size,
        )
        for region in loop.REGIONS
    ]
    missing = [region["region_id"] for region in regions if not region["detected_motion"]]
    union_offsets = _requested_union_offsets(region_offsets)
    collateral = loop.collateral_activity(
        frames[0],
        frames[1:],
        outside_offsets,
        size=size,
    )
    collateral.pop("fidelity_status", None)
    collateral["temporal_smoothness"] = temporal_smoothness(frames, outside_offsets)
    square = (
        abs(metadata["width"] / metadata["height"] - 1.0)
        <= SQUARE_ASPECT_RATIO_TOLERANCE
    )
    return {
        "analysis_status": "measured",
        "frame_analysis": {
            "decoded_frame_count": len(frames),
            "normalized_width": size,
            "normalized_height": size,
            "coverage_frame_indices": coverage_indices,
            "coverage_timestamps_seconds": [
                round(
                    float(Fraction(index, 1) / metadata["frame_rate"]),
                    6,
                )
                for index in coverage_indices
            ],
        },
        "motion_coverage": {
            "requested_region_count": len(regions),
            "regions_with_detected_motion": len(regions) - len(missing),
            "coverage_ratio": round((len(regions) - len(missing)) / len(regions), 8),
            "missing_motion_regions": missing,
        },
        "regions": regions,
        "requested_union_smoothness": temporal_smoothness(frames, union_offsets),
        "collateral_activity": collateral,
        "square_output": square,
    }


def probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    try:
        return loop.probe_video(path, ffprobe)
    except loop.LoopAnalysisError as exc:
        raise SmoothAnalysisError(str(exc)) from exc


def analyze_video(
    spec: VideoSpec,
    *,
    ffmpeg: str,
    ffprobe: str,
    size: int,
    coverage_sample_count: int,
    root: Path = ROOT,
) -> dict[str, Any]:
    path = root / spec.path
    if not path.is_file():
        raise SmoothAnalysisError(f"Expected video is missing: {spec.path}")
    digest = sha256_file(path)
    verify_default_video_digest(spec, digest)
    metadata = probe_video(path, ffprobe)
    frames = extract_all_normalized_frames(
        path,
        ffmpeg=ffmpeg,
        size=size,
        expected_frame_count=metadata["frame_count"],
    )
    analysis = analyze_decoded_frames(
        metadata,
        frames,
        size=size,
        coverage_sample_count=coverage_sample_count,
    )
    return {
        "video_id": spec.video_id,
        "path": spec.path.as_posix(),
        "sha256": digest,
        "media": {
            "width": metadata["width"],
            "height": metadata["height"],
            "frame_rate": str(metadata["frame_rate"]),
            "frame_count": metadata["frame_count"],
            "duration_seconds": round(metadata["duration_seconds"], 6),
            "container": metadata["container"],
            "codec": metadata["codec"],
            "pixel_format": metadata["pixel_format"],
            "has_audio": metadata["has_audio"],
            "bytes": metadata["bytes"],
        },
        **analysis,
    }


def _ranking_key(video: dict[str, Any]) -> tuple[Any, ...]:
    coverage = video["motion_coverage"]
    smoothness = video["requested_union_smoothness"]
    acceleration = smoothness["acceleration_proxy_mae_rgb"]
    energy = smoothness["motion_energy_mae_rgb"]
    collateral = video["collateral_activity"]
    return (
        -coverage["regions_with_detected_motion"],
        acceleration["abrupt_transition_ratio"],
        acceleration["normalized_p95_by_motion_p95"],
        energy["spike_ratio"],
        collateral["max_changed_pixel_ratio_from_first"],
        video["video_id"],
    )


def ranking_document(videos: Sequence[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for rank, video in enumerate(sorted(videos, key=_ranking_key), start=1):
        coverage = video["motion_coverage"]
        smoothness = video["requested_union_smoothness"]
        acceleration = smoothness["acceleration_proxy_mae_rgb"]
        energy = smoothness["motion_energy_mae_rgb"]
        entries.append(
            {
                "rank": rank,
                "video_id": video["video_id"],
                "regions_with_detected_motion": coverage[
                    "regions_with_detected_motion"
                ],
                "coverage_ratio": coverage["coverage_ratio"],
                "abrupt_transition_count": acceleration[
                    "abrupt_transition_count"
                ],
                "abrupt_transition_ratio": acceleration[
                    "abrupt_transition_ratio"
                ],
                "motion_energy_spike_count": energy["spike_count"],
                "motion_energy_spike_ratio": energy["spike_ratio"],
                "normalized_acceleration_p95": acceleration[
                    "normalized_p95_by_motion_p95"
                ],
                "collateral_max_changed_pixel_ratio_from_first": video[
                    "collateral_activity"
                ]["max_changed_pixel_ratio_from_first"],
            }
        )
    return {
        "method": "coverage-desc-then-abrupt-acceleration-spikes-collateral-asc",
        "entries": entries,
    }


def build_report(
    videos: Sequence[VideoSpec],
    *,
    ffmpeg: str,
    ffprobe: str,
    size: int,
    coverage_sample_count: int,
    root: Path = ROOT,
) -> dict[str, Any]:
    if not videos:
        raise SmoothAnalysisError("At least one video is required")
    analyzed = [
        analyze_video(
            video,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            size=size,
            coverage_sample_count=coverage_sample_count,
            root=root,
        )
        for video in videos
    ]
    ranking = ranking_document(analyzed)
    ranks = {entry["video_id"]: entry["rank"] for entry in ranking["entries"]}
    for video in analyzed:
        video["proxy_rank"] = ranks[video["video_id"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "case": {
            "article_number": "21",
            "article_slug": "21-maier-doctor-zolotoe-vremia",
            "image_id": "04",
            "model_id": "alibaba/wan-2.7",
            "experiment_id": EXPERIMENT_ID,
        },
        "analyzer": {
            "script": "scripts/analyze_clipmaker_lite_case21_smooth.py",
            "analysis_version": ANALYSIS_VERSION,
            "python": sys.version.split()[0],
            "ffmpeg": _tool_version(ffmpeg),
            "ffprobe": _tool_version(ffprobe),
            "third_party_python_dependencies": [],
        },
        "method": {
            "temporal_sampling": {
                "mode": "every-decoded-frame",
                "normalized_size": size,
                "normalization": "full-frame Lanczos scale to square RGB24",
            },
            "coverage_sampling": {
                "evenly_spaced_frame_count": coverage_sample_count,
                "active_pair_min_mae_rgb": loop.ROI_ACTIVE_PAIR_MIN_MAE_RGB,
                "active_pair_min_changed_ratio": (
                    loop.ROI_ACTIVE_PAIR_MIN_CHANGED_RATIO
                ),
                "min_active_transitions": loop.ROI_MIN_ACTIVE_TRANSITIONS,
            },
            "jerkiness_proxies": {
                "motion_energy": "mean absolute RGB difference between adjacent frames",
                "acceleration": (
                    "mean absolute RGB second difference across three adjacent frames"
                ),
                "energy_spike_threshold": {
                    "median_multiplier": ENERGY_SPIKE_MEDIAN_MULTIPLIER,
                    "mad_multiplier": ENERGY_SPIKE_MAD_MULTIPLIER,
                    "absolute_floor_rgb": ENERGY_SPIKE_ABSOLUTE_FLOOR_RGB,
                    "comparison": "strictly-greater-than",
                },
                "abrupt_transition_threshold": {
                    "median_multiplier": ABRUPT_MEDIAN_MULTIPLIER,
                    "mad_multiplier": ABRUPT_MAD_MULTIPLIER,
                    "absolute_floor_rgb": ABRUPT_ABSOLUTE_FLOOR_RGB,
                    "comparison": "strictly-greater-than",
                },
            },
            "collateral_thresholds": {
                "max_mae_rgb_from_first": loop.COLLATERAL_MAX_MAE_RGB,
                "max_changed_pixel_ratio_from_first": (
                    loop.COLLATERAL_MAX_CHANGED_RATIO
                ),
                "reporting_only": True,
            },
            "requested_regions": [
                {
                    "region_id": region.region_id,
                    "label": region.label,
                    "expected_motion": EXPECTED_MOTION_BY_REGION[region.region_id],
                    "normalized_roi": region.normalized_roi(),
                }
                for region in loop.REGIONS
            ],
        },
        "video_count": len(analyzed),
        "ranking": ranking,
        "videos": analyzed,
        "limitations": [
            (
                "All metrics are pixel-difference proxies; they do not establish "
                "semantic correctness, visual appeal, or acceptance."
            ),
            (
                "ROI coverage detects activity but cannot prove the direction of a "
                "needle, the physical meaning of a sway, or yellow-before-green order."
            ),
            (
                "Motion-energy and RGB second-difference spikes can be caused by "
                "compression, texture changes, intended staggered starts, or morphing."
            ),
            (
                "Normalization suppresses fine detail, while global ROI averages can "
                "hide a sharp local jerk; visual frame-by-frame review remains required."
            ),
            (
                "The proxy ranking is lexicographic and diagnostic only; it is not a "
                "semantic quality score or publication decision."
            ),
        ],
    }


def parse_video_spec(value: str) -> VideoSpec:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--video must use VIDEO_ID=workspace/path.mp4")
    video_id, raw_path = value.split("=", 1)
    if not loop.VIDEO_ID_PATTERN.fullmatch(video_id):
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
        help="repeatable VIDEO_ID=workspace/path.mp4; defaults to the four smooth variants",
    )
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument(
        "--coverage-samples", type=int, default=DEFAULT_COVERAGE_SAMPLE_COUNT
    )
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
    if args.size < MIN_NORMALIZED_SIZE:
        raise SmoothAnalysisError(
            f"normalized size must be at least {MIN_NORMALIZED_SIZE}"
        )
    output = args.output
    if output.is_absolute() or ".." in output.parts:
        raise SmoothAnalysisError("--output must be a workspace-relative path")
    videos = tuple(args.video) if args.video else DEFAULT_VIDEOS
    video_ids = [video.video_id for video in videos]
    if len(set(video_ids)) != len(video_ids):
        raise SmoothAnalysisError("--video ids must be unique")
    document = build_report(
        videos,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        size=args.size,
        coverage_sample_count=args.coverage_samples,
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
    except SmoothAnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
