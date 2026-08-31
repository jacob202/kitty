"""Tests for gateway/deadline_watch.py."""
from __future__ import annotations

from datetime import date

import pytest

from gateway import deadline_store, deadline_watch, project_store


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("gateway.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.deadline_watch.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.db.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.KITTY_DB_FILE", db)
    deadline_store.init_db()
    project_store.create("benefits-admin", "admin")


def _make_deadline(due_date: str) -> dict:
    return deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": due_date,
            "obligation": "Pay thing",
            "confidence": "high",
            "status": "open",
        }
    )


def test_fires_today_checkpoint():
    _make_deadline("2026-07-27")
    pushes = []

    def push_fn(message: str, *, title: str, kind: str, dedupe_key: str) -> bool:
        pushes.append({"message": message, "title": title, "kind": kind, "dedupe_key": dedupe_key})
        return True

    result = deadline_watch.check_and_push(now=date(2026, 7, 20), push_fn=push_fn)
    assert result == {"checked": 1, "due": 1, "attempted": 1, "pushed": 1, "failed": 0, "skipped": 0}
    assert pushes[0]["title"] == "Deadline T-7d"
    assert pushes[0]["kind"] == "info"


def test_skips_already_sent():
    deadline = _make_deadline("2026-07-27")
    deadline_store.record_escalation(deadline["id"], "T-7d")

    pushes = []

    def push_fn(*args, **kwargs) -> bool:
        pushes.append(kwargs)
        return True

    result = deadline_watch.check_and_push(now=date(2026, 7, 20), push_fn=push_fn)
    assert result == {"checked": 1, "due": 1, "attempted": 0, "pushed": 0, "failed": 0, "skipped": 1}
    assert pushes == []


def test_only_open_status():
    _make_deadline("2026-07-27")
    closed = _make_deadline("2026-07-21")
    deadline_store.close(closed["id"])

    pushes = []

    def push_fn(*args, **kwargs) -> bool:
        pushes.append(kwargs)
        return True

    result = deadline_watch.check_and_push(now=date(2026, 7, 20), push_fn=push_fn)
    assert result["checked"] == 1
    assert result["pushed"] == 1


def test_push_failure_counts_skipped():
    _make_deadline("2026-07-27")

    def push_fn(*args, **kwargs) -> bool:
        return False

    result = deadline_watch.check_and_push(now=date(2026, 7, 20), push_fn=push_fn)
    assert result == {"checked": 1, "due": 1, "attempted": 1, "pushed": 0, "failed": 1, "skipped": 1}


@pytest.mark.parametrize(
    ("days_out", "expected_checkpoint", "expected_kind"),
    [
        (7, "T-7d", "info"),
        (3, "T-3d", "info"),
        (1, "T-1d", "alert"),
        (0, "day-of", "alert"),
    ],
)
def test_checkpoint_kind_matches_escalation_contract(days_out, expected_checkpoint, expected_kind):
    from datetime import timedelta

    today = date(2026, 7, 20)
    _make_deadline((today + timedelta(days=days_out)).isoformat())
    pushes = []

    def push_fn(message: str, *, title: str, kind: str, dedupe_key: str) -> bool:
        pushes.append({"title": title, "kind": kind, "dedupe_key": dedupe_key})
        return True

    result = deadline_watch.check_and_push(now=today, push_fn=push_fn)

    assert result["attempted"] == 1
    assert result["pushed"] == 1
    assert pushes == [
        {
            "title": f"Deadline {expected_checkpoint}",
            "kind": expected_kind,
            "dedupe_key": f"deadline-1-{expected_checkpoint}",
        }
    ]
