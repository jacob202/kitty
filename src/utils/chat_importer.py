import json
import sqlite3
from pathlib import Path


class ChatImporter:
    """
    Handles parsing and staging large, exported chat histories from various LLMs
    (ChatGPT, Claude, etc.) into the SQLite staging table for asynchronous profiling.
    """
    def __init__(self, db_path="orange_lab_pka.db"):
        self.db_path = db_path

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
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
        conn.commit()

    def import_chatgpt_export(self, filepath: str) -> int:
        """
        Parses a ChatGPT conversations.json file.
        Returns the number of conversations staged.
        """
        path = Path(filepath).expanduser()
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            return 0

        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)

            conn = sqlite3.connect(self.db_path)
            self._ensure_schema(conn)
            cursor = conn.cursor()

            staged_count = 0
            for convo in data:
                # Extract only user and assistant messages, ignore system/tool noise
                messages = []
                mapping = convo.get("mapping", {})
                for node_id, node in mapping.items():
                    msg = node.get("message")
                    if msg and msg.get("author", {}).get("role") in ["user", "assistant"]:
                        text = ""
                        parts = msg.get("content", {}).get("parts", [])
                        for part in parts:
                            if isinstance(part, str):
                                text += part
                        if text.strip():
                            messages.append({
                                "role": msg["author"]["role"],
                                "content": text.strip()
                            })

                if messages:
                    # Filter out tiny, useless conversations (e.g., "Hi" -> "Hello")
                    if len(json.dumps(messages)) > 500:
                        cursor.execute(
                            "INSERT INTO chat_history_imports (source_llm, raw_content, processed) VALUES (?, ?, 0)",
                            ("ChatGPT", json.dumps(messages))
                        )
                        staged_count += 1

            conn.commit()
            conn.close()
            print(f"[SUCCESS] Staged {staged_count} ChatGPT conversations for profiling.")
            return staged_count

        except Exception as e:
            print(f"[ERROR] Failed to parse ChatGPT export: {e}")
            return 0

    def import_raw_text(self, text_content: str, source: str = "RawText") -> bool:
        """
        Stages a single, raw block of text (like a pasted chat log) for profiling.
        """
        if len(text_content) < 100:
            return False

        try:
            conn = sqlite3.connect(self.db_path)
            self._ensure_schema(conn)
            conn.execute(
                "INSERT INTO chat_history_imports (source_llm, raw_content, processed) VALUES (?, ?, 0)",
                (source, text_content)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[ERROR] Raw text import failed: {e}")
            return False
