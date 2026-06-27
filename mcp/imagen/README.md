# Imagen MCP Server

Photorealistic image generation and editing inside Claude Code. Default engine is
Google's **Nano Banana** (`gemini-2.5-flash-image`) — state-of-the-art photorealism plus
natural-language editing. Imagen 4, DALL-E 3, and local ComfyUI are opt-in alternatives.

Every tool **renders the image inline in the chat** and saves a copy to
`~/Pictures/kitty-gen/`, so the loop is: generate → look → "change X" → `edit_image`.

## What's new (PR 3)

- **Unified `generate`** — one tool replaces `generate_image`, `generate_image_imagen`,
  `generate_image_dalle`, `generate_image_comfy`. Pass `engine="nano_banana"` (default),
  `"imagen4"`, `"dalle"`, or `"comfyui"`.
- **`batch_generate`** — N prompts in parallel via `asyncio.gather`. 10x speedup for
  "generate these three scenes: a, b, c". Concurrency-limited (default 10) with a
  semaphore to avoid rate-limiting.
- **SHA256 cache** — identical `(prompt, engine, params)` calls return the cached path
  instantly. Cache lives at `~/Pictures/kitty-gen/.cache/`. Clear it with
  `rm -rf ~/Pictures/kitty-gen/.cache`.
- **Retry with backoff** — all engine calls wrap in tenacity (3 attempts, exponential
  backoff 1–10s). A single 429 from Gemini no longer fails the whole call.
- **Structured refusals** — when a safety filter blocks a prompt, the tool returns
  `{"blocked": True, "reason": "..."}` so the LLM can rephrase programmatically.

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
        "FAL_KEY": "your-fal-key",
        "GEMINI_API_KEY": "your-gemini-key",
        "OPENAI_API_KEY": "your-openai-key"
      }
    }
  }
}
```

Only `FAL_KEY` is required to use `generate_image_fal` and `generate_with_face_fal`.
Drop keys you don't have — the server starts fine without them and only errors when
you call a tool that needs a missing key.

Drop a key from `env` if it's already exported in your shell. Restart Claude Code, then
just ask: *"generate a photo of a misty harbor at dawn"* or *"edit that — make it night."*

## Tools

**Core**

| Tool | Engine | NSFW | Best for |
|---|---|---|---|
| `generate` | nano_banana (default) | Tasteful | **Default.** Photorealism. Pass `engine=` to switch. |
| `edit_image` | nano_banana | Tasteful | Refining an existing image by sentence |
| `batch_generate` | any | varies | N prompts in parallel |
| `generate_with_reference` | nano_banana | Tasteful | Keep a subject consistent; composite images |
| `refine_image` | nano_banana + vision | Tasteful | Autonomous generate → critique → edit loop |
| `variations` | nano_banana | Tasteful | "More like this one" — alternate pose/angle/lighting |

**Persistent character**

| Tool | Best for |
|---|---|
| `set_avatar` | Pin a reference image as a recurring character |
| `generate_with_avatar` | Drop that character into any new scene |

**Engines (pass as `engine=` to `generate` or `batch_generate`)**

| Tool | Engine | NSFW | Best for |
|---|---|---|---|
| `generate_image_fal` | fal.ai FLUX Pro Ultra | Permissive (tol 1–6) | High quality, looser safety than Gemini |
| `generate_with_face_fal` | fal.ai PuLID | Permissive | **Face-consistent** — same person in new scenes |
| `edit_image_fal` | fal.ai FLUX Pro Ultra img2img | Permissive | Edit a generated image by describing the change |
| `generate_image_imagen` | Imagen 4 | Tasteful (adults) | 1–4 variations in one call |
| `generate_image_dalle` | DALL-E 3 | ✗ | Creative/illustrative, text-in-image |
| `generate_image_comfy` | ComfyUI (local) | Full/explicit | Explicit NSFW, custom LoRAs, $0 |
| `make_gallery` | — | — | Browsable HTML contact sheet of all outputs |
| Engine | NSFW | Best for |
|---|---|---|
| `nano_banana` (default) | Tasteful | Photorealism + editing + reference consistency |
| `imagen4` | Tasteful (adults) | High-fidelity alternative |
| `dalle` | ✗ | Creative/illustrative, text-in-image |
| `comfyui` | Full/explicit | Explicit NSFW, custom LoRAs, $0 (needs ComfyUI running) |

| Utility | Best for |
|---|---|
| `make_gallery` | Browsable HTML contact sheet of all outputs |

### The standout: consistency & compositing

`generate_with_reference` is the capability DALL-E and Imagen can't match:

- **One reference** → same subject, new scene: *"the person in this photo, now on a Tokyo street at night"*
- **Multiple references** → composite: *"put the person from image 1 in the room from image 2"*, *"dress the model in image 1 in the outfit from image 2"*

`set_avatar` + `generate_with_avatar` turn that into a persistent character you place into scenes without re-uploading each time.

### The autonomous loop

`refine_image(prompt, target, max_rounds)` generates, then a vision model critiques the
result against `target` and either approves it or returns one concrete edit — applied and
re-checked until it matches or rounds run out. You get the final image plus the critique trail.

### Batch generation

`batch_generate(["prompt a", "prompt b", "prompt c"], engine="nano_banana")` fires all
three concurrently. Individual failures surface as error strings in the result list; the
batch continues. Concurrency is limited to 10 by default (override with
`concurrency_limit=`).

## Photorealism

`generate` has `photorealistic=True` by default, which appends photographic cues
(DSLR, 85mm lens, natural lighting, depth of field) to your prompt. Set it `False` for
illustrations, paintings, or cartoons.

## Cache

Identical `(prompt, engine, params)` calls hit a SHA256-keyed cache at
`~/Pictures/kitty-gen/.cache/`. The cache key includes `model_name` so engine version
changes implicitly invalidate. Clear it:

```bash
rm -rf ~/Pictures/kitty-gen/.cache
```

Disable it entirely:

```bash
IMAGEN_CACHE_ENABLED=0
```

## Model drift

Image model names move fast. Override without touching code:

```bash
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
IMAGEN_MODEL=imagen-4.0-ultra-generate-001
```

## ComfyUI prompt keywords

`realistic`/`photo`/`sdxl`/`photonic` → SDXL · `explicit`/`erect`/`cock` → explicit LoRA ·
`portrait`/`landscape` → aspect · `detailed` → more steps · `more bear`/`less bear` → LoRA strength
