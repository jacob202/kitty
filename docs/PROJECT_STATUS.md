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

A 6-phase, ~10–14 working day plan addressing 15 frictions + 2 sub-frictions across `gateway/`. Each phase is independently shippable; tests must stay green at every phase gate. **Phase 0 has landed.**

- Design doc: `docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md` (committed, `status: ACCEPTED`)
- D7 amendment: `storage_router.py` may add registration, validation, migration triggers, and telemetry. Generic verbs, smart routing, and dict-like adapter tables remain ruled out. See `docs/DECISIONS.md`.
- Resolved in the spec: (1) Phase 1 first, then Phase 4, sequential not parallel; (2) keep `context_builder.py` as thin façade for one release; (3) all 6 `try/except → mock` routes are violations — Phase 3 removes all 6. Route dedup is out of scope (UI-touching).
- **Phase 0 landed** (commits `521cdfe`, `562d99c`, `8ea0b72`): http_client loop-bound re-init harden + 3 new tests (friction 13), `routes/chat.py` deletion (friction 3), silent-swallow logging audit across 18 sites, f-string→%s conversion across 28 sites, `.claude/settings.local.json` → `.claude/settings.local.example.json` split. Test count: 687.
- **Next: Phase 1** (storage substrate): deepen `storage_router.py`, merge `sync.py` + `storage_io.py`, route writes through `StorageRouter`.

## Open Dirty Work

- `codex/raycast-quick-capture` still holds useful unmerged Raycast wrapper work at `5a07744`.
- `docs/superpowers/specs/2026-06-20-workflow-optimization-rollout.md` is still a planning artifact with `status: PENDING_APPROVAL`.
- The working tree has one in-flight edit: `gateway/litellm_config.yaml` adds a "Wafer AI" provider (deepseek-v4-flash / deepseek-v4-pro via `os.environ/WAFER_API_KEY`). **Not in the deepening-program plan; the plan forbids new services.** Decide whether this is in scope before committing.
- Older stashes remain for memory-graph and routing experiments; the current inventory is in `.agent/stash_audit.md`.

## Known Risks

- Runtime state is still spread across JSON, JSONL, SQLite, ChromaDB, and mem0.
- Claude local overrides can still drift per machine; canonical repo guidance now lives in `.claude/settings.json`, with `.claude/settings.local.json` ignored and `.claude/settings.local.example.json` as the checked-in shape.
- `gateway/inbox_watcher.py` depends on the iCloud inbox path existing on this Mac; the app should still run without it, but the feature is host-specific.

## Recent Commits (local, unpushed)

- `562d99c` chore(routes): drop unused chat shim (also commits the deepening-program design doc, `status: ACCEPTED`)
- `521cdfe` fix(http): reset shared client on loop switch (Phase 0 friction 13; new `test_http_client.py` with 3 tests)
- `8ea0b72` perf(gateway): audit depth — fix silent swallows, f-string logging, structure leaks
- `599e08f` docs(refresh): D7 amendment + status/handoff for deepening program
- `536731d` docs(refresh): handoff + status for f15697d
- `f15697d` chore(workflow): phase 4 doc + hook refresh
- `ada0438` docs(refresh): re-anchor phase 4 status
- `7236483` fix(workflow): harden inbox watcher polling

Push is intentionally deferred per the new policy in `f15697d` ("do not push unless explicitly asked").

## Verification

- `python3.12 -m pytest tests/test_inbox_watcher.py tests/test_status_glance.py -q --tb=short` passed: 7 tests.
- `python3.12 -m pytest tests/ -q --tb=short` passed: 687 passed, 2 deselected, 4 warnings.
- `./kitty status` currently shows gateway and LiteLLM stopped.
- `./kitty doctor --json` currently reports 7 PASS / 1 WARN / 2 FAIL; the 2 FAIL entries are the stopped gateway and LiteLLM services.

## Next Best Step

Phase 0 is landed. Next: **Phase 1** (storage substrate). After each Phase 1 commit lands, run the test suite, update "Recent Commits" and "Verification" with the new hash and test count, and inspect the diff for D7 compliance (no generic verbs, no dict-like adapter tables, no smart routing). The live `./kitty up` end-to-end check returns once Phase 1 lands.
