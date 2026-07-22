#!/usr/bin/env python3
"""Materialize, run, and verify isolated portrait prompt experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import video_generation_pipeline as pipeline


ROOT = pipeline.ROOT
DEFAULT_CATALOG = (
    ROOT
    / "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments"
    / "portrait-permissive-v1/experiment.json"
)
EXPECTED_MODELS = tuple(pipeline.MODEL_CONFIGS)


def prompt_strategy(document: dict[str, Any]) -> str:
    strategy = document.get("prompt_strategy", "shared_combined")
    if strategy not in {"shared_combined", "model_specific"}:
        raise pipeline.PipelineError(f"Unsupported experiment prompt_strategy: {strategy}")
    return strategy


def prompt_bundle(document: dict[str, Any], record: dict[str, Any]) -> dict[str, str]:
    strategy = prompt_strategy(document)
    source = document.get("shared_prompt") if strategy == "shared_combined" else record.get("model_prompt")
    label = "shared_prompt" if strategy == "shared_combined" else f"model_prompt for {record.get('model_id')}"
    if not isinstance(source, dict):
        raise pipeline.PipelineError(f"Experiment is missing {label}")
    for field in ("positive", "negative"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise pipeline.PipelineError(f"Experiment is missing {label}.{field}")
    return {"positive": source["positive"], "negative": source["negative"]}


def combined_prompt(document: dict[str, Any]) -> str:
    if prompt_strategy(document) != "shared_combined":
        raise pipeline.PipelineError("combined_prompt is only valid for shared_combined experiments")
    shared = document["shared_prompt"]
    return f"{shared['positive']}\n\nAvoid: {shared['negative']}"


def prompt_bundle_sha256(prompt: dict[str, Any]) -> str:
    payload = {
        "positive": prompt["positive_prompt"],
        "negative": prompt["negative_prompt"],
        "embed_negative_in_positive": prompt.get("embed_negative_in_positive", False),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_document(
    catalog_path: Path,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    try:
        catalog_path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise pipeline.PipelineError(f"Experiment catalog escapes the repository root: {catalog_path}") from exc
    document = pipeline.read_json(catalog_path)
    experiment_id = document.get("experiment_id")
    if not isinstance(experiment_id, str) or not pipeline.EXPERIMENT_ID_RE.fullmatch(experiment_id):
        raise pipeline.PipelineError(f"Unsafe experiment_id: {experiment_id}")
    if document.get("frame_inputs") != ["first_frame"]:
        raise pipeline.PipelineError("Portrait experiment must use exactly one first_frame input")
    if document.get("camera_state") != "A":
        raise pipeline.PipelineError("Portrait experiment must keep camera state A")
    strategy = prompt_strategy(document)
    if strategy == "shared_combined":
        prompt_bundle(document, {})

    samples, _ = pipeline.validate_catalogs(
        root / "PROMOPAGES-9857/video-samples.json",
        root / "PROMOPAGES-9857/video-prompts.json",
        root,
    )
    sample = next((item for item in samples if item["sample_id"] == document.get("sample_id")), None)
    if sample is None:
        raise pipeline.PipelineError(f"Experiment references unknown sample_id: {document.get('sample_id')}")

    model_records = document.get("models")
    if not isinstance(model_records, list):
        raise pipeline.PipelineError("Experiment models must be a list")
    model_ids = [record.get("model_id") for record in model_records if isinstance(record, dict)]
    if not model_records or len(model_ids) != len(model_records):
        raise pipeline.PipelineError("Experiment must contain at least one valid model record")
    unknown_models = set(model_ids) - set(EXPECTED_MODELS)
    if unknown_models:
        raise pipeline.PipelineError(f"Experiment contains unsupported models: {', '.join(sorted(unknown_models))}")
    if len(model_ids) != len(set(model_ids)):
        raise pipeline.PipelineError("Experiment contains duplicate model records")

    prompts: list[dict[str, Any]] = []
    for record in model_records:
        model_id = record["model_id"]
        config = pipeline.MODEL_CONFIGS[model_id]
        bundle = prompt_bundle(document, record)
        duration = float(record.get("target_duration_seconds", -1))
        supported = {float(value) for value in config.get("durations", [config["duration"]])}
        if duration not in supported:
            raise pipeline.PipelineError(f"Unsupported duration for {model_id}: {duration}")
        last_frame_is_source = record.get("last_frame_is_source", False)
        if not isinstance(last_frame_is_source, bool):
            raise pipeline.PipelineError(f"last_frame_is_source must be boolean for {model_id}")
        if last_frame_is_source and config["adapter"] != "eliza-openrouter":
            raise pipeline.PipelineError(f"last_frame_is_source is unsupported for {model_id}")
        action_complete_by_seconds = record.get("action_complete_by_seconds")
        if action_complete_by_seconds is not None:
            if not isinstance(action_complete_by_seconds, (int, float)) or action_complete_by_seconds <= 0:
                raise pipeline.PipelineError(f"Invalid action_complete_by_seconds for {model_id}")
            if float(action_complete_by_seconds) >= duration:
                raise pipeline.PipelineError(f"Action deadline must precede clip end for {model_id}")
        default_embed = strategy == "shared_combined" and config["adapter"] == "eliza-openrouter"
        embed_negative = record.get("embed_negative_in_positive", default_embed)
        if not isinstance(embed_negative, bool):
            raise pipeline.PipelineError(f"embed_negative_in_positive must be boolean for {model_id}")
        prompt_extend = record.get("prompt_extend")
        if prompt_extend is not None:
            if model_id != "alibaba/wan-2.7" or not isinstance(prompt_extend, bool):
                raise pipeline.PipelineError(f"prompt_extend is unsupported or invalid for {model_id}")
        prompts.append(
            {
                "sample_id": sample["sample_id"],
                "model_id": model_id,
                "target_duration_seconds": record["target_duration_seconds"],
                "motion_plan_id": document["motion_plan_id"],
                "action_complete_by_seconds": action_complete_by_seconds,
                "primary_class": sample["primary_class"],
                "graphic_kind": sample.get("graphic_kind"),
                "graphic_kinds": sample.get("graphic_kinds", []),
                "camera_state": document["camera_state"],
                "positive_prompt": bundle["positive"],
                "negative_prompt": bundle["negative"],
                "embed_negative_in_positive": embed_negative,
                "last_frame_is_source": last_frame_is_source,
                **({"prompt_extend": prompt_extend} if prompt_extend is not None else {}),
            }
        )
    return document, sample, prompts


def expected_prompt_artifact(
    document: dict[str, Any],
    sample: dict[str, Any],
    prompt: dict[str, Any],
    catalog_path: Path,
    root: Path,
) -> dict[str, Any]:
    artifact = pipeline.prompt_artifact(
        sample,
        prompt,
        root,
        source_catalog=pipeline.relative(catalog_path, root),
        experiment_id=document["experiment_id"],
    )
    if prompt_strategy(document) == "shared_combined":
        artifact["experiment"] = {
            "objective": document["objective"],
            "shared_runtime_prompt_sha256": hashlib.sha256(combined_prompt(document).encode("utf-8")).hexdigest(),
            "common_review_window_seconds": document["common_review_window_seconds"],
        }
    else:
        artifact["experiment"] = {
            "objective": document["objective"],
            "prompt_strategy": "model_specific",
            "prompt_bundle_sha256": prompt_bundle_sha256(prompt),
            "common_review_window_seconds": document["common_review_window_seconds"],
        }
    return artifact


def build_rows(
    catalog_path: Path = DEFAULT_CATALOG,
    root: Path = ROOT,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document, sample, prompts = validate_document(catalog_path, root)
    rows = []
    for prompt in sorted(prompts, key=lambda item: item["model_id"]):
        paths = pipeline.artifact_paths(root, sample, prompt["model_id"], document["experiment_id"])
        rows.append(
            {
                "sample": sample,
                "prompt": prompt,
                "paths": paths,
                "expected_prompt_artifact": expected_prompt_artifact(
                    document,
                    sample,
                    prompt,
                    catalog_path,
                    root,
                ),
            }
        )
    return document, rows


def manifest_path(rows: list[dict[str, Any]]) -> Path:
    return rows[0]["paths"]["directory"].parent / "manifest.json"


def write_manifest(document: dict[str, Any], rows: list[dict[str, Any]], root: Path = ROOT) -> None:
    outputs = []
    statuses = Counter()
    for row in rows:
        run_path = row["paths"]["run"]
        run = pipeline.read_json(run_path) if run_path.is_file() else {"status": "missing"}
        status = run.get("status", "missing")
        statuses[status] += 1
        outputs.append(
            {
                "model_id": row["prompt"]["model_id"],
                "target_duration_seconds": row["prompt"]["target_duration_seconds"],
                "status": status,
                "prompt_path": pipeline.relative(row["paths"]["prompt"], root),
                "run_path": pipeline.relative(run_path, root),
                "output_path": pipeline.relative(row["paths"]["video"], root),
                "media": run.get("media"),
                "contract_check": run.get("contract_check"),
                "error": run.get("error"),
            }
        )
    manifest = {
        "schema_version": 1,
        "ticket": document["ticket"],
        "experiment_id": document["experiment_id"],
        "updated_at": pipeline.utc_now(),
        "expected_outputs": len(rows),
        "summary": dict(sorted(statuses.items())),
        "outputs": outputs,
    }
    if prompt_strategy(document) == "shared_combined":
        manifest["shared_runtime_prompt_sha256"] = hashlib.sha256(
            combined_prompt(document).encode("utf-8")
        ).hexdigest()
    else:
        manifest["prompt_strategy"] = "model_specific"
        manifest["prompt_bundle_sha256_by_model"] = {
            row["prompt"]["model_id"]: prompt_bundle_sha256(row["prompt"])
            for row in rows
        }
    pipeline.atomic_write_json(manifest_path(rows), manifest)


def materialize(
    catalog_path: Path = DEFAULT_CATALOG,
    root: Path = ROOT,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document, rows = build_rows(catalog_path, root)
    for row in rows:
        paths = row["paths"]
        paths["directory"].mkdir(parents=True, exist_ok=True)
        expected_prompt = row["expected_prompt_artifact"]
        if paths["prompt"].is_file() and pipeline.read_json(paths["prompt"]) != expected_prompt:
            raise pipeline.PipelineError(
                f"Immutable experiment prompt changed; create a new experiment ID: {paths['prompt']}"
            )
        if not paths["prompt"].is_file():
            pipeline.atomic_write_json(paths["prompt"], expected_prompt)

        expected_request = pipeline.build_request_preview(row["sample"], row["prompt"])
        expected_fingerprint = pipeline.request_fingerprint(expected_request, row["sample"])
        if not paths["run"].is_file():
            run = pipeline.initial_run_artifact(
                row["sample"],
                row["prompt"]["model_id"],
                paths,
                root,
            )
            run["experiment_id"] = document["experiment_id"]
            pipeline.atomic_write_json(paths["run"], run)
            continue
        run = pipeline.read_json(paths["run"])
        if run.get("request") is not None and run["request"] != expected_request:
            raise pipeline.PipelineError(
                f"Immutable experiment request changed; create a new experiment ID: {paths['run']}"
            )
        if run.get("status") == "succeeded":
            if run.get("request_sha256") != expected_fingerprint:
                raise pipeline.PipelineError(f"Succeeded experiment fingerprint mismatch: {paths['run']}")
            if run.get("request_fingerprint_version") != pipeline.REQUEST_FINGERPRINT_VERSION:
                raise pipeline.PipelineError(f"Succeeded experiment fingerprint version mismatch: {paths['run']}")
    write_manifest(document, rows, root)
    return document, rows


def selected_rows(rows: list[dict[str, Any]], model_ids: list[str]) -> list[dict[str, Any]]:
    unknown = set(model_ids) - set(EXPECTED_MODELS)
    if unknown:
        raise pipeline.PipelineError(f"Unknown model filters: {', '.join(sorted(unknown))}")
    return [row for row in rows if not model_ids or row["prompt"]["model_id"] in model_ids]


def write_wan_skill_manifest(
    destination: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    root: Path = ROOT,
) -> None:
    document, rows = materialize(catalog_path, root)
    row = next(item for item in rows if item["prompt"]["model_id"] == "alibaba/wan-2.2")
    pipeline.atomic_write_json(
        destination,
        [
            {
                "image": str((root / row["sample"]["source_path"]).resolve()),
                "output": row["paths"]["video"].name,
                "positive_prompt": row["prompt"]["positive_prompt"],
                "negative_prompt": row["prompt"]["negative_prompt"],
            }
        ],
    )
    print(f"PASS: wrote Wan skill manifest to {destination}")
    print(f"OUT_DIR={row['paths']['directory']}")
    write_manifest(document, rows, root)


def record_existing(
    model_id: str,
    catalog_path: Path = DEFAULT_CATALOG,
    root: Path = ROOT,
) -> None:
    document, rows = materialize(catalog_path, root)
    row = next((item for item in rows if item["prompt"]["model_id"] == model_id), None)
    if row is None:
        raise pipeline.PipelineError(f"Unknown experiment model: {model_id}")
    video_path = row["paths"]["video"]
    if not video_path.is_file():
        raise pipeline.PipelineError(f"Generated MP4 does not exist: {video_path}")
    request = pipeline.build_request_preview(row["sample"], row["prompt"])
    media = pipeline.ffprobe_media(video_path)
    run = pipeline.read_json(row["paths"]["run"])
    run.update(
        {
            "status": "succeeded",
            "request": request,
            "request_sha256": pipeline.request_fingerprint(request, row["sample"]),
            "request_fingerprint_version": pipeline.REQUEST_FINGERPRINT_VERSION,
            "provider_job_id": None,
            "provider_session_hash": None,
            "submitted_at": None,
            "completed_at": pipeline.utc_now(),
            "media": media,
            "contract_check": pipeline.assess_contract(
                model_id,
                media,
                row["prompt"]["target_duration_seconds"],
            ),
            "generation_runner": "wan-image-to-video skill" if model_id == "alibaba/wan-2.2" else "external",
            "error": None,
        }
    )
    pipeline.atomic_write_json(row["paths"]["run"], run)
    write_manifest(document, rows, root)
    print(f"PASS: recorded {pipeline.relative(video_path, root)}")


def verify(
    catalog_path: Path = DEFAULT_CATALOG,
    root: Path = ROOT,
    allow_incomplete: bool = False,
) -> tuple[bool, list[str]]:
    document, rows = build_rows(catalog_path, root)
    errors: list[str] = []
    runtime_prompts: list[str] = []
    for row in rows:
        paths = row["paths"]
        label = row["prompt"]["model_id"]
        if not paths["prompt"].is_file() or pipeline.read_json(paths["prompt"]) != row["expected_prompt_artifact"]:
            errors.append(f"Missing or stale prompt artifact: {label}")
        if not paths["run"].is_file():
            errors.append(f"Missing run artifact: {label}")
            continue
        run = pipeline.read_json(paths["run"])
        if run.get("status") != "succeeded":
            if not allow_incomplete:
                errors.append(f"Not succeeded ({run.get('status')}): {label}")
            continue
        expected_request = pipeline.build_request_preview(row["sample"], row["prompt"])
        expected_fingerprint = pipeline.request_fingerprint(expected_request, row["sample"])
        if run.get("request") != expected_request:
            errors.append(f"Recorded request mismatch: {label}")
        if run.get("request_sha256") != expected_fingerprint:
            errors.append(f"Recorded request fingerprint mismatch: {label}")
        if run.get("request_fingerprint_version") != pipeline.REQUEST_FINGERPRINT_VERSION:
            errors.append(f"Recorded request fingerprint version mismatch: {label}")
        if label == "alibaba/wan-2.2":
            runtime_prompts.append(run["request"]["input"]["prompt"])
        else:
            frames = run["request"].get("frame_images", [])
            expected_frames = ["first_frame"]
            if row["prompt"].get("last_frame_is_source"):
                expected_frames.append("last_frame")
            if [frame.get("frame_type") for frame in frames] != expected_frames:
                errors.append(f"Experiment request has unexpected frame inputs: {label}")
            runtime_prompts.append(run["request"]["prompt"])
        if not paths["video"].is_file():
            errors.append(f"Succeeded run has no MP4: {label}")
            continue
        try:
            media = pipeline.ffprobe_media(paths["video"])
        except pipeline.PipelineError as exc:
            errors.append(str(exc))
            continue
        if run.get("media") != media:
            errors.append(f"Recorded media mismatch: {label}")
        expected_contract = pipeline.assess_contract(
            label,
            media,
            row["prompt"]["target_duration_seconds"],
        )
        if run.get("contract_check") != expected_contract:
            errors.append(f"Recorded contract check mismatch: {label}")
    if (
        prompt_strategy(document) == "shared_combined"
        and runtime_prompts
        and any(value != combined_prompt(document) for value in runtime_prompts)
    ):
        errors.append("Submitted runtime prompts are not identical across models")
    return not errors, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--model", action="append", default=[])
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument(
        "--allow-project-wan-fallback",
        action="store_true",
        help="use the reconnecting project adapter after the bundled Wan skill transport fails",
    )
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument("--timeout", type=int, default=1800)
    run_parser.add_argument("--poll-interval", type=float, default=10.0)
    run_parser.add_argument("--wan-base-url", default=os.environ.get("WAN_DEMO_BASE_URL", pipeline.DEFAULT_WAN_BASE_URL))
    run_parser.add_argument(
        "--wan-stream-base-url",
        default=os.environ.get("WAN_DEMO_STREAM_BASE_URL", pipeline.DEFAULT_WAN_STREAM_BASE_URL),
    )
    run_parser.add_argument(
        "--eliza-base-url",
        default=os.environ.get("ELIZA_OPENROUTER_BASE_URL", pipeline.DEFAULT_ELIZA_BASE_URL),
    )

    wan_parser = subparsers.add_parser("write-wan-skill-manifest")
    wan_parser.add_argument("--output", type=Path, required=True)

    record_parser = subparsers.add_parser("record-existing")
    record_parser.add_argument("--model", required=True, choices=EXPECTED_MODELS)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--allow-incomplete", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            document, rows = materialize(args.catalog)
            print(f"PASS: materialized {len(rows)} outputs for {document['experiment_id']}")
            return 0
        if args.command == "write-wan-skill-manifest":
            write_wan_skill_manifest(args.output, args.catalog)
            return 0
        if args.command == "record-existing":
            record_existing(args.model, args.catalog)
            return 0
        if args.command == "run":
            document, rows = materialize(args.catalog)
            selected = selected_rows(rows, args.model)
            if not selected:
                raise pipeline.PipelineError("Filters selected no experiment entries")
            includes_wan = any(
                row["prompt"]["model_id"] == "alibaba/wan-2.2" for row in selected
            )
            if not args.dry_run and includes_wan and not args.allow_project_wan_fallback:
                raise pipeline.PipelineError(
                    "Run Wan 2.2 through the wan-image-to-video skill, then use record-existing"
                )
            if not args.dry_run and includes_wan:
                for row in selected:
                    if row["prompt"]["model_id"] != "alibaba/wan-2.2":
                        continue
                    run = pipeline.read_json(row["paths"]["run"])
                    run["generation_runner"] = (
                        "project Wan adapter fallback after bundled skill SSE connection reset"
                    )
                    pipeline.atomic_write_json(row["paths"]["run"], run)
            failures = pipeline.run_rows(
                selected,
                args,
                ROOT,
                manifest_writer=lambda: write_manifest(document, rows, ROOT),
            )
            write_manifest(document, rows, ROOT)
            if failures:
                print(f"FAIL: {failures} generation(s) failed", file=sys.stderr)
                return 1
            print(f"PASS: processed {len(selected)} experiment generation(s)")
            return 0
        if args.command == "verify":
            passed, errors = verify(args.catalog, allow_incomplete=args.allow_incomplete)
            if not passed:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print("PASS: portrait experiment artifacts are valid")
            return 0
        raise pipeline.PipelineError(f"Unknown command: {args.command}")
    except (OSError, json.JSONDecodeError, pipeline.PipelineError) as exc:
        print(f"error: {pipeline.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
