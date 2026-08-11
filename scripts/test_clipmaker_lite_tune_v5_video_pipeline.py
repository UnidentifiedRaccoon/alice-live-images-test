from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v5_video_pipeline as video


def entry(
    model_id: str = "alibaba/wan-2.2",
    *,
    width: int = 1280,
    height: int = 720,
) -> video.Entry:
    runtime = {
        "duration_seconds": 5 if model_id != "google/veo-3.1-lite" else 4,
        "resolution": "720p" if model_id == "alibaba/wan-2.2" else "1080p",
        "generate_audio": False,
    }
    return video.Entry(
        case_id="01#02",
        sheet_row=2,
        article_slug="01-level-ipoteka-2026",
        image_id="02",
        model_id=model_id,
        source_path="source.png",
        source_url="https://example.test/source.png",
        source_sha256="a" * 64,
        width=width,
        height=height,
        planning_run_id=f"{video.PLANNING_BATCH_ID}-01-level-ipoteka-2026-02",
        result_path="result.json",
        result_sha256="b" * 64,
        prompt_manifest_sha256="c" * 64,
        route_registry_sha256="d" * 64,
        repair_feedback_path="repair.json",
        repair_feedback_sha256="e" * 64,
        scene_plan="One bounded source-grounded motion.",
        positive_prompt="The visible subject moves gently while source geometry stays fixed.",
        runtime=runtime,
        provenance={"verified": True, "contract_version": "2.3.0"},
    )


def no_network_operations(media_probe=lambda _path: {}) -> video.ProviderOperations:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("provider operation must not be called")

    return video.ProviderOperations(
        eliza_headers=forbidden,
        http_json=forbidden,
        eliza_poll=forbidden,
        http_download=forbidden,
        segmind_generate=forbidden,
        media_probe=media_probe,
    )


class TuneV5VideoPipelineTests(unittest.TestCase):
    def test_budget_is_exact_28_times_frozen_rate(self) -> None:
        document = video.budget_document("9.80")
        self.assertEqual(document["reserved_output_count"], 28)
        self.assertEqual(document["accounting_cost_per_output_usd"], 0.35)
        self.assertEqual(document["maximum_estimated_cost_usd"], 9.8)
        self.assertFalse(document["automatic_paid_retry"])
        for bad in ("9.79", "9.81", "15.05"):
            with self.assertRaises(video.TuneV5VideoError):
                video.parse_budget(bad)

    def test_frozen_model_counts_and_independent_capacities(self) -> None:
        self.assertEqual(sum(video.EXPECTED_BY_MODEL.values()), 28)
        self.assertEqual(
            video.EXPECTED_BY_MODEL,
            {
                "alibaba/wan-2.2": 11,
                "alibaba/wan-2.7": 5,
                "google/veo-3.1-lite": 12,
            },
        )
        self.assertEqual(
            video.EXPECTED_ROUTE_CAPACITIES,
            {
                "alibaba/wan-2.2": 1,
                "alibaba/wan-2.7": 3,
                "google/veo-3.1-lite": 3,
            },
        )

    def test_provider_prompt_is_i2v_and_wan27_keeps_extension(self) -> None:
        wan22 = video.provider_prompt(entry("alibaba/wan-2.2"))
        wan27 = video.provider_prompt(entry("alibaba/wan-2.7"))
        self.assertEqual(wan22["negative_prompt"], None)
        self.assertNotIn("prompt_extend", wan22)
        self.assertTrue(wan27["prompt_extend"])
        self.assertNotIn("fallback", wan27)

    def test_dry_run_materializes_once_without_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = {"entry": entry()}
            args = argparse.Namespace(
                dry_run=True,
                timeout=10,
                poll_interval=0.01,
                segmind_base_url="https://example.test/segmind/v1",
                eliza_base_url="https://example.test/openrouter/v1",
            )
            result = video.run_provider_worker(
                original,
                args,
                output_root=root,
                operations=no_network_operations(),
            )
            self.assertFalse(result.failed)
            self.assertEqual(result.status, "dry-run")
            paths = video.artifact_paths(original["entry"], root)
            run = json.loads(paths["run"].read_text())
            self.assertEqual(run["status"], "dry-run")
            self.assertFalse(run["automatic_paid_retry"])
            self.assertIsNone(run["fallback"])
            self.assertFalse(run["s3_upload"])

    def test_terminal_provider_failure_blocks_paid_retry_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = entry("google/veo-3.1-lite")
            row = video.materialize_entry(item, output_root=root)
            run = json.loads(row["paths"]["run"].read_text())
            run.update(
                {
                    "status": "provider-failed",
                    "provider_may_be_active": False,
                    "provider_job_id": "job-1",
                    "error": "filtered",
                }
            )
            video.transport.atomic_write_json(row["paths"]["run"], run)
            args = argparse.Namespace(
                dry_run=False,
                timeout=10,
                poll_interval=0.01,
                segmind_base_url="https://example.test/segmind/v1",
                eliza_base_url="https://example.test/openrouter/v1",
            )
            result = video.run_provider_worker(
                {"entry": item},
                args,
                output_root=root,
                operations=no_network_operations(),
            )
            self.assertTrue(result.failed)
            self.assertEqual(result.status, "provider-failed")
            self.assertIn("blocks automatic paid retry and fallback", result.error)

    def test_wan27_undersize_is_rejected_before_any_provider_operation(self) -> None:
        for width, height in ((758, 220), (773, 239)):
            with (
                self.subTest(width=width, height=height),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                item = entry("alibaba/wan-2.7", width=width, height=height)
                result = video.run_provider_worker(
                    {"entry": item},
                    argparse.Namespace(
                        dry_run=False,
                        timeout=10,
                        poll_interval=0.01,
                        segmind_base_url="https://example.test/segmind/v1",
                        eliza_base_url="https://example.test/openrouter/v1",
                    ),
                    output_root=root,
                    operations=no_network_operations(),
                )

                self.assertTrue(result.failed)
                self.assertEqual(result.status, "failed-pre-submit")
                self.assertFalse(result.holds_provider_slot)
                run = json.loads(
                    video.artifact_paths(item, root)["run"].read_text()
                )
                self.assertEqual(run["status"], "failed-pre-submit")
                self.assertFalse(run["provider_may_be_active"])
                self.assertIsNone(run["provider_job_id"])
                self.assertIsNone(run["submitted_at"])
                self.assertEqual(
                    run["source_preflight"],
                    {
                        "check": "source-dimensions",
                        "model_id": "alibaba/wan-2.7",
                        "width": width,
                        "height": height,
                        "minimum_dimension_px": 240,
                        "conforms": False,
                        "normalization_applied": False,
                    },
                )
                self.assertIn("new immutable batch", run["error"])

    def test_succeeded_missing_mp4_is_stale_without_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = entry("google/veo-3.1-lite")
            row = video.materialize_entry(item, output_root=root)
            request = video.transport.build_request_preview(row["sample"], row["prompt"])
            run = json.loads(row["paths"]["run"].read_text())
            run.update(
                {
                    "status": "succeeded",
                    "request": request,
                    "request_sha256": video.transport.request_fingerprint(request, row["sample"]),
                    "request_fingerprint_version": video.transport.REQUEST_FINGERPRINT_VERSION,
                }
            )
            video.transport.atomic_write_json(row["paths"]["run"], run)
            args = argparse.Namespace(
                dry_run=False,
                timeout=10,
                poll_interval=0.01,
                segmind_base_url="https://example.test/segmind/v1",
                eliza_base_url="https://example.test/openrouter/v1",
            )
            result = video.run_provider_worker(
                {"entry": item},
                args,
                output_root=root,
                operations=no_network_operations(),
            )
            self.assertTrue(result.failed)
            self.assertEqual(result.status, "stale")
            self.assertIn("missing MP4", result.error)

    def test_succeeded_request_mismatch_is_stale_without_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = entry("google/veo-3.1-lite")
            row = video.materialize_entry(item, output_root=root)
            row["paths"]["video"].write_bytes(b"existing-mp4")
            run = json.loads(row["paths"]["run"].read_text())
            run.update(
                {
                    "status": "succeeded",
                    "request": {"tampered": True},
                    "request_sha256": "0" * 64,
                    "request_fingerprint_version": video.transport.REQUEST_FINGERPRINT_VERSION,
                }
            )
            video.transport.atomic_write_json(row["paths"]["run"], run)
            args = argparse.Namespace(
                dry_run=False,
                timeout=10,
                poll_interval=0.01,
                segmind_base_url="https://example.test/segmind/v1",
                eliza_base_url="https://example.test/openrouter/v1",
            )
            result = video.run_provider_worker(
                {"entry": item},
                args,
                output_root=root,
                operations=no_network_operations(),
            )
            self.assertTrue(result.failed)
            self.assertEqual(result.status, "stale")
            self.assertIn("request binding", result.error)

    def test_verify_rejects_terminal_request_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = entry("alibaba/wan-2.7")
            row = video.materialize_entry(item, output_root=root)
            row["paths"]["video"].write_bytes(b"existing-mp4")
            run = json.loads(row["paths"]["run"].read_text())
            run.update(
                {
                    "status": "succeeded",
                    "request": {"tampered": True},
                    "request_sha256": "0" * 64,
                    "request_fingerprint_version": video.transport.REQUEST_FINGERPRINT_VERSION,
                }
            )
            video.transport.atomic_write_json(row["paths"]["run"], run)
            inventory = video.Inventory(
                entries=(item,),
                prompt_manifest_sha256="c" * 64,
                contract_sha256="f" * 64,
                route_registry_sha256="d" * 64,
                budget=video.budget_document("9.80"),
            )
            with mock.patch.object(video, "load_inventory", return_value=inventory):
                ok, errors = video.verify("9.80", root=root, output_root=root)
            self.assertFalse(ok)
            self.assertTrue(any("request binding changed" in error for error in errors))

    def test_verification_failed_mp4_is_retained_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = video.materialize_entry(entry("alibaba/wan-2.7"), output_root=root)
            row["paths"]["video"].write_bytes(b"reviewable-mp4")
            run = json.loads(row["paths"]["run"].read_text())
            media = {
                "sha256": "1" * 64,
                "bytes": len(b"reviewable-mp4"),
                "duration_seconds": 5.0,
                "width": 1920,
                "height": 1080,
                "fps": 24.0,
                "frames": 120,
                "has_audio": True,
            }
            check = {
                "requested": {"generate_audio": False},
                "checks": {"audio": False},
                "conforms": False,
                "warnings": ["actual has_audio=True while generate_audio=False"],
            }
            with mock.patch.object(video.transport, "assess_contract", return_value=check):
                result = video._verify_media(  # noqa: SLF001
                    row,
                    run,
                    no_network_operations(media_probe=lambda _path: media),
                )
            self.assertTrue(result.failed)
            self.assertEqual(result.status, "verification-failed")
            self.assertTrue(row["paths"]["video"].is_file())
            persisted = json.loads(row["paths"]["run"].read_text())
            self.assertEqual(persisted["media"], media)
            self.assertEqual(persisted["contract_check"], check)

    def test_generation_manifest_declares_no_compositor_fallback_or_s3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = entry()
            row = video.materialize_entry(item, output_root=root)
            inventory = video.Inventory(
                entries=(item,),
                prompt_manifest_sha256="c" * 64,
                contract_sha256="f" * 64,
                route_registry_sha256="d" * 64,
                budget=video.budget_document("9.80"),
            )
            manifest = video.generation_manifest_document(
                inventory,
                [row],
                output_root=root,
            )
            self.assertEqual(manifest["scope"]["compositor_outputs"], 0)
            self.assertEqual(manifest["scope"]["fallback_outputs"], 0)
            self.assertFalse(manifest["scope"]["s3_upload"])
            self.assertFalse(manifest["scheduling"]["automatic_paid_retry"])
            self.assertFalse(manifest["scheduling"]["fallback"])
            self.assertIsNone(manifest["outputs"][0]["fallback"])


if __name__ == "__main__":
    unittest.main()
