import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

from src.core.db_config import get_db_path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB_PATH = str(get_db_path("profiler"))


class ProfilerEngine:
    """
    Background worker that analyzes raw chat logs staged in `chat_history_imports`.
    Uses Gemini Flash to extract insights and updates `user_profiles` modularly.
    """

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = _DEFAULT_DB_PATH
        self.db_path = db_path
        self._lock = threading.Lock()
        self.is_running = False

    def _ensure_schema(self, conn):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_llm TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                processed INTEGER NOT NULL DEFAULT 0,
                created_at REAL DEFAULT (strftime('%s','now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                insight TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                source_context TEXT,
                created_at REAL DEFAULT (strftime('%s','now'))
            )
            """
        )
        conn.commit()

    def start_background_loop(self, supervisor_ref, interval_seconds=300):
        if self.is_running:
            return
        self.is_running = True

        def loop():
            while self.is_running:
                try:
                    self.process_batch(supervisor_ref, batch_size=5)
                except Exception as e:
                    logger.error(f"Error in loop: {e}")
                time.sleep(interval_seconds)

        t = threading.Thread(target=loop, daemon=True, name="profiler-engine")
        t.start()

    def process_batch(self, supervisor_ref, batch_size=5):
        """
        Pulls a batch of unprocessed chats and sends them to the LLM for profiling.
        """
        try:
            with open("config/kitty_settings.json") as f:
                settings = json.load(f)
                if not settings.get("features", {}).get("chat_profiling", {}).get("enabled", True):
                    return 0
        except Exception:
            pass

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                self._ensure_schema(conn)
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT id, raw_content FROM chat_history_imports WHERE processed = 0 LIMIT ?",
                    (batch_size,),
                )
                rows = cursor.fetchall()

                if not rows:
                    return 0

                processed_count = 0
                for row_id, content in rows:
                    logger.info(f"Analyzing chat batch {row_id}...")

                    if len(content) > 100000:
                        content = content[-100000:]

                    prompt = (
                        "You are a psychological and behavioral profiling expert analyzing a user's chat history.\n"
                        "Extract 1 to 3 HIGH-VALUE insights about the user. Do not state the obvious. Look for deep patterns.\n\n"
                        "Categories must be exactly one of: 'psychology', 'coding_style', 'interests', 'communication_style', 'fallacies'.\n\n"
                        "Return ONLY a JSON list of objects:\n"
                        '[{"category": "coding_style", "insight": "Prefers functional over OOP, hates boilerplate.", "confidence": 0.9}]\n\n'
                        f"CHAT HISTORY:\n{content}"
                    )

                    try:
                        raw_response = supervisor_ref._call_openrouter(
                            prompt,
                            system_prompt="You extract JSON profiles.",
                            model=supervisor_ref.config.get(
                                "flash_model", "google/gemini-2.0-flash-001"
                            ),
                        )

                        if "```json" in raw_response:
                            raw_response = raw_response.split("```json")[1].split("```")[0]
                        elif "```" in raw_response:
                            raw_response = raw_response.split("```")[1].split("```")[0]

                        insights = json.loads(raw_response.strip())

                        for ins in insights:
                            category = ins.get("category", "interests")
                            insight = ins.get("insight", "")
                            confidence = ins.get("confidence", 0.5)

                            if insight and len(insight) > 10:
                                cursor.execute(
                                    "INSERT INTO user_profiles (category, insight, confidence, source_context) VALUES (?, ?, ?, ?)",
                                    (category, insight, float(confidence), f"ImportID_{row_id}"),
                                )

                        cursor.execute(
                            "UPDATE chat_history_imports SET processed = 1 WHERE id = ?", (row_id,)
                        )
                        conn.commit()
                        processed_count += 1

                    except Exception as e:
                        logger.error(f"Failed to process row {row_id}: {e}")
                        cursor.execute(
                            "UPDATE chat_history_imports SET processed = 1 WHERE id = ?", (row_id,)
                        )
                        conn.commit()

                return processed_count
            finally:
                conn.close()
