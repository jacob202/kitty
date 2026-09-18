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
import hashlib
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.retry import retry_with_backoff

# --- ComfyUI workflow constants (carried over from the monolithic server.py) ---

SD15_CKPT = "homofidelis_v50.safetensors"
BEAR_LORA = "Muscle_Bear_Baker_v2_for_transfer.safetensors"
EXPLICIT_LORA = "erect_penis_epoch_80.safetensors"
SDXL_PHOTONIC = "photonicFusionSDXL_final.safetensors"
FACEID_ADAPTER_FILE = (
    os.environ.get("COMFY_FACEID_ADAPTER_FILE", "").strip() or "ip-adapter-faceid_sd15.bin"
)
FACEID_INSIGHTFACE_MODEL = (
    os.environ.get("COMFY_FACEID_INSIGHTFACE_MODEL", "").strip() or "antelopev2"
)
FACEID_PROVIDER = os.environ.get("COMFY_FACEID_PROVIDER", "").strip() or "CPU"
FACEID_DEFAULT_WEIGHT = 0.9
FACEID_DEFAULT_V2_WEIGHT = 1.3

EXPLICIT_KW = {"explicit", "erect", "hard cock", "erection", "boner", "cock", "nude explicit"}
SDXL_KW = {"realistic", "sdxl", "photo", "photorealistic", "high res", "high quality", "photonic"}


def _seed() -> int:
    return int.from_bytes(os.urandom(8), "little") & 0xFFFFFFFFFFFFFFFF


def _parse_comfy(prompt: str, *, force_sd15: bool = False) -> dict:
    """Parse prompt keywords into ComfyUI workflow parameters.

    FaceID uses the recovered SD1.5 adapter graph, so identity-conditioned
    requests explicitly force the SD1.5 parameter branch even when prompt
    keywords would otherwise select SDXL.
    """
    low = prompt.lower()
    sdxl = not force_sd15 and any(k in low for k in SDXL_KW)
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
            "seed": p["seed"],
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
                "seed": p["seed"],
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



def _wf_sd15_faceid(
    prompt: str,
    p: dict[str, Any],
    *,
    image_name: str,
    id_weight: float,
    faceidv2_weight: float,
) -> dict[str, Any]:
    """Build the recovered FaceID graph on top of Kitty's current SD1.5 graph."""
    wf = _wf_sd15(prompt, p)
    source_model = wf["6"]["inputs"]["model"]
    wf["10"] = {
        "class_type": "IPAdapterModelLoader",
        "inputs": {"ipadapter_file": FACEID_ADAPTER_FILE},
    }
    wf["11"] = {
        "class_type": "IPAdapterInsightFaceLoader",
        "inputs": {
            "provider": FACEID_PROVIDER,
            "model_name": FACEID_INSIGHTFACE_MODEL,
        },
    }
    wf["12"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    wf["13"] = {
        "class_type": "IPAdapterFaceID",
        "inputs": {
            "model": source_model,
            "ipadapter": ["10", 0],
            "image": ["12", 0],
            "insightface": ["11", 0],
            "weight": id_weight,
            "weight_faceidv2": faceidv2_weight,
            "weight_type": "linear",
            "combine_embeds": "average",
            "start_at": 0.0,
            "end_at": 1.0,
            "embeds_scaling": "V only",
        },
    }
    wf["6"]["inputs"]["model"] = ["13", 0]
    wf["8"]["inputs"]["filename_prefix"] = "KittyFaceID"
    return wf


def _choice_values(
    object_info: Mapping[str, Any], node_name: str, input_name: str
) -> set[str] | None:
    node = object_info.get(node_name)
    if not isinstance(node, Mapping):
        return None
    inputs = node.get("input")
    if not isinstance(inputs, Mapping):
        return None
    for group_name in ("required", "optional"):
        group = inputs.get(group_name)
        if not isinstance(group, Mapping):
            continue
        spec = group.get(input_name)
        if (
            isinstance(spec, Sequence)
            and not isinstance(spec, (str, bytes))
            and spec
            and isinstance(spec[0], Sequence)
            and not isinstance(spec[0], (str, bytes))
        ):
            return {str(value) for value in spec[0]}
    return None


def _require_faceid_capabilities(
    object_info: Mapping[str, Any], *, explicit: bool
) -> None:
    required_nodes = {
        "CheckpointLoaderSimple",
        "IPAdapterModelLoader",
        "IPAdapterInsightFaceLoader",
        "IPAdapterFaceID",
        "LoadImage",
        "LoraLoader",
    }
    missing = sorted(node for node in required_nodes if node not in object_info)
    if missing:
        raise RuntimeError(
            "ComfyUI FaceID is unavailable; missing required node(s): "
            + ", ".join(missing)
        )

    checks = [
        ("CheckpointLoaderSimple", "ckpt_name", SD15_CKPT),
        ("LoraLoader", "lora_name", BEAR_LORA),
        ("IPAdapterModelLoader", "ipadapter_file", FACEID_ADAPTER_FILE),
        ("IPAdapterInsightFaceLoader", "provider", FACEID_PROVIDER),
        ("IPAdapterInsightFaceLoader", "model_name", FACEID_INSIGHTFACE_MODEL),
    ]
    if explicit:
        checks.append(("LoraLoader", "lora_name", EXPLICIT_LORA))
    for node_name, input_name, expected in checks:
        choices = _choice_values(object_info, node_name, input_name)
        if choices is not None and expected not in choices:
            raise RuntimeError(
                f"ComfyUI FaceID is unavailable; {node_name}.{input_name} "
                f"does not offer configured value {expected!r}"
            )


def _uploaded_input_name(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        raise RuntimeError("ComfyUI identity upload returned an invalid response")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError("ComfyUI identity upload returned no input image name")
    subfolder = payload.get("subfolder")
    if isinstance(subfolder, str) and subfolder.strip("/"):
        return f"{subfolder.strip('/')}/{name}"
    return name


def _identity_weight(
    value: object, *, label: str, default: float, max_value: float
) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    normalized = float(value)
    if not 0.0 < normalized <= max_value:
        raise ValueError(
            f"{label} must be greater than 0 and at most {max_value:g}"
        )
    return normalized


def _identity_reference(value: object) -> Path | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes, Path)) or not isinstance(value, Sequence):
        raise ValueError("ComfyUI FaceID identity_images must contain exactly one reference image")
    if len(value) != 1:
        raise ValueError(
            "ComfyUI FaceID identity_images must contain exactly one reference image"
        )
    try:
        reference = Path(value[0]).expanduser()
    except TypeError as exc:
        raise ValueError("ComfyUI FaceID reference must be a filesystem path") from exc
    if not reference.is_file():
        raise FileNotFoundError(f"ComfyUI FaceID reference not found: {reference}")
    return reference



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
        identity_path = _identity_reference(kwargs.get("identity_images"))
        p = _parse_comfy(prompt, force_sd15=identity_path is not None)
        p["seed"] = seed if seed is not None else _seed()
        if negative_prompt:
            p["neg"] = negative_prompt
        if steps is not None:
            p["steps"] = steps
        if cfg_scale is not None:
            p["cfg"] = cfg_scale

        id_weight = FACEID_DEFAULT_WEIGHT
        faceidv2_weight = FACEID_DEFAULT_V2_WEIGHT
        image_bytes: bytes | None = None
        upload_name: str | None = None
        if identity_path is not None:
            id_weight = _identity_weight(
                kwargs.get("id_weight"),
                label="id_weight",
                default=FACEID_DEFAULT_WEIGHT,
                max_value=3.0,
            )
            faceidv2_weight = _identity_weight(
                kwargs.get("faceidv2_weight"),
                label="faceidv2_weight",
                default=FACEID_DEFAULT_V2_WEIGHT,
                max_value=5.0,
            )
            image_bytes = identity_path.read_bytes()
            suffix = identity_path.suffix.lower() or ".png"
            upload_name = (
                "kitty-identity-"
                + hashlib.sha256(image_bytes).hexdigest()[:16]
                + suffix
            )

        async with httpx.AsyncClient(timeout=30) as client:
            if identity_path is not None:
                capability_response = await client.get(f"{settings.comfy_url}/object_info")
                if capability_response.status_code != 200:
                    raise RuntimeError(
                        "ComfyUI FaceID capability probe failed with HTTP "
                        f"{capability_response.status_code}"
                    )
                object_info = capability_response.json()
                if not isinstance(object_info, Mapping):
                    raise RuntimeError("ComfyUI FaceID capability probe returned invalid data")
                _require_faceid_capabilities(object_info, explicit=bool(p["explicit"]))

                if image_bytes is None or upload_name is None:
                    raise RuntimeError("ComfyUI FaceID reference preparation failed")
                upload_response = await client.post(
                    f"{settings.comfy_url}/upload/image",
                    files={
                        "image": (
                            upload_name,
                            image_bytes,
                            "application/octet-stream",
                        )
                    },
                    data={"overwrite": "true", "type": "input"},
                )
                if upload_response.status_code != 200:
                    raise RuntimeError(
                        "ComfyUI FaceID identity upload failed with HTTP "
                        f"{upload_response.status_code}"
                    )
                workflow = _wf_sd15_faceid(
                    prompt,
                    p,
                    image_name=_uploaded_input_name(upload_response.json()),
                    id_weight=id_weight,
                    faceidv2_weight=faceidv2_weight,
                )
            else:
                workflow = _wf_sdxl(prompt, p) if p["sdxl"] else _wf_sd15(prompt, p)

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
