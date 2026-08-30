from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from gateway import image_recipes, image_sessions
from gateway.image_runner import JobResult
from gateway.routes import extended


@pytest.fixture(autouse=True)
def _scratch_kitty_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import gateway.paths as paths

    monkeypatch.setattr(paths, "KITTY_DB_FILE", tmp_path / "kitty.db")


@pytest.mark.asyncio
async def test_paid_generate_debits_session_and_refuses_next_over_budget_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = image_sessions.create_session(title="paid budget")
    image_sessions.record_attempt(session.session_id, cost_usd=4.85)
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("BFL_API_KEY", "test-key")

    recipe = SimpleNamespace(provider="flux", recipe_id="paid_flux")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: image_recipes.RoutingDecision(
            recipe_id="paid_flux", recipe=recipe, reason="paid test lane"
        ),
    )

    calls = 0

    async def fake_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return JobResult(
            job_id=f"job_{calls}", filename=f"image_{calls}.png", engine="flux"
        )

    monkeypatch.setattr("gateway.image_runner.run", fake_run)
    monkeypatch.setattr(image_sessions, "attach_job", lambda *_: None)

    request = extended.StudioGenerateRequest(
        prompt="portrait", session_id=session.session_id
    )
    await extended.studio_generate(request)

    after_first = image_sessions.require_session(session.session_id)
    assert calls == 1
    assert after_first.spend_usd == pytest.approx(4.85)
    assert after_first.reserved_spend_usd == pytest.approx(0.08)

    with pytest.raises(HTTPException) as exc:
        await extended.studio_generate(request)

    assert exc.value.status_code == 429
    assert calls == 1, "budget refusal must happen before another paid provider call"

@pytest.mark.asyncio
async def test_paid_generate_without_session_is_refused_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = SimpleNamespace(provider="flux", recipe_id="paid_flux")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: image_recipes.RoutingDecision(
            recipe_id="paid_flux", recipe=recipe, reason="paid test lane"
        ),
    )

    calls = 0

    async def fake_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return JobResult(job_id="job_1", filename="image.png", engine="flux")

    monkeypatch.setattr("gateway.image_runner.run", fake_run)

    request = extended.StudioGenerateRequest(prompt="portrait")
    with pytest.raises(HTTPException) as exc:
        await extended.studio_generate(request)

    assert exc.value.status_code == 400
    assert "session" in str(exc.value.detail).lower()
    assert calls == 0, "paid generation must not bypass the session budget"

@pytest.mark.asyncio
async def test_unavailable_paid_lane_does_not_consume_session_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = image_sessions.create_session(title="disabled paid lane")
    recipe = SimpleNamespace(provider="flux", recipe_id="paid_flux")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: image_recipes.RoutingDecision(
            recipe_id="paid_flux", recipe=recipe, reason="paid test lane"
        ),
    )
    monkeypatch.delenv("KITTY_IMAGE_PAID_ENABLED", raising=False)
    monkeypatch.delenv("BFL_API_KEY", raising=False)

    request = extended.StudioGenerateRequest(
        prompt="portrait", session_id=session.session_id
    )
    with pytest.raises(HTTPException):
        await extended.studio_generate(request)

    after = image_sessions.require_session(session.session_id)
    assert after.attempt_count == 0
    assert after.spend_usd == 0.0

@pytest.mark.asyncio
async def test_paid_generate_reconciles_reservation_to_provider_reported_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = image_sessions.create_session(title="actual paid cost")
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("BFL_API_KEY", "test-key")
    recipe = SimpleNamespace(provider="flux", recipe_id="paid_flux")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: image_recipes.RoutingDecision(
            recipe_id="paid_flux", recipe=recipe, reason="paid test lane"
        ),
    )

    async def fake_run(*args, **kwargs):
        result = JobResult(job_id="job_1", filename="image.png", engine="flux")
        result.cost_usd = 0.04
        return result

    monkeypatch.setattr("gateway.image_runner.run", fake_run)
    monkeypatch.setattr(image_sessions, "attach_job", lambda *_: None)

    await extended.studio_generate(
        extended.StudioGenerateRequest(
            prompt="portrait", session_id=session.session_id
        )
    )

    after = image_sessions.require_session(session.session_id)
    assert after.attempt_count == 1
    assert after.spend_usd == pytest.approx(0.04)

@pytest.mark.asyncio
async def test_definite_no_submit_failure_releases_reserved_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gateway import image_runner

    no_submit_error = getattr(image_runner, "ImageDispatchNotSubmittedError", None)
    assert no_submit_error is not None, "runner must distinguish definite no-submit failures"

    session = image_sessions.create_session(title="definite no submit")
    recipe = SimpleNamespace(provider="flux", recipe_id="paid_flux")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: image_recipes.RoutingDecision(
            recipe_id="paid_flux", recipe=recipe, reason="paid test lane"
        ),
    )
    monkeypatch.setattr(image_runner, "paid_engine_available", lambda _engine: (True, ""))

    async def fail_before_submit(*_args, **_kwargs):
        raise no_submit_error("request rejected before provider submission")

    monkeypatch.setattr(image_runner, "run", fail_before_submit)

    with pytest.raises(HTTPException):
        await extended.studio_generate(
            extended.StudioGenerateRequest(prompt="portrait", session_id=session.session_id)
        )

    after = image_sessions.require_session(session.session_id)
    assert after.spend_usd == 0.0
    assert after.reserved_spend_usd == 0.0
    assert after.attempt_count == 1


@pytest.mark.asyncio
async def test_ambiguous_paid_failure_keeps_unknown_exposure_reserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gateway import image_runner

    session = image_sessions.create_session(title="ambiguous paid outcome")
    recipe = SimpleNamespace(provider="flux", recipe_id="paid_flux")
    monkeypatch.setattr(
        image_recipes,
        "auto_route",
        lambda **_: image_recipes.RoutingDecision(
            recipe_id="paid_flux", recipe=recipe, reason="paid test lane"
        ),
    )
    monkeypatch.setattr(image_runner, "paid_engine_available", lambda _engine: (True, ""))

    async def ambiguous_failure(*_args, **_kwargs):
        raise image_runner.ImageRunnerError("provider outcome unknown after transport failure")

    monkeypatch.setattr(image_runner, "run", ambiguous_failure)

    with pytest.raises(HTTPException):
        await extended.studio_generate(
            extended.StudioGenerateRequest(prompt="portrait", session_id=session.session_id)
        )

    after = image_sessions.require_session(session.session_id)
    assert after.spend_usd == 0.0
    assert after.reserved_spend_usd == pytest.approx(0.08)
    assert after.attempt_count == 1
