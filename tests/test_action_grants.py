"""Tests for the scoped grant layer around the action gate (issue #554).

The invariant under test is that a grant can only ever *widen* what the signed
tier sheet already permits for a kind that exists, and that every restriction —
deny, ask, expiry, revocation, tier escalation, spend ceiling — fails closed.
A grant that could resurrect a disabled kind, survive an escalation, or outlive
its revocation would be a permission bug, so each has its own test.
"""

import json
import time

import pytest

from gateway import action_grants, action_queue, todo_store


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    """Isolated DB shared by the queue and the grant store; real tier file."""
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(action_queue, "ACTIONS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_grants, "GRANTS_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(action_queue, "DRAFTS_DIR", tmp_path / "drafts", raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB_FILE", db_file, raising=False)
    monkeypatch.setattr(todo_store, "TODO_DB", tmp_path / "todos-legacy-absent.db", raising=False)
    action_queue.reload_registry()
    yield
    monkeypatch.undo()
    action_queue.reload_registry()


def _propose(kind, payload, **kw):
    return action_queue.propose(
        source_kind="manual",
        kind=kind,
        title=f"{kind} action",
        preview=f"will run {kind}",
        payload=payload,
        **kw,
    )


def _grant(capability, decision, **kw):
    return action_grants.create_grant(
        capability=capability,
        decision=decision,
        granted_tier=kw.pop("granted_tier", "T2"),
        reason=kw.pop("reason", "user chose this in the approval dialog"),
        **kw,
    )


# --- baseline behaviour is unchanged when no grant exists ------------------


def test_no_grants_leaves_tier_policy_exactly_as_before():
    auto = _propose("todo.create", {"content": "buy milk"})
    assert action_queue.execute(auto["id"])["status"] == "executed"

    gated = _propose("calendar.event.create", {"title": "dentist"})
    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(gated["id"])


def test_one_shot_approval_still_authorizes_without_any_grant(monkeypatch):
    monkeypatch.setattr(
        "gateway.calendar_integration.create", lambda *a, **k: True, raising=False
    )
    action = _propose("calendar.event.create", {"title": "dentist"})
    action_queue.approve(action["id"])

    assert action_queue.execute(action["id"])["status"] == "executed"


# --- standing allow ---------------------------------------------------------


def test_standing_allow_lets_a_t2_execute_without_per_action_approval(monkeypatch):
    monkeypatch.setattr(
        "gateway.calendar_integration.create", lambda *a, **k: True, raising=False
    )
    _grant("calendar.event.create", "allow", scope_type="project", scope_id="kitty")
    action = _propose(
        "calendar.event.create", {"title": "standup"}, scope_type="project", scope_id="kitty"
    )

    assert action["status"] == "proposed"
    assert action_queue.execute(action["id"])["status"] == "executed"


def test_a_grant_for_another_scope_does_not_authorize_this_one():
    _grant("calendar.event.create", "allow", scope_type="project", scope_id="kitty")
    action = _propose(
        "calendar.event.create", {"title": "standup"}, scope_type="project", scope_id="other"
    )

    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])


# --- restrictions fail closed ----------------------------------------------


def test_scoped_deny_beats_a_one_shot_approval():
    # Precedence rule 2 sits above rule 4: approving the individual proposal
    # must not defeat an explicit "never allow here".
    _grant("calendar.event.create", "deny", scope_type="site", scope_id="example.com")
    action = _propose(
        "calendar.event.create",
        {"title": "spam"},
        scope_type="site",
        scope_id="example.com",
    )
    action_queue.approve(action["id"])

    with pytest.raises(action_queue.GrantDenied):
        action_queue.execute(action["id"])


def test_scoped_deny_beats_a_global_allow():
    _grant("todo.create", "allow", granted_tier="T0")
    _grant("todo.create", "deny", granted_tier="T0", scope_type="project", scope_id="work")

    action = _propose(
        "todo.create", {"content": "x"}, scope_type="project", scope_id="work"
    )

    with pytest.raises(action_queue.GrantDenied):
        action_queue.execute(action["id"])


def test_scoped_ask_suppresses_a_broader_allow():
    _grant("todo.create", "allow", granted_tier="T0")
    _grant("todo.create", "ask", granted_tier="T0", scope_type="project", scope_id="work")

    action = _propose(
        "todo.create", {"content": "x"}, scope_type="project", scope_id="work"
    )

    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])


def test_ask_grant_still_yields_to_an_explicit_approval_of_this_proposal():
    _grant("todo.create", "ask", granted_tier="T0", scope_type="project", scope_id="work")
    action = _propose(
        "todo.create", {"content": "x"}, scope_type="project", scope_id="work"
    )
    action_queue.approve(action["id"])

    assert action_queue.execute(action["id"])["status"] == "executed"


def test_deny_and_allow_at_the_same_specificity_fail_closed():
    _grant("todo.create", "allow", granted_tier="T0", scope_type="repo", scope_id="kitty")
    _grant("todo.create", "deny", granted_tier="T0", scope_type="repo", scope_id="kitty")

    action = _propose("todo.create", {"content": "x"}, scope_type="repo", scope_id="kitty")

    with pytest.raises(action_queue.GrantDenied):
        action_queue.execute(action["id"])


# --- expiry, revocation, session binding -----------------------------------


def test_expired_grant_does_not_authorize():
    grant = _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        expires_at=time.time() + 60,
    )
    action = _propose(
        "calendar.event.create", {"title": "later"}, scope_type="project", scope_id="kitty"
    )

    decision = action_grants.evaluate(
        capability="calendar.event.create",
        tier="T2",
        status=action["status"],
        scope_type="project",
        scope_id="kitty",
        now=grant["expires_at"] + 1,
    )

    assert decision.outcome == "ask"


def test_revoked_grant_stops_authorizing_immediately():
    grant = _grant("calendar.event.create", "allow", scope_type="project", scope_id="kitty")
    action_grants.revoke_grant(grant["id"])

    action = _propose(
        "calendar.event.create", {"title": "x"}, scope_type="project", scope_id="kitty"
    )

    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])


def test_revocation_is_idempotent_and_keeps_the_original_timestamp():
    grant = _grant("todo.create", "allow", granted_tier="T0")
    first = action_grants.revoke_grant(grant["id"])
    second = action_grants.revoke_grant(grant["id"])

    assert first["revoked_at"] == second["revoked_at"]


def test_session_bound_grant_only_authorizes_its_own_session(monkeypatch):
    monkeypatch.setattr(
        "gateway.calendar_integration.create", lambda *a, **k: True, raising=False
    )
    _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        session_id="session-a",
    )

    mine = _propose(
        "calendar.event.create",
        {"title": "mine"},
        scope_type="project",
        scope_id="kitty",
        session_id="session-a",
    )
    assert action_queue.execute(mine["id"])["status"] == "executed"

    theirs = _propose(
        "calendar.event.create",
        {"title": "theirs"},
        scope_type="project",
        scope_id="kitty",
        session_id="session-b",
    )
    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(theirs["id"])


# --- a grant cannot widen what the baseline forbids -------------------------


def test_grant_cannot_resurrect_a_disabled_kind():
    # email.send is in _disabled_v1 and has no executor. A grant naming it must
    # change nothing: the queue refuses before the policy layer is consulted.
    _grant("email.send", "allow")

    with pytest.raises(action_queue.UnknownActionKind):
        _propose("email.send", {"content": "hi"})


def test_allow_grant_lapses_when_the_signed_tier_escalates(monkeypatch, tmp_path):
    _grant("todo.create", "allow", granted_tier="T0")
    action = _propose("todo.create", {"content": "x"})

    escalated = tmp_path / "tiers.json"
    escalated.write_text(
        json.dumps(
            {
                "todo.create": "T2",
                "note.draft": "T1",
                "packet.delegate": "T1",
                "calendar.event.create": "T2",
                "_disabled_v1": ["email.send"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(action_queue, "ACTION_TIERS_FILE", escalated, raising=False)
    action_queue.reload_registry()

    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])


def test_deny_grant_survives_a_tier_escalation():
    # Only permission lapses on escalation. A restriction that stopped applying
    # when a kind got *riskier* would be exactly backwards.
    _grant("todo.create", "deny", granted_tier="T0")

    decision = action_grants.evaluate(
        capability="todo.create", tier="T2", status="approved", scope_type="global"
    )

    assert decision.outcome == "deny"


# --- spend ceilings ---------------------------------------------------------


def test_budget_grant_allows_and_charges_within_its_ceiling():
    grant = _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=5.0,
    )
    decision = action_grants.evaluate(
        capability="calendar.event.create",
        tier="T2",
        status="proposed",
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=2.0,
    )
    assert decision.outcome == "allow"
    assert decision.charges_budget is True

    charged = action_grants.record_spend(grant["id"], 2.0)
    assert charged["budget_spent_usd"] == pytest.approx(2.0)


def test_budget_grant_asks_rather_than_spending_an_undeclared_cost():
    _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=5.0,
    )
    action = _propose(
        "calendar.event.create", {"title": "x"}, scope_type="project", scope_id="kitty"
    )

    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(action["id"])


def test_budget_grant_asks_once_the_ceiling_would_be_exceeded():
    grant = _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=5.0,
    )
    action_grants.record_spend(grant["id"], 4.5)

    decision = action_grants.evaluate(
        capability="calendar.event.create",
        tier="T2",
        status="proposed",
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=1.0,
    )

    assert decision.outcome == "ask"
    assert decision.basis == "budget_exhausted"


def test_budget_is_reserved_before_dispatch_not_after(monkeypatch):
    # The executor observes the reservation already taken. Charging afterwards
    # would let two actions that both cleared evaluate() run and overspend.
    grant = _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=5.0,
    )
    seen: list[float] = []

    def _spy(*args, **kwargs):
        seen.append(action_grants.get_grant(grant["id"])["budget_spent_usd"])
        return True

    monkeypatch.setattr("gateway.calendar_integration.create", _spy, raising=False)
    action = _propose(
        "calendar.event.create",
        {"title": "x"},
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=2.0,
    )

    action_queue.execute(action["id"])

    assert seen == [pytest.approx(2.0)]


def test_a_second_action_cannot_run_once_the_reservation_exhausts_the_ceiling(monkeypatch):
    monkeypatch.setattr(
        "gateway.calendar_integration.create", lambda *a, **k: True, raising=False
    )
    _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=3.0,
    )
    first = _propose(
        "calendar.event.create",
        {"title": "one"},
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=2.0,
    )
    second = _propose(
        "calendar.event.create",
        {"title": "two"},
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=2.0,
    )

    assert action_queue.execute(first["id"])["status"] == "executed"
    with pytest.raises(action_queue.TierViolation):
        action_queue.execute(second["id"])


def test_release_spend_cannot_manufacture_budget():
    grant = _grant("todo.create", "allow", granted_tier="T0", budget_limit_usd=1.0)
    action_grants.record_spend(grant["id"], 0.5)

    action_grants.release_spend(grant["id"], 0.5)
    action_grants.release_spend(grant["id"], 0.5)

    assert action_grants.get_grant(grant["id"])["budget_spent_usd"] == pytest.approx(0.0)


def test_record_spend_refuses_to_overshoot_the_ceiling():
    # The pre-dispatch check and the charge are separate steps, so two actions
    # can both pass the check. The conditioned UPDATE is what stops them from
    # together spending past the ceiling.
    grant = _grant("todo.create", "allow", granted_tier="T0", budget_limit_usd=1.0)
    action_grants.record_spend(grant["id"], 0.8)

    with pytest.raises(action_grants.GrantValidationError):
        action_grants.record_spend(grant["id"], 0.5)

    assert action_grants.get_grant(grant["id"])["budget_spent_usd"] == pytest.approx(0.8)


def test_failed_execution_does_not_consume_the_budget(monkeypatch):
    monkeypatch.setattr(
        "gateway.calendar_integration.create", lambda *a, **k: False, raising=False
    )
    grant = _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=5.0,
    )
    action = _propose(
        "calendar.event.create",
        {"title": "x"},
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=2.0,
    )

    assert action_queue.execute(action["id"])["status"] == "failed"
    assert action_grants.get_grant(grant["id"])["budget_spent_usd"] == pytest.approx(0.0)


def test_successful_execution_charges_the_authorizing_grant(monkeypatch):
    monkeypatch.setattr(
        "gateway.calendar_integration.create", lambda *a, **k: True, raising=False
    )
    grant = _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        budget_limit_usd=5.0,
    )
    action = _propose(
        "calendar.event.create",
        {"title": "x"},
        scope_type="project",
        scope_id="kitty",
        estimated_cost_usd=2.0,
    )

    assert action_queue.execute(action["id"])["status"] == "executed"
    assert action_grants.get_grant(grant["id"])["budget_spent_usd"] == pytest.approx(2.0)


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"decision": "maybe"},
        {"granted_tier": "T9"},
        {"scope_type": "galaxy", "scope_id": "x"},
        {"scope_type": "project"},  # non-global scope with no scope_id
        {"scope_type": "global", "scope_id": "kitty"},  # global takes no id
        {"expires_at": 1.0},  # already in the past
        {"budget_limit_usd": 0.0},
        {"reason": "   "},
    ],
)
def test_invalid_grants_are_refused(kwargs):
    payload = {
        "capability": "todo.create",
        "decision": "allow",
        "granted_tier": "T0",
        "reason": "because",
    }
    payload.update(kwargs)
    with pytest.raises(action_grants.GrantValidationError):
        action_grants.create_grant(**payload)


def test_only_an_allow_grant_can_carry_a_budget():
    with pytest.raises(action_grants.GrantValidationError):
        action_grants.create_grant(
            capability="todo.create",
            decision="deny",
            granted_tier="T0",
            reason="because",
            budget_limit_usd=5.0,
        )


def test_propose_rejects_a_scope_no_grant_could_ever_match():
    with pytest.raises(action_queue.ActionPayloadError):
        _propose("todo.create", {"content": "x"}, scope_type="galaxy", scope_id="x")


# --- manifest posture -------------------------------------------------------


def test_approval_posture_summarizes_without_leaking_the_reason_text():
    _grant(
        "calendar.event.create",
        "allow",
        scope_type="project",
        scope_id="kitty",
        reason="secret-sounding rationale",
    )

    posture = action_grants.approval_posture(project_id="kitty")

    assert posture["grant_count"] == 1
    summary = posture["relevant_grants"][0]
    assert summary["capability"] == "calendar.event.create"
    assert summary["scope"] == "project 'kitty'"
    assert "reason" not in summary
    assert "created_by" not in summary


def test_posture_caps_the_listed_grants_and_states_the_overflow():
    for index in range(4):
        _grant("todo.create", "allow", granted_tier="T0", reason=f"grant {index}")

    posture = action_grants.approval_posture(max_listed=2)

    assert posture["relevant_grant_count"] == 4
    assert len(posture["relevant_grants"]) == 2
    assert posture["truncated"] == 2


def test_posture_omits_the_truncation_key_when_nothing_was_dropped():
    _grant("todo.create", "allow", granted_tier="T0")

    posture = action_grants.approval_posture()

    assert "truncated" not in posture


def test_list_grants_hides_revoked_and_expired_by_default():
    live = _grant("todo.create", "allow", granted_tier="T0")
    revoked = _grant("todo.create", "allow", granted_tier="T0")
    action_grants.revoke_grant(revoked["id"])

    active_ids = {grant["id"] for grant in action_grants.list_grants()}
    all_ids = {grant["id"] for grant in action_grants.list_grants(include_inactive=True)}

    assert active_ids == {live["id"]}
    assert all_ids == {live["id"], revoked["id"]}
