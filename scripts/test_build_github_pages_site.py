import tempfile
import unittest
from pathlib import Path

from scripts import build_github_pages_site as pages


ROOT = Path(__file__).resolve().parents[1]


class GitHubPagesSiteTest(unittest.TestCase):
    def test_runtime_allowlist_is_complete_and_within_pages_limits(self):
        paths = pages.collect_site_paths(ROOT)
        total_bytes = pages.site_size(ROOT, paths)

        self.assertEqual(len(paths), 248)
        self.assertGreater(total_bytes, 900_000_000)
        self.assertLessEqual(total_bytes, pages.MAX_SITE_BYTES)
        self.assertIn(Path("clipmaker-lite/index.html"), paths)
        self.assertIn(Path("clipmaker-lite-test/manifest.json"), paths)
        self.assertIn(Path("manual-review/index.html"), paths)
        self.assertFalse(any("Prepared videos" in path.as_posix() for path in paths))
        self.assertEqual(
            [path for path in paths if path.suffix == ".md"],
            [Path("model-comparison-5s/fonts/NOTICE.md")],
        )

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
