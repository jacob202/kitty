"""Tests for the unified memory graph."""

import pytest
import asyncio
import json
import time
from unittest.mock import patch, AsyncMock

import gateway.memory_graph as memory_graph_module
from gateway.memory_graph import (
    unified_context,
    search_all,
    CONTEXT_TOKEN_CAP,
    MemoryGraph,
    GraphResult,
    MemoryAdapter,
    KnowledgeAdapter,
    JournalAdapter,
    TracesAdapter,
    TodosAdapter,
    StoreAdapter,
    _fetch_traces,
)


@pytest.mark.asyncio
async def test_search_all_returns_all_keys():
    """search_all should always return the five canonical keys."""
    with patch.object(
        MemoryAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        KnowledgeAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        JournalAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        TracesAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        TodosAdapter, "fetch", new=AsyncMock(return_value=[])
    ):
        results = await search_all("test query")
        assert set(results.keys()) == {
            "memory",
            "knowledge",
            "journal",
            "traces",
            "todos",
        }
        assert all(isinstance(v, list) for v in results.values())


@pytest.mark.asyncio
async def test_failure_isolation():
    """A failure in one store should not prevent others from returning results."""
    with patch.object(
        MemoryAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("Store down"))
    ), patch.object(
        KnowledgeAdapter,
        "fetch",
        new=AsyncMock(return_value=[{"text": "found it"}]),
    ), patch.object(
        JournalAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        TracesAdapter, "fetch", new=AsyncMock(return_value=[])
    ), patch.object(
        TodosAdapter, "fetch", new=AsyncMock(return_value=[])
    ):
        results = await search_all("test query")
        assert results["memory"] == []
        assert len(results["knowledge"]) == 1
        assert results["knowledge"][0]["text"] == "found it"


@pytest.mark.asyncio
async def test_slow_optional_store_is_bounded(monkeypatch):
    class SlowAdapter(StoreAdapter):
        @property
        def name(self):
            return "slow"

        async def fetch(self, query):
            await asyncio.sleep(0.2)
            return [{"text": query}]

        def format_items(self, items):
            return ""

    monkeypatch.setattr(memory_graph_module, "STORE_FETCH_TIMEOUT_SECONDS", 0.01)
    started = time.monotonic()
    result = await MemoryGraph([SlowAdapter()]).search_all("hello")

    assert time.monotonic() - started < 0.1
    assert result.results["slow"] == []
    assert result.errors == ["slow: timed out"]


@pytest.mark.asyncio
async def test_knowledge_adapter_does_not_block_event_loop(monkeypatch):
    async def blocking_search(query, limit):
        time.sleep(0.2)
        return [{"text": query}]

    monkeypatch.setattr("gateway.knowledge.search", blocking_search)
    monkeypatch.setattr(memory_graph_module, "STORE_FETCH_TIMEOUT_SECONDS", 0.01)
    started = time.monotonic()
    result = await MemoryGraph([KnowledgeAdapter()]).search_all("hello")

    assert time.monotonic() - started < 0.1
    assert result.results["knowledge"] == []


@pytest.mark.asyncio
async def test_unified_context_formatting():
    """unified_context should return a formatted string with sections."""
    mock_results = {
        "memory": [{"memory": "remembered this"}],
        "knowledge": [{"text": "learned this", "source": "book.pdf"}],
        "journal": [{"entry": "today I felt happy"}],
        "traces": [{"user_request": "how are you", "domain_classified": "chat"}],
        "todos": [],
    }

    with patch.object(
        MemoryGraph,
        "search_all",
        new=AsyncMock(return_value=GraphResult(results=mock_results)),
    ):
        ctx = await unified_context("hello")
        assert "## Memory" in ctx
        assert "remembered this" in ctx
        assert "## Knowledge" in ctx
        assert "learned this" in ctx
        assert "## Recent Journal" in ctx
        assert "today I felt happy" in ctx
        assert "## Recent Activity" in ctx
        assert "[chat] how are you" in ctx


@pytest.mark.asyncio
async def test_token_budget_truncation():
    """unified_context should truncate output according to CONTEXT_TOKEN_CAP."""
    long_text = "A" * (CONTEXT_TOKEN_CAP * 5)
    mock_results = {
        "memory": [{"memory": long_text}],
        "knowledge": [],
        "journal": [],
        "traces": [],
        "todos": [],
    }

    with patch.object(
        MemoryGraph,
        "search_all",
        new=AsyncMock(return_value=GraphResult(results=mock_results)),
    ):
        ctx = await unified_context("hello")
        assert len(ctx) <= (CONTEXT_TOKEN_CAP * 4) + 5
        assert ctx.endswith("…")


@pytest.mark.asyncio
async def test_real_journal_fetch_smoke(tmp_path, monkeypatch):
    """Test journal search_entries via the journal module with a temporary file."""
    journal_file = tmp_path / "journal_entries.jsonl"
    monkeypatch.setattr("gateway.journal.JOURNAL_LOG", journal_file)

    with open(journal_file, "w") as f:
        f.write(json.dumps({"entry": "the quick brown fox"}) + "\n")
        f.write(json.dumps({"entry": "lazy dog jumps"}) + "\n")
        f.write(json.dumps({"entry": "nothing here"}) + "\n")

    from gateway.journal import search_entries

    results = search_entries("quick dog")

    assert len(results) == 2
    assert any("quick" in r["entry"] for r in results)
    assert any("dog" in r["entry"] for r in results)


@pytest.mark.asyncio
async def test_real_trace_fetch_smoke(tmp_path, monkeypatch):
    """Test the real _fetch_traces logic with a temporary file."""
    trace_file = tmp_path / "gateway_trace.jsonl"
    monkeypatch.setattr("gateway.memory_graph.GATEWAY_LOG", trace_file)

    now = time.time()
    with open(trace_file, "w") as f:
        f.write(
            json.dumps(
                {
                    "user_request": "fix the hvac",
                    "timestamp": now,
                    "domain_classified": "repair",
                }
            )
            + "\n"
        )
        f.write(
            json.dumps(
                {
                    "user_request": "stale request",
                    "timestamp": now - 10 * 86400,
                    "domain_classified": "old",
                }
            )
            + "\n"
        )

    results = _fetch_traces("hvac")

    assert len(results) == 1
    assert results[0]["user_request"] == "fix the hvac"
    assert results[0]["domain_classified"] == "repair"
