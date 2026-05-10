"""Context builder — assembles the two-part system prompt for every request.

Returns a (soul_prompt, dynamic_context) tuple so callers can pin the soul
prefix to a cache slot and only re-fetch the dynamic suffix on each turn.

Section headers in dynamic_context:
  [MEMORY]    — retrieved episodic memory
  [KNOWLEDGE] — retrieved knowledge base chunks

Empty sections are omitted entirely (no orphaned headers).

Both fetches run concurrently via asyncio.gather(return_exceptions=True).
A failed fetch logs a warning and returns an empty section — never a 500.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("kitty.context_builder")

# Retrieval constants — change here, not scattered through call sites
MEMORY_SIMILARITY_THRESHOLD: float = 0.7
MEMORY_TOKEN_CAP: int = 500
KNOWLEDGE_TOKEN_CAP: int = 700
SOUL_TOKEN_CAP: int = 300

MEMORY_LIMIT: int = 5
KNOWLEDGE_LIMIT: int = 3


def _rough_token_count(text: str) -> int:
    return len(text) // 4


def _truncate(text: str, cap: int) -> str:
    if _rough_token_count(text) <= cap:
        return text
    char_cap = cap * 4
    return text[:char_cap] + "…"


def _fetch_memory(query: str) -> str:
    try:
        from gateway.memory import get_context_block
        raw = get_context_block(query, limit=MEMORY_LIMIT)
        return _truncate(raw, MEMORY_TOKEN_CAP) if raw else ""
    except Exception:
        logger.warning("memory fetch failed", exc_info=True)
        return ""


def _fetch_knowledge(query: str) -> str:
    try:
        from gateway.knowledge import get_knowledge_block
        raw = get_knowledge_block(query, limit=KNOWLEDGE_LIMIT)
        return _truncate(raw, KNOWLEDGE_TOKEN_CAP) if raw else ""
    except Exception:
        logger.warning("knowledge fetch failed", exc_info=True)
        return ""


def _build_dynamic(memory: str, knowledge: str) -> str:
    parts = []
    if memory:
        parts.append(f"[MEMORY]\n{memory}")
    if knowledge:
        parts.append(f"[KNOWLEDGE]\n{knowledge}")
    return "\n\n".join(parts)


async def build_user_context(
    query: str,
    soul_prompt: str,
) -> tuple[str, str]:
    """Return (soul_prompt, dynamic_context).

    Both fetches run concurrently. Either or both may be empty strings on
    failure — the soul_prompt is always returned unchanged.
    """
    results = await asyncio.gather(
        asyncio.to_thread(_fetch_memory, query),
        asyncio.to_thread(_fetch_knowledge, query),
        return_exceptions=True,
    )

    memory = results[0] if isinstance(results[0], str) else ""
    knowledge = results[1] if isinstance(results[1], str) else ""

    if isinstance(results[0], Exception):
        logger.warning("memory fetch raised: %s", results[0])
    if isinstance(results[1], Exception):
        logger.warning("knowledge fetch raised: %s", results[1])

    if not memory and not knowledge:
        logger.warning("both context fetches failed for query=%r", query[:60])

    dynamic = _build_dynamic(memory, knowledge)
    return soul_prompt, dynamic


def assemble_system_prompt(soul_prompt: str, dynamic_context: str) -> str:
    if not dynamic_context:
        return soul_prompt
    return f"{soul_prompt}\n\n{dynamic_context}"
