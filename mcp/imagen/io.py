"""I/O helpers — save images, parse Gemini responses, build image parts.

These are shared across all engines and tools so the engine modules stay
focused on API calls.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from mcp.imagen.config import settings


def save_image(data: bytes, prefix: str = "img", metadata: dict[str, Any] | None = None) -> Path:
    """Save raw image bytes to the output dir, return the path.

    ``metadata`` is accepted for forward-compatibility (PR 4 sidecar) but
    not yet written to disk.
    """
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    path = settings.output_dir / f"{prefix}_{int(time.time() * 1000)}.png"
    path.write_bytes(data)
    return path


def first_image_bytes(response: object) -> bytes | None:
    """Pull raw image bytes out of a Gemini generate_content response.

    Returns None when the model returned only text (usually a safety refusal).
    """
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        parts = getattr(candidate.content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
    return None


def refusal_text(response: object) -> str:
    """Extract the text explanation from a response that produced no image."""
    candidates = getattr(response, "candidates", None) or []
    texts: list[str] = []
    for candidate in candidates:
        parts = getattr(candidate.content, "parts", None) or []
        for part in parts:
            if getattr(part, "text", None):
                texts.append(part.text)
    return " ".join(texts) if texts else "no image and no explanation returned"


def image_part(path: Path):
    """Build a Gemini image Part from a file on disk."""
    from google.genai import types

    raw = path.read_bytes()
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return types.Part.from_bytes(data=raw, mime_type=mime)
