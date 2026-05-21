# Kitty — Claude Code

## What this is
A local-first AI companion for Jacob. FastAPI backend (`gateway/`) + Next.js frontend (`gateway/kitty-chat/`). One checkout, one tool, build fast.

## Structure
```
gateway/          FastAPI app (:5001), all backend logic
gateway/kitty-chat/  Next.js UI
tests/            pytest suite
config/           SOUL.md, SOUL_SCRATCHPAD.md
data/             gitignored runtime data
.env              secrets — never commit
```

## Run tests
```bash
python3.11 -m pytest tests/ -q --tb=short
```
Currently: **300 passed, 2 skipped** (as of 2026-05-21).

## Key files
| File | Purpose |
|---|---|
| `gateway/app.py` | All FastAPI routes |
| `gateway/llm_client.py` | LLM routing + fallback chain |
| `gateway/context_builder.py` | Builds system prompt (memory + knowledge + soul) |
| `gateway/memory_graph.py` | Unified query across all 4 stores |
| `gateway/buddy.py` | Kitty's persistent mood state |
| `gateway/paths.py` | All path constants — import from here, nowhere else |
| `config/SOUL.md` | Who Kitty is — read before writing any dialogue |
| `.env.example` | Every secret that belongs in `.env` |

## Model routing
- **Default (execution):** `kitty-default` → DeepSeek V4 Flash via LiteLLM
- **Review/reasoning:** `kitty-sonnet` → Claude Sonnet (triggered by `route_model()` on reasoning keywords)
- **Fallback chain:** LiteLLM → AgentRouter → OpenRouter → Gemini → NVIDIA
- Never use Opus unless Jacob explicitly asks

## Rules
- Secrets in `.env` only — never in code
- Auth middleware in `gateway/auth.py` — don't bypass
- All storage goes through `StorageRouter` — never import a backend directly
- Run tests before claiming done on any Python/config change
- One concern per commit

## Current state (Phase 1 complete)
- ✅ Unified context: `memory_graph.unified_context()` queries memory/knowledge/journal/traces
- ✅ Voice gate: `voice_gate.py` filters drift, `self_review.py` logs it
- ✅ Voice session: WebSocket at `/voice` with 20-turn history
- ✅ Buddy: `buddy.py` + `/mood` endpoint; TopBar polls it live

**Next: Phase 2** — agents & background tasks. See `TASKS.md`.
