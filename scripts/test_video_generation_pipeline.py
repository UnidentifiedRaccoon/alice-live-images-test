from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler


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

    def test_http_json_preserves_dns_resolution_as_pre_submit_failure(self) -> None:
        reason = socket.gaierror(
            8, "nodename nor servname provided, or not known"
        )
        with patch.object(pipeline, "urlopen", side_effect=URLError(reason)):
            with self.assertRaises(pipeline.PreSubmitNetworkError) as raised:
                pipeline.http_json(
                    "POST",
                    "https://api.eliza.yandex.net/openrouter/v1/videos",
                    {"model": "test"},
                )

        self.assertEqual(
            str(raised.exception),
            "POST https://api.eliza.yandex.net/openrouter/v1/videos failed: "
            "[Errno 8] nodename nor servname provided, or not known",
        )

    def test_http_json_does_not_reclassify_other_url_errors(self) -> None:
        with patch.object(
            pipeline,
            "urlopen",
            side_effect=URLError(TimeoutError("connection timed out")),
        ):
            with self.assertRaises(pipeline.PipelineError) as raised:
                pipeline.http_json(
                    "POST",
                    "https://api.eliza.yandex.net/openrouter/v1/videos",
                    {"model": "test"},
                )

        self.assertNotIsInstance(raised.exception, pipeline.PreSubmitNetworkError)

    def test_http_json_post_429_is_a_definitive_pre_submit_rejection(self) -> None:
        url = "https://api.eliza.yandex.net/openrouter/v1/videos"
        rejection = HTTPError(
            url,
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":"Quota exceeded"}'),
        )
        with patch.object(pipeline, "urlopen", side_effect=rejection):
            with self.assertRaises(pipeline.PreSubmitRejectedError) as raised:
                pipeline.http_json("POST", url, {"model": "test"})
        rejection.close()

        self.assertEqual(raised.exception.http_status, 429)
        self.assertIn('HTTP 429: {"error":"Quota exceeded"}', str(raised.exception))

    def test_http_json_get_429_is_not_a_pre_submit_rejection(self) -> None:
        url = "https://api.eliza.yandex.net/openrouter/v1/videos/existing-job"
        rejection = HTTPError(
            url,
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":"Quota exceeded"}'),
        )
        with patch.object(pipeline, "urlopen", side_effect=rejection):
            with self.assertRaises(pipeline.PipelineError) as raised:
                pipeline.http_json("GET", url)
        rejection.close()

        self.assertNotIsInstance(raised.exception, pipeline.PreSubmitRejectedError)

    def test_generation_route_registry_is_exact_and_discovery_free(self) -> None:
        policy = pipeline.GENERATION_ROUTE_DOCUMENT["policy"]
        self.assertEqual(policy["resolution"], "exact-model-id")
        self.assertFalse(policy["automatic_fallback"])
        self.assertFalse(policy["normal_run_discovery"])
        self.assertEqual(
            set(policy["forbidden_discovery_paths"]),
            {"/videos/models", "/gradio_api/info", "/config"},
        )
        self.assertEqual(set(pipeline.GENERATION_ROUTES), set(pipeline.MODEL_CONFIGS))
        wan = pipeline.route_for_model("alibaba/wan-2.2")
        self.assertEqual(wan["adapter"], "eliza-segmind")
        self.assertEqual(wan["transport"], "eliza-synchronous-binary")
        self.assertEqual(wan["gateway"], "eliza")
        self.assertEqual(wan["provider_key"], "segmind")
        self.assertEqual(wan["provider_model_id"], "segmind/wan-2.2-i2v-flash")
        self.assertEqual(wan["paths"]["submit"], "/wan-2.2-i2v-flash")
        self.assertEqual(wan["capacity"], 1)
        self.assertTrue(wan["synchronous"])
        self.assertFalse(wan["automatic_retry"])
        self.assertEqual(
            wan["submit_payload"]["fields"],
            [
                "image",
                "prompt",
                "negative_prompt",
                "resolution",
                "prompt_extend",
                "watermark",
                "seed",
            ],
        )
        self.assertEqual(
            pipeline.route_for_model("alibaba/wan-2.7")["provider_key"],
            "atlas-cloud",
        )
        self.assertEqual(
            pipeline.route_for_model("google/veo-3.1-lite")["provider_key"],
            "google-vertex",
        )
        with self.assertRaisesRegex(pipeline.PipelineError, "No exact generation route"):
            pipeline.route_for_model("alibaba/wan-latest")

    def test_eliza_models_use_exact_fixed_routes_without_discovery(self) -> None:
        sample = {
            "source_url": "https://example.invalid/image.png",
            "width": 1600,
            "height": 900,
        }
        cases = (
            ("alibaba/wan-2.7", 3, "atlas-cloud"),
            ("google/veo-3.1-lite", 4, "google-vertex"),
        )
        for model_id, duration, provider_key in cases:
            with self.subTest(model_id=model_id):
                prompt = {
                    "model_id": model_id,
                    "positive_prompt": "move once",
                    "negative_prompt": "flicker",
                    "target_duration_seconds": duration,
                }
                requests: list[tuple[str, str, object | None]] = []

                def request(
                    method: str,
                    url: str,
                    payload: object | None = None,
                    **_kwargs: object,
                ) -> object:
                    requests.append((method, url, payload))
                    if method == "POST":
                        return {"id": "job-123"}
                    return {"status": "completed"}

                with tempfile.TemporaryDirectory() as directory:
                    destination = Path(directory) / "result.mp4"
                    with patch.dict(
                        pipeline.os.environ,
                        {"ELIZA_OAUTH_TOKEN": "test-token"},
                        clear=True,
                    ):
                        with (
                            patch.object(pipeline, "http_json", side_effect=request),
                            patch.object(pipeline, "http_download") as download,
                        ):
                            pipeline.eliza_generate(
                                sample,
                                prompt,
                                destination,
                                "https://eliza.invalid/openrouter/v1",
                                30,
                                0,
                                None,
                                lambda *_args: None,
                            )
                self.assertEqual(
                    [(method, url) for method, url, _payload in requests],
                    [
                        ("POST", "https://eliza.invalid/openrouter/v1/videos"),
                        (
                            "GET",
                            "https://eliza.invalid/openrouter/v1/videos/job-123",
                        ),
                    ],
                )
                payload = requests[0][2]
                self.assertIsInstance(payload, dict)
                assert isinstance(payload, dict)
                self.assertEqual(payload["model"], model_id)
                self.assertEqual(
                    set(payload["provider"]["options"]),
                    {provider_key},
                )
                download.assert_called_once_with(
                    "https://eliza.invalid/openrouter/v1/videos/job-123/content?index=0",
                    destination,
                    headers={"Authorization": "OAuth test-token", "X-Retries": "1"},
                    timeout=600,
                )
                forbidden = pipeline.GENERATION_ROUTE_DOCUMENT["policy"][
                    "forbidden_discovery_paths"
                ]
                self.assertFalse(
                    any(path in url for _method, url, _payload in requests for path in forbidden)
                )

    def test_wan_named_headers_prefer_dod_token_and_fall_back_to_ya_token(self) -> None:
        base_url = "https://wan-streamlit.dod.yandex.net"
        with patch.dict(
            pipeline.os.environ,
            {"DOD_TOKEN": "dod-test-token", "YA_TOKEN": "ya-test-token"},
            clear=True,
        ):
            headers = pipeline.wan_named_headers(base_url)
        self.assertEqual(headers["Authorization"], "OAuth dod-test-token")
        self.assertEqual(headers["X-Dod-Autostart"], "true")
        self.assertEqual(headers["X-Requested-With"], "bot")

        with patch.dict(
            pipeline.os.environ,
            {"YA_TOKEN": "ya-test-token"},
            clear=True,
        ):
            fallback = pipeline.wan_named_headers(base_url)
        self.assertEqual(fallback["Authorization"], "OAuth ya-test-token")

    def test_wan_named_headers_fail_closed_without_token_or_trusted_https_host(self) -> None:
        with patch.dict(pipeline.os.environ, {}, clear=True):
            with self.assertRaisesRegex(pipeline.PipelineError, "DOD_TOKEN or YA_TOKEN"):
                pipeline.wan_named_headers(
                    "https://wan-streamlit.dod.yandex.net"
                )
        with patch.dict(
            pipeline.os.environ,
            {"DOD_TOKEN": "must-not-leak"},
            clear=True,
        ):
            for base_url in (
                "http://wan-streamlit.dod.yandex.net",
                "https://wan-streamlit.dod.yandex.net.evil.invalid",
                "https://outside.invalid",
            ):
                with self.subTest(base_url=base_url):
                    with self.assertRaisesRegex(
                        pipeline.PipelineError,
                        r"HTTPS \*\.dod\.yandex\.net",
                    ):
                        pipeline.wan_named_headers(base_url)

    def test_scoped_wan_headers_are_not_forwarded_by_redirects(self) -> None:
        headers = {
            "Authorization": "OAuth redirect-test-token",
            "X-Dod-Autostart": "true",
            "X-Requested-With": "bot",
        }
        request = pipeline._request_with_scoped_headers(
            "https://wan-streamlit.dod.yandex.net/gradio_api/file=result.mp4",
            method="GET",
            headers=headers,
        )
        redirected = HTTPRedirectHandler().redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://cdn.invalid/result.mp4",
        )
        self.assertIsNotNone(redirected)
        for name in headers:
            self.assertIsNone(redirected.get_header(name))

    def test_eliza_download_stays_on_authenticated_content_endpoint(self) -> None:
        headers = {"Authorization": "OAuth test-token", "X-Retries": "1"}
        with patch.object(pipeline, "eliza_headers", return_value=headers), patch.object(
            pipeline,
            "eliza_poll",
            return_value={"response": {"status": "completed", "video_url": "https://outside.invalid/video.mp4"}},
        ), patch.object(pipeline, "http_download") as download:
            pipeline.eliza_generate(
                {},
                {"model_id": "alibaba/wan-2.7"},
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

    def test_segmind_preview_uses_exact_payload_and_serializes_null_negative(self) -> None:
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": "a" * 64,
            "width": 1000,
            "height": 450,
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": None,
        }
        preview = pipeline.build_request_preview(sample, prompt)
        self.assertEqual(preview["endpoint"], "/wan-2.2-i2v-flash")
        self.assertEqual(preview["model"], "alibaba/wan-2.2")
        self.assertEqual(preview["provider"], "segmind")
        self.assertEqual(preview["provider_model_id"], "segmind/wan-2.2-i2v-flash")
        self.assertEqual(
            preview["input"],
            {
                "image": "https://cdn.invalid/image.jpeg",
                "prompt": "one step",
                "negative_prompt": "",
                "resolution": "720p",
                "prompt_extend": False,
                "watermark": False,
                "seed": 220214,
            },
        )

    def test_segmind_generate_preflights_and_posts_once_after_guard(self) -> None:
        source_bytes = b"frozen source"
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": None,
        }
        events: list[str] = []

        class Response(io.BytesIO):
            def __init__(self, value: bytes, headers: dict[str, str] | None = None):
                super().__init__(value)
                self.status = 200
                self.headers = headers or {}

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

        def source_open(request, **_kwargs: object):
            events.append("preflight")
            self.assertEqual(request.full_url, sample["source_url"])
            return Response(source_bytes)

        class PostOpener:
            calls = 0
            request = None

            def open(self, request, **_kwargs: object):
                self.calls += 1
                self.request = request
                events.append("post")
                return Response(
                    b"binary mp4",
                    {
                        "Content-Type": "video/mp4",
                        "X-Segmind-Request-Id": "request-123",
                        "X-Response-Cost": "0.18",
                    },
                )

        post = PostOpener()

        def guarded(preflight: dict[str, object]) -> None:
            events.append("guard")
            self.assertEqual(preflight["sha256"], sample["sha256"])

        with tempfile.TemporaryDirectory() as directory, patch.object(
            pipeline,
            "segmind_headers",
            return_value={
                "Authorization": "OAuth test",
                "X-Retries": "1",
                "X-Include-Cost": "true",
                "Accept": "video/mp4, application/octet-stream",
            },
        ):
            destination = Path(directory) / "result.mp4"
            response = pipeline.segmind_generate(
                sample,
                prompt,
                destination,
                "https://api.eliza.invalid/segmind/v1",
                30,
                guarded,
                source_opener=source_open,
                post_opener=post,
            )

            self.assertEqual(destination.read_bytes(), b"binary mp4")

        self.assertEqual(events, ["preflight", "guard", "post"])
        self.assertEqual(post.calls, 1)
        self.assertEqual(
            post.request.full_url,
            "https://api.eliza.invalid/segmind/v1/wan-2.2-i2v-flash",
        )
        self.assertEqual(
            json.loads(post.request.data.decode("utf-8")),
            pipeline.segmind_request_payload(sample, prompt),
        )
        request_headers = {
            name.lower(): value for name, value in post.request.header_items()
        }
        self.assertEqual(request_headers["authorization"], "OAuth test")
        self.assertEqual(request_headers["x-retries"], "1")
        self.assertEqual(request_headers["x-include-cost"], "true")
        self.assertEqual(request_headers["content-type"], "application/json")
        self.assertEqual(response["request_id"], "request-123")
        self.assertFalse(response["automatic_retry"])

    def test_segmind_digest_mismatch_never_reaches_guard_or_post(self) -> None:
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": hashlib.sha256(b"expected").hexdigest(),
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": None,
        }

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

        post = unittest.mock.Mock()
        guard = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            pipeline, "segmind_headers", return_value={"Authorization": "OAuth test"}
        ):
            with self.assertRaisesRegex(pipeline.PipelineError, "digest changed"):
                pipeline.segmind_generate(
                    sample,
                    prompt,
                    Path(directory) / "result.mp4",
                    "https://api.eliza.invalid/segmind/v1",
                    30,
                    guard,
                    source_opener=lambda *_args, **_kwargs: Response(b"changed"),
                    post_opener=post,
                )

        guard.assert_not_called()
        post.open.assert_not_called()

    def test_segmind_post_transport_failure_is_not_retried(self) -> None:
        source_bytes = b"source"
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": "",
        }

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

        class FailingPost:
            calls = 0

            def open(self, *_args: object, **_kwargs: object):
                self.calls += 1
                raise URLError("closed")

        post = FailingPost()
        guard = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            pipeline, "segmind_headers", return_value={"Authorization": "OAuth test"}
        ):
            with self.assertRaisesRegex(pipeline.PipelineError, "POST failed"):
                pipeline.segmind_generate(
                    sample,
                    prompt,
                    Path(directory) / "result.mp4",
                    "https://api.eliza.invalid/segmind/v1",
                    30,
                    guard,
                    source_opener=lambda *_args, **_kwargs: Response(source_bytes),
                    post_opener=post,
                )

        guard.assert_called_once()
        self.assertEqual(post.calls, 1)

    def test_segmind_http_429_is_a_definitive_pre_submit_rejection(self) -> None:
        source_bytes = b"source"
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": "",
        }

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

        class RejectingPost:
            calls = 0

            def open(self, request, **_kwargs: object):
                self.calls += 1
                raise HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    {},
                    io.BytesIO(b'{"error":"Quota exceeded"}'),
                )

        post = RejectingPost()
        guard = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            pipeline, "segmind_headers", return_value={"Authorization": "OAuth test"}
        ):
            with self.assertRaises(pipeline.PreSubmitRejectedError) as raised:
                pipeline.segmind_generate(
                    sample,
                    prompt,
                    Path(directory) / "result.mp4",
                    "https://api.eliza.invalid/segmind/v1",
                    30,
                    guard,
                    source_opener=lambda *_args, **_kwargs: Response(source_bytes),
                    post_opener=post,
                )

        self.assertEqual(raised.exception.http_status, 429)
        self.assertIn("Quota exceeded", str(raised.exception))
        guard.assert_called_once()
        self.assertEqual(post.calls, 1)

    def test_segmind_oversize_task_failure_parser_is_exact_and_structural(self) -> None:
        provider_failure = {
            "task_id": "task-123",
            "task_status": "FAILED",
            "video_url": "",
            "submit_time": "2026-08-05 16:16:38.596",
            "scheduled_time": "2026-08-05 16:16:38.614",
            "end_time": "2026-08-05 16:16:42.626",
            "code": "InvalidParameter",
            "message": pipeline.SEGMIND_OVERSIZE_ERROR_MESSAGE,
        }

        def body(
            nested: dict[str, object],
            **outer_extra: object,
        ) -> str:
            return json.dumps(
                {
                    "error": pipeline.SEGMIND_PROVIDER_FAILURE_PREFIX
                    + json.dumps(nested),
                    **outer_extra,
                }
            )

        detail = body(provider_failure)
        self.assertEqual(
            pipeline.parse_segmind_oversize_task_failure(400, detail),
            {
                "http_status": 400,
                "provider_task_id": "task-123",
                "provider_task_status": "FAILED",
                "provider_error_code": "InvalidParameter",
                "provider_error_message": pipeline.SEGMIND_OVERSIZE_ERROR_MESSAGE,
                "submit_time": "2026-08-05 16:16:38.596",
                "scheduled_time": "2026-08-05 16:16:38.614",
                "end_time": "2026-08-05 16:16:42.626",
            },
        )

        without_times = {
            key: value
            for key, value in provider_failure.items()
            if key not in {"submit_time", "scheduled_time", "end_time"}
        }
        minimal = pipeline.parse_segmind_oversize_task_failure(
            400, body(without_times)
        )
        self.assertIsNotNone(minimal)
        self.assertNotIn("submit_time", minimal)

        variants = (
            (409, detail),
            (400, body(provider_failure, request_id="gateway-only")),
            (400, body({**provider_failure, "task_id": ""})),
            (400, body({**provider_failure, "task_status": "RUNNING"})),
            (400, body({**provider_failure, "video_url": "https://cdn.invalid/video.mp4"})),
            (400, body({**provider_failure, "code": "BadRequest"})),
            (
                400,
                body(
                    {
                        **provider_failure,
                        "message": "Image size is too large than 20 mb",
                    }
                ),
            ),
            (400, body({**provider_failure, "unexpected": True})),
            (400, body({**provider_failure, "end_time": None})),
            (400, '{"error":"the provider task failed: not-json"}'),
        )
        for status, near_match in variants:
            with self.subTest(status=status, detail=near_match):
                self.assertIsNone(
                    pipeline.parse_segmind_oversize_task_failure(
                        status, near_match
                    )
                )

    def test_segmind_exact_http_400_task_failure_is_typed_terminal(self) -> None:
        source_bytes = b"source"
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": "",
        }
        provider_failure = {
            "task_id": "task-400",
            "task_status": "FAILED",
            "video_url": "",
            "submit_time": "2026-08-05 16:16:38.596",
            "scheduled_time": "2026-08-05 16:16:38.614",
            "end_time": "2026-08-05 16:16:42.626",
            "code": "InvalidParameter",
            "message": pipeline.SEGMIND_OVERSIZE_ERROR_MESSAGE,
        }
        detail = json.dumps(
            {
                "error": pipeline.SEGMIND_PROVIDER_FAILURE_PREFIX
                + json.dumps(provider_failure)
            }
        ).encode("utf-8")

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

        class RejectingPost:
            calls = 0

            def open(self, request, **_kwargs: object):
                self.calls += 1
                raise HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    {},
                    io.BytesIO(detail),
                )

        post = RejectingPost()
        guard = unittest.mock.Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            pipeline, "segmind_headers", return_value={"Authorization": "OAuth test"}
        ):
            with self.assertRaises(
                pipeline.SegmindProviderTaskFailedError
            ) as raised:
                pipeline.segmind_generate(
                    sample,
                    prompt,
                    Path(directory) / "result.mp4",
                    "https://api.eliza.invalid/segmind/v1",
                    30,
                    guard,
                    source_opener=lambda *_args, **_kwargs: Response(source_bytes),
                    post_opener=post,
                )

        self.assertIsInstance(raised.exception, pipeline.ProviderTerminalError)
        self.assertEqual(raised.exception.http_status, 400)
        self.assertEqual(raised.exception.provider_task_id, "task-400")
        self.assertEqual(
            raised.exception.evidence["provider_error_message"],
            pipeline.SEGMIND_OVERSIZE_ERROR_MESSAGE,
        )
        guard.assert_called_once()
        self.assertEqual(post.calls, 1)

    def test_segmind_generic_http_400_remains_untyped(self) -> None:
        source_bytes = b"source"
        sample = {
            "source_url": "https://cdn.invalid/image.jpeg",
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "one step",
            "negative_prompt": "",
        }

        class Response(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args: object) -> None:
                self.close()

        class RejectingPost:
            def open(self, request, **_kwargs: object):
                raise HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    {},
                    io.BytesIO(b'{"error":"Bad request"}'),
                )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            pipeline, "segmind_headers", return_value={"Authorization": "OAuth test"}
        ):
            with self.assertRaises(pipeline.PipelineError) as raised:
                pipeline.segmind_generate(
                    sample,
                    prompt,
                    Path(directory) / "result.mp4",
                    "https://api.eliza.invalid/segmind/v1",
                    30,
                    lambda _preflight: None,
                    source_opener=lambda *_args, **_kwargs: Response(source_bytes),
                    post_opener=RejectingPost(),
                )

        self.assertNotIsInstance(
            raised.exception, pipeline.SegmindProviderTaskFailedError
        )
        self.assertIn("HTTP 400", str(raised.exception))

    def test_wan_named_sse_returns_documented_file_url(self) -> None:
        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def __iter__(self):
                return iter(
                    [
                        b"event: complete\n",
                        b'data: [{"url":"/gradio_api/file=result.mp4"}]\n',
                        b"\n",
                    ]
                )

        headers = {
            "Authorization": "OAuth sse-test-token",
            "X-Dod-Autostart": "true",
            "X-Requested-With": "bot",
        }

        def open_sse(request, **_kwargs: object) -> Response:
            request_headers = {
                name.lower(): value for name, value in request.header_items()
            }
            for name, value in headers.items():
                self.assertEqual(request_headers[name.lower()], value)
            return Response()

        with patch.object(pipeline, "urlopen", side_effect=open_sse):
            result = pipeline.wan_wait_for_named_result(
                "https://wan-streamlit.dod.yandex.net",
                "event-1",
                10,
                headers=headers,
            )
        self.assertEqual(
            result,
            "https://wan-streamlit.dod.yandex.net/gradio_api/file=result.mp4",
        )

    def test_wan_named_sse_treats_null_completion_as_terminal_failure(self) -> None:
        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def __iter__(self):
                return iter(
                    [
                        b"event: complete\n",
                        b"data: null\n",
                        b"\n",
                    ]
                )

        with patch.object(pipeline, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(
                pipeline.ProviderTerminalError,
                "completed without a video result",
            ):
                pipeline.wan_wait_for_named_result(
                    "https://wan-streamlit.dod.yandex.net",
                    "event-1",
                    10,
                    headers={"Authorization": "OAuth terminal-test-token"},
                )

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
        with patch.dict(
            pipeline.os.environ,
            {"DOD_TOKEN": "raw-dod-secret"},
            clear=True,
        ):
            message = pipeline.safe_error(
                'Authorization: OAuth secret-value token=second '
                'https://x.invalid/a?signature=third&ok=1 '
                '{"Authorization":"OAuth raw-dod-secret",'
                '"detail":"raw-dod-secret"}'
            )
        self.assertNotIn("secret-value", message)
        self.assertNotIn("second", message)
        self.assertNotIn("third", message)
        self.assertNotIn("raw-dod-secret", message)
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

    def test_wan_normal_run_uses_only_exact_legacy_route_and_payload(self) -> None:
        sample = {"source_path": "PROMOPAGES-9857/articles/fake/01.png"}
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "exact prompt",
            "negative_prompt": "flicker",
        }
        submitted: dict[str, str] = {}

        def submit(
            method: str,
            url: str,
            payload: dict[str, object],
            **kwargs: object,
        ) -> dict[str, str]:
            self.assertEqual(method, "POST")
            self.assertEqual(
                url,
                "https://wan.invalid/gradio_api/queue/join",
            )
            self.assertIsNone(kwargs["headers"])
            self.assertEqual(payload["event_data"], None)
            self.assertEqual(payload["fn_index"], 0)
            self.assertEqual(payload["trigger_id"], 19)
            self.assertIsInstance(payload["session_hash"], str)
            self.assertEqual(
                payload["data"],
                [
                    "exact prompt\n\nAvoid: flicker",
                    {
                        "path": "/provider/upload/01.png",
                        "orig_name": "01.png",
                        "mime_type": "image/png",
                        "is_stream": False,
                        "meta": {"_type": "gradio.FileData"},
                    },
                    "720p",
                    1,
                    False,
                    None,
                    97,
                    30,
                ],
            )
            self.assertIsInstance(payload["data"][3], int)
            self.assertIsInstance(payload["data"][4], bool)
            self.assertIsNone(payload["data"][5])
            self.assertIsInstance(payload["data"][6], int)
            self.assertIsInstance(payload["data"][7], int)
            return {"event_id": "event-1"}

        def on_submitted(job_id: str, session_hash: str) -> None:
            submitted.update(job_id=job_id, session_hash=session_hash)

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.mp4"
            with (
                patch.object(
                    pipeline,
                    "upload_wan_image",
                    return_value="/provider/upload/01.png",
                ) as upload,
                patch.object(pipeline, "http_json", side_effect=submit) as http_json,
                patch.object(
                    pipeline,
                    "wan_wait_for_result",
                    return_value="https://wan-stream.invalid/result.mp4",
                ) as wait_legacy,
                patch.object(pipeline, "wan_wait_for_named_result") as wait_named,
                patch.object(pipeline, "http_download") as download,
            ):
                pipeline.wan_generate(
                    sample,
                    prompt,
                    destination,
                    "https://wan.invalid",
                    "https://wan-stream.invalid",
                    10,
                    None,
                    on_submitted,
                    allow_resubmit_after_missing_session=False,
                )

        upload.assert_called_once()
        self.assertIsNone(upload.call_args.kwargs["headers"])
        http_json.assert_called_once()
        wait_named.assert_not_called()
        wait_legacy.assert_called_once_with(
            "https://wan-stream.invalid",
            submitted["session_hash"],
            "event-1",
            10,
        )
        download.assert_called_once_with(
            "https://wan-stream.invalid/result.mp4",
            destination,
            headers=None,
            timeout=600,
        )

    def test_wan_normal_route_failure_never_falls_back_to_named_endpoint(self) -> None:
        sample = {"source_path": "PROMOPAGES-9857/articles/fake/01.png"}
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "exact prompt",
            "negative_prompt": None,
        }
        requested_urls: list[str] = []

        def fail_submit(
            _method: str,
            url: str,
            _payload: object,
            **_kwargs: object,
        ) -> object:
            requested_urls.append(url)
            raise pipeline.PipelineError("legacy route rejected request")

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    pipeline,
                    "upload_wan_image",
                    return_value="/provider/upload/01.png",
                ),
                patch.object(pipeline, "http_json", side_effect=fail_submit),
                patch.object(pipeline, "wan_wait_for_named_result") as wait_named,
            ):
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "legacy route rejected request",
                ):
                    pipeline.wan_generate(
                        sample,
                        prompt,
                        Path(directory) / "result.mp4",
                        "https://wan.invalid",
                        "https://wan-stream.invalid",
                        10,
                        None,
                        lambda *_args: None,
                        allow_resubmit_after_missing_session=False,
                    )
        self.assertEqual(
            requested_urls,
            ["https://wan.invalid/gradio_api/queue/join"],
        )
        wait_named.assert_not_called()

    def test_wan_marks_submitting_after_upload_and_before_named_submit(self) -> None:
        sample = {
            "source_path": "PROMOPAGES-9857/articles/fake/01.png",
        }
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "exact prompt",
            "negative_prompt": None,
        }
        events: list[str] = []
        receipt: dict[str, str] = {}
        expected_headers = {
            "Authorization": "OAuth named-test-token",
            "X-Dod-Autostart": "true",
            "X-Requested-With": "bot",
        }

        def upload(*_args: object, **kwargs: object) -> str:
            self.assertEqual(kwargs["headers"], expected_headers)
            events.append("upload")
            return "/provider/upload/01.png"

        def submit(*args: object, **kwargs: object) -> dict[str, str]:
            self.assertEqual(events, ["upload", "submitting"])
            self.assertEqual(kwargs["headers"], expected_headers)
            payload = args[2]
            self.assertEqual(
                payload["data"],
                [
                    "exact prompt",
                    {
                        "path": "/provider/upload/01.png",
                        "orig_name": "01.png",
                        "mime_type": "image/png",
                        "is_stream": False,
                        "meta": {"_type": "gradio.FileData"},
                    },
                    "720p",
                    1,
                    False,
                    None,
                    97,
                    30,
                ],
            )
            self.assertIsInstance(payload["data"][6], int)
            self.assertIsInstance(payload["data"][7], int)
            events.append("named-submit")
            return {"event_id": "event-1"}

        def on_submitted(job_id: str, session_hash: str) -> None:
            events.append("submitted")
            receipt.update(
                {
                    "provider_job_id": job_id,
                    "provider_session_hash": session_hash,
                }
            )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.mp4"
            with patch.dict(
                pipeline.os.environ,
                {"DOD_TOKEN": "named-test-token"},
                clear=True,
            ):
                with (
                    patch.object(pipeline, "upload_wan_image", side_effect=upload),
                    patch.object(pipeline, "http_json", side_effect=submit),
                    patch.object(
                        pipeline,
                        "wan_wait_for_named_result",
                        return_value=(
                            "https://wan-streamlit.dod.yandex.net/result.mp4"
                        ),
                    ) as wait_named,
                    patch.object(pipeline, "http_download") as download,
                ):
                    pipeline.wan_generate(
                        sample,
                        prompt,
                        destination,
                        "https://wan-streamlit.dod.yandex.net",
                        "https://wan-stream.invalid",
                        10,
                        None,
                        on_submitted,
                        allow_resubmit_after_missing_session=False,
                        on_submitting=lambda: events.append("submitting"),
                        submit_mode="named",
                    )

        self.assertEqual(events[:4], ["upload", "submitting", "named-submit", "submitted"])
        wait_named.assert_called_once_with(
            "https://wan-streamlit.dod.yandex.net",
            "event-1",
            10,
            headers=expected_headers,
        )
        download.assert_called_once_with(
            "https://wan-streamlit.dod.yandex.net/result.mp4",
            destination,
            headers=expected_headers,
            timeout=600,
        )
        serialized_receipt = json.dumps(receipt)
        self.assertNotIn("named-test-token", serialized_receipt)
        self.assertNotIn("Authorization", serialized_receipt)

    def test_wan_named_download_does_not_send_oauth_to_cross_host_result(self) -> None:
        sample = {"source_path": "PROMOPAGES-9857/articles/fake/01.png"}
        prompt = {
            "model_id": "alibaba/wan-2.2",
            "positive_prompt": "exact prompt",
            "negative_prompt": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "result.mp4"
            with patch.dict(
                pipeline.os.environ,
                {"DOD_TOKEN": "cross-host-test-token"},
                clear=True,
            ):
                with (
                    patch.object(
                        pipeline,
                        "upload_wan_image",
                        return_value="/provider/upload/01.png",
                    ),
                    patch.object(
                        pipeline,
                        "http_json",
                        return_value={"event_id": "event-1"},
                    ),
                    patch.object(
                        pipeline,
                        "wan_wait_for_named_result",
                        return_value="https://cdn.invalid/result.mp4",
                    ),
                    patch.object(pipeline, "http_download") as download,
                ):
                    pipeline.wan_generate(
                        sample,
                        prompt,
                        destination,
                        "https://wan-streamlit.dod.yandex.net",
                        "https://wan-stream.invalid",
                        10,
                        None,
                        lambda *_args: None,
                        allow_resubmit_after_missing_session=False,
                        submit_mode="named",
                    )
        download.assert_called_once_with(
            "https://cdn.invalid/result.mp4",
            destination,
            headers=None,
            timeout=600,
        )

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

    def test_wan_legacy_upload_uses_exact_registry_path(self) -> None:
        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'["/provider/upload/source.png"]'

        def open_upload(request, **_kwargs: object) -> Response:
            self.assertEqual(
                request.full_url,
                "https://wan.invalid/gradio_api/upload",
            )
            self.assertEqual(request.get_method(), "POST")
            self.assertIsNone(request.get_header("Authorization"))
            return Response()

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "source.png"
            image_path.write_bytes(b"source bytes")
            with patch.object(pipeline, "urlopen", side_effect=open_upload):
                result = pipeline.upload_wan_image(
                    "https://wan.invalid",
                    image_path,
                )
        self.assertEqual(result, "/provider/upload/source.png")

    def test_wan_legacy_sse_uses_exact_registry_paths(self) -> None:
        event = {
            "msg": "process_completed",
            "event_id": "event-1",
            "success": True,
            "output": {"data": [{"path": "tmp/result.mp4"}]},
        }

        class Response:
            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def __iter__(self):
                return iter([f"data: {json.dumps(event)}\n".encode(), b"\n"])

        def open_stream(request, **_kwargs: object) -> Response:
            self.assertEqual(
                request.full_url,
                "http://wan-stream.invalid/gradio_api/queue/data?session_hash=session-1",
            )
            return Response()

        with patch.object(pipeline, "urlopen", side_effect=open_stream):
            result = pipeline.wan_wait_for_result(
                "http://wan-stream.invalid",
                "session-1",
                "event-1",
                10,
            )
        self.assertEqual(
            result,
            "http://wan-stream.invalid/gradio_api/file=tmp/result.mp4",
        )

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
