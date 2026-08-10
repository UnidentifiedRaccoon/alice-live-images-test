#!/usr/bin/env python3
"""Run one immutable reversible framed-source V6 Veo experiment."""

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
    clipmaker_lite_promopages_10060_femibion_veo_recovery_v5 as v5,
)


v4 = v5.v4
v2 = v5.v2
RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v6"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
PLANNING_RUN_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v6-"
    "07-femibion-gotovites-k-beremennosti-06"
)
SOURCE_PATH = (
    "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v6/articles/"
    "07-femibion-gotovites-k-beremennosti/06.jpeg"
)
CONTEXT_PATH = (
    "PROMOPAGES-9884/PROMOPAGES-10060/recovery-v6/articles/"
    "07-femibion-gotovites-k-beremennosti/content.json"
)
SOURCE_URL = (
    "https://yastatic.net/s3/promopages-front-bundles/front-images/exp_video/"
    "_recovery_inputs/promopages-10060/femibion-07-06/v6/"
    "06--sha256-74764f50e6a2.jpeg"
)
SOURCE_SHA256 = "74764f50e6a2b6c307817c2862df40c8ed50367aa9f5e191106f22772397bb88"
CONTEXT_SHA256 = "998f1567400275e9115b979e13550fb68901d06df030313ebf29c818e2e6a3a9"
PLANNING_RESULT_SHA256 = (
    "95ae631ee8a365bc902270aa1ceb5d7958d99d2bc7e823493621beafb040c1a3"
)
EXPECTED_REQUEST_SHA256 = (
    "b6bcc541ad18e332e1adbadf3e1df7d43b3bca45b0e4042f06bc4e0d1310b0d6"
)
EXPECTED_PROMPT = v5.EXPECTED_PROMPT
REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("100.80")

V5_EVIDENCE = {
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v5/generation-manifest.json"): "2f062d6e425890d4151e0dcd34f1fa56f5e09b8c221c6da4d7c87971cdf50088",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v5/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json"): "7c99494cd2d6b0b72efc85cfebe9ab921173c9ad449401f22010dd4eed64323a",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v5/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"): "0cfd06f0e75f729ecb487f3b9e037c12284d08b4706cca4aa54bfab4722036ad",
}


class RecoveryError(RuntimeError):
    """Fail-closed V6 experiment error."""


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be a decimal amount") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError("V6 requires --budget-cap-usd 100.80 exactly")
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RecoveryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def accounting_document(value: str | Decimal) -> dict[str, Any]:
    parsed = Decimal(str(value))
    if parsed not in {Decimal("99.40"), REQUIRED_OPERATOR_BUDGET_CAP_USD}:
        raise RecoveryError("Unexpected V6 accounting literal")
    return {
        "currency": "USD",
        "baseline_paid_submissions": 287,
        "baseline_reserved_usd": 100.45,
        "recovery_paid_submissions": 1,
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 0.35,
        "aggregate_paid_submissions": 288,
        "aggregate_reserved_usd": 100.80,
        "operator_budget_cap_usd": 100.80,
        "hard_budget_cap_usd": 104.75,
        "hard_cap_headroom_usd": 3.95,
        "authorized_additional_budget_usd": 5.0,
        "automatic_paid_retries": False,
        "pricing_basis": "explicit user-authorized experiment budget",
    }


def load_v6_job(entry: Any, root: Path = ROOT) -> Any:
    if entry != v2.ENTRY:
        raise RecoveryError(f"Unexpected V6 entry: {entry.run_id}")
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
        raise RecoveryError("V6 Lite provenance/prompt binding differs")
    result = v2.read_json(root / expected_result)
    direction = result.get("inputs", {}).get("user_direction")
    if not isinstance(direction, str) or "Reversible framed-source experiment" not in direction:
        raise RecoveryError("V6 Lite framed-source intent differs")
    return job


def configure_v6() -> None:
    v5.RECOVERY_ID = RECOVERY_ID
    v5.PROVIDER_BATCH_ID = PROVIDER_BATCH_ID
    v5.RECOVERY_ROOT_REL = RECOVERY_ROOT_REL
    v5.GENERATION_MANIFEST_REL = GENERATION_MANIFEST_REL
    v5.PLANNING_RUN_ID = PLANNING_RUN_ID
    v5.SOURCE_PATH = SOURCE_PATH
    v5.CONTEXT_PATH = CONTEXT_PATH
    v5.SOURCE_URL = SOURCE_URL
    v5.SOURCE_SHA256 = SOURCE_SHA256
    v5.CONTEXT_SHA256 = CONTEXT_SHA256
    v5.PLANNING_RESULT_SHA256 = PLANNING_RESULT_SHA256
    v5.EXPECTED_REQUEST_SHA256 = EXPECTED_REQUEST_SHA256
    v5.EXPECTED_PROMPT = EXPECTED_PROMPT
    v5.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v4.PINNED_PRIOR_EVIDENCE.update(V5_EVIDENCE)
    v5.configure_v5()
    v2.BASELINE_PAID_SUBMISSIONS = 287
    v2.BASELINE_RESERVED_USD = Decimal("100.45")
    v2.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v2.HARD_BUDGET_CAP_USD = Decimal("104.75")
    v2.accounting_document = accounting_document
    v2.load_v2_job = load_v6_job


def dry_run(value: str | Decimal) -> int:
    parse_budget(value)
    state = v4.preflight(value, ROOT)
    if state["record"]["positive_prompt"] != EXPECTED_PROMPT:
        raise RecoveryError("V6 preflight prompt changed")
    print(f"PASS: {v2.ENTRY.provider_run_id} uses verified {PLANNING_RUN_ID}")
    print("PASS: V6 framed-source request validated under $100.80; no files written")
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
    configure_v6()
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
