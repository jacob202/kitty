"""Imagen MCP server — photorealistic image generation and editing for Claude Code.

Default engine is Google's "Nano Banana" (gemini-2.5-flash-image), which does both
generation and natural-language editing with strong photorealism. Imagen 4, DALL-E 3,
and local ComfyUI are available as opt-in alternatives.

Every tool returns the image inline (it renders directly in the chat) AND saves a
copy to ~/Pictures/kitty-gen/ so you can pass the path back to edit_image to refine it.

Tools:
  generate_image        — Nano Banana: photorealistic generation (the default)
  edit_image            — Nano Banana: natural-language edits to an existing image
  generate_with_reference — Nano Banana: keep a subject consistent / composite images
  refine_image          — auto loop: generate → vision-critique → edit until it matches
  variations            — several alternates of an existing image
  set_avatar / generate_with_avatar — a persistent character you can drop into scenes
  make_gallery          — HTML contact sheet of everything generated
  generate_image_imagen — Imagen 4: alternative high-fidelity generation, 1-4 at once
  generate_image_dalle  — DALL-E 3: creative/illustrative prompts, text-in-image
  generate_image_comfy  — local ComfyUI: full NSFW incl. explicit (needs ComfyUI running)
"""

from __future__ import annotations

import asyncio
import html
import os
import shutil
import time
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Image

load_dotenv(Path(__file__).parent / ".env")

OUTPUT_DIR = Path.home() / "Pictures" / "kitty-gen"
AVATAR_PATH = OUTPUT_DIR / "_avatar.png"

# Overridable so model-name drift never bricks the server — bump via env if Google
# ships a newer image model (e.g. GEMINI_IMAGE_MODEL=gemini-3.1-flash-image).
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
GEMINI_VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")
IMAGEN_MODEL = os.environ.get("IMAGEN_MODEL", "imagen-4.0-generate-001")

# Appended to a prompt when photorealistic=True. Photographic cues measurably push
# Nano Banana toward realism; toggle off for illustration/painting styles.
PHOTOREAL_SUFFIX = (
    ", photorealistic, shot on a full-frame DSLR, 85mm lens, natural lighting, "
    "shallow depth of field, sharp focus, high detail, true-to-life color"
)

mcp = FastMCP(
    "imagen",
    instructions=(
        "Generate and edit photorealistic images. Default to generate_image (Nano "
        "Banana) for new images and edit_image to refine them — both render inline and "
        "save to ~/Pictures/kitty-gen/. The generate→look→edit loop is the intended "
        "workflow: make an image, the user reacts, call edit_image with their change. "
        "To keep a subject consistent or composite images, use generate_with_reference. "
        "set_avatar pins a recurring character for generate_with_avatar. refine_image "
        "runs the generate→critique→edit loop automatically. variations makes alternates, "
        "make_gallery builds a browsable contact sheet. "
        "Use generate_image_imagen for batches of 1-4, generate_image_dalle for "
        "illustrative/text-heavy prompts, generate_image_comfy for explicit NSFW."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment")
    from google import genai
    return genai.Client(api_key=api_key)


def _openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment")
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def _save(image_bytes: bytes, prefix: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{prefix}_{int(time.time() * 1000)}.png"
    path.write_bytes(image_bytes)
    return path


def _first_image_bytes(response) -> bytes | None:
    """Pull raw image bytes out of a generate_content response, or None if the model
    returned only text (usually a safety refusal explaining why)."""
    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
    return None


def _refusal_text(response) -> str:
    texts = []
    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            if getattr(part, "text", None):
                texts.append(part.text)
    return " ".join(texts) if texts else "no image and no explanation returned"


def _image_part(path: Path):
    """Build a Gemini image Part from a file on disk."""
    from google.genai import types

    raw = path.read_bytes()
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return types.Part.from_bytes(data=raw, mime_type=mime)


def _nano_image(contents) -> tuple[bytes | None, str]:
    """Run a Nano Banana generate_content call, return (image_bytes, refusal_text)."""
    from google.genai import types

    client = _gemini_client()
    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    return _first_image_bytes(response), _refusal_text(response)


# ---------------------------------------------------------------------------
# ComfyUI helpers (mirrors gateway/image_gen.py without the gateway dependency)
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
    photorealistic: bool = True,
) -> list:
    """Generate an image from a text description using Nano Banana (gemini-2.5-flash-image).
    This is the default, best-quality engine for photorealism. The image renders inline
    and is saved to ~/Pictures/kitty-gen/ — pass that path to edit_image to refine it.

    Args:
        prompt: What to generate. Be specific about subject, setting, lighting, mood.
        aspect_ratio: 1:1, 3:2, 2:3, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, or 21:9. Default 1:1.
        photorealistic: When True (default), appends photographic quality cues to the
                        prompt. Set False for illustrations, paintings, or cartoons.

    Returns:
        The generated image (inline) plus the saved file path.
    """
    from google.genai import types

    full_prompt = prompt + (PHOTOREAL_SUFFIX if photorealistic else "")
    client = _gemini_client()

    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )

    data = _first_image_bytes(response)
    if data is None:
        return [f"No image generated. Model said: {_refusal_text(response)}"]

    path = _save(data, "nano")
    return [
        Image(data=data, format="png"),
        f"Saved to: {path}\n(pass this path to edit_image to refine it)",
    ]


@mcp.tool()
def edit_image(image_path: str, edit_prompt: str) -> list:
    """Edit an existing image with natural-language instructions using Nano Banana.
    Keeps the rest of the image consistent and only changes what you ask for. The result
    renders inline and is saved as a new file (the original is untouched).

    Args:
        image_path: Absolute path to the source image (PNG or JPEG).
        edit_prompt: What to change, e.g. "make the background a sunset over the ocean",
                     "give her a red dress", "remove the car", "make it nighttime".

    Returns:
        The edited image (inline) plus the saved file path.
    """
    from google import genai  # noqa: F401  (ensures package present for clear error)
    from google.genai import types

    src = Path(image_path).expanduser()
    if not src.exists():
        return [f"File not found: {image_path}"]

    raw = src.read_bytes()
    mime = "image/jpeg" if src.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    client = _gemini_client()

    response = client.models.generate_content(
        model=GEMINI_IMAGE_MODEL,
        contents=[
            types.Part.from_bytes(data=raw, mime_type=mime),
            types.Part.from_text(text=edit_prompt),
        ],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )

    data = _first_image_bytes(response)
    if data is None:
        return [f"Edit produced no image. Model said: {_refusal_text(response)}"]

    path = _save(data, "edit")
    return [
        Image(data=data, format="png"),
        f"Saved to: {path}\n(pass this path back to edit_image to keep refining)",
    ]


@mcp.tool()
def generate_image_imagen(
    prompt: str,
    aspect_ratio: str = "1:1",
    count: int = 1,
) -> list:
    """Generate 1-4 images at once using Imagen 4 (imagen-4.0-generate-001). An alternative
    to generate_image when you want several variations of the same prompt in one call.
    Allows tasteful adult imagery (person_generation=ALLOW_ADULT); explicit content is
    blocked — use generate_image_comfy for that. All images render inline and are saved.

    Args:
        prompt: What to generate.
        aspect_ratio: 1:1, 3:4, 4:3, 9:16, or 16:9. Default 1:1.
        count: Number of variations (1-4). Default 1.

    Returns:
        Each generated image (inline) plus its saved file path.
    """
    from google.genai import types

    client = _gemini_client()
    response = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=max(1, min(count, 4)),
            aspect_ratio=aspect_ratio,
            person_generation="ALLOW_ADULT",
        ),
    )

    out: list = []
    for img in response.generated_images or []:
        data = img.image.image_bytes
        path = _save(data, "imagen")
        out.append(Image(data=data, format="png"))
        out.append(f"Saved to: {path}")

    if not out:
        return ["No images generated — the prompt was likely blocked by Imagen's safety filters."]
    return out


@mcp.tool()
def generate_image_dalle(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "hd",
) -> list:
    """Generate an image using DALL-E 3. Best for creative/illustrative prompts, rendering
    text inside the image, and strong instruction-following. No NSFW. Renders inline + saved.

    Args:
        prompt: What to generate. DALL-E 3 follows complex multi-part instructions well.
        size: 1024x1024, 1792x1024 (landscape), or 1024x1792 (portrait).
        quality: "hd" (default, more detail) or "standard" (faster, cheaper).

    Returns:
        The generated image (inline) plus the saved file path, and any prompt revision.
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
        return ["DALL-E returned no image URL."]

    data = httpx.get(url, timeout=60).content
    path = _save(data, "dalle")
    result = [Image(data=data, format="png"), f"Saved to: {path}"]

    revised = response.data[0].revised_prompt
    if revised and revised.strip() != prompt.strip():
        result.append(f"DALL-E revised your prompt to: {revised}")
    return result


@mcp.tool()
async def generate_image_comfy(prompt: str) -> list:
    """Generate an image using local ComfyUI (SD1.5 / SDXL). The only backend that allows
    full explicit NSFW; uses the LoRAs already configured in your ComfyUI. No API cost.
    Requires ComfyUI running at COMFY_URL (default http://127.0.0.1:8188). Renders inline.

    Prompt keywords drive model/LoRA selection automatically:
      realistic / photo / sdxl / photonic → SDXL model
      explicit / erect / cock / etc        → explicit LoRA
      portrait / landscape                 → aspect ratio
      detailed                             → more sampling steps
      more bear / less bear                → bear LoRA strength

    Args:
        prompt: Text description. Model and LoRA selection is automatic from keywords.

    Returns:
        The generated image (inline) plus its ComfyUI filename.
    """
    import httpx

    p = _parse_comfy(prompt)
    workflow = _wf_sdxl(prompt, p) if p["sdxl"] else _wf_sd15(prompt, p)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
        except httpx.ConnectError:
            return [f"Could not reach ComfyUI at {COMFY_URL}. Is it running?"]
        if r.status_code != 200:
            return [f"ComfyUI rejected the prompt: {r.text}"]
        prompt_id = r.json()["prompt_id"]

        deadline = time.monotonic() + 360
        filename = None
        while time.monotonic() < deadline:
            await asyncio.sleep(4)
            hist = (await client.get(f"{COMFY_URL}/history/{prompt_id}")).json()
            if prompt_id not in hist:
                continue
            for out in hist[prompt_id].get("outputs", {}).values():
                for img in out.get("images", []):
                    filename = img["filename"]
                    break
            if filename:
                break

        if not filename:
            return ["ComfyUI timed out after 6 minutes."]

        view = await client.get(
            f"{COMFY_URL}/view", params={"filename": filename, "type": "output"}
        )
        data = view.content

    _save(data, "comfy")
    return [Image(data=data, format="png"), f"ComfyUI file: {filename}"]


@mcp.tool()
def generate_with_reference(
    reference_paths: list[str],
    prompt: str,
) -> list:
    """Generate an image conditioned on one or more reference images using Nano Banana.
    This is the standout capability no other engine has:

      • One reference → keep that subject CONSISTENT in a new scene
        ("the person in this photo, now sitting in a Paris cafe at night").
      • Multiple references → COMPOSITE them
        ("put the person from image 1 in the room from image 2",
         "dress the model in image 1 in the outfit from image 2").

    Args:
        reference_paths: 1-3 absolute paths to reference images (PNG/JPEG).
        prompt: What to make using those references.

    Returns:
        The generated image (inline) plus the saved file path.
    """
    refs = [Path(p).expanduser() for p in reference_paths]
    missing = [str(p) for p in refs if not p.exists()]
    if missing:
        return ["Reference file(s) not found: " + ", ".join(missing)]

    from google.genai import types

    contents = [_image_part(p) for p in refs[:3]]
    contents.append(types.Part.from_text(text=prompt))

    data, refusal = _nano_image(contents)
    if data is None:
        return [f"No image generated. Model said: {refusal}"]

    path = _save(data, "ref")
    return [Image(data=data, format="png"), f"Saved to: {path}"]


@mcp.tool()
def set_avatar(image_path: str) -> str:
    """Pin a reference image as the persistent avatar/character. Once set, use
    generate_with_avatar to drop this exact subject into any scene without re-uploading.

    Args:
        image_path: Absolute path to the image to use as the persistent character.

    Returns:
        Confirmation and where it was stored.
    """
    src = Path(image_path).expanduser()
    if not src.exists():
        return f"File not found: {image_path}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, AVATAR_PATH)
    return f"Avatar set from {src.name}. Use generate_with_avatar to place this character in scenes."


@mcp.tool()
def generate_with_avatar(prompt: str) -> list:
    """Generate an image of the pinned avatar character (see set_avatar) in a new scene,
    keeping the character consistent. Convenience wrapper over generate_with_reference.

    Args:
        prompt: The scene/action, e.g. "on a snowy mountain trail, golden hour".

    Returns:
        The generated image (inline) plus the saved file path.
    """
    if not AVATAR_PATH.exists():
        return ["No avatar set yet. Call set_avatar with an image path first."]

    from google.genai import types

    contents = [_image_part(AVATAR_PATH), types.Part.from_text(text=prompt)]
    data, refusal = _nano_image(contents)
    if data is None:
        return [f"No image generated. Model said: {refusal}"]

    path = _save(data, "avatar")
    return [Image(data=data, format="png"), f"Saved to: {path}"]


@mcp.tool()
def variations(image_path: str, count: int = 3) -> list:
    """Produce several alternates of an existing image — same subject, varied pose,
    angle, and lighting. Good for "give me more like this one."

    Args:
        image_path: Absolute path to the source image.
        count: How many variations (1-4). Default 3.

    Returns:
        Each variation (inline) plus its saved path.
    """
    src = Path(image_path).expanduser()
    if not src.exists():
        return [f"File not found: {image_path}"]

    from google.genai import types

    vary_prompt = (
        "Create a variation of this image. Keep the same subject and overall style, "
        "but change the pose, camera angle, and lighting. Photorealistic."
    )

    out: list = []
    for _ in range(max(1, min(count, 4))):
        contents = [_image_part(src), types.Part.from_text(text=vary_prompt)]
        data, refusal = _nano_image(contents)
        if data is None:
            out.append(f"A variation failed: {refusal}")
            continue
        path = _save(data, "var")
        out.append(Image(data=data, format="png"))
        out.append(f"Saved to: {path}")

    return out or ["No variations were produced."]


@mcp.tool()
def refine_image(prompt: str, target: str = "", max_rounds: int = 3) -> list:
    """Generate an image, then automatically critique and re-edit it until it matches —
    the autonomous generate → analyze → fix loop. Each round a vision model checks the
    result against `target` (or `prompt`) and either approves it or hands back one
    concrete edit, which is applied before the next check.

    Args:
        prompt: What to generate initially.
        target: The success criteria to judge against. Defaults to `prompt`.
        max_rounds: Max critique/edit rounds (1-5). Default 3.

    Returns:
        The final image (inline), the saved path, and the round-by-round critique trail.
    """
    from google.genai import types

    goal = target.strip() or prompt
    client = _gemini_client()

    data, refusal = _nano_image(prompt + PHOTOREAL_SUFFIX)
    if data is None:
        return [f"Initial generation failed. Model said: {refusal}"]

    trail: list[str] = []
    rounds = max(1, min(max_rounds, 5))

    for i in range(rounds):
        critique = client.models.generate_content(
            model=GEMINI_VISION_MODEL,
            contents=[
                types.Part.from_bytes(data=data, mime_type="image/png"),
                types.Part.from_text(text=(
                    f"Target: {goal}\n\n"
                    "Judge whether this image matches the target. If it is a good match, "
                    "reply with exactly the word DONE. Otherwise reply with ONE specific, "
                    "actionable edit instruction (and nothing else) to bring it closer."
                )),
            ],
        )
        verdict = (_refusal_text(critique) or "").strip()

        if verdict.upper().startswith("DONE") or not verdict:
            trail.append(f"Round {i + 1}: approved.")
            break

        trail.append(f"Round {i + 1}: {verdict}")
        new_data, edit_refusal = _nano_image([
            types.Part.from_bytes(data=data, mime_type="image/png"),
            types.Part.from_text(text=verdict),
        ])
        if new_data is None:
            trail.append(f"Round {i + 1}: edit failed ({edit_refusal}); keeping previous.")
            break
        data = new_data

    path = _save(data, "refined")
    return [
        Image(data=data, format="png"),
        f"Saved to: {path}\n\nCritique trail:\n" + "\n".join(trail),
    ]


@mcp.tool()
def make_gallery() -> str:
    """Build an HTML contact sheet of every image in ~/Pictures/kitty-gen, newest first,
    so you can browse past generations. Returns the path to the gallery file.

    Returns:
        Path to the generated gallery.html (open it in a browser).
    """
    if not OUTPUT_DIR.exists():
        return "No images yet — generate something first."

    pngs = sorted(
        (p for p in OUTPUT_DIR.glob("*.png") if p.name != AVATAR_PATH.name),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not pngs:
        return "No images yet — generate something first."

    cards = "\n".join(
        f'<figure><img src="{html.escape(p.name)}" loading="lazy">'
        f'<figcaption>{html.escape(p.name)}</figcaption></figure>'
        for p in pngs
    )
    doc = (
        "<!doctype html><meta charset=utf-8><title>kitty-gen gallery</title>"
        "<style>body{background:#111;color:#eee;font-family:system-ui;margin:1rem}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}"
        "figure{margin:0}img{width:100%;border-radius:8px;display:block}"
        "figcaption{font-size:11px;color:#888;word-break:break-all;margin-top:4px}</style>"
        f"<h1>kitty-gen — {len(pngs)} images</h1><main>{cards}</main>"
    )
    gallery = OUTPUT_DIR / "gallery.html"
    gallery.write_text(doc, encoding="utf-8")
    return f"Gallery written to {gallery} ({len(pngs)} images). Open it in a browser."


if __name__ == "__main__":
    mcp.run()
