"""Durable Image Lab estimate and batch queue HTTP contract."""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway import image_batches, image_estimates, image_recipes
from gateway.image_runner import FLUX_GENERATE_MODEL, OPENROUTER_IMAGE_MODEL

router = APIRouter(tags=["image-studio-jobs"])

QualityTier = Literal["fast", "quality", "maximum"]
IdentityMode = Literal["creative", "balanced", "identity_first"]
OutputCount = Literal[1, 2, 4]


class StudioEstimateRequest(BaseModel):
    quality: QualityTier = "quality"
    identity: IdentityMode = "balanced"
    character_id: str | None = None
    recipe_id: str | None = None
    count: OutputCount = 1


class StudioBatchRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_240)
    quality: QualityTier = "quality"
    identity: IdentityMode = "balanced"
    character_id: str | None = None
    recipe_id: str | None = None
    negative_prompt: str | None = None
    plan_id: str | None = None
    session_id: str | None = None
    count: OutputCount = 1


def _exact_model_id(provider: str) -> str | None:
    provider = provider.strip().lower()
    if provider == "openrouter":
        return OPENROUTER_IMAGE_MODEL
    if provider == "flux":
        return FLUX_GENERATE_MODEL
    if provider == "comfyui":
        from gateway.image_gen import SDXL_PHOTONIC

        return SDXL_PHOTONIC
    # Draw Things chooses its installed model at runtime. Returning None is
    # more honest than grouping observations under a made-up family label.
    return None


async def studio_estimate(req: StudioEstimateRequest) -> dict:
    try:
        decision = image_recipes.auto_route(
            has_character=bool(req.character_id),
            character_count=1 if req.character_id else 0,
            quality_tier=req.quality,
            identity_mode=req.identity,
            operation="txt2img",
            preferred_recipe=req.recipe_id,
        )
    except image_recipes.RecipeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    recipe = decision.recipe
    provider = recipe.provider if recipe else "comfyui"
    model_id = _exact_model_id(provider)
    per_image = image_estimates.estimate(
        provider, model_id=model_id, operation="txt2img"
    )
    return {
        "provider": provider,
        "model_id": model_id,
        "recipe_id": decision.recipe_id,
        "routing_reason": decision.reason,
        "count": req.count,
        "per_image_estimate": per_image,
        "estimate": image_batches.scale_estimate(per_image, req.count),
    }


@router.post("/studio/estimate")
async def studio_estimate_route(req: StudioEstimateRequest) -> dict:
    return await studio_estimate(req)


@router.post("/studio/batches")
async def studio_create_batch(req: StudioBatchRequest) -> dict:
    preflight = await studio_estimate(
        StudioEstimateRequest(
            quality=req.quality,
            identity=req.identity,
            character_id=req.character_id,
            recipe_id=req.recipe_id,
            count=req.count,
        )
    )
    request = req.model_dump(exclude={"count"})
    request["estimated_provider"] = preflight["provider"]
    request["estimated_model_id"] = preflight["model_id"]
    return image_batches.create_batch(
        request,
        count=req.count,
        per_image_estimate=preflight["per_image_estimate"],
    )


@router.get("/studio/batches")
async def studio_list_batches(session_id: str | None = None, limit: int = 20) -> dict:
    try:
        batches = image_batches.list_batches(session_id=session_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"batches": batches}


@router.get("/studio/batches/{batch_id}")
async def studio_get_batch(batch_id: str) -> dict:
    try:
        return image_batches.get_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"batch {batch_id} not found") from exc


@router.post("/studio/batches/{batch_id}/cancel")
async def studio_cancel_batch(batch_id: str) -> dict:
    try:
        return image_batches.cancel_batch(batch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"batch {batch_id} not found") from exc


async def execute_studio_batch_request(request: dict) -> dict:
    """Execute one queued child through the existing Studio generation path.

    The queue stores the estimate-time provider/model for audit, but actual job
    metadata after routing remains the source of truth for observations.
    """
    from gateway import image_jobs
    from gateway.routes.extended import StudioGenerateRequest, studio_generate

    payload = {
        key: value
        for key, value in request.items()
        if key not in {"estimated_provider", "estimated_model_id"}
    }
    started = time.monotonic()
    result = await studio_generate(StudioGenerateRequest(**payload))
    duration = max(time.monotonic() - started, 0.001)

    job_id = result.get("job_id")
    job = image_jobs.get_job(job_id) if isinstance(job_id, str) else None
    if job is not None:
        image_estimates.record_observation(
            job_id=job.job_id,
            provider=job.provider,
            model_id=job.model_id,
            operation=job.operation,
            actual_cost_usd=result.get("actual_cost_usd"),
            duration_seconds=duration,
        )
    return result


__all__ = [
    "StudioBatchRequest",
    "StudioEstimateRequest",
    "execute_studio_batch_request",
    "router",
    "studio_create_batch",
    "studio_estimate",
]
