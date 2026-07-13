"""Unified Memory Graph — deep module for cross-store context retrieval.

Phase 2 deepening (per
``docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md``):
the read path now exposes one entry point (``gateway.context_assembler``)
and one item shape (``Item``). The adapters return ``list[Item]``; the
``format_items`` and ``correlate`` methods are gone from the adapter
contract — formatting lives in the assembler, not in the stores. This
module still owns the per-store retrieval and the concurrent fan-in.

Public surface:

- :class:`Item` — the uniform result shape every adapter returns.
- :class:`Source` — enum of store sources, used in :attr:`Item.source`.
- :class:`StoreAdapter` — abstract base. Subclasses implement
  :meth:`name` and :meth:`fetch`. The legacy ``format_items`` and
  ``correlate`` are removed.
- :class:`GraphResult` — what :meth:`MemoryGraph.search_all` returns.
- :func:`unified_context` — convenience wrapper around
  :class:`MemoryGraph` returning a formatted string.
- :func:`_format_unified_items` — free function used by the assembler
  to render a :class:`GraphResult` as the memory section.
- :func:`_truncate_text` — token-cap aware truncation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from gateway.paths import INBOX_FILE, LOG_FILE

logger = logging.getLogger("kitty.memory_graph")

CONTEXT_TOKEN_CAP: int = 1200  # legacy default; prefer context_cap_for_model()
STORE_FETCH_TIMEOUT_SECONDS: float = 5.0

_CAP_FLOOR = 800
_CAP_CEILING = 16_000
_CAP_RATIO = 0.04  # 4% of context window → memory budget

_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "kitty-default": 128_000,
    "kitty-sonnet": 200_000,
    "kitty-default-or": 128_000,
    "deepseek/deepseek-v4-flash": 128_000,
    "deepseek/deepseek-chat": 128_000,
    "deepseek-ai/deepseek-v4-pro": 128_000,
    "deepseek/deepseek-r1": 128_000,
    "google/gemini-2.0-flash-001": 1_000_000,
    "google/gemini-2.0-flash-exp:free": 1_000_000,
    "gemini-2.5-flash-image": 1_000_000,
    "qwen/qwen3-235b-a22b:free": 128_000,
}


def context_cap_for_model(model: str | None) -> int:
    """Return memory-block token cap scaled to the model's context window."""
    if not model:
        return 4000
    window = _MODEL_CONTEXT_WINDOWS.get(model)
    if window is None:
        lower = model.lower()
        if "deepseek" in lower:
            window = 128_000
        elif "gemini" in lower:
            window = 1_000_000
        elif "claude" in lower or "sonnet" in lower or "opus" in lower:
            window = 200_000
        elif "gpt-4" in lower:
            window = 128_000
        else:
            window = 100_000
    raw = int(window * _CAP_RATIO)
    return max(_CAP_FLOOR, min(raw, _CAP_CEILING))


# --- Uniform item shape ---


class Source(str, Enum):
    """Which store an :class:`Item` came from. Stable identifier; the string
    value is what callers see in :attr:`Item.source`."""

    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    JOURNAL = "journal"
    TRACES = "traces"
    TODOS = "todos"
    INBOX = "inbox"
    MEMORY_PALACE = "memory_palace"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass
class Item:
    """The uniform shape every adapter returns.

    Attributes:
        text: The displayable text. The assembler uses this directly.
        source: Where the item came from.
        score: Optional relevance score from the underlying store. ``None``
            when the store didn't compute one.
        ts: Optional timestamp. ``None`` when the store has no concept
            of time for the item.
        metadata: Optional store-specific fields. The assembler doesn't
            read this; it's for future debugging and store-specific
            rendering. Always a dict, never ``None``.
    """

    text: str
    source: Source
    score: float | None = None
    ts: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Store Adapter Interface ---


class StoreAdapter(ABC):
    """Abstract base for memory graph stores.

    After Phase 2 the only contract is :attr:`name` and
    :meth:`fetch`. Formatting and cross-store correlation live in
    :func:`gateway.context_assembler.assemble_context` and its helpers,
    not in the adapters.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable store name. Matches the value of one of the
        :class:`Source` enum members."""
        pass

    @abstractmethod
    async def fetch(self, query: str) -> list[Item]:
        """Fetch items matching ``query``. Returns ``[]`` (not raises) on
        no data; raises on infrastructure failure so the orchestrator
        can convert it into a warning."""
        pass


# --- Store Adapters ---


class MemoryAdapter(StoreAdapter):
    """Adapter for mem0-based memory store."""

    @property
    def name(self) -> str:
        return Source.MEMORY.value

    async def fetch(self, query: str) -> list[Item]:
        from gateway.memory import search_memory

        rows = await asyncio.to_thread(search_memory, query, 5)
        items: list[Item] = []
        for m in rows:
            if not isinstance(m, dict):
                continue
            text = m.get("memory") or m.get("text") or ""
            if not text:
                continue
            items.append(
                Item(
                    text=text,
                    source=Source.MEMORY,
                    score=m.get("_score"),
                    ts=None,
                    metadata={k: v for k, v in m.items() if k not in {"memory", "text", "_score"}},
                )
            )
        return items


class KnowledgeAdapter(StoreAdapter):
    """Adapter for ChromaDB-based knowledge store."""

    @property
    def name(self) -> str:
        return Source.KNOWLEDGE.value

    async def fetch(self, query: str) -> list[Item]:
        from gateway.knowledge import search

        rows = await asyncio.to_thread(lambda: asyncio.run(search(query, limit=3)))
        items: list[Item] = []
        for c in rows:
            if not isinstance(c, dict):
                continue
            text = c.get("text") or ""
            if not text:
                continue
            items.append(
                Item(
                    text=text[:400],
                    source=Source.KNOWLEDGE,
                    score=c.get("_score"),
                    ts=None,
                    metadata={k: v for k, v in c.items() if k not in {"text", "_score"}},
                )
            )
        return items


class JournalAdapter(StoreAdapter):
    """Adapter for journal entries (SQLite-backed via journal_store)."""

    @property
    def name(self) -> str:
        return Source.JOURNAL.value

    async def fetch(self, query: str) -> list[Item]:
        from gateway.journal import search_entries

        rows = await asyncio.to_thread(search_entries, query)
        items: list[Item] = []
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            text = entry.get("entry", "")
            if not text:
                continue
            ts_raw = entry.get("ts")
            ts = (
                datetime.fromtimestamp(float(ts_raw), tz=timezone.utc)
                if isinstance(ts_raw, (int, float))
                else None
            )
            items.append(
                Item(
                    text=text[:200],
                    source=Source.JOURNAL,
                    score=entry.get("_score"),
                    ts=ts,
                    metadata={k: v for k, v in entry.items() if k not in {"entry", "ts", "_score"}},
                )
            )
        return items


class TracesAdapter(StoreAdapter):
    """Adapter for gateway activity traces."""

    @property
    def name(self) -> str:
        return Source.TRACES.value

    async def fetch(self, query: str) -> list[Item]:
        return await asyncio.to_thread(self._fetch_traces, query)

    def _fetch_traces(self, query: str) -> list[Item]:
        """Simple text-match search over recent gateway traces."""
        if not LOG_FILE.exists():
            return []
        cutoff = time.time() - 7 * 86400
        terms = query.lower().split()
        matches: list[Item] = []
        with LOG_FILE.open("r") as f:
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
                request_text = str(trace.get("user_request", "")).lower()
                score = sum(1 for t in terms if t in request_text)
                if score <= 0:
                    continue
                text = str(trace.get("user_request", ""))[:120]
                if not text:
                    continue
                matches.append(
                    Item(
                        text=text,
                        source=Source.TRACES,
                        score=float(score),
                        ts=None,
                        metadata={
                            k: v for k, v in trace.items() if k not in {"user_request", "timestamp"}
                        },
                    )
                )
        matches.sort(key=lambda i: i.score or 0.0, reverse=True)
        return matches[:5]


class TodosAdapter(StoreAdapter):
    """Adapter for todo store."""

    @property
    def name(self) -> str:
        return Source.TODOS.value

    async def fetch(self, query: str) -> list[Item]:
        from gateway.todo_store import get

        todos = await asyncio.to_thread(get)
        terms = [term for term in query.lower().split() if term]

        def _content(todo: dict[str, Any]) -> str:
            return str(todo.get("content") or "").lower()

        if not terms:
            chosen = todos[:5]
        else:
            chosen = [t for t in todos if any(term in _content(t) for term in terms)][:5]
        items: list[Item] = []
        for todo in chosen:
            text = str(todo.get("content") or "")
            if not text:
                continue
            items.append(
                Item(
                    text=text,
                    source=Source.TODOS,
                    score=None,
                    ts=None,
                    metadata={k: v for k, v in todo.items() if k != "content"},
                )
            )
        return items


class InboxAdapter(StoreAdapter):
    """Adapter for mobile-compatible quick captures."""

    @property
    def name(self) -> str:
        return Source.INBOX.value

    async def fetch(self, query: str) -> list[Item]:
        return await asyncio.to_thread(self._fetch_inbox, query)

    def _fetch_inbox(self, query: str) -> list[Item]:
        if not INBOX_FILE.exists():
            return []
        rows: list[dict[str, Any]] = []
        with INBOX_FILE.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(entry, dict):
                    rows.append(entry)

        rows = rows[-50:]
        terms = [term for term in query.lower().split() if term]
        brief_query = any(
            term in {"brief", "morning", "today", "inbox", "capture", "captures"} for term in terms
        )

        def searchable(entry: dict[str, Any]) -> str:
            raw_tags = entry.get("tags")
            tags: list[Any] = raw_tags if isinstance(raw_tags, list) else []
            return " ".join(
                [
                    str(entry.get("text") or ""),
                    str(entry.get("source") or ""),
                    str(entry.get("type") or ""),
                    str(entry.get("project") or ""),
                    " ".join(str(tag) for tag in tags),
                ]
            ).lower()

        items: list[Item] = []
        for entry in reversed(rows):
            include = False
            if brief_query and entry.get("processed") is False:
                include = True
            elif terms and any(term in searchable(entry) for term in terms):
                include = True
            elif not terms:
                include = True
            if not include:
                continue
            text = str(entry.get("text") or "")
            if not text:
                continue
            items.append(
                Item(
                    text=text[:240],
                    source=Source.INBOX,
                    score=None,
                    ts=None,
                    metadata={k: v for k, v in entry.items() if k != "text"},
                )
            )
            if len(items) >= 5:
                break
        return items


class SignalsAdapter(StoreAdapter):
    """Adapter for the P1 signal store (connector and system events)."""

    @property
    def name(self) -> str:
        return "signals"

    async def fetch(self, query: str) -> list[Item]:
        try:
            from gateway.signal_store import list_recent

            signals = await asyncio.to_thread(list_recent, 20)
            terms = [term for term in query.lower().split() if term]
            chosen = signals if not terms else [
                s for s in signals
                if any(
                    term in " ".join([
                        str(s.get("source") or ""),
                        str(s.get("kind") or ""),
                        str(s.get("payload") or ""),
                    ]).lower()
                    for term in terms
                )
            ]
            items: list[Item] = []
            for s in chosen[:5]:
                payload = s.get("payload") or {}
                summary = str(payload.get("message") or payload.get("label") or s.get("kind", ""))
                seen = "seen" if s.get("processed_at") else "unseen"
                source = s.get("source", "unknown")
                items.append(Item(
                    text=f"[{source} | {seen}] {summary[:200]}",
                    source=Source.TRACES,
                    score=None,
                    ts=None,
                    metadata={k: v for k, v in s.items() if k not in {"payload"}},
                ))
            return items
        except Exception as e:
            logger.warning("Signals fetch failed: %s", e)
            return []


class WeaveAdapter(StoreAdapter):
    """Adapter for the temporal knowledge graph (MemoryWeave)."""

    @property
    def name(self) -> str:
        return "facts"

    async def fetch(self, query: str) -> list[Item]:
        try:
            from gateway.memory_weave import get_weave

            weave = get_weave()
            results = await asyncio.to_thread(weave.search, query, limit=5)

            items: list[Item] = []

            # Check for exact conflicts on matched entities
            for q in results:
                # Basic token extraction to guess entity/relation
                parts = q.fact.split("=")
                if len(parts) == 2:
                    left_parts = parts[0].strip().split(" ", 1)
                    if len(left_parts) == 2:
                        conflict_check = weave.surface_conflict(left_parts[0], left_parts[1])
                        if conflict_check.get("has_conflict"):
                            stale_marker = " [CONFLICT DETECTED]"
                            items.append(Item(
                                text=f"{q.fact}{stale_marker} (confidence: {q.confidence:.2f}) - Warning: multiple conflicting facts exist. {conflict_check.get('recommendation', '')}",
                                source=Source.MEMORY,
                                score=q.confidence,
                                ts=datetime.fromisoformat(q.last_verified) if q.last_verified else None,
                                metadata=q.to_dict(),
                            ))
                            continue

                stale_marker = " [STALE]" if q.is_stale else ""
                items.append(Item(
                    text=f"{q.fact}{stale_marker} (confidence: {q.confidence:.2f})",
                    source=Source.MEMORY, # we use Source.MEMORY as a fallback type, or we could add FACTS to Source
                    score=q.confidence,
                    ts=datetime.fromisoformat(q.last_verified) if q.last_verified else None,
                    metadata=q.to_dict(),
                ))
            return items
        except Exception as e:
            logger.warning("Weave fetch failed: %s", e)
            return []


# --- Adapter registry ---


def _default_adapters() -> list[StoreAdapter]:
    """The active store adapters. MemPalace is appended only when enabled."""
    adapters: list[StoreAdapter] = [
        MemoryAdapter(),
        KnowledgeAdapter(),
        JournalAdapter(),
        TracesAdapter(),
        TodosAdapter(),
        InboxAdapter(),
        SignalsAdapter(),
        WeaveAdapter(),
    ]
    try:
        from gateway.mempalace_adapter import MemPalaceAdapter

        if MemPalaceAdapter.is_enabled():
            adapters.append(MemPalaceAdapter())
    except Exception as e:  # optional backend must never break the graph
        logger.warning("MemPalace adapter unavailable: %s", e)
    return adapters


# --- Memory Graph Orchestrator ---


@dataclass
class GraphResult:
    """Result of a unified graph query.

    After Phase 2, ``results`` is keyed by adapter name (string) and the
    values are ``list[Item]``. ``errors`` carries per-adapter failure
    messages for the assembler to surface as ``ContextBundle.warnings``.
    """

    results: dict[str, list[Item]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class MemoryGraph:
    """Deep memory graph module.

    High-leverage entry point for all context retrieval. The store
    adapters are implementation details; the only thing callers touch is
    :meth:`search_all` (returning a :class:`GraphResult`) and
    :meth:`unified_context` (returning a formatted string).
    """

    def __init__(self, adapters: list[StoreAdapter] | None = None):
        self._adapters = adapters or _default_adapters()

    async def unified_context(self, query: str) -> str:
        """Get unified context from all stores as a formatted string.

        Kept for callers that want the legacy single-string return shape.
        The new assemblers use :meth:`search_all` directly.
        """
        result = await self.search_all(query)
        return _format_unified_items(result.results, query=query)

    async def search_all(self, query: str) -> GraphResult:
        """Search all stores concurrently.

        Returns structured :class:`GraphResult`. Per-adapter failures
        become entries in ``GraphResult.errors`` so the caller can
        surface them; no exception escapes for store-level failures.
        """
        tasks = [
            asyncio.wait_for(
                adapter.fetch(query),
                timeout=STORE_FETCH_TIMEOUT_SECONDS,
            )
            for adapter in self._adapters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        result = GraphResult()
        for i, adapter in enumerate(self._adapters):
            res = results[i]
            if isinstance(res, Exception):
                if isinstance(res, TimeoutError):
                    logger.warning("%s fetch timed out", adapter.name)
                    result.errors.append(f"{adapter.name}: {type(res).__name__}: timed out")
                else:
                    logger.warning("%s fetch failed: %s", adapter.name, res)
                    result.errors.append(f"{adapter.name}: {type(res).__name__}: {res}")
                result.results[adapter.name] = []
            else:
                result.results[adapter.name] = res  # type: ignore[assignment]

        return result


# --- Global instance for backward compatibility ---

_graph: MemoryGraph | None = None


def _get_graph() -> MemoryGraph:
    global _graph
    if _graph is None:
        _graph = MemoryGraph()
    return _graph


# --- Public API (backward compatible) ---


async def search_all(query: str) -> GraphResult:
    """Public module-level entry point for cross-store search. Returns GraphResult."""
    return await _get_graph().search_all(query)


async def unified_context(query: str, *, _record: bool = True) -> str:
    """Return unified context from all stores as a formatted string.

    Checks the predictive prefetch cache first; on a miss, computes the context,
    caches it, and (for real asks) records the query so the prefetcher learns.
    """
    from gateway import prefetcher

    hit = prefetcher.get_cached(query)
    if hit is not None:
        return hit
    result = await _get_graph().unified_context(query)
    prefetcher.put_cached(query, result)
    if _record:
        prefetcher.record(query)
    return result


# --- Free functions used by the assembler ---


def _truncate_text(text: str, cap: int) -> str:
    """Truncate ``text`` to a rough token cap. Used by the assembler to keep
    the memory section under budget."""
    if (len(text) // 4) <= cap:
        return text
    return text[: cap * 4] + "…"


def _is_sensitive(item: Item, query_terms: set[str]) -> bool:
    """Filter out items with sensitive tags unless requested in the query."""
    if item.metadata.get("sensitivity") == "high":
        return True

    tags = item.metadata.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            tag_lower = str(tag).lower()
            if tag_lower in {"health", "location", "financial", "private", "secret", "billing"}:
                if tag_lower not in query_terms:
                    return True
    return False


def _format_unified_items(results: dict[str, list[Item]], cap: int = CONTEXT_TOKEN_CAP, query: str = "") -> str:
    """Render ``results`` (keyed by adapter name) as the memory section.

    Uses Token-Aware Budgeting and a Privacy Gate.
    """
    query_terms = set(query.lower().split())
    sections: list[str] = []
    current_tokens = 0

    for source_name, items in results.items():
        if not items:
            continue
        try:
            heading = f"## {Source(source_name).name.title().replace('_', ' ')}"
        except ValueError:
            heading = f"## {source_name.title()}"

        lines = [heading]
        heading_tokens = len(heading) // 4

        added_any = False
        for item in items[:5]: # Allow up to 5 if budget permits
            if _is_sensitive(item, query_terms):
                continue

            text = item.text.strip()
            if not text:
                continue

            item_tokens = len(text) // 4
            remaining_cap = cap - (current_tokens + heading_tokens + 2)
            if remaining_cap <= 5:
                continue

            if item_tokens > remaining_cap:
                text = _truncate_text(text, remaining_cap)
                item_tokens = len(text) // 4

            if not added_any:
                current_tokens += heading_tokens
                added_any = True

            lines.append(f"- {text}")
            current_tokens += item_tokens + 2

        if added_any:
            sections.append("\n".join(lines))

    if not sections:
        return ""
    return "\n\n".join(sections)


# --- Legacy shims for backward compatibility (tests) ---


async def _fetch_memory(query: str) -> list[Item]:
    return await MemoryAdapter().fetch(query)


async def _fetch_knowledge(query: str) -> list[Item]:
    return await KnowledgeAdapter().fetch(query)


async def _fetch_todos(query: str) -> list[Item]:
    return await TodosAdapter().fetch(query)


def _fetch_traces(query: str) -> list[Item]:
    return TracesAdapter()._fetch_traces(query)


async def _fetch_all_stores(query: str) -> dict[str, list[Item]]:
    """Legacy shim for tests."""
    result = await MemoryGraph().search_all(query)
    return result.results


def search_entries(query: str) -> list[dict[str, Any]]:
    """Legacy shim for tests — delegates to journal."""
    from gateway.journal import search_entries as journal_search

    return journal_search(query)
