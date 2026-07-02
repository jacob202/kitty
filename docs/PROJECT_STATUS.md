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

**PR #65** — autonomous action queue + calendar write + tier sheet

- `action_queue.py`, `routes/actions.py`, `009_actions.sql`
- `calendar.event.create` T2 executor
- `config/action_tiers.json` (Jacob's tier sign-off is the merge blocker)
- Packets 004 and 007 are both stacked on this PR

## Test State (2026-07-02)

```
803 passed, 4 failed, 1 skipped, 2 deselected, 4 warnings
```

Known failures:

- `tests/test_check_continuity_state.py` — 4 tests fail when `docs/AGENT_HANDOFF.md` has a stale or missing date. Fixed by updating the handoff doc.

Known collection error:

- `tests/test_llm_client_alt_ua.py` — 1 file fails to collect; skip with `--ignore` or fix the import.

## Runtime Shape

- Gateway: FastAPI on `127.0.0.1:8000`
- LiteLLM proxy: `127.0.0.1:8001`
- Data: `data/kitty/kitty.db` (SQLite), `data/chroma/` (vectors), `data/inbox.jsonl` (capture)
- Start: `./kitty up` | Stop: `./kitty down` | Health: `./kitty doctor --json`

## Active Technical Debt

| Issue                                        | Location                                                      | Priority                          |
| -------------------------------------------- | ------------------------------------------------------------- | --------------------------------- |
| Fake data in loops + insights routes         | `gateway/routes/loops.py:12`, `gateway/routes/insights.py:12` | High — violates non-negotiable #1 |
| `test_llm_client_alt_ua.py` collection error | `tests/`                                                      | Medium                            |
| SIRI_SHORTCUT.md references dead launcher    | `docs/SIRI_SHORTCUT.md`                                       | Low — tombstone it                |
| Local-only branches not pushed to origin     | `codex/raycast-quick-capture`, `backup-local-main-0628`       | Medium — at risk of loss          |

## What's Next

See `docs/packets/README.md` for the packet queue (001–013). The immediate sequence:

1. Jacob signs tier sheet → merge PR #65 (packet 003)
2. Packet 004: mascot state + de-fake loops/insights
3. Packet 006: project resume (drafted — see `docs/packets/006-project-resume.md`)
4. Packet 008: GitHub read-only connector (can start anytime)

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
