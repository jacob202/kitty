"""Tests for persisted, session-owned image plans (issue #336, slice A2).

Covers the A2 acceptance: generation dispatched from a stored approved plan
uses that plan's refined prompt and guidance tags, a mutated form field after
approval cannot change what renders, cross-session and unapproved plans are
rejected, guidance tags reach the renderer request, and a plan survives a
store reopen.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway import image_jobs, image_plans
from gateway import image_sessions as sessions
from gateway.image_plans import (
    PlanMalformedError,
    PlanNotApprovedError,
    PlanNotFoundError,
    PlanSessionMismatchError,
    PlanStatus,
    PlanStoreError,
    persist_plan,
    require_approved_plan,
)
from gateway.routes import extended


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

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


def _build_plan(character_id: str | None = None):
    from gateway.image_plan import build_image_plan

    return build_image_plan(
        "a cozy portrait in soft light",
        character_id=character_id,
        guidance_tags=["text_rendering"],
    )


class TestPersistAndLoad:
    def test_persist_returns_stable_approved_plan(self):
        s = sessions.create_session(title="James portraits")
        plan = _build_plan()
        stored = persist_plan(s.session_id, plan)

        assert stored.plan_id.startswith("imgplan_")
        assert stored.session_id == s.session_id
        assert stored.status is PlanStatus.APPROVED
        assert stored.guidance_tags == ["text_rendering"]
        assert "soft light" in stored.refined_prompt
        assert stored.original_prompt == "a cozy portrait in soft light"

    def test_plan_survives_store_reopen(self):
        """Restart-resume: a new connection must see the same approved plan."""
        s = sessions.create_session()
        plan = _build_plan()
        stored = persist_plan(s.session_id, plan)

        resumed = image_plans.require_plan(stored.plan_id)
        assert resumed.refined_prompt == stored.refined_prompt
        assert resumed.guidance_tags == ["text_rendering"]
        assert resumed.session_id == s.session_id
        assert resumed.status is PlanStatus.APPROVED

    def test_get_plan_returns_none_for_unknown(self):
        assert image_plans.get_plan("imgplan_nope") is None

    def test_persist_requires_existing_session(self):
        with pytest.raises(PlanStoreError, match="session"):
            persist_plan("imgses_nope", _build_plan())

    def test_persist_rejects_empty_original_prompt(self):
        s = sessions.create_session()

        class _Empty:
            def to_dict(self):
                return {"original_prompt": "   ", "refined_prompt": "x", "guidance_tags": []}

        with pytest.raises(PlanStoreError, match="empty original prompt"):
            persist_plan(s.session_id, _Empty())


class TestDispatchGate:
    def test_require_approved_plan_round_trips(self):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        plan = require_approved_plan(stored.plan_id, s.session_id)
        assert plan.plan_id == stored.plan_id
        assert plan.guidance_tags == ["text_rendering"]

    def test_unknown_plan_rejected(self):
        with pytest.raises(PlanNotFoundError, match="imgplan_nope"):
            require_approved_plan("imgplan_nope", "imgses_x")

    def test_cross_session_plan_rejected(self):
        owner = sessions.create_session()
        other = sessions.create_session()
        stored = persist_plan(owner.session_id, _build_plan())
        with pytest.raises(PlanSessionMismatchError, match="belongs to session"):
            require_approved_plan(stored.plan_id, other.session_id)

    def test_unapproved_plan_rejected(self):
        s = sessions.create_session()
        stored = persist_plan(
            s.session_id, _build_plan(), status=PlanStatus.REJECTED
        )
        with pytest.raises(PlanNotApprovedError, match="only an approved plan"):
            require_approved_plan(stored.plan_id, s.session_id)

    def test_malformed_plan_row_rejected(self):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        import gateway.paths as gp

        with sqlite3.connect(gp.KITTY_DB_FILE) as conn:
            conn.execute(
                "UPDATE image_plans SET guidance_tags_json = 'not json'"
                " WHERE plan_id = ?",
                (stored.plan_id,),
            )
            conn.commit()
        with pytest.raises(PlanMalformedError, match="guidance_tags"):
            require_approved_plan(stored.plan_id, s.session_id)

    def test_empty_session_id_rejected(self):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        with pytest.raises(PlanStoreError, match="session_id must not be empty"):
            require_approved_plan(stored.plan_id, "  ")


def _succeeded_anchor(tmp_path: Path, *, prompt: str = "a portrait") -> str:
    """A job in a state real dispatch code will accept as an edit source."""
    job = image_jobs.create_job(provider="comfyui", operation="txt2img", prompt=prompt)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUBMITTED)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.RUNNING)
    artifact = tmp_path / f"{job.job_id}.png"
    artifact.write_bytes(b"\x89PNG\r\n\x1a\n-fake-source-bytes")
    image_jobs.update_job(
        job.job_id, output_path=str(artifact), artifact_id=f"art_{job.job_id}"
    )
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUCCEEDED)
    return job.job_id


class TestEditPlanRoundTrip:
    """IL-01: operation and anchor_job_id are part of the approved plan
    contract, not decision-only fields the store silently drops.
    """

    def test_img2img_plan_round_trips_operation_and_anchor(self, tmp_path: Path):
        s = sessions.create_session()
        anchor = _succeeded_anchor(tmp_path)
        stored = persist_plan(
            s.session_id, _build_plan(), operation="img2img", anchor_job_id=anchor
        )

        assert stored.operation == "img2img"
        assert stored.anchor_job_id == anchor

        resumed = image_plans.require_plan(stored.plan_id)
        assert resumed.operation == "img2img"
        assert resumed.anchor_job_id == anchor

    def test_txt2img_plan_defaults_operation_and_leaves_anchor_null(self):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())

        assert stored.operation == "txt2img"
        assert stored.anchor_job_id is None
        assert image_plans.require_plan(stored.plan_id).operation == "txt2img"

    def test_persist_rejects_unknown_operation(self):
        s = sessions.create_session()
        with pytest.raises(PlanStoreError, match="unknown operation"):
            persist_plan(s.session_id, _build_plan(), operation="upscale")

    def test_persist_rejects_img2img_without_anchor(self):
        s = sessions.create_session()
        with pytest.raises(PlanStoreError, match="anchor_job_id"):
            persist_plan(s.session_id, _build_plan(), operation="img2img")

    def test_unknown_operation_stored_in_row_fails_loud_not_txt2img(self):
        """A row an out-of-band write corrupted must not silently read as txt2img."""
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        import gateway.paths as gp

        with sqlite3.connect(gp.KITTY_DB_FILE) as conn:
            conn.execute(
                "UPDATE image_plans SET operation = 'upscale' WHERE plan_id = ?",
                (stored.plan_id,),
            )
            conn.commit()

        with pytest.raises(PlanMalformedError, match="unknown operation"):
            image_plans.require_plan(stored.plan_id)


class TestRoutePlanPersistence:
    @pytest.mark.asyncio
    async def test_studio_plan_persists_when_session_given(self):
        s = sessions.create_session()
        result = await extended.studio_plan(
            extended.PlanPreviewRequest(
                prompt="a cozy portrait",
                guidance_tags=["text_rendering"],
                session_id=s.session_id,
            )
        )
        assert result["plan_id"].startswith("imgplan_")
        resumed = image_plans.require_plan(result["plan_id"])
        assert resumed.session_id == s.session_id

    @pytest.mark.asyncio
    async def test_studio_plan_without_session_stays_ephemeral(self):
        result = await extended.studio_plan(
            extended.PlanPreviewRequest(prompt="a cozy portrait")
        )
        assert "plan_id" not in result


class TestPlanDispatchRoute:
    def _capture_run(self, monkeypatch):
        captured: dict = {}

        async def fake_run(engine, prompt, **kwargs):
            captured.update({"engine": engine, "prompt": prompt, **kwargs})
            from gateway import image_jobs
            from gateway.image_runner import JobResult

            # The real runner always leaves a durable job row behind, and the
            # route now binds that row to the session. A fake that returns an
            # id with no row would test a state the runner cannot produce.
            job = image_jobs.create_job(
                provider=engine, operation="txt2img", prompt=prompt
            )
            return JobResult(job_id=job.job_id, filename="/tmp/out.png", engine=engine)

        def fake_auto_route(**kwargs):
            from gateway.image_recipes import Recipe, RoutingDecision

            recipe = Recipe(
                recipe_id="r_default",
                display_name="Default",
                description=None,
                provider="comfyui",
                workflow_template_id=None,
                model_family=None,
            )
            return RoutingDecision(recipe.recipe_id, recipe, "test")

        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)
        return captured

    @pytest.mark.asyncio
    async def test_generate_dispatches_from_stored_plan_prompt_and_guidance(self, monkeypatch):
        """The render inputs come from the stored plan, not the live form."""
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        captured = self._capture_run(monkeypatch)

        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="totally different live text",
                plan_id=stored.plan_id,
                session_id=s.session_id,
            )
        )

        assert captured["prompt"] == stored.refined_prompt
        assert captured["guidance_tags"] == ["text_rendering"]

    @pytest.mark.asyncio
    async def test_mutated_form_field_after_approval_cannot_change_dispatch(self, monkeypatch):
        """Editing the form after the plan was approved must not change what renders."""
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan(character_id=None))
        captured = self._capture_run(monkeypatch)

        # The user re-edits the form: new prompt AND a different character.
        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="editted after approval",
                character_id="char_other",
                recipe_id="r_other",
                plan_id=stored.plan_id,
                session_id=s.session_id,
            )
        )

        assert captured["prompt"] == stored.refined_prompt
        assert captured["prompt"] != "editted after approval"
        assert captured["character_id"] is None
        assert captured["guidance_tags"] == ["text_rendering"]

    @pytest.mark.asyncio
    async def test_generate_plan_requires_session(self, monkeypatch):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        self._capture_run(monkeypatch)

        with pytest.raises(HTTPException, match="session_id must not be empty"):
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=None
                )
            )

    @pytest.mark.asyncio
    async def test_generate_unknown_plan_404(self, monkeypatch):
        self._capture_run(monkeypatch)
        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id="imgplan_nope", session_id="imgses_any"
                )
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_cross_session_plan_400(self, monkeypatch):
        owner = sessions.create_session()
        other = sessions.create_session()
        stored = persist_plan(owner.session_id, _build_plan())
        self._capture_run(monkeypatch)

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=other.session_id
                )
            )
        assert exc.value.status_code == 400
        assert "belongs to session" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_generate_unapproved_plan_400(self, monkeypatch):
        s = sessions.create_session()
        stored = persist_plan(
            s.session_id, _build_plan(), status=PlanStatus.REJECTED
        )
        self._capture_run(monkeypatch)

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=s.session_id
                )
            )
        assert exc.value.status_code == 400
        assert "only an approved plan" in str(exc.value.detail)


class TestEditPlanDispatchRoute:
    """IL-01 acceptance: an approved edit must dispatch through run_edit(),
    carrying the exact stored prompt and anchor, and refuse a non-owned or
    missing anchor before any renderer is touched.
    """

    def _capture_run_edit(self, monkeypatch):
        captured: dict = {}

        async def fake_run_edit(prompt: str, *, anchor_job_id: str, **kwargs):
            captured.update(
                {"prompt": prompt, "anchor_job_id": anchor_job_id, **kwargs}
            )
            from gateway.image_runner import JobResult

            job = image_jobs.create_job(
                provider="kitty_worker",
                operation="img2img",
                prompt=prompt,
                parent_id=anchor_job_id,
            )
            return JobResult(job_id=job.job_id, filename="/tmp/edit.png", engine="kitty_worker")

        async def fail_run(*_args, **_kwargs):
            raise AssertionError("an approved img2img plan must not use run()")

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
                supports_img2img=True,
            )
            return RoutingDecision(recipe.recipe_id, recipe, "test")

        monkeypatch.setattr("gateway.image_runner.run_edit", fake_run_edit)
        monkeypatch.setattr("gateway.image_runner.run", fail_run)
        monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)
        return captured

    @pytest.mark.asyncio
    async def test_approved_edit_dispatches_through_run_edit_with_stored_values(
        self, tmp_path: Path, monkeypatch
    ):
        s = sessions.create_session()
        anchor = _succeeded_anchor(tmp_path)
        sessions.attach_job(s.session_id, anchor)
        sessions.set_anchor(s.session_id, anchor)

        stored = persist_plan(
            s.session_id, _build_plan(), operation="img2img", anchor_job_id=anchor
        )
        captured = self._capture_run_edit(monkeypatch)

        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable live text must be ignored",
                plan_id=stored.plan_id,
                session_id=s.session_id,
            )
        )

        assert captured["route_operation"] == "img2img"
        assert captured["prompt"] == stored.refined_prompt
        assert captured["prompt"] != "mutable live text must be ignored"
        assert captured["anchor_job_id"] == anchor

    @pytest.mark.asyncio
    async def test_safe_openai_edit_dispatches_anchor_through_approved_hosted_recipe(
        self, tmp_path: Path, monkeypatch
    ):
        s = sessions.create_session()
        anchor = _succeeded_anchor(tmp_path)
        sessions.attach_job(s.session_id, anchor)
        sessions.set_anchor(s.session_id, anchor)
        stored = persist_plan(
            s.session_id, _build_plan(), operation="img2img", anchor_job_id=anchor
        )
        captured: dict = {}

        def fake_auto_route(**kwargs):
            captured["route_operation"] = kwargs["operation"]
            from gateway.image_recipes import Recipe, RoutingDecision
            recipe = Recipe(
                recipe_id="openai_gpt_image_2", display_name="GPT-Image-2",
                description=None, provider="openai", workflow_template_id=None,
                model_family="gpt-image-2", supports_img2img=True,
            )
            return RoutingDecision(recipe.recipe_id, recipe, "selected hosted edit")

        async def fake_run(engine, prompt, **kwargs):
            captured.update({"engine": engine, "prompt": prompt, **kwargs})
            from gateway.image_runner import JobResult
            job = image_jobs.create_job(
                provider=engine, operation="img2img", prompt=prompt,
                parent_id=kwargs.get("parent_id"),
            )
            return JobResult(job_id=job.job_id, filename="/tmp/openai-edit.png", engine=engine)

        async def fail_run_edit(*_args, **_kwargs):
            raise AssertionError("safe hosted edit must not be diverted to kitty_worker")

        monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)
        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr("gateway.image_runner.run_edit", fail_run_edit)
        monkeypatch.setattr("gateway.image_runner.estimated_cost_usd", lambda engine: 0.0)

        await extended.studio_generate(extended.StudioGenerateRequest(
            prompt="mutable text ignored", plan_id=stored.plan_id, session_id=s.session_id
        ))

        assert captured["route_operation"] == "img2img"
        assert captured["engine"] == "openai"
        assert captured["prompt"] == stored.refined_prompt
        assert captured["parent_id"] == anchor
        assert captured["source_image"] == Path(
            image_jobs.get_job(anchor).output_path
        ).read_bytes()
        assert captured["content_lane"] == "safe"

    @pytest.mark.asyncio
    async def test_edit_refuses_anchor_not_owned_by_session(
        self, tmp_path: Path, monkeypatch
    ):
        """A plan naming an anchor from a different session must be refused
        before any routing or renderer call, even though the plan itself
        belongs to the requesting session.
        """
        owner = sessions.create_session()
        other = sessions.create_session()
        anchor = _succeeded_anchor(tmp_path)
        sessions.attach_job(owner.session_id, anchor)
        sessions.set_anchor(owner.session_id, anchor)

        stored = persist_plan(
            other.session_id, _build_plan(), operation="img2img", anchor_job_id=anchor
        )

        def fail_route(**_kwargs):
            raise AssertionError("must refuse ownership before routing")

        async def fail_dispatch(*_args, **_kwargs):
            raise AssertionError("must refuse ownership before dispatch")

        monkeypatch.setattr("gateway.image_recipes.auto_route", fail_route)
        monkeypatch.setattr("gateway.image_runner.run_edit", fail_dispatch)
        monkeypatch.setattr("gateway.image_runner.run", fail_dispatch)

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=other.session_id
                )
            )
        assert exc.value.status_code == 400
        assert "does not belong to session" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_edit_refuses_unknown_anchor(self, monkeypatch):
        s = sessions.create_session()
        stored = persist_plan(
            s.session_id,
            _build_plan(),
            operation="img2img",
            anchor_job_id="imgjob_never_existed",
        )

        async def fail_dispatch(*_args, **_kwargs):
            raise AssertionError("must refuse before dispatch")

        monkeypatch.setattr("gateway.image_runner.run_edit", fail_dispatch)
        monkeypatch.setattr("gateway.image_runner.run", fail_dispatch)

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=s.session_id
                )
            )
        assert exc.value.status_code == 400
        assert "no longer exists" in str(exc.value.detail)

    @pytest.mark.asyncio
    async def test_edit_refuses_dispatch_when_stored_row_has_no_anchor(
        self, tmp_path: Path, monkeypatch
    ):
        """Defense in depth: even if a row bypassed persist_plan's own
        img2img-requires-anchor check, load must still fail loud rather than
        let a missing anchor reach the renderer.
        """
        s = sessions.create_session()
        anchor = _succeeded_anchor(tmp_path)
        sessions.attach_job(s.session_id, anchor)
        sessions.set_anchor(s.session_id, anchor)
        stored = persist_plan(
            s.session_id, _build_plan(), operation="img2img", anchor_job_id=anchor
        )

        import gateway.paths as gp

        with sqlite3.connect(gp.KITTY_DB_FILE) as conn:
            conn.execute(
                "UPDATE image_plans SET anchor_job_id = NULL WHERE plan_id = ?",
                (stored.plan_id,),
            )
            conn.commit()

        async def fail_dispatch(*_args, **_kwargs):
            raise AssertionError("must refuse before dispatch")

        monkeypatch.setattr("gateway.image_runner.run_edit", fail_dispatch)
        monkeypatch.setattr("gateway.image_runner.run", fail_dispatch)

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=s.session_id
                )
            )
        assert exc.value.status_code == 400
        assert "anchor_job_id" in str(exc.value.detail)


class TestGuidanceToRenderer:
    @pytest.mark.asyncio
    async def test_runner_forwards_guidance_to_character_renderer(self, monkeypatch):
        """guidance_tags survive the runner → renderer boundary."""
        from gateway import image_runner

        captured: dict = {}

        resolved = {
            "positive_prompt": "person",
            "negative_prompt": "",
            "reference_path": "/tmp/ref.png",
            "identity_mode": "balanced",
            "width": 1024,
            "height": 1024,
            "steps": 8,
            "guidance": 4.5,
            "recipe_id": "contract-v1",
            "identity_method": "ipadapter_faceid",
            "references": [{"ref_id": "ref-primary"}],
        }

        async def fake_generate_with_character(**kwargs):
            captured.update(kwargs)
            return {
                "job_id": "job_x",
                "filename": "/tmp/out.png",
                "prompt_id": "p",
                "character_weight": 0.7,
            }

        async def fake_available():
            return True

        async def fake_ready():
            return True, "ready"

        monkeypatch.setattr("gateway.image_gen.is_available", fake_available)
        monkeypatch.setattr(
            "gateway.image_gen.generate_with_character", fake_generate_with_character
        )
        monkeypatch.setattr(
            "gateway.image_character_contracts.resolve_comfyui_character",
            lambda _cid: resolved,
        )
        monkeypatch.setattr(
            "gateway.image_character_contracts.comfyui_character_runtime_status",
            fake_ready,
        )

        result = await image_runner._run_comfyui_character(
            "portrait",
            character_id="char_james",
            guidance_tags=["text_rendering"],
        )
        assert captured["guidance_tags"] == ["text_rendering"]
        assert result.job_id == "job_x"

    @pytest.mark.asyncio
    async def test_generate_with_character_carries_guidance_in_renderer_request(
        self, monkeypatch
    ):
        """The renderer request record (provider_params_json) carries guidance tags."""
        from gateway import image_gen

        captured: dict = {}

        class _Stop(Exception):
            pass

        def fake_create_job(**kwargs):
            captured.update(kwargs)
            raise _Stop("stop before network")

        monkeypatch.setattr("gateway.image_gen.create_job", fake_create_job)

        with pytest.raises(_Stop):
            await image_gen.generate_with_character(
                "portrait",
                character_ref_path="/tmp/ref.png",
                guidance_tags=["text_rendering"],
            )

        params = json.loads(captured["provider_params_json"])
        assert params["guidance_tags"] == ["text_rendering"]

    @pytest.mark.asyncio
    async def test_generate_carries_guidance_in_renderer_request(self, monkeypatch):
        from gateway import image_gen

        captured: dict = {}

        class _Stop(Exception):
            pass

        def fake_create_job(**kwargs):
            captured.update(kwargs)
            raise _Stop("stop before network")

        monkeypatch.setattr("gateway.image_gen.create_job", fake_create_job)

        with pytest.raises(_Stop):
            await image_gen.generate(
                "a cat on a windowsill", guidance_tags=["text_rendering"]
            )

        params = json.loads(captured["provider_params_json"])
        assert params["guidance_tags"] == ["text_rendering"]
