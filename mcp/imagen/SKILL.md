# imagen MCP — Agent Skill

## When to use this server

Use the `imagen` MCP server when the user asks for image generation, photo
editing, or character-consistent scenes. It exposes four engines, each with
different strengths. The default is **nano_banana** (Google's
gemini-2.5-flash-image) — strongest photorealism and natural-language
editing.

Skip this server for: diagrams/charts (use a different tool), image
analysis (no `analyze_image` tool here — describe what the user wants and
suggest they re-photograph), or batch processing of >10 images
(workflows above 10 should be scripted separately).

## Tool catalog

| Tool | When to use |
|---|---|
| `generate_image` | Default. Photorealistic new image from a text prompt. Returns inline + saves. |
| `edit_image` | Natural-language edit of an existing image. Pass the saved path. |
| `generate_with_reference` | Keep a subject consistent OR composite 1-3 reference images. |
| `refine_image` | Auto loop: generate → vision-critique → edit up to 5 rounds. |
| `variations` | 1-4 alternate angles of an existing image. |
| `set_avatar` | Pin a character image as the persistent avatar. |
| `generate_with_avatar` | Place the avatar in a new scene. |
| `generate_image_imagen` | Imagen 4: 1-4 variations in one call. |
| `generate_image_dalle` | DALL-E 3: creative, text-in-image, illustration. |
| `generate_image_comfy` | Local ComfyUI: full NSFW, $0, needs ComfyUI running. |
| `make_gallery` | Build HTML contact sheet of every image in `~/Pictures/kitty-gen/`. |
| `read_image_metadata` | Read the sidecar JSON for an image. |
| `read_manifest` | Query the manifest, filter by engine and `since` (epoch seconds). |
| `regenerate` | Re-run a generation from saved metadata. Same seed, same prompt. |
| `open_in_viewer` | macOS: open the file in Preview.app. |

## Default engine: nano_banana

Use `generate_image` for new work. Reasons:
- Best photorealism of the four (DSLR, 85mm, natural lighting cues appended).
- Natural-language editing built in (no mask needed; pass the path + a sentence).
- Subject consistency via `generate_with_reference` is a standout capability the other engines lack.
- Cost-effective at low volume.

Switch away from nano_banana when the user explicitly asks for:
- A batch of 1-4 variations of the same prompt → `generate_image_imagen`.
- A text-heavy or illustration-style image → `generate_image_dalle`.
- An explicit-NSFW image, or one that must run fully local with no API cost → `generate_image_comfy`.

## Engine routing

- **nano_banana** (default) — photorealism, edits, character consistency. Aspect: `aspect_ratio` string (`"1:1"`, `"9:16"`, `"21:9"`, etc.) or alias (see below).
- **imagen4** — 1-4 variations in one call. Aspect: `aspect_ratio` string. Not NSFW-explicit.
- **dalle** — illustrations, text-in-image, strong instruction-following. Aspect: `size` (`"1024x1024"`, `"1024x1792"`, `"1792x1024"`). Not NSFW.
- **comfyui** — explicit NSFW, fully local, $0. Aspect: parsed from prompt keywords (`portrait`/`landscape`) or default square.

### Aspect aliases

Stable names that resolve per engine:

- `cinemascope` → 21:9 / 16:9 / 1792x768 / (1536, 640)
- `widescreen` → 16:9 / 16:9 / 1792x1024 / (1280, 720)
- `portrait_phone` → 9:16 / 9:16 / 1024x1792 / (576, 1024)
- `portrait_classic` → 2:3 / 3:4 / 1024x1792 / (832, 1216)
- `landscape_classic` → 3:2 / 4:3 / 1792x1024 / (1216, 832)
- `instagram_square` → 1:1 / 1:1 / 1024x1024 / (1024, 1024)
- `photo_35mm` → 3:2 / 3:2 / _not supported by DALL-E_ / (1500, 1000)

Power users can pass engine-native values directly (`"21:9"`,
`"1024x1024"`, `(1024, 1024)`) — they're passed through unchanged.

## Workflow recipes

**Quick gen:**
```python
generate_image("a harbor at dawn, fog on the water", aspect="cinemascope")
```

**Refine:** generate → look at it → `edit_image(path, "make it night")` → repeat.

**Batch:** `generate_image_imagen("a serene mountain cabin", count=4)` for 4 alternates in one call.

**Character:** `set_avatar(photo_path)` once, then `generate_with_avatar("at a Paris cafe, golden hour")` for any new scene with the same character.

**Find old work:** `read_manifest(since=hours_ago_epoch)` returns recent generations, newest first.

**Reproducible re-roll:** `regenerate(path)` re-runs the saved prompt + params. ComfyUI is the only engine with deterministic seeds.

## Common mistakes to avoid

- Don't call `generate_image_imagen` when you want a single new image — use `generate_image` (nano_banana is faster, cheaper, and more photorealistic for single shots).
- Don't pass `seed` to DALL-E or Imagen 4 — they don't support it. Pass it to ComfyUI for reproducibility.
- Don't pass `size` to nano_banana — use `aspect_ratio` (or an alias).
- Don't try to read metadata for a file that doesn't have a sidecar — `read_image_metadata` will return a string message; render it to the user.
- Don't delete the manifest file — it's the fast-query index. Each sidecar is the source of truth, but reading 100 sidecars is slow.
- Don't open the same image with `open_in_viewer` repeatedly on macOS — `open` is non-blocking, so duplicates will pile up in Preview.
