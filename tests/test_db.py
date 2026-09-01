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


def test_migrate_applies_new_migration_dropped_after_first_run(tmp_path):
    """A migration file added after migrate() has run must still be applied."""
    db_file = tmp_path / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_base.sql").write_text(
        "CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )

    first = db.migrate(db_file=db_file, migrations_dir=migrations_dir)
    assert first == ["001_base.sql"]

    (migrations_dir / "002_extra.sql").write_text(
        "CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    second = db.migrate(db_file=db_file, migrations_dir=migrations_dir)
    assert second == ["002_extra.sql"]

    with sqlite3.connect(db_file) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"t1", "t2"} <= tables


def test_migrate_reapplies_when_schema_marker_is_removed(tmp_path):
    """Rollback recovery must not be hidden by an in-process migration cache."""
    db_file = tmp_path / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_base.sql").write_text(
        "CREATE TABLE recovered (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )

    assert db.migrate(db_file=db_file, migrations_dir=migrations_dir) == ["001_base.sql"]
    with sqlite3.connect(db_file) as conn:
        conn.execute("DROP TABLE recovered")
        conn.execute("DELETE FROM schema_migrations WHERE name = '001_base.sql'")
        conn.commit()

    assert db.migrate(db_file=db_file, migrations_dir=migrations_dir) == ["001_base.sql"]
    with sqlite3.connect(db_file) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='recovered'"
        ).fetchone() == ("recovered",)


def test_migrate_reconciles_renamed_migrations_without_replaying_sql(tmp_path):
    """Renumbered migrations must not replay against DBs that saw legacy names."""
    db_file = tmp_path / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    with db.connect(db_file) as conn:
        conn.execute("CREATE TABLE image_recipes (recipe_id TEXT, execution_target TEXT)")
        conn.executemany(
            "INSERT INTO schema_migrations (name) VALUES (?)",
            [
                ("036_image_jobs_compiler_provenance.sql",),
                ("037_image_recipes_execution_target.sql",),
                ("038_image_jobs_canonical_artifact.sql",),
                ("039_image_sessions_project_scope.sql",),
            ],
        )

    (migrations_dir / "040_image_jobs_compiler_provenance.sql").write_text("-- no-op\n")
    (migrations_dir / "041_image_recipes_execution_target.sql").write_text(
        "ALTER TABLE image_recipes ADD COLUMN execution_target TEXT;\n"
    )
    (migrations_dir / "042_image_jobs_canonical_artifact.sql").write_text("-- no-op\n")
    (migrations_dir / "043_image_sessions_project_scope.sql").write_text("-- no-op\n")

    applied = db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    assert applied == []
    db.assert_schema_current(db_file=db_file, migrations_dir=migrations_dir)
    with sqlite3.connect(db_file) as conn:
        recorded = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    assert {
        "040_image_jobs_compiler_provenance.sql",
        "041_image_recipes_execution_target.sql",
        "042_image_jobs_canonical_artifact.sql",
        "043_image_sessions_project_scope.sql",
    } <= recorded


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
    assert columns == {"id", "payload", "updated_at", "objective"}


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

    assert {
        "app_settings",
        "todos",
        "chats",
        "journal_entries",
        "buddy_state",
        "signals",
        "state_snapshots",
        "inbox_triage",
        "actions",
        "projects",
        "project_next_steps",
        "image_job_observations",
        "image_batches",
        "image_batch_items",
        "action_grants",
        "automation_runs",
    } <= tables
    assert applied == [
        "001_foundation.sql",
        "002_plugin_settings.sql",
        "003_todos.sql",
        "004_chats.sql",
        "005_journal_entries.sql",
        "006_buddy_state.sql",
        "007_signals.sql",
        "008_inbox_triage.sql",
        "009_actions.sql",
        "010_projects.sql",
        "011_project_next_steps.sql",
        "012_cron_schedules.sql",
        "013_memory_weave.sql",
        "014_deadlines.sql",
        "015_expert_state.sql",
        "016_chat_lifecycle.sql",
        "017_artifacts.sql",
        "018_message_attachments.sql",
        "019_idea_mine.sql",
        "020_chat_objective.sql",
        "021_chat_lifecycle_objective.sql",
        "022_chat_message_memory.sql",
        "023_image_jobs.sql",
        "024_image_characters.sql",
        "025_image_references.sql",
        "026_image_recipes.sql",
        "027_image_characters_v2.sql",
        "028_image_jobs_queue.sql",
        "029_image_sessions.sql",
        "030_image_plans.sql",
        "031_agent_workspace.sql",
        "032_agent_workspace_turns.sql",
        "033_image_job_observations.sql",
        "034_image_batches.sql",
        "035_image_plans_operation.sql",
        "036_action_grants.sql",
        "037_action_approval_identity.sql",
        "040_image_jobs_compiler_provenance.sql",
        "041_image_recipes_execution_target.sql",
        "042_image_jobs_canonical_artifact.sql",
        "043_image_sessions_project_scope.sql",
        "044_image_characters_v2_columns.sql",
        "045_image_intent_provenance.sql",
        "046_explicit_memories.sql",
        "047_automation_runs.sql",
        "048_image_session_reserved_spend.sql",
        "049_automation_runs_payload.sql",
        "050_automation_runs_watch_disabled_status.sql",
        "051_undo_journal.sql",
        "052_agent_workspace_receipts.sql",
        "053_action_undo_receipt.sql",
        "054_agent_workspace_presence.sql",
        "055_research_runs.sql",
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


# ---------------------------------------------------------------------------
# assert_schema_current
# ---------------------------------------------------------------------------

def test_assert_schema_current_passes_after_full_migrate(tmp_path):
    """After migrate() runs, assert_schema_current() should not raise."""
    db_file = tmp_path / "kitty.db"
    db.migrate(db_file=db_file)
    db.assert_schema_current(db_file=db_file)  # must not raise


def test_assert_schema_current_raises_if_migration_file_not_applied(tmp_path):
    """A new migration file on disk that is absent from the DB triggers an error."""
    db_file = tmp_path / "kitty.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "001_base.sql").write_text(
        "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    db.migrate(db_file=db_file, migrations_dir=migrations_dir)

    # Drop a second migration file onto disk without running migrate again.
    (migrations_dir / "002_extra.sql").write_text(
        "CREATE TABLE IF NOT EXISTS t2 (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError) as exc:
        db.assert_schema_current(db_file=db_file, migrations_dir=migrations_dir)

    assert "002_extra.sql" in str(exc.value)
