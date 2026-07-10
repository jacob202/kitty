"""PR 1 tests for gateway/builder_queue.py — durable queue store & schema.

Scope: only the PR 1 store/schema helpers. No transitions, claims, fencing,
release, expiry, CLI, daemon, or worker behavior is tested here (those are
PR 2-5).
"""

from __future__ import annotations

import json
import sqlite3
import threading
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


def _event_payloads(
    conn: sqlite3.Connection, task_id: str, event_type: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT payload_json FROM events
        WHERE task_id = ? AND type = ?
        ORDER BY id ASC
        """,
        (task_id, event_type),
    ).fetchall()
    return [json.loads(r[0]) if r[0] is not None else {} for r in rows]


def _set_task_fields(db_path: Path, task_id: str, **fields):
    if not fields:
        raise ValueError("fields are required")
    conn = bq.connect(db_path)
    try:
        assignments = ", ".join(f"{name}=?" for name in fields)
        conn.execute(
            f"UPDATE tasks SET {assignments} WHERE id=?",
            (*fields.values(), task_id),
        )
        conn.commit()
    finally:
        conn.close()


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
            # pr_links landed in Phase 1B; runs landed in Phase 1C-alpha.
            assert "pr_links" in names
            assert "runs" in names
            # artifacts is still a future table and must NOT exist.
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
            assert "idx_runs_one_active_per_task" in names
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
        self._set_lease(db_path, task["id"])
        result = bq.transition_task(task["id"], bq.QUEUED, db_path=db_path)
        assert result["state"] == bq.QUEUED
        assert result["lease_owner"] is None
        assert result["lease_token"] is None
        assert result["lease_expires_at"] is None

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
        self._set_lease(db_path, task["id"])
        result = bq.transition_task(task["id"], bq.QUEUED, db_path=db_path)
        assert result["state"] == bq.QUEUED
        assert result["lease_owner"] is None
        assert result["lease_token"] is None
        assert result["lease_expires_at"] is None
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == 3  # created + claimed + queued
            assert _count_events_of_type(conn, task["id"], bq.QUEUED) == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


class TestClaimTask:
    def _set_archived(self, db_path, task_id):
        _set_task_fields(db_path, task_id, archived_at="2099-12-31 23:59:59")

    def test_claiming_queued_task_sets_claim_state_and_lease_fields(self, db_path):
        task = bq.create_task("t", db_path=db_path)

        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        assert claimed["state"] == bq.CLAIMED
        assert claimed["lease_owner"] == "worker-a"
        assert isinstance(claimed["lease_token"], str)
        assert len(claimed["lease_token"]) == 64
        int(claimed["lease_token"], 16)
        assert claimed["claim_version"] == 1
        assert claimed["lease_expires_at"] is not None

    def test_claimed_event_is_appended_once_without_full_token(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        conn = bq.connect(db_path)
        try:
            assert _count_events_of_type(conn, task["id"], bq.CLAIMED) == 1
            payloads = _event_payloads(conn, task["id"], bq.CLAIMED)
        finally:
            conn.close()

        assert payloads == [{"worker": "worker-a", "claim_version": 1}]
        assert claimed["lease_token"] not in json.dumps(payloads)

    def test_double_claim_raises_conflict_and_appends_no_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.claim_task(task["id"], "worker-a", db_path=db_path)

        conn = bq.connect(db_path)
        try:
            before = _count_events(conn, task["id"])
        finally:
            conn.close()

        with pytest.raises(bq.LeaseConflictError):
            bq.claim_task(task["id"], "worker-b", db_path=db_path)

        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == before
            assert _count_events_of_type(conn, task["id"], bq.CLAIMED) == 1
        finally:
            conn.close()

    def test_expired_queued_lease_can_be_claimed(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        _set_task_fields(
            db_path,
            task["id"],
            lease_owner="stale-worker",
            lease_token="old-token",
            lease_expires_at="2000-01-01 00:00:00",
        )

        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        assert claimed["state"] == bq.CLAIMED
        assert claimed["lease_owner"] == "worker-a"
        assert claimed["lease_token"] != "old-token"
        assert claimed["claim_version"] == 1

    def test_expired_claimed_lease_reclaims_through_recovery_path(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        first = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        _set_task_fields(
            db_path,
            task["id"],
            lease_expires_at="2000-01-01 00:00:00",
        )

        with pytest.raises(bq.LeaseConflictError):
            bq.claim_task(task["id"], "worker-b", db_path=db_path)

        assert bq.recover_expired_leases(db_path=db_path) == {
            "claimed_requeued": 1,
            "running_blocked": 0,
            "total": 1,
        }
        second = bq.claim_task(task["id"], "worker-b", db_path=db_path)

        assert second["state"] == bq.CLAIMED
        assert second["lease_owner"] == "worker-b"
        assert second["lease_token"] != first["lease_token"]
        assert second["claim_version"] == first["claim_version"] + 1

    def test_running_task_cannot_be_claimed(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)

        with pytest.raises(bq.LeaseConflictError):
            bq.claim_task(task["id"], "worker-a", db_path=db_path)

    def test_archived_task_cannot_be_claimed(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        self._set_archived(db_path, task["id"])

        with pytest.raises(bq.IllegalTransitionError, match="archived"):
            bq.claim_task(task["id"], "worker-a", db_path=db_path)

    def test_claim_requires_positive_lease_seconds(self, db_path):
        task = bq.create_task("t", db_path=db_path)

        with pytest.raises(ValueError, match="lease_seconds"):
            bq.claim_task(
                task["id"],
                "worker-a",
                lease_seconds=0,
                db_path=db_path,
            )

    def test_claim_task_does_not_use_public_get_task_after_commit(
        self, db_path, monkeypatch
    ):
        task = bq.create_task("t", db_path=db_path)

        def fail_get_task(*args, **kwargs):
            raise AssertionError("claim_task must not read back through public get_task")

        monkeypatch.setattr(bq, "get_task", fail_get_task)

        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        assert claimed["id"] == task["id"]
        assert claimed["state"] == bq.CLAIMED
        assert claimed["lease_owner"] == "worker-a"
        assert claimed["claim_version"] == 1
        assert claimed["lease_token"] is not None

    def test_claim_task_returned_lease_cannot_be_stolen_by_post_commit_readback(
        self, db_path, monkeypatch
    ):
        task = bq.create_task("t", db_path=db_path)

        def racing_get_task(task_id, db_path=None):
            bq.operator_release_task(task_id, db_path=db_path)
            bq.claim_task(task_id, "worker-b", db_path=db_path)
            raise AssertionError("claim_task called public get_task after commit")

        monkeypatch.setattr(bq, "get_task", racing_get_task)

        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        assert claimed["lease_owner"] == "worker-a"
        assert claimed["claim_version"] == 1


class TestClaimNext:
    def test_returns_highest_priority_eligible_queued_task(self, db_path):
        low = bq.create_task("low", priority=1, db_path=db_path)
        high = bq.create_task("high", priority=10, db_path=db_path)

        claimed = bq.claim_next("worker-a", db_path=db_path)

        assert claimed is not None
        assert claimed["id"] == high["id"]
        assert bq.get_task(low["id"], db_path=db_path)["state"] == bq.QUEUED

    def test_breaks_equal_priority_by_id_ascending(self, db_path):
        first = bq.create_task("first", priority=5, db_path=db_path)
        second = bq.create_task("second", priority=5, db_path=db_path)
        expected_id = min(first["id"], second["id"])

        claimed = bq.claim_next("worker-a", db_path=db_path)

        assert claimed is not None
        assert claimed["id"] == expected_id

    def test_returns_none_when_queue_empty(self, db_path):
        assert bq.claim_next("worker-a", db_path=db_path) is None

    def test_requires_positive_lease_seconds_even_when_queue_empty(self, db_path):
        with pytest.raises(ValueError, match="lease_seconds"):
            bq.claim_next("worker-a", lease_seconds=0, db_path=db_path)

    def test_returns_none_when_all_tasks_have_active_claims(self, db_path):
        first = bq.create_task("first", db_path=db_path)
        second = bq.create_task("second", db_path=db_path)
        bq.claim_task(first["id"], "worker-a", db_path=db_path)
        bq.claim_task(second["id"], "worker-b", db_path=db_path)

        assert bq.claim_next("worker-c", db_path=db_path) is None

    def test_claim_next_does_not_use_public_get_task_after_commit(
        self, db_path, monkeypatch
    ):
        task = bq.create_task("t", db_path=db_path)

        def fail_get_task(*args, **kwargs):
            raise AssertionError("claim_next must not read back through public get_task")

        monkeypatch.setattr(bq, "get_task", fail_get_task)

        claimed = bq.claim_next("worker-a", db_path=db_path)

        assert claimed is not None
        assert claimed["id"] == task["id"]
        assert claimed["lease_owner"] == "worker-a"
        assert claimed["claim_version"] == 1
        assert claimed["lease_token"] is not None

    def test_claim_next_returned_lease_cannot_be_stolen_by_post_commit_readback(
        self, db_path, monkeypatch
    ):
        bq.create_task("t", db_path=db_path)

        def racing_get_task(task_id, db_path=None):
            bq.operator_release_task(task_id, db_path=db_path)
            bq.claim_task(task_id, "worker-b", db_path=db_path)
            raise AssertionError("claim_next called public get_task after commit")

        monkeypatch.setattr(bq, "get_task", racing_get_task)

        claimed = bq.claim_next("worker-a", db_path=db_path)

        assert claimed is not None
        assert claimed["lease_owner"] == "worker-a"
        assert claimed["claim_version"] == 1


# ---------------------------------------------------------------------------
# Worker release
# ---------------------------------------------------------------------------


class TestWorkerReleaseTask:
    def test_valid_worker_release_returns_task_to_queued_and_clears_lease(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        released = bq.worker_release_task(
            task["id"],
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        assert released["state"] == bq.QUEUED
        assert released["lease_owner"] is None
        assert released["lease_token"] is None
        assert released["lease_expires_at"] is None
        assert released["claim_version"] == claimed["claim_version"]

    def test_worker_release_returns_row_without_public_get_task(
        self, db_path, monkeypatch
    ):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        def fail_get_task(*args, **kwargs):
            raise AssertionError(
                "worker_release_task must not read back through public get_task"
            )

        monkeypatch.setattr(bq, "get_task", fail_get_task)

        released = bq.worker_release_task(
            task["id"],
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        assert released["id"] == task["id"]
        assert released["state"] == bq.QUEUED
        assert released["lease_owner"] is None
        assert released["claim_version"] == claimed["claim_version"]

    def test_valid_worker_release_appends_released_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        bq.worker_release_task(
            task["id"],
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        conn = bq.connect(db_path)
        try:
            assert _count_events_of_type(conn, task["id"], "released") == 1
            assert _count_events_of_type(conn, task["id"], bq.QUEUED) == 0
        finally:
            conn.close()

    def test_wrong_token_raises_conflict(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_release_task(
                task["id"],
                "wrong-token",
                claimed["claim_version"],
                db_path=db_path,
            )

    def test_wrong_claim_version_raises_conflict(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_release_task(
                task["id"],
                claimed["lease_token"],
                claimed["claim_version"] + 1,
                db_path=db_path,
            )

    def test_expired_lease_raises_conflict(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        _set_task_fields(
            db_path, task["id"], lease_expires_at="2000-01-01 00:00:00"
        )

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_release_task(
                task["id"],
                claimed["lease_token"],
                claimed["claim_version"],
                db_path=db_path,
            )

    def test_failed_release_appends_no_event_and_mutates_no_state(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            before_events = _count_events(conn, task["id"])
        finally:
            conn.close()

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_release_task(
                task["id"],
                "wrong-token",
                claimed["claim_version"],
                db_path=db_path,
            )

        after = bq.get_task(task["id"], db_path=db_path)
        assert after["state"] == bq.CLAIMED
        assert after["lease_owner"] == "worker-a"
        assert after["lease_token"] == claimed["lease_token"]
        assert after["claim_version"] == claimed["claim_version"]
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == before_events
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Operator release
# ---------------------------------------------------------------------------


class TestOperatorReleaseTask:
    def test_claimed_to_queued(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.claim_task(task["id"], "worker-a", db_path=db_path)

        released = bq.operator_release_task(task["id"], db_path=db_path)

        assert released["state"] == bq.QUEUED
        assert released["lease_owner"] is None
        assert released["lease_token"] is None
        assert released["lease_expires_at"] is None

    def test_operator_release_returns_row_without_public_get_task(
        self, db_path, monkeypatch
    ):
        task = bq.create_task("t", db_path=db_path)
        bq.claim_task(task["id"], "worker-a", db_path=db_path)

        def fail_get_task(*args, **kwargs):
            raise AssertionError(
                "operator_release_task must not read back through public get_task"
            )

        monkeypatch.setattr(bq, "get_task", fail_get_task)

        released = bq.operator_release_task(task["id"], db_path=db_path)

        assert released["id"] == task["id"]
        assert released["state"] == bq.QUEUED
        assert released["lease_owner"] is None

    def test_blocked_to_queued(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )
        blocked = bq.worker_transition_task(
            task["id"],
            bq.BLOCKED,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        released = bq.operator_release_task(blocked["id"], db_path=db_path)

        assert released["state"] == bq.QUEUED
        assert released["lease_owner"] is None
        assert released["lease_token"] is None
        assert released["lease_expires_at"] is None

    def test_event_type_is_operator_released_with_reason(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.claim_task(task["id"], "worker-a", db_path=db_path)

        bq.operator_release_task(
            task["id"], reason="operator reset", db_path=db_path
        )

        conn = bq.connect(db_path)
        try:
            assert _count_events_of_type(conn, task["id"], "operator_released") == 1
            assert _count_events_of_type(conn, task["id"], bq.QUEUED) == 0
            assert _event_payloads(conn, task["id"], "operator_released") == [
                {"reason": "operator reset"}
            ]
        finally:
            conn.close()

    def test_running_release_raises_clear_error(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        with pytest.raises(bq.IllegalTransitionError, match="must be blocked"):
            bq.operator_release_task(task["id"], db_path=db_path)

    def test_archived_task_raises(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.claim_task(task["id"], "worker-a", db_path=db_path)
        _set_task_fields(db_path, task["id"], archived_at="2099-12-31 23:59:59")

        with pytest.raises(bq.IllegalTransitionError, match="archived"):
            bq.operator_release_task(task["id"], db_path=db_path)


# ---------------------------------------------------------------------------
# Worker-fenced transitions
# ---------------------------------------------------------------------------


class TestWorkerTransitionTask:
    def test_claimed_to_running_works_with_valid_fence(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        running = bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        assert running["state"] == bq.RUNNING
        assert running["lease_token"] == claimed["lease_token"]
        assert running["claim_version"] == claimed["claim_version"]

    def test_worker_transition_returns_row_without_public_get_task(
        self, db_path, monkeypatch
    ):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        def fail_get_task(*args, **kwargs):
            raise AssertionError(
                "worker_transition_task must not read back through public get_task"
            )

        monkeypatch.setattr(bq, "get_task", fail_get_task)

        running = bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        assert running["id"] == task["id"]
        assert running["state"] == bq.RUNNING
        assert running["lease_token"] == claimed["lease_token"]
        assert running["claim_version"] == claimed["claim_version"]

    def test_running_to_blocked_works_with_valid_fence(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        blocked = bq.worker_transition_task(
            task["id"],
            bq.BLOCKED,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )

        assert blocked["state"] == bq.BLOCKED
        assert blocked["lease_token"] == claimed["lease_token"]

    def test_wrong_token_raises_conflict(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_transition_task(
                task["id"],
                bq.RUNNING,
                "wrong-token",
                claimed["claim_version"],
                db_path=db_path,
            )

    def test_wrong_claim_version_raises_conflict(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_transition_task(
                task["id"],
                bq.RUNNING,
                claimed["lease_token"],
                claimed["claim_version"] + 1,
                db_path=db_path,
            )

    def test_expired_lease_raises_conflict(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        _set_task_fields(
            db_path, task["id"], lease_expires_at="2000-01-01 00:00:00"
        )

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_transition_task(
                task["id"],
                bq.RUNNING,
                claimed["lease_token"],
                claimed["claim_version"],
                db_path=db_path,
            )

    def test_stale_worker_after_reclaim_is_rejected(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        worker_a = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        bq.worker_release_task(
            task["id"],
            worker_a["lease_token"],
            worker_a["claim_version"],
            db_path=db_path,
        )
        worker_b = bq.claim_task(task["id"], "worker-b", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            before_events = _count_events(conn, task["id"])
        finally:
            conn.close()

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_transition_task(
                task["id"],
                bq.RUNNING,
                worker_a["lease_token"],
                worker_a["claim_version"],
                db_path=db_path,
            )
        with pytest.raises(bq.LeaseConflictError):
            bq.worker_release_task(
                task["id"],
                worker_a["lease_token"],
                worker_a["claim_version"],
                db_path=db_path,
            )

        after = bq.get_task(task["id"], db_path=db_path)
        assert after["state"] == bq.CLAIMED
        assert after["lease_owner"] == "worker-b"
        assert after["lease_token"] == worker_b["lease_token"]
        assert after["claim_version"] == worker_b["claim_version"]
        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == before_events
        finally:
            conn.close()

    def test_no_event_on_failed_worker_transition(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            before_events = _count_events(conn, task["id"])
        finally:
            conn.close()

        with pytest.raises(bq.LeaseConflictError):
            bq.worker_transition_task(
                task["id"],
                bq.RUNNING,
                "wrong-token",
                claimed["claim_version"],
                db_path=db_path,
            )

        conn = bq.connect(db_path)
        try:
            assert _count_events(conn, task["id"]) == before_events
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Expired lease recovery
# ---------------------------------------------------------------------------


class TestRecoverExpiredLeases:
    def test_expired_claimed_lease_requeues_and_appends_released_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        _set_task_fields(
            db_path, task["id"], lease_expires_at="2000-01-01 00:00:00"
        )

        counts = bq.recover_expired_leases(db_path=db_path)

        recovered = bq.get_task(task["id"], db_path=db_path)
        assert recovered["state"] == bq.QUEUED
        assert recovered["lease_owner"] is None
        assert recovered["lease_token"] is None
        assert recovered["lease_expires_at"] is None
        assert recovered["claim_version"] == claimed["claim_version"]
        assert counts == {"claimed_requeued": 1, "running_blocked": 0, "total": 1}
        conn = bq.connect(db_path)
        try:
            assert _event_payloads(conn, task["id"], "released") == [
                {"reason": "lease_expired"}
            ]
        finally:
            conn.close()

    def test_expired_running_lease_blocks_and_appends_blocked_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        claimed = bq.claim_task(task["id"], "worker-a", db_path=db_path)
        bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )
        _set_task_fields(
            db_path, task["id"], lease_expires_at="2000-01-01 00:00:00"
        )

        counts = bq.recover_expired_leases(db_path=db_path)

        recovered = bq.get_task(task["id"], db_path=db_path)
        assert recovered["state"] == bq.BLOCKED
        assert recovered["blocked_reason"] == "stale_heartbeat"
        assert recovered["lease_owner"] is None
        assert recovered["lease_token"] is None
        assert recovered["lease_expires_at"] is None
        assert recovered["claim_version"] == claimed["claim_version"]
        assert counts == {"claimed_requeued": 0, "running_blocked": 1, "total": 1}
        conn = bq.connect(db_path)
        try:
            assert _event_payloads(conn, task["id"], bq.BLOCKED) == [
                {"reason": "stale_heartbeat"}
            ]
        finally:
            conn.close()

    def test_recovery_returns_total_counts_across_claimed_and_running(self, db_path):
        claimed_task = bq.create_task("claimed", db_path=db_path)
        running_task = bq.create_task("running", db_path=db_path)
        active_task = bq.create_task("active", db_path=db_path)
        claimed = bq.claim_task(claimed_task["id"], "worker-a", db_path=db_path)
        running = bq.claim_task(running_task["id"], "worker-b", db_path=db_path)
        bq.claim_task(active_task["id"], "worker-c", db_path=db_path)
        bq.worker_transition_task(
            running_task["id"],
            bq.RUNNING,
            running["lease_token"],
            running["claim_version"],
            db_path=db_path,
        )
        _set_task_fields(
            db_path, claimed_task["id"], lease_expires_at="2000-01-01 00:00:00"
        )
        _set_task_fields(
            db_path, running_task["id"], lease_expires_at="2000-01-01 00:00:00"
        )

        counts = bq.recover_expired_leases(db_path=db_path)

        assert counts == {"claimed_requeued": 1, "running_blocked": 1, "total": 2}
        assert bq.get_task(claimed_task["id"], db_path=db_path)["claim_version"] == (
            claimed["claim_version"]
        )
        assert bq.get_task(active_task["id"], db_path=db_path)["state"] == bq.CLAIMED


# ---------------------------------------------------------------------------
# Concurrent claim_next
# ---------------------------------------------------------------------------


class TestConcurrentClaimNext:
    def test_one_winner_and_nine_empty_results(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        barrier = threading.Barrier(10)
        results = []
        errors = []
        lock = threading.Lock()

        def claim(worker_index: int):
            try:
                barrier.wait()
                result = bq.claim_next(
                    f"worker-{worker_index}", db_path=db_path
                )
                with lock:
                    results.append(result)
            except Exception as exc:  # fail loud in the assertion below
                with lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=claim, args=(i,)) for i in range(10)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        winners = [r for r in results if r is not None]
        empty = [r for r in results if r is None]
        assert errors == []
        assert len(winners) == 1
        assert len(empty) == 9
        assert winners[0]["id"] == task["id"]
        final = bq.get_task(task["id"], db_path=db_path)
        assert final["state"] == bq.CLAIMED
        assert final["lease_owner"] is not None
        assert final["lease_token"] is not None
        assert final["claim_version"] == 1
        conn = bq.connect(db_path)
        try:
            assert _count_events_of_type(conn, task["id"], bq.CLAIMED) == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Edit task (queued-only)
# ---------------------------------------------------------------------------


class TestEditTask:
    def test_edit_title_of_queued_task(self, db_path):
        task = bq.create_task("original", db_path=db_path)
        edited = bq.edit_task(task["id"], title="updated", db_path=db_path)
        assert edited["title"] == "updated"
        assert edited["id"] == task["id"]

    def test_edit_description(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        edited = bq.edit_task(task["id"], description="new desc", db_path=db_path)
        assert edited["description"] == "new desc"

    def test_edit_priority(self, db_path):
        task = bq.create_task("t", priority=0, db_path=db_path)
        edited = bq.edit_task(task["id"], priority=99, db_path=db_path)
        assert edited["priority"] == 99

    def test_edit_acceptance_criteria(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        edited = bq.edit_task(
            task["id"], acceptance_criteria=["new c1", "new c2"], db_path=db_path
        )
        assert edited["acceptance_criteria"] == ["new c1", "new c2"]

    def test_edit_allowed_paths(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        edited = bq.edit_task(
            task["id"], allowed_paths=["gateway/", "tests/"], db_path=db_path
        )
        assert edited["allowed_paths"] == ["gateway/", "tests/"]

    def test_edit_appends_edited_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.edit_task(task["id"], title="updated", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events_of_type(conn, task["id"], "edited") == 1
        finally:
            conn.close()

    def test_edit_rejected_when_not_queued(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        with pytest.raises(bq.IllegalTransitionError, match="only queued"):
            bq.edit_task(task["id"], title="update", db_path=db_path)

    def test_edit_rejected_when_archived(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET archived_at=CURRENT_TIMESTAMP WHERE id=?",
                (task["id"],),
            )
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(bq.IllegalTransitionError, match="archived"):
            bq.edit_task(task["id"], title="update", db_path=db_path)

    def test_edit_raises_for_unknown_task(self, db_path):
        with pytest.raises(bq.TaskNotFoundError):
            bq.edit_task("kb_nonexistent", title="x", db_path=db_path)

    def test_edit_requires_at_least_one_field(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        with pytest.raises(ValueError, match="at least one"):
            bq.edit_task(task["id"], db_path=db_path)

    def test_edit_empty_title_raises(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        with pytest.raises(ValueError, match="title must be non-empty"):
            bq.edit_task(task["id"], title="   ", db_path=db_path)


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_returns_all_events_in_order(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)

        events = bq.list_events(task["id"], db_path=db_path)
        assert len(events) == 3
        assert events[0]["type"] == "created"
        assert events[1]["type"] == bq.CLAIMED
        assert events[2]["type"] == bq.RUNNING
        for ev in events:
            assert ev["task_id"] == task["id"]
            assert ev["id"] is not None

    def test_raises_for_unknown_task(self, db_path):
        with pytest.raises(bq.TaskNotFoundError):
            bq.list_events("kb_nonexistent", db_path=db_path)

    def test_returns_empty_list_for_task_without_events(self, db_path):
        # This can't happen under normal operation (created event is always
        # appended), but test the code path for robustness.
        conn = bq.connect(db_path)
        task_id = "kb_test0001_abcd"
        try:
            conn.execute(
                "INSERT INTO tasks (id, title) VALUES (?, ?)",
                (task_id, "orphan"),
            )
            conn.commit()
        finally:
            conn.close()
        events = bq.list_events(task_id, db_path=db_path)
        assert events == []


# ---------------------------------------------------------------------------
# queue_status
# ---------------------------------------------------------------------------


class TestQueueStatus:
    def test_empty_queue(self, db_path):
        status = bq.queue_status(db_path=db_path)
        assert status["total"] == 0
        assert status["queued"] == 0

    def test_counts_per_state(self, db_path):
        bq.create_task("t1", db_path=db_path)
        t2 = bq.create_task("t2", db_path=db_path)
        bq.transition_task(t2["id"], bq.CLAIMED, db_path=db_path)
        t3 = bq.create_task("t3", db_path=db_path)
        bq.transition_task(t3["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(t3["id"], bq.RUNNING, db_path=db_path)

        status = bq.queue_status(db_path=db_path)
        assert status["queued"] == 1
        assert status["claimed"] == 1
        assert status["running"] == 1
        assert status["total"] == 3
        assert status["per_state"]["queued"] == 1
        assert status["per_state"]["claimed"] == 1
        assert status["per_state"]["running"] == 1

    def test_excludes_archived(self, db_path):
        bq.create_task("live", db_path=db_path)
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

        status = bq.queue_status(db_path=db_path)
        assert status["total"] == 1
        assert status["queued"] == 1

    def test_all_states_present(self, db_path):
        status = bq.queue_status(db_path=db_path)
        for key in (
            "queued", "claimed", "running", "blocked",
            "pr_opened", "awaiting_review", "done", "failed", "cancelled",
        ):
            assert key in status, f"missing key: {key}"
        assert "per_state" in status


# ---------------------------------------------------------------------------
# archive_tasks
# ---------------------------------------------------------------------------


class TestArchiveTasks:
    def test_archive_requires_terminal_state(self, db_path):
        with pytest.raises(ValueError, match="terminal"):
            bq.archive_tasks(bq.QUEUED, older_than_days=0, db_path=db_path)

    def test_archive_requires_non_negative_days(self, db_path):
        with pytest.raises(ValueError, match="non-negative"):
            bq.archive_tasks(bq.DONE, older_than_days=-1, db_path=db_path)

    def test_archive_rejects_unknown_state(self, db_path):
        with pytest.raises(ValueError, match="unknown state"):
            bq.archive_tasks("invalid_state", older_than_days=0, db_path=db_path)

    def test_archives_old_done_tasks(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(task["id"], bq.PR_OPENED, db_path=db_path)
        bq.transition_task(task["id"], bq.AWAITING_REVIEW, db_path=db_path)
        bq.transition_task(task["id"], bq.DONE, db_path=db_path)
        # Set updated_at far in the past.
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET updated_at='2000-01-01 00:00:00' WHERE id=?",
                (task["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        result = bq.archive_tasks(bq.DONE, older_than_days=1, db_path=db_path)
        assert result["tasks_archived"] == 1
        assert task["id"] in result["task_ids"]

        archived = bq.get_task(task["id"], db_path=db_path)
        assert archived["archived_at"] is not None

    def test_archived_task_has_archived_event(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        bq.transition_task(task["id"], bq.CLAIMED, db_path=db_path)
        bq.transition_task(task["id"], bq.RUNNING, db_path=db_path)
        bq.transition_task(task["id"], bq.FAILED, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET updated_at='2000-01-01 00:00:00' WHERE id=?",
                (task["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        bq.archive_tasks(bq.FAILED, older_than_days=1, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            assert _count_events_of_type(conn, task["id"], "archived") == 1
        finally:
            conn.close()

    def test_does_not_archive_recent_tasks(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        for state in (bq.CLAIMED, bq.RUNNING, bq.PR_OPENED, bq.AWAITING_REVIEW, bq.DONE):
            bq.transition_task(task["id"], state, db_path=db_path)

        result = bq.archive_tasks(bq.DONE, older_than_days=365, db_path=db_path)
        assert result["tasks_archived"] == 0

        archived = bq.get_task(task["id"], db_path=db_path)
        assert archived["archived_at"] is None

    def test_archives_multiple_old_tasks(self, db_path):
        ids = []
        for _ in range(3):
            t = bq.create_task("t", db_path=db_path)
            for state in (
                bq.CLAIMED, bq.RUNNING, bq.PR_OPENED, bq.AWAITING_REVIEW, bq.DONE
            ):
                bq.transition_task(t["id"], state, db_path=db_path)
            conn = bq.connect(db_path)
            try:
                conn.execute(
                    "UPDATE tasks SET updated_at='2000-01-01 00:00:00' WHERE id=?",
                    (t["id"],),
                )
                conn.commit()
            finally:
                conn.close()
            ids.append(t["id"])

        result = bq.archive_tasks(bq.DONE, older_than_days=1, db_path=db_path)
        assert result["tasks_archived"] == 3
        assert set(result["task_ids"]) == set(ids)

    def test_does_not_archive_non_terminal_state(self, db_path):
        task = bq.create_task("t", db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET updated_at='2000-01-01 00:00:00' WHERE id=?",
                (task["id"],),
            )
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(ValueError, match="terminal"):
            bq.archive_tasks(bq.QUEUED, older_than_days=1, db_path=db_path)


# ---------------------------------------------------------------------------
# Phase 1B — attach_final_report
# ---------------------------------------------------------------------------


class TestAttachFinalReport:
    def _claimed_task(self, db_path: Path) -> dict:
        task = bq.create_task("report task", db_path=db_path)
        return bq.claim_task(task["id"], "worker-1", db_path=db_path)

    def test_fenced_attach_succeeds(self, db_path: Path):
        claimed = self._claimed_task(db_path)
        report = {"summary": "did the thing", "tests": "5/5 passed"}
        updated = bq.attach_final_report(
            claimed["id"],
            report,
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        assert json.loads(updated["final_report_json"]) == report
        with bq.connect(db_path) as conn:
            assert _count_events_of_type(conn, claimed["id"], "report_attached") == 1

    def test_stale_lease_rejected_no_event(self, db_path: Path):
        claimed = self._claimed_task(db_path)
        with pytest.raises(bq.LeaseConflictError):
            bq.attach_final_report(
                claimed["id"],
                {"summary": "stale"},
                lease_token="wrong-token",
                claim_version=claimed["claim_version"],
                db_path=db_path,
            )
        with bq.connect(db_path) as conn:
            assert _count_events_of_type(conn, claimed["id"], "report_attached") == 0
        refreshed = bq.get_task(claimed["id"], db_path=db_path)
        assert refreshed["final_report_json"] is None

    def test_operator_attach_without_lease(self, db_path: Path):
        task = bq.create_task("dead task", db_path=db_path)
        updated = bq.attach_final_report(
            task["id"],
            {"summary": "post-mortem"},
            operator_reason="worker crashed",
            db_path=db_path,
        )
        assert json.loads(updated["final_report_json"])["summary"] == "post-mortem"
        events = bq.list_events(task["id"], db_path=db_path)
        report_events = [e for e in events if e["type"] == "report_attached"]
        assert report_events[0]["payload"]["operator"] is True
        assert report_events[0]["payload"]["reason"] == "worker crashed"

    def test_requires_mode(self, db_path: Path):
        task = bq.create_task("no mode", db_path=db_path)
        with pytest.raises(ValueError):
            bq.attach_final_report(task["id"], {"summary": "x"}, db_path=db_path)

    def test_partial_fencing_rejected(self, db_path: Path):
        task = bq.create_task("partial", db_path=db_path)
        with pytest.raises(ValueError):
            bq.attach_final_report(
                task["id"], {"s": 1}, lease_token="t", db_path=db_path
            )

    def test_empty_report_rejected(self, db_path: Path):
        task = bq.create_task("empty", db_path=db_path)
        with pytest.raises(ValueError):
            bq.attach_final_report(
                task["id"], {}, operator_reason="x", db_path=db_path
            )

    def test_unknown_task(self, db_path: Path):
        with pytest.raises(bq.TaskNotFoundError):
            bq.attach_final_report(
                "kb_nope_0000", {"s": 1}, operator_reason="x", db_path=db_path
            )

    def test_reattach_overwrites_column_keeps_history(self, db_path: Path):
        claimed = self._claimed_task(db_path)
        for i in (1, 2):
            bq.attach_final_report(
                claimed["id"],
                {"summary": f"v{i}"},
                lease_token=claimed["lease_token"],
                claim_version=claimed["claim_version"],
                db_path=db_path,
            )
        refreshed = bq.get_task(claimed["id"], db_path=db_path)
        assert json.loads(refreshed["final_report_json"])["summary"] == "v2"
        with bq.connect(db_path) as conn:
            assert _count_events_of_type(conn, claimed["id"], "report_attached") == 2


# ---------------------------------------------------------------------------
# Phase 1B — attach_pr / get_pr_links
# ---------------------------------------------------------------------------


class TestAttachPr:
    def test_attach_creates_link_and_event(self, db_path: Path):
        task = bq.create_task("pr task", db_path=db_path)
        link = bq.attach_pr(
            task["id"],
            141,
            pr_url="https://github.com/jacob202/kitty/pull/141",
            head_sha="abc123",
            db_path=db_path,
        )
        assert link["pr_number"] == 141
        assert link["head_sha"] == "abc123"
        with bq.connect(db_path) as conn:
            assert _count_events_of_type(conn, task["id"], "pr_attached") == 1

    def test_attach_does_not_change_task_state(self, db_path: Path):
        task = bq.create_task("stays queued", db_path=db_path)
        bq.attach_pr(task["id"], 7, db_path=db_path)
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed["state"] == "queued"

    def test_reattach_updates_only_given_fields(self, db_path: Path):
        task = bq.create_task("update pr", db_path=db_path)
        bq.attach_pr(
            task["id"], 8, pr_url="https://x/8", head_sha="aaa", db_path=db_path
        )
        link = bq.attach_pr(
            task["id"], 8, checks_state="success", db_path=db_path
        )
        assert link["pr_url"] == "https://x/8"
        assert link["head_sha"] == "aaa"
        assert link["checks_state"] == "success"
        with bq.connect(db_path) as conn:
            assert _count_events_of_type(conn, task["id"], "pr_updated") == 1

    def test_multiple_prs_per_task(self, db_path: Path):
        task = bq.create_task("two prs", db_path=db_path)
        bq.attach_pr(task["id"], 10, db_path=db_path)
        bq.attach_pr(task["id"], 11, db_path=db_path)
        links = bq.get_pr_links(task["id"], db_path=db_path)
        assert [link["pr_number"] for link in links] == [10, 11]

    def test_invalid_pr_number(self, db_path: Path):
        task = bq.create_task("bad pr", db_path=db_path)
        with pytest.raises(ValueError):
            bq.attach_pr(task["id"], 0, db_path=db_path)

    def test_unknown_task(self, db_path: Path):
        with pytest.raises(bq.TaskNotFoundError):
            bq.attach_pr("kb_nope_0000", 5, db_path=db_path)
        with pytest.raises(bq.TaskNotFoundError):
            bq.get_pr_links("kb_nope_0000", db_path=db_path)

    def test_no_links_returns_empty(self, db_path: Path):
        task = bq.create_task("no prs", db_path=db_path)
        assert bq.get_pr_links(task["id"], db_path=db_path) == []


# ---------------------------------------------------------------------------
# Phase 1C-alpha — renew_lease
# ---------------------------------------------------------------------------


class TestRenewLease:
    def test_renew_extends_expiry(self, db_path: Path):
        task = bq.create_task("hb", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", lease_seconds=60, db_path=db_path)
        renewed = bq.renew_lease(
            claimed["id"],
            claimed["lease_token"],
            claimed["claim_version"],
            lease_seconds=3600,
            db_path=db_path,
        )
        assert renewed["lease_expires_at"] > claimed["lease_expires_at"]

    def test_stale_token_rejected(self, db_path: Path):
        task = bq.create_task("hb2", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        with pytest.raises(bq.LeaseConflictError):
            bq.renew_lease(
                claimed["id"], "wrong", claimed["claim_version"], db_path=db_path
            )

    def test_expired_lease_cannot_renew(self, db_path: Path):
        task = bq.create_task("hb3", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", lease_seconds=1, db_path=db_path)
        conn = bq.connect(db_path)
        try:
            conn.execute(
                "UPDATE tasks SET lease_expires_at = "
                "strftime('%Y-%m-%d %H:%M:%f', 'now', '-10 seconds') WHERE id = ?",
                (claimed["id"],),
            )
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(bq.LeaseConflictError):
            bq.renew_lease(
                claimed["id"],
                claimed["lease_token"],
                claimed["claim_version"],
                db_path=db_path,
            )

    def test_no_event_appended(self, db_path: Path):
        task = bq.create_task("hb4", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        with bq.connect(db_path) as conn:
            before = _count_events(conn, claimed["id"])
        bq.renew_lease(
            claimed["id"],
            claimed["lease_token"],
            claimed["claim_version"],
            db_path=db_path,
        )
        with bq.connect(db_path) as conn:
            assert _count_events(conn, claimed["id"]) == before


# ---------------------------------------------------------------------------
# Phase 1C-alpha — run records
# ---------------------------------------------------------------------------


class TestRunRecords:
    @staticmethod
    def _claim(task: dict, db_path: Path) -> dict:
        return bq.claim_task(task["id"], "runner", db_path=db_path)

    def test_create_run_requires_current_claim(self, db_path: Path):
        task = bq.create_task("must be claimed", db_path=db_path)

        with pytest.raises(bq.LeaseConflictError, match="claimed task"):
            bq.create_run(
                task["id"],
                ["true"],
                lease_token="not-a-current-token",
                claim_version=0,
                db_path=db_path,
            )

    def test_create_and_get_run(self, db_path: Path):
        task = bq.create_task("run me", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["echo", "hi"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            worker="w1",
            model="m",
            provider="p",
            branch="kittybuilder/x",
            start_sha="abc123",
            db_path=db_path,
        )
        assert run["state"] == bq.RUN_STARTING
        assert run["command"] == ["echo", "hi"]
        assert run["claim_version"] == claimed["claim_version"]
        assert run["start_sha"] == "abc123"
        fetched = bq.get_run(run["id"], db_path=db_path)
        assert fetched is not None and fetched["worker"] == "w1"

    def test_create_run_unknown_task(self, db_path: Path):
        with pytest.raises(bq.TaskNotFoundError):
            bq.create_run(
                "kb_nope_0000",
                ["true"],
                lease_token="missing",
                claim_version=1,
                db_path=db_path,
            )

    def test_empty_command_rejected(self, db_path: Path):
        task = bq.create_task("no cmd", db_path=db_path)
        with pytest.raises(ValueError):
            bq.create_run(
                task["id"],
                [],
                lease_token="unused",
                claim_version=0,
                db_path=db_path,
            )

    def test_second_active_run_for_same_task_is_rejected(self, db_path: Path):
        task = bq.create_task("one active attempt", db_path=db_path)
        claimed = self._claim(task, db_path)
        fencing = {
            "lease_token": claimed["lease_token"],
            "claim_version": claimed["claim_version"],
        }
        first = bq.create_run(task["id"], ["first"], **fencing, db_path=db_path)

        with pytest.raises(bq.ActiveRunConflictError, match="active run"):
            bq.create_run(task["id"], ["second"], **fencing, db_path=db_path)

        bq.update_run(first["id"], state=bq.RUN_EXITED, db_path=db_path)
        second = bq.create_run(
            task["id"], ["second"], **fencing, db_path=db_path
        )
        assert second["state"] == bq.RUN_STARTING

    def test_list_runs_filters(self, db_path: Path):
        t1 = bq.create_task("t1", db_path=db_path)
        t2 = bq.create_task("t2", db_path=db_path)
        c1 = self._claim(t1, db_path)
        c2 = self._claim(t2, db_path)
        r1 = bq.create_run(
            t1["id"],
            ["a"],
            lease_token=c1["lease_token"],
            claim_version=c1["claim_version"],
            db_path=db_path,
        )
        bq.create_run(
            t2["id"],
            ["b"],
            lease_token=c2["lease_token"],
            claim_version=c2["claim_version"],
            db_path=db_path,
        )
        bq.update_run(r1["id"], state=bq.RUN_EXITED, db_path=db_path)
        assert len(bq.list_runs(db_path=db_path)) == 2
        assert len(bq.list_runs(task_id=t1["id"], db_path=db_path)) == 1
        assert len(bq.list_runs(state=bq.RUN_EXITED, db_path=db_path)) == 1

    def test_update_run_expected_state_guard(self, db_path: Path):
        task = bq.create_task("guard", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["x"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(run["id"], state=bq.RUN_CANCELLED, db_path=db_path)
        with pytest.raises(ValueError):
            bq.update_run(
                run["id"],
                state=bq.RUN_RUNNING,
                expected_states=bq.RUN_ACTIVE_STATES,
                db_path=db_path,
            )

    def test_terminal_run_cannot_be_resurrected(self, db_path: Path):
        task = bq.create_task("terminal means terminal", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(run["id"], state=bq.RUN_EXITED, db_path=db_path)

        with pytest.raises(bq.RunStateConflictError, match="exited -> running"):
            bq.update_run(run["id"], state=bq.RUN_RUNNING, db_path=db_path)

    def test_finalize_run_preserves_worker_advanced_task_state(self, db_path: Path):
        task = bq.create_task("worker handles its own stop state", db_path=db_path)
        claimed = self._claim(task, db_path)
        lease_token = claimed["lease_token"]
        claim_version = claimed["claim_version"]
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=lease_token,
            claim_version=claim_version,
            db_path=db_path,
        )
        bq.worker_transition_task(
            task["id"],
            bq.RUNNING,
            lease_token,
            claim_version,
            db_path=db_path,
        )
        bq.update_run(run["id"], state=bq.RUN_RUNNING, db_path=db_path)
        bq.worker_transition_task(
            task["id"],
            bq.BLOCKED,
            lease_token,
            claim_version,
            payload={"reason": "worker_requested_review"},
            db_path=db_path,
        )

        final = bq.finalize_run(
            run["id"],
            bq.RUN_EXITED,
            exit_code=0,
            report={"summary": "worker completed its own handoff"},
            lease_token=lease_token,
            claim_version=claim_version,
            block_reason="shadow_run_complete",
            db_path=db_path,
        )

        assert final["state"] == bq.RUN_EXITED
        refreshed = bq.get_task(task["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.BLOCKED
        assert refreshed["blocked_reason"] == "worker_requested_review"
        notes = [
            event
            for event in bq.list_events(task["id"], db_path=db_path)
            if event["type"] == "runner_note"
        ]
        assert notes[-1]["payload"]["task_state"] == bq.BLOCKED

    def test_update_unknown_run(self, db_path: Path):
        with pytest.raises(bq.RunNotFoundError):
            bq.update_run("run_nope_0000", state=bq.RUN_EXITED, db_path=db_path)

    def test_recover_interrupted_marks_dead_pid(self, db_path: Path):
        import subprocess as sp

        task = bq.create_task("crashy", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        proc = sp.Popen(["true"])
        proc.wait()
        bq.update_run(
            run["id"], state=bq.RUN_RUNNING, pid=proc.pid, db_path=db_path
        )
        result = bq.recover_interrupted_runs(db_path=db_path)
        assert result["runs_interrupted"] == 1
        refreshed = bq.get_run(run["id"], db_path=db_path)
        assert refreshed["state"] == bq.RUN_INTERRUPTED
        events = bq.list_events(task["id"], db_path=db_path)
        assert any(e["type"] == "run_interrupted" for e in events)

    def test_recovery_does_not_interrupt_fresh_starting_run(self, db_path: Path):
        task = bq.create_task("launcher is still starting", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )

        result = bq.recover_interrupted_runs(
            db_path=db_path,
            starting_grace_seconds=30,
        )

        assert result["runs_interrupted"] == 0
        refreshed = bq.get_run(run["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.RUN_STARTING

    def test_recover_interrupted_skips_live_pid(self, db_path: Path):
        import os as _os

        task = bq.create_task("alive", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            run["id"], state=bq.RUN_RUNNING, pid=_os.getpid(), db_path=db_path
        )
        result = bq.recover_interrupted_runs(db_path=db_path)
        assert result["runs_interrupted"] == 0
        assert result["runs_unverified"] == 1

    def test_recovery_marks_reused_live_pid_interrupted(
        self, db_path: Path, monkeypatch
    ):
        import os as _os

        task = bq.create_task("pid was reused", db_path=db_path)
        claimed = self._claim(task, db_path)
        run = bq.create_run(
            task["id"],
            ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        bq.update_run(
            run["id"],
            state=bq.RUN_RUNNING,
            pid=_os.getpid(),
            process_identity="original process identity",
            db_path=db_path,
        )
        monkeypatch.setattr(
            bq,
            "capture_process_identity",
            lambda _pid: "replacement process identity",
        )

        result = bq.recover_interrupted_runs(db_path=db_path)

        assert result["run_ids"] == [run["id"]]
        refreshed = bq.get_run(run["id"], db_path=db_path)
        assert refreshed is not None
        assert refreshed["state"] == bq.RUN_INTERRUPTED
        event = [
            event
            for event in bq.list_events(task["id"], db_path=db_path)
            if event["type"] == "run_interrupted"
        ][-1]
        assert event["run_id"] == run["id"]
        assert event["payload"]["reason"] == "process_identity_mismatch"
