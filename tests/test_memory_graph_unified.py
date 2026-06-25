from unittest.mock import AsyncMock, patch

import pytest

from gateway.memory_graph import (
    InboxAdapter,
    JournalAdapter,
    KnowledgeAdapter,
    MemoryAdapter,
    TodosAdapter,
    TracesAdapter,
    search_all,
    unified_context,
)


@pytest.mark.asyncio
async def test_unified_context_aggregation():
    with patch.object(
        MemoryAdapter, "fetch", new=AsyncMock(return_value=[{"memory": "memory test"}])
    ), patch.object(
        KnowledgeAdapter,
        "fetch",
        new=AsyncMock(
            return_value=[
                {"source": "kn_src", "doc_type": "manual", "text": "knowledge test"}
            ]
        ),
    ), patch.object(
        JournalAdapter,
        "fetch",
        new=AsyncMock(return_value=[{"entry": "journal test", "ts": 123}]),
    ), patch.object(
        TracesAdapter,
        "fetch",
        new=AsyncMock(
            return_value=[{"user_request": "trace test", "domain_classified": "soul"}]
        ),
    ), patch.object(
        TodosAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        InboxAdapter, "fetch", new=AsyncMock(return_value=[])
    ):
        ctx = await unified_context("test query")

        assert "## Memory" in ctx
        assert "memory test" in ctx
        assert "## Knowledge" in ctx
        assert "knowledge test" in ctx
        assert "## Recent Journal" in ctx
        assert "journal test" in ctx
        assert "## Recent Activity" in ctx
        assert "trace test" in ctx


@pytest.mark.asyncio
async def test_search_all_structure():
    with patch.object(
        MemoryAdapter, "fetch", new=AsyncMock(return_value=[{"memory": "mem"}])
    ), patch.object(
        KnowledgeAdapter, "fetch", new=AsyncMock(return_value=[{"text": "kn"}])
    ), patch.object(
        JournalAdapter, "fetch", new=AsyncMock(return_value=[{"entry": "journal test"}])
    ), patch.object(
        TracesAdapter,
        "fetch",
        new=AsyncMock(return_value=[{"user_request": "trace test"}]),
    ), patch.object(
        TodosAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        InboxAdapter, "fetch", new=AsyncMock(return_value=[])
    ):
        results = await search_all("test")
        assert "memory" in results
        assert "knowledge" in results
        assert "journal" in results
        assert "traces" in results
        assert "todos" in results
        assert "inbox" in results
