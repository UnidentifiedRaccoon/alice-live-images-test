from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
                "motion_plan_id": f"motion-{index}",
                "action_complete_by_seconds": 0 if primary_class == "text_interface_collage" else 2,
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
                        "motion_plan_id": f"motion-{index}",
                        "action_complete_by_seconds": 0 if primary_class == "text_interface_collage" else 2,
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
        wan = pipeline.build_request_preview(
            sample,
            {**base, "model_id": "alibaba/wan-2.7", "target_duration_seconds": 5},
        )
        veo = pipeline.build_request_preview(
            sample,
            {**base, "model_id": "google/veo-3.1-lite", "target_duration_seconds": 4},
        )
        self.assertEqual(wan["provider"]["options"]["atlas-cloud"]["parameters"]["negative_prompt"], "flicker")
        self.assertEqual(veo["provider"]["options"]["google-vertex"]["parameters"]["negativePrompt"], "flicker")
        self.assertFalse(wan["provider"]["options"]["atlas-cloud"]["parameters"]["prompt_extend"])
        self.assertTrue(veo["provider"]["options"]["google-vertex"]["parameters"]["enhancePrompt"])
        self.assertEqual(wan["duration"], 5)
        self.assertEqual(veo["duration"], 4)
        self.assertFalse(wan["generate_audio"])
        self.assertEqual(wan["frame_images"][0]["frame_type"], "first_frame")
        held_veo = pipeline.build_request_preview(
            sample,
            {
                **base,
                "model_id": "google/veo-3.1-lite",
                "target_duration_seconds": 4,
                "last_frame_is_source": True,
            },
        )
        self.assertEqual(
            [frame["frame_type"] for frame in held_veo["frame_images"]],
            ["first_frame", "last_frame"],
        )
        self.assertEqual(
            held_veo["frame_images"][0]["image_url"],
            held_veo["frame_images"][1]["image_url"],
        )
        extended_wan = pipeline.build_request_preview(
            sample,
            {
                **base,
                "model_id": "alibaba/wan-2.7",
                "target_duration_seconds": 3,
                "prompt_extend": True,
            },
        )
        self.assertTrue(extended_wan["provider"]["options"]["atlas-cloud"]["parameters"]["prompt_extend"])
        for payload in (wan, veo):
            self.assertNotIn("speed", payload)
            self.assertNotIn("fps", payload)
            self.assertNotIn("motion_strength", payload)

    def test_inline_negative_uses_exact_wan_demo_transport_without_last_frame(self) -> None:
        sample = {"source_url": "https://example.invalid/image.png", "width": 1600, "height": 900}
        base = {
            "positive_prompt": "same positive",
            "negative_prompt": "same negative",
            "embed_negative_in_positive": True,
        }
        wan = pipeline.build_request_preview(
            sample,
            {**base, "model_id": "alibaba/wan-2.7", "target_duration_seconds": 5},
        )
        veo = pipeline.build_request_preview(
            sample,
            {**base, "model_id": "google/veo-3.1-lite", "target_duration_seconds": 4},
        )
        for payload in (wan, veo):
            self.assertEqual(payload["prompt"], "same positive\n\nAvoid: same negative")
            self.assertEqual(
                [frame["frame_type"] for frame in payload["frame_images"]],
                ["first_frame"],
            )
        self.assertNotIn("negative_prompt", wan["provider"]["options"]["atlas-cloud"]["parameters"])
        self.assertNotIn("negativePrompt", veo["provider"]["options"]["google-vertex"]["parameters"])

    def test_eliza_headers_disable_paid_request_retries(self) -> None:
        self.assertEqual(
            pipeline.DEFAULT_ELIZA_BASE_URL,
            "https://api.eliza.yandex.net/openrouter/v1",
        )
        headers = pipeline.eliza_headers("test-token")
        self.assertEqual(headers["Authorization"], "OAuth test-token")
        self.assertEqual(headers["X-Retries"], "1")

    def test_eliza_download_stays_on_authenticated_content_endpoint(self) -> None:
        headers = {"Authorization": "OAuth test-token", "X-Retries": "1"}
        with patch.object(pipeline, "eliza_headers", return_value=headers), patch.object(
            pipeline,
            "eliza_poll",
            return_value={"response": {"status": "completed", "video_url": "https://outside.invalid/video.mp4"}},
        ), patch.object(pipeline, "http_download") as download:
            pipeline.eliza_generate(
                {},
                {},
                Path("result.mp4"),
                "https://eliza.invalid/openrouter/v1",
                30,
                0,
                {"provider_job_id": "job-123"},
                lambda _job_id, _session_hash: None,
            )
        download.assert_called_once_with(
            "https://eliza.invalid/openrouter/v1/videos/job-123/content?index=0",
            Path("result.mp4"),
            headers=headers,
            timeout=600,
        )

    def test_wan_demo_preview_preserves_97_frame_contract(self) -> None:
        sample = {"source_path": "image.jpeg", "width": 1000, "height": 450}
        prompt = {"model_id": "alibaba/wan-2.2", "positive_prompt": "one step", "negative_prompt": "flicker"}
        preview = pipeline.build_request_preview(sample, prompt)
        self.assertEqual(preview["runtime"]["frames"], 97)
        self.assertEqual(preview["runtime"]["fps"], 30)
        self.assertIn("Avoid: flicker", preview["input"]["prompt"])

    def test_contract_check_records_provider_audio_nonconformance(self) -> None:
        media = {"duration_seconds": 3.0, "has_audio": True, "frames": 90, "fps": 30.0}
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
        experiment_paths = pipeline.artifact_paths(
            root,
            sample,
            "google/veo-3.1-lite",
            "portrait-permissive-v1",
        )
        self.assertEqual(
            experiment_paths["video"],
            root
            / "PROMOPAGES-9857/articles/04-product/video/experiments"
            / "portrait-permissive-v1/veo-3.1-lite/05.mp4",
        )
        with self.assertRaises(pipeline.PipelineError):
            pipeline.artifact_paths(root, sample, "unknown/model")
        with self.assertRaises(pipeline.PipelineError):
            pipeline.artifact_paths(root, sample, "google/veo-3.1-lite", "../escape")

    def test_prompt_artifact_records_experiment_provenance(self) -> None:
        sample = {
            "sample_id": "01-sample",
            "image_id": "image-1",
            "source_path": "PROMOPAGES-9857/articles/01/01.jpeg",
            "source_url": "https://example.invalid/01.jpeg",
            "sha256": "abc",
            "width": 1600,
            "height": 900,
        }
        prompt = {
            "model_id": "alibaba/wan-2.7",
            "primary_class": "portrait_closeup",
            "graphic_kind": None,
            "graphic_kinds": [],
            "camera_state": "A",
            "motion_plan_id": "open-improvisation",
            "action_complete_by_seconds": None,
            "positive_prompt": "move freely",
            "negative_prompt": "identity drift",
            "target_duration_seconds": 5,
            "prompt_extend": True,
        }
        artifact = pipeline.prompt_artifact(
            sample,
            prompt,
            Path("/tmp/example-root"),
            source_catalog="path/to/experiment.json",
            experiment_id="portrait-permissive-v1",
        )
        self.assertEqual(artifact["source_catalog"], "path/to/experiment.json")
        self.assertEqual(artifact["experiment_id"], "portrait-permissive-v1")
        self.assertTrue(artifact["target"]["prompt_extend"])

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
        wrapper = {
            "response": {
                "id": "job-wrapper",
                "status": "completed",
                "unsigned_urls": ["https://cdn.invalid/wrapper.mp4"],
            }
        }
        self.assertEqual(pipeline.find_job_id(wrapper), "job-wrapper")
        self.assertEqual(pipeline.find_status(wrapper), "completed")
        self.assertEqual(pipeline.find_video_url(wrapper), "https://cdn.invalid/wrapper.mp4")
        self.assertEqual(
            pipeline.find_error_detail(
                {"response": {"status": "failed", "error": "content may have been filtered"}}
            ),
            "content may have been filtered",
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
            expected_request = pipeline.build_request_preview(rows[0]["sample"], rows[0]["prompt"])
            run["request"] = expected_request
            run["request_sha256"] = pipeline.request_fingerprint(expected_request, rows[0]["sample"])
            pipeline.atomic_write_json(run_path, run)
            pipeline.materialize_plan(samples_path, prompts_path, root)
            preserved = pipeline.read_json(run_path)
            self.assertEqual(preserved["status"], "succeeded")
            self.assertEqual(preserved["provider_job_id"], "job-keep")

            prompt_document = json.loads(prompts_path.read_text(encoding="utf-8"))
            changed = next(
                item
                for item in prompt_document["prompts"]
                if item["sample_id"] == rows[0]["sample"]["sample_id"]
                and item["model_id"] == rows[0]["prompt"]["model_id"]
            )
            changed["positive_prompt"] += " changed"
            prompts_path.write_text(json.dumps(prompt_document), encoding="utf-8")
            pipeline.materialize_plan(samples_path, prompts_path, root)
            stale = pipeline.read_json(run_path)
            self.assertEqual(stale["status"], "stale")
            self.assertIn("--force", stale["error"])

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
            self.assertEqual(
                run["request_sha256"],
                pipeline.request_fingerprint(run["request"], selected[0]["sample"]),
            )
            serialized = json.dumps(run)
            self.assertNotIn("Authorization", serialized)
            self.assertNotIn("token", serialized.lower())

    def test_materialize_fails_closed_for_legacy_active_job_with_changed_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            rows = pipeline.materialize_plan(samples_path, prompts_path, root)
            run_path = rows[0]["paths"]["run"]
            run = pipeline.read_json(run_path)
            run.update(
                {
                    "status": "submitted",
                    "provider_job_id": "legacy-job",
                    "request": {"prompt": "old request"},
                    "request_sha256": None,
                }
            )
            pipeline.atomic_write_json(run_path, run)
            pipeline.materialize_plan(samples_path, prompts_path, root)
            stale = pipeline.read_json(run_path)
            self.assertEqual(stale["status"], "stale")
            self.assertEqual(stale["provider_job_id"], "legacy-job")
            self.assertIn("active", stale["error"])

    def test_materialize_fails_closed_for_active_job_without_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            rows = pipeline.materialize_plan(samples_path, prompts_path, root)
            row = rows[0]
            run_path = row["paths"]["run"]
            run = pipeline.read_json(run_path)
            run.update(
                {
                    "status": "running",
                    "provider_job_id": "legacy-job",
                    "request": pipeline.build_request_preview(row["sample"], row["prompt"]),
                    "request_sha256": None,
                    "request_fingerprint_version": None,
                }
            )
            pipeline.atomic_write_json(run_path, run)
            pipeline.materialize_plan(samples_path, prompts_path, root)
            stale = pipeline.read_json(run_path)
            self.assertEqual(stale["status"], "stale")
            self.assertIn("active", stale["error"])

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

    def test_validation_rejects_last_frame_for_wan_demo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            document = json.loads(prompts_path.read_text(encoding="utf-8"))
            record = next(item for item in document["prompts"] if item["model_id"] == "alibaba/wan-2.2")
            record["last_frame_is_source"] = True
            prompts_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.validate_catalogs(samples_path, prompts_path, root)

    def test_validation_rejects_incomplete_or_self_referencing_prompt_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            document = json.loads(prompts_path.read_text(encoding="utf-8"))
            source = next(
                item
                for item in document["prompts"]
                if item["sample_id"] == "01-sample" and item["model_id"] == "alibaba/wan-2.2"
            )
            target = next(
                item
                for item in document["prompts"]
                if item["sample_id"] == "01-sample" and item["model_id"] == "alibaba/wan-2.7"
            )
            target["positive_prompt"] = source["positive_prompt"]
            target["negative_prompt"] = source["negative_prompt"]
            target["prompt_source_model_id"] = source["model_id"]
            prompts_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.validate_catalogs(samples_path, prompts_path, root)

            target["embed_negative_in_positive"] = True
            target["prompt_source_model_id"] = target["model_id"]
            prompts_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(pipeline.PipelineError):
                pipeline.validate_catalogs(samples_path, prompts_path, root)

    def test_source_digest_change_marks_succeeded_output_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_path, prompts_path = self.make_catalogs(root)
            rows = pipeline.materialize_plan(samples_path, prompts_path, root)
            row = rows[0]
            run_path = row["paths"]["run"]
            request = pipeline.build_request_preview(row["sample"], row["prompt"])
            run = pipeline.read_json(run_path)
            run.update(
                {
                    "status": "succeeded",
                    "request": request,
                    "request_sha256": pipeline.request_fingerprint(request, row["sample"]),
                    "request_fingerprint_version": pipeline.REQUEST_FINGERPRINT_VERSION,
                }
            )
            pipeline.atomic_write_json(run_path, run)

            source = root / row["sample"]["source_path"]
            content = b"changed-image"
            source.write_bytes(content)
            samples_document = json.loads(samples_path.read_text(encoding="utf-8"))
            sample_record = next(
                item for item in samples_document["samples"] if item["sample_id"] == row["sample"]["sample_id"]
            )
            sample_record["sha256"] = hashlib.sha256(content).hexdigest()
            samples_path.write_text(json.dumps(samples_document), encoding="utf-8")

            pipeline.materialize_plan(samples_path, prompts_path, root)
            stale = pipeline.read_json(run_path)
            self.assertEqual(stale["status"], "stale")
            self.assertIn("--force", stale["error"])

    def test_wan_resume_can_disable_submit_after_missing_session(self) -> None:
        sample = {
            "source_path": "PROMOPAGES-9857/articles/fake/01.png",
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "exact prompt",
            "negative_prompt": None,
        }
        resume = {
            "provider_job_id": "existing-event",
            "provider_session_hash": "existing-session",
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.mp4"
            with (
                patch.object(
                    pipeline,
                    "wan_wait_for_result",
                    side_effect=pipeline.PipelineError("session_not_found"),
                ),
                patch.object(pipeline, "upload_wan_image") as upload,
                patch.object(pipeline, "http_json") as submit,
            ):
                with self.assertRaisesRegex(pipeline.PipelineError, "session_not_found"):
                    pipeline.wan_generate(
                        sample,
                        prompt,
                        destination,
                        "https://wan.invalid",
                        "https://wan-stream.invalid",
                        10,
                        resume,
                        lambda *_args: self.fail("resume must not submit"),
                        allow_resubmit_after_missing_session=False,
                    )
            upload.assert_not_called()
            submit.assert_not_called()

    def test_wan_marks_submitting_after_upload_and_before_queue_join(self) -> None:
        sample = {
            "source_path": "PROMOPAGES-9857/articles/fake/01.png",
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "exact prompt",
            "negative_prompt": None,
        }
        events: list[str] = []

        def upload(*_args: object, **_kwargs: object) -> str:
            events.append("upload")
            return "/provider/upload/01.png"

        def submit(*_args: object, **_kwargs: object) -> dict[str, str]:
            self.assertEqual(events, ["upload", "submitting"])
            events.append("queue-join")
            return {"event_id": "event-1"}

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.mp4"
            with (
                patch.object(pipeline, "upload_wan_image", side_effect=upload),
                patch.object(pipeline, "http_json", side_effect=submit),
                patch.object(
                    pipeline,
                    "wan_wait_for_result",
                    return_value="https://wan.invalid/result.mp4",
                ),
                patch.object(pipeline, "http_download"),
            ):
                pipeline.wan_generate(
                    sample,
                    prompt,
                    destination,
                    "https://wan.invalid",
                    "https://wan-stream.invalid",
                    10,
                    None,
                    lambda *_args: events.append("submitted"),
                    allow_resubmit_after_missing_session=False,
                    on_submitting=lambda: events.append("submitting"),
                )

        self.assertEqual(events[:4], ["upload", "submitting", "queue-join", "submitted"])

    def test_wan_upload_validates_the_exact_bytes_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "source.png"
            image_path.write_bytes(b"exact source bytes")
            with patch.object(pipeline, "urlopen") as urlopen:
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "upload source digest changed",
                ):
                    pipeline.upload_wan_image(
                        "https://wan.invalid",
                        image_path,
                        expected_sha256="0" * 64,
                    )
            urlopen.assert_not_called()

    def test_tracked_openrouter_prompts_keep_shared_real_time_motion_plan(self) -> None:
        samples, prompts = pipeline.validate_catalogs(
            pipeline.DEFAULT_SAMPLES,
            pipeline.DEFAULT_PROMPTS,
            pipeline.ROOT,
        )
        samples_by_id = {sample["sample_id"]: sample for sample in samples}
        prompts_by_key = {
            (prompt["sample_id"], prompt["model_id"]): prompt
            for prompt in prompts
        }
        for prompt in prompts:
            sample = samples_by_id[prompt["sample_id"]]
            self.assertEqual(prompt["motion_plan_id"], sample["motion_plan_id"])
            self.assertEqual(
                prompt["action_complete_by_seconds"],
                sample["action_complete_by_seconds"],
            )
            source_model_id = prompt.get("prompt_source_model_id")
            if source_model_id:
                source = prompts_by_key[(prompt["sample_id"], source_model_id)]
                self.assertEqual(prompt["positive_prompt"], source["positive_prompt"])
                self.assertEqual(prompt["negative_prompt"], source["negative_prompt"])
                self.assertTrue(prompt["embed_negative_in_positive"])
                preview = pipeline.build_request_preview(sample, prompt)
                self.assertEqual(
                    preview["prompt"],
                    f"{source['positive_prompt']}\n\nAvoid: {source['negative_prompt']}",
                )
                self.assertEqual(
                    [frame["frame_type"] for frame in preview["frame_images"]],
                    ["first_frame"],
                )
                continue
            if prompt["model_id"] == "alibaba/wan-2.2" or prompt["primary_class"] == "text_interface_collage":
                continue
            positive = prompt["positive_prompt"].lower()
            negative = prompt["negative_prompt"].lower()
            self.assertIn("normal real-time", positive)
            self.assertNotIn("slowly", positive)
            self.assertLessEqual(float(prompt["action_complete_by_seconds"]), 2.0)
            self.assertTrue("slow motion" in negative or "slow-motion" in negative)


if __name__ == "__main__":
    unittest.main()
