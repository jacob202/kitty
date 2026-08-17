"""Runware engine — REST image generation with FLUX + PuLID identity conditioning.

Runware's REST API (``https://api.runware.ai/v1``) takes a JSON array of
tasks (each with its own ``taskUUID``) and returns a JSON array of results
under ``data``. FLUX PuLID identity conditioning here is intentionally
restricted to exactly one reference image — the character-locked pipeline
this engine feeds never has more than one approved reference, and silently
accepting several would let unlocked photos leak into conditioning.

The request shape is pinned to Runware's current FLUX.1 [dev] API reference:
``inputs.seedImage`` for img2img, ``safety.checkContent`` for content safety,
``lora: [{model, weight}]``, and ``puLID: {images, idWeight, ...}``.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import uuid
from pathlib import Path

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff

RUNWARE_API_URL = "https://api.runware.ai/v1"

_REFUSAL_MARKERS = ("nsfw", "flagged", "safety", "blocked", "policy", "refus")


def _api_key() -> str:
    key = os.environ.get("RUNWARE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "RUNWARE_API_KEY is not set. Live Runware generation is blocked until a "
            "rotated key is configured in the environment — do not reuse a previously "
            "committed/burned key."
        )
    return key


def _to_data_uri(path: Path | str) -> str:
    path = Path(path)
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _is_refusal(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


class RunwareEngine:
    """Runware REST backend — FLUX with optional single-image PuLID identity lock."""

    @property
    def name(self) -> str:
        return "runware"

    @property
    def model_name(self) -> str:
        return settings.runware_model

    @retry_with_backoff(attempts=settings.retry_attempts)
    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        negative_prompt: str | None = None,
        steps: int | None = None,
        cfg_scale: float | None = None,
        width: int | None = None,
        height: int | None = None,
        init_image: Path | str | None = None,
        strength: float = 0.5,
        identity_images: list[Path | str] | None = None,
        id_weight: float = 0.8,
        lora: list[dict[str, object]] | None = None,
        **kwargs: object,
    ) -> bytes:
        """Generate one image. Raises ``RefusalError`` on a safety block.

        ``identity_images``, when given, must contain exactly one path — FLUX
        PuLID identity conditioning is enforced single-reference here.
        """
        if identity_images is not None and len(identity_images) != 1:
            raise ValueError(
                "Runware PuLID identity conditioning requires exactly one reference "
                f"image, got {len(identity_images)}."
            )

        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")
        w, h = _aspect_to_wh(aspect_ratio, width, height)

        task: dict[str, object] = {
            "taskType": "imageInference",
            "taskUUID": str(uuid.uuid4()),
            "positivePrompt": full_prompt,
            "model": settings.runware_model,
            "width": w,
            "height": h,
            "numberResults": 1,
            "outputType": "base64Data",
            "outputFormat": "PNG",
            "safety": {"checkContent": True},
        }
        if negative_prompt:
            task["negativePrompt"] = negative_prompt
        if steps is not None:
            task["steps"] = steps
        if cfg_scale is not None:
            task["CFGScale"] = cfg_scale
        if seed is not None:
            task["seed"] = seed
        if lora:
            task["lora"] = lora

        if init_image is not None:
            task["inputs"] = {"seedImage": _to_data_uri(init_image)}
            task["strength"] = strength

        if identity_images:
            task["puLID"] = {
                "images": [_to_data_uri(identity_images[0])],
                "idWeight": id_weight,
            }

        result = self._post([task])[0]

        error = result.get("error") or result.get("errorMessage")
        if error:
            message = str(error)
            if _is_refusal(message):
                raise RefusalError(message)
            raise RuntimeError(f"Runware task failed: {message}")

        b64 = result.get("imageBase64Data")
        if not isinstance(b64, str) or not b64:
            raise RefusalError("Runware returned no image — the prompt may have been blocked.")
        return base64.b64decode(b64)

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
        """Not implemented — Runware's ``seedImage`` is strength-guided img2img,
        not natural-language instruction editing. Do not call this a natural-
        language edit until it genuinely is one.
        """
        raise NotImplementedError(
            "Runware does not support natural-language editing. seedImage/strength "
            "img2img is available via generate(init_image=...), not edit()."
        )

    def _post(self, tasks: list[dict[str, object]]) -> list[dict[str, object]]:
        key = _api_key()
        resp = httpx.post(
            RUNWARE_API_URL,
            json=tasks,
            headers={"Authorization": f"Bearer {key}"},
            timeout=120,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if 400 <= status < 500 and status != 429:
                if status in {401, 403}:
                    raise RuntimeError(
                        "Runware authentication failed. Check RUNWARE_API_KEY and use a rotated key."
                    ) from e
                raise RuntimeError(f"Runware request rejected with HTTP {status}") from e
            raise

        payload = resp.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Runware returned an unexpected response shape: {payload!r}")
        return data


def _aspect_to_wh(aspect_ratio: str, width: int | None, height: int | None) -> tuple[int, int]:
    if width is not None and height is not None:
        return width, height

    ratio_map = {
        "1:1": (1024, 1024),
        "3:2": (1216, 832),
        "2:3": (832, 1216),
        "3:4": (896, 1152),
        "4:3": (1152, 896),
        "4:5": (896, 1088),
        "5:4": (1088, 896),
        "9:16": (768, 1344),
        "16:9": (1344, 768),
        "21:9": (1536, 640),
    }
    return ratio_map.get(aspect_ratio, (1024, 1024))
