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
Currently: **449 passed, 2 skipped** (as of 2026-05-21).

## Key files
| File | Purpose |
|---|---|
| `gateway/app.py` | All FastAPI routes |
| `gateway/llm_client.py` | LLM routing + fallback chain |
| `gateway/context_builder.py` | Builds system prompt (memory + knowledge + soul) |
| `gateway/memory_graph.py` | Unified query across all 5 stores (memory, knowledge, journal, traces, todos) |
| `gateway/buddy.py` | Kitty's persistent mood state + drift tracking |
| `gateway/voice_pipeline.py` | Deep voice pipeline (STT → LLM → TTS → gate) |
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
- All storage reads for prompt/search context go through `memory_graph` — never bypass with raw JSONL/file reads in new code
- Direct backend imports (`memory`, `knowledge`, `todo_store`) are OK for write paths until a StorageRouter exists
- Run tests before claiming done on any Python/config change
- One concern per commit

## Deep Module Pattern
Modules like `voice_pipeline`, `memory_graph`, and `buddy` follow the **deep module principle**:
- **Small interface, large implementation** — a lot of behavior behind a small API
- **Internal adapters hidden from callers** — stores, providers, backends are implementation details
- **Tests at the interface, not internal seams** — test behavior, not structure

When adding new stores or adapters, follow the pattern in `memory_graph.py`:
1. Define a `StoreAdapter` class with `fetch()` and `format_items()`
2. Keep the adapter internal (not exported)
3. Expose only high-leverage functions (`unified_context`, `search_all`)

## Current state (Phase 1 complete)
- ✅ Unified context: `memory_graph.unified_context()` queries 5 stores with cross-store correlation
- ✅ Voice pipeline: Deep module consolidates STT/TTS/gate/session (`voice_pipeline.py`)
- ✅ Session state: Buddy tracks mood/energy/drift across all endpoints (ask, chat, voice)
- ✅ Deep module pattern: Documented in CLAUDE.md; applied to voice, memory, buddy

**Next: Phase 2** — agents & background tasks. See `TASKS.md`.
