"""Draw Things engine — A1111-compatible API for local Apple Silicon generation.

Draw Things exposes an A1111-compatible HTTP API (Settings → enable API Server,
default http://127.0.0.1:7860). The /sdapi/v1/txt2img endpoint accepts the same
JSON payload as Automatic1111, making this engine compatible with any A1111-
compatible backend (Draw Things native, A1111, Forge, SD.Next, etc.).

Set ``DT_URL`` to point at the running instance.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from mcp.imagen.config import settings
from mcp.imagen.engines.adapters import DrawThingsHttpAdapter, ImagegenAdapter
from mcp.imagen.retry import retry_with_backoff


class DrawThingsEngine:
    """Local Draw Things / A1111-compatible backend via the standard txt2img API.

    The network transport is an :class:`ImagegenAdapter`; by default a live
    ``DrawThingsHttpAdapter`` is used, but a mock adapter can be injected for
    tests (Packet 025 — no server or model download needed).
    """

    def __init__(self, adapter: ImagegenAdapter | None = None) -> None:
        # Falls back to the live HTTP adapter against settings.dt_url.
        self._adapter: ImagegenAdapter = adapter or DrawThingsHttpAdapter(settings.dt_url)

    @property
    def name(self) -> str:
        return "drawthings"

    @property
    def model_name(self) -> str:
        return f"drawthings@{settings.dt_url}"

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
        sampler_name: str | None = None,
        width: int | None = None,
        height: int | None = None,
        init_image: Path | None = None,
        denoising_strength: float = 0.5,
        **kwargs: object,
    ) -> bytes:
        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")

        w, h = _aspect_to_wh(aspect_ratio, width, height)

        payload: dict = {
            "model": settings.dt_model,
            "prompt": full_prompt,
            "negative_prompt": negative_prompt or "",
            "width": w,
            "height": h,
            "steps": steps or 20,
            "cfg_scale": cfg_scale or 7.0,
            "sampler_name": sampler_name or "Euler a",
            "batch_size": 1,
        }

        endpoint = "txt2img"
        if init_image:
            import io

            from PIL import Image as PILImage
            with PILImage.open(init_image) as img:
                prepared: PILImage.Image = (
                    img.convert("RGB") if img.mode != "RGB" else img
                )
                prepared = prepared.resize(
                    (w, h), PILImage.Resampling.LANCZOS
                )
                buf = io.BytesIO()
                prepared.save(buf, format="PNG")
                img_data = base64.b64encode(buf.getvalue()).decode("utf-8")
            payload["init_images"] = [img_data]
            payload["denoising_strength"] = denoising_strength
            endpoint = "img2img"
        if seed is not None:
            payload["seed"] = seed

        images = (
            self._adapter.img2img(payload)
            if endpoint == "img2img"
            else self._adapter.txt2img(payload)
        )
        return images[0]

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
            "Draw Things / A1111 does not support natural-language editing. "
            "Use engine='nano_banana' for edit_image."
        )


def _aspect_to_wh(aspect_ratio: str, width: int | None, height: int | None) -> tuple[int, int]:
    if width is not None and height is not None:
        return width, height

    map = {
        "1:1": (512, 512),
        "3:2": (768, 512),
        "2:3": (512, 768),
        "3:4": (512, 682),
        "4:3": (682, 512),
        "4:5": (512, 640),
        "5:4": (640, 512),
        "9:16": (512, 910),
        "16:9": (910, 512),
        "21:9": (1024, 440),
    }
    return map.get(aspect_ratio, (512, 512))
