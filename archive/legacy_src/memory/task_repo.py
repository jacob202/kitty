"""
Task repository — SQLite table for tasks.
"""
import sqlite3, os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Always resolve relative to project root
DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "kitty.db")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def init_task_db(conn=None):
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT CHECK(status IN ('open','done','parked','blocked')) NOT NULL DEFAULT 'open',
            project TEXT,
            source_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """)
    conn.commit()
    if close:
        conn.close()


def add_task(title: str, project: Optional[str] = None, source_message: Optional[str] = None) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (title, project, source_message, created_at) VALUES (?, ?, ?, ?)",
        (title, project, source_message, datetime.now().isoformat())
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def mark_done(title_or_id, conn=None) -> Dict:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    # Try by id first
    row = None
    if isinstance(title_or_id, int):
        row = conn.execute("SELECT id, title, status FROM tasks WHERE id = ? AND status = 'open'", (title_or_id,)).fetchone()
    if row is None:
        # Try by title substring match
        row = conn.execute(
            "SELECT id, title, status FROM tasks WHERE title LIKE ? AND status = 'open' ORDER BY id LIMIT 1",
            (f"%{title_or_id}%",)
        ).fetchone()
    if row is None:
        next_open = get_next_task(conn)
        if close:
            conn.close()
        return {"found": False, "task": None, "next_open": next_open}
    task_id, title, status = row
    conn.execute(
        "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), task_id)
    )
    conn.commit()
    task = {"id": task_id, "title": title, "status": "done"}
    next_open = get_next_task(conn)
    if close:
        conn.close()
    return {"found": True, "task": task, "next_open": next_open}


def get_open_tasks(conn=None) -> List[Dict]:
    close = False
    if conn is None:
        conn = _get_conn()
        close = True
    rows = conn.execute("SELECT id, title, status, project FROM tasks WHERE status = 'open' ORDER BY id").fetchall()
    result = [{"id": r[0], "title": r[1], "status": r[2], "project": r[3]} for r in rows]
    if close:
        conn.close()
    return result


def get_next_task(conn=None) -> Optional[Dict]:
    tasks = get_open_tasks(conn)
    return tasks[0] if tasks else None


def get_next_action() -> str:
    nxt = get_next_task()
    return nxt["title"] if nxt else "No open tasks"
