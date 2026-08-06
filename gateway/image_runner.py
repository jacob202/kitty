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
) -> JobResult:
    """Generate an image through the specified engine.

    A character ID is not merely a request to pick the first stored photo. It
    requires a valid character contract whose identity method, reference set,
    weights, prompt fragments, and recipe can all be honored by the engine.
    """
    engine = engine.strip().lower()
    if engine not in ENGINES:
        raise ImageRunnerError(
            f"unknown engine {engine!r}; must be one of {', '.join(sorted(ENGINES))}"
        )

    if engine == "flux":
        return await _run_flux(
            prompt, recipe=recipe, parent_id=parent_id, source_image=source_image,
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
) -> JobResult:
    """Edit the anchor job's artifact, rather than rerolling from its prompt."""
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


#: Engines ``run`` will dispatch to. comfyui and drawthings are local; openrouter
#: is the hosted lane and the only one that spends money.
ENGINES = frozenset({"comfyui", "drawthings", "flux", "openrouter"})

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
            "Paid image generation is off. Every image costs about 7 cents. "
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
                },
            )
        if response.status_code != 200:
            raise ImageRunnerError(
                f"OpenRouter returned HTTP {response.status_code}: {response.text[:300]}"
            )
        payload = response.json()
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
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine="openrouter",
        recipe=recipe.recipe_id if recipe else None,
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
            "Paid image generation is off. Flux costs about 2.5 cents a picture. "
            "Set KITTY_IMAGE_PAID_ENABLED=1 in .env and restart Kitty to turn it on."
        )
    if not os.environ.get("BFL_API_KEY", "").strip():
        return False, "BFL_API_KEY is not set"
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
            polling_url = submit.json()["polling_url"]

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
        image_jobs.transition(job.job_id, ImageJobStatus.SUCCEEDED)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    return JobResult(
        job_id=job.job_id,
        filename=str(path),
        engine="flux",
        recipe=recipe.recipe_id if recipe else None,
    )
