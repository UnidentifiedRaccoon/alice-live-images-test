import contextlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_case21_opacity_stage2 as stage2


class ClipmakerLiteCase21OpacityStage2Test(unittest.TestCase):
    def test_identity_is_exactly_one_wan27_entry_in_a_new_namespace(self) -> None:
        self.assertEqual(
            stage2.PLANNING_RUN_ID,
            "promopages-9930-case21-opacity-only-20260727-v1",
        )
        self.assertEqual(
            stage2.PROVIDER_BATCH_ID,
            "promopages-9930-case21-opacity-only-stage2-20260727-v1",
        )
        self.assertEqual(
            stage2.PLANNING_RESULT_SHA256,
            "57caec79fa7390a07101fbe314dc66b11f448291e271adc5eca8d447332187db",
        )
        self.assertEqual(stage2.ENTRIES, (stage2.ENTRY,))
        self.assertEqual(stage2.ENTRY.sample, stage2.SAMPLE)
        self.assertEqual(stage2.ENTRY.model_id, stage2.native.WAN_27_MODEL_ID)
        self.assertEqual(stage2.MODEL_IDS, (stage2.native.WAN_27_MODEL_ID,))
        self.assertEqual(stage2.EXPECTED_OUTPUTS, 1)
        self.assertTrue(
            stage2.EXPERIMENT_ROOT.as_posix().startswith(
                "clipmaker-lite-test/experiments/"
            )
        )
        self.assertEqual(
            stage2._provider_run_id(),
            (
                "promopages-9930-case21-opacity-only-stage2-20260727-v1-"
                "21-maier-04-opacity-only-wan-2-7"
            ),
        )

        unknown = stage2.native.Entry(stage2.SAMPLE, stage2.native.WAN_MODEL_ID)
        with self.assertRaisesRegex(stage2.Stage2Error, "one entry"):
            stage2._provider_run_id(unknown)
        with self.assertRaisesRegex(stage2.Stage2Error, "only the exact Wan 2.7"):
            stage2.load_stage2_job(unknown, stage2.ROOT)

    def test_verified_provenance_source_context_runtime_and_negative_repair(self) -> None:
        job = stage2.load_stage2_job(stage2.ENTRY, stage2.ROOT)

        self.assertIs(job.provenance["verified"], True)
        self.assertEqual(job.provenance["agent_id"], "clipmaker-lite")
        self.assertEqual(job.provenance["contract_version"], "2.0.2")
        self.assertEqual(job.provenance["models"], [stage2.native.WAN_27_MODEL_ID])
        self.assertEqual(
            job.provenance["source_image_sha256"], stage2.SOURCE_SHA256
        )
        self.assertEqual(
            job.provenance["article_context_sha256"], stage2.CONTEXT_SHA256
        )
        self.assertEqual(job.result_sha256, stage2.PLANNING_RESULT_SHA256)
        self.assertEqual(
            job.result_path,
            (
                stage2.case21.ARTIFACT_NAMESPACE
                / stage2.PLANNING_RUN_ID
                / "result.json"
            ).as_posix(),
        )
        self.assertIn("exact first-frame footprint", job.positive_prompt)
        self.assertIsInstance(job.negative_prompt, str)
        self.assertIn("No size change", job.negative_prompt)
        self.assertLessEqual(len(job.negative_prompt), 500)
        self.assertEqual(job.runtime["duration_seconds"], 5)
        self.assertEqual(job.runtime["provider"], "atlas-cloud")
        self.assertEqual(
            job.runtime["prompt_expansion"],
            {"parameter": "prompt_extend", "value": True},
        )
        self.assertEqual(
            stage2.sha256_file(stage2.ROOT / stage2.case21.SOURCE_PATH),
            stage2.SOURCE_SHA256,
        )
        self.assertEqual(
            stage2.sha256_file(stage2.ROOT / stage2.case21.CONTEXT_PATH),
            stage2.CONTEXT_SHA256,
        )

    def test_budget_is_270_aggregate_and_never_exceeds_three_dollars(self) -> None:
        self.assertEqual(stage2.STAGE1_RESERVED_USD, Decimal("2.20"))
        self.assertEqual(stage2.STAGE2_RESERVED_USD, Decimal("0.50"))
        self.assertEqual(stage2.AGGREGATE_RESERVED_USD, Decimal("2.70"))
        self.assertEqual(stage2.parse_budget("2.70"), Decimal("2.70"))
        self.assertEqual(stage2.parse_budget("3.00"), Decimal("3.00"))

        cost = stage2.cost_document("3.00")
        self.assertEqual(cost["reserved_stage1_usd"], 2.2)
        self.assertEqual(cost["reserved_stage2_usd"], 0.5)
        self.assertEqual(cost["reserved_aggregate_usd"], 2.7)
        self.assertEqual(cost["unreserved_after_stage2_usd"], 0.3)
        self.assertEqual(cost["stage2_maximum_provider_entries"], 1)
        self.assertEqual(cost["maximum_submissions_per_stage2_entry"], 1)
        self.assertFalse(cost["automatic_paid_retries"])
        self.assertFalse(cost["provider_unit_costs_asserted"])
        self.assertFalse(cost["actual_billing_available"])

        with self.assertRaisesRegex(stage2.Stage2Error, "below"):
            stage2.parse_budget("2.69")
        with self.assertRaisesRegex(stage2.Stage2Error, "exceeds"):
            stage2.parse_budget("3.01")
        with self.assertRaisesRegex(stage2.Stage2Error, "Invalid"):
            stage2.parse_budget("bad")

    def test_primary_retry_and_stage1_core_digests_are_pinned(self) -> None:
        self.assertEqual(
            stage2.validate_control_trees(stage2.ROOT),
            {
                "primary": stage2.PRIMARY_TREE_DIGEST,
                "retry": stage2.RETRY_TREE_DIGEST,
                "stage1_generation_core": stage2.STAGE1_EXPERIMENT_CORE_DIGEST,
            },
        )

        review_path = stage2.ROOT / stage2.STAGE1_EXPERIMENT_ROOT / "review"
        self.assertTrue(review_path.is_dir())
        self.assertEqual(
            stage2.tree_digest(
                stage2.STAGE1_EXPERIMENT_ROOT,
                stage2.ROOT,
                excluded_top_levels=("review",),
                excluded_name_suffixes=(".review.json",),
            ),
            stage2.STAGE1_EXPERIMENT_CORE_DIGEST,
        )

        with mock.patch.object(
            stage2,
            "tree_digest",
            side_effect=[
                stage2.PRIMARY_TREE_DIGEST,
                stage2.RETRY_TREE_DIGEST,
                "tampered",
            ],
        ):
            with self.assertRaisesRegex(stage2.Stage2Error, "control trees changed"):
                stage2.validate_control_trees(stage2.ROOT)

    def test_request_uses_exact_mds_orig_and_non_null_negative(self) -> None:
        self.assertTrue(stage2.SOURCE_URL.endswith("/orig"))
        self.assertIn("avatars.mds.yandex.net", stage2.SOURCE_URL)

        with stage2.configured_native(stage2.ROOT):
            entry = stage2.native.matrix()[0]
            job = stage2.native.load_lite_job(entry, stage2.ROOT)
            sample = stage2.native.provider_sample(entry)
            prompt = stage2.native.provider_prompt(job)
            request = stage2.native.provider_request_preview(sample, prompt)

            self.assertEqual(request["model"], stage2.native.WAN_27_MODEL_ID)
            self.assertEqual(sample["source_url"], stage2.SOURCE_URL)
            self.assertEqual(sample["source_path"], stage2.case21.SOURCE_PATH.as_posix())
            self.assertEqual(sample["sha256"], stage2.SOURCE_SHA256)
            self.assertNotIn("raw.githubusercontent.com", json.dumps(request))
            self.assertEqual(
                [frame["image_url"]["url"] for frame in request["frame_images"]],
                [stage2.SOURCE_URL],
            )
            parameters = request["provider"]["options"]["atlas-cloud"]["parameters"]
            self.assertIs(parameters["prompt_extend"], True)
            self.assertEqual(parameters["negative_prompt"], job.negative_prompt)
            self.assertEqual(prompt["negative_prompt"], job.negative_prompt)
            self.assertFalse(prompt["embed_negative_in_positive"])

    def test_inventory_binds_one_request_and_is_immutable(self) -> None:
        inventory = stage2.inventory_document("3.00", stage2.ROOT)

        self.assertEqual(inventory["expected_outputs"], 1)
        self.assertEqual(len(inventory["entries"]), 1)
        self.assertEqual(
            inventory["controls"],
            {
                "primary": stage2.PRIMARY_TREE_DIGEST,
                "retry": stage2.RETRY_TREE_DIGEST,
                "stage1_generation_core": stage2.STAGE1_EXPERIMENT_CORE_DIGEST,
            },
        )
        self.assertEqual(inventory["source"]["provider_url"], stage2.SOURCE_URL)
        self.assertEqual(inventory["source"]["sha256"], stage2.SOURCE_SHA256)
        self.assertEqual(
            inventory["source"]["context_sha256"], stage2.CONTEXT_SHA256
        )
        row = inventory["entries"][0]
        self.assertEqual(row["provider_run_id"], stage2._provider_run_id())
        self.assertEqual(row["model_id"], stage2.native.WAN_27_MODEL_ID)
        self.assertEqual(row["provider_source"], stage2.SOURCE_URL)
        self.assertTrue(row["request_sha256"])
        self.assertTrue(row["positive_prompt_sha256"])
        self.assertTrue(row["negative_prompt_sha256"])
        self.assertEqual(row["reservation_usd"], 0.5)
        self.assertEqual(
            inventory["generation_policy"]["stage2_maximum_submissions"], 1
        )
        self.assertFalse(inventory["generation_policy"]["automatic_retries"])
        self.assertFalse(inventory["generation_policy"]["automatic_fallback"])
        self.assertFalse(inventory["generation_policy"]["normal_run_discovery"])
        self.assertFalse(inventory["generation_policy"]["force_allowed"])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = {"schema_version": 1, "entries": ["frozen"]}
            with mock.patch.object(stage2, "inventory_document", return_value=first):
                self.assertEqual(stage2.write_inventory("3.00", root), first)
                self.assertEqual(stage2.write_inventory("3.00", root), first)

            path = root / stage2.INVENTORY_PATH
            before = path.read_bytes()
            with mock.patch.object(
                stage2,
                "inventory_document",
                return_value={"schema_version": 1, "entries": ["changed"]},
            ):
                with self.assertRaisesRegex(
                    stage2.Stage2Error, "Immutable stage-2 inventory differs"
                ):
                    stage2.write_inventory("3.00", root)
            self.assertEqual(path.read_bytes(), before)

    def test_configured_native_sets_one_entry_and_restores_every_binding(self) -> None:
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
        before = {name: getattr(stage2.native, name) for name in names}

        with stage2.configured_native(stage2.ROOT):
            self.assertEqual(stage2.native.matrix(), stage2.ENTRIES)
            self.assertEqual(stage2.native.BATCH_ID, stage2.PROVIDER_BATCH_ID)
            self.assertEqual(
                stage2.native.PLANNING_BATCH_ID, stage2.PLANNING_RUN_ID
            )
            self.assertEqual(stage2.native.MODEL_IDS, stage2.MODEL_IDS)
            self.assertEqual(stage2.native.PLANNING_MODEL_IDS, stage2.MODEL_IDS)
            self.assertEqual(stage2.native.SAMPLES, stage2.SAMPLES)
            self.assertIsNone(stage2.native.WAN_SUBMIT_MODE)
            self.assertEqual(
                stage2.native.MANIFEST_PATH,
                stage2.GENERATION_MANIFEST_PATH,
            )
            self.assertEqual(
                stage2.native.matrix()[0].provider_run_id,
                stage2._provider_run_id(),
            )

        for name, value in before.items():
            with self.subTest(binding=name):
                if callable(value):
                    self.assertIs(getattr(stage2.native, name), value)
                else:
                    self.assertEqual(getattr(stage2.native, name), value)

    def test_real_generation_requires_external_flag_before_native_submit(self) -> None:
        expected_inventory = {"exact": True}
        with (
            mock.patch.object(
                stage2, "inventory_document", return_value=expected_inventory
            ),
            mock.patch.object(stage2, "read_json", return_value=expected_inventory),
            mock.patch.object(stage2.native, "main") as native_main,
        ):
            with self.assertRaisesRegex(
                stage2.Stage2Error, "requires --allow-external-processing"
            ):
                stage2.run_generation(
                    "3.00",
                    root=stage2.ROOT,
                    dry_run=False,
                    allow_external_processing=False,
                )
        native_main.assert_not_called()

    def test_dry_run_delegates_one_entry_without_filters_force_or_retry(self) -> None:
        expected_inventory = {"exact": True}
        controls = {
            "primary": stage2.PRIMARY_TREE_DIGEST,
            "retry": stage2.RETRY_TREE_DIGEST,
            "stage1_generation_core": stage2.STAGE1_EXPERIMENT_CORE_DIGEST,
        }
        observed_matrix = []

        def fake_native_main(argv, root):
            observed_matrix.extend(stage2.native.matrix())
            return 0

        with (
            mock.patch.object(
                stage2, "inventory_document", return_value=expected_inventory
            ),
            mock.patch.object(stage2, "read_json", return_value=expected_inventory),
            mock.patch.object(stage2, "validate_control_trees", return_value=controls),
            mock.patch.object(
                stage2.native, "main", side_effect=fake_native_main
            ) as native_main,
            mock.patch.object(stage2, "write_experiment_manifest") as write_manifest,
        ):
            result = stage2.run_generation(
                "3.00",
                root=stage2.ROOT,
                timeout=30,
                poll_interval=1.0,
                dry_run=True,
                allow_external_processing=False,
            )

        self.assertEqual(result, 0)
        self.assertEqual(observed_matrix, [stage2.ENTRY])
        argv = native_main.call_args.args[0]
        self.assertEqual(argv[argv.index("--wan27-concurrency") + 1], "1")
        self.assertEqual(argv[argv.index("--timeout") + 1], "30")
        self.assertEqual(argv[argv.index("--poll-interval") + 1], "1.0")
        self.assertIn("--dry-run", argv)
        self.assertNotIn("--allow-external-processing", argv)
        self.assertNotIn("--force", argv)
        self.assertNotIn("--model", argv)
        self.assertNotIn("--run-id", argv)
        self.assertNotIn("--fail-fast", argv)
        write_manifest.assert_called_once_with("3.00", stage2.ROOT)

    def test_same_entry_can_transition_from_dry_run_to_one_real_attempt(self) -> None:
        expected_inventory = {"exact": True}
        controls = {
            "primary": stage2.PRIMARY_TREE_DIGEST,
            "retry": stage2.RETRY_TREE_DIGEST,
            "stage1_generation_core": stage2.STAGE1_EXPERIMENT_CORE_DIGEST,
        }
        calls: list[tuple[list[str], tuple[stage2.native.Entry, ...]]] = []

        def fake_native_main(argv, root):
            calls.append((list(argv), stage2.native.matrix()))
            return 0

        with (
            mock.patch.object(
                stage2, "inventory_document", return_value=expected_inventory
            ),
            mock.patch.object(stage2, "read_json", return_value=expected_inventory),
            mock.patch.object(stage2, "validate_control_trees", return_value=controls),
            mock.patch.object(stage2.native, "main", side_effect=fake_native_main),
            mock.patch.object(stage2, "write_experiment_manifest"),
            mock.patch.object(
                stage2.case21,
                "batch_run_lock",
                return_value=contextlib.nullcontext(),
            ),
        ):
            self.assertEqual(
                stage2.run_generation("3.00", root=stage2.ROOT, dry_run=True),
                0,
            )
            self.assertEqual(
                stage2.run_generation(
                    "3.00",
                    root=stage2.ROOT,
                    dry_run=False,
                    allow_external_processing=True,
                ),
                0,
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1], (stage2.ENTRY,))
        self.assertEqual(calls[1][1], (stage2.ENTRY,))
        self.assertIn("--dry-run", calls[0][0])
        self.assertIn("--allow-external-processing", calls[1][0])
        self.assertNotIn("--force", calls[1][0])
        self.assertNotIn("dry-run", stage2.native.BLOCKED_STATUSES)


if __name__ == "__main__":
    unittest.main()
