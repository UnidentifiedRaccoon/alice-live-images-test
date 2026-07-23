from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import build_quality_review_data as builder


class QualityReviewDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = builder.build_dataset()
        cls.items = cls.dataset["items"]

    def test_mixed_dataset_is_complete_unique_and_traceable(self) -> None:
        self.assertEqual(self.dataset["schema_version"], 2)
        self.assertEqual(self.dataset["review_ticket"], "PROMOPAGES-9897")
        self.assertEqual(len(self.items), 57)
        self.assertEqual(len({item["id"] for item in self.items}), 57)
        self.assertEqual(len({item["video"]["sha256"] for item in self.items}), 57)
        self.assertEqual(len({item["review_basis_sha256"] for item in self.items}), 57)
        self.assertTrue(
            all(
                item["review_basis_sha256"] == builder.review_basis_sha256(item)
                for item in self.items
            )
        )
        self.assertEqual(self.dataset["data_sha256"], builder.stable_sha256(self.items))
        self.assertIn(
            "promopages-9891-lite3-20260723@f6fdff5dba9a",
            self.dataset["supersedes_dataset_ids"],
        )
        self.assertTrue(all(item["prompt"]["positive"] for item in self.items))
        self.assertTrue(all(item["video"]["sha256"] for item in self.items))

    def test_review_groups_are_ordered_and_have_expected_sizes(self) -> None:
        expected = {
            "clipmaker-lite-current": 15,
            "clipmaker-lite-previous": 15,
            "clipmaker-classic-main": 15,
            "clipmaker-classic-experiments": 12,
        }
        self.assertEqual(
            Counter(item["review_group"]["id"] for item in self.items),
            expected,
        )
        groups = {
            item["review_group"]["id"]: item["review_group"]
            for item in self.items
        }
        self.assertEqual(
            [groups[group_id]["order"] for group_id in expected],
            [0, 1, 2, 3],
        )
        for group in groups.values():
            self.assertEqual(
                set(group), {"id", "label", "short_label", "order"}
            )

    def test_current_lite_ids_and_exact_context_are_preserved(self) -> None:
        current = [
            item
            for item in self.items
            if item["review_group"]["id"] == "clipmaker-lite-current"
        ]
        manifest = json.loads(
            (builder.ROOT / builder.DEFAULT_MANIFEST).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [item["id"] for item in current],
            [output["lite_run_id"] for output in manifest["outputs"]],
        )
        self.assertTrue(all(item["context"]["fragments"] for item in current))
        self.assertTrue(
            all(
                item["context_status"] == {"availability": "shown", "reason": None}
                for item in current
            )
        )
        self.assertTrue(all(item["prompt_author"]["provenance_verified"] for item in current))
        self.assertTrue(all(item["prompt"]["native_for_generation_model"] for item in current))

    def test_historical_context_policy_never_invents_a_fragment(self) -> None:
        previous = [
            item
            for item in self.items
            if item["review_group"]["id"] == "clipmaker-lite-previous"
        ]
        classic = [item for item in self.items if item["prompt_author"]["id"] == "clipmaker-classic"]
        self.assertTrue(all(item["context"] is None for item in previous + classic))
        self.assertTrue(
            all(
                item["context_status"]["availability"] == "omitted_by_review_policy"
                for item in previous
            )
        )
        self.assertTrue(
            all(
                item["context_status"]["availability"] == "not_available_in_artifacts"
                for item in classic
            )
        )

    def test_prompt_authorship_is_explicit_for_both_clipmakers(self) -> None:
        authors = Counter(item["prompt_author"]["id"] for item in self.items)
        self.assertEqual(authors, {"clipmaker-lite": 30, "clipmaker-classic": 27})
        required = {
            "id",
            "label",
            "contract_version",
            "attribution_basis",
            "provenance_verified",
        }
        self.assertTrue(all(set(item["prompt_author"]) == required for item in self.items))
        classic = [item for item in self.items if item["prompt_author"]["id"] == "clipmaker-classic"]
        self.assertTrue(all(item["prompt_author"]["contract_version"] is None for item in classic))
        self.assertTrue(all(not item["prompt_author"]["provenance_verified"] for item in classic))
        self.assertTrue(all(item["agent"]["planning_run_id"] is None for item in classic))

    def test_previous_lite_contains_ten_native_and_five_cross_model_controls(self) -> None:
        previous = [
            item
            for item in self.items
            if item["review_group"]["id"] == "clipmaker-lite-previous"
        ]
        native = [item for item in previous if item["prompt"]["native_for_generation_model"]]
        controls = [item for item in previous if not item["prompt"]["native_for_generation_model"]]
        self.assertEqual(len(native), 10)
        self.assertEqual(len(controls), 5)
        self.assertTrue(
            all(item["approach"]["id"] == "clipmaker-lite-cross-model-control" for item in controls)
        )
        self.assertTrue(all(item["model"]["id"] == "alibaba/wan-2.2" for item in controls))
        self.assertTrue(all(item["prompt"]["source_model_id"] == "alibaba/wan-2.7" for item in controls))
        self.assertTrue(
            all(
                item["prompt_author"]["attribution_basis"]
                == "historical_lite_prompt_reused_cross_model"
                for item in controls
            )
        )

    def test_classic_main_marks_two_wan22_prompt_transfers_as_cross_model(self) -> None:
        transfers = [
            item
            for item in self.items
            if item["prompt_author"]["id"] == "clipmaker-classic"
            and not item["prompt"]["native_for_generation_model"]
        ]
        self.assertEqual(
            {item["model"]["id"] for item in transfers},
            {"alibaba/wan-2.7", "google/veo-3.1-lite"},
        )
        self.assertTrue(
            all(item["prompt"]["source_model_id"] == "alibaba/wan-2.2" for item in transfers)
        )
        self.assertTrue(
            all(item["review_group"]["id"] == "clipmaker-classic-main" for item in transfers)
        )
        classic_source = next(
            source
            for source in self.dataset["sources"]
            if source["id"] == "clipmaker-classic-main"
        )
        self.assertEqual(classic_source["cross_model_transfer_item_count"], 2)

    def test_classic_successes_include_main_and_experiments_but_not_failed_veo(self) -> None:
        classic_main = [
            item
            for item in self.items
            if item["review_group"]["id"] == "clipmaker-classic-main"
        ]
        experiments = [
            item
            for item in self.items
            if item["review_group"]["id"] == "clipmaker-classic-experiments"
        ]
        self.assertEqual(len(classic_main), 15)
        self.assertEqual(len(experiments), 12)
        self.assertTrue(all(item["experiment"] is None for item in classic_main))
        self.assertTrue(all(item["experiment"]["id"] for item in experiments))
        failed_ids = {
            "promopages-9856-classic-portrait-permissive-v1-veo-3.1-lite",
            "promopages-9856-classic-portrait-permissive-v2-veo-3.1-lite",
        }
        self.assertTrue(failed_ids.isdisjoint(item["id"] for item in self.items))
        experiment_source = next(
            source
            for source in self.dataset["sources"]
            if source["id"] == "clipmaker-classic-experiments"
        )
        self.assertEqual(experiment_source["excluded_failed_item_count"], 2)

    def test_prompt_transport_and_provider_transform_are_explicit(self) -> None:
        allowed_transport = {"none", "separate", "embedded_in_positive"}
        self.assertTrue(
            all(item["prompt"]["negative_transport"] in allowed_transport for item in self.items)
        )
        enabled = [
            item
            for item in self.items
            if item["prompt"]["prompt_expansion"]["mode"] == "enabled"
        ]
        self.assertTrue(enabled)
        self.assertEqual(
            {
                item["prompt"]["prompt_expansion"]["parameter"]
                for item in enabled
            },
            {"prompt_extend", "enhancePrompt"},
        )
        controls = [
            item
            for item in self.items
            if item["approach"]["id"] == "clipmaker-lite-cross-model-control"
        ]
        self.assertTrue(
            all(item["prompt"]["prompt_expansion"]["mode"] == "disabled" for item in controls)
        )
        classic = [
            item for item in self.items if item["prompt_author"]["id"] == "clipmaker-classic"
        ]
        self.assertEqual(
            Counter(item["prompt"]["negative_transport"] for item in classic),
            {"embedded_in_positive": 15, "separate": 12},
        )

    def test_all_source_receipts_and_videos_are_still_current(self) -> None:
        for item in self.items:
            video_path = builder.ROOT / item["video"]["path"]
            prompt_path = builder.ROOT / item["source_refs"]["prompt_path"]
            run_path = builder.ROOT / item["source_refs"]["run_path"]
            self.assertEqual(builder.sha256_file(video_path), item["video"]["sha256"])
            self.assertEqual(builder.sha256_file(prompt_path), item["source_refs"]["prompt_sha256"])
            self.assertEqual(builder.sha256_file(run_path), item["source_refs"]["run_sha256"])

    def test_javascript_regeneration_is_deterministic(self) -> None:
        rendered = builder.render_javascript(self.dataset)
        self.assertTrue(rendered.startswith("window.qualityReviewDataset = {"))
        self.assertTrue(rendered.endswith(";\n"))
        with tempfile.TemporaryDirectory() as temporary:
            output_path = Path(temporary) / "review-data.js"
            builder.write_output(self.dataset, output_path)
            self.assertEqual(output_path.read_text(encoding="utf-8"), rendered)
        rebuilt = builder.build_dataset()
        self.assertEqual(builder.render_javascript(rebuilt), rendered)

    def test_workspace_path_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(builder.ReviewDataError):
                builder.workspace_path(Path(temporary), "../escape.json", "fixture")


if __name__ == "__main__":
    unittest.main()
