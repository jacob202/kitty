"""Engine protocol and shared exceptions.

Every engine implements the same interface so the tool layer can dispatch
generically by name. ``RefusalError`` lets the tool layer distinguish a
safety refusal (return structured dict to the LLM) from a transient failure
(retry or surface the error).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class RefusalError(Exception):
    """The engine returned no image — a safety filter blocked the prompt.

    The message contains the model's explanation (if any) so the LLM can
    rephrase and retry with a different prompt.
    """


@runtime_checkable
class Engine(Protocol):
    """One image-generation backend.

    ``generate`` and ``generate_async`` return raw PNG bytes on success and
    raise ``RefusalError`` when the prompt is blocked. Transient errors
    (429, 503, connection) are retried by the ``@retry_with_backoff`` decorator
    on the concrete engine; after exhausting retries the real exception
    propagates (prime directive: fail loud).
    """

    @property
    def name(self) -> str:
        """Short slug used in the registry and cache keys (e.g. ``nano_banana``)."""
        ...

    @property
    def model_name(self) -> str:
        """Upstream model id, included in cache keys for version invalidation."""
        ...

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        **kwargs: object,
    ) -> bytes:
        """Generate an image from a text prompt, return raw PNG bytes."""
        ...

    async def generate_async(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        **kwargs: object,
    ) -> bytes:
        """Async variant for batch generation."""
        ...

    def edit(self, image_path: Path, edit_prompt: str) -> bytes:
        """Edit an existing image with natural-language instructions."""
        ...
