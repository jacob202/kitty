"""Unified Search — normalized query results across Kitty stores.

Public API:
  async_search(query) -> dict  Async search with grouped, normalized hits
  search(query) -> dict        Sync wrapper for offline scripts/tests only
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from gateway import memory_graph

logger = logging.getLogger("kitty.search")

SECTION_TO_KIND = {
    "memories": "memory",
    "knowledge": "knowledge",
    "journal": "journal",
    "todos": "todo",
}

RAW_TO_SECTION = {
    "memory": "memories",
    "memories": "memories",
    "knowledge": "knowledge",
    "journal": "journal",
    "todos": "todos",
}


def _compact(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _first_text(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = _compact(item.get(key))
        if text:
            return text
    return ""


def _score(item: dict[str, Any]) -> float | int | None:
    for key in ("score", "_score", "similarity", "relevance"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return value
    return None


def _short_title(text: str, fallback: str) -> str:
    title = " ".join(text.split())
    if not title:
        return fallback
    return title[:80]


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    hidden = {
        "memory",
        "text",
        "content",
        "entry",
        "title",
        "source",
        "score",
        "_score",
        "similarity",
        "relevance",
    }
    return {k: v for k, v in item.items() if k not in hidden}


def normalize_hit(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    """Return one stable hit shape for display and LLM context callers."""
    if kind == "memory":
        text = _first_text(item, ("text", "memory", "content"))
        source = _compact(item.get("source"), "memory")
        title = _compact(item.get("title")) or source or "Memory"
    elif kind == "knowledge":
        text = _first_text(item, ("text", "content", "chunk"))
        source = _compact(item.get("source"), "knowledge")
        title = _compact(item.get("title")) or source or "Knowledge"
    elif kind == "journal":
        text = _first_text(item, ("text", "entry", "content"))
        source = _compact(item.get("source"), "journal")
        title = (
            _compact(item.get("title")) or _compact(item.get("ts")) or "Journal entry"
        )
    elif kind == "todo":
        text = _first_text(item, ("text", "content", "title", "task"))
        source = _compact(item.get("source"), "todo")
        title = _compact(item.get("title")) or _short_title(text, "Todo")
    else:
        text = _first_text(item, ("text", "content", "entry", "memory"))
        source = _compact(item.get("source"), kind)
        title = _compact(item.get("title")) or source or kind

    return {
        "kind": kind,
        "source": source,
        "title": title,
        "text": text,
        "score": _score(item),
        "metadata": _metadata(item),
    }


async def async_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Unified async search with stable grouped hit shapes."""
    raw = await memory_graph.search_all(query)

    results: dict[str, Any] = {
        "memories": [],
        "knowledge": [],
        "journal": [],
        "todos": [],
        "query": query,
    }

    for raw_key, items in raw.items():
        section = RAW_TO_SECTION.get(raw_key)
        if not section or not isinstance(items, list):
            continue
        kind = SECTION_TO_KIND[section]
        results[section] = [
            normalize_hit(kind, item)
            for item in items[:limit]
            if isinstance(item, dict)
        ]
    return results


def search(query: str, limit: int = 5) -> dict[str, Any]:
    """Sync wrapper for offline scripts. Async routes should call async_search()."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(async_search(query, limit=limit))
    raise RuntimeError("search() cannot run inside an event loop; await async_search()")
