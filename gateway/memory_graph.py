"""Unified memory graph — single query across Memory, Knowledge, Journal, Traces, and Todos.

Entry points:
- unified_context(query) -> str: The one function context_builder should call.
- search_all(query) -> dict[str, list]: Raw results from all stores for debugging/search UI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from gateway.journal import search_entries
from gateway.paths import LOGS_DIR

logger = logging.getLogger("kitty.memory_graph")

CONTEXT_TOKEN_CAP: int = 1200
STORE_KEYS = ("memory", "knowledge", "journal", "traces", "todos")

GATEWAY_LOG = LOGS_DIR / "gateway_trace.jsonl"


async def unified_context(query: str) -> str:
    """Return a single formatted context block from all stores."""
    results = await _fetch_all_stores(query)
    return _format_unified(results)


async def search_all(query: str) -> dict[str, list[dict[str, Any]]]:
    """Search all stores, return raw results keyed by store name."""
    return await _fetch_all_stores(query)


async def _fetch_all_stores(query: str) -> dict[str, list[dict[str, Any]]]:
    """Fetch from all registered stores concurrently."""
    tasks = [
        _fetch_memory(query),
        _fetch_knowledge(query),
        asyncio.to_thread(search_entries, query),
        asyncio.to_thread(_fetch_traces, query),
        _fetch_todos(query),
    ]
    mem, kn, journal, traces, todos = await asyncio.gather(
        *tasks, return_exceptions=True
    )

    out: dict[str, list[dict[str, Any]]] = {}
    out["memory"] = mem if isinstance(mem, list) else []
    out["knowledge"] = kn if isinstance(kn, list) else []
    out["journal"] = journal if isinstance(journal, list) else []
    out["traces"] = traces if isinstance(traces, list) else []
    out["todos"] = todos if isinstance(todos, list) else []

    for label, exc in [
        ("memory", mem),
        ("knowledge", kn),
        ("journal", journal),
        ("traces", traces),
        ("todos", todos),
    ]:
        if isinstance(exc, Exception):
            logger.warning("Unified fetch failed for %s: %s", label, exc)

    return out


def _format_unified(results: dict[str, list[dict[str, Any]]]) -> str:
    """Build a single context block from all store results."""
    sections: list[str] = []

    if results.get("memory"):
        lines = ["## Memory"]
        for m in results["memory"][:5]:
            text = m.get("memory", m.get("text", ""))
            if text:
                lines.append(f"- {text}")
        sections.append("\n".join(lines))

    if results.get("knowledge"):
        lines = ["## Knowledge"]
        for c in results["knowledge"][:3]:
            src = c.get("source", "unknown")
            dtype = c.get("doc_type", "general")
            text = (c.get("text") or "")[:400]
            lines.append(f"[{src} | {dtype}]\n{text}")
        sections.append("\n".join(lines))

    if results.get("journal"):
        lines = ["## Recent Journal"]
        for entry in results["journal"][:3]:
            lines.append(f"- {entry['entry'][:200]}")
        sections.append("\n".join(lines))

    if results.get("traces"):
        lines = ["## Recent Activity"]
        for trace in results["traces"][:3]:
            text = trace.get("user_request", "")[:120]
            domain = trace.get("domain_classified", "")
            lines.append(f"- [{domain}] {text}")
        sections.append("\n".join(lines))

    raw = "\n\n".join(sections)
    return _truncate(raw, CONTEXT_TOKEN_CAP)


async def _fetch_memory(query: str) -> list[dict[str, Any]]:
    try:
        from gateway.memory import search_memory

        return search_memory(query, limit=5)
    except Exception as e:
        logger.warning("Memory fetch failed in unified graph: %s", e)
        return []


async def _fetch_knowledge(query: str) -> list[dict[str, Any]]:
    try:
        from gateway.knowledge import search

        return await search(query, limit=3)
    except Exception as e:
        logger.warning("Knowledge fetch failed in unified graph: %s", e)
        return []


async def _fetch_todos(query: str, limit: int = 5) -> list[dict[str, Any]]:
    try:
        from gateway.todo_store import get

        terms = [term for term in query.lower().split() if term]
        todos = await asyncio.to_thread(get)
        if not terms:
            return todos[:limit]

        def _content(todo: dict[str, Any]) -> str:
            return str(todo.get("content") or "").lower()

        matches = [
            todo for todo in todos if any(term in _content(todo) for term in terms)
        ]
        return matches[:limit]
    except Exception as e:
        logger.warning("Todo fetch failed in unified graph: %s", e)
        return []


def _fetch_traces(query: str) -> list[dict[str, Any]]:
    """Simple text-match search over recent gateway traces."""
    try:
        if not GATEWAY_LOG.exists():
            return []
        cutoff = time.time() - 7 * 86400
        terms = query.lower().split()
        matches: list[dict[str, Any]] = []
        with GATEWAY_LOG.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if trace.get("timestamp", 0) < cutoff:
                    continue
                request_text = trace.get("user_request", "").lower()
                score = sum(1 for t in terms if t in request_text)
                if score > 0:
                    trace["_score"] = score
                    matches.append(trace)
        matches.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return matches[:5]
    except Exception as e:
        logger.warning("Trace fetch failed in unified graph: %s", e)
        return []


def _truncate(text: str, cap: int) -> str:
    if (len(text) // 4) <= cap:
        return text
    return text[: cap * 4] + "…"
