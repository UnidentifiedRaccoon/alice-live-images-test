#!/usr/bin/env python3
"""Focused tests for the immutable Femibion V1..V7 final selection."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from scripts import (
    clipmaker_lite_promopages_10060_femibion_all_attempts_selection as selection,
)


ROOT = Path(__file__).resolve().parents[1]


class AllAttemptsSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = selection.validate_selection(ROOT)

    def test_reconstructs_byte_for_value_from_immutable_evidence(self) -> None:
        actual = self.document
        expected = selection.selection_document(
            ROOT,
            updated_at=actual["updated_at"],
        )
        self.assertEqual(actual, expected)
        self.assertTrue(actual["ready_for_merge"])
        self.assertEqual(actual["accepted_output_count"], 2)
        self.assertEqual(
            actual["summary"],
            {"succeeded": 2, "provider-filtered": 0},
        )

    def test_accounting_pins_all_eight_paid_recovery_attempts(self) -> None:
        accounting = self.document["accounting"]
        self.assertEqual(len(self.document["attempt_evidence"]), 8)
        self.assertEqual(accounting["baseline_paid_submissions"], 281)
        self.assertEqual(accounting["recovery_paid_submissions"], 8)
        self.assertEqual(accounting["aggregate_paid_submissions"], 289)
        self.assertEqual(accounting["aggregate_reserved_usd"], 101.15)
        self.assertEqual(accounting["hard_budget_cap_usd"], 104.75)
        self.assertEqual(accounting["hard_cap_headroom_usd"], 3.6)
        self.assertEqual(
            accounting["recovery_submissions_by_iteration"],
            {"v1": 2, "v2": 1, "v3": 1, "v4": 1, "v5": 1, "v6": 1, "v7": 1},
        )

    def test_exact_route_and_current_lite_provenance_are_pinned(self) -> None:
        route = self.document["route"]
        self.assertEqual(route["model_id"], selection.MODEL_ID)
        self.assertEqual(route["adapter"], "eliza-openrouter")
        self.assertEqual(route["transport"], "eliza-video-jobs")
        self.assertEqual(route["provider_key"], "google-vertex")
        self.assertEqual(route["capacity"], 3)
        self.assertFalse(route["automatic_fallback"])
        self.assertFalse(route["normal_run_discovery"])
        self.assertEqual(self.document["contract"]["contract_version"], "2.0.8")
        for attempt in self.document["attempt_evidence"]:
            provenance = attempt["planning"]["provenance"]
            self.assertTrue(provenance["verified"])
            self.assertEqual(provenance["agent_id"], selection.AGENT_ID)
            self.assertEqual(provenance["contract_version"], "2.0.8")
            self.assertEqual(provenance["models"], [selection.MODEL_ID])
            self.assertEqual(
                provenance["source_image_sha256"],
                attempt["source"]["sha256"],
            )

    def test_selects_composite_07_and_raw_v1_08_as_regular_mp4s(self) -> None:
        outputs = {
            (output["article_slug"], output["image_id"]): output
            for output in self.document["outputs"]
        }
        selected_07 = outputs[(selection.ARTICLE_07, "06")]
        self.assertEqual(selected_07["provider_job_id"], "c4pO6Fw8YaEz0vPon3wH")
        self.assertEqual(
            selected_07["selected_attempt"],
            "content-filter-recovery-v7-composite",
        )
        self.assertEqual(selected_07["video_path"], selection.COMPOSITE_VIDEO_REL.as_posix())
        self.assertEqual(selected_07["media"]["sha256"], selection.COMPOSITE_VIDEO_SHA256)
        self.assertEqual(selected_07["media"]["bytes"], selection.COMPOSITE_VIDEO_BYTES)
        self.assertEqual(
            selected_07["recovery"]["composite_receipt"]["sha256"],
            selection.COMPOSITE_RECEIPT_SHA256,
        )

        selected_08 = outputs[(selection.ARTICLE_08, "05")]
        self.assertEqual(selected_08["provider_job_id"], "8FDZycf6v5wTtzPmNYwF")
        self.assertEqual(selected_08["selected_attempt"], "content-filter-recovery-v1")
        self.assertEqual(
            selected_08["media"]["sha256"],
            "be2a072ffe4fe3934563e148956c3d05bcb6123e8a878829b18d9adead5af153",
        )
        self.assertEqual(selected_08["media"]["bytes"], 2_979_506)
        for output in outputs.values():
            path = ROOT / output["video_path"]
            self.assertTrue(path.is_file())
            self.assertFalse(path.is_symlink())
            self.assertTrue(output["contract_check"]["conforms"])

    def test_preserves_original_retry_and_recovery_failure_chain(self) -> None:
        failed = self.document["failed_attempt_chain"]
        self.assertEqual(len(failed), 10)
        self.assertEqual(
            [record["provider_job_id"] for record in failed],
            [
                "Hfvx2OaGO9vsyrcs6AMf",
                "dqjE7PrI5frFAFW7Y2Aa",
                "6QIWOmo7PJgVMK4qECeg",
                "tpePxKfkVlYvoc1nVeS0",
                "SwdH1eVdnIzgLHeXaTIg",
                "axgyuIecP85mwRLo7d13",
                "5UTHzBnYIH5XkaGt7kJj",
                "ph4kAnk1VL2vETZwBiSo",
                "c2wwhmzoBtXaxBRuDKl3",
                "rxIfCOzWeIJTt0yhb7wB",
            ],
        )
        self.assertTrue(all(record["status"] == "provider-filtered" for record in failed))

    def test_v5_dimension_receipt_discrepancy_is_explicit_and_verified(self) -> None:
        v5 = next(
            record
            for record in self.document["attempt_evidence"]
            if record["iteration"] == 5
        )
        source = v5["source"]
        self.assertEqual(source["recorded_dimensions"], {"width": 1920, "height": 1080})
        self.assertEqual(
            source["actual_local_dimensions"],
            {"format": "JPEG", "width": 2400, "height": 1600},
        )
        self.assertTrue(source["receipt_metadata_discrepancy"])
        self.assertEqual(
            source["sha256"],
            "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12",
        )
        transformations = self.document["source_transformations"]
        self.assertEqual(len(transformations["attempt_sources"]), 8)
        self.assertEqual(
            transformations["receipt_metadata_discrepancies"],
            [{"iteration": 5, "logical_key": v5["logical_key"], "source": source}],
        )

    def test_tampered_composite_receipt_digest_fails_closed(self) -> None:
        real_sha256 = selection.sha256_file

        def changed(path: Path) -> str:
            if path == ROOT / selection.COMPOSITE_RECEIPT_REL:
                return "0" * 64
            return real_sha256(path)

        with mock.patch.object(selection, "sha256_file", side_effect=changed):
            with self.assertRaisesRegex(
                selection.SelectionError,
                "Immutable evidence digest changed",
            ):
                selection.validate_selection(ROOT)


if __name__ == "__main__":
    unittest.main()
