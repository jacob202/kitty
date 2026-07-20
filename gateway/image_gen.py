"""ComfyUI image generation — calls the ComfyUI REST API (local or Colab tunnel)."""
import asyncio
import os
import time
from typing import Optional

import httpx

from gateway.image_jobs import ImageJobStore

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")

SD15_CKPT     = "homofidelis_v50.safetensors"
BEAR_LORA     = "Muscle_Bear_Baker_v2_for_transfer.safetensors"
EXPLICIT_LORA = "erect_penis_epoch_80.safetensors"
SDXL_PHOTONIC = "photonicFusionSDXL_final.safetensors"

EXPLICIT_KW = {"explicit", "erect", "hard cock", "erection", "boner", "cock", "nude explicit"}
SDXL_KW     = {"realistic", "sdxl", "photo", "photorealistic", "high res", "high quality", "photonic"}

_history: list[dict] = []
MAX_HISTORY = 20

_job_store = ImageJobStore()


def get_history() -> list[dict]:
    return list(reversed(_history))


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


async def _poll(client: httpx.AsyncClient, prompt_id: str, timeout: int = 360) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(4)
        r = await client.get(f"{COMFY_URL}/history/{prompt_id}")
        hist = r.json()
        if prompt_id not in hist:
            continue
        outputs = hist[prompt_id].get("outputs", {})
        for out in outputs.values():
            for img in out.get("images", []):
                return img["filename"]
    return None


async def is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{COMFY_URL}/system_stats")
            return r.status_code == 200
    except Exception:
        return False


async def generate(prompt: str) -> dict:
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
        model=model,
        provider_params={"lora_strength": p["lstr"], "explicit": p["explicit"]},
        workflow_template=template,
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
        _job_store.fail_job(job_id, error_type="submit_error", error_message=str(exc)[:500])
        raise

    if not filename:
        _job_store.fail_job(job_id, error_type="timeout", error_message="Image generation timed out (6 min)")
        raise TimeoutError("Image generation timed out (6 min)")

    _job_store.complete_job(job_id, output_path=filename)

    entry = {"prompt_id": prompt_id, "filename": filename, "prompt": prompt,
             "created_at": time.time(), "job_id": job_id}
    _history.append(entry)
    if len(_history) > MAX_HISTORY:
        _history.pop(0)

    return {"prompt_id": prompt_id, "filename": filename, "job_id": job_id}
