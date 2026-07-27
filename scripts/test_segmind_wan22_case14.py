from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock

from scripts import segmind_wan22_case14 as case14


class FakeResponse:
    def __init__(self, payload: bytes, *, content_type: str, headers: dict[str, str] | None = None):
        self._stream = io.BytesIO(payload)
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        for name, value in (headers or {}).items():
            self.headers[name] = value

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


class Case14Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = self.root / case14.SOURCE_PATH
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source-image")
        self.source_patch = mock.patch.object(
            case14, "SOURCE_SHA256", hashlib.sha256(b"source-image").hexdigest()
        )
        self.source_patch.start()

    def tearDown(self):
        self.source_patch.stop()
        self.temp.cleanup()

    def source_response(self):
        return FakeResponse(b"source-image", content_type="image/jpeg")

    def valid_media(self, *, size_bytes: int = 8):
        return {
            "container": "mov,mp4",
            "duration_seconds": 5.0,
            "size_bytes": size_bytes,
            "bit_rate_bps": 100,
            "video": {
                "codec": "h264",
                "profile": "High",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30/1",
                "avg_fps": 30.0,
                "r_frame_rate": "30/1",
                "r_fps": 30.0,
                "nb_read_frames": 150,
                "bit_rate_bps": 90,
            },
            "has_audio": False,
            "audio": None,
        }

    def test_request_contract_is_fixed(self):
        payload = case14.request_parameters()
        self.assertEqual(payload["resolution"], "720p")
        self.assertIs(payload["prompt_extend"], False)
        self.assertIs(payload["watermark"], False)
        self.assertEqual(payload["seed"], 220214)
        self.assertIn("lower-center", payload["prompt"])
        self.assertIn("camera movement", payload["negative_prompt"])

    def test_prepare_writes_only_sanitized_metadata(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret"}, clear=False):
            run = case14.prepare(self.root)
        serialized = json.dumps(run)
        self.assertEqual(run["status"], "prepared")
        self.assertEqual(run["request"]["headers"]["Authorization"], "[REDACTED]")
        self.assertNotIn("top-secret", serialized)
        self.assertTrue((self.root / case14.PROMPT_PATH).is_file())
        self.assertTrue((self.root / case14.RUN_PATH).is_file())

    def test_success_writes_one_attempt_and_blocks_rerun(self):
        source = self.source_response()
        video = FakeResponse(
            b"fake-mp4",
            content_type="video/mp4",
            headers={
                "X-Segmind-Request-Id": "segmind-request-1",
                "X-Response-Cost": "0.18",
            },
        )
        client = FakeClient(video)
        media = self.valid_media()
        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret"}, clear=False):
            result = case14.generate(
                self.root,
                opener=client,
                source_opener=lambda request, timeout: source,
                probe=lambda path: media,
            )
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["response"]["x_response_cost"]["numeric"], 0.18)
        self.assertEqual(len(client.requests), 1)
        request_body = json.loads(client.requests[0][0].data)
        self.assertEqual(request_body, case14.request_parameters())
        self.assertEqual(
            client.requests[0][0].get_header("Authorization"), "OAuth top-secret"
        )
        serialized = (self.root / case14.RUN_PATH).read_text()
        self.assertNotIn("top-secret", serialized)
        with self.assertRaisesRegex(case14.Case14Error, "already has an attempt receipt"):
            case14.generate(
                self.root,
                opener=client,
                source_opener=lambda request, timeout: self.source_response(),
                probe=lambda path: media,
            )
        self.assertEqual(len(client.requests), 1)

    def test_prepare_never_rewrites_a_changed_prompt(self):
        case14.prepare(self.root)
        prompt_path = self.root / case14.PROMPT_PATH
        prompt_path.write_text("{}\n", encoding="utf-8")

        with self.assertRaisesRegex(case14.Case14Error, "immutable"):
            case14.prepare(self.root)

        self.assertEqual(prompt_path.read_text(encoding="utf-8"), "{}\n")

    def test_media_contract_failure_is_persisted_and_raised(self):
        video = FakeResponse(
            b"fake-mp4",
            content_type="video/mp4",
            headers={
                "X-Segmind-Request-Id": "segmind-request-contract-fail",
                "X-Response-Cost": "0.18",
            },
        )
        client = FakeClient(video)
        media = self.valid_media()
        media["video"]["width"] = 640

        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret"}, clear=False):
            with self.assertRaisesRegex(case14.Case14Error, "failed verification"):
                case14.generate(
                    self.root,
                    opener=client,
                    source_opener=lambda request, timeout: self.source_response(),
                    probe=lambda path: media,
                )

        run = case14.read_json(self.root / case14.RUN_PATH)
        self.assertEqual(run["status"], "verification_failed")
        self.assertEqual(run["error"]["stage"], "ffprobe")
        self.assertEqual(len(client.requests), 1)

    def test_octet_stream_response_is_consistently_accepted(self):
        video = FakeResponse(
            b"fake-mp4",
            content_type="application/octet-stream",
            headers={
                "X-Segmind-Request-Id": "segmind-request-octet-stream",
                "X-Response-Cost": "0.18",
            },
        )
        client = FakeClient(video)
        media = self.valid_media()

        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret"}, clear=False):
            result = case14.generate(
                self.root,
                opener=client,
                source_opener=lambda request, timeout: self.source_response(),
                probe=lambda path: media,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["response"]["content_type"], "application/octet-stream")
        with mock.patch.object(case14, "ffprobe_media", return_value=media):
            self.assertEqual(case14.verify(self.root)["status"], "succeeded")

    def test_pool_change_after_prepare_is_rejected_before_post(self):
        with mock.patch.dict(os.environ, {"ELIZA_POOL": "pool-a"}, clear=False):
            prepared = case14.prepare(self.root)
        self.assertEqual(prepared["request"]["headers"]["Ya-Pool"], "pool-a")

        client = FakeClient(
            FakeResponse(
                b"fake-mp4",
                content_type="video/mp4",
                headers={
                    "X-Segmind-Request-Id": "must-not-be-used",
                    "X-Response-Cost": "0.18",
                },
            )
        )
        with mock.patch.dict(
            os.environ,
            {"ANTHROPIC_AUTH_TOKEN": "top-secret", "ELIZA_POOL": "pool-b"},
            clear=False,
        ):
            with self.assertRaisesRegex(case14.Case14Error, "Ya-Pool changed"):
                case14.generate(
                    self.root,
                    opener=client,
                    source_opener=lambda request, timeout: self.source_response(),
                    probe=lambda path: self.valid_media(),
                )

        self.assertEqual(len(client.requests), 0)
        self.assertEqual(case14.read_json(self.root / case14.RUN_PATH)["status"], "prepared")

    def test_concurrent_generation_claim_allows_only_one_paid_post(self):
        video = FakeResponse(
            b"fake-mp4",
            content_type="video/mp4",
            headers={
                "X-Segmind-Request-Id": "segmind-request-concurrent",
                "X-Response-Cost": "0.18",
            },
        )
        client = FakeClient(video)
        source_barrier = threading.Barrier(2)

        def source_opener(request, timeout):
            source_barrier.wait(timeout=5)
            return self.source_response()

        def worker():
            try:
                case14.generate(
                    self.root,
                    opener=client,
                    source_opener=source_opener,
                    probe=lambda path: self.valid_media(),
                )
                return "succeeded"
            except case14.Case14Error:
                return "blocked"

        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret"}, clear=False):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: worker(), range(2)))

        self.assertEqual(sorted(results), ["blocked", "succeeded"])
        self.assertEqual(len(client.requests), 1)

    def test_failed_transport_still_blocks_rerun(self):
        class FailingClient:
            calls = 0

            def open(self, request, timeout):
                self.calls += 1
                raise case14.URLError("offline")

        client = FailingClient()
        with mock.patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": "top-secret"}, clear=False):
            with self.assertRaisesRegex(case14.Case14Error, "transport failed"):
                case14.generate(
                    self.root,
                    opener=client,
                    source_opener=lambda request, timeout: self.source_response(),
                )
        run = case14.read_json(self.root / case14.RUN_PATH)
        self.assertEqual(run["status"], "failed")
        self.assertTrue(run["attempt"]["request_dispatched"])
        self.assertEqual(client.calls, 1)
        with self.assertRaisesRegex(case14.Case14Error, "already has an attempt receipt"):
            case14.generate(
                self.root,
                opener=client,
                source_opener=lambda request, timeout: self.source_response(),
            )
        self.assertEqual(client.calls, 1)


if __name__ == "__main__":
    unittest.main()
