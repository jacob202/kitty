"""Cron wrappers for blocking life-awareness/provider work."""
from __future__ import annotations

import asyncio


def _run_evening_reflection() -> None:
    from gateway.life_awareness import evening_reflection
    from gateway.push import push_to_jacob

    result = evening_reflection()
    push_result = push_to_jacob(
        result.get("reflection", "")[:300],
        kind="info",
        title="Kitty Evening Reflection",
    )
    if isinstance(push_result, dict):
        ok = push_result.get("ok", False)
    else:
        ok = push_result
    if not ok:
        raise Exception("Evening reflection push failed")


def _run_morning_proactive() -> None:
    from gateway.life_awareness import morning_proactive
    from gateway.push import push_to_jacob

    result = morning_proactive()
    suggestions = result.get("proactive_suggestions", [])
    if suggestions:
        text = suggestions[0].get("text", "")
        push_result = push_to_jacob(text, kind="info", title="Life Suggestion")
        if isinstance(push_result, dict):
            ok = push_result.get("ok", False)
        else:
            ok = push_result
        if not ok:
            raise Exception("Morning proactive push failed")


async def _to_thread_attached(fn) -> None:
    task = asyncio.create_task(asyncio.to_thread(fn))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    task.result()
    if cancelled:
        raise asyncio.CancelledError()


async def evening_reflection_action() -> None:
    await _to_thread_attached(_run_evening_reflection)


async def morning_proactive_action() -> None:
    await _to_thread_attached(_run_morning_proactive)
