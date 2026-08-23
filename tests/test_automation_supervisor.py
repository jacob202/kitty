from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_supervisor_tracks_running_failure_and_shutdown():
    from gateway.automation_supervisor import AutomationSupervisor

    supervisor = AutomationSupervisor()
    hold = asyncio.Event()

    async def healthy():
        await hold.wait()

    task = asyncio.create_task(healthy())
    supervisor.track_task("healthy", task)
    assert supervisor.get_status("healthy")["status"] == "available"

    await supervisor.stop_all()
    assert task.cancelled()
    assert supervisor.get_status("healthy")["status"] == "unavailable"


@pytest.mark.asyncio
async def test_supervisor_isolates_failed_service():
    from gateway.automation_supervisor import AutomationSupervisor

    supervisor = AutomationSupervisor()
    hold = asyncio.Event()

    async def healthy():
        await hold.wait()

    async def boom():
        raise RuntimeError("watcher crashed")

    healthy_task = asyncio.create_task(healthy())
    failed_task = asyncio.create_task(boom())
    supervisor.track_task("healthy", healthy_task)
    supervisor.track_task("failed", failed_task)
    with pytest.raises(RuntimeError, match="watcher crashed"):
        await failed_task

    assert supervisor.get_status("failed")["status"] == "degraded"
    assert "watcher crashed" in supervisor.get_status("failed")["reason"]
    assert supervisor.get_status("healthy")["status"] == "available"

    await supervisor.stop_all()


def test_supervisor_can_report_stale_from_heartbeat_age(monkeypatch):
    import gateway.automation_supervisor as module

    supervisor = module.AutomationSupervisor()
    monkeypatch.setattr(module.time, "time", lambda: 100.0)
    supervisor.mark("cron", "available", reason="runner active", stale_after=30.0)
    supervisor.heartbeat("cron")

    monkeypatch.setattr(module.time, "time", lambda: 131.0)
    status = supervisor.get_status("cron")
    assert status["status"] == "stale"
    assert "heartbeat" in status["reason"]


def test_supervisor_status_vocabulary_is_bounded():
    from gateway.automation_supervisor import VALID_STATUSES

    assert VALID_STATUSES == {
        "available",
        "degraded",
        "stale",
        "unavailable",
        "unknown",
    }


@pytest.mark.asyncio
async def test_shutdown_isolates_one_stop_failure():
    from gateway.automation_supervisor import AutomationSupervisor

    supervisor = AutomationSupervisor()
    stopped: list[str] = []

    async def broken_stop():
        stopped.append("broken")
        raise RuntimeError("cannot stop")

    async def healthy_stop():
        stopped.append("healthy")

    supervisor.mark("broken", "available", reason="running")
    supervisor.mark("healthy", "available", reason="running")
    supervisor._services["broken"].stop = broken_stop
    supervisor._services["healthy"].stop = healthy_stop

    await supervisor.stop_all()

    assert stopped == ["healthy", "broken"]
    assert supervisor.get_status("healthy")["status"] == "unavailable"
    assert supervisor.get_status("broken")["status"] == "degraded"
    assert "cannot stop" in supervisor.get_status("broken")["reason"]
