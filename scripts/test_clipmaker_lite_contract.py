#!/usr/bin/env python3
"""Contract checks for the standalone clipmaker-lite documentation."""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import unittest
from pathlib import Path

from scripts import clipmaker_lite_runner as runner


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
LITE = ROOT / "docs/agents/clipmaker-lite"
README = LITE / "README.md"
MODELS = LITE / "models"
CONTRACT = LITE / "contract.json"
ARCHIVED_207_CONTRACT = LITE / "contracts/contract-2.0.7.json"
ARCHIVED_208_CONTRACT = LITE / "contracts/contract-2.0.8.json"
ARCHIVED_208_SUPPORT = LITE / "contracts/support-2.0.8"
ARCHIVED_220_CONTRACT = LITE / "contracts/contract-2.2.0.json"
ARCHIVED_220_SUPPORT = LITE / "contracts/support-2.2.0"
RUNNER = ROOT / "scripts/clipmaker_lite_runner.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClipmakerLiteContractTest(unittest.TestCase):
    def test_agent_is_registered(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("## clipmaker-classic", text)
        self.assertIn("## clipmaker-lite", text)
        self.assertIn("docs/agents/clipmaker-lite/README.md", text)
        self.assertIn("docs/agents/clipmaker-lite/generation-routes.json", text)
        self.assertIn("scripts/clipmaker_lite_runner.py", text)
        self.assertIn("ask which contract to use", text)

    def test_v1_has_exactly_three_model_specs(self) -> None:
        self.assertEqual(
            [path.name for path in sorted(MODELS.glob("*.md"))],
            [
                "alibaba-wan-2.2.md",
                "alibaba-wan-2.7.md",
                "google-veo-3.1-lite.md",
            ],
        )

    def test_model_durations_and_expansion(self) -> None:
        wan22 = (MODELS / "alibaba-wan-2.2.md").read_text(encoding="utf-8")
        wan = (MODELS / "alibaba-wan-2.7.md").read_text(encoding="utf-8")
        veo = (MODELS / "google-veo-3.1-lite.md").read_text(encoding="utf-8")
        self.assertIn("| Planning duration | `5 s` |", wan22)
        self.assertIn("Prompt expansion | `prompt_extend: false`", wan22)
        self.assertIn("authored `null`", wan22)
        self.assertIn("пустая строка `\"\"`", wan22)
        self.assertIn("межмодельный replay запрещены", wan22)
        self.assertIn("| Duration | `5 s` |", wan)
        self.assertIn("`prompt_extend: true`", wan)
        self.assertIn("| Duration | `4 s` |", veo)
        self.assertIn("`enhancePrompt: true`", veo)

    def test_machine_contract_locks_runner_and_instructions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["agent_id"], "clipmaker-lite")
        self.assertEqual(contract["contract_version"], "2.3.0")
        self.assertEqual(contract["runner"]["runner_version"], 10)
        self.assertEqual(runner.DRAFT_SCHEMA_VERSION, 5)
        self.assertEqual(runner.RESULT_SCHEMA_VERSION, 5)
        self.assertEqual(contract["output_namespace"], "artifacts/clipmaker-lite/v1")
        self.assertEqual(contract["execution"]["executor_id"], "codex-exec")
        self.assertEqual(contract["execution"]["tool_event_policy"], "reject-run")
        self.assertTrue(contract["execution"]["requires_thread_id"])
        self.assertTrue(contract["execution"]["requires_explicit_external_processing"])
        self.assertEqual(
            contract["execution"]["binary"]["path"],
            "/Applications/ChatGPT.app/Contents/Resources/codex",
        )
        self.assertEqual(
            contract["execution"]["binary"]["sha256"],
            "04ddea2f332bd524bf6cc02f8efcf45f0afa0c7d9b97d77aaef7bb84adf3d4c5",
        )
        self.assertEqual(
            contract["execution"]["binary"]["version"],
            "codex-cli 0.147.0-alpha.6.5",
        )
        self.assertEqual(contract["input_binding"]["image_root"], "PROMOPAGES-9857")
        self.assertEqual(contract["input_binding"]["context_root"], "PROMOPAGES-9884")
        self.assertEqual(contract["runner"]["sha256"], sha256_file(RUNNER))
        self.assertEqual(contract["base_instruction"]["sha256"], sha256_file(README))
        self.assertEqual(
            list(contract["models"]),
            ["alibaba/wan-2.2", "alibaba/wan-2.7", "google/veo-3.1-lite"],
        )
        for model_id, filename in (
            ("alibaba/wan-2.2", "alibaba-wan-2.2.md"),
            ("alibaba/wan-2.7", "alibaba-wan-2.7.md"),
            ("google/veo-3.1-lite", "google-veo-3.1-lite.md"),
        ):
            self.assertEqual(
                contract["models"][model_id]["spec_sha256"],
                sha256_file(MODELS / filename),
            )
        wan22_runtime = contract["models"]["alibaba/wan-2.2"]["runtime"]
        self.assertEqual(wan22_runtime["duration_seconds"], 5)
        self.assertEqual(wan22_runtime["resolution"], "720p")
        self.assertEqual(wan22_runtime["aspect_ratios"], ["source"])
        self.assertEqual(wan22_runtime["gateway"], "eliza")
        self.assertEqual(wan22_runtime["provider"], "segmind")
        self.assertEqual(
            wan22_runtime["provider_model_id"],
            "segmind/wan-2.2-i2v-flash",
        )
        self.assertEqual(wan22_runtime["adapter"], "eliza-segmind")
        self.assertTrue(wan22_runtime["synchronous"])
        self.assertFalse(wan22_runtime["automatic_retry"])
        self.assertEqual((wan22_runtime["frames"], wan22_runtime["fps"]), (150, 30))
        self.assertEqual(wan22_runtime["seed"], 220214)
        self.assertFalse(wan22_runtime["watermark"])
        self.assertEqual(
            wan22_runtime["prompt_expansion"],
            {"parameter": "prompt_extend", "value": False},
        )
        self.assertEqual(
            wan22_runtime["negative_prompt_transport"],
            {
                "mode": "separate_field",
                "parameter": "negative_prompt",
                "null_serialization": "empty_string",
            },
        )
        self.assertEqual(contract["models"]["alibaba/wan-2.7"]["runtime"]["duration_seconds"], 5)
        self.assertEqual(contract["models"]["google/veo-3.1-lite"]["runtime"]["duration_seconds"], 4)

    def test_installed_codex_binary_matches_lock_when_present(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        locked = contract["execution"]["binary"]
        binary = Path(locked["path"])
        if not binary.is_file():
            self.skipTest("locked macOS Codex binary is not installed")
        self.assertFalse(binary.is_symlink())
        self.assertEqual(sha256_file(binary), locked["sha256"])
        inspected = subprocess.run(
            [str(binary), "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(
            inspected.stdout.decode("utf-8", errors="replace").strip(),
            locked["version"],
        )

    def test_207_contract_is_archived_with_exact_historical_lock(self) -> None:
        contract = json.loads(ARCHIVED_207_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["agent_id"], "clipmaker-lite")
        self.assertEqual(contract["contract_version"], "2.0.7")
        self.assertEqual(
            contract["execution"]["binary"],
            {
                "path": "/Applications/ChatGPT.app/Contents/Resources/codex",
                "sha256": (
                    "9f6748b4ab10ffc92c28b9ccedae89e61a302bbc011df7d276ee38f55906e481"
                ),
                "version": "codex-cli 0.147.0-alpha.1.2",
            },
        )
        self.assertEqual(
            sha256_file(ARCHIVED_207_CONTRACT),
            "3336d03bb268cb73515256b438a02905fb2455f5875cb028f239bfafa11e0d86",
        )
        self.assertEqual(
            runner.sha256_bytes(runner.canonical_json_bytes(contract)),
            "1e804e0f1f8cddb8738179e50c50688a0b8d5ef4480c1f41dc1828f892fe17dd",
        )

    def test_208_contract_and_support_are_archived_with_exact_historical_lock(
        self,
    ) -> None:
        contract = json.loads(ARCHIVED_208_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["agent_id"], "clipmaker-lite")
        self.assertEqual(contract["contract_version"], "2.0.8")
        self.assertEqual(contract["runner"]["runner_version"], 7)
        self.assertEqual(
            contract["execution"]["binary"],
            {
                "path": "/Applications/ChatGPT.app/Contents/Resources/codex",
                "sha256": (
                    "e4432c0c085e4a2e5b9cf982e4dd2ebdb44ed33c422827b6e6c64353778e773b"
                ),
                "version": "codex-cli 0.147.0-alpha.6.5",
            },
        )
        self.assertEqual(
            sha256_file(ARCHIVED_208_CONTRACT),
            "500731400dc59b191ab73bf9a890efae7c84a44115c40b9f3b0bb1a646bc095f",
        )
        self.assertEqual(
            runner.sha256_bytes(runner.canonical_json_bytes(contract)),
            "62abfd56e1b68abf2a6e7bb0eba402a73fd29eebc26b72055b66aefd1c6ccbc0",
        )

        support_bindings = [
            (contract["runner"]["path"], contract["runner"]["sha256"]),
            (
                contract["base_instruction"]["path"],
                contract["base_instruction"]["sha256"],
            ),
            *[
                (model["spec_path"], model["spec_sha256"])
                for model in contract["models"].values()
            ],
        ]
        self.assertEqual(len(support_bindings), 5)
        for relative, expected_sha256 in support_bindings:
            with self.subTest(relative=relative):
                path = ARCHIVED_208_SUPPORT / relative
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                self.assertEqual(sha256_file(path), expected_sha256)

    def test_220_contract_and_support_are_archived_with_exact_historical_lock(
        self,
    ) -> None:
        contract = json.loads(ARCHIVED_220_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["agent_id"], "clipmaker-lite")
        self.assertEqual(contract["contract_version"], "2.2.0")
        self.assertEqual(contract["runner"]["runner_version"], 9)
        self.assertEqual(
            sha256_file(ARCHIVED_220_CONTRACT),
            "3428f60536e09e254150d7b3de880477dcadff357ccead6562c1e2757836cf4f",
        )
        self.assertEqual(
            runner.sha256_bytes(runner.canonical_json_bytes(contract)),
            "b81df0faaf3674807f13bc9f800c0f1d2d66aae9edc9414c99345321cfb0cc5f",
        )
        support_bindings = [
            (contract["runner"]["path"], contract["runner"]["sha256"]),
            (
                contract["base_instruction"]["path"],
                contract["base_instruction"]["sha256"],
            ),
            *[
                (model["spec_path"], model["spec_sha256"])
                for model in contract["models"].values()
            ],
        ]
        self.assertEqual(len(support_bindings), 5)
        for relative, expected_sha256 in support_bindings:
            with self.subTest(relative=relative):
                path = ARCHIVED_220_SUPPORT / relative
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                self.assertEqual(sha256_file(path), expected_sha256)

    def test_codex_authoring_model_is_not_fixed_by_contract(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        execution = contract["execution"]

        def nested_keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | {
                    key
                    for child in value.values()
                    for key in nested_keys(child)
                }
            if isinstance(value, list):
                return {
                    key
                    for child in value
                    for key in nested_keys(child)
                }
            return set()

        self.assertTrue(
            {
                "author_model",
                "requested_model",
                "model",
                "model_id",
                "model_policy",
                "allowed_models",
                "required_model",
            }.isdisjoint(nested_keys(execution))
        )

        parser = runner.build_parser()
        cli_default = parser.parse_args(
            ["run", "--run-id", "sample", "--allow-external-processing"]
        )
        self.assertIsNone(cli_default.author_model)

        arbitrary = parser.parse_args(
            [
                "run",
                "--run-id",
                "sample",
                "--author-model",
                "provider/future-codex-model",
                "--allow-external-processing",
            ]
        )
        self.assertEqual(arbitrary.author_model, "provider/future-codex-model")

    def test_workflow_is_context_aware_and_model_specific(self) -> None:
        text = README.read_text(encoding="utf-8")
        for heading in (
            "### 1. Анализ изображения",
            "### 2. Анализ контекста",
            "### 3. Structured intent",
            "### 4. Независимый план для каждой модели",
        ):
            self.assertIn(heading, text)
        self.assertIn("PROMOPAGES-9884", text)
        self.assertIn("Нет общего deadline", text)
        self.assertIn("Межмодельный replay", text)
        for field in (
            "editorial_meaning",
            "initial_state",
            "motion_owner",
            "primary_action",
            "terminal_state",
            "geometry_invariant",
            "identity_invariant",
            "semantic_invariant",
            "feasibility_assessment",
            "attention_anchor",
            "motion_boundary",
            "rendering_strategy",
        ):
            self.assertIn(field, text)
        for marker in (
            "#### Feasibility gate",
            "execution_mode: i2v",
            "непустой `positive_prompt`",
            "Если первый кадр уже соответствует `terminal_state`",
            "### Risk-aware action policy",
            "Статичная архитектура и выраженная глубина",
            "visibility floor",
            "composition ceiling",
        ):
            self.assertIn(marker, text)
        self.assertIn("model × scene routing", text)

    def test_each_model_has_endpoint_persistence_ui_and_people_policy(self) -> None:
        for path in sorted(MODELS.glob("*.md")):
            with self.subTest(model=path.name):
                text = " ".join(path.read_text(encoding="utf-8").split())
                for marker in (
                    "Terminal state",
                    "semantic_invariant",
                    "geometry_invariant",
                    "identity_invariant",
                    "Ключевой объект",
                    "## UI и people risks",
                    "camera state",
                    "`execution_mode: i2v`",
                    "непустой `positive_prompt`",
                    "Authored `negative_prompt` всегда и буквально равен `null`",
                ):
                    self.assertIn(marker, text)

    def test_runner_schema_projects_every_scene_strategy_to_i2v(self) -> None:
        schema = runner.draft_output_schema(
            "contract-schema",
            ["alibaba/wan-2.2"],
        )
        model_schema = schema["properties"]["models"]["items"]
        self.assertEqual(
            model_schema["properties"]["execution_mode"],
            {"type": "string", "const": "i2v"},
        )
        self.assertEqual(
            model_schema["properties"]["positive_prompt"],
            {"type": "string", "minLength": 1, "maxLength": 500},
        )
        source = inspect.getsource(runner.validate_draft)
        self.assertIn('execution_mode != "i2v"', source)
        self.assertIn("require_short_positive_prompt", source)

    def test_active_contract_has_no_compositor_route(self) -> None:
        documents = [README, CONTRACT, *sorted(MODELS.glob("*.md")), RUNNER]
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        self.assertNotIn("deterministic-compositor", text)
        self.assertNotIn("compositor", text.lower())

    def test_heavy_clipmaker_contract_is_not_imported(self) -> None:
        documents = [README, CONTRACT, *sorted(MODELS.glob("*.md"))]
        text = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        for forbidden in (
            "scene-modules.md",
            "prompt-templates.md",
            "action_complete_by_seconds",
            "primary_class",
            "graphic_kind",
            "Module A",
        ):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("../clipmaker/", text)
        self.assertNotIn("../../clipmaker/", text)


if __name__ == "__main__":
    unittest.main()
