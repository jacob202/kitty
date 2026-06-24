# Project Status

**Date:** 2026-06-24
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`
**Current branch:** `codex/phase-4-workflow`
**Base:** `cfa440f`

## Current Product State

Kitty is a local-first companion with a FastAPI gateway, LiteLLM proxy, and Next.js UI. Phase B is shipped. Phase C chats and journal are shipped and backed by `data/kitty/kitty.db`. The current branch adds Phase 4 workflow polish: PR description CI, an iCloud inbox watcher that ingests voice-note markdown into `data/inbox.jsonl`, a lightweight `/status/glance` endpoint, and pre-commit test-status caching for glance consumers.

## Current Priority

Workflow polish and source-of-truth cleanup. Do not add cloud auth, push notifications, new agent dashboards, or new storage systems while the operating story still has local rough edges.

## Open Dirty Work

- `codex/raycast-quick-capture` still holds useful unmerged Raycast wrapper work at `5a07744`.
- `docs/superpowers/specs/2026-06-20-workflow-optimization-rollout.md` is still a planning artifact with `status: PENDING_APPROVAL`.
- Older stashes remain for memory-graph and routing experiments; the current inventory is in `.agent/stash_audit.md`.

## Known Risks

- Runtime state is still spread across JSON, JSONL, SQLite, ChromaDB, and mem0.
- `.claude/settings.local.json` is tracked and contains machine-local permissive settings (`bypassPermissions` plus absolute-path allowances). Review before treating it as canonical repo config.
- `gateway/inbox_watcher.py` depends on the iCloud inbox path existing on this Mac; the app should still run without it, but the feature is host-specific.

## Recent Commits (local, unpushed)

- `f15697d` chore(workflow): phase 4 doc + hook refresh
- `ada0438` docs(refresh): re-anchor phase 4 status
- `7236483` fix(workflow): harden inbox watcher polling

Push is intentionally deferred per the new policy in `f15697d` ("do not push unless explicitly asked").

## Verification

- `python3.12 -m pytest tests/test_inbox_watcher.py tests/test_status_glance.py -q --tb=short` passed: 7 tests.
- `python3.12 -m pytest tests/ -q --tb=short` passed: 684 passed, 2 deselected, 4 warnings.
- `./kitty status` currently shows gateway and LiteLLM stopped.
- `./kitty doctor --json` currently reports 7 PASS / 1 WARN / 2 FAIL; the 2 FAIL entries are the stopped gateway and LiteLLM services.

## Next Best Step

Run an end-to-end live check of `./kitty up`, `/status/glance`, and the iCloud inbox flow on Jacob's machine. After that, this branch is close to ship-ready. The tracked-local-Claude-runtime-file question was settled in `f15697d` (front-door reading order codified, hook surface hardened, push policy flipped).
