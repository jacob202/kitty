"""I/O helpers — save images, parse Gemini responses, build image parts.

These are shared across all engines and tools so the engine modules stay
focused on API calls.
"""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from mcp.imagen.config import settings


def save_image(data: bytes, prefix: str = "img", metadata: dict[str, Any] | None = None) -> Path:
    """Save raw image bytes to the output dir, return the path.

    ``metadata`` is accepted for forward-compatibility (PR 4 sidecar) but
    not yet written to disk.
    """
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    path = settings.output_dir / f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png"

    # Materialize the input before creating a temporary file.  Besides
    # normalizing bytes-like values, this ensures an invalid provider payload
    # cannot leave a partial artifact behind.
    payload = bytes(data)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=settings.output_dir,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
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
