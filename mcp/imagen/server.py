"""Imagen MCP server — Gemini Imagen 3, DALL-E 3, and ComfyUI in one place.

Tools:
  generate_image        — Gemini Imagen 3 (photorealistic, tasteful NSFW ok)
  edit_image            — Gemini 2.0 Flash image editing
  batch_generate        — parallel Imagen 3 (up to 10 prompts)
  generate_image_dalle  — DALL-E 3 (creative, strong prompt adherence)
  generate_image_comfy  — ComfyUI local (full NSFW including explicit, needs ComfyUI running)
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

OUTPUT_DIR = Path.home() / "Pictures" / "kitty-gen"

mcp = FastMCP(
    "imagen",
    instructions=(
        "Generate and edit images using three backends:\n"
        "• generate_image — Gemini Imagen 3: best photorealism, tasteful NSFW ok\n"
        "• generate_image_dalle — DALL-E 3: great at complex creative prompts, no NSFW\n"
        "• generate_image_comfy — ComfyUI local: full NSFW including explicit, SD1.5/SDXL\n"
        "• edit_image — Gemini 2.0 Flash: natural-language edits to existing images\n"
        "• batch_generate — multiple prompts in parallel via Imagen 3\n"
        "All images saved to ~/Pictures/kitty-gen/."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment")
    from google import genai
    return genai.Client(api_key=api_key)


def _openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment")
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def _save(image_bytes: bytes, prefix: str = "gen") -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{prefix}_{int(time.time() * 1000)}.png"
    path.write_bytes(image_bytes)
    return path


# ---------------------------------------------------------------------------
# ComfyUI helpers (mirrors gateway/image_gen.py without the gateway dep)
# ---------------------------------------------------------------------------

COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")

SD15_CKPT = "homofidelis_v50.safetensors"
BEAR_LORA = "Muscle_Bear_Baker_v2_for_transfer.safetensors"
EXPLICIT_LORA = "erect_penis_epoch_80.safetensors"
SDXL_PHOTONIC = "photonicFusionSDXL_final.safetensors"

EXPLICIT_KW = {"explicit", "erect", "hard cock", "erection", "boner", "cock", "nude explicit"}
SDXL_KW = {"realistic", "sdxl", "photo", "photorealistic", "high res", "high quality", "photonic"}


def _seed() -> int:
    return int.from_bytes(os.urandom(8), "little") & 0xFFFFFFFFFFFFFFFF


def _parse_comfy(prompt: str) -> dict:
    low = prompt.lower()
    sdxl = any(k in low for k in SDXL_KW)
    explicit = any(k in low for k in EXPLICIT_KW)
    if sdxl:
        w, h, steps, cfg = 1024, 1024, 6, 1.5
        if "portrait" in low: w, h = 832, 1216
        if "landscape" in low: w, h = 1216, 832
        if "detailed" in low: steps, cfg = 10, 2.0
    else:
        w, h, steps, cfg = 512, 512, 25, 7.0
        if "portrait" in low: w, h = 512, 768
        if "landscape" in low: w, h = 768, 512
        if "fast" in low: steps = 15
        if "detailed" in low: steps = 35
    lstr = 1.0 if "more bear" in low else 0.5 if "less bear" in low else 0.8
    neg = "worst quality, low quality, bad anatomy, deformed, ugly, watermark, text, blurry"
    if sdxl:
        neg += ", illustration, painting, drawing, cartoon"
    return dict(sdxl=sdxl, explicit=explicit, w=w, h=h, steps=steps, cfg=cfg, lstr=lstr, neg=neg)


def _wf_sd15(prompt: str, p: dict) -> dict:
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SD15_CKPT}},
        "4": {"class_type": "LoraLoader",
              "inputs": {"model": ["1", 0], "clip": ["1", 1],
                         "lora_name": BEAR_LORA, "strength_model": p["lstr"], "strength_clip": p["lstr"]}},
    }
    model_node = "4"
    if p["explicit"]:
        wf["9"] = {"class_type": "LoraLoader",
                   "inputs": {"model": [model_node, 0], "clip": ["4", 1],
                              "lora_name": EXPLICIT_LORA, "strength_model": 0.75, "strength_clip": 0.0}}
        model_node = "9"
    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": p["neg"], "clip": ["4", 1]}}
    wf["5"] = {"class_type": "EmptyLatentImage", "inputs": {"width": p["w"], "height": p["h"], "batch_size": 1}}
    wf["6"] = {"class_type": "KSampler",
               "inputs": {"seed": _seed(), "steps": p["steps"], "cfg": p["cfg"],
                          "sampler_name": "euler_ancestral", "scheduler": "karras",
                          "denoise": 1.0, "model": [model_node, 0],
                          "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["5", 0]}}
    wf["7"] = {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}}
    wf["8"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": "Kitty", "images": ["7", 0]}}
    return wf


def _wf_sdxl(prompt: str, p: dict) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SDXL_PHOTONIC}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": p["neg"], "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": p["w"], "height": p["h"], "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": _seed(), "steps": p["steps"], "cfg": p["cfg"],
                         "sampler_name": "euler", "scheduler": "sgm_uniform",
                         "denoise": 1.0, "model": ["1", 0],
                         "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "KittyXL", "images": ["6", 0]}},
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_image(
    prompt: str,
    aspect_ratio: str = "1:1",
    count: int = 1,
    negative_prompt: str = "",
) -> str:
    """Generate photorealistic images using Gemini Imagen 3. Good for: portraits,
    landscapes, product shots, tasteful NSFW (artistic nudity, suggestive).

    Args:
        prompt: What to generate. Be descriptive — lighting, style, subject, setting.
        aspect_ratio: "1:1", "16:9", "9:16", "4:3", or "3:4". Default 1:1.
        count: Number of images (1–4). Default 1.
        negative_prompt: Elements to avoid.

    Returns:
        File paths for each generated image, one per line.
    """
    from google.genai import types

    client = _gemini_client()
    cfg = types.GenerateImagesConfig(
        number_of_images=max(1, min(count, 4)),
        aspect_ratio=aspect_ratio,
    )
    if negative_prompt:
        cfg.negative_prompt = negative_prompt

    response = client.models.generate_images(
        model="imagen-3.0-generate-001",
        prompt=prompt,
        config=cfg,
    )

    paths: list[str] = []
    for img in response.generated_images:
        p = _save(img.image.image_bytes, "imagen")
        paths.append(str(p))

    if not paths:
        return "No images generated — prompt may have been blocked by Imagen's safety filters."
    return "Generated:\n" + "\n".join(paths)


@mcp.tool()
def edit_image(image_path: str, edit_prompt: str) -> str:
    """Edit an existing image with natural language using Gemini 2.0 Flash.

    Args:
        image_path: Absolute path to the source image (PNG or JPEG).
        edit_prompt: What to change, e.g. "make the background a sunset" or
                     "add a coffee cup on the desk".

    Returns:
        File path to the edited image.
    """
    from google import genai
    from google.genai import types

    src = Path(image_path).expanduser()
    if not src.exists():
        return f"File not found: {image_path}"

    raw = src.read_bytes()
    mime = "image/jpeg" if src.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    client = _gemini_client()

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[types.Content(role="user", parts=[
            types.Part.from_bytes(data=raw, mime_type=mime),
            types.Part.from_text(text=edit_prompt),
        ])],
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            p = _save(part.inline_data.data, "edit")
            return f"Edited image saved to: {p}"

    text_parts = [p.text for p in response.candidates[0].content.parts if p.text]
    reason = " ".join(text_parts) if text_parts else "unknown"
    return f"Edit produced no image. Model said: {reason}"


@mcp.tool()
async def batch_generate(prompts: list[str], aspect_ratio: str = "1:1") -> str:
    """Generate multiple images in parallel from a list of prompts using Imagen 3.

    Args:
        prompts: Up to 10 text prompts, one image each.
        aspect_ratio: "1:1", "16:9", "9:16", "4:3", or "3:4". Default 1:1.

    Returns:
        Each prompt mapped to its output file path.
    """
    from google.genai import types

    if not prompts:
        return "No prompts provided."
    prompts = prompts[:10]
    client = _gemini_client()

    async def _one(prompt: str, idx: int) -> tuple[int, str, str]:
        cfg = types.GenerateImagesConfig(number_of_images=1, aspect_ratio=aspect_ratio)
        try:
            response = await asyncio.to_thread(
                client.models.generate_images,
                model="imagen-3.0-generate-001",
                prompt=prompt,
                config=cfg,
            )
            imgs = response.generated_images
            if imgs:
                p = _save(imgs[0].image.image_bytes, f"batch{idx:02d}")
                return idx, prompt, str(p)
            return idx, prompt, "BLOCKED"
        except Exception as e:
            return idx, prompt, f"ERROR: {e}"

    results = sorted(
        await asyncio.gather(*[_one(p, i) for i, p in enumerate(prompts)]),
        key=lambda r: r[0],
    )
    return "\n".join(f"{r[1]!r} → {r[2]}" for r in results)


@mcp.tool()
def generate_image_dalle(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "hd",
) -> str:
    """Generate an image using DALL-E 3. Good for: creative/illustrative prompts,
    text in images, abstract concepts. No NSFW.

    Args:
        prompt: What to generate. DALL-E 3 is good at following complex instructions.
        size: "1024x1024", "1792x1024" (landscape), or "1024x1792" (portrait).
        quality: "hd" (default, more detail) or "standard" (faster).

    Returns:
        File path to the generated image.
    """
    import httpx

    client = _openai_client()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,  # type: ignore[arg-type]
        quality=quality,  # type: ignore[arg-type]
        n=1,
    )

    url = response.data[0].url
    if not url:
        return "DALL-E returned no image URL."

    image_bytes = httpx.get(url, timeout=60).content
    p = _save(image_bytes, "dalle")
    revised = response.data[0].revised_prompt
    result = f"Generated: {p}"
    if revised and revised != prompt:
        result += f"\nDALL-E revised your prompt to: {revised}"
    return result


@mcp.tool()
async def generate_image_comfy(prompt: str) -> str:
    """Generate an image using local ComfyUI (SD1.5 or SDXL). Good for: full NSFW
    including explicit content, custom LoRAs, local generation with no API cost.
    Requires ComfyUI running at COMFY_URL (default http://127.0.0.1:8188).

    Prompt keywords:
      • "realistic" / "photo" / "sdxl" / "photonic" → SDXL model
      • "explicit" / "erect" / "cock" etc → explicit LoRA
      • "portrait" / "landscape" → aspect ratio
      • "detailed" → more steps
      • "more bear" / "less bear" → bear LoRA strength

    Args:
        prompt: Text description. LoRA and model selection is automatic from keywords.

    Returns:
        Filename of the generated image (served by ComfyUI at /view?filename=...).
    """
    import httpx

    p = _parse_comfy(prompt)
    workflow = _wf_sdxl(prompt, p) if p["sdxl"] else _wf_sd15(prompt, p)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
        except httpx.ConnectError:
            return f"Could not reach ComfyUI at {COMFY_URL}. Is it running?"
        if r.status_code != 200:
            return f"ComfyUI rejected prompt: {r.text}"
        prompt_id = r.json()["prompt_id"]

        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            await asyncio.sleep(4)
            hist = (await client.get(f"{COMFY_URL}/history/{prompt_id}")).json()
            if prompt_id not in hist:
                continue
            for out in hist[prompt_id].get("outputs", {}).values():
                for img in out.get("images", []):
                    filename = img["filename"]
                    view_url = f"{COMFY_URL}/view?filename={filename}&type=output"
                    return f"Generated: {filename}\nView: {view_url}"

    return "ComfyUI timed out after 6 minutes."


if __name__ == "__main__":
    mcp.run()
