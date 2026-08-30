"""Journal entry store — normalized columns in kitty.db.

The journal module (gateway/journal.py:save_journal_entry) calls into
this module instead of appending to data/journal_entries.jsonl directly.
The wire shape (return value of save_journal_entry) is preserved; the
storage substrate changes.

Public API:
  append_entry(ts, theme, entry, session_id=None) -> dict
      Mirror of save_journal_entry's contract: returns the stored record.

  list_entries(limit=50, theme=None) -> list[dict]
      Newest first. Optional theme filter.

  list_recent(days=14, limit=20) -> list[dict]
      Newer than `days` ago, newest first. Used by the brief.

  search(query, limit=5) -> list[dict]
      Keyword search. Each result carries an `_score`.

  count_entries(theme=None) -> int
      Total entries, optionally filtered by theme.

  delete_entry(ts, session_id=None) -> bool
      Remove one entry by ts (and optional session_id). True if a row was
      deleted.

Legacy import: on first access, if data/journal_entries.jsonl exists
and the table is empty, the JSONL contents are imported. The JSONL
file is never deleted. The import marker is stored in app_settings
key 'journal_legacy_imported'.

Rollback (documented escape hatch): if the SQLite layer needs to be
abandoned, the JSONL file is still the source of truth. To roll back:
  1. DROP TABLE journal_entries;
  2. DELETE FROM app_settings WHERE key = 'journal_legacy_imported';
  3. DELETE FROM schema_migrations WHERE name = '005_journal_entries.sql';
  4. Re-run the gateway; migrate re-applies 005_journal_entries.sql,
     then the import rebuilds the table from the JSONL file.
This is verified by TestLegacyImport.test_rollback_re_imports_from_intact_jsonl.
"""
from __future__ import annotations

import json
import logging
import sqlite3

from gateway import db as kitty_db
from gateway.paths import DATA_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.journal_store")

JOURNAL_DB_FILE = KITTY_DB_FILE
LEGACY_JOURNAL_LOG = DATA_DIR / "journal_entries.jsonl"
LEGACY_IMPORT_SETTING = "journal_legacy_imported"


def init_db() -> None:
    """Apply pending migrations and run the one-time legacy import. Idempotent."""
    kitty_db.migrate(db_file=JOURNAL_DB_FILE)
    _import_legacy_journal_once()


def append_entry(
    *,
    ts: float,
    entry: str,
    theme: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Append one entry. Returns the stored record (mirrors save_journal_entry)."""
    record = {"ts": ts, "theme": theme, "entry": entry}
    if session_id:
        record["session_id"] = session_id
    init_db()
    with kitty_db.connect(JOURNAL_DB_FILE) as conn:
        cursor = conn.execute(
            """
            INSERT INTO journal_entries (ts, theme, entry, session_id)
            VALUES (?, ?, ?, ?)
            """,
            (ts, theme, entry, session_id),
        )
        conn.commit()
        record["id"] = cursor.lastrowid
    return record


def list_entries(limit: int = 50, theme: str | None = None) -> list[dict]:
    """Return entries, newest first. Optional theme filter."""
    init_db()
    with kitty_db.connect(JOURNAL_DB_FILE) as conn:
        if theme is None:
            rows = conn.execute(
                "SELECT id, ts, theme, entry, session_id, created_at "
                "FROM journal_entries ORDER BY ts DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, ts, theme, entry, session_id, created_at "
                "FROM journal_entries WHERE theme = ? "
                "ORDER BY ts DESC, id DESC LIMIT ?",
                (theme, limit),
            ).fetchall()
    return [_row_to_entry(r) for r in rows]


def count_entries(theme: str | None = None) -> int:
    """Total entries, optionally filtered by theme."""
    init_db()
    with kitty_db.connect(JOURNAL_DB_FILE) as conn:
        if theme is None:
            return conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM journal_entries WHERE theme = ?", (theme,)
        ).fetchone()[0]


def delete_entry(*, ts: float, session_id: str | None = None) -> bool:
    """Remove one entry by ts (and optional session_id). True if a row was deleted."""
    init_db()
    with kitty_db.connect(JOURNAL_DB_FILE) as conn:
        if session_id is None:
            cursor = conn.execute(
                "DELETE FROM journal_entries WHERE ts = ?", (ts,)
            )
        else:
            cursor = conn.execute(
                "DELETE FROM journal_entries WHERE ts = ? AND session_id = ?",
                (ts, session_id),
            )
        conn.commit()
        return cursor.rowcount > 0


def list_recent(days: int = 14, limit: int = 20) -> list[dict]:
    """Return entries newer than `days` ago, newest first. Used by the brief."""
    import time as _time

    cutoff = _time.time() - (days * 86400)
    init_db()
    with kitty_db.connect(JOURNAL_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, ts, theme, entry, session_id, created_at "
            "FROM journal_entries WHERE ts >= ? "
            "ORDER BY ts DESC, id DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
    return [_row_to_entry(r) for r in rows]


def search(query: str, limit: int = 5) -> list[dict]:
    """Keyword search over entry text. Each result carries an `_score`.

    Used by memory_graph unified_context. Score is the count of distinct query
    terms that appear in the entry text. Empty query returns [].
    """
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []
    init_db()
    with kitty_db.connect(JOURNAL_DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id, ts, theme, entry, session_id, created_at "
            "FROM journal_entries ORDER BY ts DESC, id DESC LIMIT 1000"
        ).fetchall()
    scored: list[dict] = []
    for r in rows:
        entry = _row_to_entry(r)
        text = entry.get("entry", "").lower()
        score = sum(1 for t in terms if t in text)
        if score > 0:
            entry["_score"] = score
            scored.append(entry)
    scored.sort(key=lambda e: e.get("_score", 0), reverse=True)
    return scored[:limit]


def _row_to_entry(row: sqlite3.Row) -> dict:
    out = {
        "id": row["id"],
        "ts": row["ts"],
        "theme": row["theme"],
        "entry": row["entry"],
        "created_at": row["created_at"],
    }
    if row["session_id"] is not None:
        out["session_id"] = row["session_id"]
    return out


def _import_legacy_journal_once() -> None:
    """Copy entries from the legacy JSONL file once. The JSONL file is never deleted."""
    with kitty_db.connect(JOURNAL_DB_FILE) as target:
        if _already_imported(target):
            return
        target_count = target.execute(
            "SELECT COUNT(*) FROM journal_entries"
        ).fetchone()[0]
        if target_count > 0:
            _mark_legacy_imported(target, "skipped-target-not-empty")
            return
        if not LEGACY_JOURNAL_LOG.exists():
            _mark_legacy_imported(target, "no-source-file")
            return
        try:
            entries = _read_legacy_entries()
            for entry in entries:
                _insert_entry_raw(target, entry)
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Legacy journal import failed from {LEGACY_JOURNAL_LOG}: {exc}"
            ) from exc
        _mark_legacy_imported(target, str(LEGACY_JOURNAL_LOG))


def _insert_entry_raw(conn: sqlite3.Connection, entry: dict) -> None:
    validated = _validate_legacy_entry(entry)
    conn.execute(
        """
        INSERT INTO journal_entries (ts, theme, entry, session_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            validated["ts"],
            validated["theme"],
            validated["entry"],
            validated["session_id"],
        ),
    )


def _validate_legacy_entry(entry: object) -> dict[str, object]:
    if not isinstance(entry, dict):
        raise ValueError(
            f"Expected legacy journal record dict, got {type(entry).__name__}"
        )

    if "ts" not in entry:
        raise ValueError(f"Legacy journal record missing required 'ts': {entry!r}")
    if "entry" not in entry:
        raise ValueError(f"Legacy journal record missing required 'entry': {entry!r}")

    ts = entry["ts"]
    if not isinstance(ts, (int, float)):
        raise ValueError(f"Legacy journal record has non-numeric 'ts': {entry!r}")

    entry_text = entry["entry"]
    if not isinstance(entry_text, str):
        raise ValueError(
            f"Legacy journal record has non-string 'entry': {entry!r}"
        )

    theme = entry.get("theme")
    if theme is not None and not isinstance(theme, str):
        raise ValueError(
            f"Legacy journal record has non-string 'theme': {entry!r}"
        )

    session_id = entry.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        raise ValueError(
            f"Legacy journal record has non-string 'session_id': {entry!r}"
        )

    return {
        "ts": float(ts),
        "theme": theme,
        "entry": entry_text,
        "session_id": session_id,
    }


def _already_imported(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (LEGACY_IMPORT_SETTING,),
    ).fetchone()
    return row is not None


def _read_legacy_entries() -> list[dict]:
    out: list[dict] = []
    with LEGACY_JOURNAL_LOG.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL line in {LEGACY_JOURNAL_LOG}: {line!r}"
                ) from exc
    return out


def _mark_legacy_imported(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (LEGACY_IMPORT_SETTING, value),
    )
