"""Phase B SQLite foundation for app-owned Kitty state."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gateway.paths import DB_MIGRATIONS_DIR, KITTY_DB_FILE


def connect(db_file: Path = KITTY_DB_FILE) -> sqlite3.Connection:
    """Open the Kitty SQLite database with project defaults enabled."""
    db_path = Path(db_file)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
            row["name"]
            for row in conn.execute("SELECT name FROM schema_migrations")
        }
        for path in sorted(migration_path.glob("*.sql")):
            if path.name in applied:
                continue
            _apply_migration(conn, path, db_path)
            applied_now.append(path.name)
    return applied_now


def _ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _apply_migration(conn: sqlite3.Connection, path: Path, db_path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    try:
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Migration {path.name} failed for database {db_path}: {exc}"
        ) from exc
