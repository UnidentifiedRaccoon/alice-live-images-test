#!/usr/bin/env python3
"""Measure case-21 aura motion and collateral redraw without third-party deps.

The analyzer reads the two baseline, four available stage-1, and one adaptive
stage-2 videos, samples nine source frames, center-crops every video to a square
(which is a material 1920x1080 -> 1080x1080 crop for Veo), and normalizes the
samples to 512x512 RGB.
It never edits source videos or generation receipts.  The only write is the
derived JSON report selected by ``--output``.

The purple signal is intentionally simple and auditable: inside a fixed central
ROI, a pixel's purple opponent chroma is ``max(0, min(R, B) - G)``.  A pixel is
part of the purple mask when that chroma is at least six RGB levels.  Outside
the ROI, the report compares every sample with that video's first sampled frame.
These measurements are diagnostics, not perceptual quality or semantic checks.
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
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "promopages-9930-case21-prompt-research-20260727-v1"
EXPERIMENT_ROOT = Path("clipmaker-lite-test/experiments") / EXPERIMENT_ID
DEFAULT_OUTPUT = EXPERIMENT_ROOT / "review/motion-metrics.json"

DEFAULT_SAMPLE_COUNT = 9
DEFAULT_NORMALIZED_SIZE = 512
PURPLE_MASK_THRESHOLD_RGB = 6
CHANGED_PIXEL_THRESHOLD_RGB = 12
AREA_INCREASE_TOLERANCE = 0.002
CHROMA_MASS_INCREASE_TOLERANCE = 0.001

# The initial source aura occupies roughly x=0.38..0.62, y=0.27..0.52.  A
# slightly larger box admits its soft boundary and treats growth beyond it as
# edit leakage into the supposedly frozen part of the infographic.
ROI_NORMALIZED = {
    "x0": 0.34,
    "y0": 0.245,
    "x1": 0.66,
    "y1": 0.55,
}


class AnalysisError(RuntimeError):
    """A deterministic case-21 motion-analysis error."""


@dataclass(frozen=True)
class VideoSpec:
    video_id: str
    cohort: str
    strategy: str
    model_id: str
    path: Path


VIDEOS = (
    VideoSpec(
        video_id="baseline-wan22",
        cohort="baseline",
        strategy="baseline",
        model_id="alibaba/wan-2.2",
        path=Path(
            "clipmaker-lite-test/runs/"
            "promopages-9930-case21-maier-runs-20260727-v1/videos/"
            "21-maier-doctor-zolotoe-vremia/wan-2.2/04.mp4"
        ),
    ),
    VideoSpec(
        video_id="baseline-wan27",
        cohort="baseline",
        strategy="baseline",
        model_id="alibaba/wan-2.7",
        path=Path(
            "clipmaker-lite-test/runs/"
            "promopages-9930-case21-maier-retry-wan27-veo-20260727-v1/videos/"
            "21-maier-doctor-zolotoe-vremia/wan-2.7/04.mp4"
        ),
    ),
    VideoSpec(
        video_id="erosion-negative-wan22",
        cohort="stage1",
        strategy="erosion-negative",
        model_id="alibaba/wan-2.2",
        path=EXPERIMENT_ROOT / "videos/erosion-negative/wan-2.2/04.mp4",
    ),
    VideoSpec(
        video_id="erosion-negative-wan27",
        cohort="stage1",
        strategy="erosion-negative",
        model_id="alibaba/wan-2.7",
        path=EXPERIMENT_ROOT / "videos/erosion-negative/wan-2.7/04.mp4",
    ),
    VideoSpec(
        video_id="monotonic-positive-wan27",
        cohort="stage1",
        strategy="monotonic-positive",
        model_id="alibaba/wan-2.7",
        path=EXPERIMENT_ROOT / "videos/monotonic-positive/wan-2.7/04.mp4",
    ),
    VideoSpec(
        video_id="veo-motion-only",
        cohort="stage1",
        strategy="veo-motion-only",
        model_id="google/veo-3.1-lite",
        path=EXPERIMENT_ROOT / "videos/veo-motion-only/veo-3.1-lite/04.mp4",
    ),
    VideoSpec(
        video_id="opacity-only-wan27",
        cohort="stage2",
        strategy="opacity-only",
        model_id="alibaba/wan-2.7",
        path=Path(
            "clipmaker-lite-test/experiments/"
            "promopages-9930-case21-opacity-only-stage2-20260727-v1/"
            "videos/wan-2.7/04.mp4"
        ),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AnalysisError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


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
        raise AnalysisError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise AnalysisError(
            f"Command failed ({exc.returncode}): {' '.join(command)}\n{detail}"
        ) from exc
    return completed.stdout


def _tool_version(executable: str) -> str:
    output = _run((executable, "-version")).decode("utf-8", errors="replace")
    return output.splitlines()[0].strip()


def probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    raw = _run(
        (
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,nb_frames",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        )
    )
    try:
        document = json.loads(raw)
        stream = document["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
        frame_rate = Fraction(stream["avg_frame_rate"])
        duration = float(document["format"]["duration"])
        frame_count = int(stream["nb_frames"])
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise AnalysisError(f"Incomplete ffprobe metadata for {path}") from exc
    if width <= 0 or height <= 0 or frame_rate <= 0 or frame_count <= 0 or duration <= 0:
        raise AnalysisError(f"Invalid video geometry or timing for {path}")
    return {
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "frame_count": frame_count,
        "duration_seconds": duration,
    }


def evenly_spaced_frame_indices(frame_count: int, sample_count: int) -> list[int]:
    if sample_count < 2:
        raise AnalysisError("sample_count must be at least 2")
    if frame_count < sample_count:
        raise AnalysisError(
            f"Cannot take {sample_count} unique samples from {frame_count} frames"
        )
    last = frame_count - 1
    indices = [round(last * index / (sample_count - 1)) for index in range(sample_count)]
    if len(set(indices)) != sample_count:
        raise AnalysisError("evenly spaced sampling produced duplicate frame indices")
    return indices


def extract_normalized_frames(
    path: Path,
    metadata: dict[str, Any],
    indices: Sequence[int],
    *,
    ffmpeg: str,
    size: int,
) -> tuple[list[bytes], dict[str, int]]:
    width = metadata["width"]
    height = metadata["height"]
    side = min(width, height)
    crop_x = (width - side) // 2
    crop_y = (height - side) // 2
    select = "+".join(f"eq(n\\,{index})" for index in indices)
    filter_graph = (
        f"select={select},crop={side}:{side}:{crop_x}:{crop_y},"
        f"scale={size}:{size}:flags=lanczos"
    )
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
        raise AnalysisError(
            f"Expected {expected_bytes} normalized bytes from {path}, got {len(raw)}"
        )
    frames = [
        raw[offset : offset + frame_bytes]
        for offset in range(0, len(raw), frame_bytes)
    ]
    return frames, {
        "source_width": width,
        "source_height": height,
        "crop_x": crop_x,
        "crop_y": crop_y,
        "crop_width": side,
        "crop_height": side,
        "output_width": size,
        "output_height": size,
    }


def pixel_roi(size: int) -> dict[str, int]:
    roi = {
        "x0": round(ROI_NORMALIZED["x0"] * size),
        "y0": round(ROI_NORMALIZED["y0"] * size),
        "x1": round(ROI_NORMALIZED["x1"] * size),
        "y1": round(ROI_NORMALIZED["y1"] * size),
    }
    if not (0 <= roi["x0"] < roi["x1"] <= size):
        raise AnalysisError("Invalid horizontal ROI")
    if not (0 <= roi["y0"] < roi["y1"] <= size):
        raise AnalysisError("Invalid vertical ROI")
    return roi


def measure_frame(
    frame: bytes,
    first_frame: bytes,
    *,
    size: int,
    roi: dict[str, int],
) -> dict[str, float | int | str]:
    expected = size * size * 3
    if len(frame) != expected or len(first_frame) != expected:
        raise AnalysisError("Normalized RGB frame has an unexpected byte length")

    purple_pixels = 0
    purple_chroma_sum = 0
    outside_pixels = 0
    outside_abs_sum = 0
    outside_changed_pixels = 0
    x0, x1 = roi["x0"], roi["x1"]
    y0, y1 = roi["y0"], roi["y1"]

    for y in range(size):
        row = y * size * 3
        inside_y = y0 <= y < y1
        for x in range(size):
            offset = row + x * 3
            red = frame[offset]
            green = frame[offset + 1]
            blue = frame[offset + 2]
            if inside_y and x0 <= x < x1:
                purple_chroma = max(0, min(red, blue) - green)
                if purple_chroma >= PURPLE_MASK_THRESHOLD_RGB:
                    purple_pixels += 1
                    purple_chroma_sum += purple_chroma
                continue

            red_diff = abs(red - first_frame[offset])
            green_diff = abs(green - first_frame[offset + 1])
            blue_diff = abs(blue - first_frame[offset + 2])
            outside_abs_sum += red_diff + green_diff + blue_diff
            outside_pixels += 1
            if max(red_diff, green_diff, blue_diff) >= CHANGED_PIXEL_THRESHOLD_RGB:
                outside_changed_pixels += 1

    roi_pixels = (x1 - x0) * (y1 - y0)
    purple_area = purple_pixels / roi_pixels
    chroma_mean = purple_chroma_sum / purple_pixels if purple_pixels else 0.0
    chroma_mass = purple_chroma_sum / (roi_pixels * 255.0)
    outside_mean_abs = outside_abs_sum / (outside_pixels * 3.0)
    outside_changed_fraction = outside_changed_pixels / outside_pixels
    return {
        "frame_sha256": hashlib.sha256(frame).hexdigest(),
        "purple_mask_pixels": purple_pixels,
        "purple_mask_area_fraction_of_roi": round(purple_area, 8),
        "purple_mask_mean_opponent_chroma_rgb": round(chroma_mean, 6),
        "purple_chroma_mass_fraction": round(chroma_mass, 8),
        "outside_roi_mean_absolute_rgb_diff_from_first": round(outside_mean_abs, 6),
        "outside_roi_changed_pixel_fraction_from_first": round(
            outside_changed_fraction, 8
        ),
    }


def monotonic_violations(
    samples: Sequence[dict[str, Any]],
    key: str,
    tolerance: float,
) -> dict[str, Any]:
    strict_steps: list[dict[str, Any]] = []
    material_steps: list[dict[str, Any]] = []
    for index in range(1, len(samples)):
        previous = float(samples[index - 1][key])
        current = float(samples[index][key])
        delta = current - previous
        if delta > 0:
            step = {
                "from_sample": index - 1,
                "to_sample": index,
                "delta": round(delta, 8),
            }
            strict_steps.append(step)
            if delta > tolerance:
                material_steps.append(step)
    values = [float(sample[key]) for sample in samples]
    return {
        "metric": key,
        "expected_direction": "non-increasing",
        "material_increase_tolerance": tolerance,
        "strict_increase_count": len(strict_steps),
        "strict_increase_steps": strict_steps,
        "material_violation_count": len(material_steps),
        "material_violation_steps": material_steps,
        "initial": values[0],
        "final": values[-1],
        "minimum": min(values),
        "minimum_sample": values.index(min(values)),
        "maximum": max(values),
        "maximum_sample": values.index(max(values)),
        "net_change": round(values[-1] - values[0], 8),
    }


def summarize(samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    area = monotonic_violations(
        samples,
        "purple_mask_area_fraction_of_roi",
        AREA_INCREASE_TOLERANCE,
    )
    chroma_mass = monotonic_violations(
        samples,
        "purple_chroma_mass_fraction",
        CHROMA_MASS_INCREASE_TOLERANCE,
    )
    outside_diff = [
        float(sample["outside_roi_mean_absolute_rgb_diff_from_first"])
        for sample in samples
    ]
    outside_changed = [
        float(sample["outside_roi_changed_pixel_fraction_from_first"])
        for sample in samples
    ]
    material_violations = (
        area["material_violation_count"] + chroma_mass["material_violation_count"]
    )
    ends_no_larger = (
        area["final"] <= area["initial"] + AREA_INCREASE_TOLERANCE
        and chroma_mass["final"]
        <= chroma_mass["initial"] + CHROMA_MASS_INCREASE_TOLERANCE
    )
    return {
        "purple_area_trajectory": area,
        "purple_chroma_mass_trajectory": chroma_mass,
        "monotonic_decrease_material_violation_count": material_violations,
        "monotonic_decrease_metric_pass": material_violations == 0 and ends_no_larger,
        "outside_roi": {
            "max_mean_absolute_rgb_diff_from_first": max(outside_diff),
            "max_mean_absolute_rgb_diff_sample": outside_diff.index(max(outside_diff)),
            "final_mean_absolute_rgb_diff_from_first": outside_diff[-1],
            "max_changed_pixel_fraction_from_first": max(outside_changed),
            "max_changed_pixel_fraction_sample": outside_changed.index(
                max(outside_changed)
            ),
            "final_changed_pixel_fraction_from_first": outside_changed[-1],
        },
    }


def analyze_video(
    spec: VideoSpec,
    *,
    ffmpeg: str,
    ffprobe: str,
    sample_count: int,
    size: int,
) -> dict[str, Any]:
    path = ROOT / spec.path
    if not path.is_file():
        raise AnalysisError(f"Expected case-21 video is missing: {spec.path}")
    metadata = probe_video(path, ffprobe)
    indices = evenly_spaced_frame_indices(metadata["frame_count"], sample_count)
    frames, normalization = extract_normalized_frames(
        path,
        metadata,
        indices,
        ffmpeg=ffmpeg,
        size=size,
    )
    roi = pixel_roi(size)
    measured = [
        measure_frame(frame, frames[0], size=size, roi=roi) for frame in frames
    ]
    frame_rate = metadata["frame_rate"]
    samples: list[dict[str, Any]] = []
    for sample_index, (frame_index, metrics) in enumerate(zip(indices, measured)):
        samples.append(
            {
                "sample_index": sample_index,
                "source_frame_index": frame_index,
                "timestamp_seconds": round(float(Fraction(frame_index, 1) / frame_rate), 6),
                **metrics,
            }
        )
    return {
        "video_id": spec.video_id,
        "cohort": spec.cohort,
        "strategy": spec.strategy,
        "model_id": spec.model_id,
        "path": spec.path.as_posix(),
        "sha256": sha256_file(path),
        "source_video": {
            "width": metadata["width"],
            "height": metadata["height"],
            "frame_rate": str(frame_rate),
            "frame_count": metadata["frame_count"],
            "duration_seconds": round(metadata["duration_seconds"], 6),
        },
        "normalization": normalization,
        "samples": samples,
        "summary": summarize(samples),
    }


def build_report(
    *,
    ffmpeg: str,
    ffprobe: str,
    sample_count: int,
    size: int,
) -> dict[str, Any]:
    videos = [
        analyze_video(
            spec,
            ffmpeg=ffmpeg,
            ffprobe=ffprobe,
            sample_count=sample_count,
            size=size,
        )
        for spec in VIDEOS
    ]
    ranking = sorted(
        videos,
        key=lambda video: (
            video["summary"]["monotonic_decrease_material_violation_count"],
            video["summary"]["outside_roi"][
                "max_changed_pixel_fraction_from_first"
            ],
        ),
    )
    return {
        "schema_version": "clipmaker-lite.case21-motion-analysis.v1",
        "experiment_id": EXPERIMENT_ID,
        "analyzer": {
            "script": Path(__file__).relative_to(ROOT).as_posix(),
            "analysis_version": 1,
            "python": sys.version.split()[0],
            "ffmpeg": _tool_version(ffmpeg),
            "ffprobe": _tool_version(ffprobe),
            "third_party_python_dependencies": [],
        },
        "method": {
            "sample_count_per_video": sample_count,
            "sample_selection": (
                "frame indices evenly spaced from the first through the last "
                "decoded source frame, inclusive"
            ),
            "normalization": (
                "center-crop min(width,height) square, then Lanczos scale to "
                f"{size}x{size} RGB24"
            ),
            "veo_crop_note": (
                "The Veo 1920x1080 frame is center-cropped to 1080x1080 before "
                "measurement; square Wan frames have a no-op centered crop."
            ),
            "central_roi_normalized": ROI_NORMALIZED,
            "central_roi_pixels_after_normalization": pixel_roi(size),
            "purple_opponent_chroma": "max(0, min(R, B) - G)",
            "purple_mask_threshold_rgb": PURPLE_MASK_THRESHOLD_RGB,
            "purple_chroma_mass": (
                "sum(masked purple opponent chroma) / (ROI pixels * 255)"
            ),
            "outside_roi_reference": "first normalized frame of the same video",
            "outside_changed_pixel_rule": (
                "max absolute RGB-channel difference from first frame >= "
                f"{CHANGED_PIXEL_THRESHOLD_RGB}"
            ),
            "material_increase_tolerances": {
                "purple_mask_area_fraction_of_roi": AREA_INCREASE_TOLERANCE,
                "purple_chroma_mass_fraction": CHROMA_MASS_INCREASE_TOLERANCE,
            },
        },
        "coverage": {
            "video_count": len(videos),
            "baseline_count": sum(video["cohort"] == "baseline" for video in videos),
            "stage1_count": sum(video["cohort"] == "stage1" for video in videos),
            "stage2_count": sum(video["cohort"] == "stage2" for video in videos),
            "known_missing_stage1_video": {
                "strategy": "monotonic-positive",
                "model_id": "alibaba/wan-2.2",
                "reason": "no MP4 was produced; excluded from video metrics",
            },
        },
        "videos": videos,
        "diagnostic_ranking": {
            "basis": (
                "fewest material purple-trajectory violations, then lowest "
                "maximum outside-ROI changed-pixel fraction"
            ),
            "video_ids_best_first": [video["video_id"] for video in ranking],
        },
        "limitations": [
            (
                "The color heuristic measures the purple aura together with any "
                "purple molecule fill inside the ROI; it is not semantic segmentation."
            ),
            (
                "Nine samples can miss reversals between sampled frames; a pass is "
                "only a coarse trajectory diagnostic."
            ),
            (
                "Outside-ROI differences are relative to each generated video's "
                "first frame, so first-frame drift from the source image is invisible."
            ),
            (
                "Camera or layout motion can move the intended aura outside the fixed "
                "ROI and will then count as collateral redraw, by design."
            ),
            (
                "The Veo center crop excludes its lateral 420-pixel bands on each "
                "side; metrics compare the shared square composition only."
            ),
            (
                "Thresholds and tolerances suppress compression noise but are task-"
                "specific diagnostics, not calibrated perceptual acceptance limits."
            ),
        ],
    }


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
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"workspace-relative JSON path (default: {DEFAULT_OUTPUT})",
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
        raise AnalysisError("normalized size must be at least 64")
    output = args.output
    if output.is_absolute() or ".." in output.parts:
        raise AnalysisError("--output must be a workspace-relative path")
    document = build_report(
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
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
