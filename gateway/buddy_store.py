"""Buddy state persistence — single-row store in kitty.db.

Public API:
  get_state() -> dict            Read the current buddy state row.
  save_state(state: dict) -> None  Write (upsert) the buddy state row.
  init_db() -> None              Apply pending migrations + one-time legacy import.

Legacy import: on first access, if data/kitty/buddy_state.json exists and the
buddy_state table is empty, its contents are imported into kitty.db. The JSON
file is never deleted.

Rollback (documented escape hatch): if the SQLite layer needs to be abandoned,
the JSON file is still readable. To roll back:
  1. DROP TABLE buddy_state;
  2. DELETE FROM app_settings WHERE key = 'buddy_state_legacy_imported';
  3. DELETE FROM schema_migrations WHERE name = '006_buddy_state.sql';
  4. Re-run the gateway; the migration re-applies 006_buddy_state.sql and
     the import rebuilds the table from the JSON file.
This is verified by test_buddy_store.TestLegacyImport.test_rollback_re_imports_from_json.
"""
from __future__ import annotations

import json
import logging

from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.buddy_store")

LEGACY_STATE_FILE = DATA_DIR / "kitty" / "buddy_state.json"
LEGACY_IMPORT_SETTING = "buddy_state_legacy_imported"

_DEFAULTS: dict = {
    "mood": "idle",
    "energy": 100,
    "session_turns": 0,
    "total_turns": 0,
    "last_active_ts": 0.0,
    "drift_count": 0,
}


def init_db() -> None:
    """Apply pending migrations and run the one-time legacy import. Idempotent."""
    kitty_db.migrate(db_file=KITTY_DB_FILE)
    _import_legacy_state_once()


def get_state() -> dict:
    """Return the buddy state dict. Returns defaults if the table is empty."""
    init_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute("SELECT * FROM buddy_state WHERE id = 1").fetchone()
    if row is None:
        return dict(_DEFAULTS)
    return {
        "mood": row["mood"],
        "energy": row["energy"],
        "session_turns": row["session_turns"],
        "total_turns": row["total_turns"],
        "last_active_ts": row["last_active_ts"],
        "drift_count": row["drift_count"],
    }


def save_state(state: dict) -> None:
    """Upsert the buddy state row. Only the known columns are written."""
    init_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO buddy_state
                (id, mood, energy, session_turns, total_turns, last_active_ts, drift_count, updated_at)
            VALUES (1, :mood, :energy, :session_turns, :total_turns, :last_active_ts, :drift_count,
                    CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                mood           = excluded.mood,
                energy         = excluded.energy,
                session_turns  = excluded.session_turns,
                total_turns    = excluded.total_turns,
                last_active_ts = excluded.last_active_ts,
                drift_count    = excluded.drift_count,
                updated_at     = excluded.updated_at
            """,
            {
                "mood": state.get("mood", _DEFAULTS["mood"]),
                "energy": state.get("energy", _DEFAULTS["energy"]),
                "session_turns": state.get("session_turns", _DEFAULTS["session_turns"]),
                "total_turns": state.get("total_turns", _DEFAULTS["total_turns"]),
                "last_active_ts": state.get("last_active_ts", _DEFAULTS["last_active_ts"]),
                "drift_count": state.get("drift_count", _DEFAULTS["drift_count"]),
            },
        )
        conn.commit()


def _import_legacy_state_once() -> None:
    """Copy buddy_state from the legacy JSON file once. The JSON file is never deleted."""
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        if _already_imported(conn):
            return
        existing = conn.execute("SELECT COUNT(*) FROM buddy_state").fetchone()[0]
        if existing > 0:
            _mark_imported(conn, "skipped-target-not-empty")
            return
        if not LEGACY_STATE_FILE.exists():
            _mark_imported(conn, "no-source-file")
            return
        try:
            saved = json.loads(LEGACY_STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Legacy buddy state import failed from {LEGACY_STATE_FILE}: {exc}"
            ) from exc
        merged = {**_DEFAULTS, **saved}
        conn.execute(
            """
            INSERT INTO buddy_state
                (id, mood, energy, session_turns, total_turns, last_active_ts, drift_count)
            VALUES (1, :mood, :energy, :session_turns, :total_turns, :last_active_ts, :drift_count)
            """,
            {k: merged[k] for k in _DEFAULTS},
        )
        _mark_imported(conn, str(LEGACY_STATE_FILE))


def _already_imported(conn) -> bool:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (LEGACY_IMPORT_SETTING,),
    ).fetchone()
    return row is not None


def _mark_imported(conn, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (LEGACY_IMPORT_SETTING, value),
    )
