"""Tests for gateway.memory_consolidation.prune_trace_log — trace log compaction.

This is the logic wired up as the "traces.compact" cron action (see
gateway/app.py). It used to be duplicated in the now-deleted
gateway/task_runner.py's `cleanup` task type; that duplicate is gone and
this is the one remaining implementation.
"""
import json
import time

from gateway.memory_consolidation import prune_trace_log


def test_drops_old_lines_keeps_recent(tmp_path):
    log = tmp_path / "trace.jsonl"
    now = time.time()
    old = {"timestamp": now - 40 * 86400, "user_request": "old"}
    fresh = {"timestamp": now - 1 * 86400, "user_request": "fresh"}
    log.write_text(json.dumps(old) + "\n" + json.dumps(fresh) + "\n")

    from unittest.mock import patch

    with patch("gateway.memory_consolidation.LOG_FILE", log):
        pruned = prune_trace_log(keep_days=30)

    assert pruned == 1
    remaining = log.read_text().splitlines()
    assert len(remaining) == 1
    assert json.loads(remaining[0])["user_request"] == "fresh"


def test_keeps_unparseable_lines(tmp_path):
    log = tmp_path / "trace.jsonl"
    log.write_text("not json\n")

    from unittest.mock import patch

    with patch("gateway.memory_consolidation.LOG_FILE", log):
        pruned = prune_trace_log(keep_days=30)

    assert pruned == 0
    assert log.read_text().splitlines() == ["not json"]


def test_no_log_file_is_a_noop(tmp_path):
    from unittest.mock import patch

    with patch("gateway.memory_consolidation.LOG_FILE", tmp_path / "missing.jsonl"):
        assert prune_trace_log(keep_days=30) == 0


def test_nothing_pruned_leaves_content_unchanged(tmp_path):
    log = tmp_path / "trace.jsonl"
    now = time.time()
    fresh = {"timestamp": now - 1 * 86400, "user_request": "fresh"}
    original = json.dumps(fresh) + "\n"
    log.write_text(original)

    from unittest.mock import patch

    with patch("gateway.memory_consolidation.LOG_FILE", log):
        pruned = prune_trace_log(keep_days=30)

    assert pruned == 0
    assert log.read_text() == original
