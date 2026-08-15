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
    result["agents"] = [{**agent, "id": agent.pop("agent_id")} for agent in agents]
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
        if parent_message_id is not None:
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
            message = append_message(
                workspace_id,
                sender_kind="agent",
                sender_id=agent_id,
                recipient_id=recipient_id,
                content=output,
                message_kind=message_kind,
                parent_message_id=parent_message_id,
                require_turn_running=turn_id,
            )
            outputs[agent_id] = output
            parent_message_id = message["id"]
            _record_event(
                workspace_id,
                "agent_completed",
                actor_kind="agent",
                actor_id=agent_id,
                message_id=message["id"],
                metadata={"turn_id": turn_id},
            )
    except Exception as exc:
        logger.exception("shared agent turn %s failed at %s", turn_id, active_agent_id)
        _record_turn_failure(
            workspace_id,
            turn_id,
            active_agent_id=active_agent_id,
            parent_message_id=parent_message_id,
            exc=exc,
        )
    else:
        _finish_turn(workspace_id, turn_id, status="completed")
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
    now = time.time()
    failure_message_id = f"message_{uuid.uuid4().hex}"
    failure_content = (
        f"Incomplete: {active_agent_id or 'the room'} could not finish. {error_type}: {detail}"
    )
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
            metadata={"turn_id": turn_id, "error_type": error_type, "error_message": detail},
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
            metadata={"turn_id": turn_id, "error_type": error_type, "error_message": detail},
            now=now,
        )
        conn.commit()


def _bounded_failure_detail(exc: Exception) -> str:
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
                "Messages are durable room records. Be explicit about evidence and "
                "uncertainty. Never claim that another agent or Builder performed an "
                "action unless the room contains evidence."
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
    messages = list_messages(workspace_id, limit=MAX_CONTEXT_MESSAGES)
    return [
        {
            "id": message["id"],
            "sender_id": message["sender_id"],
            "sender_kind": message["sender_kind"],
            "recipient_id": message["recipient_id"],
            "message_kind": message["message_kind"],
            "content": message["content"][:MAX_CONTEXT_CONTENT],
        }
        for message in messages
    ]


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
