# Kitty — live stack (canonical)

This file describes the **current** runnable Kitty brain and how Open WebUI (and other clients) attach to it. Ports and URLs below are taken from **`kitty_gateway/start_gateway.sh`**, **`kitty_gateway/start_litellm.sh`**, and the `wait_http` checks in **`kitty_gateway/start_all.sh`** — not from memory.

## Processes

| Role | Default host:port | Health check (from `start_all.sh`) |
|------|-------------------|--------------------------------------|
| Kitty Gateway (FastAPI) | `127.0.0.1:5001` | `http://127.0.0.1:5001/health` |
| LiteLLM proxy | `127.0.0.1:8001` | `http://127.0.0.1:8001/health` (with LiteLLM auth header) |
| Open WebUI | `127.0.0.1:3000` | `http://127.0.0.1:3000/health` |

Overrides:

- Gateway: `GATEWAY_HOST`, `GATEWAY_PORT` in `gateway/start_gateway.sh` (defaults `127.0.0.1`, `5001`).
- LiteLLM: `LITELLM_HOST`, `LITELLM_PORT` in `kitty_gateway/start_litellm.sh` (defaults `127.0.0.1`, `8001`).

Launch entrypoint for the full stack: **`kitty_gateway/start_all.sh`** (also invoked via `./kitty` — see `kitty` script for `KITTY_PORT`).

**Portability:** Several `kitty_gateway/*.sh` files set `ROOT_DIR` to a fixed path for this checkout. If you clone or move the repo, search for `ROOT_DIR=` in `kitty_gateway/` and align it with your tree before trusting the launchers.

## Supported clients

- **Open WebUI** — primary UI; chat hits LiteLLM, which can target the gateway for enriched flows per `kitty_gateway/litellm_config.yaml`.
- **Any other UI or script** — same HTTP surface as the gateway (e.g. `POST /v1/chat/completions`, `POST /ask`) against the gateway base URL.

## Python package layout

- **`gateway/`** — Kitty application code (FastAPI app, context builder, knowledge pipeline, memory, etc.). For chat prompts, use **`await context_builder.get_system_prompt()`** (or **`await knowledge.search()`** for chunks). The sync helper **`knowledge.get_knowledge_block()`** is for offline scripts/tests only — it returns `""` if called while an event loop is already running.
- **`contracts/`** — Shared Pydantic shapes (e.g. knowledge pipeline).
- **`scripts/`** — CLIs; **`scripts/kitty_manage.py`** owns KB ingest/status/prune.
- **`archive/`** — Legacy / historical trees; **not** part of the runtime import graph. See `archive/README.md`.

## Verification

After code changes:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```

(Use the project venv interpreter if that is your standard.)

## Rebuilding the knowledge index (derived data)

The vector index is **derived**; sources live under your chosen ingest roots (e.g. `data/knowledge/` — see `gateway/paths.py` `KNOWLEDGE_DIR`).

From the repo root:

```bash
make rebuild-index
```

Equivalent:

```bash
./venv/bin/python scripts/kitty_manage.py ingest data/knowledge
```

Adjust the path to match where your source documents live. Use **`scripts/kitty_manage.py --help`** and the `ingest` subcommand for flags (`--force-refresh`, etc.).
