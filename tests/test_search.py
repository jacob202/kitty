"""Tests for the normalized gateway search interface."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.memory_graph import GraphResult, Item, Source


@pytest.mark.asyncio
async def test_async_search_normalizes_grouped_store_hits() -> None:
    from gateway.search import async_search

    items = {
        Source.PROJECTS.value: [
            Item(
                text="Project Kitty: status=active",
                source=Source.PROJECTS,
                metadata={"project_id": "proj-1"},
            )
        ],
        Source.MEMORY.value: [
            Item(
                text="Jacob likes concise plans",
                source=Source.MEMORY,
                score=3,
                metadata={"source": "facts"},
            )
        ],
        Source.KNOWLEDGE.value: [
            Item(
                text="MOSFET bias notes",
                source=Source.KNOWLEDGE,
                score=0.87,
                metadata={"source": "sansui.pdf"},
            )
        ],
        Source.JOURNAL.value: [
            Item(text="Felt focused after the short work block.", source=Source.JOURNAL)
        ],
        Source.TRACES.value: [
            Item(
                text="fix the hvac",
                source=Source.TRACES,
                score=1.0,
                metadata={"domain_classified": "repair"},
            )
        ],
        Source.TODOS.value: [
            Item(
                text="Recheck gateway search",
                source=Source.TODOS,
                metadata={"id": "todo-1", "done": False},
            )
        ],
        Source.INBOX.value: [
            Item(
                text="Capture the Sansui bias setting",
                source=Source.INBOX,
                metadata={"source": "desktop_quick_capture"},
            )
        ],
        Source.SIGNALS.value: [
            Item(
                text="[connector | unseen] New signal",
                source=Source.SIGNALS,
                metadata={"source": "connector"},
            )
        ],
    }
    mock_result = GraphResult(results=items)

    with patch("gateway.search.memory_graph.search_all", new=AsyncMock(return_value=mock_result)):
        result = await async_search("gateway search", limit=3)

    assert result["query"] == "gateway search"
    assert set(result) >= {
        "projects", "memories", "knowledge", "journal", "traces",
        "todos", "inbox", "signals", "stores", "errors",
    }
    assert result["errors"] == []
    for section, kind in (
        ("projects", "project"),
        ("memories", "memory"),
        ("knowledge", "knowledge"),
        ("journal", "journal"),
        ("traces", "trace"),
        ("todos", "todo"),
        ("inbox", "capture"),
        ("signals", "signal"),
    ):
        hit = result[section][0]
        assert hit["kind"] == kind
        assert isinstance(hit["source"], str)
        assert isinstance(hit["title"], str)
        assert isinstance(hit["text"], str)
        assert "score" in hit
        assert isinstance(hit["metadata"], dict)

    assert result["projects"][0]["text"] == "Project Kitty: status=active"
    assert result["memories"][0]["text"] == "Jacob likes concise plans"
    assert result["knowledge"][0]["title"] == "sansui.pdf"
    assert result["journal"][0]["source"] == "journal"
    assert result["traces"][0]["text"] == "fix the hvac"
    assert result["todos"][0]["title"] == "Recheck gateway search"
    assert result["inbox"][0]["title"] == "Capture the Sansui bias setting"
    assert result["signals"][0]["text"] == "[connector | unseen] New signal"


def test_search_route_exposes_structured_degraded_stores() -> None:
    with patch(
        "gateway.memory_graph.search_all",
        new=AsyncMock(return_value=GraphResult(
            results={Source.MEMORY.value: []},
            errors=["memory: MemoryError: unavailable"],
            degraded_stores=[Source.MEMORY.value],
        )),
    ):
        client = TestClient(app)
        response = client.get("/search", params={"q": "anything", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded_stores"] == [Source.MEMORY.value]
    assert body["errors"] == ["memory: MemoryError: unavailable"]


def test_search_route_uses_normalized_owner_and_preserves_hit_provenance() -> None:
    items = {
        Source.KNOWLEDGE.value: [
            Item(
                text="MOSFET bias notes",
                source=Source.KNOWLEDGE,
                score=0.87,
                metadata={"source": "sansui.pdf"},
            )
        ],
    }

    with patch(
        "gateway.memory_graph.search_all",
        new=AsyncMock(return_value=GraphResult(results=items)),
    ):
        client = TestClient(app)
        response = client.get("/search", params={"q": "mosfet", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "mosfet"
    hit = next(r for r in body["results"] if r["store"] == Source.KNOWLEDGE.value)
    assert "MOSFET bias notes" in hit["content"]
    assert hit["title"] == "sansui.pdf"
    assert hit["source"] == Source.KNOWLEDGE.value
    assert hit["metadata"]["source"] == "sansui.pdf"


def test_search_route_balances_the_global_limit_across_stores() -> None:
    items = {
        Source.MEMORY.value: [
            Item(text=f"Memory {index}", source=Source.MEMORY, score=10 - index)
            for index in range(5)
        ],
        Source.KNOWLEDGE.value: [
            Item(text="Knowledge result", source=Source.KNOWLEDGE, score=0.2)
        ],
        Source.JOURNAL.value: [
            Item(text="Journal result", source=Source.JOURNAL, score=None)
        ],
    }

    with patch(
        "gateway.memory_graph.search_all",
        new=AsyncMock(return_value=GraphResult(results=items)),
    ):
        client = TestClient(app)
        response = client.get("/search", params={"q": "balanced", "limit": 3})

    assert response.status_code == 200
    assert {row["store"] for row in response.json()["results"]} == {
        Source.MEMORY.value,
        Source.KNOWLEDGE.value,
        Source.JOURNAL.value,
    }


def test_deep_research_route_uses_typed_payload() -> None:
    with patch("gateway.researcher.deep_dive", new=AsyncMock(return_value="done")):
        client = TestClient(app)
        response = client.post("/research/deep", json={"topic": "mosfet bias"})

    assert response.status_code == 200
    assert response.json() == {"result": "done"}


@pytest.mark.asyncio
async def test_explicit_memory_hits_merge_into_memories() -> None:
    """KF-SEARCH-01: explicit_memory hits appear as memories retaining source
    explicit_memory and its metadata/provenance."""
    from gateway.search import async_search

    items = {
        Source.EXPLICIT_MEMORY.value: [
            Item(
                text="Jacob prefers dark mode",
                source=Source.EXPLICIT_MEMORY,
                metadata={"id": "em-1", "namespace": "user", "source_kind": "confirmed"},
            )
        ],
    }
    mock_result = GraphResult(results=items)

    with patch("gateway.search.memory_graph.search_all", new=AsyncMock(return_value=mock_result)):
        result = await async_search("dark mode", limit=5)

    # explicit_memory merges into memories
    assert len(result["memories"]) == 1
    hit = result["memories"][0]
    assert hit["kind"] == "memory"
    assert hit["text"] == "Jacob prefers dark mode"
    assert hit["metadata"]["source_kind"] == "explicit_memory"
    assert hit["metadata"]["id"] == "em-1"
    # No separate explicit_memory section
    assert "explicit_memory" not in result


@pytest.mark.asyncio
async def test_project_trace_signal_hits_are_not_dropped() -> None:
    """KF-SEARCH-01: hits from projects, traces and signals are returned
    rather than silently discarded."""
    from gateway.search import async_search

    items = {
        Source.PROJECTS.value: [
            Item(
                text="Project Kitty: status=active",
                source=Source.PROJECTS,
                metadata={"project_id": "proj-1"},
            )
        ],
        Source.TRACES.value: [
            Item(
                text="fix the hvac",
                source=Source.TRACES,
                score=1.0,
                metadata={"domain_classified": "repair"},
            )
        ],
        Source.SIGNALS.value: [
            Item(
                text="[connector | unseen] New signal",
                source=Source.SIGNALS,
                metadata={"source": "connector"},
            )
        ],
    }
    mock_result = GraphResult(results=items)

    with patch("gateway.search.memory_graph.search_all", new=AsyncMock(return_value=mock_result)):
        result = await async_search("project hvac signal", limit=10)

    assert len(result["projects"]) == 1
    assert result["projects"][0]["kind"] == "project"
    assert len(result["traces"]) == 1
    assert result["traces"][0]["kind"] == "trace"
    assert len(result["signals"]) == 1
    assert result["signals"][0]["kind"] == "signal"


def test_search_route_returns_all_nine_sections() -> None:
    """KF-SEARCH-01: the HTTP /search response surfaces all nine default
    MemoryGraph stores while preserving its global limit and round-robin
    balancing."""
    items = {
        Source.PROJECTS.value: [
            Item(text="Project Kitty", source=Source.PROJECTS, metadata={"project_id": "p1"}),
        ],
        Source.EXPLICIT_MEMORY.value: [
            Item(text="Explicit memory hit", source=Source.EXPLICIT_MEMORY, metadata={"id": "em-1"}),
        ],
        Source.MEMORY.value: [
            Item(text="Memory hit", source=Source.MEMORY, score=1),
        ],
        Source.KNOWLEDGE.value: [
            Item(text="Knowledge hit", source=Source.KNOWLEDGE, score=0.9),
        ],
        Source.JOURNAL.value: [
            Item(text="Journal hit", source=Source.JOURNAL),
        ],
        Source.TRACES.value: [
            Item(text="Trace hit", source=Source.TRACES, score=1.0),
        ],
        Source.TODOS.value: [
            Item(text="Todo hit", source=Source.TODOS),
        ],
        Source.INBOX.value: [
            Item(text="Inbox hit", source=Source.INBOX),
        ],
        Source.SIGNALS.value: [
            Item(text="Signal hit", source=Source.SIGNALS),
        ],
    }

    with patch(
        "gateway.memory_graph.search_all",
        new=AsyncMock(return_value=GraphResult(results=items)),
    ):
        client = TestClient(app)
        response = client.get("/search", params={"q": "everything", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    stores_present = {row["store"] for row in body["results"]}
    # All nine default stores should appear (explicit_memory merges into memory store)
    assert "projects" in stores_present
    assert "memory" in stores_present
    assert "knowledge" in stores_present
    assert "journal" in stores_present
    assert "traces" in stores_present
    assert "todos" in stores_present
    assert "inbox" in stores_present
    assert "signals" in stores_present


def test_search_route_balances_round_robin_across_all_stores() -> None:
    """KF-SEARCH-01: round-robin interleaving works across all nine stores."""
    items = {
        Source.PROJECTS.value: [
            Item(text="Project 1", source=Source.PROJECTS, metadata={"project_id": "p1"}),
            Item(text="Project 2", source=Source.PROJECTS, metadata={"project_id": "p2"}),
        ],
        Source.MEMORY.value: [
            Item(text="Memory 1", source=Source.MEMORY, score=2),
            Item(text="Memory 2", source=Source.MEMORY, score=1),
        ],
        Source.TRACES.value: [
            Item(text="Trace 1", source=Source.TRACES, score=1.0),
        ],
        Source.SIGNALS.value: [
            Item(text="Signal 1", source=Source.SIGNALS),
        ],
    }

    with patch(
        "gateway.memory_graph.search_all",
        new=AsyncMock(return_value=GraphResult(results=items)),
    ):
        client = TestClient(app)
        response = client.get("/search", params={"q": "round robin", "limit": 5})

    assert response.status_code == 200
    body = response.json()
    rows = body["results"]
    assert len(rows) == 5
    # Round-robin: first item from each store, then second item from stores that have them
    stores_seen = [row["store"] for row in rows]
    # First pass: projects, memory, traces, signals (4 stores)
    assert stores_seen[0] == "projects"
    assert stores_seen[1] == "memory"
    assert stores_seen[2] == "traces"
    assert stores_seen[3] == "signals"
    # Second pass: projects again (has 2 items)
    assert stores_seen[4] == "projects"
