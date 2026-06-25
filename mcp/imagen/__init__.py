"""Imagen MCP — photorealistic image generation and editing for Claude Code.

Package structure (PR 2 + PR 3):
  config.py    — settings, constants, model names
  logging.py   — structured logger
  io.py        — save_image, image-part helpers, response parsing
  cache.py     — SHA256-keyed cache for identical (prompt, engine, params)
  retry.py     — tenacity decorator with exponential backoff
  engines/     — nano_banana, imagen4, dalle, comfyui (+ registry)
  tools/       — generate, edit_image, batch_generate, refine, variations, ...
  server.py    — FastMCP app + tool wiring
"""
