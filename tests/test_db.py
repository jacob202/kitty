"""Tests for the Phase B SQLite foundation."""

from __future__ import annotations

import sqlite3

import pytest

from gateway import db


def test_migrate_applies_foundation_once(tmp_path):
    db_file = tmp_path / "data" / "kitty" / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_foundation.sql").write_text(
        """
        CREATE TABLE app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """,
        encoding="utf-8",
    )

    first = db.migrate(db_file=db_file, migrations_dir=migrations_dir)
    second = db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    assert first == ["001_foundation.sql"]
    assert second == []
    with sqlite3.connect(db_file) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        applied = conn.execute(
            "SELECT name FROM schema_migrations ORDER BY name"
        ).fetchall()

    assert "schema_migrations" in tables
    assert "app_settings" in tables
    assert applied == [("001_foundation.sql",)]


def test_connect_sets_row_factory_and_foreign_keys(tmp_path):
    db_file = tmp_path / "kitty.db"

    with db.connect(db_file) as conn:
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES (?)", ("Kitty",))
        row = conn.execute("SELECT id, name FROM sample").fetchone()

    assert foreign_keys == 1
    assert row["name"] == "Kitty"


def test_default_migrations_create_app_settings(tmp_path):
    db_file = tmp_path / "kitty.db"

    applied = db.migrate(db_file=db_file)

    assert "001_foundation.sql" in applied
    with sqlite3.connect(db_file) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_settings'"
        ).fetchone()
    assert table == ("app_settings",)


def test_default_migrations_create_chats_table(tmp_path):
    """Phase C C1: 004_chats.sql adds a chats table keyed by id with a JSON payload."""
    db_file = tmp_path / "kitty.db"

    applied = db.migrate(db_file=db_file)

    assert "004_chats.sql" in applied
    with sqlite3.connect(db_file) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'chats'"
        ).fetchone()
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(chats)").fetchall()
        }
    assert table == ("chats",)
    assert columns == {"id", "payload", "updated_at"}


def test_default_migrations_create_journal_entries_table(tmp_path):
    """Phase C B1: 005_journal_entries.sql adds a normalized journal_entries table."""
    db_file = tmp_path / "kitty.db"

    applied = db.migrate(db_file=db_file)

    assert "005_journal_entries.sql" in applied
    with sqlite3.connect(db_file) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'journal_entries'"
        ).fetchone()
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(journal_entries)").fetchall()
        }
    assert table == ("journal_entries",)
    assert columns == {"id", "ts", "theme", "entry", "session_id", "created_at"}


def test_default_migrations_preserve_existing_tables_when_adding_journal(tmp_path):
    """Phase C B1 should add journal_entries without disturbing earlier storage slices."""
    db_file = tmp_path / "kitty.db"

    db.migrate(db_file=db_file)

    with sqlite3.connect(db_file) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        applied = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM schema_migrations ORDER BY name"
            ).fetchall()
        ]

    assert {"app_settings", "todos", "chats", "journal_entries"} <= tables
    assert applied == [
        "001_foundation.sql",
        "002_plugin_settings.sql",
        "003_todos.sql",
        "004_chats.sql",
        "005_journal_entries.sql",
    ]


def test_journal_entries_schema_matches_phase_c_contract(tmp_path):
    """Phase C B1: column order, required fields, and default timestamp match the plan."""
    db_file = tmp_path / "kitty.db"

    db.migrate(db_file=db_file)

    with sqlite3.connect(db_file) as conn:
        columns = {
            row[1]: {
                "type": row[2],
                "notnull": row[3],
                "default": row[4],
                "pk": row[5],
            }
            for row in conn.execute("PRAGMA table_info(journal_entries)").fetchall()
        }

    assert columns == {
        "id": {"type": "INTEGER", "notnull": 0, "default": None, "pk": 1},
        "ts": {"type": "REAL", "notnull": 1, "default": None, "pk": 0},
        "theme": {"type": "TEXT", "notnull": 0, "default": None, "pk": 0},
        "entry": {"type": "TEXT", "notnull": 1, "default": None, "pk": 0},
        "session_id": {"type": "TEXT", "notnull": 0, "default": None, "pk": 0},
        "created_at": {
            "type": "TEXT",
            "notnull": 1,
            "default": "CURRENT_TIMESTAMP",
            "pk": 0,
        },
    }


def test_migrate_failure_names_file_and_database(tmp_path):
    db_file = tmp_path / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_bad.sql").write_text("SELECT nope FROM", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc:
        db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    message = str(exc.value)
    assert "001_bad.sql" in message
    assert str(db_file) in message
    with sqlite3.connect(db_file) as conn:
        applied = conn.execute("SELECT name FROM schema_migrations").fetchall()
    assert applied == []
