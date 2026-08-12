#!/usr/bin/env python3
"""Prepare the immutable PROMOPAGES-10060 Tune v5 repair batch.

The v5 repair revision is intentionally separate from both the historical v4
Tune workflow and the first immutable v5 authoring pass.  It reuses the first
v5/r2 results for unaffected cases, assigns new run IDs and feedback files
only to the remaining case that failed the r3 semantic gate, and emits a new immutable prompt
manifest without rewriting either prior batch.

This coordinator is prompt-only.  It never calls a video provider, uploads to
S3, rewrites the live Tune manifest, or re-verifies v4 artifacts with the
current runner.  Historical v4 evidence is accepted only as an exact byte
snapshot with the frozen SHA-256 below.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner as runner  # noqa: E402


TICKET = "PROMOPAGES-10060"
AGENT_ID = "clipmaker-lite"
V4_BATCH_ID = "promopages-10060-tune-prompts-20260811-v4"
BATCH_ID = "promopages-10060-tune-prompts-20260811-v5"
R2_REVISION = "r2"
R2_BATCH_ID = f"{BATCH_ID}-{R2_REVISION}"
R3_REVISION = "r3"
R3_BATCH_ID = f"{BATCH_ID}-{R3_REVISION}"
REPAIR_REVISION = "r4"
REPAIR_BATCH_ID = f"{BATCH_ID}-{REPAIR_REVISION}"
EXPECTED_CONTRACT_VERSION = "2.3.0"
EXPECTED_EVALUATION_SHA256 = (
    "196fe3a0183b6a4d6ffd912d7e8f9d7157b0986dd47da7102134adf44540563d"
)
EXPECTED_V4_MANIFEST_SHA256 = (
    "efd1ff402f5c79028496d89463640832e7ff507441167b24adc129e19ca01a4f"
)
LIVE_V4_MANIFEST_REL = Path("clipmaker-lite-test/tune-manifest.json")
V4_SNAPSHOT_REL = Path(
    "clipmaker-lite-test/runs/"
    "promopages-10060-tune-review-20260811-v4/manifest.json"
)
BASE_BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / BATCH_ID
BASE_SELECTION_REL = BASE_BATCH_ROOT_REL / "selection.json"
BASE_PROMPT_MANIFEST_REL = BASE_BATCH_ROOT_REL / "prompt-manifest.json"
BASE_REPAIR_ROOT_REL = BASE_BATCH_ROOT_REL / "repair-feedback"
R2_BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / R2_BATCH_ID
R2_SELECTION_REL = R2_BATCH_ROOT_REL / "selection.json"
R2_PROMPT_MANIFEST_REL = R2_BATCH_ROOT_REL / "prompt-manifest.json"
R2_REPAIR_ROOT_REL = R2_BATCH_ROOT_REL / "repair-feedback"
R3_BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / R3_BATCH_ID
R3_SELECTION_REL = R3_BATCH_ROOT_REL / "selection.json"
R3_REPAIR_ROOT_REL = R3_BATCH_ROOT_REL / "repair-feedback"
BATCH_ROOT_REL = Path("clipmaker-lite-test/runs") / REPAIR_BATCH_ID
SELECTION_REL = BATCH_ROOT_REL / "selection.json"
PROMPT_MANIFEST_REL = BATCH_ROOT_REL / "prompt-manifest.json"
REPAIR_ROOT_REL = BATCH_ROOT_REL / "repair-feedback"
EXPECTED_BASE_SELECTION_SHA256 = (
    "343528bd1d7313315b73184d8d5eac8ab00d550b856d2af4c6176bf51391798a"
)
EXPECTED_BASE_PROMPT_MANIFEST_SHA256 = (
    "06c9696d93d3d5d050a99550062611deebd61d2f75e8fed76d32bb3094bb4dd4"
)
EXPECTED_R2_SELECTION_SHA256 = (
    "af1800ac82f4270330f5dc82a6d6c7658937467b65ee1eef22323e712432f49a"
)
EXPECTED_R2_PROMPT_MANIFEST_SHA256 = (
    "2ffe2cd03f9ee4b6aff3b9ea8f18303492b56e9462f369244bcdc2e47d7a72af"
)
EXPECTED_R3_SELECTION_SHA256 = (
    "68b0442abe3ae5acc81080c6254e52ccde8b13f65db08bf68d8614757a77f010"
)

MODEL_IDS = (
    "alibaba/wan-2.2",
    "alibaba/wan-2.7",
    "google/veo-3.1-lite",
)
EXPECTED_MODEL_COUNTS = {
    "alibaba/wan-2.2": 11,
    "alibaba/wan-2.7": 5,
    "google/veo-3.1-lite": 12,
}
EXPECTED_OUTCOME_COUNTS = {
    "unrated": 19,
    "same-or-unclear": 4,
    "worse": 5,
}
EXPECTED_INPUT_BINDING = {
    "image_root": "PROMOPAGES-9857",
    "context_root": "PROMOPAGES-9884",
    "context_filename": "content.json",
}


def _key(case_id: str, model_id: str) -> str:
    return f"{case_id}::{model_id}"


EXPECTED_REGENERATE_KEYS = frozenset(
    {
        _key("01#02", "alibaba/wan-2.2"),
        _key("01#02", "google/veo-3.1-lite"),
        _key("01#03", "alibaba/wan-2.2"),
        _key("01#03", "alibaba/wan-2.7"),
        _key("03#09", "alibaba/wan-2.2"),
        _key("03#09", "google/veo-3.1-lite"),
        _key("04#04", "alibaba/wan-2.2"),
        _key("04#04", "google/veo-3.1-lite"),
        _key("05#04", "alibaba/wan-2.7"),
        _key("07#06", "google/veo-3.1-lite"),
        _key("10#07", "google/veo-3.1-lite"),
        _key("11#03", "google/veo-3.1-lite"),
        _key("13#05", "google/veo-3.1-lite"),
        _key("14#04", "alibaba/wan-2.2"),
        _key("14#04", "alibaba/wan-2.7"),
        _key("14#04", "google/veo-3.1-lite"),
        _key("14#05", "alibaba/wan-2.2"),
        _key("14#05", "google/veo-3.1-lite"),
        _key("16#06", "alibaba/wan-2.2"),
        _key("17#08", "google/veo-3.1-lite"),
        _key("17#11", "alibaba/wan-2.2"),
        _key("18#05", "alibaba/wan-2.2"),
        _key("18#05", "alibaba/wan-2.7"),
        _key("18#05", "google/veo-3.1-lite"),
        _key("18#06", "alibaba/wan-2.2"),
        _key("18#07", "alibaba/wan-2.2"),
        _key("18#07", "alibaba/wan-2.7"),
        _key("18#07", "google/veo-3.1-lite"),
    }
)
EXPECTED_WORSE_KEYS = frozenset(
    {
        _key("07#06", "google/veo-3.1-lite"),
        _key("10#07", "google/veo-3.1-lite"),
        _key("13#05", "google/veo-3.1-lite"),
        _key("16#06", "alibaba/wan-2.2"),
        _key("17#11", "alibaba/wan-2.2"),
    }
)
EXPECTED_UNCLEAR_KEYS = frozenset(
    {
        _key("05#04", "alibaba/wan-2.7"),
        _key("11#03", "google/veo-3.1-lite"),
        _key("17#08", "google/veo-3.1-lite"),
        _key("18#06", "alibaba/wan-2.2"),
    }
)
EXPECTED_CASE_IDS = frozenset(key.split("::", 1)[0] for key in EXPECTED_REGENERATE_KEYS)
R2_CASE_IDS = frozenset(
    {
        "01#02",
        "01#03",
        "03#09",
        "04#04",
        "11#03",
        "14#04",
        "18#05",
        "18#06",
        "18#07",
    }
)
R3_CASE_IDS = frozenset({"03#09"})
REPAIR_CASE_IDS = frozenset({"18#06"})
REPAIR_TARGET_KEYS = frozenset(
    key for key in EXPECTED_REGENERATE_KEYS if key.split("::", 1)[0] in REPAIR_CASE_IDS
)

FOCAL_TARGETS = {
    "01#02": "the existing January-February 2026 chart region",
    "01#03": (
        "the mortgage issuance regional bar chart, especially the existing "
        "blue February 2026 bars"
    ),
    "03#09": "the complete apartment floor plan with its existing arrow and room 3.9",
    "04#04": "the four apartment listing cards and their existing layouts",
    "05#04": "the cleaning products on the two cabinet shelves, not the cabinet door",
    "07#06": "the visible woman and her phone",
    "10#07": "the visible family",
    "11#03": (
        "the projected pterosaur, kept fully inside the existing screen and away "
        "from the upper-right crop"
    ),
    "13#05": "the existing visible attraction",
    "14#04": "the exact text screenshot and its existing page layout",
    "14#05": "the existing two-column interface card grid",
    "16#06": "the visible cosmetic products",
    "17#08": "the central broken floor section, cracks, raised slab, and visible tools",
    "17#11": "the visible product composition",
    "18#05": "the two-row material recommendation table with its existing check and warning",
    "18#06": (
        "the visible worker's head, shoulders, and torso inspecting the floor; "
        "the detached trowel remains lying separately at right"
    ),
    "18#07": "the two-row adhesive recommendation table and its existing warning",
}

RIGID_REGIONS = {
    "01#02": ["the chart plane, labels, plotted marks, axes, and legend layout"],
    "01#03": ["the chart plane, regional labels, bars, values, axes, and legend layout"],
    "03#09": ["the floor-plan plane, walls, room labels, dimensions, and existing arrow"],
    "04#04": ["the four UI cards, price text, controls, and apartment-plan geometry"],
    "05#04": ["the cabinet, both shelves, cleaning-product containers, brush, and dustpan"],
    "07#06": ["the red smartphone, sofa, and visible room geometry"],
    "10#07": ["the table, sofa, room, dishes, cups, utensils, and food"],
    "11#03": ["the foreground seats, rails, ride supports, and projected-screen boundary"],
    "13#05": ["the visible attraction structure and its existing supports"],
    "14#04": ["the screenshot plane, text glyphs, and page layout"],
    "14#05": ["the interface plane, four cards, text glyphs, and controls"],
    "16#06": ["the cosmetic packages, labels, and visible support surface"],
    "17#08": ["the broken floor, cracks, raised slab, rubble, and all visible tools"],
    "17#11": ["the product packages, labels, and existing composition"],
    "18#05": ["the recommendation-table plane, both rows, glyphs, check, and warning"],
    "18#06": [
        "the detached trowel at right, adhesive, substrate, installed tiles, grout "
        "lines, and red alignment guides"
    ],
    "18#07": ["the recommendation-table plane, both rows, glyphs, and warning"],
}

CONTACTS = {
    "05#04": ["all products and tools retain their existing shelf support"],
    "07#06": ["the left hand keeps supporting the phone while the right finger stays at the screen"],
    "10#07": ["preserve every visible hand-to-cup, hand-to-food, and hand-to-utensil contact"],
    "11#03": ["seats, rails, and supports retain their existing attachment points"],
    "13#05": ["the attraction structure retains all visible support contacts"],
    "16#06": ["all packages retain their visible support contacts"],
    "17#08": ["floor fragments, rubble, and tools retain their existing floor contacts"],
    "17#11": ["all packages retain their existing support and overlap relationships"],
    "18#06": [],
}

MAX_SCREEN_TRAVEL_PERCENT = {
    "01#02": 5.0,
    "01#03": 6.0,
    "03#09": 4.0,
    "04#04": 1.5,
    "11#03": 0,
    "14#04": 4.0,
    "18#05": 1.5,
    "18#06": 0,
    "18#07": 1.5,
}

FULL_LAYOUT_ANCHORS = {
    "01#02": "the complete chart and all labels remain fully visible throughout",
    "01#03": "the complete regional bar chart remains fully visible throughout",
    "03#09": "the complete apartment floor plan remains fully visible throughout",
    "04#04": "all four apartment listing cards remain fully visible throughout",
    "14#04": "the full text screenshot and page layout remain visible throughout",
    "18#05": "the complete two-row material table remains fully visible throughout",
    "18#07": "the complete two-row adhesive table remains fully visible throughout",
}

REQUIRED_POSITIVE_PROMPT_PHRASES = {
    "03#09": "total screen travel capped at 4%",
}


def planning_revision_for_case(case_id: str) -> str | None:
    if case_id in REPAIR_CASE_IDS:
        return REPAIR_REVISION
    if case_id in R3_CASE_IDS:
        return R3_REVISION
    if case_id in R2_CASE_IDS:
        return R2_REVISION
    return None


def planning_batch_id_for_case(case_id: str) -> str:
    revision = planning_revision_for_case(case_id)
    if revision == REPAIR_REVISION:
        return REPAIR_BATCH_ID
    if revision == R3_REVISION:
        return R3_BATCH_ID
    if revision == R2_REVISION:
        return R2_BATCH_ID
    return BATCH_ID


def repair_root_for_case(case_id: str) -> Path:
    revision = planning_revision_for_case(case_id)
    if revision == REPAIR_REVISION:
        return REPAIR_ROOT_REL
    if revision == R3_REVISION:
        return R3_REPAIR_ROOT_REL
    if revision == R2_REVISION:
        return R2_REPAIR_ROOT_REL
    return BASE_REPAIR_ROOT_REL


class TuneV5PipelineError(RuntimeError):
    """The v5 prompt batch failed a frozen binding or completeness check."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
            return digest.hexdigest()
    except FileNotFoundError as exc:
        raise TuneV5PipelineError(f"Required file is missing: {path}") from exc


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256_bytes(encoded)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TuneV5PipelineError(f"Required JSON is missing: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TuneV5PipelineError(f"Invalid JSON: {path}") from exc


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise TuneV5PipelineError(f"Path is outside the workspace: {path}") from exc


def atomic_create_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == value:
            return
        raise TuneV5PipelineError(f"Immutable artifact already differs: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise TuneV5PipelineError(f"Immutable artifact appeared concurrently: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def atomic_create_json(path: Path, value: Any) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    atomic_create_bytes(path, encoded)


def _regular_file(path: Path, *, label: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise TuneV5PipelineError(f"{label} is missing: {path}") from exc
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise TuneV5PipelineError(f"{label} must be a regular non-symlink file")


def snapshot_v4(
    *,
    root: Path = ROOT,
    source: Path | None = None,
    destination: Path | None = None,
    expected_sha256: str = EXPECTED_V4_MANIFEST_SHA256,
) -> Path:
    root = root.resolve()
    source = source or (root / LIVE_V4_MANIFEST_REL)
    destination = destination or (root / V4_SNAPSHOT_REL)
    _regular_file(source, label="v4 live Tune manifest")
    payload = source.read_bytes()
    if sha256_bytes(payload) != expected_sha256:
        raise TuneV5PipelineError("v4 live Tune manifest SHA-256 changed")
    validate_v4_manifest(json.loads(payload), manifest_sha256=expected_sha256)
    atomic_create_bytes(destination, payload)
    if sha256_file(destination) != expected_sha256:
        raise TuneV5PipelineError("v4 snapshot bytes changed while freezing")
    return destination


def flatten_v4_targets(manifest: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    flattened: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for case in manifest["cases"]:
        case_id = case.get("case_id")
        for target in case.get("targets", []):
            evaluation_id = _key(str(case_id), str(target.get("model_id")))
            if evaluation_id in flattened:
                raise TuneV5PipelineError(f"Duplicate v4 target: {evaluation_id}")
            flattened[evaluation_id] = (case, target)
    return flattened


def validate_v4_manifest(
    manifest: Any,
    *,
    manifest_sha256: str,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("manifest_role") != "clipmaker-lite-tune-review"
        or manifest.get("ticket") != TICKET
        or manifest.get("batch_id") != V4_BATCH_ID
        or manifest.get("agent_id") != AGENT_ID
        or not isinstance(manifest.get("cases"), list)
        or len(manifest["cases"]) != 36
        or len(manifest_sha256) != 64
    ):
        raise TuneV5PipelineError("Unexpected historical v4 Tune manifest")
    flattened = flatten_v4_targets(manifest)
    if len(flattened) != 65:
        raise TuneV5PipelineError("Historical v4 manifest must contain 65 targets")
    return flattened


def _validate_export_summary(document: dict[str, Any], outcomes: list[str]) -> None:
    summary = document.get("summary")
    counts = {outcome: outcomes.count(outcome) for outcome in {"helped", "same-or-unclear", "worse"}}
    if (
        not isinstance(summary, dict)
        or summary.get("target_count") != 65
        or summary.get("saved_entry_count") != len(outcomes)
        or summary.get("evaluated_count") != len(outcomes)
        or summary.get("draft_count") != 0
        or summary.get("helped_count") != counts["helped"]
        or summary.get("same_or_unclear_count") != counts["same-or-unclear"]
        or summary.get("worse_count") != counts["worse"]
        or summary.get("unrated_count") != 65 - len(outcomes)
    ):
        raise TuneV5PipelineError("Evaluation export summary does not match its entries")


def load_evaluation_export(
    path: Path,
    *,
    v4_targets: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    expected_sha256: str = EXPECTED_EVALUATION_SHA256,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    _regular_file(path, label="v4 evaluation export")
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise TuneV5PipelineError(
            f"Evaluation export SHA-256 changed: {actual_sha256}"
        )
    document = read_json(path)
    dataset = document.get("dataset") if isinstance(document, dict) else None
    evaluations = document.get("evaluations") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("export_role") != "clipmaker-lite-tune-evaluation"
        or not isinstance(dataset, dict)
        or dataset.get("ticket") != TICKET
        or dataset.get("batch_id") != V4_BATCH_ID
        or not isinstance(evaluations, list)
    ):
        raise TuneV5PipelineError("Unexpected v4 evaluation export identity")
    by_id: dict[str, dict[str, Any]] = {}
    outcomes: list[str] = []
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            raise TuneV5PipelineError("Evaluation entries must be objects")
        evaluation_id = evaluation.get("evaluation_id")
        outcome = evaluation.get("outcome")
        if (
            not isinstance(evaluation_id, str)
            or evaluation_id not in v4_targets
            or evaluation_id in by_id
            or outcome not in {"helped", "same-or-unclear", "worse"}
        ):
            raise TuneV5PipelineError(f"Invalid/duplicate evaluation: {evaluation_id!r}")
        _case, target = v4_targets[evaluation_id]
        tuned_video = target.get("tuned", {}).get("video")
        exported_video = evaluation.get("tuned_video")
        if (
            evaluation.get("case_id") != evaluation_id.split("::", 1)[0]
            or evaluation.get("model_id") != target.get("model_id")
            or not isinstance(tuned_video, dict)
            or not isinstance(exported_video, dict)
            or exported_video.get("method") != tuned_video.get("method")
            or exported_video.get("sha256") != tuned_video.get("sha256")
        ):
            raise TuneV5PipelineError(f"Evaluation video binding changed: {evaluation_id}")
        by_id[evaluation_id] = evaluation
        outcomes.append(outcome)
    _validate_export_summary(document, outcomes)
    if len(by_id) != 46:
        raise TuneV5PipelineError("Evaluation export must contain exactly 46 saved entries")
    return document, by_id


def _failure_codes(
    evaluation_id: str,
    *,
    outcome: str,
    previous_method: str,
) -> list[str]:
    codes: list[str] = []
    if previous_method in {"deterministic-compositor", "deterministic-compositor-fallback"}:
        codes.append("route_rejected")
    if previous_method == "deterministic-compositor-fallback":
        codes.extend(["fallback_rejected", "provider_no_output"])
    explicit = {
        _key("05#04", "alibaba/wan-2.7"): ["focal_target_drift", "out_of_source_reveal"],
        _key("07#06", "google/veo-3.1-lite"): ["insufficient_motion"],
        _key("10#07", "google/veo-3.1-lite"): ["insufficient_motion"],
        _key("11#03", "google/veo-3.1-lite"): ["topology_hallucination", "out_of_source_reveal"],
        _key("13#05", "google/veo-3.1-lite"): ["insufficient_motion"],
        _key("16#06", "alibaba/wan-2.2"): ["insufficient_motion"],
        _key("17#08", "google/veo-3.1-lite"): ["rigid_world_deformation"],
        _key("17#11", "alibaba/wan-2.2"): ["insufficient_motion"],
        _key("18#06", "alibaba/wan-2.2"): ["unclear_review"],
    }
    codes.extend(explicit.get(evaluation_id, []))
    if outcome == "same-or-unclear" and not codes:
        codes.append("unclear_review")
    return list(dict.fromkeys(codes))


def _bounded_feedback_text(value: Any, fallback: str) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        text = fallback
    return text[:300].rstrip()


def repair_feedback_for_target(
    case: dict[str, Any],
    target: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    model_id = str(target["model_id"])
    evaluation_id = _key(case_id, model_id)
    outcome = str(evaluation.get("outcome")) if evaluation else "unrated"
    review_note = evaluation.get("note") if evaluation else None
    if not isinstance(review_note, str) or not review_note.strip():
        review_note = None
    previous_video = target.get("tuned", {}).get("video")
    if not isinstance(previous_video, dict):
        raise TuneV5PipelineError(f"v4 target has no video evidence: {evaluation_id}")
    previous_method = str(previous_video.get("method"))
    codes = _failure_codes(
        evaluation_id,
        outcome=outcome,
        previous_method=previous_method,
    )
    if review_note is not None:
        evidence_strength = "explicit"
    elif codes:
        evidence_strength = "inferred"
    else:
        evidence_strength = "none"
    planning = case.get("planning") or {}
    intent = planning.get("structured_intent") or {}
    focal_target = FOCAL_TARGETS[case_id]
    if case_id in {"07#06", "10#07", "11#03", "13#05", "18#06"}:
        # The review explicitly asks for believable subject motion.  Keep the
        # camera fixed so the authoring model does not replace that requested
        # micro-action with another camera-only move.
        camera_move = "fixed"
    elif case_id == "17#08":
        camera_move = "handheld-inspection"
    elif case_id == "05#04":
        camera_move = "push-in"
    elif previous_method == "deterministic-compositor":
        camera_move = "push-in"
    else:
        camera_move = "fixed"
    identity = _bounded_feedback_text(
        intent.get("identity_invariant"),
        "Preserve visible entity counts.",
    )
    geometry = _bounded_feedback_text(
        intent.get("geometry_invariant"),
        "Preserve visible topology and contacts.",
    )
    if case_id == "18#06":
        identity = (
            "Exactly one visible worker and one detached trowel lying separately at "
            "right remain present; the worker's hands stay away from the tool."
        )
        geometry = (
            "The detached trowel, adhesive, substrate, installed tiles, grout lines, "
            "and red alignment guides remain fixed; the worker does not reach toward "
            "or touch the tool."
        )
    must_remain_visible = [focal_target]
    topology_anchors = [geometry]
    rigid_regions = list(RIGID_REGIONS[case_id])
    contacts = list(CONTACTS.get(case_id, []))
    if case_id == "05#04":
        must_remain_visible.append("all four upper bottles throughout the shot")
    elif case_id == "11#03":
        topology_anchors.append("foreground seats and rails stay fixed; add no ride rows")
        topology_anchors.append(
            "the projected pterosaur may only flap in place or drift slightly inward; "
            "it never approaches the upper-right crop"
        )
    elif case_id == "03#09":
        topology_anchors.append(
            'the positive_prompt must include the exact phrase "total screen travel capped at 4%"'
        )
    elif case_id == "18#06":
        topology_anchors.append(
            "animate only one clear low-risk inspection shift of the visible worker's "
            "head, shoulders, and torso; the arms do not reach toward or touch any tool"
        )
        topology_anchors.append(
            "the detached trowel stays lying separately at right; adhesive, substrate, "
            "tiles, and alignment guides remain fixed"
        )
        must_remain_visible.append("the detached trowel lying separately at right")
    layout_anchor = FULL_LAYOUT_ANCHORS.get(case_id)
    if layout_anchor is not None:
        must_remain_visible.append(layout_anchor)
    return {
        "evaluation_id": evaluation_id,
        "outcome": outcome,
        "review_note": review_note,
        "evidence_strength": evidence_strength,
        "failure_codes": codes,
        "required_execution_mode": "i2v",
        "fallback_policy": "none",
        "camera_repair": {
            "move": camera_move,
            "focal_target": focal_target,
            "target_retention": "continuously-visible",
            "max_screen_travel_percent": MAX_SCREEN_TRAVEL_PERCENT.get(case_id, 8),
            "reveal_unseen_space": False,
        },
        "preservation": {
            "entity_counts": [identity],
            "topology_anchors": topology_anchors,
            "rigid_regions": rigid_regions,
            "contacts": contacts,
            "must_remain_visible": must_remain_visible,
        },
    }


def build_selection_document(
    evaluation_path: Path,
    *,
    root: Path = ROOT,
    snapshot_path: Path | None = None,
    evaluation_sha256: str = EXPECTED_EVALUATION_SHA256,
    v4_manifest_sha256: str = EXPECTED_V4_MANIFEST_SHA256,
) -> dict[str, Any]:
    root = root.resolve()
    snapshot_path = snapshot_path or (root / V4_SNAPSHOT_REL)
    if sha256_file(snapshot_path) != v4_manifest_sha256:
        raise TuneV5PipelineError("Historical v4 snapshot SHA-256 changed")
    v4_manifest = read_json(snapshot_path)
    if (
        sha256_file(root / BASE_SELECTION_REL) != EXPECTED_BASE_SELECTION_SHA256
        or sha256_file(root / BASE_PROMPT_MANIFEST_REL)
        != EXPECTED_BASE_PROMPT_MANIFEST_SHA256
        or sha256_file(root / R2_SELECTION_REL) != EXPECTED_R2_SELECTION_SHA256
        or sha256_file(root / R2_PROMPT_MANIFEST_REL)
        != EXPECTED_R2_PROMPT_MANIFEST_SHA256
        or sha256_file(root / R3_SELECTION_REL) != EXPECTED_R3_SELECTION_SHA256
    ):
        raise TuneV5PipelineError("Immutable base/r2/r3 v5 planning lineage changed")
    v4_targets = validate_v4_manifest(
        v4_manifest,
        manifest_sha256=v4_manifest_sha256,
    )
    export, evaluations = load_evaluation_export(
        evaluation_path,
        v4_targets=v4_targets,
        expected_sha256=evaluation_sha256,
    )
    selected_ids = {
        evaluation_id
        for evaluation_id in v4_targets
        if evaluations.get(evaluation_id, {}).get("outcome") != "helped"
    }
    if selected_ids != EXPECTED_REGENERATE_KEYS:
        missing = sorted(EXPECTED_REGENERATE_KEYS - selected_ids)
        extra = sorted(selected_ids - EXPECTED_REGENERATE_KEYS)
        raise TuneV5PipelineError(
            f"v5 target selection changed; missing={missing}, extra={extra}"
        )
    cases: list[dict[str, Any]] = []
    model_counts = {model_id: 0 for model_id in MODEL_IDS}
    outcome_counts = {outcome: 0 for outcome in EXPECTED_OUTCOME_COUNTS}
    for source_case in v4_manifest["cases"]:
        case_id = str(source_case["case_id"])
        selected_targets = [
            target
            for target in source_case["targets"]
            if _key(case_id, str(target["model_id"])) in selected_ids
        ]
        if not selected_targets:
            continue
        source_record = copy.deepcopy(source_case["source"])
        source_path, source_relative = runner.workspace_file(
            root,
            source_record["path"],
            f"v5 source image {case_id}",
        )
        if (
            source_relative != source_record["path"]
            or sha256_file(source_path) != source_record["sha256"]
        ):
            raise TuneV5PipelineError(f"v5 source image binding changed: {case_id}")
        context_path, context_relative = runner.workspace_file(
            root,
            source_case["context_path"],
            f"v5 article context {case_id}",
        )
        locator = runner.resolve_context_locator(
            read_json(context_path),
            source_relative,
            context_relative,
            str(source_record["image_id"]),
            EXPECTED_INPUT_BINDING,
        )
        context_binding = {
            "path": context_relative,
            "sha256": sha256_file(context_path),
            "locator": locator,
        }
        feedback_by_model: dict[str, dict[str, Any]] = {}
        targets: list[dict[str, Any]] = []
        for source_target in selected_targets:
            model_id = str(source_target["model_id"])
            evaluation_id = _key(case_id, model_id)
            evaluation = evaluations.get(evaluation_id)
            feedback = repair_feedback_for_target(source_case, source_target, evaluation)
            outcome = feedback["outcome"]
            feedback_by_model[model_id] = feedback
            model_counts[model_id] += 1
            outcome_counts[outcome] += 1
            targets.append(
                {
                    "evaluation_id": evaluation_id,
                    "sheet_row": source_target["sheet_row"],
                    "model_id": model_id,
                    "selection_outcome": outcome,
                    "original_sheet_comment": source_target.get("comment"),
                    "review_note": feedback["review_note"],
                    "repair_feedback": feedback,
                    "prior": {
                        "planning_batch_id": V4_BATCH_ID,
                        "execution_mode": source_target.get("tuned", {}).get("execution_mode"),
                        "scene_plan": source_target.get("tuned", {}).get("scene_plan"),
                        "positive_prompt": source_target.get("tuned", {}).get("positive_prompt"),
                        "video": copy.deepcopy(source_target.get("tuned", {}).get("video")),
                    },
                }
            )
        ordered_models = [model_id for model_id in MODEL_IDS if model_id in feedback_by_model]
        targets.sort(key=lambda target: ordered_models.index(target["model_id"]))
        repair_root = repair_root_for_case(case_id)
        repair_path = repair_root / f"{case_id.replace('#', '-')}.json"
        run_batch_id = planning_batch_id_for_case(case_id)
        cases.append(
            {
                "case_id": case_id,
                "article_number": source_case["article_number"],
                "article_slug": source_case["article_slug"],
                "brand": source_case.get("brand"),
                "title": source_case.get("title"),
                "publication_id": source_case.get("publication_id"),
                "content_class": source_case.get("content_class"),
                "source": source_record,
                "context_path": context_relative,
                "context_binding": context_binding,
                "selected_model_ids": ordered_models,
                "repair_feedback_path": repair_path.as_posix(),
                "repair_feedback_sha256": canonical_sha256(feedback_by_model),
                "repair_feedback": {
                    model_id: feedback_by_model[model_id] for model_id in ordered_models
                },
                "run_id": (
                    f"{run_batch_id}-{source_case['article_slug']}-"
                    f"{source_case['source']['image_id']}"
                ),
                "repair_revision": planning_revision_for_case(case_id),
                "targets": targets,
            }
        )
    if (
        len(cases) != 17
        or {case["case_id"] for case in cases} != EXPECTED_CASE_IDS
        or sum(len(case["targets"]) for case in cases) != 28
        or model_counts != EXPECTED_MODEL_COUNTS
        or outcome_counts != EXPECTED_OUTCOME_COUNTS
    ):
        raise TuneV5PipelineError("v5 selected case/model/outcome matrix changed")
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-selection",
        "ticket": TICKET,
        "batch_id": REPAIR_BATCH_ID,
        "agent_id": AGENT_ID,
        "policy": {
            "selection": "outcome is unrated, same-or-unclear, or worse",
            "repair_revision": REPAIR_REVISION,
            "required_execution_mode": "i2v",
            "fallback": False,
            "s3_upload": False,
        },
        "lineage": {
            "evaluation_export": {
                "source_name": evaluation_path.name,
                "sha256": evaluation_sha256,
                "exported_at": export.get("exported_at"),
                "source_batch_id": V4_BATCH_ID,
            },
            "v4_manifest": {
                "path": relative(snapshot_path, root),
                "sha256": v4_manifest_sha256,
                "current_runner_reverification": False,
            },
            "base_v5_selection": {
                "path": BASE_SELECTION_REL.as_posix(),
                "sha256": EXPECTED_BASE_SELECTION_SHA256,
            },
            "base_v5_prompt_manifest": {
                "path": BASE_PROMPT_MANIFEST_REL.as_posix(),
                "sha256": EXPECTED_BASE_PROMPT_MANIFEST_SHA256,
            },
            "r2_v5_selection": {
                "path": R2_SELECTION_REL.as_posix(),
                "sha256": EXPECTED_R2_SELECTION_SHA256,
            },
            "r2_v5_prompt_manifest": {
                "path": R2_PROMPT_MANIFEST_REL.as_posix(),
                "sha256": EXPECTED_R2_PROMPT_MANIFEST_SHA256,
            },
            "r3_v5_selection": {
                "path": R3_SELECTION_REL.as_posix(),
                "sha256": EXPECTED_R3_SELECTION_SHA256,
                "reuse_scope": ["03#09"],
            },
        },
        "summary": {
            "case_count": 17,
            "target_count": 28,
            "reused_helped_count": 37,
            "repair_case_count": len(REPAIR_CASE_IDS),
            "repair_target_count": len(REPAIR_TARGET_KEYS),
            "reused_prior_v5_case_count": 17 - len(REPAIR_CASE_IDS),
            "reused_prior_v5_target_count": 28 - len(REPAIR_TARGET_KEYS),
            "model_counts": model_counts,
            "outcome_counts": outcome_counts,
        },
        "cases": cases,
    }


def write_selection(document: dict[str, Any], *, root: Path = ROOT) -> Path:
    root = root.resolve()
    for case in document["cases"]:
        feedback_path = root / case["repair_feedback_path"]
        atomic_create_json(feedback_path, case["repair_feedback"])
        if canonical_sha256(read_json(feedback_path)) != case["repair_feedback_sha256"]:
            raise TuneV5PipelineError(f"Repair feedback digest changed: {feedback_path}")
    output = root / SELECTION_REL
    atomic_create_json(output, document)
    return output


def load_selection(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    document = read_json(root / SELECTION_REL)
    if (
        not isinstance(document, dict)
        or document.get("manifest_role") != "clipmaker-lite-tune-v5-selection"
        or document.get("batch_id") != REPAIR_BATCH_ID
        or document.get("summary", {}).get("target_count") != 28
        or document.get("policy", {}).get("required_execution_mode") != "i2v"
        or document.get("policy", {}).get("repair_revision") != REPAIR_REVISION
        or document.get("policy", {}).get("fallback") is not False
        or document.get("policy", {}).get("s3_upload") is not False
    ):
        raise TuneV5PipelineError("Unexpected v5 selection manifest")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 17:
        raise TuneV5PipelineError("v5 selection must contain exactly 17 cases")
    case_ids: set[str] = set()
    run_ids: set[str] = set()
    evaluation_ids: set[str] = set()
    model_counts = {model_id: 0 for model_id in MODEL_IDS}
    outcome_counts = {outcome: 0 for outcome in EXPECTED_OUTCOME_COUNTS}
    for case in cases:
        if not isinstance(case, dict):
            raise TuneV5PipelineError("v5 selection cases must be objects")
        case_id = case.get("case_id")
        run_id = case.get("run_id")
        source = case.get("source")
        context = case.get("context_binding")
        if (
            not isinstance(case_id, str)
            or case_id in case_ids
            or not isinstance(run_id, str)
            or run_id in run_ids
            or run_id
            != (
                f"{planning_batch_id_for_case(str(case_id))}-"
                f"{case.get('article_slug')}-{(source or {}).get('image_id')}"
            )
            or case.get("repair_revision") != planning_revision_for_case(str(case_id))
            or not isinstance(source, dict)
            or not isinstance(source.get("path"), str)
            or not isinstance(source.get("image_id"), str)
            or not isinstance(source.get("sha256"), str)
            or not isinstance(context, dict)
            or set(context) != {"path", "sha256", "locator"}
            or case.get("context_path") != context.get("path")
            or not isinstance(context.get("path"), str)
            or not isinstance(context.get("sha256"), str)
            or not isinstance(context.get("locator"), dict)
            or str(context["locator"].get("image_id")) != source.get("image_id")
        ):
            raise TuneV5PipelineError(f"Invalid v5 case/source/context binding: {case_id!r}")
        case_ids.add(case_id)
        run_ids.add(run_id)
        source_path, source_relative = runner.workspace_file(
            root, source["path"], f"v5 source image {case_id}"
        )
        context_path, context_relative = runner.workspace_file(
            root, context["path"], f"v5 article context {case_id}"
        )
        expected_locator = runner.resolve_context_locator(
            read_json(context_path),
            source_relative,
            context_relative,
            source["image_id"],
            EXPECTED_INPUT_BINDING,
        )
        if (
            source_relative != source["path"]
            or sha256_file(source_path) != source["sha256"]
            or context_relative != context["path"]
            or sha256_file(context_path) != context["sha256"]
            or expected_locator != context["locator"]
        ):
            raise TuneV5PipelineError(f"v5 source/context content changed: {case_id}")
        targets = case.get("targets")
        selected_models = case.get("selected_model_ids")
        if not isinstance(targets, list) or not isinstance(selected_models, list):
            raise TuneV5PipelineError(f"Invalid v5 targets: {case_id}")
        target_models = [target.get("model_id") for target in targets if isinstance(target, dict)]
        if (
            len(target_models) != len(targets)
            or target_models != selected_models
            or selected_models != [model_id for model_id in MODEL_IDS if model_id in target_models]
        ):
            raise TuneV5PipelineError(f"v5 selected model order changed: {case_id}")
        feedback = read_json(root / case["repair_feedback_path"])
        expected_repair_root = repair_root_for_case(case_id)
        if case["repair_feedback_path"] != (
            expected_repair_root / f"{case_id.replace('#', '-')}.json"
        ).as_posix():
            raise TuneV5PipelineError(f"v5 repair path changed: {case_id}")
        try:
            normalized_feedback = runner.validate_repair_feedback_models(
                feedback,
                selected_models,
                f"v5 repair feedback {case_id}",
            )
        except runner.LiteRunnerError as exc:
            raise TuneV5PipelineError(str(exc)) from exc
        if (
            feedback != case["repair_feedback"]
            or normalized_feedback != feedback
            or canonical_sha256(feedback) != case["repair_feedback_sha256"]
            or list(feedback) != case["selected_model_ids"]
        ):
            raise TuneV5PipelineError(
                f"Repair feedback binding changed: {case['case_id']}"
            )
        for target in targets:
            model_id = target["model_id"]
            evaluation_id = _key(case_id, model_id)
            outcome = target.get("selection_outcome")
            if (
                target.get("evaluation_id") != evaluation_id
                or evaluation_id in evaluation_ids
                or outcome not in outcome_counts
                or target.get("repair_feedback") != feedback[model_id]
            ):
                raise TuneV5PipelineError(f"v5 target binding changed: {evaluation_id}")
            evaluation_ids.add(evaluation_id)
            model_counts[model_id] += 1
            outcome_counts[outcome] += 1
    expected_summary = {
        "case_count": 17,
        "target_count": 28,
        "reused_helped_count": 37,
        "repair_case_count": len(REPAIR_CASE_IDS),
        "repair_target_count": len(REPAIR_TARGET_KEYS),
        "reused_prior_v5_case_count": 17 - len(REPAIR_CASE_IDS),
        "reused_prior_v5_target_count": 28 - len(REPAIR_TARGET_KEYS),
        "model_counts": model_counts,
        "outcome_counts": outcome_counts,
    }
    if (
        case_ids != EXPECTED_CASE_IDS
        or evaluation_ids != EXPECTED_REGENERATE_KEYS
        or model_counts != EXPECTED_MODEL_COUNTS
        or outcome_counts != EXPECTED_OUTCOME_COUNTS
        or document.get("summary") != expected_summary
    ):
        raise TuneV5PipelineError("v5 selected case/model/outcome matrix changed")
    return document


def _run_inputs_match_case(inputs: Any, case: dict[str, Any]) -> bool:
    if not isinstance(inputs, dict):
        return False
    source = inputs.get("source_image")
    context = inputs.get("article_context")
    expected_source = case["source"]
    expected_context = case["context_binding"]
    return (
        isinstance(source, dict)
        and source.get("path") == expected_source["path"]
        and source.get("sha256") == expected_source["sha256"]
        and isinstance(context, dict)
        and context.get("path") == expected_context["path"]
        and context.get("sha256") == expected_context["sha256"]
        and context.get("locator") == expected_context["locator"]
        and str(context.get("locator", {}).get("image_id"))
        == expected_source["image_id"]
    )


def prepare_case(case: dict[str, Any], *, root: Path = ROOT) -> str:
    run_id = case["run_id"]
    directory = root / runner.OUTPUT_NAMESPACE / run_id
    if directory.exists():
        job, selection, _directory = runner.validate_prepared_job(root, run_id)
        actual_models = [value["model_id"] for value in selection["selected_models"]]
        repair_input = job.get("inputs", {}).get("repair_feedback")
        if (
            actual_models != case["selected_model_ids"]
            or not _run_inputs_match_case(job.get("inputs"), case)
            or not isinstance(repair_input, dict)
            or repair_input.get("path") != case["repair_feedback_path"]
            or repair_input.get("canonical_sha256") != case["repair_feedback_sha256"]
        ):
            raise TuneV5PipelineError(f"Prepared v5 job binding changed: {run_id}")
        return "already-prepared"
    runner.prepare_run(
        root,
        run_id,
        case["source"]["path"],
        case["context_path"],
        image_id=case["source"]["image_id"],
        model_ids=case["selected_model_ids"],
        user_direction=None,
        repair_feedback_path=case["repair_feedback_path"],
    )
    return "prepared"


def result_is_verified(case: dict[str, Any], *, root: Path = ROOT) -> bool:
    result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
    if not result_path.is_file() or result_path.is_symlink():
        return False
    summary = runner.provenance_summary(root, case["run_id"])
    result = read_json(result_path)
    repair_input = result.get("inputs", {}).get("repair_feedback")
    return (
        summary.get("verified") is True
        and summary.get("contract_version") == EXPECTED_CONTRACT_VERSION
        and summary.get("models") == case["selected_model_ids"]
        and _run_inputs_match_case(result.get("inputs"), case)
        and isinstance(repair_input, dict)
        and repair_input.get("path") == case["repair_feedback_path"]
        and repair_input.get("canonical_sha256") == case["repair_feedback_sha256"]
    )


def run_case(
    case: dict[str, Any],
    *,
    root: Path = ROOT,
    author_model: str | None = None,
    timeout: int = 900,
) -> str:
    if result_is_verified(case, root=root):
        return "already-complete"
    runner.run_agent(
        root,
        case["run_id"],
        author_model=author_model,
        timeout=timeout,
        external_processing_approved=True,
    )
    if not result_is_verified(case, root=root):
        raise TuneV5PipelineError(f"Lite 2.3 provenance failed: {case['run_id']}")
    return "completed"


def run_cases(
    cases: Iterable[dict[str, Any]],
    *,
    root: Path = ROOT,
    jobs: int,
    author_model: str | None,
    timeout: int,
) -> None:
    cases = list(cases)
    if not 1 <= jobs <= 4:
        raise TuneV5PipelineError("--jobs must be between 1 and 4")
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        future_to_case = {
            executor.submit(
                run_case,
                case,
                root=root,
                author_model=author_model,
                timeout=timeout,
            ): case
            for case in cases
        }
        for index, future in enumerate(concurrent.futures.as_completed(future_to_case), 1):
            case = future_to_case[future]
            try:
                status = future.result()
                print(f"v5 [{index}/{len(cases)}] {case['case_id']} -> {status}", flush=True)
            except Exception as exc:  # noqa: BLE001 - aggregate all immutable failures
                failures.append(f"{case['case_id']}: {exc}")
    if failures:
        raise TuneV5PipelineError("v5 planning failures:\n" + "\n".join(failures))


def _model_map(result: dict[str, Any], case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    models = result.get("models")
    if not isinstance(models, list):
        raise TuneV5PipelineError(f"Lite result models are invalid: {case['case_id']}")
    by_id = {str(model.get("model_id")): model for model in models if isinstance(model, dict)}
    if list(by_id) != case["selected_model_ids"]:
        raise TuneV5PipelineError(f"Lite model order changed: {case['case_id']}")
    for model_id, model in by_id.items():
        if (
            model.get("execution_mode") != "i2v"
            or not isinstance(model.get("positive_prompt"), str)
            or not model["positive_prompt"].strip()
            or model.get("negative_prompt") is not None
        ):
            raise TuneV5PipelineError(
                f"v5 forbids compositor/null prompt: {case['case_id']} / {model_id}"
            )
        required_phrase = REQUIRED_POSITIVE_PROMPT_PHRASES.get(case["case_id"])
        if required_phrase is not None and required_phrase not in model["positive_prompt"]:
            raise TuneV5PipelineError(
                f"v5 prompt is missing required numeric motion cap: "
                f"{case['case_id']} / {model_id} / {required_phrase!r}"
            )
    return by_id


def build_prompt_manifest(
    selection: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    published: list[dict[str, Any]] = []
    target_count = 0
    for case in selection["cases"]:
        if not result_is_verified(case, root=root):
            raise TuneV5PipelineError(f"v5 result is not verified: {case['run_id']}")
        result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
        result = read_json(result_path)
        provenance = runner.provenance_summary(root, case["run_id"])
        by_model = _model_map(result, case)
        targets: list[dict[str, Any]] = []
        selected_by_model = {target["model_id"]: target for target in case["targets"]}
        for model_id in case["selected_model_ids"]:
            source_target = selected_by_model[model_id]
            model = by_model[model_id]
            target_count += 1
            targets.append(
                {
                    **copy.deepcopy(source_target),
                    "tuned": {
                        "execution_mode": "i2v",
                        "scene_plan": model["scene_plan"],
                        "positive_prompt": model["positive_prompt"],
                        "negative_prompt": None,
                        "runtime": model["runtime"],
                    },
                }
            )
        published.append(
            {
                **{key: copy.deepcopy(value) for key, value in case.items() if key not in {"repair_feedback", "targets"}},
                "planning": {
                    "run_id": case["run_id"],
                    "result_path": relative(result_path, root),
                    "result_sha256": sha256_file(result_path),
                    "provenance": provenance,
                    "structured_intent": result["analysis"]["structured_intent"],
                    "image_reading": result["analysis"]["image_reading"],
                    "article_context": result["analysis"]["article_context"],
                    "repair_feedback_path": case["repair_feedback_path"],
                    "repair_feedback_sha256": case["repair_feedback_sha256"],
                },
                "targets": targets,
            }
        )
    if len(published) != 17 or target_count != 28:
        raise TuneV5PipelineError("v5 prompt manifest completeness changed")
    output_path = root / PROMPT_MANIFEST_REL
    if output_path.exists() or output_path.is_symlink():
        if output_path.is_symlink() or not output_path.is_file():
            raise TuneV5PipelineError("Existing v5 prompt manifest must be a regular file")
        existing = read_json(output_path)
        if (
            not isinstance(existing, dict)
            or existing.get("manifest_role") != "clipmaker-lite-tune-v5-planning"
            or existing.get("batch_id") != REPAIR_BATCH_ID
            or not isinstance(existing.get("generated_at"), str)
            or not existing["generated_at"].strip()
        ):
            raise TuneV5PipelineError("Existing v5 prompt manifest identity changed")
        generated_at = existing["generated_at"]
    else:
        generated_at = utc_now()
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-v5-planning",
        "ticket": TICKET,
        "batch_id": REPAIR_BATCH_ID,
        "agent_id": AGENT_ID,
        "contract_version": EXPECTED_CONTRACT_VERSION,
        "generated_at": generated_at,
        "scope": {
            "selection_path": SELECTION_REL.as_posix(),
            "selection_sha256": sha256_file(root / SELECTION_REL),
            "case_count": 17,
            "target_count": 28,
            "required_execution_mode": "i2v",
            "fallback": False,
            "video_generation": False,
            "s3_upload": False,
        },
        "lineage": copy.deepcopy(selection["lineage"]),
        "summary": copy.deepcopy(selection["summary"]),
        "cases": published,
    }


def _filtered_cases(selection: dict[str, Any], requested: list[str]) -> list[dict[str, Any]]:
    if not requested:
        return list(selection["cases"])
    by_id = {case["case_id"]: case for case in selection["cases"]}
    unknown = sorted(set(requested) - set(by_id))
    if unknown:
        raise TuneV5PipelineError(f"Unknown v5 cases: {', '.join(unknown)}")
    return [by_id[case_id] for case_id in requested]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("snapshot-v4", "select", "prepare", "run", "build", "all"),
    )
    parser.add_argument("--evaluation", type=Path)
    parser.add_argument("--case", action="append", default=[], dest="case_ids")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--author-model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--allow-external-processing", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "snapshot-v4":
            output = snapshot_v4(root=root)
            print(relative(output, root), flush=True)
            return 0
        if args.command in {"select", "all"}:
            if args.evaluation is None:
                raise TuneV5PipelineError("select/all requires --evaluation")
            document = build_selection_document(args.evaluation, root=root)
            output = write_selection(document, root=root)
            print(relative(output, root), flush=True)
        selection = load_selection(root)
        cases = _filtered_cases(selection, args.case_ids)
        if args.command in {"prepare", "all"}:
            for case in cases:
                print(f"{case['case_id']}: {prepare_case(case, root=root)}", flush=True)
        if args.command in {"run", "all"}:
            if not args.allow_external_processing:
                raise TuneV5PipelineError("run/all requires --allow-external-processing")
            run_cases(
                cases,
                root=root,
                jobs=args.jobs,
                author_model=args.author_model,
                timeout=args.timeout,
            )
        if args.command in {"build", "all"}:
            manifest = build_prompt_manifest(selection, root=root)
            atomic_create_json(root / PROMPT_MANIFEST_REL, manifest)
            print(PROMPT_MANIFEST_REL.as_posix(), flush=True)
        return 0
    except (TuneV5PipelineError, runner.LiteRunnerError) as exc:
        print(f"clipmaker-lite tune v5 error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
