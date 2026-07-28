# Spatial Layout Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — tested and effective.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
Draw Things compatibility unknown — its A1111 adapter may parse
positioning differently.

## Composition

- Describe the **overall scene structure** before listing objects.
- Use explicit positioning: "centered," "top-left," "foreground,"
  "background," "to the left of," "below."
- If multiple subjects, specify their **relative positions**:
  "A cat in the foreground left, a dog in the background right."

## Camera & Framing

- Specify **camera angle** when relevant: "bird's-eye view,"
  "low angle looking up," "eye-level."
- Declare **framing**: "full-body," "head-and-shoulders portrait,"
  "wide establishing shot."

## Depth and Scale

- Add **depth cues**: "shallow depth of field,"
  "foreground elements sharp, background blurred."
- Specify **relative scale**: "the character fills one-third of the frame."

## Common Pitfalls

- Vague placement leads to center-weighted composition.
- Multiple characters without relative positions often overlap.
- Background described before foreground confuses renderer depth.

---

Version: 1.0 — Kitty ComfyUI-tested
Source: kitty/image_guidance/spatial_layout.md
