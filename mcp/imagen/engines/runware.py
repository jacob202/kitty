"""Runware REST engine for FLUX generation and identity conditioning."""
from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.logger import log
from mcp.imagen.retry import retry_with_backoff

_RUNWARE_URL = "https://api.runware.ai/v1"
_SAFETY_MARKERS = ("safety", "moderation", "contentpolicy", "content_policy", "contentmoderation", "nsfw", "blocked")


class RunwareEngine:
    """Runware imageInference backend.

    PuLID is used only when explicit identity references are supplied.  LoRAs
    remain opt-in so the cheap reference-only benchmark is a real control.
    """

    @property
    def name(self) -> str:
        return "runware"

    @property
    def model_name(self) -> str:
        return settings.runware_model

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        identity_images: list[str | Path] | None = None,
        pulid_weight: float = 1.0,
        lora: list[dict[str, Any]] | None = None,
        init_image: str | Path | None = None,
        strength: float = 0.65,
        width: int | None = None,
        height: int | None = None,
        steps: int = 28,
        negative_prompt: str | None = None,
        **kwargs: object,
    ) -> bytes:
        api_key = os.environ.get("RUNWARE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Set RUNWARE_API_KEY in the environment before using Runware")

        if identity_images is not None and len(identity_images) != 1:
            raise ValueError("Runware PuLID requires exactly one identity image")
        if not 0 <= pulid_weight <= 3:
            raise ValueError("pulid_weight must be between 0 and 3")
        if not 0 <= strength <= 1:
            raise ValueError("strength must be between 0 and 1")

        w, h = _aspect_to_wh(aspect_ratio, width, height)
        full_prompt = prompt + (settings.photoreal_suffix if photorealistic else "")
        task: dict[str, Any] = {
            "taskType": "imageInference",
            "taskUUID": str(uuid.uuid4()),
            "model": settings.runware_model,
            "positivePrompt": full_prompt,
            "width": w,
            "height": h,
            "steps": steps,
            "numberResults": 1,
            "outputType": "base64Data",
            "outputFormat": "PNG",
            "includeCost": True,
        }
        if seed is not None:
            task["seed"] = seed
        if negative_prompt:
            task["negativePrompt"] = negative_prompt
        if identity_images:
            task["puLID"] = {
                "images": [_image_data_uri(Path(p).expanduser()) for p in identity_images],
                "idWeight": pulid_weight,
            }
        if lora:
            task["lora"] = lora
        if init_image is not None:
            task["inputs"] = {"seedImage": _image_data_uri(Path(init_image).expanduser())}
            task["strength"] = strength

        response = _post_with_retry(api_key, task)
        payload = _json_payload(response)
        _raise_for_errors(response, payload, task["taskUUID"])

        data = payload.get("data") or []
        if not data or not isinstance(data[0], dict):
            raise RuntimeError(f"Runware returned no image data for task {task['taskUUID']}")
        item = data[0]
        encoded = item.get("imageBase64Data")
        if not encoded:
            raise RuntimeError(f"Runware returned no base64 image for task {task['taskUUID']}")

        if isinstance(encoded, str) and encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[-1]
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise RuntimeError(f"Runware returned invalid base64 for task {task['taskUUID']}") from exc

        log.info(
            "runware task=%s model=%s cost=%s",
            task["taskUUID"],
            settings.runware_model,
            item.get("cost", "unknown"),
        )
        return image_bytes

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
            "Runware FLUX img2img is not instruction editing; use generate(..., init_image=...) "
            "for controlled img2img or a dedicated edit model."
        )


@retry_with_backoff(attempts=settings.retry_attempts)
def _post_with_retry(api_key: str, task: dict[str, Any]) -> httpx.Response:
    response = httpx.post(
        _RUNWARE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=[task],
        timeout=settings.runware_timeout,
    )
    if response.status_code == 429 or response.status_code >= 500:
        response.raise_for_status()
    return response


def _json_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Runware returned HTTP {response.status_code} with invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Runware returned an unexpected response shape")
    return payload


def _raise_for_errors(response: httpx.Response, payload: dict[str, Any], task_uuid: str) -> None:
    errors = payload.get("errors") or []
    if response.status_code < 400 and not errors:
        return

    first = errors[0] if errors and isinstance(errors[0], dict) else {}
    code = str(first.get("code", f"http_{response.status_code}"))
    message = str(first.get("message", response.text or "Runware request failed"))
    marker_text = f"{code} {message}".lower().replace(" ", "")
    if any(marker in marker_text for marker in _SAFETY_MARKERS):
        raise RefusalError(f"Runware blocked task {task_uuid}: {message}")
    raise RuntimeError(f"Runware error {code} for task {task_uuid}: {message}")


def _image_data_uri(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Reference image not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _aspect_to_wh(
    aspect_ratio: str,
    width: int | None,
    height: int | None,
) -> tuple[int, int]:
    if width is not None or height is not None:
        if width is None or height is None:
            raise ValueError("width and height must be provided together")
        if width % 64 or height % 64:
            raise ValueError("Runware FLUX width and height must be multiples of 64")
        return width, height

    sizes = {
        "1:1": (1024, 1024),
        "3:2": (1152, 768),
        "2:3": (768, 1152),
        "3:4": (768, 1024),
        "4:3": (1024, 768),
        "4:5": (768, 960),
        "5:4": (960, 768),
        "9:16": (768, 1344),
        "16:9": (1344, 768),
        "21:9": (1344, 576),
    }
    return sizes.get(aspect_ratio, sizes["1:1"])
