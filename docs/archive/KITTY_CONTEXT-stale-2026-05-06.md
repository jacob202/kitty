# Kitty — Curated Context

**Purpose:** Single source of truth for what Kitty is, what's been decided, and what corrections matter most. Read this before starting any new session.

---

## What Kitty Is

Kitty is Jacob's local-first personal AI assistant. It runs as a Flask + SocketIO web app (Python 3.12) with a chat UI, voice input, and a specialist framework for routing queries to domain experts. The goal is a private, always-on companion that learns Jacob's patterns over time.

**Entry point:** `web.py` → `create_app()` → blueprints + CoreOrchestrator  
**Run command:** `/opt/homebrew/bin/python3.12 web.py`  
**Test command:** `/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short`

---

## Codebase Map (Real Paths)

```
web.py                          # App factory + Flask entry point
kitty                           # Launcher script (start/stop/logs)
src/
  api/                          # HTTP/SocketIO routes & services
  core/                         # Orchestration, framework, specialists
  memory/                       # Memory subsystems (CorrectionMemory, etc)
  space_kitty/                  # Behavioral & reasoning orchestrators
  cli/                          # Terminal UI & reference tools
  tools/                        # Custom tool implementations
  autonomy/                     # Self-improvement engine
evals/                          # Smoke suite, personas, artifacts
tests/                          # pytest suite (~85 tests)
config/specialists/             # Per-specialist markdown configs
docs/                           # Context, tasks, plans, audits
skills/                         # Legacy, consolidated, & packaged skills
scripts/                        # Setup, eval, and maintenance scripts
data/                           # Databases, logs, checkpoints, budget
```

---

## Storage Routing (Never swap these)

| Data | System | Never use |
|------|--------|-----------|
| Knowledge base ingestion | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| MCP entities/relations | @modelcontextprotocol/server-memory | — |
| Eval artifacts | `evals/artifacts/*.json` | DB |
| Session memory | hybrid (in-memory + AgentDB) | — |

Routing violations are the #1 source of data-loss bugs in this project.

---

## Model Routing

| Need | Model | Notes |
|------|-------|-------|
| Fast / free / local | MLX Qwen3.5-4B | `enable_thinking=True` for reasoning |
| Cheap remote | deepseek-chat | wired for both large + small slots |
| Heavy reasoning | deepseek-reasoner | paid — use sparingly |

Local models are free. Always try them first.

---

## Validated Corrections (High Priority)

These are decisions that were tested and confirmed correct. Don't revert them.

**1. Context slot assignment must be direct, not positional.**  
`ContextBudget.add()` must always receive the named `ContextSlot` (IDENTITY, CORRECTIONS, RECENT, EPHEMERAL). Never use a positional list and index into it — when sections are empty the indices shift and corrections land in the wrong slot.

**2. Reasoning layer must be sourced from `current_app.orchestrator`.**  
`_get_reasoning_layer()` in `reasoning_routes.py` must check `current_app.orchestrator` first. `current_app.supervisor.orchestrator` is always `None` in web mode — the shim has no orchestrator attribute.

**3. `POST /api/memory/corrections` must return 400 when `item_id` is missing.**  
Currently returns 207. This validation gap is a known open bug.

---

## Eval Platform

Baseline: **95–100% pass rate on smoke suite.**

Run the full loop:
```bash
# Quick: pytest only
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short

# Full: pytest + eval route + regression check
/opt/homebrew/bin/python3.12 scripts/eval_loop.py
```

The eval route (`POST /api/eval/run`) returns:
- `200` — suite passed
- `422` — baseline below threshold (regression)
- `400` — unknown suite name

Never skip evals after touching ChromaDB, context routing, or specialist configs.

---

## Launch Commands

```bash
./kitty              # start server + open browser
./kitty stop         # kill server
./kitty restart      # bounce
./kitty status       # running? + URLs
./kitty logs         # tail live output
```

Phone URL prints on start (e.g. `http://172.16.1.161:5001`)

---

## Slash Commands (User-Facing)

```
/brief              morning brief — where you left off
/stuck [task]       ADHD rescue: one concrete next step
/bench [name]       work mode (sansui, ridgeline, or custom project)
/bench off          clear work mode
/council <topic>    dynamic expert panel debate
/capture <thought>  quick brain dump (persisted)
/review             show all captures + saved facts
/remember <fact>    save a persistent fact
/deepsearch <q>     web search + synthesis
/screen [q]         screenshot + vision analysis
/status             model, tools, session cost
/clear              clear conversation history
/help               full command list
```

Stable API surface: `/api/chat`, `/api/transcribe`, `/api/capabilities`, `/health`

Experimental (only with `KITTY_ENABLE_INTERNAL_API=1`): `/prep`, `/optic`, `/ocr`, `/scrape`, `/cal`, `/watch`, `/council`

Swarm routes (`/api/swarm/*`) disabled by default; enable with `KITTY_ENABLE_EXPERIMENTAL_SWARM=1`

---

## Specialists

Auto-activated by topic. Shown in the right panel.

| Name | Domain |
|------|--------|
| Alex | Audio electronics (Sansui) |
| Kelly | Fitness, health |
| Mike | Automotive (Ridgeline) |
| Taylor | Recovery, growth |
| Devin | Code, systems |

Configs: `config/specialists/` | Python: `src/core/specialists/`

---

## Key Env Vars

```bash
OPENROUTER_API_KEY=sk-or-...     # primary remote provider
ANTHROPIC_API_KEY=sk-ant-...     # fallback
KITTY_MODEL=openrouter/free                 # free online default
KITTY_MAX_MODEL=deepseek/deepseek-r1-0528   # max mode
MLX_MODEL=mlx-community/Qwen3.5-4B-4bit     # optional local model
KITTY_ENABLE_LOCAL_MLX=1                    # opt in to local MLX fast mode
KITTY_ENABLE_EXPERIMENTAL_SWARM=1           # unlock swarm routes
KITTY_ENABLE_INTERNAL_API=1                 # unlock dev-only routes
```

Fallback order: OpenRouter free router → Anthropic by default; MLX first only when `KITTY_ENABLE_LOCAL_MLX=1`

---

## Voice Pipeline

```
Browser MediaRecorder
  → POST /api/transcribe (multipart/form-data)
  → src/api/transcription_service.py
  → faster-whisper (lazy-loaded on first call)
  → transcribed text → normal chat path
```

Frontend elements already exist: `#voice-toggle` button, mic CSS. Do NOT add them again.

---

## Frontend Rule

Before adding any CSS class, DOM ID, or JS function: search for it first. Previous agents introduced duplicate mic button CSS twice. Check before touching the UI.

---

## Dev Environment

- Python: `/opt/homebrew/bin/python3.12` (Homebrew — not venv)
- playwright installed system-wide: `pip install playwright --break-system-packages`
- direnv: auto-activates venv on `cd` into project
- Post-edit hook: `py_compile` runs on every Python file save (`.claude/settings.json`)
- Pre-commit hook: blocks commits when pytest fails (`.git/hooks/pre-commit`)
