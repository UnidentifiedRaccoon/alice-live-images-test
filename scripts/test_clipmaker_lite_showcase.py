import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "clipmaker-lite-test" / "manifest.json"
MODEL_IDS = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
]
NAVIGATION_PAGES = [
    ROOT / "index.html",
    ROOT / "generated-gallery.html",
    ROOT / "model-comparison-5s" / "index.html",
    ROOT / "manual-review" / "index.html",
    ROOT / "clipmaker-lite" / "index.html",
]


class ClipmakerLiteShowcaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_contains_exact_20_by_3_dataset(self):
        manifest = self.manifest
        articles = manifest["articles"]
        expected_numbers = [f"{number:02d}" for number in range(1, 21)]

        self.assertEqual(manifest["article_count"], 20)
        self.assertEqual(manifest["expected_outputs"], 60)
        self.assertEqual(len(articles), 20)
        self.assertEqual(len(manifest["outputs"]), 60)
        self.assertEqual([article["article_number"] for article in articles], expected_numbers)

        prompts = []
        video_paths = []
        source_paths = []

        for article in articles:
            outputs = article["outputs"]
            self.assertEqual([output["model_id"] for output in outputs], MODEL_IDS)
            self.assertEqual(len({output["model_id"] for output in outputs}), 3)

            source_path = article["selected_image"]["source_path"]
            self.assertNotIn("Prepared videos", source_path)
            self.assertTrue((ROOT / source_path).is_file(), source_path)
            source_paths.append(source_path)

            for output in outputs:
                prompt = output["positive_prompt"]
                video_path = output["video_path"]

                self.assertTrue(prompt.strip(), f"Empty prompt: {article['article_number']}")
                self.assertNotIn("Prepared videos", video_path)
                self.assertEqual(Path(video_path).suffix.lower(), ".mp4")
                self.assertTrue((ROOT / video_path).is_file(), video_path)
                self.assertGreater((ROOT / video_path).stat().st_size, 0, video_path)

                prompts.append(prompt)
                video_paths.append(video_path)

        self.assertEqual(len(prompts), 60)
        self.assertEqual(len(video_paths), 60)
        self.assertEqual(len(set(video_paths)), 60)
        self.assertEqual(len(source_paths), 20)

    def test_selected_assets_are_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        tracked = {path for path in result.stdout.decode("utf-8").split("\0") if path}
        selected_assets = {
            article["selected_image"]["source_path"]
            for article in self.manifest["articles"]
        }
        selected_assets.update(
            output["video_path"]
            for article in self.manifest["articles"]
            for output in article["outputs"]
        )

        self.assertEqual(len(selected_assets), 80)
        self.assertFalse(selected_assets - tracked, selected_assets - tracked)

    def test_all_demo_pages_keep_step_four_and_add_step_five(self):
        step_pattern = re.compile(r'<span class="viewSwitchStep" lang="en">Step №(\d+)</span>')

        for page in NAVIGATION_PAGES:
            with self.subTest(page=page.relative_to(ROOT)):
                html = page.read_text(encoding="utf-8")
                self.assertEqual(step_pattern.findall(html), ["1", "2", "3", "4", "5"])
                self.assertIn('<strong class="viewSwitchTitle">Разметка</strong>', html)
                self.assertIn('<strong class="viewSwitchTitle">Clipmaker Lite</strong>', html)
                self.assertEqual(html.count('aria-current="page"'), 1)

    def test_showcase_uses_manifest_and_only_renders_active_videos(self):
        app = (ROOT / "clipmaker-lite" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "clipmaker-lite" / "index.html").read_text(encoding="utf-8")

        self.assertIn('const MANIFEST_PATH = "../clipmaker-lite-test/manifest.json";', app)
        self.assertIn('preload="metadata"', app)
        self.assertIn('video.removeAttribute("src")', app)
        self.assertIn('elements.caseViewport.innerHTML = `', app)
        self.assertIn("Воспроизвести все", app)
        self.assertIn("Показать оригинал", app)
        self.assertIn("data-original-src", app)
        self.assertNotIn('poster="', app)
        self.assertNotIn("Prepared videos", app)
        self.assertNotIn("<video", html)
        self.assertIn("8–10 ₽", app)
        self.assertIn("$0.50", app)
        self.assertIn("$0.20", app)

        styles = (ROOT / "clipmaker-lite" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", styles)
        self.assertIn(".sourcePanel[hidden]", styles)


if __name__ == "__main__":
    unittest.main()
