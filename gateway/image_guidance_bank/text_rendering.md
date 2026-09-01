# Text Rendering Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — renders text, not always accurate.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
Draw Things: text quality depends on the loaded checkpoint (SD1.5-based checkpoints
rarely produce legible text; SDXL-based ones are better).

## Prompt Structure

- **Put text in quotes** and specify where it should appear:
  "A neon sign that reads 'OPEN' in the foreground."
- **State the text content twice** — once in the description and again as a
  standalone instruction: "The sign says 'OPEN'. The sign text: OPEN."
- For short words (<8 chars), spell letter-by-letter:
  "The word CAT spelled out: C A T."

## Font & Style

- Specify **font characteristics** explicitly: "bold serif font,"
  "handwritten script," "clean sans-serif."
- Include **size and color**: "large red letters," "small black text."
- For stylised text, describe the **material**: "carved stone lettering,"
  "metallic embossed," "painted wood."

## Placement

- Anchor text to a surface or object: "text on the wall," "label on the product."
- Specify **alignment**: "centered," "left-aligned," "stacked vertically."

## Common Pitfalls

- Text without quotes is often ignored or hallucinated as garbled shapes.
- Text size unspecified → renderer defaults to tiny or disproportionate.
- Multiple text elements without distinct placement → merge or overlap.
- Long phrases (>15 chars) are unreliable — split into multiple prompts or
  use short, distinct labels.

---

Version: 1.0 — Kitty ComfyUI-tested, SDXL-based
Source: kitty/image_guidance/text_rendering.md (adapted from GenEvolve)
