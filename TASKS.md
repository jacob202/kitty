# Tasks

Last updated: 2026-04-30

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
- Copy-first `kitty-system` workspace created beside the old checkout; migrated path is active and old checkout remains rollback.
- Copied app gate and basic launch smoke passed from `/Users/jacobbrizinski/Projects/kitty-system/kitty-app` on `KITTY_PORT=5002`.
- Phase 4 incoming worker changes enforced and cleared via `docs/PHASE4_MERGE_GATE_2026-04-30.md`.
- Reviewed MCP-agent lane triage/spec-first reconciliation completed (no MCP expansion adopted).
- `src/tools/image_gen.py` diff reviewed and adopted.
- Migration lane started with refreshed copy-first sync, preflight `READY`, copied-app gate pass (`92 passed`), and launch validation on port 5004.
- Phase 4 merge gate rerun completed from migrated runtime path; full suite `348 passed`, focused route suite `22 passed`, and route smoke returned HTTP 200 for `/api/brief`, `/api/command`, and `/api/chat`.
- Phase 4 merge-gate automation script added and validated: `scripts/run_phase4_merge_gate.sh` (full run passed against `kitty-system/kitty-app` and wrote `docs/PHASE4_MERGE_GATE_RUN_2026-04-30_114555.md`).
- Phase 4 merge gate re-run **PASS** on migrated app (`kitty-system/kitty-app`, port **5001**): `docs/PHASE4_MERGE_GATE_RUN_2026-04-30_goahead.md` (2026-04-30, cursor).
- `runtime-001` / `specs/runtime-parity-critical-fixes.spec.md` **completed** and verified on legacy + migrated focused tests (2026-04-30, cursor closeout).

## Next Smallest Action

- For every incoming Phase 4 worker change, run `scripts/run_phase4_merge_gate.sh --project /Users/jacobbrizinski/Projects/kitty-system/kitty-app --port 5001` and only merge/checkpoint on pass.

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

## Archive

The imported snapshot that previously lived here duplicated **Verified Done** milestones and used broken markdown (`##!`, trailing `__`). It was removed **2026-04-30** to avoid drift and contradictions with **Next smallest action** above. Narrative backlog and infra notes remain in `docs/TASKS.md` (does not override `CURRENT_FOCUS.md`).
