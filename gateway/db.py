"""Phase B SQLite foundation for app-owned Kitty state."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from gateway.paths import DB_MIGRATIONS_DIR, KITTY_DB_FILE

logger = logging.getLogger("kitty.db")

_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA busy_timeout=5000;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA synchronous=NORMAL;",
)


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply standard WAL/busy/foreign_keys/sync pragmas to a connection.

    Safe to call on any SQLite connection regardless of how it was opened.
    Idempotent — repeated calls are harmless.
    """
    for pragma in _PRAGMAS:
        conn.execute(pragma)


def connect(db_file: Path = KITTY_DB_FILE) -> sqlite3.Connection:
    """Open a SQLite database with WAL, busy_timeout, foreign_keys, synchronous."""
    db_path = Path(db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    apply_pragmas(conn)
    return conn


def migrate(
    db_file: Path = KITTY_DB_FILE,
    migrations_dir: Path = DB_MIGRATIONS_DIR,
) -> list[str]:
    """Apply pending SQL migrations and return the filenames applied."""
    db_path = Path(db_file)
    migration_path = Path(migrations_dir)
    if not migration_path.exists():
        raise RuntimeError(f"Migration directory does not exist: {migration_path}")

    applied_now: list[str] = []
    with connect(db_path) as conn:
        _ensure_schema_migrations(conn)
        applied = {
            row["name"] for row in conn.execute("SELECT name FROM schema_migrations")
        }
        for path in sorted(migration_path.glob("*.sql")):
            if path.name in applied:
                continue
            _apply_migration(conn, path, db_path)
            applied_now.append(path.name)
            logger.info("Applied migration: %s", path.name)
    return applied_now


def assert_schema_current(
    db_file: Path = KITTY_DB_FILE,
    migrations_dir: Path = DB_MIGRATIONS_DIR,
) -> None:
    """Raise RuntimeError if any migration file on disk has not been applied.

    Call this after :func:`migrate` to assert the database is fully up to date.
    Fails loud — never silently swallows a missing migration.
    """
    migration_files = {p.name for p in Path(migrations_dir).glob("*.sql")}
    if not migration_files:
        return

    db_path = Path(db_file)
    try:
        with connect(db_path) as conn:
            try:
                applied = {
                    row["name"]
                    for row in conn.execute("SELECT name FROM schema_migrations")
                }
            except sqlite3.OperationalError as exc:
                raise RuntimeError(
                    f"schema_migrations table missing in {db_path} — "
                    "run migrate() before asserting schema currency"
                ) from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Could not open database {db_path} to assert schema currency: {exc}"
        ) from exc

    missing = sorted(migration_files - applied)
    if missing:
        raise RuntimeError(
            f"Database {db_path} is missing {len(missing)} migration(s): "
            + ", ".join(missing)
        )


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)


def _apply_migration(conn: sqlite3.Connection, path: Path, db_path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    try:
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Migration {path.name} failed for database {db_path}: {exc}"
        ) from exc
