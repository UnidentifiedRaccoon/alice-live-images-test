#!/usr/bin/env python3
"""Focused, network-free tests for the Wan 2.2 Lite control wrapper."""

from __future__ import annotations

import fcntl
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from scripts import clipmaker_lite_wan22_pipeline as pipeline


class Wan22ControlPipelineTest(unittest.TestCase):
    def make_workspace(
        self, directory: str
    ) -> tuple[Path, list[Path], Path]:
        root = Path(directory).resolve()
        result_paths: list[Path] = []
        for index, source_relative in enumerate(pipeline.EXPECTED_SOURCE_PATHS, start=1):
            source = root / source_relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source_bytes = (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR"
                + (1500).to_bytes(4, "big")
                + (1000).to_bytes(4, "big")
                + f"source-image-{index}".encode()
            )
            source.write_bytes(source_bytes)
            run_id = f"promopages-9891-schemafix-{index:02d}-test-wan-2-7"
            result_path = (
                root
                / "artifacts/clipmaker-lite/v1"
                / run_id
                / "result.json"
            )
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "job_id": run_id,
                        "inputs": {
                            "source_image": {
                                "path": source_relative,
                                "sha256": hashlib.sha256(source_bytes).hexdigest(),
                            }
                        },
                        "models": [
                            {
                                "model_id": pipeline.PROMPT_SOURCE_MODEL_ID,
                                "scene_plan": f"Scene plan {index}",
                                "positive_prompt": f"Exact Lite prompt {index}",
                                "negative_prompt": None,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result_paths.append(result_path)
        manifest = root / "control.json"
        return root, result_paths, manifest

    def verifier(self, root: Path, result_paths: list[Path]):
        by_id = {path.parent.name: path for path in result_paths}

        def verify(_root: Path, run_id: str) -> dict:
            self.assertEqual(_root, root)
            result_path = by_id[run_id]
            result = json.loads(result_path.read_text(encoding="utf-8"))
            return {
                "verified": True,
                "verification_scope": "trusted-workspace-route",
                "cryptographically_signed": False,
                "result_path": result_path.relative_to(root).as_posix(),
                "agent_id": "clipmaker-lite",
                "contract_version": "test",
                "contract_fingerprint": "sha256:test",
                "models": [pipeline.PROMPT_SOURCE_MODEL_ID],
                "source_image_sha256": result["inputs"]["source_image"]["sha256"],
            }

        return verify

    def build_plan(
        self, root: Path, result_paths: list[Path], manifest: Path
    ) -> dict:
        return pipeline.build_control_plan(
            root,
            result_paths,
            manifest,
            provenance_verifier=self.verifier(root, result_paths),
        )

    @staticmethod
    def successful_transport(submissions: list[dict], waits: list[tuple[str, str]]):
        def submit(image_path, prompt, runtime, timeout):
            index = len(submissions) + 1
            submissions.append(
                {
                    "image_path": image_path,
                    "prompt": prompt,
                    "runtime": runtime,
                    "timeout": timeout,
                }
            )
            return f"event-{index}", f"session-{index}"

        def wait(session_hash, event_id, _timeout, on_started):
            waits.append((session_hash, event_id))
            on_started()
            return f"https://provider.invalid/{event_id}.mp4?signature=secret"

        def download(_url, destination, _timeout):
            destination.write_bytes(b"fake-mp4")

        return submit, wait, download

    def test_plan_locks_five_article_local_jobs_and_exact_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            plan = self.build_plan(root, results, manifest)

            self.assertEqual(plan["job_count"], 5)
            self.assertEqual(plan["target_model_id"], "alibaba/wan-2.2")
            self.assertEqual(plan["prompt_source_model_id"], "alibaba/wan-2.7")
            self.assertEqual(plan["provider_route"], "wan-streamlit")
            self.assertFalse(plan["attested_lite_model"])
            self.assertEqual(
                plan["runtime"],
                {
                    "resolution": "720p",
                    "frames": 97,
                    "fps": 30,
                    "seed": 1,
                    "loop": False,
                    "last_frame": None,
                },
            )
            for job in plan["jobs"]:
                source = Path(job["source_image"]["path"])
                expected_directory = (
                    source.parent / "clipmaker-lite/wan-streamlit-wan-2.2"
                )
                self.assertEqual(
                    job["artifacts"]["video"],
                    (expected_directory / f"{source.stem}.mp4").as_posix(),
                )
                self.assertEqual(
                    job["prompt"]["positive_prompt"],
                    f"Exact Lite prompt {pipeline.EXPECTED_SOURCE_PATHS.index(source.as_posix()) + 1}",
                )
                prompt_path = root / job["artifacts"]["prompt"]
                run_path = root / job["artifacts"]["run"]
                prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
                run = json.loads(run_path.read_text(encoding="utf-8"))
                self.assertFalse(prompt["attested_lite_model"])
                self.assertEqual(run["status"], "pending")
                self.assertEqual(run["attempts"], 0)

            serialized = manifest.read_text(encoding="utf-8").lower()
            self.assertNotIn("http://", serialized)
            self.assertNotIn("https://", serialized)
            self.assertNotIn("authorization", serialized)

    def test_plan_rejects_unverified_prompt_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)

            def unverified(_root: Path, _run_id: str) -> dict:
                return {"verified": False}

            with self.assertRaisesRegex(pipeline.Wan22ControlError, "not verified"):
                pipeline.build_control_plan(
                    root,
                    results,
                    manifest,
                    provenance_verifier=unverified,
                )
            self.assertFalse(manifest.exists())

    def test_run_requires_consent_and_resumes_without_duplicate_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            plan = self.build_plan(root, results, manifest)
            submissions: list[dict] = []
            waits: list[tuple[str, str]] = []
            submit, wait, download = self.successful_transport(submissions, waits)

            with self.assertRaisesRegex(
                pipeline.Wan22ControlError, "allow-external-processing"
            ):
                pipeline.run_jobs(
                    root,
                    manifest,
                    allow_external_processing=False,
                    submitter=submit,
                    waiter=wait,
                    downloader=download,
                )
            self.assertEqual(submissions, [])

            first = pipeline.run_jobs(
                root,
                manifest,
                allow_external_processing=True,
                submitter=submit,
                waiter=wait,
                downloader=download,
            )
            second = pipeline.run_jobs(
                root,
                manifest,
                allow_external_processing=True,
                submitter=submit,
                waiter=wait,
                downloader=download,
            )
            self.assertEqual(first, {"generated": 5, "skipped": 0})
            self.assertEqual(second, {"generated": 0, "skipped": 5})
            self.assertEqual(len(submissions), 5)
            self.assertEqual(len(waits), 5)

            for submission in submissions:
                self.assertEqual(submission["runtime"], pipeline.RUNTIME)
                self.assertEqual(submission["prompt"], submission["prompt"].strip())
                self.assertNotIn("Avoid:", submission["prompt"])
                self.assertEqual(submission["timeout"], 120)

            for job in plan["jobs"]:
                run = json.loads((root / job["artifacts"]["run"]).read_text(encoding="utf-8"))
                self.assertEqual(run["status"], "generated")
                self.assertEqual(run["attempts"], 1)
                self.assertTrue(run["provider_event_id"].startswith("event-"))
                self.assertTrue(run["provider_session_hash"].startswith("session-"))
                self.assertFalse(run["attested_lite_model"])

    def test_interrupted_wait_persists_ids_and_resumes_without_resubmit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            plan = self.build_plan(root, results, manifest)
            first_run_path = root / plan["jobs"][0]["artifacts"]["run"]
            submitted_images: list[Path] = []
            interrupted = False

            def submit(image, prompt, runtime, _timeout):
                submitted_images.append(image)
                self.assertNotIn("Avoid:", prompt)
                self.assertEqual(runtime, pipeline.RUNTIME)
                index = len(submitted_images)
                return f"event-{index}", f"session-{index}"

            def wait(session_hash, event_id, _timeout, on_started):
                nonlocal interrupted
                persisted = json.loads(first_run_path.read_text(encoding="utf-8"))
                if not interrupted:
                    self.assertEqual(persisted["status"], "submitted")
                    self.assertEqual(persisted["provider_event_id"], event_id)
                    self.assertEqual(persisted["provider_session_hash"], session_hash)
                    interrupted = True
                    raise pipeline.ResumableProviderError(
                        "timeout at https://provider.invalid token=secret"
                    )
                on_started()
                return f"https://provider.invalid/{event_id}.mp4"

            def download(_url, destination, _timeout):
                destination.write_bytes(b"fake-mp4")

            with self.assertRaisesRegex(pipeline.Wan22ControlError, "resumable"):
                pipeline.run_jobs(
                    root,
                    manifest,
                    allow_external_processing=True,
                    submitter=submit,
                    waiter=wait,
                    downloader=download,
                )
            submitted = json.loads(first_run_path.read_text(encoding="utf-8"))
            self.assertEqual(submitted["status"], "submitted")
            self.assertEqual(submitted["provider_event_id"], "event-1")
            self.assertEqual(submitted["provider_session_hash"], "session-1")
            self.assertTrue(submitted["error"]["retryable"])
            self.assertNotIn("provider.invalid", json.dumps(submitted))
            self.assertNotIn("secret", json.dumps(submitted))

            result = pipeline.run_jobs(
                root,
                manifest,
                allow_external_processing=True,
                submitter=submit,
                waiter=wait,
                downloader=download,
            )
            self.assertEqual(result, {"generated": 5, "skipped": 0})
            self.assertEqual(len(submitted_images), 5)
            first_source = root / plan["jobs"][0]["source_image"]["path"]
            self.assertEqual(submitted_images.count(first_source), 1)
            completed = json.loads(first_run_path.read_text(encoding="utf-8"))
            self.assertEqual(completed["status"], "generated")
            self.assertEqual(completed["attempts"], 1)

    def test_manifest_run_lock_fails_fast_for_a_second_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            self.build_plan(root, results, manifest)
            with manifest.open("rb") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    with self.assertRaisesRegex(
                        pipeline.Wan22ControlError, "already holds this manifest run lock"
                    ):
                        pipeline.run_jobs(
                            root,
                            manifest,
                            allow_external_processing=True,
                            submitter=lambda *_args: self.fail("must not submit"),
                            waiter=lambda *_args: self.fail("must not wait"),
                            downloader=lambda *_args: self.fail("must not download"),
                        )
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def test_exception_does_not_overwrite_newer_concurrent_completion(self) -> None:
        for provider_exception in (
            pipeline.ResumableProviderError("stream interrupted"),
            pipeline.ProviderSessionLostError("session discarded"),
        ):
            with self.subTest(exception=type(provider_exception).__name__), tempfile.TemporaryDirectory() as directory:
                root, results, manifest = self.make_workspace(directory)
                plan = self.build_plan(root, results, manifest)
                first = plan["jobs"][0]
                first_run_path = root / first["artifacts"]["run"]
                first_video_path = root / first["artifacts"]["video"]
                submissions = 0
                injected = False

                def submit(_image, _prompt, _runtime, _timeout):
                    nonlocal submissions
                    submissions += 1
                    return f"event-{submissions}", f"session-{submissions}"

                def wait(_session, _event, _timeout, on_started):
                    nonlocal injected
                    if not injected:
                        injected = True
                        video_bytes = b"concurrent-completed-mp4"
                        first_video_path.write_bytes(video_bytes)
                        newest = json.loads(first_run_path.read_text(encoding="utf-8"))
                        newest.update(
                            {
                                "status": "generated",
                                "output": {
                                    "path": first["artifacts"]["video"],
                                    "sha256": hashlib.sha256(video_bytes).hexdigest(),
                                    "bytes": len(video_bytes),
                                },
                                "error": None,
                                "updated_at": "concurrent-newest",
                            }
                        )
                        pipeline.atomic_write_json(first_run_path, newest)
                        raise provider_exception
                    on_started()
                    return "https://provider.invalid/video.mp4"

                def download(_url, destination, _timeout):
                    destination.write_bytes(b"normal-completed-mp4")

                result = pipeline.run_jobs(
                    root,
                    manifest,
                    allow_external_processing=True,
                    submitter=submit,
                    waiter=wait,
                    downloader=download,
                )
                self.assertEqual(result, {"generated": 4, "skipped": 1})
                self.assertEqual(submissions, 5)
                preserved = json.loads(first_run_path.read_text(encoding="utf-8"))
                self.assertEqual(preserved["status"], "generated")
                self.assertEqual(preserved["updated_at"], "concurrent-newest")
                self.assertIsNone(preserved["error"])

    def test_recovery_requires_exact_receipt_and_prior_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            plan = self.build_plan(root, results, manifest)
            job = plan["jobs"][0]
            run_path = root / job["artifacts"]["run"]
            video_path = root / job["artifacts"]["video"]
            video_bytes = b"receipt-bound-completion"
            video_path.write_bytes(video_bytes)
            failed = json.loads(run_path.read_text(encoding="utf-8"))
            failed.update({"status": "failed", "attempts": 1, "error": {"summary": "race"}})
            pipeline.atomic_write_json(run_path, failed)
            expected_sha256 = hashlib.sha256(video_bytes).hexdigest()

            with self.assertRaisesRegex(pipeline.Wan22ControlError, "does not match"):
                pipeline.recover_generated_job(
                    root,
                    manifest,
                    job["job_id"],
                    "0" * 64,
                    len(video_bytes),
                )
            self.assertEqual(json.loads(run_path.read_text(encoding="utf-8"))["status"], "failed")

            recovered = pipeline.recover_generated_job(
                root,
                manifest,
                job["job_id"],
                expected_sha256,
                len(video_bytes),
            )
            self.assertEqual(recovered["status"], "generated")
            self.assertEqual(recovered["output"]["sha256"], expected_sha256)
            self.assertEqual(recovered["recovery"]["method"], "explicit-sha256-and-size")

            pending_job = plan["jobs"][1]
            pending_video = root / pending_job["artifacts"]["video"]
            pending_video.write_bytes(video_bytes)
            with self.assertRaisesRegex(pipeline.Wan22ControlError, "attempted"):
                pipeline.recover_generated_job(
                    root,
                    manifest,
                    pending_job["job_id"],
                    expected_sha256,
                    len(video_bytes),
                )

    def test_failed_job_is_redacted_and_not_retried_implicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            plan = self.build_plan(root, results, manifest)
            submissions = 0

            def submit(_image, _prompt, _runtime, _timeout):
                nonlocal submissions
                submissions += 1
                return "event-failed", "session-failed"

            def fail_wait(_session, _event, _timeout, _on_started):
                raise pipeline.Wan22ControlError(
                    "POST https://provider.invalid/job "
                    "Authorization: OAuth secret token=also-secret"
                )

            with self.assertRaisesRegex(pipeline.Wan22ControlError, "failed"):
                pipeline.run_jobs(
                    root,
                    manifest,
                    allow_external_processing=True,
                    submitter=submit,
                    waiter=fail_wait,
                    downloader=lambda _url, _path, _timeout: None,
                )
            first_run_path = root / plan["jobs"][0]["artifacts"]["run"]
            first_run = json.loads(first_run_path.read_text(encoding="utf-8"))
            serialized = json.dumps(first_run).lower()
            self.assertEqual(first_run["status"], "failed")
            self.assertNotIn("provider.invalid", serialized)
            self.assertNotIn("secret", serialized)

            with self.assertRaisesRegex(pipeline.Wan22ControlError, "retry-failed"):
                pipeline.run_jobs(
                    root,
                    manifest,
                    allow_external_processing=True,
                    submitter=submit,
                    waiter=fail_wait,
                    downloader=lambda _url, _path, _timeout: None,
                )
            self.assertEqual(submissions, 1)

    def test_combined_prompt_is_conditional_on_an_actual_negative(self) -> None:
        self.assertEqual(pipeline.combine_prompt("move once", None), "move once")
        self.assertEqual(pipeline.combine_prompt("move once", ""), "move once")
        self.assertEqual(
            pipeline.combine_prompt("move once", "flicker"),
            "move once\n\nAvoid: flicker",
        )

    def test_sse_interruption_reconnects_the_same_session(self) -> None:
        completed = {
            "msg": "process_completed",
            "event_id": "event-locked",
            "success": True,
            "output": {"data": [{"url": "https://provider.invalid/video.mp4"}]},
        }
        starts = {"msg": "process_starts", "event_id": "event-locked"}

        class Stream:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return iter(
                    [
                        f"data: {json.dumps(starts)}\n".encode(),
                        b"\n",
                        f"data: {json.dumps(completed)}\n".encode(),
                        b"\n",
                    ]
                )

        opened_urls: list[str] = []

        def opener(request, timeout):
            del timeout
            opened_urls.append(request.full_url)
            if len(opened_urls) == 1:
                raise URLError("socket timeout")
            return Stream()

        started = 0

        def on_started():
            nonlocal started
            started += 1

        result = pipeline.wait_wan_job(
            "session-locked",
            "event-locked",
            10,
            on_started,
            opener=opener,
            sleeper=lambda _seconds: None,
        )
        self.assertEqual(result, "https://provider.invalid/video.mp4")
        self.assertEqual(started, 1)
        self.assertEqual(len(opened_urls), 2)
        self.assertEqual(opened_urls[0], opened_urls[1])
        self.assertIn("session_hash=session-locked", opened_urls[0])

    def test_720p_class_accepts_live_3_by_2_dimensions_and_rejects_aspect_drift(self) -> None:
        live_media = {
            "width": 1152,
            "height": 768,
            "fps": 30.0,
            "frames": 97,
            "duration_seconds": 3.233333,
        }
        pipeline._validate_media(live_media, "live", (1500, 1000))
        with self.assertRaisesRegex(pipeline.Wan22ControlError, "aspect ratio"):
            pipeline._validate_media(
                {**live_media, "width": 1280, "height": 720},
                "drifted",
                (1500, 1000),
            )

    def test_verify_checks_media_contract_and_is_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, results, manifest = self.make_workspace(directory)
            plan = self.build_plan(root, results, manifest)
            submit, wait, download = self.successful_transport([], [])
            pipeline.run_jobs(
                root,
                manifest,
                allow_external_processing=True,
                submitter=submit,
                waiter=wait,
                downloader=download,
            )
            probes: list[Path] = []

            def probe(path: Path) -> dict:
                probes.append(path)
                return {
                    "width": 1152,
                    "height": 768,
                    "fps": 30.0,
                    "frames": 97,
                    "duration_seconds": 97 / 30,
                }

            first = pipeline.verify_jobs(root, manifest, probe=probe)
            second = pipeline.verify_jobs(root, manifest, probe=probe)
            self.assertEqual(first, {"verified": 5, "already_verified": 0})
            self.assertEqual(second, {"verified": 0, "already_verified": 5})
            self.assertEqual(len(probes), 5)
            for job in plan["jobs"]:
                run = json.loads((root / job["artifacts"]["run"]).read_text(encoding="utf-8"))
                self.assertEqual(run["status"], "verified")
                self.assertEqual(run["media"]["frames"], 97)
                self.assertEqual(run["media"]["source_width"], 1500)
                self.assertEqual(run["media"]["source_height"], 1000)


if __name__ == "__main__":
    unittest.main()
