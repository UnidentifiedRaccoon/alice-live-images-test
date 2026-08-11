from __future__ import annotations

import argparse
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v5_retry_video_pipeline as video


def source_wan_entry(key: str = "18#05::alibaba/wan-2.7") -> video.Entry:
    inventory = video.v5_generation.load_inventory("9.80", root=video.ROOT)
    source = next(
        entry
        for entry in inventory.entries
        if f"{entry.case_id}::{entry.model_id}" == key
    )
    outputs = video._source_outputs(  # noqa: SLF001
        video.read_json(video.ROOT / video.SOURCE_GENERATION_MANIFEST_REL)
    )
    return video._entry_from_v5(source, root=video.ROOT, source_output=outputs[key])  # noqa: SLF001


class TuneV5RetryVideoTests(unittest.TestCase):
    def test_frozen_matrix_and_budget(self) -> None:
        self.assertEqual(len(video.EXPECTED_KEYS), 8)
        self.assertEqual(sum(video.EXPECTED_BY_MODEL.values()), 8)
        self.assertEqual(video.aggregate_budget_document()["hard_incremental_budget_cap_usd"], 2.8)
        self.assertEqual(video.validate_subset_budget("1.40", 4)["selected_output_count"], 4)
        with self.assertRaisesRegex(video.TuneV5RetryVideoError, "require exact"):
            video.validate_subset_budget("2.80", 4)

    def test_subset_filters_make_two_disjoint_four_target_groups(self) -> None:
        entries = tuple(
            mock.Mock(model_id=model_id, evaluation_id=key)
            for key in sorted(video.EXPECTED_KEYS)
            for model_id in [key.split("::", 1)[1]]
        )
        non_wan22 = video.select_entries(
            entries,
            model_ids=[],
            exclude_models=["alibaba/wan-2.2"],
            targets=[],
        )
        wan22 = video.select_entries(
            entries,
            model_ids=["alibaba/wan-2.2"],
            exclude_models=[],
            targets=[],
        )
        self.assertEqual(len(non_wan22), 4)
        self.assertEqual(len(wan22), 4)
        self.assertFalse({entry.evaluation_id for entry in non_wan22} & {entry.evaluation_id for entry in wan22})

    def test_wan27_uses_exact_commit_pinned_uniform_scale_source(self) -> None:
        entry = source_wan_entry()
        expected = video.NORMALIZED_ASSETS["18#05"]
        self.assertEqual(entry.provider_source_path, expected["path"])
        self.assertEqual(entry.provider_source_url, expected["url"])
        self.assertEqual(entry.provider_source_sha256, expected["sha256"])
        self.assertEqual((entry.provider_width, entry.provider_height), (882, 256))
        self.assertEqual(entry.normalized_source["strategy"], "uniform-scale-source")
        self.assertNotIn("compositor", str(entry.normalized_source).lower())

    def test_wan_prompt_text_is_byte_exact_r4_and_new_run_id(self) -> None:
        key = "18#05::alibaba/wan-2.7"
        entry = source_wan_entry(key)
        source_inventory = video.v5_generation.load_inventory("9.80", root=video.ROOT)
        source = next(
            item for item in source_inventory.entries if f"{item.case_id}::{item.model_id}" == key
        )
        self.assertEqual(entry.positive_prompt.encode("utf-8"), source.positive_prompt.encode("utf-8"))
        self.assertEqual(entry.scene_plan.encode("utf-8"), source.scene_plan.encode("utf-8"))
        self.assertNotEqual(entry.provider_run_id, source.provider_run_id)
        self.assertTrue(entry.provider_run_id.startswith(video.BATCH_ID + "-"))

    def test_dry_run_calls_no_provider_and_records_zero_submissions(self) -> None:
        entry = source_wan_entry()
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            operations = video.ProviderOperations(
                eliza_headers=mock.Mock(),
                http_json=mock.Mock(),
                eliza_poll=mock.Mock(),
                http_download=mock.Mock(),
                segmind_generate=mock.Mock(),
                media_probe=mock.Mock(),
            )
            args = argparse.Namespace(
                dry_run=True,
                timeout=1,
                poll_interval=0.01,
                segmind_base_url="https://segmind.invalid",
                eliza_base_url="https://eliza.invalid",
            )
            result = video.run_provider_worker(
                {"entry": entry}, args, output_root=output_root, operations=operations
            )
            self.assertFalse(result.failed)
            run = video.read_json(video.artifact_paths(entry, output_root)["run"])
            self.assertEqual(run["status"], "dry-run")
            self.assertEqual(run["submission_count"], 0)
            operations.eliza_headers.assert_not_called()
            operations.http_json.assert_not_called()
            operations.segmind_generate.assert_not_called()

    def test_prior_submit_unknown_requires_explicit_inactive_ack(self) -> None:
        fake = mock.Mock()
        fake.entries = tuple(
            mock.Mock(
                model_id="alibaba/wan-2.2",
                evaluation_id=video.SUBMIT_UNKNOWN_KEY,
                provider_run_id="new-run",
            )
            for _ in range(1)
        )
        with mock.patch.object(video, "load_inventory", return_value=fake):
            with self.assertRaisesRegex(video.TuneV5RetryVideoError, "capacity 1"):
                video.run_batch(
                    "0.35",
                    dry_run=False,
                    model_ids=[],
                    exclude_models=[],
                    targets=[video.SUBMIT_UNKNOWN_KEY],
                    allow_external_processing=True,
                )

    def test_any_wan22_subset_is_blocked_while_prior_submit_unknown_holds_route(self) -> None:
        entries = tuple(
            mock.Mock(
                model_id="alibaba/wan-2.2",
                evaluation_id=f"18#{image_id}::alibaba/wan-2.2",
                provider_run_id=f"new-{image_id}",
            )
            for image_id in ("05", "06", "07")
        )
        fake = mock.Mock(entries=entries)
        operations = mock.Mock()
        with mock.patch.object(video, "load_inventory", return_value=fake):
            with self.assertRaisesRegex(video.TuneV5RetryVideoError, "holds that route slot"):
                video.run_batch(
                    "1.05",
                    dry_run=False,
                    targets=[entry.evaluation_id for entry in entries],
                    allow_external_processing=True,
                    operations=operations,
                )
        operations.assert_not_called()

    def test_terminal_attempt_consumes_one_submit_and_never_resubmits_same_run_id(self) -> None:
        entry = next(
            item
            for item in video.load_inventory(root=video.ROOT).entries
            if item.evaluation_id == "07#06::google/veo-3.1-lite"
        )
        operations = video.ProviderOperations(
            eliza_headers=mock.Mock(return_value={}),
            http_json=mock.Mock(return_value={"id": "job-1"}),
            eliza_poll=mock.Mock(side_effect=video.transport.ProviderTerminalError("terminal")),
            http_download=mock.Mock(),
            segmind_generate=mock.Mock(),
            media_probe=mock.Mock(),
        )
        args = argparse.Namespace(
            dry_run=False,
            timeout=1,
            poll_interval=0.01,
            segmind_base_url="https://segmind.invalid",
            eliza_base_url="https://eliza.invalid",
        )
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary)
            first = video.run_provider_worker(
                {"entry": entry}, args, output_root=output_root, operations=operations
            )
            second = video.run_provider_worker(
                {"entry": entry}, args, output_root=output_root, operations=operations
            )
            run = video.read_json(video.artifact_paths(entry, output_root)["run"])
        self.assertTrue(first.failed)
        self.assertEqual(first.status, "provider-failed")
        self.assertTrue(second.failed)
        self.assertEqual(second.status, "provider-failed")
        self.assertEqual(run["submission_count"], 1)
        self.assertEqual(operations.http_json.call_count, 1)
        operations.http_download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
