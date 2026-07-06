# Project Status

**Date:** 2026-07-02
**Branch:** `main`
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`

## What's Shipped

| Phase                   | Description                                                  | Status               |
| ----------------------- | ------------------------------------------------------------ | -------------------- |
| Phase B (B0–B5)         | Storage consolidation, SQLite seam, storage router           | ✓ Shipped            |
| Phase C chats (C0–C6)   | Chat sessions migrated to SQLite                             | ✓ Shipped            |
| Phase C journal (B0–B6) | Journal migrated to SQLite                                   | ✓ Shipped            |
| Phase E                 | PWA seam (manifest, service worker, install banner)          | ✓ Shipped            |
| Memory loop             | Session stop hook + recall-thread readback + /remember skill | ✓ Shipped (#48)      |
| Mypy gate               | 80 gateway mypy errors cleared; typecheck now blocks CI      | ✓ Shipped (#51)      |
| Session persistence     | Chat sessions survive restart; SOUL reads real config        | ✓ Shipped (#765caa3) |
| Startup preflight       | Reliable preflight runs on `./kitty up`                      | ✓ Shipped (#50)      |

## Open PR

None. The 2026-07-02 swarm merged #70–#77 (gateway deepening, resume script,
privacy boundary, knowledge routes, capture, de-fake, brief scheduler, signal
wiring). #70 merged with red checks after #75/#77 and broke main; the
reconcile fix repaired it. PR #78 was closed unmerged as obsolete.

## Test State (2026-07-05)

```
Local: 1120 passed, 1 skipped, 2 deselected, 4 warnings
```

The 2026-07-02 entries for `test_action_queue.py::test_t0_executes_from_proposed_and_records_result`,
`test_state_composer.py::test_real_sources_compose_against_isolated_stores`, and the untracked
`tests/test_llm_client_alt_ua.py` are no longer reproducible — both tests pass and the untracked
file is gone. If the failures recur, re-isolate them with `tmp_path` fixtures (see
`tests/test_env_loader.py` for the pattern).

## Runtime Shape

- Gateway: FastAPI on `127.0.0.1:8000`
- LiteLLM proxy: `127.0.0.1:8001`
- Data: `data/kitty/kitty.db` (SQLite), `data/chroma/` (vectors), `data/inbox.jsonl` (capture)
- Start: `./kitty up` | Stop: `./kitty down` | Health: `./kitty doctor --json`

## Active Technical Debt

| Issue                                          | Location                                                     | Priority                          |
| ---------------------------------------------- | ------------------------------------------------------------ | --------------------------------- |
| No kitty-chat CI job                           | `.github/workflows/`                                         | High — add a UI test job          |
| Test isolation leaks (2 tests read real data/) | `tests/test_action_queue.py`, `tests/test_state_composer.py` | Medium — red locally, green on CI |
| SIRI_SHORTCUT.md references dead launcher      | `docs/SIRI_SHORTCUT.md`                                      | Low — tombstone it                |

### Resolved 2026-07-05

- `npm run` exits 194 silently — **fixed** in `gateway/kitty-chat/.npmrc` with
  `script-shell=/bin/sh` (npm 11.17 spawn-ELOOP on default shell). `npm test`
  and `npm run build` both exit 0 and pass.
- 6 UI test failures — **stale**. All 85 UI tests pass via `npm test`. The
  6-failures claim was from 2026-07-02; current count is 14 files, 85 tests, 0 fails.

## What's Next

All open work has authored, executor-ready packets (2026-07-03). Execution
order per `docs/packets/README.md`: **014 → 004 → 005 → 007 → 008-remainder.**

1. Packet 014: make the gates honest (UI tests, CI job, isolation leaks) — mechanical, do first
2. Packet 004: console home — active phase, plan at `docs/superpowers/specs/2026-07-02-console-home-phase-design.md`
3. Packet 005: Gmail read-only connector (D11) — Jacob owns the OAuth setup
4. Packet 007: delegation packet generator
5. Packet 008 remainder: collections/tags + expert retrieval (items 1–3 landed in #73)

## Sources of Truth

| Need                | File                     |
| ------------------- | ------------------------ |
| Orientation         | `START_HERE.md`          |
| Architecture        | `docs/ARCHITECTURE.md`   |
| Settled decisions   | `docs/DECISIONS.md`      |
| Hard lessons        | `docs/LEARNINGS.md`      |
| Handoff             | `docs/AGENT_HANDOFF.md`  |
| Work queue          | `docs/packets/README.md` |
| Voice/persona       | `config/SOUL.md`         |
| Agent/runtime rules | `docs/AGENT_RUNTIME.md`  |
