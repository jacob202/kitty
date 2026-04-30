# Tasks

Last updated: 2026-04-29

## Verified Done

- Phase 0/1 control docs, intake, builder contract, file governance, context pack.
- Phase 3 runtime utilities now have passing tests and live route wiring:
  - `/api/brief`
  - `/api/command` with `/stuck`
  - task/done tracking modules
- Phase 4 chat-log consolidation tests pass.
- Phase 5 response quality critic tests pass.
- Phase 6 memory/vector/specialist focused tests pass.
- Phase 6+ security scanner pure utility implemented and tested.
- Phase 6+ builder write/command security enforcement implemented and tested.
- Phase 6+ eval dashboard backend implemented and tested.
- Live route smoke completed for `/api/brief` and `/api/command`.
- Live `/api/chat` empty-response bug fixed and smoke-tested.
- Chat-log consolidation dry-run processed `data/sessions` without errors.
- Chat-log consolidation CLI implemented and verified: `20 passed`.
- Control gates verified after builder security enforcement: `83 passed`.
- Full suite verified: `333 passed, 2 warnings`.
- Tiny generated-cache cleanup completed under `specs/tiny-generated-cache-cleanup.spec.md`.
- Builder security enforcement verified: `53 passed`.
- Gemini/chat-log candidate intake imported and reviewed; weak assistant-authored claims were demoted to open loops or rejected/noisy.
- Eval dashboard UI panel spec written, component implemented in Garage UI, and failed-check object rendering fixed.
- `/api/chat` real provider response implementation completed (fallback logic improved and errors passed clearly).
- Gemini/chat-log candidates reviewed; only durable preferences/safety rules were accepted, and uncertain items remain open loops.
- `./kitty status` command fixed to correctly report server state based on port 5001 usage.
- UI panel regression coverage added for eval dashboard failed-check rendering (using Vitest and React Testing Library).
- MCP agent bundle exists in the dirty tree but is unverified, out of phase, and blocked by current focus; import smoke tests currently fail on missing optional dependencies.
- Copy-first `kitty-system` workspace created beside the old checkout; old checkout remains authoritative until launch verification passes.
- Copied app gate and basic launch smoke passed from `/Users/jacobbrizinski/Projects/kitty-system/kitty-app` on `KITTY_PORT=5002`.

## Next Smallest Action

- Finalize the release candidate checkpoint (Phase E deliverables complete). Await user approval before moving to `kitty-system` repo migration or reviewing parked MCP agents.
- For incoming Phase 4 worker changes, enforce `docs/PHASE4_MERGE_GATE_2026-04-30.md` before any merge/checkpoint.

## Delegation Queue

- Cleanup worker: only read-only/spec-first for remaining candidates; do not clean protected-tree metadata or tracked deletions.

## Blocked Without New Spec

- physical `kitty-system/kitty-app` repo move
- memory migration beyond current focused modules
- QLoRA/model training
- MCP expansion
- proactive idle nudging
- UI polish
- deletion of raw chat logs
- deletion inside protected `src/` paths for metadata files without waiver

---

# Previous Imported Tasks

Last updated: 2026-04-28#

This file is the control-layer task list for the current Kitty stabilization pass.#

## Done##!

- Phase 0 — Structural separation and control files ✅__
- Phase 1 — Intake and builder contract ✅__
- Phase 2 — P0 Stabilization and Gates ✅__
- Phase 3 — Core Runtime Utility ✅__
  - Morning brief module (10 tests pass)__
  - Task tracker + done handler (10 tests pass)__
  - /stuck command (6 tests pass)__
  - All specs created: morning-brief, task-tracker, stuck-command__
- Phase 3+4 Wiring ✅__
  - Morning brief route (brief_bp) — 3/3 tests pass)__
  - Commands route (commands_bp) — 4/4 tests pass)__
  - Blueprints registered in `src/api/__init__.py`__
- Phase 4 — Consolidation and Cleanup ✅__
  - Chat log consolidation pipeline (15 tests pass)__
  - Spec: chat-log-consolidation.spec.md__
  - Report template: docs/CHAT_LOG_CONSOLIDATION_REPORT.md__
- Phase 5 — Skills and Quality ✅__
  - Response quality critic (10 tests pass)__
  - Self-correction skill exists (SKILL.md)__
  - Spec: quality-critic.spec.md__
- Phase 6 — Memory and Source-Grounded Specialist ✅__
  - Vector store (8 tests pass)__
  - Specialist router (7 tests pass)__
  - Specialist validator (5 tests pass)__
  - Memory inspect/forget (5 tests pass)__
  - KittyCoderSpecialist (4 tests pass)__
  - Specs: memory-vector-store, memory-inspect, goose-phase6-stack__
- Phase 6+ — Transparent Evals Dashboard ✅__
- Phase 6+ — Security Scanning of Builder Output ✅__

## In Progress##!

- None.

## Next Smallest Action##!

1. **Run full test suite** — confirm 204+ tests passing.
2. **Test wired routes** — use `curl` to verify /api/brief and /api/command work. 
3. **Chat log consolidation** — run dry-run on `data/sessions/`, review, write report. 
4. **Delegate to Goose** — fix authentication issue, then delegate Phase 6+ tasks. 

## Blocked Without New Spec##!

- `/stuck` runtime integration (wired, needs testing)__
- deterministic `/api/brief` route changes (wired, needs testing)__
- task/done tracking integration (wired, needs testing)__
- memory migration__
- physical `kitty-system/kitty-app` repo move__
- source-tree cleanup under protected paths__

## Delegation Queue##!

- Gemini: canonical chat-log intake using `docs/GEMINI_CHAT_LOG_INTAKE.md`. 
- Read-only scout: `/stuck` route/dispatch/test surface. 
- Read-only scout: deterministic brief route/socket/test surface. 
- Read-only scout: task/done tracking storage/dispatch/test surface. 
- Cleanup scout: keep `docs/CLEANUP_CANDIDATES.md` current; do not delete files.#

## Related Backlog##!

Older product backlog lives in `docs/TASKS.md`. It does not override `CURRENT_FOCUS.md`. 
