"""Reproduces: RunPodWorkerClient embedded up to 500 raw chars of the
worker's HTTP response body directly into RunPodWorkerError messages, which
flow through image_runner.run_edit()'s broad except handler into
image_jobs.normalized_error -- a field the job status route returns to the
client verbatim. The raw body (which can carry internal infrastructure
detail) must go to the log instead.
"""

from __future__ import annotations

import logging

import httpx
import pytest

from gateway.runpod_worker import RunPodWorkerClient, RunPodWorkerError

TOKEN = "t" * 32
INTERNAL_DETAIL = "Traceback (most recent call last): worker-node-7a3f internal path /srv/comfy/secrets"


@pytest.mark.asyncio
async def test_get_job_error_does_not_leak_raw_response_body(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=INTERNAL_DETAIL)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://worker.invalid"
    ) as http_client:
        async with RunPodWorkerClient(
            "https://worker.invalid", TOKEN, client=http_client
        ) as client:
            with caplog.at_level(logging.WARNING, logger="kitty.runpod_worker"):
                with pytest.raises(RunPodWorkerError) as excinfo:
                    await client.get_job("job-1")

    assert INTERNAL_DETAIL not in str(excinfo.value)
    assert "500" in str(excinfo.value)
    assert any(INTERNAL_DETAIL in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_cancel_error_does_not_leak_raw_response_body(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text=INTERNAL_DETAIL)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://worker.invalid"
    ) as http_client:
        async with RunPodWorkerClient(
            "https://worker.invalid", TOKEN, client=http_client
        ) as client:
            with pytest.raises(RunPodWorkerError) as excinfo:
                await client.cancel("job-1")

    assert INTERNAL_DETAIL not in str(excinfo.value)
