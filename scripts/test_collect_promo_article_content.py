from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any


MODULE_PATH = Path(__file__).with_name("collect_promo_article_content.py")
SPEC = importlib.util.spec_from_file_location("collect_promo_article_content", MODULE_PATH)
collector = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(collector)


MISSING = object()


class CollectPromoArticleContentTest(unittest.TestCase):
    def manifest_row(
        self,
        image_number: str,
        image_id: str,
        role: str,
        *,
        block_index: str = "",
        gallery_index: str = "",
        extension: str = "jpeg",
        duplicate_of: str = "",
    ) -> dict[str, str]:
        return {
            "article_number": "01",
            "article_label": "Sample article",
            "article_url": "https://source.example/article",
            "image_number": image_number,
            "image_role": role,
            "block_index": block_index,
            "gallery_index": gallery_index,
            "image_id": image_id,
            "file_path": f"articles/01-sample-article/{image_number}.{extension}",
            "orig_url": f"https://images.example/{image_id}/orig",
            "duplicate_of": duplicate_of,
        }

    def raw_block(
        self,
        block_type: str,
        text: str = "",
        *,
        data: dict[str, Any] | None = None,
        depth: int = 0,
        inline_styles: list[dict[str, Any]] | None = None,
        entity_ranges: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "key": f"block-{block_type}",
            "type": block_type,
            "text": text,
            "depth": depth,
            "data": data or {},
            "inlineStyleRanges": inline_styles or [],
            "entityRanges": entity_ranges or [],
        }

    def page_data(
        self,
        blocks: list[dict[str, Any]],
        *,
        entity_map: dict[str, Any] | None = None,
        lead: str | object = "Source lead",
        cta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        preview: dict[str, Any] = {"title": "Source title"}
        if lead is not MISSING:
            preview["snippet"] = lead
        return {
            "canonicalUrl": "https://canonical.example/article",
            "metaNameDescription": "Forbidden lead fallback",
            "og": {"description": "Another forbidden lead fallback"},
            "publication": {
                "id": "publication-123",
                "version": 7,
                "headImage": {"imageDesktop": {"id": "cover-source"}},
                "swipeToSite": cta
                or {
                    "callToAction": "",
                    "linkToOpen": "",
                    "linkToShow": "",
                },
                "content": {
                    "preview": preview,
                    "articleContent": {
                        "contentState": json.dumps(
                            {
                                "draftJsState": {
                                    "blocks": blocks,
                                    "entityMap": entity_map or {},
                                }
                            },
                            ensure_ascii=False,
                        )
                    },
                },
            },
        }

    def build(
        self,
        rows: list[dict[str, str]],
        page_data: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return collector.build_article_content(
            rows,
            page_data,
            "https://final.example/article",
        )

    def test_extract_page_data_reads_embedded_json_and_rejects_missing_marker(self) -> None:
        expected = {"publication": {"id": "publication-123"}, "images": {}}
        html = (
            "<html><script>const w = window; w._data = "
            + json.dumps(expected)
            + "; window.afterData = true;</script></html>"
        ).encode()

        self.assertEqual(collector.extract_page_data(html), expected)
        with self.assertRaises(ValueError):
            collector.extract_page_data(b"<html>no embedded page data</html>")

    def test_happy_path_preserves_metadata_text_ranges_images_and_cta(self) -> None:
        blocks = [
            self.raw_block(
                "unstyled",
                "Bold link text",
                inline_styles=[{"offset": 0, "length": 4, "style": "BOLD"}],
                entity_ranges=[{"offset": 5, "length": 4, "key": 0}],
            ),
            self.raw_block(
                "atomic:image",
                "Single image caption",
                data={
                    "image": {"id": "single-source", "alt": "must be ignored"},
                    "contents": {"single-source": "wrong caption source"},
                },
            ),
            self.raw_block(
                "atomic:image",
                "Gallery B caption",
                data={
                    "images": [
                        {"id": "gallery-b-source"},
                        {"id": "gallery-a-source"},
                    ],
                    "contents": {
                        "gallery-a-source": "Gallery A caption",
                        "gallery-b-source": "Wrong first-slide caption source",
                    },
                },
            ),
            self.raw_block("header-two", "Second-level heading"),
            self.raw_block("header-three", "Third-level heading"),
            self.raw_block("blockquote", "Quoted text"),
            self.raw_block("unordered-list-item", "List item", depth=2),
            self.raw_block("legal", "Legal text"),
        ]
        rows = [
            self.manifest_row("01", "cover-source", "cover"),
            self.manifest_row(
                "02",
                "single-source",
                "article_image",
                block_index="1",
                extension="png",
            ),
            self.manifest_row(
                "03",
                "gallery-b-source",
                "gallery_image",
                block_index="2",
                gallery_index="0",
                extension="webp",
            ),
            self.manifest_row(
                "04",
                "gallery-a-source",
                "gallery_image",
                block_index="2",
                gallery_index="1",
            ),
        ]
        page_data = self.page_data(
            blocks,
            entity_map={
                "0": {
                    "type": "LINK",
                    "mutability": "MUTABLE",
                    "data": {
                        "href": "https://link.example/ignored-alias",
                        "url": "https://link.example/target",
                    },
                }
            },
            cta={
                "callToAction": "Read more",
                "linkToOpen": "https://cta.example/open",
                "linkToShow": "cta.example/show",
            },
        )

        content, unresolved = self.build(rows, page_data)

        self.assertEqual(unresolved, [])
        self.assertEqual(
            set(content),
            {
                "schema_version",
                "article_number",
                "article_key",
                "article_id",
                "url",
                "final_url",
                "canonical_url",
                "publication_id",
                "publication_version",
                "title",
                "lead",
                "cta",
                "blocks",
            },
        )
        self.assertEqual(content["schema_version"], "1.0")
        self.assertEqual(content["article_number"], 1)
        self.assertEqual(content["article_key"], "01")
        self.assertEqual(content["article_id"], "01-sample-article")
        self.assertEqual(content["url"], "https://source.example/article")
        self.assertEqual(content["final_url"], "https://final.example/article")
        self.assertEqual(content["canonical_url"], "https://canonical.example/article")
        self.assertEqual(content["publication_id"], "publication-123")
        self.assertEqual(content["publication_version"], 7)
        self.assertEqual(content["title"], "Source title")
        self.assertEqual(content["lead"], "Source lead")
        self.assertEqual(
            content["cta"],
            {
                "text": "Read more",
                "link_to_open": "https://cta.example/open",
                "link_to_show": "cta.example/show",
                "included_in_blocks": True,
            },
        )

        output_blocks = content["blocks"]
        self.assertEqual(
            [block["type"] for block in output_blocks],
            [
                "image",
                "paragraph",
                "image",
                "image",
                "image",
                "heading",
                "heading",
                "quote",
                "list_item",
                "legal",
                "cta",
            ],
        )
        self.assertEqual(
            output_blocks[0],
            {
                "type": "image",
                "image_id": "01",
                "file": "01.jpeg",
                "manifest_file_path": "articles/01-sample-article/01.jpeg",
                "role": "cover",
                "source_image_id": "cover-source",
                "source_block_index": None,
                "gallery_index": None,
                "alt": "",
                "caption": "",
                "duplicate_of": None,
            },
        )
        self.assertEqual(
            output_blocks[1],
            {
                "type": "paragraph",
                "source_block_index": 0,
                "text": "Bold link text",
                "inline_styles": [{"offset": 0, "length": 4, "style": "BOLD"}],
                "links": [
                    {
                        "offset": 5,
                        "length": 4,
                        "url": "https://link.example/target",
                    }
                ],
            },
        )
        self.assertEqual(
            output_blocks[2],
            {
                "type": "image",
                "image_id": "02",
                "file": "02.png",
                "manifest_file_path": "articles/01-sample-article/02.png",
                "role": "article_image",
                "source_image_id": "single-source",
                "source_block_index": 1,
                "gallery_index": None,
                "alt": "",
                "caption": "Single image caption",
                "duplicate_of": None,
            },
        )
        self.assertEqual(
            [
                (
                    block["image_id"],
                    block["source_image_id"],
                    block["gallery_index"],
                    block["caption"],
                )
                for block in output_blocks[3:5]
            ],
            [
                ("03", "gallery-b-source", 0, "Gallery B caption"),
                ("04", "gallery-a-source", 1, "Gallery A caption"),
            ],
        )
        self.assertEqual(
            output_blocks[5],
            {
                "type": "heading",
                "source_block_index": 3,
                "text": "Second-level heading",
                "level": 2,
                "inline_styles": [],
                "links": [],
            },
        )
        self.assertEqual(output_blocks[6]["level"], 3)
        self.assertEqual(output_blocks[7]["source_block_index"], 5)
        self.assertEqual(
            output_blocks[8],
            {
                "type": "list_item",
                "source_block_index": 6,
                "text": "List item",
                "list_style": "unordered",
                "depth": 2,
                "inline_styles": [],
                "links": [],
            },
        )
        self.assertEqual(output_blocks[9]["text"], "Legal text")
        self.assertEqual(
            output_blocks[10],
            {
                "type": "cta",
                "source_block_index": None,
                "text": "Read more",
                "url": "https://cta.example/open",
                "inline_styles": [],
                "links": [],
            },
        )

    def test_zero_block_and_gallery_indices_remain_integer_zero(self) -> None:
        rows = [
            self.manifest_row("01", "cover-source", "cover"),
            self.manifest_row(
                "02",
                "gallery-source",
                "gallery_image",
                block_index="0",
                gallery_index="0",
                extension="png",
            ),
        ]
        page_data = self.page_data(
            [
                self.raw_block(
                    "atomic:image",
                    "Zero-index caption",
                    data={
                        "images": [{"id": "gallery-source"}],
                        "contents": {
                            "gallery-source": "Wrong first-slide caption source"
                        },
                    },
                )
            ]
        )

        content, unresolved = self.build(rows, page_data)

        self.assertEqual(unresolved, [])
        gallery = content["blocks"][1]
        self.assertEqual(gallery["source_block_index"], 0)
        self.assertEqual(gallery["gallery_index"], 0)
        self.assertEqual(gallery["caption"], "Zero-index caption")

    def test_gallery_uses_only_images_order_and_ignores_legacy_and_junk_ids(self) -> None:
        rows = [
            self.manifest_row("01", "cover-source", "cover"),
            self.manifest_row(
                "02",
                "gallery-b-source",
                "gallery_image",
                block_index="0",
                gallery_index="0",
            ),
            self.manifest_row(
                "03",
                "gallery-a-source",
                "gallery_image",
                block_index="0",
                gallery_index="1",
            ),
        ]
        page_data = self.page_data(
            [
                self.raw_block(
                    "atomic:image",
                    "Caption B",
                    data={
                        "image": {"id": "gallery-b-source"},
                        "images": [
                            {"id": "gallery-b-source"},
                            {"id": "gallery-a-source"},
                        ],
                        "contents": {
                            "gallery-a-source": "Caption A",
                            "gallery-b-source": "Wrong first-slide caption source",
                            "imageId": "junk-source-that-is-not-an-image",
                        },
                    },
                )
            ]
        )

        content, unresolved = self.build(rows, page_data)

        self.assertEqual(unresolved, [])
        gallery_blocks = [
            block for block in content["blocks"] if block["role"] == "gallery_image"
        ]
        self.assertEqual(len(gallery_blocks), 2)
        self.assertEqual(
            [block["source_image_id"] for block in gallery_blocks],
            ["gallery-b-source", "gallery-a-source"],
        )
        self.assertEqual(
            [block["caption"] for block in gallery_blocks],
            ["Caption B", "Caption A"],
        )

    def test_manifest_and_source_image_mismatch_raises(self) -> None:
        rows = [
            self.manifest_row("01", "cover-source", "cover"),
            self.manifest_row(
                "02",
                "manifest-source",
                "article_image",
                block_index="0",
            ),
        ]
        page_data = self.page_data(
            [
                self.raw_block(
                    "atomic:image",
                    data={"image": {"id": "page-source"}},
                )
            ]
        )

        with self.assertRaises(ValueError):
            self.build(rows, page_data)

    def test_unknown_draft_block_type_raises(self) -> None:
        rows = [self.manifest_row("01", "cover-source", "cover")]
        page_data = self.page_data([self.raw_block("header-one", "Unsupported")])

        with self.assertRaises(ValueError):
            self.build(rows, page_data)

    def test_unknown_referenced_entity_type_raises(self) -> None:
        rows = [self.manifest_row("01", "cover-source", "cover")]
        page_data = self.page_data(
            [
                self.raw_block(
                    "unstyled",
                    "Mention",
                    entity_ranges=[{"offset": 0, "length": 7, "key": 0}],
                )
            ],
            entity_map={
                "0": {
                    "type": "MENTION",
                    "mutability": "IMMUTABLE",
                    "data": {"id": "user-1"},
                }
            },
        )

        with self.assertRaises(ValueError):
            self.build(rows, page_data)

    def test_missing_preview_lead_is_unresolved_without_fallback(self) -> None:
        rows = [self.manifest_row("01", "cover-source", "cover")]
        page_data = self.page_data([], lead=MISSING)
        page_data["publication"]["lead"] = "Forbidden publication fallback"
        page_data["publication"]["content"]["preview"]["description"] = (
            "Forbidden preview fallback"
        )

        content, unresolved = self.build(rows, page_data)

        self.assertEqual(content["lead"], "")
        self.assertEqual(
            unresolved,
            [
                {
                    "article_number": 1,
                    "article_key": "01",
                    "article_id": "01-sample-article",
                    "field": "lead",
                    "source_path": "publication.content.preview.snippet",
                    "reason": "source field is empty; no fallback was generated",
                }
            ],
        )

    def test_empty_cta_is_not_appended_to_blocks(self) -> None:
        rows = [self.manifest_row("01", "cover-source", "cover")]
        page_data = self.page_data([])

        content, unresolved = self.build(rows, page_data)

        self.assertEqual(unresolved, [])
        self.assertEqual(
            content["cta"],
            {
                "text": "",
                "link_to_open": "",
                "link_to_show": "",
                "included_in_blocks": False,
            },
        )
        self.assertEqual([block["type"] for block in content["blocks"]], ["image"])


if __name__ == "__main__":
    unittest.main()
