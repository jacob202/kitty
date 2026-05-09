# Tasks

Last updated: 2026-05-09

## Current Build Plan (Phase 2 Track)

- [x] Phase 2A memory architecture decision + mini bake-off executed.
  - Decision draft: `docs/plans/memory-architecture-decision-2026-05-06.md`
  - Scored bake-off: `docs/audits/memory-architecture-bakeoff-2026-05-06.md`
  - Deferred cognitive features parking: `docs/plans/memory-architecture-deferred-cognitive-features-2026-05-06.md`
- [x] Phase 2A.1 foundation implementation plan created:
  - `docs/superpowers/plans/2026-05-memory-architecture.md`
- [x] Phase 2 orchestration workflow v2 documented:
  - `docs/plans/phase2-orchestration-workflow-2026-05-06.md`
- [x] Phase 2 orchestration workflow token audit completed with session telemetry:
  - `docs/plans/phase2-orchestration-workflow-2026-05-06.md` (actual token deltas + budget controls)
- [x] Continuity tracking standard established for takeover safety:
  - `docs/CONTINUITY_STANDARD.md`
  - `docs/DECISIONS.md` (D-0015)
  - `docs/handoffs/HANDOFF-2026-05-06.md`
- [x] Phase 2A.1 Wave 2 completed:
  - `src/memory/storage_router.py`
  - `src/services/context_service.py` (retrieval routing + `general -> None` fallback)
  - `tests/memory/test_storage_router.py`
  - `tests/services/test_context_service_retrieval_domain_filter.py`
  - focused verification: `16 passed` (`--noconftest`)
- [x] Phase 2A.1 Wave 3 completed:
  - `src/memory/retrieval_adapter.py`
  - `src/memory/storage_router.py` (adapter-aware query path)
  - `src/services/context_service.py` (uses `CurrentStackRetrievalAdapter`)
  - `tests/memory/test_retrieval_adapter_contract.py`
  - focused verification: `20 passed` (`--noconftest`)
- [x] Phase 2B KittyBuilder token instrumentation completed:
  - `scripts/kitty_builder.py` (`TOKEN_USAGE_FILE`, per-call logging, `/tokens`, tool `get_builder_token_usage`)
  - `scripts/report_builder_token_usage.py`
  - tests: `tests/test_kitty_builder.py` (`106 passed` in focused run)
- [x] Phase 2 plan hardening for low-capability execution completed:
  - meta-analysis: `docs/plans/phase2-build-plan-meta-analysis-2026-05-06.md`
  - deterministic execution packet: `docs/superpowers/plans/2026-05-phase2-low-capability-execution.md`
  - workflow integration: `docs/plans/phase2-orchestration-workflow-2026-05-06.md`
- [x] Phase 2C tool runtime alignment (18 tests, 483 total passing).
- [x] Phase 2D token optimization infrastructure:
  - `src/core/prompt_cache.py` — PromptCache + SemanticCache (SQLite), `truncate_to_token_budget()`
  - `tests/test_prompt_cache.py` — 11 tests
  - `scripts/kitty_builder.py` — SemanticCache integration in `call_openrouter()` / `stream_openrouter()`
  - `scripts/kitty_builder.py` — token-aware `read_file()` truncation (2K tokens default)
  - `src/core/specialists/knowledge_researcher.py` — Firecrawl `_firecrawl_scrape()` token budgeting
  - `src/tools/research_pipeline.py` — agentic research pipeline (map+batch_scrape, caching, MCP-aware)
  - Agent practices in `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `.gemini`
  - Research report: `docs/optimizer/token-optimization-research-2026-05-06.md`
  - Optimizer upgraded: fixed token log parsing, self-review → TODO.md, research pipeline integration
  - Optimizer path fix: `~/.agents/skills/kitty-optimizer/` symlinked into project `.agents/skills/`
  - Verified: 483 tests pass

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
- Phase 4 incoming worker changes enforced and cleared via `docs/archive/2026-04-30-phase4-runs/PHASE4_MERGE_GATE_2026-04-30.md`.
- Reviewed MCP-agent lane triage/spec-first reconciliation completed (no MCP expansion adopted).
- `src/tools/image_gen.py` diff reviewed and adopted.
- Migration lane started with refreshed copy-first sync, preflight `READY`, copied-app gate pass (`92 passed`), and launch validation on port 5004.
- Phase 4 merge gate rerun completed from migrated runtime path; full suite `348 passed`, focused route suite `22 passed`, and route smoke returned HTTP 200 for `/api/brief`, `/api/command`, and `/api/chat`.
- Phase 4 merge-gate automation script added and validated: `scripts/run_phase4_merge_gate.sh` (full run passed against `kitty-system/kitty-app`; report: `docs/archive/2026-04-30-phase4-runs/PHASE4_MERGE_GATE_RUN_2026-04-30_FINAL.md`).
- Phase 4 merge gate re-run **PASS** on migrated app (`kitty-system/kitty-app`, port **5001**): `docs/archive/2026-04-30-phase4-runs/PHASE4_MERGE_GATE_RUN_2026-04-30_FINAL.md` (2026-04-30, cursor).
- `runtime-001` / `specs/runtime-parity-critical-fixes.spec.md` **completed** and verified on legacy + migrated focused tests (2026-04-30, cursor closeout).
- Streaming supervisor DRY refactor shipped (`f134a2f`); copy-first sync to `kitty-system/kitty-app`, migrated `pytest tests/` **393 passed**, Phase 4 merge gate **PASS** (`docs/PHASE4_MERGE_GATE_RUN_2026-05-01_resume.md`, 2026-04-30).
- **Phase A** (`docs/audits/operational-plan-20260430.md`): all six blocker items verified in tree; plan doc updated with completion row + build-order note (2026-05-01).
- D-0011/D-0012 recorded in `docs/DECISIONS.md`; merge gate script anchors relative `--report` to `--project`; regression `tests/test_phase4_merge_gate_report_path.py` (2026-05-01).
- Two-repo consolidation completed: migrated `kitty-system/kitty-app` reconciled into legacy and deleted. Single canonical checkout at `/Users/jacobbrizinski/Projects/kitty`. Copied `honcho_routes.py` + 3 migrated-only docs. Stale references fixed in TASKS.md, AGENT_COORDINATION.md, CURRENT_FOCUS.md (2026-05-01).
- Docs bloat cleanup: `2.6M → 680K`. Removed 13 Mac resource forks, 2 orphan anchors, 10 phase4 run dupes. Phase4 archive: 17 → 7 canonical reports (2026-05-01).
- Utils dead code archiving: 48 files → 17 live. 34 dead (11504 lines) moved to `src/utils/_dead_archive/`. 3 restored after dep discovery (`security_scanner`, `performance_monitor`, `datasheet_intelligence`). Full suite verified: `399 passed` (2026-05-01).
- Two new skills created: `recommend` (two-mode: NEED SCOUT + MATCHMAKER) and `spec-to-impl` (two-mode: SPEC VALIDATOR + IMPL GENERATOR) in `.claude/skills/` (2026-05-01).
- Report: `docs/audits/CONSOLIDATION_REPORT_2026-05-01.md`.
- Documentation authority pass: `docs/FILE_MANIFEST.md` single-checkout truth, `docs/DECISIONS.md` **D-0014**, `docs/README.md` index, `SESSION_SUMMARY.md` / `docs/OPEN_LOOPS.md` migration stale-path cleanup, `docs/HANDOFF.md` canonical workspace, redirect stubs for consolidated chat-log + workspace-map paths, `docs/archive/README.md`, stray `docs/_merge_gate_anchor_*.md` removed (2026-05-02).
- Trust Dashboard (Control Room) UI and SQLite-backed Quarantine Queue implemented, integrating `garage-ui` with backend REST API `src/api/quarantine_routes.py` and `kitty.db` (2026-05-06).

## Next Smallest Action

- For every incoming Phase 4 worker change, run `scripts/run_phase4_merge_gate.sh --project /Users/jacobbrizinski/Projects/kitty --port 5001` and only merge/checkpoint on pass.

## Delegation Queue

- Cleanup worker: only read-only/spec-first for remaining candidates; do not clean protected-tree metadata or tracked deletions.

## Blocked Without New Spec

- memory migration beyond current focused modules
- QLoRA/model training
- MCP expansion
- proactive idle nudging
- UI polish
- deletion of raw chat logs
- deletion inside protected `src/` paths for metadata files without waiver

## Priority 4 — Eval + Reliability (Current Truth)

- [x] Define eval domain model (`src/core/eval_domain.py`).
- [x] Targeted pytest eval suite (`evals/smoke_suite.py` + artifacts in `evals/artifacts/`).
- [x] Browser smoke flows (page load, text chat, voice-state transitions) integrated into `scripts/eval_loop.py` default path.
- [x] Persona scripts with consistent scoring (`evals/persona_suite.py`).
- [x] Eval loop auto-generates daily summary artifacts on each run (`scripts/eval_loop.py` -> `scripts/daily_eval_summary.py`).
- [x] Eval loop has explicit offline mode (`--offline`) and disables remote provider keys for deterministic local runs.
- [ ] Self-improving loop: propose -> eval -> merge-on-improvement only.
