"""Tests for the normalized gateway search interface."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app


@pytest.mark.asyncio
async def test_async_search_normalizes_grouped_store_hits() -> None:
    from gateway.search import async_search

    raw = {
        "memory": [{"memory": "Jacob likes concise plans", "source": "facts", "_score": 3}],
        "knowledge": [{"text": "MOSFET bias notes", "source": "sansui.pdf", "score": 0.87}],
        "journal": [{"entry": "Felt focused after the short work block.", "ts": "2026-05-18"}],
        "todos": [{"content": "Recheck gateway search", "id": "todo-1", "done": False}],
    }

    with patch("gateway.search.memory_graph.search_all", new=AsyncMock(return_value=raw)):
        result = await async_search("gateway search", limit=3)

    assert result["query"] == "gateway search"
    assert set(result) >= {"memories", "knowledge", "journal", "todos"}
    for section, kind in (
        ("memories", "memory"),
        ("knowledge", "knowledge"),
        ("journal", "journal"),
        ("todos", "todo"),
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


def test_search_route_uses_async_search_without_dropping_knowledge() -> None:
    payload = {
        "query": "mosfet",
        "memories": [],
        "knowledge": [
            {
                "kind": "knowledge",
                "source": "sansui.pdf",
                "title": "sansui.pdf",
                "text": "MOSFET bias notes",
                "score": 0.87,
                "metadata": {},
            }
        ],
        "journal": [],
        "todos": [],
    }

    with patch("gateway.search.async_search", new=AsyncMock(return_value=payload)):
        client = TestClient(app)
        response = client.get("/search", params={"q": "mosfet", "limit": 3})

    assert response.status_code == 200
    assert response.json()["knowledge"][0]["text"] == "MOSFET bias notes"
