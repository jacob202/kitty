from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_studio_generate_returns_provider_reported_actual_cost(monkeypatch) -> None:
    from gateway import image_agent, image_recipes, image_runner, image_sessions
    from gateway.routes.extended import StudioGenerateRequest, studio_generate

    recipe = SimpleNamespace(provider="openrouter", recipe_id="hosted")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: SimpleNamespace(recipe=recipe, reason="hosted test lane"),
    )
    monkeypatch.setattr(image_runner, "estimated_cost_usd", lambda _engine: 0.15)
    monkeypatch.setattr(image_runner, "paid_engine_available", lambda _engine: (True, ""))
    monkeypatch.setattr(
        image_agent,
        "AgentBudget",
        lambda: SimpleNamespace(max_attempts=10, max_spend_usd=5.0),
    )

    async def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            job_id="imgjob_paid",
            filename="paid.png",
            recipe="hosted",
            cost_usd=0.041,
        )

    monkeypatch.setattr(image_runner, "run", fake_run)
    monkeypatch.setattr(image_sessions, "reserve_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(image_sessions, "attach_job", lambda *_args, **_kwargs: None)
    reconciled: dict[str, float] = {}

    def fake_reconcile(_session_id: str, *, reserved_cost_usd: float, actual_cost_usd: float):
        reconciled.update(reserved=reserved_cost_usd, actual=actual_cost_usd)

    monkeypatch.setattr(image_sessions, "reconcile_reserved_attempt_cost", fake_reconcile)

    result = await studio_generate(
        StudioGenerateRequest(prompt="cat", session_id="imgses_test")
    )

    assert result["actual_cost_usd"] == pytest.approx(0.041)
    assert reconciled == {"reserved": pytest.approx(0.15), "actual": pytest.approx(0.041)}


@pytest.mark.asyncio
async def test_studio_generate_keeps_local_provider_cost_unknown(monkeypatch) -> None:
    from gateway import image_recipes, image_runner
    from gateway.routes.extended import StudioGenerateRequest, studio_generate

    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: SimpleNamespace(recipe=None, reason="local test lane"),
    )
    monkeypatch.setattr(image_runner, "estimated_cost_usd", lambda _engine: 0.0)

    async def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            job_id="imgjob_local",
            filename="local.png",
            recipe=None,
            cost_usd=None,
        )

    monkeypatch.setattr(image_runner, "run", fake_run)

    result = await studio_generate(StudioGenerateRequest(prompt="cat"))

    assert result["actual_cost_usd"] is None


@pytest.mark.asyncio
async def test_batch_executor_records_propagated_actual_cost(monkeypatch) -> None:
    from gateway import image_jobs
    from gateway.routes import extended, image_studio_jobs

    async def fake_studio_generate(_request):
        return {
            "job_id": "imgjob_paid",
            "filename": "paid.png",
            "actual_cost_usd": 0.041,
        }

    monkeypatch.setattr(extended, "studio_generate", fake_studio_generate)
    monkeypatch.setattr(
        image_jobs,
        "get_job",
        lambda _job_id: SimpleNamespace(
            job_id="imgjob_paid",
            provider="openrouter",
            model_id="vendor/image",
            operation="txt2img",
        ),
    )
    observed: dict = {}
    monkeypatch.setattr(
        image_studio_jobs.image_estimates,
        "record_observation",
        lambda **kwargs: observed.update(kwargs),
    )

    result = await image_studio_jobs.execute_studio_batch_request({"prompt": "cat"})

    assert result["actual_cost_usd"] == pytest.approx(0.041)
    assert observed["actual_cost_usd"] == pytest.approx(0.041)
    assert observed["provider"] == "openrouter"
    assert observed["model_id"] == "vendor/image"
    assert observed["operation"] == "txt2img"
    assert observed["duration_seconds"] > 0


@pytest.mark.asyncio
async def test_batch_executor_warns_when_returned_job_is_not_visible(monkeypatch, caplog) -> None:
    from gateway import image_jobs
    from gateway.routes import extended, image_studio_jobs

    async def fake_studio_generate(_request):
        return {
            "job_id": "imgjob_missing",
            "filename": "missing.png",
            "actual_cost_usd": 0.041,
        }

    monkeypatch.setattr(extended, "studio_generate", fake_studio_generate)
    monkeypatch.setattr(image_jobs, "get_job", lambda _job_id: None)

    await image_studio_jobs.execute_studio_batch_request({"prompt": "cat"})

    assert "imgjob_missing" in caplog.text
    assert "observation" in caplog.text.lower()
