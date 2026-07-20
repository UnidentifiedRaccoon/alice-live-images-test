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


CLASSIFICATION_FIELDS = (
    "primary_class",
    "scene_tags",
    "scene_description",
    "motion_cues",
    "risk_notes",
)


def fail(message: str) -> None:
    raise AssertionError(message)


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
    with manifest_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        fail("manifest has no rows")

    article_numbers = sorted({row["article_number"] for row in rows})
    expected_article_numbers = [f"{number:02d}" for number in range(1, 15)]
    if article_numbers != expected_article_numbers:
        fail(f"article numbers differ: {article_numbers}")

    article_urls: dict[str, set[str]] = defaultdict(set)
    article_folders: dict[str, set[str]] = defaultdict(set)
    image_numbers: dict[str, list[int]] = defaultdict(list)
    expected_files: set[Path] = set()
    seen_by_id: dict[str, dict[str, str]] = {}
    class_by_id: dict[str, tuple[str, ...]] = {}
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
        for field in CLASSIFICATION_FIELDS:
            if not row[field].strip():
                fail(f"{article}/{row['image_number']} has empty {field}")

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

        classification = tuple(row[field] for field in CLASSIFICATION_FIELDS)
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

    folders = [path for path in articles_root.iterdir() if path.is_dir()]
    if len(folders) != 14:
        fail(f"expected 14 article folders, found {len(folders)}")
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
