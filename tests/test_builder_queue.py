"""PR 1 tests for gateway/builder_queue.py — durable queue store & schema.

Scope: only the PR 1 store/schema helpers. No transitions, claims, fencing,
release, expiry, CLI, daemon, or worker behavior is tested here (those are
PR 2-5).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gateway import builder_queue as bq


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A fresh DB path on a tmp filesystem. Initializes the schema."""
    p = tmp_path / "kittybuilder" / "builder_queue.db"
    bq.init_db(p)
    return p


def _count_events(conn: sqlite3.Connection, task_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM events WHERE task_id = ?", (task_id,)
    ).fetchone()
    return int(row[0])


def _count_created_events(conn: sqlite3.Connection, task_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM events WHERE task_id = ? AND type = 'created'",
        (task_id,),
    ).fetchone()
    return int(row[0])


def _count_events_of_type(conn: sqlite3.Connection, task_id: str, event_type: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM events WHERE task_id = ? AND type = ?",
        (task_id, event_type),
    ).fetchone()
    return int(row[0])


# ---------------------------------------------------------------------------
# Schema / init
# ---------------------------------------------------------------------------


class TestSchema:
    def test_db_initializes_successfully(self, db_path: Path):
        # init_db in the fixture already ran; verify the file exists and is a
        # usable SQLite db.
        assert db_path.exists()
        conn = bq.connect(db_path)
        try:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()

    def test_tables_exist(self, db_path: Path):
        conn = bq.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            names = {r[0] for r in rows}
            assert "tasks" in names
            assert "events" in names
            # runs/pr_links/artifacts are future tables and must NOT exist.
            assert "runs" not in names
            assert "pr_links" not in names
            assert "artifacts" not in names
        finally:
            conn.close()

    def test_required_indexes_exist(self, db_path: Path):
        conn = bq.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
            names = {r[0] for r in rows}
            assert "idx_tasks_claim" in names
            assert "idx_tasks_bridge_external" in names
        finally:
            conn.close()

    def test_idx_tasks_bridge_external_is_unique(self, db_path: Path):
        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_tasks_bridge_external'"
            ).fetchone()
            sql = row[0].lower()
            assert "unique" in sql
            assert "bridge_source" in sql
            assert "bridge_external_id" in sql
            # Partial index: only applies when both columns are non-null.
            assert "is not null" in sql
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Event log append-only triggers
# ---------------------------------------------------------------------------


class TestAppendOnlyEvents:
    def test_update_on_event_raises(self, db_path: Path):
        task = bq.create_task("t", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            with pytest.raises(sqlite3.DatabaseError) as excinfo:
                conn.execute("UPDATE events SET type='oops' WHERE task_id=?", (task["id"],))
            assert "append-only" in str(excinfo.value).lower()
        finally:
            conn.close()

    def test_delete_on_event_raises(self, db_path: Path):
        task = bq.create_task("t", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            with pytest.raises(sqlite3.DatabaseError) as excinfo:
                conn.execute("DELETE FROM events WHERE task_id=?", (task["id"],))
            assert "append-only" in str(excinfo.value).lower()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Task creation + 'created' event
# ---------------------------------------------------------------------------


class TestCreateTask:
    def test_persists_expected_fields(self, db_path: Path):
        task = bq.create_task(
            "title one",
            description="desc",
            acceptance_criteria=["criterion A", "criterion B"],
            priority=5,
            db_path=db_path,
        )
        assert task["id"].startswith("kb_")
        assert task["title"] == "title one"
        assert task["description"] == "desc"
        assert task["state"] == "queued"
        assert task["priority"] == 5
        assert task["acceptance_criteria"] == ["criterion A", "criterion B"]
        # Default lease/claim fields present and unset in PR 1.
        assert task["lease_owner"] is None
        assert task["lease_token"] is None
        assert task["lease_expires_at"] is None
        assert task["claim_version"] == 0
        assert task["archived_at"] is None

    def test_appends_exactly_one_created_event(self, db_path: Path):
        task = bq.create_task("t", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 1
            assert _count_created_events(conn, task["id"]) == 1
            row = conn.execute(
                "SELECT type FROM events WHERE task_id=?", (task["id"],)
            ).fetchone()
            assert row[0] == "created"
        finally:
            conn.close()

    def test_failed_duplicate_bridge_insert_no_second_created_event(
        self, db_path: Path
    ):
        first = bq.create_task(
            "first",
            bridge_source="github_issue",
            bridge_external_id="comment-1",
            db_path=db_path,
        )
        with pytest.raises(sqlite3.IntegrityError):
            bq.create_task(
                "dup",
                bridge_source="github_issue",
                bridge_external_id="comment-1",
                db_path=db_path,
            )
        conn = bq.connect(db_path)
        try:
            # First task: exactly one created event.
            assert _count_created_events(conn, first["id"]) == 1
            # No second task row was committed.
            rows = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE title='dup'"
            ).fetchone()
            assert rows[0] == 0
            # Total events still just the one from 'first'.
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert total == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# get_task
# ---------------------------------------------------------------------------


class TestGetTask:
    def test_returns_created_task(self, db_path: Path):
        created = bq.create_task(
            "abc",
            acceptance_criteria=["x"],
            db_path=db_path,
        )
        got = bq.get_task(created["id"], db_path=db_path)
        assert got is not None
        assert got["id"] == created["id"]
        assert got["title"] == "abc"
        assert got["acceptance_criteria"] == ["x"]

    def test_returns_none_for_unknown_id(self, db_path: Path):
        assert bq.get_task("kb_doesnotexist", db_path=db_path) is None


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_filters_by_state(self, db_path: Path):
        t1 = bq.create_task("a", db_path=db_path)
        # Create a second task and manually move it to a different state, since
        # PR 1 has no transition helper. This bypasses state-machine logic
        # (PR 2) by using a direct SQL update — we're only testing the query
        # filter on list_tasks here.
        t2 = bq.create_task("b", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute("UPDATE tasks SET state='blocked' WHERE id=?", (t2["id"],))
            conn.commit()
        finally:
            conn.close()

        queued = bq.list_tasks(state="queued", db_path=db_path)
        blocked = bq.list_tasks(state="blocked", db_path=db_path)
        assert {t["id"] for t in queued} == {t1["id"]}
        assert {t["id"] for t in blocked} == {t2["id"]}

    def test_excludes_archived_by_default(self, db_path: Path):
        t1 = bq.create_task("live", db_path=db_path)
        t2 = bq.create_task("archived", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET archived_at=CURRENT_TIMESTAMP WHERE id=?",
                (t2["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        listed = bq.list_tasks(db_path=db_path)
        ids = {t["id"] for t in listed}
        assert t1["id"] in ids
        assert t2["id"] not in ids

    def test_includes_archived_when_flagged(self, db_path: Path):
        t1 = bq.create_task("live", db_path=db_path)
        t2 = bq.create_task("archived", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET archived_at=CURRENT_TIMESTAMP WHERE id=?",
                (t2["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        listed = bq.list_tasks(include_archived=True, db_path=db_path)
        ids = {t["id"] for t in listed}
        assert t1["id"] in ids
        assert t2["id"] in ids


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------


class TestAcceptanceCriteria:
    def test_stored_and_retrievable(self, db_path: Path):
        bq.create_task(
            "t",
            acceptance_criteria=["c1", "c2", "c3"],
            db_path=db_path,
        )
        listed = bq.list_tasks(db_path=db_path)
        assert len(listed) == 1
        assert listed[0]["acceptance_criteria"] == ["c1", "c2", "c3"]
        # The raw JSON column should also be present and valid.
        assert listed[0]["acceptance_criteria_json"] == '["c1", "c2", "c3"]'

    def test_optional_acceptance_criteria(self, db_path: Path):
        t = bq.create_task("t", db_path=db_path)
        assert t["acceptance_criteria"] is None
        assert t["acceptance_criteria_json"] is None


# ---------------------------------------------------------------------------
# Bridge idempotency
# ---------------------------------------------------------------------------


class TestBridgeIdempotency:
    def test_same_source_and_external_id_twice_raises(self, db_path: Path):
        bq.create_task(
            "first",
            bridge_source="github_issue",
            bridge_external_id="c-1",
            db_path=db_path,
        )
        with pytest.raises(sqlite3.IntegrityError):
            bq.create_task(
                "second",
                bridge_source="github_issue",
                bridge_external_id="c-1",
                db_path=db_path,
            )

    def test_different_external_ids_from_same_issue_allowed(self, db_path: Path):
        bq.create_task(
            "first",
            bridge_source="github_issue",
            bridge_issue="#127",
            bridge_external_id="c-1",
            db_path=db_path,
        )
        second = bq.create_task(
            "second",
            bridge_source="github_issue",
            bridge_issue="#127",
            bridge_external_id="c-2",
            db_path=db_path,
        )
        assert second is not None
        assert second["bridge_issue"] == "#127"
        listed = bq.list_tasks(db_path=db_path)
        assert len(listed) == 2


# ---------------------------------------------------------------------------
# Reopen persistence
# ---------------------------------------------------------------------------


class TestReopenPersistence:
    def test_reopening_preserves_tasks_and_events(self, db_path: Path):
        t1 = bq.create_task("first", db_path=db_path)
        t2 = bq.create_task(
            "second",
            acceptance_criteria=["a"],
            bridge_source="github_issue",
            bridge_external_id="x-1",
            db_path=db_path,
        )

        # init_db is idempotent and should not destroy existing data.
        bq.init_db(db_path)

        got1 = bq.get_task(t1["id"], db_path=db_path)
        got2 = bq.get_task(t2["id"], db_path=db_path)
        assert got1 is not None and got1["title"] == "first"
        assert got2 is not None and got2["acceptance_criteria"] == ["a"]

        listed = bq.list_tasks(db_path=db_path)
        assert len(listed) == 2

        conn = bq.connect(db_path)
        try:
            # Each task has its 'created' event preserved across reopen.
            assert _count_created_events(conn, t1["id"]) == 1
            assert _count_created_events(conn, t2["id"]) == 1
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert total == 2
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Task ID helper
# ---------------------------------------------------------------------------


class TestTaskId:
    def test_id_format(self, db_path: Path):
        t = bq.create_task("t", db_path=db_path)
        tid = t["id"]
        assert tid.startswith("kb_")
        # kb_<base36>_<hex4>
        parts = tid.split("_")
        assert len(parts) == 3
        assert parts[0] == "kb"
        assert parts[1].isalnum()  # base36
        assert len(parts[2]) == 4  # hex4
        int(parts[2], 16)  # parses as hex

    def test_ids_time_sorted_within_ms(self, db_path: Path):
        # Two IDs generated in increasing time should preserve base36 ordering
        # (monotonic on a single machine at ms resolution).
        t1 = bq.create_task("a", db_path=db_path)
        import time as _time

        _time.sleep(0.005)
        t2 = bq.create_task("b", db_path=db_path)
        p1 = t1["id"].split("_")[1]
        p2 = t2["id"].split("_")[1]
        # base36 strings compare lexicographically when same length, but
        # length grows over time; compare as integers via base36 decode.
        def b36(s: str) -> int:
            return int(s, 36)

        assert b36(p2) >= b36(p1)


# ---------------------------------------------------------------------------
# Legal transition map (static contract tests)
# ---------------------------------------------------------------------------


class TestLegalTransitionMap:
    def test_contains_expected_paths(self):
        m = bq.LEGAL_TRANSITIONS

        valid = {
            (bq.QUEUED, bq.CLAIMED),
            (bq.QUEUED, bq.FAILED),
            (bq.QUEUED, bq.CANCELLED),
            (bq.CLAIMED, bq.RUNNING),
            (bq.CLAIMED, bq.QUEUED),
            (bq.CLAIMED, bq.FAILED),
            (bq.CLAIMED, bq.CANCELLED),
            (bq.RUNNING, bq.BLOCKED),
            (bq.RUNNING, bq.PR_OPENED),
            (bq.RUNNING, bq.FAILED),
            (bq.RUNNING, bq.CANCELLED),
            (bq.PR_OPENED, bq.AWAITING_REVIEW),
            (bq.PR_OPENED, bq.FAILED),
            (bq.PR_OPENED, bq.CANCELLED),
            (bq.AWAITING_REVIEW, bq.DONE),
            (bq.AWAITING_REVIEW, bq.FAILED),
            (bq.AWAITING_REVIEW, bq.CANCELLED),
            (bq.BLOCKED, bq.RUNNING),
            (bq.BLOCKED, bq.QUEUED),
            (bq.BLOCKED, bq.FAILED),
            (bq.BLOCKED, bq.CANCELLED),
        }
        for src, dst in valid:
            assert dst in m[src], f"missing: {src} -> {dst}"

        invalid = {
            (bq.RUNNING, bq.QUEUED),
            (bq.DONE, bq.QUEUED),
            (bq.QUEUED, bq.DONE),
            (bq.FAILED, bq.QUEUED),
            (bq.CANCELLED, bq.QUEUED),
            (bq.DONE, bq.DONE),
            (bq.FAILED, bq.FAILED),
            (bq.CANCELLED, bq.CANCELLED),
        }
        for src, dst in invalid:
            assert dst not in m[src], f"unexpected: {src} -> {dst}"


# ---------------------------------------------------------------------------
# Transition task
# ---------------------------------------------------------------------------


class TestTransitionTask:
    def _set_lease(
        self, db_path, task_id, owner="bot", token="tok", expires="2099-12-31 23:59:59"
    ):
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET lease_owner=?, lease_token=?, lease_expires_at=? WHERE id=?",
                (owner, token, expires, task_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _set_archived(self, db_path, task_id):
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET archived_at=CURRENT_TIMESTAMP WHERE id=?",
                (task_id,),
            )
            conn.commit()
        finally:
            conn.close()

    # -- happy path -----------------------------------------------------------

    def test_valid_transition_updates_state(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        result = bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        assert result["state"] == bq.CLAIMED

    def test_valid_transition_appends_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 2
            assert _count_events_of_type(conn, task["id"], bq.CLAIMED) == 1
        finally:
            conn.close()

    def test_transition_event_has_payload(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        payload = {"reason": "operator assigned", "engineer": "bot"}
        bq.transition_task(task["id"], bq.CLAIMED, payload=payload, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE task_id=? AND type=?",
                (task["id"], bq.CLAIMED),
            ).fetchone()
            assert row is not None
            assert json.loads(row[0]) == payload
        finally:
            conn.close()

    def test_transition_event_round_trips_payload(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        payload = {"key": "value", "nested": {"a": 1}}
        bq.transition_task(task["id"], bq.CLAIMED, payload=payload, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            row = conn.execute(
                "SELECT payload_json FROM events WHERE task_id=? AND type=?",
                (task["id"], bq.CLAIMED),
            ).fetchone()
            assert json.loads(row[0]) == payload
        finally:
            conn.close()

    # -- illegal transitions --------------------------------------------------

    def test_illegal_transition_raises(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        with pytest.raises(bq.IllegalTransitionError):
            bq.transition_task(task["id"], bq.DONE, db_path=db_path)

    def test_illegal_transition_appends_no_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        with pytest.raises(bq.IllegalTransitionError):
            bq.transition_task(task["id"], bq.DONE, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 1
        finally:
            conn.close()

    def test_running_to_queued_rejected(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        with pytest.raises(bq.IllegalTransitionError):
            bq.transition_task(task["id"], bq.QUEUED, db_path=db_path)

    def test_done_to_queued_rejected(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        for state in (bq.CLAIMED, bq.RUNNING, bq.PR_OPENED, bq.AWAITING_REVIEW, bq.DONE):
            bq.transition_task(task["id"], state, db_path=db_path)
        with pytest.raises(bq.IllegalTransitionError):
            bq.transition_task(task["id"], bq.QUEUED, db_path=db_path)

    # -- unknown task / state -------------------------------------------------

    def test_unknown_task_raises(self, db_path):
        with pytest.raises(bq.TaskNotFoundError):
            bq.transition_task("kb_nonexistent", bq.CLAIMED, db_path=db_path)

    def test_unknown_state_raises(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        with pytest.raises(ValueError, match="unknown state"):
            bq.transition_task(task["id"], "invalid_state", db_path=db_path)

    def test_unknown_state_appends_no_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        with pytest.raises(ValueError, match="unknown state"):
            bq.transition_task(task["id"], "invalid_state", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 1
        finally:
            conn.close()

    # -- terminal clears lease ------------------------------------------------

    def test_terminal_failed_clears_lease(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        self._set_lease(db_path, task["id"])
        result = bq.transition_task(task["id"], bq.FAILED, db_path=db_path)
        assert result["lease_owner"] is None
        assert result["lease_token"] is None
        assert result["lease_expires_at"] is None

    def test_terminal_cancelled_clears_lease(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        self._set_lease(db_path, task["id"])
        result = bq.transition_task(task["id"], bq.CANCELLED, db_path=db_path)
        assert result["lease_owner"] is None
        assert result["lease_token"] is None
        assert result["lease_expires_at"] is None

    def test_terminal_done_clears_lease(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        for state in (bq.CLAIMED, bq.RUNNING, bq.PR_OPENED, bq.AWAITING_REVIEW):
            bq.transition_task(task["id"], state, db_path=db_path)
        self._set_lease(db_path, task["id"])
        result = bq.transition_task(task["id"], bq.DONE, db_path=db_path)
        assert result["lease_owner"] is None
        assert result["lease_token"] is None
        assert result["lease_expires_at"] is None

    # -- non-terminal preserves lease -----------------------------------------

    def test_non_terminal_preserves_lease(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        self._set_lease(db_path, task["id"], owner="bot", token="tok", expires="2099-12-31")
        result = bq.transition_task(task["id"], bq.BLOCKED, db_path=db_path)
        assert result["lease_owner"] == "bot"
        assert result["lease_token"] == "tok"
        assert result["lease_expires_at"] is not None

    # -- blocked paths --------------------------------------------------------

    def test_blocked_to_running_allowed(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(task["id"], bq.BLOCKED, db_path=db_path)
        result = bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        assert result["state"] == bq.RUNNING

    def test_blocked_to_queued_allowed(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(task["id"], bq.BLOCKED, db_path=db_path)
        result = bq.transition_task(task["id"], bq.QUEUED, db_path=db_path)
        assert result["state"] == bq.QUEUED

    # -- updated_at -----------------------------------------------------------

    def test_updated_at_changes(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        before = task["updated_at"]
        result = bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        assert result["updated_at"] != before

    # -- archived -------------------------------------------------------------

    def test_archived_task_transition_raises(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        self._set_archived(db_path, task["id"])
        with pytest.raises(bq.IllegalTransitionError, match="archived"):
            bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)

    def test_archived_task_transition_appends_no_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        self._set_archived(db_path, task["id"])
        with pytest.raises(bq.IllegalTransitionError, match="archived"):
            bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 1
        finally:
            conn.close()

    # -- full lifecycle -------------------------------------------------------

    def test_full_lifecycle_transition(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        states = [bq.CLAIMED, bq.RUNNING, bq.PR_OPENED, bq.AWAITING_REVIEW, bq.DONE]
        for state in states:
            result = bq.transition_task(task["id"], state, db_path=db_path)
            assert result["state"] == state
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 6  # created + 5 transitions
        finally:
            conn.close()

    def test_claimed_to_queued_allowed(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        result = bq.transition_task(task["id"], bq.QUEUED, db_path=db_path)
        assert result["state"] == bq.QUEUED
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 3  # created + claimed + queued
            assert _count_events_of_type(conn, task["id"], bq.QUEUED) == 1
        finally:
            conn.close()
