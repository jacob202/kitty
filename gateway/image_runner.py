"""Image generation runner — deep module owning job lifecycle and engine dispatch.

Routes become thin handlers: request model → run() → status-code mapping.
The runner owns job creation, engine dispatch, lifecycle transitions, artifact
persistence, error normalization, and character-contract resolution.

Invariant: if run() returns or raises, the job is in a terminal state.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
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
    guidance_tags: list[str] | None = None,
) -> JobResult:
    """Generate an image through the specified engine.

    A character ID is not merely a request to pick the first stored photo. It
    requires a valid character contract whose identity method, reference set,
    weights, prompt fragments, and recipe can all be honored by the engine.
    """
    engine = engine.strip().lower()
    if engine not in {"comfyui", "drawthings"}:
        raise ImageRunnerError(
            f"unknown engine {engine!r}; must be 'comfyui' or 'drawthings'"
        )

    if engine == "drawthings":
        return await _run_drawthings(
            prompt,
            recipe=recipe,
            parent_id=parent_id,
        )

    if character_id:
        return await _run_comfyui_character(
            prompt,
            character_id=character_id,
            recipe=recipe,
            negative_prompt=negative_prompt,
            guidance_tags=guidance_tags,
        )

    return await _run_comfyui(
        prompt,
        recipe=recipe,
        parent_id=parent_id,
        guidance_tags=guidance_tags,
    )


#: Fraction of the source image the sampler is allowed to rewrite. Low enough
#: that identity survives, high enough that a requested change actually lands.
DEFAULT_EDIT_DENOISE = 0.55

#: The only workflow that consumes a source image as a real input (slice A4).
EDIT_WORKFLOW_ID = "image_to_image_v1"


async def run_edit(
    prompt: str,
    *,
    anchor_job_id: str,
    worker: Any | None = None,
    denoise: float = DEFAULT_EDIT_DENOISE,
    recipe: Any | None = None,
    negative_prompt: str | None = None,
    checkpoint: str | None = None,
    seed: int | None = None,
) -> JobResult:
    """Edit the anchor job's artifact, rather than rerolling from its prompt.

    The anchor's rendered image is uploaded to the worker and passed to
    ``image_to_image_v1`` as an actual workflow input, so what comes back is
    derived from the selected result. A fresh text-to-image render whose prompt
    merely contains preservation words is not an edit, and this path cannot
    produce one — the workflow has a ``LoadImage`` node that must be bound.

    Omitting *worker* resolves one from the operator's environment
    (``KITTY_WORKER_URL`` and ``KITTY_WORKER_BEARER_TOKEN``). If either is
    unset this raises rather than falling back to a default endpoint — sending
    Jacob's images somewhere he did not configure is worse than not rendering.
    Tests pass a stub instead.

    Invariant: if this function returns or raises, the job is terminal.
    """
    if not 0 < denoise <= 1:
        raise ImageRunnerError(
            f"denoise must be within (0, 1], got {denoise}; 0 would return the "
            "source image unchanged"
        )

    owns_worker = worker is None
    if worker is None:
        from gateway.runpod_worker import client_from_env

        worker = client_from_env()

    source_bytes, source_name = _read_anchor_artifact(anchor_job_id)

    job = image_jobs.create_job(
        provider="kitty_worker",
        operation="img2img",
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        parent_id=anchor_job_id,
        workflow_template_id=EDIT_WORKFLOW_ID,
        provider_params_json=json.dumps(
            {"denoise": denoise, "source_job_id": anchor_job_id}
        ),
    )

    try:
        image = await worker.upload_source_image(source_bytes)
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)

        submitted = await worker.submit(
            workflow_id=EDIT_WORKFLOW_ID,
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            checkpoint=checkpoint,
            width=image.width,
            height=image.height,
            steps=20,
            guidance=5.0,
            seed=seed if seed is not None else 0,
            source_image_id=image.image_id,
            denoise=denoise,
            client_action_id=job.job_id,
        )
        image_jobs.update_job(
            job.job_id,
            provider_job_id=submitted.job_id,
            workflow_hash=submitted.workflow_sha256 or None,
        )
        image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)

        finished = await worker.wait(
            submitted.job_id,
            timeout_seconds=600,
            poll_interval_seconds=2.0,
        )
        if not finished.outputs:
            raise ImageRunnerError(
                f"worker job {submitted.job_id} succeeded without an artifact"
            )
        output = finished.outputs[0]
        artifact = await worker.download(output)
        output_path = _persist_artifact(job.job_id, output.filename, artifact)

        image_jobs.update_job(
            job.job_id,
            output_path=str(output_path),
            artifact_id=output.asset_id,
        )
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if owns_worker:
            await worker.aclose()

    return JobResult(
        job_id=job.job_id,
        filename=str(output_path),
        prompt_id=submitted.job_id,
        engine="kitty_worker",
        recipe=recipe.recipe_id if recipe else None,
        routing_reason=f"edit of {source_name} at denoise {denoise}",
    )


def _read_anchor_artifact(anchor_job_id: str) -> tuple[bytes, str]:
    """Load the bytes a follow-up edit is supposed to build on."""
    anchor = image_jobs.get_job(anchor_job_id)
    if anchor is None:
        raise ImageRunnerError(f"no image job {anchor_job_id!r} to edit from")
    if anchor.status is not ImageJobStatus.SUCCEEDED:
        raise ImageRunnerError(
            f"job {anchor_job_id!r} is {anchor.status.value}; only a succeeded "
            "job can be edited"
        )
    if not anchor.output_path:
        raise ImageRunnerError(
            f"job {anchor_job_id!r} succeeded but has no artifact to edit from"
        )
    source = Path(anchor.output_path)
    if not source.is_file():
        raise ImageRunnerError(
            f"artifact for job {anchor_job_id!r} is missing from disk: {source}"
        )
    return source.read_bytes(), source.name


def _persist_artifact(job_id: str, filename: str, data: bytes) -> Path:
    from gateway import paths as _paths

    out_dir = _paths.DATA_DIR / "images" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / Path(filename).name
    target.write_bytes(data)
    return target


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
    guidance_tags: list[str] | None = None,
) -> JobResult:
    """Standard ComfyUI generation path (no character)."""
    from gateway.image_gen import generate, is_available

    if not await is_available():
        raise ImageRunnerError("ComfyUI is not running")

    result = await generate(
        prompt,
        parent_id=parent_id,
        guidance_tags=guidance_tags,
    )
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
    guidance_tags: list[str] | None = None,
) -> JobResult:
    """Generate through the exact stored character contract.

    Legacy behavior picked the primary photo—or simply the first photo—and
    silently ignored the written description, all other references, weights,
    fusion method, provenance, and recipe. The resolver now refuses every field
    the current single-reference IP-Adapter workflow cannot honor.
    """
    from gateway.image_character_contracts import (
        CharacterContractError,
        resolve_comfyui_character,
    )
    from gateway.image_gen import (
        generate_with_character,
        is_available,
        is_identity_ready,
    )

    if not await is_available():
        raise ImageRunnerError("ComfyUI is not running")
    if not await is_identity_ready():
        raise ImageRunnerError(
            "ComfyUI is running but its identity workflow is not ready; "
            "verify the IP-Adapter nodes and configured adapter model"
        )

    try:
        resolved = resolve_comfyui_character(character_id)
    except CharacterContractError as exc:
        raise ImageRunnerError(str(exc)) from exc

    final_prompt = ", ".join(
        part.strip()
        for part in (resolved["positive_prompt"], prompt)
        if isinstance(part, str) and part.strip()
    )
    final_negative = ", ".join(
        part.strip()
        for part in (resolved["negative_prompt"], negative_prompt)
        if isinstance(part, str) and part.strip()
    )

    result = await generate_with_character(
        prompt=final_prompt,
        character_ref_path=resolved["reference_path"],
        identity_mode=resolved["identity_mode"],
        negative_prompt=final_negative or None,
        width=resolved["width"],
        height=resolved["height"],
        steps=resolved["steps"],
        cfg=resolved["guidance"],
        guidance_tags=guidance_tags,
    )

    return JobResult(
        job_id=result["job_id"],
        filename=result["filename"],
        prompt_id=result.get("prompt_id"),
        engine="comfyui",
        recipe=resolved["recipe_id"],
        routing_reason=(
            f"character contract {character_id}: {resolved['identity_method']} "
            f"with {len(resolved['references'])} reference(s)"
        ),
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
