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
    import gateway.telegram_bot as telegram_bot

    monkeypatch.setenv("KITTY_ENV", "test")
    monkeypatch.setattr(app_module, "validate_dirs", lambda: None)
    monkeypatch.setattr(app_module, "validate_env", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_jobs_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_batches_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_agent_workspace_turns_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_autonomy_sessions_on_startup", lambda: None)
    monkeypatch.setattr(image_recipes, "seed_default_recipes", lambda: None)

    started: list[str] = []

    async def image_batch_loop(*_args, **_kwargs) -> None:
        started.append("image-batch-worker")
        await asyncio.Event().wait()

    monkeypatch.setattr(image_batches, "worker_loop", image_batch_loop)
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


@pytest.mark.asyncio
async def test_gateway_registers_inbox_scan_with_cron_not_private_loop(monkeypatch):
    import gateway.app as app_module
    import gateway.brief_scheduler as brief_scheduler
    import gateway.cron as cron
    import gateway.image_batches as image_batches
    import gateway.image_recipes as image_recipes
    import gateway.inbox_watcher as inbox_watcher
    import gateway.telegram_bot as telegram_bot

    monkeypatch.setenv("KITTY_ENV", "development")
    monkeypatch.setattr(app_module, "validate_dirs", lambda: None)
    monkeypatch.setattr(app_module, "validate_env", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_jobs_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_batches_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_agent_workspace_turns_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_autonomy_sessions_on_startup", lambda: None)
    monkeypatch.setattr(image_recipes, "seed_default_recipes", lambda: None)
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)

    async def forever(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(image_batches, "worker_loop", forever)
    monkeypatch.setattr(brief_scheduler, "start_brief_scheduler", lambda: None)

    scans: list[str] = []
    monkeypatch.setattr(inbox_watcher, "scan_once", lambda: scans.append("scan"))

    actions: dict[str, object] = {}
    schedules: list[tuple] = []
    monkeypatch.setattr(cron, "register_action", lambda name, fn: actions.__setitem__(name, fn))
    monkeypatch.setattr(cron, "schedule", lambda *args, **kwargs: schedules.append(args) or "sid")
    monkeypatch.setattr(cron, "start", lambda: None)

    async with app_module.lifespan(app_module.app):
        assert "inbox.scan" in actions
        assert "traces.compact" in actions
        assert ("brief cache refresh", "brief.refresh", "interval", "15") in schedules
        assert ("web monitor due checks", "monitors.check", "interval", "5") in schedules
        assert ("iCloud inbox scan", "inbox.scan", "interval", "0.5") in schedules
        assert ("trace log compaction", "traces.compact", "daily", "03:30") in schedules
        await actions["inbox.scan"]()  # type: ignore[operator]
        assert scans == ["scan"]


@pytest.mark.asyncio
async def test_lifespan_reconciles_autonomy_sessions_left_active_by_the_previous_process(
    monkeypatch,
):
    """Startup is the only moment that can prove no executor survived."""
    import gateway.app as app_module
    import gateway.autonomy_state as autonomy_state
    import gateway.brief_scheduler as brief_scheduler
    import gateway.cron as cron
    import gateway.image_batches as image_batches
    import gateway.image_recipes as image_recipes
    import gateway.telegram_bot as telegram_bot

    monkeypatch.setenv("KITTY_ENV", "test")
    monkeypatch.setattr(app_module, "validate_dirs", lambda: None)
    monkeypatch.setattr(app_module, "validate_env", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_jobs_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_image_batches_on_startup", lambda: None)
    monkeypatch.setattr(app_module, "_reconcile_agent_workspace_turns_on_startup", lambda: None)
    monkeypatch.setattr(image_recipes, "seed_default_recipes", lambda: None)
    monkeypatch.setattr(telegram_bot, "is_configured", lambda: False)

    async def forever(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(image_batches, "worker_loop", forever)
    monkeypatch.setattr(brief_scheduler, "start_brief_scheduler", lambda: None)
    monkeypatch.setattr(cron, "register_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(cron, "schedule", lambda *args, **kwargs: None)
    monkeypatch.setattr(cron, "start", lambda: None)

    calls: list[str] = []
    monkeypatch.setattr(
        autonomy_state,
        "interrupt_active_sessions",
        lambda: calls.append("reconciled") or 0,
    )

    async with app_module.lifespan(app_module.app):
        assert calls == ["reconciled"]
