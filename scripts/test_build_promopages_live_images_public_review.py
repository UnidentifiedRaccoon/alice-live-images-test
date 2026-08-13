from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import build_promopages_live_images_public_review as review


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _acceptance(
    model_id: str,
    media: dict[str, Any],
    contract_check: dict[str, Any],
    article: dict[str, Any],
) -> dict[str, Any]:
    entry = review.native.Entry(
        review.native.Sample(
            sample_id="public-review-fixture",
            article_slug=article["article_slug"],
            image_id=article["image_id"],
            filename="fixture.png",
            source_sha256=article["source_sha256"],
            width=article["width"],
            height=article["height"],
        ),
        model_id,
    )
    return review.native.media_acceptance(entry, media, contract_check)


def _fixtures() -> tuple[dict[str, Any], dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    delivered: list[dict[str, Any]] = []
    for contract in review.ARTICLE_CONTRACTS:
        articles.append(
            {
                "article_number": contract["article_number"],
                "article_slug": contract["article_slug"],
                "publication_id": contract["publication_id"],
                "brand": contract["brand"],
                "title": contract["title"],
                "article_url": contract["article_url"],
                "image": {
                    "image_id": contract["image_id"],
                    "media_id": contract["media_id"],
                    "width": contract["width"],
                    "height": contract["height"],
                    "caption": contract["caption"],
                    "source_url": contract["source_url"],
                    "source_sha256": contract["source_sha256"],
                    "planning_run_id": contract["planning_run_id"],
                },
            }
        )
        for model_index, model_id in enumerate(review.MODEL_IDS, start=1):
            attempt_id = f"attempt-{contract['article_number']}-{model_index}"
            provider_run_id = f"provider-{contract['article_number']}-{model_index}"
            prompt = {
                "positive": f"Stable motion for {contract['media_id']} and {model_id}.",
                "negative": None,
            }
            media_sha = _sha(f"{contract['article_slug']}/{model_id}")
            media = {
                "container": "mov,mp4,m4a,3gp,3g2,mj2",
                "codec": "h264",
                "duration_seconds": 4.0 if model_id.startswith("google/") else 5.0,
                "width": 1920 if model_id.startswith("google/") else 1280,
                "height": 1080 if model_id.startswith("google/") else 720,
                "fps": 24.0,
                "frames": 96,
                "has_audio": False,
                "bytes": 1_000_000 + model_index,
                "sha256": media_sha,
            }
            contract_check = {
                "requested": {"generate_audio": False},
                "checks": {"audio": True},
                "conforms": True,
                "warnings": [],
            }
            media_acceptance = _acceptance(
                model_id, media, contract_check, contract
            )
            output = {
                "article_number": contract["article_number"],
                "article_slug": contract["article_slug"],
                "publication_id": contract["publication_id"],
                "image_id": contract["image_id"],
                "media_id": contract["media_id"],
                "model_id": model_id,
                "status": "succeeded",
                "recorded_status": "succeeded",
                "selected_attempt_id": attempt_id,
                "selected_prompt": copy.deepcopy(prompt),
                "provider_run_id": provider_run_id,
                "video_path": (
                    f"clipmaker-lite-test/runs/{review.BATCH_ID}/videos/"
                    f"{contract['article_slug']}/{model_id}/{contract['image_id']}.mp4"
                ),
                "media": media,
                "contract_check": contract_check,
                "media_acceptance": media_acceptance,
                "error": None,
                "attempt_count": 1,
                "attempts": [
                    {
                        "attempt_id": attempt_id,
                        "status": "succeeded",
                        "recorded_status": "succeeded",
                        "prompt": copy.deepcopy(prompt),
                        "provider_run_id": provider_run_id,
                        "provider_response": {
                            "http_status": 200,
                            "request_id": f"request-{attempt_id}",
                        },
                        "media": copy.deepcopy(media),
                        "contract_check": copy.deepcopy(contract_check),
                        "media_acceptance": copy.deepcopy(media_acceptance),
                        "error": None,
                    }
                ],
            }
            outputs.append(output)
            object_key = (
                f"{review.OBJECT_PREFIX}{contract['cabinet_path']}/"
                f"{contract['publication_id']}/{review.MODEL_DIRECTORIES[model_id]}/"
                f"image_{contract['image_id']}--sha256-{media_sha[:12]}.mp4"
            )
            delivered.append(
                {
                    "article_slug": contract["article_slug"],
                    "publication_id": contract["publication_id"],
                    "image_id": contract["image_id"],
                    "media_id": contract["media_id"],
                    "model_id": model_id,
                    "recorded_status": "succeeded",
                    "selected_attempt_id": attempt_id,
                    "provider_run_id": provider_run_id,
                    "sha256": media_sha,
                    "bytes": media["bytes"],
                    "media_acceptance": copy.deepcopy(media_acceptance),
                    "object_key": object_key,
                    "yastatic_url": review.PUBLIC_BASE_URL + object_key,
                }
            )
    final = {
        "schema_version": 1,
        "manifest_role": "clipmaker-lite-final-selection",
        "dataset_prefix": review.DATASET_PREFIX,
        "batch_id": review.BATCH_ID,
        "producer": {
            "agent_id": review.AGENT_ID,
            "contract_version": review.CONTRACT_VERSION,
            "runner_version": review.RUNNER_VERSION,
        },
        "models": list(review.MODEL_IDS),
        "article_count": 2,
        "image_count": 2,
        "expected_outputs": 6,
        "articles": articles,
        "outputs": outputs,
    }
    delivery = {
        "schema_version": 1,
        "manifest_role": "promopages-live-images-s3-delivery",
        "batch_id": review.BATCH_ID,
        "bucket": review.BUCKET,
        "object_prefix": review.OBJECT_PREFIX,
        "verified_output_count": len(delivered),
        "outputs": delivered,
    }
    return final, delivery


def _provenance(root: Path, run_id: str) -> dict[str, Any]:
    contract = next(
        item for item in review.ARTICLE_CONTRACTS if item["planning_run_id"] == run_id
    )
    return {
        "verified": True,
        "verification_scope": review.runner.VERIFICATION_SCOPE,
        "cryptographically_signed": False,
        "result_path": (
            review.runner.OUTPUT_NAMESPACE / run_id / "result.json"
        ).as_posix(),
        "agent_id": review.AGENT_ID,
        "contract_version": review.CONTRACT_VERSION,
        "contract_fingerprint": f"sha256:{_sha('contract')}",
        "instruction_bundle_sha256": _sha("bundle"),
        "runner": {
            "path": review.runner.RUNNER_PATH.as_posix(),
            "sha256": review._sha256_file(root / review.runner.RUNNER_PATH),
        },
        "models": list(review.MODEL_IDS),
        "source_image_sha256": contract["source_sha256"],
        "article_context_sha256": _sha(run_id),
    }


class PublicReviewBuilderTest(unittest.TestCase):
    def _write(self, directory: Path, name: str, value: dict[str, Any]) -> Path:
        path = directory / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def _build(
        self, directory: Path, final: dict[str, Any], delivery: dict[str, Any]
    ) -> dict[str, Any]:
        return review.build_manifest(
            root=review.ROOT,
            final_selection_path=self._write(directory, "final.json", final),
            delivery_manifest_path=self._write(directory, "delivery.json", delivery),
            provenance_resolver=_provenance,
        )

    def test_rejects_delivery_hash_mismatch(self) -> None:
        final, delivery = _fixtures()
        delivery["outputs"][0]["sha256"] = "f" * 64
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                review.ReviewManifestError, "selection or media differs"
            ):
                self._build(Path(temporary), final, delivery)

    def test_rejects_unverified_primary_planning_provenance(self) -> None:
        final, delivery = _fixtures()

        def unverified(root: Path, run_id: str) -> dict[str, Any]:
            value = _provenance(root, run_id)
            value["verified"] = False
            return value

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            final_path = self._write(directory, "final.json", final)
            delivery_path = self._write(directory, "delivery.json", delivery)
            with self.assertRaisesRegex(review.ReviewManifestError, "provenance differs"):
                review.build_manifest(
                    root=review.ROOT,
                    final_selection_path=final_path,
                    delivery_manifest_path=delivery_path,
                    provenance_resolver=unverified,
                )

    def test_unavailable_output_has_null_selection_and_no_delivery(self) -> None:
        final, delivery = _fixtures()
        target = next(
            output
            for output in final["outputs"]
            if output["article_slug"] == review.ARTICLE_CONTRACTS[0]["article_slug"]
            and output["model_id"] == "alibaba/wan-2.7"
        )
        target.update(
            {
                "status": "unavailable",
                "recorded_status": None,
                "selected_attempt_id": None,
                "selected_prompt": None,
                "provider_run_id": None,
                "video_path": None,
                "media": None,
                "contract_check": None,
                "media_acceptance": None,
                "error": "No technically valid MP4 after the final attempt",
            }
        )
        target["attempts"][0]["status"] = "verification-failed"
        target["attempts"][0]["recorded_status"] = "verification-failed"
        target["attempts"][0]["media"] = None
        target["attempts"][0]["contract_check"] = None
        target["attempts"][0]["media_acceptance"] = None
        target["attempts"][0]["error"] = "Media contract verification failed"
        delivery["outputs"] = [
            row
            for row in delivery["outputs"]
            if not (
                row["article_slug"] == target["article_slug"]
                and row["model_id"] == target["model_id"]
            )
        ]
        delivery["verified_output_count"] = len(delivery["outputs"])

        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._build(Path(temporary), final, delivery)
        output = manifest["articles"][0]["image"]["outputs"][1]
        self.assertEqual(output["status"], "unavailable")
        for field in (
            "selected_attempt_id",
            "selected_prompt",
            "video_url",
            "media",
            "contract_check",
            "media_acceptance",
            "recorded_status",
        ):
            self.assertIsNone(output[field])
        self.assertTrue(output["error"])

    def test_normalizes_null_negative_prompts_and_preserves_attempt_audit(self) -> None:
        final, delivery = _fixtures()
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._build(Path(temporary), final, delivery)
        outputs = [
            output
            for article in manifest["articles"]
            for output in article["image"]["outputs"]
        ]
        self.assertEqual(len(outputs), 6)
        for output in outputs:
            self.assertEqual(output["selected_prompt"]["negative"], "")
            self.assertEqual(output["attempts"][0]["prompt"]["negative"], "")
            self.assertIn("request_id", output["attempts"][0]["provider_response"])

    def test_accepts_exact_wan_27_audio_exception_and_preserves_raw_audit(self) -> None:
        final, delivery = _fixtures()
        target = next(
            output
            for output in final["outputs"]
            if output["article_slug"] == review.ARTICLE_CONTRACTS[1]["article_slug"]
            and output["model_id"] == "alibaba/wan-2.7"
        )
        target["media"]["has_audio"] = True
        target["contract_check"] = {
            "requested": {"generate_audio": False},
            "checks": {
                "duration": True,
                "audio": False,
                "resolution": True,
                "aspect_ratio": True,
            },
            "conforms": False,
            "warnings": ["audio"],
        }
        contract = review.ARTICLE_CONTRACTS[1]
        target["media_acceptance"] = _acceptance(
            target["model_id"], target["media"], target["contract_check"], contract
        )
        target["recorded_status"] = "verification-failed"
        attempt = target["attempts"][0]
        attempt.update(
            {
                "status": "succeeded",
                "recorded_status": "verification-failed",
                "media": copy.deepcopy(target["media"]),
                "contract_check": copy.deepcopy(target["contract_check"]),
                "media_acceptance": copy.deepcopy(target["media_acceptance"]),
                "error": "Media contract verification failed: audio",
            }
        )
        delivered = next(
            row
            for row in delivery["outputs"]
            if row["article_slug"] == target["article_slug"]
            and row["model_id"] == target["model_id"]
        )
        delivered["recorded_status"] = "verification-failed"
        delivered["media_acceptance"] = copy.deepcopy(target["media_acceptance"])

        with tempfile.TemporaryDirectory() as temporary:
            manifest = self._build(Path(temporary), final, delivery)
        public = manifest["articles"][1]["image"]["outputs"][1]
        self.assertEqual(public["status"], "succeeded")
        self.assertEqual(public["recorded_status"], "verification-failed")
        self.assertFalse(public["contract_check"]["conforms"])
        self.assertEqual(public["contract_check"]["warnings"], ["audio"])
        self.assertEqual(public["media_acceptance"]["mode"], "route-exception")
        self.assertEqual(public["attempts"][0]["recorded_status"], "verification-failed")

    def test_rejects_wan_27_exception_that_waives_resolution(self) -> None:
        final, delivery = _fixtures()
        target = next(
            output
            for output in final["outputs"]
            if output["article_slug"] == review.ARTICLE_CONTRACTS[1]["article_slug"]
            and output["model_id"] == "alibaba/wan-2.7"
        )
        target["media"]["has_audio"] = True
        audio_only_check = {
            "requested": {"generate_audio": False},
            "checks": {"audio": False, "resolution": True},
            "conforms": False,
            "warnings": ["audio"],
        }
        target["media_acceptance"] = _acceptance(
            target["model_id"],
            target["media"],
            audio_only_check,
            review.ARTICLE_CONTRACTS[1],
        )
        target["contract_check"] = {
            **audio_only_check,
            "checks": {"audio": False, "resolution": False},
            "warnings": ["audio", "resolution"],
        }
        target["recorded_status"] = "verification-failed"
        attempt = target["attempts"][0]
        attempt.update(
            {
                "recorded_status": "verification-failed",
                "media": copy.deepcopy(target["media"]),
                "contract_check": copy.deepcopy(target["contract_check"]),
                "media_acceptance": copy.deepcopy(target["media_acceptance"]),
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                review.ReviewManifestError, "media acceptance is invalid"
            ):
                self._build(Path(temporary), final, delivery)


if __name__ == "__main__":
    unittest.main()
