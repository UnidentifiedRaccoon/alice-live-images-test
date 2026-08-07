#!/usr/bin/env python3
"""Build the exact static payload published from the gh-pages branch.

The repository is larger than the GitHub Pages 1 GB published-site limit.  This
builder follows only runtime references used by the six demo screens and
copies those files into an isolated directory while preserving their paths.
"""

from __future__ import annotations

import argparse
import hashlib
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
PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH = Path(
    "clipmaker-lite-test/promopages-10060-article-02-20260806-v2-manifest.json"
)
PROMOPAGES_10060_ARTICLE_02_ROLE = "promopages-10060-article-02"
PROMOPAGES_10060_ARTICLE_02_BATCH_ID = (
    "promopages-10060-article-02-20260806-v2"
)
PROMOPAGES_10060_ARTICLE_02_DATASET_PREFIX = (
    "PROMOPAGES-10060-article-02-20260806-v1"
)
PROMOPAGES_10060_ARTICLE_02_NUMBER = "02"
PROMOPAGES_10060_ARTICLE_02_SLUG = "02-level-rabotaiu-v-level"
PROMOPAGES_10060_ARTICLE_02_TITLE = (
    "Работаю в Level: почему купил квартиру от нашей компании"
)
PROMOPAGES_10060_ARTICLE_02_IMAGE_COUNT = 11
PROMOPAGES_10060_ARTICLE_02_OUTPUT_COUNT = 33
PROMOPAGES_10060_ARTICLE_02_SOURCE_ROOT = (
    Path("PROMOPAGES-9857")
    / PROMOPAGES_10060_ARTICLE_02_DATASET_PREFIX
    / "articles"
)
PROMOPAGES_10060_ARTICLE_02_CONTEXT_ROOT = (
    Path("PROMOPAGES-9884")
    / PROMOPAGES_10060_ARTICLE_02_DATASET_PREFIX
    / "articles"
)
PROMOPAGES_10060_ARTICLE_02_MANIFEST_ROOT = (
    Path(PROMOPAGES_10060_ARTICLE_02_DATASET_PREFIX) / "articles"
)
PROMOPAGES_10060_ARTICLE_02_RUN_ROOT = (
    Path("clipmaker-lite-test/runs") / PROMOPAGES_10060_ARTICLE_02_BATCH_ID
)
PROMOPAGES_10060_ARTICLE_02_ARTIFACT_ROOT = Path(
    "artifacts/clipmaker-lite/v1"
)
PROMOPAGES_10060_ARTICLE_02_MODEL_DIRECTORIES = {
    "alibaba/wan-2.2": "wan-2.2",
    "alibaba/wan-2.7": "wan-2.7",
    "google/veo-3.1-lite": "veo-3.1-lite",
}
PROMOPAGES_10060_EXTENSION_RELATIVE_PATH = Path(
    "clipmaker-lite-test/promopages-10060-campaigns-20260805-v1-manifest.json"
)
PROMOPAGES_10060_EXTENSION_ROLE = "promopages-10060-campaign-extension"
PROMOPAGES_10060_EXTENSION_BATCH_ID = "promopages-10060-campaigns-20260805-v1"
PROMOPAGES_10060_EXTENSION_DATASET_PREFIX = (
    "PROMOPAGES-10060-campaigns-20260805-v1"
)
PROMOPAGES_10060_EXTENSION_ARTICLE_NUMBERS = ("15", "16", "17", "18")
PROMOPAGES_10060_EXTENSION_CONTEXT_ROOT = (
    Path("PROMOPAGES-9884")
    / PROMOPAGES_10060_EXTENSION_DATASET_PREFIX
    / "articles"
)
PROMOPAGES_10060_EXTENSION_MANIFEST_ROOT = (
    Path(PROMOPAGES_10060_EXTENSION_DATASET_PREFIX) / "articles"
)
PROMOPAGES_10060_CAMPAIGN_20260807_RELATIVE_PATH = Path(
    "clipmaker-lite-test/promopages-10060-campaigns-20260807-v1-manifest.json"
)
PROMOPAGES_10060_CAMPAIGN_20260807_ROLE = (
    "promopages-10060-campaigns-20260807-extension"
)
PROMOPAGES_10060_CAMPAIGN_20260807_BATCH_ID = (
    "promopages-10060-campaigns-20260807-v1"
)
PROMOPAGES_10060_CAMPAIGN_20260807_DATASET_PREFIX = (
    "PROMOPAGES-10060-campaigns-20260807-v1"
)
PROMOPAGES_10060_CAMPAIGN_20260807_ARTICLE_NUMBERS = ("19", "20", "21")
PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH = Path(
    "clipmaker-lite-test/promopages-10060-s3-delivery.json"
)
PROMOPAGES_10060_S3_ARTICLES_RELATIVE_PATH = Path(
    "PROMOPAGES-10060/s3-export/articles.json"
)
PROMOPAGES_10060_S3_DELIVERY_OUTPUT_COUNT = 508
PROMOPAGES_10060_S3_BUCKET = "promopages-front-bundles"
PROMOPAGES_10060_S3_OBJECT_PREFIX = "front-images/exp_video/"
PROMOPAGES_10060_S3_PUBLIC_BASE_URL = (
    "https://yastatic.net/s3/promopages-front-bundles/"
)
PROMOPAGES_10060_S3_MODEL_DIRECTORIES = {
    "alibaba/wan-2.2": "wan_2_2",
    "alibaba/wan-2.7": "wan_2_7",
    "google/veo-3.1-lite": "veo_3_1",
}
PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE = (
    Path("clipmaker-lite-test/runs")
    / PROMOPAGES_10060_EXTENSION_BATCH_ID
    / "normalized-input-retries-v1"
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_ASSET_NAMESPACE = (
    Path("clipmaker-lite-test/runs")
    / PROMOPAGES_10060_EXTENSION_BATCH_ID
    / "normalized-input-assets-v1"
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCE_COMMIT = (
    "25995ee6ea168d2ae7025e5a416bc008ae17a908"
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES = {
    ("18-volma-plitochnyi-klei", "05"): {
        "source_sha256": (
            "95a38e9469f6055c7eab934ab7173af57d5445112e835e200a83964f74938543"
        ),
        "asset_key": "660c32c4d1331cb3a82d",
        "sha256": (
            "4ad98c730c783a63bce382ecffe640d51c936b3ccaec019b637861f8ddbf5b23"
        ),
        "bytes": 46_883,
        "width": 882,
        "height": 256,
        "format": "PNG",
    },
    ("18-volma-plitochnyi-klei", "07"): {
        "source_sha256": (
            "07fd4373396697d3078265a72337a759d591449deb6cafe9869e9d2f92fb43e8"
        ),
        "asset_key": "0535f187b92384618210",
        "sha256": (
            "7f71227971a99ca0f204eccadb89a706128eabfb6022657bf8718e952fca70e4"
        ),
        "bytes": 57_771,
        "width": 828,
        "height": 256,
        "format": "PNG",
    },
    ("18-volma-plitochnyi-klei", "08"): {
        "source_sha256": (
            "ff2fa123c99e8b82a954af9870660faa5306e3d6ebb7c57675df542077fbaa03"
        ),
        "asset_key": "2d974dbe489b2e6617a3",
        "sha256": (
            "1a005159d7efaee55f2124844851b7135f28cccfcad0463ad1ac2f5dec1f589a"
        ),
        "bytes": 246_119,
        "width": 998,
        "height": 256,
        "format": "PNG",
    },
}
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
PROMOPAGES_10060_NORMALIZED_SUPERSEDE_SELECTION = (
    "normalized-input-superseding-attempt-v1"
)
PROMOPAGES_10060_NORMALIZED_SUPERSEDE_EXHAUSTED_SELECTION = (
    "normalized-input-superseding-attempt-v1-exhausted"
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_KEY = (
    "18-volma-plitochnyi-klei",
    "07",
    "alibaba/wan-2.7",
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_JOB_ID = (
    "novcFDcwbuZkgtrmgQIY"
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_DIRECTORY = (
    "superseding-attempt-v1"
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_NAMESPACE = (
    PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE
    / "c45a8447813d1b4e4df0"
    / PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_DIRECTORY
)
PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_RUN_ID = (
    "promopages-10060-campaigns-20260805-v1-normalized-input-retry-v1-"
    "c45a8447813d1b4e4df0-18-volma-plitochnyi-klei-07-wan-2-7"
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
    "ab-preparation/index.html",
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


def _safe_extension_audit_path(value: Any, *, label: str) -> Path:
    """Return one canonical POSIX audit path bound by the extension manifest."""

    if not isinstance(value, str) or "\\" in value:
        raise ValueError(f"{label} must be a canonical relative POSIX path")
    try:
        return _safe_relative_path(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a canonical relative POSIX path") from exc


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_article_02_raw_media(
    root: Path,
    manifest: dict[str, Any],
    *,
    skip_video_paths: set[Path] | None = None,
) -> None:
    skip_video_paths = skip_video_paths or set()
    article = manifest["articles"][0]
    for record in article["images"]:
        image = record["image"]
        source_path = root / _safe_extension_audit_path(
            image["source_path"], label="Article 02 source_path"
        )
        if (
            not source_path.is_file()
            or source_path.is_symlink()
            or _sha256_file(source_path) != image["sha256"]
        ):
            raise ValueError(
                f"Article 02 raw source hash differs: {image['source_path']}"
            )
        for output in record["outputs"]:
            relative_video_path = _safe_extension_audit_path(
                output["video_path"], label="Article 02 video_path"
            )
            if relative_video_path in skip_video_paths:
                continue
            video_path = root / relative_video_path
            media = output["media"]
            if (
                not video_path.is_file()
                or video_path.is_symlink()
                or video_path.stat().st_size != media["bytes"]
                or _sha256_file(video_path) != media["sha256"]
            ):
                raise ValueError(
                    f"Article 02 raw video hash differs: {output['video_path']}"
                )


def _validate_promopages_10060_s3_delivery(
    delivery_manifest: dict[str, Any],
    routing_config: dict[str, Any],
    *source_manifests: dict[str, Any],
) -> set[Path]:
    """Bind the verified S3 overlay to every canonical available MP4."""

    label = "PROMOPAGES-10060 S3 delivery overlay"
    if (
        not isinstance(routing_config, dict)
        or set(routing_config) != {"schema_version", "ticket", "articles"}
        or routing_config.get("schema_version") != 1
        or routing_config.get("ticket") != "PROMOPAGES-10060"
        or not isinstance(routing_config.get("articles"), list)
        or not routing_config["articles"]
    ):
        raise ValueError(f"{label} routing config identity is invalid")

    routing_fields = {
        "article_number",
        "article_slug",
        "label",
        "url",
        "cabinet",
        "campaign_ids",
        "publication_id",
        "source_status",
        "expected_image_count",
        "expected_ready_output_count",
    }
    delivery_article_fields = {
        "article_slug",
        "cabinet_slug",
        "cabinet_id",
        "publication_id",
    }
    expected_delivery_articles: list[dict[str, str]] = []
    routes_by_slug: dict[str, dict[str, Any]] = {}
    expected_output_count = 0
    for article in routing_config["articles"]:
        if (
            not isinstance(article, dict)
            or set(article) != routing_fields
            or not isinstance(article.get("article_number"), str)
            or len(article["article_number"]) != 2
            or not article["article_number"].isdigit()
            or not isinstance(article.get("article_slug"), str)
            or not article["article_slug"].strip()
            or not isinstance(article.get("label"), str)
            or not article["label"].strip()
            or not isinstance(article.get("url"), str)
            or not article["url"].startswith("https://")
            or not isinstance(article.get("cabinet"), dict)
            or set(article["cabinet"]) != {"name", "slug", "id"}
            or not all(
                isinstance(article["cabinet"].get(field), str)
                and article["cabinet"][field].strip()
                for field in ("name", "slug", "id")
            )
            or not isinstance(article.get("campaign_ids"), list)
            or not article["campaign_ids"]
            or not all(
                isinstance(campaign_id, str) and campaign_id.strip()
                for campaign_id in article["campaign_ids"]
            )
            or not isinstance(article.get("publication_id"), str)
            or not article["publication_id"].strip()
            or article.get("source_status") != "available"
            or not isinstance(article.get("expected_image_count"), int)
            or isinstance(article["expected_image_count"], bool)
            or article["expected_image_count"] <= 0
            or not isinstance(article.get("expected_ready_output_count"), int)
            or isinstance(article["expected_ready_output_count"], bool)
            or article["expected_ready_output_count"] <= 0
            or article["article_slug"] in routes_by_slug
        ):
            raise ValueError(f"{label} routing config article is invalid")
        routes_by_slug[article["article_slug"]] = article
        expected_output_count += article["expected_ready_output_count"]
        expected_delivery_articles.append(
            {
                "article_slug": article["article_slug"],
                "cabinet_slug": article["cabinet"]["slug"],
                "cabinet_id": article["cabinet"]["id"],
                "publication_id": article["publication_id"],
            }
        )

    if any(set(article) != delivery_article_fields for article in expected_delivery_articles):
        raise AssertionError("Internal delivery article projection is invalid")

    expected_identity = {
        "schema_version": 1,
        "manifest_role": "promopages-10060-s3-delivery",
        "ticket": "PROMOPAGES-10060",
        "bucket": PROMOPAGES_10060_S3_BUCKET,
        "object_prefix": PROMOPAGES_10060_S3_OBJECT_PREFIX,
        "public_base_url": PROMOPAGES_10060_S3_PUBLIC_BASE_URL,
        "verified_output_count": expected_output_count,
    }
    if (
        not isinstance(delivery_manifest, dict)
        or set(delivery_manifest) != {*expected_identity, "articles", "outputs"}
        or any(
            delivery_manifest.get(field) != value
            for field, value in expected_identity.items()
        )
    ):
        raise ValueError(f"{label} identity is invalid")
    if delivery_manifest.get("articles") != expected_delivery_articles:
        raise ValueError(f"{label} article routing differs from authoritative config")

    allowed_source_roles = (
        "promopages-10060-all-images",
        PROMOPAGES_10060_ARTICLE_02_ROLE,
        PROMOPAGES_10060_EXTENSION_ROLE,
        PROMOPAGES_10060_CAMPAIGN_20260807_ROLE,
    )
    source_roles = tuple(
        manifest.get("manifest_role")
        for manifest in source_manifests
        if isinstance(manifest, dict)
    )
    if (
        not source_manifests
        or len(source_roles) != len(source_manifests)
        or source_roles[0] != allowed_source_roles[0]
        or len(set(source_roles)) != len(source_roles)
        or any(role not in allowed_source_roles for role in source_roles)
        or tuple(sorted(source_roles, key=allowed_source_roles.index)) != source_roles
    ):
        raise ValueError(f"{label} canonical source manifest set is invalid")

    canonical_outputs: dict[
        tuple[str, str, str], tuple[Path, str, int]
    ] = {}
    canonical_video_paths: set[Path] = set()
    for source_manifest in source_manifests:
        outputs = source_manifest.get("outputs")
        if not isinstance(outputs, list):
            raise ValueError(f"{label} canonical source outputs are invalid")
        for output in outputs:
            if not isinstance(output, dict):
                raise ValueError(f"{label} canonical source output is invalid")
            video_value = output.get("video_path")
            if video_value is None:
                continue
            media = output.get("media")
            key = (
                output.get("article_slug"),
                output.get("image_id"),
                output.get("model_id"),
            )
            if (
                not all(isinstance(value, str) and value for value in key)
                or key[2] not in PROMOPAGES_10060_MODELS
                or output.get("status") not in PROMOPAGES_10060_MEDIA_STATUSES
                or not isinstance(media, dict)
                or not _is_sha256(media.get("sha256"))
                or not isinstance(media.get("bytes"), int)
                or isinstance(media["bytes"], bool)
                or media["bytes"] <= 0
            ):
                raise ValueError(f"{label} canonical available output is invalid")
            video_path = _safe_extension_audit_path(
                video_value,
                label=f"{label} canonical source_video_path",
            )
            if (
                video_value != video_path.as_posix()
                or video_path.suffix.lower() != ".mp4"
            ):
                raise ValueError(f"{label} canonical output is not an MP4")
            if key in canonical_outputs:
                raise ValueError(f"{label} canonical logical output is duplicated")
            if video_path in canonical_video_paths:
                raise ValueError(f"{label} canonical source path is duplicated")
            canonical_outputs[key] = (
                video_path,
                media["sha256"],
                media["bytes"],
            )
            canonical_video_paths.add(video_path)

    canonical_counts_by_article = {
        article_slug: sum(1 for key in canonical_outputs if key[0] == article_slug)
        for article_slug in routes_by_slug
    }
    if (
        set(key[0] for key in canonical_outputs) != set(routes_by_slug)
        or any(
            canonical_counts_by_article[article_slug]
            != route["expected_ready_output_count"]
            for article_slug, route in routes_by_slug.items()
        )
        or len(canonical_outputs) != expected_output_count
    ):
        raise ValueError(
            f"{label} canonical outputs differ from authoritative routing config"
        )

    outputs = delivery_manifest.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != expected_output_count:
        raise ValueError(
            f"{label} must contain exactly "
            f"{expected_output_count} verified outputs"
        )

    row_fields = {
        "article_slug",
        "image_id",
        "model_id",
        "source_video_path",
        "sha256",
        "bytes",
        "object_key",
        "yastatic_url",
    }
    seen_keys: set[tuple[str, str, str]] = set()
    seen_video_paths: set[Path] = set()
    seen_object_keys: set[Path] = set()
    for row in outputs:
        if not isinstance(row, dict) or set(row) != row_fields:
            raise ValueError(f"{label} output shape is invalid")
        key = (row["article_slug"], row["image_id"], row["model_id"])
        if (
            not all(isinstance(value, str) and value for value in key)
            or key[2] not in PROMOPAGES_10060_MODELS
        ):
            raise ValueError(f"{label} logical output triple is invalid")
        if key in seen_keys:
            raise ValueError(f"{label} logical output triple is duplicated")
        canonical = canonical_outputs.get(key)
        if canonical is None:
            raise ValueError(f"{label} contains an unexpected logical output")

        source_video_path = _safe_extension_audit_path(
            row["source_video_path"], label=f"{label} source_video_path"
        )
        if (
            row["source_video_path"] != source_video_path.as_posix()
            or source_video_path != canonical[0]
        ):
            raise ValueError(f"{label} source path differs from canonical output")
        if source_video_path in seen_video_paths:
            raise ValueError(f"{label} source path is duplicated")
        if (
            row["sha256"] != canonical[1]
            or row["bytes"] != canonical[2]
            or not _is_sha256(row["sha256"])
            or not isinstance(row["bytes"], int)
            or isinstance(row["bytes"], bool)
            or row["bytes"] <= 0
        ):
            raise ValueError(f"{label} hash or byte size differs from canonical output")

        object_key = _safe_extension_audit_path(
            row["object_key"], label=f"{label} object_key"
        )
        if row["object_key"] != object_key.as_posix():
            raise ValueError(f"{label} object key is not canonical")
        route = routes_by_slug[key[0]]
        expected_filename = (
            f"image_{int(key[1]):02d}--sha256-{row['sha256'][:12]}.mp4"
            if key[1].isdigit()
            else None
        )
        expected_object_key = (
            f"{PROMOPAGES_10060_S3_OBJECT_PREFIX}"
            f"{route['cabinet']['slug']}__{route['cabinet']['id']}/"
            f"{route['publication_id']}/"
            f"{PROMOPAGES_10060_S3_MODEL_DIRECTORIES[key[2]]}/"
            f"{expected_filename}"
            if expected_filename is not None
            else None
        )
        if (
            row["object_key"] != expected_object_key
            or any(
                not character.isascii()
                or not (character.isalnum() or character in "/-._")
                for character in row["object_key"]
            )
        ):
            raise ValueError(f"{label} object key differs from authoritative route")
        if object_key in seen_object_keys:
            raise ValueError(f"{label} object key is duplicated")
        if row["yastatic_url"] != (
            PROMOPAGES_10060_S3_PUBLIC_BASE_URL + row["object_key"]
        ):
            raise ValueError(f"{label} yastatic URL does not match its object key")

        seen_keys.add(key)
        seen_video_paths.add(source_video_path)
        seen_object_keys.add(object_key)

    if seen_keys != set(canonical_outputs):
        raise ValueError(f"{label} has missing or extra canonical outputs")
    return seen_video_paths


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


def _extension_normalized_supersede_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "namespace": (
            PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_NAMESPACE.as_posix()
        ),
        "explicit_operator_command_required": True,
        "operator_authorized_active_job": True,
        "automatic_retry": False,
        "maximum_new_paid_submissions": 1,
        "retry2_forbidden": True,
        "one_off_allowlist": {
            "article_slug": "18-volma-plitochnyi-klei",
            "image_id": "07",
            "model_id": "alibaba/wan-2.7",
            "normalized_retry_provider_run_id": (
                PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_RUN_ID
            ),
            "active_provider_job_id": (
                PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_JOB_ID
            ),
        },
        "duplicate_submission_risk_acknowledged": True,
        "duplicate_billing_risk_acknowledged": True,
        "same_verified_lite_result": True,
        "same_normalized_source": True,
        "same_prompt": True,
        "same_model": True,
        "same_route": True,
        "same_seed": True,
        "same_request": True,
        "fallback": False,
        "route_discovery": False,
        "primary_receipt_immutable": True,
        "normalized_retry_envelope_immutable": True,
        "superseded_receipt_immutable": True,
    }


def _validate_extension_normalized_supersede(
    output: dict[str, Any],
    retry: dict[str, Any],
    *,
    label: str,
    exhausted: bool,
) -> dict[str, Any] | None:
    """Validate the sole operator-authorized successor to an active retry."""

    supersede = retry.get("supersede")
    if supersede is None:
        return None
    if (
        (output.get("article_slug"), output.get("image_id"), output.get("model_id"))
        != PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_KEY
        or not isinstance(supersede, dict)
        or supersede.get("version") != 1
        or supersede.get("exhausted") is not exhausted
        or not isinstance(supersede.get("namespace"), str)
        or not isinstance(supersede.get("envelope_path"), str)
        or not _is_sha256(supersede.get("envelope_sha256"))
    ):
        raise ValueError(f"{label} normalized supersede audit is invalid")

    normalized_namespace = _safe_extension_audit_path(
        retry.get("namespace"), label=f"{label} normalized retry namespace"
    )
    supersede_namespace = _safe_extension_audit_path(
        supersede["namespace"], label=f"{label} supersede namespace"
    )
    supersede_envelope = _safe_extension_audit_path(
        supersede["envelope_path"], label=f"{label} supersede envelope"
    )
    if (
        supersede_namespace
        != normalized_namespace
        / PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_DIRECTORY
        or supersede_namespace
        != PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_NAMESPACE
        or supersede_envelope != supersede_namespace / "supersede.json"
    ):
        raise ValueError(f"{label} normalized supersede escaped its namespace")

    superseded = supersede.get("superseded_attempt")
    selected = supersede.get("superseding_attempt")
    if not isinstance(superseded, dict) or not isinstance(selected, dict):
        raise ValueError(f"{label} normalized supersede attempts are missing")
    if (
        superseded.get("provider_job_id")
        != PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_JOB_ID
        or superseded.get("provider_run_id")
        != PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDED_RUN_ID
        or superseded.get("status") not in {"submitted", "running"}
        or superseded.get("provider_may_be_active") is not True
        or not isinstance(superseded.get("submitted_at"), str)
        or not superseded["submitted_at"].strip()
        or superseded.get("completed_at") is not None
    ):
        raise ValueError(f"{label} superseded active job evidence is invalid")
    if (
        selected.get("status") != output.get("recorded_status")
        or selected.get("provider_may_be_active") is not False
        or not isinstance(selected.get("provider_job_id"), str)
        or not selected["provider_job_id"].strip()
        or selected.get("provider_job_id") == superseded.get("provider_job_id")
        or not isinstance(selected.get("submitted_at"), str)
        or not selected["submitted_at"].strip()
        or not isinstance(selected.get("completed_at"), str)
        or not selected["completed_at"].strip()
        or selected.get("error") != output.get("error")
    ):
        raise ValueError(f"{label} superseding attempt is not terminal")

    for attempt_name, attempt in (
        ("superseded", superseded),
        ("superseding", selected),
    ):
        for field in ("provider_run_id", "run_path", "prompt_path"):
            if not isinstance(attempt.get(field), str) or not attempt[field].strip():
                raise ValueError(f"{label} {attempt_name} attempt lacks {field}")
            if field.endswith("_path"):
                _safe_extension_audit_path(
                    attempt[field], label=f"{label} {attempt_name} {field}"
                )
        for field in ("run_sha256", "prompt_sha256", "request_sha256"):
            if not _is_sha256(attempt.get(field)):
                raise ValueError(f"{label} {attempt_name} attempt has invalid {field}")
    outer_retry = retry.get("retry_attempt")
    if (
        not isinstance(outer_retry, dict)
        or superseded.get("provider_run_id")
        != outer_retry.get("provider_run_id")
        or superseded.get("request_sha256")
        != outer_retry.get("request_sha256")
        or selected.get("provider_run_id") == superseded.get("provider_run_id")
        or selected.get("request_sha256") != superseded.get("request_sha256")
        or output.get("provider_run_id") != selected.get("provider_run_id")
        or output.get("selected_attempt")
        != (
            PROMOPAGES_10060_NORMALIZED_SUPERSEDE_EXHAUSTED_SELECTION
            if exhausted
            else PROMOPAGES_10060_NORMALIZED_SUPERSEDE_SELECTION
        )
    ):
        raise ValueError(f"{label} normalized supersede identity/request differs")
    return selected


def _validate_extension_normalized_input_retry(
    output: dict[str, Any],
    image: dict[str, Any],
    *,
    label: str,
    exhausted: bool,
) -> tuple[tuple[str, str], tuple[Any, ...], set[Path], Path]:
    """Validate the fixed undersize-input retry contract for the extension."""

    retry = output.get("retry")
    if (
        not isinstance(retry, dict)
        or retry.get("retry_kind") != "normalized-input"
        or retry.get("retry_number") != 1
        or retry.get("exhausted") is not exhausted
        or not isinstance(retry.get("namespace"), str)
        or not isinstance(retry.get("envelope_path"), str)
        or not _is_sha256(retry.get("envelope_sha256"))
    ):
        raise ValueError(f"{label} extension normalized-input retry audit is invalid")
    source_key = (output.get("article_slug"), output.get("image_id"))
    expected_asset = PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES.get(source_key)
    if (
        expected_asset is None
        or output.get("model_id") not in {"alibaba/wan-2.2", "alibaba/wan-2.7"}
    ):
        raise ValueError(f"{label} is not an eligible extension normalized input")

    namespace = _safe_extension_audit_path(
        retry["namespace"], label=f"{label} normalized retry namespace"
    )
    envelope_path = _safe_extension_audit_path(
        retry["envelope_path"], label=f"{label} normalized retry envelope"
    )
    if (
        namespace.parent != PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE
        or envelope_path != namespace / "retry.json"
    ):
        raise ValueError(f"{label} normalized retry is outside its allowed namespace")

    transform = retry.get("source_transform")
    original = transform.get("original") if isinstance(transform, dict) else None
    normalized = transform.get("normalized") if isinstance(transform, dict) else None
    delta = transform.get("request_delta") if isinstance(transform, dict) else None
    preparation = transform.get("preparation") if isinstance(transform, dict) else None
    if (
        not isinstance(transform, dict)
        or set(transform)
        != {
            "strategy",
            "original",
            "normalized",
            "request_delta",
            "preparation",
            "minimum_provider_input_dimension",
        }
        or transform.get("strategy") != "deterministic-uniform-upscale"
        or transform.get("minimum_provider_input_dimension") != 240
        or not isinstance(original, dict)
        or not isinstance(normalized, dict)
        or not isinstance(delta, dict)
        or preparation
        != {
            "operation": "uniform-scale",
            "target_height": expected_asset["height"],
            "resampler": "lanczos",
            "crop": False,
            "local_reencode": True,
        }
    ):
        raise ValueError(f"{label} extension normalized source_transform is invalid")

    original_width = original.get("width")
    original_height = original.get("height")
    original_bytes = original.get("bytes")
    if (
        set(original) != {"url", "path", "sha256", "bytes", "width", "height"}
        or not isinstance(original.get("url"), str)
        or not original["url"].startswith("https://avatars.mds.yandex.net/")
        or original.get("url") != image.get("orig_url")
        or original.get("path") != output.get("source_path")
        or original.get("path") != image.get("source_path")
        or original.get("sha256") != image.get("sha256")
        or original.get("sha256") != expected_asset["source_sha256"]
        or not isinstance(original_bytes, int)
        or isinstance(original_bytes, bool)
        or not 0 < original_bytes <= MAX_PROVIDER_SOURCE_BYTES
        or not isinstance(original_width, int)
        or isinstance(original_width, bool)
        or original_width < 1
        or original_width != image.get("width")
        or not isinstance(original_height, int)
        or isinstance(original_height, bool)
        or original_height < 1
        or original_height != image.get("height")
        or min(original_width, original_height) >= 240
    ):
        raise ValueError(f"{label} extension original undersize source audit is invalid")
    _safe_extension_audit_path(
        original["path"], label=f"{label} original source path"
    )

    asset_parent = (
        PROMOPAGES_10060_EXTENSION_NORMALIZED_ASSET_NAMESPACE
        / expected_asset["asset_key"]
    )
    expected_repository_path = asset_parent / "normalized.png"
    expected_metadata_path = asset_parent / "asset.json"
    expected_url = (
        "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
        "alice-live-images-test/"
        f"{PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCE_COMMIT}/"
        f"{expected_repository_path.as_posix()}"
    )
    repository_path = _safe_extension_audit_path(
        normalized.get("repository_path"),
        label=f"{label} normalized repository_path",
    )
    metadata_path = _safe_extension_audit_path(
        normalized.get("metadata_path"),
        label=f"{label} normalized metadata_path",
    )
    if (
        set(normalized)
        != {
            "http_status",
            "url",
            "sha256",
            "bytes",
            "width",
            "height",
            "format",
            "delivery",
            "repository_path",
            "source_commit_sha",
            "metadata_path",
            "metadata_sha256",
        }
        or normalized.get("http_status") != 200
        or normalized.get("url") != expected_url
        or normalized.get("sha256") != expected_asset["sha256"]
        or normalized.get("bytes") != expected_asset["bytes"]
        or normalized.get("width") != expected_asset["width"]
        or normalized.get("height") != expected_asset["height"]
        or normalized.get("width", 0) < 240
        or normalized.get("height", 0) < 240
        or normalized.get("format") != expected_asset["format"]
        or normalized.get("delivery") != "repository-raw"
        or repository_path != expected_repository_path
        or normalized.get("source_commit_sha")
        != PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCE_COMMIT
        or metadata_path != expected_metadata_path
        or not _is_sha256(normalized.get("metadata_sha256"))
    ):
        raise ValueError(
            f"{label} extension normalized repository-raw asset audit is invalid"
        )

    expected_pointer = (
        "/input/image"
        if output["model_id"] == "alibaba/wan-2.2"
        else "/frame_images/0/image_url/url"
    )
    if (
        set(delta) != {"json_pointer", "from", "to", "changed_leaf_count"}
        or delta.get("json_pointer") != expected_pointer
        or delta.get("from") != original["url"]
        or delta.get("to") != normalized["url"]
        or delta.get("changed_leaf_count") != 1
    ):
        raise ValueError(f"{label} normalized request delta is not one image leaf")

    primary = retry.get("primary_attempt")
    retry_attempt = retry.get("retry_attempt")
    if (
        not isinstance(primary, dict)
        or primary.get("status") != "provider-failed"
        or primary.get("provider_may_be_active") is not False
        or not isinstance(primary.get("provider_job_id"), str)
        or not primary["provider_job_id"].strip()
        or not isinstance(primary.get("error"), str)
        or "240" not in primary["error"]
    ):
        raise ValueError(f"{label} normalized primary dimension failure is invalid")
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
            raise ValueError(f"{label} Wan 2.2 dimension evidence is invalid")
    elif (
        primary.get("recorded_status") != "provider-failed"
        or primary.get("recorded_provider_may_be_active") is not False
        or not isinstance(primary.get("submitted_at"), str)
        or not primary["submitted_at"].strip()
        or not isinstance(primary.get("completed_at"), str)
        or not primary["completed_at"].strip()
    ):
        raise ValueError(f"{label} Wan 2.7 dimension evidence is invalid")

    superseding_attempt = _validate_extension_normalized_supersede(
        output,
        retry,
        label=label,
        exhausted=exhausted,
    )
    selected_attempt = superseding_attempt or retry_attempt
    if (
        not isinstance(selected_attempt, dict)
        or selected_attempt.get("status") != output.get("recorded_status")
        or selected_attempt.get("provider_may_be_active") is not False
        or not isinstance(selected_attempt.get("provider_job_id"), str)
        or not selected_attempt["provider_job_id"].strip()
        or not isinstance(selected_attempt.get("submitted_at"), str)
        or not selected_attempt["submitted_at"].strip()
        or not isinstance(selected_attempt.get("completed_at"), str)
        or not selected_attempt["completed_at"].strip()
        or selected_attempt.get("error") != output.get("error")
    ):
        raise ValueError(f"{label} extension normalized selected attempt is not terminal")
    for attempt_name, attempt in (("primary", primary), ("selected", selected_attempt)):
        for field in ("provider_run_id", "run_path", "prompt_path"):
            if not isinstance(attempt.get(field), str) or not attempt[field].strip():
                raise ValueError(f"{label} {attempt_name} audit is missing {field}")
            if field.endswith("_path"):
                _safe_extension_audit_path(
                    attempt[field], label=f"{label} {attempt_name} {field}"
                )
        for field in ("run_sha256", "prompt_sha256", "request_sha256"):
            if not _is_sha256(attempt.get(field)):
                raise ValueError(f"{label} {attempt_name} audit has invalid {field}")
    if (
        output.get("provider_run_id") != selected_attempt["provider_run_id"]
        or primary["provider_run_id"] == selected_attempt["provider_run_id"]
        or primary["request_sha256"] == selected_attempt["request_sha256"]
    ):
        raise ValueError(f"{label} extension normalized retry binding is invalid")

    expected_selection = (
        (
            PROMOPAGES_10060_NORMALIZED_SUPERSEDE_EXHAUSTED_SELECTION
            if exhausted
            else PROMOPAGES_10060_NORMALIZED_SUPERSEDE_SELECTION
        )
        if superseding_attempt is not None
        else PROMOPAGES_10060_NORMALIZED_RETRY_EXHAUSTED_SELECTION
        if exhausted
        else PROMOPAGES_10060_NORMALIZED_RETRY_SELECTION
    )
    if output.get("selected_attempt") != expected_selection:
        raise ValueError(f"{label} normalized selected attempt is invalid")
    if exhausted:
        if (
            output.get("status") != PROMOPAGES_10060_UNAVAILABLE_STATUS
            or output.get("recorded_status") != "provider-failed"
            or output.get("video_path") is not None
            or output.get("media") is not None
            or output.get("contract_check") is not None
            or not isinstance(output.get("error"), str)
            or not output["error"].strip()
        ):
            raise ValueError(f"{label} exhausted normalized retry state is invalid")
    else:
        status = output.get("status")
        contract_check = output.get("contract_check")
        if (
            status not in PROMOPAGES_10060_MEDIA_STATUSES
            or not isinstance(output.get("media"), dict)
            or not isinstance(contract_check, dict)
        ):
            raise ValueError(
                f"{label} successful normalized retry has no accepted media"
            )
        if status == "succeeded" and (
            output.get("error") is not None
            or contract_check.get("conforms") is not True
        ):
            raise ValueError(f"{label} normalized succeeded media audit is invalid")
        if status == "verification-failed" and (
            not isinstance(output.get("error"), str)
            or not output["error"].strip()
            or contract_check.get("conforms") is not False
            or not isinstance(contract_check.get("warnings"), list)
            or not contract_check["warnings"]
        ):
            raise ValueError(
                f"{label} normalized verification warning audit is invalid"
            )

    asset_identity = (
        normalized["url"],
        normalized["repository_path"],
        normalized["sha256"],
        normalized["bytes"],
        normalized["width"],
        normalized["height"],
        normalized["format"],
        normalized["source_commit_sha"],
        normalized["metadata_path"],
        normalized["metadata_sha256"],
    )
    return source_key, asset_identity, {repository_path, metadata_path}, namespace


def _collect_promopages_10060_article_02_paths(
    manifest: dict[str, Any],
    legacy_manifest: dict[str, Any],
    remote_repository_paths: set[Path],
) -> None:
    """Validate the immutable article-02 replacement and register raw media."""

    label = "PROMOPAGES-10060 article 02 replacement"
    expected_merge_contract = {
        "article_key": ["article_slug"],
        "image_key": ["article_slug", "image_id"],
        "output_key": ["article_slug", "image_id", "model_id"],
        "target_field": "articles[].images[]",
    }
    if (
        manifest.get("schema_version") != 1
        or manifest.get("manifest_role") != PROMOPAGES_10060_ARTICLE_02_ROLE
        or manifest.get("ticket") != "PROMOPAGES-10060"
        or manifest.get("batch_id") != PROMOPAGES_10060_ARTICLE_02_BATCH_ID
        or manifest.get("agent_id") != "clipmaker-lite"
        or manifest.get("models") != list(PROMOPAGES_10060_MODELS)
        or manifest.get("merge_contract") != expected_merge_contract
        or manifest.get("article_count") != 1
        or manifest.get("image_count") != PROMOPAGES_10060_ARTICLE_02_IMAGE_COUNT
        or manifest.get("expected_outputs")
        != PROMOPAGES_10060_ARTICLE_02_OUTPUT_COUNT
        or manifest.get("unavailable_articles") != []
        or manifest.get("inventory_manifest")
        != (PROMOPAGES_10060_ARTICLE_02_RUN_ROOT / "inventory.json").as_posix()
        or manifest.get("generation_manifest")
        != (
            PROMOPAGES_10060_ARTICLE_02_RUN_ROOT / "generation-manifest.json"
        ).as_posix()
    ):
        raise ValueError(f"{label} identity is invalid")

    status_summary = manifest.get("status_summary")
    acceptance_policy = manifest.get("acceptance_policy")
    if (
        not isinstance(status_summary, dict)
        or set(status_summary) - PROMOPAGES_10060_MEDIA_STATUSES
        or any(
            not isinstance(count, int) or isinstance(count, bool) or count < 0
            for count in status_summary.values()
        )
        or sum(status_summary.values())
        != PROMOPAGES_10060_ARTICLE_02_OUTPUT_COUNT
        or manifest.get("accepted_output_count")
        != PROMOPAGES_10060_ARTICLE_02_OUTPUT_COUNT
        or manifest.get("terminal_accounted_output_count")
        != PROMOPAGES_10060_ARTICLE_02_OUTPUT_COUNT
        or manifest.get("conforming_output_count")
        != status_summary.get("succeeded", 0)
        or manifest.get("provider_filtered_output_count") != 0
        or manifest.get("provider_unavailable_output_count") != 0
        or not isinstance(acceptance_policy, dict)
        or acceptance_policy.get("allow_contract_warnings") is not True
        or acceptance_policy.get("accepted_complete_statuses")
        != ["succeeded", "verification-failed"]
        or acceptance_policy.get("requires_mp4_and_media") is not True
        or set(acceptance_policy.get("terminal_accounted_without_media", []))
        != {
            PROMOPAGES_10060_FILTERED_STATUS,
            PROMOPAGES_10060_UNAVAILABLE_STATUS,
        }
        or acceptance_policy.get("preserve_recorded_status") is not True
    ):
        raise ValueError(f"{label} terminal accounting is invalid")

    generation_policy = manifest.get("generation_policy")
    if not isinstance(generation_policy, dict):
        raise ValueError(f"{label} generation policy is invalid")
    expected_policy_namespaces = {
        "terminal_provider_retry": (
            PROMOPAGES_10060_ARTICLE_02_RUN_ROOT
            / "terminal-provider-retries-v1"
        ),
        "ambiguous_submit_retry": (
            PROMOPAGES_10060_ARTICLE_02_RUN_ROOT
            / "ambiguous-submit-retries-v1"
        ),
        "normalized_input_retry": (
            PROMOPAGES_10060_ARTICLE_02_RUN_ROOT
            / "normalized-input-retries-v1"
        ),
    }
    if (
        generation_policy.get("route_capacities")
        != {
            "alibaba/wan-2.2": 1,
            "alibaba/wan-2.7": 3,
            "google/veo-3.1-lite": 3,
        }
        or generation_policy.get("exact_model_routes_only") is not True
        or generation_policy.get("route_discovery") is not False
        or generation_policy.get("automatic_fallback") is not False
    ):
        raise ValueError(f"{label} generation policy is invalid")
    for policy_key, expected_namespace in expected_policy_namespaces.items():
        policy = generation_policy.get(policy_key)
        if (
            not isinstance(policy, dict)
            or policy.get("version") != 1
            or policy.get("namespace") != expected_namespace.as_posix()
        ):
            raise ValueError(f"{label} {policy_key} namespace is invalid")
    normalized_policy = generation_policy["normalized_input_retry"]
    if (
        normalized_policy.get("shared_asset_namespace")
        != (
            PROMOPAGES_10060_ARTICLE_02_RUN_ROOT
            / "normalized-input-assets-v1"
        ).as_posix()
        or normalized_policy.get("eligible_sources") != []
    ):
        raise ValueError(f"{label} normalized input namespace is invalid")

    legacy_articles = legacy_manifest.get("articles")
    legacy_unavailable = legacy_manifest.get("unavailable_articles")
    if not isinstance(legacy_articles, list) or not isinstance(
        legacy_unavailable, list
    ):
        raise ValueError(f"{label} legacy manifest is invalid")
    replacement_targets = [
        article
        for article in legacy_unavailable
        if isinstance(article, dict)
        and article.get("article_number") == PROMOPAGES_10060_ARTICLE_02_NUMBER
    ]
    if (
        len(legacy_unavailable) != 1
        or len(replacement_targets) != 1
        or replacement_targets[0].get("article_slug")
        != PROMOPAGES_10060_ARTICLE_02_SLUG
        or replacement_targets[0].get("status") != "source-unavailable"
    ):
        raise ValueError(f"{label} has no exact legacy unavailable target")
    if any(
        isinstance(article, dict)
        and (
            article.get("article_number") == PROMOPAGES_10060_ARTICLE_02_NUMBER
            or article.get("article_slug") == PROMOPAGES_10060_ARTICLE_02_SLUG
        )
        for article in legacy_articles
    ):
        raise ValueError(f"{label} collides with an available legacy article")

    articles = manifest.get("articles")
    if not isinstance(articles, list) or len(articles) != 1:
        raise ValueError(f"{label} must contain only article 02")
    article = articles[0]
    if not isinstance(article, dict):
        raise ValueError(f"{label} article is invalid")
    article_slug = article.get("article_slug")
    if (
        article.get("article_number") != PROMOPAGES_10060_ARTICLE_02_NUMBER
        or article_slug != PROMOPAGES_10060_ARTICLE_02_SLUG
        or article.get("title") != PROMOPAGES_10060_ARTICLE_02_TITLE
        or article.get("url")
        != (
            "https://level-group.promo.page/media/"
            "rabotaiu-v-level-pochemu-kupil-kvartiru-ot-nashei-kompanii-"
            "69ef21df12346c2fdfdffecd_0_0"
        )
        or article.get("image_count")
        != PROMOPAGES_10060_ARTICLE_02_IMAGE_COUNT
    ):
        raise ValueError(f"{label} must contain only the registered article 02")

    context_path = _safe_extension_audit_path(
        article.get("context_path"), label=f"{label} context_path"
    )
    if context_path != (
        PROMOPAGES_10060_ARTICLE_02_CONTEXT_ROOT
        / PROMOPAGES_10060_ARTICLE_02_SLUG
        / "content.json"
    ):
        raise ValueError(f"{label} context_path is outside dataset v1")

    image_records = article.get("images")
    if (
        not isinstance(image_records, list)
        or len(image_records) != PROMOPAGES_10060_ARTICLE_02_IMAGE_COUNT
    ):
        raise ValueError(f"{label} images are incomplete")

    expected_image_ids = tuple(
        f"{index:02d}"
        for index in range(1, PROMOPAGES_10060_ARTICLE_02_IMAGE_COUNT + 1)
    )
    nested_outputs: list[dict[str, Any]] = []
    seen_source_paths: set[Path] = set()
    seen_video_paths: set[Path] = set()
    observed_statuses: dict[str, int] = {}
    expected_primary_root = (
        PROMOPAGES_10060_ARTICLE_02_RUN_ROOT
        / "videos"
        / PROMOPAGES_10060_ARTICLE_02_SLUG
    )

    for expected_image_id, record in zip(expected_image_ids, image_records):
        image = record.get("image") if isinstance(record, dict) else None
        planning = record.get("lite_planning") if isinstance(record, dict) else None
        if (
            not isinstance(image, dict)
            or image.get("image_id") != expected_image_id
            or image.get("order") != int(expected_image_id)
            or image.get("delivery") not in {None, "repository-raw"}
            or not _is_sha256(image.get("sha256"))
            or not isinstance(image.get("width"), int)
            or image["width"] <= 0
            or not isinstance(image.get("height"), int)
            or image["height"] <= 0
            or not isinstance(planning, dict)
        ):
            raise ValueError(f"{label}/{expected_image_id} image identity is invalid")

        file_name = image.get("file")
        if (
            not isinstance(file_name, str)
            or Path(file_name).name != file_name
            or Path(file_name).stem != expected_image_id
        ):
            raise ValueError(f"{label}/{expected_image_id} filename is invalid")
        source_path = _safe_extension_audit_path(
            image.get("source_path"),
            label=f"{label}/{expected_image_id} source_path",
        )
        manifest_file_path = _safe_extension_audit_path(
            image.get("manifest_file_path"),
            label=f"{label}/{expected_image_id} manifest_file_path",
        )
        if (
            source_path
            != (
                PROMOPAGES_10060_ARTICLE_02_SOURCE_ROOT
                / PROMOPAGES_10060_ARTICLE_02_SLUG
                / file_name
            )
            or manifest_file_path
            != (
                PROMOPAGES_10060_ARTICLE_02_MANIFEST_ROOT
                / PROMOPAGES_10060_ARTICLE_02_SLUG
                / file_name
            )
        ):
            raise ValueError(
                f"{label}/{expected_image_id} source paths are outside dataset v1"
            )
        if source_path in seen_source_paths or source_path in remote_repository_paths:
            raise ValueError(f"{label} source path collision: {source_path}")
        seen_source_paths.add(source_path)
        remote_repository_paths.add(source_path)

        run_id = (
            f"{PROMOPAGES_10060_ARTICLE_02_BATCH_ID}-"
            f"{PROMOPAGES_10060_ARTICLE_02_SLUG}-{expected_image_id}"
        )
        provenance = planning.get("provenance")
        if (
            planning.get("run_id") != run_id
            or planning.get("result_path")
            != (
                PROMOPAGES_10060_ARTICLE_02_ARTIFACT_ROOT
                / run_id
                / "result.json"
            ).as_posix()
            or not isinstance(provenance, dict)
            or provenance.get("verified") is not True
            or provenance.get("agent_id") != "clipmaker-lite"
            or provenance.get("models") != list(PROMOPAGES_10060_MODELS)
            or provenance.get("source_image_sha256") != image["sha256"]
            or not _is_sha256(provenance.get("article_context_sha256"))
        ):
            raise ValueError(
                f"{label}/{expected_image_id} Lite provenance is invalid"
            )

        outputs = record.get("outputs")
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
                f"{label}/{expected_image_id} must contain all three models"
            )

        for output in outputs:
            model_id = output["model_id"]
            model_directory = PROMOPAGES_10060_ARTICLE_02_MODEL_DIRECTORIES[model_id]
            output_label = f"{label}/{expected_image_id}/{model_id}"
            if (
                output.get("article_slug") != article_slug
                or output.get("image_id") != expected_image_id
                or output.get("source_path") != source_path.as_posix()
                or output.get("sample_id")
                != f"{article_slug}-{expected_image_id}"
                or output.get("lite_run_id") != run_id
                or output.get("delivery") not in {None, "repository-raw"}
                or output.get("recorded_status") != output.get("status")
                or not isinstance(output.get("provider_run_id"), str)
                or not output["provider_run_id"].strip()
            ):
                raise ValueError(f"{output_label} binding is invalid")

            status = output.get("status")
            media = output.get("media")
            contract_check = output.get("contract_check")
            if (
                status not in PROMOPAGES_10060_MEDIA_STATUSES
                or not isinstance(media, dict)
                or not _is_sha256(media.get("sha256"))
                or not isinstance(media.get("bytes"), int)
                or media["bytes"] <= 0
                or not isinstance(contract_check, dict)
            ):
                raise ValueError(f"{output_label} accepted media audit is invalid")
            if status == "succeeded" and (
                output.get("error") is not None
                or contract_check.get("conforms") is not True
            ):
                raise ValueError(f"{output_label} succeeded audit is invalid")
            if status == "verification-failed" and (
                not isinstance(output.get("error"), str)
                or not output["error"].strip()
                or contract_check.get("conforms") is not False
                or not isinstance(contract_check.get("warnings"), list)
                or not contract_check["warnings"]
            ):
                raise ValueError(f"{output_label} warning audit is invalid")

            primary_namespace = expected_primary_root / model_directory
            selected_namespace = primary_namespace
            selected_attempt = output.get("selected_attempt")
            retry = output.get("retry")
            if selected_attempt == "primary":
                if retry is not None:
                    raise ValueError(f"{output_label} primary retry audit is invalid")
            elif selected_attempt in {
                "terminal-retry-v1",
                PROMOPAGES_10060_AMBIGUOUS_RETRY_SELECTION,
            }:
                if not isinstance(retry, dict):
                    raise ValueError(f"{output_label} retry audit is missing")
                retry_kind = (
                    "ambiguous_submit_retry"
                    if selected_attempt == PROMOPAGES_10060_AMBIGUOUS_RETRY_SELECTION
                    else "terminal_provider_retry"
                )
                retry_parent = expected_policy_namespaces[retry_kind]
                selected_namespace = _safe_extension_audit_path(
                    retry.get("namespace"), label=f"{output_label} retry namespace"
                )
                if (
                    selected_namespace.parent != retry_parent
                    or _safe_extension_audit_path(
                        retry.get("envelope_path"),
                        label=f"{output_label} retry envelope_path",
                    )
                    != selected_namespace / "retry.json"
                    or retry.get("retry_number") != 1
                    or retry.get("exhausted") is not False
                ):
                    raise ValueError(f"{output_label} retry namespace is invalid")
                selected_namespace = selected_namespace / "videos" / model_directory
                primary_attempt = retry.get("primary_attempt")
                retry_attempt = retry.get("retry_attempt")
                if not isinstance(primary_attempt, dict) or not isinstance(
                    retry_attempt, dict
                ):
                    raise ValueError(f"{output_label} retry attempts are invalid")
                for field, suffix in (
                    ("run_path", ".run.json"),
                    ("prompt_path", ".prompt.json"),
                ):
                    if (
                        _safe_extension_audit_path(
                            primary_attempt.get(field),
                            label=f"{output_label} primary {field}",
                        )
                        != primary_namespace / f"{expected_image_id}{suffix}"
                        or _safe_extension_audit_path(
                            retry_attempt.get(field),
                            label=f"{output_label} retry {field}",
                        )
                        != selected_namespace / f"{expected_image_id}{suffix}"
                    ):
                        raise ValueError(
                            f"{output_label} retry audit escaped its namespace"
                        )
                if selected_attempt == PROMOPAGES_10060_AMBIGUOUS_RETRY_SELECTION:
                    _validate_ambiguous_submit_retry(
                        output, label=output_label, exhausted=False
                    )
            else:
                raise ValueError(f"{output_label} selected attempt is invalid")

            expected_paths = {
                "prompt_path": selected_namespace
                / f"{expected_image_id}.prompt.json",
                "run_path": selected_namespace / f"{expected_image_id}.run.json",
                "video_path": selected_namespace / f"{expected_image_id}.mp4",
            }
            for field, expected_path in expected_paths.items():
                actual_path = _safe_extension_audit_path(
                    output.get(field), label=f"{output_label} {field}"
                )
                if actual_path != expected_path:
                    raise ValueError(f"{output_label} {field} escaped its namespace")
            video_path = expected_paths["video_path"]
            if video_path in seen_video_paths or video_path in remote_repository_paths:
                raise ValueError(f"{label} video path collision: {video_path}")
            seen_video_paths.add(video_path)
            remote_repository_paths.add(video_path)
            observed_statuses[status] = observed_statuses.get(status, 0) + 1
            nested_outputs.append(output)

    if article.get("selected_image") != image_records[0]["image"]:
        raise ValueError(f"{label} selected image is not image 01")
    if observed_statuses != status_summary:
        raise ValueError(f"{label} status summary differs from nested outputs")
    if manifest.get("outputs") != nested_outputs:
        raise ValueError(f"{label} flat outputs differ from nested outputs")


def _collect_promopages_10060_extension_paths(
    manifest: dict[str, Any],
    legacy_manifest: dict[str, Any],
    remote_repository_paths: set[Path],
    *,
    label: str = "PROMOPAGES-10060 campaign extension",
    manifest_role: str | None = None,
    batch_id: str | None = None,
    dataset_prefix: str | None = None,
    registered_article_numbers: tuple[str, ...] | None = None,
    additional_existing_manifests: tuple[dict[str, Any], ...] = (),
) -> None:
    """Validate one additive campaign sidecar and register raw media paths."""

    manifest_role = manifest_role or PROMOPAGES_10060_EXTENSION_ROLE
    batch_id = batch_id or PROMOPAGES_10060_EXTENSION_BATCH_ID
    dataset_prefix = dataset_prefix or PROMOPAGES_10060_EXTENSION_DATASET_PREFIX
    registered_article_numbers = tuple(
        sorted(
            registered_article_numbers
            or PROMOPAGES_10060_EXTENSION_ARTICLE_NUMBERS,
            key=int,
        )
    )

    if (
        manifest.get("schema_version") != 1
        or manifest.get("manifest_role") != manifest_role
        or manifest.get("ticket") != "PROMOPAGES-10060"
        or manifest.get("batch_id") != batch_id
        or manifest.get("agent_id") != "clipmaker-lite"
        or manifest.get("models") != list(PROMOPAGES_10060_MODELS)
    ):
        raise ValueError(f"{label} identity is invalid")

    article_count = manifest.get("article_count")
    image_count = manifest.get("image_count")
    expected_outputs = manifest.get("expected_outputs")
    if (
        not isinstance(article_count, int)
        or isinstance(article_count, bool)
        or article_count <= 0
        or not isinstance(image_count, int)
        or isinstance(image_count, bool)
        or image_count <= 0
        or not isinstance(expected_outputs, int)
        or isinstance(expected_outputs, bool)
        or expected_outputs != image_count * len(PROMOPAGES_10060_MODELS)
    ):
        raise ValueError(f"{label} dynamic counts are invalid")

    provider_filtered_count = manifest.get("provider_filtered_output_count")
    provider_unavailable_count = manifest.get("provider_unavailable_output_count")
    if (
        not isinstance(provider_filtered_count, int)
        or isinstance(provider_filtered_count, bool)
        or provider_filtered_count < 0
        or not isinstance(provider_unavailable_count, int)
        or isinstance(provider_unavailable_count, bool)
        or provider_unavailable_count < 0
        or manifest.get("accepted_output_count")
        != expected_outputs - provider_filtered_count - provider_unavailable_count
        or manifest.get("terminal_accounted_output_count") != expected_outputs
    ):
        raise ValueError(f"{label} terminal accounting is invalid")

    status_summary = manifest.get("status_summary")
    acceptance_policy = manifest.get("acceptance_policy")
    if (
        not isinstance(status_summary, dict)
        or status_summary.get(PROMOPAGES_10060_FILTERED_STATUS, 0)
        != provider_filtered_count
        or status_summary.get(PROMOPAGES_10060_UNAVAILABLE_STATUS, 0)
        != provider_unavailable_count
        or any(
            not isinstance(count, int) or isinstance(count, bool) or count < 0
            for count in status_summary.values()
        )
        or sum(status_summary.values()) != expected_outputs
        or not isinstance(acceptance_policy, dict)
        or acceptance_policy.get("requires_mp4_and_media") is not True
        or set(acceptance_policy.get("terminal_accounted_without_media", []))
        != {
            PROMOPAGES_10060_FILTERED_STATUS,
            PROMOPAGES_10060_UNAVAILABLE_STATUS,
        }
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
        raise ValueError(f"{label} acceptance policy is invalid")

    existing_manifests = (legacy_manifest, *additional_existing_manifests)
    legacy_articles = [
        article
        for existing_manifest in existing_manifests
        for article in existing_manifest.get("articles", [])
        if isinstance(article, dict)
    ]
    existing_article_numbers = {
        article.get("article_number")
        for article in legacy_articles
        if isinstance(article, dict)
    }
    existing_article_slugs = {
        article.get("article_slug")
        for article in legacy_articles
        if isinstance(article, dict)
    }
    existing_source_paths = {
        _safe_relative_path(record["image"]["source_path"])
        for article in legacy_articles
        for record in article.get("images", [])
    }
    existing_video_paths = {
        _safe_relative_path(output["video_path"])
        for article in legacy_articles
        for record in article.get("images", [])
        for output in record.get("outputs", [])
        if isinstance(output.get("video_path"), str) and output["video_path"]
    }
    existing_unavailable_numbers = {
        article.get("article_number")
        for existing_manifest in existing_manifests
        for article in existing_manifest.get("unavailable_articles", [])
        if isinstance(article, dict)
    }
    existing_unavailable_slugs = {
        article.get("article_slug")
        for existing_manifest in existing_manifests
        for article in existing_manifest.get("unavailable_articles", [])
        if isinstance(article, dict)
    }
    context_root = Path("PROMOPAGES-9884") / dataset_prefix / "articles"
    manifest_root = Path(dataset_prefix) / "articles"

    articles = manifest.get("articles")
    if not isinstance(articles, list) or len(articles) != article_count:
        raise ValueError(f"{label} articles do not match article_count")
    article_numbers: set[str] = set()
    article_slugs: set[str] = set()
    source_paths: set[Path] = set()
    video_paths: set[Path] = set()
    nested_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    actual_image_count = 0
    actual_filtered_count = 0
    actual_unavailable_count = 0
    previous_article_number = 0
    normalized_retry_keys: set[tuple[str, str, str]] = set()
    normalized_asset_by_source: dict[tuple[str, str], tuple[Any, ...]] = {}
    normalized_source_by_asset: dict[tuple[Any, ...], tuple[str, str]] = {}
    normalized_repository_path_owners: dict[Path, tuple[str, str]] = {}
    normalized_retry_namespaces: set[Path] = set()
    normalized_supersede_keys: set[tuple[str, str, str]] = set()

    def record_normalized_retry(
        output: dict[str, Any],
        image: dict[str, Any],
        *,
        output_label: str,
        exhausted: bool,
    ) -> None:
        source_key, asset_identity, repository_paths, namespace = (
            _validate_extension_normalized_input_retry(
                output,
                image,
                label=output_label,
                exhausted=exhausted,
            )
        )
        logical_key = (*source_key, output["model_id"])
        if logical_key in normalized_retry_keys:
            raise ValueError(f"{output_label} duplicate normalized logical output")
        if namespace in normalized_retry_namespaces:
            raise ValueError(f"{output_label} normalized retry namespace is reused")
        normalized_retry_keys.add(logical_key)
        normalized_retry_namespaces.add(namespace)
        if isinstance(output.get("retry", {}).get("supersede"), dict):
            if logical_key in normalized_supersede_keys:
                raise ValueError(f"{output_label} duplicate normalized supersede")
            normalized_supersede_keys.add(logical_key)

        prior_identity = normalized_asset_by_source.get(source_key)
        if prior_identity is not None and prior_identity != asset_identity:
            raise ValueError(
                f"{output_label} normalized models do not share one frozen image asset"
            )
        prior_source = normalized_source_by_asset.get(asset_identity)
        if prior_source is not None and prior_source != source_key:
            raise ValueError(
                f"{output_label} normalized frozen asset is shared across images"
            )
        normalized_asset_by_source[source_key] = asset_identity
        normalized_source_by_asset[asset_identity] = source_key
        for repository_path in repository_paths:
            prior_owner = normalized_repository_path_owners.get(repository_path)
            if prior_owner is not None and prior_owner != source_key:
                raise ValueError(
                    f"{output_label} normalized repository path is shared across images"
                )
            normalized_repository_path_owners[repository_path] = source_key

    for article in articles:
        if not isinstance(article, dict):
            raise ValueError(f"{label} article must be an object")
        article_number = article.get("article_number")
        article_slug = article.get("article_slug")
        if (
            not isinstance(article_number, str)
            or len(article_number) != 2
            or not article_number.isdigit()
            or int(article_number) <= previous_article_number
            or article_number in article_numbers
            or article_number in existing_article_numbers
            or article_number in existing_unavailable_numbers
            or not isinstance(article_slug, str)
            or not article_slug.strip()
            or article_slug in article_slugs
            or article_slug in existing_article_slugs
            or article_slug in existing_unavailable_slugs
        ):
            raise ValueError(f"{label} article identity collides or is unordered")
        previous_article_number = int(article_number)
        article_numbers.add(article_number)
        article_slugs.add(article_slug)
        image_records = article.get("images")
        context_path = _safe_extension_audit_path(
            article.get("context_path"),
            label=f"{label}/{article_number} context_path",
        )
        expected_context_path = (
            context_root
            / article_slug
            / "content.json"
        )
        if context_path != expected_context_path:
            raise ValueError(
                f"{label} context_path is outside its extension namespace"
            )
        if (
            not isinstance(article.get("title"), str)
            or not article["title"].strip()
            or not isinstance(article.get("url"), str)
            or not article["url"].startswith("https://")
            or not isinstance(image_records, list)
            or not image_records
            or article.get("image_count") != len(image_records)
        ):
            raise ValueError(f"{label} article payload is incomplete")

        image_ids: set[str] = set()
        for record in image_records:
            image = record.get("image") if isinstance(record, dict) else None
            image_id = image.get("image_id") if isinstance(image, dict) else None
            planning = record.get("lite_planning") if isinstance(record, dict) else None
            if (
                not isinstance(image_id, str)
                or len(image_id) != 2
                or not image_id.isdigit()
                or image_id in image_ids
                or image.get("delivery") not in {None, "repository-raw"}
                or not _is_sha256(image.get("sha256"))
                or not isinstance(image.get("manifest_file_path"), str)
                or not image["manifest_file_path"].strip()
                or not isinstance(planning, dict)
                or planning.get("provenance", {}).get("verified") is not True
                or planning.get("provenance", {}).get("agent_id") != "clipmaker-lite"
            ):
                raise ValueError(f"{label} image or Lite provenance is invalid")
            image_ids.add(image_id)
            manifest_file_path = _safe_extension_audit_path(
                image.get("manifest_file_path"),
                label=(
                    f"{label}/{article_number}/{image_id} manifest_file_path"
                ),
            )
            expected_manifest_parent = (
                manifest_root / article_slug
            )
            if manifest_file_path.parent != expected_manifest_parent:
                raise ValueError(
                    f"{label} manifest_file_path is outside its extension namespace"
                )
            source_path = _safe_relative_path(image.get("source_path"))
            if (
                source_path in source_paths
                or source_path in existing_source_paths
                or source_path in remote_repository_paths
            ):
                raise ValueError(f"{label} source path collision: {source_path}")
            source_paths.add(source_path)
            remote_repository_paths.add(source_path)

            outputs = record.get("outputs")
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
                raise ValueError(f"{label} image must contain all three models")
            for output in outputs:
                if (
                    not isinstance(output, dict)
                    or output.get("article_slug") != article_slug
                    or output.get("image_id") != image_id
                    or output.get("delivery") not in {None, "repository-raw"}
                ):
                    raise ValueError(f"{label} output identity or delivery is invalid")
                key = (article_slug, image_id, output["model_id"])
                if key in nested_by_key:
                    raise ValueError(f"{label} logical output collision")
                nested_by_key[key] = output
                status = output.get("status")
                if status == PROMOPAGES_10060_FILTERED_STATUS:
                    _validate_provider_filtered_output(
                        output,
                        label=f"{label}/{article_number}/{image_id}/{output['model_id']}",
                    )
                    actual_filtered_count += 1
                    continue
                if status == PROMOPAGES_10060_UNAVAILABLE_STATUS:
                    retry = output.get("retry")
                    if (
                        isinstance(retry, dict)
                        and retry.get("retry_kind") == "normalized-input"
                    ):
                        record_normalized_retry(
                            output,
                            image,
                            output_label=(
                                f"{label}/{article_number}/{image_id}/"
                                f"{output['model_id']}"
                            ),
                            exhausted=True,
                        )
                    else:
                        _validate_provider_unavailable_output(
                            output,
                            label=(
                                f"{label}/{article_number}/{image_id}/"
                                f"{output['model_id']}"
                            ),
                        )
                    actual_unavailable_count += 1
                    continue
                if status not in PROMOPAGES_10060_MEDIA_STATUSES:
                    raise ValueError(f"{label} output status is invalid")
                video_path = _safe_relative_path(output.get("video_path"))
                if (
                    video_path.suffix.lower() != ".mp4"
                    or video_path in video_paths
                    or video_path in existing_video_paths
                    or video_path in remote_repository_paths
                ):
                    raise ValueError(f"{label} video path collision or invalid MP4")
                retry = output.get("retry")
                if (
                    isinstance(retry, dict)
                    and retry.get("retry_kind") == "normalized-input"
                ):
                    record_normalized_retry(
                        output,
                        image,
                        output_label=(
                            f"{label}/{article_number}/{image_id}/"
                            f"{output['model_id']}"
                        ),
                        exhausted=False,
                    )
                elif (
                    isinstance(retry, dict)
                    and retry.get("retry_kind") == "ambiguous-submit"
                ):
                    _validate_ambiguous_submit_retry(
                        output,
                        label=f"{label}/{article_number}/{image_id}/{output['model_id']}",
                        exhausted=False,
                    )
                video_paths.add(video_path)
                remote_repository_paths.add(video_path)
            actual_image_count += 1

    if normalized_retry_keys:
        expected_normalized_retry_keys = {
            (*source_key, model_id)
            for source_key in PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES
            for model_id in ("alibaba/wan-2.2", "alibaba/wan-2.7")
        }
        if (
            normalized_retry_keys != expected_normalized_retry_keys
            or set(normalized_asset_by_source)
            != set(PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES)
        ):
            raise ValueError(
                f"{label} must contain both Wan normalized retries for images 05/07/08"
            )

        generation_policy = manifest.get("generation_policy")
        normalized_policy = (
            generation_policy.get("normalized_input_retry")
            if isinstance(generation_policy, dict)
            else None
        )
        expected_eligible_sources = [
            {
                "article_slug": article_slug,
                "image_id": image_id,
                "source_sha256": asset["source_sha256"],
                "models": ["alibaba/wan-2.2", "alibaba/wan-2.7"],
                "failure_kind": "minimum-dimension",
                "normalization_strategy": "deterministic-uniform-upscale",
            }
            for (article_slug, image_id), asset in (
                PROMOPAGES_10060_EXTENSION_NORMALIZED_SOURCES.items()
            )
        ]
        if (
            not isinstance(normalized_policy, dict)
            or normalized_policy.get("version") != 1
            or normalized_policy.get("namespace")
            != PROMOPAGES_10060_EXTENSION_NORMALIZED_RETRY_NAMESPACE.as_posix()
            or normalized_policy.get("shared_asset_namespace")
            != PROMOPAGES_10060_EXTENSION_NORMALIZED_ASSET_NAMESPACE.as_posix()
            or normalized_policy.get("eligible_sources")
            != expected_eligible_sources
            or normalized_policy.get("explicit_operator_command_required") is not True
            or normalized_policy.get(
                "maximum_new_paid_submissions_per_eligible_output"
            )
            != 1
            or normalized_policy.get("retry2_forbidden") is not True
            or normalized_policy.get("automatic_paid_retries") is not False
            or normalized_policy.get("fallback") is not False
            or normalized_policy.get("primary_receipts_immutable") is not True
            or normalized_policy.get("request_delta_only_image_pointer") is not True
        ):
            raise ValueError(f"{label} normalized-input generation policy is invalid")

        cost = manifest.get("cost")
        retry_count_fields = (
            "terminal_retry_reservations",
            "ambiguous_submit_retry_reservations",
            "normalized_input_retry_reservations",
        )
        supersede_count = len(normalized_supersede_keys)
        supersede_policy = (
            generation_policy.get("normalized_input_supersede")
            if isinstance(generation_policy, dict)
            else None
        )
        if (
            not isinstance(cost, dict)
            or cost.get("normalized_input_retry_version") != 1
            or isinstance(
                cost.get("normalized_input_retry_accounting_cost_usd"), bool
            )
            or cost.get("normalized_input_retry_accounting_cost_usd") != 0.35
            or cost.get("normalized_input_retry_reservations")
            != len(normalized_retry_keys)
            or cost.get("maximum_new_paid_submissions_per_normalized_input_output")
            != 1
            or cost.get("automatic_paid_retries") is not False
            or any(
                not isinstance(cost.get(field), int)
                or isinstance(cost.get(field), bool)
                or cost[field] < 0
                for field in retry_count_fields
            )
            or cost.get("total_retry_reservations")
            != sum(cost[field] for field in retry_count_fields) + supersede_count
        ):
            raise ValueError(f"{label} normalized-input cost accounting is invalid")

        if supersede_count:
            if (
                normalized_supersede_keys
                != {PROMOPAGES_10060_EXTENSION_NORMALIZED_SUPERSEDE_KEY}
                or cost.get("normalized_input_supersede_version") != 1
                or isinstance(
                    cost.get("normalized_input_supersede_accounting_cost_usd"),
                    bool,
                )
                or cost.get("normalized_input_supersede_accounting_cost_usd")
                != 0.35
                or cost.get("normalized_input_supersede_reservations") != 1
                or cost.get("maximum_new_paid_submissions_per_superseded_output")
                != 1
            ):
                raise ValueError(f"{label} normalized supersede cost is invalid")
            if supersede_policy != _extension_normalized_supersede_policy():
                raise ValueError(f"{label} normalized supersede policy is invalid")
        elif any(
            field in cost
            for field in (
                "normalized_input_supersede_version",
                "normalized_input_supersede_accounting_cost_usd",
                "normalized_input_supersede_reservations",
                "maximum_new_paid_submissions_per_superseded_output",
            )
        ) or supersede_policy is not None:
            raise ValueError(f"{label} unbound normalized supersede metadata")

        for repository_path in normalized_repository_path_owners:
            if repository_path in remote_repository_paths:
                raise ValueError(
                    f"{label} normalized repository path collides: {repository_path}"
                )
            remote_repository_paths.add(repository_path)

    if (
        actual_image_count != image_count
        or len(nested_by_key) != expected_outputs
        or actual_filtered_count != provider_filtered_count
        or actual_unavailable_count != provider_unavailable_count
    ):
        raise ValueError(f"{label} declared counts do not match nested records")

    flat_outputs = manifest.get("outputs")
    if not isinstance(flat_outputs, list) or len(flat_outputs) != expected_outputs:
        raise ValueError(f"{label} flat outputs do not match nested outputs")
    flat_by_key = {
        (
            output.get("article_slug"),
            output.get("image_id"),
            output.get("model_id"),
        ): output
        for output in flat_outputs
        if isinstance(output, dict)
    }
    if set(flat_by_key) != set(nested_by_key):
        raise ValueError(f"{label} flat output keys do not match nested outputs")
    for key, nested in nested_by_key.items():
        flat = flat_by_key[key]
        for field in (
            "status",
            "video_path",
            "provider_run_id",
            "recorded_status",
            "selected_attempt",
            "error",
            "media",
            "contract_check",
            "retry",
        ):
            if flat.get(field) != nested.get(field):
                raise ValueError(f"{label} flat output audit differs from nested")

    unavailable_articles = manifest.get("unavailable_articles", [])
    if not isinstance(unavailable_articles, list):
        raise ValueError(f"{label} unavailable_articles is invalid")
    unavailable_numbers: set[str] = set()
    unavailable_slugs: set[str] = set()
    for article in unavailable_articles:
        if (
            not isinstance(article, dict)
            or not isinstance(article.get("article_number"), str)
            or len(article["article_number"]) != 2
            or not article["article_number"].isdigit()
            or not isinstance(article.get("article_slug"), str)
            or not article["article_slug"].strip()
            or not isinstance(article.get("url"), str)
            or not article["url"].startswith("https://")
            or article.get("status") != "source-unavailable"
            or not isinstance(article.get("error"), str)
            or not article["error"].strip()
            or article["article_number"] in article_numbers
            or article["article_number"] in existing_article_numbers
            or article["article_number"] in existing_unavailable_numbers
            or article["article_number"] in unavailable_numbers
            or article["article_slug"] in article_slugs
            or article["article_slug"] in existing_article_slugs
            or article["article_slug"] in existing_unavailable_slugs
            or article["article_slug"] in unavailable_slugs
        ):
            raise ValueError(f"{label} unavailable article collides or is invalid")
        unavailable_numbers.add(article["article_number"])
        unavailable_slugs.add(article["article_slug"])

    actual_article_numbers = article_numbers | unavailable_numbers
    if actual_article_numbers != set(registered_article_numbers):
        raise ValueError(
            f"{label} must account for registered articles "
            f"{registered_article_numbers[0]} through "
            f"{registered_article_numbers[-1]}"
        )


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
    promopages_10060_manifest: dict[str, Any] | None = None
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

    article_02_manifest: dict[str, Any] | None = None
    extension_manifest: dict[str, Any] | None = None
    promopages_10060_article_02_path = (
        root / PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH
    )
    if promopages_10060_article_02_path.is_file():
        if not promopages_10060_path.is_file():
            raise ValueError(
                "PROMOPAGES-10060 article 02 replacement requires the legacy sidecar"
            )
        relative_paths.add(PROMOPAGES_10060_ARTICLE_02_RELATIVE_PATH)
        article_02_manifest = json.loads(
            promopages_10060_article_02_path.read_text(encoding="utf-8")
        )
        _collect_promopages_10060_article_02_paths(
            article_02_manifest,
            promopages_10060_manifest,
            remote_repository_paths,
        )

    promopages_10060_extension_path = (
        root / PROMOPAGES_10060_EXTENSION_RELATIVE_PATH
    )
    if promopages_10060_extension_path.is_file():
        if not promopages_10060_path.is_file():
            raise ValueError(
                "PROMOPAGES-10060 campaign extension requires the legacy sidecar"
            )
        relative_paths.add(PROMOPAGES_10060_EXTENSION_RELATIVE_PATH)
        extension_manifest = json.loads(
            promopages_10060_extension_path.read_text(encoding="utf-8")
        )
        _collect_promopages_10060_extension_paths(
            extension_manifest,
            promopages_10060_manifest,
            remote_repository_paths,
        )

    campaign_20260807_manifest: dict[str, Any] | None = None
    campaign_20260807_path = (
        root / PROMOPAGES_10060_CAMPAIGN_20260807_RELATIVE_PATH
    )
    if campaign_20260807_path.is_file():
        if not promopages_10060_path.is_file():
            raise ValueError(
                "PROMOPAGES-10060 campaigns 20260807 extension requires the legacy sidecar"
            )
        relative_paths.add(PROMOPAGES_10060_CAMPAIGN_20260807_RELATIVE_PATH)
        campaign_20260807_manifest = json.loads(
            campaign_20260807_path.read_text(encoding="utf-8")
        )
        prior_sidecars = tuple(
            sidecar
            for sidecar in (extension_manifest, article_02_manifest)
            if sidecar is not None
        )
        _collect_promopages_10060_extension_paths(
            campaign_20260807_manifest,
            promopages_10060_manifest,
            remote_repository_paths,
            label="PROMOPAGES-10060 campaigns 20260807 extension",
            manifest_role=PROMOPAGES_10060_CAMPAIGN_20260807_ROLE,
            batch_id=PROMOPAGES_10060_CAMPAIGN_20260807_BATCH_ID,
            dataset_prefix=PROMOPAGES_10060_CAMPAIGN_20260807_DATASET_PREFIX,
            registered_article_numbers=(
                PROMOPAGES_10060_CAMPAIGN_20260807_ARTICLE_NUMBERS
            ),
            additional_existing_manifests=prior_sidecars,
        )

    s3_delivery_video_paths: set[Path] = set()
    s3_delivery_path = root / PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH
    s3_articles_path = root / PROMOPAGES_10060_S3_ARTICLES_RELATIVE_PATH
    if promopages_10060_manifest is not None:
        if not s3_delivery_path.is_file():
            raise FileNotFoundError(
                "PROMOPAGES-10060 base dataset requires its S3 delivery overlay"
            )
        if not s3_articles_path.is_file():
            raise FileNotFoundError(
                "PROMOPAGES-10060 base dataset requires its S3 routing config"
            )
        relative_paths.add(PROMOPAGES_10060_S3_DELIVERY_RELATIVE_PATH)
        s3_delivery_manifest = json.loads(
            s3_delivery_path.read_text(encoding="utf-8")
        )
        s3_routing_config = json.loads(s3_articles_path.read_text(encoding="utf-8"))
        source_manifests = tuple(
            manifest
            for manifest in (
                promopages_10060_manifest,
                article_02_manifest,
                extension_manifest,
                campaign_20260807_manifest,
            )
            if manifest is not None
        )
        s3_delivery_video_paths = _validate_promopages_10060_s3_delivery(
            s3_delivery_manifest,
            s3_routing_config,
            *source_manifests,
        )
        if not s3_delivery_video_paths <= remote_repository_paths:
            raise ValueError(
                "PROMOPAGES-10060 S3 delivery overlay contains a non-canonical "
                "repository path"
            )
        remote_repository_paths.difference_update(s3_delivery_video_paths)
    elif s3_delivery_path.is_file():
        raise ValueError(
            "PROMOPAGES-10060 S3 delivery overlay requires the base dataset"
        )

    if article_02_manifest is not None:
        _verify_article_02_raw_media(
            root,
            article_02_manifest,
            skip_video_paths=s3_delivery_video_paths,
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
