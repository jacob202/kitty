"""Tests for the unified memory graph (Phase 2: ``list[Item]`` shape)."""

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
    Item,
    JournalAdapter,
    KnowledgeAdapter,
    MemoryAdapter,
    MemoryGraph,
    SignalsAdapter,
    Source,
    StoreAdapter,
    TodosAdapter,
    TracesAdapter,
    _fetch_traces,
    unified_context,
)


@pytest.mark.asyncio
async def test_search_all_returns_all_keys():
    """``MemoryGraph.search_all`` should always return the canonical store keys
    and each value should be a ``list[Item]``."""
    with (
        patch.object(MemoryAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(KnowledgeAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(JournalAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(TracesAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(TodosAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(InboxAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(SignalsAdapter, "fetch", new=AsyncMock(return_value=[])),
    ):
        graph = MemoryGraph()
        result = await graph.search_all("test query")
        assert set(result.results.keys()) == {
            "memory",
            "knowledge",
            "journal",
            "traces",
            "todos",
            "inbox",
            "signals",
        }
        assert all(isinstance(v, list) for v in result.results.values())
        assert all(isinstance(it, Item) for v in result.results.values() for it in v)


@pytest.mark.asyncio
async def test_failure_isolation():
    """A failure in one store should not prevent others from returning results."""
    ok_item = Item(text="found it", source=Source.KNOWLEDGE)
    with (
        patch.object(MemoryAdapter, "fetch", new=AsyncMock(side_effect=RuntimeError("Store down"))),
        patch.object(KnowledgeAdapter, "fetch", new=AsyncMock(return_value=[ok_item])),
        patch.object(JournalAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(TracesAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(TodosAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(InboxAdapter, "fetch", new=AsyncMock(return_value=[])),
    ):
        result = await MemoryGraph().search_all("test query")
        assert result.results["memory"] == []
        assert len(result.results["knowledge"]) == 1
        assert result.results["knowledge"][0].text == "found it"
        assert any("RuntimeError" in e for e in result.errors)


@pytest.mark.asyncio
async def test_slow_optional_store_is_bounded(monkeypatch):
    class SlowAdapter(StoreAdapter):
        @property
        def name(self):
            return "slow"

        async def fetch(self, query):
            await asyncio.sleep(0.2)
            return [Item(text=query, source=Source.MEMORY)]

    monkeypatch.setattr(memory_graph_module, "STORE_FETCH_TIMEOUT_SECONDS", 0.01)
    started = time.monotonic()
    result = await MemoryGraph([SlowAdapter()]).search_all("hello")

    assert time.monotonic() - started < 0.15
    assert result.results["slow"] == []
    assert any("TimeoutError" in e and "timed out" in e for e in result.errors)


@pytest.mark.asyncio
async def test_knowledge_adapter_does_not_block_event_loop(monkeypatch):
    def blocking_search(query, limit):
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
    """``unified_context`` returns a formatted string with sections per source."""
    mock_results = {
        "memory": [Item(text="remembered this", source=Source.MEMORY)],
        "knowledge": [
            Item(
                text="learned this",
                source=Source.KNOWLEDGE,
                metadata={"source": "book.pdf"},
            )
        ],
        "journal": [Item(text="today I felt happy", source=Source.JOURNAL)],
        "traces": [
            Item(
                text="how are you",
                source=Source.TRACES,
                metadata={"domain_classified": "chat"},
            )
        ],
        "todos": [],
        "inbox": [
            Item(
                text="remember to order bias trim pots",
                source=Source.INBOX,
                metadata={
                    "created_at": "2026-06-18T12:00:00Z",
                    "source": "desktop_quick_capture",
                },
            )
        ],
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
        assert "## Journal" in ctx
        assert "today I felt happy" in ctx
        assert "## Traces" in ctx
        assert "how are you" in ctx
        assert "## Inbox" in ctx
        assert "remember to order bias trim pots" in ctx


@pytest.mark.asyncio
async def test_token_budget_truncation():
    """``unified_context`` truncates output according to ``CONTEXT_TOKEN_CAP``."""
    long_text = "A" * (CONTEXT_TOKEN_CAP * 5)
    mock_results = {
        "memory": [Item(text=long_text, source=Source.MEMORY)],
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
    """JournalAdapter fetches via journal.search_entries (SQLite-backed)."""
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

    items = await JournalAdapter().fetch("quick dog")

    assert len(items) == 2
    assert all(isinstance(it, Item) for it in items)
    assert all(it.source == Source.JOURNAL for it in items)
    texts = [it.text for it in items]
    assert any("quick" in t for t in texts)
    assert any("dog" in t for t in texts)


@pytest.mark.asyncio
async def test_real_trace_fetch_smoke(tmp_path, monkeypatch):
    """TracesAdapter._fetch_traces returns ``list[Item]`` from the trace log."""
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

    items = _fetch_traces("hvac")

    assert len(items) == 1
    assert all(isinstance(it, Item) for it in items)
    assert items[0].text == "fix the hvac"
    assert items[0].metadata.get("domain_classified") == "repair"


@pytest.mark.asyncio
async def test_inbox_adapter_resurfaces_unprocessed_captures_for_brief(tmp_path, monkeypatch):
    """Brief queries should include recent unprocessed captures as ``Item``."""
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

    assert [item.metadata["id"] for item in items] == ["new"]
    assert items[0].source == Source.INBOX
    assert "Ask Mike about the Ridgeline tires" in items[0].text


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

    assert by_text[0].metadata["id"] == "capture-1"
    assert by_tag[0].metadata["id"] == "capture-1"
