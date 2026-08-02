"""Contracts for the authenticated, allowlisted Kitty Comfy worker."""

from __future__ import annotations

import asyncio
import base64
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
    RunPodWorkerConfigurationError,
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
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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


def _comfy_nodes(*, omit: str | None = None) -> dict[str, object]:
    # /health verifies every installed bundle, so the fake ComfyUI has to
    # advertise the node types all of them need — not just text-to-image's.
    required: set[str] = set()
    for workflow_id in ("text_to_image_v1", "image_to_image_v1"):
        required |= WorkflowBundle.load(
            Path("workflows"), workflow_id
        ).required_node_types
    nodes: dict[str, object] = {
        node_type: {} for node_type in required if node_type != omit
    }
    if omit != "CheckpointLoaderSimple":
        nodes["CheckpointLoaderSimple"] = {
            "input": {
                "required": {
                    "ckpt_name": [["model.safetensors"], {}],
                }
            }
        }
    return nodes


def _job_payload(*, action_id: str | None = None) -> dict[str, object]:
    return {
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
        "client_action_id": action_id,
    }


def _successful_comfy_handler(
    *,
    prompt_calls: list[int] | None = None,
    image_bytes: bytes = PNG_BYTES,
    content_type: str = "image/png",
) -> httpx.MockTransport:
    history_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal history_calls
        if request.url.path == "/object_info":
            return httpx.Response(200, json=_comfy_nodes())
        if request.url.path == "/prompt":
            if prompt_calls is not None:
                prompt_calls.append(1)
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
            return httpx.Response(
                200,
                content=image_bytes,
                headers={"content-type": content_type},
            )
        raise AssertionError(f"unexpected ComfyUI path: {request.url.path}")

    return httpx.MockTransport(handler)


def _wait_for_terminal(
    client: TestClient,
    job_id: str,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    for _ in range(100):
        response = client.get(f"/v1/jobs/{job_id}", headers=AUTH)
        payload = response.json()
        if payload["status"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    return payload


def test_workflow_bundle_binds_values_without_mutating_source():
    bundle = WorkflowBundle.load(Path("workflows"), "text_to_image_v1")
    request = JobRequest(**_job_payload())

    compiled = bundle.compile(request, "model.safetensors")

    assert compiled["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert compiled["2"]["inputs"]["text"] == "a brass robot"
    assert compiled["4"]["inputs"]["width"] == 832
    assert compiled["5"]["inputs"]["seed"] == 42
    assert bundle.workflow["2"]["inputs"]["text"] == "__PROMPT__"
    assert "VAEDecode" in bundle.required_node_types


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
    async_client = httpx.AsyncClient(
        transport=_successful_comfy_handler(),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/v1/jobs", json={}).status_code == 401

        response = client.post("/v1/jobs", headers=AUTH, json=_job_payload())
        assert response.status_code == 202
        payload = _wait_for_terminal(client, response.json()["job_id"])

        assert payload["status"] == "succeeded"
        outputs = payload["outputs"]
        assert isinstance(outputs, list)
        assert outputs[0]["sha256"]
        assert outputs[0]["width"] == 1
        assert outputs[0]["height"] == 1
        download = client.get(outputs[0]["download_url"], headers=AUTH)
        assert download.content == PNG_BYTES

    asyncio.run(async_client.aclose())


def test_duplicate_client_action_returns_same_job(tmp_path):
    prompt_calls: list[int] = []
    async_client = httpx.AsyncClient(
        transport=_successful_comfy_handler(prompt_calls=prompt_calls),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        first = client.post(
            "/v1/jobs",
            headers=AUTH,
            json=_job_payload(action_id="click-1"),
        )
        second = client.post(
            "/v1/jobs",
            headers=AUTH,
            json=_job_payload(action_id="click-1"),
        )
        assert second.status_code == 202
        assert second.json()["job_id"] == first.json()["job_id"]
        payload = _wait_for_terminal(client, first.json()["job_id"])
        assert payload["status"] == "succeeded"
        assert len(prompt_calls) == 1

    asyncio.run(async_client.aclose())


def test_duplicate_action_with_different_request_conflicts(tmp_path):
    async_client = httpx.AsyncClient(
        transport=_successful_comfy_handler(),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        first_payload = _job_payload(action_id="click-1")
        assert client.post(
            "/v1/jobs", headers=AUTH, json=first_payload
        ).status_code == 202
        changed = dict(first_payload)
        changed["prompt"] = "a different request"
        response = client.post("/v1/jobs", headers=AUTH, json=changed)
        assert response.status_code == 409

    asyncio.run(async_client.aclose())


def test_worker_rejects_corrupt_image_bytes(tmp_path):
    async_client = httpx.AsyncClient(
        transport=_successful_comfy_handler(
            image_bytes=b"<html>proxy error</html>",
            content_type="image/png",
        ),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        response = client.post("/v1/jobs", headers=AUTH, json=_job_payload())
        payload = _wait_for_terminal(client, response.json()["job_id"])
        assert payload["status"] == "failed"
        assert "not a valid image" in str(payload["error"])

    asyncio.run(async_client.aclose())


def test_worker_rejects_non_image_content_type(tmp_path):
    async_client = httpx.AsyncClient(
        transport=_successful_comfy_handler(content_type="text/html"),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        response = client.post("/v1/jobs", headers=AUTH, json=_job_payload())
        payload = _wait_for_terminal(client, response.json()["job_id"])
        assert payload["status"] == "failed"
        assert "non-image content type" in str(payload["error"])

    asyncio.run(async_client.aclose())


def test_worker_rejects_non_allowlisted_checkpoint(tmp_path):
    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
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


def test_health_marks_missing_nodes_as_permanent_configuration(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/object_info"
        return httpx.Response(200, json=_comfy_nodes(omit="VAEDecode"))

    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://comfy.invalid",
    )
    app = create_app(_config(tmp_path), client=async_client)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 424
        assert response.json()["detail"]["kind"] == "configuration"
        assert "VAEDecode" in response.text

    asyncio.run(async_client.aclose())


@pytest.mark.asyncio
async def test_worker_client_marks_configuration_failure_permanent():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            424,
            json={
                "detail": {
                    "kind": "configuration",
                    "message": "checkpoint is missing",
                }
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://worker.invalid",
    ) as http_client:
        async with RunPodWorkerClient(
            "https://worker.invalid", TOKEN, client=http_client
        ) as client:
            with pytest.raises(
                RunPodWorkerConfigurationError,
                match="checkpoint is missing",
            ):
                await client.assert_ready()


@pytest.mark.asyncio
async def test_worker_client_marks_submission_timeout_ambiguous():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("lost response")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://worker.invalid",
    ) as http_client:
        async with RunPodWorkerClient(
            "https://worker.invalid", TOKEN, client=http_client
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
