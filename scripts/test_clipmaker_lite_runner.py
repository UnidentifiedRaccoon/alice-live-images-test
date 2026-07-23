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
        wan22.write_text("Wan 2.2 three-second instruction.\n", encoding="utf-8")
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
                        "duration_seconds": 3.2,
                        "resolution": "720p",
                        "aspect_ratios": ["source"],
                        "generate_audio": False,
                        "frame_inputs": ["first_frame"],
                        "provider": "wan-streamlit",
                        "adapter": "wan-demo",
                        "frames": 97,
                        "fps": 30,
                        "seed": 1,
                        "loop": False,
                        "last_frame": None,
                        "prompt_expansion": {"mode": "not_exposed"},
                        "negative_prompt_transport": {
                            "mode": "combined_prompt",
                            "separator": "\n\nAvoid: ",
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
                "primary_action": "One visible change develops from the source frame.",
                "terminal_state": "The change reaches an observable endpoint.",
                "semantic_invariant": "The editorial state remains unchanged through the end.",
            },
            "models": [
                {
                    "model_id": model_id,
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
            self.assertIn("Wan 2.2 three-second instruction.", bundle)
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
                [3.2, 5, 4],
            )
            self.assertEqual(
                result["models"][0]["runtime"]["prompt_expansion"],
                {"mode": "not_exposed"},
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
            summary = runner.provenance_summary(root, "sample-run")
            self.assertTrue(summary["verified"])
            self.assertEqual(summary["agent_id"], "clipmaker-lite")
            self.assertEqual(summary["verification_scope"], "trusted-workspace-route")
            self.assertFalse(summary["cryptographically_signed"])
            receipt = runner.read_json(run / "execution.json")
            self.assertTrue(receipt["external_processing_approved"])
            self.assertEqual(receipt["executor"]["thread_id"], "thread-test")
            self.assertEqual(receipt["executor"]["binary_path"], "/test/codex")

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
            self.assertIn("Wan 2.2 three-second instruction.", bundle)
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
            self.assertEqual(result["models"][0]["runtime"]["frames"], 97)
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

    def test_structured_intent_is_required_and_has_only_four_fields(self) -> None:
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
            self.assertIn("Keep camera, timing, amplitude, scene type", prompt)
            self.assertLess(
                prompt.index("write structured_intent before any model plan"),
                prompt.index("return only the JSON object"),
            )

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

    def test_wan_negative_repair_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, image, context = self.make_workspace(directory)
            runner.prepare_run(
                root,
                "long-negative",
                image,
                context,
                model_ids=["alibaba/wan-2.7"],
            )

            def invalid_executor(request, execution_policy, author_model, timeout):
                draft = json.loads(self.draft_bytes("long-negative", ["alibaba/wan-2.7"]))
                draft["models"][0]["negative_prompt"] = "x" * 501
                execution = self.fake_executor("long-negative", ["alibaba/wan-2.7"])(
                    request,
                    execution_policy,
                    author_model,
                    timeout,
                )
                execution["draft_bytes"] = json.dumps(draft).encode("utf-8")
                return execution

            with self.assertRaisesRegex(runner.LiteRunnerError, "must not exceed 500"):
                with mock.patch.object(
                    runner,
                    "execute_codex_agent",
                    side_effect=invalid_executor,
                ):
                    runner.run_agent(
                        root,
                        "long-negative",
                        external_processing_approved=True,
                    )

    def test_codex_event_parser_detects_tool_use(self) -> None:
        stdout = (
            b'{"type":"thread.started","thread_id":"thread-1"}\n'
            b'{"type":"item.completed","item":{"type":"command_execution"}}\n'
        )
        thread_id, tool_events = runner._codex_event_metadata(stdout)
        self.assertEqual(thread_id, "thread-1")
        self.assertEqual(tool_events, ["command_execution"])

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
            for flag in (
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--json",
            ):
                self.assertIn(flag, command)
            self.assertEqual(execution["executor"]["thread_id"], "thread-real")
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
