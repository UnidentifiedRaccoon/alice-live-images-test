#!/usr/bin/env python3
"""Build the exact static payload published from the gh-pages branch.

The repository is larger than the GitHub Pages 1 GB published-site limit.  This
builder follows only runtime references used by the five demo screens and
copies those files into an isolated directory while preserving their paths.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MAX_SITE_BYTES = 950_000_000
MAX_FILE_BYTES = 100_000_000
PROMOPAGES_10060_MODELS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
PROMOPAGES_10060_ARTICLE_NUMBERS = (
    "01",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
)
PROMOPAGES_10060_ARTICLE_COUNT = 13
PROMOPAGES_10060_IMAGE_COUNT = 92
PROMOPAGES_10060_OUTPUT_COUNT = 276
PROMOPAGES_10060_MEDIA_STATUSES = {"succeeded", "verification-failed"}
PROMOPAGES_10060_FILTERED_STATUS = "provider-filtered"
PROMOPAGES_10060_UNAVAILABLE_STATUS = "provider-unavailable"
PROMOPAGES_10060_AMBIGUOUS_RETRY_SELECTION = "ambiguous-submit-retry-v1"
PROMOPAGES_10060_AMBIGUOUS_RETRY_EXHAUSTED_SELECTION = (
    "ambiguous-submit-retry-v1-exhausted"
)
PROMOPAGES_10060_NORMALIZED_RETRY_SELECTION = "normalized-input-retry-v1"
PROMOPAGES_10060_NORMALIZED_RETRY_EXHAUSTED_SELECTION = (
    "normalized-input-retry-v1-exhausted"
)
MAX_PROVIDER_SOURCE_BYTES = 20 * 1024 * 1024

STATIC_FILES = (
    ".nojekyll",
    "index.html",
    "styles.css",
    "app.js",
    "shared.css",
    "generated-gallery.html",
    "generated-gallery.css",
    "generated-gallery-data.js",
    "generated-gallery.js",
    "model-comparison-5s/index.html",
    "model-comparison-5s/styles.css",
    "model-comparison-5s/comparison-data.js",
    "model-comparison-5s/app.js",
    "model-comparison-5s/favicon.svg",
    "manual-review/index.html",
    "manual-review/styles.css",
    "manual-review/review-core.js",
    "manual-review/review-data.js",
    "manual-review/app.js",
    "clipmaker-lite/index.html",
    "clipmaker-lite/styles.css",
    "clipmaker-lite/app.js",
    "clipmaker-lite-test/manifest.json",
    "clipmaker-lite-test/promopages-9930-manifest.json",
    "clipmaker-lite-test/case-21-manifest.json",
    "clipmaker-lite-test/promopages-10060-manifest.json",
)

STATIC_TREES = (
    "videos",
    "webp",
    "model-comparison-5s/fonts",
    "model-comparison-5s/input",
    "model-comparison-5s/final",
)


def _safe_relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected a non-empty relative path, got {value!r}")

    posix_path = PurePosixPath(value)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise ValueError(f"Unsafe site path: {value!r}")
    if any(part in {"", "."} for part in posix_path.parts):
        raise ValueError(f"Non-canonical site path: {value!r}")

    return Path(*posix_path.parts)


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_provider_filtered_attempt(
    attempt: Any,
    *,
    label: str,
    require_inactive: bool = False,
) -> dict[str, Any]:
    if not isinstance(attempt, dict):
        raise ValueError(f"{label} provider-filtered attempt audit is missing")
    for field in (
        "provider_run_id",
        "provider_job_id",
        "submitted_at",
        "completed_at",
        "error",
        "run_path",
        "prompt_path",
    ):
        if not isinstance(attempt.get(field), str) or not attempt[field].strip():
            raise ValueError(f"{label} provider-filtered audit is missing {field}")
    if attempt.get("status") != "provider-failed" or "filter" not in attempt[
        "error"
    ].lower():
        raise ValueError(
            f"{label} provider-filtered attempt is not terminal content-filtered"
        )
    for field in ("run_sha256", "prompt_sha256", "request_sha256"):
        if not _is_sha256(attempt.get(field)):
            raise ValueError(
                f"{label} provider-filtered audit has invalid {field}"
            )
    if require_inactive and attempt.get("provider_may_be_active") is not False:
        raise ValueError(
            f"{label} provider-filtered retry is not confirmed terminal"
        )
    return attempt


def _validate_provider_filtered_output(output: dict[str, Any], *, label: str) -> None:
    if (
        output.get("status") != PROMOPAGES_10060_FILTERED_STATUS
        or output.get("recorded_status") != "provider-failed"
        or output.get("selected_attempt") != "terminal-retry-v1-exhausted"
        or output.get("video_path") is not None
        or output.get("media") is not None
        or output.get("contract_check") is not None
        or not isinstance(output.get("error"), str)
        or not output["error"].strip()
        or "filter" not in output["error"].lower()
    ):
        raise ValueError(f"{label} has an invalid provider-filtered terminal state")
    retry = output.get("retry")
    if (
        not isinstance(retry, dict)
        or retry.get("retry_number") != 1
        or retry.get("exhausted") is not True
        or not isinstance(retry.get("namespace"), str)
        or not retry["namespace"].strip()
        or retry.get("envelope_path") != f"{retry['namespace']}/retry.json"
    ):
        raise ValueError(f"{label} is missing immutable retry-v1 audit")
    primary = _validate_provider_filtered_attempt(
        retry.get("primary_attempt"), label=f"{label} primary"
    )
    retry_attempt = _validate_provider_filtered_attempt(
        retry.get("retry_attempt"),
        label=f"{label} retry-v1",
        require_inactive=True,
    )
    if (
        output.get("provider_run_id") != retry_attempt["provider_run_id"]
        or output.get("error") != retry_attempt["error"]
        or primary["provider_run_id"] == retry_attempt["provider_run_id"]
        or primary["provider_job_id"] == retry_attempt["provider_job_id"]
        or primary["request_sha256"] != retry_attempt["request_sha256"]
    ):
        raise ValueError(
            f"{label} provider-filtered primary/retry audit does not match output"
        )


def _validate_ambiguous_submit_retry(
    output: dict[str, Any],
    *,
    label: str,
    exhausted: bool,
) -> None:
    retry = output.get("retry")
    if (
        not isinstance(retry, dict)
        or retry.get("retry_kind") != "ambiguous-submit"
        or retry.get("retry_number") != 1
        or retry.get("exhausted") is not exhausted
        or retry.get("primary_outcome_unknown") is not True
        or not isinstance(retry.get("namespace"), str)
        or not retry["namespace"].strip()
        or retry.get("envelope_path") != f"{retry['namespace']}/retry.json"
        or not _is_sha256(retry.get("envelope_sha256"))
    ):
        raise ValueError(f"{label} ambiguous-submit retry audit is invalid")

    primary = retry.get("primary_attempt")
    if (
        not isinstance(primary, dict)
        or primary.get("status") != "submit-unknown"
        or primary.get("recorded_status") not in {"submitting", "submit-unknown"}
        or primary.get("outcome") != "unknown"
        or primary.get("outcome_unknown") is not True
        or primary.get("provider_may_be_active") is not True
        or primary.get("provider_job_id") is not None
        or primary.get("submitted_at") is not None
        or primary.get("completed_at") is not None
        or not isinstance(primary.get("ambiguity_reason"), str)
        or not primary["ambiguity_reason"].strip()
        or (
            primary.get("error") is not None
            and (
                not isinstance(primary["error"], str)
                or not primary["error"].strip()
            )
        )
    ):
        raise ValueError(f"{label} primary provider outcome is not strictly unknown")

    retry_attempt = retry.get("retry_attempt")
    if (
        not isinstance(retry_attempt, dict)
        or not isinstance(retry_attempt.get("provider_job_id"), str)
        or not retry_attempt["provider_job_id"].strip()
        or retry_attempt.get("status") != output.get("recorded_status")
        or retry_attempt.get("provider_may_be_active") is not False
        or not isinstance(retry_attempt.get("submitted_at"), str)
        or not retry_attempt["submitted_at"].strip()
        or not isinstance(retry_attempt.get("completed_at"), str)
        or not retry_attempt["completed_at"].strip()
        or retry_attempt.get("error") != output.get("error")
    ):
        raise ValueError(f"{label} retry-v1 is not a terminal selected attempt")

    for attempt_name, attempt in (("primary", primary), ("retry-v1", retry_attempt)):
        for field in ("provider_run_id", "run_path", "prompt_path"):
            if not isinstance(attempt.get(field), str) or not attempt[field].strip():
                raise ValueError(f"{label} {attempt_name} audit is missing {field}")
            if field.endswith("_path"):
                _safe_relative_path(attempt[field])
        for field in ("run_sha256", "prompt_sha256", "request_sha256"):
            if not _is_sha256(attempt.get(field)):
                raise ValueError(
                    f"{label} {attempt_name} audit has invalid {field}"
                )

    if (
        output.get("provider_run_id") != retry_attempt["provider_run_id"]
        or primary["provider_run_id"] == retry_attempt["provider_run_id"]
        or primary["request_sha256"] != retry_attempt["request_sha256"]
    ):
        raise ValueError(f"{label} ambiguous primary/retry binding differs")

    expected_selection = (
        PROMOPAGES_10060_AMBIGUOUS_RETRY_EXHAUSTED_SELECTION
        if exhausted
        else PROMOPAGES_10060_AMBIGUOUS_RETRY_SELECTION
    )
    if output.get("selected_attempt") != expected_selection:
        raise ValueError(f"{label} ambiguous retry selected_attempt is invalid")
    if exhausted:
        if (
            output.get("status") != PROMOPAGES_10060_UNAVAILABLE_STATUS
            or output.get("recorded_status") != "provider-failed"
            or not isinstance(output.get("error"), str)
            or not output["error"].strip()
        ):
            raise ValueError(f"{label} exhausted ambiguous retry identity is invalid")
    elif output.get("status") not in PROMOPAGES_10060_MEDIA_STATUSES:
        raise ValueError(f"{label} successful ambiguous retry has no accepted media status")


def _validate_provider_unavailable_output(
    output: dict[str, Any], *, label: str
) -> None:
    if (
        output.get("video_path") is not None
        or output.get("media") is not None
        or output.get("contract_check") is not None
    ):
        raise ValueError(f"{label} provider-unavailable output must not contain media")
    _validate_ambiguous_submit_retry(output, label=label, exhausted=True)


def _validate_normalized_input_retry(
    output: dict[str, Any],
    image: dict[str, Any],
    *,
    label: str,
    exhausted: bool,
) -> None:
    retry = output.get("retry")
    if (
        not isinstance(retry, dict)
        or retry.get("retry_kind") != "normalized-input"
        or retry.get("retry_number") != 1
        or retry.get("exhausted") is not exhausted
        or not isinstance(retry.get("namespace"), str)
        or not retry["namespace"].strip()
        or retry.get("envelope_path") != f"{retry['namespace']}/retry.json"
        or not _is_sha256(retry.get("envelope_sha256"))
    ):
        raise ValueError(f"{label} normalized-input retry audit is invalid")
    if (
        output.get("article_slug") != "12-dream-island-7-fishek"
        or output.get("image_id") != "08"
        or output.get("model_id") not in {"alibaba/wan-2.2", "alibaba/wan-2.7"}
    ):
        raise ValueError(f"{label} is not an eligible normalized-input output")

    transform = retry.get("source_transform")
    original = transform.get("original") if isinstance(transform, dict) else None
    normalized = transform.get("normalized") if isinstance(transform, dict) else None
    delta = transform.get("request_delta") if isinstance(transform, dict) else None
    if (
        not isinstance(transform, dict)
        or transform.get("strategy") != "frozen-page-variant"
        or not isinstance(original, dict)
        or not isinstance(normalized, dict)
        or not isinstance(delta, dict)
    ):
        raise ValueError(f"{label} normalized-input source_transform is invalid")
    if (
        not isinstance(original.get("url"), str)
        or not original["url"].startswith("https://")
        or original.get("path") != output.get("source_path")
        or original.get("path") != image.get("source_path")
        or not _is_sha256(original.get("sha256"))
        or original.get("sha256") != image.get("sha256")
        or not isinstance(original.get("bytes"), int)
        or isinstance(original["bytes"], bool)
        or original["bytes"] <= MAX_PROVIDER_SOURCE_BYTES
        or not isinstance(original.get("width"), int)
        or isinstance(original["width"], bool)
        or original["width"] < 1
        or original["width"] != image.get("width")
        or not isinstance(original.get("height"), int)
        or isinstance(original["height"], bool)
        or original["height"] < 1
        or original["height"] != image.get("height")
        or (
            image.get("orig_url") is not None
            and image.get("orig_url") != original.get("url")
        )
    ):
        raise ValueError(f"{label} original source audit differs from logical source")
    if (
        not isinstance(normalized.get("url"), str)
        or not normalized["url"].startswith("https://avatars.mds.yandex.net/")
        or not normalized["url"].endswith("/scale_1200")
        or normalized["url"] == original["url"]
        or not _is_sha256(normalized.get("sha256"))
        or normalized["sha256"] == original["sha256"]
        or not isinstance(normalized.get("bytes"), int)
        or isinstance(normalized["bytes"], bool)
        or normalized["bytes"] < 1
        or normalized["bytes"] > MAX_PROVIDER_SOURCE_BYTES
        or normalized["bytes"] >= original["bytes"]
        or not isinstance(normalized.get("width"), int)
        or isinstance(normalized["width"], bool)
        or normalized["width"] < 1
        or normalized["width"] > original["width"]
        or not isinstance(normalized.get("height"), int)
        or isinstance(normalized["height"], bool)
        or normalized["height"] < 1
        or normalized["height"] > original["height"]
        or (
            normalized["width"] == original["width"]
            and normalized["height"] == original["height"]
        )
        or not isinstance(normalized.get("metadata_path"), str)
        or not normalized["metadata_path"].strip()
        or not _is_sha256(normalized.get("metadata_sha256"))
    ):
        raise ValueError(f"{label} normalized source audit is invalid or exceeds 20 MiB")
    _safe_relative_path(original["path"])
    _safe_relative_path(normalized["metadata_path"])
    _safe_relative_path(retry["namespace"])
    _safe_relative_path(retry["envelope_path"])
    expected_pointer = (
        "/input/image"
        if output["model_id"] == "alibaba/wan-2.2"
        else "/frame_images/0/image_url/url"
    )
    if (
        delta.get("json_pointer") != expected_pointer
        or delta.get("from") != original["url"]
        or delta.get("to") != normalized["url"]
        or delta.get("changed_leaf_count") != 1
        or set(delta) != {"json_pointer", "from", "to", "changed_leaf_count"}
    ):
        raise ValueError(f"{label} request delta is not the single allowed image URL")

    primary = retry.get("primary_attempt")
    retry_attempt = retry.get("retry_attempt")
    if (
        not isinstance(primary, dict)
        or primary.get("status") != "provider-failed"
        or primary.get("provider_may_be_active") is not False
        or not isinstance(primary.get("provider_job_id"), str)
        or not primary["provider_job_id"].strip()
        or not isinstance(primary.get("error"), str)
        or not primary["error"].strip()
    ):
        raise ValueError(f"{label} normalized-input primary failure audit is invalid")
    if output["model_id"] == "alibaba/wan-2.2":
        if (
            primary.get("recorded_status") != "submit-unknown"
            or primary.get("recorded_provider_may_be_active") is not True
            or primary.get("submitted_at") is not None
            or primary.get("completed_at") is not None
            or any(
                not isinstance(primary.get(field), str) or not primary[field].strip()
                for field in (
                    "provider_submit_time",
                    "provider_scheduled_time",
                    "provider_end_time",
                )
            )
        ):
            raise ValueError(f"{label} Wan 2.2 nested terminal evidence is invalid")
    elif (
        primary.get("recorded_status") != "provider-failed"
        or primary.get("recorded_provider_may_be_active") is not False
        or not isinstance(primary.get("submitted_at"), str)
        or not primary["submitted_at"].strip()
        or not isinstance(primary.get("completed_at"), str)
        or not primary["completed_at"].strip()
    ):
        raise ValueError(f"{label} Wan 2.7 primary terminal evidence is invalid")

    if (
        not isinstance(retry_attempt, dict)
        or retry_attempt.get("status") != output.get("recorded_status")
        or retry_attempt.get("provider_may_be_active") is not False
        or not isinstance(retry_attempt.get("provider_job_id"), str)
        or not retry_attempt["provider_job_id"].strip()
        or not isinstance(retry_attempt.get("submitted_at"), str)
        or not retry_attempt["submitted_at"].strip()
        or not isinstance(retry_attempt.get("completed_at"), str)
        or not retry_attempt["completed_at"].strip()
        or retry_attempt.get("error") != output.get("error")
    ):
        raise ValueError(f"{label} normalized-input retry-v1 is not terminal")
    for attempt_name, attempt in (("primary", primary), ("retry-v1", retry_attempt)):
        for field in ("provider_run_id", "run_path", "prompt_path"):
            if not isinstance(attempt.get(field), str) or not attempt[field].strip():
                raise ValueError(f"{label} {attempt_name} audit is missing {field}")
            if field.endswith("_path"):
                _safe_relative_path(attempt[field])
        for field in ("run_sha256", "prompt_sha256", "request_sha256"):
            if not _is_sha256(attempt.get(field)):
                raise ValueError(f"{label} {attempt_name} audit has invalid {field}")
    if (
        output.get("provider_run_id") != retry_attempt["provider_run_id"]
        or primary["provider_run_id"] == retry_attempt["provider_run_id"]
        or primary["request_sha256"] == retry_attempt["request_sha256"]
    ):
        raise ValueError(f"{label} normalized retry identity/request binding is invalid")

    expected_selection = (
        PROMOPAGES_10060_NORMALIZED_RETRY_EXHAUSTED_SELECTION
        if exhausted
        else PROMOPAGES_10060_NORMALIZED_RETRY_SELECTION
    )
    if output.get("selected_attempt") != expected_selection:
        raise ValueError(f"{label} normalized retry selected_attempt is invalid")
    if exhausted:
        if (
            output.get("status") != PROMOPAGES_10060_UNAVAILABLE_STATUS
            or output.get("recorded_status") != "provider-failed"
            or not isinstance(output.get("error"), str)
            or not output["error"].strip()
        ):
            raise ValueError(f"{label} exhausted normalized retry identity is invalid")
    elif output.get("status") not in PROMOPAGES_10060_MEDIA_STATUSES:
        raise ValueError(f"{label} successful normalized retry has no media status")


def _validate_normalized_input_unavailable_output(
    output: dict[str, Any], image: dict[str, Any], *, label: str
) -> None:
    if (
        output.get("video_path") is not None
        or output.get("media") is not None
        or output.get("contract_check") is not None
    ):
        raise ValueError(f"{label} provider-unavailable normalized retry has media")
    _validate_normalized_input_retry(
        output, image, label=label, exhausted=True
    )


def _load_js_assignment(path: Path, variable: str) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    prefix = f"window.{variable} = "
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError(f"Unexpected JavaScript assignment format: {path}")
    return json.loads(text[len(prefix) : -1])


def _tree_files(root: Path, relative_tree: str) -> Iterable[Path]:
    tree = root / _safe_relative_path(relative_tree)
    if not tree.is_dir():
        raise FileNotFoundError(tree)
    for path in tree.rglob("*"):
        if path.is_file():
            yield path.relative_to(root)


def collect_site_paths(root: Path = ROOT) -> tuple[Path, ...]:
    root = root.resolve()
    relative_paths = {_safe_relative_path(path) for path in STATIC_FILES}

    for tree in STATIC_TREES:
        relative_paths.update(_tree_files(root, tree))

    gallery = _load_js_assignment(
        root / "generated-gallery-data.js", "generatedGalleryData"
    )
    for item in gallery:
        for field in ("sourceImage", "video", "webp"):
            value = item[field]
            if value:
                relative_paths.add(_safe_relative_path(value))

    review = _load_js_assignment(
        root / "manual-review" / "review-data.js", "qualityReviewDataset"
    )
    for item in review["items"]:
        relative_paths.add(_safe_relative_path(item["video"]["path"]))

    remote_repository_paths: set[Path] = set()

    lite_manifest = json.loads(
        (root / "clipmaker-lite-test" / "manifest.json").read_text(encoding="utf-8")
    )
    for article in lite_manifest["articles"]:
        relative_paths.add(
            _safe_relative_path(article["selected_image"]["source_path"])
        )
        outputs = [
            *article["outputs"],
            *article.get("comparison_outputs", []),
        ]
        for output in outputs:
            relative_paths.add(_safe_relative_path(output["video_path"]))
        for output in article.get("external_outputs", []):
            relative_path = _safe_relative_path(output["video_path"])
            if output.get("delivery") == "repository-raw":
                remote_repository_paths.add(relative_path)
            else:
                relative_paths.add(relative_path)

    # The Step 5 client uses stable raw-repository URLs for PROMOPAGES-9930 media.
    # Keep the compact manifest in Pages and validate every referenced repository
    # artifact without copying the extension media into the Pages payload.
    additional_lite_manifest = json.loads(
        (root / "clipmaker-lite-test" / "promopages-9930-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for article in additional_lite_manifest["articles"]:
        for image_record in article["images"]:
            remote_repository_paths.add(
                _safe_relative_path(image_record["image"]["source_path"])
            )
            for output in image_record["outputs"]:
                remote_repository_paths.add(_safe_relative_path(output["video_path"]))

    # Case 21 is an independent one-image sidecar. Its compact JSON is part of
    # the Pages payload, while the source, seven historical videos and every
    # available loop/smooth experiment outputs stay on main and are delivered
    # through raw.githubusercontent.com.
    case_21_manifest = json.loads(
        (root / "clipmaker-lite-test" / "case-21-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for article in case_21_manifest["articles"]:
        for image_record in article["images"]:
            image = image_record["image"]
            if image.get("delivery") != "repository-raw":
                raise ValueError(
                    "Case 21 source image must use repository-raw delivery"
                )
            remote_repository_paths.add(_safe_relative_path(image["source_path"]))
            outputs = [
                *image_record["outputs"],
                *image_record.get("research_outputs", []),
            ]
            for output in outputs:
                if output.get("delivery") != "repository-raw":
                    raise ValueError(
                        "Case 21 outputs must use repository-raw delivery"
                    )
                remote_repository_paths.add(
                    _safe_relative_path(output["video_path"])
                )

    loop_experiment = case_21_manifest.get("loop_experiment")
    if loop_experiment is not None:
        if not isinstance(loop_experiment, dict) or not isinstance(
            loop_experiment.get("outputs"), list
        ):
            raise ValueError("Case 21 loop_experiment must contain an outputs list")
        for output in loop_experiment["outputs"]:
            if not isinstance(output, dict) or output.get("delivery") != "repository-raw":
                raise ValueError(
                    "Case 21 loop outputs must use repository-raw delivery"
                )
            remote_repository_paths.add(
                _safe_relative_path(output.get("video_path"))
            )

    smooth_experiment = case_21_manifest.get("smooth_experiment")
    if smooth_experiment is not None:
        if not isinstance(smooth_experiment, dict) or not isinstance(
            smooth_experiment.get("outputs"), list
        ):
            raise ValueError("Case 21 smooth_experiment must contain an outputs list")
        for output in smooth_experiment["outputs"]:
            if not isinstance(output, dict) or output.get("delivery") != "repository-raw":
                raise ValueError(
                    "Case 21 smooth outputs must use repository-raw delivery"
                )
            remote_repository_paths.add(
                _safe_relative_path(output.get("video_path"))
            )

    # PROMOPAGES-10060 follows the existing extension-sidecar transport: Pages
    # publishes only compact JSON, while every source image and MP4 is checked in
    # the repository and delivered by the Step 5 client through raw GitHub URLs.
    # The delivery field is optional for this canonical sidecar shape; when it is
    # present, any value other than repository-raw is a fail-closed mismatch.
    promopages_10060_path = (
        root / "clipmaker-lite-test" / "promopages-10060-manifest.json"
    )
    if promopages_10060_path.is_file():
        promopages_10060_manifest = json.loads(
            promopages_10060_path.read_text(encoding="utf-8")
        )
        provider_filtered_output_count = promopages_10060_manifest.get(
            "provider_filtered_output_count"
        )
        provider_unavailable_output_count = promopages_10060_manifest.get(
            "provider_unavailable_output_count"
        )
        if (
            promopages_10060_manifest.get("schema_version") != 1
            or promopages_10060_manifest.get("manifest_role")
            != "promopages-10060-all-images"
            or promopages_10060_manifest.get("ticket") != "PROMOPAGES-10060"
            or promopages_10060_manifest.get("agent_id") != "clipmaker-lite"
            or promopages_10060_manifest.get("models")
            != list(PROMOPAGES_10060_MODELS)
            or promopages_10060_manifest.get("article_count")
            != PROMOPAGES_10060_ARTICLE_COUNT
            or promopages_10060_manifest.get("image_count")
            != PROMOPAGES_10060_IMAGE_COUNT
            or promopages_10060_manifest.get("expected_outputs")
            != PROMOPAGES_10060_OUTPUT_COUNT
            or not isinstance(provider_filtered_output_count, int)
            or isinstance(provider_filtered_output_count, bool)
            or provider_filtered_output_count < 0
            or not isinstance(provider_unavailable_output_count, int)
            or isinstance(provider_unavailable_output_count, bool)
            or provider_unavailable_output_count < 0
            or promopages_10060_manifest.get("accepted_output_count")
            != PROMOPAGES_10060_OUTPUT_COUNT
            - provider_filtered_output_count
            - provider_unavailable_output_count
            or promopages_10060_manifest.get("terminal_accounted_output_count")
            != PROMOPAGES_10060_OUTPUT_COUNT
        ):
            raise ValueError("PROMOPAGES-10060 sidecar identity is invalid")
        status_summary = promopages_10060_manifest.get("status_summary")
        acceptance_policy = promopages_10060_manifest.get("acceptance_policy")
        if (
            not isinstance(status_summary, dict)
            or status_summary.get(PROMOPAGES_10060_FILTERED_STATUS)
            != provider_filtered_output_count
            or status_summary.get(PROMOPAGES_10060_UNAVAILABLE_STATUS, 0)
            != provider_unavailable_output_count
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 0
                for count in status_summary.values()
            )
            or sum(status_summary.values()) != PROMOPAGES_10060_OUTPUT_COUNT
            or not isinstance(acceptance_policy, dict)
            or acceptance_policy.get("requires_mp4_and_media") is not True
            or not isinstance(
                acceptance_policy.get("terminal_accounted_without_media"), list
            )
            or set(acceptance_policy["terminal_accounted_without_media"])
            != {
                PROMOPAGES_10060_FILTERED_STATUS,
                PROMOPAGES_10060_UNAVAILABLE_STATUS,
            }
            or len(acceptance_policy["terminal_accounted_without_media"]) != 2
            or acceptance_policy.get(
                "provider_filtered_requires_exhausted_retry_v1"
            )
            is not True
            or acceptance_policy.get(
                "provider_unavailable_requires_ambiguous_submit_retry_v1"
            )
            is not True
            or acceptance_policy.get("provider_unavailable_requires_retry_v1")
            != ["ambiguous-submit", "normalized-input"]
        ):
            raise ValueError(
                "PROMOPAGES-10060 provider-filtered accounting policy is invalid"
            )
        review_articles = promopages_10060_manifest.get("articles")
        if (
            not isinstance(review_articles, list)
            or len(review_articles) != PROMOPAGES_10060_ARTICLE_COUNT
        ):
            raise ValueError(
                "PROMOPAGES-10060 sidecar must contain all 13 available articles"
            )
        unavailable_articles = promopages_10060_manifest.get("unavailable_articles")
        if (
            not isinstance(unavailable_articles, list)
            or len(unavailable_articles) != 1
            or not isinstance(unavailable_articles[0], dict)
            or unavailable_articles[0].get("article_number") != "02"
            or unavailable_articles[0].get("status") != "source-unavailable"
            or not isinstance(unavailable_articles[0].get("error"), str)
            or not unavailable_articles[0]["error"].strip()
        ):
            raise ValueError(
                "PROMOPAGES-10060 sidecar must mark article 02 source-unavailable"
            )
        article_numbers: list[str] = []
        review_source_paths: set[Path] = set()
        review_video_paths: set[Path] = set()
        nested_output_keys: set[tuple[str, str, str]] = set()
        image_count = 0
        output_count = 0
        filtered_output_count = 0
        unavailable_output_count = 0
        normalized_input_retry_output_count = 0
        normalized_input_asset_identity: str | None = None
        for article in review_articles:
            if not isinstance(article, dict):
                raise ValueError("PROMOPAGES-10060 article must be an object")
            article_number = article.get("article_number")
            article_slug = article.get("article_slug")
            article_numbers.append(article_number)
            image_records = article.get("images")
            if (
                not isinstance(article_number, str)
                or not isinstance(article_slug, str)
                or not article_slug
                or not isinstance(image_records, list)
                or not image_records
                or article.get("image_count") != len(image_records)
            ):
                raise ValueError(
                    "PROMOPAGES-10060 article must contain its complete images list"
                )
            image_ids: set[str] = set()
            for image_record in image_records:
                image = image_record.get("image") if isinstance(image_record, dict) else None
                image_id = image.get("image_id") if isinstance(image, dict) else None
                if (
                    not isinstance(image, dict)
                    or not isinstance(image_id, str)
                    or not image_id
                    or image_id in image_ids
                    or image.get("delivery") not in {None, "repository-raw"}
                ):
                    raise ValueError(
                        "PROMOPAGES-10060 source images must use repository-raw delivery"
                    )
                image_ids.add(image_id)
                source_path = _safe_relative_path(image.get("source_path"))
                if source_path in review_source_paths:
                    raise ValueError("PROMOPAGES-10060 source paths must be unique")
                review_source_paths.add(source_path)
                remote_repository_paths.add(source_path)
                outputs = image_record.get("outputs")
                if (
                    not isinstance(outputs, list)
                    or len(outputs) != len(PROMOPAGES_10060_MODELS)
                    or tuple(
                        output.get("model_id")
                        for output in outputs
                        if isinstance(output, dict)
                    )
                    != PROMOPAGES_10060_MODELS
                ):
                    raise ValueError(
                        "PROMOPAGES-10060 image must contain all three model outputs"
                    )
                for output in outputs:
                    if (
                        not isinstance(output, dict)
                        or output.get("article_slug") != article_slug
                        or output.get("image_id") != image_id
                        or output.get("delivery") not in {None, "repository-raw"}
                    ):
                        raise ValueError(
                            "PROMOPAGES-10060 outputs must use repository-raw delivery"
                        )
                    logical_key = (article_slug, image_id, output["model_id"])
                    if logical_key in nested_output_keys:
                        raise ValueError(
                            "PROMOPAGES-10060 logical output keys must be unique"
                        )
                    nested_output_keys.add(logical_key)
                    status = output.get("status")
                    if status == PROMOPAGES_10060_FILTERED_STATUS:
                        _validate_provider_filtered_output(
                            output,
                            label=(
                                "PROMOPAGES-10060/"
                                f"{article_number}/{image_id}/{output['model_id']}"
                            ),
                        )
                        filtered_output_count += 1
                        output_count += 1
                        continue
                    if status == PROMOPAGES_10060_UNAVAILABLE_STATUS:
                        label = (
                            "PROMOPAGES-10060/"
                            f"{article_number}/{image_id}/{output['model_id']}"
                        )
                        retry = output.get("retry")
                        if (
                            isinstance(retry, dict)
                            and retry.get("retry_kind") == "normalized-input"
                        ):
                            _validate_normalized_input_unavailable_output(
                                output, image, label=label
                            )
                            normalized_input_retry_output_count += 1
                        else:
                            _validate_provider_unavailable_output(output, label=label)
                        unavailable_output_count += 1
                        output_count += 1
                    elif status not in PROMOPAGES_10060_MEDIA_STATUSES:
                        raise ValueError(
                            "PROMOPAGES-10060 non-video status is not allowed"
                        )
                    else:
                        video_path = _safe_relative_path(output.get("video_path"))
                        if video_path.suffix.lower() != ".mp4":
                            raise ValueError(
                                "PROMOPAGES-10060 media output must reference an MP4"
                            )
                        if video_path in review_video_paths:
                            raise ValueError("PROMOPAGES-10060 output paths must be unique")
                        retry = output.get("retry")
                        ambiguous_retry_marker = (
                            output.get("selected_attempt")
                            in {
                                PROMOPAGES_10060_AMBIGUOUS_RETRY_SELECTION,
                                PROMOPAGES_10060_AMBIGUOUS_RETRY_EXHAUSTED_SELECTION,
                            }
                            or (
                                isinstance(retry, dict)
                                and retry.get("retry_kind") == "ambiguous-submit"
                            )
                        )
                        if ambiguous_retry_marker:
                            _validate_ambiguous_submit_retry(
                                output,
                                label=(
                                    "PROMOPAGES-10060/"
                                    f"{article_number}/{image_id}/{output['model_id']}"
                                ),
                                exhausted=False,
                            )
                        normalized_retry_marker = (
                            output.get("selected_attempt")
                            in {
                                PROMOPAGES_10060_NORMALIZED_RETRY_SELECTION,
                                PROMOPAGES_10060_NORMALIZED_RETRY_EXHAUSTED_SELECTION,
                            }
                            or (
                                isinstance(retry, dict)
                                and retry.get("retry_kind") == "normalized-input"
                            )
                        )
                        if normalized_retry_marker:
                            _validate_normalized_input_retry(
                                output,
                                image,
                                label=(
                                    "PROMOPAGES-10060/"
                                    f"{article_number}/{image_id}/{output['model_id']}"
                                ),
                                exhausted=False,
                            )
                            normalized_input_retry_output_count += 1
                        review_video_paths.add(video_path)
                        remote_repository_paths.add(video_path)
                        output_count += 1
                    if (
                        isinstance(output.get("retry"), dict)
                        and output["retry"].get("retry_kind") == "normalized-input"
                    ):
                        transform = output["retry"]["source_transform"]
                        asset_identity = json.dumps(
                            {
                                "strategy": transform["strategy"],
                                "original": transform["original"],
                                "normalized": transform["normalized"],
                            },
                            sort_keys=True,
                        )
                        if (
                            normalized_input_asset_identity is not None
                            and normalized_input_asset_identity != asset_identity
                        ):
                            raise ValueError(
                                "PROMOPAGES-10060 normalized retries use different frozen assets"
                            )
                        normalized_input_asset_identity = asset_identity
                image_count += 1
        if tuple(article_numbers) != PROMOPAGES_10060_ARTICLE_NUMBERS:
            raise ValueError(
                "PROMOPAGES-10060 sidecar must contain articles 01 and 03 through 14"
            )
        if (
            image_count != PROMOPAGES_10060_IMAGE_COUNT
            or output_count != PROMOPAGES_10060_OUTPUT_COUNT
            or filtered_output_count != provider_filtered_output_count
            or unavailable_output_count != provider_unavailable_output_count
        ):
            raise ValueError(
                "PROMOPAGES-10060 sidecar must contain 92 images, 276 logical "
                "outputs and exactly its audited no-media outputs"
            )
        if normalized_input_retry_output_count:
            cost = promopages_10060_manifest.get("cost")
            generation_policy = promopages_10060_manifest.get("generation_policy")
            normalized_policy = (
                generation_policy.get("normalized_input_retry")
                if isinstance(generation_policy, dict)
                else None
            )
            if (
                not isinstance(cost, dict)
                or cost.get("normalized_input_retry_version") != 1
                or not isinstance(
                    cost.get("normalized_input_retry_accounting_cost_usd"),
                    (int, float),
                )
                or isinstance(
                    cost.get("normalized_input_retry_accounting_cost_usd"), bool
                )
                or cost["normalized_input_retry_accounting_cost_usd"] <= 0
                or cost.get("normalized_input_retry_reservations")
                != normalized_input_retry_output_count
            ):
                raise ValueError(
                    "PROMOPAGES-10060 normalized-input cost accounting is invalid"
                )
            if (
                not isinstance(normalized_policy, dict)
                or normalized_policy.get("version") != 1
                or not isinstance(normalized_policy.get("namespace"), str)
                or not normalized_policy["namespace"].strip()
                or not isinstance(
                    normalized_policy.get("shared_asset_namespace"), str
                )
                or not normalized_policy["shared_asset_namespace"].strip()
                or normalized_policy.get("eligible_source")
                != {
                    "article_slug": "12-dream-island-7-fishek",
                    "image_id": "08",
                }
                or normalized_policy.get("models")
                != ["alibaba/wan-2.2", "alibaba/wan-2.7"]
                or normalized_policy.get("explicit_operator_command_required")
                is not True
                or normalized_policy.get(
                    "maximum_new_paid_submissions_per_eligible_output"
                )
                != 1
                or normalized_policy.get("retry2_forbidden") is not True
                or normalized_policy.get("automatic_paid_retries") is not False
                or normalized_policy.get("fallback") is not False
                or normalized_policy.get("primary_receipts_immutable") is not True
                or normalized_policy.get("request_delta_only_image_pointer")
                is not True
            ):
                raise ValueError(
                    "PROMOPAGES-10060 normalized-input generation policy is invalid"
                )
            for article in review_articles:
                for image_record in article["images"]:
                    for output in image_record["outputs"]:
                        retry = output.get("retry")
                        if (
                            not isinstance(retry, dict)
                            or retry.get("retry_kind") != "normalized-input"
                        ):
                            continue
                        metadata_path = retry["source_transform"]["normalized"][
                            "metadata_path"
                        ]
                        if (
                            not retry["namespace"].startswith(
                                f"{normalized_policy['namespace']}/"
                            )
                            or not metadata_path.startswith(
                                f"{normalized_policy['shared_asset_namespace']}/"
                            )
                        ):
                            raise ValueError(
                                "PROMOPAGES-10060 normalized-input retry is outside "
                                "the allowed namespaces"
                            )
        flat_outputs = promopages_10060_manifest.get("outputs")
        if not isinstance(flat_outputs, list) or len(flat_outputs) != output_count:
            raise ValueError(
                "PROMOPAGES-10060 flat outputs must match nested outputs"
            )
        flat_output_keys = {
            (
                output.get("article_slug"),
                output.get("image_id"),
                output.get("model_id"),
            )
            for output in flat_outputs
            if isinstance(output, dict)
        }
        if flat_output_keys != nested_output_keys:
            raise ValueError(
                "PROMOPAGES-10060 flat outputs must match nested outputs"
            )
        nested_by_key = {
            (
                output["article_slug"],
                output["image_id"],
                output["model_id"],
            ): output
            for article in review_articles
            for image_record in article["images"]
            for output in image_record["outputs"]
        }
        for flat_output in flat_outputs:
            if not isinstance(flat_output, dict):
                raise ValueError(
                    "PROMOPAGES-10060 flat outputs must contain objects"
                )
            key = (
                flat_output.get("article_slug"),
                flat_output.get("image_id"),
                flat_output.get("model_id"),
            )
            nested_output = nested_by_key.get(key)
            if (
                nested_output is None
                or flat_output.get("status") != nested_output.get("status")
                or flat_output.get("video_path") != nested_output.get("video_path")
                or flat_output.get("provider_run_id")
                != nested_output.get("provider_run_id")
                or flat_output.get("recorded_status")
                != nested_output.get("recorded_status")
                or flat_output.get("selected_attempt")
                != nested_output.get("selected_attempt")
                or flat_output.get("error") != nested_output.get("error")
                or flat_output.get("media") != nested_output.get("media")
                or flat_output.get("contract_check")
                != nested_output.get("contract_check")
                or flat_output.get("retry") != nested_output.get("retry")
            ):
                raise ValueError(
                    "PROMOPAGES-10060 flat output status/audit differs from nested output"
                )

    for relative_path in remote_repository_paths:
        source = root / relative_path
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(
                f"Missing regular raw-repository media file: {relative_path}"
            )
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(
                f"Raw-repository media exceeds GitHub's 100 MB file limit: {relative_path}"
            )

    for relative_path in relative_paths:
        source = root / relative_path
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(f"Missing regular site file: {relative_path}")
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(
                f"Site file exceeds GitHub's 100 MB file limit: {relative_path}"
            )

    return tuple(sorted(relative_paths, key=lambda path: path.as_posix()))


def site_size(root: Path, relative_paths: Iterable[Path]) -> int:
    return sum((root / path).stat().st_size for path in relative_paths)


def build_site(root: Path, output: Path, *, hardlink: bool = False) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    if output == root:
        raise ValueError("Output directory must not be the repository root")
    if output.exists():
        raise FileExistsError(f"Output path already exists: {output}")

    paths = collect_site_paths(root)
    total_bytes = site_size(root, paths)
    if total_bytes > MAX_SITE_BYTES:
        raise ValueError(
            f"Pages payload is {total_bytes:,} bytes; limit is {MAX_SITE_BYTES:,} bytes"
        )

    output.mkdir(parents=True)
    for relative_path in paths:
        source = root / relative_path
        destination = output / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if hardlink:
            os.link(source, destination)
        else:
            shutil.copy2(source, destination)

    return {
        "output": str(output),
        "file_count": len(paths),
        "total_bytes": total_bytes,
        "max_site_bytes": MAX_SITE_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--hardlink",
        action="store_true",
        help="Hard-link files instead of copying them (output must share a filesystem).",
    )
    args = parser.parse_args()

    result = build_site(args.root, args.output, hardlink=args.hardlink)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
