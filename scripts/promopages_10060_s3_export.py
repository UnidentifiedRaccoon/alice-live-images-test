#!/usr/bin/env python3
"""Build, validate, and upload the PROMOPAGES-10060 experiment video package.

The final Clipmaker Lite sidecar manifests are the only source of selected video
files.  In particular, this preserves results selected from retry/supersede
namespaces instead of guessing them by globbing the generation directories.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTICLES_PATH = REPO_ROOT / "PROMOPAGES-10060" / "s3-export" / "articles.json"
DEFAULT_MANIFEST_PATHS = (
    REPO_ROOT / "clipmaker-lite-test" / "promopages-10060-manifest.json",
    REPO_ROOT / "clipmaker-lite-test" / "promopages-10060-campaigns-20260805-v1-manifest.json",
    REPO_ROOT / "clipmaker-lite-test" / "promopages-10060-article-02-20260806-v2-manifest.json",
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "PROMOPAGES-10060" / "s3-export" / "output"

BUCKET = "promopages-front-bundles"
OBJECT_PREFIX = "front-images/exp_video/"
PUBLIC_BASE_URL = "https://yastatic.net/s3/promopages-front-bundles/"
PACKAGE_ID = "PROMOPAGES-10060-exp-video-v1"
CONTENT_TYPE = "video/mp4"
CACHE_CONTROL = "public,max-age=31536000,immutable"

MODEL_DIRS = {
    "alibaba/wan-2.2": "wan_2_2",
    "alibaba/wan-2.7": "wan_2_7",
    "google/veo-3.1-lite": "veo_3_1",
}
MODEL_ORDER = {model_id: index for index, model_id in enumerate(MODEL_DIRS)}
LITE_MODELS = tuple(MODEL_DIRS)
MERGE_CONTRACT = {
    "article_key": ["article_slug"],
    "image_key": ["article_slug", "image_id"],
    "output_key": ["article_slug", "image_id", "model_id"],
    "target_field": "articles[].images[]",
}
READY_STATUSES = {"succeeded", "verification-failed"}
MISSING_STATUSES = {"provider-filtered", "provider-unavailable"}
HEX24_RE = re.compile(r"^[0-9a-f]{24}$")
CABINET_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# The original all-images batch froze article 02 as source-unavailable after a
# typo in its public URL.  The immutable v2 sidecar is the sole authorised
# replacement.  Keeping this exception exact prevents a later manifest from
# silently overriding any other unavailable marker.
ALLOWED_UNAVAILABLE_SUPERSESSIONS = {
    "02-level-rabotaiu-v-level": {
        "article_number": "02",
        "legacy_batch_id": "promopages-10060-lite-all-images-20260805-v2",
        "legacy_manifest_role": "promopages-10060-all-images",
        "replacement_batch_id": "promopages-10060-article-02-20260806-v2",
        "replacement_manifest_role": "promopages-10060-article-02",
    }
}


class ExportError(RuntimeError):
    """Raised when the package contract or an upload invariant is violated."""


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExportError(f"Cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ExportError(f"Expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _hash_file(path: Path) -> Tuple[str, str, int]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)  # nosec B324: required by S3 Content-MD5
    size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(4 * 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            sha256.update(chunk)
            md5.update(chunk)
    md5_base64 = base64.b64encode(md5.digest()).decode("ascii")
    return sha256.hexdigest(), md5_base64, size


def _sha256_file(path: Path) -> str:
    return _hash_file(path)[0]


def _safe_repo_file(root: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ExportError(f"Unsafe source path: {relative_path!r}")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ExportError(f"Source path escapes the repository or is missing: {relative_path}") from error
    if candidate.is_symlink() or not resolved.is_file():
        raise ExportError(f"Source video must be a regular non-symlink file: {relative_path}")
    return resolved


def _safe_package_relative_path(value: str) -> PurePosixPath:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ExportError(f"Unsafe package path: {value!r}")
    if any(not part.isascii() for part in pure.parts):
        raise ExportError(f"Package paths must be ASCII: {value!r}")
    if any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in pure.parts):
        raise ExportError(f"Package path contains an unsafe character: {value!r}")
    return pure


def _public_url(object_key: str) -> str:
    return PUBLIC_BASE_URL + urllib.parse.quote(object_key, safe="/-._~")


def _validate_hex24(value: Any, label: str) -> str:
    text = str(value)
    if not HEX24_RE.fullmatch(text):
        raise ExportError(f"{label} must be a 24-character lowercase hex ID, got {text!r}")
    return text


def _load_articles(path: Path) -> List[Dict[str, Any]]:
    config = _load_json(path)
    if config.get("ticket") != "PROMOPAGES-10060":
        raise ExportError(f"Unexpected ticket in {path}: {config.get('ticket')!r}")
    articles = config.get("articles")
    if not isinstance(articles, list) or not articles:
        raise ExportError("articles.json must contain at least one ticket row")

    seen_numbers: set[str] = set()
    seen_slugs: set[str] = set()
    seen_publications: set[str] = set()
    normalized: List[Dict[str, Any]] = []
    for raw in articles:
        if not isinstance(raw, dict):
            raise ExportError("Every article mapping must be an object")
        article = dict(raw)
        number = str(article.get("article_number", ""))
        if not re.fullmatch(r"\d{2}", number):
            raise ExportError(f"Invalid article_number: {number!r}")
        slug = str(article.get("article_slug", ""))
        if not re.fullmatch(r"\d{2}-[a-z0-9-]+", slug):
            raise ExportError(f"Invalid article_slug: {slug!r}")
        if not slug.startswith(number + "-"):
            raise ExportError(f"article_number and article_slug disagree: {number}/{slug}")
        if number in seen_numbers or slug in seen_slugs:
            raise ExportError(f"Duplicate article mapping: {number}/{slug}")
        seen_numbers.add(number)
        seen_slugs.add(slug)

        cabinet = article.get("cabinet")
        if not isinstance(cabinet, dict):
            raise ExportError(f"Missing cabinet mapping for {slug}")
        cabinet_name = str(cabinet.get("name", "")).strip()
        cabinet_slug = str(cabinet.get("slug", ""))
        cabinet_id = _validate_hex24(cabinet.get("id"), f"cabinet.id for {slug}")
        if not cabinet_name or not CABINET_SLUG_RE.fullmatch(cabinet_slug):
            raise ExportError(f"Invalid cabinet name/slug for {slug}")
        article["cabinet"] = {"name": cabinet_name, "slug": cabinet_slug, "id": cabinet_id}

        publication_id = _validate_hex24(article.get("publication_id"), f"publication_id for {slug}")
        if publication_id in seen_publications:
            raise ExportError(f"Duplicate publication_id: {publication_id}")
        seen_publications.add(publication_id)
        article["publication_id"] = publication_id
        if publication_id not in str(article.get("url", "")):
            raise ExportError(f"publication_id is not present in the public article URL for {slug}")

        campaign_ids = article.get("campaign_ids")
        if not isinstance(campaign_ids, list) or not campaign_ids:
            raise ExportError(f"campaign_ids must be a non-empty list for {slug}")
        article["campaign_ids"] = [
            _validate_hex24(item, f"campaign_id for {slug}") for item in campaign_ids
        ]
        status = article.get("source_status")
        if status not in {"available", "source-unavailable"}:
            raise ExportError(f"Invalid source_status for {slug}: {status!r}")
        expected_images = article.get("expected_image_count")
        expected_ready = article.get("expected_ready_output_count")
        if status == "available":
            if not isinstance(expected_images, int) or expected_images <= 0:
                raise ExportError(f"expected_image_count must be positive for {slug}")
            if not isinstance(expected_ready, int) or not 0 <= expected_ready <= expected_images * 3:
                raise ExportError(f"Invalid expected_ready_output_count for {slug}")
        elif expected_images is not None or expected_ready != 0:
            raise ExportError(f"Unavailable article {slug} must expect no packaged files")
        normalized.append(article)

    normalized.sort(key=lambda item: item["article_number"])
    return normalized


def _load_source_manifests(paths: Sequence[Path]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    manifests: List[Dict[str, Any]] = []
    receipts: List[Dict[str, Any]] = []
    for path in paths:
        manifest = _load_json(path)
        if manifest.get("ticket") != "PROMOPAGES-10060":
            raise ExportError(f"Unexpected ticket in source manifest {path}")
        if manifest.get("agent_id") != "clipmaker-lite":
            raise ExportError(f"Source manifest is not a Clipmaker Lite result: {path}")
        if (
            not isinstance(manifest.get("manifest_role"), str)
            or not manifest["manifest_role"].strip()
            or manifest.get("merge_contract") != MERGE_CONTRACT
        ):
            raise ExportError(f"Source manifest contract is invalid: {path}")
        outputs = manifest.get("outputs")
        articles = manifest.get("articles")
        if not isinstance(outputs, list) or not isinstance(articles, list):
            raise ExportError(f"Malformed source manifest: {path}")
        for article in articles:
            image_records = article.get("images") if isinstance(article, dict) else None
            if not isinstance(image_records, list):
                raise ExportError(f"Source manifest article images are invalid: {path}")
            for record in image_records:
                planning = record.get("lite_planning") if isinstance(record, dict) else None
                provenance = planning.get("provenance") if isinstance(planning, dict) else None
                if (
                    not isinstance(provenance, dict)
                    or provenance.get("verified") is not True
                    or provenance.get("agent_id") != "clipmaker-lite"
                    or tuple(provenance.get("models") or ()) != LITE_MODELS
                ):
                    raise ExportError(f"Source manifest Lite provenance is invalid: {path}")
        manifests.append(manifest)
        try:
            relative = path.resolve(strict=True).relative_to(REPO_ROOT.resolve(strict=True)).as_posix()
        except ValueError:
            relative = path.resolve(strict=True).as_posix()
        receipts.append(
            {
                "path": relative,
                "sha256": _sha256_file(path),
                "batch_id": manifest.get("batch_id"),
                "updated_at": manifest.get("updated_at"),
            }
        )
    return manifests, receipts


def _materialize(source: Path, destination: Path, mode: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode == "copy":
        shutil.copy2(source, destination)
        return "copy"
    if mode not in {"auto", "hardlink"}:
        raise ExportError(f"Unknown materialization mode: {mode}")
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        if mode == "hardlink":
            raise
        shutil.copy2(source, destination)
        return "copy"


def _csv_text(fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> str:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


LINK_FIELDS = (
    "cabinet_name",
    "cabinet_id",
    "article_number",
    "article_slug",
    "publication_id",
    "image_id",
    "experiment",
    "model_id",
    "generation_status",
    "bytes",
    "sha256",
    "object_key",
    "yastatic_url",
)
MISSING_FIELDS = (
    "missing_kind",
    "article_number",
    "article_slug",
    "publication_id",
    "image_id",
    "experiment",
    "model_id",
    "generation_status",
    "reason",
)


def _links_csv(outputs: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for item in outputs:
        if item["package_status"] != "ready":
            continue
        rows.append(
            {
                "cabinet_name": item["cabinet"]["name"],
                "cabinet_id": item["cabinet"]["id"],
                "article_number": item["article_number"],
                "article_slug": item["article_slug"],
                "publication_id": item["publication_id"],
                "image_id": item["image_id"],
                "experiment": item["experiment"],
                "model_id": item["model_id"],
                "generation_status": item["generation_status"],
                "bytes": item["media"]["bytes"],
                "sha256": item["media"]["sha256"],
                "object_key": item["object_key"],
                "yastatic_url": item["yastatic_url"],
            }
        )
    return _csv_text(LINK_FIELDS, rows)


def _missing_csv(
    outputs: Sequence[Mapping[str, Any]], unavailable_articles: Sequence[Mapping[str, Any]]
) -> str:
    rows: List[Dict[str, Any]] = []
    for item in outputs:
        if item["package_status"] == "ready":
            continue
        rows.append(
            {
                "missing_kind": "output-unavailable",
                "article_number": item["article_number"],
                "article_slug": item["article_slug"],
                "publication_id": item["publication_id"],
                "image_id": item["image_id"],
                "experiment": item["experiment"],
                "model_id": item["model_id"],
                "generation_status": item["generation_status"],
                "reason": item.get("error") or item["generation_status"],
            }
        )
    for article in unavailable_articles:
        rows.append(
            {
                "missing_kind": "source-unavailable",
                "article_number": article["article_number"],
                "article_slug": article["article_slug"],
                "publication_id": article["publication_id"],
                "image_id": "",
                "experiment": "",
                "model_id": "",
                "generation_status": "source-unavailable",
                "reason": article.get("error") or "Article source returned HTTP 404",
            }
        )
    return _csv_text(MISSING_FIELDS, rows)


def _sha256sums(outputs: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        f"{item['media']['sha256']}  upload/{item['relative_path']}\n"
        for item in outputs
        if item["package_status"] == "ready"
    )


def _command_text() -> str:
    return (
        "# Dry-run (no external writes)\n"
        "python3 scripts/promopages_10060_s3_export.py upload "
        "--output PROMOPAGES-10060/s3-export/output "
        "--yc-profile promopages-internal\n\n"
        "# Execute the verified upload\n"
        "python3 scripts/promopages_10060_s3_export.py upload "
        "--output PROMOPAGES-10060/s3-export/output "
        "--yc-profile promopages-internal --execute\n"
    )


def _safe_replace_output(staging: Path, output_dir: Path) -> None:
    output = output_dir.resolve(strict=False)
    if output in {Path("/").resolve(), REPO_ROOT.resolve()} or output == output.parent:
        raise ExportError(f"Refusing unsafe output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    backup: Optional[Path] = None
    if output.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent))
        backup.rmdir()
        output.rename(backup)
    try:
        staging.rename(output)
    except BaseException:
        if backup is not None and not output.exists():
            backup.rename(output)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def build_export(
    root: Path,
    articles_path: Path,
    manifest_paths: Sequence[Path],
    output_dir: Path,
    *,
    materialize_mode: str = "auto",
) -> Dict[str, Any]:
    """Build the deterministic local package and return its manifest."""

    root = root.resolve(strict=True)
    output_dir = output_dir.resolve(strict=False)
    articles = _load_articles(articles_path)
    source_manifests, source_receipts = _load_source_manifests(manifest_paths)
    mappings = {item["article_slug"]: item for item in articles}
    available_mappings = {slug: item for slug, item in mappings.items() if item["source_status"] == "available"}
    unavailable_mappings = {
        slug: item for slug, item in mappings.items() if item["source_status"] == "source-unavailable"
    }

    source_articles: Dict[str, Dict[str, Any]] = {}
    source_article_batches: Dict[str, str] = {}
    source_article_roles: Dict[str, str] = {}
    source_outputs: List[Dict[str, Any]] = []
    unavailable_source: Dict[str, Dict[str, Any]] = {}
    unavailable_source_batches: Dict[str, str] = {}
    unavailable_source_roles: Dict[str, str] = {}
    for manifest in source_manifests:
        batch_id = str(manifest.get("batch_id"))
        manifest_role = str(manifest.get("manifest_role"))
        for article in manifest["articles"]:
            slug = str(article.get("article_slug"))
            if slug in source_articles:
                raise ExportError(f"Article occurs in more than one source manifest: {slug}")
            source_articles[slug] = article
            source_article_batches[slug] = batch_id
            source_article_roles[slug] = manifest_role
        source_outputs.extend(manifest["outputs"])
        for article in manifest.get("unavailable_articles", []):
            slug = str(article.get("article_slug"))
            if slug in unavailable_source:
                raise ExportError(
                    f"Unavailable article occurs in more than one source manifest: {slug}"
                )
            unavailable_source[slug] = article
            unavailable_source_batches[slug] = batch_id
            unavailable_source_roles[slug] = manifest_role

    superseded_unavailable: set[str] = set()
    for slug in sorted(set(source_articles) & set(unavailable_source)):
        rule = ALLOWED_UNAVAILABLE_SUPERSESSIONS.get(slug)
        mapping = mappings.get(slug)
        source = source_articles[slug]
        unavailable = unavailable_source[slug]
        if (
            rule is None
            or mapping is None
            or mapping["source_status"] != "available"
            or source_article_batches[slug] != rule["replacement_batch_id"]
            or source_article_roles[slug] != rule["replacement_manifest_role"]
            or unavailable_source_batches[slug] != rule["legacy_batch_id"]
            or unavailable_source_roles[slug] != rule["legacy_manifest_role"]
            or str(source.get("article_number")) != rule["article_number"]
            or str(unavailable.get("article_number")) != rule["article_number"]
            or unavailable.get("status") != "source-unavailable"
            or source.get("url") != mapping.get("url")
        ):
            raise ExportError(
                f"Article has conflicting available and unavailable source records: {slug}"
            )
        superseded_unavailable.add(slug)

    effective_unavailable_source = {
        slug: article
        for slug, article in unavailable_source.items()
        if slug not in superseded_unavailable
    }

    if set(source_articles) != set(available_mappings):
        raise ExportError(
            "Article mapping does not match source manifests: "
            f"missing={sorted(set(available_mappings) - set(source_articles))}, "
            f"unexpected={sorted(set(source_articles) - set(available_mappings))}"
        )
    if set(effective_unavailable_source) != set(unavailable_mappings):
        raise ExportError("Source-unavailable article mapping does not match final manifests")

    by_article_image: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for output in source_outputs:
        slug = str(output.get("article_slug"))
        image_id = str(output.get("image_id"))
        if slug not in available_mappings:
            raise ExportError(f"Output references an unmapped article: {slug}")
        by_article_image[(slug, image_id)].append(output)

    expected_image_count = sum(int(article["image_count"]) for article in source_articles.values())
    if len(by_article_image) != expected_image_count:
        raise ExportError(
            f"Expected {expected_image_count} article/image pairs, found {len(by_article_image)}"
        )

    for slug, mapping in available_mappings.items():
        configured_images = int(mapping["expected_image_count"])
        source_images = int(source_articles[slug]["image_count"])
        actual_images = sum(1 for article_slug, _image_id in by_article_image if article_slug == slug)
        ready_outputs = sum(
            1
            for (article_slug, _image_id), outputs in by_article_image.items()
            if article_slug == slug
            for output in outputs
            if output.get("video_path")
        )
        if source_images != configured_images or actual_images != configured_images:
            raise ExportError(
                f"Image count mismatch for {slug}: config={configured_images}, "
                f"manifest={source_images}, outputs={actual_images}"
            )
        if ready_outputs != mapping["expected_ready_output_count"]:
            raise ExportError(
                f"Ready output count mismatch for {slug}: "
                f"expected={mapping['expected_ready_output_count']}, actual={ready_outputs}"
            )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    materialization_counts: Counter[str] = Counter()
    package_outputs: List[Dict[str, Any]] = []
    seen_tuples: set[Tuple[str, str, str]] = set()
    seen_keys: set[str] = set()
    try:
        for (slug, image_id), outputs in sorted(
            by_article_image.items(), key=lambda pair: (int(pair[0][0][:2]), int(pair[0][1]))
        ):
            mapping = available_mappings[slug]
            models = {str(output.get("model_id")): output for output in outputs}
            if set(models) != set(MODEL_DIRS) or len(outputs) != len(MODEL_DIRS):
                raise ExportError(f"Expected exactly three model outputs for {slug}/{image_id}")
            image_token = f"{int(image_id):02d}"
            for model_id in MODEL_DIRS:
                output = models[model_id]
                status = str(output.get("status"))
                cabinet = mapping["cabinet"]
                experiment = MODEL_DIRS[model_id]
                tuple_key = (mapping["publication_id"], image_token, model_id)
                if tuple_key in seen_tuples:
                    raise ExportError(f"Duplicate logical output: {tuple_key}")
                seen_tuples.add(tuple_key)

                base: Dict[str, Any] = {
                    "package_status": "ready" if output.get("video_path") else "unavailable",
                    "article_number": mapping["article_number"],
                    "article_slug": slug,
                    "article_title": source_articles[slug].get("title") or mapping.get("label"),
                    "cabinet": cabinet,
                    "campaign_ids": mapping["campaign_ids"],
                    "publication_id": mapping["publication_id"],
                    "image_id": image_token,
                    "model_id": model_id,
                    "experiment": experiment,
                    "generation_status": status,
                    "selected_attempt": output.get("selected_attempt"),
                    "provider_run_id": output.get("provider_run_id"),
                    "source_video_path": output.get("video_path"),
                    "relative_path": None,
                    "object_key": None,
                    "yastatic_url": None,
                    "media": None,
                    "verification": output.get("contract_check"),
                    "error": output.get("error"),
                }
                video_path = output.get("video_path")
                media = output.get("media")
                if video_path:
                    if status not in READY_STATUSES:
                        raise ExportError(f"Unexpected ready status {status!r} for {slug}/{image_id}/{model_id}")
                    if not isinstance(media, dict):
                        raise ExportError(f"Missing media metadata for {slug}/{image_id}/{model_id}")
                    source = _safe_repo_file(root, str(video_path))
                    sha256, md5_base64, size = _hash_file(source)
                    if sha256 != media.get("sha256") or size != media.get("bytes"):
                        raise ExportError(f"Source hash/size mismatch: {video_path}")
                    cabinet_dir = f"{cabinet['slug']}__{cabinet['id']}"
                    filename = f"image_{image_token}--sha256-{sha256[:12]}.mp4"
                    relative = PurePosixPath(
                        cabinet_dir,
                        mapping["publication_id"],
                        experiment,
                        filename,
                    )
                    _safe_package_relative_path(relative.as_posix())
                    object_key = OBJECT_PREFIX + relative.as_posix()
                    if object_key in seen_keys:
                        raise ExportError(f"Duplicate object key: {object_key}")
                    seen_keys.add(object_key)
                    mode_used = _materialize(source, staging / "upload" / Path(*relative.parts), materialize_mode)
                    materialization_counts[mode_used] += 1
                    base.update(
                        {
                            "relative_path": relative.as_posix(),
                            "object_key": object_key,
                            "yastatic_url": _public_url(object_key),
                            "media": {
                                "sha256": sha256,
                                "md5_base64": md5_base64,
                                "bytes": size,
                                "container": media.get("container"),
                                "codec": media.get("codec"),
                                "duration_seconds": media.get("duration_seconds"),
                                "width": media.get("width"),
                                "height": media.get("height"),
                                "fps": media.get("fps"),
                                "frames": media.get("frames"),
                                "has_audio": media.get("has_audio"),
                            },
                        }
                    )
                else:
                    if status not in MISSING_STATUSES:
                        raise ExportError(f"Unexpected unavailable status {status!r} for {slug}/{image_id}/{model_id}")
                    if media is not None:
                        raise ExportError(f"Unavailable output unexpectedly has media: {slug}/{image_id}/{model_id}")
                package_outputs.append(base)

        package_outputs.sort(
            key=lambda item: (
                int(item["article_number"]),
                int(item["image_id"]),
                MODEL_ORDER[item["model_id"]],
            )
        )
        ready = [item for item in package_outputs if item["package_status"] == "ready"]
        unavailable = [item for item in package_outputs if item["package_status"] != "ready"]
        unavailable_articles: List[Dict[str, Any]] = []
        for slug, mapping in sorted(unavailable_mappings.items(), key=lambda item: item[1]["article_number"]):
            source = effective_unavailable_source[slug]
            unavailable_articles.append(
                {
                    "article_number": mapping["article_number"],
                    "article_slug": slug,
                    "label": mapping.get("label"),
                    "url": mapping.get("url"),
                    "cabinet": mapping["cabinet"],
                    "campaign_ids": mapping["campaign_ids"],
                    "publication_id": mapping["publication_id"],
                    "status": "source-unavailable",
                    "error": source.get("error"),
                }
            )

        counts = {
            "cabinets": len({item["cabinet"]["id"] for item in articles}),
            "ticket_articles": len(articles),
            "articles_with_video": len(available_mappings),
            "source_unavailable_articles": len(unavailable_articles),
            "images": len(by_article_image),
            "logical_outputs": len(package_outputs),
            "ready_outputs": len(ready),
            "unavailable_outputs": len(unavailable),
            "bytes": sum(item["media"]["bytes"] for item in ready),
            "generation_statuses": dict(sorted(Counter(item["generation_status"] for item in package_outputs).items())),
            "materialization": dict(sorted(materialization_counts.items())),
        }
        expected_images = sum(
            int(item["expected_image_count"])
            for item in articles
            if item["source_status"] == "available"
        )
        expected_ready = sum(int(item["expected_ready_output_count"]) for item in articles)
        expected_counts = {
            "cabinets": len({item["cabinet"]["id"] for item in articles}),
            "ticket_articles": len(articles),
            "articles_with_video": len(available_mappings),
            "source_unavailable_articles": len(unavailable_mappings),
            "images": expected_images,
            "logical_outputs": expected_images * len(MODEL_DIRS),
            "ready_outputs": expected_ready,
            "unavailable_outputs": expected_images * len(MODEL_DIRS) - expected_ready,
        }
        for key, expected in expected_counts.items():
            if counts[key] != expected:
                raise ExportError(f"Unexpected {key}: expected {expected}, got {counts[key]}")

        manifest = {
            "schema_version": "promopages-exp-video-package/v1",
            "package_id": PACKAGE_ID,
            "ticket": "PROMOPAGES-10060",
            "bucket": BUCKET,
            "object_prefix": OBJECT_PREFIX,
            "public_base_url": PUBLIC_BASE_URL,
            "content_type": CONTENT_TYPE,
            "cache_control": CACHE_CONTROL,
            "model_directory_map": MODEL_DIRS,
            "source_manifests": source_receipts,
            "counts": counts,
            "unavailable_articles": unavailable_articles,
            "outputs": package_outputs,
        }
        _write_json(staging / "manifest.json", manifest)
        (staging / "links.csv").write_text(_links_csv(package_outputs), encoding="utf-8")
        (staging / "missing.csv").write_text(
            _missing_csv(package_outputs, unavailable_articles), encoding="utf-8"
        )
        (staging / "SHA256SUMS").write_text(_sha256sums(package_outputs), encoding="utf-8")
        (staging / "upload-command.txt").write_text(_command_text(), encoding="utf-8")
        _safe_replace_output(staging, output_dir)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return manifest


def _assert_output_counts(manifest: Mapping[str, Any]) -> None:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise ExportError("manifest.json has no outputs array")
    ready = [item for item in outputs if item.get("package_status") == "ready"]
    unavailable = [item for item in outputs if item.get("package_status") != "ready"]
    counts = manifest.get("counts", {})
    expected = {
        "logical_outputs": len(outputs),
        "ready_outputs": len(ready),
        "unavailable_outputs": len(unavailable),
        "bytes": sum(item["media"]["bytes"] for item in ready),
    }
    for field, actual in expected.items():
        if counts.get(field) != actual:
            raise ExportError(f"Manifest count {field} is stale: {counts.get(field)} != {actual}")


def verify_export(output_dir: Path) -> Dict[str, Any]:
    """Verify the exact package file set, sidecars, sizes, and hashes."""

    output_dir = output_dir.resolve(strict=True)
    manifest = _load_json(output_dir / "manifest.json")
    if manifest.get("schema_version") != "promopages-exp-video-package/v1":
        raise ExportError("Unsupported package manifest schema")
    if manifest.get("bucket") != BUCKET or manifest.get("object_prefix") != OBJECT_PREFIX:
        raise ExportError("Package bucket/prefix does not match the locked export contract")
    if manifest.get("model_directory_map") != MODEL_DIRS:
        raise ExportError("Package model directory map does not match the locked export contract")
    _assert_output_counts(manifest)

    outputs: List[Dict[str, Any]] = manifest["outputs"]
    expected_files: set[str] = set()
    seen_tuples: set[Tuple[str, str, str]] = set()
    seen_keys: set[str] = set()
    verified_bytes = 0
    for item in outputs:
        tuple_key = (item["publication_id"], item["image_id"], item["model_id"])
        if tuple_key in seen_tuples:
            raise ExportError(f"Duplicate logical output in package: {tuple_key}")
        seen_tuples.add(tuple_key)
        if item["model_id"] not in MODEL_DIRS or item["experiment"] != MODEL_DIRS[item["model_id"]]:
            raise ExportError(f"Invalid model/experiment mapping for {tuple_key}")
        if item["package_status"] != "ready":
            if any(item.get(key) is not None for key in ("relative_path", "object_key", "yastatic_url", "media")):
                raise ExportError(f"Unavailable output has upload fields: {tuple_key}")
            continue
        relative = _safe_package_relative_path(item["relative_path"])
        object_key = OBJECT_PREFIX + relative.as_posix()
        if item["object_key"] != object_key or item["yastatic_url"] != _public_url(object_key):
            raise ExportError(f"Object key or yastatic URL mismatch for {tuple_key}")
        if object_key in seen_keys:
            raise ExportError(f"Duplicate object key in package: {object_key}")
        seen_keys.add(object_key)
        package_relative = PurePosixPath("upload", *relative.parts).as_posix()
        expected_files.add(package_relative)
        candidate = output_dir / Path(*PurePosixPath(package_relative).parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise ExportError(f"Missing or non-regular package file: {package_relative}")
        sha256, md5_base64, size = _hash_file(candidate)
        media = item["media"]
        if (sha256, md5_base64, size) != (
            media["sha256"],
            media["md5_base64"],
            media["bytes"],
        ):
            raise ExportError(f"Package hash/size mismatch: {package_relative}")
        verified_bytes += size

    upload_root = output_dir / "upload"
    actual_files: set[str] = set()
    if upload_root.exists():
        for path in upload_root.rglob("*"):
            if path.is_symlink():
                raise ExportError(f"Symlink found in upload tree: {path}")
            if path.is_file():
                actual_files.add(path.relative_to(output_dir).as_posix())
    if actual_files != expected_files:
        raise ExportError(
            "Upload tree does not match manifest: "
            f"missing={sorted(expected_files - actual_files)}, extras={sorted(actual_files - expected_files)}"
        )

    sidecars = {
        "links.csv": _links_csv(outputs),
        "missing.csv": _missing_csv(outputs, manifest.get("unavailable_articles", [])),
        "SHA256SUMS": _sha256sums(outputs),
        "upload-command.txt": _command_text(),
    }
    for name, expected_text in sidecars.items():
        try:
            actual_text = (output_dir / name).read_text(encoding="utf-8")
        except OSError as error:
            raise ExportError(f"Cannot read package sidecar {name}: {error}") from error
        if actual_text != expected_text:
            raise ExportError(f"Package sidecar is stale or edited: {name}")

    return {
        "verified": True,
        "package_id": manifest["package_id"],
        "counts": {
            "ready_outputs": len(expected_files),
            "unavailable_outputs": len(outputs) - len(expected_files),
            "bytes": verified_bytes,
        },
        "ready_outputs": len(expected_files),
        "unavailable_outputs": len(outputs) - len(expected_files),
        "bytes": verified_bytes,
    }


def _run_yc(
    command: Sequence[str], runner: Callable[..., subprocess.CompletedProcess[str]]
) -> subprocess.CompletedProcess[str]:
    return runner(list(command), capture_output=True, text=True)


def _json_from_process(result: subprocess.CompletedProcess[str], operation: str) -> Dict[str, Any]:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        raise ExportError(f"{operation} failed: {detail}")
    if not result.stdout.strip():
        return {}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ExportError(f"{operation} returned invalid JSON: {result.stdout[:500]}") from error
    return value if isinstance(value, dict) else {"value": value}


def _normalize_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {re.sub(r"[-_]", "", str(key)).lower(): _normalize_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_keys(item) for item in value]
    return value


def _head_object(
    item: Mapping[str, Any],
    yc_profile: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> Optional[Dict[str, Any]]:
    command = [
        "yc",
        "storage",
        "s3api",
        "head-object",
        "--profile",
        yc_profile,
        "--format",
        "json",
        "--bucket",
        BUCKET,
        "--key",
        item["object_key"],
    ]
    result = _run_yc(command, runner)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").lower()
        if any(
            marker in detail
            for marker in (
                "nosuchkey",
                "not found",
                "status code: 404",
                "statuscode: 404",
                "statuscode=404",
            )
        ):
            return None
        raise ExportError(f"S3 HEAD failed for {item['object_key']}: {(result.stderr or result.stdout).strip()}")
    return _json_from_process(result, f"S3 HEAD {item['object_key']}")


def _head_matches(item: Mapping[str, Any], head: Mapping[str, Any]) -> bool:
    normalized = _normalize_keys(head)
    size = normalized.get("contentlength")
    metadata = normalized.get("metadata") or {}
    sha256 = metadata.get("sha256") if isinstance(metadata, dict) else None
    publication_id = metadata.get("publicationid") if isinstance(metadata, dict) else None
    image_id = metadata.get("imageid") if isinstance(metadata, dict) else None
    experiment = metadata.get("experiment") if isinstance(metadata, dict) else None
    content_type = normalized.get("contenttype")
    cache_control = normalized.get("cachecontrol")
    content_disposition = normalized.get("contentdisposition")
    return (
        int(size or -1) == item["media"]["bytes"]
        and sha256 == item["media"]["sha256"]
        and publication_id == item["publication_id"]
        and image_id == item["image_id"]
        and experiment == item["experiment"]
        and content_type == CONTENT_TYPE
        and cache_control == CACHE_CONTROL
        and content_disposition == "inline"
    )


def _put_object(
    output_dir: Path,
    item: Mapping[str, Any],
    yc_profile: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> Dict[str, Any]:
    relative = _safe_package_relative_path(item["relative_path"])
    body = output_dir / "upload" / Path(*relative.parts)
    metadata = ",".join(
        (
            f"sha256={item['media']['sha256']}",
            f"publication-id={item['publication_id']}",
            f"image-id={item['image_id']}",
            f"experiment={item['experiment']}",
        )
    )
    command = [
        "yc",
        "storage",
        "s3api",
        "put-object",
        "--profile",
        yc_profile,
        "--format",
        "json",
        "--bucket",
        BUCKET,
        "--key",
        item["object_key"],
        "--body",
        str(body),
        "--content-md5",
        item["media"]["md5_base64"],
        "--content-type",
        CONTENT_TYPE,
        "--cache-control",
        CACHE_CONTROL,
        "--content-disposition",
        "inline",
        "--metadata",
        metadata,
    ]
    result = _run_yc(command, runner)
    return _json_from_process(result, f"S3 PUT {item['object_key']}")


def _verify_yastatic(item: Mapping[str, Any], attempts: int = 6) -> Dict[str, Any]:
    url = item["yastatic_url"]
    last_error = "unknown error"
    for attempt in range(attempts):
        try:
            head_request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(head_request, timeout=30) as response:
                status = response.status
                content_type = response.headers.get_content_type()
                content_length = response.headers.get("Content-Length")
            range_request = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
            with urllib.request.urlopen(range_request, timeout=30) as response:
                range_status = response.status
                content_range = response.headers.get("Content-Range")
                response.read(1)
            if status != 200 or content_type != CONTENT_TYPE:
                raise ExportError(f"unexpected HEAD status/type {status}/{content_type}")
            if content_length is not None and int(content_length) != item["media"]["bytes"]:
                raise ExportError(f"unexpected Content-Length {content_length}")
            if range_status not in {200, 206}:
                raise ExportError(f"unexpected Range status {range_status}")
            if range_status == 206 and content_range and not content_range.endswith(
                f"/{item['media']['bytes']}"
            ):
                raise ExportError(f"unexpected Content-Range {content_range}")
            return {
                "verified": True,
                "head_status": status,
                "range_status": range_status,
                "content_type": content_type,
                "content_length": int(content_length) if content_length else None,
            }
        except (OSError, ValueError, urllib.error.URLError, ExportError) as error:
            last_error = str(error)
            if attempt + 1 < attempts:
                time.sleep(min(2**attempt, 16))
    raise ExportError(f"yastatic verification failed for {url}: {last_error}")


def _atomic_upload_report(path: Path, report: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    _write_json(temporary, report)
    os.replace(temporary, path)


def upload_export(
    output_dir: Path,
    *,
    execute: bool,
    yc_profile: Optional[str] = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Dict[str, Any]:
    """Plan or execute an idempotent manifest-driven upload.

    Dry-run never invokes ``yc`` and performs no external writes.  Execute mode
    requires an explicitly named internal profile and refuses content conflicts.
    """

    local_verification = verify_export(output_dir)
    output_dir = output_dir.resolve(strict=True)
    manifest = _load_json(output_dir / "manifest.json")
    ready = [item for item in manifest["outputs"] if item["package_status"] == "ready"]
    operations = [
        {
            "operation": "head-then-put-if-missing",
            "object_key": item["object_key"],
            "bytes": item["media"]["bytes"],
            "sha256": item["media"]["sha256"],
            "yastatic_url": item["yastatic_url"],
        }
        for item in ready
    ]
    if not execute:
        return {
            "mode": "dry-run",
            "external_writes": 0,
            "local_verification": local_verification,
            "operation_count": len(operations),
            "bytes": sum(item["bytes"] for item in operations),
            "operations": operations,
        }
    if not yc_profile:
        raise ExportError("--yc-profile is required with --execute")

    preflight_command = [
        "yc",
        "storage",
        "s3api",
        "list-objects-v2",
        "--profile",
        yc_profile,
        "--format",
        "json",
        "--bucket",
        BUCKET,
        "--prefix",
        OBJECT_PREFIX,
        "--max-keys",
        "1",
    ]
    _json_from_process(_run_yc(preflight_command, runner), "S3 access preflight")

    report: Dict[str, Any] = {
        "schema_version": "promopages-exp-video-upload-report/v1",
        "package_id": manifest["package_id"],
        "bucket": BUCKET,
        "object_prefix": OBJECT_PREFIX,
        "yc_profile": yc_profile,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "counts": {"total": len(ready), "uploaded": 0, "skipped": 0, "verified": 0},
        "objects": [],
    }
    report_path = output_dir / "upload-report.json"
    _atomic_upload_report(report_path, report)

    for item in ready:
        entry: Dict[str, Any] = {
            "object_key": item["object_key"],
            "yastatic_url": item["yastatic_url"],
            "action": "pending",
            "status": "pending",
            "s3_head": None,
            "put_result": None,
            "yastatic": None,
            "error": None,
        }
        report["objects"].append(entry)
        _atomic_upload_report(report_path, report)
        stage = "s3-head"
        try:
            head = _head_object(item, yc_profile, runner)
            entry["s3_head"] = head
            if head is not None and not _head_matches(item, head):
                entry["action"] = "conflict"
                entry["status"] = "conflict"
                raise ExportError(
                    "Immutable object key conflict; refusing overwrite: " + item["object_key"]
                )
            if head is None:
                stage = "upload"
                entry["put_result"] = _put_object(output_dir, item, yc_profile, runner)
                entry["action"] = "uploaded"
                entry["status"] = "uploaded-awaiting-verification"
                report["counts"]["uploaded"] += 1
                _atomic_upload_report(report_path, report)
                stage = "s3-verification"
                head = _head_object(item, yc_profile, runner)
                entry["s3_head"] = head
                if head is None or not _head_matches(item, head):
                    entry["status"] = "s3-verification-failed"
                    raise ExportError(f"S3 post-upload verification failed: {item['object_key']}")
            else:
                entry["action"] = "skipped"
                entry["status"] = "s3-verified"
                report["counts"]["skipped"] += 1
                _atomic_upload_report(report_path, report)

            entry["status"] = "s3-verified"
            stage = "yastatic-verification"
            entry["yastatic"] = _verify_yastatic(item)
            entry["status"] = "verified"
            report["counts"]["verified"] += 1
            _atomic_upload_report(report_path, report)
        except (ExportError, OSError, ValueError) as error:
            if entry["status"] != "conflict":
                entry["status"] = stage + "-failed"
            entry["error"] = str(error)
            _atomic_upload_report(report_path, report)
            raise

    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_upload_report(report_path, report)
    verified_keys = {row["object_key"] for row in report["objects"] if row["status"] == "verified"}
    verified_links = [item for item in ready if item["object_key"] in verified_keys]
    (output_dir / "verified-links.csv").write_text(_links_csv(verified_links), encoding="utf-8")
    return report


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build the local S3 upload package")
    build.add_argument("--root", type=_path, default=REPO_ROOT)
    build.add_argument("--articles", type=_path, default=DEFAULT_ARTICLES_PATH)
    build.add_argument("--manifest", action="append", type=_path, dest="manifests")
    build.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)
    build.add_argument("--materialize", choices=("auto", "hardlink", "copy"), default="auto")

    verify = subparsers.add_parser("verify", help="Verify package files and sidecars")
    verify.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)

    upload = subparsers.add_parser("upload", help="Plan or execute the manifest-driven upload")
    upload.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)
    upload.add_argument("--yc-profile", default="promopages-internal")
    upload.add_argument("--execute", action="store_true", help="Perform external S3 writes")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            manifests = tuple(args.manifests) if args.manifests else DEFAULT_MANIFEST_PATHS
            result = build_export(
                args.root,
                args.articles,
                manifests,
                args.output,
                materialize_mode=args.materialize,
            )
            summary = {"built": True, "output": str(args.output), "counts": result["counts"]}
        elif args.command == "verify":
            summary = verify_export(args.output)
        else:
            summary = upload_export(
                args.output,
                execute=args.execute,
                yc_profile=args.yc_profile,
            )
            if not args.execute:
                summary = {key: value for key, value in summary.items() if key != "operations"}
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    except (ExportError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
