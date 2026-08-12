from __future__ import annotations

import copy
import unittest
from unittest import mock

from scripts import clipmaker_lite_tune_v8_veo_prompt_experiment_planning as planning


class TuneV8VeoPromptExperimentPlanningTests(unittest.TestCase):
    def test_selection_is_three_controlled_canonical_source_experiments(self) -> None:
        document = planning.build_selection_document(root=planning.ROOT)
        case = document["cases"][0]
        self.assertEqual(document["summary"]["experiment_count"], 3)
        self.assertEqual(document["summary"]["provider_request_count"], 3)
        self.assertEqual(case["source"]["sha256"], planning.CANONICAL_SOURCE_SHA256)
        self.assertEqual(
            [item["variant_id"] for item in case["experiments"]],
            [item["variant_id"] for item in planning.VARIANTS],
        )
        self.assertEqual(
            {item["shared_provider_seed"] for item in case["experiments"]},
            {planning.SHARED_PROVIDER_SEED},
        )
        policy = document["policy"]
        self.assertIsNone(policy["source_transform"])
        self.assertFalse(policy["disable_provider_safety_filters"])
        self.assertFalse(policy["fallback"])
        self.assertFalse(policy["compositor"])
        self.assertFalse(policy["automatic_paid_retry"])
        self.assertTrue(policy["one_paid_submit_per_new_provider_run_id"])

    def test_prompt_variants_change_only_motion_wording(self) -> None:
        prompts = [item["positive_prompt"] for item in planning.VARIANTS]
        self.assertEqual(len(prompts), len(set(prompts)))
        self.assertEqual(
            prompts,
            [
                "Slow centered zoom in.",
                "The camera moves slowly straight forward, centered and steady throughout the shot.",
                "Smoothly tighten the centered framing by about 5% from start to finish.",
            ],
        )
        forbidden = (
            "woman",
            "body",
            "phone",
            "pregnan",
            "medical",
            "femibion",
            "brand",
        )
        for prompt in prompts:
            lowered = prompt.lower()
            self.assertFalse(any(token in lowered for token in forbidden))

    def test_source_lineage_is_terminal_no_output_and_inactive(self) -> None:
        document = planning.build_selection_document(root=planning.ROOT)
        prior = document["cases"][0]["source_provider_attempt"]
        self.assertEqual(prior["status"], "provider-failed")
        self.assertFalse(prior["provider_may_be_active"])
        self.assertEqual(prior["submission_count"], 1)
        self.assertTrue(prior["terminal_no_output_stop_applied"])
        self.assertGreaterEqual(
            document["diagnosis"]["person_preserving_provider_failures_at_least"],
            12,
        )

    def test_result_gate_requires_exact_variant_prompt(self) -> None:
        experiment = planning.build_selection_document(root=planning.ROOT)["cases"][0][
            "experiments"
        ][0]
        result = {
            "analysis": {"structured_intent": {"rendering_strategy": "camera-only"}},
            "models": [
                {
                    "model_id": planning.MODEL_ID,
                    "execution_mode": "i2v",
                    "positive_prompt": experiment["positive_prompt"] + " Extra.",
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
        with self.assertRaisesRegex(planning.TuneV8PlanningError, "exact V8 prompt"):
            planning.validate_result(result, experiment)

    def test_prepare_uses_three_distinct_lite_runner_run_ids(self) -> None:
        document = planning.build_selection_document(root=planning.ROOT)
        case = document["cases"][0]
        with mock.patch("pathlib.Path.exists", return_value=False), mock.patch.object(
            planning.runner, "prepare_run"
        ) as prepare:
            for experiment in case["experiments"]:
                self.assertEqual(
                    planning.prepare_experiment(case, copy.deepcopy(experiment)),
                    "prepared",
                )
        self.assertEqual(prepare.call_count, 3)
        run_ids = [call.args[1] for call in prepare.call_args_list]
        self.assertEqual(len(run_ids), len(set(run_ids)))
        self.assertTrue(all(call.args[2] == case["source"]["path"] for call in prepare.call_args_list))

    def test_built_manifest_has_three_verified_lite_results(self) -> None:
        document = planning.read_json(planning.ROOT / planning.PROMPT_MANIFEST_REL)
        experiments = document["cases"][0]["experiments"]
        self.assertEqual(len(experiments), 3)
        for experiment, variant in zip(experiments, planning.VARIANTS, strict=True):
            self.assertEqual(experiment["positive_prompt"], variant["positive_prompt"])
            self.assertEqual(experiment["tuned"]["positive_prompt"], variant["positive_prompt"])
            self.assertTrue(experiment["planning"]["provenance"]["verified"])
            self.assertEqual(
                experiment["planning"]["provenance"]["agent_id"],
                planning.AGENT_ID,
            )


if __name__ == "__main__":
    unittest.main()
