#!/usr/bin/env python3
"""Network-free tests for the two-image Clipmaker Lite coordinator."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_promopages_live_images_pipeline as pipeline


class LiveImagesPipelineTest(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def make_fixture(self, directory: str) -> tuple[Path, tuple[pipeline.Source, ...]]:
        root = Path(directory) / "workspace"
        root.mkdir(parents=True)
        repository = Path(pipeline.__file__).resolve().parents[1]
        for relative in (pipeline.CONTRACT_REL, pipeline.ROUTES_REL):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repository / relative, target)
        self.write_json(
            root / pipeline.ARTICLE_CONFIG_REL,
            [
                {
                    "number": int(spec.number),
                    "label": f"{spec.brand} — {spec.title}",
                    "folder": spec.slug,
                    "url": spec.url,
                }
                for spec in pipeline.ARTICLE_SPECS
            ],
        )

        rows: list[dict[str, object]] = []
        for spec in pipeline.ARTICLE_SPECS:
            if spec.number == "01":
                images = [
                    ("01", "cover", "1" * 24, "01.png", 1516, 845, ""),
                    ("02", "article_image", "2" * 24, "02.jpeg", 1280, 753, "graph one"),
                    ("03", "article_image", "3" * 24, "03.png", 1460, 954, "graph two"),
                    (
                        spec.selected_image_id,
                        "article_image",
                        spec.selected_media_id,
                        "04.jpeg",
                        spec.width,
                        spec.height,
                        "Level selected caption",
                    ),
                ]
            else:
                images = [
                    (
                        spec.selected_image_id,
                        "article_image",
                        spec.selected_media_id,
                        "01.jpeg",
                        spec.width,
                        spec.height,
                        "",
                    )
                ]
            blocks = []
            for index, (image_number, role, media_id, filename, width, height, caption) in enumerate(images):
                manifest_path = f"{pipeline.DATASET_PREFIX}/articles/{spec.slug}/{filename}"
                payload = f"{spec.slug}-{filename}".encode("utf-8")
                local = root / "PROMOPAGES-9857" / manifest_path
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(payload)
                sha256 = hashlib.sha256(payload).hexdigest()
                orig_url = (
                    spec.source_url
                    if image_number == spec.selected_image_id
                    else f"https://avatars.example/{media_id}/orig"
                )
                rows.append(
                    {
                        "article_number": spec.number,
                        "article_url": spec.url,
                        "image_number": image_number,
                        "image_role": role,
                        "image_id": media_id,
                        "orig_url": orig_url,
                        "file_path": manifest_path,
                        "actual_width": width,
                        "actual_height": height,
                        "sha256": sha256,
                        "download_status": "ok",
                    }
                )
                blocks.append(
                    {
                        "type": "image",
                        "image_id": image_number,
                        "file": filename,
                        "manifest_file_path": manifest_path,
                        "role": role,
                        "source_image_id": media_id,
                        "source_block_index": None if role == "cover" else index,
                        "gallery_index": None,
                        "caption": caption,
                        "duplicate_of": None,
                    }
                )
            self.write_json(
                root / pipeline.SOURCE_CONTEXT_ROOT_REL / spec.slug / "content.json",
                {
                    "schema_version": 1,
                    "article_number": spec.number,
                    "url": spec.url,
                    "publication_id": spec.publication_id,
                    "title": spec.title,
                    "lead": "fixture",
                    "blocks": blocks,
                },
            )
        manifest = root / pipeline.SOURCE_MANIFEST_REL
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return root, pipeline.discover(root)

    def write_operator_policy(self, root: Path) -> None:
        repository = Path(pipeline.__file__).resolve().parents[1]
        source = repository / pipeline.OPERATOR_ACCEPTANCE_REL
        target = root / pipeline.OPERATOR_ACCEPTANCE_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def test_discovery_selects_only_body_photo_and_coverless_banki_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, sources = self.make_fixture(directory)
            self.assertEqual(
                [(source.spec.number, source.spec.selected_image_id) for source in sources],
                [("01", "04"), ("02", "01")],
            )
            self.assertEqual(sources[0].caption, "Level selected caption")
            self.assertEqual(sources[1].caption, "")
            self.assertTrue(sources[1].source_path.endswith("/01.jpeg"))

    def test_inventory_locks_contract_routes_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, sources = self.make_fixture(directory)
            document = pipeline.inventory_document(sources, root)
            self.assertEqual(document["contract"]["contract_version"], "2.1.4")
            self.assertEqual(document["contract"]["runner_version"], 8)
            self.assertEqual(document["generation_routes"]["models"], {
                model: {
                    "adapter": pipeline.ROUTE_TRANSPORTS[model][0],
                    "transport": pipeline.ROUTE_TRANSPORTS[model][1],
                    "capacity": pipeline.ROUTE_CAPACITIES[model],
                }
                for model in pipeline.MODEL_IDS
            })
            self.assertEqual(document["cost"]["primary_reservations"], 6)
            self.assertEqual(document["cost"]["maximum_new_prompt_attempts"], 8)
            self.assertEqual(document["cost"]["maximum_estimated_cost_usd"], 4.9)
            pipeline.write_inventory(sources, root)
            self.assertEqual(pipeline.require_inventory(sources, root), document)

    def test_retry_reservations_are_fresh_idempotent_and_capped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, sources = self.make_fixture(directory)
            pipeline.write_inventory(sources, root)
            primary_id = pipeline._primary_provider_run_id(
                sources[0], "google/veo-3.1-lite"
            )
            first = pipeline.reserve_retry(sources, primary_id, "Reduce camera motion", root)
            duplicate = pipeline.reserve_retry(sources, primary_id, "Reduce camera motion", root)
            self.assertEqual(first, duplicate)
            self.assertEqual(first["attempt_id"], "retry-01")
            self.assertNotEqual(first["provider_batch_id"], pipeline.BATCH_ID)
            self.assertNotEqual(first["planning_run_id"], sources[0].planning_run_id)
            for index in range(2, 9):
                pipeline.reserve_retry(sources, primary_id, f"Direction {index}", root)
            registry = pipeline.load_attempt_registry(root)
            self.assertEqual(registry["cost"]["retry_reservations"], 8)
            self.assertEqual(registry["cost"]["total_reservations"], 14)
            self.assertEqual(registry["cost"]["estimated_reserved_cost_usd"], 4.9)
            with self.assertRaisesRegex(pipeline.PipelineError, "eight"):
                pipeline.reserve_retry(sources, primary_id, "Ninth direction", root)

    def test_native_configuration_has_exact_primary_and_retry_matrices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, sources = self.make_fixture(directory)
            pipeline.write_inventory(sources, root)
            pipeline.configure_native(sources, root)
            self.assertEqual(len(pipeline.native.matrix()), 6)
            self.assertEqual(tuple(pipeline.native.MODEL_IDS), pipeline.MODEL_IDS)
            primary_id = pipeline._primary_provider_run_id(
                sources[1], "alibaba/wan-2.2"
            )
            attempt = pipeline.reserve_retry(sources, primary_id, "Keep text rigid", root)
            pipeline.configure_native(sources, root, attempt)
            matrix = pipeline.native.matrix()
            self.assertEqual(len(matrix), 1)
            self.assertEqual(matrix[0].model_id, "alibaba/wan-2.2")
            self.assertEqual(matrix[0].provider_run_id, attempt["provider_run_id"])
            self.assertEqual(matrix[0].planning_run_id, attempt["planning_run_id"])
            self.assertIsNone(pipeline.native.WAN_SUBMIT_MODE)

    def test_final_selection_uses_explicit_retry_only_for_its_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, sources = self.make_fixture(directory)
            pipeline.write_inventory(sources, root)
            primary_id = pipeline._primary_provider_run_id(
                sources[0], "alibaba/wan-2.7"
            )
            attempt = pipeline.reserve_retry(sources, primary_id, "Preserve facade", root)

            def fake_artifacts(_sources, _root, selected):
                rows = []
                if selected is None:
                    for source in sources:
                        for model_id in pipeline.MODEL_IDS:
                            rows.append(
                                {
                                    "attempt_id": "primary",
                                    "article_slug": source.spec.slug,
                                    "image_id": source.spec.selected_image_id,
                                    "model_id": model_id,
                                    "provider_run_id": pipeline._primary_provider_run_id(source, model_id),
                                    "status": "succeeded",
                                    "recorded_status": "succeeded",
                                    "accepted": True,
                                    "prompt": {"positive": "primary", "negative": None},
                                    "video_path": "primary.mp4",
                                    "media": {"bytes": 1, "sha256": "a" * 64},
                                    "contract_check": {"conforms": True},
                                    "media_acceptance": {
                                        "accepted": True,
                                        "mode": "strict-contract",
                                    },
                                    "error": None,
                                }
                            )
                    return rows
                logical = selected["logical_output"]
                return [
                    {
                        "attempt_id": selected["attempt_id"],
                        "article_slug": logical["article_slug"],
                        "image_id": logical["image_id"],
                        "model_id": logical["model_id"],
                        "provider_run_id": selected["provider_run_id"],
                        "status": "succeeded",
                        "recorded_status": "succeeded",
                        "accepted": True,
                        "prompt": {"positive": "retry", "negative": None},
                        "video_path": "retry.mp4",
                        "media": {"bytes": 1, "sha256": "b" * 64},
                        "contract_check": {"conforms": True},
                        "media_acceptance": {
                            "accepted": True,
                            "mode": "strict-contract",
                        },
                        "error": None,
                    }
                ]

            with mock.patch.object(pipeline, "_attempt_artifacts", side_effect=fake_artifacts):
                final = pipeline.build_final_selection(
                    sources, root=root, selected_attempt_ids=[attempt["attempt_id"]]
                )
            selected = [
                output
                for output in final["outputs"]
                if output["article_slug"] == sources[0].spec.slug
                and output["model_id"] == "alibaba/wan-2.7"
            ][0]
            self.assertEqual(selected["selected_attempt_id"], "retry-01")
            self.assertEqual(selected["selected_prompt"]["positive"], "retry")
            self.assertEqual(selected["recorded_status"], "succeeded")
            self.assertEqual(selected["media_acceptance"]["mode"], "strict-contract")
            self.assertEqual(selected["attempts"][0]["recorded_status"], "succeeded")
            self.assertEqual(sum(row["selected_attempt_id"] == "primary" for row in final["outputs"]), 5)

    def test_operator_acceptance_is_exact_to_level_retry_media_and_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _sources = self.make_fixture(directory)
            self.write_operator_policy(root)
            document, policy_sha = pipeline.load_operator_acceptance(root)
            decision = document["decisions"][0]
            row = {
                **decision["scope"],
                **decision["selected_attempt"],
                "recorded_status": decision["expected_recorded_status"],
            }
            acceptance = pipeline.operator_media_acceptance(
                root, row, decision["expected_media"], decision["expected_contract_check"]
            )
            self.assertEqual(acceptance["mode"], "operator-exception")
            self.assertEqual(acceptance["policy_sha256"], policy_sha)
            for field, changed in (
                ("attempt_id", "primary"),
                ("provider_run_id", "changed"),
                ("publication_id", "0" * 24),
            ):
                with self.subTest(field=field):
                    bad = dict(row)
                    bad[field] = changed
                    self.assertIsNone(
                        pipeline.operator_media_acceptance(
                            root, bad, decision["expected_media"], decision["expected_contract_check"]
                        )
                    )
            bad_media = dict(decision["expected_media"])
            bad_media["width"] = 1920
            self.assertIsNone(
                pipeline.operator_media_acceptance(
                    root, row, bad_media, decision["expected_contract_check"]
                )
            )


if __name__ == "__main__":
    unittest.main()
