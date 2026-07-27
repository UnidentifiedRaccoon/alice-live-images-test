import copy
import json
import tempfile
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_case21_prompt_experiment as experiment


class ClipmakerLiteCase21PromptExperimentTest(unittest.TestCase):
    def test_matrix_is_the_exact_fail_closed_five_entry_design(self) -> None:
        expected = [
            ("monotonic-positive", experiment.native.WAN_MODEL_ID),
            ("monotonic-positive", experiment.native.WAN_27_MODEL_ID),
            ("erosion-negative", experiment.native.WAN_MODEL_ID),
            ("erosion-negative", experiment.native.WAN_27_MODEL_ID),
            ("veo-motion-only", experiment.native.VEO_31_MODEL_ID),
        ]
        actual = [
            (entry.sample.variant_id, entry.model_id)
            for entry in experiment.ENTRIES
        ]

        self.assertEqual(actual, expected)
        self.assertEqual(len(experiment.SAMPLES), 3)
        self.assertEqual(len(experiment.ENTRIES), experiment.EXPECTED_OUTPUTS)
        self.assertEqual(
            Counter(entry.model_id for entry in experiment.ENTRIES),
            {
                experiment.native.WAN_MODEL_ID: 2,
                experiment.native.WAN_27_MODEL_ID: 2,
                experiment.native.VEO_31_MODEL_ID: 1,
            },
        )
        self.assertEqual(
            len(
                {
                    (entry.sample.sample_id, entry.model_id)
                    for entry in experiment.ENTRIES
                }
            ),
            experiment.EXPECTED_OUTPUTS,
        )

        forbidden = experiment.native.Entry(
            experiment.SAMPLE_BY_VARIANT["veo-motion-only"],
            experiment.native.WAN_MODEL_ID,
        )
        with self.assertRaisesRegex(experiment.ExperimentError, "forbidden"):
            experiment._variant(forbidden)

    def test_budget_reserves_220_and_rejects_values_outside_220_to_300(self) -> None:
        self.assertEqual(experiment.RESERVED_COST_USD, Decimal("2.20"))
        self.assertEqual(experiment.parse_budget("2.20"), Decimal("2.20"))
        self.assertEqual(experiment.parse_budget("3.00"), Decimal("3.00"))

        cost = experiment.cost_document("3.00")
        self.assertEqual(cost["reserved_stage1_usd"], 2.2)
        self.assertEqual(cost["unreserved_after_stage1_usd"], 0.8)
        self.assertEqual(cost["maximum_provider_entries"], 5)
        self.assertEqual(cost["maximum_submissions_per_entry"], 1)
        self.assertFalse(cost["automatic_paid_retries"])
        self.assertFalse(cost["provider_unit_costs_asserted"])
        self.assertFalse(cost["actual_billing_available"])

        with self.assertRaisesRegex(experiment.ExperimentError, "below"):
            experiment.parse_budget("2.19")
        with self.assertRaisesRegex(experiment.ExperimentError, "exceeds"):
            experiment.parse_budget("3.01")
        with self.assertRaisesRegex(experiment.ExperimentError, "Invalid"):
            experiment.parse_budget("not-a-number")

    def test_control_tree_digests_are_exact_and_mismatch_fails_closed(self) -> None:
        self.assertEqual(
            experiment.validate_control_trees(experiment.ROOT),
            {
                "primary": experiment.PRIMARY_TREE_DIGEST,
                "retry": experiment.RETRY_TREE_DIGEST,
            },
        )

        with mock.patch.object(
            experiment,
            "tree_digest",
            side_effect=[experiment.PRIMARY_TREE_DIGEST, "tampered"],
        ):
            with self.assertRaisesRegex(
                experiment.ExperimentError, "control batches changed"
            ):
                experiment.validate_control_trees(experiment.ROOT)

    def test_all_plans_have_verified_provenance_and_exact_negative_policy(self) -> None:
        positives: set[str] = set()
        for entry in experiment.ENTRIES:
            with self.subTest(
                variant=entry.sample.variant_id,
                model=entry.model_id,
            ):
                variant = experiment._variant(entry)
                job = experiment.load_experiment_job(entry, experiment.ROOT)
                positives.add(job.positive_prompt)

                self.assertIs(job.provenance["verified"], True)
                self.assertEqual(job.provenance["agent_id"], "clipmaker-lite")
                self.assertEqual(job.provenance["contract_version"], "2.0.2")
                self.assertEqual(
                    job.provenance["models"], list(variant.model_ids)
                )
                self.assertEqual(
                    job.provenance["source_image_sha256"],
                    experiment.SOURCE_SHA256,
                )
                self.assertEqual(
                    job.provenance["article_context_sha256"],
                    experiment.CONTEXT_SHA256,
                )
                self.assertEqual(job.result_sha256, variant.result_sha256)
                self.assertEqual(
                    job.result_path,
                    (
                        experiment.case21.ARTIFACT_NAMESPACE
                        / variant.planning_run_id
                        / "result.json"
                    ).as_posix(),
                )
                if variant.negative_policy == "required-observed-repair":
                    self.assertIsInstance(job.negative_prompt, str)
                    self.assertTrue(job.negative_prompt.strip())
                    self.assertIn("aura growth", job.negative_prompt.lower())
                else:
                    self.assertIsNone(job.negative_prompt)

        self.assertEqual(len(positives), experiment.EXPECTED_OUTPUTS)

    def test_negative_policy_rejects_tampered_lite_results(self) -> None:
        original_read_json = experiment.read_json

        for variant_id, replacement, error in (
            ("monotonic-positive", "new negative", "Unexpected negative"),
            ("erosion-negative", None, "repair is missing"),
        ):
            entry = next(
                item
                for item in experiment.ENTRIES
                if item.sample.variant_id == variant_id
            )
            variant = experiment._variant(entry)
            result_path = (
                experiment.ROOT
                / experiment.case21.ARTIFACT_NAMESPACE
                / variant.planning_run_id
                / "result.json"
            )
            mutated = copy.deepcopy(original_read_json(result_path))
            model = next(
                item
                for item in mutated["models"]
                if item["model_id"] == entry.model_id
            )
            model["negative_prompt"] = replacement

            def fake_read_json(path: Path, *, _mutated=mutated, _path=result_path):
                if Path(path) == _path:
                    return _mutated
                return original_read_json(Path(path))

            with self.subTest(variant=variant_id):
                with mock.patch.object(
                    experiment, "read_json", side_effect=fake_read_json
                ):
                    with self.assertRaisesRegex(experiment.ExperimentError, error):
                        experiment.load_experiment_job(entry, experiment.ROOT)

    def test_provider_requests_use_local_upload_only_for_wan22_and_mds_orig_for_eliza(self) -> None:
        self.assertTrue(experiment.SOURCE_URL.endswith("/orig"))
        self.assertIn("avatars.mds.yandex.net", experiment.SOURCE_URL)

        with experiment.configured_native(experiment.ROOT):
            for entry in experiment.native.matrix():
                with self.subTest(
                    variant=entry.sample.variant_id,
                    model=entry.model_id,
                ):
                    job = experiment.native.load_lite_job(entry, experiment.ROOT)
                    sample = experiment.native.provider_sample(entry)
                    prompt = experiment.native.provider_prompt(job)
                    request = experiment.native.provider_request_preview(sample, prompt)

                    self.assertEqual(request["model"], entry.model_id)
                    self.assertEqual(sample["source_url"], experiment.SOURCE_URL)
                    self.assertEqual(sample["source_path"], experiment.case21.SOURCE_PATH.as_posix())
                    self.assertNotIn("raw.githubusercontent.com", json.dumps(request))

                    if entry.model_id == experiment.native.WAN_MODEL_ID:
                        self.assertNotIn("frame_images", request)
                        self.assertEqual(
                            request["input"]["source_path"],
                            experiment.case21.SOURCE_PATH.as_posix(),
                        )
                        if entry.sample.variant_id == "erosion-negative":
                            self.assertIn("Avoid:", request["input"]["prompt"])
                    else:
                        self.assertEqual(
                            [
                                frame["image_url"]["url"]
                                for frame in request["frame_images"]
                            ],
                            [experiment.SOURCE_URL],
                        )
                        if entry.model_id == experiment.native.WAN_27_MODEL_ID:
                            parameters = request["provider"]["options"][
                                "atlas-cloud"
                            ]["parameters"]
                            self.assertIs(parameters["prompt_extend"], True)
                            if entry.sample.variant_id == "erosion-negative":
                                self.assertEqual(
                                    parameters["negative_prompt"],
                                    job.negative_prompt,
                                )
                        else:
                            self.assertEqual(
                                request["provider"]["options"]["google-vertex"][
                                    "parameters"
                                ],
                                {"enhancePrompt": True},
                            )

    def test_inventory_binds_all_five_requests_and_is_immutable(self) -> None:
        inventory = experiment.inventory_document("3.00", experiment.ROOT)
        self.assertEqual(inventory["expected_outputs"], 5)
        self.assertEqual(len(inventory["entries"]), 5)
        self.assertEqual(
            inventory["controls"],
            {
                "primary": experiment.PRIMARY_TREE_DIGEST,
                "retry": experiment.RETRY_TREE_DIGEST,
            },
        )
        self.assertEqual(
            Counter(row["provider_source"] for row in inventory["entries"]),
            {"local-upload": 2, experiment.SOURCE_URL: 3},
        )
        self.assertTrue(
            all(row["request_sha256"] for row in inventory["entries"])
        )
        self.assertEqual(
            len({row["provider_run_id"] for row in inventory["entries"]}), 5
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = {"schema_version": 1, "entries": ["frozen"]}
            with mock.patch.object(
                experiment, "inventory_document", return_value=first
            ):
                self.assertEqual(experiment.write_inventory("3.00", root), first)
                self.assertEqual(experiment.write_inventory("3.00", root), first)

            path = root / experiment.INVENTORY_PATH
            before = path.read_bytes()
            with mock.patch.object(
                experiment,
                "inventory_document",
                return_value={"schema_version": 1, "entries": ["changed"]},
            ):
                with self.assertRaisesRegex(
                    experiment.ExperimentError, "Immutable experiment inventory differs"
                ):
                    experiment.write_inventory("3.00", root)
            self.assertEqual(path.read_bytes(), before)

    def test_configured_native_sets_exact_identity_and_restores_every_binding(self) -> None:
        names = (
            "BATCH_ID",
            "PLANNING_BATCH_ID",
            "MODEL_IDS",
            "PLANNING_MODEL_IDS",
            "TICKET",
            "MANIFEST_PATH",
            "CONTRACT_PATH",
            "PLANNING_WORKSPACE",
            "PLANNING_PROVENANCE_VERIFIER",
            "SAMPLES",
            "WAN_SUBMIT_MODE",
            "artifact_paths",
            "provider_sample",
            "matrix",
            "load_lite_job",
        )
        before = {name: getattr(experiment.native, name) for name in names}

        with experiment.configured_native(experiment.ROOT):
            entries = experiment.native.matrix()
            self.assertEqual(entries, experiment.ENTRIES)
            self.assertEqual(experiment.native.BATCH_ID, experiment.PROVIDER_BATCH_ID)
            self.assertEqual(experiment.native.PLANNING_BATCH_ID, experiment.EXPERIMENT_ID)
            self.assertEqual(experiment.native.MODEL_IDS, experiment.MODEL_IDS)
            self.assertIsNone(experiment.native.WAN_SUBMIT_MODE)
            self.assertEqual(
                experiment.native.MANIFEST_PATH,
                experiment.GENERATION_MANIFEST_PATH,
            )
            self.assertTrue(
                all(
                    entry.provider_run_id == experiment._provider_run_id(entry)
                    for entry in entries
                )
            )

        for name, value in before.items():
            with self.subTest(binding=name):
                if callable(value):
                    self.assertIs(getattr(experiment.native, name), value)
                else:
                    self.assertEqual(getattr(experiment.native, name), value)

    def test_real_generation_requires_external_flag_before_native_submit(self) -> None:
        expected_inventory = {"exact": True}
        with (
            mock.patch.object(
                experiment, "inventory_document", return_value=expected_inventory
            ),
            mock.patch.object(experiment, "read_json", return_value=expected_inventory),
            mock.patch.object(experiment.native, "main") as native_main,
        ):
            with self.assertRaisesRegex(
                experiment.ExperimentError, "requires --allow-external-processing"
            ):
                experiment.run_generation(
                    "3.00",
                    root=experiment.ROOT,
                    dry_run=False,
                    allow_external_processing=False,
                )
        native_main.assert_not_called()

    def test_dry_run_delegates_all_entries_with_independent_1_3_3_caps(self) -> None:
        expected_inventory = {"exact": True}
        controls = {
            "primary": experiment.PRIMARY_TREE_DIGEST,
            "retry": experiment.RETRY_TREE_DIGEST,
        }
        observed_matrix = []

        def fake_native_main(argv, root):
            observed_matrix.extend(experiment.native.matrix())
            return 0

        with (
            mock.patch.object(
                experiment, "inventory_document", return_value=expected_inventory
            ),
            mock.patch.object(experiment, "read_json", return_value=expected_inventory),
            mock.patch.object(
                experiment, "validate_control_trees", return_value=controls
            ),
            mock.patch.object(
                experiment.native, "main", side_effect=fake_native_main
            ) as native_main,
            mock.patch.object(experiment, "write_experiment_manifest") as write_manifest,
        ):
            result = experiment.run_generation(
                "3.00",
                root=experiment.ROOT,
                timeout=30,
                poll_interval=1.0,
                dry_run=True,
                allow_external_processing=False,
            )

        self.assertEqual(result, 0)
        self.assertEqual(observed_matrix, list(experiment.ENTRIES))
        argv = native_main.call_args.args[0]
        self.assertEqual(argv[argv.index("--wan22-concurrency") + 1], "1")
        self.assertEqual(argv[argv.index("--wan27-concurrency") + 1], "3")
        self.assertEqual(argv[argv.index("--veo31-concurrency") + 1], "3")
        self.assertIn("--dry-run", argv)
        self.assertNotIn("--allow-external-processing", argv)
        self.assertNotIn("--force", argv)
        self.assertNotIn("--model", argv)
        self.assertNotIn("--run-id", argv)
        write_manifest.assert_called_once_with("3.00", experiment.ROOT)

    def test_experiment_manifest_uses_sample_and_model_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / experiment.GENERATION_MANIFEST_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            outputs = [
                {
                    "sample_id": entry.sample.sample_id,
                    "model_id": entry.model_id,
                    "lite_run_id": entry.planning_run_id,
                    "provider_run_id": experiment._provider_run_id(entry),
                    "status": "dry-run",
                }
                for entry in reversed(experiment.ENTRIES)
            ]
            path.write_text(
                json.dumps(
                    {
                        "ticket": experiment.TICKET,
                        "batch_id": experiment.PROVIDER_BATCH_ID,
                        "agent_id": experiment.case21.AGENT_ID,
                        "expected_outputs": experiment.EXPECTED_OUTPUTS,
                        "outputs": outputs,
                    }
                ),
                encoding="utf-8",
            )
            inventory = {
                "source": {
                    "path": experiment.case21.SOURCE_PATH.as_posix(),
                    "sha256": experiment.SOURCE_SHA256,
                }
            }
            controls = {
                "primary": experiment.PRIMARY_TREE_DIGEST,
                "retry": experiment.RETRY_TREE_DIGEST,
            }

            with (
                mock.patch.object(
                    experiment, "inventory_document", return_value=inventory
                ),
                mock.patch.object(
                    experiment, "validate_control_trees", return_value=controls
                ),
            ):
                document = experiment._experiment_document(
                    "3.00", root, updated_at="2026-07-27T00:00:00Z"
                )

                self.assertEqual(len(document["outputs"]), 5)
                self.assertEqual(
                    {
                        (row["sample_id"], row["model_id"]): row["variant_id"]
                        for row in document["outputs"]
                    },
                    {
                        (entry.sample.sample_id, entry.model_id): entry.sample.variant_id
                        for entry in experiment.ENTRIES
                    },
                )

                invalid_outputs = copy.deepcopy(outputs)
                invalid_outputs[0]["sample_id"] = experiment.SAMPLE_BY_VARIANT[
                    "monotonic-positive"
                ].sample_id
                path.write_text(
                    json.dumps(
                        {
                            "ticket": experiment.TICKET,
                            "batch_id": experiment.PROVIDER_BATCH_ID,
                            "agent_id": experiment.case21.AGENT_ID,
                            "expected_outputs": experiment.EXPECTED_OUTPUTS,
                            "outputs": invalid_outputs,
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    experiment.ExperimentError, "output identity changed"
                ):
                    experiment._experiment_document(
                        "3.00", root, updated_at="2026-07-27T00:00:00Z"
                    )


if __name__ == "__main__":
    unittest.main()
