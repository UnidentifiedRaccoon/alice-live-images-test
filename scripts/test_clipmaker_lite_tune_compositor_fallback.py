from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import clipmaker_lite_tune_compositor as renderer
from scripts import clipmaker_lite_tune_compositor_fallback as fallback


class ClipmakerLiteTuneCompositorFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plans, cls.targets = fallback.load_fallback_targets()

    def test_exact_two_i2v_terminal_failure_targets(self) -> None:
        self.assertEqual({target.key for target in self.targets}, fallback.EXPECTED_KEYS)
        self.assertEqual(len(self.targets), 2)
        for target in self.targets:
            with self.subTest(key=target.key):
                self.assertEqual(target.render.model_id, "google/veo-3.1-lite")
                self.assertEqual(target.render.duration_seconds, 4)
                self.assertEqual(target.render.expected_frames, 120)
                self.assertIn(
                    target.render.plan["primitive"], {"camera_push", "pan"}
                )
                self.assertEqual(
                    target.provider_failure["status"], "provider-failed"
                )
                self.assertIn(
                    "completed with no output",
                    target.provider_failure["terminal_error"],
                )

    def test_provider_run_and_prompt_are_exact_sha_bound_terminal_receipts(self) -> None:
        expected_jobs = {
            "07#06": "lkVqOh5FmFC2nj931yFH",
            "10#07": "vix3OSm0iISSLk0ZtLoR",
        }
        for target in self.targets:
            with self.subTest(key=target.key):
                binding = target.provider_failure
                run_path = fallback.ROOT / binding["run_path"]
                prompt_path = fallback.ROOT / binding["prompt_path"]
                self.assertEqual(renderer.sha256_file(run_path), binding["run_sha256"])
                self.assertEqual(
                    renderer.sha256_file(prompt_path), binding["prompt_sha256"]
                )
                run = renderer.read_json(run_path)
                self.assertEqual(run["status"], "provider-failed")
                self.assertFalse(run["provider_may_be_active"])
                self.assertFalse(run["automatic_paid_retry"])
                self.assertIsNone(run["media"])
                self.assertEqual(
                    run["provider_job_id"], expected_jobs[target.render.case_id]
                )
                self.assertFalse(
                    (fallback.ROOT / target.canonical_video_path).exists()
                )

    def test_original_execution_mode_is_not_relabelled_compositor(self) -> None:
        tune = renderer.read_json(fallback.ROOT / renderer.TUNE_MANIFEST_REL)
        projection = {
            (row["case_id"], row["model_id"]): row
            for row in fallback.fallback_projection(tune)
        }
        for target in self.targets:
            with self.subTest(key=target.key):
                self.assertEqual(projection[target.key]["execution_mode"], "i2v")
                self.assertNotEqual(
                    projection[target.key]["execution_mode"],
                    "deterministic-compositor",
                )
                self.assertTrue(
                    target.render.output_path.as_posix().startswith(
                        fallback.VIDEO_ROOT_REL.as_posix() + "/"
                    )
                )
                self.assertFalse(
                    target.render.output_path.as_posix().startswith(
                        renderer.VIDEO_ROOT_REL.as_posix() + "/"
                    )
                )

    def test_render_commands_are_camera_only_local_and_no_audio(self) -> None:
        for value in self.targets:
            target = value.render
            with self.subTest(key=target.key):
                command, width, height = renderer.command_for_target(
                    target,
                    fallback.ROOT / target.source_path,
                    Path("fallback.mp4"),
                    "/usr/bin/ffmpeg",
                )
                joined = " ".join(command)
                self.assertNotIn("http://", joined)
                self.assertNotIn("https://", joined)
                self.assertNotIn("s3", joined.lower())
                self.assertNotIn("-filter_complex", command)
                self.assertIn("-an", command)
                self.assertEqual(command[command.index("-frames:v") + 1], "120")
                self.assertLessEqual(width, 1920)
                self.assertLessEqual(height, 1080)

    def test_changed_provider_run_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_rel = Path("runs/failure.run.json")
            prompt_rel = Path("runs/failure.prompt.json")
            run_path = root / run_rel
            prompt_path = root / prompt_rel
            run_path.parent.mkdir(parents=True)
            prompt_path.write_text("{}\n", encoding="utf-8")
            run = {
                "manifest_role": "clipmaker-lite-tune-video-run",
                "batch_id": fallback.PROVIDER_BATCH_ID,
                "agent_id": "clipmaker-lite",
                "provider_run_id": "provider-run",
                "case_id": "07#06",
                "model_id": "google/veo-3.1-lite",
                "execution_mode": "i2v",
                "status": "provider-failed",
                "provider_job_id": "job-id",
                "error": "terminal error",
                "provider_may_be_active": False,
                "automatic_paid_retry": False,
                "media": None,
                "contract_check": None,
                "completed_at": "2026-08-11T00:00:00Z",
                "request": {
                    "model": "google/veo-3.1-lite",
                    "duration": 4,
                    "generate_audio": False,
                },
            }
            renderer.atomic_write_json(run_path, run)
            binding = {
                "provider_run_id": "provider-run",
                "run_path": run_rel.as_posix(),
                "run_sha256": renderer.sha256_file(run_path),
                "prompt_path": prompt_rel.as_posix(),
                "prompt_sha256": renderer.sha256_file(prompt_path),
                "status": "provider-failed",
                "provider_job_id": "job-id",
                "terminal_error": "terminal error",
            }
            generation = {
                "provider_run_id": "provider-run",
                "run_path": run_rel.as_posix(),
                "prompt_path": prompt_rel.as_posix(),
                "status": "provider-failed",
                "execution_mode": "i2v",
                "media": None,
                "contract_check": None,
                "error": "terminal error",
                "video_path": "runs/provider-output.mp4",
            }
            run["error"] = "changed after terminal receipt"
            renderer.atomic_write_json(run_path, run)
            with self.assertRaisesRegex(
                fallback.TuneFallbackError, "run/prompt SHA-256 changed"
            ):
                fallback._validate_provider_failure(
                    binding,
                    generation,
                    root=root,
                    key=("07#06", "google/veo-3.1-lite"),
                )

    def test_rendered_fallback_aggregate_is_separate_and_verified(self) -> None:
        aggregate_path = fallback.ROOT / fallback.AGGREGATE_REL
        if not aggregate_path.is_file():
            self.skipTest("fallback render has not been materialized yet")
        result = fallback.verify_batch()
        self.assertTrue(result["verified"])
        aggregate = renderer.read_json(aggregate_path)
        self.assertEqual(aggregate["method"], fallback.METHOD)
        self.assertEqual(aggregate["summary"], {"succeeded": 2})
        self.assertFalse(aggregate["scope"]["tune_manifest_mutation"])
        self.assertFalse(
            aggregate["scope"]["canonical_compositor_manifest_mutation"]
        )
        for row in aggregate["outputs"]:
            self.assertEqual(row["execution_mode"], "i2v")
            self.assertEqual(row["original_execution_mode"], "i2v")
            self.assertEqual(row["method"], fallback.METHOD)
            self.assertEqual(row["media"]["duration_seconds"], 4.0)
            self.assertEqual(row["media"]["frames"], 120)
            self.assertEqual(row["media"]["audio_streams"], 0)
            self.assertTrue(all(row["contract_check"].values()))


if __name__ == "__main__":
    unittest.main()
