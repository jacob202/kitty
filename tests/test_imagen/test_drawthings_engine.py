"""Tests for mcp/imagen/engines/drawthings.py — HTTP stubbed."""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from mcp.imagen.config import settings


@pytest.fixture(autouse=True)
def _patch_settings():
    with patch.object(settings, "dt_url", "http://test-dt:7860"):
        yield


@pytest.fixture()
def engine():
    from mcp.imagen.engines.drawthings import DrawThingsEngine

    return DrawThingsEngine()


def test_name(engine):
    assert engine.name == "drawthings"


def test_model_name(engine):
    assert "drawthings@" in engine.model_name


def test_generate_returns_bytes(engine):
    fake_png = base64.b64encode(b"fake-png-content").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        result = engine.generate("a test prompt", seed=42)

    assert result == b"fake-png-content"
    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "/sdapi/v1/txt2img" in url
    payload = mock_post.call_args[1]["json"]
    assert payload["prompt"].startswith("a test prompt")
    assert payload["seed"] == 42
    assert payload["width"] == 512
    assert payload["height"] == 512


def test_generate_aspect_ratio(engine):
    fake_png = base64.b64encode(b"data").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        engine.generate("portrait", aspect_ratio="3:4")

    payload = mock_post.call_args[1]["json"]
    assert payload["width"] == 512
    assert payload["height"] == 682


def test_generate_custom_size(engine):
    fake_png = base64.b64encode(b"data").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        engine.generate("custom", width=1024, height=768)

    payload = mock_post.call_args[1]["json"]
    assert payload["width"] == 1024
    assert payload["height"] == 768


def test_generate_connect_error(engine):
    with patch("httpx.post", side_effect=__import__("httpx").ConnectError("No connection")):
        with pytest.raises(RuntimeError, match="Could not reach Draw Things"):
            engine.generate("test")


def test_generate_no_images(engine):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": []}

    with patch("httpx.post", return_value=mock_resp):
        from mcp.imagen.engines.base import RefusalError

        with pytest.raises(RefusalError):
            engine.generate("test")


def test_generate_http_error(engine):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal error"
    mock_resp.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
        "500", request=MagicMock(), response=mock_resp
    )

    with patch("httpx.post", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="Draw Things returned 500"):
            engine.generate("test")


def test_edit_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.edit(MagicMock(), "make it blue")


def test_generate_async(engine):
    fake_png = base64.b64encode(b"async-data").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}

    with patch("httpx.post", return_value=mock_resp):
        import asyncio

        result = asyncio.run(engine.generate_async("async test"))
    assert result == b"async-data"


def test_generate_photorealistic(engine):
    fake_png = base64.b64encode(b"data").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        engine.generate("test shot", photorealistic=True)

    payload = mock_post.call_args[1]["json"]
    assert "photorealistic" in payload["prompt"].lower()


def test_generate_non_photorealistic(engine):
    fake_png = base64.b64encode(b"data").decode()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"images": [fake_png]}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        engine.generate("a cartoon", photorealistic=False)

    payload = mock_post.call_args[1]["json"]
    assert payload["prompt"] == "a cartoon"
