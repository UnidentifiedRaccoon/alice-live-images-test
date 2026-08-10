import contextlib
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_promopages_10060_femibion_veo_recovery_v2 as recovery


class FemibionVeoRecoveryV2Test(unittest.TestCase):
    def test_scope_budget_and_verified_prompt_are_exact(self) -> None:
        self.assertEqual(recovery.ENTRIES, (recovery.ENTRY,))
        self.assertEqual(recovery.ENTRY.model_id, "google/veo-3.1-lite")
        self.assertEqual(recovery.SAMPLE.image_id, "06")
        self.assertTrue(recovery.SAMPLE.planning_run_id.startswith(recovery.RECOVERY_ID))
        self.assertTrue(recovery.ENTRY.provider_run_id.startswith(recovery.PROVIDER_BATCH_ID))

        state = recovery.preflight(recovery.ROOT, budget_cap_usd="99.40")
        record = state["record"]
        self.assertEqual(record["positive_prompt"], recovery.EXPECTED_POSITIVE_PROMPT)
        self.assertIsNone(record["negative_prompt"])
        self.assertEqual(record["request_sha256"], recovery.EXPECTED_REQUEST_SHA256)
        self.assertNotIn(record["request_sha256"], {
            recovery.OLD_REQUEST_SHA256,
            recovery.V1_REQUEST_SHA256,
        })
        self.assertTrue(record["provenance"]["verified"])
        self.assertEqual(record["provenance"]["contract_version"], "2.0.8")
        words = set(record["positive_prompt"].casefold().replace(".", "").split())
        self.assertFalse(words.intersection(recovery.FORBIDDEN_PROMPT_TERMS))

        accounting = state["accounting"]
        self.assertEqual(accounting["baseline_paid_submissions"], 283)
        self.assertEqual(accounting["baseline_reserved_usd"], 99.05)
        self.assertEqual(accounting["recovery_paid_submissions"], 1)
        self.assertEqual(accounting["recovery_reserved_usd"], 0.35)
        self.assertEqual(accounting["aggregate_paid_submissions"], 284)
        self.assertEqual(accounting["aggregate_reserved_usd"], 99.40)
        self.assertEqual(accounting["hard_cap_headroom_usd"], 0.60)

    def test_v1_partial_evidence_and_full_failure_chain_are_immutable(self) -> None:
        evidence = recovery.validate_v1_evidence(recovery.ROOT)
        self.assertEqual(len(evidence["failed_attempt_chain"]), 3)
        self.assertEqual(
            [item["attempt"] for item in evidence["failed_attempt_chain"]],
            ["primary", "terminal-retry-v1", "content-filter-recovery-v1"],
        )
        self.assertEqual(
            [item["provider_job_id"] for item in evidence["failed_attempt_chain"]],
            ["Hfvx2OaGO9vsyrcs6AMf", "dqjE7PrI5frFAFW7Y2Aa", "SwdH1eVdnIzgLHeXaTIg"],
        )
        self.assertTrue(
            all(item["status"] == "provider-filtered" for item in evidence["failed_attempt_chain"])
        )
        self.assertEqual(
            evidence["selected_08"]["provider_run_id"],
            recovery.V1_SUCCESS_PROVIDER_RUN_ID,
        )
        self.assertEqual(evidence["selected_08"]["status"], "succeeded")
        self.assertEqual(
            evidence["selected_08"]["media"]["sha256"],
            "be2a072ffe4fe3934563e148956c3d05bcb6123e8a878829b18d9adead5af153",
        )

    def test_request_rejects_any_prompt_or_route_change(self) -> None:
        with recovery.configured_native(recovery.ROOT):
            job = recovery.load_v2_job(recovery.ENTRY, recovery.ROOT)
            request = recovery.native.provider_request_preview(
                recovery.provider_sample(recovery.ENTRY),
                recovery.native.provider_prompt(job),
            )
        recovery.assert_request(request, job)
        changed = copy.deepcopy(request)
        changed["prompt"] = "Locked camera. The phone stays visible."
        with self.assertRaisesRegex(recovery.RecoveryError, "Non-exact"):
            recovery.assert_request(changed, job)
        changed = copy.deepcopy(request)
        changed["model"] = "google/veo-3.1"
        with self.assertRaisesRegex(recovery.RecoveryError, "Non-exact"):
            recovery.assert_request(changed, job)

    def test_budget_and_external_processing_gates_are_mandatory(self) -> None:
        for invalid in ("99.39", "99.41", "100", "nope"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(recovery.RecoveryError):
                    recovery.accounting_document(invalid)
        parser = recovery.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["generate", "--allow-external-processing"])
        parsed = parser.parse_args(
            [
                "generate",
                "--budget-cap-usd",
                "99.40",
                "--allow-external-processing",
            ]
        )
        self.assertEqual(parsed.budget_cap_usd, recovery.REQUIRED_OPERATOR_BUDGET_CAP_USD)
        with self.assertRaisesRegex(recovery.RecoveryError, "requires"):
            recovery.run_generation(
                "generate",
                budget_cap_usd="99.40",
                root=recovery.ROOT,
                allow_external_processing=False,
            )

    @staticmethod
    @contextlib.contextmanager
    def noop_context(*args, **kwargs):
        yield

    def test_generate_selects_exactly_one_new_provider_identity(self) -> None:
        observed: list[str] = []

        def fake_main(argv, root):
            observed.extend(argv)
            return 0

        state = {"record": {}}
        rows = [{"entry": recovery.ENTRY}]
        manifests = (
            {"ready_for_combined_selection": False},
            {"ready_for_merge": False},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(recovery, "preflight", return_value=state),
                mock.patch.object(recovery, "snapshot_v1_evidence", return_value={}),
                mock.patch.object(recovery, "recovery_run_lock", self.noop_context),
                mock.patch.object(recovery, "configured_native", self.noop_context),
                mock.patch.object(recovery.native, "materialize", return_value=rows),
                mock.patch.object(recovery.native, "main", side_effect=fake_main),
                mock.patch.object(
                    recovery,
                    "write_recovery_manifests",
                    return_value=manifests,
                ),
            ):
                result = recovery.run_generation(
                    "generate",
                    budget_cap_usd="99.40",
                    root=root,
                    allow_external_processing=True,
                )
        self.assertEqual(result, 0)
        self.assertEqual(observed.count("--run-id"), 1)
        self.assertEqual(
            observed[observed.index("--run-id") + 1],
            recovery.ENTRY.provider_run_id,
        )
        self.assertEqual(observed[observed.index("--veo31-concurrency") + 1], "1")
        self.assertNotIn("--force", observed)
        self.assertNotIn("--model", observed)

    def _accepted_fixture(self, root: Path):
        paths = recovery.artifact_paths(recovery.ENTRY, root)
        paths["directory"].mkdir(parents=True)
        payload = b"v2-video"
        paths["video"].write_bytes(payload)
        media = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        check = {"conforms": True, "warnings": []}
        request = {"model": recovery.MODEL_ID, "prompt": recovery.EXPECTED_POSITIVE_PROMPT}
        record = {
            "planning_run_id": recovery.SAMPLE.planning_run_id,
            "planning_result_path": (
                recovery.ARTIFACT_NAMESPACE / recovery.SAMPLE.planning_run_id / "result.json"
            ).as_posix(),
            "planning_result_sha256": recovery.EXPECTED_PLANNING_RESULT_SHA256,
            "provenance": {"verified": True, "contract_version": "2.0.8"},
            "scene_plan": "subtle blink and breathing",
            "positive_prompt": recovery.EXPECTED_POSITIVE_PROMPT,
            "negative_prompt": None,
            "request": request,
            "request_sha256": recovery.EXPECTED_REQUEST_SHA256,
            "request_fingerprint_version": recovery.transport.REQUEST_FINGERPRINT_VERSION,
        }
        recovery.transport.atomic_write_json(
            paths["prompt"],
            {
                "provider_run_id": recovery.ENTRY.provider_run_id,
                "supersedes_for_demo": recovery.ORIGINAL_SUPERSEDES_07,
                "supersedes_attempt": recovery.V1_FAILED_PROVIDER_RUN_ID,
                "recovery": recovery._recovery_binding(),
            },
        )
        recovery.transport.atomic_write_json(
            paths["run"],
            {
                "provider_run_id": recovery.ENTRY.provider_run_id,
                "provider_job_id": "new-job",
                "supersedes_for_demo": recovery.ORIGINAL_SUPERSEDES_07,
                "supersedes_attempt": recovery.V1_FAILED_PROVIDER_RUN_ID,
                "recovery": recovery._recovery_binding(),
                "status": "succeeded",
                "provider_may_be_active": False,
                "request": request,
                "request_sha256": recovery.EXPECTED_REQUEST_SHA256,
                "request_fingerprint_version": recovery.transport.REQUEST_FINGERPRINT_VERSION,
                "media": media,
                "contract_check": check,
                "error": None,
            },
        )
        generation = {
            "ticket": recovery.TICKET,
            "batch_id": recovery.PROVIDER_BATCH_ID,
            "agent_id": recovery.AGENT_ID,
            "expected_outputs": 1,
            "outputs": [
                {
                    "lite_run_id": recovery.SAMPLE.planning_run_id,
                    "provider_run_id": recovery.ENTRY.provider_run_id,
                    "sample_id": recovery.SAMPLE.sample_id,
                    "article_slug": recovery.SAMPLE.article_slug,
                    "source_path": recovery.SAMPLE.source_path,
                    "model_id": recovery.MODEL_ID,
                    "status": "succeeded",
                    "recorded_status": "succeeded",
                    "provider_may_be_active": False,
                    "prompt_path": paths["prompt"].relative_to(root).as_posix(),
                    "run_path": paths["run"].relative_to(root).as_posix(),
                    "video_path": paths["video"].relative_to(root).as_posix(),
                    "media": media,
                    "contract_check": check,
                    "error": None,
                }
            ],
        }
        v1_output = {
            "article_slug": "08-femibion-grudnoe-vskarmlivanie",
            "image_id": "05",
            "model_id": recovery.MODEL_ID,
            "provider_run_id": recovery.V1_SUCCESS_PROVIDER_RUN_ID,
            "status": "succeeded",
            "recorded_status": "succeeded",
            "provider_may_be_active": False,
            "video_path": "v1/05.mp4",
            "media": {"sha256": "b" * 64, "bytes": 5},
            "contract_check": {"conforms": True},
            "supersedes_for_demo": recovery.ORIGINAL_SUPERSEDES_08,
        }
        chain = [{"attempt": str(index)} for index in range(3)]
        state = {
            "route": {"model_id": recovery.MODEL_ID},
            "contract": {"contract_version": "2.0.8"},
            "accounting": recovery.accounting_document("99.40"),
            "record": record,
            "v1_evidence": {
                "generation_manifest": {"path": "v1-generation", "sha256": "c" * 64},
                "recovery_manifest": {
                    "path": recovery.V1_RECOVERY_MANIFEST_REL.as_posix(),
                    "sha256": recovery.V1_EVIDENCE_SHA256[
                        recovery.V1_RECOVERY_MANIFEST_REL
                    ],
                    "accepted_output_count": 1,
                    "ready_for_merge": False,
                },
                "failed_attempt_chain": chain,
                "selected_08": v1_output,
                "planning_08": {"planning_run_id": "v1-08", "provenance": {"verified": True}},
            },
        }
        return generation, state

    def test_v2_and_combined_manifests_are_all_or_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generation, state = self._accepted_fixture(root)
            v2 = recovery.recovery_document(
                generation, state, root=root, updated_at="v2-time"
            )
            self.assertEqual(v2["accepted_output_count"], 1)
            self.assertTrue(v2["ready_for_combined_selection"])
            self.assertFalse(v2["ready_for_merge"])
            self.assertEqual(v2["outputs"][0]["provider_job_id"], "new-job")
            self.assertEqual(
                v2["outputs"][0]["recovery"]["failed_attempt_chain"],
                state["v1_evidence"]["failed_attempt_chain"],
            )

            path = root / recovery.RECOVERY_MANIFEST_REL
            recovery.transport.atomic_write_json(path, v2)
            combined = recovery.combined_selection_document(
                v2, state, root=root, updated_at="combined-time"
            )
            self.assertTrue(combined["ready_for_merge"])
            self.assertEqual(combined["accepted_output_count"], 2)
            self.assertEqual(len(combined["outputs"]), 2)
            self.assertEqual(len(combined["attempt_manifests"]), 2)
            self.assertEqual(len(combined["failed_attempt_chain"]), 3)
            self.assertEqual(combined["accounting"]["aggregate_paid_submissions"], 284)
            self.assertEqual(combined["accounting"]["aggregate_reserved_usd"], 99.40)
            self.assertEqual(combined["merge_contract"]["replace_exactly"], 2)
            self.assertTrue(combined["merge_contract"]["all_or_nothing"])


if __name__ == "__main__":
    unittest.main()
