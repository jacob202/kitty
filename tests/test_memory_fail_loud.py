"""Regression tests for memory persistence — session consolidation and dream insights.

Session close must actually store facts in long-term memory, not just log
and return True. Dream insights must write to disk and be readable.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from gateway import dream_insights, memory


def test_consolidate_session_stores_facts() -> None:
    messages = [
        {"role": "user", "content": "Let's build a CLI tool for backups"},
        {"role": "assistant", "content": "I'll create a backup script."},
        {"role": "user", "content": "Use Python with pathlib"},
        {"role": "assistant", "content": "Done. backup.py created."},
        {"role": "user", "content": "Add cron scheduling too"},
    ]
    stored = {}

    def mock_add(text, namespace="facts", metadata=None):
        stored["text"] = text
        stored["namespace"] = namespace
        stored["metadata"] = metadata

    with patch.object(memory, "add_memory", side_effect=mock_add):
        result = memory.consolidate_session("test-123", messages)

    assert result is True
    assert stored["namespace"] == "sessions"
    assert "test-123" in stored["text"]
    assert "backup" in stored["text"].lower()
    assert stored["metadata"]["session_id"] == "test-123"
    assert stored["metadata"]["message_count"] == 5
    assert stored["metadata"]["user_message_count"] == 3


def test_consolidate_session_empty_messages() -> None:
    result = memory.consolidate_session("test-empty", [])
    assert result is False


def test_consolidate_session_no_user_messages() -> None:
    messages = [{"role": "assistant", "content": "Hello"}]
    result = memory.consolidate_session("test-no-user", messages)
    assert result is False


def test_consolidate_session_backend_failure() -> None:
    messages = [{"role": "user", "content": "test"}]

    def boom(text, namespace="facts", metadata=None):
        raise RuntimeError("mem0 down")

    with patch.object(memory, "add_memory", side_effect=boom):
        result = memory.consolidate_session("test-fail", messages)

    assert result is False


def test_dream_insights_persist_to_disk(tmp_path: Path) -> None:
    insights_file = tmp_path / "dream_insights.json"
    with patch.object(dream_insights, "DREAM_INSIGHTS_FILE", insights_file):
        dream_insights.save_dream_insights(
            "Consolidated 3 trace clusters into long-term memory\n"
            "Pruned 12 old trace entries (kept last 30d)\n"
            "Weekly mirror refreshed"
        )

    assert insights_file.exists()
    cards = json.loads(insights_file.read_text())
    assert len(cards) == 3
    assert cards[0]["kind"] == "consolidation"
    assert cards[1]["kind"] == "maintenance"
    assert cards[2]["kind"] == "reflection"
    # All have required fields
    for card in cards:
        assert "insight_id" in card
        assert "title" in card
        assert "created_at" in card
        assert card["source"] == "nightly_dream"


def test_dream_insights_load_readable(tmp_path: Path) -> None:
    insights_file = tmp_path / "dream_insights.json"
    cards = [
        {
            "insight_id": "abc12345",
            "kind": "consolidation",
            "title": "Jacob decided to use FastAPI",
            "detail": "Jacob decided to use FastAPI for the gateway",
            "source": "nightly_dream",
            "confidence": 0.9,
            "created_at": "2026-07-12T10:00:00",
            "actions": [],
        }
    ]
    insights_file.write_text(json.dumps(cards))

    with patch.object(dream_insights, "DREAM_INSIGHTS_FILE", insights_file):
        loaded = dream_insights.load_dream_insights(limit=5)

    assert len(loaded) == 1
    assert loaded[0]["title"] == "Jacob decided to use FastAPI"
