from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v5_retry_planning as retry


class TuneV5RetryPlanningTests(unittest.TestCase):
    def test_selection_repairs_only_07_and_reuses_verified_r6_10(self) -> None:
        document = retry.build_selection_document(root=retry.ROOT)
        self.assertEqual([case["case_id"] for case in document["cases"]], ["07#06", "10#07"])
        by_id = {case["case_id"]: case for case in document["cases"]}
        self.assertTrue(by_id["07#06"]["run_id"].startswith(retry.BATCH_ID + "-"))
        self.assertTrue(by_id["10#07"]["run_id"].startswith(retry.PREVIOUS_BATCH_ID + "-"))
        self.assertEqual(document["summary"]["new_repair_case_count"], 1)
        self.assertEqual(document["summary"]["reused_previous_case_count"], 1)
        self.assertFalse(document["policy"]["fallback"])
        self.assertFalse(document["policy"]["s3_upload"])

    def test_07_feedback_and_gate_require_numeric_cap_in_positive_prompt(self) -> None:
        feedback = retry._feedback("07#06")  # noqa: SLF001
        phrase = "within a 5% screen-travel cap"
        self.assertEqual(feedback["camera_repair"]["max_screen_travel_percent"], 5)
        self.assertIn(phrase, feedback["review_note"])
        case = {"case_id": "07#06"}
        result = {
            "analysis": {"structured_intent": {"rendering_strategy": "camera-only"}},
            "models": [
                {
                    "model_id": retry.MODEL_ID,
                    "execution_mode": "i2v",
                    "scene_plan": "The camera makes one centered push-in capped at 5%.",
                    "positive_prompt": "The camera makes one centered push-in.",
                    "negative_prompt": None,
                }
            ],
        }
        with self.assertRaisesRegex(retry.TuneV5RetryPlanningError, "numeric 5%"):
            retry.validate_neutral_result(result, case)
        result["models"][0]["positive_prompt"] = (
            "The camera makes one centered push-in within a 5% screen-travel cap."
        )
        self.assertEqual(retry.validate_neutral_result(result, case)["model_id"], retry.MODEL_ID)

    def test_10_feedback_uses_neutral_count_and_tight_cap(self) -> None:
        feedback = retry._feedback("10#07")  # noqa: SLF001
        encoded = json.dumps(feedback, ensure_ascii=False).lower()
        self.assertIn("exactly four visible people", encoded)
        self.assertNotIn("children", encoded)
        self.assertNotIn("family", encoded)
        self.assertEqual(feedback["camera_repair"]["max_screen_travel_percent"], 3)

    def test_prepare_is_local_and_does_not_run_agent(self) -> None:
        selection = retry.load_selection(root=retry.ROOT)
        case = next(case for case in selection["cases"] if case["case_id"] == "07#06")
        with mock.patch.object(retry.runner, "run_agent") as run_agent:
            status = retry.prepare_case(case, root=retry.ROOT)
        self.assertIn(status, {"prepared", "already-prepared"})
        run_agent.assert_not_called()

    def test_atomic_create_rejects_changed_immutable_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value.json"
            retry.atomic_create_json(path, {"value": 1})
            retry.atomic_create_json(path, {"value": 1})
            with self.assertRaisesRegex(retry.TuneV5RetryPlanningError, "already differs"):
                retry.atomic_create_json(path, {"value": 2})


if __name__ == "__main__":
    unittest.main()
