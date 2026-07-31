"""Contracts for the authenticated, allowlisted Kitty Comfy worker."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.runpod_worker import (
    RunPodWorkerAmbiguousSubmissionError,
    RunPodWorkerClient,
)
from workers.comfy_worker.app import (
    JobRequest,
    WorkerConfig,
    WorkerConfigurationError,
    WorkflowBundle,
    create_app,
)

TOKEN = "t" * 48
AUTH = {"Authorization": f"Bearer {TOKEN}"}
PNG_BYTES = b"\x89PNG\r\n\x1a\nkitty-test"


def _config(tmp_path: Path, **overrides: object) -> WorkerConfig:
    values: dict[str, object] = {
        "bearer_token": TOKEN,
        "comfy_url": "http://comfy.invalid",
        "workflow_root": Path("workflows"),
        "job_root": tmp_path / "jobs",
        "default_checkpoint": "model.safetensors",
        "allowed_checkpoints": frozenset({"model.safetensors"}),
        "generation_timeout_seconds": 2,
        "poll_interval_seconds": 0.001,
        "max_request_bytes": 64 * 1024,
    }
    values.update(overrides)
    return WorkerConfig(**values)  # type: ignore[arg-type]


def _comfy_nodes() -> dict[str, object]:
    bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
    nodes: dict[str, object] = {
        node_type: {} for node_type in bundle.required_node_types
    }
    nodes["CheckpointLoaderSimple"] = {
        "input": {
            "required": {
                "ckpt_name": [["model.safetensors"], {}],
            }
        }
    }
    return nodes


def test_workflow_bundle_binds_values_without_mutating_source():
    bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
    request = JobRequest(
        workflow_id="text_to_image_v1",
        prompt="a brass robot",
        negative_prompt="blurry",
        checkpoint="model.safetensors",
        width=832,
        height=1216,
        steps=18,
        guidance=4.5,
        seed=42,
    )

    compiled = bundle.compile(request, "model.safetensors")

    assert compiled["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert compiled["2"]["inputs"]["text"] == "a brass robot"
    assert compiled["4"]["inputs"]["width"] == 832
    assert compiled["5"]["inputs"]["seed"] == 42
    assert bundle.workflow["2"]["inputs"]["text"] == "__PROMPT__"


def test_workflow_bundle_detects_tampering(tmp_path):
    bundle_root = tmp_path / "workflows"
    shutil.copytree(
        Path("workflows") / "text_to_image_v1",
        bundle_root / "text_to_image_v1",
    )
    workflow_path = bundle_root / "text_to_image_v1" / "workflow-api.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    workflow["2"]["inputs"]["text"] = "tampered"
    workflow_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")

    with pytest.raises(WorkerConfigurationError, match="hash mismatch"):
        WorkflowBundle.load(bundle_root, "text_to_image_v1")


def test_job_request_rejects_checkpoint_paths():
    with pytest.raises(ValueError, match="filename"):
        JobRequest(
            workflow_id="text_to_image_v1",
            prompt="test",
            checkpoint="../../secret.safetensors",
        )


def test_worker_requires_auth_and_runs_one_job(tmp_path):
    history_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal history_calls
        if request.url.path == "/object_info":
            return httpx.Response(200, json=_comfy_nodes())
        if request.url.path == "/prompt":
            payload = json.loads(request.content)
            workflow = payload["prompt"]
            assert workflow["2"]["inputs"]["text"] == "a brass robot"
            assert workflow["5"]["inputs"]["seed"] == 42
            return httpx.Response(200, json={"prompt_id": "prompt-1"})
        if request.url.path == "/history/prompt-1":
            history_calls += 1
            if history_calls == 1:
                return httpx.Response(200, json={})
            return httpx.Response(
                200,
                json={
                    "prompt-1": {
                        "outputs": {
                            "7": {
                                "images": [
                                    {
                                        "filename": "KittyWorker_00001_.png",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=PNG_BYTES)
        raise AssertionError(f"unexpected ComfyUI path: {request.url.path}")

    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/v1/jobs", json={}).status_code == 401

        response = client.post(
            "/v1/jobs",
            headers=AUTH,
            json={
                "workflow_id": "text_to_image_v1",
                "prompt": "a brass robot",
                "negative_prompt": "blurry",
                "checkpoint": "model.safetensors",
                "width": 832,
                "height": 1216,
                "steps": 18,
                "guidance": 4.5,
                "seed": 42,
                "count": 1,
            },
        )
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        payload: dict[str, object] = {}
        for _ in range(100):
            status_response = client.get(
                f"/v1/jobs/{job_id}",
                headers=AUTH,
            )
            payload = status_response.json()
            if payload["status"] == "succeeded":
                break
            time.sleep(0.01)

        assert payload["status"] == "succeeded"
        outputs = payload["outputs"]
        assert isinstance(outputs, list)
        assert outputs[0]["sha256"]
        download = client.get(outputs[0]["download_url"], headers=AUTH)
        assert download.content == PNG_BYTES

    asyncio.run(async_client.aclose())


def test_worker_rejects_non_allowlisted_checkpoint(tmp_path):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        response = client.post(
            "/v1/jobs",
            headers=AUTH,
            json={
                "workflow_id": "text_to_image_v1",
                "prompt": "test",
                "checkpoint": "other.safetensors",
            },
        )
        assert response.status_code == 400
        assert "allowlisted" in response.text

    asyncio.run(async_client.aclose())


@pytest.mark.asyncio
async def test_worker_client_marks_submission_timeout_ambiguous():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lost response")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://worker.invalid",
    ) as http_client:
        async with RunPodWorkerClient(
            "https://worker.invalid",
            TOKEN,
            client=http_client,
        ) as client:
            with pytest.raises(
                RunPodWorkerAmbiguousSubmissionError,
                match="will not retry",
            ):
                await client.submit(
                    workflow_id="text_to_image_v1",
                    prompt="test",
                    negative_prompt="",
                    checkpoint="model.safetensors",
                    width=1024,
                    height=1024,
                    steps=20,
                    guidance=5,
                    seed=42,
                )
