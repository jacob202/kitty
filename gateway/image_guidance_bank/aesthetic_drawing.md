# Aesthetic Drawing Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — style words have strong effect.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
SD3 responds better to art-movement names (Art Nouveau, Bauhaus); SDXL Turbo
responds better to material/technique words (watercolour, charcoal).

## Opening

- Lead with **style + medium**: "A watercolour illustration of..." or "A charcoal sketch of..."
- Name an **artist or movement** as a shortcut: "in the style of Monet,"
  "Art Deco poster," "cyberpunk anime."
- Combine two styles for novelty: "Bauhaus architecture rendered as a children's book illustration."

## Emotional Tone

- Use **mood words** to guide the renderer's color and lighting choices:
  "melancholic," "joyful," "ominous," "serene."
- Pair mood with **light quality**: "warm golden light" for cosy, "cold blue neon" for dystopian.

## Detail Level

- Specify **level of detail** explicitly: "highly detailed," "minimalist line art,"
  "loose and expressive brushwork."
- "Illustration" → flat, stylised. "Photorealistic" → sharp, realistic. Nothing said → renderer default.

## Common Pitfalls

- "Beautiful" and "stunning" are noise — the renderer doesn't know your taste.
- Artist names as style shortcuts work on SD3 but may be ignored on Draw Things
  depending on the checkpoint.
- Mixing >3 style descriptors dilutes all of them. Pick one primary style, one mood, one light.

---

Version: 1.0 — Kitty ComfyUI-tested, SDXL/SD3
Source: kitty/image_guidance/aesthetic_drawing.md (adapted from GenEvolve)
