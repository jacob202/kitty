# Kitty — Architecture (canonical)

**Last updated:** 2026-06-17
**Source of truth:** this file. Supersedes the old `ARCHITECTURE.md` that described an Open WebUI stack.

---

## Processes

Everything runs on Jacob's Mac. Three processes; the gateway is the only one clients talk to directly.

| Role | Default host:port | Health endpoint |
|------|-------------------|-----------------|
| Kitty Gateway (FastAPI) | `127.0.0.1:5001` | `http://127.0.0.1:5001/health` |
| LiteLLM proxy | `127.0.0.1:8001` | `http://127.0.0.1:8001/health` |
| kitty-chat (Next.js) | `127.0.0.1:3000` | — |

Port overrides: set `GATEWAY_PORT` / `LITELLM_PORT` in `.env`. The Next.js proxy reads `KITTY_GATEWAY_URL` (defaults to `http://127.0.0.1:5001`). All three are aligned at 5001 / 8001 / 3000 out of the box — no `.env` override required for a standard run.

---

## How the pieces connect

```
Jacob (browser → localhost:3000)
        │
        ▼
kitty-chat  (Next.js, :3000)
  └── /proxy/[...path]  →  proxies everything to Gateway :5001
        │
        ▼
Kitty Gateway  (FastAPI, :5001)
  ├── context_builder.py   — assembles system prompt from all memory stores
  ├── memory_graph.py      — unified read interface across all 5 stores
  │     ├── mem0           (semantic facts)
  │     ├── ChromaDB       (document knowledge)
  │     ├── SQLite/JSONL   (chats, journal, traces, todos)
  │     └── buddy.py       (mood / relationship state)
  ├── llm_client.py        — LiteLLM → fallback chain (DeepSeek / Sonnet / …)
  ├── voice_pipeline.py    — STT → LLM → TTS
  ├── cron.py              — background loops (brief refresh, nudge engine, …)
  └── telegram_bot.py      — remote channel (/brief, /stuck, chat)
        │
        ▼
LiteLLM proxy  (:8001)
  └── routes to DeepSeek V4 Flash (default), Claude Sonnet (reasoning),
      or fallback chain (AgentRouter → OpenRouter → Gemini → NVIDIA)
```

The gateway is the product. Every client (browser, Telegram, Siri Shortcut, future PWA) is a thin view over the same HTTP/WebSocket surface. Logic lives in the gateway, never in a client.

---

## Python package layout

| Path | What lives there |
|------|-----------------|
| `gateway/` | All FastAPI routes + modules |
| `gateway/kitty-chat/` | Next.js frontend |
| `tests/` | pytest suite |
| `scripts/` | CLI tools (`kitty_manage.py` for KB ingest/status/prune) |
| `config/` | `SOUL.md`, `SOUL_SCRATCHPAD.md` |
| `design-system/` | Design tokens, colours, type |
| `data/` | Runtime data (gitignored) |
| `docs/` | This and related architecture/decision docs |
| `archive/` | Legacy trees — not part of the runtime import graph |

---

## Running tests

```bash
python3.11 -m pytest tests/ -q --tb=short
```

**Current baseline:** 498 passed, 2 deselected (as of 2026-06-18, after Phase A A1+A4 cleanup, stale council tests removed, and doctor/auth/launcher regressions covered).

---

## Key files

| File | Purpose |
|------|---------|
| `gateway/app.py` | All FastAPI routes |
| `gateway/llm_client.py` | LLM routing + fallback chain |
| `gateway/context_builder.py` | Builds system prompt (memory + knowledge + soul) |
| `gateway/memory_graph.py` | Unified query across all 5 stores |
| `gateway/buddy.py` | Kitty's persistent mood state + drift tracking |
| `gateway/voice_pipeline.py` | STT → LLM → TTS → gate |
| `gateway/paths.py` | All path constants — import from here, nowhere else |
| `gateway/config.py` | Gateway + LiteLLM host/port config |
| `.env.example` | Every secret that belongs in `.env` |

---

## Rebuilding the knowledge index (derived data)

The ChromaDB index is derived — sources live in `data/knowledge/` (see `gateway/paths.py`).

```bash
python scripts/kitty_manage.py ingest data/knowledge
```

Use `--force-refresh` to re-ingest everything. The index can be rebuilt from scratch at any time; it is not a primary store.

---

## What changed from the old stack

The repo previously ran Open WebUI as the primary UI. That path was abandoned. All Open WebUI scaffolding (filters, library tools, backup scripts, admin docs) was deleted in Phase A. The primary UI is now `kitty-chat` (Next.js). There is no Open WebUI process in the stack.
