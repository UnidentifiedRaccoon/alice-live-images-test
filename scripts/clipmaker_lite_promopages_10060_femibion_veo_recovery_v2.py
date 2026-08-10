#!/usr/bin/env python3
"""Run one isolated V2 recovery attempt for Femibion article 07 image 06.

V1 remains immutable evidence: its article 08 image 05 video succeeded while
article 07 image 06 was filtered for a third time.  This coordinator consumes
one newly authored and verified Clipmaker Lite plan whose prompt intentionally
isolates the prompt factor, creates one new Veo provider identity, and writes a
separate combined-selection manifest selecting V1/08 and V2/07 only when both
media records are accepted.  It never performs discovery, fallback, automatic
retry, S3 upload, canonical aggregate mutation, or demo mutation.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_promopages_10060_femibion_veo_recovery as v1  # noqa: E402
from scripts import clipmaker_lite_promopages_10060_pipeline as pipeline  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
MODEL_ID = "google/veo-3.1-lite"
MODEL_IDS = (MODEL_ID,)
RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v2"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"

CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
CANONICAL_MANIFEST_REL = Path("clipmaker-lite-test/promopages-10060-manifest.json")
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
RECOVERY_MANIFEST_REL = RECOVERY_ROOT_REL / "recovery-manifest.json"
COMBINED_SELECTION_MANIFEST_REL = (
    RECOVERY_ROOT_REL / "combined-selection-manifest.json"
)
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")

V1_RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v1"
V1_PROVIDER_BATCH_ID = f"{V1_RECOVERY_ID}-provider"
V1_ROOT_REL = Path("clipmaker-lite-test/runs") / V1_RECOVERY_ID
V1_GENERATION_MANIFEST_REL = V1_ROOT_REL / "generation-manifest.json"
V1_RECOVERY_MANIFEST_REL = V1_ROOT_REL / "recovery-manifest.json"

EXPECTED_CONTRACT_VERSION = "2.0.8"
EXPECTED_ROUTE_ADAPTER = "eliza-openrouter"
EXPECTED_ROUTE_TRANSPORT = "eliza-video-jobs"
EXPECTED_ROUTE_PROVIDER = "google-vertex"
EXPECTED_ROUTE_CAPACITY = 3
FILTER_MARKER = "Video generation completed with no output (content may have been filtered)"
ACCEPTED_STATUSES = frozenset({"succeeded", "verification-failed"})

EXPECTED_POSITIVE_PROMPT = (
    "Locked camera. Very subtle natural blinking and breathing only. "
    "The composition and every visible object stay unchanged."
)
FORBIDDEN_PROMPT_TERMS = (
    "medical",
    "pregnancy",
    "phone",
    "smartphone",
    "screen",
    "device",
    "hand",
    "finger",
    "touch",
    "swipe",
    "tap",
    "gesture",
)
EXPECTED_PLANNING_RESULT_SHA256 = (
    "47a3579def0b40bf845609604e342fee3f5bf49d6cf8b223ed4e72590a3ff944"
)
EXPECTED_REQUEST_SHA256 = (
    "3e82fe9aa019bea8225c28f0e8fbaef1a621d2e80fd4d60ed88eae9e268115fc"
)
OLD_REQUEST_SHA256 = (
    "f7f0c0c20f702b1deb1b5ee3a8e28d2487c8c3988653792518b03a223afa7a01"
)
V1_REQUEST_SHA256 = (
    "d80e38498bd48c2318efda51a5335e2a5fd51f0bbf6f2d418a2c594f873fb6e1"
)

BASELINE_PAID_SUBMISSIONS = 283
BASELINE_RESERVED_USD = Decimal("99.05")
RECOVERY_PAID_SUBMISSIONS = 1
ACCOUNTING_COST_PER_OUTPUT_USD = Decimal("0.35")
RECOVERY_RESERVED_USD = Decimal("0.35")
REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("99.40")
HARD_BUDGET_CAP_USD = Decimal("100.00")

ORIGINAL_SUPERSEDES_07 = (
    "promopages-10060-lite-all-images-20260805-v2-terminal-retry-v1-"
    "6243bd1bbb1a1e3fe253-07-femibion-gotovites-k-beremennosti-06-"
    "veo-3-1-lite"
)
ORIGINAL_SUPERSEDES_08 = (
    "promopages-10060-lite-all-images-20260805-v2-terminal-retry-v1-"
    "0cc5261325a58f1785ee-08-femibion-grudnoe-vskarmlivanie-05-"
    "veo-3-1-lite"
)
V1_FAILED_PROVIDER_RUN_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v1-provider-"
    "07-femibion-gotovites-k-beremennosti-06-veo-3-1-lite"
)
V1_SUCCESS_PROVIDER_RUN_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v1-provider-"
    "08-femibion-grudnoe-vskarmlivanie-05-veo-3-1-lite"
)

V1_EVIDENCE_SHA256 = {
    V1_GENERATION_MANIFEST_REL: (
        "096d1f16ee8bb0f550c356ed32f6edc6e7f779edfabb54e236042d9635b44dd1"
    ),
    V1_RECOVERY_MANIFEST_REL: (
        "3f0578942d8253d6c627f5a30c215121503aef1ef72df3057090d62a00043478"
    ),
    V1_ROOT_REL
    / "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json": (
        "e46bad806f4d9811967702e23862bd8dbfc033ec3171b3b56ab65348a6d1e7dc"
    ),
    V1_ROOT_REL
    / "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json": (
        "2946444b1ca4cbd603e728c9de4df4349c1254cea4243e896fdc20e884346da7"
    ),
    V1_ROOT_REL
    / "videos/08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.prompt.json": (
        "635e3485693a7882525e383105991d04fe6ac47c83b9ec4eefdaea73ffef1dc2"
    ),
    V1_ROOT_REL
    / "videos/08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.run.json": (
        "969dcb6420437ce76abd1dce477cf3a89756a7dedb78cf83aaf0db52b79183b6"
    ),
    V1_ROOT_REL
    / "videos/08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.mp4": (
        "be2a072ffe4fe3934563e148956c3d05bcb6123e8a878829b18d9adead5af153"
    ),
}

PRIMARY_PROMPT_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/"
    "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json"
)
PRIMARY_RUN_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/"
    "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"
)
RETRY_PROMPT_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/"
    "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/videos/"
    "veo-3.1-lite/06.prompt.json"
)
RETRY_RUN_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/"
    "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/videos/"
    "veo-3.1-lite/06.run.json"
)
RETRY_ENVELOPE_REL = Path(
    "clipmaker-lite-test/runs/promopages-10060-lite-all-images-20260805-v2/"
    "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/retry.json"
)
EARLIER_EVIDENCE_SHA256 = {
    PRIMARY_PROMPT_REL: (
        "2f28a4279c77fc93df39914fdb995441b370d210767a3a17276fda20a909a9a1"
    ),
    PRIMARY_RUN_REL: (
        "9a4527b55d846de60f52d4a4cbf54f600c748919c7d75babcc2d2059d6861c3f"
    ),
    RETRY_PROMPT_REL: (
        "5d4438188907c6f45bcd4925709962b0f2a6e49ef5007a769145aa4c6035583d"
    ),
    RETRY_RUN_REL: (
        "b4f6561f1bc0084c81ecd3c47c3c6158a1bc08f0049fa286875da091daa3bc8d"
    ),
    RETRY_ENVELOPE_REL: (
        "5b26c05000069a0cc89513bf5a37dde497d956a7699b4c4a921bddee9d66d452"
    ),
}


class RecoveryError(RuntimeError):
    """A fail-closed, user-actionable V2 recovery error."""


@dataclass(frozen=True)
class RecoverySample(native.Sample):
    bound_source_path: str
    bound_context_path: str
    lite_run_id: str

    @property
    def source_path(self) -> str:
        return self.bound_source_path

    @property
    def context_path(self) -> str:
        return self.bound_context_path

    @property
    def planning_run_id(self) -> str:
        return self.lite_run_id


@dataclass(frozen=True)
class RecoveryEntry(native.Entry):
    @property
    def provider_run_id(self) -> str:
        return (
            f"{PROVIDER_BATCH_ID}-{self.sample.sample_id}-"
            f"{native.MODEL_SUFFIXES[self.model_id]}"
        )


SAMPLE = RecoverySample(
    sample_id="07-femibion-gotovites-k-beremennosti-06",
    article_slug="07-femibion-gotovites-k-beremennosti",
    image_id="06",
    filename="06.jpeg",
    source_sha256=(
        "35c6fd00f399b2061746d6a27fc9f01adeedd25c3ae5ff80d70b9439b9b4ad12"
    ),
    width=2400,
    height=1600,
    bound_source_path=(
        "PROMOPAGES-9857/PROMOPAGES-10060/articles/"
        "07-femibion-gotovites-k-beremennosti/06.jpeg"
    ),
    bound_context_path=(
        "PROMOPAGES-9884/PROMOPAGES-10060/articles/"
        "07-femibion-gotovites-k-beremennosti/content.json"
    ),
    lite_run_id=(
        "promopages-10060-femibion-veo-recovery-20260810-v2-"
        "07-femibion-gotovites-k-beremennosti-06"
    ),
)
ENTRY = RecoveryEntry(SAMPLE, MODEL_ID)
ENTRIES = (ENTRY,)
CONTEXT_SHA256 = (
    "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c"
)
SOURCE_URL = (
    "https://avatars.mds.yandex.net/get-promoarticles/5096941/"
    "pub_685a45c483113703283d5b0e_685ab42c046a3d4397850a85/orig"
)
LOGICAL_KEY = {
    "article_slug": SAMPLE.article_slug,
    "image_id": SAMPLE.image_id,
    "model_id": MODEL_ID,
}

_NATIVE_LOAD_LITE_JOB = native.load_lite_job
_NATIVE_PROMPT_ARTIFACT = native.prompt_artifact
_NATIVE_INITIAL_RUN = native.initial_run
_NATIVE_MATERIALIZE_ENTRY = native.materialize_entry


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise RecoveryError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecoveryError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RecoveryError(f"Cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _safe_relative_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RecoveryError(f"{label} must be a non-empty workspace-relative path")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise RecoveryError(f"Unsafe {label}: {value!r}")
    return Path(*parsed.parts)


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be a decimal USD amount") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError(
            "this immutable V2 recovery requires --budget-cap-usd 99.40 exactly"
        )
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        return parse_budget(value)
    except RecoveryError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def accounting_document(value: str | Decimal) -> dict[str, Any]:
    operator_cap = parse_budget(value)
    if (
        BASELINE_RESERVED_USD + RECOVERY_RESERVED_USD
        != REQUIRED_OPERATOR_BUDGET_CAP_USD
        or RECOVERY_RESERVED_USD
        != RECOVERY_PAID_SUBMISSIONS * ACCOUNTING_COST_PER_OUTPUT_USD
        or operator_cap > HARD_BUDGET_CAP_USD
    ):
        raise RecoveryError("Femibion V2 accounting constants are inconsistent")
    return {
        "currency": "USD",
        "baseline_paid_submissions": BASELINE_PAID_SUBMISSIONS,
        "baseline_reserved_usd": float(BASELINE_RESERVED_USD),
        "recovery_paid_submissions": RECOVERY_PAID_SUBMISSIONS,
        "accounting_cost_per_output_usd": float(ACCOUNTING_COST_PER_OUTPUT_USD),
        "recovery_reserved_usd": float(RECOVERY_RESERVED_USD),
        "aggregate_paid_submissions": (
            BASELINE_PAID_SUBMISSIONS + RECOVERY_PAID_SUBMISSIONS
        ),
        "aggregate_reserved_usd": float(REQUIRED_OPERATOR_BUDGET_CAP_USD),
        "operator_budget_cap_usd": float(operator_cap),
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "hard_cap_headroom_usd": float(HARD_BUDGET_CAP_USD - operator_cap),
        "maximum_new_paid_submissions": 1,
        "automatic_paid_retries": False,
        "pricing_basis": "frozen local PROMOPAGES-10060 accounting evidence",
    }


def validate_route(root: Path = ROOT) -> dict[str, Any]:
    route = v1.validate_route(root)
    if (
        route.get("model_id") != MODEL_ID
        or route.get("adapter") != EXPECTED_ROUTE_ADAPTER
        or route.get("transport") != EXPECTED_ROUTE_TRANSPORT
        or route.get("provider_key") != EXPECTED_ROUTE_PROVIDER
        or route.get("capacity") != EXPECTED_ROUTE_CAPACITY
        or route.get("automatic_fallback") is not False
        or route.get("normal_run_discovery") is not False
    ):
        raise RecoveryError("Exact Veo 3.1 Lite route changed")
    return route


def validate_contract(root: Path = ROOT) -> dict[str, Any]:
    contract = v1.validate_contract(root)
    if contract.get("contract_version") != EXPECTED_CONTRACT_VERSION:
        raise RecoveryError("Current Clipmaker Lite contract is not 2.0.8")
    return contract


def _validate_pinned_files(
    records: dict[Path, str],
    root: Path,
    *,
    label: str,
) -> None:
    for relative, expected_sha in records.items():
        path = root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or sha256_file(path) != expected_sha
        ):
            raise RecoveryError(f"{label} changed: {path}")


def _provider_filtered_attempt(
    *,
    root: Path,
    name: str,
    run: dict[str, Any],
    run_path: Path,
    run_sha256: str,
    prompt_path: Path,
    prompt_sha256: str,
    expected_provider_run_id: str,
    expected_provider_job_id: str,
    expected_request_sha256: str,
) -> dict[str, Any]:
    if (
        run.get("provider_run_id") != expected_provider_run_id
        or run.get("provider_job_id") != expected_provider_job_id
        or run.get("model_id") != MODEL_ID
        or run.get("status") != "provider-failed"
        or run.get("provider_may_be_active") is not False
        or run.get("request_sha256") != expected_request_sha256
        or run.get("media") is not None
        or run.get("contract_check") is not None
        or FILTER_MARKER not in str(run.get("error"))
    ):
        raise RecoveryError(f"Filtered attempt evidence changed: {run_path}")
    output = run.get("output_path")
    if output is not None and (
        root / _safe_relative_path(output, label="output_path")
    ).exists():
        raise RecoveryError(f"Filtered attempt unexpectedly has output: {output}")
    return {
        "attempt": name,
        "provider_run_id": expected_provider_run_id,
        "provider_job_id": expected_provider_job_id,
        "status": "provider-filtered",
        "recorded_status": "provider-failed",
        "request_sha256": expected_request_sha256,
        "prompt_path": prompt_path.as_posix(),
        "prompt_sha256": prompt_sha256,
        "run_path": run_path.as_posix(),
        "run_sha256": run_sha256,
        "error": run.get("error"),
        "provider_may_be_active": False,
    }


def _validate_failure_chain(root: Path) -> list[dict[str, Any]]:
    _validate_pinned_files(
        EARLIER_EVIDENCE_SHA256,
        root,
        label="Pre-V1 provider-filtered evidence",
    )
    envelope = read_json(root / RETRY_ENVELOPE_REL)
    primary = envelope.get("primary_attempt") if isinstance(envelope, dict) else None
    retry = envelope.get("retry_attempt") if isinstance(envelope, dict) else None
    if (
        envelope.get("ticket") != TICKET
        or envelope.get("retry_number") != 1
        or envelope.get("logical_output_key") != LOGICAL_KEY
        or not isinstance(primary, dict)
        or not isinstance(retry, dict)
        or primary.get("run_path") != PRIMARY_RUN_REL.as_posix()
        or primary.get("prompt_path") != PRIMARY_PROMPT_REL.as_posix()
        or primary.get("run_sha256") != EARLIER_EVIDENCE_SHA256[PRIMARY_RUN_REL]
        or primary.get("prompt_sha256")
        != EARLIER_EVIDENCE_SHA256[PRIMARY_PROMPT_REL]
        or retry.get("run_path") != RETRY_RUN_REL.as_posix()
        or retry.get("prompt_path") != RETRY_PROMPT_REL.as_posix()
    ):
        raise RecoveryError("Terminal retry-v1 envelope changed")

    primary_run = read_json(root / PRIMARY_RUN_REL)
    retry_run = read_json(root / RETRY_RUN_REL)
    v1_run_rel = (
        V1_ROOT_REL
        / "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.run.json"
    )
    v1_prompt_rel = (
        V1_ROOT_REL
        / "videos/07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.prompt.json"
    )
    v1_run = read_json(root / v1_run_rel)
    return [
        _provider_filtered_attempt(
            root=root,
            name="primary",
            run=primary_run,
            run_path=PRIMARY_RUN_REL,
            run_sha256=EARLIER_EVIDENCE_SHA256[PRIMARY_RUN_REL],
            prompt_path=PRIMARY_PROMPT_REL,
            prompt_sha256=EARLIER_EVIDENCE_SHA256[PRIMARY_PROMPT_REL],
            expected_provider_run_id=(
                "promopages-10060-lite-all-images-20260805-v2-"
                "07-femibion-gotovites-k-beremennosti-06-veo-3-1-lite"
            ),
            expected_provider_job_id="Hfvx2OaGO9vsyrcs6AMf",
            expected_request_sha256=OLD_REQUEST_SHA256,
        ),
        _provider_filtered_attempt(
            root=root,
            name="terminal-retry-v1",
            run=retry_run,
            run_path=RETRY_RUN_REL,
            run_sha256=EARLIER_EVIDENCE_SHA256[RETRY_RUN_REL],
            prompt_path=RETRY_PROMPT_REL,
            prompt_sha256=EARLIER_EVIDENCE_SHA256[RETRY_PROMPT_REL],
            expected_provider_run_id=ORIGINAL_SUPERSEDES_07,
            expected_provider_job_id="dqjE7PrI5frFAFW7Y2Aa",
            expected_request_sha256=OLD_REQUEST_SHA256,
        ),
        _provider_filtered_attempt(
            root=root,
            name="content-filter-recovery-v1",
            run=v1_run,
            run_path=v1_run_rel,
            run_sha256=V1_EVIDENCE_SHA256[v1_run_rel],
            prompt_path=v1_prompt_rel,
            prompt_sha256=V1_EVIDENCE_SHA256[v1_prompt_rel],
            expected_provider_run_id=V1_FAILED_PROVIDER_RUN_ID,
            expected_provider_job_id="SwdH1eVdnIzgLHeXaTIg",
            expected_request_sha256=V1_REQUEST_SHA256,
        ),
    ]


def validate_v1_evidence(root: Path = ROOT) -> dict[str, Any]:
    """Validate the complete partial V1 namespace without reading canonical state."""

    _validate_pinned_files(V1_EVIDENCE_SHA256, root, label="Immutable V1 evidence")
    generation = read_json(root / V1_GENERATION_MANIFEST_REL)
    recovery = read_json(root / V1_RECOVERY_MANIFEST_REL)
    outputs = recovery.get("outputs") if isinstance(recovery, dict) else None
    generation_outputs = (
        generation.get("outputs") if isinstance(generation, dict) else None
    )
    if (
        generation.get("ticket") != TICKET
        or generation.get("batch_id") != V1_PROVIDER_BATCH_ID
        or generation.get("expected_outputs") != 2
        or not isinstance(generation_outputs, list)
        or len(generation_outputs) != 2
        or recovery.get("ticket") != TICKET
        or recovery.get("recovery_id") != V1_RECOVERY_ID
        or recovery.get("provider_batch_id") != V1_PROVIDER_BATCH_ID
        or recovery.get("agent_id") != AGENT_ID
        or recovery.get("expected_outputs") != 2
        or recovery.get("accepted_output_count") != 1
        or recovery.get("ready_for_merge") is not False
        or recovery.get("summary") != {"provider-failed": 1, "succeeded": 1}
        or recovery.get("route") != validate_route(root)
        or recovery.get("contract") != validate_contract(root)
        or recovery.get("accounting") != v1.accounting_document("99.05")
        or not isinstance(outputs, list)
        or len(outputs) != 2
    ):
        raise RecoveryError("Partial V1 recovery manifest identity changed")

    by_key = {
        (item.get("article_slug"), item.get("image_id"), item.get("model_id")): item
        for item in outputs
        if isinstance(item, dict)
    }
    key07 = (SAMPLE.article_slug, SAMPLE.image_id, MODEL_ID)
    key08 = ("08-femibion-grudnoe-vskarmlivanie", "05", MODEL_ID)
    if set(by_key) != {key07, key08}:
        raise RecoveryError("Partial V1 output set changed")
    failed = by_key[key07]
    succeeded = by_key[key08]
    if (
        failed.get("provider_run_id") != V1_FAILED_PROVIDER_RUN_ID
        or failed.get("status") != "provider-failed"
        or failed.get("recorded_status") != "provider-failed"
        or failed.get("provider_may_be_active") is not False
        or failed.get("video_path") is not None
        or failed.get("media") is not None
        or failed.get("contract_check") is not None
        or FILTER_MARKER not in str(failed.get("error"))
        or failed.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_07
        or succeeded.get("provider_run_id") != V1_SUCCESS_PROVIDER_RUN_ID
        or succeeded.get("status") != "succeeded"
        or succeeded.get("recorded_status") != "succeeded"
        or succeeded.get("provider_may_be_active") is not False
        or succeeded.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_08
        or not isinstance(succeeded.get("media"), dict)
        or not isinstance(succeeded.get("contract_check"), dict)
        or succeeded["contract_check"].get("conforms") is not True
    ):
        raise RecoveryError("Partial V1 outcome evidence changed")
    success_video = root / _safe_relative_path(
        succeeded.get("video_path"), label="V1 successful video_path"
    )
    if (
        not success_video.is_file()
        or success_video.is_symlink()
        or succeeded["media"].get("sha256") != sha256_file(success_video)
        or succeeded["media"].get("bytes") != success_video.stat().st_size
    ):
        raise RecoveryError("V1 article 08 media evidence changed")

    planning = recovery.get("planning")
    if not isinstance(planning, list) or len(planning) != 2:
        raise RecoveryError("V1 planning evidence changed")
    planning08 = [
        item
        for item in planning
        if isinstance(item, dict)
        and item.get("planning_run_id")
        == f"{V1_RECOVERY_ID}-08-femibion-grudnoe-vskarmlivanie-05"
    ]
    if len(planning08) != 1 or planning08[0].get("provenance", {}).get("verified") is not True:
        raise RecoveryError("V1 article 08 planning evidence changed")

    return {
        "generation_manifest": {
            "path": V1_GENERATION_MANIFEST_REL.as_posix(),
            "sha256": V1_EVIDENCE_SHA256[V1_GENERATION_MANIFEST_REL],
        },
        "recovery_manifest": {
            "path": V1_RECOVERY_MANIFEST_REL.as_posix(),
            "sha256": V1_EVIDENCE_SHA256[V1_RECOVERY_MANIFEST_REL],
            "accepted_output_count": 1,
            "ready_for_merge": False,
        },
        "failed_attempt_chain": _validate_failure_chain(root),
        "selected_08": copy.deepcopy(succeeded),
        "planning_08": copy.deepcopy(planning08[0]),
    }


def snapshot_v1_evidence(root: Path = ROOT) -> dict[str, str]:
    paths = tuple(V1_EVIDENCE_SHA256) + tuple(EARLIER_EVIDENCE_SHA256)
    return {path.as_posix(): sha256_file(root / path) for path in paths}


def provider_sample(entry: native.Entry) -> dict[str, Any]:
    if entry != ENTRY:
        raise RecoveryError(f"Unexpected V2 entry: {entry.run_id}")
    return {
        "sample_id": SAMPLE.sample_id,
        "article_slug": SAMPLE.article_slug,
        "image_id": SAMPLE.image_id,
        "image_number": SAMPLE.image_id,
        "source_path": SAMPLE.source_path,
        "source_url": SOURCE_URL,
        "sha256": SAMPLE.source_sha256,
        "width": SAMPLE.width,
        "height": SAMPLE.height,
    }


def artifact_paths(entry: native.Entry, root: Path = ROOT) -> dict[str, Path]:
    if entry != ENTRY:
        raise RecoveryError(f"Unexpected V2 entry: {entry.run_id}")
    directory = (
        root
        / RECOVERY_ROOT_REL
        / "videos"
        / SAMPLE.article_slug
        / native.MODEL_DIRECTORIES[MODEL_ID]
    )
    return {
        "directory": directory,
        "prompt": directory / "06.prompt.json",
        "run": directory / "06.run.json",
        "video": directory / "06.mp4",
    }


def _recovery_binding() -> dict[str, Any]:
    return {
        "recovery_id": RECOVERY_ID,
        "iteration": 2,
        "logical_key": LOGICAL_KEY,
        "supersedes_for_demo": ORIGINAL_SUPERSEDES_07,
        "supersedes_attempt": V1_FAILED_PROVIDER_RUN_ID,
        "prior_provider_filtered_attempts": 3,
        "prompt_factor_isolation": True,
        "automatic_retry": False,
        "fallback": False,
    }


def load_v2_job(entry: native.Entry, root: Path = ROOT) -> native.LiteJob:
    if entry != ENTRY:
        raise RecoveryError(f"Unexpected V2 entry: {entry.run_id}")
    contract = validate_contract(root)
    job = _NATIVE_LOAD_LITE_JOB(entry, root)
    summary = job.provenance
    expected_result = (ARTIFACT_NAMESPACE / SAMPLE.planning_run_id / "result.json").as_posix()
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("contract_version") != contract["contract_version"]
        or summary.get("models") != [MODEL_ID]
        or summary.get("source_image_sha256") != SAMPLE.source_sha256
        or summary.get("article_context_sha256") != CONTEXT_SHA256
        or summary.get("result_path") != expected_result
        or job.result_path != expected_result
        or job.result_sha256 != EXPECTED_PLANNING_RESULT_SHA256
        or job.positive_prompt != EXPECTED_POSITIVE_PROMPT
        or job.negative_prompt is not None
    ):
        raise RecoveryError("New V2 Lite provenance/prompt binding differs")
    result = read_json(root / expected_result)
    direction = result.get("inputs", {}).get("user_direction")
    models = result.get("models") if isinstance(result, dict) else None
    if (
        not isinstance(direction, str)
        or "prompt-factor isolation" not in direction
        or not isinstance(models, list)
        or len(models) != 1
        or not isinstance(models[0], dict)
        or models[0].get("model_id") != MODEL_ID
        or models[0].get("positive_prompt") != EXPECTED_POSITIVE_PROMPT
    ):
        raise RecoveryError("New V2 Lite result intent differs")
    words = set(re.findall(r"[a-z]+", job.positive_prompt.casefold()))
    present = sorted(words.intersection(FORBIDDEN_PROMPT_TERMS))
    if present:
        raise RecoveryError(f"V2 prompt contains forbidden terms: {present}")
    return job


def recovery_prompt_artifact(job: native.LiteJob) -> dict[str, Any]:
    document = _NATIVE_PROMPT_ARTIFACT(job)
    document["supersedes_for_demo"] = ORIGINAL_SUPERSEDES_07
    document["supersedes_attempt"] = V1_FAILED_PROVIDER_RUN_ID
    document["recovery"] = _recovery_binding()
    return document


def recovery_initial_run(
    job: native.LiteJob,
    paths: dict[str, Path],
    root: Path = ROOT,
) -> dict[str, Any]:
    document = _NATIVE_INITIAL_RUN(job, paths, root)
    document["supersedes_for_demo"] = ORIGINAL_SUPERSEDES_07
    document["supersedes_attempt"] = V1_FAILED_PROVIDER_RUN_ID
    document["recovery"] = _recovery_binding()
    return document


def recovery_materialize_entry(
    entry: native.Entry,
    root: Path = ROOT,
) -> dict[str, Any]:
    row = _NATIVE_MATERIALIZE_ENTRY(entry, root)
    run = read_json(row["paths"]["run"])
    if (
        run.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_07
        or run.get("supersedes_attempt") != V1_FAILED_PROVIDER_RUN_ID
        or run.get("recovery") != _recovery_binding()
    ):
        raise RecoveryError(f"Immutable V2 run binding changed: {row['paths']['run']}")
    return row


@contextmanager
def configured_native(root: Path = ROOT) -> Iterator[None]:
    validate_route(root)
    validate_contract(root)
    names = (
        "BATCH_ID",
        "PLANNING_BATCH_ID",
        "MODEL_IDS",
        "PLANNING_MODEL_IDS",
        "TICKET",
        "MANIFEST_PATH",
        "CONTRACT_PATH",
        "PLANNING_WORKSPACE",
        "PLANNING_PROVENANCE_VERIFIER",
        "SAMPLES",
        "WAN_SUBMIT_MODE",
        "SCHEDULING_EXCLUDED_RUN_IDS",
        "provider_sample",
        "artifact_paths",
        "prompt_artifact",
        "initial_run",
        "matrix",
        "load_lite_job",
        "materialize_entry",
    )
    saved = {name: getattr(native, name) for name in names}
    try:
        native.BATCH_ID = PROVIDER_BATCH_ID
        native.PLANNING_BATCH_ID = RECOVERY_ID
        native.MODEL_IDS = MODEL_IDS
        native.PLANNING_MODEL_IDS = MODEL_IDS
        native.TICKET = TICKET
        native.MANIFEST_PATH = GENERATION_MANIFEST_REL
        native.CONTRACT_PATH = root / CONTRACT_REL
        native.PLANNING_WORKSPACE = None
        native.PLANNING_PROVENANCE_VERIFIER = pipeline.planning_provenance_summary
        native.SAMPLES = (SAMPLE,)
        native.WAN_SUBMIT_MODE = None
        native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()
        native.provider_sample = provider_sample
        native.artifact_paths = artifact_paths
        native.prompt_artifact = recovery_prompt_artifact
        native.initial_run = recovery_initial_run
        native.matrix = lambda: ENTRIES
        native.load_lite_job = load_v2_job
        native.materialize_entry = recovery_materialize_entry
        if native.matrix() != ENTRIES:
            raise RecoveryError("Native V2 matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def assert_request(request: dict[str, Any], job: native.LiteJob) -> None:
    frames = [
        {
            "type": "image_url",
            "image_url": {"url": SOURCE_URL},
            "frame_type": "first_frame",
        }
    ]
    if (
        request.get("model") != MODEL_ID
        or request.get("prompt") != EXPECTED_POSITIVE_PROMPT
        or request.get("prompt") != job.positive_prompt
        or request.get("duration") != 4
        or request.get("resolution") != "1080p"
        or request.get("aspect_ratio") != "16:9"
        or request.get("seed") != 9681
        or request.get("generate_audio") is not False
        or request.get("frame_images") != frames
        or request.get("provider")
        != {
            "options": {
                EXPECTED_ROUTE_PROVIDER: {
                    "parameters": {"enhancePrompt": True}
                }
            }
        }
        or "loop" in request
    ):
        raise RecoveryError("Non-exact Veo V2 recovery request")
    fingerprint = transport.request_fingerprint(request, provider_sample(ENTRY))
    if (
        fingerprint != EXPECTED_REQUEST_SHA256
        or fingerprint in {OLD_REQUEST_SHA256, V1_REQUEST_SHA256}
    ):
        raise RecoveryError("V2 recovery request fingerprint changed or repeats a failure")


def preflight(
    root: Path = ROOT,
    *,
    budget_cap_usd: str | Decimal = REQUIRED_OPERATOR_BUDGET_CAP_USD,
) -> dict[str, Any]:
    accounting = accounting_document(budget_cap_usd)
    route = validate_route(root)
    contract = validate_contract(root)
    v1_evidence = validate_v1_evidence(root)
    with configured_native(root):
        job = load_v2_job(ENTRY, root)
        prompt = native.provider_prompt(job)
        request = native.provider_request_preview(provider_sample(ENTRY), prompt)
        assert_request(request, job)
        result = read_json(root / job.result_path)
        model = result["models"][0]
        record = {
            "planning_run_id": SAMPLE.planning_run_id,
            "planning_result_path": job.result_path,
            "planning_result_sha256": job.result_sha256,
            "provenance": native.safe_provenance(job),
            "structured_intent": dict(job.structured_intent),
            "scene_plan": model["scene_plan"].strip(),
            "positive_prompt": job.positive_prompt,
            "negative_prompt": job.negative_prompt,
            "request": request,
            "request_sha256": transport.request_fingerprint(
                request, provider_sample(ENTRY)
            ),
            "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
        }
    return {
        "route": route,
        "contract": contract,
        "accounting": accounting,
        "v1_evidence": v1_evidence,
        "record": record,
    }


def dry_run(
    budget_cap_usd: str | Decimal,
    root: Path = ROOT,
) -> int:
    state = preflight(root, budget_cap_usd=budget_cap_usd)
    print(
        f"PASS: {ENTRY.provider_run_id} uses verified {SAMPLE.planning_run_id}",
        flush=True,
    )
    print(
        "PASS: exact neutral prompt and one Veo request validated under the "
        "$99.40 operator cap; no files written",
        flush=True,
    )
    if len(state["v1_evidence"]["failed_attempt_chain"]) != 3:
        raise RecoveryError("V1 failed-attempt chain is incomplete")
    return 0


def _accepted_output(output: dict[str, Any]) -> bool:
    status = output.get("status")
    check = output.get("contract_check")
    media = output.get("media")
    if (
        status not in ACCEPTED_STATUSES
        or not isinstance(check, dict)
        or not isinstance(media, dict)
    ):
        return False
    if status == "succeeded":
        return check.get("conforms") is True
    return check.get("conforms") is False


def recovery_document(
    generation: dict[str, Any],
    state: dict[str, Any],
    *,
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    if state.get("accounting") != accounting_document("99.40"):
        raise RecoveryError("V2 accounting state changed")
    raw_outputs = generation.get("outputs") if isinstance(generation, dict) else None
    if (
        generation.get("ticket") != TICKET
        or generation.get("batch_id") != PROVIDER_BATCH_ID
        or generation.get("agent_id") != AGENT_ID
        or generation.get("expected_outputs") != 1
        or not isinstance(raw_outputs, list)
        or len(raw_outputs) != 1
    ):
        raise RecoveryError("V2 generation manifest identity changed")
    raw = raw_outputs[0]
    paths = artifact_paths(ENTRY, root)
    prompt_rel = paths["prompt"].relative_to(root).as_posix()
    run_rel = paths["run"].relative_to(root).as_posix()
    video_rel = paths["video"].relative_to(root).as_posix()
    if (
        not isinstance(raw, dict)
        or raw.get("sample_id") != SAMPLE.sample_id
        or raw.get("article_slug") != SAMPLE.article_slug
        or raw.get("source_path") != SAMPLE.source_path
        or raw.get("model_id") != MODEL_ID
        or raw.get("lite_run_id") != SAMPLE.planning_run_id
        or raw.get("provider_run_id") != ENTRY.provider_run_id
        or raw.get("prompt_path") != prompt_rel
        or raw.get("run_path") != run_rel
        or raw.get("video_path") != video_rel
    ):
        raise RecoveryError("V2 generation output identity changed")
    prompt_receipt = read_json(paths["prompt"])
    run_receipt = read_json(paths["run"])
    if (
        prompt_receipt.get("provider_run_id") != ENTRY.provider_run_id
        or prompt_receipt.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_07
        or prompt_receipt.get("supersedes_attempt") != V1_FAILED_PROVIDER_RUN_ID
        or prompt_receipt.get("recovery") != _recovery_binding()
        or run_receipt.get("provider_run_id") != ENTRY.provider_run_id
        or run_receipt.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_07
        or run_receipt.get("supersedes_attempt") != V1_FAILED_PROVIDER_RUN_ID
        or run_receipt.get("recovery") != _recovery_binding()
        or run_receipt.get("status") != raw.get("recorded_status")
        or run_receipt.get("media") != raw.get("media")
        or run_receipt.get("contract_check") != raw.get("contract_check")
        or run_receipt.get("error") != raw.get("error")
        or run_receipt.get("provider_may_be_active")
        != raw.get("provider_may_be_active")
    ):
        raise RecoveryError("V2 prompt/run receipt binding changed")
    record = state["record"]
    if (
        run_receipt.get("request") != record["request"]
        or run_receipt.get("request_sha256") != record["request_sha256"]
        or run_receipt.get("request_fingerprint_version")
        != record["request_fingerprint_version"]
    ):
        raise RecoveryError("V2 provider request receipt changed")

    accepted = _accepted_output(raw)
    video_path: str | None = None
    if accepted:
        media = raw["media"]
        relative_video = _safe_relative_path(
            raw.get("video_path"), label="V2 video_path"
        )
        absolute_video = root / relative_video
        if (
            not absolute_video.is_file()
            or absolute_video.is_symlink()
            or media.get("sha256") != sha256_file(absolute_video)
            or media.get("bytes") != absolute_video.stat().st_size
        ):
            raise RecoveryError(f"Accepted V2 media receipt differs: {absolute_video}")
        video_path = relative_video.as_posix()

    status = str(raw.get("status"))
    output = {
        "article_slug": SAMPLE.article_slug,
        "image_id": SAMPLE.image_id,
        "source_path": SAMPLE.source_path,
        "sample_id": SAMPLE.sample_id,
        "lite_run_id": SAMPLE.planning_run_id,
        "provider_run_id": ENTRY.provider_run_id,
        "provider_job_id": run_receipt.get("provider_job_id"),
        "model_id": MODEL_ID,
        "scene_plan": record["scene_plan"],
        "positive_prompt": record["positive_prompt"],
        "negative_prompt": record["negative_prompt"],
        "status": status,
        "recorded_status": raw.get("recorded_status"),
        "provider_may_be_active": raw.get("provider_may_be_active"),
        "prompt_path": raw.get("prompt_path"),
        "run_path": raw.get("run_path"),
        "video_path": video_path,
        "media": raw.get("media"),
        "contract_check": raw.get("contract_check"),
        "error": raw.get("error"),
        "request_sha256": record["request_sha256"],
        "selected_attempt": "content-filter-recovery-v2",
        "supersedes_for_demo": ORIGINAL_SUPERSEDES_07,
        "recovery": {
            **_recovery_binding(),
            "prior_attempt_manifest": state["v1_evidence"]["recovery_manifest"],
            "failed_attempt_chain": state["v1_evidence"]["failed_attempt_chain"],
            "new_request_sha256": record["request_sha256"],
            "request_changed_from_all_failed_attempts": True,
            "prompt_factor": {
                "isolated": True,
                "expected_positive_prompt": EXPECTED_POSITIVE_PROMPT,
                "forbidden_terms": list(FORBIDDEN_PROMPT_TERMS),
            },
        },
    }
    return {
        "schema_version": 1,
        "manifest_role": "promopages-10060-femibion-veo-content-filter-recovery-v2",
        "ticket": TICKET,
        "recovery_id": RECOVERY_ID,
        "iteration": 2,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "expected_outputs": 1,
        "accepted_output_count": int(accepted),
        "ready_for_combined_selection": accepted,
        "ready_for_merge": False,
        "merge_requires_combined_selection_manifest": True,
        "summary": {status: 1},
        "route": state["route"],
        "contract": state["contract"],
        "accounting": state["accounting"],
        "prompt_factor_isolation": {
            "expected_positive_prompt": EXPECTED_POSITIVE_PROMPT,
            "forbidden_terms": list(FORBIDDEN_PROMPT_TERMS),
            "prior_request_sha256": V1_REQUEST_SHA256,
            "new_request_sha256": record["request_sha256"],
        },
        "generation_policy": {
            "exact_model_id": MODEL_ID,
            "exact_route_only": True,
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "automatic_paid_retries": False,
            "maximum_new_paid_submissions": 1,
            "maximum_submissions_per_new_provider_identity": 1,
            "resume_may_submit_only_never_submitted_pending_receipts": True,
            "resume_repeats_ambiguous_or_terminal_submit": False,
        },
        "v1_evidence": {
            "generation_manifest": state["v1_evidence"]["generation_manifest"],
            "recovery_manifest": state["v1_evidence"]["recovery_manifest"],
            "failed_attempt_chain": state["v1_evidence"]["failed_attempt_chain"],
        },
        "planning": [
            {
                "planning_run_id": record["planning_run_id"],
                "result_path": record["planning_result_path"],
                "result_sha256": record["planning_result_sha256"],
                "provenance": record["provenance"],
            }
        ],
        "generation_manifest_path": GENERATION_MANIFEST_REL.as_posix(),
        "combined_selection_manifest_path": (
            COMBINED_SELECTION_MANIFEST_REL.as_posix()
        ),
        "outputs": [output],
    }


def combined_selection_document(
    v2_recovery: dict[str, Any],
    state: dict[str, Any],
    *,
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    v2_outputs = v2_recovery.get("outputs") if isinstance(v2_recovery, dict) else None
    if (
        v2_recovery.get("recovery_id") != RECOVERY_ID
        or v2_recovery.get("ready_for_merge") is not False
        or not isinstance(v2_outputs, list)
        or len(v2_outputs) != 1
    ):
        raise RecoveryError("V2 attempt manifest cannot feed combined selection")
    v2_output = copy.deepcopy(v2_outputs[0])
    v1_output = copy.deepcopy(state["v1_evidence"]["selected_08"])
    if (
        v2_output.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_07
        or v1_output.get("supersedes_for_demo") != ORIGINAL_SUPERSEDES_08
        or not _accepted_output(v1_output)
    ):
        raise RecoveryError("Combined selection input identities changed")
    outputs = [v2_output, v1_output]
    accepted = sum(int(_accepted_output(output)) for output in outputs)
    ready = accepted == 2 and v2_recovery.get("ready_for_combined_selection") is True
    v2_manifest_path = root / RECOVERY_MANIFEST_REL
    if not v2_manifest_path.is_file() or v2_manifest_path.is_symlink():
        raise RecoveryError(f"Missing immutable V2 recovery manifest: {v2_manifest_path}")
    v2_manifest_sha = sha256_file(v2_manifest_path)
    record = state["record"]
    return {
        "schema_version": 1,
        "manifest_role": "promopages-10060-femibion-veo-combined-selection",
        "ticket": TICKET,
        "selection_id": f"{RECOVERY_ID}-combined-selection",
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "expected_outputs": 2,
        "accepted_output_count": accepted,
        "ready_for_merge": ready,
        "summary": {
            status: sum(1 for output in outputs if output.get("status") == status)
            for status in sorted({str(output.get("status")) for output in outputs})
        },
        "route": state["route"],
        "contract": state["contract"],
        "accounting": state["accounting"],
        "attempt_manifests": [
            {
                "iteration": 1,
                **state["v1_evidence"]["recovery_manifest"],
            },
            {
                "iteration": 2,
                "path": RECOVERY_MANIFEST_REL.as_posix(),
                "sha256": v2_manifest_sha,
                "accepted_output_count": v2_recovery["accepted_output_count"],
                "ready_for_combined_selection": v2_recovery[
                    "ready_for_combined_selection"
                ],
            },
        ],
        "failed_attempt_chain": state["v1_evidence"]["failed_attempt_chain"],
        "selection": [
            {
                "logical_key": LOGICAL_KEY,
                "source_iteration": 2,
                "provider_run_id": ENTRY.provider_run_id,
                "supersedes_for_demo": ORIGINAL_SUPERSEDES_07,
            },
            {
                "logical_key": {
                    "article_slug": "08-femibion-grudnoe-vskarmlivanie",
                    "image_id": "05",
                    "model_id": MODEL_ID,
                },
                "source_iteration": 1,
                "provider_run_id": V1_SUCCESS_PROVIDER_RUN_ID,
                "supersedes_for_demo": ORIGINAL_SUPERSEDES_08,
            },
        ],
        "supersedes_for_demo": [
            {
                "logical_key": output_key,
                "old_provider_run_id": old_id,
                "new_provider_run_id": new_id,
            }
            for output_key, old_id, new_id in (
                (LOGICAL_KEY, ORIGINAL_SUPERSEDES_07, ENTRY.provider_run_id),
                (
                    {
                        "article_slug": "08-femibion-grudnoe-vskarmlivanie",
                        "image_id": "05",
                        "model_id": MODEL_ID,
                    },
                    ORIGINAL_SUPERSEDES_08,
                    V1_SUCCESS_PROVIDER_RUN_ID,
                ),
            )
        ],
        "planning": [
            {
                "planning_run_id": record["planning_run_id"],
                "result_path": record["planning_result_path"],
                "result_sha256": record["planning_result_sha256"],
                "provenance": record["provenance"],
            },
            state["v1_evidence"]["planning_08"],
        ],
        "merge_contract": {
            "target_manifest": CANONICAL_MANIFEST_REL.as_posix(),
            "logical_key": ["article_slug", "image_id", "model_id"],
            "replace_only_status": "provider-filtered",
            "replace_exactly": 2,
            "requires_ready_for_merge": True,
            "preserve_all_other_outputs": True,
            "all_or_nothing": True,
            "demo_selection_field": "supersedes_for_demo",
        },
        "outputs": outputs,
    }


def _write_stable_document(
    path: Path,
    builder,
) -> dict[str, Any]:
    if path.is_file():
        current = read_json(path)
        existing_time = current.get("updated_at") if isinstance(current, dict) else None
        if isinstance(existing_time, str):
            unchanged = builder(existing_time)
            if current == unchanged:
                return unchanged
    document = builder(None)
    transport.atomic_write_json(path, document)
    return document


def write_recovery_manifests(
    state: dict[str, Any],
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generation = read_json(root / GENERATION_MANIFEST_REL)
    recovery_path = root / RECOVERY_MANIFEST_REL
    recovery = _write_stable_document(
        recovery_path,
        lambda updated_at: recovery_document(
            generation,
            state,
            root=root,
            updated_at=updated_at,
        ),
    )
    combined_path = root / COMBINED_SELECTION_MANIFEST_REL
    combined = _write_stable_document(
        combined_path,
        lambda updated_at: combined_selection_document(
            recovery,
            state,
            root=root,
            updated_at=updated_at,
        ),
    )
    return recovery, combined


def validate_combined_selection_for_canonical_overlay(
    root: Path = ROOT,
    *,
    budget_cap_usd: str | Decimal = REQUIRED_OPERATOR_BUDGET_CAP_USD,
) -> dict[str, Any]:
    """Validate V1+V2 selection without requiring current canonical filtered rows."""

    state = preflight(root, budget_cap_usd=budget_cap_usd)
    generation = read_json(root / GENERATION_MANIFEST_REL)
    recovery_path = root / RECOVERY_MANIFEST_REL
    recovery = read_json(recovery_path)
    recovery_time = recovery.get("updated_at") if isinstance(recovery, dict) else None
    if not isinstance(recovery_time, str) or not recovery_time:
        raise RecoveryError(f"V2 recovery manifest has no updated_at: {recovery_path}")
    expected_recovery = recovery_document(
        generation,
        state,
        root=root,
        updated_at=recovery_time,
    )
    if recovery != expected_recovery:
        raise RecoveryError("V2 recovery manifest differs from verified receipts")

    combined_path = root / COMBINED_SELECTION_MANIFEST_REL
    combined = read_json(combined_path)
    combined_time = combined.get("updated_at") if isinstance(combined, dict) else None
    if not isinstance(combined_time, str) or not combined_time:
        raise RecoveryError(f"Combined selection has no updated_at: {combined_path}")
    expected_combined = combined_selection_document(
        recovery,
        state,
        root=root,
        updated_at=combined_time,
    )
    if combined != expected_combined:
        raise RecoveryError("Combined selection differs from verified V1/V2 evidence")
    if (
        combined.get("ready_for_merge") is not True
        or combined.get("accepted_output_count") != 2
        or len(combined.get("failed_attempt_chain", [])) != 3
    ):
        raise RecoveryError("Combined selection is not ready for canonical overlay")
    return combined


def _known_recovery_artifacts(root: Path) -> tuple[Path, ...]:
    paths = artifact_paths(ENTRY, root)
    return (
        root / GENERATION_MANIFEST_REL,
        root / RECOVERY_MANIFEST_REL,
        root / COMBINED_SELECTION_MANIFEST_REL,
        paths["prompt"],
        paths["run"],
        paths["video"],
    )


def _validate_mode_state(mode: str, root: Path) -> None:
    recovery_root = root / RECOVERY_ROOT_REL
    known = _known_recovery_artifacts(root)
    if mode == "generate":
        if recovery_root.exists():
            raise RecoveryError(
                f"Immutable V2 namespace already exists; use resume: {recovery_root}"
            )
        return
    if mode != "resume":
        raise RecoveryError(f"Unknown V2 recovery mode: {mode}")
    if (
        not recovery_root.is_dir()
        or recovery_root.is_symlink()
        or not any(path.exists() for path in known)
    ):
        raise RecoveryError(
            f"Resume requires an existing V2 receipt namespace: {recovery_root}"
        )


@contextmanager
def recovery_run_lock(root: Path) -> Iterator[None]:
    lock_path = root / "scripts/clipmaker_lite_promopages_10060_femibion_veo_recovery_v2.py"
    with lock_path.open("rb") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecoveryError("another Femibion V2 coordinator is running") from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_generation(
    mode: str,
    *,
    budget_cap_usd: str | Decimal,
    root: Path = ROOT,
    allow_external_processing: bool = False,
    timeout: int = 1800,
    poll_interval: float = 10.0,
) -> int:
    parse_budget(budget_cap_usd)
    if not allow_external_processing:
        raise RecoveryError(
            f"{mode} requires --allow-external-processing because one source image "
            "and the V2 prompt are sent to the exact Veo provider route"
        )
    state = preflight(root, budget_cap_usd=budget_cap_usd)
    before = snapshot_v1_evidence(root)
    with recovery_run_lock(root):
        _validate_mode_state(mode, root)
        with configured_native(root):
            rows = native.materialize(root)
            if len(rows) != 1 or rows[0]["entry"] != ENTRY:
                raise RecoveryError("Materialized V2 matrix is not exactly one Veo job")
            argv = [
                "run",
                "--veo31-concurrency",
                "1",
                "--timeout",
                str(timeout),
                "--poll-interval",
                str(poll_interval),
                "--allow-external-processing",
                "--run-id",
                ENTRY.provider_run_id,
            ]
            result = native.main(argv, root)
        if snapshot_v1_evidence(root) != before:
            raise RecoveryError("V1 evidence changed during V2 recovery")
        recovery, combined = write_recovery_manifests(state, root)
    print(
        f"V2 recovery manifest: {RECOVERY_MANIFEST_REL.as_posix()} "
        f"ready_for_combined_selection="
        f"{str(recovery['ready_for_combined_selection']).lower()}",
        flush=True,
    )
    print(
        f"combined selection: {COMBINED_SELECTION_MANIFEST_REL.as_posix()} "
        f"ready_for_merge={str(combined['ready_for_merge']).lower()}",
        flush=True,
    )
    return result


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be numeric") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dry = commands.add_parser("dry-run", help="validate the one V2 request")
    dry.add_argument("--budget-cap-usd", type=budget_arg, required=True)
    for name in ("generate", "resume"):
        command = commands.add_parser(name)
        command.add_argument("--budget-cap-usd", type=budget_arg, required=True)
        command.add_argument("--allow-external-processing", action="store_true")
        command.add_argument("--timeout", type=positive_int, default=1800)
        command.add_argument("--poll-interval", type=positive_float, default=10.0)
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "dry-run":
            return dry_run(args.budget_cap_usd, root)
        return run_generation(
            args.command,
            budget_cap_usd=args.budget_cap_usd,
            root=root,
            allow_external_processing=args.allow_external_processing,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
        )
    except (
        RecoveryError,
        v1.RecoveryError,
        native.BatchPipelineError,
        pipeline.PipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
