import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import build_github_pages_site as pages
from scripts import clipmaker_lite_tune_v5_media_overlay as tune_overlay


ROOT = Path(__file__).resolve().parents[1]
ADDITIONAL_MANIFEST_PATH = (
    ROOT / "clipmaker-lite-test" / "promopages-9930-manifest.json"
)
CASE_21_MANIFEST_PATH = ROOT / "clipmaker-lite-test" / "case-21-manifest.json"
PROMOPAGES_10060_MANIFEST_PATH = (
    ROOT / "clipmaker-lite-test" / "promopages-10060-manifest.json"
)
PROMOPAGES_10060_ARTICLE_02_PATH = (
    ROOT / pages.PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH
)
PROMOPAGES_10060_EXTENSION_PATH = (
    ROOT
    / "clipmaker-lite-test"
    / "promopages-10060-campaigns-20260805-v1-manifest.json"
)
PROMOPAGES_10060_CAMPAIGN_20260807_PATH = (
    ROOT / pages.PROMOPAGES_10060_CAMPAIGN_20260807_RELATIVE_PATH
)
PROMOPAGES_10060_S3_DELIVERY_PATH = (
    ROOT / pages.PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH
)
PROMOPAGES_10060_S3_ARTICLES_PATH = (
    ROOT / pages.PROMOPAGES_10060_S3_ARTICLES_RELATIVE_PATH
)
TUNE_MANIFEST_PATH = ROOT / pages.TUNE_MANIFEST_RELATIVE_PATH
PROMOPAGES_10060_IMAGE_COUNTS = (
    ("01", 4),
    ("03", 9),
    ("04", 8),
    ("05", 7),
    ("06", 6),
    ("07", 9),
    ("08", 8),
    ("09", 5),
    ("10", 8),
    ("11", 4),
    ("12", 10),
    ("13", 8),
    ("14", 6),
)
NORMALIZED_RETRY_NAMESPACE = (
    "clipmaker-lite-test/runs/promopages-10060-test/normalized-input-retries-v1"
)
NORMALIZED_ASSET_NAMESPACE = (
    "clipmaker-lite-test/runs/promopages-10060-test/normalized-input-assets-v1"
)
NORMALIZED_ORIGINAL_URL = (
    "https://avatars.mds.yandex.net/get-direct-picture/117225/oversize/orig"
)
NORMALIZED_URL = (
    "https://avatars.mds.yandex.net/get-direct-picture/117225/oversize/scale_1200"
)


def _provider_filtered_output(article_slug, image_id, model_id):
    request_sha = "1" * 64
    namespace = (
        "clipmaker-lite-test/runs/promopages-10060-test/"
        "terminal-provider-retries-v1/filtered-output"
    )
    retry_error = "Video completed with no output; content may have been filtered"
    return {
        "article_slug": article_slug,
        "image_id": image_id,
        "model_id": model_id,
        "provider_run_id": "retry-provider-run",
        "positive_prompt": "Keep the source stable with one subtle movement.",
        "status": "provider-filtered",
        "recorded_status": "provider-failed",
        "selected_attempt": "terminal-retry-v1-exhausted",
        "video_path": None,
        "media": None,
        "contract_check": None,
        "error": retry_error,
        "retry": {
            "retry_number": 1,
            "namespace": namespace,
            "envelope_path": f"{namespace}/retry.json",
            "exhausted": True,
            "primary_attempt": {
                "provider_run_id": "primary-provider-run",
                "provider_job_id": "primary-job",
                "status": "provider-failed",
                "submitted_at": "2026-08-04T23:42:39Z",
                "completed_at": "2026-08-04T23:44:12Z",
                "error": "Video completed with no output; content may have been filtered",
                "run_path": "runs/primary.run.json",
                "run_sha256": "2" * 64,
                "prompt_path": "runs/primary.prompt.json",
                "prompt_sha256": "3" * 64,
                "request_sha256": request_sha,
            },
            "retry_attempt": {
                "provider_run_id": "retry-provider-run",
                "provider_job_id": "retry-job",
                "status": "provider-failed",
                "provider_may_be_active": False,
                "submitted_at": "2026-08-04T23:57:23Z",
                "completed_at": "2026-08-04T23:58:27Z",
                "error": retry_error,
                "run_path": "runs/retry.run.json",
                "run_sha256": "4" * 64,
                "prompt_path": "runs/retry.prompt.json",
                "prompt_sha256": "5" * 64,
                "request_sha256": request_sha,
            },
        },
    }


def _provider_unavailable_output(article_slug, image_id, model_id):
    request_sha = "6" * 64
    namespace = (
        "clipmaker-lite-test/runs/promopages-10060-test/"
        "ambiguous-submit-retries-v1/unavailable-output"
    )
    retry_error = "Provider returned a terminal failure after the explicit retry"
    return {
        "article_slug": article_slug,
        "image_id": image_id,
        "model_id": model_id,
        "provider_run_id": "ambiguous-retry-provider-run",
        "positive_prompt": "Keep the exact source with one restrained movement.",
        "status": "provider-unavailable",
        "recorded_status": "provider-failed",
        "selected_attempt": "ambiguous-submit-retry-v1-exhausted",
        "video_path": None,
        "media": None,
        "contract_check": None,
        "error": retry_error,
        "retry": {
            "retry_kind": "ambiguous-submit",
            "retry_number": 1,
            "namespace": namespace,
            "envelope_path": f"{namespace}/retry.json",
            "envelope_sha256": "7" * 64,
            "exhausted": True,
            "primary_outcome_unknown": True,
            "primary_attempt": {
                "provider_run_id": "ambiguous-primary-provider-run",
                "provider_job_id": None,
                "status": "submit-unknown",
                "recorded_status": "submitting",
                "outcome": "unknown",
                "outcome_unknown": True,
                "ambiguity_reason": (
                    "Synchronous submit may have reached the provider without "
                    "a durable response"
                ),
                "provider_may_be_active": True,
                "submitted_at": None,
                "completed_at": None,
                "error": None,
                "run_path": "runs/ambiguous-primary.run.json",
                "run_sha256": "8" * 64,
                "prompt_path": "runs/ambiguous-primary.prompt.json",
                "prompt_sha256": "9" * 64,
                "request_sha256": request_sha,
            },
            "retry_attempt": {
                "provider_run_id": "ambiguous-retry-provider-run",
                "provider_job_id": "ambiguous-retry-provider-job",
                "status": "provider-failed",
                "provider_may_be_active": False,
                "submitted_at": "2026-08-05T05:10:00Z",
                "completed_at": "2026-08-05T05:12:00Z",
                "error": retry_error,
                "run_path": "runs/ambiguous-retry.run.json",
                "run_sha256": "a" * 64,
                "prompt_path": "runs/ambiguous-retry.prompt.json",
                "prompt_sha256": "b" * 64,
                "request_sha256": request_sha,
            },
        },
    }


def _ambiguous_retry_success_output(article_slug, image_id, model_id, video_path):
    output = _provider_unavailable_output(article_slug, image_id, model_id)
    output.update(
        {
            "status": "succeeded",
            "recorded_status": "succeeded",
            "selected_attempt": "ambiguous-submit-retry-v1",
            "video_path": video_path,
            "media": {
                "width": 1280,
                "height": 720,
                "duration_seconds": 5,
                "bytes": 2048,
                "sha256": hashlib.sha256(video_path.encode()).hexdigest(),
            },
            "contract_check": {"conforms": True, "warnings": []},
            "error": None,
        }
    )
    output["retry"]["exhausted"] = False
    output["retry"]["retry_attempt"].update(
        {"status": "succeeded", "error": None}
    )
    return output


def _normalized_input_retry_output(
    article_slug,
    image,
    model_id,
    *,
    exhausted,
    video_path=None,
):
    model_suffix = "wan22" if model_id == "alibaba/wan-2.2" else "wan27"
    namespace = f"{NORMALIZED_RETRY_NAMESPACE}/{model_suffix}-retry-key"
    retry_error = (
        "Provider returned a terminal failure after normalized input retry"
        if exhausted
        else None
    )
    recorded_status = "provider-failed" if exhausted else "succeeded"
    primary = {
        "provider_run_id": f"{model_suffix}-oversize-primary-run",
        "provider_job_id": f"{model_suffix}-oversize-primary-job",
        "status": "provider-failed",
        "recorded_status": (
            "submit-unknown"
            if model_id == "alibaba/wan-2.2"
            else "provider-failed"
        ),
        "provider_may_be_active": False,
        "recorded_provider_may_be_active": model_id == "alibaba/wan-2.2",
        "submitted_at": (
            None
            if model_id == "alibaba/wan-2.2"
            else "2026-08-05T06:00:00Z"
        ),
        "completed_at": (
            None
            if model_id == "alibaba/wan-2.2"
            else "2026-08-05T06:01:00Z"
        ),
        "error": "File size exceeds maximum allowed size of 20971520 bytes",
        "run_path": f"runs/{model_suffix}-oversize-primary.run.json",
        "run_sha256": "c" * 64,
        "prompt_path": f"runs/{model_suffix}-oversize-primary.prompt.json",
        "prompt_sha256": "d" * 64,
        "request_sha256": "e" * 64,
    }
    if model_id == "alibaba/wan-2.2":
        primary.update(
            {
                "provider_submit_time": "2026-08-05T06:00:00Z",
                "provider_scheduled_time": "2026-08-05T06:00:01Z",
                "provider_end_time": "2026-08-05T06:00:02Z",
            }
        )
    return {
        "article_slug": article_slug,
        "image_id": image["image_id"],
        "source_path": image["source_path"],
        "model_id": model_id,
        "provider_run_id": f"{model_suffix}-normalized-retry-run",
        "positive_prompt": "Keep the exact scene and add restrained movement.",
        "status": "provider-unavailable" if exhausted else "succeeded",
        "recorded_status": recorded_status,
        "selected_attempt": (
            "normalized-input-retry-v1-exhausted"
            if exhausted
            else "normalized-input-retry-v1"
        ),
        "video_path": None if exhausted else video_path,
        "media": (
            None
            if exhausted
            else {
                "width": 1280,
                "height": 720,
                "bytes": 2048,
                "sha256": hashlib.sha256(video_path.encode()).hexdigest(),
            }
        ),
        "contract_check": None if exhausted else {"conforms": True},
        "error": retry_error,
        "retry": {
            "retry_kind": "normalized-input",
            "retry_number": 1,
            "namespace": namespace,
            "envelope_path": f"{namespace}/retry.json",
            "envelope_sha256": "f" * 64,
            "exhausted": exhausted,
            "primary_attempt": primary,
            "retry_attempt": {
                "provider_run_id": f"{model_suffix}-normalized-retry-run",
                "provider_job_id": f"{model_suffix}-normalized-retry-job",
                "status": recorded_status,
                "provider_may_be_active": False,
                "submitted_at": "2026-08-05T06:05:00Z",
                "completed_at": "2026-08-05T06:07:00Z",
                "error": retry_error,
                "run_path": f"runs/{model_suffix}-normalized-retry.run.json",
                "run_sha256": "1" * 64,
                "prompt_path": f"runs/{model_suffix}-normalized-retry.prompt.json",
                "prompt_sha256": "2" * 64,
                "request_sha256": "3" * 64,
            },
            "source_transform": {
                "strategy": "frozen-page-variant",
                "original": {
                    "url": NORMALIZED_ORIGINAL_URL,
                    "path": image["source_path"],
                    "sha256": image["sha256"],
                    "bytes": 23_472_383,
                    "width": image["width"],
                    "height": image["height"],
                },
                "normalized": {
                    "url": NORMALIZED_URL,
                    "sha256": "4" * 64,
                    "bytes": 1_500_000,
                    "width": 1200,
                    "height": 801,
                    "metadata_path": (
                        f"{NORMALIZED_ASSET_NAMESPACE}/shared-asset/asset.json"
                    ),
                    "metadata_sha256": "5" * 64,
                },
                "request_delta": {
                    "json_pointer": (
                        "/input/image"
                        if model_id == "alibaba/wan-2.2"
                        else "/frame_images/0/image_url/url"
                    ),
                    "from": NORMALIZED_ORIGINAL_URL,
                    "to": NORMALIZED_URL,
                    "changed_leaf_count": 1,
                },
            },
        },
    }


def _promopages_10060_fixture(
    first_source_delivery=None, *, include_provider_filtered=False
):
    articles = []
    flat_outputs = []
    source_paths = []
    video_paths = []
    for article_number, image_count in PROMOPAGES_10060_IMAGE_COUNTS:
        article_slug = (
            "12-dream-island-7-fishek"
            if article_number == "12"
            else f"{article_number}-article"
        )
        image_records = []
        for image_number in range(1, image_count + 1):
            image_id = f"{image_number:02d}"
            source_path = f"raw/promopages-10060/{article_number}/{image_id}.jpg"
            image = {
                "image_id": image_id,
                "source_path": source_path,
            }
            if first_source_delivery is not None and not source_paths:
                image["delivery"] = first_source_delivery
            outputs = []
            for model_index, model_id in enumerate(
                pages.PROMOPAGES_10060_MODELS, start=1
            ):
                if (
                    include_provider_filtered
                    and article_number == "07"
                    and image_id == "06"
                    and model_id == "google/veo-3.1-lite"
                ):
                    output = _provider_filtered_output(
                        article_slug, image_id, model_id
                    )
                    outputs.append(output)
                    flat_outputs.append(output.copy())
                    continue
                video_path = (
                    f"raw/promopages-10060/{article_number}/{image_id}-"
                    f"model-{model_index}.mp4"
                )
                output = {
                    "article_slug": article_slug,
                    "image_id": image_id,
                    "model_id": model_id,
                    "status": "succeeded",
                    "video_path": video_path,
                    "media": {
                        "bytes": 2048,
                        "sha256": hashlib.sha256(video_path.encode()).hexdigest(),
                    },
                }
                outputs.append(output)
                flat_outputs.append(output.copy())
                video_paths.append(video_path)
            image_records.append({"image": image, "outputs": outputs})
            source_paths.append(source_path)
        articles.append(
            {
                "article_number": article_number,
                "article_slug": article_slug,
                "image_count": image_count,
                "images": image_records,
            }
        )
    provider_filtered_count = int(include_provider_filtered)
    manifest = {
        "schema_version": 1,
        "manifest_role": "promopages-10060-all-images",
        "ticket": "PROMOPAGES-10060",
        "agent_id": "clipmaker-lite",
        "models": list(pages.PROMOPAGES_10060_MODELS),
        "article_count": 13,
        "image_count": 92,
        "expected_outputs": 276,
        "accepted_output_count": 276 - provider_filtered_count,
        "terminal_accounted_output_count": 276,
        "provider_filtered_output_count": provider_filtered_count,
        "provider_unavailable_output_count": 0,
        "status_summary": {
            "succeeded": 276 - provider_filtered_count,
            "provider-filtered": provider_filtered_count,
            "provider-unavailable": 0,
        },
        "acceptance_policy": {
            "requires_mp4_and_media": True,
            "terminal_accounted_without_media": [
                "provider-filtered",
                "provider-unavailable",
            ],
            "provider_filtered_requires_exhausted_retry_v1": True,
            "provider_unavailable_requires_ambiguous_submit_retry_v1": True,
            "provider_unavailable_requires_retry_v1": [
                "ambiguous-submit",
                "normalized-input",
            ],
        },
        "articles": articles,
        "outputs": flat_outputs,
        "unavailable_articles": [
            {
                "article_number": "02",
                "article_slug": "02-level-rabotaiu-v-level",
                "status": "source-unavailable",
                "error": "Public article is unavailable.",
            }
        ],
    }
    return manifest, source_paths, video_paths


def _promopages_10060_article_02_fixture():
    manifest = json.loads(PROMOPAGES_10060_ARTICLE_02_PATH.read_text(encoding="utf-8"))
    source_paths = [
        record["image"]["source_path"]
        for record in manifest["articles"][0]["images"]
    ]
    video_paths = [
        output["video_path"]
        for record in manifest["articles"][0]["images"]
        for output in record["outputs"]
    ]
    return manifest, source_paths, video_paths


def _materialize_article_02_raw_fixture(root, manifest):
    flat_outputs = {
        (output["article_slug"], output["image_id"], output["model_id"]): output
        for output in manifest["outputs"]
    }
    for record in manifest["articles"][0]["images"]:
        image = record["image"]
        source_bytes = f"article-02-source-{image['image_id']}".encode()
        source_path = root / image["source_path"]
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(source_bytes)
        image["sha256"] = hashlib.sha256(source_bytes).hexdigest()
        record["lite_planning"]["provenance"]["source_image_sha256"] = image[
            "sha256"
        ]
        if image["image_id"] == "01":
            manifest["articles"][0]["selected_image"] = dict(image)
        for output in record["outputs"]:
            video_bytes = (
                f"article-02-video-{image['image_id']}-{output['model_id']}"
            ).encode()
            video_path = root / output["video_path"]
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(video_bytes)
            media = dict(output["media"])
            media.update(
                {
                    "bytes": len(video_bytes),
                    "sha256": hashlib.sha256(video_bytes).hexdigest(),
                }
            )
            output["media"] = media
            flat_outputs[
                (output["article_slug"], output["image_id"], output["model_id"])
            ]["media"] = dict(media)


def _promopages_10060_campaign_extension_fixture():
    article_slug = "15-campaign-6a3d17575c59bd0e6d046aa6"
    image_id = "01"
    source_path = f"raw/promopages-10060/{article_slug}/{image_id}.jpg"
    image = {
        "image_id": image_id,
        "source_path": source_path,
        "manifest_file_path": (
            pages.PROMOPAGES_10060_EXTENSION_MANIFEST_ROOT
            / article_slug
            / f"{image_id}.jpg"
        ).as_posix(),
        "sha256": "c" * 64,
        "width": 1200,
        "height": 800,
    }
    outputs = []
    video_paths = []
    for model_index, model_id in enumerate(
        pages.PROMOPAGES_10060_MODELS, start=1
    ):
        video_path = (
            f"raw/promopages-10060/{article_slug}/{image_id}-model-{model_index}.mp4"
        )
        video_paths.append(video_path)
        outputs.append(
            {
                "article_slug": article_slug,
                "image_id": image_id,
                "model_id": model_id,
                "positive_prompt": "Keep the source stable with restrained motion.",
                "status": "succeeded",
                "video_path": video_path,
                "media": {
                    "width": 1280,
                    "height": 720,
                    "duration_seconds": 5,
                    "bytes": 2048,
                    "sha256": hashlib.sha256(video_path.encode()).hexdigest(),
                },
            }
        )
    article = {
        "article_number": "15",
        "article_slug": article_slug,
        "title": "Campaign article 15",
        "url": "https://example.promo.page/media/campaign-15",
        "context_path": (
            pages.PROMOPAGES_10060_EXTENSION_CONTEXT_ROOT
            / article_slug
            / "content.json"
        ).as_posix(),
        "image_count": 1,
        "images": [
            {
                "image": image,
                "lite_planning": {
                    "run_id": "promopages-10060-campaign-15-01",
                    "result_path": "artifacts/clipmaker-lite/v1/campaign-15-01/result.json",
                    "structured_intent": {"primary_action": "Subtle motion."},
                    "provenance": {
                        "verified": True,
                        "agent_id": "clipmaker-lite",
                    },
                },
                "outputs": outputs,
            }
        ],
    }
    manifest = {
        "schema_version": 1,
        "manifest_role": pages.PROMOPAGES_10060_EXTENSION_ROLE,
        "ticket": "PROMOPAGES-10060",
        "batch_id": pages.PROMOPAGES_10060_EXTENSION_BATCH_ID,
        "agent_id": "clipmaker-lite",
        "models": list(pages.PROMOPAGES_10060_MODELS),
        "article_count": 1,
        "image_count": 1,
        "expected_outputs": 3,
        "accepted_output_count": 3,
        "terminal_accounted_output_count": 3,
        "provider_filtered_output_count": 0,
        "provider_unavailable_output_count": 0,
        "status_summary": {
            "succeeded": 3,
        },
        "acceptance_policy": {
            "requires_mp4_and_media": True,
            "terminal_accounted_without_media": [
                "provider-filtered",
                "provider-unavailable",
            ],
            "provider_filtered_requires_exhausted_retry_v1": True,
            "provider_unavailable_requires_ambiguous_submit_retry_v1": True,
            "provider_unavailable_requires_retry_v1": [
                "ambiguous-submit",
                "normalized-input",
            ],
        },
        "articles": [article],
        "outputs": [output.copy() for output in outputs],
        "unavailable_articles": [
            {
                "article_number": number,
                "article_slug": f"{number}-unavailable-campaign",
                "url": f"https://example.promo.page/media/campaign-{number}",
                "status": "source-unavailable",
                "error": "Article source is unavailable.",
            }
            for number in ("16", "17", "18")
        ],
    }
    return manifest, [source_path], video_paths


def _extension_normalized_input_retry_output(
    article_slug,
    image,
    model_id,
    video_path,
    *,
    metadata_sha256,
):
    source_key = (article_slug, image["image_id"])
    asset = pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES[source_key]
    model_suffix = "wan-2.2" if model_id == "alibaba/wan-2.2" else "wan-2.7"
    retry_key = (
        "c45a8447813d1b4e4df0"
        if image["image_id"] == "07" and model_id == "alibaba/wan-2.7"
        else f"{image['image_id']}-{model_suffix}-retry-key"
    )
    namespace = (
        pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE / retry_key
    )
    asset_parent = (
        pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_ASSET_NAMESPACE
        / asset["asset_key"]
    )
    repository_path = asset_parent / "normalized.png"
    metadata_path = asset_parent / "asset.json"
    normalized_url = (
        "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
        "alice-live-images-test/"
        f"{pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCE_COMMIT}/"
        f"{repository_path.as_posix()}"
    )
    primary = {
        "provider_run_id": f"{image['image_id']}-{model_suffix}-primary",
        "provider_job_id": f"{image['image_id']}-{model_suffix}-primary-job",
        "status": "provider-failed",
        "recorded_status": (
            "submit-unknown" if model_id == "alibaba/wan-2.2" else "provider-failed"
        ),
        "provider_may_be_active": False,
        "recorded_provider_may_be_active": model_id == "alibaba/wan-2.2",
        "submitted_at": (
            None if model_id == "alibaba/wan-2.2" else "2026-08-05T18:00:00Z"
        ),
        "completed_at": (
            None if model_id == "alibaba/wan-2.2" else "2026-08-05T18:01:00Z"
        ),
        "error": (
            "Image height or width is too small than 240"
            if model_id == "alibaba/wan-2.2"
            else (
                "Error validating image resolution: resolution must be at least "
                f"240x240, got {image['width']}x{image['height']}"
            )
        ),
        "run_path": f"runs/{image['image_id']}-{model_suffix}-primary.run.json",
        "run_sha256": "1" * 64,
        "prompt_path": (
            f"runs/{image['image_id']}-{model_suffix}-primary.prompt.json"
        ),
        "prompt_sha256": "2" * 64,
        "request_sha256": "3" * 64,
    }
    if model_id == "alibaba/wan-2.2":
        primary.update(
            {
                "provider_submit_time": "2026-08-05 18:00:00.000",
                "provider_scheduled_time": "2026-08-05 18:00:00.010",
                "provider_end_time": "2026-08-05 18:00:01.000",
            }
        )
    retry_provider_run_id = f"{image['image_id']}-{model_suffix}-normalized-retry"
    accepted_status = (
        "succeeded"
        if model_id == "alibaba/wan-2.2"
        else "verification-failed"
    )
    accepted_error = (
        None
        if accepted_status == "succeeded"
        else "Media contract verification failed: audio, resolution, aspect_ratio"
    )
    contract_check = (
        {"conforms": True, "warnings": []}
        if accepted_status == "succeeded"
        else {
            "conforms": False,
            "warnings": ["audio", "resolution", "aspect_ratio"],
        }
    )
    return {
        "article_slug": article_slug,
        "image_id": image["image_id"],
        "source_path": image["source_path"],
        "model_id": model_id,
        "provider_run_id": retry_provider_run_id,
        "positive_prompt": "Keep the source stable with restrained motion.",
        "status": accepted_status,
        "recorded_status": accepted_status,
        "selected_attempt": "normalized-input-retry-v1",
        "video_path": video_path,
        "media": {
            "width": 1280,
            "height": 720,
            "duration_seconds": 5,
            "bytes": 2048,
            "sha256": hashlib.sha256(video_path.encode()).hexdigest(),
        },
        "contract_check": contract_check,
        "error": accepted_error,
        "retry": {
            "retry_kind": "normalized-input",
            "retry_number": 1,
            "namespace": namespace.as_posix(),
            "envelope_path": (namespace / "retry.json").as_posix(),
            "envelope_sha256": "4" * 64,
            "exhausted": False,
            "primary_attempt": primary,
            "retry_attempt": {
                "provider_run_id": retry_provider_run_id,
                "provider_job_id": f"{retry_provider_run_id}-job",
                "status": accepted_status,
                "provider_may_be_active": False,
                "submitted_at": "2026-08-05T18:02:00Z",
                "completed_at": "2026-08-05T18:03:00Z",
                "error": accepted_error,
                "run_path": f"runs/{retry_key}.run.json",
                "run_sha256": "5" * 64,
                "prompt_path": f"runs/{retry_key}.prompt.json",
                "prompt_sha256": "6" * 64,
                "request_sha256": "7" * 64,
            },
            "source_transform": {
                "strategy": "deterministic-uniform-upscale",
                "original": {
                    "url": image["orig_url"],
                    "path": image["source_path"],
                    "sha256": image["sha256"],
                    "bytes": image["bytes"],
                    "width": image["width"],
                    "height": image["height"],
                },
                "normalized": {
                    "http_status": 200,
                    "url": normalized_url,
                    "sha256": asset["sha256"],
                    "bytes": asset["bytes"],
                    "width": asset["width"],
                    "height": asset["height"],
                    "format": asset["format"],
                    "delivery": "repository-raw",
                    "repository_path": repository_path.as_posix(),
                    "source_commit_sha": (
                        pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCE_COMMIT
                    ),
                    "metadata_path": metadata_path.as_posix(),
                    "metadata_sha256": metadata_sha256,
                },
                "request_delta": {
                    "json_pointer": (
                        "/input/image"
                        if model_id == "alibaba/wan-2.2"
                        else "/frame_images/0/image_url/url"
                    ),
                    "from": image["orig_url"],
                    "to": normalized_url,
                    "changed_leaf_count": 1,
                },
                "preparation": {
                    "operation": "uniform-scale",
                    "target_height": asset["height"],
                    "resampler": "lanczos",
                    "crop": False,
                    "local_reencode": True,
                },
                "minimum_provider_input_dimension": 240,
            },
        },
    }


def _extension_normalized_supersede_output(output):
    output = json.loads(json.dumps(output))
    retry = output["retry"]
    namespace = Path(retry["namespace"])
    supersede_namespace = (
        namespace / pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_DIRECTORY
    )
    superseded = json.loads(json.dumps(retry["retry_attempt"]))
    superseded.update(
        {
            "provider_run_id": (
                pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_RUN_ID
            ),
            "provider_job_id": (
                pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_JOB_ID
            ),
            "status": "running",
            "provider_may_be_active": True,
            "completed_at": None,
            "error": None,
        }
    )
    selected_provider_run_id = (
        "promopages-10060-campaigns-20260805-v1-normalized-input-"
        "supersede-v1-selected-18-volma-plitochnyi-klei-07-wan-2-7"
    )
    selected = {
        "provider_run_id": selected_provider_run_id,
        "provider_job_id": "replacement-wan27-job",
        "status": output["recorded_status"],
        "provider_may_be_active": False,
        "submitted_at": "2026-08-06T02:00:00Z",
        "completed_at": "2026-08-06T02:03:00Z",
        "error": output["error"],
        "run_path": (
            supersede_namespace / "videos/wan-2.7/07.run.json"
        ).as_posix(),
        "run_sha256": "8" * 64,
        "prompt_path": (
            supersede_namespace / "videos/wan-2.7/07.prompt.json"
        ).as_posix(),
        "prompt_sha256": "9" * 64,
        "request_sha256": superseded["request_sha256"],
    }
    output.update(
        {
            "provider_run_id": selected_provider_run_id,
            "selected_attempt": pages.PROMOPAGES_10060_NORMALIZED_SUPERSEDE_SELECTION,
            "video_path": (
                supersede_namespace / "videos/wan-2.7/07.mp4"
            ).as_posix(),
        }
    )
    retry["retry_attempt"] = json.loads(json.dumps(superseded))
    retry["supersede"] = {
        "version": 1,
        "namespace": supersede_namespace.as_posix(),
        "envelope_path": (supersede_namespace / "supersede.json").as_posix(),
        "envelope_sha256": "a" * 64,
        "exhausted": False,
        "superseded_attempt": superseded,
        "superseding_attempt": selected,
    }
    return output


def _promopages_10060_campaign_normalized_extension_fixture():
    article_slug = "18-volma-plitochnyi-klei"
    source_details = {
        "05": {
            "file": "05.png",
            "orig_url": (
                "https://avatars.mds.yandex.net/get-promoarticles/5400274/"
                "pub_6a267e54c6621a31e5630a18_6a2682a081cbac61b6b77c7f/orig"
            ),
            "bytes": 17_569,
            "width": 758,
            "height": 220,
        },
        "07": {
            "file": "07.png",
            "orig_url": (
                "https://avatars.mds.yandex.net/get-promoarticles/5096941/"
                "pub_6a267e54c6621a31e5630a18_6a269812b55c4222ecf7445c/orig"
            ),
            "bytes": 27_754,
            "width": 773,
            "height": 239,
        },
        "08": {
            "file": "08.jpeg",
            "orig_url": (
                "https://avatars.mds.yandex.net/get-promoarticles/5400274/"
                "pub_6a267e54c6621a31e5630a18_6a267e6fc6621a31e5630ed8/orig"
            ),
            "bytes": 30_852,
            "width": 752,
            "height": 193,
        },
    }
    records = []
    flat_outputs = []
    source_paths = []
    video_paths = []
    for image_id, details in source_details.items():
        source_path = (
            "PROMOPAGES-9857/"
            f"{pages.PROMOPAGES_10060_EXTENSION_DATASET_PREFIX}/articles/"
            f"{article_slug}/{details['file']}"
        )
        source_paths.append(source_path)
        asset = pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES[
            (article_slug, image_id)
        ]
        image = {
            "image_id": image_id,
            "source_path": source_path,
            "manifest_file_path": (
                pages.PROMOPAGES_10060_EXTENSION_MANIFEST_ROOT
                / article_slug
                / details["file"]
            ).as_posix(),
            "orig_url": details["orig_url"],
            "sha256": asset["source_sha256"],
            "bytes": details["bytes"],
            "width": details["width"],
            "height": details["height"],
        }
        outputs = []
        metadata_sha256 = str(int(image_id)) * 64
        for model_index, model_id in enumerate(
            pages.PROMOPAGES_10060_MODELS, start=1
        ):
            video_path = (
                "clipmaker-lite-test/runs/"
                f"{pages.PROMOPAGES_10060_EXTENSION_BATCH_ID}/videos/"
                f"{article_slug}/model-{model_index}/{image_id}.mp4"
            )
            video_paths.append(video_path)
            if model_id in {"alibaba/wan-2.2", "alibaba/wan-2.7"}:
                output = _extension_normalized_input_retry_output(
                    article_slug,
                    image,
                    model_id,
                    video_path,
                    metadata_sha256=metadata_sha256,
                )
            else:
                output = {
                    "article_slug": article_slug,
                    "image_id": image_id,
                    "source_path": source_path,
                    "model_id": model_id,
                    "provider_run_id": f"{image_id}-veo-primary",
                    "positive_prompt": "Keep the source stable.",
                    "status": "succeeded",
                    "recorded_status": "succeeded",
                    "selected_attempt": "primary",
                    "video_path": video_path,
                    "media": {
                        "width": 1280,
                        "height": 720,
                        "bytes": 2048,
                        "sha256": hashlib.sha256(video_path.encode()).hexdigest(),
                    },
                    "contract_check": {"conforms": True, "warnings": []},
                    "error": None,
                    "retry": None,
                }
            outputs.append(output)
            flat_outputs.append(json.loads(json.dumps(output)))
        records.append(
            {
                "image": image,
                "lite_planning": {
                    "run_id": f"extension-{article_slug}-{image_id}",
                    "result_path": (
                        f"artifacts/clipmaker-lite/v1/{article_slug}-{image_id}/"
                        "result.json"
                    ),
                    "structured_intent": {"primary_action": "Subtle motion."},
                    "provenance": {
                        "verified": True,
                        "agent_id": "clipmaker-lite",
                    },
                },
                "outputs": outputs,
            }
        )

    eligible_sources = [
        {
            "article_slug": source_article_slug,
            "image_id": image_id,
            "source_sha256": asset["source_sha256"],
            "models": ["alibaba/wan-2.2", "alibaba/wan-2.7"],
            "failure_kind": "minimum-dimension",
            "normalization_strategy": "deterministic-uniform-upscale",
        }
        for (source_article_slug, image_id), asset in (
            pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES.items()
        )
    ]
    supersede_record = next(
        record for record in records if record["image"]["image_id"] == "07"
    )
    supersede_index = next(
        index
        for index, output in enumerate(supersede_record["outputs"])
        if output["model_id"] == "alibaba/wan-2.7"
    )
    previous_video_path = supersede_record["outputs"][supersede_index]["video_path"]
    supersede_output = _extension_normalized_supersede_output(
        supersede_record["outputs"][supersede_index]
    )
    supersede_record["outputs"][supersede_index] = supersede_output
    flat_index = next(
        index
        for index, output in enumerate(flat_outputs)
        if output["article_slug"] == "18-volma-plitochnyi-klei"
        and output["image_id"] == "07"
        and output["model_id"] == "alibaba/wan-2.7"
    )
    flat_outputs[flat_index] = json.loads(json.dumps(supersede_output))
    video_paths[video_paths.index(previous_video_path)] = supersede_output["video_path"]

    manifest = {
        "schema_version": 1,
        "manifest_role": pages.PROMOPAGES_10060_EXTENSION_ROLE,
        "ticket": "PROMOPAGES-10060",
        "batch_id": pages.PROMOPAGES_10060_EXTENSION_BATCH_ID,
        "agent_id": "clipmaker-lite",
        "models": list(pages.PROMOPAGES_10060_MODELS),
        "article_count": 1,
        "image_count": 3,
        "expected_outputs": 9,
        "accepted_output_count": 9,
        "terminal_accounted_output_count": 9,
        "provider_filtered_output_count": 0,
        "provider_unavailable_output_count": 0,
        "status_summary": {"succeeded": 6, "verification-failed": 3},
        "acceptance_policy": {
            "requires_mp4_and_media": True,
            "terminal_accounted_without_media": [
                "provider-filtered",
                "provider-unavailable",
            ],
            "provider_filtered_requires_exhausted_retry_v1": True,
            "provider_unavailable_requires_ambiguous_submit_retry_v1": True,
            "provider_unavailable_requires_retry_v1": [
                "ambiguous-submit",
                "normalized-input",
            ],
        },
        "cost": {
            "terminal_retry_reservations": 0,
            "ambiguous_submit_retry_reservations": 0,
            "normalized_input_retry_version": 1,
            "normalized_input_retry_accounting_cost_usd": 0.35,
            "normalized_input_retry_reservations": 6,
            "normalized_input_supersede_version": 1,
            "normalized_input_supersede_accounting_cost_usd": 0.35,
            "normalized_input_supersede_reservations": 1,
            "maximum_new_paid_submissions_per_superseded_output": 1,
            "total_retry_reservations": 7,
            "maximum_new_paid_submissions_per_normalized_input_output": 1,
            "automatic_paid_retries": False,
        },
        "generation_policy": {
            "normalized_input_retry": {
                "version": 1,
                "namespace": (
                    pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE
                ).as_posix(),
                "shared_asset_namespace": (
                    pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_ASSET_NAMESPACE
                ).as_posix(),
                "eligible_sources": eligible_sources,
                "explicit_operator_command_required": True,
                "maximum_new_paid_submissions_per_eligible_output": 1,
                "retry2_forbidden": True,
                "automatic_paid_retries": False,
                "fallback": False,
                "primary_receipts_immutable": True,
                "request_delta_only_image_pointer": True,
            },
            "normalized_input_supersede": (
                pages._extension_normalized_supersede_policy()
            ),
        },
        "articles": [
            {
                "article_number": "18",
                "article_slug": article_slug,
                "title": "Плиточный клей: 5 вопросов экспертам по ремонту",
                "url": "https://volma.promo.page/promo/example",
                "context_path": (
                    pages.PROMOPAGES_10060_EXTENSION_CONTEXT_ROOT
                    / article_slug
                    / "content.json"
                ).as_posix(),
                "image_count": 3,
                "images": records,
            }
        ],
        "outputs": flat_outputs,
        "unavailable_articles": [
            {
                "article_number": number,
                "article_slug": f"{number}-unavailable-campaign",
                "url": f"https://example.promo.page/media/campaign-{number}",
                "status": "source-unavailable",
                "error": "Article source is unavailable.",
            }
            for number in ("15", "16", "17")
        ],
    }
    return manifest, source_paths, video_paths


def _s3_delivery_fixture(*source_manifests):
    routing_articles = []
    delivery_articles = []
    delivery_outputs = []
    seen_article_slugs = set()

    for manifest in source_manifests:
        outputs_by_article = {}
        for output in manifest["outputs"]:
            if output.get("video_path") is None:
                continue
            outputs_by_article.setdefault(output["article_slug"], []).append(output)

        for article in manifest["articles"]:
            article_slug = article["article_slug"]
            outputs = outputs_by_article.get(article_slug, [])
            if not outputs:
                continue
            if article_slug in seen_article_slugs:
                raise AssertionError(f"Duplicate fixture article: {article_slug}")
            seen_article_slugs.add(article_slug)

            article_number = article["article_number"]
            cabinet_slug = f"fixture-cabinet-{article_number}"
            cabinet_id = f"fixturecabinet{article_number}"
            publication_id = f"fixturepublication{article_number}"
            routing_articles.append(
                {
                    "article_number": article_number,
                    "article_slug": article_slug,
                    "label": article.get("title", f"Fixture article {article_number}"),
                    "url": article.get(
                        "url", f"https://example.test/articles/{article_number}"
                    ),
                    "cabinet": {
                        "name": f"Fixture cabinet {article_number}",
                        "slug": cabinet_slug,
                        "id": cabinet_id,
                    },
                    "campaign_ids": [f"fixturecampaign{article_number}"],
                    "publication_id": publication_id,
                    "source_status": "available",
                    "expected_image_count": article["image_count"],
                    "expected_ready_output_count": len(outputs),
                }
            )
            delivery_articles.append(
                {
                    "article_slug": article_slug,
                    "cabinet_slug": cabinet_slug,
                    "cabinet_id": cabinet_id,
                    "publication_id": publication_id,
                }
            )
            for output in outputs:
                media = output["media"]
                filename = (
                    f"image_{int(output['image_id']):02d}--sha256-"
                    f"{media['sha256'][:12]}.mp4"
                )
                object_key = (
                    f"{pages.PROMOPAGES_10060_S3_OBJECT_PREFIX}"
                    f"{cabinet_slug}__{cabinet_id}/{publication_id}/"
                    f"{pages.PROMOPAGES_10060_S3_MODEL_DIRECTORIES[output['model_id']]}/"
                    f"{filename}"
                )
                delivery_outputs.append(
                    {
                        "article_slug": article_slug,
                        "image_id": output["image_id"],
                        "model_id": output["model_id"],
                        "source_video_path": output["video_path"],
                        "sha256": media["sha256"],
                        "bytes": media["bytes"],
                        "object_key": object_key,
                        "yastatic_url": (
                            pages.PROMOPAGES_10060_S3_PUBLIC_BASE_URL + object_key
                        ),
                    }
                )

    routing_config = {
        "schema_version": 1,
        "ticket": "PROMOPAGES-10060",
        "articles": routing_articles,
    }
    delivery_manifest = {
        "schema_version": 1,
        "manifest_role": "promopages-10060-s3-delivery",
        "ticket": "PROMOPAGES-10060",
        "bucket": pages.PROMOPAGES_10060_S3_BUCKET,
        "object_prefix": pages.PROMOPAGES_10060_S3_OBJECT_PREFIX,
        "public_base_url": pages.PROMOPAGES_10060_S3_PUBLIC_BASE_URL,
        "verified_output_count": len(delivery_outputs),
        "articles": delivery_articles,
        "outputs": delivery_outputs,
    }
    return routing_config, delivery_manifest


def _write_s3_delivery_fixture(root, *source_manifests):
    routing_config, delivery_manifest = _s3_delivery_fixture(*source_manifests)
    routing_path = root / pages.PROMOPAGES_10060_S3_ARTICLES_RELATIVE_PATH
    routing_path.parent.mkdir(parents=True, exist_ok=True)
    routing_path.write_text(json.dumps(routing_config), encoding="utf-8")
    delivery_path = root / pages.PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH
    delivery_path.parent.mkdir(parents=True, exist_ok=True)
    delivery_path.write_text(json.dumps(delivery_manifest), encoding="utf-8")


def _write_promopages_collection_fixture(root, *, include_campaign_extension):
    def write_text(relative_path, content):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
    write_text(
        "manual-review/review-data.js",
        'window.qualityReviewDataset = {"items": []};\n',
    )
    write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
    write_text(
        "clipmaker-lite-test/promopages-9930-manifest.json",
        '{"articles": []}\n',
    )
    write_text(
        "clipmaker-lite-test/case-21-manifest.json",
        '{"articles": []}\n',
    )
    legacy, legacy_sources, legacy_videos = _promopages_10060_fixture()
    write_text(
        "clipmaker-lite-test/promopages-10060-manifest.json",
        json.dumps(legacy),
    )
    for relative_path in [*legacy_sources, *legacy_videos]:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"legacy-media")

    extension_paths = []
    source_manifests = [legacy]
    if include_campaign_extension:
        extension, extension_sources, extension_videos = (
            _promopages_10060_campaign_extension_fixture()
        )
        write_text(
            pages.PROMOPAGES_10060_EXTENSION_RELATIVE_PATH.as_posix(),
            json.dumps(extension),
        )
        extension_paths = [*extension_sources, *extension_videos]
        source_manifests.append(extension)
        for relative_path in extension_paths:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"campaign-media")
    _write_s3_delivery_fixture(root, *source_manifests)
    return extension_paths


def _tune_manifest_fixture(*, root, terminal_failure_indices=()):
    terminal_failure_indices = set(terminal_failure_indices)
    cases = []
    next_sheet_row = 2
    immutable_commit = "a" * 40
    for case_index in range(pages.TUNE_CASE_COUNT):
        targets = []
        target_count = 2 if case_index < 29 else 1
        for target_index in range(target_count):
            target_number = next_sheet_row - 1
            regenerated = target_number <= pages.TUNE_REGENERATED_TARGET_COUNT
            action = (
                pages.TUNE_REGENERATED_ACTION
                if regenerated
                else pages.TUNE_REUSED_ACTION
            )
            model_id = pages.PROMOPAGES_10060_MODELS[
                target_number % len(pages.PROMOPAGES_10060_MODELS)
            ]
            evaluation_id = f"case-{case_index + 1:02d}::{model_id}"
            if not regenerated:
                source_outcome = "helped"
            elif target_number <= 19:
                source_outcome = "unrated"
            elif target_number <= 24:
                source_outcome = "worse"
            else:
                source_outcome = "same-or-unclear"
            target = {
                "sheet_row": next_sheet_row,
                "model_id": model_id,
                "baseline": {
                    "video_url": (
                        "https://cdn.example.test/tune/"
                        f"case-{case_index + 1:02d}-{target_index + 1}.mp4"
                    ),
                    "repository_video_path": (
                        "private-tune-videos/"
                        f"case-{case_index + 1:02d}-{target_index + 1}.mp4"
                    ),
                },
                "iteration": {
                    "action": action,
                    "review_scope": regenerated,
                    "source_evaluation": {
                        "evaluation_id": evaluation_id,
                        "outcome": source_outcome,
                        "note": None if source_outcome == "unrated" else "Imported review",
                        "updated_at": None if source_outcome == "unrated" else "2026-08-11T16:41:34Z",
                    },
                },
                "tuned": {"execution_mode": "i2v"},
            }
            video_bytes = f"tune-v5-video-row-{next_sheet_row}".encode()
            repository_video_path = (
                "clipmaker-lite-test/runs/tune-v5/videos/"
                f"case-{case_index + 1:02d}/row-{next_sheet_row}.mp4"
            )
            sha256 = hashlib.sha256(video_bytes).hexdigest()
            media = {
                "duration_seconds": 5.0,
                "width": 1280,
                "height": 720,
                "fps": 24.0,
                "frames": 120,
                "bytes": len(video_bytes),
                "sha256": sha256,
                "container": "mov,mp4,m4a,3gp,3g2,mj2",
                "codec": "h264",
                "has_audio": False,
            }
            origin = "regenerated-v5" if regenerated else "reused-helped-v4"
            generation = {
                "origin": origin,
                "batch_id": "tune-v5-fixture",
                "provider_run_id": f"provider-run-{next_sheet_row}",
                "prompt_path": (
                    "clipmaker-lite-test/runs/tune-v5/videos/"
                    f"case-{case_index + 1:02d}/row-{next_sheet_row}.prompt.json"
                ),
                "run_path": (
                    "clipmaker-lite-test/runs/tune-v5/videos/"
                    f"case-{case_index + 1:02d}/row-{next_sheet_row}.run.json"
                ),
            }
            if target_number - 1 in terminal_failure_indices:
                prompt_file = root / generation["prompt_path"]
                run_file = root / generation["run_path"]
                output_path = repository_video_path
                provider_error = "Provider terminal failure produced no output"
                prompt_file.parent.mkdir(parents=True, exist_ok=True)
                prompt_file.write_text("{}\n", encoding="utf-8")
                run = {
                    "status": "provider-failed",
                    "execution_mode": "i2v",
                    "provider_run_id": generation["provider_run_id"],
                    "provider_may_be_active": False,
                    "provider_job_id": None,
                    "prompt_path": generation["prompt_path"],
                    "output_path": output_path,
                    "media": None,
                    "contract_check": None,
                    "error": provider_error,
                    "automatic_paid_retry": False,
                    "fallback": None,
                    "s3_upload": False,
                }
                run_file.write_text(json.dumps(run) + "\n", encoding="utf-8")
                target["tuned"]["video"] = {
                    "state": "unavailable",
                    "status": "provider-failed",
                    "method": "eliza-i2v",
                    "prompt_evaluated": False,
                    "delivery": "unavailable",
                    "url": None,
                    "repository_video_path": None,
                    "sha256": None,
                    "bytes": None,
                    "media": None,
                    "contract_check": None,
                    "generation": generation,
                    "provider_attempt": {
                        "status": "provider-failed",
                        "run_path": generation["run_path"],
                        "run_sha256": hashlib.sha256(run_file.read_bytes()).hexdigest(),
                        "prompt_path": generation["prompt_path"],
                        "prompt_sha256": hashlib.sha256(prompt_file.read_bytes()).hexdigest(),
                        "provider_job_id": None,
                        "error": provider_error,
                        "automatic_paid_retry": False,
                        "fallback": None,
                    },
                }
            else:
                video_path = root / repository_video_path
                video_path.parent.mkdir(parents=True, exist_ok=True)
                video_path.write_bytes(video_bytes)
                target["tuned"]["video"] = {
                    "state": "available",
                    "status": "succeeded",
                    "method": "eliza-i2v",
                    "prompt_evaluated": True,
                    "delivery": "repository-raw",
                    "url": (
                        "https://raw.githubusercontent.com/example/demo/"
                        f"{immutable_commit}/{repository_video_path}"
                    ),
                    "repository_video_path": repository_video_path,
                    "sha256": sha256,
                    "bytes": len(video_bytes),
                    "media": media,
                    "contract_check": {"conforms": True, "warnings": []},
                    "generation": generation,
                    "provider_attempt": None,
                }

            if regenerated:
                historical_method = (
                    "deterministic-compositor"
                    if target_number <= 22
                    else (
                        "deterministic-compositor-fallback"
                        if target_number <= 24
                        else "eliza-i2v"
                    )
                )
                historical_bytes = f"historical-row-{next_sheet_row}".encode()
                historical_sha = hashlib.sha256(historical_bytes).hexdigest()
                historical_path = (
                    "clipmaker-lite-test/runs/tune-v4/history/"
                    f"case-{case_index + 1:02d}/row-{next_sheet_row}.mp4"
                )
                historical_media = {
                    "duration_seconds": 4.0,
                    "width": 1280,
                    "height": 720,
                    "fps": 30.0,
                    "frames": 120,
                    "bytes": len(historical_bytes),
                    "sha256": historical_sha,
                }
                if historical_method == "eliza-i2v":
                    historical_media.update(
                        {
                            "container": "mov,mp4,m4a,3gp,3g2,mj2",
                            "codec": "h264",
                            "has_audio": False,
                        }
                    )
                    historical_contract = {"conforms": True, "warnings": []}
                else:
                    historical_media.update(
                        {
                            "video_codec": "h264",
                            "pixel_format": "yuv420p",
                            "audio_streams": 0,
                        }
                    )
                    historical_contract = {
                        "codec_h264": True,
                        "pixel_format_yuv420p": True,
                        "dimensions_exact": True,
                        "fps_exact": True,
                        "frames_exact": True,
                        "duration_exact": True,
                        "no_audio": True,
                        "source_sha256_bound": True,
                        "source_dimensions_bound": True,
                    }
                historical_video = {
                    "status": "succeeded",
                    "method": historical_method,
                    "delivery": "repository-raw",
                    "url": (
                        "https://raw.githubusercontent.com/example/demo/"
                        f"{'b' * 40}/{historical_path}"
                    ),
                    "repository_video_path": historical_path,
                    "sha256": historical_sha,
                    "bytes": len(historical_bytes),
                    "media": historical_media,
                    "contract_check": historical_contract,
                }
                if historical_method == "deterministic-compositor-fallback":
                    historical_video.update(
                        {
                            "prompt_evaluated": False,
                            "provider_attempt": {
                                "status": "provider-failed",
                                "prompt_evaluated": False,
                                "run_path": (
                                    "clipmaker-lite-test/runs/tune-v4/history/"
                                    f"row-{next_sheet_row}.run.json"
                                ),
                                "run_sha256": "c" * 64,
                                "provider_job_id": "historical-job",
                                "error": "Historical provider failure",
                            },
                        }
                    )
                target["previous_tuned"] = {
                    "execution_mode": (
                        "deterministic-compositor"
                        if historical_method == "deterministic-compositor"
                        else "i2v"
                    ),
                    "scene_plan": "Historical v4 plan",
                    "video": historical_video,
                }
            targets.append(target)
            next_sheet_row += 1
        cases.append(
            {
                "case_id": f"case-{case_index + 1:02d}",
                "source": {
                    "url": (
                        "https://images.example.test/tune/"
                        f"case-{case_index + 1:02d}.jpg"
                    ),
                    "path": f"private-tune-images/case-{case_index + 1:02d}.jpg",
                },
                "targets": targets,
            }
        )
    return {
        "schema_version": 2,
        "manifest_role": "clipmaker-lite-tune-review",
        "ticket": "PROMOPAGES-10060",
        "agent_id": "clipmaker-lite",
        "scope": {
            "case_count": pages.TUNE_CASE_COUNT,
            "target_count": pages.TUNE_TARGET_COUNT,
            "review_target_count": pages.TUNE_REVIEW_TARGET_COUNT,
            "regenerated_target_count": pages.TUNE_REGENERATED_TARGET_COUNT,
            "reused_helped_target_count": pages.TUNE_REUSED_HELPED_TARGET_COUNT,
            "execution_mode_counts": {"i2v": pages.TUNE_TARGET_COUNT},
            "video_method_counts": {"eliza-i2v": pages.TUNE_TARGET_COUNT},
            "available_video_count": (
                pages.TUNE_TARGET_COUNT - len(terminal_failure_indices)
            ),
            "unavailable_video_count": len(terminal_failure_indices),
            "new_video_generation": True,
            "new_s3_upload": False,
        },
        "summary": {
            "iteration_action_counts": {
                "regenerated-v5": pages.TUNE_REGENERATED_TARGET_COUNT,
                "reused-helped": pages.TUNE_REUSED_HELPED_TARGET_COUNT,
            },
            "video_method_counts": {"eliza-i2v": pages.TUNE_TARGET_COUNT},
            "unavailable_video_count": len(terminal_failure_indices),
        },
        "cases": cases,
    }


def _apply_v8_prompt_experiment_fixture(root: Path, manifest: dict) -> dict:
    generation_path = ROOT / tune_overlay.V8_EXPERIMENT_GENERATION_MANIFEST_REL
    document = json.loads(generation_path.read_text(encoding="utf-8"))
    outputs, entries, prompt_case, _generation_sha, _prompt_sha = (
        tune_overlay.validate_v8_experiment_generation_manifest(
            document,
            path=generation_path,
            root=ROOT,
        )
    )
    video = tune_overlay._v8_experiment_video(  # noqa: SLF001
        outputs,
        entries,
        prompt_case,
        root=ROOT,
    )
    record = tune_overlay._v8_prompt_experiment_record(  # noqa: SLF001
        prompt_case,
        entries,
    )
    audit_paths = [
        attempt[field]
        for attempt in video["provider_attempt"]["attempts"]
        for field in ("run_path", "prompt_path")
    ]
    audit_paths.append(video["generation"]["prior_attempt"]["run_path"])
    for value in audit_paths:
        source = ROOT / value
        destination = root / value
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    target = manifest["cases"][0]["targets"][0]
    target["tuned"]["video"] = video
    target["prompt_experiment"] = record
    return target


class GitHubPagesSiteTest(unittest.TestCase):
    def test_tune_v5_payload_keeps_all_tune_media_outside_pages(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            pages._validate_tune_manifest_for_pages(manifest, root=root)

        self.assertEqual(
            pages.TUNE_STATIC_FILES,
            ("tune/index.html", "tune/styles.css", "tune/app.js"),
        )
        self.assertIn(
            pages.TUNE_MANIFEST_RELATIVE_PATH.as_posix(), pages.STATIC_FILES
        )
        for relative_path in pages.TUNE_STATIC_FILES:
            self.assertIn(relative_path, pages.STATIC_FILES)
        tune_media = {
            target["baseline"]["repository_video_path"]
            for case in manifest["cases"]
            for target in case["targets"]
        }
        tune_media.update(
            target["tuned"]["video"]["repository_video_path"]
            for case in manifest["cases"]
            for target in case["targets"]
            if target["tuned"]["video"]["repository_video_path"]
        )
        tune_media.update(
            target["previous_tuned"]["video"]["repository_video_path"]
            for case in manifest["cases"]
            for target in case["targets"]
            if "previous_tuned" in target
        )
        self.assertTrue(all(path not in pages.STATIC_FILES for path in tune_media))

    def test_tune_v5_manifest_is_published_but_no_tune_mp4_is_collected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_promopages_collection_fixture(
                root, include_campaign_extension=False
            )
            manifest = _tune_manifest_fixture(root=root)
            manifest_path = root / pages.TUNE_MANIFEST_RELATIVE_PATH
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
                pages.TUNE_MANIFEST_RELATIVE_PATH.as_posix(),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            tune_mp4s = {
                Path(video["repository_video_path"])
                for case in manifest["cases"]
                for target in case["targets"]
                for video in (
                    target["tuned"]["video"],
                    target.get("previous_tuned", {}).get("video"),
                )
                if isinstance(video, dict)
                and isinstance(video.get("repository_video_path"), str)
            }
            self.assertIn(pages.TUNE_MANIFEST_RELATIVE_PATH, paths)
            self.assertTrue(tune_mp4s.isdisjoint(paths))

    def test_tune_v5_identity_and_delivery_mismatches_fail_closed(self):
        mutations = {
            "identity": lambda manifest: manifest.update({"schema_version": 1}),
            "iteration scope": lambda manifest: manifest["scope"].update(
                {"new_video_generation": False}
            ),
            "source delivery": lambda manifest: manifest["cases"][0][
                "source"
            ].update({"url": "private-tune-images/case-01.jpg"}),
            "baseline": lambda manifest: manifest["cases"][0]["targets"][0][
                "baseline"
            ].update({"video_url": "private-tune-videos/case-01-01.mp4"}),
            "target identity": lambda manifest: manifest["cases"][0]["targets"][0].update(
                {"sheet_row": manifest["cases"][0]["targets"][1]["sheet_row"]}
            ),
            "target identity is duplicated": lambda manifest: manifest["cases"][0][
                "targets"
            ][1].update(
                {"model_id": manifest["cases"][0]["targets"][0]["model_id"]}
            ),
            "forbidden active metadata": lambda manifest: manifest["scope"].update(
                {"fallback_method": "deterministic-compositor"}
            ),
            "summary counts": lambda manifest: manifest["summary"].update(
                {
                    "video_method_counts": {
                        "eliza-i2v": 64,
                        "deterministic-compositor": 1,
                    }
                }
            ),
        }
        for error, mutate in mutations.items():
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = _tune_manifest_fixture(root=root)
                mutate(manifest)
                with self.assertRaisesRegex(ValueError, error):
                    pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_is_exactly_65_active_i2v_with_28_review_targets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            targets = [
                target for case in manifest["cases"] for target in case["targets"]
            ]
            self.assertEqual(len(targets), 65)
            self.assertTrue(
                all(target["tuned"]["execution_mode"] == "i2v" for target in targets)
            )
            self.assertTrue(
                all(target["tuned"]["video"]["method"] == "eliza-i2v" for target in targets)
            )
            self.assertEqual(
                sum(target["iteration"]["review_scope"] for target in targets), 28
            )
            self.assertEqual(
                sum(target["iteration"]["action"] == "reused-helped" for target in targets),
                37,
            )
            self.assertEqual(sum("previous_tuned" in target for target in targets), 28)
            self.assertTrue(
                all(
                    not (root / target["previous_tuned"]["video"]["repository_video_path"]).exists()
                    for target in targets
                    if "previous_tuned" in target
                )
            )
            active_paths = {
                Path(target["tuned"]["video"]["repository_video_path"])
                for target in targets
            }
            self.assertEqual(len(active_paths), 65)
            self.assertTrue(
                active_paths.isdisjoint({Path(path) for path in pages.STATIC_FILES})
            )

            warning_video = targets[0]["tuned"]["video"]
            warning_video["status"] = "verification-failed"
            warning_video["media"]["has_audio"] = True
            warning_video["contract_check"] = {
                "conforms": False,
                "requested": {"generate_audio": False},
                "checks": {"audio": False},
                "warnings": [
                    "provider returned has_audio=True despite generate_audio=False"
                ],
            }
            pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_i2v_audio_warning_preserves_exact_provider_violation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = _tune_manifest_fixture(root=root)

            def audio_failure_manifest():
                manifest = json.loads(json.dumps(fixture))
                video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
                video["status"] = "verification-failed"
                video["media"]["has_audio"] = True
                video["contract_check"] = {
                    "conforms": False,
                    "requested": {"generate_audio": False},
                    "checks": {"audio": False},
                    "warnings": [
                        "provider returned has_audio=True despite generate_audio=False"
                    ],
                }
                return manifest, video

            mutations = {
                "succeeded output cannot contain audio": lambda video: video.update(
                    {"status": "succeeded", "contract_check": {"conforms": True, "warnings": []}}
                ),
                "requested audio must remain false": lambda video: video[
                    "contract_check"
                ]["requested"].update({"generate_audio": True}),
                "audio check must remain false": lambda video: video[
                    "contract_check"
                ]["checks"].update({"audio": True}),
                "warning must name actual audio": lambda video: video[
                    "contract_check"
                ].update({"warnings": ["provider contract mismatch"]}),
            }
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    manifest, video = audio_failure_manifest()
                    mutate(video)
                    with self.assertRaisesRegex(
                        ValueError, "I2V media or contract warnings"
                    ):
                        pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_terminal_provider_failure_is_unavailable_without_fallback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root, terminal_failure_indices={0})
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
            self.assertEqual(video["state"], "unavailable")
            self.assertEqual(video["method"], "eliza-i2v")
            self.assertIsNone(video["url"])
            self.assertIsNone(video["provider_attempt"]["fallback"])
            run = json.loads((root / video["provider_attempt"]["run_path"]).read_text())
            self.assertFalse((root / run["output_path"]).exists())

        def rewrite_run(root, video, **updates):
            run_path = root / video["provider_attempt"]["run_path"]
            run = json.loads(run_path.read_text())
            run.update(updates)
            run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")
            video["provider_attempt"]["run_sha256"] = hashlib.sha256(
                run_path.read_bytes()
            ).hexdigest()

        mutations = {
            "unavailable video receipt": lambda root, video: video.update(
                {"url": "https://example.test/not-an-output.mp4"}
            ),
            "forbidden active metadata": lambda root, video: video[
                "provider_attempt"
            ].update({"fallback": {"method": "camera"}}),
            "terminal provider audit": lambda root, video: video[
                "provider_attempt"
            ].update({"automatic_paid_retry": True}),
            "run SHA mismatch": lambda root, video: video["provider_attempt"].update(
                {"run_sha256": "f" * 64}
            ),
            "prompt SHA mismatch": lambda root, video: video["provider_attempt"].update(
                {"prompt_sha256": "f" * 64}
            ),
            "does not bind terminal failure": lambda root, video: rewrite_run(
                root, video, provider_may_be_active=True
            ),
            "must not have an MP4": lambda root, video: (
                lambda output: (
                    output.parent.mkdir(parents=True, exist_ok=True),
                    output.write_bytes(b"unexpected"),
                )
            )(
                root
                / json.loads(
                    (root / video["provider_attempt"]["run_path"]).read_text()
                )["output_path"]
            ),
        }
        for error, mutate in mutations.items():
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = _tune_manifest_fixture(root=root, terminal_failure_indices={0})
                video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
                mutate(root, video)
                with self.assertRaisesRegex(ValueError, error):
                    pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_iteration_scope_and_previous_history_are_exact(self):
        def first_two(manifest):
            targets = [target for case in manifest["cases"] for target in case["targets"]]
            return targets[0], targets[28]

        mutations = (
            ("regenerated-v5 review scope", lambda manifest: first_two(manifest)[0][
                "iteration"
            ].update({"review_scope": False})),
            ("regenerated-v5 review scope", lambda manifest: first_two(manifest)[0][
                "iteration"
            ]["source_evaluation"].update({"outcome": "helped"})),
            ("regenerated-v5 review scope", lambda manifest: first_two(manifest)[0].pop(
                "previous_tuned"
            )),
            ("reused-helped review scope", lambda manifest: first_two(manifest)[1].update(
                {"previous_tuned": first_two(manifest)[0]["previous_tuned"]}
            )),
            ("iteration audit", lambda manifest: first_two(manifest)[0]["iteration"][
                "source_evaluation"
            ].update({"evaluation_id": "wrong"})),
            ("iteration scope", lambda manifest: manifest["scope"].update(
                {"review_target_count": 27}
            )),
        )
        for error, mutate in mutations:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = _tune_manifest_fixture(root=root)
                mutate(manifest)
                with self.assertRaisesRegex(ValueError, error):
                    pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_rejects_active_compositor_and_fallback_metadata(self):
        mutations = (
            ("active I2V mode", lambda tuned, video: tuned.update(
                {"execution_mode": "deterministic-compositor"}
            )),
            ("forbidden active metadata", lambda tuned, video: video.update(
                {"method": "deterministic-compositor"}
            )),
            ("forbidden active metadata", lambda tuned, video: video[
                "generation"
            ].update({"run_path": "runs/compositor/row.run.json"})),
            ("forbidden active metadata", lambda tuned, video: video.update(
                {"compositor": {"primitive": "camera_push"}}
            )),
            ("forbidden active metadata", lambda tuned, video: video.update(
                {"fallback": {"method": "still-frame"}}
            )),
        )
        for error, mutate in mutations:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = _tune_manifest_fixture(root=root)
                tuned = manifest["cases"][0]["targets"][0]["tuned"]
                mutate(tuned, tuned["video"])
                with self.assertRaisesRegex(ValueError, error):
                    pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_previous_tuned_is_validated_as_remote_history(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            previous = manifest["cases"][0]["targets"][0]["previous_tuned"]["video"]
            self.assertFalse((root / previous["repository_video_path"]).exists())
            pages._validate_tune_manifest_for_pages(manifest, root=root)

            previous_path = root / previous["repository_video_path"]
            previous_path.parent.mkdir(parents=True, exist_ok=True)
            previous_path.write_bytes(b"wrong historical bytes")
            with self.assertRaisesRegex(ValueError, "repository file SHA/bytes mismatch"):
                pages._validate_tune_manifest_for_pages(manifest, root=root)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            previous = manifest["cases"][0]["targets"][0]["previous_tuned"]["video"]
            previous["url"] = (
                "https://raw.githubusercontent.com/example/demo/main/"
                f"{previous['repository_video_path']}"
            )
            with self.assertRaisesRegex(ValueError, "immutable raw.githubusercontent.com"):
                pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v5_rejects_missing_or_non_regular_active_repo_media(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
            video_path = root / video["repository_video_path"]
            video_path.unlink()
            with self.assertRaisesRegex(ValueError, "repository file is missing"):
                pages._validate_tune_manifest_for_pages(manifest, root=root)

            video_path.mkdir()
            with self.assertRaisesRegex(ValueError, "repository file must be regular"):
                pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_s3_delivery_overlay_matches_all_available_canonical_outputs(self):
        source_manifests = [
            json.loads(PROMOPAGES_10060_MANIFEST_PATH.read_text(encoding="utf-8")),
            json.loads(PROMOPAGES_10060_ARTICLE_02_PATH.read_text(encoding="utf-8")),
            json.loads(PROMOPAGES_10060_EXTENSION_PATH.read_text(encoding="utf-8")),
            json.loads(
                PROMOPAGES_10060_CAMPAIGN_20260807_PATH.read_text(
                    encoding="utf-8"
                )
            ),
        ]
        delivery = json.loads(
            PROMOPAGES_10060_S3_DELIVERY_PATH.read_text(encoding="utf-8")
        )
        routing_config = json.loads(
            PROMOPAGES_10060_S3_ARTICLES_PATH.read_text(encoding="utf-8")
        )

        covered_paths = pages._validate_promopages_10060_s3_delivery(
            delivery, routing_config, *source_manifests
        )
        canonical_paths = {
            Path(output["video_path"])
            for manifest in source_manifests
            for output in manifest["outputs"]
            if output.get("video_path") is not None
        }

        self.assertEqual(len(covered_paths), 510)
        self.assertEqual(covered_paths, canonical_paths)

    def test_s3_delivery_overlay_mismatches_fail_closed(self):
        source_manifests = [
            json.loads(PROMOPAGES_10060_MANIFEST_PATH.read_text(encoding="utf-8")),
            json.loads(PROMOPAGES_10060_ARTICLE_02_PATH.read_text(encoding="utf-8")),
            json.loads(PROMOPAGES_10060_EXTENSION_PATH.read_text(encoding="utf-8")),
            json.loads(
                PROMOPAGES_10060_CAMPAIGN_20260807_PATH.read_text(
                    encoding="utf-8"
                )
            ),
        ]
        routing_config = json.loads(
            PROMOPAGES_10060_S3_ARTICLES_PATH.read_text(encoding="utf-8")
        )

        def make_object_key_noncanonical(manifest):
            output = manifest["outputs"][0]
            output["object_key"] = output["object_key"].replace("/", "//", 1)
            output["yastatic_url"] = (
                pages.PROMOPAGES_10060_S3_PUBLIC_BASE_URL + output["object_key"]
            )

        def replace_object_key_segment(manifest, index, value):
            output = manifest["outputs"][0]
            parts = output["object_key"].split("/")
            parts[index] = value
            output["object_key"] = "/".join(parts)
            output["yastatic_url"] = (
                pages.PROMOPAGES_10060_S3_PUBLIC_BASE_URL + output["object_key"]
            )

        mutations = {
            "identity": (
                "identity",
                lambda manifest: manifest.update({"bucket": "wrong-bucket"}),
            ),
            "logical_triple": (
                "logical output triple",
                lambda manifest: manifest["outputs"][0].update(
                    {"model_id": "alibaba/wan-9.9"}
                ),
            ),
            "source_path": (
                "source path differs",
                lambda manifest: manifest["outputs"][0].update(
                    {"source_video_path": "wrong/video.mp4"}
                ),
            ),
            "noncanonical_source_path": (
                "source path differs",
                lambda manifest: manifest["outputs"][0].update(
                    {
                        "source_video_path": (
                            "./" + manifest["outputs"][0]["source_video_path"]
                        )
                    }
                ),
            ),
            "sha256": (
                "hash or byte size differs",
                lambda manifest: manifest["outputs"][0].update(
                    {"sha256": "0" * 64}
                ),
            ),
            "bytes": (
                "hash or byte size differs",
                lambda manifest: manifest["outputs"][0].update(
                    {"bytes": manifest["outputs"][0]["bytes"] + 1}
                ),
            ),
            "object_prefix": (
                "object key differs from authoritative route",
                lambda manifest: manifest["outputs"][0].update(
                    {
                        "object_key": manifest["outputs"][0]["object_key"].replace(
                            pages.PROMOPAGES_10060_S3_OBJECT_PREFIX,
                            "wrong-prefix/",
                            1,
                        )
                    }
                ),
            ),
            "noncanonical_object_key": (
                "object key is not canonical",
                make_object_key_noncanonical,
            ),
            "article_cabinet": (
                "article routing differs",
                lambda manifest: manifest["articles"][0].update(
                    {"cabinet_id": "mutated-cabinet"}
                ),
            ),
            "object_cabinet": (
                "object key differs from authoritative route",
                lambda manifest: replace_object_key_segment(
                    manifest, 2, "mutated-cabinet"
                ),
            ),
            "object_publication": (
                "object key differs from authoritative route",
                lambda manifest: replace_object_key_segment(
                    manifest, 3, "mutated-publication"
                ),
            ),
            "yastatic_url": (
                "yastatic URL",
                lambda manifest: manifest["outputs"][0].update(
                    {"yastatic_url": "https://example.invalid/video.mp4"}
                ),
            ),
            "missing": (
                "exactly 510 verified outputs",
                lambda manifest: manifest["outputs"].pop(),
            ),
            "extra": (
                "exactly 510 verified outputs",
                lambda manifest: manifest["outputs"].append(
                    dict(manifest["outputs"][0])
                ),
            ),
        }
        original_delivery = PROMOPAGES_10060_S3_DELIVERY_PATH.read_text(
            encoding="utf-8"
        )
        for name, (error, mutate) in mutations.items():
            with self.subTest(name=name):
                delivery = json.loads(original_delivery)
                mutate(delivery)
                with self.assertRaisesRegex(ValueError, error):
                    pages._validate_promopages_10060_s3_delivery(
                        delivery, routing_config, *source_manifests
                    )

    def test_tune_v6_route_safety_withholding_is_audited_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root, terminal_failure_indices={0})
            video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
            run_path = root / video["provider_attempt"]["run_path"]
            prompt_path = root / video["provider_attempt"]["prompt_path"]
            run = json.loads(run_path.read_text())
            run.update(
                {
                    "status": "dry-run",
                    "submission_count": 0,
                    "provider_may_be_active": False,
                    "provider_job_id": None,
                    "error": None,
                }
            )
            run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")

            barrier_run_path = root / "clipmaker-lite-test/runs/tune-v5/barrier/17.run.json"
            barrier_prompt_path = root / "clipmaker-lite-test/runs/tune-v5/barrier/17.prompt.json"
            barrier_run_path.parent.mkdir(parents=True, exist_ok=True)
            barrier_prompt_path.write_text("{}\n", encoding="utf-8")
            barrier_run = {
                "status": "submit-unknown",
                "provider_may_be_active": True,
                "provider_job_id": None,
                "automatic_paid_retry": False,
                "fallback": None,
            }
            barrier_run_path.write_text(json.dumps(barrier_run) + "\n", encoding="utf-8")
            source_attempt = {
                "status": "submit-unknown",
                "provider_may_be_active": True,
                "run_path": barrier_run_path.relative_to(root).as_posix(),
                "run_sha256": hashlib.sha256(barrier_run_path.read_bytes()).hexdigest(),
                "prompt_path": barrier_prompt_path.relative_to(root).as_posix(),
                "prompt_sha256": hashlib.sha256(barrier_prompt_path.read_bytes()).hexdigest(),
                "automatic_paid_retry": False,
                "fallback": None,
            }
            barrier = {
                "model_id": "alibaba/wan-2.2",
                "route_capacity": 1,
                "reason": "Prior submit-unknown may still hold the only route slot.",
                "source_provider_attempt": source_attempt,
            }
            video.update(
                {
                    "status": "provider-unavailable",
                    "recorded_status": "dry-run",
                    "prompt_evaluated": False,
                    "unavailable_reason": "Not attempted because the route slot may still be active.",
                    "safety_barrier": barrier,
                    "generation": {
                        **video["generation"],
                        "origin": pages.TUNE_ROUTE_SAFETY_ORIGIN,
                        "run_status": "dry-run",
                    },
                    "provider_attempt": {
                        "status": "not-attempted-route-safety",
                        "run_path": run_path.relative_to(root).as_posix(),
                        "run_sha256": hashlib.sha256(run_path.read_bytes()).hexdigest(),
                        "prompt_path": prompt_path.relative_to(root).as_posix(),
                        "prompt_sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest(),
                        "provider_job_id": None,
                        "provider_may_be_active": False,
                        "submission_count": 0,
                        "error": "Not attempted because the route slot may still be active.",
                        "automatic_paid_retry": False,
                        "fallback": None,
                        "safety_barrier": barrier,
                    },
                }
            )
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            video["safety_barrier"]["source_provider_attempt"][
                "provider_may_be_active"
            ] = False
            with self.assertRaisesRegex(ValueError, "safety barrier"):
                pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_v7_filter_retry_success_and_failure_are_valid_without_pages_media(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
            video["generation"]["origin"] = pages.TUNE_V7_FILTER_RETRY_ORIGIN
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            collected = {
                Path(target["tuned"]["video"]["repository_video_path"])
                for case in manifest["cases"]
                for target in case["targets"]
                if target["tuned"]["video"]["repository_video_path"]
            }
            self.assertTrue(all(path.suffix == ".mp4" for path in collected))
            self.assertTrue(all(path not in pages.STATIC_FILES for path in collected))

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root, terminal_failure_indices={0})
            video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
            run_path = root / video["provider_attempt"]["run_path"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["submission_count"] = 1
            run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")
            video.update(
                {
                    "status": "provider-unavailable",
                    "recorded_status": "provider-failed",
                    "unavailable_reason": video["provider_attempt"]["error"],
                    "safety_barrier": None,
                }
            )
            video["generation"]["origin"] = pages.TUNE_V7_FILTER_RETRY_ORIGIN
            video["provider_attempt"].update(
                {
                    "run_sha256": hashlib.sha256(run_path.read_bytes()).hexdigest(),
                    "submission_count": 1,
                    "provider_may_be_active": False,
                }
            )
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            self.assertIsNone(video["repository_video_path"])
            self.assertIsNone(video["provider_attempt"]["fallback"])

    def test_tune_v8_prompt_experiment_preserves_all_three_terminal_attempts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root, terminal_failure_indices={0})
            target = _apply_v8_prompt_experiment_fixture(root, manifest)
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            video = target["tuned"]["video"]
            self.assertEqual(video["unavailable_reason"], pages.TUNE_V8_UNAVAILABLE_REASON)
            self.assertEqual(video["provider_attempt"]["attempt_count"], 3)
            self.assertEqual(
                [
                    attempt["variant_id"]
                    for attempt in video["provider_attempt"]["attempts"]
                ],
                list(pages.TUNE_V8_VARIANT_ORDER),
            )
            self.assertTrue(
                target["prompt_experiment"][
                    "displayed_tuned_prompt_is_prior_baseline"
                ]
            )
            self.assertTrue(
                all(
                    not (root / attempt["run_path"]).with_suffix(".mp4").exists()
                    for attempt in video["provider_attempt"]["attempts"]
                )
            )

        for name, mutate in (
            (
                "aggregate",
                lambda target: target["tuned"]["video"]["provider_attempt"].update(
                    {"attempt_count": 2}
                ),
            ),
            (
                "run IDs",
                lambda target: target["tuned"]["video"]["generation"].update(
                    {"provider_run_ids": ["wrong"] * 3}
                ),
            ),
            (
                "prompt experiment record",
                lambda target: target["prompt_experiment"].update(
                    {"prompt_manifest_sha256": "f" * 64}
                ),
            ),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = _tune_manifest_fixture(
                    root=root,
                    terminal_failure_indices={0},
                )
                target = _apply_v8_prompt_experiment_fixture(root, manifest)
                mutate(target)
                with self.assertRaisesRegex(ValueError, name):
                    pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_tune_manual_visual_qa_is_sha_bound_and_non_rejecting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = _tune_manifest_fixture(root=root)
            video = manifest["cases"][0]["targets"][0]["tuned"]["video"]
            video["qa"] = {
                "status": "visual-review-failed",
                "verified": False,
                "reviewable": True,
                "reviewer": "codex-visual-qa",
                "video_sha256": video["sha256"],
                "automatic_rejection": False,
                "scope": "strict-visual-fidelity",
                "summary": "Strict visual fidelity failed; provider contract still conforms.",
                "findings": ["A semantic region changes independently."],
            }
            pages._validate_tune_manifest_for_pages(manifest, root=root)
            self.assertEqual(video["status"], "succeeded")
            self.assertTrue(video["contract_check"]["conforms"])
            self.assertFalse(video["qa"]["automatic_rejection"])
            video["qa"]["video_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "manual visual QA"):
                pages._validate_tune_manifest_for_pages(manifest, root=root)

    def test_article_02_replacement_is_published_but_media_stays_raw(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_promopages_collection_fixture(
                root, include_campaign_extension=False
            )
            article_02, source_paths, video_paths = (
                _promopages_10060_article_02_fixture()
            )
            sidecar_path = root / pages.PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            _materialize_article_02_raw_fixture(root, article_02)
            sidecar_path.write_text(json.dumps(article_02), encoding="utf-8")
            legacy = json.loads(
                (root / "clipmaker-lite-test/promopages-10060-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            _write_s3_delivery_fixture(root, legacy, article_02)

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            self.assertIn(pages.PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH, paths)
            for relative_path in [*source_paths, *video_paths]:
                self.assertNotIn(Path(relative_path), paths)

    def test_article_02_replacement_rejects_raw_media_hash_drift(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_promopages_collection_fixture(
                root, include_campaign_extension=False
            )
            article_02, source_paths, _ = _promopages_10060_article_02_fixture()
            _materialize_article_02_raw_fixture(root, article_02)
            sidecar_path = root / pages.PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            sidecar_path.write_text(json.dumps(article_02), encoding="utf-8")
            legacy = json.loads(
                (root / "clipmaker-lite-test/promopages-10060-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            _write_s3_delivery_fixture(root, legacy, article_02)
            (root / source_paths[0]).write_bytes(b"corrupted")

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "raw source hash differs"),
            ):
                pages.collect_site_paths(root)

    def test_article_02_replacement_requires_exact_legacy_unavailable_target(self):
        article_02, source_paths, video_paths = (
            _promopages_10060_article_02_fixture()
        )

        legacy, _, _ = _promopages_10060_fixture()
        legacy["unavailable_articles"][0]["article_slug"] = "02-wrong-article"
        with self.assertRaisesRegex(ValueError, "exact legacy unavailable target"):
            pages._collect_promopages_10060_article_02_paths(
                article_02, legacy, set()
            )

        legacy, _, _ = _promopages_10060_fixture()
        legacy["articles"].append(
            {
                "article_number": "02",
                "article_slug": pages.PROMOPAGES_10060_ARTICLE_02_SLUG,
                "images": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "available legacy article"):
            pages._collect_promopages_10060_article_02_paths(
                article_02, legacy, set()
            )

        legacy, _, _ = _promopages_10060_fixture()
        for collision_path in (source_paths[0], video_paths[0]):
            with self.subTest(collision_path=collision_path):
                with self.assertRaisesRegex(ValueError, "path collision"):
                    pages._collect_promopages_10060_article_02_paths(
                        article_02, legacy, {Path(collision_path)}
                    )

    def test_article_02_replacement_identity_and_namespaces_fail_closed(self):
        legacy, _, _ = _promopages_10060_fixture()

        def first_image(manifest):
            return manifest["articles"][0]["images"][0]["image"]

        def first_output(manifest):
            return manifest["articles"][0]["images"][0]["outputs"][0]

        mutations = {
            "role": (
                "identity",
                lambda manifest: manifest.update({"manifest_role": "wrong-role"}),
            ),
            "batch": (
                "identity",
                lambda manifest: manifest.update(
                    {"batch_id": "promopages-10060-article-02-20260806-v1"}
                ),
            ),
            "article_number": (
                "registered article 02",
                lambda manifest: manifest["articles"][0].update(
                    {"article_number": "03"}
                ),
            ),
            "title": (
                "registered article 02",
                lambda manifest: manifest["articles"][0].update(
                    {"title": "Подменённый заголовок"}
                ),
            ),
            "context_dataset": (
                "context_path is outside dataset v1",
                lambda manifest: manifest["articles"][0].update(
                    {
                        "context_path": manifest["articles"][0]["context_path"].replace(
                            "20260806-v1", "20260806-v2"
                        )
                    }
                ),
            ),
            "source_dataset": (
                "source paths are outside dataset v1",
                lambda manifest: first_image(manifest).update(
                    {
                        "source_path": first_image(manifest)["source_path"].replace(
                            "20260806-v1", "20260806-v2"
                        )
                    }
                ),
            ),
            "retry_namespace": (
                "terminal_provider_retry namespace",
                lambda manifest: manifest["generation_policy"][
                    "terminal_provider_retry"
                ].update(
                    {
                        "namespace": (
                            "clipmaker-lite-test/runs/"
                            "promopages-10060-article-02-20260806-v1/"
                            "terminal-provider-retries-v1"
                        )
                    }
                ),
            ),
            "video_namespace": (
                "video_path escaped its namespace",
                lambda manifest: first_output(manifest).update(
                    {
                        "video_path": (
                            "clipmaker-lite-test/runs/"
                            "promopages-10060-article-02-20260806-v1/videos/"
                            "02-level-rabotaiu-v-level/wan-2.2/01.mp4"
                        )
                    }
                ),
            ),
        }
        for name, (error, mutate) in mutations.items():
            with self.subTest(name=name):
                article_02, _, _ = _promopages_10060_article_02_fixture()
                mutate(article_02)
                with self.assertRaisesRegex(ValueError, error):
                    pages._collect_promopages_10060_article_02_paths(
                        article_02, legacy, set()
                    )

    def test_campaign_extension_is_optional_and_missing_sidecar_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_promopages_collection_fixture(
                root, include_campaign_extension=False
            )
            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            self.assertNotIn(
                pages.PROMOPAGES_10060_EXTENSION_RELATIVE_PATH, paths
            )

    def test_promopages_10060_base_dataset_requires_s3_delivery_overlay(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            _write_promopages_collection_fixture(
                root, include_campaign_extension=False
            )
            (root / pages.PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH).unlink()
            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(FileNotFoundError, "requires its S3 delivery"),
            ):
                pages.collect_site_paths(root)

    def test_campaign_extension_manifest_is_published_but_media_stays_raw(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            extension_paths = _write_promopages_collection_fixture(
                root, include_campaign_extension=True
            )
            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            self.assertIn(
                pages.PROMOPAGES_10060_EXTENSION_RELATIVE_PATH, paths
            )
            for relative_path in extension_paths:
                self.assertNotIn(Path(relative_path), paths)

    def test_campaign_extension_collisions_fail_closed(self):
        legacy, _, _ = _promopages_10060_fixture()
        extension, _, _ = _promopages_10060_campaign_extension_fixture()
        extension["articles"][0]["article_number"] = "01"
        with self.assertRaisesRegex(ValueError, "identity collides"):
            pages._collect_promopages_10060_extension_paths(
                extension, legacy, set()
            )

    def test_campaign_extension_requires_registered_article_union(self):
        legacy, _, _ = _promopages_10060_fixture()
        extension, _, _ = _promopages_10060_campaign_extension_fixture()
        extension["articles"][0]["article_number"] = "99"
        with self.assertRaisesRegex(ValueError, "registered articles 15 through 18"):
            pages._collect_promopages_10060_extension_paths(
                extension, legacy, set()
            )

    def test_campaign_extension_audit_paths_are_safe_and_namespaced(self):
        legacy, _, _ = _promopages_10060_fixture()

        for context_path in (
            "../../outside.json",
            "PROMOPAGES-10060/articles/15-campaign/content.json",
        ):
            with self.subTest(context_path=context_path):
                extension, _, _ = _promopages_10060_campaign_extension_fixture()
                extension["articles"][0]["context_path"] = context_path
                with self.assertRaisesRegex(ValueError, "context_path"):
                    pages._collect_promopages_10060_extension_paths(
                        extension, legacy, set()
                    )

        for manifest_file_path in (
            "/absolute/source.jpg",
            "PROMOPAGES-10060/articles/15-campaign/source.jpg",
        ):
            with self.subTest(manifest_file_path=manifest_file_path):
                extension, _, _ = _promopages_10060_campaign_extension_fixture()
                extension["articles"][0]["images"][0]["image"][
                    "manifest_file_path"
                ] = manifest_file_path
                with self.assertRaisesRegex(ValueError, "manifest_file_path"):
                    pages._collect_promopages_10060_extension_paths(
                        extension, legacy, set()
                    )

    def test_campaign_extension_media_collides_with_any_aggregated_raw_path(self):
        legacy, _, _ = _promopages_10060_fixture()

        extension, source_paths, _ = _promopages_10060_campaign_extension_fixture()
        with self.assertRaisesRegex(ValueError, "source path collision"):
            pages._collect_promopages_10060_extension_paths(
                extension,
                legacy,
                {Path(source_paths[0])},
            )

        extension, _, video_paths = _promopages_10060_campaign_extension_fixture()
        with self.assertRaisesRegex(ValueError, "video path collision"):
            pages._collect_promopages_10060_extension_paths(
                extension,
                legacy,
                {Path(video_paths[0])},
            )

    def test_campaign_extension_accepts_exact_normalized_input_assets(self):
        legacy, _, _ = _promopages_10060_fixture()
        extension, source_paths, video_paths = (
            _promopages_10060_campaign_normalized_extension_fixture()
        )
        remote_paths = set()

        pages._collect_promopages_10060_extension_paths(
            extension, legacy, remote_paths
        )

        self.assertTrue({Path(path) for path in source_paths} <= remote_paths)
        self.assertTrue({Path(path) for path in video_paths} <= remote_paths)
        for asset in pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES.values():
            asset_parent = (
                pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_ASSET_NAMESPACE
                / asset["asset_key"]
            )
            self.assertIn(asset_parent / "normalized.png", remote_paths)
            self.assertIn(asset_parent / "asset.json", remote_paths)

    def test_campaign_extension_normalized_supersede_tampering_fails_closed(self):
        legacy, _, _ = _promopages_10060_fixture()

        def supersede_output(manifest):
            record = next(
                item
                for item in manifest["articles"][0]["images"]
                if item["image"]["image_id"] == "07"
            )
            return next(
                output
                for output in record["outputs"]
                if output["model_id"] == "alibaba/wan-2.7"
            )

        mutations = {
            "wrong_abandoned_job": (
                "superseded active job evidence",
                lambda manifest: supersede_output(manifest)["retry"]["supersede"]
                ["superseded_attempt"].update({"provider_job_id": "other-job"}),
            ),
            "old_job_not_active": (
                "superseded active job evidence",
                lambda manifest: supersede_output(manifest)["retry"]["supersede"]
                ["superseded_attempt"].update({"provider_may_be_active": False}),
            ),
            "request_changed": (
                "identity/request differs",
                lambda manifest: supersede_output(manifest)["retry"]["supersede"]
                ["superseding_attempt"].update({"request_sha256": "b" * 64}),
            ),
            "namespace_escape": (
                "escaped its namespace",
                lambda manifest: supersede_output(manifest)["retry"]["supersede"].update(
                    {
                        "namespace": (
                            pages.PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE
                            / "other"
                            / "superseding-attempt-v1"
                        ).as_posix()
                    }
                ),
            ),
            "selection_hidden": (
                "identity/request differs",
                lambda manifest: supersede_output(manifest).update(
                    {"selected_attempt": "normalized-input-retry-v1"}
                ),
            ),
            "policy_ack_removed": (
                "supersede policy",
                lambda manifest: manifest["generation_policy"][
                    "normalized_input_supersede"
                ].update({"duplicate_billing_risk_acknowledged": False}),
            ),
            "cost_unreserved": (
                "supersede cost",
                lambda manifest: manifest["cost"].update(
                    {"normalized_input_supersede_reservations": 0}
                ),
            ),
        }
        for name, (error, mutate) in mutations.items():
            with self.subTest(name=name):
                extension, _, _ = (
                    _promopages_10060_campaign_normalized_extension_fixture()
                )
                mutate(extension)
                with self.assertRaisesRegex(ValueError, error):
                    pages._collect_promopages_10060_extension_paths(
                        extension,
                        legacy,
                        set(),
                    )

    def test_campaign_extension_normalized_input_mutations_fail_closed(self):
        legacy, _, _ = _promopages_10060_fixture()

        def nested_output(manifest, image_id, model_id):
            for record in manifest["articles"][0]["images"]:
                if record["image"]["image_id"] != image_id:
                    continue
                return next(
                    output
                    for output in record["outputs"]
                    if output["model_id"] == model_id
                )
            raise AssertionError(f"Missing fixture output {image_id}/{model_id}")

        mutations = {
            "original_bytes": (
                "original undersize source audit",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"]["source_transform"]["original"].update(
                    {"bytes": pages.MAX_PROVIDER_SOURCE_BYTES + 1}
                ),
            ),
            "original_dimensions": (
                "original undersize source audit",
                lambda manifest: (
                    manifest["articles"][0]["images"][0]["image"].update(
                        {"width": 300, "height": 300}
                    ),
                    nested_output(manifest, "05", "alibaba/wan-2.2")["retry"]
                    ["source_transform"]["original"].update(
                        {"width": 300, "height": 300}
                    ),
                ),
            ),
            "normalized_sha": (
                "repository-raw asset audit",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"]["source_transform"]["normalized"].update(
                    {"sha256": "f" * 64}
                ),
            ),
            "normalized_dimensions": (
                "repository-raw asset audit",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"]["source_transform"]["normalized"].update(
                    {"height": 239}
                ),
            ),
            "normalized_format": (
                "repository-raw asset audit",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"]["source_transform"]["normalized"].update(
                    {"format": "JPEG"}
                ),
            ),
            "raw_commit": (
                "repository-raw asset audit",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"]["source_transform"]["normalized"].update(
                    {"source_commit_sha": "0" * 40}
                ),
            ),
            "unsafe_raw_path": (
                "repository_path",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"]["source_transform"]["normalized"].update(
                    {"repository_path": "../normalized.png"}
                ),
            ),
            "per_model_asset_drift": (
                "share one frozen image asset",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.7"
                )["retry"]["source_transform"]["normalized"].update(
                    {"metadata_sha256": "f" * 64}
                ),
            ),
            "retry_namespace": (
                "allowed namespace",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                )["retry"].update(
                    {
                        "namespace": "wrong/normalized-retry",
                        "envelope_path": "wrong/normalized-retry/retry.json",
                    }
                ),
            ),
            "reservation_count": (
                "cost accounting",
                lambda manifest: manifest["cost"].update(
                    {"normalized_input_retry_reservations": 5}
                ),
            ),
            "policy_source": (
                "generation policy",
                lambda manifest: manifest["generation_policy"][
                    "normalized_input_retry"
                ]["eligible_sources"][0].update({"image_id": "99"}),
            ),
            "missing_wan_retry": (
                "both Wan normalized retries",
                lambda manifest: nested_output(
                    manifest, "05", "alibaba/wan-2.2"
                ).update({"retry": None, "selected_attempt": "primary"}),
            ),
        }
        for name, (error, mutate) in mutations.items():
            with self.subTest(name=name):
                extension, _, _ = (
                    _promopages_10060_campaign_normalized_extension_fixture()
                )
                mutate(extension)
                with self.assertRaisesRegex(ValueError, error):
                    pages._collect_promopages_10060_extension_paths(
                        extension, legacy, set()
                    )

    def test_runtime_allowlist_is_complete_and_within_pages_limits(self):
        if (
            not ADDITIONAL_MANIFEST_PATH.is_file()
            or not CASE_21_MANIFEST_PATH.is_file()
            or not PROMOPAGES_10060_MANIFEST_PATH.is_file()
            or not PROMOPAGES_10060_S3_DELIVERY_PATH.is_file()
            or not PROMOPAGES_10060_S3_ARTICLES_PATH.is_file()
            or not TUNE_MANIFEST_PATH.is_file()
            or any(not (ROOT / path).is_file() for path in pages.TUNE_STATIC_FILES)
        ):
            self.skipTest(
                "Final Step 5 delivery and Step 8 Tune files are not available"
            )
        tune_manifest = json.loads(TUNE_MANIFEST_PATH.read_text(encoding="utf-8"))
        if tune_manifest.get("schema_version") != 2:
            self.skipTest("Final Step 8 Tune v5 manifest is not available")

        delivery = json.loads(
            PROMOPAGES_10060_S3_DELIVERY_PATH.read_text(encoding="utf-8")
        )
        covered_video = ROOT / next(
            output["source_video_path"]
            for output in delivery["outputs"]
            if output["article_slug"] == pages.PROMOPAGES_10060_ARTICLE_02_SLUG
        )
        real_is_file = Path.is_file

        def is_file_except_covered_video(path):
            if path == covered_video:
                return False
            return real_is_file(path)

        with mock.patch.object(Path, "is_file", is_file_except_covered_video):
            paths = pages.collect_site_paths(ROOT)
        total_bytes = pages.site_size(ROOT, paths)

        self.assertEqual(
            len(paths),
            253
            + len(pages.TUNE_STATIC_FILES)
            + 1
            + int(PROMOPAGES_10060_ARTICLE_02_PATH.is_file())
            + int(PROMOPAGES_10060_EXTENSION_PATH.is_file())
            + int(PROMOPAGES_10060_CAMPAIGN_20260807_PATH.is_file()),
        )
        self.assertGreater(total_bytes, 900_000_000)
        self.assertLessEqual(total_bytes, pages.MAX_SITE_BYTES)
        self.assertIn(Path("clipmaker-lite/index.html"), paths)
        self.assertIn(Path("ab-preparation/index.html"), paths)
        for relative_path in pages.TUNE_STATIC_FILES:
            self.assertIn(Path(relative_path), paths)
        self.assertIn(pages.TUNE_MANIFEST_RELATIVE_PATH, paths)
        self.assertIn(Path("clipmaker-lite-test/manifest.json"), paths)
        self.assertIn(
            Path("clipmaker-lite-test/promopages-9930-manifest.json"), paths
        )
        self.assertIn(Path("clipmaker-lite-test/case-21-manifest.json"), paths)
        self.assertIn(
            Path("clipmaker-lite-test/promopages-10060-manifest.json"), paths
        )
        self.assertIn(pages.PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH, paths)
        self.assertNotIn(pages.PROMOPAGES_10060_S3_ARTICLES_RELATIVE_PATH, paths)
        if PROMOPAGES_10060_ARTICLE_02_PATH.is_file():
            self.assertIn(
                pages.PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH, paths
            )
        if PROMOPAGES_10060_EXTENSION_PATH.is_file():
            self.assertIn(
                pages.PROMOPAGES_10060_EXTENSION_RELATIVE_PATH, paths
            )
        if PROMOPAGES_10060_CAMPAIGN_20260807_PATH.is_file():
            self.assertIn(
                pages.PROMOPAGES_10060_CAMPAIGN_20260807_RELATIVE_PATH, paths
            )
        self.assertIn(Path("manual-review/index.html"), paths)
        tune_repository_videos = {
            Path(target["baseline"]["repository_video_path"])
            for case in tune_manifest["cases"]
            for target in case["targets"]
        }
        tune_repository_videos.update(
            Path(video["repository_video_path"])
            for case in tune_manifest["cases"]
            for target in case["targets"]
            if isinstance(target.get("tuned"), dict)
            if isinstance(video := target["tuned"].get("video"), dict)
            if isinstance(video.get("repository_video_path"), str)
        )
        tune_repository_videos.update(
            Path(video["repository_video_path"])
            for case in tune_manifest["cases"]
            for target in case["targets"]
            if isinstance(target.get("previous_tuned"), dict)
            if isinstance(video := target["previous_tuned"].get("video"), dict)
            if isinstance(video.get("repository_video_path"), str)
        )
        self.assertTrue(tune_repository_videos.isdisjoint(paths))
        self.assertFalse(any(path.parts[0] == "faststart-lab" for path in paths))
        self.assertFalse(any("Prepared videos" in path.as_posix() for path in paths))
        self.assertEqual(
            [path for path in paths if path.suffix == ".md"],
            [Path("model-comparison-5s/fonts/NOTICE.md")],
        )

    def test_extension_media_is_validated_but_excluded_from_pages_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text(
                "clipmaker-lite-test/manifest.json",
                """{
                  "articles": [{
                    "selected_image": {"source_path": "raw/base.jpg"},
                    "outputs": [],
                    "external_outputs": [{
                      "video_path": "raw/external.mp4",
                      "delivery": "repository-raw"
                    }]
                  }]
                }\n""",
            )
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {"source_path": "raw/source.jpg"},
                      "outputs": [{"video_path": "raw/output.mp4"}]
                    }]
                  }]
                }\n""",
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/case-21-source.png",
                        "delivery": "repository-raw"
                      },
                      "outputs": [{
                        "video_path": "raw/case-21-wan22.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan27.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-veo31.mp4",
                        "delivery": "repository-raw"
                      }],
                      "research_outputs": [{
                        "video_path": "raw/case-21-wan27-retry.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan27-monotonic.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan22-erosion.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan27-opacity.mp4",
                        "delivery": "repository-raw"
                      }]
                    }]
                  }],
                  "loop_experiment": {
                    "outputs": [{
                      "video_path": "raw/case-21-loop-sync.mp4",
                      "delivery": "repository-raw"
                    }, {
                      "video_path": "raw/case-21-loop-staggered.mp4",
                      "delivery": "repository-raw"
                    }]
                  },
                  "smooth_experiment": {
                    "outputs": [{
                      "video_path": "raw/case-21-smooth-continuous.mp4",
                      "delivery": "repository-raw"
                    }, {
                      "video_path": "raw/case-21-smooth-staggered.mp4",
                      "delivery": "repository-raw"
                    }]
                  }
                }\n""",
            )
            review_manifest, review_source_paths, review_video_paths = (
                _promopages_10060_fixture(include_provider_filtered=True)
            )
            self.assertEqual(len(review_manifest["outputs"]), 276)
            self.assertEqual(len(review_video_paths), 275)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            source_path = root / "raw/source.jpg"
            base_path = root / "raw/base.jpg"
            video_path = root / "raw/output.mp4"
            external_video_path = root / "raw/external.mp4"
            case_21_source_path = root / "raw/case-21-source.png"
            case_21_video_paths = [
                root / "raw/case-21-wan22.mp4",
                root / "raw/case-21-wan27.mp4",
                root / "raw/case-21-veo31.mp4",
                root / "raw/case-21-wan27-retry.mp4",
                root / "raw/case-21-wan27-monotonic.mp4",
                root / "raw/case-21-wan22-erosion.mp4",
                root / "raw/case-21-wan27-opacity.mp4",
                root / "raw/case-21-loop-sync.mp4",
                root / "raw/case-21-loop-staggered.mp4",
                root / "raw/case-21-smooth-continuous.mp4",
                root / "raw/case-21-smooth-staggered.mp4",
            ]
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(b"source")
            base_path.write_bytes(b"base")
            video_path.write_bytes(b"video")
            external_video_path.write_bytes(b"external-video")
            case_21_source_path.write_bytes(b"case-21-source")
            for case_21_video_path in case_21_video_paths:
                case_21_video_path.write_bytes(b"case-21-video")
            for review_source_path in review_source_paths:
                absolute_source_path = root / review_source_path
                absolute_source_path.parent.mkdir(parents=True, exist_ok=True)
                absolute_source_path.write_bytes(b"review-source")
            for review_video_path in review_video_paths:
                absolute_video_path = root / review_video_path
                absolute_video_path.parent.mkdir(parents=True, exist_ok=True)
                absolute_video_path.write_bytes(b"review-video")
            _write_s3_delivery_fixture(root, review_manifest)

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            expected_site_files = {
                *static_files,
                "raw/base.jpg",
                pages.PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH.as_posix(),
            }
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)
            self.assertNotIn(Path("raw/source.jpg"), paths)
            self.assertNotIn(Path("raw/output.mp4"), paths)
            self.assertNotIn(Path("raw/external.mp4"), paths)
            self.assertNotIn(Path("raw/case-21-source.png"), paths)
            for review_source_path in review_source_paths:
                self.assertNotIn(Path(review_source_path), paths)
            for case_21_video_path in case_21_video_paths:
                self.assertNotIn(case_21_video_path.relative_to(root), paths)
            for review_video_path in review_video_paths:
                self.assertNotIn(Path(review_video_path), paths)

            filtered_nested = review_manifest["articles"][5]["images"][5][
                "outputs"
            ][2]
            filtered_flat = next(
                output
                for output in review_manifest["outputs"]
                if output["article_slug"] == filtered_nested["article_slug"]
                and output["image_id"] == filtered_nested["image_id"]
                and output["model_id"] == filtered_nested["model_id"]
            )
            retry_request_sha = filtered_nested["retry"]["retry_attempt"].pop(
                "request_sha256"
            )
            filtered_flat["retry"]["retry_attempt"].pop("request_sha256", None)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "invalid request_sha256"),
            ):
                pages.collect_site_paths(root)
            filtered_nested["retry"]["retry_attempt"][
                "request_sha256"
            ] = retry_request_sha
            filtered_flat["retry"]["retry_attempt"][
                "request_sha256"
            ] = retry_request_sha

            filtered_nested["status"] = "provider-failed"
            filtered_flat["status"] = "provider-failed"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "non-video status"),
            ):
                pages.collect_site_paths(root)
            filtered_nested["status"] = "provider-filtered"
            filtered_flat["status"] = "provider-filtered"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            ambiguous_nested = review_manifest["articles"][8]["images"][3][
                "outputs"
            ][0]
            ambiguous_flat_index = next(
                index
                for index, output in enumerate(review_manifest["outputs"])
                if output["article_slug"] == ambiguous_nested["article_slug"]
                and output["image_id"] == ambiguous_nested["image_id"]
                and output["model_id"] == ambiguous_nested["model_id"]
            )
            original_video_path = ambiguous_nested["video_path"]

            def replace_ambiguous_output(output):
                nested_copy = json.loads(json.dumps(output))
                review_manifest["articles"][8]["images"][3]["outputs"][
                    0
                ] = nested_copy
                review_manifest["outputs"][ambiguous_flat_index] = json.loads(
                    json.dumps(output)
                )

            unavailable_output = _provider_unavailable_output(
                ambiguous_nested["article_slug"],
                ambiguous_nested["image_id"],
                ambiguous_nested["model_id"],
            )
            replace_ambiguous_output(unavailable_output)
            review_manifest["accepted_output_count"] = 274
            review_manifest["provider_unavailable_output_count"] = 1
            review_manifest["status_summary"]["succeeded"] = 274
            review_manifest["status_summary"]["provider-unavailable"] = 1
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)
            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "primary_attempt"
            ]["outcome_unknown"] = False
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "primary provider outcome"),
            ):
                pages.collect_site_paths(root)
            replace_ambiguous_output(unavailable_output)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "retry_attempt"
            ]["provider_may_be_active"] = True
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "terminal selected attempt"),
            ):
                pages.collect_site_paths(root)
            replace_ambiguous_output(unavailable_output)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "retry_attempt"
            ]["request_sha256"] = "c" * 64
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "binding differs"),
            ):
                pages.collect_site_paths(root)

            success_output = _ambiguous_retry_success_output(
                ambiguous_nested["article_slug"],
                ambiguous_nested["image_id"],
                ambiguous_nested["model_id"],
                original_video_path,
            )
            replace_ambiguous_output(success_output)
            review_manifest["accepted_output_count"] = 275
            review_manifest["provider_unavailable_output_count"] = 0
            review_manifest["status_summary"]["succeeded"] = 275
            review_manifest["status_summary"]["provider-unavailable"] = 0
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                pages.collect_site_paths(root)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "retry_attempt"
            ]["request_sha256"] = "c" * 64
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "binding differs"),
            ):
                pages.collect_site_paths(root)
            replace_ambiguous_output(success_output)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            normalized_article = review_manifest["articles"][10]
            normalized_record = normalized_article["images"][7]
            normalized_image = normalized_record["image"]
            normalized_image.update(
                {
                    "orig_url": NORMALIZED_ORIGINAL_URL,
                    "sha256": (
                        "2cf03435b0ae53b208f033a4ec407750ed494e0cd6ec6c76e1b36e397dd1377d"
                    ),
                    "width": 5445,
                    "height": 3635,
                }
            )
            normalized_flat_indexes = {
                output["model_id"]: index
                for index, output in enumerate(review_manifest["outputs"])
                if output["article_slug"] == normalized_article["article_slug"]
                and output["image_id"] == normalized_image["image_id"]
                and output["model_id"] in {"alibaba/wan-2.2", "alibaba/wan-2.7"}
            }
            original_normalized_video_paths = {
                output["model_id"]: output["video_path"]
                for output in normalized_record["outputs"]
                if output["model_id"] in normalized_flat_indexes
            }

            def replace_normalized_output(model_id, output):
                model_index = list(pages.PROMOPAGES_10060_MODELS).index(model_id)
                normalized_record["outputs"][model_index] = json.loads(
                    json.dumps(output)
                )
                review_manifest["outputs"][normalized_flat_indexes[model_id]] = (
                    json.loads(json.dumps(output))
                )

            normalized_success = _normalized_input_retry_output(
                normalized_article["article_slug"],
                normalized_image,
                "alibaba/wan-2.2",
                exhausted=False,
                video_path=original_normalized_video_paths["alibaba/wan-2.2"],
            )
            normalized_unavailable = _normalized_input_retry_output(
                normalized_article["article_slug"],
                normalized_image,
                "alibaba/wan-2.7",
                exhausted=True,
            )
            replace_normalized_output("alibaba/wan-2.2", normalized_success)
            replace_normalized_output("alibaba/wan-2.7", normalized_unavailable)
            review_manifest["accepted_output_count"] = 274
            review_manifest["provider_unavailable_output_count"] = 1
            review_manifest["status_summary"]["succeeded"] = 274
            review_manifest["status_summary"]["provider-unavailable"] = 1
            review_manifest["cost"] = {
                "normalized_input_retry_version": 1,
                "normalized_input_retry_accounting_cost_usd": 0.35,
                "normalized_input_retry_reservations": 2,
            }
            review_manifest["generation_policy"] = {
                "normalized_input_retry": {
                    "version": 1,
                    "namespace": NORMALIZED_RETRY_NAMESPACE,
                    "shared_asset_namespace": NORMALIZED_ASSET_NAMESPACE,
                    "eligible_source": {
                        "article_slug": "12-dream-island-7-fishek",
                        "image_id": "08",
                    },
                    "models": ["alibaba/wan-2.2", "alibaba/wan-2.7"],
                    "explicit_operator_command_required": True,
                    "maximum_new_paid_submissions_per_eligible_output": 1,
                    "retry2_forbidden": True,
                    "automatic_paid_retries": False,
                    "fallback": False,
                    "primary_receipts_immutable": True,
                    "request_delta_only_image_pointer": True,
                }
            }
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            _write_s3_delivery_fixture(root, review_manifest)
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)
            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)

            normalized_record["outputs"][0]["retry"]["source_transform"][
                "normalized"
            ]["bytes"] = pages.MAX_PROVIDER_SOURCE_BYTES + 1
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "normalized source audit"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.2", normalized_success)

            normalized_record["outputs"][1]["retry"]["source_transform"][
                "request_delta"
            ]["extra"] = "not allowed"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "single allowed image URL"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.7", normalized_unavailable)

            normalized_retry = normalized_record["outputs"][0]["retry"]
            normalized_retry["retry_attempt"]["request_sha256"] = normalized_retry[
                "primary_attempt"
            ]["request_sha256"]
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "request binding"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.2", normalized_success)

            review_manifest["cost"]["normalized_input_retry_reservations"] = 1
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "cost accounting"),
            ):
                pages.collect_site_paths(root)
            review_manifest["cost"]["normalized_input_retry_reservations"] = 2

            review_manifest["generation_policy"]["normalized_input_retry"][
                "namespace"
            ] = "wrong/namespace"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "allowed namespaces"),
            ):
                pages.collect_site_paths(root)
            review_manifest["generation_policy"]["normalized_input_retry"][
                "namespace"
            ] = NORMALIZED_RETRY_NAMESPACE

            normalized_record["outputs"][1]["video_path"] = "unexpected.mp4"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "normalized retry has media"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.7", normalized_unavailable)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            case_21_video_paths[-1].unlink()
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaises(FileNotFoundError),
            ):
                pages.collect_site_paths(root)

    def test_case_21_media_must_use_repository_raw_delivery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/source.png",
                        "delivery": "site"
                      },
                      "outputs": []
                    }]
                  }]
                }\n""",
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "repository-raw"),
            ):
                pages.collect_site_paths(root)

    def test_case_21_loop_outputs_must_use_repository_raw_delivery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/source.png",
                        "delivery": "repository-raw"
                      },
                      "outputs": []
                    }]
                  }],
                  "loop_experiment": {
                    "outputs": [{
                      "video_path": "raw/loop.mp4",
                      "delivery": "site"
                    }]
                  }
                }\n""",
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "loop outputs.*repository-raw"),
            ):
                pages.collect_site_paths(root)

    def test_case_21_smooth_outputs_must_use_repository_raw_delivery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/source.png",
                        "delivery": "repository-raw"
                      },
                      "outputs": []
                    }]
                  }],
                  "smooth_experiment": {
                    "outputs": [{
                      "video_path": "raw/smooth.mp4",
                      "delivery": "site"
                    }]
                  }
                }\n""",
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "smooth outputs.*repository-raw"),
            ):
                pages.collect_site_paths(root)

    def test_promopages_10060_media_transport_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                '{"articles": []}\n',
            )
            review_manifest, _, _ = _promopages_10060_fixture(
                first_source_delivery="site"
            )
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(
                    ValueError,
                    "PROMOPAGES-10060 source images.*repository-raw",
                ),
            ):
                pages.collect_site_paths(root)

    def test_rejects_paths_that_can_escape_the_site_root(self):
        for value in ("../secret", "/absolute", "folder/../secret", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    pages._safe_relative_path(value)

    def test_builder_refuses_to_overwrite_an_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                pages.build_site(ROOT, output)


if __name__ == "__main__":
    unittest.main()
