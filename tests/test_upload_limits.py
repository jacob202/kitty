"""Regression tests for upload size limits.

Voice and inventory uploads must enforce per-route streaming caps so
that oversized uploads are rejected with 413 instead of consuming
unbounded memory.
"""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from gateway.constants import MAX_INVENTORY_BYTES, MAX_VOICE_BYTES


def _make_upload(data: bytes, filename: str = "test.bin") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data))


@pytest.mark.asyncio
async def test_voice_upload_oversized_rejects() -> None:
    from gateway.routes.voice import audio_transcriptions

    oversized = _make_upload(b"\x00" * (MAX_VOICE_BYTES + 1), "audio.webm")
    with pytest.raises(HTTPException) as exc_info:
        await audio_transcriptions(file=oversized, model="whisper-1")
    assert exc_info.value.status_code == 413
    assert "exceeds" in exc_info.value.detail


@pytest.mark.asyncio
async def test_voice_upload_within_limit_passes() -> None:
    from unittest.mock import patch

    from gateway.routes.voice import audio_transcriptions

    small = _make_upload(b"\x00" * 1024, "audio.webm")
    with patch("gateway.stt.transcribe_bytes", return_value={"text": "ok"}):
        result = await audio_transcriptions(file=small, model="whisper-1")
    assert result["text"] == "ok"


@pytest.mark.asyncio
async def test_inventory_upload_oversized_rejects() -> None:
    from gateway.routes.kitty_tools import inventory_photo

    oversized = _make_upload(b"\xff" * (MAX_INVENTORY_BYTES + 1), "photo.jpg")
    with pytest.raises(HTTPException) as exc_info:
        await inventory_photo(file=oversized)
    assert exc_info.value.status_code == 413
    assert "exceeds" in exc_info.value.detail


def test_constants_are_sane() -> None:
    assert MAX_VOICE_BYTES > 0
    assert MAX_INVENTORY_BYTES > 0
    assert MAX_VOICE_BYTES >= 1024 * 1024  # at least 1 MB
    assert MAX_INVENTORY_BYTES >= 1024 * 1024  # at least 1 MB
