from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError


def test_batch_request_accepts_only_ui_supported_decision_values() -> None:
    from gateway.routes.image_studio_jobs import StudioBatchRequest, StudioEstimateRequest

    for count in (1, 2, 4):
        assert StudioBatchRequest(prompt="cat", count=count).count == count
    with pytest.raises(ValidationError):
        StudioBatchRequest(prompt="cat", count=3)
    with pytest.raises(ValidationError):
        StudioEstimateRequest(quality="ultra")
    with pytest.raises(ValidationError):
        StudioEstimateRequest(identity="perfect")


@pytest.mark.asyncio
async def test_estimate_uses_exact_provider_model_and_scales_batch(monkeypatch) -> None:
    from gateway.routes import image_studio_jobs as routes

    async def live_providers():
        return {"openrouter"}
    monkeypatch.setattr(routes, "_runtime_available_providers", live_providers)
    recipe = SimpleNamespace(provider="openrouter", recipe_id="hosted", model_family="gemini-image")
    monkeypatch.setattr(
        routes.image_recipes,
        "auto_route",
        lambda **_: SimpleNamespace(recipe=recipe, recipe_id="hosted", reason="best available image lane"),
    )
    seen: dict = {}

    def fake_estimate(provider: str, *, model_id: str | None, operation: str):
        seen.update(provider=provider, model_id=model_id, operation=operation)
        return {
            "cost": {"state": "known", "usd": 0.067, "basis": "observed", "samples": 4},
            "duration": {"state": "known", "seconds": 12, "basis": "observed", "samples": 4},
        }

    monkeypatch.setattr(routes.image_estimates, "estimate", fake_estimate)
    result = await routes.studio_estimate(routes.StudioEstimateRequest(count=4))

    assert seen == {
        "provider": "openrouter",
        "model_id": routes.OPENROUTER_IMAGE_MODEL,
        "operation": "txt2img",
    }
    assert result["per_image_estimate"]["cost"]["usd"] == pytest.approx(0.067)
    assert result["estimate"]["cost"]["usd"] == pytest.approx(0.268)
    assert result["estimate"]["duration"]["seconds"] == pytest.approx(48)
    assert result["routing_reason"] == "best available image lane"


@pytest.mark.asyncio
async def test_estimate_flux2_klein_returns_exact_model_id(monkeypatch) -> None:
    """FLUX.2 Klein recipe resolves its execution_target to the exact BFL model id."""
    from gateway.routes import image_studio_jobs as routes

    recipe = SimpleNamespace(
        provider="flux2",
        recipe_id="bfl_flux2_draft",
        execution_target="flux2-klein-4b-h",
    )
    monkeypatch.setattr(
        routes.image_recipes,
        "auto_route",
        lambda **_: SimpleNamespace(
            recipe=recipe, recipe_id="bfl_flux2_draft", reason="draft fast path"
        ),
    )
    seen: dict = {}

    def fake_estimate(provider: str, *, model_id: str | None, operation: str):
        seen.update(provider=provider, model_id=model_id, operation=operation)
        return {
            "cost": {"state": "known", "usd": 0.02, "basis": "observed", "samples": 4},
            "duration": {"state": "known", "seconds": 5, "basis": "observed", "samples": 4},
        }

    monkeypatch.setattr(routes.image_estimates, "estimate", fake_estimate)
    result = await routes.studio_estimate(routes.StudioEstimateRequest())

    assert seen == {
        "provider": "flux2",
        "model_id": "flux-2-klein-4b",
        "operation": "txt2img",
    }
    assert result["model_id"] == "flux-2-klein-4b"
    assert result["recipe_id"] == "bfl_flux2_draft"
    assert result["routing_reason"] == "draft fast path"


@pytest.mark.asyncio
async def test_estimate_flux2_pro_returns_exact_model_id(monkeypatch) -> None:
    """FLUX.2 Pro recipe resolves its execution_target to the exact BFL model id."""
    from gateway.routes import image_studio_jobs as routes

    recipe = SimpleNamespace(
        provider="flux2",
        recipe_id="bfl_flux2_final",
        execution_target="flux2-pro-h",
    )
    monkeypatch.setattr(
        routes.image_recipes,
        "auto_route",
        lambda **_: SimpleNamespace(
            recipe=recipe, recipe_id="bfl_flux2_final", reason="quality final path"
        ),
    )
    seen: dict = {}

    def fake_estimate(provider: str, *, model_id: str | None, operation: str):
        seen.update(provider=provider, model_id=model_id, operation=operation)
        return {
            "cost": {"state": "known", "usd": 0.05, "basis": "observed", "samples": 4},
            "duration": {"state": "known", "seconds": 10, "basis": "observed", "samples": 4},
        }

    monkeypatch.setattr(routes.image_estimates, "estimate", fake_estimate)
    result = await routes.studio_estimate(routes.StudioEstimateRequest())

    assert seen == {
        "provider": "flux2",
        "model_id": "flux-2-pro",
        "operation": "txt2img",
    }
    assert result["model_id"] == "flux-2-pro"
    assert result["recipe_id"] == "bfl_flux2_final"
    assert result["routing_reason"] == "quality final path"


@pytest.mark.asyncio
async def test_estimate_passes_live_provider_allowlist_to_routing(monkeypatch) -> None:
    from gateway.routes import image_studio_jobs as routes

    async def live_providers():
        return {"openai"}
    monkeypatch.setattr(routes, "_runtime_available_providers", live_providers)
    routed = {}
    recipe = SimpleNamespace(
        provider="openai", recipe_id="openai_gpt_image_2", model_family="gpt-image-2",
        execution_target=None, supports_img2img=True,
    )
    monkeypatch.setattr(
        routes.image_recipes,
        "auto_route",
        lambda **kwargs: routed.update(kwargs) or SimpleNamespace(
            recipe=recipe, recipe_id=recipe.recipe_id, reason="live route"
        ),
    )
    monkeypatch.setattr(
        routes.image_estimates, "estimate",
        lambda *args, **kwargs: {
            "cost": {"state": "unknown", "usd": None},
            "duration": {"state": "unknown", "seconds": None},
        },
    )

    await routes.studio_estimate(routes.StudioEstimateRequest())
    assert routed["available_providers"] == {"openai"}


@pytest.mark.asyncio
async def test_img2img_estimate_uses_selected_recipe_operation_and_exact_model(monkeypatch) -> None:
    from gateway.routes import image_studio_jobs as routes

    async def live_providers():
        return {"openai"}
    monkeypatch.setattr(routes, "_runtime_available_providers", live_providers)
    recipe = SimpleNamespace(
        provider="openai", recipe_id="openai_gpt_image_2", model_family="gpt-image-2",
        execution_target=None, supports_img2img=True,
    )
    routed = {}
    monkeypatch.setattr(
        routes.image_recipes,
        "auto_route",
        lambda **kwargs: routed.update(kwargs) or SimpleNamespace(
            recipe=recipe, recipe_id=recipe.recipe_id, reason="user selected"
        ),
    )
    seen = {}
    monkeypatch.setattr(
        routes.image_estimates, "estimate",
        lambda provider, *, model_id, operation: seen.update(
            provider=provider, model_id=model_id, operation=operation
        ) or {
            "cost": {"state": "unknown", "usd": None},
            "duration": {"state": "unknown", "seconds": None},
        },
    )

    result = await routes.studio_estimate(routes.StudioEstimateRequest(
        operation="img2img", recipe_id="openai_gpt_image_2"
    ))

    assert routed["operation"] == "img2img"
    assert seen == {
        "provider": "openai", "model_id": routes.OPENAI_IMAGE_MODEL, "operation": "img2img"
    }
    assert result["operation"] == "img2img"


@pytest.mark.asyncio
async def test_batch_preflight_uses_approved_plan_operation_and_recipe(monkeypatch) -> None:
    from gateway import image_plan_store
    from gateway.routes import image_studio_jobs as routes

    plan = SimpleNamespace(operation="img2img", recipe_id="openai_gpt_image_2", character_id=None)
    monkeypatch.setattr(image_plan_store, "require_approved_plan", lambda plan_id, session_id: plan)
    seen = {}
    async def fake_preflight(req):
        seen.update(operation=req.operation, recipe_id=req.recipe_id)
        return {
            "provider": "openai", "model_id": "gpt-image-2",
            "recipe_id": "openai_gpt_image_2", "routing_reason": "selected", "count": 1,
            "per_image_estimate": {
                "cost": {"state": "unknown", "usd": None},
                "duration": {"state": "unknown", "seconds": None},
            },
            "estimate": {}, "operation": "img2img",
        }
    monkeypatch.setattr(routes, "studio_estimate", fake_preflight)
    monkeypatch.setattr(routes.image_batches, "create_batch", lambda *args, **kwargs: {"batch_id": "b", "status": "queued"})

    await routes.studio_create_batch(routes.StudioBatchRequest(
        prompt="edit", plan_id="plan_1", session_id="session_1"
    ))

    assert seen == {"operation": "img2img", "recipe_id": "openai_gpt_image_2"}


@pytest.mark.asyncio
async def test_batch_preflight_rejects_unknown_approved_plan_operation(monkeypatch) -> None:
    from gateway import image_plan_store
    from gateway.routes import image_studio_jobs as routes

    plan = SimpleNamespace(operation="video", recipe_id="openai_gpt_image_2", character_id=None)
    monkeypatch.setattr(image_plan_store, "require_approved_plan", lambda plan_id, session_id: plan)

    with pytest.raises(routes.HTTPException) as exc_info:
        await routes.studio_create_batch(routes.StudioBatchRequest(
            prompt="edit", plan_id="plan_1", session_id="session_1"
        ))

    assert exc_info.value.status_code == 400
    assert "unknown operation" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_create_batch_returns_queued_without_running_provider(monkeypatch) -> None:
    from gateway.routes import image_studio_jobs as routes

    fake_batch = {
        "batch_id": "imgbatch_1",
        "status": "queued",
        "count": 4,
        "items": [{"status": "queued"}] * 4,
        "estimate": {"cost": {"state": "known", "usd": 0.32}},
    }
    calls = {"provider": 0}

    async def fake_preflight(_req):
        return {
            "provider": "openrouter",
            "model_id": "vendor/image",
            "recipe_id": "hosted",
            "routing_reason": "test",
            "count": 4,
            "per_image_estimate": {
                "cost": {"state": "known", "usd": 0.08, "basis": "observed", "samples": 4},
                "duration": {"state": "unknown", "seconds": None, "basis": "unknown", "samples": 0},
            },
            "estimate": {},
        }

    monkeypatch.setattr(routes, "studio_estimate", fake_preflight)
    monkeypatch.setattr(routes.image_batches, "create_batch", lambda *args, **kwargs: fake_batch)

    result = await routes.studio_create_batch(routes.StudioBatchRequest(prompt="four cats", count=4))
    assert result["status"] == "queued"
    assert result["count"] == 4
    assert calls["provider"] == 0
