#!/usr/bin/env python3
"""Network-free tests for the isolated Clipmaker Lite case-21 pipeline."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_case21_pipeline as pipeline


class ClipmakerLiteCase21PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = pipeline.discover_case(pipeline.ROOT)

    def _copy_primary_attempts(self, root: Path) -> None:
        planning_source = (
            pipeline.ROOT
            / pipeline.ARTIFACT_NAMESPACE
            / pipeline.PLANNING_RUN_ID
            / "result.json"
        )
        planning_target = (
            root
            / pipeline.ARTIFACT_NAMESPACE
            / pipeline.PLANNING_RUN_ID
            / "result.json"
        )
        planning_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(planning_source, planning_target)
        manifest_target = root / pipeline.GENERATION_MANIFEST_PATH
        manifest_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pipeline.ROOT / pipeline.GENERATION_MANIFEST_PATH, manifest_target)
        for model_id in pipeline.MODEL_IDS:
            paths = pipeline._manifest_artifact_paths(pipeline.BATCH_ROOT, model_id)
            for key in ("prompt", "run", "video", "review"):
                source = pipeline.ROOT / paths[key]
                if not source.is_file():
                    continue
                target = root / paths[key]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    def _write_retry_successes(self, root: Path) -> dict:
        result_path = (
            root
            / pipeline.ARTIFACT_NAMESPACE
            / pipeline.PLANNING_RUN_ID
            / "result.json"
        )
        result_sha = pipeline.sha256_file(result_path)
        planning_result = pipeline.read_json(result_path)
        planning_by_model = {
            item["model_id"]: item for item in planning_result["models"]
        }
        structured_intent = planning_result["analysis"]["structured_intent"]
        outputs = []
        for index, model_id in enumerate(pipeline.RETRY_MODEL_IDS, start=1):
            paths = pipeline._manifest_artifact_paths(
                pipeline.RETRY_BATCH_ROOT,
                model_id,
            )
            prompt_path = root / paths["prompt"]
            run_path = root / paths["run"]
            video_path = root / paths["video"]
            review_path = root / paths["review"]
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            planning_model = planning_by_model[model_id]
            prompt_receipt = {
                "schema_version": 2,
                "ticket": pipeline.TICKET,
                "batch_id": pipeline.RETRY_PROVIDER_BATCH_ID,
                "agent_id": pipeline.AGENT_ID,
                "lite_run_id": pipeline.PLANNING_RUN_ID,
                "provider_run_id": pipeline._provider_run_id(
                    pipeline.RETRY_PROVIDER_BATCH_ID,
                    model_id,
                ),
                "model_id": model_id,
                "source": {
                    "path": self.source.image["source_path"],
                    "sha256": self.source.image["sha256"],
                    "width": self.source.image["width"],
                    "height": self.source.image["height"],
                },
                "structured_intent": structured_intent,
                "prompt": {
                    "positive": planning_model["positive_prompt"],
                    "negative": planning_model["negative_prompt"],
                },
                "runtime": planning_model["runtime"],
                "lite_result": {"sha256": result_sha},
            }
            prompt_path.write_text(json.dumps(prompt_receipt), encoding="utf-8")
            payload = f"network-free-retry-video-{index}".encode("ascii")
            video_path.write_bytes(payload)
            media = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
            provider_run_id = pipeline._provider_run_id(
                pipeline.RETRY_PROVIDER_BATCH_ID,
                model_id,
            )
            request = {
                "model": model_id,
                "prompt": planning_model["positive_prompt"],
                "frame_images": [
                    {
                        "type": "image_url",
                        "image_url": {"url": pipeline.EXPECTED_ORIG_URL},
                        "frame_type": "first_frame",
                    }
                ],
            }
            sample = {
                "sample_id": pipeline.SAMPLE_ID,
                "article_slug": pipeline.ARTICLE_SLUG,
                "image_id": pipeline.IMAGE_ID,
                "image_number": pipeline.IMAGE_ID,
                "source_path": self.source.image["source_path"],
                "source_url": pipeline.EXPECTED_ORIG_URL,
                "sha256": self.source.image["sha256"],
                "width": self.source.image["width"],
                "height": self.source.image["height"],
            }
            run = {
                "schema_version": 1,
                "ticket": pipeline.TICKET,
                "batch_id": pipeline.RETRY_PROVIDER_BATCH_ID,
                "agent_id": pipeline.AGENT_ID,
                "lite_run_id": pipeline.PLANNING_RUN_ID,
                "provider_run_id": provider_run_id,
                "lite_result_sha256": result_sha,
                "sample_id": pipeline.SAMPLE_ID,
                "image_id": pipeline.IMAGE_ID,
                "model_id": model_id,
                "status": "succeeded",
                "request": request,
                "request_sha256": pipeline.transport.request_fingerprint(
                    request,
                    sample,
                ),
                "request_fingerprint_version": (
                    pipeline.transport.REQUEST_FINGERPRINT_VERSION
                ),
                "provider_job_id": f"job-{index}",
                "submitted_at": "2026-07-27T15:00:00Z",
                "completed_at": "2026-07-27T15:01:00Z",
                "provider_may_be_active": False,
                "media": media,
                "contract_check": {"conforms": True, "warnings": []},
                "error": None,
            }
            run_path.write_text(json.dumps(run), encoding="utf-8")
            output = {
                "lite_run_id": pipeline.PLANNING_RUN_ID,
                "provider_run_id": provider_run_id,
                "sample_id": pipeline.SAMPLE_ID,
                "article_slug": pipeline.ARTICLE_SLUG,
                "source_path": self.source.image["source_path"],
                "model_id": model_id,
                "status": "succeeded",
                "recorded_status": "succeeded",
                "provider_may_be_active": False,
                "prompt_path": paths["prompt"].as_posix(),
                "run_path": paths["run"].as_posix(),
                "video_path": paths["video"].as_posix(),
                "media": media,
                "contract_check": {"conforms": True, "warnings": []},
                "error": None,
            }
            outputs.append(output)
            review = {
                "schema_version": 1,
                "ticket": pipeline.TICKET,
                "model_id": model_id,
                "provider_run_id": provider_run_id,
                "lite_run_id": pipeline.PLANNING_RUN_ID,
                "source": {
                    "path": self.source.image["source_path"],
                    "sha256": self.source.image["sha256"],
                },
                "artifact": {
                    "path": paths["video"].as_posix(),
                    "sha256": media["sha256"],
                },
                "review_method": {
                    "source_comparison": "Compared source and decoded frames.",
                    "technical_verification": "Verified the media receipt.",
                },
                "observations": {
                    "requested_motion": "The purple aura contracts and fades.",
                    "camera": "Camera remains fixed.",
                    "stable_elements": ["Text and diagram topology"],
                    "invariant_failures": [],
                },
                "verdict": {
                    "status": "fidelity-passed",
                    "summary": "Requested motion and invariants are preserved.",
                },
            }
            review_path.write_text(json.dumps(review), encoding="utf-8")
        generation = {
            "schema_version": 1,
            "ticket": pipeline.TICKET,
            "batch_id": pipeline.RETRY_PROVIDER_BATCH_ID,
            "agent_id": pipeline.AGENT_ID,
            "updated_at": "2026-07-27T15:01:00Z",
            "expected_outputs": 2,
            "summary": {"succeeded": 2},
            "conforming_outputs": 2,
            "outputs": outputs,
        }
        path = root / pipeline.RETRY_GENERATION_MANIFEST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(generation), encoding="utf-8")
        return generation

    def test_discovers_all_materials_and_binds_exact_image_04(self) -> None:
        source = self.source
        self.assertEqual(source.article_number, "21")
        self.assertEqual(source.article_slug, pipeline.ARTICLE_SLUG)
        self.assertEqual(len(source.images), 8)
        self.assertEqual(
            [image["image_id"] for image in source.images],
            ["01", "02", "03", "04", "05", "06", "07", "08"],
        )
        self.assertEqual(source.image["image_id"], "04")
        self.assertEqual(source.image["source_block_index"], 33)
        self.assertEqual(source.image["role"], "article_image")
        self.assertEqual(source.image["sha256"], pipeline.EXPECTED_SOURCE_SHA256)
        self.assertEqual(source.context_sha256, pipeline.EXPECTED_CONTEXT_SHA256)
        self.assertEqual(source.provider_source_url, pipeline.EXPECTED_ORIG_URL)

    def test_provider_url_is_exact_trusted_mds_orig_bound_to_image_04(self) -> None:
        self.assertEqual(
            pipeline.validate_public_orig_url(
                pipeline.EXPECTED_ORIG_URL,
                source_image_id=pipeline.EXPECTED_SOURCE_IMAGE_ID,
                source_sha256=pipeline.EXPECTED_SOURCE_SHA256,
            ),
            pipeline.EXPECTED_ORIG_URL,
        )
        invalid_values = (
            pipeline.EXPECTED_ORIG_URL.replace(
                "avatars.mds.yandex.net", "evil.example"
            ),
            pipeline.EXPECTED_ORIG_URL + "?redirect=1",
            pipeline.EXPECTED_ORIG_URL.removesuffix("/orig") + "/scale_1200",
        )
        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(
                pipeline.PipelineError
            ):
                pipeline.validate_public_orig_url(
                    value,
                    source_image_id=pipeline.EXPECTED_SOURCE_IMAGE_ID,
                    source_sha256=pipeline.EXPECTED_SOURCE_SHA256,
                )
        with self.assertRaisesRegex(pipeline.PipelineError, "not bound"):
            pipeline.validate_public_orig_url(
                pipeline.EXPECTED_ORIG_URL,
                source_image_id="wrong",
                source_sha256=pipeline.EXPECTED_SOURCE_SHA256,
            )

    def test_inventory_is_separate_from_historical_manifests(self) -> None:
        document = pipeline.inventory_document(self.source)
        encoded = json.dumps(document, ensure_ascii=False)
        self.assertEqual(document["case_number"], "21")
        self.assertEqual(document["expected_outputs"], 3)
        self.assertEqual(document["planning_run_id"], pipeline.PLANNING_RUN_ID)
        self.assertEqual(document["models"], list(pipeline.MODEL_IDS))
        self.assertEqual(document["article"]["collected_image_count"], 8)
        self.assertNotIn("clipmaker-lite-test/manifest.json", encoded)
        self.assertNotIn("promopages-9930-manifest.json", encoded)

    def test_source_or_context_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_target = root / pipeline.SOURCE_MANIFEST_PATH
            manifest_target.parent.mkdir(parents=True)
            shutil.copy2(pipeline.ROOT / pipeline.SOURCE_MANIFEST_PATH, manifest_target)
            context_target = root / pipeline.CONTEXT_PATH
            context_target.parent.mkdir(parents=True)
            shutil.copy2(pipeline.ROOT / pipeline.CONTEXT_PATH, context_target)
            for image in self.source.images:
                source_path = pipeline.ROOT / image["source_path"]
                target = root / image["source_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target)

            self.assertEqual(pipeline.discover_case(root).image["image_id"], "04")
            document = json.loads(context_target.read_text(encoding="utf-8"))
            document["lead"] += " mutation"
            context_target.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaisesRegex(pipeline.PipelineError, "context digest"):
                pipeline.discover_case(root)

    def test_prepare_command_is_one_combined_three_model_job(self) -> None:
        self.assertEqual(
            pipeline.PLANNING_RUN_ID,
            "promopages-9930-case21-maier-20260727-v4",
        )
        command = pipeline.planning_prepare_command(pipeline.ROOT)
        self.assertEqual(
            command[command.index("--run-id") + 1], pipeline.PLANNING_RUN_ID
        )
        self.assertEqual(command[command.index("--image-id") + 1], "04")
        models = [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--model"
        ]
        self.assertEqual(models, list(pipeline.MODEL_IDS))
        self.assertNotIn("promopages-9930-case21-maier-20260727-v1-wan22", command)
        self.assertNotIn("promopages-9930-case21-maier-20260727-v1-wan27", command)
        self.assertNotIn("promopages-9930-case21-maier-20260727-v1-veo31", command)

    def test_prepare_dry_run_does_not_invoke_runner(self) -> None:
        with (
            mock.patch.object(pipeline, "planning_state", return_value=None),
            mock.patch.object(pipeline.subprocess, "run") as run,
        ):
            state = pipeline.prepare_planning_run(
                self.source, root=pipeline.ROOT, dry_run=True
            )
        self.assertEqual(state, "would-prepare")
        run.assert_not_called()

    def test_planning_external_processing_gate_precedes_runner(self) -> None:
        with (
            mock.patch.object(pipeline, "planning_state", return_value=None),
            mock.patch.object(pipeline, "prepare_planning_run") as prepare,
            mock.patch.object(pipeline.subprocess, "run") as run,
            self.assertRaisesRegex(pipeline.PipelineError, "requires --allow"),
        ):
            pipeline.run_planning(
                self.source,
                root=pipeline.ROOT,
                dry_run=False,
                allow_external_processing=False,
            )
        prepare.assert_not_called()
        run.assert_not_called()

    def test_exact_routes_have_independent_1_3_3_capacities(self) -> None:
        routes = pipeline.validate_routes()
        self.assertEqual(
            {model_id: routes[model_id]["capacity"] for model_id in pipeline.MODEL_IDS},
            pipeline.ROUTE_CAPACITIES,
        )
        self.assertEqual(routes["alibaba/wan-2.2"]["transport"], "gradio-legacy-queue")
        self.assertEqual(routes["alibaba/wan-2.7"]["provider_key"], "atlas-cloud")
        self.assertEqual(routes["google/veo-3.1-lite"]["provider_key"], "google-vertex")
        policy = pipeline.transport.GENERATION_ROUTE_DOCUMENT["policy"]
        self.assertFalse(policy["automatic_fallback"])
        self.assertFalse(policy["normal_run_discovery"])

    def test_native_bridge_has_one_source_three_models_and_combined_plan(self) -> None:
        original = {
            "BATCH_ID": pipeline.native.BATCH_ID,
            "MODEL_IDS": pipeline.native.MODEL_IDS,
            "SAMPLES": pipeline.native.SAMPLES,
            "artifact_paths": pipeline.native.artifact_paths,
        }
        with pipeline.configured_native(self.source, pipeline.ROOT):
            matrix = pipeline.native.matrix()
            self.assertEqual(len(matrix), 3)
            self.assertEqual(
                [entry.model_id for entry in matrix], list(pipeline.MODEL_IDS)
            )
            self.assertTrue(
                all(entry.planning_run_id == pipeline.PLANNING_RUN_ID for entry in matrix)
            )
            self.assertTrue(
                all(
                    pipeline.PROVIDER_BATCH_ID in entry.provider_run_id
                    for entry in matrix
                )
            )
            self.assertIsNone(pipeline.native.WAN_SUBMIT_MODE)
            self.assertEqual(
                pipeline.native.MANIFEST_PATH, pipeline.GENERATION_MANIFEST_PATH
            )
        self.assertEqual(pipeline.native.BATCH_ID, original["BATCH_ID"])
        self.assertEqual(pipeline.native.MODEL_IDS, original["MODEL_IDS"])
        self.assertEqual(pipeline.native.SAMPLES, original["SAMPLES"])
        self.assertIs(pipeline.native.artifact_paths, original["artifact_paths"])

    def test_batch_lock_rejects_a_second_real_coordinator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            inventory = Path(temporary) / "inventory.json"
            inventory.write_text("{}", encoding="utf-8")
            with pipeline.batch_run_lock(inventory):
                with self.assertRaisesRegex(
                    pipeline.PipelineError, "another case-21 coordinator"
                ):
                    with pipeline.batch_run_lock(inventory):
                        self.fail("a second coordinator acquired the batch lock")

    def test_budget_is_hard_capped_and_has_no_retry_allowance(self) -> None:
        cost = pipeline.cost_metadata("1.50")
        self.assertEqual(cost["hard_budget_cap_usd"], 1.5)
        self.assertEqual(cost["configured_budget_cap_usd"], 1.5)
        self.assertEqual(cost["planned_paid_submissions"], 3)
        self.assertEqual(cost["maximum_paid_submissions"], 3)
        self.assertFalse(cost["automatic_paid_retries"])
        with self.assertRaisesRegex(pipeline.PipelineError, "exceeds"):
            pipeline.cost_metadata("1.51")

    def test_retry_budget_is_separate_and_allows_only_two_submissions(self) -> None:
        cost = pipeline.retry_cost_metadata("1.00")
        self.assertEqual(cost["configured_budget_cap_usd"], 1.0)
        self.assertEqual(cost["maximum_paid_submissions"], 2)
        self.assertEqual(cost["planned_paid_submissions"], 2)
        self.assertFalse(cost["automatic_paid_retries"])
        self.assertIn("alibaba/wan-2.7", cost["authorization_scope"])
        with self.assertRaisesRegex(pipeline.PipelineError, "retry cap"):
            pipeline.retry_cost_metadata("1.01")

    def test_primary_receipts_admit_only_wan27_and_veo_retry(self) -> None:
        state = pipeline.validate_primary_retry_eligibility(
            self.source,
            pipeline.ROOT,
        )
        self.assertEqual(
            state[pipeline.native.WAN_MODEL_ID]["eligibility"],
            "reuse-primary-success; never retry",
        )
        self.assertEqual(
            state[pipeline.native.WAN_27_MODEL_ID]["receipt"]["status"],
            "provider-failed",
        )
        self.assertEqual(
            state[pipeline.native.VEO_31_MODEL_ID]["rejection_proof"],
            {
                "http_status": 400,
                "source_fetch_status": 404,
                "attempt_count": 1,
                "provider_job_created": False,
            },
        )

    def test_primary_status_mutation_fails_retry_eligibility_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_primary_attempts(root)
            paths = pipeline._manifest_artifact_paths(
                pipeline.BATCH_ROOT,
                pipeline.native.WAN_27_MODEL_ID,
            )
            run_path = root / paths["run"]
            run = pipeline.read_json(run_path)
            run["status"] = "failed-pre-submit"
            run_path.write_text(json.dumps(run), encoding="utf-8")
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "aggregate output differs",
            ):
                pipeline.validate_primary_retry_eligibility(self.source, root)

    def test_retry_native_bridge_excludes_wan22_and_uses_mds_orig(self) -> None:
        with pipeline.configured_retry_native(self.source, pipeline.ROOT):
            entries = pipeline.native.matrix()
            self.assertEqual(
                [entry.model_id for entry in entries],
                list(pipeline.RETRY_MODEL_IDS),
            )
            self.assertNotIn(pipeline.native.WAN_MODEL_ID, pipeline.native.MODEL_IDS)
            self.assertTrue(
                all(
                    pipeline.native.provider_sample(entry)["source_url"]
                    == pipeline.EXPECTED_ORIG_URL
                    for entry in entries
                )
            )
            self.assertTrue(
                all(
                    pipeline.RETRY_PROVIDER_BATCH_ID in entry.provider_run_id
                    for entry in entries
                )
            )
            self.assertTrue(
                all(
                    pipeline.RETRY_BATCH_ROOT.as_posix()
                    in pipeline.native.artifact_paths(entry, pipeline.ROOT)[
                        "run"
                    ].as_posix()
                    for entry in entries
                )
            )

    def test_generation_gate_precedes_planning_or_native_calls(self) -> None:
        with (
            mock.patch.object(pipeline, "_validated_planning") as planning,
            mock.patch.object(pipeline.native, "main") as native_main,
            self.assertRaisesRegex(pipeline.PipelineError, "requires --allow"),
        ):
            pipeline.run_generation(
                self.source,
                root=pipeline.ROOT,
                dry_run=False,
                allow_external_processing=False,
            )
        planning.assert_not_called()
        native_main.assert_not_called()

    def test_generation_delegates_fixed_pools_without_force_or_filters(self) -> None:
        with (
            mock.patch.object(
                pipeline, "_validated_planning", return_value=({}, {})
            ),
            mock.patch.object(pipeline, "_retry_state_errors", return_value=[]),
            mock.patch.object(pipeline.native, "main", return_value=0) as native_main,
        ):
            result = pipeline.run_generation(
                self.source,
                root=pipeline.ROOT,
                timeout=30,
                poll_interval=1.0,
                dry_run=True,
                allow_external_processing=False,
            )
        self.assertEqual(result, 0)
        argv = native_main.call_args.args[0]
        self.assertEqual(argv[argv.index("--wan22-concurrency") + 1], "1")
        self.assertEqual(argv[argv.index("--wan27-concurrency") + 1], "3")
        self.assertEqual(argv[argv.index("--veo31-concurrency") + 1], "3")
        self.assertIn("--dry-run", argv)
        self.assertNotIn("--force", argv)
        self.assertNotIn("--model", argv)
        self.assertNotIn("--run-id", argv)

    def test_real_retry_gate_precedes_primary_validation_or_native_calls(self) -> None:
        with (
            mock.patch.object(
                pipeline, "validate_primary_retry_eligibility"
            ) as primary,
            mock.patch.object(pipeline.native, "main") as native_main,
            self.assertRaisesRegex(pipeline.PipelineError, "requires --allow"),
        ):
            pipeline.run_retry_generation(
                self.source,
                root=pipeline.ROOT,
                retry_budget_cap_usd="1.00",
                dry_run=False,
                allow_external_processing=False,
            )
        primary.assert_not_called()
        native_main.assert_not_called()

    def test_retry_dry_run_delegates_two_exact_models_without_filters(self) -> None:
        with (
            mock.patch.object(
                pipeline, "_validated_planning", return_value=({}, {})
            ),
            mock.patch.object(
                pipeline, "validate_primary_retry_eligibility", return_value={}
            ),
            mock.patch.object(pipeline, "_retry_namespace_errors", return_value=[]),
            mock.patch.object(pipeline.native, "main", return_value=0) as native_main,
        ):
            result = pipeline.run_retry_generation(
                self.source,
                root=pipeline.ROOT,
                timeout=30,
                poll_interval=1.0,
                retry_budget_cap_usd="1.00",
                dry_run=True,
            )
        self.assertEqual(result, 0)
        argv = native_main.call_args.args[0]
        self.assertIn("--dry-run", argv)
        self.assertNotIn("--force", argv)
        self.assertNotIn("--model", argv)
        self.assertNotIn("--run-id", argv)
        with pipeline.configured_retry_native(self.source, pipeline.ROOT):
            self.assertEqual(
                [entry.model_id for entry in pipeline.native.matrix()],
                list(pipeline.RETRY_MODEL_IDS),
            )

    def test_real_retry_locks_primary_inventory_before_creating_retry_inventory(self) -> None:
        lock_context = mock.MagicMock()

        def write_while_locked(*args, **kwargs):
            self.assertTrue(lock_context.__enter__.called)
            return {}

        with (
            mock.patch.object(pipeline, "validate_routes"),
            mock.patch.object(
                pipeline, "validate_primary_retry_eligibility", return_value={}
            ),
            mock.patch.object(
                pipeline, "write_retry_inventory", side_effect=write_while_locked
            ) as write_inventory,
            mock.patch.object(pipeline, "_retry_namespace_errors", return_value=[]),
            mock.patch.object(pipeline, "_validated_planning", return_value=({}, {})),
            mock.patch.object(pipeline, "configured_retry_native") as configured,
            mock.patch.object(pipeline.native, "main", return_value=0),
            mock.patch.object(
                pipeline, "batch_run_lock", return_value=lock_context
            ) as batch_lock,
        ):
            result = pipeline.run_retry_generation(
                self.source,
                root=pipeline.ROOT,
                timeout=30,
                poll_interval=1.0,
                retry_budget_cap_usd="1.00",
                dry_run=False,
                allow_external_processing=True,
            )

        self.assertEqual(result, 0)
        batch_lock.assert_called_once_with(pipeline.ROOT / pipeline.INVENTORY_PATH)
        write_inventory.assert_called_once()
        configured.assert_called_once_with(self.source, pipeline.ROOT)

    def test_allow_incomplete_verify_does_not_require_generation_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                mock.patch.object(pipeline, "planning_state", return_value="verified"),
                mock.patch.object(pipeline.native, "verify") as native_verify,
            ):
                passed, errors = pipeline.verify(
                    self.source,
                    root=root,
                    allow_incomplete=True,
                )
        self.assertTrue(passed)
        self.assertEqual(errors, [])
        native_verify.assert_not_called()

    def test_final_manifest_selects_primary_wan22_and_two_retry_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_primary_attempts(root)
            retry_generation = self._write_retry_successes(root)
            planning_summary = {
                "verified": True,
                "agent_id": pipeline.AGENT_ID,
                "models": list(pipeline.MODEL_IDS),
                "source_image_sha256": self.source.image["sha256"],
                "article_context_sha256": self.source.context_sha256,
                "result_path": (
                    pipeline.ARTIFACT_NAMESPACE
                    / pipeline.PLANNING_RUN_ID
                    / "result.json"
                ).as_posix(),
            }
            planning_result = pipeline.read_json(
                root
                / pipeline.ARTIFACT_NAMESPACE
                / pipeline.PLANNING_RUN_ID
                / "result.json"
            )
            primary_generation = pipeline.read_json(
                root / pipeline.GENERATION_MANIFEST_PATH
            )
            document = pipeline.build_final_manifest(
                self.source,
                planning_summary=planning_summary,
                planning_result=planning_result,
                primary_generation=primary_generation,
                retry_generation=retry_generation,
                root=root,
                retry_budget_cap_usd="1.00",
                updated_at="2026-07-27T12:00:00Z",
            )

        self.assertEqual(document["delivery"], "repository-raw")
        self.assertEqual(document["manifest_role"], "case-21-extension")
        self.assertEqual(document["accepted_output_count"], 3)
        self.assertEqual(document["conforming_output_count"], 3)
        self.assertEqual(document["visual_fidelity_passed_count"], 2)
        self.assertEqual(document["visual_fidelity_failed_count"], 1)
        self.assertEqual(document["planning"]["run_id"], pipeline.PLANNING_RUN_ID)
        self.assertEqual(
            [output["model_id"] for output in document["outputs"]],
            list(pipeline.MODEL_IDS),
        )
        self.assertTrue(
            all(output["delivery"] == "repository-raw" for output in document["outputs"])
        )
        self.assertEqual(
            document["articles"][0]["images"][0]["image"]["delivery"],
            "repository-raw",
        )
        self.assertTrue(
            all(output["route"]["fallback"] is None for output in document["outputs"])
        )
        by_model = {output["model_id"]: output for output in document["outputs"]}
        self.assertIn(
            pipeline.PROVIDER_BATCH_ID,
            by_model[pipeline.native.WAN_MODEL_ID]["provider_run_id"],
        )
        self.assertIn(
            pipeline.RETRY_PROVIDER_BATCH_ID,
            by_model[pipeline.native.WAN_27_MODEL_ID]["provider_run_id"],
        )
        self.assertIn(
            pipeline.RETRY_PROVIDER_BATCH_ID,
            by_model[pipeline.native.VEO_31_MODEL_ID]["provider_run_id"],
        )
        self.assertEqual(
            len(by_model[pipeline.native.WAN_MODEL_ID]["attempt_history"]),
            1,
        )
        self.assertEqual(
            len(by_model[pipeline.native.WAN_27_MODEL_ID]["attempt_history"]),
            2,
        )
        self.assertEqual(
            len(by_model[pipeline.native.VEO_31_MODEL_ID]["attempt_history"]),
            2,
        )
        self.assertEqual(
            by_model[pipeline.native.WAN_MODEL_ID]["visual_review"]["status"],
            "fidelity-failed",
        )
        self.assertEqual(len(document["attempt_history"]), 5)
        self.assertTrue(
            all(output["review_path"].endswith("04.review.json") for output in document["outputs"])
        )

    def test_final_manifest_fails_closed_without_exact_visual_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_primary_attempts(root)
            retry_generation = self._write_retry_successes(root)
            missing = (
                root
                / pipeline._manifest_artifact_paths(
                    pipeline.RETRY_BATCH_ROOT,
                    pipeline.native.WAN_27_MODEL_ID,
                )["review"]
            )
            missing.unlink()
            planning_result = pipeline.read_json(
                root
                / pipeline.ARTIFACT_NAMESPACE
                / pipeline.PLANNING_RUN_ID
                / "result.json"
            )
            planning_summary = {
                "verified": True,
                "agent_id": pipeline.AGENT_ID,
                "models": list(pipeline.MODEL_IDS),
                "source_image_sha256": self.source.image["sha256"],
                "article_context_sha256": self.source.context_sha256,
                "result_path": (
                    pipeline.ARTIFACT_NAMESPACE
                    / pipeline.PLANNING_RUN_ID
                    / "result.json"
                ).as_posix(),
            }
            with self.assertRaisesRegex(pipeline.PipelineError, "visual review"):
                pipeline.build_final_manifest(
                    self.source,
                    planning_summary=planning_summary,
                    planning_result=planning_result,
                    primary_generation=pipeline.read_json(
                        root / pipeline.GENERATION_MANIFEST_PATH
                    ),
                    retry_generation=retry_generation,
                    root=root,
                    retry_budget_cap_usd="1.00",
                )

    def test_retry_manifest_fails_closed_on_non_mds_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._copy_primary_attempts(root)
            generation = self._write_retry_successes(root)
            paths = pipeline._manifest_artifact_paths(
                pipeline.RETRY_BATCH_ROOT,
                pipeline.native.VEO_31_MODEL_ID,
            )
            run_path = root / paths["run"]
            run = pipeline.read_json(run_path)
            run["request"]["frame_images"][0]["image_url"]["url"] = (
                pipeline.PUBLIC_RAW_BASE + self.source.image["source_path"]
            )
            run_path.write_text(json.dumps(run), encoding="utf-8")
            with self.assertRaisesRegex(pipeline.PipelineError, "source URL"):
                pipeline.validate_retry_generation(
                    self.source,
                    generation,
                    root=root,
                    allow_contract_warnings=False,
                )

    def test_retry_namespace_fails_closed_if_wan22_artifacts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary_run = (
                root
                / pipeline._manifest_artifact_paths(
                    pipeline.BATCH_ROOT,
                    pipeline.native.WAN_MODEL_ID,
                )["run"]
            )
            primary_run.parent.mkdir(parents=True, exist_ok=True)
            primary_run.write_text("{}", encoding="utf-8")
            forbidden = (
                root
                / pipeline.RETRY_BATCH_ROOT
                / "videos"
                / pipeline.ARTICLE_SLUG
                / pipeline.native.MODEL_DIRECTORIES[pipeline.native.WAN_MODEL_ID]
            )
            forbidden.mkdir(parents=True)
            errors = pipeline._retry_namespace_errors(self.source, root)
            self.assertTrue(
                any("Wan 2.2 artifacts are forbidden" in error for error in errors)
            )

    def test_cli_does_not_expose_force_or_model_fallback_controls(self) -> None:
        parser = pipeline.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["generate", "--force"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["generate", "--model", "alibaba/wan-2.7"])
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "retry-generate",
                    "--retry-budget-cap-usd",
                    "1.00",
                    "--force",
                ]
            )
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "retry-generate",
                    "--retry-budget-cap-usd",
                    "1.00",
                    "--model",
                    "alibaba/wan-2.7",
                ]
            )
        with self.assertRaises(SystemExit):
            parser.parse_args(["retry-generate"])
        args = parser.parse_args(
            [
                "retry-generate",
                "--retry-budget-cap-usd",
                "1.00",
                "--allow-external-processing",
            ]
        )
        self.assertTrue(args.allow_external_processing)


if __name__ == "__main__":
    unittest.main()
