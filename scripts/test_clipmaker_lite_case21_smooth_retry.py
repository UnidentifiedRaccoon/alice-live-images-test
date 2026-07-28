import contextlib
import copy
import unittest
from decimal import Decimal
from unittest import mock

from scripts import clipmaker_lite_case21_smooth_retry as retry


class ClipmakerLiteCase21SmoothRetryTest(unittest.TestCase):
    def test_identity_budget_and_retry_binding_are_exact(self) -> None:
        self.assertEqual(retry.SAMPLE.variant_id, "staggered-ease-retry1")
        self.assertEqual(
            retry.PLANNING_RUN_ID,
            "promopages-9930-case21-wan27-smooth-staggered-ease-retry1-20260728-v1",
        )
        self.assertEqual(
            retry.PLANNING_RESULT_SHA256,
            "a5c5da332d3bd46634928b517083fb0bf35fe8b4261ef388b5ca267d501a0ef6",
        )
        self.assertEqual(
            retry.RETRY_OF_PROVIDER_RUN_ID,
            "promopages-9930-case21-wan27-smooth-provider-20260728-v1-"
            "21-maier-04-smooth-staggered-ease-wan-2-7",
        )
        self.assertEqual(
            retry.SUPERSEDES_FOR_DEMO_PROVIDER_RUN_ID,
            retry.RETRY_OF_PROVIDER_RUN_ID,
        )
        self.assertNotEqual(retry._provider_run_id(), retry.RETRY_OF_PROVIDER_RUN_ID)
        self.assertEqual(retry.parse_budget("2.50"), Decimal("2.50"))
        self.assertEqual(retry.parse_budget("3.00"), Decimal("3.00"))
        with self.assertRaisesRegex(retry.SmoothRetryError, "below"):
            retry.parse_budget("2.49")
        with self.assertRaisesRegex(retry.SmoothRetryError, "exceeds"):
            retry.parse_budget("3.01")
        cost = retry.cost_document("3.00")
        self.assertEqual(cost["base_reserved_usd"], 2.0)
        self.assertEqual(cost["explicit_retry_reserved_usd"], 0.5)
        self.assertEqual(cost["aggregate_reserved_usd"], 2.5)
        self.assertEqual(cost["remaining_contingency_attempt_count"], 1)
        self.assertFalse(cost["automatic_paid_retries"])

    def test_verified_planning_result_is_bound_and_semantically_repaired(self) -> None:
        job = retry.load_retry_job(retry.ENTRY, retry.ROOT)
        self.assertTrue(job.provenance["verified"])
        self.assertEqual(job.provenance["models"], [retry.MODEL_ID])
        self.assertEqual(job.result_sha256, retry.PLANNING_RESULT_SHA256)
        self.assertEqual(job.runtime["frame_inputs"], ["first_frame"])
        self.assertLessEqual(len(job.positive_prompt), 480)
        self.assertIn("two-pan balance", job.positive_prompt)
        self.assertIn("central stand locked", job.positive_prompt)
        self.assertIn("battery fills red through yellow to full green", job.positive_prompt)
        self.assertIn("No clock or dial substitution", job.negative_prompt)

    def test_request_is_one_first_frame_and_has_no_loop_or_last_frame(self) -> None:
        job = retry.load_retry_job(retry.ENTRY, retry.ROOT)
        prompt = retry.retry_provider_prompt(job)
        request = retry.native.provider_request_preview(
            retry.provider_sample(), prompt
        )
        retry.assert_retry_request(retry.ENTRY, request, job)
        self.assertEqual(len(request["frame_images"]), 1)
        self.assertEqual(request["frame_images"][0]["frame_type"], "first_frame")
        self.assertNotIn("loop", request)
        self.assertNotIn("last_frame", request)
        self.assertEqual(
            request["provider"]["options"]["atlas-cloud"]["parameters"],
            {"prompt_extend": True, "negative_prompt": job.negative_prompt},
        )

        invalid = copy.deepcopy(request)
        invalid["loop"] = False
        with self.assertRaisesRegex(retry.SmoothRetryError, "Non-exact"):
            retry.assert_retry_request(retry.ENTRY, invalid, job)

    def test_initial_four_receipts_are_exact_and_immutable(self) -> None:
        observed = retry.validate_base_receipts(retry.ROOT)
        self.assertEqual(observed, retry.BASE_RECEIPT_SHA256)
        self.assertEqual(len(observed), 15)

        real_sha256_file = retry.sha256_file

        def changed_digest(path):
            if path.as_posix().endswith("generation-manifest.json"):
                return "0" * 64
            return real_sha256_file(path)

        with mock.patch.object(retry, "sha256_file", side_effect=changed_digest):
            with self.assertRaisesRegex(retry.SmoothRetryError, "receipt changed"):
                retry.validate_base_receipts(retry.ROOT)

    def test_inventory_binds_one_request_and_aggregate_reservation(self) -> None:
        inventory = retry.inventory_document("3.00", retry.ROOT)
        self.assertEqual(inventory["expected_outputs"], 1)
        self.assertTrue(inventory["initial_four_receipts_immutable"])
        self.assertEqual(inventory["base_receipts_sha256"], retry.BASE_RECEIPT_SHA256)
        self.assertEqual(inventory["cost"]["aggregate_reserved_usd"], 2.5)
        self.assertEqual(inventory["retry_of"], retry.RETRY_OF_PROVIDER_RUN_ID)
        row = inventory["entries"][0]
        self.assertEqual(row["provider_run_id"], retry._provider_run_id())
        self.assertEqual(row["planning_result_sha256"], retry.PLANNING_RESULT_SHA256)
        self.assertEqual(row["frame_inputs"], ["first_frame"])
        self.assertEqual(len(row["request_sha256"]), 64)
        policy = inventory["generation_policy"]
        self.assertEqual(policy["wan27_capacity"], 3)
        self.assertEqual(policy["maximum_submissions_for_provider_identity"], 1)
        self.assertFalse(policy["automatic_paid_retries"])
        self.assertFalse(policy["automatic_fallback"])

    @staticmethod
    @contextlib.contextmanager
    def noop_context(*args, **kwargs):
        yield

    def test_configured_native_restores_all_overrides(self) -> None:
        names = (
            "BATCH_ID",
            "MODEL_IDS",
            "MANIFEST_PATH",
            "provider_prompt",
            "prompt_artifact",
            "initial_run",
            "matrix",
            "load_lite_job",
        )
        before = {name: getattr(retry.native, name) for name in names}
        with retry.configured_native(retry.ROOT):
            self.assertEqual(retry.native.matrix(), retry.ENTRIES)
            self.assertEqual(retry.ENTRY.provider_run_id, retry._provider_run_id())
            self.assertIs(retry.native.provider_prompt, retry.retry_provider_prompt)
        for name, value in before.items():
            if callable(value):
                self.assertIs(getattr(retry.native, name), value)
            else:
                self.assertEqual(getattr(retry.native, name), value)

    def test_generate_requires_external_flag_and_selects_only_new_identity(self) -> None:
        with mock.patch.object(retry, "_validate_inventory"):
            with self.assertRaisesRegex(
                retry.SmoothRetryError, "requires --allow-external-processing"
            ):
                retry.run_generation(
                    "3.00",
                    root=retry.ROOT,
                    dry_run=False,
                    allow_external_processing=False,
                )

        observed = []

        def fake_main(argv, root):
            observed.extend(argv)
            return 0

        receipts = {"base": "stable"}
        with (
            mock.patch.object(retry, "_validate_inventory"),
            mock.patch.object(retry, "validate_base_receipts", return_value=receipts),
            mock.patch.object(retry, "configured_native", self.noop_context),
            mock.patch.object(retry.native, "main", side_effect=fake_main),
            mock.patch.object(retry, "write_experiment_manifest"),
        ):
            self.assertEqual(
                retry.run_generation("3.00", root=retry.ROOT, dry_run=True),
                0,
            )
        self.assertEqual(observed.count("--run-id"), 1)
        self.assertIn(retry._provider_run_id(), observed)
        self.assertEqual(observed[observed.index("--wan27-concurrency") + 1], "3")
        self.assertIn("--dry-run", observed)
        self.assertNotIn("--force", observed)


if __name__ == "__main__":
    unittest.main()
