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

## Runtime Check (verified 2026-06-20, two states)

**State 1 — services down** (initial, before `./kitty up`):

- `./kitty status` -> gateway not running, LiteLLM not running.
- `./kitty doctor --json` -> 7 PASS / 1 WARN / 2 FAIL.
- FAIL is `service:gateway` and `service:litellm` unreachable.

**State 2 — services up** (after `./kitty up`):

- `./kitty up` -> both processes start; gateway binds 127.0.0.1:8000, LiteLLM binds 127.0.0.1:8001.
- `./kitty doctor --json` -> **9 PASS / 1 WARN / 0 FAIL** (the 1 WARN is `env:telegram_token` not set, expected).
- `curl http://127.0.0.1:8000/health` -> HTTP 200 in 0.10s.
- `curl http://127.0.0.1:8001/health/readiness` -> HTTP 200 in 0.10s.
- Authenticated: `GET /todos` and `GET /plugins` return real data.
- **End-to-end through B3+B4 (storage_router):** `POST /todos/add` returns a new id, the row persists in `data/kitty/kitty.db` (`sqlite3` confirms it), `DELETE /todos/{id}` removes it.
- `./kitty down` -> both processes stop cleanly.

**Port state:** the runtime is on **8000/8001** (the launcher's defaults — `GATEWAY_PORT` and `LITELLM_PORT` are not set in `.env` or `.env.example`). The historical port-mismatch (older docs saying 5001) is **resolved** in the current state: `docs/ARCHITECTURE.md` says 8000, `.env.example` says 8000, the Next.js proxy at `gateway/kitty-chat/src/app/proxy/[...path]/route.ts` defaults to 8000, and `CLAUDE.md` does not name a port number. The 5001 references that remain are:
- Historical archive (`docs/DECISIONS_AND_ROADMAP.md`, `docs/LESSONS.md`, the Phase 1 evidence docs) — correct to keep as history
- `docs/KITTY_HUB.md` — a separate FastAPI service ("kitty hub") on its own 5001, unrelated to the main gateway
- One unit test (`tests/test_doctor.py:29`) uses 5001 as a test input value for URL building; harmless and orthogonal
- A historical `DESKTOP_PHASE_1_HARD_CRITIC_REVIEW.md` note that flagged the proxy default; the code has since been fixed to 8000

If you ever want the runtime to bind 5001, set `GATEWAY_PORT=5001` in `.env` and the launcher will use it; current code does not need it.

**External service note:** the gateway logs `Embedding batch failed at index 0: HTTPConnectionPool(host='localhost', port='11434'): Connection refused` on every startup — that's the local ollama embed service. It is not required for the gateway to start, but `memory_graph.unified_context()` falls back to no-embeddings when it's down. The morning brief still works (it uses RSS feeds, not embeddings). If you want embeddings to work, start ollama locally on 11434.

## Issue #30 fix (verified 2026-06-20)

Closed the brief-context-shaping follow-up from issue #30 in one commit:

- **Real theme source:** `detect_research_themes()` now reads from `journal.recent_entries(days=14)` and ranks bigrams by mention count. Replaces the old `search_all("research learning pattern")` heuristic. Each returned theme has `{"theme", "mentions", "source": "journal"}`.
- **Honest empty state:** when journal has no recent entries, the function returns `[]` instead of the fabricated `[{"theme": "general knowledge", ...}]` fallback. `synthesize_brief_with_llm` skips the "YOUR RESEARCH INTERESTS" prompt section when `themes == []`, so the LLM no longer gets told Jacob is working on "general knowledge."
- **asyncio refactor:** introduced a module-level `_run_async(coro)` helper in `gateway/brief.py` and routed the one remaining `asyncio.run` call (`_fetch_memory_snippet`) through it. The original two call-site refactor the issue called for collapses to one call site now that `detect_research_themes` is sync.
- **Integration test:** `test_detect_research_themes_integration_with_real_journal` exercises real `journal.recent_entries` against a temp `journal_entries.jsonl` and asserts `[]` on empty — proves the "no fake fallback" contract.
- **Test count:** 6 new brief tests (27 brief total, up from 21). Full suite: **586 passed, 2 deselected, 4 warnings**.
