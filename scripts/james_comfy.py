#!/usr/bin/env python3
"""Run the James identity workflow against a ComfyUI instance.

The identity LoRA was trained on Flux, so everything here is Flux-family. Jacob's
larger body LoRAs (xhirsute, sulphur2, the Qwen penis LoRAs) target Qwen-Image
and cannot be stacked with it — mixing families is why earlier results were
inconsistent. Retraining identity on Qwen is the only way to use those.

Usage:
    COMFY_URL=https://<pod>-8188.proxy.runpod.net \\
    python3 scripts/james_comfy.py "prompt" --identity 0.9 --steps 24
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
CHECKPOINT = os.environ.get("JAMES_CHECKPOINT", "flux1-dev-fp8.safetensors")
IDENTITY_LORA = os.environ.get(
    "JAMES_IDENTITY_LORA", "FrhOzsbkqvvcgrLw_2Tel_pytorch_lora_weights.safetensors"
)
ANATOMY_LORA = os.environ.get(
    "JAMES_ANATOMY_LORA", "Male_Nude_and_Genital_Anatomy_for_Flux_1_Dev.safetensors"
)
OUT_DIR = Path(os.environ.get("JAMES_OUT_DIR", "data/images/james"))

# RunPod's proxy rejects requests without a browser agent.
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def upload_image(path: Path) -> str:
    """Push a reference into ComfyUI's input folder and return its name."""
    boundary = "----kitty" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=body,
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)["name"]


def build_workflow(
    prompt: str,
    *,
    identity: float,
    anatomy: float,
    steps: int,
    seed: int,
    width: int,
    height: int,
    guidance: float,
    source: str | None = None,
    denoise: float = 1.0,
) -> dict:
    """Checkpoint -> identity LoRA -> anatomy LoRA -> sample -> save.

    Order matters: identity loads first so the anatomy LoRA modifies a model that
    already knows the face, rather than competing with it for the same weights.
    """
    graph: dict = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": CHECKPOINT},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": IDENTITY_LORA,
                "strength_model": identity,
                "strength_clip": identity,
                "model": ["1", 0],
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["2", 1]},
        },
        "5": {
            "class_type": "FluxGuidance",
            "inputs": {"guidance": guidance, "conditioning": ["4", 0]},
        },
        "6": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": denoise,
                "model": ["2", 0],
                "positive": ["5", 0],
                # Flux is guidance-distilled: CFG 1.0 means the negative branch
                # is never evaluated, so it only needs to be a valid conditioning.
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "james", "images": ["8", 0]},
        },
    }
    if source is not None:
        # Starting from real pixels of Jacob's face beats any LoRA this pair was
        # trained to be. Low denoise keeps the face and repaints everything else.
        graph["10"] = {"class_type": "LoadImage", "inputs": {"image": source}}
        graph["11"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["10", 0], "vae": ["1", 2]},
        }
        graph["7"]["inputs"]["latent_image"] = ["11", 0]
        del graph["6"]

    if anatomy > 0:
        graph["3"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": ANATOMY_LORA,
                "strength_model": anatomy,
                "strength_clip": anatomy,
                "model": ["2", 0],
                "clip": ["2", 1],
            },
        }
        graph["4"]["inputs"]["clip"] = ["3", 1]
        graph["7"]["inputs"]["model"] = ["3", 0]
    return graph


def _post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{COMFY_URL}{path}", data=json.dumps(payload).encode(), headers=HEADERS
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def _get(path: str) -> dict:
    request = urllib.request.Request(f"{COMFY_URL}{path}", headers={"User-Agent": HEADERS["User-Agent"]})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def run(workflow: dict, *, timeout: float = 900) -> list[Path]:
    client_id = str(uuid.uuid4())
    queued = _post("/prompt", {"prompt": workflow, "client_id": client_id})
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise SystemExit(f"ComfyUI rejected the workflow: {json.dumps(queued)[:400]}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = _get(f"/history/{prompt_id}")
        entry = history.get(prompt_id)
        if entry:
            status = (entry.get("status") or {}).get("status_str")
            if status == "error":
                messages = (entry.get("status") or {}).get("messages")
                raise SystemExit(f"ComfyUI errored: {json.dumps(messages)[:600]}")
            images = [
                image
                for output in (entry.get("outputs") or {}).values()
                for image in (output.get("images") or [])
            ]
            if images:
                return [_download(image) for image in images]
        time.sleep(3)
    raise SystemExit(f"ComfyUI did not finish within {timeout:.0f}s")


def _download(image: dict) -> Path:
    query = urllib.parse.urlencode(
        {
            "filename": image["filename"],
            "subfolder": image.get("subfolder", ""),
            "type": image.get("type", "output"),
        }
    )
    request = urllib.request.Request(
        f"{COMFY_URL}/view?{query}", headers={"User-Agent": HEADERS["User-Agent"]}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        data = response.read()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / image["filename"]
    target.write_bytes(data)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--identity", type=float, default=0.9)
    parser.add_argument("--anatomy", type=float, default=0.0)
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--width", type=int, default=896)
    parser.add_argument("--height", type=int, default=1152)
    parser.add_argument("--guidance", type=float, default=3.0)
    parser.add_argument("--source", help="reference image to start from (img2img)")
    parser.add_argument("--denoise", type=float, default=1.0)
    args = parser.parse_args()

    source = None
    if args.source:
        source = upload_image(Path(args.source).expanduser())
        if args.denoise >= 1.0:
            # Denoise 1.0 discards the source entirely — silently ignoring the
            # reference the caller just supplied.
            raise SystemExit("--source needs --denoise below 1.0 (try 0.4)")

    workflow = build_workflow(
        args.prompt,
        identity=args.identity,
        anatomy=args.anatomy,
        steps=args.steps,
        seed=args.seed,
        width=args.width,
        height=args.height,
        guidance=args.guidance,
        source=source,
        denoise=args.denoise,
    )
    started = time.monotonic()
    try:
        paths = run(workflow)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"ComfyUI HTTP {exc.code}: {exc.read()[:300].decode(errors='replace')}")
    for path in paths:
        print(f"{time.monotonic() - started:.1f}s  {path}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
