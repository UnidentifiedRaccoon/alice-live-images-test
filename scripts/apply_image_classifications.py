#!/usr/bin/env python3
"""Merge image-id keyed scene annotations into the PROMOPAGES-9857 manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


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


def serialize_graphic_routing(
    image_id: str, annotation: dict[str, object]
) -> tuple[str, str]:
    primary_class = annotation.get("primary_class")
    active_kind = annotation.get("graphic_kind", "")
    kinds = annotation.get("graphic_kinds", [])

    if primary_class != GRAPHIC_PRIMARY_CLASS:
        if active_kind or kinds:
            raise ValueError(
                f"annotation for {image_id} has graphic routing outside "
                f"{GRAPHIC_PRIMARY_CLASS}"
            )
        return "", ""

    if not isinstance(active_kind, str) or not active_kind:
        raise ValueError(f"annotation for {image_id} has no active graphic_kind")
    if not isinstance(kinds, list) or not kinds:
        raise ValueError(f"annotation for {image_id} has no graphic_kinds")
    if any(not isinstance(kind, str) or not kind for kind in kinds):
        raise ValueError(f"annotation for {image_id} has invalid graphic_kinds")
    if len(kinds) != len(set(kinds)):
        raise ValueError(f"annotation for {image_id} has duplicate graphic_kinds")
    unknown = [kind for kind in kinds if kind not in GRAPHIC_KIND_VALUES]
    if unknown:
        raise ValueError(
            f"annotation for {image_id} has unknown graphic_kinds: {unknown}"
        )
    if active_kind not in GRAPHIC_KIND_VALUES:
        raise ValueError(
            f"annotation for {image_id} has unknown graphic_kind: {active_kind}"
        )
    if kinds[0] != active_kind:
        raise ValueError(
            f"annotation for {image_id} must place active graphic_kind first"
        )
    return active_kind, "; ".join(kinds)


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

    missing_columns = set(MANIFEST_CLASSIFICATION_FIELDS) - set(fieldnames)
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
        invalid_fields = [
            field
            for field in BASE_CLASSIFICATION_FIELDS
            if not isinstance(annotation.get(field), str) or not annotation[field]
        ]
        if invalid_fields:
            raise ValueError(
                f"annotation for {image_id} has invalid fields: {invalid_fields}"
            )
        serialize_graphic_routing(image_id, annotation)

    for row in rows:
        annotation = annotations[row["image_id"]]
        graphic_kind, graphic_kinds = serialize_graphic_routing(
            row["image_id"], annotation
        )
        row["graphic_kind"] = graphic_kind
        row["graphic_kinds"] = graphic_kinds
        for field in BASE_CLASSIFICATION_FIELDS:
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
