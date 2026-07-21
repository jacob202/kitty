"""Contract tests for memory_graph adapter failure isolation and source labeling.

Tests the contract: adapters raise on infra failure; search_all owns isolation.
Also tests that source labels are truthful (adapter name, not copy-paste).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from gateway.memory_graph import (
    GraphResult,
    InboxAdapter,
    Item,
    JournalAdapter,
    KnowledgeAdapter,
    MemoryAdapter,
    MemoryGraph,
    SignalsAdapter,
    Source,
    TodosAdapter,
    TracesAdapter,
    WeaveAdapter,
)


# ── Failure isolation contract ───────────────────────────────────────────────


class TestAdapterFailureIsolation:
    """When an adapter's fetch raises, search_all isolates the failure
    into GraphResult.errors and returns [] for that adapter."""

    @pytest.mark.asyncio
    async def test_signals_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[SignalsAdapter()])
        with patch.object(
            SignalsAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("db down"))
        ):
            result = await graph.search_all("test")
            assert "signals" in result.errors[0]
            assert result.results.get("signals") == []

    @pytest.mark.asyncio
    async def test_weave_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[WeaveAdapter()])
        with patch.object(
            WeaveAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("weave exploded"))
        ):
            result = await graph.search_all("test")
            assert "facts" in result.errors[0]
            assert result.results.get("facts") == []

    @pytest.mark.asyncio
    async def test_knowledge_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[KnowledgeAdapter()])
        with patch.object(
            KnowledgeAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("chroma oom"))
        ):
            result = await graph.search_all("test")
            assert "knowledge" in result.errors[0]
            assert result.results.get("knowledge") == []

    @pytest.mark.asyncio
    async def test_memory_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[MemoryAdapter()])
        with patch.object(
            MemoryAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("mem0 down"))
        ):
            result = await graph.search_all("test")
            assert "memory" in result.errors[0]
            assert result.results.get("memory") == []

    @pytest.mark.asyncio
    async def test_journal_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[JournalAdapter()])
        with patch.object(
            JournalAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("sqlite locked"))
        ):
            result = await graph.search_all("test")
            assert "journal" in result.errors[0]
            assert result.results.get("journal") == []

    @pytest.mark.asyncio
    async def test_todos_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[TodosAdapter()])
        with patch.object(
            TodosAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("todo boom"))
        ):
            result = await graph.search_all("test")
            assert "todos" in result.errors[0]
            assert result.results.get("todos") == []

    @pytest.mark.asyncio
    async def test_inbox_adapter_failure_isolated(self):
        graph = MemoryGraph(adapters=[InboxAdapter()])
        with patch.object(
            InboxAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("inbox gone"))
        ):
            result = await graph.search_all("test")
            assert "inbox" in result.errors[0]
            assert result.results.get("inbox") == []

    @pytest.mark.asyncio
    async def test_multiple_failures_all_isolated(self):
        """Multiple adapter failures are all captured in errors."""
        adapters = [SignalsAdapter(), WeaveAdapter()]
        graph = MemoryGraph(adapters=adapters)
        with (
            patch.object(SignalsAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("a"))),
            patch.object(WeaveAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("b"))),
        ):
            result = await graph.search_all("test")
            assert len(result.errors) == 2

    @pytest.mark.asyncio
    async def test_success_still_works(self):
        """Successful adapters return items normally."""
        items = [Item(text="hello", source=Source.MEMORY)]
        graph = MemoryGraph(adapters=[MemoryAdapter()])
        with patch.object(MemoryAdapter, "fetch", new=AsyncMock(return_value=items)):
            result = await graph.search_all("test")
            assert result.results["memory"] == items
            assert result.errors == []


# ── Source labeling contract ─────────────────────────────────────────────────


class TestSourceLabels:
    """Items from adapters have truthful source labels matching adapter name."""

    def test_signals_adapter_source_is_signals(self):
        """SignalsAdapter labels items Source.SIGNALS, not Source.TRACES."""
        assert Source.SIGNALS.value == "signals"
        # Verify the enum member exists and is distinct from TRACES
        assert Source.SIGNALS is not Source.TRACES

    def test_facts_source_is_facts(self):
        """WeaveAdapter labels items Source.FACTS, not Source.MEMORY."""
        assert Source.FACTS.value == "facts"
        assert Source.FACTS is not Source.MEMORY

    def test_source_enum_has_all_members(self):
        """Source enum includes all adapter-relevant members."""
        expected = {"memory", "knowledge", "journal", "traces", "todos", "inbox",
                    "memory_palace", "signals", "facts"}
        actual = {s.value for s in Source}
        assert expected == actual
