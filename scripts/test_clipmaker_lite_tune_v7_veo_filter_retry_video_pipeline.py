from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v7_veo_filter_retry_video_pipeline as video


class TuneV7VeoFilterRetryVideoTests(unittest.TestCase):
    def test_inventory_and_wire_request_are_exact(self) -> None:
        entry = video.load_inventory(root=video.ROOT)
        request = video.provider_request(entry)
        self.assertEqual(entry.evaluation_id, video.EXPECTED_KEY)
        self.assertEqual(entry.source_sha256, video.planning.CANONICAL_SOURCE_SHA256)
        self.assertEqual(request["seed"], 967732034)
        self.assertEqual(request["prompt"], video.planning.EXACT_POSITIVE_PROMPT)
        self.assertFalse(request["generate_audio"])
        self.assertEqual(
            request["provider"]["options"]["google-vertex"]["parameters"],
            {"enhancePrompt": True},
        )

    def test_budget_is_exact_and_no_safety_evasion_is_declared(self) -> None:
        with self.assertRaisesRegex(video.TuneV7VeoRetryError, "exact budget cap"):
            video.parse_budget("0.70")
        prompt = video.prompt_artifact(video.load_inventory(root=video.ROOT))
        self.assertIsNone(prompt["canonical_source"]["transform"])
        self.assertFalse(prompt["policy"]["disable_provider_safety_filters"])
        self.assertIsNone(prompt["policy"]["fallback"])
        self.assertFalse(prompt["policy"]["compositor"])

    def test_dry_run_never_calls_provider(self) -> None:
        operations = video.ProviderOperations(
            eliza_headers=mock.Mock(side_effect=AssertionError("credentials called")),
            http_json=mock.Mock(side_effect=AssertionError("provider called")),
            http_download=mock.Mock(side_effect=AssertionError("download called")),
            media_probe=mock.Mock(side_effect=AssertionError("probe called")),
            sleep=mock.Mock(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            self.assertEqual(
                video.run_batch(
                    "0.35",
                    dry_run=True,
                    root=video.ROOT,
                    output_root=output_root,
                    operations=operations,
                ),
                0,
            )
            manifest = video.read_json(output_root / video.GENERATION_MANIFEST_REL)
        self.assertEqual(manifest["summary"], {"dry-run": 1})
        operations.http_json.assert_not_called()

    def test_terminal_no_output_is_sanitized_and_never_resubmitted(self) -> None:
        calls: list[str] = []

        def http_json(method: str, _url: str, *_args, **_kwargs):
            calls.append(method)
            if method == "POST":
                return {"response": {"id": "job-test"}}
            return {
                "key": "must-not-be-persisted",
                "response": {
                    "id": "job-test",
                    "generation_id": "generation-test",
                    "status": "failed",
                    "error": "Video generation completed with no output (content may have been filtered)",
                },
                "request_id": "request-test",
                "stats": {"cost": "must-not-be-persisted"},
            }

        operations = video.ProviderOperations(
            eliza_headers=mock.Mock(return_value={"Authorization": "redacted"}),
            http_json=mock.Mock(side_effect=http_json),
            http_download=mock.Mock(side_effect=AssertionError("download called")),
            media_probe=mock.Mock(side_effect=AssertionError("probe called")),
            sleep=mock.Mock(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            first = video.run_batch(
                "0.35",
                dry_run=False,
                allow_external_processing=True,
                root=video.ROOT,
                output_root=output_root,
                operations=operations,
                poll_interval=0,
            )
            second = video.run_batch(
                "0.35",
                dry_run=False,
                allow_external_processing=True,
                root=video.ROOT,
                output_root=output_root,
                operations=operations,
                poll_interval=0,
            )
            entry = video.load_inventory(root=video.ROOT)
            run = video.read_json(video.artifact_paths(entry, output_root)["run"])
        self.assertEqual((first, second), (1, 1))
        self.assertEqual(calls.count("POST"), 1)
        self.assertEqual(run["status"], "provider-failed")
        self.assertTrue(run["terminal_no_output_stop_applied"])
        self.assertTrue(run["diagnostics_unavailable_upstream"])
        self.assertEqual(
            run["provider_terminal_diagnostics"]["generation_id"],
            "generation-test",
        )
        self.assertEqual(
            run["provider_terminal_diagnostics"]["request_id"], "request-test"
        )
        self.assertNotIn("key", run["provider_terminal_diagnostics"])
        self.assertNotIn("stats", run["provider_terminal_diagnostics"])

    def test_safety_codes_are_preserved_when_upstream_exposes_them(self) -> None:
        diagnostics = video._sanitize_terminal_response(  # noqa: SLF001
            {
                "response": {
                    "status": "failed",
                    "support_code": "15236754",
                    "raiFilteredReason": "celebrity",
                    "blockedReason": "input image",
                }
            }
        )
        self.assertFalse(diagnostics["diagnostics_unavailable_upstream"])
        self.assertEqual(diagnostics["support_code"], "15236754")


if __name__ == "__main__":
    unittest.main()
