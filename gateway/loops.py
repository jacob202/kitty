"""Background task loops — owned substrate for the loops endpoint.

Why this module exists (Phase 3 of the gateway deepening program):
the route used to keep three hardcoded loop dicts in an
in-memory ``_loops`` list and serve them on every request. The
"loop" was a Python module-level mutable that disappeared on
restart. The new module backs loops with a SQLite table owned by
this module, seeded with the three real loops on first init.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Optional

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.loops")

LOOPS_DB = DATA_DIR / "loops.db"

#: The three real loops that ship with the gateway. Seeded into the
#: store on first init; from then on, the store is canonical.
SEED_LOOPS: list[dict] = [
    {
        "loop_id": "daily-brief",
        "name": "Daily Brief",
        "description": "Generates morning brief at 7am",
        "status": "running",
        "interval_minutes": 1440,
        "last_result": "Brief generated successfully",
    },
    {
        "loop_id": "search-index",
        "name": "Search Index",
        "description": "Updates search index every 15 minutes",
        "status": "running",
        "interval_minutes": 15,
    },
    {
        "loop_id": "memory-consolidation",
        "name": "Memory Consolidation",
        "description": "Consolidates memories during off-peak hours",
        "status": "paused",
        "interval_minutes": 360,
    },
]


def init_db() -> None:
    """Create the loops table and seed it on first run."""
    LOOPS_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(LOOPS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS loops (
                loop_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'idle',
                interval_minutes INTEGER DEFAULT 60,
                last_run REAL DEFAULT 0,
                last_result TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL
            )
        """)
        existing = conn.execute("SELECT COUNT(*) FROM loops").fetchone()[0]
        if existing == 0:
            now = time.time()
            for offset, seed in enumerate(SEED_LOOPS):
                created_at = now - (len(SEED_LOOPS) - offset) * 3600
                conn.execute(
                    """
                    INSERT INTO loops (
                        loop_id, name, description, status,
                        interval_minutes, last_run, last_result,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        seed["loop_id"],
                        seed["name"],
                        seed.get("description", ""),
                        seed.get("status", "idle"),
                        seed.get("interval_minutes", 60),
                        created_at,
                        seed.get("last_result", ""),
                        created_at,
                        created_at,
                    ),
                )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def list_loops() -> list[dict]:
    """Return every loop, ordered by creation time."""
    init_db()
    with sqlite3.connect(LOOPS_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM loops ORDER BY created_at ASC").fetchall()
    return [_row_to_dict(r) for r in rows]


def _generate_id(name: str, *, fallback_index: int) -> str:
    base = (name or "").strip().lower().replace(" ", "-")
    return base or f"loop-{fallback_index}"


def _next_available_id(conn: sqlite3.Connection, base_id: str) -> str:
    """Return ``base_id`` if free, else ``base_id-N`` for the smallest free N."""
    if conn.execute("SELECT 1 FROM loops WHERE loop_id = ?", (base_id,)).fetchone() is None:
        return base_id
    n = 1
    while True:
        candidate = f"{base_id}-{n}"
        if conn.execute("SELECT 1 FROM loops WHERE loop_id = ?", (candidate,)).fetchone() is None:
            return candidate
        n += 1


def create_loop(spec: dict) -> dict:
    """Insert one loop and return it as a dict.

    ``spec`` keys: ``name`` (required), ``description``,
    ``interval_minutes``, ``status``. The id is derived from
    ``name``; collisions get a numeric suffix.
    """
    if not isinstance(spec, dict):
        raise TypeError(f"loop spec must be a dict, got {type(spec).__name__}")

    init_db()
    name = str(spec.get("name", "")).strip()
    if not name:
        raise ValueError("loop 'name' is required")

    base_id = _generate_id(name, fallback_index=int(time.time()))
    with sqlite3.connect(LOOPS_DB) as conn:
        loop_id = _next_available_id(conn, base_id)
        now = time.time()
        conn.execute(
            """
            INSERT INTO loops (
                loop_id, name, description, status,
                interval_minutes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                loop_id,
                name,
                str(spec.get("description", "") or ""),
                str(spec.get("status", "idle")),
                int(spec.get("interval_minutes", 60) or 60),
                now,
                now,
            ),
        )
        conn.commit()

        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM loops WHERE loop_id = ?", (loop_id,)).fetchone()
    return _row_to_dict(row) if row else {"loop_id": loop_id, "name": name}


def toggle_loop(loop_id: str) -> Optional[dict]:
    """Flip a loop between ``running`` and ``paused``. Returns the new
    row, or ``None`` if the id is unknown.
    """
    if not isinstance(loop_id, str) or not loop_id:
        raise ValueError("loop_id must be a non-empty string")
    init_db()
    with sqlite3.connect(LOOPS_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM loops WHERE loop_id = ?", (loop_id,)).fetchone()
        if row is None:
            return None
        current = row["status"]
        if current == "running":
            new_status = "paused"
        elif current == "paused":
            new_status = "running"
        else:
            new_status = "running"
        now = time.time()
        conn.execute(
            "UPDATE loops SET status = ?, updated_at = ? WHERE loop_id = ?",
            (new_status, now, loop_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM loops WHERE loop_id = ?", (loop_id,)).fetchone()
    return _row_to_dict(updated) if updated else None


def delete_loop(loop_id: str) -> bool:
    """Remove a loop by id. Returns ``False`` if it was not present."""
    if not isinstance(loop_id, str) or not loop_id:
        raise ValueError("loop_id must be a non-empty string")
    init_db()
    with sqlite3.connect(LOOPS_DB) as conn:
        cursor = conn.execute("DELETE FROM loops WHERE loop_id = ?", (loop_id,))
        conn.commit()
        return cursor.rowcount > 0
