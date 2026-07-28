import contextlib
import copy
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import clipmaker_lite_case21_smooth_experiment as experiment


class ClipmakerLiteCase21SmoothExperimentTest(unittest.TestCase):
    def make_job(self, entry=None, *, negative=None, result_sha256="a" * 64):
        entry = entry or experiment.ENTRIES[0]
        runtime = experiment.read_json(
            experiment.ROOT / experiment.case21.CONTRACT_PATH
        )["models"][experiment.MODEL_ID]["runtime"]
        return experiment.native.LiteJob(
            entry=entry,
            structured_intent={
                key: f"intent {key}"
                for key in experiment.runner.STRUCTURED_INTENT_KEYS
            },
            positive_prompt=f"smooth prompt for {entry.sample.variant_id}",
            negative_prompt=negative,
            result_path=f"artifacts/{entry.sample.variant_id}/result.json",
            result_sha256=result_sha256,
            provenance={"verified": True},
            runtime=runtime,
        )

    def test_matrix_negative_policies_and_budget_are_exact(self) -> None:
        self.assertEqual(
            [variant.variant_id for variant in experiment.VARIANTS],
            [
                "low-amplitude-continuous",
                "staggered-ease",
                "left-to-right-flow",
                "preservation-smooth-repair",
            ],
        )
        self.assertEqual(
            [variant.negative_policy for variant in experiment.VARIANTS],
            [
                "required-observed-repair",
                "must-be-null",
                "must-be-null",
                "required-observed-repair",
            ],
        )
        self.assertEqual(
            [variant.planning_run_id.rsplit("-", 1)[-1] for variant in experiment.VARIANTS],
            ["v3", "v4", "v3", "v3"],
        )
        self.assertEqual(
            [variant.result_sha256 for variant in experiment.VARIANTS],
            [
                "441894fee34c64eee91529f3f98039adf180f257092cc2207a69f7180440157e",
                "ac773559abba5386897ef830fbbf1ec186d3c58e3149d2b4f605c026bca7a5aa",
                "6ee108f3cfbeda317ecc861288ce5a6148049f87e2eb4807cf4b6ca995682f8b",
                "e5a115bb7aeaaee815f5656adde2144a6b0453e72e09128b91deadbfc3a71d3b",
            ],
        )
        self.assertEqual(len(experiment.ENTRIES), 4)
        self.assertTrue(
            all(entry.model_id == "alibaba/wan-2.7" for entry in experiment.ENTRIES)
        )
        self.assertEqual(experiment.parse_budget("2.00"), Decimal("2.00"))
        self.assertEqual(experiment.parse_budget("3.00"), Decimal("3.00"))
        with self.assertRaisesRegex(experiment.SmoothExperimentError, "below"):
            experiment.parse_budget("1.99")
        with self.assertRaisesRegex(experiment.SmoothExperimentError, "exceeds"):
            experiment.parse_budget("3.01")

        cost = experiment.cost_document("3.00")
        self.assertEqual(cost["initial_reserved_usd"], 2.0)
        self.assertEqual(cost["contingency_attempt_count"], 2)
        self.assertEqual(cost["contingency_reserved_usd"], 1.0)
        self.assertEqual(cost["maximum_provider_entries"], 6)
        self.assertEqual(cost["admitted_provider_entries"], 4)
        self.assertEqual(cost["contingency_entries_materialized"], 0)
        self.assertFalse(cost["automatic_paid_retries"])

    def test_request_is_exact_first_frame_only_non_loop_runtime(self) -> None:
        route = experiment.validate_route()
        self.assertEqual(route["capacity"], 3)
        entry = experiment.ENTRIES[0]
        job = self.make_job(entry)
        prompt = experiment.smooth_provider_prompt(job)
        request = experiment.native.provider_request_preview(
            experiment.provider_sample(entry), prompt
        )

        experiment.assert_smooth_request(entry, request, job)
        self.assertFalse(prompt["last_frame_is_source"])
        self.assertTrue(prompt["prompt_extend"])
        self.assertEqual(len(request["frame_images"]), 1)
        self.assertEqual(request["frame_images"][0]["frame_type"], "first_frame")
        self.assertNotIn("last_frame", request)
        self.assertNotIn("loop", request)
        self.assertEqual(
            request["provider"]["options"]["atlas-cloud"]["parameters"],
            {"prompt_extend": True},
        )

        with self.subTest("reject last frame"):
            invalid = copy.deepcopy(request)
            invalid["frame_images"].append(
                {
                    "type": "image_url",
                    "image_url": {"url": experiment.SOURCE_URL},
                    "frame_type": "last_frame",
                }
            )
            with self.assertRaisesRegex(
                experiment.SmoothExperimentError, "Non-exact smooth request"
            ):
                experiment.assert_smooth_request(entry, invalid, job)

        with self.subTest("reject loop key"):
            invalid = copy.deepcopy(request)
            invalid["loop"] = False
            with self.assertRaisesRegex(
                experiment.SmoothExperimentError, "Non-exact smooth request"
            ):
                experiment.assert_smooth_request(entry, invalid, job)

    def test_all_four_plans_have_verified_provenance_and_exact_negative_policy(self) -> None:
        expected_paths = [
            experiment.ROOT
            / experiment.case21.ARTIFACT_NAMESPACE
            / variant.planning_run_id
            / "result.json"
            for variant in experiment.VARIANTS
        ]
        if not all(path.is_file() for path in expected_paths):
            self.skipTest("accepted v3/v4 planning results are not materialized yet")
        for entry in experiment.ENTRIES:
            with self.subTest(variant=entry.sample.variant_id):
                variant = experiment._variant(entry)
                job = experiment.load_experiment_job(entry, experiment.ROOT)
                self.assertTrue(job.provenance["verified"])
                self.assertEqual(job.provenance["models"], [experiment.MODEL_ID])
                self.assertEqual(
                    job.result_sha256,
                    experiment.sha256_file(
                        experiment.ROOT
                        / experiment.case21.ARTIFACT_NAMESPACE
                        / variant.planning_run_id
                        / "result.json"
                    ),
                )
                self.assertEqual(job.runtime["frame_inputs"], ["first_frame"])
                self.assertLessEqual(len(job.positive_prompt), 480)
                if variant.negative_policy == "required-observed-repair":
                    self.assertIsInstance(job.negative_prompt, str)
                    self.assertTrue(job.negative_prompt)
                    self.assertLessEqual(len(job.negative_prompt), 500)
                else:
                    self.assertIsNone(job.negative_prompt)

    def test_transport_markers_are_canonical_and_non_loop(self) -> None:
        entry = experiment.ENTRIES[0]
        job = self.make_job(entry)
        with experiment.configured_native(experiment.ROOT):
            prompt_artifact = experiment.native.prompt_artifact(job)
            run = experiment.native.initial_run(
                job,
                experiment.artifact_paths(entry, experiment.ROOT),
                experiment.ROOT,
            )
        for document in (prompt_artifact, run):
            marker = document["provider_transport_experiment"]
            self.assertEqual(marker["profile"], "non-loop-smooth-motion")
            self.assertTrue(marker["canonical_lite_provider_runtime"])
            self.assertTrue(marker["first_frame_only"])
            self.assertFalse(marker["last_frame_is_source"])
            self.assertFalse(marker["loop"])

    def test_missing_planning_result_fails_closed(self) -> None:
        entry = experiment.ENTRIES[0]
        with mock.patch.object(
            experiment.runner,
            "provenance_summary",
            side_effect=RuntimeError("missing"),
        ):
            with self.assertRaisesRegex(
                experiment.SmoothExperimentError, "planning result is not ready"
            ):
                experiment.load_experiment_job(entry, experiment.ROOT)

    def test_changed_planning_result_digest_fails_closed(self) -> None:
        entry = experiment.ENTRIES[0]
        with mock.patch.object(experiment, "sha256_file", return_value="0" * 64):
            with self.assertRaisesRegex(
                experiment.SmoothExperimentError, "Planning result digest changed"
            ):
                experiment.load_experiment_job(entry, experiment.ROOT)

    @staticmethod
    @contextlib.contextmanager
    def noop_context(*args, **kwargs):
        yield

    def test_inventory_binds_four_dynamic_verified_results_and_controls(self) -> None:
        jobs = {
            entry: self.make_job(
                entry,
                negative=(
                    "preserve text and layout"
                    if entry.sample.variant_id == "preservation-smooth-repair"
                    else None
                ),
                result_sha256=f"{index + 1:064x}",
            )
            for index, entry in enumerate(experiment.ENTRIES)
        }
        source = SimpleNamespace(
            provider_source_url=experiment.SOURCE_URL,
            image={
                "source_image_id": experiment.case21.EXPECTED_SOURCE_IMAGE_ID,
                "sha256": experiment.SOURCE_SHA256,
            },
        )
        controls = {"loop_experiment": {"path": "old", "sha256": "frozen"}}
        with (
            mock.patch.object(experiment, "configured_native", self.noop_context),
            mock.patch.object(
                experiment,
                "load_experiment_job",
                side_effect=lambda entry, root: jobs[entry],
            ),
            mock.patch.object(experiment.case21, "discover_case", return_value=source),
            mock.patch.object(experiment.case21, "validate_public_orig_url"),
            mock.patch.object(experiment, "control_snapshots", return_value=controls),
        ):
            inventory = experiment.inventory_document("3.00", experiment.ROOT)

        self.assertEqual(inventory["expected_outputs"], 4)
        self.assertEqual(len(inventory["entries"]), 4)
        self.assertEqual(inventory["controls"], controls)
        self.assertTrue(
            all(row["frame_inputs"] == ["first_frame"] for row in inventory["entries"])
        )
        self.assertEqual(
            [row["planning_result_sha256"] for row in inventory["entries"]],
            [jobs[entry].result_sha256 for entry in experiment.ENTRIES],
        )
        self.assertTrue(all(row["request_sha256"] for row in inventory["entries"]))
        self.assertTrue(
            all(row["request_fingerprint_version"] == 2 for row in inventory["entries"])
        )

    def test_inventory_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen = {"schema_version": 1, "entries": ["frozen"]}
            with mock.patch.object(experiment, "inventory_document", return_value=frozen):
                self.assertEqual(experiment.write_inventory("3.00", root), frozen)
                self.assertEqual(experiment.write_inventory("3.00", root), frozen)
            path = root / experiment.INVENTORY_PATH
            before = path.read_bytes()
            with mock.patch.object(
                experiment,
                "inventory_document",
                return_value={"schema_version": 1, "entries": ["changed"]},
            ):
                with self.assertRaisesRegex(
                    experiment.SmoothExperimentError, "Immutable smooth inventory differs"
                ):
                    experiment.write_inventory("3.00", root)
            self.assertEqual(path.read_bytes(), before)

    def test_configured_native_restores_overrides(self) -> None:
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
        before = {name: getattr(experiment.native, name) for name in names}
        with experiment.configured_native(experiment.ROOT):
            self.assertEqual(experiment.native.MODEL_IDS, (experiment.MODEL_ID,))
            self.assertEqual(experiment.native.matrix(), experiment.ENTRIES)
            self.assertIs(
                experiment.native.provider_prompt, experiment.smooth_provider_prompt
            )
        for name, value in before.items():
            if callable(value):
                self.assertIs(getattr(experiment.native, name), value)
            else:
                self.assertEqual(getattr(experiment.native, name), value)

    def test_generation_requires_external_flag_and_filters_four_initial_entries(self) -> None:
        with mock.patch.object(experiment, "_validate_inventory"):
            with self.assertRaisesRegex(
                experiment.SmoothExperimentError,
                "requires --allow-external-processing",
            ):
                experiment.run_generation(
                    "3.00",
                    root=experiment.ROOT,
                    dry_run=False,
                    allow_external_processing=False,
                )

        observed = []

        def fake_main(argv, root):
            observed.extend(argv)
            return 0

        with (
            mock.patch.object(experiment, "_validate_inventory"),
            mock.patch.object(
                experiment,
                "control_snapshots",
                return_value={"old": {"sha256": "stable"}},
            ),
            mock.patch.object(experiment, "configured_native", self.noop_context),
            mock.patch.object(experiment.native, "main", side_effect=fake_main),
            mock.patch.object(experiment, "write_experiment_manifest"),
        ):
            self.assertEqual(
                experiment.run_generation(
                    "3.00", root=experiment.ROOT, dry_run=True
                ),
                0,
            )

        self.assertEqual(observed.count("--run-id"), 4)
        self.assertEqual(observed[observed.index("--wan27-concurrency") + 1], "3")
        self.assertIn("--dry-run", observed)
        self.assertNotIn("--force", observed)
        self.assertNotIn("--model", observed)


if __name__ == "__main__":
    unittest.main()
