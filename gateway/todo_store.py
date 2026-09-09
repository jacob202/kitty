"""Structured Todo Store — model-maintainable task list across turns.

The LLM can create and update a structured task list via POST /todos.
Each item has: content, status (pending/in_progress/completed/deprioritized),
and active_form (present continuous for "currently doing" display).

Public API:
  update(items: list[dict]) -> list[dict]   Replace the entire list
  get() -> list[dict]                       Get current list
  add(content: str) -> dict                 Append one item
  complete(index: int) -> bool              Mark one item done
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.todo_store")


class TodoStoreError(RuntimeError):
    """Raised when a todo operation cannot proceed safely."""

TODO_DB = DATA_DIR / "todos.db"
TODO_DB_FILE = KITTY_DB_FILE
LEGACY_IMPORT_SETTING = "todos_legacy_imported"
VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "deprioritized"})


def init_db() -> None:
    kitty_db.migrate(db_file=TODO_DB_FILE)
    _import_legacy_todos_once()


def update(items: list[dict]) -> list[dict]:
    """Set the todo list, reconciling against what is already there.

    This used to delete every row and re-insert, which handed every item a new
    id on each refresh. Anything holding a todo id — a project's chosen next
    action, a recorded progress note, the completion the user just reported —
    silently pointed at nothing afterwards.

    Items are now matched to existing rows by explicit ``id`` first, then by
    exact content, so a model regenerating the same list keeps the same
    identities. A matched row is updated in place and keeps its id,
    ``created_at``, ``project_id`` and progress note. Only rows the caller
    genuinely dropped are deleted.

    Each item dict: {content, status?, active_form?, id?}
    Returns the new list.
    """
    init_db()
    from gateway import project_store

    if Path(TODO_DB_FILE).resolve() != Path(project_store.PROJECTS_DB_FILE).resolve():
        # Selection protection is only atomic because Projects and Todos share
        # one SQLite transaction. Refuse a split configuration before touching
        # the Project store; silently proceeding would reintroduce the exact
        # selected-todo loss this reconciliation prevents.
        raise TodoStoreError(
            "cannot safely reconcile todos while the todo and project stores are separate databases"
        )
    try:
        project_store.init_db()
    except Exception as exc:
        raise TodoStoreError(
            "cannot reconcile the todo list without reading project selections"
        ) from exc
    now = time.time()

    with kitty_db.connect(TODO_DB_FILE) as conn:
        # Protect the selection snapshot and deletion sweep with the same write
        # transaction. select_todo() takes the same lock and revalidates after
        # acquiring it, so neither ordering can return success with a deleted
        # chosen action.
        conn.execute("BEGIN IMMEDIATE")
        try:
            protected = {
                row["selected_todo_id"]
                for row in conn.execute(
                    "SELECT selected_todo_id FROM projects "
                    "WHERE selected_todo_id IS NOT NULL"
                ).fetchall()
            }
        except sqlite3.Error as exc:
            raise TodoStoreError(
                "cannot reconcile the todo list without reading project selections"
            ) from exc
        existing = conn.execute(
            "SELECT id, content FROM todos ORDER BY sort_order ASC"
        ).fetchall()
        by_id = {row["id"]: row for row in existing}
        unclaimed_by_content: dict[str, list[int]] = {}
        for row in existing:
            unclaimed_by_content.setdefault(row["content"], []).append(row["id"])

        kept: set[int] = set()
        for position, item in enumerate(items):
            status = item.get("status", "pending")
            if status not in VALID_STATUSES:
                status = "pending"
            content = str(item.get("content", ""))
            active_form = str(item.get("active_form", ""))

            matched = _match_existing_todo(item, content, by_id, unclaimed_by_content, kept)
            if matched is None:
                conn.execute(
                    "INSERT INTO todos "
                    "(content, status, active_form, sort_order, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (content, status, active_form, position, now, now),
                )
                continue

            kept.add(matched)
            conn.execute(
                "UPDATE todos SET content = ?, status = ?, active_form = ?, "
                "sort_order = ?, updated_at = ? WHERE id = ?",
                (content, status, active_form, position, now, matched),
            )

        # A todo a project has explicitly selected is not a suggestion, and a
        # regenerated list that omits it is not the user removing it. Deleting
        # it here would silently destroy the chosen action and its progress
        # note — the exact loss this reconciliation exists to prevent. Explicit
        # removal still works: that is `delete_by_id`.
        survivors = [
            row["id"]
            for row in existing
            if row["id"] not in kept and row["id"] in protected
        ]
        dropped = [
            row["id"]
            for row in existing
            if row["id"] not in kept and row["id"] not in protected
        ]
        for todo_id in dropped:
            conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        # A survivor keeps its row but not its old position: incoming items were
        # numbered from zero, so leaving it where it was creates duplicate
        # sort_orders. `complete(index)` addresses rows by position and would
        # then finish every row sharing one. Survivors go after the new list.
        for offset, todo_id in enumerate(survivors):
            conn.execute(
                "UPDATE todos SET sort_order = ?, updated_at = ? WHERE id = ?",
                (len(items) + offset, now, todo_id),
            )
        conn.commit()

    return get()


def _match_existing_todo(
    item: dict,
    content: str,
    by_id: dict[int, sqlite3.Row],
    unclaimed_by_content: dict[str, list[int]],
    kept: set[int],
) -> int | None:
    """Resolve one incoming item to the row it should keep being."""
    raw_id = item.get("id")
    if isinstance(raw_id, int) and not isinstance(raw_id, bool):
        if raw_id in by_id and raw_id not in kept:
            candidates = unclaimed_by_content.get(by_id[raw_id]["content"])
            if candidates and raw_id in candidates:
                candidates.remove(raw_id)
            return raw_id
        # An id the caller invented, or one already used by an earlier item in
        # this same payload, is not identity — fall through to content.

    candidates = unclaimed_by_content.get(content)
    while candidates:
        candidate = candidates.pop(0)
        if candidate not in kept:
            return candidate
    return None


def get() -> list[dict]:
    """Get the current todo list, ordered by sort_order."""
    init_db()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, content, status, active_form, sort_order, progress_note, "
            "project_id, created_at, updated_at FROM todos ORDER BY sort_order ASC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def add(content: str, status: str = "pending", active_form: str = "") -> dict:
    """Append one item to the list."""
    init_db()
    now = time.time()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        # Find max sort_order
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM todos").fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO todos (content, status, active_form, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (content, status, active_form, max_order + 1, now, now),
        )
        conn.commit()
        todo_id = cursor.lastrowid

    with kitty_db.connect(TODO_DB_FILE) as conn:
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_dict(row) if row else {}


def complete(index: int) -> bool:
    """Mark item at sort_order=index as completed."""
    init_db()
    now = time.time()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE todos SET status = 'completed', updated_at = ? WHERE sort_order = ?",
            (now, index),
        )
        conn.commit()
        return cursor.rowcount > 0


def clear() -> None:
    """Remove all todos."""
    init_db()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        conn.execute("DELETE FROM todos")
        conn.commit()


def complete_by_id(todo_id: int) -> bool:
    """Mark item with given DB id as completed."""
    init_db()
    now = time.time()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE todos SET status = 'completed', updated_at = ? WHERE id = ?",
            (now, todo_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def set_progress(todo_id: int, note: str) -> dict | None:
    """Record where the user stopped, without claiming the item is finished.

    "This is where I stopped" is a different statement from "I did this", and
    conflating them loses the only thing that makes the action resumable. An
    item with progress moves to ``in_progress``; clearing the note leaves the
    status alone, because erasing a note is not abandoning the work.
    """
    init_db()
    now = time.time()
    text = note.strip() if isinstance(note, str) else ""
    with kitty_db.connect(TODO_DB_FILE) as conn:
        if text:
            cursor = conn.execute(
                "UPDATE todos SET progress_note = ?, status = 'in_progress', updated_at = ? "
                "WHERE id = ? AND status != 'completed'",
                (text, now, todo_id),
            )
        else:
            cursor = conn.execute(
                "UPDATE todos SET progress_note = NULL, updated_at = ? WHERE id = ?",
                (now, todo_id),
            )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_dict(row) if row else None


def set_project(todo_id: int, project_id: int | None) -> dict | None:
    """Associate one todo with the project it belongs to."""
    init_db()
    now = time.time()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE todos SET project_id = ?, updated_at = ? WHERE id = ?",
            (project_id, now, todo_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_by_id(todo_id: int) -> bool:
    """Remove one todo by DB id."""
    init_db()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_todos_text() -> str:
    """Return current todo list as a formatted string for context injection."""
    todos = get()
    if not todos:
        return ""
    active = [t for t in todos if t["status"] in ("pending", "in_progress")]
    if not active:
        return ""
    status_label = {"pending": "☐", "in_progress": "▶"}
    lines = ["[Current Todos]"]
    for t in active[:8]:
        prefix = status_label.get(t["status"], "☐")
        form = f" ({t['active_form']})" if t.get("active_form") else ""
        lines.append(f"  {prefix} {t['content']}{form}")
    return "\n".join(lines)


def _row_to_dict(row: sqlite3.Row) -> dict:
    # Every caller selects the full row or names these columns explicitly. A
    # missing one is a schema bug and should say so, not quietly read as "no
    # progress recorded" — which is how a lost note looks exactly like a note
    # that was never taken.
    return {
        "id": row["id"],
        "content": row["content"],
        "status": row["status"],
        "active_form": row["active_form"] or "",
        "sort_order": row["sort_order"],
        "progress_note": row["progress_note"],
        "project_id": row["project_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _import_legacy_todos_once() -> None:
    """Copy existing todos from the old DB once without deleting the old file."""
    if not TODO_DB.exists():
        return

    with kitty_db.connect(TODO_DB_FILE) as target:
        imported = target.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (LEGACY_IMPORT_SETTING,),
        ).fetchone()
        if imported:
            return

        target_count = target.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        if target_count > 0:
            _mark_legacy_imported(target, "skipped-target-not-empty")
            return

        try:
            rows = _read_legacy_todos()
        except sqlite3.Error as exc:
            raise RuntimeError(
                "Legacy todo import failed "
                f"from {TODO_DB} to {TODO_DB_FILE}: {exc}"
            ) from exc

        target.executemany(
            """
            INSERT INTO todos (
                id, content, status, active_form, sort_order, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["content"],
                    row["status"],
                    row["active_form"],
                    row["sort_order"],
                    row["created_at"],
                    row["updated_at"],
                )
                for row in rows
            ],
        )
        _mark_legacy_imported(target, str(TODO_DB))


def _read_legacy_todos() -> list[sqlite3.Row]:
    with kitty_db.connect(TODO_DB) as source:
        source.row_factory = sqlite3.Row
        return source.execute(
            """
            SELECT id, content, status, active_form, sort_order, created_at, updated_at
            FROM todos
            ORDER BY sort_order ASC
            """
        ).fetchall()


def _mark_legacy_imported(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (LEGACY_IMPORT_SETTING, value),
    )
