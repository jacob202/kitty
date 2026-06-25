"""Tests for Kitty memory layer."""
from unittest.mock import MagicMock, patch

import pytest


def test_memory_event_schema():
    """MemoryEvent validates correctly."""
    from datetime import datetime

    from contracts.memory_event import MemoryEvent, MemoryNamespace, MemorySensitivity
    event = MemoryEvent(
        text="Jacob owns a 2010 Honda Civic",
        namespace=MemoryNamespace.FACTS,
        sensitivity=MemorySensitivity.LOW,
        source="jacob_statement",
        confidence=1.0,
        human_confirmed=True,
    )
    assert event.namespace == MemoryNamespace.FACTS
    assert event.confidence == 1.0
    assert isinstance(event.created_at, datetime)


def test_memory_event_defaults():
    """MemoryEvent has sensible defaults."""
    from contracts.memory_event import MemoryEvent
    event = MemoryEvent(
        text="Jacob tends to research before acting",
        source="honcho_inferred",
        confidence=0.7,
    )
    assert event.allowed_models == ["cloud_ok"]
    assert event.human_confirmed is False


def test_get_context_block_empty_on_no_results():
    """get_context_block returns empty string when no memories found."""
    with patch("gateway.memory._get_memory") as mock_mem:
        mock_instance = MagicMock()
        mock_instance.search.return_value = {"results": []}
        mock_mem.return_value = mock_instance
        import gateway.memory
        from gateway.memory import get_context_block
        gateway.memory._get_memory.cache_clear()  # clear lru_cache
        with patch("gateway.memory._get_memory", return_value=mock_instance):
            result = get_context_block("test query")
        assert result == ""


def test_get_context_block_formats_memories():
    """get_context_block returns formatted block when memories exist."""
    mock_results = {
        "results": [
            {"memory": "Jacob owns a 2010 Honda Civic", "metadata": {"namespace": "facts"}},
            {"memory": "Jacob is learning electronics", "metadata": {"namespace": "facts"}},
        ]
    }
    with patch("gateway.memory._get_memory") as mock_get:
        mock_instance = MagicMock()
        mock_instance.search.return_value = mock_results
        mock_get.return_value = mock_instance
        from gateway import memory as mem_module
        with patch.object(mem_module, "_get_memory", return_value=mock_instance):
            result = mem_module.get_context_block("Honda")
    assert "Jacob owns a 2010 Honda Civic" in result
    assert "## What Kitty knows" in result


def test_add_memory_non_fatal_on_failure():
    """add_memory swallows exceptions — memory failure never crashes the gateway."""
    with patch("gateway.memory._get_memory", side_effect=Exception("DB error")):
        from gateway import memory as mem_module
        # Should not raise
        mem_module.add_memory("some fact", namespace="facts")


@pytest.mark.integration
def test_memory_roundtrip():
    """Write a fact, search for it, verify retrieval. Requires Ollama + OpenRouter."""
    from gateway.memory import add_memory, search_memory
    add_memory("Jacob's test fact: he owns a purple bicycle", namespace="facts")
    results = search_memory("bicycle", limit=3)
    texts = [r.get("memory", r.get("text", "")) for r in results]
    assert any("bicycle" in t.lower() for t in texts), f"Expected bicycle in: {texts}"
