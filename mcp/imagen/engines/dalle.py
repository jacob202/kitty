"""DALL-E 3 engine — OpenAI's image generation.

Best for creative/illustrative prompts, rendering text inside the image,
and strong instruction-following. No NSFW. Uses the OpenAI Python SDK.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff


def _openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


class DalleEngine:
    """OpenAI DALL-E 3 — creative/illustrative generation with text-in-image."""

    @property
    def name(self) -> str:
        return "dalle"

    @property
    def model_name(self) -> str:
        return "dall-e-3"

    @retry_with_backoff(attempts=settings.retry_attempts)
    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        size: str = "1024x1024",
        quality: str = "hd",
        **kwargs: object,
    ) -> bytes:
        """DALL-E uses ``size`` (e.g. 1024x1024) not ``aspect_ratio``.

        The tool layer maps aspect_ratio → size when the user doesn't pass
        an explicit ``size`` kwarg.
        """
        import httpx

        client = _openai_client()
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,  # type: ignore[arg-type]
            quality=quality,  # type: ignore[arg-type]
            n=1,
        )
        url = response.data[0].url
        if not url:
            raise RefusalError("DALL-E returned no image URL.")
        data = httpx.get(url, timeout=60).content
        return data

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
        """DALL-E 3 does not support natural-language editing — use Nano Banana."""
        raise NotImplementedError(
            "DALL-E 3 does not support editing. Use engine='nano_banana' for edit_image."
        )
