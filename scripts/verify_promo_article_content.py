#!/usr/bin/env python3
"""Verify the extracted PROMOPAGES-9884 article-content dataset.

The verifier is read-only unless ``--write-report`` is passed.  The source
image manifest remains the ordering and identity source of truth for every
image occurrence in the extracted article content.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn
from urllib.parse import urlsplit


SCHEMA_VERSION = "1.0"
EXPECTED_ARTICLE_COUNT = 20
EXPECTED_IMAGE_COUNT = 125
EXPECTED_ARTICLE_KEYS = tuple(
    f"{number:02d}" for number in range(1, EXPECTED_ARTICLE_COUNT + 1)
)

MANIFEST_REQUIRED_COLUMNS = frozenset(
    {
        "article_number",
        "article_url",
        "image_number",
        "image_role",
        "block_index",
        "gallery_index",
        "image_id",
        "file_path",
        "duplicate_of",
    }
)

ARTICLE_FIELDS = frozenset(
    {
        "schema_version",
        "article_number",
        "article_key",
        "article_id",
        "url",
        "final_url",
        "canonical_url",
        "publication_id",
        "publication_version",
        "title",
        "lead",
        "cta",
        "blocks",
    }
)

CTA_FIELDS = frozenset(
    {"text", "link_to_open", "link_to_show", "included_in_blocks"}
)
CTA_BLOCK_FIELDS = frozenset(
    {"type", "source_block_index", "text", "url", "inline_styles", "links"}
)

IMAGE_FIELDS = frozenset(
    {
        "type",
        "image_id",
        "file",
        "manifest_file_path",
        "role",
        "source_image_id",
        "source_block_index",
        "gallery_index",
        "alt",
        "caption",
        "duplicate_of",
    }
)

TEXT_BLOCK_TYPES = frozenset(
    {"paragraph", "heading", "list_item", "quote", "legal"}
)
TEXT_REQUIRED_FIELDS = frozenset(
    {"type", "source_block_index", "text", "inline_styles", "links"}
)
TEXT_TYPE_FIELDS = {
    "paragraph": frozenset(),
    "heading": frozenset({"level"}),
    "list_item": frozenset({"list_style", "depth"}),
    "quote": frozenset(),
    "legal": frozenset(),
}

INLINE_STYLE_FIELDS = frozenset({"offset", "length", "style"})
LINK_FIELDS = frozenset({"offset", "length", "url"})
UNRESOLVED_FIELDS = frozenset(
    {
        "article_number",
        "article_key",
        "article_id",
        "field",
        "source_path",
        "reason",
    }
)
RESOLVED_EXCEPTION_STATUSES = frozenset(
    {"resolved", "closed", "accepted", "ignored", "waived"}
)
UNRESOLVED_EXCEPTION_STATUSES = frozenset(
    {"unresolved", "open", "pending", "failed", "error"}
)


class VerificationError(Exception):
    """A deterministic dataset-contract failure."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def is_int(value: object) -> bool:
    """Return True for JSON integers, but not for JSON booleans."""

    return isinstance(value, int) and not isinstance(value, bool)


def require_object(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{context} must be a JSON object")
    return value


def require_exact_fields(
    value: dict[str, Any],
    required: frozenset[str],
    allowed: frozenset[str],
    context: str,
) -> None:
    missing = sorted(required - value.keys())
    extra = sorted(value.keys() - allowed)
    if missing or extra:
        fail(f"{context} fields differ: missing={missing}, extra={extra}")


def require_string(
    value: object, context: str, *, nonempty: bool = False
) -> str:
    if not isinstance(value, str):
        fail(f"{context} must be a string")
    if nonempty and not value.strip():
        fail(f"{context} must be a non-empty string")
    return value


def require_nonnegative_int(value: object, context: str) -> int:
    if not is_int(value) or value < 0:
        fail(f"{context} must be a non-negative integer")
    return value


def require_nullable_nonnegative_int(value: object, context: str) -> int | None:
    if value is None:
        return None
    return require_nonnegative_int(value, context)


def require_http_url(value: object, context: str) -> str:
    url = require_string(value, context, nonempty=True)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        fail(f"{context} must be an absolute HTTP(S) URL")
    return url


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object has duplicate key {key!r}")
        result[key] = value
    return result


def reject_nonfinite_number(value: str) -> NoReturn:
    fail(f"JSON contains non-finite number {value}")


def load_json(path: Path, context: str) -> Any:
    if not path.is_file():
        fail(f"{context} is missing: {path}")
    try:
        payload = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{context} is not valid UTF-8: {exc}")
    except OSError as exc:
        fail(f"cannot read {context}: {exc}")
    try:
        return json.loads(
            payload,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonfinite_number,
        )
    except json.JSONDecodeError as exc:
        fail(
            f"{context} is not valid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )


def manifest_nullable_int(raw: str, context: str) -> int | None:
    """Convert an optional CSV integer without treating zero as missing."""

    if raw == "":
        return None
    try:
        value = int(raw)
    except ValueError:
        fail(f"{context} must be an integer or empty in the manifest")
    if value < 0:
        fail(f"{context} must not be negative in the manifest")
    return value


def load_manifest(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        fail(f"source manifest is missing: {path}")
    try:
        with path.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
    except UnicodeDecodeError as exc:
        fail(f"source manifest is not valid UTF-8: {exc}")
    except (csv.Error, OSError) as exc:
        fail(f"cannot read source manifest: {exc}")

    missing_columns = sorted(MANIFEST_REQUIRED_COLUMNS - set(fieldnames))
    if missing_columns:
        fail(f"source manifest is missing columns: {missing_columns}")
    if len(rows) != EXPECTED_IMAGE_COUNT:
        fail(
            f"source manifest must contain {EXPECTED_IMAGE_COUNT} image rows, "
            f"found {len(rows)}"
        )

    article_keys: list[str] = []
    article_folders: dict[str, set[str]] = defaultdict(set)
    article_urls: dict[str, set[str]] = defaultdict(set)
    image_numbers: dict[str, list[str]] = defaultdict(list)

    for row_index, row in enumerate(rows, start=2):
        key = row["article_number"]
        if key not in EXPECTED_ARTICLE_KEYS:
            fail(f"manifest row {row_index} has invalid article_number {key!r}")
        if not article_keys or article_keys[-1] != key:
            article_keys.append(key)

        image_number = row["image_number"]
        if len(image_number) != 2 or not image_number.isascii() or not image_number.isdigit():
            fail(f"manifest row {row_index} has invalid image_number {image_number!r}")
        image_numbers[key].append(image_number)

        manifest_path = PurePosixPath(row["file_path"])
        if (
            manifest_path.is_absolute()
            or ".." in manifest_path.parts
            or len(manifest_path.parts) != 3
            or manifest_path.parts[0] != "articles"
            or manifest_path.name in {"", "."}
        ):
            fail(f"manifest row {row_index} has unsafe file_path {row['file_path']!r}")
        article_folders[key].add(manifest_path.parent.name)
        article_urls[key].add(row["article_url"])

        manifest_nullable_int(
            row["block_index"], f"manifest row {row_index} block_index"
        )
        manifest_nullable_int(
            row["gallery_index"], f"manifest row {row_index} gallery_index"
        )

    if tuple(article_keys) != EXPECTED_ARTICLE_KEYS:
        fail(f"manifest article order differs: {article_keys}")

    for key in EXPECTED_ARTICLE_KEYS:
        if len(article_folders[key]) != 1:
            fail(
                f"manifest article {key} maps to {len(article_folders[key])} folders"
            )
        if len(article_urls[key]) != 1:
            fail(f"manifest article {key} maps to {len(article_urls[key])} URLs")
        expected_numbers = [
            f"{number:02d}" for number in range(1, len(image_numbers[key]) + 1)
        ]
        if image_numbers[key] != expected_numbers:
            fail(
                f"manifest image order differs for article {key}: "
                f"{image_numbers[key]}"
            )

    return rows


def validate_range(
    item: object,
    text: str,
    context: str,
    *,
    range_kind: str,
) -> None:
    value = require_object(item, context)
    fields = INLINE_STYLE_FIELDS if range_kind == "inline style" else LINK_FIELDS
    require_exact_fields(value, fields, fields, context)
    offset = require_nonnegative_int(value["offset"], f"{context}.offset")
    length = require_nonnegative_int(value["length"], f"{context}.length")
    if length == 0:
        fail(f"{context}.length must be positive")
    text_boundaries = {0}
    utf16_length = 0
    for character in text:
        utf16_length += 2 if ord(character) > 0xFFFF else 1
        text_boundaries.add(utf16_length)
    range_end = offset + length
    if range_end > utf16_length:
        fail(
            f"{context} range {offset}:{range_end} exceeds "
            f"UTF-16 text length {utf16_length}"
        )
    if offset not in text_boundaries or range_end not in text_boundaries:
        fail(f"{context} range splits a UTF-16 surrogate pair")
    detail_field = "style" if range_kind == "inline style" else "url"
    require_string(value[detail_field], f"{context}.{detail_field}", nonempty=True)


def validate_ranges(block: dict[str, Any], text: str, context: str) -> None:
    for field, range_kind in (("inline_styles", "inline style"), ("links", "link")):
        ranges = block.get(field, [])
        if not isinstance(ranges, list):
            fail(f"{context}.{field} must be an array")
        for index, item in enumerate(ranges):
            validate_range(
                item,
                text,
                f"{context}.{field}[{index}]",
                range_kind=range_kind,
            )


def validate_text_block(block: dict[str, Any], context: str) -> str:
    block_type = block.get("type")
    if block_type not in TEXT_BLOCK_TYPES:
        fail(f"{context}.type has unsupported value {block_type!r}")
    required = TEXT_REQUIRED_FIELDS | TEXT_TYPE_FIELDS[block_type]
    require_exact_fields(block, required, required, context)
    require_nonnegative_int(
        block["source_block_index"], f"{context}.source_block_index"
    )
    text = require_string(block["text"], f"{context}.text")

    if block_type == "heading":
        level = block["level"]
        if not is_int(level) or not 1 <= level <= 6:
            fail(f"{context}.level must be an integer from 1 to 6")
    if block_type == "list_item":
        list_style = require_string(
            block["list_style"], f"{context}.list_style", nonempty=True
        )
        if list_style not in {"ordered", "unordered"}:
            fail(f"{context}.list_style must be 'ordered' or 'unordered'")
        require_nonnegative_int(block["depth"], f"{context}.depth")

    validate_ranges(block, text, context)
    return block_type


def expected_image_values(row: dict[str, str]) -> dict[str, object]:
    manifest_path = PurePosixPath(row["file_path"])
    return {
        "type": "image",
        "image_id": row["image_number"],
        "file": manifest_path.name,
        "manifest_file_path": row["file_path"],
        "role": row["image_role"],
        "source_image_id": row["image_id"],
        "source_block_index": manifest_nullable_int(
            row["block_index"],
            f"manifest {row['article_number']}/{row['image_number']} block_index",
        ),
        "gallery_index": manifest_nullable_int(
            row["gallery_index"],
            f"manifest {row['article_number']}/{row['image_number']} gallery_index",
        ),
        "duplicate_of": row["duplicate_of"] or None,
    }


def validate_image_block(
    block: dict[str, Any], row: dict[str, str], context: str
) -> None:
    require_exact_fields(block, IMAGE_FIELDS, IMAGE_FIELDS, context)
    for field in (
        "type",
        "image_id",
        "file",
        "manifest_file_path",
        "role",
        "source_image_id",
        "alt",
        "caption",
    ):
        require_string(block[field], f"{context}.{field}")
    require_nullable_nonnegative_int(
        block["source_block_index"], f"{context}.source_block_index"
    )
    require_nullable_nonnegative_int(
        block["gallery_index"], f"{context}.gallery_index"
    )
    if block["duplicate_of"] is not None:
        require_string(
            block["duplicate_of"], f"{context}.duplicate_of", nonempty=True
        )

    expected = expected_image_values(row)
    for field, expected_value in expected.items():
        if block[field] != expected_value:
            fail(
                f"{context}.{field} differs from manifest: "
                f"expected {expected_value!r}, found {block[field]!r}"
            )


def validate_cta_metadata(value: object, context: str) -> dict[str, Any]:
    cta = require_object(value, context)
    require_exact_fields(cta, CTA_FIELDS, CTA_FIELDS, context)
    for field in ("text", "link_to_open", "link_to_show"):
        require_string(cta[field], f"{context}.{field}")
    if not isinstance(cta["included_in_blocks"], bool):
        fail(f"{context}.included_in_blocks must be a boolean")
    return cta


def validate_cta_block(
    block: dict[str, Any], cta: dict[str, Any], context: str
) -> None:
    require_exact_fields(block, CTA_BLOCK_FIELDS, CTA_BLOCK_FIELDS, context)
    if block["type"] != "cta":
        fail(f"{context}.type must be 'cta'")
    if block["source_block_index"] is not None:
        fail(f"{context}.source_block_index must be null")
    require_string(block["text"], f"{context}.text")
    require_string(block["url"], f"{context}.url")
    if block["inline_styles"] != []:
        fail(f"{context}.inline_styles must be an empty array")
    if block["links"] != []:
        fail(f"{context}.links must be an empty array")
    if block["text"] != cta["text"]:
        fail(f"{context}.text differs from top-level cta.text")
    expected_url = cta["link_to_open"] or cta["link_to_show"]
    if block["url"] != expected_url:
        fail(f"{context}.url differs from the top-level CTA destination")


def validate_article(
    path: Path,
    article_key: str,
    article_folder: str,
    article_rows: list[dict[str, str]],
) -> tuple[Counter[str], list[tuple[str, str]], int, int]:
    context = path.as_posix()
    article = require_object(load_json(path, context), context)
    require_exact_fields(article, ARTICLE_FIELDS, ARTICLE_FIELDS, context)

    if article["schema_version"] != SCHEMA_VERSION:
        fail(
            f"{context}.schema_version must be {SCHEMA_VERSION!r}, "
            f"found {article['schema_version']!r}"
        )
    expected_number = int(article_key)
    if not is_int(article["article_number"]) or article["article_number"] != expected_number:
        fail(
            f"{context}.article_number must be integer {expected_number}, "
            f"found {article['article_number']!r}"
        )
    if article["article_key"] != article_key:
        fail(
            f"{context}.article_key must be {article_key!r}, "
            f"found {article['article_key']!r}"
        )
    if article["article_id"] != article_folder:
        fail(
            f"{context}.article_id must equal folder {article_folder!r}, "
            f"found {article['article_id']!r}"
        )
    require_string(article["article_key"], f"{context}.article_key")
    require_string(article["article_id"], f"{context}.article_id")

    source_url = require_http_url(article["url"], f"{context}.url")
    expected_urls = {row["article_url"] for row in article_rows}
    if source_url not in expected_urls or len(expected_urls) != 1:
        fail(
            f"{context}.url differs from manifest: "
            f"expected {sorted(expected_urls)}, found {source_url!r}"
        )
    require_http_url(article["final_url"], f"{context}.final_url")
    require_http_url(article["canonical_url"], f"{context}.canonical_url")
    require_string(
        article["publication_id"], f"{context}.publication_id", nonempty=True
    )
    require_nonnegative_int(
        article["publication_version"], f"{context}.publication_version"
    )
    require_string(article["title"], f"{context}.title", nonempty=True)
    require_string(article["lead"], f"{context}.lead")
    cta = validate_cta_metadata(article["cta"], f"{context}.cta")

    blocks = article["blocks"]
    if not isinstance(blocks, list):
        fail(f"{context}.blocks must be an array")

    block_types: Counter[str] = Counter()
    image_order: list[tuple[str, str]] = []
    image_index = 0
    image_source_zero_count = 0
    text_source_zero_count = 0
    cta_block_indices: list[int] = []

    for block_index, raw_block in enumerate(blocks):
        block_context = f"{context}.blocks[{block_index}]"
        block = require_object(raw_block, block_context)
        block_type = block.get("type")
        if block_type == "cta":
            validate_cta_block(block, cta, block_context)
            cta_block_indices.append(block_index)
            block_types["cta"] += 1
        elif block_type == "image":
            if image_index >= len(article_rows):
                fail(f"{block_context} is an extra image block")
            row = article_rows[image_index]
            validate_image_block(block, row, block_context)
            image_order.append((article_key, block["image_id"]))
            if block["source_block_index"] == 0:
                image_source_zero_count += 1
            image_index += 1
            block_types["image"] += 1
        else:
            text_type = validate_text_block(block, block_context)
            if block["source_block_index"] == 0:
                text_source_zero_count += 1
            block_types[text_type] += 1

    if image_index != len(article_rows):
        missing_rows = [row["image_number"] for row in article_rows[image_index:]]
        fail(f"{context} is missing manifest images in order: {missing_rows}")

    has_cta_text = bool(cta["text"].strip())
    if cta["included_in_blocks"] != has_cta_text:
        fail(
            f"{context}.cta.included_in_blocks must equal whether cta.text is non-empty"
        )
    expected_cta_count = 1 if has_cta_text else 0
    if len(cta_block_indices) != expected_cta_count:
        fail(
            f"{context} must contain {expected_cta_count} CTA blocks, "
            f"found {len(cta_block_indices)}"
        )
    if cta_block_indices and cta_block_indices[0] != len(blocks) - 1:
        fail(f"{context} CTA block must be the final block")

    return (
        block_types,
        image_order,
        image_source_zero_count,
        text_source_zero_count,
    )


def exception_is_unresolved(entry: object, context: str) -> bool:
    value = require_object(entry, context)
    resolved_marker = value.get("resolved")
    status_marker = value.get("status")

    if resolved_marker is not None and not isinstance(resolved_marker, bool):
        fail(f"{context}.resolved must be a boolean")
    if status_marker is not None and not isinstance(status_marker, str):
        fail(f"{context}.status must be a string")

    normalized_status = (
        status_marker.strip().lower() if isinstance(status_marker, str) else None
    )
    status_resolved = normalized_status in RESOLVED_EXCEPTION_STATUSES
    status_unresolved = normalized_status in UNRESOLVED_EXCEPTION_STATUSES

    if resolved_marker is True and status_unresolved:
        fail(f"{context} has conflicting resolved/status markers")
    if resolved_marker is False and status_resolved:
        fail(f"{context} has conflicting resolved/status markers")
    if resolved_marker is not None:
        return not resolved_marker
    if normalized_status is not None:
        return not status_resolved
    return True


def validate_exceptions(path: Path) -> tuple[int, int]:
    context = path.as_posix()
    payload = load_json(path, context)
    entries: list[tuple[object, str]] = []
    explicit_unresolved: list[tuple[object, str]] = []
    declared_unresolved_count: int | None = None

    if isinstance(payload, list):
        entries.extend(
            (entry, f"{context}[{index}]") for index, entry in enumerate(payload)
        )
    elif isinstance(payload, dict):
        for field in ("exceptions", "entries"):
            if field not in payload:
                continue
            collection = payload[field]
            if not isinstance(collection, list):
                fail(f"{context}.{field} must be an array")
            entries.extend(
                (entry, f"{context}.{field}[{index}]")
                for index, entry in enumerate(collection)
            )

        if "unresolved" in payload:
            unresolved = payload["unresolved"]
            if is_int(unresolved):
                if unresolved < 0:
                    fail(f"{context}.unresolved must not be negative")
                declared_unresolved_count = unresolved
            elif isinstance(unresolved, list):
                explicit_unresolved.extend(
                    (entry, f"{context}.unresolved[{index}]")
                    for index, entry in enumerate(unresolved)
                )
            else:
                fail(f"{context}.unresolved must be an array or integer")

        if "unresolved_count" in payload:
            count = payload["unresolved_count"]
            if not is_int(count) or count < 0:
                fail(f"{context}.unresolved_count must be a non-negative integer")
            if declared_unresolved_count is not None and count != declared_unresolved_count:
                fail(f"{context} has conflicting unresolved counts")
            declared_unresolved_count = count
    else:
        fail(f"{context} must be a JSON object or array")

    for entry, entry_context in explicit_unresolved:
        value = require_object(entry, entry_context)
        require_exact_fields(
            value,
            UNRESOLVED_FIELDS,
            UNRESOLVED_FIELDS,
            entry_context,
        )
        article_number = value["article_number"]
        if not is_int(article_number) or not 1 <= article_number <= EXPECTED_ARTICLE_COUNT:
            fail(f"{entry_context}.article_number must be an integer from 1 to 20")
        expected_key = f"{article_number:02d}"
        if value["article_key"] != expected_key:
            fail(
                f"{entry_context}.article_key must be {expected_key!r}, "
                f"found {value['article_key']!r}"
            )
        require_string(value["article_id"], f"{entry_context}.article_id", nonempty=True)
        require_string(value["field"], f"{entry_context}.field", nonempty=True)
        require_string(
            value["source_path"], f"{entry_context}.source_path", nonempty=True
        )
        require_string(value["reason"], f"{entry_context}.reason", nonempty=True)

    unresolved_entries = [
        entry_context
        for entry, entry_context in entries
        if exception_is_unresolved(entry, entry_context)
    ]
    unresolved_count = len(unresolved_entries) + len(explicit_unresolved)
    if declared_unresolved_count is not None and declared_unresolved_count != unresolved_count:
        fail(
            f"{context} declares {declared_unresolved_count} unresolved entries, "
            f"found {unresolved_count}"
        )
    return len(entries) + len(explicit_unresolved), unresolved_count


def normalized_report(value: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(value)
    normalized.pop("generated_at", None)
    return normalized


def compare_committed_report(path: Path, summary: dict[str, Any]) -> None:
    context = path.as_posix()
    report = require_object(load_json(path, context), context)
    committed = normalized_report(report)
    expected = normalized_report(summary)
    if committed != expected:
        all_keys = sorted(set(committed) | set(expected))
        differing = [key for key in all_keys if committed.get(key) != expected.get(key)]
        fail(
            f"{context} differs from computed verification summary in fields "
            f"{differing}; rerun with --write-report after reviewing the dataset"
        )


def atomic_write_report(path: Path, summary: dict[str, Any]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as target:
            temporary_path = Path(target.name)
            json.dump(summary, target, ensure_ascii=False, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    except OSError as exc:
        fail(f"cannot atomically write verification report {path}: {exc}")
    finally:
        if temporary_path is not None and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def verify_dataset(output_root: Path, manifest_path: Path) -> dict[str, Any]:
    rows = load_manifest(manifest_path)
    articles_root = output_root / "articles"
    if not articles_root.is_dir():
        fail(f"article-content directory is missing: {articles_root}")

    rows_by_article: dict[str, list[dict[str, str]]] = defaultdict(list)
    folder_by_article: dict[str, str] = {}
    for row in rows:
        key = row["article_number"]
        rows_by_article[key].append(row)
        folder = PurePosixPath(row["file_path"]).parent.name
        previous = folder_by_article.setdefault(key, folder)
        if previous != folder:
            fail(f"manifest article {key} maps to conflicting folders")

    expected_folders = {folder_by_article[key] for key in EXPECTED_ARTICLE_KEYS}
    actual_folders = {path.name for path in articles_root.iterdir() if path.is_dir()}
    if actual_folders != expected_folders:
        fail(
            "article-content folders differ from manifest: "
            f"missing={sorted(expected_folders - actual_folders)}, "
            f"extra={sorted(actual_folders - expected_folders)}"
        )
    if len(actual_folders) != EXPECTED_ARTICLE_COUNT:
        fail(
            f"expected exactly {EXPECTED_ARTICLE_COUNT} article folders, "
            f"found {len(actual_folders)}"
        )

    expected_content_paths = {
        articles_root / folder_by_article[key] / "content.json"
        for key in EXPECTED_ARTICLE_KEYS
    }
    actual_content_paths = set(articles_root.rglob("content.json"))
    if actual_content_paths != expected_content_paths:
        fail(
            "content.json coverage differs: "
            f"missing={sorted(str(path) for path in expected_content_paths - actual_content_paths)}, "
            f"extra={sorted(str(path) for path in actual_content_paths - expected_content_paths)}"
        )

    block_types: Counter[str] = Counter()
    actual_image_order: list[tuple[str, str]] = []
    image_source_zero_count = 0
    text_source_zero_count = 0

    for key in EXPECTED_ARTICLE_KEYS:
        folder = folder_by_article[key]
        article_block_types, article_images, image_zeros, text_zeros = validate_article(
            articles_root / folder / "content.json",
            key,
            folder,
            rows_by_article[key],
        )
        block_types.update(article_block_types)
        actual_image_order.extend(article_images)
        image_source_zero_count += image_zeros
        text_source_zero_count += text_zeros

    expected_image_order = [
        (row["article_number"], row["image_number"]) for row in rows
    ]
    if actual_image_order != expected_image_order:
        fail("global image occurrence order differs from the source manifest")
    if block_types["image"] != EXPECTED_IMAGE_COUNT:
        fail(
            f"expected {EXPECTED_IMAGE_COUNT} image blocks, "
            f"found {block_types['image']}"
        )

    exception_count, unresolved_exception_count = validate_exceptions(
        output_root / "exceptions.json"
    )
    images_per_article = Counter(row["article_number"] for row in rows)
    text_block_count = sum(
        count for block_type, count in block_types.items() if block_type != "image"
    )

    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "article_count": EXPECTED_ARTICLE_COUNT,
        "block_count": sum(block_types.values()),
        "text_block_count": text_block_count,
        "image_block_count": block_types["image"],
        "block_types": dict(sorted(block_types.items())),
        "images_per_article": dict(sorted(images_per_article.items())),
        "image_source_block_zero_count": image_source_zero_count,
        "text_source_block_zero_count": text_source_zero_count,
        "exception_count": exception_count,
        "unresolved_exception_count": unresolved_exception_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify PROMOPAGES-9884 article content against the image manifest"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("PROMOPAGES-9884"),
        help="article-content dataset root (default: PROMOPAGES-9884)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("PROMOPAGES-9857/articles/manifest.csv"),
        help="source image manifest",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="atomically write PROMOPAGES-9884/verification-report.json",
    )
    args = parser.parse_args(argv)

    output_root = args.output_root.resolve()
    manifest_path = args.manifest.resolve()
    report_path = output_root / "verification-report.json"

    try:
        summary = verify_dataset(output_root, manifest_path)
        if args.write_report:
            atomic_write_report(report_path, summary)
        else:
            compare_committed_report(report_path, summary)
    except VerificationError as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
