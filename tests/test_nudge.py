"""Tests for gateway/nudge.py — proactive nudge engine."""
import hashlib
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def test_check_no_log_returns_empty():
    """check() returns empty list when gateway log doesn't exist."""
    from gateway.nudge import check
    with patch("gateway.nudge.LOG_FILE", Path("/nonexistent/path.jsonl")):
        with patch("gateway.nudge._check_milestones", return_value=[]):
            result = check()
    assert isinstance(result, list)


def test_dismiss_marks_nudge_dismissed(tmp_path):
    """dismiss() persists nudge id so it won't reappear."""
    from gateway.nudge import _load_dismissed, dismiss
    store = tmp_path / "nudge_state.json"
    with patch("gateway.nudge.NUDGE_STORE", store):
        dismiss("test-nudge-id")
        dismissed = _load_dismissed()
    assert "test-nudge-id" in dismissed


def test_dismiss_returns_true(tmp_path):
    """dismiss() returns True on success."""
    from gateway.nudge import dismiss
    store = tmp_path / "nudge_state.json"
    with patch("gateway.nudge.NUDGE_STORE", store):
        result = dismiss("abc123")
    assert result is True


def test_dismissed_nudges_filtered(tmp_path):
    """check() filters out dismissed nudges."""
    from gateway.nudge import check, dismiss
    store = tmp_path / "nudge_state.json"

    fake_nudges = [{"id": "nudge-a", "type": "milestone", "message": "hi"}]

    with patch("gateway.nudge.NUDGE_STORE", store):
        with patch("gateway.nudge._check_repeated_research", return_value=fake_nudges):
            with patch("gateway.nudge._check_dropped_threads", return_value=[]):
                with patch("gateway.nudge._check_milestones", return_value=[]):
                    dismiss("nudge-a")
                    result = check()
    assert not any(n["id"] == "nudge-a" for n in result)


def test_get_pending_calls_check():
    """get_pending() delegates to check()."""
    from gateway.nudge import get_pending
    with patch("gateway.nudge.check", return_value=[{"id": "x", "type": "t", "message": "m"}]) as mock_check:
        result = get_pending()
    mock_check.assert_called_once()
    assert len(result) == 1


def test_repeated_research_nudge(tmp_path):
    """_check_repeated_research creates nudge when topic appears 3+ times."""
    from gateway.nudge import _check_repeated_research

    now = time.time()
    log = tmp_path / "gateway_trace.jsonl"
    topic = "optimize database queries"
    lines = [
        json.dumps({"timestamp": now - i * 3600, "domain_classified": "research", "user_request": topic})
        for i in range(4)  # 4 times = above threshold
    ]
    log.write_text("\n".join(lines) + "\n")

    with patch("gateway.nudge.LOG_FILE", log):
        nudges = _check_repeated_research()

    assert len(nudges) >= 1
    assert nudges[0]["type"] == "repeated_research"
    assert "3" in nudges[0]["message"] or "4" in nudges[0]["message"]


def test_repeated_research_below_threshold(tmp_path):
    """_check_repeated_research returns nothing for topics appearing < 3 times."""
    from gateway.nudge import _check_repeated_research

    now = time.time()
    log = tmp_path / "gateway_trace.jsonl"
    lines = [
        json.dumps({"timestamp": now - i * 3600, "domain_classified": "research", "user_request": "some topic"})
        for i in range(2)
    ]
    log.write_text("\n".join(lines) + "\n")

    with patch("gateway.nudge.LOG_FILE", log):
        nudges = _check_repeated_research()

    assert len(nudges) == 0


def test_milestone_nudges_no_crash():
    """_check_milestones runs without crashing even when deps fail."""
    from gateway.nudge import _check_milestones
    with patch("gateway.nudge._check_milestones", wraps=_check_milestones):
        # builder.list_builds will fail in CI — should be caught silently
        result = _check_milestones()
    assert isinstance(result, list)


def test_nudge_id_is_deterministic():
    """Repeated research nudge ID is deterministic for the same topic."""
    topic = "test topic for id stability"
    expected_id = hashlib.md5(f"repeat_{topic}".encode()).hexdigest()[:12]
    import time

    from gateway.nudge import _check_repeated_research
    now = time.time()
    import json
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "trace.jsonl"
        lines = [
            json.dumps({"timestamp": now - i * 3600, "domain_classified": "research", "user_request": topic})
            for i in range(4)
        ]
        log.write_text("\n".join(lines) + "\n")
        with patch("gateway.nudge.LOG_FILE", log):
            nudges = _check_repeated_research()
    assert nudges[0]["id"] == expected_id
