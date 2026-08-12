from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from scripts import build_github_pages_site as pages
from scripts import clipmaker_lite_tune_media_overlay as overlay
from scripts import video_generation_pipeline as transport


class OverlayFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tune = copy.deepcopy(
            overlay.read_json(overlay.ROOT / overlay.TUNE_MANIFEST_REL)
        )
        self.plan = copy.deepcopy(
            overlay.read_json(overlay.ROOT / overlay.COMPOSITOR_PLAN_REL)
        )
        self.fallback_plan = copy.deepcopy(
            overlay.read_json(overlay.ROOT / overlay.FALLBACK_PLAN_REL)
        )
        transport.atomic_write_json(root / overlay.TUNE_MANIFEST_REL, self.tune)
        transport.atomic_write_json(root / overlay.COMPOSITOR_PLAN_REL, self.plan)
        for script in (
            Path("scripts/clipmaker_lite_tune_compositor.py"),
            Path("scripts/clipmaker_lite_tune_compositor_fallback.py"),
        ):
            (root / script).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(overlay.ROOT / script, root / script)
        self.provider_failures: dict[tuple[str, str], dict[str, object]] = {}
        self.i2v = self._i2v_manifest()
        transport.atomic_write_json(root / overlay.I2V_MANIFEST_REL, self.i2v)
        self.fallback_plan["provider_generation"]["sha256"] = overlay.sha256_file(
            root / overlay.I2V_MANIFEST_REL
        )
        for row in self.fallback_plan["targets"]:
            row["provider_failure"] = copy.deepcopy(
                self.provider_failures[(row["case_id"], row["model_id"])]
            )
        transport.atomic_write_json(
            root / overlay.FALLBACK_PLAN_REL,
            self.fallback_plan,
        )
        self.compositor = self._compositor_manifest()
        self.fallback = self._fallback_manifest()
        transport.atomic_write_json(
            root / overlay.COMPOSITOR_MANIFEST_REL,
            self.compositor,
        )
        transport.atomic_write_json(
            root / overlay.FALLBACK_MANIFEST_REL,
            self.fallback,
        )

    def flat_targets(self):
        for case in self.tune["cases"]:
            for target in case["targets"]:
                yield case, target

    def _write_video(self, path: str, payload: bytes) -> dict[str, object]:
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return {
            "bytes": len(payload),
            "sha256": overlay.sha256_file(destination),
        }

    def _i2v_manifest(self) -> dict[str, object]:
        outputs = []
        exclusions = []
        statuses: Counter[str] = Counter()
        failure_written = False
        for case, target in self.flat_targets():
            mode = target["tuned"]["execution_mode"]
            key = f"{case['case_id']}-{target['model_id'].replace('/', '-')}"
            if mode != "i2v":
                exclusions.append(
                    {
                        "case_id": case["case_id"],
                        "sheet_row": target["sheet_row"],
                        "article_slug": case["article_slug"],
                        "image_id": case["source"]["image_id"],
                        "model_id": target["model_id"],
                        "planning_run_id": case["planning"]["run_id"],
                        "execution_mode": "deterministic-compositor",
                        "status": "abstained",
                        "provider_artifact": None,
                    }
                )
                continue
            path = (
                f"clipmaker-lite-test/runs/{overlay.I2V_BATCH_ID}/videos/"
                f"{case['article_slug']}/{target['model_id'].split('/')[-1]}/"
                f"{case['source']['image_id']}.mp4"
            )
            target_key = (case["case_id"], target["model_id"])
            if target_key in overlay.EXPECTED_FALLBACK_KEYS:
                prompt_path = path.removesuffix(".mp4") + ".prompt.json"
                run_path = path.removesuffix(".mp4") + ".run.json"
                provider_run_id = f"{overlay.I2V_BATCH_ID}-{key}"
                provider_job_id = f"failed-job-{case['case_id'].replace('#', '-')}"
                error = f"terminal provider failure for {case['case_id']}"
                prompt = {
                    "schema_version": 1,
                    "manifest_role": "clipmaker-lite-tune-video-prompt",
                    "ticket": overlay.TICKET,
                    "batch_id": overlay.I2V_BATCH_ID,
                    "agent_id": overlay.AGENT_ID,
                    "provider_run_id": provider_run_id,
                    "case_id": case["case_id"],
                    "sheet_row": target["sheet_row"],
                    "model_id": target["model_id"],
                    "execution_mode": "i2v",
                    "prompt": {
                        "positive": target["tuned"]["positive_prompt"],
                        "negative": target["tuned"]["negative_prompt"],
                        "rewritten": False,
                    },
                }
                transport.atomic_write_json(self.root / prompt_path, prompt)
                run = {
                    "schema_version": 1,
                    "manifest_role": "clipmaker-lite-tune-video-run",
                    "ticket": overlay.TICKET,
                    "batch_id": overlay.I2V_BATCH_ID,
                    "agent_id": overlay.AGENT_ID,
                    "provider_run_id": provider_run_id,
                    "case_id": case["case_id"],
                    "model_id": target["model_id"],
                    "execution_mode": "i2v",
                    "status": "provider-failed",
                    "prompt_path": prompt_path,
                    "output_path": path,
                    "request": {
                        "model": target["model_id"],
                        "duration": target["tuned"]["runtime"]["duration_seconds"],
                        "generate_audio": False,
                    },
                    "provider_job_id": provider_job_id,
                    "completed_at": "2026-08-11T00:00:00Z",
                    "provider_may_be_active": False,
                    "media": None,
                    "contract_check": None,
                    "error": error,
                    "automatic_paid_retry": False,
                }
                transport.atomic_write_json(self.root / run_path, run)
                provider_failure = {
                    "provider_run_id": provider_run_id,
                    "run_path": run_path,
                    "run_sha256": overlay.sha256_file(self.root / run_path),
                    "prompt_path": prompt_path,
                    "prompt_sha256": overlay.sha256_file(self.root / prompt_path),
                    "status": "provider-failed",
                    "provider_job_id": provider_job_id,
                    "terminal_error": error,
                }
                self.provider_failures[target_key] = provider_failure
                statuses["provider-failed"] += 1
                outputs.append(
                    {
                        "provider_run_id": provider_run_id,
                        "case_id": case["case_id"],
                        "sheet_row": target["sheet_row"],
                        "article_slug": case["article_slug"],
                        "image_id": case["source"]["image_id"],
                        "model_id": target["model_id"],
                        "execution_mode": "i2v",
                        "status": "provider-failed",
                        "prompt_path": prompt_path,
                        "run_path": run_path,
                        "video_path": path,
                        "media": None,
                        "contract_check": None,
                        "error": error,
                    }
                )
                continue
            file_binding = self._write_video(path, f"i2v-{key}".encode())
            is_warning = target["model_id"] == "alibaba/wan-2.7" and not failure_written
            failure_written = failure_written or is_warning
            status = "verification-failed" if is_warning else "succeeded"
            statuses[status] += 1
            checks = {"duration": True, "audio": not is_warning}
            warnings = (
                ["provider returned has_audio=True despite generate_audio=False"]
                if is_warning
                else []
            )
            duration = target["tuned"]["runtime"]["duration_seconds"]
            media = {
                "container": "mov,mp4,m4a,3gp,3g2,mj2",
                "codec": "h264",
                "duration_seconds": float(duration),
                "width": 1280,
                "height": 720,
                "fps": 24.0,
                "frames": int(duration * 24),
                "has_audio": is_warning,
                **file_binding,
            }
            outputs.append(
                {
                    "provider_run_id": f"{overlay.I2V_BATCH_ID}-{key}",
                    "case_id": case["case_id"],
                    "sheet_row": target["sheet_row"],
                    "article_slug": case["article_slug"],
                    "image_id": case["source"]["image_id"],
                    "model_id": target["model_id"],
                    "execution_mode": "i2v",
                    "status": status,
                    "prompt_path": f"receipts/{key}.prompt.json",
                    "run_path": f"receipts/{key}.run.json",
                    "video_path": path,
                    "media": media,
                    "contract_check": {
                        "requested": {
                            "duration_seconds": duration,
                            "generate_audio": False,
                        },
                        "checks": checks,
                        "conforms": not is_warning,
                        "warnings": warnings,
                    },
                    "error": warnings[0] if warnings else None,
                }
            )
        tune_sha = overlay.sha256_file(self.root / overlay.TUNE_MANIFEST_REL)
        return {
            "schema_version": 1,
            "manifest_role": "clipmaker-lite-tune-video-generation",
            "ticket": overlay.TICKET,
            "batch_id": overlay.I2V_BATCH_ID,
            "agent_id": overlay.AGENT_ID,
            "updated_at": "2026-08-11T00:00:00Z",
            "scope": {
                "planning_batch_id": overlay.PLANNING_BATCH_ID,
                "tune_manifest_path": overlay.TUNE_MANIFEST_REL.as_posix(),
                "tune_manifest_sha256": tune_sha,
                "expected_i2v_outputs": overlay.EXPECTED_I2V,
                "compositor_provider_outputs": 0,
                "s3_upload": False,
                "delivery": "repository-files",
            },
            "budget": {},
            "scheduling": {
                "independent_route_pools": True,
                "route_capacities": {
                    "alibaba/wan-2.2": 1,
                    "alibaba/wan-2.7": 3,
                    "google/veo-3.1-lite": 3,
                },
                "one_paid_submission_per_provider_run_id": True,
                "automatic_paid_retry": False,
            },
            "summary": dict(sorted(statuses.items())),
            "outputs": outputs,
            "compositor_exclusions": exclusions,
        }

    def _fallback_manifest(self) -> dict[str, object]:
        outputs = []
        for row in self.fallback_plan["targets"]:
            payload = f"fallback-{row['case_id']}-{row['model_id']}".encode()
            file_binding = self._write_video(row["output_path"], payload)
            media = {
                "width": 1620,
                "height": 1080,
                "duration_seconds": 4.0,
                "fps": 30,
                "frames": 120,
                "video_codec": "h264",
                "pixel_format": "yuv420p",
                "audio_streams": 0,
                **file_binding,
            }
            outputs.append(
                {
                    "case_id": row["case_id"],
                    "model_id": row["model_id"],
                    "execution_mode": "i2v",
                    "original_execution_mode": "i2v",
                    "method": "deterministic-compositor-fallback",
                    "status": "succeeded",
                    "fallback_reason": "terminal-provider-failure",
                    "provider_failure": copy.deepcopy(row["provider_failure"]),
                    "canonical_provider_video_path": next(
                        value["video_path"]
                        for value in self.i2v["outputs"]
                        if (value["case_id"], value["model_id"])
                        == (row["case_id"], row["model_id"])
                    ),
                    "source": {**row["source"], "mutated": False},
                    "planning": {
                        **row["planning"],
                        "scene_plan_sha256": row["scene_plan_sha256"],
                    },
                    "plan": copy.deepcopy(row["plan"]),
                    "video_path": row["output_path"],
                    "media": media,
                    "contract_check": {
                        key: True for key in overlay.COMPOSITOR_CHECKS
                    },
                }
            )
        return {
            "schema_version": 1,
            "manifest_role": "clipmaker-lite-tune-compositor-fallback-generation",
            "batch_id": overlay.FALLBACK_BATCH_ID,
            "agent_id": overlay.AGENT_ID,
            "method": "deterministic-compositor-fallback",
            "generated_at": "2026-08-11T00:00:00Z",
            "producer": {
                "script_path": "scripts/clipmaker_lite_tune_compositor_fallback.py",
                "script_sha256": overlay.sha256_file(
                    self.root / "scripts/clipmaker_lite_tune_compositor_fallback.py"
                ),
                "renderer_path": "scripts/clipmaker_lite_tune_compositor.py",
                "renderer_sha256": overlay.sha256_file(
                    self.root / "scripts/clipmaker_lite_tune_compositor.py"
                ),
            },
            "input_plan": {
                "path": overlay.FALLBACK_PLAN_REL.as_posix(),
                "sha256": overlay.sha256_file(
                    self.root / overlay.FALLBACK_PLAN_REL
                ),
            },
            "provider_generation": copy.deepcopy(
                self.fallback_plan["provider_generation"]
            ),
            "render_contract": copy.deepcopy(
                self.fallback_plan["render_contract"]
            ),
            "scope": {
                "targets": 2,
                "original_execution_mode": "i2v",
                "provider_calls": 0,
                "network": False,
                "s3_upload": False,
                "tune_manifest_mutation": False,
                "canonical_compositor_manifest_mutation": False,
            },
            "summary": {"succeeded": 2},
            "bytes_total": sum(row["media"]["bytes"] for row in outputs),
            "outputs": outputs,
        }

    def _compositor_manifest(self) -> dict[str, object]:
        outputs = []
        model_counts: Counter[str] = Counter()
        for row in self.plan["targets"]:
            payload = f"compositor-{row['case_id']}-{row['model_id']}".encode()
            file_binding = self._write_video(row["output_path"], payload)
            duration = row["duration_seconds"]
            media = {
                "width": row["source"]["width"],
                "height": row["source"]["height"],
                "duration_seconds": float(duration),
                "fps": 30,
                "frames": int(duration * 30),
                "video_codec": "h264",
                "pixel_format": "yuv420p",
                "audio_streams": 0,
                **file_binding,
            }
            checks = {key: True for key in overlay.COMPOSITOR_CHECKS}
            outputs.append(
                {
                    "case_id": row["case_id"],
                    "model_id": row["model_id"],
                    "execution_mode": "deterministic-compositor",
                    "status": "succeeded",
                    "source": {**row["source"], "mutated": False},
                    "planning": {
                        **row["planning"],
                        "scene_plan_sha256": row["scene_plan_sha256"],
                    },
                    "plan": row["plan"],
                    "video_path": row["output_path"],
                    "media": media,
                    "contract_check": checks,
                }
            )
            model_counts[row["model_id"]] += 1
        script_path = self.root / "scripts/clipmaker_lite_tune_compositor.py"
        plan_path = self.root / overlay.COMPOSITOR_PLAN_REL
        return {
            "schema_version": 1,
            "manifest_role": "clipmaker-lite-tune-compositor-generation",
            "batch_id": overlay.COMPOSITOR_BATCH_ID,
            "agent_id": overlay.AGENT_ID,
            "producer": {
                "script_path": "scripts/clipmaker_lite_tune_compositor.py",
                "script_sha256": overlay.sha256_file(script_path),
            },
            "generated_at": "2026-08-11T00:00:00Z",
            "input_plan": {
                "path": overlay.COMPOSITOR_PLAN_REL.as_posix(),
                "sha256": overlay.sha256_file(plan_path),
            },
            "render_contract": self.plan["render_contract"],
            "scope": {
                "targets": overlay.EXPECTED_COMPOSITOR,
                "provider_calls": 0,
                "network": False,
                "s3_upload": False,
                "tune_manifest_mutation": False,
            },
            "summary": {"succeeded": overlay.EXPECTED_COMPOSITOR},
            "model_summary": dict(sorted(model_counts.items())),
            "bytes_total": sum(row["media"]["bytes"] for row in outputs),
            "outputs": outputs,
        }

    def write_i2v(self) -> None:
        transport.atomic_write_json(self.root / overlay.I2V_MANIFEST_REL, self.i2v)

    def write_compositor(self) -> None:
        transport.atomic_write_json(
            self.root / overlay.COMPOSITOR_MANIFEST_REL,
            self.compositor,
        )

    def write_fallback(self) -> None:
        transport.atomic_write_json(
            self.root / overlay.FALLBACK_MANIFEST_REL,
            self.fallback,
        )


class ClipmakerLiteTuneMediaOverlayTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        return temporary, root, OverlayFixture(root)

    def test_builds_exact_41_plus_22_plus_2_repository_raw_overlay(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        commit_sha = "a" * 40
        document, existing = overlay.build_merged_manifest(commit_sha, root=root)
        self.assertIsNone(existing)
        videos = [
            target["tuned"]["video"]
            for case in document["cases"]
            for target in case["targets"]
        ]
        self.assertEqual(len(videos), 65)
        self.assertEqual(
            Counter(video["method"] for video in videos),
            Counter(
                {
                    "eliza-i2v": 41,
                    "deterministic-compositor": 22,
                    "deterministic-compositor-fallback": 2,
                }
            ),
        )
        self.assertTrue(
            all(video["delivery"] == "repository-raw" for video in videos)
        )
        self.assertTrue(all(f"/{commit_sha}/" in video["url"] for video in videos))
        self.assertEqual(document["scope"]["generated_video_count"], 65)
        self.assertFalse(document["scope"]["new_s3_upload"])
        warning = next(
            video for video in videos if video["status"] == "verification-failed"
        )
        self.assertTrue(warning["media"]["has_audio"])
        self.assertFalse(warning["contract_check"]["conforms"])
        fallbacks = [
            video
            for video in videos
            if video["method"] == "deterministic-compositor-fallback"
        ]
        self.assertEqual(len(fallbacks), 2)
        self.assertTrue(all(video["prompt_evaluated"] is False for video in fallbacks))
        self.assertTrue(
            all(
                video["provider_attempt"]["status"] == "provider-failed"
                and video["provider_attempt"]["prompt_evaluated"] is False
                for video in fallbacks
            )
        )
        # Keep the merge helper and the Pages no-copy review contract exact.
        pages._validate_tune_manifest_for_pages(document, root=root)  # noqa: SLF001

    def test_compositor_video_carries_primitive_and_plan_provenance(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        document, _ = overlay.build_merged_manifest("b" * 40, root=root)
        compositor = next(
            target["tuned"]["video"]
            for case in document["cases"]
            for target in case["targets"]
            if target["tuned"]["execution_mode"] == "deterministic-compositor"
        )
        self.assertEqual(compositor["method"], "deterministic-compositor")
        provenance = compositor["compositor"]
        self.assertIn(provenance["primitive"], overlay.ALLOWED_PRIMITIVES)
        self.assertEqual(provenance["primitive"], provenance["plan"]["primitive"])
        self.assertEqual(provenance["batch_id"], overlay.COMPOSITOR_BATCH_ID)
        self.assertRegex(provenance["manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(provenance["plan_sha256"], r"^[0-9a-f]{64}$")

    def test_fallback_keeps_i2v_mode_and_terminal_provider_audit(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        document, _ = overlay.build_merged_manifest("9" * 40, root=root)
        rows = [
            (case, target)
            for case in document["cases"]
            for target in case["targets"]
            if target["tuned"]["video"]["method"]
            == "deterministic-compositor-fallback"
        ]
        self.assertEqual(
            {(case["case_id"], target["model_id"]) for case, target in rows},
            overlay.EXPECTED_FALLBACK_KEYS,
        )
        for _, target in rows:
            tuned = target["tuned"]
            video = tuned["video"]
            self.assertEqual(tuned["execution_mode"], "i2v")
            self.assertFalse(video["prompt_evaluated"])
            self.assertEqual(
                video["compositor_fallback"]["primitive"],
                video["compositor_fallback"]["plan"]["primitive"],
            )
            self.assertFalse(video["provider_attempt"]["prompt_evaluated"])
            self.assertRegex(
                video["provider_attempt"]["run_sha256"], r"^[0-9a-f]{64}$"
            )

    def test_rejects_fallback_or_provider_failure_provenance_drift(self) -> None:
        for mutation in ("method", "provider-run", "plan"):
            with self.subTest(mutation=mutation):
                temporary, root, fixture = self.fixture()
                try:
                    if mutation == "method":
                        fixture.fallback["outputs"][0]["method"] = "eliza-i2v"
                        fixture.write_fallback()
                    elif mutation == "provider-run":
                        failure = next(
                            row
                            for row in fixture.i2v["outputs"]
                            if row["status"] == "provider-failed"
                        )
                        run = overlay.read_json(root / failure["run_path"])
                        run["provider_may_be_active"] = True
                        transport.atomic_write_json(root / failure["run_path"], run)
                    else:
                        fixture.fallback["outputs"][0]["plan"]["zoom_end"] = 1.2
                        fixture.write_fallback()
                    with self.assertRaises(overlay.TuneMediaOverlayError):
                        overlay.build_merged_manifest("8" * 40, root=root)
                finally:
                    temporary.cleanup()

    def test_atomic_merge_is_idempotent_for_same_sha_and_refuses_different_sha(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        commit_sha = "c" * 40
        first, wrote_first = overlay.merge_manifest(commit_sha, root=root)
        first_bytes = (root / overlay.TUNE_MANIFEST_REL).read_bytes()
        second, wrote_second = overlay.merge_manifest(commit_sha, root=root)
        self.assertTrue(wrote_first)
        self.assertFalse(wrote_second)
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, (root / overlay.TUNE_MANIFEST_REL).read_bytes())
        with self.assertRaisesRegex(
            overlay.TuneMediaOverlayError,
            "different media commit",
        ):
            overlay.merge_manifest("d" * 40, root=root)

    def test_same_sha_manifest_drift_fails_instead_of_overwriting(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        commit_sha = "e" * 40
        overlay.merge_manifest(commit_sha, root=root)
        path = root / overlay.TUNE_MANIFEST_REL
        document = overlay.read_json(path)
        document["cases"][0]["targets"][0]["tuned"]["video"]["bytes"] += 1
        transport.atomic_write_json(path, document)
        with self.assertRaisesRegex(
            overlay.TuneMediaOverlayError,
            "same-commit Tune media overlay differs",
        ):
            overlay.merge_manifest(commit_sha, root=root)

    def test_rejects_incomplete_or_unfinished_i2v_matrix(self) -> None:
        for mutation in ("unfinished", "missing"):
            with self.subTest(mutation=mutation):
                temporary, root, fixture = self.fixture()
                try:
                    if mutation == "unfinished":
                        fixture.i2v["outputs"][0]["status"] = "submitted"
                        fixture.i2v["summary"] = dict(
                            sorted(
                                Counter(
                                    row["status"] for row in fixture.i2v["outputs"]
                                ).items()
                            )
                        )
                    else:
                        fixture.i2v["outputs"].pop()
                    fixture.write_i2v()
                    with self.assertRaises(overlay.TuneMediaOverlayError):
                        overlay.build_merged_manifest("f" * 40, root=root)
                finally:
                    temporary.cleanup()

    def test_rejects_tampered_mp4_binding(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        output = fixture.i2v["outputs"][0]
        (root / output["video_path"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(
            overlay.TuneMediaOverlayError,
            "byte size mismatch|SHA-256 mismatch",
        ):
            overlay.build_merged_manifest("1" * 40, root=root)

    def test_preserves_non_failing_strict_quantization_warning(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        output = next(
            row
            for row in fixture.i2v["outputs"]
            if row["status"] == "succeeded"
        )
        warning = "resolution quantized within the strict 1080p-equivalent tolerance"
        output["contract_check"]["warnings"].append(warning)
        fixture.write_i2v()
        # Fallback inputs pin the provider-generation manifest, so a deliberate
        # local QA refresh must update both frozen bindings before validation.
        i2v_sha256 = overlay.sha256_file(root / overlay.I2V_MANIFEST_REL)
        fixture.fallback_plan["provider_generation"]["sha256"] = i2v_sha256
        for row in fixture.fallback_plan["targets"]:
            row["provider_failure"] = copy.deepcopy(
                fixture.provider_failures[(row["case_id"], row["model_id"])]
            )
        transport.atomic_write_json(
            root / overlay.FALLBACK_PLAN_REL,
            fixture.fallback_plan,
        )
        fixture.fallback["provider_generation"] = copy.deepcopy(
            fixture.fallback_plan["provider_generation"]
        )
        fixture.fallback["input_plan"]["sha256"] = overlay.sha256_file(
            root / overlay.FALLBACK_PLAN_REL
        )
        fixture.write_fallback()
        document, _ = overlay.build_merged_manifest("7" * 40, root=root)
        video = next(
            target["tuned"]["video"]
            for case in document["cases"]
            for target in case["targets"]
            if target["tuned"]["video"].get("generation", {}).get(
                "provider_run_id"
            )
            == output["provider_run_id"]
        )
        self.assertEqual(video["status"], "succeeded")
        self.assertIn(warning, video["contract_check"]["warnings"])

    def test_rejects_compositor_schema_or_plan_provenance_drift(self) -> None:
        for mutation in ("audio", "primitive"):
            with self.subTest(mutation=mutation):
                temporary, root, fixture = self.fixture()
                try:
                    if mutation == "audio":
                        fixture.compositor["outputs"][0]["media"]["audio_streams"] = 1
                    else:
                        fixture.compositor["outputs"][0]["plan"]["primitive"] = "pan"
                    fixture.write_compositor()
                    with self.assertRaises(overlay.TuneMediaOverlayError):
                        overlay.build_merged_manifest("2" * 40, root=root)
                finally:
                    temporary.cleanup()

    def test_refuses_noncanonical_commit_sha(self) -> None:
        temporary, root, fixture = self.fixture()
        self.addCleanup(temporary.cleanup)
        for value in ("main", "A" * 40, "a" * 39, "a" * 41):
            with self.subTest(value=value):
                with self.assertRaises(overlay.TuneMediaOverlayError):
                    overlay.build_merged_manifest(value, root=root)


if __name__ == "__main__":
    unittest.main()
