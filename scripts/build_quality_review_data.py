#!/usr/bin/env python3
"""Build the mixed clipmaker dataset for PROMOPAGES-9897 annotations.

The browser dataset is deliberately an allowlist rather than a directory
listing.  Every item is tied back to immutable prompt/run/video artifacts and
their hashes.  Only the latest Lite cohort exposes article context: historical
cohorts keep ``context`` null instead of reconstructing or guessing it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path(
    "PROMOPAGES-9857/clipmaker-lite-runs/"
    "promopages-9891-lite3-20260723/manifest.json"
)
PREVIOUS_LITE_MANIFEST = Path("PROMOPAGES-9857/clipmaker-lite-generation-manifest.json")
CLASSIC_MANIFEST = Path("PROMOPAGES-9857/video-generation-manifest.json")
DEFAULT_SAMPLES = Path("PROMOPAGES-9857/video-samples.json")
DEFAULT_OUTPUT = Path("manual-review/review-data.js")

REVIEW_TICKET = "PROMOPAGES-9897"
SUPERSEDED_DATASET_IDS = ("promopages-9891-lite3-20260723@f6fdff5dba9a",)
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
MODEL_DIRECTORY_NAMES = {
    "alibaba/wan-2.2": "wan-2.2",
    "alibaba/wan-2.7": "wan-2.7",
    "google/veo-3.1-lite": "veo-3.1-lite",
}

REVIEW_GROUPS = {
    "clipmaker-lite-current": {
        "id": "clipmaker-lite-current",
        "label": "Clipmaker Lite · текущая итерация",
        "short_label": "Lite · текущая",
        "order": 0,
    },
    "clipmaker-lite-previous": {
        "id": "clipmaker-lite-previous",
        "label": "Clipmaker Lite · предыдущая итерация",
        "short_label": "Lite · предыдущая",
        "order": 1,
    },
    "clipmaker-classic-main": {
        "id": "clipmaker-classic-main",
        "label": "Clipmaker Classic · основной прогон",
        "short_label": "Classic · основной",
        "order": 2,
    },
    "clipmaker-classic-experiments": {
        "id": "clipmaker-classic-experiments",
        "label": "Clipmaker Classic · эксперименты",
        "short_label": "Classic · эксперименты",
        "order": 3,
    },
}

# The two Veo jobs listed as failed are intentionally checked and excluded.
# Making the matrix explicit prevents a later unrelated experiment from
# silently entering an annotation dataset.
CLASSIC_EXPERIMENT_MATRIX = {
    "portrait-angry-outburst-v1": EXPECTED_MODELS,
    "portrait-angry-outburst-wan27-v2": ("alibaba/wan-2.7",),
    "portrait-angry-outburst-wan27-extend-v3": ("alibaba/wan-2.7",),
    "portrait-permissive-v1": ("alibaba/wan-2.2", "alibaba/wan-2.7"),
    "portrait-permissive-v2": ("alibaba/wan-2.2", "alibaba/wan-2.7"),
    "portrait-permissive-veo-safe-v1": EXPECTED_MODELS,
}
CLASSIC_EXPECTED_FAILURES = {
    ("portrait-permissive-v1", "google/veo-3.1-lite"),
    ("portrait-permissive-v2", "google/veo-3.1-lite"),
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


def optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReviewDataError(f"{label} must be a string or null")
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


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def artifact_index_sha256(root: Path, paths: Iterable[Path]) -> str:
    index = [
        {"path": workspace_relative(root, path), "sha256": sha256_file(path)}
        for path in sorted(set(paths), key=lambda value: workspace_relative(root, value))
    ]
    return stable_sha256(index)


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
    for relation, field in (("before", "nearest_text_before"), ("after", "nearest_text_after")):
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


def request_parameters(run: dict[str, Any]) -> dict[str, Any]:
    request = run.get("request")
    if not isinstance(request, dict):
        return {}
    provider = request.get("provider")
    if not isinstance(provider, dict):
        return {}
    options = provider.get("options")
    if not isinstance(options, dict):
        return {}
    merged: dict[str, Any] = {}
    for option in options.values():
        if isinstance(option, dict) and isinstance(option.get("parameters"), dict):
            merged.update(option["parameters"])
    return merged


def provider_name(run: dict[str, Any]) -> str | None:
    request = run.get("request")
    if isinstance(request, dict):
        provider = request.get("provider")
        if isinstance(provider, dict) and isinstance(provider.get("options"), dict):
            option_names = list(provider["options"])
            if len(option_names) == 1:
                return option_names[0]
    return optional_string(run.get("adapter"), "run.adapter")


def request_prompt(run: dict[str, Any]) -> str | None:
    request = run.get("request")
    if not isinstance(request, dict):
        return None
    if isinstance(request.get("prompt"), str):
        return request["prompt"]
    request_input = request.get("input")
    if isinstance(request_input, dict) and isinstance(request_input.get("prompt"), str):
        return request_input["prompt"]
    return None


def expansion_from_run(run: dict[str, Any]) -> dict[str, Any]:
    parameters = request_parameters(run)
    for parameter in ("prompt_extend", "enhancePrompt"):
        if parameter in parameters:
            value = parameters[parameter]
            return {
                "mode": "enabled" if value is True else "disabled",
                "parameter": parameter,
                "value": value,
                "expanded_text_available": False,
            }
    return {"mode": "not_recorded", "expanded_text_available": False}


def detect_negative_transport(
    run: dict[str, Any],
    positive: str,
    negative: str | None,
) -> str:
    if not negative:
        return "none"
    parameters = request_parameters(run)
    if (
        parameters.get("negative_prompt") == negative
        or parameters.get("negativePrompt") == negative
    ):
        return "separate"
    transported_prompt = request_prompt(run)
    if transported_prompt and positive in transported_prompt and negative in transported_prompt:
        return "embedded_in_positive"
    return "none"


def review_group(group_id: str) -> dict[str, Any]:
    return dict(REVIEW_GROUPS[group_id])


def article_snapshot(output: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": output.get("article_slug") or sample.get("article_slug"),
        "label": sample.get("article_label"),
        "url": sample.get("article_url"),
    }


def validate_warnings(contract_check: dict[str, Any], label: str) -> list[str]:
    warnings = contract_check.get("warnings") or []
    if not isinstance(warnings, list) or not all(isinstance(value, str) for value in warnings):
        raise ReviewDataError(f"{label}.warnings must be strings")
    return warnings


def media_snapshot(
    root: Path,
    item_id: str,
    video_path: Path,
    media: dict[str, Any],
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    media_sha256 = expected_sha256 or require_string(media.get("sha256"), f"{item_id}.media.sha256")
    if sha256_file(video_path) != media_sha256:
        raise ReviewDataError(f"{item_id} video SHA-256 differs from its artifact receipt")
    recorded_bytes = media.get("bytes")
    if recorded_bytes is not None and recorded_bytes != video_path.stat().st_size:
        raise ReviewDataError(f"{item_id} video byte count differs from its artifact receipt")
    return {
        "id": item_id,
        "path": workspace_relative(root, video_path),
        "sha256": media_sha256,
        "bytes": recorded_bytes if recorded_bytes is not None else video_path.stat().st_size,
        "duration_seconds": media.get("duration_seconds"),
        "width": media.get("width"),
        "height": media.get("height"),
        "fps": media.get("fps"),
        "frames": media.get("frames"),
        "has_audio": media.get("has_audio"),
    }


def generation_snapshot(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": run.get("provider_job_id") or run.get("job_id"),
        "request_sha256": run.get("request_sha256"),
        "submitted_at": run.get("submitted_at"),
        "completed_at": run.get("completed_at") or run.get("updated_at"),
    }


def provider_contract_snapshot(
    run: dict[str, Any],
    contract_check: dict[str, Any],
    review_status: Any,
    label: str,
) -> dict[str, Any]:
    return {
        "recorded_status": run.get("status"),
        "review_status": review_status,
        "conforms": contract_check.get("conforms") is True,
        "warnings": validate_warnings(contract_check, label),
        "requested": contract_check.get("requested"),
    }


def lite_result_receipt(
    root: Path,
    item_id: str,
    lite_result: dict[str, Any],
    expected_agent_id: str = "clipmaker-lite",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    result_path = workspace_path(root, lite_result.get("path"), f"{item_id}.lite_result.path")
    result_relative = workspace_relative(root, result_path)
    result = require_mapping(read_json(result_path, "Lite result"), "Lite result")
    result_sha256 = require_string(lite_result.get("sha256"), f"{item_id}.lite_result.sha256")
    if sha256_file(result_path) != result_sha256:
        raise ReviewDataError(f"{item_id} Lite result SHA-256 differs from its receipt")
    producer = require_mapping(result.get("producer"), f"{item_id}.producer")
    execution = require_mapping(producer.get("execution"), f"{item_id}.producer.execution")
    provenance = require_mapping(lite_result.get("provenance"), f"{item_id}.provenance")
    if producer.get("agent_id") != expected_agent_id or provenance.get("verified") is not True:
        raise ReviewDataError(f"{item_id} does not have verified historical Lite provenance")
    return result, producer, execution, result_relative, result_sha256


def build_current_lite_item(
    root: Path,
    output: dict[str, Any],
    sample: dict[str, Any],
    batch_id: str,
    manifest_agent_id: str,
) -> dict[str, Any]:
    item_id = require_string(output.get("lite_run_id"), "output.lite_run_id")
    model_id = require_string(output.get("model_id"), f"{item_id}.model_id")
    if model_id not in EXPECTED_MODELS:
        raise ReviewDataError(f"{item_id} uses unsupported model {model_id!r}")

    prompt_path = workspace_path(root, output.get("prompt_path"), f"{item_id}.prompt_path")
    run_path = workspace_path(root, output.get("run_path"), f"{item_id}.run_path")
    video_path = workspace_path(root, output.get("video_path"), f"{item_id}.video_path")
    prompt = require_mapping(read_json(prompt_path, "prompt artifact"), "prompt artifact")
    run = require_mapping(read_json(run_path, "run artifact"), "run artifact")

    if prompt.get("lite_run_id") != item_id or run.get("lite_run_id") != item_id:
        raise ReviewDataError(f"{item_id} does not match its prompt/run artifacts")
    if prompt.get("batch_id") != batch_id or run.get("batch_id") != batch_id:
        raise ReviewDataError(f"{item_id} does not match batch {batch_id}")
    if prompt.get("agent_id") != manifest_agent_id or run.get("agent_id") != manifest_agent_id:
        raise ReviewDataError(f"{item_id} does not match agent {manifest_agent_id}")
    if prompt.get("model_id") != model_id or run.get("model_id") != model_id:
        raise ReviewDataError(f"{item_id} model identity differs across artifacts")

    lite_result = require_mapping(prompt.get("lite_result"), f"{item_id}.lite_result")
    result, producer, execution, result_relative, result_sha256 = lite_result_receipt(
        root, item_id, lite_result, manifest_agent_id
    )
    if result.get("job_id") != item_id:
        raise ReviewDataError(f"{item_id} differs from Lite result job_id")

    prompt_value = require_mapping(prompt.get("prompt"), f"{item_id}.prompt")
    positive = require_string(prompt_value.get("positive"), f"{item_id}.prompt.positive")
    negative = optional_string(prompt_value.get("negative"), f"{item_id}.prompt.negative")
    result_models = require_list(result.get("models"), f"{item_id}.models")
    if len(result_models) != 1:
        raise ReviewDataError(f"{item_id} must be a singleton Lite run")
    authored_model = require_mapping(result_models[0], f"{item_id}.models[0]")
    if (
        authored_model.get("model_id") != model_id
        or authored_model.get("positive_prompt") != positive
        or authored_model.get("negative_prompt") != negative
    ):
        raise ReviewDataError(f"{item_id} prompt differs from the isolated Lite result")

    media = require_mapping(output.get("media"), f"{item_id}.media")
    contract_check = require_mapping(output.get("contract_check"), f"{item_id}.contract_check")
    runtime = require_mapping(prompt.get("runtime"), f"{item_id}.runtime")
    contract_version = require_string(
        producer.get("contract_version"), f"{item_id}.producer.contract_version"
    )
    return {
        "id": item_id,
        "sample_id": require_string(output.get("sample_id"), f"{item_id}.sample_id"),
        "article": article_snapshot(output, sample),
        "review_group": review_group("clipmaker-lite-current"),
        "approach": {"id": "clipmaker-lite-current", "label": "Lite · текущая итерация"},
        "prompt_author": {
            "id": manifest_agent_id,
            "label": "Clipmaker Lite",
            "contract_version": contract_version,
            "attribution_basis": "isolated_runner_verified",
            "provenance_verified": True,
        },
        "agent": {
            "id": manifest_agent_id,
            "contract_version": contract_version,
            "planning_run_id": item_id,
            "author_thread_id": require_string(
                execution.get("thread_id"), f"{item_id}.producer.execution.thread_id"
            ),
            "batch_id": batch_id,
            "provenance_verified": True,
        },
        "generation": generation_snapshot(run),
        "model": {"id": model_id, "label": MODEL_LABELS[model_id]},
        "video": media_snapshot(root, item_id, video_path, media),
        "context": context_snapshot(root, result, result_relative),
        "context_status": {"availability": "shown", "reason": None},
        "prompt": {
            "positive": positive,
            "negative": negative,
            "provider": runtime.get("provider"),
            "prompt_expansion": prompt_expansion_snapshot(runtime),
            "source_model_id": model_id,
            "native_for_generation_model": True,
            "negative_transport": detect_negative_transport(run, positive, negative),
        },
        "provider_contract": provider_contract_snapshot(
            run, contract_check, output.get("status"), f"{item_id}.contract_check"
        ),
        "experiment": None,
        "source_refs": {
            "prompt_path": workspace_relative(root, prompt_path),
            "prompt_sha256": sha256_file(prompt_path),
            "run_path": workspace_relative(root, run_path),
            "run_sha256": sha256_file(run_path),
            "lite_result_path": result_relative,
            "lite_result_sha256": result_sha256,
        },
    }


def build_previous_lite_native_item(
    root: Path,
    output: dict[str, Any],
    sample: dict[str, Any],
) -> dict[str, Any]:
    item_id = require_string(output.get("output_id"), "previous output.output_id")
    model_id = require_string(output.get("target_model_id"), f"{item_id}.target_model_id")
    if output.get("route") != "native" or output.get("attested_lite_model") is not True:
        raise ReviewDataError(f"{item_id} is not a native historical Lite output")
    prompt_path = workspace_path(root, output.get("prompt_path"), f"{item_id}.prompt_path")
    run_path = workspace_path(root, output.get("run_path"), f"{item_id}.run_path")
    video_path = workspace_path(root, output.get("video_path"), f"{item_id}.video_path")
    prompt = require_mapping(read_json(prompt_path, "historical Lite prompt"), "historical Lite prompt")
    run = require_mapping(read_json(run_path, "historical Lite run"), "historical Lite run")
    if (
        prompt.get("lite_run_id") != item_id
        or run.get("lite_run_id") != item_id
        or prompt.get("agent_id") != "clipmaker-lite"
        or run.get("agent_id") != "clipmaker-lite"
        or prompt.get("model_id") != model_id
        or run.get("model_id") != model_id
    ):
        raise ReviewDataError(f"{item_id} historical Lite prompt/run identity differs")

    lite_result = require_mapping(prompt.get("lite_result"), f"{item_id}.lite_result")
    result, producer, execution, result_relative, result_sha256 = lite_result_receipt(root, item_id, lite_result)
    if result.get("job_id") != item_id:
        raise ReviewDataError(f"{item_id} differs from its historical Lite result job_id")
    prompt_value = require_mapping(prompt.get("prompt"), f"{item_id}.prompt")
    positive = require_string(prompt_value.get("positive"), f"{item_id}.prompt.positive")
    negative = optional_string(prompt_value.get("negative"), f"{item_id}.prompt.negative")
    models = require_list(result.get("models"), f"{item_id}.models")
    if len(models) != 1:
        raise ReviewDataError(f"{item_id} historical Lite result must contain one model")
    authored = require_mapping(models[0], f"{item_id}.models[0]")
    if (
        authored.get("model_id") != model_id
        or authored.get("positive_prompt") != positive
        or authored.get("negative_prompt") != negative
    ):
        raise ReviewDataError(f"{item_id} differs from its historical isolated Lite prompt")

    run_media = require_mapping(run.get("media"), f"{item_id}.run.media")
    manifest_media = require_mapping(output.get("media"), f"{item_id}.manifest.media")
    if run_media.get("sha256") != manifest_media.get("sha256"):
        raise ReviewDataError(f"{item_id} media hash differs between run and manifest")
    contract_check = require_mapping(output.get("contract_check"), f"{item_id}.contract_check")
    runtime = require_mapping(prompt.get("target"), f"{item_id}.target")
    contract_version = require_string(producer.get("contract_version"), f"{item_id}.contract_version")
    return {
        "id": item_id,
        "sample_id": require_string(output.get("sample_id"), f"{item_id}.sample_id"),
        "article": article_snapshot(output, sample),
        "review_group": review_group("clipmaker-lite-previous"),
        "approach": {"id": "clipmaker-lite-previous-native", "label": "Lite · предыдущая итерация"},
        "prompt_author": {
            "id": "clipmaker-lite",
            "label": "Clipmaker Lite",
            "contract_version": contract_version,
            "attribution_basis": "historical_isolated_runner_receipt",
            "provenance_verified": True,
        },
        "agent": {
            "id": "clipmaker-lite",
            "contract_version": contract_version,
            "planning_run_id": item_id,
            "author_thread_id": require_string(execution.get("thread_id"), f"{item_id}.thread_id"),
            "batch_id": None,
            "provenance_verified": True,
        },
        "generation": generation_snapshot(run),
        "model": {"id": model_id, "label": MODEL_LABELS[model_id]},
        "video": media_snapshot(root, item_id, video_path, run_media),
        "context": None,
        "context_status": {
            "availability": "omitted_by_review_policy",
            "reason": "Контекст не показывается для этой исторической итерации.",
        },
        "prompt": {
            "positive": positive,
            "negative": negative,
            "provider": runtime.get("provider"),
            "prompt_expansion": prompt_expansion_snapshot(runtime),
            "source_model_id": model_id,
            "native_for_generation_model": True,
            "negative_transport": detect_negative_transport(run, positive, negative),
        },
        "provider_contract": provider_contract_snapshot(
            run, contract_check, output.get("status"), f"{item_id}.contract_check"
        ),
        "experiment": None,
        "source_refs": {
            "prompt_path": workspace_relative(root, prompt_path),
            "prompt_sha256": sha256_file(prompt_path),
            "run_path": workspace_relative(root, run_path),
            "run_sha256": sha256_file(run_path),
            "lite_result_path": result_relative,
            "lite_result_sha256": result_sha256,
        },
    }


def build_previous_lite_control_item(
    root: Path,
    output: dict[str, Any],
    sample: dict[str, Any],
) -> dict[str, Any]:
    item_id = require_string(output.get("output_id"), "control output.output_id")
    target_model_id = require_string(output.get("target_model_id"), f"{item_id}.target_model_id")
    source_model_id = require_string(output.get("prompt_source_model_id"), f"{item_id}.prompt_source_model_id")
    if (
        output.get("route") != "wan-streamlit-control"
        or output.get("attested_lite_model") is not False
        or target_model_id != "alibaba/wan-2.2"
        or source_model_id != "alibaba/wan-2.7"
    ):
        raise ReviewDataError(f"{item_id} is not the expected Wan 2.7 → Wan 2.2 Lite control")
    prompt_path = workspace_path(root, output.get("prompt_path"), f"{item_id}.prompt_path")
    run_path = workspace_path(root, output.get("run_path"), f"{item_id}.run_path")
    video_path = workspace_path(root, output.get("video_path"), f"{item_id}.video_path")
    prompt = require_mapping(read_json(prompt_path, "Lite control prompt"), "Lite control prompt")
    run = require_mapping(read_json(run_path, "Lite control run"), "Lite control run")
    if (
        prompt.get("job_id") != item_id
        or run.get("job_id") != item_id
        or prompt.get("target_model_id") != target_model_id
        or run.get("target_model_id") != target_model_id
        or prompt.get("prompt_source_model_id") != source_model_id
        or run.get("prompt_source_model_id") != source_model_id
    ):
        raise ReviewDataError(f"{item_id} control prompt/run identity differs")

    positive = require_string(prompt.get("positive_prompt"), f"{item_id}.positive_prompt")
    negative = optional_string(prompt.get("negative_prompt"), f"{item_id}.negative_prompt")
    source = require_mapping(prompt.get("prompt_source"), f"{item_id}.prompt_source")
    manifest_source = require_mapping(output.get("prompt_source"), f"{item_id}.manifest.prompt_source")
    for field in ("result_job_id", "result_path", "result_sha256"):
        if source.get(field) != manifest_source.get(field):
            raise ReviewDataError(f"{item_id} control {field} differs between prompt and manifest")
    source_provenance = require_mapping(source.get("lite_provenance"), f"{item_id}.lite_provenance")
    if source_provenance.get("agent_id") != "clipmaker-lite" or source_provenance.get("verified") is not True:
        raise ReviewDataError(f"{item_id} control prompt source is not verified Lite output")
    result_path = workspace_path(root, source.get("result_path"), f"{item_id}.result_path")
    result_sha256 = require_string(source.get("result_sha256"), f"{item_id}.result_sha256")
    if sha256_file(result_path) != result_sha256:
        raise ReviewDataError(f"{item_id} control source result SHA-256 differs")
    result = require_mapping(read_json(result_path, "control source Lite result"), "control source Lite result")
    if result.get("job_id") != source.get("result_job_id"):
        raise ReviewDataError(f"{item_id} control source result job id differs")
    models = require_list(result.get("models"), f"{item_id}.source.models")
    if len(models) != 1:
        raise ReviewDataError(f"{item_id} control source result must contain one model")
    authored = require_mapping(models[0], f"{item_id}.source.models[0]")
    if (
        authored.get("model_id") != source_model_id
        or authored.get("positive_prompt") != positive
        or authored.get("negative_prompt") != negative
    ):
        raise ReviewDataError(f"{item_id} control prompt differs from its Lite source model")

    producer = require_mapping(result.get("producer"), f"{item_id}.source.producer")
    execution = require_mapping(producer.get("execution"), f"{item_id}.source.execution")
    contract_version = require_string(source_provenance.get("contract_version"), f"{item_id}.contract_version")
    run_output = require_mapping(run.get("output"), f"{item_id}.run.output")
    if workspace_relative(root, video_path) != run_output.get("path"):
        raise ReviewDataError(f"{item_id} control video path differs from its run receipt")
    run_media = dict(require_mapping(run.get("media"), f"{item_id}.run.media"))
    run_media["sha256"] = require_string(run_output.get("sha256"), f"{item_id}.run.output.sha256")
    run_media["bytes"] = run_output.get("bytes")
    contract_check = require_mapping(output.get("contract_check"), f"{item_id}.contract_check")
    runtime = require_mapping(prompt.get("runtime"), f"{item_id}.runtime")
    return {
        "id": item_id,
        "sample_id": require_string(output.get("sample_id"), f"{item_id}.sample_id"),
        "article": article_snapshot(output, sample),
        "review_group": review_group("clipmaker-lite-previous"),
        "approach": {
            "id": "clipmaker-lite-cross-model-control",
            "label": "Lite · перенос Wan 2.7 → Wan 2.2",
        },
        "prompt_author": {
            "id": "clipmaker-lite",
            "label": "Clipmaker Lite",
            "contract_version": contract_version,
            "attribution_basis": "historical_lite_prompt_reused_cross_model",
            "provenance_verified": True,
        },
        "agent": {
            "id": "clipmaker-lite",
            "contract_version": contract_version,
            "planning_run_id": source.get("result_job_id"),
            "author_thread_id": require_string(execution.get("thread_id"), f"{item_id}.thread_id"),
            "batch_id": None,
            "provenance_verified": True,
        },
        "generation": generation_snapshot(run),
        "model": {"id": target_model_id, "label": MODEL_LABELS[target_model_id]},
        "video": media_snapshot(root, item_id, video_path, run_media),
        "context": None,
        "context_status": {
            "availability": "omitted_by_review_policy",
            "reason": "Контекст не показывается для этой исторической итерации.",
        },
        "prompt": {
            "positive": positive,
            "negative": negative,
            "provider": prompt.get("provider_route"),
            "prompt_expansion": {"mode": "disabled", "expanded_text_available": False},
            "source_model_id": source_model_id,
            "native_for_generation_model": False,
            "negative_transport": detect_negative_transport(run, positive, negative),
        },
        "provider_contract": provider_contract_snapshot(
            run, contract_check, output.get("status"), f"{item_id}.contract_check"
        ),
        "experiment": None,
        "source_refs": {
            "prompt_path": workspace_relative(root, prompt_path),
            "prompt_sha256": sha256_file(prompt_path),
            "run_path": workspace_relative(root, run_path),
            "run_sha256": sha256_file(run_path),
            "lite_result_path": workspace_relative(root, result_path),
            "lite_result_sha256": result_sha256,
        },
    }


def build_classic_item(
    root: Path,
    item_id: str,
    prompt_path: Path,
    run_path: Path,
    video_path: Path,
    sample: dict[str, Any],
    review_group_id: str,
    review_status: Any,
    manifest_media: dict[str, Any] | None = None,
    experiment_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = require_mapping(read_json(prompt_path, "Classic prompt"), "Classic prompt")
    run = require_mapping(read_json(run_path, "Classic run"), "Classic run")
    model_id = require_string(prompt.get("model_id"), f"{item_id}.model_id")
    sample_id = require_string(prompt.get("sample_id"), f"{item_id}.sample_id")
    if model_id not in EXPECTED_MODELS:
        raise ReviewDataError(f"{item_id} uses unsupported model {model_id!r}")
    if (
        run.get("model_id") != model_id
        or run.get("sample_id") != sample_id
        or run.get("status") != "succeeded"
        or prompt.get("generator") != "project clipmaker agent"
        or run.get("prompt_path") != workspace_relative(root, prompt_path)
        or run.get("output_path") != workspace_relative(root, video_path)
    ):
        raise ReviewDataError(f"{item_id} Classic prompt/run binding differs")

    prompt_value = require_mapping(prompt.get("prompt"), f"{item_id}.prompt")
    positive = require_string(prompt_value.get("positive"), f"{item_id}.prompt.positive")
    negative = optional_string(prompt_value.get("negative"), f"{item_id}.prompt.negative")
    source_model_id = optional_string(
        prompt_value.get("source_model_id"), f"{item_id}.prompt.source_model_id"
    )
    if source_model_id is not None and source_model_id not in EXPECTED_MODELS:
        raise ReviewDataError(f"{item_id} uses unsupported source model {source_model_id!r}")
    if positive not in (request_prompt(run) or ""):
        raise ReviewDataError(f"{item_id} authored positive prompt is absent from provider request")
    run_media = require_mapping(run.get("media"), f"{item_id}.run.media")
    if manifest_media is not None:
        manifest_sha = require_string(manifest_media.get("sha256"), f"{item_id}.manifest.media.sha256")
        if run_media.get("sha256") != manifest_sha:
            raise ReviewDataError(f"{item_id} media hash differs between run and manifest")
    contract_check = require_mapping(run.get("contract_check"), f"{item_id}.contract_check")
    experiment_id = prompt.get("experiment_id")
    if experiment_document is None:
        if experiment_id is not None or run.get("experiment_id") is not None:
            raise ReviewDataError(f"{item_id} unexpected experiment identity")
        approach = {"id": "clipmaker-classic-main", "label": "Classic · основной подход"}
        experiment = None
    else:
        expected_experiment_id = require_string(
            experiment_document.get("experiment_id"), f"{item_id}.experiment.experiment_id"
        )
        if experiment_id != expected_experiment_id or run.get("experiment_id") != expected_experiment_id:
            raise ReviewDataError(f"{item_id} experiment identity differs")
        approach = {
            "id": f"clipmaker-classic-{expected_experiment_id}",
            "label": f"Classic · {expected_experiment_id}",
        }
        experiment_meta = require_mapping(prompt.get("experiment"), f"{item_id}.experiment")
        experiment = {
            "id": expected_experiment_id,
            "objective": experiment_document.get("objective") or experiment_meta.get("objective"),
            "prompt_strategy": (
                experiment_document.get("prompt_strategy") or experiment_meta.get("prompt_strategy")
            ),
            "source_catalog": prompt.get("source_catalog"),
        }

    return {
        "id": item_id,
        "sample_id": sample_id,
        "article": article_snapshot(prompt, sample),
        "review_group": review_group(review_group_id),
        "approach": approach,
        "prompt_author": {
            "id": "clipmaker-classic",
            "label": "Clipmaker Classic",
            "contract_version": None,
            "attribution_basis": "legacy_generator_field",
            "provenance_verified": False,
        },
        "agent": {
            "id": "clipmaker-classic",
            "contract_version": None,
            "planning_run_id": None,
            "author_thread_id": None,
            "batch_id": None,
            "provenance_verified": False,
        },
        "generation": generation_snapshot(run),
        "model": {"id": model_id, "label": MODEL_LABELS[model_id]},
        "video": media_snapshot(root, item_id, video_path, run_media),
        "context": None,
        "context_status": {
            "availability": "not_available_in_artifacts",
            "reason": "Фрагмент статьи не записан в артефактах этого прогона.",
        },
        "prompt": {
            "positive": positive,
            "negative": negative,
            "provider": provider_name(run),
            "prompt_expansion": expansion_from_run(run),
            "source_model_id": source_model_id,
            "native_for_generation_model": source_model_id in (None, model_id),
            "negative_transport": detect_negative_transport(run, positive, negative),
        },
        "provider_contract": provider_contract_snapshot(
            run, contract_check, review_status, f"{item_id}.contract_check"
        ),
        "experiment": experiment,
        "source_refs": {
            "prompt_path": workspace_relative(root, prompt_path),
            "prompt_sha256": sha256_file(prompt_path),
            "run_path": workspace_relative(root, run_path),
            "run_sha256": sha256_file(run_path),
            "lite_result_path": None,
            "lite_result_sha256": None,
        },
    }


def load_samples(root: Path, samples_relative: Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    samples_path = workspace_path(root, samples_relative.as_posix(), "samples")
    samples_document = require_mapping(read_json(samples_path, "sample manifest"), "sample manifest")
    samples: dict[str, dict[str, Any]] = {}
    for value in require_list(samples_document.get("samples"), "samples.samples"):
        sample = require_mapping(value, "sample")
        sample_id = require_string(sample.get("sample_id"), "sample.sample_id")
        if sample_id in samples:
            raise ReviewDataError(f"duplicate sample id {sample_id!r}")
        samples[sample_id] = sample
    return samples_path, samples


def validate_five_by_three(items: list[dict[str, Any]], label: str) -> None:
    if len(items) != 15:
        raise ReviewDataError(f"{label} must contain 15 items, got {len(items)}")
    sample_order = list(dict.fromkeys(item["sample_id"] for item in items))
    if len(sample_order) != 5:
        raise ReviewDataError(f"{label} must contain five samples")
    for sample_id in sample_order:
        model_ids = [item["model"]["id"] for item in items if item["sample_id"] == sample_id]
        if tuple(model_ids) != EXPECTED_MODELS:
            raise ReviewDataError(f"{label} {sample_id} model order/coverage differs: {model_ids!r}")


def review_basis_sha256(item: dict[str, Any]) -> str:
    """Hash the immutable evidence and labels that a reviewer actually evaluates."""
    return stable_sha256(
        {
            "video": {
                "id": item["video"]["id"],
                "sha256": item["video"]["sha256"],
            },
            "context": item["context"],
            "context_status": item["context_status"],
            "prompt": item["prompt"],
            "prompt_author": item["prompt_author"],
            "review_group": item["review_group"],
            "approach": item["approach"],
            "model_id": item["model"]["id"],
            "provider_contract": item["provider_contract"],
        }
    )


def build_dataset(
    root: Path = ROOT,
    manifest_relative: Path = DEFAULT_MANIFEST,
    samples_relative: Path = DEFAULT_SAMPLES,
) -> dict[str, Any]:
    root = root.resolve()
    samples_path, samples = load_samples(root, samples_relative)

    current_manifest_path = workspace_path(root, manifest_relative.as_posix(), "current Lite manifest")
    current_manifest = require_mapping(
        read_json(current_manifest_path, "current Lite manifest"), "current Lite manifest"
    )
    current_outputs = [
        require_mapping(value, f"current.outputs[{index}]")
        for index, value in enumerate(require_list(current_manifest.get("outputs"), "current.outputs"))
    ]
    if current_manifest.get("expected_outputs") != len(current_outputs) or len(current_outputs) != 15:
        raise ReviewDataError("current Lite manifest must expose the complete 5×3 matrix")
    batch_id = require_string(current_manifest.get("batch_id"), "current.batch_id")
    current_agent_id = require_string(current_manifest.get("agent_id"), "current.agent_id")
    if current_agent_id != "clipmaker-lite":
        raise ReviewDataError(f"current review dataset must use clipmaker-lite, got {current_agent_id!r}")
    current_items = []
    for output in current_outputs:
        sample_id = require_string(output.get("sample_id"), "current.output.sample_id")
        if sample_id not in samples:
            raise ReviewDataError(f"current output references unknown sample {sample_id!r}")
        current_items.append(
            build_current_lite_item(root, output, samples[sample_id], batch_id, current_agent_id)
        )
    validate_five_by_three(current_items, "current Lite cohort")

    previous_manifest_path = workspace_path(
        root, PREVIOUS_LITE_MANIFEST.as_posix(), "previous Lite manifest"
    )
    previous_manifest = require_mapping(
        read_json(previous_manifest_path, "previous Lite manifest"), "previous Lite manifest"
    )
    previous_outputs = [
        require_mapping(value, f"previous.outputs[{index}]")
        for index, value in enumerate(require_list(previous_manifest.get("outputs"), "previous.outputs"))
    ]
    if previous_manifest.get("expected_outputs") != len(previous_outputs) or len(previous_outputs) != 15:
        raise ReviewDataError("previous Lite manifest must expose 15 completed outputs")
    previous_items = []
    for output in previous_outputs:
        sample_id = require_string(output.get("sample_id"), "previous.output.sample_id")
        if sample_id not in samples:
            raise ReviewDataError(f"previous output references unknown sample {sample_id!r}")
        if output.get("route") == "native":
            item = build_previous_lite_native_item(root, output, samples[sample_id])
        elif output.get("route") == "wan-streamlit-control":
            item = build_previous_lite_control_item(root, output, samples[sample_id])
        else:
            raise ReviewDataError(f"previous output has unknown route {output.get('route')!r}")
        previous_items.append(item)
    sample_order = {sample_id: index for index, sample_id in enumerate(samples)}
    model_order = {model_id: index for index, model_id in enumerate(EXPECTED_MODELS)}
    previous_items.sort(key=lambda item: (sample_order[item["sample_id"]], model_order[item["model"]["id"]]))
    validate_five_by_three(previous_items, "previous Lite cohort")

    classic_manifest_path = workspace_path(root, CLASSIC_MANIFEST.as_posix(), "Classic manifest")
    classic_manifest = require_mapping(read_json(classic_manifest_path, "Classic manifest"), "Classic manifest")
    classic_outputs = [
        require_mapping(value, f"classic.outputs[{index}]")
        for index, value in enumerate(require_list(classic_manifest.get("outputs"), "classic.outputs"))
    ]
    if classic_manifest.get("expected_outputs") != len(classic_outputs) or len(classic_outputs) != 15:
        raise ReviewDataError("Classic manifest must expose the complete 5×3 matrix")
    classic_main_items = []
    for output in classic_outputs:
        sample_id = require_string(output.get("sample_id"), "classic.output.sample_id")
        model_id = require_string(output.get("model_id"), "classic.output.model_id")
        if sample_id not in samples or model_id not in EXPECTED_MODELS:
            raise ReviewDataError(f"Classic output has unknown sample/model {sample_id!r}/{model_id!r}")
        item_id = f"promopages-9856-classic-{sample_id}-{MODEL_DIRECTORY_NAMES[model_id]}"
        prompt_path = workspace_path(root, output.get("prompt_path"), f"{item_id}.prompt_path")
        run_path = workspace_path(root, output.get("run_path"), f"{item_id}.run_path")
        video_path = workspace_path(root, output.get("video_path"), f"{item_id}.video_path")
        item = build_classic_item(
            root,
            item_id,
            prompt_path,
            run_path,
            video_path,
            samples[sample_id],
            "clipmaker-classic-main",
            output.get("status"),
            require_mapping(output.get("media"), f"{item_id}.media"),
        )
        if item["sample_id"] != sample_id or item["model"]["id"] != model_id:
            raise ReviewDataError(f"{item_id} differs from its Classic manifest entry")
        classic_main_items.append(item)
    validate_five_by_three(classic_main_items, "Classic main cohort")

    experiment_root = workspace_path(
        root,
        "PROMOPAGES-9857/articles/01-pharmocean-magiia-magniia/video/experiments",
        "Classic experiment root",
    )
    actual_experiment_ids = {path.name for path in experiment_root.iterdir() if path.is_dir()}
    if actual_experiment_ids != set(CLASSIC_EXPERIMENT_MATRIX):
        raise ReviewDataError(
            "Classic experiment allowlist differs from artifact directories: "
            f"{sorted(actual_experiment_ids)!r}"
        )
    experiment_items = []
    experiment_source_paths: list[Path] = []
    for experiment_id, successful_models in CLASSIC_EXPERIMENT_MATRIX.items():
        experiment_dir = experiment_root / experiment_id
        experiment_path = experiment_dir / "experiment.json"
        experiment_document = require_mapping(
            read_json(experiment_path, f"{experiment_id} manifest"), f"{experiment_id} manifest"
        )
        if experiment_document.get("experiment_id") != experiment_id:
            raise ReviewDataError(f"{experiment_id} manifest identity differs")
        experiment_source_paths.append(experiment_path)
        expected_models = set(successful_models) | {
            model_id
            for failed_experiment, model_id in CLASSIC_EXPECTED_FAILURES
            if failed_experiment == experiment_id
        }
        actual_models = {
            model_id
            for model_id, directory_name in MODEL_DIRECTORY_NAMES.items()
            if (experiment_dir / directory_name).is_dir()
        }
        if actual_models != expected_models:
            raise ReviewDataError(f"{experiment_id} model directory coverage differs")

        for model_id in EXPECTED_MODELS:
            if model_id not in expected_models:
                continue
            model_dir = experiment_dir / MODEL_DIRECTORY_NAMES[model_id]
            prompt_path = model_dir / "02.prompt.json"
            run_path = model_dir / "02.run.json"
            video_path = model_dir / "02.mp4"
            experiment_source_paths.extend((prompt_path, run_path))
            run = require_mapping(read_json(run_path, f"{experiment_id} {model_id} run"), "experiment run")
            if (experiment_id, model_id) in CLASSIC_EXPECTED_FAILURES:
                if run.get("status") != "failed" or not isinstance(run.get("error"), str) or video_path.exists():
                    raise ReviewDataError(f"{experiment_id} {model_id} expected failure state differs")
                continue
            if not video_path.is_file():
                raise ReviewDataError(f"{experiment_id} {model_id} successful video is missing")
            experiment_source_paths.append(video_path)
            item_id = f"promopages-9856-classic-{experiment_id}-{MODEL_DIRECTORY_NAMES[model_id]}"
            item = build_classic_item(
                root,
                item_id,
                prompt_path,
                run_path,
                video_path,
                samples["01-portrait-hands"],
                "clipmaker-classic-experiments",
                "succeeded",
                experiment_document=experiment_document,
            )
            if item["model"]["id"] != model_id:
                raise ReviewDataError(f"{item_id} model differs from its experiment directory")
            experiment_items.append(item)
    if len(experiment_items) != 12:
        raise ReviewDataError(f"Classic experiment cohort must contain 12 videos, got {len(experiment_items)}")

    items = current_items + previous_items + classic_main_items + experiment_items
    if len(items) != 57 or len({item["id"] for item in items}) != 57:
        raise ReviewDataError("mixed review dataset must contain 57 unique items")
    video_hashes = [item["video"]["sha256"] for item in items]
    if len(set(video_hashes)) != len(video_hashes):
        raise ReviewDataError("mixed review dataset contains duplicate video payloads")

    for item in items:
        item["review_basis_sha256"] = review_basis_sha256(item)

    data_sha256 = stable_sha256(items)
    sources = [
        {
            "id": "clipmaker-lite-current",
            "review_group_id": "clipmaker-lite-current",
            "kind": "batch_manifest",
            "ticket": current_manifest.get("ticket"),
            "batch_id": batch_id,
            "manifest_path": workspace_relative(root, current_manifest_path),
            "manifest_sha256": sha256_file(current_manifest_path),
            "manifest_updated_at": current_manifest.get("updated_at"),
            "item_count": len(current_items),
        },
        {
            "id": "clipmaker-lite-previous",
            "review_group_id": "clipmaker-lite-previous",
            "kind": "generation_manifest",
            "ticket": previous_manifest.get("ticket"),
            "batch_id": None,
            "manifest_path": workspace_relative(root, previous_manifest_path),
            "manifest_sha256": sha256_file(previous_manifest_path),
            "manifest_updated_at": previous_manifest.get("updated_at"),
            "item_count": len(previous_items),
            "native_item_count": 10,
            "cross_model_control_item_count": 5,
        },
        {
            "id": "clipmaker-classic-main",
            "review_group_id": "clipmaker-classic-main",
            "kind": "generation_manifest",
            "ticket": classic_manifest.get("ticket"),
            "batch_id": None,
            "manifest_path": workspace_relative(root, classic_manifest_path),
            "manifest_sha256": sha256_file(classic_manifest_path),
            "manifest_updated_at": classic_manifest.get("updated_at"),
            "item_count": len(classic_main_items),
            "cross_model_transfer_item_count": sum(
                not item["prompt"]["native_for_generation_model"]
                for item in classic_main_items
            ),
        },
        {
            "id": "clipmaker-classic-experiments",
            "review_group_id": "clipmaker-classic-experiments",
            "kind": "explicit_artifact_allowlist",
            "ticket": "PROMOPAGES-9856",
            "batch_id": None,
            "artifact_root": workspace_relative(root, experiment_root),
            "artifact_index_sha256": artifact_index_sha256(root, experiment_source_paths),
            "experiment_ids": list(CLASSIC_EXPERIMENT_MATRIX),
            "item_count": len(experiment_items),
            "excluded_failed_item_count": len(CLASSIC_EXPECTED_FAILURES),
        },
        {
            "id": "sample-catalog",
            "review_group_id": None,
            "kind": "sample_manifest",
            "ticket": None,
            "batch_id": None,
            "manifest_path": workspace_relative(root, samples_path),
            "manifest_sha256": sha256_file(samples_path),
            "manifest_updated_at": None,
            "item_count": len(samples),
        },
    ]
    return {
        "schema_version": 2,
        "dataset_id": f"promopages-9897-mixed@{data_sha256[:12]}",
        "supersedes_dataset_ids": list(SUPERSEDED_DATASET_IDS),
        "review_ticket": REVIEW_TICKET,
        "data_sha256": data_sha256,
        "sources": sources,
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
