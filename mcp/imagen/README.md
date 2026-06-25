# Imagen MCP Server

Generate and edit images inside Claude Code with three backends.

## Setup

```bash
cd mcp/imagen
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Add to Claude Code (`~/.claude/settings.json`)

```json
{
  "mcpServers": {
    "imagen": {
      "command": "/Users/jacobbrizinski/Projects/kitty/mcp/imagen/.venv/bin/python",
      "args": ["/Users/jacobbrizinski/Projects/kitty/mcp/imagen/server.py"],
      "env": {
        "GEMINI_API_KEY": "your-gemini-key",
        "OPENAI_API_KEY": "your-openai-key"
      }
    }
  }
}
```

Drop keys from `env` if they're already in your shell profile. `COMFY_URL` defaults to `http://127.0.0.1:8188`.

## Tools

| Tool | Backend | NSFW | Notes |
|---|---|---|---|
| `generate_image` | Gemini Imagen 3 | Tasteful ✓ | Best photorealism |
| `edit_image` | Gemini 2.0 Flash | Tasteful ✓ | Natural-language edits to existing images |
| `batch_generate` | Gemini Imagen 3 | Tasteful ✓ | Up to 10 prompts in parallel |
| `generate_image_dalle` | DALL-E 3 | ✗ | Best at complex/creative prompts, text in images |
| `generate_image_comfy` | ComfyUI (local) | Full ✓ | Needs ComfyUI running; explicit LoRA built in |

All images saved to `~/Pictures/kitty-gen/`.

## ComfyUI prompt keywords

- `realistic` / `photo` / `sdxl` / `photonic` → SDXL model
- `explicit` / `erect` / `cock` etc → explicit LoRA
- `portrait` / `landscape` → aspect ratio
- `detailed` → more steps
- `more bear` / `less bear` → bear LoRA strength
