#!/usr/bin/env python3
"""Isolated exact-45 Tune approval S3 exporter for PROMOPAGES-10060."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from scripts import promopages_10060_s3_export as base
except ImportError:
    import promopages_10060_s3_export as base  # type: ignore[no-redef]


ExportError = base.ExportError
REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "PROMOPAGES-10060" / "tune-s3-export"
DEFAULT_CONTRACT_PATH = CONFIG_DIR / "selection-contract.json"
DEFAULT_OUTPUT_DIR = CONFIG_DIR / "output"
DEFAULT_OVERLAY_PATH = (
    REPO_ROOT / "clipmaker-lite-test"
    / "promopages-10060-tune-approved-s3-overlay.json"
)

CONTRACT_ROLE = "promopages-10060-tune-approved-selection-contract"
PACKAGE_SCHEMA = "promopages-10060-tune-approved-s3-package/v1"
PACKAGE_ROLE = "promopages-10060-tune-approved-s3-package"
OVERLAY_ROLE = "promopages-10060-tune-approved-s3-overlay"
REPORT_SCHEMA = "promopages-10060-tune-approved-upload-report/v1"
EXPECTED_MODELS = {
    "alibaba/wan-2.2": 16,
    "alibaba/wan-2.7": 12,
    "google/veo-3.1-lite": 17,
}
EXPECTED_KINDS = {"explicit-latest-wan": 2, "helped": 43}
EXPECTED_SOURCES = {
    "explicit-latest-wan": 2,
    "v4-evaluation": 37,
    "v6-evaluation": 6,
}
FORCED_IDS = (
    "17#11::alibaba/wan-2.2",
    "18#06::alibaba/wan-2.2",
)
FORCED_PRIOR_V4_OUTCOMES = {
    "17#11::alibaba/wan-2.2": "worse",
    "18#06::alibaba/wan-2.2": "same-or-unclear",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EVALUATION_ID = re.compile(
    r"^(?P<case>\d{2}#\d{2})::"
    r"(?P<model>alibaba/wan-2\.[27]|google/veo-3\.1-lite)$"
)
SELECTION_FIELDS = (
    "evaluation_id", "sheet_row", "case_id", "article_number",
    "article_slug", "image_id", "model_id", "approval_kind",
    "approval_source", "generation_origin", "source_video_path",
    "sha256", "bytes",
)


def _repo_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(
            root.resolve(strict=True)
        ).as_posix()
    except (OSError, ValueError) as error:
        raise ExportError(f"Input is outside repository: {path}") from error


def _receipt_file(
    root: Path, receipt: Mapping[str, Any], label: str
) -> Path:
    if not isinstance(receipt.get("path"), str) or not isinstance(
        receipt.get("sha256"), str
    ):
        raise ExportError(f"{label} receipt is incomplete")
    path = base._safe_repo_file(root, receipt["path"])
    actual = base._sha256_file(path)
    if actual != receipt["sha256"]:
        raise ExportError(
            f"{label} SHA-256 mismatch: {actual} != {receipt['sha256']}"
        )
    return path


def _counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "selected_outputs": len(rows),
        "approval_kinds": dict(sorted(Counter(
            str(row["approval_kind"]) for row in rows
        ).items())),
        "approval_sources": dict(sorted(Counter(
            str(row["approval_source"]) for row in rows
        ).items())),
        "models": dict(sorted(Counter(
            str(row["model_id"]) for row in rows
        ).items())),
    }


def _evaluation_doc(
    path: Path, receipt: Mapping[str, Any]
) -> Dict[str, Any]:
    doc = base._load_json(path)
    if (
        doc.get("export_role") != "clipmaker-lite-tune-evaluation"
        or doc.get("dataset", {}).get("ticket") != "PROMOPAGES-10060"
        or doc.get("dataset", {}).get("batch_id") != receipt.get("batch_id")
        or not isinstance(doc.get("evaluations"), list)
    ):
        raise ExportError(f"Invalid frozen evaluation input: {path}")
    return doc


def _approval_map(
    v4: Mapping[str, Any], v6: Mapping[str, Any]
) -> Dict[str, Dict[str, Any]]:
    approved: Dict[str, Dict[str, Any]] = {}
    seen_v4: set[str] = set()
    for item in v4["evaluations"]:
        evaluation_id = str(item.get("evaluation_id"))
        if evaluation_id in seen_v4:
            raise ExportError(f"Duplicate v4 evaluation_id: {evaluation_id}")
        seen_v4.add(evaluation_id)
        if item.get("outcome") == "helped":
            approved[evaluation_id] = {
                "entry": item, "approval_kind": "helped",
                "approval_source": "v4-evaluation",
            }
    seen_v6: set[str] = set()
    for item in v6["evaluations"]:
        evaluation_id = str(item.get("evaluation_id"))
        if evaluation_id in seen_v6:
            raise ExportError(f"Duplicate v6 evaluation_id: {evaluation_id}")
        seen_v6.add(evaluation_id)
        if item.get("outcome") == "helped":
            approved[evaluation_id] = {
                "entry": item, "approval_kind": "helped",
                "approval_source": "v6-evaluation",
            }
    return approved


def _targets(tune: Mapping[str, Any]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    if (
        tune.get("manifest_role") != "clipmaker-lite-tune-review"
        or tune.get("ticket") != "PROMOPAGES-10060"
        or not isinstance(tune.get("cases"), list)
    ):
        raise ExportError("Invalid Tune manifest")
    result: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for case in tune["cases"]:
        for target in case.get("targets", []):
            key = (str(case.get("case_id")), str(target.get("model_id")))
            if key in result:
                raise ExportError(f"Duplicate Tune target: {key}")
            result[key] = {"case": case, "target": target}
    return result


def _bind(
    evaluation_id: str,
    approval_kind: str,
    approval_source: str,
    targets: Mapping[Tuple[str, str], Mapping[str, Any]],
    evaluation: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    match = EVALUATION_ID.fullmatch(evaluation_id)
    if match is None:
        raise ExportError(f"Invalid evaluation_id: {evaluation_id}")
    binding = targets.get((match.group("case"), match.group("model")))
    if binding is None:
        raise ExportError(f"No current Tune target: {evaluation_id}")
    case = binding["case"]
    target = binding["target"]
    video = target.get("tuned", {}).get("video")
    if not isinstance(video, Mapping) or video.get("state") != "available":
        raise ExportError(f"No current Tune video: {evaluation_id}")
    if (
        video.get("status") not in {"succeeded", "verification-failed"}
        or video.get("method") != "eliza-i2v"
        or video.get("delivery") != "repository-raw"
        or video.get("prompt_evaluated") is not True
    ):
        raise ExportError(
            f"Current Tune video transport is not approved: {evaluation_id}"
        )
    sha256 = video.get("sha256")
    size = video.get("bytes")
    video_path = video.get("repository_video_path")
    origin = video.get("generation", {}).get("origin")
    sheet_row = target.get("sheet_row")
    if (
        not isinstance(sha256, str) or HEX64.fullmatch(sha256) is None
        or not isinstance(size, int) or isinstance(size, bool) or size <= 0
        or not isinstance(video_path, str) or not video_path
        or not isinstance(origin, str) or not origin
        or not isinstance(sheet_row, int) or isinstance(sheet_row, bool)
    ):
        raise ExportError(f"Incomplete current Tune binding: {evaluation_id}")
    if evaluation is not None:
        evaluated_video = evaluation.get("tuned_video")
        if (
            evaluation.get("outcome") != "helped"
            or evaluation.get("case_id") != case.get("case_id")
            or evaluation.get("article_number") != case.get("article_number")
            or evaluation.get("article_slug") != case.get("article_slug")
            or evaluation.get("image_id") != case.get("source", {}).get("image_id")
            or evaluation.get("model_id") != target.get("model_id")
            or not isinstance(evaluated_video, Mapping)
            or evaluated_video.get("repository_video_path") != video_path
            or evaluated_video.get("sha256") != sha256
        ):
            raise ExportError(
                f"Helped evaluation differs from current Tune: {evaluation_id}"
            )
    return {
        "evaluation_id": evaluation_id,
        "sheet_row": sheet_row,
        "case_id": case["case_id"],
        "article_number": case["article_number"],
        "article_slug": case["article_slug"],
        "image_id": case["source"]["image_id"],
        "model_id": target["model_id"],
        "approval_kind": approval_kind,
        "approval_source": approval_source,
        "generation_origin": origin,
        "source_video_path": video_path,
        "sha256": sha256,
        "bytes": size,
    }


def validate_selection(
    root: Path, contract_path: Path
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    root = root.resolve(strict=True)
    contract_path = contract_path.resolve(strict=True)
    if _repo_relative(root, contract_path) != (
        "PROMOPAGES-10060/tune-s3-export/selection-contract.json"
    ):
        raise ExportError("Selection contract path is not locked")
    contract = base._load_json(contract_path)
    if (
        contract.get("schema_version") != 1
        or contract.get("manifest_role") != CONTRACT_ROLE
        or contract.get("ticket") != "PROMOPAGES-10060"
    ):
        raise ExportError("Invalid selection contract identity")
    receipts = contract.get("evaluation_inputs")
    if (
        not isinstance(receipts, list) or len(receipts) != 2
        or [row.get("kind") for row in receipts]
        != ["v4-evaluation", "v6-evaluation"]
    ):
        raise ExportError("Contract must bind exact v4/v6 inputs")
    v4 = _evaluation_doc(
        _receipt_file(root, receipts[0], "v4 evaluation"), receipts[0]
    )
    v6 = _evaluation_doc(
        _receipt_file(root, receipts[1], "v6 evaluation"), receipts[1]
    )
    tune_receipt = contract.get("tune_manifest")
    routing_receipt = contract.get("routing_config")
    if not isinstance(tune_receipt, Mapping) or not isinstance(
        routing_receipt, Mapping
    ):
        raise ExportError("Contract Tune/routing receipts missing")
    tune = base._load_json(_receipt_file(root, tune_receipt, "Tune manifest"))
    if (
        tune.get("batch_id") != tune_receipt.get("batch_id")
        or tune.get("lineage", {}).get("media_commit_sha")
        != tune_receipt.get("media_commit_sha")
    ):
        raise ExportError("Tune receipt metadata differs")
    routing_path = _receipt_file(root, routing_receipt, "routing config")
    articles = base._load_articles(routing_path)

    policy = contract.get("selection_policy")
    expected_policy = {
        "approved_outcome": "helped",
        "deduplication_key": "evaluation_id",
        "precedence": (
            "v6-helped-over-v4; preserve-v4-helped-when-v6-is-not-helped"
        ),
        "explicit_latest_wan_evaluation_ids": list(FORCED_IDS),
        "current_tune_binding_required": True,
        "previous_tuned_fallback_allowed": False,
    }
    if policy != expected_policy:
        raise ExportError("Selection policy differs")
    approvals = _approval_map(v4, v6)
    v4_by_id = {
        str(item.get("evaluation_id")): item for item in v4["evaluations"]
    }
    v6_ids = {
        str(item.get("evaluation_id")) for item in v6["evaluations"]
    }
    for evaluation_id, expected_outcome in (
        FORCED_PRIOR_V4_OUTCOMES.items()
    ):
        if (
            v4_by_id.get(evaluation_id, {}).get("outcome")
            != expected_outcome
            or evaluation_id in v6_ids
        ):
            raise ExportError(
                f"Forced latest Wan prior evaluation drift: {evaluation_id}"
            )
    target_map = _targets(tune)
    selected: List[Dict[str, Any]] = []
    for evaluation_id, approval in approvals.items():
        selected.append(_bind(
            evaluation_id, approval["approval_kind"],
            approval["approval_source"], target_map, approval["entry"],
        ))
    for evaluation_id in FORCED_IDS:
        if evaluation_id in approvals:
            raise ExportError(f"Forced ID overlaps Helped: {evaluation_id}")
        selected.append(_bind(
            evaluation_id, "explicit-latest-wan",
            "explicit-latest-wan", target_map, None,
        ))
    selected.sort(key=lambda row: row["sheet_row"])

    contract_items = contract.get("items")
    expected_items = [
        {
            "evaluation_id": row["evaluation_id"],
            "approval_kind": row["approval_kind"],
            "approval_source": row["approval_source"],
        }
        for row in selected
    ]
    if contract_items != expected_items:
        raise ExportError("Frozen contract items differ from derived selection")
    actual_counts = _counts(selected)
    locked_counts = {
        "selected_outputs": 45,
        "approval_kinds": EXPECTED_KINDS,
        "approval_sources": EXPECTED_SOURCES,
        "models": EXPECTED_MODELS,
    }
    if actual_counts != locked_counts or contract.get(
        "expected_counts"
    ) != locked_counts:
        raise ExportError(f"Selection count mismatch: {actual_counts}")
    if len({row["evaluation_id"] for row in selected}) != 45:
        raise ExportError("Selection evaluation_id values are not unique")
    for fields, label in (
        (("article_slug", "image_id", "model_id"), "logical key"),
        (("source_video_path",), "source video path"),
        (("sha256",), "video SHA-256"),
    ):
        values = {tuple(row[field] for field in fields) for row in selected}
        if len(values) != 45:
            raise ExportError(f"Selection {label} values are not unique")
    return contract, selected, articles


LINK_FIELDS = (
    "evaluation_id", "sheet_row", "article_number", "article_slug",
    "publication_id", "image_id", "model_id", "experiment",
    "approval_kind", "approval_source", "generation_origin", "bytes",
    "sha256", "object_key", "yastatic_url",
)


def _links_csv(outputs: Sequence[Mapping[str, Any]]) -> str:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=LINK_FIELDS, lineterminator="\n"
    )
    writer.writeheader()
    for output in outputs:
        writer.writerow({
            field: output.get(field, "") for field in LINK_FIELDS
        })
    return buffer.getvalue()


def _sums(outputs: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        f"{row['sha256']}  upload/{row['relative_path']}\n"
        for row in outputs
    )


def _command_text() -> str:
    return (
        "# Dry-run: no external calls or writes\n"
        "python3 scripts/promopages_10060_tune_s3_export.py upload "
        "--output PROMOPAGES-10060/tune-s3-export/output\n\n"
        "# Execute and publish overlay only after 45/45 verification\n"
        "python3 scripts/promopages_10060_tune_s3_export.py upload "
        "--output PROMOPAGES-10060/tune-s3-export/output "
        "--yc-profile promopages-internal --execute\n"
    )


def _route(
    row: Mapping[str, Any], article: Mapping[str, Any]
) -> Tuple[str, str]:
    cabinet = article["cabinet"]
    relative = PurePosixPath(
        f"{cabinet['slug']}__{cabinet['id']}",
        article["publication_id"],
        base.MODEL_DIRS[row["model_id"]],
        f"image_{row['image_id']}--sha256-{row['sha256'][:12]}.mp4",
    ).as_posix()
    base._safe_package_relative_path(relative)
    return relative, base.OBJECT_PREFIX + relative


def build_export(
    root: Path,
    contract_path: Path,
    output_dir: Path,
    *,
    materialize_mode: str = "auto",
) -> Dict[str, Any]:
    root = root.resolve(strict=True)
    contract_path = contract_path.resolve(strict=True)
    output_dir = output_dir.resolve(strict=False)
    contract, selected, articles = validate_selection(root, contract_path)
    article_map = {
        article["article_slug"]: article for article in articles
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{output_dir.name}.staging-", dir=output_dir.parent
    ))
    outputs: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    try:
        for row in selected:
            article = article_map.get(row["article_slug"])
            if article is None or article.get("source_status") != "available":
                raise ExportError(
                    f"No available route: {row['evaluation_id']}"
                )
            source = base._safe_repo_file(root, row["source_video_path"])
            sha256, md5_base64, size = base._hash_file(source)
            if sha256 != row["sha256"] or size != row["bytes"]:
                raise ExportError(
                    f"Approved source drift: {row['evaluation_id']}"
                )
            relative, object_key = _route(row, article)
            if object_key in seen_keys:
                raise ExportError(
                    f"Duplicate immutable object key: {object_key}"
                )
            seen_keys.add(object_key)
            base._materialize(
                source,
                staging / "upload" / Path(*PurePosixPath(relative).parts),
                materialize_mode,
            )
            outputs.append({
                **row,
                "package_status": "ready",
                "cabinet": article["cabinet"],
                "publication_id": article["publication_id"],
                "experiment": base.MODEL_DIRS[row["model_id"]],
                "relative_path": relative,
                "object_key": object_key,
                "yastatic_url": base._public_url(object_key),
                "media": {
                    "sha256": sha256,
                    "md5_base64": md5_base64,
                    "bytes": size,
                },
            })
        selection_receipt = {
            "path": _repo_relative(root, contract_path),
            "sha256": base._sha256_file(contract_path),
        }
        counts = {
            **_counts(outputs),
            "articles": len({
                row["article_slug"] for row in outputs
            }),
            "bytes": sum(row["bytes"] for row in outputs),
        }
        manifest = {
            "schema_version": PACKAGE_SCHEMA,
            "manifest_role": PACKAGE_ROLE,
            "package_id": (
                "PROMOPAGES-10060-tune-approved-v1-"
                + selection_receipt["sha256"][:12]
            ),
            "ticket": "PROMOPAGES-10060",
            "bucket": base.BUCKET,
            "object_prefix": base.OBJECT_PREFIX,
            "public_base_url": base.PUBLIC_BASE_URL,
            "content_type": base.CONTENT_TYPE,
            "cache_control": base.CACHE_CONTROL,
            "model_directory_map": base.MODEL_DIRS,
            "selection_contract": selection_receipt,
            "evaluation_inputs": contract["evaluation_inputs"],
            "selection_policy": contract["selection_policy"],
            "tune_manifest": contract["tune_manifest"],
            "routing_config": contract["routing_config"],
            "counts": counts,
            "outputs": outputs,
        }
        base._write_json(staging / "manifest.json", manifest)
        (staging / "links.csv").write_text(
            _links_csv(outputs), encoding="utf-8"
        )
        (staging / "SHA256SUMS").write_text(
            _sums(outputs), encoding="utf-8"
        )
        (staging / "upload-command.txt").write_text(
            _command_text(), encoding="utf-8"
        )
        base._safe_replace_output(staging, output_dir)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def verify_export(
    output_dir: Path, *, root: Path = REPO_ROOT
) -> Dict[str, Any]:
    root = root.resolve(strict=True)
    output_dir = output_dir.resolve(strict=True)
    manifest = base._load_json(output_dir / "manifest.json")
    if (
        manifest.get("schema_version") != PACKAGE_SCHEMA
        or manifest.get("manifest_role") != PACKAGE_ROLE
        or manifest.get("ticket") != "PROMOPAGES-10060"
        or manifest.get("bucket") != base.BUCKET
        or manifest.get("object_prefix") != base.OBJECT_PREFIX
        or manifest.get("public_base_url") != base.PUBLIC_BASE_URL
        or manifest.get("content_type") != base.CONTENT_TYPE
        or manifest.get("cache_control") != base.CACHE_CONTROL
        or manifest.get("model_directory_map") != base.MODEL_DIRS
    ):
        raise ExportError("Package identity/transport contract differs")
    contract_receipt = manifest.get("selection_contract")
    if not isinstance(contract_receipt, Mapping):
        raise ExportError("Package selection receipt missing")
    contract_path = _receipt_file(
        root, contract_receipt, "selection contract"
    )
    contract, selected, articles = validate_selection(
        root, contract_path
    )
    for field in (
        "evaluation_inputs", "selection_policy", "tune_manifest",
        "routing_config",
    ):
        if manifest.get(field) != contract[field]:
            raise ExportError(f"Package {field} differs from contract")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 45:
        raise ExportError("Package must contain exactly 45 outputs")
    article_map = {
        article["article_slug"]: article for article in articles
    }
    expected_files: set[str] = set()
    seen_keys: set[str] = set()
    verified_bytes = 0
    for output, selected_row in zip(outputs, selected):
        for field in SELECTION_FIELDS:
            if output.get(field) != selected_row[field]:
                raise ExportError(
                    f"Selection drift: {selected_row['evaluation_id']}/{field}"
                )
        if output.get("package_status") != "ready":
            raise ExportError(
                f"Approved output unavailable: {selected_row['evaluation_id']}"
            )
        article = article_map[selected_row["article_slug"]]
        relative, object_key = _route(selected_row, article)
        if (
            output.get("cabinet") != article["cabinet"]
            or output.get("publication_id") != article["publication_id"]
            or output.get("experiment")
            != base.MODEL_DIRS[selected_row["model_id"]]
            or output.get("relative_path") != relative
            or output.get("object_key") != object_key
            or output.get("yastatic_url") != base._public_url(object_key)
        ):
            raise ExportError(
                f"S3 route drift: {selected_row['evaluation_id']}"
            )
        if object_key in seen_keys:
            raise ExportError(f"Duplicate object key: {object_key}")
        seen_keys.add(object_key)
        package_relative = PurePosixPath(
            "upload", relative
        ).as_posix()
        expected_files.add(package_relative)
        candidate = output_dir / Path(
            *PurePosixPath(package_relative).parts
        )
        if candidate.is_symlink() or not candidate.is_file():
            raise ExportError(f"Missing package file: {package_relative}")
        sha256, md5_base64, size = base._hash_file(candidate)
        expected_media = {
            "sha256": sha256,
            "md5_base64": md5_base64,
            "bytes": size,
        }
        if (
            sha256 != selected_row["sha256"]
            or size != selected_row["bytes"]
            or output.get("media") != expected_media
        ):
            raise ExportError(
                f"Package media drift: {selected_row['evaluation_id']}"
            )
        verified_bytes += size
    actual_files: set[str] = set()
    for candidate in (output_dir / "upload").rglob("*"):
        if candidate.is_symlink():
            raise ExportError(f"Symlink in upload tree: {candidate}")
        if candidate.is_file():
            actual_files.add(
                candidate.relative_to(output_dir).as_posix()
            )
    if actual_files != expected_files:
        raise ExportError(
            "Upload tree differs: "
            f"missing={sorted(expected_files-actual_files)}, "
            f"extra={sorted(actual_files-expected_files)}"
        )
    counts = {
        **_counts(outputs),
        "articles": len({
            row["article_slug"] for row in outputs
        }),
        "bytes": verified_bytes,
    }
    if manifest.get("counts") != counts:
        raise ExportError("Package counts are stale")
    sidecars = {
        "links.csv": _links_csv(outputs),
        "SHA256SUMS": _sums(outputs),
        "upload-command.txt": _command_text(),
    }
    for filename, expected in sidecars.items():
        try:
            actual = (output_dir / filename).read_text(
                encoding="utf-8"
            )
        except OSError as error:
            raise ExportError(
                f"Cannot read sidecar {filename}: {error}"
            ) from error
        if actual != expected:
            raise ExportError(f"Stale sidecar: {filename}")
    return {
        "verified": True,
        "package_id": manifest["package_id"],
        "selected_outputs": 45,
        "model_counts": EXPECTED_MODELS,
        "bytes": verified_bytes,
    }


def _overlay(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    fields = (
        "evaluation_id", "sheet_row", "case_id", "article_number",
        "article_slug", "publication_id", "image_id", "model_id",
        "experiment", "approval_kind", "approval_source",
        "generation_origin", "source_video_path", "sha256", "bytes",
        "object_key", "yastatic_url",
    )
    outputs = [
        {field: row[field] for field in fields}
        for row in manifest["outputs"]
    ]
    return {
        "schema_version": 1,
        "manifest_role": OVERLAY_ROLE,
        "ticket": "PROMOPAGES-10060",
        "bucket": base.BUCKET,
        "object_prefix": base.OBJECT_PREFIX,
        "public_base_url": base.PUBLIC_BASE_URL,
        "selection_contract": manifest["selection_contract"],
        "evaluation_inputs": manifest["evaluation_inputs"],
        "selection_policy": manifest["selection_policy"],
        "tune_manifest": manifest["tune_manifest"],
        "selected_output_count": len(outputs),
        "model_counts": EXPECTED_MODELS,
        "outputs": outputs,
    }


def _publish_overlay(path: Path, value: Mapping[str, Any]) -> None:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ExportError(f"Overlay path is symlinked: {candidate}")
    path = candidate.resolve(strict=False)
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise ExportError(f"Overlay path is not regular: {path}")
        if base._load_json(path) != value:
            raise ExportError(f"Immutable overlay conflict: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    base._atomic_write_json(path, value)


SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(authorization|bearer|token|api[_-]?key|access[_-]?key|"
    r"secret|signature|credential|password)\b"
    r"(\s*[:=]\s*|\s+)([^\s,;]+)"
)
AUTHORIZATION = re.compile(
    r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"
)
BEARER = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
SECRET_QUERY = re.compile(
    r"(?i)([?&](?:token|key|api[_-]?key|access[_-]?key|"
    r"signature|secret|credential|password)=)[^&\s]+"
)
JWT = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r"(?:\.[A-Za-z0-9_-]{8,})?\b"
)
ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b")
YANDEX_TOKEN_STYLE = re.compile(
    r"\b(?:y[01]_[A-Za-z0-9_-]{8,}|"
    r"t[01]_[A-Za-z0-9_-]{8,}|AQAD-[A-Za-z0-9_-]{8,})\b"
)


def _redact(value: Any) -> str:
    text = str(value)
    text = AUTHORIZATION.sub(r"\1[REDACTED]", text)
    text = BEARER.sub("Bearer [REDACTED]", text)
    text = SECRET_ASSIGNMENT.sub(
        lambda match: (
            match.group(1) + match.group(2) + "[REDACTED]"
        ),
        text,
    )
    text = SECRET_QUERY.sub(r"\1[REDACTED]", text)
    text = JWT.sub("[REDACTED_JWT]", text)
    text = ACCESS_KEY.sub("[REDACTED_ACCESS_KEY]", text)
    return YANDEX_TOKEN_STYLE.sub("[REDACTED_YANDEX_TOKEN]", text)


def _safe_process_json(
    result: subprocess.CompletedProcess[str], operation: str
) -> Dict[str, Any]:
    if result.returncode != 0:
        detail = _redact(
            result.stderr or result.stdout or "unknown error"
        ).strip()
        raise ExportError(f"{operation} failed: {detail}")
    if not result.stdout.strip():
        return {}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ExportError(
            f"{operation} returned invalid JSON: "
            + _redact(result.stdout[:500])
        ) from error
    return value if isinstance(value, dict) else {"value": value}


def _run_yc_safe(
    command: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(list(command), capture_output=True, text=True)
    except OSError as error:
        raise ExportError(_redact(error)) from None


def _head_safe(
    row: Mapping[str, Any],
    yc_profile: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> Optional[Dict[str, Any]]:
    command = [
        "yc", "storage", "s3api", "head-object",
        "--profile", yc_profile, "--format", "json",
        "--bucket", base.BUCKET, "--key", row["object_key"],
    ]
    result = _run_yc_safe(command, runner)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").lower()
        if any(marker in detail for marker in (
            "nosuchkey", "not found", "status code: 404",
            "statuscode: 404", "statuscode=404",
        )):
            return None
    return _safe_process_json(
        result, f"S3 HEAD {row['object_key']}"
    )


def _put_safe(
    output_dir: Path,
    row: Mapping[str, Any],
    yc_profile: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> Dict[str, Any]:
    relative = base._safe_package_relative_path(row["relative_path"])
    body = output_dir / "upload" / Path(*relative.parts)
    metadata = ",".join((
        f"sha256={row['sha256']}",
        f"publication-id={row['publication_id']}",
        f"image-id={row['image_id']}",
        f"experiment={row['experiment']}",
    ))
    command = [
        "yc", "storage", "s3api", "put-object",
        "--profile", yc_profile, "--format", "json",
        "--bucket", base.BUCKET, "--key", row["object_key"],
        "--body", str(body),
        "--content-md5", row["media"]["md5_base64"],
        "--content-type", base.CONTENT_TYPE,
        "--cache-control", base.CACHE_CONTROL,
        "--content-disposition", "inline",
        "--metadata", metadata,
    ]
    return _safe_process_json(
        _run_yc_safe(command, runner),
        f"S3 PUT {row['object_key']}",
    )


def upload_export(
    output_dir: Path,
    *,
    execute: bool,
    root: Path = REPO_ROOT,
    yc_profile: Optional[str] = None,
    overlay_path: Path = DEFAULT_OVERLAY_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    yastatic_verifier: Callable[
        [Mapping[str, Any]], Dict[str, Any]
    ] = base._verify_yastatic,
) -> Dict[str, Any]:
    verification = verify_export(output_dir, root=root)
    output_dir = output_dir.resolve(strict=True)
    manifest = base._load_json(output_dir / "manifest.json")
    outputs = manifest["outputs"]
    operations = [
        {
            "operation": "head-then-put-if-missing",
            "object_key": row["object_key"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
            "yastatic_url": row["yastatic_url"],
        }
        for row in outputs
    ]
    if not execute:
        return {
            "mode": "dry-run",
            "external_calls": 0,
            "external_writes": 0,
            "overlay_written": False,
            "local_verification": verification,
            "operation_count": len(operations),
            "bytes": sum(row["bytes"] for row in operations),
            "operations": operations,
        }
    if not yc_profile:
        raise ExportError("--yc-profile is required with --execute")
    preflight = [
        "yc", "storage", "s3api", "list-objects-v2",
        "--profile", yc_profile, "--format", "json",
        "--bucket", base.BUCKET, "--prefix", base.OBJECT_PREFIX,
        "--max-keys", "1",
    ]
    _safe_process_json(
        _run_yc_safe(preflight, runner), "S3 access preflight"
    )
    report: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "package_id": manifest["package_id"],
        "bucket": base.BUCKET,
        "object_prefix": base.OBJECT_PREFIX,
        "yc_profile": yc_profile,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "counts": {
            "total": 45, "uploaded": 0, "skipped": 0, "verified": 0
        },
        "objects": [],
    }
    report_path = output_dir / "upload-report.json"
    base._atomic_write_json(report_path, report)
    for row in outputs:
        entry: Dict[str, Any] = {
            "evaluation_id": row["evaluation_id"],
            "object_key": row["object_key"],
            "yastatic_url": row["yastatic_url"],
            "action": "pending",
            "status": "pending",
            "s3_head": None,
            "put_result": None,
            "yastatic": None,
            "error": None,
        }
        report["objects"].append(entry)
        base._atomic_write_json(report_path, report)
        stage = "s3-head"
        try:
            head = _head_safe(row, yc_profile, runner)
            entry["s3_head"] = head
            if head is not None and not base._head_matches(row, head):
                entry["action"] = "conflict"
                entry["status"] = "conflict"
                raise ExportError(
                    "Immutable object key conflict; refusing overwrite: "
                    + row["object_key"]
                )
            if head is None:
                stage = "upload"
                entry["put_result"] = _put_safe(
                    output_dir, row, yc_profile, runner
                )
                entry["action"] = "uploaded"
                entry["status"] = "uploaded-awaiting-verification"
                report["counts"]["uploaded"] += 1
                base._atomic_write_json(report_path, report)
                stage = "s3-verification"
                head = _head_safe(row, yc_profile, runner)
                entry["s3_head"] = head
                if head is None or not base._head_matches(row, head):
                    raise ExportError(
                        f"S3 post-upload verification failed: "
                        f"{row['object_key']}"
                    )
            else:
                entry["action"] = "skipped"
                report["counts"]["skipped"] += 1
            stage = "yastatic-verification"
            entry["yastatic"] = yastatic_verifier(row)
            if entry["yastatic"].get("verified") is not True:
                raise ExportError(
                    f"yastatic did not verify: {row['yastatic_url']}"
                )
            entry["status"] = "verified"
            report["counts"]["verified"] += 1
            base._atomic_write_json(report_path, report)
        except (ExportError, OSError, ValueError) as error:
            safe_error = _redact(error)
            if entry["status"] != "conflict":
                entry["status"] = stage + "-failed"
            entry["error"] = safe_error
            base._atomic_write_json(report_path, report)
            raise ExportError(safe_error) from None
    if report["counts"]["verified"] != 45:
        raise ExportError("Refusing to publish a partial overlay")
    overlay = _overlay(manifest)
    _publish_overlay(overlay_path, overlay)
    (output_dir / "verified-links.csv").write_text(
        _links_csv(outputs), encoding="utf-8"
    )
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["overlay"] = {
        "path": str(overlay_path),
        "sha256": base._sha256_file(overlay_path.resolve(strict=True)),
    }
    base._atomic_write_json(report_path, report)
    return report


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    selection = subparsers.add_parser("validate-selection")
    selection.add_argument("--root", type=_path, default=REPO_ROOT)
    selection.add_argument(
        "--contract", type=_path, default=DEFAULT_CONTRACT_PATH
    )
    build = subparsers.add_parser("build")
    build.add_argument("--root", type=_path, default=REPO_ROOT)
    build.add_argument(
        "--contract", type=_path, default=DEFAULT_CONTRACT_PATH
    )
    build.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)
    build.add_argument(
        "--materialize",
        choices=("auto", "hardlink", "copy"),
        default="auto",
    )
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", type=_path, default=REPO_ROOT)
    verify.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)
    upload = subparsers.add_parser("upload")
    upload.add_argument("--root", type=_path, default=REPO_ROOT)
    upload.add_argument("--output", type=_path, default=DEFAULT_OUTPUT_DIR)
    upload.add_argument("--overlay", type=_path, default=DEFAULT_OVERLAY_PATH)
    upload.add_argument("--yc-profile", default="promopages-internal")
    upload.add_argument("--execute", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-selection":
            contract, selected, _articles = validate_selection(
                args.root, args.contract
            )
            summary = {
                "verified": True,
                "counts": contract["expected_counts"],
                "evaluation_ids": [
                    row["evaluation_id"] for row in selected
                ],
            }
        elif args.command == "build":
            manifest = build_export(
                args.root,
                args.contract,
                args.output,
                materialize_mode=args.materialize,
            )
            summary = {
                "built": True,
                "output": str(args.output),
                "counts": manifest["counts"],
            }
        elif args.command == "verify":
            summary = verify_export(args.output, root=args.root)
        else:
            summary = upload_export(
                args.output,
                execute=args.execute,
                root=args.root,
                yc_profile=args.yc_profile,
                overlay_path=args.overlay,
            )
            if not args.execute:
                summary = {
                    key: value for key, value in summary.items()
                    if key != "operations"
                }
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0
    except (ExportError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
