"""SQLite source ledger for provenance, candidate lifecycle, and audit trails."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.db_config import get_db_path

ALLOWED_STATES = ("candidate", "quarantined", "durable", "retired")
ALLOWED_SOFT_DELETE_TABLES = ("raw_source", "memory_candidates")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SourceLedger:
    """Minimal SQLite ledger for source provenance and memory lifecycle."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else get_db_path("source_ledger")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_source (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_timestamp TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    snippet_hash TEXT NOT NULL,
                    raw_text TEXT,
                    created_at TEXT NOT NULL,
                    deleted_at TEXT,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(source_path, source_type, source_timestamp, chunk_id, snippet_hash)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_source_id INTEGER NOT NULL,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_timestamp TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    snippet_hash TEXT NOT NULL,
                    candidate_text TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    state TEXT NOT NULL DEFAULT 'candidate',
                    quarantine_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT,
                    is_deleted INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(raw_source_id) REFERENCES raw_source(id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT,
                    CHECK(state IN ('candidate', 'quarantined', 'durable', 'retired')),
                    CHECK(confidence >= 0.0 AND confidence <= 1.0)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_promotions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    previous_state TEXT NOT NULL,
                    new_state TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_timestamp TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    snippet_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY(candidate_id) REFERENCES memory_candidates(id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT,
                    CHECK(action IN ('promote', 'retire', 'quarantine')),
                    CHECK(new_state IN ('candidate', 'quarantined', 'durable', 'retired')),
                    CHECK(previous_state IN ('candidate', 'quarantined', 'durable', 'retired')),
                    CHECK(confidence >= 0.0 AND confidence <= 1.0)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER NOT NULL,
                    conflicting_candidate_id INTEGER,
                    conflict_reason TEXT NOT NULL,
                    resolution_state TEXT NOT NULL DEFAULT 'quarantined',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_timestamp TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    snippet_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY(candidate_id) REFERENCES memory_candidates(id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT,
                    FOREIGN KEY(conflicting_candidate_id) REFERENCES memory_candidates(id)
                        ON UPDATE CASCADE
                        ON DELETE SET NULL,
                    CHECK(resolution_state IN ('candidate', 'quarantined', 'durable', 'retired')),
                    CHECK(confidence >= 0.0 AND confidence <= 1.0)
                )
                """
            )
            conn.commit()

    def _row(self, cursor: sqlite3.Cursor) -> dict[str, Any]:
        row = cursor.fetchone()
        return dict(row) if row is not None else {}

    def _row_by_id(self, table: str, record_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row is not None else None

    def insert_source(
        self,
        source_path: str,
        source_type: str,
        source_timestamp: str,
        chunk_id: str,
        snippet_hash: str,
        raw_text: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        created_at = created_at or _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO raw_source (
                    source_path, source_type, source_timestamp, chunk_id,
                    snippet_hash, raw_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (source_path, source_type, source_timestamp, chunk_id, snippet_hash, raw_text, created_at),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT *
                FROM raw_source
                WHERE source_path = ? AND source_type = ? AND source_timestamp = ?
                  AND chunk_id = ? AND snippet_hash = ?
                """,
                (source_path, source_type, source_timestamp, chunk_id, snippet_hash),
            ).fetchone()
            return dict(row)

    def add_candidate(
        self,
        raw_source_id: int,
        candidate_text: str,
        confidence: float,
        state: str = "candidate",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        if state not in ALLOWED_STATES:
            raise ValueError(f"Invalid state: {state}")
        created_at = created_at or _utc_now()
        with self._connect() as conn:
            source = conn.execute(
                """
                SELECT source_path, source_type, source_timestamp, chunk_id, snippet_hash
                FROM raw_source
                WHERE id = ?
                """,
                (raw_source_id,),
            ).fetchone()
            if source is None:
                raise ValueError(f"Unknown raw_source_id: {raw_source_id}")
            cur = conn.execute(
                """
                INSERT INTO memory_candidates (
                    raw_source_id, source_path, source_type, source_timestamp,
                    chunk_id, snippet_hash, candidate_text, confidence, state,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_source_id,
                    source["source_path"],
                    source["source_type"],
                    source["source_timestamp"],
                    source["chunk_id"],
                    source["snippet_hash"],
                    candidate_text,
                    confidence,
                    state,
                    created_at,
                    created_at,
                ),
            )
            conn.commit()
            return self.get_candidate(cur.lastrowid)

    def quarantine_candidate(
        self,
        candidate_id: int,
        reason: str,
        quarantined_at: str | None = None,
        conflicting_candidate_id: int | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        quarantined_at = quarantined_at or _utc_now()
        with self._connect() as conn:
            candidate = conn.execute(
                "SELECT * FROM memory_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                raise ValueError(f"Unknown candidate_id: {candidate_id}")
            conn.execute(
                """
                UPDATE memory_candidates
                SET state = 'quarantined',
                    quarantine_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (reason, quarantined_at, candidate_id),
            )
            conn.execute(
                """
                INSERT INTO memory_conflicts (
                    candidate_id, conflicting_candidate_id, conflict_reason,
                    resolution_state, confidence, source_path, source_type,
                    source_timestamp, chunk_id, snippet_hash, created_at, notes
                ) VALUES (?, ?, ?, 'quarantined', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    conflicting_candidate_id,
                    reason,
                    float(candidate["confidence"]),
                    candidate["source_path"],
                    candidate["source_type"],
                    candidate["source_timestamp"],
                    candidate["chunk_id"],
                    candidate["snippet_hash"],
                    quarantined_at,
                    notes,
                ),
            )
            conn.execute(
                """
                INSERT INTO memory_promotions (
                    candidate_id, action, previous_state, new_state, confidence,
                    source_path, source_type, source_timestamp, chunk_id,
                    snippet_hash, created_at, notes
                ) VALUES (?, 'quarantine', ?, 'quarantined', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    candidate["state"],
                    float(candidate["confidence"]),
                    candidate["source_path"],
                    candidate["source_type"],
                    candidate["source_timestamp"],
                    candidate["chunk_id"],
                    candidate["snippet_hash"],
                    quarantined_at,
                    notes or reason,
                ),
            )
            conn.commit()
            return self.get_candidate(candidate_id)

    def promote_candidate(
        self,
        candidate_id: int,
        promoted_at: str | None = None,
        confidence: float | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        promoted_at = promoted_at or _utc_now()
        with self._connect() as conn:
            candidate = conn.execute(
                "SELECT * FROM memory_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                raise ValueError(f"Unknown candidate_id: {candidate_id}")
            new_confidence = float(candidate["confidence"]) if confidence is None else confidence
            conn.execute(
                """
                UPDATE memory_candidates
                SET state = 'durable',
                    confidence = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_confidence, promoted_at, candidate_id),
            )
            conn.execute(
                """
                INSERT INTO memory_promotions (
                    candidate_id, action, previous_state, new_state, confidence,
                    source_path, source_type, source_timestamp, chunk_id,
                    snippet_hash, created_at, notes
                ) VALUES (?, 'promote', ?, 'durable', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    candidate["state"],
                    new_confidence,
                    candidate["source_path"],
                    candidate["source_type"],
                    candidate["source_timestamp"],
                    candidate["chunk_id"],
                    candidate["snippet_hash"],
                    promoted_at,
                    notes,
                ),
            )
            conn.commit()
            return self.get_candidate(candidate_id)

    def retire_candidate(
        self,
        candidate_id: int,
        retired_at: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        retired_at = retired_at or _utc_now()
        with self._connect() as conn:
            candidate = conn.execute(
                "SELECT * FROM memory_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if candidate is None:
                raise ValueError(f"Unknown candidate_id: {candidate_id}")
            conn.execute(
                """
                UPDATE memory_candidates
                SET state = 'retired',
                    updated_at = ?
                WHERE id = ?
                """,
                (retired_at, candidate_id),
            )
            conn.execute(
                """
                INSERT INTO memory_promotions (
                    candidate_id, action, previous_state, new_state, confidence,
                    source_path, source_type, source_timestamp, chunk_id,
                    snippet_hash, created_at, notes
                ) VALUES (?, 'retire', ?, 'retired', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    candidate["state"],
                    float(candidate["confidence"]),
                    candidate["source_path"],
                    candidate["source_type"],
                    candidate["source_timestamp"],
                    candidate["chunk_id"],
                    candidate["snippet_hash"],
                    retired_at,
                    notes,
                ),
            )
            conn.commit()
            return self.get_candidate(candidate_id)

    def soft_delete_marker(
        self,
        table_name: str,
        record_id: int,
        deleted_at: str | None = None,
    ) -> dict[str, Any]:
        if table_name not in ALLOWED_SOFT_DELETE_TABLES:
            raise ValueError(f"Unsupported table for soft delete: {table_name}")
        deleted_at = deleted_at or _utc_now()
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE {table_name}
                SET is_deleted = 1,
                    deleted_at = ?
                WHERE id = ?
                """,
                (deleted_at, record_id),
            )
            conn.commit()
            row = conn.execute(
                f"SELECT * FROM {table_name} WHERE id = ?",
                (record_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown record_id: {record_id}")
            return dict(row)

    def soft_delete_source(self, source_id: int, deleted_at: str | None = None) -> dict[str, Any]:
        return self.soft_delete_marker("raw_source", source_id, deleted_at=deleted_at)

    def soft_delete_candidate(self, candidate_id: int, deleted_at: str | None = None) -> dict[str, Any]:
        return self.soft_delete_marker("memory_candidates", candidate_id, deleted_at=deleted_at)

    def get_source(self, source_id: int) -> dict[str, Any] | None:
        return self._row_by_id("raw_source", source_id)

    def get_candidate(self, candidate_id: int) -> dict[str, Any] | None:
        return self._row_by_id("memory_candidates", candidate_id)

    def list_candidates(self, state: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if state is None:
                rows = conn.execute("SELECT * FROM memory_candidates ORDER BY id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memory_candidates WHERE state = ? ORDER BY id",
                    (state,),
                ).fetchall()
            return [dict(row) for row in rows]

