#!/usr/bin/env python3
"""Focused acceptance-policy tests for the PROMOPAGES-9910 wrapper."""

from __future__ import annotations

import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import clipmaker_lite_20x3_pipeline as pipeline
from scripts import video_generation_pipeline as transport


class ClipmakerLite20x3AcceptanceTest(unittest.TestCase):
    def test_frozen_201_bundle_remains_authoritative_after_root_202(self) -> None:
        root_contract = pipeline.read_json(
            pipeline.ROOT / "docs/agents/clipmaker-lite/contract.json"
        )
        frozen_contract = pipeline.require_frozen_lite_bundle(pipeline.TEST_ROOT)

        self.assertEqual(root_contract["contract_version"], "2.0.2")
        self.assertEqual(frozen_contract["contract_version"], "2.0.1")
        self.assertNotEqual(root_contract, frozen_contract)

    def test_prepare_dataset_never_copies_current_lite_files_over_frozen_bundle(self) -> None:
        with (
            mock.patch.object(pipeline, "discover_articles", return_value=()),
            mock.patch.object(pipeline, "copy_exact") as copy_exact,
            mock.patch.object(pipeline, "require_frozen_lite_bundle") as require_frozen,
            mock.patch.object(pipeline, "write_readme"),
            mock.patch.object(pipeline.transport, "atomic_write_json"),
        ):
            pipeline.prepare_dataset(pipeline.ROOT)

        destinations = {call.args[1] for call in copy_exact.call_args_list}
        for relative_path in pipeline.FROZEN_LITE_FILES:
            self.assertNotIn(pipeline.TEST_ROOT / relative_path, destinations)
        require_frozen.assert_called_once_with(pipeline.TEST_ROOT)

    def test_historical_native_binding_separates_frozen_planning_from_provider_root(self) -> None:
        mutable_names = (
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
        with ExitStack() as stack:
            for name in mutable_names:
                stack.enter_context(
                    mock.patch.object(
                        pipeline.native,
                        name,
                        getattr(pipeline.native, name),
                    )
                )
            pipeline.configure_native(())
            self.assertEqual(pipeline.native.PLANNING_WORKSPACE, pipeline.TEST_ROOT)
            self.assertIs(
                pipeline.native.PLANNING_PROVENANCE_VERIFIER,
                pipeline.frozen_provenance_summary,
            )
            self.assertEqual(
                pipeline.native.CONTRACT_PATH,
                pipeline.TEST_ROOT / "docs/agents/clipmaker-lite/contract.json",
            )

    def test_generate_defaults_to_all_three_routes_and_forwards_pool_limits(self) -> None:
        with (
            mock.patch.object(pipeline, "configure_native") as configure,
            mock.patch.object(pipeline.native, "main", return_value=0) as native_main,
        ):
            result = pipeline.run_generation(
                (),
                concurrency=1,
                wan22_concurrency=1,
                wan27_concurrency=2,
                veo31_concurrency=3,
                timeout=30,
                poll_interval=0.0,
                dry_run=True,
                fail_fast=False,
            )

        self.assertEqual(result, 0)
        configure.assert_called_once_with(())
        argv, root = native_main.call_args.args
        self.assertIs(root, pipeline.ROOT)
        self.assertIn("--dry-run", argv)
        self.assertEqual(
            [argv[index + 1] for index, value in enumerate(argv) if value == "--model"],
            list(pipeline.MODEL_IDS),
        )
        for flag, expected in (
            ("--wan22-concurrency", "1"),
            ("--wan27-concurrency", "2"),
            ("--veo31-concurrency", "3"),
        ):
            self.assertEqual(argv[argv.index(flag) + 1], expected)

    def test_wan_selection_uses_legacy_retry5_success_without_hiding_history(self) -> None:
        primary = {"provider_run_id": "primary", "status": "provider-failed"}
        retry1 = {"provider_run_id": "retry1", "status": "provider-failed"}
        retry2 = {"provider_run_id": "retry2", "status": "provider-failed"}
        retry3 = {"provider_run_id": "retry3", "status": "succeeded"}
        legacy_retry5 = {
            "provider_run_id": "legacy-retry5",
            "status": "succeeded",
        }

        selected = pipeline.select_wan_attempt(
            primary=primary,
            retry1=retry1,
            retry2=retry2,
            retry3=retry3,
            legacy_retry5=legacy_retry5,
        )

        self.assertIs(selected, legacy_retry5)
        primary["status"] = "succeeded"
        self.assertIs(
            pipeline.select_wan_attempt(
                primary=primary,
                retry1=retry1,
                retry2=retry2,
                retry3=retry3,
                legacy_retry5=legacy_retry5,
            ),
            primary,
        )

    def raw_output(self, root: Path) -> dict[str, object]:
        video = root / "raw.mp4"
        video.write_bytes(b"raw provider mp4")
        return {
            "provider_run_id": "raw-wan-27",
            "status": "verification-failed",
            "video_path": "raw.mp4",
            "media": {
                "width": 1930,
                "height": 1074,
                "duration_seconds": 5.0,
                "has_audio": True,
                "bytes": video.stat().st_size,
                "sha256": "a" * 64,
            },
            "contract_check": {
                "requested": {
                    "duration_seconds": 5,
                    "resolution": "1080p",
                    "aspect_ratio": "16:9",
                    "generate_audio": False,
                },
                "checks": {
                    "duration": True,
                    "audio": False,
                    "resolution": False,
                    "aspect_ratio": True,
                },
                "conforms": False,
                "warnings": ["audio", "resolution"],
            },
            "error": "Media contract verification failed: audio, resolution",
        }

    def document(self, output: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": 1,
            "updated_at": "fixed",
            "expected_outputs": 1,
            "status_summary": {"verification-failed": 1},
            "outputs": [output],
        }

    def test_raw_output_is_accepted_only_by_explicit_warning_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = self.raw_output(root)
            original = copy.deepcopy(output)

            strict_error = pipeline.final_output_acceptance_error(
                output,
                allow_contract_warnings=False,
                root=root,
            )
            warning_error = pipeline.final_output_acceptance_error(
                output,
                allow_contract_warnings=True,
                root=root,
            )

            self.assertIn("warnings were not allowed", strict_error or "")
            self.assertIsNone(warning_error)
            self.assertEqual(output, original)
            self.assertEqual(output["status"], "verification-failed")
            self.assertFalse(output["contract_check"]["conforms"])
            self.assertEqual(
                output["contract_check"]["warnings"],
                ["audio", "resolution"],
            )

    def test_warning_policy_rejects_missing_or_incomplete_provider_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = self.raw_output(root)
            (root / "raw.mp4").unlink()
            self.assertIn(
                "MP4 is missing",
                pipeline.final_output_acceptance_error(
                    output,
                    allow_contract_warnings=True,
                    root=root,
                )
                or "",
            )
            (root / "raw.mp4").write_bytes(b"raw provider mp4")
            for status in ("dry-run", "running", "provider-failed"):
                output["status"] = status
                self.assertIn(
                    "is not a generated final output",
                    pipeline.final_output_acceptance_error(
                        output,
                        allow_contract_warnings=True,
                        root=root,
                    )
                    or "",
                )

    def test_finalize_threads_explicit_policy_without_mutating_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self.document(self.raw_output(root))
            original = copy.deepcopy(document)
            with (
                mock.patch.object(pipeline, "ROOT", root),
                mock.patch.object(pipeline, "FINAL_MANIFEST_REL", Path("manifest.json")),
                mock.patch.object(pipeline, "sync_planning_artifacts"),
                mock.patch.object(pipeline, "build_final_manifest", return_value=document),
            ):
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.finalize((), allow_contract_warnings=False)
                result = pipeline.finalize((), allow_contract_warnings=True)

            self.assertEqual(result, original)
            self.assertEqual(document, original)
            self.assertTrue((root / "manifest.json").is_file())

    def test_verify_all_does_not_let_retry_history_mask_primary_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self.document(self.raw_output(root))
            final_path = Path("manifest.json")
            retry_path = Path("retry1.json")
            report_path = Path("verification.json")
            transport.atomic_write_json(root / final_path, document)
            transport.atomic_write_json(root / retry_path, {"outputs": []})
            article = SimpleNamespace(sample=SimpleNamespace(planning_run_id="lite-run"))
            for workspace in (root, root / "self-contained"):
                result = (
                    workspace
                    / pipeline.native.ARTIFACT_NAMESPACE
                    / "lite-run"
                    / "result.json"
                )
                result.parent.mkdir(parents=True)
                result.write_text("{}\n", encoding="utf-8")

            patches = (
                mock.patch.object(pipeline, "ROOT", root),
                mock.patch.object(pipeline, "TEST_ROOT", root / "self-contained"),
                mock.patch.object(pipeline, "FINAL_MANIFEST_REL", final_path),
                mock.patch.object(pipeline, "VERIFICATION_REPORT_REL", report_path),
                mock.patch.object(pipeline, "WAN_RETRY1_MANIFEST_REL", retry_path),
                mock.patch.object(pipeline, "WAN_RETRY2_MANIFEST_REL", Path("retry2.json")),
                mock.patch.object(pipeline, "WAN_RETRY3_MANIFEST_REL", Path("retry3.json")),
                mock.patch.object(pipeline, "configure_native"),
                mock.patch.object(pipeline, "configure_wan_retry3"),
                mock.patch.object(
                    pipeline,
                    "verify_dataset",
                    side_effect=lambda _articles: [],
                ),
                mock.patch.object(
                    pipeline,
                    "frozen_provenance_summary",
                    return_value={"verified": True},
                ),
                mock.patch.object(pipeline.native, "verify", return_value=(True, [])),
                mock.patch.object(
                    pipeline,
                    "frozen_wan_retry_articles",
                    return_value=(article,),
                ),
                mock.patch.object(
                    pipeline,
                    "build_final_manifest",
                    return_value=document,
                ),
            )
            with ExitStack() as stack:
                for patcher in patches:
                    stack.enter_context(patcher)
                strict_ok, strict_errors = pipeline.verify_all(
                    (article,),
                    allow_incomplete=False,
                    allow_contract_warnings=False,
                )
                warning_ok, warning_errors = pipeline.verify_all(
                    (article,),
                    allow_incomplete=False,
                    allow_contract_warnings=True,
                )

            self.assertFalse(strict_ok)
            self.assertTrue(
                any("warnings were not allowed" in error for error in strict_errors)
            )
            self.assertTrue(warning_ok, warning_errors)

    def test_finalize_parser_defaults_strict_and_accepts_explicit_flag(self) -> None:
        parser = pipeline.build_parser()
        self.assertFalse(parser.parse_args(["finalize"]).allow_contract_warnings)
        self.assertTrue(
            parser.parse_args(
                ["finalize", "--allow-contract-warnings"]
            ).allow_contract_warnings
        )


if __name__ == "__main__":
    unittest.main()
