"""Chat session store — keyed by id, stored as JSON blobs in kitty.db.

This is the Phase C C2 module. The /chats route
(gateway/routes/chats.py) calls into this module instead of reading and
writing data/kitty/chats.json directly. The wire shape is preserved; the
storage substrate changes.

Public API:
  list_chats() -> list[dict]              All chats, most-recently-updated first
  upsert_chat(chat: dict) -> None         Create or replace a chat by id
  delete_chat(chat_id: str) -> bool       Remove a chat by id; True if it existed
"""
from __future__ import annotations

import json
import logging
import sqlite3

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE

logger = logging.getLogger("kitty.chats_store")

CHATS_DB_FILE = KITTY_DB_FILE


def init_db() -> None:
    """Apply pending migrations. Idempotent."""
    kitty_db.migrate(db_file=CHATS_DB_FILE)


def list_chats() -> list[dict]:
    """Return all chats, most-recently-updated first."""
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, payload FROM chats ORDER BY updated_at DESC, id ASC"
        ).fetchall()
    return [_row_to_chat(r) for r in rows]


def upsert_chat(chat: dict) -> None:
    """Create or replace a chat by id. Raises ValueError if 'id' is missing."""
    chat_id = chat.get("id")
    if not chat_id:
        raise ValueError("chat dict must include 'id'")
    payload = json.dumps(chat, ensure_ascii=False)
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO chats (id, payload) VALUES (?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP
            """,
            (chat_id, payload),
        )
        conn.commit()


def delete_chat(chat_id: str) -> bool:
    """Remove a chat by id. Returns True if a row was deleted."""
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        cursor = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
        return cursor.rowcount > 0


def _row_to_chat(row: sqlite3.Row) -> dict:
    return json.loads(row["payload"])
