#!/usr/bin/env python3
"""Regenerate PROMOPAGES-10060 tune prompts through canonical Clipmaker Lite.

This coordinator is prompt-only. It never calls a video provider and never
uploads media to S3. Existing baseline MP4 URLs are included only as review
evidence in the Step 8 manifest.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clipmaker_lite_runner as runner  # noqa: E402


EVALUATION_PATH = Path("clipmaker-lite-test/tune-evaluation.json")
OUTPUT_MANIFEST_PATH = Path("clipmaker-lite-test/tune-manifest.json")
BATCH_ID = "promopages-10060-tune-prompts-20260811-v4"
EXPECTED_CONTRACT_VERSION = "2.2.0"
EXPECTED_CASES = 36
EXPECTED_TARGETS = 65
CANONICAL_MANIFEST_PATHS = (
    Path("clipmaker-lite-test/promopages-10060-manifest.json"),
    Path("clipmaker-lite-test/promopages-10060-article-02-20260806-v2-manifest.json"),
    Path("clipmaker-lite-test/promopages-10060-campaigns-20260805-v1-manifest.json"),
    Path("clipmaker-lite-test/promopages-10060-campaigns-20260807-v1-manifest.json"),
)
S3_DELIVERY_PATH = Path("clipmaker-lite-test/promopages-10060-s3-delivery.json")


class TunePipelineError(RuntimeError):
    """The tune batch cannot be prepared or verified safely."""


def read_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink():
        raise TunePipelineError(f"Required JSON is missing or unsafe: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TunePipelineError(f"Invalid JSON: {path}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TunePipelineError(f"{label} must be a non-empty string")
    return value.strip()


def load_evaluation(root: Path = ROOT) -> dict[str, Any]:
    evaluation = read_json(root / EVALUATION_PATH)
    if (
        not isinstance(evaluation, dict)
        or evaluation.get("schema_version") != 1
        or evaluation.get("evaluation_id") != "promopages-10060-tune-20260811-v1"
    ):
        raise TunePipelineError("Unexpected tune evaluation identity")
    cases = evaluation.get("cases")
    if not isinstance(cases, list) or len(cases) != EXPECTED_CASES:
        raise TunePipelineError(f"Tune evaluation must contain {EXPECTED_CASES} cases")
    target_count = 0
    seen_case_ids: set[str] = set()
    seen_rows: set[int] = set()
    model_counts = {model_id: 0 for model_id in runner.SUPPORTED_MODELS}
    for case in cases:
        if not isinstance(case, dict):
            raise TunePipelineError("Tune case must be an object")
        case_id = nonempty(case.get("case_id"), "case_id")
        if case_id in seen_case_ids:
            raise TunePipelineError(f"Duplicate tune case: {case_id}")
        seen_case_ids.add(case_id)
        targets = case.get("targets")
        if not isinstance(targets, list) or not targets:
            raise TunePipelineError(f"Tune case has no targets: {case_id}")
        case_models: set[str] = set()
        for target in targets:
            if not isinstance(target, dict):
                raise TunePipelineError(f"Invalid target in {case_id}")
            row = target.get("sheet_row")
            model_id = target.get("model_id")
            if not isinstance(row, int) or row in seen_rows:
                raise TunePipelineError(f"Duplicate or invalid sheet row: {row}")
            if model_id not in runner.SUPPORTED_MODELS or model_id in case_models:
                raise TunePipelineError(f"Duplicate or invalid model in {case_id}: {model_id}")
            if target.get("rating_state") not in {"blank", "regenerate"}:
                raise TunePipelineError(f"Invalid rating state at sheet row {row}")
            seen_rows.add(row)
            case_models.add(model_id)
            model_counts[model_id] += 1
            target_count += 1
    if target_count != EXPECTED_TARGETS:
        raise TunePipelineError(f"Tune evaluation must contain {EXPECTED_TARGETS} targets")
    expected_model_counts = {
        "alibaba/wan-2.2": 24,
        "alibaba/wan-2.7": 16,
        "google/veo-3.1-lite": 25,
    }
    if model_counts != expected_model_counts:
        raise TunePipelineError(f"Unexpected target model counts: {model_counts}")
    return evaluation


def canonical_dataset(
    root: Path = ROOT,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], str]]:
    articles: dict[str, dict[str, Any]] = {}
    for relative in CANONICAL_MANIFEST_PATHS:
        manifest = read_json(root / relative)
        if (
            not isinstance(manifest, dict)
            or manifest.get("ticket") != "PROMOPAGES-10060"
            or manifest.get("agent_id") != runner.AGENT_ID
        ):
            raise TunePipelineError(f"Unexpected canonical manifest: {relative}")
        for article in manifest.get("articles", []):
            if not isinstance(article, dict):
                raise TunePipelineError(f"Invalid article in {relative}")
            number = nonempty(article.get("article_number"), "article_number").zfill(2)
            if number in articles:
                raise TunePipelineError(f"Duplicate canonical article number: {number}")
            articles[number] = article
    if len(articles) != 21:
        raise TunePipelineError(f"Expected 21 canonical articles, found {len(articles)}")

    delivery = read_json(root / S3_DELIVERY_PATH)
    if (
        not isinstance(delivery, dict)
        or delivery.get("ticket") != "PROMOPAGES-10060"
        or delivery.get("verified_output_count") != 510
    ):
        raise TunePipelineError("Unexpected PROMOPAGES-10060 S3 delivery manifest")
    videos: dict[tuple[str, str, str], str] = {}
    for output in delivery.get("outputs", []):
        if not isinstance(output, dict):
            raise TunePipelineError("Invalid S3 delivery output")
        key = (
            nonempty(output.get("article_slug"), "delivery.article_slug"),
            nonempty(output.get("image_id"), "delivery.image_id"),
            nonempty(output.get("model_id"), "delivery.model_id"),
        )
        if key in videos:
            raise TunePipelineError(f"Duplicate S3 delivery output: {key}")
        videos[key] = nonempty(output.get("yastatic_url"), "delivery.yastatic_url")
    return articles, videos


def resolved_cases(
    evaluation: dict[str, Any],
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    articles, public_videos = canonical_dataset(root)
    resolved: list[dict[str, Any]] = []
    for case in evaluation["cases"]:
        article_number = nonempty(case.get("article_number"), "case.article_number").zfill(2)
        article = articles.get(article_number)
        if article is None:
            raise TunePipelineError(f"Unknown article in tune evaluation: {article_number}")
        image_id = nonempty(case.get("image_id"), "case.image_id")
        image_records = [
            record
            for record in article.get("images", [])
            if isinstance(record, dict)
            and isinstance(record.get("image"), dict)
            and record["image"].get("image_id") == image_id
        ]
        if len(image_records) != 1:
            raise TunePipelineError(
                f"Expected one canonical image for {article_number}#{image_id}, found {len(image_records)}"
            )
        record = image_records[0]
        image = record["image"]
        outputs = record.get("outputs")
        if not isinstance(outputs, list) or len(outputs) != 3:
            raise TunePipelineError(f"Canonical image must have three outputs: {case['case_id']}")
        output_by_model = {
            output.get("model_id"): output
            for output in outputs
            if isinstance(output, dict)
        }
        if set(output_by_model) != set(runner.SUPPORTED_MODELS):
            raise TunePipelineError(f"Canonical model set mismatch: {case['case_id']}")
        target_models = {
            nonempty(target.get("model_id"), "target.model_id")
            for target in case["targets"]
        }
        ordered_target_models = [
            model_id for model_id in runner.SUPPORTED_MODELS if model_id in target_models
        ]
        run_id = f"{BATCH_ID}-{article['article_slug']}-{image_id.replace('.', '-')}"
        baseline_by_model: dict[str, dict[str, Any]] = {}
        for model_id, output in output_by_model.items():
            key = (article["article_slug"], image_id, model_id)
            public_video = public_videos.get(key)
            if public_video is None:
                raise TunePipelineError(f"No public baseline video for {key}")
            baseline_by_model[model_id] = {
                "scene_plan": output.get("scene_plan"),
                "positive_prompt": output.get("positive_prompt"),
                "negative_prompt": output.get("negative_prompt"),
                "video_url": public_video,
                "repository_video_path": output.get("video_path"),
                "media": output.get("media"),
                "status": output.get("status"),
            }
        resolved.append(
            {
                "evaluation": case,
                "article": article,
                "image": image,
                "baseline_by_model": baseline_by_model,
                "target_models": ordered_target_models,
                "run_id": run_id,
            }
        )
    return resolved


def filter_cases(
    cases: Iterable[dict[str, Any]],
    requested_case_ids: Iterable[str],
) -> list[dict[str, Any]]:
    cases = list(cases)
    requested = list(requested_case_ids)
    if not requested:
        return cases
    by_id = {case["evaluation"]["case_id"]: case for case in cases}
    unknown = set(requested) - set(by_id)
    if unknown:
        raise TunePipelineError(f"Unknown tune case(s): {', '.join(sorted(unknown))}")
    return [by_id[case_id] for case_id in requested]


def prepare_case(case: dict[str, Any], root: Path = ROOT) -> str:
    run_id = case["run_id"]
    directory = root / runner.OUTPUT_NAMESPACE / run_id
    if directory.exists():
        job, _, _ = runner.validate_prepared_job(root, run_id)
        actual_models = [
            model["model_id"] for model in job["selected_models"]
        ]
        if actual_models != case["target_models"]:
            raise TunePipelineError(f"Prepared model set changed: {run_id}")
        return "already-prepared"
    runner.prepare_run(
        root,
        run_id,
        case["image"]["source_path"],
        case["article"]["context_path"],
        image_id=case["image"]["image_id"],
        model_ids=case["target_models"],
        user_direction=None,
    )
    return "prepared"


def result_is_verified(case: dict[str, Any], root: Path = ROOT) -> bool:
    result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
    if not result_path.is_file() or result_path.is_symlink():
        return False
    summary = runner.provenance_summary(root, case["run_id"])
    return (
        summary.get("verified") is True
        and summary.get("contract_version") == EXPECTED_CONTRACT_VERSION
        and summary.get("models") == case["target_models"]
    )


def run_case(
    case: dict[str, Any],
    *,
    root: Path = ROOT,
    author_model: str | None,
    timeout: int,
) -> str:
    if result_is_verified(case, root):
        return "already-complete"
    runner.run_agent(
        root,
        case["run_id"],
        author_model=author_model,
        timeout=timeout,
        external_processing_approved=True,
    )
    if not result_is_verified(case, root):
        raise TunePipelineError(f"Lite provenance did not verify: {case['run_id']}")
    return "completed"


def run_cases(
    cases: list[dict[str, Any]],
    *,
    root: Path = ROOT,
    jobs: int,
    author_model: str | None,
    timeout: int,
) -> None:
    if jobs < 1 or jobs > 4:
        raise TunePipelineError("--jobs must be between 1 and 4")
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
        completed = 0
        for future in concurrent.futures.as_completed(future_to_case):
            case = future_to_case[future]
            completed += 1
            try:
                status = future.result()
                print(
                    f"tune [{completed}/{len(cases)}] {case['evaluation']['case_id']} "
                    f"{case['run_id']} -> {status}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001 - aggregate immutable failures
                failures.append(f"{case['evaluation']['case_id']}: {exc}")
                print(
                    f"tune [{completed}/{len(cases)}] {case['evaluation']['case_id']} -> failed: {exc}",
                    flush=True,
                )
    if failures:
        raise TunePipelineError(
            f"{len(failures)} tune run(s) failed:\n" + "\n".join(failures)
        )


def build_manifest(
    evaluation: dict[str, Any],
    cases: list[dict[str, Any]],
    root: Path = ROOT,
) -> dict[str, Any]:
    if len(cases) != EXPECTED_CASES:
        raise TunePipelineError("The published tune manifest requires the complete 36-case batch")
    published_cases: list[dict[str, Any]] = []
    mode_counts = {"i2v": 0, "deterministic-compositor": 0}
    strategy_counts = {
        "image-to-video": 0,
        "camera-only": 0,
        "deterministic-compositor": 0,
    }
    target_count = 0
    for case in cases:
        if not result_is_verified(case, root):
            raise TunePipelineError(f"Tune result is not verified: {case['run_id']}")
        result_path = root / runner.OUTPUT_NAMESPACE / case["run_id"] / "result.json"
        result = read_json(result_path)
        summary = runner.provenance_summary(root, case["run_id"])
        structured_intent = result["analysis"]["structured_intent"]
        strategy = structured_intent["rendering_strategy"]
        strategy_counts[strategy] += 1
        tuned_by_model = {model["model_id"]: model for model in result["models"]}
        published_targets: list[dict[str, Any]] = []
        for target in case["evaluation"]["targets"]:
            model_id = target["model_id"]
            tuned = tuned_by_model.get(model_id)
            if tuned is None:
                raise TunePipelineError(f"Missing tuned model {model_id}: {case['run_id']}")
            execution_mode = tuned["execution_mode"]
            mode_counts[execution_mode] += 1
            target_count += 1
            published_targets.append(
                {
                    **target,
                    "baseline": case["baseline_by_model"][model_id],
                    "tuned": {
                        "execution_mode": execution_mode,
                        "scene_plan": tuned["scene_plan"],
                        "positive_prompt": tuned["positive_prompt"],
                        "negative_prompt": tuned["negative_prompt"],
                        "runtime": tuned["runtime"],
                    },
                }
            )
        target_models = set(case["target_models"])
        published_cases.append(
            {
                "case_id": case["evaluation"]["case_id"],
                "article_number": case["evaluation"]["article_number"],
                "article_slug": case["article"]["article_slug"],
                "brand": case["evaluation"]["brand"],
                "title": case["evaluation"]["title"],
                "publication_id": case["evaluation"]["publication_id"],
                "content_class": case["evaluation"]["content_class"],
                "hypothesis": case["evaluation"]["hypothesis"],
                "source": {
                    "image_id": case["image"]["image_id"],
                    "role": case["image"]["role"],
                    "caption": case["image"]["caption"],
                    "path": case["image"]["source_path"],
                    "url": case["image"]["orig_url"],
                    "sha256": case["image"]["sha256"],
                    "width": case["image"]["width"],
                    "height": case["image"]["height"],
                },
                "context_path": case["article"]["context_path"],
                "planning": {
                    "run_id": case["run_id"],
                    "result_path": result_path.relative_to(root).as_posix(),
                    "provenance": summary,
                    "structured_intent": structured_intent,
                    "image_reading": result["analysis"]["image_reading"],
                    "article_context": result["analysis"]["article_context"],
                },
                "accepted_sibling_model_ids": [
                    model_id
                    for model_id in runner.SUPPORTED_MODELS
                    if model_id not in target_models
                ],
                "targets": published_targets,
            }
        )
    if target_count != EXPECTED_TARGETS:
        raise TunePipelineError(f"Published target count mismatch: {target_count}")
    return {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-tune-review",
        "ticket": "PROMOPAGES-10060",
        "batch_id": BATCH_ID,
        "agent_id": runner.AGENT_ID,
        "contract_version": EXPECTED_CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": {
            "source_evaluation": EVALUATION_PATH.as_posix(),
            "case_count": EXPECTED_CASES,
            "target_count": EXPECTED_TARGETS,
            "new_video_generation": False,
            "new_s3_upload": False,
            "baseline_video_delivery": "existing-yastatic",
            "quality_acceptance": "fresh-human-review-required",
        },
        "summary": {
            "rating": evaluation["selection"],
            "execution_mode_counts": mode_counts,
            "rendering_strategy_case_counts": strategy_counts,
        },
        "cases": published_cases,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("prepare", "run", "build", "all"),
        nargs="?",
        default="all",
    )
    parser.add_argument("--case", action="append", default=[], dest="case_ids")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--author-model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--allow-external-processing", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        evaluation = load_evaluation(ROOT)
        all_cases = resolved_cases(evaluation, ROOT)
        selected_cases = filter_cases(all_cases, args.case_ids)
        if args.command in {"prepare", "all"}:
            for index, case in enumerate(selected_cases, 1):
                status = prepare_case(case, ROOT)
                print(
                    f"prepare [{index}/{len(selected_cases)}] "
                    f"{case['evaluation']['case_id']} -> {status}",
                    flush=True,
                )
        if args.command in {"run", "all"}:
            if not args.allow_external_processing:
                raise TunePipelineError(
                    "run/all requires --allow-external-processing"
                )
            run_cases(
                selected_cases,
                root=ROOT,
                jobs=args.jobs,
                author_model=args.author_model,
                timeout=args.timeout,
            )
        if args.command in {"build", "all"}:
            manifest = build_manifest(evaluation, all_cases, ROOT)
            atomic_write_json(ROOT / OUTPUT_MANIFEST_PATH, manifest)
            print(
                f"wrote {OUTPUT_MANIFEST_PATH} "
                f"({len(manifest['cases'])} cases / "
                f"{sum(len(case['targets']) for case in manifest['cases'])} targets)",
                flush=True,
            )
        return 0
    except (TunePipelineError, runner.LiteRunnerError) as exc:
        print(f"clipmaker-lite tune error: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
