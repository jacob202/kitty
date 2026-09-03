"""Image generation runner — deep module owning job lifecycle and engine dispatch.

Routes become thin handlers: request model → run() → status-code mapping.
The runner owns job creation, engine dispatch, lifecycle transitions, artifact
persistence, error normalization, and character-contract resolution.

Invariant: if run() returns or raises, the job is terminal or explicitly quarantined UNKNOWN.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gateway import image_jobs
from gateway.image_jobs import ImageJobStatus


class ImageRunnerError(RuntimeError):
    """Raised when the image runner cannot complete a generation request."""


class ImageDispatchNotSubmittedError(ImageRunnerError):
    """Raised only when Kitty can prove no provider submission occurred."""


class ImageProviderOutcomeUnknownError(ImageRunnerError):
    """Raised when a paid provider may have accepted work but outcome is unknown."""


FAL_PULID_COST_PER_OUTPUT_MP_USD = 0.0333


def fal_pulid_contract_cost_usd_for_dimensions(width: int, height: int) -> float:
    """Return fal PuLID's contractual output charge for exact image dimensions."""
    import math

    if isinstance(width, bool) or isinstance(height, bool) or width <= 0 or height <= 0:
        raise ImageRunnerError("fal output dimensions must be positive integers")
    billed_mp = max(math.ceil((width * height) / 1_000_000.0), 1)
    return round(billed_mp * FAL_PULID_COST_PER_OUTPUT_MP_USD, 6)


def _fal_pulid_contract_cost_and_dimensions(image_data: bytes) -> tuple[float, int, int]:
    """Decode provider bytes and return billed amount plus auditable dimensions."""
    import io

    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(image_data)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageRunnerError("fal returned an undecodable image; cost cannot be settled") from exc
    return fal_pulid_contract_cost_usd_for_dimensions(width, height), width, height


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
    cost_usd: float | None = None
    cost_source: str | None = None


async def run(
    engine: str,
    prompt: str,
    *,
    recipe: Any | None = None,
    character_id: str | None = None,
    character_ref_path: str | None = None,
    negative_prompt: str | None = None,
    parent_id: str | None = None,
    guidance_tags: list[str] | None = None,
    source_image: bytes | None = None,
    quality_tier: str | None = None,
    content_lane: str = "safe",
    consent_basis: str | None = None,
    adult_confirmed: bool = False,
    flux2_target: Any | None = None,
    compiled_request: Any | None = None,
    reference_bytes: tuple[bytes, ...] = (),
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
    session_id: str | None = None,
    reserved_cost_usd: float | None = None,
) -> JobResult:
    """Generate an image through the specified engine.

    A character ID is not merely a request to pick the first stored photo. It
    requires a valid character contract whose identity method, reference set,
    weights, prompt fragments, and recipe can all be honored by the engine.

    *content_lane*/*consent_basis*/*adult_confirmed* carry the approved plan's
    execution policy (ADR 0040 #8). They default to the safe lane, and are
    validated against *engine* through the canonical policy seam before any
    network or renderer call — so even a direct runner invocation cannot route
    private work to a hosted provider.
    """
    engine = engine.strip().lower()
    from gateway.image_policy import validate_image_execution_policy

    validate_image_execution_policy(
        content_lane, consent_basis, adult_confirmed, engine
    )
    if engine not in ENGINES:
        raise ImageRunnerError(
            f"unknown engine {engine!r}; must be one of {', '.join(sorted(ENGINES))}"
        )

    if engine == "flux":
        return await _run_flux(
            prompt, recipe=recipe, parent_id=parent_id, source_image=source_image,
            project_id=project_id, plan_id=plan_id, intent_json=intent_json,
            session_id=session_id, reserved_cost_usd=reserved_cost_usd,
        )

    if engine == "flux2":
        return await _run_flux2(
            prompt,
            recipe=recipe,
            parent_id=parent_id,
            target=flux2_target,
            compiled=compiled_request,
            reference_bytes=reference_bytes,
            negative_prompt=negative_prompt,
            project_id=project_id,
            plan_id=plan_id,
            intent_json=intent_json,
            session_id=session_id,
            reserved_cost_usd=reserved_cost_usd,
        )

    if engine == "openai":
        return await _run_openai(
            prompt, recipe=recipe, parent_id=parent_id, source_image=source_image,
            character_ref_path=character_ref_path, project_id=project_id,
            plan_id=plan_id, intent_json=intent_json, session_id=session_id,
            quality_tier=quality_tier,
        )

    if engine == "openrouter":
        return await _run_openrouter(
            prompt, recipe=recipe, parent_id=parent_id, source_image=source_image,
            project_id=project_id, plan_id=plan_id, intent_json=intent_json,
        )

    if engine == "drawthings":
        return await _run_drawthings(
            prompt,
            recipe=recipe,
            parent_id=parent_id,
            source_image=source_image,
            project_id=project_id,
            plan_id=plan_id,
            intent_json=intent_json,
        )

    if engine in {"airforce", "fal"}:
        return await _run_registry_hosted(
            engine,
            prompt,
            recipe=recipe,
            character_id=character_id,
            character_ref_path=character_ref_path,
            negative_prompt=negative_prompt,
            parent_id=parent_id,
            project_id=project_id,
            plan_id=plan_id,
            intent_json=intent_json,
        )

    if character_id:
        return await _run_comfyui_character(
            prompt,
            character_id=character_id,
            recipe=recipe,
            negative_prompt=negative_prompt,
            guidance_tags=guidance_tags,
            project_id=project_id,
            plan_id=plan_id,
            intent_json=intent_json,
        )

    return await _run_comfyui(
        prompt,
        recipe=recipe,
        parent_id=parent_id,
        guidance_tags=guidance_tags,
        project_id=project_id,
        plan_id=plan_id,
        intent_json=intent_json,
    )


DEFAULT_EDIT_DENOISE = 0.55
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
    content_lane: str = "safe",
    consent_basis: str | None = None,
    adult_confirmed: bool = False,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
) -> JobResult:
    """Edit the anchor job's artifact, rather than rerolling from its prompt.

    The edit lane is the only Kitty-controlled private executor in v1, and the
    content-lane policy is validated before any worker configuration or network
    call: a private plan may only land here, and a direct invocation of this
    function cannot be coerced into a hosted fallback.
    """
    from gateway.image_policy import validate_image_execution_policy

    validate_image_execution_policy(
        content_lane, consent_basis, adult_confirmed, "kitty_worker"
    )

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
        plan_id=plan_id,
        intent_json=intent_json,
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
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
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


def read_anchor_artifact(anchor_job_id: str) -> tuple[bytes, str]:
    """Public wrapper for transport wiring: bytes + filename of a succeeded
    anchor job artifact, for hosted reference conditioned rendering."""
    return _read_anchor_artifact(anchor_job_id)


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


async def _run_registry_hosted(
    engine_name: str,
    prompt: str,
    *,
    recipe: Any | None = None,
    character_id: str | None = None,
    character_ref_path: str | None = None,
    negative_prompt: str | None = None,
    parent_id: str | None = None,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
) -> JobResult:
    """Dispatch an existing MCP hosted engine through Kitty's durable job spine."""
    from mcp.imagen.engines import get
    from mcp.imagen.io import save_image

    identity_images: list[Path] | None = None
    if engine_name == "fal":
        if not character_id or not character_ref_path:
            raise ImageDispatchNotSubmittedError(
                "fal character generation requires a bound character reference"
            )
        ref_path = Path(character_ref_path)
        if not ref_path.is_file():
            raise ImageDispatchNotSubmittedError(
                f"bound character reference is missing from disk: {ref_path}"
            )
        identity_images = [ref_path]
    elif character_id:
        raise ImageDispatchNotSubmittedError(
            f"{engine_name} cannot honor character identity conditioning; use fal instead"
        )

    available, reason = paid_engine_available(engine_name)
    if not available:
        raise ImageDispatchNotSubmittedError(reason)

    provider = get(engine_name)
    job = image_jobs.create_job(
        provider=engine_name,
        operation="variation" if parent_id else "txt2img",
        prompt=prompt,
        parent_id=parent_id,
        model_id=getattr(provider, "model_name", None),
        workflow_template_id=recipe.workflow_template_id if recipe else None,
        plan_id=plan_id,
        intent_json=intent_json,
    )

    kwargs: dict[str, Any] = {}
    if identity_images is not None:
        kwargs["identity_images"] = identity_images
    if negative_prompt:
        kwargs["negative_prompt"] = negative_prompt

    try:
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        data = await provider.generate_async(prompt, **kwargs)
        cost_usd = None
        cost_source = None
        if engine_name == "fal":
            cost_usd, output_width, output_height = _fal_pulid_contract_cost_and_dimensions(data)
            cost_source = "provider_contract"
            image_jobs.update_job(job.job_id, width=output_width, height=output_height)
        path = await asyncio.to_thread(save_image, data, prefix=engine_name)
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine=engine_name,
        recipe=recipe.recipe_id if recipe else None,
        cost_usd=cost_usd,
        cost_source=cost_source,
    )


async def _run_drawthings(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
    source_image: bytes | None = None,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
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
        operation="img2img" if source_image is not None else ("variation" if parent_id else "txt2img"),
        prompt=prompt,
        parent_id=parent_id,
        model_id=getattr(drawthings, "model_name", None),
        workflow_template_id=workflow_template_id,
        plan_id=plan_id,
        intent_json=intent_json,
    )

    try:
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        if source_image is not None:
            import tempfile

            source_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as handle:
                    handle.write(source_image)
                    source_path = Path(handle.name)
                data = await drawthings.generate_async(
                    prompt,
                    init_image=source_path,
                    denoising_strength=DEFAULT_EDIT_DENOISE,
                )
            finally:
                if source_path is not None:
                    source_path.unlink(missing_ok=True)
        else:
            data = await drawthings.generate_async(prompt)
        path = await asyncio.to_thread(save_image, data, prefix="drawthings")
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
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
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
) -> JobResult:
    """Standard ComfyUI generation path (no character)."""
    from gateway.image_gen import generate, is_available

    if not await is_available():
        raise ImageRunnerError("ComfyUI is not running")

    result = await generate(
        prompt,
        parent_id=parent_id,
        guidance_tags=guidance_tags,
        project_id=project_id,
        plan_id=plan_id,
        intent_json=intent_json,
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
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
) -> JobResult:
    """Generate through the exact stored character contract."""
    from gateway.image_character_contracts import (
        CharacterContractError,
        comfyui_character_runtime_status,
        resolve_comfyui_character,
    )
    from gateway.image_gen import generate_with_character, is_available

    if not await is_available():
        raise ImageRunnerError("ComfyUI is not running")

    try:
        resolved = resolve_comfyui_character(character_id)
    except CharacterContractError as exc:
        raise ImageRunnerError(str(exc)) from exc

    ready, readiness_reason = await comfyui_character_runtime_status()
    if not ready:
        raise ImageRunnerError(
            "ComfyUI is running but its identity workflow is not ready: "
            f"{readiness_reason}"
        )

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
        project_id=project_id,
        plan_id=plan_id,
        intent_json=intent_json,
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
    """Record a known failure without collapsing an unresolved provider outcome."""
    job = image_jobs.get_job(job_id)
    if job is None:
        return
    if job.status.is_terminal() or job.status is ImageJobStatus.UNKNOWN:
        return
    image_jobs.update_job(job_id, normalized_error=message)
    image_jobs.transition(job_id, ImageJobStatus.FAILED)


def _mark_unknown(job_id: str, message: str) -> None:
    """Preserve an ambiguous post-submission outcome for later reconciliation."""
    job = image_jobs.get_job(job_id)
    if job is None or job.status.is_terminal():
        return
    image_jobs.update_job(job_id, normalized_error=message)
    if job.status is not ImageJobStatus.UNKNOWN:
        image_jobs.transition(job_id, ImageJobStatus.UNKNOWN)


def _persist_bfl_receipt(
    job_id: str,
    submit_payload: dict[str, Any],
    *,
    project_id: int | None,
    session_id: str | None = None,
    reserved_cost_usd: float | None = None,
) -> str:
    """Persist the provider request identity and poll locator before waiting."""
    polling_url = str(submit_payload.get("polling_url") or "").strip()
    if not polling_url:
        raise ImageProviderOutcomeUnknownError("BFL accepted a request without a polling_url")
    request_id = str(submit_payload.get("id") or polling_url).strip()
    diagnostics: dict[str, Any] = {
        "receipt_version": 1,
        "request_id": request_id,
        "polling_url": polling_url,
    }
    if project_id is not None:
        diagnostics["project_id"] = project_id
    if session_id is not None:
        diagnostics["session_id"] = session_id
    if reserved_cost_usd is not None:
        diagnostics["reserved_cost_usd"] = float(reserved_cost_usd)
    raw_cost = submit_payload.get("cost")
    if isinstance(raw_cost, (int, float)) and not isinstance(raw_cost, bool) and raw_cost >= 0:
        diagnostics["provider_cost_credits"] = float(raw_cost)
    image_jobs.update_job(
        job_id,
        provider_job_id=request_id,
        provider_diagnostics_json=json.dumps(diagnostics, sort_keys=True),
    )
    return polling_url


def _attach_job_to_session_before_dispatch(job_id: str, session_id: str | None) -> None:
    """Persist Studio ownership before any provider call can become billable."""
    if session_id is None:
        return
    from gateway.image_sessions import ImageSessionError, attach_job

    try:
        attach_job(session_id, job_id)
    except ImageSessionError as exc:
        raise ImageDispatchNotSubmittedError(str(exc)) from exc


async def recover_bfl_job(job_id: str) -> JobResult:
    """Recover one UNKNOWN BFL job from its durable receipt without resubmitting."""
    import httpx

    job = image_jobs.get_job(job_id)
    if job is None:
        raise ImageRunnerError(f"no image job {job_id!r} to recover")
    if job.status is not ImageJobStatus.UNKNOWN:
        raise ImageRunnerError(
            f"job {job_id!r} is {job.status.value}; only unknown BFL jobs are recoverable"
        )
    if job.provider not in {"flux", "flux2"}:
        raise ImageRunnerError(
            f"job {job_id!r} uses provider {job.provider!r}; BFL recovery is unsupported"
        )

    try:
        diagnostics = json.loads(job.provider_diagnostics_json or "{}")
    except json.JSONDecodeError as exc:
        raise ImageProviderOutcomeUnknownError(
            f"job {job_id!r} has an unreadable BFL provider receipt"
        ) from exc
    if not isinstance(diagnostics, dict):
        raise ImageProviderOutcomeUnknownError(
            f"job {job_id!r} has an invalid BFL provider receipt"
        )
    polling_url = str(diagnostics.get("polling_url") or "").strip()
    if not polling_url:
        raise ImageProviderOutcomeUnknownError(
            f"job {job_id!r} has no durable BFL polling URL; provider outcome remains unknown"
        )
    api_key = os.environ.get("BFL_API_KEY", "").strip()
    if not api_key:
        raise ImageProviderOutcomeUnknownError(
            f"job {job_id!r} cannot reconcile until BFL_API_KEY is configured"
        )

    headers = {"x-key": api_key}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            for _ in range(150):
                poll = await client.get(polling_url, headers=headers)
                poll.raise_for_status()
                state = poll.json()
                status = str(state.get("status") or "")
                if status not in {"Pending", "Queued", "Processing"}:
                    break
                await asyncio.sleep(2)
            else:
                message = f"job {job_id!r} BFL reconciliation timed out; outcome remains unknown"
                _mark_unknown(job_id, message)
                raise ImageProviderOutcomeUnknownError(message)

            if status != "Ready":
                message = f"BFL reconciled job {job_id!r} as {status or 'failed'}"
                image_jobs.update_job(job_id, normalized_error=message)
                image_jobs.transition(job_id, ImageJobStatus.FAILED)
                raise ImageRunnerError(message)

            result = state.get("result") or {}
            sample = result.get("sample") if isinstance(result, dict) else None
            if not sample:
                message = f"BFL reported job {job_id!r} Ready without a recoverable image URL"
                _mark_unknown(job_id, message)
                raise ImageProviderOutcomeUnknownError(message)

            download = await client.get(str(sample))
            download.raise_for_status()
            data = download.content
    except ImageRunnerError:
        raise
    except httpx.HTTPError as exc:
        message = f"BFL reconciliation transport error for job {job_id!r}: {exc}"
        _mark_unknown(job_id, message)
        raise ImageProviderOutcomeUnknownError(message) from exc

    seed = result.get("seed") if isinstance(result, dict) else None
    if seed is not None:
        diagnostics["seed"] = seed
        image_jobs.update_job(
            job_id, provider_diagnostics_json=json.dumps(diagnostics, sort_keys=True)
        )

    path = _persist_artifact(job_id, f"{job_id}.png", data)
    image_jobs.update_job(job_id, output_path=str(path))
    project_id = diagnostics.get("project_id")
    image_jobs.register_canonical_artifact(
        job_id, project_id=project_id if isinstance(project_id, int) else None
    )

    raw_cost = diagnostics.get("provider_cost_credits")
    cost_usd = (
        float(raw_cost) * 0.01
        if isinstance(raw_cost, (int, float)) and not isinstance(raw_cost, bool) and raw_cost >= 0
        else None
    )
    receipt_session_id = diagnostics.get("session_id")
    reserved_cost = diagnostics.get("reserved_cost_usd")
    if (
        isinstance(receipt_session_id, str)
        and isinstance(reserved_cost, (int, float))
        and not isinstance(reserved_cost, bool)
        and cost_usd is not None
    ):
        from gateway.image_sessions import (
            ImageSessionError,
            finalize_recovered_paid_job,
        )

        try:
            finalize_recovered_paid_job(
                receipt_session_id,
                job_id,
                reserved_cost_usd=float(reserved_cost),
                actual_cost_usd=cost_usd,
            )
        except ImageSessionError as exc:
            message = f"BFL artifact recovered but spend settlement remains unresolved: {exc}"
            _mark_unknown(job_id, message)
            raise ImageProviderOutcomeUnknownError(message) from exc
    else:
        image_jobs.transition(job_id, ImageJobStatus.SUCCEEDED)
    return JobResult(
        job_id=job_id,
        filename=str(path),
        engine=job.provider,
        cost_usd=cost_usd,
        cost_source="provider_reported" if cost_usd is not None else None,
    )


async def recover_unknown_bfl_jobs(limit: int = 50) -> int:
    """Best-effort recovery pass for unresolved BFL jobs; never submits new work."""
    recovered = 0
    for job in image_jobs.list_unknown(limit=limit):
        if job.provider not in {"flux", "flux2"}:
            continue
        try:
            await recover_bfl_job(job.job_id)
        except ImageRunnerError:
            continue
        recovered += 1
    return recovered


#: Engines ``run`` will dispatch to. Hosted engines carry a conservative
#: contracted per-render estimate so the session budget can be reserved before
#: a provider call is allowed to spend money.
ENGINES = frozenset({"comfyui", "drawthings", "airforce", "fal", "flux", "flux2", "openrouter", "openai"})
_ESTIMATED_COST_USD = {
    "comfyui": 0.0,
    "drawthings": 0.0,
    # The worker edit lane is Kitty-owned and not billed per render.
    "kitty_worker": 0.0,
    # Current list prices are lower; reserve conservatively to avoid spending
    # beyond a session budget when provider-reported actual cost is unavailable.
    "airforce": 0.02,
    "fal": 0.07,
    # Budget reservations are deliberately conservative ceilings, not price
    # claims. Actual provider-reported cost is reconciled after success when
    # available.
    "flux": 0.08,
    "openrouter": 0.15,
    # Conservative high-quality square ceiling. Actual GPT-Image-2 token usage
    # is reconciled from the provider response when available.
    "openai": 0.25,
}


def estimated_cost_usd(engine: str) -> float:
    """Return the conservative per-render cost used for pre-dispatch budgeting."""
    normalized = engine.strip().lower()
    try:
        return _ESTIMATED_COST_USD[normalized]
    except KeyError as exc:
        raise ImageRunnerError(f"no cost contract for image engine {engine!r}") from exc


def paid_engine_available(engine: str) -> tuple[bool, str]:
    """Preflight a hosted lane before consuming any session budget."""
    normalized = engine.strip().lower()
    if normalized == "flux":
        return flux_images_available()
    if normalized == "flux2":
        return flux2_images_available()
    if normalized == "openrouter":
        return openrouter_images_available()
    if normalized == "openai":
        return openai_images_available()
    if normalized == "airforce":
        return airforce_images_available()
    if normalized == "fal":
        return fal_images_available()
    if normalized in {"comfyui", "drawthings", "kitty_worker"}:
        return True, ""
    raise ImageRunnerError(f"no availability contract for image engine {engine!r}")

#: Accepts image input as well as text, so the same route does img2img editing.
OPENROUTER_IMAGE_MODEL = os.environ.get(
    "KITTY_IMAGE_MODEL", "google/gemini-3.1-flash-image"
)
_TRUTHY = {"1", "true", "yes", "on"}


def paid_images_enabled() -> bool:
    """Off unless Jacob turns it on.

    Measured 2026-08-02: ~$0.067 per image on gemini-3.1-flash-image. Cheap next
    to a rented GPU box, not free, and fal was retired over exactly this — so
    nothing here spends until the switch is thrown. Read per call rather than at
    import so the answer follows the environment.
    """
    return os.environ.get("KITTY_IMAGE_PAID_ENABLED", "").strip().lower() in _TRUTHY


def _hosted_engine_enabled(provider: str) -> bool:
    """Provider-specific opt-in, falling back to the legacy global paid switch."""
    raw = os.environ.get(f"KITTY_IMAGE_{provider.upper()}_ENABLED")
    if raw is not None and raw.strip():
        return raw.strip().lower() in _TRUTHY
    return paid_images_enabled()


def hosted_image_configured(provider: str) -> tuple[bool, str]:
    normalized = provider.strip().lower()
    if normalized not in {"airforce", "fal", "openai"}:
        raise ImageRunnerError(f"no hosted image configuration contract for {provider!r}")
    if not _hosted_engine_enabled(normalized):
        env_name = f"KITTY_IMAGE_{normalized.upper()}_ENABLED"
        label = {"airforce": "Airforce", "fal": "fal", "openai": "OpenAI"}[normalized]
        return False, (
            f"{label} image generation is off. Set {env_name}=1 in .env and "
            f"restart Kitty to use your {label} credits."
        )
    key_name = {"airforce": "AIRFORCE_API_KEY", "fal": "FAL_KEY", "openai": "OPENAI_API_KEY"}[normalized]
    if not os.environ.get(key_name, "").strip():
        return False, f"{key_name} is not set"
    return True, ""


_HOSTED_HEALTH_CACHE: dict[tuple[str, str, str], tuple[float, tuple[bool, str]]] = {}


def _hosted_health_ttl_seconds() -> float:
    raw = os.environ.get("KITTY_IMAGE_PROVIDER_HEALTH_TTL_SECONDS", "60").strip()
    try:
        return max(0.0, min(float(raw), 300.0))
    except ValueError:
        return 60.0


def _cached_hosted_health(
    provider: str, model: str, api_key: str, probe
) -> tuple[bool, str]:
    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
    cache_key = (provider, model, fingerprint)
    ttl = _hosted_health_ttl_seconds()
    now = time.monotonic()
    cached = _HOSTED_HEALTH_CACHE.get(cache_key)
    if ttl > 0 and cached is not None and cached[0] > now:
        return cached[1]
    result = probe()
    if ttl > 0:
        _HOSTED_HEALTH_CACHE[cache_key] = (now + ttl, result)
    return result


def _probe_airforce_image_health(api_key: str, model: str) -> tuple[bool, str]:
    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_balance", "arguments": {}},
    }
    try:
        response = httpx.post(
            "https://api.airforce/mcp",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=5,
        )
    except httpx.HTTPError as exc:
        return False, f"Airforce health check failed: {type(exc).__name__}"

    if response.status_code in {401, 403}:
        return False, "Airforce API key was rejected. Refresh AIRFORCE_API_KEY and retry."
    if response.status_code == 429:
        return False, "Airforce health check is rate-limited. Retry in about a minute."
    if response.status_code >= 500:
        return False, "Airforce is temporarily unavailable. Retry shortly."
    if response.status_code != 200:
        return False, f"Airforce health check returned HTTP {response.status_code}."

    try:
        result = response.json().get("result", {})
        if result.get("isError"):
            return False, "Airforce could not verify account readiness."
        account = result.get("structuredContent") or {}
        balance = float(account.get("balance_usd") or 0.0)
        plan = str(account.get("plan") or "").strip().lower()
    except (AttributeError, TypeError, ValueError):
        return False, "Airforce returned an unreadable account-health response."

    if plan == "free" and balance <= 0:
        return False, (
            "Airforce account balance is $0. Add pay-as-you-go credits before "
            "using hosted image generation."
        )

    try:
        models_response = httpx.get(
            "https://api.airforce/v1/models?channels=1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
    except httpx.HTTPError as exc:
        return False, f"Airforce model-health check failed: {type(exc).__name__}"
    if models_response.status_code == 429:
        return False, "Airforce model-health check is rate-limited. Retry shortly."
    if models_response.status_code >= 500:
        return False, "Airforce model catalogue is temporarily unavailable."
    if models_response.status_code != 200:
        return False, f"Airforce model-health check returned HTTP {models_response.status_code}."
    try:
        models = models_response.json().get("data") or []
        match = next((item for item in models if item.get("id") == model), None)
    except (AttributeError, TypeError):
        return False, "Airforce returned an unreadable model-health response."
    if match is None:
        return False, f"Airforce model {model!r} is not available to this account."
    status = str(match.get("status") or "").strip().lower()
    if status not in {"operational", "stable", "degraded"}:
        return False, f"Airforce model {model!r} is currently {status or 'unhealthy'}."
    return True, ""


def airforce_images_available() -> tuple[bool, str]:
    configured, reason = hosted_image_configured("airforce")
    if not configured:
        return False, reason
    api_key = os.environ["AIRFORCE_API_KEY"].strip()
    model = os.environ.get("AIRFORCE_MODEL", "grok-imagine-image-2.0").strip()
    return _cached_hosted_health(
        "airforce", model, api_key, lambda: _probe_airforce_image_health(api_key, model)
    )


def _probe_fal_image_health(api_key: str, model: str) -> tuple[bool, str]:
    import httpx

    try:
        response = httpx.get(
            "https://api.fal.ai/v1/models",
            headers={"Authorization": f"Key {api_key}"},
            params={"endpoint_id": model, "limit": 1},
            timeout=5,
        )
    except httpx.HTTPError as exc:
        return False, f"fal health check failed: {type(exc).__name__}"

    if response.status_code == 401:
        return False, "fal API key was rejected. Refresh FAL_KEY and retry."
    if response.status_code == 403:
        return False, "fal API key does not have API scope for model access."
    if response.status_code == 429:
        return False, "fal health check is rate-limited. Retry shortly."
    if response.status_code >= 500:
        return False, "fal is temporarily unavailable. Retry shortly."
    if response.status_code != 200:
        return False, f"fal health check returned HTTP {response.status_code}."

    try:
        models = response.json().get("models") or []
        match = next((item for item in models if item.get("endpoint_id") == model), None)
    except (AttributeError, TypeError):
        return False, "fal returned an unreadable model-health response."
    if match is None:
        return False, f"fal model {model!r} is not available to this account."
    status = str((match.get("metadata") or {}).get("status") or "").lower()
    if status and status != "active":
        return False, f"fal model {model!r} is currently {status}."
    return True, ""


def fal_images_available() -> tuple[bool, str]:
    configured, reason = hosted_image_configured("fal")
    if not configured:
        return False, reason
    api_key = os.environ["FAL_KEY"].strip()
    model = os.environ.get("FAL_MODEL", "fal-ai/flux-pulid").strip()
    return _cached_hosted_health(
        "fal", model, api_key, lambda: _probe_fal_image_health(api_key, model)
    )


OPENAI_IMAGE_MODEL = os.environ.get("KITTY_OPENAI_IMAGE_MODEL", "gpt-image-2")


def openai_images_available() -> tuple[bool, str]:
    """Whether the direct GPT-Image-2 lane is explicitly enabled and configured."""
    configured, reason = hosted_image_configured("openai")
    if not configured:
        return False, reason
    return True, ""


def _openai_image_client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"].strip())


def _openai_image_actual_cost_usd(usage: Any | None) -> float | None:
    """Price provider-reported GPT-Image-2 token usage using configurable rates.

    Defaults reflect the public GPT-Image-2 rates current on 2026-08-31.
    Environment overrides keep cost truth adjustable without a code deploy.
    """
    if usage is None:
        return None
    details = getattr(usage, "input_tokens_details", None)
    try:
        text_tokens = int(getattr(details, "text_tokens", 0) or 0)
        image_tokens = int(getattr(details, "image_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        text_rate = float(os.environ.get("KITTY_OPENAI_IMAGE_TEXT_INPUT_USD_PER_M", "5"))
        image_rate = float(os.environ.get("KITTY_OPENAI_IMAGE_INPUT_USD_PER_M", "8"))
        output_rate = float(os.environ.get("KITTY_OPENAI_IMAGE_OUTPUT_USD_PER_M", "30"))
    except (TypeError, ValueError):
        return None
    return round((text_tokens * text_rate + image_tokens * image_rate + output_tokens * output_rate) / 1_000_000, 6)


def _openai_quality(quality_tier: str | None, recipe: Any | None) -> str:
    tier = str(quality_tier or getattr(recipe, "quality_tier", "quality") or "quality").lower()
    return {"fast": "low", "quality": "medium", "maximum": "high"}.get(tier, "medium")


def _openai_image_upload(data: bytes, name_hint: str) -> tuple[str, bytes, str]:
    """Build an OpenAI upload tuple from actual image bytes, never a guessed MIME."""
    import io

    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = str(image.format or "").upper()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageDispatchNotSubmittedError(
            "OpenAI reference image could not be decoded before submission"
        ) from exc
    formats = {
        "PNG": (".png", "image/png"),
        "JPEG": (".jpg", "image/jpeg"),
        "WEBP": (".webp", "image/webp"),
    }
    resolved = formats.get(fmt)
    if resolved is None:
        raise ImageDispatchNotSubmittedError(
            f"OpenAI reference image format {fmt or 'unknown'!r} is unsupported; use PNG, JPEG, or WebP"
        )
    extension, media_type = resolved
    stem = Path(name_hint).stem or "reference"
    return f"{stem}{extension}", data, media_type


async def _run_openai(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
    source_image: bytes | None = None,
    character_ref_path: str | None = None,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
    session_id: str | None = None,
    quality_tier: str | None = None,
) -> JobResult:
    """Direct OpenAI Images lane using GPT-Image-2 for generation and edits."""
    import base64

    from openai import APIConnectionError, APITimeoutError

    enabled, reason = openai_images_available()
    if not enabled:
        raise ImageDispatchNotSubmittedError(reason)

    reference_images: list[Any] = []
    if source_image is not None:
        reference_images.append(_openai_image_upload(source_image, "edit-source"))
    if character_ref_path:
        ref_path = Path(character_ref_path)
        if not ref_path.is_file():
            raise ImageDispatchNotSubmittedError(
                f"OpenAI character reference is missing from disk: {ref_path}"
            )
        reference_images.append(_openai_image_upload(ref_path.read_bytes(), ref_path.name))

    operation = "img2img" if source_image is not None else ("variation" if parent_id else "txt2img")
    job = image_jobs.create_job(
        provider="openai", operation=operation, prompt=prompt, parent_id=parent_id,
        model_id=OPENAI_IMAGE_MODEL,
        workflow_template_id=recipe.workflow_template_id if recipe else None,
        plan_id=plan_id, intent_json=intent_json,
    )
    try:
        _attach_job_to_session_before_dispatch(job.job_id, session_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        client = _openai_image_client()
        request = {
            "model": OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "quality": _openai_quality(quality_tier, recipe),
            "size": "1024x1024",
            "response_format": "b64_json",
            "output_format": "png",
        }
        try:
            if reference_images:
                response = await client.images.edit(
                    **request,
                    image=reference_images if len(reference_images) > 1 else reference_images[0],
                    input_fidelity="high",
                )
            else:
                response = await client.images.generate(**request)
        except (APIConnectionError, APITimeoutError) as exc:
            message = f"OpenAI image provider outcome unknown after transport error: {exc}"
            _mark_unknown(job.job_id, message)
            raise ImageProviderOutcomeUnknownError(message) from exc
        image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        data_items = getattr(response, "data", None) or []
        encoded = getattr(data_items[0], "b64_json", None) if data_items else None
        if not encoded:
            raise ImageRunnerError("OpenAI returned no image bytes")
        data = base64.b64decode(encoded)
        path = _persist_artifact(job.job_id, f"{job.job_id}.png", data)
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
        actual_cost = _openai_image_actual_cost_usd(getattr(response, "usage", None))
    except ImageProviderOutcomeUnknownError:
        raise
    except Exception as exc:
        _mark_failed(job.job_id, f"{type(exc).__name__}: {exc}"[:500])
        raise

    return JobResult(
        job_id=job.job_id, filename=str(path), engine="openai",
        recipe=recipe.recipe_id if recipe else None,
        routing_reason="GPT-Image-2 high-fidelity edit" if reference_images else "GPT-Image-2 generation",
        cost_usd=actual_cost,
        cost_source="provider_usage" if actual_cost is not None else None,
    )


def openrouter_images_available() -> tuple[bool, str]:
    """Whether the hosted lane will run, and why not when it will not."""
    if not paid_images_enabled():
        return False, (
            "Paid image generation is off. OpenRouter image generation is billed usage. "
            "Set KITTY_IMAGE_PAID_ENABLED=1 in .env and restart Kitty to turn it on."
        )
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        return False, "OPENROUTER_API_KEY is not set"
    return True, ""


async def _run_openrouter(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
    source_image: bytes | None = None,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
) -> JobResult:
    """Hosted lane. Same job lifecycle as the local engines — one queue, one
    history, one gallery, per the image-studio architecture."""
    import base64

    import httpx

    enabled, reason = openrouter_images_available()
    if not enabled:
        raise ImageDispatchNotSubmittedError(reason)

    content: Any = prompt
    if source_image is not None:
        # The same model edits an uploaded image; identity survives far better
        # than describing the photo and generating from scratch.
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,"
                    + base64.b64encode(source_image).decode()
                },
            },
        ]

    job = image_jobs.create_job(
        provider="openrouter",
        operation="img2img" if source_image is not None else (
            "variation" if parent_id else "txt2img"
        ),
        prompt=prompt,
        parent_id=parent_id,
        model_id=OPENROUTER_IMAGE_MODEL,
        workflow_template_id=recipe.workflow_template_id if recipe else None,
        plan_id=plan_id,
        intent_json=intent_json,
    )

    try:
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "HTTP-Referer": "https://github.com/jacobbrizinski/kitty",
                    "X-Title": "Kitty Image Studio",
                },
                json={
                    "model": OPENROUTER_IMAGE_MODEL,
                    "messages": [{"role": "user", "content": content}],
                    "modalities": ["image", "text"],
                    "usage": {"include": True},
                },
            )
        if response.status_code != 200:
            raise ImageRunnerError(
                f"OpenRouter returned HTTP {response.status_code}: {response.text[:300]}"
            )
        payload = response.json()
        usage = payload.get("usage") or {}
        raw_cost = usage.get("cost") if isinstance(usage, dict) else None
        cost_usd = (
            float(raw_cost)
            if isinstance(raw_cost, (int, float)) and raw_cost >= 0
            else None
        )
        message = payload["choices"][0]["message"]
        images = message.get("images") or []
        if not images:
            # A text-only reply is usually a refusal; relay it rather than
            # reporting a generic failure.
            raise ImageRunnerError(
                "the model returned no image: "
                f"{str(message.get('content'))[:300] or 'no explanation given'}"
            )
        data_url = images[0]["image_url"]["url"]
        data = base64.b64decode(data_url.split(",", 1)[1])
        path = _persist_artifact(job.job_id, f"{job.job_id}.png", data)
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine="openrouter",
        recipe=recipe.recipe_id if recipe else None,
        cost_usd=cost_usd,
        cost_source="provider_reported" if cost_usd is not None else None,
    )


#: Black Forest Labs. flux-dev generates, flux-kontext-pro edits an existing
#: image. Roughly a third the price of the Gemini lane and materially better at
#: photoreal, which is why it is the hosted default.
FLUX_API = "https://api.bfl.ai/v1"
FLUX_GENERATE_MODEL = os.environ.get("KITTY_FLUX_MODEL", "flux-dev")
FLUX_EDIT_MODEL = os.environ.get("KITTY_FLUX_EDIT_MODEL", "flux-kontext-pro")


def flux_images_available() -> tuple[bool, str]:
    """Whether the Flux lane will run, and why not when it will not."""
    if not paid_images_enabled():
        return False, (
            "Paid image generation is off. Flux image generation is billed per request. "
            "Set KITTY_IMAGE_PAID_ENABLED=1 in .env and restart Kitty to turn it on."
        )
    if not os.environ.get("BFL_API_KEY", "").strip():
        return False, "BFL_API_KEY is not set"
    return True, ""


def flux2_images_available() -> tuple[bool, str]:
    """Whether the hosted FLUX.2 (BFL Direct) lane will run, and why not."""
    if not paid_images_enabled():
        return False, (
            "Paid image generation is off. Hosted FLUX.2 generation is billed per request. "
            "Set KITTY_IMAGE_PAID_ENABLED=1 in .env and restart Kitty to turn it on."
        )
    if not os.environ.get("BFL_API_KEY", "").strip():
        return False, "BFL_API_KEY is not set to reach BFL Direct"
    return True, ""


async def _run_flux(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
    source_image: bytes | None = None,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
    session_id: str | None = None,
    reserved_cost_usd: float | None = None,
) -> JobResult:
    """Black Forest Labs lane, on the shared job lifecycle.

    BFL is submit-then-poll rather than a single call, and a moderated request
    comes back as a status rather than an error — both are surfaced verbatim so
    a refusal never reads as a crash.
    """
    import asyncio as _asyncio
    import base64

    import httpx

    enabled, reason = flux_images_available()
    if not enabled:
        raise ImageDispatchNotSubmittedError(reason)

    model = FLUX_EDIT_MODEL if source_image is not None else FLUX_GENERATE_MODEL
    payload: dict[str, Any] = {"prompt": prompt}
    if source_image is not None:
        payload["input_image"] = base64.b64encode(source_image).decode()
    else:
        payload["width"] = 1024
        payload["height"] = 1024

    job = image_jobs.create_job(
        provider="flux",
        operation="img2img"
        if source_image is not None
        else ("variation" if parent_id else "txt2img"),
        prompt=prompt,
        parent_id=parent_id,
        model_id=model,
        workflow_template_id=recipe.workflow_template_id if recipe else None,
        plan_id=plan_id,
        intent_json=intent_json,
    )

    try:
        _attach_job_to_session_before_dispatch(job.job_id, session_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        headers = {"x-key": os.environ["BFL_API_KEY"], "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                submit = await client.post(
                    f"{FLUX_API}/{model}", headers=headers, json=payload
                )
            except httpx.HTTPError as exc:
                message = f"Flux provider outcome unknown after submit transport error: {exc}"
                _mark_unknown(job.job_id, message)
                raise ImageProviderOutcomeUnknownError(message) from exc
            if submit.status_code != 200:
                raise ImageRunnerError(
                    f"Flux returned HTTP {submit.status_code}: {submit.text[:300]}"
                )
            submit_payload = submit.json()
            try:
                polling_url = _persist_bfl_receipt(
                    job.job_id,
                    submit_payload,
                    project_id=project_id,
                    session_id=session_id,
                    reserved_cost_usd=reserved_cost_usd,
                )
            except ImageProviderOutcomeUnknownError as exc:
                _mark_unknown(job.job_id, str(exc))
                raise
            raw_cost_credits = submit_payload.get("cost")
            cost_usd = (
                float(raw_cost_credits) * 0.01
                if isinstance(raw_cost_credits, (int, float)) and raw_cost_credits >= 0
                else None
            )

            image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
            try:
                for _ in range(150):
                    poll = await client.get(
                        polling_url, headers={"x-key": headers["x-key"]}
                    )
                    state = poll.json()
                    status = state.get("status")
                    if status not in {"Pending", "Queued", "Processing"}:
                        break
                    await _asyncio.sleep(2)
                else:
                    message = "Flux provider outcome unknown after polling timeout"
                    _mark_unknown(job.job_id, message)
                    raise ImageProviderOutcomeUnknownError(message)
            except httpx.HTTPError as exc:
                message = f"Flux provider outcome unknown after polling error: {exc}"
                _mark_unknown(job.job_id, message)
                raise ImageProviderOutcomeUnknownError(message) from exc

        if status != "Ready":
            # "Request Moderated" and "Content Moderated" arrive here. Say which.
            raise ImageRunnerError(f"Flux did not produce an image: {status}")
        sample = (state.get("result") or {}).get("sample")
        if not sample:
            raise ImageRunnerError("Flux reported Ready but returned no image")

        async with httpx.AsyncClient(timeout=180) as client:
            download = await client.get(sample)
            download.raise_for_status()
            data = download.content

        path = _persist_artifact(job.job_id, f"{job.job_id}.png", data)
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine="flux",
        recipe=recipe.recipe_id if recipe else None,
        cost_usd=cost_usd,
        cost_source="provider_reported" if cost_usd is not None else None,
    )


async def _run_flux2(
    prompt: str,
    *,
    recipe: Any | None = None,
    parent_id: str | None = None,
    target: Any | None = None,
    compiled: Any | None = None,
    reference_bytes: tuple[bytes, ...] = (),
    negative_prompt: str | None = None,
    project_id: int | None = None,
    plan_id: str | None = None,
    intent_json: str | None = None,
    session_id: str | None = None,
    reserved_cost_usd: float | None = None,
) -> JobResult:
    """Hosted FLUX.2 (BFL Direct) lane on the shared job lifecycle.

    This replaced the FLUX.1-era assumptions of ``_run_flux`` for the modern
    FLUX.2 family: a single semantic compiler output (``compiled``) targeted at
    exactly one Flux2HostedTarget drives the exact model endpoint, the estimate
    contract, and the reference serialization. IL-02 policy is enforced at the
    ``run()`` boundary before this lane is reachable, so private_adult work can
    never reach BFL Direct — even in a retry or reroute — and this lane never
    silently falls back to another hosted engine.
    """
    import asyncio as _asyncio

    import httpx

    from gateway import flux2_transport

    enabled, reason = flux2_images_available()
    if not enabled:
        raise ImageDispatchNotSubmittedError(reason)

    if target is None or compiled is None:
        raise ImageDispatchNotSubmittedError(
            "engine 'flux2' requires an explicit flux2_target and compiled request"
        )
    compiled_request = compiled
    operation = compiled_request.operation
    payload = flux2_transport.serialize_payload(
        target, compiled_request, list(reference_bytes), seed=compiled_request.seed
    )

    job = image_jobs.create_job(
        provider="flux2",
        operation=operation,
        prompt=compiled_request.prompt,
        parent_id=parent_id,
        model_id=target.model_id,
        seed=compiled_request.seed,
        width=compiled_request.width,
        height=compiled_request.height,
        workflow_template_id=recipe.workflow_template_id if recipe else None,
        compiler_version=compiled_request.compiler_id,
        compiler_params_json=compiled_request.to_json(),
        plan_id=plan_id,
        intent_json=intent_json,
    )

    try:
        _attach_job_to_session_before_dispatch(job.job_id, session_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        headers = flux2_transport.submit_headers()
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                submit = await client.post(
                    flux2_transport.endpoint_for(target), headers=headers, json=payload
                )
            except httpx.HTTPError as exc:
                message = (
                    "BFL Direct provider outcome unknown after submit transport error: "
                    f"{exc}"
                )
                _mark_unknown(job.job_id, message)
                raise ImageProviderOutcomeUnknownError(message) from exc
            if submit.status_code != 200:
                raise ImageRunnerError(
                    f"BFL Direct returned HTTP {submit.status_code}: {submit.text[:300]}"
                )
            submit_payload = submit.json()
            try:
                polling_url = _persist_bfl_receipt(
                    job.job_id,
                    submit_payload,
                    project_id=project_id,
                    session_id=session_id,
                    reserved_cost_usd=reserved_cost_usd,
                )
            except ImageProviderOutcomeUnknownError as exc:
                _mark_unknown(job.job_id, str(exc))
                raise
            cost_usd = flux2_transport.parse_cost_usd(submit_payload)

            image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
            try:
                for _ in range(150):
                    poll = await client.get(
                        polling_url, headers={"x-key": headers["x-key"]}
                    )
                    state = poll.json()
                    status = state.get("status", "")
                    if not flux2_transport.is_running_status(status):
                        break
                    await _asyncio.sleep(2)
                else:
                    message = "BFL Direct provider outcome unknown after polling timeout"
                    _mark_unknown(job.job_id, message)
                    raise ImageProviderOutcomeUnknownError(message)
            except httpx.HTTPError as exc:
                message = f"BFL Direct provider outcome unknown after polling error: {exc}"
                _mark_unknown(job.job_id, message)
                raise ImageProviderOutcomeUnknownError(message) from exc

        if status != "Ready":
            # "Request Moderated" and "Content Moderated" arrive here. Say which.
            raise ImageRunnerError(f"BFL Direct did not produce an image: {status}")
        result = state.get("result") or {}
        sample = flux2_transport.sample_url_from_result(result)
        if not sample:
            raise ImageRunnerError("BFL Direct reported Ready but returned no image")
        seed = flux2_transport.seed_from_result(result)

        if seed is not None and compiled_request.seed is None:
            current = image_jobs.get_job(job.job_id)
            diagnostics = json.loads(
                current.provider_diagnostics_json or "{}"
            ) if current is not None else {}
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            diagnostics["seed"] = seed
            image_jobs.update_job(
                job.job_id,
                provider_diagnostics_json=json.dumps(diagnostics, sort_keys=True),
            )

        async with httpx.AsyncClient(timeout=180) as client:
            download = await client.get(sample)
            download.raise_for_status()
            data = download.content

        path = _persist_artifact(job.job_id, f"{job.job_id}.png", data)
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id, project_id=project_id)
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine="flux2",
        recipe=recipe.recipe_id if recipe else None,
        cost_usd=cost_usd,
        cost_source="provider_reported" if cost_usd is not None else None,
    )
