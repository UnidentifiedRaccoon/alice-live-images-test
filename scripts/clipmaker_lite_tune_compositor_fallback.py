#!/usr/bin/env python3
"""Render two local camera-only fallbacks for terminal Tune provider failures.

The original targets remain Clipmaker Lite ``execution_mode: i2v``.  This
separate batch is permitted only when an exact provider run is terminal
``provider-failed`` and has no output.  It makes no provider, network, or S3
calls and never mutates the Tune or canonical compositor manifests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_tune_compositor as renderer  # noqa: E402


BATCH_ID = "promopages-10060-tune-compositor-fallback-20260811-v1"
METHOD = "deterministic-compositor-fallback"
PLAN_REL = Path("clipmaker-lite-test/tune-compositor-fallback-plans.json")
RUN_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
VIDEO_ROOT_REL = RUN_ROOT_REL / "videos"
AGGREGATE_REL = RUN_ROOT_REL / "manifest.json"
PROVIDER_GENERATION_REL = (
    Path("clipmaker-lite-test/runs")
    / "promopages-10060-tune-videos-20260811-v1"
    / "generation-manifest.json"
)
PROVIDER_BATCH_ID = "promopages-10060-tune-videos-20260811-v1"
EXPECTED_KEYS = {
    ("07#06", "google/veo-3.1-lite"),
    ("10#07", "google/veo-3.1-lite"),
}


class TuneFallbackError(renderer.TuneCompositorError):
    """Raised when a fallback lacks a terminal provider-failure binding."""


@dataclass(frozen=True)
class FallbackTarget:
    render: renderer.Target
    provider_failure: dict[str, Any]
    canonical_video_path: Path

    @property
    def key(self) -> tuple[str, str]:
        return self.render.key


def fallback_projection(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise TuneFallbackError("Tune manifest cases are invalid")
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("targets"), list):
            raise TuneFallbackError("Tune manifest case is invalid")
        for target in case["targets"]:
            key = (case.get("case_id"), target.get("model_id"))
            if key not in EXPECTED_KEYS:
                continue
            planning = case.get("planning") or {}
            provenance = planning.get("provenance") or {}
            tuned = target.get("tuned") or {}
            rows.append(
                {
                    "case_id": key[0],
                    "model_id": key[1],
                    "source": case.get("source"),
                    "planning_run_id": planning.get("run_id"),
                    "planning_result_path": planning.get("result_path"),
                    "planning_provenance": {
                        "verified": provenance.get("verified"),
                        "agent_id": provenance.get("agent_id"),
                        "result_path": provenance.get("result_path"),
                        "source_image_sha256": provenance.get("source_image_sha256"),
                        "models": provenance.get("models"),
                    },
                    "execution_mode": tuned.get("execution_mode"),
                    "scene_plan": tuned.get("scene_plan"),
                    "positive_prompt": tuned.get("positive_prompt"),
                    "negative_prompt": tuned.get("negative_prompt"),
                    "runtime": tuned.get("runtime"),
                }
            )
    return sorted(rows, key=lambda row: (row["case_id"], row["model_id"]))


def _exact_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    renderer.require_exact_keys(value, expected, label=label)


def _failure_rows(generation: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    outputs = generation.get("outputs")
    if not isinstance(outputs, list):
        raise TuneFallbackError("Provider generation outputs are invalid")
    failed = [
        row
        for row in outputs
        if isinstance(row, dict) and row.get("status") == "provider-failed"
    ]
    by_key = {(row.get("case_id"), row.get("model_id")): row for row in failed}
    if len(failed) != 2 or set(by_key) != EXPECTED_KEYS:
        raise TuneFallbackError("Expected exactly the two frozen terminal provider failures")
    return by_key


def _validate_provider_failure(
    value: Any,
    generation_row: dict[str, Any],
    *,
    root: Path,
    key: tuple[str, str],
) -> tuple[dict[str, Any], Path]:
    if not isinstance(value, dict):
        raise TuneFallbackError(f"Provider-failure binding is invalid: {key}")
    _exact_keys(
        value,
        {
            "provider_run_id",
            "run_path",
            "run_sha256",
            "prompt_path",
            "prompt_sha256",
            "status",
            "provider_job_id",
            "terminal_error",
        },
        label=f"target {key} provider_failure",
    )
    for plan_name, generation_name in (
        ("provider_run_id", "provider_run_id"),
        ("run_path", "run_path"),
        ("prompt_path", "prompt_path"),
        ("status", "status"),
        ("terminal_error", "error"),
    ):
        if value.get(plan_name) != generation_row.get(generation_name):
            raise TuneFallbackError(f"Provider generation binding changed: {key} / {plan_name}")
    if (
        value.get("status") != "provider-failed"
        or generation_row.get("execution_mode") != "i2v"
        or generation_row.get("media") is not None
        or generation_row.get("contract_check") is not None
    ):
        raise TuneFallbackError(f"Provider failure is not terminal/no-output: {key}")
    run_rel = renderer.safe_relative(value["run_path"], label=f"target {key} run_path")
    prompt_rel = renderer.safe_relative(
        value["prompt_path"], label=f"target {key} prompt_path"
    )
    run_path = renderer.confined(
        root / run_rel, root, label=f"target {key} provider run", must_exist=True
    )
    prompt_path = renderer.confined(
        root / prompt_rel, root, label=f"target {key} provider prompt", must_exist=True
    )
    if (
        renderer.sha256_file(run_path) != value.get("run_sha256")
        or renderer.sha256_file(prompt_path) != value.get("prompt_sha256")
    ):
        raise TuneFallbackError(f"Provider run/prompt SHA-256 changed: {key}")
    run = renderer.read_json(run_path)
    if not isinstance(run, dict):
        raise TuneFallbackError(f"Provider run artifact is invalid: {key}")
    if (
        run.get("manifest_role") != "clipmaker-lite-tune-video-run"
        or run.get("batch_id") != PROVIDER_BATCH_ID
        or run.get("agent_id") != "clipmaker-lite"
        or run.get("provider_run_id") != value.get("provider_run_id")
        or run.get("case_id") != key[0]
        or run.get("model_id") != key[1]
        or run.get("execution_mode") != "i2v"
        or run.get("status") != "provider-failed"
        or run.get("provider_job_id") != value.get("provider_job_id")
        or run.get("error") != value.get("terminal_error")
        or run.get("provider_may_be_active") is not False
        or run.get("automatic_paid_retry") is not False
        or run.get("media") is not None
        or run.get("contract_check") is not None
        or not isinstance(run.get("completed_at"), str)
    ):
        raise TuneFallbackError(f"Provider run is not the frozen terminal failure: {key}")
    request = run.get("request")
    if (
        not isinstance(request, dict)
        or request.get("model") != "google/veo-3.1-lite"
        or request.get("duration") != 4
        or request.get("generate_audio") is not False
    ):
        raise TuneFallbackError(f"Provider request contract changed: {key}")
    canonical_rel = renderer.safe_relative(
        generation_row.get("video_path"), label=f"target {key} canonical video_path"
    )
    canonical_path = root / canonical_rel
    if canonical_path.exists():
        raise TuneFallbackError(f"Provider output now exists; fallback is forbidden: {key}")
    return value, canonical_rel


def load_fallback_targets(
    *, root: Path = ROOT
) -> tuple[dict[str, Any], tuple[FallbackTarget, ...]]:
    root = root.resolve(strict=True)
    tune_path = renderer.confined(
        root / renderer.TUNE_MANIFEST_REL,
        root,
        label="Tune manifest",
        must_exist=True,
    )
    plan_path = renderer.confined(
        root / PLAN_REL, root, label="fallback plans", must_exist=True
    )
    generation_path = renderer.confined(
        root / PROVIDER_GENERATION_REL,
        root,
        label="provider generation manifest",
        must_exist=True,
    )
    tune = renderer.read_json(tune_path)
    plans = renderer.read_json(plan_path)
    generation = renderer.read_json(generation_path)
    if (
        not isinstance(tune, dict)
        or tune.get("manifest_role") != "clipmaker-lite-tune-review"
        or tune.get("agent_id") != "clipmaker-lite"
        or tune.get("contract_version") != "2.2.0"
    ):
        raise TuneFallbackError("Tune manifest identity mismatch")
    if not isinstance(plans, dict):
        raise TuneFallbackError("Fallback plan document must be an object")
    _exact_keys(
        plans,
        {
            "schema_version",
            "manifest_role",
            "batch_id",
            "agent_id",
            "method",
            "source_manifest",
            "provider_generation",
            "render_contract",
            "targets",
        },
        label="fallback plan document",
    )
    if (
        plans.get("schema_version") != 1
        or plans.get("manifest_role")
        != "clipmaker-lite-tune-compositor-fallback-plans"
        or plans.get("batch_id") != BATCH_ID
        or plans.get("agent_id") != "clipmaker-lite"
        or plans.get("method") != METHOD
    ):
        raise TuneFallbackError("Fallback plan identity mismatch")
    projection = fallback_projection(tune)
    if len(projection) != 2 or {
        (row["case_id"], row["model_id"]) for row in projection
    } != EXPECTED_KEYS:
        raise TuneFallbackError("Tune fallback selection changed")
    source_manifest = plans.get("source_manifest")
    if not isinstance(source_manifest, dict):
        raise TuneFallbackError("Fallback source_manifest is invalid")
    _exact_keys(
        source_manifest,
        {"path", "batch_id", "selection_sha256"},
        label="fallback source_manifest",
    )
    if (
        source_manifest.get("path") != renderer.TUNE_MANIFEST_REL.as_posix()
        or source_manifest.get("batch_id") != tune.get("batch_id")
        or source_manifest.get("selection_sha256")
        != renderer.sha256_bytes(renderer.canonical_json(projection))
    ):
        raise TuneFallbackError("Fallback Tune selection binding changed")
    provider_generation = plans.get("provider_generation")
    if not isinstance(provider_generation, dict):
        raise TuneFallbackError("provider_generation binding is invalid")
    _exact_keys(
        provider_generation,
        {"path", "batch_id", "sha256"},
        label="provider_generation",
    )
    if (
        provider_generation.get("path") != PROVIDER_GENERATION_REL.as_posix()
        or provider_generation.get("batch_id") != PROVIDER_BATCH_ID
        or provider_generation.get("sha256") != renderer.sha256_file(generation_path)
        or not isinstance(generation, dict)
        or generation.get("manifest_role")
        != "clipmaker-lite-tune-video-generation"
        or generation.get("batch_id") != PROVIDER_BATCH_ID
    ):
        raise TuneFallbackError("Provider generation manifest binding changed")
    generation_by_key = _failure_rows(generation)
    contract = plans.get("render_contract")
    if contract != {
        "fps": 30,
        "video_codec": "h264",
        "pixel_format": "yuv420p",
        "duration_seconds": 4,
        "frames": 120,
        "audio": False,
        "network": False,
        "source_mutation": False,
        "allowlisted_primitives": ["camera_push", "pan"],
        "maximum_output": {"width": 1920, "height": 1080, "upscale": False},
    }:
        raise TuneFallbackError("Fallback render contract changed")
    plan_rows = plans.get("targets")
    if not isinstance(plan_rows, list) or len(plan_rows) != 2:
        raise TuneFallbackError("Expected exactly two fallback plans")
    tune_by_key = {(row["case_id"], row["model_id"]): row for row in projection}
    target_keys = {
        "case_id",
        "model_id",
        "original_execution_mode",
        "method",
        "duration_seconds",
        "source",
        "planning",
        "scene_plan_sha256",
        "provider_failure",
        "output_path",
        "plan",
    }
    seen: set[tuple[str, str]] = set()
    result: list[FallbackTarget] = []
    for index, row in enumerate(plan_rows):
        if not isinstance(row, dict):
            raise TuneFallbackError(f"targets[{index}] must be an object")
        _exact_keys(row, target_keys, label=f"fallback targets[{index}]")
        key = (row.get("case_id"), row.get("model_id"))
        if key in seen or key not in EXPECTED_KEYS:
            raise TuneFallbackError(f"Unexpected/duplicate fallback target: {key}")
        seen.add(key)
        frozen = tune_by_key[key]
        if (
            row.get("original_execution_mode") != "i2v"
            or frozen.get("execution_mode") != "i2v"
            or row.get("method") != METHOD
            or row.get("duration_seconds") != 4
            or (frozen.get("runtime") or {}).get("duration_seconds") != 4
            or frozen.get("negative_prompt") is not None
            or not isinstance(frozen.get("positive_prompt"), str)
        ):
            raise TuneFallbackError(f"Original I2V contract changed: {key}")
        source = row.get("source")
        if not isinstance(source, dict):
            raise TuneFallbackError(f"Fallback source is invalid: {key}")
        _exact_keys(
            source, {"path", "sha256", "width", "height"}, label=f"target {key} source"
        )
        frozen_source = frozen.get("source")
        if not isinstance(frozen_source, dict) or any(
            source.get(name) != frozen_source.get(name)
            for name in ("path", "sha256", "width", "height")
        ):
            raise TuneFallbackError(f"Fallback source binding changed: {key}")
        source_rel = renderer.safe_relative(
            source["path"], label=f"target {key} source.path"
        )
        source_path = renderer.confined(
            root / source_rel, root, label=f"target {key} source", must_exist=True
        )
        if renderer.sha256_file(source_path) != source["sha256"]:
            raise TuneFallbackError(f"Fallback source SHA-256 changed: {key}")
        planning = row.get("planning")
        if not isinstance(planning, dict):
            raise TuneFallbackError(f"Fallback planning binding is invalid: {key}")
        _exact_keys(planning, {"run_id", "result_path"}, label=f"target {key} planning")
        provenance = frozen.get("planning_provenance")
        if (
            planning.get("run_id") != frozen.get("planning_run_id")
            or planning.get("result_path") != frozen.get("planning_result_path")
            or not isinstance(provenance, dict)
            or provenance.get("verified") is not True
            or provenance.get("agent_id") != "clipmaker-lite"
            or provenance.get("result_path") != planning.get("result_path")
            or provenance.get("source_image_sha256") != source.get("sha256")
            or key[1] not in (provenance.get("models") or [])
        ):
            raise TuneFallbackError(f"Fallback Lite provenance changed: {key}")
        scene_plan = frozen.get("scene_plan")
        if (
            not isinstance(scene_plan, str)
            or row.get("scene_plan_sha256")
            != renderer.sha256_bytes(scene_plan.encode("utf-8"))
        ):
            raise TuneFallbackError(f"Fallback scene-plan binding changed: {key}")
        plan = renderer.validate_plan(row.get("plan"), duration=4, label=f"target {key} plan")
        if plan["primitive"] not in {"camera_push", "pan"}:
            raise TuneFallbackError(f"Fallback must be camera-only: {key}")
        output_rel = renderer.safe_relative(
            row["output_path"], label=f"target {key} output_path"
        )
        if (
            not output_rel.as_posix().startswith(VIDEO_ROOT_REL.as_posix() + "/")
            or output_rel.suffix != ".mp4"
        ):
            raise TuneFallbackError(f"Fallback output escapes its batch: {key}")
        provider_failure, canonical_video = _validate_provider_failure(
            row.get("provider_failure"), generation_by_key[key], root=root, key=key
        )
        render_target = renderer.Target(
            case_id=str(key[0]),
            model_id=str(key[1]),
            duration_seconds=4,
            source_path=source_rel,
            source_sha256=str(source["sha256"]),
            source_width=int(source["width"]),
            source_height=int(source["height"]),
            planning_run_id=str(planning["run_id"]),
            planning_result_path=str(planning["result_path"]),
            scene_plan_sha256=str(row["scene_plan_sha256"]),
            output_path=output_rel,
            plan=plan,
        )
        result.append(
            FallbackTarget(
                render=render_target,
                provider_failure=provider_failure,
                canonical_video_path=canonical_video,
            )
        )
    if seen != EXPECTED_KEYS:
        raise TuneFallbackError("Fallback target matrix is incomplete")
    return plans, tuple(sorted(result, key=lambda target: target.key))


def _render_target(
    fallback: FallbackTarget,
    *,
    root: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    target = fallback.render
    source = renderer.confined(
        root / target.source_path, root, label="fallback source", must_exist=True
    )
    if renderer.sha256_file(source) != target.source_sha256:
        raise TuneFallbackError(f"Fallback source SHA-256 mismatch: {target.key}")
    output = root / target.output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    renderer.confined(
        output.parent,
        root,
        label="fallback output directory",
        must_exist=True,
        kind="directory",
    )
    with tempfile.NamedTemporaryFile(
        suffix=".mp4", dir=output.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
    temporary.unlink()
    try:
        command, width, height = renderer.command_for_target(
            target, source, temporary, ffmpeg
        )
        renderer.run_command(command, label=f"ffmpeg fallback render {target.key}")
        media, checks = renderer.verify_media(
            target,
            temporary,
            expected_width=width,
            expected_height=height,
            ffprobe=ffprobe,
            root=root,
        )
        if output.exists():
            if not output.is_file() or output.is_symlink():
                raise TuneFallbackError(f"Unsafe existing fallback output: {output}")
            if renderer.sha256_file(output) != media["sha256"]:
                raise TuneFallbackError(
                    f"Refusing to overwrite a different fallback MP4: {output}"
                )
            temporary.unlink()
        else:
            os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "case_id": target.case_id,
        "model_id": target.model_id,
        "execution_mode": "i2v",
        "original_execution_mode": "i2v",
        "method": METHOD,
        "status": "succeeded",
        "fallback_reason": "terminal-provider-failure",
        "provider_failure": fallback.provider_failure,
        "canonical_provider_video_path": fallback.canonical_video_path.as_posix(),
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


def _tool(name: str, explicit: str | None) -> str:
    value = explicit or shutil.which(name)
    if not value:
        raise TuneFallbackError(f"Required local executable not found: {name}")
    return value


def render_batch(
    *, root: Path = ROOT, ffmpeg: str | None = None, ffprobe: str | None = None
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    plans, targets = load_fallback_targets(root=root)
    ffmpeg_path = _tool("ffmpeg", ffmpeg)
    ffprobe_path = _tool("ffprobe", ffprobe)
    outputs = [
        _render_target(
            target, root=root, ffmpeg=ffmpeg_path, ffprobe=ffprobe_path
        )
        for target in targets
    ]
    aggregate = {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-compositor-fallback-generation",
        "batch_id": BATCH_ID,
        "agent_id": "clipmaker-lite",
        "method": METHOD,
        "generated_at": dt.datetime.now(dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "producer": {
            "script_path": "scripts/clipmaker_lite_tune_compositor_fallback.py",
            "script_sha256": renderer.sha256_file(
                root / "scripts/clipmaker_lite_tune_compositor_fallback.py"
            ),
            "renderer_path": "scripts/clipmaker_lite_tune_compositor.py",
            "renderer_sha256": renderer.sha256_file(
                root / "scripts/clipmaker_lite_tune_compositor.py"
            ),
        },
        "input_plan": {
            "path": PLAN_REL.as_posix(),
            "sha256": renderer.sha256_file(root / PLAN_REL),
        },
        "provider_generation": plans["provider_generation"],
        "render_contract": plans["render_contract"],
        "scope": {
            "targets": 2,
            "original_execution_mode": "i2v",
            "provider_calls": 0,
            "network": False,
            "s3_upload": False,
            "tune_manifest_mutation": False,
            "canonical_compositor_manifest_mutation": False,
        },
        "summary": {"succeeded": 2},
        "bytes_total": sum(output["media"]["bytes"] for output in outputs),
        "outputs": outputs,
    }
    renderer.atomic_write_json(root / AGGREGATE_REL, aggregate)
    return aggregate


def verify_batch(
    *, root: Path = ROOT, ffprobe: str | None = None
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    _, targets = load_fallback_targets(root=root)
    aggregate_path = renderer.confined(
        root / AGGREGATE_REL,
        root,
        label="fallback aggregate manifest",
        must_exist=True,
    )
    aggregate = renderer.read_json(aggregate_path)
    if (
        not isinstance(aggregate, dict)
        or aggregate.get("manifest_role")
        != "clipmaker-lite-tune-compositor-fallback-generation"
        or aggregate.get("batch_id") != BATCH_ID
        or aggregate.get("method") != METHOD
        or aggregate.get("input_plan", {}).get("sha256")
        != renderer.sha256_file(root / PLAN_REL)
        or aggregate.get("producer", {}).get("script_sha256")
        != renderer.sha256_file(
            root / "scripts/clipmaker_lite_tune_compositor_fallback.py"
        )
        or aggregate.get("producer", {}).get("renderer_sha256")
        != renderer.sha256_file(root / "scripts/clipmaker_lite_tune_compositor.py")
    ):
        raise TuneFallbackError("Fallback aggregate identity/binding mismatch")
    outputs = aggregate.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 2:
        raise TuneFallbackError("Fallback aggregate output matrix is incomplete")
    by_key = {
        (row.get("case_id"), row.get("model_id")): row
        for row in outputs
        if isinstance(row, dict)
    }
    if set(by_key) != EXPECTED_KEYS:
        raise TuneFallbackError("Fallback aggregate targets changed")
    ffprobe_path = _tool("ffprobe", ffprobe)
    for fallback in targets:
        target = fallback.render
        row = by_key[target.key]
        if (
            row.get("execution_mode") != "i2v"
            or row.get("original_execution_mode") != "i2v"
            or row.get("method") != METHOD
            or row.get("provider_failure") != fallback.provider_failure
            or row.get("video_path") != target.output_path.as_posix()
        ):
            raise TuneFallbackError(f"Fallback aggregate binding changed: {target.key}")
        video = renderer.confined(
            root / target.output_path,
            root,
            label="fallback MP4",
            must_exist=True,
        )
        media, checks = renderer.verify_media(
            target,
            video,
            expected_width=row.get("media", {}).get("width"),
            expected_height=row.get("media", {}).get("height"),
            ffprobe=ffprobe_path,
            root=root,
        )
        if media != row.get("media") or checks != row.get("contract_check"):
            raise TuneFallbackError(f"Fallback media binding changed: {target.key}")
    return {
        "verified": True,
        "batch_id": BATCH_ID,
        "method": METHOD,
        "targets": 2,
        "bytes_total": aggregate["bytes_total"],
        "aggregate_path": AGGREGATE_REL.as_posix(),
        "aggregate_sha256": renderer.sha256_file(aggregate_path),
    }


def summary(aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_id": aggregate["batch_id"],
        "method": aggregate["method"],
        "summary": aggregate["summary"],
        "bytes_total": aggregate["bytes_total"],
        "outputs": [
            {
                "case_id": row["case_id"],
                "model_id": row["model_id"],
                "execution_mode": row["execution_mode"],
                "method": row["method"],
                "provider_job_id": row["provider_failure"]["provider_job_id"],
                "video_path": row["video_path"],
                "sha256": row["media"]["sha256"],
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
    subparsers.add_parser("validate", help="validate both terminal provider failures")
    render = subparsers.add_parser("render", help="render both local camera fallbacks")
    render.add_argument("--ffmpeg")
    render.add_argument("--ffprobe")
    verify = subparsers.add_parser("verify", help="re-probe both fallback outputs")
    verify.add_argument("--ffprobe")
    subparsers.add_parser("summary", help="print the fallback aggregate summary")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate":
            _, targets = load_fallback_targets(root=args.root)
            result: Any = {
                "valid": True,
                "batch_id": BATCH_ID,
                "method": METHOD,
                "targets": len(targets),
                "original_execution_mode": "i2v",
                "provider_jobs": [
                    target.provider_failure["provider_job_id"] for target in targets
                ],
            }
        elif args.command == "render":
            result = summary(
                render_batch(
                    root=args.root,
                    ffmpeg=args.ffmpeg,
                    ffprobe=args.ffprobe,
                )
            )
        elif args.command == "verify":
            result = verify_batch(root=args.root, ffprobe=args.ffprobe)
        else:
            result = summary(
                renderer.read_json(args.root.resolve(strict=True) / AGGREGATE_REL)
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except renderer.TuneCompositorError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
