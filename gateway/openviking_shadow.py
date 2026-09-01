"""Optional local OpenViking retrieval for Kitty context assembly.

Default mode is ``off``. ``shadow`` performs retrieval and logs a receipt but
returns no prompt content. ``context`` returns a small bounded block suitable
for the existing enrichment seam. Failures are deliberately non-fatal.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import httpx

from gateway.http_client import get_http_client

logger = logging.getLogger("kitty.openviking_shadow")

DEFAULT_URL = "http://127.0.0.1:1933"
DEFAULT_URI = "viking://resources/kitty-kb"
DEFAULT_LIMIT = 4
DEFAULT_MAX_CHARS_PER_HIT = 1800


@dataclass(frozen=True)
class Hit:
    uri: str
    score: float
    content: str


@dataclass(frozen=True)
class RetrievalResult:
    hits: tuple[Hit, ...]
    latency_ms: float


def _mode() -> str:
    value = os.getenv("KITTY_OPENVIKING_MODE", "off").strip().lower()
    return value if value in {"off", "shadow", "context"} else "off"


async def retrieve(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    max_chars_per_hit: int = DEFAULT_MAX_CHARS_PER_HIT,
) -> RetrievalResult:
    url = os.getenv("KITTY_OPENVIKING_URL", DEFAULT_URL).rstrip("/")
    target_uri = os.getenv("KITTY_OPENVIKING_URI", DEFAULT_URI)
    client = await get_http_client()
    started = time.perf_counter()
    response = await client.post(
        f"{url}/api/v1/search/find",
        json={
            "query": query,
            "target_uri": target_uri,
            "context_type": "resource",
            "limit": max(1, min(int(limit), 8)),
            "read_content": True,
            "level": 2,
        },
        timeout=2.0,
    )
    response.raise_for_status()
    payload = response.json()
    resources = (payload.get("result") or {}).get("resources") or []
    hits: list[Hit] = []
    for item in resources:
        uri = str(item.get("uri") or "")
        if not uri:
            continue
        content = str(item.get("content") or "")[: max(0, max_chars_per_hit)]
        hits.append(Hit(uri=uri, score=float(item.get("score") or 0.0), content=content))
    return RetrievalResult(hits=tuple(hits), latency_ms=(time.perf_counter() - started) * 1000.0)


async def context_block(message: str) -> str | None:
    mode = _mode()
    if mode == "off" or not message.strip():
        return None
    try:
        result = await retrieve(message)
    except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
        logger.warning("OpenViking retrieval failed mode=%s: %s", mode, exc)
        return None

    logger.info(
        "OpenViking retrieval mode=%s hits=%d latency_ms=%.1f top_uri=%s",
        mode,
        len(result.hits),
        result.latency_ms,
        result.hits[0].uri if result.hits else "",
    )
    if mode == "shadow" or not result.hits:
        return None

    lines = ["[OpenViking engineering context]"]
    for hit in result.hits:
        lines.append(f"Source: {hit.uri} (score={hit.score:.3f})")
        if hit.content:
            lines.append(hit.content)
    return "\n".join(lines)
