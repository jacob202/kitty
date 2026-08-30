"""ComfyUI engine — local SD1.5 / SDXL generation.

The only backend that allows full explicit NSFW; uses the LoRAs already
configured in the ComfyUI instance. No API cost. Requires ComfyUI running
at COMFY_URL (default http://127.0.0.1:8188).

Retry strategy differs from the cloud engines: only retry on httpx
connection/timeout errors (the prompt was accepted, polling is what's flaky),
not on 4xx (ComfyUI errors are usually prompt issues, not transient).
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff

# --- ComfyUI workflow constants (carried over from the monolithic server.py) ---

SD15_CKPT = "homofidelis_v50.safetensors"
BEAR_LORA = "Muscle_Bear_Baker_v2_for_transfer.safetensors"
EXPLICIT_LORA = "erect_penis_epoch_80.safetensors"
SDXL_PHOTONIC = "photonicFusionSDXL_final.safetensors"

EXPLICIT_KW = {"explicit", "erect", "hard cock", "erection", "boner", "cock", "nude explicit"}
SDXL_KW = {"realistic", "sdxl", "photo", "photorealistic", "high res", "high quality", "photonic"}


def _seed() -> int:
    return int.from_bytes(os.urandom(8), "little") & 0xFFFFFFFFFFFFFFFF


def _parse_comfy(prompt: str) -> dict:
    """Parse prompt keywords into ComfyUI workflow parameters."""
    low = prompt.lower()
    sdxl = any(k in low for k in SDXL_KW)
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
    neg = "worst quality, low quality, bad anatomy, deformed, ugly, watermark, text, blurry"
    if sdxl:
        neg += ", illustration, painting, drawing, cartoon"
    return dict(sdxl=sdxl, explicit=explicit, w=w, h=h, steps=steps, cfg=cfg, lstr=lstr, neg=neg)


def _wf_sd15(prompt: str, p: dict) -> dict:
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SD15_CKPT}},
        "4": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": BEAR_LORA,
                "strength_model": p["lstr"],
                "strength_clip": p["lstr"],
            },
        },
    }
    model_node = "4"
    if p["explicit"]:
        wf["9"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": [model_node, 0],
                "clip": ["4", 1],
                "lora_name": EXPLICIT_LORA,
                "strength_model": 0.75,
                "strength_clip": 0.0,
            },
        }
        model_node = "9"
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": p["neg"], "clip": ["4", 1]}}
    wf["5"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": p["w"], "height": p["h"], "batch_size": 1},
    }
    wf["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": _seed(),
            "steps": p["steps"],
            "cfg": p["cfg"],
            "sampler_name": "euler_ancestral",
            "scheduler": "karras",
            "denoise": 1.0,
            "model": [model_node, 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["5", 0],
        },
    }
    wf["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
    wf["8"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "Kitty", "images": ["7", 0]},
    }
    return wf


def _wf_sdxl(prompt: str, p: dict) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SDXL_PHOTONIC}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": p["neg"], "clip": ["1", 1]}},
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": p["w"], "height": p["h"], "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": _seed(),
                "steps": p["steps"],
                "cfg": p["cfg"],
                "sampler_name": "euler",
                "scheduler": "sgm_uniform",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "KittyXL", "images": ["6", 0]},
        },
    }


# ComfyUI only retries on connection/timeout errors, not 4xx or HTTP status errors.
# 4xx from ComfyUI is usually a prompt issue, not a transient failure.
_comfy_retry = retry_with_backoff(attempts=settings.retry_attempts)


class ComfyuiEngine:
    """Local ComfyUI — SD1.5/SDXL with LoRAs, full NSFW, no API cost."""

    @property
    def name(self) -> str:
        return "comfyui"

    @property
    def model_name(self) -> str:
        # Includes the workflow variant so SDXL vs SD15 cache keys differ.
        return "comfyui-local"

    @_comfy_retry
    async def generate_async(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        negative_prompt: str | None = None,
        steps: int | None = None,
        cfg_scale: float | None = None,
        **kwargs: object,
    ) -> bytes:
        p = _parse_comfy(prompt)
        if negative_prompt:
            p["neg"] = negative_prompt
        if steps is not None:
            p["steps"] = steps
        if cfg_scale is not None:
            p["cfg"] = cfg_scale
        workflow = _wf_sdxl(prompt, p) if p["sdxl"] else _wf_sd15(prompt, p)

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{settings.comfy_url}/prompt", json={"prompt": workflow})
            if r.status_code != 200:
                raise RefusalError(f"ComfyUI rejected the prompt: {r.text}")
            prompt_id = r.json()["prompt_id"]

            deadline = time.monotonic() + 360
            filename = None
            while time.monotonic() < deadline:
                await asyncio.sleep(4)
                hist = (await client.get(f"{settings.comfy_url}/history/{prompt_id}")).json()
                if prompt_id not in hist:
                    continue
                for out in hist[prompt_id].get("outputs", {}).values():
                    for img in out.get("images", []):
                        filename = img["filename"]
                        break
                if filename:
                    break

            if not filename:
                raise TimeoutError("ComfyUI timed out after 6 minutes.")

            view = await client.get(
                f"{settings.comfy_url}/view", params={"filename": filename, "type": "output"}
            )
            return view.content

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        photorealistic: bool = True,
        seed: int | None = None,
        **kwargs: object,
    ) -> bytes:
        """Sync wrapper — runs the async generation in a new event loop."""
        return asyncio.run(
            self.generate_async(
                prompt,
                aspect_ratio=aspect_ratio,
                photorealistic=photorealistic,
                seed=seed,
                **kwargs,
            )
        )

    def edit(self, image_path: Path, edit_prompt: str) -> bytes:
        """ComfyUI does not support natural-language editing — use Nano Banana."""
        raise NotImplementedError(
            "ComfyUI does not support editing. Use engine='nano_banana' for edit_image."
        )
