from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_gateway_supervises_background_service_lifecycle(monkeypatch):
    import gateway.app as app_module
    import gateway.automation_supervisor as supervision
    import gateway.cron as cron
    import gateway.image_batches as image_batches
    import gateway.image_recipes as image_recipes
    import gateway.telegram_bot as telegram_bot

    monkeypatch.setenv("KITTY_ENV", "development")
    monkeypatch.setattr(app_module, "validate_dirs", lambda: None)
    monkeypatch.setattr(app_module, "validate_env", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_jobs_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_batches_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_agent_workspace_turns_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_autonomy_sessions_on_startup", lambda: None)
    monkeypatch.setattr(image_recipes, "seed_default_recipes", lambda: None)

    async def forever(*_args, **_kwargs):
        await asyncio.Event().wait()

    telegram_task: asyncio.Task | None = None
    cron_task: asyncio.Task | None = None

    monkeypatch.setattr(image_batches, "worker_loop", forever)
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)

    def start_telegram():
        nonlocal telegram_task
        telegram_task = asyncio.create_task(asyncio.sleep(0))
        return telegram_task

    async def stop_telegram():
        return None

    def start_cron():
        nonlocal cron_task
        cron_task = asyncio.create_task(asyncio.sleep(0))
        return cron_task

    async def stop_cron():
        return None

    monkeypatch.setattr(telegram_bot, "start_polling", start_telegram)
    monkeypatch.setattr(telegram_bot, "stop", stop_telegram)
    monkeypatch.setattr(cron, "start", start_cron)
    monkeypatch.setattr(cron, "stop", stop_cron, raising=False)
    monkeypatch.setattr(cron, "register_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(cron, "schedule", lambda *args, **kwargs: "sid")
    monkeypatch.setattr(cron, "ensure_schedule", lambda *args, **kwargs: "brief-id")

    tracked: list[tuple[str, object, object]] = []
    recoverable: list[tuple[str, object, object]] = []
    stopped: list[str] = []
    monkeypatch.setattr(
        supervision.supervisor,
        "track_task",
        lambda name, task, **kwargs: tracked.append((name, task, kwargs.get("stop"))),
    )
    monkeypatch.setattr(
        supervision.supervisor,
        "track_recoverable",
        lambda name, factory, **kwargs: recoverable.append((name, factory, kwargs.get("stop"))),
    )

    async def stop_all():
        stopped.append("all")
        for _name, task, _stop in tracked:
            if isinstance(task, asyncio.Task) and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    monkeypatch.setattr(supervision.supervisor, "stop_all", stop_all)

    async with app_module.lifespan(app_module.app):
        supervised = set()
        for name, _task, _stop in tracked:
            supervised.add(name)
        for name, _factory, _stop in recoverable:
            supervised.add(name)
        assert supervised == {
            "cron",
            "image-batch-worker",
            "image-recovery",
            "telegram",
        }
        assert next(stop for name, _factory, stop in recoverable if name == "cron") is stop_cron
        assert next(stop for name, _factory, stop in recoverable if name == "telegram") is stop_telegram
        assert next(factory for name, factory, _stop in recoverable if name == "image-batch-worker") is not None

    assert stopped == ["all"]
