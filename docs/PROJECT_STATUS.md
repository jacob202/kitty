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

## Test State (2026-07-02)

```
Local: ~1010 passed, 2 failed, 1 skipped, 2 deselected
```

Known local-only failures (pass on CI — tests leak real local `data/` state):

- `tests/test_action_queue.py::test_t0_executes_from_proposed_and_records_result`
- `tests/test_state_composer.py::test_real_sources_compose_against_isolated_stores`

Known collection error:

- `tests/test_llm_client_alt_ua.py` — untracked file importing a function that doesn't exist; skip with `--ignore` or delete.

## Runtime Shape

- Gateway: FastAPI on `127.0.0.1:8000`
- LiteLLM proxy: `127.0.0.1:8001`
- Data: `data/kitty/kitty.db` (SQLite), `data/chroma/` (vectors), `data/inbox.jsonl` (capture)
- Start: `./kitty up` | Stop: `./kitty down` | Health: `./kitty doctor --json`

## Active Technical Debt

| Issue                                          | Location                                                      | Priority                          |
| ---------------------------------------------- | ------------------------------------------------------------- | --------------------------------- |
| `test_llm_client_alt_ua.py` collection error   | `tests/` (untracked)                                          | Medium — delete or fix            |
| Test isolation leaks (2 tests read real data/) | `tests/test_action_queue.py`, `tests/test_state_composer.py`  | Medium — red locally, green on CI |
| Stale worktrees + branches for merged PRs      | `.claude/worktrees/feat-*`, `.worktrees/gateway-deepening`    | Low — prune                       |
| Uncommitted workflow configs                   | `.pre-commit-config.yaml`, `.prettierrc`, `dependabot.yml`, … | Medium — commit or discard        |
| Nested foreign repo                            | `hermes-webui/`                                               | Medium — move out of kitty        |
| SIRI_SHORTCUT.md references dead launcher      | `docs/SIRI_SHORTCUT.md`                                       | Low — tombstone it                |
| Local-only branch not pushed to origin         | `backup-local-main-0628`                                      | Medium — at risk of loss          |

## What's Next

See `docs/packets/README.md` for the packet queue (001–013). Remaining:

1. Packet 004: state home surface (spec-complete, unblocked)
2. Packet 007: delegation packet generator (unblocked — 003 + 012 shipped)
3. Packet 008 remainder: expert retrieval (routes landed in #73)
4. Packet 005: mail connector — blocked on Jacob's §16.2 decision (Apple Mail vs Gmail API)

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
