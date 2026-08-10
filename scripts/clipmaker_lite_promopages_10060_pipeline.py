#!/usr/bin/env python3
"""Coordinate the resumable PROMOPAGES-10060 Clipmaker Lite batch.

The batch is discovered from the ticket article configuration plus the
namespaced image manifest and article contexts.  It includes every manifest
image from every successfully extracted article, including each cover, in
article/block order.  One isolated Lite plan contains independent plans for all
three exact model IDs, and the provider matrix uses the locked generation
registry without discovery or fallback.

This module intentionally writes only the selected registered batch namespace
and that batch's separate final sidecar.  With no ``--batch`` it preserves the
frozen legacy PROMOPAGES-10060 behavior; extension runs never rewrite or extend
the legacy inventory, provider receipts, or final sidecar in place.
"""

from __future__ import annotations

import argparse
import copy
import csv
import fcntl
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-10060"
LEGACY_BATCH_ID = "promopages-10060-lite-all-images-20260805-v2"
CAMPAIGN_EXTENSION_BATCH_ID = "promopages-10060-campaigns-20260805-v1"
ARTICLE_02_BATCH_ID = "promopages-10060-article-02-20260806-v2"
CAMPAIGN_20260807_BATCH_ID = "promopages-10060-campaigns-20260807-v1"
AGENT_ID = "clipmaker-lite"
MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
REQUIRED_CONTRACT_VERSION = "2.0.8"

CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
FROZEN_206_CONTRACT_REL = Path(
    "docs/agents/clipmaker-lite/contracts/contract-2.0.6.json"
)
FROZEN_206_CONTRACT_SHA256 = (
    "ad0e5f3026d27a4f3c25b5c344ef678a2f10b3eb92848f24eec5e28566a2f98c"
)
FROZEN_206_BATCH_IDS = frozenset(
    {LEGACY_BATCH_ID, CAMPAIGN_EXTENSION_BATCH_ID}
)
FROZEN_207_CONTRACT_REL = Path(
    "docs/agents/clipmaker-lite/contracts/contract-2.0.7.json"
)
FROZEN_207_CONTRACT_SHA256 = (
    "1e804e0f1f8cddb8738179e50c50688a0b8d5ef4480c1f41dc1828f892fe17dd"
)
FROZEN_207_BATCH_IDS = frozenset(
    {ARTICLE_02_BATCH_ID, CAMPAIGN_20260807_BATCH_ID}
)
FROZEN_CONTRACTS = {
    "2.0.6": {
        "path": FROZEN_206_CONTRACT_REL,
        "canonical_sha256": FROZEN_206_CONTRACT_SHA256,
        "batch_ids": FROZEN_206_BATCH_IDS,
    },
    "2.0.7": {
        "path": FROZEN_207_CONTRACT_REL,
        "canonical_sha256": FROZEN_207_CONTRACT_SHA256,
        "batch_ids": FROZEN_207_BATCH_IDS,
    },
}
FROZEN_BATCH_CONTRACT_VERSIONS = {
    batch_id: contract_version
    for contract_version, frozen in FROZEN_CONTRACTS.items()
    for batch_id in frozen["batch_ids"]
}
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
ARTIFACT_NAMESPACE = Path("artifacts/clipmaker-lite/v1")

FEMIBION_VEO_RECOVERY_VERSION = 1
FEMIBION_VEO_RECOVERY_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v1"
)
FEMIBION_VEO_RECOVERY_PROVIDER_BATCH_ID = (
    f"{FEMIBION_VEO_RECOVERY_ID}-provider"
)
FEMIBION_VEO_RECOVERY_MODEL_ID = "google/veo-3.1-lite"
FEMIBION_VEO_RECOVERY_ROOT_REL = (
    Path("clipmaker-lite-test/runs") / FEMIBION_VEO_RECOVERY_ID
)
FEMIBION_VEO_RECOVERY_MANIFEST_REL = (
    FEMIBION_VEO_RECOVERY_ROOT_REL / "recovery-manifest.json"
)
FEMIBION_VEO_RECOVERY_GENERATION_MANIFEST_REL = (
    FEMIBION_VEO_RECOVERY_ROOT_REL / "generation-manifest.json"
)
FEMIBION_VEO_RECOVERY_ACCOUNTING_COST_USD = Decimal("0.35")
FEMIBION_VEO_FINAL_SELECTION_VERSION = 7
FEMIBION_VEO_FINAL_SELECTION_ID = (
    "promopages-10060-femibion-veo-recovery-20260810-v7-"
    "all-attempts-selection"
)
FEMIBION_VEO_FINAL_SELECTION_ROOT_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-femibion-veo-recovery-20260810-v7"
)
FEMIBION_VEO_FINAL_SELECTION_MANIFEST_REL = (
    FEMIBION_VEO_FINAL_SELECTION_ROOT_REL
    / "all-attempts-selection-manifest.json"
)
FEMIBION_VEO_RECOVERY_KEYS = (
    (
        "07-femibion-gotovites-k-beremennosti",
        "06",
        FEMIBION_VEO_RECOVERY_MODEL_ID,
    ),
    (
        "08-femibion-grudnoe-vskarmlivanie",
        "05",
        FEMIBION_VEO_RECOVERY_MODEL_ID,
    ),
)
FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS = {
    FEMIBION_VEO_RECOVERY_KEYS[0]: (
        "promopages-10060-lite-all-images-20260805-v2-terminal-retry-v1-"
        "6243bd1bbb1a1e3fe253-07-femibion-gotovites-k-beremennosti-06-"
        "veo-3-1-lite"
    ),
    FEMIBION_VEO_RECOVERY_KEYS[1]: (
        "promopages-10060-lite-all-images-20260805-v2-terminal-retry-v1-"
        "0cc5261325a58f1785ee-08-femibion-grudnoe-vskarmlivanie-05-"
        "veo-3-1-lite"
    ),
}

# A provider-confirmed terminal failure may be retried only by an explicit
# operator command in a new, deterministic namespace.  The primary batch
# receipts are immutable evidence and are never rewritten by this mechanism.
TERMINAL_RETRY_VERSION = 1
TERMINAL_RETRY_ACCOUNTING_COST_USD = Decimal("0.35")

# A provider POST can be left in an honestly ambiguous state when the client
# loses the response after the paid request may already have reached the
# provider. Such a receipt is never rewritten or reclassified as pre-submit.
# The only escape hatch is one operator-authorized, separately accounted retry
# on the exact frozen route in this quarantine namespace.
AMBIGUOUS_SUBMIT_RETRY_VERSION = 1
AMBIGUOUS_SUBMIT_RETRY_ACCOUNTING_COST_USD = Decimal("0.35")

# A small, batch-local allowlist covers sources rejected by both Wan transports
# for a provider input constraint (the legacy >20 MiB image or an extension
# image below the 240 px minimum dimension).  The only allowed remediation is
# one explicit retry per exact failed primary, replacing only the provider
# request's image URL with the batch policy's frozen normalized replacement
# (a manifest-published /scale_1200 variant for legacy sources, or an exact
# commit-pinned repository asset for registered extension sources). The
# original Lite analysis, prompts, model routes, and primary receipts remain
# immutable.
NORMALIZED_INPUT_RETRY_VERSION = 1
NORMALIZED_INPUT_RETRY_ACCOUNTING_COST_USD = Decimal("0.35")
# One ticket-specific normalized-input provider job remained active beyond the
# operator's acceptable wait window.  The operator may explicitly supersede
# that exact job once.  This is not retry-v2: the original retry envelope,
# receipt, and provider identity remain immutable evidence, while the new paid
# attempt lives below a separate nested namespace and has its own reservation.
NORMALIZED_INPUT_SUPERSEDE_VERSION = 1
NORMALIZED_INPUT_SUPERSEDE_ACCOUNTING_COST_USD = Decimal("0.35")
NORMALIZED_INPUT_SUPERSEDE_DIRECTORY_NAME = "superseding-attempt-v1"
NORMALIZED_INPUT_SUPERSEDE_TARGET = {
    "batch_id": CAMPAIGN_EXTENSION_BATCH_ID,
    "article_slug": "18-volma-plitochnyi-klei",
    "image_id": "07",
    "model_id": "alibaba/wan-2.7",
    "normalized_retry_provider_run_id": (
        "promopages-10060-campaigns-20260805-v1-normalized-input-retry-v1-"
        "c45a8447813d1b4e4df0-18-volma-plitochnyi-klei-07-wan-2-7"
    ),
    "active_provider_job_id": "novcFDcwbuZkgtrmgQIY",
}
NORMALIZED_INPUT_MAX_BYTES = 20 * 1024 * 1024
NORMALIZED_INPUT_MIN_DIMENSION = 240
DEFAULT_OPERATOR_BUDGET_CAP_USD = Decimal("100.00")
# Ticket-local accounting envelope used to admit whole articles in their
# configured order. The frozen PROMOPAGES-9930 estimate reserves $0.35 for
# every output. This is conservative for Wan 2.2 compared with its observed
# $0.18 Segmind response cost. Runtime route discovery remains forbidden.
ACCOUNTING_COST_PER_OUTPUT_USD = {
    "alibaba/wan-2.2": Decimal("0.35"),
    "alibaba/wan-2.7": Decimal("0.35"),
    "google/veo-3.1-lite": Decimal("0.35"),
}
ROUTE_CAPACITIES = {
    "alibaba/wan-2.2": 1,
    "alibaba/wan-2.7": 3,
    "google/veo-3.1-lite": 3,
}
ROUTE_IDENTITIES = {
    "alibaba/wan-2.2": ("eliza-segmind", "eliza-synchronous-binary"),
    "alibaba/wan-2.7": ("eliza-openrouter", "eliza-video-jobs"),
    "google/veo-3.1-lite": ("eliza-openrouter", "eliza-video-jobs"),
}


class PipelineError(RuntimeError):
    """A fail-closed error in the PROMOPAGES-10060 coordinator."""


@dataclass(frozen=True)
class NormalizedInputReplacement:
    """One immutable, publicly fetchable normalized source artifact."""

    strategy: str
    repository_path: str
    url: str
    sha256: str
    byte_size: int
    width: int
    height: int
    image_format: str


@dataclass(frozen=True)
class NormalizedInputRetryTarget:
    """One immutable source/model allowlist entry for input normalization."""

    article_slug: str
    image_id: str
    source_sha256: str
    model_ids: tuple[str, ...]
    failure_kind: str = "maximum-bytes"
    replacement: NormalizedInputReplacement | None = None


@dataclass(frozen=True)
class BatchSpec:
    """Registered immutable input/output binding for one coordinator batch."""

    batch_id: str
    dataset_prefix: str
    article_numbers: tuple[int, ...]
    ticket_config_rel: Path
    extraction_report_rel: Path
    source_manifest_rel: Path
    source_image_root_rel: Path
    source_context_root_rel: Path
    final_manifest_rel: Path
    inventory_manifest_role: str
    final_manifest_role: str
    terminal_retry_manifest_role: str
    ambiguous_retry_manifest_role: str
    normalized_retry_manifest_role: str
    normalized_asset_manifest_role: str
    hard_budget_cap_usd: Decimal | None
    normalized_input_retry_allowlist: tuple[NormalizedInputRetryTarget, ...]


LEGACY_NORMALIZED_INPUT_TARGET = NormalizedInputRetryTarget(
    article_slug="12-dream-island-7-fishek",
    image_id="08",
    source_sha256=(
        "2cf03435b0ae53b208f033a4ec407750ed494e0cd6ec6c76e1b36e397dd1377d"
    ),
    model_ids=("alibaba/wan-2.2", "alibaba/wan-2.7"),
)

CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS = (
    NormalizedInputRetryTarget(
        article_slug="18-volma-plitochnyi-klei",
        image_id="05",
        source_sha256=(
            "95a38e9469f6055c7eab934ab7173af57d5445112e835e200a83964f74938543"
        ),
        model_ids=("alibaba/wan-2.2", "alibaba/wan-2.7"),
        failure_kind="minimum-dimension",
        replacement=NormalizedInputReplacement(
            strategy="deterministic-uniform-upscale",
            repository_path=(
                "clipmaker-lite-test/runs/"
                "promopages-10060-campaigns-20260805-v1/"
                "normalized-input-assets-v1/660c32c4d1331cb3a82d/normalized.png"
            ),
            url=(
                "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
                "alice-live-images-test/"
                "25995ee6ea168d2ae7025e5a416bc008ae17a908/"
                "clipmaker-lite-test/runs/"
                "promopages-10060-campaigns-20260805-v1/"
                "normalized-input-assets-v1/660c32c4d1331cb3a82d/normalized.png"
            ),
            sha256=(
                "4ad98c730c783a63bce382ecffe640d51c936b3ccaec019b637861f8ddbf5b23"
            ),
            byte_size=46_883,
            width=882,
            height=256,
            image_format="PNG",
        ),
    ),
    NormalizedInputRetryTarget(
        article_slug="18-volma-plitochnyi-klei",
        image_id="07",
        source_sha256=(
            "07fd4373396697d3078265a72337a759d591449deb6cafe9869e9d2f92fb43e8"
        ),
        model_ids=("alibaba/wan-2.2", "alibaba/wan-2.7"),
        failure_kind="minimum-dimension",
        replacement=NormalizedInputReplacement(
            strategy="deterministic-uniform-upscale",
            repository_path=(
                "clipmaker-lite-test/runs/"
                "promopages-10060-campaigns-20260805-v1/"
                "normalized-input-assets-v1/0535f187b92384618210/normalized.png"
            ),
            url=(
                "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
                "alice-live-images-test/"
                "25995ee6ea168d2ae7025e5a416bc008ae17a908/"
                "clipmaker-lite-test/runs/"
                "promopages-10060-campaigns-20260805-v1/"
                "normalized-input-assets-v1/0535f187b92384618210/normalized.png"
            ),
            sha256=(
                "7f71227971a99ca0f204eccadb89a706128eabfb6022657bf8718e952fca70e4"
            ),
            byte_size=57_771,
            width=828,
            height=256,
            image_format="PNG",
        ),
    ),
    NormalizedInputRetryTarget(
        article_slug="18-volma-plitochnyi-klei",
        image_id="08",
        source_sha256=(
            "ff2fa123c99e8b82a954af9870660faa5306e3d6ebb7c57675df542077fbaa03"
        ),
        model_ids=("alibaba/wan-2.2", "alibaba/wan-2.7"),
        failure_kind="minimum-dimension",
        replacement=NormalizedInputReplacement(
            strategy="deterministic-uniform-upscale",
            repository_path=(
                "clipmaker-lite-test/runs/"
                "promopages-10060-campaigns-20260805-v1/"
                "normalized-input-assets-v1/2d974dbe489b2e6617a3/normalized.png"
            ),
            url=(
                "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
                "alice-live-images-test/"
                "25995ee6ea168d2ae7025e5a416bc008ae17a908/"
                "clipmaker-lite-test/runs/"
                "promopages-10060-campaigns-20260805-v1/"
                "normalized-input-assets-v1/2d974dbe489b2e6617a3/normalized.png"
            ),
            sha256=(
                "1a005159d7efaee55f2124844851b7135f28cccfcad0463ad1ac2f5dec1f589a"
            ),
            byte_size=246_119,
            width=998,
            height=256,
            image_format="PNG",
        ),
    ),
)

BATCH_SPECS = {
    LEGACY_BATCH_ID: BatchSpec(
        batch_id=LEGACY_BATCH_ID,
        dataset_prefix="PROMOPAGES-10060",
        article_numbers=tuple(range(1, 15)),
        ticket_config_rel=Path("PROMOPAGES-10060/articles.json"),
        extraction_report_rel=Path("PROMOPAGES-10060/extraction-report.json"),
        source_manifest_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060/articles/manifest.csv"
        ),
        source_image_root_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060/articles"
        ),
        source_context_root_rel=Path(
            "PROMOPAGES-9884/PROMOPAGES-10060/articles"
        ),
        final_manifest_rel=Path(
            "clipmaker-lite-test/promopages-10060-manifest.json"
        ),
        inventory_manifest_role="promopages-10060-frozen-generation-inventory",
        final_manifest_role="promopages-10060-all-images",
        terminal_retry_manifest_role="promopages-10060-terminal-provider-retry",
        ambiguous_retry_manifest_role="promopages-10060-ambiguous-submit-retry",
        normalized_retry_manifest_role="promopages-10060-normalized-input-retry",
        normalized_asset_manifest_role="promopages-10060-normalized-input-asset",
        hard_budget_cap_usd=Decimal("100.00"),
        normalized_input_retry_allowlist=(LEGACY_NORMALIZED_INPUT_TARGET,),
    ),
    CAMPAIGN_EXTENSION_BATCH_ID: BatchSpec(
        batch_id=CAMPAIGN_EXTENSION_BATCH_ID,
        dataset_prefix="PROMOPAGES-10060-campaigns-20260805-v1",
        article_numbers=(15, 16, 17, 18),
        ticket_config_rel=Path(
            "PROMOPAGES-10060/campaigns-20260805-v1/articles.json"
        ),
        extraction_report_rel=Path(
            "PROMOPAGES-10060/campaigns-20260805-v1/extraction-report.json"
        ),
        source_manifest_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060-campaigns-20260805-v1/"
            "articles/manifest.csv"
        ),
        source_image_root_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060-campaigns-20260805-v1/articles"
        ),
        source_context_root_rel=Path(
            "PROMOPAGES-9884/PROMOPAGES-10060-campaigns-20260805-v1/articles"
        ),
        final_manifest_rel=Path(
            "clipmaker-lite-test/"
            "promopages-10060-campaigns-20260805-v1-manifest.json"
        ),
        inventory_manifest_role=(
            "promopages-10060-campaign-extension-frozen-generation-inventory"
        ),
        final_manifest_role="promopages-10060-campaign-extension",
        terminal_retry_manifest_role=(
            "promopages-10060-campaign-extension-terminal-provider-retry"
        ),
        ambiguous_retry_manifest_role=(
            "promopages-10060-campaign-extension-ambiguous-submit-retry"
        ),
        normalized_retry_manifest_role=(
            "promopages-10060-campaign-extension-normalized-input-retry"
        ),
        normalized_asset_manifest_role=(
            "promopages-10060-campaign-extension-normalized-input-asset"
        ),
        # This extension was explicitly authorized without the legacy $100
        # ceiling.  The operator must still provide a positive aggregate cap;
        # the frozen inventory binds that exact cap for every resume/retry.
        hard_budget_cap_usd=None,
        normalized_input_retry_allowlist=(
            CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS
        ),
    ),
    ARTICLE_02_BATCH_ID: BatchSpec(
        batch_id=ARTICLE_02_BATCH_ID,
        dataset_prefix="PROMOPAGES-10060-article-02-20260806-v1",
        article_numbers=(2,),
        ticket_config_rel=Path(
            "PROMOPAGES-10060/article-02-20260806-v1/articles.json"
        ),
        extraction_report_rel=Path(
            "PROMOPAGES-10060/article-02-20260806-v1/extraction-report.json"
        ),
        source_manifest_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060-article-02-20260806-v1/"
            "articles/manifest.csv"
        ),
        source_image_root_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060-article-02-20260806-v1/articles"
        ),
        source_context_root_rel=Path(
            "PROMOPAGES-9884/PROMOPAGES-10060-article-02-20260806-v1/articles"
        ),
        final_manifest_rel=Path(
            "clipmaker-lite-test/"
            "promopages-10060-article-02-20260806-v2-manifest.json"
        ),
        inventory_manifest_role=(
            "promopages-10060-article-02-frozen-generation-inventory"
        ),
        final_manifest_role="promopages-10060-article-02",
        terminal_retry_manifest_role=(
            "promopages-10060-article-02-terminal-provider-retry"
        ),
        ambiguous_retry_manifest_role=(
            "promopages-10060-article-02-ambiguous-submit-retry"
        ),
        normalized_retry_manifest_role=(
            "promopages-10060-article-02-normalized-input-retry"
        ),
        normalized_asset_manifest_role=(
            "promopages-10060-article-02-normalized-input-asset"
        ),
        hard_budget_cap_usd=None,
        normalized_input_retry_allowlist=(),
    ),
    CAMPAIGN_20260807_BATCH_ID: BatchSpec(
        batch_id=CAMPAIGN_20260807_BATCH_ID,
        dataset_prefix="PROMOPAGES-10060-campaigns-20260807-v1",
        article_numbers=(19, 20, 21),
        ticket_config_rel=Path(
            "PROMOPAGES-10060/campaigns-20260807-v1/articles.json"
        ),
        extraction_report_rel=Path(
            "PROMOPAGES-10060/campaigns-20260807-v1/extraction-report.json"
        ),
        source_manifest_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060-campaigns-20260807-v1/"
            "articles/manifest.csv"
        ),
        source_image_root_rel=Path(
            "PROMOPAGES-9857/PROMOPAGES-10060-campaigns-20260807-v1/articles"
        ),
        source_context_root_rel=Path(
            "PROMOPAGES-9884/PROMOPAGES-10060-campaigns-20260807-v1/articles"
        ),
        final_manifest_rel=Path(
            "clipmaker-lite-test/"
            "promopages-10060-campaigns-20260807-v1-manifest.json"
        ),
        inventory_manifest_role=(
            "promopages-10060-campaigns-20260807-frozen-generation-inventory"
        ),
        final_manifest_role="promopages-10060-campaigns-20260807-extension",
        terminal_retry_manifest_role=(
            "promopages-10060-campaigns-20260807-terminal-provider-retry"
        ),
        ambiguous_retry_manifest_role=(
            "promopages-10060-campaigns-20260807-ambiguous-submit-retry"
        ),
        normalized_retry_manifest_role=(
            "promopages-10060-campaigns-20260807-normalized-input-retry"
        ),
        normalized_asset_manifest_role=(
            "promopages-10060-campaigns-20260807-normalized-input-asset"
        ),
        # The operator supplies the exact aggregate cap for this separately
        # authorized extension; the frozen inventory binds it on resume.
        hard_budget_cap_usd=None,
        normalized_input_retry_allowlist=(),
    ),
}


def _validate_batch_specs() -> None:
    seen_paths: set[tuple[str, str]] = set()
    for selector, spec in BATCH_SPECS.items():
        if selector != spec.batch_id:
            raise PipelineError(f"Batch selector/id mismatch: {selector!r}")
        if not spec.article_numbers or any(
            isinstance(number, bool) or not isinstance(number, int) or number < 1
            for number in spec.article_numbers
        ):
            raise PipelineError(f"Batch article numbers are invalid: {selector}")
        if len(spec.article_numbers) != len(set(spec.article_numbers)):
            raise PipelineError(f"Batch article numbers are duplicated: {selector}")
        for label, path in (
            ("ticket config", spec.ticket_config_rel),
            ("extraction report", spec.extraction_report_rel),
            ("source manifest", spec.source_manifest_rel),
            ("source image root", spec.source_image_root_rel),
            ("source context root", spec.source_context_root_rel),
            ("final manifest", spec.final_manifest_rel),
        ):
            if path.is_absolute() or ".." in path.parts:
                raise PipelineError(
                    f"Registered batch {label} escapes the workspace: {path}"
                )
            identity = (label, path.as_posix())
            if identity in seen_paths:
                raise PipelineError(
                    f"Registered batches share the same {label}: {path}"
                )
            seen_paths.add(identity)
        logical_keys: set[tuple[str, str, str]] = set()
        for target in spec.normalized_input_retry_allowlist:
            if (
                len(target.source_sha256) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in target.source_sha256
                )
                or not target.model_ids
                or any(
                    model_id not in {"alibaba/wan-2.2", "alibaba/wan-2.7"}
                    for model_id in target.model_ids
                )
                or target.failure_kind
                not in {"maximum-bytes", "minimum-dimension"}
            ):
                raise PipelineError(
                    f"Invalid normalized-input allowlist in batch {selector}"
                )
            replacement = target.replacement
            if target.failure_kind == "maximum-bytes" and replacement is not None:
                raise PipelineError(
                    f"Legacy maximum-bytes target cannot replace its MDS strategy: "
                    f"{target.article_slug}/{target.image_id}"
                )
            if target.failure_kind == "minimum-dimension":
                parsed = (
                    urlparse(replacement.url)
                    if isinstance(replacement, NormalizedInputReplacement)
                    else None
                )
                repository_path = (
                    PurePosixPath(replacement.repository_path)
                    if isinstance(replacement, NormalizedInputReplacement)
                    else None
                )
                raw_prefix = (
                    "/UnidentifiedRaccoon/alice-live-images-test/"
                    if parsed is not None
                    else ""
                )
                raw_tail = (
                    parsed.path.removeprefix(raw_prefix)
                    if parsed is not None and parsed.path.startswith(raw_prefix)
                    else ""
                )
                commit_sha, separator, raw_repository_path = raw_tail.partition("/")
                if (
                    replacement is None
                    or replacement.strategy != "deterministic-uniform-upscale"
                    or repository_path is None
                    or repository_path.is_absolute()
                    or ".." in repository_path.parts
                    or parsed is None
                    or parsed.scheme != "https"
                    or parsed.hostname != "raw.githubusercontent.com"
                    or parsed.params
                    or parsed.query
                    or parsed.fragment
                    or not separator
                    or len(commit_sha) != 40
                    or any(character not in "0123456789abcdef" for character in commit_sha)
                    or raw_repository_path != replacement.repository_path
                    or len(replacement.sha256) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in replacement.sha256
                    )
                    or not 0 < replacement.byte_size <= NORMALIZED_INPUT_MAX_BYTES
                    or replacement.width < NORMALIZED_INPUT_MIN_DIMENSION
                    or replacement.height < NORMALIZED_INPUT_MIN_DIMENSION
                    or replacement.image_format not in {"JPEG", "PNG"}
                ):
                    raise PipelineError(
                        f"Invalid commit-pinned normalized replacement in batch "
                        f"{selector}: {target.article_slug}/{target.image_id}"
                    )
            for model_id in target.model_ids:
                key = (target.article_slug, target.image_id, model_id)
                if key in logical_keys:
                    raise PipelineError(
                        f"Duplicate normalized-input allowlist key: {key}"
                    )
                logical_keys.add(key)


def activate_batch(batch_id: str) -> BatchSpec:
    """Activate one registered batch before reading inputs or parsing budget."""

    try:
        spec = BATCH_SPECS[batch_id]
    except KeyError as exc:
        raise PipelineError(f"Unknown registered batch: {batch_id!r}") from exc

    global ACTIVE_BATCH_SPEC
    global BATCH_ID, PLANNING_BATCH_ID, DATASET_PREFIX, EXPECTED_ARTICLE_NUMBERS
    global TICKET_CONFIG_REL, EXTRACTION_REPORT_REL, SOURCE_MANIFEST_REL
    global SOURCE_IMAGE_ROOT_REL, SOURCE_CONTEXT_ROOT_REL
    global BATCH_ROOT_REL, INVENTORY_MANIFEST_REL, GENERATION_MANIFEST_REL
    global VERIFICATION_REPORT_REL, FINAL_MANIFEST_REL
    global TERMINAL_RETRY_NAMESPACE_REL, AMBIGUOUS_SUBMIT_RETRY_NAMESPACE_REL
    global NORMALIZED_INPUT_RETRY_NAMESPACE_REL
    global NORMALIZED_INPUT_ASSET_NAMESPACE_REL
    global NORMALIZED_INPUT_SUPERSEDE_NAMESPACE_REL
    global INVENTORY_MANIFEST_ROLE, FINAL_MANIFEST_ROLE
    global TERMINAL_RETRY_MANIFEST_ROLE, AMBIGUOUS_RETRY_MANIFEST_ROLE
    global NORMALIZED_RETRY_MANIFEST_ROLE, NORMALIZED_ASSET_MANIFEST_ROLE
    global NORMALIZED_INPUT_SUPERSEDE_MANIFEST_ROLE
    global HARD_BUDGET_CAP_USD, NORMALIZED_INPUT_RETRY_ALLOWLIST
    global NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
    global NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
    global NORMALIZED_INPUT_ELIGIBLE_SOURCE_SHA256
    global NORMALIZED_INPUT_ELIGIBLE_MODELS

    ACTIVE_BATCH_SPEC = spec
    BATCH_ID = spec.batch_id
    PLANNING_BATCH_ID = spec.batch_id
    DATASET_PREFIX = spec.dataset_prefix
    EXPECTED_ARTICLE_NUMBERS = spec.article_numbers
    TICKET_CONFIG_REL = spec.ticket_config_rel
    EXTRACTION_REPORT_REL = spec.extraction_report_rel
    SOURCE_MANIFEST_REL = spec.source_manifest_rel
    SOURCE_IMAGE_ROOT_REL = spec.source_image_root_rel
    SOURCE_CONTEXT_ROOT_REL = spec.source_context_root_rel
    BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / spec.batch_id
    INVENTORY_MANIFEST_REL = BATCH_ROOT_REL / "inventory.json"
    GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"
    VERIFICATION_REPORT_REL = BATCH_ROOT_REL / "verification-report.json"
    FINAL_MANIFEST_REL = spec.final_manifest_rel
    TERMINAL_RETRY_NAMESPACE_REL = (
        BATCH_ROOT_REL / "terminal-provider-retries-v1"
    )
    AMBIGUOUS_SUBMIT_RETRY_NAMESPACE_REL = (
        BATCH_ROOT_REL / "ambiguous-submit-retries-v1"
    )
    NORMALIZED_INPUT_RETRY_NAMESPACE_REL = (
        BATCH_ROOT_REL / "normalized-input-retries-v1"
    )
    NORMALIZED_INPUT_ASSET_NAMESPACE_REL = (
        BATCH_ROOT_REL / "normalized-input-assets-v1"
    )
    if spec.batch_id == NORMALIZED_INPUT_SUPERSEDE_TARGET["batch_id"]:
        superseded_primary_id = (
            f"{spec.batch_id}-"
            f"{NORMALIZED_INPUT_SUPERSEDE_TARGET['article_slug']}-"
            f"{NORMALIZED_INPUT_SUPERSEDE_TARGET['image_id']}-"
            f"{native.MODEL_SUFFIXES[NORMALIZED_INPUT_SUPERSEDE_TARGET['model_id']]}"
        )
        superseded_key = hashlib.sha256(
            f"normalized-input-v1:{superseded_primary_id}".encode("utf-8")
        ).hexdigest()[:20]
        # Fail closed if the registered exact run identity and the deterministic
        # normalized retry binding ever drift apart.
        if superseded_key != "c45a8447813d1b4e4df0":
            raise PipelineError("Normalized-input supersede target binding changed")
        NORMALIZED_INPUT_SUPERSEDE_NAMESPACE_REL = (
            NORMALIZED_INPUT_RETRY_NAMESPACE_REL
            / superseded_key
            / NORMALIZED_INPUT_SUPERSEDE_DIRECTORY_NAME
        )
    else:
        # No other registered batch is authorized to create this namespace.
        NORMALIZED_INPUT_SUPERSEDE_NAMESPACE_REL = (
            BATCH_ROOT_REL / "normalized-input-supersede-disabled"
        )
    INVENTORY_MANIFEST_ROLE = spec.inventory_manifest_role
    FINAL_MANIFEST_ROLE = spec.final_manifest_role
    TERMINAL_RETRY_MANIFEST_ROLE = spec.terminal_retry_manifest_role
    AMBIGUOUS_RETRY_MANIFEST_ROLE = spec.ambiguous_retry_manifest_role
    NORMALIZED_RETRY_MANIFEST_ROLE = spec.normalized_retry_manifest_role
    NORMALIZED_ASSET_MANIFEST_ROLE = spec.normalized_asset_manifest_role
    NORMALIZED_INPUT_SUPERSEDE_MANIFEST_ROLE = (
        f"{spec.normalized_retry_manifest_role}-supersede"
    )
    HARD_BUDGET_CAP_USD = spec.hard_budget_cap_usd
    NORMALIZED_INPUT_RETRY_ALLOWLIST = spec.normalized_input_retry_allowlist

    # Compatibility aliases for the frozen legacy tests and audit documents.
    # Runtime authorization always consults NORMALIZED_INPUT_RETRY_ALLOWLIST.
    target = (
        spec.normalized_input_retry_allowlist[0]
        if spec.normalized_input_retry_allowlist
        else None
    )
    NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG = target.article_slug if target else ""
    NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID = target.image_id if target else ""
    NORMALIZED_INPUT_ELIGIBLE_SOURCE_SHA256 = target.source_sha256 if target else ""
    NORMALIZED_INPUT_ELIGIBLE_MODELS = target.model_ids if target else ()
    return spec


_validate_batch_specs()
activate_batch(LEGACY_BATCH_ID)


@dataclass(frozen=True)
class ArticleConfig:
    number: int
    label: str
    folder: str
    url: str

    @property
    def number_key(self) -> str:
        return f"{self.number:02d}"


@dataclass(frozen=True)
class NamespacedSample:
    """The subset of ``native.Sample`` with ticket-specific bound paths."""

    sample_id: str
    article_slug: str
    image_id: str
    filename: str
    source_sha256: str
    width: int
    height: int
    bound_source_path: str
    bound_context_path: str

    @property
    def source_path(self) -> str:
        return self.bound_source_path

    @property
    def context_path(self) -> str:
        return self.bound_context_path

    @property
    def planning_run_id(self) -> str:
        return f"{PLANNING_BATCH_ID}-{self.sample_id}"


@dataclass(frozen=True)
class Article:
    number: str
    slug: str
    label: str
    url: str
    title: str
    lead: str
    context_path: str
    context_sha256: str
    cover_image: dict[str, Any]
    images: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Source:
    article_number: str
    article_slug: str
    context_path: str
    context_sha256: str
    image: dict[str, Any]

    @property
    def sample_id(self) -> str:
        return f"{self.article_slug}-{self.image['image_id']}"

    @property
    def planning_run_id(self) -> str:
        return f"{PLANNING_BATCH_ID}-{self.sample_id}"

    @property
    def sample(self) -> NamespacedSample:
        return NamespacedSample(
            sample_id=self.sample_id,
            article_slug=self.article_slug,
            image_id=self.image["image_id"],
            filename=self.image["file"],
            source_sha256=self.image["sha256"],
            width=self.image["width"],
            height=self.image["height"],
            bound_source_path=self.image["source_path"],
            bound_context_path=self.context_path,
        )


@dataclass(frozen=True)
class TerminalRetryBinding:
    """Deterministic retry-v1 identity for one primary logical output."""

    source: Source
    model_id: str
    primary_provider_run_id: str
    retry_key: str
    retry_batch_id: str
    retry_provider_run_id: str

    @property
    def directory_rel(self) -> Path:
        return TERMINAL_RETRY_NAMESPACE_REL / self.retry_key

    @property
    def envelope_rel(self) -> Path:
        return self.directory_rel / "retry.json"

    @property
    def manifest_rel(self) -> Path:
        return self.directory_rel / "generation-manifest.json"

    @property
    def media_directory_rel(self) -> Path:
        return (
            self.directory_rel
            / "videos"
            / native.MODEL_DIRECTORIES[self.model_id]
        )

    @property
    def prompt_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.prompt.json"

    @property
    def run_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.run.json"

    @property
    def video_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.mp4"


@dataclass(frozen=True)
class AmbiguousSubmitRetryBinding:
    """Deterministic retry-v1 identity for one quarantined provider submit."""

    source: Source
    model_id: str
    primary_provider_run_id: str
    retry_key: str
    retry_batch_id: str
    retry_provider_run_id: str

    @property
    def directory_rel(self) -> Path:
        return AMBIGUOUS_SUBMIT_RETRY_NAMESPACE_REL / self.retry_key

    @property
    def envelope_rel(self) -> Path:
        return self.directory_rel / "retry.json"

    @property
    def manifest_rel(self) -> Path:
        return self.directory_rel / "generation-manifest.json"

    @property
    def media_directory_rel(self) -> Path:
        return (
            self.directory_rel
            / "videos"
            / native.MODEL_DIRECTORIES[self.model_id]
        )

    @property
    def prompt_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.prompt.json"

    @property
    def run_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.run.json"

    @property
    def video_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.mp4"


@dataclass(frozen=True)
class NormalizedInputRetryBinding:
    """Retry-v1 identity for one exact oversize primary logical output."""

    source: Source
    model_id: str
    primary_provider_run_id: str
    retry_key: str
    retry_batch_id: str
    retry_provider_run_id: str
    asset_key: str

    @property
    def directory_rel(self) -> Path:
        return NORMALIZED_INPUT_RETRY_NAMESPACE_REL / self.retry_key

    @property
    def envelope_rel(self) -> Path:
        return self.directory_rel / "retry.json"

    @property
    def manifest_rel(self) -> Path:
        return self.directory_rel / "generation-manifest.json"

    @property
    def asset_metadata_rel(self) -> Path:
        return NORMALIZED_INPUT_ASSET_NAMESPACE_REL / self.asset_key / "asset.json"

    @property
    def media_directory_rel(self) -> Path:
        return (
            self.directory_rel
            / "videos"
            / native.MODEL_DIRECTORIES[self.model_id]
        )

    @property
    def prompt_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.prompt.json"

    @property
    def run_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.run.json"

    @property
    def video_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.mp4"


@dataclass(frozen=True)
class NormalizedInputSupersedeBinding:
    """One deterministic operator-authorized successor to an active retry."""

    source: Source
    model_id: str
    normalized_retry_provider_run_id: str
    supersede_key: str
    supersede_batch_id: str
    supersede_provider_run_id: str

    @property
    def directory_rel(self) -> Path:
        normalized = normalized_input_retry_binding(self.source, self.model_id)
        return normalized.directory_rel / NORMALIZED_INPUT_SUPERSEDE_DIRECTORY_NAME

    @property
    def envelope_rel(self) -> Path:
        return self.directory_rel / "supersede.json"

    @property
    def manifest_rel(self) -> Path:
        return self.directory_rel / "generation-manifest.json"

    @property
    def media_directory_rel(self) -> Path:
        return self.directory_rel / "videos" / native.MODEL_DIRECTORIES[self.model_id]

    @property
    def prompt_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.prompt.json"

    @property
    def run_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.run.json"

    @property
    def video_rel(self) -> Path:
        return self.media_directory_rel / f"{self.source.image['image_id']}.mp4"


@dataclass(frozen=True)
class Discovery:
    articles: tuple[Article, ...]
    sources: tuple[Source, ...]
    unavailable_articles: tuple[dict[str, Any], ...]
    source_manifest_row_count: int
    extraction_report_sha256: str | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PipelineError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise PipelineError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in {path}: {exc}") from exc


def _safe_workspace_relative(value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PipelineError(f"{label} is missing")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise PipelineError(f"{label} escapes the workspace: {value}")
    return Path(*pure.parts)


def _copy_frozen_regular(source: Path, destination: Path, *, label: str) -> None:
    if not source.is_file() or source.is_symlink():
        raise PipelineError(f"{label} is missing or unsafe: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def frozen_provenance_summary(
    workspace: Path,
    run_id: str,
) -> dict[str, Any]:
    """Verify a historical job with its exact registered archived contract.

    The current executable lock may advance, but completed jobs must remain
    verifiable against the contract and execution receipt that authored them.
    A small temporary workspace contains only the exact frozen contract,
    digest-bound current support files (unchanged since 2.0.6), the requested
    job directory, and its two immutable inputs.  The frozen runner then
    performs the normal fail-closed provenance command without any bypass.
    """

    workspace = workspace.resolve()
    matching_batches = [
        batch_id
        for batch_id in FROZEN_BATCH_CONTRACT_VERSIONS
        if run_id.startswith(f"{batch_id}-")
    ]
    if len(matching_batches) != 1:
        raise PipelineError(
            f"Run does not belong to exactly one frozen contract batch: {run_id}"
        )
    contract_version = FROZEN_BATCH_CONTRACT_VERSIONS[matching_batches[0]]
    frozen = FROZEN_CONTRACTS[contract_version]
    contract_rel = frozen["path"]
    contract_digest = frozen["canonical_sha256"]
    archived_contract_path = workspace / contract_rel
    contract = read_json(archived_contract_path)
    if (
        not isinstance(contract, dict)
        or contract.get("agent_id") != AGENT_ID
        or contract.get("contract_version") != contract_version
    ):
        raise PipelineError(
            f"Archived Clipmaker Lite {contract_version} contract is invalid"
        )
    if (
        runner.sha256_bytes(runner.canonical_json_bytes(contract))
        != contract_digest
    ):
        raise PipelineError(
            f"Archived Clipmaker Lite {contract_version} contract digest changed"
        )

    run_rel = ARTIFACT_NAMESPACE / run_id
    run_directory = workspace / run_rel
    if not run_directory.is_dir() or run_directory.is_symlink():
        raise PipelineError(f"Historical Lite run directory is missing: {run_directory}")
    job_path = run_directory / "job.json"
    job = read_json(job_path)
    if not isinstance(job, dict) or job.get("job_id") != run_id:
        raise PipelineError(f"Historical Lite job identity differs: {run_id}")
    inputs = job.get("inputs")
    if not isinstance(inputs, dict):
        raise PipelineError(f"Historical Lite job inputs are missing: {run_id}")
    source_image = inputs.get("source_image")
    article_context = inputs.get("article_context")
    if not isinstance(source_image, dict) or not isinstance(article_context, dict):
        raise PipelineError(f"Historical Lite input bindings are invalid: {run_id}")
    input_relatives = (
        _safe_workspace_relative(source_image.get("path"), label="source image path"),
        _safe_workspace_relative(article_context.get("path"), label="article context path"),
    )

    runner_record = contract.get("runner")
    base_instruction = contract.get("base_instruction")
    models = contract.get("models")
    if (
        not isinstance(runner_record, dict)
        or not isinstance(base_instruction, dict)
        or not isinstance(models, dict)
    ):
        raise PipelineError("Archived Clipmaker Lite support bindings are invalid")
    support_relatives = [
        _safe_workspace_relative(runner_record.get("path"), label="runner path"),
        _safe_workspace_relative(
            base_instruction.get("path"),
            label="base instruction path",
        ),
    ]
    for model_id in MODEL_IDS:
        model = models.get(model_id)
        if not isinstance(model, dict):
            raise PipelineError(f"Archived model binding is missing: {model_id}")
        support_relatives.append(
            _safe_workspace_relative(
                model.get("spec_path"),
                label=f"{model_id} spec path",
            )
        )

    version_label = contract_version.replace(".", "")
    with tempfile.TemporaryDirectory(
        prefix=f"clipmaker-lite-{version_label}-provenance-"
    ) as directory:
        frozen_root = Path(directory)
        _copy_frozen_regular(
            archived_contract_path,
            frozen_root / CONTRACT_REL,
            label="archived contract",
        )
        for relative_path in support_relatives:
            _copy_frozen_regular(
                workspace / relative_path,
                frozen_root / relative_path,
                label="frozen contract support file",
            )
        for relative_path in input_relatives:
            _copy_frozen_regular(
                workspace / relative_path,
                frozen_root / relative_path,
                label="historical Lite input",
            )
        for source_path in sorted(run_directory.rglob("*")):
            if source_path.is_dir() and not source_path.is_symlink():
                continue
            if not source_path.is_file() or source_path.is_symlink():
                raise PipelineError(
                    f"Historical Lite artifact is unsafe: {source_path}"
                )
            relative_path = source_path.relative_to(workspace)
            _copy_frozen_regular(
                source_path,
                frozen_root / relative_path,
                label="historical Lite artifact",
            )
        completed = subprocess.run(
            [
                sys.executable,
                str(frozen_root / runner_record["path"]),
                "provenance",
                "--run-id",
                run_id,
            ],
            cwd=frozen_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        if completed.returncode:
            detail = transport.safe_error(completed.stderr or completed.stdout)
            raise PipelineError(f"Frozen Lite provenance failed for {run_id}: {detail}")
        try:
            summary = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise PipelineError(
                f"Frozen Lite provenance returned invalid JSON for {run_id}"
            ) from exc
    if (
        not isinstance(summary, dict)
        or summary.get("verified") is not True
        or summary.get("contract_version") != contract_version
    ):
        raise PipelineError(f"Frozen Lite provenance is not verified: {run_id}")
    return summary


def frozen_206_provenance_summary(
    workspace: Path,
    run_id: str,
) -> dict[str, Any]:
    """Compatibility wrapper restricted to the frozen 2.0.6 batches."""

    if not any(run_id.startswith(f"{batch_id}-") for batch_id in FROZEN_206_BATCH_IDS):
        raise PipelineError(f"Run does not belong to a frozen 2.0.6 batch: {run_id}")
    return frozen_provenance_summary(workspace, run_id)


def planning_provenance_verifier():
    return (
        frozen_provenance_summary
        if BATCH_ID in FROZEN_BATCH_CONTRACT_VERSIONS
        else None
    )


def planning_contract_version() -> str:
    return FROZEN_BATCH_CONTRACT_VERSIONS.get(
        BATCH_ID,
        REQUIRED_CONTRACT_VERSION,
    )


def planning_provenance_summary(
    workspace: Path,
    run_id: str,
) -> dict[str, Any]:
    if any(
        run_id.startswith(f"{batch_id}-")
        for batch_id in FROZEN_BATCH_CONTRACT_VERSIONS
    ):
        return frozen_provenance_summary(workspace, run_id)
    return runner.provenance_summary(workspace, run_id)


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise PipelineError(f"Path escapes workspace: {path}") from exc


def _safe_component(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise PipelineError(f"{field} must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise PipelineError(f"{field} must be one safe path component: {value!r}")
    if value != value.strip() or any(
        not (character.isalnum() or character in "._-") for character in value
    ):
        raise PipelineError(f"{field} contains unsafe characters: {value!r}")
    return value


def load_ticket_config(root: Path = ROOT) -> tuple[ArticleConfig, ...]:
    value = read_json(root / TICKET_CONFIG_REL)
    if not isinstance(value, list) or not value:
        raise PipelineError("Ticket article config must be a non-empty JSON array")
    articles: list[ArticleConfig] = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict):
            raise PipelineError(f"Ticket article {index} is not an object")
        number = item.get("number")
        label = item.get("label")
        url = item.get("url")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise PipelineError(f"Ticket article {index} has invalid number")
        if not isinstance(label, str) or not label.strip():
            raise PipelineError(f"Ticket article {index} has invalid label")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise PipelineError(f"Ticket article {index} has invalid URL")
        articles.append(
            ArticleConfig(
                number=number,
                label=label,
                folder=_safe_component(item.get("folder"), "article folder"),
                url=url,
            )
        )
    actual_numbers = tuple(article.number for article in articles)
    if actual_numbers != EXPECTED_ARTICLE_NUMBERS:
        raise PipelineError(
            "Ticket article numbers/order differ from registered batch: "
            f"expected={list(EXPECTED_ARTICLE_NUMBERS)}, "
            f"actual={list(actual_numbers)}"
        )
    folders = [article.folder for article in articles]
    if len(folders) != len(set(folders)):
        raise PipelineError("Ticket article folders must be unique")
    return tuple(articles)


def _normalized_report_record(
    config: ArticleConfig,
    report: dict[str, Any] | None,
    *,
    fallback_error: str | None = None,
) -> dict[str, Any]:
    status = report.get("status") if isinstance(report, dict) else "source-unavailable"
    image_count = report.get("image_count") if isinstance(report, dict) else None
    error = report.get("error") if isinstance(report, dict) else fallback_error
    return {
        "article_number": config.number_key,
        "article_slug": config.folder,
        "label": config.label,
        "url": config.url,
        "status": status,
        "image_count": image_count,
        "error": error,
    }


def _availability(
    configs: Sequence[ArticleConfig], root: Path
) -> tuple[set[str], tuple[dict[str, Any], ...], str | None]:
    report_path = root / EXTRACTION_REPORT_REL
    if not report_path.is_file():
        available: set[str] = set()
        unavailable: list[dict[str, Any]] = []
        for config in configs:
            context = root / SOURCE_CONTEXT_ROOT_REL / config.folder / "content.json"
            has_rows = False
            manifest = root / SOURCE_MANIFEST_REL
            if manifest.is_file():
                with manifest.open("r", encoding="utf-8", newline="") as stream:
                    has_rows = any(
                        row.get("article_number") == config.number_key
                        for row in csv.DictReader(stream)
                    )
            if context.is_file() and has_rows:
                available.add(config.folder)
            else:
                unavailable.append(
                    _normalized_report_record(
                        config,
                        None,
                        fallback_error="missing_extracted_context_or_manifest_rows",
                    )
                )
        return available, tuple(unavailable), None

    report = read_json(report_path)
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != 1
        or report.get("ticket") != TICKET
        or report.get("dataset_prefix") != DATASET_PREFIX
        or report.get("article_config") != TICKET_CONFIG_REL.as_posix()
    ):
        raise PipelineError("Unexpected PROMOPAGES-10060 extraction report identity")
    records = report.get("articles")
    if not isinstance(records, list) or len(records) != len(configs):
        raise PipelineError("Extraction report must describe every configured article")
    by_number: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise PipelineError("Extraction report article is not an object")
        number = record.get("article_number")
        if not isinstance(number, str) or number in by_number:
            raise PipelineError("Extraction report article numbers are invalid")
        by_number[number] = record

    available: set[str] = set()
    unavailable: list[dict[str, Any]] = []
    for config in configs:
        record = by_number.get(config.number_key)
        if (
            record is None
            or record.get("article_slug") != config.folder
            or record.get("url") != config.url
        ):
            raise PipelineError(
                f"Extraction report differs from config for article {config.number_key}"
            )
        status = record.get("status")
        if status == "ok":
            if not isinstance(record.get("image_count"), int) or record["image_count"] < 1:
                raise PipelineError(
                    f"Available article has invalid image_count: {config.folder}"
                )
            if record.get("error") is not None:
                raise PipelineError(f"Available article has an error: {config.folder}")
            available.add(config.folder)
        elif status == "source-unavailable":
            unavailable.append(_normalized_report_record(config, record))
        else:
            raise PipelineError(
                f"Unsupported extraction status for {config.folder}: {status!r}"
            )
    normalized_report_unavailable = report.get("unavailable_articles")
    if not isinstance(normalized_report_unavailable, list):
        raise PipelineError("Extraction report unavailable_articles must be a list")
    expected_unavailable_numbers = [item["article_number"] for item in unavailable]
    actual_unavailable_numbers = [
        item.get("article_number")
        for item in normalized_report_unavailable
        if isinstance(item, dict)
    ]
    if actual_unavailable_numbers != expected_unavailable_numbers:
        raise PipelineError("Extraction report unavailable_articles differs from articles")
    if report.get("available_article_count") != len(available):
        raise PipelineError("Extraction report available_article_count is inconsistent")
    return available, tuple(unavailable), sha256_file(report_path)


def _source_rows(
    configs: Sequence[ArticleConfig], available: set[str], root: Path
) -> dict[str, dict[str, str]]:
    path = root / SOURCE_MANIFEST_REL
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fieldnames = set(reader.fieldnames or ())
            required = {
                "article_number",
                "article_label",
                "article_url",
                "image_number",
                "image_role",
                "orig_url",
                "file_path",
                "actual_width",
                "actual_height",
                "sha256",
                "download_status",
                "duplicate_of",
            }
            if not required.issubset(fieldnames):
                raise PipelineError(
                    f"Source manifest is missing fields: {sorted(required - fieldnames)}"
                )
            rows = list(reader)
    except OSError as exc:
        raise PipelineError(f"Cannot read source manifest {path}: {exc}") from exc
    if not rows:
        raise PipelineError("Source manifest has no rows")

    config_by_number = {config.number_key: config for config in configs}
    indexed: dict[str, dict[str, str]] = {}
    row_slugs: set[str] = set()
    for row in rows:
        config = config_by_number.get(row.get("article_number", ""))
        if config is None:
            raise PipelineError(
                f"Source manifest has unknown article number: {row.get('article_number')!r}"
            )
        if config.folder not in available:
            raise PipelineError(f"Unavailable article has source rows: {config.folder}")
        file_path = row.get("file_path", "")
        parts = PurePosixPath(file_path).parts
        if (
            len(parts) != 4
            or parts[0] != DATASET_PREFIX
            or parts[1] != "articles"
            or parts[2] != config.folder
            or PurePosixPath(file_path).is_absolute()
            or ".." in parts
        ):
            raise PipelineError(f"Invalid namespaced manifest path: {file_path!r}")
        if (
            row.get("article_url") != config.url
            or row.get("download_status") != "ok"
            or not row.get("sha256")
            or not row.get("orig_url", "").startswith("https://")
        ):
            raise PipelineError(f"Invalid manifest source row: {file_path}")
        if file_path in indexed:
            raise PipelineError(f"Duplicate manifest file_path: {file_path}")
        indexed[file_path] = row
        row_slugs.add(config.folder)
    if row_slugs != available:
        raise PipelineError(
            "Source manifest article coverage differs from available articles: "
            f"manifest={sorted(row_slugs)}, available={sorted(available)}"
        )
    return indexed


def _image_record(
    *,
    root: Path,
    article: ArticleConfig,
    order: int,
    block: dict[str, Any],
    row: dict[str, str],
) -> dict[str, Any]:
    image_id = block.get("image_id")
    filename = block.get("file")
    expected_manifest_path = (
        f"{DATASET_PREFIX}/articles/{article.folder}/{filename}"
    )
    if (
        not isinstance(image_id, str)
        or not image_id
        or not isinstance(filename, str)
        or not filename
        or block.get("manifest_file_path") != expected_manifest_path
        or row.get("image_number") != image_id
    ):
        raise PipelineError(f"Invalid context/manifest image binding: {article.folder}")
    source_path = root / SOURCE_IMAGE_ROOT_REL / article.folder / str(filename)
    digest = sha256_file(source_path)
    if digest != row.get("sha256"):
        raise PipelineError(f"Source image digest mismatch: {source_path}")
    try:
        width = int(row["actual_width"])
        height = int(row["actual_height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"Invalid source dimensions: {source_path}") from exc
    if width < 1 or height < 1:
        raise PipelineError(f"Invalid source dimensions: {source_path}")
    duplicate_of = row.get("duplicate_of") or None
    if (block.get("duplicate_of") or None) != duplicate_of:
        raise PipelineError(f"duplicate_of mismatch: {expected_manifest_path}")
    return {
        "order": order,
        "image_id": image_id,
        "file": filename,
        "role": block.get("role"),
        "caption": block.get("caption") or "",
        "source_block_index": block.get("source_block_index"),
        "gallery_index": block.get("gallery_index"),
        "source_path": relative(source_path, root),
        "manifest_file_path": expected_manifest_path,
        "orig_url": row["orig_url"],
        "sha256": digest,
        "width": width,
        "height": height,
        "duplicate_of": duplicate_of,
    }


def discover(root: Path = ROOT) -> Discovery:
    """Discover every available image in deterministic article/block order."""

    configs = load_ticket_config(root)
    available, unavailable, report_sha256 = _availability(configs, root)
    rows = _source_rows(configs, available, root)
    seen_paths: set[str] = set()
    articles: list[Article] = []
    sources: list[Source] = []
    for config in configs:
        context_path = root / SOURCE_CONTEXT_ROOT_REL / config.folder / "content.json"
        if config.folder not in available:
            if context_path.exists():
                raise PipelineError(
                    f"Unavailable article unexpectedly has context: {config.folder}"
                )
            continue
        if not context_path.is_file() or context_path.is_symlink():
            raise PipelineError(f"Available article context is missing: {context_path}")
        value = read_json(context_path)
        blocks = value.get("blocks") if isinstance(value, dict) else None
        if not isinstance(blocks, list):
            raise PipelineError(f"Article blocks are missing: {context_path}")
        image_blocks = [
            block
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "image"
        ]
        if not image_blocks:
            raise PipelineError(f"Article has no image blocks: {context_path}")
        records: list[dict[str, Any]] = []
        for order, block in enumerate(image_blocks, 1):
            manifest_path = block.get("manifest_file_path")
            row = rows.get(manifest_path) if isinstance(manifest_path, str) else None
            if row is None:
                raise PipelineError(
                    f"Context image is absent from source manifest: {manifest_path!r}"
                )
            if manifest_path in seen_paths:
                raise PipelineError(f"Manifest image appears twice: {manifest_path}")
            seen_paths.add(manifest_path)
            records.append(
                _image_record(
                    root=root,
                    article=config,
                    order=order,
                    block=block,
                    row=row,
                )
            )
        if records[0]["role"] != "cover":
            raise PipelineError(f"First image block is not the cover: {config.folder}")
        cover = records[0]
        context_relative = relative(context_path, root)
        context_digest = sha256_file(context_path)
        article = Article(
            number=config.number_key,
            slug=config.folder,
            label=config.label,
            url=config.url,
            title=str(value.get("title") or ""),
            lead=str(value.get("lead") or ""),
            context_path=context_relative,
            context_sha256=context_digest,
            cover_image=cover,
            images=tuple(records),
        )
        articles.append(article)
        sources.extend(
            Source(
                article_number=config.number_key,
                article_slug=config.folder,
                context_path=context_relative,
                context_sha256=context_digest,
                image=image,
            )
            for image in records
        )

    if seen_paths != set(rows):
        raise PipelineError(
            "Article contexts do not exactly cover the source manifest: "
            f"missing={sorted(set(rows) - seen_paths)}, "
            f"extra={sorted(seen_paths - set(rows))}"
        )
    if not articles or not sources:
        raise PipelineError("No complete article/image matrix was discovered")
    if [article.number for article in articles] != sorted(
        (article.number for article in articles), key=int
    ):
        raise PipelineError("Available articles are not in ticket-config order")
    if len({source.sample_id for source in sources}) != len(sources):
        raise PipelineError("Source sample IDs are not unique")
    if len(sources) != len(rows):
        raise PipelineError(
            "Discovered source count differs from the source manifest: "
            f"sources={len(sources)}, manifest={len(rows)}"
        )
    expected_source_order = [
        (article.slug, image["image_id"])
        for article in articles
        for image in article.images
    ]
    actual_source_order = [
        (source.article_slug, source.image["image_id"])
        for source in sources
    ]
    if actual_source_order != expected_source_order:
        raise PipelineError("Sources are not in article/block order")
    context_slugs = {
        path.parent.name
        for path in (root / SOURCE_CONTEXT_ROOT_REL).glob("*/content.json")
    }
    if context_slugs != available:
        raise PipelineError(
            "Context directory coverage differs from extraction availability: "
            f"contexts={sorted(context_slugs)}, available={sorted(available)}"
        )
    return Discovery(
        articles=tuple(articles),
        sources=tuple(sources),
        unavailable_articles=unavailable,
        source_manifest_row_count=len(rows),
        extraction_report_sha256=report_sha256,
    )


def _positive_budget(value: str | Decimal) -> Decimal:
    try:
        parsed = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise PipelineError(f"Invalid USD budget cap: {value!r}") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise PipelineError("USD budget cap must be positive")
    return parsed


def parse_budget(value: str | Decimal) -> Decimal:
    parsed = _positive_budget(value)
    if HARD_BUDGET_CAP_USD is not None and parsed > HARD_BUDGET_CAP_USD:
        raise PipelineError(
            f"USD budget cap ${parsed:.2f} exceeds the hard "
            f"${HARD_BUDGET_CAP_USD:.2f} cap"
        )
    return parsed


def budget_arg(value: str) -> Decimal:
    try:
        # argparse runs before main activates --batch.  Validate only syntax
        # and positivity here; parse_budget applies the selected batch policy.
        return _positive_budget(value)
    except PipelineError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _contract_snapshot(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_REL
    contract = read_json(path)
    if (
        not isinstance(contract, dict)
        or contract.get("agent_id") != AGENT_ID
        or contract.get("contract_version") != REQUIRED_CONTRACT_VERSION
        or list(contract.get("models", {})) != list(MODEL_IDS)
    ):
        raise PipelineError("Unexpected current Clipmaker Lite contract")
    binding = contract.get("input_binding")
    if not isinstance(binding, dict) or binding != {
        "image_root": "PROMOPAGES-9857",
        "context_root": "PROMOPAGES-9884",
        "context_filename": "content.json",
    }:
        raise PipelineError("Clipmaker Lite input binding changed")
    return {
        "path": CONTRACT_REL.as_posix(),
        "sha256": sha256_file(path),
        "contract_version": contract["contract_version"],
        "runner_version": contract.get("runner", {}).get("runner_version"),
    }


def _inventory_contract_snapshot(root: Path) -> dict[str, Any]:
    """Keep an immutable batch inventory bound to its archived contract.

    Advancing the executable Lite contract must not make a completed frozen
    batch inventory unverifiable.  The inventory retains its original logical
    path while the digest and metadata are read from the exact registered
    archive used by historical provenance verification.
    """

    contract_version = FROZEN_BATCH_CONTRACT_VERSIONS.get(BATCH_ID)
    if contract_version is None:
        return _contract_snapshot(root)
    frozen = FROZEN_CONTRACTS[contract_version]
    archived_path = root / frozen["path"]
    contract = read_json(archived_path)
    if (
        not isinstance(contract, dict)
        or contract.get("agent_id") != AGENT_ID
        or contract.get("contract_version") != contract_version
        or list(contract.get("models", {})) != list(MODEL_IDS)
        or runner.sha256_bytes(runner.canonical_json_bytes(contract))
        != frozen["canonical_sha256"]
    ):
        raise PipelineError(
            f"Archived Clipmaker Lite {contract_version} inventory contract changed"
        )
    return {
        "path": CONTRACT_REL.as_posix(),
        "sha256": sha256_file(archived_path),
        "contract_version": contract_version,
        "runner_version": contract.get("runner", {}).get("runner_version"),
    }


def _route_snapshot(root: Path) -> dict[str, Any]:
    path = root / ROUTES_REL
    routes = read_json(path)
    policy = routes.get("policy") if isinstance(routes, dict) else None
    models = routes.get("models") if isinstance(routes, dict) else None
    if (
        not isinstance(policy, dict)
        or policy.get("resolution") != "exact-model-id"
        or policy.get("automatic_fallback") is not False
        or policy.get("normal_run_discovery") is not False
        or not isinstance(models, dict)
        or list(models) != list(MODEL_IDS)
    ):
        raise PipelineError("Generation route policy or model order changed")
    snapshot_models: dict[str, Any] = {}
    for model_id in MODEL_IDS:
        route = models[model_id]
        expected_adapter, expected_transport = ROUTE_IDENTITIES[model_id]
        if (
            not isinstance(route, dict)
            or route.get("adapter") != expected_adapter
            or route.get("transport") != expected_transport
            or route.get("capacity") != ROUTE_CAPACITIES[model_id]
            or transport.route_for_model(model_id) != route
        ):
            raise PipelineError(f"Exact generation route changed: {model_id}")
        snapshot_models[model_id] = {
            "adapter": expected_adapter,
            "transport": expected_transport,
            "capacity": ROUTE_CAPACITIES[model_id],
        }
    return {
        "path": ROUTES_REL.as_posix(),
        "sha256": sha256_file(path),
        "policy": {
            "resolution": "exact-model-id",
            "automatic_fallback": False,
            "normal_run_discovery": False,
        },
        "models": snapshot_models,
    }


def cost_metadata(budget: str | Decimal, job_count: int) -> dict[str, Any]:
    parsed = parse_budget(budget)
    if job_count < 1:
        raise PipelineError("Budget admission requires at least one provider job")
    if job_count % len(MODEL_IDS):
        raise PipelineError("Budget admission requires a complete three-model matrix")
    image_count = job_count // len(MODEL_IDS)
    estimated_per_image = sum(ACCOUNTING_COST_PER_OUTPUT_USD.values())
    maximum_estimated_cost = (
        estimated_per_image * image_count
    ).quantize(Decimal("0.01"))
    if maximum_estimated_cost > parsed:
        raise PipelineError(
            f"Estimated full-matrix cost ${maximum_estimated_cost:.2f} exceeds "
            f"the operator ${parsed:.2f} cap"
        )
    return {
        "currency": "USD",
        "operator_budget_cap_usd": float(parsed),
        "hard_budget_cap_usd": float(
            HARD_BUDGET_CAP_USD
            if HARD_BUDGET_CAP_USD is not None
            else parsed
        ),
        "accounting_cost_per_output_usd": {
            model_id: float(ACCOUNTING_COST_PER_OUTPUT_USD[model_id])
            for model_id in MODEL_IDS
        },
        "accounting_cost_per_image_usd": float(estimated_per_image),
        "maximum_estimated_cost_usd": float(maximum_estimated_cost),
        "estimated_headroom_usd": float(parsed - maximum_estimated_cost),
        "planned_paid_submissions": job_count,
        "maximum_paid_submissions": job_count,
        "maximum_paid_submissions_per_job": 1,
        "automatic_paid_retries": False,
        "actual_billing_available": False,
        "enforcement": (
            "admit only complete articles in ticket-config order within the "
            "accounting envelope; each admitted immutable job may submit once; "
            "resume may poll/download an existing provider identity but never "
            "automatically resubmit a paid job"
        ),
        "pricing_basis": (
            "local frozen accounting evidence only: reserve $0.35 for every "
            "output using the existing PROMOPAGES-9930 20x2 estimate; this is "
            "conservative for Wan 2.2 versus its observed Eliza/Segmind "
            "X-Response-Cost of $0.18; no live price or model discovery"
        ),
    }


def terminal_retry_budget_metadata(
    inventory: dict[str, Any],
    retry_reservations: int,
) -> dict[str, Any]:
    """Compatibility wrapper for primary + terminal provider retry-v1."""

    return aggregate_retry_budget_metadata(
        inventory,
        terminal_retry_reservations=retry_reservations,
        ambiguous_submit_retry_reservations=0,
        normalized_input_retry_reservations=0,
    )


def aggregate_retry_budget_metadata(
    inventory: dict[str, Any],
    *,
    terminal_retry_reservations: int,
    ambiguous_submit_retry_reservations: int,
    normalized_input_retry_reservations: int = 0,
    normalized_input_supersede_reservations: int = 0,
) -> dict[str, Any]:
    """Return conservative accounting for every immutable retry namespace.

    A reservation is counted even if its transport later fails before submit.
    This deliberately favors a fail-closed budget ledger over trying to infer
    provider billing from partial receipts.
    """

    reservation_counts = {
        "terminal": terminal_retry_reservations,
        "ambiguous submit": ambiguous_submit_retry_reservations,
        "normalized input": normalized_input_retry_reservations,
        "normalized input supersede": normalized_input_supersede_reservations,
    }
    for label, count in reservation_counts.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise PipelineError(
                f"{label.capitalize()} retry reservation count must be a "
                "non-negative integer"
            )
    primary = inventory.get("cost") if isinstance(inventory, dict) else None
    if not isinstance(primary, dict):
        raise PipelineError("Frozen inventory cost metadata is missing")
    try:
        operator_cap = Decimal(str(primary["operator_budget_cap_usd"]))
        primary_maximum = Decimal(str(primary["maximum_estimated_cost_usd"]))
        primary_submissions = int(primary["maximum_paid_submissions"])
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise PipelineError("Frozen inventory cost metadata is invalid") from exc
    terminal_retry_maximum = (
        TERMINAL_RETRY_ACCOUNTING_COST_USD * terminal_retry_reservations
    )
    ambiguous_retry_maximum = (
        AMBIGUOUS_SUBMIT_RETRY_ACCOUNTING_COST_USD
        * ambiguous_submit_retry_reservations
    )
    normalized_retry_maximum = (
        NORMALIZED_INPUT_RETRY_ACCOUNTING_COST_USD
        * normalized_input_retry_reservations
    )
    normalized_supersede_maximum = (
        NORMALIZED_INPUT_SUPERSEDE_ACCOUNTING_COST_USD
        * normalized_input_supersede_reservations
    )
    retry_maximum = (
        terminal_retry_maximum
        + ambiguous_retry_maximum
        + normalized_retry_maximum
        + normalized_supersede_maximum
    ).quantize(Decimal("0.01"))
    aggregate_maximum = (primary_maximum + retry_maximum).quantize(
        Decimal("0.01")
    )
    if aggregate_maximum > operator_cap or (
        HARD_BUDGET_CAP_USD is not None
        and aggregate_maximum > HARD_BUDGET_CAP_USD
    ):
        raise PipelineError(
            f"Retry reservation would raise the aggregate accounting maximum "
            f"to ${aggregate_maximum:.2f}, above the ${operator_cap:.2f} cap"
        )
    return {
        **primary,
        "maximum_estimated_cost_usd": float(aggregate_maximum),
        "estimated_headroom_usd": float(operator_cap - aggregate_maximum),
        "maximum_paid_submissions": primary_submissions
        + terminal_retry_reservations
        + ambiguous_submit_retry_reservations
        + normalized_input_retry_reservations
        + normalized_input_supersede_reservations,
        # The remaining superseding reservation fields are added below only
        # when used, preserving the byte-shape of the frozen legacy batch.
        "terminal_retry_version": TERMINAL_RETRY_VERSION,
        "terminal_retry_accounting_cost_usd": float(
            TERMINAL_RETRY_ACCOUNTING_COST_USD
        ),
        "terminal_retry_reservations": terminal_retry_reservations,
        "ambiguous_submit_retry_version": AMBIGUOUS_SUBMIT_RETRY_VERSION,
        "ambiguous_submit_retry_accounting_cost_usd": float(
            AMBIGUOUS_SUBMIT_RETRY_ACCOUNTING_COST_USD
        ),
        "ambiguous_submit_retry_reservations": (
            ambiguous_submit_retry_reservations
        ),
        "normalized_input_retry_version": NORMALIZED_INPUT_RETRY_VERSION,
        "normalized_input_retry_accounting_cost_usd": float(
            NORMALIZED_INPUT_RETRY_ACCOUNTING_COST_USD
        ),
        "normalized_input_retry_reservations": (
            normalized_input_retry_reservations
        ),
        "total_retry_reservations": (
            terminal_retry_reservations
            + ambiguous_submit_retry_reservations
            + normalized_input_retry_reservations
            + normalized_input_supersede_reservations
        ),
        "maximum_new_paid_submissions_per_failed_output": 1,
        "maximum_new_paid_submissions_per_ambiguous_output": 1,
        "maximum_new_paid_submissions_per_normalized_input_output": 1,
        "automatic_paid_retries": False,
        "enforcement": (
            f"{primary.get('enforcement', '')}; provider-confirmed terminal "
            "failures may receive at most one separately namespaced, explicit "
            "retry-v1 submit; a quarantined exact-route provider submit with "
            "unknown outcome may receive at most one separately namespaced, "
            "explicit ambiguous-submit retry-v1; each exact oversize Wan "
            "primary may receive one separately namespaced normalized-input "
            "retry-v1 whose only request change is the frozen image URL; "
            "one explicitly authorized active normalized-input job may receive "
            "one separately namespaced byte-identical superseding attempt; "
            "every immutable reservation "
            "is included in the aggregate accounting maximum"
        ).strip("; "),
        **(
            {
                "normalized_input_supersede_version": (
                    NORMALIZED_INPUT_SUPERSEDE_VERSION
                ),
                "normalized_input_supersede_accounting_cost_usd": float(
                    NORMALIZED_INPUT_SUPERSEDE_ACCOUNTING_COST_USD
                ),
                "normalized_input_supersede_reservations": (
                    normalized_input_supersede_reservations
                ),
                "maximum_new_paid_submissions_per_superseded_output": 1,
            }
            if normalized_input_supersede_reservations
            else {}
        ),
    }


def primary_provider_run_id(source: Source, model_id: str) -> str:
    if model_id not in MODEL_IDS:
        raise PipelineError(f"Unsupported retry model: {model_id}")
    return (
        f"{BATCH_ID}-{source.sample_id}-{native.MODEL_SUFFIXES[model_id]}"
    )


def terminal_retry_binding(source: Source, model_id: str) -> TerminalRetryBinding:
    primary_run_id = primary_provider_run_id(source, model_id)
    retry_key = hashlib.sha256(primary_run_id.encode("utf-8")).hexdigest()[:20]
    retry_batch_id = f"{BATCH_ID}-terminal-retry-v1-{retry_key}"
    retry_provider_run_id = (
        f"{retry_batch_id}-{source.sample_id}-{native.MODEL_SUFFIXES[model_id]}"
    )
    return TerminalRetryBinding(
        source=source,
        model_id=model_id,
        primary_provider_run_id=primary_run_id,
        retry_key=retry_key,
        retry_batch_id=retry_batch_id,
        retry_provider_run_id=retry_provider_run_id,
    )


def ambiguous_submit_retry_binding(
    source: Source,
    model_id: str,
) -> AmbiguousSubmitRetryBinding:
    """Bind one logical output to its only exact-route quarantine retry."""

    route_identity = ROUTE_IDENTITIES.get(model_id)
    if model_id not in MODEL_IDS or route_identity is None:
        raise PipelineError(f"Ambiguous-submit retry model is unsupported: {model_id}")
    if route_identity[0] not in {"eliza-segmind", "eliza-openrouter"}:
        raise PipelineError(
            f"Ambiguous-submit retry adapter is unsupported: {route_identity[0]}"
        )
    primary_run_id = primary_provider_run_id(source, model_id)
    retry_key = hashlib.sha256(
        f"ambiguous-submit-v1:{primary_run_id}".encode("utf-8")
    ).hexdigest()[:20]
    retry_batch_id = f"{BATCH_ID}-ambiguous-submit-retry-v1-{retry_key}"
    retry_provider_run_id = (
        f"{retry_batch_id}-{source.sample_id}-{native.MODEL_SUFFIXES[model_id]}"
    )
    return AmbiguousSubmitRetryBinding(
        source=source,
        model_id=model_id,
        primary_provider_run_id=primary_run_id,
        retry_key=retry_key,
        retry_batch_id=retry_batch_id,
        retry_provider_run_id=retry_provider_run_id,
    )


def _normalized_input_target_for_key(
    article_slug: Any,
    image_id: Any,
    model_id: Any,
) -> NormalizedInputRetryTarget | None:
    for target in NORMALIZED_INPUT_RETRY_ALLOWLIST:
        if (
            article_slug == target.article_slug
            and image_id == target.image_id
            and model_id in target.model_ids
        ):
            return target
    return None


def _normalized_input_target(
    source: Source,
    model_id: str,
) -> NormalizedInputRetryTarget | None:
    target = _normalized_input_target_for_key(
        source.article_slug,
        source.image.get("image_id"),
        model_id,
    )
    if target is None or source.image.get("sha256") != target.source_sha256:
        return None
    return target


def _normalized_input_target_for_source(source: Source) -> NormalizedInputRetryTarget:
    targets = {
        target
        for model_id in MODEL_IDS
        if (target := _normalized_input_target(source, model_id)) is not None
    }
    if len(targets) != 1:
        raise PipelineError(
            "Normalized-input source must resolve to one exact batch target: "
            f"{source.article_slug}/{source.image.get('image_id')}"
        )
    return next(iter(targets))


def _require_normalized_input_target(source: Source, model_id: str) -> None:
    if _normalized_input_target(source, model_id) is None:
        raise PipelineError(
            "Normalized-input retry is restricted to exact targets in the "
            f"selected batch allowlist: {source.article_slug}/"
            f"{source.image.get('image_id')}/{model_id}"
        )


def normalized_input_retry_binding(
    source: Source,
    model_id: str,
) -> NormalizedInputRetryBinding:
    """Bind each exact failed primary to one model-isolated retry identity."""

    _require_normalized_input_target(source, model_id)
    primary_run_id = primary_provider_run_id(source, model_id)
    retry_key = hashlib.sha256(
        f"normalized-input-v1:{primary_run_id}".encode("utf-8")
    ).hexdigest()[:20]
    asset_key = hashlib.sha256(
        (
            "scale-1200-v1:"
            f"{source.sample_id}:{source.image['sha256']}"
        ).encode("utf-8")
    ).hexdigest()[:20]
    retry_batch_id = f"{BATCH_ID}-normalized-input-retry-v1-{retry_key}"
    retry_provider_run_id = (
        f"{retry_batch_id}-{source.sample_id}-{native.MODEL_SUFFIXES[model_id]}"
    )
    return NormalizedInputRetryBinding(
        source=source,
        model_id=model_id,
        primary_provider_run_id=primary_run_id,
        retry_key=retry_key,
        retry_batch_id=retry_batch_id,
        retry_provider_run_id=retry_provider_run_id,
        asset_key=asset_key,
    )


def _require_normalized_input_supersede_target(
    source: Source,
    model_id: str,
) -> NormalizedInputRetryBinding:
    """Authorize only the exact active job named by the operator."""

    target = NORMALIZED_INPUT_SUPERSEDE_TARGET
    if (
        BATCH_ID != target["batch_id"]
        or source.article_slug != target["article_slug"]
        or source.image.get("image_id") != target["image_id"]
        or model_id != target["model_id"]
    ):
        raise PipelineError(
            "Normalized-input supersede is authorized only for the exact "
            "ticket-specific active Wan 2.7 job"
        )
    normalized = normalized_input_retry_binding(source, model_id)
    if (
        normalized.retry_provider_run_id
        != target["normalized_retry_provider_run_id"]
    ):
        raise PipelineError("Normalized-input supersede run binding changed")
    return normalized


def normalized_input_supersede_binding(
    source: Source,
    model_id: str,
) -> NormalizedInputSupersedeBinding:
    """Bind the one permitted successor to the exact active normalized retry."""

    normalized = _require_normalized_input_supersede_target(source, model_id)
    supersede_key = hashlib.sha256(
        (
            "normalized-input-supersede-v1:"
            f"{normalized.retry_provider_run_id}"
        ).encode("utf-8")
    ).hexdigest()[:20]
    supersede_batch_id = (
        f"{BATCH_ID}-normalized-input-supersede-v1-{supersede_key}"
    )
    supersede_provider_run_id = (
        f"{supersede_batch_id}-{source.sample_id}-"
        f"{native.MODEL_SUFFIXES[model_id]}"
    )
    return NormalizedInputSupersedeBinding(
        source=source,
        model_id=model_id,
        normalized_retry_provider_run_id=normalized.retry_provider_run_id,
        supersede_key=supersede_key,
        supersede_batch_id=supersede_batch_id,
        supersede_provider_run_id=supersede_provider_run_id,
    )


def resolve_normalized_input_supersede_target(
    sources: Iterable[Source],
    normalized_retry_provider_run_id: str,
) -> tuple[Source, str]:
    """Resolve only the registered normalized retry identity, never a primary."""

    target = NORMALIZED_INPUT_SUPERSEDE_TARGET
    if (
        BATCH_ID != target["batch_id"]
        or normalized_retry_provider_run_id
        != target["normalized_retry_provider_run_id"]
    ):
        raise PipelineError(
            "Unknown or unauthorized normalized-input retry provider run ID "
            "for supersede"
        )
    matches = [
        source
        for source in sources
        if source.article_slug == target["article_slug"]
        and source.image.get("image_id") == target["image_id"]
    ]
    if len(matches) != 1:
        raise PipelineError("Normalized-input supersede source binding is missing")
    source = matches[0]
    model_id = str(target["model_id"])
    normalized = _require_normalized_input_supersede_target(source, model_id)
    if normalized.retry_provider_run_id != normalized_retry_provider_run_id:
        raise PipelineError("Normalized-input supersede provider identity differs")
    return source, model_id


def primary_artifact_paths(
    source: Source,
    model_id: str,
    root: Path,
) -> dict[str, Path]:
    base = (
        root
        / BATCH_ROOT_REL
        / "videos"
        / source.article_slug
        / native.MODEL_DIRECTORIES[model_id]
    )
    stem = source.image["image_id"]
    return {
        "directory": base,
        "prompt": base / f"{stem}.prompt.json",
        "run": base / f"{stem}.run.json",
        "video": base / f"{stem}.mp4",
    }


def _normalized_input_page_variant_url(source: Source, root: Path) -> str:
    """Resolve the exact allowlisted normalized URL without changing inventory."""

    target = _normalized_input_target_for_source(source)
    if target.replacement is not None:
        return target.replacement.url
    manifest_path = root / SOURCE_MANIFEST_REL
    try:
        with manifest_path.open("r", encoding="utf-8", newline="") as stream:
            matches = [
                row
                for row in csv.DictReader(stream)
                if row.get("file_path") == source.image["manifest_file_path"]
            ]
    except OSError as exc:
        raise PipelineError(
            f"Cannot read normalized-input source manifest {manifest_path}: {exc}"
        ) from exc
    if len(matches) != 1:
        raise PipelineError(
            "Normalized-input source must have one exact manifest row: "
            f"{source.image['manifest_file_path']}"
        )
    row = matches[0]
    url = row.get("page_variant_url")
    parsed = urlparse(url) if isinstance(url, str) else None
    if (
        row.get("article_number") != source.article_number
        or row.get("image_number") != source.image["image_id"]
        or row.get("orig_url") != source.image["orig_url"]
        or row.get("sha256") != source.image["sha256"]
        or not isinstance(parsed, type(urlparse("https://example.test/")))
        or parsed.scheme != "https"
        or parsed.hostname != "avatars.mds.yandex.net"
        or not parsed.path.endswith("/scale_1200")
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise PipelineError(
            "Normalized-input page_variant_url is not the exact manifest-bound "
            "/scale_1200 MDS asset"
        )
    return url


def _encoded_image_dimensions(payload: bytes) -> tuple[str, int, int]:
    """Read dimensions from a normalized PNG/JPEG payload without dependencies."""

    if payload.startswith(b"\x89PNG\r\n\x1a\n") and len(payload) >= 24:
        width = int.from_bytes(payload[16:20], "big")
        height = int.from_bytes(payload[20:24], "big")
        if width > 0 and height > 0:
            return "PNG", width, height
    if payload.startswith(b"\xff\xd8"):
        offset = 2
        sof_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        while offset + 4 <= len(payload):
            if payload[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(payload) and payload[offset] == 0xFF:
                offset += 1
            if offset >= len(payload):
                break
            marker = payload[offset]
            offset += 1
            if marker in {0x01, 0xD8, 0xD9}:
                continue
            if offset + 2 > len(payload):
                break
            segment_length = int.from_bytes(payload[offset : offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(payload):
                break
            if marker in sof_markers and segment_length >= 7:
                height = int.from_bytes(payload[offset + 3 : offset + 5], "big")
                width = int.from_bytes(payload[offset + 5 : offset + 7], "big")
                if width > 0 and height > 0:
                    return "JPEG", width, height
            offset += segment_length
    raise PipelineError("Normalized /scale_1200 payload is not a supported PNG/JPEG")


def preflight_normalized_input_asset(
    url: str,
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    """Fetch and measure the public MDS variant; never contacts a video provider."""

    parsed = urlparse(url)
    is_mds_scale = (
        parsed.scheme == "https"
        and parsed.hostname == "avatars.mds.yandex.net"
        and parsed.path.endswith("/scale_1200")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )
    raw_prefix = "/UnidentifiedRaccoon/alice-live-images-test/"
    raw_tail = parsed.path.removeprefix(raw_prefix)
    raw_commit, raw_separator, raw_repository_path = raw_tail.partition("/")
    is_commit_pinned_raw = (
        parsed.scheme == "https"
        and parsed.hostname == "raw.githubusercontent.com"
        and parsed.path.startswith(raw_prefix)
        and bool(raw_separator)
        and len(raw_commit) == 40
        and all(character in "0123456789abcdef" for character in raw_commit)
        and bool(raw_repository_path)
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )
    if not is_mds_scale and not is_commit_pinned_raw:
        raise PipelineError("Refusing normalized-input preflight for an unsafe URL")
    request = Request(
        url,
        headers={"Accept": "image/*", "User-Agent": "clipmaker-lite/1"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(response.getcode())
            final_url = response.geturl()
            payload = response.read(NORMALIZED_INPUT_MAX_BYTES + 1)
    except OSError as exc:
        raise PipelineError(
            f"Normalized-input MDS preflight failed: {transport.safe_error(exc)}"
        ) from exc
    if status != 200 or final_url != url:
        raise PipelineError(
            "Normalized-input MDS preflight did not return the exact URL with HTTP 200"
        )
    if not payload or len(payload) > NORMALIZED_INPUT_MAX_BYTES:
        raise PipelineError(
            "Normalized /scale_1200 asset is empty or still exceeds 20 MiB"
        )
    image_format, width, height = _encoded_image_dimensions(payload)
    if width < NORMALIZED_INPUT_MIN_DIMENSION or height < NORMALIZED_INPUT_MIN_DIMENSION:
        raise PipelineError(
            "Normalized /scale_1200 asset still has a dimension below 240 px"
        )
    return {
        "http_status": 200,
        "url": url,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "width": width,
        "height": height,
        "format": image_format,
    }


def _normalized_input_constraint(source: Source, root: Path) -> str:
    """Return the one provider constraint proven by the frozen local source."""

    source_path = root / source.image["source_path"]
    if not source_path.is_file() or source_path.is_symlink():
        raise PipelineError(f"Normalized-input original source is missing: {source_path}")
    payload = source_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != source.image["sha256"]:
        raise PipelineError(
            f"Normalized-input original source hash differs: {source_path}"
        )
    _image_format, actual_width, actual_height = _encoded_image_dimensions(payload)
    width = source.image.get("width")
    height = source.image.get("height")
    if actual_width != width or actual_height != height:
        raise PipelineError(
            f"Normalized-input original dimensions differ: {source_path}"
        )
    byte_size = len(payload)
    constraint: str | None = None
    if byte_size > NORMALIZED_INPUT_MAX_BYTES:
        constraint = "maximum-bytes"
    elif (
        isinstance(width, int)
        and isinstance(height, int)
        and (
            width < NORMALIZED_INPUT_MIN_DIMENSION
            or height < NORMALIZED_INPUT_MIN_DIMENSION
        )
    ):
        constraint = "minimum-dimension"
    if constraint is None:
        raise PipelineError(
            "Normalized-input target no longer violates the known provider input "
            "constraints"
        )
    target = _normalized_input_target_for_source(source)
    if target.failure_kind != constraint:
        raise PipelineError(
            "Normalized-input target failure kind differs from the frozen source"
        )
    return constraint


def _normalized_input_original_source(source: Source, root: Path) -> dict[str, Any]:
    source_path = root / source.image["source_path"]
    _normalized_input_constraint(source, root)
    byte_size = source_path.stat().st_size
    return {
        "url": source.image["orig_url"],
        "path": source.image["source_path"],
        "sha256": source.image["sha256"],
        "bytes": byte_size,
        "width": source.image["width"],
        "height": source.image["height"],
    }


def _commit_pinned_replacement_record(
    binding: NormalizedInputRetryBinding,
    preflight: dict[str, Any],
    *,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    target = _normalized_input_target(binding.source, binding.model_id)
    replacement = target.replacement if target is not None else None
    if replacement is None:
        raise PipelineError("Normalized-input target has no commit-pinned replacement")
    expected_preflight = {
        "http_status": 200,
        "url": replacement.url,
        "sha256": replacement.sha256,
        "bytes": replacement.byte_size,
        "width": replacement.width,
        "height": replacement.height,
        "format": replacement.image_format,
    }
    if preflight != expected_preflight:
        raise PipelineError(
            "Commit-pinned normalized asset differs from its exact allowlist metadata"
        )
    repository_path = Path(replacement.repository_path)
    if repository_path.parent != binding.asset_metadata_rel.parent:
        raise PipelineError(
            "Commit-pinned normalized asset is outside its deterministic asset key"
        )
    local_path = root / repository_path
    if not local_path.is_file() or local_path.is_symlink():
        raise PipelineError(
            f"Commit-pinned normalized asset is missing locally: {local_path}"
        )
    local_payload = local_path.read_bytes()
    local_format, local_width, local_height = _encoded_image_dimensions(local_payload)
    if (
        hashlib.sha256(local_payload).hexdigest() != replacement.sha256
        or len(local_payload) != replacement.byte_size
        or local_width != replacement.width
        or local_height != replacement.height
        or local_format != replacement.image_format
    ):
        raise PipelineError(
            f"Commit-pinned normalized local asset differs: {local_path}"
        )
    parsed = urlparse(replacement.url)
    raw_tail = parsed.path.removeprefix(
        "/UnidentifiedRaccoon/alice-live-images-test/"
    )
    commit_sha, separator, raw_repository_path = raw_tail.partition("/")
    if not separator or raw_repository_path != replacement.repository_path:
        raise PipelineError("Commit-pinned normalized URL path differs")
    normalized = {
        **expected_preflight,
        "delivery": "repository-raw",
        "repository_path": replacement.repository_path,
        "source_commit_sha": commit_sha,
    }
    transform = {
        "operation": "uniform-scale",
        "target_height": replacement.height,
        "resampler": "lanczos",
        "crop": False,
        "local_reencode": True,
    }
    return normalized, transform


def _normalized_input_asset_document(
    binding: NormalizedInputRetryBinding,
    preflight: dict[str, Any],
    *,
    root: Path,
) -> dict[str, Any]:
    target = _normalized_input_target(binding.source, binding.model_id)
    if target is None:
        raise PipelineError("Normalized-input asset target is not allowlisted")
    normalized = dict(preflight)
    transform: dict[str, Any] | None = None
    strategy = "frozen-page-variant"
    if target.replacement is not None:
        strategy = target.replacement.strategy
        normalized, transform = _commit_pinned_replacement_record(
            binding,
            preflight,
            root=root,
        )
    document = {
        "schema_version": 1,
        "manifest_role": NORMALIZED_ASSET_MANIFEST_ROLE,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "strategy": strategy,
        "source_key": {
            "article_slug": binding.source.article_slug,
            "image_id": binding.source.image["image_id"],
        },
        "original": _normalized_input_original_source(binding.source, root),
        "normalized": normalized,
        "maximum_provider_input_bytes": NORMALIZED_INPUT_MAX_BYTES,
    }
    if transform is not None:
        document["transform"] = transform
        document["minimum_provider_input_dimension"] = (
            NORMALIZED_INPUT_MIN_DIMENSION
        )
    return document


def _validated_normalized_input_asset(
    binding: NormalizedInputRetryBinding,
    *,
    root: Path,
) -> tuple[dict[str, Any], str]:
    path = root / binding.asset_metadata_rel
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"Normalized-input asset metadata is missing: {path}")
    document = read_json(path)
    normalized = document.get("normalized") if isinstance(document, dict) else None
    if not isinstance(document, dict) or not isinstance(normalized, dict):
        raise PipelineError(f"Normalized-input asset metadata differs: {path}")
    preflight_fields = (
        "http_status",
        "url",
        "sha256",
        "bytes",
        "width",
        "height",
        "format",
    )
    preflight = {field: normalized.get(field) for field in preflight_fields}
    expected = _normalized_input_asset_document(binding, preflight, root=root)
    if document != expected:
        raise PipelineError(f"Normalized-input asset metadata differs: {path}")
    return document, sha256_file(path)


def _set_request_pointer(document: dict[str, Any], pointer: str, value: str) -> None:
    parts = [part for part in pointer.split("/") if part]
    current: Any = document
    try:
        for part in parts[:-1]:
            current = current[int(part)] if isinstance(current, list) else current[part]
        leaf = parts[-1]
        if isinstance(current, list):
            current[int(leaf)] = value
        else:
            current[leaf] = value
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise PipelineError(f"Normalized request pointer is absent: {pointer}") from exc


def _request_leaf_differences(
    left: Any,
    right: Any,
    pointer: str = "",
) -> list[tuple[str, Any, Any]]:
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        differences: list[tuple[str, Any, Any]] = []
        for key in left:
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            differences.extend(
                _request_leaf_differences(left[key], right[key], f"{pointer}/{escaped}")
            )
        return differences
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        differences = []
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            differences.extend(
                _request_leaf_differences(
                    left_item,
                    right_item,
                    f"{pointer}/{index}",
                )
            )
        return differences
    return [] if left == right else [(pointer or "/", left, right)]


def _normalized_retry_request(
    primary_request: dict[str, Any],
    model_id: str,
    original_url: str,
    normalized_url: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pointer = {
        "alibaba/wan-2.2": "/input/image",
        "alibaba/wan-2.7": "/frame_images/0/image_url/url",
    }.get(model_id)
    if pointer is None:
        raise PipelineError(f"Unsupported normalized-input retry model: {model_id}")
    retry_request = copy.deepcopy(primary_request)
    _set_request_pointer(retry_request, pointer, normalized_url)
    differences = _request_leaf_differences(primary_request, retry_request)
    expected = [(pointer, original_url, normalized_url)]
    if differences != expected:
        raise PipelineError(
            "Normalized-input retry must change exactly one model-specific image URL"
        )
    return retry_request, {
        "json_pointer": pointer,
        "from": original_url,
        "to": normalized_url,
        "changed_leaf_count": 1,
    }


def _known_retry_envelopes(root: Path) -> tuple[dict[str, Any], ...]:
    namespace = root / TERMINAL_RETRY_NAMESPACE_REL
    if not namespace.exists():
        return ()
    if not namespace.is_dir() or namespace.is_symlink():
        raise PipelineError(f"Retry namespace is not a real directory: {namespace}")
    documents: list[dict[str, Any]] = []
    for path in sorted(namespace.glob("*/retry.json")):
        if path.parent.is_symlink() or not path.is_file() or path.is_symlink():
            raise PipelineError(f"Retry envelope is not a regular file: {path}")
        document = read_json(path)
        if not isinstance(document, dict):
            raise PipelineError(f"Retry envelope is not an object: {path}")
        primary = document.get("primary_attempt")
        retry = document.get("retry_attempt")
        if (
            document.get("schema_version") != 1
            or document.get("manifest_role")
            != TERMINAL_RETRY_MANIFEST_ROLE
            or document.get("ticket") != TICKET
            or document.get("primary_batch_id") != BATCH_ID
            or document.get("retry_number") != TERMINAL_RETRY_VERSION
            or not isinstance(primary, dict)
            or not isinstance(retry, dict)
        ):
            raise PipelineError(f"Retry envelope identity is invalid: {path}")
        primary_id = primary.get("provider_run_id")
        logical_key = document.get("logical_output_key")
        if not isinstance(primary_id, str) or not primary_id:
            raise PipelineError(f"Retry envelope primary identity is missing: {path}")
        expected_key = hashlib.sha256(primary_id.encode("utf-8")).hexdigest()[:20]
        if path.parent.name != expected_key or retry.get("retry_key") != expected_key:
            raise PipelineError(f"Retry envelope path binding differs: {path}")
        if any(
            existing.get("primary_attempt", {}).get("provider_run_id") == primary_id
            for existing in documents
        ):
            raise PipelineError(f"Duplicate retry reservation for {primary_id}")
        documents.append(document)
    unexpected = [
        child
        for child in namespace.iterdir()
        if child.is_dir() and not (child / "retry.json").is_file()
    ]
    if unexpected:
        raise PipelineError(
            "Retry namespace contains an unbound directory: "
            + ", ".join(str(path) for path in unexpected[:3])
        )
    return tuple(documents)


def _known_ambiguous_submit_retry_envelopes(
    root: Path,
) -> tuple[dict[str, Any], ...]:
    """Inventory immutable quarantine reservations without provider access."""

    namespace = root / AMBIGUOUS_SUBMIT_RETRY_NAMESPACE_REL
    if not namespace.exists():
        return ()
    if not namespace.is_dir() or namespace.is_symlink():
        raise PipelineError(
            f"Ambiguous-submit retry namespace is not a real directory: {namespace}"
        )
    documents: list[dict[str, Any]] = []
    for path in sorted(namespace.glob("*/retry.json")):
        if path.parent.is_symlink() or not path.is_file() or path.is_symlink():
            raise PipelineError(
                f"Ambiguous-submit retry envelope is not a regular file: {path}"
            )
        document = read_json(path)
        if not isinstance(document, dict):
            raise PipelineError(
                f"Ambiguous-submit retry envelope is not an object: {path}"
            )
        primary = document.get("primary_attempt")
        retry = document.get("retry_attempt")
        if (
            document.get("schema_version") != 1
            or document.get("manifest_role")
            != AMBIGUOUS_RETRY_MANIFEST_ROLE
            or document.get("ticket") != TICKET
            or document.get("primary_batch_id") != BATCH_ID
            or document.get("retry_number") != AMBIGUOUS_SUBMIT_RETRY_VERSION
            or document.get("policy") != _ambiguous_submit_retry_policy()
            or not isinstance(primary, dict)
            or not isinstance(retry, dict)
        ):
            raise PipelineError(
                f"Ambiguous-submit retry envelope identity is invalid: {path}"
            )
        primary_id = primary.get("provider_run_id")
        if not isinstance(primary_id, str) or not primary_id:
            raise PipelineError(
                f"Ambiguous-submit retry primary identity is missing: {path}"
            )
        expected_key = hashlib.sha256(
            f"ambiguous-submit-v1:{primary_id}".encode("utf-8")
        ).hexdigest()[:20]
        if path.parent.name != expected_key or retry.get("retry_key") != expected_key:
            raise PipelineError(
                f"Ambiguous-submit retry envelope path binding differs: {path}"
            )
        if any(
            existing.get("primary_attempt", {}).get("provider_run_id")
            == primary_id
            for existing in documents
        ):
            raise PipelineError(
                f"Duplicate ambiguous-submit retry reservation for {primary_id}"
            )
        documents.append(document)
    unexpected = [
        child
        for child in namespace.iterdir()
        if child.is_dir() and not (child / "retry.json").is_file()
    ]
    if unexpected:
        raise PipelineError(
            "Ambiguous-submit retry namespace contains an unbound directory: "
            + ", ".join(str(path) for path in unexpected[:3])
        )
    return tuple(documents)


def _known_normalized_input_retry_envelopes(
    root: Path,
) -> tuple[dict[str, Any], ...]:
    """Inventory the two model-isolated oversize remediation reservations."""

    namespace = root / NORMALIZED_INPUT_RETRY_NAMESPACE_REL
    if not namespace.exists():
        return ()
    if not namespace.is_dir() or namespace.is_symlink():
        raise PipelineError(
            f"Normalized-input retry namespace is not a real directory: {namespace}"
        )
    documents: list[dict[str, Any]] = []
    for path in sorted(namespace.glob("*/retry.json")):
        if path.parent.is_symlink() or not path.is_file() or path.is_symlink():
            raise PipelineError(
                f"Normalized-input retry envelope is not a regular file: {path}"
            )
        document = read_json(path)
        primary = document.get("primary_attempt") if isinstance(document, dict) else None
        retry = document.get("retry_attempt") if isinstance(document, dict) else None
        logical_key = (
            document.get("logical_output_key")
            if isinstance(document, dict)
            else None
        )
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != 1
            or document.get("manifest_role")
            != NORMALIZED_RETRY_MANIFEST_ROLE
            or document.get("ticket") != TICKET
            or document.get("primary_batch_id") != BATCH_ID
            or document.get("retry_number") != NORMALIZED_INPUT_RETRY_VERSION
            or not isinstance(primary, dict)
            or not isinstance(retry, dict)
        ):
            raise PipelineError(
                f"Normalized-input retry envelope identity is invalid: {path}"
            )
        primary_id = primary.get("provider_run_id")
        if not isinstance(primary_id, str) or not primary_id:
            raise PipelineError(
                f"Normalized-input retry primary identity is missing: {path}"
            )
        target = (
            _normalized_input_target_for_key(
                logical_key.get("article_slug"),
                logical_key.get("image_id"),
                logical_key.get("model_id"),
            )
            if isinstance(logical_key, dict)
            else None
        )
        if target is None or primary_id != (
            f"{BATCH_ID}-{target.article_slug}-{target.image_id}-"
            f"{native.MODEL_SUFFIXES[logical_key['model_id']]}"
        ):
            raise PipelineError(
                f"Normalized-input retry logical output is ineligible: {path}"
            )
        if document.get("policy") != _normalized_input_retry_policy(
            target=target
        ):
            raise PipelineError(
                f"Normalized-input retry policy differs for its target: {path}"
            )
        expected_key = hashlib.sha256(
            f"normalized-input-v1:{primary_id}".encode("utf-8")
        ).hexdigest()[:20]
        if path.parent.name != expected_key or retry.get("retry_key") != expected_key:
            raise PipelineError(
                f"Normalized-input retry envelope path binding differs: {path}"
            )
        if any(
            existing.get("primary_attempt", {}).get("provider_run_id") == primary_id
            for existing in documents
        ):
            raise PipelineError(
                f"Duplicate normalized-input retry reservation for {primary_id}"
            )
        documents.append(document)
    unexpected = [
        child
        for child in namespace.iterdir()
        if child.is_dir() and not (child / "retry.json").is_file()
    ]
    if unexpected:
        raise PipelineError(
            "Normalized-input retry namespace contains an unbound directory: "
            + ", ".join(str(path) for path in unexpected[:3])
        )
    allowed_output_count = sum(
        len(target.model_ids) for target in NORMALIZED_INPUT_RETRY_ALLOWLIST
    )
    if len(documents) > allowed_output_count:
        raise PipelineError("Too many normalized-input retry reservations")
    return tuple(documents)


def _known_normalized_input_supersede_envelopes(
    root: Path,
) -> tuple[dict[str, Any], ...]:
    """Inventory the one exact nested supersede reservation without I/O."""

    if BATCH_ID != NORMALIZED_INPUT_SUPERSEDE_TARGET["batch_id"]:
        return ()
    path = root / NORMALIZED_INPUT_SUPERSEDE_NAMESPACE_REL / "supersede.json"
    candidates = list(
        (root / NORMALIZED_INPUT_RETRY_NAMESPACE_REL).glob(
            f"*/{NORMALIZED_INPUT_SUPERSEDE_DIRECTORY_NAME}/supersede.json"
        )
    )
    if not path.exists():
        if candidates:
            raise PipelineError(
                "Normalized-input supersede exists outside the exact allowlist"
            )
        return ()
    if not path.is_file() or path.is_symlink():
        raise PipelineError(
            f"Normalized-input supersede envelope is not a regular file: {path}"
        )
    document = read_json(path)
    normalized = document.get("normalized_retry") if isinstance(document, dict) else None
    supersede = document.get("superseding_attempt") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("manifest_role")
        != NORMALIZED_INPUT_SUPERSEDE_MANIFEST_ROLE
        or document.get("ticket") != TICKET
        or document.get("primary_batch_id") != BATCH_ID
        or document.get("supersede_number")
        != NORMALIZED_INPUT_SUPERSEDE_VERSION
        or not isinstance(normalized, dict)
        or normalized.get("provider_run_id")
        != NORMALIZED_INPUT_SUPERSEDE_TARGET[
            "normalized_retry_provider_run_id"
        ]
        or not isinstance(supersede, dict)
    ):
        raise PipelineError(
            f"Normalized-input supersede envelope identity is invalid: {path}"
        )
    unexpected = [candidate for candidate in candidates if candidate != path]
    if unexpected:
        raise PipelineError(
            "More than one normalized-input supersede reservation is forbidden"
        )
    return (document,)


def _enforce_retry_namespace_conflicts(
    terminal: Iterable[dict[str, Any]],
    ambiguous: Iterable[dict[str, Any]],
    normalized: Iterable[dict[str, Any]],
) -> None:
    seen: dict[str, str] = {}
    for label, documents in (
        ("terminal", terminal),
        ("ambiguous-submit", ambiguous),
        ("normalized-input", normalized),
    ):
        for document in documents:
            primary = document.get("primary_attempt")
            primary_id = primary.get("provider_run_id") if isinstance(primary, dict) else None
            if not isinstance(primary_id, str) or not primary_id:
                raise PipelineError(f"{label} retry primary identity is missing")
            previous = seen.setdefault(primary_id, label)
            if previous != label:
                raise PipelineError(
                    f"Logical output {primary_id} has conflicting {previous} and "
                    f"{label} retry reservations"
                )


def _aggregate_retry_cost(
    inventory: dict[str, Any],
    *,
    root: Path,
    additional_terminal: int = 0,
    additional_ambiguous: int = 0,
    additional_normalized: int = 0,
    additional_normalized_supersede: int = 0,
) -> dict[str, Any]:
    """Count every immutable namespace before admitting another reservation."""

    terminal = _known_retry_envelopes(root)
    ambiguous = _known_ambiguous_submit_retry_envelopes(root)
    normalized = _known_normalized_input_retry_envelopes(root)
    normalized_supersedes = _known_normalized_input_supersede_envelopes(root)
    _enforce_retry_namespace_conflicts(terminal, ambiguous, normalized)

    return aggregate_retry_budget_metadata(
        inventory,
        terminal_retry_reservations=(
            len(terminal) + additional_terminal
        ),
        ambiguous_submit_retry_reservations=(
            len(ambiguous) + additional_ambiguous
        ),
        normalized_input_retry_reservations=(
            len(normalized) + additional_normalized
        ),
        normalized_input_supersede_reservations=(
            len(normalized_supersedes) + additional_normalized_supersede
        ),
    )


def inventory_document(
    discovery: Discovery,
    budget: str | Decimal,
    root: Path = ROOT,
) -> dict[str, Any]:
    expected_outputs = len(discovery.sources) * len(MODEL_IDS)
    return {
        "schema_version": 1,
        "manifest_role": INVENTORY_MANIFEST_ROLE,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "article_config": {
            "path": TICKET_CONFIG_REL.as_posix(),
            "sha256": sha256_file(root / TICKET_CONFIG_REL),
        },
        "extraction_report": {
            "path": EXTRACTION_REPORT_REL.as_posix(),
            "sha256": discovery.extraction_report_sha256,
        },
        "source_manifest": {
            "path": SOURCE_MANIFEST_REL.as_posix(),
            "sha256": sha256_file(root / SOURCE_MANIFEST_REL),
            "row_count": discovery.source_manifest_row_count,
        },
        "contract": _inventory_contract_snapshot(root),
        "generation_routes": _route_snapshot(root),
        "models": list(MODEL_IDS),
        "article_count": len(discovery.articles),
        "image_count": len(discovery.sources),
        "expected_outputs": expected_outputs,
        "selection_rule": (
            "in ticket-config order, include every image block from every "
            "successfully extracted article, including the cover, in original "
            "block order; preserve original article numbers"
        ),
        "generation_policy": {
            "independent_route_pools": True,
            "route_capacities": dict(ROUTE_CAPACITIES),
            "article_order": "ticket-config-order",
            "article_barrier": True,
            "exact_model_routes_only": True,
            "route_discovery": False,
            "automatic_fallback": False,
            "automatic_paid_retries": False,
            "maximum_paid_submissions_per_job": 1,
            "aggregate_manifest_writer": "coordinator-only",
        },
        "cost": cost_metadata(budget, expected_outputs),
        "unavailable_articles": list(discovery.unavailable_articles),
        "articles": [
            {
                "article_number": article.number,
                "article_slug": article.slug,
                "label": article.label,
                "url": article.url,
                "title": article.title,
                "lead": article.lead,
                "context": {
                    "path": article.context_path,
                    "sha256": article.context_sha256,
                },
                "cover_image": article.cover_image,
                "image_count": len(article.images),
                "images": [
                    {
                        "image": source.image,
                        "planning_run_id": source.planning_run_id,
                    }
                    for source in discovery.sources
                    if source.article_slug == article.slug
                ],
            }
            for article in discovery.articles
        ],
    }


def write_inventory(
    discovery: Discovery,
    budget: str | Decimal,
    root: Path = ROOT,
) -> dict[str, Any]:
    document = inventory_document(discovery, budget, root)
    path = root / INVENTORY_MANIFEST_REL
    if path.is_file():
        if read_json(path) != document:
            raise PipelineError(f"Immutable inventory differs: {path}")
        return document
    if path.exists():
        raise PipelineError(f"Inventory target is not a regular file: {path}")
    transport.atomic_write_json(path, document)
    return document


def require_inventory(
    discovery: Discovery,
    budget: str | Decimal,
    root: Path = ROOT,
) -> dict[str, Any]:
    expected = inventory_document(discovery, budget, root)
    path = root / INVENTORY_MANIFEST_REL
    if not path.is_file() or path.is_symlink():
        raise PipelineError(
            f"Frozen inventory is missing; run the inventory command first: {path}"
        )
    if read_json(path) != expected:
        raise PipelineError("Frozen inventory or its bound extraction/route inputs changed")
    return expected


@contextmanager
def inventory_run_lock(root: Path):
    path = root / INVENTORY_MANIFEST_REL
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"Frozen inventory cannot be locked: {path}")
    with path.open("rb") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError(
                "another PROMOPAGES-10060 coordinator holds the batch lock"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def configure_native(sources: Iterable[Source], root: Path = ROOT) -> None:
    """Bind the tested provider bridge to this exact namespaced matrix."""

    sources = tuple(sources)
    if not sources:
        raise PipelineError("Cannot configure an empty provider matrix")
    _contract_snapshot(root)
    _route_snapshot(root)
    by_sample_id = {source.sample_id: source for source in sources}
    if len(by_sample_id) != len(sources):
        raise PipelineError("Provider sample IDs are not unique")

    native.BATCH_ID = BATCH_ID
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = MODEL_IDS
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = GENERATION_MANIFEST_REL
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = planning_provenance_verifier()
    native.SAMPLES = tuple(source.sample for source in sources)
    native.WAN_SUBMIT_MODE = None
    native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()

    def provider_sample(entry: native.Entry) -> dict[str, Any]:
        source = by_sample_id.get(entry.sample.sample_id)
        if source is None:
            raise PipelineError(f"Unknown provider sample: {entry.sample.sample_id}")
        image = source.image
        return {
            "sample_id": source.sample_id,
            "article_slug": source.article_slug,
            "image_id": image["image_id"],
            "image_number": image["image_id"],
            "source_path": image["source_path"],
            # The public source-of-truth MDS original avoids depending on a
            # repository push before the Eliza image_url request is submitted.
            "source_url": image["orig_url"],
            "sha256": image["sha256"],
            "width": image["width"],
            "height": image["height"],
        }

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        base = (
            workspace
            / BATCH_ROOT_REL
            / "videos"
            / entry.sample.article_slug
            / native.MODEL_DIRECTORIES[entry.model_id]
        )
        stem = entry.sample.image_id
        return {
            "directory": base,
            "prompt": base / f"{stem}.prompt.json",
            "run": base / f"{stem}.run.json",
            "video": base / f"{stem}.mp4",
        }

    native.provider_sample = provider_sample
    native.artifact_paths = artifact_paths
    matrix = native.matrix()
    if len(matrix) != len(sources) * len(MODEL_IDS):
        raise PipelineError("Native provider matrix size changed")


def resolve_primary_retry_target(
    sources: Iterable[Source],
    provider_run_id: str,
) -> tuple[Source, str]:
    matches = [
        (source, model_id)
        for source in sources
        for model_id in MODEL_IDS
        if primary_provider_run_id(source, model_id) == provider_run_id
    ]
    if len(matches) != 1:
        raise PipelineError(
            f"Unknown primary provider run ID for terminal retry: {provider_run_id}"
        )
    return matches[0]


def _primary_terminal_failure_evidence(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any]:
    """Validate one definitive primary failure without writing any artifact."""

    entry = native.Entry(source.sample, model_id)
    expected_provider_run_id = primary_provider_run_id(source, model_id)
    if entry.provider_run_id != expected_provider_run_id:
        raise PipelineError("Primary native retry target is not configured")
    paths = primary_artifact_paths(source, model_id, root)
    if not paths["run"].is_file() or paths["run"].is_symlink():
        raise PipelineError(f"Primary terminal receipt is missing: {paths['run']}")
    if not paths["prompt"].is_file() or paths["prompt"].is_symlink():
        raise PipelineError(f"Primary immutable prompt is missing: {paths['prompt']}")
    run = read_json(paths["run"])
    if not isinstance(run, dict):
        raise PipelineError(f"Primary terminal receipt is not an object: {paths['run']}")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": expected_provider_run_id,
        "model_id": model_id,
    }
    mismatches = [
        key for key, expected in expected_identity.items() if run.get(key) != expected
    ]
    if mismatches:
        raise PipelineError(
            "Primary terminal receipt identity differs "
            f"({', '.join(mismatches)}): {paths['run']}"
        )
    if (
        run.get("status") != "provider-failed"
        or run.get("provider_may_be_active") is not False
        or not isinstance(run.get("provider_job_id"), str)
        or not run.get("provider_job_id")
        or not isinstance(run.get("completed_at"), str)
    ):
        raise PipelineError(
            "Explicit retry requires a definitive provider-failed primary "
            "receipt with a provider identity and no active job"
        )
    if paths["video"].exists():
        raise PipelineError(
            f"Primary provider-failed receipt unexpectedly has media: {paths['video']}"
        )
    job = native.load_lite_job(entry, root)
    expected_prompt_artifact = native.prompt_artifact(job)
    actual_prompt_artifact = read_json(paths["prompt"])
    if actual_prompt_artifact != expected_prompt_artifact:
        raise PipelineError(
            f"Primary prompt differs from verified Lite result: {entry.provider_run_id}"
        )
    sample = native.provider_sample(entry)
    prompt = native.provider_prompt(job)
    expected_request = native.provider_request_preview(sample, prompt)
    expected_request_sha256 = transport.request_fingerprint(
        expected_request, sample
    )
    if (
        run.get("request") != expected_request
        or run.get("request_sha256") != expected_request_sha256
    ):
        raise PipelineError(
            f"Primary provider request differs from verified Lite binding: "
            f"{entry.provider_run_id}"
        )
    return {
        "provider_run_id": expected_provider_run_id,
        "provider_job_id": run["provider_job_id"],
        "status": "provider-failed",
        "provider_may_be_active": False,
        "submitted_at": run.get("submitted_at"),
        "completed_at": run["completed_at"],
        "error": run.get("error"),
        "run_path": relative(paths["run"], root),
        "run_sha256": sha256_file(paths["run"]),
        "prompt_path": relative(paths["prompt"], root),
        "prompt_sha256": sha256_file(paths["prompt"]),
        "request": expected_request,
        "request_sha256": expected_request_sha256,
        "lite_result_path": job.result_path,
        "lite_result_sha256": job.result_sha256,
        "source_path": source.image["source_path"],
        "source_sha256": source.image["sha256"],
        "model_id": model_id,
        "lite_run_id": source.planning_run_id,
    }


def _terminal_retry_envelope_document(
    binding: TerminalRetryBinding,
    primary: dict[str, Any],
    aggregate_cost: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": TERMINAL_RETRY_MANIFEST_ROLE,
        "ticket": TICKET,
        "primary_batch_id": BATCH_ID,
        "retry_number": TERMINAL_RETRY_VERSION,
        "agent_id": AGENT_ID,
        "logical_output_key": {
            "article_slug": binding.source.article_slug,
            "image_id": binding.source.image["image_id"],
            "model_id": binding.model_id,
        },
        "primary_attempt": primary,
        "retry_attempt": {
            "retry_key": binding.retry_key,
            "batch_id": binding.retry_batch_id,
            "provider_run_id": binding.retry_provider_run_id,
            "lite_run_id": binding.source.planning_run_id,
            "model_id": binding.model_id,
            "source_path": binding.source.image["source_path"],
            "source_sha256": binding.source.image["sha256"],
            "prompt_path": binding.prompt_rel.as_posix(),
            "run_path": binding.run_rel.as_posix(),
            "video_path": binding.video_rel.as_posix(),
            "generation_manifest_path": binding.manifest_rel.as_posix(),
        },
        "cost": aggregate_cost,
        "policy": {
            "explicit_operator_command_required": True,
            "automatic_retry": False,
            "maximum_new_paid_submissions": 1,
            "same_verified_lite_result": True,
            "same_source": True,
            "same_prompt": True,
            "same_model": True,
            "fallback": False,
            "primary_receipt_immutable": True,
        },
    }


def configure_terminal_retry_native(
    binding: TerminalRetryBinding,
    root: Path = ROOT,
) -> None:
    """Bind the native one-submit guard to one isolated retry-v1 output."""

    _contract_snapshot(root)
    _route_snapshot(root)
    source = binding.source
    model_id = binding.model_id
    native.BATCH_ID = binding.retry_batch_id
    # Planning remains the exact original verified three-model Lite result.
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = (model_id,)
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = binding.manifest_rel
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = planning_provenance_verifier()
    native.SAMPLES = (source.sample,)
    native.WAN_SUBMIT_MODE = None
    native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()

    def provider_sample(entry: native.Entry) -> dict[str, Any]:
        if (
            entry.sample.sample_id != source.sample_id
            or entry.model_id != model_id
        ):
            raise PipelineError(f"Unknown retry provider entry: {entry.run_id}")
        image = source.image
        return {
            "sample_id": source.sample_id,
            "article_slug": source.article_slug,
            "image_id": image["image_id"],
            "image_number": image["image_id"],
            "source_path": image["source_path"],
            "source_url": image["orig_url"],
            "sha256": image["sha256"],
            "width": image["width"],
            "height": image["height"],
        }

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        if entry.provider_run_id != binding.retry_provider_run_id:
            raise PipelineError(
                f"Retry provider identity changed: {entry.provider_run_id}"
            )
        directory = workspace / binding.media_directory_rel
        return {
            "directory": directory,
            "prompt": workspace / binding.prompt_rel,
            "run": workspace / binding.run_rel,
            "video": workspace / binding.video_rel,
        }

    native.provider_sample = provider_sample
    native.artifact_paths = artifact_paths
    matrix = native.matrix()
    if (
        len(matrix) != 1
        or matrix[0].provider_run_id != binding.retry_provider_run_id
        or matrix[0].planning_run_id != source.planning_run_id
        or matrix[0].model_id != model_id
    ):
        raise PipelineError("Terminal retry native matrix identity changed")


def _primary_ambiguous_submit_evidence(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any]:
    """Bind one genuinely unknown provider POST without reclassifying it."""

    route_identity = ROUTE_IDENTITIES.get(model_id)
    if model_id not in MODEL_IDS or route_identity is None:
        raise PipelineError(f"Ambiguous-submit retry model is unsupported: {model_id}")
    expected_adapter, _expected_transport = route_identity
    if expected_adapter not in {"eliza-segmind", "eliza-openrouter"}:
        raise PipelineError(
            f"Ambiguous-submit retry adapter is unsupported: {expected_adapter}"
        )
    entry = native.Entry(source.sample, model_id)
    expected_provider_run_id = primary_provider_run_id(source, model_id)
    if entry.provider_run_id != expected_provider_run_id:
        raise PipelineError("Primary ambiguous-submit target is not configured")
    paths = primary_artifact_paths(source, model_id, root)
    if not paths["run"].is_file() or paths["run"].is_symlink():
        raise PipelineError(f"Primary ambiguous receipt is missing: {paths['run']}")
    if not paths["prompt"].is_file() or paths["prompt"].is_symlink():
        raise PipelineError(f"Primary immutable prompt is missing: {paths['prompt']}")
    if paths["video"].exists():
        raise PipelineError(
            f"Ambiguous primary unexpectedly has media: {paths['video']}"
        )
    run = read_json(paths["run"])
    if not isinstance(run, dict):
        raise PipelineError(f"Primary ambiguous receipt is not an object: {paths['run']}")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": expected_provider_run_id,
        "model_id": model_id,
        "adapter": expected_adapter,
    }
    mismatches = [
        key for key, expected in expected_identity.items() if run.get(key) != expected
    ]
    if mismatches:
        raise PipelineError(
            "Primary ambiguous receipt identity differs "
            f"({', '.join(mismatches)}): {paths['run']}"
        )
    recorded_status = run.get("status")
    if (
        recorded_status not in {"submitting", "submit-unknown"}
        or run.get("provider_may_be_active") is not True
        or run.get("provider_job_id") is not None
        or run.get("provider_session_hash") is not None
        or run.get("submitted_at") is not None
        or run.get("completed_at") is not None
        or run.get("media") is not None
        or run.get("contract_check") is not None
    ):
        raise PipelineError(
            "Explicit ambiguous-submit retry requires an unresolved provider "
            "receipt with no provider identity, timestamps, or media"
        )

    job = native.load_lite_job(entry, root)
    expected_prompt_artifact = native.prompt_artifact(job)
    if read_json(paths["prompt"]) != expected_prompt_artifact:
        raise PipelineError(
            f"Primary prompt differs from verified Lite result: {entry.provider_run_id}"
        )
    sample = native.provider_sample(entry)
    prompt = native.provider_prompt(job)
    expected_request = native.provider_request_preview(sample, prompt)
    expected_request_sha256 = transport.request_fingerprint(
        expected_request, sample
    )
    if (
        run.get("request") != expected_request
        or run.get("request_sha256") != expected_request_sha256
    ):
        raise PipelineError(
            f"Primary provider request differs from verified Lite binding: "
            f"{entry.provider_run_id}"
        )
    if expected_adapter == "eliza-segmind":
        if native._is_exact_legacy_segmind_quota_pre_submit_failure(
            run,
            expected_request,
            expected_request_sha256,
            expected_adapter,
        ):
            raise PipelineError(
                "The primary receipt is exact known pre-submit quota evidence, "
                "not an ambiguous provider outcome"
            )
    elif native._is_exact_legacy_eliza_dns_pre_submit_failure(
        run,
        expected_request,
        expected_request_sha256,
        expected_adapter,
    ):
        raise PipelineError(
            "The primary receipt is exact known pre-submit DNS evidence, not "
            "an ambiguous provider outcome"
        )
    source_preflight = run.get("source_preflight")
    if expected_adapter == "eliza-segmind":
        if (
            not isinstance(source_preflight, dict)
            or source_preflight.get("http_status") != 200
            or not isinstance(source_preflight.get("bytes"), int)
            or source_preflight["bytes"] < 1
            or source_preflight.get("sha256") != source.image["sha256"]
        ):
            raise PipelineError(
                "Ambiguous Segmind receipt lacks the exact successful source preflight"
            )
    elif source_preflight is not None:
        raise PipelineError(
            "Ambiguous Eliza/OpenRouter receipt unexpectedly has source preflight"
        )
    receipt_error = run.get("error")
    if receipt_error is not None and (
        not isinstance(receipt_error, str) or not receipt_error
    ):
        raise PipelineError("Ambiguous primary receipt error is invalid")
    ambiguity_reason = receipt_error or (
        "Provider POST may have reached the exact configured route, but no "
        "response or provider request identity was durably recorded"
    )
    return {
        "provider_run_id": expected_provider_run_id,
        # The envelope exposes a stable semantic status while preserving the
        # byte-identical primary receipt and its recorded transition below.
        "status": "submit-unknown",
        "recorded_status": recorded_status,
        "outcome": "unknown",
        "outcome_unknown": True,
        "ambiguity_reason": ambiguity_reason,
        "provider_may_be_active": True,
        "provider_job_id": None,
        "provider_session_hash": None,
        "submitted_at": None,
        "completed_at": None,
        "error": receipt_error,
        "run_path": relative(paths["run"], root),
        "run_sha256": sha256_file(paths["run"]),
        "prompt_path": relative(paths["prompt"], root),
        "prompt_sha256": sha256_file(paths["prompt"]),
        "request": expected_request,
        "request_sha256": expected_request_sha256,
        "source_preflight": source_preflight,
        "lite_result_path": job.result_path,
        "lite_result_sha256": job.result_sha256,
        "source_path": source.image["source_path"],
        "source_sha256": source.image["sha256"],
        "model_id": model_id,
        "adapter": expected_adapter,
        "lite_run_id": source.planning_run_id,
    }


def _ambiguous_submit_retry_envelope_document(
    binding: AmbiguousSubmitRetryBinding,
    primary: dict[str, Any],
    aggregate_cost: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": AMBIGUOUS_RETRY_MANIFEST_ROLE,
        "ticket": TICKET,
        "primary_batch_id": BATCH_ID,
        "retry_number": AMBIGUOUS_SUBMIT_RETRY_VERSION,
        "agent_id": AGENT_ID,
        "logical_output_key": {
            "article_slug": binding.source.article_slug,
            "image_id": binding.source.image["image_id"],
            "model_id": binding.model_id,
        },
        "primary_attempt": primary,
        "retry_attempt": {
            "retry_key": binding.retry_key,
            "batch_id": binding.retry_batch_id,
            "provider_run_id": binding.retry_provider_run_id,
            "lite_run_id": binding.source.planning_run_id,
            "model_id": binding.model_id,
            "source_path": binding.source.image["source_path"],
            "source_sha256": binding.source.image["sha256"],
            "prompt_path": binding.prompt_rel.as_posix(),
            "run_path": binding.run_rel.as_posix(),
            "video_path": binding.video_rel.as_posix(),
            "generation_manifest_path": binding.manifest_rel.as_posix(),
        },
        "cost": aggregate_cost,
        "policy": _ambiguous_submit_retry_policy(),
    }


def _ambiguous_submit_retry_policy() -> dict[str, Any]:
    return {
        "explicit_operator_command_required": True,
        "automatic_retry": False,
        "maximum_new_paid_submissions": 1,
        "retry2_forbidden": True,
        "same_verified_lite_result": True,
        "same_source": True,
        "same_prompt": True,
        "same_model": True,
        "same_request": True,
        "fallback": False,
        "primary_receipt_immutable": True,
        "primary_outcome": "unknown",
        "primary_is_definitive_pre_submit": False,
        "duplicate_submission_risk_acknowledged": True,
    }


def configure_ambiguous_submit_retry_native(
    binding: AmbiguousSubmitRetryBinding,
    root: Path = ROOT,
) -> None:
    """Bind one quarantine namespace to the exact frozen provider route."""

    _contract_snapshot(root)
    _route_snapshot(root)
    source = binding.source
    model_id = binding.model_id
    route_identity = ROUTE_IDENTITIES.get(model_id)
    if model_id not in MODEL_IDS or route_identity is None:
        raise PipelineError(f"Ambiguous-submit retry model is unsupported: {model_id}")
    if route_identity[0] not in {"eliza-segmind", "eliza-openrouter"}:
        raise PipelineError(
            f"Ambiguous-submit retry adapter is unsupported: {route_identity[0]}"
        )
    native.BATCH_ID = binding.retry_batch_id
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = (model_id,)
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = binding.manifest_rel
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = planning_provenance_verifier()
    native.SAMPLES = (source.sample,)
    native.WAN_SUBMIT_MODE = None
    native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()

    def provider_sample(entry: native.Entry) -> dict[str, Any]:
        if entry.sample.sample_id != source.sample_id or entry.model_id != model_id:
            raise PipelineError(
                f"Unknown ambiguous-submit retry provider entry: {entry.run_id}"
            )
        image = source.image
        return {
            "sample_id": source.sample_id,
            "article_slug": source.article_slug,
            "image_id": image["image_id"],
            "image_number": image["image_id"],
            "source_path": image["source_path"],
            "source_url": image["orig_url"],
            "sha256": image["sha256"],
            "width": image["width"],
            "height": image["height"],
        }

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        if entry.provider_run_id != binding.retry_provider_run_id:
            raise PipelineError(
                f"Ambiguous-submit retry identity changed: {entry.provider_run_id}"
            )
        return {
            "directory": workspace / binding.media_directory_rel,
            "prompt": workspace / binding.prompt_rel,
            "run": workspace / binding.run_rel,
            "video": workspace / binding.video_rel,
        }

    native.provider_sample = provider_sample
    native.artifact_paths = artifact_paths
    matrix = native.matrix()
    if (
        len(matrix) != 1
        or matrix[0].provider_run_id != binding.retry_provider_run_id
        or matrix[0].planning_run_id != source.planning_run_id
        or matrix[0].model_id != model_id
    ):
        raise PipelineError("Ambiguous-submit retry native matrix identity changed")


def _verified_primary_normalized_input_evidence(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], Any, dict[str, Path]]:
    """Bind the immutable primary prompt/request before interpreting failure."""

    _require_normalized_input_target(source, model_id)
    entry = native.Entry(source.sample, model_id)
    expected_provider_run_id = primary_provider_run_id(source, model_id)
    if entry.provider_run_id != expected_provider_run_id:
        raise PipelineError("Primary normalized-input target is not configured")
    paths = primary_artifact_paths(source, model_id, root)
    if not paths["run"].is_file() or paths["run"].is_symlink():
        raise PipelineError(
            f"Primary normalized-input receipt is missing: {paths['run']}"
        )
    if not paths["prompt"].is_file() or paths["prompt"].is_symlink():
        raise PipelineError(f"Primary immutable prompt is missing: {paths['prompt']}")
    if paths["video"].exists():
        raise PipelineError(
            "Primary normalized-input failure unexpectedly has media: "
            f"{paths['video']}"
        )
    run = read_json(paths["run"])
    if not isinstance(run, dict):
        raise PipelineError(
            f"Primary normalized-input receipt is not an object: {paths['run']}"
        )
    expected_identity = {
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": expected_provider_run_id,
        "model_id": model_id,
        "adapter": ROUTE_IDENTITIES[model_id][0],
    }
    mismatches = [
        key for key, expected in expected_identity.items() if run.get(key) != expected
    ]
    if mismatches:
        raise PipelineError(
            "Primary normalized-input receipt identity differs "
            f"({', '.join(mismatches)}): {paths['run']}"
        )
    if run.get("media") is not None or run.get("contract_check") is not None:
        raise PipelineError(
            "Primary normalized-input receipt unexpectedly contains media audit"
        )
    job = native.load_lite_job(entry, root)
    if read_json(paths["prompt"]) != native.prompt_artifact(job):
        raise PipelineError(
            f"Primary prompt differs from verified Lite result: {expected_provider_run_id}"
        )
    sample = native.provider_sample(entry)
    prompt = native.provider_prompt(job)
    expected_request = native.provider_request_preview(sample, prompt)
    expected_request_sha256 = transport.request_fingerprint(expected_request, sample)
    if (
        run.get("request") != expected_request
        or run.get("request_sha256") != expected_request_sha256
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        raise PipelineError(
            f"Primary normalized-input request differs from verified Lite binding: "
            f"{expected_provider_run_id}"
        )
    return run, expected_request, job, paths


def _primary_normalized_input_failure_evidence(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any]:
    """Recognize only an exact allowlisted input failure; never rewrite it."""

    run, request, job, paths = _verified_primary_normalized_input_evidence(
        source,
        model_id,
        root=root,
    )
    recorded_status = run.get("status")
    recorded_active = run.get("provider_may_be_active")
    provider_failure: dict[str, Any] | None = None
    recorded_provider_job_id = run.get("provider_job_id")
    constraint = _normalized_input_constraint(source, root)
    if model_id == "alibaba/wan-2.2":
        prefix = "Eliza/Segmind POST failed with HTTP 400: "
        error = run.get("error")
        if not isinstance(error, str) or not error.startswith(prefix):
            raise PipelineError(
                "Wan 2.2 primary is not the exact normalized-input HTTP 400"
            )
        parser = (
            transport.parse_segmind_oversize_task_failure
            if constraint == "maximum-bytes"
            else transport.parse_segmind_undersize_task_failure
        )
        provider_failure = parser(400, error[len(prefix) :])
        source_preflight = run.get("source_preflight")
        original = _normalized_input_original_source(source, root)
        if (
            provider_failure is None
            or recorded_status != "submit-unknown"
            or recorded_active is not True
            or recorded_provider_job_id is not None
            or run.get("submitted_at") is not None
            or run.get("completed_at") is not None
            or not isinstance(source_preflight, dict)
            or source_preflight.get("http_status") != 200
            or source_preflight.get("bytes") != original["bytes"]
            or source_preflight.get("sha256") != original["sha256"]
        ):
            raise PipelineError(
                "Wan 2.2 primary lacks exact terminal Segmind normalized-input "
                "evidence"
            )
        provider_job_id = provider_failure["provider_task_id"]
    else:
        provider_job_id = run.get("provider_job_id")
        if constraint == "maximum-bytes":
            exact_error = (
                f"Eliza/OpenRouter job {provider_job_id} failed with status failed: "
                "File size exceeds maximum allowed size of 20971520 bytes"
            )
        else:
            exact_error = (
                f"Eliza/OpenRouter job {provider_job_id} failed with status failed: "
                "Error validating image resolution: "
                '{"name": "InvalidParameter", "code": 400, "message": '
                '"image *** resolution must be at least 240x240, got '
                f'{source.image["width"]}x{source.image["height"]}", '
                '"internal_name": "InvalidParameter"}'
            )
        if (
            recorded_status != "provider-failed"
            or recorded_active is not False
            or not isinstance(provider_job_id, str)
            or not provider_job_id
            or not isinstance(run.get("submitted_at"), str)
            or not run.get("submitted_at")
            or not isinstance(run.get("completed_at"), str)
            or not run.get("completed_at")
            or run.get("error") != exact_error
        ):
            raise PipelineError(
                "Wan 2.7 primary is not the exact terminal normalized-input "
                "failure"
            )
    evidence: dict[str, Any] = {
        "provider_run_id": primary_provider_run_id(source, model_id),
        "provider_job_id": provider_job_id,
        "provider_task_id": (
            provider_failure.get("provider_task_id")
            if isinstance(provider_failure, dict)
            else None
        ),
        "status": "provider-failed",
        "recorded_status": recorded_status,
        "provider_may_be_active": False,
        "recorded_provider_may_be_active": recorded_active,
        "recorded_provider_job_id": recorded_provider_job_id,
        "submitted_at": run.get("submitted_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error"),
        "run_path": relative(paths["run"], root),
        "run_sha256": sha256_file(paths["run"]),
        "prompt_path": relative(paths["prompt"], root),
        "prompt_sha256": sha256_file(paths["prompt"]),
        "request": request,
        "request_sha256": run["request_sha256"],
        "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
        "lite_result_path": job.result_path,
        "lite_result_sha256": job.result_sha256,
        "source": _normalized_input_original_source(source, root),
        "model_id": model_id,
        "adapter": ROUTE_IDENTITIES[model_id][0],
        "lite_run_id": source.planning_run_id,
    }
    if provider_failure is not None:
        evidence["provider_failure"] = provider_failure
        evidence["provider_submit_time"] = provider_failure.get("submit_time")
        evidence["provider_scheduled_time"] = provider_failure.get("scheduled_time")
        evidence["provider_end_time"] = provider_failure.get("end_time")
    return evidence


def _normalized_input_retry_policy(
    binding: NormalizedInputRetryBinding | None = None,
    *,
    target: NormalizedInputRetryTarget | None = None,
) -> dict[str, Any]:
    policy = {
        "explicit_operator_command_required": True,
        "automatic_retry": False,
        "maximum_new_paid_submissions": 1,
        "retry2_forbidden": True,
        "same_verified_lite_result": True,
        "same_prompt": True,
        "same_model": True,
        "request_delta_only_image_pointer": True,
        "shared_frozen_scale_1200_asset": True,
        "local_reencode": False,
        "fallback": False,
        "primary_receipt_immutable": True,
    }
    if binding is not None and target is not None:
        raise PipelineError("Normalized-input retry policy target is ambiguous")
    if binding is not None:
        target = _normalized_input_target(binding.source, binding.model_id)
        if target is None:
            raise PipelineError("Normalized-input retry policy target is not allowlisted")
    if target is not None and target.replacement is not None:
        policy.update(
            {
                "shared_frozen_scale_1200_asset": False,
                "local_reencode": True,
                "commit_pinned_repository_asset": True,
                "normalization_strategy": target.replacement.strategy,
            }
        )
    return policy


def _normalized_input_generation_policy() -> dict[str, Any]:
    """Describe the selected batch allowlist without inventing retry targets."""

    policy: dict[str, Any] = {
        "version": NORMALIZED_INPUT_RETRY_VERSION,
        "namespace": NORMALIZED_INPUT_RETRY_NAMESPACE_REL.as_posix(),
        "shared_asset_namespace": NORMALIZED_INPUT_ASSET_NAMESPACE_REL.as_posix(),
    }
    if len(NORMALIZED_INPUT_RETRY_ALLOWLIST) == 1:
        # Preserve the frozen legacy sidecar shape exactly.
        target = NORMALIZED_INPUT_RETRY_ALLOWLIST[0]
        policy.update(
            {
                "eligible_source": {
                    "article_slug": target.article_slug,
                    "image_id": target.image_id,
                },
                "models": list(target.model_ids),
            }
        )
    else:
        policy["eligible_sources"] = [
            {
                "article_slug": target.article_slug,
                "image_id": target.image_id,
                "source_sha256": target.source_sha256,
                "models": list(target.model_ids),
                "failure_kind": target.failure_kind,
                "normalization_strategy": (
                    target.replacement.strategy
                    if target.replacement is not None
                    else "frozen-page-variant"
                ),
            }
            for target in NORMALIZED_INPUT_RETRY_ALLOWLIST
        ]
    policy.update(
        {
            "explicit_operator_command_required": True,
            "maximum_new_paid_submissions_per_eligible_output": 1,
            "retry2_forbidden": True,
            "automatic_paid_retries": False,
            "fallback": False,
            "primary_receipts_immutable": True,
            "request_delta_only_image_pointer": True,
        }
    )
    return policy


def _normalized_input_source_transform(
    binding: NormalizedInputRetryBinding,
    asset: dict[str, Any],
    asset_sha256: str,
    request_delta: dict[str, Any],
) -> dict[str, Any]:
    normalized = asset["normalized"]
    transform = {
        "strategy": asset["strategy"],
        "original": asset["original"],
        "normalized": {
            **normalized,
            "metadata_path": binding.asset_metadata_rel.as_posix(),
            "metadata_sha256": asset_sha256,
        },
        "request_delta": request_delta,
    }
    if asset["strategy"] == "deterministic-uniform-upscale":
        transform["preparation"] = asset["transform"]
        transform["minimum_provider_input_dimension"] = (
            asset["minimum_provider_input_dimension"]
        )
    return transform


def _normalized_input_retry_envelope_document(
    binding: NormalizedInputRetryBinding,
    primary: dict[str, Any],
    asset: dict[str, Any],
    asset_sha256: str,
    aggregate_cost: dict[str, Any],
) -> dict[str, Any]:
    normalized = asset["normalized"]
    retry_request, request_delta = _normalized_retry_request(
        primary["request"],
        binding.model_id,
        primary["source"]["url"],
        normalized["url"],
    )
    normalized_sample = {
        "source_path": binding.source.image["source_path"],
        "sha256": normalized["sha256"],
    }
    retry_request_sha256 = transport.request_fingerprint(
        retry_request,
        normalized_sample,
    )
    return {
        "schema_version": 1,
        "manifest_role": NORMALIZED_RETRY_MANIFEST_ROLE,
        "ticket": TICKET,
        "primary_batch_id": BATCH_ID,
        "retry_number": NORMALIZED_INPUT_RETRY_VERSION,
        "agent_id": AGENT_ID,
        "logical_output_key": {
            "article_slug": binding.source.article_slug,
            "image_id": binding.source.image["image_id"],
            "model_id": binding.model_id,
        },
        "primary_attempt": primary,
        "retry_attempt": {
            "retry_key": binding.retry_key,
            "batch_id": binding.retry_batch_id,
            "provider_run_id": binding.retry_provider_run_id,
            "lite_run_id": binding.source.planning_run_id,
            "model_id": binding.model_id,
            "source_path": binding.source.image["source_path"],
            "source_sha256": normalized["sha256"],
            "source_url": normalized["url"],
            "prompt_path": binding.prompt_rel.as_posix(),
            "run_path": binding.run_rel.as_posix(),
            "video_path": binding.video_rel.as_posix(),
            "generation_manifest_path": binding.manifest_rel.as_posix(),
            "request": retry_request,
            "request_sha256": retry_request_sha256,
            "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
        },
        "source_transform": _normalized_input_source_transform(
            binding,
            asset,
            asset_sha256,
            request_delta,
        ),
        "cost": aggregate_cost,
        "policy": _normalized_input_retry_policy(binding),
    }


def _normalized_input_supersede_policy() -> dict[str, Any]:
    target = NORMALIZED_INPUT_SUPERSEDE_TARGET
    return {
        "explicit_operator_command_required": True,
        "operator_authorized_active_job": True,
        "automatic_retry": False,
        "maximum_new_paid_submissions": 1,
        "retry2_forbidden": True,
        "one_off_allowlist": {
            "article_slug": target["article_slug"],
            "image_id": target["image_id"],
            "model_id": target["model_id"],
            "normalized_retry_provider_run_id": target[
                "normalized_retry_provider_run_id"
            ],
            "active_provider_job_id": target["active_provider_job_id"],
        },
        "duplicate_submission_risk_acknowledged": True,
        "duplicate_billing_risk_acknowledged": True,
        "same_verified_lite_result": True,
        "same_normalized_source": True,
        "same_prompt": True,
        "same_model": True,
        "same_route": True,
        "same_seed": True,
        "same_request": True,
        "fallback": False,
        "route_discovery": False,
        "primary_receipt_immutable": True,
        "normalized_retry_envelope_immutable": True,
        "superseded_receipt_immutable": True,
    }


def _normalized_input_supersede_envelope_document(
    binding: NormalizedInputSupersedeBinding,
    normalized_envelope: dict[str, Any],
    active_run: dict[str, Any],
    active_run_sha256: str,
    aggregate_cost: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Freeze the exact active retry and a byte-identical successor request."""

    normalized = _require_normalized_input_supersede_target(
        binding.source,
        binding.model_id,
    )
    retry = normalized_envelope.get("retry_attempt")
    transform = normalized_envelope.get("source_transform")
    if (
        not isinstance(retry, dict)
        or retry.get("provider_run_id") != binding.normalized_retry_provider_run_id
        or not isinstance(transform, dict)
        or active_run.get("provider_run_id")
        != binding.normalized_retry_provider_run_id
        or active_run.get("provider_job_id")
        != NORMALIZED_INPUT_SUPERSEDE_TARGET["active_provider_job_id"]
        or active_run.get("status") not in UNRESOLVED_PROVIDER_STATUSES
        or active_run.get("provider_may_be_active") is not True
        or not isinstance(active_run.get("submitted_at"), str)
        or not active_run.get("submitted_at")
        or active_run.get("completed_at") is not None
        or active_run.get("media") is not None
        or active_run.get("contract_check") is not None
        or active_run.get("request") != retry.get("request")
        or active_run.get("request_sha256") != retry.get("request_sha256")
        or active_run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        raise PipelineError(
            "Active normalized-input retry differs from its immutable envelope"
        )
    normalized_prompt_path = root / normalized.prompt_rel
    normalized_manifest_path = root / normalized.manifest_rel
    normalized_envelope_path = root / normalized.envelope_rel
    if (
        not normalized_prompt_path.is_file()
        or normalized_prompt_path.is_symlink()
        or not normalized_manifest_path.is_file()
        or normalized_manifest_path.is_symlink()
        or not normalized_envelope_path.is_file()
        or normalized_envelope_path.is_symlink()
    ):
        raise PipelineError("Normalized-input supersede evidence is incomplete")
    return {
        "schema_version": 1,
        "manifest_role": NORMALIZED_INPUT_SUPERSEDE_MANIFEST_ROLE,
        "ticket": TICKET,
        "primary_batch_id": BATCH_ID,
        "supersede_number": NORMALIZED_INPUT_SUPERSEDE_VERSION,
        "agent_id": AGENT_ID,
        "logical_output_key": {
            "article_slug": binding.source.article_slug,
            "image_id": binding.source.image["image_id"],
            "model_id": binding.model_id,
        },
        "normalized_retry": {
            "retry_key": normalized.retry_key,
            "batch_id": normalized.retry_batch_id,
            "provider_run_id": normalized.retry_provider_run_id,
            "envelope_path": normalized.envelope_rel.as_posix(),
            "envelope_sha256": sha256_file(normalized_envelope_path),
            "generation_manifest_path": normalized.manifest_rel.as_posix(),
            "generation_manifest_sha256": sha256_file(normalized_manifest_path),
        },
        "superseded_attempt": {
            "provider_run_id": normalized.retry_provider_run_id,
            "provider_job_id": active_run.get("provider_job_id"),
            "provider_task_id": active_run.get("provider_task_id"),
            "status": active_run.get("status"),
            "provider_may_be_active": active_run.get("provider_may_be_active"),
            "submitted_at": active_run.get("submitted_at"),
            "completed_at": active_run.get("completed_at"),
            "error": active_run.get("error"),
            "run_path": normalized.run_rel.as_posix(),
            "run_sha256": active_run_sha256,
            "prompt_path": normalized.prompt_rel.as_posix(),
            "prompt_sha256": sha256_file(normalized_prompt_path),
            "request": retry["request"],
            "request_sha256": retry["request_sha256"],
            "request_fingerprint_version": (
                transport.REQUEST_FINGERPRINT_VERSION
            ),
        },
        "superseding_attempt": {
            "supersede_key": binding.supersede_key,
            "batch_id": binding.supersede_batch_id,
            "provider_run_id": binding.supersede_provider_run_id,
            "lite_run_id": binding.source.planning_run_id,
            "model_id": binding.model_id,
            "source_path": binding.source.image["source_path"],
            "source_sha256": retry["source_sha256"],
            "source_url": retry["source_url"],
            "prompt_path": binding.prompt_rel.as_posix(),
            "run_path": binding.run_rel.as_posix(),
            "video_path": binding.video_rel.as_posix(),
            "generation_manifest_path": binding.manifest_rel.as_posix(),
            "request": retry["request"],
            "request_sha256": retry["request_sha256"],
            "request_fingerprint_version": (
                transport.REQUEST_FINGERPRINT_VERSION
            ),
        },
        "source_transform": transform,
        "cost": aggregate_cost,
        "policy": _normalized_input_supersede_policy(),
    }
def configure_normalized_input_retry_native(
    binding: NormalizedInputRetryBinding,
    asset: dict[str, Any],
    root: Path = ROOT,
) -> None:
    """Bind one isolated retry to the normalized URL and original Lite plan."""

    _contract_snapshot(root)
    _route_snapshot(root)
    source = binding.source
    model_id = binding.model_id
    normalized = asset.get("normalized") if isinstance(asset, dict) else None
    if not isinstance(normalized, dict):
        raise PipelineError("Normalized-input asset metadata is invalid")
    native.BATCH_ID = binding.retry_batch_id
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = (model_id,)
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = binding.manifest_rel
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = planning_provenance_verifier()
    native.SAMPLES = (source.sample,)
    native.WAN_SUBMIT_MODE = None
    native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()

    def provider_sample(entry: native.Entry) -> dict[str, Any]:
        if entry.sample.sample_id != source.sample_id or entry.model_id != model_id:
            raise PipelineError(
                f"Unknown normalized-input retry provider entry: {entry.run_id}"
            )
        image = source.image
        return {
            "sample_id": source.sample_id,
            "article_slug": source.article_slug,
            "image_id": image["image_id"],
            "image_number": image["image_id"],
            # Keep the logical/source provenance path original. Only the
            # provider URL and its byte fingerprint are normalized.
            "source_path": image["source_path"],
            "source_url": normalized["url"],
            "sha256": normalized["sha256"],
            "width": normalized["width"],
            "height": normalized["height"],
        }

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        if entry.provider_run_id != binding.retry_provider_run_id:
            raise PipelineError(
                f"Normalized-input retry identity changed: {entry.provider_run_id}"
            )
        return {
            "directory": workspace / binding.media_directory_rel,
            "prompt": workspace / binding.prompt_rel,
            "run": workspace / binding.run_rel,
            "video": workspace / binding.video_rel,
        }

    native.provider_sample = provider_sample
    native.artifact_paths = artifact_paths
    matrix = native.matrix()
    if (
        len(matrix) != 1
        or matrix[0].provider_run_id != binding.retry_provider_run_id
        or matrix[0].planning_run_id != source.planning_run_id
        or matrix[0].model_id != model_id
    ):
        raise PipelineError("Normalized-input retry native matrix identity changed")


def configure_normalized_input_supersede_native(
    binding: NormalizedInputSupersedeBinding,
    asset: dict[str, Any],
    root: Path = ROOT,
) -> None:
    """Bind the successor to the same frozen normalized source and route."""

    _contract_snapshot(root)
    _route_snapshot(root)
    source = binding.source
    model_id = binding.model_id
    _require_normalized_input_supersede_target(source, model_id)
    normalized = asset.get("normalized") if isinstance(asset, dict) else None
    if not isinstance(normalized, dict):
        raise PipelineError("Normalized-input supersede asset metadata is invalid")
    native.BATCH_ID = binding.supersede_batch_id
    native.PLANNING_BATCH_ID = PLANNING_BATCH_ID
    native.MODEL_IDS = (model_id,)
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = binding.manifest_rel
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = planning_provenance_verifier()
    native.SAMPLES = (source.sample,)
    native.WAN_SUBMIT_MODE = None
    native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()

    def provider_sample(entry: native.Entry) -> dict[str, Any]:
        if entry.sample.sample_id != source.sample_id or entry.model_id != model_id:
            raise PipelineError(
                f"Unknown normalized-input supersede entry: {entry.run_id}"
            )
        image = source.image
        return {
            "sample_id": source.sample_id,
            "article_slug": source.article_slug,
            "image_id": image["image_id"],
            "image_number": image["image_id"],
            "source_path": image["source_path"],
            "source_url": normalized["url"],
            "sha256": normalized["sha256"],
            "width": normalized["width"],
            "height": normalized["height"],
        }

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        if entry.provider_run_id != binding.supersede_provider_run_id:
            raise PipelineError(
                f"Normalized-input supersede identity changed: {entry.provider_run_id}"
            )
        return {
            "directory": workspace / binding.media_directory_rel,
            "prompt": workspace / binding.prompt_rel,
            "run": workspace / binding.run_rel,
            "video": workspace / binding.video_rel,
        }

    native.provider_sample = provider_sample
    native.artifact_paths = artifact_paths
    matrix = native.matrix()
    if (
        len(matrix) != 1
        or matrix[0].provider_run_id != binding.supersede_provider_run_id
        or matrix[0].planning_run_id != source.planning_run_id
        or matrix[0].model_id != model_id
    ):
        raise PipelineError("Normalized-input supersede native matrix identity changed")


def runner_command(root: Path, *parts: str) -> list[str]:
    return [sys.executable, str(root / "scripts/clipmaker_lite_runner.py"), *parts]


def _planning_state(source: Source, root: Path) -> str | None:
    directory = root / ARTIFACT_NAMESPACE / source.planning_run_id
    result_path = directory / "result.json"
    job_path = directory / "job.json"
    if result_path.is_file():
        summary = planning_provenance_summary(root, source.planning_run_id)
        if (
            summary.get("verified") is not True
            or summary.get("agent_id") != AGENT_ID
            or summary.get("contract_version") != planning_contract_version()
            or summary.get("models") != list(MODEL_IDS)
            or summary.get("source_image_sha256") != source.image["sha256"]
            or summary.get("article_context_sha256") != source.context_sha256
        ):
            raise PipelineError(
                f"Existing planning provenance differs: {source.planning_run_id}"
            )
        return "verified"
    if job_path.is_file():
        _job, selection, _directory = runner.validate_prepared_job(
            root, source.planning_run_id
        )
        selected_ids = [
            item.get("model_id") for item in selection.get("selected_models", [])
        ]
        if selected_ids != list(MODEL_IDS):
            raise PipelineError(
                f"Existing planning model set differs: {source.planning_run_id}"
            )
        return "prepared"
    return None


def select_sources(
    sources: Iterable[Source],
    *,
    article_slugs: Iterable[str] = (),
    planning_run_ids: Iterable[str] = (),
) -> tuple[Source, ...]:
    sources = tuple(sources)
    article_slugs = tuple(article_slugs)
    planning_run_ids = tuple(planning_run_ids)
    unknown_articles = set(article_slugs) - {
        source.article_slug for source in sources
    }
    unknown_runs = set(planning_run_ids) - {
        source.planning_run_id for source in sources
    }
    if unknown_articles:
        raise PipelineError(
            f"Unknown article slugs: {', '.join(sorted(unknown_articles))}"
        )
    if unknown_runs:
        raise PipelineError(
            f"Unknown planning run IDs: {', '.join(sorted(unknown_runs))}"
        )
    selected = tuple(
        source
        for source in sources
        if (not article_slugs or source.article_slug in article_slugs)
        and (not planning_run_ids or source.planning_run_id in planning_run_ids)
    )
    if not selected:
        raise PipelineError("Planning filters selected no image sources")
    return selected


def prepare_planning_runs(
    sources: Iterable[Source],
    *,
    root: Path = ROOT,
    dry_run: bool,
) -> dict[str, int]:
    counts = {"verified": 0, "prepared": 0, "pending": 0}
    for source in sources:
        state = _planning_state(source, root)
        if state is not None:
            counts[state] += 1
            print(
                f"planning prepare {source.planning_run_id} -> existing-{state}",
                flush=True,
            )
            continue
        if dry_run:
            counts["pending"] += 1
            print(
                f"planning prepare {source.planning_run_id} -> would-prepare",
                flush=True,
            )
            continue
        command = runner_command(
            root,
            "prepare",
            "--run-id",
            source.planning_run_id,
            "--image",
            source.image["source_path"],
            "--context",
            source.context_path,
            "--image-id",
            source.image["image_id"],
        )
        for model_id in MODEL_IDS:
            command.extend(("--model", model_id))
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode:
            raise PipelineError(
                f"Planning prepare failed for {source.planning_run_id}: "
                f"{transport.safe_error(completed.stderr or completed.stdout)}"
            )
        if _planning_state(source, root) != "prepared":
            raise PipelineError(
                f"Runner did not create a valid planning job: {source.planning_run_id}"
            )
        counts["prepared"] += 1
        print(f"planning prepare {source.planning_run_id} -> prepared", flush=True)
    return counts


def _run_one_planning(
    source: Source,
    *,
    root: Path,
    timeout: int,
    author_model: str | None,
) -> tuple[str, str, str | None]:
    try:
        if _planning_state(source, root) == "verified":
            return source.planning_run_id, "existing", None
    except Exception as exc:
        return source.planning_run_id, "failed", transport.safe_error(exc)
    command = runner_command(
        root,
        "run",
        "--run-id",
        source.planning_run_id,
        "--timeout",
        str(timeout),
        "--allow-external-processing",
    )
    if author_model:
        command.extend(("--author-model", author_model))
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return source.planning_run_id, "failed", f"planning timed out: {exc}"
    if completed.returncode:
        return (
            source.planning_run_id,
            "failed",
            transport.safe_error(completed.stderr or completed.stdout),
        )
    try:
        state = _planning_state(source, root)
    except Exception as exc:
        return source.planning_run_id, "failed", transport.safe_error(exc)
    if state != "verified":
        return source.planning_run_id, "failed", "planning provenance is not verified"
    return source.planning_run_id, "completed", None


def run_planning_runs(
    sources: Iterable[Source],
    *,
    root: Path,
    concurrency: int,
    timeout: int,
    dry_run: bool,
    allow_external_processing: bool,
    author_model: str | None,
) -> int:
    sources = tuple(sources)
    if dry_run:
        prepare_planning_runs(sources, root=root, dry_run=True)
        for source in sources:
            state = _planning_state(source, root)
            print(
                f"planning run {source.planning_run_id} -> "
                f"{'existing' if state == 'verified' else 'would-run'}",
                flush=True,
            )
        return 0
    if not allow_external_processing:
        raise PipelineError(
            "Real planning requires --allow-external-processing because the "
            "image and article context are sent to the isolated Codex execution"
        )
    failures: list[str] = []
    completed_count = 0
    with inventory_run_lock(root):
        prepare_planning_runs(sources, root=root, dry_run=False)
        with ThreadPoolExecutor(
            max_workers=concurrency,
            thread_name_prefix="promopages-10060-lite-plan",
        ) as executor:
            futures: dict[Future[tuple[str, str, str | None]], Source] = {
                executor.submit(
                    _run_one_planning,
                    source,
                    root=root,
                    timeout=timeout,
                    author_model=author_model,
                ): source
                for source in sources
            }
            for future in as_completed(futures):
                run_id, status, error = future.result()
                completed_count += 1
                print(
                    f"planning [{completed_count}/{len(sources)}] {run_id} -> "
                    f"{status}{f': {error}' if error else ''}",
                    flush=True,
                )
                if error:
                    failures.append(f"{run_id}: {error}")
    if failures:
        raise PipelineError(
            f"{len(failures)} planning run(s) failed: "
            + "; ".join(failures[:5])
        )
    return 0


def materialize_generation(
    sources: Iterable[Source],
    *,
    root: Path,
    dry_run: bool,
) -> int:
    sources = tuple(sources)
    configure_native(sources, root)
    expected = len(sources) * len(MODEL_IDS)
    if dry_run:
        for entry in native.matrix():
            job = native.load_lite_job(entry, root)
            native.provider_request_preview(
                native.provider_sample(entry), native.provider_prompt(job)
            )
        print(f"PASS: validated {expected} exact provider jobs; no files written")
        return 0
    rows = native.materialize(root)
    if len(rows) != expected:
        raise PipelineError(f"Expected {expected} provider jobs, got {len(rows)}")
    print(
        f"PASS: materialized {len(rows)} provider jobs from "
        f"{len(sources)} verified Lite plans"
    )
    return 0


UNRESOLVED_PROVIDER_STATUSES = {
    "submitting",
    "submitted",
    "running",
    "submit-unknown",
}


@dataclass(frozen=True)
class GenerationArticleState:
    """Network-free summary of the native receipts for one article."""

    article_slug: str
    accepted_outputs: int
    terminal_accounted_outputs: int
    provider_filtered_outputs: int
    expected_outputs: int
    unresolved_run_ids: tuple[str, ...]
    provider_unavailable_outputs: int = 0

    @property
    def complete(self) -> bool:
        return self.terminal_accounted_outputs == self.expected_outputs


def _native_run_receipt(
    entry: native.Entry,
    *,
    root: Path,
) -> tuple[dict[str, Any] | None, Path]:
    """Read and bind one native receipt without materializing or calling a provider."""

    path = native.artifact_paths(entry, root)["run"]
    if not path.is_file():
        return None, path
    receipt = read_json(path)
    if not isinstance(receipt, dict):
        raise PipelineError(f"Native run receipt is not an object: {path}")
    expected_identity = {
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "lite_run_id": entry.planning_run_id,
        "provider_run_id": entry.provider_run_id,
        "model_id": entry.model_id,
    }
    mismatches = [
        key
        for key, expected in expected_identity.items()
        if receipt.get(key) != expected
    ]
    if mismatches:
        raise PipelineError(
            f"Native run receipt identity differs ({', '.join(mismatches)}): {path}"
        )
    return receipt, path


def _native_receipt_is_unresolved(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") in UNRESOLVED_PROVIDER_STATUSES
        or receipt.get("provider_may_be_active") is True
    )


def _normalized_input_retry_envelope(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> tuple[NormalizedInputRetryBinding, dict[str, Any]] | None:
    """Validate one reserved normalized retry and all immutable bindings."""

    if _normalized_input_target(source, model_id) is None:
        return None
    binding = normalized_input_retry_binding(source, model_id)
    path = root / binding.envelope_rel
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise PipelineError(
            f"Normalized-input retry envelope is not a regular file: {path}"
        )
    envelope = read_json(path)
    if not isinstance(envelope, dict):
        raise PipelineError(f"Normalized-input retry envelope is invalid: {path}")
    primary = envelope.get("primary_attempt")
    retry = envelope.get("retry_attempt")
    transform = envelope.get("source_transform")
    expected_logical_key = {
        "article_slug": source.article_slug,
        "image_id": source.image["image_id"],
        "model_id": model_id,
    }
    asset, asset_sha256 = _validated_normalized_input_asset(binding, root=root)
    normalized = asset["normalized"]
    expected_retry_identity = {
        "retry_key": binding.retry_key,
        "batch_id": binding.retry_batch_id,
        "provider_run_id": binding.retry_provider_run_id,
        "lite_run_id": source.planning_run_id,
        "model_id": model_id,
        "source_path": source.image["source_path"],
        "source_sha256": normalized["sha256"],
        "source_url": normalized["url"],
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": binding.video_rel.as_posix(),
        "generation_manifest_path": binding.manifest_rel.as_posix(),
    }
    if (
        envelope.get("schema_version") != 1
        or envelope.get("manifest_role")
        != NORMALIZED_RETRY_MANIFEST_ROLE
        or envelope.get("ticket") != TICKET
        or envelope.get("primary_batch_id") != BATCH_ID
        or envelope.get("retry_number") != NORMALIZED_INPUT_RETRY_VERSION
        or envelope.get("agent_id") != AGENT_ID
        or envelope.get("logical_output_key") != expected_logical_key
        or envelope.get("policy") != _normalized_input_retry_policy(binding)
        or not isinstance(primary, dict)
        or primary.get("provider_run_id") != binding.primary_provider_run_id
        or primary.get("status") != "provider-failed"
        or primary.get("provider_may_be_active") is not False
        or not isinstance(retry, dict)
        or any(retry.get(key) != value for key, value in expected_retry_identity.items())
        or not isinstance(transform, dict)
    ):
        raise PipelineError(f"Normalized-input retry envelope binding differs: {path}")
    cost = envelope.get("cost")
    if not isinstance(cost, dict):
        raise PipelineError(f"Normalized-input retry cost ledger is missing: {path}")
    try:
        operator_cap = Decimal(str(cost["operator_budget_cap_usd"]))
        hard_cap = Decimal(str(cost["hard_budget_cap_usd"]))
        maximum = Decimal(str(cost["maximum_estimated_cost_usd"]))
        accounting_cost = Decimal(
            str(cost["normalized_input_retry_accounting_cost_usd"])
        )
        normalized_count = int(cost["normalized_input_retry_reservations"])
        ambiguous_count = int(cost["ambiguous_submit_retry_reservations"])
        terminal_count = int(cost["terminal_retry_reservations"])
        total_count = int(cost["total_retry_reservations"])
        supersede_keys = (
            "normalized_input_supersede_version",
            "normalized_input_supersede_accounting_cost_usd",
            "normalized_input_supersede_reservations",
            "maximum_new_paid_submissions_per_superseded_output",
        )
        present_supersede_keys = tuple(key in cost for key in supersede_keys)
        if any(present_supersede_keys) and not all(present_supersede_keys):
            raise ValueError("partial normalized-input supersede ledger")
        if all(present_supersede_keys):
            supersede_version = int(cost[supersede_keys[0]])
            supersede_accounting_cost = Decimal(str(cost[supersede_keys[1]]))
            supersede_count = int(cost[supersede_keys[2]])
            supersede_max_per_output = int(cost[supersede_keys[3]])
        else:
            supersede_version = None
            supersede_accounting_cost = None
            supersede_count = 0
            supersede_max_per_output = None
    except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
        raise PipelineError(
            f"Normalized-input retry cost ledger is invalid: {path}"
        ) from exc
    supersede_documents = _known_normalized_input_supersede_envelopes(root)
    if supersede_count:
        supersede_state_valid = (
            supersede_version == NORMALIZED_INPUT_SUPERSEDE_VERSION
            and supersede_accounting_cost
            == NORMALIZED_INPUT_SUPERSEDE_ACCOUNTING_COST_USD
            and supersede_count == 1
            and supersede_max_per_output == 1
            and len(supersede_documents) == 1
        )
    else:
        # A retry envelope written before the supersede does not gain new
        # ledger fields retroactively. Once the supersede exists, its frozen
        # cost snapshot is the reservation boundary proving that this older
        # envelope was admitted first.
        supersede_state_valid = True
        if supersede_documents:
            boundary = supersede_documents[0].get("cost")
            if not isinstance(boundary, dict):
                supersede_state_valid = False
            else:
                try:
                    boundary_counts = (
                        int(boundary["terminal_retry_reservations"]),
                        int(boundary["ambiguous_submit_retry_reservations"]),
                        int(boundary["normalized_input_retry_reservations"]),
                    )
                    boundary_supersede_version = int(
                        boundary["normalized_input_supersede_version"]
                    )
                    boundary_supersede_cost = Decimal(
                        str(
                            boundary[
                                "normalized_input_supersede_accounting_cost_usd"
                            ]
                        )
                    )
                    boundary_supersede_count = int(
                        boundary["normalized_input_supersede_reservations"]
                    )
                except (InvalidOperation, KeyError, TypeError, ValueError):
                    supersede_state_valid = False
                else:
                    supersede_state_valid = (
                        boundary_supersede_version
                        == NORMALIZED_INPUT_SUPERSEDE_VERSION
                        and boundary_supersede_cost
                        == NORMALIZED_INPUT_SUPERSEDE_ACCOUNTING_COST_USD
                        and boundary_supersede_count == 1
                        and all(
                            value <= boundary_value
                            for value, boundary_value in zip(
                                (
                                    terminal_count,
                                    ambiguous_count,
                                    normalized_count,
                                ),
                                boundary_counts,
                            )
                        )
                    )
    if (
        accounting_cost != NORMALIZED_INPUT_RETRY_ACCOUNTING_COST_USD
        or normalized_count < 1
        or ambiguous_count < 0
        or terminal_count < 0
        or not supersede_state_valid
        or total_count
        != (
            normalized_count
            + ambiguous_count
            + terminal_count
            + supersede_count
        )
        or maximum > operator_cap
        or maximum > hard_cap
        or hard_cap
        != (
            HARD_BUDGET_CAP_USD
            if HARD_BUDGET_CAP_USD is not None
            else operator_cap
        )
    ):
        raise PipelineError(f"Normalized-input retry cost ledger differs: {path}")
    expected_request, expected_delta = _normalized_retry_request(
        primary.get("request"),
        model_id,
        asset["original"]["url"],
        normalized["url"],
    )
    expected_request_sha256 = transport.request_fingerprint(
        expected_request,
        {
            "source_path": source.image["source_path"],
            "sha256": normalized["sha256"],
        },
    )
    expected_transform = _normalized_input_source_transform(
        binding,
        asset,
        asset_sha256,
        expected_delta,
    )
    if (
        retry.get("request") != expected_request
        or retry.get("request_sha256") != expected_request_sha256
        or retry.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
        or transform != expected_transform
    ):
        raise PipelineError(
            f"Normalized-input request delta differs after reservation: {path}"
        )
    primary_paths = primary_artifact_paths(source, model_id, root)
    if (
        not primary_paths["run"].is_file()
        or primary_paths["run"].is_symlink()
        or sha256_file(primary_paths["run"]) != primary.get("run_sha256")
        or not primary_paths["prompt"].is_file()
        or primary_paths["prompt"].is_symlink()
        or sha256_file(primary_paths["prompt"]) != primary.get("prompt_sha256")
        or primary_paths["video"].exists()
    ):
        raise PipelineError(
            "Primary normalized-input evidence changed after retry reservation: "
            f"{binding.primary_provider_run_id}"
        )
    return binding, envelope


def _active_normalized_input_retry_evidence(
    source: Source,
    model_id: str,
    normalized_envelope: dict[str, Any],
    *,
    root: Path,
) -> tuple[dict[str, Any], str]:
    """Validate the exact still-active receipt the operator chose to ignore."""

    normalized = _require_normalized_input_supersede_target(source, model_id)
    run_path = root / normalized.run_rel
    prompt_path = root / normalized.prompt_rel
    video_path = root / normalized.video_rel
    if (
        not run_path.is_file()
        or run_path.is_symlink()
        or not prompt_path.is_file()
        or prompt_path.is_symlink()
        or video_path.exists()
    ):
        raise PipelineError(
            "The authorized normalized-input retry no longer has exact active evidence"
        )
    run = read_json(run_path)
    retry = normalized_envelope.get("retry_attempt")
    primary = normalized_envelope.get("primary_attempt")
    if not isinstance(run, dict) or not isinstance(retry, dict) or not isinstance(primary, dict):
        raise PipelineError("Active normalized-input retry evidence is invalid")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": normalized.retry_batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": normalized.retry_provider_run_id,
        "model_id": model_id,
        "adapter": ROUTE_IDENTITIES[model_id][0],
    }
    if any(run.get(key) != value for key, value in expected_identity.items()):
        raise PipelineError("Active normalized-input retry identity differs")
    if (
        run.get("provider_job_id")
        != NORMALIZED_INPUT_SUPERSEDE_TARGET["active_provider_job_id"]
        or run.get("status") not in UNRESOLVED_PROVIDER_STATUSES
        or run.get("provider_may_be_active") is not True
        or not isinstance(run.get("submitted_at"), str)
        or not run.get("submitted_at")
        or run.get("completed_at") is not None
        or run.get("media") is not None
        or run.get("contract_check") is not None
        or run.get("request") != retry.get("request")
        or run.get("request_sha256") != retry.get("request_sha256")
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        raise PipelineError(
            "Supersede requires the exact allowlisted active normalized-input job"
        )
    primary_prompt_path = root / primary["prompt_path"]
    if not primary_prompt_path.is_file() or primary_prompt_path.is_symlink():
        raise PipelineError("Primary normalized-input prompt evidence is missing")
    primary_prompt = read_json(primary_prompt_path)
    retry_prompt = read_json(prompt_path)
    shared_prompt_fields = (
        "ticket",
        "agent_id",
        "lite_run_id",
        "model_id",
        "source",
        "structured_intent",
        "prompt",
        "runtime",
        "lite_result",
    )
    if (
        not isinstance(primary_prompt, dict)
        or not isinstance(retry_prompt, dict)
        or any(
            retry_prompt.get(field) != primary_prompt.get(field)
            for field in shared_prompt_fields
        )
        or retry_prompt.get("batch_id") != normalized.retry_batch_id
        or retry_prompt.get("provider_run_id")
        != normalized.retry_provider_run_id
    ):
        raise PipelineError("Active normalized-input retry prompt differs")
    return run, sha256_file(run_path)


def _normalized_input_supersede_envelope(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> tuple[NormalizedInputSupersedeBinding, dict[str, Any]] | None:
    """Validate the single nested supersede reservation and immutable parent."""

    target = NORMALIZED_INPUT_SUPERSEDE_TARGET
    if (
        BATCH_ID != target["batch_id"]
        or source.article_slug != target["article_slug"]
        or source.image.get("image_id") != target["image_id"]
        or model_id != target["model_id"]
    ):
        return None
    binding = normalized_input_supersede_binding(source, model_id)
    path = root / binding.envelope_rel
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise PipelineError(
            f"Normalized-input supersede envelope is not a regular file: {path}"
        )
    document = read_json(path)
    normalized_loaded = _normalized_input_retry_envelope(
        source,
        model_id,
        root=root,
    )
    if normalized_loaded is None:
        raise PipelineError("Superseded normalized-input retry envelope is missing")
    _normalized_binding, normalized_envelope = normalized_loaded
    active_run, active_run_sha256 = _active_normalized_input_retry_evidence(
        source,
        model_id,
        normalized_envelope,
        root=root,
    )
    if not isinstance(document, dict):
        raise PipelineError(f"Normalized-input supersede envelope is invalid: {path}")
    cost = document.get("cost")
    if not isinstance(cost, dict):
        raise PipelineError(f"Normalized-input supersede cost ledger is missing: {path}")
    try:
        supersede_cost = Decimal(
            str(cost["normalized_input_supersede_accounting_cost_usd"])
        )
        supersede_count = int(cost["normalized_input_supersede_reservations"])
        maximum = Decimal(str(cost["maximum_estimated_cost_usd"]))
        operator_cap = Decimal(str(cost["operator_budget_cap_usd"]))
    except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
        raise PipelineError(
            f"Normalized-input supersede cost ledger is invalid: {path}"
        ) from exc
    if (
        supersede_cost != NORMALIZED_INPUT_SUPERSEDE_ACCOUNTING_COST_USD
        or supersede_count != 1
        or maximum > operator_cap
    ):
        raise PipelineError(f"Normalized-input supersede cost ledger differs: {path}")
    expected = _normalized_input_supersede_envelope_document(
        binding,
        normalized_envelope,
        active_run,
        active_run_sha256,
        cost,
        root=root,
    )
    if document != expected:
        raise PipelineError(f"Normalized-input supersede envelope differs: {path}")
    return binding, document


def _normalized_input_supersede_provider_record(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any] | None:
    """Select terminal media from the successor while retaining both attempts."""

    loaded = _normalized_input_supersede_envelope(source, model_id, root=root)
    if loaded is None:
        return None
    binding, envelope = loaded
    prompt_path = root / binding.prompt_rel
    run_path = root / binding.run_rel
    video_path = root / binding.video_rel
    if not prompt_path.is_file() or prompt_path.is_symlink():
        return None
    superseded = envelope["superseded_attempt"]
    old_prompt = read_json(root / superseded["prompt_path"])
    new_prompt = read_json(prompt_path)
    shared_prompt_fields = (
        "ticket",
        "agent_id",
        "lite_run_id",
        "model_id",
        "source",
        "structured_intent",
        "prompt",
        "runtime",
        "lite_result",
    )
    if (
        not isinstance(old_prompt, dict)
        or not isinstance(new_prompt, dict)
        or any(
            new_prompt.get(field) != old_prompt.get(field)
            for field in shared_prompt_fields
        )
        or new_prompt.get("batch_id") != binding.supersede_batch_id
        or new_prompt.get("provider_run_id") != binding.supersede_provider_run_id
    ):
        raise PipelineError("Normalized-input supersede changed the Lite prompt")
    if not run_path.is_file() or run_path.is_symlink():
        return None
    run = read_json(run_path)
    if not isinstance(run, dict):
        raise PipelineError(f"Normalized-input supersede receipt is invalid: {run_path}")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": binding.supersede_batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.supersede_provider_run_id,
        "model_id": model_id,
        "adapter": ROUTE_IDENTITIES[model_id][0],
    }
    if any(run.get(key) != value for key, value in expected_identity.items()):
        raise PipelineError(f"Normalized-input supersede receipt identity differs: {run_path}")
    if _native_receipt_is_unresolved(run):
        return None
    status = native.effective_run_status(run)
    check = run.get("contract_check")
    media_accepted = (
        status in {"succeeded", "verification-failed"}
        and run.get("provider_may_be_active") is False
        and video_path.is_file()
        and isinstance(run.get("media"), dict)
        and native.complete_media_is_accepted(
            status,
            check,
            allow_contract_warnings=True,
        )
    )
    exhausted = (
        run.get("status") == "provider-failed"
        and run.get("provider_may_be_active") is False
        and isinstance(run.get("provider_job_id"), str)
        and bool(run.get("provider_job_id"))
        and isinstance(run.get("completed_at"), str)
        and bool(run.get("completed_at"))
        and isinstance(run.get("error"), str)
        and bool(run.get("error"))
        and not video_path.exists()
        and run.get("media") is None
        and run.get("contract_check") is None
    )
    if not media_accepted and not exhausted:
        return None
    expected_attempt = envelope["superseding_attempt"]
    if (
        run.get("request") != expected_attempt["request"]
        or run.get("request_sha256") != expected_attempt["request_sha256"]
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        raise PipelineError("Normalized-input supersede request differs from envelope")

    def attempt_audit(attempt: dict[str, Any], *, current: bool) -> dict[str, Any]:
        return {
            "provider_run_id": attempt.get("provider_run_id"),
            "provider_job_id": attempt.get("provider_job_id"),
            "provider_task_id": attempt.get("provider_task_id"),
            "status": attempt.get("status"),
            "provider_may_be_active": attempt.get("provider_may_be_active"),
            "submitted_at": attempt.get("submitted_at"),
            "completed_at": attempt.get("completed_at"),
            "error": attempt.get("error"),
            "run_path": (
                binding.run_rel.as_posix() if current else attempt.get("run_path")
            ),
            "run_sha256": (
                sha256_file(run_path) if current else attempt.get("run_sha256")
            ),
            "prompt_path": (
                binding.prompt_rel.as_posix()
                if current
                else attempt.get("prompt_path")
            ),
            "prompt_sha256": (
                sha256_file(prompt_path)
                if current
                else attempt.get("prompt_sha256")
            ),
            "request_sha256": attempt.get("request_sha256"),
        }

    current_attempt = attempt_audit({**run}, current=True)
    superseded_attempt = attempt_audit(superseded, current=False)
    normalized_envelope_path = Path(envelope["normalized_retry"]["envelope_path"])
    normalized_envelope = read_json(root / normalized_envelope_path)
    primary = normalized_envelope["primary_attempt"]
    primary_attempt = {
        key: primary.get(key)
        for key in (
            "provider_run_id",
            "provider_job_id",
            "provider_task_id",
            "status",
            "recorded_status",
            "provider_may_be_active",
            "recorded_provider_may_be_active",
            "recorded_provider_job_id",
            "submitted_at",
            "completed_at",
            "provider_submit_time",
            "provider_scheduled_time",
            "provider_end_time",
            "error",
            "run_path",
            "run_sha256",
            "prompt_path",
            "prompt_sha256",
            "request_sha256",
        )
    }
    return {
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.supersede_provider_run_id,
        "sample_id": source.sample_id,
        "article_slug": source.article_slug,
        "source_path": source.image["source_path"],
        "model_id": model_id,
        "status": "provider-unavailable" if exhausted else status,
        "recorded_status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": None if exhausted else binding.video_rel.as_posix(),
        "media": None if exhausted else run.get("media"),
        "contract_check": None if exhausted else check,
        "error": run.get("error"),
        "retry_selection": {
            "retry_kind": "normalized-input",
            "retry_number": NORMALIZED_INPUT_RETRY_VERSION,
            "namespace": normalized_envelope_path.parent.as_posix(),
            "envelope_path": normalized_envelope_path.as_posix(),
            "envelope_sha256": envelope["normalized_retry"]["envelope_sha256"],
            "exhausted": False,
            "primary_attempt": primary_attempt,
            "retry_attempt": superseded_attempt,
            "source_transform": envelope["source_transform"],
            "supersede": {
                "version": NORMALIZED_INPUT_SUPERSEDE_VERSION,
                "namespace": binding.directory_rel.as_posix(),
                "envelope_path": binding.envelope_rel.as_posix(),
                "envelope_sha256": sha256_file(root / binding.envelope_rel),
                "exhausted": exhausted,
                "superseded_attempt": superseded_attempt,
                "superseding_attempt": current_attempt,
            },
        },
    }


def _normalized_input_retry_provider_record(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any] | None:
    """Select normalized retry media or terminal provider-unavailable audit."""

    supersede = _normalized_input_supersede_envelope(source, model_id, root=root)
    if supersede is not None:
        return _normalized_input_supersede_provider_record(
            source,
            model_id,
            root=root,
        )

    loaded = _normalized_input_retry_envelope(source, model_id, root=root)
    if loaded is None:
        return None
    binding, envelope = loaded
    primary = envelope["primary_attempt"]
    prompt_path = root / binding.prompt_rel
    run_path = root / binding.run_rel
    video_path = root / binding.video_rel
    if not prompt_path.is_file() or prompt_path.is_symlink():
        return None
    primary_prompt = read_json(root / primary["prompt_path"])
    retry_prompt = read_json(prompt_path)
    if not isinstance(primary_prompt, dict) or not isinstance(retry_prompt, dict):
        raise PipelineError(f"Normalized-input retry prompt is invalid: {prompt_path}")
    shared_prompt_fields = (
        "ticket",
        "agent_id",
        "lite_run_id",
        "model_id",
        "source",
        "structured_intent",
        "prompt",
        "runtime",
        "lite_result",
    )
    if any(
        retry_prompt.get(field) != primary_prompt.get(field)
        for field in shared_prompt_fields
    ) or retry_prompt.get("batch_id") != binding.retry_batch_id or retry_prompt.get(
        "provider_run_id"
    ) != binding.retry_provider_run_id:
        raise PipelineError(
            "Normalized-input retry changed the verified Lite prompt: "
            f"{prompt_path}"
        )
    if not run_path.is_file() or run_path.is_symlink():
        return None
    run = read_json(run_path)
    if not isinstance(run, dict):
        raise PipelineError(f"Normalized-input retry receipt is invalid: {run_path}")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": binding.retry_batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.retry_provider_run_id,
        "model_id": model_id,
        "adapter": ROUTE_IDENTITIES[model_id][0],
    }
    if any(run.get(key) != value for key, value in expected_identity.items()):
        raise PipelineError(f"Normalized-input retry receipt identity differs: {run_path}")
    if _native_receipt_is_unresolved(run):
        return None
    status = native.effective_run_status(run)
    check = run.get("contract_check")
    media_accepted = (
        status in {"succeeded", "verification-failed"}
        and run.get("provider_may_be_active") is False
        and video_path.is_file()
        and isinstance(run.get("media"), dict)
        and native.complete_media_is_accepted(
            status,
            check,
            allow_contract_warnings=True,
        )
    )
    retry_exhausted = (
        run.get("status") == "provider-failed"
        and run.get("provider_may_be_active") is False
        and isinstance(run.get("provider_job_id"), str)
        and bool(run.get("provider_job_id"))
        and isinstance(run.get("completed_at"), str)
        and bool(run.get("completed_at"))
        and isinstance(run.get("error"), str)
        and bool(run.get("error"))
        and not video_path.exists()
        and run.get("media") is None
        and run.get("contract_check") is None
    )
    if not media_accepted and not retry_exhausted:
        return None
    expected_retry = envelope["retry_attempt"]
    if (
        run.get("request") != expected_retry["request"]
        or run.get("request_sha256") != expected_retry["request_sha256"]
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
    ):
        raise PipelineError(
            f"Normalized-input retry request differs from envelope: {run_path}"
        )
    retry_attempt = {
        "provider_run_id": binding.retry_provider_run_id,
        "provider_job_id": run.get("provider_job_id"),
        "provider_task_id": run.get("provider_task_id"),
        "status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "submitted_at": run.get("submitted_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error"),
        "run_path": binding.run_rel.as_posix(),
        "run_sha256": sha256_file(run_path),
        "prompt_path": binding.prompt_rel.as_posix(),
        "prompt_sha256": sha256_file(prompt_path),
        "request_sha256": run.get("request_sha256"),
    }
    primary_attempt = {
        key: primary.get(key)
        for key in (
            "provider_run_id",
            "provider_job_id",
            "provider_task_id",
            "status",
            "recorded_status",
            "provider_may_be_active",
            "recorded_provider_may_be_active",
            "recorded_provider_job_id",
            "submitted_at",
            "completed_at",
            "provider_submit_time",
            "provider_scheduled_time",
            "provider_end_time",
            "error",
            "run_path",
            "run_sha256",
            "prompt_path",
            "prompt_sha256",
            "request_sha256",
        )
    }
    return {
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.retry_provider_run_id,
        "sample_id": source.sample_id,
        "article_slug": source.article_slug,
        "source_path": source.image["source_path"],
        "model_id": model_id,
        "status": "provider-unavailable" if retry_exhausted else status,
        "recorded_status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": None if retry_exhausted else binding.video_rel.as_posix(),
        "media": None if retry_exhausted else run.get("media"),
        "contract_check": None if retry_exhausted else check,
        "error": run.get("error"),
        "retry_selection": {
            "retry_kind": "normalized-input",
            "retry_number": NORMALIZED_INPUT_RETRY_VERSION,
            "namespace": binding.directory_rel.as_posix(),
            "envelope_path": binding.envelope_rel.as_posix(),
            "envelope_sha256": sha256_file(root / binding.envelope_rel),
            "exhausted": retry_exhausted,
            "primary_attempt": primary_attempt,
            "retry_attempt": retry_attempt,
            "source_transform": envelope["source_transform"],
        },
    }


def _terminal_retry_envelope(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> tuple[TerminalRetryBinding, dict[str, Any]] | None:
    """Read and validate an existing retry envelope without configuring native."""

    binding = terminal_retry_binding(source, model_id)
    path = root / binding.envelope_rel
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise PipelineError(f"Retry envelope is not a regular file: {path}")
    envelope = read_json(path)
    if not isinstance(envelope, dict):
        raise PipelineError(f"Retry envelope is not an object: {path}")
    primary = envelope.get("primary_attempt")
    retry = envelope.get("retry_attempt")
    expected_logical_key = {
        "article_slug": source.article_slug,
        "image_id": source.image["image_id"],
        "model_id": model_id,
    }
    expected_retry = {
        "retry_key": binding.retry_key,
        "batch_id": binding.retry_batch_id,
        "provider_run_id": binding.retry_provider_run_id,
        "lite_run_id": source.planning_run_id,
        "model_id": model_id,
        "source_path": source.image["source_path"],
        "source_sha256": source.image["sha256"],
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": binding.video_rel.as_posix(),
        "generation_manifest_path": binding.manifest_rel.as_posix(),
    }
    if (
        envelope.get("schema_version") != 1
        or envelope.get("manifest_role")
        != TERMINAL_RETRY_MANIFEST_ROLE
        or envelope.get("ticket") != TICKET
        or envelope.get("primary_batch_id") != BATCH_ID
        or envelope.get("retry_number") != TERMINAL_RETRY_VERSION
        or envelope.get("agent_id") != AGENT_ID
        or envelope.get("logical_output_key") != expected_logical_key
        or retry != expected_retry
        or not isinstance(primary, dict)
        or primary.get("provider_run_id") != binding.primary_provider_run_id
        or primary.get("status") != "provider-failed"
        or primary.get("provider_may_be_active") is not False
    ):
        raise PipelineError(f"Retry envelope binding differs: {path}")
    primary_paths = primary_artifact_paths(source, model_id, root)
    if (
        not primary_paths["run"].is_file()
        or primary_paths["run"].is_symlink()
        or sha256_file(primary_paths["run"]) != primary.get("run_sha256")
        or not primary_paths["prompt"].is_file()
        or primary_paths["prompt"].is_symlink()
        or sha256_file(primary_paths["prompt"]) != primary.get("prompt_sha256")
        or primary_paths["video"].exists()
    ):
        raise PipelineError(
            f"Primary terminal evidence changed after retry reservation: "
            f"{binding.primary_provider_run_id}"
        )
    current_primary_run = read_json(primary_paths["run"])
    if (
        not isinstance(current_primary_run, dict)
        or current_primary_run.get("request") != primary.get("request")
        or current_primary_run.get("request_sha256")
        != primary.get("request_sha256")
    ):
        raise PipelineError(
            f"Primary provider request changed after retry reservation: "
            f"{binding.primary_provider_run_id}"
        )
    return binding, envelope


def _terminal_retry_provider_record(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any] | None:
    """Return an accepted retry attempt in generation-manifest shape."""

    loaded = _terminal_retry_envelope(source, model_id, root=root)
    if loaded is None:
        return None
    binding, envelope = loaded
    prompt_path = root / binding.prompt_rel
    run_path = root / binding.run_rel
    video_path = root / binding.video_rel
    if not prompt_path.is_file() or prompt_path.is_symlink():
        return None
    primary = envelope["primary_attempt"]
    primary_prompt = read_json(root / primary["prompt_path"])
    retry_prompt = read_json(prompt_path)
    if not isinstance(primary_prompt, dict) or not isinstance(retry_prompt, dict):
        raise PipelineError(f"Retry prompt is invalid: {prompt_path}")
    shared_prompt_fields = (
        "ticket",
        "agent_id",
        "lite_run_id",
        "model_id",
        "source",
        "structured_intent",
        "prompt",
        "runtime",
        "lite_result",
    )
    if any(
        retry_prompt.get(field) != primary_prompt.get(field)
        for field in shared_prompt_fields
    ) or retry_prompt.get("batch_id") != binding.retry_batch_id or retry_prompt.get(
        "provider_run_id"
    ) != binding.retry_provider_run_id:
        raise PipelineError(
            f"Retry prompt is not the exact original verified Lite prompt: {prompt_path}"
        )
    if not run_path.is_file() or run_path.is_symlink():
        return None
    run = read_json(run_path)
    if not isinstance(run, dict):
        raise PipelineError(f"Retry receipt is not an object: {run_path}")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": binding.retry_batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.retry_provider_run_id,
        "model_id": model_id,
    }
    if any(run.get(key) != value for key, value in expected_identity.items()):
        raise PipelineError(f"Retry receipt identity differs: {run_path}")
    if _native_receipt_is_unresolved(run):
        return None
    status = native.effective_run_status(run)
    check = run.get("contract_check")
    media_accepted = (
        status in {"succeeded", "verification-failed"}
        and video_path.is_file()
        and isinstance(run.get("media"), dict)
        and native.complete_media_is_accepted(
            status,
            check,
            allow_contract_warnings=True,
        )
    )
    retry_exhausted = (
        run.get("status") == "provider-failed"
        and run.get("provider_may_be_active") is False
        and isinstance(run.get("provider_job_id"), str)
        and bool(run.get("provider_job_id"))
        and isinstance(run.get("completed_at"), str)
        and isinstance(run.get("error"), str)
        and bool(run.get("error"))
        and not video_path.exists()
        and run.get("media") is None
        and run.get("contract_check") is None
    )
    if not media_accepted and not retry_exhausted:
        return None
    if (
        run.get("request") != primary.get("request")
        or run.get("request_sha256") != primary.get("request_sha256")
    ):
        raise PipelineError(
            f"Retry provider request is not exactly the primary request: {run_path}"
        )
    reported_status = "provider-filtered" if retry_exhausted else status
    retry_attempt = {
        "provider_run_id": binding.retry_provider_run_id,
        "provider_job_id": run.get("provider_job_id"),
        "status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "submitted_at": run.get("submitted_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error"),
        "run_path": binding.run_rel.as_posix(),
        "run_sha256": sha256_file(run_path),
        "prompt_path": binding.prompt_rel.as_posix(),
        "prompt_sha256": sha256_file(prompt_path),
        "request_sha256": run.get("request_sha256"),
    }
    return {
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.retry_provider_run_id,
        "sample_id": source.sample_id,
        "article_slug": source.article_slug,
        "source_path": source.image["source_path"],
        "model_id": model_id,
        "status": reported_status,
        "recorded_status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": None if retry_exhausted else binding.video_rel.as_posix(),
        "media": None if retry_exhausted else run.get("media"),
        "contract_check": None if retry_exhausted else check,
        "error": run.get("error"),
        "retry_selection": {
            "retry_number": TERMINAL_RETRY_VERSION,
            "namespace": binding.directory_rel.as_posix(),
            "envelope_path": binding.envelope_rel.as_posix(),
            "exhausted": retry_exhausted,
            "primary_attempt": {
                key: primary.get(key)
                for key in (
                    "provider_run_id",
                    "provider_job_id",
                    "status",
                    "submitted_at",
                    "completed_at",
                    "error",
                    "run_path",
                    "run_sha256",
                    "prompt_path",
                    "prompt_sha256",
                    "request_sha256",
                )
            },
            "retry_attempt": retry_attempt,
        },
    }


def _ambiguous_submit_retry_envelope(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> tuple[AmbiguousSubmitRetryBinding, dict[str, Any]] | None:
    """Read and fully bind an existing ambiguous-submit retry reservation."""

    binding = ambiguous_submit_retry_binding(source, model_id)
    path = root / binding.envelope_rel
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise PipelineError(
            f"Ambiguous-submit retry envelope is not a regular file: {path}"
        )
    envelope = read_json(path)
    if not isinstance(envelope, dict):
        raise PipelineError(f"Ambiguous-submit retry envelope is not an object: {path}")
    primary = envelope.get("primary_attempt")
    retry = envelope.get("retry_attempt")
    expected_logical_key = {
        "article_slug": source.article_slug,
        "image_id": source.image["image_id"],
        "model_id": model_id,
    }
    expected_retry = {
        "retry_key": binding.retry_key,
        "batch_id": binding.retry_batch_id,
        "provider_run_id": binding.retry_provider_run_id,
        "lite_run_id": source.planning_run_id,
        "model_id": model_id,
        "source_path": source.image["source_path"],
        "source_sha256": source.image["sha256"],
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": binding.video_rel.as_posix(),
        "generation_manifest_path": binding.manifest_rel.as_posix(),
    }
    if (
        envelope.get("schema_version") != 1
        or envelope.get("manifest_role")
        != AMBIGUOUS_RETRY_MANIFEST_ROLE
        or envelope.get("ticket") != TICKET
        or envelope.get("primary_batch_id") != BATCH_ID
        or envelope.get("retry_number") != AMBIGUOUS_SUBMIT_RETRY_VERSION
        or envelope.get("agent_id") != AGENT_ID
        or envelope.get("logical_output_key") != expected_logical_key
        or retry != expected_retry
        or envelope.get("policy") != _ambiguous_submit_retry_policy()
        or not isinstance(primary, dict)
        or primary.get("provider_run_id") != binding.primary_provider_run_id
        or primary.get("status") != "submit-unknown"
        or primary.get("recorded_status") not in {"submitting", "submit-unknown"}
        or primary.get("outcome") != "unknown"
        or primary.get("outcome_unknown") is not True
        or primary.get("provider_may_be_active") is not True
        or primary.get("provider_job_id") is not None
        or primary.get("submitted_at") is not None
        or primary.get("completed_at") is not None
        or primary.get("adapter") != ROUTE_IDENTITIES[model_id][0]
        or not isinstance(primary.get("ambiguity_reason"), str)
        or not primary.get("ambiguity_reason")
    ):
        raise PipelineError(f"Ambiguous-submit retry envelope binding differs: {path}")
    cost = envelope.get("cost")
    if not isinstance(cost, dict):
        raise PipelineError(f"Ambiguous-submit retry cost ledger is missing: {path}")
    try:
        operator_cap = Decimal(str(cost["operator_budget_cap_usd"]))
        hard_cap = Decimal(str(cost["hard_budget_cap_usd"]))
        maximum = Decimal(str(cost["maximum_estimated_cost_usd"]))
        accounting_cost = Decimal(
            str(cost["ambiguous_submit_retry_accounting_cost_usd"])
        )
        ambiguous_count = int(cost["ambiguous_submit_retry_reservations"])
        terminal_count = int(cost["terminal_retry_reservations"])
        normalized_count = int(cost.get("normalized_input_retry_reservations", 0))
        total_count = int(cost["total_retry_reservations"])
    except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
        raise PipelineError(
            f"Ambiguous-submit retry cost ledger is invalid: {path}"
        ) from exc
    if (
        accounting_cost != AMBIGUOUS_SUBMIT_RETRY_ACCOUNTING_COST_USD
        or ambiguous_count < 1
        or terminal_count < 0
        or normalized_count < 0
        or total_count != ambiguous_count + terminal_count + normalized_count
        or maximum > operator_cap
        or maximum > hard_cap
        or hard_cap
        != (
            HARD_BUDGET_CAP_USD
            if HARD_BUDGET_CAP_USD is not None
            else operator_cap
        )
    ):
        raise PipelineError(f"Ambiguous-submit retry cost ledger differs: {path}")
    primary_paths = primary_artifact_paths(source, model_id, root)
    if (
        not primary_paths["run"].is_file()
        or primary_paths["run"].is_symlink()
        or not primary_paths["prompt"].is_file()
        or primary_paths["prompt"].is_symlink()
        or sha256_file(primary_paths["prompt"]) != primary.get("prompt_sha256")
        or primary_paths["video"].exists()
    ):
        raise PipelineError(
            "Primary ambiguous evidence changed after retry reservation: "
            f"{binding.primary_provider_run_id}"
        )
    current_primary = _ambiguous_primary_receipt_state(
        primary,
        primary_paths["run"],
    )
    current_primary_run = current_primary["receipt"]
    if (
        current_primary_run.get("provider_may_be_active") is not True
        or current_primary_run.get("request") != primary.get("request")
        or current_primary_run.get("request_sha256")
        != primary.get("request_sha256")
    ):
        raise PipelineError(
            "Primary ambiguous provider receipt changed after retry reservation: "
            f"{binding.primary_provider_run_id}"
        )
    return binding, envelope


AMBIGUOUS_PRIMARY_SCHEDULER_NORMALIZATION_ERROR = (
    "Previous submit outcome is unknown; automatic retry is blocked"
)


def _json_document_sha256(document: dict[str, Any]) -> str:
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ambiguous_primary_receipt_state(
    reserved_primary: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    """Validate an immutable primary or the one legacy scheduler normalization.

    The first real resume before scheduling exclusion was added changed only
    ``submitting`` to ``submit-unknown`` and attached the native guard message.
    Accept that exact, reconstructably bound transition without writing the
    primary receipt again. Any other drift remains fatal.
    """

    receipt = read_json(run_path)
    if not isinstance(receipt, dict):
        raise PipelineError(f"Primary ambiguous receipt is not an object: {run_path}")
    current_sha256 = sha256_file(run_path)
    reserved_sha256 = reserved_primary.get("run_sha256")
    if current_sha256 == reserved_sha256:
        if receipt.get("status") != reserved_primary.get("recorded_status"):
            raise PipelineError(
                f"Primary ambiguous receipt status differs: {run_path}"
            )
        return {
            "receipt": receipt,
            "run_sha256": current_sha256,
            "scheduler_normalized": False,
        }
    restored = dict(receipt)
    scheduler_normalized = (
        reserved_primary.get("recorded_status") == "submitting"
        and reserved_primary.get("error") is None
        and receipt.get("status") == "submit-unknown"
        and receipt.get("error")
        == AMBIGUOUS_PRIMARY_SCHEDULER_NORMALIZATION_ERROR
    )
    if scheduler_normalized:
        restored["status"] = "submitting"
        restored["error"] = None
        scheduler_normalized = (
            _json_document_sha256(restored) == reserved_sha256
        )
    if not scheduler_normalized:
        raise PipelineError(
            f"Primary ambiguous evidence changed after retry reservation: {run_path}"
        )
    return {
        "receipt": receipt,
        "run_sha256": current_sha256,
        "scheduler_normalized": True,
    }


def _ambiguous_submit_retry_provider_record(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any] | None:
    """Return terminal retry media or a strictly audited unavailable output."""

    loaded = _ambiguous_submit_retry_envelope(source, model_id, root=root)
    if loaded is None:
        return None
    binding, envelope = loaded
    primary = envelope["primary_attempt"]
    primary_state = _ambiguous_primary_receipt_state(
        primary,
        root / primary["run_path"],
    )
    current_primary_run = primary_state["receipt"]
    prompt_path = root / binding.prompt_rel
    run_path = root / binding.run_rel
    video_path = root / binding.video_rel
    if not prompt_path.is_file() or prompt_path.is_symlink():
        return None
    primary_prompt = read_json(root / primary["prompt_path"])
    retry_prompt = read_json(prompt_path)
    if not isinstance(primary_prompt, dict) or not isinstance(retry_prompt, dict):
        raise PipelineError(f"Ambiguous-submit retry prompt is invalid: {prompt_path}")
    shared_prompt_fields = (
        "ticket",
        "agent_id",
        "lite_run_id",
        "model_id",
        "source",
        "structured_intent",
        "prompt",
        "runtime",
        "lite_result",
    )
    if any(
        retry_prompt.get(field) != primary_prompt.get(field)
        for field in shared_prompt_fields
    ) or retry_prompt.get("batch_id") != binding.retry_batch_id or retry_prompt.get(
        "provider_run_id"
    ) != binding.retry_provider_run_id:
        raise PipelineError(
            "Ambiguous-submit retry prompt is not the exact original verified "
            f"Lite prompt: {prompt_path}"
        )
    if not run_path.is_file() or run_path.is_symlink():
        return None
    run = read_json(run_path)
    if not isinstance(run, dict):
        raise PipelineError(f"Ambiguous-submit retry receipt is not an object: {run_path}")
    expected_identity = {
        "ticket": TICKET,
        "batch_id": binding.retry_batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.retry_provider_run_id,
        "model_id": model_id,
        "adapter": ROUTE_IDENTITIES[model_id][0],
    }
    if any(run.get(key) != value for key, value in expected_identity.items()):
        raise PipelineError(f"Ambiguous-submit retry receipt identity differs: {run_path}")
    if _native_receipt_is_unresolved(run):
        return None
    status = native.effective_run_status(run)
    check = run.get("contract_check")
    media_accepted = (
        status in {"succeeded", "verification-failed"}
        and run.get("provider_may_be_active") is False
        and video_path.is_file()
        and isinstance(run.get("media"), dict)
        and native.complete_media_is_accepted(
            status,
            check,
            allow_contract_warnings=True,
        )
    )
    retry_exhausted = (
        run.get("status") == "provider-failed"
        and run.get("provider_may_be_active") is False
        and isinstance(run.get("provider_job_id"), str)
        and bool(run.get("provider_job_id"))
        and isinstance(run.get("submitted_at"), str)
        and bool(run.get("submitted_at"))
        and isinstance(run.get("completed_at"), str)
        and bool(run.get("completed_at"))
        and isinstance(run.get("error"), str)
        and bool(run.get("error"))
        and not video_path.exists()
        and run.get("media") is None
        and run.get("contract_check") is None
    )
    if not media_accepted and not retry_exhausted:
        return None
    if (
        run.get("request") != primary.get("request")
        or run.get("request_sha256") != primary.get("request_sha256")
    ):
        raise PipelineError(
            f"Ambiguous-submit retry request is not exactly the primary request: {run_path}"
        )
    reported_status = "provider-unavailable" if retry_exhausted else status
    retry_attempt = {
        "provider_run_id": binding.retry_provider_run_id,
        "provider_job_id": run.get("provider_job_id"),
        "status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "submitted_at": run.get("submitted_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error"),
        "run_path": binding.run_rel.as_posix(),
        "run_sha256": sha256_file(run_path),
        "prompt_path": binding.prompt_rel.as_posix(),
        "prompt_sha256": sha256_file(prompt_path),
        "request_sha256": run.get("request_sha256"),
    }
    primary_attempt = {
        key: primary.get(key)
        for key in (
            "provider_run_id",
            "provider_job_id",
            "status",
            "recorded_status",
            "outcome",
            "outcome_unknown",
            "ambiguity_reason",
            "provider_may_be_active",
            "submitted_at",
            "completed_at",
            "error",
            "run_path",
            "run_sha256",
            "prompt_path",
            "prompt_sha256",
            "request_sha256",
        )
    }
    primary_attempt.update(
        {
            # The envelope retains the original reservation hash. The final
            # audit points at the current evidence file and separately records
            # the one reconstructable legacy scheduler normalization, if any.
            "recorded_status": current_primary_run.get("status"),
            "error": current_primary_run.get("error"),
            "run_sha256": primary_state["run_sha256"],
            "reserved_recorded_status": primary.get("recorded_status"),
            "reserved_run_sha256": primary.get("run_sha256"),
            "scheduler_normalized_after_reservation": primary_state[
                "scheduler_normalized"
            ],
        }
    )
    return {
        "lite_run_id": source.planning_run_id,
        "provider_run_id": binding.retry_provider_run_id,
        "sample_id": source.sample_id,
        "article_slug": source.article_slug,
        "source_path": source.image["source_path"],
        "model_id": model_id,
        "status": reported_status,
        "recorded_status": run.get("status"),
        "provider_may_be_active": run.get("provider_may_be_active"),
        "prompt_path": binding.prompt_rel.as_posix(),
        "run_path": binding.run_rel.as_posix(),
        "video_path": None if retry_exhausted else binding.video_rel.as_posix(),
        "media": None if retry_exhausted else run.get("media"),
        "contract_check": None if retry_exhausted else check,
        "error": run.get("error"),
        "retry_selection": {
            "retry_kind": "ambiguous-submit",
            "retry_number": AMBIGUOUS_SUBMIT_RETRY_VERSION,
            "namespace": binding.directory_rel.as_posix(),
            "envelope_path": binding.envelope_rel.as_posix(),
            "envelope_sha256": sha256_file(root / binding.envelope_rel),
            "exhausted": retry_exhausted,
            "primary_outcome_unknown": True,
            "primary_attempt": primary_attempt,
            "retry_attempt": retry_attempt,
        },
    }


def _native_output_is_accepted(
    entry: native.Entry,
    receipt: dict[str, Any] | None,
    *,
    root: Path,
) -> bool:
    """Apply the native terminal-media acceptance policy without network I/O."""

    if receipt is None or _native_receipt_is_unresolved(receipt):
        return False
    paths = native.artifact_paths(entry, root)
    if not paths["video"].is_file() or not isinstance(receipt.get("media"), dict):
        return False
    status = native.effective_run_status(receipt)
    check = receipt.get("contract_check")
    return native.complete_media_is_accepted(
        status,
        check,
        # Existing raw MP4s with explicitly recorded contract deviations are
        # terminal experiment outputs; their warning remains in the receipt.
        allow_contract_warnings=True,
    )


def generation_article_states(
    sources: Iterable[Source],
    *,
    root: Path,
) -> tuple[GenerationArticleState, ...]:
    """Inspect every expected native receipt in configured article order."""

    sources = tuple(sources)
    article_order = tuple(dict.fromkeys(source.article_slug for source in sources))
    expected_by_article = {slug: 0 for slug in article_order}
    accepted_by_article = {slug: 0 for slug in article_order}
    accounted_by_article = {slug: 0 for slug in article_order}
    filtered_by_article = {slug: 0 for slug in article_order}
    unavailable_by_article = {slug: 0 for slug in article_order}
    unresolved_by_article: dict[str, list[str]] = {
        slug: [] for slug in article_order
    }
    for source in sources:
        for model_id in MODEL_IDS:
            entry = native.Entry(source.sample, model_id)
            expected_by_article[source.article_slug] += 1
            receipt, _path = _native_run_receipt(entry, root=root)
            primary_accepted = _native_output_is_accepted(entry, receipt, root=root)
            retry_record = _terminal_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            ambiguous_loaded = _ambiguous_submit_retry_envelope(
                source,
                model_id,
                root=root,
            )
            ambiguous_record = (
                _ambiguous_submit_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if ambiguous_loaded is not None
                else None
            )
            normalized_loaded = _normalized_input_retry_envelope(
                source,
                model_id,
                root=root,
            )
            normalized_record = (
                _normalized_input_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if normalized_loaded is not None
                else None
            )
            overlay_count = sum(
                candidate is not None
                for candidate in (
                    retry_record,
                    ambiguous_loaded,
                    normalized_loaded,
                )
            )
            if overlay_count > 1:
                raise PipelineError(
                    "A logical output cannot use conflicting retry namespaces: "
                    f"{entry.provider_run_id}"
                )
            if ambiguous_loaded is None and normalized_loaded is None:
                if receipt is not None and _native_receipt_is_unresolved(receipt):
                    unresolved_by_article[source.article_slug].append(entry.run_id)
            elif ambiguous_record is None and normalized_record is None:
                active_overlay = ambiguous_loaded or normalized_loaded
                assert active_overlay is not None
                overlay_binding, _envelope = active_overlay
                unresolved_by_article[source.article_slug].append(
                    overlay_binding.retry_provider_run_id
                )
            retry_accepted = (
                isinstance(retry_record, dict)
                and retry_record.get("status")
                in {"succeeded", "verification-failed"}
            )
            retry_filtered = (
                isinstance(retry_record, dict)
                and retry_record.get("status") == "provider-filtered"
            )
            ambiguous_accepted = (
                isinstance(ambiguous_record, dict)
                and ambiguous_record.get("status")
                in {"succeeded", "verification-failed"}
            )
            ambiguous_unavailable = (
                isinstance(ambiguous_record, dict)
                and ambiguous_record.get("status") == "provider-unavailable"
            )
            normalized_accepted = (
                isinstance(normalized_record, dict)
                and normalized_record.get("status")
                in {"succeeded", "verification-failed"}
            )
            normalized_unavailable = (
                isinstance(normalized_record, dict)
                and normalized_record.get("status") == "provider-unavailable"
            )
            if (
                primary_accepted
                or retry_accepted
                or ambiguous_accepted
                or normalized_accepted
            ):
                accepted_by_article[source.article_slug] += 1
            if (
                primary_accepted
                or retry_accepted
                or retry_filtered
                or ambiguous_accepted
                or ambiguous_unavailable
                or normalized_accepted
                or normalized_unavailable
            ):
                accounted_by_article[source.article_slug] += 1
            if retry_filtered:
                filtered_by_article[source.article_slug] += 1
            if ambiguous_unavailable or normalized_unavailable:
                unavailable_by_article[source.article_slug] += 1
    return tuple(
        GenerationArticleState(
            article_slug=slug,
            accepted_outputs=accepted_by_article[slug],
            terminal_accounted_outputs=accounted_by_article[slug],
            provider_filtered_outputs=filtered_by_article[slug],
            expected_outputs=expected_by_article[slug],
            unresolved_run_ids=tuple(unresolved_by_article[slug]),
            provider_unavailable_outputs=unavailable_by_article[slug],
        )
        for slug in article_order
    )


def enforce_real_generation_article_order(
    sources: Iterable[Source],
    selected_sources: Iterable[Source],
    *,
    root: Path,
) -> GenerationArticleState:
    """Require one whole next-incomplete article and reject cross-article work."""

    sources = tuple(sources)
    selected_sources = tuple(selected_sources)
    selected_slugs = tuple(
        dict.fromkeys(source.article_slug for source in selected_sources)
    )
    if len(selected_slugs) != 1:
        raise PipelineError(
            "Real generation requires exactly one --article; "
            "an unfiltered or multi-article provider run is forbidden"
        )
    selected_slug = selected_slugs[0]
    complete_article_selection = tuple(
        source for source in sources if source.article_slug == selected_slug
    )
    if selected_sources != complete_article_selection:
        raise PipelineError(
            f"Real generation must select every image of exactly one article: "
            f"{selected_slug}"
        )

    states = generation_article_states(sources, root=root)
    next_incomplete = next((state for state in states if not state.complete), None)
    if next_incomplete is None:
        raise PipelineError("All available articles already have accepted complete outputs")
    if selected_slug != next_incomplete.article_slug:
        raise PipelineError(
            f"Next incomplete article is {next_incomplete.article_slug}; "
            f"refusing out-of-order article {selected_slug}"
        )

    current_index = states.index(next_incomplete)
    outside_prefix = [
        run_id
        for state in states[current_index + 1 :]
        for run_id in state.unresolved_run_ids
    ]
    if outside_prefix:
        raise PipelineError(
            "Unresolved provider jobs exist outside the current article prefix; "
            "refusing a run that the native coordinator could widen: "
            + ", ".join(outside_prefix[:5])
        )
    return next_incomplete


def generation_scheduling_plan(
    sources: Iterable[Source],
    selected_sources: Iterable[Source],
    *,
    root: Path,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Select primary workers while quarantining terminal retry overlays.

    Source-level article completeness remains unchanged. Only the exact model
    row represented by a terminal retry overlay is removed from provider
    scheduling. An ambiguous envelope without a terminal retry result blocks
    normal generation rather than reopening its unknown primary POST.
    """

    sources = tuple(sources)
    selected_sources = tuple(selected_sources)
    scheduled: list[str] = []
    exclusions: list[str] = []
    for source in sources:
        for model_id in MODEL_IDS:
            entry = native.Entry(source.sample, model_id)
            terminal_loaded = _terminal_retry_envelope(
                source,
                model_id,
                root=root,
            )
            terminal_record = (
                _terminal_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if terminal_loaded is not None
                else None
            )
            ambiguous_loaded = _ambiguous_submit_retry_envelope(
                source,
                model_id,
                root=root,
            )
            ambiguous_record = (
                _ambiguous_submit_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if ambiguous_loaded is not None
                else None
            )
            normalized_loaded = _normalized_input_retry_envelope(
                source,
                model_id,
                root=root,
            )
            normalized_record = (
                _normalized_input_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if normalized_loaded is not None
                else None
            )
            if sum(
                candidate is not None
                for candidate in (
                    terminal_loaded,
                    ambiguous_loaded,
                    normalized_loaded,
                )
            ) > 1:
                raise PipelineError(
                    "A logical output cannot have conflicting retry namespaces: "
                    f"{entry.provider_run_id}"
                )
            if terminal_loaded is not None and terminal_record is None:
                raise PipelineError(
                    "Terminal retry is not terminal; resume its explicit "
                    f"namespace before normal generation: {entry.provider_run_id}"
                )
            if ambiguous_loaded is not None:
                if ambiguous_record is None:
                    raise PipelineError(
                        "Ambiguous-submit retry is not terminal; resume its "
                        "explicit namespace before normal generation: "
                        f"{entry.provider_run_id}"
                    )
                if ambiguous_record.get("status") not in {
                    "succeeded",
                    "verification-failed",
                    "provider-unavailable",
                }:
                    raise PipelineError(
                        "Ambiguous-submit retry has a non-terminal scheduling "
                        f"status: {entry.provider_run_id}"
                    )
                # This exact primary remains audit evidence but must never be
                # fed to a worker or auto-added as an unresolved job again.
                exclusions.append(entry.run_id)
            if normalized_loaded is not None:
                if normalized_record is None:
                    raise PipelineError(
                        "Normalized-input retry is not terminal; resume its "
                        "explicit namespace before normal generation: "
                        f"{entry.provider_run_id}"
                    )
                if normalized_record.get("status") not in {
                    "succeeded",
                    "verification-failed",
                    "provider-unavailable",
                }:
                    raise PipelineError(
                        "Normalized-input retry has a non-terminal scheduling "
                        f"status: {entry.provider_run_id}"
                    )
                exclusions.append(entry.run_id)
            if source not in selected_sources:
                continue
            if (
                terminal_record is not None
                or ambiguous_record is not None
                or normalized_record is not None
            ):
                continue
            scheduled.append(entry.run_id)
    if not scheduled:
        raise PipelineError("Generation article has no executable provider rows")
    if len(scheduled) != len(set(scheduled)) or len(exclusions) != len(
        set(exclusions)
    ):
        raise PipelineError("Generation scheduling identities are not unique")
    return tuple(scheduled), tuple(exclusions)


@contextmanager
def native_scheduling_exclusions(run_ids: Iterable[str]):
    """Scope terminal exclusions to one native invocation and restore state."""

    exclusions = frozenset(run_ids)
    known = {entry.run_id for entry in native.matrix()}
    unknown = exclusions - known
    if unknown:
        raise PipelineError(
            "Unknown native scheduling exclusions: "
            + ", ".join(sorted(unknown))
        )
    original = native.SCHEDULING_EXCLUDED_RUN_IDS
    if original:
        raise PipelineError("Native scheduling exclusions leaked from a prior run")
    native.SCHEDULING_EXCLUDED_RUN_IDS = exclusions
    try:
        yield
    finally:
        native.SCHEDULING_EXCLUDED_RUN_IDS = original


def run_generation(
    sources: Iterable[Source],
    *,
    selected_sources: Iterable[Source] | None = None,
    root: Path,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
    fail_fast: bool,
) -> int:
    sources = tuple(sources)
    selected_sources = (
        sources if selected_sources is None else tuple(selected_sources)
    )
    if not selected_sources:
        raise PipelineError("Generation selection is empty")
    unknown_sources = [source for source in selected_sources if source not in sources]
    if unknown_sources:
        raise PipelineError("Generation selection contains unknown sources")
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real generation requires --allow-external-processing because "
            "images and prompts are sent to the three providers"
        )
    configure_native(sources, root)
    argv = [
        "run",
        "--wan22-concurrency",
        "1",
        "--wan27-concurrency",
        "3",
        "--veo31-concurrency",
        "3",
        "--timeout",
        str(timeout),
        "--poll-interval",
        str(poll_interval),
        "--dry-run" if dry_run else "--allow-external-processing",
    ]
    if fail_fast:
        argv.append("--fail-fast")
    # No model filter is passed: native.run_provider_pools starts the three
    # exact route queues together.  Succeeded jobs are skipped and submitted
    # identities are only polled/downloaded, which provides safe resume.
    if dry_run:
        scheduled_run_ids, scheduling_exclusions = generation_scheduling_plan(
            sources,
            selected_sources,
            root=root,
        )
        for run_id in scheduled_run_ids:
            argv.extend(["--run-id", run_id])
        with native_scheduling_exclusions(scheduling_exclusions):
            return native.main(argv, root)
    with inventory_run_lock(root):
        state = enforce_real_generation_article_order(
            sources,
            selected_sources,
            root=root,
        )
        print(
            f"generation article barrier {state.article_slug}: "
            f"accepted={state.accepted_outputs}, "
            f"provider-filtered={state.provider_filtered_outputs}, "
            f"provider-unavailable={state.provider_unavailable_outputs}, "
            f"terminal-accounted={state.terminal_accounted_outputs}/"
            f"{state.expected_outputs}",
            flush=True,
        )
        scheduled_run_ids, scheduling_exclusions = generation_scheduling_plan(
            sources,
            selected_sources,
            root=root,
        )
        for run_id in scheduled_run_ids:
            argv.extend(["--run-id", run_id])
        if scheduling_exclusions:
            print(
                "generation scheduling exclusions (terminal retry overlays): "
                + ", ".join(scheduling_exclusions),
                flush=True,
            )
        with native_scheduling_exclusions(scheduling_exclusions):
            return native.main(argv, root)


def _enforce_terminal_retry_order(
    sources: Iterable[Source],
    target_source: Source,
    target_model_id: str,
    *,
    root: Path,
) -> None:
    """Admit only the first unresolved logical output of the current article."""

    sources = tuple(sources)
    states = generation_article_states(sources, root=root)
    next_incomplete = next((state for state in states if not state.complete), None)
    if next_incomplete is None:
        raise PipelineError("All available articles already have accepted outputs")
    if target_source.article_slug != next_incomplete.article_slug:
        raise PipelineError(
            f"Next incomplete article is {next_incomplete.article_slug}; refusing "
            f"terminal retry in {target_source.article_slug}"
        )
    unresolved: list[str] = []
    first_incomplete: tuple[Source, str] | None = None
    for source in sources:
        for model_id in MODEL_IDS:
            entry = native.Entry(source.sample, model_id)
            receipt, _path = _native_run_receipt(entry, root=root)
            ambiguous_loaded = _ambiguous_submit_retry_envelope(
                source,
                model_id,
                root=root,
            )
            ambiguous_record = (
                _ambiguous_submit_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if ambiguous_loaded is not None
                else None
            )
            normalized_loaded = _normalized_input_retry_envelope(
                source,
                model_id,
                root=root,
            )
            normalized_record = (
                _normalized_input_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if normalized_loaded is not None
                else None
            )
            if ambiguous_loaded is None and normalized_loaded is None:
                if receipt is not None and _native_receipt_is_unresolved(receipt):
                    unresolved.append(primary_provider_run_id(source, model_id))
            elif ambiguous_record is None and normalized_record is None:
                active_overlay = ambiguous_loaded or normalized_loaded
                assert active_overlay is not None
                unresolved.append(active_overlay[0].retry_provider_run_id)
            if source.article_slug != next_incomplete.article_slug:
                continue
            accepted = _native_output_is_accepted(entry, receipt, root=root) or (
                _terminal_retry_provider_record(source, model_id, root=root)
                is not None
            ) or (
                ambiguous_record is not None
            ) or (
                normalized_record is not None
            )
            if not accepted and first_incomplete is None:
                first_incomplete = (source, model_id)
    if unresolved:
        raise PipelineError(
            "Terminal retry is blocked while any primary provider identity is "
            "unresolved: " + ", ".join(unresolved[:5])
        )
    if first_incomplete != (target_source, target_model_id):
        label = (
            primary_provider_run_id(*first_incomplete)
            if first_incomplete is not None
            else "unknown"
        )
        raise PipelineError(
            "Terminal retries must preserve logical output order; first "
            f"incomplete output is {label}"
        )


def run_terminal_provider_retry(
    sources: Iterable[Source],
    inventory: dict[str, Any],
    *,
    primary_provider_run_id_value: str,
    root: Path,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
) -> int:
    """Create/resume one explicit retry-v1 attempt without touching primary."""

    sources = tuple(sources)
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real terminal retry requires --allow-external-processing because "
            "the exact original image and Lite prompt are sent to the same provider"
        )

    def execute() -> int:
        configure_native(sources, root)
        source, model_id = resolve_primary_retry_target(
            sources, primary_provider_run_id_value
        )
        binding = terminal_retry_binding(source, model_id)
        existing = _terminal_retry_envelope(source, model_id, root=root)
        ambiguous_existing = _ambiguous_submit_retry_envelope(
            source,
            model_id,
            root=root,
        )
        if ambiguous_existing is not None:
            raise PipelineError(
                "A logical output with an ambiguous-submit retry reservation "
                "cannot also receive a terminal retry"
            )
        if (
            _normalized_input_target(source, model_id) is not None
            and _normalized_input_retry_envelope(source, model_id, root=root)
            is not None
        ):
            raise PipelineError(
                "A logical output with a normalized-input retry reservation "
                "cannot also receive a terminal retry"
            )
        existing_retry_record = (
            _terminal_retry_provider_record(source, model_id, root=root)
            if existing is not None
            else None
        )
        if existing is None:
            _enforce_terminal_retry_order(
                sources,
                source,
                model_id,
                root=root,
            )
            primary = _primary_terminal_failure_evidence(
                source,
                model_id,
                root=root,
            )
            aggregate_cost = _aggregate_retry_cost(
                inventory,
                root=root,
                additional_terminal=1,
            )
            envelope = _terminal_retry_envelope_document(
                binding,
                primary,
                aggregate_cost,
            )
        else:
            _existing_binding, envelope = existing
            primary = envelope["primary_attempt"]
            aggregate_cost = _aggregate_retry_cost(
                inventory,
                root=root,
            )

        configure_terminal_retry_native(binding, root)
        entry = native.matrix()[0]
        job = native.load_lite_job(entry, root)
        sample = native.provider_sample(entry)
        prompt = native.provider_prompt(job)
        retry_request = native.provider_request_preview(sample, prompt)
        retry_request_sha256 = transport.request_fingerprint(
            retry_request, sample
        )
        if (
            retry_request != primary.get("request")
            or retry_request_sha256 != primary.get("request_sha256")
        ):
            raise PipelineError(
                "Retry-v1 request is not byte-semantically identical to the "
                "primary verified source/prompt/model request"
            )
        if dry_run:
            action = (
                "existing-exhausted-retry2-forbidden"
                if isinstance(existing_retry_record, dict)
                and existing_retry_record.get("status") == "provider-filtered"
                else ("existing" if existing is not None else "would-reserve")
            )
            print(
                f"PASS: terminal retry {binding.retry_provider_run_id} -> {action}; "
                f"aggregate maximum=${aggregate_cost['maximum_estimated_cost_usd']:.2f}; "
                "no files written and no provider call"
            )
            return 0

        if (
            isinstance(existing_retry_record, dict)
            and existing_retry_record.get("status") == "provider-filtered"
        ):
            raise PipelineError(
                f"Terminal retry-v1 is exhausted for "
                f"{binding.primary_provider_run_id}; retry2 is forbidden"
            )

        envelope_path = root / binding.envelope_rel
        if envelope_path.is_file():
            if read_json(envelope_path) != envelope:
                raise PipelineError(
                    f"Immutable terminal retry envelope differs: {envelope_path}"
                )
        else:
            if envelope_path.exists():
                raise PipelineError(
                    f"Retry envelope target is not a regular file: {envelope_path}"
                )
            transport.atomic_write_json(envelope_path, envelope)
        row = native.materialize_entry(entry, root)
        materialized_request = native.provider_request_preview(
            row["sample"], row["prompt"]
        )
        if materialized_request != primary["request"]:
            raise PipelineError(
                "Materialized retry request differs from the immutable primary request"
            )
        argv = [
            "run",
            "--run-id",
            binding.retry_provider_run_id,
            "--wan22-concurrency",
            "1",
            "--wan27-concurrency",
            "3",
            "--veo31-concurrency",
            "3",
            "--timeout",
            str(timeout),
            "--poll-interval",
            str(poll_interval),
            "--allow-external-processing",
        ]
        result = native.main(argv, root)
        if result == 0:
            selected = _terminal_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            if selected is None:
                raise PipelineError(
                    "Retry command returned success without accepted retry media"
                )
        return result

    if dry_run:
        return execute()
    with inventory_run_lock(root):
        return execute()


def _enforce_ambiguous_submit_retry_order(
    sources: Iterable[Source],
    target_source: Source,
    target_model_id: str,
    *,
    root: Path,
) -> None:
    """Admit the first unknown primary POST of only the current article.

    A later unknown POST must be quarantined before a previously recorded
    terminal failure can be retried: terminal retries are intentionally
    blocked while *any* primary identity remains unresolved.  Ordering this
    guard by the first generally incomplete logical output would therefore
    deadlock an article when independent route pools observe an earlier
    provider failure and a later ambiguous submit in the same run.
    """

    sources = tuple(sources)
    if target_model_id not in MODEL_IDS:
        raise PipelineError(
            f"Ambiguous-submit retry model is unsupported: {target_model_id}"
        )
    states = generation_article_states(sources, root=root)
    next_incomplete = next((state for state in states if not state.complete), None)
    if next_incomplete is None:
        raise PipelineError("All available articles already have accepted outputs")
    if target_source.article_slug != next_incomplete.article_slug:
        raise PipelineError(
            f"Next incomplete article is {next_incomplete.article_slug}; refusing "
            f"ambiguous-submit retry in {target_source.article_slug}"
        )
    first_unknown_primary: tuple[Source, str] | None = None
    unsafe_outside_article: list[str] = []
    active_same_route: list[str] = []
    target_primary_id = primary_provider_run_id(target_source, target_model_id)
    for source in sources:
        for model_id in MODEL_IDS:
            entry = native.Entry(source.sample, model_id)
            receipt, _path = _native_run_receipt(entry, root=root)
            terminal_record = _terminal_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            ambiguous_loaded = _ambiguous_submit_retry_envelope(
                source,
                model_id,
                root=root,
            )
            ambiguous_record = (
                _ambiguous_submit_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if ambiguous_loaded is not None
                else None
            )
            normalized_loaded = _normalized_input_retry_envelope(
                source,
                model_id,
                root=root,
            )
            normalized_record = (
                _normalized_input_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if normalized_loaded is not None
                else None
            )
            unknown_primary = (
                receipt is not None
                and receipt.get("status") in {"submitting", "submit-unknown"}
                and receipt.get("provider_may_be_active") is True
                and receipt.get("provider_job_id") is None
                and terminal_record is None
                and ambiguous_loaded is None
                and normalized_loaded is None
            )
            if (
                model_id == target_model_id
                and entry.provider_run_id != target_primary_id
                and receipt is not None
                and _native_receipt_is_unresolved(receipt)
                and terminal_record is None
                and ambiguous_record is None
                and normalized_record is None
            ):
                active_same_route.append(entry.provider_run_id)
            if (
                source.article_slug == next_incomplete.article_slug
                and unknown_primary
                and first_unknown_primary is None
            ):
                first_unknown_primary = (source, model_id)
            if (
                source.article_slug != next_incomplete.article_slug
                and receipt is not None
                and _native_receipt_is_unresolved(receipt)
                and ambiguous_loaded is None
                and normalized_loaded is None
            ):
                unsafe_outside_article.append(entry.provider_run_id)
    if unsafe_outside_article:
        raise PipelineError(
            "Ambiguous-submit retry is blocked by unresolved provider identities "
            "outside the current article: "
            + ", ".join(unsafe_outside_article[:5])
        )
    expected_adapter = ROUTE_IDENTITIES[target_model_id][0]
    if (
        expected_adapter == "eliza-openrouter"
        and len(active_same_route) + 2 > ROUTE_CAPACITIES[target_model_id]
    ):
        raise PipelineError(
            f"Ambiguous-submit retry would exceed the active "
            f"{target_model_id} route capacity; resume these jobs first: "
            + ", ".join(active_same_route[:5])
        )
    if first_unknown_primary != (target_source, target_model_id):
        label = (
            primary_provider_run_id(*first_unknown_primary)
            if first_unknown_primary is not None
            else "unknown"
        )
        raise PipelineError(
            "Ambiguous-submit retry must preserve unknown primary POST order; "
            f"first unknown primary is {label}"
        )


def run_ambiguous_submit_retry(
    sources: Iterable[Source],
    inventory: dict[str, Any],
    *,
    primary_provider_run_id_value: str,
    root: Path,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
) -> int:
    """Create/resume the sole explicit retry of a quarantined provider POST."""

    sources = tuple(sources)
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real ambiguous-submit retry requires --allow-external-processing "
            "because the exact original image and Lite prompt are sent to the "
            "same provider route"
        )

    def execute() -> int:
        configure_native(sources, root)
        source, model_id = resolve_primary_retry_target(
            sources,
            primary_provider_run_id_value,
        )
        if _terminal_retry_envelope(source, model_id, root=root) is not None:
            raise PipelineError(
                "A logical output with a terminal retry reservation cannot also "
                "receive an ambiguous-submit retry"
            )
        if (
            _normalized_input_target(source, model_id) is not None
            and _normalized_input_retry_envelope(source, model_id, root=root)
            is not None
        ):
            raise PipelineError(
                "A logical output with a normalized-input retry reservation "
                "cannot also receive an ambiguous-submit retry"
            )
        binding = ambiguous_submit_retry_binding(source, model_id)
        existing = _ambiguous_submit_retry_envelope(
            source,
            model_id,
            root=root,
        )
        existing_retry_record = (
            _ambiguous_submit_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            if existing is not None
            else None
        )
        if existing is None:
            _enforce_ambiguous_submit_retry_order(
                sources,
                source,
                model_id,
                root=root,
            )
            primary = _primary_ambiguous_submit_evidence(
                source,
                model_id,
                root=root,
            )
            aggregate_cost = _aggregate_retry_cost(
                inventory,
                root=root,
                additional_ambiguous=1,
            )
            envelope = _ambiguous_submit_retry_envelope_document(
                binding,
                primary,
                aggregate_cost,
            )
        else:
            _existing_binding, envelope = existing
            primary = envelope["primary_attempt"]
            aggregate_cost = _aggregate_retry_cost(
                inventory,
                root=root,
            )

        configure_ambiguous_submit_retry_native(binding, root)
        entry = native.matrix()[0]
        job = native.load_lite_job(entry, root)
        sample = native.provider_sample(entry)
        prompt = native.provider_prompt(job)
        retry_request = native.provider_request_preview(sample, prompt)
        retry_request_sha256 = transport.request_fingerprint(
            retry_request,
            sample,
        )
        if (
            retry_request != primary.get("request")
            or retry_request_sha256 != primary.get("request_sha256")
        ):
            raise PipelineError(
                "Ambiguous-submit retry request is not byte-semantically "
                "identical to the primary verified source/prompt/model request"
            )
        retry_is_unavailable = (
            isinstance(existing_retry_record, dict)
            and existing_retry_record.get("status") == "provider-unavailable"
        )
        retry_has_media = (
            isinstance(existing_retry_record, dict)
            and existing_retry_record.get("status")
            in {"succeeded", "verification-failed"}
        )
        if dry_run:
            action = (
                "existing-exhausted-retry2-forbidden"
                if retry_is_unavailable
                else "existing-complete"
                if retry_has_media
                else "existing"
                if existing is not None
                else "would-reserve"
            )
            print(
                f"PASS: ambiguous-submit retry {binding.retry_provider_run_id} "
                f"-> {action}; aggregate maximum="
                f"${aggregate_cost['maximum_estimated_cost_usd']:.2f}; "
                "primary outcome remains unknown; no files written and no provider call"
            )
            return 0
        if retry_is_unavailable:
            raise PipelineError(
                f"Ambiguous-submit retry-v1 is exhausted for "
                f"{binding.primary_provider_run_id}; retry2 is forbidden"
            )
        if retry_has_media:
            print(
                f"PASS: ambiguous-submit retry already complete: "
                f"{binding.retry_provider_run_id}",
                flush=True,
            )
            return 0

        envelope_path = root / binding.envelope_rel
        if envelope_path.is_file():
            if read_json(envelope_path) != envelope:
                raise PipelineError(
                    f"Immutable ambiguous-submit retry envelope differs: {envelope_path}"
                )
        else:
            if envelope_path.exists():
                raise PipelineError(
                    "Ambiguous-submit retry envelope target is not a regular "
                    f"file: {envelope_path}"
                )
            transport.atomic_write_json(envelope_path, envelope)
        row = native.materialize_entry(entry, root)
        materialized_request = native.provider_request_preview(
            row["sample"],
            row["prompt"],
        )
        if materialized_request != primary["request"]:
            raise PipelineError(
                "Materialized ambiguous-submit retry request differs from the "
                "immutable primary request"
            )
        argv = [
            "run",
            "--run-id",
            binding.retry_provider_run_id,
            "--wan22-concurrency",
            "1",
            "--wan27-concurrency",
            "3",
            "--veo31-concurrency",
            "3",
            "--timeout",
            str(timeout),
            "--poll-interval",
            str(poll_interval),
            "--allow-external-processing",
        ]
        result = native.main(argv, root)
        if result == 0:
            selected = _ambiguous_submit_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            if (
                not isinstance(selected, dict)
                or selected.get("status")
                not in {"succeeded", "verification-failed"}
            ):
                raise PipelineError(
                    "Ambiguous-submit retry command returned success without "
                    "accepted retry media"
                )
        return result

    if dry_run:
        return execute()
    with inventory_run_lock(root):
        return execute()


def _effective_terminal_retry_overlay(
    source: Source,
    model_id: str,
    *,
    root: Path,
) -> dict[str, Any] | None:
    """Return the selected terminal overlay which retires a raw primary receipt.

    This intentionally mirrors normal scheduler semantics. A primary receipt
    may remain ``submit-unknown`` forever as immutable audit evidence after an
    explicit retry succeeds or exhausts; it must not continue consuming route
    capacity. An absent or nonterminal overlay returns ``None``, so a genuinely
    unresolved primary still fails closed in the caller.
    """

    terminal_loaded = _terminal_retry_envelope(source, model_id, root=root)
    ambiguous_loaded = _ambiguous_submit_retry_envelope(
        source,
        model_id,
        root=root,
    )
    normalized_loaded = _normalized_input_retry_envelope(
        source,
        model_id,
        root=root,
    )
    loaded = tuple(
        candidate
        for candidate in (terminal_loaded, ambiguous_loaded, normalized_loaded)
        if candidate is not None
    )
    if len(loaded) > 1:
        raise PipelineError(
            "A logical output has conflicting retry overlays while calculating "
            f"route capacity: {primary_provider_run_id(source, model_id)}"
        )
    if not loaded:
        return None
    if terminal_loaded is not None:
        record = _terminal_retry_provider_record(source, model_id, root=root)
    elif ambiguous_loaded is not None:
        record = _ambiguous_submit_retry_provider_record(
            source,
            model_id,
            root=root,
        )
    else:
        record = _normalized_input_retry_provider_record(
            source,
            model_id,
            root=root,
        )
    if record is None:
        return None
    allowed = {
        "succeeded",
        "verification-failed",
        "provider-filtered",
        "provider-unavailable",
    }
    if record.get("status") not in allowed:
        raise PipelineError(
            "Retry overlay has a nonterminal effective status while calculating "
            f"route capacity: {primary_provider_run_id(source, model_id)}"
        )
    return record


def _enforce_normalized_input_retry_order(
    sources: Iterable[Source],
    target_source: Source,
    target_model_id: str,
    *,
    root: Path,
) -> None:
    """Keep the remediation in the current article and respect route capacity."""

    states = generation_article_states(tuple(sources), root=root)
    next_incomplete = next((state for state in states if not state.complete), None)
    if next_incomplete is None:
        raise PipelineError("All available articles already have terminal outputs")
    if target_source.article_slug != next_incomplete.article_slug:
        raise PipelineError(
            f"Next incomplete article is {next_incomplete.article_slug}; refusing "
            f"normalized-input retry in {target_source.article_slug}"
        )
    active_same_route: list[str] = []
    for source in sources:
        entry = native.Entry(source.sample, target_model_id)
        receipt, _path = _native_run_receipt(entry, root=root)
        effective_overlay = _effective_terminal_retry_overlay(
            source,
            target_model_id,
            root=root,
        )
        if (
            entry.provider_run_id != primary_provider_run_id(
                target_source,
                target_model_id,
            )
            and effective_overlay is None
            and receipt is not None
            and _native_receipt_is_unresolved(receipt)
        ):
            active_same_route.append(entry.provider_run_id)
    if len(active_same_route) >= ROUTE_CAPACITIES[target_model_id]:
        raise PipelineError(
            f"Normalized-input retry would exceed the active "
            f"{target_model_id} route capacity; resume these jobs first: "
            + ", ".join(active_same_route[:5])
        )


def run_normalized_input_retry(
    sources: Iterable[Source],
    inventory: dict[str, Any],
    *,
    primary_provider_run_id_value: str,
    root: Path,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
) -> int:
    """Reserve/run the one frozen-input retry for an exact rejected primary."""

    sources = tuple(sources)
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real normalized-input retry requires --allow-external-processing "
            "because the frozen normalized image and Lite prompt are sent to "
            "the exact original provider route"
        )

    def execute() -> int:
        configure_native(sources, root)
        source, model_id = resolve_primary_retry_target(
            sources,
            primary_provider_run_id_value,
        )
        _require_normalized_input_target(source, model_id)
        if _terminal_retry_envelope(source, model_id, root=root) is not None:
            raise PipelineError(
                "A terminal retry reservation conflicts with normalized-input retry"
            )
        if (
            _ambiguous_submit_retry_envelope(source, model_id, root=root)
            is not None
        ):
            raise PipelineError(
                "An ambiguous-submit retry reservation conflicts with "
                "normalized-input retry"
            )
        binding = normalized_input_retry_binding(source, model_id)
        existing = _normalized_input_retry_envelope(
            source,
            model_id,
            root=root,
        )
        existing_record = (
            _normalized_input_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            if existing is not None
            else None
        )
        if existing is None:
            primary = _primary_normalized_input_failure_evidence(
                source,
                model_id,
                root=root,
            )
            aggregate_cost = _aggregate_retry_cost(
                inventory,
                root=root,
                additional_normalized=1,
            )
        else:
            _existing_binding, envelope = existing
            primary = envelope["primary_attempt"]
            aggregate_cost = _aggregate_retry_cost(inventory, root=root)
        normalized_url = _normalized_input_page_variant_url(source, root)
        _preview_request, request_delta = _normalized_retry_request(
            primary["request"],
            model_id,
            source.image["orig_url"],
            normalized_url,
        )
        exhausted = (
            isinstance(existing_record, dict)
            and existing_record.get("status") == "provider-unavailable"
        )
        complete = (
            isinstance(existing_record, dict)
            and existing_record.get("status")
            in {"succeeded", "verification-failed"}
        )
        if dry_run:
            action = (
                "existing-exhausted-retry2-forbidden"
                if exhausted
                else "existing-complete"
                if complete
                else "existing"
                if existing is not None
                else "would-preflight-and-reserve"
            )
            print(
                f"PASS: normalized-input retry {binding.retry_provider_run_id} "
                f"-> {action}; request delta={request_delta['json_pointer']}; "
                f"aggregate maximum="
                f"${aggregate_cost['maximum_estimated_cost_usd']:.2f}; "
                "no files written, no MDS fetch, and no provider call"
            )
            return 0
        if exhausted:
            raise PipelineError(
                f"Normalized-input retry-v1 is exhausted for "
                f"{binding.primary_provider_run_id}; retry2 is forbidden"
            )
        if complete:
            print(
                f"PASS: normalized-input retry already complete: "
                f"{binding.retry_provider_run_id}",
                flush=True,
            )
            return 0
        if existing is None:
            _enforce_normalized_input_retry_order(
                sources,
                source,
                model_id,
                root=root,
            )

        preflight = preflight_normalized_input_asset(normalized_url)
        candidate_asset = _normalized_input_asset_document(
            binding,
            preflight,
            root=root,
        )
        asset_path = root / binding.asset_metadata_rel
        if asset_path.is_file():
            asset, asset_sha256 = _validated_normalized_input_asset(
                binding,
                root=root,
            )
            if asset != candidate_asset:
                raise PipelineError(
                    "Remote /scale_1200 bytes changed after the normalized asset "
                    "was frozen"
                )
        else:
            if asset_path.exists():
                raise PipelineError(
                    f"Normalized asset metadata target is unsafe: {asset_path}"
                )
            transport.atomic_write_json(asset_path, candidate_asset)
            asset, asset_sha256 = _validated_normalized_input_asset(
                binding,
                root=root,
            )
        if existing is not None:
            envelope = existing[1]
        else:
            envelope = _normalized_input_retry_envelope_document(
                binding,
                primary,
                asset,
                asset_sha256,
                aggregate_cost,
            )
        configure_normalized_input_retry_native(binding, asset, root)
        entry = native.matrix()[0]
        job = native.load_lite_job(entry, root)
        sample = native.provider_sample(entry)
        prompt = native.provider_prompt(job)
        retry_request = native.provider_request_preview(sample, prompt)
        retry_request_sha256 = transport.request_fingerprint(retry_request, sample)
        expected_retry = envelope["retry_attempt"]
        if (
            retry_request != expected_retry["request"]
            or retry_request_sha256 != expected_retry["request_sha256"]
        ):
            raise PipelineError(
                "Normalized-input native request differs from the one-leaf "
                "immutable envelope"
            )
        envelope_path = root / binding.envelope_rel
        if envelope_path.is_file():
            if read_json(envelope_path) != envelope:
                raise PipelineError(
                    f"Immutable normalized-input retry envelope differs: {envelope_path}"
                )
        else:
            if envelope_path.exists():
                raise PipelineError(
                    f"Normalized-input retry target is unsafe: {envelope_path}"
                )
            transport.atomic_write_json(envelope_path, envelope)
        row = native.materialize_entry(entry, root)
        materialized_request = native.provider_request_preview(
            row["sample"],
            row["prompt"],
        )
        if materialized_request != expected_retry["request"]:
            raise PipelineError(
                "Materialized normalized-input request changed after reservation"
            )
        argv = [
            "run",
            "--run-id",
            binding.retry_provider_run_id,
            "--wan22-concurrency",
            "1",
            "--wan27-concurrency",
            "3",
            "--veo31-concurrency",
            "3",
            "--timeout",
            str(timeout),
            "--poll-interval",
            str(poll_interval),
            "--allow-external-processing",
        ]
        result = native.main(argv, root)
        if result == 0:
            selected = _normalized_input_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            if (
                not isinstance(selected, dict)
                or selected.get("status")
                not in {"succeeded", "verification-failed"}
            ):
                raise PipelineError(
                    "Normalized-input retry returned success without accepted media"
                )
        return result

    if dry_run:
        return execute()
    with inventory_run_lock(root):
        return execute()


def run_normalized_input_supersede(
    sources: Iterable[Source],
    inventory: dict[str, Any],
    *,
    normalized_retry_provider_run_id_value: str,
    operator_authorized: bool,
    root: Path,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
) -> int:
    """Create/resume the one paid successor to the exact active retry job."""

    sources = tuple(sources)
    if not dry_run and not operator_authorized:
        raise PipelineError(
            "Real normalized-input supersede requires "
            "--operator-authorized-active-job"
        )
    if not dry_run and not allow_external_processing:
        raise PipelineError(
            "Real normalized-input supersede requires --allow-external-processing"
        )

    def execute() -> int:
        source, model_id = resolve_normalized_input_supersede_target(
            sources,
            normalized_retry_provider_run_id_value,
        )
        configure_native(sources, root)
        binding = normalized_input_supersede_binding(source, model_id)
        normalized_loaded = _normalized_input_retry_envelope(
            source,
            model_id,
            root=root,
        )
        if normalized_loaded is None:
            raise PipelineError(
                "The exact normalized-input retry reservation is missing"
            )
        normalized_binding, normalized_envelope = normalized_loaded
        if (
            normalized_binding.retry_provider_run_id
            != normalized_retry_provider_run_id_value
        ):
            raise PipelineError("Normalized-input supersede parent identity differs")
        active_run, active_run_sha256 = _active_normalized_input_retry_evidence(
            source,
            model_id,
            normalized_envelope,
            root=root,
        )
        states = generation_article_states(sources, root=root)
        next_incomplete = next((state for state in states if not state.complete), None)
        if (
            next_incomplete is None
            or next_incomplete.article_slug != source.article_slug
        ):
            raise PipelineError(
                "Normalized-input supersede is outside the next incomplete article"
            )
        existing = _normalized_input_supersede_envelope(
            source,
            model_id,
            root=root,
        )
        if existing is None:
            other_active_same_route = []
            for candidate in sources:
                primary_entry = native.Entry(candidate.sample, model_id)
                primary_receipt, _path = _native_run_receipt(
                    primary_entry,
                    root=root,
                )
                if (
                    primary_receipt is not None
                    and _native_receipt_is_unresolved(primary_receipt)
                    and primary_entry.provider_run_id
                    != primary_provider_run_id(source, model_id)
                ):
                    other_active_same_route.append(
                        primary_entry.provider_run_id
                    )
            # The exact superseded job remains active and the new attempt takes
            # one additional slot; both count against the frozen Wan 2.7 pool.
            if len(other_active_same_route) + 2 > ROUTE_CAPACITIES[model_id]:
                raise PipelineError(
                    "Normalized-input supersede would exceed the exact route "
                    "capacity; resume other jobs first: "
                    + ", ".join(other_active_same_route[:5])
                )
            aggregate_cost = _aggregate_retry_cost(
                inventory,
                root=root,
                additional_normalized_supersede=1,
            )
            envelope = _normalized_input_supersede_envelope_document(
                binding,
                normalized_envelope,
                active_run,
                active_run_sha256,
                aggregate_cost,
                root=root,
            )
        else:
            existing_binding, envelope = existing
            if existing_binding != binding:
                raise PipelineError("Normalized-input supersede binding differs")
            aggregate_cost = _aggregate_retry_cost(inventory, root=root)
        if dry_run:
            action = "existing" if existing is not None else "would-reserve"
            print(
                f"PASS: normalized-input supersede "
                f"{binding.supersede_provider_run_id} -> {action}; "
                f"supersedes active job {active_run['provider_job_id']}; "
                f"aggregate maximum="
                f"${aggregate_cost['maximum_estimated_cost_usd']:.2f}; "
                "no files written and no provider call"
            )
            return 0

        selected = (
            _normalized_input_supersede_provider_record(
                source,
                model_id,
                root=root,
            )
            if existing is not None
            else None
        )
        if isinstance(selected, dict):
            print(
                f"PASS: normalized-input supersede already terminal: "
                f"{binding.supersede_provider_run_id} -> {selected['status']}",
                flush=True,
            )
            return 0

        asset, _asset_sha256 = _validated_normalized_input_asset(
            normalized_binding,
            root=root,
        )
        configure_normalized_input_supersede_native(binding, asset, root)
        entry = native.matrix()[0]
        job = native.load_lite_job(entry, root)
        sample = native.provider_sample(entry)
        prompt = native.provider_prompt(job)
        request = native.provider_request_preview(sample, prompt)
        expected = envelope["superseding_attempt"]
        if (
            request != expected["request"]
            or transport.request_fingerprint(request, sample)
            != expected["request_sha256"]
        ):
            raise PipelineError(
                "Normalized-input supersede is not byte-identical to the "
                "superseded provider request"
            )
        envelope_path = root / binding.envelope_rel
        if envelope_path.is_file():
            if read_json(envelope_path) != envelope:
                raise PipelineError(
                    f"Immutable normalized-input supersede differs: {envelope_path}"
                )
        else:
            if envelope_path.exists():
                raise PipelineError(
                    f"Normalized-input supersede target is unsafe: {envelope_path}"
                )
            transport.atomic_write_json(envelope_path, envelope)
        row = native.materialize_entry(entry, root)
        materialized_request = native.provider_request_preview(
            row["sample"],
            row["prompt"],
        )
        if materialized_request != expected["request"]:
            raise PipelineError(
                "Materialized normalized-input supersede request changed"
            )
        argv = [
            "run",
            "--run-id",
            binding.supersede_provider_run_id,
            "--wan22-concurrency",
            "1",
            "--wan27-concurrency",
            "3",
            "--veo31-concurrency",
            "3",
            "--timeout",
            str(timeout),
            "--poll-interval",
            str(poll_interval),
            "--allow-external-processing",
        ]
        result = native.main(argv, root)
        if result == 0:
            selected = _normalized_input_supersede_provider_record(
                source,
                model_id,
                root=root,
            )
            if (
                not isinstance(selected, dict)
                or selected.get("status")
                not in {
                    "succeeded",
                    "verification-failed",
                    "provider-unavailable",
                }
            ):
                raise PipelineError(
                    "Normalized-input supersede returned success without a "
                    "terminal audited result"
                )
        return result

    if dry_run:
        return execute()
    with inventory_run_lock(root):
        return execute()


def _planning_record(
    source: Source, root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    if _planning_state(source, root) != "verified":
        raise PipelineError(f"Planning run is not verified: {source.planning_run_id}")
    summary = planning_provenance_summary(root, source.planning_run_id)
    result_path = ARTIFACT_NAMESPACE / source.planning_run_id / "result.json"
    if summary.get("result_path") != result_path.as_posix():
        raise PipelineError(f"Unexpected planning result path: {source.planning_run_id}")
    result = read_json(root / result_path)
    models = result.get("models") if isinstance(result, dict) else None
    if (
        result.get("job_id") != source.planning_run_id
        or not isinstance(models, list)
        or [model.get("model_id") for model in models if isinstance(model, dict)]
        != list(MODEL_IDS)
    ):
        raise PipelineError(f"Planning result identity/model set differs: {source.planning_run_id}")
    return summary, result


def _output_record(
    *,
    article: Article,
    source: Source,
    model_id: str,
    model: dict[str, Any],
    provider: dict[str, Any],
) -> dict[str, Any]:
    retry = provider.get("retry_selection")
    if isinstance(retry, dict) and retry.get("retry_kind") == "normalized-input":
        if isinstance(retry.get("supersede"), dict):
            selected_attempt = (
                "normalized-input-superseding-attempt-v1-exhausted"
                if provider.get("status") == "provider-unavailable"
                else "normalized-input-superseding-attempt-v1"
            )
        else:
            selected_attempt = (
                "normalized-input-retry-v1-exhausted"
                if provider.get("status") == "provider-unavailable"
                else "normalized-input-retry-v1"
            )
    elif isinstance(retry, dict) and retry.get("retry_kind") == "ambiguous-submit":
        selected_attempt = (
            "ambiguous-submit-retry-v1-exhausted"
            if provider.get("status") == "provider-unavailable"
            else "ambiguous-submit-retry-v1"
        )
    elif isinstance(retry, dict):
        selected_attempt = (
            "terminal-retry-v1-exhausted"
            if provider.get("status") == "provider-filtered"
            else "terminal-retry-v1"
        )
    else:
        selected_attempt = "primary"
    return {
        "article_slug": article.slug,
        "image_id": source.image["image_id"],
        "source_path": source.image["source_path"],
        "sample_id": source.sample_id,
        "lite_run_id": source.planning_run_id,
        "provider_run_id": provider.get("provider_run_id"),
        "model_id": model_id,
        "scene_plan": model.get("scene_plan"),
        "positive_prompt": model.get("positive_prompt"),
        "negative_prompt": model.get("negative_prompt"),
        "status": provider.get("status"),
        "recorded_status": provider.get("recorded_status"),
        "prompt_path": provider.get("prompt_path"),
        "run_path": provider.get("run_path"),
        "video_path": provider.get("video_path"),
        "media": provider.get("media"),
        "contract_check": provider.get("contract_check"),
        "error": provider.get("error"),
        "selected_attempt": selected_attempt,
        "retry": retry,
    }


def final_output_acceptance_error(
    output: Any,
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> str | None:
    if not isinstance(output, dict):
        return "final output is not an object"
    label = output.get("provider_run_id") or "unknown output"
    status = output.get("status")
    if status not in {"succeeded", "verification-failed"}:
        return f"{label}: status {status!r} is not complete"
    video_path = output.get("video_path")
    if not isinstance(video_path, str) or not video_path:
        return f"{label}: video_path is missing"
    relative_video = Path(video_path)
    if relative_video.is_absolute() or ".." in relative_video.parts:
        return f"{label}: video_path is unsafe"
    if not (root / relative_video).is_file():
        return f"{label}: MP4 is missing"
    if not isinstance(output.get("media"), dict):
        return f"{label}: measured media is missing"
    check = output.get("contract_check")
    if not isinstance(check, dict):
        return f"{label}: media contract is missing"
    if status == "succeeded":
        return None if check.get("conforms") is True else f"{label}: succeeded output does not conform"
    warnings = check.get("warnings")
    if (
        not allow_contract_warnings
        or check.get("conforms") is not False
        or not isinstance(warnings, list)
        or not warnings
    ):
        return f"{label}: media-contract warnings were not accepted"
    return None


def final_output_terminal_error(
    output: Any,
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> str | None:
    """Accept media or one strictly audited exhausted retry namespace."""

    media_error = final_output_acceptance_error(
        output,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    if isinstance(output, dict) and output.get("status") == "provider-unavailable":
        normalized_retry = output.get("retry")
        if (
            isinstance(normalized_retry, dict)
            and normalized_retry.get("retry_kind") == "normalized-input"
        ):
            label = output.get("provider_run_id") or "unknown output"
            supersede = normalized_retry.get("supersede")
            if isinstance(supersede, dict):
                superseded = supersede.get("superseded_attempt")
                superseding = supersede.get("superseding_attempt")
                if (
                    output.get("recorded_status") != "provider-failed"
                    or output.get("selected_attempt")
                    != "normalized-input-superseding-attempt-v1-exhausted"
                    or output.get("video_path") is not None
                    or output.get("media") is not None
                    or output.get("contract_check") is not None
                    or not isinstance(output.get("error"), str)
                    or not output.get("error")
                    or supersede.get("version")
                    != NORMALIZED_INPUT_SUPERSEDE_VERSION
                    or supersede.get("exhausted") is not True
                    or normalized_retry.get("exhausted") is not False
                    or not isinstance(superseded, dict)
                    or not isinstance(superseding, dict)
                    or superseded.get("provider_run_id")
                    != NORMALIZED_INPUT_SUPERSEDE_TARGET[
                        "normalized_retry_provider_run_id"
                    ]
                    or superseded.get("provider_job_id")
                    != NORMALIZED_INPUT_SUPERSEDE_TARGET[
                        "active_provider_job_id"
                    ]
                    or superseded.get("status")
                    not in UNRESOLVED_PROVIDER_STATUSES
                    or superseded.get("provider_may_be_active") is not True
                    or superseding.get("provider_run_id")
                    != output.get("provider_run_id")
                    or superseding.get("status") != "provider-failed"
                    or superseding.get("provider_may_be_active") is not False
                    or superseding.get("error") != output.get("error")
                    or superseding.get("request_sha256")
                    != superseded.get("request_sha256")
                ):
                    return f"{label}: normalized supersede exhaustion audit is invalid"
                for attempt_name, attempt in (
                    ("superseded", superseded),
                    ("superseding", superseding),
                ):
                    for field in ("provider_run_id", "provider_job_id"):
                        if not isinstance(attempt.get(field), str) or not attempt.get(field):
                            return f"{label}: normalized {attempt_name} {field} is missing"
                    for field, digest_field in (
                        ("run_path", "run_sha256"),
                        ("prompt_path", "prompt_sha256"),
                    ):
                        value = attempt.get(field)
                        digest = attempt.get(digest_field)
                        artifact = Path(value) if isinstance(value, str) else None
                        if (
                            artifact is None
                            or artifact.is_absolute()
                            or ".." in artifact.parts
                            or not (root / artifact).is_file()
                            or not isinstance(digest, str)
                            or sha256_file(root / artifact) != digest
                        ):
                            return (
                                f"{label}: normalized {attempt_name} "
                                f"{field} evidence differs"
                            )
                for field, digest_field in (
                    ("envelope_path", "envelope_sha256"),
                ):
                    value = supersede.get(field)
                    digest = supersede.get(digest_field)
                    artifact = Path(value) if isinstance(value, str) else None
                    if (
                        artifact is None
                        or artifact.is_absolute()
                        or ".." in artifact.parts
                        or not (root / artifact).is_file()
                        or not isinstance(digest, str)
                        or sha256_file(root / artifact) != digest
                    ):
                        return f"{label}: normalized supersede envelope differs"
                return None
            normalized_target = _normalized_input_target_for_key(
                output.get("article_slug"),
                output.get("image_id"),
                output.get("model_id"),
            )
            if normalized_target is None:
                return f"{label}: normalized retry target is not allowlisted"
            if (
                output.get("recorded_status") != "provider-failed"
                or output.get("selected_attempt")
                != "normalized-input-retry-v1-exhausted"
                or output.get("video_path") is not None
                or output.get("media") is not None
                or output.get("contract_check") is not None
                or not isinstance(output.get("error"), str)
                or not output.get("error")
                or normalized_retry.get("retry_number")
                != NORMALIZED_INPUT_RETRY_VERSION
                or normalized_retry.get("exhausted") is not True
            ):
                return f"{label}: provider-unavailable normalized retry audit is invalid"
            primary = normalized_retry.get("primary_attempt")
            retry_attempt = normalized_retry.get("retry_attempt")
            transform = normalized_retry.get("source_transform")
            if (
                not isinstance(primary, dict)
                or not isinstance(retry_attempt, dict)
                or not isinstance(transform, dict)
            ):
                return f"{label}: normalized retry attempt/source audit is missing"
            if (
                primary.get("status") != "provider-failed"
                or primary.get("provider_may_be_active") is not False
                or retry_attempt.get("status") != "provider-failed"
                or retry_attempt.get("provider_may_be_active") is not False
                or retry_attempt.get("provider_run_id")
                != output.get("provider_run_id")
                or retry_attempt.get("provider_run_id")
                == primary.get("provider_run_id")
                or retry_attempt.get("error") != output.get("error")
                or primary.get("request_sha256")
                == retry_attempt.get("request_sha256")
            ):
                return f"{label}: normalized retry primary/retry audit differs"
            expected_pointer = {
                "alibaba/wan-2.2": "/input/image",
                "alibaba/wan-2.7": "/frame_images/0/image_url/url",
            }.get(output.get("model_id"))
            original = transform.get("original")
            normalized = transform.get("normalized")
            delta = transform.get("request_delta")
            expected_strategy = (
                normalized_target.replacement.strategy
                if normalized_target.replacement is not None
                else "frozen-page-variant"
            )
            if (
                transform.get("strategy") != expected_strategy
                or not isinstance(original, dict)
                or not isinstance(normalized, dict)
                or not isinstance(delta, dict)
                or delta.get("json_pointer") != expected_pointer
                or delta.get("from") != original.get("url")
                or delta.get("to") != normalized.get("url")
                or delta.get("changed_leaf_count") != 1
                or original.get("path") != output.get("source_path")
                or original.get("sha256") != normalized_target.source_sha256
                or not isinstance(original.get("bytes"), int)
                or not isinstance(normalized.get("bytes"), int)
                or not 0 < normalized["bytes"] <= NORMALIZED_INPUT_MAX_BYTES
                or not isinstance(normalized.get("width"), int)
                or normalized["width"] < NORMALIZED_INPUT_MIN_DIMENSION
                or not isinstance(normalized.get("height"), int)
                or normalized["height"] < NORMALIZED_INPUT_MIN_DIMENSION
            ):
                return f"{label}: normalized source/request delta audit differs"
            if normalized_target.failure_kind == "maximum-bytes":
                if original["bytes"] <= NORMALIZED_INPUT_MAX_BYTES:
                    return f"{label}: normalized oversize source audit differs"
            else:
                original_width = original.get("width")
                original_height = original.get("height")
                replacement = normalized_target.replacement
                if (
                    original["bytes"] > NORMALIZED_INPUT_MAX_BYTES
                    or not isinstance(original_width, int)
                    or not isinstance(original_height, int)
                    or min(original_width, original_height)
                    >= NORMALIZED_INPUT_MIN_DIMENSION
                    or replacement is None
                    or normalized.get("url") != replacement.url
                    or normalized.get("sha256") != replacement.sha256
                    or normalized.get("bytes") != replacement.byte_size
                    or normalized.get("width") != replacement.width
                    or normalized.get("height") != replacement.height
                    or normalized.get("format") != replacement.image_format
                    or normalized.get("delivery") != "repository-raw"
                    or normalized.get("repository_path")
                    != replacement.repository_path
                    or transform.get("preparation")
                    != {
                        "operation": "uniform-scale",
                        "target_height": replacement.height,
                        "resampler": "lanczos",
                        "crop": False,
                        "local_reencode": True,
                    }
                    or transform.get("minimum_provider_input_dimension")
                    != NORMALIZED_INPUT_MIN_DIMENSION
                ):
                    return f"{label}: normalized undersize source audit differs"
            for attempt_name, attempt in (
                ("primary", primary),
                ("retry", retry_attempt),
            ):
                for field in ("provider_run_id", "provider_job_id", "error"):
                    if not isinstance(attempt.get(field), str) or not attempt.get(field):
                        return f"{label}: normalized {attempt_name} {field} is missing"
                for field in ("run_sha256", "prompt_sha256", "request_sha256"):
                    value = attempt.get(field)
                    if (
                        not isinstance(value, str)
                        or len(value) != 64
                        or any(
                            character not in "0123456789abcdef"
                            for character in value
                        )
                    ):
                        return f"{label}: normalized {attempt_name} {field} is invalid"
                for field, digest_field in (
                    ("run_path", "run_sha256"),
                    ("prompt_path", "prompt_sha256"),
                ):
                    value = attempt.get(field)
                    artifact = Path(value) if isinstance(value, str) else None
                    if (
                        artifact is None
                        or artifact.is_absolute()
                        or ".." in artifact.parts
                        or not (root / artifact).is_file()
                        or sha256_file(root / artifact) != attempt[digest_field]
                    ):
                        return (
                            f"{label}: normalized {attempt_name} {field} "
                            "evidence differs"
                        )
            for field, digest_field in (
                ("envelope_path", "envelope_sha256"),
                ("metadata_path", "metadata_sha256"),
            ):
                if field.startswith("metadata"):
                    value = normalized.get(field)
                    digest = normalized.get(digest_field)
                else:
                    value = normalized_retry.get(field)
                    digest = normalized_retry.get(digest_field)
                artifact = Path(value) if isinstance(value, str) else None
                if (
                    artifact is None
                    or artifact.is_absolute()
                    or ".." in artifact.parts
                    or not (root / artifact).is_file()
                    or not isinstance(digest, str)
                    or sha256_file(root / artifact) != digest
                ):
                    return f"{label}: normalized {field} evidence differs"
            return None
    if isinstance(output, dict) and output.get("status") == "provider-unavailable":
        label = output.get("provider_run_id") or "unknown output"
        retry = output.get("retry")
        if (
            output.get("recorded_status") != "provider-failed"
            or output.get("selected_attempt")
            != "ambiguous-submit-retry-v1-exhausted"
            or output.get("video_path") is not None
            or output.get("media") is not None
            or output.get("contract_check") is not None
            or not isinstance(output.get("error"), str)
            or not output.get("error")
            or not isinstance(retry, dict)
            or retry.get("retry_kind") != "ambiguous-submit"
            or retry.get("retry_number") != AMBIGUOUS_SUBMIT_RETRY_VERSION
            or retry.get("exhausted") is not True
            or retry.get("primary_outcome_unknown") is not True
        ):
            return f"{label}: provider-unavailable ambiguous retry audit is invalid"
        primary = retry.get("primary_attempt")
        retry_attempt = retry.get("retry_attempt")
        if not isinstance(primary, dict) or not isinstance(retry_attempt, dict):
            return f"{label}: provider-unavailable attempt audit is missing"
        if (
            primary.get("status") != "submit-unknown"
            or primary.get("recorded_status")
            not in {"submitting", "submit-unknown"}
            or primary.get("outcome") != "unknown"
            or primary.get("outcome_unknown") is not True
            or primary.get("provider_may_be_active") is not True
            or primary.get("provider_job_id") is not None
            or primary.get("submitted_at") is not None
            or primary.get("completed_at") is not None
            or not isinstance(primary.get("ambiguity_reason"), str)
            or not primary.get("ambiguity_reason")
            or retry_attempt.get("status") != "provider-failed"
            or retry_attempt.get("provider_may_be_active") is not False
            or retry_attempt.get("provider_run_id") != output.get("provider_run_id")
            or retry_attempt.get("provider_run_id")
            == primary.get("provider_run_id")
            or retry_attempt.get("error") != output.get("error")
            or primary.get("request_sha256")
            != retry_attempt.get("request_sha256")
        ):
            return f"{label}: provider-unavailable primary/retry audit differs"
        for field in (
            "provider_run_id",
            "ambiguity_reason",
        ):
            if not isinstance(primary.get(field), str) or not primary.get(field):
                return f"{label}: ambiguous primary {field} is missing"
        for field in (
            "provider_run_id",
            "provider_job_id",
            "submitted_at",
            "completed_at",
            "error",
        ):
            if (
                not isinstance(retry_attempt.get(field), str)
                or not retry_attempt.get(field)
            ):
                return f"{label}: ambiguous retry {field} is missing"
        for attempt_name, attempt in (
            ("primary", primary),
            ("retry", retry_attempt),
        ):
            for field in ("run_sha256", "prompt_sha256", "request_sha256"):
                value = attempt.get(field)
                if (
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(
                        character not in "0123456789abcdef"
                        for character in value
                    )
                ):
                    return f"{label}: ambiguous {attempt_name} {field} is invalid"
            for field, digest_field in (
                ("run_path", "run_sha256"),
                ("prompt_path", "prompt_sha256"),
            ):
                value = attempt.get(field)
                if not isinstance(value, str) or not value:
                    return f"{label}: ambiguous {attempt_name} {field} is missing"
                artifact = Path(value)
                if artifact.is_absolute() or ".." in artifact.parts:
                    return f"{label}: ambiguous {attempt_name} {field} is unsafe"
                path = root / artifact
                if not path.is_file() or sha256_file(path) != attempt[digest_field]:
                    return f"{label}: ambiguous {attempt_name} {field} evidence differs"
        envelope_value = retry.get("envelope_path")
        envelope_digest = retry.get("envelope_sha256")
        if not isinstance(envelope_value, str) or not envelope_value:
            return f"{label}: ambiguous retry envelope_path is missing"
        envelope_path = Path(envelope_value)
        if (
            envelope_path.is_absolute()
            or ".." in envelope_path.parts
            or not (root / envelope_path).is_file()
            or not isinstance(envelope_digest, str)
            or sha256_file(root / envelope_path) != envelope_digest
        ):
            return f"{label}: ambiguous retry envelope evidence differs"
        return None
    if not isinstance(output, dict) or output.get("status") != "provider-filtered":
        return media_error
    label = output.get("provider_run_id") or "unknown output"
    retry = output.get("retry")
    if (
        output.get("recorded_status") != "provider-failed"
        or output.get("selected_attempt") != "terminal-retry-v1-exhausted"
        or output.get("video_path") is not None
        or output.get("media") is not None
        or output.get("contract_check") is not None
        or not isinstance(output.get("error"), str)
        or not output.get("error")
        or not isinstance(retry, dict)
        or retry.get("retry_number") != TERMINAL_RETRY_VERSION
        or retry.get("exhausted") is not True
    ):
        return f"{label}: provider-filtered retry exhaustion is invalid"
    primary = retry.get("primary_attempt")
    retry_attempt = retry.get("retry_attempt")
    if not isinstance(primary, dict) or not isinstance(retry_attempt, dict):
        return f"{label}: provider-filtered attempt audit is missing"
    if (
        primary.get("status") != "provider-failed"
        or retry_attempt.get("status") != "provider-failed"
        or retry_attempt.get("provider_may_be_active") is not False
        or retry_attempt.get("provider_run_id") != output.get("provider_run_id")
        or retry_attempt.get("error") != output.get("error")
        or primary.get("request_sha256") != retry_attempt.get("request_sha256")
    ):
        return f"{label}: provider-filtered primary/retry audit differs"
    for attempt_name, attempt in (
        ("primary", primary),
        ("retry", retry_attempt),
    ):
        for field in ("provider_run_id", "provider_job_id", "error"):
            if not isinstance(attempt.get(field), str) or not attempt.get(field):
                return f"{label}: {attempt_name} {field} is missing"
        for field in ("run_sha256", "prompt_sha256", "request_sha256"):
            value = attempt.get(field)
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                return f"{label}: {attempt_name} {field} is invalid"
        for field, digest_field in (
            ("run_path", "run_sha256"),
            ("prompt_path", "prompt_sha256"),
        ):
            value = attempt.get(field)
            if not isinstance(value, str) or not value:
                return f"{label}: {attempt_name} {field} is missing"
            artifact = Path(value)
            if artifact.is_absolute() or ".." in artifact.parts:
                return f"{label}: {attempt_name} {field} is unsafe"
            path = root / artifact
            if not path.is_file() or sha256_file(path) != attempt[digest_field]:
                return f"{label}: {attempt_name} {field} evidence differs"
    envelope_value = retry.get("envelope_path")
    if not isinstance(envelope_value, str) or not envelope_value:
        return f"{label}: retry envelope_path is missing"
    envelope_path = Path(envelope_value)
    if (
        envelope_path.is_absolute()
        or ".." in envelope_path.parts
        or not (root / envelope_path).is_file()
    ):
        return f"{label}: retry envelope_path is invalid"
    return None


def _acceptance_audit(
    outputs: Iterable[dict[str, Any]],
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> dict[str, int]:
    outputs = tuple(outputs)
    return {
        "accepted_output_count": sum(
            final_output_acceptance_error(
                output,
                root=root,
                allow_contract_warnings=allow_contract_warnings,
            )
            is None
            for output in outputs
        ),
        "conforming_output_count": sum(
            output.get("status") == "succeeded"
            and isinstance(output.get("contract_check"), dict)
            and output["contract_check"].get("conforms") is True
            for output in outputs
        ),
        "terminal_accounted_output_count": sum(
            final_output_terminal_error(
                output,
                root=root,
                allow_contract_warnings=allow_contract_warnings,
            )
            is None
            for output in outputs
        ),
        "provider_filtered_output_count": sum(
            output.get("status") == "provider-filtered" for output in outputs
        ),
        "provider_unavailable_output_count": sum(
            output.get("status") == "provider-unavailable" for output in outputs
        ),
    }


def _final_output_key(output: Any) -> tuple[str, str, str]:
    if not isinstance(output, dict):
        raise PipelineError("Final output is not an object")
    key = (
        output.get("article_slug"),
        output.get("image_id"),
        output.get("model_id"),
    )
    if not all(isinstance(value, str) and value for value in key):
        raise PipelineError(f"Final output key is invalid: {key}")
    return key


def _femibion_recovery_route_snapshot(root: Path) -> dict[str, Any]:
    path = root / ROUTES_REL
    routes = read_json(path)
    policy = routes.get("policy") if isinstance(routes, dict) else None
    models = routes.get("models") if isinstance(routes, dict) else None
    route = (
        models.get(FEMIBION_VEO_RECOVERY_MODEL_ID)
        if isinstance(models, dict)
        else None
    )
    if (
        not isinstance(policy, dict)
        or policy.get("resolution") != "exact-model-id"
        or policy.get("automatic_fallback") is not False
        or policy.get("normal_run_discovery") is not False
        or not isinstance(route, dict)
        or route.get("adapter") != "eliza-openrouter"
        or route.get("transport") != "eliza-video-jobs"
        or route.get("provider_key") != "google-vertex"
        or route.get("capacity") != 3
        or transport.route_for_model(FEMIBION_VEO_RECOVERY_MODEL_ID) != route
    ):
        raise PipelineError("Exact Femibion Veo recovery route changed")
    paths = route.get("paths")
    if not isinstance(paths, dict) or paths != {
        "submit": "/videos",
        "status_template": "/videos/{job_id}",
        "content_template": "/videos/{job_id}/content?index=0",
    }:
        raise PipelineError("Exact Femibion Veo recovery route paths changed")
    return {
        "registry_path": ROUTES_REL.as_posix(),
        "registry_sha256": sha256_file(path),
        "model_id": FEMIBION_VEO_RECOVERY_MODEL_ID,
        "adapter": route["adapter"],
        "transport": route["transport"],
        "provider_key": route["provider_key"],
        "capacity": route["capacity"],
        "paths": dict(paths),
        "automatic_fallback": False,
        "normal_run_discovery": False,
    }


def _femibion_recovery_contract_snapshot(root: Path) -> dict[str, Any]:
    snapshot = _contract_snapshot(root)
    path = root / CONTRACT_REL
    contract = read_json(path)
    models = contract.get("models") if isinstance(contract, dict) else None
    model = (
        models.get(FEMIBION_VEO_RECOVERY_MODEL_ID)
        if isinstance(models, dict)
        else None
    )
    runtime = model.get("runtime") if isinstance(model, dict) else None
    if (
        snapshot.get("contract_version") != REQUIRED_CONTRACT_VERSION
        or REQUIRED_CONTRACT_VERSION != "2.0.8"
        or not isinstance(runtime, dict)
        or runtime.get("duration_seconds") != 4
        or runtime.get("resolution") != "1080p"
        or runtime.get("aspect_ratios") != ["16:9", "9:16"]
        or runtime.get("generate_audio") is not False
        or runtime.get("frame_inputs") != ["first_frame"]
        or runtime.get("provider") != "google-vertex"
        or runtime.get("prompt_expansion")
        != {"parameter": "enhancePrompt", "value": True}
    ):
        raise PipelineError("Current Clipmaker Lite recovery contract changed")
    return {
        "path": CONTRACT_REL.as_posix(),
        "sha256": sha256_file(path),
        "contract_version": REQUIRED_CONTRACT_VERSION,
        "runtime": runtime,
    }


def _femibion_recovery_regular_path(
    root: Path,
    value: Any,
    *,
    label: str,
) -> tuple[Path, Path]:
    relative_path = _safe_workspace_relative(value, label=label)
    absolute_path = root / relative_path
    if not absolute_path.is_file() or absolute_path.is_symlink():
        raise PipelineError(f"{label} is missing or unsafe: {relative_path}")
    return relative_path, absolute_path


def _femibion_old_filtered_evidence(
    output: dict[str, Any],
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> dict[str, Any]:
    key = _final_output_key(output)
    expected_provider_run_id = FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
    terminal_error = final_output_terminal_error(
        output,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    retry = output.get("retry")
    retry_attempt = retry.get("retry_attempt") if isinstance(retry, dict) else None
    if (
        terminal_error is not None
        or output.get("status") != "provider-filtered"
        or output.get("recorded_status") != "provider-failed"
        or output.get("provider_run_id") != expected_provider_run_id
        or output.get("selected_attempt") != "terminal-retry-v1-exhausted"
        or not isinstance(retry, dict)
        or retry.get("retry_number") != TERMINAL_RETRY_VERSION
        or retry.get("exhausted") is not True
        or not isinstance(retry_attempt, dict)
        or retry_attempt.get("provider_run_id") != expected_provider_run_id
        or retry_attempt.get("status") != "provider-failed"
        or retry_attempt.get("provider_may_be_active") is not False
    ):
        raise PipelineError(
            f"Femibion recovery base is not exhausted provider-filtered: {key}"
        )
    run_rel, run_path = _femibion_recovery_regular_path(
        root,
        retry_attempt.get("run_path"),
        label="old filtered run receipt",
    )
    envelope_rel, envelope_path = _femibion_recovery_regular_path(
        root,
        retry.get("envelope_path"),
        label="old terminal retry envelope",
    )
    if sha256_file(run_path) != retry_attempt.get("run_sha256"):
        raise PipelineError(f"Old filtered run receipt digest differs: {key}")
    request_sha256 = retry_attempt.get("request_sha256")
    if (
        not isinstance(request_sha256, str)
        or len(request_sha256) != 64
        or any(character not in "0123456789abcdef" for character in request_sha256)
    ):
        raise PipelineError(f"Old filtered request digest is invalid: {key}")
    return {
        "provider_run_id": expected_provider_run_id,
        "provider_job_id": retry_attempt.get("provider_job_id"),
        "status": "provider-filtered",
        "request_sha256": request_sha256,
        "run_path": run_rel.as_posix(),
        "run_sha256": retry_attempt["run_sha256"],
        "retry_envelope_path": envelope_rel.as_posix(),
        "retry_envelope_sha256": sha256_file(envelope_path),
        "retry_v1_exhausted": True,
    }


def _femibion_recovery_planning_record(
    document: dict[str, Any],
    output: dict[str, Any],
    source: Source,
    *,
    root: Path,
) -> dict[str, Any]:
    run_id = output.get("lite_run_id")
    expected_run_id = f"{FEMIBION_VEO_RECOVERY_ID}-{source.sample_id}"
    planning = document.get("planning")
    matches = [
        record
        for record in planning
        if isinstance(record, dict) and record.get("planning_run_id") == run_id
    ] if isinstance(planning, list) else []
    if run_id != expected_run_id or len(matches) != 1:
        raise PipelineError(f"Femibion recovery planning identity differs: {run_id}")
    summary = planning_provenance_summary(root, expected_run_id)
    expected_result_rel = ARTIFACT_NAMESPACE / expected_run_id / "result.json"
    result_rel, result_path = _femibion_recovery_regular_path(
        root,
        expected_result_rel.as_posix(),
        label="Femibion recovery Lite result",
    )
    record = matches[0]
    expected_record = {
        "planning_run_id": expected_run_id,
        "result_path": result_rel.as_posix(),
        "result_sha256": sha256_file(result_path),
        "provenance": summary,
    }
    if record != expected_record:
        raise PipelineError(f"Femibion recovery planning record differs: {run_id}")
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("contract_version") != REQUIRED_CONTRACT_VERSION
        or summary.get("models") != [FEMIBION_VEO_RECOVERY_MODEL_ID]
        or summary.get("result_path") != result_rel.as_posix()
        or summary.get("source_image_sha256") != source.image["sha256"]
        or summary.get("article_context_sha256") != source.context_sha256
    ):
        raise PipelineError(f"Femibion recovery Lite provenance differs: {run_id}")
    context_path = root / source.context_path
    source_path = root / source.image["source_path"]
    if (
        not source_path.is_file()
        or source_path.is_symlink()
        or sha256_file(source_path) != source.image["sha256"]
        or not context_path.is_file()
        or context_path.is_symlink()
        or sha256_file(context_path) != source.context_sha256
    ):
        raise PipelineError(f"Femibion recovery source/context changed: {run_id}")
    result = read_json(result_path)
    models = result.get("models") if isinstance(result, dict) else None
    model = models[0] if isinstance(models, list) and len(models) == 1 else None
    if (
        result.get("job_id") != expected_run_id
        or not isinstance(model, dict)
        or model.get("model_id") != FEMIBION_VEO_RECOVERY_MODEL_ID
        or output.get("scene_plan") != model.get("scene_plan")
        or output.get("positive_prompt") != model.get("positive_prompt")
        or output.get("negative_prompt") != model.get("negative_prompt")
    ):
        raise PipelineError(f"Femibion recovery Lite result differs: {run_id}")
    return expected_record


def _femibion_recovery_cost(
    base_cost: dict[str, Any],
    *,
    recovery_applied: bool,
    recovery_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not recovery_applied:
        return base_cost
    result = copy.deepcopy(base_cost)
    if (
        isinstance(recovery_provenance, dict)
        and recovery_provenance.get("selection_id")
        == FEMIBION_VEO_FINAL_SELECTION_ID
    ):
        accounting = recovery_provenance.get("accounting")
        expected_accounting = {
            "currency": "USD",
            "baseline_paid_submissions": 281,
            "baseline_reserved_usd": 98.35,
            "recovery_paid_submissions": 8,
            "recovery_submissions_by_iteration": {
                "v1": 2,
                "v2": 1,
                "v3": 1,
                "v4": 1,
                "v5": 1,
                "v6": 1,
                "v7": 1,
            },
            "accounting_cost_per_output_usd": 0.35,
            "recovery_reserved_usd": 2.8,
            "aggregate_paid_submissions": 289,
            "aggregate_reserved_usd": 101.15,
            "operator_budget_cap_usd": 101.15,
            "hard_budget_cap_usd": 104.75,
            "hard_cap_headroom_usd": 3.6,
            "authorized_additional_budget_usd": 5.0,
            "automatic_paid_retries": False,
            "pricing_basis": "explicit user-authorized experiment budget",
        }
        if accounting != expected_accounting:
            raise PipelineError("Final Femibion recovery accounting changed")
        if (
            result.get("maximum_paid_submissions") != 281
            or Decimal(str(result.get("maximum_estimated_cost_usd")))
            != Decimal("98.35")
            or int(result.get("total_retry_reservations", -1)) != 5
        ):
            raise PipelineError("Legacy cost baseline changed before final recovery")
        reservations = 8
        maximum_cost = Decimal("101.15")
        hard_cap = Decimal("104.75")
        headroom = (hard_cap - maximum_cost).quantize(Decimal("0.01"))
        result.update(
            {
                "operator_budget_cap_usd": float(hard_cap),
                "hard_budget_cap_usd": float(hard_cap),
                "maximum_estimated_cost_usd": float(maximum_cost),
                "estimated_headroom_usd": float(headroom),
                "maximum_paid_submissions": 289,
                "content_filter_recovery_version": (
                    FEMIBION_VEO_FINAL_SELECTION_VERSION
                ),
                "content_filter_recovery_id": FEMIBION_VEO_FINAL_SELECTION_ID,
                "content_filter_recovery_accounting_cost_usd": float(
                    FEMIBION_VEO_RECOVERY_ACCOUNTING_COST_USD
                ),
                "content_filter_recovery_reservations": reservations,
                "content_filter_recovery_reserved_usd": 2.8,
                "authorized_additional_budget_usd": 5.0,
                "additional_budget_spent_usd": 1.4,
                "additional_budget_remaining_usd": float(headroom),
                "total_additional_reservations": (
                    int(result.get("total_retry_reservations", 0))
                    + reservations
                ),
            }
        )
        return result
    reservations = len(FEMIBION_VEO_RECOVERY_KEYS)
    additional_cost = (
        FEMIBION_VEO_RECOVERY_ACCOUNTING_COST_USD * reservations
    ).quantize(Decimal("0.01"))
    operator_cap = Decimal(str(result.get("operator_budget_cap_usd")))
    maximum_cost = (
        Decimal(str(result.get("maximum_estimated_cost_usd"))) + additional_cost
    ).quantize(Decimal("0.01"))
    maximum_submissions = result.get("maximum_paid_submissions")
    if not isinstance(maximum_submissions, int):
        raise PipelineError("Legacy cost maximum_paid_submissions is invalid")
    maximum_submissions += reservations
    headroom = (operator_cap - maximum_cost).quantize(Decimal("0.01"))
    if (
        maximum_submissions != 283
        or maximum_cost != Decimal("99.05")
        or headroom != Decimal("0.95")
        or headroom < 0
    ):
        raise PipelineError("Femibion recovery exceeds the exact legacy budget envelope")
    result.update(
        {
            "maximum_estimated_cost_usd": float(maximum_cost),
            "estimated_headroom_usd": float(headroom),
            "maximum_paid_submissions": maximum_submissions,
            "content_filter_recovery_version": FEMIBION_VEO_RECOVERY_VERSION,
            "content_filter_recovery_id": FEMIBION_VEO_RECOVERY_ID,
            "content_filter_recovery_accounting_cost_usd": float(
                FEMIBION_VEO_RECOVERY_ACCOUNTING_COST_USD
            ),
            "content_filter_recovery_reservations": reservations,
            "total_additional_reservations": (
                int(result.get("total_retry_reservations", 0)) + reservations
            ),
        }
    )
    return result


def _femibion_final_selection_overlay(
    base_outputs: Sequence[dict[str, Any]],
    discovery: Discovery,
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any]]:
    manifest_path = root / FEMIBION_VEO_FINAL_SELECTION_MANIFEST_REL
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PipelineError(
            f"Final Femibion selection manifest is missing or unsafe: {manifest_path}"
        )
    try:
        from scripts import (  # noqa: PLC0415
            clipmaker_lite_promopages_10060_femibion_all_attempts_selection
            as final_selection,
        )

        document = final_selection.validate_selection(root)
    except Exception as exc:
        raise PipelineError(
            f"Final Femibion selection evidence is invalid: {exc}"
        ) from exc
    expected_route = _femibion_recovery_route_snapshot(root)
    expected_contract = _femibion_recovery_contract_snapshot(root)
    expected_accounting = {
        "currency": "USD",
        "baseline_paid_submissions": 281,
        "baseline_reserved_usd": 98.35,
        "recovery_paid_submissions": 8,
        "recovery_submissions_by_iteration": {
            "v1": 2,
            "v2": 1,
            "v3": 1,
            "v4": 1,
            "v5": 1,
            "v6": 1,
            "v7": 1,
        },
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 2.8,
        "aggregate_paid_submissions": 289,
        "aggregate_reserved_usd": 101.15,
        "operator_budget_cap_usd": 101.15,
        "hard_budget_cap_usd": 104.75,
        "hard_cap_headroom_usd": 3.6,
        "authorized_additional_budget_usd": 5.0,
        "automatic_paid_retries": False,
        "pricing_basis": "explicit user-authorized experiment budget",
    }
    expected_merge_contract = {
        "target_manifest": FINAL_MANIFEST_REL.as_posix(),
        "logical_key": ["article_slug", "image_id", "model_id"],
        "replace_only_status": "provider-filtered",
        "replace_exactly": 2,
        "requires_ready_for_merge": True,
        "preserve_all_other_outputs": True,
        "all_or_nothing": True,
        "demo_selection_field": "supersedes_for_demo",
    }
    attempt_evidence = document.get("attempt_evidence")
    failed_attempt_chain = document.get("failed_attempt_chain")
    recovery_outputs = document.get("outputs")
    if (
        document.get("schema_version") != 1
        or document.get("manifest_role")
        != "promopages-10060-femibion-veo-all-attempts-selection"
        or document.get("ticket") != TICKET
        or document.get("selection_id") != FEMIBION_VEO_FINAL_SELECTION_ID
        or document.get("agent_id") != AGENT_ID
        or not isinstance(document.get("updated_at"), str)
        or not document["updated_at"]
        or document.get("expected_outputs") != 2
        or document.get("accepted_output_count") != 2
        or document.get("ready_for_merge") is not True
        or document.get("summary") != {"succeeded": 2, "provider-filtered": 0}
        or document.get("route") != expected_route
        or document.get("contract") != expected_contract
        or document.get("accounting") != expected_accounting
        or document.get("merge_contract") != expected_merge_contract
        or not isinstance(attempt_evidence, list)
        or len(attempt_evidence) != 8
        or not isinstance(failed_attempt_chain, list)
        or len(failed_attempt_chain) != 10
        or not isinstance(recovery_outputs, list)
        or len(recovery_outputs) != 2
    ):
        raise PipelineError("Final Femibion selection identity/accounting changed")

    base_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for output in base_outputs:
        key = _final_output_key(output)
        if key in base_by_key:
            raise PipelineError(f"Duplicate base output key before recovery: {key}")
        base_by_key[key] = output
    expected_keys = set(FEMIBION_VEO_RECOVERY_KEYS)
    filtered_keys = {
        key
        for key, output in base_by_key.items()
        if output.get("status") == "provider-filtered"
    }
    if filtered_keys != expected_keys:
        raise PipelineError(
            "Final Femibion selection requires exactly the two audited filtered outputs"
        )
    sources_by_key = {
        (
            source.article_slug,
            source.image["image_id"],
            FEMIBION_VEO_RECOVERY_MODEL_ID,
        ): source
        for source in discovery.sources
        if (
            source.article_slug,
            source.image["image_id"],
            FEMIBION_VEO_RECOVERY_MODEL_ID,
        )
        in expected_keys
    }
    if set(sources_by_key) != expected_keys:
        raise PipelineError("Final Femibion selection source bindings changed")

    recovery_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for output in recovery_outputs:
        key = _final_output_key(output)
        if key in recovery_by_key:
            raise PipelineError(f"Duplicate final Femibion output key: {key}")
        recovery_by_key[key] = output
    if set(recovery_by_key) != expected_keys:
        raise PipelineError("Final Femibion selection output keys changed")

    selected_expectations = {
        FEMIBION_VEO_RECOVERY_KEYS[0]: {
            "iteration": 7,
            "provider_job_id": "c4pO6Fw8YaEz0vPon3wH",
            "provider_run_id": (
                "promopages-10060-femibion-veo-recovery-20260810-v7-provider-"
                "07-femibion-gotovites-k-beremennosti-06-veo-3-1-lite"
            ),
            "selected_attempt": "content-filter-recovery-v7-composite",
            "video_path": (
                "clipmaker-lite-test/runs/promopages-10060-femibion-veo-"
                "recovery-20260810-v7/composite/videos/"
                "07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.mp4"
            ),
            "sha256": (
                "d058fe8556e2f3badaa436745b1aa6e30ff0e726ef1648134225508e5917e13c"
            ),
            "bytes": 552_368,
            "failed_attempts": 8,
            "composite": True,
        },
        FEMIBION_VEO_RECOVERY_KEYS[1]: {
            "iteration": 1,
            "provider_job_id": "8FDZycf6v5wTtzPmNYwF",
            "provider_run_id": (
                "promopages-10060-femibion-veo-recovery-20260810-v1-provider-"
                "08-femibion-grudnoe-vskarmlivanie-05-veo-3-1-lite"
            ),
            "selected_attempt": "content-filter-recovery-v1",
            "video_path": (
                "clipmaker-lite-test/runs/promopages-10060-femibion-veo-"
                "recovery-20260810-v1/videos/"
                "08-femibion-grudnoe-vskarmlivanie/veo-3.1-lite/05.mp4"
            ),
            "sha256": (
                "be2a072ffe4fe3934563e148956c3d05bcb6123e8a878829b18d9adead5af153"
            ),
            "bytes": 2_979_506,
            "failed_attempts": 2,
            "composite": False,
        },
    }
    replacements: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key in FEMIBION_VEO_RECOVERY_KEYS:
        old = base_by_key[key]
        source = sources_by_key[key]
        output = recovery_by_key[key]
        expected = selected_expectations[key]
        old_evidence = _femibion_old_filtered_evidence(
            old,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        recovery = output.get("recovery")
        selected_attempt = (
            recovery.get("selected_provider_attempt")
            if isinstance(recovery, dict)
            else None
        )
        selected_failed_chain = (
            recovery.get("failed_attempt_chain")
            if isinstance(recovery, dict)
            else None
        )
        composite_receipt = (
            recovery.get("composite_receipt")
            if isinstance(recovery, dict)
            else None
        )
        media = output.get("media")
        if (
            output.get("article_slug") != source.article_slug
            or output.get("image_id") != source.image["image_id"]
            or output.get("source_path") != source.image["source_path"]
            or output.get("sample_id") != source.sample_id
            or output.get("model_id") != FEMIBION_VEO_RECOVERY_MODEL_ID
            or output.get("status") != "succeeded"
            or output.get("recorded_status") != "succeeded"
            or output.get("provider_may_be_active") is not False
            or output.get("provider_job_id") != expected["provider_job_id"]
            or output.get("provider_run_id") != expected["provider_run_id"]
            or output.get("selected_attempt") != expected["selected_attempt"]
            or output.get("video_path") != expected["video_path"]
            or output.get("supersedes_for_demo")
            != FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            or not isinstance(media, dict)
            or media.get("sha256") != expected["sha256"]
            or media.get("bytes") != expected["bytes"]
            or not isinstance(recovery, dict)
            or recovery.get("selection_id") != FEMIBION_VEO_FINAL_SELECTION_ID
            or recovery.get("source_iteration") != expected["iteration"]
            or recovery.get("supersedes_for_demo")
            != FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            or not isinstance(selected_attempt, dict)
            or selected_attempt.get("provider_job_id") != expected["provider_job_id"]
            or selected_attempt.get("provider_run_id") != expected["provider_run_id"]
            or not isinstance(selected_failed_chain, list)
            or len(selected_failed_chain) != expected["failed_attempts"]
            or (composite_receipt is not None) is not expected["composite"]
            or recovery.get("automatic_retry") is not False
            or recovery.get("fallback") is not False
        ):
            raise PipelineError(f"Final Femibion selected output changed: {key}")
        _video_rel, video_path = _femibion_recovery_regular_path(
            root,
            output.get("video_path"),
            label="Final Femibion selected MP4",
        )
        if (
            sha256_file(video_path) != expected["sha256"]
            or video_path.stat().st_size != expected["bytes"]
            or final_output_acceptance_error(
                output,
                root=root,
                allow_contract_warnings=allow_contract_warnings,
            )
            is not None
        ):
            raise PipelineError(f"Final Femibion selected MP4 is not accepted: {key}")
        selected = copy.deepcopy(output)
        selected["retry"] = copy.deepcopy(old["retry"])
        selected_recovery = copy.deepcopy(recovery)
        selected_recovery["old_provider_filtered"] = old_evidence
        selected_recovery["superseded_selected_attempt"] = {
            "provider_run_id": old["provider_run_id"],
            "status": old["status"],
            "recorded_status": old["recorded_status"],
            "selected_attempt": old["selected_attempt"],
            "error": old["error"],
        }
        selected["recovery"] = selected_recovery
        replacements[key] = selected

    supersedes = document.get("supersedes_for_demo")
    planning = document.get("planning")
    composite = document.get("composite_receipt")
    if (
        not isinstance(supersedes, list)
        or len(supersedes) != 2
        or not isinstance(planning, list)
        or len(planning) != 2
        or not isinstance(composite, dict)
        or composite.get("path")
        != (
            "clipmaker-lite-test/runs/promopages-10060-femibion-veo-"
            "recovery-20260810-v7/composite/videos/"
            "07-femibion-gotovites-k-beremennosti/veo-3.1-lite/06.receipt.json"
        )
        or composite.get("sha256")
        != "80e90a4cf753be47d5ddb5e36874e321991ffa50f4e041b9807725614a2e09e4"
    ):
        raise PipelineError("Final Femibion selection provenance changed")
    provenance = {
        "version": FEMIBION_VEO_FINAL_SELECTION_VERSION,
        "recovery_id": FEMIBION_VEO_FINAL_SELECTION_ID,
        "selection_id": FEMIBION_VEO_FINAL_SELECTION_ID,
        "manifest_path": FEMIBION_VEO_FINAL_SELECTION_MANIFEST_REL.as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "ready_for_merge": True,
        "overlay_keys": [
            {
                "article_slug": key[0],
                "image_id": key[1],
                "model_id": key[2],
            }
            for key in FEMIBION_VEO_RECOVERY_KEYS
        ],
        "route": expected_route,
        "contract": expected_contract,
        "accounting": copy.deepcopy(expected_accounting),
        "attempt_evidence_count": len(attempt_evidence),
        "failed_attempt_count": len(failed_attempt_chain),
        "planning": copy.deepcopy(planning),
        "supersedes_for_demo": copy.deepcopy(supersedes),
        "composite_receipt": {
            "path": composite["path"],
            "sha256": composite["sha256"],
        },
    }
    return replacements, provenance


def _femibion_recovery_overlay(
    base_outputs: Sequence[dict[str, Any]],
    discovery: Discovery,
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any] | None]:
    if BATCH_ID != LEGACY_BATCH_ID:
        return {}, None
    final_manifest_path = root / FEMIBION_VEO_FINAL_SELECTION_MANIFEST_REL
    if final_manifest_path.exists():
        return _femibion_final_selection_overlay(
            base_outputs,
            discovery,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
    manifest_path = root / FEMIBION_VEO_RECOVERY_MANIFEST_REL
    if not manifest_path.exists():
        return {}, None
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PipelineError(f"Femibion recovery manifest is unsafe: {manifest_path}")
    document = read_json(manifest_path)
    if not isinstance(document, dict):
        raise PipelineError("Femibion recovery manifest is not an object")
    expected_route = _femibion_recovery_route_snapshot(root)
    expected_contract = _femibion_recovery_contract_snapshot(root)
    expected_merge_contract = {
        "target_manifest": FINAL_MANIFEST_REL.as_posix(),
        "logical_key": ["article_slug", "image_id", "model_id"],
        "replace_only_status": "provider-filtered",
        "replace_exactly": 2,
        "requires_ready_for_merge": True,
        "preserve_all_other_outputs": True,
        "demo_selection_field": "supersedes_for_demo",
    }
    expected_accounting = {
        "currency": "USD",
        "baseline_paid_submissions": 281,
        "baseline_reserved_usd": 98.35,
        "recovery_paid_submissions": 2,
        "accounting_cost_per_output_usd": 0.35,
        "recovery_reserved_usd": 0.7,
        "aggregate_paid_submissions": 283,
        "aggregate_reserved_usd": 99.05,
        "operator_budget_cap_usd": 99.05,
        "hard_budget_cap_usd": 100.0,
        "hard_cap_headroom_usd": 0.95,
        "maximum_new_paid_submissions": 2,
        "automatic_paid_retries": False,
        "pricing_basis": "frozen local PROMOPAGES-10060 accounting evidence",
    }
    if (
        document.get("schema_version") != 1
        or document.get("manifest_role")
        != "promopages-10060-femibion-veo-content-filter-recovery"
        or document.get("ticket") != TICKET
        or document.get("recovery_id") != FEMIBION_VEO_RECOVERY_ID
        or document.get("provider_batch_id")
        != FEMIBION_VEO_RECOVERY_PROVIDER_BATCH_ID
        or document.get("agent_id") != AGENT_ID
        or document.get("expected_outputs") != 2
        or not isinstance(document.get("updated_at"), str)
        or not document["updated_at"]
        or document.get("route") != expected_route
        or document.get("contract") != expected_contract
        or document.get("accounting") != expected_accounting
        or document.get("merge_contract") != expected_merge_contract
        or document.get("generation_manifest_path")
        != FEMIBION_VEO_RECOVERY_GENERATION_MANIFEST_REL.as_posix()
    ):
        raise PipelineError("Femibion recovery manifest identity/route changed")
    accepted_output_count = document.get("accepted_output_count")
    ready_for_merge = document.get("ready_for_merge")
    recovery_outputs = document.get("outputs")
    if (
        isinstance(accepted_output_count, bool)
        or not isinstance(accepted_output_count, int)
        or accepted_output_count not in {0, 1, 2}
        or not isinstance(ready_for_merge, bool)
        or ready_for_merge != (accepted_output_count == 2)
        or not isinstance(recovery_outputs, list)
        or len(recovery_outputs) != 2
    ):
        raise PipelineError("Femibion recovery readiness accounting changed")
    policy = document.get("generation_policy")
    if (
        not isinstance(policy, dict)
        or policy.get("exact_model_id") != FEMIBION_VEO_RECOVERY_MODEL_ID
        or policy.get("exact_route_only") is not True
        or policy.get("automatic_fallback") is not False
        or policy.get("normal_run_discovery") is not False
        or policy.get("automatic_paid_retries") is not False
        or policy.get("maximum_submissions_per_new_provider_identity") != 1
    ):
        raise PipelineError("Femibion recovery generation policy changed")
    if not ready_for_merge:
        # A partial v1 result remains immutable evidence in its own namespace,
        # but canonical selection is deliberately all-or-nothing.  In
        # particular, never publish only one of the two registered keys.
        return {}, None

    base_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for output in base_outputs:
        key = _final_output_key(output)
        if key in base_by_key:
            raise PipelineError(f"Duplicate base output key before recovery: {key}")
        base_by_key[key] = output
    expected_keys = set(FEMIBION_VEO_RECOVERY_KEYS)
    filtered_keys = {
        key
        for key, output in base_by_key.items()
        if output.get("status") == "provider-filtered"
    }
    if filtered_keys != expected_keys:
        raise PipelineError(
            "Femibion recovery requires exactly the two registered filtered outputs"
        )
    sources_by_key = {
        (
            source.article_slug,
            source.image["image_id"],
            FEMIBION_VEO_RECOVERY_MODEL_ID,
        ): source
        for source in discovery.sources
        if (
            source.article_slug,
            source.image["image_id"],
            FEMIBION_VEO_RECOVERY_MODEL_ID,
        )
        in expected_keys
    }
    if set(sources_by_key) != expected_keys:
        raise PipelineError("Femibion recovery source bindings changed")

    recovery_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for output in recovery_outputs:
        key = _final_output_key(output)
        if key in recovery_by_key:
            raise PipelineError(f"Duplicate Femibion recovery output key: {key}")
        recovery_by_key[key] = output
    if set(recovery_by_key) != expected_keys:
        raise PipelineError("Femibion recovery output keys changed")
    computed_summary: dict[str, int] = {}
    replacements: dict[tuple[str, str, str], dict[str, Any]] = {}
    planning_records: list[dict[str, Any]] = []
    supersedes_records: list[dict[str, Any]] = []
    for key in FEMIBION_VEO_RECOVERY_KEYS:
        old = base_by_key[key]
        source = sources_by_key[key]
        output = recovery_by_key[key]
        old_evidence = _femibion_old_filtered_evidence(
            old,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        recovery = output.get("recovery")
        expected_provider_run_id = (
            f"{FEMIBION_VEO_RECOVERY_PROVIDER_BATCH_ID}-{source.sample_id}-"
            "veo-3-1-lite"
        )
        status = output.get("status")
        computed_summary[str(status)] = computed_summary.get(str(status), 0) + 1
        expected_directory = (
            FEMIBION_VEO_RECOVERY_ROOT_REL
            / "videos"
            / source.article_slug
            / "veo-3.1-lite"
        )
        expected_prompt = expected_directory / f"{source.image['image_id']}.prompt.json"
        expected_run = expected_directory / f"{source.image['image_id']}.run.json"
        expected_video = expected_directory / f"{source.image['image_id']}.mp4"
        if (
            output.get("article_slug") != source.article_slug
            or output.get("image_id") != source.image["image_id"]
            or output.get("source_path") != source.image["source_path"]
            or output.get("sample_id") != source.sample_id
            or output.get("provider_run_id") != expected_provider_run_id
            or output.get("model_id") != FEMIBION_VEO_RECOVERY_MODEL_ID
            or output.get("recorded_status") != status
            or output.get("provider_may_be_active") is not False
            or output.get("prompt_path") != expected_prompt.as_posix()
            or output.get("run_path") != expected_run.as_posix()
            or output.get("video_path") != expected_video.as_posix()
            or output.get("selected_attempt") != "content-filter-recovery-v1"
            or output.get("supersedes_for_demo")
            != FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            or not isinstance(recovery, dict)
            or recovery.get("recovery_id") != FEMIBION_VEO_RECOVERY_ID
            or recovery.get("supersedes_for_demo")
            != FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            or recovery.get("old_provider_filtered") != old_evidence
            or recovery.get("request_changed") is not True
            or recovery.get("automatic_retry") is not False
            or recovery.get("fallback") is not False
        ):
            raise PipelineError(f"Femibion recovery output identity changed: {key}")
        request_sha256 = recovery.get("new_request_sha256")
        if (
            not isinstance(request_sha256, str)
            or len(request_sha256) != 64
            or request_sha256 == old_evidence["request_sha256"]
            or any(
                character not in "0123456789abcdef"
                for character in request_sha256
            )
        ):
            raise PipelineError(f"Femibion recovery request audit differs: {key}")
        prompt_rel, prompt_path = _femibion_recovery_regular_path(
            root,
            output.get("prompt_path"),
            label="Femibion recovery prompt receipt",
        )
        run_rel, run_path = _femibion_recovery_regular_path(
            root,
            output.get("run_path"),
            label="Femibion recovery run receipt",
        )
        video_rel, video_path = _femibion_recovery_regular_path(
            root,
            output.get("video_path"),
            label="Femibion recovery MP4",
        )
        media = output.get("media")
        if (
            prompt_rel != expected_prompt
            or run_rel != expected_run
            or video_rel != expected_video
            or not isinstance(media, dict)
            or media.get("sha256") != sha256_file(video_path)
            or media.get("bytes") != video_path.stat().st_size
            or final_output_acceptance_error(
                output,
                root=root,
                allow_contract_warnings=allow_contract_warnings,
            )
            is not None
        ):
            raise PipelineError(f"Femibion recovery MP4 is not accepted: {key}")
        prompt_receipt = read_json(prompt_path)
        run_receipt = read_json(run_path)
        receipt_binding = {
            "recovery_id": FEMIBION_VEO_RECOVERY_ID,
            "logical_key": {
                "article_slug": key[0],
                "image_id": key[1],
                "model_id": key[2],
            },
            "supersedes_for_demo": FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key],
            "old_status": "provider-filtered",
            "old_retry_v1_exhausted": True,
            "automatic_retry": False,
            "fallback": False,
        }
        if (
            not isinstance(prompt_receipt, dict)
            or prompt_receipt.get("provider_run_id") != expected_provider_run_id
            or prompt_receipt.get("lite_run_id") != output.get("lite_run_id")
            or prompt_receipt.get("model_id") != FEMIBION_VEO_RECOVERY_MODEL_ID
            or prompt_receipt.get("supersedes_for_demo")
            != FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            or prompt_receipt.get("recovery") != receipt_binding
            or not isinstance(run_receipt, dict)
            or run_receipt.get("provider_run_id") != expected_provider_run_id
            or run_receipt.get("sample_id") != source.sample_id
            or run_receipt.get("image_id") != source.image["image_id"]
            or run_receipt.get("lite_run_id") != output.get("lite_run_id")
            or run_receipt.get("model_id") != FEMIBION_VEO_RECOVERY_MODEL_ID
            or run_receipt.get("status") != output.get("recorded_status")
            or run_receipt.get("media") != media
            or run_receipt.get("contract_check") != output.get("contract_check")
            or run_receipt.get("error") != output.get("error")
            or run_receipt.get("output_path") != output.get("video_path")
            or run_receipt.get("request_sha256") != request_sha256
            or run_receipt.get("supersedes_for_demo")
            != FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            or run_receipt.get("recovery") != receipt_binding
        ):
            raise PipelineError(f"Femibion recovery provider receipts differ: {key}")
        planning_record = _femibion_recovery_planning_record(
            document,
            output,
            source,
            root=root,
        )
        planning_records.append(planning_record)
        supersedes_record = {
            "logical_key": {
                "article_slug": key[0],
                "image_id": key[1],
                "model_id": key[2],
            },
            "old_provider_run_id": FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key],
            "new_provider_run_id": expected_provider_run_id,
        }
        supersedes_records.append(supersedes_record)
        selected = copy.deepcopy(output)
        selected["retry"] = copy.deepcopy(old["retry"])
        selected_recovery = copy.deepcopy(recovery)
        selected_recovery["planning"] = planning_record
        selected_recovery["superseded_selected_attempt"] = {
            "provider_run_id": old["provider_run_id"],
            "status": old["status"],
            "recorded_status": old["recorded_status"],
            "selected_attempt": old["selected_attempt"],
            "error": old["error"],
        }
        selected["recovery"] = selected_recovery
        replacements[key] = selected

    if document.get("summary") != computed_summary:
        raise PipelineError("Femibion recovery status summary differs")
    if document.get("supersedes_for_demo") != supersedes_records:
        raise PipelineError("Femibion recovery supersedes links changed")
    if document.get("planning") != planning_records:
        raise PipelineError("Femibion recovery planning set changed")
    provenance = {
        "version": FEMIBION_VEO_RECOVERY_VERSION,
        "recovery_id": FEMIBION_VEO_RECOVERY_ID,
        "manifest_path": FEMIBION_VEO_RECOVERY_MANIFEST_REL.as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "ready_for_merge": True,
        "overlay_keys": [
            {
                "article_slug": key[0],
                "image_id": key[1],
                "model_id": key[2],
            }
            for key in FEMIBION_VEO_RECOVERY_KEYS
        ],
        "route": expected_route,
        "contract": expected_contract,
        "planning": planning_records,
        "supersedes_for_demo": supersedes_records,
    }
    return replacements, provenance


def _apply_final_output_replacements(
    outputs: Sequence[dict[str, Any]],
    articles: list[dict[str, Any]],
    replacements: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    if not replacements:
        return list(outputs)
    flat_seen: set[tuple[str, str, str]] = set()
    selected_outputs: list[dict[str, Any]] = []
    for output in outputs:
        key = _final_output_key(output)
        selected = replacements.get(key, output)
        if key in replacements:
            flat_seen.add(key)
        selected_outputs.append(selected)
    nested_seen: set[tuple[str, str, str]] = set()
    for article_record in articles:
        for image_record in article_record["images"]:
            selected_image_outputs: list[dict[str, Any]] = []
            for output in image_record["outputs"]:
                key = _final_output_key(output)
                selected = replacements.get(key, output)
                if key in replacements:
                    nested_seen.add(key)
                selected_image_outputs.append(selected)
            image_record["outputs"] = selected_image_outputs
    expected = set(replacements)
    if flat_seen != expected or nested_seen != expected:
        raise PipelineError("Recovery replacements did not cover flat and nested outputs")
    return selected_outputs


def build_final_manifest(
    discovery: Discovery,
    inventory: dict[str, Any],
    *,
    root: Path,
    updated_at: str | None = None,
    allow_contract_warnings: bool,
) -> dict[str, Any]:
    configure_native(discovery.sources, root)
    native.materialize(root)
    generation = read_json(root / GENERATION_MANIFEST_REL)
    generation_outputs = generation.get("outputs") if isinstance(generation, dict) else None
    expected_outputs = len(discovery.sources) * len(MODEL_IDS)
    if not isinstance(generation_outputs, list) or len(generation_outputs) != expected_outputs:
        raise PipelineError(
            f"Generation manifest must contain {expected_outputs} outputs"
        )
    provider_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for provider in generation_outputs:
        if not isinstance(provider, dict):
            raise PipelineError("Generation output is not an object")
        key = (str(provider.get("source_path")), str(provider.get("model_id")))
        if key in provider_by_key:
            raise PipelineError(f"Duplicate generation output key: {key}")
        provider_by_key[key] = provider

    sources_by_slug: dict[str, list[Source]] = {}
    for source in discovery.sources:
        sources_by_slug.setdefault(source.article_slug, []).append(source)
    articles: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    for article in discovery.articles:
        article_sources = sources_by_slug.get(article.slug, [])
        if tuple(source.image for source in article_sources) != article.images:
            raise PipelineError(
                f"Article source order differs from discovery: {article.slug}"
            )
        image_records: list[dict[str, Any]] = []
        for source in article_sources:
            summary, result = _planning_record(source, root)
            model_by_id = {
                model.get("model_id"): model
                for model in result["models"]
                if isinstance(model, dict)
            }
            image_outputs: list[dict[str, Any]] = []
            for model_id in MODEL_IDS:
                provider = provider_by_key.get(
                    (source.image["source_path"], model_id)
                )
                retry_provider = _terminal_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                ambiguous_provider = _ambiguous_submit_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                normalized_provider = _normalized_input_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                if sum(
                    candidate is not None
                    for candidate in (
                        retry_provider,
                        ambiguous_provider,
                        normalized_provider,
                    )
                ) > 1:
                    raise PipelineError(
                        "A logical output has conflicting retry results: "
                        f"{source.sample_id}/{model_id}"
                    )
                if retry_provider is not None:
                    provider = retry_provider
                if ambiguous_provider is not None:
                    provider = ambiguous_provider
                if normalized_provider is not None:
                    provider = normalized_provider
                model = model_by_id.get(model_id)
                if provider is None or model is None:
                    raise PipelineError(
                        f"Missing output binding: {source.sample_id}/{model_id}"
                    )
                if normalized_provider is not None:
                    normalized_selection = normalized_provider.get(
                        "retry_selection"
                    )
                    if (
                        isinstance(normalized_selection, dict)
                        and isinstance(
                            normalized_selection.get("supersede"),
                            dict,
                        )
                    ):
                        expected_run_id = normalized_input_supersede_binding(
                            source,
                            model_id,
                        ).supersede_provider_run_id
                    else:
                        expected_run_id = normalized_input_retry_binding(
                            source,
                            model_id,
                        ).retry_provider_run_id
                elif ambiguous_provider is not None:
                    expected_run_id = ambiguous_submit_retry_binding(
                        source,
                        model_id,
                    ).retry_provider_run_id
                elif retry_provider is not None:
                    expected_run_id = terminal_retry_binding(
                        source,
                        model_id,
                    ).retry_provider_run_id
                else:
                    expected_run_id = primary_provider_run_id(source, model_id)
                if provider.get("provider_run_id") != expected_run_id:
                    raise PipelineError(
                        f"Provider identity mismatch: {source.sample_id}/{model_id}"
                    )
                output = _output_record(
                    article=article,
                    source=source,
                    model_id=model_id,
                    model=model,
                    provider=provider,
                )
                image_outputs.append(output)
                outputs.append(output)
            image_records.append(
                {
                    "image": source.image,
                    "lite_planning": {
                        "run_id": source.planning_run_id,
                        "result_path": summary.get("result_path"),
                        "structured_intent": result.get("analysis", {}).get(
                            "structured_intent"
                        ),
                        "provenance": summary,
                    },
                    "outputs": image_outputs,
                }
            )
        articles.append(
            {
                "article_number": article.number,
                "article_slug": article.slug,
                "label": article.label,
                "url": article.url,
                "title": article.title,
                "lead": article.lead,
                "context_path": article.context_path,
                # Keep the cover as the article-level representative for demo
                # compatibility. Every image, including this cover, is planned
                # and generated independently below articles[].images[].
                "selected_image": article.cover_image,
                "image_count": len(image_records),
                "images": image_records,
            }
        )

    if len(outputs) != expected_outputs:
        raise PipelineError("Final output count changed")
    output_keys = {
        (output["article_slug"], output["image_id"], output["model_id"])
        for output in outputs
    }
    if len(output_keys) != expected_outputs:
        raise PipelineError("Final output keys are not unique")
    recovery_replacements, recovery_provenance = _femibion_recovery_overlay(
        outputs,
        discovery,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    if recovery_replacements:
        outputs = _apply_final_output_replacements(
            outputs,
            articles,
            recovery_replacements,
        )
    status_summary: dict[str, int] = {}
    for output in outputs:
        status = str(output.get("status") or "missing")
        status_summary[status] = status_summary.get(status, 0) + 1
    status_summary.setdefault("provider-filtered", 0)
    cost = _femibion_recovery_cost(
        _aggregate_retry_cost(inventory, root=root),
        recovery_applied=recovery_provenance is not None,
        recovery_provenance=recovery_provenance,
    )
    return {
        "schema_version": 1,
        "manifest_role": FINAL_MANIFEST_ROLE,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "updated_at": updated_at or transport.utc_now(),
        "merge_contract": {
            "article_key": ["article_slug"],
            "image_key": ["article_slug", "image_id"],
            "output_key": ["article_slug", "image_id", "model_id"],
            "target_field": "articles[].images[]",
        },
        "models": list(MODEL_IDS),
        "article_count": len(articles),
        "image_count": len(discovery.sources),
        "expected_outputs": expected_outputs,
        "unavailable_articles": list(discovery.unavailable_articles),
        "cost": cost,
        "generation_policy": {
            **inventory["generation_policy"],
            "terminal_provider_retry": {
                "version": TERMINAL_RETRY_VERSION,
                "namespace": TERMINAL_RETRY_NAMESPACE_REL.as_posix(),
                "explicit_operator_command_required": True,
                "maximum_new_paid_submissions_per_failed_output": 1,
                "automatic_paid_retries": False,
                "fallback": False,
                "primary_receipts_immutable": True,
            },
            "ambiguous_submit_retry": {
                "version": AMBIGUOUS_SUBMIT_RETRY_VERSION,
                "namespace": AMBIGUOUS_SUBMIT_RETRY_NAMESPACE_REL.as_posix(),
                # Preserve the frozen legacy sidecar byte-semantics while the
                # extension truthfully records that each retry stays on the
                # logical output's exact registry-bound model route.
                "route": (
                    "eliza-segmind/alibaba/wan-2.2"
                    if BATCH_ID == LEGACY_BATCH_ID
                    else "exact-frozen-generation-route-per-model"
                ),
                "explicit_operator_command_required": True,
                "maximum_new_paid_submissions_per_ambiguous_output": 1,
                "retry2_forbidden": True,
                "automatic_paid_retries": False,
                "fallback": False,
                "primary_receipts_immutable": True,
                "primary_outcome_remains_unknown": True,
            },
            "normalized_input_retry": _normalized_input_generation_policy(),
            **(
                {
                    "content_filter_recovery": {
                        "version": recovery_provenance["version"],
                        "recovery_id": recovery_provenance["recovery_id"],
                        "namespace": Path(
                            recovery_provenance["manifest_path"]
                        ).parent.as_posix(),
                        "model_id": FEMIBION_VEO_RECOVERY_MODEL_ID,
                        "replace_exactly": len(FEMIBION_VEO_RECOVERY_KEYS),
                        "automatic_paid_retries": False,
                        "fallback": False,
                        "old_retry_receipts_immutable": True,
                        **(
                            {
                                "all_attempts_preserved": True,
                                "deterministic_composite_is_derived_demo_media": True,
                                "selected_output_count": 2,
                                "selected_raw_provider_output_count": 1,
                                "selected_derived_output_count": 1,
                            }
                            if recovery_provenance.get("selection_id")
                            == FEMIBION_VEO_FINAL_SELECTION_ID
                            else {}
                        ),
                    }
                }
                if recovery_provenance is not None
                else {}
            ),
            **(
                {
                    "normalized_input_supersede": {
                        "version": NORMALIZED_INPUT_SUPERSEDE_VERSION,
                        "namespace": (
                            NORMALIZED_INPUT_SUPERSEDE_NAMESPACE_REL.as_posix()
                        ),
                        **_normalized_input_supersede_policy(),
                    }
                }
                if _known_normalized_input_supersede_envelopes(root)
                else {}
            ),
        },
        "status_summary": status_summary,
        "acceptance_policy": {
            "allow_contract_warnings": allow_contract_warnings,
            "accepted_complete_statuses": (
                ["succeeded", "verification-failed"]
                if allow_contract_warnings
                else ["succeeded"]
            ),
            "requires_mp4_and_media": True,
            "terminal_accounted_without_media": [
                "provider-filtered",
                "provider-unavailable",
            ],
            "provider_filtered_requires_exhausted_retry_v1": True,
            "provider_unavailable_requires_retry_v1": [
                "ambiguous-submit",
                "normalized-input",
            ],
            "provider_unavailable_requires_ambiguous_submit_retry_v1": True,
            "preserve_recorded_status": True,
            **(
                {
                    "content_filter_recovery_requires_verified_current_lite_provenance": True,
                    "content_filter_recovery_preserves_old_retry_audit": True,
                }
                if recovery_provenance is not None
                else {}
            ),
        },
        **_acceptance_audit(
            outputs,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        ),
        "inventory_manifest": INVENTORY_MANIFEST_REL.as_posix(),
        "generation_manifest": GENERATION_MANIFEST_REL.as_posix(),
        **(
            {"recovery_provenance": recovery_provenance}
            if recovery_provenance is not None
            else {}
        ),
        "articles": articles,
        "outputs": outputs,
    }


def final_manifest_errors(
    document: Any,
    *,
    discovery: Discovery,
    root: Path,
    allow_contract_warnings: bool,
) -> list[str]:
    if not isinstance(document, dict):
        return ["Final manifest is not an object"]
    outputs = document.get("outputs")
    errors: list[str] = []
    expected_outputs = len(discovery.sources) * len(MODEL_IDS)
    if document.get("article_count") != len(discovery.articles):
        errors.append("Final article_count differs from frozen inventory")
    if document.get("image_count") != len(discovery.sources):
        errors.append("Final image_count differs from frozen inventory")
    if document.get("expected_outputs") != expected_outputs:
        errors.append("Final expected_outputs differs from frozen inventory")
    if document.get("unavailable_articles") != list(discovery.unavailable_articles):
        errors.append("Final unavailable_articles differs from extraction report")
    if not isinstance(outputs, list) or len(outputs) != expected_outputs:
        errors.append("Final flat output list has the wrong size")
        return errors
    seen: set[tuple[Any, Any, Any]] = set()
    flat_by_key: dict[tuple[Any, Any, Any], Any] = {}
    for output in outputs:
        if isinstance(output, dict):
            key = (
                output.get("article_slug"),
                output.get("image_id"),
                output.get("model_id"),
            )
            if key in seen:
                errors.append(f"Duplicate final output key: {key}")
            seen.add(key)
            flat_by_key[key] = output
        error = final_output_terminal_error(
            output,
            root=root,
            allow_contract_warnings=allow_contract_warnings,
        )
        if error:
            errors.append(error)
    nested_by_key: dict[tuple[Any, Any, Any], Any] = {}
    articles = document.get("articles")
    if not isinstance(articles, list) or len(articles) != len(discovery.articles):
        errors.append("Final nested article list has the wrong size")
    else:
        for article in articles:
            images = article.get("images") if isinstance(article, dict) else None
            if not isinstance(images, list):
                errors.append("Final nested article images are invalid")
                continue
            for image in images:
                image_outputs = image.get("outputs") if isinstance(image, dict) else None
                if not isinstance(image_outputs, list):
                    errors.append("Final nested image outputs are invalid")
                    continue
                for output in image_outputs:
                    if not isinstance(output, dict):
                        errors.append("Final nested output is not an object")
                        continue
                    key = (
                        output.get("article_slug"),
                        output.get("image_id"),
                        output.get("model_id"),
                    )
                    if key in nested_by_key:
                        errors.append(f"Duplicate nested final output key: {key}")
                    nested_by_key[key] = output
    if set(nested_by_key) != set(flat_by_key):
        errors.append("Final nested/flat output key sets differ")
    else:
        for key, output in flat_by_key.items():
            if nested_by_key[key] != output:
                errors.append(f"Final nested/flat selected output differs: {key}")
    expected_status_summary: dict[str, int] = {}
    for output in outputs:
        status = str(output.get("status") or "missing") if isinstance(output, dict) else "missing"
        expected_status_summary[status] = expected_status_summary.get(status, 0) + 1
    expected_status_summary.setdefault("provider-filtered", 0)
    if document.get("status_summary") != expected_status_summary:
        errors.append("Final status_summary does not match selected outputs")
    expected_audit = _acceptance_audit(
        outputs,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    for key, expected in expected_audit.items():
        if document.get(key) != expected:
            errors.append(f"Final {key} does not match artifacts")
    recovery_provenance = document.get("recovery_provenance")
    if recovery_provenance is not None:
        cost = document.get("cost")
        if (
            isinstance(recovery_provenance, dict)
            and recovery_provenance.get("selection_id")
            == FEMIBION_VEO_FINAL_SELECTION_ID
        ):
            cost_differs = (
                not isinstance(cost, dict)
                or cost.get("operator_budget_cap_usd") != 104.75
                or cost.get("hard_budget_cap_usd") != 104.75
                or cost.get("maximum_paid_submissions") != 289
                or cost.get("maximum_estimated_cost_usd") != 101.15
                or cost.get("estimated_headroom_usd") != 3.6
                or cost.get("content_filter_recovery_reservations") != 8
                or cost.get("content_filter_recovery_reserved_usd") != 2.8
                or cost.get("authorized_additional_budget_usd") != 5.0
                or cost.get("additional_budget_spent_usd") != 1.4
                or cost.get("additional_budget_remaining_usd") != 3.6
            )
        else:
            cost_differs = (
                not isinstance(cost, dict)
                or cost.get("maximum_paid_submissions") != 283
                or cost.get("maximum_estimated_cost_usd") != 99.05
                or cost.get("estimated_headroom_usd") != 0.95
                or cost.get("content_filter_recovery_reservations") != 2
            )
        if cost_differs:
            errors.append("Final Femibion recovery cost accounting differs")
    return errors


def finalize(
    discovery: Discovery,
    inventory: dict[str, Any],
    *,
    root: Path,
    allow_contract_warnings: bool,
) -> dict[str, Any]:
    document = build_final_manifest(
        discovery,
        inventory,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    errors = final_manifest_errors(
        document,
        discovery=discovery,
        root=root,
        allow_contract_warnings=allow_contract_warnings,
    )
    if errors:
        raise PipelineError(
            f"Cannot finalize: {len(errors)} acceptance error(s): "
            + "; ".join(errors[:5])
        )
    transport.atomic_write_json(root / FINAL_MANIFEST_REL, document)
    return document


def verify_all(
    discovery: Discovery,
    inventory: dict[str, Any],
    *,
    root: Path,
    allow_incomplete: bool,
    allow_contract_warnings: bool,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    configure_native(discovery.sources, root)
    terminal_retry_count = len(_known_retry_envelopes(root))
    ambiguous_retry_count = len(_known_ambiguous_submit_retry_envelopes(root))
    normalized_retry_count = len(_known_normalized_input_retry_envelopes(root))
    normalized_supersede_count = len(
        _known_normalized_input_supersede_envelopes(root)
    )
    _enforce_retry_namespace_conflicts(
        _known_retry_envelopes(root),
        _known_ambiguous_submit_retry_envelopes(root),
        _known_normalized_input_retry_envelopes(root),
    )
    retry_count = (
        terminal_retry_count
        + ambiguous_retry_count
        + normalized_retry_count
        + normalized_supersede_count
    )
    native_ok, native_errors = native.verify(
        root,
        # A selected retry intentionally leaves its immutable primary receipt
        # in provider-failed. Final logical-output acceptance below remains
        # strict and is the completeness authority when retry-v1 is present.
        allow_incomplete=allow_incomplete or retry_count > 0,
        allow_contract_warnings=allow_contract_warnings,
    )
    if not native_ok:
        errors.extend(native_errors)
    final_path = root / FINAL_MANIFEST_REL
    if not final_path.is_file():
        if not allow_incomplete:
            errors.append(f"Missing final manifest: {FINAL_MANIFEST_REL}")
    else:
        actual = read_json(final_path)
        updated_at = actual.get("updated_at") if isinstance(actual, dict) else None
        rebuilt = (
            build_final_manifest(
                discovery,
                inventory,
                root=root,
                updated_at=updated_at,
                allow_contract_warnings=allow_contract_warnings,
            )
            if isinstance(updated_at, str)
            else None
        )
        if rebuilt is None or actual != rebuilt:
            errors.append("Final sidecar does not match current planning/provider artifacts")
        if not allow_incomplete and rebuilt is not None:
            errors.extend(
                final_manifest_errors(
                    rebuilt,
                    discovery=discovery,
                    root=root,
                    allow_contract_warnings=allow_contract_warnings,
                )
            )
    report = {
        "schema_version": 1,
        "ticket": TICKET,
        "batch_id": BATCH_ID,
        "passed": not errors,
        "allow_incomplete": allow_incomplete,
        "allow_contract_warnings": allow_contract_warnings,
        "article_count": len(discovery.articles),
        "unavailable_article_count": len(discovery.unavailable_articles),
        "image_count": len(discovery.sources),
        "expected_outputs": len(discovery.sources) * len(MODEL_IDS),
        "terminal_retry_reservations": terminal_retry_count,
        "ambiguous_submit_retry_reservations": ambiguous_retry_count,
        "normalized_input_retry_reservations": normalized_retry_count,
        **(
            {
                "normalized_input_supersede_reservations": (
                    normalized_supersede_count
                )
            }
            if normalized_supersede_count
            else {}
        ),
        "total_retry_reservations": retry_count,
        "errors": errors,
    }
    transport.atomic_write_json(root / VERIFICATION_REPORT_REL, report)
    return not errors, errors


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _add_budget(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--budget-cap-usd",
        type=budget_arg,
        default=DEFAULT_OPERATOR_BUDGET_CAP_USD,
        help=(
            "operator aggregate cap; must cover the complete frozen matrix "
            "and comply with the selected registered batch policy"
        ),
    )


def _add_planning_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--article", action="append", default=[])
    parser.add_argument("--planning-run-id", action="append", default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch",
        choices=tuple(BATCH_SPECS),
        default=LEGACY_BATCH_ID,
        help=(
            "registered immutable input/output batch; defaults to the frozen "
            "legacy PROMOPAGES-10060 run"
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser(
        "inventory", help="discover and freeze the ticket-specific all-image matrix"
    )
    inventory.add_argument("--dry-run", action="store_true")
    _add_budget(inventory)

    prepare = commands.add_parser(
        "prepare-plans", help="prepare or resume all selected three-model Lite jobs"
    )
    prepare.add_argument("--dry-run", action="store_true")
    _add_planning_filters(prepare)
    _add_budget(prepare)

    run_plans = commands.add_parser(
        "run-plans", help="run or resume isolated three-model Lite analyses"
    )
    run_plans.add_argument("--concurrency", type=positive_int, default=3)
    run_plans.add_argument("--timeout", type=positive_int, default=1800)
    run_plans.add_argument("--author-model")
    run_plans.add_argument("--dry-run", action="store_true")
    run_plans.add_argument("--allow-external-processing", action="store_true")
    _add_planning_filters(run_plans)
    _add_budget(run_plans)

    plan_generation = commands.add_parser(
        "plan-generation", help="materialize or preview the frozen provider matrix"
    )
    plan_generation.add_argument("--dry-run", action="store_true")
    _add_budget(plan_generation)

    generate = commands.add_parser(
        "generate", help="run/resume independent route pools at capacities 1/3/3"
    )
    generate.add_argument("--timeout", type=positive_int, default=1800)
    generate.add_argument("--poll-interval", type=float, default=10.0)
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--allow-external-processing", action="store_true")
    generate.add_argument("--fail-fast", action="store_true")
    generate.add_argument("--article", action="append", default=[])
    _add_budget(generate)

    retry = commands.add_parser(
        "retry-terminal-failure",
        help=(
            "explicitly submit one provider-confirmed terminal failure in an "
            "immutable retry-v1 namespace"
        ),
    )
    retry.add_argument(
        "--provider-run-id",
        required=True,
        help="exact primary provider_run_id with terminal provider-failed status",
    )
    retry.add_argument("--timeout", type=positive_int, default=1800)
    retry.add_argument("--poll-interval", type=float, default=10.0)
    retry.add_argument("--dry-run", action="store_true")
    retry.add_argument("--allow-external-processing", action="store_true")
    _add_budget(retry)

    ambiguous_retry = commands.add_parser(
        "retry-ambiguous-submit",
        help=(
            "explicitly quarantine and retry one exact-route provider submit "
            "whose primary outcome is unknown"
        ),
    )
    ambiguous_retry.add_argument(
        "--provider-run-id",
        required=True,
        help=(
            "exact primary provider_run_id with submitting or submit-unknown "
            "status"
        ),
    )
    ambiguous_retry.add_argument("--timeout", type=positive_int, default=1800)
    ambiguous_retry.add_argument("--poll-interval", type=float, default=10.0)
    ambiguous_retry.add_argument("--dry-run", action="store_true")
    ambiguous_retry.add_argument(
        "--allow-external-processing",
        action="store_true",
    )
    _add_budget(ambiguous_retry)

    normalized_retry = commands.add_parser(
        "retry-normalized-input",
        help=(
            "explicitly retry one exact input-constrained Wan primary using "
            "only its policy-bound frozen normalized image URL"
        ),
    )
    normalized_retry.add_argument(
        "--provider-run-id",
        required=True,
        help=(
            "exact allowlisted Wan 2.2 or Wan 2.7 primary provider_run_id"
        ),
    )
    normalized_retry.add_argument("--timeout", type=positive_int, default=1800)
    normalized_retry.add_argument("--poll-interval", type=float, default=10.0)
    normalized_retry.add_argument("--dry-run", action="store_true")
    normalized_retry.add_argument(
        "--allow-external-processing",
        action="store_true",
    )
    _add_budget(normalized_retry)

    normalized_supersede = commands.add_parser(
        "supersede-normalized-input",
        help=(
            "explicitly submit one separately accounted successor to the "
            "exact allowlisted active normalized-input retry job"
        ),
    )
    normalized_supersede.add_argument(
        "--provider-run-id",
        required=True,
        help="exact active normalized-input retry provider_run_id",
    )
    normalized_supersede.add_argument(
        "--operator-authorized-active-job",
        action="store_true",
        help=(
            "acknowledge the still-active old job and duplicate submission/"
            "billing risk; required for a real supersede"
        ),
    )
    normalized_supersede.add_argument("--timeout", type=positive_int, default=1800)
    normalized_supersede.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
    )
    normalized_supersede.add_argument("--dry-run", action="store_true")
    normalized_supersede.add_argument(
        "--allow-external-processing",
        action="store_true",
    )
    _add_budget(normalized_supersede)

    finalize_parser = commands.add_parser(
        "finalize", help="write the isolated PROMOPAGES-10060 Step-5 sidecar"
    )
    finalize_parser.add_argument("--allow-contract-warnings", action="store_true")
    _add_budget(finalize_parser)

    verify = commands.add_parser(
        "verify", help="verify frozen inputs, Lite provenance, receipts, media, and sidecar"
    )
    verify.add_argument("--allow-incomplete", action="store_true")
    verify.add_argument("--allow-contract-warnings", action="store_true")
    _add_budget(verify)
    return parser


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        activate_batch(args.batch)
        budget = parse_budget(args.budget_cap_usd)
        discovery = discover(root)
        if args.command == "inventory":
            document = inventory_document(discovery, budget, root)
            if not args.dry_run:
                write_inventory(discovery, budget, root)
            print(
                f"PASS: available={document['article_count']}, "
                f"unavailable={len(document['unavailable_articles'])}, "
                f"images={document['image_count']}, "
                f"outputs={document['expected_outputs']}"
            )
            return 0

        inventory = require_inventory(discovery, budget, root)
        if args.command in {"prepare-plans", "run-plans"}:
            selected = select_sources(
                discovery.sources,
                article_slugs=args.article,
                planning_run_ids=args.planning_run_id,
            )
            if args.command == "prepare-plans":
                counts = prepare_planning_runs(
                    selected, root=root, dry_run=args.dry_run
                )
                print(
                    f"PASS: selection={len(selected)}, verified={counts['verified']}, "
                    f"prepared={counts['prepared']}, pending={counts['pending']}"
                )
                return 0
            return run_planning_runs(
                selected,
                root=root,
                concurrency=args.concurrency,
                timeout=args.timeout,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                author_model=args.author_model,
            )
        if args.command == "plan-generation":
            return materialize_generation(
                discovery.sources, root=root, dry_run=args.dry_run
            )
        if args.command == "generate":
            if not args.dry_run and len(args.article) != 1:
                raise PipelineError(
                    "Real generation requires exactly one --article in ticket order"
                )
            selected = select_sources(
                discovery.sources,
                article_slugs=args.article,
            )
            return run_generation(
                discovery.sources,
                selected_sources=selected,
                root=root,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
                fail_fast=args.fail_fast,
            )
        if args.command == "retry-terminal-failure":
            return run_terminal_provider_retry(
                discovery.sources,
                inventory,
                primary_provider_run_id_value=args.provider_run_id,
                root=root,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
        if args.command == "retry-ambiguous-submit":
            return run_ambiguous_submit_retry(
                discovery.sources,
                inventory,
                primary_provider_run_id_value=args.provider_run_id,
                root=root,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
        if args.command == "retry-normalized-input":
            return run_normalized_input_retry(
                discovery.sources,
                inventory,
                primary_provider_run_id_value=args.provider_run_id,
                root=root,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
        if args.command == "supersede-normalized-input":
            return run_normalized_input_supersede(
                discovery.sources,
                inventory,
                normalized_retry_provider_run_id_value=args.provider_run_id,
                operator_authorized=args.operator_authorized_active_job,
                root=root,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
        if args.command == "finalize":
            document = finalize(
                discovery,
                inventory,
                root=root,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            print(
                f"PASS: sidecar articles={document['article_count']}, "
                f"unavailable={len(document['unavailable_articles'])}, "
                f"outputs={document['expected_outputs']}"
            )
            return 0
        if args.command == "verify":
            passed, errors = verify_all(
                discovery,
                inventory,
                root=root,
                allow_incomplete=args.allow_incomplete,
                allow_contract_warnings=args.allow_contract_warnings,
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: PROMOPAGES-10060 Clipmaker Lite batch is valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except (
        PipelineError,
        native.BatchPipelineError,
        runner.LiteRunnerError,
        transport.PipelineError,
        OSError,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
