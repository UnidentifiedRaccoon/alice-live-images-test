#!/usr/bin/env python3
"""Build and upload the selected two-publication live-images video package.

Only ``final-selection.json`` may select source videos.  Object keys are
content-addressed and publication-scoped.  Upload is idempotent: an exact
existing object is skipped, while any metadata/content mismatch is a hard
collision and is never overwritten.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import promopages_10060_s3_export as transport  # noqa: E402
from scripts import clipmaker_lite_batch_pipeline as native  # noqa: E402


BATCH_ID = "promopages-live-images-20260813-v1"
PACKAGE_ID = "promopages-live-images-20260813-v1-s3"
DEFAULT_FINAL_MANIFEST = (
    ROOT / "clipmaker-lite-test/runs" / BATCH_ID / "final-selection.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "PROMOPAGES-live-images-20260813-v1/s3-export/output"
BUCKET = "promopages-front-bundles"
OBJECT_PREFIX = "front-images/exp_video/"
PUBLIC_BASE_URL = "https://yastatic.net/s3/promopages-front-bundles/"
CONTENT_TYPE = "video/mp4"
CACHE_CONTROL = "public,max-age=31536000,immutable"
MODEL_DIRS = {
    "alibaba/wan-2.2": "wan_2_2",
    "alibaba/wan-2.7": "wan_2_7",
    "google/veo-3.1-lite": "veo_3_1",
}
MODEL_IDS = tuple(MODEL_DIRS)

ARTICLE_ROUTES = {
    "01-level-ipoteka-2026": {
        "article_number": "01",
        "cabinet_name": "Level Group",
        "cabinet_slug": "level-group",
        "cabinet_id": "69ee06293ba10e0ae4b765d1",
        "publication_id": "6a048ddca495b52c9d873940",
        "image_id": "04",
        "media_id": "6a049156a495b52c9d87cb75",
    },
    "02-banki-vygodno-kupit-dollar": {
        "article_number": "02",
        "cabinet_name": "Банки.ру",
        "cabinet_slug": "banki-ru",
        "cabinet_id": "5b0fb7c448c85e2421e049ab",
        "publication_id": "6a4f5fe924801975680d9be5",
        "image_id": "01",
        "media_id": "6a4f718952e3ce75a3110deb",
    },
}


class ExportError(RuntimeError):
    """Fail-closed S3 package/export error."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExportError(f"Expected a JSON object in {path}")
    return value


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(_json_text(dict(value)), encoding="utf-8")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    _write_json(temporary, value)
    os.replace(temporary, path)


def _hash_file(path: Path) -> tuple[str, str, int]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)  # nosec B324: S3 Content-MD5
    size = 0
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                size += len(chunk)
                sha256.update(chunk)
                md5.update(chunk)
    except OSError as exc:
        raise ExportError(f"Cannot hash {path}: {exc}") from exc
    return (
        sha256.hexdigest(),
        base64.b64encode(md5.digest()).decode("ascii"),
        size,
    )


def _safe_root_file(root: Path, value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ExportError(f"Unsafe selected video path: {value!r}")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise ExportError(f"Selected video is missing or escapes root: {value}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise ExportError(f"Selected video must be a regular non-symlink file: {value}")
    return resolved


def _safe_relative(value: str) -> PurePosixPath:
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
        or any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in pure.parts)
    ):
        raise ExportError(f"Unsafe package-relative path: {value!r}")
    return pure


def _public_url(object_key: str) -> str:
    return PUBLIC_BASE_URL + object_key


def _validate_final_manifest(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    producer = value.get("producer")
    outputs = value.get("outputs")
    if (
        value.get("schema_version") != 1
        or value.get("manifest_role") != "clipmaker-lite-final-selection"
        or value.get("batch_id") != BATCH_ID
        or producer
        != {
            "agent_id": "clipmaker-lite",
            "contract_version": "2.1.4",
            "runner_version": 8,
        }
        or value.get("models") != list(MODEL_IDS)
        or value.get("article_count") != 2
        or value.get("image_count") != 2
        or value.get("expected_outputs") != 6
        or not isinstance(outputs, list)
        or len(outputs) != 6
    ):
        raise ExportError("Unexpected final-selection manifest identity")

    expected = {
        (slug, route["image_id"], model_id)
        for slug, route in ARTICLE_ROUTES.items()
        for model_id in MODEL_IDS
    }
    seen: set[tuple[str, str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for raw in outputs:
        if not isinstance(raw, dict):
            raise ExportError("Final-selection output is not an object")
        row = dict(raw)
        key = (
            str(row.get("article_slug")),
            str(row.get("image_id")),
            str(row.get("model_id")),
        )
        if key not in expected or key in seen:
            raise ExportError(f"Unexpected or duplicate logical output: {key}")
        seen.add(key)
        route = ARTICLE_ROUTES[key[0]]
        if (
            row.get("article_number") != route["article_number"]
            or row.get("publication_id") != route["publication_id"]
            or row.get("media_id") != route["media_id"]
        ):
            raise ExportError(f"Final selection route differs: {key}")
        status = row.get("status")
        if status == "succeeded":
            if (
                not isinstance(row.get("video_path"), str)
                or not isinstance(row.get("media"), dict)
                or not isinstance(row.get("contract_check"), dict)
                or not isinstance(row.get("media_acceptance"), dict)
                or not native.validate_media_acceptance(
                    row["model_id"],
                    row["media"],
                    row["contract_check"],
                    row["media_acceptance"],
                )
                or row.get("selected_attempt_id") is None
                or row.get("error") is not None
            ):
                raise ExportError(f"Succeeded selection is incomplete: {key}")
        elif status == "unavailable":
            if any(
                row.get(field) is not None
                for field in (
                    "video_path",
                    "media",
                    "contract_check",
                    "media_acceptance",
                    "selected_attempt_id",
                    "recorded_status",
                )
            ) or not isinstance(row.get("error"), str) or not row["error"].strip():
                raise ExportError(f"Unavailable selection has upload data: {key}")
        else:
            raise ExportError(f"Unsupported final selection status: {key}/{status!r}")
        normalized.append(row)
    if seen != expected:
        raise ExportError(f"Final selection coverage differs: missing={sorted(expected - seen)}")
    normalized.sort(
        key=lambda row: (
            int(row["article_number"]),
            int(row["image_id"]),
            MODEL_IDS.index(row["model_id"]),
        )
    )
    return normalized


def _csv_text(fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> str:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


LINK_FIELDS = (
    "article_slug",
    "publication_id",
    "image_id",
    "model_id",
    "experiment",
    "bytes",
    "sha256",
    "object_key",
    "yastatic_url",
)


def _links_csv(outputs: Sequence[Mapping[str, Any]]) -> str:
    return _csv_text(
        LINK_FIELDS,
        (
            {
                "article_slug": row["article_slug"],
                "publication_id": row["publication_id"],
                "image_id": row["image_id"],
                "model_id": row["model_id"],
                "experiment": row["experiment"],
                "bytes": row["media"]["bytes"],
                "sha256": row["media"]["sha256"],
                "object_key": row["object_key"],
                "yastatic_url": row["yastatic_url"],
            }
            for row in outputs
            if row["package_status"] == "ready"
        ),
    )


def _sha256sums(outputs: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        f"{row['media']['sha256']}  upload/{row['relative_path']}\n"
        for row in outputs
        if row["package_status"] == "ready"
    )


def _safe_replace(staging: Path, output_dir: Path) -> None:
    output = output_dir.resolve(strict=False)
    root = ROOT.resolve()
    if output in {Path("/").resolve(), root} or output == output.parent:
        raise ExportError(f"Refusing unsafe output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if output.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent))
        backup.rmdir()
        output.rename(backup)
    try:
        staging.rename(output)
    except BaseException:
        if backup is not None and not output.exists():
            backup.rename(output)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def build_export(
    root: Path,
    final_manifest_path: Path,
    output_dir: Path,
    *,
    materialize_mode: str = "auto",
) -> dict[str, Any]:
    """Materialize a deterministic local upload package."""

    root = root.resolve(strict=True)
    if not final_manifest_path.is_absolute():
        final_manifest_path = root / final_manifest_path
    final_manifest_path = final_manifest_path.resolve(strict=True)
    value = _read_json(final_manifest_path)
    selected = _validate_final_manifest(value)
    output_dir = output_dir.resolve(strict=False)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    package_outputs: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    try:
        for row in selected:
            route = ARTICLE_ROUTES[row["article_slug"]]
            base = {
                "package_status": "ready" if row["status"] == "succeeded" else "unavailable",
                "article_number": route["article_number"],
                "article_slug": row["article_slug"],
                "cabinet": {
                    "name": route["cabinet_name"],
                    "slug": route["cabinet_slug"],
                    "id": route["cabinet_id"],
                },
                "publication_id": route["publication_id"],
                "image_id": route["image_id"],
                "media_id": route["media_id"],
                "model_id": row["model_id"],
                "experiment": MODEL_DIRS[row["model_id"]],
                "recorded_status": row.get("recorded_status"),
                "selected_attempt_id": row["selected_attempt_id"],
                "provider_run_id": row.get("provider_run_id"),
                "source_video_path": row.get("video_path"),
                "relative_path": None,
                "object_key": None,
                "yastatic_url": None,
                "media": None,
                "contract_check": row.get("contract_check"),
                "media_acceptance": row.get("media_acceptance"),
                "error": row.get("error"),
            }
            if row["status"] == "succeeded":
                source = _safe_root_file(root, row["video_path"])
                sha256, md5_base64, size = _hash_file(source)
                recorded = row["media"]
                if recorded.get("sha256") != sha256 or recorded.get("bytes") != size:
                    raise ExportError(f"Selected video bytes differ: {row['video_path']}")
                relative = PurePosixPath(
                    f"{route['cabinet_slug']}__{route['cabinet_id']}",
                    route["publication_id"],
                    MODEL_DIRS[row["model_id"]],
                    f"image_{route['image_id']}--sha256-{sha256[:12]}.mp4",
                ).as_posix()
                object_key = OBJECT_PREFIX + relative
                if object_key in seen_keys:
                    raise ExportError(f"Duplicate object key: {object_key}")
                seen_keys.add(object_key)
                destination = staging / "upload" / Path(*PurePosixPath(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if materialize_mode == "copy":
                    shutil.copy2(source, destination)
                elif materialize_mode in {"auto", "hardlink"}:
                    try:
                        os.link(source, destination)
                    except OSError:
                        if materialize_mode == "hardlink":
                            raise
                        shutil.copy2(source, destination)
                else:
                    raise ExportError(f"Unknown materialization mode: {materialize_mode}")
                base.update(
                    {
                        "relative_path": relative,
                        "object_key": object_key,
                        "yastatic_url": _public_url(object_key),
                        "media": {**recorded, "sha256": sha256, "md5_base64": md5_base64, "bytes": size},
                    }
                )
            package_outputs.append(base)

        ready = [row for row in package_outputs if row["package_status"] == "ready"]
        manifest = {
            "schema_version": "promopages-live-images-s3-package/v1",
            "package_id": PACKAGE_ID,
            "batch_id": BATCH_ID,
            "bucket": BUCKET,
            "object_prefix": OBJECT_PREFIX,
            "public_base_url": PUBLIC_BASE_URL,
            "content_type": CONTENT_TYPE,
            "cache_control": CACHE_CONTROL,
            "model_directory_map": MODEL_DIRS,
            "source_final_manifest": {
                "path": final_manifest_path.resolve().relative_to(root).as_posix(),
                "sha256": _hash_file(final_manifest_path)[0],
            },
            "counts": {
                "logical_outputs": len(package_outputs),
                "ready_outputs": len(ready),
                "unavailable_outputs": len(package_outputs) - len(ready),
                "bytes": sum(row["media"]["bytes"] for row in ready),
            },
            "outputs": package_outputs,
        }
        _write_json(staging / "manifest.json", manifest)
        (staging / "links.csv").write_text(_links_csv(package_outputs), encoding="utf-8")
        (staging / "SHA256SUMS").write_text(_sha256sums(package_outputs), encoding="utf-8")
        _safe_replace(staging, output_dir)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def verify_export(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve(strict=True)
    manifest = _read_json(output_dir / "manifest.json")
    if (
        manifest.get("schema_version") != "promopages-live-images-s3-package/v1"
        or manifest.get("package_id") != PACKAGE_ID
        or manifest.get("batch_id") != BATCH_ID
        or manifest.get("bucket") != BUCKET
        or manifest.get("object_prefix") != OBJECT_PREFIX
        or manifest.get("model_directory_map") != MODEL_DIRS
    ):
        raise ExportError("Unexpected local S3 package identity")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != 6:
        raise ExportError("Local package must describe exactly six logical outputs")
    expected_files: set[str] = set()
    ready_count = 0
    unavailable_count = 0
    total_bytes = 0
    for row in outputs:
        if row.get("package_status") == "unavailable":
            unavailable_count += 1
            if any(row.get(key) is not None for key in ("relative_path", "object_key", "yastatic_url", "media")):
                raise ExportError("Unavailable package output contains upload fields")
            continue
        if row.get("package_status") != "ready":
            raise ExportError("Unsupported package output status")
        ready_count += 1
        if not native.validate_media_acceptance(
            str(row.get("model_id")),
            row.get("media"),
            row.get("contract_check"),
            row.get("media_acceptance"),
        ):
            raise ExportError("Ready package output has invalid media acceptance")
        relative = _safe_relative(str(row.get("relative_path")))
        object_key = OBJECT_PREFIX + relative.as_posix()
        if row.get("object_key") != object_key or row.get("yastatic_url") != _public_url(object_key):
            raise ExportError(f"Package object route mismatch: {object_key}")
        package_path = output_dir / "upload" / Path(*relative.parts)
        if package_path.is_symlink() or not package_path.is_file():
            raise ExportError(f"Missing regular package video: {relative}")
        sha256, md5_base64, size = _hash_file(package_path)
        media = row.get("media")
        if not isinstance(media, dict) or (
            media.get("sha256"), media.get("md5_base64"), media.get("bytes")
        ) != (sha256, md5_base64, size):
            raise ExportError(f"Package video digest differs: {relative}")
        total_bytes += size
        expected_files.add((PurePosixPath("upload") / relative).as_posix())
    actual_files = {
        path.relative_to(output_dir).as_posix()
        for path in (output_dir / "upload").rglob("*")
        if path.is_file()
    } if (output_dir / "upload").exists() else set()
    if actual_files != expected_files:
        raise ExportError(
            f"Upload tree differs: missing={sorted(expected_files - actual_files)}, "
            f"extras={sorted(actual_files - expected_files)}"
        )
    counts = manifest.get("counts")
    if counts != {
        "logical_outputs": 6,
        "ready_outputs": ready_count,
        "unavailable_outputs": unavailable_count,
        "bytes": total_bytes,
    }:
        raise ExportError("Package counts are stale")
    if (output_dir / "links.csv").read_text(encoding="utf-8") != _links_csv(outputs):
        raise ExportError("links.csv is stale")
    if (output_dir / "SHA256SUMS").read_text(encoding="utf-8") != _sha256sums(outputs):
        raise ExportError("SHA256SUMS is stale")
    return {"verified": True, "counts": counts}


def _delivery_manifest(ready: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_role": "promopages-live-images-s3-delivery",
        "batch_id": BATCH_ID,
        "bucket": BUCKET,
        "object_prefix": OBJECT_PREFIX,
        "verified_output_count": len(ready),
        "outputs": [
            {
                "article_slug": row["article_slug"],
                "publication_id": row["publication_id"],
                "image_id": row["image_id"],
                "media_id": row["media_id"],
                "model_id": row["model_id"],
                "recorded_status": row["recorded_status"],
                "selected_attempt_id": row["selected_attempt_id"],
                "provider_run_id": row["provider_run_id"],
                "sha256": row["media"]["sha256"],
                "bytes": row["media"]["bytes"],
                "media_acceptance": row["media_acceptance"],
                "object_key": row["object_key"],
                "yastatic_url": row["yastatic_url"],
            }
            for row in ready
        ],
    }


def upload_export(
    output_dir: Path,
    *,
    execute: bool,
    yc_profile: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    verify_cdn: Callable[[Mapping[str, Any]], dict[str, Any]] = transport._verify_yastatic,
) -> dict[str, Any]:
    """Plan or perform the idempotent head/put/verify sequence."""

    local = verify_export(output_dir)
    output_dir = output_dir.resolve(strict=True)
    manifest = _read_json(output_dir / "manifest.json")
    ready = [row for row in manifest["outputs"] if row["package_status"] == "ready"]
    operations = [
        {
            "operation": "head-then-put-if-missing",
            "object_key": row["object_key"],
            "sha256": row["media"]["sha256"],
            "bytes": row["media"]["bytes"],
            "yastatic_url": row["yastatic_url"],
        }
        for row in ready
    ]
    if not execute:
        return {
            "mode": "dry-run",
            "external_writes": 0,
            "local_verification": local,
            "operation_count": len(operations),
            "operations": operations,
        }
    if not yc_profile:
        raise ExportError("--yc-profile is required with --execute")

    delivery_path = output_dir / "delivery-manifest.json"
    if delivery_path.exists():
        delivery_path.unlink()

    preflight = [
        "yc",
        "storage",
        "s3api",
        "list-objects-v2",
        "--profile",
        yc_profile,
        "--format",
        "json",
        "--bucket",
        BUCKET,
        "--prefix",
        OBJECT_PREFIX,
        "--max-keys",
        "1",
    ]
    transport._json_from_process(transport._run_yc(preflight, runner), "S3 access preflight")
    report: dict[str, Any] = {
        "schema_version": "promopages-live-images-upload-report/v1",
        "package_id": PACKAGE_ID,
        "batch_id": BATCH_ID,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "counts": {"total": len(ready), "uploaded": 0, "skipped": 0, "verified": 0},
        "objects": [],
    }
    report_path = output_dir / "upload-report.json"
    _atomic_write_json(report_path, report)
    for row in ready:
        item = {
            "object_key": row["object_key"],
            "yastatic_url": row["yastatic_url"],
            "action": "pending",
            "status": "pending",
            "error": None,
        }
        report["objects"].append(item)
        _atomic_write_json(report_path, report)
        try:
            head = transport._head_object(row, yc_profile, runner)
            if head is not None and not transport._head_matches(row, head):
                item["action"] = "conflict"
                item["status"] = "conflict"
                raise ExportError(
                    "Immutable object key conflict; refusing overwrite: " + row["object_key"]
                )
            if head is None:
                transport._put_object(output_dir, row, yc_profile, runner)
                item["action"] = "uploaded"
                report["counts"]["uploaded"] += 1
                head = transport._head_object(row, yc_profile, runner)
                if head is None or not transport._head_matches(row, head):
                    raise ExportError(f"S3 post-upload verification failed: {row['object_key']}")
            else:
                item["action"] = "skipped"
                report["counts"]["skipped"] += 1
            item["cdn"] = verify_cdn(row)
            item["status"] = "verified"
            report["counts"]["verified"] += 1
            _atomic_write_json(report_path, report)
        except (ExportError, transport.ExportError, OSError, ValueError) as exc:
            item["error"] = str(exc)
            if item["status"] != "conflict":
                item["status"] = "failed"
            _atomic_write_json(report_path, report)
            raise ExportError(str(exc)) from exc
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(report_path, report)
    if report["counts"]["verified"] != len(ready):
        raise ExportError("Refusing a partial S3 delivery manifest")
    _atomic_write_json(delivery_path, _delivery_manifest(ready))
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--root", type=Path, default=ROOT)
    build.add_argument("--final-manifest", type=Path, default=DEFAULT_FINAL_MANIFEST)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    build.add_argument("--materialize", choices=("auto", "hardlink", "copy"), default="auto")
    verify = commands.add_parser("verify")
    verify.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    upload = commands.add_parser("upload")
    upload.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    upload.add_argument("--yc-profile", default="promopages-internal")
    upload.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_export(
                args.root,
                args.final_manifest,
                args.output,
                materialize_mode=args.materialize,
            )
            print(f"PASS: built {result['counts']['ready_outputs']} upload object(s)")
            return 0
        if args.command == "verify":
            result = verify_export(args.output)
            print(f"PASS: verified {result['counts']['ready_outputs']} upload object(s)")
            return 0
        if args.command == "upload":
            result = upload_export(
                args.output,
                execute=args.execute,
                yc_profile=args.yc_profile,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        raise ExportError(f"Unknown command: {args.command}")
    except (ExportError, transport.ExportError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
