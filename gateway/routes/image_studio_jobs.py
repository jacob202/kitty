"""Durable Image Lab estimate and batch queue HTTP contract."""

from __future__ import annotations

import logging
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway import image_batches, image_estimates, image_recipes
from gateway.image_runner import FLUX_GENERATE_MODEL, OPENROUTER_IMAGE_MODEL

logger = logging.getLogger(__name__)
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


class JobModifyRequest(BaseModel):
    """One-or-more render-parameter changes for iterating on an image.

    Only fields present in the request body are changed; everything else is
    carried forward from the source job. Provider, operation, plan, and intent
    are intentionally absent so a modify can never re-route or re-approve.
    """

    prompt: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None
    guidance: float | None = None
    sampler: str | None = None
    scheduler: str | None = None
    model_id: str | None = None
    preset_id: str | None = None


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


@router.delete("/studio/sessions/{session_id}/anchor")
async def studio_clear_anchor(session_id: str) -> dict:
    from gateway import undo_journal
    from gateway.image_sessions import ImageSessionError, SessionNotFoundError, require_session
    from gateway.routes.extended import _session_payload

    try:
        journal_id = undo_journal.clear_anchor_with_undo(session_id)
        session = require_session(session_id)
    except (SessionNotFoundError, undo_journal.UndoNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImageSessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = _session_payload(session)
    result["undo_journal_id"] = journal_id
    return result


def _iteration_error(exc: Exception) -> HTTPException:
    from gateway.image_jobs import JobNotFoundError

    if isinstance(exc, JobNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/studio/jobs/{job_id}/duplicate")
async def studio_duplicate_job(job_id: str) -> dict:
    """Enqueue an independent re-run of a succeeded job's approved plan."""
    from gateway import image_iteration
    from gateway.image_jobs import ImageJobError
    from gateway.image_sessions import ImageSessionError

    try:
        batch = image_iteration.enqueue_duplicate(job_id)
    except (ImageJobError, ImageSessionError) as exc:
        raise _iteration_error(exc) from exc
    return {"batch": batch}


@router.post("/studio/jobs/{job_id}/retry")
async def studio_retry_job(job_id: str) -> dict:
    """Enqueue a fresh attempt of a succeeded job's generation intent."""
    from gateway import image_iteration
    from gateway.image_jobs import ImageJobError
    from gateway.image_sessions import ImageSessionError

    try:
        batch = image_iteration.enqueue_retry(job_id)
    except (ImageJobError, ImageSessionError) as exc:
        raise _iteration_error(exc) from exc
    return {"batch": batch}


@router.post("/studio/jobs/{job_id}/modify")
async def studio_modify_job(job_id: str, req: JobModifyRequest) -> dict:
    """Enqueue a re-run and report the changed-vs-unchanged diff."""

    changes = req.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="no parameters supplied to modify")
    raise HTTPException(
        status_code=409,
        detail=(
            "Image Lab cannot safely dispatch a modified approved plan yet; "
            "use a new Create request so the changed prompt is approved before rendering"
        ),
    )


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
        if key not in {"estimated_provider", "estimated_model_id", "lineage_parent_id"}
    }
    lineage_parent_id = request.get("lineage_parent_id")
    started = time.monotonic()
    result = await studio_generate(StudioGenerateRequest(**payload))
    duration = max(time.monotonic() - started, 0.001)

    job_id = result.get("job_id")
    if lineage_parent_id and isinstance(job_id, str) and job_id:
        image_jobs.set_parent(job_id, lineage_parent_id)
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
    elif isinstance(job_id, str) and job_id:
        logger.warning(
            "Image Lab observation skipped because returned job %s was not visible in image_jobs",
            job_id,
        )
    return result


__all__ = [
    "JobModifyRequest",
    "StudioBatchRequest",
    "StudioEstimateRequest",
    "execute_studio_batch_request",
    "router",
    "studio_clear_anchor",
    "studio_create_batch",
    "studio_duplicate_job",
    "studio_estimate",
    "studio_modify_job",
    "studio_retry_job",
]
