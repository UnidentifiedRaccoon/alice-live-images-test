#!/usr/bin/env python3
"""Acceptance specification for the final Femibion two-key overlay."""

from __future__ import annotations

import unittest

from scripts import clipmaker_lite_promopages_10060_pipeline as pipeline


class FemibionFinalSelectionOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)
        cls.discovery = pipeline.discover(pipeline.ROOT)
        cls.inventory = pipeline.inventory_document(
            cls.discovery,
            pipeline.HARD_BUDGET_CAP_USD,
            pipeline.ROOT,
        )
        cls.document = pipeline.build_final_manifest(
            cls.discovery,
            cls.inventory,
            root=pipeline.ROOT,
            updated_at="2026-08-10T20:00:00Z",
            allow_contract_warnings=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    def test_replaces_exactly_two_keys_and_keeps_flat_nested_identical(self) -> None:
        outputs = {
            (output["article_slug"], output["image_id"], output["model_id"]): output
            for output in self.document["outputs"]
        }
        expected_keys = set(pipeline.FEMIBION_VEO_RECOVERY_KEYS)
        self.assertTrue(expected_keys <= set(outputs))
        for key in expected_keys:
            selected = outputs[key]
            self.assertEqual(selected["status"], "succeeded")
            self.assertTrue(selected["contract_check"]["conforms"])
            self.assertIn("retry", selected)
            self.assertTrue(selected["retry"]["exhausted"])
            self.assertEqual(
                selected["recovery"]["old_provider_filtered"]["status"],
                "provider-filtered",
            )
        nested = {}
        for article in self.document["articles"]:
            for image in article["images"]:
                for output in image["outputs"]:
                    nested[
                        (
                            output["article_slug"],
                            output["image_id"],
                            output["model_id"],
                        )
                    ] = output
        self.assertEqual(nested, outputs)

    def test_selects_final_composite_and_v1_raw_mp4(self) -> None:
        outputs = {
            (output["article_slug"], output["image_id"]): output
            for output in self.document["outputs"]
            if output["model_id"] == pipeline.FEMIBION_VEO_RECOVERY_MODEL_ID
        }
        selected_07 = outputs[("07-femibion-gotovites-k-beremennosti", "06")]
        self.assertEqual(selected_07["provider_job_id"], "c4pO6Fw8YaEz0vPon3wH")
        self.assertEqual(
            selected_07["media"]["sha256"],
            "d058fe8556e2f3badaa436745b1aa6e30ff0e726ef1648134225508e5917e13c",
        )
        self.assertEqual(selected_07["media"]["bytes"], 552_368)
        self.assertIn("/composite/videos/", selected_07["video_path"])
        selected_08 = outputs[("08-femibion-grudnoe-vskarmlivanie", "05")]
        self.assertEqual(selected_08["provider_job_id"], "8FDZycf6v5wTtzPmNYwF")
        self.assertEqual(
            selected_08["media"]["sha256"],
            "be2a072ffe4fe3934563e148956c3d05bcb6123e8a878829b18d9adead5af153",
        )
        self.assertEqual(selected_08["media"]["bytes"], 2_979_506)

    def test_recomputes_status_acceptance_and_authorized_accounting(self) -> None:
        self.assertEqual(self.document["status_summary"]["provider-filtered"], 0)
        self.assertEqual(self.document["accepted_output_count"], 276)
        self.assertEqual(self.document["terminal_accounted_output_count"], 276)
        cost = self.document["cost"]
        self.assertEqual(cost["maximum_paid_submissions"], 289)
        self.assertEqual(cost["maximum_estimated_cost_usd"], 101.15)
        self.assertEqual(cost["estimated_headroom_usd"], 3.6)
        self.assertEqual(cost["content_filter_recovery_reservations"], 8)
        provenance = self.document["recovery_provenance"]
        self.assertEqual(
            provenance["selection_id"],
            pipeline.FEMIBION_VEO_FINAL_SELECTION_ID,
        )
        self.assertEqual(provenance["attempt_evidence_count"], 8)
        self.assertEqual(provenance["failed_attempt_count"], 10)

    def test_exact_rebuild_and_final_validation_are_clean(self) -> None:
        rebuilt = pipeline.build_final_manifest(
            self.discovery,
            self.inventory,
            root=pipeline.ROOT,
            updated_at=self.document["updated_at"],
            allow_contract_warnings=True,
        )
        self.assertEqual(rebuilt, self.document)
        self.assertEqual(
            pipeline.final_manifest_errors(
                self.document,
                discovery=self.discovery,
                root=pipeline.ROOT,
                allow_contract_warnings=True,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
