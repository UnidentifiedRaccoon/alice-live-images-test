import contextlib
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_case21_loop_experiment as experiment


class ClipmakerLiteCase21LoopExperimentTest(unittest.TestCase):
    def test_matrix_budget_and_stages_are_exact(self) -> None:
        self.assertEqual(
            [variant.variant_id for variant in experiment.VARIANTS],
            [
                "sync-cycle",
                "mirror-midpoint",
                "local-icons",
                "kinetic-compact",
                "staggered-wave",
                "simultaneous-microloops",
                "endpoint-first",
                "preservation-repair",
            ],
        )
        self.assertEqual(len(experiment.ENTRIES), 8)
        self.assertTrue(
            all(entry.model_id == "alibaba/wan-2.7" for entry in experiment.ENTRIES)
        )
        self.assertEqual(
            set(experiment.CANARY_VARIANT_IDS),
            {"sync-cycle", "local-icons", "endpoint-first"},
        )
        self.assertEqual(len(experiment.MAIN_VARIANT_IDS), 5)
        self.assertFalse(
            set(experiment.CANARY_VARIANT_IDS) & set(experiment.MAIN_VARIANT_IDS)
        )
        self.assertEqual(experiment.parse_budget("4.00"), Decimal("4.00"))
        self.assertEqual(experiment.parse_budget("5.00"), Decimal("5.00"))
        with self.assertRaisesRegex(experiment.LoopExperimentError, "below"):
            experiment.parse_budget("3.99")
        with self.assertRaisesRegex(experiment.LoopExperimentError, "exceeds"):
            experiment.parse_budget("5.01")

        cost = experiment.cost_document("5.00")
        self.assertEqual(cost["initial_reserved_usd"], 4.0)
        self.assertEqual(cost["contingency_slot_count"], 2)
        self.assertEqual(cost["maximum_provider_entries"], 10)
        self.assertEqual(cost["admitted_provider_entries"], 8)
        self.assertEqual(cost["contingency_entries_materialized"], 0)
        self.assertEqual(cost["maximum_submissions_per_entry"], 1)
        self.assertFalse(cost["automatic_paid_retries"])
        self.assertFalse(cost["provider_unit_costs_asserted"])

    def test_exact_route_and_all_verified_plans_build_two_identical_frames(self) -> None:
        route = experiment.validate_route()
        self.assertEqual(route["capacity"], 3)
        self.assertEqual(route["provider_key"], "atlas-cloud")
        self.assertEqual(route["paths"]["submit"], "/videos")

        seen_prompts: set[str] = set()
        with experiment.configured_native(experiment.ROOT):
            for entry in experiment.ENTRIES:
                with self.subTest(variant=entry.sample.variant_id):
                    variant = experiment._variant(entry)
                    job = experiment.load_experiment_job(entry, experiment.ROOT)
                    prompt = experiment.loop_provider_prompt(job)
                    request = experiment.native.provider_request_preview(
                        experiment.provider_sample(entry), prompt
                    )
                    experiment.assert_loop_request(entry, request, job)

                    self.assertTrue(job.provenance["verified"])
                    self.assertEqual(job.provenance["models"], [experiment.MODEL_ID])
                    self.assertEqual(job.result_sha256, variant.result_sha256)
                    self.assertEqual(prompt["last_frame_is_source"], True)
                    self.assertEqual(prompt["prompt_extend"], True)
                    self.assertEqual(
                        [frame["frame_type"] for frame in request["frame_images"]],
                        ["first_frame", "last_frame"],
                    )
                    self.assertEqual(
                        request["frame_images"][0]["image_url"],
                        request["frame_images"][1]["image_url"],
                    )
                    self.assertNotIn("loop", request)
                    self.assertEqual(
                        experiment.transport.REQUEST_FINGERPRINT_VERSION,
                        experiment.REQUEST_FINGERPRINT_VERSION,
                    )
                    seen_prompts.add(job.positive_prompt)

        self.assertEqual(len(seen_prompts), 8)

    def test_artifacts_explicitly_mark_noncanonical_transport_and_bind_inventory(self) -> None:
        with experiment.configured_native(experiment.ROOT):
            entry = experiment.ENTRIES[0]
            job = experiment.native.load_lite_job(entry, experiment.ROOT)
            prompt_artifact = experiment.native.prompt_artifact(job)
            run = experiment.native.initial_run(
                job, experiment.artifact_paths(entry, experiment.ROOT), experiment.ROOT
            )

        for document in (prompt_artifact, run):
            marker = document["provider_transport_experiment"]
            self.assertEqual(marker["profile"], "non-canonical-loop-closure")
            self.assertTrue(marker["canonical_lite_planning"])
            self.assertFalse(marker["canonical_lite_provider_runtime"])
            self.assertTrue(marker["last_frame_is_source"])

        inventory = experiment.inventory_document("5.00", experiment.ROOT)
        self.assertEqual(inventory["expected_outputs"], 8)
        self.assertEqual(len(inventory["entries"]), 8)
        self.assertEqual(
            [row["stage"] for row in inventory["entries"]].count("canary"), 3
        )
        self.assertEqual(
            [row["stage"] for row in inventory["entries"]].count("main"), 5
        )
        self.assertTrue(
            all(
                row["first_frame_url"] == row["last_frame_url"] == experiment.SOURCE_URL
                for row in inventory["entries"]
            )
        )
        self.assertTrue(all(row["request_sha256"] for row in inventory["entries"]))
        self.assertTrue(
            all(
                row["request_fingerprint_version"] == 2
                for row in inventory["entries"]
            )
        )
        self.assertEqual(set(inventory["controls"]), set(experiment.CONTROL_PATHS))
        self.assertTrue(
            all(record["sha256"] for record in inventory["controls"].values())
        )

    def test_configured_native_restores_all_overrides(self) -> None:
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
            "provider_prompt",
            "prompt_artifact",
            "initial_run",
            "matrix",
            "load_lite_job",
        )
        before = {name: getattr(experiment.native, name) for name in names}
        with experiment.configured_native(experiment.ROOT):
            self.assertEqual(experiment.native.MODEL_IDS, (experiment.MODEL_ID,))
            self.assertEqual(experiment.native.matrix(), experiment.ENTRIES)
            self.assertIs(experiment.native.provider_prompt, experiment.loop_provider_prompt)
        for name, value in before.items():
            with self.subTest(binding=name):
                if callable(value):
                    self.assertIs(getattr(experiment.native, name), value)
                else:
                    self.assertEqual(getattr(experiment.native, name), value)

    def test_inventory_is_immutable_and_uses_runtime_control_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = {"schema_version": 1, "controls": {"old": "snapshot"}}
            with mock.patch.object(experiment, "inventory_document", return_value=frozen):
                self.assertEqual(experiment.write_inventory("5.00", root), frozen)
                self.assertEqual(experiment.write_inventory("5.00", root), frozen)
            path = root / experiment.INVENTORY_PATH
            before = path.read_bytes()
            with mock.patch.object(
                experiment,
                "inventory_document",
                return_value={"schema_version": 1, "controls": {"old": "changed"}},
            ):
                with self.assertRaisesRegex(
                    experiment.LoopExperimentError, "Immutable loop inventory differs"
                ):
                    experiment.write_inventory("5.00", root)
            self.assertEqual(path.read_bytes(), before)

    @staticmethod
    @contextlib.contextmanager
    def _noop_context(*args, **kwargs):
        yield

    def _gate_fixture(self, root: Path, statuses: dict[str, tuple[str, str | None]]) -> None:
        request = {"exact": "loop-request"}
        path_by_variant = {}
        for variant_id in experiment.CANARY_VARIANT_IDS:
            base = root / variant_id
            base.mkdir(parents=True)
            run_path = base / "04.run.json"
            video_path = base / "04.mp4"
            status, error = statuses[variant_id]
            run_path.write_text(
                json.dumps(
                    {
                        "status": status,
                        "error": error,
                        "provider_job_id": "job-id" if status == "submitted" else None,
                        "request": request,
                        "request_sha256": "fp",
                        "request_fingerprint_version": 2,
                    }
                ),
                encoding="utf-8",
            )
            if status in {"succeeded", "verification-failed"}:
                video_path.write_bytes(b"mp4")
            path_by_variant[variant_id] = {
                "run": run_path,
                "video": video_path,
                "prompt": base / "04.prompt.json",
                "directory": base,
            }

        def fake_paths(entry, workspace=root):
            return path_by_variant[entry.sample.variant_id]

        patches = (
            mock.patch.object(experiment, "configured_native", self._noop_context),
            mock.patch.object(experiment, "artifact_paths", side_effect=fake_paths),
            mock.patch.object(experiment, "load_experiment_job", return_value=object()),
            mock.patch.object(experiment, "provider_sample", return_value={"sample": True}),
            mock.patch.object(experiment, "loop_provider_prompt", return_value={"prompt": True}),
            mock.patch.object(experiment.native, "provider_request_preview", return_value=request),
            mock.patch.object(experiment, "assert_loop_request"),
            mock.patch.object(experiment.transport, "request_fingerprint", return_value="fp"),
        )
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            experiment._canary_gate(root)

    def test_canary_gate_allows_one_mp4_plus_non_schema_terminal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._gate_fixture(
                root,
                {
                    "sync-cycle": ("verification-failed", None),
                    "local-icons": ("submitted", "content download failed after 3 attempts"),
                    "endpoint-first": ("provider-failed", "job expired upstream"),
                },
            )

    def test_canary_gate_blocks_last_frame_rejection_and_zero_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(
                experiment.LoopExperimentError, "rejected the loop request schema"
            ):
                self._gate_fixture(
                    root,
                    {
                        "sync-cycle": (
                            "provider-failed",
                            "validation: unsupported last_frame in frame_images",
                        ),
                        "local-icons": ("provider-failed", "job expired"),
                        "endpoint-first": ("provider-failed", "job expired"),
                    },
                )

    def test_generation_is_staged_filtered_and_requires_external_flag(self) -> None:
        with self.assertRaisesRegex(
            experiment.LoopExperimentError, "requires --allow-external-processing"
        ):
            with mock.patch.object(experiment, "_validate_inventory"):
                experiment.run_generation(
                    "canary",
                    "5.00",
                    root=experiment.ROOT,
                    dry_run=False,
                    allow_external_processing=False,
                )

        observed: list[list[str]] = []

        def fake_main(argv, root):
            observed.append(list(argv))
            return 0

        with (
            mock.patch.object(experiment, "_validate_inventory"),
            mock.patch.object(experiment, "control_snapshots", return_value={"stable": {}}),
            mock.patch.object(experiment, "configured_native", self._noop_context),
            mock.patch.object(experiment.native, "main", side_effect=fake_main),
            mock.patch.object(experiment, "write_experiment_manifest"),
            mock.patch.object(experiment, "_canary_gate") as gate,
        ):
            self.assertEqual(
                experiment.run_generation(
                    "canary", "5.00", root=experiment.ROOT, dry_run=True
                ),
                0,
            )
            gate.assert_not_called()
            self.assertEqual(
                experiment.run_generation(
                    "main", "5.00", root=experiment.ROOT, dry_run=True
                ),
                0,
            )
            gate.assert_called_once_with(experiment.ROOT)

        canary_args, main_args = observed
        self.assertEqual(canary_args.count("--run-id"), 3)
        self.assertEqual(main_args.count("--run-id"), 5)
        self.assertEqual(
            canary_args[canary_args.index("--wan27-concurrency") + 1], "3"
        )
        for argv in observed:
            self.assertIn("--dry-run", argv)
            self.assertNotIn("--force", argv)
            self.assertNotIn("--model", argv)


if __name__ == "__main__":
    unittest.main()
