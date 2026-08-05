import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import build_github_pages_site as pages


ROOT = Path(__file__).resolve().parents[1]
ADDITIONAL_MANIFEST_PATH = (
    ROOT / "clipmaker-lite-test" / "promopages-9930-manifest.json"
)
CASE_21_MANIFEST_PATH = ROOT / "clipmaker-lite-test" / "case-21-manifest.json"
PROMOPAGES_10060_MANIFEST_PATH = (
    ROOT / "clipmaker-lite-test" / "promopages-10060-manifest.json"
)
PROMOPAGES_10060_IMAGE_COUNTS = (
    ("01", 4),
    ("03", 9),
    ("04", 8),
    ("05", 7),
    ("06", 6),
    ("07", 9),
    ("08", 8),
    ("09", 5),
    ("10", 8),
    ("11", 4),
    ("12", 10),
    ("13", 8),
    ("14", 6),
)
NORMALIZED_RETRY_NAMESPACE = (
    "clipmaker-lite-test/runs/promopages-10060-test/normalized-input-retries-v1"
)
NORMALIZED_ASSET_NAMESPACE = (
    "clipmaker-lite-test/runs/promopages-10060-test/normalized-input-assets-v1"
)
NORMALIZED_ORIGINAL_URL = (
    "https://avatars.mds.yandex.net/get-direct-picture/117225/oversize/orig"
)
NORMALIZED_URL = (
    "https://avatars.mds.yandex.net/get-direct-picture/117225/oversize/scale_1200"
)


def _provider_filtered_output(article_slug, image_id, model_id):
    request_sha = "1" * 64
    namespace = (
        "clipmaker-lite-test/runs/promopages-10060-test/"
        "terminal-provider-retries-v1/filtered-output"
    )
    retry_error = "Video completed with no output; content may have been filtered"
    return {
        "article_slug": article_slug,
        "image_id": image_id,
        "model_id": model_id,
        "provider_run_id": "retry-provider-run",
        "positive_prompt": "Keep the source stable with one subtle movement.",
        "status": "provider-filtered",
        "recorded_status": "provider-failed",
        "selected_attempt": "terminal-retry-v1-exhausted",
        "video_path": None,
        "media": None,
        "contract_check": None,
        "error": retry_error,
        "retry": {
            "retry_number": 1,
            "namespace": namespace,
            "envelope_path": f"{namespace}/retry.json",
            "exhausted": True,
            "primary_attempt": {
                "provider_run_id": "primary-provider-run",
                "provider_job_id": "primary-job",
                "status": "provider-failed",
                "submitted_at": "2026-08-04T23:42:39Z",
                "completed_at": "2026-08-04T23:44:12Z",
                "error": "Video completed with no output; content may have been filtered",
                "run_path": "runs/primary.run.json",
                "run_sha256": "2" * 64,
                "prompt_path": "runs/primary.prompt.json",
                "prompt_sha256": "3" * 64,
                "request_sha256": request_sha,
            },
            "retry_attempt": {
                "provider_run_id": "retry-provider-run",
                "provider_job_id": "retry-job",
                "status": "provider-failed",
                "provider_may_be_active": False,
                "submitted_at": "2026-08-04T23:57:23Z",
                "completed_at": "2026-08-04T23:58:27Z",
                "error": retry_error,
                "run_path": "runs/retry.run.json",
                "run_sha256": "4" * 64,
                "prompt_path": "runs/retry.prompt.json",
                "prompt_sha256": "5" * 64,
                "request_sha256": request_sha,
            },
        },
    }


def _provider_unavailable_output(article_slug, image_id, model_id):
    request_sha = "6" * 64
    namespace = (
        "clipmaker-lite-test/runs/promopages-10060-test/"
        "ambiguous-submit-retries-v1/unavailable-output"
    )
    retry_error = "Provider returned a terminal failure after the explicit retry"
    return {
        "article_slug": article_slug,
        "image_id": image_id,
        "model_id": model_id,
        "provider_run_id": "ambiguous-retry-provider-run",
        "positive_prompt": "Keep the exact source with one restrained movement.",
        "status": "provider-unavailable",
        "recorded_status": "provider-failed",
        "selected_attempt": "ambiguous-submit-retry-v1-exhausted",
        "video_path": None,
        "media": None,
        "contract_check": None,
        "error": retry_error,
        "retry": {
            "retry_kind": "ambiguous-submit",
            "retry_number": 1,
            "namespace": namespace,
            "envelope_path": f"{namespace}/retry.json",
            "envelope_sha256": "7" * 64,
            "exhausted": True,
            "primary_outcome_unknown": True,
            "primary_attempt": {
                "provider_run_id": "ambiguous-primary-provider-run",
                "provider_job_id": None,
                "status": "submit-unknown",
                "recorded_status": "submitting",
                "outcome": "unknown",
                "outcome_unknown": True,
                "ambiguity_reason": (
                    "Synchronous submit may have reached the provider without "
                    "a durable response"
                ),
                "provider_may_be_active": True,
                "submitted_at": None,
                "completed_at": None,
                "error": None,
                "run_path": "runs/ambiguous-primary.run.json",
                "run_sha256": "8" * 64,
                "prompt_path": "runs/ambiguous-primary.prompt.json",
                "prompt_sha256": "9" * 64,
                "request_sha256": request_sha,
            },
            "retry_attempt": {
                "provider_run_id": "ambiguous-retry-provider-run",
                "provider_job_id": "ambiguous-retry-provider-job",
                "status": "provider-failed",
                "provider_may_be_active": False,
                "submitted_at": "2026-08-05T05:10:00Z",
                "completed_at": "2026-08-05T05:12:00Z",
                "error": retry_error,
                "run_path": "runs/ambiguous-retry.run.json",
                "run_sha256": "a" * 64,
                "prompt_path": "runs/ambiguous-retry.prompt.json",
                "prompt_sha256": "b" * 64,
                "request_sha256": request_sha,
            },
        },
    }


def _ambiguous_retry_success_output(article_slug, image_id, model_id, video_path):
    output = _provider_unavailable_output(article_slug, image_id, model_id)
    output.update(
        {
            "status": "succeeded",
            "recorded_status": "succeeded",
            "selected_attempt": "ambiguous-submit-retry-v1",
            "video_path": video_path,
            "media": {
                "width": 1280,
                "height": 720,
                "duration_seconds": 5,
                "bytes": 2048,
            },
            "contract_check": {"conforms": True, "warnings": []},
            "error": None,
        }
    )
    output["retry"]["exhausted"] = False
    output["retry"]["retry_attempt"].update(
        {"status": "succeeded", "error": None}
    )
    return output


def _normalized_input_retry_output(
    article_slug,
    image,
    model_id,
    *,
    exhausted,
    video_path=None,
):
    model_suffix = "wan22" if model_id == "alibaba/wan-2.2" else "wan27"
    namespace = f"{NORMALIZED_RETRY_NAMESPACE}/{model_suffix}-retry-key"
    retry_error = (
        "Provider returned a terminal failure after normalized input retry"
        if exhausted
        else None
    )
    recorded_status = "provider-failed" if exhausted else "succeeded"
    primary = {
        "provider_run_id": f"{model_suffix}-oversize-primary-run",
        "provider_job_id": f"{model_suffix}-oversize-primary-job",
        "status": "provider-failed",
        "recorded_status": (
            "submit-unknown"
            if model_id == "alibaba/wan-2.2"
            else "provider-failed"
        ),
        "provider_may_be_active": False,
        "recorded_provider_may_be_active": model_id == "alibaba/wan-2.2",
        "submitted_at": (
            None
            if model_id == "alibaba/wan-2.2"
            else "2026-08-05T06:00:00Z"
        ),
        "completed_at": (
            None
            if model_id == "alibaba/wan-2.2"
            else "2026-08-05T06:01:00Z"
        ),
        "error": "File size exceeds maximum allowed size of 20971520 bytes",
        "run_path": f"runs/{model_suffix}-oversize-primary.run.json",
        "run_sha256": "c" * 64,
        "prompt_path": f"runs/{model_suffix}-oversize-primary.prompt.json",
        "prompt_sha256": "d" * 64,
        "request_sha256": "e" * 64,
    }
    if model_id == "alibaba/wan-2.2":
        primary.update(
            {
                "provider_submit_time": "2026-08-05T06:00:00Z",
                "provider_scheduled_time": "2026-08-05T06:00:01Z",
                "provider_end_time": "2026-08-05T06:00:02Z",
            }
        )
    return {
        "article_slug": article_slug,
        "image_id": image["image_id"],
        "source_path": image["source_path"],
        "model_id": model_id,
        "provider_run_id": f"{model_suffix}-normalized-retry-run",
        "positive_prompt": "Keep the exact scene and add restrained movement.",
        "status": "provider-unavailable" if exhausted else "succeeded",
        "recorded_status": recorded_status,
        "selected_attempt": (
            "normalized-input-retry-v1-exhausted"
            if exhausted
            else "normalized-input-retry-v1"
        ),
        "video_path": None if exhausted else video_path,
        "media": None if exhausted else {"width": 1280, "height": 720},
        "contract_check": None if exhausted else {"conforms": True},
        "error": retry_error,
        "retry": {
            "retry_kind": "normalized-input",
            "retry_number": 1,
            "namespace": namespace,
            "envelope_path": f"{namespace}/retry.json",
            "envelope_sha256": "f" * 64,
            "exhausted": exhausted,
            "primary_attempt": primary,
            "retry_attempt": {
                "provider_run_id": f"{model_suffix}-normalized-retry-run",
                "provider_job_id": f"{model_suffix}-normalized-retry-job",
                "status": recorded_status,
                "provider_may_be_active": False,
                "submitted_at": "2026-08-05T06:05:00Z",
                "completed_at": "2026-08-05T06:07:00Z",
                "error": retry_error,
                "run_path": f"runs/{model_suffix}-normalized-retry.run.json",
                "run_sha256": "1" * 64,
                "prompt_path": f"runs/{model_suffix}-normalized-retry.prompt.json",
                "prompt_sha256": "2" * 64,
                "request_sha256": "3" * 64,
            },
            "source_transform": {
                "strategy": "frozen-page-variant",
                "original": {
                    "url": NORMALIZED_ORIGINAL_URL,
                    "path": image["source_path"],
                    "sha256": image["sha256"],
                    "bytes": 23_472_383,
                    "width": image["width"],
                    "height": image["height"],
                },
                "normalized": {
                    "url": NORMALIZED_URL,
                    "sha256": "4" * 64,
                    "bytes": 1_500_000,
                    "width": 1200,
                    "height": 801,
                    "metadata_path": (
                        f"{NORMALIZED_ASSET_NAMESPACE}/shared-asset/asset.json"
                    ),
                    "metadata_sha256": "5" * 64,
                },
                "request_delta": {
                    "json_pointer": (
                        "/input/image"
                        if model_id == "alibaba/wan-2.2"
                        else "/frame_images/0/image_url/url"
                    ),
                    "from": NORMALIZED_ORIGINAL_URL,
                    "to": NORMALIZED_URL,
                    "changed_leaf_count": 1,
                },
            },
        },
    }


def _promopages_10060_fixture(first_source_delivery=None):
    articles = []
    flat_outputs = []
    source_paths = []
    video_paths = []
    for article_number, image_count in PROMOPAGES_10060_IMAGE_COUNTS:
        article_slug = (
            "12-dream-island-7-fishek"
            if article_number == "12"
            else f"{article_number}-article"
        )
        image_records = []
        for image_number in range(1, image_count + 1):
            image_id = f"{image_number:02d}"
            source_path = f"raw/promopages-10060/{article_number}/{image_id}.jpg"
            image = {
                "image_id": image_id,
                "source_path": source_path,
            }
            if first_source_delivery is not None and not source_paths:
                image["delivery"] = first_source_delivery
            outputs = []
            for model_index, model_id in enumerate(
                pages.PROMOPAGES_10060_MODELS, start=1
            ):
                if (
                    article_number == "07"
                    and image_id == "06"
                    and model_id == "google/veo-3.1-lite"
                ):
                    output = _provider_filtered_output(
                        article_slug, image_id, model_id
                    )
                    outputs.append(output)
                    flat_outputs.append(output.copy())
                    continue
                video_path = (
                    f"raw/promopages-10060/{article_number}/{image_id}-"
                    f"model-{model_index}.mp4"
                )
                output = {
                    "article_slug": article_slug,
                    "image_id": image_id,
                    "model_id": model_id,
                    "status": "succeeded",
                    "video_path": video_path,
                }
                outputs.append(output)
                flat_outputs.append(output.copy())
                video_paths.append(video_path)
            image_records.append({"image": image, "outputs": outputs})
            source_paths.append(source_path)
        articles.append(
            {
                "article_number": article_number,
                "article_slug": article_slug,
                "image_count": image_count,
                "images": image_records,
            }
        )
    manifest = {
        "schema_version": 1,
        "manifest_role": "promopages-10060-all-images",
        "ticket": "PROMOPAGES-10060",
        "agent_id": "clipmaker-lite",
        "models": list(pages.PROMOPAGES_10060_MODELS),
        "article_count": 13,
        "image_count": 92,
        "expected_outputs": 276,
        "accepted_output_count": 275,
        "terminal_accounted_output_count": 276,
        "provider_filtered_output_count": 1,
        "provider_unavailable_output_count": 0,
        "status_summary": {
            "succeeded": 275,
            "provider-filtered": 1,
            "provider-unavailable": 0,
        },
        "acceptance_policy": {
            "requires_mp4_and_media": True,
            "terminal_accounted_without_media": [
                "provider-filtered",
                "provider-unavailable",
            ],
            "provider_filtered_requires_exhausted_retry_v1": True,
            "provider_unavailable_requires_ambiguous_submit_retry_v1": True,
            "provider_unavailable_requires_retry_v1": [
                "ambiguous-submit",
                "normalized-input",
            ],
        },
        "articles": articles,
        "outputs": flat_outputs,
        "unavailable_articles": [
            {
                "article_number": "02",
                "status": "source-unavailable",
                "error": "Public article is unavailable.",
            }
        ],
    }
    return manifest, source_paths, video_paths


class GitHubPagesSiteTest(unittest.TestCase):
    def test_runtime_allowlist_is_complete_and_within_pages_limits(self):
        if (
            not ADDITIONAL_MANIFEST_PATH.is_file()
            or not CASE_21_MANIFEST_PATH.is_file()
            or not PROMOPAGES_10060_MANIFEST_PATH.is_file()
        ):
            self.skipTest("Final Step 5 extension manifests have not been produced yet")

        paths = pages.collect_site_paths(ROOT)
        total_bytes = pages.site_size(ROOT, paths)

        self.assertEqual(len(paths), 251)
        self.assertGreater(total_bytes, 900_000_000)
        self.assertLessEqual(total_bytes, pages.MAX_SITE_BYTES)
        self.assertIn(Path("clipmaker-lite/index.html"), paths)
        self.assertIn(Path("clipmaker-lite-test/manifest.json"), paths)
        self.assertIn(
            Path("clipmaker-lite-test/promopages-9930-manifest.json"), paths
        )
        self.assertIn(Path("clipmaker-lite-test/case-21-manifest.json"), paths)
        self.assertIn(
            Path("clipmaker-lite-test/promopages-10060-manifest.json"), paths
        )
        self.assertIn(Path("manual-review/index.html"), paths)
        self.assertFalse(any("Prepared videos" in path.as_posix() for path in paths))
        self.assertEqual(
            [path for path in paths if path.suffix == ".md"],
            [Path("model-comparison-5s/fonts/NOTICE.md")],
        )

    def test_extension_media_is_validated_but_excluded_from_pages_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text(
                "clipmaker-lite-test/manifest.json",
                """{
                  "articles": [{
                    "selected_image": {"source_path": "raw/base.jpg"},
                    "outputs": [],
                    "external_outputs": [{
                      "video_path": "raw/external.mp4",
                      "delivery": "repository-raw"
                    }]
                  }]
                }\n""",
            )
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {"source_path": "raw/source.jpg"},
                      "outputs": [{"video_path": "raw/output.mp4"}]
                    }]
                  }]
                }\n""",
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/case-21-source.png",
                        "delivery": "repository-raw"
                      },
                      "outputs": [{
                        "video_path": "raw/case-21-wan22.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan27.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-veo31.mp4",
                        "delivery": "repository-raw"
                      }],
                      "research_outputs": [{
                        "video_path": "raw/case-21-wan27-retry.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan27-monotonic.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan22-erosion.mp4",
                        "delivery": "repository-raw"
                      }, {
                        "video_path": "raw/case-21-wan27-opacity.mp4",
                        "delivery": "repository-raw"
                      }]
                    }]
                  }],
                  "loop_experiment": {
                    "outputs": [{
                      "video_path": "raw/case-21-loop-sync.mp4",
                      "delivery": "repository-raw"
                    }, {
                      "video_path": "raw/case-21-loop-staggered.mp4",
                      "delivery": "repository-raw"
                    }]
                  },
                  "smooth_experiment": {
                    "outputs": [{
                      "video_path": "raw/case-21-smooth-continuous.mp4",
                      "delivery": "repository-raw"
                    }, {
                      "video_path": "raw/case-21-smooth-staggered.mp4",
                      "delivery": "repository-raw"
                    }]
                  }
                }\n""",
            )
            review_manifest, review_source_paths, review_video_paths = (
                _promopages_10060_fixture()
            )
            self.assertEqual(len(review_manifest["outputs"]), 276)
            self.assertEqual(len(review_video_paths), 275)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            source_path = root / "raw/source.jpg"
            base_path = root / "raw/base.jpg"
            video_path = root / "raw/output.mp4"
            external_video_path = root / "raw/external.mp4"
            case_21_source_path = root / "raw/case-21-source.png"
            case_21_video_paths = [
                root / "raw/case-21-wan22.mp4",
                root / "raw/case-21-wan27.mp4",
                root / "raw/case-21-veo31.mp4",
                root / "raw/case-21-wan27-retry.mp4",
                root / "raw/case-21-wan27-monotonic.mp4",
                root / "raw/case-21-wan22-erosion.mp4",
                root / "raw/case-21-wan27-opacity.mp4",
                root / "raw/case-21-loop-sync.mp4",
                root / "raw/case-21-loop-staggered.mp4",
                root / "raw/case-21-smooth-continuous.mp4",
                root / "raw/case-21-smooth-staggered.mp4",
            ]
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(b"source")
            base_path.write_bytes(b"base")
            video_path.write_bytes(b"video")
            external_video_path.write_bytes(b"external-video")
            case_21_source_path.write_bytes(b"case-21-source")
            for case_21_video_path in case_21_video_paths:
                case_21_video_path.write_bytes(b"case-21-video")
            for review_source_path in review_source_paths:
                absolute_source_path = root / review_source_path
                absolute_source_path.parent.mkdir(parents=True, exist_ok=True)
                absolute_source_path.write_bytes(b"review-source")
            for review_video_path in review_video_paths:
                absolute_video_path = root / review_video_path
                absolute_video_path.parent.mkdir(parents=True, exist_ok=True)
                absolute_video_path.write_bytes(b"review-video")

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            expected_site_files = {*static_files, "raw/base.jpg"}
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)

            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)
            self.assertNotIn(Path("raw/source.jpg"), paths)
            self.assertNotIn(Path("raw/output.mp4"), paths)
            self.assertNotIn(Path("raw/external.mp4"), paths)
            self.assertNotIn(Path("raw/case-21-source.png"), paths)
            for review_source_path in review_source_paths:
                self.assertNotIn(Path(review_source_path), paths)
            for case_21_video_path in case_21_video_paths:
                self.assertNotIn(case_21_video_path.relative_to(root), paths)
            for review_video_path in review_video_paths:
                self.assertNotIn(Path(review_video_path), paths)

            filtered_nested = review_manifest["articles"][5]["images"][5][
                "outputs"
            ][2]
            filtered_flat = next(
                output
                for output in review_manifest["outputs"]
                if output["article_slug"] == filtered_nested["article_slug"]
                and output["image_id"] == filtered_nested["image_id"]
                and output["model_id"] == filtered_nested["model_id"]
            )
            retry_request_sha = filtered_nested["retry"]["retry_attempt"].pop(
                "request_sha256"
            )
            filtered_flat["retry"]["retry_attempt"].pop("request_sha256", None)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "invalid request_sha256"),
            ):
                pages.collect_site_paths(root)
            filtered_nested["retry"]["retry_attempt"][
                "request_sha256"
            ] = retry_request_sha
            filtered_flat["retry"]["retry_attempt"][
                "request_sha256"
            ] = retry_request_sha

            filtered_nested["status"] = "provider-failed"
            filtered_flat["status"] = "provider-failed"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "non-video status"),
            ):
                pages.collect_site_paths(root)
            filtered_nested["status"] = "provider-filtered"
            filtered_flat["status"] = "provider-filtered"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            ambiguous_nested = review_manifest["articles"][8]["images"][3][
                "outputs"
            ][0]
            ambiguous_flat_index = next(
                index
                for index, output in enumerate(review_manifest["outputs"])
                if output["article_slug"] == ambiguous_nested["article_slug"]
                and output["image_id"] == ambiguous_nested["image_id"]
                and output["model_id"] == ambiguous_nested["model_id"]
            )
            original_video_path = ambiguous_nested["video_path"]

            def replace_ambiguous_output(output):
                nested_copy = json.loads(json.dumps(output))
                review_manifest["articles"][8]["images"][3]["outputs"][
                    0
                ] = nested_copy
                review_manifest["outputs"][ambiguous_flat_index] = json.loads(
                    json.dumps(output)
                )

            unavailable_output = _provider_unavailable_output(
                ambiguous_nested["article_slug"],
                ambiguous_nested["image_id"],
                ambiguous_nested["model_id"],
            )
            replace_ambiguous_output(unavailable_output)
            review_manifest["accepted_output_count"] = 274
            review_manifest["provider_unavailable_output_count"] = 1
            review_manifest["status_summary"]["succeeded"] = 274
            review_manifest["status_summary"]["provider-unavailable"] = 1
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)
            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "primary_attempt"
            ]["outcome_unknown"] = False
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "primary provider outcome"),
            ):
                pages.collect_site_paths(root)
            replace_ambiguous_output(unavailable_output)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "retry_attempt"
            ]["provider_may_be_active"] = True
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "terminal selected attempt"),
            ):
                pages.collect_site_paths(root)
            replace_ambiguous_output(unavailable_output)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "retry_attempt"
            ]["request_sha256"] = "c" * 64
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "binding differs"),
            ):
                pages.collect_site_paths(root)

            success_output = _ambiguous_retry_success_output(
                ambiguous_nested["article_slug"],
                ambiguous_nested["image_id"],
                ambiguous_nested["model_id"],
                original_video_path,
            )
            replace_ambiguous_output(success_output)
            review_manifest["accepted_output_count"] = 275
            review_manifest["provider_unavailable_output_count"] = 0
            review_manifest["status_summary"]["succeeded"] = 275
            review_manifest["status_summary"]["provider-unavailable"] = 0
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                pages.collect_site_paths(root)

            review_manifest["articles"][8]["images"][3]["outputs"][0]["retry"][
                "retry_attempt"
            ]["request_sha256"] = "c" * 64
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "binding differs"),
            ):
                pages.collect_site_paths(root)
            replace_ambiguous_output(success_output)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            normalized_article = review_manifest["articles"][10]
            normalized_record = normalized_article["images"][7]
            normalized_image = normalized_record["image"]
            normalized_image.update(
                {
                    "orig_url": NORMALIZED_ORIGINAL_URL,
                    "sha256": (
                        "2cf03435b0ae53b208f033a4ec407750ed494e0cd6ec6c76e1b36e397dd1377d"
                    ),
                    "width": 5445,
                    "height": 3635,
                }
            )
            normalized_flat_indexes = {
                output["model_id"]: index
                for index, output in enumerate(review_manifest["outputs"])
                if output["article_slug"] == normalized_article["article_slug"]
                and output["image_id"] == normalized_image["image_id"]
                and output["model_id"] in {"alibaba/wan-2.2", "alibaba/wan-2.7"}
            }
            original_normalized_video_paths = {
                output["model_id"]: output["video_path"]
                for output in normalized_record["outputs"]
                if output["model_id"] in normalized_flat_indexes
            }

            def replace_normalized_output(model_id, output):
                model_index = list(pages.PROMOPAGES_10060_MODELS).index(model_id)
                normalized_record["outputs"][model_index] = json.loads(
                    json.dumps(output)
                )
                review_manifest["outputs"][normalized_flat_indexes[model_id]] = (
                    json.loads(json.dumps(output))
                )

            normalized_success = _normalized_input_retry_output(
                normalized_article["article_slug"],
                normalized_image,
                "alibaba/wan-2.2",
                exhausted=False,
                video_path=original_normalized_video_paths["alibaba/wan-2.2"],
            )
            normalized_unavailable = _normalized_input_retry_output(
                normalized_article["article_slug"],
                normalized_image,
                "alibaba/wan-2.7",
                exhausted=True,
            )
            replace_normalized_output("alibaba/wan-2.2", normalized_success)
            replace_normalized_output("alibaba/wan-2.7", normalized_unavailable)
            review_manifest["accepted_output_count"] = 274
            review_manifest["provider_unavailable_output_count"] = 1
            review_manifest["status_summary"]["succeeded"] = 274
            review_manifest["status_summary"]["provider-unavailable"] = 1
            review_manifest["cost"] = {
                "normalized_input_retry_version": 1,
                "normalized_input_retry_accounting_cost_usd": 0.35,
                "normalized_input_retry_reservations": 2,
            }
            review_manifest["generation_policy"] = {
                "normalized_input_retry": {
                    "version": 1,
                    "namespace": NORMALIZED_RETRY_NAMESPACE,
                    "shared_asset_namespace": NORMALIZED_ASSET_NAMESPACE,
                    "eligible_source": {
                        "article_slug": "12-dream-island-7-fishek",
                        "image_id": "08",
                    },
                    "models": ["alibaba/wan-2.2", "alibaba/wan-2.7"],
                    "explicit_operator_command_required": True,
                    "maximum_new_paid_submissions_per_eligible_output": 1,
                    "retry2_forbidden": True,
                    "automatic_paid_retries": False,
                    "fallback": False,
                    "primary_receipts_immutable": True,
                    "request_delta_only_image_pointer": True,
                }
            }
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
            ):
                paths = pages.collect_site_paths(root)
            self.assertEqual({path.as_posix() for path in paths}, expected_site_files)

            normalized_record["outputs"][0]["retry"]["source_transform"][
                "normalized"
            ]["bytes"] = pages.MAX_PROVIDER_SOURCE_BYTES + 1
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "normalized source audit"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.2", normalized_success)

            normalized_record["outputs"][1]["retry"]["source_transform"][
                "request_delta"
            ]["extra"] = "not allowed"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "single allowed image URL"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.7", normalized_unavailable)

            normalized_retry = normalized_record["outputs"][0]["retry"]
            normalized_retry["retry_attempt"]["request_sha256"] = normalized_retry[
                "primary_attempt"
            ]["request_sha256"]
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "request binding"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.2", normalized_success)

            review_manifest["cost"]["normalized_input_retry_reservations"] = 1
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "cost accounting"),
            ):
                pages.collect_site_paths(root)
            review_manifest["cost"]["normalized_input_retry_reservations"] = 2

            review_manifest["generation_policy"]["normalized_input_retry"][
                "namespace"
            ] = "wrong/namespace"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "allowed namespaces"),
            ):
                pages.collect_site_paths(root)
            review_manifest["generation_policy"]["normalized_input_retry"][
                "namespace"
            ] = NORMALIZED_RETRY_NAMESPACE

            normalized_record["outputs"][1]["video_path"] = "unexpected.mp4"
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "normalized retry has media"),
            ):
                pages.collect_site_paths(root)
            replace_normalized_output("alibaba/wan-2.7", normalized_unavailable)
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            case_21_video_paths[-1].unlink()
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaises(FileNotFoundError),
            ):
                pages.collect_site_paths(root)

    def test_case_21_media_must_use_repository_raw_delivery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/source.png",
                        "delivery": "site"
                      },
                      "outputs": []
                    }]
                  }]
                }\n""",
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "repository-raw"),
            ):
                pages.collect_site_paths(root)

    def test_case_21_loop_outputs_must_use_repository_raw_delivery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/source.png",
                        "delivery": "repository-raw"
                      },
                      "outputs": []
                    }]
                  }],
                  "loop_experiment": {
                    "outputs": [{
                      "video_path": "raw/loop.mp4",
                      "delivery": "site"
                    }]
                  }
                }\n""",
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "loop outputs.*repository-raw"),
            ):
                pages.collect_site_paths(root)

    def test_case_21_smooth_outputs_must_use_repository_raw_delivery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                """{
                  "articles": [{
                    "images": [{
                      "image": {
                        "source_path": "raw/source.png",
                        "delivery": "repository-raw"
                      },
                      "outputs": []
                    }]
                  }],
                  "smooth_experiment": {
                    "outputs": [{
                      "video_path": "raw/smooth.mp4",
                      "delivery": "site"
                    }]
                  }
                }\n""",
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(ValueError, "smooth outputs.*repository-raw"),
            ):
                pages.collect_site_paths(root)

    def test_promopages_10060_media_transport_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            def write_text(relative_path, content):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            write_text("generated-gallery-data.js", "window.generatedGalleryData = [];\n")
            write_text(
                "manual-review/review-data.js",
                'window.qualityReviewDataset = {"items": []};\n',
            )
            write_text("clipmaker-lite-test/manifest.json", '{"articles": []}\n')
            write_text(
                "clipmaker-lite-test/promopages-9930-manifest.json",
                '{"articles": []}\n',
            )
            write_text(
                "clipmaker-lite-test/case-21-manifest.json",
                '{"articles": []}\n',
            )
            review_manifest, _, _ = _promopages_10060_fixture(
                first_source_delivery="site"
            )
            write_text(
                "clipmaker-lite-test/promopages-10060-manifest.json",
                json.dumps(review_manifest),
            )

            static_files = (
                "clipmaker-lite-test/manifest.json",
                "clipmaker-lite-test/promopages-9930-manifest.json",
                "clipmaker-lite-test/case-21-manifest.json",
                "clipmaker-lite-test/promopages-10060-manifest.json",
            )
            with (
                mock.patch.object(pages, "STATIC_FILES", static_files),
                mock.patch.object(pages, "STATIC_TREES", ()),
                self.assertRaisesRegex(
                    ValueError,
                    "PROMOPAGES-10060 source images.*repository-raw",
                ),
            ):
                pages.collect_site_paths(root)

    def test_rejects_paths_that_can_escape_the_site_root(self):
        for value in ("../secret", "/absolute", "folder/../secret", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    pages._safe_relative_path(value)

    def test_builder_refuses_to_overwrite_an_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                pages.build_site(ROOT, output)


if __name__ == "__main__":
    unittest.main()
