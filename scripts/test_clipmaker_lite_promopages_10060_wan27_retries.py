from __future__ import annotations

import unittest
from unittest import mock

from scripts import clipmaker_lite_promopages_10060_wan27_retries as retry


class Wan27QualitativeRetriesTest(unittest.TestCase):
    def test_three_distinct_retry_identities_share_the_exact_original_request(self) -> None:
        requests = [
            retry.request_for_sample(sample, retry.ROOT)
            for sample in retry.SAMPLES
        ]
        self.assertEqual(len(requests), 3)
        self.assertTrue(all(request == retry.EXPECTED_REQUEST for request in requests))
        self.assertEqual(
            {retry.sha256_json(request) for request in requests},
            {retry.EXPECTED_REQUEST_BODY_SHA256},
        )
        provider_ids = [retry.provider_run_id(sample) for sample in retry.SAMPLES]
        self.assertEqual(len(set(provider_ids)), 3)
        self.assertEqual(
            [sample.attempt_index for sample in retry.SAMPLES],
            [1, 2, 3],
        )

    def test_inventory_records_explicit_untuned_retries_and_fixed_cost(self) -> None:
        document = retry.inventory_document(root=retry.ROOT)
        self.assertEqual(document["expected_outputs"], 3)
        self.assertEqual(document["retry_of"], retry.ORIGINAL_PROVIDER_RUN_ID)
        self.assertTrue(document["planning"]["historical_provenance_reverified"])
        self.assertTrue(document["planning"]["provenance"]["verified"])
        self.assertEqual(document["cost"]["aggregate_reserved_usd"], 1.05)
        self.assertEqual(document["cost"]["reservation_per_retry_usd"], 0.35)
        self.assertEqual(
            {entry["retry_of"] for entry in document["entries"]},
            {retry.ORIGINAL_PROVIDER_RUN_ID},
        )
        self.assertEqual(
            {entry["tuning_applied"] for entry in document["entries"]},
            {False},
        )
        self.assertEqual(
            {entry["request_unchanged"] for entry in document["entries"]},
            {True},
        )

    def test_historical_runner_reverifies_the_planning_artifact(self) -> None:
        summary = retry.historical_provenance_summary(retry.ROOT)
        self.assertEqual(summary, retry.EXPECTED_HISTORICAL_PROVENANCE)
        self.assertTrue(summary["verified"])
        self.assertEqual(summary["contract_version"], "2.0.6")

    def test_base_receipt_drift_fails_closed(self) -> None:
        key = retry.SOURCE_PATH.as_posix()
        with mock.patch.dict(
            retry.BASE_RECEIPTS_SHA256,
            {key: "0" * 64},
            clear=False,
        ):
            with self.assertRaisesRegex(
                retry.RetryExperimentError,
                "Immutable base receipt changed",
            ):
                retry.validate_base_receipts(retry.ROOT)

    def test_plan_dry_run_does_not_write_or_materialize(self) -> None:
        with (
            mock.patch.object(retry.transport, "atomic_write_json") as write_json,
            mock.patch.object(retry.native, "materialize") as native_materialize,
        ):
            self.assertEqual(retry.materialize(root=retry.ROOT, dry_run=True), 0)
        write_json.assert_not_called()
        native_materialize.assert_not_called()

    def test_route_is_exact_and_has_capacity_three(self) -> None:
        route = retry.validate_route()
        self.assertEqual(route["adapter"], "eliza-openrouter")
        self.assertEqual(route["provider_key"], "atlas-cloud")
        self.assertEqual(route["capacity"], 3)


if __name__ == "__main__":
    unittest.main()
