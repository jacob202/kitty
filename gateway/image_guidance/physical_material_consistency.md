# Physical Material Consistency Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — material words parsed reliably.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
SDXL Turbo produces more consistent materials at low step counts; SD3 at
higher steps may blend materials (glass + metal → ambiguous shiny surface).

## Prompt Structure

- Pair every object with its **material**: "a wooden table," "a glass vase,"
  "a brushed steel lamp." Never say "a table" if the material matters.
- Use **compound material descriptors** for realism: "weathered oak," "frosted glass,"
  "polished brass," "rough-hewn stone."
- Contrast materials for visual interest: "a smooth marble countertop beside
  a rough brick wall."

## Surface Properties

- Specify **reflectivity**: "matte," "glossy," "metallic," "translucent."
- Describe **texture**: "rough," "smooth," "grainy," "porous," "cracked."
- For liquids: "still water" vs "rippling water," "thick syrup" vs "thin tea."

## Common Pitfalls

- "A table" with no material → renderer picks a generic brown surface.
- Two objects of the same material may merge visually — add a texture or
  color distinction: "a polished oak chair beside a rough oak stump."
- Translucent materials (glass, ice) without a background behind them
  render as empty space.

---

Version: 1.0 — Kitty ComfyUI-tested, SDXL/SD3
Source: kitty/image_guidance/physical_material_consistency.md (adapted from GenEvolve)
