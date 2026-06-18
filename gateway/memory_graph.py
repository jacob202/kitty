"""Unified Memory Graph — deep module for cross-store context retrieval.

This is a DEEP module. Callers should only use:
- unified_context(query) -> str: High-leverage entry point for context building.
- search_all(query) -> dict: Raw results from all stores for debugging.

Internal store adapters (Memory, Knowledge, Journal, Traces, Todos, Inbox) are
implementation details. The module provides:
1. Unified query interface across active stores
2. Cross-store correlation (find related entities across stores)
3. Concurrent fetching with graceful degradation
4. Token-aware truncation

Depth principle: A lot of behaviour (stores + correlation) behind a small
interface (unified_context, search_all).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol

from gateway.paths import INBOX_FILE, LOGS_DIR

logger = logging.getLogger("kitty.memory_graph")

CONTEXT_TOKEN_CAP: int = 1200
STORE_FETCH_TIMEOUT_SECONDS: float = 5.0
GATEWAY_LOG = LOGS_DIR / "gateway_trace.jsonl"


# --- Store Adapter Interface ---


class StoreAdapter(ABC):
    """Abstract base for all memory graph stores.

    Each store implements:
    - fetch(query): Get relevant items from this store
    - format(items): Format items for context injection
    - correlate(items, other_stores): Find cross-store relationships
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable store name."""
        pass

    @abstractmethod
    async def fetch(self, query: str) -> list[dict[str, Any]]:
        """Fetch items matching query."""
        pass

    @abstractmethod
    def format_items(self, items: list[dict[str, Any]]) -> str:
        """Format items for context injection."""
        pass

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """Find cross-store correlations.

        Args:
            items: This store's fetched items
            all_results: Results from all stores (for cross-reference)

        Returns:
            List of correlation notes (e.g., "3 related journal entries found")
        """
        # Default: no correlation
        return []


# --- Store Adapters ---


class MemoryAdapter(StoreAdapter):
    """Adapter for mem0-based memory store."""

    @property
    def name(self) -> str:
        return "memory"

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        try:
            from gateway.memory import search_memory

            return await asyncio.to_thread(search_memory, query, 5)
        except Exception as e:
            logger.warning("Memory fetch failed: %s", e)
            return []

    def format_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = ["## Memory"]
        for m in items[:5]:
            text = m.get("memory", m.get("text", ""))
            if text:
                lines.append(f"- {text}")
        return "\n".join(lines)

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """Find correlations with journal and knowledge."""
        correlations = []
        if items and all_results.get("journal"):
            count = len(all_results["journal"])
            if count > 0:
                correlations.append(f"{count} related journal entries")
        if items and all_results.get("knowledge"):
            count = len(all_results["knowledge"])
            if count > 0:
                correlations.append(f"{count} related knowledge chunks")
        return correlations


class KnowledgeAdapter(StoreAdapter):
    """Adapter for ChromaDB-based knowledge store."""

    @property
    def name(self) -> str:
        return "knowledge"

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        try:
            from gateway.knowledge import search

            return await asyncio.to_thread(
                lambda: asyncio.run(search(query, limit=3))
            )
        except Exception as e:
            logger.warning("Knowledge fetch failed: %s", e)
            return []

    def format_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = ["## Knowledge"]
        for c in items[:3]:
            src = c.get("source", "unknown")
            dtype = c.get("doc_type", "general")
            text = (c.get("text") or "")[:400]
            lines.append(f"[{src} | {dtype}]\n{text}")
        return "\n".join(lines)

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """Find correlations with memory and traces."""
        correlations = []
        if items and all_results.get("memory"):
            count = len(all_results["memory"])
            if count > 0:
                correlations.append(f"Supported by {count} memory entries")
        return correlations


class JournalAdapter(StoreAdapter):
    """Adapter for journal entries (JSONL-based)."""

    @property
    def name(self) -> str:
        return "journal"

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        try:
            from gateway.journal import search_entries
            # Run in executor since it's synchronous
            return await asyncio.to_thread(search_entries, query)
        except Exception as e:
            logger.warning("Journal fetch failed: %s", e)
            return []

    def format_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = ["## Recent Journal"]
        for entry in items[:3]:
            lines.append(f"- {entry.get('entry', '')[:200]}")
        return "\n".join(lines)

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """Find correlations with traces (same timestamp range)."""
        correlations = []
        if items and all_results.get("traces"):
            # Check for temporal correlation
            traces = all_results["traces"]
            if traces:
                correlations.append(f"Concurrent with {len(traces)} activity traces")
        return correlations


class TracesAdapter(StoreAdapter):
    """Adapter for gateway activity traces."""

    @property
    def name(self) -> str:
        return "traces"

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        try:
            return await asyncio.to_thread(self._fetch_traces, query)
        except Exception as e:
            logger.warning("Trace fetch failed: %s", e)
            return []

    def _fetch_traces(self, query: str) -> list[dict[str, Any]]:
        """Simple text-match search over recent gateway traces."""
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

    def format_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = ["## Recent Activity"]
        for trace in items[:3]:
            text = trace.get("user_request", "")[:120]
            domain = trace.get("domain_classified", "")
            lines.append(f"- [{domain}] {text}")
        return "\n".join(lines)

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """Find correlations with knowledge (domain-based)."""
        correlations = []
        if items and all_results.get("knowledge"):
            domains = set(t.get("domain_classified", "") for t in items if t.get("domain_classified"))
            if domains:
                correlations.append(f"Domains: {', '.join(domains)}")
        return correlations


class TodosAdapter(StoreAdapter):
    """Adapter for todo store."""

    @property
    def name(self) -> str:
        return "todos"

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        try:
            from gateway.todo_store import get
            todos = await asyncio.to_thread(get)
            terms = [term for term in query.lower().split() if term]
            if not terms:
                return todos[:5]
            def _content(todo: dict[str, Any]) -> str:
                return str(todo.get("content") or "").lower()
            matches = [
                todo for todo in todos if any(term in _content(todo) for term in terms)
            ]
            return matches[:5]
        except Exception as e:
            logger.warning("Todo fetch failed: %s", e)
            return []

    def format_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = ["## Todos"]
        for todo in items[:5]:
            content = todo.get("content", "")
            status = todo.get("status", "pending")
            lines.append(f"- [{status}] {content}")
        return "\n".join(lines)

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        """Find correlations with journal (completed todos)."""
        correlations = []
        if items:
            completed = [t for t in items if t.get("status") == "completed"]
            if completed:
                correlations.append(f"{len(completed)} completed, rest pending")
        return correlations


class InboxAdapter(StoreAdapter):
    """Adapter for mobile-compatible quick captures."""

    @property
    def name(self) -> str:
        return "inbox"

    async def fetch(self, query: str) -> list[dict[str, Any]]:
        try:
            return await asyncio.to_thread(self._fetch_inbox, query)
        except Exception as e:
            logger.warning("Inbox fetch failed: %s", e)
            return []

    def _fetch_inbox(self, query: str) -> list[dict[str, Any]]:
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
            term in {"brief", "morning", "today", "inbox", "capture", "captures"}
            for term in terms
        )

        def searchable(entry: dict[str, Any]) -> str:
            tags = entry.get("tags") if isinstance(entry.get("tags"), list) else []
            return " ".join(
                [
                    str(entry.get("text") or ""),
                    str(entry.get("source") or ""),
                    str(entry.get("type") or ""),
                    str(entry.get("project") or ""),
                    " ".join(str(tag) for tag in tags),
                ]
            ).lower()

        matches = []
        for entry in reversed(rows):
            if brief_query and entry.get("processed") is False:
                matches.append(entry)
            elif terms and any(term in searchable(entry) for term in terms):
                matches.append(entry)
            elif not terms:
                matches.append(entry)
            if len(matches) >= 5:
                break
        return matches

    def format_items(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = ["## Recent Captures"]
        for entry in items[:5]:
            created = entry.get("created_at", "unknown time")
            text = str(entry.get("text") or "").strip()
            source = entry.get("source", "capture")
            if text:
                lines.append(f"- [{created} | {source}] {text[:240]}")
        return "\n".join(lines)

    def correlate(
        self, items: list[dict[str, Any]], all_results: dict[str, list[dict[str, Any]]]
    ) -> list[str]:
        unprocessed = [item for item in items if item.get("processed") is False]
        if unprocessed:
            return [f"{len(unprocessed)} unprocessed capture(s)"]
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
    """Result of a unified graph query."""
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    correlations: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def formatted_context(self, cap: int = CONTEXT_TOKEN_CAP) -> str:
        """Format results as a single context string."""
        sections = []
        adapters = self._get_adapters()

        for adapter in adapters:
            items = self.results.get(adapter.name, [])
            if items:
                formatted = adapter.format_items(items)
                if formatted:
                    sections.append(formatted)
                    # Add correlation notes
                    corr_notes = adapter.correlate(items, self.results)
                    if corr_notes:
                        sections[-1] += f"\n→ {', '.join(corr_notes)}"

        raw = "\n\n".join(sections)
        return self._truncate(raw, cap)

    def _get_adapters(self) -> list[StoreAdapter]:
        return _default_adapters()

    def _truncate(self, text: str, cap: int) -> str:
        if (len(text) // 4) <= cap:
            return text
        return text[: cap * 4] + "…"


class MemoryGraph:
    """Deep memory graph module.

    High-leverage entry point for all context retrieval.
    Internal store adapters are implementation details.
    """

    def __init__(self, adapters: list[StoreAdapter] | None = None):
        self._adapters = adapters or _default_adapters()

    async def unified_context(self, query: str) -> str:
        """Get unified context from all stores.

        This is the DEEP entry point. Callers don't need to know about
        individual stores — they just get relevant context.
        """
        result = await self.search_all(query)
        return result.formatted_context()

    async def search_all(self, query: str) -> GraphResult:
        """Search all stores concurrently.

        Returns structured results for callers who want raw data.
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
                    result.errors.append(f"{adapter.name}: timed out")
                else:
                    logger.warning("%s fetch failed: %s", adapter.name, res)
                    result.errors.append(f"{adapter.name}: {res}")
                result.results[adapter.name] = []
            else:
                result.results[adapter.name] = res

        return result


# --- Global instance for backward compatibility ---

_graph: MemoryGraph | None = None


def _get_graph() -> MemoryGraph:
    global _graph
    if _graph is None:
        _graph = MemoryGraph()
    return _graph


# --- Public API (backward compatible) ---


async def unified_context(query: str) -> str:
    """Return unified context from all stores."""
    return await _get_graph().unified_context(query)


async def search_all(query: str) -> dict[str, list[dict[str, Any]]]:
    """Search all stores, return raw results."""
    result = await _get_graph().search_all(query)
    return result.results


# --- Legacy shims for backward compatibility ---
# These exist only for tests that patch internal functions.
# New code should use the adapter pattern directly.


async def _fetch_memory(query: str) -> list[dict[str, Any]]:
    """Legacy shim for tests."""
    return await MemoryAdapter().fetch(query)


async def _fetch_knowledge(query: str) -> list[dict[str, Any]]:
    """Legacy shim for tests."""
    return await KnowledgeAdapter().fetch(query)


async def _fetch_todos(query: str) -> list[dict[str, Any]]:
    """Legacy shim for tests."""
    return await TodosAdapter().fetch(query)


def _fetch_traces(query: str) -> list[dict[str, Any]]:
    """Legacy shim for tests."""
    adapter = TracesAdapter()
    return adapter._fetch_traces(query)


async def _fetch_all_stores(query: str) -> dict[str, list[dict[str, Any]]]:
    """Legacy shim for tests."""
    result = await MemoryGraph().search_all(query)
    return result.results


def search_entries(query: str) -> list[dict[str, Any]]:
    """Legacy shim for tests - delegates to journal."""
    from gateway.journal import search_entries as journal_search
    return journal_search(query)


def _format_unified(results: dict[str, list[dict[str, Any]]]) -> str:
    """Format results for backward compatibility."""
    # Create a dummy GraphResult for formatting
    result = GraphResult(results=results)
    return result.formatted_context()


def _truncate(text: str, cap: int) -> str:
    """Truncate text to token cap."""
    if (len(text) // 4) <= cap:
        return text
    return text[: cap * 4] + "…"
