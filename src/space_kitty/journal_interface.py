"""
Frictionless conversation logging and pattern detection.
Logs invisibly, detects loops, planning marathons, emotional compression.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


class JournalInterface:
    """Log conversations and detect behavioral patterns."""

    def __init__(self, db_path: str = "data/journal.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        """Initialize journal database."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT
            )
        """)
        conn.commit()

    def log(self, role: str, content: str):
        """Log a message. Invisible to user."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO journal (timestamp, role, content) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), role, content),
        )
        conn.commit()

    def get_recent(self, limit: int = 10) -> list[dict[str, str]]:
        """Get recent journal entries."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT timestamp, role, content FROM journal ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"timestamp": r[0], "role": r[1], "content": r[2]}
            for r in reversed(rows)
        ]

    def detect_patterns(self) -> list[str]:
        """Detect behavioral patterns in conversation."""
        recent = self.get_recent(limit=50)
        patterns = []

        user_msgs = [e for e in recent if e["role"] == "user"]
        assistant_msgs = [e for e in recent if e["role"] == "assistant"]
        user_lower = [e["content"].lower() for e in user_msgs]

        # Research loop: multiple research requests without action
        research_count = sum(1 for c in user_lower if "research" in c)
        if research_count > 3:
            patterns.append("research_loop")

        # Planning marathon: many planning messages
        planning_count = sum(
            1 for c in user_lower
            if any(w in c for w in ["plan", "strategy", "design"])
        )
        if planning_count > 5:
            patterns.append("planning_marathon")

        # Emotional compression: short responses in sequence
        assistant_recent = assistant_msgs[-10:]
        if len(assistant_recent) > 3:
            short_responses = sum(1 for e in assistant_recent if len(e["content"]) < 30)
            if short_responses > 2:
                patterns.append("emotional_compression")

        # Execution gap: plan but no implementation
        has_planning = any("plan" in c for c in user_lower)
        has_implementation = any(
            any(w in c for w in ["write", "implement", "fix"]) for c in user_lower
        )
        if has_planning and not has_implementation:
            patterns.append("execution_gap")

        return patterns

    def get_summary(self, limit: int = 20) -> str:
        """Get readable summary of recent conversation."""
        recent = self.get_recent(limit=limit)
        if not recent:
            return "No conversation history"

        summary_lines = []
        for entry in recent:
            role_label = "You" if entry["role"] == "user" else "Kitty"
            content_preview = entry["content"][:60]
            summary_lines.append(f"{role_label}: {content_preview}")

        return "\n".join(summary_lines)

    def search(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        """Search journal for entries containing query."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT timestamp, role, content FROM journal WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [
            {"timestamp": r[0], "role": r[1], "content": r[2]}
            for r in rows
        ]
