"""Tests that web_monitor and nudge output land in the signal store and are
readable by memory_graph's SignalsAdapter.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gateway import signal_store


@pytest.fixture(autouse=True)
def isolate_signal_store(monkeypatch, tmp_path):
    """Keep signal tests away from live user data."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)


class TestWebMonitorEmitsSignals:
    def test_notify_match_emits_web_monitor_signal(self):
        from gateway.web_monitor import _notify_match

        watch = {
            "id": "abc123",
            "label": "Example Watch",
            "url": "https://example.com",
        }
        result = {"changed": True, "keyword_matches": ["launch", "kitty"]}

        with patch("gateway.notify.send"):
            _notify_match(watch, result)

        signals = signal_store.list_recent(source="web_monitor")
        assert len(signals) == 1
        assert signals[0]["kind"] == "watch_match"
        assert signals[0]["payload"]["watch_id"] == "abc123"
        assert signals[0]["payload"]["keyword_matches"] == ["launch", "kitty"]


class TestNudgeEmitsSignals:
    def test_check_emits_nudge_signals(self, tmp_path, monkeypatch):
        from gateway import nudge

        # Empty log so no real nudges fire.
        fake_log = tmp_path / "traces.jsonl"
        fake_log.write_text("")
        monkeypatch.setattr(nudge, "LOG_FILE", fake_log)

        # Inject a controlled active nudge.
        fake_nudges = [
            {
                "id": "nudge-test-1",
                "type": "repeated_research",
                "message": "You keep researching tests.",
                "priority": "medium",
            }
        ]
        monkeypatch.setattr(nudge, "_check_repeated_research", lambda: fake_nudges)
        monkeypatch.setattr(nudge, "_check_dropped_threads", lambda: [])
        monkeypatch.setattr(nudge, "_check_milestones", lambda: [])

        nudge.check()

        signals = signal_store.list_recent(source="nudge")
        assert len(signals) == 1
        assert signals[0]["kind"] == "repeated_research"
        assert signals[0]["payload"]["nudge_id"] == "nudge-test-1"


class TestMemoryGraphReadsSignals:
    @pytest.mark.asyncio
    async def test_signals_adapter_returns_recent_signals(self):
        signal_store.emit(
            source="web_monitor",
            kind="watch_match",
            payload={"label": "Test watch"},
        )
        signal_store.emit(
            source="nudge",
            kind="milestone",
            payload={"message": "First build"},
        )

        from gateway.memory_graph import SignalsAdapter

        adapter = SignalsAdapter()
        items = await adapter.fetch("")
        sources = {s["source"] for s in items}
        assert "web_monitor" in sources
        assert "nudge" in sources

    @pytest.mark.asyncio
    async def test_signals_adapter_format_includes_unseen(self):
        signal_store.emit(
            source="nudge",
            kind="repeated_research",
            payload={"message": "Keep shipping"},
        )

        from gateway.memory_graph import SignalsAdapter

        adapter = SignalsAdapter()
        items = await adapter.fetch("")
        formatted = adapter.format_items(items)
        assert "## Signals" in formatted
        assert "unseen" in formatted
        assert "Keep shipping" in formatted
