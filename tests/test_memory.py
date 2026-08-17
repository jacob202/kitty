"""Tests for Kitty memory layer."""

import json
from unittest.mock import MagicMock, patch



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
    mock_instance = MagicMock()
    mock_instance.search.return_value = {"results": []}
    from gateway.memory import get_context_block

    with patch("gateway.memory._get_memory", return_value=mock_instance):
        result = get_context_block("test query")

    assert result == ""


def test_get_context_block_formats_memories():
    """get_context_block formats every memory returned by the backend."""
    mock_results = {
        "results": [
            {"memory": "Jacob owns a 2010 Honda Civic", "metadata": {"namespace": "facts"}},
            {"memory": "Jacob is learning electronics", "metadata": {"namespace": "facts"}},
        ]
    }
    mock_instance = MagicMock()
    mock_instance.search.return_value = mock_results
    from gateway import memory as mem_module

    with patch.object(mem_module, "_get_memory", return_value=mock_instance):
        result = mem_module.get_context_block("Honda")

    assert "## What Kitty knows" in result
    assert "Jacob owns a 2010 Honda Civic" in result
    assert "Jacob is learning electronics" in result


class TestSessionConsolidationPersistence:
    """Issue #160 — a closed session must actually write a consolidation record."""

    def test_closed_session_writes_consolidation_record(self, tmp_path, monkeypatch):
        from gateway import memory as mem_module

        log = tmp_path / "session_consolidation_log.jsonl"
        monkeypatch.setattr(mem_module, "SESSION_CONSOLIDATION_LOG", log)
        # Simulate Mem0 accepting the entry.
        monkeypatch.setattr(
            mem_module, "add_memory", lambda text, namespace="sessions", metadata=None: True
        )

        messages = [
            {"role": "user", "content": "Let's migrate the gateway to FastAPI"},
            {"role": "assistant", "content": "Sure, here is a plan"},
            {"role": "user", "content": "Also wire up the session-end hook"},
        ]
        result = mem_module.consolidate_session("sess-123", messages)

        assert result is True
        assert log.exists()
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["session_id"] == "sess-123"
        assert record["user_message_count"] == 2
        assert record["stored_to_memory"] is True
        assert any("FastAPI" in t for t in record["topics"])

    def test_empty_session_records_no_consolidation(self, tmp_path, monkeypatch):
        from gateway import memory as mem_module

        log = tmp_path / "session_consolidation_log.jsonl"
        monkeypatch.setattr(mem_module, "SESSION_CONSOLIDATION_LOG", log)
        monkeypatch.setattr(
            mem_module, "add_memory", lambda text, namespace="sessions", metadata=None: False
        )

        assert mem_module.consolidate_session("sess-empty", []) is False
        # Record is written even when there is nothing to store, so the close is auditable.
        assert log.exists()
        record = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])
        assert record["user_message_count"] == 0
        assert record["stored_to_memory"] is False
