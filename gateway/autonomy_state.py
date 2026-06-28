"""Autonomy State Layer for Kitty.

Provides persistent memory of 'thinking' and tool execution history
across long reasoning cycles (10+ turns).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.autonomy_state")
STATE_DB = DATA_DIR / "autonomy_state.db"

def init_db():
    """Initialize the autonomy state database."""
    with sqlite3.connect(STATE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS autonomy_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT,
                status TEXT DEFAULT 'active', -- active, completed, failed
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS autonomy_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                turn_index INTEGER,
                role TEXT, -- assistant, tool, system, user
                content TEXT,
                thinking TEXT,
                tool_name TEXT,
                tool_args TEXT,
                tool_result TEXT,
                created_at REAL,
                FOREIGN KEY(session_id) REFERENCES autonomy_sessions(id)
            )
        """)
        conn.commit()

class AutonomyState:
    def __init__(self, session_id: Optional[int] = None):
        init_db()
        self.session_id = session_id
        self.current_turn = 0

        if self.session_id:
            # Resume existing session
            with sqlite3.connect(STATE_DB) as conn:
                row = conn.execute("SELECT MAX(turn_index) FROM autonomy_steps WHERE session_id = ?", (self.session_id,)).fetchone()
                self.current_turn = (row[0] or 0) + 1

    @classmethod
    def start_new(cls, goal: str) -> AutonomyState:
        """Start a new autonomy session."""
        now = time.time()
        with sqlite3.connect(STATE_DB) as conn:
            cursor = conn.execute(
                "INSERT INTO autonomy_sessions (goal, created_at, updated_at) VALUES (?, ?, ?)",
                (goal, now, now)
            )
            session_id = cursor.lastrowid
            conn.commit()
        return cls(session_id=session_id)

    def record_step(self, role: str, content: str = "", thinking: str = "",
                    tool_name: str | None = None, tool_args: Any = None, tool_result: str | None = None):
        """Record a single step in the autonomy loop."""
        if not self.session_id:
            logger.warning("No session_id set for AutonomyState. Step not recorded.")
            return

        now = time.time()
        with sqlite3.connect(STATE_DB) as conn:
            conn.execute("""
                INSERT INTO autonomy_steps (session_id, turn_index, role, content, thinking, tool_name, tool_args, tool_result, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.session_id, self.current_turn, role, content, thinking,
                tool_name, json.dumps(tool_args) if tool_args else None, tool_result, now
            ))
            conn.execute("UPDATE autonomy_sessions SET updated_at = ? WHERE id = ?", (now, self.session_id))
            conn.commit()

        self.current_turn += 1

    def get_history(self) -> List[Dict]:
        """Fetch the full history of the current session."""
        if not self.session_id:
            return []

        with sqlite3.connect(STATE_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM autonomy_steps WHERE session_id = ? ORDER BY turn_index ASC",
                (self.session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def finish(self, status: str = 'completed'):
        """Mark the session as finished."""
        if not self.session_id:
            return

        now = time.time()
        with sqlite3.connect(STATE_DB) as conn:
            conn.execute("UPDATE autonomy_sessions SET status = ?, updated_at = ? WHERE id = ?", (status, now, self.session_id))
            conn.commit()

if __name__ == "__main__":
    # Quick test
    state = AutonomyState.start_new("Test Goal")
    state.record_step("user", "Hello")
    state.record_step("assistant", "Hi there", thinking="I should say hi")
    print(f"Session {state.session_id} history: {len(state.get_history())} steps.")
    state.finish()
