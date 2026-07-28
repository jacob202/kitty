# Creative Drawing Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — strongest at stylistic range.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
Draw Things: supported through loaded checkpoints; style fidelity depends on
the checkpoint's training data (anime checkpoints don't do oil painting).

## Opening

- Describe the **artistic medium and style** first: "A pencil sketch," "An oil painting," "A vector illustration."
- Name a specific **art movement or style** if you have one: "Art Nouveau," "Ukiyo-e," "synthwave."

## Composition

- Creative prompts benefit from **mood words**: "ethereal," "gritty," "dreamlike," "vibrant."
- One strong **focal point** with supporting detail: "A towering crystal spire dominates the scene, with tiny figures at its base for scale."

## Palette

- Specify a **color palette** with three terms: "warm amber, teal, and cream."
- **Light quality**: "golden hour," "neon-lit," "moonlight," "overcast."

## Common Pitfalls

- "Beautiful" and "stunning" add no information — the renderer doesn't know what you find beautiful.
- Over-specifying every detail crowds the prompt and dilutes the focal point.
- Skipping medium/style defaults to photorealistic, which may not match your intent.

---

Version: 1.0
Source: kitty/image_guidance/creative_drawing.md (adapted from GenEvolve)
