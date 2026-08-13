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
    }
    merged: dict[str, str | int | list[str] | None] = dict(base)
    merged.update(overrides)
    t = bq.create_task(**merged, db_path=db_path)  # type: ignore[arg-type]
    return t


# ---------------------------------------------------------------------------
# Tests: _normalize_state — exact mapping
# ---------------------------------------------------------------------------


class TestNormalizeState:
    """Builder states map to normalized Work states per the contract."""

    def test_queued_maps_to_pending(self):
        assert ws._normalize_state(bq.QUEUED) == "pending"

    def test_claimed_maps_to_pending(self):
        assert ws._normalize_state(bq.CLAIMED) == "pending"

    def test_running_maps_to_running(self):
        assert ws._normalize_state(bq.RUNNING) == "running"

    def test_blocked_maps_to_blocked(self):
        assert ws._normalize_state(bq.BLOCKED) == "blocked"

    def test_awaiting_review_maps_to_review(self):
        assert ws._normalize_state(bq.AWAITING_REVIEW) == "review"

    def test_pr_opened_maps_to_review(self):
        assert ws._normalize_state(bq.PR_OPENED) == "review"

    def test_done_maps_to_completed(self):
        assert ws._normalize_state(bq.DONE) == "completed"

    def test_failed_maps_to_failed(self):
        assert ws._normalize_state(bq.FAILED) == "failed"

    def test_cancelled_maps_to_cancelled(self):
        assert ws._normalize_state(bq.CANCELLED) == "cancelled"

    def test_all_mapped_states_are_valid(self):
        for builder_state in (
            bq.QUEUED, bq.CLAIMED, bq.RUNNING, bq.BLOCKED,
            bq.PR_OPENED, bq.AWAITING_REVIEW, bq.DONE, bq.FAILED,
            bq.CANCELLED,
        ):
            work_state = ws._normalize_state(builder_state)
            assert work_state in ws._WORK_STATES

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
# Tests: list_work — contract
# ---------------------------------------------------------------------------


class TestListWork:
    def test_empty_returns_empty_items(self, db_path: Path):
        campaign, items = ws.list_work(db_path=db_path)
        assert items == []

    def test_state_filter_pending_includes_queued(self, db_path: Path):
        _task(db_path=db_path, title="Queued task")
        campaign, items = ws.list_work(state="pending", db_path=db_path)
        assert len(items) == 1
        assert items[0]["state"] == "pending"
        assert items[0]["source_state"] == bq.QUEUED

    def test_state_filter_pending_includes_claimed(self, db_path: Path):
        t = _task(db_path=db_path, title="Claimed task")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        campaign, items = ws.list_work(state="pending", db_path=db_path)
        assert len(items) == 1
        assert items[0]["state"] == "pending"
        assert items[0]["source_state"] == bq.CLAIMED

    def test_state_filter_review_includes_pr_opened(self, db_path: Path):
        t = _task(db_path=db_path, title="PR opened")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(t["id"], bq.PR_OPENED, db_path=db_path)
        campaign, items = ws.list_work(state="review", db_path=db_path)
        assert len(items) == 1
        assert items[0]["state"] == "review"
        assert items[0]["source_state"] == bq.PR_OPENED

    def test_state_filter_review_includes_awaiting_review(self, db_path: Path):
        t = _task(db_path=db_path, title="Awaiting review")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(t["id"], bq.PR_OPENED, db_path=db_path)
        bq.transition_task(t["id"], bq.AWAITING_REVIEW, db_path=db_path)
        campaign, items = ws.list_work(state="review", db_path=db_path)
        assert len(items) == 1
        assert items[0]["state"] == "review"
        assert items[0]["source_state"] == bq.AWAITING_REVIEW

    def test_state_filter_completed(self, db_path: Path):
        t = _task(db_path=db_path, title="Done task")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(t["id"], bq.PR_OPENED, db_path=db_path)
        bq.transition_task(t["id"], bq.AWAITING_REVIEW, db_path=db_path)
        bq.transition_task(t["id"], bq.DONE, db_path=db_path)
        campaign, items = ws.list_work(state="completed", db_path=db_path)
        assert len(items) == 1
        assert items[0]["state"] == "completed"
        assert items[0]["source_state"] == bq.DONE

    def test_source_filter_only_builder(self, db_path: Path):
        _task(db_path=db_path, title="Task")
        campaign, items = ws.list_work(source="builder", db_path=db_path)
        assert len(items) == 1

    def test_non_builder_source_raises(self, db_path: Path):
        with pytest.raises(ws.WorkSourceError, match="unsupported source"):
            ws.list_work(source="initiative", db_path=db_path)

    def test_limit(self, db_path: Path):
        for _ in range(5):
            _task(db_path=db_path)
        campaign, items = ws.list_work(limit=2, db_path=db_path)
        assert len(items) == 2

    def test_limit_clamped(self, db_path: Path):
        campaign, items = ws.list_work(limit=1000, db_path=db_path)
        assert isinstance(items, list)

    def test_invalid_state_raises(self, db_path: Path):
        with pytest.raises(ws.WorkStateError, match="unrecognised Work state"):
            ws.list_work(state="bogus", db_path=db_path)

    def test_unknown_builder_state_fails_loud(self, db_path: Path):
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
        """Every list item has all required fields including evidence.approval."""
        t = _task(db_path=db_path, title="Shape test", priority=5)
        campaign, items = ws.list_work(db_path=db_path)
        assert len(items) == 1
        item = items[0]
        assert item["work_id"] == f"builder:{t['id']}"
        assert item["source"] == "builder"
        assert item["source_id"] == t["id"]
        assert item["title"] == "Shape test"
        assert item["summary"] == "A Builder queue task for testing"
        assert item["state"] == "pending"
        assert item["source_state"] == bq.QUEUED
        assert item["priority"] == 5
        assert "created_at" in item
        assert "updated_at" in item
        assert item["blocker"] is None
        assert item["error"] is None
        assert item["latest_run"] is None
        assert item["latest_pr"] is None
        assert item["links"] == []
        # evidence must always contain approval
        assert item["evidence"] is not None
        assert item["evidence"]["approval"]["state"] == "unavailable"
        assert "binding" in item["evidence"]["approval"]["reason"]


# ---------------------------------------------------------------------------
# Tests: list_work — campaign-level truth
# ---------------------------------------------------------------------------


class TestListWorkCampaign:
    def test_campaign_schema_version(self, db_path: Path):
        _task(db_path=db_path)
        campaign, _ = ws.list_work(db_path=db_path)
        assert campaign["schema_version"] == 1

    def test_campaign_observed_at_is_iso(self, db_path: Path):
        _task(db_path=db_path)
        campaign, _ = ws.list_work(db_path=db_path)
        assert "T" in campaign["observed_at"]

    def test_campaign_valid_until_30s_after(self, db_path: Path):
        from datetime import datetime

        _task(db_path=db_path)
        campaign, _ = ws.list_work(db_path=db_path)
        observed = datetime.fromisoformat(campaign["observed_at"])
        valid = datetime.fromisoformat(campaign["valid_until"])
        delta = valid - observed
        assert delta.total_seconds() == 30

    def test_campaign_source_health(self, db_path: Path):
        _task(db_path=db_path)
        campaign, _ = ws.list_work(db_path=db_path)
        assert campaign["source_health"] == {"kind": "builder", "state": "available"}

    def test_campaign_total_items_matches_full_set(self, db_path: Path):
        for _ in range(5):
            _task(db_path=db_path)
        campaign, items = ws.list_work(limit=2, db_path=db_path)
        assert campaign["total_items"] == 5
        assert campaign["item_limit"] == 2
        assert len(items) == 2

    def test_campaign_state_counts(self, db_path: Path):
        _task(db_path=db_path, title="Queued")
        t2 = _task(db_path=db_path, title="Running")
        bq.transition_task(t2["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t2["id"], bq.RUNNING, db_path=db_path)
        campaign, _ = ws.list_work(db_path=db_path)
        assert campaign["state_counts"]["pending"] == 1
        assert campaign["state_counts"]["running"] == 1

    def test_campaign_empty_returns_zero_totals(self, db_path: Path):
        campaign, items = ws.list_work(db_path=db_path)
        assert campaign["total_items"] == 0
        assert campaign["item_limit"] == 100
        assert campaign["state_counts"] == {}
        assert items == []


# ---------------------------------------------------------------------------
# Tests: get_work — contract
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
        assert item["source"] == "builder"
        assert item["source_id"] == t["id"]
        assert item["title"] == "Detail test"
        assert item["summary"] == "A description"
        assert item["state"] == "pending"
        assert item["source_state"] == bq.QUEUED
        assert "created_at" in item
        assert "updated_at" in item
        assert item["blocker"] is None
        assert item["error"] is None
        assert item["latest_run"] is None
        assert item["latest_pr"] is None
        assert item["links"] == []
        # evidence must always contain approval
        assert item["evidence"] is not None
        assert item["evidence"]["approval"]["state"] == "unavailable"
        assert "binding" in item["evidence"]["approval"]["reason"]

    def test_blocked_task_has_blocker(self, db_path: Path):
        t = _task(db_path=db_path, title="Blocked")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(
            t["id"], bq.BLOCKED, payload={"reason": "dep blocked"}, db_path=db_path
        )
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["state"] == "blocked"
        assert item["source_state"] == bq.BLOCKED
        assert item["blocker"] is not None

    def test_failed_task_has_error(self, db_path: Path):
        t = _task(db_path=db_path, title="Failed task")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(t["id"], bq.FAILED, db_path=db_path)
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["state"] == "failed"
        assert item["source_state"] == bq.FAILED

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

    def test_source_is_always_builder(self, db_path: Path):
        """source is always 'builder', never bridge_source."""
        t = _task(db_path=db_path, title="Bridge task", bridge_source="initiative")
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["source"] == "builder"
        assert item["source_id"] == t["id"]
        # evidence must always contain approval
        assert item["evidence"] is not None
        assert item["evidence"]["approval"]["state"] == "unavailable"

    def test_source_state_preserves_raw_builder_state(self, db_path: Path):
        t = _task(db_path=db_path, title="Raw state")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["state"] == "running"
        assert item["source_state"] == "running"

    def test_completed_only_from_done(self, db_path: Path):
        """Completed status is derived only from Builder task state done."""
        t = _task(db_path=db_path, title="Done task")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(t["id"], bq.PR_OPENED, db_path=db_path)
        bq.transition_task(t["id"], bq.AWAITING_REVIEW, db_path=db_path)
        bq.transition_task(t["id"], bq.DONE, db_path=db_path)
        item = ws.get_work(f"builder:{t['id']}", db_path=db_path)
        assert item["state"] == "completed"
        assert item["source_state"] == bq.DONE


# ---------------------------------------------------------------------------
# Tests: get_work_events — contract
# ---------------------------------------------------------------------------


class TestGetWorkEvents:
    def test_events_exist_for_task(self, db_path: Path):
        t = _task(db_path=db_path, title="Eventful")
        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        assert len(events) >= 1
        assert events[0]["type"] == "created"

    def test_returns_events_in_builder_order(self, db_path: Path):
        t = _task(db_path=db_path, title="Events test")
        bq.transition_task(t["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t["id"], bq.RUNNING, db_path=db_path)

        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        assert len(events) >= 3
        for i in range(1, len(events)):
            assert events[i]["id"] > events[i - 1]["id"]

    def test_event_preserves_source_timestamps(self, db_path: Path):
        t = _task(db_path=db_path, title="Timestamps")
        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        assert len(events) == 1
        assert "created_at" in events[0]

    def test_event_preserves_source_identity(self, db_path: Path):
        t = _task(db_path=db_path, title="Identity")
        events = ws.get_work_events(f"builder:{t['id']}", db_path=db_path)
        event = events[0]
        assert event["task_id"] == t["id"]
        assert event["type"] == "created"
        assert "id" in event

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
        source, parsed_id = ws._parse_work_id(work_id)
        assert source == "builder"
        assert parsed_id == t["id"]


# ---------------------------------------------------------------------------
# Tests: read-only guarantee
# ---------------------------------------------------------------------------


class TestReadOnly:
    """The work spine must never write to the Builder store."""

    def test_list_work_does_not_create_tasks(self, db_path: Path):
        ws.list_work(db_path=db_path)
        assert bq.list_tasks(db_path=db_path) == []

    def test_get_work_does_not_mutate_task(self, db_path: Path):
        t = _task(db_path=db_path, title="Immutability test")
        original = bq.get_task(t["id"], db_path=db_path)
        ws.get_work(f"builder:{t['id']}", db_path=db_path)
        after = bq.get_task(t["id"], db_path=db_path)
        assert original is not None and after is not None
        assert original["state"] == after["state"]
        assert original["updated_at"] == after["updated_at"]
