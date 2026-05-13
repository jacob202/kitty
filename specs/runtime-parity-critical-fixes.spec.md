# Spec: runtime-parity-critical-fixes

Date: 2026-04-30
Owner: codex
Worker lane: `runtime-001`
Status: **completed** (verified 2026-04-30)

## Goal

Fix the smallest set of audited runtime blockers that can cause crashes or
wrong specialist routing while preserving the current migration baseline.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty-system/kitty-app`

Canonical git/rollback checkout:

`/Users/jacobbrizinski/Projects/kitty`

Physical repo move allowed:

No.

Future `kitty-system` separation:

Pending controlled migration. Do not implement path moves, import rewrites, or
launch-command rewrites in this spec.

## Background

Source audit:

- `docs/audits/project-context-audit-20260430.md`
- `docs/audits/cursor-kitty-chat-inventory-20260430.md`
- `docs/audits/operational-plan-20260430.md`

The audit found the P2 no-mode `/stream` default is already addressed and
synced, but three sharp runtime defects remain:

1. `src.memory.memory_weave` fails on import because `memory_weave` is missing
   from `src/core/db_config.py::DB_PATHS`.
2. `src/core/specialists/router.py` routes code/programming queries to `alex`
   instead of the code specialist.
3. The migrated workspace lacks the legacy guard that makes `/unified` return
   a controlled `501` when the web supervisor shim does not implement
   `handle_unified_request`.
4. Migrated validation may fail before tests run if blueprint imports reference
   a route file that exists in legacy but not migrated. During execution, this
   occurred for `src/api/news_routes.py` and its service dependency.

The audit also found live `/health` and `/api/health` returned `404` while
current disk code registered those routes. Follow-up inspection showed both
routes call `_require_internal_api()`, so the 404 is expected unless internal
API mode is enabled. This spec records that as a docs/expectation mismatch, not
a runtime blocker.

## Allowed Files

Legacy checkout changes:

- `specs/runtime-parity-critical-fixes.spec.md`
- `docs/superpowers/plans/2026-04-30-runtime-parity-critical-fixes.md`
- `docs/AGENT_COORDINATION.md`
- `src/core/db_config.py`
- `src/core/specialists/router.py`
- `src/api/streaming_routes.py`
- `src/api/news_routes.py`
- `src/services/domain_news_monitor.py`
- `tests/test_memory_weave.py`
- `tests/test_specialist_router.py`
- `tests/test_unified_route.py`

Migrated runtime sync targets after legacy validation:

- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/core/db_config.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/core/specialists/router.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/api/streaming_routes.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/api/news_routes.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/src/services/domain_news_monitor.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/tests/test_memory_weave.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/tests/test_specialist_router.py`
- `/Users/jacobbrizinski/Projects/kitty-system/kitty-app/tests/test_unified_route.py`

## Forbidden Files

- `web.py`
- `kitty-chat/`
- `data/`
- `data/lightrag/`
- `data/vector_store/`
- `data/chroma/`
- raw chat logs
- generated database files
- `Icon\r` files
- launch scripts except using existing `./kitty status` or `./kitty restart`
  for validation only

## Non-Goals

- No UI polish.
- No backend port config refactor.
- No memory migration.
- No LightRAG ingestion.
- No physical workspace move.
- No provider/model setup.
- No broad specialist framework rewrite.
- No route coverage expansion beyond the three defects named above.

## Implementation Plan

Detailed execution plan:

`docs/superpowers/plans/2026-04-30-runtime-parity-critical-fixes.md`

Summary:

1. Add a failing import regression test for `src.memory.memory_weave`.
2. Add `memory_weave` to `DB_PATHS` using the existing centralized DB path
   pattern.
3. Add a failing specialist-router test proving code queries route to the code
   specialist.
4. Fix the router result for code/programming queries without changing other
   route priorities.
5. Add a failing `/unified` route guard test using a Flask app with a supervisor
   shim that lacks `handle_unified_request`.
6. Add or preserve the route guard in `src/api/streaming_routes.py`.
7. Run focused tests in legacy.
8. Sync only the allowed source/test files to the migrated runtime workspace.
   Include `news_routes.py` and `domain_news_monitor.py` if migrated test
   collection fails because `src/api/__init__.py` imports `news_bp`.
9. Run focused tests and live route smoke from the migrated runtime workspace.

## Acceptance Tests

- Test: `/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py -q --tb=short`
  - Expected result: passes, and importing `src.memory.memory_weave` does not raise `ValueError`.
- Test: `/opt/homebrew/bin/python3.12 -m pytest tests/test_specialist_router.py -q --tb=short`
  - Expected result: code/programming query routes to the code specialist identifier used by the app.
- Test: `/opt/homebrew/bin/python3.12 -m pytest tests/test_unified_route.py -q --tb=short`
  - Expected result: `/unified` returns `501` with a clear JSON error when the supervisor lacks `handle_unified_request`.
- Test: `/opt/homebrew/bin/python3.12 -m pytest tests/test_default_web_chat_mode.py -q --tb=short`
  - Expected result: still passes, proving the P2 stream default remains intact.

## Smoke Test

Run from migrated runtime workspace after sync:

```bash
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app
./kitty status
curl -sS -o /tmp/kitty_brief_smoke.json -w '%{http_code}' http://localhost:5001/api/brief
curl -sS -o /tmp/kitty_command_smoke.json -w '%{http_code}' -X POST http://localhost:5001/api/command -H 'Content-Type: application/json' -d '{"command":"/stuck"}'
curl -sS -o /tmp/kitty_caps_smoke.json -w '%{http_code}' http://localhost:5001/api/capabilities
```

Expected result:

- `./kitty status` reports running from `kitty-system/kitty-app`.
- Brief, command, and capabilities curls return `200`.
- `/health` and `/api/health` may return `404` unless `KITTY_ENABLE_INTERNAL_API=1`.
  Do not edit launch scripts under this spec.

## Validation Commands

Legacy focused validation:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py tests/test_default_web_chat_mode.py -q --tb=short
```

Expected:

- Exit code: 0
- Required output: all selected tests pass.

Migrated focused validation after sync:

```bash
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py tests/test_default_web_chat_mode.py -q --tb=short
```

Expected:

- Exit code: 0
- Required output: all selected tests pass.

Optional full gate if focused validation is green and runtime remains stable:

```bash
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app
scripts/run_phase4_merge_gate.sh --project /Users/jacobbrizinski/Projects/kitty-system/kitty-app --port 5001
```

Expected:

- Exit code: 0
- Generated Phase 4 merge-gate report shows full suite and route smoke pass.

## Rollback Plan

Rollback steps:

1. In legacy, revert only:
   - `src/core/db_config.py`
   - `src/core/specialists/router.py`
   - `src/api/streaming_routes.py`
   - `tests/test_memory_weave.py`
   - `tests/test_specialist_router.py`
   - `tests/test_unified_route.py`
2. Copy the reverted source/test files back to the migrated runtime workspace if
   sync already happened.
3. Re-run the focused validation command.
4. Leave `specs/runtime-parity-critical-fixes.spec.md` and the completion
   report in place unless the spec itself is superseded.

## Risk Notes

- Adding `memory_weave` to `DB_PATHS` may create a new SQLite file when
  `MemoryWeave` initializes. This is expected runtime behavior but generated DB
  files must not be committed.
- Specialist router string identifiers must match the caller's expectations.
  Tests should lock the actual identifier before implementation changes.
- `/unified` should fail closed with a clear `501`, not hide broader route bugs.
- Migrated workspace edits require explicit sync evidence because that path has
  no git metadata.

## Completion Report

Verification date: **2026-04-30**.

### Files changed in legacy

- `src/core/specialists/router.py` now returns `KittyCoder` for code/programming keywords instead of `alex`.
- `tests/test_specialist_router.py` now locks that routing behavior.
- `tests/test_memory_weave.py` verifies `src.memory.memory_weave` imports with a configured `memory_weave.db` path.
- `tests/test_unified_route.py` verifies `/unified` returns a controlled `501` when the web supervisor shim lacks `handle_unified_request`.
- `docs/audits/project-context-audit-20260430.md` was corrected: health 404 is an internal API gate, not stale code.

Already present before Codex implementation:

- `src/core/db_config.py` already contained `"memory_weave": DATA_ROOT / "memory_weave.db"`.
- `src/api/streaming_routes.py` already contained the `/unified` 501 guard.

### Files synced to migrated runtime

Copied from legacy to `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`:

- `src/core/db_config.py`
- `src/core/specialists/router.py`
- `src/api/streaming_routes.py`
- `src/api/news_routes.py`
- `src/services/domain_news_monitor.py`
- `tests/test_memory_weave.py`
- `tests/test_specialist_router.py`
- `tests/test_unified_route.py`

The news route and service were included because migrated `src/api/__init__.py`
already imported `news_bp`, but the route file and service dependency were
missing, causing migrated test collection to fail.

### Files intentionally not touched

- `web.py`
- `src/api/__init__.py`
- `kitty-chat/`
- launch scripts
- generated DBs and raw data

### Validation

Focused command:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_memory_weave.py tests/test_specialist_router.py tests/test_unified_route.py tests/test_default_web_chat_mode.py -q --tb=short
```

- Legacy (`/Users/jacobbrizinski/Projects/kitty`): **15 passed, 2 warnings**.
- Migrated (`/Users/jacobbrizinski/Projects/kitty-system/kitty-app`): **15 passed, 2 warnings**.

Full suite:

- Legacy: **365 passed, 2 warnings**.
- Migrated: **365 passed, 2 warnings**.

Synced-file parity check:

- `cmp -s` across the synced files: passed.

### Live smoke

- `./kitty status`: running on port 5001 after one escalated restart.
- `GET /api/brief`: 200.
- `POST /api/command` with `/stuck`: 200.
- `GET /api/capabilities`: 200.
- `GET /health`: 404 by internal API gate.
- `GET /api/health`: 404 by internal API gate.

### Known gaps for later specs

- Decide whether health routes should remain internal-only or become public.
- `KittyCoderSpecialist` depth / LLM wiring vs stub behavior.
- Blueprint parity and broad route coverage.
- Garage UI `:5001` backend URL configuration.
