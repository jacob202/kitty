"""Contract tests for the Runware image engine."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp.imagen.config import settings


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("RUNWARE_API_KEY", "test-secret")


@pytest.fixture()
def engine():
    from mcp.imagen.engines.runware import RunwareEngine

    return RunwareEngine()


def _response(payload: dict, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    response.text = "response body"
    return response


def test_identity_and_model(engine):
    assert engine.name == "runware"
    assert engine.model_name == settings.runware_model


def test_generate_posts_rest_task_and_decodes_png(engine):
    encoded = base64.b64encode(b"png-bytes").decode()
    response = _response({"data": [{"imageBase64Data": encoded, "cost": 0.004}]})

    with patch("httpx.post", return_value=response) as post:
        result = engine.generate("portrait of James", seed=42)

    assert result == b"png-bytes"
    url = post.call_args.args[0]
    kwargs = post.call_args.kwargs
    assert url == "https://api.runware.ai/v1"
    assert kwargs["headers"]["Authorization"] == "Bearer test-secret"
    task = kwargs["json"][0]
    assert task["taskType"] == "imageInference"
    assert task["model"] == settings.runware_model
    assert task["positivePrompt"].startswith("portrait of James")
    assert task["outputType"] == "base64Data"
    assert task["outputFormat"] == "PNG"
    assert task["includeCost"] is True
    assert task["numberResults"] == 1
    assert task["seed"] == 42
    assert task["width"] == task["height"] == 1024


def test_generate_adds_pulid_refs_and_lora(engine, tmp_path: Path):
    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"jpeg-ref")
    encoded = base64.b64encode(b"result").decode()
    response = _response({"data": [{"imageBase64Data": encoded}]})

    with patch("httpx.post", return_value=response) as post:
        engine.generate(
            "new scene",
            identity_images=[ref],
            pulid_weight=1.25,
            lora=[{"model": "user:james@1", "weight": 0.8}],
        )

    task = post.call_args.kwargs["json"][0]
    assert task["puLID"]["idWeight"] == 1.25
    assert task["puLID"]["images"][0].startswith("data:image/jpeg;base64,")
    assert task["lora"] == [{"model": "user:james@1", "weight": 0.8}]


def test_pulid_rejects_multiple_identity_images(engine, tmp_path: Path):
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    with pytest.raises(ValueError, match="exactly one"):
        engine.generate("test", identity_images=[a, b])


def test_generate_img2img_uses_seed_image(engine, tmp_path: Path):
    src = tmp_path / "seed.png"
    src.write_bytes(b"source-png")
    response = _response({"data": [{"imageBase64Data": base64.b64encode(b"out").decode()}]})

    with patch("httpx.post", return_value=response) as post:
        engine.generate("restyle", init_image=src, strength=0.65)

    task = post.call_args.kwargs["json"][0]
    assert task["inputs"]["seedImage"].startswith("data:image/png;base64,")
    assert "seedImage" not in task
    assert task["strength"] == 0.65


def test_missing_key_fails_before_network(engine, monkeypatch):
    monkeypatch.delenv("RUNWARE_API_KEY", raising=False)
    with patch("httpx.post") as post, pytest.raises(RuntimeError, match="RUNWARE_API_KEY"):
        engine.generate("test")
    post.assert_not_called()


def test_api_client_error_is_not_retried(engine):
    request = httpx.Request("POST", "https://api.runware.ai/v1")
    response = httpx.Response(400, request=request, json={"errors": [{"code": "invalidParameter", "message": "bad width"}]})

    with patch("httpx.post", return_value=response) as post, pytest.raises(RuntimeError, match="invalidParameter"):
        engine.generate("test")
    assert post.call_count == 1


def test_api_safety_error_becomes_refusal(engine):
    from mcp.imagen.engines.base import RefusalError

    response = _response({"errors": [{"code": "contentModeration", "message": "blocked by safety policy"}]})
    with patch("httpx.post", return_value=response), pytest.raises(RefusalError, match="blocked"):
        engine.generate("test")


def test_edit_is_not_falsely_advertised(engine, tmp_path: Path):
    src = tmp_path / "seed.png"
    src.write_bytes(b"source")
    with pytest.raises(NotImplementedError, match="generate.*init_image"):
        engine.edit(src, "change shirt")
