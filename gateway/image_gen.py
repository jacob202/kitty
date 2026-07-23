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

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")

# Checkpoint names — update these to match what's in ComfyUI's models/checkpoints/.
# Legacy checkpoint names — SD15_CKPT is unused (SDXL-only generation).
# Kept for reference; _wf_sd15 was removed in the recipe-cleanup deepening.
SDXL_CKPT     = "RealCoreXL.safetensors"
SDXL_PHOTONIC = "RealCoreXL.safetensors"

# IP-Adapter models for identity-preserving generation.
# These must be present in ComfyUI's models/ipadapter/ directory.
# The currently installed model is SD1.5 FaceID — download ip-adapter-plus_sdxl_vit-h.safetensors
# for SDXL identity generation.
IPADAPTER_MODEL  = "ip-adapter-faceid_sd15.bin"
IPADAPTER_CLIP_VISION = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"

# These are the built-in node types emitted by Kitty's workflow variants.
# Checking them through /object_info turns a ComfyUI upgrade or stripped custom
# install into an honest health failure before a user submits a job.
COMFY_REQUIRED_NODES = frozenset(
    {
        "CheckpointLoaderSimple",
        "LoraLoader",
        "CLIPTextEncode",
        "EmptyLatentImage",
        "KSampler",
        "VAEDecode",
        "SaveImage",
        "LoadImage",
    }
)

# IP-Adapter requires these node types from ComfyUI_IPAdapter_plus.
# Marked as optional so basic generation works without them; identity generation
# verifies these explicitly before building the workflow.
COMFY_IDENTITY_NODES = frozenset({"IPAdapter", "IPAdapterModelLoader"})

EXPLICIT_KW = {"explicit", "erect", "hard cock", "erection", "boner", "cock", "nude explicit"}
SDXL_KW     = {"realistic", "sdxl", "photo", "photorealistic", "high res", "high quality", "photonic"}

_history: list[dict] = []
MAX_HISTORY = 20

_job_store = ImageJobStore()


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
    """Extract keyword-derived params for an SDXL workflow.

    Always returns SDXL-native defaults (1024×1024, 6 steps, cfg 1.5).
    Keyword overrides for dimensions and quality are preserved.
    """
    low = prompt.lower()
    explicit = any(k in low for k in EXPLICIT_KW)

    w, h, steps, cfg = 1024, 1024, 6, 1.5
    if "portrait" in low:
        w, h = 832, 1216
    if "landscape" in low:
        w, h = 1216, 832
    if "detailed" in low:
        steps, cfg = 10, 2.0

    neg = "worst quality, low quality, bad anatomy, deformed, ugly, watermark, text, blurry"
    neg += ", illustration, painting, drawing, cartoon"

    return dict(explicit=explicit, w=w, h=h, steps=steps, cfg=cfg,
                negative=neg)


def _seed() -> int:
    return int.from_bytes(os.urandom(8), "little") & 0xFFFFFFFFFFFFFFFF


def _wf_sd15(prompt: str, neg: str, w: int, h: int, steps: int, cfg: float,
             lstr: float, explicit: bool, estr: float, seed: int) -> dict:
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
               "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                          "sampler_name": "euler_ancestral", "scheduler": "karras",
                          "denoise": 1.0, "model": [model_node, 0],
                          "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0]}}
    wf["7"] = {"class_type": "VAEDecode",  "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
    wf["8"] = {"class_type": "SaveImage",  "inputs": {"filename_prefix": "Kitty", "images": ["7", 0]}}
    return wf


def _wf_sdxl(prompt: str, neg: str, w: int, h: int, steps: int, cfg: float, ckpt: str, seed: int) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg,    "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": "euler", "scheduler": "sgm_uniform",
                         "denoise": 1.0, "model": ["1", 0],
                         "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "KittyXL", "images": ["6", 0]}},
    }


def _wf_ipadapter_sdxl(
    prompt: str, neg: str, w: int, h: int,
    steps: int, cfg: float, ckpt: str,
    ref_image_name: str, identity_weight: float = 0.7,
) -> dict:
    """SDXL workflow with IP-Adapter FaceID identity preservation."""
    return {
        "1":  {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2":  {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3":  {"class_type": "CLIPTextEncode", "inputs": {"text": neg,    "clip": ["1", 1]}},
        "4":  {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "10": {"class_type": "LoadImage", "inputs": {"image": ref_image_name}},
        "11": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": IPADAPTER_MODEL}},
        "12": {"class_type": "IPAdapter",
               "inputs": {
                   "model": ["1", 0],
                   "ipadapter": ["11", 0],
                   "image": ["10", 0],
                   "weight": identity_weight,
                   "start_at": 0.0, "end_at": 1.0,
                   "weight_type": "standard",
               }},
        "5":  {"class_type": "KSampler",
               "inputs": {
                   "seed": _seed(), "steps": steps, "cfg": cfg,
                   "sampler_name": "euler", "scheduler": "sgm_uniform",
                   "denoise": 1.0, "model": ["12", 0],
                   "positive": ["2", 0], "negative": ["3", 0],
                   "latent_image": ["4", 0],
               }},
        "6":  {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7":  {"class_type": "SaveImage", "inputs": {"filename_prefix": "KittyIdentity", "images": ["6", 0]}},
    }


def _wf_ipadapter_identity(
    prompt: str, neg: str, w: int, h: int,
    steps: int, cfg: float, ckpt: str, ref_image_name: str,
) -> dict:
    return _wf_ipadapter_sdxl(
        prompt=prompt, neg=neg, w=w, h=h,
        steps=max(steps, 12), cfg=max(cfg, 3.5),
        ckpt=ckpt, ref_image_name=ref_image_name,
        identity_weight=0.85,
    )


async def _upload_ref_to_comfy(ref_path: str, client: httpx.AsyncClient) -> str:
    from pathlib import Path
    path = Path(ref_path)
    if not path.exists():
        raise RuntimeError(f"reference image not found: {ref_path}")
    with open(ref_path, "rb") as f:
        r = await client.post(
            f"{COMFY_URL}/upload/image",
            files={"image": (path.name, f, "image/png")},
        )
        if r.status_code != 200:
            raise RuntimeError(f"ComfyUI rejected reference upload ({r.status_code})")
    return path.name


async def is_identity_ready() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{COMFY_URL}/object_info")
            if r.status_code != 200:
                return False
            payload = r.json()
            if not isinstance(payload, dict):
                return False
            missing = sorted(COMFY_IDENTITY_NODES.difference(payload))
            if missing:
                return False
            # Also verify IPAdapterModelLoader actually finds a model
            loader_inputs = payload.get("IPAdapterModelLoader", {}).get("input", {}).get("required", {})
            model_opts = loader_inputs.get("ipadapter_file", [[]])
            if isinstance(model_opts, list) and len(model_opts) > 1:
                if not model_opts[0]:
                    return False
            return True
    except httpx.RequestError:
        return False


async def generate_with_character(
    prompt: str, *,
    character_ref_path: str,
    identity_mode: str = "balanced",
    negative_prompt: str | None = None,
    width: int = 1024, height: int = 1024,
    steps: int = 8, cfg: float = 4.5,
    seed: int | None = None,
) -> dict:
    state_seed = seed or _seed()
    neg = negative_prompt or "worst quality, low quality, bad anatomy, deformed, ugly, watermark, blurry"

    weight_map = {"identity_first": 0.85, "creative": 0.5, "balanced": 0.7}
    identity_weight = weight_map.get(identity_mode, 0.7)

    job = create_job(
        provider="comfyui", operation="txt2img",
        prompt=prompt, negative_prompt=neg, seed=state_seed,
        model_id=SDXL_PHOTONIC, width=width, height=height,
        steps=steps, guidance=cfg, sampler="euler", scheduler="sgm_uniform",
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            ref_name = await _upload_ref_to_comfy(character_ref_path, client)
            workflow = _wf_ipadapter_sdxl(
                prompt=prompt, neg=neg, w=width, h=height,
                steps=steps, cfg=cfg, ckpt=SDXL_PHOTONIC,
                ref_image_name=ref_name, identity_weight=identity_weight,
            )
            workflow_hash = hashlib.sha256(
                json.dumps(workflow, sort_keys=True).encode()
            ).hexdigest()[:16]
            update_job(job.job_id, workflow_hash=workflow_hash)

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

    if not filename:
        _mark_failed(job.job_id, "timed out (6 min)")
        raise TimeoutError("Image generation timed out")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            vr = await client.get(
                f"{COMFY_URL}/view",
                params={"filename": filename, "subfolder": "", "type": "output"},
            )
            vr.raise_for_status()
            if not vr.content:
                raise RuntimeError(f"empty image for prompt {prompt_id}")
            local_path = await asyncio.to_thread(save_image, vr.content, prefix="identity")
    except Exception as exc:
        _mark_failed(job.job_id, str(exc)[:500])
        raise

    update_job(job.job_id, output_path=str(local_path))
    transition(job.job_id, ImageJobStatus.SUCCEEDED)

    return {
        "prompt_id": prompt_id, "filename": str(local_path),
        "job_id": job.job_id, "character_weight": identity_weight,
    }


# ── polling, cancellation, and generation ────────────────────────────────────


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


class CancellationUnsupportedError(RuntimeError):
    """The job's provider does not support cancellation."""


class CancellationConflictError(RuntimeError):
    """The job cannot be canceled in its current provider-side state."""


async def cancel(job_id: str) -> dict:
    """Cancel an in-flight ComfyUI generation after verifying prompt ownership.

    Safety rules enforced:
    - Only comfyui jobs are cancellable (other providers have no implemented
      cancellation mechanism).
    - The job must have a stored provider_job_id (prompt was submitted).
    - ComfyUI's queue/running state is queried to determine whether the
      requested prompt is currently executing or queued.
    - /interrupt is sent only when the requested prompt is proven to be the
      active prompt.
    - Queued prompts are removed via the /queue DELETE API.
    - Durable status changes to canceled only after provider-side cancellation
      succeeds.
    - Terminal jobs are rejected.
    """
    job = get_job(job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if job.status.is_terminal():
        raise IllegalTransitionError(
            f"job {job_id} is already {job.status.value}; nothing to cancel"
        )
    if job.provider != "comfyui":
        raise CancellationUnsupportedError(
            f"cancellation is not supported for provider {job.provider!r}; "
            f"only comfyui jobs can be canceled"
        )
    if not job.provider_job_id:
        raise CancellationConflictError(
            f"job {job_id} has no provider_job_id; it was never submitted to ComfyUI"
        )

    prompt_id = job.provider_job_id

    async with httpx.AsyncClient(timeout=10) as client:
        queue_resp = await client.get(f"{COMFY_URL}/queue")
        queue_resp.raise_for_status()
        queue_data = queue_resp.json()

        running_ids = {
            entry[1] for entry in queue_data.get("queue_running", [])
            if isinstance(entry, list) and len(entry) > 1
        }
        pending_ids = {
            entry[1] for entry in queue_data.get("queue_pending", [])
            if isinstance(entry, list) and len(entry) > 1
        }

        if prompt_id in running_ids:
            r = await client.post(f"{COMFY_URL}/interrupt")
            r.raise_for_status()
        elif prompt_id in pending_ids:
            r = await client.post(
                f"{COMFY_URL}/queue",
                json={"delete": [prompt_id]},
            )
            r.raise_for_status()
        else:
            history_resp = await client.get(f"{COMFY_URL}/history/{prompt_id}")
            history_resp.raise_for_status()
            history = history_resp.json()
            if prompt_id in history:
                raise CancellationConflictError(
                    f"prompt {prompt_id} already completed in ComfyUI; "
                    f"cannot cancel"
                )
            raise CancellationConflictError(
                f"prompt {prompt_id} is not running, queued, or in history; "
                f"provider state cannot be determined"
            )

    updated = transition(job_id, ImageJobStatus.CANCELED)
    return {"canceled": True, "job_id": job_id, "status": updated.status.value}


async def is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            stats = await c.get(f"{COMFY_URL}/system_stats")
            if stats.status_code != 200:
                return False
            object_info = await c.get(f"{COMFY_URL}/object_info")
            if object_info.status_code != 200:
                return False
            payload = object_info.json()
            if not isinstance(payload, dict):
                raise RuntimeError(
                    f"ComfyUI /object_info returned {type(payload).__name__}, expected an object"
                )
            missing = sorted(COMFY_REQUIRED_NODES.difference(payload))
            if missing:
                return False
            return True
    except httpx.RequestError:
        return False


async def generate(prompt: str, parent_id: str | None = None) -> dict:
    """Submit prompt to ComfyUI, poll until done, return {prompt_id, filename, job_id}."""
    p = _parse(prompt)
    seed = _seed()

    if p["sdxl"]:
        workflow = _wf_sdxl(prompt, p["negative"], p["w"], p["h"], p["steps"], p["cfg"], SDXL_PHOTONIC, seed)
        model, sampler, scheduler = SDXL_PHOTONIC, "euler", "sgm_uniform"
        template = "sdxl_photonic"
    else:
        workflow = _wf_sd15(prompt, p["negative"], p["w"], p["h"], p["steps"], p["cfg"],
                            p["lstr"], p["explicit"], p["estr"], seed)
        model, sampler, scheduler = SD15_CKPT, "euler_ancestral", "karras"
        template = "sd15_basic"

    job_id = _job_store.create_job(
        engine="comfyui",
        prompt=prompt,
        negative_prompt=p["negative"],
        seed=seed,
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
            _job_store.submit_job(job_id, prompt_id)
            filename = await _poll(client, prompt_id)
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

    _job_store.complete_job(job_id, output_path=filename)

    current_job = get_job(job.job_id)
    if current_job is None:
        raise JobNotFoundError(f"job {job.job_id} disappeared before persistence")
    if current_job.status is ImageJobStatus.CANCELED:
        raise ImageGenerationCancelled(f"Image generation canceled for job {job.job_id}")

    update_job(job.job_id, output_path=str(local_path))
    transition(job.job_id, ImageJobStatus.SUCCEEDED)

    return {"prompt_id": prompt_id, "filename": str(local_path), "job_id": job.job_id}
