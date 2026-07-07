"""Tests for deadline integration in the morning brief (P7, 017)."""
from __future__ import annotations

import pytest

from gateway import brief, deadline_store, project_store


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    db = tmp_path / "kitty.db"
    monkeypatch.setattr("gateway.deadline_store.DEADLINES_DB_FILE", db)
    monkeypatch.setattr("gateway.project_store.PROJECTS_DB_FILE", db)
    monkeypatch.setattr("gateway.db.KITTY_DB_FILE", db)
    monkeypatch.setattr("gateway.paths.KITTY_DB_FILE", db)
    deadline_store.init_db()
    project_store.init_db()


def test_get_deadlines_section_orders_by_due_date():
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-08-01",
            "obligation": "Later",
            "confidence": "high",
        }
    )
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-07-15",
            "obligation": "Sooner",
            "confidence": "high",
        }
    )
    section = brief.get_deadlines_section(limit=3)
    assert [s["obligation"] for s in section] == ["Sooner", "Later"]


def test_get_deadlines_section_includes_needs_jacob_when_room():
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": "2026-08-01",
            "obligation": "Confident",
            "confidence": "high",
        }
    )
    deadline_store.upsert(
        {
            "project_id": 2,
            "source": "test",
            "due_date": None,
            "obligation": "Ambiguous",
            "confidence": "needs_jacob",
            "status": "needs_jacob",
        }
    )
    section = brief.get_deadlines_section(limit=2)
    assert len(section) == 2
    assert section[1].get("needs_jacob") is True


def test_format_brief_text_includes_deadlines():
    from gateway.brief_scheduler import _format_brief_text

    text = _format_brief_text(
        {
            "date": "2026-07-06",
            "deadlines": [
                {"due_date": "2026-07-10", "obligation": "Pay parking ticket", "amount": "$30"}
            ],
        }
    )
    assert "Pay parking ticket" in text
    assert "$30" in text
