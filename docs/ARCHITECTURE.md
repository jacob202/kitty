# Kitty — live stack (canonical)

This file describes the **current** runnable Kitty stack. Ports below reflect `.env.example` and `CLAUDE.md`; `start_gateway.sh` has a legacy default of 8000 which is overridden by `GATEWAY_PORT=5001` in `.env`.

## Processes

| Role | Default host:port | Health check |
|------|-------------------|--------------|
| Kitty Gateway (FastAPI) | `127.0.0.1:5001` | `http://127.0.0.1:5001/health` |
| LiteLLM proxy | `127.0.0.1:8001` | `http://127.0.0.1:8001/health` (with LiteLLM auth header) |
| kitty-chat (Next.js UI) | `127.0.0.1:3000` | `http://127.0.0.1:3000` |

Overrides (set in `.env`):
- Gateway: `GATEWAY_PORT` (default in script: 8000; override to 5001 in `.env`)
- LiteLLM: no override needed unless you move it off 8001

Launch entrypoint: **`gateway/start_all.sh`**  
Status: **`gateway/status_all.sh`**  
Stop: **`gateway/stop_all.sh`**

> **Portability:** `start_all.sh` has a hardcoded `ROOT_DIR`. If you clone or move the repo, update `ROOT_DIR=` in each `gateway/start_*.sh` file, or set `GATEWAY_PORT` and other vars in `.env`.

## Client

**kitty-chat** (`gateway/kitty-chat/`) — the Next.js frontend at `:3000`. All chat, dashboard, tasks, mood, and voice run through it. It proxies to the gateway via `/proxy/[...path]`, which forwards to `KITTY_GATEWAY_URL` (default `http://127.0.0.1:5001`).

There is no other supported frontend. Open WebUI was removed in the Phase A cleanup.

## Python package layout

| Path | Purpose |
|------|---------|
| `gateway/` | FastAPI app, all backend logic |
| `gateway/app.py` | All routes |
| `gateway/llm_client.py` | LLM routing + fallback chain |
| `gateway/context_builder.py` | Builds system prompt (memory + knowledge + soul) |
| `gateway/memory_graph.py` | Unified query across all 5 stores |
| `gateway/buddy.py` | Kitty's persistent mood state |
| `gateway/voice_pipeline.py` | STT → LLM → TTS → gate |
| `gateway/paths.py` | All path constants — import from here only |
| `contracts/` | Shared Pydantic shapes |
| `scripts/` | CLIs; `scripts/kitty_manage.py` owns KB ingest/status/prune |

## Model routing

| Alias | Model | Trigger |
|-------|-------|---------|
| `kitty-default` | DeepSeek V4 Flash via LiteLLM | Default for all chat |
| `kitty-sonnet` | Claude Sonnet | Reasoning keywords via `route_model()` |

Fallback chain: LiteLLM → AgentRouter → OpenRouter → Gemini → NVIDIA

## Running tests

```bash
python3.11 -m pytest tests/ -q --tb=short
```

Baseline: **451 passed, 2 skipped** (as of 2026-06-14).

## Rebuilding the knowledge index

The vector index in ChromaDB is derived data (rebuildable via ingest):

```bash
python3.11 scripts/kitty_manage.py ingest data/knowledge
```
