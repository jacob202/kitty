"""Undo/Restore journal for Packet 09.

This is a projection + dispatcher over the single Kitty DB (``KITTY_DB_FILE``),
NOT a new backend. Mutations record a ``before``/``after`` snapshot in
``undo_journal``; ``undo`` restores ``before`` by calling the owning module's own
mutator, which produces a NEW valid state rather than rewriting history.

Undo is refused (fail-loud) when: the entry is already undone, a newer change
to the same entity would be clobbered, or restoring would resurface a forgotten
sensitive memory.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

DB_FILE = KITTY_DB_FILE

ENTITY_TYPES = frozenset({"memory", "character", "automation", "image", "todo"})


class UndoError(Exception):
    """An undo cannot be applied (already undone, refused, or malformed)."""


class UndoNotFound(UndoError):
    """The journal entry (or the entity it references) does not exist."""


class UndoConflict(UndoError):
    """A newer change to the same entity would be clobbered by this undo."""


def _ensure_db() -> None:
    kitty_db.migrate(db_file=DB_FILE)


def _connect() -> Any:
    return kitty_db.connect(DB_FILE)


def record(
    entity_type: str,
    entity_id: str,
    operation: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    *,
    now: float | None = None,
) -> str:
    """Append a journal entry and return its id."""
    if entity_type not in ENTITY_TYPES:
        raise UndoError(f"unknown entity type: {entity_type!r}")
    _ensure_db()
    journal_id = f"undo_{secrets.token_hex(8)}"
    created_at = float(now if now is not None else time.time())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO undo_journal (
                id, entity_type, entity_id, operation,
                before_json, after_json, undone, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                journal_id,
                entity_type,
                entity_id,
                operation,
                json.dumps(before or {}),
                json.dumps(after or {}),
                created_at,
            ),
        )
        conn.commit()
    return journal_id


def _entry_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "operation": row["operation"],
        "before": json.loads(row["before_json"]),
        "after": json.loads(row["after_json"]),
        "undone": bool(row["undone"]),
        "created_at": row["created_at"],
    }


def get(journal_id: str) -> dict[str, Any] | None:
    _ensure_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM undo_journal WHERE id = ?", (journal_id,)
        ).fetchone()
    return _entry_from_row(row) if row is not None else None


def _public_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive memory snapshots from the user-visible history API."""
    if entry["entity_type"] == "memory":
        snapshots = (entry.get("before") or {}, entry.get("after") or {})
        if any(snapshot.get("sensitivity") == "sensitive" for snapshot in snapshots):
            return {**entry, "before": {"redacted": True}, "after": {"redacted": True}}
    return entry


def list_history(
    entity_type: str, entity_id: str, *, limit: int = 50
) -> list[dict[str, Any]]:
    if entity_type not in ENTITY_TYPES:
        raise UndoError(f"unknown entity type {entity_type!r}")
    _ensure_db()
    limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM undo_journal
             WHERE entity_type = ? AND entity_id = ?
             ORDER BY created_at DESC, rowid DESC
             LIMIT ?
            """,
            (entity_type, entity_id, limit),
        ).fetchall()
    return [_public_entry(_entry_from_row(r)) for r in rows]


# --- snapshots ---------------------------------------------------------------


def snapshot_memory(memory_id: str) -> dict[str, Any]:
    from gateway import explicit_memory

    row = explicit_memory.get(memory_id, include_inactive=True)
    if row is None:
        raise UndoNotFound(f"memory not found: {memory_id}")
    return {
        "id": row["id"],
        "text": row["text"],
        "namespace": row["namespace"],
        "memory_key": row["memory_key"],
        "source_kind": row["source_kind"],
        "source_ref": row["source_ref"],
        "sensitivity": row["sensitivity"],
        "pinned": bool(row["pinned"]),
        "status": row["status"],
    }


def snapshot_character(character_id: str) -> dict[str, Any]:
    from gateway import image_characters

    char = image_characters.get_character(character_id)
    return {
        "name": char.name,
        "description": char.description,
        "preferred_recipe": char.preferred_recipe,
        "identity_preset": char.identity_preset,
        "tags": list(char.tags) if char.tags else None,
    }


def snapshot_automation(sid: str) -> dict[str, Any]:
    from gateway import cron

    for row in cron.list_schedules():
        if row.get("id") == sid:
            return row
    raise UndoNotFound(f"automation schedule not found: {sid}")


def snapshot_anchor(session_id: str) -> dict[str, Any]:
    from gateway import image_sessions

    session = image_sessions.get_session(session_id)
    if session is None:
        raise UndoNotFound(f"session not found: {session_id}")
    return {
        "anchor_job_id": session.anchor_job_id,
        "anchor_artifact_id": session.anchor_artifact_id,
    }


def snapshot_todo(todo_id: int) -> dict[str, Any]:
    from gateway import todo_store

    todos = todo_store.get()
    for t in todos:
        if t["id"] == todo_id:
            return {
                "id": t["id"],
                "content": t["content"],
                "status": t["status"],
                "active_form": t.get("active_form", ""),
                "sort_order": t["sort_order"],
            }
    raise UndoNotFound(f"todo not found: {todo_id}")


# --- restore dispatch --------------------------------------------------------


def _restore(entry: dict[str, Any]) -> dict[str, Any]:
    entity_type = entry["entity_type"]
    operation = entry["operation"]
    entity_id = entry["entity_id"]
    before = entry["before"]

    if entity_type == "character":
        from gateway import image_characters

        image_characters.restore_character_profile(
            entity_id,
            name=before.get("name") or "",
            description=before.get("description"),
            preferred_recipe=before.get("preferred_recipe"),
            identity_preset=before.get("identity_preset") or "balanced",
            tags=before.get("tags"),
        )
        return {"entity_type": entity_type, "entity_id": entity_id, "restored": "character"}

    if entity_type == "automation":
        from gateway import cron

        if operation == "toggle":
            current = [r for r in cron.list_schedules() if r.get("id") == entity_id]
            if current and bool(current[0].get("enabled")) != bool(before.get("enabled")):
                cron.toggle(entity_id)
            return {"entity_type": entity_type, "entity_id": entity_id, "restored": "automation"}

        metadata = before.get("metadata") or "{}"
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        cron.update(
            entity_id,
            before.get("name") or "",
            before.get("action") or "",
            before.get("schedule_type") or "daily",
            before.get("schedule_value") or "07:00",
            metadata=metadata,
        )
        return {"entity_type": entity_type, "entity_id": entity_id, "restored": "automation"}

    if entity_type == "memory":
        from gateway import explicit_memory

        if operation == "forget":
            if before.get("sensitivity") == "sensitive":
                raise UndoError("refusing to resurface a forgotten sensitive memory")
            explicit_memory.remember(
                before.get("text") or "",
                namespace=before.get("namespace") or "facts",
                memory_key=before.get("memory_key"),
                source_kind=before.get("source_kind") or "user_explicit",
                source_ref=before.get("source_ref"),
                sensitivity=before.get("sensitivity") or "normal",
                pinned=bool(before.get("pinned")),
            )
            return {"entity_type": entity_type, "entity_id": entity_id, "restored": "memory"}

        if operation == "correct":
            new_id = entry["after"].get("id") if isinstance(entry["after"], dict) else None
            explicit_memory.remember(
                before.get("text") or "",
                namespace=before.get("namespace") or "facts",
                memory_key=before.get("memory_key"),
                supersedes_id=new_id,
                source_kind="user_correction",
                source_ref=before.get("source_ref"),
                sensitivity=before.get("sensitivity") or "normal",
                pinned=bool(before.get("pinned")),
            )
            return {"entity_type": entity_type, "entity_id": entity_id, "restored": "memory"}

        raise UndoError(f"unsupported memory operation: {operation!r}")

    if entity_type == "image":
        from gateway import image_sessions

        anchor_job_id = before.get("anchor_job_id")
        if anchor_job_id:
            image_sessions.set_anchor(entity_id, anchor_job_id)
        else:
            image_sessions.clear_anchor(entity_id)
        return {"entity_type": entity_type, "entity_id": entity_id, "restored": "image"}

    if entity_type == "todo":
        from gateway import todo_store

        if operation == "create":
            # Undoing a create = delete the todo that was created.
            todo_id = int(entity_id)
            if not todo_store.delete_by_id(todo_id):
                raise UndoNotFound(f"todo not found: {todo_id}")
            return {"entity_type": entity_type, "entity_id": entity_id, "restored": "todo"}

        raise UndoError(f"unsupported todo operation: {operation!r}")

    raise UndoError(f"unsupported entity type: {entity_type!r}")


def undo(journal_id: str) -> dict[str, Any]:
    """Restore the ``before`` state captured by a journal entry."""
    entry = get(journal_id)
    if entry is None:
        raise UndoNotFound(f"journal entry not found: {journal_id}")
    if entry["undone"]:
        raise UndoError(f"journal entry already undone: {journal_id}")

    # Conflict guard: refuse if any NEWER, still-pending entry exists for the same
    # entity. Ordering uses rowid (monotonic insert order) rather than created_at,
    # which can tie when several mutations land within the same clock tick.
    with _connect() as conn:
        row = conn.execute(
            "SELECT rowid FROM undo_journal WHERE id = ?", (journal_id,)
        ).fetchone()
    if row is None:
        raise UndoNotFound(f"journal entry not found: {journal_id}")
    entry_rowid = row["rowid"]
    with _connect() as conn:
        newer = conn.execute(
            """
            SELECT id FROM undo_journal
             WHERE entity_type = ? AND entity_id = ?
               AND id != ? AND undone = 0 AND rowid > ?
             ORDER BY rowid DESC
             LIMIT 1
            """,
            (entry["entity_type"], entry["entity_id"], journal_id, entry_rowid),
        ).fetchone()
    if newer is not None:
        raise UndoConflict(
            f"newer change {newer['id']!r} for "
            f"{entry['entity_type']}/{entry['entity_id']} would be clobbered"
        )

    result = _restore(entry)
    restoration_id = f"undo_{secrets.token_hex(8)}"
    with _connect() as conn:
        conn.execute("UPDATE undo_journal SET undone = 1 WHERE id = ?", (journal_id,))
        conn.execute(
            """
            INSERT INTO undo_journal
                (id, entity_type, entity_id, operation, before_json, after_json, undone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                restoration_id,
                entry["entity_type"],
                entry["entity_id"],
                f"undo:{entry['operation']}",
                json.dumps(entry["after"], ensure_ascii=False),
                json.dumps(entry["before"], ensure_ascii=False),
                time.time(),
            ),
        )
        conn.commit()
    result["journal_id"] = journal_id
    result["restoration_journal_id"] = restoration_id
    return result


# --- with-undo mutation helpers ---------------------------------------------


def forget_memory_with_undo(memory_id: str) -> str:
    from gateway import explicit_memory

    before = snapshot_memory(memory_id)
    if not explicit_memory.forget(memory_id):
        raise UndoNotFound(f"active memory not found: {memory_id}")
    return record("memory", memory_id, "forget", before, {"id": memory_id, "status": "forgotten"})


def correct_memory_with_undo(
    memory_id: str, text: str, *, memory_key: str | None = None
) -> str:
    from gateway import explicit_memory

    before = snapshot_memory(memory_id)
    try:
        corrected = explicit_memory.remember(
            text,
            namespace=before["namespace"],
            memory_key=memory_key or before["memory_key"],
            supersedes_id=memory_id,
            source_kind="user_correction",
            source_ref=before.get("source_ref"),
            sensitivity=before.get("sensitivity") or "normal",
            pinned=bool(before.get("pinned")),
        )
    except explicit_memory.ExplicitMemoryNotFound as exc:
        raise UndoNotFound(f"active memory not found: {memory_id}") from exc
    after = {
        "id": corrected["id"],
        "text": corrected["text"],
        "status": corrected["status"],
    }
    return record("memory", memory_id, "correct", before, after)


def update_character_with_undo(character_id: str, **fields: Any) -> str:
    from gateway import image_characters

    before = snapshot_character(character_id)
    image_characters.update_character(character_id, **fields)
    after = snapshot_character(character_id)
    return record("character", character_id, "update", before, after)


def update_automation_with_undo(
    sid: str,
    name: str,
    action: str,
    schedule_type: str,
    schedule_value: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> str:
    from gateway import cron

    before = snapshot_automation(sid)
    if not cron.update(
        sid, name, action, schedule_type, schedule_value, metadata=metadata or {}
    ):
        raise UndoNotFound(f"automation schedule not found: {sid}")
    after = snapshot_automation(sid)
    return record("automation", sid, "update", before, after)


def toggle_automation_with_undo(sid: str) -> str:
    from gateway import cron

    before = snapshot_automation(sid)
    result = cron.toggle(sid)
    if result is None:
        raise UndoNotFound(f"automation schedule not found: {sid}")
    after = snapshot_automation(sid)
    return record("automation", sid, "toggle", before, after)


def set_anchor_with_undo(session_id: str, job_id: str) -> str:
    from gateway import image_sessions

    before = snapshot_anchor(session_id)
    image_sessions.set_anchor(session_id, job_id)
    after = snapshot_anchor(session_id)
    return record("image", session_id, "set_anchor", before, after)


def clear_anchor_with_undo(session_id: str) -> str:
    from gateway import image_sessions

    before = snapshot_anchor(session_id)
    image_sessions.clear_anchor(session_id)
    after = snapshot_anchor(session_id)
    return record("image", session_id, "clear_anchor", before, after)
