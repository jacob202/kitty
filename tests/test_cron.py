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

    def test_schedule_idempotent_exact_match(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule

        sid1 = schedule("sched-1", "brief.refresh", "interval", "60")
        sid2 = schedule("sched-2", "brief.refresh", "interval", "60")

        assert sid2 == sid1
        rows = list_schedules()
        assert len(rows) == 1
        assert rows[0]["id"] == sid1
        assert rows[0]["action"] == "brief.refresh"
        assert rows[0]["schedule_type"] == "interval"
        assert rows[0]["schedule_value"] == "60"

    def test_schedule_same_action_different_value_remains_distinct(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule

        sid_a = schedule("sched-a", "insights.return_due", "interval", "15")
        sid_b = schedule("sched-b", "insights.return_due", "interval", "30")

        assert sid_b != sid_a  # different schedule_value -> distinct schedules
        rows = list_schedules()
        assert len(rows) == 2
        values = {r["schedule_value"] for r in rows}
        assert values == {"15", "30"}

    def test_schedule_same_action_different_type_remains_distinct(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule

        sid_a = schedule("sched-a", "notify.daily", "daily", "08:00")
        sid_b = schedule("sched-b", "notify.daily", "interval", "60")

        assert sid_b != sid_a  # different schedule_type -> distinct schedules
        rows = list_schedules()
        assert len(rows) == 2
        types = {r["schedule_type"] for r in rows}
        assert types == {"daily", "interval"}

    def test_schedule_gateway_startup_does_not_create_duplicates(self, tmp_kitty_db):
        from gateway.cron import list_schedules, schedule

        params = ("insights return due", "insights.return_due", "interval", "15")
        for i in range(5):
            schedule(*params)

        rows = list_schedules()
        assert len(rows) == 1
        assert rows[0]["action"] == "insights.return_due"
        assert rows[0]["schedule_value"] == "15"

    def test_schedule_same_seed_name_after_edit_returns_same_id_preserves_value(self, tmp_kitty_db):
        """schedule() must reuse existing row when seed name matches (edited schedule preserved)."""
        from gateway import db as kitty_db
        from gateway.cron import list_schedules, schedule

        # Seed a schedule with a stable name
        sid1 = schedule("morning brief", "brief.deliver", "daily", "08:00", {"timezone": "America/Regina"})
        rows = list_schedules()
        assert len(rows) == 1
        assert rows[0]["schedule_value"] == "08:00"

        # User edits the schedule_value directly in DB (simulating UI/API edit)
        with kitty_db.connect(tmp_kitty_db) as conn:
            conn.execute(
                "UPDATE cron_schedules SET schedule_value = ? WHERE id = ?",
                ("07:30", sid1),
            )
            conn.commit()

        # Restart: schedule() called again with same seed name but original profile value
        # Must return same ID and preserve the EDITED value (07:30), not overwrite with 08:00
        sid2 = schedule("morning brief", "brief.deliver", "daily", "08:00", {"timezone": "America/Regina"})

        assert sid2 == sid1  # same stable identity
        rows = list_schedules()
        assert len(rows) == 1
        assert rows[0]["schedule_value"] == "07:30"  # user edit preserved, not overwritten

    def test_schedule_same_action_type_value_different_metadata_and_names_remain_distinct(self, tmp_kitty_db):
        """schedule() must NOT collapse rows when metadata differs, even if action/type/value match."""
        from gateway.cron import list_schedules, schedule

        # Two schedules with identical action/type/value but DIFFERENT metadata AND different names
        sid_a = schedule("sched-a", "brief.deliver", "daily", "08:00", {"timezone": "America/Regina"})
        sid_b = schedule("sched-b", "brief.deliver", "daily", "08:00", {"timezone": "America/Toronto"})

        # Must remain distinct (different metadata)
        assert sid_b != sid_a
        rows = list_schedules()
        assert len(rows) == 2
        metadatas = {r["metadata"] for r in rows}
        assert len(metadatas) == 2
        names = {r["name"] for r in rows}
        assert names == {"sched-a", "sched-b"}


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

    def test_ensure_schedule_updates_one_stable_automation_identity(self, tmp_kitty_db):
        from gateway.cron import ensure_schedule, list_schedules

        first = ensure_schedule(
            "morning brief",
            "brief.deliver",
            "daily",
            "08:00",
            {"timezone": "America/Regina"},
        )
        second = ensure_schedule(
            "morning brief",
            "brief.deliver",
            "daily",
            "07:30",
            {"timezone": "America/Toronto"},
        )

        assert second == first
        rows = [row for row in list_schedules() if row["name"] == "morning brief"]
        assert len(rows) == 1
        assert rows[0]["schedule_value"] == "07:30"
        assert rows[0]["metadata"] == '{"timezone": "America/Toronto"}'

    def test_ensure_schedule_preserves_disabled_state_and_last_run(self, tmp_kitty_db):
        from gateway import db as kitty_db
        from gateway.cron import ensure_schedule, list_schedules, toggle

        sid = ensure_schedule(
            "morning brief",
            "brief.deliver",
            "daily",
            "08:00",
            {"timezone": "America/Regina"},
        )
        with kitty_db.connect(tmp_kitty_db) as conn:
            conn.execute("UPDATE cron_schedules SET last_run = ? WHERE id = ?", (12345.0, sid))
            conn.commit()
        assert toggle(sid) is False

        assert ensure_schedule(
            "morning brief",
            "brief.deliver",
            "daily",
            "07:30",
            {"timezone": "America/Toronto"},
        ) == sid
        row = next(item for item in list_schedules() if item["id"] == sid)
        assert row["enabled"] == 0
        assert row["last_run"] == 12345.0


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

    def test_fractional_interval_supports_30_second_watchers(self):
        from gateway.cron import _should_fire

        now = time.time()
        s = {"schedule_type": "interval", "schedule_value": "0.5", "last_run": now - 31}
        assert _should_fire(s, now) is True

        s["last_run"] = now - 29
        assert _should_fire(s, now) is False

    def test_invalid_interval_returns_false(self):
        from gateway.cron import _should_fire
        s = {"schedule_type": "interval", "schedule_value": "not-a-number", "last_run": 0}
        assert _should_fire(s, time.time()) is False

    def test_daily_uses_configured_iana_timezone_and_local_date(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from gateway.cron import _should_fire

        eastern = ZoneInfo("America/Toronto")
        now = datetime(2026, 8, 23, 8, 1, tzinfo=eastern).timestamp()
        schedule = {
            "schedule_type": "daily",
            "schedule_value": "08:00",
            "last_run": datetime(2026, 8, 22, 8, 0, tzinfo=eastern).timestamp(),
            "metadata": '{"timezone": "America/Toronto"}',
        }
        assert _should_fire(schedule, now) is True

        schedule["last_run"] = datetime(2026, 8, 23, 8, 0, 30, tzinfo=eastern).timestamp()
        assert _should_fire(schedule, now) is False

    def test_daily_timezone_keeps_local_clock_across_dst(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from gateway.cron import _should_fire

        eastern = ZoneInfo("America/Toronto")
        schedule = {
            "schedule_type": "daily",
            "schedule_value": "08:00",
            "last_run": 0,
            "metadata": '{"timezone": "America/Toronto"}',
        }
        winter = datetime(2026, 1, 15, 8, 1, tzinfo=eastern).timestamp()
        summer = datetime(2026, 8, 15, 8, 1, tzinfo=eastern).timestamp()
        assert _should_fire(schedule, winter) is True
        assert _should_fire(schedule, summer) is True

    def test_daily_falls_back_to_profile_timezone_when_metadata_missing(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        import gateway.cron as cron_module
        from gateway.cron import _should_fire

        monkeypatch.setattr(cron_module, "_default_timezone_name", lambda: "America/Toronto")

        eastern = ZoneInfo("America/Toronto")
        now = datetime(2026, 8, 23, 8, 1, tzinfo=eastern).timestamp()
        schedule = {
            "schedule_type": "daily",
            "schedule_value": "08:00",
            "last_run": 0,
            "metadata": "{}",
        }
        assert _should_fire(schedule, now) is True

    def test_daily_explicit_timezone_overrides_profile_default(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        import gateway.cron as cron_module
        from gateway.cron import _should_fire

        monkeypatch.setattr(cron_module, "_default_timezone_name", lambda: "America/Regina")

        eastern = ZoneInfo("America/Toronto")
        now = datetime(2026, 8, 23, 8, 1, tzinfo=eastern).timestamp()
        schedule = {
            "schedule_type": "daily",
            "schedule_value": "08:00",
            "last_run": 0,
            "metadata": '{"timezone": "America/Toronto"}',
        }
        assert _should_fire(schedule, now) is True

    def test_daily_unknown_timezone_does_not_fire(self):
        from gateway.cron import _should_fire

        schedule = {
            "schedule_type": "daily",
            "schedule_value": "08:00",
            "last_run": 0,
            "metadata": '{"timezone": "Not/AZone"}',
        }
        assert _should_fire(schedule, time.time()) is False

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


class TestDefaultTimezoneName:
    def test_reads_configured_profile_timezone(self, tmp_path, monkeypatch):
        import gateway.cron as cron_module

        profile = tmp_path / "user_profile.json"
        profile.write_text('{"timezone": "America/Toronto"}', encoding="utf-8")
        monkeypatch.setattr(cron_module, "USER_PROFILE_PATH", profile)
        assert cron_module._default_timezone_name() == "America/Toronto"

    def test_falls_back_when_profile_missing(self, tmp_path, monkeypatch):
        import gateway.cron as cron_module

        monkeypatch.setattr(cron_module, "USER_PROFILE_PATH", tmp_path / "missing.json")
        assert cron_module._default_timezone_name() == cron_module.DEFAULT_TIMEZONE

    def test_falls_back_when_profile_has_no_timezone_key(self, tmp_path, monkeypatch):
        import gateway.cron as cron_module

        profile = tmp_path / "user_profile.json"
        profile.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(cron_module, "USER_PROFILE_PATH", profile)
        assert cron_module._default_timezone_name() == cron_module.DEFAULT_TIMEZONE


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
