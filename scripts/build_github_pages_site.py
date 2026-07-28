#!/usr/bin/env python3
"""Build the exact static payload published from the gh-pages branch.

The repository is larger than the GitHub Pages 1 GB published-site limit.  This
builder follows only runtime references used by the five demo screens and
copies those files into an isolated directory while preserving their paths.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
MAX_SITE_BYTES = 950_000_000
MAX_FILE_BYTES = 100_000_000

STATIC_FILES = (
    ".nojekyll",
    "index.html",
    "styles.css",
    "app.js",
    "shared.css",
    "generated-gallery.html",
    "generated-gallery.css",
    "generated-gallery-data.js",
    "generated-gallery.js",
    "model-comparison-5s/index.html",
    "model-comparison-5s/styles.css",
    "model-comparison-5s/comparison-data.js",
    "model-comparison-5s/app.js",
    "model-comparison-5s/favicon.svg",
    "manual-review/index.html",
    "manual-review/styles.css",
    "manual-review/review-core.js",
    "manual-review/review-data.js",
    "manual-review/app.js",
    "clipmaker-lite/index.html",
    "clipmaker-lite/styles.css",
    "clipmaker-lite/app.js",
    "clipmaker-lite-test/manifest.json",
    "clipmaker-lite-test/promopages-9930-manifest.json",
    "clipmaker-lite-test/case-21-manifest.json",
)

STATIC_TREES = (
    "videos",
    "webp",
    "model-comparison-5s/fonts",
    "model-comparison-5s/input",
    "model-comparison-5s/final",
)


def _safe_relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected a non-empty relative path, got {value!r}")

    posix_path = PurePosixPath(value)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise ValueError(f"Unsafe site path: {value!r}")
    if any(part in {"", "."} for part in posix_path.parts):
        raise ValueError(f"Non-canonical site path: {value!r}")

    return Path(*posix_path.parts)


def _load_js_assignment(path: Path, variable: str) -> Any:
    text = path.read_text(encoding="utf-8").strip()
    prefix = f"window.{variable} = "
    if not text.startswith(prefix) or not text.endswith(";"):
        raise ValueError(f"Unexpected JavaScript assignment format: {path}")
    return json.loads(text[len(prefix) : -1])


def _tree_files(root: Path, relative_tree: str) -> Iterable[Path]:
    tree = root / _safe_relative_path(relative_tree)
    if not tree.is_dir():
        raise FileNotFoundError(tree)
    for path in tree.rglob("*"):
        if path.is_file():
            yield path.relative_to(root)


def collect_site_paths(root: Path = ROOT) -> tuple[Path, ...]:
    root = root.resolve()
    relative_paths = {_safe_relative_path(path) for path in STATIC_FILES}

    for tree in STATIC_TREES:
        relative_paths.update(_tree_files(root, tree))

    gallery = _load_js_assignment(
        root / "generated-gallery-data.js", "generatedGalleryData"
    )
    for item in gallery:
        for field in ("sourceImage", "video", "webp"):
            value = item[field]
            if value:
                relative_paths.add(_safe_relative_path(value))

    review = _load_js_assignment(
        root / "manual-review" / "review-data.js", "qualityReviewDataset"
    )
    for item in review["items"]:
        relative_paths.add(_safe_relative_path(item["video"]["path"]))

    remote_repository_paths: set[Path] = set()

    lite_manifest = json.loads(
        (root / "clipmaker-lite-test" / "manifest.json").read_text(encoding="utf-8")
    )
    for article in lite_manifest["articles"]:
        relative_paths.add(
            _safe_relative_path(article["selected_image"]["source_path"])
        )
        outputs = [
            *article["outputs"],
            *article.get("comparison_outputs", []),
        ]
        for output in outputs:
            relative_paths.add(_safe_relative_path(output["video_path"]))
        for output in article.get("external_outputs", []):
            relative_path = _safe_relative_path(output["video_path"])
            if output.get("delivery") == "repository-raw":
                remote_repository_paths.add(relative_path)
            else:
                relative_paths.add(relative_path)

    # The Step 5 client uses stable raw-repository URLs for PROMOPAGES-9930 media.
    # Keep the compact manifest in Pages and validate every referenced repository
    # artifact without copying the extension media into the Pages payload.
    additional_lite_manifest = json.loads(
        (root / "clipmaker-lite-test" / "promopages-9930-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for article in additional_lite_manifest["articles"]:
        for image_record in article["images"]:
            remote_repository_paths.add(
                _safe_relative_path(image_record["image"]["source_path"])
            )
            for output in image_record["outputs"]:
                remote_repository_paths.add(_safe_relative_path(output["video_path"]))

    # Case 21 is an independent one-image sidecar. Its compact JSON is part of
    # the Pages payload, while the source, seven historical videos and every
    # available loop/smooth experiment outputs stay on main and are delivered
    # through raw.githubusercontent.com.
    case_21_manifest = json.loads(
        (root / "clipmaker-lite-test" / "case-21-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for article in case_21_manifest["articles"]:
        for image_record in article["images"]:
            image = image_record["image"]
            if image.get("delivery") != "repository-raw":
                raise ValueError(
                    "Case 21 source image must use repository-raw delivery"
                )
            remote_repository_paths.add(_safe_relative_path(image["source_path"]))
            outputs = [
                *image_record["outputs"],
                *image_record.get("research_outputs", []),
            ]
            for output in outputs:
                if output.get("delivery") != "repository-raw":
                    raise ValueError(
                        "Case 21 outputs must use repository-raw delivery"
                    )
                remote_repository_paths.add(
                    _safe_relative_path(output["video_path"])
                )

    loop_experiment = case_21_manifest.get("loop_experiment")
    if loop_experiment is not None:
        if not isinstance(loop_experiment, dict) or not isinstance(
            loop_experiment.get("outputs"), list
        ):
            raise ValueError("Case 21 loop_experiment must contain an outputs list")
        for output in loop_experiment["outputs"]:
            if not isinstance(output, dict) or output.get("delivery") != "repository-raw":
                raise ValueError(
                    "Case 21 loop outputs must use repository-raw delivery"
                )
            remote_repository_paths.add(
                _safe_relative_path(output.get("video_path"))
            )

    smooth_experiment = case_21_manifest.get("smooth_experiment")
    if smooth_experiment is not None:
        if not isinstance(smooth_experiment, dict) or not isinstance(
            smooth_experiment.get("outputs"), list
        ):
            raise ValueError("Case 21 smooth_experiment must contain an outputs list")
        for output in smooth_experiment["outputs"]:
            if not isinstance(output, dict) or output.get("delivery") != "repository-raw":
                raise ValueError(
                    "Case 21 smooth outputs must use repository-raw delivery"
                )
            remote_repository_paths.add(
                _safe_relative_path(output.get("video_path"))
            )

    for relative_path in remote_repository_paths:
        source = root / relative_path
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(
                f"Missing regular raw-repository media file: {relative_path}"
            )
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(
                f"Raw-repository media exceeds GitHub's 100 MB file limit: {relative_path}"
            )

    for relative_path in relative_paths:
        source = root / relative_path
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(f"Missing regular site file: {relative_path}")
        if source.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(
                f"Site file exceeds GitHub's 100 MB file limit: {relative_path}"
            )

    return tuple(sorted(relative_paths, key=lambda path: path.as_posix()))


def site_size(root: Path, relative_paths: Iterable[Path]) -> int:
    return sum((root / path).stat().st_size for path in relative_paths)


def build_site(root: Path, output: Path, *, hardlink: bool = False) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    if output == root:
        raise ValueError("Output directory must not be the repository root")
    if output.exists():
        raise FileExistsError(f"Output path already exists: {output}")

    paths = collect_site_paths(root)
    total_bytes = site_size(root, paths)
    if total_bytes > MAX_SITE_BYTES:
        raise ValueError(
            f"Pages payload is {total_bytes:,} bytes; limit is {MAX_SITE_BYTES:,} bytes"
        )

    output.mkdir(parents=True)
    for relative_path in paths:
        source = root / relative_path
        destination = output / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if hardlink:
            os.link(source, destination)
        else:
            shutil.copy2(source, destination)

    return {
        "output": str(output),
        "file_count": len(paths),
        "total_bytes": total_bytes,
        "max_site_bytes": MAX_SITE_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--hardlink",
        action="store_true",
        help="Hard-link files instead of copying them (output must share a filesystem).",
    )
    args = parser.parse_args()

    result = build_site(args.root, args.output, hardlink=args.hardlink)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
