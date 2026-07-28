# Attribute Binding Guidance

## What It Is

Attribute binding means assigning the right properties to the right objects
so a "red ball and blue cube" renders as a red sphere and a blue box — not
a red cube or a purple blob.

## Prompt Structure

- Pair each object with its **modifiers immediately**: "a red rubber ball,"
  not "there is a ball and a cube, the ball is red and the cube is blue."
- **Order matters**: the first object in the prompt gets priority in the
  renderer's attention. Put the most important object first.
- Separate objects with **distinct identifiers**: "A polished wooden chair
  beside a glass-topped metal table."

## Multiple Similar Objects

- When objects share a type, make each **uniquely identifiable**: "A red
  umbrella folded in a gold stand, and a blue umbrella open on the floor."
- Count + color + material is the strongest binding: "Two ceramic mugs,
  one forest green with a chip on the rim, one matte black and pristine."

## Common Pitfalls

- "A red and blue ball and cube" — the adjectives bleed across all nouns.
- Long description chains (>4 attributes per object) lose binding accuracy.
- Color bleeding: a brightly colored foreground object bleeds into a neutral
  background. Counter with explicit background color.

---

Version: 1.0
Source: kitty/image_guidance/attribute_binding.md (adapted from GenEvolve)
