"""Imagen 4 engine — Google's imagen-4.0-generate-001.

Alternative high-fidelity generation, 1-4 images at once. Allows tasteful
adult imagery (person_generation=ALLOW_ADULT); explicit content is blocked
— use ComfyUI for that.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment")
    from google import genai

    return genai.Client(api_key=api_key)


class Imagen4Engine:
    """Google Imagen 4 — batch generation of 1-4 images."""

    @property
    def name(self) -> str:
        return "imagen4"

    @property
    def model_name(self) -> str:
        return settings.imagen_model

    @retry_with_backoff(attempts=settings.retry_attempts)
    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        count: int = 1,
        **kwargs: object,
    ) -> bytes:
        """Generate one image (count>1 is handled by the batch tool, not here).

        Imagen's generate_images returns multiple images; we take the first
        so this engine fits the uniform ``generate -> bytes`` interface.
        """
        from google.genai import types

        client = _gemini_client()
        response = client.models.generate_images(
            model=settings.imagen_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                person_generation="ALLOW_ADULT",
            ),
        )
        images = response.generated_images or []
        if not images:
            raise RefusalError(
                "Imagen produced no images — the prompt was likely blocked by safety filters."
            )
        return images[0].image.image_bytes

    async def generate_async(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        **kwargs: object,
    ) -> bytes:
        return await asyncio.to_thread(
            self.generate,
            prompt,
            aspect_ratio=aspect_ratio,
            photorealistic=photorealistic,
            seed=seed,
            **kwargs,
        )

    def edit(self, image_path: Path, edit_prompt: str) -> bytes:
        """Imagen 4 does not support natural-language editing — use Nano Banana."""
        raise NotImplementedError(
            "Imagen 4 does not support editing. Use engine='nano_banana' for edit_image."
        )
