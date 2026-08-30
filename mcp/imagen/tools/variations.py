"""Variations tool — several alternates of an existing image."""

from __future__ import annotations

from pathlib import Path

from mcp.imagen.engines.base import RefusalError
from mcp.imagen.engines.nano_banana import NanoBananaEngine
from mcp.imagen.io import save_image
from mcp.server.fastmcp import Image


def variations(image_path: str, count: int = 3) -> list:
    """Produce several alternates of an existing image — same subject, varied pose,
    angle, and lighting. Good for "give me more like this one."

    Args:
        image_path: Absolute path to the source image.
        count: How many variations (1-4). Default 3.

    Returns:
        Each variation (inline) plus its saved path.
    """
    src = Path(image_path).expanduser()
    if not src.exists():
        return [f"File not found: {image_path}"]

    engine = NanoBananaEngine()
    vary_prompt = (
        "Create a variation of this image. Keep the same subject and overall style, "
        "but change the pose, camera angle, and lighting. Photorealistic."
    )

    out: list = []
    for _ in range(max(1, min(count, 4))):
        try:
            data = engine.edit(src, vary_prompt)
        except RefusalError as e:
            out.append(f"A variation failed: {e}")
            continue
        path = save_image(data, "var")
        out.append(Image(data=data, format="png"))
        out.append(f"Saved to: {path}")

    return out or ["No variations were produced."]
