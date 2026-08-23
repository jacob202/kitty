"""Read-only API coverage for Automation Run evidence."""

from __future__ import annotations

import pytest


@pytest.fixture
def automation_db(tmp_path, monkeypatch):
    from gateway import automation_runs, cron
    from gateway import db as kitty_db

    db_file = tmp_path / "kitty.db"
    kitty_db.migrate(db_file=db_file)
    monkeypatch.setattr(automation_runs, "DB_FILE", db_file)
    monkeypatch.setattr(cron, "KITTY_DB_FILE", db_file)
    return db_file


@pytest.mark.asyncio
async def test_cron_runs_route_returns_bounded_run_evidence(automation_db):
    from gateway import automation_runs
    from gateway.routes import cron as cron_routes

    run = automation_runs.begin_run(
        automation_id="sched-1",
        action="brief.deliver",
        trigger_kind="manual",
        started_at=10.0,
    )
    automation_runs.finish_run(run["id"], status="completed", completed_at=11.0)

    payload = await cron_routes.cron_list_runs(automation_id="sched-1", action=None, limit=10)

    assert [item["id"] for item in payload["runs"]] == [run["id"]]
    assert payload["runs"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_schedule_status_keeps_history_when_schedule_is_disabled(automation_db):
    from gateway import automation_runs, cron
    from gateway.routes import cron as cron_routes

    sid = cron.schedule("morning brief", "brief.deliver", "daily", "08:00")
    run = automation_runs.begin_run(
        automation_id=sid,
        action="brief.deliver",
        trigger_kind="time",
        due_at=100.0,
        started_at=100.0,
    )
    automation_runs.finish_run(run["id"], status="completed", completed_at=101.0)
    assert cron.toggle(sid) is False

    payload = await cron_routes.cron_schedule_status(sid)

    assert payload["execution"]["state"] == "disabled"
    assert payload["latest_run"]["id"] == run["id"]
    assert payload["latest_run"]["status"] == "completed"
