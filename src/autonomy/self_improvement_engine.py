"""
SelfImprovementEngine — central hub for Kitty's self-improvement loop.

Responsibilities:
  1. Record every interaction with quality signals.
  2. Write validated interactions as JSONL training examples.
  3. Surface improvement metrics and history.

Training format: OpenAI-style messages JSONL so examples are model-agnostic.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from src.core.db_config import get_db_path

logger = logging.getLogger(__name__)

_TRAINING_DIR = Path("data/training")
_TRAINING_FILE = _TRAINING_DIR / "interactions.jsonl"
_DB_PATH = get_db_path("self_improvement")


def _weak_response(text: str) -> bool:
    """Heuristic: short or apologetic responses aren't worth training on."""
    if not text or len(text.strip()) < 40:
        return True
    low = text.lower()
    weak_phrases = ["i don't know", "i'm not sure", "i cannot", "i can't", "i apologize", "sorry,"]
    return any(p in low for p in weak_phrases)


class SelfImprovementEngine:
    """
    Singleton. Thread-safe. Wired into Supervisor._finish().
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._db_lock = threading.Lock()
        _TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── DB setup ───────────────────────────────────────────────────────────────

    def _init_db(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          TEXT NOT NULL,
                    query       TEXT NOT NULL,
                    result_len  INTEGER NOT NULL,
                    tag         TEXT,
                    elapsed_s   REAL,
                    was_skill_hit INTEGER DEFAULT 0,
                    quality     TEXT DEFAULT 'unknown',
                    wrote_training INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS improvement_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts          TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    detail      TEXT
                );
            """)

    def _conn(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=5)

    # ── Public API ─────────────────────────────────────────────────────────────

    def record_interaction(
        self,
        query: str,
        result: str,
        tag: str = "unknown",
        elapsed_s: float = 0.0,
        was_skill_hit: bool = False,
    ):
        """Called after every run(). Logs the interaction and writes training data if good."""
        quality = "good" if not _weak_response(result) else "weak"
        wrote = 0
        if quality == "good":
            wrote = int(self._write_training_example(query, result))

        ts = datetime.now().isoformat()
        try:
            with self._db_lock:
                with self._conn() as c:
                    c.execute(
                        "INSERT INTO interactions "
                        "(ts, query, result_len, tag, elapsed_s, was_skill_hit, quality, wrote_training) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (ts, query[:200], len(result), tag, elapsed_s, int(was_skill_hit), quality, wrote),
                    )
        except Exception as e:
            logger.error(f"SIE record_interaction: {e}")

    def log_event(self, event_type: str, detail: str = ""):
        """Log a named improvement event (skill learned, self-heal fired, etc.)."""
        ts = datetime.now().isoformat()
        try:
            with self._db_lock:
                with self._conn() as c:
                    c.execute(
                        "INSERT INTO improvement_log (ts, event_type, detail) VALUES (?, ?, ?)",
                        (ts, event_type, detail[:500]),
                    )
        except Exception as e:
            logger.error(f"SIE log_event: {e}")

    def get_stats(self) -> dict:
        """Return aggregate improvement metrics for status display."""
        try:
            with self._conn() as c:
                total = c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
                good = c.execute(
                    "SELECT COUNT(*) FROM interactions WHERE quality='good'"
                ).fetchone()[0]
                training_written = c.execute(
                    "SELECT COUNT(*) FROM interactions WHERE wrote_training=1"
                ).fetchone()[0]
                skill_hits = c.execute(
                    "SELECT COUNT(*) FROM interactions WHERE was_skill_hit=1"
                ).fetchone()[0]
                recent_events = c.execute(
                    "SELECT event_type, detail FROM improvement_log ORDER BY id DESC LIMIT 5"
                ).fetchall()
            return {
                "total_interactions": total,
                "good_responses": good,
                "quality_rate": round(good / total, 2) if total else 0,
                "training_examples_written": training_written,
                "skill_cache_hits": skill_hits,
                "recent_events": [{"type": e[0], "detail": e[1]} for e in recent_events],
            }
        except Exception as e:
            logger.error(f"SIE get_stats: {e}")
            return {}

    def load_corrections(self) -> list[dict]:
        """Pull user corrections from corrections.db for inclusion in training."""
        corrections_db = Path("data/corrections.db")
        if not corrections_db.exists():
            return []
        try:
            with sqlite3.connect(str(corrections_db)) as c:
                rows = c.execute(
                    "SELECT original_query, correction_text FROM corrections "
                    "WHERE applied_count > 0 ORDER BY id DESC LIMIT 50"
                ).fetchall()
            return [{"query": r[0], "correction": r[1]} for r in rows]
        except Exception as e:
            logger.error(f"SIE load_corrections: {e}")
            return []

    def flush_corrections_to_training(self) -> int:
        """Write unwritten correction pairs as training examples. Returns count written."""
        corrections = self.load_corrections()
        written = 0
        for item in corrections:
            # Format as a correction-style training example
            result = (
                f"[Correction noted] {item['correction']}\n"
                "I'll apply this understanding going forward."
            )
            if self._write_training_example(item["query"], result, source="correction"):
                written += 1
        if written:
            self.log_event("corrections_flushed", f"{written} correction examples written")
        return written

    # ── Private ────────────────────────────────────────────────────────────────

    def _write_training_example(self, query: str, result: str, source: str = "interaction") -> bool:
        """Append one JSONL training example. Returns True if written."""
        if _weak_response(result):
            return False
        example = {
            "messages": [
                {"role": "user", "content": query.strip()},
                {"role": "assistant", "content": result.strip()[:2000]},
            ],
            "metadata": {
                "source": source,
                "ts": datetime.now().isoformat(),
            },
        }
        try:
            with self._db_lock:
                with open(_TRAINING_FILE, "a") as f:
                    f.write(json.dumps(example) + "\n")
            return True
        except Exception as e:
            logger.error(f"SIE write_training_example: {e}")
            return False
