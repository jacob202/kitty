# Text Rendering Guidance

## Prompt Structure

- **Put text in quotes** and specify where it should appear:
  "A neon sign that reads 'OPEN' in the foreground."
- **State the text content twice** — once in the description and again as a
  standalone instruction: "The sign says 'OPEN'. The sign text: OPEN."

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

---

Version: 1.0
Source: kitty/image_guidance/text_rendering.md
