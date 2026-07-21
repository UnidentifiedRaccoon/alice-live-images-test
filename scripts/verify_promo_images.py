#!/usr/bin/env python3
"""Independently verify the PROMOPAGES-9857 image dataset and its manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


GRAPHIC_PRIMARY_CLASS = "text_interface_collage"
GRAPHIC_KIND_VALUES = (
    "banner",
    "ui_screenshot",
    "floor_plan",
    "map",
    "table",
    "chart",
    "diagram",
    "text_document",
    "collage",
)
BASE_CLASSIFICATION_FIELDS = (
    "primary_class",
    "scene_tags",
    "scene_description",
    "motion_cues",
    "risk_notes",
)
MANIFEST_CLASSIFICATION_FIELDS = (
    "primary_class",
    "graphic_kind",
    "graphic_kinds",
    "scene_tags",
    "scene_description",
    "motion_cues",
    "risk_notes",
)

EXPECTED_ARTICLE_COUNT = 20


def fail(message: str) -> None:
    raise AssertionError(message)


def parse_graphic_routing(row: dict[str, str], occurrence: str) -> tuple[str, ...]:
    active_kind = row["graphic_kind"].strip()
    raw_kinds = row["graphic_kinds"].strip()
    if row["primary_class"] != GRAPHIC_PRIMARY_CLASS:
        if active_kind or raw_kinds:
            fail(f"{occurrence} has graphic routing outside {GRAPHIC_PRIMARY_CLASS}")
        return ()
    if not active_kind or not raw_kinds:
        fail(f"{occurrence} has incomplete graphic routing")
    kinds = tuple(kind.strip() for kind in raw_kinds.split(";"))
    if any(not kind for kind in kinds):
        fail(f"{occurrence} has an empty graphic kind")
    if len(kinds) != len(set(kinds)):
        fail(f"{occurrence} has duplicate graphic kinds")
    unknown = [kind for kind in kinds if kind not in GRAPHIC_KIND_VALUES]
    if unknown or active_kind not in GRAPHIC_KIND_VALUES:
        fail(
            f"{occurrence} has unknown graphic routing: "
            f"active={active_kind!r}, kinds={unknown}"
        )
    if kinds[0] != active_kind:
        fail(f"{occurrence} must place active graphic_kind first")
    return kinds


def annotation_graphic_routing(
    image_id: str, annotation: dict[str, object]
) -> tuple[str, tuple[str, ...]]:
    primary_class = annotation.get("primary_class")
    active_kind = annotation.get("graphic_kind", "")
    raw_kinds = annotation.get("graphic_kinds", [])
    if primary_class != GRAPHIC_PRIMARY_CLASS:
        if active_kind or raw_kinds:
            fail(
                f"annotation {image_id} has graphic routing outside "
                f"{GRAPHIC_PRIMARY_CLASS}"
            )
        return "", ()
    if not isinstance(active_kind, str) or not active_kind:
        fail(f"annotation {image_id} has no active graphic_kind")
    if not isinstance(raw_kinds, list) or not raw_kinds:
        fail(f"annotation {image_id} has no graphic_kinds")
    if any(not isinstance(kind, str) or not kind for kind in raw_kinds):
        fail(f"annotation {image_id} has invalid graphic_kinds")
    kinds = tuple(raw_kinds)
    if len(kinds) != len(set(kinds)):
        fail(f"annotation {image_id} has duplicate graphic_kinds")
    unknown = [kind for kind in kinds if kind not in GRAPHIC_KIND_VALUES]
    if unknown or active_kind not in GRAPHIC_KIND_VALUES:
        fail(
            f"annotation {image_id} has unknown graphic routing: "
            f"active={active_kind!r}, kinds={unknown}"
        )
    if kinds[0] != active_kind:
        fail(f"annotation {image_id} must place active graphic_kind first")
    return active_kind, kinds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root", type=Path, default=Path("PROMOPAGES-9857")
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write articles/verification-report.json after a successful check",
    )
    args = parser.parse_args()

    root = args.output_root.resolve()
    articles_root = root / "articles"
    manifest_path = articles_root / "manifest.csv"
    taxonomy_path = articles_root / "taxonomy.md"
    annotations_path = root / "classifications.json"
    with manifest_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    if not rows:
        fail("manifest has no rows")
    missing_columns = set(MANIFEST_CLASSIFICATION_FIELDS) - set(fieldnames)
    if missing_columns:
        fail(f"manifest is missing columns: {sorted(missing_columns)}")

    article_numbers = sorted({row["article_number"] for row in rows})
    expected_article_numbers = [
        f"{number:02d}" for number in range(1, EXPECTED_ARTICLE_COUNT + 1)
    ]
    if article_numbers != expected_article_numbers:
        fail(f"article numbers differ: {article_numbers}")

    article_urls: dict[str, set[str]] = defaultdict(set)
    article_folders: dict[str, set[str]] = defaultdict(set)
    image_numbers: dict[str, list[int]] = defaultdict(list)
    expected_files: set[Path] = set()
    seen_by_id: dict[str, dict[str, str]] = {}
    class_by_id: dict[str, tuple[str, ...]] = {}
    graphic_route_counts: Counter[str] = Counter()
    graphic_kind_presence: Counter[str] = Counter()
    total_bytes = 0

    for row in rows:
        article = row["article_number"]
        article_urls[article].add(row["article_url"])
        image_numbers[article].append(int(row["image_number"]))
        if row["download_status"] != "ok":
            fail(
                f"{article}/{row['image_number']} has status "
                f"{row['download_status']!r}"
            )
        if row["exception_note"]:
            fail(f"{article}/{row['image_number']} has an exception note")
        if not row["orig_url"].endswith("/orig"):
            fail(f"{article}/{row['image_number']} does not point to /orig")
        if row["page_variant_url"].endswith("/orig"):
            fail(f"{article}/{row['image_number']} page variant is orig")
        for field in BASE_CLASSIFICATION_FIELDS:
            if not row[field].strip():
                fail(f"{article}/{row['image_number']} has empty {field}")
        graphic_kinds = parse_graphic_routing(
            row, f"{article}/{row['image_number']}"
        )
        if graphic_kinds:
            graphic_route_counts[row["graphic_kind"]] += 1
            graphic_kind_presence.update(graphic_kinds)

        relative_path = Path(row["file_path"])
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root):
            fail(f"unsafe file path: {relative_path}")
        if not path.is_file():
            fail(f"missing image: {relative_path}")
        expected_files.add(path)
        article_folders[article].add(path.parent.name)

        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != row["sha256"]:
            fail(f"sha256 mismatch: {relative_path}")
        if len(payload) != int(row["byte_size"]):
            fail(f"byte-size mismatch: {relative_path}")
        with Image.open(path) as image:
            actual_format = (image.format or "").upper()
            width, height = image.size
            image.verify()
        if actual_format != row["actual_format"]:
            fail(f"actual-format mismatch: {relative_path}")
        if (width, height) != (
            int(row["actual_width"]),
            int(row["actual_height"]),
        ):
            fail(f"actual-dimension mismatch: {relative_path}")
        if (width, height) != (int(row["orig_width"]), int(row["orig_height"])):
            fail(f"orig-dimension mismatch: {relative_path}")
        if actual_format != row["orig_format"]:
            fail(f"orig-format mismatch: {relative_path}")
        total_bytes += len(payload)

        classification = tuple(
            row[field] for field in MANIFEST_CLASSIFICATION_FIELDS
        )
        if row["image_id"] in class_by_id and class_by_id[row["image_id"]] != classification:
            fail(f"classification differs for duplicate id {row['image_id']}")
        class_by_id[row["image_id"]] = classification
        if row["image_id"] in seen_by_id:
            first = seen_by_id[row["image_id"]]
            if row["sha256"] != first["sha256"] or row["orig_url"] != first["orig_url"]:
                fail(f"duplicate id has different source or bytes: {row['image_id']}")
            if not row["duplicate_of"]:
                fail(f"duplicate id lacks duplicate_of: {row['image_id']}")
        else:
            if row["duplicate_of"]:
                fail(f"first occurrence unexpectedly marked duplicate: {row['image_id']}")
            seen_by_id[row["image_id"]] = row

    for article in expected_article_numbers:
        if len(article_urls[article]) != 1:
            fail(f"article {article} has {len(article_urls[article])} source URLs")
        if len(article_folders[article]) != 1:
            fail(f"article {article} has {len(article_folders[article])} folders")
        numbers = sorted(image_numbers[article])
        if numbers != list(range(1, len(numbers) + 1)):
            fail(f"article {article} image numbering is not contiguous: {numbers}")

    if not annotations_path.is_file():
        fail("classifications.json is missing")
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
    if not isinstance(annotations, dict):
        fail("classifications.json must be an object keyed by image_id")
    if set(annotations) != set(seen_by_id):
        fail(
            "classification coverage differs: "
            f"missing={sorted(set(seen_by_id) - set(annotations))}, "
            f"extra={sorted(set(annotations) - set(seen_by_id))}"
        )
    for image_id, row in seen_by_id.items():
        annotation = annotations[image_id]
        if not isinstance(annotation, dict):
            fail(f"annotation {image_id} must be an object")
        for field in BASE_CLASSIFICATION_FIELDS:
            value = annotation.get(field)
            if not isinstance(value, str) or not value:
                fail(f"annotation {image_id} has invalid {field}")
            if value != row[field]:
                fail(f"annotation {image_id} differs from manifest in {field}")
        active_kind, kinds = annotation_graphic_routing(image_id, annotation)
        if active_kind != row["graphic_kind"]:
            fail(f"annotation {image_id} differs from manifest in graphic_kind")
        if "; ".join(kinds) != row["graphic_kinds"]:
            fail(f"annotation {image_id} differs from manifest in graphic_kinds")

    folders = [path for path in articles_root.iterdir() if path.is_dir()]
    if len(folders) != EXPECTED_ARTICLE_COUNT:
        fail(
            f"expected {EXPECTED_ARTICLE_COUNT} article folders, "
            f"found {len(folders)}"
        )
    actual_image_files = {
        path.resolve() for folder in folders for path in folder.iterdir() if path.is_file()
    }
    if actual_image_files != expected_files:
        unexpected = sorted(str(path) for path in actual_image_files - expected_files)
        missing = sorted(str(path) for path in expected_files - actual_image_files)
        fail(f"folder contents differ; unexpected={unexpected}, missing={missing}")

    if not taxonomy_path.is_file():
        fail("taxonomy.md is missing")
    taxonomy = taxonomy_path.read_text(encoding="utf-8")
    classes = sorted({row["primary_class"] for row in rows})
    missing_taxonomy_classes = [name for name in classes if f"`{name}`" not in taxonomy]
    if missing_taxonomy_classes:
        fail(f"taxonomy lacks classes: {missing_taxonomy_classes}")
    missing_graphic_kinds = [
        kind for kind in GRAPHIC_KIND_VALUES if f"`{kind}`" not in taxonomy
    ]
    if missing_graphic_kinds:
        fail(f"taxonomy lacks graphic kinds: {missing_graphic_kinds}")

    unique_graphic_route_counts = Counter(
        row["graphic_kind"]
        for row in seen_by_id.values()
        if row["graphic_kind"]
    )
    unique_graphic_kind_presence = Counter(
        kind.strip()
        for row in seen_by_id.values()
        for kind in row["graphic_kinds"].split(";")
        if kind.strip()
    )

    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "article_count": len(article_numbers),
        "image_occurrence_count": len(rows),
        "unique_image_count": len(seen_by_id),
        "duplicate_occurrence_count": len(rows) - len(seen_by_id),
        "total_bytes_with_duplicates": total_bytes,
        "formats": dict(sorted(Counter(row["actual_format"] for row in rows).items())),
        "classes": dict(sorted(Counter(row["primary_class"] for row in rows).items())),
        "graphic_routes": {
            kind: {
                "unique": unique_graphic_route_counts[kind],
                "occurrences": graphic_route_counts[kind],
            }
            for kind in GRAPHIC_KIND_VALUES
        },
        "graphic_kind_presence": {
            kind: {
                "unique": unique_graphic_kind_presence[kind],
                "occurrences": graphic_kind_presence[kind],
            }
            for kind in GRAPHIC_KIND_VALUES
        },
        "images_per_article": dict(
            sorted(Counter(row["article_number"] for row in rows).items())
        ),
        "orig_exceptions": 0,
    }
    if args.write_report:
        report_path = articles_root / "verification-report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Verification report: {report_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
