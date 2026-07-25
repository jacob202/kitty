"""Abstract image backend interface with ComfyUI and Stability AI implementations."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


class ImageBackend(abc.ABC):
    """Abstract interface for an image generation backend.

    Each backend provides generation, status checks, and health probes.
    Backends register themselves so the runner can dispatch by name.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Backend identifier, e.g. 'comfyui' or 'stability_ai'."""

    @abc.abstractmethod
    async def is_available(self) -> bool:
        """Return True if the backend is reachable and healthy."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 6,
        cfg: float = 1.5,
        seed: int | None = None,
        sampler: str | None = None,
        scheduler: str | None = None,
        model_id: str | None = None,
        **extra: Any,
    ) -> GenerateResult:
        ...

    async def generate_with_character(
        self,
        prompt: str,
        *,
        character_ref_path: str,
        identity_weight: float = 0.7,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 8,
        cfg: float = 4.5,
        seed: int | None = None,
    ) -> GenerateResult:
        """Generate an image preserving a reference character's identity.
        Default implementation raises NotImplementedError.
        """
        raise NotImplementedError(f"{self.name} does not support identity generation")


@dataclass
class GenerateResult:
    image_data: bytes
    seed: int
    info: dict[str, Any] = field(default_factory=dict)


class BackendRegistry:
    """Registry of available image backends."""

    def __init__(self) -> None:
        self._backends: dict[str, ImageBackend] = {}

    def register(self, backend: ImageBackend) -> None:
        self._backends[backend.name] = backend

    def get(self, name: str) -> ImageBackend | None:
        return self._backends.get(name)

    def get_all(self) -> list[ImageBackend]:
        return list(self._backends.values())

    def names(self) -> list[str]:
        return list(self._backends)


_backend_registry = BackendRegistry()


def get_registry() -> BackendRegistry:
    return _backend_registry


def register_backend(backend: ImageBackend) -> None:
    _backend_registry.register(backend)


# ── ComfyUI Backend ──────────────────────────────────────────────────────────


class ComfyUIBackend(ImageBackend):
    """Backend that wraps gateway.image.gen for ComfyUI generation."""

    def __init__(self, timeout: int = 360) -> None:
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "comfyui"

    async def is_available(self) -> bool:
        from gateway.image.gen import is_available
        return await is_available()

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 6,
        cfg: float = 1.5,
        seed: int | None = None,
        sampler: str | None = None,
        scheduler: str | None = None,
        model_id: str | None = None,
        **extra: Any,
    ) -> GenerateResult:
        from gateway.image.gen import generate as comfy_generate

        result = await comfy_generate(prompt)
        image_path = result["filename"]
        from pathlib import Path
        image_data = Path(image_path).read_bytes()
        return GenerateResult(
            image_data=image_data,
            seed=seed or 0,
            info={"prompt_id": result.get("prompt_id", ""), "job_id": result.get("job_id", "")},
        )

    async def generate_with_character(
        self,
        prompt: str,
        *,
        character_ref_path: str,
        identity_weight: float = 0.7,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 8,
        cfg: float = 4.5,
        seed: int | None = None,
    ) -> GenerateResult:
        from gateway.image.gen import generate_with_character as comfy_generate_char

        result = await comfy_generate_char(
            prompt=prompt,
            character_ref_path=character_ref_path,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
        )
        from pathlib import Path
        image_data = Path(result["filename"]).read_bytes()
        return GenerateResult(
            image_data=image_data,
            seed=seed or 0,
            info={
                "prompt_id": result.get("prompt_id", ""),
                "job_id": result.get("job_id", ""),
                "character_weight": result.get("character_weight"),
            },
        )


# ── Stability AI Backend ─────────────────────────────────────────────────────


class StabilityAIBackend(ImageBackend):
    """Backend for Stability AI API (stability.ai REST API)."""

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.stability.ai") -> None:
        import os
        self._api_key = api_key or os.environ.get("STABILITY_AI_KEY", "")
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "stability_ai"

    async def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(
                    f"{self._base_url}/v1/user/account",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return r.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        cfg: float = 7.0,
        seed: int | None = None,
        sampler: str | None = None,
        scheduler: str | None = None,
        model_id: str | None = None,
        **extra: Any,
    ) -> GenerateResult:
        if not self._api_key:
            raise RuntimeError("Stability AI API key not configured")
        import httpx
        aspect = f"{width}:{height}"
        payload: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": aspect,
            "steps": steps,
            "cfg_scale": cfg,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed is not None:
            payload["seed"] = seed
        if model_id:
            payload["model"] = model_id

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self._base_url}/v2beta/stable-image/generate/sd3",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "image/*",
                },
                json=payload,
            )
            if r.status_code != 200:
                raise RuntimeError(
                    f"Stability AI API error ({r.status_code}): {r.text[:500]}"
                )
            return GenerateResult(
                image_data=r.content,
                seed=seed or 0,
                info={"model": model_id or "sd3"},
            )


# ── Auto-register backends at import time ────────────────────────────────────

register_backend(ComfyUIBackend())
register_backend(StabilityAIBackend())


__all__ = [
    "ImageBackend",
    "GenerateResult",
    "BackendRegistry",
    "get_registry",
    "register_backend",
    "ComfyUIBackend",
    "StabilityAIBackend",
]
