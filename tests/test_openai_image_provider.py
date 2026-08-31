from __future__ import annotations

import base64
import io
from types import SimpleNamespace

import pytest
from PIL import Image

from gateway import image_runner


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (512, 512), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeImages:
    def __init__(self):
        self.generate_calls = []
        self.edit_calls = []
        self.payload = base64.b64encode(b"fake-png").decode()

    async def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self.payload)], usage=None)

    async def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=self.payload)], usage=None)


class FakeClient:
    def __init__(self):
        self.images = FakeImages()


@pytest.fixture
def openai_lane(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setenv("KITTY_IMAGE_OPENAI_ENABLED", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(image_runner, "_openai_image_client", lambda: client)
    monkeypatch.setattr("gateway.paths.DATA_DIR", tmp_path)
    monkeypatch.setattr(image_runner.image_jobs, "register_canonical_artifact", lambda *a, **k: {"id": "artifact_1"})
    return client


@pytest.mark.asyncio
async def test_openai_text_to_image_uses_gpt_image_2(openai_lane):
    result = await image_runner.run("openai", "a precise product photo")
    call = openai_lane.images.generate_calls[0]
    assert call["model"] == "gpt-image-2"
    assert call["prompt"] == "a precise product photo"
    assert call["response_format"] == "b64_json"
    assert result.engine == "openai"
    assert image_runner.image_jobs.get_job(result.job_id).operation == "txt2img"


@pytest.mark.asyncio
async def test_openai_img2img_uses_high_fidelity_edit_input(openai_lane):
    parent = image_runner.image_jobs.create_job("openai", "txt2img", prompt="source")
    result = await image_runner.run(
        "openai",
        "keep the person, change only the jacket",
        source_image=_png_bytes(),
        parent_id=parent.job_id,
    )
    call = openai_lane.images.edit_calls[0]
    assert call["model"] == "gpt-image-2"
    assert call["prompt"] == "keep the person, change only the jacket"
    assert call["input_fidelity"] == "high"
    assert call["response_format"] == "b64_json"
    assert image_runner.image_jobs.get_job(result.job_id).operation == "img2img"
    assert image_runner.image_jobs.get_job(result.job_id).parent_id == parent.job_id

@pytest.mark.asyncio
async def test_openai_quality_uses_the_studio_quality_control(openai_lane):
    await image_runner.run(
        "openai", "maximum quality portrait", quality_tier="maximum"
    )
    assert openai_lane.images.generate_calls[-1]["quality"] == "high"

    await image_runner.run(
        "openai", "fast draft portrait", quality_tier="fast"
    )
    assert openai_lane.images.generate_calls[-1]["quality"] == "low"

@pytest.mark.asyncio
async def test_openai_edit_labels_reference_with_its_real_image_format(openai_lane):
    buffer = io.BytesIO()
    Image.new("RGB", (512, 512), "white").save(buffer, format="JPEG")
    parent = image_runner.image_jobs.create_job("openai", "txt2img", prompt="source")

    await image_runner.run(
        "openai", "change the background", source_image=buffer.getvalue(), parent_id=parent.job_id
    )

    uploaded = openai_lane.images.edit_calls[-1]["image"]
    assert uploaded[0].endswith(".jpg")
    assert uploaded[2] == "image/jpeg"
