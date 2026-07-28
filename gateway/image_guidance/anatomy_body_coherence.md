# Anatomy & Body Coherence Guidance

**Renderer:** ComfyUI (SDXL Turbo / SD3) — anatomy improves with more steps.
**Model:** `kitty-default` routes through `image_recipes.auto_route()`.
Use `quality` tier (8+ steps, CFG ~4.5) for character work — `speed` tier
(6 steps, CFG ~1.5) produces anatomy that's fast but less coherent.
Draw Things: SD1.5-based checkpoints have worse hands/faces; SDXL-based are better.

## Proportions

- Specify **body proportions** explicitly when they matter: "tall and slender,"
  "muscular and broad-shouldered," "child proportions, large head relative
  to body."
- For realistic anatomy, include **landmark terms**: "well-defined collarbone,"
  "visible knuckles," "defined jawline."

## Hands & Faces

- Hands are the most common failure point. **Describe what hands are doing**:
  "hands resting on lap," "right hand holding a cup, left hand at side."
  A hand with no task often renders as a blob.
- Faces benefit from **asymmetry cues**: "slight smile, tilted head, one
  eyebrow raised." Perfect symmetry reads as uncanny.

## Multiple Characters

- Each character gets their own **pose + relation** sentence: "Figure A sits
  cross-legged on the floor, looking up. Figure B stands behind them, arms
  folded."
- Specify **relative height** and **distance**: "Figure A is shorter, about
  shoulder-height to Figure B."

## Common Pitfalls

- "A person" with no posture, clothing, or action spec → generic rendered
  figure with unpredictable anatomy.
- Too many fingers, merged limbs, floating body parts — the renderer didn't
  understand spatial separation. Add explicit spacing words: "spread fingers,"
  "arms at sides with space between body and elbows."
- Profile/side views often lose one eye or ear — specify "visible in profile,
  one eye visible" when shooting from side.

---

Version: 1.0
Source: kitty/image_guidance/anatomy_body_coherence.md (adapted from GenEvolve)
