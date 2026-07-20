"""Tests for reference image quality checks."""
from __future__ import annotations

import io

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

import pytest

from gateway.image_quality import (
    check_reference_image,
)


def _png_bytes(width: int = 512, height: int = 512) -> bytes:
    img = PILImage.new("RGB", (width, height), color=(200, 180, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width: int = 512, height: int = 512) -> bytes:
    img = PILImage.new("RGB", (width, height), color=(200, 180, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestQualityChecks:
    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_valid_png_passes(self):
        result = check_reference_image(_png_bytes())
        assert not result.has_blockers
        assert result.width == 512
        assert result.height == 512
        assert result.format == "PNG"

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_valid_jpeg_passes(self):
        result = check_reference_image(_jpeg_bytes())
        assert not result.has_blockers

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_small_image_blocked(self):
        result = check_reference_image(_png_bytes(128, 128))
        assert result.has_blockers
        assert any("too small" in c.message.lower() for c in result.checks if c.severity == "blocker")

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_below_recommended_gets_warning(self):
        result = check_reference_image(_png_bytes(400, 400))
        assert result.has_warnings
        assert any("below the recommended" in c.message for c in result.checks)

    def test_corrupted_data_blocked(self):
        result = check_reference_image(b"not an image at all")
        assert result.has_blockers
        assert any("corrupted" in c.message.lower() for c in result.checks)

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_large_file_warning(self):
        large = _png_bytes()
        result = check_reference_image(large + b"\x00" * (6 * 1024 * 1024 - len(large)))
        assert result.has_warnings
        assert any("5 mb" in c.message.lower() for c in result.checks)

    def test_empty_data(self):
        result = check_reference_image(b"")
        assert result.has_blockers

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_summary_returns_string(self):
        result = check_reference_image(_png_bytes())
        assert isinstance(result.summary(), str)

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_advice_list(self):
        result = check_reference_image(_png_bytes(256, 256))
        advice = result.advice()
        assert isinstance(advice, list)

    def test_is_perfect(self):
        result = check_reference_image(_png_bytes(512, 512) if HAS_PIL else b"\x00")
        assert isinstance(result.is_perfect, bool)

    def test_filesize_recorded(self):
        data = _png_bytes() if HAS_PIL else b"\x00" * 100
        result = check_reference_image(data)
        assert result.file_size == len(data)
