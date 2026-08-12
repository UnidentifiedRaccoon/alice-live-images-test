from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_tune_v5_pipeline as v5


ROOT = Path(__file__).resolve().parents[1]
V4_PATH = ROOT / v5.V4_SNAPSHOT_REL


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flatten(manifest: dict) -> dict[str, tuple[dict, dict]]:
    return {
        f"{case['case_id']}::{target['model_id']}": (case, target)
        for case in manifest["cases"]
        for target in case["targets"]
    }


def evaluation_fixture(manifest: dict) -> dict:
    flattened = _flatten(manifest)
    evaluations = []
    for key, (case, target) in flattened.items():
        if key in v5.EXPECTED_WORSE_KEYS:
            outcome = "worse"
        elif key in v5.EXPECTED_UNCLEAR_KEYS:
            outcome = "same-or-unclear"
        elif key in v5.EXPECTED_REGENERATE_KEYS:
            continue
        else:
            outcome = "helped"
        video = target["tuned"]["video"]
        note = None if key == "18#06::alibaba/wan-2.2" else f"review for {key}"
        evaluations.append(
            {
                "evaluation_id": key,
                "case_id": case["case_id"],
                "article_number": case["article_number"],
                "article_slug": case["article_slug"],
                "image_id": case["source"]["image_id"],
                "model_id": target["model_id"],
                "planned_execution_mode": target["tuned"]["execution_mode"],
                "method": video["method"],
                "prompt_evaluated": video.get("prompt_evaluated"),
                "outcome": outcome,
                "note": note,
                "updated_at": "2026-08-11T16:00:00Z",
                "tuned_video": {
                    "state": "available",
                    "status": video["status"],
                    "delivery": video["delivery"],
                    "url": video["url"],
                    "repository_video_path": video["repository_video_path"],
                    "sha256": video["sha256"],
                    "method": video["method"],
                },
            }
        )
    outcomes = [entry["outcome"] for entry in evaluations]
    return {
        "schema_version": 1,
        "export_role": "clipmaker-lite-tune-evaluation",
        "exported_at": "2026-08-11T16:59:38.979Z",
        "dataset": {
            "ticket": v5.TICKET,
            "batch_id": v5.V4_BATCH_ID,
            "contract_version": "2.2.0",
            "manifest_generated_at": manifest["generated_at"],
        },
        "summary": {
            "target_count": 65,
            "saved_entry_count": 46,
            "evaluated_count": 46,
            "draft_count": 0,
            "helped_count": outcomes.count("helped"),
            "same_or_unclear_count": outcomes.count("same-or-unclear"),
            "worse_count": outcomes.count("worse"),
            "unrated_count": 19,
        },
        "evaluations": evaluations,
    }


class TuneV5PlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v4 = json.loads(V4_PATH.read_text(encoding="utf-8"))

    def _workspace(self) -> tuple[tempfile.TemporaryDirectory, Path, Path, str, str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        snapshot = root / v5.V4_SNAPSHOT_REL
        snapshot.parent.mkdir(parents=True)
        snapshot.write_bytes(V4_PATH.read_bytes())
        for relative in (
            v5.BASE_SELECTION_REL,
            v5.BASE_PROMPT_MANIFEST_REL,
            v5.R2_SELECTION_REL,
            v5.R2_PROMPT_MANIFEST_REL,
            v5.R3_SELECTION_REL,
        ):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        for case in self.v4["cases"]:
            if case["case_id"] not in v5.EXPECTED_CASE_IDS:
                continue
            for relative in (case["source"]["path"], case["context_path"]):
                source = ROOT / relative
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        evaluation = root / "evaluation.json"
        evaluation.write_text(
            json.dumps(evaluation_fixture(self.v4), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return temporary, root, evaluation, _sha(snapshot), _sha(evaluation)

    def test_frozen_production_identity_matches_committed_v4(self) -> None:
        self.assertEqual(_sha(V4_PATH), v5.EXPECTED_V4_MANIFEST_SHA256)
        self.assertEqual(len(v5.EXPECTED_REGENERATE_KEYS), 28)
        self.assertEqual(len(v5.EXPECTED_CASE_IDS), 17)

    def test_selection_is_exact_28_target_17_case_matrix(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        document = v5.build_selection_document(
            evaluation,
            root=root,
            evaluation_sha256=evaluation_sha,
            v4_manifest_sha256=v4_sha,
        )
        targets = [target for case in document["cases"] for target in case["targets"]]
        self.assertEqual(document["summary"]["case_count"], 17)
        self.assertEqual(document["summary"]["target_count"], 28)
        self.assertEqual(document["summary"]["reused_helped_count"], 37)
        self.assertEqual(document["summary"]["repair_case_count"], 1)
        self.assertEqual(document["summary"]["repair_target_count"], 1)
        self.assertEqual(document["summary"]["reused_prior_v5_target_count"], 27)
        self.assertEqual(document["summary"]["model_counts"], v5.EXPECTED_MODEL_COUNTS)
        self.assertEqual(document["summary"]["outcome_counts"], v5.EXPECTED_OUTCOME_COUNTS)
        self.assertEqual({target["evaluation_id"] for target in targets}, v5.EXPECTED_REGENERATE_KEYS)
        self.assertTrue(all(target["repair_feedback"]["required_execution_mode"] == "i2v" for target in targets))
        self.assertTrue(all(target["repair_feedback"]["fallback_policy"] == "none" for target in targets))
        revised_cases = {
            case["case_id"]
            for case in document["cases"]
            if case["repair_revision"] == v5.REPAIR_REVISION
        }
        self.assertEqual(revised_cases, v5.REPAIR_CASE_IDS)
        for case in document["cases"]:
            expected_batch = v5.planning_batch_id_for_case(case["case_id"])
            self.assertTrue(case["run_id"].startswith(f"{expected_batch}-"))

    def test_repair_feedback_encodes_visual_qa_repairs(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        document = v5.build_selection_document(
            evaluation,
            root=root,
            evaluation_sha256=evaluation_sha,
            v4_manifest_sha256=v4_sha,
        )
        feedback = {
            target["evaluation_id"]: target["repair_feedback"]
            for case in document["cases"]
            for target in case["targets"]
        }
        bottles = feedback["05#04::alibaba/wan-2.7"]
        self.assertEqual(bottles["camera_repair"]["move"], "push-in")
        self.assertIn("focal_target_drift", bottles["failure_codes"])
        self.assertIn("all four upper bottles throughout the shot", bottles["preservation"]["must_remain_visible"])
        ride = feedback["11#03::google/veo-3.1-lite"]
        self.assertIn("topology_hallucination", ride["failure_codes"])
        self.assertTrue(any("add no ride rows" in value for value in ride["preservation"]["topology_anchors"]))
        self.assertEqual(ride["camera_repair"]["move"], "fixed")
        self.assertEqual(ride["camera_repair"]["max_screen_travel_percent"], 0)
        self.assertIn("projected pterosaur", ride["camera_repair"]["focal_target"])
        self.assertTrue(any("flap in place" in value for value in ride["preservation"]["topology_anchors"]))
        floor = feedback["17#08::google/veo-3.1-lite"]
        self.assertEqual(floor["camera_repair"]["move"], "handheld-inspection")
        self.assertIn("rigid_world_deformation", floor["failure_codes"])
        required_cap = v5.REQUIRED_POSITIVE_PROMPT_PHRASES["03#09"]
        for evaluation_id in (
            "03#09::alibaba/wan-2.2",
            "03#09::google/veo-3.1-lite",
        ):
            self.assertTrue(
                any(
                    required_cap in value
                    for value in feedback[evaluation_id]["preservation"]["topology_anchors"]
                )
            )
        unclear = feedback["18#06::alibaba/wan-2.2"]
        self.assertEqual(unclear["failure_codes"], ["unclear_review"])
        self.assertIsNone(unclear["review_note"])
        self.assertEqual(unclear["camera_repair"]["move"], "fixed")
        self.assertEqual(unclear["camera_repair"]["max_screen_travel_percent"], 0)
        semantic_values = [unclear["camera_repair"]["focal_target"]]
        semantic_values.extend(
            item
            for values in unclear["preservation"].values()
            for item in values
        )
        serialized_unclear = json.dumps(semantic_values, ensure_ascii=False).lower()
        self.assertIn("head, shoulders, and torso", serialized_unclear)
        self.assertIn("detached trowel stays lying separately", serialized_unclear)
        self.assertIn("head, shoulders, and torso", serialized_unclear)
        self.assertIn("arms do not reach toward or touch any tool", serialized_unclear)
        self.assertNotIn("hand-forearm-trowel chain", serialized_unclear)
        self.assertNotIn("adhesive-application stroke", serialized_unclear)
        self.assertEqual(unclear["preservation"]["contacts"], [])
        self.assertTrue(any("detached trowel" in value for value in unclear["preservation"]["rigid_regions"]))
        for forbidden in ("held", " hold", "contact", "blade", "stroke", "trowel-motion"):
            self.assertNotIn(forbidden, serialized_unclear)

        for evaluation_id in (
            "07#06::google/veo-3.1-lite",
            "10#07::google/veo-3.1-lite",
        ):
            people = feedback[evaluation_id]
            self.assertIn("insufficient_motion", people["failure_codes"])
            self.assertEqual(people["camera_repair"]["move"], "fixed")
        attraction = feedback["13#05::google/veo-3.1-lite"]
        self.assertIn("insufficient_motion", attraction["failure_codes"])
        self.assertEqual(attraction["camera_repair"]["move"], "fixed")

    def test_repair_focal_targets_are_source_consistent(self) -> None:
        expected = {
            "01#03": (
                "the mortgage issuance regional bar chart, especially the existing "
                "blue February 2026 bars"
            ),
            "04#04": "the four apartment listing cards and their existing layouts",
            "05#04": "the cleaning products on the two cabinet shelves, not the cabinet door",
            "14#05": "the existing two-column interface card grid",
            "17#08": "the central broken floor section, cracks, raised slab, and visible tools",
            "03#09": "the complete apartment floor plan with its existing arrow and room 3.9",
            "14#04": "the exact text screenshot and its existing page layout",
            "18#05": (
                "the two-row material recommendation table with its existing check and warning"
            ),
            "18#07": "the two-row adhesive recommendation table and its existing warning",
            "18#06": (
                "the visible worker's head, shoulders, and torso inspecting the floor; "
                "the detached trowel remains lying separately at right"
            ),
        }
        for case_id, focal_target in expected.items():
            self.assertEqual(v5.FOCAL_TARGETS[case_id], focal_target)

    def test_camera_caps_preserve_tight_and_semantic_layouts(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        document = v5.build_selection_document(
            evaluation,
            root=root,
            evaluation_sha256=evaluation_sha,
            v4_manifest_sha256=v4_sha,
        )
        feedback = {
            target["evaluation_id"]: target["repair_feedback"]
            for case in document["cases"]
            for target in case["targets"]
        }
        expected_caps = {
            "01#02": 5.0,
            "01#03": 6.0,
            "03#09": 4.0,
            "04#04": 1.5,
            "14#04": 4.0,
            "18#05": 1.5,
            "18#07": 1.5,
        }
        for case_id, cap in expected_caps.items():
            case_feedback = [
                value for key, value in feedback.items() if key.startswith(f"{case_id}::")
            ]
            self.assertTrue(case_feedback)
            for value in case_feedback:
                self.assertEqual(value["camera_repair"]["max_screen_travel_percent"], cap)
                self.assertIn(
                    v5.FULL_LAYOUT_ANCHORS[case_id],
                    value["preservation"]["must_remain_visible"],
                )
        for key, value in feedback.items():
            if key.startswith("14#05::"):
                self.assertEqual(value["camera_repair"]["max_screen_travel_percent"], 8)

    def test_rigid_regions_and_contacts_are_visible_physical_anchors(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        document = v5.build_selection_document(
            evaluation,
            root=root,
            evaluation_sha256=evaluation_sha,
            v4_manifest_sha256=v4_sha,
        )
        for case in document["cases"]:
            for target in case["targets"]:
                preservation = target["repair_feedback"]["preservation"]
                self.assertEqual(preservation["rigid_regions"], v5.RIGID_REGIONS[case["case_id"]])
                self.assertEqual(preservation["contacts"], v5.CONTACTS.get(case["case_id"], []))

    def test_write_selection_materializes_exact_per_case_feedback(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        document = v5.build_selection_document(
            evaluation,
            root=root,
            evaluation_sha256=evaluation_sha,
            v4_manifest_sha256=v4_sha,
        )
        output = v5.write_selection(document, root=root)
        self.assertTrue(output.is_file())
        loaded = v5.load_selection(root)
        self.assertEqual(loaded, document)
        for case in loaded["cases"]:
            feedback = json.loads((root / case["repair_feedback_path"]).read_text())
            self.assertEqual(list(feedback), case["selected_model_ids"])
            self.assertEqual(v5.canonical_sha256(feedback), case["repair_feedback_sha256"])

    def test_snapshot_is_byte_identical_and_refuses_changed_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            source.write_bytes(V4_PATH.read_bytes())
            destination = root / "snapshot.json"
            v5.snapshot_v4(
                root=root,
                source=source,
                destination=destination,
                expected_sha256=_sha(source),
            )
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaisesRegex(v5.TuneV5PipelineError, "SHA-256 changed"):
                v5.snapshot_v4(
                    root=root,
                    source=source,
                    destination=root / "other.json",
                    expected_sha256=_sha(destination),
                )

    def test_export_digest_is_fail_closed(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(v5.TuneV5PipelineError, "SHA-256 changed"):
            v5.build_selection_document(
                evaluation,
                root=root,
                evaluation_sha256="0" * 64,
                v4_manifest_sha256=v4_sha,
            )
        self.assertNotEqual(evaluation_sha, "0" * 64)

    def test_prepare_passes_repair_feedback_path_to_runner(self) -> None:
        case = {
            "run_id": f"{v5.BATCH_ID}-example-01",
            "source": {"path": "source.png", "image_id": "01"},
            "context_path": "context.json",
            "selected_model_ids": ["alibaba/wan-2.2"],
            "repair_feedback_path": "repair.json",
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            v5.runner, "prepare_run"
        ) as prepare:
            status = v5.prepare_case(case, root=Path(directory))
        self.assertEqual(status, "prepared")
        self.assertEqual(prepare.call_args.kwargs["repair_feedback_path"], "repair.json")
        self.assertIsNone(prepare.call_args.kwargs["user_direction"])

    def test_existing_prepared_run_rejects_swapped_source_binding(self) -> None:
        temporary, root, evaluation, v4_sha, evaluation_sha = self._workspace()
        self.addCleanup(temporary.cleanup)
        document = v5.build_selection_document(
            evaluation,
            root=root,
            evaluation_sha256=evaluation_sha,
            v4_manifest_sha256=v4_sha,
        )
        case = document["cases"][0]
        directory = root / v5.runner.OUTPUT_NAMESPACE / case["run_id"]
        directory.mkdir(parents=True)
        job = {
            "inputs": {
                "source_image": {
                    "path": "swapped.png",
                    "sha256": "0" * 64,
                },
                "article_context": copy.deepcopy(case["context_binding"]),
                "repair_feedback": {
                    "path": case["repair_feedback_path"],
                    "canonical_sha256": case["repair_feedback_sha256"],
                },
            }
        }
        runner_selection = {
            "selected_models": [
                {"model_id": model_id} for model_id in case["selected_model_ids"]
            ]
        }
        with mock.patch.object(
            v5.runner,
            "validate_prepared_job",
            return_value=(job, runner_selection, directory),
        ):
            with self.assertRaisesRegex(v5.TuneV5PipelineError, "binding changed"):
                v5.prepare_case(case, root=root)

    def test_model_map_rejects_compositor_or_null_prompt(self) -> None:
        case = {"case_id": "01#02", "selected_model_ids": ["alibaba/wan-2.2"]}
        bad = {
            "models": [
                {
                    "model_id": "alibaba/wan-2.2",
                    "execution_mode": "deterministic-compositor",
                    "positive_prompt": None,
                    "negative_prompt": None,
                }
            ]
        }
        with self.assertRaisesRegex(v5.TuneV5PipelineError, "forbids compositor"):
            v5._model_map(copy.deepcopy(bad), case)  # noqa: SLF001

    def test_floor_plan_published_prompts_require_numeric_four_percent_cap(self) -> None:
        case = {
            "case_id": "03#09",
            "selected_model_ids": ["alibaba/wan-2.2", "google/veo-3.1-lite"],
        }
        def result(prompt: str) -> dict:
            return {
                "models": [
                    {
                        "model_id": model_id,
                        "execution_mode": "i2v",
                        "positive_prompt": prompt,
                        "negative_prompt": None,
                    }
                    for model_id in case["selected_model_ids"]
                ]
            }

        with self.assertRaisesRegex(v5.TuneV5PipelineError, "numeric motion cap"):
            v5._model_map(  # noqa: SLF001
                result("Keep the complete plan visible with a very small camera move."),
                case,
            )
        phrase = v5.REQUIRED_POSITIVE_PROMPT_PHRASES["03#09"]
        published = v5._model_map(  # noqa: SLF001
            result(f"Keep the complete plan visible, with {phrase}."),
            case,
        )
        self.assertTrue(
            all(phrase in value["positive_prompt"] for value in published.values())
        )


if __name__ == "__main__":
    unittest.main()
