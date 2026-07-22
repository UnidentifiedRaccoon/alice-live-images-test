#!/usr/bin/env python3
"""Contract checks for the standalone clipmaker-lite documentation."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
LITE = ROOT / "docs/agents/clipmaker-lite"
README = LITE / "README.md"
MODELS = LITE / "models"
CONTRACT = LITE / "contract.json"
RUNNER = ROOT / "scripts/clipmaker_lite_runner.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClipmakerLiteContractTest(unittest.TestCase):
    def test_agent_is_registered(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("## clipmaker-classic", text)
        self.assertIn("## clipmaker-lite", text)
        self.assertIn("docs/agents/clipmaker-lite/README.md", text)
        self.assertIn("scripts/clipmaker_lite_runner.py", text)
        self.assertIn("ask which contract to use", text)

    def test_v1_has_only_two_model_specs(self) -> None:
        self.assertEqual(
            [path.name for path in sorted(MODELS.glob("*.md"))],
            ["alibaba-wan-2.7.md", "google-veo-3.1-lite.md"],
        )

    def test_model_durations_and_expansion(self) -> None:
        wan = (MODELS / "alibaba-wan-2.7.md").read_text(encoding="utf-8")
        veo = (MODELS / "google-veo-3.1-lite.md").read_text(encoding="utf-8")
        self.assertIn("| Duration | `5 s` |", wan)
        self.assertIn("`prompt_extend: true`", wan)
        self.assertIn("| Duration | `4 s` |", veo)
        self.assertIn("`enhancePrompt: true`", veo)

    def test_machine_contract_locks_runner_and_instructions(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["agent_id"], "clipmaker-lite")
        self.assertEqual(contract["output_namespace"], "artifacts/clipmaker-lite/v1")
        self.assertEqual(contract["execution"]["executor_id"], "codex-exec")
        self.assertEqual(contract["execution"]["tool_event_policy"], "reject-run")
        self.assertTrue(contract["execution"]["requires_thread_id"])
        self.assertTrue(contract["execution"]["requires_explicit_external_processing"])
        self.assertEqual(
            contract["execution"]["binary"]["path"],
            "/Applications/ChatGPT.app/Contents/Resources/codex",
        )
        self.assertEqual(contract["input_binding"]["image_root"], "PROMOPAGES-9857")
        self.assertEqual(contract["input_binding"]["context_root"], "PROMOPAGES-9884")
        self.assertEqual(contract["runner"]["sha256"], sha256_file(RUNNER))
        self.assertEqual(contract["base_instruction"]["sha256"], sha256_file(README))
        for model_id, filename in (
            ("alibaba/wan-2.7", "alibaba-wan-2.7.md"),
            ("google/veo-3.1-lite", "google-veo-3.1-lite.md"),
        ):
            self.assertEqual(
                contract["models"][model_id]["spec_sha256"],
                sha256_file(MODELS / filename),
            )
        self.assertEqual(contract["models"]["alibaba/wan-2.7"]["runtime"]["duration_seconds"], 5)
        self.assertEqual(contract["models"]["google/veo-3.1-lite"]["runtime"]["duration_seconds"], 4)

    def test_workflow_is_context_aware_and_model_specific(self) -> None:
        text = README.read_text(encoding="utf-8")
        for heading in (
            "### 1. Анализ изображения",
            "### 2. Анализ контекста",
            "### 3. Base scene",
            "### 4. Независимый план для каждой модели",
        ):
            self.assertIn(heading, text)
        self.assertIn("PROMOPAGES-9884", text)
        self.assertIn("Нет общего deadline", text)

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
