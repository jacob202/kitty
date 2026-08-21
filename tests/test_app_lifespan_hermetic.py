from __future__ import annotations

import asyncio

import pytest


@pytest.mark.asyncio
async def test_test_env_skips_external_background_services(monkeypatch):
    import gateway.app as app_module
    import gateway.brief_scheduler as brief_scheduler
    import gateway.cron as cron
    import gateway.image_batches as image_batches
    import gateway.image_recipes as image_recipes
    import gateway.inbox_watcher as inbox_watcher
    import gateway.telegram_bot as telegram_bot

    monkeypatch.setenv("KITTY_ENV", "test")
    monkeypatch.setattr(app_module, "validate_dirs", lambda: None)
    monkeypatch.setattr(app_module, "validate_env", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_jobs_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_batches_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_agent_workspace_turns_on_startup", lambda: None)
    monkeypatch.setattr(image_recipes, "seed_default_recipes", lambda: None)

    started: list[str] = []

    async def brief_loop() -> None:
        started.append("brief-loop")
        await asyncio.Event().wait()

    async def inbox_loop() -> None:
        started.append("inbox-watcher")
        await asyncio.Event().wait()

    async def image_batch_loop(*_args, **_kwargs) -> None:
        started.append("image-batch-worker")
        await asyncio.Event().wait()

    monkeypatch.setattr(app_module, "_brief_bg_loop", brief_loop)
    monkeypatch.setattr(image_batches, "worker_loop", image_batch_loop)
    monkeypatch.setattr(inbox_watcher, "watch_loop", inbox_loop)
    monkeypatch.setattr(brief_scheduler, "start_brief_scheduler", lambda: started.append("brief-scheduler"))
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: True)
    monkeypatch.setattr(telegram_bot, "start_polling", lambda: started.append("telegram"))
    monkeypatch.setattr(telegram_bot, "stop", lambda: asyncio.sleep(0))
    monkeypatch.setattr(cron, "register_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(cron, "schedule", lambda *args, **kwargs: None)
    monkeypatch.setattr(cron, "start", lambda: started.append("cron"))

    async with app_module.lifespan(app_module.app):
        await asyncio.sleep(0)
        assert started == []
