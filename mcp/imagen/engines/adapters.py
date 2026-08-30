"""Adapter interface for local image-generation servers (Packet 025).

An adapter isolates the transport (HTTP to Draw Things / A1111 / ComfyUI) from
the engine so it can be swapped for a mock in unit tests without a running
server or a ~7GB model download. The local-first pipeline talks only to this
interface; the live HTTP adapter is the only place that knows about ``httpx``.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx


@runtime_checkable
class ImagegenAdapter(Protocol):
    """Transport to a local A1111-compatible image server.

    ``txt2img`` / ``img2img`` take a standard A1111 JSON payload and return the
    generated images as raw bytes. The Draw Things engine builds the payload;
    the adapter owns the network call, so a mock adapter can stand in for a
    real server in tests.
    """

    def txt2img(self, payload: dict) -> list[bytes]:
        """Return generated images (raw bytes) for a txt2img payload."""
        ...

    def img2img(self, payload: dict) -> list[bytes]:
        """Return generated images (raw bytes) for an img2img payload."""
        ...


class DrawThingsHttpAdapter:
    """Talks to a Draw Things / A1111 server over HTTP via httpx.

    Draw Things exposes an A1111-compatible API (Settings → enable API Server).
    Because it is plain A1111 protocol, the same adapter works against any
    A1111 / Forge / SD.Next box — point ``base_url`` at a RunPod/Vast pod for
    the metered tier, no extra code.
    """

    def __init__(self, base_url: str, *, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        """Return whether the A1111-compatible server answers its health API.

        Health is intentionally a bounded probe: an offline optional engine is
        a normal status result, while generation continues to raise provider
        errors with their full response context.
        """
        try:
            response = httpx.get(
                f"{self.base_url}/sdapi/v1/samplers",
                timeout=min(self.timeout, 5.0),
            )
            return response.status_code == 200
        except httpx.RequestError:
            return False

    # The adapter is the single network boundary; retry/refusal semantics live
    # here so the engine stays a pure payload builder (prime directive: fail loud).
    def _post(self, endpoint: str, payload: dict) -> list[bytes]:
        from mcp.imagen.engines.base import RefusalError

        url = f"{self.base_url}/sdapi/v1/{endpoint}"
        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.ConnectError:
            raise RuntimeError(
                f"Could not reach Draw Things at {self.base_url}. "
                "Is the API server enabled in Draw Things Settings?"
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Draw Things returned {e.response.status_code}: {e.response.text[:200]}"
            )

        data = resp.json()
        images = data.get("images")
        if not images:
            raise RefusalError(
                "Image server returned no images — the prompt may have been blocked."
            )
        return [base64.b64decode(img) for img in images]

    def txt2img(self, payload: dict) -> list[bytes]:
        return self._post("txt2img", payload)

    def img2img(self, payload: dict) -> list[bytes]:
        return self._post("img2img", payload)


__all__ = ["ImagegenAdapter", "DrawThingsHttpAdapter", "Path"]
