# Kitty
# Kitty 🐾

Jacob's local-first AI companion. Runs on the Mac, keeps data on the Mac, and aims for **daily-use reliability over spectacle** — start cleanly, capture a thought fast, resurface it later, don't lose anything.

> **Status:** Phases B and C shipped · ~580+ tests passing · Python 3.12 + Next.js · personal project, not packaged for public use.
>
> **Coming back cold?** Read [`START_HERE.md`](START_HERE.md) first — it's the front door for agents and future-Jacob. This README is the map; `START_HERE.md` → `docs/PROJECT_STATUS.md` → `docs/ARCHITECTURE.md` is the deep path.

---

## Architecture at a glance

Kitty runs as three local processes. **The gateway is the product; every client is a thin view over its API.**

| Process | Address (default) | Job |
|---|---|---|
| **Gateway** | `127.0.0.1:8000` | FastAPI — API, memory, tools, chat, capture |
| **LiteLLM** | `127.0.0.1:8001` | Model proxy + routing/fallback |
| **kitty-chat** | `127.0.0.1:4000` (dev) | Next.js UI |

**Request flow:**
```text
Browser / Raycast / Telegram / Siri / iMessage
  → gateway routes (gateway/routes/)
  → context_builder
  → memory_graph + live enrichment
  → llm_client
  → LiteLLM + provider fallback chain
```

Rule that keeps it clean: **new context reads go through `memory_graph`; no product logic in clients; surface failures loudly, never silently recover.**

---

## Repo layout

```text
kitty
├── kitty                 # ./kitty launcher — up/down/status/doctor/logs/backup/install
├── gateway/              # THE PRODUCT — FastAPI app, routes, memory, tools, voice, UI
│   ├── app.py            #   FastAPI setup, middleware, lifespan
│   ├── context_builder.py#   prompt/context assembly
│   ├── memory_graph.py   #   unified read path across memory stores
│   ├── llm_client.py     #   model routing + provider fallback
│   ├── desktop_store.py  #   Quick Capture inbox
│   ├── honcho.py / memory.py / memory_consolidation.py
│   ├── voice_*.py, stt.py, tts.py   # voice pipeline
│   └── kitty-chat/       #   Next.js UI
├── soul/                 # identity — kitty.md + specialists/ (analyst, coder, companion, creative, researcher)
├── contracts/            # interface contracts/schemas between layers
├── backend/ · gateway/ · mcp/imagen/   # services + image-gen MCP
├── docs/                 # canonical design docs (start with PROJECT_STATUS + ARCHITECTURE)
├── scripts/ · tests/ · config/ · data/ · logs/ · prompts/
├── AGENTS.md · CLAUDE.md · CODEX.md     # per-agent instructions
└── START_HERE.md · TASKS.md · TODOS_NEXT.md
```

---

## Quick start

```bash
# 1. Python env (3.12)
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt

# 2. Config — copy and fill in keys locally (never commit .env)
cp .env.example .env

# 3. Bring up gateway + LiteLLM
./kitty up

# 4. Verify
./kitty status
./kitty doctor --json     # expect 9 PASS / 1 WARN (telegram token) / 0 FAIL

# 5. UI (separate terminal)
cd gateway/kitty-chat && npm install && npm run dev   # → 127.0.0.1:4000
```

`./kitty down` stops everything. `./kitty install` registers launchd plists so the stack auto-starts on reboot. Ports are overridable in `.env` via `GATEWAY_PORT` / `LITELLM_PORT`.

**Optional:** local Ollama on `:11434` enables embeddings. Without it, `memory_graph` falls back to no-embeddings and the morning brief still works (it uses RSS).

---

## Everyday commands

```bash
git status --short --branch
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
make agent-wrap                       # write a session wrap-up log
```

---

## Memory & storage

Storage is deliberately mixed, with `memory_graph` as the unified read path:

- **JSONL** — inbox, journal, logs, feedback, traces
- **SQLite** (`data/kitty/kitty.db`) — todos, cron, model digest, task/build state, corrections
- **ChromaDB** — reference-knowledge vectors
- **mem0** — semantic/personal memory
- **JSON** — config + small state

Phase B consolidated app-owned episodic state behind one SQLite story via a thin write-side `storage_router`. ChromaDB, mem0, imported knowledge, logs, and backups were intentionally **not** migrated.

---

## Model routing

`llm_client` + LiteLLM route through a provider fallback chain, all keyed in `.env`: **AgentRouter** (preferred first hop) → Anthropic / Gemini / OpenAI / NVIDIA NIM → **OpenRouter** (free-tier + last-resort). Set only the keys you have; unset providers are skipped.

---

## Working with agents

This is vibe-coded across a rotating toolchain, so the instruction files are the contract — point any agent at them first:

- **`AGENTS.md`** — shared agent rules
- **`CLAUDE.md`** — Claude Code
- **`CODEX.md`** — Codex
- **`START_HERE.md`** — orientation + read-order for everything else

`soul/kitty.md` is the identity core; `soul/specialists/` holds the per-role personas (analyst, coder, companion, creative, researcher).

---

## Where to go next (docs map)

| Doc | What it's for |
|---|---|
| `docs/PROJECT_STATUS.md` | Current branch, what's shipped, dirty work, verification |
| `docs/ARCHITECTURE.md` | Canonical runnable stack (the source for this section) |
| `docs/DECISIONS.md` | Settled decisions |
| `docs/LEARNINGS.md` | Hard lessons + guardrails |
| `.claude/HANDOFF.md` | Latest continuation package |

---

## Known rough edges

- `docs/` has sprawl (40+ files, some marked stale). `HANDOFF.md` / `SESSION_HANDOFF.md` at root are **stale** — use `.claude/HANDOFF.md`.
- `LITELLM_MASTER_KEY` defaults to `kitty-local-key-change-me` — fine for localhost, change it if Kitty ever binds beyond loopback.
