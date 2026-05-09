"""Tests for Phase 9 PDF pipeline."""
import pytest
from unittest.mock import patch, MagicMock


def test_pdf_chunk_schema():
    from contracts.pdf_chunk import PdfChunk
    chunk = PdfChunk(page_num=0, text="Voltage regulator circuit.", source="schematic.pdf")
    assert chunk.parse_method == "pymupdf"
    assert chunk.has_images is False
    assert chunk.image_descriptions == []


def test_pdf_chunk_combined_text_no_images():
    from contracts.pdf_chunk import PdfChunk
    chunk = PdfChunk(page_num=0, text="Hello world.", source="doc.pdf")
    assert chunk.combined_text() == "Hello world."


def test_pdf_chunk_combined_text_with_images():
    from contracts.pdf_chunk import PdfChunk
    chunk = PdfChunk(
        page_num=0,
        text="See figure below.",
        source="doc.pdf",
        image_descriptions=["A 555 timer circuit with resistors R1=10kΩ and R2=4.7kΩ."],
        has_images=True,
    )
    combined = chunk.combined_text()
    assert "See figure below." in combined
    assert "[Image 1 description]" in combined
    assert "555 timer" in combined


def test_extract_pdf_enhanced_fallback_no_api_key(tmp_path, monkeypatch):
    """Falls back to basic text when LLAMA_CLOUD_API_KEY is absent."""
    monkeypatch.delenv("LLAMA_CLOUD_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    pdf_path = tmp_path / "test.pdf"
    mock_text = "Page one content about resistors."

    with patch("gateway.pdf_pipeline._extract_text_fallback", return_value=mock_text), \
         patch("gateway.pdf_pipeline._extract_images_with_vision", return_value=[]):
        from gateway.pdf_pipeline import extract_pdf_enhanced
        chunks = extract_pdf_enhanced(pdf_path)

    assert len(chunks) == 1
    assert chunks[0].text == mock_text
    assert chunks[0].parse_method == "pymupdf"
    assert chunks[0].image_descriptions == []


def test_extract_pdf_enhanced_with_llamaparse(tmp_path, monkeypatch):
    """Uses LlamaParse when LLAMA_CLOUD_API_KEY is set."""
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "test-llama-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    pdf_path = tmp_path / "schematic.pdf"
    pdf_path.write_bytes(b"fake-pdf")

    mock_doc = MagicMock()
    mock_doc.text = "# Page 1\n\nVoltage regulator with LM7805."
    mock_parser = MagicMock()
    mock_parser.load_data.return_value = [mock_doc]

    with patch("gateway.pdf_pipeline.LlamaParse", return_value=mock_parser), \
         patch("gateway.pdf_pipeline._extract_images_with_vision", return_value=[]):
        from gateway.pdf_pipeline import extract_pdf_enhanced
        chunks = extract_pdf_enhanced(pdf_path)

    assert len(chunks) == 1
    assert "LM7805" in chunks[0].text
    assert chunks[0].parse_method == "llamaparse"


def test_extract_images_with_vision_calls_vision(tmp_path, monkeypatch):
    """_extract_images_with_vision() calls describe_schematic for each image."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_image = b"\x89PNG\r\n" + b"\x00" * 2048  # 2KB fake PNG

    with patch("gateway.pdf_pipeline.describe_schematic", return_value="A voltage regulator.") as mock_vision, \
         patch("gateway.pdf_pipeline._get_pdf_images", return_value=[(fake_image, "image/png")]):
        from gateway.pdf_pipeline import _extract_images_with_vision
        from pathlib import Path
        descriptions = _extract_images_with_vision(Path(tmp_path / "test.pdf"))

    assert descriptions == ["A voltage regulator."]
    mock_vision.assert_called_once()


def test_extract_images_skips_tiny_images(tmp_path, monkeypatch):
    """_extract_images_with_vision() skips images smaller than MIN_IMAGE_BYTES."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    tiny_image = b"\x89PNG\r\n" + b"\x00" * 50  # tiny, likely a logo/icon

    with patch("gateway.pdf_pipeline.describe_schematic", return_value="ignored") as mock_vision, \
         patch("gateway.pdf_pipeline._get_pdf_images", return_value=[(tiny_image, "image/png")]):
        from gateway.pdf_pipeline import _extract_images_with_vision
        from pathlib import Path
        descriptions = _extract_images_with_vision(Path(tmp_path / "test.pdf"))

    assert descriptions == []
    mock_vision.assert_not_called()
