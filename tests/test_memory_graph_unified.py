import pytest
from unittest.mock import AsyncMock, patch
from gateway.memory_graph import unified_context, search_all


@pytest.mark.asyncio
async def test_unified_context_aggregation():
    # Mock all internal fetchers
    with patch(
        "gateway.memory_graph._fetch_memory", new_callable=AsyncMock
    ) as m_mem, patch(
        "gateway.memory_graph._fetch_knowledge", new_callable=AsyncMock
    ) as m_kn, patch(
        "gateway.memory_graph.search_entries",
        return_value=[{"entry": "journal test", "ts": 123}],
    ), patch(
        "gateway.memory_graph._fetch_traces",
        return_value=[{"user_request": "trace test", "domain_classified": "soul"}],
    ), patch(
        "gateway.memory_graph._fetch_todos", return_value=[]
    ):

        m_mem.return_value = [{"memory": "memory test"}]
        m_kn.return_value = [
            {"source": "kn_src", "doc_type": "manual", "text": "knowledge test"}
        ]

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
    with patch(
        "gateway.memory_graph._fetch_memory", new_callable=AsyncMock
    ) as m_mem, patch(
        "gateway.memory_graph._fetch_knowledge", new_callable=AsyncMock
    ) as m_kn, patch(
        "gateway.memory_graph.search_entries", return_value=[{"entry": "journal test"}]
    ), patch(
        "gateway.memory_graph._fetch_traces",
        return_value=[{"user_request": "trace test"}],
    ), patch(
        "gateway.memory_graph._fetch_todos", return_value=[]
    ):

        m_mem.return_value = [{"memory": "mem"}]
        m_kn.return_value = [{"text": "kn"}]

        results = await search_all("test")
        assert "memory" in results
        assert "knowledge" in results
        assert "journal" in results
        assert "traces" in results
        assert "todos" in results
