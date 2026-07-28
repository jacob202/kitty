# Quantity Counting Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — counts up to 4-5 are reliable.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
SDXL Turbo handles counts better at quality tier (8+ steps, CFG ~4.5).
Beyond 5 objects, accuracy drops sharply — split into multiple generations.

## Prompt Structure

- State the **exact count first**: "Three apples," "Two chairs and one table."
  Never "some apples" or "a few chairs."
- **List items individually** when count matters: "One red apple, one green
  apple, one yellow apple on a wooden cutting board."
- Use **ordinal cues** as backup: "first... second... third..." helps the
  renderer separate instances.

## Grouping

- When counting similar objects, **group by attribute**: "Five glasses — two
  filled with water, three empty."
- For large counts, create **visual groupings**: "A cluster of seven roses
  in a vase" (the renderer sees "cluster" not "seven").
- Avoid "exactly N" — it's treated as a suggestion, not a constraint.

## Common Pitfalls

- Counts >5 are unreliable across all current renderers. Split the prompt.
- "A flock of birds" (vague) vs "Seven birds in flight" (specific but risky).
  Use the vague form when count accuracy isn't load-bearing.
- Identical objects without distinguishing attributes merge — give each a
  unique trait: color, position, size, or state.

---

Version: 1.0 — Kitty ComfyUI-tested, SDXL/SD3
Source: kitty/image_guidance/quantity_counting.md (adapted from GenEvolve)
