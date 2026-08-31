"""Durable Image Lab estimate and batch queue HTTP contract."""

from __future__ import annotations

import json
import logging
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field

from gateway import image_batches, image_estimates, image_recipes
from gateway import paths as _paths
from gateway.image_runner import (
    FLUX_EDIT_MODEL,
    FLUX_GENERATE_MODEL,
    OPENAI_IMAGE_MODEL,
    OPENROUTER_IMAGE_MODEL,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["image-studio-jobs"])

_SOURCE_IMAGE_ROOT = _paths.DATA_DIR / "images" / "imports"
_SOURCE_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_SOURCE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}

QualityTier = Literal["fast", "quality", "maximum"]
IdentityMode = Literal["creative", "balanced", "identity_first"]
OutputCount = Literal[1, 2, 4]
ImageOperation = Literal["txt2img", "img2img"]


class StudioEstimateRequest(BaseModel):
    quality: QualityTier = "quality"
    operation: ImageOperation = "txt2img"
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
    if provider == "openai":
        return OPENAI_IMAGE_MODEL
    if provider == "flux":
        return FLUX_GENERATE_MODEL
    if provider == "comfyui":
        from gateway.image_gen import SDXL_PHOTONIC

        return SDXL_PHOTONIC
    # Draw Things chooses its installed model at runtime. Returning None is
    # more honest than grouping observations under a made-up family label.
    return None


def _iteration_model_id(recipe: object, *, operation: str) -> str | None:
    """Resolve the exact model the current recipe would dispatch without doing I/O."""
    provider = str(getattr(recipe, "provider", "")).strip().lower()
    if provider == "flux2":
        from gateway.flux2_targets import Flux2TargetError, resolve_flux2_target

        target_id = getattr(recipe, "execution_target", None)
        if not target_id:
            return None
        try:
            return resolve_flux2_target(str(target_id)).model_id
        except Flux2TargetError:
            return None
    if provider == "flux":
        return FLUX_EDIT_MODEL if operation == "img2img" else FLUX_GENERATE_MODEL
    if provider == "openrouter":
        return OPENROUTER_IMAGE_MODEL
    if provider == "openai":
        return OPENAI_IMAGE_MODEL
    if provider == "comfyui":
        from gateway.image_gen import SDXL_PHOTONIC

        return SDXL_PHOTONIC
    if provider in {"airforce", "fal", "drawthings"}:
        try:
            from mcp.imagen.engines import get

            return getattr(get(provider), "model_name", None)
        except Exception:
            return None
    return None


def _validate_iteration_route(request: dict) -> None:
    """Fail before dispatch when a retry/duplicate can no longer reproduce its source route."""
    expected_provider = request.get("expected_provider")
    expected_model_id = request.get("expected_model_id")
    if not expected_provider and not expected_model_id:
        return

    recipe_id = request.get("recipe_id")
    parent_id = request.get("lineage_parent_id")
    if not recipe_id or not parent_id:
        raise HTTPException(status_code=409, detail="source route cannot be proven for this iteration")

    from gateway import image_jobs

    source = image_jobs.get_job(str(parent_id))
    if source is None:
        raise HTTPException(status_code=409, detail="source route cannot be proven because the source job is missing")
    if expected_provider and source.provider != expected_provider:
        raise HTTPException(status_code=409, detail="source route metadata no longer matches the source provider")
    if expected_model_id and source.model_id != expected_model_id:
        raise HTTPException(status_code=409, detail="source route metadata no longer matches the source model")

    try:
        recipe = image_recipes.get_recipe(str(recipe_id))
    except image_recipes.RecipeError as exc:
        raise HTTPException(status_code=409, detail="source route recipe is no longer available") from exc
    if not recipe.is_available:
        raise HTTPException(status_code=409, detail="source route recipe is currently unavailable")
    if expected_provider and recipe.provider != expected_provider:
        raise HTTPException(status_code=409, detail="source route provider changed; refusing to reroute the iteration")

    current_model_id = _iteration_model_id(recipe, operation=source.operation)
    if expected_model_id and current_model_id != expected_model_id:
        raise HTTPException(status_code=409, detail="source route model changed; refusing to reroute the iteration")


async def _runtime_available_providers() -> set[str]:
    """Return provider ids whose actual execution transports are ready now."""
    from gateway.routes.extended import image_status

    status = await image_status()
    return {
        str(engine.get("name", "")).strip().lower()
        for engine in status.get("engines", [])
        if engine.get("available") is True and engine.get("name")
    }


async def studio_estimate(req: StudioEstimateRequest) -> dict:
    try:
        available_providers = await _runtime_available_providers()
        decision = image_recipes.auto_route(
            has_character=bool(req.character_id),
            character_count=1 if req.character_id else 0,
            quality_tier=req.quality,
            identity_mode=req.identity,
            operation=req.operation,
            preferred_recipe=req.recipe_id,
            available_providers=available_providers,
        )
    except image_recipes.RecipeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    recipe = decision.recipe
    if req.operation == "img2img" and (recipe is None or not recipe.supports_img2img):
        raise HTTPException(
            status_code=503,
            detail=f"recipe {decision.recipe_id!r} does not support img2img",
        )
    provider = recipe.provider if recipe else "comfyui"
    model_id = (
        _iteration_model_id(recipe, operation=req.operation)
        if recipe is not None
        else _exact_model_id(provider)
    )
    per_image = image_estimates.estimate(
        provider, model_id=model_id, operation=req.operation
    )
    return {
        "provider": provider,
        "model_id": model_id,
        "recipe_id": decision.recipe_id,
        "routing_reason": decision.reason,
        "operation": req.operation,
        "count": req.count,
        "per_image_estimate": per_image,
        "estimate": image_batches.scale_estimate(per_image, req.count),
    }


@router.post("/studio/estimate")
async def studio_estimate_route(req: StudioEstimateRequest) -> dict:
    return await studio_estimate(req)




@router.post("/studio/sessions/{session_id}/source-image")
async def studio_import_source_image(session_id: str, file: UploadFile) -> dict:
    """Import a user-owned image as the durable edit source for a Studio session."""
    from gateway import image_jobs, image_sessions, undo_journal
    from gateway.image_quality import check_reference_image

    try:
        session = image_sessions.require_session(session_id)
    except image_sessions.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if session.status.is_terminal():
        raise HTTPException(status_code=409, detail=f"image session {session_id!r} has ended")

    media_type = (file.content_type or "").lower().strip()
    if media_type not in _SOURCE_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="source image must be PNG, JPEG, or WebP")
    data = await file.read(_SOURCE_IMAGE_MAX_BYTES + 1)
    if len(data) > _SOURCE_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="source image is too large (max 20 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="source image is empty")

    quality = check_reference_image(data)
    if quality.has_blockers or not quality.format or not quality.width or not quality.height:
        raise HTTPException(status_code=400, detail=quality.summary())
    extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(quality.format.upper())
    if extension is None:
        raise HTTPException(status_code=415, detail="source image must be PNG, JPEG, or WebP")

    job = image_jobs.create_job(
        provider="upload",
        operation="import",
        width=quality.width,
        height=quality.height,
        provider_params_json=json.dumps({
            "source": "user_upload",
            "original_name": file.filename,
            "media_type": media_type,
        }),
    )
    try:
        image_sessions.attach_job(session_id, job.job_id)
        image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUBMITTED)
        image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.RUNNING)
        target_dir = _SOURCE_IMAGE_ROOT / job.job_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"source{extension}"
        partial = target.with_suffix(target.suffix + ".part")
        partial.write_bytes(data)
        partial.replace(target)
        image_jobs.update_job(
            job.job_id,
            output_path=str(target),
            width=quality.width,
            height=quality.height,
        )
        artifact = image_jobs.register_canonical_artifact(
            job.job_id, project_id=session.project_id
        )
        image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUCCEEDED)
        undo_journal_id = undo_journal.set_anchor_with_undo(session_id, job.job_id)
    except Exception as exc:
        current = image_jobs.get_job(job.job_id)
        if current is not None and not current.status.is_terminal():
            try:
                image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.FAILED)
            except Exception:
                pass
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    refreshed = image_jobs.get_job(job.job_id)
    assert refreshed is not None
    return {
        "job": refreshed.to_dict(),
        "artifact": artifact,
        "session": image_sessions.require_session(session_id).to_dict(),
        "undo_journal_id": undo_journal_id,
        "quality": {
            "has_blockers": quality.has_blockers,
            "has_warnings": quality.has_warnings,
            "is_perfect": quality.is_perfect,
            "summary": quality.summary(),
            "advice": quality.advice(),
            "dimensions": f"{quality.width}×{quality.height}",
        },
    }


@router.post("/studio/batches")
async def studio_create_batch(req: StudioBatchRequest) -> dict:
    operation: ImageOperation = "txt2img"
    recipe_id = req.recipe_id
    character_id = req.character_id
    if req.plan_id:
        if not req.session_id:
            raise HTTPException(
                status_code=400, detail="a planned image batch requires session_id"
            )
        from gateway.image_plans import (
            PlanNotApprovedError,
            PlanNotFoundError,
            PlanSessionMismatchError,
            PlanStoreError,
            require_approved_plan,
        )
        try:
            plan = require_approved_plan(req.plan_id, req.session_id)
        except PlanNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (PlanSessionMismatchError, PlanNotApprovedError, PlanStoreError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        operation = plan.operation
        recipe_id = plan.recipe_id
        character_id = plan.character_id

    preflight = await studio_estimate(
        StudioEstimateRequest(
            quality=req.quality,
            identity=req.identity,
            operation=operation,
            character_id=character_id,
            recipe_id=recipe_id,
            count=req.count,
        )
    )
    request = req.model_dump(exclude={"count"})
    if req.plan_id:
        request["recipe_id"] = recipe_id
    request["estimated_operation"] = operation
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

    _validate_iteration_route(request)
    payload = {
        key: value
        for key, value in request.items()
        if key not in {
            "estimated_provider", "estimated_model_id", "estimated_operation", "lineage_parent_id",
            "expected_provider", "expected_model_id",
        }
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
