#!/usr/bin/env python3
"""Run one immutable ambient-motion V5 experiment on the original frame."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import (  # noqa: E402
    clipmaker_lite_promopages_10060_femibion_veo_recovery_v4 as v4,
)


v2 = v4.v2
RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v5"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
PLANNING_RUN_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v5b-"
    "07-femibion-gotovites-k-beremennosti-06"
)
SOURCE_PATH = (
    "PROMOPAGES-9857/PROMOPAGES-10060/articles/"
    "07-femibion-gotovites-k-beremennosti/06.jpeg"
)
CONTEXT_PATH = (
    "PROMOPAGES-9884/PROMOPAGES-10060/articles/"
    "07-femibion-gotovites-k-beremennosti/content.json"
)
SOURCE_URL = (
    "https://avatars.mds.yandex.net/get-promoarticles/5096941/"
    "pub_685a45c483113703283d5b0e_685ab42c046a3d4397850a85/orig"
)
SOURCE_SHA256 = "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12"
CONTEXT_SHA256 = "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c"
PLANNING_RESULT_SHA256 = (
    "95022eb555ae4d6474471c682b36b1c50f6cc44664f49a142ef673497d6697eb"
)
EXPECTED_REQUEST_SHA256 = (
    "f7c89bf386a5d160d4731fb4a1372c2817797f24ea708dd7988bd2dbfe889031"
)
EXPECTED_PROMPT = (
    "Locked camera. A slight, gradual shift in natural daylight is the only "
    "motion. Preserve the complete composition and all visible details."
)
REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("100.45")

V4_EVIDENCE = {
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v4/generation-manifest.json"): "069c04ecc7ac488bd421384bb66924f02a4d81841bd735b62448c3f8a188fad4",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v4/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json"): "904ec62f1c11e24e9abf1b97f0e90271ab284e58434c81534b35fb6f3ce14f87",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v4/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"): "cccbbf73288ee1379906bd46e9d782ef456c0ee9e392712e66e2f7b8571ecffc",
}


class RecoveryError(RuntimeError):
    """Fail-closed V5 experiment error."""


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be a decimal amount") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError("V5 requires --budget-cap-usd 100.45 exactly")
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RecoveryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def accounting_document(value: str | Decimal) -> dict[str, Any]:
    parsed = Decimal(str(value))
    if parsed not in {Decimal("99.40"), REQUIRED_OPERATOR_BUDGET_CAP_USD}:
        raise RecoveryError("Unexpected V5 accounting literal")
    return {
        "currency": "USD",
        "baseline_paid_submissions": 286,
        "baseline_reserved_usd": 100.10,
        "recovery_paid_submissions": 1,
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 0.35,
        "aggregate_paid_submissions": 287,
        "aggregate_reserved_usd": 100.45,
        "operator_budget_cap_usd": 100.45,
        "hard_budget_cap_usd": 104.75,
        "hard_cap_headroom_usd": 4.30,
        "authorized_additional_budget_usd": 5.0,
        "automatic_paid_retries": False,
        "pricing_basis": "explicit user-authorized experiment budget",
    }


def load_v5_job(entry: Any, root: Path = ROOT) -> Any:
    if entry != v2.ENTRY:
        raise RecoveryError(f"Unexpected V5 entry: {entry.run_id}")
    contract = v2.validate_contract(root)
    job = v2._NATIVE_LOAD_LITE_JOB(entry, root)
    summary = job.provenance
    expected_result = (
        v2.ARTIFACT_NAMESPACE / PLANNING_RUN_ID / "result.json"
    ).as_posix()
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != v2.AGENT_ID
        or summary.get("contract_version") != contract["contract_version"]
        or summary.get("models") != [v2.MODEL_ID]
        or summary.get("source_image_sha256") != SOURCE_SHA256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
        or summary.get("result_path") != expected_result
        or job.result_path != expected_result
        or job.result_sha256 != PLANNING_RESULT_SHA256
        or job.positive_prompt != EXPECTED_PROMPT
        or job.negative_prompt is not None
    ):
        raise RecoveryError("V5 Lite provenance/prompt binding differs")
    result = v2.read_json(root / expected_result)
    direction = result.get("inputs", {}).get("user_direction")
    if not isinstance(direction, str) or "Prompt-action experiment" not in direction:
        raise RecoveryError("V5 Lite prompt-action intent differs")
    forbidden = {"medical", "pregnancy", "health", "phone", "hand", "breathing", "blink"}
    present = sorted(set(re.findall(r"[a-z]+", job.positive_prompt.casefold())) & forbidden)
    if present:
        raise RecoveryError(f"V5 provider prompt contains forbidden terms: {present}")
    return job


def configure_v5() -> None:
    v4.RECOVERY_ID = RECOVERY_ID
    v4.PROVIDER_BATCH_ID = PROVIDER_BATCH_ID
    v4.RECOVERY_ROOT_REL = RECOVERY_ROOT_REL
    v4.GENERATION_MANIFEST_REL = GENERATION_MANIFEST_REL
    v4.RECOVERY_MANIFEST_REL = RECOVERY_ROOT_REL / "recovery-manifest.json"
    v4.COMBINED_SELECTION_MANIFEST_REL = RECOVERY_ROOT_REL / "combined-selection-manifest.json"
    v4.PLANNING_RUN_ID = PLANNING_RUN_ID
    v4.SOURCE_PATH = SOURCE_PATH
    v4.CONTEXT_PATH = CONTEXT_PATH
    v4.SOURCE_URL = SOURCE_URL
    v4.SOURCE_SHA256 = SOURCE_SHA256
    v4.CONTEXT_SHA256 = CONTEXT_SHA256
    v4.PLANNING_RESULT_SHA256 = PLANNING_RESULT_SHA256
    v4.EXPECTED_REQUEST_SHA256 = EXPECTED_REQUEST_SHA256
    v4.EXPECTED_PROMPT = EXPECTED_PROMPT
    v4.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v4.PINNED_PRIOR_EVIDENCE.update(V4_EVIDENCE)
    v4.configure_v4()
    v2.BASELINE_PAID_SUBMISSIONS = 286
    v2.BASELINE_RESERVED_USD = Decimal("100.10")
    v2.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v2.HARD_BUDGET_CAP_USD = Decimal("104.75")
    v2.accounting_document = accounting_document
    v2.load_v2_job = load_v5_job


def dry_run(value: str | Decimal) -> int:
    parse_budget(value)
    state = v4.preflight(value, ROOT)
    if state["record"]["positive_prompt"] != EXPECTED_PROMPT:
        raise RecoveryError("V5 preflight prompt changed")
    print(f"PASS: {v2.ENTRY.provider_run_id} uses verified {PLANNING_RUN_ID}")
    print("PASS: V5 changes only the motion prompt; one submit under $100.45; no files written")
    return 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dry = commands.add_parser("dry-run")
    dry.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    for name in ("generate", "resume"):
        command = commands.add_parser(name)
        command.add_argument("--budget-cap-usd", type=budget_arg, required=True)
        command.add_argument("--allow-external-processing", action="store_true")
        command.add_argument("--timeout", type=positive_int, default=1800)
        command.add_argument("--poll-interval", type=positive_float, default=10.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    configure_v5()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            return dry_run(args.budget_cap_usd)
        return v4.run_generation(
            args.command,
            budget_cap_usd=args.budget_cap_usd,
            allow_external_processing=args.allow_external_processing,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
            root=ROOT,
        )
    except (
        RecoveryError,
        v4.RecoveryError,
        v2.RecoveryError,
        v2.v1.RecoveryError,
        v2.native.BatchPipelineError,
        v2.pipeline.PipelineError,
        v2.transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {v2.transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
