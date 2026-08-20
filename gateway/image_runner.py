"""Image generation runner — deep module owning job lifecycle and engine dispatch.

Routes become thin handlers: request model → run() → status-code mapping.
The runner owns job creation, engine dispatch, lifecycle transitions, artifact
persistence, error normalization, and character-contract resolution.

Invariant: if run() returns or raises, the job is in a terminal state.
"""

from __future__ import annotations

import asyncio
import json
import os
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
    cost_usd: float | None = None


async def run(
    engine: str,
    prompt: str,
    *,
    recipe: Any | None = None,
    character_id: str | None = None,
    negative_prompt: str | None = None,
    parent_id: str | None = None,
    guidance_tags: list[str] | None = None,
    source_image: bytes | None = None,
    content_lane: str = "safe",
    consent_basis: str | None = None,
    adult_confirmed: bool = False,
    flux2_target: Any | None = None,
    compiled_request: Any | None = None,
    reference_bytes: tuple[bytes, ...] = (),
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
        )

    if engine == "openrouter":
        return await _run_openrouter(
            prompt, recipe=recipe, parent_id=parent_id, source_image=source_image,
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
        image_jobs.register_canonical_artifact(job.job_id)
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
        image_jobs.register_canonical_artifact(job.job_id)
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


#: Engines ``run`` will dispatch to. Hosted engines carry a conservative
#: contracted per-render estimate so the session budget can be reserved before
#: a provider call is allowed to spend money.
ENGINES = frozenset({"comfyui", "drawthings", "flux", "flux2", "openrouter"})
_ESTIMATED_COST_USD = {
    "comfyui": 0.0,
    "drawthings": 0.0,
    # The worker edit lane is Kitty-owned and not billed per render.
    "kitty_worker": 0.0,
    # Budget reservations are deliberately conservative ceilings, not price
    # claims. Actual provider-reported cost is reconciled after success when
    # available.
    "flux": 0.08,
    "openrouter": 0.15,
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
) -> JobResult:
    """Hosted lane. Same job lifecycle as the local engines — one queue, one
    history, one gallery, per the image-studio architecture."""
    import base64

    import httpx

    enabled, reason = openrouter_images_available()
    if not enabled:
        raise ImageRunnerError(reason)

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
        image_jobs.register_canonical_artifact(job.job_id)
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
        raise ImageRunnerError(reason)

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
    )

    try:
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        headers = {"x-key": os.environ["BFL_API_KEY"], "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=180) as client:
            submit = await client.post(f"{FLUX_API}/{model}", headers=headers, json=payload)
            if submit.status_code != 200:
                raise ImageRunnerError(
                    f"Flux returned HTTP {submit.status_code}: {submit.text[:300]}"
                )
            submit_payload = submit.json()
            polling_url = submit_payload["polling_url"]
            raw_cost_credits = submit_payload.get("cost")
            cost_usd = (
                float(raw_cost_credits) * 0.01
                if isinstance(raw_cost_credits, (int, float)) and raw_cost_credits >= 0
                else None
            )

            image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
            for _ in range(150):
                poll = await client.get(polling_url, headers={"x-key": headers["x-key"]})
                state = poll.json()
                status = state.get("status")
                if status not in {"Pending", "Queued", "Processing"}:
                    break
                await _asyncio.sleep(2)
            else:
                raise TimeoutError("Flux did not finish within 5 minutes")

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
        image_jobs.register_canonical_artifact(job.job_id)
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
        raise ImageRunnerError(reason)

    if target is None or compiled is None:
        raise ImageRunnerError(
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
    )

    try:
        image_jobs.transition(job.job_id, ImageJobStatus.SUBMITTED)
        headers = flux2_transport.submit_headers()
        async with httpx.AsyncClient(timeout=180) as client:
            submit = await client.post(
                flux2_transport.endpoint_for(target), headers=headers, json=payload
            )
            if submit.status_code != 200:
                raise ImageRunnerError(
                    f"BFL Direct returned HTTP {submit.status_code}: {submit.text[:300]}"
                )
            submit_payload = submit.json()
            polling_url = submit_payload.get("polling_url")
            if not polling_url:
                raise ImageRunnerError(
                    "BFL Direct submitted without a polling_url"
                )
            cost_usd = flux2_transport.parse_cost_usd(submit_payload)

            image_jobs.transition(job.job_id, ImageJobStatus.RUNNING)
            for _ in range(150):
                poll = await client.get(polling_url, headers={"x-key": headers["x-key"]})
                state = poll.json()
                status = state.get("status", "")
                if not flux2_transport.is_running_status(status):
                    break
                await _asyncio.sleep(2)
            else:
                raise TimeoutError("BFL Direct did not finish within 5 minutes")

        if status != "Ready":
            # "Request Moderated" and "Content Moderated" arrive here. Say which.
            raise ImageRunnerError(f"BFL Direct did not produce an image: {status}")
        result = state.get("result") or {}
        sample = flux2_transport.sample_url_from_result(result)
        if not sample:
            raise ImageRunnerError("BFL Direct reported Ready but returned no image")
        seed = flux2_transport.seed_from_result(result)

        if seed is not None and compiled_request.seed is None:
            import json as _json

            image_jobs.update_job(
                job.job_id, provider_diagnostics_json=_json.dumps({"seed": seed})
            )

        async with httpx.AsyncClient(timeout=180) as client:
            download = await client.get(sample)
            download.raise_for_status()
            data = download.content

        path = _persist_artifact(job.job_id, f"{job.job_id}.png", data)
        image_jobs.update_job(job.job_id, output_path=str(path))
        image_jobs.register_canonical_artifact(job.job_id)
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
    )
