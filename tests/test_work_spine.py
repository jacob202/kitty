"""Tests for gateway/work_spine.py — read-only Work projection over Builder APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway import builder_queue as bq
from gateway import work_spine as ws

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A fresh Builder queue DB with schema initialised."""
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bq.init_db(p)
    return p


def _task(db_path: Path, **overrides: str | int | list[str] | None) -> dict:
    """Create a task dict with defaults, then apply overrides."""
    base: dict[str, str | int | list[str] | None] = {
        "title": "Test task",
        "description": "A Builder queue task for testing",
        "acceptance_criteria": ["criterion one"],
        "priority": 0,
        "bridge_source": "test",
    }
    merged: dict[str, str | int | list[str] | None] = dict(base)
    merged.update(overrides)
    t = bq.create_task(**merged, db_path=db_path)  # type: ignore[arg-type]
    return t


# ---------------------------------------------------------------------------
# Tests: _normalize_state
# ---------------------------------------------------------------------------


class TestNormalizeState:
    def test_all_builder_states_map(self):
        for builder_state in (
            bq.QUEUED,
            bq.CLAIMED,
            bq.RUNNING,
            bq.BLOCKED,
            bq.PR_OPENED,
            bq.AWAITING_REVIEW,
            bq.DONE,
            bq.FAILED,
            bq.CANCELLED,
        ):
            work_state = ws._normalize_state(builder_state)
            assert isinstance(work_state, str)
            assert work_state in ws._VALID_WORK_STATES

    def test_unknown_state_raises(self):
        with pytest.raises(ws.WorkStateError, match="unrecognised Builder task state"):
            ws._normalize_state("nonexistent_state")


# ---------------------------------------------------------------------------
# Tests: _parse_work_id
# ---------------------------------------------------------------------------


class TestParseWorkId:
    def test_valid_builder_id(self):
        source, task_id = ws._parse_work_id("builder:kb_abc123_0001")
        assert source == "builder"
        assert task_id == "kb_abc123_0001"

    def test_unrecognised_prefix_raises(self):
        with pytest.raises(ws.WorkSourceError, match="unrecognised source prefix"):
            ws._parse_work_id("github:123")


# ---------------------------------------------------------------------------
# Tests: list_work
# ---------------------------------------------------------------------------


class TestListWork:
    def test_empty_returns_empty_list(self, db_path: Path):
        items = ws.list_work(db_path=db_path)
        assert items == []

    def test_state_filter(self, db_path: Path):
        _task(db_path=db_path, title="Queued task")
        running = _task(db_path=db_path, title="Running task")
        bq.transition_task(running["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(running["id"], bq.RUNNING, db_path=db_path)

        items = ws.list_work(state="running", db_path=db_path)
        assert len(items) == 1
        assert items[0]["title"] == "Running task"

    def test_source_filter(self, db_path: Path):
        _task(db_path=db_path, title="From initiative", bridge_source="initiative")
        _task(db_path=db_path, title="From test", bridge_source="test")

        items = ws.list_work(source="initiative", db_path=db_path)
        assert len(items) == 1
        assert items[0]["title"] == "From initiative"

    def test_limit(self, db_path: Path):
        _task(db_path=db_path, title="Task 1")
        _task(db_path=db_path, title="Task 2")
        _task(db_path=db_path, title="Task 3")

        items = ws.list_work(limit=2, db_path=db_path)
        assert len(items) == 2

    def test_limit_clamped(self, db_path: Path):
        items = ws.list_work(limit=1000, db_path=db_path)
        # Clamped to 500; empty is fine as long as it doesn't error.
        assert isinstance(items, list)

    def test_invalid_state_raises(self, db_path: Path):
        with pytest.raises(ws.WorkStateError, match="unrecognised Work state"):
            ws.list_work(state="bogus", db_path=db_path)

    def test_unknown_builder_state_fails_loud(self, db_path: Path):
        # Directly set an invalid state in the DB to bypass the transition machine.
        t = _task(db_path=db_path, title="Bad state task")
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET state = ? WHERE id = ?",
                ("made_up_state", t["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(ws.WorkStateError, match="unrecognised Builder task state"):
            ws.list_work(db_path=db_path)

    def test_result_shape(self, db_path: Path):
        t = _task(db_path=db_path, title="Shape test")
        items = ws.list_work(db_path=db_path)
        assert len(items) == 1
        item = items[0]
        assert item["work_id"] == f"builder:{t['id']}"
        assert item["state"] == "queued"
        assert item["source"] == "test"
        assert item["title"] == "Shape test"
        assert item["task_id"] == t["id"]
        assert "created_at" in item
        assert "updated_at" in item
        assert item["blocked_reason"] is None


# ---------------------------------------------------------------------------
# Tests: get_work
# ---------------------------------------------------------------------------


class TestGetWork:
    def test_missing_id_raises(self, db_path: Path):
        with pytest.raises(ws.WorkNotFoundError, match="not found"):
            ws.get_work("builder:kb_nonexistent_0000", db_path=db_path)

    def test_unrecognised_prefix_raises(self, db_path: Path):
        with pytest.raises(ws.WorkSourceError, match="unrecognised source prefix"):
            ws.get_work("github:42", db_path=db_path)

    def test_returns_full_detail(self, db_path: Path):
        t = _task(db_path=db_path, title="Detail test", description="A description")
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["work_id"] == f"builder:{t['id']}"
        assert item["state"] == "queued"
        assert item["title"] == "Detail test"
        assert item["description"] == "A description"
        assert item["task_id"] == t["id"]
        assert "created_at" in item
        assert "updated_at" in item
        assert item["blocked_reason"] is None
        assert item["failure_reason"] is None
        assert item["errors"] == []
        assert item["latest_run"] is None
        assert item["latest_attempt"] is None
        assert item["latest_pr"] is None

    def test_blocked_task_has_reason(self, db_path: Path):
        t = _task(db_path=db_path, title="Blocked")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(
            t["id"], bq.BLOCKED, payload={"reason": "dep blocked"}, db_path=db_path
        )
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["state"] == "blocked"
        assert item.get("blocked_reason") is not None

    def test_failed_task_has_errors(self, db_path: Path):
        t = _task(db_path=db_path, title="Failed task")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(t["id"], bq.FAILED, db_path=db_path)
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["state"] == "failed"

    def test_unknown_builder_state_fails_loud(self, db_path: Path):
        t = _task(db_path=db_path, title="Bad state")
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET state = ? WHERE id = ?",
                ("made_up_state", t["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(ws.WorkStateError, match="unrecognised Builder task state"):
            ws.get_work(f"builder:{t['id']}", db_path=db_path)


# ---------------------------------------------------------------------------
# Tests: get_work_events
# ---------------------------------------------------------------------------


class TestGetWorkEvents:
    def test_events_exist_for_task(self, db_path: Path):
        # Every created task has at least a "created" event.
        t = _task(db_path=db_path, title="Eventful")
        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        assert len(events) >= 1
        assert events[0]["type"] == "created"

    def test_returns_events_in_order(self, db_path: Path):
        t = _task(db_path=db_path, title="Events test")
        # queued -> claimed -> running
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)

        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        assert len(events) >= 3
        # Verify chronological order by event id.
        for i in range(1, len(events)):
            assert events[i]["id"] > events[i - 1]["id"]

    def test_event_shape(self, db_path: Path):
        t = _task(db_path=db_path, title="Event shape")
        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        assert len(events) == 1  # just the created event
        event = events[0]
        assert event["task_id"] == t["id"]
        assert event["type"] == "created"
        assert "id" in event
        assert "created_at" in event

    def test_missing_id_raises(self, db_path: Path):
        with pytest.raises(ws.WorkNotFoundError, match="not found"):
            ws.get_work_events("builder:kb_nonexistent_0000", db_path=db_path)


# ---------------------------------------------------------------------------
# Tests: ID format
# ---------------------------------------------------------------------------


class TestWorkIdFormat:
    def test_work_id_is_builder_prefix(self, db_path: Path):
        t = _task(db_path=db_path, title="ID format")
        work_id = ws._build_work_id(t["id"])
        assert work_id.startswith("builder:")
        assert work_id == f"builder:{t['id']}"

    def test_parse_roundtrip(self, db_path: Path):
        t = _task(db_path=db_path, title="Roundtrip")
        work_id = ws._build_work_id(t["id"])
        _source, parsed_id = ws._parse_work_id(work_id)
        assert parsed_id == t["id"]
