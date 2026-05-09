"""Phase 9 PDF pipeline — LlamaParse primary, PyMuPDF fallback, vision for images."""
from __future__ import annotations
import logging
import os
from pathlib import Path

from contracts.pdf_chunk import PdfChunk
from gateway.vision import describe_schematic

logger = logging.getLogger("kitty.pdf_pipeline")

MIN_IMAGE_BYTES = 1024  # skip tiny images (icons, logos)

try:
    from llama_parse import LlamaParse
except ImportError:
    LlamaParse = None  # type: ignore


def extract_pdf_enhanced(path: Path) -> list[PdfChunk]:
    """Extract text and images from a PDF. Returns one PdfChunk per logical page/section.

    Strategy:
    1. Try LlamaParse (if LLAMA_CLOUD_API_KEY set) — structured markdown, handles tables/headers
    2. Fall back to PyMuPDF → pdfplumber for plain text
    3. Always extract embedded images and run vision on them (if ANTHROPIC_API_KEY set)
    """
    image_descriptions = _extract_images_with_vision(path)
    has_images = bool(image_descriptions)

    api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
    if api_key and LlamaParse is not None:
        try:
            text = _extract_text_llamaparse(path, api_key)
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
            logger.warning("LlamaParse failed for %s: %s — falling back", path.name, exc)

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


def _extract_text_llamaparse(path: Path, api_key: str) -> str:
    """Extract text via LlamaParse (returns structured markdown)."""
    parser = LlamaParse(api_key=api_key, result_type="markdown")
    documents = parser.load_data(str(path))
    return "\n\n".join(doc.text for doc in documents)


def _extract_text_fallback(path: Path) -> str:
    """Extract plain text using PyMuPDF, then pdfplumber as secondary fallback."""
    try:
        import fitz
        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        pass
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
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
    """Describe each embedded image using Claude Sonnet vision. Skips tiny images."""
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
