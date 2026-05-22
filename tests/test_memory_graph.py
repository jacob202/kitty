"""Tests for the unified memory graph."""

import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from gateway.memory_graph import unified_context, search_all, CONTEXT_TOKEN_CAP


@pytest.mark.asyncio
async def test_search_all_returns_all_keys():
    """search_all should always return the five canonical keys."""
    # Mocking external store fetchers to return empty lists
    with patch("gateway.memory_graph._fetch_memory", return_value=[]), patch(
        "gateway.memory_graph._fetch_knowledge", return_value=[]
    ), patch("gateway.memory_graph.search_entries", return_value=[]), patch(
        "gateway.memory_graph._fetch_traces", return_value=[]
    ), patch(
        "gateway.memory_graph._fetch_todos", return_value=[]
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
    # Mock one to fail, others to succeed
    with patch(
        "gateway.memory_graph._fetch_memory", side_effect=RuntimeError("Store down")
    ), patch(
        "gateway.memory_graph._fetch_knowledge", return_value=[{"text": "found it"}]
    ), patch(
        "gateway.memory_graph.search_entries", return_value=[]
    ), patch(
        "gateway.memory_graph._fetch_traces", return_value=[]
    ), patch(
        "gateway.memory_graph._fetch_todos", return_value=[]
    ):

        results = await search_all("test query")
        assert results["memory"] == []  # Isolated failure
        assert len(results["knowledge"]) == 1
        assert results["knowledge"][0]["text"] == "found it"


@pytest.mark.asyncio
async def test_unified_context_formatting():
    """unified_context should return a formatted string with sections."""
    mock_results = {
        "memory": [{"memory": "remembered this"}],
        "knowledge": [{"text": "learned this", "source": "book.pdf"}],
        "journal": [{"entry": "today I felt happy"}],
        "traces": [{"user_request": "how are you", "domain_classified": "chat"}],
    }

    with patch("gateway.memory_graph._fetch_all_stores", return_value=mock_results):
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
    # Create a result that will exceed the 1200 token (4800 char) cap
    long_text = "A" * (CONTEXT_TOKEN_CAP * 5)
    mock_results = {
        "memory": [{"memory": long_text}],
        "knowledge": [],
        "journal": [],
        "traces": [],
    }

    with patch("gateway.memory_graph._fetch_all_stores", return_value=mock_results):
        ctx = await unified_context("hello")
        # chars approx 4 * tokens
        assert len(ctx) <= (CONTEXT_TOKEN_CAP * 4) + 5
        assert ctx.endswith("…")


@pytest.mark.asyncio
async def test_real_journal_fetch_smoke(tmp_path, monkeypatch):
    """Test journal search_entries via the journal module with a temporary file."""
    journal_file = tmp_path / "journal_entries.jsonl"
    monkeypatch.setattr("gateway.journal.JOURNAL_LOG", journal_file)

    # Write some mock entries
    with open(journal_file, "w") as f:
        f.write(json.dumps({"entry": "the quick brown fox"}) + "\n")
        f.write(json.dumps({"entry": "lazy dog jumps"}) + "\n")
        f.write(json.dumps({"entry": "nothing here"}) + "\n")

    from gateway.journal import search_entries

    results = search_entries("quick dog")

    assert len(results) == 2
    # "quick brown fox" has "quick"
    # "lazy dog jumps" has "dog"
    assert any("quick" in r["entry"] for r in results)
    assert any("dog" in r["entry"] for r in results)


@pytest.mark.asyncio
async def test_real_trace_fetch_smoke(tmp_path, monkeypatch):
    """Test the real _fetch_traces logic with a temporary file."""
    import time

    trace_file = tmp_path / "gateway_trace.jsonl"
    monkeypatch.setattr("gateway.memory_graph.GATEWAY_LOG", trace_file)

    now = time.time()
    # Write some mock entries
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

    from gateway.memory_graph import _fetch_traces

    results = _fetch_traces("hvac")

    assert len(results) == 1
    assert results[0]["user_request"] == "fix the hvac"
    assert results[0]["domain_classified"] == "repair"
