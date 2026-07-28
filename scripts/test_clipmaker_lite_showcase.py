import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "clipmaker-lite-test" / "manifest.json"
ADDITIONAL_MANIFEST_PATH = (
    ROOT / "clipmaker-lite-test" / "promopages-9930-manifest.json"
)
CASE_21_MANIFEST_PATH = ROOT / "clipmaker-lite-test" / "case-21-manifest.json"
MODEL_IDS = [
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
]
CASE14_WAN22_PROMPT_SHA256 = (
    "71352fa20f1bbba882c9900a9656aafd0764fc93d71ca5c6a4cf06c02b82a5ad"
)
CASE14_ELIZA_SEGMIND_MODEL_ID = "segmind/wan-2.2-i2v-flash"
CASE14_ELIZA_SEGMIND_VIDEO_SHA256 = (
    "c4ad82232afee3116fb7f6e60013f7df43c0275bd2325ae8c7a51cb1cb2db7e7"
)
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
        cls.additional_manifest = None
        if ADDITIONAL_MANIFEST_PATH.is_file():
            cls.additional_manifest = json.loads(
                ADDITIONAL_MANIFEST_PATH.read_text(encoding="utf-8")
            )
        cls.case_21_manifest = None
        if CASE_21_MANIFEST_PATH.is_file():
            cls.case_21_manifest = json.loads(
                CASE_21_MANIFEST_PATH.read_text(encoding="utf-8")
            )

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
        comparison_paths = []
        external_paths = []
        source_paths = []

        for article in articles:
            outputs = article["outputs"]
            self.assertEqual([output["model_id"] for output in outputs], MODEL_IDS)
            self.assertEqual(len({output["model_id"] for output in outputs}), 3)

            source_path = article["selected_image"]["source_path"]
            self.assertEqual(article["selected_image"]["image_id"], "01")
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

            if "comparison_outputs" in article:
                comparisons = article["comparison_outputs"]
                self.assertIsInstance(comparisons, list)
                self.assertEqual(article["article_number"], "14")
                self.assertEqual(
                    [output["model_id"] for output in comparisons],
                    MODEL_IDS[1:],
                )
                self.assertEqual(len(comparisons), 2)
                reference_prompt = outputs[0]["positive_prompt"]
                for output in comparisons:
                    self.assertEqual(output["prompt_source_model_id"], MODEL_IDS[0])
                    self.assertEqual(output["positive_prompt"], reference_prompt)
                    self.assertFalse(output["canonical_lite_artifact"])
                    self.assertEqual(
                        output["runtime_prompt_sha256"],
                        CASE14_WAN22_PROMPT_SHA256,
                    )
                    self.assertEqual(
                        hashlib.sha256(output["positive_prompt"].encode("utf-8")).hexdigest(),
                        CASE14_WAN22_PROMPT_SHA256,
                    )
                    if output["model_id"] == "alibaba/wan-2.7":
                        self.assertEqual(
                            output["provider_prompt_expansion"],
                            {"prompt_extend": True},
                        )
                    else:
                        self.assertEqual(
                            output["provider_prompt_expansion"],
                            {"enhancePrompt": True},
                        )
                    video_path = output["video_path"]
                    self.assertNotIn("Prepared videos", video_path)
                    self.assertEqual(Path(video_path).suffix.lower(), ".mp4")
                    self.assertTrue((ROOT / video_path).is_file(), video_path)
                    self.assertGreater((ROOT / video_path).stat().st_size, 0, video_path)
                    self.assertGreater(output["media"]["width"], 0)
                    self.assertGreater(output["media"]["height"], 0)
                    self.assertGreater(output["media"]["duration_seconds"], 0)
                    self.assertGreater(output["media"]["bytes"], 0)
                    comparison_paths.append(video_path)

            if "external_outputs" in article:
                external_outputs = article["external_outputs"]
                self.assertEqual(article["article_number"], "14")
                self.assertEqual(len(external_outputs), 1)
                output = external_outputs[0]
                self.assertEqual(output["model_id"], CASE14_ELIZA_SEGMIND_MODEL_ID)
                self.assertEqual(output["gateway"], "eliza")
                self.assertEqual(output["provider"], "segmind")
                self.assertEqual(output["route_label"], "Eliza → Segmind")
                self.assertEqual(output["delivery"], "repository-raw")
                self.assertEqual(output["actual_cost_usd"], 0.18)
                self.assertEqual(output["request"]["prompt_extend"], False)
                self.assertEqual(output["request"]["watermark"], False)
                self.assertEqual(output["request"]["seed"], 220214)
                self.assertTrue(output["positive_prompt"].strip())
                self.assertTrue(output["negative_prompt"].strip())
                self.assertEqual(output["media"]["width"], 1280)
                self.assertEqual(output["media"]["height"], 720)
                self.assertEqual(output["media"]["frames"], 150)
                self.assertFalse(output["media"]["has_audio"])
                self.assertEqual(output["visual_review"]["status"], "fidelity-failed")
                self.assertTrue(output["visual_review"]["summary"].strip())
                self.assertEqual(
                    output["media"]["sha256"],
                    CASE14_ELIZA_SEGMIND_VIDEO_SHA256,
                )
                video_path = output["video_path"]
                self.assertTrue((ROOT / video_path).is_file(), video_path)
                self.assertEqual(
                    hashlib.sha256((ROOT / video_path).read_bytes()).hexdigest(),
                    CASE14_ELIZA_SEGMIND_VIDEO_SHA256,
                )
                external_paths.append(video_path)

        self.assertEqual(len(prompts), 60)
        self.assertEqual(len(video_paths), 60)
        self.assertEqual(len(set(video_paths)), 60)
        self.assertEqual(
            len(set(video_paths + comparison_paths + external_paths)),
            60 + len(comparison_paths) + len(external_paths),
        )
        self.assertEqual(len(source_paths), 20)
        if comparison_paths:
            self.assertEqual(manifest.get("comparison_output_count"), 2)
            self.assertEqual(len(comparison_paths), manifest["comparison_output_count"])
        elif "comparison_output_count" in manifest:
            self.assertEqual(manifest["comparison_output_count"], 0)
        self.assertEqual(manifest.get("external_output_count"), 1)
        self.assertEqual(len(external_paths), manifest["external_output_count"])

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
        selected_assets.update(
            output["video_path"]
            for article in self.manifest["articles"]
            for output in article.get("comparison_outputs", [])
        )
        selected_assets.update(
            output["video_path"]
            for article in self.manifest["articles"]
            for output in article.get("external_outputs", [])
        )

        comparison_count = sum(
            len(article.get("comparison_outputs", []))
            for article in self.manifest["articles"]
        )
        external_count = sum(
            len(article.get("external_outputs", []))
            for article in self.manifest["articles"]
        )
        self.assertEqual(len(selected_assets), 80 + comparison_count + external_count)
        self.assertFalse(selected_assets - tracked, selected_assets - tracked)

    def test_additional_manifest_contains_20_unique_images_by_three_models(self):
        if self.additional_manifest is None:
            self.skipTest("Final PROMOPAGES-9930 manifest has not been produced yet")

        manifest = self.additional_manifest
        self.assertEqual(manifest["ticket"], "PROMOPAGES-9930")
        self.assertEqual(manifest["article_count"], 20)
        self.assertEqual(manifest["image_count"], 20)
        self.assertEqual(manifest["expected_outputs"], 60)
        self.assertEqual(manifest["models"], MODEL_IDS)
        self.assertEqual(len(manifest["articles"]), 20)
        self.assertEqual(len(manifest["outputs"]), 60)

        base_digests = {
            article["selected_image"]["sha256"] for article in self.manifest["articles"]
        }
        source_digests = set()
        source_paths = set()
        video_paths = set()
        output_count = 0

        for article in manifest["articles"]:
            self.assertEqual(len(article["images"]), 1)
            for record in article["images"]:
                image = record["image"]
                self.assertNotIn(image["sha256"], base_digests)
                self.assertNotIn(image["sha256"], source_digests)
                self.assertNotIn(image["source_path"], source_paths)
                self.assertTrue((ROOT / image["source_path"]).is_file())
                source_digests.add(image["sha256"])
                source_paths.add(image["source_path"])

                outputs = record["outputs"]
                self.assertEqual([output["model_id"] for output in outputs], MODEL_IDS)
                for output in outputs:
                    self.assertIn(output["status"], {"succeeded", "verification-failed"})
                    self.assertTrue(output["positive_prompt"].strip())
                    self.assertNotIn(output["video_path"], video_paths)
                    self.assertTrue((ROOT / output["video_path"]).is_file())
                    self.assertGreater(output["media"]["bytes"], 0)
                    video_paths.add(output["video_path"])
                    output_count += 1

        self.assertEqual(len(source_digests), 20)
        self.assertEqual(len(source_paths), 20)
        self.assertEqual(len(video_paths), 60)
        self.assertEqual(output_count, 60)
        self.assertEqual(20 + len(source_digests), 40)
        self.assertEqual(len(self.manifest["outputs"]) + len(manifest["outputs"]), 120)
        self.assertEqual(
            sum(
                len(article.get("comparison_outputs", []))
                for article in self.manifest["articles"]
            ),
            2,
        )
        self.assertEqual(
            sum(
                len(article.get("external_outputs", []))
                for article in self.manifest["articles"]
            ),
            1,
        )

    def test_case_21_sidecar_adds_one_raw_image_by_three_models(self):
        if self.additional_manifest is None or self.case_21_manifest is None:
            self.skipTest("Final case 21 sidecar has not been produced yet")

        manifest = self.case_21_manifest
        self.assertEqual(manifest["manifest_role"], "case-21-extension")
        self.assertEqual(manifest["agent_id"], "clipmaker-lite")
        self.assertEqual(manifest["article_count"], 1)
        self.assertEqual(manifest["image_count"], 1)
        self.assertEqual(manifest["expected_outputs"], 3)
        self.assertEqual(manifest["canonical_output_count"], 3)
        self.assertEqual(manifest["research_output_count"], 4)
        self.assertEqual(manifest["display_output_count"], 7)
        self.assertEqual(manifest["attempt_count"], 11)
        self.assertEqual(manifest["attempts_without_video_count"], 4)
        self.assertEqual(manifest["available_output_count"], 7)
        self.assertEqual(manifest["accepted_output_count"], 0)
        self.assertEqual(manifest["visual_fidelity_failed_count"], 7)
        self.assertEqual(manifest["models"], MODEL_IDS)
        self.assertEqual(len(manifest["articles"]), 1)
        self.assertEqual(len(manifest["outputs"]), 3)
        self.assertEqual(len(manifest["research_outputs"]), 4)

        article = manifest["articles"][0]
        self.assertEqual(article["article_number"], "21")
        self.assertTrue(article["article_slug"])
        self.assertTrue(article["title"])
        self.assertTrue(article["context_path"])
        self.assertEqual(len(article["images"]), 1)

        record = article["images"][0]
        image = record["image"]
        self.assertEqual(image["delivery"], "repository-raw")
        self.assertEqual(len(image["sha256"]), 64)
        self.assertGreater(image["width"], 0)
        self.assertGreater(image["height"], 0)
        source_path = ROOT / image["source_path"]
        self.assertTrue(source_path.is_file(), image["source_path"])
        self.assertEqual(
            hashlib.sha256(source_path.read_bytes()).hexdigest(), image["sha256"]
        )

        previous_digests = {
            article["selected_image"]["sha256"]
            for article in self.manifest["articles"]
        }
        previous_digests.update(
            image_record["image"]["sha256"]
            for additional_article in self.additional_manifest["articles"]
            for image_record in additional_article["images"]
        )
        self.assertNotIn(image["sha256"], previous_digests)

        outputs = record["outputs"]
        self.assertEqual([output["model_id"] for output in outputs], MODEL_IDS)
        self.assertEqual(len({output["video_path"] for output in outputs}), 3)
        research_outputs = record["research_outputs"]
        self.assertEqual(research_outputs, manifest["research_outputs"])
        self.assertEqual(len(research_outputs), 4)
        display_outputs = outputs + research_outputs
        self.assertEqual(len({output["video_path"] for output in display_outputs}), 7)
        for output in display_outputs:
            self.assertEqual(output["delivery"], "repository-raw")
            self.assertTrue(output["positive_prompt"].strip())
            self.assertFalse(output["accepted"])
            self.assertEqual(output["visual_review"]["status"], "fidelity-failed")
            video_path = ROOT / output["video_path"]
            self.assertTrue(video_path.is_file(), output["video_path"])
            self.assertGreater(output["media"]["width"], 0)
            self.assertGreater(output["media"]["height"], 0)
            self.assertGreater(output["media"]["duration_seconds"], 0)
            self.assertEqual(output["media"]["bytes"], video_path.stat().st_size)

        flat_by_model = {
            output["model_id"]: output for output in manifest["outputs"]
        }
        self.assertEqual(
            flat_by_model,
            {output["model_id"]: output for output in outputs},
        )
        self.assertEqual(
            len(self.manifest["articles"]) + manifest["article_count"], 21
        )
        self.assertEqual(
            len(self.manifest["outputs"])
            + len(self.additional_manifest["outputs"])
            + len(manifest["outputs"]),
            123,
        )
        self.assertEqual(20 + self.additional_manifest["image_count"] + 1, 41)

    def test_all_demo_pages_keep_step_four_and_add_step_five(self):
        step_pattern = re.compile(r'<span class="viewSwitchStep" lang="en">Step №(\d+)</span>')

        for page in NAVIGATION_PAGES:
            with self.subTest(page=page.relative_to(ROOT)):
                html = page.read_text(encoding="utf-8")
                self.assertEqual(step_pattern.findall(html), ["1", "2", "3", "4", "5"])
                self.assertIn('<strong class="viewSwitchTitle">Разметка</strong>', html)
                self.assertIn('<strong class="viewSwitchTitle">Clipmaker Lite</strong>', html)
                self.assertIn("41 изображение · 3 модели", html)
                self.assertNotIn("40 изображений · 2–3 модели", html)
                self.assertEqual(html.count('aria-current="page"'), 1)
                self.assertEqual(
                    len(
                        re.findall(
                            r'href="(?:\./\?v=6|(?:\.\./)?clipmaker-lite/\?v=6)"',
                            html,
                        )
                    ),
                    1,
                )

    def test_showcase_uses_manifest_and_only_renders_active_videos(self):
        app = (ROOT / "clipmaker-lite" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "clipmaker-lite" / "index.html").read_text(encoding="utf-8")

        self.assertIn(
            'const BASE_MANIFEST_PATH = "../clipmaker-lite-test/manifest.json";',
            app,
        )
        self.assertIn("promopages-9930-manifest.json", app)
        self.assertIn("case-21-manifest.json", app)
        self.assertIn("EXPECTED_BASE_ARTICLE_COUNT = 20", app)
        self.assertIn("EXPECTED_BASE_OUTPUT_COUNT = 60", app)
        self.assertIn("EXPECTED_ADDITIONAL_ARTICLE_COUNT = 20", app)
        self.assertIn("EXPECTED_ADDITIONAL_IMAGE_COUNT = 20", app)
        self.assertIn("EXPECTED_ADDITIONAL_OUTPUT_COUNT = 60", app)
        self.assertIn("EXPECTED_CASE_21_ARTICLE_COUNT = 1", app)
        self.assertIn("EXPECTED_CASE_21_IMAGE_COUNT = 1", app)
        self.assertIn("EXPECTED_CASE_21_OUTPUT_COUNT = 3", app)
        self.assertIn("EXPECTED_CASE_21_RESEARCH_OUTPUT_COUNT = 4", app)
        self.assertIn("EXPECTED_CASE_21_DISPLAY_OUTPUT_COUNT = 7", app)
        self.assertIn("EXPECTED_CASE_21_ATTEMPT_COUNT = 11", app)
        self.assertIn("EXPECTED_TOTAL_ARTICLE_COUNT = 21", app)
        self.assertIn("EXPECTED_UNIQUE_IMAGE_COUNT = 41", app)
        self.assertIn("EXPECTED_CANONICAL_OUTPUT_COUNT = 123", app)
        self.assertIn("EXPECTED_EXPERIMENT_OUTPUT_COUNT = 2", app)
        self.assertIn("EXPECTED_EXTERNAL_OUTPUT_COUNT = 1", app)
        self.assertIn('const EXTERNAL_MODEL_ID = "segmind/wan-2.2-i2v-flash";', app)
        self.assertIn("const ADDITIONAL_MODEL_ORDER = MODEL_ORDER;", app)
        self.assertIn("repository-raw", app)
        self.assertIn("raw.githubusercontent.com", app)
        self.assertIn('preload="metadata"', app)
        self.assertIn('video.removeAttribute("src")', app)
        self.assertIn('elements.caseViewport.innerHTML = `', app)
        self.assertIn("Воспроизвести ${displayOutputs.length} основных", app)
        self.assertIn("data-play-loop", app)
        self.assertIn('data-video-group="loop"', app)
        self.assertIn("loop_experiment", app)
        self.assertIn("same-source-first-and-last-frame", app)
        self.assertIn("provider_native_loop_parameter", app)
        self.assertIn("API loop-closure", app)
        self.assertIn("seam review", app)
        self.assertIn("attempt_history", app)
        self.assertIn("Показать оригинал", app)
        self.assertIn("data-original-src", app)
        self.assertNotIn('poster="', app)
        self.assertNotIn("Prepared videos", app)
        self.assertNotIn("<video", html)
        self.assertNotIn("autoplay", app)
        self.assertNotIn("autoplay", html)
        self.assertIn('prefers-reduced-motion: reduce', app)
        self.assertIn(' loop"', app)
        self.assertIn("8–10 ₽", app)
        self.assertIn("$0.50", app)
        self.assertIn("$0.20", app)
        self.assertIn('const EXPERIMENT_ARTICLE_NUMBER = "14";', app)
        self.assertIn('showcaseLabel: "Референс · свой prompt"', app)
        self.assertIn('showcaseLabel: "Свой prompt"', app)
        self.assertIn('showcaseLabel: "Prompt Wan 2.2"', app)
        self.assertIn('showcaseLabel: "Eliza → Segmind"', app)
        self.assertIn("Visual review · fidelity failed.", app)
        self.assertIn('cost: "$0.18"', app)
        self.assertIn("const videoCount = videos.length;", app)
        self.assertNotIn("три видео", app)
        self.assertNotIn("из 3", app)
        self.assertNotIn("Остальные 57", app)
        self.assertIn("123 + 7", html)
        self.assertIn("все семь полученных MP4 из одиннадцати", html)
        self.assertIn("Историческая выборка из 20 статей и 40 изображений сохранена", html)
        self.assertRegex(
            html,
            r"Wan 2\.2 Flash\s+через Eliza → Segmind за \$0\.18",
        )
        self.assertIn('src="app.js?v=10"', html)
        self.assertIn('href="styles.css?v=7"', html)
        self.assertIn('id="videoCountSummary"', html)
        self.assertIn("endpoint-conditioning, а не native", html)
        self.assertIn('id="imageSelect"', html)
        self.assertIn('id="previousImage"', html)
        self.assertIn('id="nextImage"', html)

        styles = (ROOT / "clipmaker-lite" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", styles)
        self.assertIn("grid-template-columns: repeat(5, minmax(0, 1fr));", styles)
        self.assertIn(".modelGrid.hasExperiment", styles)
        self.assertIn(".modelGrid.hasExperiment.multiRow", styles)
        self.assertIn('.modelPanel[data-output-kind="research"]', styles)
        self.assertIn('.modelPanel[data-output-kind="loop"]', styles)
        self.assertIn(".researchSummary", styles)
        self.assertIn(".loopExperimentSection", styles)
        self.assertIn(".loopAttemptHistory", styles)
        self.assertIn(".loopGrid", styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)
        self.assertIn('.modelPanel[data-output-kind="external"]', styles)
        self.assertIn(".modelGrid.twoModels", styles)
        self.assertIn(".sourcePanel[hidden]", styles)


if __name__ == "__main__":
    unittest.main()
