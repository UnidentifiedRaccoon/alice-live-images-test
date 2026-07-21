from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("video_generation_pipeline.py")
SPEC = importlib.util.spec_from_file_location("video_generation_pipeline", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pipeline)


class VideoGenerationPipelineTest(unittest.TestCase):
    def make_catalogs(self, root: Path) -> tuple[Path, Path]:
        samples = []
        prompts = []
        classes = ["portrait_closeup", "product_still_life", "animal", "interior", "text_interface_collage"]
        dataset = root / "PROMOPAGES-9857"
        for index, primary_class in enumerate(classes, start=1):
            slug = f"{index:02d}-article"
            source = dataset / "articles" / slug / f"{index:02d}.jpeg"
            source.parent.mkdir(parents=True, exist_ok=True)
            content = f"image-{index}".encode()
            source.write_bytes(content)
            sample_id = f"{index:02d}-sample"
            sample = {
                "sample_id": sample_id,
                "article_slug": slug,
                "image_number": f"{index:02d}",
                "image_id": f"image-{index}",
                "source_path": source.relative_to(root).as_posix(),
                "source_url": f"https://example.invalid/{index}.jpeg",
                "sha256": hashlib.sha256(content).hexdigest(),
                "width": 1600 if index != 1 else 800,
                "height": 900 if index != 1 else 1200,
                "primary_class": primary_class,
                "graphic_kind": "ui_screenshot" if primary_class == "text_interface_collage" else None,
                "graphic_kinds": ["ui_screenshot", "chart"] if primary_class == "text_interface_collage" else [],
            }
            samples.append(sample)
            for model_id, config in pipeline.MODEL_CONFIGS.items():
                prompts.append(
                    {
                        "sample_id": sample_id,
                        "model_id": model_id,
                        "target_duration_seconds": config["duration"],
                        "primary_class": primary_class,
                        "graphic_kind": "ui_screenshot" if primary_class == "text_interface_collage" else None,
                        "graphic_kinds": ["ui_screenshot", "chart"] if primary_class == "text_interface_collage" else [],
                        "camera_state": "A",
                        "positive_prompt": f"Positive prompt {sample_id} {model_id}",
                        "negative_prompt": "flicker, morphing, camera shake",
                    }
                )
        samples_path = dataset / "video-samples.json"
        prompts_path = dataset / "video-prompts.json"
        samples_path.write_text(json.dumps({"samples": samples}), encoding="utf-8")
        prompts_path.write_text(json.dumps({"prompts": prompts}), encoding="utf-8")
        return samples_path, prompts_path

    def test_aspect_ratio_chooses_nearest_supported_value(self) -> None:
        self.assertEqual(
            pipeline.choose_aspect_ratio(1600, 900, pipeline.MODEL_CONFIGS["alibaba/wan-2.7"]["aspect_ratios"]),
            "16:9",
        )
        self.assertEqual(
            pipeline.choose_aspect_ratio(800, 1200, pipeline.MODEL_CONFIGS["alibaba/wan-2.7"]["aspect_ratios"]),
            "3:4",
        )
        self.assertEqual(
            pipeline.choose_aspect_ratio(800, 1200, pipeline.MODEL_CONFIGS["google/veo-3.1-lite"]["aspect_ratios"]),
            "9:16",
        )

    def test_provider_payloads_keep_model_specific_negative_prompt_shape(self) -> None:
        sample = {"source_url": "https://example.invalid/image.png", "width": 1600, "height": 900}
        base = {"positive_prompt": "move once", "negative_prompt": "flicker"}
        wan = pipeline.build_request_preview(sample, {**base, "model_id": "alibaba/wan-2.7"})
        veo = pipeline.build_request_preview(sample, {**base, "model_id": "google/veo-3.1-lite"})
        self.assertEqual(wan["provider"]["options"]["atlas-cloud"]["parameters"]["negative_prompt"], "flicker")
        self.assertEqual(veo["provider"]["options"]["google-vertex"]["parameters"]["negativePrompt"], "flicker")
        self.assertFalse(wan["generate_audio"])
        self.assertEqual(wan["frame_images"][0]["frame_type"], "first_frame")

    def test_wan_demo_preview_preserves_97_frame_contract(self) -> None:
        sample = {"source_path": "image.jpeg", "width": 1000, "height": 450}
        prompt = {"model_id": "alibaba/wan-2.2", "positive_prompt": "one step", "negative_prompt": "flicker"}
        preview = pipeline.build_request_preview(sample, prompt)
        self.assertEqual(preview["runtime"]["frames"], 97)
        self.assertEqual(preview["runtime"]["fps"], 30)
        self.assertIn("Avoid: flicker", preview["input"]["prompt"])

    def test_contract_check_records_provider_audio_nonconformance(self) -> None:
        media = {"duration_seconds": 5.0, "has_audio": True, "frames": 150, "fps": 30.0}
        check = pipeline.assess_contract("alibaba/wan-2.7", media)
        self.assertFalse(check["conforms"])
        self.assertTrue(check["checks"]["duration"])
        self.assertFalse(check["checks"]["audio"])
        self.assertIn("generate_audio=False", check["warnings"][0])

    def test_paths_are_article_local_and_model_specific(self) -> None:
        root = Path("/tmp/example-root")
        sample = {"article_slug": "04-product", "image_number": "05"}
        paths = pipeline.artifact_paths(root, sample, "google/veo-3.1-lite")
        self.assertEqual(
            paths["video"],
            root / "PROMOPAGES-9857/articles/04-product/video/veo-3.1-lite/05.mp4",
        )
        with self.assertRaises(pipeline.PipelineError):
            pipeline.artifact_paths(root, sample, "unknown/model")

    def test_safe_error_redacts_credentials_and_signed_query_values(self) -> None:
        message = pipeline.safe_error(
            "Authorization: OAuth secret-value token=second https://x.invalid/a?signature=third&ok=1"
        )
        self.assertNotIn("secret-value", message)
        self.assertNotIn("second", message)
        self.assertNotIn("third", message)
        self.assertIn("[REDACTED]", message)

    def test_result_helpers_accept_nested_openrouter_shapes(self) -> None:
        response = {
            "data": {
                "job": {"id": "job-123", "status": "completed"},
                "outputs": [{"video_url": "https://cdn.invalid/output.mp4?sig=secret"}],
            }
        }
        self.assertEqual(pipeline.find_job_id(response), "job-123")
        self.assertEqual(pipeline.find_status(response), "completed")
        self.assertTrue(pipeline.find_video_url(response).startswith("https://cdn.invalid/"))
        self.assertEqual(
            pipeline.find_video_url({"unsigned_urls": {"video": "https://cdn.invalid/unsigned.mp4"}}),
            "https://cdn.invalid/unsigned.mp4",
        )

    def test_materialize_is_complete_and_preserves_existing_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            rows = pipeline.materialize_plan(samples_path, prompts_path, root)
            self.assertEqual(len(rows), 15)
            run_path = rows[0]["paths"]["run"]
            run = pipeline.read_json(run_path)
            run["status"] = "succeeded"
            run["provider_job_id"] = "job-keep"
            pipeline.atomic_write_json(run_path, run)
            pipeline.materialize_plan(samples_path, prompts_path, root)
            preserved = pipeline.read_json(run_path)
            self.assertEqual(preserved["status"], "succeeded")
            self.assertEqual(preserved["provider_job_id"], "job-keep")

    def test_dry_run_writes_sanitized_requests_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            rows = pipeline.materialize_plan(samples_path, prompts_path, root)
            selected = pipeline.select_rows(rows, ["01-sample"], ["alibaba/wan-2.7"])
            args = argparse.Namespace(
                force=False,
                dry_run=True,
                fail_fast=False,
                timeout=1,
                poll_interval=0,
                wan_base_url="https://wan.invalid",
                wan_stream_base_url="http://wan.invalid",
                eliza_base_url="https://eliza.invalid/v1",
            )
            failures = pipeline.run_rows(selected, args, root)
            self.assertEqual(failures, 0)
            run = pipeline.read_json(selected[0]["paths"]["run"])
            self.assertEqual(run["status"], "dry-run")
            serialized = json.dumps(run)
            self.assertNotIn("Authorization", serialized)
            self.assertNotIn("token", serialized.lower())

    def test_validation_rejects_wan_27_negative_prompt_over_500_chars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            document = json.loads(prompts_path.read_text(encoding="utf-8"))
            record = next(item for item in document["prompts"] if item["model_id"] == "alibaba/wan-2.7")
            record["negative_prompt"] = "x" * 501
            prompts_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.validate_catalogs(samples_path, prompts_path, root)


if __name__ == "__main__":
    unittest.main()
