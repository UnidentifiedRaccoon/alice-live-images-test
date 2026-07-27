#!/usr/bin/env python3
"""Finalize the case-21 research sidecar without hiding fidelity failures.

This is a read-only verifier plus one local JSON write.  It does not call a
provider, discover a route, retry an entry, or fetch a URL.  Three generated
MP4s are intentionally exposed for visual comparison, but all three remain
unaccepted because their exact visual-review receipts say ``fidelity-failed``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402
from scripts import clipmaker_lite_case21_pipeline as case21  # noqa: E402
from scripts import clipmaker_lite_runner as runner  # noqa: E402
from scripts import video_generation_pipeline as transport  # noqa: E402


TICKET = "PROMOPAGES-9930"
AGENT_ID = "clipmaker-lite"
FINAL_BATCH_ID = "promopages-9930-case21-failure-aware-20260727-v1"
FINAL_MANIFEST_PATH = Path("clipmaker-lite-test/case-21-manifest.json")
STAGE1_EXPERIMENT_ID = "promopages-9930-case21-prompt-research-20260727-v1"
STAGE2_EXPERIMENT_ID = "promopages-9930-case21-opacity-only-stage2-20260727-v1"
STAGE1_ROOT = Path("clipmaker-lite-test/experiments") / STAGE1_EXPERIMENT_ID
STAGE2_ROOT = Path("clipmaker-lite-test/experiments") / STAGE2_EXPERIMENT_ID
STAGE1_GENERATION_PATH = STAGE1_ROOT / "generation-manifest.json"
STAGE2_GENERATION_PATH = STAGE2_ROOT / "generation-manifest.json"
STAGE1_INVENTORY_PATH = STAGE1_ROOT / "inventory.json"
STAGE2_INVENTORY_PATH = STAGE2_ROOT / "inventory.json"

PUBLIC_RAW_BASE = (
    "https://raw.githubusercontent.com/UnidentifiedRaccoon/"
    "alice-live-images-test/main/"
)

PRIMARY_TREE_DIGEST = (
    "0e7dc0d0fe9461a6c91d91df56aec4a1e49562929c756dc7913fab21e7cfe7a8"
)
RETRY_TREE_DIGEST = (
    "54967ca5b10ef079a21deca6ab0de9835a0b0105da032d57e9364718c914e53b"
)
STAGE1_GENERATION_CORE_DIGEST = (
    "bbb230607f881491635dfab3e9a9d970d49eafdaabdbc1f2582d405076004f51"
)
STAGE2_GENERATION_CORE_DIGEST = (
    "09d7af5f90ed8296f41544b10330f25cc2295af4596f7ae6ad9bc296f0afa54a"
)

AGGREGATE_BUDGET_CAP_USD = 3.0
STAGE1_RESERVED_USD = 2.2
STAGE2_RESERVED_USD = 0.5
AGGREGATE_RESERVED_USD = 2.7


class FinalizeError(RuntimeError):
    """A fail-closed case-21 research-finalization error."""


@dataclass(frozen=True)
class Control:
    path: Path
    digest: str
    exclude_review_material: bool = False


CONTROLS = {
    "primary": Control(case21.BATCH_ROOT, PRIMARY_TREE_DIGEST),
    "retry": Control(case21.RETRY_BATCH_ROOT, RETRY_TREE_DIGEST),
    "stage1_generation_core": Control(
        STAGE1_ROOT,
        STAGE1_GENERATION_CORE_DIGEST,
        exclude_review_material=True,
    ),
    "stage2_generation_core": Control(
        STAGE2_ROOT,
        STAGE2_GENERATION_CORE_DIGEST,
        exclude_review_material=True,
    ),
}


@dataclass(frozen=True)
class DisplaySelection:
    model_id: str
    planning_run_id: str
    planning_result_sha256: str
    planning_model_ids: tuple[str, ...]
    batch_id: str
    generation_path: Path
    sample_id: str
    provider_run_id: str
    prompt_path: Path
    run_path: Path
    video_path: Path
    review_path: Path
    review_sha256: str
    review_evidence_path: Path
    review_evidence_sha256: str
    video_sha256: str
    request_sha256: str
    expected_status: str
    expected_media: dict[str, Any]
    expected_contract_conforms: bool
    expected_contract_warnings: tuple[str, ...]
    activity: str
    experiment_id: str | None = None
    variant_id: str | None = None


PRIMARY_WAN22_BASE = (
    case21.BATCH_ROOT
    / "videos"
    / case21.ARTICLE_SLUG
    / native.MODEL_DIRECTORIES[native.WAN_MODEL_ID]
)
STAGE1_WAN27_BASE = (
    STAGE1_ROOT / "videos" / "erosion-negative" / native.MODEL_DIRECTORIES[native.WAN_27_MODEL_ID]
)
STAGE1_VEO_BASE = (
    STAGE1_ROOT / "videos" / "veo-motion-only" / native.MODEL_DIRECTORIES[native.VEO_31_MODEL_ID]
)

DISPLAY_SELECTIONS = (
    DisplaySelection(
        model_id=native.WAN_MODEL_ID,
        planning_run_id=case21.PLANNING_RUN_ID,
        planning_result_sha256=(
            "c1a4453979a13ea9291efde8c2ef0491a9e4a08327d615ba4dc6699ce7bf1a39"
        ),
        planning_model_ids=case21.MODEL_IDS,
        batch_id=case21.PROVIDER_BATCH_ID,
        generation_path=case21.GENERATION_MANIFEST_PATH,
        sample_id=case21.SAMPLE_ID,
        provider_run_id=(
            "promopages-9930-case21-maier-runs-20260727-v1-"
            "21-maier-doctor-zolotoe-vremia-04-wan-2-2"
        ),
        prompt_path=PRIMARY_WAN22_BASE / "04.prompt.json",
        run_path=PRIMARY_WAN22_BASE / "04.run.json",
        video_path=PRIMARY_WAN22_BASE / "04.mp4",
        review_path=PRIMARY_WAN22_BASE / "04.review.json",
        review_sha256=(
            "a82bfc1c029c55532a65ca73b4ae737f45ba1b1b03853365f717cfdef0dca246"
        ),
        review_evidence_path=PRIMARY_WAN22_BASE / "04.review.json",
        review_evidence_sha256=(
            "a82bfc1c029c55532a65ca73b4ae737f45ba1b1b03853365f717cfdef0dca246"
        ),
        video_sha256=(
            "98712af3715210cd1d6709deb3b409b81a8ea1d8c8b6f057f0271fabc529a2ec"
        ),
        request_sha256=(
            "6dc36da3ff5093eb8c6e9ea783e3c8fe44b92a38931aa1fba3ce50a5cc633097"
        ),
        expected_status="succeeded",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 3.233,
            "width": 944,
            "height": 944,
            "fps": 30.0,
            "frames": 97,
            "has_audio": False,
            "bytes": 247040,
            "sha256": (
                "98712af3715210cd1d6709deb3b409b81a8ea1d8c8b6f057f0271fabc529a2ec"
            ),
        },
        expected_contract_conforms=True,
        expected_contract_warnings=(),
        activity="baseline-generation",
    ),
    DisplaySelection(
        model_id=native.WAN_27_MODEL_ID,
        planning_run_id="promopages-9930-case21-erosion-negative-20260727-v1",
        planning_result_sha256=(
            "a2934ffa723151b82b869d835934407dbbcea7ac384a270412e3adbe3fc71664"
        ),
        planning_model_ids=(native.WAN_MODEL_ID, native.WAN_27_MODEL_ID),
        batch_id="promopages-9930-case21-prompt-research-stage1-20260727-v1",
        generation_path=STAGE1_GENERATION_PATH,
        sample_id="21-maier-04-erosion-negative",
        provider_run_id=(
            "promopages-9930-case21-prompt-research-stage1-20260727-v1-"
            "21-maier-04-erosion-negative-wan-2-7"
        ),
        prompt_path=STAGE1_WAN27_BASE / "04.prompt.json",
        run_path=STAGE1_WAN27_BASE / "04.run.json",
        video_path=STAGE1_WAN27_BASE / "04.mp4",
        review_path=STAGE1_WAN27_BASE / "04.review.json",
        review_sha256=(
            "47dc0e3e9c3584b17dbb4927507906b748a79eea38bbeebcd6b5ed3f1093fb1c"
        ),
        review_evidence_path=(
            STAGE1_ROOT / "review/contact-sheets/erosion-negative-wan27.png"
        ),
        review_evidence_sha256=(
            "926dc1cd5edb6d4e3b5e65136e537527379b12905179a08e2e37dcc97160eefb"
        ),
        video_sha256=(
            "12f7e4ae07bb607ac5849f14815df9053ae50ff6551ce8ec299c609ffb994b65"
        ),
        request_sha256=(
            "f3d3fb960427ea6122b4c0ba5889ae308298e34656a57c48be32f21a821c2caf"
        ),
        expected_status="verification-failed",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 5.0,
            "width": 1440,
            "height": 1440,
            "fps": 30.0,
            "frames": 150,
            "has_audio": True,
            "bytes": 2318997,
            "sha256": (
                "12f7e4ae07bb607ac5849f14815df9053ae50ff6551ce8ec299c609ffb994b65"
            ),
        },
        expected_contract_conforms=False,
        expected_contract_warnings=("audio", "resolution"),
        activity="prompt-experiment",
        experiment_id=STAGE1_EXPERIMENT_ID,
        variant_id="erosion-negative",
    ),
    DisplaySelection(
        model_id=native.VEO_31_MODEL_ID,
        planning_run_id="promopages-9930-case21-veo-motion-only-20260727-v1",
        planning_result_sha256=(
            "df820159b155a45012f16d43d24c544dc8782882ed6118023118399989c03506"
        ),
        planning_model_ids=(native.VEO_31_MODEL_ID,),
        batch_id="promopages-9930-case21-prompt-research-stage1-20260727-v1",
        generation_path=STAGE1_GENERATION_PATH,
        sample_id="21-maier-04-veo-motion-only",
        provider_run_id=(
            "promopages-9930-case21-prompt-research-stage1-20260727-v1-"
            "21-maier-04-veo-motion-only-veo-3-1-lite"
        ),
        prompt_path=STAGE1_VEO_BASE / "04.prompt.json",
        run_path=STAGE1_VEO_BASE / "04.run.json",
        video_path=STAGE1_VEO_BASE / "04.mp4",
        review_path=STAGE1_VEO_BASE / "04.review.json",
        review_sha256=(
            "83dd2a7f078c7b2cfa91fe5e111b6f2b43204c90048a4d1348b79ac37bc51b2b"
        ),
        review_evidence_path=STAGE1_ROOT / "review/contact-sheets/veo-motion-only.png",
        review_evidence_sha256=(
            "d75e9a82f3cef1651ffb8971f92ffb13f6e73da84e5ba8552a3447c7f7535b98"
        ),
        video_sha256=(
            "0c96252e39323c77bcc2853b236e133fdd812b519328d8985d3dd5f626e58574"
        ),
        request_sha256=(
            "dd2c007450f7011981c4a4122fcf7bd5f8c23efc0a36f5f8b629ccba8eb28148"
        ),
        expected_status="succeeded",
        expected_media={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "codec": "h264",
            "duration_seconds": 4.0,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "frames": 96,
            "has_audio": False,
            "bytes": 1384917,
            "sha256": (
                "0c96252e39323c77bcc2853b236e133fdd812b519328d8985d3dd5f626e58574"
            ),
        },
        expected_contract_conforms=True,
        expected_contract_warnings=(),
        activity="prompt-experiment",
        experiment_id=STAGE1_EXPERIMENT_ID,
        variant_id="veo-motion-only",
    ),
)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError as exc:
        raise FinalizeError(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FinalizeError(f"Invalid JSON in {path}: {exc}") from exc


def sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise FinalizeError(f"Required regular file is missing or unsafe: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise FinalizeError(f"Cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise FinalizeError(f"Path escapes workspace: {path}") from exc


def tree_digest(control: Control, root: Path = ROOT) -> str:
    base = root / control.path
    if not base.is_dir() or base.is_symlink():
        raise FinalizeError(f"Control tree is missing or unsafe: {base}")
    lines: list[str] = []
    for item in sorted(base.rglob("*")):
        if item.is_symlink():
            raise FinalizeError(f"Symlink is forbidden in control tree: {item}")
        if not item.is_file():
            continue
        relative_to_base = item.relative_to(base)
        if control.exclude_review_material and (
            (relative_to_base.parts and relative_to_base.parts[0] == "review")
            or item.name.endswith(".review.json")
        ):
            continue
        lines.append(f"{sha256_file(item)}  {_relative(item, root)}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def validate_controls(root: Path = ROOT) -> dict[str, str]:
    measured = {name: tree_digest(control, root) for name, control in CONTROLS.items()}
    expected = {name: control.digest for name, control in CONTROLS.items()}
    if measured != expected:
        raise FinalizeError(
            f"Case-21 immutable control digests changed: expected {expected}, got {measured}"
        )
    return measured


def _expected_cost() -> dict[str, Any]:
    return {
        "currency": "USD",
        "operator_budget_cap_usd": AGGREGATE_BUDGET_CAP_USD,
        "reserved_stage1_usd": STAGE1_RESERVED_USD,
        "reserved_stage2_usd": STAGE2_RESERVED_USD,
        "reserved_aggregate_usd": AGGREGATE_RESERVED_USD,
        "unreserved_usd": round(
            AGGREGATE_BUDGET_CAP_USD - AGGREGATE_RESERVED_USD, 2
        ),
        "reservation_kind": "conservative-operator-envelope",
        "provider_unit_costs_asserted": False,
        "actual_billing_available": False,
        "note": (
            "$2.70 is reserved inside the $3.00 operator cap; provider receipts "
            "do not expose actual billing, so this is not an actual-spend claim."
        ),
    }


def validate_budget_receipts(root: Path = ROOT) -> None:
    stage1 = read_json(root / STAGE1_INVENTORY_PATH)
    stage2 = read_json(root / STAGE2_INVENTORY_PATH)
    stage1_cost = stage1.get("cost") if isinstance(stage1, dict) else None
    stage2_cost = stage2.get("cost") if isinstance(stage2, dict) else None
    if (
        stage1.get("manifest_role") != "case-21-prompt-research-stage1"
        or stage1.get("agent_id") != AGENT_ID
        or stage1.get("controls")
        != {
            "primary": PRIMARY_TREE_DIGEST,
            "retry": RETRY_TREE_DIGEST,
        }
        or not isinstance(stage1_cost, dict)
        or stage1_cost.get("operator_budget_cap_usd") != AGGREGATE_BUDGET_CAP_USD
        or stage1_cost.get("reserved_stage1_usd") != STAGE1_RESERVED_USD
        or stage1_cost.get("actual_billing_available") is not False
    ):
        raise FinalizeError("Stage-1 budget/control receipt changed")
    if (
        stage2.get("manifest_role") != "case-21-opacity-only-stage2"
        or stage2.get("agent_id") != AGENT_ID
        or stage2.get("controls")
        != {
            "primary": PRIMARY_TREE_DIGEST,
            "retry": RETRY_TREE_DIGEST,
            "stage1_generation_core": STAGE1_GENERATION_CORE_DIGEST,
        }
        or not isinstance(stage2_cost, dict)
        or stage2_cost.get("operator_aggregate_budget_cap_usd")
        != AGGREGATE_BUDGET_CAP_USD
        or stage2_cost.get("reserved_stage1_usd") != STAGE1_RESERVED_USD
        or stage2_cost.get("reserved_stage2_usd") != STAGE2_RESERVED_USD
        or stage2_cost.get("reserved_aggregate_usd") != AGGREGATE_RESERVED_USD
        or stage2_cost.get("actual_billing_available") is not False
    ):
        raise FinalizeError("Stage-2 aggregate budget/control receipt changed")


def _safe_provenance(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "verified": True,
        "verification_scope": summary.get("verification_scope"),
        "cryptographically_signed": summary.get("cryptographically_signed"),
        "agent_id": summary.get("agent_id"),
        "contract_version": summary.get("contract_version"),
        "contract_fingerprint": summary.get("contract_fingerprint"),
        "instruction_bundle_sha256": summary.get("instruction_bundle_sha256"),
        "source_image_sha256": summary.get("source_image_sha256"),
        "article_context_sha256": summary.get("article_context_sha256"),
        "models": summary.get("models"),
    }


def _validated_planning(
    selection: DisplaySelection,
    source: case21.CaseSource,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    summary = runner.provenance_summary(root, selection.planning_run_id)
    result_relative = (
        case21.ARTIFACT_NAMESPACE / selection.planning_run_id / "result.json"
    ).as_posix()
    if (
        summary.get("verified") is not True
        or summary.get("agent_id") != AGENT_ID
        or summary.get("contract_version") != "2.0.2"
        or summary.get("models") != list(selection.planning_model_ids)
        or summary.get("source_image_sha256") != source.image["sha256"]
        or summary.get("article_context_sha256") != source.context_sha256
        or summary.get("result_path") != result_relative
    ):
        raise FinalizeError(
            f"Lite provenance changed for {selection.planning_run_id}"
        )
    result_path = root / result_relative
    if sha256_file(result_path) != selection.planning_result_sha256:
        raise FinalizeError(f"Lite result changed for {selection.planning_run_id}")
    result = read_json(result_path)
    producer = result.get("producer") if isinstance(result, dict) else None
    inputs = result.get("inputs") if isinstance(result, dict) else None
    result_source = inputs.get("source_image") if isinstance(inputs, dict) else None
    context = inputs.get("article_context") if isinstance(inputs, dict) else None
    models = result.get("models") if isinstance(result, dict) else None
    analysis = result.get("analysis") if isinstance(result, dict) else None
    intent = analysis.get("structured_intent") if isinstance(analysis, dict) else None
    if (
        result.get("job_id") != selection.planning_run_id
        or not isinstance(producer, dict)
        or producer.get("agent_id") != AGENT_ID
        or not isinstance(result_source, dict)
        or result_source.get("path") != source.image["source_path"]
        or result_source.get("sha256") != source.image["sha256"]
        or not isinstance(context, dict)
        or context.get("path") != source.context_path
        or context.get("sha256") != source.context_sha256
        or not isinstance(models, list)
        or [item.get("model_id") for item in models if isinstance(item, dict)]
        != list(selection.planning_model_ids)
        or not isinstance(intent, dict)
        or set(intent) != set(runner.STRUCTURED_INTENT_KEYS)
        or any(
            not isinstance(intent.get(key), str) or not intent[key].strip()
            for key in runner.STRUCTURED_INTENT_KEYS
        )
    ):
        raise FinalizeError(
            f"Lite result binding changed for {selection.planning_run_id}"
        )
    model = next(
        (
            item
            for item in models
            if isinstance(item, dict) and item.get("model_id") == selection.model_id
        ),
        None,
    )
    contract = read_json(root / case21.CONTRACT_PATH)
    expected_runtime = contract.get("models", {}).get(selection.model_id, {}).get(
        "runtime"
    )
    if (
        not isinstance(model, dict)
        or model.get("runtime") != expected_runtime
        or not isinstance(model.get("positive_prompt"), str)
        or not model["positive_prompt"].strip()
    ):
        raise FinalizeError(
            f"Selected model plan changed for {selection.planning_run_id}"
        )
    return summary, result, model, {
        key: intent[key].strip() for key in runner.STRUCTURED_INTENT_KEYS
    }


def _generation_output(
    selection: DisplaySelection,
    root: Path,
) -> dict[str, Any]:
    manifest = read_json(root / selection.generation_path)
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    expected_count = (
        len(case21.MODEL_IDS)
        if selection.generation_path == case21.GENERATION_MANIFEST_PATH
        else 5
    )
    if (
        manifest.get("batch_id") != selection.batch_id
        or manifest.get("agent_id") != AGENT_ID
        or manifest.get("expected_outputs") != expected_count
        or not isinstance(outputs, list)
        or len(outputs) != expected_count
    ):
        raise FinalizeError(f"Generation manifest changed: {selection.generation_path}")
    matches = [
        output
        for output in outputs
        if isinstance(output, dict)
        and output.get("provider_run_id") == selection.provider_run_id
    ]
    if len(matches) != 1:
        raise FinalizeError(
            f"Selected provider output is missing or duplicated: "
            f"{selection.provider_run_id}"
        )
    return matches[0]


def _expected_prompt_artifact(
    selection: DisplaySelection,
    summary: dict[str, Any],
    model: dict[str, Any],
    intent: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "ticket": TICKET,
        "batch_id": selection.batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "model_id": selection.model_id,
        "source": {
            "path": case21.SOURCE_PATH.as_posix(),
            "sha256": case21.EXPECTED_SOURCE_SHA256,
            "width": 1024,
            "height": 1024,
        },
        "structured_intent": intent,
        "prompt": {
            "positive": model.get("positive_prompt"),
            "negative": model.get("negative_prompt"),
        },
        "runtime": model.get("runtime"),
        "lite_result": {
            "path": (
                case21.ARTIFACT_NAMESPACE
                / selection.planning_run_id
                / "result.json"
            ).as_posix(),
            "sha256": selection.planning_result_sha256,
            "provenance": _safe_provenance(summary),
        },
    }


def _provider_sample(selection: DisplaySelection) -> dict[str, Any]:
    source_url = (
        PUBLIC_RAW_BASE + quote(case21.SOURCE_PATH.as_posix(), safe="/")
        if selection.activity == "baseline-generation"
        else case21.EXPECTED_ORIG_URL
    )
    return {
        "sample_id": selection.sample_id,
        "article_slug": case21.ARTICLE_SLUG,
        "image_id": case21.IMAGE_ID,
        "image_number": case21.IMAGE_ID,
        "source_path": case21.SOURCE_PATH.as_posix(),
        "source_url": source_url,
        "sha256": case21.EXPECTED_SOURCE_SHA256,
        "width": 1024,
        "height": 1024,
    }


def _provider_prompt(selection: DisplaySelection, model: dict[str, Any]) -> dict[str, Any]:
    prompt = {
        "sample_id": selection.sample_id,
        "model_id": selection.model_id,
        "target_duration_seconds": model["runtime"]["duration_seconds"],
        "positive_prompt": model.get("positive_prompt"),
        "negative_prompt": model.get("negative_prompt"),
        "embed_negative_in_positive": False,
        "last_frame_is_source": False,
    }
    if selection.model_id == native.WAN_27_MODEL_ID:
        if model["runtime"].get("prompt_expansion") != {
            "parameter": "prompt_extend",
            "value": True,
        }:
            raise FinalizeError("Wan 2.7 prompt-expansion contract changed")
        prompt["prompt_extend"] = True
    return prompt


def _validate_review(
    selection: DisplaySelection,
    source: case21.CaseSource,
    root: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    review_path = root / selection.review_path
    evidence_path = root / selection.review_evidence_path
    if sha256_file(review_path) != selection.review_sha256:
        raise FinalizeError(
            f"Exact visual review changed: {selection.review_path}"
        )
    if sha256_file(evidence_path) != selection.review_evidence_sha256:
        raise FinalizeError(
            f"Exact visual-review evidence changed: {selection.review_evidence_path}"
        )
    review = read_json(review_path)
    expected_keys = {
        "schema_version",
        "ticket",
        "model_id",
        "provider_run_id",
        "lite_run_id",
        "source",
        "artifact",
        "review_method",
        "observations",
        "verdict",
    }
    observations = review.get("observations") if isinstance(review, dict) else None
    verdict = review.get("verdict") if isinstance(review, dict) else None
    if (
        not isinstance(review, dict)
        or set(review) != expected_keys
        or review.get("schema_version") != 1
        or review.get("ticket") != TICKET
        or review.get("model_id") != selection.model_id
        or review.get("provider_run_id") != selection.provider_run_id
        or review.get("lite_run_id") != selection.planning_run_id
        or review.get("source")
        != {
            "path": source.image["source_path"],
            "sha256": source.image["sha256"],
        }
        or review.get("artifact")
        != {
            "path": selection.video_path.as_posix(),
            "sha256": selection.video_sha256,
        }
        or not isinstance(observations, dict)
        or not isinstance(observations.get("invariant_failures"), list)
        or not observations["invariant_failures"]
        or not isinstance(verdict, dict)
        or set(verdict) != {"status", "summary"}
        or verdict.get("status") != "fidelity-failed"
        or not isinstance(verdict.get("summary"), str)
        or not verdict["summary"].strip()
    ):
        raise FinalizeError(
            f"Visual-review identity or failure verdict changed: {selection.review_path}"
        )
    return verdict, {
        "path": selection.review_evidence_path.as_posix(),
        "sha256": selection.review_evidence_sha256,
    }


def validate_display_selection(
    selection: DisplaySelection,
    source: case21.CaseSource,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary, _result, model, intent = _validated_planning(selection, source, root)
    output = _generation_output(selection, root)
    expected_paths = {
        "prompt_path": selection.prompt_path.as_posix(),
        "run_path": selection.run_path.as_posix(),
        "video_path": selection.video_path.as_posix(),
    }
    expected_identity = {
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "sample_id": selection.sample_id,
        "article_slug": case21.ARTICLE_SLUG,
        "source_path": source.image["source_path"],
        "model_id": selection.model_id,
        **expected_paths,
    }
    if any(output.get(key) != value for key, value in expected_identity.items()):
        raise FinalizeError(
            f"Aggregate output identity changed: {selection.provider_run_id}"
        )

    prompt_path = root / selection.prompt_path
    run_path = root / selection.run_path
    video_path = root / selection.video_path
    prompt = read_json(prompt_path)
    expected_prompt = _expected_prompt_artifact(selection, summary, model, intent)
    if prompt != expected_prompt:
        raise FinalizeError(
            f"Prompt receipt differs from the verified Lite result: "
            f"{selection.prompt_path}"
        )
    run = read_json(run_path)
    if not isinstance(run, dict):
        raise FinalizeError(f"Run receipt is not an object: {selection.run_path}")
    run_identity = {
        "ticket": TICKET,
        "batch_id": selection.batch_id,
        "agent_id": AGENT_ID,
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "sample_id": selection.sample_id,
        "image_id": case21.IMAGE_ID,
        "model_id": selection.model_id,
        "prompt_path": selection.prompt_path.as_posix(),
        "output_path": selection.video_path.as_posix(),
        "lite_result_sha256": selection.planning_result_sha256,
    }
    if any(run.get(key) != value for key, value in run_identity.items()):
        raise FinalizeError(f"Run identity changed: {selection.run_path}")
    if any(run.get(key) for key in ("retry_of", "retry_count", "attempts")):
        raise FinalizeError(f"Mutable retry metadata is forbidden: {selection.run_path}")

    sample = _provider_sample(selection)
    provider_prompt = _provider_prompt(selection, model)
    expected_request = transport.build_request_preview(sample, provider_prompt)
    request_sha256 = transport.request_fingerprint(expected_request, sample)
    if (
        run.get("request") != expected_request
        or run.get("request_fingerprint_version")
        != transport.REQUEST_FINGERPRINT_VERSION
        or run.get("request_sha256") != request_sha256
        or request_sha256 != selection.request_sha256
    ):
        raise FinalizeError(f"Provider request changed: {selection.run_path}")
    effective_status = native.effective_run_status(run)
    mirrored = {
        "recorded_status": run.get("status"),
        "status": effective_status,
        "provider_may_be_active": run.get("provider_may_be_active"),
        "media": run.get("media"),
        "contract_check": run.get("contract_check"),
        "error": run.get("error"),
    }
    if any(output.get(key) != value for key, value in mirrored.items()):
        raise FinalizeError(
            f"Aggregate output differs from run receipt: {selection.provider_run_id}"
        )
    if (
        effective_status != selection.expected_status
        or run.get("provider_may_be_active") is not False
        or run.get("last_worker_failure") is not None
        or run.get("media") != selection.expected_media
        or output.get("media") != selection.expected_media
    ):
        raise FinalizeError(
            f"Selected run status/media changed: {selection.provider_run_id}"
        )
    if (
        sha256_file(video_path) != selection.video_sha256
        or video_path.stat().st_size != selection.expected_media["bytes"]
    ):
        raise FinalizeError(f"Selected MP4 bytes changed: {selection.video_path}")
    contract_check = run.get("contract_check")
    if (
        not isinstance(contract_check, dict)
        or contract_check.get("conforms")
        is not selection.expected_contract_conforms
        or contract_check.get("warnings")
        != list(selection.expected_contract_warnings)
    ):
        raise FinalizeError(
            f"Selected media contract receipt changed: {selection.run_path}"
        )
    verdict, review_evidence = _validate_review(selection, source, root)
    route = transport.route_for_model(selection.model_id)
    final_output = {
        "article_slug": case21.ARTICLE_SLUG,
        "image_id": case21.IMAGE_ID,
        "source_path": source.image["source_path"],
        "sample_id": selection.sample_id,
        "lite_run_id": selection.planning_run_id,
        "provider_run_id": selection.provider_run_id,
        "model_id": selection.model_id,
        "scene_plan": model.get("scene_plan"),
        "positive_prompt": model.get("positive_prompt"),
        "negative_prompt": model.get("negative_prompt"),
        "status": effective_status,
        "recorded_status": run.get("status"),
        "available": True,
        "accepted": False,
        "availability_status": "available-for-research-display",
        "acceptance_status": "rejected-visual-fidelity",
        "prompt_path": selection.prompt_path.as_posix(),
        "run_path": selection.run_path.as_posix(),
        "video_path": selection.video_path.as_posix(),
        "delivery": "repository-raw",
        "repository_raw_url": PUBLIC_RAW_BASE
        + quote(selection.video_path.as_posix(), safe="/"),
        "route": {
            "adapter": route["adapter"],
            "transport": route["transport"],
            "provider": route.get("provider_key") or "wan-streamlit",
            "capacity": int(route["capacity"]),
            "route_substitution": False,
        },
        "media": selection.expected_media,
        "contract_check": contract_check,
        "visual_review": verdict,
        "review_path": selection.review_path.as_posix(),
        "review_evidence": review_evidence,
        "selection": {
            "activity": selection.activity,
            "experiment_id": selection.experiment_id,
            "variant_id": selection.variant_id,
            "purpose": "failure-analysis-display",
        },
        "error": run.get("error"),
    }
    planning = {
        "model_id": selection.model_id,
        "run_id": selection.planning_run_id,
        "result_path": summary.get("result_path"),
        "result_sha256": selection.planning_result_sha256,
        "structured_intent": intent,
        "provenance": summary,
    }
    return final_output, planning


def _manifest_attempts(
    manifest_path: Path,
    *,
    activity: str,
    experiment_id: str | None,
    variant_from_sample: bool,
    root: Path,
) -> Iterable[dict[str, Any]]:
    manifest = read_json(root / manifest_path)
    outputs = manifest.get("outputs") if isinstance(manifest, dict) else None
    if not isinstance(outputs, list):
        raise FinalizeError(f"Attempt manifest has no outputs: {manifest_path}")
    selected_ids = {selection.provider_run_id for selection in DISPLAY_SELECTIONS}
    for output in outputs:
        if not isinstance(output, dict):
            raise FinalizeError(f"Attempt output is not an object: {manifest_path}")
        run_value = output.get("run_path")
        if not isinstance(run_value, str):
            raise FinalizeError(f"Attempt run_path is missing: {manifest_path}")
        run_path = root / Path(run_value)
        run = read_json(run_path)
        mirrored = {
            "provider_run_id": run.get("provider_run_id"),
            "lite_run_id": run.get("lite_run_id"),
            "model_id": run.get("model_id"),
            "recorded_status": run.get("status"),
            "status": native.effective_run_status(run),
            "provider_may_be_active": run.get("provider_may_be_active"),
            "media": run.get("media"),
            "contract_check": run.get("contract_check"),
            "error": run.get("error"),
        }
        if any(output.get(key) != value for key, value in mirrored.items()):
            raise FinalizeError(f"Attempt aggregate differs from receipt: {run_value}")
        sample_id = output.get("sample_id")
        variant_id = None
        if variant_from_sample:
            if not isinstance(sample_id, str) or not sample_id.startswith("21-maier-04-"):
                raise FinalizeError(f"Experiment sample identity changed: {sample_id}")
            variant_id = sample_id.removeprefix("21-maier-04-")
        provider_run_id = output.get("provider_run_id")
        video_value = output.get("video_path")
        available_video = (
            isinstance(video_value, str)
            and (root / Path(video_value)).is_file()
            and not (root / Path(video_value)).is_symlink()
            and isinstance(output.get("media"), dict)
        )
        yield {
            "activity": activity,
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "batch_id": manifest.get("batch_id"),
            "provider_run_id": provider_run_id,
            "lite_run_id": output.get("lite_run_id"),
            "sample_id": sample_id,
            "model_id": output.get("model_id"),
            "status": output.get("status"),
            "recorded_status": output.get("recorded_status"),
            "provider_may_be_active": output.get("provider_may_be_active"),
            "request_sha256": run.get("request_sha256"),
            "provider_job_id": run.get("provider_job_id"),
            "submitted_at": run.get("submitted_at"),
            "completed_at": run.get("completed_at"),
            "prompt_path": output.get("prompt_path"),
            "run_path": run_value,
            "video_path": video_value,
            "available_video": available_video,
            "selected_for_display": provider_run_id in selected_ids,
            "selected_for_acceptance": False,
            "error": output.get("error"),
        }


def build_attempt_history(root: Path = ROOT) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    history.extend(
        _manifest_attempts(
            case21.GENERATION_MANIFEST_PATH,
            activity="baseline-generation",
            experiment_id=None,
            variant_from_sample=False,
            root=root,
        )
    )
    history.extend(
        _manifest_attempts(
            case21.RETRY_GENERATION_MANIFEST_PATH,
            activity="explicit-retry",
            experiment_id=None,
            variant_from_sample=False,
            root=root,
        )
    )
    history.extend(
        _manifest_attempts(
            STAGE1_GENERATION_PATH,
            activity="prompt-experiment",
            experiment_id=STAGE1_EXPERIMENT_ID,
            variant_from_sample=True,
            root=root,
        )
    )
    history.extend(
        _manifest_attempts(
            STAGE2_GENERATION_PATH,
            activity="prompt-experiment",
            experiment_id=STAGE2_EXPERIMENT_ID,
            variant_from_sample=True,
            root=root,
        )
    )
    counters: dict[str, int] = {}
    for attempt in history:
        model_id = str(attempt.get("model_id"))
        counters[model_id] = counters.get(model_id, 0) + 1
        attempt["model_attempt_number"] = counters[model_id]
    if (
        len(history) != 11
        or sum(item["activity"] == "prompt-experiment" for item in history) != 6
        or sum(item["selected_for_display"] for item in history) != 3
        or any(item["selected_for_acceptance"] for item in history)
    ):
        raise FinalizeError("Case-21 research attempt history changed")
    return history


def build_manifest(
    *,
    root: Path = ROOT,
    updated_at: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    source = case21.discover_case(root)
    controls = validate_controls(root)
    validate_budget_receipts(root)
    case21.validate_routes()
    attempts = build_attempt_history(root)
    outputs: list[dict[str, Any]] = []
    planning: list[dict[str, Any]] = []
    for selection in DISPLAY_SELECTIONS:
        output, selected_planning = validate_display_selection(selection, source, root)
        output["attempt_history"] = [
            item for item in attempts if item["model_id"] == selection.model_id
        ]
        outputs.append(output)
        planning.append(selected_planning)
    if (
        [output["model_id"] for output in outputs] != list(case21.MODEL_IDS)
        or any(output["visual_review"]["status"] != "fidelity-failed" for output in outputs)
        or any(output["accepted"] for output in outputs)
        or any(not output["available"] for output in outputs)
    ):
        raise FinalizeError("Failure-aware output selection changed")

    image_record = {
        "image": {
            **source.image,
            "delivery": "repository-raw",
        },
        "delivery": "repository-raw",
        "repository_raw_url": PUBLIC_RAW_BASE
        + quote(source.image["source_path"], safe="/"),
        "outputs": outputs,
    }
    return {
        "schema_version": 1,
        "manifest_role": "case-21-extension",
        "ticket": TICKET,
        "case_number": case21.CASE_NUMBER,
        "batch_id": FINAL_BATCH_ID,
        "agent_id": AGENT_ID,
        "delivery": "repository-raw",
        "updated_at": updated_at or transport.utc_now(),
        "models": list(case21.MODEL_IDS),
        "article_count": 1,
        "image_count": 1,
        "expected_outputs": 3,
        "available_output_count": 3,
        "accepted_output_count": 0,
        "rejected_output_count": 3,
        "conforming_output_count": 2,
        "contract_warning_output_count": 1,
        "visual_fidelity_passed_count": 0,
        "visual_fidelity_failed_count": 3,
        "cost": _expected_cost(),
        "generation_policy": {
            "route_resolution": "exact-model-id",
            "automatic_route_substitution": False,
            "normal_run_discovery": False,
            "automatic_retries": False,
            "research_attempts_are_explicit": True,
            "route_capacities": dict(case21.ROUTE_CAPACITIES),
        },
        "acceptance_policy": {
            "display_availability_is_not_acceptance": True,
            "requires_exact_source_context_and_lite_provenance": True,
            "requires_exact_request_video_media_and_review_receipts": True,
            "fidelity_failed_outputs_are_accepted": False,
            "purpose": "preserve failed clips for comparative research",
        },
        "controls": controls,
        "source_manifests": {
            "primary_generation": case21.GENERATION_MANIFEST_PATH.as_posix(),
            "retry_generation": case21.RETRY_GENERATION_MANIFEST_PATH.as_posix(),
            "stage1_inventory": STAGE1_INVENTORY_PATH.as_posix(),
            "stage1_generation": STAGE1_GENERATION_PATH.as_posix(),
            "stage2_inventory": STAGE2_INVENTORY_PATH.as_posix(),
            "stage2_generation": STAGE2_GENERATION_PATH.as_posix(),
        },
        "attempt_history": attempts,
        "planning": {
            "selection_mode": "per-model-research-display",
            "selected_runs": planning,
        },
        "articles": [
            {
                "article_number": source.article_number,
                "article_slug": source.article_slug,
                "title": source.title,
                "lead": source.lead,
                "url": source.url,
                "context_path": source.context_path,
                "collected_image_count": len(source.images),
                "images": [image_record],
            }
        ],
        "outputs": outputs,
    }


def finalize(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    document = build_manifest(root=root)
    destination = root / FINAL_MANIFEST_PATH
    if destination.exists() and (not destination.is_file() or destination.is_symlink()):
        raise FinalizeError(f"Final manifest path is unsafe: {destination}")
    transport.atomic_write_json(destination, document)
    return document


def verify(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    path = root / FINAL_MANIFEST_PATH
    existing = read_json(path)
    if not isinstance(existing, dict):
        raise FinalizeError("Final case-21 manifest is not an object")
    updated_at = existing.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        raise FinalizeError("Final case-21 manifest updated_at is missing")
    expected = build_manifest(root=root, updated_at=updated_at)
    if existing != expected:
        raise FinalizeError("Final case-21 manifest differs from exact reconstruction")
    return existing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preview", "finalize", "verify"),
        help="validate only, validate and write the sidecar, or verify the sidecar",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="workspace root (defaults to the script workspace)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preview":
            document = build_manifest(root=args.root)
        elif args.command == "finalize":
            document = finalize(args.root)
        else:
            document = verify(args.root)
    except (
        FinalizeError,
        case21.PipelineError,
        runner.LiteRunnerError,
        native.BatchPipelineError,
        transport.PipelineError,
        OSError,
        KeyError,
        ValueError,
    ) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "PASS: case 21 exposes "
        f"{document['available_output_count']} research clips and accepts "
        f"{document['accepted_output_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
