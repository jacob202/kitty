# Project Status

**Date:** 2026-07-16
**Branch:** `chore/engineering-leverage-phase-8-9` (local PR branch)
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

The Engineering Leverage + Builder Phase 2 integrity branch is locally
review-ready. It has not been pushed and no remote PR has been created.

Recent merged PRs: #149 (kittybuilder dogfood preflight), #148 (brief news
source seam), #147 (builder CLI registry), #146 (KB-S5 run-loop).

## Test State (2026-07-16)

```
Full suite: 2241 passed, 1 skipped, 2 deselected, 4 failed before closeout fixes
Branch-caused failures fixed and re-run: tests/test_builder_run.py — 7 passed
Remaining unchanged failure: mail credential-refresh test needs optional google.auth
Builder identity + loop: 65 passed
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
| SIRI_SHORTCUT.md references dead launcher      | `docs/SIRI_SHORTCUT.md`                                      | Low — tombstone it                |
| Codex Blockers #1/#5/#7 (security/worker/mem) | `gateway/kitty-chat/src/app/proxy/`, `gateway/agent_runner.py` | T2 — escalate to Jacob            |

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

## What's Next

1. Review and publish the Engineering Leverage + Builder integrity PR (push requires Jacob approval)
2. Add a read-only Builder status projection before implementing UI controls
3. Execute deferred audit rows D2/A1, A2/H5, and D4/A3 with their recorded evidence gates
4. Codex Blockers #1/#5/#7 (T2, escalate) — security/auth, worker failure states, memory consolidation

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
