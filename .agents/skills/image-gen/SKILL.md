# Skill: image-gen

Generate images via ComfyUI running locally at port 8188.

## When to use
User asks Kitty to generate, draw, create, or make an image or picture.

## Check availability first
GET /image/status → {"available": true/false}
If false, tell the user ComfyUI isn't running and they should start it.

## Generate
POST /image/generate
Body: {"prompt": "<the user's description>"}

Returns: {"filename": "Kitty_00001_.png", "path": "/full/path/to/file", "prompt_id": "..."}

The output file lands in ComfyUI's output folder.
Tell the user the filename and that it's ready in the ComfyUI output folder.

## Model behavior
- Default (SD1.5): homofidelis_v50 + bear LoRA. Good for character art.
- Keywords that trigger SDXL (photonicFusionSDXL): "realistic", "photo", "photonic", "sdxl"
- Keywords that add explicit LoRA: "explicit", "erect", "cock", "nude explicit"
- Orientation: add "portrait" or "landscape"
- Speed: add "fast" (fewer steps) or "detailed" (more steps)

## Timing
Generation takes 2–5 minutes on M1. Tell the user upfront so they don't think it's stuck.
