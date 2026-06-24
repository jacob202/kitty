# Kitty Architecture

**Date:** 2026-06-24
**Status:** Canonical current architecture

## Runtime

Kitty runs locally on Jacob's Mac.

| Process | Default | Purpose |
|---|---|---|
| Gateway | `127.0.0.1:${GATEWAY_PORT:-8000}` | FastAPI API, memory, tools, chat, capture |
| LiteLLM | `127.0.0.1:${LITELLM_PORT:-8001}` | Model proxy and routing |
| kitty-chat | `127.0.0.1:4000` in dev | Next.js UI |

The `./kitty` launcher is the preferred local entrypoint. Older shell scripts remain for compatibility but should not be treated as product architecture.

## Request Flow

```text
Browser / Raycast / Telegram / Siri
  -> Gateway routes in gateway/routes/
  -> context_builder
  -> memory_graph + live enrichment
  -> llm_client
  -> LiteLLM and provider fallback chain
```

The gateway is the product. Clients should be thin views over gateway APIs.

## Important Modules

| Path | Responsibility |
|---|---|
| `gateway/app.py` | FastAPI app setup, middleware, lifespan |
| `gateway/routes/register.py` | Route registration |
| `gateway/routes/` | API route modules |
| `gateway/paths.py` | Path constants |
| `gateway/context_builder.py` | Prompt/context assembly |
| `gateway/memory_graph.py` | Unified read path across memory stores |
| `gateway/desktop_store.py` | Quick Capture inbox writer/status helper |
| `gateway/llm_client.py` | Model routing and provider fallback |
| `gateway/cron.py` | Local scheduled actions |
| `gateway/kitty-chat/` | Next.js UI |

## Storage

Storage is mixed. App-owned state (Phase B shipped 2026-06) is consolidated in a single SQLite database at `data/kitty/kitty.db`.

- **SQLite** (`data/kitty/kitty.db`): todos, plugin_settings, chats, journal_entries, cron, model digest, task/build state, corrections
- **JSONL**: inbox (append-only per D4), logs, feedback, traces; legacy `data/journal.jsonl` is read-only (sync-only, going away with deepening-program Phase 1)
- **ChromaDB**: reference knowledge vectors
- **mem0**: semantic/personal memory
- **JSON**: config and small state files

Phase B shipped 2026-06: app-owned episodic state consolidated behind a single SQLite story. It did not migrate ChromaDB, mem0, imported raw knowledge, logs, or backups. The accepted **Gateway Architecture Deepening Program** (`docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md`, `status: ACCEPTED`) further deepens this substrate in 6 phases without touching the out-of-scope stores.

## Architecture Rules

- New context reads go through `memory_graph` (`gateway/memory_graph.py`). After deepening-program **Phase 2** lands, the canonical read path is `gateway/context_assembler.py` and `memory_graph` becomes an internal seam.
- Write paths go through `StorageRouter` (`gateway/storage_router.py`) for stores that have a registered adapter. Per **D7** (`docs/DECISIONS.md`), the router is a thin write-side seam, not a port — stores register themselves and routes consume typed accessors, never generic verbs.
- Do not put product logic in clients.
- Do not silently recover from storage or network failures; surface the failure clearly. (Deepening program Phases 2 and 3 enforce this.)
- Do not add a new database, queue, cloud service, or mobile sync. The deepening program deepens existing modules only.
