#!/usr/bin/env python3
"""Focused tests for the native Clipmaker Lite provider bridge."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_generation_pipeline as pipeline


class ClipmakerLiteGenerationPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.entries = {entry.run_id: entry for entry in pipeline.MATRIX}
        for entry in pipeline.MATRIX:
            source = self.root / entry.source_path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(f"fixture:{entry.source_path}".encode("utf-8"))
            result_path = (
                self.root
                / pipeline.ARTIFACT_NAMESPACE
                / entry.run_id
                / "result.json"
            )
            result_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_result(entry)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def _result_path(self, entry: pipeline.MatrixEntry) -> Path:
        return self.root / pipeline.ARTIFACT_NAMESPACE / entry.run_id / "result.json"

    def _write_result(
        self,
        entry: pipeline.MatrixEntry,
        *,
        negative_marker: object = unittest.mock.sentinel.missing,
    ) -> None:
        model = {
            "model_id": entry.model_id,
            "scene_plan": f"scene::{entry.run_id}",
            "positive_prompt": f"positive::{entry.run_id}",
            "runtime": pipeline.expected_runtime(entry.model_id),
        }
        if negative_marker is not unittest.mock.sentinel.missing:
            model["negative_prompt"] = negative_marker
        result = {
            "schema_version": 1,
            "job_id": entry.run_id,
            "producer": {"agent_id": pipeline.AGENT_ID},
            "inputs": {
                "source_image": {
                    "path": entry.source_path,
                    "sha256": entry.source_sha256,
                }
            },
            "analysis": {},
            "models": [model],
        }
        path = self._result_path(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False)

    def _provenance(self, root: Path, run_id: str) -> dict:
        self.assertEqual(root, self.root.resolve())
        entry = self.entries[run_id]
        return {
            "verified": True,
            "verification_scope": "trusted-workspace-route",
            "cryptographically_signed": False,
            "result_path": (
                pipeline.ARTIFACT_NAMESPACE / entry.run_id / "result.json"
            ).as_posix(),
            "agent_id": pipeline.AGENT_ID,
            "contract_version": "test-contract",
            "contract_fingerprint": "sha256:" + "a" * 64,
            "instruction_bundle_sha256": "b" * 64,
            "models": [entry.model_id],
            "source_image_sha256": entry.source_sha256,
            "article_context_sha256": "c" * 64,
        }

    def test_fixed_schemafix_matrix_and_output_namespace(self) -> None:
        self.assertEqual(len(pipeline.MATRIX), 10)
        self.assertEqual(len({entry.run_id for entry in pipeline.MATRIX}), 10)
        self.assertTrue(all("-schemafix-" in entry.run_id for entry in pipeline.MATRIX))
        self.assertEqual(
            {entry.model_id for entry in pipeline.MATRIX},
            {"alibaba/wan-2.7", "google/veo-3.1-lite"},
        )
        for entry in pipeline.MATRIX:
            paths = pipeline.artifact_paths(self.root, entry)
            self.assertIn("/clipmaker-lite/", paths["video"].as_posix())
            self.assertNotIn("/video/", paths["video"].as_posix())
            self.assertEqual(paths["video"].name, f"{entry.stem}.mp4")

    def test_plan_reads_stamped_prompts_and_writes_only_lite_artifacts(self) -> None:
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ) as provenance:
            rows = pipeline.materialize_plan(self.root)

        self.assertEqual(len(rows), 10)
        self.assertEqual(provenance.call_count, 10)
        for row in rows:
            entry = row["entry"]
            prompt = pipeline.read_json(row["paths"]["prompt"])
            run = pipeline.read_json(row["paths"]["run"])
            self.assertEqual(prompt["prompt"], {"positive": f"positive::{entry.run_id}"})
            self.assertNotIn("negative", prompt["prompt"])
            self.assertNotIn("url", json.dumps(run).lower())
            pipeline.assert_sanitized_metadata(prompt)
            pipeline.assert_sanitized_metadata(run)
        self.assertFalse((self.root / "PROMOPAGES-9857/articles/video").exists())
        manifest = pipeline.read_json(self.root / pipeline.MANIFEST_RELATIVE_PATH)
        self.assertEqual(manifest["expected_outputs"], 10)
        self.assertEqual(manifest["summary"], {"pending": 10})
        pipeline.assert_sanitized_metadata(manifest)

    def test_unverified_or_wrong_agent_provenance_is_rejected(self) -> None:
        entry = pipeline.MATRIX[0]
        bad = self._provenance(self.root.resolve(), entry.run_id)
        bad["verified"] = False
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            return_value=bad,
        ):
            with self.assertRaisesRegex(pipeline.LiteGenerationError, "not verified"):
                pipeline.load_lite_job(self.root, entry)

        bad["verified"] = True
        bad["agent_id"] = "clipmaker-classic"
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            return_value=bad,
        ):
            with self.assertRaisesRegex(pipeline.LiteGenerationError, "Unexpected Lite producer"):
                pipeline.load_lite_job(self.root, entry)

    def test_native_runtime_and_explicit_null_negative_parameter(self) -> None:
        wan = next(entry for entry in pipeline.MATRIX if entry.model_id == "alibaba/wan-2.7")
        veo = next(entry for entry in pipeline.MATRIX if entry.model_id == "google/veo-3.1-lite")
        self._write_result(wan, negative_marker="exact wan repair")
        self._write_result(veo, negative_marker=None)
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            wan_job = pipeline.load_lite_job(self.root, wan)
            veo_job = pipeline.load_lite_job(self.root, veo)

        wan_payload = pipeline.provider_request(wan_job)
        veo_payload = pipeline.provider_request(veo_job)
        self.assertEqual(wan_payload["duration"], 5)
        self.assertEqual(wan_payload["resolution"], "1080p")
        self.assertIs(wan_payload["generate_audio"], False)
        self.assertEqual(
            wan_payload["provider"]["options"]["atlas-cloud"]["parameters"],
            {"prompt_extend": True, "negative_prompt": "exact wan repair"},
        )
        self.assertEqual(veo_payload["duration"], 4)
        self.assertEqual(veo_payload["resolution"], "1080p")
        self.assertIs(veo_payload["generate_audio"], False)
        self.assertEqual(
            veo_payload["provider"]["options"]["google-vertex"]["parameters"],
            {"enhancePrompt": True},
        )
        self.assertEqual(wan_payload["prompt"], f"positive::{wan.run_id}")
        self.assertIn("image_url", wan_payload["frame_images"][0])
        self.assertNotIn("image_url", pipeline.sanitized_request(wan_job)["frame_images"][0])

    def test_blank_negative_prompt_is_rejected(self) -> None:
        entry = pipeline.MATRIX[0]
        self._write_result(entry, negative_marker="   ")
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            with self.assertRaisesRegex(
                pipeline.LiteGenerationError,
                "null or a non-empty string",
            ):
                pipeline.load_lite_job(self.root, entry)

    def test_dry_run_revalidates_each_job_and_never_calls_transport(self) -> None:
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ) as provenance:
            rows = pipeline.materialize_plan(self.root)
            selected = rows[:2]
            with (
                mock.patch.object(pipeline.provider_transport, "eliza_headers") as headers,
                mock.patch.object(pipeline.provider_transport, "http_json") as http_json,
                mock.patch.object(pipeline.provider_transport, "eliza_poll") as poll,
                mock.patch.object(pipeline.provider_transport, "http_download") as download,
            ):
                failures = pipeline.run_rows(
                    self.root,
                    selected,
                    dry_run=True,
                    base_url="https://provider.invalid",
                    timeout=1,
                    poll_interval=0,
                    fail_fast=True,
                    external_processing_approved=False,
                )

        self.assertEqual(failures, 0)
        self.assertEqual(provenance.call_count, 12)
        headers.assert_not_called()
        http_json.assert_not_called()
        poll.assert_not_called()
        download.assert_not_called()
        for row in selected:
            self.assertEqual(pipeline.read_json(row["paths"]["run"])["status"], "dry-run")

    def test_resume_uses_existing_provider_job_without_paid_submit(self) -> None:
        entry = pipeline.MATRIX[0]
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            row = pipeline.materialize_plan(self.root)[0]
            run = pipeline.read_json(row["paths"]["run"])
            run.update(
                {
                    "status": "submitted",
                    "provider_job_id": "existing-job-123",
                    "submitted_at": "2026-07-22T10:00:00Z",
                }
            )
            pipeline.write_json(row["paths"]["run"], run)

            def fake_download(url: str, destination: Path, **_: object) -> None:
                self.assertIn("existing-job-123", url)
                destination.write_bytes(b"fake mp4")

            fake_media = {
                "container": "mov,mp4",
                "codec": "h264",
                "duration_seconds": 5.0,
                "width": 1440,
                "height": 1080,
                "fps": 30.0,
                "frames": 150,
                "has_audio": False,
                "bytes": 8,
                "sha256": "d" * 64,
            }
            with (
                mock.patch.object(
                    pipeline.provider_transport,
                    "eliza_headers",
                    return_value={"Authorization": "secret"},
                ),
                mock.patch.object(pipeline.provider_transport, "http_json") as submit,
                mock.patch.object(pipeline.provider_transport, "eliza_poll", return_value={"status": "done"}) as poll,
                mock.patch.object(pipeline.provider_transport, "http_download", side_effect=fake_download),
                mock.patch.object(pipeline.provider_transport, "ffprobe_media", return_value=fake_media),
            ):
                pipeline._run_one(
                    self.root,
                    row,
                    dry_run=False,
                    base_url="https://provider.invalid",
                    timeout=1,
                    poll_interval=0,
                    external_processing_approved=True,
                )

        submit.assert_not_called()
        poll.assert_called_once()
        completed = pipeline.read_json(row["paths"]["run"])
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["provider_job_id"], "existing-job-123")
        self.assertNotIn("Authorization", json.dumps(completed))
        self.assertNotIn("provider.invalid", json.dumps(completed))
        self.assertEqual(entry.model_id, "alibaba/wan-2.7")

    def test_unknown_submit_outcome_blocks_automatic_retry(self) -> None:
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            row = pipeline.materialize_plan(self.root)[0]
            with (
                mock.patch.object(
                    pipeline.provider_transport,
                    "eliza_headers",
                    return_value={"Authorization": "secret"},
                ),
                mock.patch.object(
                    pipeline.provider_transport,
                    "http_json",
                    side_effect=RuntimeError("timeout after POST https://signed.example/video?sig=secret"),
                ) as submit,
            ):
                with self.assertRaisesRegex(pipeline.LiteGenerationError, "automatic retry is blocked"):
                    pipeline._run_one(
                        self.root,
                        row,
                        dry_run=False,
                        base_url="https://provider.invalid",
                        timeout=1,
                        poll_interval=0,
                        external_processing_approved=True,
                    )
                with self.assertRaisesRegex(pipeline.LiteGenerationError, "paid submit will not repeat"):
                    pipeline._run_one(
                        self.root,
                        row,
                        dry_run=False,
                        base_url="https://provider.invalid",
                        timeout=1,
                        poll_interval=0,
                        external_processing_approved=True,
                    )

        self.assertEqual(submit.call_count, 1)
        blocked = pipeline.read_json(row["paths"]["run"])
        self.assertEqual(blocked["status"], "submit-unknown")
        self.assertNotIn("signed.example", json.dumps(blocked))
        self.assertNotIn("secret", json.dumps(blocked))

    def test_dns_resolution_failure_is_pre_submit_and_retryable(self) -> None:
        dns_error = (
            "POST https://provider.invalid/videos failed: [Errno 8] "
            "nodename nor servname provided, or not known"
        )
        self.assertTrue(pipeline.is_definitive_dns_pre_submit_failure(dns_error))
        self.assertFalse(
            pipeline.is_definitive_dns_pre_submit_failure(
                "POST https://provider.invalid/videos failed with HTTP 502: "
                "name or service not known"
            )
        )
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            row = pipeline.materialize_plan(self.root)[0]
            with (
                mock.patch.object(
                    pipeline.provider_transport,
                    "eliza_headers",
                    return_value={"Authorization": "secret"},
                ),
                mock.patch.object(
                    pipeline.provider_transport,
                    "http_json",
                    side_effect=RuntimeError(dns_error),
                ) as submit,
            ):
                for _ in range(2):
                    with self.assertRaisesRegex(pipeline.LiteGenerationError, "safe to retry"):
                        pipeline._run_one(
                            self.root,
                            row,
                            dry_run=False,
                            base_url="https://provider.invalid",
                            timeout=1,
                            poll_interval=0,
                            external_processing_approved=True,
                        )

        self.assertEqual(submit.call_count, 2)
        retryable = pipeline.read_json(row["paths"]["run"])
        self.assertEqual(retryable["status"], "failed-pre-submit")
        self.assertIsNone(retryable["provider_job_id"])
        self.assertNotIn("provider.invalid", json.dumps(retryable))

    def test_reconcile_migrates_only_proven_dns_without_provider_id(self) -> None:
        dns_error = (
            "POST [REDACTED_URL] failed: [Errno 8] "
            "nodename nor servname provided, or not known"
        )
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            rows = pipeline.materialize_plan(self.root)
            safe_dns, ambiguous, has_provider_id, missing_provider_field = rows[:4]
            cases = (
                (safe_dns, dns_error, None),
                (ambiguous, "POST [REDACTED_URL] failed: timed out", None),
                (has_provider_id, dns_error, "possibly-submitted-job"),
            )
            for row, error, provider_job_id in cases:
                run = pipeline.read_json(row["paths"]["run"])
                run.update(
                    {
                        "status": "submit-unknown",
                        "provider_job_id": provider_job_id,
                        "error": error,
                    }
                )
                pipeline.write_json(row["paths"]["run"], run)
            missing_run = pipeline.read_json(missing_provider_field["paths"]["run"])
            missing_run.update({"status": "submit-unknown", "error": dns_error})
            del missing_run["provider_job_id"]
            pipeline.write_json(missing_provider_field["paths"]["run"], missing_run)
            pipeline.materialize_plan(self.root)

        self.assertEqual(
            pipeline.read_json(safe_dns["paths"]["run"])["status"],
            "failed-pre-submit",
        )
        self.assertEqual(
            pipeline.read_json(ambiguous["paths"]["run"])["status"],
            "submit-unknown",
        )
        self.assertEqual(
            pipeline.read_json(has_provider_id["paths"]["run"])["status"],
            "submit-unknown",
        )
        self.assertEqual(
            pipeline.read_json(missing_provider_field["paths"]["run"])["status"],
            "submit-unknown",
        )

    def test_verify_accepts_only_explicitly_allowed_incomplete_plan(self) -> None:
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            pipeline.materialize_plan(self.root)
            allowed, allowed_errors = pipeline.verify_materialized(
                self.root,
                allow_incomplete=True,
            )
            strict, strict_errors = pipeline.verify_materialized(
                self.root,
                allow_incomplete=False,
            )
        self.assertTrue(allowed, allowed_errors)
        self.assertFalse(strict)
        self.assertTrue(any("Not succeeded" in error for error in strict_errors))

    def test_real_run_requires_explicit_external_processing_consent(self) -> None:
        with mock.patch.object(
            pipeline.clipmaker_lite_runner,
            "provenance_summary",
            side_effect=self._provenance,
        ):
            row = pipeline.materialize_plan(self.root)[0]
            with (
                mock.patch.object(pipeline.provider_transport, "eliza_headers") as headers,
                mock.patch.object(pipeline.provider_transport, "http_json") as submit,
            ):
                with self.assertRaisesRegex(
                    pipeline.LiteGenerationError,
                    "requires --allow-external-processing",
                ):
                    pipeline._run_one(
                        self.root,
                        row,
                        dry_run=False,
                        base_url="https://provider.invalid",
                        timeout=1,
                        poll_interval=0,
                        external_processing_approved=False,
                    )
        headers.assert_not_called()
        submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
