"""Real reference-conditioned editing (issue #336, slice A4).

The slice's acceptance is one claim: the renderer request carries the parent
artifact as an actual workflow input, with an explicit denoise value. A fresh
text-to-image reroll whose prompt merely contains preservation words fails.

These tests pin the request/compile boundary and the worker's upload path. They
do not render anything — no ComfyUI, no GPU, no artifact. That is A6.
"""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.runpod_worker import RunPodWorkerClient, RunPodWorkerError
from workers.comfy_worker.app import (
    IMAGE_UPLOAD_PATH,
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
WORKFLOWS = Path("workflows")


def _config(tmp_path: Path, **overrides: object) -> WorkerConfig:
    values: dict[str, object] = {
        "bearer_token": TOKEN,
        "comfy_url": "http://comfy.invalid",
        "workflow_root": WORKFLOWS,
        "job_root": tmp_path / "jobs",
        "comfy_input_root": tmp_path / "comfy-input",
        "default_checkpoint": "model.safetensors",
        "allowed_checkpoints": frozenset({"model.safetensors"}),
        "generation_timeout_seconds": 2,
        "poll_interval_seconds": 0.001,
    }
    values.update(overrides)
    return WorkerConfig(**values)  # type: ignore[arg-type]


def _edit_payload(source_image_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "workflow_id": "image_to_image_v1",
        "prompt": "keep the face, broader build",
        "negative_prompt": "blurry",
        "checkpoint": "model.safetensors",
        "steps": 18,
        "guidance": 4.5,
        "seed": 42,
        "count": 1,
        "source_image_id": source_image_id,
        "denoise": 0.45,
    }
    payload.update(overrides)
    return payload


def _stored_image_id(client: TestClient) -> str:
    response = client.post(IMAGE_UPLOAD_PATH, headers=AUTH, content=PNG_BYTES)
    assert response.status_code == 201, response.text
    return str(response.json()["image_id"])


class TestBundle:
    def test_bundle_loads_and_hash_pins(self):
        bundle = WorkflowBundle.load(WORKFLOWS, "image_to_image_v1")

        assert bundle.workflow_id == "image_to_image_v1"
        assert bundle.consumes_source_image is True
        assert "LoadImage" in bundle.required_node_types
        assert "VAEEncode" in bundle.required_node_types

    def test_text_to_image_bundle_does_not_consume_a_source_image(self):
        assert (
            WorkflowBundle.load(WORKFLOWS, "text_to_image_v1").consumes_source_image
            is False
        )

    def test_tampering_with_the_edit_workflow_is_detected(self, tmp_path: Path):
        root = tmp_path / "workflows"
        shutil.copytree(WORKFLOWS / "image_to_image_v1", root / "image_to_image_v1")
        path = root / "image_to_image_v1" / "workflow-api.json"
        workflow = json.loads(path.read_text(encoding="utf-8"))
        workflow["6"]["inputs"]["denoise"] = 1.0
        path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")

        with pytest.raises(WorkerConfigurationError, match="hash mismatch"):
            WorkflowBundle.load(root, "image_to_image_v1")


class TestCompiledRequest:
    def test_compiled_workflow_carries_the_source_image_and_denoise(self):
        """A4's acceptance: the parent artifact is an actual workflow input."""
        bundle = WorkflowBundle.load(WORKFLOWS, "image_to_image_v1")
        image_id = f"{'a' * 64}.png"
        request = JobRequest(**_edit_payload(image_id))

        compiled = bundle.compile(request, "model.safetensors")

        assert compiled["4"]["class_type"] == "LoadImage"
        assert compiled["4"]["inputs"]["image"] == image_id
        assert compiled["6"]["inputs"]["denoise"] == 0.45
        # The sampler starts from the encoded source image, not an empty latent.
        assert compiled["6"]["inputs"]["latent_image"] == ["5", 0]
        assert compiled["5"]["class_type"] == "VAEEncode"
        assert compiled["5"]["inputs"]["pixels"] == ["4", 0]
        # The loaded bundle is a template and must survive compilation unchanged.
        assert bundle.workflow["4"]["inputs"]["image"] == "__SOURCE_IMAGE__"

    def test_a_reroll_with_preservation_words_has_no_source_image_input(self):
        """The explicit fail case: prompt language is not an edit."""
        bundle = WorkflowBundle.load(WORKFLOWS, "text_to_image_v1")
        request = JobRequest(
            workflow_id="text_to_image_v1",
            prompt="keep his face exactly the same, broader build",
            checkpoint="model.safetensors",
        )

        compiled = bundle.compile(request, "model.safetensors")

        assert not any(
            node.get("class_type") == "LoadImage" for node in compiled.values()
        )
        assert compiled["5"]["inputs"]["denoise"] == 1.0
        assert compiled["5"]["inputs"]["latent_image"] == ["4", 0]
        assert compiled["4"]["class_type"] == "EmptyLatentImage"

    def test_compiling_an_edit_without_a_source_image_raises(self):
        bundle = WorkflowBundle.load(WORKFLOWS, "image_to_image_v1")
        request = JobRequest(
            workflow_id="image_to_image_v1",
            prompt="broader build",
            checkpoint="model.safetensors",
        )

        with pytest.raises(WorkerConfigurationError, match="needs a source image"):
            bundle.compile(request, "model.safetensors")


class TestRequestValidation:
    @pytest.mark.parametrize(
        "value",
        [
            "../../etc/passwd",
            "/etc/passwd",
            "subdir/abc.png",
            "not-a-hash.png",
            f"{'a' * 64}.exe",
            f"{'A' * 64}.png",
            f"{'a' * 63}.png",
        ],
    )
    def test_source_image_id_must_be_worker_issued(self, value: str):
        with pytest.raises(ValueError, match="issued by POST"):
            JobRequest(
                workflow_id="image_to_image_v1",
                prompt="x",
                source_image_id=value,
            )

    def test_blank_source_image_id_becomes_none(self):
        request = JobRequest(
            workflow_id="image_to_image_v1", prompt="x", source_image_id="  "
        )
        assert request.source_image_id is None

    @pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
    def test_denoise_is_bounded_and_finite(self, value: float):
        with pytest.raises(ValueError):
            JobRequest(workflow_id="image_to_image_v1", prompt="x", denoise=value)

    def test_denoise_defaults_to_a_full_render(self):
        assert JobRequest(workflow_id="text_to_image_v1", prompt="x").denoise == 1.0


class TestUploadEndpoint:
    def test_upload_requires_auth(self, tmp_path: Path):
        with TestClient(create_app(_config(tmp_path))) as client:
            assert client.post(IMAGE_UPLOAD_PATH, content=PNG_BYTES).status_code == 401

    def test_upload_stores_by_content_hash_and_is_idempotent(self, tmp_path: Path):
        config = _config(tmp_path)
        with TestClient(create_app(config)) as client:
            first = client.post(IMAGE_UPLOAD_PATH, headers=AUTH, content=PNG_BYTES)
            second = client.post(IMAGE_UPLOAD_PATH, headers=AUTH, content=PNG_BYTES)

        assert first.status_code == 201
        assert first.json()["image_id"] == second.json()["image_id"]
        assert first.json()["media_type"] == "image/png"
        stored = list(config.comfy_input_root.iterdir())
        assert [p.name for p in stored] == [first.json()["image_id"]]

    def test_upload_rejects_bytes_that_are_not_an_image(self, tmp_path: Path):
        with TestClient(create_app(_config(tmp_path))) as client:
            response = client.post(
                IMAGE_UPLOAD_PATH, headers=AUTH, content=b"not an image"
            )
        assert response.status_code == 400
        assert "not a valid image" in response.text

    def test_upload_rejects_an_oversized_image(self, tmp_path: Path):
        with TestClient(create_app(_config(tmp_path, max_image_bytes=32))) as client:
            response = client.post(IMAGE_UPLOAD_PATH, headers=AUTH, content=PNG_BYTES)
        assert response.status_code == 413

    def test_json_routes_keep_the_small_request_cap(self, tmp_path: Path):
        """The upload cap must not become a hole for oversized job payloads."""
        config = _config(tmp_path, max_request_bytes=256, max_image_bytes=1_000_000)
        with TestClient(create_app(config)) as client:
            response = client.post(
                "/v1/jobs",
                headers=AUTH,
                json=_edit_payload(f"{'a' * 64}.png", prompt="x" * 4000),
            )
        assert response.status_code == 413


class TestJobCoupling:
    def test_edit_job_is_accepted_with_a_stored_source_image(self, tmp_path: Path):
        with TestClient(create_app(_config(tmp_path))) as client:
            image_id = _stored_image_id(client)
            response = client.post(
                "/v1/jobs", headers=AUTH, json=_edit_payload(image_id)
            )

        assert response.status_code == 202, response.text
        body = response.json()
        assert body["request"]["source_image_id"] == image_id
        assert body["request"]["denoise"] == 0.45
        assert body["workflow_sha256"] == (
            WorkflowBundle.load(WORKFLOWS, "image_to_image_v1").workflow_sha256
        )

    def test_edit_workflow_without_a_source_image_is_refused(self, tmp_path: Path):
        payload = _edit_payload(f"{'a' * 64}.png")
        payload.pop("source_image_id")
        with TestClient(create_app(_config(tmp_path))) as client:
            response = client.post("/v1/jobs", headers=AUTH, json=payload)

        assert response.status_code == 400
        assert "requires source_image_id" in response.text

    def test_source_image_against_a_text_only_workflow_is_refused(
        self, tmp_path: Path
    ):
        """Accepting this would return a reroll dressed as an edit."""
        with TestClient(create_app(_config(tmp_path))) as client:
            image_id = _stored_image_id(client)
            response = client.post(
                "/v1/jobs",
                headers=AUTH,
                json=_edit_payload(image_id, workflow_id="text_to_image_v1"),
            )

        assert response.status_code == 400
        assert "cannot consume a source image" in response.text

    def test_unstored_source_image_is_refused(self, tmp_path: Path):
        with TestClient(create_app(_config(tmp_path))) as client:
            response = client.post(
                "/v1/jobs", headers=AUTH, json=_edit_payload(f"{'b' * 64}.png")
            )

        assert response.status_code == 404
        assert "is not stored" in response.text


class TestHealthEnumeratesWorkflows:
    def test_health_reports_every_installed_bundle(self, tmp_path: Path):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/object_info"
            required: set[str] = set()
            for workflow_id in ("text_to_image_v1", "image_to_image_v1"):
                required |= WorkflowBundle.load(
                    WORKFLOWS, workflow_id
                ).required_node_types
            nodes: dict[str, object] = {name: {} for name in required}
            nodes["CheckpointLoaderSimple"] = {
                "input": {"required": {"ckpt_name": [["model.safetensors"], {}]}}
            }
            return httpx.Response(200, json=nodes)

        app = create_app(
            _config(tmp_path),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        with TestClient(app) as client:
            body = client.get("/health").json()

        assert body["workflows"] == ["image_to_image_v1", "text_to_image_v1"]
        assert body["edit_workflows"] == ["image_to_image_v1"]

    def test_health_fails_when_the_edit_workflow_nodes_are_missing(
        self, tmp_path: Path
    ):
        """A worker missing LoadImage must not report healthy for editing."""

        def handler(request: httpx.Request) -> httpx.Response:
            bundle = WorkflowBundle.load(WORKFLOWS, "text_to_image_v1")
            nodes: dict[str, object] = {
                name: {} for name in bundle.required_node_types
            }
            nodes["CheckpointLoaderSimple"] = {
                "input": {"required": {"ckpt_name": [["model.safetensors"], {}]}}
            }
            return httpx.Response(200, json=nodes)

        app = create_app(
            _config(tmp_path),
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 424
        assert "LoadImage" in response.text

    def test_health_fails_when_no_bundle_is_installed(self, tmp_path: Path):
        app = create_app(_config(tmp_path, workflow_root=tmp_path / "empty"))
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 424
        assert "no workflow bundle is installed" in response.text


class TestClientSchema:
    @pytest.mark.asyncio
    async def test_upload_returns_the_worker_issued_id(self):
        image_id = f"{'c' * 64}.png"

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/images"
            assert request.headers["Authorization"] == f"Bearer {TOKEN}"
            assert request.content == PNG_BYTES
            return httpx.Response(
                201,
                json={
                    "image_id": image_id,
                    "sha256": "c" * 64,
                    "media_type": "image/png",
                    "size_bytes": len(PNG_BYTES),
                    "width": 1,
                    "height": 1,
                },
            )

        async with RunPodWorkerClient(
            "http://worker.invalid",
            TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ) as client:
            image = await client.upload_source_image(PNG_BYTES, media_type="image/png")

        assert image.image_id == image_id
        assert image.width == 1

    @pytest.mark.asyncio
    async def test_submit_sends_the_source_image_and_denoise(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(202, json={"job_id": "job-1", "status": "queued"})

        async with RunPodWorkerClient(
            "http://worker.invalid",
            TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ) as client:
            await client.submit(
                workflow_id="image_to_image_v1",
                prompt="keep the face, broader build",
                negative_prompt="",
                checkpoint="model.safetensors",
                width=1024,
                height=1024,
                steps=18,
                guidance=4.5,
                seed=42,
                source_image_id=f"{'d' * 64}.png",
                denoise=0.45,
            )

        assert captured["source_image_id"] == f"{'d' * 64}.png"
        assert captured["denoise"] == 0.45

    @pytest.mark.asyncio
    async def test_a_plain_generate_omits_the_edit_fields(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(202, json={"job_id": "job-1", "status": "queued"})

        async with RunPodWorkerClient(
            "http://worker.invalid",
            TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        ) as client:
            await client.submit(
                workflow_id="text_to_image_v1",
                prompt="a brass robot",
                negative_prompt="",
                checkpoint="model.safetensors",
                width=1024,
                height=1024,
                steps=18,
                guidance=4.5,
                seed=42,
            )

        assert "source_image_id" not in captured
        assert "denoise" not in captured

    @pytest.mark.asyncio
    async def test_a_source_image_without_denoise_is_refused_client_side(self):
        async with RunPodWorkerClient(
            "http://worker.invalid",
            TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: None)),
        ) as client:
            with pytest.raises(RunPodWorkerError, match="denoise strength"):
                await client.submit(
                    workflow_id="image_to_image_v1",
                    prompt="broader build",
                    negative_prompt="",
                    checkpoint="model.safetensors",
                    width=1024,
                    height=1024,
                    steps=18,
                    guidance=4.5,
                    seed=42,
                    source_image_id=f"{'d' * 64}.png",
                )

    @pytest.mark.asyncio
    async def test_denoise_without_a_source_image_is_refused_client_side(self):
        async with RunPodWorkerClient(
            "http://worker.invalid",
            TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: None)),
        ) as client:
            with pytest.raises(RunPodWorkerError, match="only to an edit"):
                await client.submit(
                    workflow_id="text_to_image_v1",
                    prompt="a brass robot",
                    negative_prompt="",
                    checkpoint="model.safetensors",
                    width=1024,
                    height=1024,
                    steps=18,
                    guidance=4.5,
                    seed=42,
                    denoise=0.45,
                )

    @pytest.mark.asyncio
    async def test_empty_upload_is_refused_before_any_request(self):
        async with RunPodWorkerClient(
            "http://worker.invalid",
            TOKEN,
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: None)),
        ) as client:
            with pytest.raises(RunPodWorkerError, match="empty source image"):
                await client.upload_source_image(b"")
