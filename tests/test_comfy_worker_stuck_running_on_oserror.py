"""Reproduces: workers/comfy_worker/app.py's WorkerRuntime.execute() only
catches (httpx.HTTPError, WorkerConfigurationError, ValueError), but output
download inside the same try block does raw filesystem writes that can raise
OSError (disk full, permissions). An uncaught OSError there leaves the job
permanently stuck at JobStatus.RUNNING instead of transitioning to FAILED --
it's a fire-and-forget asyncio.create_task with no outer handler.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from workers.comfy_worker.app import (
    JobRecord,
    JobRequest,
    JobStatus,
    WorkerConfig,
    WorkerRuntime,
    WorkflowBundle,
)

TOKEN = "t" * 48


def _config(tmp_path: Path) -> WorkerConfig:
    return WorkerConfig(
        bearer_token=TOKEN,
        comfy_url="http://comfy.invalid",
        workflow_root=Path("workflows"),
        job_root=tmp_path / "jobs",
        default_checkpoint="model.safetensors",
        allowed_checkpoints=frozenset({"model.safetensors"}),
        generation_timeout_seconds=2,
        poll_interval_seconds=0.001,
        max_request_bytes=64 * 1024,
    )


@pytest.mark.asyncio
async def test_disk_error_during_output_download_leaves_job_stuck_running(tmp_path):
    config = _config(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prompt_id": "p1"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://comfy.invalid"
    ) as http_client:
        manager = WorkerRuntime(config, client=http_client)
        try:
            bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
            record = JobRecord(
                job_id="job-1",
                status=JobStatus.QUEUED,
                request={},
                workflow_sha256=bundle.workflow_sha256,
                created_at="2026-09-17T00:00:00Z",
                updated_at="2026-09-17T00:00:00Z",
            )
            manager.jobs[record.job_id] = record
            request = JobRequest(
                workflow_id="text_to_image_v1",
                prompt="test",
                negative_prompt="",
                checkpoint="model.safetensors",
                width=512,
                height=512,
                steps=1,
                guidance=5,
                seed=1,
            )

            # A disk failure surfacing as OSError while writing generated
            # output to disk -- not one of the types execute()'s except
            # clause catches (httpx.HTTPError, WorkerConfigurationError,
            # ValueError).
            manager.assert_comfy_ready = AsyncMock(return_value=None)
            manager._wait_and_collect = AsyncMock(
                side_effect=OSError("[Errno 28] No space left on device")
            )

            with pytest.raises(OSError):
                await manager.execute(record, request, bundle, "model.safetensors")

            # This is the bug: the job is left stuck at RUNNING instead of
            # being marked FAILED with the disk error, because the OSError
            # propagated straight out of execute() uncaught.
            assert record.status is not JobStatus.RUNNING, (
                "job was left stuck at RUNNING after an uncaught OSError during "
                "output download -- it will stay stuck until the worker process "
                "is restarted"
            )
        finally:
            await manager.close()


@pytest.mark.asyncio
async def test_unhandled_task_failure_retires_job(tmp_path):
    """The fire-and-forget job task must retire the record even when execute()
    escapes with an exception that never reaches its own handler."""
    config = _config(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prompt_id": "p1"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://comfy.invalid"
    ) as http_client:
        manager = WorkerRuntime(config, client=http_client)
        try:
            bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
            record = JobRecord(
                job_id="job-outer-guard",
                status=JobStatus.QUEUED,
                request={},
                workflow_sha256=bundle.workflow_sha256,
                created_at="2026-09-17T00:00:00Z",
                updated_at="2026-09-17T00:00:00Z",
            )
            manager.jobs[record.job_id] = record
            request = JobRequest(
                workflow_id="text_to_image_v1",
                prompt="test",
                negative_prompt="",
                checkpoint="model.safetensors",
                width=512,
                height=512,
                steps=1,
                guidance=5,
                seed=1,
            )

            async def _fail(_record, _request, _bundle, _checkpoint) -> None:
                raise OSError("[Errno 28] No space left on device")

            manager.execute = _fail  # type: ignore[method-assign]
            manager.start_job(record, request, bundle, "model.safetensors")

            # Let the spawned task finish and the done-callback run.
            for _ in range(50):
                if record.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
                    break
                await asyncio.sleep(0)

            assert record.status is JobStatus.FAILED
            assert record.error == "OSError: [Errno 28] No space left on device"
        finally:
            await manager.close()


@pytest.mark.asyncio
async def test_unhandled_failure_with_empty_exception_message_still_names_the_cause(
    tmp_path,
):
    """Qodo finding: an exception with an empty ``str()`` (e.g. ``OSError()``
    with no arguments) must not produce an empty/uninformative job error."""
    config = _config(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prompt_id": "p1"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://comfy.invalid"
    ) as http_client:
        manager = WorkerRuntime(config, client=http_client)
        try:
            bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
            record = JobRecord(
                job_id="job-empty-message",
                status=JobStatus.QUEUED,
                request={},
                workflow_sha256=bundle.workflow_sha256,
                created_at="2026-09-17T00:00:00Z",
                updated_at="2026-09-17T00:00:00Z",
            )
            manager.jobs[record.job_id] = record
            request = JobRequest(
                workflow_id="text_to_image_v1",
                prompt="test",
                negative_prompt="",
                checkpoint="model.safetensors",
                width=512,
                height=512,
                steps=1,
                guidance=5,
                seed=1,
            )

            async def _fail(_record, _request, _bundle, _checkpoint) -> None:
                raise OSError  # no message -> str(exc) == ""

            manager.execute = _fail  # type: ignore[method-assign]
            manager.start_job(record, request, bundle, "model.safetensors")

            for _ in range(50):
                if record.status in (
                    JobStatus.SUCCEEDED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ):
                    break
                await asyncio.sleep(0)

            assert record.status is JobStatus.FAILED
            assert record.error, "job was retired with no recorded cause"
            assert "OSError" in record.error
        finally:
            await manager.close()


@pytest.mark.asyncio
async def test_persist_recovers_by_clearing_outputs_when_disk_is_full(
    tmp_path, monkeypatch
):
    """Qodo finding: the OSError that fails a job can also fail persisting
    the FAILED state to the same full filesystem, leaving job.json stuck at
    RUNNING forever. Clearing this job's own partial outputs must free
    enough space for the terminal write to land."""
    config = _config(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"prompt_id": "p1"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://comfy.invalid"
    ) as http_client:
        manager = WorkerRuntime(config, client=http_client)
        try:
            bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
            record = JobRecord(
                job_id="job-disk-full",
                status=JobStatus.RUNNING,
                request={},
                workflow_sha256=bundle.workflow_sha256,
                created_at="2026-09-17T00:00:00Z",
                updated_at="2026-09-17T00:00:00Z",
            )
            manager.jobs[record.job_id] = record

            job_dir = config.job_root / record.job_id
            outputs_dir = job_dir / "outputs"
            outputs_dir.mkdir(parents=True)
            (outputs_dir / "partial.png").write_bytes(b"x" * 10)
            # Seed a job.json so a failed retry still leaves a prior file in
            # place if the fix regresses.
            manager._persist(record)

            original_write_text = Path.write_text

            def flaky_write_text(self: Path, *args, **kwargs):
                if self.name == "job.json.tmp" and outputs_dir.exists() and any(
                    outputs_dir.iterdir()
                ):
                    raise OSError(28, "No space left on device")
                return original_write_text(self, *args, **kwargs)

            monkeypatch.setattr(Path, "write_text", flaky_write_text)

            manager.update(record, job_status=JobStatus.FAILED, error="disk full")

            assert record.status is JobStatus.FAILED
            assert not outputs_dir.exists() or not any(outputs_dir.iterdir()), (
                "partial outputs were not cleared to reclaim space"
            )
            job_json = job_dir / "job.json"
            assert job_json.exists()
            persisted = json.loads(job_json.read_text())
            assert persisted["status"] == "failed", (
                "terminal state was not persisted to disk after the disk-full "
                "condition cleared"
            )
        finally:
            await manager.close()
