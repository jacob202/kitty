# Kitty — Memory Index

**Purpose:** One-line pointers to where information lives. Update when adding a new doc or decision. If a pointer is stale, delete it.

---

## Canonical Docs

| File | What's in it |
|------|-------------|
| `docs/KITTY_CONTEXT.md` | Architecture, storage routing, validated corrections, model routing |
| `docs/SESSION_LOG.md` | Append-only session history |
| `docs/MEMORY_INDEX.md` | This file |
| `docs/EVALS.md` | Eval scores, baselines, what changed each run |
| `docs/CAPABILITY_INVENTORY.md` | What each specialist can do |
| `docs/cheatsheet.md` | Quick command reference |

## Plans

| File | What it covers |
|------|----------------|
| `docs/plans/2026-04-23-phase2-capability-platform.md` | Phase 2 plan |
| `docs/plans/2026-04-23-phase3-memory-reasoning.md` | Phase 3 plan (memory + context budget) |
| `docs/plans/2026-04-23-phase4-eval-platform.md` | Phase 4 plan (eval platform — now complete) |

## Key Source Locations

| Concept | File |
|---------|------|
| App factory | `web.py` → `create_app()` |
| Chat routing | `src/api/dispatcher.py` |
| SSE streaming | `src/api/streaming_routes.py` |
| Reasoning API | `src/api/reasoning_routes.py` |
| Memory product API | `src/api/memory_product_routes.py` |
| Eval route | `src/api/eval_routes.py` |
| Voice transcription | `src/api/transcription_service.py` + `src/api/voice_routes.py` |
| Context budget | `src/core/context_budget.py` |
| Context assembly | `src/core/context_manager.py` |
| Specialist base | `src/core/specialist_framework.py` |
| CoreOrchestrator | `src/space_kitty/core_orchestrator.py` |
| Domain Config | `config/domain_config.json` |
| Hardware Triggers | `config/hardware_triggers.json` |
| UI Strings | `config/ui_strings.json` |
| Honcho (psychology) | `src/space_kitty/honcho.py` |
| Journal patterns | `src/space_kitty/journal_interface.py` |
| Correction memory | `src/memory/correction_memory.py` |
| Smoke suite | `evals/smoke_suite.py` |
| Regression detection | `evals/compare_runs.py` |
| Eval artifacts | `evals/artifacts/*.json` |
| Full eval loop | `scripts/eval_loop.py` |
| Setup verifier | `scripts/verify_setup.sh` |
| Browser smoke tests | `tests/test_browser_smoke.py` |

## Feature Backlog

- AI model digest (daily summary of relevant AI news via domain news feed)
- Specialist KB training (ingest curated knowledge per specialist into LightRAG)
- Move `checkpoint.log` → `data/checkpoints/overnight.log`
