"""Batch generation tool — N prompts concurrently via asyncio.gather.

10x speedup for parallel work. Individual failures surface as error strings
in the result list; the batch continues. A semaphore limits concurrency to
avoid rate-limiting (default 10).
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.imagen import engines
from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.io import save_image
from mcp.imagen.logger import log
from mcp.server.fastmcp import Image


async def batch_generate(
    prompts: list[str],
    engine: str = "",
    aspect_ratio: str = "1:1",
    photorealistic: bool = True,
    concurrency_limit: int = 0,
    **kwargs: Any,
) -> list:
    """Generate N images in parallel. Returns N [Image, path] pairs.

    Failures on individual prompts return an error string in the result list;
    the batch continues. Use this when you need several different prompts at once
    (e.g. "generate these three scenes: a, b, c").

    Args:
        prompts: List of text prompts to generate.
        engine: One of: nano_banana (default), imagen4, dalle, comfyui.
        aspect_ratio: Aspect ratio for all images in the batch.
        photorealistic: Whether to append photographic quality cues.
        concurrency_limit: Max parallel calls (default 10, from settings).
                          Lower this if hitting rate limits.
        **kwargs: Engine-specific passthrough.

    Returns:
        A flat list alternating [Image, path_string, Image, path_string, ...]
        for successes and error strings for failures.
    """
    eng_name = engine or settings.default_engine
    eng = engines.get(eng_name)
    limit = concurrency_limit or settings.batch_concurrency_limit
    sem = asyncio.Semaphore(limit)

    async def _one(prompt: str) -> bytes:
        async with sem:
            await asyncio.sleep(0.1)  # spread out the burst
            return await eng.generate_async(
                prompt, aspect_ratio=aspect_ratio, photorealistic=photorealistic, **kwargs
            )

    results = await asyncio.gather(*(_one(p) for p in prompts), return_exceptions=True)

    out: list = []
    for prompt, result in zip(prompts, results):
        if isinstance(result, RefusalError):
            out.append(f"FAILED: {prompt[:80]!r}: blocked — {str(result)[:100]}")
            continue
        if isinstance(result, Exception):
            log.warning("batch prompt failed: %s", str(result)[:200])
            out.append(f"FAILED: {prompt[:80]!r}: {str(result)[:100]}")
            continue
        path = save_image(
            result, prefix=f"batch-{eng_name}", metadata={"batch_prompt": prompt[:200]}
        )
        out.append(Image(data=result, format="png"))
        out.append(f"Saved: {path} (for prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''})")
    return out
