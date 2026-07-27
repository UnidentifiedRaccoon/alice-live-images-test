#!/usr/bin/env python3
"""Network-free tests for the PROMOPAGES-9930 Wan 2.2 add-on."""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_promopages_9930_wan22_pipeline as pipeline


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
    previous = {name: getattr(pipeline.native, name) for name in names}
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(pipeline.native, name, value)


class Promopages9930Wan22PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.articles, cls.sources = pipeline.discover(pipeline.ROOT)

    def test_frozen_selection_and_namespaces_are_exact(self) -> None:
        self.assertEqual(len(self.articles), 20)
        self.assertEqual(len(self.sources), 20)
        self.assertEqual(
            [source.image["image_id"] for source in self.sources],
            [
                "02",
                "02",
                "03",
                "03",
                "02",
                "02",
                "03",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "02",
                "03",
            ],
        )
        self.assertTrue(
            all(
                source.planning_run_id.startswith(pipeline.PLANNING_BATCH_ID)
                for source in self.sources
            )
        )
        self.assertNotEqual(pipeline.BATCH_ID, pipeline.ORIGINAL_BATCH_ID)
        self.assertNotEqual(
            pipeline.INVENTORY_MANIFEST_REL,
            pipeline.ORIGINAL_INVENTORY_REL,
        )

    def test_budget_reserves_only_remaining_six_dollars(self) -> None:
        cost = pipeline.cost_metadata()
        self.assertEqual(cost["original_20x2_estimate_usd"], 14.0)
        self.assertEqual(cost["wan22_addon_budget_reservation_usd"], 6.0)
        self.assertEqual(cost["hard_budget_cap_usd"], 20.0)
        self.assertEqual(cost["maximum_reserved_total_usd"], 20.0)
        self.assertEqual(cost["wan22_maximum_paid_submissions"], 21)
        self.assertEqual(cost["wan22_intentional_retry_allowance"], 1)
        self.assertFalse(cost["wan22_exact_usd_unit_cost_known"])
        self.assertFalse(cost["automatic_paid_retries"])

    def test_native_binding_is_singleton_legacy_route_with_capacity_one(self) -> None:
        with preserved_native_state():
            pipeline.configure_native(self.sources, pipeline.ROOT)
            self.assertEqual(pipeline.native.MODEL_IDS, (pipeline.native.WAN_MODEL_ID,))
            self.assertEqual(
                pipeline.native.PLANNING_MODEL_IDS,
                (pipeline.native.WAN_MODEL_ID,),
            )
            self.assertEqual(
                pipeline.native.PLANNING_BATCH_ID,
                pipeline.PLANNING_BATCH_ID,
            )
            self.assertIsNone(pipeline.native.WAN_SUBMIT_MODE)
            self.assertEqual(len(pipeline.native.matrix()), 20)
            route = pipeline.transport.route_for_model(pipeline.MODEL_ID)
            self.assertEqual(route["transport"], "gradio-legacy-queue")
            self.assertEqual(route["capacity"], 1)
            paths = pipeline.native.artifact_paths(
                pipeline.native.matrix()[0],
                pipeline.ROOT,
            )
            self.assertIn(pipeline.BATCH_ID, paths["video"].parts)
            self.assertEqual(paths["video"].parent.name, "wan-2.2")

    def test_prepare_passes_exactly_one_model_to_runner(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "ok", "")
        with (
            mock.patch.object(
                pipeline,
                "planning_state",
                side_effect=[None, "prepared"],
            ),
            mock.patch.object(
                pipeline.subprocess,
                "run",
                return_value=completed,
            ) as run,
        ):
            counts = pipeline.prepare_planning_runs(
                (self.sources[0],),
                root=pipeline.ROOT,
            )
        self.assertEqual(counts, {"verified": 0, "prepared": 1, "pending": 0})
        command = run.call_args.args[0]
        models = [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--model"
        ]
        self.assertEqual(models, [pipeline.MODEL_ID])
        self.assertEqual(
            command[command.index("--run-id") + 1],
            self.sources[0].planning_run_id,
        )

    def test_prepare_dry_run_never_invokes_runner(self) -> None:
        with (
            mock.patch.object(pipeline, "planning_state", return_value=None),
            mock.patch.object(pipeline.subprocess, "run") as run,
        ):
            counts = pipeline.prepare_planning_runs(
                (self.sources[0],),
                root=pipeline.ROOT,
                dry_run=True,
            )
        self.assertEqual(counts["pending"], 1)
        run.assert_not_called()

    def test_planning_state_is_safe_under_three_parallel_readers(self) -> None:
        original_models = pipeline.original.MODEL_IDS
        with ThreadPoolExecutor(max_workers=3) as executor:
            states = list(
                executor.map(
                    lambda source: pipeline.planning_state(source, pipeline.ROOT),
                    self.sources,
                )
            )
        self.assertTrue(all(state in {"prepared", "verified"} for state in states))
        self.assertEqual(pipeline.original.MODEL_IDS, original_models)

    def test_generation_uses_one_wan_slot_and_canary_provider_id(self) -> None:
        with (
            preserved_native_state(),
            mock.patch.object(pipeline.native, "main", return_value=0) as main,
        ):
            result = pipeline.run_generation(
                self.sources,
                root=pipeline.ROOT,
                timeout=30,
                poll_interval=1.0,
                dry_run=True,
                allow_external_processing=False,
                canary=True,
                fail_fast=True,
            )
            first_id = pipeline.native.matrix()[0].provider_run_id
        self.assertEqual(result, 0)
        argv = main.call_args.args[0]
        self.assertEqual(argv[argv.index("--wan22-concurrency") + 1], "1")
        self.assertEqual(argv[argv.index("--model") + 1], pipeline.MODEL_ID)
        self.assertEqual(argv[argv.index("--run-id") + 1], first_id)
        route = pipeline.transport.route_for_model(pipeline.MODEL_ID)
        self.assertEqual(
            argv[argv.index("--wan-base-url") + 1],
            route["default_base_url"],
        )
        self.assertEqual(
            argv[argv.index("--wan-stream-base-url") + 1],
            route["default_stream_base_url"],
        )
        self.assertIn("--dry-run", argv)
        self.assertIn("--fail-fast", argv)

    def test_full_real_generation_is_gated_on_conforming_canary(self) -> None:
        with (
            preserved_native_state(),
            mock.patch.object(pipeline, "_canary_is_conforming", return_value=False),
            mock.patch.object(pipeline.native, "main") as main,
            self.assertRaisesRegex(pipeline.PipelineError, "gated"),
        ):
            pipeline.run_generation(
                self.sources,
                root=pipeline.ROOT,
                timeout=30,
                poll_interval=1.0,
                dry_run=False,
                allow_external_processing=True,
                canary=False,
                fail_fast=False,
            )
        main.assert_not_called()

    def test_aggregate_merges_wan_first_without_mutating_component(self) -> None:
        component_path = pipeline.ROOT / pipeline.ORIGINAL_COMPONENT_REL
        if not component_path.is_file():
            component_path = pipeline.ROOT / pipeline.STABLE_MANIFEST_REL
        component = json.loads(
            component_path.read_text(encoding="utf-8")
        )
        original_bytes = copy.deepcopy(component)
        reference = next(
            output
            for output in json.loads(
                (pipeline.ROOT / "clipmaker-lite-test/manifest.json").read_text(
                    encoding="utf-8"
                )
            )["outputs"]
            if output["model_id"] == pipeline.native.WAN_MODEL_ID
            and output["status"] == "succeeded"
        )
        sidecar_articles = []
        sidecar_outputs = []
        for article in component["articles"]:
            old_image = article["images"][0]
            image = old_image["image"]
            wan = {
                **copy.deepcopy(reference),
                "article_slug": article["article_slug"],
                "image_id": image["image_id"],
                "source_path": image["source_path"],
                "sample_id": f"{article['article_slug']}-{image['image_id']}",
                "lite_run_id": (
                    f"{pipeline.PLANNING_BATCH_ID}-"
                    f"{article['article_slug']}-{image['image_id']}"
                ),
                "provider_run_id": (
                    f"{pipeline.BATCH_ID}-{article['article_slug']}-"
                    f"{image['image_id']}-wan-2-2"
                ),
            }
            sidecar_outputs.append(wan)
            sidecar_articles.append(
                {
                    "article_number": article["article_number"],
                    "article_slug": article["article_slug"],
                    "images": [
                        {
                            "image": copy.deepcopy(image),
                            "lite_planning": {"run_id": wan["lite_run_id"]},
                            "outputs": [wan],
                        }
                    ],
                }
            )
        sidecar = {
            "batch_id": pipeline.BATCH_ID,
            "models": [pipeline.MODEL_ID],
            "expected_outputs": 20,
            "accepted_output_count": 20,
            "conforming_output_count": 20,
            "articles": sidecar_articles,
            "outputs": sidecar_outputs,
        }
        aggregate = pipeline.aggregate_document(
            component,
            sidecar,
            root=pipeline.ROOT,
            updated_at="fixed",
        )
        self.assertEqual(component, original_bytes)
        self.assertEqual(aggregate["models"], list(pipeline.ALL_MODEL_IDS))
        self.assertEqual(aggregate["expected_outputs"], 60)
        self.assertEqual(aggregate["accepted_output_count"], 60)
        self.assertEqual(len(aggregate["outputs"]), 60)
        self.assertTrue(
            all(
                [output["model_id"] for output in article["images"][0]["outputs"]]
                == list(pipeline.ALL_MODEL_IDS)
                for article in aggregate["articles"]
            )
        )

    def test_original_component_is_preserved_byte_for_byte_and_tamper_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stable = root / pipeline.STABLE_MANIFEST_REL
            stable.parent.mkdir(parents=True)
            source = pipeline.ROOT / pipeline.ORIGINAL_COMPONENT_REL
            if not source.is_file():
                source = pipeline.ROOT / pipeline.STABLE_MANIFEST_REL
            stable.write_bytes(
                source.read_bytes()
            )
            component = pipeline.ensure_original_component(root)
            self.assertEqual(component["expected_outputs"], 40)
            component_path = root / pipeline.ORIGINAL_COMPONENT_REL
            self.assertEqual(
                pipeline.sha256_file(component_path),
                pipeline.ORIGINAL_STABLE_MANIFEST_SHA256,
            )
            component_path.write_bytes(component_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(pipeline.PipelineError, "bytes changed"):
                pipeline.ensure_original_component(root)


if __name__ == "__main__":
    unittest.main()
