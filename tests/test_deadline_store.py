"""Tests for gateway/deadline_store.py."""
from __future__ import annotations

from datetime import date

import pytest

from gateway import deadline_store, project_store
from gateway.deadline_store import DeadlineNotFound


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("gateway.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.db.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.KITTY_DB_FILE", db)
    deadline_store.init_db()
    project_store.create("benefits-admin", "admin")


def _sample(project_id: int = 2, **overrides) -> dict:
    return {
        "project_id": project_id,
        "source": "knowledge:letter.pdf",
        "source_id": "abc",
        "due_date": "2026-08-01",
        "obligation": "Submit SAID renewal",
        "amount": "$50",
        "currency": "CAD",
        "confidence": "high",
        "status": "open",
        **overrides,
    }


def test_upsert_and_get():
    d = deadline_store.upsert(_sample())
    assert d["id"] is not None
    fetched = deadline_store.get(d["id"])
    assert fetched["obligation"] == "Submit SAID renewal"
    assert fetched["confidence"] == "high"
    assert fetched["status"] == "open"


def test_upsert_updates_existing_by_dedupe_key():
    d1 = deadline_store.upsert(_sample(confidence="low"))
    d2 = deadline_store.upsert(_sample(confidence="high", amount="$75"))
    assert d1["id"] == d2["id"]
    assert d2["confidence"] == "high"
    assert d2["amount"] == "$75"


def test_needs_jacob_forces_status():
    d = deadline_store.upsert(_sample(confidence="needs_jacob"))
    assert d["status"] == "needs_jacob"


def test_list_open_ordered_by_due_date():
    deadline_store.upsert(_sample(due_date="2026-08-10", obligation="Later"))
    deadline_store.upsert(_sample(due_date="2026-07-10", obligation="Sooner"))
    rows = deadline_store.list_open()
    assert [r["obligation"] for r in rows] == ["Sooner", "Later"]


def test_close():
    d = deadline_store.upsert(_sample())
    closed = deadline_store.close(d["id"])
    assert closed["status"] == "closed"


def test_close_missing_raises():
    with pytest.raises(DeadlineNotFound):
        deadline_store.close(9999)


def test_checkpoint_due():
    today = date(2026, 7, 20)
    cases = [
        ("2026-07-27", "T-7d"),
        ("2026-07-23", "T-3d"),
        ("2026-07-21", "T-1d"),
        ("2026-07-20", "day-of"),
        ("2026-07-19", None),
        ("2026-08-20", None),
    ]
    for due, expected in cases:
        assert deadline_store.checkpoint_due(_sample(due_date=due), today) == expected


def test_checkpoint_skips_non_open():
    today = date(2026, 7, 20)
    closed = _sample(status="closed", due_date="2026-07-27")
    assert deadline_store.checkpoint_due(closed, today) is None


def test_escalation_recorded_once():
    d = deadline_store.upsert(_sample())
    deadline_store.record_escalation(d["id"], "T-7d")
    assert deadline_store.escalation_already_sent(d["id"], "T-7d")
    assert not deadline_store.escalation_already_sent(d["id"], "T-3d")


def test_list_for_project_is_scoped_open_and_bounded():
    second = project_store.create("second-project", "admin")
    deadline_store.upsert(_sample(project_id=2, due_date="2026-08-03", obligation="Later open"))
    deadline_store.upsert(_sample(project_id=2, due_date="2026-08-01", obligation="Soon open", source_id="soon"))
    deadline_store.upsert(_sample(project_id=2, due_date="2026-07-31", obligation="Needs Jacob", confidence="needs_jacob", source_id="needs"))
    closed = deadline_store.upsert(_sample(project_id=2, due_date="2026-07-30", obligation="Closed", source_id="closed"))
    deadline_store.close(closed["id"])
    deadline_store.upsert(_sample(project_id=second["id"], due_date="2026-07-29", obligation="Other project", source_id="other"))

    rows = deadline_store.list_for_project(2, limit=2)

    assert [row["obligation"] for row in rows] == ["Needs Jacob", "Soon open"]
    assert all(row["project_id"] == 2 for row in rows)
    assert all(row["status"] in {"open", "needs_jacob"} for row in rows)
