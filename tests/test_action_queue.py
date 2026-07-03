"""Tests for action_queue — lifecycle and tier enforcement (P3).

Tier enforcement is proven here, not by convention: an unapproved T2 must fail,
unknown and disabled kinds must fail, a kind absent from the tier file must fail
registration, and every execution must record a result.
"""

import json

import pytest

from gateway import action_queue, calendar_integration, todo_store


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Isolated DB, drafts dir, and todo store; registry from the real tier file."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "DRAFTS_DIR", tmp_path / "drafts", raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    # Point the legacy todo import at a path that does not exist so init_db()
    # never reads the real on-disk data/todos.db into the temp kitty.db.
    monkeypatch.setattr(todo_store, "TODO_DB", tmp_path / "todos-legacy-absent.db", raising=False)
    action_queue.reload_registry()
    yield
    # Some tests point ACTION_TIERS_FILE at a deliberately-broken file; restore
    # the real paths before rebuilding so the reset reads the signed tier sheet.
    monkeypatch.undo()
    action_queue.reload_registry()


def _propose(kind, payload, source_kind="manual", **kw):
    return action_queue.propose(
        source_kind=source_kind,
        kind=kind,
        title=kw.get("title", f"{kind} action"),
        preview=kw.get("preview", f"will run {kind}"),
        payload=payload,
    )


# --- tier assignments match the signed file --------------------------------


def test_signed_tiers_are_applied_on_propose():
    assert _propose("todo.create", {"content": "x"})["risk_tier"] == "T0"
    assert _propose("note.draft", {"content": "x"})["risk_tier"] == "T1"
    assert _propose("calendar.event.create", {"title": "x"})["risk_tier"] == "T2"


# --- T0: executes from proposed, records a result --------------------------


def test_t0_executes_from_proposed_and_records_result():
    action = _propose("todo.create", {"content": "buy milk"})
    assert action["status"] == "proposed"

    done = action_queue.execute(action["id"])

    assert done["status"] == "executed"
    assert "todo created" in done["result"]
    assert done["executed_at"] is not None
    assert todo_store.get()[0]["content"] == "buy milk"


# --- T1: local artifact from proposed, transmits nothing -------------------


def test_t1_note_draft_writes_local_file_from_proposed(tmp_path):
    action = _propose("note.draft", {"title": "Reply to Sam", "content": "Hi Sam"})

    done = action_queue.execute(action["id"])

    assert done["status"] == "executed"
    assert "draft written to" in done["result"]
    drafts = list(action_queue.DRAFTS_DIR.glob("*.md"))
    assert len(drafts) == 1
    assert "Hi Sam" in drafts[0].read_text(encoding="utf-8")


# --- T2: requires approval -------------------------------------------------


def test_t2_execute_without_approval_is_a_tier_violation(monkeypatch):
    monkeypatch.setattr(calendar_integration, "create", lambda *a, **k: True)
    action = _propose("calendar.event.create", {"title": "Dentist"})

    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])

    # Still proposed — nothing executed.
    assert action_queue.get(action["id"])["status"] == "proposed"


def test_t2_executes_after_explicit_approval(monkeypatch):
    calls = []
    monkeypatch.setattr(
        calendar_integration, "create", lambda title, **k: calls.append(title) or True
    )
    action = _propose("calendar.event.create", {"title": "Dentist"})

    approved = action_queue.approve(action["id"])
    assert approved["status"] == "approved"
    assert approved["decided_at"] is not None

    done = action_queue.execute(action["id"])
    assert done["status"] == "executed"
    assert calls == ["Dentist"]


# --- unknown / disabled kinds ----------------------------------------------


def test_unknown_kind_cannot_be_proposed():
    with pytest.raises(action_queue.UnknownActionKind):
        _propose("frobnicate", {"content": "x"})


@pytest.mark.parametrize(
    "kind",
    ["email.send", "email.archive", "github.push", "payments", "account.change"],
)
def test_disabled_v1_kinds_cannot_be_proposed(kind):
    with pytest.raises(action_queue.UnknownActionKind):
        _propose(kind, {"content": "x"})


# --- registry integrity vs. the tier file ----------------------------------


def test_kind_absent_from_tier_file_fails_registration(monkeypatch, tmp_path):
    partial = tmp_path / "tiers.json"
    partial.write_text(
        json.dumps({"todo.create": "T0", "note.draft": "T1", "_disabled_v1": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(action_queue, "ACTION_TIERS_FILE", partial, raising=False)

    # calendar.event.create has an executor but no tier here → build must fail.
    with pytest.raises(action_queue.ActionConfigError):
        action_queue.reload_registry()


def test_executor_listed_as_disabled_fails_registration(monkeypatch, tmp_path):
    poisoned = tmp_path / "tiers.json"
    poisoned.write_text(
        json.dumps(
            {
                "note.draft": "T1",
                "calendar.event.create": "T2",
                "_disabled_v1": ["todo.create"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(action_queue, "ACTION_TIERS_FILE", poisoned, raising=False)

    with pytest.raises(action_queue.ActionConfigError):
        action_queue.reload_registry()


# --- payload validation ----------------------------------------------------


def test_missing_required_payload_field_is_rejected_at_propose():
    with pytest.raises(action_queue.ActionPayloadError):
        _propose("todo.create", {})
    with pytest.raises(action_queue.ActionPayloadError):
        _propose("calendar.event.create", {"notes": "no title"})


# --- failed execution records the error, is terminal -----------------------


def test_failed_execution_records_result_and_is_terminal(monkeypatch):
    monkeypatch.setattr(calendar_integration, "create", lambda *a, **k: False)
    action = _propose("calendar.event.create", {"title": "Dentist"})
    action_queue.approve(action["id"])

    done = action_queue.execute(action["id"])
    assert done["status"] == "failed"
    assert "calendar create failed" in done["result"]

    # Terminal: no retry.
    with pytest.raises(action_queue.ActionStateError):
        action_queue.execute(action["id"])


# --- rejection -------------------------------------------------------------


def test_rejected_action_stays_queryable_and_cannot_execute():
    action = _propose("todo.create", {"content": "maybe"})
    rejected = action_queue.reject(action["id"])
    assert rejected["status"] == "rejected"

    assert any(a["id"] == action["id"] for a in action_queue.list_actions(status="rejected"))

    with pytest.raises(action_queue.ActionStateError):
        action_queue.execute(action["id"])


def test_only_proposed_actions_can_be_approved():
    action = _propose("todo.create", {"content": "x"})
    action_queue.execute(action["id"])  # T0 executes from proposed

    with pytest.raises(action_queue.ActionStateError):
        action_queue.approve(action["id"])


# --- listing / not found ---------------------------------------------------


def test_list_filters_by_status():
    a = _propose("todo.create", {"content": "one"})
    _propose("todo.create", {"content": "two"})
    action_queue.execute(a["id"])

    proposed = action_queue.list_actions(status="proposed")
    executed = action_queue.list_actions(status="executed")
    assert {p["kind"] for p in proposed} == {"todo.create"}
    assert len(proposed) == 1
    assert len(executed) == 1


def test_operations_on_missing_action_raise_not_found():
    for op in (action_queue.approve, action_queue.reject, action_queue.execute):
        with pytest.raises(action_queue.ActionNotFound):
            op(999999)


# --- hardening: concurrency + live-tier enforcement (Codex review) ---------


def test_execute_refuses_a_row_already_claimed():
    """A concurrent /execute that claimed the row first blocks the second."""
    action = _propose("todo.create", {"content": "x"})
    assert action_queue._claim_for_execution(action["id"], "proposed") is True

    # Row is now 'executing'; a second execute must not dispatch again.
    with pytest.raises(action_queue.ActionStateError):
        action_queue.execute(action["id"])


def test_execute_enforces_current_registry_tier_not_the_stored_one(monkeypatch, tmp_path):
    """A kind escalated in the sheet after propose must gate the queued action."""
    action = _propose("todo.create", {"content": "x"})  # stamped T0 at propose
    assert action["risk_tier"] == "T0"

    escalated = tmp_path / "tiers.json"
    escalated.write_text(
        json.dumps(
            {
                "todo.create": "T2",
                "note.draft": "T1",
                "calendar.event.create": "T2",
                "_disabled_v1": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(action_queue, "ACTION_TIERS_FILE", escalated, raising=False)
    action_queue.reload_registry()

    # Now T2 per the live sheet — auto-execution from proposed must be refused.
    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])


def test_note_draft_filenames_are_unique_for_same_title():
    a = _propose("note.draft", {"title": "Same Title", "content": "first"})
    b = _propose("note.draft", {"title": "Same Title", "content": "second"})
    action_queue.execute(a["id"])
    action_queue.execute(b["id"])

    files = list(action_queue.DRAFTS_DIR.glob("*.md"))
    assert len(files) == 2
    bodies = sorted(f.read_text(encoding="utf-8") for f in files)
    assert any("first" in b for b in bodies)
    assert any("second" in b for b in bodies)
