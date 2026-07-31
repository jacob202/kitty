"""Focused tests for Kitty's narrow RunPod control-plane client."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from gateway.runpod_control import (
    KITTY_POD_PREFIX,
    PodInfo,
    RunPodApiError,
    RunPodBudgetError,
    RunPodConfigurationError,
    RunPodControlClient,
)


def test_pod_info_normalizes_rate_gpu_proxy_and_expiry():
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    pod = PodInfo.from_payload(
        {
            "id": "pod-123",
            "name": f"{KITTY_POD_PREFIX}test",
            "desiredStatus": "RUNNING",
            "adjustedCostPerHr": 0.22,
            "gpu": {"displayName": "NVIDIA GeForce RTX 3090"},
            "env": {"KITTY_SESSION_EXPIRES_AT": expiry.isoformat()},
        }
    )

    assert pod.pod_id == "pod-123"
    assert pod.hourly_rate == pytest.approx(0.22)
    assert pod.gpu_name == "NVIDIA GeForce RTX 3090"
    assert pod.proxy_url(8188) == "https://pod-123-8188.proxy.runpod.net"
    assert pod.expiry() == expiry
    assert pod.is_expired(now=expiry - timedelta(seconds=1)) is False
    assert pod.is_expired(now=expiry) is True


def test_client_rejects_empty_api_key():
    with pytest.raises(RunPodConfigurationError, match="RUNPOD_API_KEY"):
        RunPodControlClient("  ")


@pytest.mark.asyncio
async def test_list_managed_pods_filters_by_kitty_prefix():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pods"
        return httpx.Response(
            200,
            json=[
                {"id": "a", "name": f"{KITTY_POD_PREFIX}one"},
                {"id": "b", "name": "someone-elses-pod"},
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with RunPodControlClient(
            "secret",
            base_url="https://example.invalid/v1",
            client=http_client,
        ) as client:
            pods = await client.list_managed_pods()

    assert [pod.pod_id for pod in pods] == ["a"]


@pytest.mark.asyncio
async def test_create_image_pod_sends_bounded_configuration():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pods"
        assert request.headers["authorization"] == "Bearer secret"
        captured.update(json.loads(request.content))
        return httpx.Response(
            201,
            json={
                "id": "pod-1",
                "name": f"{KITTY_POD_PREFIX}test",
                "desiredStatus": "CREATED",
                "adjustedCostPerHr": 0.24,
                "gpu": {"displayName": "NVIDIA GeForce RTX 3090"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with RunPodControlClient(
            "secret",
            base_url="https://example.invalid/v1",
            client=http_client,
        ) as client:
            pod = await client.create_image_pod(
                template_id="template-1",
                gpu_type_ids=[
                    "NVIDIA GeForce RTX 3090",
                    "NVIDIA RTX A5000",
                ],
                max_hourly_rate=0.50,
                hard_runtime_minutes=120,
                ports=("8188/http",),
                container_disk_gb=30,
                volume_gb=20,
                name_suffix="test",
            )

    assert pod.pod_id == "pod-1"
    assert captured["templateId"] == "template-1"
    assert captured["gpuCount"] == 1
    assert captured["containerDiskInGb"] == 30
    assert captured["volumeInGb"] == 20
    assert captured["ports"] == ["8188/http"]
    assert captured["env"]["KITTY_MANAGED"] == "1"  # type: ignore[index]
    assert "KITTY_SESSION_EXPIRES_AT" in captured["env"]  # type: ignore[operator]


@pytest.mark.asyncio
async def test_create_image_pod_terminates_rate_above_ceiling():
    deleted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/pods":
            return httpx.Response(
                201,
                json={
                    "id": "too-expensive",
                    "name": f"{KITTY_POD_PREFIX}expensive",
                    "adjustedCostPerHr": 0.75,
                },
            )
        if request.method == "DELETE":
            deleted.append(request.url.path)
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with RunPodControlClient(
            "secret",
            base_url="https://example.invalid/v1",
            client=http_client,
        ) as client:
            with pytest.raises(RunPodBudgetError, match="Pod was terminated"):
                await client.create_image_pod(
                    template_id="template-1",
                    gpu_type_ids=["NVIDIA GeForce RTX 3090"],
                    max_hourly_rate=0.50,
                    hard_runtime_minutes=120,
                )

    assert deleted == ["/v1/pods/too-expensive"]


@pytest.mark.asyncio
async def test_actual_cost_sums_matching_billing_records():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/billing/pods"
        assert request.url.params["podId"] == "pod-1"
        return httpx.Response(
            200,
            json=[
                {"podId": "pod-1", "amount": 0.03},
                {"podId": "pod-1", "amount": 0.04},
                {"podId": "other", "amount": 99},
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with RunPodControlClient(
            "secret",
            base_url="https://example.invalid/v1",
            client=http_client,
        ) as client:
            cost = await client.actual_cost("pod-1")

    assert cost == pytest.approx(0.07)


@pytest.mark.asyncio
async def test_api_error_is_loud_and_does_not_include_api_key():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with RunPodControlClient(
            "super-secret-token",
            base_url="https://example.invalid/v1",
            client=http_client,
        ) as client:
            with pytest.raises(RunPodApiError) as error:
                await client.list_pods()

    assert "401" in str(error.value)
    assert "super-secret-token" not in str(error.value)
