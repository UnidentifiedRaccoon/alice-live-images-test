#!/usr/bin/env python3
"""Run one immutable source-crop V4 experiment for Femibion 07/image 06.

The exact V2 prompt and seed are retained.  Only the first-frame bytes, their
public URL, and the provenance-bound derived context differ.  The coordinator
writes a fresh provider identity and never retries or selects a fallback.
"""

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
    clipmaker_lite_promopages_10060_femibion_veo_recovery_v2 as v2,
)


RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v4"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
RECOVERY_MANIFEST_REL = RECOVERY_ROOT_REL / "recovery-manifest.json"
COMBINED_SELECTION_MANIFEST_REL = (
    RECOVERY_ROOT_REL / "combined-selection-manifest.json"
)

PLANNING_RUN_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v4-"
    "07-femibion-gotovites-k-beremennosti-06"
)
SOURCE_PATH = (
    "PROMOPAGES-9857/PROMOPAGES-10060/recovery-v4/articles/"
    "07-femibion-gotovites-k-beremennosti/06.jpeg"
)
CONTEXT_PATH = (
    "PROMOPAGES-9884/PROMOPAGES-10060/recovery-v4/articles/"
    "07-femibion-gotovites-k-beremennosti/content.json"
)
SOURCE_URL = (
    "https://yastatic.net/s3/promopages-front-bundles/front-images/exp_video/"
    "_recovery_inputs/promopages-10060/femibion-07-06/v4/"
    "06--sha256-f3eac13ca2c7.jpeg"
)
SOURCE_SHA256 = "f3eac13ca2c71c7cec3a1a860c701caea68728a3f9dc9e77c1d05b2455143ce9"
CONTEXT_SHA256 = "d1c65a16f8d24e2bde20704f82376b4167211fa8d62fccd19ed75f2def0105ca"
PLANNING_RESULT_SHA256 = (
    "bead524d13e018c0905be09440226c5367d6ae0c40122a19dc270d3b13b49d35"
)
EXPECTED_REQUEST_SHA256 = (
    "e469d1aef96cb0a1fd96506a8af4e558590934049b5c4ad4b7ee5d5a4594568d"
)
EXPECTED_PROMPT = (
    "Locked camera. Very subtle natural blinking and breathing only. "
    "The composition and every visible object stay unchanged."
)

REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("100.10")
AUTHORIZED_EXPERIMENT_HARD_CAP_USD = Decimal("104.75")

PINNED_PRIOR_EVIDENCE = {
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v2/generation-manifest.json"): "161afc67e957dcd433eab519d2bf369c0aa4fa703360fe380b7cd2b37b6192b8",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v2/recovery-manifest.json"): "64ab1e3ac9be2bcd9a5c6af9c591fcaf7763aee78d278d2ee308e56e767abaea",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v2/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"): "f796052a0573350ee9611d0f4d59375d201411d73b94440d99352cb3ebb1acde",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v3/generation-manifest.json"): "33d36a5cf40008b250bf9f96673ce8f39e95f1b8b7726fa13b4769597fd4afab",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v3/recovery-manifest.json"): "39aa47cfb78e325825a53ee1536127b4c74c8e4548b92752022d45da528d5d3d",
    Path("clipmaker-lite-test/runs/promopages-10060-femibion-veo-recovery-20260810-v3/videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"): "2f60a081e3779214de61f6b8ef3fd1b14f6e93eae5f1029c06601fe1970de247",
}


class RecoveryError(RuntimeError):
    """Fail-closed V4 experiment error."""


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be a decimal amount") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError("V4 requires --budget-cap-usd 100.10 exactly")
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RecoveryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def accounting_document(value: str | Decimal) -> dict[str, Any]:
    parsed = Decimal(str(value))
    if parsed not in {Decimal("99.40"), REQUIRED_OPERATOR_BUDGET_CAP_USD}:
        raise RecoveryError("Unexpected V4 accounting literal")
    return {
        "currency": "USD",
        "baseline_paid_submissions": 285,
        "baseline_reserved_usd": 99.75,
        "recovery_paid_submissions": 1,
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 0.35,
        "aggregate_paid_submissions": 286,
        "aggregate_reserved_usd": 100.10,
        "operator_budget_cap_usd": 100.10,
        "hard_budget_cap_usd": 104.75,
        "hard_cap_headroom_usd": 4.65,
        "authorized_additional_budget_usd": 5.0,
        "maximum_additional_paid_submissions": 14,
        "automatic_paid_retries": False,
        "pricing_basis": "explicit user-authorized experiment budget",
    }


def snapshot_prior_evidence(root: Path = ROOT) -> dict[str, str]:
    snapshot = v2.snapshot_v1_evidence(root)
    for relative, expected in PINNED_PRIOR_EVIDENCE.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise RecoveryError(f"Missing prior experiment evidence: {path}")
        actual = v2.sha256_file(path)
        if actual != expected:
            raise RecoveryError(f"Prior experiment evidence changed: {path}")
        snapshot[relative.as_posix()] = actual
        if relative.name == "06.run.json":
            with path.open("r", encoding="utf-8") as stream:
                run = json.load(stream)
            if (
                run.get("status") != "provider-failed"
                or run.get("provider_may_be_active") is not False
                or run.get("media") is not None
                or v2.FILTER_MARKER not in str(run.get("error"))
            ):
                raise RecoveryError(f"Prior terminal evidence changed: {path}")
    return snapshot


def assert_request(request: dict[str, Any], job: Any) -> None:
    expected_frames = [
        {
            "type": "image_url",
            "image_url": {"url": SOURCE_URL},
            "frame_type": "first_frame",
        }
    ]
    if (
        request.get("model") != v2.MODEL_ID
        or request.get("prompt") != EXPECTED_PROMPT
        or request.get("prompt") != job.positive_prompt
        or request.get("duration") != 4
        or request.get("resolution") != "1080p"
        or request.get("aspect_ratio") != "16:9"
        or request.get("seed") != 9681
        or request.get("generate_audio") is not False
        or request.get("frame_images") != expected_frames
        or request.get("provider")
        != {
            "options": {
                "google-vertex": {"parameters": {"enhancePrompt": True}}
            }
        }
        or "loop" in request
    ):
        raise RecoveryError("V4 request changed outside the source-frame factor")
    fingerprint = v2.transport.request_fingerprint(
        request, v2.provider_sample(v2.ENTRY)
    )
    if fingerprint != EXPECTED_REQUEST_SHA256:
        raise RecoveryError("V4 request fingerprint changed")


def load_v4_job(entry: Any, root: Path = ROOT) -> Any:
    if entry != v2.ENTRY:
        raise RecoveryError(f"Unexpected V4 entry: {entry.run_id}")
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
        raise RecoveryError("V4 Lite provenance/prompt binding differs")
    result = v2.read_json(root / expected_result)
    direction = result.get("inputs", {}).get("user_direction")
    models = result.get("models") if isinstance(result, dict) else None
    if (
        not isinstance(direction, str)
        or "Source-factor experiment" not in direction
        or not isinstance(models, list)
        or len(models) != 1
        or not isinstance(models[0], dict)
        or models[0].get("model_id") != v2.MODEL_ID
        or models[0].get("positive_prompt") != EXPECTED_PROMPT
    ):
        raise RecoveryError("V4 Lite source-factor intent differs")
    forbidden = set(v2.FORBIDDEN_PROMPT_TERMS)
    present = sorted(set(re.findall(r"[a-z]+", job.positive_prompt.casefold())) & forbidden)
    if present:
        raise RecoveryError(f"V4 provider prompt contains forbidden terms: {present}")
    return job


def configure_v4() -> None:
    sample = v2.RecoverySample(
        sample_id="07-femibion-gotovites-k-beremennosti-06",
        article_slug="07-femibion-gotovites-k-beremennosti",
        image_id="06",
        filename="06.jpeg",
        source_sha256=SOURCE_SHA256,
        width=1920,
        height=1080,
        bound_source_path=SOURCE_PATH,
        bound_context_path=CONTEXT_PATH,
        lite_run_id=PLANNING_RUN_ID,
    )
    v2.RECOVERY_ID = RECOVERY_ID
    v2.PROVIDER_BATCH_ID = PROVIDER_BATCH_ID
    v2.RECOVERY_ROOT_REL = RECOVERY_ROOT_REL
    v2.GENERATION_MANIFEST_REL = GENERATION_MANIFEST_REL
    v2.RECOVERY_MANIFEST_REL = RECOVERY_MANIFEST_REL
    v2.COMBINED_SELECTION_MANIFEST_REL = COMBINED_SELECTION_MANIFEST_REL
    v2.SAMPLE = sample
    v2.ENTRY = v2.RecoveryEntry(sample, v2.MODEL_ID)
    v2.ENTRIES = (v2.ENTRY,)
    v2.CONTEXT_SHA256 = CONTEXT_SHA256
    v2.SOURCE_URL = SOURCE_URL
    v2.LOGICAL_KEY = {
        "article_slug": sample.article_slug,
        "image_id": sample.image_id,
        "model_id": v2.MODEL_ID,
    }
    v2.EXPECTED_PLANNING_RESULT_SHA256 = PLANNING_RESULT_SHA256
    v2.EXPECTED_REQUEST_SHA256 = EXPECTED_REQUEST_SHA256
    v2.BASELINE_PAID_SUBMISSIONS = 285
    v2.BASELINE_RESERVED_USD = Decimal("99.75")
    v2.RECOVERY_PAID_SUBMISSIONS = 1
    v2.RECOVERY_RESERVED_USD = Decimal("0.35")
    v2.REQUIRED_OPERATOR_BUDGET_CAP_USD = REQUIRED_OPERATOR_BUDGET_CAP_USD
    v2.HARD_BUDGET_CAP_USD = AUTHORIZED_EXPERIMENT_HARD_CAP_USD
    v2.accounting_document = accounting_document
    v2.assert_request = assert_request
    v2.load_v2_job = load_v4_job
    v2.transport.MODEL_CONFIGS[v2.MODEL_ID]["seed"] = 9681


def preflight(budget_cap_usd: str | Decimal, root: Path = ROOT) -> dict[str, Any]:
    parse_budget(budget_cap_usd)
    before = snapshot_prior_evidence(root)
    state = v2.preflight(root, budget_cap_usd=budget_cap_usd)
    if snapshot_prior_evidence(root) != before:
        raise RecoveryError("Prior evidence changed during V4 preflight")
    return state


def dry_run(budget_cap_usd: str | Decimal, root: Path = ROOT) -> int:
    state = preflight(budget_cap_usd, root)
    request = state["record"]["request"]
    print(
        f"PASS: {v2.ENTRY.provider_run_id} uses verified {PLANNING_RUN_ID}",
        flush=True,
    )
    print(
        "PASS: only the first-frame source changed; one Veo submission "
        "validated under the $100.10 cap; no files written",
        flush=True,
    )
    if request.get("frame_images", [{}])[0].get("image_url", {}).get("url") != SOURCE_URL:
        raise RecoveryError("V4 public crop URL is not bound into the request")
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
    if not allow_external_processing:
        raise RecoveryError("V4 generate requires --allow-external-processing")
    preflight(budget_cap_usd, root)
    before = snapshot_prior_evidence(root)
    with v2.recovery_run_lock(root):
        v2._validate_mode_state(mode, root)
        with v2.configured_native(root):
            rows = v2.native.materialize(root)
            if len(rows) != 1 or rows[0]["entry"] != v2.ENTRY:
                raise RecoveryError("V4 materialized matrix is not exactly one job")
            result = v2.native.main(
                [
                    "run",
                    "--veo31-concurrency",
                    "1",
                    "--timeout",
                    str(timeout),
                    "--poll-interval",
                    str(poll_interval),
                    "--allow-external-processing",
                    "--run-id",
                    v2.ENTRY.provider_run_id,
                ],
                root,
            )
    if snapshot_prior_evidence(root) != before:
        raise RecoveryError("Prior evidence changed during V4 generation")
    print(
        f"V4 generation manifest: {GENERATION_MANIFEST_REL.as_posix()}",
        flush=True,
    )
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
    configure_v4()
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
