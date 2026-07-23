from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import build_quality_review_data as builder


class QualityReviewDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = builder.build_dataset()

    def test_current_batch_is_complete_and_traceable(self) -> None:
        self.assertEqual(self.dataset["schema_version"], 1)
        self.assertEqual(self.dataset["review_ticket"], "PROMOPAGES-9897")
        self.assertEqual(len(self.dataset["items"]), 15)
        self.assertEqual(len({item["id"] for item in self.dataset["items"]}), 15)
        self.assertTrue(all(item["agent"]["provenance_verified"] for item in self.dataset["items"]))
        self.assertTrue(all(item["context"]["fragments"] for item in self.dataset["items"]))
        self.assertTrue(all(item["prompt"]["positive"] for item in self.dataset["items"]))
        self.assertTrue(all(item["video"]["sha256"] for item in self.dataset["items"]))

    def test_provider_transform_and_contract_deviations_are_explicit(self) -> None:
        items = self.dataset["items"]
        enabled = [
            item
            for item in items
            if item["prompt"]["prompt_expansion"]["mode"] == "enabled"
        ]
        nonconforming = [item for item in items if not item["provider_contract"]["conforms"]]
        self.assertEqual(len(enabled), 10)
        self.assertEqual(
            {item["prompt"]["prompt_expansion"]["parameter"] for item in enabled},
            {"prompt_extend", "enhancePrompt"},
        )
        self.assertEqual(len(nonconforming), 5)
        self.assertTrue(all(item["model"]["id"] == "alibaba/wan-2.7" for item in nonconforming))
        self.assertTrue(all(item["provider_contract"]["warnings"] for item in nonconforming))

    def test_checked_in_browser_data_is_current(self) -> None:
        checked_in = (builder.ROOT / builder.DEFAULT_OUTPUT).read_text(encoding="utf-8")
        self.assertEqual(checked_in, builder.render_javascript(self.dataset))

    def test_workspace_path_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(builder.ReviewDataError):
                builder.workspace_path(Path(temporary), "../escape.json", "fixture")


if __name__ == "__main__":
    unittest.main()
