"""Tests for mcp/imagen/engines/fal.py — HTTP stubbed, no live calls.

Fal's REST API is queue-based: submit → poll status → fetch result → fetch
the image bytes from the returned URL. Every httpx call is stubbed here.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError


@pytest.fixture()
def engine():
    from mcp.imagen.engines.fal import FalEngine

    return FalEngine()


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "test-fal-key-not-real")


@pytest.fixture(autouse=True)
def _fast_poll(monkeypatch):
    monkeypatch.setattr(settings, "fal_poll_interval_seconds", 0.0)


def _submit_resp(request_id="req-1", status_url="https://queue.fal.run/x/requests/req-1/status",
                  response_url="https://queue.fal.run/x/requests/req-1"):
    resp = MagicMock()
    resp.json.return_value = {
        "request_id": request_id,
        "status_url": status_url,
        "response_url": response_url,
    }
    resp.raise_for_status.return_value = None
    return resp


def _status_resp(status="COMPLETED"):
    resp = MagicMock()
    resp.json.return_value = {"status": status}
    resp.raise_for_status.return_value = None
    return resp


def _result_resp(image_url="https://cdn.fal.ai/out.png"):
    resp = MagicMock()
    resp.json.return_value = {"images": [{"url": image_url}]}
    resp.raise_for_status.return_value = None
    return resp


def _image_bytes_resp(data=b"fake-image-bytes"):
    resp = MagicMock()
    resp.content = data
    resp.raise_for_status.return_value = None
    return resp


def test_name(engine):
    assert engine.name == "fal"


def test_model_name(engine):
    assert engine.model_name == settings.fal_model


def test_generate_no_api_key_raises(engine, monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        engine.generate("prompt")


def test_generate_happy_path(engine):
    with (
        patch("httpx.post", return_value=_submit_resp()) as mock_post,
        patch(
            "httpx.get",
            side_effect=[_status_resp(), _result_resp(), _image_bytes_resp()],
        ) as mock_get,
    ):
        result = engine.generate("a test prompt", seed=42)

    assert result == b"fake-image-bytes"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Key test-fal-key-not-real"
    payload = kwargs["json"]
    assert payload["prompt"].startswith("a test prompt")
    assert payload["seed"] == 42
    assert mock_get.call_count == 3


def test_generate_polls_until_completed(engine):
    with (
        patch("httpx.post", return_value=_submit_resp()),
        patch(
            "httpx.get",
            side_effect=[
                _status_resp("IN_QUEUE"),
                _status_resp("IN_PROGRESS"),
                _status_resp("COMPLETED"),
                _result_resp(),
                _image_bytes_resp(),
            ],
        ) as mock_get,
    ):
        result = engine.generate("prompt")

    assert result == b"fake-image-bytes"
    assert mock_get.call_count == 5


def test_generate_poll_timeout_raises(engine, monkeypatch):
    monkeypatch.setattr(settings, "fal_poll_max_attempts", 2)
    with (
        patch("httpx.post", return_value=_submit_resp()),
        patch("httpx.get", return_value=_status_resp("IN_PROGRESS")),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            engine.generate("prompt")


def test_generate_failed_status_is_refusal(engine):
    with (
        patch("httpx.post", return_value=_submit_resp()),
        patch("httpx.get", return_value=_status_resp("FAILED")),
    ):
        with pytest.raises(RefusalError):
            engine.generate("prompt")


def test_single_identity_image_required(engine, tmp_path):
    ref_a = tmp_path / "a.png"
    ref_b = tmp_path / "b.png"
    ref_a.write_bytes(b"a")
    ref_b.write_bytes(b"b")

    with pytest.raises(ValueError, match="exactly one"):
        engine.generate("prompt", identity_images=[ref_a, ref_b])


def test_single_identity_image_sets_reference_url(engine, tmp_path):
    ref = tmp_path / "james.png"
    ref.write_bytes(b"reference-bytes")

    with (
        patch("httpx.post", return_value=_submit_resp()) as mock_post,
        patch(
            "httpx.get",
            side_effect=[_status_resp(), _result_resp(), _image_bytes_resp()],
        ),
    ):
        engine.generate("prompt", identity_images=[ref], id_weight=0.75)

    payload = mock_post.call_args.kwargs["json"]
    assert payload["reference_image_url"].startswith("data:")
    assert payload["id_weight"] == 0.75


def test_zero_identity_images_omits_reference(engine):
    with (
        patch("httpx.post", return_value=_submit_resp()) as mock_post,
        patch(
            "httpx.get",
            side_effect=[_status_resp(), _result_resp(), _image_bytes_resp()],
        ),
    ):
        engine.generate("prompt")

    payload = mock_post.call_args.kwargs["json"]
    assert "reference_image_url" not in payload


def test_edit_not_supported(engine, tmp_path):
    with pytest.raises(NotImplementedError):
        engine.edit(tmp_path / "x.png", "make it blue")


def test_generate_async_delegates(engine):
    import asyncio

    with (
        patch("httpx.post", return_value=_submit_resp()),
        patch(
            "httpx.get",
            side_effect=[_status_resp(), _result_resp(), _image_bytes_resp()],
        ),
    ):
        result = asyncio.run(engine.generate_async("prompt", seed=7))
    assert result == b"fake-image-bytes"
