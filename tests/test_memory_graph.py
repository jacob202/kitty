"""Tests for the unified memory graph (Phase 2: ``list[Item]`` shape)."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

import gateway.memory_graph as memory_graph_module
from gateway import prefetcher
from gateway.memory_graph import (
    CONTEXT_TOKEN_CAP,
    ExplicitMemoryAdapter,
    GraphResult,
    InboxAdapter,
    Item,
    JournalAdapter,
    KnowledgeAdapter,
    MemoryAdapter,
    MemoryGraph,
    ProjectAdapter,
    SignalsAdapter,
    Source,
    StoreAdapter,
    TodosAdapter,
    TracesAdapter,
    _fetch_traces,
    unified_context,
)


@pytest.fixture(autouse=True)
def _isolate_prefetch_cache(tmp_path, monkeypatch):
    """Per-test history file + clean prefetcher cache so tests in this file
    don't bleed into each other (the in-process TTL cache would otherwise
    return stale ``unified_context`` results from a previous test in the
    same pytest run)."""
    monkeypatch.setattr(prefetcher, "_HISTORY", tmp_path / "hist.jsonl")
    prefetcher._cache.clear()
    yield
    prefetcher._cache.clear()


@pytest.mark.asyncio
async def test_search_all_returns_all_keys():
    """``MemoryGraph.search_all`` should always return the canonical store keys
    and each value should be a ``list[Item]``."""
    with (
        patch.object(ProjectAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(ExplicitMemoryAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(MemoryAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(KnowledgeAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(JournalAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(TracesAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(TodosAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(InboxAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch.object(SignalsAdapter, "fetch", new=AsyncMock(return_value=[])),
        patch("gateway.chat_search.ChatMessagesAdapter.fetch", new=AsyncMock(return_value=[])),
    ):
        graph = MemoryGraph()
        result = await graph.search_all("test query")
        assert set(result.results.keys()) == {
            "projects",
            "explicit_memory",
            "memory",
            "knowledge",
            "journal",
            "traces",
            "todos",
            "inbox",
            "signals",
            "chats",
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
    never_ready = asyncio.Event()

    class SlowAdapter(StoreAdapter):
        @property
        def name(self):
            return "slow"

        async def fetch(self, query):
            await never_ready.wait()
            return [Item(text=query, source=Source.MEMORY)]

    monkeypatch.setattr(memory_graph_module, "STORE_FETCH_TIMEOUT_SECONDS", 0.01)
    result = await asyncio.wait_for(
        MemoryGraph([SlowAdapter()]).search_all("hello"), timeout=0.2
    )

    assert result.results["slow"] == []
    assert any("TimeoutError" in e and "timed out" in e for e in result.errors)


@pytest.mark.asyncio
async def test_unified_context_race_with_invalidation_does_not_repopulate_cache(monkeypatch):
    """A unified_context() call already in flight when a correction
    invalidates the cache must not overwrite that invalidation once it
    finishes — otherwise a slow query racing remember()/forget() resurrects
    the pre-correction answer for the rest of the TTL (found by review on
    #629's original fix)."""
    release = asyncio.Event()

    class _SlowGraph:
        async def unified_context(self, query):
            await release.wait()
            return "STALE-CONTEXT"

    monkeypatch.setattr(memory_graph_module, "_get_graph", lambda: _SlowGraph())

    task = asyncio.create_task(unified_context("q"))
    await asyncio.sleep(0)  # let the task start and capture its generation

    prefetcher.invalidate_all()  # a correction lands while the compute is in flight
    release.set()
    result = await task

    assert result == "STALE-CONTEXT"  # the in-flight caller still gets its answer
    assert prefetcher.get_cached("q") is None  # but it must not poison the cache


@pytest.mark.asyncio
async def test_knowledge_adapter_does_not_block_event_loop(monkeypatch):
    never_ready = asyncio.Event()

    async def blocking_search(query, limit):
        await never_ready.wait()
        return [{"text": query}]

    monkeypatch.setattr("gateway.knowledge.search", blocking_search)
    monkeypatch.setattr(memory_graph_module, "STORE_FETCH_TIMEOUT_SECONDS", 0.01)
    result = await asyncio.wait_for(
        MemoryGraph([KnowledgeAdapter()]).search_all("hello"), timeout=0.2
    )

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


@pytest.mark.asyncio
async def test_knowledge_adapter_reads_actual_score_field(monkeypatch):
    """C4-05: gateway.knowledge.search returns rows keyed 'score', but the
    adapter was reading '_score' — every Knowledge Item.score was silently
    None regardless of the store's real relevance ranking."""

    async def fake_search(query, limit):
        return [{"text": "a relevant chunk", "score": 0.87}]

    monkeypatch.setattr("gateway.knowledge.search", fake_search)

    items = await KnowledgeAdapter().fetch("hello")

    assert items[0].score == 0.87


def test_select_unified_items_budgets_by_score_not_adapter_order():
    """C4-05: within a store's items, the highest-scored ones must win a
    budget slot — not whichever the adapter happened to list first."""
    low = Item(text="low relevance", source=Source.KNOWLEDGE, score=0.1)
    high = Item(text="high relevance", source=Source.KNOWLEDGE, score=0.9)

    sections, rendered = memory_graph_module._select_unified_items(
        {"knowledge": [low, high]}, cap=1000, query=""
    )

    assert rendered[0]["text"] == "high relevance"
    assert sections[0].index("high relevance") < sections[0].index("low relevance")


@pytest.fixture
def _project_scope_db(tmp_path, monkeypatch):
    """Isolated project store + matching active-project scope, both pointed
    at the same on-disk DB (project_store and project_context each bind their
    own module-level DB_FILE name from gateway.paths, so both need patching)."""
    from gateway import project_context, project_store

    db_file = tmp_path / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(project_context, "KITTY_DB_FILE", db_file, raising=False)
    return project_store, project_context


@pytest.mark.asyncio
async def test_project_adapter_excludes_other_projects_on_generic_query(_project_scope_db):
    """C4-02: a query with no matchable keywords used to return every
    project unfiltered. Only the active project should surface."""
    project_store, project_context = _project_scope_db
    active = project_store.create("kitty", "code")
    other = project_store.create("benefits paperwork", "admin")
    project_context.set_active_project(active["id"])

    items = await ProjectAdapter().fetch("?")  # no matchable terms

    project_ids = {item.metadata["project_id"] for item in items}
    assert project_ids == {active["id"]}
    assert other["id"] not in project_ids


@pytest.mark.asyncio
async def test_project_adapter_still_matches_other_project_by_keyword(_project_scope_db):
    """A non-active project must still surface when the query names it —
    scoping must not become a blanket suppression."""
    project_store, project_context = _project_scope_db
    active = project_store.create("kitty", "code")
    other = project_store.create("benefits paperwork", "admin")
    project_context.set_active_project(active["id"])

    items = await ProjectAdapter().fetch("benefits paperwork status")

    project_ids = {item.metadata["project_id"] for item in items}
    assert other["id"] in project_ids


@pytest.mark.asyncio
async def test_project_adapter_active_project_always_included(_project_scope_db):
    """The active project is context even without a keyword match."""
    project_store, project_context = _project_scope_db
    active = project_store.create("kitty", "code")
    project_context.set_active_project(active["id"])

    items = await ProjectAdapter().fetch("completely unrelated query terms")

    active_items = [item for item in items if item.metadata["project_id"] == active["id"]]
    assert len(active_items) == 1
    assert active_items[0].metadata["active"] is True


@pytest.mark.asyncio
async def test_project_adapter_propagates_corrupt_scope_as_degraded_store(_project_scope_db):
    """P2 (review on #630): a corrupt/missing persisted active-project scope
    must surface as a degraded store, not silently degrade to an apparently
    healthy empty result — that's exactly the hidden-degradation pattern
    C4-06 exists to prevent."""
    project_store, project_context = _project_scope_db
    project_store.init_db()
    project_context._write_active_project_id(999999)  # points at nothing

    result = await MemoryGraph([ProjectAdapter()]).search_all("hello")

    assert result.results["projects"] == []
    assert result.degraded_stores == ["projects"]
    assert any("ProjectContextError" in e for e in result.errors)


def test_set_active_project_invalidates_prefetch_cache(_project_scope_db):
    """P1 (review on #630): switching the active project must not leave a
    cached generic-query answer describing the previous project for the
    rest of the TTL."""
    project_store, project_context = _project_scope_db

    first = project_store.create("kitty", "code")
    second = project_store.create("benefits paperwork", "admin")
    project_context.set_active_project(first["id"])

    prefetcher.put_cached("status", f"CACHED::{first['id']}")
    assert prefetcher.get_cached("status") is not None

    project_context.set_active_project(second["id"])

    assert prefetcher.get_cached("status") is None
