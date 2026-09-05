"""Durable shared rooms for user and specialist-agent collaboration.

This is a collaboration layer over Kitty's existing product database. It does
not replace Builder's execution queue or create a second work authority.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Protocol

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

WORKSPACE_DB_FILE = KITTY_DB_FILE
MAX_MESSAGE_LENGTH = 12_000
MAX_CONTEXT_MESSAGES = 40
MAX_CONTEXT_CONTENT = 4_000
AGENT_TIMEOUT_SECONDS = 60

DEFAULT_AGENTS: tuple[dict[str, str], ...] = (
    {
        "id": "planner",
        "display_name": "Planner",
        "role": "planner",
        "model": "kitty-sonnet",
    },
    {
        "id": "researcher",
        "display_name": "Researcher",
        "role": "researcher",
        "model": "kitty-default",
    },
    {
        "id": "builder",
        "display_name": "Builder",
        "role": "builder",
        "model": "kitty-default",
    },
    {
        "id": "reviewer",
        "display_name": "Reviewer",
        "role": "reviewer",
        "model": "kitty-sonnet",
    },
)

GLOBAL_WORKSPACE_ID = "workspace_global"
GLOBAL_WORKSPACE_NAME = "Global Agent Room"
GLOBAL_WORKSPACE_OBJECTIVE = (
    "Shared durable coordination for Jacob, ChatGPT, Claude, Codex, Kitty, and authorized agents."
)
GLOBAL_AGENTS: tuple[dict[str, str | None], ...] = (
    {"id": "chatgpt", "display_name": "ChatGPT", "role": "external", "model": None},
    {"id": "claude", "display_name": "Claude", "role": "external", "model": None},
    {"id": "codex", "display_name": "Codex", "role": "external", "model": None},
    {"id": "kitty", "display_name": "Kitty", "role": "principal", "model": None},
    {"id": "dsh", "display_name": "DSH", "role": "principal", "model": None},
    {"id": "commandcode", "display_name": "Command Code", "role": "external", "model": None},
)
_GLOBAL_AGENT_IDS = frozenset(agent["id"] for agent in GLOBAL_AGENTS)
_GLOBAL_USER_IDS = frozenset({"jacob"})
_GLOBAL_PARTICIPANT_IDS = _GLOBAL_AGENT_IDS | _GLOBAL_USER_IDS
# Retired participants can read and have receipts recorded but cannot send new
# messages or be addressed in new posts. Claude is retired for active routing
# while remaining a valid historical participant.
_RETIRED_PARTICIPANT_IDS: frozenset[str] = frozenset({"claude"})
_ACTIVE_SENDER_IDS = _GLOBAL_PARTICIPANT_IDS - _RETIRED_PARTICIPANT_IDS
_RECEIPT_STATES = {"seen", "acknowledged"}

PRESENCE_TTL: float = 120.0  # seconds; heartbeat age determines active vs stale

_SENDER_KINDS = {"user", "agent", "system"}
_MESSAGE_KINDS = {"prompt", "plan", "handoff", "review", "result", "status"}
_TURN_STATUSES = {"running", "completed", "failed", "interrupted"}
_AGENT_SEQUENCE = ("planner", "researcher", "builder", "reviewer")

logger = logging.getLogger("kitty.agent_workspace")


class AgentWorkspaceError(RuntimeError):
    """Raised when a workspace operation cannot be completed safely."""


class AgentWorkspaceConflict(AgentWorkspaceError):
    """Raised when a room already has a live turn executor."""


class WorkspaceBackend(Protocol):
    """Model seam used by orchestration and deterministic tests."""

    def complete(self, agent_id: str, prompt: str, context: list[dict[str, Any]]) -> str:
        """Ask one named agent to produce one bounded workspace message."""


def init_db() -> None:
    kitty_db.migrate(db_file=WORKSPACE_DB_FILE)


def create_workspace(*, name: str, objective: str | None) -> dict[str, Any]:
    name = _required_text(name, "name", 200)
    if objective is not None:
        objective = _bounded_text(objective, "objective", 6_000)

    workspace_id = f"workspace_{uuid.uuid4().hex}"
    now = time.time()
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO agent_workspaces (id, name, objective, status, created_at, updated_at)
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (workspace_id, name, objective, now, now),
        )
        for agent in DEFAULT_AGENTS:
            conn.execute(
                """
                INSERT INTO agent_workspace_agents
                    (workspace_id, agent_id, display_name, role, model, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'available', ?, ?)
                """,
                (
                    workspace_id,
                    agent["id"],
                    agent["display_name"],
                    agent["role"],
                    agent["model"],
                    now,
                    now,
                ),
            )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="workspace_created",
            actor_kind="system",
            actor_id="gateway",
            metadata={"agent_ids": [agent["id"] for agent in DEFAULT_AGENTS]},
            now=now,
        )
        conn.commit()
    return get_workspace(workspace_id)


def ensure_global_workspace() -> dict[str, Any]:
    """Create the one canonical global room and roster exactly once."""
    init_db()
    now = time.time()
    created = False
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT 1 FROM agent_workspaces WHERE id = ?", (GLOBAL_WORKSPACE_ID,)
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO agent_workspaces
                    (id, name, objective, status, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (
                    GLOBAL_WORKSPACE_ID,
                    GLOBAL_WORKSPACE_NAME,
                    GLOBAL_WORKSPACE_OBJECTIVE,
                    now,
                    now,
                ),
            )
            created = True
        for agent in GLOBAL_AGENTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO agent_workspace_agents
                    (workspace_id, agent_id, display_name, role, model, status,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'available', ?, ?)
                """,
                (
                    GLOBAL_WORKSPACE_ID,
                    agent["id"],
                    agent["display_name"],
                    agent["role"],
                    agent["model"],
                    now,
                    now,
                ),
            )
        if created:
            _append_event(
                conn,
                workspace_id=GLOBAL_WORKSPACE_ID,
                event_type="workspace_created",
                actor_kind="system",
                actor_id="gateway",
                metadata={"agent_ids": [agent["id"] for agent in GLOBAL_AGENTS]},
                now=now,
            )
        conn.commit()
    return get_workspace(GLOBAL_WORKSPACE_ID)


def global_sender_kind(participant_id: str) -> str:
    participant_id = _required_text(participant_id, "participant_id", 200)
    if participant_id in _GLOBAL_USER_IDS:
        return "user"
    if participant_id in _GLOBAL_AGENT_IDS:
        return "agent"
    raise AgentWorkspaceError(f"unknown global participant {participant_id}")


def validate_global_participant(participant_id: str) -> str:
    """Accept any known participant, including retired ones (for reads/receipts)."""
    participant_id = _required_text(participant_id, "participant_id", 200)
    if participant_id not in _GLOBAL_PARTICIPANT_IDS:
        raise AgentWorkspaceError(f"unknown global participant {participant_id}")
    return participant_id


def validate_active_participant(participant_id: str) -> str:
    """Accept only active (non-retired) participants for sending/addressing."""
    participant_id = validate_global_participant(participant_id)
    if participant_id in _RETIRED_PARTICIPANT_IDS:
        raise AgentWorkspaceError(
            f"participant {participant_id} is retired and cannot be used for "
            f"active routing"
        )
    return participant_id


def post_global_message(
    *,
    sender_id: str,
    content: str,
    message_kind: str,
    recipient_id: str | None = None,
    parent_message_id: str | None = None,
) -> dict[str, Any]:
    ensure_global_workspace()
    sender_id = validate_active_participant(sender_id)
    if recipient_id is not None:
        recipient_id = validate_active_participant(recipient_id)
    return append_message(
        GLOBAL_WORKSPACE_ID,
        sender_kind=global_sender_kind(sender_id),
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content,
        message_kind=message_kind,
        parent_message_id=parent_message_id,
    )


def _global_participant_joined_at(conn: Any, participant_id: str) -> float:
    if participant_id in _GLOBAL_USER_IDS:
        row = conn.execute(
            "SELECT created_at FROM agent_workspaces WHERE id = ?",
            (GLOBAL_WORKSPACE_ID,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT created_at FROM agent_workspace_agents
            WHERE workspace_id = ? AND agent_id = ?
            """,
            (GLOBAL_WORKSPACE_ID, participant_id),
        ).fetchone()
    if row is None:
        raise AgentWorkspaceError(f"unknown global participant {participant_id}")
    return float(row["created_at"])


def _with_receipt_state(row: Any) -> dict[str, Any]:
    result = dict(row)
    if result.get("acknowledged_at") is not None:
        result["receipt_state"] = "acknowledged"
    elif result.get("seen_at") is not None:
        result["receipt_state"] = "seen"
    else:
        result["receipt_state"] = "sent"
    return result


def list_inbox(
    participant_id: str,
    *,
    unread_only: bool = False,
    direct_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    participant_id = validate_global_participant(participant_id)
    if not isinstance(unread_only, bool):
        raise AgentWorkspaceError("unread_only must be a boolean")
    if not isinstance(direct_only, bool):
        raise AgentWorkspaceError("direct_only must be a boolean")
    if isinstance(limit, bool) or limit <= 0 or limit > 500:
        raise AgentWorkspaceError("limit must be between 1 and 500")
    ensure_global_workspace()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        joined_at = _global_participant_joined_at(conn, participant_id)
        rows = conn.execute(
            """
            SELECT m.*, r.seen_at, r.acknowledged_at
            FROM agent_workspace_messages AS m
            LEFT JOIN agent_workspace_message_receipts AS r
              ON r.message_id = m.id AND r.participant_id = ?
            WHERE m.workspace_id = ?
              AND m.sender_id <> ?
              AND m.created_at >= ?
              AND (m.recipient_id = ? OR m.recipient_id IS NULL)
              AND (? = 0 OR m.recipient_id = ?)
              AND (? = 0 OR r.seen_at IS NULL)
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            (
                participant_id,
                GLOBAL_WORKSPACE_ID,
                participant_id,
                joined_at,
                participant_id,
                1 if direct_only else 0,
                participant_id,
                1 if unread_only else 0,
                limit,
            ),
        ).fetchall()
    return [_with_receipt_state(row) for row in reversed(rows)]


def record_receipt(
    message_id: str, participant_id: str, state: str
) -> dict[str, Any]:
    message_id = _required_text(message_id, "message_id", 200)
    participant_id = validate_global_participant(participant_id)
    state = _required_text(state, "state", 30)
    if state not in _RECEIPT_STATES:
        raise AgentWorkspaceError(f"state must be one of {sorted(_RECEIPT_STATES)}")
    ensure_global_workspace()
    now = time.time()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        conn.execute("BEGIN IMMEDIATE")
        message = conn.execute(
            "SELECT * FROM agent_workspace_messages WHERE id = ? AND workspace_id = ?",
            (message_id, GLOBAL_WORKSPACE_ID),
        ).fetchone()
        if message is None:
            raise AgentWorkspaceError(f"message {message_id} does not belong to global room")
        joined_at = _global_participant_joined_at(conn, participant_id)
        addressed = (
            message["sender_id"] != participant_id
            and float(message["created_at"]) >= joined_at
            and (message["recipient_id"] is None or message["recipient_id"] == participant_id)
        )
        if not addressed:
            raise AgentWorkspaceError(
                f"message {message_id} is not addressed to participant {participant_id}"
            )
        if state == "seen":
            conn.execute(
                """
                INSERT INTO agent_workspace_message_receipts
                    (message_id, participant_id, seen_at, acknowledged_at)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(message_id, participant_id) DO UPDATE SET
                    seen_at = COALESCE(agent_workspace_message_receipts.seen_at, excluded.seen_at)
                """,
                (message_id, participant_id, now),
            )
        else:
            conn.execute(
                """
                INSERT INTO agent_workspace_message_receipts
                    (message_id, participant_id, seen_at, acknowledged_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id, participant_id) DO UPDATE SET
                    seen_at = COALESCE(agent_workspace_message_receipts.seen_at, excluded.seen_at),
                    acknowledged_at = COALESCE(
                        agent_workspace_message_receipts.acknowledged_at, excluded.acknowledged_at
                    )
                """,
                (message_id, participant_id, now, now),
            )
        conn.commit()
        row = conn.execute(
            """
            SELECT message_id, participant_id, seen_at, acknowledged_at
            FROM agent_workspace_message_receipts
            WHERE message_id = ? AND participant_id = ?
            """,
            (message_id, participant_id),
        ).fetchone()
    assert row is not None
    return _with_receipt_state(row)


def list_thread(message_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    message_id = _required_text(message_id, "message_id", 200)
    if isinstance(limit, bool) or limit <= 0 or limit > 500:
        raise AgentWorkspaceError("limit must be between 1 and 500")
    ensure_global_workspace()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        current = conn.execute(
            "SELECT * FROM agent_workspace_messages WHERE id = ? AND workspace_id = ?",
            (message_id, GLOBAL_WORKSPACE_ID),
        ).fetchone()
        if current is None:
            raise AgentWorkspaceError(f"message {message_id} does not belong to global room")
        visited: set[str] = set()
        while current["parent_message_id"] is not None:
            current_id = str(current["id"])
            if current_id in visited:
                raise AgentWorkspaceError(f"message {message_id} has a cyclic parent chain")
            visited.add(current_id)
            parent_id = str(current["parent_message_id"])
            current = conn.execute(
                "SELECT * FROM agent_workspace_messages WHERE id = ? AND workspace_id = ?",
                (parent_id, GLOBAL_WORKSPACE_ID),
            ).fetchone()
            if current is None:
                raise AgentWorkspaceError(
                    f"parent message {parent_id} does not belong to global room"
                )
        root_id = str(current["id"])
        rows = conn.execute(
            """
            WITH RECURSIVE thread_ids(id) AS (
                SELECT ?
                UNION ALL
                SELECT m.id
                FROM agent_workspace_messages AS m
                JOIN thread_ids AS t ON m.parent_message_id = t.id
                WHERE m.workspace_id = ?
            )
            SELECT m.*
            FROM agent_workspace_messages AS m
            JOIN thread_ids AS t ON t.id = m.id
            ORDER BY m.created_at ASC, m.id ASC
            LIMIT ?
            """,
            (root_id, GLOBAL_WORKSPACE_ID, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_workspace(workspace_id: str) -> dict[str, Any]:
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        # Explicit BEGIN so every read below sees one snapshot; without it each
        # SELECT is its own autocommit read and a concurrent writer (e.g. the
        # turn executor committing its final message) can be interleaved.
        conn.execute("BEGIN")
        try:
            workspace = conn.execute(
                "SELECT * FROM agent_workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
            if workspace is None:
                raise AgentWorkspaceError(f"workspace {workspace_id} does not exist")
            agents = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM agent_workspace_agents
                    WHERE workspace_id = ?
                    ORDER BY rowid
                    """,
                    (workspace_id,),
                ).fetchall()
            ]
            messages = _list_messages(conn, workspace_id, limit=200)
            events = _list_events(conn, workspace_id, limit=500)
            turns = _list_turns(conn, workspace_id, limit=100)
        finally:
            conn.commit()
    result = dict(workspace)
    projected_agents = [{**agent, "id": agent.pop("agent_id")} for agent in agents]
    if workspace_id == GLOBAL_WORKSPACE_ID:
        # The legacy schema calls roster membership "available", but external
        # participants may be offline or quota-blocked. Expose membership, not
        # fabricated presence, on the canonical global-room projection.
        projected_agents = [{**agent, "status": "registered"} for agent in projected_agents]
    result["agents"] = projected_agents
    result["messages"] = messages
    result["events"] = events
    result["turns"] = turns
    return result


def append_message(
    workspace_id: str,
    *,
    sender_kind: str,
    sender_id: str,
    content: str,
    message_kind: str,
    recipient_id: str | None = None,
    parent_message_id: str | None = None,
    require_turn_running: str | None = None,
) -> dict[str, Any]:
    """Append a message.

    ``require_turn_running``, when set to a turn id, fences the write: the
    insert only happens if that turn is still ``running`` at commit time, so
    a turn marked ``interrupted`` mid-flight (e.g. by a Gateway restart) can't
    have a late agent message land on top of it.
    """
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    sender_kind = _required_text(sender_kind, "sender_kind", 20)
    if sender_kind not in _SENDER_KINDS:
        raise AgentWorkspaceError(f"sender_kind must be one of {sorted(_SENDER_KINDS)}")
    sender_id = _required_text(sender_id, "sender_id", 200)
    content = _bounded_text(content, "content", MAX_MESSAGE_LENGTH)
    message_kind = _required_text(message_kind, "message_kind", 20)
    if message_kind not in _MESSAGE_KINDS:
        raise AgentWorkspaceError(f"message_kind must be one of {sorted(_MESSAGE_KINDS)}")
    if recipient_id is not None:
        recipient_id = _required_text(recipient_id, "recipient_id", 200)
    if parent_message_id is not None:
        parent_message_id = _required_text(parent_message_id, "parent_message_id", 200)

    message_id = f"message_{uuid.uuid4().hex}"
    now = time.time()
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        if require_turn_running is not None:
            # Take the write lock before checking, so a concurrent writer
            # (e.g. interrupt_running_turns) can't flip the turn's status
            # between our check and the insert below.
            conn.execute("BEGIN IMMEDIATE")
        _require_workspace(conn, workspace_id)
        if require_turn_running is not None:
            turn = conn.execute(
                "SELECT status FROM agent_workspace_turns WHERE id = ? AND workspace_id = ?",
                (require_turn_running, workspace_id),
            ).fetchone()
            if turn is None or turn["status"] != "running":
                raise AgentWorkspaceError(
                    f"turn {require_turn_running} is no longer running"
                )
        parent = None
        if parent_message_id is not None:
            parent = conn.execute(
                """
                SELECT recipient_id FROM agent_workspace_messages
                WHERE id = ? AND workspace_id = ?
                """,
                (parent_message_id, workspace_id),
            ).fetchone()
            if parent is None:
                raise AgentWorkspaceError(
                    f"parent message {parent_message_id} does not belong to workspace {workspace_id}"
                )
        conn.execute(
            """
            INSERT INTO agent_workspace_messages
                (id, workspace_id, parent_message_id, sender_kind, sender_id,
                 recipient_id, message_kind, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                workspace_id,
                parent_message_id,
                sender_kind,
                sender_id,
                recipient_id,
                message_kind,
                content,
                now,
            ),
        )
        if (
            workspace_id == GLOBAL_WORKSPACE_ID
            and parent is not None
            and parent["recipient_id"] == sender_id
        ):
            conn.execute(
                """
                INSERT INTO agent_workspace_message_receipts
                    (message_id, participant_id, seen_at, acknowledged_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id, participant_id) DO UPDATE SET
                    seen_at = COALESCE(agent_workspace_message_receipts.seen_at, excluded.seen_at),
                    acknowledged_at = COALESCE(
                        agent_workspace_message_receipts.acknowledged_at, excluded.acknowledged_at
                    )
                """,
                (parent_message_id, sender_id, now, now),
            )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="message_created",
            actor_kind=sender_kind,
            actor_id=sender_id,
            message_id=message_id,
            metadata={
                "message_kind": message_kind,
                "recipient_id": recipient_id,
            },
            now=now,
        )
        conn.execute(
            "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
            (now, workspace_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_workspace_messages WHERE id = ?", (message_id,)
        ).fetchone()
    assert row is not None
    return dict(row)


def _persist_agent_output(
    workspace_id: str,
    turn_id: str,
    *,
    agent_id: str,
    recipient_id: str | None,
    content: str,
    message_kind: str,
    parent_message_id: str,
    final_step: bool,
) -> dict[str, Any]:
    """Commit an accepted agent output and its turn transition atomically."""
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    turn_id = _required_text(turn_id, "turn_id", 200)
    agent_id = _required_text(agent_id, "agent_id", 200)
    if agent_id not in _AGENT_SEQUENCE:
        raise AgentWorkspaceError(f"unknown agent {agent_id}")
    if recipient_id is not None:
        recipient_id = _required_text(recipient_id, "recipient_id", 200)
    content = _bounded_text(content, "content", MAX_MESSAGE_LENGTH)
    message_kind = _required_text(message_kind, "message_kind", 20)
    if message_kind not in _MESSAGE_KINDS:
        raise AgentWorkspaceError(f"message_kind must be one of {sorted(_MESSAGE_KINDS)}")
    parent_message_id = _required_text(parent_message_id, "parent_message_id", 200)

    message_id = f"message_{uuid.uuid4().hex}"
    now = time.time()
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        # Serialize the status check, durable output, completion event, and the
        # active/terminal turn transition. Startup recovery can therefore see
        # either the whole completed step or none of it, never a contradiction.
        conn.execute("BEGIN IMMEDIATE")
        _require_workspace(conn, workspace_id)
        turn = conn.execute(
            """
            SELECT status, active_agent_id
            FROM agent_workspace_turns
            WHERE id = ? AND workspace_id = ?
            """,
            (turn_id, workspace_id),
        ).fetchone()
        if (
            turn is None
            or turn["status"] != "running"
            or turn["active_agent_id"] != agent_id
        ):
            raise AgentWorkspaceError(
                f"turn {turn_id} is no longer running for agent {agent_id}"
            )
        parent = conn.execute(
            """
            SELECT 1 FROM agent_workspace_messages
            WHERE id = ? AND workspace_id = ?
            """,
            (parent_message_id, workspace_id),
        ).fetchone()
        if parent is None:
            raise AgentWorkspaceError(
                f"parent message {parent_message_id} does not belong to workspace {workspace_id}"
            )

        conn.execute(
            """
            INSERT INTO agent_workspace_messages
                (id, workspace_id, parent_message_id, sender_kind, sender_id,
                 recipient_id, message_kind, content, created_at)
            VALUES (?, ?, ?, 'agent', ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                workspace_id,
                parent_message_id,
                agent_id,
                recipient_id,
                message_kind,
                content,
                now,
            ),
        )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="message_created",
            actor_kind="agent",
            actor_id=agent_id,
            message_id=message_id,
            metadata={"message_kind": message_kind, "recipient_id": recipient_id},
            now=now,
        )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="agent_completed",
            actor_kind="agent",
            actor_id=agent_id,
            message_id=message_id,
            metadata={"turn_id": turn_id},
            now=now,
        )

        if final_step:
            updated = conn.execute(
                """
                UPDATE agent_workspace_turns
                SET status = 'completed', active_agent_id = NULL, finished_at = ?
                WHERE id = ? AND workspace_id = ? AND status = 'running'
                  AND active_agent_id = ?
                """,
                (now, turn_id, workspace_id, agent_id),
            ).rowcount
            if updated != 1:
                raise AgentWorkspaceError(f"turn {turn_id} is no longer running")
            _append_event(
                conn,
                workspace_id=workspace_id,
                event_type="turn_completed",
                actor_kind="system",
                actor_id="gateway",
                metadata={"agent_sequence": list(_AGENT_SEQUENCE), "turn_id": turn_id},
                now=now,
            )
        else:
            updated = conn.execute(
                """
                UPDATE agent_workspace_turns
                SET active_agent_id = NULL
                WHERE id = ? AND workspace_id = ? AND status = 'running'
                  AND active_agent_id = ?
                """,
                (turn_id, workspace_id, agent_id),
            ).rowcount
            if updated != 1:
                raise AgentWorkspaceError(f"turn {turn_id} is no longer running")

        conn.execute(
            "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
            (now, workspace_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_workspace_messages WHERE id = ?", (message_id,)
        ).fetchone()
    assert row is not None
    return dict(row)


def list_messages(workspace_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    if isinstance(limit, bool) or limit <= 0 or limit > 500:
        raise AgentWorkspaceError("limit must be between 1 and 500")
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        _require_workspace(conn, workspace_id)
        return _list_messages(conn, workspace_id, limit=limit)


def _list_messages(conn: Any, workspace_id: str, *, limit: int) -> list[dict[str, Any]]:
    # Bounded callers (e.g. _model_context) need the newest window, not the
    # oldest: select DESC, then restore chronological order before returning.
    rows = conn.execute(
        """
        SELECT * FROM agent_workspace_messages
        WHERE workspace_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def list_events(workspace_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    if isinstance(limit, bool) or limit <= 0 or limit > 1_000:
        raise AgentWorkspaceError("limit must be between 1 and 1000")
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        _require_workspace(conn, workspace_id)
        return _list_events(conn, workspace_id, limit=limit)


def _list_events(conn: Any, workspace_id: str, *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT rowid AS sequence, * FROM agent_workspace_events
        WHERE workspace_id = ?
        ORDER BY rowid DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    events = []
    for row in reversed(rows):
        event = dict(row)
        event["metadata"] = json.loads(event.pop("metadata_json"))
        events.append(event)
    return events


def list_turns(workspace_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    if isinstance(limit, bool) or limit <= 0 or limit > 500:
        raise AgentWorkspaceError("limit must be between 1 and 500")
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        _require_workspace(conn, workspace_id)
        return _list_turns(conn, workspace_id, limit=limit)


def _list_turns(conn: Any, workspace_id: str, *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM agent_workspace_turns
        WHERE workspace_id = ?
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_turn(workspace_id: str, turn_id: str) -> dict[str, Any]:
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    turn_id = _required_text(turn_id, "turn_id", 200)
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        _require_workspace(conn, workspace_id)
        turn = conn.execute(
            "SELECT * FROM agent_workspace_turns WHERE id = ? AND workspace_id = ?",
            (turn_id, workspace_id),
        ).fetchone()
    if turn is None:
        raise AgentWorkspaceError(f"turn {turn_id} does not belong to workspace {workspace_id}")
    return dict(turn)


def start_turn(
    workspace_id: str,
    user_text: str,
    *,
    user_id: str = "jacob",
) -> dict[str, Any]:
    """Persist a user request and its running room turn before model work begins."""
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    user_text = _bounded_text(user_text, "message", MAX_MESSAGE_LENGTH)
    user_id = _required_text(user_id, "user_id", 200)
    turn_id = f"turn_{uuid.uuid4().hex}"
    user_message_id = f"message_{uuid.uuid4().hex}"
    now = time.time()
    init_db()
    try:
        with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
            # The partial unique index is the durable authority; this write lock
            # also makes the preflight check deterministic for simultaneous tabs.
            conn.execute("BEGIN IMMEDIATE")
            _require_workspace(conn, workspace_id)
            active = conn.execute(
                "SELECT id FROM agent_workspace_turns WHERE workspace_id = ? AND status = 'running'",
                (workspace_id,),
            ).fetchone()
            if active is not None:
                raise AgentWorkspaceConflict(
                    f"workspace {workspace_id} already has running turn {active['id']}"
                )
            conn.execute(
                """
                INSERT INTO agent_workspace_messages
                    (id, workspace_id, parent_message_id, sender_kind, sender_id,
                     recipient_id, message_kind, content, created_at)
                VALUES (?, ?, NULL, 'user', ?, NULL, 'prompt', ?, ?)
                """,
                (user_message_id, workspace_id, user_id, user_text, now),
            )
            _append_event(
                conn,
                workspace_id=workspace_id,
                event_type="message_created",
                actor_kind="user",
                actor_id=user_id,
                message_id=user_message_id,
                metadata={"message_kind": "prompt", "recipient_id": None, "turn_id": turn_id},
                now=now,
            )
            conn.execute(
                """
                INSERT INTO agent_workspace_turns
                    (id, workspace_id, user_message_id, status, active_agent_id,
                     error_type, error_message, started_at, finished_at)
                VALUES (?, ?, ?, 'running', NULL, NULL, NULL, ?, NULL)
                """,
                (turn_id, workspace_id, user_message_id, now),
            )
            _append_event(
                conn,
                workspace_id=workspace_id,
                event_type="turn_started",
                actor_kind="user",
                actor_id=user_id,
                message_id=user_message_id,
                metadata={"agent_sequence": list(_AGENT_SEQUENCE), "turn_id": turn_id},
                now=now,
            )
            conn.execute(
                "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
                (now, workspace_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        if "agent_workspace_turns.workspace_id" in str(exc):
            raise AgentWorkspaceConflict(
                f"workspace {workspace_id} already has a running turn"
            ) from exc
        raise
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise AgentWorkspaceConflict(
                f"workspace {workspace_id} is busy starting another turn; retry shortly"
            ) from exc
        raise
    return get_turn(workspace_id, turn_id)


def interrupt_running_turns(
    *,
    reason: str = "Gateway restarted before the room executor could finish.",
) -> int:
    """Mark running turns interrupted when no executor survives a Gateway restart."""
    detail = _bounded_text(reason, "reason", 1_000)
    now = time.time()
    init_db()
    recovered = 0
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        turns = conn.execute(
            """
            SELECT id, workspace_id, user_message_id, active_agent_id
            FROM agent_workspace_turns
            WHERE status = 'running'
            ORDER BY started_at, id
            """
        ).fetchall()
        for turn in turns:
            turn_id = turn["id"]
            workspace_id = turn["workspace_id"]
            active_agent_id = turn["active_agent_id"]
            parent = conn.execute(
                """
                SELECT id FROM agent_workspace_messages
                WHERE workspace_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()
            parent_message_id = parent["id"] if parent is not None else turn["user_message_id"]
            failure_message_id = f"message_{uuid.uuid4().hex}"
            updated = conn.execute(
                """
                UPDATE agent_workspace_turns
                SET status = 'interrupted', active_agent_id = NULL,
                    error_type = 'InterruptedError', error_message = ?, finished_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (detail, now, turn_id),
            ).rowcount
            # The executor may have completed after the snapshot above. Only the
            # transition winner may write the corresponding interruption record.
            if updated != 1:
                continue
            recovered += 1
            _append_event(
                conn,
                workspace_id=workspace_id,
                event_type="agent_interrupted",
                actor_kind="agent" if active_agent_id is not None else "system",
                actor_id=active_agent_id or "gateway",
                metadata={"turn_id": turn_id, "reason": detail},
                now=now,
            )
            conn.execute(
                """
                INSERT INTO agent_workspace_messages
                    (id, workspace_id, parent_message_id, sender_kind, sender_id,
                     recipient_id, message_kind, content, created_at)
                VALUES (?, ?, ?, 'system', 'gateway', 'jacob', 'status', ?, ?)
                """,
                (
                    failure_message_id,
                    workspace_id,
                    parent_message_id,
                    (
                        f"Incomplete: {active_agent_id or 'the room'} was interrupted before it "
                        f"could finish. InterruptedError: {detail}"
                    ),
                    now,
                ),
            )
            _append_event(
                conn,
                workspace_id=workspace_id,
                event_type="message_created",
                actor_kind="system",
                actor_id="gateway",
                message_id=failure_message_id,
                metadata={"message_kind": "status", "recipient_id": "jacob", "turn_id": turn_id},
                now=now,
            )
            _append_event(
                conn,
                workspace_id=workspace_id,
                event_type="turn_interrupted",
                actor_kind="system",
                actor_id="gateway",
                message_id=failure_message_id,
                metadata={"turn_id": turn_id, "reason": detail},
                now=now,
            )
            conn.execute(
                "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
                (now, workspace_id),
            )
        conn.commit()
    return recovered


def run_turn(
    workspace_id: str,
    user_text: str,
    *,
    backend: WorkspaceBackend | None = None,
    user_id: str = "jacob",
) -> dict[str, Any]:
    """Synchronously execute one durable, proposal-only room turn."""
    turn = start_turn(workspace_id, user_text, user_id=user_id)
    return run_persisted_turn(workspace_id, turn["id"], backend=backend)


def run_persisted_turn(
    workspace_id: str,
    turn_id: str,
    *,
    backend: WorkspaceBackend | None = None,
) -> dict[str, Any]:
    """Execute an already-durable running turn; partial work remains visible on failure."""
    turn = get_turn(workspace_id, turn_id)
    if turn["status"] != "running":
        raise AgentWorkspaceError(f"turn {turn_id} is {turn['status']}, not running")
    parent_message_id = turn["user_message_id"]
    active_agent_id: str | None = None
    outputs: dict[str, str] = {}
    try:
        user_message = _get_message(workspace_id, turn["user_message_id"])
        backend = backend or _default_backend()
        parent_message_id = user_message["id"]
        for agent_id, recipient_id, message_kind, prompt in _turn_steps(
            user_message["content"], outputs
        ):
            active_agent_id = agent_id
            _set_turn_active_agent(workspace_id, turn_id, agent_id)
            _record_event(
                workspace_id,
                "agent_started",
                actor_kind="agent",
                actor_id=agent_id,
                metadata={"turn_id": turn_id},
            )
            output = _complete(backend, agent_id, prompt, _model_context(workspace_id))
            message = _persist_agent_output(
                workspace_id,
                turn_id,
                agent_id=agent_id,
                recipient_id=recipient_id,
                content=output,
                message_kind=message_kind,
                parent_message_id=parent_message_id,
                final_step=agent_id == _AGENT_SEQUENCE[-1],
            )
            outputs[agent_id] = output
            parent_message_id = message["id"]
    except Exception as exc:
        logger.exception("shared agent turn %s failed at %s", turn_id, active_agent_id)
        _record_turn_failure(
            workspace_id,
            turn_id,
            active_agent_id=active_agent_id,
            parent_message_id=parent_message_id,
            exc=exc,
        )
    return _turn_result(workspace_id, turn_id)


def _turn_steps(user_text: str, outputs: dict[str, str]):
    yield (
        "planner",
        "researcher",
        "plan",
        (
            f"User request:\n{user_text}\n\n"
            "Produce a bounded plan for the room. Identify the desired outcome, "
            "unknowns, acceptance evidence, and the next specialist handoff. "
            "Do not claim that any code or external action has happened."
        ),
    )
    yield (
        "researcher",
        "builder",
        "handoff",
        (
            "Review the Planner's handoff below. Return relevant evidence, risks, "
            "and concrete information the Builder needs. Stay read-only.\n\n"
            f"Planner handoff:\n{outputs['planner']}"
        ),
    )
    yield (
        "builder",
        "reviewer",
        "handoff",
        (
            "Review the Planner and Researcher handoffs. Produce a proposal for the "
            "existing KittyBuilder authority path, including any missing acceptance "
            "evidence. This room cannot submit a Mission, create a queue task, run a "
            "worker, modify files, or claim execution.\n\n"
            f"Planner:\n{outputs['planner']}\n\nResearcher:\n{outputs['researcher']}"
        ),
    )
    yield (
        "reviewer",
        "jacob",
        "review",
        (
            "Review the Planner, Researcher, and Builder proposal. Return a concise "
            "verdict, remaining blockers, and one recommended next action for Jacob. "
            "Treat the Builder output as a proposal only; do not claim Builder "
            "execution or completion.\n\n"
            f"Planner:\n{outputs['planner']}\n\n"
            f"Researcher:\n{outputs['researcher']}\n\n"
            f"Builder proposal:\n{outputs['builder']}"
        ),
    )


def _get_message(workspace_id: str, message_id: str) -> dict[str, Any]:
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        message = conn.execute(
            "SELECT * FROM agent_workspace_messages WHERE id = ? AND workspace_id = ?",
            (message_id, workspace_id),
        ).fetchone()
    if message is None:
        raise AgentWorkspaceError(
            f"message {message_id} does not belong to workspace {workspace_id}"
        )
    return dict(message)


def _set_turn_active_agent(workspace_id: str, turn_id: str, agent_id: str) -> None:
    now = time.time()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        updated = conn.execute(
            """
            UPDATE agent_workspace_turns
            SET active_agent_id = ?
            WHERE id = ? AND workspace_id = ? AND status = 'running'
            """,
            (agent_id, turn_id, workspace_id),
        ).rowcount
        if updated != 1:
            raise AgentWorkspaceError(f"turn {turn_id} is no longer running")
        conn.execute(
            "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
            (now, workspace_id),
        )
        conn.commit()


def _finish_turn(workspace_id: str, turn_id: str, *, status: str) -> None:
    if status not in _TURN_STATUSES - {"running"}:
        raise AgentWorkspaceError(f"invalid terminal turn status {status!r}")
    now = time.time()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        updated = conn.execute(
            """
            UPDATE agent_workspace_turns
            SET status = ?, active_agent_id = NULL, finished_at = ?
            WHERE id = ? AND workspace_id = ? AND status = 'running'
            """,
            (status, now, turn_id, workspace_id),
        ).rowcount
        if updated != 1:
            raise AgentWorkspaceError(f"turn {turn_id} is no longer running")
        conn.execute(
            "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
            (now, workspace_id),
        )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="turn_completed",
            actor_kind="system",
            actor_id="gateway",
            metadata={"agent_sequence": list(_AGENT_SEQUENCE), "turn_id": turn_id},
            now=now,
        )
        conn.commit()


def _record_turn_failure(
    workspace_id: str,
    turn_id: str,
    *,
    active_agent_id: str | None,
    parent_message_id: str,
    exc: Exception,
) -> None:
    error_type = type(exc).__name__
    detail = _bounded_failure_detail(exc)
    operator_detail = _bounded_failure_detail(exc, user_facing=False)
    now = time.time()
    failure_message_id = f"message_{uuid.uuid4().hex}"
    failure_content = f"Incomplete: {active_agent_id or 'the room'} could not finish. {detail}"
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        updated = conn.execute(
            """
            UPDATE agent_workspace_turns
            SET status = 'failed', active_agent_id = NULL, error_type = ?,
                error_message = ?, finished_at = ?
            WHERE id = ? AND workspace_id = ? AND status = 'running'
            """,
            (error_type, detail, now, turn_id, workspace_id),
        ).rowcount
        if updated != 1:
            # Someone else (e.g. interrupt_running_turns after a Gateway
            # restart) already moved this turn to a terminal state and wrote
            # its own record — this failure is stale, not a new one to report.
            conn.rollback()
            logger.info(
                "turn %s already left running before failure could be recorded; skipping",
                turn_id,
            )
            return
        conn.execute(
            "UPDATE agent_workspaces SET updated_at = ? WHERE id = ?",
            (now, workspace_id),
        )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="agent_failed",
            actor_kind="agent" if active_agent_id is not None else "system",
            actor_id=active_agent_id or "gateway",
            metadata={
                "turn_id": turn_id,
                "error_type": error_type,
                "error_message": operator_detail,
            },
            now=now,
        )
        conn.execute(
            """
            INSERT INTO agent_workspace_messages
                (id, workspace_id, parent_message_id, sender_kind, sender_id,
                 recipient_id, message_kind, content, created_at)
            VALUES (?, ?, ?, 'system', 'gateway', 'jacob', 'status', ?, ?)
            """,
            (failure_message_id, workspace_id, parent_message_id, failure_content, now),
        )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="message_created",
            actor_kind="system",
            actor_id="gateway",
            message_id=failure_message_id,
            metadata={"message_kind": "status", "recipient_id": "jacob", "turn_id": turn_id},
            now=now,
        )
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type="turn_failed",
            actor_kind="system",
            actor_id="gateway",
            message_id=failure_message_id,
            metadata={
                "turn_id": turn_id,
                "error_type": error_type,
                "error_message": operator_detail,
            },
            now=now,
        )
        conn.commit()


def _bounded_failure_detail(exc: Exception, *, user_facing: bool = True) -> str:
    """Bounded failure text; plain language for the room, raw for the event log.

    A dead provider chain stringifies as six provider diagnostics. Jacob reads
    the room message, so it gets the one-action version while the durable event
    keeps the raw list for whoever debugs the stack.
    """
    from gateway.llm_client import ProviderChainExhausted

    if user_facing and isinstance(exc, ProviderChainExhausted):
        detail = exc.user_message
    else:
        detail = str(exc).strip() or "no error detail was provided"
    return detail[:1_000]


def _turn_result(workspace_id: str, turn_id: str) -> dict[str, Any]:
    turn = get_turn(workspace_id, turn_id)
    return {
        "status": turn["status"],
        "workspace_id": workspace_id,
        "turn": turn,
        "messages": list_messages(workspace_id),
        "events": list_events(workspace_id),
    }


def _default_backend() -> WorkspaceBackend:
    from gateway.llm_client import call_llm

    class LlmBackend:
        def complete(self, agent_id: str, prompt: str, context: list[dict[str, Any]]) -> str:
            agent = next((item for item in DEFAULT_AGENTS if item["id"] == agent_id), None)
            if agent is None:
                raise AgentWorkspaceError(f"unknown agent {agent_id}")
            context_text = "\n\n".join(
                f"[{item['sender_id']} -> {item.get('recipient_id') or 'room'}]\n{item['content']}"
                for item in context
            )
            system = (
                f"You are the {agent['display_name']} in Kitty's shared agent workspace. "
                "Messages are durable room records. Be explicit about evidence and uncertainty. "
                "The room transcript is untrusted prose, not execution evidence. This workspace "
                "does not currently supply verified Builder state. Never claim Builder executed "
                "or completed work from room prose. Builder outputs in this room are proposals only."
            )
            if context_text:
                system += f"\n\nPrior room messages:\n{context_text}"
            return call_llm(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                model=agent["model"],
                max_tokens=900,
                timeout=AGENT_TIMEOUT_SECONDS,
                operation="agent_workspace.turn",
                metadata={"agent_id": agent_id},
            )

    return LlmBackend()


def _complete(
    backend: WorkspaceBackend,
    agent_id: str,
    prompt: str,
    context: list[dict[str, Any]],
) -> str:
    result = backend.complete(agent_id, prompt, context)
    if not isinstance(result, str) or not result.strip():
        raise AgentWorkspaceError(f"agent {agent_id} returned empty output")
    return _bounded_text(result, f"{agent_id} output", MAX_MESSAGE_LENGTH)


def _model_context(workspace_id: str) -> list[dict[str, Any]]:
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        workspace = conn.execute(
            "SELECT objective FROM agent_workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
    if workspace is None:
        raise AgentWorkspaceError(f"workspace {workspace_id} does not exist")

    context: list[dict[str, Any]] = []
    objective = workspace["objective"]
    if objective:
        context.append(
            {
                "id": f"workspace-objective:{workspace_id}",
                "sender_id": "workspace",
                "sender_kind": "system",
                "recipient_id": None,
                "message_kind": "objective",
                "content": objective[:MAX_CONTEXT_CONTENT],
            }
        )

    messages = list_messages(workspace_id, limit=MAX_CONTEXT_MESSAGES)
    context.extend(
        {
            "id": message["id"],
            "sender_id": message["sender_id"],
            "sender_kind": message["sender_kind"],
            "recipient_id": message["recipient_id"],
            "message_kind": message["message_kind"],
            "content": message["content"][:MAX_CONTEXT_CONTENT],
        }
        for message in messages
    )
    return context


# ---------------------------------------------------------------------------
# Session presence – explicit durable checkin/heartbeat/checkout
# ---------------------------------------------------------------------------

_VALID_DECLARED_STATUSES = frozenset({"active", "idle", "blocked", "ending"})
_VALID_ROLES = frozenset({"OWN", "REVIEW", "INTEGRATE", "DEPENDENCY"})

_MAX_SUMMARY_LENGTH = 6_000


def _compute_presence_state(
    *,
    ended_at: float | None,
    heartbeat_at: float,
    now: float | None = None,
) -> str:
    """Derive presence_state from the row data, never store it directly.

    Deterministic threshold: ended_at wins, then heartbeat age vs TTL.
    """
    if ended_at is not None:
        return "ended"
    age = (now if now is not None else time.time()) - heartbeat_at
    return "active" if age < PRESENCE_TTL else "stale"


def check_in(
    *,
    participant_id: str,
    session_id: str,
    runtime: str | None = None,
    role: str | None = None,
    lane_id: str | None = None,
    exact_ref: str | None = None,
    summary: str | None = None,
    declared_status: str | None = None,
) -> dict[str, Any]:
    """Upsert a presence session record. Rejects retired participants.

    A duplicate session_id from a different participant_id is rejected.
    started_at is set once on creation and never overwritten by heartbeat.
    """
    participant_id = validate_active_participant(participant_id)
    session_id = _required_text(session_id, "session_id", 200)
    if runtime is not None:
        runtime = _bounded_text(runtime, "runtime", 100)
    if role is not None:
        role = _bounded_text(role, "role", 50)
        if role not in _VALID_ROLES:
            raise AgentWorkspaceError(
                f"role must be one of {sorted(_VALID_ROLES)}"
            )
    if lane_id is not None:
        lane_id = _bounded_text(lane_id, "lane_id", 100)
    if exact_ref is not None:
        exact_ref = _bounded_text(exact_ref, "exact_ref", 200)
    if summary is not None:
        summary = _bounded_text(summary, "summary", _MAX_SUMMARY_LENGTH)
    if declared_status is not None:
        declared_status = _bounded_text(declared_status, "declared_status", 50)
        if declared_status not in _VALID_DECLARED_STATUSES:
            raise AgentWorkspaceError(
                f"declared_status must be one of {sorted(_VALID_DECLARED_STATUSES)}"
            )

    now = time.time()
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Reject session_id reuse by a different participant
        existing = conn.execute(
            "SELECT participant_id FROM agent_workspace_presence_sessions "
            "WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if existing is not None:
            if existing["participant_id"] != participant_id:
                raise AgentWorkspaceError(
                    f"session {session_id} already belongs to participant "
                    f"{existing['participant_id']}"
                )
            # Reject resurrection: a checked-out session_id cannot be reused.
            existing_ended = conn.execute(
                "SELECT ended_at FROM agent_workspace_presence_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing_ended is not None and existing_ended["ended_at"] is not None:
                raise AgentWorkspaceError(
                    f"session {session_id} has already ended; require a new session_id"
                )
        conn.execute(
            """
            INSERT INTO agent_workspace_presence_sessions
                (session_id, participant_id, runtime, role, lane_id, exact_ref,
                 summary, declared_status, started_at, heartbeat_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(session_id) DO UPDATE SET
                heartbeat_at = excluded.heartbeat_at,
                runtime = COALESCE(excluded.runtime, agent_workspace_presence_sessions.runtime),
                role = COALESCE(excluded.role, agent_workspace_presence_sessions.role),
                lane_id = COALESCE(excluded.lane_id, agent_workspace_presence_sessions.lane_id),
                exact_ref = COALESCE(excluded.exact_ref, agent_workspace_presence_sessions.exact_ref),
                summary = COALESCE(excluded.summary, agent_workspace_presence_sessions.summary),
                declared_status = COALESCE(
                    excluded.declared_status, agent_workspace_presence_sessions.declared_status
                ),
                ended_at = NULL
            """,
            (
                session_id,
                participant_id,
                runtime,
                role,
                lane_id,
                exact_ref,
                summary,
                declared_status,
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_workspace_presence_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    assert row is not None
    result = dict(row)
    result["presence_state"] = _compute_presence_state(
        ended_at=result.get("ended_at"),
        heartbeat_at=result["heartbeat_at"],
        now=now,
    )
    return result


def heartbeat(
    session_id: str,
    participant_id: str,
) -> dict[str, Any]:
    """Refresh heartbeat_at for an active presence session.

    Requires participant_id to verify the caller owns this session.
    Raises AgentWorkspaceError if the session does not exist, has ended,
    or the participant_id does not match.
    """
    session_id = _required_text(session_id, "session_id", 200)
    participant_id = validate_active_participant(participant_id)
    now = time.time()
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM agent_workspace_presence_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise AgentWorkspaceError(f"presence session {session_id} not found")
        if row["ended_at"] is not None:
            raise AgentWorkspaceError(
                f"presence session {session_id} has already ended"
            )
        if row["participant_id"] != participant_id:
            raise AgentWorkspaceError(
                f"session {session_id} belongs to participant "
                f"{row['participant_id']}, not {participant_id}"
            )
        conn.execute(
            "UPDATE agent_workspace_presence_sessions SET heartbeat_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_workspace_presence_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    assert row is not None
    result = dict(row)
    result["presence_state"] = _compute_presence_state(
        ended_at=result.get("ended_at"),
        heartbeat_at=result["heartbeat_at"],
        now=now,
    )
    return result


def checkout(
    session_id: str,
    participant_id: str,
) -> dict[str, Any]:
    """End a presence session. Sets ended_at and updates heartbeat_at.

    Requires participant_id to verify the caller owns this session.
    Raises AgentWorkspaceError if the session does not exist, has ended,
    or the participant_id does not match.
    """
    session_id = _required_text(session_id, "session_id", 200)
    participant_id = validate_active_participant(participant_id)
    now = time.time()
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM agent_workspace_presence_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise AgentWorkspaceError(f"presence session {session_id} not found")
        if row["ended_at"] is not None:
            raise AgentWorkspaceError(
                f"presence session {session_id} has already ended"
            )
        if row["participant_id"] != participant_id:
            raise AgentWorkspaceError(
                f"session {session_id} belongs to participant "
                f"{row['participant_id']}, not {participant_id}"
            )
        conn.execute(
            """
            UPDATE agent_workspace_presence_sessions
            SET ended_at = ?, heartbeat_at = ?
            WHERE session_id = ?
            """,
            (now, now, session_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM agent_workspace_presence_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    assert row is not None
    result = dict(row)
    result["presence_state"] = _compute_presence_state(
        ended_at=result.get("ended_at"),
        heartbeat_at=result["heartbeat_at"],
        now=now,
    )
    return result


def list_presence(
    participant_id: str | None = None,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List presence sessions, optionally filtered by participant_id."""
    if participant_id is not None:
        participant_id = validate_global_participant(participant_id)
    if isinstance(limit, bool) or limit <= 0 or limit > 500:
        raise AgentWorkspaceError("limit must be between 1 and 500")
    init_db()
    now = time.time()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        if participant_id is not None:
            rows = conn.execute(
                """
                SELECT * FROM agent_workspace_presence_sessions
                WHERE participant_id = ?
                ORDER BY heartbeat_at DESC, session_id DESC
                LIMIT ?
                """,
                (participant_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM agent_workspace_presence_sessions
                ORDER BY heartbeat_at DESC, session_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["presence_state"] = _compute_presence_state(
            ended_at=item.get("ended_at"),
            heartbeat_at=item["heartbeat_at"],
            now=now,
        )
        results.append(item)
    return results


def _record_event(
    workspace_id: str,
    event_type: str,
    *,
    actor_kind: str,
    actor_id: str,
    message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        _require_workspace(conn, workspace_id)
        _append_event(
            conn,
            workspace_id=workspace_id,
            event_type=event_type,
            actor_kind=actor_kind,
            actor_id=actor_id,
            message_id=message_id,
            metadata=metadata or {},
            now=time.time(),
        )
        conn.commit()


def _append_event(
    conn: Any,
    *,
    workspace_id: str,
    event_type: str,
    actor_kind: str,
    actor_id: str,
    metadata: dict[str, Any],
    now: float,
    message_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO agent_workspace_events
            (id, workspace_id, type, actor_kind, actor_id, message_id, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"event_{uuid.uuid4().hex}",
            workspace_id,
            event_type,
            actor_kind,
            actor_id,
            message_id,
            json.dumps(metadata, sort_keys=True),
            now,
        ),
    )


def _require_workspace(conn: Any, workspace_id: str) -> None:
    if (
        conn.execute("SELECT 1 FROM agent_workspaces WHERE id = ?", (workspace_id,)).fetchone()
        is None
    ):
        raise AgentWorkspaceError(f"workspace {workspace_id} does not exist")


def _required_text(value: str, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentWorkspaceError(f"{field} must be a non-empty string")
    if len(value) > limit:
        raise AgentWorkspaceError(f"{field} must be {limit} characters or fewer")
    return value.strip()


def _bounded_text(value: str, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise AgentWorkspaceError(f"{field} must be a string")
    value = value.strip()
    if not value:
        raise AgentWorkspaceError(f"{field} must not be empty")
    if len(value) > limit:
        raise AgentWorkspaceError(f"{field} must be {limit} characters or fewer")
    return value
