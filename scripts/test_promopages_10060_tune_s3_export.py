#!/usr/bin/env python3
"""Network-free focused tests for the exact-45 Tune S3 exporter."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import promopages_10060_tune_s3_export as exporter


class TuneApprovedS3ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = exporter.REPO_ROOT
        cls.output = Path(cls.temporary.name) / "output"
        cls.manifest = exporter.build_export(
            cls.root,
            exporter.DEFAULT_CONTRACT_PATH,
            cls.output,
            materialize_mode="hardlink",
        )
        cls.by_key = {
            row["object_key"]: row for row in cls.manifest["outputs"]
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @staticmethod
    def _completed(
        stdout: str = "{}", stderr: str = "", returncode: int = 0
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr=stderr
        )

    @classmethod
    def _head_payload(cls, row: dict, *, sha256: str | None = None) -> str:
        return json.dumps({
            "content_length": row["bytes"],
            "content_type": exporter.base.CONTENT_TYPE,
            "cache_control": exporter.base.CACHE_CONTROL,
            "content_disposition": "inline",
            "metadata": {
                "sha256": sha256 or row["sha256"],
                "publication-id": row["publication_id"],
                "image-id": row["image_id"],
                "experiment": row["experiment"],
            },
        })

    def test_frozen_selection_is_exact_and_current(self) -> None:
        contract, rows, _articles = exporter.validate_selection(
            self.root, exporter.DEFAULT_CONTRACT_PATH
        )
        self.assertEqual(len(rows), 45)
        self.assertEqual(
            contract["expected_counts"]["models"],
            exporter.EXPECTED_MODELS,
        )
        self.assertEqual(
            {row["approval_kind"] for row in rows},
            {"helped", "explicit-latest-wan"},
        )
        forced = {
            row["evaluation_id"]: row
            for row in rows
            if row["approval_kind"] == "explicit-latest-wan"
        }
        self.assertEqual(set(forced), set(exporter.FORCED_IDS))
        self.assertEqual(forced[exporter.FORCED_IDS[0]]["sheet_row"], 246)
        self.assertEqual(forced[exporter.FORCED_IDS[1]]["sheet_row"], 261)
        self.assertEqual(
            len({row["source_video_path"] for row in rows}), 45
        )
        self.assertEqual(len({row["sha256"] for row in rows}), 45)

    def test_build_verify_and_dry_run_are_exact_and_network_free(self) -> None:
        verified = exporter.verify_export(self.output, root=self.root)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["selected_outputs"], 45)
        self.assertEqual(verified["bytes"], 405981270)
        calls: list[list[str]] = []

        def forbidden(command: list[str], **_kwargs: object):
            calls.append(command)
            raise AssertionError("dry-run invoked yc")

        overlay = Path(self.temporary.name) / "dry-run-overlay.json"
        result = exporter.upload_export(
            self.output,
            execute=False,
            root=self.root,
            overlay_path=overlay,
            runner=forbidden,
        )
        self.assertEqual(result["operation_count"], 45)
        self.assertEqual(result["external_calls"], 0)
        self.assertEqual(result["external_writes"], 0)
        self.assertFalse(result["overlay_written"])
        self.assertFalse(overlay.exists())
        self.assertEqual(calls, [])

    def test_keys_follow_existing_content_addressed_convention(self) -> None:
        keys = [row["object_key"] for row in self.manifest["outputs"]]
        self.assertEqual(len(keys), len(set(keys)))
        for row in self.manifest["outputs"]:
            expected_tail = (
                f"/{row['experiment']}/image_{row['image_id']}"
                f"--sha256-{row['sha256'][:12]}.mp4"
            )
            self.assertTrue(row["object_key"].startswith(
                "front-images/exp_video/"
            ))
            self.assertTrue(row["object_key"].endswith(expected_tail))
            self.assertEqual(
                row["yastatic_url"],
                exporter.base.PUBLIC_BASE_URL + row["object_key"],
            )

    def test_execute_is_idempotent_and_publishes_overlay_after_45_heads(
        self,
    ) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str], **_kwargs: object):
            commands.append(command)
            if "list-objects-v2" in command:
                return self._completed()
            if "head-object" in command:
                key = command[command.index("--key") + 1]
                return self._completed(self._head_payload(self.by_key[key]))
            raise AssertionError(f"unexpected command: {command}")

        overlay = Path(self.temporary.name) / "verified-overlay.json"
        yastatic_calls: list[str] = []

        def yastatic(row: dict) -> dict:
            yastatic_calls.append(row["object_key"])
            return {"verified": True, "head_status": 200}

        first = exporter.upload_export(
            self.output,
            execute=True,
            root=self.root,
            yc_profile="test-profile",
            overlay_path=overlay,
            runner=runner,
            yastatic_verifier=yastatic,
        )
        self.assertEqual(first["counts"], {
            "total": 45, "uploaded": 0, "skipped": 45, "verified": 45
        })
        self.assertEqual(len(yastatic_calls), 45)
        document = json.loads(overlay.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["manifest_role"], exporter.OVERLAY_ROLE)
        self.assertEqual(document["selected_output_count"], 45)
        self.assertEqual(document["model_counts"], exporter.EXPECTED_MODELS)
        self.assertEqual(len(document["outputs"]), 45)

        before = overlay.read_bytes()
        second = exporter.upload_export(
            self.output,
            execute=True,
            root=self.root,
            yc_profile="test-profile",
            overlay_path=overlay,
            runner=runner,
            yastatic_verifier=yastatic,
        )
        self.assertEqual(second["counts"]["skipped"], 45)
        self.assertEqual(overlay.read_bytes(), before)
        self.assertFalse(any("put-object" in command for command in commands))

    def test_missing_object_is_uploaded_once_then_verified(self) -> None:
        first_key = self.manifest["outputs"][0]["object_key"]
        head_counts: dict[str, int] = {}
        puts: list[str] = []

        def runner(command: list[str], **_kwargs: object):
            if "list-objects-v2" in command:
                return self._completed()
            key = command[command.index("--key") + 1]
            if "put-object" in command:
                puts.append(key)
                return self._completed('{"etag":"ok"}')
            head_counts[key] = head_counts.get(key, 0) + 1
            if key == first_key and head_counts[key] == 1:
                return self._completed(
                    stderr="NoSuchKey status code: 404", returncode=1
                )
            return self._completed(self._head_payload(self.by_key[key]))

        overlay = Path(self.temporary.name) / "one-upload-overlay.json"
        report = exporter.upload_export(
            self.output,
            execute=True,
            root=self.root,
            yc_profile="test-profile",
            overlay_path=overlay,
            runner=runner,
            yastatic_verifier=lambda _row: {"verified": True},
        )
        self.assertEqual(puts, [first_key])
        self.assertEqual(report["counts"]["uploaded"], 1)
        self.assertEqual(report["counts"]["skipped"], 44)
        self.assertEqual(report["counts"]["verified"], 45)
        self.assertTrue(overlay.exists())

    def test_conflict_and_provider_error_fail_without_overlay_or_secret(
        self,
    ) -> None:
        first = self.manifest["outputs"][0]
        puts: list[list[str]] = []

        def conflict_runner(command: list[str], **_kwargs: object):
            if "list-objects-v2" in command:
                return self._completed()
            if "put-object" in command:
                puts.append(command)
                return self._completed()
            return self._completed(self._head_payload(
                first, sha256="0" * 64
            ))

        conflict_overlay = (
            Path(self.temporary.name) / "conflict-overlay.json"
        )
        with self.assertRaisesRegex(
            exporter.ExportError, "refusing overwrite"
        ):
            exporter.upload_export(
                self.output,
                execute=True,
                root=self.root,
                yc_profile="test-profile",
                overlay_path=conflict_overlay,
                runner=conflict_runner,
                yastatic_verifier=lambda _row: {"verified": True},
            )
        self.assertEqual(puts, [])
        self.assertFalse(conflict_overlay.exists())

        secret = "very-private-token-value"
        yandex_secrets = (
            "y0_abcdefgh12345678",
            "t1_abcdefgh12345678",
            "AQAD-abcdefgh12345678",
        )

        def error_runner(command: list[str], **_kwargs: object):
            if "list-objects-v2" in command:
                return self._completed()
            return self._completed(
                stderr=(
                    f"Authorization: Bearer {secret} token={secret} "
                    + " ".join(yandex_secrets)
                ),
                returncode=1,
            )

        error_overlay = Path(self.temporary.name) / "error-overlay.json"
        with self.assertRaises(exporter.ExportError) as caught:
            exporter.upload_export(
                self.output,
                execute=True,
                root=self.root,
                yc_profile="test-profile",
                overlay_path=error_overlay,
                runner=error_runner,
                yastatic_verifier=lambda _row: {"verified": True},
            )
        self.assertNotIn(secret, str(caught.exception))
        for value in yandex_secrets:
            self.assertNotIn(value, str(caught.exception))
        report_text = (self.output / "upload-report.json").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(secret, report_text)
        for value in yandex_secrets:
            self.assertNotIn(value, report_text)
        self.assertIn("[REDACTED]", report_text)
        self.assertIn("[REDACTED_YANDEX_TOKEN]", report_text)
        self.assertFalse(error_overlay.exists())

        raised_secret = "AQAD-preflightSecret12345"

        def raises_oserror(
            _command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            raise OSError(f"credential={raised_secret}")

        with self.assertRaises(exporter.ExportError) as preflight_error:
            exporter._run_yc_safe(["yc"], raises_oserror)
        self.assertNotIn(raised_secret, str(preflight_error.exception))


if __name__ == "__main__":
    unittest.main()
