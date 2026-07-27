import argparse
import unittest
from unittest import mock

from scripts import clipmaker_lite_case14_prompt_experiment as experiment


class ClipmakerLiteCase14PromptExperimentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = experiment.load_prompt_source(experiment.ROOT)

    def make_row(self, model_id: str) -> experiment.ExperimentRow:
        return experiment.ExperimentRow(
            model_id=model_id,
            provider_run_id=(
                f"{experiment.EXPERIMENT_ID}-{experiment.MODEL_SUFFIXES[model_id]}"
            ),
            source=self.source,
            sample=experiment.provider_sample(),
            prompt=experiment.provider_prompt(model_id, self.source),
            runtime=experiment.runtime_for_model(model_id),
            paths=experiment.artifact_paths(model_id),
        )

    def test_attested_source_prompt_is_exact(self):
        self.assertEqual(
            experiment.sha256_text(self.source.positive_prompt),
            experiment.EXPECTED_PROMPT_SHA256,
        )
        self.assertEqual(self.source.provenance["verified"], True)
        self.assertEqual(self.source.provenance["agent_id"], "clipmaker-lite")
        self.assertEqual(
            self.source.provenance["contract_version"],
            experiment.FROZEN_CONTRACT_VERSION,
        )
        self.assertEqual(
            self.source.provenance["source_image_sha256"],
            experiment.SOURCE_SHA256,
        )
        canonical = (
            experiment.ROOT
            / "artifacts/clipmaker-lite/v1"
            / experiment.PLANNING_RUN_ID
            / "result.json"
        )
        frozen = (
            experiment.ROOT
            / experiment.FROZEN_PLANNING_ROOT
            / "artifacts/clipmaker-lite/v1"
            / experiment.PLANNING_RUN_ID
            / "result.json"
        )
        self.assertEqual(canonical.read_bytes(), frozen.read_bytes())

    def test_both_provider_requests_receive_the_same_input_prompt(self):
        previews = {}
        for model_id in experiment.TARGET_MODEL_IDS:
            row = self.make_row(model_id)
            preview = experiment.request_preview(row)
            previews[model_id] = preview
            self.assertEqual(preview["prompt"], self.source.positive_prompt)
            self.assertEqual(row.prompt["negative_prompt"], None)

        wan_parameters = previews["alibaba/wan-2.7"]["provider"]["options"][
            "atlas-cloud"
        ]["parameters"]
        veo_parameters = previews["google/veo-3.1-lite"]["provider"]["options"][
            "google-vertex"
        ]["parameters"]
        self.assertEqual(wan_parameters, {"prompt_extend": True})
        self.assertEqual(veo_parameters, {"enhancePrompt": True})

    def test_experiment_artifacts_do_not_claim_canonical_lite_identity(self):
        for model_id in experiment.TARGET_MODEL_IDS:
            row = self.make_row(model_id)
            artifact = experiment.prompt_artifact(row)
            self.assertEqual(artifact["canonical_lite_artifact"], False)
            self.assertNotIn("producer", artifact)
            self.assertNotIn("artifacts/clipmaker-lite/v1", row.paths["video"].as_posix())

    def test_real_generation_requires_explicit_external_processing(self):
        args = argparse.Namespace(
            dry_run=False,
            allow_external_processing=False,
        )
        with self.assertRaisesRegex(
            experiment.ExperimentError, "requires --allow-external-processing"
        ):
            experiment.run([], args)

    def test_sync_showcase_runs_full_media_verification_first(self):
        rows = [self.make_row(model_id) for model_id in experiment.TARGET_MODEL_IDS]
        with mock.patch.object(
            experiment,
            "verify",
            return_value=(False, ["Recorded media digest/size changed: alibaba/wan-2.7"]),
        ):
            with self.assertRaisesRegex(
                experiment.ExperimentError,
                "verification failed before showcase sync",
            ):
                experiment.sync_showcase(rows)

    def test_sync_showcase_rejects_unexpected_contract_warnings(self):
        rows = [self.make_row(model_id) for model_id in experiment.TARGET_MODEL_IDS]
        with (
            mock.patch.object(experiment, "verify", return_value=(True, [])),
            mock.patch.object(
                experiment,
                "read_json",
                side_effect=[
                    {
                        "contract_check": {
                            "conforms": False,
                            "warnings": ["unexpected duration warning"],
                        }
                    }
                ],
            ),
        ):
            with self.assertRaisesRegex(
                experiment.ExperimentError,
                "Unsupported media contract warning",
            ):
                experiment.sync_showcase(rows)


if __name__ == "__main__":
    unittest.main()
