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
    image_sessions.record_attempt(session.session_id, cost_usd=4.96)

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
    assert after_first.spend_usd == pytest.approx(4.985)

    with pytest.raises(HTTPException) as exc:
        await extended.studio_generate(request)

    assert exc.value.status_code == 429
    assert calls == 1, "budget refusal must happen before another paid provider call"
