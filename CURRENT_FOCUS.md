# Current focus

Last updated: **2026-05-13**

## Operating reality

- **Canonical repo:** `/Users/jacobbrizinski/Projects/kitty` (never the Desktop copy).
- **Runtime:** Python in **`gateway/`** (Flask + SocketIO API on **:5001**). Open WebUI / LiteLLM / stack details: **`docs/ARCHITECTURE.md`**, launcher scripts under **`kitty_gateway/*.sh`**.
- **LLM hub:** `gateway/llm_client.py` — LiteLLM first, then AgentRouter → OpenRouter → Gemini → NVIDIA. Short AgentRouter slugs + env overrides documented in **`.env.example`** and **`SESSION_HANDOFF.md`**.
- **Orientation:** **`docs/STANDUP.md`**, **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`**, root **`TASKS.md`**, **`CURRENT_FOCUS.md`**.

## Recent repo changes (committed)

- Retired stale root **`MASTER_INDEX.md`**, **`KITTY_CONTEXT.md`**, **`PROJECT_REALITY_CHECK.md`**. Orientation = **`docs/STANDUP.md`** + **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`** + **`TASKS.md`** (see **`docs/DECISIONS.md` D-0030**).
- **Gateway:** ingest path scoring via **`gateway/ingest_policy.py`**, **`tests/test_ingest_policy.py`**, plus routing / librarian / memory / researcher / queue updates; **`gateway/eval_domain.py`**, **`gateway/smoke_eval.py`** scaffold.
- **Prune:** removed legacy **`src/`** (core + builder), old **`evals/`** harness, **`benchmarks/`**, most **`scripts/*.py` shims**, and **`config/specialists/`** JSON. Remaining scripts are mainly **books / ingest / queue** helpers — see **`scripts/`**.
- Tooling hygiene: **`.cursorignore`** excludes **`.git/`**; duplicate **`scripts/setup/gate-check (N).sh`** Finder copies deleted locally.

## Verification

- Last full run: **`244 passed`**, 2 skipped, 2 deselected  
  `/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short`
- One known warning in **`tests/test_researcher.py`** (async mock not awaited) — non-blocking.

## Working tree backlog (still untracked / local)

Roughly **~70 untracked** paths: IDE configs (`.vscode/`, `.mcp.json`, …), **`free-code/`**, **`config/swarm/`**, **`scripts/archive/`**, extra **`tests/*`**, Open WebUI tool stubs under **`kitty_gateway/openwebui_library_tools/`**, etc. Treat as optional; **`git add`** only intentional slices.

Dirty: **`.claude/settings.json`** (local; do not commit secrets).

## Forbidden work

- MCP expansion beyond current scope · QLoRA · deleting raw chat logs · renaming/removing canonical checkout root.
