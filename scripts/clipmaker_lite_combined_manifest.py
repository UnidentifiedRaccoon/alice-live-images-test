#!/usr/bin/env python3
"""Build and verify the combined PROMOPAGES-9891 generation manifest.

The canonical manifest joins two deliberately different routes:

* ten native, attested Clipmaker Lite outputs from the private native aggregate;
* five non-Lite Wan 2.2 controls from the wan-streamlit control plan and its
  article-local run metadata.

This module is metadata-only: it performs no provider or network operations.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = 1
TICKET = "PROMOPAGES-9891"
AGENT_ID = "clipmaker-lite"
EXPECTED_NATIVE_OUTPUTS = 10
EXPECTED_CONTROL_OUTPUTS = 5
EXPECTED_OUTPUTS = EXPECTED_NATIVE_OUTPUTS + EXPECTED_CONTROL_OUTPUTS

NATIVE_ROUTE = "native"
CONTROL_ROUTE = "wan-streamlit-control"
NATIVE_MODELS = ("alibaba/wan-2.7", "google/veo-3.1-lite")
CONTROL_MODEL = "alibaba/wan-2.2"
CONTROL_PROMPT_SOURCE_MODEL = "alibaba/wan-2.7"

DEFAULT_NATIVE_MANIFEST = Path(
    "PROMOPAGES-9857/clipmaker-lite-native-generation-manifest.json"
)
DEFAULT_CONTROL_PLAN = Path(
    "artifacts/clipmaker-lite-controls/promopages-9891-wan-streamlit-wan-2.2.json"
)
DEFAULT_OUTPUT = Path("PROMOPAGES-9857/clipmaker-lite-generation-manifest.json")

NATIVE_COMPLETE_STATUS = "succeeded"
CONTROL_COMPLETE_STATUS = "verified"
FAILURE_STATUSES = {
    "failed",
    "failed-pre-submit",
    "provider-failed",
    "stale",
    "submit-unknown",
}

FORBIDDEN_METADATA_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "content_url",
    "download_url",
    "header",
    "headers",
    "signed_url",
    "source_url",
    "token",
    "url",
}


class CombinedManifestError(RuntimeError):
    """A fail-closed manifest validation error safe to show to the user."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CombinedManifestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> Any:
    if not path.is_file() or path.is_symlink():
        raise CombinedManifestError(
            f"{label} is missing, not a regular file, or a symlink: {path}"
        )
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CombinedManifestError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CombinedManifestError(f"could not read {label}: {path}: {exc}") from exc


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def safe_error(value: Any) -> str:
    """Return a compact diagnostic without URLs or credential values."""

    message = str(value)
    message = re.sub(r"https?://[^\s\]\[{}<>'\"]+", "[REDACTED_URL]", message)
    message = re.sub(
        r"(?i)\b(authorization|oauth|bearer|api[-_]?key|token|signature|sig)\b"
        r"\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?i)([?&](?:token|signature|sig|key|auth)=)[^&\s]+",
        r"\1[REDACTED]",
        message,
    )
    return " ".join(message.split())[:1000]


def assert_sanitized_metadata(value: Any, label: str = "metadata") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_METADATA_KEYS:
                raise CombinedManifestError(
                    f"forbidden metadata key {key!r} in {label}"
                )
            assert_sanitized_metadata(child, f"{label}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_sanitized_metadata(child, f"{label}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise CombinedManifestError(f"non-finite number in {label}")
    if isinstance(value, str):
        if re.search(r"https?://", value, flags=re.I):
            raise CombinedManifestError(f"URL leaked into {label}")
        if re.search(r"(?i)\b(?:bearer|oauth)\s+[A-Za-z0-9._~+/=-]+", value):
            raise CombinedManifestError(f"credential leaked into {label}")
        if re.search(r"(?i)[?&](?:token|key|signature|sig|auth)=", value):
            raise CombinedManifestError(f"signed query leaked into {label}")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CombinedManifestError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CombinedManifestError(f"{label} must be an array")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CombinedManifestError(f"{label} must be a non-empty string")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise CombinedManifestError(f"{label} must be a boolean")
    return value


def _rooted(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def workspace_relative(root: Path, path: Path, label: str) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise CombinedManifestError(f"{label} escapes the workspace: {path}") from exc


def resolve_workspace_path(root: Path, raw: Any, label: str) -> Path:
    value = _string(raw, label)
    path = Path(value)
    if path.is_absolute():
        raise CombinedManifestError(f"{label} must be workspace-relative")
    resolved = (root / path).resolve()
    workspace_relative(root, resolved, label)
    if resolved.as_posix() == root.resolve().as_posix():
        raise CombinedManifestError(f"{label} must point below the workspace root")
    return resolved


def _path(value: Any, root: Path, label: str) -> str:
    raw = _string(value, label)
    resolve_workspace_path(root, raw, label)
    return Path(raw).as_posix()


def _native_outputs(root: Path, manifest: Any) -> list[dict[str, Any]]:
    native = _mapping(manifest, "native manifest")
    assert_sanitized_metadata(native, "native manifest")
    if native.get("schema_version") != SCHEMA_VERSION:
        raise CombinedManifestError("native manifest has an unsupported schema_version")
    if native.get("ticket") != TICKET or native.get("agent_id") != AGENT_ID:
        raise CombinedManifestError("native manifest identity does not match PROMOPAGES-9891")
    if native.get("expected_outputs") != EXPECTED_NATIVE_OUTPUTS:
        raise CombinedManifestError(
            f"native manifest must declare {EXPECTED_NATIVE_OUTPUTS} outputs"
        )
    rows = _list(native.get("outputs"), "native manifest.outputs")
    if len(rows) != EXPECTED_NATIVE_OUTPUTS:
        raise CombinedManifestError(
            f"native manifest must contain {EXPECTED_NATIVE_OUTPUTS} outputs"
        )

    outputs: list[dict[str, Any]] = []
    ids: set[str] = set()
    path_sets: dict[str, set[str]] = {
        "prompt_path": set(),
        "run_path": set(),
        "video_path": set(),
    }
    model_counts: Counter[str] = Counter()
    sources_by_model: dict[str, set[str]] = {model: set() for model in NATIVE_MODELS}

    for index, raw_row in enumerate(rows):
        label = f"native manifest.outputs[{index}]"
        row = _mapping(raw_row, label)
        lite_run_id = _string(row.get("lite_run_id"), f"{label}.lite_run_id")
        if lite_run_id in ids:
            raise CombinedManifestError(f"duplicate native lite_run_id: {lite_run_id}")
        ids.add(lite_run_id)

        target_model_id = _string(row.get("model_id"), f"{label}.model_id")
        if target_model_id not in NATIVE_MODELS:
            raise CombinedManifestError(
                f"unsupported native target model: {target_model_id}"
            )
        model_counts[target_model_id] += 1

        source_path = _path(row.get("source_path"), root, f"{label}.source_path")
        sources_by_model[target_model_id].add(source_path)
        prompt_path = _path(row.get("prompt_path"), root, f"{label}.prompt_path")
        run_path = _path(row.get("run_path"), root, f"{label}.run_path")
        video_path = _path(row.get("video_path"), root, f"{label}.video_path")
        for key, value in (
            ("prompt_path", prompt_path),
            ("run_path", run_path),
            ("video_path", video_path),
        ):
            if value in path_sets[key]:
                raise CombinedManifestError(f"duplicate native {key}: {value}")
            path_sets[key].add(value)

        status = _string(row.get("status"), f"{label}.status")
        article_slug = row.get("article_slug")
        if article_slug is None:
            parts = Path(source_path).parts
            article_slug = parts[2] if len(parts) >= 4 else None
        article_slug = _string(article_slug, f"{label}.article_slug")

        outputs.append(
            {
                "output_id": lite_run_id,
                "route": NATIVE_ROUTE,
                "sample_id": row.get("sample_id"),
                "article_slug": article_slug,
                "source_path": source_path,
                "target_model_id": target_model_id,
                "prompt_source_model_id": target_model_id,
                "prompt_source": {
                    "kind": "clipmaker-lite-run",
                    "lite_run_id": lite_run_id,
                },
                "attested_lite_model": True,
                "status": status,
                "prompt_path": prompt_path,
                "run_path": run_path,
                "video_path": video_path,
                "media": row.get("media"),
                "contract_check": row.get("contract_check"),
                "error": row.get("error"),
            }
        )

    expected_model_counts = {model: 5 for model in NATIVE_MODELS}
    if dict(model_counts) != expected_model_counts:
        raise CombinedManifestError(
            "native manifest must contain five outputs for each Lite model"
        )
    if sources_by_model[NATIVE_MODELS[0]] != sources_by_model[NATIVE_MODELS[1]]:
        raise CombinedManifestError(
            "native Lite models do not cover the same five source images"
        )
    return outputs


def _control_contract(job: dict[str, Any], run: dict[str, Any]) -> dict[str, Any] | None:
    if run["status"] != CONTROL_COMPLETE_STATUS:
        return None
    return {
        "requested": job["runtime"],
        "checks": {"wan_streamlit_run_verified": True},
        "conforms": True,
        "warnings": [],
    }


def _control_outputs(
    root: Path,
    plan: Any,
    native_outputs: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    control = _mapping(plan, "Wan 2.2 control plan")
    assert_sanitized_metadata(control, "Wan 2.2 control plan")
    expected_plan = {
        "schema_version": SCHEMA_VERSION,
        "target_model_id": CONTROL_MODEL,
        "prompt_source_model_id": CONTROL_PROMPT_SOURCE_MODEL,
        "provider_route": "wan-streamlit",
        "attested_lite_model": False,
        "job_count": EXPECTED_CONTROL_OUTPUTS,
    }
    for key, expected in expected_plan.items():
        if control.get(key) != expected:
            raise CombinedManifestError(f"control plan has invalid {key}")
    runtime = _mapping(control.get("runtime"), "control plan.runtime")
    jobs = _list(control.get("jobs"), "control plan.jobs")
    if len(jobs) != EXPECTED_CONTROL_OUTPUTS:
        raise CombinedManifestError(
            f"control plan must contain {EXPECTED_CONTROL_OUTPUTS} jobs"
        )

    native_wan_by_source = {
        output["source_path"]: output
        for output in native_outputs
        if output["target_model_id"] == CONTROL_PROMPT_SOURCE_MODEL
    }
    outputs: list[dict[str, Any]] = []
    ids: set[str] = set()
    paths_by_kind: dict[str, set[str]] = {
        "prompt": set(),
        "run": set(),
        "video": set(),
    }

    for index, raw_job in enumerate(jobs):
        label = f"control plan.jobs[{index}]"
        job = _mapping(raw_job, label)
        job_id = _string(job.get("job_id"), f"{label}.job_id")
        if job_id in ids:
            raise CombinedManifestError(f"duplicate control job_id: {job_id}")
        ids.add(job_id)
        for key, expected in (
            ("target_model_id", CONTROL_MODEL),
            ("prompt_source_model_id", CONTROL_PROMPT_SOURCE_MODEL),
            ("provider_route", "wan-streamlit"),
            ("attested_lite_model", False),
        ):
            if job.get(key) != expected:
                raise CombinedManifestError(f"{label} has invalid {key}")
        if job.get("runtime") != runtime:
            raise CombinedManifestError(f"{label} runtime differs from the control plan")

        source = _mapping(job.get("source_image"), f"{label}.source_image")
        source_path = _path(source.get("path"), root, f"{label}.source_image.path")
        native_source = native_wan_by_source.get(source_path)
        if native_source is None:
            raise CombinedManifestError(
                f"control source has no matching native Wan 2.7 output: {source_path}"
            )

        artifacts = _mapping(job.get("artifacts"), f"{label}.artifacts")
        paths = {
            kind: _path(artifacts.get(kind), root, f"{label}.artifacts.{kind}")
            for kind in ("prompt", "run", "video")
        }
        for kind, value in paths.items():
            if value in paths_by_kind[kind]:
                raise CombinedManifestError(f"duplicate control {kind} path: {value}")
            paths_by_kind[kind].add(value)

        prompt_source = _mapping(job.get("prompt_source"), f"{label}.prompt_source")
        if prompt_source.get("result_job_id") != native_source["output_id"]:
            raise CombinedManifestError(
                f"control prompt source does not match native Wan 2.7 run: {job_id}"
            )

        run_path = root / paths["run"]
        run = _mapping(read_json(run_path, f"{job_id} run metadata"), "run metadata")
        assert_sanitized_metadata(run, f"{job_id} run metadata")
        for key, expected in (
            ("schema_version", SCHEMA_VERSION),
            ("job_id", job_id),
            ("target_model_id", CONTROL_MODEL),
            ("prompt_source_model_id", CONTROL_PROMPT_SOURCE_MODEL),
            ("provider_route", "wan-streamlit"),
            ("attested_lite_model", False),
            ("runtime", runtime),
        ):
            if run.get(key) != expected:
                raise CombinedManifestError(
                    f"control run metadata has invalid {key}: {job_id}"
                )
        status = _string(run.get("status"), f"{job_id}.status")
        outputs.append(
            {
                "output_id": job_id,
                "route": CONTROL_ROUTE,
                "sample_id": native_source.get("sample_id"),
                "article_slug": native_source["article_slug"],
                "source_path": source_path,
                "target_model_id": CONTROL_MODEL,
                "prompt_source_model_id": CONTROL_PROMPT_SOURCE_MODEL,
                "prompt_source": prompt_source,
                "attested_lite_model": False,
                "status": status,
                "prompt_path": paths["prompt"],
                "run_path": paths["run"],
                "video_path": paths["video"],
                "media": run.get("media"),
                "contract_check": _control_contract(job, run),
                "error": run.get("error"),
            }
        )
    return outputs


def _is_complete(output: dict[str, Any]) -> bool:
    expected = (
        NATIVE_COMPLETE_STATUS
        if output["route"] == NATIVE_ROUTE
        else CONTROL_COMPLETE_STATUS
    )
    return output["status"] == expected


def _group_summary(outputs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(outputs)
    statuses = Counter(output["status"] for output in materialized)
    completed = sum(_is_complete(output) for output in materialized)
    return {
        "total": len(materialized),
        "completed": completed,
        "incomplete": len(materialized) - completed,
        "by_status": dict(sorted(statuses.items())),
    }


def _summary(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    by_route = {
        route: _group_summary(output for output in outputs if output["route"] == route)
        for route in (NATIVE_ROUTE, CONTROL_ROUTE)
    }
    by_model = {
        model: _group_summary(
            output for output in outputs if output["target_model_id"] == model
        )
        for model in (*NATIVE_MODELS, CONTROL_MODEL)
    }
    return {
        **_group_summary(outputs),
        "by_route": by_route,
        "by_model": by_model,
    }


def compose_manifest(
    root: Path,
    native_manifest_path: Path,
    control_plan_path: Path,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    native_path = _rooted(root, native_manifest_path)
    control_path = _rooted(root, control_plan_path)
    native_outputs = _native_outputs(
        root, read_json(native_path, "native generation manifest")
    )
    control_outputs = _control_outputs(
        root,
        read_json(control_path, "Wan 2.2 control plan"),
        native_outputs,
    )
    outputs = native_outputs + control_outputs
    if len(outputs) != EXPECTED_OUTPUTS:
        raise CombinedManifestError(
            f"combined manifest must contain {EXPECTED_OUTPUTS} outputs"
        )
    all_paths = [
        output[key]
        for output in outputs
        for key in ("prompt_path", "run_path", "video_path")
    ]
    if len(all_paths) != len(set(all_paths)):
        raise CombinedManifestError("combined outputs reuse an artifact path")

    summary = _summary(outputs)
    if any(output["status"] in FAILURE_STATUSES for output in outputs):
        status = "failed"
    elif summary["completed"] == EXPECTED_OUTPUTS:
        status = "complete"
    else:
        status = "incomplete"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "ticket": TICKET,
        "manifest_kind": "combined-generation",
        "updated_at": updated_at or utc_now(),
        "status": status,
        "sources": {
            "native_manifest": workspace_relative(
                root, native_path, "native generation manifest"
            ),
            "wan_2_2_control_plan": workspace_relative(
                root, control_path, "Wan 2.2 control plan"
            ),
        },
        "expected_outputs": EXPECTED_OUTPUTS,
        "summary": summary,
        "outputs": outputs,
    }
    assert_sanitized_metadata(manifest, "combined manifest")
    return manifest


def build_combined_manifest(
    root: Path,
    native_manifest_path: Path = DEFAULT_NATIVE_MANIFEST,
    control_plan_path: Path = DEFAULT_CONTROL_PLAN,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    root = root.resolve()
    destination = _rooted(root, output_path)
    workspace_relative(root, destination, "combined manifest")
    manifest = compose_manifest(root, native_manifest_path, control_plan_path)
    atomic_write_json(destination, manifest)
    return manifest


def verify_combined_manifest(
    root: Path,
    native_manifest_path: Path = DEFAULT_NATIVE_MANIFEST,
    control_plan_path: Path = DEFAULT_CONTROL_PLAN,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    destination = _rooted(root, output_path)
    actual = _mapping(
        read_json(destination, "combined generation manifest"),
        "combined generation manifest",
    )
    assert_sanitized_metadata(actual, "combined generation manifest")
    updated_at = _string(actual.get("updated_at"), "combined manifest.updated_at")
    expected = compose_manifest(
        root,
        native_manifest_path,
        control_plan_path,
        updated_at=updated_at,
    )
    if actual != expected:
        raise CombinedManifestError(
            "combined manifest is stale or differs from its source metadata"
        )

    if allow_incomplete:
        return actual
    if actual.get("status") != "complete":
        raise CombinedManifestError(
            f"combined manifest is {actual.get('status')!r}; expected 15 complete outputs"
        )
    for output in actual["outputs"]:
        output_id = output["output_id"]
        if not _is_complete(output):
            raise CombinedManifestError(f"output is not complete: {output_id}")
        media = output.get("media")
        if not isinstance(media, dict) or not media:
            raise CombinedManifestError(f"output has no verified media metadata: {output_id}")
        contract = output.get("contract_check")
        if not isinstance(contract, dict) or contract.get("conforms") is not True:
            raise CombinedManifestError(f"output contract does not conform: {output_id}")
        for key in ("prompt_path", "run_path", "video_path"):
            artifact = resolve_workspace_path(root, output[key], f"{output_id}.{key}")
            if not artifact.is_file() or artifact.is_symlink():
                raise CombinedManifestError(
                    f"complete output has no regular {key}: {output_id}"
                )
    return actual


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    parser.add_argument("--native-manifest", type=Path, default=DEFAULT_NATIVE_MANIFEST)
    parser.add_argument("--control-plan", type=Path, default=DEFAULT_CONTROL_PLAN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="build the 15-output manifest, allowing pending jobs")
    verify = subparsers.add_parser("verify", help="verify the canonical combined manifest")
    verify.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="verify structure and freshness without requiring all 15 outputs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.workspace.resolve()
    try:
        if args.command == "build":
            manifest = build_combined_manifest(
                root, args.native_manifest, args.control_plan, args.output
            )
            print(
                f"PASS: built {manifest['expected_outputs']}-output combined manifest "
                f"({manifest['status']})"
            )
        elif args.command == "verify":
            manifest = verify_combined_manifest(
                root,
                args.native_manifest,
                args.control_plan,
                args.output,
                allow_incomplete=args.allow_incomplete,
            )
            qualifier = " (incomplete allowed)" if args.allow_incomplete else ""
            print(
                f"PASS: verified {manifest['expected_outputs']}-output combined manifest"
                f"{qualifier}"
            )
        else:  # pragma: no cover - argparse enforces the command set.
            raise CombinedManifestError(f"unsupported command: {args.command}")
    except CombinedManifestError as exc:
        print(f"error: {safe_error(exc)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
