"""Tests for gateway/honcho.py — weekly pattern mirror."""
import json
import time
from pathlib import Path
from unittest.mock import patch

# ── get_recent_traces ────────────────────────────────────────────────────────

def test_get_recent_traces_no_log():
    """Returns empty list when gateway log does not exist."""
    from gateway.honcho import get_recent_traces
    with patch("gateway.honcho.LOG_FILE", Path("/nonexistent/trace.jsonl")):
        result = get_recent_traces(days=7)
    assert result == []


def test_get_recent_traces_filters_old_entries(tmp_path):
    """Entries older than cutoff are excluded."""
    from gateway.honcho import get_recent_traces

    log = tmp_path / "trace.jsonl"
    now = time.time()
    old = {"timestamp": now - 10 * 86400, "domain_classified": "code", "user_request": "old"}
    fresh = {"timestamp": now - 1 * 86400, "domain_classified": "code", "user_request": "fresh"}
    log.write_text(json.dumps(old) + "\n" + json.dumps(fresh) + "\n")

    with patch("gateway.honcho.LOG_FILE", log):
        result = get_recent_traces(days=7)

    assert len(result) == 1
    assert result[0]["user_request"] == "fresh"


def test_get_recent_traces_includes_all_recent(tmp_path):
    """All entries within the window are returned."""
    from gateway.honcho import get_recent_traces

    log = tmp_path / "trace.jsonl"
    now = time.time()
    entries = [
        {"timestamp": now - i * 3600, "domain_classified": "research", "user_request": f"q{i}"}
        for i in range(5)
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    with patch("gateway.honcho.LOG_FILE", log):
        result = get_recent_traces(days=7)

    assert len(result) == 5


def test_get_recent_traces_skips_malformed_lines(tmp_path):
    """Malformed JSON lines are silently skipped."""
    from gateway.honcho import get_recent_traces

    log = tmp_path / "trace.jsonl"
    now = time.time()
    good = {"timestamp": now - 3600, "domain_classified": "code", "user_request": "good"}
    log.write_text("not json\n" + json.dumps(good) + "\n{broken\n")

    with patch("gateway.honcho.LOG_FILE", log):
        result = get_recent_traces(days=7)

    assert len(result) == 1
    assert result[0]["user_request"] == "good"


# ── summarize_patterns ───────────────────────────────────────────────────────

def test_summarize_patterns_empty_list():
    """Returns fallback string when no traces provided."""
    from gateway.honcho import _FALLBACK_EMPTY, summarize_patterns
    result = summarize_patterns([])
    assert result == _FALLBACK_EMPTY


def test_summarize_patterns_calls_llm():
    """Calls call_llm with traces summary and returns its output."""
    from gateway.honcho import summarize_patterns

    traces = [
        {"domain_classified": "code", "user_request": "fix this bug", "timestamp": time.time()}
        for _ in range(5)
    ]
    with patch("gateway.llm_client.call_llm", return_value="You've been coding a lot this week.") as mock_llm:
        result = summarize_patterns(traces)

    mock_llm.assert_called_once()
    assert result == "You've been coding a lot this week."


def test_summarize_patterns_llm_failure_returns_fallback():
    """LLM failure returns the error fallback string instead of raising."""
    from gateway.honcho import _FALLBACK_ERROR, summarize_patterns

    traces = [{"domain_classified": "code", "user_request": "x", "timestamp": time.time()}]
    with patch("gateway.llm_client.call_llm", side_effect=Exception("timeout")):
        result = summarize_patterns(traces)

    assert result == _FALLBACK_ERROR


# ── get_weekly_mirror ─────────────────────────────────────────────────────────

def test_get_weekly_mirror_returns_cache_when_fresh(tmp_path):
    """Returns cached signal without calling LLM when cache is < 23h old."""
    from gateway.honcho import get_weekly_mirror

    cache_path = tmp_path / "honcho_weekly.json"
    cached_signal = {
        "source_session_id": "weekly_mirror",
        "signal_type": "weekly_observation",
        "observation": "Cached observation.",
        "intensity": 0.7,
        "_cached_at": time.time() - 3600,  # 1h old → still fresh
    }
    cache_path.write_text(json.dumps(cached_signal))

    with patch("gateway.honcho.SIGNAL_CACHE", cache_path):
        with patch("gateway.honcho.summarize_patterns") as mock_summarize:
            result = get_weekly_mirror(days=7, use_cache=True)

    mock_summarize.assert_not_called()
    assert result["observation"] == "Cached observation."
    assert "_cached_at" not in result  # private keys stripped


def test_get_weekly_mirror_regenerates_stale_cache(tmp_path):
    """Regenerates when cached signal is > 23h old."""
    from gateway.honcho import get_weekly_mirror

    cache_path = tmp_path / "honcho_weekly.json"
    stale = {"observation": "old", "_cached_at": time.time() - 25 * 3600}
    cache_path.write_text(json.dumps(stale))

    with patch("gateway.honcho.SIGNAL_CACHE", cache_path):
        with patch("gateway.honcho.LOG_FILE", Path("/nonexistent/trace.jsonl")):
            with patch("gateway.honcho.summarize_patterns", return_value="Fresh observation."):
                result = get_weekly_mirror(days=7, use_cache=True)

    assert result["observation"] == "Fresh observation."


def test_get_weekly_mirror_no_cache(tmp_path):
    """With use_cache=False always regenerates."""
    from gateway.honcho import get_weekly_mirror

    cache_path = tmp_path / "honcho_weekly.json"
    fresh = {"observation": "should be ignored", "_cached_at": time.time()}
    cache_path.write_text(json.dumps(fresh))

    with patch("gateway.honcho.SIGNAL_CACHE", cache_path):
        with patch("gateway.honcho.LOG_FILE", Path("/nonexistent/trace.jsonl")):
            with patch("gateway.honcho.summarize_patterns", return_value="Regenerated."):
                result = get_weekly_mirror(days=7, use_cache=False)

    assert result["observation"] == "Regenerated."


def test_get_weekly_mirror_structure(tmp_path):
    """Returned dict has required HonchoSignal fields."""
    from gateway.honcho import get_weekly_mirror

    cache_path = tmp_path / "honcho_weekly.json"

    with patch("gateway.honcho.SIGNAL_CACHE", cache_path):
        with patch("gateway.honcho.LOG_FILE", Path("/nonexistent/trace.jsonl")):
            with patch("gateway.honcho.summarize_patterns", return_value="Weekly summary."):
                result = get_weekly_mirror(days=7, use_cache=False)

    assert "observation" in result
    assert "signal_type" in result
    assert result["signal_type"] == "weekly_observation"
    assert "intensity" in result
    assert "_cached_at" not in result
