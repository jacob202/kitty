"""Tests for gateway.honcho weekly pattern mirror."""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_get_recent_traces_empty_when_no_log(tmp_path):
    import gateway.honcho as h
    with patch.object(h, "GATEWAY_LOG", tmp_path / "nonexistent.jsonl"):
        assert h.get_recent_traces(days=7) == []


def test_get_recent_traces_filters_by_date(tmp_path):
    import gateway.honcho as h
    log = tmp_path / "trace.jsonl"
    now = time.time()
    entries = [
        {"timestamp": now - 100, "domain_classified": "soul", "user_request": "hello"},
        {"timestamp": now - 10 * 86400, "domain_classified": "code", "user_request": "old"},
    ]
    log.write_text("\n".join(json.dumps(e) for e in entries))
    with patch.object(h, "GATEWAY_LOG", log):
        result = h.get_recent_traces(days=7)
    assert len(result) == 1
    assert result[0]["domain_classified"] == "soul"


def test_get_recent_traces_ignores_malformed_lines(tmp_path):
    import gateway.honcho as h
    log = tmp_path / "trace.jsonl"
    recent = {"timestamp": time.time(), "domain_classified": "soul", "user_request": "hi"}
    log.write_text("not json\n" + json.dumps(recent))
    with patch.object(h, "GATEWAY_LOG", log):
        result = h.get_recent_traces(days=7)
    assert len(result) == 1


def test_summarize_patterns_fallback_on_empty():
    from gateway.honcho import summarize_patterns
    result = summarize_patterns([])
    assert isinstance(result, str)
    assert len(result) > 10


def test_summarize_patterns_calls_litellm():
    import gateway.honcho as h
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "You've been in repair mode this week."}}]
    }
    mock_resp.raise_for_status.return_value = None
    traces = [
        {"domain_classified": "repair", "user_request": "oil change question", "timestamp": time.time()},
    ]
    with patch.object(h, "requests") as mock_requests:
        mock_requests.post.return_value = mock_resp
        result = h.summarize_patterns(traces)
    assert isinstance(result, str)
    assert len(result) > 5


def test_summarize_patterns_handles_litellm_error():
    import gateway.honcho as h
    traces = [{"domain_classified": "soul", "user_request": "hello", "timestamp": time.time()}]
    with patch.object(h, "requests") as mock_requests:
        mock_requests.post.side_effect = Exception("connection refused")
        result = h.summarize_patterns(traces)
    assert isinstance(result, str)
    assert len(result) > 5


def test_get_weekly_mirror_schema(tmp_path):
    import gateway.honcho as h
    with patch.object(h, "GATEWAY_LOG", tmp_path / "empty.jsonl"):
        with patch.object(h, "SIGNAL_CACHE", tmp_path / "cache.json"):
            result = h.get_weekly_mirror(use_cache=False)
    assert result["signal_type"] == "weekly_observation"
    assert isinstance(result["observation"], str)
    assert 0.0 <= result["intensity"] <= 1.0
    assert "trace_count" in result["metadata"]


def test_get_weekly_mirror_uses_cache(tmp_path):
    import gateway.honcho as h
    cached = {
        "signal_type": "weekly_observation",
        "observation": "Cached observation.",
        "intensity": 0.7,
        "source_session_id": "weekly_mirror",
        "metadata": {"trace_count": 5, "days": 7},
        "_cached_at": time.time() - 100,
    }
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(cached))
    with patch.object(h, "SIGNAL_CACHE", cache_file):
        result = h.get_weekly_mirror(use_cache=True)
    assert result["observation"] == "Cached observation."
    assert "_cached_at" not in result
