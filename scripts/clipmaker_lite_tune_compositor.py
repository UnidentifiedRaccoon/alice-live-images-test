#!/usr/bin/env python3
"""Render the frozen Clipmaker Lite Tune deterministic-compositor matrix.

This pipeline is deliberately local and fail closed.  It never calls a video
provider, S3, or the network; it reads immutable source bitmaps, validates the
reviewed per-target machine plan, renders with ffmpeg, and writes a separate
aggregate manifest.  ``clipmaker-lite-test/tune-manifest.json`` is read-only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "promopages-10060-tune-compositor-20260811-v1"
TUNE_MANIFEST_REL = Path("clipmaker-lite-test/tune-manifest.json")
PLAN_REL = Path("clipmaker-lite-test/tune-compositor-plans.json")
RUN_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
AGGREGATE_REL = RUN_ROOT_REL / "manifest.json"
VIDEO_ROOT_REL = RUN_ROOT_REL / "videos"
FPS = 30
EXPECTED_TARGETS = 22
EXPECTED_BY_MODEL = {
    "alibaba/wan-2.2": 10,
    "alibaba/wan-2.7": 4,
    "google/veo-3.1-lite": 8,
}
MODEL_DURATIONS = {
    "alibaba/wan-2.2": 5,
    "alibaba/wan-2.7": 5,
    "google/veo-3.1-lite": 4,
}
ALLOWED_PRIMITIVES = {"camera_push", "pan", "pulse", "highlight", "glint"}
ALLOWED_COLORS = {
    "alice-blue": "#5B68FF",
    "chart-blue": "#1296D4",
    "soft-white": "#FFFFFF",
    "signal-green": "#32C98B",
}
CAMERA_KEYS = {
    "camera_push": {
        "primitive",
        "zoom_start",
        "zoom_end",
        "focal_point",
        "ease",
        "protected_content",
        "rationale",
    },
    "pan": {
        "primitive",
        "zoom",
        "start",
        "end",
        "ease",
        "protected_content",
        "rationale",
    },
}
OVERLAY_KEYS = {
    "primitive",
    "region",
    "region_confidence",
    "direction",
    "band_fraction",
    "opacity",
    "color",
    "timing",
    "protected_content",
    "rationale",
}


class TuneCompositorError(RuntimeError):
    """Raised when an immutable compositor contract is not satisfied."""


@dataclass(frozen=True)
class Target:
    case_id: str
    model_id: str
    duration_seconds: int
    source_path: Path
    source_sha256: str
    source_width: int
    source_height: int
    planning_run_id: str
    planning_result_path: str
    scene_plan_sha256: str
    output_path: Path
    plan: dict[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        return self.case_id, self.model_id

    @property
    def expected_frames(self) -> int:
        return self.duration_seconds * FPS


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TuneCompositorError(f"Cannot read JSON {path}: {exc}") from exc


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TuneCompositorError(f"{label} must be a non-empty POSIX path")
    candidate = Path(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise TuneCompositorError(f"Unsafe {label}: {value!r}")
    return candidate


def confined(
    path: Path,
    root: Path,
    *,
    label: str,
    must_exist: bool,
    kind: str = "file",
) -> Path:
    root_real = root.resolve(strict=True)
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise TuneCompositorError(f"Cannot resolve {label}: {path}") from exc
    if not resolved.is_relative_to(root_real):
        raise TuneCompositorError(f"{label} escapes workspace: {path}")
    if must_exist:
        valid_kind = resolved.is_file() if kind == "file" else resolved.is_dir()
        if not valid_kind or path.is_symlink():
            raise TuneCompositorError(
                f"{label} must be a regular non-symlink {kind}: {path}"
            )
    return resolved


def require_exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise TuneCompositorError(f"{label} keys mismatch; missing={missing}, extra={extra}")


def finite_number(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TuneCompositorError(f"{label} must be a number")
    result = float(value)
    if result != result or result in {float("inf"), float("-inf")}:
        raise TuneCompositorError(f"{label} must be finite")
    return result


def point(value: Any, *, label: str) -> tuple[float, float]:
    if not isinstance(value, dict):
        raise TuneCompositorError(f"{label} must be an object")
    require_exact_keys(value, {"x", "y"}, label=label)
    x = finite_number(value["x"], label=f"{label}.x")
    y = finite_number(value["y"], label=f"{label}.y")
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise TuneCompositorError(f"{label} must be normalized")
    return x, y


def region(value: Any, *, label: str) -> tuple[float, float, float, float]:
    if not isinstance(value, dict):
        raise TuneCompositorError(f"{label} must be an object")
    require_exact_keys(value, {"x", "y", "width", "height"}, label=label)
    x = finite_number(value["x"], label=f"{label}.x")
    y = finite_number(value["y"], label=f"{label}.y")
    width = finite_number(value["width"], label=f"{label}.width")
    height = finite_number(value["height"], label=f"{label}.height")
    if (
        x < 0
        or y < 0
        or width < 0.02
        or height < 0.02
        or width > 0.95
        or height > 0.95
        or x + width > 1.0
        or y + height > 1.0
    ):
        raise TuneCompositorError(f"{label} is not a safe normalized bbox")
    return x, y, width, height


def validate_plan(value: Any, *, duration: int, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TuneCompositorError(f"{label} must be an object")
    primitive = value.get("primitive")
    if primitive not in ALLOWED_PRIMITIVES:
        raise TuneCompositorError(f"Unsupported compositor primitive: {primitive!r}")
    if primitive in CAMERA_KEYS:
        require_exact_keys(value, CAMERA_KEYS[primitive], label=label)
        if value.get("ease") != "smoothstep":
            raise TuneCompositorError(f"{label}.ease must be smoothstep")
        if primitive == "camera_push":
            start = finite_number(value["zoom_start"], label=f"{label}.zoom_start")
            end = finite_number(value["zoom_end"], label=f"{label}.zoom_end")
            point(value["focal_point"], label=f"{label}.focal_point")
            if start != 1.0 or not (1.005 <= end <= 1.08):
                raise TuneCompositorError(f"{label} camera push exceeds the 0.5–8% bound")
        else:
            zoom = finite_number(value["zoom"], label=f"{label}.zoom")
            start_xy = point(value["start"], label=f"{label}.start")
            end_xy = point(value["end"], label=f"{label}.end")
            if not (1.01 <= zoom <= 1.08):
                raise TuneCompositorError(f"{label}.zoom exceeds the 1–8% bound")
            if max(abs(start_xy[0] - end_xy[0]), abs(start_xy[1] - end_xy[1])) > 0.25:
                raise TuneCompositorError(f"{label} pan travel is too large")
    else:
        require_exact_keys(value, OVERLAY_KEYS, label=label)
        region(value["region"], label=f"{label}.region")
        if value.get("region_confidence") != "visual-verified":
            raise TuneCompositorError(f"{label} overlay bbox was not visually verified")
        if value.get("direction") not in {
            "left-to-right",
            "top-to-bottom",
            "stationary",
        }:
            raise TuneCompositorError(f"{label}.direction is not allowlisted")
        band = finite_number(value["band_fraction"], label=f"{label}.band_fraction")
        opacity = finite_number(value["opacity"], label=f"{label}.opacity")
        if not (0.03 <= band <= 1.0) or not (0.01 <= opacity <= 0.14):
            raise TuneCompositorError(f"{label} overlay intensity is out of bounds")
        if value.get("color") not in ALLOWED_COLORS:
            raise TuneCompositorError(f"{label}.color is not allowlisted")
        timing = value.get("timing")
        if not isinstance(timing, dict):
            raise TuneCompositorError(f"{label}.timing must be an object")
        require_exact_keys(timing, {"start", "end", "fade_in", "fade_out"}, label=f"{label}.timing")
        start = finite_number(timing["start"], label=f"{label}.timing.start")
        end = finite_number(timing["end"], label=f"{label}.timing.end")
        fade_in = finite_number(timing["fade_in"], label=f"{label}.timing.fade_in")
        fade_out = finite_number(timing["fade_out"], label=f"{label}.timing.fade_out")
        if not (0 <= start < end <= duration) or fade_in <= 0 or fade_out <= 0:
            raise TuneCompositorError(f"{label}.timing is invalid")
        if fade_in + fade_out > end - start:
            raise TuneCompositorError(f"{label}.timing fades overlap")
    protected = value.get("protected_content")
    if not isinstance(protected, list) or not protected or not all(
        isinstance(item, str) and item for item in protected
    ):
        raise TuneCompositorError(f"{label}.protected_content must name preserved content")
    if not isinstance(value.get("rationale"), str) or not value["rationale"]:
        raise TuneCompositorError(f"{label}.rationale is required")
    return value


def compositor_projection(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    projection: list[dict[str, Any]] = []
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise TuneCompositorError("Tune manifest cases are invalid")
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("targets"), list):
            raise TuneCompositorError("Tune manifest case is invalid")
        for target in case["targets"]:
            tuned = target.get("tuned") if isinstance(target, dict) else None
            if not isinstance(tuned, dict) or tuned.get("execution_mode") != "deterministic-compositor":
                continue
            projection.append(
                {
                    "case_id": case.get("case_id"),
                    "model_id": target.get("model_id"),
                    "source": case.get("source"),
                    "planning_run_id": (case.get("planning") or {}).get("run_id"),
                    "planning_result_path": (case.get("planning") or {}).get("result_path"),
                    "planning_provenance": {
                        "verified": ((case.get("planning") or {}).get("provenance") or {}).get("verified"),
                        "agent_id": ((case.get("planning") or {}).get("provenance") or {}).get("agent_id"),
                        "result_path": ((case.get("planning") or {}).get("provenance") or {}).get("result_path"),
                        "source_image_sha256": ((case.get("planning") or {}).get("provenance") or {}).get("source_image_sha256"),
                        "models": ((case.get("planning") or {}).get("provenance") or {}).get("models"),
                    },
                    "scene_plan": tuned.get("scene_plan"),
                    "runtime": tuned.get("runtime"),
                    "positive_prompt": tuned.get("positive_prompt"),
                    "negative_prompt": tuned.get("negative_prompt"),
                }
            )
    return sorted(projection, key=lambda value: (value["case_id"], value["model_id"]))


def load_targets(*, root: Path = ROOT) -> tuple[dict[str, Any], tuple[Target, ...]]:
    root = root.resolve(strict=True)
    manifest_path = confined(root / TUNE_MANIFEST_REL, root, label="Tune manifest", must_exist=True)
    plan_path = confined(root / PLAN_REL, root, label="compositor plans", must_exist=True)
    manifest = read_json(manifest_path)
    plans = read_json(plan_path)
    if (
        not isinstance(manifest, dict)
        or manifest.get("manifest_role") != "clipmaker-lite-tune-review"
        or manifest.get("agent_id") != "clipmaker-lite"
        or manifest.get("contract_version") != "2.2.0"
    ):
        raise TuneCompositorError("Tune manifest identity mismatch")
    if not isinstance(plans, dict):
        raise TuneCompositorError("Compositor plan document must be an object")
    require_exact_keys(
        plans,
        {"schema_version", "manifest_role", "batch_id", "agent_id", "source_manifest", "render_contract", "targets"},
        label="compositor plan document",
    )
    if (
        plans.get("schema_version") != 1
        or plans.get("manifest_role") != "clipmaker-lite-tune-compositor-plans"
        or plans.get("batch_id") != BATCH_ID
        or plans.get("agent_id") != "clipmaker-lite"
    ):
        raise TuneCompositorError("Compositor plan identity mismatch")
    source_manifest = plans.get("source_manifest")
    if not isinstance(source_manifest, dict):
        raise TuneCompositorError("source_manifest binding is invalid")
    require_exact_keys(source_manifest, {"path", "batch_id", "selection_sha256"}, label="source_manifest")
    projection = compositor_projection(manifest)
    if (
        source_manifest.get("path") != TUNE_MANIFEST_REL.as_posix()
        or source_manifest.get("batch_id") != manifest.get("batch_id")
        or source_manifest.get("selection_sha256") != sha256_bytes(canonical_json(projection))
    ):
        raise TuneCompositorError("Compositor selection binding changed")
    contract = plans.get("render_contract")
    if not isinstance(contract, dict):
        raise TuneCompositorError("render_contract is invalid")
    require_exact_keys(
        contract,
        {"fps", "video_codec", "pixel_format", "audio", "network", "source_mutation", "allowlisted_primitives", "maximum_output"},
        label="render_contract",
    )
    if (
        contract.get("fps") != FPS
        or contract.get("video_codec") != "h264"
        or contract.get("pixel_format") != "yuv420p"
        or contract.get("audio") is not False
        or contract.get("network") is not False
        or contract.get("source_mutation") is not False
        or contract.get("allowlisted_primitives") != sorted(ALLOWED_PRIMITIVES)
        or contract.get("maximum_output") != {"width": 1920, "height": 1080, "upscale": False}
    ):
        raise TuneCompositorError("Render contract changed")
    plan_rows = plans.get("targets")
    if not isinstance(plan_rows, list) or len(plan_rows) != EXPECTED_TARGETS:
        raise TuneCompositorError(f"Expected exactly {EXPECTED_TARGETS} compositor plans")
    manifest_by_key = {(row["case_id"], row["model_id"]): row for row in projection}
    targets: list[Target] = []
    seen: set[tuple[str, str]] = set()
    target_keys = {
        "case_id",
        "model_id",
        "duration_seconds",
        "source",
        "planning",
        "scene_plan_sha256",
        "output_path",
        "plan",
    }
    for index, row in enumerate(plan_rows):
        if not isinstance(row, dict):
            raise TuneCompositorError(f"targets[{index}] must be an object")
        require_exact_keys(row, target_keys, label=f"targets[{index}]")
        key = (row.get("case_id"), row.get("model_id"))
        if key in seen or key not in manifest_by_key:
            raise TuneCompositorError(f"Unexpected or duplicate compositor target: {key}")
        seen.add(key)
        frozen = manifest_by_key[key]
        model_id = str(key[1])
        duration = row.get("duration_seconds")
        runtime = frozen.get("runtime")
        if (
            model_id not in MODEL_DURATIONS
            or duration != MODEL_DURATIONS[model_id]
            or not isinstance(runtime, dict)
            or runtime.get("duration_seconds") != duration
            or frozen.get("positive_prompt") is not None
            or frozen.get("negative_prompt") is not None
        ):
            raise TuneCompositorError(f"Model/runtime compositor contract changed: {key}")
        source = row.get("source")
        if not isinstance(source, dict):
            raise TuneCompositorError(f"Target source binding is invalid: {key}")
        require_exact_keys(source, {"path", "sha256", "width", "height"}, label=f"target {key} source")
        frozen_source = frozen.get("source")
        if not isinstance(frozen_source, dict) or any(
            source.get(name) != frozen_source.get(name)
            for name in ("path", "sha256", "width", "height")
        ):
            raise TuneCompositorError(f"Source binding changed: {key}")
        source_rel = safe_relative(source["path"], label=f"target {key} source.path")
        source_file = confined(root / source_rel, root, label=f"target {key} source", must_exist=True)
        if sha256_file(source_file) != source["sha256"]:
            raise TuneCompositorError(f"Source SHA-256 mismatch: {key}")
        planning = row.get("planning")
        if not isinstance(planning, dict):
            raise TuneCompositorError(f"Planning binding is invalid: {key}")
        require_exact_keys(planning, {"run_id", "result_path"}, label=f"target {key} planning")
        if (
            planning.get("run_id") != frozen.get("planning_run_id")
            or planning.get("result_path") != frozen.get("planning_result_path")
        ):
            raise TuneCompositorError(f"Planning binding changed: {key}")
        scene_plan = frozen.get("scene_plan")
        if not isinstance(scene_plan, str) or sha256_bytes(scene_plan.encode("utf-8")) != row.get("scene_plan_sha256"):
            raise TuneCompositorError(f"Scene-plan binding changed: {key}")
        provenance = frozen.get("planning_provenance")
        if (
            not isinstance(provenance, dict)
            or provenance.get("verified") is not True
            or provenance.get("agent_id") != "clipmaker-lite"
            or provenance.get("result_path") != planning.get("result_path")
            or provenance.get("source_image_sha256") != source.get("sha256")
            or not isinstance(provenance.get("models"), list)
            or model_id not in provenance["models"]
        ):
            raise TuneCompositorError(f"Clipmaker Lite provenance is not verified: {key}")
        output_rel = safe_relative(row["output_path"], label=f"target {key} output_path")
        expected_prefix = VIDEO_ROOT_REL.as_posix() + "/"
        if not output_rel.as_posix().startswith(expected_prefix) or output_rel.suffix != ".mp4":
            raise TuneCompositorError(f"Output path is outside the compositor batch: {key}")
        targets.append(
            Target(
                case_id=str(key[0]),
                model_id=model_id,
                duration_seconds=int(duration),
                source_path=source_rel,
                source_sha256=str(source["sha256"]),
                source_width=int(source["width"]),
                source_height=int(source["height"]),
                planning_run_id=str(planning["run_id"]),
                planning_result_path=str(planning["result_path"]),
                scene_plan_sha256=str(row["scene_plan_sha256"]),
                output_path=output_rel,
                plan=validate_plan(row["plan"], duration=int(duration), label=f"target {key} plan"),
            )
        )
    if seen != set(manifest_by_key):
        raise TuneCompositorError("Compositor target matrix is incomplete")
    if Counter(value.model_id for value in targets) != Counter(EXPECTED_BY_MODEL):
        raise TuneCompositorError("Compositor model counts changed")
    return plans, tuple(sorted(targets, key=lambda value: value.key))


def fit_dimensions(width: int, height: int) -> tuple[int, int, int, int]:
    scale = min(1.0, 1920 / width, 1080 / height)
    scaled_width = max(2, int(width * scale))
    scaled_height = max(2, int(height * scale))
    output_width = scaled_width + scaled_width % 2
    output_height = scaled_height + scaled_height % 2
    return scaled_width, scaled_height, output_width, output_height


def base_filter(target: Target) -> tuple[str, int, int]:
    scaled_w, scaled_h, out_w, out_h = fit_dimensions(target.source_width, target.source_height)
    filters: list[str] = []
    if (scaled_w, scaled_h) != (target.source_width, target.source_height):
        filters.append(f"scale={scaled_w}:{scaled_h}:flags=lanczos")
    if (out_w, out_h) != (scaled_w, scaled_h):
        filters.append(f"pad={out_w}:{out_h}:0:0:black")
        right = out_w - scaled_w
        bottom = out_h - scaled_h
        filters.append(f"fillborders=right={right}:bottom={bottom}:mode=smear")
    return ",".join(filters), out_w, out_h


def ease_expression(frame_count: int) -> str:
    denominator = max(1, frame_count - 1)
    progress = f"(on/{denominator})"
    return f"({progress}*{progress}*(3-2*{progress}))"


def camera_filter(target: Target) -> tuple[str, int, int]:
    prefix, width, height = base_filter(target)
    ease = ease_expression(target.expected_frames)
    plan = target.plan
    if plan["primitive"] == "camera_push":
        start = float(plan["zoom_start"])
        end = float(plan["zoom_end"])
        focal_x, focal_y = point(plan["focal_point"], label="focal_point")
        zoom = f"{start:.6f}+{end - start:.6f}*{ease}"
        x = f"(iw-iw/zoom)*{focal_x:.6f}"
        y = f"(ih-ih/zoom)*{focal_y:.6f}"
    else:
        zoom_value = float(plan["zoom"])
        start_x, start_y = point(plan["start"], label="start")
        end_x, end_y = point(plan["end"], label="end")
        zoom = f"{zoom_value:.6f}"
        x = f"(iw-iw/zoom)*({start_x:.6f}+{end_x - start_x:.6f}*{ease})"
        y = f"(ih-ih/zoom)*({start_y:.6f}+{end_y - start_y:.6f}*{ease})"
    chain = f"zoompan=z='{zoom}':x='{x}':y='{y}':d={target.expected_frames}:s={width}x{height}:fps={FPS}"
    if prefix:
        chain = prefix + "," + chain
    return chain + ",scale=iw:ih:in_range=auto:out_range=tv,format=yuv420p", width, height


def overlay_graph(target: Target) -> tuple[str, str, int, int, list[str]]:
    prefix, width, height = base_filter(target)
    plan = target.plan
    x, y, region_w, region_h = region(plan["region"], label="region")
    px = round(x * width)
    py = round(y * height)
    pw = max(2, round(region_w * width))
    ph = max(2, round(region_h * height))
    band = float(plan["band_fraction"])
    direction = plan["direction"]
    if direction == "left-to-right":
        overlay_w = max(2, round(pw * band))
        overlay_h = ph
    elif direction == "top-to-bottom":
        overlay_w = pw
        overlay_h = max(2, round(ph * band))
    else:
        overlay_w = pw
        overlay_h = ph
    timing = plan["timing"]
    start = float(timing["start"])
    end = float(timing["end"])
    fade_in = float(timing["fade_in"])
    fade_out = float(timing["fade_out"])
    color = ALLOWED_COLORS[plan["color"]]
    opacity = float(plan["opacity"])
    overlay_input = (
        f"color=c={color}@{opacity:.4f}:s={overlay_w}x{overlay_h}:r={FPS}:d={target.duration_seconds},"
        f"format=rgba,fade=t=in:st={start:.4f}:d={fade_in:.4f}:alpha=1,"
        f"fade=t=out:st={end - fade_out:.4f}:d={fade_out:.4f}:alpha=1"
    )
    active = max(0.001, end - start)
    smooth = f"((t-{start:.6f})/{active:.6f})*((t-{start:.6f})/{active:.6f})*(3-2*((t-{start:.6f})/{active:.6f}))"
    if direction == "left-to-right":
        overlay_x = f"{px}+({pw - overlay_w})*{smooth}"
        overlay_y = str(py)
    elif direction == "top-to-bottom":
        overlay_x = str(px)
        overlay_y = f"{py}+({ph - overlay_h})*{smooth}"
    else:
        overlay_x = str(px)
        overlay_y = str(py)
    base = prefix + "," if prefix else ""
    graph = (
        f"[0:v]{base}fps={FPS},tpad=stop_mode=clone:stop_duration={target.duration_seconds},"
        f"trim=duration={target.duration_seconds},setpts=PTS-STARTPTS[base];"
        f"[base][1:v]overlay=x='{overlay_x}':y='{overlay_y}':"
        f"enable='between(t,{start:.6f},{end:.6f})':shortest=1:format=auto,"
        "scale=iw:ih:in_range=auto:out_range=tv,format=yuv420p[v]"
    )
    return graph, overlay_input, width, height, ["-map", "[v]"]


def command_for_target(target: Target, source: Path, output: Path, ffmpeg: str) -> tuple[list[str], int, int]:
    common = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(source)]
    if target.plan["primitive"] in {"camera_push", "pan"}:
        filter_chain, width, height = camera_filter(target)
        command = common + ["-vf", filter_chain]
    else:
        graph, overlay_input, width, height, mapping = overlay_graph(target)
        command = common + ["-f", "lavfi", "-i", overlay_input, "-filter_complex", graph] + mapping
    command += [
        "-frames:v",
        str(target.expected_frames),
        "-fps_mode",
        "cfr",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-map_metadata",
        "-1",
        "-metadata",
        "creation_time=",
        "-threads",
        "1",
        str(output),
    ]
    return command, width, height


def run_command(command: list[str], *, label: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, text=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "")
        raise TuneCompositorError(f"{label} failed: {stderr or exc}") from exc


def probe_video(path: Path, *, ffprobe: str) -> dict[str, Any]:
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,nb_frames,duration:format=duration",
            "-of",
            "json",
            str(path),
        ],
        label=f"ffprobe {path}",
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise TuneCompositorError(f"ffprobe returned invalid JSON for {path}") from exc
    if not isinstance(value, dict):
        raise TuneCompositorError(f"ffprobe returned invalid data for {path}")
    return value


def probe_dimensions(path: Path, *, ffprobe: str) -> tuple[int, int]:
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(path),
        ],
        label=f"ffprobe dimensions {path}",
    )
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise TuneCompositorError(f"Cannot read source dimensions: {path}") from exc


def verify_media(
    target: Target,
    path: Path,
    *,
    expected_width: int,
    expected_height: int,
    ffprobe: str,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    probe = probe_video(path, ffprobe=ffprobe)
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise TuneCompositorError(f"No streams in {path}")
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(video_streams) != 1:
        raise TuneCompositorError(f"Expected one video stream in {path}")
    video = video_streams[0]
    try:
        duration = float(video.get("duration") or probe.get("format", {}).get("duration"))
        frames = int(video["nb_frames"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TuneCompositorError(f"Incomplete ffprobe result for {path}") from exc
    checks = {
        "codec_h264": video.get("codec_name") == "h264",
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "dimensions_exact": (video.get("width"), video.get("height")) == (expected_width, expected_height),
        "fps_exact": video.get("avg_frame_rate") == f"{FPS}/1",
        "frames_exact": frames == target.expected_frames,
        "duration_exact": abs(duration - target.duration_seconds) <= 0.001,
        "no_audio": not audio_streams,
        "source_sha256_bound": sha256_file(root / target.source_path) == target.source_sha256,
        "source_dimensions_bound": probe_dimensions(
            root / target.source_path, ffprobe=ffprobe
        )
        == (target.source_width, target.source_height),
    }
    if not all(checks.values()):
        raise TuneCompositorError(f"MP4 contract check failed for {target.key}: {checks}")
    media = {
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "duration_seconds": duration,
        "fps": FPS,
        "frames": frames,
        "video_codec": str(video["codec_name"]),
        "pixel_format": str(video["pix_fmt"]),
        "audio_streams": len(audio_streams),
    }
    return media, checks


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(encoded)
        temp = Path(stream.name)
    os.replace(temp, path)


def tool_path(name: str, explicit: str | None) -> str:
    value = explicit or shutil.which(name)
    if not value:
        raise TuneCompositorError(f"Required local executable not found: {name}")
    return value


def render_target(target: Target, *, root: Path, ffmpeg: str, ffprobe: str) -> dict[str, Any]:
    source = confined(root / target.source_path, root, label="source", must_exist=True)
    if sha256_file(source) != target.source_sha256:
        raise TuneCompositorError(f"Source SHA-256 mismatch: {target.key}")
    output = root / target.output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    confined(
        output.parent,
        root,
        label="output directory",
        must_exist=True,
        kind="directory",
    )
    with tempfile.NamedTemporaryFile(suffix=".mp4", dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    temporary.unlink()
    try:
        command, width, height = command_for_target(target, source, temporary, ffmpeg)
        run_command(command, label=f"ffmpeg render {target.key}")
        media, checks = verify_media(
            target,
            temporary,
            expected_width=width,
            expected_height=height,
            ffprobe=ffprobe,
            root=root,
        )
        if output.exists():
            if not output.is_file() or output.is_symlink():
                raise TuneCompositorError(f"Unsafe existing output: {output}")
            if sha256_file(output) != media["sha256"]:
                raise TuneCompositorError(f"Refusing to overwrite a different immutable MP4: {output}")
            temporary.unlink()
        else:
            os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "case_id": target.case_id,
        "model_id": target.model_id,
        "execution_mode": "deterministic-compositor",
        "status": "succeeded",
        "source": {
            "path": target.source_path.as_posix(),
            "sha256": target.source_sha256,
            "width": target.source_width,
            "height": target.source_height,
            "mutated": False,
        },
        "planning": {
            "run_id": target.planning_run_id,
            "result_path": target.planning_result_path,
            "scene_plan_sha256": target.scene_plan_sha256,
        },
        "plan": target.plan,
        "video_path": target.output_path.as_posix(),
        "media": media,
        "contract_check": checks,
    }


def render_batch(*, root: Path = ROOT, ffmpeg: str | None = None, ffprobe: str | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    plans, targets = load_targets(root=root)
    ffmpeg_path = tool_path("ffmpeg", ffmpeg)
    ffprobe_path = tool_path("ffprobe", ffprobe)
    outputs = [
        render_target(target, root=root, ffmpeg=ffmpeg_path, ffprobe=ffprobe_path)
        for target in targets
    ]
    plan_path = root / PLAN_REL
    aggregate = {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-compositor-generation",
        "batch_id": BATCH_ID,
        "agent_id": "clipmaker-lite",
        "producer": {
            "script_path": "scripts/clipmaker_lite_tune_compositor.py",
            "script_sha256": sha256_file(root / "scripts/clipmaker_lite_tune_compositor.py"),
        },
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "input_plan": {"path": PLAN_REL.as_posix(), "sha256": sha256_file(plan_path)},
        "render_contract": plans["render_contract"],
        "scope": {
            "targets": EXPECTED_TARGETS,
            "provider_calls": 0,
            "network": False,
            "s3_upload": False,
            "tune_manifest_mutation": False,
        },
        "summary": dict(sorted(Counter(output["status"] for output in outputs).items())),
        "model_summary": dict(sorted(Counter(output["model_id"] for output in outputs).items())),
        "bytes_total": sum(output["media"]["bytes"] for output in outputs),
        "outputs": outputs,
    }
    aggregate_path = root / AGGREGATE_REL
    atomic_write_json(aggregate_path, aggregate)
    return aggregate


def verify_batch(*, root: Path = ROOT, ffprobe: str | None = None) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _, targets = load_targets(root=root)
    aggregate_path = confined(root / AGGREGATE_REL, root, label="aggregate manifest", must_exist=True)
    aggregate = read_json(aggregate_path)
    if (
        not isinstance(aggregate, dict)
        or aggregate.get("manifest_role") != "clipmaker-lite-tune-compositor-generation"
        or aggregate.get("batch_id") != BATCH_ID
        or aggregate.get("input_plan", {}).get("sha256") != sha256_file(root / PLAN_REL)
        or aggregate.get("producer", {}).get("script_sha256")
        != sha256_file(root / "scripts/clipmaker_lite_tune_compositor.py")
    ):
        raise TuneCompositorError("Aggregate manifest identity/binding mismatch")
    outputs = aggregate.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != EXPECTED_TARGETS:
        raise TuneCompositorError("Aggregate output matrix is incomplete")
    by_key = {(row.get("case_id"), row.get("model_id")): row for row in outputs if isinstance(row, dict)}
    if len(by_key) != EXPECTED_TARGETS:
        raise TuneCompositorError("Aggregate has duplicate/invalid outputs")
    ffprobe_path = tool_path("ffprobe", ffprobe)
    verified: list[dict[str, Any]] = []
    for target in targets:
        row = by_key.get(target.key)
        if not isinstance(row, dict) or row.get("video_path") != target.output_path.as_posix():
            raise TuneCompositorError(f"Aggregate target binding mismatch: {target.key}")
        path = confined(root / target.output_path, root, label="rendered MP4", must_exist=True)
        expected_width = row.get("media", {}).get("width")
        expected_height = row.get("media", {}).get("height")
        media, checks = verify_media(
            target,
            path,
            expected_width=expected_width,
            expected_height=expected_height,
            ffprobe=ffprobe_path,
            root=root,
        )
        if media != row.get("media") or checks != row.get("contract_check"):
            raise TuneCompositorError(f"Aggregate media binding changed: {target.key}")
        verified.append(row)
    return {
        "verified": True,
        "batch_id": BATCH_ID,
        "targets": len(verified),
        "bytes_total": sum(row["media"]["bytes"] for row in verified),
        "aggregate_path": AGGREGATE_REL.as_posix(),
        "aggregate_sha256": sha256_file(aggregate_path),
    }


def concise_summary(aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_id": aggregate["batch_id"],
        "summary": aggregate["summary"],
        "model_summary": aggregate["model_summary"],
        "bytes_total": aggregate["bytes_total"],
        "outputs": [
            {
                "case_id": row["case_id"],
                "model_id": row["model_id"],
                "primitive": row["plan"]["primitive"],
                "video_path": row["video_path"],
                "bytes": row["media"]["bytes"],
                "dimensions": f"{row['media']['width']}x{row['media']['height']}",
                "duration_seconds": row["media"]["duration_seconds"],
                "frames": row["media"]["frames"],
                "audio_streams": row["media"]["audio_streams"],
            }
            for row in aggregate["outputs"]
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the frozen 22-target matrix and plans")
    render = subparsers.add_parser("render", help="render and verify all 22 local MP4s")
    render.add_argument("--ffmpeg")
    render.add_argument("--ffprobe")
    verify = subparsers.add_parser("verify", help="re-probe all rendered MP4s and bindings")
    verify.add_argument("--ffprobe")
    subparsers.add_parser("summary", help="print a concise aggregate summary")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate":
            _, targets = load_targets(root=args.root)
            result: Any = {
                "valid": True,
                "batch_id": BATCH_ID,
                "targets": len(targets),
                "models": dict(sorted(Counter(target.model_id for target in targets).items())),
                "primitives": dict(sorted(Counter(target.plan["primitive"] for target in targets).items())),
            }
        elif args.command == "render":
            result = concise_summary(
                render_batch(root=args.root, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
            )
        elif args.command == "verify":
            result = verify_batch(root=args.root, ffprobe=args.ffprobe)
        else:
            aggregate = read_json(args.root.resolve(strict=True) / AGGREGATE_REL)
            result = concise_summary(aggregate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except TuneCompositorError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
