# Kitty

Jacob's local-first AI companion. Starts cleanly, captures thoughts quickly, resurfaces them, keeps your data on your machine.

## What it is

A FastAPI gateway (`gateway/`) wired to a LiteLLM proxy for model routing, with a Next.js chat UI (`gateway/kitty-chat/`). All storage is local: SQLite for structured data, ChromaDB for semantic search, JSONL for journals and logs. An MCP server (`mcp/imagen/`) handles image generation via multiple engines.

The core loop: you talk to Kitty → it writes to storage → `memory_graph` resurfaces relevant context in future turns.

## Stack

| Layer | What |
|---|---|
| Gateway | `gateway/` — FastAPI, Python 3.12 |
| UI | `gateway/kitty-chat/` — Next.js, TypeScript |
| Model routing | LiteLLM proxy (`gateway/llm_client.py`) |
| Storage | SQLite + ChromaDB + JSONL under `data/` |
| MCP | `mcp/imagen/` — image generation (Imagen 4, DALL-E 3, ComfyUI) |
| Runtime data | `data/` |
| Logs | `logs/` |

## Quick start

```bash
./kitty up          # start the stack
./kitty status      # health check
./kitty doctor --json
```

## Where to read

Start at [`START_HERE.md`](START_HERE.md) — it gives you the right reading order and current status. For a tagged index of all docs, see [`docs/README.md`](docs/README.md).

## Tests

```bash
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test
```

## Phase status

Phase B (SQLite migration, storage router, plugin registry) is shipped. Phase C (journal migration) is complete. Current focus is daily-use reliability — not new features.
