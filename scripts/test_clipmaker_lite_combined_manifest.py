#!/usr/bin/env python3
"""Focused tests for the Clipmaker Lite combined manifest aggregator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import clipmaker_lite_combined_manifest as combined


class ClipmakerLiteCombinedManifestTest(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def make_workspace(self, directory: str) -> tuple[Path, dict, dict]:
        root = Path(directory)
        native_outputs: list[dict] = []
        control_jobs: list[dict] = []
        runtime = {
            "resolution": "720p",
            "frames": 97,
            "fps": 30,
            "seed": 1,
            "loop": False,
            "last_frame": None,
        }

        for sample in range(1, 6):
            stem = f"0{sample}"
            article_slug = f"{stem}-article"
            source_path = f"PROMOPAGES-9857/articles/{article_slug}/{stem}.png"
            (root / source_path).parent.mkdir(parents=True, exist_ok=True)
            (root / source_path).write_bytes(b"image")
            wan_run_id = f"promopages-9891-schemafix-{stem}-sample-wan-2-7"

            for model_id, directory_name, run_id in (
                ("alibaba/wan-2.7", "wan-2.7", wan_run_id),
                (
                    "google/veo-3.1-lite",
                    "veo-3.1-lite",
                    f"promopages-9891-schemafix-{stem}-sample-veo-3-1-lite",
                ),
            ):
                base = (
                    f"PROMOPAGES-9857/articles/{article_slug}/"
                    f"clipmaker-lite/{directory_name}/{stem}"
                )
                native_outputs.append(
                    {
                        "lite_run_id": run_id,
                        "sample_id": f"{stem}-sample",
                        "article_slug": article_slug,
                        "source_path": source_path,
                        "model_id": model_id,
                        "status": "pending",
                        "prompt_path": f"{base}.prompt.json",
                        "run_path": f"{base}.run.json",
                        "video_path": f"{base}.mp4",
                        "media": None,
                        "contract_check": None,
                        "error": None,
                    }
                )

            control_base = (
                f"PROMOPAGES-9857/articles/{article_slug}/"
                f"clipmaker-lite/wan-streamlit-wan-2.2/{stem}"
            )
            job_id = f"{article_slug}-{stem}-wan-streamlit-wan-2-2"
            artifacts = {
                "prompt": f"{control_base}.prompt.json",
                "run": f"{control_base}.run.json",
                "video": f"{control_base}.mp4",
            }
            prompt_source = {
                "result_path": f"artifacts/clipmaker-lite/v1/{wan_run_id}/result.json",
                "result_sha256": f"sha256-{sample}",
                "result_job_id": wan_run_id,
                "lite_provenance": {
                    "verified": True,
                    "agent_id": "clipmaker-lite",
                },
            }
            control_jobs.append(
                {
                    "schema_version": 1,
                    "job_id": job_id,
                    "source_image": {
                        "path": source_path,
                        "sha256": f"image-sha256-{sample}",
                        "bytes": 5,
                    },
                    "target_model_id": "alibaba/wan-2.2",
                    "prompt_source_model_id": "alibaba/wan-2.7",
                    "provider_route": "wan-streamlit",
                    "attested_lite_model": False,
                    "runtime": runtime,
                    "prompt": {"positive_prompt": f"Prompt {sample}"},
                    "prompt_source": prompt_source,
                    "artifacts": artifacts,
                }
            )
            self.write_json(root / artifacts["prompt"], {"prompt": f"Prompt {sample}"})
            self.write_json(
                root / artifacts["run"],
                {
                    "schema_version": 1,
                    "job_id": job_id,
                    "target_model_id": "alibaba/wan-2.2",
                    "prompt_source_model_id": "alibaba/wan-2.7",
                    "provider_route": "wan-streamlit",
                    "attested_lite_model": False,
                    "runtime": runtime,
                    "status": "pending",
                    "attempts": 0,
                    "output": None,
                    "media": None,
                    "error": None,
                },
            )

        native = {
            "schema_version": 1,
            "ticket": "PROMOPAGES-9891",
            "agent_id": "clipmaker-lite",
            "expected_outputs": 10,
            "summary": {"pending": 10},
            "outputs": native_outputs,
        }
        control = {
            "schema_version": 1,
            "control_id": "promopages-9891-wan-streamlit-wan-2.2",
            "target_model_id": "alibaba/wan-2.2",
            "prompt_source_model_id": "alibaba/wan-2.7",
            "provider_route": "wan-streamlit",
            "attested_lite_model": False,
            "runtime": runtime,
            "job_count": 5,
            "jobs": control_jobs,
        }
        self.write_json(root / combined.DEFAULT_NATIVE_MANIFEST, native)
        self.write_json(root / combined.DEFAULT_CONTROL_PLAN, control)
        return root, native, control

    def complete_workspace(self, root: Path, native: dict, control: dict) -> None:
        media = {
            "width": 1280,
            "height": 720,
            "duration_seconds": 4.0,
            "bytes": 123,
            "sha256": "media-sha256",
        }
        contract = {
            "requested": {"resolution": "1080p"},
            "checks": {"duration": True},
            "conforms": True,
            "warnings": [],
        }
        for output in native["outputs"]:
            output["status"] = "succeeded"
            output["media"] = media
            output["contract_check"] = contract
            for key in ("prompt_path", "run_path"):
                self.write_json(root / output[key], {"output_id": output["lite_run_id"]})
            path = root / output["video_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"mp4")
        native["summary"] = {"succeeded": 10}
        self.write_json(root / combined.DEFAULT_NATIVE_MANIFEST, native)

        for job in control["jobs"]:
            run_path = root / job["artifacts"]["run"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run.update(
                {
                    "status": "verified",
                    "output": {
                        "path": job["artifacts"]["video"],
                        "sha256": "control-sha256",
                        "bytes": 3,
                    },
                    "media": {
                        "width": 1280,
                        "height": 720,
                        "fps": 30.0,
                        "frames": 97,
                        "duration_seconds": 97 / 30,
                    },
                }
            )
            self.write_json(run_path, run)
            video_path = root / job["artifacts"]["video"]
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"mp4")

    def test_build_and_verify_incomplete_then_complete_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, native, control = self.make_workspace(directory)
            manifest = combined.build_combined_manifest(root)

            self.assertEqual(manifest["expected_outputs"], 15)
            self.assertEqual(manifest["status"], "incomplete")
            self.assertEqual(manifest["summary"]["by_status"], {"pending": 15})
            self.assertEqual(manifest["summary"]["by_route"]["native"]["total"], 10)
            self.assertEqual(
                manifest["summary"]["by_route"]["wan-streamlit-control"]["total"],
                5,
            )
            native_rows = [row for row in manifest["outputs"] if row["route"] == "native"]
            controls = [
                row
                for row in manifest["outputs"]
                if row["route"] == "wan-streamlit-control"
            ]
            self.assertTrue(all(row["attested_lite_model"] for row in native_rows))
            self.assertTrue(all(not row["attested_lite_model"] for row in controls))
            self.assertTrue(
                all(row["prompt_source_model_id"] == row["target_model_id"] for row in native_rows)
            )
            self.assertTrue(
                all(row["prompt_source_model_id"] == "alibaba/wan-2.7" for row in controls)
            )
            self.assertEqual(
                controls[0]["video_path"], control["jobs"][0]["artifacts"]["video"]
            )
            combined.verify_combined_manifest(root, allow_incomplete=True)
            with self.assertRaisesRegex(combined.CombinedManifestError, "expected 15"):
                combined.verify_combined_manifest(root)

            self.complete_workspace(root, native, control)
            completed = combined.build_combined_manifest(root)
            self.assertEqual(completed["status"], "complete")
            self.assertEqual(completed["summary"]["completed"], 15)
            verified = combined.verify_combined_manifest(root)
            self.assertEqual(verified["summary"]["by_status"], {"succeeded": 10, "verified": 5})
            self.assertTrue(
                all(row["contract_check"]["conforms"] for row in verified["outputs"])
            )

    def test_build_rejects_url_or_token_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _native, control = self.make_workspace(directory)
            run_path = root / control["jobs"][0]["artifacts"]["run"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["error"] = "provider failed at https://provider.invalid/job"
            self.write_json(run_path, run)
            with self.assertRaisesRegex(combined.CombinedManifestError, "URL leaked"):
                combined.build_combined_manifest(root)
            self.assertFalse((root / combined.DEFAULT_OUTPUT).exists())

            run["error"] = None
            run["token"] = "secret"
            self.write_json(run_path, run)
            with self.assertRaisesRegex(combined.CombinedManifestError, "forbidden metadata key"):
                combined.build_combined_manifest(root)


if __name__ == "__main__":
    unittest.main()
