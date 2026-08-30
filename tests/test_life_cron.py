from __future__ import annotations

import asyncio
import time

import pytest

from gateway import life_cron


@pytest.mark.asyncio
@pytest.mark.parametrize("action_name,runner_name", [
    ("evening_reflection_action", "_run_evening_reflection"),
    ("morning_proactive_action", "_run_morning_proactive"),
])
async def test_life_cron_blocking_work_does_not_block_event_loop(monkeypatch, action_name, runner_name):
    def slow_runner() -> None:
        time.sleep(0.15)

    monkeypatch.setattr(life_cron, runner_name, slow_runner)
    action = getattr(life_cron, action_name)

    started = asyncio.get_running_loop().time()
    task = asyncio.create_task(action())
    await asyncio.sleep(0.02)
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.08
    await task


@pytest.mark.asyncio
async def test_thread_action_waits_for_worker_before_propagating_cancellation(monkeypatch) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_to_thread(_fn):
        started.set()
        await release.wait()

    monkeypatch.setattr(life_cron.asyncio, "to_thread", fake_to_thread)
    task = asyncio.create_task(life_cron.evening_reflection_action())
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()

    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
