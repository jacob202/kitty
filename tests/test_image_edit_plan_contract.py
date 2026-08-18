from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway import image_plans
from gateway import image_sessions as sessions
from gateway.routes import extended


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as gp

    test_db = tmp_path / "kitty.db"
    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    image_plans._ensure_db(conn)
    conn.commit()
    conn.close()

    yield test_db
    gp.KITTY_DB_FILE = original


def test_edit_plan_round_trips_operation_and_anchor():
    session = sessions.create_session()
    stored = image_plans.persist_plan(
        session.session_id,
        {
            "original_prompt": "make the jacket blue",
            "refined_prompt": "make the jacket blue",
            "operation": "img2img",
            "anchor_job_id": "imgjob_anchor",
            "guidance_tags": [],
            "references": [],
        },
    )

    resumed = image_plans.require_plan(stored.plan_id)
    assert stored.operation == "img2img"
    assert stored.anchor_job_id == "imgjob_anchor"
    assert resumed.operation == "img2img"
    assert resumed.anchor_job_id == "imgjob_anchor"


@pytest.mark.asyncio
async def test_generate_dispatches_approved_edit_through_bound_anchor(monkeypatch):
    session = sessions.create_session()
    captured: dict[str, object] = {}

    stored = SimpleNamespace(
        plan_id="imgplan_edit",
        session_id=session.session_id,
        refined_prompt="make the jacket blue",
        character_id=None,
        recipe_id=None,
        guidance_tags=[],
        operation="img2img",
        anchor_job_id="imgjob_anchor",
    )
    monkeypatch.setattr(image_plans, "require_approved_plan", lambda *_args: stored)

    def fake_auto_route(**kwargs):
        captured["route_operation"] = kwargs["operation"]
        from gateway.image_recipes import Recipe, RoutingDecision

        recipe = Recipe(
            recipe_id="r_edit",
            display_name="Edit",
            description=None,
            provider="comfyui",
            workflow_template_id=None,
            model_family=None,
        )
        return RoutingDecision(recipe.recipe_id, recipe, "test")

    async def fail_generate(*_args, **_kwargs):
        raise AssertionError("approved img2img plan must not use text-to-image run()")

    async def fake_run_edit(prompt: str, *, anchor_job_id: str, **kwargs):
        captured.update(
            {
                "prompt": prompt,
                "anchor_job_id": anchor_job_id,
                "edit_kwargs": kwargs,
            }
        )
        from gateway import image_jobs
        from gateway.image_runner import JobResult

        job = image_jobs.create_job(
            provider="kitty_worker",
            operation="img2img",
            prompt=prompt,
            parent_id=anchor_job_id,
        )
        return JobResult(
            job_id=job.job_id,
            filename="/tmp/edit.png",
            engine="kitty_worker",
        )

    monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)
    monkeypatch.setattr("gateway.image_runner.run", fail_generate)
    monkeypatch.setattr("gateway.image_runner.run_edit", fake_run_edit)

    await extended.studio_generate(
        extended.StudioGenerateRequest(
            prompt="mutable live text must be ignored",
            plan_id=stored.plan_id,
            session_id=session.session_id,
        )
    )

    assert captured["route_operation"] == "img2img"
    assert captured["prompt"] == stored.refined_prompt
    assert captured["anchor_job_id"] == "imgjob_anchor"
