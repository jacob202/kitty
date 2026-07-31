"""Focused tests for Kitty's narrow RunPod control-plane client."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from gateway.runpod_control import (
    KITTY_POD_PREFIX,
    PodInfo,
    RunPodAmbiguousCreateError,
    RunPodApiError,
    RunPodBudgetError,
    RunPodConfigurationError,
    RunPodControlClient,
)

REST_URL = "https://example.invalid/v1"
GRAPHQL_URL = "https://example.invalid/graphql"


def _graphql_pod(
    *,
    pod_id: str = "pod-1",
    name: str = f"{KITTY_POD_PREFIX}test",
    rate: object = 0.24,
    gpu: str = "NVIDIA GeForce RTX 3090",
) -> dict[str, object]:
    return {
        "data": {
            "podFindAndDeployOnDemand": {
                "id": pod_id,
                "name": name,
                "desiredStatus": "CREATED",
                "costPerHr": rate,
                "machine": {"gpuDisplayName": gpu},
            }
        }
    }


def _client(
    http_client: httpx.AsyncClient,
    *,
    api_key: str = "secret",
) -> RunPodControlClient:
    return RunPodControlClient(
        api_key,
        base_url=REST_URL,
        graphql_url=GRAPHQL_URL,
        client=http_client,
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
            "env": {
                "KITTY_MANAGED": "1",
                "KITTY_SESSION_EXPIRES_AT": expiry.isoformat(),
            },
        }
    )

    assert pod.pod_id == "pod-123"
    assert pod.hourly_rate == pytest.approx(0.22)
    assert pod.gpu_name == "NVIDIA GeForce RTX 3090"
    assert pod.proxy_url(8000) == "https://pod-123-8000.proxy.runpod.net"
    assert pod.expiry() == expiry
    assert pod.is_expired(now=expiry - timedelta(seconds=1)) is False
    assert pod.is_expired(now=expiry) is True
    assert pod.is_managed() is True


def test_client_rejects_empty_api_key():
    with pytest.raises(RunPodConfigurationError, match="RUNPOD_API_KEY"):
        RunPodControlClient("  ")


@pytest.mark.asyncio
async def test_list_managed_pods_requires_prefix_and_marker():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pods"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "a",
                    "name": f"{KITTY_POD_PREFIX}one",
                    "env": {"KITTY_MANAGED": "1"},
                },
                {
                    "id": "b",
                    "name": f"{KITTY_POD_PREFIX}unmarked",
                    "env": {},
                },
                {
                    "id": "c",
                    "name": "someone-elses-pod",
                    "env": {"KITTY_MANAGED": "1"},
                },
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            pods = await client.list_managed_pods()

    assert [pod.pod_id for pod in pods] == ["a"]


@pytest.mark.asyncio
async def test_create_image_pod_sets_server_termination_and_no_ssh():
    captured_input: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graphql"
        assert request.headers["authorization"] == "Bearer secret"
        body = json.loads(request.content)
        captured_input.update(body["variables"]["input"])
        return httpx.Response(200, json=_graphql_pod())

    before = datetime.now(timezone.utc)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            pod = await client.create_image_pod(
                template_id="template-1",
                gpu_type_ids=[
                    "NVIDIA GeForce RTX 3090",
                    "NVIDIA RTX A5000",
                ],
                max_hourly_rate=0.50,
                hard_runtime_minutes=120,
                ports=("8000/http",),
                container_disk_gb=30,
                volume_gb=20,
                env={
                    "CUSTOM_SETTING": "yes",
                    "KITTY_MANAGED": "0",
                    "KITTY_SESSION_EXPIRES_AT": "2099-01-01T00:00:00+00:00",
                },
                name_suffix="test",
            )
    after = datetime.now(timezone.utc)

    assert pod.pod_id == "pod-1"
    assert captured_input["templateId"] == "template-1"
    assert captured_input["gpuCount"] == 1
    assert captured_input["gpuTypeId"] == "NVIDIA GeForce RTX 3090"
    assert captured_input["containerDiskInGb"] == 30
    assert captured_input["volumeInGb"] == 20
    assert captured_input["ports"] == "8000/http"
    assert captured_input["startSsh"] is False

    terminate_after = datetime.fromisoformat(
        str(captured_input["terminateAfter"]).replace("Z", "+00:00")
    )
    assert before + timedelta(minutes=120) <= terminate_after
    assert terminate_after <= after + timedelta(minutes=120)

    captured_env = captured_input["env"]
    assert isinstance(captured_env, list)
    env_map = {
        str(item["key"]): str(item["value"])
        for item in captured_env
        if isinstance(item, dict)
    }
    assert env_map["CUSTOM_SETTING"] == "yes"
    assert env_map["KITTY_MANAGED"] == "1"
    assert env_map["KITTY_SESSION_EXPIRES_AT"] != (
        "2099-01-01T00:00:00+00:00"
    )


@pytest.mark.asyncio
async def test_create_image_pod_tries_next_gpu_after_definite_rejection():
    attempted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        gpu = str(body["variables"]["input"]["gpuTypeId"])
        attempted.append(gpu)
        if len(attempted) == 1:
            return httpx.Response(
                200,
                json={"data": None, "errors": [{"message": "no capacity"}]},
            )
        return httpx.Response(
            200,
            json=_graphql_pod(gpu="NVIDIA RTX A5000"),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            pod = await client.create_image_pod(
                template_id="template-1",
                gpu_type_ids=[
                    "NVIDIA GeForce RTX 3090",
                    "NVIDIA RTX A5000",
                ],
                max_hourly_rate=0.50,
                hard_runtime_minutes=120,
            )

    assert attempted == [
        "NVIDIA GeForce RTX 3090",
        "NVIDIA RTX A5000",
    ]
    assert pod.gpu_name == "NVIDIA RTX A5000"


@pytest.mark.asyncio
async def test_create_image_pod_terminates_rate_above_ceiling():
    deleted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/graphql":
            return httpx.Response(
                200,
                json=_graphql_pod(
                    pod_id="too-expensive",
                    name=f"{KITTY_POD_PREFIX}expensive",
                    rate=0.75,
                ),
            )
        if request.method == "DELETE":
            deleted.append(request.url.path)
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            with pytest.raises(RunPodBudgetError, match="Pod was terminated"):
                await client.create_image_pod(
                    template_id="template-1",
                    gpu_type_ids=["NVIDIA GeForce RTX 3090"],
                    max_hourly_rate=0.50,
                    hard_runtime_minutes=120,
                )

    assert deleted == ["/v1/pods/too-expensive"]


@pytest.mark.asyncio
async def test_create_image_pod_terminates_unknown_rate():
    deleted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/graphql":
            return httpx.Response(
                200,
                json=_graphql_pod(
                    pod_id="unknown-rate",
                    name=f"{KITTY_POD_PREFIX}unknown-rate",
                    rate="nan",
                ),
            )
        if request.method == "DELETE":
            deleted.append(request.url.path)
            return httpx.Response(204)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            with pytest.raises(RunPodApiError, match="positive finite"):
                await client.create_image_pod(
                    template_id="template-1",
                    gpu_type_ids=["NVIDIA GeForce RTX 3090"],
                    max_hourly_rate=0.50,
                    hard_runtime_minutes=120,
                )

    assert deleted == ["/v1/pods/unknown-rate"]


@pytest.mark.asyncio
async def test_create_transport_failure_is_billably_ambiguous():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lost response")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            with pytest.raises(RunPodAmbiguousCreateError) as error:
                await client.create_image_pod(
                    template_id="template-1",
                    gpu_type_ids=["NVIDIA GeForce RTX 3090"],
                    max_hourly_rate=0.50,
                    hard_runtime_minutes=120,
                    name_suffix="ambiguous-test",
                )

    assert error.value.pod_name == f"{KITTY_POD_PREFIX}ambiguous-test"
    assert "reconcile" in str(error.value)


@pytest.mark.asyncio
async def test_create_image_pod_rest_preserves_container_start_cmd():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/pods"
        assert request.method == "POST"
        body = json.loads(request.content)
        captured.update(body)
        return httpx.Response(
            201,
            json={
                "id": "rest-pod",
                "name": f"{KITTY_POD_PREFIX}rest",
                "desiredStatus": "RUNNING",
                "adjustedCostPerHr": 0.31,
                "env": body["env"],
                "gpu": {"displayName": "NVIDIA L4"},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            pod = await client.create_image_pod(
                template_id="source-template-only",
                image_name="runpod/comfyui:cuda13.0",
                container_start_cmd="curl -sSL 'https://example.com/bootstrap.sh' -o /tmp/kitty-bootstrap.sh && chmod 700 /tmp/kitty-bootstrap.sh && exec /tmp/kitty-bootstrap.sh",
                gpu_type_ids=("NVIDIA L4", "NVIDIA RTX A5000"),
                max_hourly_rate=0.60,
                hard_runtime_minutes=55,
                ports=("8000/http",),
                name_suffix="rest",
            )

    assert pod.pod_id == "rest-pod"
    assert captured["imageName"] == "runpod/comfyui:cuda13.0"
    assert captured["dockerEntrypoint"] == ["/bin/sh", "-c"]
    assert captured["dockerStartCmd"] == ["curl -sSL 'https://example.com/bootstrap.sh' -o /tmp/kitty-bootstrap.sh && chmod 700 /tmp/kitty-bootstrap.sh && exec /tmp/kitty-bootstrap.sh"]
    assert captured["gpuTypeIds"] == ["NVIDIA L4", "NVIDIA RTX A5000"]
    assert captured["gpuTypePriority"] == "custom"
    assert captured["ports"] == ["8000/http"]
    assert captured["supportPublicIp"] is False
    assert isinstance(captured["env"], dict)
    assert captured["env"]["KITTY_MANAGED"] == "1"


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
        async with _client(http_client) as client:
            cost = await client.actual_cost("pod-1")

    assert cost == pytest.approx(0.07)


@pytest.mark.asyncio
async def test_actual_cost_rejects_malformed_amount():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"podId": "pod-1", "amount": "not-money"}],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(http_client) as client:
            with pytest.raises(RunPodApiError, match="invalid 'amount'"):
                await client.actual_cost("pod-1")


@pytest.mark.asyncio
async def test_api_error_is_loud_and_does_not_include_api_key():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        async with _client(
            http_client,
            api_key="super-secret-token",
        ) as client:
            with pytest.raises(RunPodApiError) as error:
                await client.list_pods()

    assert "401" in str(error.value)
    assert "super-secret-token" not in str(error.value)
