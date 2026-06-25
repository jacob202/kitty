"""Imagen MCP server — photorealistic image generation and editing for Claude Code.

Default engine is Google's "Nano Banana" (gemini-2.5-flash-image), which does both
generation and natural-language editing with strong photorealism. Imagen 4, DALL-E 3,
and local ComfyUI are available as opt-in alternatives.

Every tool returns the image inline (it renders directly in the chat) AND saves a
copy to ~/Pictures/kitty-gen/ so you can pass the path back to edit_image to refine it.

PR 3: the 4 legacy generate_image* tools are collapsed into one ``generate(prompt,
engine=...)`` + ``batch_generate(prompts, engine=...)``. A SHA256 cache deduplicates
identical (prompt, engine, params) calls. All engine calls retry with exponential
backoff so 429s recover.

Tools:
  generate              — unified generation (engine: nano_banana | imagen4 | dalle | comfyui)
  edit_image            — natural-language edits (Nano Banana)
  batch_generate        — N prompts in parallel (asyncio.gather)
  generate_with_reference — keep a subject consistent / composite images
  refine_image          — auto loop: generate → vision-critique → edit until it matches
  variations            — several alternates of an existing image
  set_avatar / generate_with_avatar — a persistent character you can drop into scenes
  make_gallery          — HTML contact sheet of everything generated
"""

from __future__ import annotations

from mcp.imagen import engines
from mcp.imagen.logging import log
from mcp.imagen.tools.batch import batch_generate
from mcp.imagen.tools.gallery import make_gallery
from mcp.imagen.tools.generate import edit_image, generate
from mcp.imagen.tools.reference import (
    generate_with_avatar,
    generate_with_reference,
    set_avatar,
)
from mcp.imagen.tools.refine import refine_image
from mcp.imagen.tools.variations import variations
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "imagen",
    instructions=(
        "Generate and edit photorealistic images. Default to generate (Nano Banana) "
        "for new images and edit_image to refine them — both render inline and save to "
        "~/Pictures/kitty-gen/. Pass the engine name to generate() to switch backends: "
        "nano_banana (default, best photorealism), imagen4 (1-4 at once), dalle "
        "(creative/text-in-image), comfyui (local, full NSFW). batch_generate runs N "
        "prompts in parallel. The generate→look→edit loop is the intended workflow: "
        "make an image, the user reacts, call edit_image with their change. "
        "To keep a subject consistent or composite images, use generate_with_reference. "
        "set_avatar pins a recurring character for generate_with_avatar. refine_image "
        "runs the generate→critique→edit loop automatically. variations makes alternates, "
        "make_gallery builds a browsable contact sheet."
    ),
)

# Register all tools on the FastMCP instance. Each function is decorated here
# (not in the tool modules) so the tool modules stay testable without a live
# FastMCP server.
mcp.tool()(generate)
mcp.tool()(edit_image)
mcp.tool()(batch_generate)
mcp.tool()(refine_image)
mcp.tool()(variations)
mcp.tool()(generate_with_reference)
mcp.tool()(set_avatar)
mcp.tool()(generate_with_avatar)
mcp.tool()(make_gallery)

log.debug("imagen MCP server ready — engines: %s", ", ".join(engines.available()))


if __name__ == "__main__":
    mcp.run()
