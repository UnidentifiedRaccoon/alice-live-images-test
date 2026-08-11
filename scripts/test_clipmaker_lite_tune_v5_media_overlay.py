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


if __name__ == "__main__":
    unittest.main()
