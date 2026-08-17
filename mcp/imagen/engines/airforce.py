"""Airforce engine — OpenAI-compatible images/generations REST gateway.

``https://api.airforce/v1/images/generations`` is OpenAI-compatible:
``Authorization: Bearer <AIRFORCE_API_KEY>``, JSON body with ``model`` and
``prompt``, response ``data: [{b64_json | url}]``.

This gateway has no reference-image identity conditioning. Rather than
silently generating an unconditioned image while a caller believes identity
is locked, ``identity_images`` raises — the character-lock invariant must
never be quietly weakened to make a provider easier to integrate.

Schema note: written from public documentation/search results; the
``api.airforce`` domain was unreachable from this environment's network
egress policy at write time. Re-verify before the first live (paid) request.
"""

from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff

AIRFORCE_API_URL = "https://api.airforce/v1/images/generations"


def _api_key() -> str:
    key = os.environ.get("AIRFORCE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "AIRFORCE_API_KEY is not set. Live Airforce generation is blocked until a "
            "key is configured in the environment."
        )
    return key


class AirforceEngine:
    """Airforce REST backend — OpenAI-compatible, no identity conditioning."""

    @property
    def name(self) -> str:
        return "airforce"

    @property
    def model_name(self) -> str:
        return settings.airforce_model

    @retry_with_backoff(attempts=settings.retry_attempts)
    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        size: str = "1024x1024",
        identity_images: list[Path | str] | None = None,
        **kwargs: object,
    ) -> bytes:
        """Generate one image. Raises ``RefusalError`` on no image returned.

        Raises ``NotImplementedError`` if ``identity_images`` is given —
        this gateway cannot honor identity conditioning, so it refuses
        rather than pretending to.
        """
        if identity_images:
            raise NotImplementedError(
                "Airforce does not support identity conditioning. Passing "
                "identity_images would silently generate an unconditioned image "
                "under a character lock — use engine='runware' or 'fal' instead."
            )

        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")

        payload: dict[str, object] = {
            "model": settings.airforce_model,
            "prompt": full_prompt,
            "n": 1,
            "size": size,
        }
        if seed is not None:
            payload["seed"] = seed

        resp = httpx.post(
            AIRFORCE_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {_api_key()}"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
        if not data:
            raise RefusalError("Airforce returned no image — the prompt may have been blocked.")

        entry = data[0]
        if entry.get("b64_json"):
            return base64.b64decode(entry["b64_json"])
        if entry.get("url"):
            image_resp = httpx.get(entry["url"], timeout=120)
            image_resp.raise_for_status()
            return image_resp.content

        raise RefusalError("Airforce response contained no b64_json or url.")

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
        raise NotImplementedError(
            "Airforce natural-language editing is not implemented. Use "
            "engine='nano_banana' for edit_image."
        )
