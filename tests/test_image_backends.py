"""Tests for the abstract image backend interface and implementations."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.image.backends import (
    BackendRegistry,
    ComfyUIBackend,
    GenerateResult,
    StabilityAIBackend,
    get_registry,
)


def test_backend_registry():
    reg = BackendRegistry()
    mock = MagicMock()
    mock.name = "test_backend"
    reg.register(mock)
    assert reg.get("test_backend") is mock
    assert "test_backend" in reg.names()


def test_get_registry_returns_singleton():
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


class TestComfyUIBackend:
    @pytest.mark.asyncio
    async def test_name(self):
        backend = ComfyUIBackend()
        assert backend.name == "comfyui"

    @pytest.mark.asyncio
    async def test_is_available(self):
        with patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=True):
            backend = ComfyUIBackend()
            assert await backend.is_available()

    @pytest.mark.asyncio
    async def test_is_available_false(self):
        with patch("gateway.image_gen.is_available", new_callable=AsyncMock, return_value=False):
            backend = ComfyUIBackend()
            assert not await backend.is_available()

    @pytest.mark.asyncio
    async def test_generate(self, tmp_path):
        out_path = tmp_path / "out.png"
        out_path.write_bytes(b"fake-png-data")
        with (
            patch("gateway.image_gen.generate", new_callable=AsyncMock) as mock_gen,
        ):
            mock_gen.return_value = {
                "prompt_id": "p123",
                "filename": str(out_path),
                "job_id": "job_abc",
            }
            backend = ComfyUIBackend()
            result = await backend.generate("a cat")
            assert isinstance(result, GenerateResult)
            assert result.image_data == b"fake-png-data"

    @pytest.mark.asyncio
    async def test_generate_with_character(self, tmp_path):
        out_path = tmp_path / "char_out.png"
        out_path.write_bytes(b"char-png-data")
        with patch(
            "gateway.image_gen.generate_with_character", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = {
                "prompt_id": "p_char",
                "filename": str(out_path),
                "job_id": "job_char",
                "character_weight": 0.7,
            }
            backend = ComfyUIBackend()
            result = await backend.generate_with_character(
                "draw my character", character_ref_path=str(tmp_path / "ref.png")
            )
            assert result.image_data == b"char-png-data"
            assert result.info.get("character_weight") == 0.7


class TestStabilityAIBackend:
    @pytest.mark.asyncio
    async def test_name(self):
        backend = StabilityAIBackend(api_key="test-key")
        assert backend.name == "stability_ai"

    @pytest.mark.asyncio
    async def test_is_available_no_key(self):
        backend = StabilityAIBackend(api_key="")
        assert not await backend.is_available()

    @pytest.mark.asyncio
    async def test_is_available_with_key(self):
        backend = StabilityAIBackend(api_key="test-key")
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = MagicMock(status_code=200)
        with patch("httpx.AsyncClient", return_value=mock_client):
            assert await backend.is_available()

    @pytest.mark.asyncio
    async def test_generate_no_key_raises(self):
        backend = StabilityAIBackend(api_key="")
        with pytest.raises(RuntimeError, match="API key not configured"):
            await backend.generate("test")

    @pytest.mark.asyncio
    async def test_generate_success(self):
        backend = StabilityAIBackend(api_key="test-key")
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"stable-png-data"
        mock_client.post.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await backend.generate("a landscape")
            assert result.image_data == b"stable-png-data"


def test_comfyui_registered():
    reg = get_registry()
    backend = reg.get("comfyui")
    assert backend is not None
    assert backend.name == "comfyui"


def test_stability_ai_registered():
    reg = get_registry()
    backend = reg.get("stability_ai")
    assert backend is not None
    assert backend.name == "stability_ai"
