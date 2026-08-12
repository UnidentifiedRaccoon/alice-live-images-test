from __future__ import annotations

import copy
import unittest
from unittest import mock

from scripts import clipmaker_lite_tune_v7_filter_retry_planning as planning


class TuneV7FilterRetryPlanningTests(unittest.TestCase):
    def test_selection_is_one_canonical_source_target_with_typed_diagnosis(self) -> None:
        document = planning.build_selection_document(root=planning.ROOT)
        self.assertEqual(document["summary"]["target_count"], 1)
        self.assertEqual(document["cases"][0]["case_id"], planning.CASE_ID)
        self.assertEqual(
            document["cases"][0]["source"]["sha256"],
            planning.CANONICAL_SOURCE_SHA256,
        )
        self.assertIsNone(document["policy"]["source_transform"])
        self.assertFalse(document["policy"]["disable_provider_safety_filters"])
        self.assertFalse(document["policy"]["fallback"])
        self.assertFalse(document["policy"]["compositor"])
        self.assertTrue(document["policy"]["one_new_paid_attempt_only"])
        diagnosis = document["diagnosis"]
        self.assertEqual(diagnosis["type"], "suspected_source_filter")
        self.assertGreaterEqual(
            diagnosis["person_preserving_provider_failures_at_least"], 11
        )
        self.assertEqual(diagnosis["observed_failed_seeds"], [9681, 27183])
        self.assertFalse(diagnosis["provider_support_code_available"])
        self.assertFalse(diagnosis["prior_provider_response_present"])

    def test_repair_feedback_requires_exact_neutral_provider_prompt(self) -> None:
        feedback = planning.repair_feedback()[planning.MODEL_ID]
        serialized = str(feedback).lower()
        self.assertIn(planning.EXACT_POSITIVE_PROMPT.lower(), serialized)
        self.assertEqual(feedback["fallback_policy"], "none")
        self.assertEqual(feedback["camera_repair"]["max_screen_travel_percent"], 5)

    def test_result_gate_rejects_semantically_expanded_prompt(self) -> None:
        result = {
            "analysis": {"structured_intent": {"rendering_strategy": "camera-only"}},
            "models": [
                {
                    "model_id": planning.MODEL_ID,
                    "execution_mode": "i2v",
                    "positive_prompt": planning.EXACT_POSITIVE_PROMPT + " Extra detail.",
                    "negative_prompt": None,
                    "runtime": {
                        "duration_seconds": 4,
                        "resolution": "1080p",
                        "generate_audio": False,
                        "provider": "google-vertex",
                        "prompt_expansion": {
                            "parameter": "enhancePrompt",
                            "value": True,
                        },
                    },
                }
            ],
        }
        with self.assertRaisesRegex(planning.TuneV7FilterPlanningError, "exact neutral"):
            planning.validate_result(result, {"case_id": planning.CASE_ID})

    def test_result_gate_accepts_exact_prompt_and_route_runtime(self) -> None:
        result = {
            "analysis": {"structured_intent": {"rendering_strategy": "camera-only"}},
            "models": [
                {
                    "model_id": planning.MODEL_ID,
                    "execution_mode": "i2v",
                    "positive_prompt": planning.EXACT_POSITIVE_PROMPT,
                    "negative_prompt": None,
                    "runtime": {
                        "duration_seconds": 4,
                        "resolution": "1080p",
                        "generate_audio": False,
                        "provider": "google-vertex",
                        "prompt_expansion": {
                            "parameter": "enhancePrompt",
                            "value": True,
                        },
                    },
                }
            ],
        }
        self.assertEqual(
            planning.validate_result(result, {"case_id": planning.CASE_ID})[
                "positive_prompt"
            ],
            planning.EXACT_POSITIVE_PROMPT,
        )

    def test_prepare_uses_runner_and_canonical_source(self) -> None:
        case = planning.build_selection_document(root=planning.ROOT)["cases"][0]
        with mock.patch("pathlib.Path.exists", return_value=False), mock.patch.object(
            planning.runner, "prepare_run"
        ) as prepare:
            self.assertEqual(planning.prepare_case(copy.deepcopy(case)), "prepared")
        prepare.assert_called_once()
        args = prepare.call_args.args
        self.assertEqual(args[2], case["source"]["path"])


if __name__ == "__main__":
    unittest.main()
