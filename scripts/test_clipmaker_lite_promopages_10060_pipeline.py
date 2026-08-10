#!/usr/bin/env python3
"""Network-free tests for the PROMOPAGES-10060 Clipmaker Lite coordinator."""

from __future__ import annotations

import json
import io
import csv
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import clipmaker_lite_promopages_10060_pipeline as pipeline


def write_campaign_extension_fixture(
    root: Path,
    *,
    article_numbers: tuple[int, ...] = (15, 16, 17, 18),
) -> None:
    """Write a tiny four-article extraction fixture in the extension namespace."""

    spec = pipeline.BATCH_SPECS[pipeline.CAMPAIGN_EXTENSION_BATCH_ID]
    configs = []
    manifest_rows = []
    for number in article_numbers:
        folder = f"{number:02d}-campaign-{number}"
        label = f"Campaign {number}"
        url = f"https://example.test/articles/{number}"
        filename = "01.png"
        manifest_file_path = (
            f"{spec.dataset_prefix}/articles/{folder}/{filename}"
        )
        configs.append(
            {
                "number": number,
                "label": label,
                "folder": folder,
                "url": url,
            }
        )
        image_bytes = f"fixture-image-{number}".encode("utf-8")
        image_path = root / spec.source_image_root_rel / folder / filename
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
        context_path = root / spec.source_context_root_rel / folder / "content.json"
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(
            json.dumps(
                {
                    "title": f"Article {number}",
                    "lead": f"Lead {number}",
                    "blocks": [
                        {
                            "type": "image",
                            "image_id": "01",
                            "file": filename,
                            "manifest_file_path": manifest_file_path,
                            "role": "cover",
                            "caption": "",
                            "source_block_index": 0,
                            "gallery_index": None,
                            "duplicate_of": None,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest_rows.append(
            {
                "article_number": f"{number:02d}",
                "article_label": label,
                "article_url": url,
                "image_number": "01",
                "image_role": "cover",
                "orig_url": f"https://avatars.mds.yandex.net/{number}/orig",
                "file_path": manifest_file_path,
                "actual_width": "1200",
                "actual_height": "800",
                "sha256": hashlib.sha256(image_bytes).hexdigest(),
                "download_status": "ok",
                "duplicate_of": "",
            }
        )
    config_path = root / spec.ticket_config_rel
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(configs, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_path = root / spec.source_manifest_rel
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)


@contextmanager
def preserved_native_state():
    names = (
        "BATCH_ID",
        "PLANNING_BATCH_ID",
        "MODEL_IDS",
        "PLANNING_MODEL_IDS",
        "TICKET",
        "MANIFEST_PATH",
        "CONTRACT_PATH",
        "PLANNING_WORKSPACE",
        "PLANNING_PROVENANCE_VERIFIER",
        "SAMPLES",
        "WAN_SUBMIT_MODE",
        "SCHEDULING_EXCLUDED_RUN_IDS",
        "provider_sample",
        "artifact_paths",
    )
    original = {name: getattr(pipeline.native, name) for name in names}
    try:
        yield
    finally:
        for name, value in original.items():
            setattr(pipeline.native, name, value)


class FrozenContractRoutingTest(unittest.TestCase):
    def tearDown(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    def test_every_historical_batch_routes_to_its_exact_archived_contract(
        self,
    ) -> None:
        expected = {
            pipeline.LEGACY_BATCH_ID: "2.0.6",
            pipeline.CAMPAIGN_EXTENSION_BATCH_ID: "2.0.6",
            pipeline.ARTICLE_02_BATCH_ID: "2.0.7",
            pipeline.CAMPAIGN_20260807_BATCH_ID: "2.0.7",
        }
        self.assertEqual(pipeline.FROZEN_BATCH_CONTRACT_VERSIONS, expected)
        for batch_id, contract_version in expected.items():
            with self.subTest(batch_id=batch_id):
                pipeline.activate_batch(batch_id)
                self.assertEqual(
                    pipeline.planning_contract_version(),
                    contract_version,
                )
                self.assertIs(
                    pipeline.planning_provenance_verifier(),
                    pipeline.frozen_provenance_summary,
                )

    def test_recovery_run_id_uses_current_contract_even_while_legacy_is_active(
        self,
    ) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)
        run_id = f"{pipeline.FEMIBION_VEO_RECOVERY_ID}-sample"
        expected = {"verified": True, "contract_version": "2.0.8"}
        with (
            mock.patch.object(
                pipeline.runner,
                "provenance_summary",
                return_value=expected,
            ) as current,
            mock.patch.object(
                pipeline,
                "frozen_provenance_summary",
                side_effect=AssertionError("recovery routed to a frozen contract"),
            ),
        ):
            self.assertEqual(
                pipeline.planning_provenance_summary(pipeline.ROOT, run_id),
                expected,
            )
        current.assert_called_once_with(pipeline.ROOT, run_id)


class FemibionRecoveryOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.discovery = pipeline.discover(pipeline.ROOT)
        canonical = json.loads(
            (pipeline.ROOT / pipeline.FINAL_MANIFEST_REL).read_text(encoding="utf-8")
        )
        keys = set(pipeline.FEMIBION_VEO_RECOVERY_KEYS)
        cls.base_outputs = [
            cls._legacy_filtered_fixture(output)
            for output in canonical["outputs"]
            if (
                output["article_slug"],
                output["image_id"],
                output["model_id"],
            )
            in keys
        ]

    @staticmethod
    def _legacy_filtered_fixture(output: dict[str, object]) -> dict[str, object]:
        legacy = json.loads(json.dumps(output))
        if legacy.get("status") == "provider-filtered":
            return legacy
        retry = legacy.get("retry")
        retry_attempt = retry.get("retry_attempt") if isinstance(retry, dict) else None
        recovery = legacy.get("recovery")
        old = (
            recovery.get("superseded_selected_attempt")
            if isinstance(recovery, dict)
            else None
        )
        if not isinstance(retry_attempt, dict) or not isinstance(old, dict):
            raise AssertionError("Final recovery output lacks preserved filtered evidence")
        legacy.update(
            {
                "provider_run_id": retry_attempt["provider_run_id"],
                "provider_job_id": retry_attempt["provider_job_id"],
                "status": "provider-filtered",
                "recorded_status": "provider-failed",
                "provider_may_be_active": False,
                "prompt_path": retry_attempt["prompt_path"],
                "run_path": retry_attempt["run_path"],
                "video_path": None,
                "media": None,
                "contract_check": None,
                "error": retry_attempt["error"],
                "selected_attempt": "terminal-retry-v1-exhausted",
            }
        )
        legacy.pop("recovery", None)
        legacy.pop("supersedes_for_demo", None)
        return legacy

    def setUp(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    def tearDown(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _copy(root: Path, relative_path: str) -> None:
        source = pipeline.ROOT / relative_path
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)

    def _fixture(
        self,
        root: Path,
    ) -> tuple[
        list[dict[str, object]],
        dict[str, dict[str, object]],
        dict[str, object],
    ]:
        self._copy(root, pipeline.CONTRACT_REL.as_posix())
        self._copy(root, pipeline.ROUTES_REL.as_posix())
        sources = {
            (
                source.article_slug,
                source.image["image_id"],
                pipeline.FEMIBION_VEO_RECOVERY_MODEL_ID,
            ): source
            for source in self.discovery.sources
            if (
                source.article_slug,
                source.image["image_id"],
                pipeline.FEMIBION_VEO_RECOVERY_MODEL_ID,
            )
            in set(pipeline.FEMIBION_VEO_RECOVERY_KEYS)
        }
        base_by_key = {
            (
                output["article_slug"],
                output["image_id"],
                output["model_id"],
            ): json.loads(json.dumps(output))
            for output in self.base_outputs
        }
        for key, old in base_by_key.items():
            source = sources[key]
            self._copy(root, source.image["source_path"])
            self._copy(root, source.context_path)
            retry = old["retry"]
            for attempt in (retry["primary_attempt"], retry["retry_attempt"]):
                self._copy(root, attempt["run_path"])
                self._copy(root, attempt["prompt_path"])
            self._copy(root, retry["envelope_path"])

        summaries: dict[str, dict[str, object]] = {}
        planning: list[dict[str, object]] = []
        outputs: list[dict[str, object]] = []
        supersedes: list[dict[str, object]] = []
        for index, key in enumerate(pipeline.FEMIBION_VEO_RECOVERY_KEYS, 1):
            source = sources[key]
            old = base_by_key[key]
            old_evidence = pipeline._femibion_old_filtered_evidence(
                old,
                root=root,
                allow_contract_warnings=True,
            )
            run_id = f"{pipeline.FEMIBION_VEO_RECOVERY_ID}-{source.sample_id}"
            result_rel = pipeline.ARTIFACT_NAMESPACE / run_id / "result.json"
            model = {
                "model_id": pipeline.FEMIBION_VEO_RECOVERY_MODEL_ID,
                "scene_plan": f"Recovery scene {index}",
                "positive_prompt": f"Recovery prompt {index}",
                "negative_prompt": None,
            }
            self._write_json(
                root / result_rel,
                {"job_id": run_id, "models": [model]},
            )
            summary = {
                "verified": True,
                "agent_id": pipeline.AGENT_ID,
                "contract_version": pipeline.REQUIRED_CONTRACT_VERSION,
                "models": [pipeline.FEMIBION_VEO_RECOVERY_MODEL_ID],
                "result_path": result_rel.as_posix(),
                "source_image_sha256": source.image["sha256"],
                "article_context_sha256": source.context_sha256,
            }
            summaries[run_id] = summary
            planning_record = {
                "planning_run_id": run_id,
                "result_path": result_rel.as_posix(),
                "result_sha256": pipeline.sha256_file(root / result_rel),
                "provenance": summary,
            }
            planning.append(planning_record)
            provider_run_id = (
                f"{pipeline.FEMIBION_VEO_RECOVERY_PROVIDER_BATCH_ID}-"
                f"{source.sample_id}-veo-3-1-lite"
            )
            superseded = pipeline.FEMIBION_VEO_RECOVERY_SUPERSEDED_PROVIDER_IDS[key]
            directory = (
                pipeline.FEMIBION_VEO_RECOVERY_ROOT_REL
                / "videos"
                / source.article_slug
                / "veo-3.1-lite"
            )
            prompt_rel = directory / f"{source.image['image_id']}.prompt.json"
            run_rel = directory / f"{source.image['image_id']}.run.json"
            video_rel = directory / f"{source.image['image_id']}.mp4"
            video_path = root / video_rel
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(f"fixture-mp4-{index}".encode("utf-8"))
            media = {
                "container": "mov,mp4,m4a,3gp,3g2,mj2",
                "codec": "h264",
                "duration_seconds": 4.0,
                "width": 1920,
                "height": 1080,
                "fps": 24.0,
                "frames": 96,
                "has_audio": False,
                "bytes": video_path.stat().st_size,
                "sha256": pipeline.sha256_file(video_path),
            }
            contract_check = {
                "requested": {
                    "duration_seconds": 4,
                    "resolution": "1080p",
                    "aspect_ratio": "16:9",
                    "generate_audio": False,
                    "frames": None,
                    "fps": None,
                },
                "checks": {
                    "duration": True,
                    "audio": True,
                    "resolution": True,
                    "aspect_ratio": True,
                },
                "conforms": True,
                "warnings": [],
            }
            logical_key = {
                "article_slug": key[0],
                "image_id": key[1],
                "model_id": key[2],
            }
            receipt_binding = {
                "recovery_id": pipeline.FEMIBION_VEO_RECOVERY_ID,
                "logical_key": logical_key,
                "supersedes_for_demo": superseded,
                "old_status": "provider-filtered",
                "old_retry_v1_exhausted": True,
                "automatic_retry": False,
                "fallback": False,
            }
            request_sha256 = f"{index}" * 64
            self._write_json(
                root / prompt_rel,
                {
                    "provider_run_id": provider_run_id,
                    "lite_run_id": run_id,
                    "model_id": key[2],
                    "supersedes_for_demo": superseded,
                    "recovery": receipt_binding,
                },
            )
            self._write_json(
                root / run_rel,
                {
                    "provider_run_id": provider_run_id,
                    "sample_id": source.sample_id,
                    "image_id": source.image["image_id"],
                    "lite_run_id": run_id,
                    "model_id": key[2],
                    "status": "succeeded",
                    "media": media,
                    "contract_check": contract_check,
                    "error": None,
                    "output_path": video_rel.as_posix(),
                    "request_sha256": request_sha256,
                    "supersedes_for_demo": superseded,
                    "recovery": receipt_binding,
                },
            )
            outputs.append(
                {
                    "article_slug": key[0],
                    "image_id": key[1],
                    "source_path": source.image["source_path"],
                    "sample_id": source.sample_id,
                    "lite_run_id": run_id,
                    "provider_run_id": provider_run_id,
                    "model_id": key[2],
                    **model,
                    "status": "succeeded",
                    "recorded_status": "succeeded",
                    "provider_may_be_active": False,
                    "prompt_path": prompt_rel.as_posix(),
                    "run_path": run_rel.as_posix(),
                    "video_path": video_rel.as_posix(),
                    "media": media,
                    "contract_check": contract_check,
                    "error": None,
                    "selected_attempt": "content-filter-recovery-v1",
                    "supersedes_for_demo": superseded,
                    "recovery": {
                        "recovery_id": pipeline.FEMIBION_VEO_RECOVERY_ID,
                        "supersedes_for_demo": superseded,
                        "old_provider_filtered": old_evidence,
                        "new_request_sha256": request_sha256,
                        "request_changed": True,
                        "automatic_retry": False,
                        "fallback": False,
                    },
                }
            )
            supersedes.append(
                {
                    "logical_key": logical_key,
                    "old_provider_run_id": superseded,
                    "new_provider_run_id": provider_run_id,
                }
            )

        document: dict[str, object] = {
            "schema_version": 1,
            "manifest_role": "promopages-10060-femibion-veo-content-filter-recovery",
            "ticket": pipeline.TICKET,
            "recovery_id": pipeline.FEMIBION_VEO_RECOVERY_ID,
            "provider_batch_id": pipeline.FEMIBION_VEO_RECOVERY_PROVIDER_BATCH_ID,
            "agent_id": pipeline.AGENT_ID,
            "updated_at": "2026-08-10T12:00:00Z",
            "expected_outputs": 2,
            "accepted_output_count": 2,
            "ready_for_merge": True,
            "summary": {"succeeded": 2},
            "route": pipeline._femibion_recovery_route_snapshot(root),
            "contract": pipeline._femibion_recovery_contract_snapshot(root),
            "accounting": {
                "currency": "USD",
                "baseline_paid_submissions": 281,
                "baseline_reserved_usd": 98.35,
                "recovery_paid_submissions": 2,
                "accounting_cost_per_output_usd": 0.35,
                "recovery_reserved_usd": 0.7,
                "aggregate_paid_submissions": 283,
                "aggregate_reserved_usd": 99.05,
                "operator_budget_cap_usd": 99.05,
                "hard_budget_cap_usd": 100.0,
                "hard_cap_headroom_usd": 0.95,
                "maximum_new_paid_submissions": 2,
                "automatic_paid_retries": False,
                "pricing_basis": "frozen local PROMOPAGES-10060 accounting evidence",
            },
            "generation_policy": {
                "exact_model_id": pipeline.FEMIBION_VEO_RECOVERY_MODEL_ID,
                "exact_route_only": True,
                "automatic_fallback": False,
                "normal_run_discovery": False,
                "automatic_paid_retries": False,
                "maximum_submissions_per_new_provider_identity": 1,
                "resume_may_submit_only_never_submitted_pending_receipts": True,
                "resume_repeats_ambiguous_or_terminal_submit": False,
            },
            "merge_contract": {
                "target_manifest": pipeline.FINAL_MANIFEST_REL.as_posix(),
                "logical_key": ["article_slug", "image_id", "model_id"],
                "replace_only_status": "provider-filtered",
                "replace_exactly": 2,
                "requires_ready_for_merge": True,
                "preserve_all_other_outputs": True,
                "demo_selection_field": "supersedes_for_demo",
            },
            "supersedes_for_demo": supersedes,
            "planning": planning,
            "generation_manifest_path": (
                pipeline.FEMIBION_VEO_RECOVERY_GENERATION_MANIFEST_REL.as_posix()
            ),
            "outputs": outputs,
        }
        self._write_json(
            root / pipeline.FEMIBION_VEO_RECOVERY_MANIFEST_REL,
            document,
        )
        return list(base_by_key.values()), summaries, document

    def test_exact_overlay_preserves_retry_and_replaces_flat_and_nested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, summaries, _document = self._fixture(root)
            with mock.patch.object(
                pipeline,
                "planning_provenance_summary",
                side_effect=lambda _root, run_id: summaries[run_id],
            ):
                replacements, provenance = pipeline._femibion_recovery_overlay(
                    base,
                    self.discovery,
                    root=root,
                    allow_contract_warnings=True,
                )
            articles = [
                {
                    "images": [
                        {"outputs": [base[0]]},
                        {"outputs": [base[1]]},
                    ]
                }
            ]
            selected = pipeline._apply_final_output_replacements(
                base,
                articles,
                replacements,
            )
        self.assertEqual(set(replacements), set(pipeline.FEMIBION_VEO_RECOVERY_KEYS))
        self.assertIsNotNone(provenance)
        self.assertEqual([output["status"] for output in selected], ["succeeded"] * 2)
        self.assertEqual(
            [output["retry"] for output in selected],
            [output["retry"] for output in base],
        )
        self.assertTrue(
            all(output["recovery"]["planning"]["provenance"]["verified"] for output in selected)
        )
        self.assertEqual(
            [image["outputs"][0] for image in articles[0]["images"]],
            selected,
        )
        cost = pipeline._femibion_recovery_cost(
            {
                "operator_budget_cap_usd": 100.0,
                "maximum_estimated_cost_usd": 98.35,
                "estimated_headroom_usd": 1.65,
                "maximum_paid_submissions": 281,
                "total_retry_reservations": 5,
            },
            recovery_applied=True,
        )
        self.assertEqual(
            (
                cost["maximum_paid_submissions"],
                cost["maximum_estimated_cost_usd"],
                cost["estimated_headroom_usd"],
            ),
            (283, 99.05, 0.95),
        )

    def test_partial_manifest_is_preserved_without_any_canonical_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, _summaries, document = self._fixture(root)
            document["ready_for_merge"] = False
            document["accepted_output_count"] = 1
            self._write_json(
                root / pipeline.FEMIBION_VEO_RECOVERY_MANIFEST_REL,
                document,
            )
            replacements, provenance = pipeline._femibion_recovery_overlay(
                base,
                self.discovery,
                root=root,
                allow_contract_warnings=True,
            )
        self.assertEqual(replacements, {})
        self.assertIsNone(provenance)
        self.assertTrue(all(output["status"] == "provider-filtered" for output in base))


class Campaign20260807BatchTest(unittest.TestCase):
    def setUp(self) -> None:
        pipeline.activate_batch(pipeline.CAMPAIGN_20260807_BATCH_ID)

    def tearDown(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    def test_registered_campaign_batch_has_isolated_current_contract_namespace(
        self,
    ) -> None:
        spec = pipeline.ACTIVE_BATCH_SPEC
        self.assertEqual(spec.article_numbers, (19, 20, 21))
        self.assertEqual(
            spec.dataset_prefix,
            "PROMOPAGES-10060-campaigns-20260807-v1",
        )
        self.assertEqual(
            spec.ticket_config_rel.as_posix(),
            "PROMOPAGES-10060/campaigns-20260807-v1/articles.json",
        )
        self.assertEqual(
            spec.source_manifest_rel.as_posix(),
            "PROMOPAGES-9857/PROMOPAGES-10060-campaigns-20260807-v1/"
            "articles/manifest.csv",
        )
        self.assertEqual(
            pipeline.FINAL_MANIFEST_REL.as_posix(),
            "clipmaker-lite-test/"
            "promopages-10060-campaigns-20260807-v1-manifest.json",
        )
        self.assertIsNone(pipeline.HARD_BUDGET_CAP_USD)
        self.assertEqual(pipeline.NORMALIZED_INPUT_RETRY_ALLOWLIST, ())
        self.assertNotIn(
            pipeline.CAMPAIGN_20260807_BATCH_ID,
            pipeline.FROZEN_206_BATCH_IDS,
        )
        self.assertIn(
            pipeline.CAMPAIGN_20260807_BATCH_ID,
            pipeline.FROZEN_207_BATCH_IDS,
        )

    def test_campaign_batch_cli_accepts_exact_operator_cap(self) -> None:
        args = pipeline.build_parser().parse_args(
            [
                "--batch",
                pipeline.CAMPAIGN_20260807_BATCH_ID,
                "inventory",
                "--budget-cap-usd",
                "34.65",
                "--dry-run",
            ]
        )
        pipeline.activate_batch(args.batch)
        self.assertEqual(
            pipeline.parse_budget(args.budget_cap_usd),
            Decimal("34.65"),
        )


class Article02BatchTest(unittest.TestCase):
    def setUp(self) -> None:
        pipeline.activate_batch(pipeline.ARTICLE_02_BATCH_ID)

    def tearDown(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    def test_registered_article_02_has_isolated_immutable_namespaces(self) -> None:
        spec = pipeline.ACTIVE_BATCH_SPEC
        self.assertEqual(spec.batch_id, pipeline.ARTICLE_02_BATCH_ID)
        self.assertEqual(
            spec.dataset_prefix,
            "PROMOPAGES-10060-article-02-20260806-v1",
        )
        self.assertEqual(spec.article_numbers, (2,))
        self.assertEqual(
            spec.ticket_config_rel.as_posix(),
            "PROMOPAGES-10060/article-02-20260806-v1/articles.json",
        )
        self.assertEqual(
            spec.extraction_report_rel.as_posix(),
            "PROMOPAGES-10060/article-02-20260806-v1/extraction-report.json",
        )
        self.assertEqual(
            spec.source_manifest_rel.as_posix(),
            "PROMOPAGES-9857/PROMOPAGES-10060-article-02-20260806-v1/"
            "articles/manifest.csv",
        )
        self.assertEqual(
            spec.source_image_root_rel.as_posix(),
            "PROMOPAGES-9857/PROMOPAGES-10060-article-02-20260806-v1/articles",
        )
        self.assertEqual(
            spec.source_context_root_rel.as_posix(),
            "PROMOPAGES-9884/PROMOPAGES-10060-article-02-20260806-v1/articles",
        )
        self.assertEqual(
            pipeline.FINAL_MANIFEST_REL.as_posix(),
            "clipmaker-lite-test/"
            "promopages-10060-article-02-20260806-v2-manifest.json",
        )
        self.assertEqual(
            pipeline.INVENTORY_MANIFEST_ROLE,
            "promopages-10060-article-02-frozen-generation-inventory",
        )
        self.assertEqual(
            pipeline.FINAL_MANIFEST_ROLE,
            "promopages-10060-article-02",
        )
        self.assertIn(
            pipeline.ARTICLE_02_BATCH_ID,
            pipeline.INVENTORY_MANIFEST_REL.parts,
        )
        self.assertIsNone(pipeline.HARD_BUDGET_CAP_USD)
        self.assertEqual(pipeline.NORMALIZED_INPUT_RETRY_ALLOWLIST, ())

    def test_article_02_cli_selects_registered_uncapped_batch(self) -> None:
        parser = pipeline.build_parser()
        args = parser.parse_args(
            [
                "--batch",
                pipeline.ARTICLE_02_BATCH_ID,
                "inventory",
                "--budget-cap-usd",
                "250",
                "--dry-run",
            ]
        )
        pipeline.activate_batch(args.batch)
        self.assertEqual(
            pipeline.parse_budget(args.budget_cap_usd),
            Decimal("250.00"),
        )

    def test_ambiguous_submit_is_quarantined_before_earlier_terminal_retry(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        earlier_terminal_source = discovery.sources[4]
        ambiguous_source = discovery.sources[7]
        ambiguous_model_id = "alibaba/wan-2.2"
        ambiguous_run_id = pipeline.primary_provider_run_id(
            ambiguous_source,
            ambiguous_model_id,
        )

        def receipt_for(entry, *, root):
            del root
            if entry.provider_run_id == ambiguous_run_id:
                return (
                    {
                        "status": "submit-unknown",
                        "provider_may_be_active": True,
                        "provider_job_id": None,
                    },
                    Path("ambiguous.json"),
                )
            status = (
                "provider-failed"
                if entry.sample.sample_id == earlier_terminal_source.sample_id
                and entry.model_id == "google/veo-3.1-lite"
                else "succeeded"
            )
            return (
                {
                    "status": status,
                    "provider_may_be_active": False,
                    "provider_job_id": None,
                },
                Path("terminal.json"),
            )

        state = pipeline.GenerationArticleState(
            article_slug=ambiguous_source.article_slug,
            accepted_outputs=31,
            terminal_accounted_outputs=32,
            provider_filtered_outputs=0,
            expected_outputs=33,
            unresolved_run_ids=(ambiguous_run_id,),
        )
        with preserved_native_state():
            pipeline.configure_native(discovery.sources, pipeline.ROOT)
            with (
                mock.patch.object(
                    pipeline,
                    "generation_article_states",
                    return_value=(state,),
                ),
                mock.patch.object(
                    pipeline,
                    "_native_run_receipt",
                    side_effect=receipt_for,
                ),
                mock.patch.object(
                    pipeline,
                    "_terminal_retry_provider_record",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_envelope",
                    return_value=None,
                ),
            ):
                pipeline._enforce_ambiguous_submit_retry_order(
                    discovery.sources,
                    ambiguous_source,
                    ambiguous_model_id,
                    root=pipeline.ROOT,
                )


class CampaignExtensionBatchTest(unittest.TestCase):
    def setUp(self) -> None:
        pipeline.activate_batch(pipeline.CAMPAIGN_EXTENSION_BATCH_ID)

    def tearDown(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)

    def test_registered_extension_has_isolated_immutable_namespaces(self) -> None:
        spec = pipeline.ACTIVE_BATCH_SPEC
        self.assertEqual(spec.batch_id, pipeline.CAMPAIGN_EXTENSION_BATCH_ID)
        self.assertEqual(spec.article_numbers, (15, 16, 17, 18))
        self.assertEqual(
            spec.ticket_config_rel.as_posix(),
            "PROMOPAGES-10060/campaigns-20260805-v1/articles.json",
        )
        self.assertEqual(
            spec.dataset_prefix,
            "PROMOPAGES-10060-campaigns-20260805-v1",
        )
        self.assertEqual(
            pipeline.FINAL_MANIFEST_REL.as_posix(),
            "clipmaker-lite-test/"
            "promopages-10060-campaigns-20260805-v1-manifest.json",
        )
        self.assertEqual(
            pipeline.FINAL_MANIFEST_ROLE,
            "promopages-10060-campaign-extension",
        )
        self.assertEqual(
            pipeline.NORMALIZED_INPUT_RETRY_ALLOWLIST,
            pipeline.CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS,
        )
        self.assertEqual(
            [target.image_id for target in pipeline.NORMALIZED_INPUT_RETRY_ALLOWLIST],
            ["05", "07", "08"],
        )
        self.assertIn(
            pipeline.CAMPAIGN_EXTENSION_BATCH_ID,
            pipeline.INVENTORY_MANIFEST_REL.parts,
        )

    def test_extension_discovery_requires_exact_ordered_articles_15_to_18(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_extension_fixture(root)
            discovery = pipeline.discover(root)
        self.assertEqual(
            [article.number for article in discovery.articles],
            ["15", "16", "17", "18"],
        )
        self.assertEqual(len(discovery.sources), 4)
        self.assertEqual(discovery.source_manifest_row_count, 4)
        for source in discovery.sources:
            self.assertTrue(
                source.image["manifest_file_path"].startswith(
                    "PROMOPAGES-10060-campaigns-20260805-v1/articles/"
                )
            )
            self.assertTrue(
                source.image["source_path"].startswith(
                    "PROMOPAGES-9857/"
                    "PROMOPAGES-10060-campaigns-20260805-v1/articles/"
                )
            )

    def test_extension_rejects_reordered_or_renumbered_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_extension_fixture(
                root,
                article_numbers=(15, 17, 16, 18),
            )
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "numbers/order differ from registered batch",
            ):
                pipeline.load_ticket_config(root)

    def test_extension_inventory_uses_separate_role_and_operator_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_extension_fixture(root)
            discovery = pipeline.discover(root)
            with (
                mock.patch.object(
                    pipeline,
                    "_inventory_contract_snapshot",
                    return_value={"contract_version": "fixture"},
                ),
                mock.patch.object(
                    pipeline,
                    "_route_snapshot",
                    return_value={"policy": "fixture"},
                ),
            ):
                inventory = pipeline.inventory_document(
                    discovery,
                    Decimal("250.00"),
                    root,
                )
        self.assertEqual(
            inventory["manifest_role"],
            "promopages-10060-campaign-extension-frozen-generation-inventory",
        )
        self.assertEqual(inventory["batch_id"], pipeline.CAMPAIGN_EXTENSION_BATCH_ID)
        self.assertEqual(inventory["article_count"], 4)
        self.assertEqual(inventory["image_count"], 4)
        self.assertEqual(inventory["expected_outputs"], 12)
        self.assertEqual(inventory["cost"]["operator_budget_cap_usd"], 250.0)
        self.assertEqual(inventory["cost"]["hard_budget_cap_usd"], 250.0)
        self.assertEqual(
            inventory["article_config"]["path"],
            "PROMOPAGES-10060/campaigns-20260805-v1/articles.json",
        )

    def test_extension_accepts_explicit_cap_above_100_but_legacy_does_not(self) -> None:
        parser = pipeline.build_parser()
        args = parser.parse_args(
            [
                "--batch",
                pipeline.CAMPAIGN_EXTENSION_BATCH_ID,
                "inventory",
                "--budget-cap-usd",
                "250",
                "--dry-run",
            ]
        )
        pipeline.activate_batch(args.batch)
        self.assertEqual(pipeline.parse_budget(args.budget_cap_usd), Decimal("250.00"))
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)
        with self.assertRaisesRegex(pipeline.PipelineError, r"hard \$100.00 cap"):
            pipeline.parse_budget(args.budget_cap_usd)

    def test_extension_normalized_retry_allowlist_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_campaign_extension_fixture(root)
            source = pipeline.discover(root).sources[0]
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "selected batch allowlist",
        ):
            pipeline.normalized_input_retry_binding(source, "alibaba/wan-2.2")

    def test_extension_commit_pinned_allowlist_is_exact_three_by_two(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        sources = {
            (source.article_slug, source.image["image_id"]): source
            for source in discovery.sources
        }
        targets = pipeline.CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS
        models = ("alibaba/wan-2.2", "alibaba/wan-2.7")
        self.assertEqual(
            [(target.article_slug, target.image_id) for target in targets],
            [
                ("18-volma-plitochnyi-klei", "05"),
                ("18-volma-plitochnyi-klei", "07"),
                ("18-volma-plitochnyi-klei", "08"),
            ],
        )

        bindings = []
        for target in targets:
            source = sources[(target.article_slug, target.image_id)]
            self.assertEqual(source.image["sha256"], target.source_sha256)
            self.assertEqual(target.model_ids, models)
            self.assertEqual(target.failure_kind, "minimum-dimension")
            self.assertIsNotNone(target.replacement)
            target_bindings = [
                pipeline.normalized_input_retry_binding(source, model_id)
                for model_id in models
            ]
            self.assertEqual(
                {binding.asset_key for binding in target_bindings},
                {target_bindings[0].asset_key},
            )
            self.assertEqual(
                {
                    binding.asset_metadata_rel
                    for binding in target_bindings
                },
                {target_bindings[0].asset_metadata_rel},
            )
            self.assertIsNone(
                pipeline._normalized_input_target_for_key(
                    target.article_slug,
                    target.image_id,
                    "google/veo-3.1-lite",
                )
            )
            bindings.extend(target_bindings)

        self.assertEqual(len(bindings), 6)
        self.assertEqual(len({binding.primary_provider_run_id for binding in bindings}), 6)
        self.assertEqual(len({binding.retry_provider_run_id for binding in bindings}), 6)
        self.assertEqual(len({binding.asset_key for binding in bindings}), 3)

    def test_extension_local_assets_match_commit_pinned_binding_metadata(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        sources = {
            (source.article_slug, source.image["image_id"]): source
            for source in discovery.sources
        }
        for target in pipeline.CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS:
            replacement = target.replacement
            self.assertIsNotNone(replacement)
            assert replacement is not None
            source = sources[(target.article_slug, target.image_id)]
            preflight = {
                "http_status": 200,
                "url": replacement.url,
                "sha256": replacement.sha256,
                "bytes": replacement.byte_size,
                "width": replacement.width,
                "height": replacement.height,
                "format": replacement.image_format,
            }
            documents = []
            for model_id in target.model_ids:
                binding = pipeline.normalized_input_retry_binding(source, model_id)
                self.assertEqual(
                    Path(replacement.repository_path).parent,
                    binding.asset_metadata_rel.parent,
                )
                normalized, transform = pipeline._commit_pinned_replacement_record(
                    binding,
                    preflight,
                    root=pipeline.ROOT,
                )
                self.assertEqual(
                    normalized["repository_path"],
                    replacement.repository_path,
                )
                self.assertEqual(normalized["sha256"], replacement.sha256)
                self.assertEqual(normalized["bytes"], replacement.byte_size)
                self.assertEqual(transform["operation"], "uniform-scale")
                documents.append(
                    pipeline._normalized_input_asset_document(
                        binding,
                        preflight,
                        root=pipeline.ROOT,
                    )
                )
            self.assertEqual(documents[0], documents[1])
            self.assertEqual(
                documents[0]["source_key"],
                {
                    "article_slug": target.article_slug,
                    "image_id": target.image_id,
                },
            )
            self.assertEqual(
                documents[0]["normalized"]["source_commit_sha"],
                replacement.url.split("/")[5],
            )

    def test_extension_commit_pinned_bindings_reject_mutations(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        sources = {
            (source.article_slug, source.image["image_id"]): source
            for source in discovery.sources
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target in pipeline.CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS:
                source = sources[(target.article_slug, target.image_id)]
                mutated_source = pipeline.Source(
                    article_number=source.article_number,
                    article_slug=source.article_slug,
                    context_path=source.context_path,
                    context_sha256=source.context_sha256,
                    image={**source.image, "sha256": "0" * 64},
                )
                for model_id in target.model_ids:
                    with self.assertRaisesRegex(
                        pipeline.PipelineError,
                        "selected batch allowlist",
                    ):
                        pipeline.normalized_input_retry_binding(
                            mutated_source,
                            model_id,
                        )

                replacement = target.replacement
                self.assertIsNotNone(replacement)
                assert replacement is not None
                local_payload = (pipeline.ROOT / replacement.repository_path).read_bytes()
                mutated_path = root / replacement.repository_path
                mutated_path.parent.mkdir(parents=True, exist_ok=True)
                mutated_path.write_bytes(local_payload[:-1] + bytes([local_payload[-1] ^ 1]))
                binding = pipeline.normalized_input_retry_binding(
                    source,
                    target.model_ids[0],
                )
                exact_preflight = {
                    "http_status": 200,
                    "url": replacement.url,
                    "sha256": replacement.sha256,
                    "bytes": replacement.byte_size,
                    "width": replacement.width,
                    "height": replacement.height,
                    "format": replacement.image_format,
                }
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "local asset differs",
                ):
                    pipeline._commit_pinned_replacement_record(
                        binding,
                        exact_preflight,
                        root=root,
                    )
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "allowlist metadata",
                ):
                    pipeline._commit_pinned_replacement_record(
                        binding,
                        {**exact_preflight, "sha256": "f" * 64},
                        root=pipeline.ROOT,
                    )

    def test_extension_retry_scan_requires_binding_specific_policy(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        sources = {
            (source.article_slug, source.image["image_id"]): source
            for source in discovery.sources
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bindings = []
            for target in pipeline.CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS:
                source = sources[(target.article_slug, target.image_id)]
                for model_id in target.model_ids:
                    binding = pipeline.normalized_input_retry_binding(source, model_id)
                    bindings.append(binding)
                    pipeline.transport.atomic_write_json(
                        root / binding.envelope_rel,
                        {
                            "schema_version": 1,
                            "manifest_role": pipeline.NORMALIZED_RETRY_MANIFEST_ROLE,
                            "ticket": pipeline.TICKET,
                            "primary_batch_id": pipeline.BATCH_ID,
                            "retry_number": pipeline.NORMALIZED_INPUT_RETRY_VERSION,
                            "logical_output_key": {
                                "article_slug": source.article_slug,
                                "image_id": source.image["image_id"],
                                "model_id": model_id,
                            },
                            "primary_attempt": {
                                "provider_run_id": binding.primary_provider_run_id,
                            },
                            "retry_attempt": {"retry_key": binding.retry_key},
                            "policy": pipeline._normalized_input_retry_policy(binding),
                        },
                    )
            documents = pipeline._known_normalized_input_retry_envelopes(root)
            self.assertEqual(len(documents), 6)
            self.assertEqual(
                {
                    document["primary_attempt"]["provider_run_id"]
                    for document in documents
                },
                {binding.primary_provider_run_id for binding in bindings},
            )

            mutated = pipeline.read_json(root / bindings[0].envelope_rel)
            mutated["policy"] = pipeline._normalized_input_retry_policy()
            pipeline.transport.atomic_write_json(
                root / bindings[0].envelope_rel,
                mutated,
            )
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "policy differs for its target",
            ):
                pipeline._known_normalized_input_retry_envelopes(root)

    def test_legacy_normalized_policy_and_sidecar_shape_are_unchanged(self) -> None:
        pipeline.activate_batch(pipeline.LEGACY_BATCH_ID)
        self.assertEqual(
            pipeline._normalized_input_retry_policy(
                target=pipeline.LEGACY_NORMALIZED_INPUT_TARGET
            ),
            {
                "explicit_operator_command_required": True,
                "automatic_retry": False,
                "maximum_new_paid_submissions": 1,
                "retry2_forbidden": True,
                "same_verified_lite_result": True,
                "same_prompt": True,
                "same_model": True,
                "request_delta_only_image_pointer": True,
                "shared_frozen_scale_1200_asset": True,
                "local_reencode": False,
                "fallback": False,
                "primary_receipt_immutable": True,
            },
        )
        generation_policy = pipeline._normalized_input_generation_policy()
        self.assertNotIn("eligible_sources", generation_policy)
        self.assertEqual(
            generation_policy,
            {
                "version": 1,
                "namespace": (
                    "clipmaker-lite-test/runs/"
                    "promopages-10060-lite-all-images-20260805-v2/"
                    "normalized-input-retries-v1"
                ),
                "shared_asset_namespace": (
                    "clipmaker-lite-test/runs/"
                    "promopages-10060-lite-all-images-20260805-v2/"
                    "normalized-input-assets-v1"
                ),
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
            },
        )

    def test_exact_extension_undersized_primaries_are_terminal_evidence(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        source = next(
            source
            for source in discovery.sources
            if source.article_slug == "18-volma-plitochnyi-klei"
            and source.image["image_id"] == "05"
        )
        self.assertEqual(
            pipeline._normalized_input_constraint(source, pipeline.ROOT),
            "minimum-dimension",
        )
        with preserved_native_state():
            pipeline.configure_native(discovery.sources, pipeline.ROOT)
            before = {
                model_id: pipeline.sha256_file(
                    pipeline.primary_artifact_paths(
                        source,
                        model_id,
                        pipeline.ROOT,
                    )["run"]
                )
                for model_id in ("alibaba/wan-2.2", "alibaba/wan-2.7")
            }
            evidence = {
                model_id: pipeline._primary_normalized_input_failure_evidence(
                    source,
                    model_id,
                    root=pipeline.ROOT,
                )
                for model_id in ("alibaba/wan-2.2", "alibaba/wan-2.7")
            }
            after = {
                model_id: pipeline.sha256_file(
                    pipeline.primary_artifact_paths(
                        source,
                        model_id,
                        pipeline.ROOT,
                    )["run"]
                )
                for model_id in ("alibaba/wan-2.2", "alibaba/wan-2.7")
            }
        self.assertEqual(before, after)
        self.assertEqual(evidence["alibaba/wan-2.2"]["status"], "provider-failed")
        self.assertEqual(
            evidence["alibaba/wan-2.2"]["recorded_status"],
            "submit-unknown",
        )
        self.assertEqual(
            evidence["alibaba/wan-2.2"]["provider_task_id"],
            "9d2d4347-7fbd-473c-adf2-cc2b7f5199c2",
        )
        self.assertEqual(
            evidence["alibaba/wan-2.7"]["recorded_status"],
            "provider-failed",
        )
        self.assertEqual(
            evidence["alibaba/wan-2.7"]["provider_job_id"],
            "PyF26u7pxzE0fNJ0DGgB",
        )

    def _supersede_target(self) -> pipeline.Source:
        return next(
            source
            for source in pipeline.discover(pipeline.ROOT).sources
            if source.article_slug == "18-volma-plitochnyi-klei"
            and source.image["image_id"] == "07"
        )

    def test_active_wan27_supersede_has_one_deterministic_isolated_identity(
        self,
    ) -> None:
        source = self._supersede_target()
        normalized = pipeline.normalized_input_retry_binding(
            source,
            "alibaba/wan-2.7",
        )
        first = pipeline.normalized_input_supersede_binding(
            source,
            "alibaba/wan-2.7",
        )
        second = pipeline.normalized_input_supersede_binding(
            source,
            "alibaba/wan-2.7",
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first.normalized_retry_provider_run_id,
            normalized.retry_provider_run_id,
        )
        self.assertNotEqual(
            first.supersede_provider_run_id,
            normalized.retry_provider_run_id,
        )
        self.assertEqual(
            first.supersede_key,
            hashlib.sha256(
                (
                    "normalized-input-supersede-v1:"
                    f"{normalized.retry_provider_run_id}"
                ).encode("utf-8")
            ).hexdigest()[:20],
        )
        self.assertEqual(
            first.directory_rel,
            normalized.directory_rel / "superseding-attempt-v1",
        )
        self.assertEqual(first.envelope_rel, first.directory_rel / "supersede.json")

        # The operator authorized only the exact stuck image-07 Wan 2.7 job,
        # not a reusable escape hatch for another model or normalized target.
        for image_id, model_id in (
            ("07", "alibaba/wan-2.2"),
            ("05", "alibaba/wan-2.7"),
            ("08", "alibaba/wan-2.7"),
        ):
            other = next(
                candidate
                for candidate in pipeline.discover(pipeline.ROOT).sources
                if candidate.article_slug == "18-volma-plitochnyi-klei"
                and candidate.image["image_id"] == image_id
            )
            with self.subTest(image_id=image_id, model_id=model_id):
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "supersed|operator-authorized|allowlist",
                ):
                    pipeline.normalized_input_supersede_binding(other, model_id)

    def test_supersede_is_a_separate_conservative_paid_reservation(self) -> None:
        discovery = pipeline.discover(pipeline.ROOT)
        inventory = pipeline.inventory_document(
            discovery,
            Decimal("1000.00"),
            pipeline.ROOT,
        )
        before = pipeline.aggregate_retry_budget_metadata(
            inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
            normalized_input_retry_reservations=4,
            normalized_input_supersede_reservations=0,
        )
        after = pipeline.aggregate_retry_budget_metadata(
            inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
            normalized_input_retry_reservations=4,
            normalized_input_supersede_reservations=1,
        )

        self.assertEqual(after["normalized_input_supersede_reservations"], 1)
        self.assertEqual(
            after["normalized_input_supersede_accounting_cost_usd"],
            0.35,
        )
        self.assertEqual(
            Decimal(str(after["maximum_estimated_cost_usd"]))
            - Decimal(str(before["maximum_estimated_cost_usd"])),
            Decimal("0.35"),
        )
        self.assertEqual(
            after["maximum_paid_submissions"],
            before["maximum_paid_submissions"] + 1,
        )
        self.assertEqual(
            after["total_retry_reservations"],
            before["total_retry_reservations"] + 1,
        )

    def test_supersede_scanner_allows_exactly_one_nested_reservation(self) -> None:
        source = self._supersede_target()
        normalized = pipeline.normalized_input_retry_binding(
            source,
            "alibaba/wan-2.7",
        )
        binding = pipeline.normalized_input_supersede_binding(
            source,
            "alibaba/wan-2.7",
        )
        document = {
            "schema_version": 1,
            "manifest_role": pipeline.NORMALIZED_INPUT_SUPERSEDE_MANIFEST_ROLE,
            "ticket": pipeline.TICKET,
            "primary_batch_id": pipeline.BATCH_ID,
            "supersede_number": pipeline.NORMALIZED_INPUT_SUPERSEDE_VERSION,
            "normalized_retry": {
                "provider_run_id": normalized.retry_provider_run_id,
            },
            "superseding_attempt": {
                "provider_run_id": binding.supersede_provider_run_id,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline.transport.atomic_write_json(
                root / binding.envelope_rel,
                document,
            )
            self.assertEqual(
                pipeline._known_normalized_input_supersede_envelopes(root),
                (document,),
            )

            second = (
                root
                / pipeline.NORMALIZED_INPUT_RETRY_NAMESPACE_REL
                / "another-normalized-retry"
                / pipeline.NORMALIZED_INPUT_SUPERSEDE_DIRECTORY_NAME
                / "supersede.json"
            )
            pipeline.transport.atomic_write_json(second, document)
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "More than one normalized-input supersede",
            ):
                pipeline._known_normalized_input_supersede_envelopes(root)

    def test_supersede_envelope_preserves_the_active_attempt_and_exact_request(
        self,
    ) -> None:
        source = self._supersede_target()
        model_id = "alibaba/wan-2.7"
        normalized = pipeline.normalized_input_retry_binding(source, model_id)
        binding = pipeline.normalized_input_supersede_binding(source, model_id)
        replacement = next(
            target.replacement
            for target in pipeline.CAMPAIGN_EXTENSION_NORMALIZED_INPUT_TARGETS
            if target.article_slug == source.article_slug
            and target.image_id == source.image["image_id"]
        )
        self.assertIsNotNone(replacement)
        assert replacement is not None
        normalized_envelope = pipeline.read_json(
            pipeline.ROOT / normalized.envelope_rel
        )
        active_run = pipeline.read_json(pipeline.ROOT / normalized.run_rel)
        active_run_sha256 = pipeline.sha256_file(
            pipeline.ROOT / normalized.run_rel
        )
        normalized_envelope_sha256 = pipeline.sha256_file(
            pipeline.ROOT / normalized.envelope_rel
        )
        normalized_prompt_sha256 = pipeline.sha256_file(
            pipeline.ROOT / normalized.prompt_rel
        )
        request = normalized_envelope["retry_attempt"]["request"]
        request_sha256 = normalized_envelope["retry_attempt"]["request_sha256"]
        self.assertEqual(active_run["provider_job_id"], "novcFDcwbuZkgtrmgQIY")
        self.assertEqual(active_run["status"], "running")
        self.assertTrue(active_run["provider_may_be_active"])
        self.assertEqual(active_run["request"], request)
        self.assertEqual(active_run["request_sha256"], request_sha256)
        inventory = pipeline.inventory_document(
            pipeline.discover(pipeline.ROOT),
            Decimal("1000.00"),
            pipeline.ROOT,
        )
        aggregate_cost = pipeline.aggregate_retry_budget_metadata(
            inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
            normalized_input_retry_reservations=4,
            normalized_input_supersede_reservations=1,
        )
        frozen_envelope = json.loads(json.dumps(normalized_envelope))
        frozen_run = json.loads(json.dumps(active_run))

        document = pipeline._normalized_input_supersede_envelope_document(
            binding,
            normalized_envelope,
            active_run,
            active_run_sha256,
            aggregate_cost,
        )

        self.assertEqual(normalized_envelope, frozen_envelope)
        self.assertEqual(active_run, frozen_run)
        self.assertEqual(
            pipeline.sha256_file(pipeline.ROOT / normalized.run_rel),
            active_run_sha256,
        )
        self.assertEqual(
            pipeline.sha256_file(pipeline.ROOT / normalized.envelope_rel),
            normalized_envelope_sha256,
        )
        self.assertEqual(
            pipeline.sha256_file(pipeline.ROOT / normalized.prompt_rel),
            normalized_prompt_sha256,
        )
        self.assertEqual(
            document["manifest_role"],
            pipeline.NORMALIZED_INPUT_SUPERSEDE_MANIFEST_ROLE,
        )
        self.assertEqual(document["supersede_number"], 1)
        self.assertEqual(
            document["superseded_attempt"]["provider_run_id"],
            normalized.retry_provider_run_id,
        )
        self.assertEqual(
            document["superseded_attempt"]["provider_job_id"],
            "novcFDcwbuZkgtrmgQIY",
        )
        self.assertEqual(
            document["superseded_attempt"]["run_sha256"],
            active_run_sha256,
        )
        superseding = document["superseding_attempt"]
        self.assertEqual(
            superseding["provider_run_id"],
            binding.supersede_provider_run_id,
        )
        self.assertEqual(superseding["model_id"], model_id)
        self.assertEqual(superseding["lite_run_id"], source.planning_run_id)
        self.assertEqual(superseding["source_url"], replacement.url)
        self.assertEqual(superseding["source_sha256"], replacement.sha256)
        self.assertEqual(superseding["request"], request)
        self.assertEqual(superseding["request_sha256"], request_sha256)
        self.assertEqual(document["cost"], aggregate_cost)
        self.assertEqual(
            document["policy"]["maximum_new_paid_submissions"],
            1,
        )
        self.assertTrue(document["policy"]["superseded_receipt_immutable"])
        self.assertTrue(
            document["policy"]["duplicate_billing_risk_acknowledged"]
        )
        self.assertTrue(document["policy"]["same_request"])
        self.assertTrue(document["policy"]["same_route"])

        # A terminal or request-mutated receipt is not the job the operator
        # authorized and must fail before a new reservation can be authored.
        for mutation in (
            {"provider_may_be_active": False, "status": "provider-failed"},
            {"request": {**request, "seed": 1}},
            {"provider_job_id": None},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(pipeline.PipelineError):
                    pipeline._normalized_input_supersede_envelope_document(
                        binding,
                        normalized_envelope,
                        {**active_run, **mutation},
                        active_run_sha256,
                        aggregate_cost,
                    )

    def test_normalized_retry_ledgers_straddle_supersede_reservation(self) -> None:
        """Pre-supersede snapshots and post-supersede ledgers both validate."""

        discovery = pipeline.discover(pipeline.ROOT)
        by_image = {
            source.image["image_id"]: source
            for source in discovery.sources
            if source.article_slug == "18-volma-plitochnyi-klei"
        }
        with preserved_native_state():
            pipeline.configure_native(discovery.sources, pipeline.ROOT)
            pre_supersede = pipeline._normalized_input_retry_envelope(
                by_image["07"],
                "alibaba/wan-2.7",
                root=pipeline.ROOT,
            )
            post_supersede = pipeline._normalized_input_retry_envelope(
                by_image["08"],
                "alibaba/wan-2.2",
                root=pipeline.ROOT,
            )

        self.assertIsNotNone(pre_supersede)
        self.assertIsNotNone(post_supersede)
        assert pre_supersede is not None
        assert post_supersede is not None
        old_cost = pre_supersede[1]["cost"]
        new_cost = post_supersede[1]["cost"]
        self.assertNotIn("normalized_input_supersede_reservations", old_cost)
        self.assertEqual(new_cost["normalized_input_supersede_version"], 1)
        self.assertEqual(
            new_cost["normalized_input_supersede_accounting_cost_usd"],
            0.35,
        )
        self.assertEqual(new_cost["normalized_input_supersede_reservations"], 1)
        self.assertEqual(
            new_cost["total_retry_reservations"],
            new_cost["terminal_retry_reservations"]
            + new_cost["ambiguous_submit_retry_reservations"]
            + new_cost["normalized_input_retry_reservations"]
            + new_cost["normalized_input_supersede_reservations"],
        )

    def test_supersede_requires_explicit_operator_authorization_before_io(
        self,
    ) -> None:
        source = self._supersede_target()
        normalized = pipeline.normalized_input_retry_binding(
            source,
            "alibaba/wan-2.7",
        )
        discovery = pipeline.discover(pipeline.ROOT)
        inventory = pipeline.inventory_document(
            discovery,
            Decimal("1000.00"),
            pipeline.ROOT,
        )
        parser = pipeline.build_parser()
        without_flag = parser.parse_args(
            [
                "--batch",
                pipeline.CAMPAIGN_EXTENSION_BATCH_ID,
                "supersede-normalized-input",
                "--provider-run-id",
                normalized.retry_provider_run_id,
                "--dry-run",
            ]
        )
        with_flag = parser.parse_args(
            [
                "--batch",
                pipeline.CAMPAIGN_EXTENSION_BATCH_ID,
                "supersede-normalized-input",
                "--provider-run-id",
                normalized.retry_provider_run_id,
                "--operator-authorized-active-job",
                "--dry-run",
            ]
        )
        self.assertFalse(without_flag.operator_authorized_active_job)
        self.assertTrue(with_flag.operator_authorized_active_job)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(pipeline, "configure_native") as configure,
                mock.patch.object(
                    pipeline.transport,
                    "atomic_write_json",
                    side_effect=AssertionError("authorization failure wrote a file"),
                ) as writer,
                mock.patch.object(
                    pipeline.native,
                    "main",
                    side_effect=AssertionError("authorization failure called provider"),
                ) as provider_main,
            ):
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "operator.*authoriz|authorization",
                ):
                    pipeline.run_normalized_input_supersede(
                        discovery.sources,
                        inventory,
                        normalized_retry_provider_run_id_value=(
                            normalized.retry_provider_run_id
                        ),
                        root=root,
                        dry_run=False,
                        operator_authorized=False,
                        allow_external_processing=True,
                        timeout=901,
                        poll_interval=7.5,
                    )
        configure.assert_not_called()
        writer.assert_not_called()
        provider_main.assert_not_called()

    def test_default_cli_selection_preserves_legacy_batch(self) -> None:
        args = pipeline.build_parser().parse_args(["inventory", "--dry-run"])
        self.assertEqual(args.batch, pipeline.LEGACY_BATCH_ID)
        pipeline.activate_batch(args.batch)
        self.assertEqual(pipeline.BATCH_ID, pipeline.LEGACY_BATCH_ID)
        self.assertEqual(pipeline.HARD_BUDGET_CAP_USD, Decimal("100.00"))
        self.assertEqual(
            pipeline.FINAL_MANIFEST_REL.as_posix(),
            "clipmaker-lite-test/promopages-10060-manifest.json",
        )


class Promopages10060PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.discovery = pipeline.discover(pipeline.ROOT)
        cls.inventory = pipeline.inventory_document(
            cls.discovery, pipeline.HARD_BUDGET_CAP_USD, pipeline.ROOT
        )

    def test_real_inventory_is_13_nonrenumbered_articles_and_276_outputs(self) -> None:
        discovery = self.discovery
        self.assertEqual(len(discovery.articles), 13)
        self.assertEqual(len(discovery.sources), 92)
        self.assertEqual(discovery.source_manifest_row_count, 92)
        self.assertEqual(
            [article.number for article in discovery.articles],
            ["01", *[f"{number:02d}" for number in range(3, 15)]],
        )
        self.assertEqual(len(discovery.unavailable_articles), 1)
        unavailable = discovery.unavailable_articles[0]
        self.assertEqual(unavailable["article_number"], "02")
        self.assertEqual(unavailable["article_slug"], "02-level-rabotaiu-v-level")
        self.assertEqual(unavailable["status"], "source-unavailable")
        self.assertIn("404", unavailable["error"])

        self.assertEqual(self.inventory["article_count"], 13)
        self.assertEqual(self.inventory["image_count"], 92)
        self.assertEqual(self.inventory["expected_outputs"], 276)
        self.assertEqual(self.inventory["models"], list(pipeline.MODEL_IDS))
        self.assertEqual(
            sum(article["image_count"] for article in self.inventory["articles"]),
            92,
        )
        self.assertIn("including the cover", self.inventory["selection_rule"])
        self.assertIn("original block order", self.inventory["selection_rule"])
        self.assertEqual(
            pipeline.BATCH_ID,
            "promopages-10060-lite-all-images-20260805-v2",
        )

    def test_discovery_includes_every_cover_and_body_image_in_block_order(self) -> None:
        expected_counts = {
            "01": 4,
            "03": 9,
            "04": 8,
            "05": 7,
            "06": 6,
            "07": 9,
            "08": 8,
            "09": 5,
            "10": 8,
            "11": 4,
            "12": 10,
            "13": 8,
            "14": 6,
        }
        expected_flat_order = []
        for article in self.discovery.articles:
            self.assertEqual(article.cover_image["role"], "cover")
            self.assertEqual(article.cover_image["image_id"], "01")
            self.assertEqual(len(article.images), expected_counts[article.number])
            self.assertEqual(
                [image["image_id"] for image in article.images],
                [f"{index:02d}" for index in range(1, len(article.images) + 1)],
            )
            self.assertEqual(
                [image["order"] for image in article.images],
                list(range(1, len(article.images) + 1)),
            )
            for image in article.images:
                expected_flat_order.append((article.slug, image["image_id"]))
                self.assertTrue(
                    image["manifest_file_path"].startswith(
                        f"PROMOPAGES-10060/articles/{article.slug}/"
                    )
                )
                self.assertEqual(
                    image["source_path"],
                    f"PROMOPAGES-9857/{image['manifest_file_path']}",
                )

        actual_flat_order = [
            (source.article_slug, source.image["image_id"])
            for source in self.discovery.sources
        ]
        self.assertEqual(actual_flat_order, expected_flat_order)
        self.assertEqual(self.discovery.sources[0].image["role"], "cover")
        self.assertEqual(self.discovery.sources[-1].article_number, "14")
        self.assertEqual(self.discovery.sources[-1].image["image_id"], "06")

    def test_budget_reserves_the_complete_matrix_below_the_operator_cap(self) -> None:
        cost = self.inventory["cost"]
        self.assertEqual(cost["operator_budget_cap_usd"], 100.0)
        self.assertEqual(cost["hard_budget_cap_usd"], 100.0)
        self.assertEqual(
            cost["accounting_cost_per_output_usd"],
            {model_id: 0.35 for model_id in pipeline.MODEL_IDS},
        )
        self.assertEqual(cost["accounting_cost_per_image_usd"], 1.05)
        self.assertEqual(cost["maximum_estimated_cost_usd"], 96.6)
        self.assertEqual(cost["estimated_headroom_usd"], 3.4)
        self.assertEqual(cost["planned_paid_submissions"], 276)
        self.assertEqual(cost["maximum_paid_submissions"], 276)
        self.assertEqual(cost["maximum_paid_submissions_per_job"], 1)
        self.assertFalse(cost["automatic_paid_retries"])
        self.assertFalse(cost["actual_billing_available"])
        self.assertIn("ticket-config order", cost["enforcement"])
        self.assertIn("no live price or model discovery", cost["pricing_basis"])
        with self.assertRaises(pipeline.PipelineError):
            pipeline.parse_budget("100.01")
        with self.assertRaisesRegex(
            pipeline.PipelineError, "Estimated full-matrix cost"
        ):
            pipeline.cost_metadata("96.59", 276)

    def test_terminal_retry_budget_counts_every_reservation_under_100(self) -> None:
        nine = pipeline.terminal_retry_budget_metadata(self.inventory, 9)
        self.assertEqual(nine["terminal_retry_reservations"], 9)
        self.assertEqual(nine["maximum_estimated_cost_usd"], 99.75)
        self.assertEqual(nine["estimated_headroom_usd"], 0.25)
        self.assertEqual(nine["maximum_paid_submissions"], 285)
        self.assertEqual(
            nine["maximum_new_paid_submissions_per_failed_output"], 1
        )
        self.assertFalse(nine["automatic_paid_retries"])
        with self.assertRaisesRegex(
            pipeline.PipelineError, r"above the \$100.00 cap"
        ):
            pipeline.terminal_retry_budget_metadata(self.inventory, 10)

    def test_aggregate_budget_counts_terminal_and_ambiguous_reservations(self) -> None:
        cost = pipeline.aggregate_retry_budget_metadata(
            self.inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
        )
        self.assertEqual(cost["terminal_retry_reservations"], 2)
        self.assertEqual(cost["ambiguous_submit_retry_reservations"], 1)
        self.assertEqual(cost["total_retry_reservations"], 3)
        self.assertEqual(cost["maximum_estimated_cost_usd"], 97.65)
        self.assertEqual(cost["maximum_paid_submissions"], 279)
        self.assertEqual(cost["estimated_headroom_usd"], 2.35)
        self.assertEqual(
            cost["ambiguous_submit_retry_accounting_cost_usd"],
            0.35,
        )
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            r"above the \$100.00 cap",
        ):
            pipeline.aggregate_retry_budget_metadata(
                self.inventory,
                terminal_retry_reservations=2,
                ambiguous_submit_retry_reservations=8,
            )

    def test_normalized_input_budget_reaches_exact_98_35_envelope(self) -> None:
        cost = pipeline.aggregate_retry_budget_metadata(
            self.inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
            normalized_input_retry_reservations=2,
        )
        self.assertEqual(cost["normalized_input_retry_reservations"], 2)
        self.assertEqual(cost["total_retry_reservations"], 5)
        self.assertEqual(cost["maximum_estimated_cost_usd"], 98.35)
        self.assertEqual(cost["estimated_headroom_usd"], 1.65)
        self.assertEqual(cost["maximum_paid_submissions"], 281)
        self.assertEqual(
            cost["normalized_input_retry_accounting_cost_usd"],
            0.35,
        )

    def test_terminal_retry_identity_is_deterministic_and_separate(self) -> None:
        source = self.discovery.sources[0]
        model_id = "google/veo-3.1-lite"
        first = pipeline.terminal_retry_binding(source, model_id)
        second = pipeline.terminal_retry_binding(source, model_id)
        self.assertEqual(first, second)
        self.assertNotEqual(first.retry_batch_id, pipeline.BATCH_ID)
        self.assertNotEqual(
            first.retry_provider_run_id, first.primary_provider_run_id
        )
        self.assertTrue(
            first.envelope_rel.is_relative_to(
                pipeline.TERMINAL_RETRY_NAMESPACE_REL
            )
        )
        self.assertIn("terminal-provider-retries-v1", first.envelope_rel.parts)

    def test_ambiguous_retry_identity_is_deterministic_and_model_isolated(self) -> None:
        source = self.discovery.sources[0]
        bindings = []
        for model_id in pipeline.MODEL_IDS:
            first = pipeline.ambiguous_submit_retry_binding(source, model_id)
            second = pipeline.ambiguous_submit_retry_binding(source, model_id)
            self.assertEqual(first, second)
            self.assertNotEqual(first.retry_batch_id, pipeline.BATCH_ID)
            self.assertNotEqual(
                first.retry_provider_run_id,
                first.primary_provider_run_id,
            )
            self.assertTrue(
                first.envelope_rel.is_relative_to(
                    pipeline.AMBIGUOUS_SUBMIT_RETRY_NAMESPACE_REL
                )
            )
            self.assertIn(
                "ambiguous-submit-retries-v1",
                first.envelope_rel.parts,
            )
            bindings.append(first)
        self.assertEqual(len({binding.retry_key for binding in bindings}), 3)
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "unsupported",
        ):
            pipeline.ambiguous_submit_retry_binding(
                source,
                "unsupported/model",
            )

    def test_normalized_retry_identity_is_model_isolated_but_asset_is_shared(self) -> None:
        source = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        wan22 = pipeline.normalized_input_retry_binding(
            source,
            "alibaba/wan-2.2",
        )
        wan27 = pipeline.normalized_input_retry_binding(
            source,
            "alibaba/wan-2.7",
        )
        self.assertNotEqual(wan22.retry_key, wan27.retry_key)
        self.assertNotEqual(wan22.retry_batch_id, wan27.retry_batch_id)
        self.assertNotEqual(wan22.retry_provider_run_id, wan27.retry_provider_run_id)
        self.assertEqual(wan22.asset_key, wan27.asset_key)
        self.assertEqual(wan22.asset_metadata_rel, wan27.asset_metadata_rel)
        self.assertEqual(
            pipeline._normalized_input_page_variant_url(source, pipeline.ROOT),
            "https://avatars.mds.yandex.net/get-promoarticles/6165752/"
            "pub_6a59e32a3a302a69aec403c2_6a5a036cb1afef7284d68d17/"
            "scale_1200",
        )
        with self.assertRaisesRegex(pipeline.PipelineError, "restricted to exact"):
            pipeline.normalized_input_retry_binding(
                self.discovery.sources[0],
                "alibaba/wan-2.2",
            )

    def test_exact_oversize_primaries_are_semantically_terminal_and_immutable(self) -> None:
        source = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        with preserved_native_state():
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            before = {
                model_id: pipeline.sha256_file(
                    pipeline.primary_artifact_paths(
                        source,
                        model_id,
                        pipeline.ROOT,
                    )["run"]
                )
                for model_id in pipeline.NORMALIZED_INPUT_ELIGIBLE_MODELS
            }
            wan22 = pipeline._primary_normalized_input_failure_evidence(
                source,
                "alibaba/wan-2.2",
                root=pipeline.ROOT,
            )
            wan27 = pipeline._primary_normalized_input_failure_evidence(
                source,
                "alibaba/wan-2.7",
                root=pipeline.ROOT,
            )
            after = {
                model_id: pipeline.sha256_file(
                    pipeline.primary_artifact_paths(
                        source,
                        model_id,
                        pipeline.ROOT,
                    )["run"]
                )
                for model_id in pipeline.NORMALIZED_INPUT_ELIGIBLE_MODELS
            }
        self.assertEqual(before, after)
        self.assertEqual(wan22["status"], "provider-failed")
        self.assertEqual(wan22["recorded_status"], "submit-unknown")
        self.assertFalse(wan22["provider_may_be_active"])
        self.assertTrue(wan22["recorded_provider_may_be_active"])
        self.assertEqual(
            wan22["provider_task_id"],
            "3cc24b8d-51c7-43be-a504-6d550dd9c368",
        )
        self.assertEqual(wan27["status"], "provider-failed")
        self.assertEqual(wan27["recorded_status"], "provider-failed")
        self.assertEqual(wan27["provider_job_id"], "xLTwgTdOaEs6RRiWCpyn")

    def test_normalized_retry_changes_exactly_one_model_specific_image_leaf(self) -> None:
        original_url = "https://avatars.mds.yandex.net/example/orig"
        normalized_url = "https://avatars.mds.yandex.net/example/scale_1200"
        cases = (
            (
                "alibaba/wan-2.2",
                {"input": {"image": original_url, "prompt": "same"}},
                "/input/image",
            ),
            (
                "alibaba/wan-2.7",
                {
                    "prompt": "same",
                    "frame_images": [
                        {"image_url": {"url": original_url}, "frame_type": "first_frame"}
                    ],
                },
                "/frame_images/0/image_url/url",
            ),
        )
        for model_id, primary, expected_pointer in cases:
            with self.subTest(model_id=model_id):
                retry, delta = pipeline._normalized_retry_request(
                    primary,
                    model_id,
                    original_url,
                    normalized_url,
                )
                self.assertEqual(delta["json_pointer"], expected_pointer)
                self.assertEqual(delta["changed_leaf_count"], 1)
                self.assertEqual(
                    pipeline._request_leaf_differences(primary, retry),
                    [(expected_pointer, original_url, normalized_url)],
                )

    def test_both_exact_normalized_dry_runs_never_fetch_write_or_call_provider(self) -> None:
        source = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        before = {
            model_id: pipeline.sha256_file(
                pipeline.primary_artifact_paths(source, model_id, pipeline.ROOT)["run"]
            )
            for model_id in pipeline.NORMALIZED_INPUT_ELIGIBLE_MODELS
        }
        with (
            preserved_native_state(),
            mock.patch.object(
                pipeline,
                "preflight_normalized_input_asset",
                side_effect=AssertionError("dry-run fetched MDS"),
            ) as preflight,
            mock.patch.object(
                pipeline.transport,
                "atomic_write_json",
                side_effect=AssertionError("dry-run wrote a file"),
            ) as writer,
            mock.patch.object(
                pipeline.native,
                "main",
                side_effect=AssertionError("dry-run called a provider runner"),
            ) as provider_main,
        ):
            results = [
                pipeline.run_normalized_input_retry(
                    self.discovery.sources,
                    self.inventory,
                    primary_provider_run_id_value=pipeline.primary_provider_run_id(
                        source,
                        model_id,
                    ),
                    root=pipeline.ROOT,
                    dry_run=True,
                    allow_external_processing=False,
                    timeout=901,
                    poll_interval=7.5,
                )
                for model_id in pipeline.NORMALIZED_INPUT_ELIGIBLE_MODELS
            ]
        after = {
            model_id: pipeline.sha256_file(
                pipeline.primary_artifact_paths(source, model_id, pipeline.ROOT)["run"]
            )
            for model_id in pipeline.NORMALIZED_INPUT_ELIGIBLE_MODELS
        }
        self.assertEqual(results, [0, 0])
        self.assertEqual(before, after)
        preflight.assert_not_called()
        writer.assert_not_called()
        provider_main.assert_not_called()

    def test_existing_first_normalized_envelope_admits_second_at_98_35(self) -> None:
        source = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        first = pipeline.normalized_input_retry_binding(
            source,
            "alibaba/wan-2.2",
        )
        second_model = "alibaba/wan-2.7"
        second_primary_id = pipeline.primary_provider_run_id(source, second_model)
        normalized_url = source.image["orig_url"].removesuffix("/orig") + "/scale_1200"
        first_document = {
            "schema_version": 1,
            "manifest_role": "promopages-10060-normalized-input-retry",
            "ticket": pipeline.TICKET,
            "primary_batch_id": pipeline.BATCH_ID,
            "retry_number": pipeline.NORMALIZED_INPUT_RETRY_VERSION,
            "logical_output_key": {
                "article_slug": source.article_slug,
                "image_id": source.image["image_id"],
                "model_id": "alibaba/wan-2.2",
            },
            "primary_attempt": {
                "provider_run_id": first.primary_provider_run_id,
            },
            "retry_attempt": {"retry_key": first.retry_key},
            "policy": pipeline._normalized_input_retry_policy(),
        }
        primary = {
            "provider_run_id": second_primary_id,
            "request": {
                "model": second_model,
                "frame_images": [
                    {
                        "image_url": {"url": source.image["orig_url"]},
                    }
                ],
            },
        }
        terminal_documents = (
            {"primary_attempt": {"provider_run_id": "terminal-primary-a"}},
            {"primary_attempt": {"provider_run_id": "terminal-primary-b"}},
        )
        ambiguous_documents = (
            {"primary_attempt": {"provider_run_id": "ambiguous-primary-a"}},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline.transport.atomic_write_json(
                root / first.envelope_rel,
                first_document,
            )
            known = pipeline._known_normalized_input_retry_envelopes(root)
            output = io.StringIO()
            with (
                mock.patch.object(pipeline, "configure_native"),
                mock.patch.object(
                    pipeline,
                    "resolve_primary_retry_target",
                    return_value=(source, second_model),
                ),
                mock.patch.object(
                    pipeline,
                    "_terminal_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_primary_normalized_input_failure_evidence",
                    return_value=primary,
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_page_variant_url",
                    return_value=normalized_url,
                ),
                mock.patch.object(
                    pipeline,
                    "_known_retry_envelopes",
                    return_value=terminal_documents,
                ),
                mock.patch.object(
                    pipeline,
                    "_known_ambiguous_submit_retry_envelopes",
                    return_value=ambiguous_documents,
                ),
                mock.patch.object(
                    pipeline,
                    "preflight_normalized_input_asset",
                    side_effect=AssertionError("dry-run fetched MDS"),
                ) as preflight,
                mock.patch.object(
                    pipeline.transport,
                    "atomic_write_json",
                    side_effect=AssertionError("dry-run wrote a file"),
                ) as writer,
                mock.patch.object(
                    pipeline.native,
                    "main",
                    side_effect=AssertionError("dry-run called provider runner"),
                ) as provider_main,
                redirect_stdout(output),
            ):
                result = pipeline.run_normalized_input_retry(
                    self.discovery.sources,
                    self.inventory,
                    primary_provider_run_id_value=second_primary_id,
                    root=root,
                    dry_run=True,
                    allow_external_processing=False,
                    timeout=901,
                    poll_interval=7.5,
                )
        self.assertEqual(result, 0)
        self.assertEqual(len(known), 1)
        self.assertEqual(
            known[0]["logical_output_key"],
            first_document["logical_output_key"],
        )
        self.assertIn("would-preflight-and-reserve", output.getvalue())
        self.assertIn("aggregate maximum=$98.35", output.getvalue())
        preflight.assert_not_called()
        writer.assert_not_called()
        provider_main.assert_not_called()

    def test_exhausted_normalized_retry_is_audited_provider_unavailable(self) -> None:
        source = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        model_id = "alibaba/wan-2.7"
        binding = pipeline.normalized_input_retry_binding(source, model_id)
        original = {
            "url": source.image["orig_url"],
            "path": source.image["source_path"],
            "sha256": source.image["sha256"],
            "bytes": 23_472_383,
            "width": 5445,
            "height": 3635,
        }
        normalized = {
            "http_status": 200,
            "url": source.image["orig_url"].removesuffix("/orig") + "/scale_1200",
            "sha256": "9" * 64,
            "bytes": 345_678,
            "width": 1200,
            "height": 801,
            "format": "JPEG",
        }
        primary_request = {
            "model": model_id,
            "prompt": "same prompt",
            "frame_images": [
                {
                    "type": "image_url",
                    "image_url": {"url": original["url"]},
                    "frame_type": "first_frame",
                }
            ],
        }
        shared_prompt = {
            "ticket": pipeline.TICKET,
            "agent_id": pipeline.AGENT_ID,
            "lite_run_id": source.planning_run_id,
            "model_id": model_id,
            "source": {
                "path": source.image["source_path"],
                "sha256": source.image["sha256"],
            },
            "structured_intent": {"editorial_meaning": "same"},
            "prompt": {"positive": "same prompt", "negative": None},
            "runtime": {"duration_seconds": 5},
            "lite_result": {"path": "result.json", "sha256": "a" * 64},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary_paths = pipeline.primary_artifact_paths(source, model_id, root)
            primary_paths["directory"].mkdir(parents=True)
            primary_prompt = {
                **shared_prompt,
                "batch_id": pipeline.BATCH_ID,
                "provider_run_id": binding.primary_provider_run_id,
            }
            pipeline.transport.atomic_write_json(
                primary_paths["prompt"],
                primary_prompt,
            )
            pipeline.transport.atomic_write_json(
                primary_paths["run"],
                {"request": primary_request, "status": "provider-failed"},
            )
            primary = {
                "provider_run_id": binding.primary_provider_run_id,
                "provider_job_id": "primary-job",
                "provider_task_id": None,
                "status": "provider-failed",
                "recorded_status": "provider-failed",
                "provider_may_be_active": False,
                "recorded_provider_may_be_active": False,
                "recorded_provider_job_id": "primary-job",
                "submitted_at": "2026-08-05T00:00:00Z",
                "completed_at": "2026-08-05T00:01:00Z",
                "error": "exact oversize primary failure",
                "run_path": pipeline.relative(primary_paths["run"], root),
                "run_sha256": pipeline.sha256_file(primary_paths["run"]),
                "prompt_path": pipeline.relative(primary_paths["prompt"], root),
                "prompt_sha256": pipeline.sha256_file(primary_paths["prompt"]),
                "request": primary_request,
                "request_sha256": "b" * 64,
                "source": original,
            }
            with (
                mock.patch.object(
                    pipeline,
                    "_normalized_input_original_source",
                    return_value=original,
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_page_variant_url",
                    return_value=normalized["url"],
                ),
            ):
                asset = pipeline._normalized_input_asset_document(
                    binding,
                    normalized,
                    root=root,
                )
                pipeline.transport.atomic_write_json(
                    root / binding.asset_metadata_rel,
                    asset,
                )
                asset_sha256 = pipeline.sha256_file(root / binding.asset_metadata_rel)
                envelope = pipeline._normalized_input_retry_envelope_document(
                    binding,
                    primary,
                    asset,
                    asset_sha256,
                    pipeline.aggregate_retry_budget_metadata(
                        self.inventory,
                        terminal_retry_reservations=2,
                        ambiguous_submit_retry_reservations=1,
                        normalized_input_retry_reservations=1,
                    ),
                )
                pipeline.transport.atomic_write_json(
                    root / binding.envelope_rel,
                    envelope,
                )
                pipeline.transport.atomic_write_json(
                    root / binding.prompt_rel,
                    {
                        **shared_prompt,
                        "batch_id": binding.retry_batch_id,
                        "provider_run_id": binding.retry_provider_run_id,
                    },
                )
                retry_request = envelope["retry_attempt"]["request"]
                pipeline.transport.atomic_write_json(
                    root / binding.run_rel,
                    {
                        "ticket": pipeline.TICKET,
                        "batch_id": binding.retry_batch_id,
                        "agent_id": pipeline.AGENT_ID,
                        "lite_run_id": source.planning_run_id,
                        "provider_run_id": binding.retry_provider_run_id,
                        "model_id": model_id,
                        "adapter": "eliza-openrouter",
                        "status": "provider-failed",
                        "provider_may_be_active": False,
                        "provider_job_id": "retry-job",
                        "submitted_at": "2026-08-05T00:02:00Z",
                        "completed_at": "2026-08-05T00:03:00Z",
                        "request": retry_request,
                        "request_sha256": envelope["retry_attempt"]["request_sha256"],
                        "request_fingerprint_version": (
                            pipeline.transport.REQUEST_FINGERPRINT_VERSION
                        ),
                        "media": None,
                        "contract_check": None,
                        "error": "normalized retry terminal failure",
                    },
                )
                provider = pipeline._normalized_input_retry_provider_record(
                    source,
                    model_id,
                    root=root,
                )
                output = pipeline._output_record(
                    article=next(
                        article
                        for article in self.discovery.articles
                        if article.slug == source.article_slug
                    ),
                    source=source,
                    model_id=model_id,
                    model={
                        "scene_plan": "same",
                        "positive_prompt": "same prompt",
                        "negative_prompt": None,
                    },
                    provider=provider,
                )
                terminal_error = pipeline.final_output_terminal_error(
                    output,
                    root=root,
                    allow_contract_warnings=True,
                )
        self.assertEqual(provider["status"], "provider-unavailable")
        self.assertEqual(
            provider["retry_selection"]["retry_kind"],
            "normalized-input",
        )
        self.assertTrue(provider["retry_selection"]["exhausted"])
        self.assertEqual(
            output["selected_attempt"],
            "normalized-input-retry-v1-exhausted",
        )
        self.assertIsNone(terminal_error)

    def test_exhausted_normalized_retry_forbids_retry2_before_any_network(self) -> None:
        source = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        model_id = "alibaba/wan-2.7"
        binding = pipeline.normalized_input_retry_binding(source, model_id)
        normalized_url = source.image["orig_url"].removesuffix("/orig") + "/scale_1200"
        primary = {
            "provider_run_id": binding.primary_provider_run_id,
            "request": {
                "model": model_id,
                "frame_images": [
                    {"image_url": {"url": source.image["orig_url"]}}
                ],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_test_inventory_lock_target(root)
            with (
                mock.patch.object(pipeline, "configure_native"),
                mock.patch.object(
                    pipeline,
                    "resolve_primary_retry_target",
                    return_value=(source, model_id),
                ),
                mock.patch.object(pipeline, "_terminal_retry_envelope", return_value=None),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_envelope",
                    return_value=(binding, {"primary_attempt": primary}),
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_provider_record",
                    return_value={"status": "provider-unavailable"},
                ),
                mock.patch.object(
                    pipeline,
                    "_aggregate_retry_cost",
                    return_value=pipeline.aggregate_retry_budget_metadata(
                        self.inventory,
                        terminal_retry_reservations=2,
                        ambiguous_submit_retry_reservations=1,
                        normalized_input_retry_reservations=2,
                    ),
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_page_variant_url",
                    return_value=normalized_url,
                ),
                mock.patch.object(
                    pipeline,
                    "preflight_normalized_input_asset",
                ) as preflight,
                mock.patch.object(pipeline.native, "main") as provider_main,
            ):
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "retry2 is forbidden",
                ):
                    pipeline.run_normalized_input_retry(
                        self.discovery.sources,
                        self.inventory,
                        primary_provider_run_id_value=binding.primary_provider_run_id,
                        root=root,
                        dry_run=False,
                        allow_external_processing=True,
                        timeout=901,
                        poll_interval=7.5,
                    )
        preflight.assert_not_called()
        provider_main.assert_not_called()

    def test_real_ambiguous_overlay_retires_raw_unknown_primary_from_capacity(self) -> None:
        target = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        legacy = next(
            source
            for source in self.discovery.sources
            if source.article_slug == "10-krasnaya-polyana-reis-zaderzhali"
            and source.image["image_id"] == "04"
        )
        model_id = "alibaba/wan-2.2"
        synthetic_states = (
            pipeline.GenerationArticleState(
                article_slug=target.article_slug,
                accepted_outputs=0,
                terminal_accounted_outputs=0,
                provider_filtered_outputs=0,
                expected_outputs=1,
                unresolved_run_ids=(),
            ),
        )
        with (
            preserved_native_state(),
            mock.patch.object(
                pipeline,
                "generation_article_states",
                return_value=synthetic_states,
            ),
        ):
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            legacy_entry = pipeline.native.Entry(legacy.sample, model_id)
            receipt, receipt_path = pipeline._native_run_receipt(
                legacy_entry,
                root=pipeline.ROOT,
            )
            before = pipeline.sha256_file(receipt_path)
            overlay = pipeline._effective_terminal_retry_overlay(
                legacy,
                model_id,
                root=pipeline.ROOT,
            )
            # Regression assertion: this used to fail before any network by
            # counting the immutable legacy primary against the one-slot pool.
            pipeline._enforce_normalized_input_retry_order(
                self.discovery.sources,
                target,
                model_id,
                root=pipeline.ROOT,
            )
            after = pipeline.sha256_file(receipt_path)
        self.assertEqual(receipt["status"], "submit-unknown")
        self.assertTrue(receipt["provider_may_be_active"])
        self.assertEqual(overlay["status"], "succeeded")
        self.assertEqual(
            overlay["retry_selection"]["retry_kind"],
            "ambiguous-submit",
        )
        self.assertEqual(before, after)

    def test_capacity_still_fails_closed_without_terminal_effective_overlay(self) -> None:
        target = next(
            source
            for source in self.discovery.sources
            if source.article_slug
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_ARTICLE_SLUG
            and source.image["image_id"]
            == pipeline.NORMALIZED_INPUT_ELIGIBLE_IMAGE_ID
        )
        legacy = next(
            source
            for source in self.discovery.sources
            if source.article_slug == "10-krasnaya-polyana-reis-zaderzhali"
            and source.image["image_id"] == "04"
        )
        model_id = "alibaba/wan-2.2"
        real_effective_overlay = pipeline._effective_terminal_retry_overlay
        synthetic_states = (
            pipeline.GenerationArticleState(
                article_slug=target.article_slug,
                accepted_outputs=0,
                terminal_accounted_outputs=0,
                provider_filtered_outputs=0,
                expected_outputs=1,
                unresolved_run_ids=(),
            ),
        )

        def without_legacy_terminal_overlay(
            source: pipeline.Source,
            selected_model: str,
            *,
            root: Path,
        ):
            if source == legacy and selected_model == model_id:
                return None
            return real_effective_overlay(
                source,
                selected_model,
                root=root,
            )

        with (
            preserved_native_state(),
            mock.patch.object(
                pipeline,
                "_effective_terminal_retry_overlay",
                side_effect=without_legacy_terminal_overlay,
            ),
            mock.patch.object(
                pipeline,
                "generation_article_states",
                return_value=synthetic_states,
            ),
        ):
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "would exceed the active alibaba/wan-2.2 route capacity",
            ):
                pipeline._enforce_normalized_input_retry_order(
                    self.discovery.sources,
                    target,
                    model_id,
                    root=pipeline.ROOT,
                )

    def test_retry_native_matrix_keeps_original_planning_and_exact_model(self) -> None:
        source = self.discovery.sources[0]
        model_id = "google/veo-3.1-lite"
        binding = pipeline.terminal_retry_binding(source, model_id)
        with preserved_native_state():
            pipeline.configure_terminal_retry_native(binding, pipeline.ROOT)
            matrix = pipeline.native.matrix()
            self.assertEqual(len(matrix), 1)
            self.assertEqual(matrix[0].model_id, model_id)
            self.assertEqual(matrix[0].planning_run_id, source.planning_run_id)
            self.assertEqual(
                matrix[0].provider_run_id, binding.retry_provider_run_id
            )
            self.assertEqual(pipeline.native.PLANNING_MODEL_IDS, pipeline.MODEL_IDS)
            self.assertEqual(pipeline.native.MODEL_IDS, (model_id,))
            paths = pipeline.native.artifact_paths(matrix[0], pipeline.ROOT)
            self.assertEqual(paths["run"], pipeline.ROOT / binding.run_rel)
            self.assertTrue(
                paths["run"].is_relative_to(
                    pipeline.ROOT / pipeline.TERMINAL_RETRY_NAMESPACE_REL
                )
            )

    def test_ambiguous_primary_evidence_preserves_unknown_receipt(self) -> None:
        source = self.discovery.sources[0]
        model_id = "alibaba/wan-2.2"
        request = {"model": model_id, "input": {"prompt": "same"}}
        request_sha256 = "a" * 64
        sample = {"source_path": source.image["source_path"]}
        prompt = {"positive_prompt": "same"}
        expected_prompt = {"bound": "verified-lite-prompt"}
        fake_job = SimpleNamespace(
            result_path="artifacts/result.json",
            result_sha256="b" * 64,
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            preserved_native_state(),
        ):
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            primary_paths = pipeline.primary_artifact_paths(source, model_id, root)
            primary_paths["directory"].mkdir(parents=True)
            pipeline.transport.atomic_write_json(
                primary_paths["prompt"],
                expected_prompt,
            )
            primary_receipt = {
                "schema_version": 1,
                "ticket": pipeline.TICKET,
                "batch_id": pipeline.BATCH_ID,
                "agent_id": pipeline.AGENT_ID,
                "lite_run_id": source.planning_run_id,
                "provider_run_id": pipeline.primary_provider_run_id(
                    source,
                    model_id,
                ),
                "model_id": model_id,
                "adapter": "eliza-segmind",
                "status": "submitting",
                "provider_may_be_active": True,
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "error": None,
                "request": request,
                "request_sha256": request_sha256,
                "source_preflight": {
                    "http_status": 200,
                    "bytes": 123,
                    "sha256": source.image["sha256"],
                },
            }
            pipeline.transport.atomic_write_json(
                primary_paths["run"],
                primary_receipt,
            )
            before = pipeline.sha256_file(primary_paths["run"])
            with (
                mock.patch.object(
                    pipeline.native,
                    "load_lite_job",
                    return_value=fake_job,
                ),
                mock.patch.object(
                    pipeline.native,
                    "prompt_artifact",
                    return_value=expected_prompt,
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_sample",
                    return_value=sample,
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_prompt",
                    return_value=prompt,
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_request_preview",
                    return_value=request,
                ),
                mock.patch.object(
                    pipeline.transport,
                    "request_fingerprint",
                    return_value=request_sha256,
                ),
                mock.patch.object(
                    pipeline.native,
                    "_is_exact_legacy_segmind_quota_pre_submit_failure",
                    return_value=False,
                ),
            ):
                evidence = pipeline._primary_ambiguous_submit_evidence(
                    source,
                    model_id,
                    root=root,
                )
            after = pipeline.sha256_file(primary_paths["run"])
        self.assertEqual(evidence["status"], "submit-unknown")
        self.assertEqual(evidence["recorded_status"], "submitting")
        self.assertEqual(evidence["outcome"], "unknown")
        self.assertTrue(evidence["outcome_unknown"])
        self.assertTrue(evidence["provider_may_be_active"])
        self.assertIsNone(evidence["provider_job_id"])
        self.assertEqual(evidence["request_sha256"], request_sha256)
        self.assertEqual(before, after)

    def test_openrouter_ambiguous_primary_evidence_preserves_unknown_receipt(self) -> None:
        source = self.discovery.sources[0]
        model_id = "google/veo-3.1-lite"
        request = {
            "model": model_id,
            "prompt": "same",
            "frame_images": [{"type": "image_url"}],
        }
        request_sha256 = "9" * 64
        sample = {"source_path": source.image["source_path"]}
        prompt = {"positive_prompt": "same"}
        expected_prompt = {"bound": "verified-lite-prompt"}
        fake_job = SimpleNamespace(
            result_path="artifacts/result.json",
            result_sha256="8" * 64,
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            preserved_native_state(),
        ):
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            primary_paths = pipeline.primary_artifact_paths(source, model_id, root)
            primary_paths["directory"].mkdir(parents=True)
            pipeline.transport.atomic_write_json(
                primary_paths["prompt"],
                expected_prompt,
            )
            primary_receipt = {
                "schema_version": 1,
                "ticket": pipeline.TICKET,
                "batch_id": pipeline.BATCH_ID,
                "agent_id": pipeline.AGENT_ID,
                "lite_run_id": source.planning_run_id,
                "provider_run_id": pipeline.primary_provider_run_id(
                    source,
                    model_id,
                ),
                "model_id": model_id,
                "adapter": "eliza-openrouter",
                "status": "submit-unknown",
                "provider_may_be_active": True,
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "error": "The read operation timed out",
                "request": request,
                "request_sha256": request_sha256,
                "request_fingerprint_version": (
                    pipeline.transport.REQUEST_FINGERPRINT_VERSION
                ),
            }
            pipeline.transport.atomic_write_json(
                primary_paths["run"],
                primary_receipt,
            )
            before = pipeline.sha256_file(primary_paths["run"])
            with (
                mock.patch.object(
                    pipeline.native,
                    "load_lite_job",
                    return_value=fake_job,
                ),
                mock.patch.object(
                    pipeline.native,
                    "prompt_artifact",
                    return_value=expected_prompt,
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_sample",
                    return_value=sample,
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_prompt",
                    return_value=prompt,
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_request_preview",
                    return_value=request,
                ),
                mock.patch.object(
                    pipeline.transport,
                    "request_fingerprint",
                    return_value=request_sha256,
                ),
            ):
                evidence = pipeline._primary_ambiguous_submit_evidence(
                    source,
                    model_id,
                    root=root,
                )
            after = pipeline.sha256_file(primary_paths["run"])
        self.assertEqual(evidence["status"], "submit-unknown")
        self.assertEqual(evidence["recorded_status"], "submit-unknown")
        self.assertEqual(evidence["adapter"], "eliza-openrouter")
        self.assertTrue(evidence["outcome_unknown"])
        self.assertTrue(evidence["provider_may_be_active"])
        self.assertIsNone(evidence["provider_job_id"])
        self.assertIsNone(evidence["source_preflight"])
        self.assertEqual(evidence["request_sha256"], request_sha256)
        self.assertEqual(before, after)

    def test_exact_scheduler_normalization_is_audited_without_rewriting_primary(self) -> None:
        original = {
            "status": "submitting",
            "provider_may_be_active": True,
            "request_sha256": "f" * 64,
            "error": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            run_path = Path(directory) / "primary.run.json"
            pipeline.transport.atomic_write_json(run_path, original)
            reserved = {
                "recorded_status": "submitting",
                "error": None,
                "run_sha256": pipeline.sha256_file(run_path),
            }
            normalized = {
                **original,
                "status": "submit-unknown",
                "error": pipeline.AMBIGUOUS_PRIMARY_SCHEDULER_NORMALIZATION_ERROR,
            }
            pipeline.transport.atomic_write_json(run_path, normalized)
            before = pipeline.sha256_file(run_path)
            state = pipeline._ambiguous_primary_receipt_state(
                reserved,
                run_path,
            )
            after = pipeline.sha256_file(run_path)
            tampered = {**normalized, "provider_may_be_active": False}
            pipeline.transport.atomic_write_json(run_path, tampered)
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "changed after retry reservation",
            ):
                pipeline._ambiguous_primary_receipt_state(
                    reserved,
                    run_path,
                )
        self.assertTrue(state["scheduler_normalized"])
        self.assertEqual(state["receipt"], normalized)
        self.assertEqual(before, after)

    def test_successful_retry_is_selected_with_primary_failure_audit(self) -> None:
        source = self.discovery.sources[0]
        model_id = "google/veo-3.1-lite"
        binding = pipeline.terminal_retry_binding(source, model_id)
        shared = {
            "ticket": pipeline.TICKET,
            "agent_id": pipeline.AGENT_ID,
            "lite_run_id": source.planning_run_id,
            "model_id": model_id,
            "source": {
                "path": source.image["source_path"],
                "sha256": source.image["sha256"],
            },
            "structured_intent": {"editorial_meaning": "test"},
            "prompt": {"positive": "same exact prompt", "negative": None},
            "runtime": {"duration_seconds": 4},
            "lite_result": {"path": "result.json", "sha256": "abc"},
        }
        request = {"model": model_id, "prompt": "same exact prompt"}
        request_sha256 = "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary_paths = pipeline.primary_artifact_paths(source, model_id, root)
            primary_paths["directory"].mkdir(parents=True)
            primary_prompt = {
                **shared,
                "batch_id": pipeline.BATCH_ID,
                "provider_run_id": binding.primary_provider_run_id,
            }
            pipeline.transport.atomic_write_json(
                primary_paths["prompt"], primary_prompt
            )
            primary_run = {
                "request": request,
                "request_sha256": request_sha256,
                "status": "provider-failed",
            }
            pipeline.transport.atomic_write_json(primary_paths["run"], primary_run)
            primary = {
                "provider_run_id": binding.primary_provider_run_id,
                "provider_job_id": "primary-job",
                "status": "provider-failed",
                "provider_may_be_active": False,
                "submitted_at": "2026-08-05T00:00:00Z",
                "completed_at": "2026-08-05T00:01:00Z",
                "error": "provider terminal failure",
                "run_path": pipeline.relative(primary_paths["run"], root),
                "run_sha256": pipeline.sha256_file(primary_paths["run"]),
                "prompt_path": pipeline.relative(primary_paths["prompt"], root),
                "prompt_sha256": pipeline.sha256_file(primary_paths["prompt"]),
                "request": request,
                "request_sha256": request_sha256,
                "lite_result_path": "result.json",
                "lite_result_sha256": "abc",
                "source_path": source.image["source_path"],
                "source_sha256": source.image["sha256"],
                "model_id": model_id,
                "lite_run_id": source.planning_run_id,
            }
            envelope = pipeline._terminal_retry_envelope_document(
                binding,
                primary,
                pipeline.terminal_retry_budget_metadata(self.inventory, 1),
            )
            pipeline.transport.atomic_write_json(root / binding.envelope_rel, envelope)
            retry_prompt = {
                **shared,
                "batch_id": binding.retry_batch_id,
                "provider_run_id": binding.retry_provider_run_id,
            }
            pipeline.transport.atomic_write_json(root / binding.prompt_rel, retry_prompt)
            retry_run = {
                "ticket": pipeline.TICKET,
                "batch_id": binding.retry_batch_id,
                "agent_id": pipeline.AGENT_ID,
                "lite_run_id": source.planning_run_id,
                "provider_run_id": binding.retry_provider_run_id,
                "model_id": model_id,
                "status": "succeeded",
                "provider_may_be_active": False,
                "provider_job_id": "retry-job",
                "submitted_at": "2026-08-05T00:02:00Z",
                "completed_at": "2026-08-05T00:03:00Z",
                "request": request,
                "request_sha256": request_sha256,
                "media": {"duration_seconds": 4.0},
                "contract_check": {"conforms": True, "warnings": []},
                "error": None,
            }
            pipeline.transport.atomic_write_json(root / binding.run_rel, retry_run)
            (root / binding.video_rel).write_bytes(b"retry-mp4")
            before = pipeline.sha256_file(primary_paths["run"])
            selected = pipeline._terminal_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            retry_run.update(
                {
                    "status": "provider-failed",
                    "completed_at": "2026-08-05T00:04:00Z",
                    "media": None,
                    "contract_check": None,
                    "error": "content may have been filtered",
                }
            )
            pipeline.transport.atomic_write_json(root / binding.run_rel, retry_run)
            (root / binding.video_rel).unlink()
            exhausted = pipeline._terminal_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            exhausted_output = pipeline._output_record(
                article=self.discovery.articles[0],
                source=source,
                model_id=model_id,
                model={
                    "scene_plan": "plan",
                    "positive_prompt": "same exact prompt",
                    "negative_prompt": None,
                },
                provider=exhausted,
            )
            exhausted_error = pipeline.final_output_terminal_error(
                exhausted_output,
                root=root,
                allow_contract_warnings=True,
            )
            after = pipeline.sha256_file(primary_paths["run"])
        self.assertIsNotNone(selected)
        self.assertEqual(selected["provider_run_id"], binding.retry_provider_run_id)
        self.assertEqual(
            selected["retry_selection"]["primary_attempt"]["provider_run_id"],
            binding.primary_provider_run_id,
        )
        self.assertEqual(
            selected["retry_selection"]["primary_attempt"]["status"],
            "provider-failed",
        )
        self.assertEqual(before, after)
        self.assertEqual(exhausted["status"], "provider-filtered")
        self.assertIsNone(exhausted["video_path"])
        self.assertTrue(exhausted["retry_selection"]["exhausted"])
        self.assertEqual(
            exhausted_output["selected_attempt"],
            "terminal-retry-v1-exhausted",
        )
        self.assertIsNone(exhausted_error)
        state = pipeline.GenerationArticleState(
            article_slug=source.article_slug,
            accepted_outputs=26,
            terminal_accounted_outputs=27,
            provider_filtered_outputs=1,
            expected_outputs=27,
            unresolved_run_ids=(),
        )
        self.assertTrue(state.complete)

    def test_ambiguous_retry_success_and_terminal_unavailable_are_audited(self) -> None:
        source = self.discovery.sources[0]
        model_id = "google/veo-3.1-lite"
        binding = pipeline.ambiguous_submit_retry_binding(source, model_id)
        shared = {
            "ticket": pipeline.TICKET,
            "agent_id": pipeline.AGENT_ID,
            "lite_run_id": source.planning_run_id,
            "model_id": model_id,
            "source": {
                "path": source.image["source_path"],
                "sha256": source.image["sha256"],
            },
            "structured_intent": {"editorial_meaning": "test"},
            "prompt": {"positive": "same exact prompt", "negative": None},
            "runtime": {"duration_seconds": 5},
            "lite_result": {"path": "result.json", "sha256": "abc"},
        }
        request = {"model": model_id, "prompt": "same exact prompt"}
        request_sha256 = "c" * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary_paths = pipeline.primary_artifact_paths(source, model_id, root)
            primary_paths["directory"].mkdir(parents=True)
            primary_prompt = {
                **shared,
                "batch_id": pipeline.BATCH_ID,
                "provider_run_id": binding.primary_provider_run_id,
            }
            pipeline.transport.atomic_write_json(
                primary_paths["prompt"],
                primary_prompt,
            )
            primary_run = {
                "status": "submitting",
                "provider_may_be_active": True,
                "request": request,
                "request_sha256": request_sha256,
            }
            pipeline.transport.atomic_write_json(primary_paths["run"], primary_run)
            primary = {
                "provider_run_id": binding.primary_provider_run_id,
                "provider_job_id": None,
                "status": "submit-unknown",
                "recorded_status": "submitting",
                "outcome": "unknown",
                "outcome_unknown": True,
                "ambiguity_reason": "response was not durably observed",
                "provider_may_be_active": True,
                "submitted_at": None,
                "completed_at": None,
                "error": None,
                "run_path": pipeline.relative(primary_paths["run"], root),
                "run_sha256": pipeline.sha256_file(primary_paths["run"]),
                "prompt_path": pipeline.relative(primary_paths["prompt"], root),
                "prompt_sha256": pipeline.sha256_file(primary_paths["prompt"]),
                "request": request,
                "request_sha256": request_sha256,
                "lite_result_path": "result.json",
                "lite_result_sha256": "abc",
                "source_path": source.image["source_path"],
                "source_sha256": source.image["sha256"],
                "model_id": model_id,
                "adapter": "eliza-openrouter",
                "lite_run_id": source.planning_run_id,
            }
            envelope = pipeline._ambiguous_submit_retry_envelope_document(
                binding,
                primary,
                pipeline.aggregate_retry_budget_metadata(
                    self.inventory,
                    terminal_retry_reservations=0,
                    ambiguous_submit_retry_reservations=1,
                ),
            )
            pipeline.transport.atomic_write_json(
                root / binding.envelope_rel,
                envelope,
            )
            retry_prompt = {
                **shared,
                "batch_id": binding.retry_batch_id,
                "provider_run_id": binding.retry_provider_run_id,
            }
            pipeline.transport.atomic_write_json(
                root / binding.prompt_rel,
                retry_prompt,
            )
            retry_run = {
                "ticket": pipeline.TICKET,
                "batch_id": binding.retry_batch_id,
                "agent_id": pipeline.AGENT_ID,
                "lite_run_id": source.planning_run_id,
                "provider_run_id": binding.retry_provider_run_id,
                "model_id": model_id,
                "adapter": "eliza-openrouter",
                "status": "succeeded",
                "provider_may_be_active": False,
                "provider_job_id": "retry-job",
                "submitted_at": "2026-08-05T00:02:00Z",
                "completed_at": "2026-08-05T00:03:00Z",
                "request": request,
                "request_sha256": request_sha256,
                "media": {"duration_seconds": 5.0},
                "contract_check": {"conforms": True, "warnings": []},
                "error": None,
            }
            pipeline.transport.atomic_write_json(root / binding.run_rel, retry_run)
            (root / binding.video_rel).write_bytes(b"retry-mp4")
            success = pipeline._ambiguous_submit_retry_provider_record(
                source,
                model_id,
                root=root,
            )

            retry_run.update(
                {
                    "status": "provider-failed",
                    "completed_at": "2026-08-05T00:04:00Z",
                    "media": None,
                    "contract_check": None,
                    "error": "provider terminal failure",
                }
            )
            pipeline.transport.atomic_write_json(root / binding.run_rel, retry_run)
            (root / binding.video_rel).unlink()
            unavailable = pipeline._ambiguous_submit_retry_provider_record(
                source,
                model_id,
                root=root,
            )
            output = pipeline._output_record(
                article=self.discovery.articles[0],
                source=source,
                model_id=model_id,
                model={
                    "scene_plan": "plan",
                    "positive_prompt": "same exact prompt",
                    "negative_prompt": None,
                },
                provider=unavailable,
            )
            terminal_error = pipeline.final_output_terminal_error(
                output,
                root=root,
                allow_contract_warnings=True,
            )
        self.assertEqual(success["status"], "succeeded")
        self.assertEqual(
            success["retry_selection"]["retry_kind"],
            "ambiguous-submit",
        )
        self.assertFalse(success["retry_selection"]["exhausted"])
        self.assertEqual(unavailable["status"], "provider-unavailable")
        self.assertIsNone(unavailable["video_path"])
        self.assertTrue(unavailable["retry_selection"]["exhausted"])
        self.assertEqual(
            output["selected_attempt"],
            "ambiguous-submit-retry-v1-exhausted",
        )
        self.assertIsNone(terminal_error)

    def test_ambiguous_retry_dry_run_never_writes_or_calls_provider(self) -> None:
        source = self.discovery.sources[0]
        model_id = "alibaba/wan-2.2"
        request = {"model": model_id, "input": {"prompt": "same"}}
        request_sha256 = "d" * 64
        primary = {
            "provider_run_id": pipeline.primary_provider_run_id(source, model_id),
            "status": "submit-unknown",
            "recorded_status": "submitting",
            "outcome": "unknown",
            "outcome_unknown": True,
            "ambiguity_reason": "unknown outcome",
            "provider_may_be_active": True,
            "provider_job_id": None,
            "submitted_at": None,
            "completed_at": None,
            "request": request,
            "request_sha256": request_sha256,
        }
        aggregate_cost = pipeline.aggregate_retry_budget_metadata(
            self.inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                mock.patch.object(pipeline, "configure_native"),
                mock.patch.object(
                    pipeline,
                    "resolve_primary_retry_target",
                    return_value=(source, model_id),
                ),
                mock.patch.object(
                    pipeline,
                    "_terminal_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_enforce_ambiguous_submit_retry_order",
                ),
                mock.patch.object(
                    pipeline,
                    "_primary_ambiguous_submit_evidence",
                    return_value=primary,
                ),
                mock.patch.object(
                    pipeline,
                    "_aggregate_retry_cost",
                    return_value=aggregate_cost,
                ),
                mock.patch.object(
                    pipeline,
                    "configure_ambiguous_submit_retry_native",
                ),
                mock.patch.object(
                    pipeline.native,
                    "matrix",
                    return_value=[SimpleNamespace()],
                ),
                mock.patch.object(
                    pipeline.native,
                    "load_lite_job",
                    return_value=SimpleNamespace(),
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_sample",
                    return_value={"source_path": source.image["source_path"]},
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_prompt",
                    return_value={"positive_prompt": "same"},
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_request_preview",
                    return_value=request,
                ),
                mock.patch.object(
                    pipeline.transport,
                    "request_fingerprint",
                    return_value=request_sha256,
                ),
                mock.patch.object(pipeline.native, "main") as provider_main,
            ):
                result = pipeline.run_ambiguous_submit_retry(
                    self.discovery.sources,
                    self.inventory,
                    primary_provider_run_id_value=primary["provider_run_id"],
                    root=root,
                    dry_run=True,
                    allow_external_processing=False,
                    timeout=901,
                    poll_interval=7.5,
                )
            files = tuple(path for path in root.rglob("*") if path.is_file())
        self.assertEqual(result, 0)
        self.assertEqual(files, ())
        provider_main.assert_not_called()

    def test_real_ambiguous_retry_requires_explicit_external_authorization(self) -> None:
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "requires --allow-external-processing",
        ):
            pipeline.run_ambiguous_submit_retry(
                self.discovery.sources,
                self.inventory,
                primary_provider_run_id_value="never-resolved",
                root=pipeline.ROOT,
                dry_run=False,
                allow_external_processing=False,
                timeout=901,
                poll_interval=7.5,
            )

    def test_exhausted_ambiguous_retry_forbids_retry2_without_provider_call(self) -> None:
        source = self.discovery.sources[0]
        model_id = "alibaba/wan-2.2"
        binding = pipeline.ambiguous_submit_retry_binding(source, model_id)
        request = {"model": model_id, "input": {"prompt": "same"}}
        request_sha256 = "e" * 64
        primary = {
            "provider_run_id": binding.primary_provider_run_id,
            "request": request,
            "request_sha256": request_sha256,
        }
        aggregate_cost = pipeline.aggregate_retry_budget_metadata(
            self.inventory,
            terminal_retry_reservations=2,
            ambiguous_submit_retry_reservations=1,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_test_inventory_lock_target(root)
            with (
                mock.patch.object(pipeline, "configure_native"),
                mock.patch.object(
                    pipeline,
                    "resolve_primary_retry_target",
                    return_value=(source, model_id),
                ),
                mock.patch.object(
                    pipeline,
                    "_terminal_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_envelope",
                    return_value=(binding, {"primary_attempt": primary}),
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_provider_record",
                    return_value={"status": "provider-unavailable"},
                ),
                mock.patch.object(
                    pipeline,
                    "_aggregate_retry_cost",
                    return_value=aggregate_cost,
                ),
                mock.patch.object(
                    pipeline,
                    "configure_ambiguous_submit_retry_native",
                ),
                mock.patch.object(
                    pipeline.native,
                    "matrix",
                    return_value=[SimpleNamespace()],
                ),
                mock.patch.object(
                    pipeline.native,
                    "load_lite_job",
                    return_value=SimpleNamespace(),
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_sample",
                    return_value={"source_path": source.image["source_path"]},
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_prompt",
                    return_value={"positive_prompt": "same"},
                ),
                mock.patch.object(
                    pipeline.native,
                    "provider_request_preview",
                    return_value=request,
                ),
                mock.patch.object(
                    pipeline.transport,
                    "request_fingerprint",
                    return_value=request_sha256,
                ),
                mock.patch.object(pipeline.native, "main") as provider_main,
            ):
                with self.assertRaisesRegex(
                    pipeline.PipelineError,
                    "retry2 is forbidden",
                ):
                    pipeline.run_ambiguous_submit_retry(
                        self.discovery.sources,
                        self.inventory,
                        primary_provider_run_id_value=binding.primary_provider_run_id,
                        root=root,
                        dry_run=False,
                        allow_external_processing=True,
                        timeout=901,
                        poll_interval=7.5,
                    )
        provider_main.assert_not_called()

    def test_inventory_contract_is_frozen_and_routes_are_current_exact(self) -> None:
        contract = self.inventory["contract"]
        routes = self.inventory["generation_routes"]
        self.assertEqual(
            contract["contract_version"], pipeline.planning_contract_version()
        )
        self.assertEqual(contract["contract_version"], "2.0.6")
        self.assertEqual(
            pipeline._contract_snapshot(pipeline.ROOT)["contract_version"],
            pipeline.REQUIRED_CONTRACT_VERSION,
        )
        self.assertEqual(
            routes["policy"],
            {
                "resolution": "exact-model-id",
                "automatic_fallback": False,
                "normal_run_discovery": False,
            },
        )
        self.assertEqual(
            {
                model_id: route["capacity"]
                for model_id, route in routes["models"].items()
            },
            pipeline.ROUTE_CAPACITIES,
        )
        self.assertEqual(
            routes["models"]["alibaba/wan-2.2"]["transport"],
            "eliza-synchronous-binary",
        )
        self.assertEqual(
            routes["models"]["alibaba/wan-2.2"]["adapter"],
            "eliza-segmind",
        )

    def test_native_bridge_uses_isolated_namespace_and_public_originals(self) -> None:
        with preserved_native_state():
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            matrix = pipeline.native.matrix()
            self.assertEqual(len(matrix), 276)
            self.assertEqual(
                {entry.model_id for entry in matrix}, set(pipeline.MODEL_IDS)
            )
            self.assertEqual(pipeline.native.PLANNING_MODEL_IDS, pipeline.MODEL_IDS)
            self.assertIsNone(pipeline.native.WAN_SUBMIT_MODE)
            first = matrix[0]
            sample = pipeline.native.provider_sample(first)
            self.assertTrue(sample["source_url"].startswith("https://avatars.mds"))
            self.assertEqual(sample["source_path"], first.sample.source_path)
            paths = pipeline.native.artifact_paths(first, pipeline.ROOT)
            self.assertTrue(
                paths["video"].is_relative_to(pipeline.ROOT / pipeline.BATCH_ROOT_REL)
            )
            self.assertIn(pipeline.BATCH_ID, paths["video"].parts)
            self.assertNotIn("PROMOPAGES-9857/clipmaker-lite-runs", paths["video"].as_posix())

    def test_prepare_explicitly_requests_all_three_models(self) -> None:
        source = self.discovery.sources[0]
        completed = subprocess.CompletedProcess([], 0, "ok", "")
        with (
            mock.patch.object(
                pipeline, "_planning_state", side_effect=[None, "prepared"]
            ),
            mock.patch.object(
                pipeline.subprocess, "run", return_value=completed
            ) as run,
        ):
            counts = pipeline.prepare_planning_runs(
                (source,), root=pipeline.ROOT, dry_run=False
            )
        self.assertEqual(counts["prepared"], 1)
        command = run.call_args.args[0]
        requested_models = [
            command[index + 1]
            for index, value in enumerate(command)
            if value == "--model"
        ]
        self.assertEqual(requested_models, list(pipeline.MODEL_IDS))
        self.assertIn(source.image["source_path"], command)
        self.assertIn(source.context_path, command)

    def test_generate_always_starts_fixed_independent_1_3_3_pools(self) -> None:
        with (
            preserved_native_state(),
            mock.patch.object(pipeline.native, "main", return_value=0) as main,
        ):
            result = pipeline.run_generation(
                self.discovery.sources,
                root=pipeline.ROOT,
                dry_run=True,
                allow_external_processing=False,
                timeout=901,
                poll_interval=7.5,
                fail_fast=False,
            )
        self.assertEqual(result, 0)
        argv = main.call_args.args[0]
        self.assertEqual(
            argv[:12],
            [
                "run",
                "--wan22-concurrency",
                "1",
                "--wan27-concurrency",
                "3",
                "--veo31-concurrency",
                "3",
                "--timeout",
                "901",
                "--poll-interval",
                "7.5",
                "--dry-run",
            ],
        )
        selected_run_ids = [
            argv[index + 1]
            for index, value in enumerate(argv)
            if value == "--run-id"
        ]
        self.assertEqual(len(selected_run_ids), len(set(selected_run_ids)))
        self.assertNotIn("--model", argv)
        self.assertNotIn("--force", argv)

    def test_generate_can_enforce_a_whole_article_barrier(self) -> None:
        first_article_sources = tuple(
            source
            for source in self.discovery.sources
            if source.article_slug == self.discovery.articles[0].slug
        )
        with (
            preserved_native_state(),
            mock.patch.object(pipeline.native, "main", return_value=0) as main,
        ):
            result = pipeline.run_generation(
                self.discovery.sources,
                selected_sources=first_article_sources,
                root=pipeline.ROOT,
                dry_run=True,
                allow_external_processing=False,
                timeout=901,
                poll_interval=7.5,
                fail_fast=False,
            )
            expected_run_ids = [
                pipeline.native.Entry(source.sample, model_id).run_id
                for source in first_article_sources
                for model_id in pipeline.MODEL_IDS
            ]
        self.assertEqual(result, 0)
        argv = main.call_args.args[0]
        selected_run_ids = [
            argv[index + 1]
            for index, value in enumerate(argv)
            if value == "--run-id"
        ]
        self.assertEqual(len(selected_run_ids), 12)
        self.assertEqual(
            selected_run_ids,
            expected_run_ids,
        )

    def test_terminal_ambiguous_overlay_excludes_only_its_primary_model_row(self) -> None:
        selected = self._article_sources(0)
        target = selected[0]
        model_id = "alibaba/wan-2.2"
        binding = pipeline.ambiguous_submit_retry_binding(target, model_id)

        def ambiguous_envelope(source, candidate_model, *, root):
            del root
            if source == target and candidate_model == model_id:
                return binding, {"terminal": True}
            return None

        for terminal_status in ("succeeded", "provider-unavailable"):
            with (
                preserved_native_state(),
                mock.patch.object(
                    pipeline,
                    "_terminal_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_envelope",
                    side_effect=ambiguous_envelope,
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_provider_record",
                    return_value={"status": terminal_status},
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_envelope",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_provider_record",
                    return_value=None,
                ),
            ):
                pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
                run_ids, exclusions = pipeline.generation_scheduling_plan(
                    self.discovery.sources,
                    selected,
                    root=pipeline.ROOT,
                )
            target_primary = pipeline.primary_provider_run_id(target, model_id)
            self.assertEqual(exclusions, (target_primary,))
            self.assertNotIn(target_primary, run_ids)
            self.assertIn(
                pipeline.primary_provider_run_id(target, "alibaba/wan-2.7"),
                run_ids,
            )
            self.assertIn(
                pipeline.primary_provider_run_id(selected[1], model_id),
                run_ids,
            )

    def test_nonterminal_ambiguous_retry_blocks_normal_generation_plan(self) -> None:
        selected = self._article_sources(0)
        target = selected[0]
        model_id = "alibaba/wan-2.2"
        binding = pipeline.ambiguous_submit_retry_binding(target, model_id)

        def ambiguous_envelope(source, candidate_model, *, root):
            del root
            if source == target and candidate_model == model_id:
                return binding, {"terminal": False}
            return None

        with (
            preserved_native_state(),
            mock.patch.object(
                pipeline,
                "_terminal_retry_envelope",
                return_value=None,
            ),
            mock.patch.object(
                pipeline,
                "_ambiguous_submit_retry_envelope",
                side_effect=ambiguous_envelope,
            ),
            mock.patch.object(
                pipeline,
                "_ambiguous_submit_retry_provider_record",
                return_value=None,
            ),
            mock.patch.object(
                pipeline,
                "_normalized_input_retry_envelope",
                return_value=None,
            ),
            mock.patch.object(
                pipeline,
                "_normalized_input_retry_provider_record",
                return_value=None,
            ),
        ):
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "retry is not terminal",
            ):
                pipeline.generation_scheduling_plan(
                    self.discovery.sources,
                    selected,
                    root=pipeline.ROOT,
                )

    def test_native_scheduling_exclusion_suppresses_unresolved_auto_widening(self) -> None:
        source = self.discovery.sources[0]
        model_id = "alibaba/wan-2.2"
        with (
            tempfile.TemporaryDirectory() as directory,
            preserved_native_state(),
        ):
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            entry = pipeline.native.Entry(source.sample, model_id)
            run_path = root / "unresolved.run.json"
            pipeline.transport.atomic_write_json(
                run_path,
                {
                    "status": "submit-unknown",
                    "provider_may_be_active": True,
                },
            )
            row = {"entry": entry, "paths": {"run": run_path}}
            self.assertTrue(pipeline.native._row_has_unresolved_provider(row))
            with pipeline.native_scheduling_exclusions((entry.run_id,)):
                self.assertFalse(
                    pipeline.native._row_has_unresolved_provider(row)
                )
                self.assertEqual(
                    pipeline.native.SCHEDULING_EXCLUDED_RUN_IDS,
                    frozenset({entry.run_id}),
                )
            self.assertTrue(pipeline.native._row_has_unresolved_provider(row))
            self.assertEqual(
                pipeline.native.SCHEDULING_EXCLUDED_RUN_IDS,
                frozenset(),
            )

    def _article_sources(self, article_index: int):
        slug = self.discovery.articles[article_index].slug
        return tuple(
            source
            for source in self.discovery.sources
            if source.article_slug == slug
        )

    def _write_native_receipt(
        self,
        source,
        model_id: str,
        root: Path,
        *,
        status: str = "succeeded",
        unresolved: bool = False,
    ) -> None:
        entry = pipeline.native.Entry(source.sample, model_id)
        paths = pipeline.native.artifact_paths(entry, root)
        paths["directory"].mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema_version": 1,
            "ticket": pipeline.TICKET,
            "batch_id": pipeline.BATCH_ID,
            "agent_id": pipeline.AGENT_ID,
            "lite_run_id": entry.planning_run_id,
            "provider_run_id": entry.provider_run_id,
            "model_id": model_id,
            "status": status,
            "provider_may_be_active": unresolved,
            "completed_at": None if unresolved else "2026-08-05T00:00:00Z",
            "media": None if unresolved else {"duration_seconds": 5.0},
            "contract_check": None if unresolved else {"conforms": True},
        }
        pipeline.transport.atomic_write_json(paths["run"], receipt)
        if not unresolved:
            paths["video"].write_bytes(b"test-mp4")

    def _complete_article(self, sources, root: Path) -> None:
        for source in sources:
            for model_id in pipeline.MODEL_IDS:
                self._write_native_receipt(source, model_id, root)

    def _write_test_inventory_lock_target(self, root: Path) -> None:
        pipeline.transport.atomic_write_json(
            root / pipeline.INVENTORY_MANIFEST_REL,
            {"test_only": True},
        )

    def test_real_generation_requires_one_whole_next_article_and_can_resume_it(self) -> None:
        first_sources = self._article_sources(0)
        with tempfile.TemporaryDirectory() as directory, preserved_native_state():
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            self._write_test_inventory_lock_target(root)
            # One terminal output makes this a partially started article. It
            # must remain the only admissible article until all 12 are done.
            self._write_native_receipt(
                first_sources[0], pipeline.MODEL_IDS[0], root
            )
            with (
                mock.patch.object(pipeline, "configure_native", return_value=None),
                mock.patch.object(pipeline.native, "main", return_value=0) as main,
            ):
                result = pipeline.run_generation(
                    self.discovery.sources,
                    selected_sources=first_sources,
                    root=root,
                    dry_run=False,
                    allow_external_processing=True,
                    timeout=901,
                    poll_interval=7.5,
                    fail_fast=False,
                )
        self.assertEqual(result, 0)
        argv = main.call_args.args[0]
        selected_run_ids = [
            argv[index + 1]
            for index, value in enumerate(argv)
            if value == "--run-id"
        ]
        self.assertEqual(len(selected_run_ids), len(first_sources) * 3)
        self.assertEqual(
            argv[1:7],
            [
                "--wan22-concurrency",
                "1",
                "--wan27-concurrency",
                "3",
                "--veo31-concurrency",
                "3",
            ],
        )

    def test_real_generation_rejects_unfiltered_partial_and_later_article(self) -> None:
        first_sources = self._article_sources(0)
        later_sources = self._article_sources(1)
        with tempfile.TemporaryDirectory() as directory, preserved_native_state():
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            self._write_test_inventory_lock_target(root)
            with (
                mock.patch.object(pipeline, "configure_native", return_value=None),
                mock.patch.object(pipeline.native, "main", return_value=0) as main,
            ):
                common = dict(
                    root=root,
                    dry_run=False,
                    allow_external_processing=True,
                    timeout=901,
                    poll_interval=7.5,
                    fail_fast=False,
                )
                with self.assertRaisesRegex(
                    pipeline.PipelineError, "exactly one --article"
                ):
                    pipeline.run_generation(
                        self.discovery.sources,
                        selected_sources=self.discovery.sources,
                        **common,
                    )
                with self.assertRaisesRegex(
                    pipeline.PipelineError, "every image"
                ):
                    pipeline.run_generation(
                        self.discovery.sources,
                        selected_sources=first_sources[:1],
                        **common,
                    )
                with self.assertRaisesRegex(
                    pipeline.PipelineError, "Next incomplete article"
                ):
                    pipeline.run_generation(
                        self.discovery.sources,
                        selected_sources=later_sources,
                        **common,
                    )
        main.assert_not_called()

    def test_gate_advances_only_after_all_prior_terminal_media_is_accepted(self) -> None:
        first_sources = self._article_sources(0)
        second_sources = self._article_sources(1)
        with tempfile.TemporaryDirectory() as directory, preserved_native_state():
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            self._complete_article(first_sources, root)
            state = pipeline.enforce_real_generation_article_order(
                self.discovery.sources,
                second_sources,
                root=root,
            )
            self.assertEqual(state.article_slug, second_sources[0].article_slug)
            self.assertEqual(state.accepted_outputs, 0)
            self.assertEqual(state.expected_outputs, len(second_sources) * 3)

            # A receipt alone is not complete: the native media file is part
            # of the local terminal acceptance proof.
            entry = pipeline.native.Entry(
                first_sources[-1].sample, pipeline.MODEL_IDS[-1]
            )
            pipeline.native.artifact_paths(entry, root)["video"].unlink()
            with self.assertRaisesRegex(
                pipeline.PipelineError, "Next incomplete article"
            ):
                pipeline.enforce_real_generation_article_order(
                    self.discovery.sources,
                    second_sources,
                    root=root,
                )

    def test_unresolved_future_provider_job_blocks_article_run(self) -> None:
        first_sources = self._article_sources(0)
        future_sources = self._article_sources(1)
        with tempfile.TemporaryDirectory() as directory, preserved_native_state():
            root = Path(directory)
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            self._write_native_receipt(
                future_sources[0],
                pipeline.MODEL_IDS[0],
                root,
                status="running",
                unresolved=True,
            )
            with self.assertRaisesRegex(
                pipeline.PipelineError, "outside the current article prefix"
            ):
                pipeline.enforce_real_generation_article_order(
                    self.discovery.sources,
                    first_sources,
                    root=root,
                )

    def test_dry_run_may_inspect_a_later_whole_article(self) -> None:
        later_sources = self._article_sources(1)
        with (
            preserved_native_state(),
            mock.patch.object(pipeline.native, "main", return_value=0) as main,
        ):
            result = pipeline.run_generation(
                self.discovery.sources,
                selected_sources=later_sources,
                root=pipeline.ROOT,
                dry_run=True,
                allow_external_processing=False,
                timeout=901,
                poll_interval=7.5,
                fail_fast=False,
            )
        self.assertEqual(result, 0)
        selected_run_ids = [
            main.call_args.args[0][index + 1]
            for index, value in enumerate(main.call_args.args[0])
            if value == "--run-id"
        ]
        self.assertEqual(len(selected_run_ids), len(later_sources) * 3)

    def test_inventory_is_write_once_and_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = {"schema_version": 1, "bound": "first"}
            second = {"schema_version": 1, "bound": "changed"}
            with mock.patch.object(
                pipeline, "inventory_document", return_value=first
            ):
                written = pipeline.write_inventory(
                    self.discovery, "100.0", root
                )
                self.assertEqual(written, first)
                self.assertEqual(
                    json.loads((root / pipeline.INVENTORY_MANIFEST_REL).read_text()),
                    first,
                )
            with mock.patch.object(
                pipeline, "inventory_document", return_value=second
            ):
                with self.assertRaisesRegex(
                    pipeline.PipelineError, "Immutable inventory differs"
                ):
                    pipeline.write_inventory(self.discovery, "100.0", root)

    def test_final_document_matches_nested_step5_shape_and_exposes_unavailable(self) -> None:
        generation_outputs = []
        result_models = []
        with preserved_native_state():
            pipeline.configure_native(self.discovery.sources, pipeline.ROOT)
            for model_id in pipeline.MODEL_IDS:
                result_models.append(
                    {
                        "model_id": model_id,
                        "scene_plan": f"plan {model_id}",
                        "positive_prompt": f"prompt {model_id}",
                        "negative_prompt": None,
                    }
                )
            for source in self.discovery.sources:
                for model_id in pipeline.MODEL_IDS:
                    entry = pipeline.native.Entry(source.sample, model_id)
                    generation_outputs.append(
                        {
                            "source_path": source.image["source_path"],
                            "model_id": model_id,
                            "provider_run_id": entry.provider_run_id,
                            "status": "planned",
                            "recorded_status": "planned",
                            "prompt_path": f"prompts/{entry.provider_run_id}.json",
                            "run_path": f"runs/{entry.provider_run_id}.json",
                            "video_path": f"videos/{entry.provider_run_id}.mp4",
                            "media": None,
                            "contract_check": None,
                            "error": None,
                        }
                    )
            planning_result = {
                "models": result_models,
                "analysis": {
                    "structured_intent": {
                        "editorial_meaning": "meaning",
                        "primary_action": "action",
                        "terminal_state": "end",
                        "semantic_invariant": "invariant",
                    }
                },
            }
            with (
                mock.patch.object(pipeline, "configure_native", return_value=None),
                mock.patch.object(pipeline.native, "materialize", return_value=[]),
                mock.patch.object(
                    pipeline,
                    "read_json",
                    return_value={"outputs": generation_outputs},
                ),
                mock.patch.object(
                    pipeline,
                    "_planning_record",
                    return_value=({"result_path": "result.json"}, planning_result),
                ),
                mock.patch.object(
                    pipeline,
                    "_terminal_retry_provider_record",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_ambiguous_submit_retry_provider_record",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_normalized_input_retry_provider_record",
                    return_value=None,
                ),
                mock.patch.object(
                    pipeline,
                    "_known_retry_envelopes",
                    return_value=(),
                ),
                mock.patch.object(
                    pipeline,
                    "_known_ambiguous_submit_retry_envelopes",
                    return_value=(),
                ),
                mock.patch.object(
                    pipeline,
                    "_known_normalized_input_retry_envelopes",
                    return_value=(),
                ),
                mock.patch.object(
                    pipeline,
                    "_femibion_recovery_overlay",
                    return_value=({}, None),
                ),
            ):
                document = pipeline.build_final_manifest(
                    self.discovery,
                    self.inventory,
                    root=pipeline.ROOT,
                    updated_at="2026-08-05T00:00:00Z",
                    allow_contract_warnings=False,
                )
        self.assertEqual(document["article_count"], 13)
        self.assertEqual(document["image_count"], 92)
        self.assertEqual(document["expected_outputs"], 276)
        self.assertEqual(
            document["manifest_role"], "promopages-10060-all-images"
        )
        self.assertEqual(document["unavailable_articles"][0]["article_number"], "02")
        self.assertEqual(len(document["articles"]), 13)
        self.assertEqual(len(document["outputs"]), 276)
        self.assertEqual(
            sum(len(article["images"]) for article in document["articles"]),
            92,
        )
        for article in document["articles"]:
            self.assertEqual(article["image_count"], len(article["images"]))
            self.assertEqual(article["images"][0]["image"]["role"], "cover")
            for record in article["images"]:
                self.assertEqual(set(record), {"image", "lite_planning", "outputs"})
                self.assertEqual(len(record["outputs"]), 3)
                self.assertEqual(
                    [output["model_id"] for output in record["outputs"]],
                    list(pipeline.MODEL_IDS),
                )

    def test_cli_exposes_the_complete_resumable_workflow(self) -> None:
        parser = pipeline.build_parser()
        for command in (
            "inventory",
            "prepare-plans",
            "run-plans",
            "plan-generation",
            "generate",
            "retry-terminal-failure",
            "retry-ambiguous-submit",
            "finalize",
            "verify",
        ):
            argv = [command]
            if command in {
                "retry-terminal-failure",
                "retry-ambiguous-submit",
            }:
                argv.extend(("--provider-run-id", "primary-run"))
            args = parser.parse_args(argv)
            self.assertEqual(args.command, command)
        generate = parser.parse_args(["generate", "--dry-run"])
        self.assertTrue(generate.dry_run)
        self.assertEqual(generate.budget_cap_usd, pipeline.HARD_BUDGET_CAP_USD)


if __name__ == "__main__":
    unittest.main()
