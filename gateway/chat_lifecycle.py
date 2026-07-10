"""Durable normalized chat turns and generation attempts.

The legacy ``chats`` JSON blob remains the UI compatibility record. This
ledger records the lifecycle facts needed for restart recovery and honest
status without forcing a client migration in the same packet.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from gateway import db as kitty_db
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

    init_db()
    now = time.time()
    turn_id = f"turn_{uuid.uuid4().hex}"
    attempt_id = f"attempt_{uuid.uuid4().hex}"
    user_storage_id = f"message_{uuid.uuid4().hex}"
    with kitty_db.connect(LIFECYCLE_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO chat_conversations (id, project_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_id = COALESCE(excluded.project_id, chat_conversations.project_id),
                title = CASE
                    WHEN excluded.title = '' THEN chat_conversations.title
                    ELSE excluded.title
                END,
                updated_at = excluded.updated_at
            """,
            (conversation_id, project_id, title, now, now),
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
                (id, turn_id, role, content, status, source_message_id, created_at)
            VALUES (?, ?, 'user', ?, 'complete', ?, ?)
            """,
            (user_storage_id, turn_id, user_text, user_message_id, now),
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
) -> None:
    """Atomically finalize an attempt, assistant message, and parent turn."""
    if status not in _TURN_STATUSES or status == "running":
        raise ChatLifecycleError(f"invalid terminal chat status {status!r}")
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
                    (id, turn_id, role, content, status, created_at)
                VALUES (?, ?, 'assistant', ?, ?, ?)
                """,
                (
                    f"message_{handle.attempt_id}",
                    handle.turn_id,
                    assistant_text,
                    message_status,
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
