"""Fal engine — REST image generation via fal's async queue API, FLUX PuLID.

Fal's queue endpoint (``https://queue.fal.run/<model>``) is asynchronous:
submit a request, poll its status until ``COMPLETED``, then fetch the result
(a list of image URLs) and download the bytes. Auth is ``Authorization: Key
<FAL_KEY>`` (not ``Bearer``).

Schema note: written from public fal documentation/search results
(``prompt``, ``reference_image_url``, ``id_weight``, ``seed``,
``guidance_scale``); ``fal.ai`` itself was unreachable from this
environment's network egress policy at write time. Re-verify field names
against https://fal.ai/models/fal-ai/flux-pulid/api before the first live
(paid) request. Like Runware, identity conditioning is restricted to exactly
one reference image — never more.
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import time
from pathlib import Path

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff

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


class FalEngine:
    """Fal REST backend — FLUX PuLID with optional single-image identity lock."""

    @property
    def name(self) -> str:
        return "fal"

    @property
    def model_name(self) -> str:
        return settings.fal_model

    @retry_with_backoff(attempts=settings.retry_attempts)
    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        negative_prompt: str | None = None,
        guidance_scale: float | None = None,
        num_inference_steps: int | None = None,
        identity_images: list[Path | str] | None = None,
        id_weight: float = 1.0,
        **kwargs: object,
    ) -> bytes:
        """Generate one image. Raises ``RefusalError`` on a failed/blocked job.

        ``identity_images``, when given, must contain exactly one path.
        """
        if identity_images is not None and len(identity_images) != 1:
            raise ValueError(
                "Fal PuLID identity conditioning requires exactly one reference "
                f"image, got {len(identity_images)}."
            )

        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")

        payload: dict[str, object] = {"prompt": full_prompt}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        if guidance_scale is not None:
            payload["guidance_scale"] = guidance_scale
        if num_inference_steps is not None:
            payload["num_inference_steps"] = num_inference_steps
        if identity_images:
            payload["reference_image_url"] = _to_data_uri(identity_images[0])
            payload["id_weight"] = id_weight

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
            self.generate,
            prompt,
            aspect_ratio=aspect_ratio,
            photorealistic=photorealistic,
            seed=seed,
            **kwargs,
        )

    def edit(self, image_path: Path, edit_prompt: str) -> bytes:
        raise NotImplementedError(
            "Fal natural-language editing is not implemented. Use engine='nano_banana' "
            "for edit_image."
        )
