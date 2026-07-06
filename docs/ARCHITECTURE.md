# Kitty Architecture

**Date:** 2026-07-02
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
  -> Gateway routes in gateway/routes/ (thin handlers)
  -> context_assembler (deep prompt-assembly pipeline)
  -> memory_graph + context_enrichment (read fan-in)
  -> llm_client (table-driven provider dispatcher + fallback chain)
  -> LiteLLM and provider fallback chain
```

The gateway is the product. Clients should be thin views over gateway APIs.

## Important Modules

| Path | Responsibility |
|---|---|
| `gateway/app.py` | FastAPI app setup, middleware, lifespan |
| `gateway/routes/register.py` | Route registration |
| `gateway/routes/` | API route modules (thin — delegate to domain modules) |
| `gateway/paths.py` | Path constants |
| `gateway/context_assembler.py` | Deep prompt/context assembly pipeline (10-step) |
| `gateway/context_builder.py` | Thin re-export facade over `context_assembler` |
| `gateway/memory_graph.py` | Unified read path across memory stores (adapters, `Item`, `GraphResult`) |
| `gateway/llm_client.py` | Table-driven provider dispatcher + 6-provider fallback chain |
| `gateway/storage_router.py` | Write seam for app-state stores |
| `gateway/storage_sync.py` | Export/import snapshot for app-state (replaces former `storage_io` + `sync`) |
| `gateway/domain_router.py` | Keyword domain classifier (soul/repair/health/research/code) |
| `gateway/prompts.py` | Inline prompt catalog + on-disk prompt loader (`load_prompt`) |
| `gateway/agent_runner.py` | Background agent loop + Algorithm reasoning phases |
| `gateway/desktop_store.py` | Quick Capture inbox writer/status helper |
| `gateway/cron.py` | Local scheduled actions |
| `gateway/kitty-chat/` | Next.js UI |

## Domain Modules (route islands)

Route files are thin handlers that delegate product logic to domain modules:

| Domain module | Route file |
|---|---|
| `gateway/dream_insights.py` | `routes/dream.py` |
| `gateway/feedback.py` | `routes/feedback.py` |
| `gateway/insights.py` | `routes/insights.py` |
| `gateway/loops.py` | `routes/loops.py` |
| `gateway/monitors.py` | `routes/monitors.py` |
| `gateway/perf.py` | `routes/perf.py` |
| `gateway/prompts_catalog.py` | `routes/prompts.py` |

## Storage

Current storage is mixed:

- JSONL: inbox, journal, logs, feedback, traces
- SQLite (`KITTY_DB_FILE`): todos, chats, journal_entries, buddy_state, plugin_settings — via `gateway/db.py`
- SQLite (subsystem DBs): cron, builds, task_queue, ingestion, web_monitors, autonomy, model_digest, signals — each module manages its own connection (see ADR-0001)
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
- App-state writes go through `storage_router`. Subsystem writes may use direct stores.
- Do not put product logic in route files — delegate to domain modules.
- Do not silently recover from storage or network failures; surface the failure clearly.
- Do not add a new database, queue, cloud service, or mobile sync without an ADR.

## Removed Modules

The following shallow modules were deleted (deepening passes):

**2026-07-02 pass:**

- `gateway/llm_utils.py` — one retry function, sole caller was `llm_client`; inlined.
- `gateway/prompt_loader.py` — 25-line pass-through; folded into `prompts.py`.
- `gateway/algorithm.py` — leaf helper with one consumer; folded into `agent_runner.py`.
- `gateway/agents.py` — orphaned persona loader; never imported by any module.
- `gateway/storage_io.py` — backup/restore; merged into `storage_sync.py`.
- `gateway/sync.py` — export logic; merged into `storage_sync.py`.
- `gateway/domain_router.py` ABC layer — `DomainClassifier`/`_classify_cached`/`classifier` param; dead (no second implementation).

**Track C pass (2026-07-06):**

- `gateway/smoke_eval.py` — orphaned smoke-suite harness; deleted with its `gateway/eval_domain.py` substrate.
- `gateway/eval_domain.py` — evaluation domain types only consumed by the deleted `smoke_eval.py`.
- `gateway/parts.py` — small parts-mode helper; folded into `gateway/context_assembler.py`.
- `gateway/prompts_catalog.py` — template list with one route consumer; folded into `gateway/prompts.py`.
- `gateway/success_criteria.py` — ISA-lite derive/check helper; folded into `gateway/builder.py`.
- `gateway/voice_session.py` — 19-line re-export shim with no callers; deleted.
