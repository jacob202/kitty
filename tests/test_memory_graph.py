"""Tests for the unified memory graph."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

import gateway.memory_graph as memory_graph_module
from gateway.memory_graph import (
    CONTEXT_TOKEN_CAP,
    GraphResult,
    InboxAdapter,
    JournalAdapter,
    KnowledgeAdapter,
    MemoryAdapter,
    MemoryGraph,
    StoreAdapter,
    TodosAdapter,
    TracesAdapter,
    _fetch_traces,
    search_all,
    unified_context,
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
    ), patch.object(
        InboxAdapter, "fetch", new=AsyncMock(return_value=[])
    ):
        results = await search_all("test query")
        assert set(results.keys()) == {
            "memory",
            "knowledge",
            "journal",
            "traces",
            "todos",
            "inbox",
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
    ), patch.object(
        InboxAdapter, "fetch", new=AsyncMock(return_value=[])
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

    assert time.monotonic() - started < 0.15
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

    assert time.monotonic() - started < 0.15
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
        "inbox": [{"text": "remember to order bias trim pots", "created_at": "2026-06-18T12:00:00Z", "source": "desktop_quick_capture", "processed": False}],
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
        assert "## Recent Captures" in ctx
        assert "remember to order bias trim pots" in ctx


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
        "inbox": [],
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
    from gateway import journal_store

    journal_file = tmp_path / "journal_entries.jsonl"
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr("gateway.journal.JOURNAL_LOG", journal_file)
    monkeypatch.setattr(journal_store, "JOURNAL_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(journal_store, "LEGACY_JOURNAL_LOG", journal_file, raising=False)

    with open(journal_file, "w") as f:
        f.write(json.dumps({"ts": 1.0, "entry": "the quick brown fox"}) + "\n")
        f.write(json.dumps({"ts": 2.0, "entry": "lazy dog jumps"}) + "\n")
        f.write(json.dumps({"ts": 3.0, "entry": "nothing here"}) + "\n")

    from gateway.journal import search_entries

    results = search_entries("quick dog")

    assert len(results) == 2
    assert any("quick" in r["entry"] for r in results)
    assert any("dog" in r["entry"] for r in results)


@pytest.mark.asyncio
async def test_real_trace_fetch_smoke(tmp_path, monkeypatch):
    """Test the real _fetch_traces logic with a temporary file."""
    trace_file = tmp_path / "gateway_trace.jsonl"
    monkeypatch.setattr("gateway.memory_graph.LOG_FILE", trace_file)

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


@pytest.mark.asyncio
async def test_inbox_adapter_resurfaces_unprocessed_captures_for_brief(tmp_path, monkeypatch):
    """Brief queries should include recent unprocessed captures."""
    inbox_file = tmp_path / "inbox.jsonl"
    monkeypatch.setattr("gateway.memory_graph.INBOX_FILE", inbox_file)
    inbox_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "old",
                        "created_at": "2026-06-17T12:00:00Z",
                        "source": "desktop_quick_capture",
                        "type": "text",
                        "text": "processed thought",
                        "processed": True,
                        "project": None,
                        "tags": [],
                    }
                ),
                "not-json",
                json.dumps(
                    {
                        "id": "new",
                        "created_at": "2026-06-18T12:00:00Z",
                        "source": "desktop_quick_capture",
                        "type": "text",
                        "text": "Ask Mike about the Ridgeline tires",
                        "processed": False,
                        "project": None,
                        "tags": ["ridgeline"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    items = await InboxAdapter().fetch("morning brief")

    assert [item["id"] for item in items] == ["new"]
    formatted = InboxAdapter().format_items(items)
    assert "## Recent Captures" in formatted
    assert "Ask Mike about the Ridgeline tires" in formatted


@pytest.mark.asyncio
async def test_inbox_adapter_matches_capture_text_and_tags(tmp_path, monkeypatch):
    inbox_file = tmp_path / "inbox.jsonl"
    monkeypatch.setattr("gateway.memory_graph.INBOX_FILE", inbox_file)
    inbox_file.write_text(
        json.dumps(
            {
                "id": "capture-1",
                "created_at": "2026-06-18T12:00:00Z",
                "source": "desktop_quick_capture",
                "type": "text",
                "text": "Order replacement transistors",
                "processed": False,
                "project": None,
                "tags": ["sansui"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    by_text = await InboxAdapter().fetch("transistors")
    by_tag = await InboxAdapter().fetch("sansui")

    assert by_text[0]["id"] == "capture-1"
    assert by_tag[0]["id"] == "capture-1"
