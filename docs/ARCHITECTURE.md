# Kitty Architecture

**Date:** 2026-06-20
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

Current storage is mixed:

- JSONL: inbox, journal, logs, feedback, traces
- SQLite: todos, cron, model digest, task/build state, corrections, signals
- ChromaDB: reference knowledge vectors
- mem0: semantic/personal memory
- JSON: config and small state files

### Signals

`gateway/signal_store.py` is the append table for connector and system events (P1). It lives in the main Kitty SQLite database and is consumed by `gateway/memory_graph.py` via `SignalsAdapter`.

Signal shape:

```json
{
  "id": 1,
  "ts": 1719900000.0,
  "source": "web_monitor",
  "kind": "watch_match",
  "payload": {"watch_id": "abc123", "label": "Example"},
  "seen": false
}
```

`seen` is derived from the SQLite `processed_at` column (`seen` is true when `processed_at` is non-null). Emitters include:

- `gateway/web_monitor.py` — emits a `web_monitor` signal on content change or keyword match.
- `gateway/nudge.py` — emits a `nudge` signal for each active nudge, deduped by nudge id.

Phase B consolidates app-owned episodic state behind a single SQLite story. It does not migrate ChromaDB, mem0, imported raw knowledge, logs, or backups first.

## Architecture Rules

- New context reads go through `memory_graph`.
- Write paths may use direct stores until Phase B introduces `StorageRouter`.
- Do not put product logic in clients.
- Do not silently recover from storage or network failures; surface the failure clearly.
- Do not add a new database, queue, cloud service, or mobile sync in Phase B.
