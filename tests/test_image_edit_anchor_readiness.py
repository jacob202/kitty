"""Regression coverage for IL-01 anchor invariants."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway import image_jobs, image_plan_store
from gateway import image_sessions as sessions
from gateway.image_plan_types import build_image_plan
from gateway.image_plan_store import PlanMalformedError, PlanStoreError, persist_plan
from gateway.routes import extended


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    test_db = tmp_path / "kitty.db"
    import gateway.paths as gp

    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    image_plan_store._ensure_db(conn)
    conn.commit()
    conn.close()

    yield

    gp.KITTY_DB_FILE = original


def test_txt2img_plan_rejects_anchor_instead_of_persisting_inconsistent_state():
    """Only img2img plans may carry an anchor job id."""
    session = sessions.create_session(title="generate")

    with pytest.raises(PlanStoreError, match="txt2img.*anchor_job_id"):
        persist_plan(
            session.session_id,
            build_image_plan("a new portrait"),
            operation="txt2img",
            anchor_job_id="imgjob_stale_anchor",
        )


def test_txt2img_row_with_anchor_fails_loud_when_reloaded():
    """An out-of-band stale anchor must not survive as valid txt2img state."""
    session = sessions.create_session(title="generate")
    stored = persist_plan(session.session_id, build_image_plan("a new portrait"))

    import gateway.paths as gp

    with sqlite3.connect(gp.KITTY_DB_FILE) as conn:
        conn.execute(
            "UPDATE image_plans SET anchor_job_id = ? WHERE plan_id = ?",
            ("imgjob_stale_anchor", stored.plan_id),
        )
        conn.commit()

    with pytest.raises(PlanMalformedError, match="txt2img.*anchor_job_id"):
        image_plan_store.require_plan(stored.plan_id)


@pytest.mark.asyncio
async def test_edit_refuses_running_anchor_before_renderer(monkeypatch):
    """A session-owned anchor must be SUCCEEDED before edit dispatch begins."""
    session = sessions.create_session(title="anchor readiness")
    anchor = image_jobs.create_job(
        provider="comfyui", operation="txt2img", prompt="source portrait"
    )
    image_jobs.transition(anchor.job_id, image_jobs.ImageJobStatus.SUBMITTED)
    image_jobs.transition(anchor.job_id, image_jobs.ImageJobStatus.RUNNING)
    sessions.attach_job(session.session_id, anchor.job_id)

    stored = persist_plan(
        session.session_id,
        build_image_plan("make the jacket darker"),
        operation="img2img",
        anchor_job_id=anchor.job_id,
    )

    def fake_auto_route(**_kwargs):
        from gateway.image_recipes import Recipe, RoutingDecision

        recipe = Recipe(
            recipe_id="r_edit",
            display_name="Edit",
            description=None,
            provider="comfyui",
            workflow_template_id=None,
            model_family=None,
            supports_img2img=True,
        )
        return RoutingDecision(recipe.recipe_id, recipe, "test")

    async def fail_dispatch(*_args, **_kwargs):
        raise AssertionError("anchor readiness must be rejected before renderer dispatch")

    monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)
    monkeypatch.setattr("gateway.image_runner.run_edit", fail_dispatch)
    monkeypatch.setattr("gateway.image_runner.run", fail_dispatch)

    with pytest.raises(HTTPException) as exc:
        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable request text",
                plan_id=stored.plan_id,
                session_id=session.session_id,
            )
        )

    assert exc.value.status_code == 400
    assert "only a succeeded job can be edited" in str(exc.value.detail)
