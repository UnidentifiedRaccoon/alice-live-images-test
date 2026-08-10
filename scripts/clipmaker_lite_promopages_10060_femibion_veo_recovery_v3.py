#!/usr/bin/env python3
"""Run the explicit V3 seed-only Femibion Veo recovery experiment.

V3 reuses the verified Clipmaker Lite V2 plan and the exact same source image,
prompt, route and runtime.  It changes only the Veo seed, writes a fresh
provider identity, pins every V2 receipt, and stops after one paid submission.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import (  # noqa: E402
    clipmaker_lite_promopages_10060_femibion_veo_recovery_v2 as v2,
)


RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v3"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
RECOVERY_MANIFEST_REL = RECOVERY_ROOT_REL / "recovery-manifest.json"
COMBINED_SELECTION_MANIFEST_REL = (
    RECOVERY_ROOT_REL / "combined-selection-manifest.json"
)

V2_ROOT_REL = Path("clipmaker-lite-test/runs") / (
    "promopages-10060-femibion-veo-recovery-20260810-v2"
)
V2_RECOVERY_MANIFEST_REL = V2_ROOT_REL / "recovery-manifest.json"
V2_RUN_REL = V2_ROOT_REL / (
    "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"
)
V2_EVIDENCE_SHA256 = {
    V2_ROOT_REL / "generation-manifest.json": (
        "161afc67e957dcd433eab519d2bf369c0aa4fa703360fe380b7cd2b37b6192b8"
    ),
    V2_RECOVERY_MANIFEST_REL: (
        "64ab1e3ac9be2bcd9a5c6af9c591fcaf7763aee78d278d2ee308e56e767abaea"
    ),
    V2_ROOT_REL / "combined-selection-manifest.json": (
        "35b51e67df496560e8e3badee6dc202049658706f47fca5a20a2ff3aed9d145b"
    ),
    V2_ROOT_REL
    / "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json": (
        "ad358837f0b256d41bcd08b35d7c0d31092b4a6f3a2f8c89441a489bf94547cf"
    ),
    V2_RUN_REL: (
        "f796052a0573350ee9611d0f4d59375d201411d73b94440d99352cb3ebb1acde"
    ),
}

V2_REQUEST_SHA256 = (
    "3e82fe9aa019bea8225c28f0e8fbaef1a621d2e80fd4d60ed88eae9e268115fc"
)
V3_REQUEST_SHA256 = (
    "0fc4588d29046e5a6d40a7c74e0711dea4f8ce1e8b801f7e64575eedb3cc4b2a"
)
V2_SEED = 9681
V3_SEED = 27183
REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("99.75")
HARD_BUDGET_CAP_USD = Decimal("100.00")

_ORIGINAL_RECOVERY_DOCUMENT = v2.recovery_document
_ORIGINAL_COMBINED_DOCUMENT = v2.combined_selection_document
_ORIGINAL_ACCOUNTING_DOCUMENT = v2.accounting_document


class RecoveryError(RuntimeError):
    """A fail-closed V3 experiment error."""


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"Cannot read JSON {path}: {exc}") from exc


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be a decimal amount") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError(
            "this immutable V3 experiment requires --budget-cap-usd 99.75 exactly"
        )
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RecoveryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def snapshot_v2_evidence(root: Path = ROOT) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for relative, expected in V2_EVIDENCE_SHA256.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise RecoveryError(f"Missing immutable V2 evidence: {path}")
        actual = v2.sha256_file(path)
        if actual != expected:
            raise RecoveryError(f"Immutable V2 evidence changed: {path}")
        snapshot[relative.as_posix()] = actual
    run = read_json(root / V2_RUN_REL)
    if (
        run.get("status") != "provider-failed"
        or run.get("request_sha256") != V2_REQUEST_SHA256
        or run.get("provider_may_be_active") is not False
        or run.get("media") is not None
        or v2.FILTER_MARKER not in str(run.get("error"))
    ):
        raise RecoveryError("V2 terminal provider evidence changed")
    return snapshot


def assert_v3_request(request: dict[str, Any], job: Any) -> None:
    baseline_run = read_json(ROOT / V2_RUN_REL)
    baseline = baseline_run.get("request")
    if not isinstance(baseline, dict):
        raise RecoveryError("V2 request evidence is missing")
    normalized = copy.deepcopy(request)
    if normalized.get("seed") != V3_SEED:
        raise RecoveryError("V3 request does not contain the frozen seed")
    normalized["seed"] = V2_SEED
    if normalized != baseline or request.get("prompt") != job.positive_prompt:
        raise RecoveryError("V3 request differs from V2 by more than seed")
    fingerprint = v2.transport.request_fingerprint(
        request, v2.provider_sample(v2.ENTRY)
    )
    if (
        baseline_run.get("request_sha256") != V2_REQUEST_SHA256
        or fingerprint != V3_REQUEST_SHA256
        or fingerprint == V2_REQUEST_SHA256
    ):
        raise RecoveryError("V3 request fingerprint is not the frozen seed variant")


def accounting_document_v3(value: str | Decimal) -> dict[str, Any]:
    """Return V3 accounting while tolerating V2's frozen internal literal.

    The reused V2 document builder calls ``accounting_document("99.40")`` as
    an immutable self-check.  V3 intentionally advances that exact baseline by
    one paid submission, so both the legacy baseline literal and the operator's
    V3 cap resolve to the same V3 accounting document.
    """

    parsed = Decimal(str(value))
    if parsed not in {Decimal("99.40"), REQUIRED_OPERATOR_BUDGET_CAP_USD}:
        raise RecoveryError("Unexpected accounting cap in V3 document builder")
    return {
        "currency": "USD",
        "baseline_paid_submissions": 284,
        "baseline_reserved_usd": 99.40,
        "recovery_paid_submissions": 1,
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 0.35,
        "aggregate_paid_submissions": 285,
        "aggregate_reserved_usd": 99.75,
        "operator_budget_cap_usd": 99.75,
        "hard_budget_cap_usd": 100.0,
        "hard_cap_headroom_usd": 0.25,
        "maximum_new_paid_submissions": 1,
        "automatic_paid_retries": False,
        "pricing_basis": "frozen local PROMOPAGES-10060 accounting evidence",
    }


def recovery_document_v3(*args: Any, **kwargs: Any) -> dict[str, Any]:
    document = _ORIGINAL_RECOVERY_DOCUMENT(*args, **kwargs)
    document["manifest_role"] = (
        "promopages-10060-femibion-veo-content-filter-recovery-v3-seed"
    )
    document["experiment"] = {
        "factor": "seed",
        "control_iteration": 2,
        "control_request_sha256": V2_REQUEST_SHA256,
        "control_seed": V2_SEED,
        "candidate_seed": V3_SEED,
        "all_other_request_fields_equal": True,
    }
    for output in document.get("outputs", []):
        output["selected_attempt"] = "content-filter-recovery-v3-seed"
        recovery = output.setdefault("recovery", {})
        recovery["prior_v2"] = {
            "manifest_path": V2_RECOVERY_MANIFEST_REL.as_posix(),
            "manifest_sha256": V2_EVIDENCE_SHA256[V2_RECOVERY_MANIFEST_REL],
            "status": "provider-failed",
            "request_sha256": V2_REQUEST_SHA256,
        }
        recovery["experiment"] = copy.deepcopy(document["experiment"])
    return document


def combined_selection_document_v3(*args: Any, **kwargs: Any) -> dict[str, Any]:
    document = _ORIGINAL_COMBINED_DOCUMENT(*args, **kwargs)
    v2_recovery = read_json(ROOT / V2_RECOVERY_MANIFEST_REL)
    v2_outputs = v2_recovery.get("outputs")
    if not isinstance(v2_outputs, list) or len(v2_outputs) != 1:
        raise RecoveryError("V2 recovery manifest output set changed")
    v2_output = v2_outputs[0]
    if (
        v2_output.get("status") != "provider-failed"
        or v2_output.get("request_sha256") == V3_REQUEST_SHA256
    ):
        raise RecoveryError("V2 failed attempt cannot feed the V3 audit chain")

    attempts = document.get("attempt_manifests")
    if not isinstance(attempts, list) or len(attempts) != 2:
        raise RecoveryError("Unexpected combined attempt manifest set")
    attempts[1]["iteration"] = 3
    attempts.insert(
        1,
        {
            "iteration": 2,
            "path": V2_RECOVERY_MANIFEST_REL.as_posix(),
            "sha256": V2_EVIDENCE_SHA256[V2_RECOVERY_MANIFEST_REL],
            "accepted_output_count": 0,
            "ready_for_combined_selection": False,
        },
    )
    failed = document.get("failed_attempt_chain")
    if not isinstance(failed, list) or len(failed) != 3:
        raise RecoveryError("V1 failed-attempt chain changed")
    failed.append(
        {
            "iteration": 2,
            "provider_run_id": v2_output.get("provider_run_id"),
            "provider_job_id": v2_output.get("provider_job_id"),
            "status": v2_output.get("recorded_status"),
            "request_sha256": V2_REQUEST_SHA256,
            "prompt": v2_output.get("positive_prompt"),
            "error": v2_output.get("error"),
        }
    )
    selection = document.get("selection")
    if not isinstance(selection, list) or len(selection) != 2:
        raise RecoveryError("Unexpected V3 selection set")
    selection[0]["source_iteration"] = 3
    document["experiment"] = {
        "factor": "seed",
        "control_iteration": 2,
        "control_seed": V2_SEED,
        "candidate_iteration": 3,
        "candidate_seed": V3_SEED,
        "all_other_request_fields_equal": True,
    }
    return document


def configure_v3() -> None:
    v2.RECOVERY_ID = RECOVERY_ID
    v2.PROVIDER_BATCH_ID = PROVIDER_BATCH_ID
    v2.RECOVERY_ROOT_REL = RECOVERY_ROOT_REL
    v2.GENERATION_MANIFEST_REL = GENERATION_MANIFEST_REL
    v2.RECOVERY_MANIFEST_REL = RECOVERY_MANIFEST_REL
    v2.COMBINED_SELECTION_MANIFEST_REL = COMBINED_SELECTION_MANIFEST_REL
    v2.BASELINE_PAID_SUBMISSIONS = 284
    v2.BASELINE_RESERVED_USD = Decimal("99.40")
    v2.RECOVERY_PAID_SUBMISSIONS = 1
    v2.RECOVERY_RESERVED_USD = Decimal("0.35")
    v2.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v2.HARD_BUDGET_CAP_USD = HARD_BUDGET_CAP_USD
    v2.EXPECTED_REQUEST_SHA256 = V3_REQUEST_SHA256
    v2.accounting_document = accounting_document_v3
    v2.assert_request = assert_v3_request
    v2.recovery_document = recovery_document_v3
    v2.combined_selection_document = combined_selection_document_v3
    v2.transport.MODEL_CONFIGS[v2.MODEL_ID]["seed"] = V3_SEED


def dry_run(budget_cap_usd: str | Decimal, root: Path = ROOT) -> int:
    parse_budget(budget_cap_usd)
    before = snapshot_v2_evidence(root)
    state = v2.preflight(root, budget_cap_usd=budget_cap_usd)
    if snapshot_v2_evidence(root) != before:
        raise RecoveryError("V2 evidence changed during V3 dry-run")
    request = state["record"]["request"]
    if request.get("seed") != V3_SEED:
        raise RecoveryError("V3 preflight did not select the frozen seed")
    print(
        f"PASS: {v2.ENTRY.provider_run_id} reuses verified "
        f"{v2.SAMPLE.planning_run_id}",
        flush=True,
    )
    print(
        "PASS: V3 request equals V2 except seed 9681 -> 27183; one Veo "
        "submission validated under the $99.75 cap; no files written",
        flush=True,
    )
    return 0


def run_generation(
    mode: str,
    *,
    budget_cap_usd: str | Decimal,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
    root: Path = ROOT,
) -> int:
    parse_budget(budget_cap_usd)
    before = snapshot_v2_evidence(root)
    result = v2.run_generation(
        mode,
        budget_cap_usd=budget_cap_usd,
        root=root,
        allow_external_processing=allow_external_processing,
        timeout=timeout,
        poll_interval=poll_interval,
    )
    if snapshot_v2_evidence(root) != before:
        raise RecoveryError("V2 evidence changed during V3 generation")
    return result


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
    configure_v3()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            return dry_run(args.budget_cap_usd)
        return run_generation(
            args.command,
            budget_cap_usd=args.budget_cap_usd,
            allow_external_processing=args.allow_external_processing,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )
    except (
        RecoveryError,
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
