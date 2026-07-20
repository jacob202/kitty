"""ComfyUI image generation — calls the ComfyUI REST API (local or Colab tunnel)."""
import asyncio
import hashlib
import json
import os
import time
from typing import Optional

import httpx

from gateway.image_jobs import (
    IllegalTransitionError,
    ImageJobStatus,
    JobNotFoundError,
    create_job,
    get_job,
    list_recent,
    transition,
    update_job,
)
from mcp.imagen.io import save_image

# Set COMFY_URL to the cloudflared tunnel URL when running on Colab, e.g.:
#   COMFY_URL=https://abc-xyz.trycloudflare.com
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")

SD15_CKPT     = "homofidelis_v50.safetensors"
BEAR_LORA     = "Muscle_Bear_Baker_v2_for_transfer.safetensors"
EXPLICIT_LORA = "erect_penis_epoch_80.safetensors"
SDXL_PHOTONIC = "photonicFusionSDXL_final.safetensors"

EXPLICIT_KW = {"explicit", "erect", "hard cock", "erection", "boner", "cock", "nude explicit"}
SDXL_KW     = {"realistic", "sdxl", "photo", "photorealistic", "high res", "high quality", "photonic"}


class ImageGenerationCancelled(RuntimeError):
    """The caller canceled this job while ComfyUI was generating it."""


def get_history(limit: int = 20) -> list[dict]:
    """Gallery history from the durable job store (IMG-01) — survives restarts.

    Only succeeded jobs with an artifact are gallery entries; the response
    keeps the legacy {prompt_id, filename, prompt, created_at} shape the UI
    polls, plus the durable job_id.
    """
    entries: list[dict] = []
    for job in list_recent(limit=max(limit, 1)):
        if job.status is not ImageJobStatus.SUCCEEDED or not job.output_path:
            continue
        entries.append(
            {
                "prompt_id": job.provider_job_id or job.job_id,
                "job_id": job.job_id,
                "filename": job.output_path,
                "prompt": job.prompt or "",
                "created_at": job.created_at,
            }
        )
    return entries


def _parse(prompt: str) -> dict:
    low = prompt.lower()
    sdxl     = any(k in low for k in SDXL_KW)
    photonic = "photonic" in low
    explicit = any(k in low for k in EXPLICIT_KW)

    if sdxl:
        w, h, steps, cfg = 1024, 1024, 6, 1.5
        if "portrait" in low:
            w, h = 832, 1216
        if "landscape" in low:
            w, h = 1216, 832
        if "detailed" in low:
            steps, cfg = 10, 2.0
    else:
        w, h, steps, cfg = 512, 512, 25, 7.0
        if "portrait" in low:
            w, h = 512, 768
        if "landscape" in low:
            w, h = 768, 512
        if "fast" in low:
            steps = 15
        if "detailed" in low:
            steps = 35

    lstr = 1.0 if "more bear" in low else 0.5 if "less bear" in low else 0.8
    estr = 0.75

    neg = "worst quality, low quality, bad anatomy, deformed, ugly, watermark, text, blurry"
    if sdxl:
        neg += ", illustration, painting, drawing, cartoon"

    return dict(sdxl=sdxl, photonic=photonic, explicit=explicit,
                w=w, h=h, steps=steps, cfg=cfg, lstr=lstr, estr=estr,
                negative=neg)


def _seed() -> int:
    return int.from_bytes(os.urandom(8), "little") & 0xFFFFFFFFFFFFFFFF


def _wf_sd15(prompt: str, neg: str, w: int, h: int, steps: int, cfg: float,
             lstr: float, explicit: bool, estr: float) -> dict:
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SD15_CKPT}},
        "4": {"class_type": "LoraLoader",
              "inputs": {"model": ["1", 0], "clip": ["1", 1],
                         "lora_name": BEAR_LORA, "strength_model": lstr, "strength_clip": lstr}},
    }
    model_node, clip_node = "4", "4"
    if explicit:
        wf["9"] = {"class_type": "LoraLoader",
                   "inputs": {"model": [model_node, 0], "clip": [clip_node, 1],
                              "lora_name": EXPLICIT_LORA, "strength_model": estr, "strength_clip": 0.0}}
        model_node = "9"
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": [clip_node, 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": neg,    "clip": [clip_node, 1]}}
    wf["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    wf["6"] = {"class_type": "KSampler",
               "inputs": {"seed": _seed(), "steps": steps, "cfg": cfg,
                          "sampler_name": "euler_ancestral", "scheduler": "karras",
                          "denoise": 1.0, "model": [model_node, 0],
                          "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0]}}
    wf["7"] = {"class_type": "VAEDecode",  "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
    wf["8"] = {"class_type": "SaveImage",  "inputs": {"filename_prefix": "Kitty", "images": ["7", 0]}}
    return wf


def _wf_sdxl(prompt: str, neg: str, w: int, h: int, steps: int, cfg: float, ckpt: str) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg,    "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": _seed(), "steps": steps, "cfg": cfg,
                         "sampler_name": "euler", "scheduler": "sgm_uniform",
                         "denoise": 1.0, "model": ["1", 0],
                         "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "KittyXL", "images": ["6", 0]}},
    }


async def _poll(
    client: httpx.AsyncClient,
    prompt_id: str,
    timeout: int = 360,
    job_id: str | None = None,
) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(4)
        # A cancel (IMG-02) marks the job canceled out-of-band; stop polling
        # instead of burning the remaining timeout.
        if job_id is not None:
            job = get_job(job_id)
            if job is not None and job.status is ImageJobStatus.CANCELED:
                return None
        r = await client.get(f"{COMFY_URL}/history/{prompt_id}")
        hist = r.json()
        if prompt_id not in hist:
            continue
        prompt_history = hist[prompt_id]
        status = prompt_history.get("status", {})
        status_str = status.get("status_str") if isinstance(status, dict) else None
        if status_str in {"error", "failed"}:
            detail = prompt_history.get("execution_error")
            if not detail and isinstance(status, dict):
                detail = status.get("messages")
            raise RuntimeError(
                f"ComfyUI generation failed for prompt {prompt_id}: "
                f"{detail or status_str}"
            )
        outputs = prompt_history.get("outputs", {})
        for out in outputs.values():
            for img in out.get("images", []):
                return img["filename"]
    return None


def _mark_failed(job_id: str, message: str) -> None:
    """Record a failure unless the job already reached a terminal state.

    A cancel racing the generate() coroutine wins: the canceled state stays,
    and the failure that the interrupt provoked is not an error to report.
    """
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found while recording failure")
    if job.status is ImageJobStatus.CANCELED:
        return
    update_job(job_id, normalized_error=message)
    transition(job_id, ImageJobStatus.FAILED)


async def cancel(job_id: str) -> dict:
    """Cancel an in-flight generation: interrupt ComfyUI, mark job canceled.

    Raises JobNotFoundError for unknown ids and IllegalTransitionError when
    the job is already terminal. ComfyUI's /interrupt stops the currently
    executing prompt.
    """
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if job.status.is_terminal():
        raise IllegalTransitionError(
            f"job {job_id} is already {job.status.value}; nothing to cancel"
        )
    # /interrupt only stops the prompt ComfyUI is executing right now; a job
    # queued behind others needs DELETE /queue with the prompt_id. That is a
    # separate multi-job queueing capability, not a silent no-op here.
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{COMFY_URL}/interrupt")
        r.raise_for_status()
    updated = transition(job_id, ImageJobStatus.CANCELED)
    return {"canceled": True, "job_id": job_id, "status": updated.status.value}


async def is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{COMFY_URL}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def generate(prompt: str, parent_id: str | None = None) -> dict:
    """Submit prompt to ComfyUI, poll until done, return {prompt_id, filename, job_id}."""
    p = _parse(prompt)

    if p["sdxl"]:
        workflow = _wf_sdxl(prompt, p["negative"], p["w"], p["h"], p["steps"], p["cfg"], SDXL_PHOTONIC)
        model_id, sampler, scheduler = SDXL_PHOTONIC, "euler", "sgm_uniform"
        template = "sdxl_photonic"
    else:
        workflow = _wf_sd15(prompt, p["negative"], p["w"], p["h"], p["steps"], p["cfg"],
                            p["lstr"], p["explicit"], p["estr"])
        model_id, sampler, scheduler = SD15_CKPT, "euler_ancestral", "karras"
        template = "sd15_basic"

    workflow_hash = hashlib.sha256(json.dumps(workflow, sort_keys=True).encode()).hexdigest()[:16]
    provider_params = {"lora_strength": p["lstr"], "explicit": p["explicit"]}

    # Record the job before submitting so it survives a crash mid-generation.
    job = create_job(
        provider="comfyui",
        operation="variation" if parent_id else "txt2img",
        prompt=prompt,
        negative_prompt=p["negative"],
        seed=None,  # seed is embedded in workflow but not surfaced back
        model_id=model_id,
        width=p["w"],
        height=p["h"],
        steps=p["steps"],
        guidance=p["cfg"],
        sampler=sampler,
        scheduler=scheduler,
        provider_params_json=json.dumps(provider_params),
        workflow_template_id=template,
        workflow_hash=workflow_hash,
        parent_id=parent_id,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
            if r.status_code != 200:
                raise RuntimeError(f"ComfyUI rejected prompt: {r.text}")
            prompt_id = r.json()["prompt_id"]
            update_job(job.job_id, provider_job_id=prompt_id)
            transition(job.job_id, ImageJobStatus.SUBMITTED)
            transition(job.job_id, ImageJobStatus.RUNNING)
            filename = await _poll(client, prompt_id, job_id=job.job_id)
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    current_job = get_job(job.job_id)
    if current_job is None:
        raise JobNotFoundError(f"job {job.job_id} disappeared during generation")
    if current_job.status is ImageJobStatus.CANCELED:
        raise ImageGenerationCancelled(f"Image generation canceled for job {job.job_id}")

    if not filename:
        update_job(job.job_id, normalized_error="Image generation timed out (6 min)")
        transition(job.job_id, ImageJobStatus.FAILED)
        raise TimeoutError("Image generation timed out (6 min)")

    # ComfyUI owns its output directory, which may be ephemeral (for example
    # a restarted Colab process). Copy the completed artifact into Kitty's
    # durable image store before marking the job succeeded.
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            view_response = await client.get(
                f"{COMFY_URL}/view",
                params={"filename": filename, "subfolder": "", "type": "output"},
            )
            view_response.raise_for_status()
            if not view_response.content:
                raise RuntimeError(
                    f"ComfyUI returned an empty image for completed prompt {prompt_id} "
                    f"(filename={filename!r})"
                )
            local_path = await asyncio.to_thread(save_image, view_response.content, prefix="comfy")
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    update_job(job.job_id, output_path=str(local_path))
    transition(job.job_id, ImageJobStatus.SUCCEEDED)

    return {"prompt_id": prompt_id, "filename": str(local_path), "job_id": job.job_id}
