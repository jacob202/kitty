"""Tests for gateway/deadline_sweep.py."""
from __future__ import annotations

from datetime import date

import pytest

from gateway import deadline_store, deadline_sweep, project_store


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("gateway.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.deadline_sweep.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.db.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.archivist.KNOWLEDGE_DB_PATH", tmp_path / "knowledge_db")
    try:
        from gateway.archivist import _get_collection
        _get_collection.cache_clear()
    except (ImportError, AttributeError):
        pass
    deadline_store.init_db()
    project_store.create("benefits-admin", "admin")


def _llm_for_deadlines(response: list[dict]):
    import json

    def llm_fn(prompt: str, privacy_tier: str, content_class: str | None) -> str:
        return json.dumps({"deadlines": response})

    return llm_fn


def test_sweep_reports_empty_blind_spots():
    report = deadline_sweep.sweep(now=date(2026, 7, 20))
    assert report["open"] == 0
    assert "no ingested documents" in report["blind_spots"]
    assert "no recent mail signals" in report["blind_spots"]


def test_sweep_ranks_near_high_amount_first():
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-08-20",
            "obligation": "Far cheap",
            "amount": "$5",
            "confidence": "high",
            "status": "open",
        }
    )
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-07-22",
            "obligation": "Soon expensive",
            "amount": "$500",
            "confidence": "high",
            "status": "open",
        }
    )

    report = deadline_sweep.sweep(now=date(2026, 7, 20))
    assert report["top"]["obligation"] == "Soon expensive"


def test_sweep_extracts_from_mail_signals():
    signal = {
        "source": "mail",
        "id": 1,
        "payload": {"summary": "Tuition due 2026-09-01", "message_id": "msg-1"},
    }

    def fake_list_recent(limit: int, source: str | None = None):
        assert source == "mail"
        return [signal]

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("gateway.deadline_sweep.signal_store.list_recent", fake_list_recent)

    llm = _llm_for_deadlines(
        [{"due_date": "2026-09-01", "obligation": "Pay tuition", "confidence": "medium"}]
    )
    report = deadline_sweep.sweep(now=date(2026, 7, 20), llm_fn=llm)
    assert report["open"] == 1
    monkeypatch.undo()


def test_sweep_pushes_summary():
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-07-22",
            "obligation": "Pay rent",
            "amount": "$800",
            "confidence": "high",
            "status": "open",
        }
    )

    pushes = []

    def push_fn(message: str, *, title: str, kind: str, dedupe_key: str) -> bool:
        pushes.append({"message": message, "title": title, "kind": kind})
        return True

    deadline_sweep.sweep(now=date(2026, 7, 20), push_fn=push_fn)
    assert len(pushes) == 1
    assert pushes[0]["title"] == "Urgent-thing sweep"
    assert "Pay rent" in pushes[0]["message"]
