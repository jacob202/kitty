"""Image generation runner — deep module owning job lifecycle and engine dispatch.

Routes become thin handlers: request model → run() → status-code mapping.
The runner owns: job creation, engine dispatch, lifecycle transitions,
artifact persistence, error normalization, and character-ref resolution.

Invariant: if run() returns or raises, the job is in a terminal state.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from gateway import image_jobs
from gateway.image_jobs import ImageJobStatus


class ImageRunnerError(RuntimeError):
    """Raised when the image runner cannot complete a generation request."""


@dataclass
class JobResult:
    """Result of a successful image generation."""
    job_id: str
    filename: str
    prompt_id: str | None = None
    engine: str = "comfyui"
    recipe: str | None = None
    routing_reason: str | None = None
    character_weight: float | None = None


async def run(
    engine: str,
    prompt: str,
    *,
    recipe: Any | None = None,
    character_id: str | None = None,
    negative_prompt: str | None = None,
    parent_id: str | None = None,
) -> JobResult:
    """Generate an image through the specified engine.

    Args:
        engine: Engine name ("comfyui" or "drawthings").
        prompt: Generation prompt.
        recipe: Optional Recipe object (from image_recipes). Records
                workflow_template_id on the job; not yet used for workflow selection.
        character_id: Optional character ID. If set, resolves the primary
                      reference image and uses identity-preserving generation.
        negative_prompt: Optional negative prompt override.
        parent_id: Optional parent job ID for variations.

    Returns:
        JobResult with job_id, filename, and engine metadata.

    Raises:
        ImageRunnerError: On validation failure (e.g. character has no refs).
        TimeoutError: On generation timeout.
        ImageGenerationCancelled: If the job was canceled mid-flight.
        RuntimeError: On engine/ComfyUI failure.

    Invariant: if this function returns or raises, the job is in a terminal state.
    """
    engine = engine.strip().lower()
    if engine not in {"comfyui", "drawthings"}:
        raise ImageRunnerError(f"unknown engine {engine!r}; must be 'comfyui' or 'drawthings'")

    if engine == "drawthings":
        return await _run_drawthings(
            prompt, recipe=recipe, parent_id=parent_id,
        )

    # ComfyUI path
    if character_id:
        return await _run_comfyui_character(
            prompt,
            character_id=character_id,
            recipe=recipe,
            negative_prompt=negative_prompt,
        )

    return await _run_comfyui(
        prompt, recipe=recipe, parent_id=parent_id,
    )


async def _run_drawthings(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
) -> JobResult:
    """Draw Things engine path — dispatches via mcp.imagen engine registry."""
    from mcp.imagen.engines import get
    from mcp.imagen.io import save_image

    drawthings = get("drawthings")
    probe = getattr(getattr(drawthings, "_adapter", None), "is_available", None)
    if probe is not None and not await asyncio.to_thread(probe):
        raise ImageRunnerError("Draw Things is not running")

    workflow_template_id = recipe.workflow_template_id if recipe else None

    job = image_jobs.create_job(
        provider="drawthings",
        operation="variation" if parent_id else "txt2img",
        prompt=prompt,
        parent_id=parent_id,
        model_id=getattr(drawthings, "model_name", None),
        workflow_template_id=workflow_template_id,
    )

    try:
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        data = await drawthings.generate_async(prompt)
        path = await asyncio.to_thread(save_image, data, prefix="drawthings")
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine="drawthings",
        recipe=recipe.recipe_id if recipe else None,
    )


async def _run_comfyui(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
) -> JobResult:
    """Standard ComfyUI generation path (no character)."""
    from gateway.image_gen import generate, is_available

    if not await is_available():
        raise ImageRunnerError("ComfyUI is not running")

    result = await generate(prompt, parent_id=parent_id)
    return JobResult(
        job_id=result["job_id"],
        filename=result["filename"],
        prompt_id=result.get("prompt_id"),
        engine="comfyui",
        recipe=recipe.recipe_id if recipe else None,
    )


async def _run_comfyui_character(
    prompt: str,
    *,
    character_id: str,
    recipe: Any | None = None,
    negative_prompt: str | None = None,
) -> JobResult:
    """ComfyUI generation with character identity preservation."""
    from gateway.image_characters import (
        CharacterNotFoundError,
        get_character,
        list_character_refs,
    )
    from gateway.image_gen import generate_with_character, is_available

    if not await is_available():
        raise ImageRunnerError("ComfyUI is not running")

    try:
        char = get_character(character_id)
        refs = list_character_refs(character_id)
    except CharacterNotFoundError as exc:
        raise ImageRunnerError(str(exc)) from exc

    primary = next((r for r in refs if r.is_primary), refs[0] if refs else None)
    if not primary:
        raise ImageRunnerError(
            f"character {char.name!r} has no reference images — "
            "upload at least one reference photo"
        )

    result = await generate_with_character(
        prompt=prompt,
        character_ref_path=primary.storage_path,
        negative_prompt=negative_prompt,
    )

    return JobResult(
        job_id=result["job_id"],
        filename=result["filename"],
        prompt_id=result.get("prompt_id"),
        engine="comfyui",
        recipe=recipe.recipe_id if recipe else None,
        character_weight=result.get("character_weight"),
    )


def _mark_failed(job_id: str, message: str) -> None:
    """Record a failure unless the job already reached a terminal state."""
    job = image_jobs.get_job(job_id)
    if job is None:
        return
    if job.status.is_terminal():
        return
    image_jobs.update_job(job_id, normalized_error=message)
    image_jobs.transition(job_id, ImageJobStatus.FAILED)
