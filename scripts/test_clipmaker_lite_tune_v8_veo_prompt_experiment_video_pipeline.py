from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v8_veo_prompt_experiment_video_pipeline as video


class TuneV8VeoPromptExperimentVideoTests(unittest.TestCase):
    def test_inventory_has_three_unique_requests_with_fixed_controls(self) -> None:
        entries = video.load_inventory(root=video.ROOT)
        self.assertEqual(len(entries), 3)
        self.assertEqual(len({entry.provider_run_id for entry in entries}), 3)
        self.assertEqual(len({entry.positive_prompt for entry in entries}), 3)
        self.assertEqual(
            {entry.source_sha256 for entry in entries},
            {video.planning.CANONICAL_SOURCE_SHA256},
        )
        for entry in entries:
            request = video.provider_request(entry)
            self.assertEqual(request["seed"], video.planning.SHARED_PROVIDER_SEED)
            self.assertEqual(request["prompt"], entry.positive_prompt)
            self.assertFalse(request["generate_audio"])
            self.assertEqual(
                request["provider"]["options"]["google-vertex"]["parameters"],
                {"enhancePrompt": True},
            )

    def test_budget_and_safety_policy_are_exact(self) -> None:
        with self.assertRaisesRegex(video.TuneV8VideoError, "exact budget cap 1.05"):
            video.parse_budget("0.70")
        self.assertEqual(video.parse_budget("1.05"), video.ACCOUNTING_BUDGET_USD)
        for entry in video.load_inventory(root=video.ROOT):
            prompt = video.prompt_artifact(entry)
            self.assertIsNone(prompt["canonical_source"]["transform"])
            self.assertFalse(prompt["policy"]["disable_provider_safety_filters"])
            self.assertIsNone(prompt["policy"]["fallback"])
            self.assertFalse(prompt["policy"]["compositor"])
            self.assertFalse(prompt["policy"]["automatic_paid_retry"])

    def test_dry_run_materializes_three_without_provider_calls(self) -> None:
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
                    "1.05",
                    dry_run=True,
                    root=video.ROOT,
                    output_root=output_root,
                    operations=operations,
                ),
                0,
            )
            manifest = video.read_json(output_root / video.GENERATION_MANIFEST_REL)
        self.assertEqual(manifest["summary"], {"dry-run": 3})
        self.assertEqual(manifest["budget"]["maximum_estimated_cost_usd"], 1.05)
        self.assertEqual(manifest["scheduling"]["worker_count"], 3)
        self.assertTrue(manifest["scheduling"]["start_together"])
        operations.http_json.assert_not_called()

    def test_three_terminal_no_outputs_submit_once_each_and_stop(self) -> None:
        lock = threading.Lock()
        post_prompts: list[str] = []

        def http_json(method: str, _url: str, *args, **_kwargs):
            del _kwargs
            if method == "POST":
                request = args[0]
                with lock:
                    post_prompts.append(request["prompt"])
                    index = len(post_prompts)
                return {"response": {"id": f"job-{index}"}}
            return {
                "response": {
                    "id": "job-terminal",
                    "status": "failed",
                    "error": (
                        "Video generation completed with no output "
                        "(content may have been filtered)"
                    ),
                },
                "request_id": "request-test",
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
                "1.05",
                dry_run=False,
                allow_external_processing=True,
                root=video.ROOT,
                output_root=output_root,
                operations=operations,
                poll_interval=0,
            )
            second = video.run_batch(
                "1.05",
                dry_run=False,
                allow_external_processing=True,
                root=video.ROOT,
                output_root=output_root,
                operations=operations,
                poll_interval=0,
            )
            entries = video.load_inventory(root=video.ROOT)
            runs = [
                video.read_json(video.artifact_paths(entry, output_root)["run"])
                for entry in entries
            ]
        self.assertEqual((first, second), (3, 3))
        self.assertCountEqual(post_prompts, [entry.positive_prompt for entry in entries])
        self.assertEqual(len(post_prompts), 3)
        for run in runs:
            self.assertEqual(run["status"], "provider-failed")
            self.assertEqual(run["submission_count"], 1)
            self.assertFalse(run["provider_may_be_active"])
            self.assertTrue(run["terminal_no_output_stop_applied"])

    def test_safety_diagnostics_are_retained_when_exposed(self) -> None:
        diagnostics = video.v7_video._sanitize_terminal_response(  # noqa: SLF001
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
