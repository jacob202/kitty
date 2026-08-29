"""Durable normalized chat turns and generation attempts.

The legacy ``chats`` JSON blob remains the UI compatibility record. This
ledger records the lifecycle facts needed for restart recovery and honest
status without forcing a client migration in the same packet.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from gateway import db as kitty_db
from gateway.memory_graph import MemoryEvidence
from gateway.paths import KITTY_DB_FILE

LIFECYCLE_DB_FILE = KITTY_DB_FILE

_TURN_STATUSES = {"running", "succeeded", "failed", "interrupted", "cancelled"}


class ChatLifecycleError(RuntimeError):
    """Raised when a durable chat lifecycle transition cannot be recorded."""


@dataclass(frozen=True)
class TurnHandle:
    conversation_id: str
    turn_id: str
    attempt_id: str
    sequence: int


def _validate_memory_items(
    memory_items: list[MemoryEvidence] | None,
) -> list[MemoryEvidence] | None:
    """Validate the exact structured evidence that reached the client."""
    if memory_items is None:
        return None
    if not isinstance(memory_items, list):
        raise ChatLifecycleError("memory_items must be a list of memory evidence records or None")

    validated: list[MemoryEvidence] = []
    for item in memory_items:
        if not isinstance(item, dict):
            raise ChatLifecycleError("each memory_items entry must be an object")
        unexpected = set(item) - {"text", "memory_id"}
        if unexpected:
            raise ChatLifecycleError(
                f"memory_items entry contains unsupported fields: {sorted(unexpected)!r}"
            )
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ChatLifecycleError("each memory_items entry must contain non-empty string text")
        record: MemoryEvidence = {"text": text}
        memory_id = item.get("memory_id")
        if memory_id is not None:
            if not isinstance(memory_id, str) or not memory_id.strip():
                raise ChatLifecycleError("memory_id must be a non-empty string when provided")
            record["memory_id"] = memory_id
        validated.append(record)
    return validated


def init_db() -> None:
    kitty_db.migrate(db_file=LIFECYCLE_DB_FILE)


def start_turn(
    *,
    conversation_id: str,
    project_id: int | None,
    title: str,
    user_message_id: str | None,
    user_text: str,
    manifest_revision: str,
    requested_model: str,
    attachment_ids: list[str] | None = None,
    objective: str | None = None,
) -> TurnHandle:
    """Persist the user message and running attempt before provider dispatch."""
    if not conversation_id.strip():
        raise ChatLifecycleError("conversation_id must not be empty")
    if project_id is not None and (isinstance(project_id, bool) or project_id <= 0):
        raise ChatLifecycleError(f"project_id must be positive, got {project_id!r}")
    if not isinstance(user_text, str):
        raise ChatLifecycleError("the latest user message must contain string content")
    if not manifest_revision.strip():
        raise ChatLifecycleError("manifest_revision must not be empty")
    if not requested_model.strip():
        raise ChatLifecycleError("requested_model must not be empty")
    if attachment_ids is not None:
        if not isinstance(attachment_ids, list) or not all(
            isinstance(a, str) and a.strip() for a in attachment_ids
        ):
            raise ChatLifecycleError("attachment_ids must be a list of non-empty strings")
    if objective is not None and not isinstance(objective, str):
        raise ChatLifecycleError("objective must be a string or None")
    artifact_ids_json = json.dumps(attachment_ids or [])

    init_db()
    now = time.time()
    turn_id = f"turn_{uuid.uuid4().hex}"
    attempt_id = f"attempt_{uuid.uuid4().hex}"
    user_storage_id = f"message_{uuid.uuid4().hex}"
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO chat_conversations
                (id, project_id, title, objective, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_id = COALESCE(excluded.project_id, chat_conversations.project_id),
                title = CASE
                    WHEN excluded.title = '' THEN chat_conversations.title
                    ELSE excluded.title
                END,
                objective = COALESCE(excluded.objective, chat_conversations.objective),
                updated_at = excluded.updated_at
            """,
            (conversation_id, project_id, title, objective, now, now),
        )
        sequence = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM chat_turns WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO chat_turns
                (id, conversation_id, project_id, sequence, status, manifest_revision, created_at)
            VALUES (?, ?, ?, ?, 'running', ?, ?)
            """,
            (turn_id, conversation_id, project_id, sequence, manifest_revision, now),
        )
        conn.execute(
            """
            INSERT INTO chat_attempts
                (id, turn_id, attempt_number, requested_model, status,
                 manifest_revision, started_at)
            VALUES (?, ?, 1, ?, 'running', ?, ?)
            """,
            (attempt_id, turn_id, requested_model, manifest_revision, now),
        )
        conn.execute(
            """
            INSERT INTO chat_messages
                (id, turn_id, role, content, status, source_message_id, artifact_ids, created_at)
            VALUES (?, ?, 'user', ?, 'complete', ?, ?, ?)
            """,
            (user_storage_id, turn_id, user_text, user_message_id, artifact_ids_json, now),
        )
        conn.commit()
    return TurnHandle(conversation_id, turn_id, attempt_id, sequence)


def finish_turn(
    handle: TurnHandle,
    *,
    status: str,
    assistant_text: str,
    resolved_model: str | None = None,
    error: str | None = None,
    memory_items: list[MemoryEvidence] | None = None,
) -> None:
    """Atomically finalize an attempt, assistant message, and parent turn.

    ``memory_items`` is the CR-04 memory evidence actually delivered to the
    client for this reply; it is stored on the assistant message so ledger
    recovery can restore the "kitty remembered" block.
    """
    if status not in _TURN_STATUSES or status == "running":
        raise ChatLifecycleError(f"invalid terminal chat status {status!r}")
    validated_memory_items = _validate_memory_items(memory_items)
    now = time.time()
    message_status = {
        "succeeded": "complete",
        "failed": "failed",
        "interrupted": "interrupted",
        "cancelled": "interrupted",
    }[status]
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        row = conn.execute(
            "SELECT status FROM chat_attempts WHERE id = ? AND turn_id = ?",
            (handle.attempt_id, handle.turn_id),
        ).fetchone()
        if row is None:
            raise ChatLifecycleError(f"attempt {handle.attempt_id} does not exist")
        if row["status"] != "running":
            raise ChatLifecycleError(
                f"attempt {handle.attempt_id} is already terminal ({row['status']})"
            )
        conn.execute(
            """
            UPDATE chat_attempts
            SET status = ?, resolved_model = ?, completed_at = ?, error = ?
            WHERE id = ? AND status = 'running'
            """,
            (status, resolved_model, now, error, handle.attempt_id),
        )
        if assistant_text:
            conn.execute(
                """
                INSERT INTO chat_messages
                    (id, turn_id, role, content, status, memory_items, created_at)
                VALUES (?, ?, 'assistant', ?, ?, ?, ?)
                """,
                (
                    f"message_{handle.attempt_id}",
                    handle.turn_id,
                    assistant_text,
                    message_status,
                    json.dumps(validated_memory_items) if validated_memory_items else None,
                    now,
                ),
            )
        conn.execute(
            """
            UPDATE chat_turns
            SET status = ?, completed_at = ?, error = ?
            WHERE id = ? AND status = 'running'
            """,
            (status, now, error, handle.turn_id),
        )
        conn.execute(
            "UPDATE chat_conversations SET updated_at = ? WHERE id = ?",
            (now, handle.conversation_id),
        )
        conn.commit()


RESTART_INTERRUPTED_ERROR = "Gateway restarted before the chat turn finished"
RESTART_INTERRUPTED_MESSAGE = "Kitty restarted before this reply finished. Tap retry to try again."
RESTART_INTERRUPTED_NO_RETRY_MESSAGE = "Kitty restarted before this reply finished."


def list_running_conversations() -> list[dict[str, Any]]:
    """Return conversation shells that currently own at least one running turn."""
    init_db()
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT c.id, c.project_id, c.title, c.objective, c.created_at, c.updated_at
            FROM chat_conversations AS c
            JOIN chat_turns AS t ON t.conversation_id = c.id
            WHERE t.status = 'running'
            ORDER BY c.updated_at DESC, c.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def reconcile_interrupted_turns() -> int:
    """Mark chat work left running by a previous Gateway process interrupted.

    A newly-started process cannot own an in-flight coroutine from the previous
    process. Leaving those rows as ``running`` makes restart recovery lie, so
    close them atomically and persist one plain-language assistant record that
    the UI can restore with its normal retry affordance.
    """
    init_db()
    now = time.time()
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, conversation_id, sequence FROM chat_turns WHERE status = 'running' ORDER BY created_at"
        ).fetchall()
        latest_sequence = {}
        for row in rows:
            latest_sequence[row["conversation_id"]] = max(
                row["sequence"], latest_sequence.get(row["conversation_id"], row["sequence"])
            )
        for row in rows:
            turn_id = row["id"]
            conversation_id = row["conversation_id"]
            interruption_message = (
                RESTART_INTERRUPTED_MESSAGE
                if row["sequence"] == latest_sequence[conversation_id]
                else RESTART_INTERRUPTED_NO_RETRY_MESSAGE
            )
            conn.execute(
                """
                UPDATE chat_attempts
                SET status = 'interrupted', completed_at = ?, error = ?
                WHERE turn_id = ? AND status = 'running'
                """,
                (now, RESTART_INTERRUPTED_ERROR, turn_id),
            )
            existing_assistant = conn.execute(
                "SELECT id FROM chat_messages WHERE turn_id = ? AND role = 'assistant' LIMIT 1",
                (turn_id,),
            ).fetchone()
            if existing_assistant is None:
                conn.execute(
                    """
                    INSERT INTO chat_messages
                        (id, turn_id, role, content, status, created_at)
                    VALUES (?, ?, 'assistant', ?, 'interrupted', ?)
                    """,
                    (f"message_restart_{turn_id}", turn_id, interruption_message, now),
                )
            else:
                conn.execute(
                    "UPDATE chat_messages SET status = 'interrupted' WHERE turn_id = ? AND role = 'assistant'",
                    (turn_id,),
                )
            conn.execute(
                """
                UPDATE chat_turns
                SET status = 'interrupted', completed_at = ?, error = ?
                WHERE id = ? AND status = 'running'
                """,
                (now, RESTART_INTERRUPTED_ERROR, turn_id),
            )
            conn.execute(
                "UPDATE chat_conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        conn.commit()
    return len(rows)


def get_turn(turn_id: str) -> dict[str, Any] | None:
    """Return a turn with its attempts and messages for recovery/read paths."""
    init_db()
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        turn = conn.execute("SELECT * FROM chat_turns WHERE id = ?", (turn_id,)).fetchone()
        if turn is None:
            return None
        result = dict(turn)
        result["attempts"] = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM chat_attempts WHERE turn_id = ? ORDER BY attempt_number",
                (turn_id,),
            ).fetchall()
        ]
        result["messages"] = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM chat_messages WHERE turn_id = ? ORDER BY created_at, id",
                (turn_id,),
            ).fetchall()
        ]
        return result


def list_project_conversations(project_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    """Return recent conversation descriptors owned by one Project.

    This is a read-side projection from the canonical chat lifecycle store. It
    deliberately does not load turns/messages; Project Resume needs context,
    not a second copy of conversation contents.
    """
    if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
        raise ChatLifecycleError(f"project_id must be positive, got {project_id!r}")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ChatLifecycleError(f"limit must be a positive integer, got {limit!r}")
    bounded_limit = min(limit, 100)
    init_db()
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, title, objective, created_at, updated_at
            FROM chat_conversations
            WHERE project_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (project_id, bounded_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_conversation(conversation_id: str) -> dict[str, Any]:
    """Return normalized conversation state and all ordered turns in bulk.

    Recovery used to call ``get_turn`` once per turn, opening a new SQLite
    connection and issuing additional queries for every turn. Fetch all turns,
    attempts, and messages with the same connection instead. This keeps the
    read cost bounded by the number of lifecycle tables rather than the number
    of turns in the conversation.
    """
    if not conversation_id.strip():
        raise ChatLifecycleError("conversation_id must not be empty")
    init_db()
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        conversation = conn.execute(
            "SELECT * FROM chat_conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if conversation is None:
            raise ChatLifecycleError(f"conversation {conversation_id} does not exist")

        turn_rows = conn.execute(
            "SELECT * FROM chat_turns WHERE conversation_id = ? ORDER BY sequence",
            (conversation_id,),
        ).fetchall()
        turn_ids = [row["id"] for row in turn_rows]

        if not turn_ids:
            return {"conversation": dict(conversation), "turns": []}

        placeholders = ",".join("?" for _ in turn_ids)
        attempt_rows = conn.execute(
            f"""
            SELECT * FROM chat_attempts
            WHERE turn_id IN ({placeholders})
            ORDER BY turn_id, attempt_number
            """,
            turn_ids,
        ).fetchall()
        message_rows = conn.execute(
            f"""
            SELECT * FROM chat_messages
            WHERE turn_id IN ({placeholders})
            ORDER BY turn_id, created_at, id
            """,
            turn_ids,
        ).fetchall()

    attempts_by_turn: dict[str, list[dict[str, Any]]] = {turn_id: [] for turn_id in turn_ids}
    messages_by_turn: dict[str, list[dict[str, Any]]] = {turn_id: [] for turn_id in turn_ids}

    for row in attempt_rows:
        attempts_by_turn[row["turn_id"]].append(dict(row))
    for row in message_rows:
        messages_by_turn[row["turn_id"]].append(dict(row))

    turns: list[dict[str, Any]] = []
    for row in turn_rows:
        turn = dict(row)
        turn["attempts"] = attempts_by_turn[row["id"]]
        turn["messages"] = messages_by_turn[row["id"]]
        turns.append(turn)

    return {"conversation": dict(conversation), "turns": turns}
