---
name: image-gen
description: Generate images via the local ComfyUI-backed image endpoint. Use when the user asks Kitty to generate, draw, create, or make an image or picture.
---

# Skill: image-gen

Generate images via `scripts/generate_image.py`, which checks ComfyUI
availability and submits the prompt to the gateway. Model/style keyword
routing ("portrait", "sdxl", "explicit", etc.) happens server-side in
`gateway/image_gen.py` — pass the user's description straight through.

## When to use
User asks Kitty to generate, draw, create, or make an image or picture.

## Run

```bash
python3.12 scripts/generate_image.py "<the user's description>"
```

Prints the output filename on success, or the reason it failed
(ComfyUI not running, timeout, etc.) on stderr.

## Timing
Generation takes 2–5 minutes on M1 and the script blocks until done — tell
the user upfront so they don't think it's stuck.
