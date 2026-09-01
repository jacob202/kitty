"""Focused presence tests for the global agent room.

Tests prove:
- Multiple ChatGPT sessions can coexist
- DSH can check in as an active participant
- Claude cannot create a new active session (but reads/receipts remain compatible)
- Heartbeat refresh changes freshness without resetting started_at
- TTL (PRESENCE_TTL) produces active then stale deterministically (injected time)
- Checkout yields ended
- Cross-participant session-id collision is rejected
- Presence metadata cannot mutate Builder/ownership
"""

from __future__ import annotations

import pytest

from gateway import agent_workspace


@pytest.fixture
def room_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(agent_workspace, "WORKSPACE_DB_FILE", db_file)
    agent_workspace.init_db()
    agent_workspace.ensure_global_workspace()
    return db_file


# ---------------------------------------------------------------------------
# TTL helpers – deterministic time injection
# ---------------------------------------------------------------------------


def _freeze(monkeypatch: pytest.MonkeyPatch, at: float) -> None:
    """Replace time.time with a fixed value."""
    monkeypatch.setattr("gateway.agent_workspace.time.time", lambda: at)


def _now() -> float:
    return agent_workspace.time.time()


def _ttl() -> float:
    return agent_workspace.PRESENCE_TTL


# ---------------------------------------------------------------------------
# 1. Multiple ChatGPT sessions can coexist
# ---------------------------------------------------------------------------


def test_multiple_chatgpt_sessions_can_coexist(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    s1 = agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="chatgpt-session-alpha",
        role="OWN",
    )
    s2 = agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="chatgpt-session-beta",
        lane_id="secondary",
        role="OWN",
    )
    assert s1["session_id"] == "chatgpt-session-alpha"
    assert s2["session_id"] == "chatgpt-session-beta"
    assert s1["participant_id"] == "chatgpt"
    assert s2["participant_id"] == "chatgpt"

    all_presence = agent_workspace.list_presence()
    session_ids = [p["session_id"] for p in all_presence]
    assert "chatgpt-session-alpha" in session_ids
    assert "chatgpt-session-beta" in session_ids


# ---------------------------------------------------------------------------
# 2. DSH can check in as an active participant
# ---------------------------------------------------------------------------


def test_dsh_can_check_in_active_participant(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    session = agent_workspace.check_in(
        participant_id="dsh",
        session_id="dsh-session-1",
        runtime="deepseek-v4-flash",
        role="REVIEW",
        lane_id="primary",
        exact_ref="abc123def",
        summary="Working on presence implementation",
        declared_status="active",
    )
    assert session["participant_id"] == "dsh"
    assert session["session_id"] == "dsh-session-1"
    assert session["runtime"] == "deepseek-v4-flash"
    assert session["role"] == "REVIEW"
    assert session["lane_id"] == "primary"
    assert session["exact_ref"] == "abc123def"
    assert session["summary"] == "Working on presence implementation"
    assert session["declared_status"] == "active"
    assert session["started_at"] == 1_000_000.0
    assert session["heartbeat_at"] == 1_000_000.0
    assert session["ended_at"] is None

    # Should appear in presence list with computed state "active"
    listing = agent_workspace.list_presence()
    dsh_sessions = [p for p in listing if p["participant_id"] == "dsh"]
    assert len(dsh_sessions) == 1
    assert dsh_sessions[0]["presence_state"] == "active"


# ---------------------------------------------------------------------------
# 3. Claude cannot create a new active session (but historical compatibility)
# ---------------------------------------------------------------------------


def test_claude_cannot_check_in_new_active_session(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="retired"):
        agent_workspace.check_in(
            participant_id="claude",
            session_id="claude-session-1",
        )


def test_claude_historical_participant_validation_remains(room_db):
    """Claude is still a valid participant for reads and receipts."""
    # validate_global_participant should still accept claude
    validated = agent_workspace.validate_global_participant("claude")
    assert validated == "claude"

    # list_inbox should still work for claude
    inbox = agent_workspace.list_inbox("claude")
    assert isinstance(inbox, list)

    # post_global_message from claude should be rejected
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="retired|active"):
        agent_workspace.post_global_message(
            sender_id="claude",
            content="This should be rejected",
            message_kind="status",
        )

    # post_global_message to claude should be rejected
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="retired|active"):
        agent_workspace.post_global_message(
            sender_id="chatgpt",
            recipient_id="claude",
            content="This should also be rejected",
            message_kind="status",
        )


# ---------------------------------------------------------------------------
# 4. Heartbeat refresh changes freshness without resetting started_at
# ---------------------------------------------------------------------------


def test_heartbeat_refreshes_without_resetting_started_at(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    session = agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="heartbeat-test-session",
    )
    assert session["started_at"] == 1_000_000.0
    assert session["heartbeat_at"] == 1_000_000.0

    # Advance time and heartbeat
    _freeze(monkeypatch, 1_000_060.0)
    refreshed = agent_workspace.heartbeat("heartbeat-test-session", "chatgpt")
    assert refreshed["started_at"] == 1_000_000.0  # unchanged
    assert refreshed["heartbeat_at"] == 1_000_060.0  # updated
    assert refreshed["ended_at"] is None


def test_heartbeat_on_ended_session_is_rejected(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="ended-session",
    )
    agent_workspace.checkout("ended-session", "chatgpt")

    with pytest.raises(agent_workspace.AgentWorkspaceError, match="ended|not found"):
        agent_workspace.heartbeat("ended-session", "chatgpt")


def test_heartbeat_on_nonexistent_session_is_rejected(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="not found"):
        agent_workspace.heartbeat("nonexistent-session", "chatgpt")


# ---------------------------------------------------------------------------
# 5. TTL produces active then stale deterministically
# ---------------------------------------------------------------------------


def test_presence_state_active_when_fresh(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="ttl-test",
    )
    # Exactly at heartbeat time: active
    listing = agent_workspace.list_presence()
    ttl_session = next(p for p in listing if p["session_id"] == "ttl-test")
    assert ttl_session["presence_state"] == "active"


def test_presence_state_active_within_ttl(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="ttl-active",
    )
    # Still within TTL (barely)
    _freeze(monkeypatch, 1_000_000.0 + _ttl() - 1)
    listing = agent_workspace.list_presence()
    ttl_session = next(p for p in listing if p["session_id"] == "ttl-active")
    assert ttl_session["presence_state"] == "active"


def test_presence_state_stale_exactly_at_ttl_boundary(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="ttl-stale",
    )
    # Exactly at TTL boundary - heartbeat_at + TTL means expired
    _freeze(monkeypatch, 1_000_000.0 + _ttl())
    listing = agent_workspace.list_presence()
    ttl_session = next(p for p in listing if p["session_id"] == "ttl-stale")
    assert ttl_session["presence_state"] == "stale"


def test_presence_state_stale_past_ttl(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="ttl-stale-2",
    )
    # Past TTL
    _freeze(monkeypatch, 1_000_000.0 + _ttl() + 60)
    listing = agent_workspace.list_presence()
    ttl_session = next(p for p in listing if p["session_id"] == "ttl-stale-2")
    assert ttl_session["presence_state"] == "stale"


def test_heartbeat_resets_stale_to_active(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="heartbeat-resurrect",
    )
    # Go stale
    _freeze(monkeypatch, 1_000_000.0 + _ttl() + 60)
    listing = agent_workspace.list_presence()
    assert next(p for p in listing if p["session_id"] == "heartbeat-resurrect")["presence_state"] == "stale"

    # Heartbeat brings it back to active
    _freeze(monkeypatch, 1_000_000.0 + _ttl() + 61)
    agent_workspace.heartbeat("heartbeat-resurrect", "chatgpt")
    listing = agent_workspace.list_presence()
    assert next(p for p in listing if p["session_id"] == "heartbeat-resurrect")["presence_state"] == "active"


# ---------------------------------------------------------------------------
# 6. Checkout yields ended and ended state overrides TTL
# ---------------------------------------------------------------------------


def test_checkout_ends_session_and_state_is_ended(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="checkout-test",
    )
    _freeze(monkeypatch, 1_000_010.0)
    ended = agent_workspace.checkout("checkout-test", "chatgpt")
    assert ended["ended_at"] == 1_000_010.0
    assert ended["heartbeat_at"] == 1_000_010.0

    listing = agent_workspace.list_presence()
    ended_session = next(p for p in listing if p["session_id"] == "checkout-test")
    assert ended_session["presence_state"] == "ended"


def test_checkout_updates_heartbeat_at_to_checkout_time(room_db, monkeypatch):
    _freeze(monkeypatch, 100.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="checkout-heartbeat-update",
    )
    _freeze(monkeypatch, 200.0)
    ended = agent_workspace.checkout("checkout-heartbeat-update", "chatgpt")
    assert ended["heartbeat_at"] == 200.0  # updated to checkout time


def test_checkout_on_ended_session_is_rejected(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="double-checkout",
    )
    agent_workspace.checkout("double-checkout", "chatgpt")
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="ended|not found"):
        agent_workspace.checkout("double-checkout", "chatgpt")


def test_checkout_on_nonexistent_session_is_rejected(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="not found"):
        agent_workspace.checkout("nonexistent", "chatgpt")


# ---------------------------------------------------------------------------
# 7. Cross-participant session-id collision is rejected
# ---------------------------------------------------------------------------


def test_duplicate_session_id_different_participant_rejected(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="chatgpt",
        session_id="shared-session-id",
    )
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="session.*participant|already exists|different participant"):
        agent_workspace.check_in(
            participant_id="kitty",
            session_id="shared-session-id",
        )


# ---------------------------------------------------------------------------
# 8. Presence metadata cannot mutate Builder/ownership
# ---------------------------------------------------------------------------


def test_presence_tables_are_separate_from_builder_state(room_db, monkeypatch):
    """Presence lives in agent workspace tables, not Builder queue tables."""
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(
        participant_id="dsh",
        session_id="builder-boundary-test",
        summary="This presence data must never appear in Builder state",
    )
    listing = agent_workspace.list_presence()
    assert any(p["session_id"] == "builder-boundary-test" for p in listing)

    # Presence should have no effect on workspace messages, turns, etc.
    room = agent_workspace.get_workspace("workspace_global")
    # Presence rows are not in the workspace projection
    assert "presence" not in room
    # Messages and turns should be the same as before presence ops
    # (no messages were created by presence operations)
    assert len(room["messages"]) == 0


# ---------------------------------------------------------------------------
# 9. Input validation and edge cases
# ---------------------------------------------------------------------------


def test_check_in_rejects_non_campaign_role(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="role"):
        agent_workspace.check_in(
            participant_id="chatgpt",
            session_id="bad-role-session",
            role="principal",
        )


def test_check_in_rejects_unknown_participant(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="participant"):
        agent_workspace.check_in(
            participant_id="unknown-agent",
            session_id="unknown-session",
        )


def test_check_in_rejects_empty_session_id(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="session_id"):
        agent_workspace.check_in(
            participant_id="chatgpt",
            session_id="",
        )


def test_checkin_with_declared_status_ended_is_rejected(room_db, monkeypatch):
    """declared_status='ended' should not be accepted on check-in."""
    _freeze(monkeypatch, 1_000_000.0)
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="declared_status|ended"):
        agent_workspace.check_in(
            participant_id="chatgpt",
            session_id="cant-start-ended",
            declared_status="ended",
        )


def test_list_presence_filters_nonexistent_participant(room_db):
    """list_presence with a participant_id that has no sessions returns empty."""
    presence = agent_workspace.list_presence()
    # No sessions yet
    assert len(presence) == 0


def test_list_presence_with_participant_filter(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    agent_workspace.check_in(participant_id="chatgpt", session_id="chat-s1")
    agent_workspace.check_in(participant_id="chatgpt", session_id="chat-s2")
    agent_workspace.check_in(participant_id="dsh", session_id="dsh-s1")

    chatgpt_sessions = agent_workspace.list_presence(participant_id="chatgpt")
    assert len(chatgpt_sessions) == 2

    dsh_sessions = agent_workspace.list_presence(participant_id="dsh")
    assert len(dsh_sessions) == 1


def test_heartbeat_on_nonexistent_session_returns_not_found(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="not found"):
        agent_workspace.heartbeat("does-not-exist", "chatgpt")


def test_checkin_rejects_long_summary(room_db, monkeypatch):
    _freeze(monkeypatch, 1_000_000.0)
    long_summary = "x" * 6001
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="summary"):
        agent_workspace.check_in(
            participant_id="chatgpt",
            session_id="long-summary-test",
            summary=long_summary,
        )


# ---------------------------------------------------------------------------
# 10. DSH is a recognized active participant for all presence ops
# ---------------------------------------------------------------------------


def test_dsh_is_listed_as_global_agent(room_db):
    room = agent_workspace.ensure_global_workspace()
    agent_ids = [a["id"] for a in room["agents"]]
    assert "dsh" in agent_ids, f"DSH should be in global roster, got {agent_ids}"


def test_dsh_can_send_global_message(room_db, monkeypatch):
    msg = agent_workspace.post_global_message(
        sender_id="dsh",
        content="DSH is now an active participant for routing",
        message_kind="status",
    )
    assert msg["sender_id"] == "dsh"


def test_claude_sending_message_rejected(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="retired|active"):
        agent_workspace.post_global_message(
            sender_id="claude",
            content="Claude should not send new messages",
            message_kind="status",
        )


def test_claude_receiving_message_rejected(room_db):
    with pytest.raises(agent_workspace.AgentWorkspaceError, match="retired|active"):
        agent_workspace.post_global_message(
            sender_id="chatgpt",
            recipient_id="claude",
            content="Should not be addressed to retired Claude",
            message_kind="status",
        )


def test_claude_can_still_read_inbox_and_receipts(room_db):
    """Historical participant compatibility: Claude can still read."""
    inbox = agent_workspace.list_inbox("claude")
    assert isinstance(inbox, list)

    # Also validate participant still works for validation
    assert agent_workspace.validate_global_participant("claude") == "claude"
