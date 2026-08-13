#!/usr/bin/env python3
"""Network-free tests for the live-images S3 exporter."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import promopages_live_images_s3_export as exporter


def _strict_acceptance(model_id: str) -> dict:
    return {
        "accepted": True,
        "mode": "strict-contract",
        "policy_id": None,
        "policy_sha256": None,
        "model_id": model_id,
        "adapter": (
            "eliza-segmind" if model_id == "alibaba/wan-2.2" else "eliza-openrouter"
        ),
        "target_generate_audio": False,
        "observed_has_audio": False,
        "waived_warnings": [],
    }


class LiveImagesS3ExportTest(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def make_fixture(
        self, directory: str, *, one_unavailable: bool = False
    ) -> tuple[Path, Path, Path]:
        root = Path(directory) / "workspace"
        root.mkdir(parents=True)
        outputs = []
        index = 0
        for article_slug, route in exporter.ARTICLE_ROUTES.items():
            for model_id in exporter.MODEL_IDS:
                index += 1
                unavailable = one_unavailable and index == 6
                if unavailable:
                    outputs.append(
                        {
                            "article_number": route["article_number"],
                            "article_slug": article_slug,
                            "publication_id": route["publication_id"],
                            "image_id": route["image_id"],
                            "media_id": route["media_id"],
                            "model_id": model_id,
                            "status": "unavailable",
                            "recorded_status": None,
                            "selected_attempt_id": None,
                            "selected_prompt": None,
                            "provider_run_id": None,
                            "video_path": None,
                            "media": None,
                            "contract_check": None,
                            "media_acceptance": None,
                            "error": "fixture provider failure",
                            "attempt_count": 1,
                            "attempts": [],
                        }
                    )
                    continue
                payload = f"fixture-{article_slug}-{model_id}".encode("utf-8")
                video = root / "generated" / f"video-{index}.mp4"
                video.parent.mkdir(parents=True, exist_ok=True)
                video.write_bytes(payload)
                sha256 = hashlib.sha256(payload).hexdigest()
                outputs.append(
                    {
                        "article_number": route["article_number"],
                        "article_slug": article_slug,
                        "publication_id": route["publication_id"],
                        "image_id": route["image_id"],
                        "media_id": route["media_id"],
                        "model_id": model_id,
                        "status": "succeeded",
                        "recorded_status": "succeeded",
                        "selected_attempt_id": "primary",
                        "selected_prompt": {"positive": "fixture", "negative": None},
                        "provider_run_id": f"provider-{index}",
                        "video_path": video.relative_to(root).as_posix(),
                        "media": {
                            "bytes": len(payload),
                            "sha256": sha256,
                            "codec": "h264",
                            "duration_seconds": 5,
                            "width": 1280,
                            "height": 720,
                            "has_audio": False,
                        },
                        "contract_check": {
                            "requested": {"generate_audio": False},
                            "checks": {"audio": True},
                            "conforms": True,
                            "warnings": [],
                        },
                        "media_acceptance": _strict_acceptance(model_id),
                        "error": None,
                        "attempt_count": 1,
                        "attempts": [],
                    }
                )
        final = {
            "schema_version": 1,
            "manifest_role": "clipmaker-lite-final-selection",
            "dataset_prefix": "PROMOPAGES-live-images-20260813-v1",
            "batch_id": exporter.BATCH_ID,
            "producer": {
                "agent_id": "clipmaker-lite",
                "contract_version": "2.1.4",
                "runner_version": 8,
            },
            "models": list(exporter.MODEL_IDS),
            "article_count": 2,
            "image_count": 2,
            "expected_outputs": 6,
            "cost": {},
            "articles": [],
            "outputs": outputs,
        }
        manifest = root / "final-selection.json"
        self.write_json(manifest, final)
        return root, manifest, root / "export"

    def build_fixture(
        self, directory: str, *, one_unavailable: bool = False
    ) -> tuple[Path, Path, dict]:
        root, final, output = self.make_fixture(
            directory, one_unavailable=one_unavailable
        )
        manifest = exporter.build_export(
            root, final, output, materialize_mode="copy"
        )
        return root, output, manifest

    def test_build_uses_exact_publication_scoped_hash_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, output, manifest = self.build_fixture(directory)
            self.assertEqual(manifest["counts"]["ready_outputs"], 6)
            for row in manifest["outputs"]:
                route = exporter.ARTICLE_ROUTES[row["article_slug"]]
                expected = (
                    f"front-images/exp_video/{route['cabinet_slug']}__{route['cabinet_id']}/"
                    f"{route['publication_id']}/{exporter.MODEL_DIRS[row['model_id']]}/"
                    f"image_{route['image_id']}--sha256-{row['media']['sha256'][:12]}.mp4"
                )
                self.assertEqual(row["object_key"], expected)
                self.assertEqual(row["yastatic_url"], exporter.PUBLIC_BASE_URL + expected)
            self.assertTrue(exporter.verify_export(output)["verified"])

    def test_unavailable_output_never_gets_an_upload_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, output, manifest = self.build_fixture(
                directory, one_unavailable=True
            )
            self.assertEqual(manifest["counts"]["ready_outputs"], 5)
            unavailable = [
                row for row in manifest["outputs"] if row["package_status"] == "unavailable"
            ]
            self.assertEqual(len(unavailable), 1)
            self.assertIsNone(unavailable[0]["object_key"])
            self.assertTrue(exporter.verify_export(output)["verified"])

    def test_rejects_audio_exception_with_any_non_audio_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, final_path, output = self.make_fixture(directory)
            final = json.loads(final_path.read_text(encoding="utf-8"))
            target = next(
                row
                for row in final["outputs"]
                if row["model_id"] == "alibaba/wan-2.7"
            )
            target["recorded_status"] = "verification-failed"
            target["media"]["has_audio"] = True
            audio_only_check = {
                "conforms": False,
                "warnings": ["audio"],
                "checks": {"audio": False, "resolution": True},
                "requested": {"generate_audio": False},
            }
            entry = exporter.native.Entry(
                exporter.native.Sample(
                    "s3-fixture",
                    target["article_slug"],
                    target["image_id"],
                    "fixture.png",
                    "0" * 64,
                    2000,
                    1125,
                ),
                target["model_id"],
            )
            target["media_acceptance"] = exporter.native.media_acceptance(
                entry, target["media"], audio_only_check
            )
            target["contract_check"] = {
                **audio_only_check,
                "warnings": ["audio", "resolution"],
                "checks": {"audio": False, "resolution": False},
            }
            self.write_json(final_path, final)
            with self.assertRaisesRegex(exporter.ExportError, "Succeeded selection"):
                exporter.build_export(_root, final_path, output, materialize_mode="copy")

    def test_upload_dry_run_never_invokes_yc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, output, _manifest = self.build_fixture(directory)

            def forbidden(*_args, **_kwargs):
                raise AssertionError("dry-run invoked yc")

            result = exporter.upload_export(output, execute=False, runner=forbidden)
            self.assertEqual(result["mode"], "dry-run")
            self.assertEqual(result["external_writes"], 0)
            self.assertEqual(result["operation_count"], 6)

    def test_execute_skips_exact_existing_objects_and_writes_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, output, manifest = self.build_fixture(directory)
            by_key = {row["object_key"]: row for row in manifest["outputs"]}

            def fake_runner(command, capture_output=True, text=True):
                self.assertTrue(capture_output)
                self.assertTrue(text)
                if "list-objects-v2" in command:
                    return subprocess.CompletedProcess(command, 0, "{}", "")
                if "head-object" in command:
                    key = command[command.index("--key") + 1]
                    row = by_key[key]
                    head = {
                        "ContentLength": row["media"]["bytes"],
                        "ContentType": exporter.CONTENT_TYPE,
                        "CacheControl": exporter.CACHE_CONTROL,
                        "ContentDisposition": "inline",
                        "Metadata": {
                            "sha256": row["media"]["sha256"],
                            "publication-id": row["publication_id"],
                            "image-id": row["image_id"],
                            "experiment": row["experiment"],
                        },
                    }
                    return subprocess.CompletedProcess(command, 0, json.dumps(head), "")
                raise AssertionError(f"unexpected yc command: {command}")

            report = exporter.upload_export(
                output,
                execute=True,
                yc_profile="fixture",
                runner=fake_runner,
                verify_cdn=lambda row: {
                    "verified": True,
                    "content_length": row["media"]["bytes"],
                },
            )
            self.assertEqual(report["counts"], {
                "total": 6,
                "uploaded": 0,
                "skipped": 6,
                "verified": 6,
            })
            delivery = json.loads((output / "delivery-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(delivery["verified_output_count"], 6)

    def test_execute_refuses_immutable_key_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, output, _manifest = self.build_fixture(directory)

            def fake_runner(command, capture_output=True, text=True):
                if "list-objects-v2" in command:
                    return subprocess.CompletedProcess(command, 0, "{}", "")
                if "head-object" in command:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        json.dumps(
                            {
                                "ContentLength": 1,
                                "ContentType": "application/octet-stream",
                                "Metadata": {},
                            }
                        ),
                        "",
                    )
                raise AssertionError(f"unexpected yc command: {command}")

            with self.assertRaisesRegex(exporter.ExportError, "refusing overwrite"):
                exporter.upload_export(
                    output,
                    execute=True,
                    yc_profile="fixture",
                    runner=fake_runner,
                    verify_cdn=lambda _row: {"verified": True},
                )

    def test_verify_detects_payload_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, output, manifest = self.build_fixture(directory)
            first = next(row for row in manifest["outputs"] if row["package_status"] == "ready")
            payload = output / "upload" / first["relative_path"]
            payload.write_bytes(b"tampered")
            with self.assertRaisesRegex(exporter.ExportError, "digest"):
                exporter.verify_export(output)


if __name__ == "__main__":
    unittest.main()
