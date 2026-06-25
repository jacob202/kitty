# Imagen MCP Server

Generate and edit photorealistic images inside Claude Code using Gemini Imagen 3.

## Setup

```bash
cd mcp/imagen
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Add to Claude Code

Add this block to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "imagen": {
      "command": "/path/to/kitty/mcp/imagen/.venv/bin/python",
      "args": ["/path/to/kitty/mcp/imagen/server.py"],
      "env": {
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

Replace `/path/to/kitty` with the real path (e.g. `/Users/jacobbrizinski/Projects/kitty`).

If `GEMINI_API_KEY` is already in your shell environment, you can omit the `env` block.

## Tools

| Tool | Description |
|---|---|
| `generate_image(prompt, aspect_ratio, count, negative_prompt)` | Text → image(s) via Imagen 3 |
| `edit_image(image_path, edit_prompt)` | Edit an existing image via Gemini 2.0 Flash |
| `batch_generate(prompts, aspect_ratio)` | Multiple prompts in parallel |

All images are saved to `~/Pictures/kitty-gen/`.

## Aspect ratios

`1:1` · `16:9` · `9:16` · `4:3` · `3:4`
