#!/usr/bin/env python3
"""Contract and publication checks for the PROMOPAGES-10060 Tune batch."""

from __future__ import annotations

import collections
import inspect
import json
import unittest
from pathlib import Path

from scripts import clipmaker_lite_tune_pipeline as tune


ROOT = Path(__file__).resolve().parents[1]


class ClipmakerLiteTunePipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evaluation = tune.load_evaluation(ROOT)
        cls.cases = tune.resolved_cases(cls.evaluation, ROOT)
        cls.manifest = json.loads(
            (ROOT / tune.OUTPUT_MANIFEST_PATH).read_text(encoding="utf-8")
        )

    def test_evaluation_encodes_exact_sheet_scope(self) -> None:
        cases = self.evaluation["cases"]
        targets = [target for case in cases for target in case["targets"]]
        self.assertEqual(len(cases), 36)
        self.assertEqual(len(targets), 65)
        self.assertEqual(
            collections.Counter(target["rating_state"] for target in targets),
            {"regenerate": 38, "blank": 27},
        )
        self.assertEqual(sum(bool(target.get("comment")) for target in targets), 62)
        self.assertEqual(
            collections.Counter(
                target["primary_failure_category"] for target in targets
            ),
            {
                "wrong_action_or_physics": 25,
                "source_identity_graphic_continuity": 20,
                "camera_shot_tempo": 7,
                "insufficient_motion": 6,
                "optical_accent": 4,
                "no_feedback": 3,
            },
        )

    def test_resolved_batch_is_prompt_only_and_uses_existing_video_evidence(self) -> None:
        self.assertEqual(len(self.cases), 36)
        self.assertEqual(
            sum(len(case["target_models"]) for case in self.cases),
            65,
        )
        for case in self.cases:
            self.assertTrue(case["run_id"].startswith(f"{tune.BATCH_ID}-"))
            for baseline in case["baseline_by_model"].values():
                self.assertTrue(baseline["video_url"].startswith("https://yastatic.net/"))
        source = inspect.getsource(tune)
        self.assertNotIn("clipmaker_lite_batch_pipeline", source)
        self.assertNotIn("boto3", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("subprocess.", source)

    def test_published_manifest_is_complete_and_fail_closed(self) -> None:
        manifest = self.manifest
        self.assertEqual(manifest["batch_id"], tune.BATCH_ID)
        self.assertEqual(manifest["contract_version"], tune.EXPECTED_CONTRACT_VERSION)
        self.assertEqual(manifest["scope"]["case_count"], 36)
        self.assertEqual(manifest["scope"]["target_count"], 65)
        self.assertFalse(manifest["scope"]["new_video_generation"])
        self.assertFalse(manifest["scope"]["new_s3_upload"])
        targets = [target for case in manifest["cases"] for target in case["targets"]]
        self.assertEqual(len(targets), 65)
        self.assertEqual(
            collections.Counter(
                target["tuned"]["execution_mode"] for target in targets
            ),
            {"i2v": 43, "deterministic-compositor": 22},
        )
        for case in manifest["cases"]:
            self.assertTrue(case["planning"]["provenance"]["verified"])
            strategy = case["planning"]["structured_intent"]["rendering_strategy"]
            expected_mode = (
                "deterministic-compositor"
                if strategy == "deterministic-compositor"
                else "i2v"
            )
            for target in case["targets"]:
                tuned = target["tuned"]
                self.assertEqual(tuned["execution_mode"], expected_mode)
                self.assertIsNone(tuned["negative_prompt"])
                if expected_mode == "deterministic-compositor":
                    self.assertIsNone(tuned["positive_prompt"])
                else:
                    self.assertIsInstance(tuned["positive_prompt"], str)
                    self.assertTrue(tuned["positive_prompt"].strip())

    def test_all_results_reverify_through_the_lite_runner(self) -> None:
        for case in self.cases:
            self.assertTrue(
                tune.result_is_verified(case, ROOT),
                msg=case["run_id"],
            )


if __name__ == "__main__":
    unittest.main()
