#!/usr/bin/env python3
"""Recover exactly two filtered PROMOPAGES-10060 Veo 3.1 Lite outputs.

The original provider attempts and their exhausted terminal-retry-v1 receipts
are immutable evidence.  This coordinator consumes two *new* verified
``clipmaker-lite`` result artifacts, creates two new provider identities in an
isolated namespace, and records explicit ``supersedes_for_demo`` links for a
later canonical-manifest merge.  It never discovers routes, falls back to a
different model, rewrites the old batch, uploads media, or edits demo data.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
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
from scripts import clipmaker_lite_promopages_10060_pipeline as pipeline  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
MODEL_ID = "google/veo-3.1-lite"
MODEL_IDS = (MODEL_ID,)
RECOVERY_ID = "promopages-10060-femibion-veo-recovery-20260810-v1"
PROVIDER_BATCH_ID = f"{RECOVERY_ID}-provider"

CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
CANONICAL_MANIFEST_REL = Path("clipmaker-lite-test/promopages-10060-manifest.json")
RECOVERY_ROOT_REL = Path("clipmaker-lite-test/runs") / RECOVERY_ID
GENERATION_MANIFEST_REL = RECOVERY_ROOT_REL / "generation-manifest.json"
RECOVERY_MANIFEST_REL = RECOVERY_ROOT_REL / "recovery-manifest.json"
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")

EXPECTED_CONTRACT_VERSION = "2.0.8"
EXPECTED_ROUTE_ADAPTER = "eliza-openrouter"
EXPECTED_ROUTE_TRANSPORT = "eliza-video-jobs"
EXPECTED_ROUTE_PROVIDER = "google-vertex"
EXPECTED_ROUTE_CAPACITY = 3
FILTER_MARKER = "Video generation completed with no output (content may have been filtered)"
ACCEPTED_STATUSES = frozenset({"succeeded", "verification-failed"})

BASELINE_PAID_SUBMISSIONS = 281
BASELINE_RESERVED_USD = Decimal("98.35")
RECOVERY_PAID_SUBMISSIONS = 2
ACCOUNTING_COST_PER_OUTPUT_USD = Decimal("0.35")
RECOVERY_RESERVED_USD = Decimal("0.70")
REQUIRED_OPERATOR_BUDGET_CAP_USD = Decimal("99.05")
HARD_BUDGET_CAP_USD = Decimal("100.00")


class RecoveryError(RuntimeError):
    """A fail-closed, user-actionable recovery coordinator error."""


@dataclass(frozen=True)
class RecoverySample(native.Sample):
    """A native sample with ticket-namespaced source/context bindings."""

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
    """An entry whose new provider identity does not depend on native globals."""

    @property
    def provider_run_id(self) -> str:
        return (
            f"{PROVIDER_BATCH_ID}-{self.sample.sample_id}-"
            f"{native.MODEL_SUFFIXES[self.model_id]}"
        )


@dataclass(frozen=True)
class RecoveryTarget:
    sample: RecoverySample
    context_sha256: str
    source_url: str
    supersedes_for_demo: str
    old_provider_job_id: str
    old_request_sha256: str
    old_run_rel: Path
    old_run_sha256: str
    old_retry_rel: Path
    old_retry_sha256: str

    @property
    def logical_key(self) -> dict[str, str]:
        return {
            "article_slug": self.sample.article_slug,
            "image_id": self.sample.image_id,
            "model_id": MODEL_ID,
        }

    @property
    def entry(self) -> RecoveryEntry:
        return RecoveryEntry(self.sample, MODEL_ID)


def _planning_run_id(sample_id: str) -> str:
    return f"{RECOVERY_ID}-{sample_id}"


TARGETS = (
    RecoveryTarget(
        sample=RecoverySample(
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
            lite_run_id=_planning_run_id(
                "07-femibion-gotovites-k-beremennosti-06"
            ),
        ),
        context_sha256=(
            "765a6fc158a59ce0c07a5e838b4d1f2fb3ecc39cbe21884dd33f5c28bb7edb5c"
        ),
        source_url=(
            "https://avatars.mds.yandex.net/get-promoarticles/5096941/"
            "pub_685a45c483113703283d5b0e_685ab42c046a3d4397850a85/orig"
        ),
        supersedes_for_demo=(
            "promopages-10060-lite-all-images-20260805-v2-terminal-retry-v1-"
            "6243bd1bbb1a1e3fe253-07-femibion-gotovites-k-beremennosti-06-"
            "veo-3-1-lite"
        ),
        old_provider_job_id="dqjE7PrI5frFAFW7Y2Aa",
        old_request_sha256=(
            "f7f0c0c20f702b1deb1b5ee3a8e28d2487c8c3988653792518b03a223afa7a01"
        ),
        old_run_rel=Path(
            "clipmaker-lite-test/runs/"
            "promopages-10060-lite-all-images-20260805-v2/"
            "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/"
            "videos/veo-3.1-lite/06.run.json"
        ),
        old_run_sha256=(
            "b4f6561f1bc0084c81ecd3c47c3c6158a1bc08f0049fa286875da091daa3bc8d"
        ),
        old_retry_rel=Path(
            "clipmaker-lite-test/runs/"
            "promopages-10060-lite-all-images-20260805-v2/"
            "terminal-provider-retries-v1/6243bd1bbb1a1e3fe253/retry.json"
        ),
        old_retry_sha256=(
            "5b26c05000069a0cc89513bf5a37dde497d956a7699b4c4a921bddee9d66d452"
        ),
    ),
    RecoveryTarget(
        sample=RecoverySample(
            sample_id="08-femibion-grudnoe-vskarmlivanie-05",
            article_slug="08-femibion-grudnoe-vskarmlivanie",
            image_id="05",
            filename="05.jpeg",
            source_sha256=(
                "e29ddb18cc961dff4595222d7a18f030a457e910a0b477cdc897adf7426af06a"
            ),
            width=1920,
            height=1280,
            bound_source_path=(
                "PROMOPAGES-9857/PROMOPAGES-10060/articles/"
                "08-femibion-grudnoe-vskarmlivanie/05.jpeg"
            ),
            bound_context_path=(
                "PROMOPAGES-9884/PROMOPAGES-10060/articles/"
                "08-femibion-grudnoe-vskarmlivanie/content.json"
            ),
            lite_run_id=_planning_run_id(
                "08-femibion-grudnoe-vskarmlivanie-05"
            ),
        ),
        context_sha256=(
            "33548f66e701ed12073d2cd1b3471ac7ae8fe34a3ae5b1587ba9092d27fef6ce"
        ),
        source_url=(
            "https://avatars.mds.yandex.net/get-promoarticles/6165752/"
            "pub_685a4ed183113703283dcca7_685a4ff6646ea17f6e82547e/orig"
        ),
        supersedes_for_demo=(
            "promopages-10060-lite-all-images-20260805-v2-terminal-retry-v1-"
            "0cc5261325a58f1785ee-08-femibion-grudnoe-vskarmlivanie-05-"
            "veo-3-1-lite"
        ),
        old_provider_job_id="tpePxKfkVlYvoc1nVeS0",
        old_request_sha256=(
            "30df775a691ff4814b67252784630c3d241cdc22a083b8ac297dd85415d93955"
        ),
        old_run_rel=Path(
            "clipmaker-lite-test/runs/"
            "promopages-10060-lite-all-images-20260805-v2/"
            "terminal-provider-retries-v1/0cc5261325a58f1785ee/"
            "videos/veo-3.1-lite/05.run.json"
        ),
        old_run_sha256=(
            "60b797369bc0f64c686ecf310b575cb086a99e2f46715b77daa0e71127c99b4e"
        ),
        old_retry_rel=Path(
            "clipmaker-lite-test/runs/"
            "promopages-10060-lite-all-images-20260805-v2/"
            "terminal-provider-retries-v1/0cc5261325a58f1785ee/retry.json"
        ),
        old_retry_sha256=(
            "7e41c6be6741700a3f046753f66a149e0e8293d0b6db92dc528e6c2b540da5e5"
        ),
    ),
)
ENTRIES = tuple(target.entry for target in TARGETS)

_TARGET_BY_SAMPLE_ID = {target.sample.sample_id: target for target in TARGETS}
_TARGET_BY_PROVIDER_RUN_ID = {
    target.entry.provider_run_id: target for target in TARGETS
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


def parse_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecoveryError("--budget-cap-usd must be a decimal USD amount") from exc
    if parsed != REQUIRED_OPERATOR_BUDGET_CAP_USD:
        raise RecoveryError(
            "this immutable recovery requires --budget-cap-usd 99.05 exactly"
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
        BASELINE_RESERVED_USD
        + RECOVERY_PAID_SUBMISSIONS * ACCOUNTING_COST_PER_OUTPUT_USD
        != REQUIRED_OPERATOR_BUDGET_CAP_USD
        or RECOVERY_RESERVED_USD
        != RECOVERY_PAID_SUBMISSIONS * ACCOUNTING_COST_PER_OUTPUT_USD
        or operator_cap > HARD_BUDGET_CAP_USD
    ):
        raise RecoveryError("Femibion recovery accounting constants are inconsistent")
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
        "maximum_new_paid_submissions": RECOVERY_PAID_SUBMISSIONS,
        "automatic_paid_retries": False,
        "pricing_basis": "frozen local PROMOPAGES-10060 accounting evidence",
    }


def _safe_relative_path(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise RecoveryError(f"{label} must be a non-empty workspace-relative path")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise RecoveryError(f"Unsafe {label}: {value!r}")
    return Path(*parsed.parts)


def _target_for_entry(entry: native.Entry) -> RecoveryTarget:
    target = _TARGET_BY_SAMPLE_ID.get(entry.sample.sample_id)
    if target is None or entry.model_id != MODEL_ID:
        raise RecoveryError(f"Unexpected recovery entry: {entry.run_id}")
    return target


def validate_route(root: Path = ROOT) -> dict[str, Any]:
    path = root / ROUTES_REL
    document = read_json(path)
    policy = document.get("policy") if isinstance(document, dict) else None
    models = document.get("models") if isinstance(document, dict) else None
    route = models.get(MODEL_ID) if isinstance(models, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or not isinstance(policy, dict)
        or policy.get("resolution") != "exact-model-id"
        or policy.get("automatic_fallback") is not False
        or policy.get("normal_run_discovery") is not False
        or not isinstance(route, dict)
        or route.get("adapter") != EXPECTED_ROUTE_ADAPTER
        or route.get("transport") != EXPECTED_ROUTE_TRANSPORT
        or route.get("provider_key") != EXPECTED_ROUTE_PROVIDER
        or route.get("capacity") != EXPECTED_ROUTE_CAPACITY
        or transport.route_for_model(MODEL_ID) != route
    ):
        raise RecoveryError("Exact Veo 3.1 Lite generation route changed")
    return {
        "registry_path": ROUTES_REL.as_posix(),
        "registry_sha256": sha256_file(path),
        "model_id": MODEL_ID,
        "adapter": route["adapter"],
        "transport": route["transport"],
        "provider_key": route["provider_key"],
        "capacity": route["capacity"],
        "paths": dict(route["paths"]),
        "automatic_fallback": False,
        "normal_run_discovery": False,
    }


def validate_contract(root: Path = ROOT) -> dict[str, Any]:
    path = root / CONTRACT_REL
    document = read_json(path)
    models = document.get("models") if isinstance(document, dict) else None
    veo = models.get(MODEL_ID) if isinstance(models, dict) else None
    runtime = veo.get("runtime") if isinstance(veo, dict) else None
    contract_version = document.get("contract_version") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("agent_id") != AGENT_ID
        or not isinstance(contract_version, str)
        or contract_version != EXPECTED_CONTRACT_VERSION
        or not isinstance(runtime, dict)
        or runtime.get("duration_seconds") != 4
        or runtime.get("resolution") != "1080p"
        or runtime.get("aspect_ratios") != ["16:9", "9:16"]
        or runtime.get("generate_audio") is not False
        or runtime.get("frame_inputs") != ["first_frame"]
        or runtime.get("provider") != EXPECTED_ROUTE_PROVIDER
        or runtime.get("prompt_expansion")
        != {"parameter": "enhancePrompt", "value": True}
    ):
        raise RecoveryError("Current Clipmaker Lite Veo contract changed")
    return {
        "path": CONTRACT_REL.as_posix(),
        "sha256": sha256_file(path),
        "contract_version": contract_version,
        "runtime": runtime,
    }


def _validate_source_and_context(target: RecoveryTarget, root: Path) -> None:
    source = root / target.sample.source_path
    context = root / target.sample.context_path
    if (
        not source.is_file()
        or source.is_symlink()
        or sha256_file(source) != target.sample.source_sha256
    ):
        raise RecoveryError(f"Recovery source image changed: {source}")
    if (
        not context.is_file()
        or context.is_symlink()
        or sha256_file(context) != target.context_sha256
    ):
        raise RecoveryError(f"Recovery article context changed: {context}")


def _validate_old_retry(target: RecoveryTarget, root: Path) -> dict[str, Any]:
    run_path = root / target.old_run_rel
    retry_path = root / target.old_retry_rel
    if (
        not run_path.is_file()
        or run_path.is_symlink()
        or sha256_file(run_path) != target.old_run_sha256
    ):
        raise RecoveryError(f"Old filtered run receipt changed: {run_path}")
    if (
        not retry_path.is_file()
        or retry_path.is_symlink()
        or sha256_file(retry_path) != target.old_retry_sha256
    ):
        raise RecoveryError(f"Old terminal retry envelope changed: {retry_path}")
    run = read_json(run_path)
    retry = read_json(retry_path)
    retry_attempt = retry.get("retry_attempt") if isinstance(retry, dict) else None
    if (
        run.get("sample_id") != target.sample.sample_id
        or run.get("model_id") != MODEL_ID
        or run.get("adapter") != EXPECTED_ROUTE_ADAPTER
        or run.get("status") != "provider-failed"
        or run.get("provider_run_id") != target.supersedes_for_demo
        or run.get("provider_job_id") != target.old_provider_job_id
        or run.get("request_sha256") != target.old_request_sha256
        or run.get("provider_may_be_active") is not False
        or run.get("media") is not None
        or run.get("contract_check") is not None
        or FILTER_MARKER not in str(run.get("error"))
        or retry.get("retry_number") != 1
        or retry.get("agent_id") != AGENT_ID
        or not isinstance(retry_attempt, dict)
        or retry_attempt.get("provider_run_id") != target.supersedes_for_demo
    ):
        raise RecoveryError(f"Old provider-filtered evidence differs: {run_path}")
    output_path = _safe_relative_path(run.get("output_path"), label="old output_path")
    if (root / output_path).exists():
        raise RecoveryError(f"Old provider-filtered output unexpectedly exists: {output_path}")
    return {
        "provider_run_id": target.supersedes_for_demo,
        "provider_job_id": target.old_provider_job_id,
        "status": "provider-filtered",
        "request_sha256": target.old_request_sha256,
        "run_path": target.old_run_rel.as_posix(),
        "run_sha256": target.old_run_sha256,
        "retry_envelope_path": target.old_retry_rel.as_posix(),
        "retry_envelope_sha256": target.old_retry_sha256,
        "retry_v1_exhausted": True,
    }


def validate_superseded_receipts(
    root: Path = ROOT,
) -> dict[str, dict[str, Any]]:
    """Validate immutable filtered-attempt evidence without reading aggregate state."""

    evidence: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        _validate_source_and_context(target, root)
        evidence[target.sample.sample_id] = _validate_old_retry(target, root)
    return evidence


def validate_old_evidence(
    root: Path = ROOT,
    *,
    require_canonical_filtered: bool = True,
) -> dict[str, dict[str, Any]]:
    evidence = validate_superseded_receipts(root)
    if not require_canonical_filtered:
        return evidence

    aggregate = read_json(root / CANONICAL_MANIFEST_REL)
    outputs = aggregate.get("outputs") if isinstance(aggregate, dict) else None
    if (
        aggregate.get("ticket") != TICKET
        or aggregate.get("agent_id") != AGENT_ID
        or not isinstance(outputs, list)
    ):
        raise RecoveryError("Unexpected canonical PROMOPAGES-10060 manifest")
    for target in TARGETS:
        matches = [
            output
            for output in outputs
            if isinstance(output, dict)
            and output.get("article_slug") == target.sample.article_slug
            and output.get("image_id") == target.sample.image_id
            and output.get("model_id") == MODEL_ID
        ]
        if len(matches) != 1:
            raise RecoveryError(
                f"Expected one old canonical output for {target.sample.sample_id}"
            )
        old = matches[0]
        retry = old.get("retry")
        legacy_filtered = (
            old.get("provider_run_id") != target.supersedes_for_demo
            or old.get("status") != "provider-filtered"
            or old.get("recorded_status") != "provider-failed"
            or old.get("video_path") is not None
            or old.get("media") is not None
            or old.get("contract_check") is not None
            or old.get("selected_attempt") != "terminal-retry-v1-exhausted"
            or not isinstance(retry, dict)
            or retry.get("exhausted") is not True
        ) is False
        recovery = old.get("recovery")
        embedded_evidence = (
            recovery.get("old_provider_filtered")
            if isinstance(recovery, dict)
            else None
        )
        selected_with_preserved_evidence = (
            old.get("status") == "succeeded"
            and old.get("supersedes_for_demo") == target.supersedes_for_demo
            and isinstance(retry, dict)
            and retry.get("exhausted") is True
            and isinstance(recovery, dict)
            and embedded_evidence == evidence[target.sample.sample_id]
            and recovery.get("automatic_retry") is False
            and recovery.get("fallback") is False
        )
        if not legacy_filtered and not selected_with_preserved_evidence:
            raise RecoveryError(
                f"Old canonical output is not exhausted provider-filtered evidence: "
                f"{target.sample.sample_id}"
            )
    return evidence


def snapshot_old_receipts(root: Path = ROOT) -> dict[str, str]:
    paths = [
        path
        for target in TARGETS
        for path in (target.old_run_rel, target.old_retry_rel)
    ]
    return {path.as_posix(): sha256_file(root / path) for path in paths}


def provider_sample(entry: native.Entry) -> dict[str, Any]:
    target = _target_for_entry(entry)
    return {
        "sample_id": target.sample.sample_id,
        "article_slug": target.sample.article_slug,
        "image_id": target.sample.image_id,
        "image_number": target.sample.image_id,
        "source_path": target.sample.source_path,
        "source_url": target.source_url,
        "sha256": target.sample.source_sha256,
        "width": target.sample.width,
        "height": target.sample.height,
    }


def artifact_paths(entry: native.Entry, root: Path = ROOT) -> dict[str, Path]:
    target = _target_for_entry(entry)
    directory = (
        root
        / RECOVERY_ROOT_REL
        / "videos"
        / target.sample.article_slug
        / native.MODEL_DIRECTORIES[MODEL_ID]
    )
    stem = target.sample.image_id
    return {
        "directory": directory,
        "prompt": directory / f"{stem}.prompt.json",
        "run": directory / f"{stem}.run.json",
        "video": directory / f"{stem}.mp4",
    }


def _recovery_binding(target: RecoveryTarget) -> dict[str, Any]:
    return {
        "recovery_id": RECOVERY_ID,
        "logical_key": target.logical_key,
        "supersedes_for_demo": target.supersedes_for_demo,
        "old_status": "provider-filtered",
        "old_retry_v1_exhausted": True,
        "automatic_retry": False,
        "fallback": False,
    }


def load_recovery_job(entry: native.Entry, root: Path = ROOT) -> native.LiteJob:
    target = _target_for_entry(entry)
    contract = validate_contract(root)
    job = _NATIVE_LOAD_LITE_JOB(entry, root)
    summary = job.provenance
    expected_result = (
        ARTIFACT_NAMESPACE / target.sample.planning_run_id / "result.json"
    ).as_posix()
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("contract_version") != contract["contract_version"]
        or summary.get("models") != [MODEL_ID]
        or summary.get("source_image_sha256") != target.sample.source_sha256
        or summary.get("article_context_sha256") != target.context_sha256
        or summary.get("result_path") != expected_result
        or job.result_path != expected_result
    ):
        raise RecoveryError(
            f"New Lite provenance binding differs: {target.sample.planning_run_id}"
        )
    result = read_json(root / expected_result)
    models = result.get("models") if isinstance(result, dict) else None
    if (
        not isinstance(models, list)
        or len(models) != 1
        or not isinstance(models[0], dict)
        or models[0].get("model_id") != MODEL_ID
        or not isinstance(models[0].get("scene_plan"), str)
        or not models[0]["scene_plan"].strip()
    ):
        raise RecoveryError(
            f"New Lite result has no exact Veo scene plan: {target.sample.planning_run_id}"
        )
    return job


def recovery_prompt_artifact(job: native.LiteJob) -> dict[str, Any]:
    target = _target_for_entry(job.entry)
    document = _NATIVE_PROMPT_ARTIFACT(job)
    binding = _recovery_binding(target)
    document["supersedes_for_demo"] = target.supersedes_for_demo
    document["recovery"] = binding
    return document


def recovery_initial_run(
    job: native.LiteJob,
    paths: dict[str, Path],
    root: Path = ROOT,
) -> dict[str, Any]:
    target = _target_for_entry(job.entry)
    document = _NATIVE_INITIAL_RUN(job, paths, root)
    document["supersedes_for_demo"] = target.supersedes_for_demo
    document["recovery"] = _recovery_binding(target)
    return document


def recovery_materialize_entry(
    entry: native.Entry,
    root: Path = ROOT,
) -> dict[str, Any]:
    target = _target_for_entry(entry)
    row = _NATIVE_MATERIALIZE_ENTRY(entry, root)
    run = read_json(row["paths"]["run"])
    if (
        run.get("supersedes_for_demo") != target.supersedes_for_demo
        or run.get("recovery") != _recovery_binding(target)
    ):
        raise RecoveryError(
            f"Immutable recovery run binding changed: {row['paths']['run']}"
        )
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
        native.SAMPLES = tuple(target.sample for target in TARGETS)
        native.WAN_SUBMIT_MODE = None
        native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()
        native.provider_sample = provider_sample
        native.artifact_paths = artifact_paths
        native.prompt_artifact = recovery_prompt_artifact
        native.initial_run = recovery_initial_run
        native.matrix = lambda: ENTRIES
        native.load_lite_job = load_recovery_job
        native.materialize_entry = recovery_materialize_entry
        if native.matrix() != ENTRIES:
            raise RecoveryError("Native recovery matrix identity changed")
        yield
    finally:
        for name, value in saved.items():
            setattr(native, name, value)


def assert_request(
    target: RecoveryTarget,
    request: dict[str, Any],
    job: native.LiteJob,
) -> None:
    frames = [
        {
            "type": "image_url",
            "image_url": {"url": target.source_url},
            "frame_type": "first_frame",
        }
    ]
    if (
        request.get("model") != MODEL_ID
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
        or any(
            frame.get("frame_type") == "last_frame"
            for frame in request.get("frame_images", [])
            if isinstance(frame, dict)
        )
    ):
        raise RecoveryError(
            f"Non-exact Veo recovery request: {target.entry.provider_run_id}"
        )
    request_sha256 = transport.request_fingerprint(
        request, provider_sample(target.entry)
    )
    if request_sha256 == target.old_request_sha256:
        raise RecoveryError(
            f"New recovery request repeats the twice-filtered request: "
            f"{target.sample.sample_id}"
        )


def _planning_model(target: RecoveryTarget, root: Path) -> dict[str, Any]:
    path = root / ARTIFACT_NAMESPACE / target.sample.planning_run_id / "result.json"
    result = read_json(path)
    models = result.get("models") if isinstance(result, dict) else None
    if not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict):
        raise RecoveryError(f"Invalid recovery Lite result: {path}")
    return models[0]


def preflight(
    root: Path = ROOT,
    *,
    budget_cap_usd: str | Decimal = REQUIRED_OPERATOR_BUDGET_CAP_USD,
    require_canonical_filtered: bool = True,
) -> dict[str, Any]:
    accounting = accounting_document(budget_cap_usd)
    route = validate_route(root)
    contract = validate_contract(root)
    old_evidence = validate_old_evidence(
        root,
        require_canonical_filtered=require_canonical_filtered,
    )
    records: dict[str, dict[str, Any]] = {}
    with configured_native(root):
        for target in TARGETS:
            job = load_recovery_job(target.entry, root)
            prompt = native.provider_prompt(job)
            request = native.provider_request_preview(provider_sample(target.entry), prompt)
            assert_request(target, request, job)
            model = _planning_model(target, root)
            records[target.sample.sample_id] = {
                "planning_run_id": target.sample.planning_run_id,
                "planning_result_path": job.result_path,
                "planning_result_sha256": job.result_sha256,
                "provenance": native.safe_provenance(job),
                "structured_intent": dict(job.structured_intent),
                "scene_plan": model["scene_plan"].strip(),
                "positive_prompt": job.positive_prompt,
                "negative_prompt": job.negative_prompt,
                "request": request,
                "request_sha256": transport.request_fingerprint(
                    request, provider_sample(target.entry)
                ),
                "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
            }
    return {
        "route": route,
        "contract": contract,
        "accounting": accounting,
        "old_evidence": old_evidence,
        "records": records,
    }


def dry_run(
    budget_cap_usd: str | Decimal,
    root: Path = ROOT,
) -> int:
    state = preflight(root, budget_cap_usd=budget_cap_usd)
    for target in TARGETS:
        record = state["records"][target.sample.sample_id]
        print(
            f"PASS: {target.entry.provider_run_id} uses verified "
            f"{record['planning_run_id']} and supersedes "
            f"{target.supersedes_for_demo}",
            flush=True,
        )
    print(
        "PASS: validated exactly two new Veo requests under the $99.05 "
        "operator cap; no files written"
    )
    return 0


def _known_recovery_artifacts(root: Path) -> tuple[Path, ...]:
    paths: list[Path] = [root / GENERATION_MANIFEST_REL, root / RECOVERY_MANIFEST_REL]
    for entry in ENTRIES:
        artifact = artifact_paths(entry, root)
        paths.extend((artifact["prompt"], artifact["run"], artifact["video"]))
    return tuple(paths)


def _validate_mode_state(mode: str, root: Path) -> None:
    recovery_root = root / RECOVERY_ROOT_REL
    known = _known_recovery_artifacts(root)
    if mode == "generate":
        if recovery_root.exists():
            raise RecoveryError(
                f"Immutable recovery namespace already exists; use resume: {recovery_root}"
            )
        return
    if mode != "resume":
        raise RecoveryError(f"Unknown recovery mode: {mode}")
    if (
        not recovery_root.is_dir()
        or recovery_root.is_symlink()
        or not any(path.exists() for path in known)
    ):
        raise RecoveryError(
            f"Resume requires an existing recovery receipt namespace: {recovery_root}"
        )


@contextmanager
def recovery_run_lock(root: Path) -> Iterator[None]:
    lock_path = root / "scripts/clipmaker_lite_promopages_10060_femibion_veo_recovery.py"
    with lock_path.open("rb") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecoveryError("another Femibion Veo recovery coordinator is running") from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


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
    expected_accounting = accounting_document(REQUIRED_OPERATOR_BUDGET_CAP_USD)
    if state.get("accounting") != expected_accounting:
        raise RecoveryError("Recovery accounting state changed")
    raw_outputs = generation.get("outputs") if isinstance(generation, dict) else None
    if (
        generation.get("ticket") != TICKET
        or generation.get("batch_id") != PROVIDER_BATCH_ID
        or generation.get("agent_id") != AGENT_ID
        or generation.get("expected_outputs") != 2
        or not isinstance(raw_outputs, list)
        or len(raw_outputs) != 2
    ):
        raise RecoveryError("Recovery generation manifest identity changed")
    by_run_id = {
        output.get("provider_run_id"): output
        for output in raw_outputs
        if isinstance(output, dict)
    }
    if set(by_run_id) != set(_TARGET_BY_PROVIDER_RUN_ID):
        raise RecoveryError("Recovery generation manifest output set changed")

    outputs: list[dict[str, Any]] = []
    summary: dict[str, int] = {}
    accepted = 0
    for target in TARGETS:
        raw = by_run_id[target.entry.provider_run_id]
        expected_paths = artifact_paths(target.entry, root)
        expected_prompt_rel = expected_paths["prompt"].relative_to(root).as_posix()
        expected_run_rel = expected_paths["run"].relative_to(root).as_posix()
        expected_video_rel = expected_paths["video"].relative_to(root).as_posix()
        if (
            raw.get("sample_id") != target.sample.sample_id
            or raw.get("article_slug") != target.sample.article_slug
            or raw.get("source_path") != target.sample.source_path
            or raw.get("model_id") != MODEL_ID
            or raw.get("lite_run_id") != target.sample.planning_run_id
            or raw.get("prompt_path") != expected_prompt_rel
            or raw.get("run_path") != expected_run_rel
            or raw.get("video_path") != expected_video_rel
        ):
            raise RecoveryError(
                f"Recovery output identity changed: {target.entry.provider_run_id}"
            )
        prompt_receipt = read_json(expected_paths["prompt"])
        run_receipt = read_json(expected_paths["run"])
        if (
            prompt_receipt.get("provider_run_id") != target.entry.provider_run_id
            or prompt_receipt.get("supersedes_for_demo")
            != target.supersedes_for_demo
            or prompt_receipt.get("recovery") != _recovery_binding(target)
            or run_receipt.get("provider_run_id") != target.entry.provider_run_id
            or run_receipt.get("supersedes_for_demo") != target.supersedes_for_demo
            or run_receipt.get("recovery") != _recovery_binding(target)
            or run_receipt.get("status") != raw.get("recorded_status")
            or run_receipt.get("media") != raw.get("media")
            or run_receipt.get("contract_check") != raw.get("contract_check")
            or run_receipt.get("error") != raw.get("error")
            or run_receipt.get("provider_may_be_active")
            != raw.get("provider_may_be_active")
        ):
            raise RecoveryError(
                f"Recovery prompt/run receipt binding changed: "
                f"{target.entry.provider_run_id}"
            )
        record = state["records"][target.sample.sample_id]
        if (
            run_receipt.get("request") != record["request"]
            or run_receipt.get("request_sha256") != record["request_sha256"]
            or run_receipt.get("request_fingerprint_version")
            != record["request_fingerprint_version"]
        ):
            raise RecoveryError(
                f"Recovery provider request receipt changed: "
                f"{target.entry.provider_run_id}"
            )
        status = str(raw.get("status"))
        summary[status] = summary.get(status, 0) + 1
        video_path: str | None = None
        if _accepted_output(raw):
            media = raw["media"]
            relative_video = _safe_relative_path(
                raw.get("video_path"), label="recovery video_path"
            )
            absolute_video = root / relative_video
            if (
                not absolute_video.is_file()
                or absolute_video.is_symlink()
                or media.get("sha256") != sha256_file(absolute_video)
                or media.get("bytes") != absolute_video.stat().st_size
            ):
                raise RecoveryError(
                    f"Accepted recovery media receipt differs: {absolute_video}"
                )
            video_path = relative_video.as_posix()
            accepted += 1
        outputs.append(
            {
                "article_slug": target.sample.article_slug,
                "image_id": target.sample.image_id,
                "source_path": target.sample.source_path,
                "sample_id": target.sample.sample_id,
                "lite_run_id": target.sample.planning_run_id,
                "provider_run_id": target.entry.provider_run_id,
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
                "selected_attempt": "content-filter-recovery-v1",
                "supersedes_for_demo": target.supersedes_for_demo,
                "recovery": {
                    "recovery_id": RECOVERY_ID,
                    "supersedes_for_demo": target.supersedes_for_demo,
                    "old_provider_filtered": state["old_evidence"][
                        target.sample.sample_id
                    ],
                    "new_request_sha256": record["request_sha256"],
                    "request_changed": (
                        record["request_sha256"] != target.old_request_sha256
                    ),
                    "automatic_retry": False,
                    "fallback": False,
                },
            }
        )
    return {
        "schema_version": 1,
        "manifest_role": "promopages-10060-femibion-veo-content-filter-recovery",
        "ticket": TICKET,
        "recovery_id": RECOVERY_ID,
        "provider_batch_id": PROVIDER_BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "expected_outputs": 2,
        "accepted_output_count": accepted,
        "ready_for_merge": accepted == 2,
        "summary": summary,
        "route": state["route"],
        "contract": state["contract"],
        "accounting": expected_accounting,
        "generation_policy": {
            "exact_model_id": MODEL_ID,
            "exact_route_only": True,
            "automatic_fallback": False,
            "normal_run_discovery": False,
            "automatic_paid_retries": False,
            "maximum_submissions_per_new_provider_identity": 1,
            "resume_may_submit_only_never_submitted_pending_receipts": True,
            "resume_repeats_ambiguous_or_terminal_submit": False,
        },
        "merge_contract": {
            "target_manifest": CANONICAL_MANIFEST_REL.as_posix(),
            "logical_key": ["article_slug", "image_id", "model_id"],
            "replace_only_status": "provider-filtered",
            "replace_exactly": 2,
            "requires_ready_for_merge": True,
            "preserve_all_other_outputs": True,
            "demo_selection_field": "supersedes_for_demo",
        },
        "supersedes_for_demo": [
            {
                "logical_key": target.logical_key,
                "old_provider_run_id": target.supersedes_for_demo,
                "new_provider_run_id": target.entry.provider_run_id,
            }
            for target in TARGETS
        ],
        "planning": [
            {
                "planning_run_id": state["records"][target.sample.sample_id][
                    "planning_run_id"
                ],
                "result_path": state["records"][target.sample.sample_id][
                    "planning_result_path"
                ],
                "result_sha256": state["records"][target.sample.sample_id][
                    "planning_result_sha256"
                ],
                "provenance": state["records"][target.sample.sample_id][
                    "provenance"
                ],
            }
            for target in TARGETS
        ],
        "generation_manifest_path": GENERATION_MANIFEST_REL.as_posix(),
        "outputs": outputs,
    }


def write_recovery_manifest(state: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    generation = read_json(root / GENERATION_MANIFEST_REL)
    path = root / RECOVERY_MANIFEST_REL
    if path.is_file():
        current = read_json(path)
        existing_time = current.get("updated_at") if isinstance(current, dict) else None
        if isinstance(existing_time, str):
            unchanged = recovery_document(
                generation, state, root=root, updated_at=existing_time
            )
            if current == unchanged:
                return unchanged
    document = recovery_document(generation, state, root=root)
    transport.atomic_write_json(path, document)
    return document


def validate_recovery_for_canonical_overlay(
    root: Path = ROOT,
    *,
    budget_cap_usd: str | Decimal = REQUIRED_OPERATOR_BUDGET_CAP_USD,
) -> dict[str, Any]:
    """Validate a completed recovery without requiring canonical filtered rows.

    The aggregate overlay can call this both before and after replacement.  The
    pinned old run/retry receipts remain the immutable supersession evidence;
    the current canonical manifest is deliberately not read on this path.
    """

    state = preflight(
        root,
        budget_cap_usd=budget_cap_usd,
        require_canonical_filtered=False,
    )
    generation = read_json(root / GENERATION_MANIFEST_REL)
    path = root / RECOVERY_MANIFEST_REL
    actual = read_json(path)
    updated_at = actual.get("updated_at") if isinstance(actual, dict) else None
    if not isinstance(updated_at, str) or not updated_at:
        raise RecoveryError(f"Recovery manifest has no updated_at: {path}")
    expected = recovery_document(
        generation,
        state,
        root=root,
        updated_at=updated_at,
    )
    if actual != expected:
        raise RecoveryError(f"Recovery manifest differs from verified receipts: {path}")
    if (
        actual.get("ready_for_merge") is not True
        or actual.get("accepted_output_count") != 2
    ):
        raise RecoveryError("Recovery manifest is not ready for canonical overlay")
    return actual


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
            f"{mode} requires --allow-external-processing because the two new "
            "images and Lite prompts are sent to the exact Veo provider route"
        )
    state = preflight(root, budget_cap_usd=budget_cap_usd)
    before = snapshot_old_receipts(root)
    with recovery_run_lock(root):
        _validate_mode_state(mode, root)
        with configured_native(root):
            rows = native.materialize(root)
            if len(rows) != 2 or {row["entry"] for row in rows} != set(ENTRIES):
                raise RecoveryError("Materialized recovery matrix is not exactly two Veo jobs")
            argv = [
                "run",
                "--veo31-concurrency",
                "2",
                "--timeout",
                str(timeout),
                "--poll-interval",
                str(poll_interval),
                "--allow-external-processing",
            ]
            for entry in ENTRIES:
                argv.extend(("--run-id", entry.provider_run_id))
            result = native.main(argv, root)
        if snapshot_old_receipts(root) != before:
            raise RecoveryError("Old provider-filtered receipts changed during recovery")
        manifest = write_recovery_manifest(state, root)
    print(
        f"recovery manifest: {RECOVERY_MANIFEST_REL.as_posix()} "
        f"ready_for_merge={str(manifest['ready_for_merge']).lower()}",
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
    dry = commands.add_parser(
        "dry-run", help="validate both new requests without writes"
    )
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
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
