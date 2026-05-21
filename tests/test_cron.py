"""Tests for gateway/cron.py — schedule CRUD and toggle."""
import time
import pytest
from unittest.mock import AsyncMock, patch


def _clear_db():
    from gateway.cron import CRON_DB, init_db
    import sqlite3
    init_db()
    with sqlite3.connect(CRON_DB) as conn:
        conn.execute("DELETE FROM schedules")
        conn.commit()


class TestSchedule:
    def test_schedule_returns_id(self):
        _clear_db()
        from gateway.cron import schedule
        sid = schedule("test", "brief.refresh", "daily", "08:00")
        assert isinstance(sid, str) and len(sid) > 0

    def test_schedule_appears_in_list(self):
        _clear_db()
        from gateway.cron import schedule, list_schedules
        schedule("my job", "nudges.check", "interval", "60")
        rows = list_schedules()
        assert any(r["name"] == "my job" for r in rows)

    def test_schedule_defaults(self):
        _clear_db()
        from gateway.cron import schedule, list_schedules
        schedule("default-test", "brief.refresh")
        row = list_schedules()[0]
        assert row["schedule_type"] == "daily"
        assert row["schedule_value"] == "07:00"
        assert row["enabled"] == 1


class TestRemove:
    def test_remove_existing(self):
        _clear_db()
        from gateway.cron import schedule, remove, list_schedules
        sid = schedule("to remove", "brief.refresh")
        assert remove(sid) is True
        assert not any(r["id"] == sid for r in list_schedules())

    def test_remove_nonexistent(self):
        _clear_db()
        from gateway.cron import remove
        assert remove("no-such-id") is False


class TestToggle:
    def test_toggle_disables(self):
        _clear_db()
        from gateway.cron import schedule, toggle, list_schedules
        sid = schedule("toggle-me", "nudges.check")
        state = toggle(sid)
        assert state is False
        row = next(r for r in list_schedules() if r["id"] == sid)
        assert row["enabled"] == 0

    def test_toggle_reenables(self):
        _clear_db()
        from gateway.cron import schedule, toggle
        sid = schedule("re-enable", "brief.refresh")
        toggle(sid)       # disable
        state = toggle(sid)  # re-enable
        assert state is True

    def test_toggle_nonexistent(self):
        from gateway.cron import toggle
        assert toggle("ghost-id") is None


class TestGetActions:
    def test_get_actions_returns_list(self):
        from gateway.cron import get_actions
        result = get_actions()
        assert isinstance(result, list)

    def test_register_and_get(self):
        from gateway.cron import register_action, get_actions
        async def _noop(): pass
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
