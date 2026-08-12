#!/usr/bin/env python3
"""Focused tests for the isolated Clipmaker Lite provenance boundary."""

from __future__ import annotations

import json
import inspect
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_runner as runner


class ClipmakerLiteRunnerTest(unittest.TestCase):
    def test_output_schema_const_fields_declare_json_types(self) -> None:
        schema = runner.draft_output_schema("schema-check", ["alibaba/wan-2.7"])

        self.assertEqual(
            schema["properties"]["schema_version"],
            {"type": "integer", "const": runner.DRAFT_SCHEMA_VERSION},
        )
        self.assertEqual(
            schema["properties"]["job_id"],
            {"type": "string", "const": "schema-check"},
        )
        self.assertNotIn("base_scene", schema["properties"])
        self.assertEqual(
            schema["properties"]["structured_intent"]["required"],
            list(runner.STRUCTURED_INTENT_KEYS),
        )
        model_schema = schema["properties"]["models"]["items"]
        self.assertEqual(
            model_schema["properties"]["negative_prompt"],
            {"type": "null"},
        )
        self.assertEqual(
            model_schema["properties"]["execution_mode"],
            {"type": "string", "const": "i2v"},
        )
        self.assertEqual(
            model_schema["properties"]["positive_prompt"],
            {"type": "string", "minLength": 1, "maxLength": 500},
        )

    def make_workspace(self, directory: str) -> tuple[Path, Path, Path]:
        root = Path(directory)
        script = root / runner.RUNNER_PATH
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(runner.__file__), script)

        lite = root / "docs/agents/clipmaker-lite"
        models = lite / "models"
        models.mkdir(parents=True)
        readme = lite / "README.md"
        wan22 = models / "alibaba-wan-2.2.md"
        wan = models / "alibaba-wan-2.7.md"
        veo = models / "google-veo-3.1-lite.md"
        readme.write_text("Lite base instruction.\n", encoding="utf-8")
        wan22.write_text("Wan 2.2 five-second Segmind instruction.\n", encoding="utf-8")
        wan.write_text("Wan five-second instruction.\n", encoding="utf-8")
        veo.write_text("Veo four-second instruction.\n", encoding="utf-8")

        image_article = root / "PROMOPAGES-9857/articles/01-article"
        image_article.mkdir(parents=True)
        image = image_article / "02.jpeg"
        image.write_bytes(b"test-image")
        context_article = root / "PROMOPAGES-9884/articles/01-article"
        context_article.mkdir(parents=True)
        context = context_article / "content.json"
        context.write_text(
            json.dumps(
                {
                    "article_id": "01-article",
                    "title": "Article title",
                    "lead": "Article lead",
                    "blocks": [
                        {"type": "paragraph", "text": "Before"},
                        {
                            "type": "image",
                            "image_id": "02",
                            "file": "02.jpeg",
                            "manifest_file_path": "articles/01-article/02.jpeg",
                            "role": "article_image",
                            "caption": "Caption",
                        },
                        {"type": "paragraph", "text": "After"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        contract = {
            "schema_version": 1,
            "agent_id": runner.AGENT_ID,
            "contract_version": "1.0.0-test",
            "loader_version": 1,
            "runner": {
                "runner_id": runner.RUNNER_ID,
                "runner_version": runner.RUNNER_VERSION,
                "path": runner.RUNNER_PATH.as_posix(),
                "sha256": runner.sha256_file(script),
            },
            "execution": {
                "executor_id": "codex-exec",
                "binary": {
                    "path": "/test/codex",
                    "sha256": "1" * 64,
                    "version": "codex-test",
                },
                "sandbox": "read-only",
                "ephemeral": True,
                "ignore_user_config": True,
                "ignore_project_rules": True,
                "tool_event_policy": "reject-run",
                "requires_thread_id": True,
                "requires_explicit_external_processing": True,
            },
            "input_binding": {
                "image_root": "PROMOPAGES-9857",
                "context_root": "PROMOPAGES-9884",
                "context_filename": "content.json",
            },
            "base_instruction": {
                "path": "docs/agents/clipmaker-lite/README.md",
                "sha256": runner.sha256_file(readme),
            },
            "models": {
                "alibaba/wan-2.2": {
                    "spec_path": "docs/agents/clipmaker-lite/models/alibaba-wan-2.2.md",
                    "spec_sha256": runner.sha256_file(wan22),
                    "runtime": {
                        "duration_seconds": 5,
                        "resolution": "720p",
                        "aspect_ratios": ["source"],
                        "generate_audio": False,
                        "frame_inputs": ["first_frame"],
                        "gateway": "eliza",
                        "provider": "segmind",
                        "provider_model_id": "segmind/wan-2.2-i2v-flash",
                        "adapter": "eliza-segmind",
                        "synchronous": True,
                        "automatic_retry": False,
                        "frames": 150,
                        "fps": 30,
                        "seed": 220214,
                        "watermark": False,
                        "prompt_expansion": {
                            "parameter": "prompt_extend",
                            "value": False,
                        },
                        "negative_prompt_transport": {
                            "mode": "separate_field",
                            "parameter": "negative_prompt",
                            "null_serialization": "empty_string",
                        },
                    },
                },
                "alibaba/wan-2.7": {
                    "spec_path": "docs/agents/clipmaker-lite/models/alibaba-wan-2.7.md",
                    "spec_sha256": runner.sha256_file(wan),
                    "runtime": {
                        "duration_seconds": 5,
                        "resolution": "1080p",
                        "aspect_ratios": ["16:9", "9:16", "1:1", "4:3", "3:4"],
                        "generate_audio": False,
                        "frame_inputs": ["first_frame"],
                        "provider": "atlas-cloud",
                        "prompt_expansion": {"parameter": "prompt_extend", "value": True},
                    },
                },
                "google/veo-3.1-lite": {
                    "spec_path": "docs/agents/clipmaker-lite/models/google-veo-3.1-lite.md",
                    "spec_sha256": runner.sha256_file(veo),
                    "runtime": {
                        "duration_seconds": 4,
                        "resolution": "1080p",
                        "aspect_ratios": ["16:9", "9:16"],
                        "generate_audio": False,
                        "frame_inputs": ["first_frame"],
                        "provider": "google-vertex",
                        "prompt_expansion": {"parameter": "enhancePrompt", "value": True},
                    },
                },
            },
            "output_namespace": runner.OUTPUT_NAMESPACE.as_posix(),
        }
        (lite / "contract.json").write_text(
            json.dumps(contract, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return root, image, context

    @staticmethod
    def draft_bytes(job_id: str, model_ids: list[str]) -> bytes:
        draft = {
            "schema_version": runner.DRAFT_SCHEMA_VERSION,
            "job_id": job_id,
            "image_reading": ["A visible subject remains the compositional focus."],
            "article_context": "The image supports the nearby editorial point.",
            "structured_intent": {
                "editorial_meaning": "Support the nearby editorial point.",
                "initial_state": "The subject starts in one observable physical state.",
                "motion_owner": "The visible subject owns the primary movement.",
                "primary_action": "One visible change develops from the source frame.",
                "attention_anchor": "The visible subject stays centered and continuously visible.",
                "motion_boundary": "Motion remains inside the source-visible subject and space.",
                "terminal_state": "The change reaches an observable endpoint.",
                "geometry_invariant": "The subject keeps the same connected geometry.",
                "identity_invariant": "One subject remains one recognizable subject.",
                "semantic_invariant": "The editorial state remains unchanged through the end.",
                "feasibility_assessment": "The action and direction are visible in the source.",
                "rendering_strategy": "image-to-video",
            },
            "models": [
                {
                    "model_id": model_id,
                    "execution_mode": "i2v",
                    "scene_plan": f"A duration-aware plan for {model_id}.",
                    "positive_prompt": (
                        f"The subject completes one continuous natural movement for {model_id}."
                    ),
                    "negative_prompt": None,
                }
                for model_id in model_ids
            ],
        }
        return json.dumps(draft, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def repair_feedback(model_ids: list[str]) -> dict[str, object]:
        return {
            model_id: {
                "evaluation_id": f"evaluation-20260811::{model_id}",
                "outcome": "worse",
                "review_note": "Keep the focal product visible and do not reveal new space.",
                "evidence_strength": "explicit",
                "failure_codes": [
                    "focal_target_drift",
                    "out_of_source_reveal",
                ],
                "required_execution_mode": "i2v",
                "fallback_policy": "none",
                "camera_repair": {
                    "move": "push-in",
                    "focal_target": "the visible focal product",
                    "target_retention": "continuously-visible",
                    "max_screen_travel_percent": 4,
                    "reveal_unseen_space": False,
                },
                "preservation": {
                    "entity_counts": ["one focal product"],
                    "topology_anchors": ["the source-visible shelf edge"],
                    "rigid_regions": ["cabinet and floor"],
                    "contacts": ["product remains on its support"],
                    "must_remain_visible": ["the focal product"],
                },
            }
            for model_id in model_ids
        }

    def fake_executor(self, job_id: str, model_ids: list[str]):
        def execute(request, execution_policy, author_model, timeout):
            del timeout
            binary = execution_policy["binary"]
            return {
                "draft_bytes": self.draft_bytes(job_id, model_ids),
                "executor": {
                    "executor_id": "codex-exec",
                    "binary_path": binary["path"],
                    "binary_sha256": binary["sha256"],
                    "version": binary["version"],
                    "requested_model": author_model,
                    "thread_id": "thread-test",
                    "tool_event_count": 0,
                    "sandbox": "read-only",
                    "ephemeral": True,
                    "ignored_user_config": True,
                    "ignored_project_rules": True,
                    "attached_image_sha256": request["image_sha256"],
                    "stdout_sha256": "2" * 64,
                    "stderr_sha256": "3" * 64,
                },
            }

        return execute

    def run_with_fake(
        self,
        root: Path,
        run_id: str,
        model_ids: list[str],
        author_model: str | None = None,
    ) -> Path:
        with mock.patch.object(
            runner,
            "execute_codex_agent",
            side_effect=self.fake_executor(run_id, model_ids),
        ):
            return runner.run_agent(
                root,
                run_id,
                author_model=author_model,
                external_processing_approved=True,
            )

    def test_prepare_and_finalize_stamp_only_lite_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(root, "sample-run", image, context, image_id="02")
            job = runner.read_json(run / "job.json")
            self.assertEqual(job["producer"]["agent_id"], "clipmaker-lite")
            self.assertEqual(
                [item["model_id"] for item in job["selected_models"]],
                list(runner.SUPPORTED_MODELS),
            )
            bundle = (run / "instruction-bundle.md").read_text(encoding="utf-8")
            self.assertIn("Lite base instruction.", bundle)
            self.assertIn("Wan 2.2 five-second Segmind instruction.", bundle)
            self.assertIn("Wan five-second instruction.", bundle)
            self.assertIn("Veo four-second instruction.", bundle)
            self.assertNotIn("docs/agents/clipmaker/", bundle)

            result_path = self.run_with_fake(
                root,
                "sample-run",
                list(runner.SUPPORTED_MODELS),
                author_model="test-model",
            )
            result = runner.read_json(result_path)
            self.assertEqual(result["producer"]["agent_id"], "clipmaker-lite")
            self.assertTrue(result["producer"]["contract_fingerprint"].startswith("sha256:"))
            self.assertEqual(
                [item["runtime"]["duration_seconds"] for item in result["models"]],
                [5, 5, 4],
            )
            self.assertEqual(
                result["models"][0]["runtime"]["prompt_expansion"],
                {"parameter": "prompt_extend", "value": False},
            )
            self.assertEqual(
                result["models"][1]["runtime"]["prompt_expansion"],
                {"parameter": "prompt_extend", "value": True},
            )
            self.assertIsNone(result["models"][0]["negative_prompt"])
            self.assertEqual(
                result["analysis"]["structured_intent"]["terminal_state"],
                "The change reaches an observable endpoint.",
            )
            self.assertEqual(
                result["analysis"]["structured_intent"]["identity_invariant"],
                "One subject remains one recognizable subject.",
            )
            self.assertEqual(result["models"][0]["execution_mode"], "i2v")
            summary = runner.provenance_summary(root, "sample-run")
            self.assertTrue(summary["verified"])
            self.assertEqual(summary["agent_id"], "clipmaker-lite")
            self.assertEqual(summary["verification_scope"], "trusted-workspace-route")
            self.assertFalse(summary["cryptographically_signed"])
            receipt = runner.read_json(run / "execution.json")
            self.assertTrue(receipt["external_processing_approved"])
            self.assertEqual(receipt["executor"]["thread_id"], "thread-test")
            self.assertEqual(receipt["executor"]["binary_path"], "/test/codex")
            self.assertEqual(receipt["executor"]["requested_model"], "test-model")
            self.assertEqual(
                result["producer"]["execution"]["requested_model"],
                "test-model",
            )

    def test_cli_default_author_model_is_recorded_as_null_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(
                root,
                "default-author-model",
                image,
                context,
                image_id="02",
                model_ids=["alibaba/wan-2.7"],
            )

            result_path = self.run_with_fake(
                root,
                "default-author-model",
                ["alibaba/wan-2.7"],
            )

            receipt = runner.read_json(run / "execution.json")
            result = runner.read_json(result_path)
            self.assertIsNone(receipt["executor"]["requested_model"])
            self.assertIsNone(
                result["producer"]["execution"]["requested_model"]
            )
            self.assertTrue(
                runner.provenance_summary(root, "default-author-model")["verified"]
            )

    def test_run_requires_explicit_external_processing_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            runner.prepare_run(root, "consent-run", image, context, image_id="02")
            with mock.patch.object(runner, "execute_codex_agent") as execute:
                with self.assertRaisesRegex(runner.LiteRunnerError, "explicit"):
                    runner.run_agent(root, "consent-run")
                execute.assert_not_called()

    def test_production_run_api_has_no_injectable_executor(self) -> None:
        self.assertNotIn("executor", inspect.signature(runner.run_agent).parameters)
        self.assertFalse(hasattr(runner, "finalize_run"))

    def test_unknown_model_fails_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            with self.assertRaises(runner.LiteRunnerError):
                runner.prepare_run(root, "bad-model", image, context, model_ids=["unknown/model"])
            self.assertFalse((root / runner.OUTPUT_NAMESPACE).exists())

    def test_instruction_bundle_contains_only_selected_model_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(
                root,
                "wan22-only",
                image,
                context,
                model_ids=["alibaba/wan-2.2"],
            )
            bundle = (run / "instruction-bundle.md").read_text(encoding="utf-8")
            self.assertIn("Wan 2.2 five-second Segmind instruction.", bundle)
            self.assertNotIn("Wan five-second instruction.", bundle)
            self.assertNotIn("Veo four-second instruction.", bundle)

            result_path = self.run_with_fake(
                root,
                "wan22-only",
                ["alibaba/wan-2.2"],
            )
            result = runner.read_json(result_path)
            self.assertEqual(
                [item["model_id"] for item in result["models"]],
                ["alibaba/wan-2.2"],
            )
            self.assertEqual(result["models"][0]["runtime"]["frames"], 150)
            self.assertEqual(
                runner.provenance_summary(root, "wan22-only")["models"],
                ["alibaba/wan-2.2"],
            )

    def test_wan22_spec_cannot_fall_back_to_wan27_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            contract_path = root / runner.CONTRACT_PATH
            contract = runner.read_json(contract_path)
            wan27_spec = root / runner.MODEL_SPEC_PATHS["alibaba/wan-2.7"]
            contract["models"]["alibaba/wan-2.2"]["spec_path"] = (
                runner.MODEL_SPEC_PATHS["alibaba/wan-2.7"]
            )
            contract["models"]["alibaba/wan-2.2"]["spec_sha256"] = runner.sha256_file(
                wan27_spec
            )
            contract_path.write_text(json.dumps(contract), encoding="utf-8")

            with self.assertRaisesRegex(
                runner.LiteRunnerError,
                "spec_path must be exactly",
            ):
                runner.prepare_run(
                    root,
                    "wan22-spec-fallback",
                    image,
                    context,
                    model_ids=["alibaba/wan-2.2"],
                )
            self.assertFalse((root / runner.OUTPUT_NAMESPACE).exists())

    def test_replay_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            runner.prepare_run(
                root,
                "wan22-replay",
                image,
                context,
                model_ids=["alibaba/wan-2.2"],
            )

            def replay_executor(request, execution_policy, author_model, timeout):
                draft = json.loads(
                    self.draft_bytes("wan22-replay", ["alibaba/wan-2.2"])
                )
                draft["models"][0]["prompt_source_model_id"] = "alibaba/wan-2.7"
                execution = self.fake_executor("wan22-replay", ["alibaba/wan-2.2"])(
                    request,
                    execution_policy,
                    author_model,
                    timeout,
                )
                execution["draft_bytes"] = json.dumps(draft).encode("utf-8")
                return execution

            with mock.patch.object(
                runner,
                "execute_codex_agent",
                side_effect=replay_executor,
            ):
                with self.assertRaisesRegex(
                    runner.LiteRunnerError,
                    "contains forbidden keys",
                ):
                    runner.run_agent(
                        root,
                        "wan22-replay",
                        external_processing_approved=True,
                    )
            self.assertFalse(
                (root / runner.OUTPUT_NAMESPACE / "wan22-replay/result.json").exists()
            )

    def test_structured_intent_is_required_and_has_only_twelve_fields(self) -> None:
        draft = json.loads(self.draft_bytes("intent-run", ["alibaba/wan-2.7"]))
        draft["base_scene"] = "Legacy unstructured scene."
        del draft["structured_intent"]
        with self.assertRaisesRegex(runner.LiteRunnerError, "structured_intent"):
            runner.validate_draft(draft, "intent-run", ["alibaba/wan-2.7"])

        draft = json.loads(self.draft_bytes("intent-run", ["alibaba/wan-2.7"]))
        draft["structured_intent"]["scene_type"] = "portrait"
        with self.assertRaisesRegex(runner.LiteRunnerError, "forbidden keys"):
            runner.validate_draft(draft, "intent-run", ["alibaba/wan-2.7"])

        draft = json.loads(self.draft_bytes("intent-run", ["alibaba/wan-2.7"]))
        draft["structured_intent"]["terminal_state"] = "   "
        with self.assertRaisesRegex(runner.LiteRunnerError, "terminal_state"):
            runner.validate_draft(draft, "intent-run", ["alibaba/wan-2.7"])

        draft = json.loads(self.draft_bytes("intent-run", ["alibaba/wan-2.7"]))
        del draft["structured_intent"]["identity_invariant"]
        with self.assertRaisesRegex(runner.LiteRunnerError, "identity_invariant"):
            runner.validate_draft(draft, "intent-run", ["alibaba/wan-2.7"])

        draft = json.loads(self.draft_bytes("intent-run", ["alibaba/wan-2.7"]))
        draft["structured_intent"]["rendering_strategy"] = "unsafe-magic"
        with self.assertRaisesRegex(runner.LiteRunnerError, "rendering_strategy"):
            runner.validate_draft(draft, "intent-run", ["alibaba/wan-2.7"])

    def test_changed_instruction_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            (root / "docs/agents/clipmaker-lite/README.md").write_text(
                "Changed after lock.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.LiteRunnerError, "digest mismatch"):
                runner.prepare_run(root, "changed-contract", image, context)
            self.assertFalse((root / runner.OUTPUT_NAMESPACE).exists())

    def test_external_draft_cannot_receive_lite_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(
                root,
                "spoofed-run",
                image,
                context,
                model_ids=["alibaba/wan-2.7"],
            )
            draft = runner.read_json_bytes(
                self.draft_bytes("spoofed-run", ["alibaba/wan-2.7"]),
                "test draft",
            )
            draft["producer"] = {"agent_id": "clipmaker-lite"}
            (run / "draft.json").write_text(json.dumps(draft), encoding="utf-8")
            with self.assertRaisesRegex(runner.LiteRunnerError, "artifact already exists"):
                self.run_with_fake(
                    root, "spoofed-run", ["alibaba/wan-2.7"]
                )
            with self.assertRaisesRegex(runner.LiteRunnerError, "internal"):
                runner._finalize_run(root, "spoofed-run", object())
            self.assertFalse((run / "result.json").exists())

    def test_inputs_and_runs_are_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(
                root,
                "immutable-run",
                image,
                context,
                model_ids=["google/veo-3.1-lite"],
            )
            with self.assertRaisesRegex(runner.LiteRunnerError, "already exists"):
                runner.prepare_run(root, "immutable-run", image, context)
            image.write_bytes(b"changed-image")
            with self.assertRaisesRegex(runner.LiteRunnerError, "changed after"):
                self.run_with_fake(
                    root, "immutable-run", ["google/veo-3.1-lite"]
                )
            self.assertFalse((run / "result.json").exists())

    def test_provenance_rejects_a_modified_final_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(
                root,
                "tampered-result",
                image,
                context,
                model_ids=["google/veo-3.1-lite"],
            )
            result_path = self.run_with_fake(
                root, "tampered-result", ["google/veo-3.1-lite"]
            )
            result = runner.read_json(result_path)
            result["models"][0]["runtime"]["duration_seconds"] = 8
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(runner.LiteRunnerError, "runtime were modified"):
                runner.provenance_summary(root, "tampered-result")

    def test_provenance_rejects_a_modified_terminal_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            run = runner.prepare_run(
                root,
                "tampered-intent",
                image,
                context,
                model_ids=["alibaba/wan-2.2"],
            )
            result_path = self.run_with_fake(
                root,
                "tampered-intent",
                ["alibaba/wan-2.2"],
            )
            result = runner.read_json(result_path)
            result["analysis"]["structured_intent"]["terminal_state"] = (
                "A different endpoint appears."
            )
            result_path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(runner.LiteRunnerError, "analysis differ"):
                runner.provenance_summary(root, "tampered-intent")

    def test_bound_request_requires_intent_before_model_plans(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            runner.prepare_run(
                root,
                "bound-intent",
                image,
                context,
                model_ids=["google/veo-3.1-lite"],
            )
            job, selection, run = runner.validate_prepared_job(root, "bound-intent")
            request = runner.build_agent_request(job, selection, run, root.resolve())
            prompt = request["prompt"].decode("utf-8")
            self.assertIn("write structured_intent before any model plan", prompt)
            self.assertIn("Keep camera route, timing, amplitude", prompt)
            self.assertIn("<selected-image-context>", prompt)
            self.assertIn('"block_index": 1', prompt)
            self.assertIn('"caption": "Caption"', prompt)
            self.assertIn("Apply the feasibility gate", prompt)
            self.assertIn("always use null for", prompt)
            self.assertIn("attention anchor", prompt)
            self.assertIn("never reveal or construct unseen space", prompt)
            self.assertIn("<repair-feedback-data>", prompt)
            self.assertNotIn("compositor", prompt.lower())
            self.assertEqual(
                request["article_context_locator_sha256"],
                runner.sha256_bytes(
                    runner.canonical_json_bytes(
                        job["inputs"]["article_context"]["locator"]
                    )
                ),
            )
            self.assertLess(
                prompt.index("write structured_intent before any model plan"),
                prompt.index("return only the JSON object"),
            )

    def test_typed_repair_feedback_is_bound_into_request_result_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            model_ids = ["alibaba/wan-2.7", "google/veo-3.1-lite"]
            feedback = self.repair_feedback(model_ids)
            feedback_path = root / "repair-feedback.json"
            feedback_path.write_text(
                json.dumps(feedback, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            run = runner.prepare_run(
                root,
                "repair-bound",
                image,
                context,
                model_ids=model_ids,
                repair_feedback_path=feedback_path,
            )
            job, selection, validated_run = runner.validate_prepared_job(
                root, "repair-bound"
            )
            repair_input = job["inputs"]["repair_feedback"]
            self.assertEqual(repair_input["models"], feedback)
            self.assertEqual(repair_input["sha256"], runner.sha256_file(feedback_path))
            request = runner.build_agent_request(
                job, selection, validated_run, root.resolve()
            )
            self.assertEqual(
                request["repair_feedback_sha256"],
                repair_input["canonical_sha256"],
            )
            prompt = request["prompt"].decode("utf-8")
            self.assertIn("evaluation-20260811::alibaba/wan-2.7", prompt)
            self.assertIn("focal_target_drift", prompt)

            result_path = self.run_with_fake(root, "repair-bound", model_ids)
            result = runner.read_json(result_path)
            receipt = runner.read_json(run / "execution.json")
            self.assertEqual(result["inputs"]["repair_feedback"], repair_input)
            self.assertEqual(
                receipt["request"]["repair_feedback_sha256"],
                repair_input["canonical_sha256"],
            )
            self.assertTrue(runner.provenance_summary(root, "repair-bound")["verified"])

    def test_repair_feedback_requires_exact_models_and_strict_bounded_values(self) -> None:
        model_id = "google/veo-3.1-lite"
        valid = self.repair_feedback([model_id])
        self.assertEqual(
            runner.validate_repair_feedback_models(valid, [model_id]),
            valid,
        )

        with self.assertRaisesRegex(runner.LiteRunnerError, "exactly the selected"):
            runner.validate_repair_feedback_models(valid, ["alibaba/wan-2.7"])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["evaluation_id"] = "wrong-model::alibaba/wan-2.7"
        with self.assertRaisesRegex(runner.LiteRunnerError, "bound to model"):
            runner.validate_repair_feedback_models(invalid, [model_id])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["outcome"] = "better"
        with self.assertRaisesRegex(runner.LiteRunnerError, "outcome is invalid"):
            runner.validate_repair_feedback_models(invalid, [model_id])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["failure_codes"].append("focal_target_drift")
        with self.assertRaisesRegex(runner.LiteRunnerError, "duplicate"):
            runner.validate_repair_feedback_models(invalid, [model_id])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["camera_repair"]["max_screen_travel_percent"] = True
        with self.assertRaisesRegex(runner.LiteRunnerError, "between 0 and 10"):
            runner.validate_repair_feedback_models(invalid, [model_id])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["camera_repair"]["reveal_unseen_space"] = True
        with self.assertRaisesRegex(runner.LiteRunnerError, "must be false"):
            runner.validate_repair_feedback_models(invalid, [model_id])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["fallback_policy"] = "projected"
        with self.assertRaisesRegex(runner.LiteRunnerError, "must be none"):
            runner.validate_repair_feedback_models(invalid, [model_id])

        invalid = json.loads(json.dumps(valid))
        invalid[model_id]["preservation"]["rigid_regions"] = ["floor"] * 13
        with self.assertRaisesRegex(runner.LiteRunnerError, "between 0 and 12"):
            runner.validate_repair_feedback_models(invalid, [model_id])

    def test_repair_feedback_mutation_after_prepare_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            model_ids = ["google/veo-3.1-lite"]
            feedback = self.repair_feedback(model_ids)
            feedback_path = root / "repair-feedback.json"
            feedback_path.write_text(json.dumps(feedback), encoding="utf-8")
            runner.prepare_run(
                root,
                "repair-mutated",
                image,
                context,
                model_ids=model_ids,
                repair_feedback_path=feedback_path,
            )
            feedback[model_ids[0]]["review_note"] = "A changed but still valid note."
            feedback_path.write_text(json.dumps(feedback), encoding="utf-8")
            with self.assertRaisesRegex(runner.LiteRunnerError, "changed after"):
                runner.validate_prepared_job(root, "repair-mutated")

    def test_context_image_must_match_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            with self.assertRaisesRegex(runner.LiteRunnerError, "found 0"):
                runner.prepare_run(root, "wrong-image", image, context, image_id="99")

            other = root / "other/02.jpeg"
            other.parent.mkdir()
            other.write_bytes(b"different-image-with-same-name")
            with self.assertRaisesRegex(runner.LiteRunnerError, "found 0"):
                runner.prepare_run(root, "wrong-path", other, context, image_id="02")
            with self.assertRaisesRegex(runner.LiteRunnerError, "found 0"):
                runner.prepare_run(root, "wrong-path-no-id", other, context)

            suffix_copy = root / "other/articles/01-article/02.jpeg"
            suffix_copy.parent.mkdir(parents=True)
            suffix_copy.write_bytes(b"same-suffix-is-not-same-dataset")
            with self.assertRaisesRegex(runner.LiteRunnerError, "found 0"):
                runner.prepare_run(root, "wrong-suffix", suffix_copy, context, image_id="02")

    def test_output_namespace_rejects_symlink_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root, image, context = self.make_workspace(directory)
            (root / "artifacts").symlink_to(Path(external), target_is_directory=True)
            with self.assertRaisesRegex(runner.LiteRunnerError, "contains a symlink"):
                runner.prepare_run(root, "escaped-run", image, context, image_id="02")
            self.assertFalse((Path(external) / "clipmaker-lite/v1/escaped-run").exists())

    def test_non_null_negative_prompt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            runner.prepare_run(
                root,
                "non-null-negative",
                image,
                context,
                model_ids=["alibaba/wan-2.7"],
            )

            def invalid_executor(request, execution_policy, author_model, timeout):
                draft = json.loads(self.draft_bytes("non-null-negative", ["alibaba/wan-2.7"]))
                draft["models"][0]["negative_prompt"] = "legacy repair"
                execution = self.fake_executor("non-null-negative", ["alibaba/wan-2.7"])(
                    request,
                    execution_policy,
                    author_model,
                    timeout,
                )
                execution["draft_bytes"] = json.dumps(draft).encode("utf-8")
                return execution

            with self.assertRaisesRegex(runner.LiteRunnerError, "must be null"):
                with mock.patch.object(
                    runner,
                    "execute_codex_agent",
                    side_effect=invalid_executor,
                ):
                    runner.run_agent(
                        root,
                        "non-null-negative",
                        external_processing_approved=True,
                    )

    def test_every_rendering_strategy_requires_i2v_and_a_non_null_prompt(self) -> None:
        model_ids = ["google/veo-3.1-lite"]
        draft = json.loads(self.draft_bytes("camera-only-run", model_ids))
        draft["structured_intent"]["rendering_strategy"] = "camera-only"
        validated = runner.validate_draft(draft, "camera-only-run", model_ids)
        self.assertEqual(validated["models"][0]["execution_mode"], "i2v")
        self.assertIsInstance(validated["models"][0]["positive_prompt"], str)

        draft = json.loads(self.draft_bytes("camera-only-run", model_ids))
        draft["structured_intent"]["rendering_strategy"] = "deterministic-compositor"
        with self.assertRaisesRegex(runner.LiteRunnerError, "rendering_strategy"):
            runner.validate_draft(draft, "camera-only-run", model_ids)

        draft = json.loads(self.draft_bytes("camera-only-run", model_ids))
        draft["models"][0]["execution_mode"] = "deterministic-compositor"
        with self.assertRaisesRegex(runner.LiteRunnerError, "execution_mode"):
            runner.validate_draft(draft, "camera-only-run", model_ids)

        draft = json.loads(self.draft_bytes("camera-only-run", model_ids))
        draft["models"][0]["positive_prompt"] = None
        with self.assertRaisesRegex(runner.LiteRunnerError, "positive_prompt"):
            runner.validate_draft(draft, "camera-only-run", model_ids)

    def test_positive_prompt_is_limited_to_two_short_sentences(self) -> None:
        draft = json.loads(self.draft_bytes("long-prompt", ["alibaba/wan-2.2"]))
        draft["models"][0]["positive_prompt"] = "One move. A second move. A third move."
        with self.assertRaisesRegex(runner.LiteRunnerError, "no more than two"):
            runner.validate_draft(draft, "long-prompt", ["alibaba/wan-2.2"])

    def test_codex_event_parser_allows_only_exact_mdm_approval_policy_error(
        self,
    ) -> None:
        stdout = (
            b'{"type":"thread.started","thread_id":"thread-1"}\n'
            b'{"type":"turn.started"}\n'
            b'{"type":"item.completed","item":{"id":"item_0","type":"error",'
            b'"message":"Configured value for `approval_policy` is disallowed by '
            b'requirements; falling back to required value UnlessTrusted. Details: '
            b'invalid value for `approval_policy`: `Never` is not in the allowed set '
            b'[UnlessTrusted, OnRequest] (set by MDM '
            b'com.openai.codex:requirements_toml_base64)"}}\n'
            b'{"type":"item.completed","item":{"type":"agent_message"}}\n'
            b'{"type":"turn.completed"}\n'
        )
        thread_id, tool_events = runner._codex_event_metadata(stdout)
        self.assertEqual(thread_id, "thread-1")
        self.assertEqual(tool_events, [])

    def test_codex_event_parser_rejects_unknown_error_item(self) -> None:
        stdout = (
            b'{"type":"thread.started","thread_id":"thread-1"}\n'
            b'{"type":"item.completed","item":{"id":"item_0","type":"error",'
            b'"message":"A different error"}}\n'
        )
        with self.assertRaisesRegex(runner.LiteRunnerError, "forbidden item type"):
            runner._codex_event_metadata(stdout)

    def test_codex_event_parser_rejects_command_execution(self) -> None:
        stdout = (
            b'{"type":"thread.started","thread_id":"thread-1"}\n'
            b'{"type":"item.completed","item":{"type":"command_execution"}}\n'
        )
        with self.assertRaisesRegex(runner.LiteRunnerError, "forbidden item type"):
            runner._codex_event_metadata(stdout)

    def test_codex_event_parser_rejects_mdm_error_on_item_started(self) -> None:
        item = json.dumps(runner.IGNORABLE_MDM_APPROVAL_POLICY_ERROR_ITEM)
        stdout = (
            '{"type":"thread.started","thread_id":"thread-1"}\n'
            f'{{"type":"item.started","item":{item}}}\n'
        ).encode()
        with self.assertRaisesRegex(runner.LiteRunnerError, "forbidden item type"):
            runner._codex_event_metadata(stdout)

    def test_codex_event_parser_fails_closed(self) -> None:
        with self.assertRaisesRegex(runner.LiteRunnerError, "Invalid Codex JSONL"):
            runner._codex_event_metadata(b"not-json\n")
        with self.assertRaisesRegex(runner.LiteRunnerError, "Unsupported Codex"):
            runner._codex_event_metadata(b'{"type":"future.event"}\n')
        with self.assertRaisesRegex(runner.LiteRunnerError, "thread ID"):
            runner._codex_event_metadata(b'{"type":"turn.started"}\n')

    def test_execute_codex_agent_uses_locked_binary_and_isolated_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "locked-codex"
            binary.write_bytes(b"locked-executable")
            image = root / "source.jpeg"
            image.write_bytes(b"source-image")
            policy = {
                "executor_id": "codex-exec",
                "binary": {
                    "path": str(binary),
                    "sha256": runner.sha256_file(binary),
                    "version": "codex-test",
                },
                "sandbox": "read-only",
                "ephemeral": True,
                "ignore_user_config": True,
                "ignore_project_rules": True,
                "tool_event_policy": "reject-run",
                "requires_thread_id": True,
                "requires_explicit_external_processing": True,
            }
            request = {
                "image_path": image,
                "image_sha256": runner.sha256_file(image),
                "schema": {"type": "object"},
                "prompt": b"Bound Lite prompt",
            }
            commands: list[list[str]] = []

            def fake_run(command, **kwargs):
                commands.append(command)
                if command == [str(binary), "--version"]:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=b"codex-test\n",
                        stderr=b"",
                    )
                response_path = Path(
                    command[command.index("--output-last-message") + 1]
                )
                response_path.write_bytes(b'{"structured":true}')
                stdout = (
                    b'{"type":"thread.started","thread_id":"thread-real"}\n'
                    b'{"type":"turn.started"}\n'
                    b'{"type":"item.completed","item":{"type":"agent_message"}}\n'
                    b'{"type":"turn.completed"}\n'
                )
                self.assertEqual(kwargs["input"], b"Bound Lite prompt")
                return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")

            with mock.patch.object(runner.subprocess, "run", side_effect=fake_run):
                execution = runner.execute_codex_agent(request, policy, None, 30)

            command = commands[1]
            self.assertEqual(command[0], str(binary))
            self.assertNotIn("--model", command)
            self.assertEqual(
                command[command.index("--ask-for-approval") + 1],
                "untrusted",
            )
            for flag in (
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--json",
            ):
                self.assertIn(flag, command)
            disabled_features = [
                command[index + 1]
                for index, value in enumerate(command[:-1])
                if value == "--disable"
            ]
            self.assertEqual(
                disabled_features,
                ["plugins", "remote_plugin", "recommended_plugins", "apps"],
            )
            self.assertEqual(execution["executor"]["thread_id"], "thread-real")
            self.assertIsNone(execution["executor"]["requested_model"])
            self.assertEqual(
                execution["executor"]["attached_image_sha256"],
                request["image_sha256"],
            )

    def test_executor_must_match_locked_binary_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            runner.prepare_run(
                root,
                "wrong-executor",
                image,
                context,
                model_ids=["google/veo-3.1-lite"],
            )

            def spoofed_executor(request, execution_policy, author_model, timeout):
                execution = self.fake_executor(
                    "wrong-executor", ["google/veo-3.1-lite"]
                )(request, execution_policy, author_model, timeout)
                execution["executor"]["binary_path"] = "/tmp/fake-codex"
                return execution

            with mock.patch.object(
                runner,
                "execute_codex_agent",
                side_effect=spoofed_executor,
            ):
                with self.assertRaisesRegex(runner.LiteRunnerError, "binary_path"):
                    runner.run_agent(
                        root,
                        "wrong-executor",
                        external_processing_approved=True,
                    )

    def test_contract_paths_cannot_cross_into_classic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            classic = root / "docs/agents/clipmaker/README.md"
            classic.parent.mkdir(parents=True)
            classic.write_text("Classic instructions.\n", encoding="utf-8")
            contract_path = root / runner.CONTRACT_PATH
            contract = runner.read_json(contract_path)
            contract["base_instruction"] = {
                "path": "docs/agents/clipmaker/README.md",
                "sha256": runner.sha256_file(classic),
            }
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(runner.LiteRunnerError, "outside the Lite instruction root"):
                runner.prepare_run(root, "classic-crossing", image, context)

    def test_canonical_fingerprint_is_key_order_independent(self) -> None:
        left = {"b": 2, "a": {"y": 1, "x": 0}}
        right = {"a": {"x": 0, "y": 1}, "b": 2}
        self.assertEqual(runner.canonical_json_bytes(left), runner.canonical_json_bytes(right))
        self.assertNotEqual(
            runner.sha256_bytes(runner.canonical_json_bytes(left)),
            runner.sha256_bytes(runner.canonical_json_bytes({"b": 3, "a": left["a"]})),
        )

    def test_runner_has_no_classic_import_or_output_namespace(self) -> None:
        source = Path(runner.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import video_generation_pipeline", source)
        self.assertNotIn("PROMOPAGES-9857", source)
        self.assertEqual(runner.OUTPUT_NAMESPACE.as_posix(), "artifacts/clipmaker-lite/v1")


if __name__ == "__main__":
    unittest.main()
