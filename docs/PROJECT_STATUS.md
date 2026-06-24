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

A 6-phase, ~10–14 working day plan addressing 15 frictions + 2 sub-frictions across `gateway/`. Each phase is independently shippable; tests must stay green at every phase gate. **Phase 0 and Phase 1 have landed.**

- Design doc: `docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md` (committed, `status: ACCEPTED`)
- D7 amendment: `storage_router.py` may add registration, validation, migration triggers, and telemetry. Generic verbs, smart routing, and dict-like adapter tables remain ruled out. See `docs/DECISIONS.md`.
- Resolved in the spec: (1) Phase 1 first, then Phase 4, sequential not parallel; (2) keep `context_builder.py` as thin façade for one release; (3) all 6 `try/except → mock` routes are violations — Phase 3 removes all 6. Route dedup is out of scope (UI-touching).
- **Phase 0 landed** (commits `521cdfe`, `562d99c`, `8ea0b72`): http_client loop-bound re-init harden + 3 new tests (friction 13), `routes/chat.py` deletion (friction 3), silent-swallow logging audit across 18 sites, f-string→%s conversion across 28 sites, `.claude/settings.local.json` → `.claude/settings.local.example.json` split.
- **Phase 1 landed** (commits `2d8feb9`, `4413395`): new `gateway/storage_sync.py` (merge of `sync.py` + `storage_io.py`, +225 lines); `sync.py` and `storage_io.py` deleted; `storage_router.py` deepened with typed accessors, validation, telemetry, registration (+100 lines); `plugin_registry.py` legacy JSON mirror removed; `inbox_watcher.py` uses `paths.INBOX_FILE`. New tests: `test_storage_router_depth.py` (11 tests, 157 lines, all green in 0.7s) + `test_storage_sync.py` (9 tests, includes slow mem0 path).
- **Next: Phase 2** (read-path unification, highest-risk phase per the spec, budget 4 days): collapse `memory_graph` + `context_enrichment` + `context_builder` into a new `context_assembler.py`. Adapters return uniform `Item`; failures surface as `Warning` (not silent skip); voice-gate stays out of the request-time path.

## Open Dirty Work

- `codex/raycast-quick-capture` still holds useful unmerged Raycast wrapper work at `5a07744`.
- `docs/superpowers/specs/2026-06-20-workflow-optimization-rollout.md` is a planning artifact with `status: PARTIALLY_IMPLEMENTED` — 5 done, 6 partial, 4 pending. See the in-doc status table.
- Older stashes remain for memory-graph and routing experiments; the current inventory is in `.agent/stash_audit.md`.
- **Skills consolidation remaining (post-Sub-Issue 3):** Sub-Issue 4 (## Flow on tdd-loop, catchup, debug-fix), 5 (trigger sharpening on deep-review), 6 (global sync verification). Skipping `phase-runner` and `phase-swarm` (deleted in Phase 1, deferred per the design's open question).

## Known Risks

- Runtime state is still spread across JSON, JSONL, SQLite, ChromaDB, and mem0.
- Claude local overrides can still drift per machine; canonical repo guidance now lives in `.claude/settings.json`, with `.claude/settings.local.json` ignored and `.claude/settings.local.example.json` as the checked-in shape.
- `gateway/inbox_watcher.py` depends on the iCloud inbox path existing on this Mac; the app should still run without it, but the feature is host-specific.
- **Pre-commit hook no longer runs pytest** (commit `a79d4ee`). Commits are instant, but the safety net is gone — devs must run `make test` (fast slice) or `make test-full` (everything, includes mem0/network/I/O) explicitly before pushing.

## Recent Commits (local, unpushed)

- `a79d4ee` chore(workflow): make commits instant — skip slow tests in pre-commit, add slow marker
- `e5b63b5` fix(kitty-chat): fail loud on chat persistence
- `948136d` docs(refresh): status + handoff for Phase 0+1 landing
- `225e648` docs(specs): skills consolidation 2C done — deep-review skill created
- `4413395` Merge branch 'phase-1-storage-substrate' into codex/phase-4-workflow
- `2d8feb9` feat(arch): phase 1 storage substrate deepening
- `704919e` docs(specs): skills consolidation execution log — phase 1, 2A, 2B done
- `4939c66` chore(gitignore): ignore claude worktrees
- `fe3a294` docs(specs): accept skills consolidation; mark workflow optimization as partial
- `905582e` docs(arch): reflect Phase B/C shipped, D7 in place, deepening accepted
- `0a028f4` docs(refresh): status + handoff for Phase 0 landing
- `562d99c` chore(routes): drop unused chat shim (also commits the deepening-program design doc, `status: ACCEPTED`)
- `521cdfe` fix(http): reset shared client on loop switch (Phase 0 friction 13; new `test_http_client.py` with 3 tests)
- `8ea0b72` perf(gateway): audit depth — fix silent swallows, f-string logging, structure leaks
- `599e08f` docs(refresh): D7 amendment + status/handoff for deepening program
- `536731d` docs(refresh): handoff + status for f15697d
- `f15697d` chore(workflow): phase 4 doc + hook refresh
- `ada0438` docs(refresh): re-anchor phase 4 status
- `7236483` fix(workflow): harden inbox watcher polling

Branch is in sync with origin (`a79d4ee` is the latest push).

## Verification

- `make test` (fast slice, default — skips `@pytest.mark.slow`): expected `~691 passed, 2 deselected` (was 687 pre-Phase-1 + 11 router_depth − 7 slow-marked = 691). Run before each push.
- `make test-full` (everything, includes real mem0 / network / I/O): expected `~698 passed, 2 deselected` once the slow path is exercised. The first `test_storage_sync` test alone takes ~23s.
- `python3.12 -m pytest tests/test_storage_router_depth.py -v`: confirmed green, 11 tests in 0.7s.
- `python3.12 -m pytest tests/test_storage_sync.py::test_export_all_returns_expected_top_level_shape -v`: confirmed green, 1 test in 23.4s.
- `./kitty status` currently shows gateway and LiteLLM stopped.
- `./kitty doctor --json` currently reports 7 PASS / 1 WARN / 2 FAIL; the 2 FAIL entries are the stopped gateway and LiteLLM services.

## Next Best Step

Phase 0 and Phase 1 are landed. Next: **Phase 2** (read-path unification, highest-risk phase, budget 4 days). When each Phase 2 commit lands, run `pytest tests/test_context_assembler.py` and the full suite (with patience for the storage_sync mem0 path), update "Recent Commits" and "Verification" with the new hash and test count, and inspect the diff for D7 compliance. The live `./kitty up` end-to-end check returns once Phase 2 lands.
