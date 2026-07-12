# Project Status

**Date:** 2026-07-12
**Branch:** `feat/council-routing` (based on `main`)
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
| Phase 3–5 product       | Chat, brief, memory, settings polish; merged to main         | ✓ Shipped (#14f5865) |
| Gateway deepening       | Route consolidation, fail-loud, duplicate route contracts     | ✓ Shipped (#569608b) |
| Builder improvements    | Queue, run-loop safety rails, initiative doctor preflight     | ✓ Shipped            |
| Fail-loud sweep         | Verifier false-green, enrichment markers, model discovery     | ✓ Shipped (Card C)   |

## Open PR

- **#164** (draft) — fail-loud sweep, doc reconciliation, CI coverage 65%, route tests (5 modules)

Recent merged PRs: #162 (memory persistence), #156 (GitHub connector),
#155 (imagegen v2), #154 (phone-native console), #153 (Magic Kitty),
#152 (chat-log idea mine), #150 (UI polish + reliability fixes).

## Test State (2026-07-12)

```
Collected: 2036 (2 deselected; test_council.py excluded — new, not yet wired)
Fail-loud suite: 24 passed
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
| ---------------------------------------------- | ------------------------------------------------------------ | --------------------------------─ |
| Codex Blocker #1 (proxy SSRF)                  | `gateway/kitty-chat/src/app/proxy/`                          | T2 — escalate to Jacob            |

### Resolved 2026-07-05

- `npm run` exits 194 silently — **fixed** in `gateway/kitty-chat/.npmrc` with
  `script-shell=/bin/sh` (npm 11.17 spawn-ELOOP on default shell). `npm test`
  and `npm run build` both exit 0 and pass.
- 6 UI test failures — **stale**. All 85 UI tests pass via `npm test`. The
  6-failures claim was from 2026-07-02; current count is 14 files, 85 tests, 0 fails.

### Resolved 2026-07-12

- Verifier false-green — **fixed** (#569608b)
- Duplicate route contracts — **fixed** (#569608b)
- Fail-loud violations (model discovery, next-step prefs, brief enrichment) — **fixed** (#569608b, context_enrichment)
- Coverage threshold was 10% — **bumped to 65%** (PR #164)
- 5 route modules had zero HTTP tests — **128 tests added** (PR #164)

## What's Next

1. Codex Blocker #1 (T2, escalate) — proxy SSRF in kitty-chat
2. Route test coverage — 11 route modules still have zero HTTP-layer tests (5 done in PR #164)

## Sources of Truth

| Need                | File                     |
| ------------------- | ------------------------ |
| Orientation         | `START_HERE.md`          |
| Architecture        | `docs/ARCHITECTURE.md`   |
| Settled decisions   | `docs/DECISIONS.md`      |
| Hard lessons        | `docs/LEARNINGS.md`      |
| Handoff             | `.claude/HANDOFF.md`     |
| Work queue          | `docs/packets/README.md` |
| Voice/persona       | `config/SOUL.md`         |
| Agent/runtime rules | `docs/AGENT_RUNTIME.md`  |
