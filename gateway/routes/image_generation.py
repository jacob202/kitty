"""Image generation routes.

Split from the former routes/extended.py on 2026-09-16 so each route module
owns one domain (architecture claim: "Routes should remain thin").
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["images"])


# --- Image generation ---


class ImageGenRequest(BaseModel):
    prompt: str
    engine: str = "comfyui"
    parent_id: Optional[str] = None


COMFYUI_OFFLINE_REASON = (
    "ComfyUI is not running on this Mac. Start ComfyUI, then check again."
)
DRAWTHINGS_OFFLINE_REASON = (
    "Draw Things is not answering. Open the Draw Things app, turn on its API "
    "server, then check again."
)
KITTY_WORKER_UNCONFIGURED_REASON = (
    "Kitty image worker is not configured. Set KITTY_WORKER_URL and "
    "KITTY_WORKER_BEARER_TOKEN, then restart Kitty."
)
KITTY_WORKER_WORKFLOW_REASON = (
    "Kitty image worker edit workflow is unavailable. Install image_to_image_v1 "
    "before using the private edit lane."
)
KITTY_WORKER_OFFLINE_REASON = (
    "Kitty image worker is configured but not ready. Check the worker health "
    "endpoint and image_to_image_v1 bundle."
)


async def _kitty_worker_runtime_status() -> tuple[bool, str | None]:
    """Probe the authenticated edit worker without exposing endpoint/token details."""
    import httpx

    from gateway.image_agent import edit_workflow_available
    from gateway.runpod_control import RunPodConfigurationError
    from gateway.runpod_worker import (
        RunPodWorkerError,
        client_from_env,
        worker_is_configured,
    )

    if not worker_is_configured():
        return False, KITTY_WORKER_UNCONFIGURED_REASON
    if not edit_workflow_available():
        return False, KITTY_WORKER_WORKFLOW_REASON

    client = None
    try:
        client = client_from_env(timeout_seconds=3.0)
        await client.assert_ready()
    except (RunPodWorkerError, RunPodConfigurationError, httpx.HTTPError):
        return False, KITTY_WORKER_OFFLINE_REASON
    finally:
        if client is not None:
            await client.aclose()
    return True, None


@router.get("/image/status")
async def image_status():
    import asyncio

    from gateway.image_gen import is_available

    comfy_available = await is_available()

    # Draw Things is an optional local engine.  Its health probe is kept on
    # the adapter so this route reports the transport Kitty actually uses.
    from mcp.imagen.engines import get

    drawthings = get("drawthings")
    probe = getattr(getattr(drawthings, "_adapter", None), "is_available", None)
    if probe is None:
        raise RuntimeError("drawthings engine adapter does not expose is_available()")
    drawthings_available = bool(await asyncio.to_thread(probe))

    from gateway.image_runner import (
        airforce_images_available,
        fal_images_available,
        flux2_images_available,
        flux_images_available,
        openai_images_available,
        openrouter_images_available,
    )

    airforce_available, airforce_reason = airforce_images_available()
    flux_available, flux_reason = flux_images_available()
    flux2_available, flux2_reason = flux2_images_available()
    fal_available, fal_reason = fal_images_available()
    hosted_available, hosted_reason = openrouter_images_available()
    openai_available, openai_reason = openai_images_available()
    kitty_worker_available, kitty_worker_reason = await _kitty_worker_runtime_status()
    engines = [
        {
            "name": "comfyui",
            "label": "ComfyUI",
            "available": comfy_available,
            "unavailable_reason": None if comfy_available else COMFYUI_OFFLINE_REASON,
        },
        {
            "name": "drawthings",
            "label": "Draw Things",
            "available": drawthings_available,
            "unavailable_reason": None if drawthings_available else DRAWTHINGS_OFFLINE_REASON,
            "supports_img2img": True,
        },
        {
            "name": "kitty_worker",
            "label": "Kitty Image Worker",
            "available": kitty_worker_available,
            "unavailable_reason": kitty_worker_reason,
            "supports_img2img": True,
            "edit_only": True,
        },
        {
            "name": "airforce",
            "label": "Grok Imagine 2.0 via Airforce",
            "available": airforce_available,
            "unavailable_reason": airforce_reason or None,
            "cost_per_image_usd": 0.01,
        },
        {
            "name": "flux",
            "label": "Flux (Black Forest Labs)",
            "available": flux_available,
            "unavailable_reason": flux_reason or None,
            "cost_per_image_usd": 0.025,
        },
        {
            "name": "flux2",
            "label": "FLUX.2 (Klein 4B / Pro)",
            "available": flux2_available,
            "unavailable_reason": flux2_reason or None,
            "draft_cost_1mp_usd": 0.014,
            "final_cost_1mp_usd": 0.03,
            "supports_img2img": True,
        },
        {
            "name": "fal",
            "label": "FLUX PuLID via fal",
            "available": fal_available,
            "unavailable_reason": fal_reason or None,
            # fal bills PuLID at $0.0333/output MP, rounding up. Kitty's
            # default square_hd output is 1024x1024 (>1 MP), so its provider
            # price is two billable MP = $0.0666 before the $0.07 budget guard.
            "cost_per_image_usd": 0.0666,
            "cost_per_megapixel_usd": 0.0333,
        },
        {
            "name": "openrouter",
            "label": "Gemini via OpenRouter",
            "available": hosted_available,
            "unavailable_reason": hosted_reason or None,
            "cost_per_image_usd": 0.067,
        },
        {
            "name": "openai",
            "label": "GPT-Image-2 via OpenAI",
            "available": openai_available,
            "unavailable_reason": openai_reason or None,
            "cost_per_image_usd": 0.25,
            "cost_basis": "conservative high-quality reservation ceiling; actual token usage reconciles after success",
        },
    ]
    available = (
        comfy_available
        or drawthings_available
        or airforce_available
        or flux_available
        or flux2_available
        or fal_available
        or hosted_available
        or openai_available
    )
    edit_available = (
        drawthings_available
        or kitty_worker_available
        or flux_available
        or flux2_available
        or hosted_available
        or openai_available
    )
    # Local first when it is up (free), then the cheapest hosted lane.
    if comfy_available:
        backend = "comfyui"
    elif drawthings_available:
        backend = "drawthings"
    elif airforce_available:
        backend = "airforce"
    elif flux_available:
        backend = "flux"
    elif flux2_available:
        backend = "flux2"
    elif fal_available:
        backend = "fal"
    elif hosted_available:
        backend = "openrouter"
    elif openai_available:
        backend = "openai"
    else:
        backend = "comfyui"
    return {
        "available": available,
        "edit_available": edit_available,
        "backend": backend,
        "engines": engines,
    }


@router.post("/image/generate")
async def image_generate(req: ImageGenRequest):
    from gateway.image_runner import ENGINES, ImageRunnerError, run

    engine = req.engine.strip().lower()
    if engine not in ENGINES:
        raise HTTPException(
            status_code=422, detail=f"engine must be one of {', '.join(sorted(ENGINES))}"
        )
    if engine not in {"comfyui", "drawthings"}:
        raise HTTPException(
            status_code=409,
            detail=(
                "Hosted image generation requires the Studio session/batch path "
                "so spend authorization, reservation, and recovery stay durable"
            ),
        )

    try:
        result = await run(engine, req.prompt, parent_id=req.parent_id)
        return {
            "prompt_id": result.prompt_id,
            "filename": result.filename,
            "job_id": result.job_id,
            "engine": result.engine,
        }
    except ImageRunnerError as e:
        status = 503 if "not running" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image/{job_id}/cancel")
async def image_cancel(job_id: str):
    """Cancel a ComfyUI image job after verifying prompt ownership."""
    import httpx

    from gateway.image_gen import (
        CancellationConflictError,
        CancellationUnsupportedError,
        cancel,
    )
    from gateway.image_jobs import IllegalTransitionError, JobNotFoundError

    try:
        return await cancel(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CancellationUnsupportedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CancellationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"ComfyUI cancellation failed: {exc}"
        ) from exc


@router.post("/image/jobs/{job_id}/retry")
async def image_job_retry(job_id: str):
    """Retry a terminal image job as a new lineaged child with the same intent."""
    from gateway.image_jobs import ImageJobError, JobNotFoundError, retry_job

    try:
        job = retry_job(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImageJobError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"job": job.to_dict(), "retried_from": job_id}


@router.get("/image/view/{filename:path}")
async def image_view(filename: str):
    """Proxy an output image from ComfyUI (works with both local and Colab tunnel URLs)."""
    import httpx
    from fastapi.responses import FileResponse, Response

    from mcp.imagen.config import settings

    # Draw Things and the converged ComfyUI path persist artifacts in Kitty's
    # local image store.  Serve only files below that configured directory;
    # all other names retain the legacy ComfyUI proxy behavior.
    candidate = Path(filename)
    if not candidate.is_absolute():
        candidate = settings.output_dir / candidate
    try:
        candidate = candidate.resolve()
        output_root = settings.output_dir.resolve()
        candidate.relative_to(output_root)
    except ValueError:
        candidate = Path()
    if candidate.is_file():
        return FileResponse(candidate)

    from gateway.image_gen import COMFY_URL

    url = f"{COMFY_URL}/view?filename={filename}&subfolder=&type=output"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="Image not found in ComfyUI")
        ct = r.headers.get("content-type", "image/png")
        return Response(content=r.content, media_type=ct)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach ComfyUI: {e}")


@router.get("/image/history")
async def image_history(limit: int = 20):
    from gateway.image_gen import get_history

    return {"images": get_history(limit=limit)}
