"""Fal engine — REST image generation via fal's async queue API, FLUX PuLID.

Fal's queue endpoint (``https://queue.fal.run/<model>``) is asynchronous:
submit a request, poll its status until ``COMPLETED``, then fetch the result
(a list of image URLs) and download the bytes. Auth is ``Authorization: Key
<FAL_KEY>`` (not ``Bearer``).

The configured PuLID model requires exactly one reference image. Paid Fal
submissions are intentionally at-most-once from Kitty: once the provider has
accepted a request, polling/result/download failures must never cause a second
paid generation to be submitted automatically.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import cast

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError

FAL_QUEUE_URL = "https://queue.fal.run"

_TERMINAL_FAILURE_STATUSES = {"FAILED", "CANCELLED"}


def _api_key() -> str:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "FAL_KEY is not set. Live Fal generation is blocked until a key is "
            "configured in the environment."
        )
    return key


def _to_data_uri(path: Path | str) -> str:
    path = Path(path)
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Key {_api_key()}"}


def _fal_image_size(aspect_ratio: str) -> str | dict[str, int]:
    known: dict[str, str | dict[str, int]] = {
        "1:1": "square_hd",
        "3:2": {"width": 1216, "height": 832},
        "2:3": {"width": 832, "height": 1216},
        "3:4": "portrait_4_3",
        "4:3": "landscape_4_3",
        "4:5": {"width": 896, "height": 1088},
        "5:4": {"width": 1088, "height": 896},
        "9:16": "portrait_16_9",
        "16:9": "landscape_16_9",
        "21:9": {"width": 1536, "height": 640},
    }
    try:
        return known[aspect_ratio]
    except KeyError as exc:
        raise ValueError(f"unsupported Fal aspect ratio: {aspect_ratio}") from exc


class FalEngine:
    """Fal REST backend — FLUX PuLID with one required identity reference."""

    @property
    def name(self) -> str:
        return "fal"

    @property
    def model_name(self) -> str:
        return settings.fal_model

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        **kwargs: object,
    ) -> bytes:
        """Generate one image without automatically resubmitting paid work.

        PuLID requires exactly one identity reference. Provider submission is
        deliberately not wrapped in the shared retry decorator because a
        timeout after provider acknowledgement cannot safely prove that no
        paid generation occurred.
        """
        negative_prompt = cast(str | None, kwargs.get("negative_prompt"))
        guidance_scale = cast(float | None, kwargs.get("guidance_scale"))
        num_inference_steps = cast(int | None, kwargs.get("num_inference_steps"))
        identity_images = cast(list[Path | str] | None, kwargs.get("identity_images"))
        id_weight = cast(float, kwargs.get("id_weight", 1.0))

        if identity_images is None or len(identity_images) != 1:
            count = 0 if identity_images is None else len(identity_images)
            raise ValueError(
                "Fal PuLID identity conditioning requires exactly one reference "
                f"image, got {count}."
            )

        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")

        payload: dict[str, object] = {
            "prompt": full_prompt,
            "reference_image_url": _to_data_uri(identity_images[0]),
            "id_weight": id_weight,
            "image_size": _fal_image_size(aspect_ratio),
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        if guidance_scale is not None:
            payload["guidance_scale"] = guidance_scale
        if num_inference_steps is not None:
            payload["num_inference_steps"] = num_inference_steps

        submit = httpx.post(
            f"{FAL_QUEUE_URL}/{settings.fal_model}",
            json=payload,
            headers=_headers(),
            timeout=60,
        )
        submit.raise_for_status()
        submitted = submit.json()

        status_url = submitted.get("status_url")
        response_url = submitted.get("response_url")
        if not status_url or not response_url:
            raise RuntimeError(f"Fal returned an unexpected submit response: {submitted!r}")

        self._wait_until_complete(status_url)

        result_resp = httpx.get(response_url, headers=_headers(), timeout=60)
        result_resp.raise_for_status()
        result = result_resp.json()

        images = result.get("images") or []
        if not images or not images[0].get("url"):
            raise RefusalError("Fal returned no image — the job may have failed or been blocked.")

        image_resp = httpx.get(images[0]["url"], timeout=120)
        image_resp.raise_for_status()
        return image_resp.content

    def _wait_until_complete(self, status_url: str) -> None:
        for _ in range(settings.fal_poll_max_attempts):
            status_resp = httpx.get(status_url, headers=_headers(), timeout=30)
            status_resp.raise_for_status()
            status = status_resp.json().get("status")

            if status == "COMPLETED":
                return
            if status in _TERMINAL_FAILURE_STATUSES:
                raise RefusalError(f"Fal job ended with status {status}")

            time.sleep(settings.fal_poll_interval_seconds)

        raise RuntimeError(
            f"Fal job at {status_url} timed out after "
            f"{settings.fal_poll_max_attempts} polls"
        )

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
            lambda: self.generate(
                prompt,
                aspect_ratio=aspect_ratio,
                photorealistic=photorealistic,
                seed=seed,
                **kwargs,
            )
        )

    def edit(self, image_path: Path, edit_prompt: str) -> bytes:
        raise NotImplementedError(
            "Fal natural-language editing is not implemented. Use engine='nano_banana' "
            "for edit_image."
        )
