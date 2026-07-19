"""Phase 9 PDF pipeline — LlamaCloud primary, PyMuPDF fallback.

Inline image vision is opt-in because the main knowledge pipeline already has a
separate vision-enrichment stage for manuals and other high-value PDFs.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from contracts.pdf_chunk import PdfChunk
from gateway.vision import describe_schematic

logger = logging.getLogger("kitty.pdf_pipeline")

MIN_IMAGE_BYTES = 1024  # skip tiny images (icons, logos)

try:
    from llama_cloud import LlamaCloud
except ImportError:
    LlamaCloud = None


def extract_pdf_enhanced(path: Path) -> list[PdfChunk]:
    """Extract text and images from a PDF. Returns one PdfChunk per logical page/section.

    Strategy:
    1. Try LlamaCloud parsing (if LLAMA_CLOUD_API_KEY set) — structured markdown output
    2. Fall back to PyMuPDF → pdfplumber for plain text
    3. Inline image vision is off by default; use the knowledge pipeline's
       separate vision enrichment stage for manuals / high-value scans.
    """
    image_descriptions = _extract_images_with_vision(path)
    has_images = bool(image_descriptions)

    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if api_key and LlamaCloud is not None:
        try:
            text = _extract_text_llamacloud(path, api_key)
            return [
                PdfChunk(
                    page_num=0,
                    text=text,
                    image_descriptions=image_descriptions,
                    source=path.name,
                    parse_method="llamaparse",
                    has_images=has_images,
                )
            ]
        except Exception as exc:
            logger.warning("LlamaCloud parsing failed for %s: %s — falling back", path.name, exc)

    text = _extract_text_fallback(path)
    return [
        PdfChunk(
            page_num=0,
            text=text,
            image_descriptions=image_descriptions,
            source=path.name,
            parse_method="pymupdf",
            has_images=has_images,
        )
    ]


def _extract_text_llamacloud(path: Path, api_key: str) -> str:
    """Extract text via LlamaCloud parsing API (returns structured markdown)."""
    client = LlamaCloud(token=api_key)
    with open(str(path), "rb") as f:
        result = client.parsing.parse(
            upload_file=(path.name, f, "application/pdf"),
            tier="fast",
            version="latest",
        )
    if result.markdown_full:
        return result.markdown_full
    if result.markdown and result.markdown.pages:
        return "\n\n".join(page.markdown for page in result.markdown.pages)
    return ""


def _extract_text_fallback(path: Path) -> str:
    """Extract plain text using PyMuPDF, then pdfplumber as secondary fallback."""
    try:
        import fitz
        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        logger.warning("PyMuPDF extraction failed for %s", path.name)
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        logger.warning("pdfplumber extraction failed for %s", path.name)
        return ""


def _get_pdf_images(path: Path) -> list[tuple[bytes, str]]:
    """Return list of (image_bytes, mime_type) for all embedded images in the PDF."""
    try:
        import fitz
        doc = fitz.open(str(path))
        images = []
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                ext = base_image.get("ext", "png").lower()
                mime = f"image/{ext}" if ext in ("png", "jpeg", "gif", "webp") else "image/png"
                if ext == "jpg":
                    mime = "image/jpeg"
                images.append((base_image["image"], mime))
        return images
    except Exception as exc:
        logger.warning("Image extraction failed for %s: %s", path.name, exc)
        return []


def _extract_images_with_vision(path: Path) -> list[str]:
    """Describe each embedded image using Claude Sonnet vision. Skips tiny images.

    This is opt-in because bulk ingest should stay text-first by default.
    """
    if os.environ.get("KITTY_ENABLE_INLINE_PDF_VISION") != "1":
        return []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return []

    descriptions = []
    for image_bytes, mime_type in _get_pdf_images(path):
        if len(image_bytes) < MIN_IMAGE_BYTES:
            continue
        desc = describe_schematic(image_bytes, mime_type)
        if desc:
            descriptions.append(desc)
    return descriptions
