"""QoL Packet 02 — Image Lab iteration contracts (retry / duplicate / modify).

These tests are RED-first: they describe the behavior a user needs to iterate on
a generated image without manually reconstructing the original generation, and
fail until the smallest implementation lands in ``gateway.image_iteration``.

Protected-subsystem invariant: nothing here changes provider routing, content
policy, or the private-adult lane. Provider and policy metadata must be carried
forward verbatim, never re-derived.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import image_jobs as jobs
from gateway import image_sessions
from gateway.image_jobs import ImageJobStatus

PLAN_ID = "plan_iteration_0001"
INTENT = {
    "intent_version": 1,
    "operation": "txt2img",
    "cast": [],
    "content_lane": "safe",
    "consent_basis": None,
    "adult_confirmed": False,
}
PROVIDER_PARAMS = {"denoise": 0.5, "source_job_id": "legacy"}
COMPILER_PARAMS = {"temperature": 1.0, "steps": 24}


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as paths

    original = paths.KITTY_DB_FILE
    paths.KITTY_DB_FILE = tmp_path / "kitty.db"
    yield
    paths.KITTY_DB_FILE = original


def _succeeded_job(**kwargs) -> jobs.ImageJob:
    """Create a job and drive it to SUCCEEDED without a provider or disk write."""
    defaults = dict(
        provider="comfyui",
        operation="txt2img",
        prompt="a wizard in a red cloak",
        negative_prompt="blurry",
        seed=1234,
        model_id="sdxl_photonic",
        preset_id="comfyui_sdxl_standard",
        width=512,
        height=512,
        steps=24,
        guidance=7.5,
        sampler="euler",
        scheduler="normal",
        provider_params_json=json.dumps(PROVIDER_PARAMS),
        compiler_version="0.9.1",
        compiler_params_json=json.dumps(COMPILER_PARAMS),
        plan_id=PLAN_ID,
        intent_json=json.dumps(INTENT),
    )
    defaults.update(kwargs)
    job = jobs.create_job(**defaults)
    return _succeed(job.job_id)


def _succeed(job_id: str) -> jobs.ImageJob:
    """Drive an existing CREATED job to SUCCEEDED without a provider or disk write."""
    jobs.transition(job_id, ImageJobStatus.SUBMITTED)
    jobs.transition(job_id, ImageJobStatus.RUNNING)
    jobs.update_job(job_id, artifact_id="asset_fake")
    jobs.transition(job_id, ImageJobStatus.SUCCEEDED)
    return jobs.get_job(job_id)  # type: ignore[return-value]


def test_duplicate_preserves_provider_model_and_config():
    from gateway import image_iteration

    src = _succeeded_job()
    child = image_iteration.duplicate_job(src.job_id)

    assert child.provider == "comfyui"
    assert child.model_id == "sdxl_photonic"
    assert child.provider_params_json == src.provider_params_json
    assert child.compiler_params_json == src.compiler_params_json
    assert child.intent_json == src.intent_json
    assert child.plan_id == src.plan_id


def test_retry_preserves_generation_context_and_links_parent():
    from gateway import image_iteration

    src = _succeeded_job()
    child = image_iteration.retry_job(src.job_id)

    assert child.parent_id == src.job_id
    assert child.prompt == src.prompt
    assert child.negative_prompt == src.negative_prompt
    assert child.model_id == src.model_id
    assert child.provider == src.provider
    assert child.provider_params_json == src.provider_params_json


def test_character_identity_survives_iteration():
    from gateway import image_iteration

    session = image_sessions.create_session(
        character_id="char_1",
        reference_ids=["ref_a", "ref_b"],
        protected_traits=["face", "hair"],
    )
    src = _succeeded_job()
    image_sessions.attach_job(session.session_id, src.job_id)

    ctx = image_iteration.build_generation_context(src.job_id)
    assert ctx.character_id == "char_1"
    assert ctx.reference_ids == ["ref_a", "ref_b"]
    assert ctx.protected_traits == ["face", "hair"]

    child = image_iteration.duplicate_job(src.job_id)
    assert image_sessions.job_session_id(child.job_id) == session.session_id

    _succeed(child.job_id)
    child_ctx = image_iteration.build_generation_context(child.job_id)
    assert child_ctx.character_id == "char_1"
    assert child_ctx.reference_ids == ["ref_a", "ref_b"]


def test_modify_changes_only_the_selected_parameter():
    from gateway import image_iteration

    src = _succeeded_job()
    child, diff = image_iteration.modify_job(src.job_id, prompt="a wizard in a blue cloak")

    assert child.prompt == "a wizard in a blue cloak"
    assert diff == {"prompt": {"before": "a wizard in a red cloak", "after": "a wizard in a blue cloak"}}


def test_modify_leaves_unchanged_parameters_unchanged():
    from gateway import image_iteration

    src = _succeeded_job()
    child, _diff = image_iteration.modify_job(src.job_id, prompt="a different wizard")

    assert child.prompt == "a different wizard"
    assert child.seed == src.seed
    assert child.width == src.width
    assert child.height == src.height
    assert child.steps == src.steps
    assert child.guidance == src.guidance
    assert child.sampler == src.sampler
    assert child.scheduler == src.scheduler
    assert child.model_id == src.model_id
    assert child.provider == src.provider


def test_provider_and_model_recorded_on_child_job():
    from gateway import image_iteration

    src = _succeeded_job(provider="fal", model_id="fal_flux")
    child = image_iteration.duplicate_job(src.job_id)

    assert child.provider == "fal"
    assert child.model_id == "fal_flux"


def test_private_adult_lane_metadata_is_preserved_not_re_routed():
    from gateway import image_iteration

    adult_intent = dict(INTENT)
    adult_intent.update(
        content_lane="private_adult",
        consent_basis="explicit",
        adult_confirmed=True,
    )
    src = _succeeded_job(
        provider="kitty_worker",
        intent_json=json.dumps(adult_intent),
    )
    child = image_iteration.duplicate_job(src.job_id)

    # Provider is carried verbatim — iteration never re-routes the lane.
    assert child.provider == "kitty_worker"
    child_intent = json.loads(child.intent_json)
    assert child_intent["content_lane"] == "private_adult"
    assert child_intent["consent_basis"] == "explicit"
    assert child_intent["adult_confirmed"] is True


def test_lineage_links_parent_to_child_and_grandchild():
    from gateway import image_iteration

    src = _succeeded_job()
    child = image_iteration.duplicate_job(src.job_id)
    _succeed(child.job_id)
    grandchild = image_iteration.retry_job(child.job_id)

    assert [j.job_id for j in jobs.list_children(src.job_id)] == [child.job_id]
    assert [j.job_id for j in jobs.list_children(child.job_id)] == [grandchild.job_id]
    assert grandchild.parent_id == child.job_id


@pytest.mark.asyncio
async def test_duplicate_route_enqueues_a_lineage_linked_batch():
    from gateway.routes import image_studio_jobs as routes

    session = image_sessions.create_session(character_id="char_1")
    src = _succeeded_job()
    image_sessions.attach_job(session.session_id, src.job_id)

    result = await routes.studio_duplicate_job(src.job_id)

    batch = result["batch"]
    assert batch["batch_id"]
    assert len(batch["items"]) == 1
    assert batch["request"]["lineage_parent_id"] == src.job_id
    assert batch["request"]["plan_id"] == src.plan_id


@pytest.mark.asyncio
async def test_retry_route_enqueues_a_lineage_linked_batch():
    from gateway.routes import image_studio_jobs as routes

    session = image_sessions.create_session(character_id="char_1")
    src = _succeeded_job()
    image_sessions.attach_job(session.session_id, src.job_id)

    result = await routes.studio_retry_job(src.job_id)

    batch = result["batch"]
    assert batch["request"]["lineage_parent_id"] == src.job_id
    assert batch["request"]["plan_id"] == src.plan_id


@pytest.mark.asyncio
async def test_modify_route_fails_closed_until_modified_plan_dispatch_is_real():
    from fastapi import HTTPException

    from gateway.routes import image_studio_jobs as routes

    session = image_sessions.create_session(character_id="char_1")
    src = _succeeded_job()
    image_sessions.attach_job(session.session_id, src.job_id)

    with pytest.raises(HTTPException) as exc:
        await routes.studio_modify_job(
            src.job_id, routes.JobModifyRequest(prompt="a taller wizard")
        )
    assert exc.value.status_code == 409
    assert "modified approved plan" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_retry_route_returns_404_for_missing_job():
    from fastapi import HTTPException

    from gateway.routes import image_studio_jobs as routes

    with pytest.raises(HTTPException) as exc:
        await routes.studio_retry_job("job_does_not_exist")
    assert exc.value.status_code == 404


def test_iteration_batch_carries_source_negative_prompt(monkeypatch):
    from gateway import image_iteration, image_recipes

    session = image_sessions.create_session(character_id="char_1")
    src = _succeeded_job(preset_id="recipe_locked")
    image_sessions.attach_job(session.session_id, src.job_id)
    monkeypatch.setattr(image_recipes, "get_recipe", lambda _rid: type("R", (), {
        "recipe_id": "recipe_locked", "provider": src.provider, "is_available": True
    })())

    batch = image_iteration.enqueue_duplicate(src.job_id)
    assert batch["request"]["negative_prompt"] == "blurry"


def test_generation_context_recovers_recipe_lock_from_approved_plan(monkeypatch):
    from types import SimpleNamespace

    from gateway import image_iteration, image_plans

    src = _succeeded_job(preset_id=None)
    monkeypatch.setattr(
        image_plans,
        "get_plan",
        lambda plan_id: SimpleNamespace(recipe_id="bfl_flux2_draft") if plan_id == PLAN_ID else None,
    )

    ctx = image_iteration.build_generation_context(src.job_id)

    assert ctx.preset_id == "bfl_flux2_draft"


def test_iteration_refuses_source_without_exact_recipe_lock():
    from gateway import image_iteration

    session = image_sessions.create_session(character_id="char_1")
    src = _succeeded_job(preset_id=None)
    image_sessions.attach_job(session.session_id, src.job_id)

    with pytest.raises(image_iteration.IterationError, match="exact source recipe"):
        image_iteration.enqueue_duplicate(src.job_id)


@pytest.mark.asyncio
async def test_iteration_batch_refuses_route_drift_before_generation(monkeypatch):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from gateway import image_recipes
    from gateway.routes import extended
    from gateway.routes import image_studio_jobs as routes

    source = _succeeded_job(
        provider="flux2",
        model_id="flux-2-klein-4b",
        preset_id="recipe_locked",
    )
    monkeypatch.setattr(
        image_recipes,
        "get_recipe",
        lambda _rid: SimpleNamespace(
            recipe_id="recipe_locked",
            provider="openrouter",
            model_family="different-model",
            execution_target=None,
            is_available=True,
        ),
    )

    async def must_not_generate(_req):
        raise AssertionError("route drift must be rejected before generation")

    monkeypatch.setattr(extended, "studio_generate", must_not_generate)

    with pytest.raises(HTTPException, match="source route"):
        await routes.execute_studio_batch_request({
            "prompt": "portrait",
            "recipe_id": "recipe_locked",
            "lineage_parent_id": source.job_id,
            "expected_provider": "flux2",
            "expected_model_id": "flux-2-klein-4b",
        })
