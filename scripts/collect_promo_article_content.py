#!/usr/bin/env python3
"""Export ordered PromoPages article content.

The public article HTML embeds both publication metadata and the DraftJS editor
state in ``w._data``.  The editor state is the source of truth for body text and
body-image order.  The PROMOPAGES-9857 manifest remains the source of truth for
the stable two-digit image identifiers and filenames used by this export.

No text, lead, caption, alt text, CTA, or image position is synthesized.  A
source mismatch fails closed instead of producing a plausible-looking export.

With no command-line overrides the PROMOPAGES-9884 export remains unchanged.
Namespaced image manifests are mirrored below the same safe dataset prefix in
the output root.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "1.0"
EXPECTED_ARTICLE_COUNT = 21
DEFAULT_MANIFEST = Path("PROMOPAGES-9857/articles/manifest.csv")
DEFAULT_OUTPUT_ROOT = Path("PROMOPAGES-9884")

REQUIRED_MANIFEST_FIELDS = {
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

TEXT_BLOCK_TYPES = {
    "unstyled": "paragraph",
    "header-two": "heading",
    "header-three": "heading",
    "blockquote": "quote",
    "unordered-list-item": "list_item",
    "ordered-list-item": "list_item",
    "legal": "legal",
}

HEADING_LEVELS = {
    "header-two": 2,
    "header-three": 3,
}

PRESENTATION_DATA_KEYS = {
    "background",
    "key",
    "linkTextColor",
    "theme",
}

IMAGE_DATA_KEYS = PRESENTATION_DATA_KEYS | {
    "animationEnabled",
    "contents",
    "image",
    "images",
}

SUPPORTED_INLINE_STYLES = {"BOLD", "ITALIC"}


def _safe_path_component(value: str, field: str) -> str:
    """Return one traversal-safe relative path component."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{field} must be one relative path component: {value!r}")
    if value != value.strip() or any(
        not (character.isalnum() or character in "._-") for character in value
    ):
        raise ValueError(f"{field} contains unsafe characters: {value!r}")
    return value


def _manifest_file_location(value: str) -> tuple[str, str, str]:
    """Parse ``[prefix/]articles/<article>/<file>`` without traversal."""

    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"unexpected manifest file_path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValueError(f"unexpected manifest file_path: {value!r}")
    parts = path.parts
    if len(parts) == 3 and parts[0] == "articles":
        prefix = ""
        article_id, filename = parts[1:]
    elif len(parts) == 4 and parts[1] == "articles":
        prefix = _safe_path_component(parts[0], "manifest dataset prefix")
        article_id, filename = parts[2:]
    else:
        raise ValueError(f"unexpected manifest file_path: {value!r}")
    _safe_path_component(article_id, "manifest article folder")
    _safe_path_component(filename, "manifest image filename")
    return prefix, article_id, filename


def _manifest_dataset_prefix(
    grouped_rows: list[list[dict[str, str]]],
) -> str:
    prefixes = {
        _manifest_file_location(row["file_path"])[0]
        for rows in grouped_rows
        for row in rows
    }
    if len(prefixes) != 1:
        raise ValueError(f"manifest rows disagree on dataset prefix: {sorted(prefixes)}")
    return next(iter(prefixes))


def fetch(url: str, retries: int = 3) -> tuple[bytes, str]:
    """Fetch a public article and return its bytes and effective URL."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 PromoPagesContentDataset/1.0"
            ),
            "Accept-Encoding": "identity",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read(), response.geturl()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def extract_page_data(html: bytes) -> dict[str, Any]:
    """Extract the JSON value assigned to ``w._data`` in SSR HTML."""

    text = html.decode("utf-8")
    marker = "w._data = "
    start = text.find(marker)
    if start < 0:
        raise ValueError("w._data marker is missing")
    value, _ = json.JSONDecoder().raw_decode(text, start + len(marker))
    if not isinstance(value, dict):
        raise ValueError("w._data is not a JSON object")
    return value


def _required_string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise ValueError(f"{field} must not be empty")
    return value


def _optional_string(value: Any, field: str) -> str:
    if value is None:
        return ""
    return _required_string(value, field, allow_empty=True)


def _gallery_caption(value: Any, field: str) -> str:
    """Read both legacy string and current structured gallery captions.

    PromoPages may store a gallery caption as ``{"text": ..., "links": []}``.
    The Lite context consumes the authored text.  Link-bearing or otherwise
    extended objects remain fail-closed until their semantics are represented
    in the exported schema.
    """

    if not isinstance(value, dict):
        return _optional_string(value, field)
    unknown = set(value) - {"text", "links"}
    if unknown:
        raise ValueError(f"{field} has unsupported fields: {sorted(unknown)}")
    links = value.get("links", [])
    if not isinstance(links, list):
        raise ValueError(f"{field} links must be a list")
    if links:
        raise ValueError(f"{field} links are not represented in the export schema")
    return _optional_string(value.get("text"), f"{field} text")


def _optional_int(value: str, field: str) -> int | None:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an integer or empty: {value!r}") from error


def _article_identity(rows: list[dict[str, str]]) -> tuple[int, str, str, str]:
    if not rows:
        raise ValueError("article manifest rows are empty")

    article_keys = {row["article_number"] for row in rows}
    urls = {row["article_url"] for row in rows}
    if len(article_keys) != 1 or len(urls) != 1:
        raise ValueError("article rows disagree on article_number or article_url")

    article_key = next(iter(article_keys))
    try:
        article_number = int(article_key)
    except ValueError as error:
        raise ValueError(f"invalid article_number: {article_key!r}") from error
    if article_key != f"{article_number:02d}":
        raise ValueError(f"article_number must be zero padded: {article_key!r}")

    article_ids: set[str] = set()
    dataset_prefixes: set[str] = set()
    for row in rows:
        dataset_prefix, article_id, _ = _manifest_file_location(row["file_path"])
        dataset_prefixes.add(dataset_prefix)
        article_ids.add(article_id)
    if len(dataset_prefixes) != 1:
        raise ValueError(
            "article rows disagree on dataset prefix: "
            f"{sorted(dataset_prefixes)}"
        )
    if len(article_ids) != 1:
        raise ValueError(f"article rows disagree on folder: {sorted(article_ids)}")

    return article_number, article_key, next(iter(article_ids)), next(iter(urls))


def _normalize_range(
    value: Any,
    field: str,
    text: str,
) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must contain objects")
    offset = value.get("offset")
    length = value.get("length")
    if not isinstance(offset, int) or not isinstance(length, int):
        raise ValueError(f"{field} offset and length must be integers")
    if offset < 0 or length < 0:
        raise ValueError(f"{field} offset and length must be non-negative")
    utf16_length = len(text.encode("utf-16-le")) // 2
    if offset + length > utf16_length:
        raise ValueError(
            f"{field} range {offset}:{length} exceeds UTF-16 length {utf16_length}"
        )
    return offset, length


def _inline_styles(block: dict[str, Any], text: str) -> list[dict[str, Any]]:
    values = block.get("inlineStyleRanges") or []
    if not isinstance(values, list):
        raise ValueError("inlineStyleRanges must be a list")
    result: list[dict[str, Any]] = []
    for value in values:
        offset, length = _normalize_range(value, "inlineStyleRanges", text)
        style = value.get("style")
        if style not in SUPPORTED_INLINE_STYLES:
            raise ValueError(f"unsupported inline style: {style!r}")
        result.append({"offset": offset, "length": length, "style": style})
    return result


def _entity(entity_map: dict[str, Any], key: Any) -> dict[str, Any]:
    candidates = (str(key), key)
    entity = next((entity_map[item] for item in candidates if item in entity_map), None)
    if not isinstance(entity, dict):
        raise ValueError(f"entity range references missing entity {key!r}")
    if entity.get("type") != "LINK":
        raise ValueError(f"unsupported entity type: {entity.get('type')!r}")
    return entity


def _links(
    block: dict[str, Any],
    text: str,
    entity_map: dict[str, Any],
) -> list[dict[str, Any]]:
    values = block.get("entityRanges") or []
    if not isinstance(values, list):
        raise ValueError("entityRanges must be a list")
    result: list[dict[str, Any]] = []
    for value in values:
        offset, length = _normalize_range(value, "entityRanges", text)
        entity = _entity(entity_map, value.get("key"))
        data = entity.get("data") or {}
        if not isinstance(data, dict):
            raise ValueError("LINK entity data must be an object")
        url = data.get("url") or data.get("href")
        url = _required_string(url, "LINK entity URL")
        result.append({"offset": offset, "length": length, "url": url})
    return result


def _text_block(
    raw_block: dict[str, Any],
    block_index: int,
    entity_map: dict[str, Any],
) -> dict[str, Any]:
    raw_type = raw_block.get("type")
    output_type = TEXT_BLOCK_TYPES.get(raw_type)
    if output_type is None:
        raise ValueError(f"unsupported DraftJS block type: {raw_type!r}")

    data = raw_block.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError(f"block {block_index} data must be an object")
    unknown_data = set(data) - PRESENTATION_DATA_KEYS
    if unknown_data:
        raise ValueError(
            f"block {block_index} has unhandled data keys: {sorted(unknown_data)}"
        )

    text = _required_string(
        raw_block.get("text"),
        f"block {block_index} text",
        allow_empty=True,
    )
    output: dict[str, Any] = {
        "type": output_type,
        "source_block_index": block_index,
        "text": text,
    }
    if raw_type in HEADING_LEVELS:
        output["level"] = HEADING_LEVELS[raw_type]
    if raw_type in {"ordered-list-item", "unordered-list-item"}:
        depth = raw_block.get("depth", 0)
        if not isinstance(depth, int) or depth < 0:
            raise ValueError(f"block {block_index} has invalid list depth")
        output["list_style"] = (
            "ordered" if raw_type == "ordered-list-item" else "unordered"
        )
        output["depth"] = depth
    output["inline_styles"] = _inline_styles(raw_block, text)
    output["links"] = _links(raw_block, text, entity_map)
    return output


def _image_block(
    row: dict[str, str],
    *,
    caption: str,
) -> dict[str, Any]:
    path = Path(row["file_path"])
    return {
        "type": "image",
        "image_id": row["image_number"],
        "file": path.name,
        "manifest_file_path": row["file_path"],
        "role": row["image_role"],
        "source_image_id": row["image_id"],
        "source_block_index": _optional_int(
            row["block_index"], "manifest block_index"
        ),
        "gallery_index": _optional_int(
            row["gallery_index"], "manifest gallery_index"
        ),
        # PromoPages does not expose an author-supplied alt field.  The DOM
        # derives alt from the title/caption, which must not be presented as
        # source data.
        "alt": "",
        "caption": caption.strip(),
        "duplicate_of": row["duplicate_of"] or None,
    }


def _cover_rows(
    rows: list[dict[str, str]],
    publication: dict[str, Any],
) -> list[dict[str, str]]:
    covers = [row for row in rows if row["block_index"] == ""]
    if not covers:
        raise ValueError("manifest has no cover image")

    head_image = publication.get("headImage") or {}
    if not isinstance(head_image, dict):
        raise ValueError("publication.headImage must be an object")
    source_ids: list[str] = []
    for field in ("imageDesktop", "imageMobile"):
        image = head_image.get(field) or {}
        if not isinstance(image, dict):
            raise ValueError(f"publication.headImage.{field} must be an object")
        image_id = image.get("id")
        if image_id and image_id not in source_ids:
            source_ids.append(_required_string(image_id, f"headImage.{field}.id"))

    manifest_ids = [row["image_id"] for row in covers]
    if manifest_ids != source_ids:
        raise ValueError(
            "cover images differ between page and manifest: "
            f"page={source_ids}, manifest={manifest_ids}"
        )

    expected_roles = ["cover"] + ["cover_mobile"] * max(0, len(covers) - 1)
    actual_roles = [row["image_role"] for row in covers]
    if actual_roles != expected_roles:
        raise ValueError(
            f"unexpected manifest cover roles: {actual_roles}, expected {expected_roles}"
        )
    return covers


def _body_manifest_rows(
    rows: list[dict[str, str]],
) -> dict[tuple[int, int | None], dict[str, str]]:
    result: dict[tuple[int, int | None], dict[str, str]] = {}
    for row in rows:
        block_index = _optional_int(row["block_index"], "manifest block_index")
        if block_index is None:
            continue
        gallery_index = _optional_int(
            row["gallery_index"], "manifest gallery_index"
        )
        key = (block_index, gallery_index)
        if key in result:
            raise ValueError(f"duplicate manifest image position: {key}")
        result[key] = row
    return result


def _image_references(
    raw_block: dict[str, Any],
    block_index: int,
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    data = raw_block.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError(f"image block {block_index} data must be an object")
    unknown_data = set(data) - IMAGE_DATA_KEYS
    if unknown_data:
        raise ValueError(
            f"image block {block_index} has unhandled data keys: {sorted(unknown_data)}"
        )

    is_gallery = "images" in data
    if is_gallery:
        references = data.get("images")
        if not isinstance(references, list) or not references:
            raise ValueError(f"gallery block {block_index} has no images")
        first = data.get("image")
        if first is not None:
            first_reference = references[0]
            if (
                not isinstance(first, dict)
                or not isinstance(first_reference, dict)
                or first.get("id") != first_reference.get("id")
            ):
                raise ValueError(
                    f"gallery block {block_index} data.image does not match first slide"
                )
    else:
        reference = data.get("image")
        if not isinstance(reference, dict):
            raise ValueError(f"image block {block_index} has no image object")
        references = [reference]

    normalized: list[dict[str, Any]] = []
    for gallery_index, reference in enumerate(references):
        if not isinstance(reference, dict):
            raise ValueError(
                f"image block {block_index}/{gallery_index} reference is not an object"
            )
        image_id = reference.get("id")
        _required_string(image_id, f"image block {block_index}/{gallery_index} id")
        normalized.append(reference)
    return normalized, is_gallery, data


def _validate_entity_map(entity_map: dict[str, Any]) -> None:
    for key, value in entity_map.items():
        if not isinstance(value, dict):
            raise ValueError(f"entity {key!r} must be an object")
        if value.get("type") != "LINK":
            raise ValueError(f"unsupported entity type: {value.get('type')!r}")


def build_article_content(
    article_rows: list[dict[str, str]],
    page_data: dict[str, Any],
    final_url: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build one article's content document and explicit unresolved list."""

    rows = sorted(article_rows, key=lambda row: int(row["image_number"]))
    article_number, article_key, article_id, requested_url = _article_identity(rows)
    expected_numbers = [f"{index:02d}" for index in range(1, len(rows) + 1)]
    actual_numbers = [row["image_number"] for row in rows]
    if actual_numbers != expected_numbers:
        raise ValueError(
            f"article {article_key} image numbers are not continuous: {actual_numbers}"
        )

    publication = page_data.get("publication")
    if not isinstance(publication, dict):
        raise ValueError("page data has no publication object")
    content = publication.get("content") or {}
    if not isinstance(content, dict):
        raise ValueError("publication.content must be an object")
    preview = content.get("preview") or {}
    if not isinstance(preview, dict):
        raise ValueError("publication content/preview must be objects")

    title = _required_string(preview.get("title"), "publication preview title")
    lead = _optional_string(preview.get("snippet"), "publication preview snippet")
    unresolved: list[dict[str, Any]] = []
    if not lead.strip():
        unresolved.append(
            {
                "article_number": article_number,
                "article_key": article_key,
                "article_id": article_id,
                "field": "lead",
                "source_path": "publication.content.preview.snippet",
                "reason": "source field is empty; no fallback was generated",
            }
        )

    article_content = content.get("articleContent") or {}
    if not isinstance(article_content, dict):
        raise ValueError("publication.content.articleContent must be an object")
    raw_state = article_content.get("contentState")
    if isinstance(raw_state, str):
        parsed_state = json.loads(raw_state)
    elif isinstance(raw_state, dict):
        parsed_state = raw_state
    else:
        raise ValueError("articleContent.contentState must be JSON text or an object")
    draft_state = parsed_state.get("draftJsState")
    if not isinstance(draft_state, dict):
        raise ValueError("contentState has no draftJsState object")
    raw_blocks = draft_state.get("blocks")
    entity_map = draft_state.get("entityMap") or {}
    if not isinstance(raw_blocks, list) or not isinstance(entity_map, dict):
        raise ValueError("draftJsState blocks/entityMap have invalid types")
    _validate_entity_map(entity_map)

    output_blocks: list[dict[str, Any]] = [
        _image_block(row, caption="") for row in _cover_rows(rows, publication)
    ]
    body_rows = _body_manifest_rows(rows)
    consumed_positions: set[tuple[int, int | None]] = set()

    for block_index, raw_block in enumerate(raw_blocks):
        if not isinstance(raw_block, dict):
            raise ValueError(f"DraftJS block {block_index} must be an object")
        raw_type = raw_block.get("type")
        if raw_type != "atomic:image":
            output_blocks.append(_text_block(raw_block, block_index, entity_map))
            continue

        references, is_gallery, data = _image_references(raw_block, block_index)
        block_caption = _required_string(
            raw_block.get("text"),
            f"image block {block_index} text",
            allow_empty=True,
        )
        contents = data.get("contents") or {}
        if not isinstance(contents, dict):
            raise ValueError(f"image block {block_index} contents must be an object")

        for gallery_index, reference in enumerate(references):
            position = (block_index, gallery_index if is_gallery else None)
            row = body_rows.get(position)
            if row is None:
                raise ValueError(
                    f"page image at position {position} is missing from manifest"
                )
            source_image_id = _required_string(
                reference.get("id"), f"image block {block_index} source id"
            )
            if source_image_id != row["image_id"]:
                raise ValueError(
                    f"image mismatch at {position}: page={source_image_id}, "
                    f"manifest={row['image_id']}"
                )
            expected_role = "gallery_image" if is_gallery else "article_image"
            if row["image_role"] != expected_role:
                raise ValueError(
                    f"image role mismatch at {position}: {row['image_role']!r}"
                )

            if is_gallery and gallery_index > 0:
                raw_caption = contents.get(source_image_id, "")
                caption = _gallery_caption(
                    raw_caption,
                    f"gallery caption {block_index}/{gallery_index}",
                )
            else:
                caption = block_caption
            output_blocks.append(_image_block(row, caption=caption))
            consumed_positions.add(position)

    unconsumed = sorted(set(body_rows) - consumed_positions)
    if unconsumed:
        raise ValueError(f"manifest image positions are absent from page: {unconsumed}")

    swipe_to_site = publication.get("swipeToSite") or {}
    if not isinstance(swipe_to_site, dict):
        raise ValueError("publication.swipeToSite must be an object")
    cta_text = _optional_string(swipe_to_site.get("callToAction"), "CTA text")
    link_to_open = _optional_string(
        swipe_to_site.get("linkToOpen"), "CTA linkToOpen"
    )
    link_to_show = _optional_string(
        swipe_to_site.get("linkToShow"), "CTA linkToShow"
    )
    included_cta = bool(cta_text.strip())
    if included_cta:
        cta_url = link_to_open or link_to_show
        if not cta_url:
            raise ValueError(f"article {article_key} CTA has text but no URL")
        output_blocks.append(
            {
                "type": "cta",
                "source_block_index": None,
                "text": cta_text,
                "url": cta_url,
                "inline_styles": [],
                "links": [],
            }
        )

    publication_id = publication.get("id")
    if not isinstance(publication_id, (str, int)):
        raise ValueError("publication.id must be a string or integer")
    publication_version = publication.get("version")
    if not isinstance(publication_version, int):
        raise ValueError("publication.version must be an integer")

    result = {
        "schema_version": SCHEMA_VERSION,
        "article_number": article_number,
        "article_key": article_key,
        "article_id": article_id,
        "url": requested_url,
        "final_url": _required_string(final_url, "effective article URL"),
        "canonical_url": _optional_string(
            page_data.get("canonicalUrl"), "canonical article URL"
        ),
        "publication_id": str(publication_id),
        "publication_version": publication_version,
        "title": title,
        "lead": lead,
        "cta": {
            "text": cta_text,
            "link_to_open": link_to_open,
            "link_to_show": link_to_show,
            "included_in_blocks": included_cta,
        },
        "blocks": output_blocks,
    }
    return result, unresolved


def load_manifest(
    path: Path,
    expected_article_count: int = EXPECTED_ARTICLE_COUNT,
) -> list[list[dict[str, str]]]:
    if (
        isinstance(expected_article_count, bool)
        or not isinstance(expected_article_count, int)
        or expected_article_count < 1
    ):
        raise ValueError("expected article count must be a positive integer")
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_MANIFEST_FIELDS - fieldnames
        if missing:
            raise ValueError(f"manifest is missing fields: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("manifest has no rows")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["article_number"]].append(row)
    article_keys: list[str] = []
    for key in grouped:
        try:
            number = int(key)
        except ValueError as error:
            raise ValueError(f"invalid manifest article number: {key!r}") from error
        if number < 1 or key != f"{number:02d}":
            raise ValueError(f"invalid manifest article number: {key!r}")
        article_keys.append(key)
    article_keys.sort(key=int)

    if expected_article_count == EXPECTED_ARTICLE_COUNT:
        expected = [
            f"{number:02d}" for number in range(1, EXPECTED_ARTICLE_COUNT + 1)
        ]
        if article_keys != expected:
            raise ValueError(f"manifest article numbers differ: {article_keys}")
    elif len(article_keys) != expected_article_count:
        raise ValueError(f"manifest article numbers differ: {sorted(grouped)}")
    grouped_rows = [grouped[key] for key in article_keys]
    _manifest_dataset_prefix(grouped_rows)
    return grouped_rows


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def collect(
    manifest_path: Path,
    output_root: Path,
    expected_article_count: int = EXPECTED_ARTICLE_COUNT,
) -> dict[str, Any]:
    grouped_rows = load_manifest(manifest_path, expected_article_count)
    dataset_prefix = _manifest_dataset_prefix(grouped_rows)
    dataset_root = output_root / dataset_prefix
    unresolved: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    image_count = 0
    link_count = 0

    for article_rows in grouped_rows:
        article_number, article_key, article_id, url = _article_identity(article_rows)
        print(
            f"[{article_key}/{expected_article_count:02d}] {article_id}",
            flush=True,
        )
        html, final_url = fetch(url)
        page_data = extract_page_data(html)
        content, article_unresolved = build_article_content(
            article_rows,
            page_data,
            final_url,
        )
        atomic_write_json(
            dataset_root / "articles" / article_id / "content.json",
            content,
        )
        unresolved.extend(article_unresolved)
        for block in content["blocks"]:
            type_counts[block["type"]] += 1
            image_count += block["type"] == "image"
            link_count += len(block.get("links", []))

    exceptions = {
        "schema_version": SCHEMA_VERSION,
        "unresolved": unresolved,
        "source_limitations": [
            {
                "scope": "all image blocks",
                "field": "alt",
                "reason": (
                    "PromoPages editor state and image catalogue expose no "
                    "author-supplied alt field; alt is left empty and no DOM-derived "
                    "fallback is stored"
                ),
            },
            {
                "scope": "article metadata",
                "field": "lead",
                "reason": (
                    "lead stores publication.content.preview.snippet exactly; it may "
                    "be empty, long, or overlap body text, and is never synthesized"
                ),
            },
        ],
    }
    atomic_write_json(dataset_root / "exceptions.json", exceptions)
    return {
        "articles": len(grouped_rows),
        "blocks": sum(type_counts.values()),
        "block_types": dict(sorted(type_counts.items())),
        "image_blocks": image_count,
        "links": link_count,
        "unresolved": len(unresolved),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="PROMOPAGES-9857 image manifest",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="directory that will contain the content export",
    )
    parser.add_argument(
        "--expected-article-count",
        type=int,
        default=EXPECTED_ARTICLE_COUNT,
        help=(
            "required article count; the historical default also enforces "
            f"contiguous keys 01..{EXPECTED_ARTICLE_COUNT}"
        ),
    )
    args = parser.parse_args()

    summary = collect(
        args.manifest,
        args.output_root,
        args.expected_article_count,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
