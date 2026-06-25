import pytest
from unittest.mock import AsyncMock, patch

from gateway.memory_graph import (
    InboxAdapter,
    Item,
    JournalAdapter,
    KnowledgeAdapter,
    MemoryAdapter,
    MemoryGraph,
    Source,
    TodosAdapter,
    TracesAdapter,
    unified_context,
)


@pytest.mark.asyncio
async def test_unified_context_aggregation():
    with (
        patch.object(
            MemoryAdapter,
            "fetch",
            new=AsyncMock(return_value=[Item(text="memory test", source=Source.MEMORY)]),
        ),
        patch.object(
            KnowledgeAdapter,
            "fetch",
            new=AsyncMock(
                return_value=[
                    Item(
                        text="knowledge test",
                        source=Source.KNOWLEDGE,
                        metadata={"source": "kn_src", "doc_type": "manual"},
                    )
                ]
            ),
        ),
        patch.object(
            JournalAdapter,
            "fetch",
            new=AsyncMock(return_value=[Item(text="journal test", source=Source.JOURNAL)]),
        ),
        patch.object(
            TracesAdapter,
            "fetch",
            new=AsyncMock(
                return_value=[
                    Item(
                        text="trace test",
                        source=Source.TRACES,
                        metadata={"domain_classified": "soul"},
                    )
                ]
            ),
        ),
        patch.object(TodosAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(InboxAdapter, "fetch", new=AsyncMock(return_value=[])),
    ):
        ctx = await unified_context("test query")

        assert "## Memory" in ctx
        assert "memory test" in ctx
        assert "## Knowledge" in ctx
        assert "knowledge test" in ctx
        assert "## Journal" in ctx
        assert "journal test" in ctx
        assert "## Traces" in ctx
        assert "trace test" in ctx


@pytest.mark.asyncio
async def test_search_all_structure():
    """MemoryGraph.search_all returns a GraphResult with all six keys."""
    with (
        patch.object(
            MemoryAdapter,
            "fetch",
            new=AsyncMock(return_value=[Item(text="mem", source=Source.MEMORY)]),
        ),
        patch.object(
            KnowledgeAdapter,
            "fetch",
            new=AsyncMock(return_value=[Item(text="kn", source=Source.KNOWLEDGE)]),
        ),
        patch.object(
            JournalAdapter,
            "fetch",
            new=AsyncMock(return_value=[Item(text="j", source=Source.JOURNAL)]),
        ),
        patch.object(
            TracesAdapter,
            "fetch",
            new=AsyncMock(return_value=[Item(text="t", source=Source.TRACES)]),
        ),
        patch.object(TodosAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(InboxAdapter, "fetch", new=AsyncMock(return_value=[])),
    ):
        result = await MemoryGraph().search_all("test")
        assert "memory" in result.results
        assert "knowledge" in result.results
        assert "journal" in result.results
        assert "traces" in result.results
        assert "todos" in result.results
        assert "inbox" in result.results
        # Each value is a list of Item.
        assert all(isinstance(it, Item) for v in result.results.values() for it in v)
