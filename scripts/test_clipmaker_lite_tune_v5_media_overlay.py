from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v5_media_overlay as overlay
from scripts import clipmaker_lite_tune_v5_pipeline as planning
from scripts import clipmaker_lite_tune_v5_video_pipeline as generation
from scripts.test_clipmaker_lite_tune_v5_pipeline import evaluation_fixture


ROOT = Path(__file__).resolve().parents[1]
V4_PATH = ROOT / planning.V4_SNAPSHOT_REL
MEDIA_COMMIT = "1" * 40
CONTRACT = json.loads((ROOT / generation.CONTRACT_REL).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_fixture(v4: dict, evaluations: dict) -> dict:
    evaluation_by_id = {value["evaluation_id"]: value for value in evaluations["evaluations"]}
    cases = []
    for source_case in v4["cases"]:
        case_id = source_case["case_id"]
        targets = []
        for source_target in source_case["targets"]:
            key = f"{case_id}::{source_target['model_id']}"
            if key not in planning.EXPECTED_REGENERATE_KEYS:
                continue
            evaluation = evaluation_by_id.get(key)
            outcome = evaluation["outcome"] if evaluation else "unrated"
            targets.append(
                {
                    "evaluation_id": key,
                    "sheet_row": source_target["sheet_row"],
                    "model_id": source_target["model_id"],
                    "selection_outcome": outcome,
                    "review_note": evaluation.get("note") if evaluation else None,
                    "original_sheet_comment": source_target.get("comment"),
                    "tuned": {
                        "execution_mode": "i2v",
                        "scene_plan": "One bounded I2V action.",
                        "positive_prompt": "The visible subject moves gently while source geometry remains fixed.",
                        "negative_prompt": None,
                        "runtime": copy.deepcopy(
                            CONTRACT["models"][source_target["model_id"]]["runtime"]
                        ),
                    },
                }
            )
        if targets:
            cases.append(
                {
                    "case_id": case_id,
                    "article_number": source_case["article_number"],
                    "article_slug": source_case["article_slug"],
                    "source": copy.deepcopy(source_case["source"]),
                    "context_path": source_case["context_path"],
                    "planning": {
                        "run_id": (
                            f"{planning.planning_batch_id_for_case(case_id)}-"
                            f"{source_case['article_slug']}-{source_case['source']['image_id']}"
                        ),
                        "result_path": "result.json",
                        "result_sha256": "a" * 64,
                        "provenance": {"verified": True},
                        "structured_intent": {
                            "rendering_strategy": "camera-only",
                        },
                        "repair_feedback_path": "repair.json",
                        "repair_feedback_sha256": "b" * 64,
                    },
                    "repair_revision": planning.planning_revision_for_case(case_id),
                    "targets": targets,
                }
            )
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-planning",
        "ticket": planning.TICKET,
        "batch_id": planning.REPAIR_BATCH_ID,
        "agent_id": planning.AGENT_ID,
        "contract_version": planning.EXPECTED_CONTRACT_VERSION,
        "scope": {
            "target_count": 28,
            "required_execution_mode": "i2v",
            "fallback": False,
        },
        "cases": cases,
    }


def copy_generation_bindings(root: Path) -> tuple[str, str]:
    for relative in (generation.CONTRACT_REL, generation.ROUTES_REL):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    return sha(root / generation.CONTRACT_REL), sha(root / generation.ROUTES_REL)


def generation_fixture(prompt: dict, prompt_sha: str, root: Path) -> dict:
    contract_sha, route_sha = copy_generation_bindings(root)
    rows = []
    entries = []
    for case in prompt["cases"]:
        for target in case["targets"]:
            model_id = target["model_id"]
            tuned = target["tuned"]
            planning_record = case["planning"]
            source = case["source"]
            item = generation.Entry(
                case_id=case["case_id"],
                sheet_row=target["sheet_row"],
                article_slug=case["article_slug"],
                image_id=str(source["image_id"]),
                model_id=model_id,
                source_path=source["path"],
                source_url=source["url"],
                source_sha256=source["sha256"],
                width=int(source["width"]),
                height=int(source["height"]),
                planning_run_id=planning_record["run_id"],
                result_path=planning_record["result_path"],
                result_sha256=planning_record["result_sha256"],
                prompt_manifest_sha256=prompt_sha,
                route_registry_sha256=route_sha,
                repair_feedback_path=planning_record["repair_feedback_path"],
                repair_feedback_sha256=planning_record["repair_feedback_sha256"],
                scene_plan=tuned["scene_plan"],
                positive_prompt=tuned["positive_prompt"],
                runtime=copy.deepcopy(tuned["runtime"]),
                provenance=copy.deepcopy(planning_record["provenance"]),
            )
            row = generation.materialize_entry(item, output_root=root)
            request = generation.transport.build_request_preview(row["sample"], row["prompt"])
            run = json.loads(row["paths"]["run"].read_text(encoding="utf-8"))
            run.update(
                {
                    "status": "provider-failed",
                    "request": request,
                    "request_sha256": generation.transport.request_fingerprint(
                        request,
                        row["sample"],
                    ),
                    "request_fingerprint_version": generation.transport.REQUEST_FINGERPRINT_VERSION,
                    "provider_job_id": "job-1",
                    "completed_at": "2026-08-11T18:00:00Z",
                    "provider_may_be_active": False,
                    "media": None,
                    "contract_check": None,
                    "error": "provider terminal failure",
                }
            )
            generation.transport.atomic_write_json(row["paths"]["run"], run)
            rows.append(row)
            entries.append(item)
    inventory = generation.Inventory(
        entries=tuple(entries),
        prompt_manifest_sha256=prompt_sha,
        contract_sha256=contract_sha,
        route_registry_sha256=route_sha,
        budget=generation.budget_document("9.80"),
    )
    return generation.generation_manifest_document(inventory, rows, output_root=root)


def v7_filter_generation_fixture(root: Path, *, status: str) -> tuple[dict, dict, dict, Path]:
    prompt_document = json.loads(
        (ROOT / overlay.V7_FILTER_PROMPT_MANIFEST_REL).read_text(encoding="utf-8")
    )
    case = copy.deepcopy(prompt_document["cases"][0])
    target = copy.deepcopy(case["targets"][0])
    entry = overlay.v7_generation.load_inventory(root=ROOT)
    paths = overlay.v7_generation.artifact_paths(entry, root)
    prompt_rel = overlay.relative_path(paths["prompt"], root)
    run_rel = overlay.relative_path(paths["run"], root)
    video_rel = overlay.relative_path(paths["video"], root)
    prompt_receipt = overlay.v7_generation.prompt_artifact(entry)
    prompt_path = root / prompt_rel
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(json.dumps(prompt_receipt) + "\n", encoding="utf-8")
    request = overlay.v7_generation.provider_request(entry)
    sample = overlay.v7_generation.provider_sample(entry)
    succeeded = status == "succeeded"
    media = None
    check = None
    error = None
    diagnostics = None
    terminal_stop = False
    if succeeded:
        payload = b"v7-filter-retry-mp4"
        video_path = root / video_rel
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(payload)
        media = {
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 4.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "frames": 96,
            "has_audio": False,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        check = {"conforms": True, "warnings": []}
    else:
        error = "Video generation completed with no output"
        diagnostics = {
            "status": "failed",
            "diagnostics_unavailable_upstream": True,
        }
        terminal_stop = True
    run = overlay.v7_generation._initial_run(entry, paths, root)  # noqa: SLF001
    run.update({
        "status": status,
        "request": request,
        "request_sha256": overlay.transport.request_fingerprint(request, sample),
        "request_fingerprint_version": overlay.transport.REQUEST_FINGERPRINT_VERSION,
        "submission_count": 1,
        "provider_job_id": "v7-job",
        "provider_may_be_active": False,
        "media": media,
        "contract_check": check,
        "error": error,
        "provider_terminal_diagnostics": diagnostics,
        "diagnostics_unavailable_upstream": (
            diagnostics.get("diagnostics_unavailable_upstream")
            if diagnostics is not None
            else None
        ),
        "terminal_no_output_stop_applied": terminal_stop,
    })
    run_path = root / run_rel
    run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")
    output = {
        "evaluation_id": overlay.V7_FILTER_EXPECTED_KEY,
        "provider_run_id": entry.provider_run_id,
        "case_id": case["case_id"],
        "sheet_row": target["sheet_row"],
        "article_slug": case["article_slug"],
        "image_id": "06",
        "model_id": target["model_id"],
        "execution_mode": "i2v",
        "prompt_path": prompt_rel,
        "run_path": run_rel,
        "video_path": video_rel,
        "status": status,
        "media": media,
        "contract_check": check,
        "error": error,
        "submission_count": 1,
        "provider_terminal_diagnostics": diagnostics,
        "diagnostics_unavailable_upstream": run[
            "diagnostics_unavailable_upstream"
        ],
        "terminal_no_output_stop_applied": terminal_stop,
        "automatic_paid_retry": False,
        "fallback": None,
        "s3_upload": False,
    }
    manifest = {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v7-filter-retry-video-generation",
        "ticket": overlay.TICKET,
        "batch_id": overlay.V7_FILTER_BATCH_ID,
        "agent_id": overlay.AGENT_ID,
        "scope": {
            "expected_i2v_outputs": 1,
            "model_counts": {target["model_id"]: 1},
            "prompt_batch_id": overlay.v7_planning.BATCH_ID,
            "prompt_manifest_sha256": overlay.V7_FILTER_EXPECTED_PROMPT_SHA256,
            "canonical_full_source_only": True,
            "source_transform": None,
            "disable_provider_safety_filters": False,
            "compositor_outputs": 0,
            "fallback_outputs": 0,
            "s3_upload": False,
        },
        "scheduling": {
            "one_paid_submission_per_new_provider_run_id": True,
            "automatic_paid_retry": False,
            "fallback": False,
        },
        "outputs": [output],
    }
    generation_path = root / overlay.V7_FILTER_GENERATION_MANIFEST_REL
    generation_path.parent.mkdir(parents=True, exist_ok=True)
    generation_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    return manifest, case, target, generation_path


class TuneV5MediaOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v4 = json.loads(V4_PATH.read_text(encoding="utf-8"))
        cls.evaluation = evaluation_fixture(cls.v4)

    def test_raw_url_requires_immutable_commit(self) -> None:
        path = "clipmaker-lite-test/runs/example/video.mp4"
        self.assertEqual(
            overlay.raw_url(MEDIA_COMMIT, path),
            f"https://raw.githubusercontent.com/UnidentifiedRaccoon/alice-live-images-test/{MEDIA_COMMIT}/{path}",
        )
        for bad in ("main", "A" * 40, "0" * 39):
            with self.assertRaises(overlay.TuneV5OverlayError):
                overlay.validate_commit_sha(bad)

    def test_helped_v4_target_is_reused_as_eliza_i2v(self) -> None:
        key = next(
            key
            for key in (
                f"{case['case_id']}::{target['model_id']}"
                for case in self.v4["cases"]
                for target in case["targets"]
            )
            if key not in planning.EXPECTED_REGENERATE_KEYS
        )
        case_id, model_id = key.split("::", 1)
        target = next(
            target
            for case in self.v4["cases"]
            if case["case_id"] == case_id
            for target in case["targets"]
            if target["model_id"] == model_id
        )
        video = overlay._reused_video(  # noqa: SLF001
            target,
            root=ROOT,
            media_commit_sha=MEDIA_COMMIT,
        )
        self.assertEqual(video["method"], "eliza-i2v")
        self.assertEqual(video["state"], "available")
        self.assertIn(f"/{MEDIA_COMMIT}/", video["url"])
        self.assertEqual(video["generation"]["origin"], "reused-helped-v4")

    def test_provider_failure_stays_unavailable_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "run.json"
            prompt = root / "prompt.json"
            run.write_text(
                json.dumps(
                    {
                        "status": "provider-failed",
                        "fallback": None,
                        "automatic_paid_retry": False,
                        "provider_job_id": "job-1",
                        "error": "filtered",
                    }
                ),
                encoding="utf-8",
            )
            prompt.write_text("{}\n", encoding="utf-8")
            value = overlay._new_video(  # noqa: SLF001
                {
                    "status": "provider-failed",
                    "provider_run_id": "run-1",
                    "run_path": "run.json",
                    "prompt_path": "prompt.json",
                    "error": "filtered",
                },
                root=root,
                media_commit_sha=MEDIA_COMMIT,
            )
            self.assertEqual(value["state"], "unavailable")
            self.assertEqual(value["method"], "eliza-i2v")
            self.assertEqual(value["delivery"], "unavailable")
            self.assertIsNone(value["url"])
            self.assertIsNone(value["provider_attempt"]["fallback"])
            self.assertFalse(value["provider_attempt"]["automatic_paid_retry"])

    def test_full_merge_is_37_reused_plus_28_new_and_only_i2v(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / planning.V4_SNAPSHOT_REL
            snapshot.parent.mkdir(parents=True)
            snapshot.write_bytes(V4_PATH.read_bytes())
            evaluation_path = root / "evaluation.json"
            evaluation_path.write_text(
                json.dumps(self.evaluation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            prompt = prompt_fixture(self.v4, self.evaluation)
            prompt_path = root / "prompt-manifest.json"
            prompt_path.write_text(json.dumps(prompt, ensure_ascii=False) + "\n", encoding="utf-8")
            generated = generation_fixture(prompt, sha(prompt_path), root)
            generation_path = root / "generation-manifest.json"
            generation_path.write_text(json.dumps(generated, ensure_ascii=False) + "\n", encoding="utf-8")
            with mock.patch.object(overlay, "confined_file", return_value=root / "fixture.mp4"):
                manifest = overlay.build_live_manifest(
                    evaluation_path,
                    MEDIA_COMMIT,
                    root=root,
                    prompt_manifest_path=prompt_path,
                    generation_manifest_path=generation_path,
                    expected_v4_sha256=sha(snapshot),
                    expected_evaluation_sha256=sha(evaluation_path),
                )
        targets = [target for case in manifest["cases"] for target in case["targets"]]
        actions = Counter(target["iteration"]["action"] for target in targets)
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(actions, Counter({"reused-helped": 37, "regenerated-v5": 28}))
        self.assertEqual(manifest["scope"]["execution_mode_counts"], {"i2v": 65})
        self.assertEqual(manifest["scope"]["video_method_counts"], {"eliza-i2v": 65})
        self.assertEqual(manifest["scope"]["unavailable_video_count"], 28)
        self.assertTrue(all(target["tuned"]["execution_mode"] == "i2v" for target in targets))
        self.assertTrue(all(target["tuned"]["video"]["method"] == "eliza-i2v" for target in targets))
        regenerated = [target for target in targets if target["iteration"]["review_scope"]]
        reused = [target for target in targets if not target["iteration"]["review_scope"]]
        self.assertEqual(len(regenerated), 28)
        self.assertEqual(len(reused), 37)
        self.assertTrue(all("previous_tuned" in target for target in regenerated))
        self.assertTrue(all("previous_tuned" not in target for target in reused))
        active_serialized = json.dumps([target["tuned"] for target in targets])
        self.assertNotIn("tune-compositor", active_serialized)
        self.assertNotIn("deterministic-compositor-fallback", active_serialized)

    def test_generation_validator_rejects_any_fallback_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = prompt_fixture(self.v4, self.evaluation)
            prompt_path = root / "prompt.json"
            prompt_path.write_text(json.dumps(prompt) + "\n", encoding="utf-8")
            targets, prompt_sha = overlay.validate_prompt_manifest(prompt, path=prompt_path)
            generated = generation_fixture(prompt, prompt_sha, root)
            generated["outputs"][0]["fallback"] = {"method": "forbidden"}
            generation_path = root / "generation.json"
            generation_path.write_text(json.dumps(generated) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(overlay.TuneV5OverlayError, "Invalid/duplicate"):
                overlay.validate_generation_manifest(
                    generated,
                    path=generation_path,
                    prompt_sha256=prompt_sha,
                    prompt_targets=targets,
                    root=root,
                )

    def test_generation_validator_rejects_cross_target_video_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = prompt_fixture(self.v4, self.evaluation)
            prompt_path = root / "prompt.json"
            prompt_path.write_text(json.dumps(prompt) + "\n", encoding="utf-8")
            targets, prompt_sha = overlay.validate_prompt_manifest(prompt, path=prompt_path)
            generated = generation_fixture(prompt, prompt_sha, root)
            generated["outputs"][0]["video_path"] = generated["outputs"][1]["video_path"]
            generation_path = root / "generation.json"
            generation_path.write_text(json.dumps(generated) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(overlay.TuneV5OverlayError, "target binding changed"):
                overlay.validate_generation_manifest(
                    generated,
                    path=generation_path,
                    prompt_sha256=prompt_sha,
                    prompt_targets=targets,
                    root=root,
                )

    def test_generation_validator_rejects_tampered_request_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = prompt_fixture(self.v4, self.evaluation)
            prompt_path = root / "prompt.json"
            prompt_path.write_text(json.dumps(prompt) + "\n", encoding="utf-8")
            targets, prompt_sha = overlay.validate_prompt_manifest(prompt, path=prompt_path)
            generated = generation_fixture(prompt, prompt_sha, root)
            run_path = root / generated["outputs"][0]["run_path"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["request"] = {"tampered": True}
            run_path.write_text(json.dumps(run) + "\n", encoding="utf-8")
            generation_path = root / "generation.json"
            generation_path.write_text(json.dumps(generated) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(overlay.TuneV5OverlayError, "receipt binding changed"):
                overlay.validate_generation_manifest(
                    generated,
                    path=generation_path,
                    prompt_sha256=prompt_sha,
                    prompt_targets=targets,
                    root=root,
                )

    def test_original_v5_nonterminal_attempts_are_accepted_only_when_superseded_by_v6(self) -> None:
        prompt_path = ROOT / generation.PROMPT_MANIFEST_REL
        prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
        targets, prompt_sha = overlay.validate_prompt_manifest(prompt, path=prompt_path)
        generation_path = ROOT / generation.GENERATION_MANIFEST_REL
        generated = json.loads(generation_path.read_text(encoding="utf-8"))
        outputs, _digest = overlay.validate_generation_manifest(
            generated,
            path=generation_path,
            prompt_sha256=prompt_sha,
            prompt_targets=targets,
            root=ROOT,
            superseded_keys=overlay.retry_generation.EXPECTED_KEYS,
        )
        self.assertEqual(
            {outputs[key]["status"] for key in overlay.retry_generation.EXPECTED_KEYS},
            {"provider-failed", "submit-unknown", "dry-run"},
        )
        with self.assertRaises(overlay.TuneV5OverlayError):
            overlay.validate_generation_manifest(
                generated,
                path=generation_path,
                prompt_sha256=prompt_sha,
                prompt_targets=targets,
                root=ROOT,
            )

    def test_retry_planning_records_bind_r7_07_and_reused_r6_10(self) -> None:
        inventory = overlay.retry_generation.load_inventory(root=ROOT)
        veo = {entry.case_id: entry for entry in inventory.entries if entry.model_id == "google/veo-3.1-lite"}
        self.assertTrue(veo["07#06"].planning_run_id.startswith("promopages-10060-tune-prompts-20260811-v5-r7-"))
        self.assertTrue(veo["10#07"].planning_run_id.startswith("promopages-10060-tune-prompts-20260811-v5-r6-"))
        self.assertIn("within a 5% screen-travel cap", veo["07#06"].positive_prompt)
        self.assertIn("3%", veo["10#07"].positive_prompt)
        for entry in veo.values():
            record = overlay._retry_planning_record(entry, root=ROOT)  # noqa: SLF001
            self.assertTrue(record["provenance"]["verified"])

    def test_retry_terminal_failure_remains_unavailable_without_fallback(self) -> None:
        entry = next(
            item
            for item in overlay.retry_generation.load_inventory(root=ROOT).entries
            if item.evaluation_id == "18#05::alibaba/wan-2.7"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_path = root / "run.json"
            prompt_path = root / "prompt.json"
            run_path.write_text(json.dumps({"provider_job_id": "job", "submission_count": 1}) + "\n")
            prompt_path.write_text("{}\n")
            value = overlay._retry_video(  # noqa: SLF001
                {
                    "status": "provider-failed",
                    "provider_run_id": entry.provider_run_id,
                    "run_path": "run.json",
                    "prompt_path": "prompt.json",
                    "error": "terminal",
                },
                entry,
                root=root,
                media_commit_sha=MEDIA_COMMIT,
                route_barrier=entry.prior_attempt,
            )
        self.assertEqual(value["state"], "unavailable")
        self.assertEqual(value["generation"]["origin"], "regenerated-v6-retry")
        self.assertIsNone(value["provider_attempt"]["fallback"])
        self.assertFalse(value["provider_attempt"]["automatic_paid_retry"])

    def test_authorized_wan_retry_success_and_unknown_statuses_stay_i2v(self) -> None:
        inventory = overlay.retry_generation.load_inventory(root=ROOT)
        entries = {entry.evaluation_id: entry for entry in inventory.entries}
        entry = entries["17#11::alibaba/wan-2.2"]
        barrier = entries[overlay.retry_generation.SUBMIT_UNKNOWN_KEY].prior_attempt
        duplicate_risk = {
            "authorization_kind": "explicit-operator-duplicate-risk-acceptance",
            "prior_inactive_not_confirmed": True,
            "source_evaluation_id": overlay.retry_generation.SUBMIT_UNKNOWN_KEY,
            "source_provider_run_id": barrier["provider_run_id"],
            "source_status": "submit-unknown",
            "source_provider_job_id": None,
            "source_run_path": barrier["run_path"],
            "source_run_sha256": barrier["run_sha256"],
            "maximum_possible_duplicate_charge_usd": 0.35,
            "automatic_paid_retry": False,
            "fallback": None,
            "authorized_evaluation_id": entry.evaluation_id,
        }
        media = {
            "sha256": "a" * 64,
            "bytes": 123,
            "duration_seconds": 5.0,
            "width": 1280,
            "height": 720,
            "fps": 24.0,
            "frames": 120,
            "has_audio": False,
            "container": "mp4",
            "codec": "h264",
        }
        check = {"conforms": True, "warnings": []}
        with (
            mock.patch.object(overlay, "confined_file", return_value=Path("video.mp4")),
            mock.patch.object(overlay, "V6_VISUAL_QA", {}),
        ):
            succeeded = overlay._retry_video(  # noqa: SLF001
                {
                    "status": "succeeded",
                    "provider_run_id": entry.provider_run_id,
                    "prompt_path": "prompt.json",
                    "run_path": "run.json",
                    "video_path": "video.mp4",
                    "media": media,
                    "contract_check": check,
                    "duplicate_risk_acceptance": duplicate_risk,
                },
                entry,
                root=ROOT,
                media_commit_sha=MEDIA_COMMIT,
                route_barrier=barrier,
            )
        self.assertEqual(succeeded["state"], "available")
        self.assertEqual(succeeded["method"], "eliza-i2v")
        self.assertEqual(
            succeeded["generation"]["duplicate_risk_acceptance"], duplicate_risk
        )

        for status, provider_may_be_active in (
            ("provider-failed", False),
            ("failed-pre-submit", False),
            ("submit-unknown", True),
        ):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                run = {
                    "provider_job_id": None,
                    "provider_may_be_active": provider_may_be_active,
                    "submission_count": 1,
                }
                (root / "run.json").write_text(json.dumps(run) + "\n", encoding="utf-8")
                (root / "prompt.json").write_text("{}\n", encoding="utf-8")
                failed = overlay._retry_video(  # noqa: SLF001
                    {
                        "status": status,
                        "provider_run_id": entry.provider_run_id,
                        "prompt_path": "prompt.json",
                        "run_path": "run.json",
                        "video_path": "video.mp4",
                        "error": f"{status} fixture",
                        "duplicate_risk_acceptance": duplicate_risk,
                    },
                    entry,
                    root=root,
                    media_commit_sha=MEDIA_COMMIT,
                    route_barrier=barrier,
                )
            self.assertEqual(failed["state"], "unavailable")
            self.assertEqual(failed["recorded_status"], status)
            self.assertEqual(failed["method"], "eliza-i2v")
            self.assertEqual(
                failed["provider_attempt"]["provider_may_be_active"],
                provider_may_be_active,
            )
            self.assertEqual(
                failed["provider_attempt"]["duplicate_risk_acceptance"],
                duplicate_risk,
            )
            self.assertIsNone(failed["provider_attempt"]["fallback"])

    def test_v7_filter_retry_success_and_no_output_are_both_publishable_i2v(self) -> None:
        for status in ("succeeded", "provider-failed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, case, target, generation_path = v7_filter_generation_fixture(
                    root, status=status
                )
                entry = overlay.v7_generation.load_inventory(root=ROOT)
                with (
                    mock.patch.object(
                        overlay,
                        "_load_v7_filter_prompt",
                        return_value=(
                            case,
                            target,
                            overlay.V7_FILTER_EXPECTED_PROMPT_SHA256,
                        ),
                    ),
                    mock.patch.object(
                        overlay.v7_generation,
                        "load_inventory",
                        return_value=entry,
                    ),
                ):
                    output, validated_case, _target, _generation_sha, _prompt_sha = (
                        overlay.validate_v7_filter_generation_manifest(
                            manifest,
                            path=generation_path,
                            root=root,
                        )
                    )
                video = overlay._v7_filter_video(  # noqa: SLF001
                    output,
                    validated_case,
                    root=root,
                    media_commit_sha=MEDIA_COMMIT,
                )
                self.assertEqual(video["method"], "eliza-i2v")
                self.assertEqual(
                    video["generation"]["origin"],
                    "regenerated-v7-filter-retry",
                )
                self.assertIsNone(video["provider_attempt"] if status == "succeeded" else video["provider_attempt"]["fallback"])
                if status == "succeeded":
                    self.assertEqual(video["state"], "available")
                    self.assertTrue(video["prompt_evaluated"])
                else:
                    self.assertEqual(video["state"], "unavailable")
                    self.assertEqual(video["recorded_status"], "provider-failed")
                    self.assertTrue(
                        video["provider_attempt"]["terminal_no_output_stop_applied"]
                    )

    def test_v7_filter_retry_rejects_fallback_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, case, target, generation_path = v7_filter_generation_fixture(
                root, status="provider-failed"
            )
            entry = overlay.v7_generation.load_inventory(root=ROOT)
            manifest["outputs"][0]["fallback"] = {"method": "forbidden"}
            with (
                mock.patch.object(
                    overlay,
                    "_load_v7_filter_prompt",
                    return_value=(
                        case,
                        target,
                        overlay.V7_FILTER_EXPECTED_PROMPT_SHA256,
                    ),
                ),
                mock.patch.object(
                    overlay.v7_generation,
                    "load_inventory",
                    return_value=entry,
                ),
                self.assertRaisesRegex(
                    overlay.TuneV5OverlayError, "output binding changed"
                ),
            ):
                overlay.validate_v7_filter_generation_manifest(
                    manifest,
                    path=generation_path,
                    root=root,
                )

    def test_v8_terminal_prompt_experiment_is_preserved_as_three_failed_attempts(self) -> None:
        generation_path = ROOT / overlay.V8_EXPERIMENT_GENERATION_MANIFEST_REL
        document = json.loads(generation_path.read_text(encoding="utf-8"))
        outputs, entries, prompt_case, generation_sha, prompt_sha = (
            overlay.validate_v8_experiment_generation_manifest(
                document,
                path=generation_path,
                root=ROOT,
            )
        )
        video = overlay._v8_experiment_video(  # noqa: SLF001
            outputs,
            entries,
            prompt_case,
            root=ROOT,
        )
        self.assertEqual(generation_sha, overlay.V8_EXPERIMENT_EXPECTED_GENERATION_SHA256)
        self.assertEqual(prompt_sha, overlay.V8_EXPERIMENT_EXPECTED_PROMPT_SHA256)
        self.assertEqual(
            [entry.variant_id for entry in entries],
            ["minimal-zoom", "camera-forward", "framing-endpoint"],
        )
        self.assertEqual(video["state"], "unavailable")
        self.assertEqual(
            video["generation"]["origin"],
            "regenerated-v8-veo-prompt-experiment",
        )
        self.assertEqual(video["unavailable_reason"], overlay.V8_UNAVAILABLE_REASON)
        self.assertTrue(
            video["generation"]["displayed_tuned_prompt_is_prior_baseline"]
        )
        self.assertEqual(video["provider_attempt"]["attempt_count"], 3)
        self.assertEqual(video["provider_attempt"]["terminal_no_output_count"], 3)
        self.assertEqual(len(video["provider_attempt"]["attempts"]), 3)
        self.assertTrue(
            all(
                attempt["status"] == "provider-failed"
                and attempt["terminal_no_output_stop_applied"] is True
                and attempt["fallback"] is None
                and attempt["s3_upload"] is False
                for attempt in video["provider_attempt"]["attempts"]
            )
        )

        for name, mutate in (
            (
                "output binding changed",
                lambda value: value["outputs"][0].update(
                    {"fallback": {"method": "forbidden"}}
                ),
            ),
            ("terminal V8 experiment manifest", lambda value: value["outputs"].pop()),
        ):
            with self.subTest(name=name):
                changed = copy.deepcopy(document)
                mutate(changed)
                with self.assertRaisesRegex(overlay.TuneV5OverlayError, name):
                    overlay.validate_v8_experiment_generation_manifest(
                        changed,
                        path=generation_path,
                        root=ROOT,
                    )

    def test_v6_successes_carry_sha_bound_non_rejecting_visual_qa(self) -> None:
        generation_path = ROOT / overlay.RETRY_GENERATION_MANIFEST_REL
        document = json.loads(generation_path.read_text(encoding="utf-8"))
        outputs, entries, _digest = overlay.validate_retry_generation_manifest(
            document,
            path=generation_path,
            root=ROOT,
        )
        self.assertEqual(
            outputs["18#05::alibaba/wan-2.2"]["status"],
            "provider-failed",
        )
        self.assertIn(
            "Image height or width is too small than 240",
            outputs["18#05::alibaba/wan-2.2"]["error"],
        )
        self.assertEqual(
            outputs["18#07::alibaba/wan-2.2"]["status"],
            "dry-run",
        )
        barrier = entries[overlay.retry_generation.SUBMIT_UNKNOWN_KEY].prior_attempt
        for key in (
            "17#11::alibaba/wan-2.2",
            "18#06::alibaba/wan-2.2",
        ):
            with self.subTest(key=key):
                video = overlay._retry_video(  # noqa: SLF001
                    outputs[key],
                    entries[key],
                    root=ROOT,
                    media_commit_sha=MEDIA_COMMIT,
                    route_barrier=barrier,
                )
                self.assertEqual(video["status"], "succeeded")
                self.assertTrue(video["contract_check"]["conforms"])
                self.assertEqual(video["qa"]["status"], "visual-review-failed")
                self.assertFalse(video["qa"]["verified"])
                self.assertTrue(video["qa"]["reviewable"])
                self.assertFalse(video["qa"]["automatic_rejection"])
                self.assertEqual(video["qa"]["video_sha256"], video["sha256"])


if __name__ == "__main__":
    unittest.main()
