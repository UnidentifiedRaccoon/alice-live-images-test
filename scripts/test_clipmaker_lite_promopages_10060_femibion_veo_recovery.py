import contextlib
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_promopages_10060_femibion_veo_recovery as recovery


class FemibionVeoRecoveryTest(unittest.TestCase):
    def fake_job(self, target, positive="A new safe recovery motion prompt."):
        runtime = recovery.read_json(recovery.ROOT / recovery.CONTRACT_REL)["models"][
            recovery.MODEL_ID
        ]["runtime"]
        return recovery.native.LiteJob(
            entry=target.entry,
            structured_intent={
                "editorial_meaning": "meaning",
                "primary_action": "action",
                "terminal_state": "endpoint",
                "semantic_invariant": "invariant",
            },
            positive_prompt=positive,
            negative_prompt=None,
            result_path=(
                recovery.ARTIFACT_NAMESPACE
                / target.sample.planning_run_id
                / "result.json"
            ).as_posix(),
            result_sha256="a" * 64,
            provenance={
                "verified": True,
                "agent_id": recovery.AGENT_ID,
                "contract_version": recovery.validate_contract(recovery.ROOT)[
                    "contract_version"
                ],
                "models": [recovery.MODEL_ID],
                "source_image_sha256": target.sample.source_sha256,
                "article_context_sha256": target.context_sha256,
            },
            runtime=runtime,
        )

    def test_scope_and_supersede_identities_are_exact(self) -> None:
        self.assertEqual(len(recovery.TARGETS), 2)
        self.assertEqual(len(recovery.ENTRIES), 2)
        self.assertEqual({entry.model_id for entry in recovery.ENTRIES}, {recovery.MODEL_ID})
        self.assertEqual(
            {target.sample.image_id for target in recovery.TARGETS}, {"05", "06"}
        )
        self.assertEqual(
            len({target.entry.provider_run_id for target in recovery.TARGETS}), 2
        )
        for target in recovery.TARGETS:
            self.assertTrue(target.sample.planning_run_id.startswith(recovery.RECOVERY_ID))
            self.assertTrue(target.entry.provider_run_id.startswith(recovery.PROVIDER_BATCH_ID))
            self.assertNotEqual(target.entry.provider_run_id, target.supersedes_for_demo)
            self.assertIn("terminal-retry-v1", target.supersedes_for_demo)

    def test_route_and_old_provider_filtered_evidence_are_bound(self) -> None:
        route = recovery.validate_route(recovery.ROOT)
        self.assertEqual(route["model_id"], recovery.MODEL_ID)
        self.assertEqual(route["adapter"], "eliza-openrouter")
        self.assertEqual(route["transport"], "eliza-video-jobs")
        self.assertEqual(route["provider_key"], "google-vertex")
        self.assertEqual(route["capacity"], 3)
        self.assertFalse(route["automatic_fallback"])
        self.assertFalse(route["normal_run_discovery"])

        evidence = recovery.validate_old_evidence(recovery.ROOT)
        self.assertEqual(set(evidence), {target.sample.sample_id for target in recovery.TARGETS})
        for target in recovery.TARGETS:
            item = evidence[target.sample.sample_id]
            self.assertEqual(item["provider_run_id"], target.supersedes_for_demo)
            self.assertEqual(item["status"], "provider-filtered")
            self.assertTrue(item["retry_v1_exhausted"])

        with mock.patch.object(
            recovery.transport,
            "route_for_model",
            return_value={"adapter": "wrong"},
        ):
            with self.assertRaisesRegex(recovery.RecoveryError, "route changed"):
                recovery.validate_route(recovery.ROOT)

    def test_request_is_exact_veo_route_and_cannot_repeat_filtered_request(self) -> None:
        target = recovery.TARGETS[0]
        job = self.fake_job(target)
        prompt = recovery.native.provider_prompt(job)
        request = recovery.native.provider_request_preview(
            recovery.provider_sample(target.entry), prompt
        )
        recovery.assert_request(target, request, job)
        self.assertEqual(request["model"], recovery.MODEL_ID)
        self.assertEqual(request["duration"], 4)
        self.assertEqual(request["resolution"], "1080p")
        self.assertEqual(request["aspect_ratio"], "16:9")
        self.assertFalse(request["generate_audio"])
        self.assertEqual(len(request["frame_images"]), 1)
        self.assertEqual(request["frame_images"][0]["frame_type"], "first_frame")
        self.assertEqual(
            request["provider"],
            {"options": {"google-vertex": {"parameters": {"enhancePrompt": True}}}},
        )

        changed = copy.deepcopy(request)
        changed["model"] = "google/veo-3.1"
        with self.assertRaisesRegex(recovery.RecoveryError, "Non-exact"):
            recovery.assert_request(target, changed, job)

        old_prompt = (
            "Fixed camera. The woman makes one gentle, deliberate tap on the "
            "smartphone screen, then her hand settles as she keeps a calm, focused "
            "smile; the phone is clearly visible in the final frame."
        )
        old_job = self.fake_job(target, positive=old_prompt)
        old_request = recovery.native.provider_request_preview(
            recovery.provider_sample(target.entry),
            recovery.native.provider_prompt(old_job),
        )
        self.assertEqual(
            recovery.transport.request_fingerprint(
                old_request, recovery.provider_sample(target.entry)
            ),
            target.old_request_sha256,
        )
        with self.assertRaisesRegex(recovery.RecoveryError, "twice-filtered"):
            recovery.assert_request(target, old_request, old_job)

    def test_new_planning_provenance_is_required(self) -> None:
        target = recovery.TARGETS[0]
        job = self.fake_job(target)
        job = recovery.native.LiteJob(
            **{**job.__dict__, "provenance": {**job.provenance, "verified": False}}
        )
        with mock.patch.object(recovery, "_NATIVE_LOAD_LITE_JOB", return_value=job):
            with self.assertRaisesRegex(recovery.RecoveryError, "provenance binding"):
                recovery.load_recovery_job(target.entry, recovery.ROOT)

    def test_receipts_carry_explicit_demo_supersede_binding(self) -> None:
        target = recovery.TARGETS[0]
        job = self.fake_job(target)
        prompt = recovery.recovery_prompt_artifact(job)
        paths = recovery.artifact_paths(target.entry, recovery.ROOT)
        run = recovery.recovery_initial_run(job, paths, recovery.ROOT)
        for document in (prompt, run):
            self.assertEqual(
                document["supersedes_for_demo"], target.supersedes_for_demo
            )
            self.assertEqual(
                document["recovery"]["logical_key"], target.logical_key
            )
            self.assertFalse(document["recovery"]["automatic_retry"])
            self.assertFalse(document["recovery"]["fallback"])

    def test_configured_native_restricts_and_restores_matrix(self) -> None:
        names = (
            "BATCH_ID",
            "MODEL_IDS",
            "MANIFEST_PATH",
            "provider_sample",
            "artifact_paths",
            "matrix",
            "load_lite_job",
            "materialize_entry",
        )
        before = {name: getattr(recovery.native, name) for name in names}
        with recovery.configured_native(recovery.ROOT):
            self.assertEqual(recovery.native.matrix(), recovery.ENTRIES)
            self.assertEqual(recovery.native.MODEL_IDS, (recovery.MODEL_ID,))
            self.assertEqual(
                recovery.native.MANIFEST_PATH, recovery.GENERATION_MANIFEST_REL
            )
        for name, value in before.items():
            if callable(value):
                self.assertIs(getattr(recovery.native, name), value)
            else:
                self.assertEqual(getattr(recovery.native, name), value)

    def test_dry_run_has_no_write_and_generate_requires_explicit_external_flag(self) -> None:
        state = {
            "records": {
                target.sample.sample_id: {
                    "planning_run_id": target.sample.planning_run_id
                }
                for target in recovery.TARGETS
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(recovery, "preflight", return_value=state):
                self.assertEqual(recovery.dry_run("99.05", root), 0)
            self.assertEqual(list(root.iterdir()), [])

        with self.assertRaisesRegex(recovery.RecoveryError, "requires"):
            recovery.run_generation(
                "generate",
                budget_cap_usd="99.05",
                root=recovery.ROOT,
                allow_external_processing=False,
            )

    def test_budget_gate_is_exact_and_accounting_is_frozen(self) -> None:
        accounting = recovery.accounting_document("99.05")
        self.assertEqual(accounting["baseline_paid_submissions"], 281)
        self.assertEqual(accounting["baseline_reserved_usd"], 98.35)
        self.assertEqual(accounting["recovery_paid_submissions"], 2)
        self.assertEqual(accounting["recovery_reserved_usd"], 0.70)
        self.assertEqual(accounting["aggregate_paid_submissions"], 283)
        self.assertEqual(accounting["aggregate_reserved_usd"], 99.05)
        self.assertEqual(accounting["operator_budget_cap_usd"], 99.05)
        self.assertEqual(accounting["hard_budget_cap_usd"], 100.0)
        self.assertEqual(accounting["hard_cap_headroom_usd"], 0.95)
        self.assertEqual(accounting["maximum_new_paid_submissions"], 2)
        self.assertFalse(accounting["automatic_paid_retries"])
        for invalid in ("99.04", "99.06", "100", "not-a-number"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(recovery.RecoveryError, "budget-cap-usd"):
                    recovery.accounting_document(invalid)

        parser = recovery.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["generate", "--allow-external-processing"])
        parsed = parser.parse_args(
            [
                "generate",
                "--budget-cap-usd",
                "99.05",
                "--allow-external-processing",
            ]
        )
        self.assertEqual(parsed.budget_cap_usd, recovery.REQUIRED_OPERATOR_BUDGET_CAP_USD)

    def test_generate_and_resume_namespace_guards_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(recovery.RecoveryError, "existing recovery"):
                recovery._validate_mode_state("resume", root)
            recovery_root = root / recovery.RECOVERY_ROOT_REL
            recovery_root.mkdir(parents=True)
            with self.assertRaisesRegex(recovery.RecoveryError, "use resume"):
                recovery._validate_mode_state("generate", root)
            with self.assertRaisesRegex(recovery.RecoveryError, "existing recovery"):
                recovery._validate_mode_state("resume", root)
            run = recovery.artifact_paths(recovery.ENTRIES[0], root)["run"]
            run.parent.mkdir(parents=True)
            run.write_text("{}", encoding="utf-8")
            recovery._validate_mode_state("resume", root)

    @staticmethod
    @contextlib.contextmanager
    def noop_context(*args, **kwargs):
        yield

    def test_generate_and_resume_select_only_two_new_provider_identities(self) -> None:
        observed: list[str] = []

        def fake_main(argv, root):
            observed.extend(argv)
            return 0

        state = {"records": {}, "route": {}, "contract": {}, "old_evidence": {}}
        rows = [{"entry": entry} for entry in recovery.ENTRIES]
        manifest = {"ready_for_merge": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common = (
                mock.patch.object(recovery, "preflight", return_value=state),
                mock.patch.object(recovery, "snapshot_old_receipts", return_value={}),
                mock.patch.object(recovery, "recovery_run_lock", self.noop_context),
                mock.patch.object(recovery, "configured_native", self.noop_context),
                mock.patch.object(recovery.native, "materialize", return_value=rows),
                mock.patch.object(recovery.native, "main", side_effect=fake_main),
                mock.patch.object(
                    recovery, "write_recovery_manifest", return_value=manifest
                ),
            )
            with common[0], common[1], common[2], common[3], common[4], common[5], common[6]:
                self.assertEqual(
                    recovery.run_generation(
                        "generate",
                        budget_cap_usd="99.05",
                        root=root,
                        allow_external_processing=True,
                    ),
                    0,
                )
            self.assertEqual(observed.count("--run-id"), 2)
            selected = [
                observed[index + 1]
                for index, value in enumerate(observed)
                if value == "--run-id"
            ]
            self.assertEqual(selected, [entry.provider_run_id for entry in recovery.ENTRIES])
            self.assertEqual(
                observed[observed.index("--veo31-concurrency") + 1], "2"
            )
            self.assertNotIn("--force", observed)
            self.assertNotIn("--model", observed)

            observed.clear()
            known = recovery.artifact_paths(recovery.ENTRIES[0], root)["run"]
            known.parent.mkdir(parents=True)
            known.write_text("{}", encoding="utf-8")
            resume_patches = (
                mock.patch.object(recovery, "preflight", return_value=state),
                mock.patch.object(recovery, "snapshot_old_receipts", return_value={}),
                mock.patch.object(recovery, "recovery_run_lock", self.noop_context),
                mock.patch.object(recovery, "configured_native", self.noop_context),
                mock.patch.object(recovery.native, "materialize", return_value=rows),
                mock.patch.object(recovery.native, "main", side_effect=fake_main),
                mock.patch.object(
                    recovery, "write_recovery_manifest", return_value=manifest
                ),
            )
            with (
                resume_patches[0],
                resume_patches[1],
                resume_patches[2],
                resume_patches[3],
                resume_patches[4],
                resume_patches[5],
                resume_patches[6],
            ):
                self.assertEqual(
                    recovery.run_generation(
                        "resume",
                        budget_cap_usd="99.05",
                        root=root,
                        allow_external_processing=True,
                    ),
                    0,
                )
            self.assertEqual(observed.count("--run-id"), 2)

    def test_recovery_manifest_is_merge_ready_only_with_two_bound_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_outputs = []
            records = {}
            old_evidence = {}
            for index, target in enumerate(recovery.TARGETS):
                paths = recovery.artifact_paths(target.entry, root)
                path = paths["video"]
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = f"video-{index}".encode()
                path.write_bytes(payload)
                request = {"model": recovery.MODEL_ID, "prompt": f"prompt-{index}"}
                request_sha256 = f"{index + 1}" * 64
                media = {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
                contract_check = {"conforms": True, "warnings": []}
                recovery.transport.atomic_write_json(
                    paths["prompt"],
                    {
                        "provider_run_id": target.entry.provider_run_id,
                        "supersedes_for_demo": target.supersedes_for_demo,
                        "recovery": recovery._recovery_binding(target),
                    },
                )
                recovery.transport.atomic_write_json(
                    paths["run"],
                    {
                        "provider_run_id": target.entry.provider_run_id,
                        "supersedes_for_demo": target.supersedes_for_demo,
                        "recovery": recovery._recovery_binding(target),
                        "status": "succeeded",
                        "provider_may_be_active": False,
                        "request": request,
                        "request_sha256": request_sha256,
                        "request_fingerprint_version": (
                            recovery.transport.REQUEST_FINGERPRINT_VERSION
                        ),
                        "media": media,
                        "contract_check": contract_check,
                        "error": None,
                    },
                )
                raw_outputs.append(
                    {
                        "lite_run_id": target.sample.planning_run_id,
                        "provider_run_id": target.entry.provider_run_id,
                        "sample_id": target.sample.sample_id,
                        "article_slug": target.sample.article_slug,
                        "source_path": target.sample.source_path,
                        "model_id": recovery.MODEL_ID,
                        "status": "succeeded",
                        "recorded_status": "succeeded",
                        "provider_may_be_active": False,
                        "prompt_path": paths["prompt"].relative_to(root).as_posix(),
                        "run_path": paths["run"].relative_to(root).as_posix(),
                        "video_path": path.relative_to(root).as_posix(),
                        "media": media,
                        "contract_check": contract_check,
                        "error": None,
                    }
                )
                records[target.sample.sample_id] = {
                    "planning_run_id": target.sample.planning_run_id,
                    "planning_result_path": "result.json",
                    "planning_result_sha256": "a" * 64,
                    "provenance": {"verified": True},
                    "scene_plan": "scene",
                    "positive_prompt": "prompt",
                    "negative_prompt": None,
                    "request": request,
                    "request_sha256": request_sha256,
                    "request_fingerprint_version": (
                        recovery.transport.REQUEST_FINGERPRINT_VERSION
                    ),
                }
                old_evidence[target.sample.sample_id] = {
                    "provider_run_id": target.supersedes_for_demo,
                    "status": "provider-filtered",
                }
            generation = {
                "ticket": recovery.TICKET,
                "batch_id": recovery.PROVIDER_BATCH_ID,
                "agent_id": recovery.AGENT_ID,
                "expected_outputs": 2,
                "outputs": raw_outputs,
            }
            state = {
                "route": {"model_id": recovery.MODEL_ID},
                "contract": {"contract_version": "current"},
                "accounting": recovery.accounting_document("99.05"),
                "records": records,
                "old_evidence": old_evidence,
            }
            document = recovery.recovery_document(
                generation, state, root=root, updated_at="fixed"
            )
            self.assertTrue(document["ready_for_merge"])
            self.assertEqual(document["accepted_output_count"], 2)
            self.assertEqual(document["merge_contract"]["replace_exactly"], 2)
            self.assertEqual(len(document["outputs"]), 2)
            for output, target in zip(document["outputs"], recovery.TARGETS):
                self.assertEqual(
                    output["supersedes_for_demo"], target.supersedes_for_demo
                )
                self.assertEqual(
                    output["selected_attempt"], "content-filter-recovery-v1"
                )
                self.assertTrue(output["recovery"]["request_changed"])

            invalid = copy.deepcopy(generation)
            invalid["outputs"][0]["model_id"] = "alibaba/wan-2.7"
            with self.assertRaisesRegex(recovery.RecoveryError, "identity changed"):
                recovery.recovery_document(invalid, state, root=root)

    def test_overlay_validator_does_not_require_canonical_filtered_rows(self) -> None:
        state = {
            "route": {"model_id": recovery.MODEL_ID},
            "contract": {"contract_version": recovery.EXPECTED_CONTRACT_VERSION},
            "accounting": recovery.accounting_document("99.05"),
            "records": {},
            "old_evidence": {},
        }
        generation = {"outputs": []}
        expected = {
            "updated_at": "2026-08-10T00:00:00Z",
            "ready_for_merge": True,
            "accepted_output_count": 2,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generation_path = root / recovery.GENERATION_MANIFEST_REL
            manifest_path = root / recovery.RECOVERY_MANIFEST_REL
            generation_path.parent.mkdir(parents=True)
            recovery.transport.atomic_write_json(generation_path, generation)
            recovery.transport.atomic_write_json(manifest_path, expected)
            with (
                mock.patch.object(recovery, "preflight", return_value=state) as preflight,
                mock.patch.object(
                    recovery,
                    "recovery_document",
                    return_value=expected,
                ) as document,
            ):
                actual = recovery.validate_recovery_for_canonical_overlay(root)
            self.assertEqual(actual, expected)
            preflight.assert_called_once_with(
                root,
                budget_cap_usd=recovery.REQUIRED_OPERATOR_BUDGET_CAP_USD,
                require_canonical_filtered=False,
            )
            document.assert_called_once_with(
                generation,
                state,
                root=root,
                updated_at="2026-08-10T00:00:00Z",
            )
            self.assertFalse((root / recovery.CANONICAL_MANIFEST_REL).exists())


if __name__ == "__main__":
    unittest.main()
