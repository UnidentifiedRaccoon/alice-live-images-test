from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("collect_promo_images.py")
SPEC = importlib.util.spec_from_file_location("collect_promo_images", MODULE_PATH)
collector = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
if "PIL" not in sys.modules:
    try:
        import PIL  # noqa: F401
    except ModuleNotFoundError:
        pil_stub = types.ModuleType("PIL")
        pil_stub.Image = object()
        sys.modules["PIL"] = pil_stub
sys.modules[SPEC.name] = collector
SPEC.loader.exec_module(collector)


class CollectPromoImagesTest(unittest.TestCase):
    def article_list(self, path: Path, *, folder: str = "01-sample-article") -> None:
        path.write_text(
            json.dumps(
                [
                    {
                        "number": 1,
                        "label": "Sample article",
                        "folder": folder,
                        "url": "https://source.example/article",
                    }
                ]
            ),
            encoding="utf-8",
        )

    def page_data(self) -> dict[str, object]:
        return {
            "publication": {
                "headImage": {"imageDesktop": {"id": "cover-source"}},
                "content": {
                    "articleContent": {
                        "contentState": json.dumps(
                            {"draftJsState": {"blocks": []}}
                        )
                    }
                },
            },
            "images": {
                "cover-source": {
                    "namespace": "promo-pages",
                    "groupId": "group-1",
                    "imageName": "cover-source",
                    "meta": {"origFormat": "JPEG"},
                    "sizes": {"orig": {"width": 16, "height": 9}},
                }
            },
        }

    def test_external_article_list_and_optional_prefix_control_output_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            article_list = root / "articles.json"
            self.article_list(article_list)
            articles = collector.load_articles(article_list)

            def fake_fetch(url: str) -> tuple[bytes, str, str]:
                if url == articles[0].url:
                    return b"article", "text/html", url
                return b"jpeg-payload", "image/jpeg", url

            for prefix, expected_path in (
                ("", "articles/01-sample-article/01.jpeg"),
                (
                    "PROMOPAGES-10060",
                    "PROMOPAGES-10060/articles/01-sample-article/01.jpeg",
                ),
            ):
                with self.subTest(prefix=prefix):
                    output_root = root / (prefix or "default")
                    with (
                        mock.patch.object(collector, "fetch", side_effect=fake_fetch),
                        mock.patch.object(
                            collector,
                            "extract_page_data",
                            return_value=self.page_data(),
                        ),
                        mock.patch.object(
                            collector,
                            "inspect_image",
                            return_value=("JPEG", 16, 9, "sha256"),
                        ),
                    ):
                        rows = collector.collect(
                            output_root,
                            root / "missing-annotations.json",
                            articles=articles,
                            dataset_prefix=prefix,
                        )

                    self.assertEqual(rows[0]["file_path"], expected_path)
                    self.assertTrue((output_root / expected_path).is_file())
                    manifest_path = (
                        output_root
                        / prefix
                        / "articles"
                        / "manifest.csv"
                    )
                    with manifest_path.open(encoding="utf-8", newline="") as source:
                        manifest_rows = list(csv.DictReader(source))
                    self.assertEqual(manifest_rows[0]["file_path"], expected_path)

    def test_design_zero_omits_legacy_cover_images(self) -> None:
        page_data = self.page_data()
        publication = page_data["publication"]
        assert isinstance(publication, dict)
        publication["headImage"] = {
            "design": {"id": "0"},
            "imageDesktop": {"id": "legacy-desktop"},
            "imageMobile": {"id": "legacy-mobile"},
        }
        publication["content"] = {
            "articleContent": {
                "contentState": json.dumps(
                    {
                        "draftJsState": {
                            "blocks": [
                                {
                                    "type": "atomic:image",
                                    "data": {"image": {"id": "body-source"}},
                                }
                            ]
                        }
                    }
                )
            }
        }

        self.assertEqual(
            collector.image_occurrences(page_data),
            [
                {
                    "image_id": "body-source",
                    "role": "article_image",
                    "block_index": 0,
                    "gallery_index": "",
                }
            ],
        )

    def test_nonzero_design_preserves_cover_images(self) -> None:
        page_data = self.page_data()
        publication = page_data["publication"]
        assert isinstance(publication, dict)
        publication["headImage"] = {
            "design": {"id": "6"},
            "imageDesktop": {"id": "desktop-source"},
            "imageMobile": {"id": "mobile-source"},
        }

        self.assertEqual(
            collector.image_occurrences(page_data),
            [
                {
                    "image_id": "desktop-source",
                    "role": "cover",
                    "block_index": "",
                    "gallery_index": "",
                },
                {
                    "image_id": "mobile-source",
                    "role": "cover_mobile",
                    "block_index": "",
                    "gallery_index": "",
                },
            ],
        )

    def test_prefix_and_article_folder_reject_unsafe_paths(self) -> None:
        for value in ("../escape", "ticket/name", "/absolute", "ticket\\name", "."):
            with self.subTest(prefix=value), self.assertRaises(ValueError):
                collector.normalize_dataset_prefix(value)

        with tempfile.TemporaryDirectory() as temporary:
            article_list = Path(temporary) / "articles.json"
            self.article_list(article_list, folder="../escape")
            with self.assertRaises(ValueError):
                collector.load_articles(article_list)

    def test_exclusion_preserves_original_non_contiguous_article_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            article_list = Path(temporary) / "articles.json"
            article_list.write_text(
                json.dumps(
                    [
                        {
                            "number": number,
                            "label": f"Article {number}",
                            "folder": f"{number:02d}-article",
                            "url": f"https://source.example/article-{number}",
                        }
                        for number in (1, 2, 3)
                    ]
                ),
                encoding="utf-8",
            )

            articles = collector.load_articles(article_list, [2])

            self.assertEqual([article.number for article in articles], [1, 3])
            with self.assertRaisesRegex(ValueError, "absent"):
                collector.load_articles(article_list, [4])


if __name__ == "__main__":
    unittest.main()
