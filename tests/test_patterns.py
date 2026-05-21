"""Tests for gateway/patterns.py — longitudinal behavioral analysis."""
import json
import time
from pathlib import Path
from unittest.mock import patch


def _make_trace(domain: str = "code", hour_offset: int = 0, days_ago: int = 0) -> dict:
    ts = time.time() - days_ago * 86400 - hour_offset * 3600
    return {
        "timestamp": ts,
        "domain_classified": domain,
        "user_request": f"help with {domain}",
        "elapsed_ms": 800,
    }


def test_analyze_empty_returns_note():
    """analyze() returns a no-data note when no traces exist."""
    from gateway.patterns import analyze
    with patch("gateway.patterns._load_traces", return_value=[]):
        result = analyze(days=7)
    assert result["total_interactions"] == 0
    assert "note" in result


def test_analyze_counts_interactions(tmp_path):
    """analyze() counts total interactions correctly."""
    traces = [_make_trace("code") for _ in range(5)] + [_make_trace("research") for _ in range(3)]
    from gateway.patterns import analyze
    with patch("gateway.patterns._load_traces", return_value=traces):
        result = analyze(days=7)
    assert result["total_interactions"] == 8


def test_analyze_top_domains(tmp_path):
    """top_domains lists most common domains first."""
    traces = (
        [_make_trace("code")] * 10
        + [_make_trace("research")] * 4
        + [_make_trace("health")] * 2
    )
    from gateway.patterns import analyze
    with patch("gateway.patterns._load_traces", return_value=traces):
        result = analyze(days=30)
    domains = [d for d, _ in result["top_domains"]]
    assert domains[0] == "code"
    assert domains[1] == "research"


def test_analyze_trend_direction():
    """trend_direction reflects second half vs first half of weekly data."""
    from gateway.patterns import analyze

    now = time.time()
    # First half: 4 older weeks with sparse activity (1 trace each)
    old_traces = [
        {"timestamp": now - (7 * w + 1) * 86400, "domain_classified": "code", "user_request": "x", "elapsed_ms": 500}
        for w in range(8, 4, -1)  # weeks 8,7,6,5 ago → 1 trace/week
    ]
    # Second half: 4 recent weeks with heavy activity (10 traces each)
    new_traces = [
        {"timestamp": now - (7 * w + 1) * 86400, "domain_classified": "code", "user_request": "x", "elapsed_ms": 500}
        for w in range(4, 0, -1)  # weeks 4,3,2,1 ago
        for _ in range(10)
    ]
    with patch("gateway.patterns._load_traces", return_value=old_traces + new_traces):
        result = analyze(days=90)
    assert result["trend_direction"] == "increasing"


def test_weekly_calls_analyze_7_days():
    """weekly() delegates to analyze(days=7)."""
    from gateway.patterns import weekly
    with patch("gateway.patterns.analyze") as mock_analyze:
        mock_analyze.return_value = {"total_interactions": 5}
        result = weekly()
    mock_analyze.assert_called_once_with(days=7)
    assert result["total_interactions"] == 5


def test_get_insight_text_empty():
    """get_insight_text returns empty string when no data."""
    from gateway.patterns import get_insight_text
    with patch("gateway.patterns._load_traces", return_value=[]):
        text = get_insight_text(days=7)
    assert text == ""


def test_get_insight_text_has_content():
    """get_insight_text returns non-empty string when data present."""
    traces = [_make_trace("code")] * 5
    from gateway.patterns import get_insight_text
    with patch("gateway.patterns._load_traces", return_value=traces):
        text = get_insight_text(days=7)
    assert "Patterns" in text or "interactions" in text
    assert len(text) > 0


def test_analyze_peak_hour():
    """peak_hour identifies the most common interaction hour."""
    from gateway.patterns import analyze
    import datetime as dt

    # Build traces all at hour 14 (2pm)
    base = time.mktime(dt.datetime.now().replace(hour=14, minute=0, second=0).timetuple())
    traces = [{"timestamp": base + i * 60, "domain_classified": "code", "user_request": "x", "elapsed_ms": 500}
              for i in range(20)]
    # A few at hour 9
    base9 = time.mktime(dt.datetime.now().replace(hour=9, minute=0, second=0).timetuple())
    traces += [{"timestamp": base9 + i * 60, "domain_classified": "code", "user_request": "x", "elapsed_ms": 500}
               for i in range(3)]

    with patch("gateway.patterns._load_traces", return_value=traces):
        result = analyze(days=7)
    assert result["peak_hour"] == 14
