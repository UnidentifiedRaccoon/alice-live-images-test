import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_case21_research_finalize as finalizer


ROOT = Path(__file__).resolve().parents[1]


def _copy_path(source_root: Path, destination_root: Path, relative: Path) -> None:
    source = source_root / relative
    destination = destination_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def make_fixture(
    *,
    include_loop: bool = False,
) -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    paths = (
        Path("PROMOPAGES-9857/articles/manifest.csv"),
        Path("PROMOPAGES-9857/articles/21-maier-doctor-zolotoe-vremia"),
        Path("PROMOPAGES-9884/articles/21-maier-doctor-zolotoe-vremia"),
        Path("docs/agents/clipmaker-lite"),
        Path("scripts/clipmaker_lite_runner.py"),
        Path("artifacts/clipmaker-lite/v1/promopages-9930-case21-maier-20260727-v4"),
        Path(
            "artifacts/clipmaker-lite/v1/"
            "promopages-9930-case21-erosion-negative-20260727-v1"
        ),
        Path(
            "artifacts/clipmaker-lite/v1/"
            "promopages-9930-case21-veo-motion-only-20260727-v1"
        ),
        Path(
            "artifacts/clipmaker-lite/v1/"
            "promopages-9930-case21-monotonic-positive-20260727-v1"
        ),
        Path(
            "artifacts/clipmaker-lite/v1/"
            "promopages-9930-case21-opacity-only-20260727-v1"
        ),
        finalizer.CONTROLS["primary"].path,
        finalizer.CONTROLS["retry"].path,
        finalizer.CONTROLS["stage1_generation_core"].path,
        finalizer.CONTROLS["stage2_generation_core"].path,
    )
    for relative in paths:
        _copy_path(ROOT, root, relative)
    if include_loop:
        for variant in finalizer.loop_experiment.VARIANTS:
            _copy_path(
                ROOT,
                root,
                finalizer.case21.ARTIFACT_NAMESPACE / variant.planning_run_id,
            )
        _copy_path(ROOT, root, finalizer.loop_experiment.EXPERIMENT_ROOT)
    return temporary


class Case21ResearchFinalizeTest(unittest.TestCase):
    def test_absent_loop_manifest_preserves_legacy_sidecar_exactly(self) -> None:
        fixture = make_fixture()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        legacy = json.loads(
            (ROOT / finalizer.FINAL_MANIFEST_PATH).read_text(encoding="utf-8")
        )
        legacy.pop("loop_experiment", None)

        document = finalizer.build_manifest(
            root=root,
            updated_at=legacy["updated_at"],
        )

        self.assertNotIn("loop_experiment", document)
        self.assertEqual(document, legacy)

    def test_failure_aware_counts_and_showcase_compatible_shape(self) -> None:
        document = finalizer.build_manifest(
            root=ROOT,
            updated_at="2026-07-27T18:00:00Z",
        )

        self.assertEqual(document["manifest_role"], "case-21-extension")
        self.assertEqual(document["agent_id"], "clipmaker-lite")
        self.assertEqual(document["models"], list(finalizer.case21.MODEL_IDS))
        self.assertEqual(document["article_count"], 1)
        self.assertEqual(document["image_count"], 1)
        self.assertEqual(document["expected_outputs"], 3)
        self.assertEqual(document["canonical_output_count"], 3)
        self.assertEqual(document["research_output_count"], 4)
        self.assertEqual(document["display_output_count"], 7)
        self.assertEqual(document["attempt_count"], 11)
        self.assertEqual(document["attempts_without_video_count"], 4)
        self.assertEqual(document["available_output_count"], 7)
        self.assertEqual(document["accepted_output_count"], 0)
        self.assertEqual(document["rejected_output_count"], 7)
        self.assertEqual(document["visual_fidelity_passed_count"], 0)
        self.assertEqual(document["visual_fidelity_failed_count"], 7)
        self.assertEqual(document["cost"]["reserved_aggregate_usd"], 2.7)
        self.assertEqual(document["cost"]["operator_budget_cap_usd"], 3.0)
        self.assertFalse(document["cost"]["actual_billing_available"])

        article = document["articles"][0]
        self.assertEqual(article["article_number"], "21")
        self.assertEqual(len(article["images"]), 1)
        image_record = article["images"][0]
        self.assertEqual(image_record["image"]["delivery"], "repository-raw")
        self.assertEqual(image_record["outputs"], document["outputs"])
        self.assertEqual(
            image_record["research_outputs"], document["research_outputs"]
        )
        self.assertTrue(ROOT.joinpath(image_record["image"]["source_path"]).is_file())

        self.assertEqual(
            [output["model_id"] for output in document["outputs"]],
            list(finalizer.case21.MODEL_IDS),
        )
        self.assertEqual(len({output["video_path"] for output in document["outputs"]}), 3)
        self.assertEqual(len(document["research_outputs"]), 4)
        display_outputs = document["outputs"] + document["research_outputs"]
        self.assertEqual(len({output["video_path"] for output in display_outputs}), 7)
        for output in display_outputs:
            video = ROOT / output["video_path"]
            self.assertTrue(video.is_file())
            self.assertEqual(video.stat().st_size, output["media"]["bytes"])
            self.assertEqual(output["delivery"], "repository-raw")
            self.assertTrue(output["available"])
            self.assertFalse(output["accepted"])
            self.assertEqual(
                output["acceptance_status"], "rejected-visual-fidelity"
            )
            self.assertEqual(
                output["visual_review"]["status"], "fidelity-failed"
            )
            self.assertNotIn("fallback", output["route"])

    def test_completed_loop_experiment_is_separate_and_fully_bound(self) -> None:
        document = finalizer.build_manifest(
            root=ROOT,
            updated_at="2026-07-28T12:40:00Z",
        )

        self.assertEqual(len(document["outputs"]), 3)
        self.assertEqual(len(document["research_outputs"]), 4)
        self.assertEqual(len(document["attempt_history"]), 11)
        loop = document["loop_experiment"]
        self.assertEqual(loop["model_id"], "alibaba/wan-2.7")
        self.assertEqual(loop["attempt_count"], 8)
        self.assertEqual(loop["available_output_count"], 8)
        self.assertEqual(loop["attempts_without_video_count"], 0)
        self.assertEqual(len(loop["attempt_history"]), 8)
        self.assertEqual(len(loop["outputs"]), 8)
        self.assertEqual(loop["cost"]["operator_budget_cap_usd"], 5.0)
        self.assertEqual(loop["cost"]["reserved_usd"], 4.0)
        contract = loop["request_contract"]
        self.assertEqual(
            contract["classification"], "api-loop-closure-experiment"
        )
        self.assertTrue(contract["verified_lite_planning"])
        self.assertFalse(contract["canonical_lite_runtime"])
        self.assertEqual(
            contract["request_mechanism"],
            "same-source-first-and-last-frame",
        )
        self.assertEqual(
            contract["first_frame_url"], contract["last_frame_url"]
        )
        self.assertEqual(contract["frame_types"], ["first_frame", "last_frame"])
        self.assertFalse(contract["provider_native_loop_parameter"])
        self.assertTrue(contract["browser_playback_loop"])
        self.assertTrue(
            all(
                output["loop_closure"]["seam_review"]["status"]
                == "seam-failed"
                for output in loop["outputs"]
            )
        )
        self.assertEqual(
            {attempt["provider_run_id"] for attempt in loop["attempt_history"]},
            {output["provider_run_id"] for output in loop["outputs"]},
        )
        for output in loop["outputs"]:
            self.assertTrue((ROOT / output["video_path"]).is_file())
            closure = output["loop_closure"]
            for digest_key in (
                "request_sha256",
                "prompt_sha256",
                "run_sha256",
                "video_sha256",
                "review_sha256",
            ):
                self.assertEqual(len(closure[digest_key]), 64)

    def test_loop_receipt_endpoint_video_and_review_tamper_fail_closed(self) -> None:
        fixture = make_fixture(include_loop=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        variant = finalizer.loop_experiment.VARIANTS[0]
        entry = finalizer.loop_experiment.ENTRY_BY_VARIANT[variant.variant_id]
        paths = finalizer.loop_experiment.artifact_paths(entry, root)

        mutations = {
            "planning-result": (
                root
                / finalizer.case21.ARTIFACT_NAMESPACE
                / variant.planning_run_id
                / "result.json",
                lambda path: path.write_bytes(path.read_bytes() + b"\n"),
            ),
            "prompt": (
                paths["prompt"],
                lambda path: _rewrite_nested_prompt(path),
            ),
            "first-frame-endpoint": (
                paths["run"],
                lambda path: _tamper_loop_endpoint(path),
            ),
            "request-fingerprint": (
                paths["run"],
                lambda path: _rewrite_json_key(path, "request_sha256", "0" * 64),
            ),
            "video": (
                paths["video"],
                lambda path: path.write_bytes(path.read_bytes() + b"tamper"),
            ),
        }
        for label, (path, mutate) in mutations.items():
            with self.subTest(label=label):
                original = path.read_bytes()
                try:
                    mutate(path)
                    with self.assertRaises(Exception):
                        finalizer.build_manifest(
                            root=root,
                            updated_at="2026-07-28T12:40:00Z",
                        )
                finally:
                    path.write_bytes(original)

        document = finalizer.finalize(root)
        review_path = root / finalizer.LOOP_REVIEW_PATH
        report = json.loads(review_path.read_text(encoding="utf-8"))
        report["videos"][0]["seam"]["failed_checks"].append("tampered")
        _rewrite_json(review_path, report)
        with self.assertRaisesRegex(
            finalizer.FinalizeError,
            "differs from exact reconstruction",
        ):
            finalizer.verify(root)

    def test_attempt_history_labels_experiments_without_fallback_semantics(self) -> None:
        document = finalizer.build_manifest(
            root=ROOT,
            updated_at="2026-07-27T18:00:00Z",
        )
        history = document["attempt_history"]

        self.assertEqual(len(history), 11)
        experiments = [
            attempt
            for attempt in history
            if attempt["activity"] == "prompt-experiment"
        ]
        self.assertEqual(len(experiments), 6)
        self.assertEqual(
            {attempt["experiment_id"] for attempt in experiments},
            {finalizer.STAGE1_EXPERIMENT_ID, finalizer.STAGE2_EXPERIMENT_ID},
        )
        self.assertEqual(sum(item["available_video"] for item in history), 7)
        self.assertEqual(sum(item["selected_for_display"] for item in history), 7)
        self.assertEqual(
            sum(item["selected_for_primary_display"] for item in history), 3
        )
        self.assertFalse(any(item["selected_for_acceptance"] for item in history))
        self.assertTrue(
            all("fallback" not in key for attempt in history for key in attempt)
        )

    def test_preview_is_local_and_does_not_write_sidecar(self) -> None:
        fixture = make_fixture()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        destination = root / finalizer.FINAL_MANIFEST_PATH
        with (
            mock.patch.object(
                finalizer.transport,
                "http_json",
                side_effect=AssertionError("network must not be called"),
            ),
            mock.patch.object(
                finalizer.transport,
                "http_download",
                side_effect=AssertionError("network must not be called"),
            ),
            mock.patch.object(
                finalizer.transport,
                "wan_generate",
                side_effect=AssertionError("network must not be called"),
            ),
        ):
            document = finalizer.build_manifest(
                root=root,
                updated_at="2026-07-27T18:00:00Z",
            )
        self.assertEqual(document["available_output_count"], 7)
        self.assertFalse(destination.exists())

    def test_finalize_writes_one_sidecar_and_verify_reconstructs_it(self) -> None:
        fixture = make_fixture()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)

        document = finalizer.finalize(root)
        destination = root / finalizer.FINAL_MANIFEST_PATH
        self.assertTrue(destination.is_file())
        self.assertEqual(
            json.loads(destination.read_text(encoding="utf-8")),
            document,
        )
        self.assertEqual(finalizer.verify(root), document)

    def test_fails_closed_on_source_context_result_run_video_or_review_tamper(
        self,
    ) -> None:
        mutations = {
            "source": (
                finalizer.case21.SOURCE_PATH,
                lambda path: path.write_bytes(path.read_bytes() + b"tamper"),
            ),
            "context": (
                finalizer.case21.CONTEXT_PATH,
                lambda path: path.write_text(
                    path.read_text(encoding="utf-8") + "\n",
                    encoding="utf-8",
                ),
            ),
            "result": (
                finalizer.case21.ARTIFACT_NAMESPACE
                / "promopages-9930-case21-veo-motion-only-20260727-v1"
                / "result.json",
                lambda path: _rewrite_json(path, {"schema_version": 999}),
            ),
            "run-request": (
                finalizer.DISPLAY_SELECTIONS[1].run_path,
                lambda path: _tamper_run_request(path),
            ),
            "video": (
                finalizer.DISPLAY_SELECTIONS[2].video_path,
                lambda path: path.write_bytes(path.read_bytes() + b"tamper"),
            ),
            "review": (
                finalizer.DISPLAY_SELECTIONS[1].review_path,
                lambda path: _tamper_review(path),
            ),
            "research-video": (
                finalizer.RESEARCH_SELECTIONS[2].video_path,
                lambda path: path.write_bytes(path.read_bytes() + b"tamper"),
            ),
            "research-review": (
                finalizer.RESEARCH_SELECTIONS[3].review_path,
                lambda path: _tamper_review(path),
            ),
        }
        for label, (relative, mutate) in mutations.items():
            with self.subTest(label=label):
                fixture = make_fixture()
                try:
                    root = Path(fixture.name)
                    mutate(root / relative)
                    with self.assertRaises(Exception):
                        finalizer.build_manifest(
                            root=root,
                            updated_at="2026-07-27T18:00:00Z",
                        )
                finally:
                    fixture.cleanup()

    def test_control_tree_tamper_is_rejected(self) -> None:
        fixture = make_fixture()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        unexpected = (
            root
            / finalizer.CONTROLS["stage2_generation_core"].path
            / "unexpected.txt"
        )
        unexpected.write_text("tamper", encoding="utf-8")

        with self.assertRaisesRegex(
            finalizer.FinalizeError,
            "control digests changed",
        ):
            finalizer.build_manifest(
                root=root,
                updated_at="2026-07-27T18:00:00Z",
            )

    def test_manifest_tamper_is_rejected_by_verify(self) -> None:
        fixture = make_fixture()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        document = finalizer.finalize(root)
        tampered = copy.deepcopy(document)
        tampered["accepted_output_count"] = 3
        finalizer.transport.atomic_write_json(
            root / finalizer.FINAL_MANIFEST_PATH,
            tampered,
        )

        with self.assertRaisesRegex(
            finalizer.FinalizeError,
            "differs from exact reconstruction",
        ):
            finalizer.verify(root)


def _rewrite_json(path: Path, replacement: object) -> None:
    path.write_text(
        json.dumps(replacement, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _tamper_run_request(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    request = value["request"]
    if "prompt" in request:
        request["prompt"] += " tamper"
    else:
        request["input"]["prompt"] += " tamper"
    _rewrite_json(path, value)


def _rewrite_nested_prompt(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["prompt"]["positive"] += " tamper"
    _rewrite_json(path, value)


def _tamper_loop_endpoint(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["request"]["frame_images"][0]["image_url"]["url"] += "?tamper=1"
    _rewrite_json(path, value)


def _rewrite_json_key(path: Path, key: str, replacement: object) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value[key] = replacement
    _rewrite_json(path, value)


def _tamper_review(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["verdict"]["status"] = "fidelity-passed"
    _rewrite_json(path, value)


if __name__ == "__main__":
    unittest.main()
