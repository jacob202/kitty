"""Durable shared rooms for user and specialist-agent collaboration.

This is a collaboration layer over Kitty's existing product database. It does
not replace Builder's execution queue or create a second work authority.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Protocol

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

WORKSPACE_DB_FILE = KITTY_DB_FILE
MAX_MESSAGE_LENGTH = 12_000
MAX_CONTEXT_MESSAGES = 40
MAX_CONTEXT_CONTENT = 4_000

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
        "model": "deepseek/deepseek-v4-flash",
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


class AgentWorkspaceError(RuntimeError):
    """Raised when a workspace operation cannot be completed safely."""


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
    result = dict(workspace)
    result["agents"] = [
        {**agent, "id": agent.pop("agent_id")} for agent in agents
    ]
    result["messages"] = list_messages(workspace_id)
    result["events"] = list_events(workspace_id)
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
) -> dict[str, Any]:
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
        _require_workspace(conn, workspace_id)
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
        rows = conn.execute(
            """
            SELECT * FROM agent_workspace_messages
            WHERE workspace_id = ?
            ORDER BY created_at, id
            LIMIT ?
            """,
            (workspace_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_events(workspace_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    workspace_id = _required_text(workspace_id, "workspace_id", 200)
    if isinstance(limit, bool) or limit <= 0 or limit > 1_000:
        raise AgentWorkspaceError("limit must be between 1 and 1000")
    init_db()
    with kitty_db.connect(WORKSPACE_DB_FILE) as conn:
        _require_workspace(conn, workspace_id)
        rows = conn.execute(
            """
            SELECT * FROM agent_workspace_events
            WHERE workspace_id = ?
            ORDER BY created_at, id
            LIMIT ?
            """,
            (workspace_id, limit),
        ).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        event["metadata"] = json.loads(event.pop("metadata_json"))
        events.append(event)
    return events


def run_turn(
    workspace_id: str,
    user_text: str,
    *,
    backend: WorkspaceBackend | None = None,
    user_id: str = "jacob",
) -> dict[str, Any]:
    """Run one durable Planner -> Researcher -> Reviewer room turn.

    This is intentionally advisory. The Builder identity is present in the
    roster, but code execution still belongs to KittyBuilder's existing
    Mission/Work contract and is not started by this slice.
    """
    user_text = _bounded_text(user_text, "message", MAX_MESSAGE_LENGTH)
    user_id = _required_text(user_id, "user_id", 200)
    get_workspace(workspace_id)
    backend = backend or _default_backend()
    _record_event(
        workspace_id,
        "turn_started",
        actor_kind="user",
        actor_id=user_id,
        metadata={"agent_sequence": ["planner", "researcher", "reviewer"]},
    )
    try:
        user_message = append_message(
            workspace_id,
            sender_kind="user",
            sender_id=user_id,
            content=user_text,
            message_kind="prompt",
        )
        planner_context = _model_context(workspace_id)
        planner = _complete(
            backend,
            "planner",
            (
                f"User request:\n{user_text}\n\n"
                "Produce a bounded plan for the room. Identify the desired outcome, "
                "unknowns, acceptance evidence, and the next specialist handoff. "
                "Do not claim that any code or external action has happened."
            ),
            planner_context,
        )
        planner_message = append_message(
            workspace_id,
            sender_kind="agent",
            sender_id="planner",
            recipient_id="researcher",
            content=planner,
            message_kind="plan",
            parent_message_id=user_message["id"],
        )
        researcher = _complete(
            backend,
            "researcher",
            (
                "Review the Planner's handoff below. Return relevant evidence, "
                "risks, and concrete information the Reviewer needs. Stay read-only.\n\n"
                f"Planner handoff:\n{planner}"
            ),
            _model_context(workspace_id),
        )
        researcher_message = append_message(
            workspace_id,
            sender_kind="agent",
            sender_id="researcher",
            recipient_id="reviewer",
            content=researcher,
            message_kind="handoff",
            parent_message_id=planner_message["id"],
        )
        reviewer = _complete(
            backend,
            "reviewer",
            (
                "Review the Planner and Researcher outputs. Return a concise verdict, "
                "remaining blockers, and one recommended next action for Jacob. "
                "Do not claim Builder execution or completion.\n\n"
                f"Planner:\n{planner}\n\nResearcher:\n{researcher}"
            ),
            _model_context(workspace_id),
        )
        append_message(
            workspace_id,
            sender_kind="agent",
            sender_id="reviewer",
            recipient_id=user_id,
            content=reviewer,
            message_kind="review",
            parent_message_id=researcher_message["id"],
        )
        _record_event(
            workspace_id,
            "turn_completed",
            actor_kind="system",
            actor_id="gateway",
            metadata={"agent_sequence": ["planner", "researcher", "reviewer"]},
        )
    except Exception as exc:
        _record_event(
            workspace_id,
            "turn_failed",
            actor_kind="system",
            actor_id="gateway",
            metadata={"error_type": type(exc).__name__},
        )
        raise
    return {
        "status": "completed",
        "workspace_id": workspace_id,
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
                f"[{item['sender_id']} -> {item.get('recipient_id') or 'room'}]\n"
                f"{item['content']}"
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
    if conn.execute(
        "SELECT 1 FROM agent_workspaces WHERE id = ?", (workspace_id,)
    ).fetchone() is None:
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
