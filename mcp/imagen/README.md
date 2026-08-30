# Imagen MCP Server

Photorealistic image generation and editing inside Claude Code. Default engine is
Google's **Nano Banana** (`gemini-2.5-flash-image`) — state-of-the-art photorealism plus
natural-language editing. Imagen 4, DALL-E 3, **Draw Things** (local Apple Silicon),
and **ComfyUI** (local) are available as opt-in alternatives.

Every tool renders the image inline in the chat and saves a copy to
`~/Pictures/kitty-gen/`, so the loop is: generate → look → "change X" → `edit_image`.

## What's new (P25 — local-first, fal retired)

- **Draw Things engine** (`engine="drawthings"`) — A1111-compatible API for local
  generation on Apple Silicon. Free, private, no API cost. Set `DT_URL` to point
  at your running instance (default `http://127.0.0.1:7860`).
- **`generate_until`** — verified generation loop: generate → score against criteria →
  keep best → stop early when one passes all hard gates. Scorers: `mechanical`
  (resolution, blank detection), `face_match` (InsightFace against reference images),
  `vision_rubric` (local VLM via Ollama). Every attempt logged to
  `~/Pictures/kitty-gen/runs/<run-id>/attempts.jsonl`.
- **`private=True` guard** — `generate_until` refuses cloud engines when `private=True`,
  enforcing local-only generation for personal creative work.
- **fal retired** — all `*_fal` tools removed. Git keeps the history. Local engines
  (Draw Things, ComfyUI) replace fal at a fraction of the per-image cost.
  See `docs/packets/025-imagegen-pipeline-v2.md`.

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

Drop keys you don't have — the server starts fine without them and only errors when
you call a tool that needs a missing key. `DT_URL` defaults to `http://127.0.0.1:7860`
if not set.

## Jacob's half — Draw Things setup (~30 min + downloads)

1. **Draw Things** (App Store, free) → Settings → enable **API Server**
   (`127.0.0.1:7860`, HTTP).
2. Pick a base checkpoint on Civitai (test-drive via free on-site generation first),
   download it + one photoreal merge + 2–3 anatomy LoRAs for that base. Import into
   Draw Things. Same files can be symlinked into ComfyUI's `models/` if using Comfy.
3. `ollama pull qwen2.5-vl:7b` (or the VLM of choice) for `vision_rubric` scorer.
4. Drop 8–12 approved reference images of a character into `config/imagen/faces/<name>/`
   for face-lock.
5. First verified run: write `config/imagen/criteria/<name>.json`, run
   `generate_until`, judge the survivors, tighten the rubric.

## Tools

**Core**

| Tool | Engine | Best for |
|------|--------|----------|
| `generate` | any (default nano_banana) | **Default.** Pass `engine="drawthings"` for local. |
| `edit_image` | nano_banana | Refine an existing image by sentence |
| `batch_generate` | any | N prompts in parallel |
| `generate_with_reference` | nano_banana | Keep a subject consistent; composite images |
| `refine_image` | nano_banana + vision | Auto generate → critique → edit loop |
| `variations` | nano_banana | "More like this one" — alternate pose/angle/lighting |
| `generate_until` | any | Verified loop — score against criteria, keep best |

**Engines (pass as `engine=` to `generate` or `batch_generate`)**

| Engine | Cost | NSFW | Best for |
|--------|------|------|----------|
| `nano_banana` (default) | Gemini API | Tasteful | Photorealism + editing |
| `drawthings` | $0 (local) | Full | Personal/private, Apple Silicon, no censorship |
| `comfyui` | $0 (local) | Full/explicit | Custom LoRAs, full NSFW |
| `imagen4` | Gemini API | Tasteful (adults) | 1–4 at once |
| `dalle` | OpenAI API | ✗ | Creative/illustrative, text-in-image |

**Persistent character**

| Tool | Best for |
|------|----------|
| `set_avatar` | Pin a reference image as a recurring character |
| `generate_with_avatar` | Drop that character into any new scene |
| `save_character` | Save a named character by photo + description |
| `generate_with_character` | Place a saved character by name in a scene |
| `generate_scene` | Two saved characters together |

**Utility**

| Tool | Best for |
|------|----------|
| `make_gallery` | Browsable HTML contact sheet of all outputs |
| `imagen_help` | This menu |

## The verified loop

`generate_until(prompt, criteria_name, engine, max_attempts=8, keep=3)`:

1. Generate → score against `config/imagen/criteria/<name>.json`
2. Scorers: `mechanical` (resolution, blank), `face_match` (InsightFace),
   `vision_rubric` (Ollama VLM)
3. If a candidate passes all hard gates → stop early
4. Otherwise, re-seed and try again (optionally rephrase prompt via local LLM)
5. Return best-N candidates sorted by total score
6. Every attempt logged to `~/Pictures/kitty-gen/runs/<run-id>/attempts.jsonl`

Set `private=True` to refuse cloud engines — for personal creative prompts.

## Face-lock

Reference-based identity locking via InsightFace. Place 8–12 approved images in
`config/imagen/faces/<character>/`. The `face_match` scorer gates every generation
against them. Threshold in the criteria file controls strictness.

For stronger consistency: train a character LoRA via Draw Things' on-device training
or Civitai's on-site trainer (runbooks only — no training code in v1).

## Criteria files

Located at `config/imagen/criteria/<name>.json`:

```json
{
  "face_match": { "character": "jace", "threshold": 0.6 },
  "rubric": [
    "anatomy is correct: no extra limbs or distorted proportions",
    "hands are anatomically correct",
    "no visible artifacts, seams, or glitches"
  ],
  "mechanical": { "min_width": 512, "min_height": 512 }
}
```

Rubric lines are soft by default. Add `"hard": true` to make a line a discard gate.

## Cost tiers

- **Tier 0 — free, local, private:** Draw Things on the Air (queue overnight;
  quantized SDXL runs on Apple Silicon), ComfyUI local for scriptable workflows.
- **Tier 1 — free, cloud, limited:** Civitai on-site (daily free Buzz) for trying
  checkpoints/LoRAs before downloading 6 GB.
- **Tier 2 — cheap, metered:** RunPod/Vast.ai spot GPU (~$0.20–0.40/hr) running
  A1111/Forge or ComfyUI. Set `DT_URL` to the pod.

## Cache

Identical `(prompt, engine, params)` calls hit a SHA256-keyed cache at
`~/Pictures/kitty-gen/.cache/`. Clear it:

```bash
rm -rf ~/Pictures/kitty-gen/.cache
```

```bash
IMAGEN_CACHE_ENABLED=0
```

## Model drift

Override without touching code:

```bash
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
DT_URL=http://192.168.1.50:7860
VISION_MODEL=llama-3.2-vision:11b
```
