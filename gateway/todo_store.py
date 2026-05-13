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

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.todo_store")

TODO_DB = DATA_DIR / "todos.db"
VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "deprioritized"})


def init_db() -> None:
    TODO_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(TODO_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                active_form TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.commit()


def update(items: list[dict]) -> list[dict]:
    """Replace the entire todo list with a new set of items.

    Each item dict: {content, status?, active_form?}
    Returns the new list with IDs assigned.
    """
    init_db()
    now = time.time()

    with sqlite3.connect(TODO_DB) as conn:
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
    with sqlite3.connect(TODO_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, content, status, active_form, sort_order, created_at, updated_at "
            "FROM todos ORDER BY sort_order ASC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def add(content: str, status: str = "pending", active_form: str = "") -> dict:
    """Append one item to the list."""
    init_db()
    now = time.time()
    with sqlite3.connect(TODO_DB) as conn:
        # Find max sort_order
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM todos").fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO todos (content, status, active_form, sort_order, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (content, status, active_form, max_order + 1, now, now),
        )
        conn.commit()
        todo_id = cursor.lastrowid

    with sqlite3.connect(TODO_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return _row_to_dict(row) if row else {}


def complete(index: int) -> bool:
    """Mark item at sort_order=index as completed."""
    init_db()
    now = time.time()
    with sqlite3.connect(TODO_DB) as conn:
        cursor = conn.execute(
            "UPDATE todos SET status = 'completed', updated_at = ? WHERE sort_order = ?",
            (now, index),
        )
        conn.commit()
        return cursor.rowcount > 0


def clear() -> None:
    """Remove all todos."""
    init_db()
    with sqlite3.connect(TODO_DB) as conn:
        conn.execute("DELETE FROM todos")
        conn.commit()


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
