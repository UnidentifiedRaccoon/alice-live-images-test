#!/usr/bin/env python3
"""Network-free tests for the PROMOPAGES-9930 20x2 orchestrator."""

from __future__ import annotations

import copy
import fcntl
import json
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_all_images_pipeline as pipeline


@contextmanager
def preserved_native_state():
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
    )
    original = {name: getattr(pipeline.native, name) for name in names}
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(pipeline.native, name, value)


class ClipmakerLiteAllImagesPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.articles, cls.sources = pipeline.discover(pipeline.ROOT)

    def test_inventory_selects_exactly_one_deterministic_new_image_per_article(self) -> None:
        self.assertEqual(len(self.articles), 20)
        self.assertEqual(len(self.sources), 20)
        self.assertEqual(
            len({source.image["source_path"] for source in self.sources}), 20
        )
        self.assertEqual(len({source.image["sha256"] for source in self.sources}), 20)
        self.assertEqual(
            sum(len(article.images) for article in self.articles), 20
        )
        self.assertEqual(
            [article.number for article in self.articles],
            [f"{number:02d}" for number in range(1, 21)],
        )
        self.assertNotIn(
            "21-maier-doctor-zolotoe-vremia",
            {article.slug for article in self.articles},
        )
        self.assertTrue(all(len(article.images) == 1 for article in self.articles))
        self.assertEqual(
            [(source.article_number, source.image["image_id"]) for source in self.sources],
            [
                ("01", "02"),
                ("02", "02"),
                ("03", "03"),
                ("04", "03"),
                ("05", "02"),
                ("06", "02"),
                ("07", "03"),
                ("08", "02"),
                ("09", "02"),
                ("10", "02"),
                ("11", "02"),
                ("12", "02"),
                ("13", "02"),
                ("14", "02"),
                ("15", "02"),
                ("16", "02"),
                ("17", "02"),
                ("18", "02"),
                ("19", "02"),
                ("20", "03"),
            ],
        )
        selected_paths = {
            article.selected_image["source_path"] for article in self.articles
        }
        source_paths = {source.image["source_path"] for source in self.sources}
        self.assertTrue(selected_paths.isdisjoint(source_paths))
        excluded_duplicates = {
            "PROMOPAGES-9857/articles/03-zov-resheniia-dlia-kuhni/02.jpeg",
            "PROMOPAGES-9857/articles/04-graceface-antivozrastnaia-syvorotka/02.png",
            "PROMOPAGES-9857/articles/07-aquadetrim-deficit-vitamina-d/02.jpeg",
            "PROMOPAGES-9857/articles/08-tochka-ooo-ili-ip/04.jpeg",
            "PROMOPAGES-9857/articles/14-miuz-modnye-sergi/04.jpeg",
            "PROMOPAGES-9857/articles/20-sravni-kreditnyi-reiting/02.jpeg",
        }
        self.assertTrue(excluded_duplicates.isdisjoint(source_paths))
        document = pipeline.inventory_document(self.articles, self.sources)
        self.assertEqual(document["article_count"], 20)
        self.assertEqual(document["image_count"], 20)
        self.assertEqual(document["expected_outputs"], 40)
        self.assertEqual(document["source_duplicate_row_count"], 6)
        self.assertEqual(document["cost"], pipeline.cost_metadata())

    def test_batch_namespace_and_final_manifest_are_isolated(self) -> None:
        self.assertEqual(
            pipeline.BATCH_ID,
            "promopages-9930-lite20-new-images-20260726-v2",
        )
        self.assertEqual(
            pipeline.FINAL_MANIFEST_REL,
            Path("clipmaker-lite-test/promopages-9930-manifest.json"),
        )
        self.assertNotEqual(pipeline.FINAL_MANIFEST_REL, pipeline.BASE_MANIFEST_REL)
        frozen_path = pipeline.ROOT / pipeline.FROZEN_FINAL_MANIFEST_REL
        self.assertEqual(
            pipeline.sha256_file(frozen_path),
            pipeline.FROZEN_FINAL_MANIFEST_SHA256,
        )
        frozen = pipeline.read_json(frozen_path)
        self.assertEqual(frozen["models"], list(pipeline.MODEL_IDS))
        self.assertEqual(frozen["expected_outputs"], pipeline.EXPECTED_OUTPUTS)
        self.assertEqual(len(frozen["outputs"]), pipeline.EXPECTED_OUTPUTS)
        self.assertIn(pipeline.BATCH_ID, pipeline.GENERATION_MANIFEST_REL.parts)

    def test_cost_envelope_stays_below_hard_cap_and_disables_paid_retries(self) -> None:
        cost = pipeline.cost_metadata()
        self.assertEqual(cost["base_estimate_usd"], 14.0)
        self.assertEqual(cost["hard_budget_cap_usd"], 20.0)
        self.assertEqual(cost["planned_paid_submissions"], 40)
        self.assertEqual(cost["maximum_paid_submissions"], 40)
        self.assertEqual(cost["maximum_estimated_cost_usd"], 14.0)
        self.assertLessEqual(
            cost["maximum_estimated_cost_usd"], cost["hard_budget_cap_usd"]
        )
        self.assertFalse(cost["automatic_paid_retries"])

    def test_native_bridge_is_bound_to_only_two_exact_models_and_40_rows(self) -> None:
        with preserved_native_state():
            pipeline.configure_native(self.sources, pipeline.ROOT)
            self.assertEqual(pipeline.native.MODEL_IDS, pipeline.MODEL_IDS)
            self.assertEqual(pipeline.native.PLANNING_MODEL_IDS, pipeline.MODEL_IDS)
            self.assertIsNone(pipeline.native.PLANNING_WORKSPACE)
            self.assertIsNone(pipeline.native.PLANNING_PROVENANCE_VERIFIER)
            self.assertEqual(
                pipeline.native.CONTRACT_PATH,
                pipeline.ROOT / pipeline.CONTRACT_REL,
            )
            self.assertNotIn(pipeline.native.WAN_MODEL_ID, pipeline.native.MODEL_IDS)
            matrix = pipeline.native.matrix()
            self.assertEqual(len(matrix), 40)
            self.assertEqual(
                {entry.model_id for entry in matrix}, set(pipeline.MODEL_IDS)
            )
            paths = pipeline.native.artifact_paths(matrix[0], pipeline.ROOT)
            self.assertIn(pipeline.BATCH_ID, paths["video"].parts)
            self.assertEqual(paths["video"].suffix, ".mp4")

    def test_prepare_invokes_runner_with_only_the_two_requested_models(self) -> None:
        source = self.sources[0]
        completed = subprocess.CompletedProcess([], 0, "ok", "")
        with (
            mock.patch.object(
                pipeline, "_planning_state", side_effect=[None, "prepared"]
            ),
            mock.patch.object(
                pipeline.subprocess, "run", return_value=completed
            ) as run,
        ):
            counts = pipeline.prepare_planning_runs(
                (source,), root=pipeline.ROOT, dry_run=False
            )
        self.assertEqual(counts, {"verified": 0, "prepared": 1, "pending": 0})
        command = run.call_args.args[0]
        models = [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--model"
        ]
        self.assertEqual(models, list(pipeline.MODEL_IDS))
        self.assertNotIn(pipeline.native.WAN_MODEL_ID, models)
        self.assertEqual(command[command.index("--image-id") + 1], source.image["image_id"])

    def test_prepare_dry_run_and_resume_make_no_runner_call(self) -> None:
        with (
            mock.patch.object(
                pipeline,
                "_planning_state",
                side_effect=[None, "verified"],
            ),
            mock.patch.object(pipeline.subprocess, "run") as run,
        ):
            first = pipeline.prepare_planning_runs(
                (self.sources[0],), root=pipeline.ROOT, dry_run=True
            )
            second = pipeline.prepare_planning_runs(
                (self.sources[1],), root=pipeline.ROOT, dry_run=False
            )
        self.assertEqual(first["pending"], 1)
        self.assertEqual(second["verified"], 1)
        run.assert_not_called()

    def test_planning_selection_is_intersection_and_rejects_unknown_values(self) -> None:
        article = self.sources[0].article_slug
        candidates = [
            source for source in self.sources if source.article_slug == article
        ]
        selected = pipeline.select_sources(
            self.sources,
            article_slugs=(article,),
            sample_ids=(candidates[-1].sample_id,),
        )
        self.assertEqual(selected, (candidates[-1],))
        with self.assertRaisesRegex(pipeline.PipelineError, "Unknown sample IDs"):
            pipeline.select_sources(self.sources, sample_ids=("missing",))

    def test_real_planning_requires_explicit_external_processing(self) -> None:
        with self.assertRaisesRegex(
            pipeline.PipelineError, "requires --allow-external-processing"
        ):
            pipeline.run_planning_runs(
                (self.sources[0],),
                root=pipeline.ROOT,
                concurrency=1,
                timeout=10,
                dry_run=False,
                allow_external_processing=False,
            )

    def test_generation_delegates_to_native_independent_3_plus_3_pools(self) -> None:
        with (
            preserved_native_state(),
            mock.patch.object(pipeline.native, "main", return_value=0) as native_main,
        ):
            result = pipeline.run_generation(
                self.sources,
                root=pipeline.ROOT,
                wan27_concurrency=3,
                veo31_concurrency=3,
                timeout=30,
                poll_interval=0.0,
                dry_run=True,
                allow_external_processing=False,
                fail_fast=False,
            )
        self.assertEqual(result, 0)
        argv, root = native_main.call_args.args
        self.assertIs(root, pipeline.ROOT)
        self.assertIn("--dry-run", argv)
        self.assertNotIn("--wan22-concurrency", argv)
        self.assertEqual(argv[argv.index("--wan27-concurrency") + 1], "3")
        self.assertEqual(argv[argv.index("--veo31-concurrency") + 1], "3")
        models = [
            argv[index + 1]
            for index, value in enumerate(argv)
            if value == "--model"
        ]
        self.assertEqual(models, list(pipeline.MODEL_IDS))

    def test_generation_rejects_wan22_and_real_calls_without_approval(self) -> None:
        with self.assertRaisesRegex(pipeline.PipelineError, "intentionally excluded"):
            pipeline.run_generation(
                self.sources,
                wan27_concurrency=3,
                veo31_concurrency=3,
                timeout=30,
                poll_interval=1.0,
                dry_run=True,
                allow_external_processing=False,
                fail_fast=False,
                models=(pipeline.native.WAN_MODEL_ID,),
            )
        with self.assertRaisesRegex(
            pipeline.PipelineError, "requires --allow-external-processing"
        ):
            pipeline.run_generation(
                self.sources,
                wan27_concurrency=3,
                veo31_concurrency=3,
                timeout=30,
                poll_interval=1.0,
                dry_run=False,
                allow_external_processing=False,
                fail_fast=False,
            )

    def test_real_generation_fails_fast_when_another_coordinator_holds_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory, preserved_native_state():
            root = Path(directory)
            inventory = root / pipeline.INVENTORY_MANIFEST_REL
            inventory.parent.mkdir(parents=True)
            inventory.write_text("{}\n", encoding="utf-8")
            with inventory.open("rb") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    with (
                        mock.patch.object(pipeline.native, "main") as native_main,
                        self.assertRaisesRegex(
                            pipeline.PipelineError,
                            "already holds the batch run lock",
                        ),
                    ):
                        pipeline.run_generation(
                            self.sources,
                            root=root,
                            wan27_concurrency=3,
                            veo31_concurrency=3,
                            timeout=30,
                            poll_interval=1.0,
                            dry_run=False,
                            allow_external_processing=True,
                            fail_fast=False,
                        )
                    native_main.assert_not_called()
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def test_final_schema_is_mergeable_by_article_image_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory, preserved_native_state():
            root = Path(directory)
            pipeline.configure_native(self.sources, root)
            generation_outputs = []
            for source in self.sources:
                for model_id in pipeline.MODEL_IDS:
                    entry = pipeline.native.Entry(source.sample, model_id)
                    generation_outputs.append(
                        {
                            "provider_run_id": entry.provider_run_id,
                            "source_path": source.image["source_path"],
                            "model_id": model_id,
                            "status": "planned",
                            "recorded_status": "planned",
                            "prompt_path": "prompt.json",
                            "run_path": "run.json",
                            "video_path": "video.mp4",
                            "media": None,
                            "contract_check": None,
                            "error": None,
                        }
                    )
            generation_path = root / pipeline.GENERATION_MANIFEST_REL
            generation_path.parent.mkdir(parents=True)
            generation_path.write_text(
                json.dumps({"outputs": generation_outputs}), encoding="utf-8"
            )

            def planning_record(source, _root):
                return (
                    {
                        "verified": True,
                        "agent_id": pipeline.AGENT_ID,
                        "models": list(pipeline.MODEL_IDS),
                        "source_image_sha256": source.image["sha256"],
                        "result_path": (
                            pipeline.ARTIFACT_NAMESPACE
                            / source.planning_run_id
                            / "result.json"
                        ).as_posix(),
                    },
                    {
                        "job_id": source.planning_run_id,
                        "analysis": {"structured_intent": {"primary_action": "move"}},
                        "models": [
                            {
                                "model_id": model_id,
                                "scene_plan": f"scene {model_id}",
                                "positive_prompt": f"prompt {model_id}",
                                "negative_prompt": None,
                            }
                            for model_id in pipeline.MODEL_IDS
                        ],
                    },
                )

            with (
                mock.patch.object(pipeline.native, "materialize"),
                mock.patch.object(
                    pipeline, "_planning_record", side_effect=planning_record
                ),
            ):
                document = pipeline.build_final_manifest(
                    self.articles, self.sources, root=root, updated_at="fixed"
                )

        self.assertEqual(
            document["manifest_role"],
            "one-new-image-per-article-extension",
        )
        self.assertEqual(document["article_count"], 20)
        self.assertEqual(document["image_count"], 20)
        self.assertEqual(document["expected_outputs"], 40)
        self.assertEqual(document["cost"], pipeline.cost_metadata())
        self.assertFalse(
            document["acceptance_policy"]["allow_contract_warnings"]
        )
        self.assertEqual(document["accepted_output_count"], 0)
        self.assertEqual(document["conforming_output_count"], 0)
        self.assertEqual(len(document["articles"]), 20)
        self.assertEqual(
            sum(len(article["images"]) for article in document["articles"]), 20
        )
        self.assertTrue(
            all(len(article["images"]) == 1 for article in document["articles"])
        )
        self.assertTrue(
            all(
                len(image["outputs"]) == 2
                for article in document["articles"]
                for image in article["images"]
            )
        )
        keys = {
            (output["article_slug"], output["image_id"], output["model_id"])
            for output in document["outputs"]
        }
        self.assertEqual(len(keys), 40)
        self.assertEqual(
            document["merge_contract"]["output_key"],
            ["article_slug", "image_id", "model_id"],
        )

    def _warning_output(self, root: Path) -> dict[str, object]:
        video = root / "raw.mp4"
        video.write_bytes(b"raw Wan 2.7 provider MP4")
        return {
            "provider_run_id": "wan27-warning",
            "model_id": pipeline.native.WAN_27_MODEL_ID,
            "status": "verification-failed",
            "video_path": "raw.mp4",
            "media": {"duration_seconds": 5.0, "has_audio": True},
            "contract_check": {
                "conforms": False,
                "warnings": ["audio", "resolution"],
            },
        }

    def test_contract_warning_policy_preserves_raw_wan27_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = self._warning_output(root)
            original = copy.deepcopy(output)
            strict = pipeline.final_output_acceptance_error(
                output, root=root, allow_contract_warnings=False
            )
            allowed = pipeline.final_output_acceptance_error(
                output, root=root, allow_contract_warnings=True
            )
        self.assertIn("warnings were not allowed", strict or "")
        self.assertIsNone(allowed)
        self.assertEqual(output, original)
        self.assertEqual(output["status"], "verification-failed")
        self.assertFalse(output["contract_check"]["conforms"])

    def test_acceptance_audit_separates_conforming_and_allowed_warning_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            warning = self._warning_output(root)
            conforming_video = root / "good.mp4"
            conforming_video.write_bytes(b"conforming Veo provider MP4")
            conforming = {
                "provider_run_id": "veo-good",
                "model_id": pipeline.native.VEO_31_MODEL_ID,
                "status": "succeeded",
                "video_path": "good.mp4",
                "media": {"duration_seconds": 4.0, "has_audio": False},
                "contract_check": {"conforms": True, "warnings": []},
            }
            strict = pipeline.output_acceptance_audit(
                (warning, conforming),
                root=root,
                allow_contract_warnings=False,
            )
            permissive = pipeline.output_acceptance_audit(
                (warning, conforming),
                root=root,
                allow_contract_warnings=True,
            )
        self.assertEqual(strict["conforming_output_count"], 1)
        self.assertEqual(strict["accepted_output_count"], 1)
        self.assertEqual(permissive["accepted_output_count"], 2)
        self.assertEqual(
            permissive["contract_warning_summary"],
            {
                "output_count": 1,
                "by_model": {pipeline.native.WAN_27_MODEL_ID: 1},
                "by_warning": {"audio": 1, "resolution": 1},
            },
        )

    def test_parser_exposes_dry_run_selection_and_warning_opt_in(self) -> None:
        parser = pipeline.build_parser()
        prepare = parser.parse_args(
            ["prepare-plans", "--dry-run", "--article", self.sources[0].article_slug]
        )
        self.assertTrue(prepare.dry_run)
        self.assertEqual(prepare.article, [self.sources[0].article_slug])
        generate = parser.parse_args(
            [
                "generate",
                "--dry-run",
                "--run-id",
                "one",
                "--model",
                pipeline.MODEL_IDS[0],
            ]
        )
        self.assertTrue(generate.dry_run)
        self.assertEqual(generate.run_id, ["one"])
        self.assertEqual(generate.model, [pipeline.MODEL_IDS[0]])
        self.assertFalse(
            parser.parse_args(["verify"]).allow_contract_warnings
        )
        self.assertTrue(
            parser.parse_args(
                ["verify", "--allow-contract-warnings"]
            ).allow_contract_warnings
        )
        with self.assertRaises(SystemExit):
            parser.parse_args(
                ["generate", "--model", pipeline.native.WAN_MODEL_ID]
            )


if __name__ == "__main__":
    unittest.main()
