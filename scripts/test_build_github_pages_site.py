import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import build_github_pages_site as pages


ROOT = Path(__file__).resolve().parents[1]
ADDITIONAL_MANIFEST_PATH = (
    ROOT / "clipmaker-lite-test" / "promopages-9930-manifest.json"
)


class GitHubPagesSiteTest(unittest.TestCase):
    def test_runtime_allowlist_is_complete_and_within_pages_limits(self):
        if not ADDITIONAL_MANIFEST_PATH.is_file():
            self.skipTest("Final PROMOPAGES-9930 manifest has not been produced yet")

        paths = pages.collect_site_paths(ROOT)
        total_bytes = pages.site_size(ROOT, paths)

        self.assertEqual(len(paths), 249)
        self.assertGreater(total_bytes, 900_000_000)
        self.assertLessEqual(total_bytes, pages.MAX_SITE_BYTES)
        self.assertIn(Path("clipmaker-lite/index.html"), paths)
        self.assertIn(Path("clipmaker-lite-test/manifest.json"), paths)
        self.assertIn(
            Path("clipmaker-lite-test/promopages-9930-manifest.json"), paths
        )
        self.assertIn(Path("manual-review/index.html"), paths)
        self.assertFalse(any("Prepared videos" in path.as_posix() for path in paths))
        self.assertEqual(
            [path for path in paths if path.suffix == ".md"],
            [Path("model-comparison-5s/fonts/NOTICE.md")],
        )

    def test_extension_media_is_validated_but_excluded_from_pages_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text(
                "clipmaker-lite-test/manifest.json",
                """{
                  "articles": [{
                    "selected_image": {"source_path": "raw/base.jpg"},
                    "outputs": [],
                    "external_outputs": [{
                      "video_path": "raw/external.mp4",
                      "delivery": "repository-raw"
                    }]
                  }]
                }\n""",
            )
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {"source_path": "raw/source.jpg"},
                      "outputs": [{"video_path": "raw/output.mp4"}]
                    }]
                  }]
                }\n""",
            )
            source_path = root / "raw/source.jpg"
            base_path = root / "raw/base.jpg"
            video_path = root / "raw/output.mp4"
            external_video_path = root / "raw/external.mp4"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(b"source")
            base_path.write_bytes(b"base")
            video_path.write_bytes(b"video")
            external_video_path.write_bytes(b"external-video")

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
            )
            expected_site_files = {*static_files, "raw/base.jpg"}
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)
            self.assertNotIn(Path("raw/source.jpg"), paths)
            self.assertNotIn(Path("raw/output.mp4"), paths)
            self.assertNotIn(Path("raw/external.mp4"), paths)

            external_video_path.unlink()
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaises(FileNotFoundError),
            ):
                pages.collect_site_paths(root)

    def test_rejects_paths_that_can_escape_the_site_root(self):
        for value in ("../secret", "/absolute", "folder/../secret", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    pages._safe_relative_path(value)

    def test_builder_refuses_to_overwrite_an_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                pages.build_site(ROOT, output)


if __name__ == "__main__":
    unittest.main()
