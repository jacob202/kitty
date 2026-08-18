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
