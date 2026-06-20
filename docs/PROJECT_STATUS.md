# Project Status

**Date:** 2026-06-20
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`
**Current branch:** `codex/phase-b-prep`
**Base:** `c6accd0`

## Current Product State

Kitty is a local-first companion with a FastAPI gateway, LiteLLM proxy, and Next.js UI. Phase A cleanup mostly landed. Quick Capture exists and writes mobile-compatible inbox entries. Inbox resurfacing exists through `memory_graph`. Phase B B1 has a SQLite migration seam, B2 migrated plugin settings behind the registry API, B3 started with todos writing through the Phase B Kitty DB with copy-only legacy import, B4 has a thin write-side storage router for todo and plugin mutations, and B5 has a local backup/restore drill for `data/kitty/`. No chat or journal data has been migrated.

## Current Priority

Prepare Phase B: one storage story and one agent/documentation story. Do not add mobile sync, cloud auth, push notifications, agent dashboards, or new TELOS/PAI expansion.

## Included Test Hygiene

- `tests/test_memory_graph.py` now allows 150ms for timeout-bound async tests instead of 100ms. The previous 100ms cutoff flaked during the commit hook at 102ms while still proving a 200ms blocking call was bounded.

## Open Dirty Work

- `codex/raycast-quick-capture` contains a useful unmerged Raycast wrapper commit: `5a07744`.
- A roadmap hunk was preserved in stash `phase-b-prep preserve roadmap deepening drift`.
- Several older stashes contain prior memory/LLM routing experiments and need review before deletion.

## Known Risks

- Runtime state is spread across JSON, JSONL, SQLite, ChromaDB, and mem0.
- Root `HANDOFF.md` and `SESSION_HANDOFF.md` are stale compatibility artifacts; use `docs/AGENT_HANDOFF.md` going forward.
- Pre-commit has an unreachable code-review-graph block after `exit 0`.

## Verification

- `python3.12 -m py_compile scripts/agent_wrapup.py` passed.
- `python3.12 -m pytest tests/test_check_continuity_state.py tests/test_run_gates_script.py -q --tb=short` passed: 23 tests.
- `python3.12 -m pytest tests/test_memory_graph.py -q --tb=short` passed: 10 tests.
- `python3.12 -m pytest tests/test_db.py -q --tb=short` passed: 4 tests.
- `python3.12 -m pytest tests/test_plugin_registry.py -q --tb=short` passed: 3 tests.
- `python3.12 -m pytest tests/test_todo_store.py tests/test_db.py tests/test_plugin_registry.py -q --tb=short` passed: 29 tests.
- `python3.12 -m pytest tests/test_storage_router.py tests/test_todo_store.py tests/test_plugin_registry.py -q --tb=short` passed: 35 tests.
- `python3.12 -m pytest tests/test_kitty_backup.py tests/test_kitty_launcher.py -q --tb=short` passed: 11 tests.
- `make agent-wrap` created an ignored session log under `.agent/session_logs/`.
- `python3.12 -m pytest tests/ -q --tb=short` passed: 571 passed, 2 deselected, 3 warnings.

## Next Best Step

Review and commit the B5 backup drill, then choose the next user-facing store deliberately. Do not migrate chats or journal without an explicit compatibility and rollback plan.
