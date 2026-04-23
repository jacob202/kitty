"""Mem0 wrapper with Pre/PostCompact hooks for session memory management."""

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Mem0Store:
    """
    Hybrid memory store with auto-compaction hooks.
    Falls back gracefully if mem0 is not installed.
    """

    def __init__(
        self,
        user_id: str = "primary_user",
        data_dir: str | None = None,
        auto_compact: bool = True,
        compact_after_interactions: int = 50,
        compact_older_than_days: int = 7,
    ):
        self.user_id = user_id
        self.data_dir = Path(data_dir) if data_dir else Path("data/memory")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoint_db = self.data_dir / "session_checkpoints.db"
        self._memory = self._init_memory()

        # Auto-compaction settings
        self.auto_compact = auto_compact
        self.compact_after_interactions = compact_after_interactions
        self.compact_older_than_days = compact_older_than_days
        self._interaction_count = 0
        self._last_compaction = time.time()
        self._local_history: list[dict] = []  # Local history when mem0 not available

        # Initialize checkpoint database
        self._init_checkpoint_db()

    def _init_checkpoint_db(self):
        """Initialize the checkpoint database schema."""
        with sqlite3.connect(self._checkpoint_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT,
                    interaction_count INTEGER,
                    data TEXT,
                    compressed BOOLEAN DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compaction_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    interactions_archived INTEGER,
                    checkpoint_id INTEGER,
                    summary TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_session
                ON checkpoints(session_id)
            """)
            conn.commit()

    def _init_memory(self):
        try:
            from mem0 import Memory

            config = {
                "llm": {
                    "provider": "ollama",
                    "config": {"model": "llama3.2:3b", "ollama_base_url": "http://localhost:11434"},
                },
                "history_db_path": str(self.data_dir / "mem0_history.db"),
            }
            return Memory.from_config(config)
        except ImportError:
            logger.warning("mem0 not installed; using stub memory")
            return None

    def _should_compact(self) -> bool:
        """Check if compaction should run based on thresholds."""
        if not self.auto_compact:
            return False
        if self._interaction_count >= self.compact_after_interactions:
            return True
        return False

    def _compact_old_memories(self) -> dict[str, Any]:
        """
        Compact old memories into dense summaries.
        Returns compaction statistics.
        """
        stats = {"archived": 0, "summaries_created": 0, "checkpoint_id": None}

        if self._memory is None:
            return stats

        try:
            # Get old interactions (simplified - in production would query by date)
            (
                datetime.now() - timedelta(days=self.compact_older_than_days)
            ).isoformat()

            # Archive current session to checkpoint
            session_history = self._get_recent_history(limit=self.compact_after_interactions)
            checkpoint_id = self._create_checkpoint(session_history)
            stats["checkpoint_id"] = checkpoint_id
            stats["archived"] = len(session_history)

            # Generate summary of archived interactions
            if session_history:
                summary = self._generate_summary(session_history)
                self._store_compaction_log(checkpoint_id, len(session_history), summary)
                stats["summaries_created"] = 1

            # Reset interaction counter and local history
            self._interaction_count = 0
            self._last_compaction = time.time()
            self._local_history = []  # Clear local history after checkpoint

            logger.info(f"Compacted {stats['archived']} interactions to checkpoint {checkpoint_id}")
            return stats

        except Exception as e:
            logger.error(f"Compaction error: {e}")
            return stats

    def _get_recent_history(self, limit: int = 50) -> list[dict]:
        """Get recent interactions from memory or local history."""
        # Use local history if mem0 is not available
        if self._memory is None:
            return self._local_history[-limit:] if self._local_history else []
        try:
            # Query recent memories
            results = self._memory.get_all(user_id=self.user_id, limit=limit)
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def _create_checkpoint(self, session_history: list[dict]) -> int:
        """Create a checkpoint and return its ID."""
        session_id = hashlib.sha256(f"{self.user_id}:{time.time()}".encode()).hexdigest()[:16]

        with sqlite3.connect(self._checkpoint_db) as conn:
            cur = conn.execute(
                """INSERT INTO checkpoints (session_id, interaction_count, data)
                   VALUES (?, ?, ?)""",
                (session_id, len(session_history), json.dumps(session_history)),
            )
            conn.commit()
            return cur.lastrowid or 0

    def _generate_summary(self, session_history: list[dict]) -> str:
        """Generate a dense summary of session history."""
        # Simplified summary - in production would use LLM
        topics = set()
        for interaction in session_history:
            # Extract key topics (simplified)
            text = json.dumps(interaction).lower()
            if "code" in text or "python" in text:
                topics.add("coding")
            if "error" in text or "bug" in text:
                topics.add("debugging")
            if "file" in text or "directory" in text:
                topics.add("file_operations")

        summary = f"Session covered: {', '.join(topics) if topics else 'general topics'}"
        return summary

    def _store_compaction_log(self, checkpoint_id: int, count: int, summary: str):
        """Store compaction log entry."""
        with sqlite3.connect(self._checkpoint_db) as conn:
            conn.execute(
                """INSERT INTO compaction_log (interactions_archived, checkpoint_id, summary)
                   VALUES (?, ?, ?)""",
                (count, checkpoint_id, summary),
            )
            conn.commit()

    def get_checkpoints(self, limit: int = 10) -> list[dict]:
        """Get recent session checkpoints."""
        with sqlite3.connect(self._checkpoint_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, timestamp, session_id, interaction_count, compressed
                   FROM checkpoints ORDER BY timestamp DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_checkpoint_data(self, checkpoint_id: int) -> list[dict] | None:
        """Retrieve full data from a checkpoint."""
        with sqlite3.connect(self._checkpoint_db) as conn:
            row = conn.execute(
                "SELECT data FROM checkpoints WHERE id = ?", (checkpoint_id,)
            ).fetchone()
            if row:
                return json.loads(row[0])
        return None

    def restore_from_checkpoint(self, checkpoint_id: int) -> bool:
        """Restore memory state from a checkpoint."""
        data = self.get_checkpoint_data(checkpoint_id)
        if data is None:
            return False

        # Restore to memory (simplified - would need mem0 bulk add)
        for item in data:
            if isinstance(item, dict):
                user_msg = item.get("user", "")
                assistant_msg = item.get("assistant", "")
                if user_msg or assistant_msg:
                    self.add_interaction(user_msg, assistant_msg, item.get("metadata"))

        return True

    def pre_compact_hook(self, session_history: list[dict]) -> Path:
        """Save full session before context wipe."""
        checkpoint_id = self._create_checkpoint(session_history)
        logger.info(f"Pre-compact checkpoint created: {checkpoint_id}")
        return self._checkpoint_db

    def post_compact_hook(self) -> str:
        """Return dense core memory string for prompt injection."""
        if self._memory is None:
            return ""
        try:
            results = self._memory.search("critical session context", user_id=self.user_id, limit=3)
            lines = [f"- {m['memory']}" for m in results.get("results", [])]
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"post_compact_hook error: {e}")
            return ""

    def add_interaction(self, user_msg: str, assistant_msg: str, metadata: dict | None = None):
        """Add an interaction to memory with auto-compaction support."""
        self._interaction_count += 1

        # Always store in local history for checkpointing
        self._local_history.append(
            {
                "user": user_msg,
                "assistant": assistant_msg,
                "metadata": metadata or {},
                "timestamp": time.time(),
            }
        )

        if self._memory is None:
            # Still track interactions for checkpointing even without mem0
            if self._should_compact():
                self._compact_old_memories()
            return
        try:
            self._memory.add(
                f"User: {user_msg}\nAssistant: {assistant_msg}",
                user_id=self.user_id,
                metadata=metadata or {},
            )
            # Trigger auto-compaction if needed
            if self._should_compact():
                self._compact_old_memories()
        except Exception as e:
            logger.error(f"add_interaction error: {e}")

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if self._memory is None:
            return []
        try:
            r = self._memory.search(query, user_id=self.user_id, limit=limit)
            return r.get("results", [])
        except Exception as e:
            logger.error(f"search error: {e}")
            return []
