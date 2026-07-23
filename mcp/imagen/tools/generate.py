"""Unified generate + edit_image tools.

Replaces the 4 legacy generate_image* tools with one ``generate(prompt, engine=...)``
that dispatches to the engine registry. SHA256-keyed cache returns the same path
for identical (prompt, engine, params) inputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.imagen import cache, engines
from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.io import save_image
from mcp.imagen.logger import log
from mcp.server.fastmcp import Image


def generate(
    prompt: str,
    engine: str = "",
    aspect_ratio: str = "1:1",
    photorealistic: bool = True,
    seed: int | None = None,
    **kwargs: Any,
) -> list:
    """Generate an image from a text description.

    Args:
        prompt: What to generate. Be specific about subject, setting, lighting, mood.
        engine: One of: nano_banana (default, best photorealism), imagen4, dalle, comfyui.
        aspect_ratio: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, or 21:9.
                      DALL-E uses ``size`` instead (e.g. 1024x1024) — pass via kwargs.
        photorealistic: When True (default), appends photographic quality cues.
                        Set False for illustrations, paintings, or cartoons.
        seed: Optional reproducibility seed. seed=0 and seed=None are different cache keys.
        **kwargs: Engine-specific passthrough (e.g. size/quality for DALL-E,
                  negative_prompt/steps/cfg_scale for ComfyUI).

    Returns:
        The generated image (inline) plus the saved file path, or a structured
        refusal dict if the prompt was blocked.
    """
    eng_name = engine or settings.default_engine
    eng = engines.get(eng_name)

    cache_key = cache.key_for(
        prompt,
        eng_name,
        {"aspect_ratio": aspect_ratio, "seed": seed, "model_name": eng.model_name, **kwargs},
    )
    if settings.cache_enabled:
        if cached := cache.get(cache_key):
            data = cached.read_bytes()
            return [Image(data=data, format="png"), f"Cached: {cached}"]

    try:
        data = eng.generate(
            prompt, aspect_ratio=aspect_ratio, photorealistic=photorealistic, seed=seed, **kwargs
        )
    except RefusalError as e:
        log.warning("engine=%s refused: %s", eng_name, str(e)[:200])
        return [{"blocked": True, "reason": str(e)}]

    path = save_image(data, prefix=eng_name)
    if settings.cache_enabled:
        cache.put(cache_key, path)
    return [
        Image(data=data, format="png"),
        f"Saved to: {path}\n(pass this path to edit_image to refine it)",
    ]


def edit_image(image_path: str, edit_prompt: str, engine: str = "") -> list:
    """Edit an existing image with natural-language instructions.

    The result renders inline and is saved as a new file (the original is untouched).
    Editing is currently supported by Nano Banana only.

    Args:
        image_path: Absolute path to the source image (PNG or JPEG).
        edit_prompt: What to change, e.g. "make the background a sunset over the ocean".
        engine: Engine to use (default: nano_banana — the only engine that supports editing).

    Returns:
        The edited image (inline) plus the saved file path, or a structured refusal dict.
    """
    eng_name = engine or settings.default_engine
    eng = engines.get(eng_name)

    src = Path(image_path).expanduser()
    if not src.exists():
        return [f"File not found: {image_path}"]

    try:
        data = eng.edit(src, edit_prompt)
    except RefusalError as e:
        log.warning("engine=%s refused edit: %s", eng_name, str(e)[:200])
        return [{"blocked": True, "reason": str(e)}]
    except NotImplementedError as e:
        return [str(e)]

    path = save_image(data, prefix="edit")
    return [
        Image(data=data, format="png"),
        f"Saved to: {path}\n(pass this path back to edit_image to keep refining)",
    ]
