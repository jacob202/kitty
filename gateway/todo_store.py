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

from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.todo_store")

TODO_DB = DATA_DIR / "todos.db"
TODO_DB_FILE = KITTY_DB_FILE
LEGACY_IMPORT_SETTING = "todos_legacy_imported"
VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "deprioritized"})


def init_db() -> None:
    kitty_db.migrate(db_file=TODO_DB_FILE)
    _import_legacy_todos_once()


def update(items: list[dict]) -> list[dict]:
    """Replace the entire todo list with a new set of items.

    Each item dict: {content, status?, active_form?}
    Returns the new list with IDs assigned.
    """
    init_db()
    now = time.time()

    with kitty_db.connect(TODO_DB_FILE) as conn:
        conn.execute("DELETE FROM todos")
        for i, item in enumerate(items):
            status = item.get("status", "pending")
            if status not in VALID_STATUSES:
                status = "pending"
            conn.execute(
                "INSERT INTO todos (content, status, active_form, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(item.get("content", "")),
                    status,
                    str(item.get("active_form", "")),
                    i,
                    now,
                    now,
                ),
            )
        conn.commit()

    return get()


def get() -> list[dict]:
    """Get the current todo list, ordered by sort_order."""
    init_db()
    with kitty_db.connect(TODO_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, content, status, active_form, sort_order, created_at, updated_at "
            "FROM todos ORDER BY sort_order ASC"
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
    return {
        "id": row["id"],
        "content": row["content"],
        "status": row["status"],
        "active_form": row["active_form"] or "",
        "sort_order": row["sort_order"],
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
    with sqlite3.connect(TODO_DB) as source:
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
