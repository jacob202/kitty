"""Tests for insight_loop — capture, return, respond lifecycle (issue #270)."""

from __future__ import annotations

import pytest

from gateway import action_queue, insight_loop, signal_store, todo_store
from gateway import db as kitty_db


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Isolated DB; real signal_store/action_queue/dispatchers run against it."""
    from gateway import idea_mine_store as ims
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(insight_loop, "INSIGHT_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB", tmp_path / "todos-legacy-absent.db", raising=False)
    monkeypatch.setattr(ims, "IDEA_MINE_DB_FILE", db_file, raising=False)
    # Reload action queue registry from the real tier file
    action_queue.reload_registry()
    # Init DB so idea_mine_items table exists
    kitty_db.migrate(db_file=db_file)
    yield
    monkeypatch.undo()
    action_queue.reload_registry()


# ── capture ──────────────────────────────────────────────────────────────────


class TestCapture:
    def test_captures_with_explicit_consent(self) -> None:
        item_id = insight_loop.capture(
            text="build the thing",
            category="task",
            explicit_consent=True,
        )
        item = insight_loop.get_insight(item_id)
        assert item is not None
        assert item["object_type"] == "insight"
        assert item["user_review"] == "approved"
        assert item["payload"]["summary"] == "build the thing"
        assert item["payload"]["category"] == "task"
        assert item["payload"]["status"] == "pending"

    def test_capture_without_consent_is_unreviewed(self) -> None:
        item_id = insight_loop.capture(
            text="inferred thought",
            category="reference",
            explicit_consent=False,
        )
        item = insight_loop.get_insight(item_id)
        assert item is not None
        assert item["user_review"] == "unreviewed"

    def test_capture_defaults_to_reference_category(self) -> None:
        item_id = insight_loop.capture(text="just a note")
        item = insight_loop.get_insight(item_id)
        assert item["payload"]["category"] == "reference"

    def test_capture_rejects_unknown_category(self) -> None:
        with pytest.raises(ValueError, match="unknown category"):
            insight_loop.capture(text="x", category="invalid_cat")

    def test_capture_requires_return_at_for_reminder(self) -> None:
        with pytest.raises(ValueError, match="return_at"):
            insight_loop.capture(text="remember this", category="reminder")

    def test_capture_accepts_return_at(self) -> None:
        item_id = insight_loop.capture(
            text="meeting at 3pm",
            category="reminder",
            return_at="2026-07-27T15:00:00",
        )
        item = insight_loop.get_insight(item_id)
        assert item["payload"]["return_at"] == "2026-07-27T15:00:00"
        assert item["payload"]["return_policy"] == "next_brief"


# ── list_due ────────────────────────────────────────────────────────────────


class TestListDue:
    def test_empty_when_no_insights(self) -> None:
        assert insight_loop.list_due() == []

    def test_excludes_unreviewed_items(self) -> None:
        insight_loop.capture(text="unreviewed thought", category="reference")
        assert insight_loop.list_due() == []

    def test_includes_approved_next_brief(self) -> None:
        insight_loop.capture(text="do this", category="task", explicit_consent=True)
        due = insight_loop.list_due()
        assert len(due) == 1

    def test_includes_explicit_time_past_due(self) -> None:
        insight_loop.capture(
            text="past reminder",
            category="reminder",
            return_at="2020-01-01T00:00:00",
            explicit_consent=True,
        )
        due = insight_loop.list_due()
        assert len(due) == 1

    def test_excludes_future_return_at(self) -> None:
        insight_loop.capture(
            text="future reminder",
            category="reminder",
            return_at="2099-12-31T23:59:59",
            return_policy="explicit_time",
            explicit_consent=True,
        )
        due = insight_loop.list_due()
        assert due == []

    def test_excludes_non_pending_status(self) -> None:
        item_id = insight_loop.capture(
            text="already acted",
            category="task",
            explicit_consent=True,
        )
        insight_loop.mark_returned(item_id)
        insight_loop.respond(item_id, "archive", archive_reason="already_handled")
        due = insight_loop.list_due()
        archived = [d for d in due if d["id"] == item_id]
        assert archived == []

    def test_excludes_suppressed_items(self) -> None:
        from gateway import idea_mine_store as ims
        item_id = insight_loop.capture(text="quiet", category="task", explicit_consent=True)
        ims.set_review(item_id, "keep_quiet")
        due = insight_loop.list_due()
        assert due == []


# ── mark_returned ────────────────────────────────────────────────────────────


class TestMarkReturned:
    def test_marks_pending_as_returned(self) -> None:
        item_id = insight_loop.capture(text="return me", category="task", explicit_consent=True)
        ok = insight_loop.mark_returned(item_id)
        assert ok is True
        item = insight_loop.get_insight(item_id)
        assert item["payload"]["status"] == "returned"
        assert item["payload"]["returned_count"] == 1

    def test_returns_false_for_missing_item(self) -> None:
        assert insight_loop.mark_returned(99999) is False

    def test_skips_non_pending_items(self) -> None:
        item_id = insight_loop.capture(text="archived", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        insight_loop.respond(item_id, "archive", archive_reason="not_useful")
        assert insight_loop.mark_returned(item_id) is False

    def test_emits_signal(self) -> None:
        item_id = insight_loop.capture(text="signal me", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        signals = signal_store.list_recent(limit=10, source="insight_loop")
        assert len(signals) >= 1
        assert signals[0]["kind"] == "insight.returned"
        assert signals[0]["payload"]["insight_id"] == item_id


# ── respond: act ─────────────────────────────────────────────────────────────


class TestRespondAct:
    def test_act_creates_action_and_updates_status(self) -> None:
        item_id = insight_loop.capture(text="buy milk", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        result = insight_loop.respond(item_id, "act")
        assert result["payload"]["status"] == "acted"
        assert result["payload"]["outcome"] == "acted"
        assert result["payload"]["action_id"] is not None

    def test_act_linked_action_is_executed(self) -> None:
        item_id = insight_loop.capture(text="buy eggs", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        result = insight_loop.respond(item_id, "act")
        action_id = result["payload"]["action_id"]
        action = action_queue.get(action_id)
        assert action is not None
        assert action["status"] == "executed"

    def test_act_emits_signal(self) -> None:
        item_id = insight_loop.capture(text="act signal", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        insight_loop.respond(item_id, "act")
        acted_signals = [
            s for s in signal_store.list_recent(limit=50)
            if s["kind"] == "insight.acted"
        ]
        assert len(acted_signals) == 1


# ── respond: snooze ──────────────────────────────────────────────────────────


class TestRespondSnooze:
    def test_snooze_updates_return_at_and_resets(self) -> None:
        item_id = insight_loop.capture(text="snooze me", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        result = insight_loop.respond(item_id, "snooze", snooze_until="2026-07-28T08:00:00")
        assert result["payload"]["status"] == "snoozed"
        assert result["payload"]["return_at"] == "2026-07-28T08:00:00"

    def test_snooze_requires_snooze_until(self) -> None:
        item_id = insight_loop.capture(text="bad snooze", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        with pytest.raises(ValueError, match="snooze_until"):
            insight_loop.respond(item_id, "snooze")


# ── respond: archive ─────────────────────────────────────────────────────────


class TestRespondArchive:
    def test_archive_closes_with_reason(self) -> None:
        item_id = insight_loop.capture(text="archive me", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        result = insight_loop.respond(item_id, "archive", archive_reason="already_handled")
        assert result["payload"]["status"] == "archived"
        assert result["payload"]["outcome"] == "already_handled"

    def test_archive_defaults_to_not_useful(self) -> None:
        item_id = insight_loop.capture(text="archive default", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        result = insight_loop.respond(item_id, "archive")
        assert result["payload"]["status"] == "archived"
        assert result["payload"]["outcome"] == "not_useful"

    def test_archive_rejects_invalid_reason(self) -> None:
        item_id = insight_loop.capture(text="bad reason", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        with pytest.raises(ValueError, match="archive_reason"):
            insight_loop.respond(item_id, "archive", archive_reason="bogus")


# ── respond: validation ──────────────────────────────────────────────────────


class TestRespondValidation:
    def test_rejects_invalid_choice(self) -> None:
        item_id = insight_loop.capture(text="bad choice", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        with pytest.raises(ValueError, match="invalid choice"):
            insight_loop.respond(item_id, "fly")

    def test_rejects_respond_on_archived(self) -> None:
        item_id = insight_loop.capture(text="done", category="task", explicit_consent=True)
        insight_loop.mark_returned(item_id)
        insight_loop.respond(item_id, "archive", archive_reason="already_handled")
        with pytest.raises(ValueError, match="cannot respond"):
            insight_loop.respond(item_id, "act")

    def test_rejects_respond_on_missing_item(self) -> None:
        with pytest.raises(LookupError, match="no insight"):
            insight_loop.respond(99999, "act")


# ── list_insights ────────────────────────────────────────────────────────────


class TestListInsights:
    def test_lists_all(self) -> None:
        insight_loop.capture(text="one", category="task", explicit_consent=True)
        insight_loop.capture(text="two", category="reference", explicit_consent=True)
        all_items = insight_loop.list_insights()
        assert len(all_items) == 2

    def test_filters_by_status(self) -> None:
        a = insight_loop.capture(text="a", category="task", explicit_consent=True)
        b = insight_loop.capture(text="b", category="task", explicit_consent=True)
        insight_loop.mark_returned(a)
        insight_loop.respond(a, "act")
        pending = insight_loop.list_insights(status="pending")
        assert len(pending) == 1
        assert pending[0]["id"] == b

    def test_respects_limit(self) -> None:
        for i in range(5):
            insight_loop.capture(text=f"item {i}", category="task", explicit_consent=True)
        assert len(insight_loop.list_insights(limit=2)) == 2


# ── get_metrics ──────────────────────────────────────────────────────────────


class TestGetMetrics:
    def test_returns_zero_for_empty(self) -> None:
        m = insight_loop.get_metrics()
        assert m["total"] == 0
        assert m["by_status"] == {}

    def test_counts_by_status_and_category(self) -> None:
        a = insight_loop.capture(text="a", category="task", explicit_consent=True)
        b = insight_loop.capture(text="b", category="task", explicit_consent=True)
        insight_loop.capture(text="c", category="reference", explicit_consent=True)
        insight_loop.mark_returned(a)
        insight_loop.respond(a, "act")
        insight_loop.mark_returned(b)
        insight_loop.respond(b, "snooze", snooze_until="2026-07-28T08:00:00")
        m = insight_loop.get_metrics()
        assert m["total"] == 3
        assert m["by_status"]["acted"] == 1
        assert m["by_status"]["snoozed"] == 1
        assert m["by_status"]["pending"] == 1
        assert m["by_category"]["task"] == 2
        assert m["by_category"]["reference"] == 1
        assert m["acted_count"] == 1
        assert m["total_returns"] == 2  # returned twice (both a and b)


# ── return_due (cron action) ─────────────────────────────────────────────────


class TestReturnDue:
    def test_sweeps_up_to_three(self) -> None:
        for i in range(5):
            insight_loop.capture(text=f"due {i}", category="task", explicit_consent=True)
        import asyncio
        asyncio.run(insight_loop.return_due())
        pending = insight_loop.list_insights(status="pending")
        returned = insight_loop.list_insights(status="returned")
        assert len(pending) == 2
        assert len(returned) == 3

    def test_is_idempotent(self) -> None:
        for i in range(3):
            insight_loop.capture(text=f"item {i}", category="task", explicit_consent=True)
        import asyncio
        asyncio.run(insight_loop.return_due())
        asyncio.run(insight_loop.return_due())
        pending = insight_loop.list_insights(status="pending")
        returned = insight_loop.list_insights(status="returned")
        assert len(pending) == 0
        assert len(returned) == 3

    def test_skips_unreviewed(self) -> None:
        for i in range(3):
            insight_loop.capture(text=f"unreviewed {i}", category="task")
        import asyncio
        asyncio.run(insight_loop.return_due())
        pending = insight_loop.list_insights(status="pending")
        returned = insight_loop.list_insights(status="returned")
        assert len(pending) == 3
        assert len(returned) == 0


# ── full loop E2E ────────────────────────────────────────────────────────────


class TestFullLoop:
    def test_complete_lifecycle(self) -> None:
        item_id = insight_loop.capture(
            text="Ship the evidence automation",
            category="task",
            explicit_consent=True,
        )
        assert item_id is not None

        due = insight_loop.list_due()
        assert any(d["id"] == item_id for d in due)

        insight_loop.mark_returned(item_id, channel="test")
        item = insight_loop.get_insight(item_id)
        assert item["payload"]["status"] == "returned"
        assert item["payload"]["returned_count"] == 1

        result = insight_loop.respond(item_id, "act")
        assert result["payload"]["status"] == "acted"
        assert result["payload"]["action_id"] is not None

        action = action_queue.get(result["payload"]["action_id"])
        assert action is not None
        assert action["status"] == "executed"

        metrics = insight_loop.get_metrics()
        assert metrics["acted_count"] == 1
        assert metrics["by_status"].get("acted") == 1

        signals = signal_store.list_recent(limit=10, source="insight_loop")
        kinds = {s["kind"] for s in signals}
        assert "insight.returned" in kinds
        assert "insight.acted" in kinds


def test_snoozed_insight_returns_after_snooze_window() -> None:
    item_id = insight_loop.capture(text="come back later", category="task", explicit_consent=True)
    insight_loop.mark_returned(item_id)
    insight_loop.respond(item_id, "snooze", snooze_until="2030-01-02T08:00:00+00:00")

    assert not any(item["id"] == item_id for item in insight_loop.list_due("2030-01-02T07:59:59+00:00"))
    assert any(item["id"] == item_id for item in insight_loop.list_due("2030-01-02T08:00:00+00:00"))

    assert insight_loop.mark_returned(item_id) is False  # real clock is before 2030
    item = insight_loop.get_insight(item_id)
    assert item is not None
    assert item["payload"]["status"] == "snoozed"


def test_elapsed_snooze_can_transition_back_to_returned(monkeypatch) -> None:
    item_id = insight_loop.capture(text="return once", category="task", explicit_consent=True)
    insight_loop.mark_returned(item_id)
    insight_loop.respond(item_id, "snooze", snooze_until="2026-01-02T08:00:00+00:00")
    monkeypatch.setattr(insight_loop, "_now_iso", lambda: "2026-01-02T08:01:00+00:00")

    due = insight_loop.list_due("2026-01-02T08:01:00+00:00")
    assert [item["id"] for item in due] == [item_id]
    assert insight_loop.mark_returned(item_id) is True
    assert insight_loop.mark_returned(item_id) is False
    item = insight_loop.get_insight(item_id)
    assert item is not None
    assert item["payload"]["status"] == "returned"
    assert item["payload"]["returned_count"] == 2

def test_snooze_offset_is_compared_as_an_instant(monkeypatch) -> None:
    item_id = insight_loop.capture(text="offset snooze", category="task", explicit_consent=True)
    insight_loop.mark_returned(item_id)
    insight_loop.respond(item_id, "snooze", snooze_until="2026-01-02T08:00:00-08:00")

    assert not any(item["id"] == item_id for item in insight_loop.list_due("2026-01-02T12:00:00+00:00"))
    assert any(item["id"] == item_id for item in insight_loop.list_due("2026-01-02T16:00:00+00:00"))
    monkeypatch.setattr(insight_loop, "_now_iso", lambda: "2026-01-02T12:00:00+00:00")
    assert insight_loop.mark_returned(item_id) is False


def test_snooze_rejects_malformed_instant_before_persistence(monkeypatch) -> None:
    import pytest

    from gateway import insight_loop

    writes = []
    monkeypatch.setattr(
        insight_loop.idea_mine_store,
        "update_payload",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="valid ISO datetime"):
        insight_loop._do_snooze(1, {}, "not-a-date")
    assert writes == []
