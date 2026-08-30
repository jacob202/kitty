"""Chat session store — keyed by id, stored as JSON blobs in kitty.db.

The /chats route (gateway/routes/chats.py) calls into this module instead
of reading and writing data/kitty/chats.json directly. The wire shape is
preserved; the storage substrate changes.

Public API:
  list_chats() -> list[dict]              All chats, most-recently-updated first
  upsert_chat(chat: dict) -> None         Create or replace a chat by id
  delete_chat(chat_id: str) -> bool       Remove a chat by id; True if it existed

Legacy import: on first access, if data/kitty/chats.json exists and the
chats table is empty, the JSON contents are imported into kitty.db. The
JSON file is never deleted. The import marker is stored in app_settings
key 'chats_legacy_imported' with a value describing the outcome.

Rollback (documented escape hatch): if the SQLite layer needs to be
abandoned, the JSON file is still the source of truth. To roll back:
  1. DROP TABLE chats;
  2. DELETE FROM app_settings WHERE key = 'chats_legacy_imported';
  3. DELETE FROM schema_migrations WHERE name = '004_chats.sql';
  4. Re-run the gateway; migrate re-applies 004_chats.sql (which is
     CREATE TABLE IF NOT EXISTS chats ...), then the import rebuilds
     the table from the JSON file.
This is verified by TestLegacyImport.test_rollback_re_imports_from_intact_json.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time

from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.chats_store")

CHATS_DB_FILE = KITTY_DB_FILE
LEGACY_CHATS_FILE = DATA_DIR / "kitty" / "chats.json"
LEGACY_IMPORT_SETTING = "chats_legacy_imported"


class ChatNotFoundError(ValueError):
    """Raised when a requested chat does not exist."""


def init_db() -> None:
    """Apply pending migrations and run the one-time legacy import. Idempotent."""
    kitty_db.migrate(db_file=CHATS_DB_FILE)
    _import_legacy_chats_once()


def list_chats() -> list[dict]:
    """Return all chats, most-recently-updated first."""
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, payload, objective FROM chats ORDER BY updated_at DESC, id ASC"
        ).fetchall()
    return [_row_to_chat(r) for r in rows]


def get_chat(chat_id: str) -> dict | None:
    """Return one chat by id, or ``None`` when it does not exist."""
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        row = conn.execute(
            "SELECT id, payload, objective FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
    return _row_to_chat(row) if row is not None else None


def upsert_chat(chat: dict) -> None:
    """Create or replace a chat by id. Raises ValueError if 'id' is missing."""
    chat_id = chat.get("id")
    if not chat_id:
        raise ValueError("chat dict must include 'id'")
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        _upsert_chat_raw(conn, chat)
        conn.commit()


def delete_chat(chat_id: str) -> bool:
    """Remove a chat by id. Returns True if a row was deleted."""
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        cursor = conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
        return cursor.rowcount > 0


def _upsert_chat_raw(conn: sqlite3.Connection, chat: dict) -> None:
    """Insert or replace a chat using an existing connection. No init_db call."""
    payload_chat = dict(chat)
    objective_present = "objective" in payload_chat
    objective = payload_chat.pop("objective", None)
    if objective_present:
        _validate_objective(objective)
    payload = json.dumps(payload_chat, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO chats (id, payload) VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET
            payload = excluded.payload,
            updated_at = CURRENT_TIMESTAMP
        """,
        (chat["id"], payload),
    )
    if objective_present:
        conn.execute(
            "UPDATE chats SET objective = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (objective, chat["id"]),
        )


def _row_to_chat(row: sqlite3.Row) -> dict:
    chat = json.loads(row["payload"])
    # Old payloads may contain objective; the normalized column is authoritative.
    chat.pop("objective", None)
    obj = row["objective"] if "objective" in row.keys() else None
    if obj is not None:
        chat["objective"] = obj
    return chat


def patch_objective(chat_id: str, objective: str | None) -> dict:
    """Set or clear a chat's objective. Returns the updated chat dict.

    Args:
        chat_id: The chat to update.
        objective: New objective text, or None to clear it.

    Raises:
        ValueError: If the chat does not exist.
    """
    _validate_objective(objective)
    init_db()
    with kitty_db.connect(CHATS_DB_FILE) as conn:
        cursor = conn.execute(
            "UPDATE chats SET objective = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (objective, chat_id),
        )
        if cursor.rowcount == 0:
            raise ChatNotFoundError(f"chat {chat_id!r} does not exist")
        conn.execute(
            "UPDATE chat_conversations SET objective = ?, updated_at = ? WHERE id = ?",
            (objective, time.time(), chat_id),
        )
        row = conn.execute(
            "SELECT id, payload, objective FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        conn.commit()
        return _row_to_chat(row)


def _validate_objective(objective: object) -> None:
    if objective is not None and not isinstance(objective, str):
        raise ValueError("objective must be a string or null")
    if isinstance(objective, str) and len(objective) > 500:
        raise ValueError(f"objective must be at most 500 characters, got {len(objective)}")


def _import_legacy_chats_once() -> None:
    """Copy chats from the legacy JSON file once. The JSON file is never deleted."""
    with kitty_db.connect(CHATS_DB_FILE) as target:
        if _already_imported(target):
            return
        target_count = target.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
        if target_count > 0:
            _mark_legacy_imported(target, "skipped-target-not-empty")
            return
        if not LEGACY_CHATS_FILE.exists():
            _mark_legacy_imported(target, "no-source-file")
            return
        try:
            chats = _read_legacy_chats()
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Legacy chats import failed from {LEGACY_CHATS_FILE}: {exc}"
            ) from exc
        for chat in chats:
            _upsert_chat_raw(target, chat)
        _mark_legacy_imported(target, str(LEGACY_CHATS_FILE))


def _already_imported(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (LEGACY_IMPORT_SETTING,),
    ).fetchone()
    return row is not None


def _read_legacy_chats() -> list[dict]:
    text = LEGACY_CHATS_FILE.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(
            f"Expected JSON list in {LEGACY_CHATS_FILE}, "
            f"got {type(data).__name__}"
        )
    return data


def _mark_legacy_imported(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (LEGACY_IMPORT_SETTING, value),
    )
