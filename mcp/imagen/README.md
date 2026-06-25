# Imagen MCP Server

Photorealistic image generation and editing inside Claude Code. Default engine is
Google's **Nano Banana** (`gemini-2.5-flash-image`) — state-of-the-art photorealism plus
natural-language editing. Imagen 4, DALL-E 3, and local ComfyUI are opt-in alternatives.

Every tool **renders the image inline in the chat** and saves a copy to
`~/Pictures/kitty-gen/`, so the loop is: generate → look → "change X" → `edit_image`.

## Setup

```bash
cd mcp/imagen
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Add to Claude Code (`~/.claude/settings.json`)

```json
{
  "mcpServers": {
    "imagen": {
      "command": "/Users/jacobbrizinski/Projects/kitty/mcp/imagen/.venv/bin/python",
      "args": ["/Users/jacobbrizinski/Projects/kitty/mcp/imagen/server.py"],
      "env": {
        "GEMINI_API_KEY": "your-gemini-key",
        "OPENAI_API_KEY": "your-openai-key"
      }
    }
  }
}
```

Drop a key from `env` if it's already exported in your shell. Restart Claude Code, then
just ask: *"generate a photo of a misty harbor at dawn"* or *"edit that — make it night."*

## Tools

**Core**

| Tool | Engine | NSFW | Best for |
|---|---|---|---|
| `generate_image` | Nano Banana | Tasteful | **Default.** Photorealism. |
| `edit_image` | Nano Banana | Tasteful | Refining an existing image by sentence |
| `generate_with_reference` | Nano Banana | Tasteful | Keep a subject consistent across scenes; composite multiple images |
| `refine_image` | Nano Banana + vision | Tasteful | Autonomous generate → critique → edit until it matches |
| `variations` | Nano Banana | Tasteful | "More like this one" — alternate pose/angle/lighting |

**Persistent character**

| Tool | Best for |
|---|---|
| `set_avatar` | Pin a reference image as a recurring character |
| `generate_with_avatar` | Drop that character into any new scene |

**Alternate engines & utilities**

| Tool | Engine | NSFW | Best for |
|---|---|---|---|
| `generate_image_imagen` | Imagen 4 | Tasteful (adults) | 1–4 variations in one call |
| `generate_image_dalle` | DALL-E 3 | ✗ | Creative/illustrative, text-in-image |
| `generate_image_comfy` | ComfyUI (local) | Full/explicit | Explicit NSFW, custom LoRAs, $0 |
| `make_gallery` | — | — | Browsable HTML contact sheet of all outputs |

### The standout: consistency & compositing

`generate_with_reference` is the capability DALL-E and Imagen can't match:

- **One reference** → same subject, new scene: *"the person in this photo, now on a Tokyo street at night"*
- **Multiple references** → composite: *"put the person from image 1 in the room from image 2"*, *"dress the model in image 1 in the outfit from image 2"*

`set_avatar` + `generate_with_avatar` turn that into a persistent character you place into scenes without re-uploading each time.

### The autonomous loop

`refine_image(prompt, target, max_rounds)` generates, then a vision model critiques the
result against `target` and either approves it or returns one concrete edit — applied and
re-checked until it matches or rounds run out. You get the final image plus the critique trail.

## Photorealism

`generate_image` has `photorealistic=True` by default, which appends photographic cues
(DSLR, 85mm lens, natural lighting, depth of field) to your prompt. Set it `False` for
illustrations, paintings, or cartoons.

## Model drift

Image model names move fast. Override without touching code:

```bash
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
IMAGEN_MODEL=imagen-4.0-ultra-generate-001
```

## ComfyUI prompt keywords

`realistic`/`photo`/`sdxl`/`photonic` → SDXL · `explicit`/`erect`/`cock` → explicit LoRA ·
`portrait`/`landscape` → aspect · `detailed` → more steps · `more bear`/`less bear` → LoRA strength
