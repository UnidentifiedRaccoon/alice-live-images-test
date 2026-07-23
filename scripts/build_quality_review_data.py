#!/usr/bin/env python3
"""Build the browser allowlist for PROMOPAGES-9897 quality annotations.

The page is intentionally static and must also work from a local HTTP server
without requesting the full prompt/run/result artifact tree.  This builder
extracts only the immutable fields needed for review and keeps their source
paths and hashes so an exported annotation can be traced back unambiguously.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path(
    "PROMOPAGES-9857/clipmaker-lite-runs/"
    "promopages-9891-lite3-20260723/manifest.json"
)
DEFAULT_SAMPLES = Path("PROMOPAGES-9857/video-samples.json")
DEFAULT_OUTPUT = Path("manual-review/review-data.js")

REVIEW_TICKET = "PROMOPAGES-9897"
EXPECTED_MODELS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
MODEL_LABELS = {
    "alibaba/wan-2.2": "Wan 2.2",
    "alibaba/wan-2.7": "Wan 2.7",
    "google/veo-3.1-lite": "Veo 3.1 Lite",
}


class ReviewDataError(ValueError):
    """Raised when source artifacts cannot form a trustworthy review item."""


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewDataError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewDataError(f"{label} is not valid JSON: {path}: {exc}") from exc


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewDataError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewDataError(f"{label} must be an array")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewDataError(f"{label} must be a non-empty string")
    return value


def workspace_path(root: Path, raw_path: Any, label: str) -> Path:
    relative = Path(require_string(raw_path, label))
    if relative.is_absolute() or ".." in relative.parts:
        raise ReviewDataError(f"{label} must be a safe workspace-relative path")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewDataError(f"{label} escapes the workspace") from exc
    return resolved


def workspace_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def context_snapshot(
    root: Path,
    result: dict[str, Any],
    result_path: str,
) -> dict[str, Any]:
    inputs = require_mapping(result.get("inputs"), f"{result_path}.inputs")
    article_context = require_mapping(
        inputs.get("article_context"), f"{result_path}.inputs.article_context"
    )
    locator = require_mapping(
        article_context.get("locator"),
        f"{result_path}.inputs.article_context.locator",
    )
    source_path = workspace_path(
        root,
        article_context.get("path"),
        f"{result_path}.inputs.article_context.path",
    )
    source_sha256 = require_string(
        article_context.get("sha256"),
        f"{result_path}.inputs.article_context.sha256",
    )
    if sha256_file(source_path) != source_sha256:
        raise ReviewDataError(f"{result_path} article context SHA-256 is stale")

    article = require_mapping(read_json(source_path, "article context"), "article context")
    blocks = [
        require_mapping(value, f"{source_path}.blocks[{index}]")
        for index, value in enumerate(require_list(article.get("blocks"), f"{source_path}.blocks"))
    ]
    image_index = locator.get("block_index")
    if not isinstance(image_index, int) or image_index < 0 or image_index >= len(blocks):
        raise ReviewDataError(f"{result_path} has an invalid image block index")
    image_block = blocks[image_index]
    if (
        image_block.get("type") != "image"
        or image_block.get("file") != locator.get("file")
        or image_block.get("role") != locator.get("role")
        or image_block.get("caption") != locator.get("caption")
    ):
        raise ReviewDataError(f"{result_path} image locator differs from article context")
    for field in ("article_id", "title", "lead"):
        if article.get(field) != locator.get(field):
            raise ReviewDataError(f"{result_path} locator {field} differs from article context")

    current_heading = locator.get("current_heading")
    if current_heading is not None:
        heading = require_mapping(current_heading, f"{result_path}.current_heading")
        heading_index = heading.get("block_index")
        if not isinstance(heading_index, int) or heading_index < 0 or heading_index >= len(blocks):
            raise ReviewDataError(f"{result_path}.current_heading has an invalid block index")
        source_heading = blocks[heading_index]
        if (
            source_heading.get("type") != "heading"
            or source_heading.get("text") != heading.get("text")
            or source_heading.get("level") != heading.get("level")
        ):
            raise ReviewDataError(f"{result_path}.current_heading differs from article context")

    fragments: list[dict[str, Any]] = []
    for relation, field in (
        ("before", "nearest_text_before"),
        ("after", "nearest_text_after"),
    ):
        raw_fragment = locator.get(field)
        if raw_fragment is None:
            continue
        fragment = require_mapping(raw_fragment, f"{result_path}.{field}")
        block_index = fragment.get("block_index")
        if not isinstance(block_index, int) or block_index < 0 or block_index >= len(blocks):
            raise ReviewDataError(f"{result_path}.{field} has an invalid block index")
        source_block = blocks[block_index]
        if (
            source_block.get("type") != fragment.get("type")
            or source_block.get("text") != fragment.get("text")
        ):
            raise ReviewDataError(f"{result_path}.{field} differs from article context")
        fragments.append(
            {
                "relation": relation,
                "block_index": block_index,
                "type": fragment.get("type"),
                "text": require_string(fragment.get("text"), f"{result_path}.{field}.text"),
            }
        )

    if not fragments:
        raise ReviewDataError(f"{result_path} has no exact adjacent context fragments")

    return {
        "input_scope": "full_article_json",
        "source_path": workspace_relative(root, source_path),
        "source_sha256": source_sha256,
        "article_id": locator.get("article_id"),
        "title": locator.get("title"),
        "lead": locator.get("lead"),
        "current_heading": locator.get("current_heading"),
        "caption": locator.get("caption"),
        "image_position": {
            "block_index": locator.get("block_index"),
            "role": locator.get("role"),
            "file": locator.get("file"),
        },
        "fragments": fragments,
    }


def prompt_expansion_snapshot(runtime: dict[str, Any]) -> dict[str, Any]:
    expansion = runtime.get("prompt_expansion")
    if not isinstance(expansion, dict):
        return {"mode": "not_recorded", "expanded_text_available": False}

    parameter = expansion.get("parameter")
    if isinstance(parameter, str) and parameter and "value" in expansion:
        return {
            "mode": "enabled" if expansion.get("value") is True else "disabled",
            "parameter": parameter,
            "value": expansion.get("value"),
            "expanded_text_available": False,
        }

    mode = expansion.get("mode")
    return {
        "mode": mode if isinstance(mode, str) and mode else "not_recorded",
        "expanded_text_available": False,
    }


def build_item(
    root: Path,
    output: dict[str, Any],
    sample: dict[str, Any],
    batch_id: str,
    manifest_agent_id: str,
) -> dict[str, Any]:
    lite_run_id = require_string(output.get("lite_run_id"), "output.lite_run_id")
    model_id = require_string(output.get("model_id"), f"{lite_run_id}.model_id")
    if model_id not in EXPECTED_MODELS:
        raise ReviewDataError(f"{lite_run_id} uses unsupported model {model_id!r}")

    prompt_path = workspace_path(root, output.get("prompt_path"), f"{lite_run_id}.prompt_path")
    run_path = workspace_path(root, output.get("run_path"), f"{lite_run_id}.run_path")
    video_path = workspace_path(root, output.get("video_path"), f"{lite_run_id}.video_path")
    prompt = require_mapping(read_json(prompt_path, "prompt artifact"), "prompt artifact")
    run = require_mapping(read_json(run_path, "run artifact"), "run artifact")

    if prompt.get("lite_run_id") != lite_run_id or run.get("lite_run_id") != lite_run_id:
        raise ReviewDataError(f"{lite_run_id} does not match its prompt/run artifacts")
    if prompt.get("batch_id") != batch_id or run.get("batch_id") != batch_id:
        raise ReviewDataError(f"{lite_run_id} does not match batch {batch_id}")
    if prompt.get("agent_id") != manifest_agent_id or run.get("agent_id") != manifest_agent_id:
        raise ReviewDataError(f"{lite_run_id} does not match agent {manifest_agent_id}")
    if prompt.get("model_id") != model_id or run.get("model_id") != model_id:
        raise ReviewDataError(f"{lite_run_id} model identity differs across artifacts")

    lite_result = require_mapping(prompt.get("lite_result"), f"{lite_run_id}.lite_result")
    result_path = workspace_path(
        root, lite_result.get("path"), f"{lite_run_id}.lite_result.path"
    )
    result_relative = workspace_relative(root, result_path)
    result = require_mapping(read_json(result_path, "Lite result"), "Lite result")
    result_sha256 = require_string(
        lite_result.get("sha256"), f"{lite_run_id}.lite_result.sha256"
    )
    if sha256_file(result_path) != result_sha256:
        raise ReviewDataError(f"{lite_run_id} Lite result SHA-256 differs from prompt receipt")
    if result.get("job_id") != lite_run_id:
        raise ReviewDataError(f"{lite_run_id} differs from Lite result job_id")

    producer = require_mapping(result.get("producer"), f"{lite_run_id}.producer")
    execution = require_mapping(producer.get("execution"), f"{lite_run_id}.producer.execution")
    provenance = require_mapping(lite_result.get("provenance"), f"{lite_run_id}.provenance")
    if producer.get("agent_id") != manifest_agent_id or provenance.get("verified") is not True:
        raise ReviewDataError(f"{lite_run_id} does not have verified Lite provenance")

    prompt_value = require_mapping(prompt.get("prompt"), f"{lite_run_id}.prompt")
    positive = require_string(prompt_value.get("positive"), f"{lite_run_id}.prompt.positive")
    negative = prompt_value.get("negative")
    if negative is not None and not isinstance(negative, str):
        raise ReviewDataError(f"{lite_run_id}.prompt.negative must be a string or null")

    result_models = require_list(result.get("models"), f"{lite_run_id}.models")
    if len(result_models) != 1:
        raise ReviewDataError(f"{lite_run_id} must be a singleton Lite run")
    authored_model = require_mapping(result_models[0], f"{lite_run_id}.models[0]")
    if (
        authored_model.get("model_id") != model_id
        or authored_model.get("positive_prompt") != positive
        or authored_model.get("negative_prompt") != negative
    ):
        raise ReviewDataError(f"{lite_run_id} prompt differs from the isolated Lite result")

    media = require_mapping(output.get("media"), f"{lite_run_id}.media")
    media_sha256 = require_string(media.get("sha256"), f"{lite_run_id}.media.sha256")
    if sha256_file(video_path) != media_sha256:
        raise ReviewDataError(f"{lite_run_id} video SHA-256 differs from the manifest")

    runtime = require_mapping(prompt.get("runtime"), f"{lite_run_id}.runtime")
    contract_check = require_mapping(
        output.get("contract_check"), f"{lite_run_id}.contract_check"
    )
    warnings = contract_check.get("warnings") or []
    if not isinstance(warnings, list) or not all(isinstance(value, str) for value in warnings):
        raise ReviewDataError(f"{lite_run_id}.contract_check.warnings must be strings")

    return {
        "id": lite_run_id,
        "sample_id": require_string(output.get("sample_id"), f"{lite_run_id}.sample_id"),
        "article": {
            "slug": output.get("article_slug"),
            "label": sample.get("article_label"),
            "url": sample.get("article_url"),
        },
        "agent": {
            "id": manifest_agent_id,
            "contract_version": require_string(
                producer.get("contract_version"), f"{lite_run_id}.producer.contract_version"
            ),
            "planning_run_id": lite_run_id,
            "author_thread_id": require_string(
                execution.get("thread_id"), f"{lite_run_id}.producer.execution.thread_id"
            ),
            "batch_id": batch_id,
            "provenance_verified": True,
        },
        "generation": {
            "job_id": require_string(
                run.get("provider_job_id"), f"{lite_run_id}.provider_job_id"
            ),
            "request_sha256": require_string(
                run.get("request_sha256"), f"{lite_run_id}.request_sha256"
            ),
            "submitted_at": run.get("submitted_at"),
            "completed_at": run.get("completed_at"),
        },
        "model": {"id": model_id, "label": MODEL_LABELS[model_id]},
        "video": {
            "id": lite_run_id,
            "path": workspace_relative(root, video_path),
            "sha256": media_sha256,
            "bytes": media.get("bytes"),
            "duration_seconds": media.get("duration_seconds"),
            "width": media.get("width"),
            "height": media.get("height"),
            "fps": media.get("fps"),
            "frames": media.get("frames"),
            "has_audio": media.get("has_audio"),
        },
        "context": context_snapshot(root, result, result_relative),
        "prompt": {
            "positive": positive,
            "negative": negative,
            "provider": runtime.get("provider"),
            "prompt_expansion": prompt_expansion_snapshot(runtime),
        },
        "provider_contract": {
            "recorded_status": run.get("status"),
            "review_status": output.get("status"),
            "conforms": contract_check.get("conforms") is True,
            "warnings": warnings,
            "requested": contract_check.get("requested"),
        },
        "source_refs": {
            "prompt_path": workspace_relative(root, prompt_path),
            "run_path": workspace_relative(root, run_path),
            "lite_result_path": result_relative,
            "lite_result_sha256": result_sha256,
        },
    }


def build_dataset(
    root: Path = ROOT,
    manifest_relative: Path = DEFAULT_MANIFEST,
    samples_relative: Path = DEFAULT_SAMPLES,
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = workspace_path(root, manifest_relative.as_posix(), "manifest")
    samples_path = workspace_path(root, samples_relative.as_posix(), "samples")
    manifest = require_mapping(read_json(manifest_path, "batch manifest"), "batch manifest")
    samples_document = require_mapping(read_json(samples_path, "sample manifest"), "sample manifest")

    outputs = [
        require_mapping(value, f"manifest.outputs[{index}]")
        for index, value in enumerate(require_list(manifest.get("outputs"), "manifest.outputs"))
    ]
    expected_outputs = manifest.get("expected_outputs")
    if expected_outputs != len(outputs) or len(outputs) != 15:
        raise ReviewDataError(
            f"batch manifest must expose the complete 5×3 matrix; "
            f"expected={expected_outputs!r}, actual={len(outputs)}"
        )

    samples = {
        require_string(value.get("sample_id"), "sample.sample_id"): require_mapping(value, "sample")
        for value in require_list(samples_document.get("samples"), "samples.samples")
    }
    batch_id = require_string(manifest.get("batch_id"), "manifest.batch_id")
    agent_id = require_string(manifest.get("agent_id"), "manifest.agent_id")
    if agent_id != "clipmaker-lite":
        raise ReviewDataError(f"review dataset must use clipmaker-lite, got {agent_id!r}")

    items = []
    seen_ids: set[str] = set()
    for output in outputs:
        sample_id = require_string(output.get("sample_id"), "output.sample_id")
        if sample_id not in samples:
            raise ReviewDataError(f"batch output references unknown sample {sample_id!r}")
        item = build_item(root, output, samples[sample_id], batch_id, agent_id)
        if item["id"] in seen_ids:
            raise ReviewDataError(f"duplicate review item id: {item['id']}")
        seen_ids.add(item["id"])
        items.append(item)

    model_matrix = {
        sample_id: [item["model"]["id"] for item in items if item["sample_id"] == sample_id]
        for sample_id in dict.fromkeys(item["sample_id"] for item in items)
    }
    for sample_id, model_ids in model_matrix.items():
        if tuple(model_ids) != EXPECTED_MODELS:
            raise ReviewDataError(
                f"{sample_id} model order/coverage differs: {model_ids!r}"
            )

    manifest_sha256 = sha256_file(manifest_path)
    data_sha256 = hashlib.sha256(
        json.dumps(
            items,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "dataset_id": f"{batch_id}@{data_sha256[:12]}",
        "review_ticket": REVIEW_TICKET,
        "source": {
            "ticket": manifest.get("ticket"),
            "batch_id": batch_id,
            "manifest_path": workspace_relative(root, manifest_path),
            "manifest_sha256": manifest_sha256,
            "data_sha256": data_sha256,
            "manifest_updated_at": manifest.get("updated_at"),
        },
        "items": items,
    }


def render_javascript(dataset: dict[str, Any]) -> str:
    payload = json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=False)
    return f"window.qualityReviewDataset = {payload};\n"


def write_output(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_javascript(dataset), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the checked-in review-data.js differs from source artifacts",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = build_dataset(ROOT, args.manifest, args.samples)
    output_path = workspace_path(ROOT, args.output.as_posix(), "output")
    rendered = render_javascript(dataset)

    if args.check:
        actual = output_path.read_text(encoding="utf-8") if output_path.exists() else None
        if actual != rendered:
            raise ReviewDataError(
                f"{args.output} is stale; run scripts/build_quality_review_data.py"
            )
        print(f"PASS: {len(dataset['items'])} review items are current")
        return 0

    write_output(dataset, output_path)
    print(f"Wrote {len(dataset['items'])} review items to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
