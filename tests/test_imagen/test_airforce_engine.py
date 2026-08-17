"""Tests for mcp/imagen/engines/airforce.py — HTTP stubbed, no live calls.

Airforce is an OpenAI-compatible ``images/generations`` gateway with no
reference-image identity conditioning. It must never silently drop identity
conditioning it can't honor — passing identity_images has to raise, not
generate an unconditioned image while claiming compliance.
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError


@pytest.fixture()
def engine():
    from mcp.imagen.engines.airforce import AirforceEngine

    return AirforceEngine()


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("AIRFORCE_API_KEY", "test-airforce-key-not-real")


def _b64_response(image_bytes: bytes) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": [{"b64_json": base64.b64encode(image_bytes).decode()}]}
    resp.raise_for_status.return_value = None
    return resp


def _url_response(url: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": [{"url": url}]}
    resp.raise_for_status.return_value = None
    return resp


def test_name(engine):
    assert engine.name == "airforce"


def test_model_name(engine):
    assert engine.model_name == settings.airforce_model


def test_generate_no_api_key_raises(engine, monkeypatch):
    monkeypatch.delenv("AIRFORCE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="AIRFORCE_API_KEY"):
        engine.generate("prompt")


def test_generate_b64_response(engine):
    with patch("httpx.post", return_value=_b64_response(b"fake-bytes")) as mock_post:
        result = engine.generate("a test prompt", seed=42)

    assert result == b"fake-bytes"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-airforce-key-not-real"
    payload = kwargs["json"]
    assert payload["prompt"].startswith("a test prompt")
    assert payload["model"] == settings.airforce_model


def test_generate_url_response_fetches_bytes(engine):
    with (
        patch("httpx.post", return_value=_url_response("https://cdn.airforce/out.png")),
        patch("httpx.get") as mock_get,
    ):
        mock_get.return_value = MagicMock(content=b"fetched-bytes")
        mock_get.return_value.raise_for_status.return_value = None
        result = engine.generate("prompt")

    assert result == b"fetched-bytes"
    mock_get.assert_called_once_with("https://cdn.airforce/out.png", timeout=120)


def test_download_failure_after_ack_does_not_resubmit_paid_generation(engine):
    with (
        patch("httpx.post", return_value=_url_response("https://cdn.airforce/out.png")) as mock_post,
        patch("httpx.get", side_effect=httpx.ConnectError("download failed")),
    ):
        with pytest.raises(httpx.ConnectError, match="download failed"):
            engine.generate("prompt")

    mock_post.assert_called_once()


def test_generate_no_data_is_refusal(engine):
    resp = MagicMock()
    resp.json.return_value = {"data": []}
    resp.raise_for_status.return_value = None
    with patch("httpx.post", return_value=resp):
        with pytest.raises(RefusalError):
            engine.generate("prompt")


def test_identity_images_rejected_not_silently_dropped(engine, tmp_path):
    ref = tmp_path / "james.png"
    ref.write_bytes(b"reference-bytes")

    with pytest.raises(NotImplementedError, match="identity"):
        engine.generate("prompt", identity_images=[ref])


def test_edit_not_supported(engine, tmp_path):
    with pytest.raises(NotImplementedError):
        engine.edit(tmp_path / "x.png", "make it blue")


def test_generate_async_delegates(engine):
    import asyncio

    with patch("httpx.post", return_value=_b64_response(b"async-bytes")):
        result = asyncio.run(engine.generate_async("prompt", seed=7))
    assert result == b"async-bytes"
