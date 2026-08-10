#!/usr/bin/env python3
"""Run one immutable background-patch V7 Veo experiment."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import (  # noqa: E402
    clipmaker_lite_promopages_10060_femibion_veo_recovery_v6 as v6,
)


v5, v4, v2 = v6.v5, v6.v4, v6.v2
RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v7"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
PLANNING_RUN_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v7-"
    "07-femibion-gotovites-k-beremennosti-06"
)
SOURCE_PATH = (
    "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v7/articles/"
    "07-femibion-gotovites-k-beremennosti/06.jpeg"
)
CONTEXT_PATH = (
    "PROMOPAGES-9884/PROMOPAGES-10060/recovery-v7/articles/"
    "07-femibion-gotovites-k-beremennosti/content.json"
)
SOURCE_URL = (
    "https://yastatic.net/s3/promopages-front-bundles/front-images/exp_video/"
    "_recovery_inputs/promopages-10060/femibion-07-06/v7/"
    "06--sha256-31672c583245.jpeg"
)
SOURCE_SHA256 = "31672c5832458e9698f2a5710a159b10cbb99febf55c7f1b0906393f977cb88e"
CONTEXT_SHA256 = "3db3fbc0a8ad5d263fd445df6add5ad5343e9eaf67529aba787ebc6e096452f8"
PLANNING_RESULT_SHA256 = (
    "73f878a18d9f063a4ed674efd6601c140ff5e406700f619bbc4acb065f75d1b0"
)
EXPECTED_REQUEST_SHA256 = (
    "e6c5a3b9586df1f116846afcae103e9475de69883add0330e7a4804922daf522"
)
EXPECTED_PROMPT = v6.EXPECTED_PROMPT
REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("101.15")

V6_EVIDENCE = {
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v6/generation-manifest.json"): "ad55d6a7cf222f67f898b057456dba2df19fd934a12022ab8e71ffd8e64235ec",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v6/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json"): "a9c983375ca098418e4bdc6c549ce0306b9e26a04067dac94fa946b7d6313394",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v6/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"): "05140dbae8cef3ce1d3d69690c10e656fe1ca74ed0584b3eec93ee53ad3bf5bb",
}


class RecoveryError(RuntimeError):
    pass


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be decimal") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError("V7 requires --budget-cap-usd 101.15 exactly")
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RecoveryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def accounting_document(value: str | Decimal) -> dict[str, Any]:
    parsed = Decimal(str(value))
    if parsed not in {Decimal("99.40"), REQUIRED_OPERATOR_BUDGET_CAP_USD}:
        raise RecoveryError("Unexpected V7 accounting literal")
    return {
        "currency": "USD",
        "baseline_paid_submissions": 288,
        "baseline_reserved_usd": 100.80,
        "recovery_paid_submissions": 1,
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 0.35,
        "aggregate_paid_submissions": 289,
        "aggregate_reserved_usd": 101.15,
        "operator_budget_cap_usd": 101.15,
        "hard_budget_cap_usd": 104.75,
        "hard_cap_headroom_usd": 3.60,
        "authorized_additional_budget_usd": 5.0,
        "automatic_paid_retries": False,
        "pricing_basis": "explicit user-authorized experiment budget",
    }


def load_v7_job(entry: Any, root: Path = ROOT) -> Any:
    if entry != v2.ENTRY:
        raise RecoveryError(f"Unexpected V7 entry: {entry.run_id}")
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
        raise RecoveryError("V7 Lite provenance/prompt binding differs")
    result = v2.read_json(root / expected_result)
    direction = result.get("inputs", {}).get("user_direction")
    if not isinstance(direction, str) or "Background-patch experiment" not in direction:
        raise RecoveryError("V7 Lite background-patch intent differs")
    return job


def configure_v7() -> None:
    v6.RECOVERY_ID = RECOVERY_ID
    v6.PROVIDER_BATCH_ID = PROVIDER_BATCH_ID
    v6.RECOVERY_ROOT_REL = RECOVERY_ROOT_REL
    v6.GENERATION_MANIFEST_REL = GENERATION_MANIFEST_REL
    v6.PLANNING_RUN_ID = PLANNING_RUN_ID
    v6.SOURCE_PATH = SOURCE_PATH
    v6.CONTEXT_PATH = CONTEXT_PATH
    v6.SOURCE_URL = SOURCE_URL
    v6.SOURCE_SHA256 = SOURCE_SHA256
    v6.CONTEXT_SHA256 = CONTEXT_SHA256
    v6.PLANNING_RESULT_SHA256 = PLANNING_RESULT_SHA256
    v6.EXPECTED_REQUEST_SHA256 = EXPECTED_REQUEST_SHA256
    v6.EXPECTED_PROMPT = EXPECTED_PROMPT
    v6.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v4.PINNED_PRIOR_EVIDENCE.update(V6_EVIDENCE)
    v6.configure_v6()
    v2.BASELINE_PAID_SUBMISSIONS = 288
    v2.BASELINE_RESERVED_USD = Decimal("100.80")
    v2.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v2.HARD_BUDGET_CAP_USD = Decimal("104.75")
    v2.accounting_document = accounting_document
    v2.load_v2_job = load_v7_job


def dry_run(value: str | Decimal) -> int:
    parse_budget(value)
    state = v4.preflight(value, ROOT)
    if state["record"]["positive_prompt"] != EXPECTED_PROMPT:
        raise RecoveryError("V7 preflight prompt changed")
    print(f"PASS: {v2.ENTRY.provider_run_id} uses verified {PLANNING_RUN_ID}")
    print("PASS: V7 background-only request validated under $101.15; no files written")
    return 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("positive value required")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("positive value required")
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
    configure_v7()
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
        v6.RecoveryError,
        v5.RecoveryError,
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
