"""Focused tests for the guarded RunPod/ComfyUI smoke-test path."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from gateway.runpod_control import PodInfo, RunPodConfigurationError
from scripts import runpod_smoke_test as smoke


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "dry_run": False,
        "allow_public_comfyui": False,
        "accept_charges": False,
        "accept_continuing_charges": False,
        "keep_pod": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_workflow_binds_reproducible_values():
    workflow = smoke.build_workflow(
        prompt="a brass robot",
        negative_prompt="blurry",
        checkpoint="model.safetensors",
        width=832,
        height=1216,
        steps=18,
        guidance=4.5,
        seed=42,
    )

    assert workflow["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert workflow["2"]["inputs"]["text"] == "a brass robot"
    assert workflow["4"]["inputs"] == {
        "width": 832,
        "height": 1216,
        "batch_size": 1,
    }
    assert workflow["5"]["inputs"]["seed"] == 42
    assert workflow["5"]["inputs"]["steps"] == 18


def test_parse_history_output_returns_first_image():
    output = smoke.parse_history_output(
        {
            "prompt-1": {
                "outputs": {
                    "7": {
                        "images": [
                            {
                                "filename": "KittySmoke_00001_.png",
                                "subfolder": "smoke",
                                "type": "output",
                            }
                        ]
                    }
                }
            }
        },
        "prompt-1",
    )

    assert output == smoke.ComfyOutput(
        filename="KittySmoke_00001_.png",
        subfolder="smoke",
        output_type="output",
    )


def test_parse_history_output_surfaces_comfy_failure():
    with pytest.raises(smoke.SmokeTestError, match="generation failed"):
        smoke.parse_history_output(
            {
                "prompt-1": {
                    "status": {
                        "status_str": "error",
                        "messages": ["checkpoint missing"],
                    }
                }
            },
            "prompt-1",
        )


def test_estimated_compute_cost_is_seconds_based():
    assert smoke.estimated_compute_cost(0.36, 900) == pytest.approx(0.09)
    assert smoke.estimated_compute_cost(-1, -10) == 0


def test_charge_guards_require_explicit_paid_acknowledgement():
    with pytest.raises(smoke.SmokeTestError, match="--allow-public-comfyui"):
        smoke._validate_charge_acknowledgements(_args(), creating_pod=True)

    with pytest.raises(smoke.SmokeTestError, match="--accept-charges"):
        smoke._validate_charge_acknowledgements(
            _args(allow_public_comfyui=True),
            creating_pod=True,
        )

    smoke._validate_charge_acknowledgements(
        _args(allow_public_comfyui=True, accept_charges=True),
        creating_pod=True,
    )


def test_existing_pod_requires_continuing_charge_acknowledgement():
    with pytest.raises(smoke.SmokeTestError, match="continues billing"):
        smoke._validate_charge_acknowledgements(
            _args(allow_public_comfyui=True),
            creating_pod=False,
        )

    smoke._validate_charge_acknowledgements(
        _args(
            allow_public_comfyui=True,
            accept_continuing_charges=True,
        ),
        creating_pod=False,
    )


def test_config_reads_env_and_rejects_bad_dimensions(monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "secret")
    monkeypatch.setenv("RUNPOD_TEMPLATE_ID", "template-1")
    monkeypatch.setenv("RUNPOD_GPU_TYPE_IDS", "gpu-a, gpu-b")
    monkeypatch.setenv("COMFY_CHECKPOINT", "model.safetensors")

    config = smoke.SmokeConfig.from_env(require_template=True)
    assert config.api_key == "secret"
    assert config.gpu_type_ids == ("gpu-a", "gpu-b")

    monkeypatch.setenv("COMFY_WIDTH", "1025")
    with pytest.raises(RunPodConfigurationError, match="COMFY_WIDTH"):
        smoke.SmokeConfig.from_env(require_template=True)


@pytest.mark.asyncio
async def test_comfy_client_checks_nodes_and_checkpoint_then_submits():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/object_info":
            nodes = {node: {} for node in smoke.REQUIRED_COMFY_NODES}
            nodes["CheckpointLoaderSimple"] = {
                "input": {
                    "required": {
                        "ckpt_name": [["model.safetensors"], {}],
                    }
                }
            }
            return httpx.Response(200, json=nodes)
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "prompt-123"})
        raise AssertionError(f"unexpected path: {request.url.path}")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://example.invalid",
    ) as http_client:
        async with smoke.ComfyUIClient(
            "https://example.invalid",
            client=http_client,
        ) as client:
            await client.assert_ready("model.safetensors")
            prompt_id = await client.submit({"1": {"class_type": "Example"}})

    assert prompt_id == "prompt-123"


@pytest.mark.asyncio
async def test_comfy_submit_network_failure_is_ambiguous():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lost response")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://example.invalid",
    ) as http_client:
        async with smoke.ComfyUIClient(
            "https://example.invalid",
            client=http_client,
        ) as client:
            with pytest.raises(smoke.AmbiguousSubmissionError, match="will not retry"):
                await client.submit({"1": {"class_type": "Example"}})


@pytest.mark.asyncio
async def test_reconcile_expired_pods_deletes_only_expired():
    now = datetime.now(timezone.utc)

    def pod(pod_id: str, expiry: datetime) -> PodInfo:
        return PodInfo(
            pod_id=pod_id,
            name=f"kitty-image-{pod_id}",
            desired_status="RUNNING",
            gpu_name="RTX 3090",
            hourly_rate=0.25,
            created_at=None,
            env={"KITTY_SESSION_EXPIRES_AT": expiry.isoformat()},
            raw={},
        )

    class Client:
        def __init__(self):
            self.deleted: list[str] = []

        async def list_managed_pods(self):
            return [
                pod("expired", now - timedelta(minutes=1)),
                pod("active", now + timedelta(minutes=30)),
            ]

        async def delete_pod(self, pod_id: str):
            self.deleted.append(pod_id)

    client = Client()
    terminated = await smoke.reconcile_expired_pods(client)  # type: ignore[arg-type]

    assert terminated == ["expired"]
    assert client.deleted == ["expired"]
