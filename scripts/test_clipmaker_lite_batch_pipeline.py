#!/usr/bin/env python3
"""Tests for the fresh native Clipmaker Lite 5x3 batch bridge."""

from __future__ import annotations

import argparse
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from scripts import clipmaker_lite_batch_pipeline as batch
from scripts import video_generation_pipeline as transport


class ClipmakerLiteBatchPipelineTest(unittest.TestCase):
    def lite_job(self, entry: batch.Entry) -> batch.LiteJob:
        runtime = batch.contract()["models"][entry.model_id]["runtime"]
        return batch.LiteJob(
            entry=entry,
            structured_intent={
                "editorial_meaning": "Test editorial meaning.",
                "primary_action": "One test action.",
                "terminal_state": "The action reaches its test endpoint.",
                "semantic_invariant": "The test meaning remains stable.",
            },
            positive_prompt=f"exact Lite prompt for {entry.model_id}",
            negative_prompt=None,
            result_path=(
                f"artifacts/clipmaker-lite/v1/{entry.planning_run_id}/result.json"
            ),
            result_sha256="a" * 64,
            provenance={"verified": True, "models": list(batch.MODEL_IDS)},
            runtime=runtime,
        )

    def args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "dry_run": False,
            "force": False,
            "fail_fast": False,
            "concurrency": 3,
            "timeout": 30,
            "poll_interval": 0.0,
            "allow_external_processing": True,
            "wan_base_url": "https://wan.invalid",
            "wan_stream_base_url": "https://wan-stream.invalid",
            "eliza_base_url": "https://eliza.invalid/v1",
            "run_id": [],
            "model": [],
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def temp_row(self, root: Path, model_id: str) -> dict[str, object]:
        entry = next(item for item in batch.matrix() if item.model_id == model_id)
        job = self.lite_job(entry)
        directory = root / model_id.replace("/", "-")
        directory.mkdir(parents=True)
        paths = {
            "directory": directory,
            "prompt": directory / "result.prompt.json",
            "run": directory / "result.run.json",
            "video": directory / "result.mp4",
        }
        row: dict[str, object] = {
            "entry": entry,
            "job": job,
            "sample": batch.provider_sample(entry),
            "prompt": batch.provider_prompt(job),
            "paths": paths,
        }
        transport.atomic_write_json(
            paths["run"],
            {
                "model_id": model_id,
                "status": "pending",
                "request": None,
                "request_sha256": None,
                "request_fingerprint_version": None,
                "provider_job_id": None,
                "provider_session_hash": None,
                "submitted_at": None,
                "completed_at": None,
                "media": None,
                "contract_check": None,
                "error": None,
            },
        )
        return row

    def valid_media(self, model_id: str) -> dict[str, object]:
        if model_id == "alibaba/wan-2.2":
            return {
                "width": 1200,
                "height": 800,
                "duration_seconds": 3.2,
                "frames": 97,
                "fps": 30.0,
                "has_audio": False,
                "bytes": 100,
                "sha256": "b" * 64,
            }
        if model_id == "alibaba/wan-2.7":
            return {
                "width": 1440,
                "height": 1080,
                "duration_seconds": 5.0,
                "has_audio": False,
                "bytes": 100,
                "sha256": "b" * 64,
            }
        return {
            "width": 1920,
            "height": 1080,
            "duration_seconds": 4.0,
            "has_audio": False,
            "bytes": 100,
            "sha256": "b" * 64,
        }

    def provider_operations(
        self,
        model_id: str,
        **overrides: object,
    ) -> batch.ProviderOperations:
        def download(
            _url: str,
            destination: Path,
            **_kwargs: object,
        ) -> None:
            destination.write_bytes(b"fake mp4")

        values: dict[str, object] = {
            "eliza_headers": lambda: {"Authorization": "OAuth test"},
            "http_json": lambda *_args, **_kwargs: {"id": "new-provider-job"},
            "eliza_poll": lambda *_args, **_kwargs: {"status": "completed"},
            "http_download": download,
            "wan_generate": lambda *_args, **_kwargs: None,
            "media_probe": lambda _path: self.valid_media(model_id),
        }
        values.update(overrides)
        return batch.ProviderOperations(**values)

    def test_matrix_has_five_shared_plans_and_fifteen_provider_runs(self) -> None:
        self.assertEqual(batch.TICKET, "PROMOPAGES-9909")
        self.assertEqual(batch.BATCH_ID, "promopages-9909-lite1-20260723")
        entries = batch.matrix()
        self.assertEqual(len(entries), 15)
        self.assertEqual(len({entry.provider_run_id for entry in entries}), 15)
        self.assertEqual(len({entry.planning_run_id for entry in entries}), 5)
        for sample in batch.SAMPLES:
            sample_entries = [entry for entry in entries if entry.sample == sample]
            self.assertEqual(
                [entry.model_id for entry in sample_entries], list(batch.MODEL_IDS)
            )
            self.assertEqual(
                {entry.planning_run_id for entry in sample_entries},
                {sample.planning_run_id},
            )
            self.assertEqual(len({entry.provider_run_id for entry in sample_entries}), 3)

    def test_artifacts_are_isolated_below_the_batch_namespace(self) -> None:
        for entry in batch.matrix():
            paths = batch.artifact_paths(entry)
            for name in ("prompt", "run", "video"):
                self.assertIn(f"/clipmaker-lite/runs/{batch.BATCH_ID}/", paths[name].as_posix())
            self.assertNotIn("wan-streamlit-wan-2.2", paths["video"].as_posix())

    def test_null_negative_does_not_modify_the_verified_lite_prompt(self) -> None:
        entry = next(item for item in batch.matrix() if item.model_id == "alibaba/wan-2.2")
        job = self.lite_job(entry)
        preview = transport.build_request_preview(
            batch.provider_sample(entry), batch.provider_prompt(job)
        )
        self.assertEqual(preview["input"]["prompt"], job.positive_prompt)
        self.assertNotIn("Avoid:", preview["input"]["prompt"])
        artifact = batch.prompt_artifact(job)
        self.assertEqual(artifact["schema_version"], 2)
        self.assertEqual(artifact["lite_run_id"], entry.planning_run_id)
        self.assertEqual(artifact["provider_run_id"], entry.provider_run_id)
        self.assertEqual(artifact["structured_intent"], job.structured_intent)
        self.assertIsNone(artifact["prompt"]["negative"])
        self.assertEqual(
            artifact["lite_result"]["provenance"]["models"],
            list(batch.MODEL_IDS),
        )

    def test_load_lite_job_requires_structured_intent_and_null_negative(self) -> None:
        entries = batch.matrix()[:3]
        entry = entries[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / entry.sample.source_path
            source.parent.mkdir(parents=True)
            source.write_bytes((batch.ROOT / entry.sample.source_path).read_bytes())
            result_path = (
                root
                / batch.ARTIFACT_NAMESPACE
                / entry.planning_run_id
                / "result.json"
            )
            result_path.parent.mkdir(parents=True)
            result = {
                "schema_version": 2,
                "job_id": entry.planning_run_id,
                "producer": {"agent_id": batch.AGENT_ID},
                "inputs": {
                    "source_image": {
                        "path": entry.sample.source_path,
                        "sha256": entry.sample.source_sha256,
                    },
                    "article_context": {"path": entry.sample.context_path},
                },
                "analysis": {"structured_intent": self.lite_job(entry).structured_intent},
                "models": [
                    {
                        "model_id": model_id,
                        "positive_prompt": f"exact shared-result prompt for {model_id}",
                        "negative_prompt": None,
                        "runtime": batch.contract()["models"][model_id]["runtime"],
                    }
                    for model_id in batch.MODEL_IDS
                ],
            }
            transport.atomic_write_json(result_path, result)
            summary = {
                "verified": True,
                "agent_id": batch.AGENT_ID,
                "models": list(batch.MODEL_IDS),
                "source_image_sha256": entry.sample.source_sha256,
                "result_path": (
                    batch.ARTIFACT_NAMESPACE / entry.planning_run_id / "result.json"
                ).as_posix(),
            }
            with mock.patch.object(
                batch.clipmaker_lite_runner,
                "provenance_summary",
                return_value=summary,
            ) as provenance:
                jobs = [batch.load_lite_job(item, root) for item in entries]

                self.assertEqual(
                    [job.positive_prompt for job in jobs],
                    [
                        f"exact shared-result prompt for {model_id}"
                        for model_id in batch.MODEL_IDS
                    ],
                )
                self.assertEqual(
                    {tuple(job.structured_intent.items()) for job in jobs},
                    {tuple(jobs[0].structured_intent.items())},
                )
                self.assertEqual({job.result_path for job in jobs}, {summary["result_path"]})
                self.assertEqual(len({job.result_sha256 for job in jobs}), 1)
                self.assertEqual(
                    [call.args[1] for call in provenance.call_args_list],
                    [entry.planning_run_id] * 3,
                )

                result["models"][1]["negative_prompt"] = "historical repair"
                transport.atomic_write_json(result_path, result)
                with self.assertRaisesRegex(
                    batch.BatchPipelineError,
                    "baseline negative_prompt must be null",
                ):
                    batch.load_lite_job(entries[1], root)

    def test_load_lite_job_rejects_incomplete_planning_provenance(self) -> None:
        entry = batch.matrix()[0]
        summary = {
            "verified": True,
            "agent_id": batch.AGENT_ID,
            "models": [entry.model_id],
            "source_image_sha256": entry.sample.source_sha256,
        }
        with mock.patch.object(
            batch.clipmaker_lite_runner,
            "provenance_summary",
            return_value=summary,
        ) as provenance:
            with self.assertRaisesRegex(
                batch.BatchPipelineError,
                "producer/model set mismatch",
            ):
                batch.load_lite_job(entry)
        provenance.assert_called_once_with(batch.ROOT, entry.planning_run_id)

    def test_provider_expansion_is_model_specific(self) -> None:
        entries = {entry.model_id: entry for entry in batch.matrix()[:3]}
        wan = self.lite_job(entries["alibaba/wan-2.7"])
        veo = self.lite_job(entries["google/veo-3.1-lite"])
        wan_request = transport.build_request_preview(
            batch.provider_sample(wan.entry), batch.provider_prompt(wan)
        )
        veo_request = transport.build_request_preview(
            batch.provider_sample(veo.entry), batch.provider_prompt(veo)
        )
        self.assertEqual(
            wan_request["provider"]["options"]["atlas-cloud"]["parameters"],
            {"prompt_extend": True},
        )
        self.assertEqual(
            veo_request["provider"]["options"]["google-vertex"]["parameters"],
            {"enhancePrompt": True},
        )

    def test_present_negative_prompt_is_transported_verbatim(self) -> None:
        entries = {entry.model_id: entry for entry in batch.matrix()[:3]}
        negative = "exact Lite negative; keep punctuation: unchanged"
        for model_id, provider_key in (
            ("alibaba/wan-2.7", "negative_prompt"),
            ("google/veo-3.1-lite", "negativePrompt"),
        ):
            base = self.lite_job(entries[model_id])
            job = batch.LiteJob(
                entry=base.entry,
                structured_intent=base.structured_intent,
                positive_prompt=base.positive_prompt,
                negative_prompt=negative,
                result_path=base.result_path,
                result_sha256=base.result_sha256,
                provenance=base.provenance,
                runtime=base.runtime,
            )
            preview = transport.build_request_preview(
                batch.provider_sample(job.entry),
                batch.provider_prompt(job),
            )
            provider = "atlas-cloud" if model_id == "alibaba/wan-2.7" else "google-vertex"
            parameters = preview["provider"]["options"][provider]["parameters"]
            self.assertEqual(preview["prompt"], base.positive_prompt)
            self.assertEqual(parameters[provider_key], negative)

    def test_global_eliza_scheduler_caps_active_jobs_at_three_and_finishes_ten(self) -> None:
        rows = [{"id": index} for index in range(10)]
        lock = threading.Lock()
        active = 0
        maximum = 0
        processed: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return batch.WorkerResult(row, False, "succeeded")

        failures = batch.run_bounded_queue(
            rows,
            3,
            worker,
            lambda result: processed.append(result.row["id"]),
            fail_fast=False,
        )

        self.assertEqual(failures, 0)
        self.assertEqual(sorted(processed), list(range(10)))
        self.assertLessEqual(maximum, 3)
        self.assertGreater(maximum, 1)

    def test_eliza_failure_does_not_cancel_other_jobs_without_fail_fast(self) -> None:
        rows = [{"id": index} for index in range(10)]
        processed: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            failed = row["id"] == 2
            return batch.WorkerResult(
                row,
                failed,
                "provider-failed" if failed else "succeeded",
            )

        failures = batch.run_bounded_queue(
            rows,
            3,
            worker,
            lambda result: processed.append(result.row["id"]),
            fail_fast=False,
        )

        self.assertEqual(failures, 1)
        self.assertEqual(sorted(processed), list(range(10)))

    def test_fail_fast_stops_enqueuing_new_eliza_jobs(self) -> None:
        rows = [{"id": index} for index in range(10)]
        started: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            started.append(row["id"])
            failed = row["id"] == 0
            if not failed:
                time.sleep(0.05)
            return batch.WorkerResult(
                row,
                failed,
                "provider-failed" if failed else "succeeded",
            )

        failures = batch.run_bounded_queue(
            rows,
            3,
            worker,
            lambda _result: None,
            fail_fast=True,
        )

        self.assertEqual(failures, 1)
        self.assertEqual(set(started), {0, 1, 2})

    def test_ambiguous_eliza_results_do_not_release_provider_slots(self) -> None:
        rows = [{"id": index} for index in range(10)]
        started: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            started.append(row["id"])
            return batch.WorkerResult(
                row,
                True,
                "submit-unknown",
                "timeout",
                holds_provider_slot=True,
            )

        failures = batch.run_bounded_queue(
            rows,
            3,
            worker,
            lambda _result: None,
            fail_fast=False,
        )

        self.assertEqual(failures, 3)
        self.assertEqual(set(started), {0, 1, 2})

    def test_one_ambiguous_job_leaves_only_remaining_safe_capacity(self) -> None:
        rows = [{"id": index} for index in range(10)]
        processed: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            ambiguous = row["id"] == 0
            return batch.WorkerResult(
                row,
                ambiguous,
                "submit-unknown" if ambiguous else "succeeded",
                "timeout" if ambiguous else None,
                holds_provider_slot=ambiguous,
            )

        failures = batch.run_bounded_queue(
            rows,
            3,
            worker,
            lambda result: processed.append(result.row["id"]),
            fail_fast=False,
        )

        self.assertEqual(failures, 1)
        self.assertEqual(sorted(processed), list(range(10)))

    def test_wan_queue_remains_sequential(self) -> None:
        rows = [{"id": index} for index in range(5)]
        active = 0
        maximum = 0
        order: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            order.append(row["id"])
            time.sleep(0.005)
            active -= 1
            return batch.WorkerResult(row, False, "succeeded")

        failures = batch.run_serial_queue(
            rows,
            worker,
            lambda _result: None,
            fail_fast=False,
        )

        self.assertEqual(failures, 0)
        self.assertEqual(maximum, 1)
        self.assertEqual(order, list(range(5)))

    def test_unresolved_wan_job_blocks_later_wan_submits(self) -> None:
        rows = [{"id": index} for index in range(5)]
        started: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            started.append(row["id"])
            return batch.WorkerResult(
                row,
                True,
                "submitted",
                "temporary polling failure",
                holds_provider_slot=True,
            )

        failures = batch.run_serial_queue(
            rows,
            worker,
            lambda _result: None,
            fail_fast=False,
        )

        self.assertEqual(failures, 1)
        self.assertEqual(started, [0])

    def test_concurrency_one_reproduces_sequential_eliza_order(self) -> None:
        rows = [{"id": index} for index in range(10)]
        started: list[int] = []
        completed: list[int] = []

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            started.append(row["id"])
            return batch.WorkerResult(row, False, "succeeded")

        failures = batch.run_bounded_queue(
            rows,
            1,
            worker,
            lambda result: completed.append(result.row["id"]),
            fail_fast=False,
        )

        self.assertEqual(failures, 0)
        self.assertEqual(started, list(range(10)))
        self.assertEqual(completed, list(range(10)))

    def test_concurrency_one_preserves_legacy_full_matrix_order(self) -> None:
        rows = [{"entry": entry} for entry in batch.matrix()]
        started: list[str] = []

        def worker(row: dict[str, batch.Entry]) -> batch.WorkerResult:
            started.append(row["entry"].run_id)
            return batch.WorkerResult(row, False, "succeeded")

        failures = batch.run_matrix_order_serial(
            rows,
            worker,
            lambda _result: None,
            fail_fast=False,
        )

        self.assertEqual(failures, 0)
        self.assertEqual(started, [entry.run_id for entry in batch.matrix()])

    def test_run_selected_concurrency_one_uses_full_matrix_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                {
                    "entry": entry,
                    "paths": {"run": root / f"{index}.run.json"},
                }
                for index, entry in enumerate(batch.matrix())
            ]
            started: list[str] = []

            def worker(
                row: dict[str, object],
                _args: argparse.Namespace,
                _root: Path,
                _operations: batch.ProviderOperations,
            ) -> batch.WorkerResult:
                started.append(row["entry"].run_id)
                return batch.WorkerResult(row, False, "succeeded")

            with (
                mock.patch.object(batch, "run_provider_worker", side_effect=worker),
                mock.patch.object(batch, "write_manifest"),
            ):
                failures = batch.run_selected(
                    rows,
                    self.args(dry_run=True, concurrency=1),
                    root,
                    self.provider_operations("alibaba/wan-2.7"),
                )

            self.assertEqual(failures, 0)
            self.assertEqual(started, [entry.run_id for entry in batch.matrix()])

    def test_manifest_completion_callback_runs_only_on_coordinator_thread(self) -> None:
        rows = [{"id": index} for index in range(4)]
        coordinator = threading.get_ident()
        worker_threads: set[int] = set()
        completion_threads: set[int] = set()

        def worker(row: dict[str, int]) -> batch.WorkerResult:
            worker_threads.add(threading.get_ident())
            return batch.WorkerResult(row, False, "succeeded")

        batch.run_bounded_queue(
            rows,
            2,
            worker,
            lambda _result: completion_threads.add(threading.get_ident()),
            fail_fast=False,
        )

        self.assertTrue(worker_threads)
        self.assertNotIn(coordinator, worker_threads)
        self.assertEqual(completion_threads, {coordinator})

    def test_filters_cannot_ignore_unresolved_jobs_when_reserving_global_slots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = [
                entry
                for entry in batch.matrix()
                if entry.model_id in batch.ELIZA_MODEL_IDS
            ][:4]
            rows: list[dict[str, object]] = []
            for index, entry in enumerate(entries):
                run_path = root / f"{index}.run.json"
                unresolved = index < 3
                transport.atomic_write_json(
                    run_path,
                    {
                        "status": "submit-unknown" if unresolved else "pending",
                        "provider_may_be_active": unresolved,
                    },
                )
                rows.append(
                    {
                        "entry": entry,
                        "paths": {"run": run_path},
                        "unresolved": unresolved,
                    }
                )
            started: list[str] = []

            def worker(
                row: dict[str, object],
                _args: argparse.Namespace,
                _root: Path,
                _operations: batch.ProviderOperations,
            ) -> batch.WorkerResult:
                entry = row["entry"]
                started.append(entry.run_id)
                unresolved = bool(row["unresolved"])
                return batch.WorkerResult(
                    row,
                    unresolved,
                    "submit-unknown" if unresolved else "succeeded",
                    holds_provider_slot=unresolved,
                )

            with (
                mock.patch.object(batch, "run_provider_worker", side_effect=worker),
                mock.patch.object(batch, "write_manifest"),
            ):
                failures = batch.run_selected(
                    rows,
                    self.args(dry_run=True, run_id=[entries[3].run_id]),
                    root,
                    self.provider_operations("alibaba/wan-2.7"),
                )

            self.assertEqual(failures, 3)
            self.assertEqual(set(started), {entry.run_id for entry in entries[:3]})
            self.assertNotIn(entries[3].run_id, started)

    def test_resume_existing_eliza_job_never_submits_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.7")
            request = transport.build_request_preview(row["sample"], row["prompt"])
            run = transport.read_json(row["paths"]["run"])
            run.update(
                {
                    "status": "submitted",
                    "request": request,
                    "request_sha256": transport.request_fingerprint(request, row["sample"]),
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                    "provider_job_id": "existing-job",
                }
            )
            transport.atomic_write_json(row["paths"]["run"], run)
            submit = mock.Mock(side_effect=AssertionError("resume must not submit"))
            poll = mock.Mock(return_value={"status": "completed"})
            operations = self.provider_operations(
                "alibaba/wan-2.7",
                http_json=submit,
                eliza_poll=poll,
            )

            with mock.patch.object(batch, "materialize_entry", return_value=row):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertFalse(result.failed)
            submit.assert_not_called()
            poll.assert_called_once()
            self.assertEqual(poll.call_args.args[1], "existing-job")
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["provider_job_id"], "existing-job")
            self.assertEqual(final["status"], "succeeded")

    def test_submit_unknown_is_not_retried_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "google/veo-3.1-lite")
            submit = mock.Mock(side_effect=TimeoutError("submit timed out"))
            operations = self.provider_operations(
                "google/veo-3.1-lite",
                http_json=submit,
            )

            with mock.patch.object(batch, "materialize_entry", return_value=row):
                first = batch.run_provider_worker(row, self.args(), root, operations)
                second = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertEqual(first.status, "submit-unknown")
            self.assertEqual(second.status, "submit-unknown")
            self.assertTrue(first.failed)
            self.assertTrue(second.failed)
            self.assertEqual(submit.call_count, 1)
            persisted = transport.read_json(row["paths"]["run"])
            self.assertEqual(persisted["status"], "submit-unknown")
            self.assertIsNone(persisted["provider_job_id"])

    def test_restart_from_submitting_becomes_submit_unknown_without_transport(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.7")
            request = transport.build_request_preview(row["sample"], row["prompt"])
            run = transport.read_json(row["paths"]["run"])
            run.update(
                {
                    "status": "submitting",
                    "request": request,
                    "request_sha256": transport.request_fingerprint(request, row["sample"]),
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                }
            )
            transport.atomic_write_json(row["paths"]["run"], run)
            submit = mock.Mock(side_effect=AssertionError("ambiguous submit must not repeat"))
            operations = self.provider_operations(
                "alibaba/wan-2.7",
                http_json=submit,
            )

            with mock.patch.object(batch, "materialize_entry", return_value=row):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertTrue(result.failed)
            self.assertEqual(result.status, "submit-unknown")
            submit.assert_not_called()
            persisted = transport.read_json(row["paths"]["run"])
            self.assertEqual(persisted["status"], "submit-unknown")

    def test_force_cannot_resubmit_or_overwrite_existing_batch_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.7")
            submit = mock.Mock(side_effect=AssertionError("force must not submit"))
            operations = self.provider_operations(
                "alibaba/wan-2.7",
                http_json=submit,
            )

            with mock.patch.object(batch, "materialize_entry", return_value=row):
                result = batch.run_provider_worker(
                    row,
                    self.args(force=True),
                    root,
                    operations,
                )

            self.assertTrue(result.failed)
            self.assertIn("--force is disabled", result.error)
            submit.assert_not_called()

    def test_revalidation_failure_is_persisted_for_manifest_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "google/veo-3.1-lite")
            operations = self.provider_operations("google/veo-3.1-lite")

            with mock.patch.object(
                batch,
                "materialize_entry",
                side_effect=batch.BatchPipelineError("result digest changed"),
            ):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertTrue(result.failed)
            self.assertEqual(result.status, "revalidation-failed")
            persisted = transport.read_json(row["paths"]["run"])
            self.assertEqual(persisted["status"], "revalidation-failed")
            self.assertIn("result digest changed", persisted["error"])

    def test_active_revalidation_failure_remains_resumable_without_resubmit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.7")
            request = transport.build_request_preview(row["sample"], row["prompt"])
            run = transport.read_json(row["paths"]["run"])
            run.update(
                {
                    "status": "submitted",
                    "request": request,
                    "request_sha256": transport.request_fingerprint(request, row["sample"]),
                    "request_fingerprint_version": transport.REQUEST_FINGERPRINT_VERSION,
                    "provider_job_id": "existing-job",
                    "provider_may_be_active": True,
                }
            )
            transport.atomic_write_json(row["paths"]["run"], run)
            submit = mock.Mock(side_effect=AssertionError("resume must not submit"))
            operations = self.provider_operations(
                "alibaba/wan-2.7",
                http_json=submit,
            )

            with mock.patch.object(
                batch,
                "materialize_entry",
                side_effect=batch.BatchPipelineError("temporary revalidation failure"),
            ):
                failed = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertTrue(failed.failed)
            self.assertTrue(failed.holds_provider_slot)
            persisted = transport.read_json(row["paths"]["run"])
            self.assertEqual(persisted["status"], "submitted")
            self.assertEqual(persisted["last_worker_failure"], "revalidation-failed")

            with mock.patch.object(batch, "materialize_entry", return_value=row):
                resumed = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertFalse(resumed.failed)
            submit.assert_not_called()
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["status"], "succeeded")
            self.assertIsNone(final["last_worker_failure"])

    def test_new_eliza_job_persists_submit_state_before_and_after_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.7")
            observed: list[str] = []

            def submit(*_args: object, **_kwargs: object) -> dict[str, str]:
                observed.append(transport.read_json(row["paths"]["run"])["status"])
                return {"id": "provider-job"}

            def poll(*_args: object, **_kwargs: object) -> dict[str, str]:
                current = transport.read_json(row["paths"]["run"])
                observed.append(current["status"])
                self.assertEqual(current["provider_job_id"], "provider-job")
                return {"status": "completed"}

            operations = self.provider_operations(
                "alibaba/wan-2.7",
                http_json=submit,
                eliza_poll=poll,
            )
            persisted_statuses: list[str] = []
            persist = batch._persist_run

            def record_persist(path: Path, run: dict[str, object]) -> None:
                persisted_statuses.append(str(run["status"]))
                persist(path, run)

            with (
                mock.patch.object(batch, "materialize_entry", return_value=row),
                mock.patch.object(batch, "_persist_run", side_effect=record_persist),
            ):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertFalse(result.failed)
            self.assertEqual(observed, ["submitting", "running"])
            self.assertEqual(
                persisted_statuses[:3],
                ["submitting", "submitted", "running"],
            )
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["status"], "succeeded")
            self.assertEqual(final["provider_job_id"], "provider-job")

    def test_wan_worker_disables_automatic_paid_resubmit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.2")
            observed: dict[str, object] = {}

            def generate(*args: object, **kwargs: object) -> None:
                observed["allow_resubmit"] = kwargs["allow_resubmit_after_missing_session"]
                observed["before_submit"] = transport.read_json(
                    row["paths"]["run"]
                )["status"]
                kwargs["on_submitting"]()
                observed["at_submit"] = transport.read_json(
                    row["paths"]["run"]
                )["status"]
                on_submitted = args[7]
                on_submitted("wan-job", "wan-session")
                row["paths"]["video"].write_bytes(b"fake mp4")

            operations = self.provider_operations(
                "alibaba/wan-2.2",
                wan_generate=generate,
            )
            with mock.patch.object(
                batch,
                "materialize_entry",
                return_value=row,
            ) as materialize:
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertFalse(result.failed)
            self.assertEqual(materialize.call_count, 2)
            self.assertIs(observed["allow_resubmit"], False)
            self.assertEqual(observed["before_submit"], "preparing")
            self.assertEqual(observed["at_submit"], "submitting")
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["provider_job_id"], "wan-job")
            self.assertEqual(final["status"], "succeeded")

    def test_wan_upload_failure_is_known_pre_submit_and_does_not_hold_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.2")

            def fail_before_submit(*_args: object, **_kwargs: object) -> None:
                current = transport.read_json(row["paths"]["run"])
                self.assertEqual(current["status"], "preparing")
                raise transport.PipelineError("upload failed before queue/join")

            operations = self.provider_operations(
                "alibaba/wan-2.2",
                wan_generate=fail_before_submit,
            )
            with mock.patch.object(batch, "materialize_entry", return_value=row):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertTrue(result.failed)
            self.assertEqual(result.status, "failed-pre-submit")
            self.assertFalse(result.holds_provider_slot)
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["status"], "failed-pre-submit")
            self.assertFalse(final["provider_may_be_active"])

    def test_wan_revalidates_after_upload_before_marking_submitting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.2")

            def after_upload(*_args: object, **kwargs: object) -> None:
                kwargs["on_submitting"]()

            operations = self.provider_operations(
                "alibaba/wan-2.2",
                wan_generate=after_upload,
            )
            with mock.patch.object(
                batch,
                "materialize_entry",
                side_effect=[
                    row,
                    batch.BatchPipelineError("Lite result changed during upload"),
                ],
            ):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertTrue(result.failed)
            self.assertEqual(result.status, "failed-pre-submit")
            self.assertFalse(result.holds_provider_slot)
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["status"], "failed-pre-submit")

    def test_media_contract_mismatch_is_a_failed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "google/veo-3.1-lite")
            invalid_media = {
                "width": 1280,
                "height": 720,
                "duration_seconds": 3.0,
                "has_audio": True,
            }
            operations = self.provider_operations(
                "google/veo-3.1-lite",
                media_probe=lambda _path: invalid_media,
            )
            with mock.patch.object(batch, "materialize_entry", return_value=row):
                result = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertTrue(result.failed)
            self.assertEqual(result.status, "verification-failed")
            final = transport.read_json(row["paths"]["run"])
            self.assertEqual(final["status"], "verification-failed")
            self.assertFalse(final["contract_check"]["conforms"])
            self.assertIn("duration", final["contract_check"]["warnings"])
            self.assertIn("audio", final["contract_check"]["warnings"])

    def test_missing_audio_probe_field_fails_strict_contract(self) -> None:
        entry = next(
            item for item in batch.matrix() if item.model_id == "google/veo-3.1-lite"
        )
        media = self.valid_media(entry.model_id)
        media.pop("has_audio")

        result = batch.strict_media_contract(entry, media)

        self.assertFalse(result["conforms"])
        self.assertFalse(result["checks"]["audio"])

    def test_terminal_provider_error_does_not_reserve_a_dead_job_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.2")
            run = transport.read_json(row["paths"]["run"])
            run.update(
                {
                    "status": "running",
                    "provider_job_id": "dead-job",
                    "provider_session_hash": "dead-session",
                }
            )

            result = batch._provider_failure(
                row,
                run,
                transport.ProviderTerminalError("provider rejected the job"),
            )

            self.assertTrue(result.failed)
            self.assertEqual(result.status, "provider-failed")
            self.assertFalse(result.holds_provider_slot)
            persisted = transport.read_json(row["paths"]["run"])
            self.assertEqual(persisted["status"], "provider-failed")

    def test_manifest_exposes_old_contract_failure_without_rewriting_run(self) -> None:
        run = {
            "status": "succeeded",
            "contract_check": {"conforms": False, "warnings": ["audio"]},
        }
        self.assertEqual(batch.effective_run_status(run), "verification-failed")
        self.assertEqual(run["status"], "succeeded")

    def test_existing_strict_failure_is_effective_failure_but_dry_run_stays_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            row = self.temp_row(root, "alibaba/wan-2.7")
            row["paths"]["video"].write_bytes(b"existing mp4")
            run = transport.read_json(row["paths"]["run"])
            run.update(
                {
                    "status": "succeeded",
                    "contract_check": {
                        "conforms": False,
                        "warnings": ["audio", "resolution"],
                    },
                }
            )
            transport.atomic_write_json(row["paths"]["run"], run)
            operations = self.provider_operations("alibaba/wan-2.7")

            with mock.patch.object(batch, "materialize_entry", return_value=row):
                dry_run = batch.run_provider_worker(
                    row,
                    self.args(dry_run=True),
                    root,
                    operations,
                )
                real_run = batch.run_provider_worker(row, self.args(), root, operations)

            self.assertFalse(dry_run.failed)
            self.assertEqual(dry_run.status, "verification-failed")
            self.assertTrue(real_run.failed)
            self.assertEqual(real_run.status, "verification-failed")
            persisted = transport.read_json(row["paths"]["run"])
            self.assertEqual(persisted["status"], "succeeded")

    def test_concurrency_cli_defaults_to_three_and_accepts_one(self) -> None:
        parser = batch.build_parser()
        self.assertEqual(parser.parse_args(["run", "--dry-run"]).concurrency, 3)
        self.assertEqual(
            parser.parse_args(["run", "--dry-run", "--concurrency", "1"]).concurrency,
            1,
        )
        with self.assertRaises(argparse.ArgumentTypeError):
            batch.positive_int("0")


if __name__ == "__main__":
    unittest.main()
