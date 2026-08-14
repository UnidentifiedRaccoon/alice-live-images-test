#!/usr/bin/env python3
"""Coordinate the two-image PROMOPAGES live-images Clipmaker Lite batch.

The coordinator freezes exactly two article-body images, prepares one isolated
three-model Lite plan per image, and delegates provider transport to the tested
``clipmaker_lite_batch_pipeline`` bridge.  Provider retries are never automatic:
an operator must reserve either a directed prompt attempt or an autonomous Lite
attempt with no additional direction.  Each reservation receives fresh planning
and provider namespaces and is charged to the immutable batch-local budget
ledger before any paid submit can occur.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


DATASET_PREFIX = "PROMOPAGES-live-images-20260813-v1"
BATCH_ID = "promopages-live-images-20260813-v1"
TICKET = DATASET_PREFIX
AGENT_ID = "clipmaker-lite"
REQUIRED_CONTRACT_VERSION = "2.1.4"
REQUIRED_RUNNER_VERSION = 8
MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
MODEL_SUFFIXES = {
    "alibaba/wan-2.2": "wan-2-2",
    "alibaba/wan-2.7": "wan-2-7",
    "google/veo-3.1-lite": "veo-3-1-lite",
}
ROUTE_CAPACITIES = {
    "alibaba/wan-2.2": 1,
    "alibaba/wan-2.7": 3,
    "google/veo-3.1-lite": 3,
}
ROUTE_TRANSPORTS = {
    "alibaba/wan-2.2": ("eliza-segmind", "eliza-synchronous-binary"),
    "alibaba/wan-2.7": ("eliza-openrouter", "eliza-video-jobs"),
    "google/veo-3.1-lite": ("eliza-openrouter", "eliza-video-jobs"),
}

CONTRACT_REL = Path("docs/agents/clipmaker-lite/contract.json")
ROUTES_REL = Path("docs/agents/clipmaker-lite/generation-routes.json")
ARTICLE_CONFIG_REL = Path(DATASET_PREFIX) / "articles.json"
SOURCE_MANIFEST_REL = (
    Path("PROMOPAGES-9857") / DATASET_PREFIX / "articles/manifest.csv"
)
SOURCE_IMAGE_ROOT_REL = Path("PROMOPAGES-9857")
SOURCE_CONTEXT_ROOT_REL = (
    Path("PROMOPAGES-9884") / DATASET_PREFIX / "articles"
)
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
INVENTORY_REL = BATCH_ROOT_REL / "inventory.json"
GENERATION_MANIFEST_REL = BATCH_ROOT_REL / "generation-manifest.json"
ATTEMPTS_REL = BATCH_ROOT_REL / "prompt-attempts.json"
FINAL_SELECTION_REL = BATCH_ROOT_REL / "final-selection.json"
VERIFICATION_REL = BATCH_ROOT_REL / "verification.json"
OPERATOR_ACCEPTANCE_REL = BATCH_ROOT_REL / "operator-output-acceptance.json"

OPERATOR_ACCEPTANCE_CONTRACT = "clipmaker-lite-batch-operator-acceptance/v1"
OPERATOR_ACCEPTANCE_ID = "level-image-04-wan-2.7-primary-native-size-v2"

HARD_BUDGET_CAP_USD = Decimal("5.00")
ACCOUNTING_COST_PER_SUBMIT_USD = Decimal("0.35")
PRIMARY_RESERVATIONS = 6
MAX_NEW_PROMPT_ATTEMPTS = 8
MAX_TOTAL_RESERVATIONS = PRIMARY_RESERVATIONS + MAX_NEW_PROMPT_ATTEMPTS
MAX_ESTIMATED_COST_USD = ACCOUNTING_COST_PER_SUBMIT_USD * MAX_TOTAL_RESERVATIONS
AUTONOMOUS_RETRY_MODE = "clipmaker-lite-autonomous"


class PipelineError(RuntimeError):
    """Fail-closed task-specific coordinator error."""


def _canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_operator_acceptance(root: Path) -> tuple[dict[str, Any], str]:
    """Load the exact user-authorized, batch-local output acceptance."""

    path = root / OPERATOR_ACCEPTANCE_REL
    if not path.is_file():
        return {
            "schema_version": 1,
            "contract": OPERATOR_ACCEPTANCE_CONTRACT,
            "batch_id": BATCH_ID,
            "decisions": [],
        }, ""
    value = _read_json(path)
    expected_decision = {
        "decision_id": OPERATOR_ACCEPTANCE_ID,
        "scope": {
            "article_slug": "01-level-ipoteka-2026",
            "publication_id": "6a048ddca495b52c9d873940",
            "image_id": "04",
            "media_id": "6a049156a495b52c9d87cb75",
            "model_id": "alibaba/wan-2.7",
            "adapter": "eliza-openrouter",
        },
        "selected_attempt": {
            "attempt_id": "primary",
            "provider_run_id": (
                "promopages-live-images-20260813-v1-"
                "01-level-ipoteka-2026-04-wan-2-7"
            ),
        },
        "expected_media": {
            "sha256": (
                "6fc6af439367c51b2c29c04dbfdd245a2620b5db4632e3f2121c06faaffc92be"
            ),
            "bytes": 30_743_398,
            "width": 1972,
            "height": 1050,
            "duration_seconds": 5.0,
            "fps": 30.0,
            "frames": 150,
            "has_audio": True,
        },
        "expected_recorded_status": "verification-failed",
        "expected_contract_check": {
            "requested": {
                "duration_seconds": 5,
                "resolution": "1080p",
                "aspect_ratio": "16:9",
                "generate_audio": False,
                "frames": None,
                "fps": None,
            },
            "checks": {
                "duration": True,
                "audio": False,
                "resolution": False,
                "aspect_ratio": False,
            },
            "conforms": False,
            "warnings": ["audio", "resolution", "aspect_ratio"],
        },
        "inherited_policy": {
            "policy_id": "wan-2.7-openrouter-audio-v1",
            "policy_sha256": transport.OUTPUT_ACCEPTANCE_POLICY_SHA256,
        },
        "additional_waived_warnings": ["resolution", "aspect_ratio"],
        "reason": (
            "Operator selected the Level primary variant and approved provider-native "
            "dimensions for this exact output."
        ),
    }
    expected = {
        "schema_version": 1,
        "contract": OPERATOR_ACCEPTANCE_CONTRACT,
        "batch_id": BATCH_ID,
        "decisions": [expected_decision],
    }
    if value != expected:
        raise PipelineError("Batch-local operator acceptance identity differs")
    return value, _canonical_json_sha256(value)


def operator_media_acceptance(
    root: Path,
    row: Mapping[str, Any],
    media: Mapping[str, Any],
    contract_check: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Accept only the exact Level primary output authorized by the user."""

    document, policy_sha256 = load_operator_acceptance(root)
    if not document["decisions"]:
        return None
    policy = document["decisions"][0]
    scope = policy["scope"]
    selected = policy["selected_attempt"]
    expected_media = policy["expected_media"]
    if (
        (row.get("attempt_id") or row.get("selected_attempt_id"))
        != selected["attempt_id"]
        or row.get("article_slug") != scope["article_slug"]
        or row.get("publication_id") != scope["publication_id"]
        or row.get("image_id") != scope["image_id"]
        or row.get("media_id") != scope["media_id"]
        or row.get("model_id") != scope["model_id"]
        or row.get("provider_run_id") != selected["provider_run_id"]
        or row.get("recorded_status") != policy["expected_recorded_status"]
        or any(media.get(key) != expected_media[key] for key in expected_media)
        or contract_check != policy["expected_contract_check"]
    ):
        return None
    return {
        "accepted": True,
        "mode": "operator-exception",
        "policy_id": policy["decision_id"],
        "policy_sha256": policy_sha256,
        "model_id": scope["model_id"],
        "adapter": scope["adapter"],
        "target_generate_audio": False,
        "observed_has_audio": True,
        "waived_warnings": list(policy["expected_contract_check"]["warnings"]),
    }


def validate_task_media_acceptance(
    root: Path,
    row: Mapping[str, Any],
    media: Mapping[str, Any],
    contract_check: Mapping[str, Any],
    acceptance: Any,
) -> bool:
    if native.validate_media_acceptance(
        str(row.get("model_id")), dict(media), dict(contract_check), acceptance
    ):
        return True
    expected = operator_media_acceptance(root, row, media, contract_check)
    return isinstance(acceptance, dict) and expected is not None and acceptance == expected


@dataclass(frozen=True)
class ArticleSpec:
    number: str
    slug: str
    brand: str
    title: str
    url: str
    publication_id: str
    cabinet_id: str
    selected_image_id: str
    selected_media_id: str
    width: int
    height: int
    source_url: str


ARTICLE_SPECS = (
    ArticleSpec(
        number="01",
        slug="01-level-ipoteka-2026",
        brand="Level Group",
        title="Брать ипотеку в II половине 2026 года? Отвечают эксперты",
        url=(
            "https://level-group.promo.page/media/"
            "brat-ipoteku-v-ii-polovine-2026-goda-otvechaiut-eksperty-"
            "6a048ddca495b52c9d873940_0_0"
        ),
        publication_id="6a048ddca495b52c9d873940",
        cabinet_id="69ee06293ba10e0ae4b765d1",
        selected_image_id="04",
        selected_media_id="6a049156a495b52c9d87cb75",
        width=1920,
        height=1023,
        source_url=(
            "https://avatars.mds.yandex.net/get-promoarticles/6165752/"
            "pub_6a048ddca495b52c9d873940_6a049156a495b52c9d87cb75/orig"
        ),
    ),
    ArticleSpec(
        number="02",
        slug="02-banki-vygodno-kupit-dollar",
        brand="Банки.ру",
        title="В каких банках можно выгодно купить доллар?",
        url=(
            "https://banki.promo.page/save/"
            "v-kakih-bankah-mojno-vygodno-kupit-dollar-"
            "6a4f5fe924801975680d9be5_0_0"
        ),
        publication_id="6a4f5fe924801975680d9be5",
        cabinet_id="5b0fb7c448c85e2421e049ab",
        selected_image_id="01",
        selected_media_id="6a4f718952e3ce75a3110deb",
        width=2000,
        height=1125,
        source_url=(
            "https://avatars.mds.yandex.net/get-promoarticles/5126709/"
            "pub_6a4f5fe924801975680d9be5_6a4f718952e3ce75a3110deb/orig"
        ),
    ),
)


@dataclass(frozen=True)
class NamespacedSample:
    sample_id: str
    article_slug: str
    image_id: str
    filename: str
    source_sha256: str
    width: int
    height: int
    bound_source_path: str
    bound_context_path: str
    bound_planning_run_id: str

    @property
    def source_path(self) -> str:
        return self.bound_source_path

    @property
    def context_path(self) -> str:
        return self.bound_context_path

    @property
    def planning_run_id(self) -> str:
        return self.bound_planning_run_id


@dataclass(frozen=True)
class Source:
    spec: ArticleSpec
    filename: str
    source_path: str
    source_sha256: str
    context_path: str
    context_sha256: str
    caption: str
    role: str

    @property
    def sample_id(self) -> str:
        return f"{self.spec.slug}-{self.spec.selected_image_id}"

    @property
    def planning_run_id(self) -> str:
        return f"{BATCH_ID}-{self.sample_id}"

    def sample_for_planning(self, planning_run_id: str | None = None) -> NamespacedSample:
        return NamespacedSample(
            sample_id=self.sample_id,
            article_slug=self.spec.slug,
            image_id=self.spec.selected_image_id,
            filename=self.filename,
            source_sha256=self.source_sha256,
            width=self.spec.width,
            height=self.spec.height,
            bound_source_path=self.source_path,
            bound_context_path=self.context_path,
            bound_planning_run_id=planning_run_id or self.planning_run_id,
        )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PipelineError(f"JSON file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"Cannot read JSON {path}: {exc}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PipelineError(f"Cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise PipelineError(f"Path escapes workspace: {path}") from exc


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    transport.atomic_write_json(path, dict(value))


def _contract_snapshot(root: Path) -> dict[str, Any]:
    path = root / CONTRACT_REL
    value = _read_json(path)
    runner_value = value.get("runner") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("agent_id") != AGENT_ID
        or value.get("contract_version") != REQUIRED_CONTRACT_VERSION
        or list(value.get("models", {})) != list(MODEL_IDS)
        or not isinstance(runner_value, dict)
        or runner_value.get("runner_version") != REQUIRED_RUNNER_VERSION
    ):
        raise PipelineError("Unexpected current Clipmaker Lite contract snapshot")
    return {
        "path": CONTRACT_REL.as_posix(),
        "sha256": _sha256_file(path),
        "contract_version": REQUIRED_CONTRACT_VERSION,
        "runner_version": REQUIRED_RUNNER_VERSION,
    }


def _route_snapshot(root: Path) -> dict[str, Any]:
    path = root / ROUTES_REL
    value = _read_json(path)
    policy = value.get("policy") if isinstance(value, dict) else None
    models = value.get("models") if isinstance(value, dict) else None
    if policy != {
        "resolution": "exact-model-id",
        "automatic_fallback": False,
        "normal_run_discovery": False,
        "forbidden_discovery_paths": ["/videos/models", "/gradio_api/info", "/config"],
    } or not isinstance(models, dict) or list(models) != list(MODEL_IDS):
        raise PipelineError("Generation route registry policy changed")
    routes: dict[str, Any] = {}
    for model_id in MODEL_IDS:
        route = models[model_id]
        expected_adapter, expected_transport = ROUTE_TRANSPORTS[model_id]
        if (
            route.get("capacity") != ROUTE_CAPACITIES[model_id]
            or route.get("adapter") != expected_adapter
            or route.get("transport") != expected_transport
        ):
            raise PipelineError(f"Generation route changed for {model_id}")
        routes[model_id] = {
            "adapter": expected_adapter,
            "transport": expected_transport,
            "capacity": ROUTE_CAPACITIES[model_id],
        }
    return {
        "path": ROUTES_REL.as_posix(),
        "sha256": _sha256_file(path),
        "policy": policy,
        "models": routes,
    }


def _validate_article_config(root: Path) -> dict[str, Any]:
    path = root / ARTICLE_CONFIG_REL
    value = _read_json(path)
    if not isinstance(value, list) or len(value) != len(ARTICLE_SPECS):
        raise PipelineError("Dataset articles.json must contain exactly two articles")
    for raw, spec in zip(value, ARTICLE_SPECS):
        if not isinstance(raw, dict):
            raise PipelineError("Dataset article config row is not an object")
        actual_number = raw.get("number")
        if actual_number not in {int(spec.number), spec.number}:
            raise PipelineError(f"Unexpected article number for {spec.slug}")
        if raw.get("folder") != spec.slug or raw.get("url") != spec.url:
            raise PipelineError(f"Dataset article config differs for {spec.slug}")
    return {"path": ARTICLE_CONFIG_REL.as_posix(), "sha256": _sha256_file(path)}


def _manifest_rows(root: Path) -> list[dict[str, str]]:
    path = root / SOURCE_MANIFEST_REL
    required = {
        "article_number",
        "article_url",
        "image_number",
        "image_role",
        "image_id",
        "orig_url",
        "file_path",
        "actual_width",
        "actual_height",
        "sha256",
        "download_status",
    }
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise PipelineError(f"Source manifest is missing fields: {sorted(missing)}")
            rows = list(reader)
    except OSError as exc:
        raise PipelineError(f"Cannot read source manifest {path}: {exc}") from exc
    if not rows:
        raise PipelineError("Source manifest has no rows")
    return rows


def discover(root: Path = ROOT) -> tuple[Source, ...]:
    """Bind the exact two eligible article images and reject input drift."""

    _validate_article_config(root)
    rows = _manifest_rows(root)
    by_path: dict[str, dict[str, str]] = {}
    for row in rows:
        file_path = row.get("file_path", "")
        pure = PurePosixPath(file_path)
        if (
            pure.is_absolute()
            or len(pure.parts) != 4
            or pure.parts[0] != DATASET_PREFIX
            or pure.parts[1] != "articles"
            or ".." in pure.parts
            or row.get("download_status") != "ok"
        ):
            raise PipelineError(f"Invalid namespaced source row: {file_path!r}")
        if file_path in by_path:
            raise PipelineError(f"Duplicate source manifest path: {file_path}")
        by_path[file_path] = row

    sources: list[Source] = []
    seen_context_paths: set[str] = set()
    for spec in ARTICLE_SPECS:
        context_path = root / SOURCE_CONTEXT_ROOT_REL / spec.slug / "content.json"
        if not context_path.is_file() or context_path.is_symlink():
            raise PipelineError(f"Missing regular article context: {context_path}")
        context = _read_json(context_path)
        if (
            not isinstance(context, dict)
            or context.get("publication_id") != spec.publication_id
            or context.get("url") != spec.url
            or not isinstance(context.get("blocks"), list)
        ):
            raise PipelineError(f"Article context identity differs: {spec.slug}")
        image_blocks = [
            block
            for block in context["blocks"]
            if isinstance(block, dict) and block.get("type") == "image"
        ]
        if spec.number == "01":
            roles = [(block.get("image_id"), block.get("role")) for block in image_blocks]
            if roles != [
                ("01", "cover"),
                ("02", "article_image"),
                ("03", "article_image"),
                ("04", "article_image"),
            ]:
                raise PipelineError("Level image sequence changed; refusing graph animation")
        elif len(image_blocks) != 1 or image_blocks[0].get("role") != "article_image":
            raise PipelineError("Банки.ру must have one body image and no cover block")

        for block in image_blocks:
            manifest_path = block.get("manifest_file_path")
            if not isinstance(manifest_path, str) or manifest_path not in by_path:
                raise PipelineError(f"Context image is absent from manifest: {manifest_path!r}")
            if manifest_path in seen_context_paths:
                raise PipelineError(f"Context image is duplicated: {manifest_path}")
            seen_context_paths.add(manifest_path)

        matches = [
            block
            for block in image_blocks
            if block.get("image_id") == spec.selected_image_id
            and block.get("source_image_id") == spec.selected_media_id
        ]
        if len(matches) != 1:
            raise PipelineError(f"Selected image binding changed: {spec.slug}")
        block = matches[0]
        if block.get("role") != "article_image":
            raise PipelineError(f"Selected image is not a body image: {spec.slug}")
        manifest_path = block["manifest_file_path"]
        row = by_path[manifest_path]
        try:
            dimensions = (int(row["actual_width"]), int(row["actual_height"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PipelineError(f"Invalid image dimensions: {manifest_path}") from exc
        if (
            row.get("article_number") != spec.number
            or row.get("article_url") != spec.url
            or row.get("image_number") != spec.selected_image_id
            or row.get("image_role") != "article_image"
            or row.get("image_id") != spec.selected_media_id
            or row.get("orig_url") != spec.source_url
            or dimensions != (spec.width, spec.height)
        ):
            raise PipelineError(f"Selected source manifest binding changed: {spec.slug}")
        source_path = root / SOURCE_IMAGE_ROOT_REL / manifest_path
        if not source_path.is_file() or source_path.is_symlink():
            raise PipelineError(f"Missing regular source image: {source_path}")
        digest = _sha256_file(source_path)
        if digest != row.get("sha256"):
            raise PipelineError(f"Source image digest mismatch: {source_path}")
        sources.append(
            Source(
                spec=spec,
                filename=str(block.get("file")),
                source_path=_relative(source_path, root),
                source_sha256=digest,
                context_path=_relative(context_path, root),
                context_sha256=_sha256_file(context_path),
                caption=str(block.get("caption") or ""),
                role="article_image",
            )
        )

    if seen_context_paths != set(by_path):
        raise PipelineError(
            "Article contexts and source manifest differ: "
            f"missing={sorted(set(by_path) - seen_context_paths)}, "
            f"extra={sorted(seen_context_paths - set(by_path))}"
        )
    if len(sources) != 2 or len({source.sample_id for source in sources}) != 2:
        raise PipelineError("Expected exactly two unique selected sources")
    return tuple(sources)


def _cost_document(retry_reservations: int = 0) -> dict[str, Any]:
    if retry_reservations < 0 or retry_reservations > MAX_NEW_PROMPT_ATTEMPTS:
        raise PipelineError("Retry reservation count exceeds the batch policy")
    total = PRIMARY_RESERVATIONS + retry_reservations
    estimated = ACCOUNTING_COST_PER_SUBMIT_USD * total
    if total > MAX_TOTAL_RESERVATIONS or estimated > HARD_BUDGET_CAP_USD:
        raise PipelineError("Paid submit reservation exceeds the hard $5 budget")
    return {
        "hard_budget_cap_usd": float(HARD_BUDGET_CAP_USD),
        "accounting_cost_per_submit_usd": float(ACCOUNTING_COST_PER_SUBMIT_USD),
        "primary_reservations": PRIMARY_RESERVATIONS,
        "maximum_new_prompt_attempts": MAX_NEW_PROMPT_ATTEMPTS,
        "retry_reservations": retry_reservations,
        "total_reservations": total,
        "maximum_total_reservations": MAX_TOTAL_RESERVATIONS,
        "estimated_reserved_cost_usd": float(estimated),
        "maximum_estimated_cost_usd": float(MAX_ESTIMATED_COST_USD),
        "headroom_usd": float(HARD_BUDGET_CAP_USD - estimated),
    }


def inventory_document(sources: Sequence[Source], root: Path = ROOT) -> dict[str, Any]:
    if len(sources) != 2:
        raise PipelineError("Inventory requires exactly two sources")
    return {
        "schema_version": 1,
        "manifest_role": "promopages-live-images-frozen-generation-inventory",
        "dataset_prefix": DATASET_PREFIX,
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "article_config": _validate_article_config(root),
        "source_manifest": {
            "path": SOURCE_MANIFEST_REL.as_posix(),
            "sha256": _sha256_file(root / SOURCE_MANIFEST_REL),
        },
        "contract": _contract_snapshot(root),
        "generation_routes": _route_snapshot(root),
        "models": list(MODEL_IDS),
        "article_count": 2,
        "image_count": 2,
        "expected_outputs": PRIMARY_RESERVATIONS,
        "selection_rule": (
            "exclude all covers; exclude Level body graphs 02 and 03; select "
            "Level body image 04 and the sole Банки.ру body image 01"
        ),
        "generation_policy": {
            "independent_route_pools": True,
            "route_capacities": dict(ROUTE_CAPACITIES),
            "exact_model_routes_only": True,
            "route_discovery": False,
            "automatic_fallback": False,
            "automatic_paid_retry": False,
            "aggregate_manifest_writer": "coordinator-only",
        },
        "cost": _cost_document(),
        "articles": [
            {
                "article_number": source.spec.number,
                "article_slug": source.spec.slug,
                "brand": source.spec.brand,
                "title": source.spec.title,
                "url": source.spec.url,
                "publication_id": source.spec.publication_id,
                "context": {
                    "path": source.context_path,
                    "sha256": source.context_sha256,
                },
                "image": {
                    "image_id": source.spec.selected_image_id,
                    "media_id": source.spec.selected_media_id,
                    "role": source.role,
                    "file": source.filename,
                    "source_path": source.source_path,
                    "source_url": source.spec.source_url,
                    "sha256": source.source_sha256,
                    "width": source.spec.width,
                    "height": source.spec.height,
                    "caption": source.caption,
                },
                "planning_run_id": source.planning_run_id,
            }
            for source in sources
        ],
    }


def write_inventory(sources: Sequence[Source], root: Path = ROOT) -> dict[str, Any]:
    expected = inventory_document(sources, root)
    path = root / INVENTORY_REL
    if path.exists():
        if not path.is_file() or path.is_symlink() or _read_json(path) != expected:
            raise PipelineError(f"Immutable inventory differs: {path}")
        return expected
    _atomic_write(path, expected)
    return expected


def require_inventory(sources: Sequence[Source], root: Path = ROOT) -> dict[str, Any]:
    expected = inventory_document(sources, root)
    path = root / INVENTORY_REL
    if not path.is_file() or path.is_symlink() or _read_json(path) != expected:
        raise PipelineError("Frozen inventory is missing or differs; run inventory first")
    return expected


def _empty_attempt_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": "promopages-live-images-prompt-attempt-ledger",
        "batch_id": BATCH_ID,
        "agent_id": AGENT_ID,
        "cost": _cost_document(),
        "attempts": [],
    }


def load_attempt_registry(root: Path = ROOT) -> dict[str, Any]:
    path = root / ATTEMPTS_REL
    value = _read_json(path) if path.is_file() else _empty_attempt_registry()
    attempts = value.get("attempts") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("manifest_role") != "promopages-live-images-prompt-attempt-ledger"
        or value.get("batch_id") != BATCH_ID
        or value.get("agent_id") != AGENT_ID
        or not isinstance(attempts, list)
        or value.get("cost") != _cost_document(len(attempts))
    ):
        raise PipelineError("Prompt attempt ledger identity or budget differs")
    seen: set[str] = set()
    for ordinal, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, dict):
            raise PipelineError("Prompt attempt ledger contains a non-object")
        attempt_id = f"retry-{ordinal:02d}"
        required = {
            "attempt_id": attempt_id,
            "ordinal": ordinal,
            "accounting_reservation_usd": float(ACCOUNTING_COST_PER_SUBMIT_USD),
        }
        if any(attempt.get(key) != expected for key, expected in required.items()):
            raise PipelineError(f"Prompt attempt ledger order differs: {attempt_id}")
        if attempt_id in seen:
            raise PipelineError(f"Duplicate prompt attempt: {attempt_id}")
        direction = attempt.get("direction")
        retry_mode = attempt.get("retry_mode")
        if retry_mode == AUTONOMOUS_RETRY_MODE:
            if direction is not None:
                raise PipelineError(
                    f"Autonomous prompt attempt has a direction: {attempt_id}"
                )
        elif retry_mode is None:
            if not isinstance(direction, str) or not direction.strip():
                raise PipelineError(
                    f"Directed prompt attempt has no direction: {attempt_id}"
                )
        else:
            raise PipelineError(f"Unknown prompt retry mode: {attempt_id}")
        seen.add(attempt_id)
    return value


def _primary_provider_run_id(source: Source, model_id: str) -> str:
    return f"{BATCH_ID}-{source.sample_id}-{MODEL_SUFFIXES[model_id]}"


def _resolve_primary_target(
    sources: Sequence[Source], provider_run_id: str
) -> tuple[Source, str]:
    matches = [
        (source, model_id)
        for source in sources
        for model_id in MODEL_IDS
        if _primary_provider_run_id(source, model_id) == provider_run_id
    ]
    if len(matches) != 1:
        raise PipelineError(f"Unknown primary provider run ID: {provider_run_id}")
    return matches[0]


def reserve_retry(
    sources: Sequence[Source],
    provider_run_id: str,
    direction: str | None,
    root: Path = ROOT,
    *,
    autonomous: bool = False,
) -> dict[str, Any]:
    if autonomous:
        if direction is not None:
            raise PipelineError("Autonomous retry must not include a direction")
    else:
        if not isinstance(direction, str) or not direction.strip():
            raise PipelineError("Retry direction must be non-empty")
        direction = direction.strip()
    source, model_id = _resolve_primary_target(sources, provider_run_id)
    registry = load_attempt_registry(root)
    attempts = list(registry["attempts"])
    if not autonomous:
        for attempt in attempts:
            if (
                attempt.get("primary_provider_run_id") == provider_run_id
                and attempt.get("direction") == direction
                and attempt.get("retry_mode") is None
            ):
                return attempt
    if len(attempts) >= MAX_NEW_PROMPT_ATTEMPTS:
        raise PipelineError("All eight new prompt-attempt reservations are exhausted")
    ordinal = len(attempts) + 1
    attempt_id = f"retry-{ordinal:02d}"
    planning_run_id = f"{BATCH_ID}-{attempt_id}-{source.sample_id}"
    provider_batch_id = f"{BATCH_ID}-{attempt_id}"
    attempt = {
        "attempt_id": attempt_id,
        "ordinal": ordinal,
        "logical_output": {
            "article_slug": source.spec.slug,
            "image_id": source.spec.selected_image_id,
            "model_id": model_id,
        },
        "primary_provider_run_id": provider_run_id,
        "direction": direction,
        "planning_run_id": planning_run_id,
        "provider_batch_id": provider_batch_id,
        "provider_run_id": (
            f"{provider_batch_id}-{source.sample_id}-{MODEL_SUFFIXES[model_id]}"
        ),
        "accounting_reservation_usd": float(ACCOUNTING_COST_PER_SUBMIT_USD),
    }
    if autonomous:
        attempt["retry_mode"] = AUTONOMOUS_RETRY_MODE
    attempts.append(attempt)
    updated = dict(registry)
    updated["attempts"] = attempts
    updated["cost"] = _cost_document(len(attempts))
    _atomic_write(root / ATTEMPTS_REL, updated)
    return attempt


def _attempt_by_id(root: Path, attempt_id: str) -> dict[str, Any]:
    registry = load_attempt_registry(root)
    matches = [item for item in registry["attempts"] if item["attempt_id"] == attempt_id]
    if len(matches) != 1:
        raise PipelineError(f"Unknown prompt attempt: {attempt_id}")
    return matches[0]


def _source_for_attempt(sources: Sequence[Source], attempt: Mapping[str, Any]) -> Source:
    key = attempt.get("logical_output")
    matches = [
        source
        for source in sources
        if isinstance(key, dict)
        and source.spec.slug == key.get("article_slug")
        and source.spec.selected_image_id == key.get("image_id")
    ]
    if len(matches) != 1 or key.get("model_id") not in MODEL_IDS:
        raise PipelineError(f"Retry logical output is invalid: {attempt.get('attempt_id')}")
    return matches[0]


def _planning_targets(
    sources: Sequence[Source], root: Path, attempt_id: str | None
) -> list[tuple[Source, str, str | None]]:
    if attempt_id is None:
        return [(source, source.planning_run_id, None) for source in sources]
    attempt = _attempt_by_id(root, attempt_id)
    direction = attempt.get("direction")
    if direction is None:
        if attempt.get("retry_mode") != AUTONOMOUS_RETRY_MODE:
            raise PipelineError(f"Retry direction is invalid: {attempt_id}")
    elif not isinstance(direction, str) or not direction.strip():
        raise PipelineError(f"Retry direction is invalid: {attempt_id}")
    return [
        (
            _source_for_attempt(sources, attempt),
            str(attempt["planning_run_id"]),
            direction,
        )
    ]


def _planning_state(
    source: Source,
    planning_run_id: str,
    root: Path,
    expected_direction: str | None,
) -> str | None:
    directory = root / "artifacts/clipmaker-lite/v1" / planning_run_id
    if (directory / "result.json").is_file():
        summary = runner.provenance_summary(root, planning_run_id)
        result = _read_json(directory / "result.json")
        if (
            summary.get("verified") is not True
            or summary.get("agent_id") != AGENT_ID
            or summary.get("contract_version") != REQUIRED_CONTRACT_VERSION
            or summary.get("models") != list(MODEL_IDS)
            or summary.get("source_image_sha256") != source.source_sha256
            or summary.get("article_context_sha256") != source.context_sha256
            or not isinstance(result.get("inputs"), dict)
            or result["inputs"].get("user_direction") != expected_direction
        ):
            raise PipelineError(f"Planning provenance differs: {planning_run_id}")
        return "verified"
    if (directory / "job.json").is_file():
        job, selection, _directory = runner.validate_prepared_job(root, planning_run_id)
        selected = [item.get("model_id") for item in selection.get("selected_models", [])]
        if (
            selected != list(MODEL_IDS)
            or not isinstance(job.get("inputs"), dict)
            or job["inputs"].get("user_direction") != expected_direction
        ):
            raise PipelineError(f"Prepared planning model set differs: {planning_run_id}")
        return "prepared"
    return None


def prepare_plans(
    sources: Sequence[Source], *, root: Path, attempt_id: str | None, dry_run: bool
) -> dict[str, int]:
    counts = {"verified": 0, "prepared": 0, "pending": 0}
    for source, planning_run_id, direction in _planning_targets(sources, root, attempt_id):
        state = _planning_state(source, planning_run_id, root, direction)
        if state is not None:
            counts[state] += 1
            continue
        if dry_run:
            counts["pending"] += 1
            continue
        command = [
            sys.executable,
            str(root / "scripts/clipmaker_lite_runner.py"),
            "prepare",
            "--run-id",
            planning_run_id,
            "--image",
            source.source_path,
            "--context",
            source.context_path,
            "--image-id",
            source.spec.selected_image_id,
        ]
        for model_id in MODEL_IDS:
            command.extend(("--model", model_id))
        if direction is not None:
            command.extend(("--direction", direction))
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if (
            completed.returncode
            or _planning_state(source, planning_run_id, root, direction) != "prepared"
        ):
            raise PipelineError(
                f"Planning prepare failed for {planning_run_id}: "
                f"{transport.safe_error(completed.stderr or completed.stdout)}"
            )
        counts["prepared"] += 1
    return counts


def run_plans(
    sources: Sequence[Source],
    *,
    root: Path,
    attempt_id: str | None,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
) -> int:
    targets = _planning_targets(sources, root, attempt_id)
    prepare_plans(sources, root=root, attempt_id=attempt_id, dry_run=dry_run)
    if dry_run:
        for _source, run_id, _direction in targets:
            print(f"planning {run_id} -> would-run")
        return 0
    if not allow_external_processing:
        raise PipelineError("Real Lite planning requires --allow-external-processing")
    for source, planning_run_id, _direction in targets:
        if _planning_state(source, planning_run_id, root, _direction) == "verified":
            continue
        command = [
            sys.executable,
            str(root / "scripts/clipmaker_lite_runner.py"),
            "run",
            "--run-id",
            planning_run_id,
            "--timeout",
            str(timeout),
            "--allow-external-processing",
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 60,
            check=False,
        )
        if (
            completed.returncode
            or _planning_state(source, planning_run_id, root, _direction) != "verified"
        ):
            raise PipelineError(
                f"Planning run failed for {planning_run_id}: "
                f"{transport.safe_error(completed.stderr or completed.stdout)}"
            )
    return 0


def _primary_paths(entry: native.Entry, root: Path) -> dict[str, Path]:
    base = (
        root
        / BATCH_ROOT_REL
        / "videos/primary"
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


def _retry_paths(attempt: Mapping[str, Any], entry: native.Entry, root: Path) -> dict[str, Path]:
    base = (
        root
        / BATCH_ROOT_REL
        / "attempts"
        / str(attempt["attempt_id"])
        / "videos"
        / native.MODEL_DIRECTORIES[entry.model_id]
    )
    stem = entry.sample.image_id
    return {
        "directory": base,
        "prompt": base / f"{stem}.prompt.json",
        "run": base / f"{stem}.run.json",
        "video": base / f"{stem}.mp4",
    }


def configure_native(
    sources: Sequence[Source], root: Path = ROOT, attempt: Mapping[str, Any] | None = None
) -> None:
    """Bind the generic bridge to either the primary matrix or one retry."""

    _contract_snapshot(root)
    _route_snapshot(root)
    if attempt is None:
        selected_sources = tuple(sources)
        model_ids = MODEL_IDS
        provider_batch_id = BATCH_ID
        manifest_rel = GENERATION_MANIFEST_REL
        samples = tuple(source.sample_for_planning() for source in selected_sources)
    else:
        source = _source_for_attempt(sources, attempt)
        selected_sources = (source,)
        model_ids = (str(attempt["logical_output"]["model_id"]),)
        provider_batch_id = str(attempt["provider_batch_id"])
        manifest_rel = (
            BATCH_ROOT_REL
            / "attempts"
            / str(attempt["attempt_id"])
            / "generation-manifest.json"
        )
        samples = (
            source.sample_for_planning(str(attempt["planning_run_id"])),
        )

    by_sample_id = {source.sample_id: source for source in selected_sources}
    native.BATCH_ID = provider_batch_id
    native.PLANNING_BATCH_ID = BATCH_ID
    native.MODEL_IDS = tuple(model_ids)
    native.PLANNING_MODEL_IDS = MODEL_IDS
    native.TICKET = TICKET
    native.MANIFEST_PATH = manifest_rel
    native.CONTRACT_PATH = root / CONTRACT_REL
    native.PLANNING_WORKSPACE = None
    native.PLANNING_PROVENANCE_VERIFIER = runner.provenance_summary
    native.SAMPLES = samples
    native.WAN_SUBMIT_MODE = None
    native.SCHEDULING_EXCLUDED_RUN_IDS = frozenset()

    def provider_sample(entry: native.Entry) -> dict[str, Any]:
        source = by_sample_id.get(entry.sample.sample_id)
        if source is None:
            raise PipelineError(f"Unknown provider sample: {entry.sample.sample_id}")
        return {
            "sample_id": source.sample_id,
            "article_slug": source.spec.slug,
            "image_id": source.spec.selected_image_id,
            "image_number": source.spec.selected_image_id,
            "source_path": source.source_path,
            "source_url": source.spec.source_url,
            "sha256": source.source_sha256,
            "width": source.spec.width,
            "height": source.spec.height,
        }

    def artifact_paths(entry: native.Entry, workspace: Path = root) -> dict[str, Path]:
        return (
            _primary_paths(entry, workspace)
            if attempt is None
            else _retry_paths(attempt, entry, workspace)
        )

    native.provider_sample = provider_sample
    native.artifact_paths = artifact_paths
    expected = len(selected_sources) * len(model_ids)
    if len(native.matrix()) != expected:
        raise PipelineError("Native provider matrix size changed")


def materialize(
    sources: Sequence[Source], *, root: Path, attempt_id: str | None, dry_run: bool
) -> int:
    attempt = _attempt_by_id(root, attempt_id) if attempt_id else None
    configure_native(sources, root, attempt)
    expected = 1 if attempt else PRIMARY_RESERVATIONS
    if dry_run:
        for entry in native.matrix():
            job = native.load_lite_job(entry, root)
            native.provider_request_preview(
                native.provider_sample(entry), native.provider_prompt(job)
            )
        print(f"PASS: validated {expected} exact provider request(s); no files written")
        return 0
    rows = native.materialize(root)
    if len(rows) != expected:
        raise PipelineError(f"Expected {expected} provider jobs, got {len(rows)}")
    return 0


def _native_args(
    *, dry_run: bool, allow_external_processing: bool, timeout: int, poll_interval: float
) -> argparse.Namespace:
    return argparse.Namespace(
        run_id=[],
        model=[],
        dry_run=dry_run,
        force=False,
        fail_fast=False,
        concurrency=3,
        wan22_concurrency=1,
        wan27_concurrency=3,
        veo31_concurrency=3,
        timeout=timeout,
        poll_interval=poll_interval,
        allow_external_processing=allow_external_processing,
        segmind_base_url=transport.DEFAULT_SEGMIND_BASE_URL,
        wan_base_url=None,
        wan_stream_base_url=None,
        eliza_base_url=transport.DEFAULT_ELIZA_BASE_URL,
    )


def generate(
    sources: Sequence[Source],
    *,
    root: Path,
    attempt_id: str | None,
    dry_run: bool,
    allow_external_processing: bool,
    timeout: int,
    poll_interval: float,
) -> int:
    attempt = _attempt_by_id(root, attempt_id) if attempt_id else None
    configure_native(sources, root, attempt)
    rows = native.materialize(root)
    failures = native.run_selected(
        rows,
        _native_args(
            dry_run=dry_run,
            allow_external_processing=allow_external_processing,
            timeout=timeout,
            poll_interval=poll_interval,
        ),
        root,
    )
    native.write_manifest(rows, root)
    return 1 if failures else 0


def _attempt_artifacts(
    sources: Sequence[Source], root: Path, attempt: Mapping[str, Any] | None
) -> list[dict[str, Any]]:
    configure_native(sources, root, attempt)
    rows: list[dict[str, Any]] = []
    attempt_id = "primary" if attempt is None else str(attempt["attempt_id"])
    for entry in native.matrix():
        paths = native.artifact_paths(entry, root)
        prompt = _read_json(paths["prompt"]) if paths["prompt"].is_file() else None
        receipt = _read_json(paths["run"]) if paths["run"].is_file() else None
        status = str(receipt.get("status", "missing")) if isinstance(receipt, dict) else "missing"
        error = receipt.get("error") if isinstance(receipt, dict) else "missing run receipt"
        media = None
        contract_check = None
        media_acceptance = None
        accepted = False
        if paths["video"].is_file() and isinstance(receipt, dict):
            try:
                media = transport.ffprobe_media(paths["video"])
                contract_check = native.strict_media_contract(entry, media)
                media_acceptance = native.media_acceptance(
                    entry, media, contract_check
                )
                if media_acceptance.get("accepted") is not True:
                    operator_acceptance = operator_media_acceptance(
                        root,
                        {
                            "attempt_id": attempt_id,
                            "article_slug": entry.sample.article_slug,
                            "publication_id": next(
                                spec.publication_id
                                for spec in ARTICLE_SPECS
                                if spec.slug == entry.sample.article_slug
                            ),
                            "image_id": entry.sample.image_id,
                            "media_id": next(
                                spec.selected_media_id
                                for spec in ARTICLE_SPECS
                                if spec.slug == entry.sample.article_slug
                            ),
                            "model_id": entry.model_id,
                            "provider_run_id": entry.provider_run_id,
                            "recorded_status": status,
                        },
                        media,
                        contract_check,
                    )
                    if operator_acceptance is not None:
                        media_acceptance = operator_acceptance
                accepted_status = (
                    status == "succeeded"
                    if media_acceptance.get("mode") == "strict-contract"
                    else status == "verification-failed"
                )
                accepted = (
                    media_acceptance.get("accepted") is True
                    and accepted_status
                    and receipt.get("media") == media
                    and receipt.get("contract_check") == contract_check
                )
                if not accepted and error is None:
                    error = "selected media did not pass an explicit acceptance policy"
            except (OSError, transport.PipelineError, native.BatchPipelineError) as exc:
                error = transport.safe_error(exc)
        rows.append(
            {
                "attempt_id": attempt_id,
                "article_slug": entry.sample.article_slug,
                "image_id": entry.sample.image_id,
                "model_id": entry.model_id,
                "planning_run_id": entry.planning_run_id,
                "provider_run_id": entry.provider_run_id,
                "status": "succeeded" if accepted else status,
                "recorded_status": status,
                "accepted": accepted,
                "prompt": (
                    prompt.get("prompt")
                    if isinstance(prompt, dict) and isinstance(prompt.get("prompt"), dict)
                    else None
                ),
                "prompt_path": _relative(paths["prompt"], root) if paths["prompt"].is_file() else None,
                "run_path": _relative(paths["run"], root) if paths["run"].is_file() else None,
                "video_path": _relative(paths["video"], root) if paths["video"].is_file() else None,
                "media": media,
                "contract_check": contract_check,
                "media_acceptance": media_acceptance,
                "provider_response": (
                    receipt.get("provider_response")
                    if isinstance(receipt, dict)
                    and isinstance(receipt.get("provider_response"), dict)
                    else None
                ),
                "error": error,
            }
        )
    return rows


def build_final_selection(
    sources: Sequence[Source],
    *,
    root: Path,
    selected_attempt_ids: Iterable[str] = (),
) -> dict[str, Any]:
    registry = load_attempt_registry(root)
    retry_attempts = list(registry["attempts"])
    all_attempts = _attempt_artifacts(sources, root, None)
    for attempt in retry_attempts:
        all_attempts.extend(_attempt_artifacts(sources, root, attempt))
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in all_attempts:
        key = (row["article_slug"], row["image_id"], row["model_id"])
        by_key.setdefault(key, []).append(row)

    requested = set(selected_attempt_ids)
    known_retry_ids = {attempt["attempt_id"] for attempt in retry_attempts}
    if requested - known_retry_ids:
        raise PipelineError(
            "Unknown selected attempt IDs: " + ", ".join(sorted(requested - known_retry_ids))
        )
    selected_by_key: dict[tuple[str, str, str], str] = {}
    for attempt in retry_attempts:
        if attempt["attempt_id"] not in requested:
            continue
        logical = attempt["logical_output"]
        key = (logical["article_slug"], logical["image_id"], logical["model_id"])
        if key in selected_by_key:
            raise PipelineError(f"More than one selected retry for logical output: {key}")
        selected_by_key[key] = attempt["attempt_id"]

    outputs: list[dict[str, Any]] = []
    for source in sources:
        for model_id in MODEL_IDS:
            key = (source.spec.slug, source.spec.selected_image_id, model_id)
            attempts = by_key.get(key, [])
            preferred = selected_by_key.get(key, "primary")
            choices = [row for row in attempts if row["attempt_id"] == preferred]
            if len(choices) != 1:
                raise PipelineError(f"Selected attempt is missing for logical output: {key}")
            chosen = choices[0]
            accepted = chosen["accepted"] is True
            attempts_summary = [
                {
                    "attempt_id": row["attempt_id"],
                    "status": row["status"],
                    "recorded_status": row["recorded_status"],
                    "prompt": row["prompt"],
                    "provider_run_id": row["provider_run_id"],
                    "provider_response": row.get("provider_response"),
                    "media": row["media"],
                    "contract_check": row["contract_check"],
                    "media_acceptance": row["media_acceptance"],
                    "error": row["error"],
                }
                for row in attempts
            ]
            outputs.append(
                {
                    "article_number": source.spec.number,
                    "article_slug": source.spec.slug,
                    "publication_id": source.spec.publication_id,
                    "image_id": source.spec.selected_image_id,
                    "media_id": source.spec.selected_media_id,
                    "model_id": model_id,
                    "status": "succeeded" if accepted else "unavailable",
                    "recorded_status": chosen["recorded_status"] if accepted else None,
                    "selected_attempt_id": chosen["attempt_id"] if accepted else None,
                    "selected_prompt": chosen["prompt"] if accepted else None,
                    "provider_run_id": chosen["provider_run_id"] if accepted else None,
                    "video_path": chosen["video_path"] if accepted else None,
                    "media": chosen["media"] if accepted else None,
                    "contract_check": chosen["contract_check"] if accepted else None,
                    "media_acceptance": chosen["media_acceptance"] if accepted else None,
                    "error": None if accepted else str(chosen["error"] or chosen["status"]),
                    "attempt_count": len(attempts),
                    "attempts": attempts_summary,
                }
            )

    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-final-selection",
        "dataset_prefix": DATASET_PREFIX,
        "batch_id": BATCH_ID,
        "producer": {
            "agent_id": AGENT_ID,
            "contract_version": REQUIRED_CONTRACT_VERSION,
            "runner_version": REQUIRED_RUNNER_VERSION,
        },
        "models": list(MODEL_IDS),
        "article_count": 2,
        "image_count": 2,
        "expected_outputs": PRIMARY_RESERVATIONS,
        "cost": registry["cost"],
        "observed_wan_22_costs": [
            {
                "attempt_id": row["attempt_id"],
                "provider_run_id": row["provider_run_id"],
                "response_cost": row["provider_response"].get("response_cost"),
            }
            for row in all_attempts
            if row["model_id"] == "alibaba/wan-2.2"
            and isinstance(row.get("provider_response"), dict)
            and row["provider_response"].get("response_cost") is not None
        ],
        # Private operator evidence used to reproduce a selection even when a
        # requested retry is unavailable (public review rows intentionally use
        # selected_attempt_id=null for unavailable outputs).
        "requested_retry_selections": sorted(requested),
        "articles": [
            {
                "article_number": source.spec.number,
                "article_slug": source.spec.slug,
                "publication_id": source.spec.publication_id,
                "brand": source.spec.brand,
                "title": source.spec.title,
                "article_url": source.spec.url,
                "image": {
                    "image_id": source.spec.selected_image_id,
                    "media_id": source.spec.selected_media_id,
                    "width": source.spec.width,
                    "height": source.spec.height,
                    "caption": source.caption,
                    "source_url": source.spec.source_url,
                    "source_sha256": source.source_sha256,
                    "planning_run_id": source.planning_run_id,
                },
            }
            for source in sources
        ],
        "outputs": outputs,
    }


def finalize(
    sources: Sequence[Source],
    *,
    root: Path,
    selected_attempt_ids: Iterable[str] = (),
) -> dict[str, Any]:
    document = build_final_selection(
        sources, root=root, selected_attempt_ids=selected_attempt_ids
    )
    _atomic_write(root / FINAL_SELECTION_REL, document)
    return document


def verify(
    sources: Sequence[Source], *, root: Path, allow_incomplete: bool
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        require_inventory(sources, root)
        registry = load_attempt_registry(root)
    except PipelineError as exc:
        return False, [str(exc)]
    if registry["cost"]["estimated_reserved_cost_usd"] > float(HARD_BUDGET_CAP_USD):
        errors.append("Prompt-attempt ledger exceeds the hard $5 budget")
    try:
        primary = _attempt_artifacts(sources, root, None)
        retries = [
            row
            for attempt in registry["attempts"]
            for row in _attempt_artifacts(sources, root, attempt)
        ]
    except (PipelineError, native.BatchPipelineError, transport.PipelineError) as exc:
        errors.append(str(exc))
        primary, retries = [], []
    for row in primary + retries:
        if row["status"] in {"submitted", "running", "submitting", "submit-unknown"}:
            continue
        if row["video_path"] is not None and row["contract_check"] is None:
            errors.append(f"Unverifiable MP4: {row['provider_run_id']}")
    final_path = root / FINAL_SELECTION_REL
    if final_path.is_file():
        actual = _read_json(final_path)
        selected = actual.get("requested_retry_selections")
        if not isinstance(selected, list) or any(
            not isinstance(item, str) for item in selected
        ):
            errors.append("Final requested_retry_selections is invalid")
            selected = []
        try:
            expected = build_final_selection(sources, root=root, selected_attempt_ids=selected)
            if actual != expected:
                errors.append("Final selection differs from current immutable artifacts")
        except PipelineError as exc:
            errors.append(str(exc))
        if not allow_incomplete:
            succeeded = sum(
                1 for output in actual.get("outputs", []) if output.get("status") == "succeeded"
            )
            if succeeded != PRIMARY_RESERVATIONS:
                errors.append(f"Expected six selected outputs, got {succeeded}")
    elif not allow_incomplete:
        errors.append(f"Missing final selection: {FINAL_SELECTION_REL}")
    report = {
        "schema_version": 1,
        "batch_id": BATCH_ID,
        "passed": not errors,
        "allow_incomplete": allow_incomplete,
        "errors": errors,
    }
    _atomic_write(root / VERIFICATION_REL, report)
    return not errors, errors


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--dry-run", action="store_true")
    for name in ("prepare-plans", "run-plans", "materialize"):
        command = commands.add_parser(name)
        command.add_argument("--attempt-id")
        command.add_argument("--dry-run", action="store_true")
        if name == "run-plans":
            command.add_argument("--timeout", type=_positive_int, default=1800)
            command.add_argument("--allow-external-processing", action="store_true")
    for name in ("generate", "resume"):
        command = commands.add_parser(name)
        command.add_argument("--attempt-id")
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--timeout", type=_positive_int, default=1800)
        command.add_argument("--poll-interval", type=float, default=10.0)
        command.add_argument("--allow-external-processing", action="store_true")
    reserve = commands.add_parser("reserve-retry")
    reserve.add_argument("--provider-run-id", required=True)
    retry_mode = reserve.add_mutually_exclusive_group(required=True)
    retry_mode.add_argument("--direction")
    retry_mode.add_argument("--autonomous", action="store_true")
    verify_command = commands.add_parser("verify")
    verify_command.add_argument("--allow-incomplete", action="store_true")
    finalize_command = commands.add_parser("finalize")
    finalize_command.add_argument("--select-attempt", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    args = _parser().parse_args(argv)
    try:
        sources = discover(root)
        if args.command == "inventory":
            document = inventory_document(sources, root)
            if not args.dry_run:
                write_inventory(sources, root)
            print(
                f"PASS: articles={document['article_count']}, images={document['image_count']}, "
                f"outputs={document['expected_outputs']}, max_cost=${MAX_ESTIMATED_COST_USD:.2f}"
            )
            return 0
        require_inventory(sources, root)
        if args.command == "prepare-plans":
            counts = prepare_plans(
                sources, root=root, attempt_id=args.attempt_id, dry_run=args.dry_run
            )
            print(f"PASS: {counts}")
            return 0
        if args.command == "run-plans":
            return run_plans(
                sources,
                root=root,
                attempt_id=args.attempt_id,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
            )
        if args.command == "materialize":
            return materialize(
                sources, root=root, attempt_id=args.attempt_id, dry_run=args.dry_run
            )
        if args.command in {"generate", "resume"}:
            return generate(
                sources,
                root=root,
                attempt_id=args.attempt_id,
                dry_run=args.dry_run,
                allow_external_processing=args.allow_external_processing,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
        if args.command == "reserve-retry":
            attempt = reserve_retry(
                sources,
                args.provider_run_id,
                args.direction,
                root,
                autonomous=args.autonomous,
            )
            print(f"PASS: reserved {attempt['attempt_id']} -> {attempt['provider_run_id']}")
            return 0
        if args.command == "finalize":
            document = finalize(
                sources,
                root=root,
                selected_attempt_ids=args.select_attempt,
            )
            succeeded = sum(
                output["status"] == "succeeded" for output in document["outputs"]
            )
            print(f"PASS: selected={succeeded}, unavailable={PRIMARY_RESERVATIONS - succeeded}")
            return 0
        if args.command == "verify":
            passed, errors = verify(
                sources, root=root, allow_incomplete=args.allow_incomplete
            )
            if not passed:
                for error in errors:
                    print(f"FAIL: {transport.safe_error(error)}", file=sys.stderr)
                return 1
            print("PASS: live-images Clipmaker Lite batch is valid")
            return 0
        raise PipelineError(f"Unknown command: {args.command}")
    except (
        PipelineError,
        native.BatchPipelineError,
        runner.LiteRunnerError,
        transport.PipelineError,
        InvalidOperation,
        OSError,
        subprocess.TimeoutExpired,
    ) as exc:
        print(f"error: {transport.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
