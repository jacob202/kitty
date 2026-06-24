# Project Status

**Date:** 2026-06-24
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`
**Current branch:** `codex/phase-4-workflow`
**Base:** `cfa440f`

## Current Product State

Kitty is a local-first companion with a FastAPI gateway, LiteLLM proxy, and Next.js UI. Phase B is shipped. Phase C chats and journal are shipped and backed by `data/kitty/kitty.db`. The current branch adds Phase 4 workflow polish: PR description CI, an iCloud inbox watcher that ingests voice-note markdown into `data/inbox.jsonl`, a lightweight `/status/glance` endpoint, and pre-commit test-status caching for glance consumers.

## Current Priority

Execute the accepted Gateway Architecture Deepening Program (Phases 0 + 1 first) under the same guardrails: no cloud auth, push notifications, new agent dashboards, or new storage systems. The program deepens existing modules only.

## Deepening Program (Accepted 2026-06-24)

A 6-phase, ~7–10 working day plan addressing 17 frictions across `gateway/`. Each phase is independently shippable; 684 tests must stay green at every phase gate.

- Design doc: `docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md`
- D7 amendment: `storage_router.py` may add registration, validation, migration triggers, and telemetry. Generic verbs, smart routing, and dict-like adapter tables remain ruled out. See `docs/DECISIONS.md`.
- Open questions for Jacob (design doc line 386–391): (1) Phase 4 parallelization with Phase 1; (2) `context_builder.py` façade length; (3) confirm the 6 `try/except → mock` routes are not load-bearing.

## Open Dirty Work

- `codex/raycast-quick-capture` still holds useful unmerged Raycast wrapper work at `5a07744`.
- `docs/superpowers/specs/2026-06-20-workflow-optimization-rollout.md` is still a planning artifact with `status: PENDING_APPROVAL`.
- The working tree is currently dirty with in-progress deepening-program gateway edits (Phases 0 + 1) plus the accepted design doc `docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md`; inspect before editing on this shared branch.
- Older stashes remain for memory-graph and routing experiments; the current inventory is in `.agent/stash_audit.md`.

## Known Risks

- Runtime state is still spread across JSON, JSONL, SQLite, ChromaDB, and mem0.
- Claude local overrides can still drift per machine; canonical repo guidance now lives in `.claude/settings.json`, with `.claude/settings.local.json` ignored and `.claude/settings.local.example.json` as the checked-in shape.
- `gateway/inbox_watcher.py` depends on the iCloud inbox path existing on this Mac; the app should still run without it, but the feature is host-specific.

## Recent Commits (local, unpushed)

- `536731d` docs(refresh): handoff + status for f15697d
- `f15697d` chore(workflow): phase 4 doc + hook refresh
- `ada0438` docs(refresh): re-anchor phase 4 status
- `7236483` fix(workflow): harden inbox watcher polling

Push is intentionally deferred per the new policy in `f15697d` ("do not push unless explicitly asked").

## Verification

- `python3.12 -m pytest tests/test_inbox_watcher.py tests/test_status_glance.py -q --tb=short` passed: 7 tests.
- `python3.12 -m pytest tests/ -q --tb=short` passed: 684 passed, 2 deselected, 3 warnings.
- `./kitty status` currently shows gateway and LiteLLM stopped.
- `./kitty doctor --json` currently reports 7 PASS / 1 WARN / 2 FAIL; the 2 FAIL entries are the stopped gateway and LiteLLM services.

## Next Best Step

Wait for Codex to land Phase 0 + Phase 1 of the deepening program as discrete commits (the D7 amendment is in place). After each phase lands, run the test suite, update "Recent Commits" and "Verification" with the new hash and test count, and inspect the diff before allowing the next phase to start. The live `./kitty up` end-to-end check returns once the deepening program has its first commit.
