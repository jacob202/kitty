"""Tests for the normalized gateway search interface."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.memory_graph import GraphResult, Item, Source


@pytest.mark.asyncio
async def test_async_search_normalizes_grouped_store_hits() -> None:
    from gateway.search import async_search

    items = {
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
    }
    mock_result = GraphResult(results=items)

    with patch("gateway.search.memory_graph.search_all", new=AsyncMock(return_value=mock_result)):
        result = await async_search("gateway search", limit=3)

    assert result["query"] == "gateway search"
    assert set(result) >= {"memories", "knowledge", "journal", "todos", "inbox"}
    for section, kind in (
        ("memories", "memory"),
        ("knowledge", "knowledge"),
        ("journal", "journal"),
        ("todos", "todo"),
        ("inbox", "capture"),
    ):
        hit = result[section][0]
        assert hit["kind"] == kind
        assert isinstance(hit["source"], str)
        assert isinstance(hit["title"], str)
        assert isinstance(hit["text"], str)
        assert "score" in hit
        assert isinstance(hit["metadata"], dict)

    assert result["memories"][0]["text"] == "Jacob likes concise plans"
    assert result["knowledge"][0]["title"] == "sansui.pdf"
    assert result["journal"][0]["source"] == "journal"
    assert result["todos"][0]["title"] == "Recheck gateway search"
    assert result["inbox"][0]["title"] == "Capture the Sansui bias setting"


def test_search_route_uses_async_search_without_dropping_knowledge() -> None:
    item = SimpleNamespace(text="MOSFET bias notes", score=0.87)
    graph_result = SimpleNamespace(results={"knowledge": [item]}, errors=[])

    with patch("gateway.memory_graph.search_all", new=AsyncMock(return_value=graph_result)):
        client = TestClient(app)
        response = client.get("/search", params={"query": "mosfet", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    knowledge_items = [r for r in body["results"] if r["store"] == "knowledge"]
    assert knowledge_items, "knowledge results must not be dropped from the search response"
    assert knowledge_items[0]["content"] == "MOSFET bias notes"


def test_deep_research_route_uses_typed_payload() -> None:
    with patch("gateway.researcher.deep_dive", new=AsyncMock(return_value="done")):
        client = TestClient(app)
        response = client.post("/research/deep", json={"topic": "mosfet bias"})

    assert response.status_code == 200
    assert response.json() == {"result": "done"}
