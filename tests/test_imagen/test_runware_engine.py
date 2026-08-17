"""Tests for mcp/imagen/engines/runware.py — HTTP stubbed, no live calls."""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError


@pytest.fixture()
def engine():
    from mcp.imagen.engines.runware import RunwareEngine

    return RunwareEngine()


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("RUNWARE_API_KEY", "test-key-not-real")


def _ok_response(image_b64: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": [{"taskType": "imageInference", "imageBase64Data": image_b64}]}
    resp.raise_for_status.return_value = None
    return resp


def test_name(engine):
    assert engine.name == "runware"


def test_model_name(engine):
    assert engine.model_name == settings.runware_model


def test_generate_returns_bytes(engine):
    b64 = base64.b64encode(b"fake-png-bytes").decode()
    with patch("httpx.post", return_value=_ok_response(b64)) as mock_post:
        result = engine.generate("a test prompt", seed=42)

    assert result == b"fake-png-bytes"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    task = kwargs["json"][0]
    assert task["taskType"] == "imageInference"
    assert task["positivePrompt"].startswith("a test prompt")
    assert task["seed"] == 42
    assert task["model"] == settings.runware_model
    assert task["outputType"] == "URL"
    assert task["safety"] == {"checkContent": True}
    assert "checkNSFW" not in task
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-not-real"



def test_generate_url_response_downloads_bytes(engine):
    resp = MagicMock()
    resp.json.return_value = {
        "data": [{"taskType": "imageInference", "imageURL": "https://im.runware.ai/x.jpg"}]
    }
    resp.raise_for_status.return_value = None
    image_resp = MagicMock()
    image_resp.content = b"downloaded-image"
    image_resp.raise_for_status.return_value = None

    with patch("httpx.post", return_value=resp), patch("httpx.get", return_value=image_resp) as mock_get:
        result = engine.generate("prompt")

    assert result == b"downloaded-image"
    mock_get.assert_called_once_with("https://im.runware.ai/x.jpg", timeout=120, follow_redirects=True)


def test_generate_url_404_fails_cleanly_without_regenerating(engine):
    api_resp = MagicMock()
    api_resp.json.return_value = {
        "data": [{"taskType": "imageInference", "imageURL": "https://im.runware.ai/missing.jpg"}]
    }
    api_resp.raise_for_status.return_value = None
    request = httpx.Request("GET", "https://im.runware.ai/missing.jpg")
    response = httpx.Response(404, request=request)
    image_resp = MagicMock()
    image_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=request, response=response
    )

    with patch("httpx.post", return_value=api_resp) as mock_post, patch(
        "httpx.get", return_value=image_resp
    ) as mock_get:
        with pytest.raises(RuntimeError, match="image download failed with HTTP 404"):
            engine.generate("prompt")

    mock_post.assert_called_once()
    mock_get.assert_called_once()


def test_generate_url_503_retries_download_without_regenerating(engine):
    api_resp = MagicMock()
    api_resp.json.return_value = {
        "data": [{"taskType": "imageInference", "imageURL": "https://im.runware.ai/retry.jpg"}]
    }
    api_resp.raise_for_status.return_value = None
    request = httpx.Request("GET", "https://im.runware.ai/retry.jpg")
    response = httpx.Response(503, request=request)
    bad = MagicMock()
    bad.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Service Unavailable", request=request, response=response
    )
    good = MagicMock()
    good.raise_for_status.return_value = None
    good.content = b"download-recovered"

    with patch("httpx.post", return_value=api_resp) as mock_post, patch(
        "httpx.get", side_effect=[bad, good]
    ) as mock_get:
        result = engine.generate("prompt")

    assert result == b"download-recovered"
    mock_post.assert_called_once()
    assert mock_get.call_count == 2

def test_generate_no_api_key_raises(engine, monkeypatch):
    monkeypatch.delenv("RUNWARE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="RUNWARE_API_KEY"):
        engine.generate("prompt")


def test_generate_missing_image_is_refusal(engine):
    resp = MagicMock()
    resp.json.return_value = {"data": [{"taskType": "imageInference"}]}
    resp.raise_for_status.return_value = None
    with patch("httpx.post", return_value=resp):
        with pytest.raises(RefusalError):
            engine.generate("prompt")


def test_generate_error_field_nsfw_is_refusal(engine):
    resp = MagicMock()
    resp.json.return_value = {
        "data": [{"taskType": "imageInference", "error": "content flagged as NSFW"}]
    }
    resp.raise_for_status.return_value = None
    with patch("httpx.post", return_value=resp):
        with pytest.raises(RefusalError):
            engine.generate("prompt")


def test_generate_error_field_other_raises_runtime_error(engine):
    resp = MagicMock()
    resp.json.return_value = {
        "data": [{"taskType": "imageInference", "error": "internal server error"}]
    }
    resp.raise_for_status.return_value = None
    with patch("httpx.post", return_value=resp):
        with pytest.raises(RuntimeError, match="internal server error"):
            engine.generate("prompt")


def test_single_identity_image_required(engine, tmp_path):
    ref_a = tmp_path / "a.png"
    ref_b = tmp_path / "b.png"
    ref_a.write_bytes(b"a")
    ref_b.write_bytes(b"b")

    with pytest.raises(ValueError, match="exactly one"):
        engine.generate("prompt", identity_images=[ref_a, ref_b])


def test_single_identity_image_accepted(engine, tmp_path):
    ref = tmp_path / "james.png"
    ref.write_bytes(b"reference-bytes")
    b64 = base64.b64encode(b"out").decode()

    with patch("httpx.post", return_value=_ok_response(b64)) as mock_post:
        engine.generate("prompt", identity_images=[ref], id_weight=0.9)

    task = mock_post.call_args.kwargs["json"][0]
    assert "puLID" in task
    assert len(task["puLID"]["inputImages"]) == 1
    assert task["puLID"]["idWeight"] == 0.9
    assert task["puLID"]["inputImages"][0].startswith("data:")
    assert "images" not in task["puLID"]


def test_zero_identity_images_omits_pulid(engine):
    b64 = base64.b64encode(b"out").decode()
    with patch("httpx.post", return_value=_ok_response(b64)) as mock_post:
        engine.generate("prompt")

    task = mock_post.call_args.kwargs["json"][0]
    assert "puLID" not in task


def test_init_image_uses_nested_seed_image(engine, tmp_path):
    src = tmp_path / "seed.png"
    src.write_bytes(b"seed-bytes")
    b64 = base64.b64encode(b"out").decode()

    with patch("httpx.post", return_value=_ok_response(b64)) as mock_post:
        engine.generate("prompt", init_image=src, strength=0.4)

    task = mock_post.call_args.kwargs["json"][0]
    assert task["inputs"]["seedImage"].startswith("data:")
    assert "seedImage" not in task
    assert task["strength"] == 0.4


def test_lora_passthrough(engine):
    b64 = base64.b64encode(b"out").decode()
    lora = [{"model": "runware:120@2", "weight": 0.8}]
    with patch("httpx.post", return_value=_ok_response(b64)) as mock_post:
        engine.generate("prompt", lora=lora)

    task = mock_post.call_args.kwargs["json"][0]
    assert task["lora"] == lora


def test_edit_not_supported(engine, tmp_path):
    with pytest.raises(NotImplementedError):
        engine.edit(tmp_path / "x.png", "make it blue")


def test_generate_async_delegates(engine):
    import asyncio

    b64 = base64.b64encode(b"async-out").decode()
    with patch("httpx.post", return_value=_ok_response(b64)):
        result = asyncio.run(engine.generate_async("prompt", seed=7))
    assert result == b"async-out"


def test_unexpected_response_shape_raises(engine):
    resp = MagicMock()
    resp.json.return_value = {"data": []}
    resp.raise_for_status.return_value = None
    with patch("httpx.post", return_value=resp):
        with pytest.raises(RuntimeError, match="unexpected response shape"):
            engine.generate("prompt")



def test_http_400_is_retried_and_can_recover(engine):
    request = httpx.Request("POST", "https://api.runware.ai/v1")
    response = httpx.Response(400, request=request)
    status_error = httpx.HTTPStatusError("400 Bad Request", request=request, response=response)
    bad = MagicMock()
    bad.raise_for_status.side_effect = status_error
    good = _ok_response(base64.b64encode(b"recovered").decode())

    with patch("httpx.post", side_effect=[bad, good]) as mock_post:
        result = engine.generate("prompt")

    assert result == b"recovered"
    assert mock_post.call_count == 2

def test_non_retryable_auth_error_is_not_retried(engine):
    request = httpx.Request("POST", "https://api.runware.ai/v1")
    response = httpx.Response(401, request=request)
    status_error = httpx.HTTPStatusError(
        "401 Unauthorized", request=request, response=response
    )
    resp = MagicMock()
    resp.raise_for_status.side_effect = status_error

    with patch("httpx.post", return_value=resp) as mock_post:
        with pytest.raises(RuntimeError, match="authentication failed"):
            engine.generate("prompt")

    mock_post.assert_called_once()
