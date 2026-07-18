"""Tests for TH-01 fail-loud sweep: every silent-swallow except now logs.

Verifies that the 11 touched modules emit a logger.warning or logger.error when
their previously-silent except paths are exercised.
"""

import json
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── cron.py ───────────────────────────────────────────────────────────────────

class TestCron:
    """_should_fire swallows invalid schedule values silently (now logs)."""

    def test_should_fire_interval_invalid(self, caplog):
        from gateway.cron import _should_fire

        caplog.set_level(logging.WARNING)
        result = _should_fire(
            {"schedule_type": "interval", "schedule_value": "not-a-number", "last_run": 0},
            0,
        )
        assert result is False
        assert any("Cron interval schedule invalid" in m for m in caplog.messages)

    def test_should_fire_daily_invalid(self, caplog):
        from gateway.cron import _should_fire

        caplog.set_level(logging.WARNING)
        result = _should_fire(
            {"schedule_type": "daily", "schedule_value": "abc:def", "last_run": 0},
            0,
        )
        assert result is False
        assert any("Cron daily schedule invalid" in m for m in caplog.messages)

    def test_should_fire_once_invalid(self, caplog):
        from gateway.cron import _should_fire

        caplog.set_level(logging.WARNING)
        result = _should_fire(
            {"schedule_type": "once", "schedule_value": "not-a-date", "last_run": 0},
            0,
        )
        assert result is False
        assert any("Cron once schedule invalid" in m for m in caplog.messages)

    def test_start_no_event_loop(self, caplog):
        """start() outside an async context logs a warning instead of silently returning."""
        from gateway.cron import start

        caplog.set_level(logging.WARNING)
        start()
        assert any("Cron start skipped" in m for m in caplog.messages)


# ── librarian.py ──────────────────────────────────────────────────────────────

class TestLibrarian:
    """generate_source_summary had silent fallback on LLM JSON parse failure."""

    def test_json_parse_failure_logs_warning(self, caplog):
        from gateway.librarian import generate_source_summary

        caplog.set_level(logging.WARNING)
        with patch("gateway.librarian.call_llm", return_value="not valid json"):
            result = generate_source_summary("test.pdf", "some text", "general")
        assert result is not None
        assert any("librarian JSON parse" in m for m in caplog.messages)

    def test_authority_score_normalization_failure(self, caplog):
        """Bad authority_score value triggers warning during normalization."""
        from gateway.librarian import generate_source_summary

        caplog.set_level(logging.WARNING)
        # Return JSON with an uncastable authority_score
        bad_json = json.dumps({
            "summary": "Test",
            "authority_score": "not-a-number",
            "relevance_period": "current",
            "safety_level": "low",
            "pollution_warning": None,
            "needs_vision": False,
            "primary_topic": "general",
        })
        with patch("gateway.librarian.call_llm", return_value=bad_json):
            result = generate_source_summary("test.pdf", "some text", "general")
        assert result is not None
        assert any("authority_score normalization" in m for m in caplog.messages)


# ── pdf_pipeline.py ───────────────────────────────────────────────────────────

class TestPdfPipeline:
    """_extract_text_fallback had two silent-swallow except: block."""

    def test_extract_fallback_failure_logs_warning(self, caplog):
        from gateway.pdf_pipeline import _extract_text_fallback

        caplog.set_level(logging.WARNING)
        result = _extract_text_fallback(Path("/nonexistent/test.pdf"))
        assert result == ""
        assert any("PyMuPDF extraction failed" in m for m in caplog.messages)
        assert any("pdfplumber extraction failed" in m for m in caplog.messages)


# ── clerk.py ──────────────────────────────────────────────────────────────────

class TestClerk:
    """_extract_text had a silent except when reading unknown file types."""

    def test_extract_text_json_read_failure_logs_warning(self, caplog):
        from gateway.clerk import _extract_text

        caplog.set_level(logging.WARNING)
        # A nonexistent .json path triggers FileNotFoundError when reading first char
        _extract_text(Path("/nonexistent/test.json"))
        assert any("Cannot read first char" in m for m in caplog.messages)

    def test_extract_text_unknown_type_failure_logs_warning(self, caplog):
        from gateway.clerk import _extract_text

        caplog.set_level(logging.WARNING)
        # A nonexistent unknown extension triggers the generic read_text fallback
        _extract_text(Path("/nonexistent/test.xyz"))
        assert any("Cannot read file" in m for m in caplog.messages)


# ── eval_runner.py ────────────────────────────────────────────────────────────

class TestEvalRunner:
    """_get_last_record had a silent except on corrupt/missing eval log."""

    def test_get_last_record_corrupt_log_warns(self, caplog, tmp_path):
        from gateway.eval_runner import _get_last_record

        caplog.set_level(logging.WARNING)
        corrupt_log = tmp_path / "eval_history.jsonl"
        corrupt_log.write_text("not valid json\n")
        with patch("gateway.eval_runner.EVAL_LOG", corrupt_log):
            result = _get_last_record()
        assert result is None
        assert any("Failed to read last eval record" in m for m in caplog.messages)


# ── expert_state.py ───────────────────────────────────────────────────────────

class TestExpertState:
    """is_global_pause and set_global_pause had silent JSONDecodeError swallows."""

    def test_is_global_pause_corrupt_file_warns(self, caplog, tmp_path):
        from gateway.expert_state import is_global_pause

        caplog.set_level(logging.WARNING)
        corrupt = tmp_path / "state.json"
        corrupt.write_text("not valid json")
        with patch("gateway.expert_state.EXPERT_STATE_FILE", corrupt):
            result = is_global_pause()
        assert result is False
        assert any("corrupt JSON" in m for m in caplog.messages)


# ── expert_proactive.py ───────────────────────────────────────────────────────

class TestExpertProactive:
    """_load_cursors silently swallowed JSONDecodeError on corrupt cursors file."""

    def test_load_cursors_corrupt_file_warns(self, caplog, tmp_path):
        from gateway.expert_proactive import _load_cursors

        caplog.set_level(logging.WARNING)
        corrupt = tmp_path / "cursors.json"
        corrupt.write_text("not valid json")
        with patch("gateway.paths.EXPERT_CURSORS_FILE", corrupt):
            result = _load_cursors()
        assert result == {}
        assert any("corrupt cursors" in m for m in caplog.messages)


# ── brief.py ──────────────────────────────────────────────────────────────────

class TestBrief:
    """_fetch_recent_journal_text and _fetch_memory_snippet had silent excepts."""

    def test_fetch_recent_journal_fails_warns(self, caplog, monkeypatch):
        from gateway.brief import _fetch_recent_journal_text

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(
            "gateway.brief.recent_entries",
            MagicMock(side_effect=Exception("db unavailable")),
        )
        result = _fetch_recent_journal_text()
        assert result == ""
        assert any("recent_entries failed" in m for m in caplog.messages)

    def test_fetch_memory_snippet_fails_warns(self, caplog, monkeypatch):
        from gateway.brief import _fetch_memory_snippet

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(
            "gateway.memory_graph.unified_context",
            MagicMock(side_effect=Exception("memory unavailable")),
        )
        result = _fetch_memory_snippet()
        assert result == ""
        assert any("_fetch_memory_snippet" in m for m in caplog.messages)


# ── nudge.py ──────────────────────────────────────────────────────────────────

class TestNudge:
    """_load_dismissed silently swallowed all exceptions."""

    def test_load_dismissed_corrupt_file_warns(self, caplog, tmp_path):
        from gateway.nudge import _load_dismissed

        caplog.set_level(logging.WARNING)
        corrupt = tmp_path / "nudge_state.json"
        corrupt.write_text("not valid json")
        with patch("gateway.nudge.NUDGE_STORE", corrupt):
            result = _load_dismissed()
        assert result == set()
        assert any("_load_dismissed" in m for m in caplog.messages)


# ── honcho.py ─────────────────────────────────────────────────────────────────

class TestHoncho:
    """get_weekly_mirror silently swallowed cache read failures."""

    def test_cache_read_corrupt_warns(self, caplog, tmp_path):
        from gateway.honcho import get_weekly_mirror

        caplog.set_level(logging.WARNING)
        corrupt = tmp_path / "honcho_weekly.json"
        corrupt.write_text("not valid json")
        with patch("gateway.honcho.SIGNAL_CACHE", corrupt):
            with patch("gateway.honcho.LOG_FILE", Path("/nonexistent/trace.jsonl")):
                result = get_weekly_mirror(use_cache=True)
        assert result is not None
        assert any("cache read failed" in m for m in caplog.messages)


# ── app.py ────────────────────────────────────────────────────────────────────

class TestApp:
    """Health endpoint silently swallowed LiteLLM connectivity failures."""

    def test_health_litellm_unreachable_warns(self, caplog, monkeypatch):
        from fastapi.testclient import TestClient

        from gateway.app import app

        caplog.set_level(logging.WARNING)

        async def mock_get_http_client():
            raise Exception("connection refused")

        monkeypatch.setattr("gateway.http_client.get_http_client", mock_get_http_client)
        with patch.dict(os.environ, {"KITTY_ENV": "test", "GATEWAY_SECRET": ""}):
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["litellm_reachable"] is False
        assert any("LiteLLM unreachable" in m for m in caplog.messages)
