#!/usr/bin/env python3
"""Merge image-id keyed scene annotations into the PROMOPAGES-9857 manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


CLASSIFICATION_FIELDS = (
    "primary_class",
    "scene_tags",
    "scene_description",
    "motion_cues",
    "risk_notes",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("annotations", type=Path)
    args = parser.parse_args()

    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    if not isinstance(annotations, dict):
        raise ValueError("annotations must be a JSON object keyed by image_id")

    with args.manifest.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    missing_columns = set(CLASSIFICATION_FIELDS) - set(fieldnames)
    if missing_columns:
        raise ValueError(f"manifest is missing columns: {sorted(missing_columns)}")

    manifest_ids = {row["image_id"] for row in rows}
    missing_annotations = manifest_ids - set(annotations)
    extra_annotations = set(annotations) - manifest_ids
    if missing_annotations or extra_annotations:
        raise ValueError(
            "annotation coverage mismatch: "
            f"missing={sorted(missing_annotations)}, extra={sorted(extra_annotations)}"
        )

    for image_id, annotation in annotations.items():
        if not isinstance(annotation, dict):
            raise ValueError(f"annotation for {image_id} must be an object")
        missing_fields = [
            field for field in CLASSIFICATION_FIELDS if not annotation.get(field)
        ]
        if missing_fields:
            raise ValueError(
                f"annotation for {image_id} has empty fields: {missing_fields}"
            )

    for row in rows:
        annotation = annotations[row["image_id"]]
        for field in CLASSIFICATION_FIELDS:
            row[field] = annotation[field]

    temporary = args.manifest.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(args.manifest)
    print(
        f"Applied {len(annotations)} unique annotations to {len(rows)} manifest rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
