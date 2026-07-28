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
    include_smooth: bool = False,
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
    if include_loop or include_smooth:
        for variant in finalizer.loop_experiment.VARIANTS:
            _copy_path(
                ROOT,
                root,
                finalizer.case21.ARTIFACT_NAMESPACE / variant.planning_run_id,
            )
        _copy_path(ROOT, root, finalizer.loop_experiment.EXPERIMENT_ROOT)
    if include_smooth:
        for variant in finalizer.smooth_experiment.VARIANTS:
            _copy_path(
                ROOT,
                root,
                finalizer.case21.ARTIFACT_NAMESPACE / variant.planning_run_id,
            )
        _copy_path(ROOT, root, finalizer.smooth_experiment.EXPERIMENT_ROOT)
        _copy_path(
            ROOT,
            root,
            finalizer.case21.ARTIFACT_NAMESPACE
            / finalizer.smooth_retry.PLANNING_RUN_ID,
        )
        _copy_path(ROOT, root, finalizer.smooth_retry.RETRY_ROOT)
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
        legacy.pop("smooth_experiment", None)

        document = finalizer.build_manifest(
            root=root,
            updated_at=legacy["updated_at"],
        )

        self.assertNotIn("loop_experiment", document)
        self.assertEqual(document, legacy)

    def test_failure_aware_counts_and_showcase_compatible_shape(self) -> None:
        fixture = make_fixture(include_loop=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        document = finalizer.build_manifest(
            root=root,
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
        self.assertTrue(root.joinpath(image_record["image"]["source_path"]).is_file())

        self.assertEqual(
            [output["model_id"] for output in document["outputs"]],
            list(finalizer.case21.MODEL_IDS),
        )
        self.assertEqual(len({output["video_path"] for output in document["outputs"]}), 3)
        self.assertEqual(len(document["research_outputs"]), 4)
        display_outputs = document["outputs"] + document["research_outputs"]
        self.assertEqual(len({output["video_path"] for output in display_outputs}), 7)
        for output in display_outputs:
            video = root / output["video_path"]
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
        fixture = make_fixture(include_loop=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        document = finalizer.build_manifest(
            root=root,
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
            self.assertTrue((root / output["video_path"]).is_file())
            closure = output["loop_closure"]
            for digest_key in (
                "request_sha256",
                "prompt_sha256",
                "run_sha256",
                "video_sha256",
                "review_sha256",
            ):
                self.assertEqual(len(closure[digest_key]), 64)

    def test_absent_smooth_preserves_existing_loop_sidecar_exactly(self) -> None:
        fixture = make_fixture(include_loop=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        expected = json.loads(
            (ROOT / finalizer.FINAL_MANIFEST_PATH).read_text(encoding="utf-8")
        )
        expected.pop("smooth_experiment", None)

        document = finalizer.build_manifest(
            root=root,
            updated_at=expected["updated_at"],
        )

        self.assertNotIn("smooth_experiment", document)
        self.assertEqual(document, expected)

    def test_completed_smooth_experiment_requires_proxy_review(self) -> None:
        fixture = make_fixture(include_smooth=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        review_path = root / finalizer.SMOOTH_REVIEW_PATH
        review_path.unlink(missing_ok=True)

        with self.assertRaisesRegex(
            finalizer.FinalizeError,
            "Completed smooth MP4s require",
        ):
            finalizer.build_manifest(
                root=root,
                updated_at="2026-07-28T17:30:00Z",
            )

    def test_completed_smooth_experiment_keeps_five_attempts_and_four_outputs(
        self,
    ) -> None:
        fixture = make_fixture(include_smooth=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        _write_smooth_review(root)

        document = finalizer.build_manifest(
            root=root,
            updated_at="2026-07-28T17:30:00Z",
        )

        self.assertEqual(len(document["outputs"]), 3)
        self.assertEqual(len(document["research_outputs"]), 4)
        self.assertEqual(len(document["attempt_history"]), 11)
        self.assertEqual(document["loop_experiment"]["attempt_count"], 8)
        self.assertEqual(document["loop_experiment"]["available_output_count"], 8)
        smooth = document["smooth_experiment"]
        self.assertEqual(smooth["model_id"], "alibaba/wan-2.7")
        self.assertEqual(smooth["attempt_count"], 5)
        self.assertEqual(smooth["available_attempt_count"], 5)
        self.assertEqual(smooth["attempts_without_video_count"], 0)
        self.assertEqual(smooth["available_output_count"], 4)
        self.assertEqual(smooth["display_output_count"], 4)
        self.assertEqual(smooth["excluded_from_demo_count"], 1)
        self.assertEqual(len(smooth["attempt_history"]), 5)
        self.assertEqual(len(smooth["outputs"]), 4)
        self.assertEqual(smooth["cost"]["operator_budget_cap_usd"], 3.0)
        self.assertEqual(smooth["cost"]["reserved_usd"], 2.5)
        contract = smooth["request_contract"]
        self.assertEqual(
            contract["classification"], "non-loop-smooth-motion-experiment"
        )
        self.assertTrue(contract["verified_lite_planning"])
        self.assertTrue(contract["canonical_lite_runtime"])
        self.assertEqual(contract["frame_types"], ["first_frame"])
        self.assertFalse(contract["last_frame_is_source"])
        self.assertIsNone(contract["last_frame_url"])
        self.assertFalse(contract["provider_native_loop_parameter"])
        self.assertFalse(contract["browser_playback_loop"])

        attempts = {
            attempt["variant_id"]: attempt for attempt in smooth["attempt_history"]
        }
        initial = attempts[finalizer.SMOOTH_REPLACED_VARIANT_ID]
        retry = attempts[finalizer.SMOOTH_RETRY_VARIANT_ID]
        self.assertTrue(
            all(
                isinstance(attempt["selected_for_demo"], bool)
                for attempt in attempts.values()
            )
        )
        self.assertTrue(initial["available_video"])
        self.assertFalse(initial["selected_for_demo"])
        self.assertFalse(initial["selected_for_display"])
        self.assertEqual(initial["human_review"]["status"], "excluded")
        self.assertEqual(
            initial["human_review"]["reason_code"], "object-substitution"
        )
        self.assertTrue(retry["available_video"])
        self.assertTrue(retry["selected_for_demo"])
        self.assertTrue(retry["selected_for_display"])
        self.assertEqual(retry["retry_of"], initial["provider_run_id"])
        self.assertEqual(retry["supersedes_for_demo"], initial["provider_run_id"])
        self.assertNotIn(
            finalizer.SMOOTH_REPLACED_VARIANT_ID,
            {output["selection"]["variant_id"] for output in smooth["outputs"]},
        )
        self.assertIn(
            finalizer.SMOOTH_RETRY_VARIANT_ID,
            {output["selection"]["variant_id"] for output in smooth["outputs"]},
        )
        featured = smooth["featured_review"]
        self.assertEqual(
            featured["schema_version"],
            finalizer.SMOOTH_FEATURED_REVIEW_SCHEMA_VERSION,
        )
        self.assertEqual(featured["status"], "visual-winner")
        self.assertEqual(featured["label"], "Визуальный победитель")
        self.assertEqual(featured["variant_id"], finalizer.SMOOTH_RETRY_VARIANT_ID)
        self.assertEqual(featured["provider_run_id"], retry["provider_run_id"])
        self.assertEqual(
            featured["selection_basis"],
            "operator-visual-review-not-proxy-rank",
        )
        self.assertTrue(featured["summary"].strip())
        self.assertTrue(featured["prompt_distinction"].strip())
        self.assertEqual(
            featured["evidence"],
            {
                "analysis_status": "measured",
                "regions_with_detected_motion": 7,
                "requested_region_count": 7,
                "abrupt_transition_count": 0,
                "motion_energy_spike_count": 0,
                "proxy_rank": 2,
                "proxy_rank_scale": 5,
            },
        )
        self.assertEqual(
            [practice["id"] for practice in featured["practices"]],
            [practice["id"] for practice in finalizer.SMOOTH_FEATURED_PRACTICES],
        )
        self.assertTrue(
            all(
                practice["title"].strip() and practice["description"].strip()
                for practice in featured["practices"]
            )
        )
        self.assertEqual(
            {attempt["provider_run_id"] for attempt in smooth["attempt_history"]},
            {
                finalizer.smooth_experiment._provider_run_id(entry)  # noqa: SLF001
                for entry in finalizer.smooth_experiment.ENTRIES
            }
            | {finalizer.smooth_retry._provider_run_id()},  # noqa: SLF001
        )
        for output in smooth["outputs"]:
            self.assertTrue((root / output["video_path"]).is_file())
            self.assertFalse(output["accepted"])
            self.assertEqual(output["visual_review"]["status"], "accepted-for-demo")
            motion = output["smooth_motion"]
            self.assertEqual(motion["frame_types"], ["first_frame"])
            self.assertIsNone(motion["last_frame_url"])
            self.assertFalse(motion["last_frame_is_source"])
            self.assertFalse(motion["provider_native_loop_parameter"])
            self.assertFalse(motion["browser_playback_loop"])
            for digest_key in (
                "request_sha256",
                "prompt_sha256",
                "run_sha256",
                "video_sha256",
                "review_sha256",
            ):
                self.assertEqual(len(motion[digest_key]), 64)

    def test_smooth_receipt_request_video_selection_and_review_tamper_fail_closed(
        self,
    ) -> None:
        fixture = make_fixture(include_smooth=True)
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        _write_smooth_review(root)
        variant = finalizer.smooth_experiment.VARIANTS[0]
        entry = finalizer.smooth_experiment.ENTRY_BY_VARIANT[variant.variant_id]
        paths = finalizer.smooth_experiment.artifact_paths(entry, root)

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
            "last-frame": (
                paths["run"],
                lambda path: _tamper_smooth_last_frame(path),
            ),
            "loop-field": (
                paths["run"],
                lambda path: _tamper_smooth_loop(path),
            ),
            "request-fingerprint": (
                paths["run"],
                lambda path: _rewrite_json_key(path, "request_sha256", "0" * 64),
            ),
            "video": (
                paths["video"],
                lambda path: path.write_bytes(path.read_bytes() + b"tamper"),
            ),
            "selection": (
                root / finalizer.smooth_experiment.EXPERIMENT_MANIFEST_PATH,
                lambda path: _tamper_smooth_selection(path),
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
                            updated_at="2026-07-28T17:30:00Z",
                        )
                finally:
                    path.write_bytes(original)

        document = finalizer.finalize(root)
        self.assertIn("smooth_experiment", document)
        review_path = root / finalizer.SMOOTH_REVIEW_PATH
        report = json.loads(review_path.read_text(encoding="utf-8"))
        report["videos"][0]["motion_coverage"]["coverage_ratio"] = 0.0
        _rewrite_json(review_path, report)
        with self.assertRaisesRegex(
            finalizer.FinalizeError,
            "Smooth review",
        ):
            finalizer.verify(root)

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
        fixture = make_fixture()
        self.addCleanup(fixture.cleanup)
        root = Path(fixture.name)
        document = finalizer.build_manifest(
            root=root,
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


def _tamper_smooth_last_frame(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    first = copy.deepcopy(value["request"]["frame_images"][0])
    first["frame_type"] = "last_frame"
    value["request"]["frame_images"].append(first)
    _rewrite_json(path, value)


def _tamper_smooth_loop(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["request"]["loop"] = True
    _rewrite_json(path, value)


def _tamper_smooth_selection(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["outputs"][0]["selected_for_demo"] = False
    _rewrite_json(path, value)


def _rewrite_json_key(path: Path, key: str, replacement: object) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value[key] = replacement
    _rewrite_json(path, value)


def _temporal_proxy(seed: int) -> dict[str, object]:
    ratio = round(seed / 1000, 8)
    distribution = {
        "mean": 1.0 + seed,
        "median": 1.0,
        "p90": 2.0,
        "p95": 2.5,
        "max": 3.0,
        "mad": 0.5,
    }
    return {
        "transition_count": 149,
        "motion_energy_mae_rgb": {
            **distribution,
            "spike_threshold": 4.0,
            "spike_count": seed,
            "spike_ratio": ratio,
            "spike_frame_indices": list(range(1, seed + 1)),
        },
        "acceleration_proxy_mae_rgb": {
            **distribution,
            "sample_count": 148,
            "abrupt_threshold": 4.0,
            "abrupt_transition_count": seed,
            "abrupt_transition_ratio": ratio,
            "abrupt_frame_indices": list(range(2, seed + 2)),
            "normalized_p95_by_motion_p95": 1.0 + ratio,
        },
    }


def _write_smooth_review(root: Path) -> None:
    videos = []
    ranking_entries = []
    inputs = [
        (
            variant.variant_id,
            finalizer.smooth_experiment.ENTRY_BY_VARIANT[variant.variant_id],
            finalizer.smooth_experiment.artifact_paths(
                finalizer.smooth_experiment.ENTRY_BY_VARIANT[variant.variant_id],
                root,
            ),
        )
        for variant in finalizer.smooth_experiment.VARIANTS
    ]
    inputs.append(
        (
            finalizer.SMOOTH_RETRY_VARIANT_ID,
            finalizer.smooth_retry.ENTRY,
            finalizer.smooth_retry.artifact_paths(
                finalizer.smooth_retry.ENTRY,
                root,
            ),
        )
    )
    proxy_ranks = (1, 3, 4, 5, 2)
    for attempt_index, (variant_id, _entry, paths) in enumerate(inputs):
        rank = proxy_ranks[attempt_index]
        run = json.loads(paths["run"].read_text(encoding="utf-8"))
        run_media = run["media"]
        temporal = _temporal_proxy(
            0 if variant_id == finalizer.SMOOTH_RETRY_VARIANT_ID else rank
        )
        collateral_temporal = _temporal_proxy(rank + 1)
        regions = [
            {
                "region_id": region_id,
                "detected_motion": True,
                "temporal_smoothness": copy.deepcopy(temporal),
            }
            for region_id in finalizer.SMOOTH_REGION_IDS
        ]
        motion_coverage = {
            "requested_region_count": len(finalizer.SMOOTH_REGION_IDS),
            "regions_with_detected_motion": len(finalizer.SMOOTH_REGION_IDS),
            "coverage_ratio": 1.0,
            "missing_motion_regions": [],
        }
        collateral = {
            "outside_requested_region_pixel_count": 1,
            "max_mae_rgb_from_first": float(rank),
            "max_changed_pixel_ratio_from_first": round(rank / 100, 8),
            "temporal_smoothness": collateral_temporal,
        }
        videos.append(
            {
                "video_id": variant_id,
                "path": paths["video"].relative_to(root).as_posix(),
                "sha256": finalizer.sha256_file(paths["video"]),
                "analysis_status": "measured",
                "media": {
                    "width": run_media["width"],
                    "height": run_media["height"],
                    "frame_rate": str(run_media["fps"]),
                    "frame_count": run_media["frames"],
                    "duration_seconds": run_media["duration_seconds"],
                    "container": run_media["container"],
                    "codec": run_media["codec"],
                    "pixel_format": "yuv420p",
                    "has_audio": run_media["has_audio"],
                    "bytes": run_media["bytes"],
                },
                "frame_analysis": {
                    "decoded_frame_count": run_media["frames"],
                    "normalized_width": 96,
                    "normalized_height": 96,
                    "coverage_frame_indices": [0, run_media["frames"] - 1],
                    "coverage_timestamps_seconds": [
                        0.0,
                        run_media["duration_seconds"],
                    ],
                },
                "motion_coverage": motion_coverage,
                "regions": regions,
                "requested_union_smoothness": temporal,
                "collateral_activity": collateral,
                "square_output": True,
                "proxy_rank": rank,
            }
        )
        ranking_entries.append(
            {
                "rank": rank,
                "video_id": variant_id,
                "regions_with_detected_motion": motion_coverage[
                    "regions_with_detected_motion"
                ],
                "coverage_ratio": motion_coverage["coverage_ratio"],
                "abrupt_transition_count": temporal[
                    "acceleration_proxy_mae_rgb"
                ]["abrupt_transition_count"],
                "abrupt_transition_ratio": temporal[
                    "acceleration_proxy_mae_rgb"
                ]["abrupt_transition_ratio"],
                "motion_energy_spike_count": temporal[
                    "motion_energy_mae_rgb"
                ]["spike_count"],
                "motion_energy_spike_ratio": temporal[
                    "motion_energy_mae_rgb"
                ]["spike_ratio"],
                "normalized_acceleration_p95": temporal[
                    "acceleration_proxy_mae_rgb"
                ]["normalized_p95_by_motion_p95"],
                "collateral_max_changed_pixel_ratio_from_first": collateral[
                    "max_changed_pixel_ratio_from_first"
                ],
            }
        )
    report = {
        "schema_version": finalizer.SMOOTH_REVIEW_SCHEMA_VERSION,
        "case": {
            "article_number": "21",
            "article_slug": finalizer.case21.ARTICLE_SLUG,
            "image_id": finalizer.case21.IMAGE_ID,
            "model_id": finalizer.smooth_experiment.MODEL_ID,
            "experiment_id": finalizer.smooth_experiment.EXPERIMENT_ID,
        },
        "analyzer": {
            "script": "scripts/analyze_clipmaker_lite_case21_smooth.py",
            "analysis_version": 1,
        },
        "method": {
            "temporal_sampling": {},
            "coverage_sampling": {},
            "jerkiness_proxies": {},
            "collateral_thresholds": {},
            "requested_regions": [
                {"region_id": region_id}
                for region_id in finalizer.SMOOTH_REGION_IDS
            ],
        },
        "video_count": len(videos),
        "ranking": {
            "method": (
                "coverage-desc-then-abrupt-acceleration-spikes-collateral-asc"
            ),
            "entries": ranking_entries,
        },
        "videos": videos,
        "limitations": ["Proxy-only fixture; no semantic acceptance."],
    }
    _rewrite_json(root / finalizer.SMOOTH_REVIEW_PATH, report)


def _tamper_review(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    value["verdict"]["status"] = "fidelity-passed"
    _rewrite_json(path, value)


if __name__ == "__main__":
    unittest.main()
