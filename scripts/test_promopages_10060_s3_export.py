#!/usr/bin/env python3
"""Network-free tests for the PROMOPAGES-10060 S3 export package."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import promopages_10060_s3_export as exporter


MODEL_DIRS = {
    "alibaba/wan-2.2": "wan_2_2",
    "alibaba/wan-2.7": "wan_2_7",
    "google/veo-3.1-lite": "veo_3_1",
}


class Promopages10060S3ExportTest(unittest.TestCase):
    """Exercise package construction without touching S3 or the real videos."""

    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def make_fixture(self, directory: str) -> tuple[Path, Path, list[Path], Path]:
        root = Path(directory) / "workspace"
        root.mkdir(parents=True)
        cabinet_id = "a" * 24
        publication_id = "b" * 24
        campaign_id = "c" * 24
        article_slug = "01-fixture-article"
        article_url = f"https://example.test/article-{publication_id}_0_0"
        article_config = {
            "schema_version": 1,
            "ticket": "PROMOPAGES-10060",
            "articles": [
                {
                    "article_number": "01",
                    "article_slug": article_slug,
                    "label": "Fixture cabinet — Fixture article",
                    "url": article_url,
                    "cabinet": {
                        "name": "Fixture cabinet",
                        "slug": "fixture-cabinet",
                        "id": cabinet_id,
                    },
                    "campaign_ids": [campaign_id],
                    "publication_id": publication_id,
                    "source_status": "available",
                    "expected_image_count": 1,
                    "expected_ready_output_count": 3,
                }
            ],
        }
        articles_path = root / "articles.json"
        self.write_json(articles_path, article_config)

        outputs = []
        for index, model_id in enumerate(MODEL_DIRS, start=1):
            video_bytes = f"fixture-mp4-{index}-{model_id}".encode("utf-8")
            video_path = root / "generated" / f"model-{index}.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(video_bytes)
            outputs.append(
                {
                    "article_slug": article_slug,
                    "image_id": "01",
                    "model_id": model_id,
                    "status": (
                        "verification-failed"
                        if model_id == "alibaba/wan-2.7"
                        else "succeeded"
                    ),
                    "recorded_status": "succeeded",
                    "selected_attempt": "primary",
                    "provider_run_id": f"fixture-provider-{index}",
                    "video_path": video_path.relative_to(root).as_posix(),
                    "media": {
                        "bytes": len(video_bytes),
                        "sha256": hashlib.sha256(video_bytes).hexdigest(),
                        "codec": "h264",
                        "duration_seconds": 5.0,
                        "width": 1280,
                        "height": 720,
                    },
                    "contract_check": {
                        "conforms": model_id != "alibaba/wan-2.7",
                        "warnings": (
                            ["fixture verification warning"]
                            if model_id == "alibaba/wan-2.7"
                            else []
                        ),
                    },
                    "error": None,
                }
            )

        source_manifest = {
            "schema_version": 1,
            "manifest_role": "fixture-final-manifest",
            "ticket": "PROMOPAGES-10060",
            "agent_id": "clipmaker-lite",
            "article_count": 1,
            "image_count": 1,
            "expected_outputs": 3,
            "merge_contract": exporter.MERGE_CONTRACT,
            "unavailable_articles": [],
            "articles": [
                {
                    "article_number": "01",
                    "article_slug": article_slug,
                    "label": "Fixture cabinet — Fixture article",
                    "title": "Fixture article",
                    "url": article_url,
                    "image_count": 1,
                    "images": [
                        {
                            "image": {"image_id": "01"},
                            "lite_planning": {
                                "provenance": {
                                    "verified": True,
                                    "agent_id": "clipmaker-lite",
                                    "models": list(exporter.LITE_MODELS),
                                }
                            },
                            "outputs": outputs,
                        }
                    ],
                }
            ],
            "outputs": outputs,
        }
        manifest_path = root / "source-manifest.json"
        self.write_json(manifest_path, source_manifest)
        return root, articles_path, [manifest_path], root / "export"

    def make_article02_supersession_fixture(
        self, directory: str
    ) -> tuple[Path, Path, list[Path], Path]:
        root, articles_path, manifest_paths, output_dir = self.make_fixture(directory)
        article_slug = "02-level-rabotaiu-v-level"

        config = json.loads(articles_path.read_text(encoding="utf-8"))
        mapping = config["articles"][0]
        mapping["article_number"] = "02"
        mapping["article_slug"] = article_slug
        self.write_json(articles_path, config)

        replacement = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
        replacement["batch_id"] = "promopages-10060-article-02-20260806-v2"
        replacement["manifest_role"] = "promopages-10060-article-02"
        replacement_article = replacement["articles"][0]
        replacement_article["article_number"] = "02"
        replacement_article["article_slug"] = article_slug
        replacement_article["url"] = mapping["url"]
        for output in replacement_article["images"][0]["outputs"]:
            output["article_slug"] = article_slug
        for output in replacement["outputs"]:
            output["article_slug"] = article_slug

        replacement_path = root / "article-02-v2-manifest.json"
        self.write_json(replacement_path, replacement)
        legacy = {
            "schema_version": 1,
            "manifest_role": "fixture-legacy-manifest",
            "ticket": "PROMOPAGES-10060",
            "agent_id": "clipmaker-lite",
            "batch_id": "promopages-10060-lite-all-images-20260805-v2",
            "merge_contract": exporter.MERGE_CONTRACT,
            "articles": [],
            "outputs": [],
            "unavailable_articles": [
                {
                    "article_number": "02",
                    "article_slug": article_slug,
                    "url": "https://example.test/legacy-404",
                    "status": "source-unavailable",
                    "image_count": None,
                    "error": "Fixture legacy URL returned HTTP 404",
                }
            ],
        }
        legacy_path = root / "legacy-manifest.json"
        legacy["manifest_role"] = "promopages-10060-all-images"
        self.write_json(legacy_path, legacy)
        return root, articles_path, [legacy_path, replacement_path], output_dir

    def build_fixture(
        self,
        directory: str,
    ) -> tuple[Path, Path, list[Path], Path, dict]:
        root, articles_path, manifest_paths, output_dir = self.make_fixture(directory)
        manifest = exporter.build_export(
            root,
            articles_path,
            manifest_paths,
            output_dir,
            materialize_mode="copy",
        )
        return root, articles_path, manifest_paths, output_dir, manifest

    def test_model_directory_map_is_locked(self) -> None:
        self.assertEqual(exporter.MODEL_DIRS, MODEL_DIRS)

    def test_default_manifests_include_article02_v2_sidecar(self) -> None:
        self.assertEqual(
            [path.name for path in exporter.DEFAULT_MANIFEST_PATHS],
            [
                "promopages-10060-manifest.json",
                "promopages-10060-campaigns-20260805-v1-manifest.json",
                "promopages-10060-article-02-20260806-v2-manifest.json",
            ],
        )

    def test_build_and_verify_small_fixture_use_deterministic_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, _articles_path, _manifest_paths, output_dir, manifest = (
                self.build_fixture(directory)
            )

            cabinet = f"fixture-cabinet__{'a' * 24}"
            publication = "b" * 24
            rows = [row for row in manifest["outputs"] if row["package_status"] == "ready"]
            self.assertEqual(len(rows), 3)
            self.assertEqual(
                {row["experiment"] for row in rows},
                set(MODEL_DIRS.values()),
            )
            self.assertEqual(
                {row["relative_path"] for row in rows},
                {
                    (
                        f"{cabinet}/{publication}/{MODEL_DIRS[row['model_id']]}/"
                        f"image_01--sha256-{row['media']['sha256'][:12]}.mp4"
                    )
                    for row in rows
                },
            )
            for row in rows:
                payload_path = output_dir / "upload" / row["relative_path"]
                self.assertTrue(payload_path.is_file())
                self.assertFalse(payload_path.is_symlink())
                self.assertEqual(
                    row["object_key"],
                    f"front-images/exp_video/{row['relative_path']}",
                )
                self.assertEqual(
                    row["yastatic_url"],
                    (
                        "https://yastatic.net/s3/promopages-front-bundles/"
                        f"{row['object_key']}"
                    ),
                )

            verified = exporter.verify_export(output_dir)
            self.assertEqual(verified["ready_outputs"], 3)
            self.assertEqual(verified["bytes"], manifest["counts"]["bytes"])

            links_path = output_dir / "links.csv"
            with links_path.open(encoding="utf-8", newline="") as stream:
                links = list(csv.DictReader(stream))
            self.assertEqual(len(links), 3)
            self.assertEqual(
                [row["object_key"] for row in links],
                [row["object_key"] for row in rows],
            )
            self.assertTrue((output_dir / "SHA256SUMS").is_file())

    def test_build_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = self.make_fixture(directory)
            first = exporter.build_export(
                root,
                articles_path,
                manifest_paths,
                output_dir,
                materialize_mode="copy",
            )
            first_links = (output_dir / "links.csv").read_bytes()
            first_sums = (output_dir / "SHA256SUMS").read_bytes()
            second = exporter.build_export(
                root,
                articles_path,
                manifest_paths,
                output_dir,
                materialize_mode="copy",
            )
            self.assertEqual(first, second)
            self.assertEqual(first_links, (output_dir / "links.csv").read_bytes())
            self.assertEqual(first_sums, (output_dir / "SHA256SUMS").read_bytes())

    def test_build_allows_exact_article02_v2_supersession(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = (
                self.make_article02_supersession_fixture(directory)
            )
            manifest = exporter.build_export(
                root,
                articles_path,
                manifest_paths,
                output_dir,
                materialize_mode="copy",
            )
            self.assertEqual(manifest["counts"]["articles_with_video"], 1)
            self.assertEqual(manifest["counts"]["source_unavailable_articles"], 0)
            self.assertEqual(manifest["unavailable_articles"], [])
            self.assertEqual(
                {row["article_slug"] for row in manifest["outputs"]},
                {"02-level-rabotaiu-v-level"},
            )

    def test_build_rejects_untrusted_article02_replacement(self) -> None:
        mutations = {
            "role": lambda manifest: manifest.update(
                {"manifest_role": "fixture-final-manifest"}
            ),
            "provenance": lambda manifest: manifest["articles"][0]["images"][0][
                "lite_planning"
            ]["provenance"].update({"verified": False}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root, articles_path, manifest_paths, output_dir = (
                    self.make_article02_supersession_fixture(directory)
                )
                replacement = json.loads(manifest_paths[1].read_text(encoding="utf-8"))
                mutate(replacement)
                self.write_json(manifest_paths[1], replacement)
                with self.assertRaises(exporter.ExportError):
                    exporter.build_export(
                        root,
                        articles_path,
                        manifest_paths,
                        output_dir,
                        materialize_mode="copy",
                    )

    def test_build_rejects_any_other_available_unavailable_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = (
                self.make_article02_supersession_fixture(directory)
            )
            legacy = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            legacy["batch_id"] = "unexpected-legacy-batch"
            self.write_json(manifest_paths[0], legacy)
            with self.assertRaisesRegex(
                exporter.ExportError,
                "conflicting available and unavailable source records",
            ):
                exporter.build_export(
                    root,
                    articles_path,
                    manifest_paths,
                    output_dir,
                    materialize_mode="copy",
                )

    def test_build_rejects_duplicate_unavailable_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = (
                self.make_article02_supersession_fixture(directory)
            )
            duplicate_path = root / "duplicate-legacy-manifest.json"
            duplicate = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            duplicate["batch_id"] = "another-legacy-batch"
            self.write_json(duplicate_path, duplicate)
            with self.assertRaisesRegex(
                exporter.ExportError,
                "Unavailable article occurs in more than one source manifest",
            ):
                exporter.build_export(
                    root,
                    articles_path,
                    [*manifest_paths, duplicate_path],
                    output_dir,
                    materialize_mode="copy",
                )

    def test_build_rejects_source_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = self.make_fixture(directory)
            manifest = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            for output in manifest["articles"][0]["images"][0]["outputs"]:
                output["video_path"] = "../escape.mp4"
            manifest["outputs"] = manifest["articles"][0]["images"][0]["outputs"]
            self.write_json(manifest_paths[0], manifest)
            with self.assertRaises(exporter.ExportError):
                exporter.build_export(
                    root,
                    articles_path,
                    manifest_paths,
                    output_dir,
                    materialize_mode="copy",
                )

    def test_build_rejects_symlinked_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = self.make_fixture(directory)
            manifest = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            output = manifest["articles"][0]["images"][0]["outputs"][0]
            source = root / output["video_path"]
            target = source.with_name("real-source.mp4")
            source.rename(target)
            source.symlink_to(target.name)
            with self.assertRaises(exporter.ExportError):
                exporter.build_export(
                    root,
                    articles_path,
                    manifest_paths,
                    output_dir,
                    materialize_mode="copy",
                )

    def test_build_rejects_source_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, articles_path, manifest_paths, output_dir = self.make_fixture(directory)
            manifest = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            output = manifest["articles"][0]["images"][0]["outputs"][0]
            output["media"]["sha256"] = "0" * 64
            manifest["outputs"][0]["media"]["sha256"] = "0" * 64
            self.write_json(manifest_paths[0], manifest)
            with self.assertRaises(exporter.ExportError):
                exporter.build_export(
                    root,
                    articles_path,
                    manifest_paths,
                    output_dir,
                    materialize_mode="copy",
                )

    def test_verify_rejects_payload_hash_mismatch_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, _articles_path, _manifest_paths, output_dir, manifest = (
                self.build_fixture(directory)
            )
            row = next(row for row in manifest["outputs"] if row["package_status"] == "ready")
            payload = output_dir / "upload" / row["relative_path"]
            original = payload.read_bytes()
            payload.write_bytes(original + b"corrupt")
            with self.assertRaises(exporter.ExportError):
                exporter.verify_export(output_dir)

            payload.unlink()
            source = root / row["source_video_path"]
            payload.symlink_to(source)
            with self.assertRaises(exporter.ExportError):
                exporter.verify_export(output_dir)

    def test_default_upload_is_yc_dry_run_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, _articles_path, _manifest_paths, output_dir, _manifest = (
                self.build_fixture(directory)
            )
            calls: list[list[str]] = []

            def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
                tokens = [str(token) for token in command]
                calls.append(tokens)
                return subprocess.CompletedProcess(tokens, 0, stdout="", stderr="")

            before = {
                path.relative_to(output_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in output_dir.rglob("*")
                if path.is_file()
            }
            result = exporter.upload_export(
                output_dir,
                execute=False,
                yc_profile="fixture-internal",
                runner=fake_runner,
            )
            after = {
                path.relative_to(output_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in output_dir.rglob("*")
                if path.is_file()
            }
            self.assertEqual(calls, [])
            self.assertEqual(result["mode"], "dry-run")
            self.assertEqual(result["external_writes"], 0)
            self.assertEqual(result["operation_count"], 3)
            self.assertEqual(before, after)

    def test_execute_uploads_missing_objects_and_writes_verified_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, _articles_path, _manifest_paths, output_dir, manifest = (
                self.build_fixture(directory)
            )
            ready = {
                row["object_key"]: row
                for row in manifest["outputs"]
                if row["package_status"] == "ready"
            }
            head_calls = {key: 0 for key in ready}
            put_commands: list[list[str]] = []

            def argument(tokens: list[str], name: str) -> str:
                return tokens[tokens.index(name) + 1]

            def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
                tokens = [str(token) for token in command]
                self.assertEqual(argument(tokens, "--profile"), "fixture-internal")
                if "list-objects-v2" in tokens:
                    return subprocess.CompletedProcess(
                        tokens,
                        0,
                        stdout="{}",
                        stderr="",
                    )
                key = argument(tokens, "--key")
                row = ready[key]
                if "head-object" in tokens:
                    head_calls[key] += 1
                    if head_calls[key] == 1:
                        return subprocess.CompletedProcess(
                            tokens,
                            1,
                            stdout="",
                            stderr="NoSuchKey: fixture object is absent",
                        )
                    head = {
                        "ContentLength": row["media"]["bytes"],
                        "ContentType": "video/mp4",
                        "CacheControl": "public,max-age=31536000,immutable",
                        "ContentDisposition": "inline",
                        "Metadata": {
                            "sha256": row["media"]["sha256"],
                            "publication-id": row["publication_id"],
                            "image-id": row["image_id"],
                            "experiment": row["experiment"],
                        },
                        "ETag": '"fixture-etag"',
                    }
                    return subprocess.CompletedProcess(
                        tokens,
                        0,
                        stdout=json.dumps(head),
                        stderr="",
                    )
                if "put-object" in tokens:
                    put_commands.append(tokens)
                    self.assertEqual(argument(tokens, "--content-type"), "video/mp4")
                    self.assertEqual(
                        argument(tokens, "--cache-control"),
                        "public,max-age=31536000,immutable",
                    )
                    self.assertEqual(
                        argument(tokens, "--content-md5"),
                        row["media"]["md5_base64"],
                    )
                    metadata = dict(
                        field.split("=", 1)
                        for field in argument(tokens, "--metadata").split(",")
                    )
                    self.assertEqual(metadata["sha256"], row["media"]["sha256"])
                    self.assertEqual(metadata["publication-id"], row["publication_id"])
                    self.assertEqual(metadata["image-id"], row["image_id"])
                    self.assertEqual(metadata["experiment"], row["experiment"])
                    body = Path(argument(tokens, "--body"))
                    self.assertTrue(body.is_file())
                    self.assertFalse(body.is_symlink())
                    return subprocess.CompletedProcess(
                        tokens,
                        0,
                        stdout=json.dumps({"ETag": "fixture-put-etag"}),
                        stderr="",
                    )
                self.fail(f"Unexpected yc command: {tokens}")

            yastatic_result = {
                "verified": True,
                "head_status": 200,
                "range_status": 206,
                "content_type": "video/mp4",
                "content_length": None,
            }
            with mock.patch.object(
                exporter,
                "_verify_yastatic",
                return_value=yastatic_result,
            ) as verify_yastatic:
                report = exporter.upload_export(
                    output_dir,
                    execute=True,
                    yc_profile="fixture-internal",
                    runner=fake_runner,
                )

            self.assertEqual(len(put_commands), 3)
            self.assertTrue(all(count == 2 for count in head_calls.values()))
            self.assertEqual(verify_yastatic.call_count, 3)
            self.assertEqual(
                {call.args[0]["object_key"] for call in verify_yastatic.call_args_list},
                set(ready),
            )
            self.assertEqual(
                report["counts"],
                {"total": 3, "uploaded": 3, "skipped": 0, "verified": 3},
            )
            self.assertIsNotNone(report["completed_at"])
            self.assertEqual(
                {row["action"] for row in report["objects"]},
                {"uploaded"},
            )
            on_disk = json.loads(
                (output_dir / "upload-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(on_disk, report)
            self.assertEqual(
                (output_dir / "verified-links.csv").read_text(encoding="utf-8"),
                (output_dir / "links.csv").read_text(encoding="utf-8"),
            )

    def test_execute_refuses_existing_object_with_wrong_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, _articles_path, _manifest_paths, output_dir, manifest = (
                self.build_fixture(directory)
            )
            first = next(
                row for row in manifest["outputs"] if row["package_status"] == "ready"
            )
            commands: list[list[str]] = []

            def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
                tokens = [str(token) for token in command]
                commands.append(tokens)
                if "list-objects-v2" in tokens:
                    return subprocess.CompletedProcess(tokens, 0, stdout="{}", stderr="")
                if "head-object" in tokens:
                    key = tokens[tokens.index("--key") + 1]
                    self.assertEqual(key, first["object_key"])
                    conflict = {
                        "ContentLength": first["media"]["bytes"],
                        "Metadata": {"sha256": "0" * 64},
                        "ETag": '"wrong-etag"',
                    }
                    return subprocess.CompletedProcess(
                        tokens,
                        0,
                        stdout=json.dumps(conflict),
                        stderr="",
                    )
                self.fail(f"Uploader must not mutate a conflicting object: {tokens}")

            with (
                mock.patch.object(exporter, "_verify_yastatic") as verify_yastatic,
                self.assertRaisesRegex(
                    exporter.ExportError,
                    "Immutable object key conflict",
                ),
            ):
                exporter.upload_export(
                    output_dir,
                    execute=True,
                    yc_profile="fixture-internal",
                    runner=fake_runner,
                )

            self.assertFalse(any("put-object" in command for command in commands))
            verify_yastatic.assert_not_called()
            partial_report = json.loads(
                (output_dir / "upload-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                partial_report["counts"],
                {"total": 3, "uploaded": 0, "skipped": 0, "verified": 0},
            )
            self.assertEqual(len(partial_report["objects"]), 1)
            conflict_entry = partial_report["objects"][0]
            self.assertEqual(conflict_entry["object_key"], first["object_key"])
            self.assertEqual(conflict_entry["action"], "conflict")
            self.assertEqual(conflict_entry["status"], "conflict")
            self.assertIn("Immutable object key conflict", conflict_entry["error"])
            self.assertIsNone(partial_report["completed_at"])
            self.assertFalse((output_dir / "verified-links.csv").exists())

    def test_execute_persists_uploaded_action_when_yastatic_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _root, _articles_path, _manifest_paths, output_dir, manifest = (
                self.build_fixture(directory)
            )
            first = next(
                row for row in manifest["outputs"] if row["package_status"] == "ready"
            )
            head_count = 0
            put_count = 0

            def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
                nonlocal head_count, put_count
                tokens = [str(token) for token in command]
                if "list-objects-v2" in tokens:
                    return subprocess.CompletedProcess(tokens, 0, stdout="{}", stderr="")
                key = tokens[tokens.index("--key") + 1]
                self.assertEqual(key, first["object_key"])
                if "head-object" in tokens:
                    head_count += 1
                    if head_count == 1:
                        return subprocess.CompletedProcess(
                            tokens,
                            1,
                            stdout="",
                            stderr="NoSuchKey: fixture object is absent",
                        )
                    matching = {
                        "ContentLength": first["media"]["bytes"],
                        "ContentType": "video/mp4",
                        "CacheControl": "public,max-age=31536000,immutable",
                        "ContentDisposition": "inline",
                        "Metadata": {
                            "sha256": first["media"]["sha256"],
                            "publication-id": first["publication_id"],
                            "image-id": first["image_id"],
                            "experiment": first["experiment"],
                        },
                    }
                    return subprocess.CompletedProcess(
                        tokens,
                        0,
                        stdout=json.dumps(matching),
                        stderr="",
                    )
                if "put-object" in tokens:
                    put_count += 1
                    return subprocess.CompletedProcess(
                        tokens,
                        0,
                        stdout=json.dumps({"ETag": "fixture-put-etag"}),
                        stderr="",
                    )
                self.fail(f"Unexpected yc command: {tokens}")

            with (
                mock.patch.object(
                    exporter,
                    "_verify_yastatic",
                    side_effect=exporter.ExportError("fixture CDN unavailable"),
                ) as verify_yastatic,
                self.assertRaisesRegex(exporter.ExportError, "fixture CDN unavailable"),
            ):
                exporter.upload_export(
                    output_dir,
                    execute=True,
                    yc_profile="fixture-internal",
                    runner=fake_runner,
                )

            self.assertEqual(head_count, 2)
            self.assertEqual(put_count, 1)
            verify_yastatic.assert_called_once()
            partial_report = json.loads(
                (output_dir / "upload-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                partial_report["counts"],
                {"total": 3, "uploaded": 1, "skipped": 0, "verified": 0},
            )
            self.assertEqual(len(partial_report["objects"]), 1)
            entry = partial_report["objects"][0]
            self.assertEqual(entry["object_key"], first["object_key"])
            self.assertEqual(entry["action"], "uploaded")
            self.assertEqual(entry["status"], "yastatic-verification-failed")
            self.assertIn("fixture CDN unavailable", entry["error"])
            self.assertIsNotNone(entry["put_result"])
            self.assertIsNotNone(entry["s3_head"])
            self.assertIsNone(entry["yastatic"])
            self.assertIsNone(partial_report["completed_at"])
            self.assertFalse((output_dir / "verified-links.csv").exists())


if __name__ == "__main__":
    unittest.main()
