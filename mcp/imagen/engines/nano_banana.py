"""Nano Banana engine — Google's gemini-2.5-flash-image.

The default engine for photorealism. Does both generation and natural-language
editing with strong photorealism. Uses Gemini's generate_content with
response_modalities=["IMAGE"].
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.io import first_image_bytes, image_part, refusal_text
from mcp.imagen.retry import retry_with_backoff


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment")
    from google import genai

    return genai.Client(api_key=api_key)


class NanoBananaEngine:
    """Gemini Nano Banana (gemini-2.5-flash-image) — generation + editing."""

    @property
    def name(self) -> str:
        return "nano_banana"

    @property
    def model_name(self) -> str:
        return settings.gemini_image_model

    @retry_with_backoff(attempts=settings.retry_attempts)
    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        **kwargs: object,
    ) -> bytes:
        from google.genai import types

        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")
        client = _gemini_client()
        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        data = first_image_bytes(response)
        if data is None:
            raise RefusalError(refusal_text(response))
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

    @retry_with_backoff(attempts=settings.retry_attempts)
    def edit(self, image_path: Path, edit_prompt: str) -> bytes:
        from google.genai import types

        src = image_path.expanduser()
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src}")

        raw = src.read_bytes()
        mime = "image/jpeg" if src.suffix.lower() in (".jpg", ".jpeg") else "image/png"
        client = _gemini_client()
        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=[
                types.Part.from_bytes(data=raw, mime_type=mime),
                types.Part.from_text(text=edit_prompt),
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        data = first_image_bytes(response)
        if data is None:
            raise RefusalError(refusal_text(response))
        return data

    def edit_inline(self, image_bytes: bytes, edit_prompt: str, mime: str = "image/png") -> bytes:
        """Edit raw image bytes in memory (no file I/O). Used by the refine loop."""
        from google.genai import types

        client = _gemini_client()
        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime),
                types.Part.from_text(text=edit_prompt),
            ],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        data = first_image_bytes(response)
        if data is None:
            raise RefusalError(refusal_text(response))
        return data

    def generate_with_references(self, reference_paths: list[Path], prompt: str) -> bytes:
        """Generate conditioned on 1-3 reference images (subject consistency / compositing)."""
        from google.genai import types

        contents = [image_part(p) for p in reference_paths[:3]]
        contents.append(types.Part.from_text(text=prompt))
        client = _gemini_client()
        response = client.models.generate_content(
            model=settings.gemini_image_model,
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        data = first_image_bytes(response)
        if data is None:
            raise RefusalError(refusal_text(response))
        return data
