"""Tests for gateway/cron.py — schedule CRUD, toggle, and the C3 legacy
import from the standalone `data/cron_schedules.db` into the shared
`data/kitty/kitty.db`.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

# All tests in this module use a tmp kitty.db + (optionally) a tmp
# legacy cron_schedules.db, applied via monkeypatch on the module
# constants. This keeps the real data untouched.


@pytest.fixture
def tmp_kitty_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point gateway.cron at a fresh tmp kitty.db with migration 012 applied."""
    from gateway import db as kitty_db
    from gateway.cron import TABLE

    db_file = tmp_path / "kitty.db"
    with kitty_db.connect(db_file) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id             TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                action         TEXT NOT NULL,
                schedule_type  TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                metadata       TEXT DEFAULT '{{}}',
                enabled        INTEGER DEFAULT 1,
                last_run       REAL DEFAULT 0,
                created_at     REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.commit()

    # Make cron.py use the tmp DB and the same TABLE name.
    monkeypatch.setattr("gateway.cron.KITTY_DB_FILE", db_file)
    monkeypatch.setattr("gateway.cron.TABLE", TABLE)
    yield db_file


@pytest.fixture
def tmp_legacy_db(tmp_path: Path) -> Path:
    """Create a standalone legacy cron_schedules.db with one row."""
    legacy = tmp_path / "cron_schedules.db"
    with sqlite3.connect(legacy) as conn:
        conn.execute(
            """
            CREATE TABLE schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                last_run REAL DEFAULT 0,
                created_at REAL
            )
            """
        )
        conn.execute(
            "INSERT INTO schedules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-1", "morning brief", "brief.refresh",
                "daily", "07:00", "{}", 1, 0.0, time.time(),
            ),
        )
        conn.commit()
    return legacy


# ── Existing CRUD tests, repointed at the tmp DB ───────────────────────


class TestSchedule:
    def test_schedule_returns_id(self, tmp_kitty_db):
        from gateway.cron import schedule
        sid = schedule("test", "brief.refresh", "daily", "08:00")
        assert isinstance(sid, str) and len(sid) > 0

    def test_schedule_appears_in_list(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule
        schedule("my job", "nudges.check", "interval", "60")
        rows = list_schedules()
        assert any(r["name"] == "my job" for r in rows)

    def test_schedule_defaults(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule
        schedule("default-test", "brief.refresh")
        row = list_schedules()[0]
        assert row["schedule_type"] == "daily"
        assert row["schedule_value"] == "07:00"
        assert row["enabled"] == 1


class TestRemove:
    def test_remove_existing(self, tmp_kitty_db):
        from gateway.cron import list_schedules, remove, schedule
        sid = schedule("to remove", "brief.refresh")
        assert remove(sid) is True
        assert not any(r["id"] == sid for r in list_schedules())

    def test_remove_nonexistent(self, tmp_kitty_db):
        from gateway.cron import remove
        assert remove("no-such-id") is False


class TestToggle:
    def test_toggle_disables(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule, toggle
        sid = schedule("toggle-me", "nudges.check")
        state = toggle(sid)
        assert state is False
        row = next(r for r in list_schedules() if r["id"] == sid)
        assert row["enabled"] == 0

    def test_toggle_reenables(self, tmp_kitty_db):
        from gateway.cron import schedule, toggle
        sid = schedule("re-enable", "brief.refresh")
        toggle(sid)
        state = toggle(sid)
        assert state is True

    def test_toggle_nonexistent(self, tmp_kitty_db):
        from gateway.cron import toggle
        assert toggle("ghost-id") is None


class TestUpdate:
    def test_update_existing_schedule(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule, update
        sid = schedule("Morning brief", "brief.refresh", "daily", "07:00")
        assert update(sid, "Evening brief", "brief.refresh", "daily", "18:30") is True
        row = next(r for r in list_schedules() if r["id"] == sid)
        assert row["name"] == "Evening brief"
        assert row["schedule_value"] == "18:30"

    def test_update_missing_schedule_returns_false(self, tmp_kitty_db):
        from gateway.cron import update
        assert update("missing", "Nope", "brief.refresh", "daily", "07:00") is False


class TestGetActions:
    def test_get_actions_returns_list(self):
        from gateway.cron import get_actions
        assert isinstance(get_actions(), list)

    def test_register_and_get(self):
        from gateway.cron import get_actions, register_action

        async def _noop():
            pass

        register_action("test.noop", _noop)
        assert "test.noop" in get_actions()


class TestShouldFire:
    def test_interval_fires_when_due(self):
        from gateway.cron import _should_fire
        s = {"schedule_type": "interval", "schedule_value": "1", "last_run": 0}
        assert _should_fire(s, time.time()) is True

    def test_interval_does_not_fire_early(self):
        from gateway.cron import _should_fire
        s = {"schedule_type": "interval", "schedule_value": "60", "last_run": time.time()}
        assert _should_fire(s, time.time()) is False

    def test_invalid_interval_returns_false(self):
        from gateway.cron import _should_fire
        s = {"schedule_type": "interval", "schedule_value": "not-a-number", "last_run": 0}
        assert _should_fire(s, time.time()) is False

    def test_once_fires_when_past_and_never_run(self):
        from gateway.cron import _should_fire
        past = "2020-01-01T00:00:00"
        s = {"schedule_type": "once", "schedule_value": past, "last_run": 0}
        assert _should_fire(s, time.time()) is True

    def test_once_does_not_refire(self):
        from gateway.cron import _should_fire
        past = "2020-01-01T00:00:00"
        s = {"schedule_type": "once", "schedule_value": past, "last_run": time.time() - 10}
        assert _should_fire(s, time.time()) is False


# ── C3 legacy import tests ──────────────────────────────────────────


class TestLegacyImport:
    def test_legacy_import_copies_rows(
        self, tmp_kitty_db, tmp_legacy_db, monkeypatch
    ):
        from gateway import db as kitty_db
        from gateway.cron import (
            LEGACY_IMPORT_SETTING,
            _import_legacy_cron_once,
        )

        monkeypatch.setattr("gateway.cron.LEGACY_CRON_DB", tmp_legacy_db)
        _import_legacy_cron_once()

        with kitty_db.connect(tmp_kitty_db) as conn:
            rows = conn.execute("SELECT * FROM cron_schedules").fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "morning brief"

        with kitty_db.connect(tmp_kitty_db) as conn:
            setting = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (LEGACY_IMPORT_SETTING,),
            ).fetchone()
        assert setting is not None
        assert "imported 1 row" in setting[0]

        # Legacy file is never deleted.
        assert tmp_legacy_db.exists()

    def test_legacy_import_is_idempotent(
        self, tmp_kitty_db, tmp_legacy_db, monkeypatch
    ):
        from gateway.cron import _import_legacy_cron_once

        monkeypatch.setattr("gateway.cron.LEGACY_CRON_DB", tmp_legacy_db)
        _import_legacy_cron_once()
        _import_legacy_cron_once()
        _import_legacy_cron_once()

        with sqlite3.connect(tmp_kitty_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM cron_schedules").fetchone()[0]
        assert count == 1

    def test_legacy_import_skips_when_destination_non_empty(
        self, tmp_kitty_db, tmp_legacy_db, monkeypatch
    ):
        from gateway import db as kitty_db
        from gateway.cron import (
            LEGACY_IMPORT_SETTING,
            _import_legacy_cron_once,
        )

        with kitty_db.connect(tmp_kitty_db) as conn:
            conn.execute(
                "INSERT INTO cron_schedules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "live-1", "live", "brief.refresh", "daily", "07:00",
                    "{}", 1, 0.0, time.time(),
                ),
            )
            conn.commit()

        monkeypatch.setattr("gateway.cron.LEGACY_CRON_DB", tmp_legacy_db)
        _import_legacy_cron_once()

        with sqlite3.connect(tmp_kitty_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM cron_schedules").fetchone()[0]
            setting = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (LEGACY_IMPORT_SETTING,),
            ).fetchone()
        assert count == 1
        assert "skipped" in setting[0]

    def test_rollback_re_imports_from_intact_db(
        self, tmp_kitty_db, tmp_legacy_db, monkeypatch
    ):
        from gateway.cron import _import_legacy_cron_once

        monkeypatch.setattr("gateway.cron.LEGACY_CRON_DB", tmp_legacy_db)
        _import_legacy_cron_once()

        with sqlite3.connect(tmp_kitty_db) as conn:
            conn.execute("DELETE FROM cron_schedules")
            conn.execute("DELETE FROM app_settings WHERE key = 'cron_legacy_imported'")
            conn.commit()

        _import_legacy_cron_once()

        with sqlite3.connect(tmp_kitty_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM cron_schedules").fetchone()[0]
        assert count == 1

    def test_legacy_import_no_op_when_legacy_db_absent(
        self, tmp_kitty_db, monkeypatch, tmp_path
    ):
        from gateway.cron import _import_legacy_cron_once

        nonexistent = tmp_path / "does-not-exist.db"
        monkeypatch.setattr("gateway.cron.LEGACY_CRON_DB", nonexistent)
        _import_legacy_cron_once()

        with sqlite3.connect(tmp_kitty_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM cron_schedules").fetchone()[0]
        assert count == 0
