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
