"""Seeded move-in bar end-to-end (issue #161, Blocker #12).

Walks ADR-0013's truthful daily loop against seeded, isolated stores:
morning brief → project next step → deadline → capture resurfacing →
auditable action. No real network, LLM, calendar, or host filesystem
state: every store points at one tmp SQLite DB and the brief's external
seams (RSS, LiteLLM, weather/calendar/todos, journal, push) are stubbed.
Persistence/migrations are untouched — the tmp DB rides the existing
kitty_db.migrate, per the card's escalation rule.
"""

from __future__ import annotations

import json

import pytest

from gateway import (
    action_queue,
    brief,
    deadline_store,
    insight_loop,
    next_step,
    project_resume,
    project_store,
    signal_store,
    todo_store,
)
from gateway import db as kitty_db


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Point every store the daily loop touches at one isolated tmp DB."""
    from gateway import idea_mine_store as ims
    from gateway.memory_graph import GraphResult

    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(project_store, "PROJECTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(next_step, "NEXT_STEP_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(deadline_store, "DEADLINES_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(insight_loop, "INSIGHT_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB", tmp_path / "todos-legacy-absent.db", raising=False)
    monkeypatch.setattr(ims, "IDEA_MINE_DB_FILE", db_file, raising=False)
    action_queue.reload_registry()
    kitty_db.migrate(db_file=db_file)

    # next_step.generate → project_resume.resume reaches for memory + signals.
    monkeypatch.setattr(project_resume, "_run_memory_search", lambda q: GraphResult())
    monkeypatch.setattr("gateway.signal_store.list_recent", lambda limit=200: [])

    # Brief external seams: no LLM, weather/calendar/todos, journal, model
    # digest, article enrichment, or phone push. RSS is injected per-call.
    monkeypatch.setattr(brief, "_fetch_memory_snippet", lambda: "")
    monkeypatch.setattr(brief, "get_tasks_summary", lambda: "Ship the move-in bar.")
    monkeypatch.setattr(brief, "_fetch_recent_journal_text", lambda limit=3: "")
    monkeypatch.setattr(brief, "detect_research_themes", lambda limit=5, lookback_days=14: [])
    monkeypatch.setattr(brief, "get_model_digest_section", lambda limit=3: None)
    monkeypatch.setattr(brief, "_ENRICH_ARTICLES", False)
    monkeypatch.setattr(
        "gateway.llm_client.chat", lambda **kwargs: "Morning. Ship the move-in bar."
    )
    monkeypatch.setattr("gateway.context_enrichment.calendar_today_text_sync", lambda: "")
    monkeypatch.setattr("gateway.context_enrichment.weather_text_sync", lambda: "")
    monkeypatch.setattr("gateway.context_enrichment.todos_text_sync", lambda: "")
    monkeypatch.setattr("gateway.notify.is_configured", lambda: False)
    monkeypatch.setattr(brief, "_brief_cache", None, raising=False)

    yield

    monkeypatch.undo()
    action_queue.reload_registry()
    monkeypatch.setattr(brief, "_brief_cache", None, raising=False)


class _EmptyNews:
    """NewsSource seam: a morning with no headlines (not under test here)."""

    def fetch(self, limit_per_feed: int = 3) -> list:
        return []


def test_move_in_bar_daily_loop_end_to_end():
    # ── Seed: an active project with its one curated next step (P4) ──
    project = project_store.create("move-in", "code")

    # LlmFn is Callable[[str], str]; the privacy_tier/content_class params this
    # stub still demanded were retired with the D10 boundary (ADR 0022).
    def llm(prompt):
        return json.dumps(
            {
                "step": "book the freight elevator",
                "why": "move-in day needs it reserved",
                "recent_win": "lease signed",
                "delegable": False,
            }
        )

    generated = next_step.generate(project["id"], llm_fn=llm)
    assert generated["step"] == "book the freight elevator"

    # ── Seed: a real deadline (P7) ──
    deadline_store.upsert(
        {
            "project_id": project["id"],
            "source": "mail:landlord",
            "due_date": "2026-08-01",
            "obligation": "pay the damage deposit",
            "amount": 1200,
            "currency": "CAD",
            "confidence": "high",
        }
    )

    # ── Seed: a capture that must come back (IL-01) ──
    capture_id = insight_loop.capture(
        text="elevator booking confirmation number",
        category="task",
        explicit_consent=True,
    )

    # ── Morning brief composes state, next step, and deadline ──
    result = brief.generate_brief(news_source=_EmptyNews())

    steps = result.get("next_steps", [])
    assert [(s["project_id"], s["step"]) for s in steps] == [
        (project["id"], "book the freight elevator")
    ]
    deadlines = result.get("deadlines", [])
    assert [d["obligation"] for d in deadlines] == ["pay the damage deposit"]
    assert deadlines[0]["due_date"] == "2026-08-01"

    # ── The capture resurfaces in the daily loop ──
    due = insight_loop.list_due()
    assert [item["id"] for item in due] == [capture_id]
    assert insight_loop.mark_returned(capture_id, channel="brief") is True

    # ── Acting on it produces an auditable action ──
    updated = insight_loop.respond(capture_id, "act")
    payload = updated["payload"]
    assert payload["status"] == "acted"
    action_id = payload["action_id"]
    assert isinstance(action_id, int)

    # The queue row is the audit trail: kind, source, tier, lifecycle
    # timestamps, and the executor's result are all stamped on it.
    record = action_queue.get(action_id)
    assert record is not None
    assert record["source_kind"] == "insight_loop"
    assert record["source_id"] == str(capture_id)
    assert record["kind"] == "todo.create"
    assert record["status"] == "executed"
    assert record["result"].startswith("todo created")
    assert record["executed_at"] is not None

    # …and it stays queryable after the fact.
    history = action_queue.list_actions()
    assert [a["id"] for a in history] == [action_id]

    # The side effect really landed: the todo exists.
    todos = todo_store.get()
    assert any("elevator booking confirmation number" in t["content"] for t in todos)
