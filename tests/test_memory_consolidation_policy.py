"""Tests for memory consolidation policy — NO_DURABLE_MEMORY, rewrite, prompt rules.

Uses monkeypatching to avoid real LLM calls while testing the orchestration
logic (skip on NO_DURABLE_MEMORY, rewrite sensitive summaries).
"""

from unittest.mock import patch

from gateway.memory_consolidation import consolidate_recent


def _make_trace(text: str, domain: str = "general", ts: float = 1_000_000) -> dict:
    return {
        "user_request": text,
        "domain_classified": domain,
        "timestamp": ts,
        "response": "",
    }


class TestNoDurableMemory:
    @patch("gateway.honcho.get_recent_traces")
    @patch("gateway.memory_consolidation._load_last_consolidation_ts")
    @patch("gateway.memory_consolidation._summarize_cluster")
    @patch("gateway.memory_consolidation._store_memory")
    def test_skips_on_no_durable_memory(
        self, mock_store, mock_summarize, mock_load_ts, mock_traces
    ):
        mock_traces.return_value = [_make_trace("feeling anxious", ts=1_000_100) for _ in range(5)]
        mock_load_ts.return_value = 0
        mock_summarize.return_value = "NO_DURABLE_MEMORY"

        count = consolidate_recent(days=3)

        assert count == 0, "should not count NO_DURABLE_MEMORY as a stored memory"
        mock_store.assert_not_called(), "should not store NO_DURABLE_MEMORY"

    @patch("gateway.honcho.get_recent_traces")
    @patch("gateway.memory_consolidation._load_last_consolidation_ts")
    @patch("gateway.memory_consolidation._summarize_cluster")
    @patch("gateway.memory_consolidation._store_memory")
    def test_skips_on_none_summary(
        self, mock_store, mock_summarize, mock_load_ts, mock_traces
    ):
        mock_traces.return_value = [_make_trace("building a thing", ts=1_000_100) for _ in range(5)]
        mock_load_ts.return_value = 0
        mock_summarize.return_value = None

        count = consolidate_recent(days=3)

        assert count == 0
        mock_store.assert_not_called()

    @patch("gateway.honcho.get_recent_traces")
    @patch("gateway.memory_consolidation._load_last_consolidation_ts")
    @patch("gateway.memory_consolidation._summarize_cluster")
    @patch("gateway.memory_consolidation._store_memory")
    def test_stores_normal_summary(
        self, mock_store, mock_summarize, mock_load_ts, mock_traces
    ):
        mock_traces.return_value = [_make_trace("added a new API endpoint", ts=1_000_100) for _ in range(5)]
        mock_load_ts.return_value = 0
        mock_summarize.return_value = "Jacob has been building a new API gateway."

        count = consolidate_recent(days=3)

        assert count == 1
        mock_store.assert_called_once()

    @patch("gateway.honcho.get_recent_traces")
    @patch("gateway.memory_consolidation._load_last_consolidation_ts")
    @patch("gateway.memory_consolidation._summarize_cluster")
    @patch("gateway.memory_consolidation._store_memory")
    def test_rewrites_sensitive_summary(
        self, mock_store, mock_summarize, mock_load_ts, mock_traces
    ):
        mock_traces.return_value = [_make_trace("spiraling about work", ts=1_000_100) for _ in range(5)]
        mock_load_ts.return_value = 0
        mock_summarize.return_value = "Jacob has been spiraling about work stress."

        count = consolidate_recent(days=3)

        assert count == 1
        stored_summary = mock_store.call_args[0][1]
        assert "prefers practical support" in stored_summary, \
            "sensitive summary should be rewritten before storage"
        assert "spiraling" not in stored_summary, \
            "psych framing should be removed"

    @patch("gateway.honcho.get_recent_traces")
    @patch("gateway.memory_consolidation._load_last_consolidation_ts")
    @patch("gateway.memory_consolidation._summarize_cluster")
    @patch("gateway.memory_consolidation._store_memory")
    def test_passes_domain_and_traces(
        self, mock_store, mock_summarize, mock_load_ts, mock_traces
    ):
        mock_traces.return_value = [
            _make_trace("working on frontend", domain="coding", ts=1_000_100) for _ in range(5)
        ]
        mock_load_ts.return_value = 0
        mock_summarize.return_value = "Jacob has been working on the frontend."

        consolidate_recent(days=3)

        assert mock_store.call_args[0][0] == "coding"
        assert len(mock_store.call_args[0][2]) == 5
