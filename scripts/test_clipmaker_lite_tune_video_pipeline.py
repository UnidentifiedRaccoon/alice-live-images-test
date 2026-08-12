from __future__ import annotations

import argparse
import copy
import json
import math
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_video_pipeline as pipeline
from scripts import video_generation_pipeline as transport


class ClipmakerLiteTuneVideoPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Provenance verification is local/read-only and is part of the
        # production preflight this test is meant to cover.
        cls.inventory = pipeline.load_inventory("15.05")

    def no_network_operations(self) -> pipeline.ProviderOperations:
        def fail(*_args, **_kwargs):
            self.fail("dry-run must not call a provider operation")

        return pipeline.ProviderOperations(
            eliza_headers=fail,
            http_json=fail,
            eliza_poll=fail,
            http_download=fail,
            segmind_generate=fail,
            media_probe=fail,
        )

    def worker_args(self, *, dry_run: bool) -> argparse.Namespace:
        return argparse.Namespace(
            dry_run=dry_run,
            timeout=30,
            poll_interval=0.01,
            fail_fast=False,
            segmind_base_url=transport.route_for_model("alibaba/wan-2.2")[
                "default_base_url"
            ],
            eliza_base_url=transport.route_for_model("alibaba/wan-2.7")[
                "default_base_url"
            ],
        )

    def strict_row(self, entry: pipeline.TuneEntry) -> dict:
        return {
            "entry": entry,
            "sample": pipeline.provider_sample(entry),
            "prompt": pipeline.provider_prompt(entry),
        }

    def valid_local_media(self, row: dict, video: Path) -> dict:
        entry = row["entry"]
        if entry.model_id == "alibaba/wan-2.2":
            ratio = entry.request_width / entry.request_height
            pixels = pipeline.WAN_22_PIXEL_BUDGET
            fps = 30.0
            frames = 150
        else:
            request = transport.build_request_preview(row["sample"], row["prompt"])
            left, right = (int(value) for value in request["aspect_ratio"].split(":"))
            ratio = left / right
            pixels = pipeline.OPENROUTER_1080P_TARGET_PIXELS
            if entry.model_id == "google/veo-3.1-lite":
                fps = 24.0
                frames = 96
            else:
                fps = 30.0
                frames = 150
        width = int(round(math.sqrt(pixels * ratio) / 2) * 2)
        height = int(round(math.sqrt(pixels / ratio) / 2) * 2)
        return {
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": float(row["prompt"]["target_duration_seconds"]),
            "width": width,
            "height": height,
            "fps": fps,
            "frames": frames,
            "has_audio": False,
            "bytes": video.stat().st_size,
            "sha256": pipeline.sha256_file(video),
        }

    def prepare_refresh_fixture(
        self,
        output_root: Path,
    ) -> tuple[dict[Path, dict], dict[Path, bytes]]:
        rows = pipeline.materialize(self.inventory, output_root=output_root)
        media_by_path: dict[Path, dict] = {}
        failed_run_bytes: dict[Path, bytes] = {}
        for row in rows:
            entry = row["entry"]
            paths = row["paths"]
            run = pipeline.read_json(paths["run"])
            request = transport.build_request_preview(row["sample"], row["prompt"])
            run.update(
                {
                    "request": request,
                    "request_sha256": transport.request_fingerprint(
                        request,
                        row["sample"],
                    ),
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                    "provider_job_id": f"job-{entry.case_id}-{entry.model_id}",
                    "submitted_at": "2026-08-11T00:00:00Z",
                    "completed_at": "2026-08-11T00:01:00Z",
                    "provider_may_be_active": False,
                }
            )
            if (entry.case_id, entry.model_id) in pipeline.EXPECTED_PROVIDER_FAILURE_KEYS:
                run.update(
                    {
                        "status": "provider-failed",
                        "media": None,
                        "contract_check": None,
                        "error": "terminal provider failure",
                    }
                )
                transport.atomic_write_json(paths["run"], run)
                failed_run_bytes[paths["run"]] = paths["run"].read_bytes()
                continue
            paths["video"].write_bytes(
                f"fixture:{entry.provider_run_id}".encode("utf-8")
            )
            media = self.valid_local_media(row, paths["video"])
            if entry.model_id == "alibaba/wan-2.7":
                media["has_audio"] = True
            contract_check = transport.assess_contract(
                entry.model_id,
                media,
                row["prompt"]["target_duration_seconds"],
            )
            status = (
                "succeeded"
                if contract_check["conforms"]
                else "verification-failed"
            )
            run.update(
                {
                    "status": status,
                    "media": media,
                    "contract_check": contract_check,
                    "error": (
                        None
                        if status == "succeeded"
                        else "Media contract warnings: "
                        + "; ".join(contract_check["warnings"])
                    ),
                }
            )
            transport.atomic_write_json(paths["run"], run)
            media_by_path[paths["video"]] = media
        pipeline.write_generation_manifest(self.inventory, rows, output_root)
        return media_by_path, failed_run_bytes

    def test_inventory_is_exact_43_i2v_plus_22_compositor(self) -> None:
        self.assertEqual(len(self.inventory.entries), 43)
        self.assertEqual(len(self.inventory.compositor_exclusions), 22)
        self.assertEqual(
            Counter(entry.model_id for entry in self.inventory.entries),
            Counter(pipeline.EXPECTED_I2V_BY_MODEL),
        )
        self.assertEqual(
            Counter(value.model_id for value in self.inventory.compositor_exclusions),
            Counter(pipeline.EXPECTED_COMPOSITOR_BY_MODEL),
        )
        self.assertTrue(
            all(entry.execution_mode == "i2v" for entry in self.inventory.entries)
        )
        self.assertTrue(
            all(
                value.execution_mode == "deterministic-compositor"
                for value in self.inventory.compositor_exclusions
            )
        )
        self.assertEqual(
            self.inventory.budget["maximum_estimated_cost_usd"], 15.05
        )
        self.assertFalse(self.inventory.budget["automatic_paid_retry"])

    def test_budget_cap_is_explicit_and_exact(self) -> None:
        for invalid in ("15.04", "15.06", "100", "nope"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(pipeline.TuneVideoPipelineError):
                    pipeline.load_inventory(invalid)

    def test_prompts_are_exact_v4_model_prompts(self) -> None:
        for entry in self.inventory.entries:
            with self.subTest(provider_run_id=entry.provider_run_id):
                result = pipeline.read_json(pipeline.ROOT / entry.result_path)
                model = next(
                    value
                    for value in result["models"]
                    if value["model_id"] == entry.model_id
                )
                self.assertEqual(entry.positive_prompt, model["positive_prompt"])
                self.assertEqual(entry.scene_plan, model["scene_plan"])
                self.assertIsNone(entry.negative_prompt)
                self.assertFalse(pipeline.prompt_artifact(entry)["prompt"]["rewritten"])

    def test_compositor_plan_hard_fails_provider_materialization(self) -> None:
        entry = replace(
            self.inventory.entries[0],
            execution_mode="deterministic-compositor",
            positive_prompt=None,
        )
        with self.assertRaisesRegex(
            pipeline.TuneVideoPipelineError,
            "must not be sent to a video provider",
        ):
            pipeline.provider_prompt(entry)

    def test_only_case_12_wan_targets_use_frozen_scale_1200_overlay(self) -> None:
        overlays = [
            entry
            for entry in self.inventory.entries
            if entry.normalized_input_overlay is not None
        ]
        self.assertEqual(
            {(entry.case_id, entry.model_id) for entry in overlays},
            {
                ("12#08", "alibaba/wan-2.2"),
                ("12#08", "alibaba/wan-2.7"),
            },
        )
        for entry in overlays:
            self.assertEqual(entry.request_source_url, pipeline.NORMALIZED_INPUT_URL)
            self.assertEqual(
                entry.request_source_sha256,
                pipeline.NORMALIZED_INPUT_SHA256,
            )
            self.assertEqual((entry.request_width, entry.request_height), (1200, 801))
            self.assertEqual(entry.source_sha256, entry.provenance["source_image_sha256"])
            self.assertNotEqual(entry.request_source_sha256, entry.source_sha256)
        veo = next(
            entry
            for entry in self.inventory.entries
            if entry.case_id == "12#08"
            and entry.model_id == "google/veo-3.1-lite"
        )
        self.assertIsNone(veo.normalized_input_overlay)
        self.assertEqual(veo.request_source_url, veo.source_url)
        self.assertEqual(veo.request_source_sha256, veo.source_sha256)

    def test_exact_routes_and_independent_pool_limits_are_locked(self) -> None:
        self.assertEqual(
            {
                model_id: transport.route_for_model(model_id)["capacity"]
                for model_id in pipeline.MODEL_IDS
            },
            pipeline.EXPECTED_ROUTE_CAPACITIES,
        )
        limits = pipeline.native.ProviderPoolLimits()
        self.assertEqual(
            {
                model_id: limits.for_model(model_id)
                for model_id in pipeline.MODEL_IDS
            },
            {"alibaba/wan-2.2": 1, "alibaba/wan-2.7": 3, "google/veo-3.1-lite": 3},
        )

    def test_strict_wan_22_checks_pixels_source_aspect_and_preserves_warnings(self) -> None:
        entry = next(
            value
            for value in self.inventory.entries
            if value.case_id == "02#06" and value.model_id == "alibaba/wan-2.2"
        )
        row = self.strict_row(entry)
        media = {
            "duration_seconds": 5.0,
            "width": 1104,
            "height": 816,
            "fps": 30.0,
            "frames": 150,
            "has_audio": False,
        }
        prior = transport.assess_contract(entry.model_id, media, 5)
        prior["warnings"].append("preserved provider warning")
        check = pipeline.assess_tune_media_contract(
            row,
            media,
            prior_contract_check=prior,
        )
        self.assertTrue(check["conforms"])
        self.assertEqual(
            check["checks"],
            {
                "duration": True,
                "audio": True,
                "frames": True,
                "fps": True,
                "pixels": True,
                "source_aspect": True,
            },
        )
        self.assertEqual(check["requested"]["pixel_budget"], 921600)
        self.assertEqual(check["requested"]["aspect_ratio"], "source")
        self.assertIn("preserved provider warning", check["warnings"])
        self.assertTrue(
            any("provider aspect quantization" in value for value in check["warnings"])
        )

        wrong_aspect = {**media, "width": 1280, "height": 720}
        failed = pipeline.assess_tune_media_contract(row, wrong_aspect)
        self.assertTrue(failed["checks"]["pixels"])
        self.assertFalse(failed["checks"]["source_aspect"])
        self.assertFalse(failed["conforms"])
        self.assertTrue(any("beyond the 2%" in value for value in failed["warnings"]))

    def test_strict_openrouter_uses_constant_area_and_requested_aspect(self) -> None:
        entry = next(
            value
            for value in self.inventory.entries
            if value.case_id == "02#06" and value.model_id == "alibaba/wan-2.7"
        )
        row = self.strict_row(entry)
        quantized = {
            "duration_seconds": 5.0,
            "width": 1662,
            "height": 1246,
            "fps": 30.0,
            "frames": 150,
            "has_audio": False,
        }
        accepted = pipeline.assess_tune_media_contract(row, quantized)
        self.assertTrue(accepted["checks"]["pixels"])
        self.assertTrue(accepted["checks"]["requested_aspect"])
        self.assertTrue(accepted["conforms"])
        self.assertEqual(accepted["requested"]["pixel_area_min"], 1_900_000)
        self.assertEqual(accepted["requested"]["pixel_area_max"], 2_200_000)
        self.assertTrue(
            any("provider aspect quantization" in value for value in accepted["warnings"])
        )

        wrong_aspect = {**quantized, "width": 1764, "height": 1176}
        failed = pipeline.assess_tune_media_contract(row, wrong_aspect)
        self.assertTrue(failed["checks"]["pixels"])
        self.assertFalse(failed["checks"]["requested_aspect"])
        self.assertFalse(failed["conforms"])
        self.assertTrue(any("beyond the 3%" in value for value in failed["warnings"]))

        outside_area = {**quantized, "width": 1200, "height": 900}
        area_failed = pipeline.assess_tune_media_contract(row, outside_area)
        self.assertFalse(area_failed["checks"]["pixels"])
        self.assertTrue(area_failed["checks"]["requested_aspect"])

    def test_strict_veo_exact_1080p_has_no_quantization_warning(self) -> None:
        entry = next(
            value
            for value in self.inventory.entries
            if value.case_id == "03#02"
            and value.model_id == "google/veo-3.1-lite"
        )
        check = pipeline.assess_tune_media_contract(
            self.strict_row(entry),
            {
                "duration_seconds": 4.0,
                "width": 1920,
                "height": 1080,
                "fps": 24.0,
                "frames": 96,
                "has_audio": False,
            },
        )
        self.assertTrue(check["conforms"])
        self.assertEqual(
            check["checks"],
            {
                "duration": True,
                "audio": True,
                "pixels": True,
                "requested_aspect": True,
            },
        )
        self.assertFalse(
            any("quantization" in value for value in check["warnings"])
        )

    def test_materialization_is_repo_relative_and_immutable(self) -> None:
        entry = self.inventory.entries[0]
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            row = pipeline.materialize_entry(entry, output_root=output_root)
            prompt_path = row["paths"]["prompt"]
            run_path = row["paths"]["run"]
            self.assertTrue(prompt_path.is_file())
            self.assertTrue(run_path.is_file())
            self.assertFalse(row["paths"]["video"].exists())
            self.assertTrue(
                pipeline.relative(prompt_path, output_root).startswith(
                    f"clipmaker-lite-test/runs/{pipeline.BATCH_ID}/videos/"
                )
            )
            self.assertNotIn("gh-pages", prompt_path.as_posix())
            self.assertNotIn("s3", pipeline.relative(prompt_path, output_root).lower())
            pipeline.materialize_entry(entry, output_root=output_root)
            prompt = pipeline.read_json(prompt_path)
            prompt["prompt"]["positive"] += " changed"
            transport.atomic_write_json(prompt_path, prompt)
            with self.assertRaisesRegex(
                pipeline.TuneVideoPipelineError,
                "Immutable Tune provider prompt changed",
            ):
                pipeline.materialize_entry(entry, output_root=output_root)

    def test_dry_run_materializes_all_requests_without_network_or_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            failures = pipeline.run_batch(
                "15.05",
                dry_run=True,
                output_root=output_root,
                operations=self.no_network_operations(),
            )
            self.assertEqual(failures, 0)
            generation = pipeline.read_json(
                output_root / pipeline.GENERATION_MANIFEST_REL
            )
            self.assertEqual(generation["summary"], {"dry-run": 43})
            self.assertEqual(len(generation["outputs"]), 43)
            self.assertEqual(len(generation["compositor_exclusions"]), 22)
            self.assertEqual(
                generation["scheduling"]["route_capacities"],
                pipeline.EXPECTED_ROUTE_CAPACITIES,
            )
            self.assertFalse(generation["scope"]["s3_upload"])
            for output in generation["outputs"]:
                self.assertFalse((output_root / output["video_path"]).exists())
                run = pipeline.read_json(output_root / output["run_path"])
                self.assertIsNotNone(run["request"])
                self.assertEqual(run["status"], "dry-run")

    def test_ambiguous_post_is_never_submitted_twice(self) -> None:
        entry = next(
            value
            for value in self.inventory.entries
            if value.model_id == "alibaba/wan-2.7"
        )
        calls = {"post": 0}

        def ambiguous_post(*_args, **_kwargs):
            calls["post"] += 1
            raise RuntimeError("connection ended after request write")

        operations = pipeline.ProviderOperations(
            eliza_headers=lambda: {"Authorization": "Bearer redacted"},
            http_json=ambiguous_post,
            eliza_poll=lambda *_args, **_kwargs: self.fail("must not poll"),
            http_download=lambda *_args, **_kwargs: self.fail("must not download"),
            segmind_generate=lambda *_args, **_kwargs: self.fail("wrong route"),
            media_probe=lambda *_args, **_kwargs: self.fail("must not probe"),
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            row = pipeline.materialize_entry(entry, output_root=output_root)
            first = pipeline.run_provider_worker(
                row,
                self.worker_args(dry_run=False),
                output_root=output_root,
                operations=operations,
            )
            second = pipeline.run_provider_worker(
                row,
                self.worker_args(dry_run=False),
                output_root=output_root,
                operations=operations,
            )
            self.assertEqual(first.status, "submit-unknown")
            self.assertEqual(second.status, "submit-unknown")
            self.assertEqual(calls["post"], 1)
            self.assertTrue(second.holds_provider_slot)

    def test_ffprobe_valid_contract_warning_is_retained_without_retry(self) -> None:
        entry = next(
            value
            for value in self.inventory.entries
            if value.model_id == "alibaba/wan-2.7"
        )
        media = {
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "frames": 120,
            "has_audio": True,
            "bytes": 4,
            "sha256": "0" * 64,
        }
        operations = pipeline.ProviderOperations(
            eliza_headers=lambda: {},
            http_json=lambda *_args, **_kwargs: {},
            eliza_poll=lambda *_args, **_kwargs: {},
            http_download=lambda *_args, **_kwargs: None,
            segmind_generate=lambda *_args, **_kwargs: {},
            media_probe=lambda _path: media,
        )
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            row = pipeline.materialize_entry(entry, output_root=output_root)
            row["paths"]["video"].write_bytes(b"mp4\n")
            run = pipeline.read_json(row["paths"]["run"])
            result = pipeline._verify_output(row, run, operations)  # noqa: SLF001
            recorded = pipeline.read_json(row["paths"]["run"])
            self.assertEqual(result.status, "verification-failed")
            self.assertTrue(row["paths"]["video"].is_file())
            self.assertEqual(recorded["media"], media)
            self.assertFalse(recorded["contract_check"]["conforms"])
            self.assertIn("has_audio=True", recorded["error"])
            blocked = pipeline.run_provider_worker(
                row,
                self.worker_args(dry_run=False),
                output_root=output_root,
                operations=operations,
            )
            self.assertEqual(blocked.status, "verification-failed")

    def test_advisory_quantization_warning_does_not_change_success_status(self) -> None:
        entry = next(
            value
            for value in self.inventory.entries
            if value.case_id == "02#06" and value.model_id == "alibaba/wan-2.2"
        )
        media = {
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1104,
            "height": 816,
            "fps": 30.0,
            "frames": 150,
            "has_audio": False,
            "bytes": 4,
            "sha256": "0" * 64,
        }
        operations = pipeline.ProviderOperations(
            eliza_headers=lambda: {},
            http_json=lambda *_args, **_kwargs: {},
            eliza_poll=lambda *_args, **_kwargs: {},
            http_download=lambda *_args, **_kwargs: None,
            segmind_generate=lambda *_args, **_kwargs: {},
            media_probe=lambda _path: media,
        )
        with tempfile.TemporaryDirectory() as directory:
            row = pipeline.materialize_entry(entry, output_root=Path(directory))
            row["paths"]["video"].write_bytes(b"mp4\n")
            result = pipeline._verify_output(  # noqa: SLF001
                row,
                pipeline.read_json(row["paths"]["run"]),
                operations,
            )
            recorded = pipeline.read_json(row["paths"]["run"])
            self.assertEqual(result.status, "succeeded")
            self.assertTrue(recorded["contract_check"]["conforms"])
            self.assertTrue(recorded["contract_check"]["warnings"])
            self.assertIsNone(recorded["error"])

    def test_refresh_local_verification_probes_41_and_never_touches_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            media_by_path, failed_run_bytes = self.prepare_refresh_fixture(output_root)
            generation_path = output_root / pipeline.GENERATION_MANIFEST_REL
            generation_before = generation_path.read_bytes()
            run_bytes_before = {
                path: path.read_bytes()
                for path in (output_root / pipeline.BATCH_ROOT_REL).rglob("*.run.json")
            }
            attempted = 0

            def failing_probe(path: Path) -> dict:
                nonlocal attempted
                attempted += 1
                if attempted == 41:
                    raise RuntimeError("synthetic final ffprobe failure")
                return copy.deepcopy(media_by_path[path])

            with self.assertRaisesRegex(
                pipeline.TuneVideoPipelineError,
                "synthetic final ffprobe failure",
            ):
                pipeline.refresh_local_verification(
                    "15.05",
                    output_root=output_root,
                    media_probe=failing_probe,
                )
            self.assertEqual(generation_path.read_bytes(), generation_before)
            self.assertTrue(
                all(path.read_bytes() == value for path, value in run_bytes_before.items())
            )

            probes: list[Path] = []

            def local_probe(path: Path) -> dict:
                probes.append(path)
                return copy.deepcopy(media_by_path[path])

            with mock.patch.object(
                pipeline,
                "run_provider_worker",
                side_effect=AssertionError("local refresh entered provider worker"),
            ):
                refreshed = pipeline.refresh_local_verification(
                    "15.05",
                    output_root=output_root,
                    media_probe=local_probe,
                )

            self.assertEqual(len(probes), 41)
            self.assertEqual(len(set(probes)), 41)
            self.assertEqual(
                refreshed["summary"],
                {
                    "succeeded": 29,
                    "verification-failed": 12,
                    "provider-failed": 2,
                },
            )
            self.assertFalse(refreshed["scheduling"]["automatic_paid_retry"])
            for run_path, original_bytes in failed_run_bytes.items():
                self.assertEqual(run_path.read_bytes(), original_bytes)
                self.assertNotIn(
                    "local_media_verification",
                    pipeline.read_json(run_path),
                )
            for output in refreshed["outputs"]:
                if output["status"] == "provider-failed":
                    continue
                run = pipeline.read_json(output_root / output["run_path"])
                self.assertEqual(
                    run["local_media_verification"],
                    {
                        "profile": pipeline.STRICT_MEDIA_QA_PROFILE,
                        "source": "local-mp4-ffprobe",
                        "media_sha256": run["media"]["sha256"],
                        "provider_calls": False,
                        "paid_submission": False,
                        "automatic_paid_retry": False,
                    },
                )
                self.assertIn("pixels", run["contract_check"]["checks"])
                self.assertIn(
                    "source_aspect"
                    if run["model_id"] == "alibaba/wan-2.2"
                    else "requested_aspect",
                    run["contract_check"]["checks"],
                )

            generation_after_refresh = generation_path.read_bytes()
            rejected, rejected_errors = pipeline.verify(
                "15.05",
                output_root=output_root,
                media_probe=lambda path: copy.deepcopy(media_by_path[path]),
            )
            self.assertFalse(rejected)
            self.assertEqual(
                sum("--allow-contract-warnings" in value for value in rejected_errors),
                12,
            )
            self.assertEqual(generation_path.read_bytes(), generation_after_refresh)

            accepted, accepted_errors = pipeline.verify(
                "15.05",
                allow_contract_warnings=True,
                output_root=output_root,
                media_probe=lambda path: copy.deepcopy(media_by_path[path]),
            )
            self.assertTrue(accepted, accepted_errors)
            self.assertEqual(accepted_errors, [])
            self.assertEqual(generation_path.read_bytes(), generation_after_refresh)
            for run_path, original_bytes in failed_run_bytes.items():
                self.assertEqual(run_path.read_bytes(), original_bytes)

    def test_refresh_parser_has_no_external_processing_or_retry_switch(self) -> None:
        parser = pipeline.build_parser()
        parsed = parser.parse_args(
            ["refresh-local-verification", "--budget-cap-usd", "15.05"]
        )
        self.assertEqual(parsed.command, "refresh-local-verification")
        self.assertFalse(hasattr(parsed, "allow_external_processing"))
        self.assertFalse(hasattr(parsed, "timeout"))
        alias = parser.parse_args(["recheck-local", "--budget-cap-usd", "15.05"])
        self.assertEqual(alias.command, "recheck-local")

    def test_legacy_export_overlay_is_explicitly_superseded(self) -> None:
        with self.assertRaisesRegex(
            pipeline.TuneVideoPipelineError,
            "clipmaker_lite_tune_media_overlay.py",
        ):
            pipeline.export_tune_video_overlay("a" * 40)


if __name__ == "__main__":
    unittest.main()
