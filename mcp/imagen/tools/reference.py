"""Reference and avatar tools — subject consistency and compositing.

generate_with_reference: condition on 1-3 reference images (keep a subject
consistent in a new scene, or composite multiple images).
set_avatar / generate_with_avatar: pin a recurring character and drop it
into any scene without re-uploading.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.engines.nano_banana import NanoBananaEngine
from mcp.imagen.io import save_image
from mcp.server.fastmcp import Image


def generate_with_reference(reference_paths: list[str], prompt: str) -> list:
    """Generate an image conditioned on one or more reference images using Nano Banana.

    One reference → keep that subject CONSISTENT in a new scene.
    Multiple references → COMPOSITE them.

    Args:
        reference_paths: 1-3 absolute paths to reference images (PNG/JPEG).
        prompt: What to make using those references.

    Returns:
        The generated image (inline) plus the saved file path.
    """
    refs = [Path(p).expanduser() for p in reference_paths]
    missing = [str(p) for p in refs if not p.exists()]
    if missing:
        return ["Reference file(s) not found: " + ", ".join(missing)]

    engine = NanoBananaEngine()
    try:
        data = engine.generate_with_references([r for r in refs if r.exists()], prompt)
    except RefusalError as e:
        return [f"No image generated. Model said: {e}"]

    path = save_image(data, "ref")
    return [Image(data=data, format="png"), f"Saved to: {path}"]


def set_avatar(image_path: str) -> str:
    """Pin a reference image as the persistent avatar/character.

    Args:
        image_path: Absolute path to the image to use as the persistent character.

    Returns:
        Confirmation and where it was stored.
    """
    src = Path(image_path).expanduser()
    if not src.exists():
        return f"File not found: {image_path}"
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, settings.avatar_path)
    return (
        f"Avatar set from {src.name}. Use generate_with_avatar to place this character in scenes."
    )


def generate_with_avatar(prompt: str) -> list:
    """Generate an image of the pinned avatar character in a new scene.

    Args:
        prompt: The scene/action, e.g. "on a snowy mountain trail, golden hour".

    Returns:
        The generated image (inline) plus the saved file path.
    """
    if not settings.avatar_path.exists():
        return ["No avatar set yet. Call set_avatar with an image path first."]

    engine = NanoBananaEngine()
    try:
        data = engine.generate_with_references([settings.avatar_path], prompt)
    except RefusalError as e:
        return [f"No image generated. Model said: {e}"]

    path = save_image(data, "avatar")
    return [Image(data=data, format="png"), f"Saved to: {path}"]
