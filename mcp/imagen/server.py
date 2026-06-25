"""Gemini Imagen MCP server for Claude Code.

Tools:
  generate_image  — text → image(s) via Imagen 3
  edit_image      — image + prompt → edited image via Gemini 2.0 Flash
  batch_generate  — multiple prompts in parallel via Imagen 3

Add to ~/.claude/settings.json under mcpServers to use in Claude Code.
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
        "Generate and edit photorealistic images using Google Gemini Imagen 3. "
        "Images are saved to ~/Pictures/kitty-gen/ and returned as file paths. "
        "For NSFW tasteful content (artistic nudity, suggestive), pass it directly — "
        "Imagen 3 allows it without the safety_filter_level restriction. "
        "For editing, provide the full path to an existing image file."
    ),
)


def _client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment or .env"
        )
    from google import genai

    return genai.Client(api_key=api_key)


def _save(image_bytes: bytes, prefix: str = "gen") -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{prefix}_{int(time.time() * 1000)}.png"
    path.write_bytes(image_bytes)
    return path


def _to_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{data}"


@mcp.tool()
def generate_image(
    prompt: str,
    aspect_ratio: str = "1:1",
    count: int = 1,
    negative_prompt: str = "",
) -> str:
    """Generate photorealistic images from a text description using Gemini Imagen 3.

    Args:
        prompt: What to generate. Be descriptive — lighting, style, subject, setting.
        aspect_ratio: "1:1", "16:9", "9:16", "4:3", or "3:4". Default 1:1.
        count: Number of images to generate (1–4). Default 1.
        negative_prompt: What to avoid in the image.

    Returns:
        File paths for each generated image, one per line.
    """
    from google.genai import types

    client = _client()
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
        p = _save(img.image.image_bytes, "gen")
        paths.append(str(p))

    if not paths:
        return "No images were generated. The prompt may have been blocked by Imagen's safety filters."

    return "Generated:\n" + "\n".join(paths)


@mcp.tool()
def edit_image(image_path: str, edit_prompt: str) -> str:
    """Edit an existing image with natural language instructions using Gemini 2.0 Flash.

    Args:
        image_path: Absolute path to the source image (PNG or JPEG).
        edit_prompt: Natural language description of the edit, e.g.
                     "make the background a sunset over the ocean" or
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
    suffix = src.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    client = _client()

    image_part = types.Part.from_bytes(data=raw, mime_type=mime)
    text_part = types.Part.from_text(text=edit_prompt)

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[types.Content(role="user", parts=[image_part, text_part])],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            p = _save(part.inline_data.data, "edit")
            return f"Edited image saved to: {p}"

    # Gemini returned text instead of an image
    text_parts = [
        p.text
        for p in response.candidates[0].content.parts
        if p.text
    ]
    reason = " ".join(text_parts) if text_parts else "unknown reason"
    return f"Edit produced no image. Model said: {reason}"


@mcp.tool()
async def batch_generate(
    prompts: list[str],
    aspect_ratio: str = "1:1",
) -> str:
    """Generate multiple images in parallel from a list of prompts using Imagen 3.

    Args:
        prompts: List of text prompts, one image per prompt (max 10).
        aspect_ratio: "1:1", "16:9", "9:16", "4:3", or "3:4". Default 1:1.

    Returns:
        Mapping of each prompt to its generated file path, one per line.
    """
    from google.genai import types

    if not prompts:
        return "No prompts provided."
    prompts = prompts[:10]

    client = _client()

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

    results = await asyncio.gather(*[_one(p, i) for i, p in enumerate(prompts)])
    results = sorted(results, key=lambda r: r[0])

    lines = [f"{r[1]!r} → {r[2]}" for r in results]
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
