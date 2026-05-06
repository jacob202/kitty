# Tasks

Last updated: 2026-05-06

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

---\n\n## Dev Infrastructure\n<!-- Things wired in, things still needing verification, and how to actually use them -->\n\n### Ready to use now\n- [x] **`bash scripts/verify_setup.sh`** — run at start of any session to check Ollama, ChromaDB, LightRAG, Python deps, project files\n- [x] **`/audit` skill** — type `/audit` in Claude Code; runs structured health check (dir structure, ChromaDB/LightRAG access, broken imports, eval pass rate)\n- [x] **`postToolUse` hook** — fires automatically on every `.py` Edit/Write; runs `py_compile` and prints errors inline. No action needed, just know it's there (external Dorothy hook)\n- [x] **`refactor_reports/`** — output dir for parallel agent runs. Use when doing multi-system work (backend + frontend + config simultaneously); each agent writes its report here\n\n### Now usable (Phase 4 complete)\n- [x] **`eval_snapshots/`** — eval runner exists; `POST /api/eval/run {\"suite\":\"smoke\"}` writes artifacts here\n- [x] **`evals/smoke_suite.py`** — 5-check smoke suite, append-only artifacts, baseline enforcement\n- [x] **`evals/compare_runs.py`** — `detect_regression()` compares against most recent artifact\n- [x] **`evals/persona_suite.py`** + `evals/personas/basic.json` — 3-persona fixture suite + daily summary\n- [x] **`src/core/eval_domain.py`** — `EvalRun`, `EvalCheck`, `EvalScore`, `EvalResult` domain types\n- [x] Wire eval-gated iteration loop: `scripts/eval_loop.py` now automates pytest → eval route → regression detection — DONE\n\n### Overnight queue pattern (when to use)\n<!-- Hand Claude your tasks.md and this prompt — then walk away: -->\n<!-- \"Work through every TODO in tasks.md. For each: attempt it, mark DONE + write one line to data/checkpoints/overnight.log, or mark BLOCKED (Retries: N/3) and move on. Never stop on a single failure. After 3 retries mark NEEDS_HUMAN. Spend max 5 min per task.\" -->\n- [ ] Add retry ceiling logic to BLOCKED items format: `(Retries: 0/3 — Error: reason)` → after 3 retries → `NEEDS_HUMAN`\n\n---\n\n## Priority 1.5 — Phase 3 Bugs (fixed)\n\n### High\n- [x] **Reasoning routes use wrong object in web mode** (`src/api/reasoning_routes.py`) — DONE\n- [x] **Context budgeting is positional, not semantic** (`src/core/context_manager.py`) — DONE\n\n### Medium\n- [x] **`/api/memory/corrections` accepts requests with no `item_id`** (`src/api/memory_product_routes.py`) — DONE (validated /api/memory/forget)\n\n---\n\n## Done (for reference)\n- [x] Phase 1: Web chat foundation (dispatcher, fallback LLM, streaming) — 2026-04-23\n- [x] Phase 4: Voice input (MediaRecorder → /api/transcribe → faster-whisper) — 2026-04-23\n- [x] Global skills: think, ship, debug, improve, kitty-arch — 2026-04-23\n- [x] crush.json: consolidated-skills path, legacy-skills path, LSP Python 3.12 — 2026-04-23\n- [x] Project CLAUDE.md — 2026-04-23\n- [x] MCP memory layer (57 entities, 47 relations) — 2026-04-23 (`src/memory/lightrag_store.py`, `docs/imports/gemini_intake_20260428.md`)\n- [x] Sequential thinking MCP wired — 2026-04-23\n- [x] Phase 4: Eval platform — EvalDomain, smoke suite, regression detection, POST /api/eval/run, persona fixtures — 2026-04-24 (23 tests, 100%)\n\n---\n\n## Priority 1 — Foundation (unblocks everything else)\n\n### Phase 3: Architectural Deepening (In Progress)\n- [x] **Unified Tool Runtime** — Centralized registry with authorization and recursion guards (`src/tools/runtime.py`).\n- [x] **Specialist Runtime** — Data-driven identity, async execution engine isolating domain logic from infra.\n- [ ] **Unified Command System** (Candidate C) — Consolidate fragmented slash commands (`/stuck`, `/brief`, `/scrape`, etc.) from `web.py` and `dispatcher.py` into a deep `CommandEngine`. Attempted but shelved due to time constraints; must be completed to finish the architecture deepening roadmap.\n\n### Phase 1: Prune MCP + Dead Surfaces\n- [x] Audit all capability surfaces: classify each as keep / hide / remove / investigate\n  - /api/swarm/* — returns 503, hide from UX until stable\n  - scorecard/health endpoints — downgrade to internal/dev-only\n  - crush.json MCP servers: keep only filesystem + memory (sequential-thinking: evaluate)\n- [x] Create `docs/CAPABILITY_INVENTORY.md` — stable vs experimental vs environment-only\n- [x] Hide or 404 any route that is not production-safe\n\n### Phase 2: Capability Registry\n- [x] Design canonical capability metadata schema (name, tier, routing, status)\n- [x] Define tiers: core / beta / internal / disabled\n- [x] Create registry that drives slash-command discovery, UI chips, and routing\n- [x] Add routing telemetry: suggested / selected / auto-invoked / succeeded / failed\n- [x] Add dry-run/explain mode: \"here's what I would invoke and why\"\n\n---\n\n## Priority 2 — Phase B Stabilization (from 2026-04-10 plan)\n- [x] Fix type/import errors in `src/tutor/` (tutorbot.py, quiz.py, session.py) — Stale: Pruned in Phase 1\n- [x] Fix type/import errors in `src/memory/context_hierarchy.py` — DONE\n- [x] Wire `ContextHierarchy` into `LightRAGStore` — DONE\n- [x] Update `supervisor.py`: route to `Council` when `mode == \"council_heavy\"` — Stale: Pruned in Phase 1\n- [x] Update `supervisor.py`: use L0/L1/L2 hierarchy for `Supervisor.search()` — Stale: Pruned in Phase 1\n- [x] Fix `/tutor` command in `cli.py` (Rich rendering issues) — Stale: Pruned in Phase 1\n- [x] Fix Docker paths in `scripts/dev_setup.sh` — Stale: Pruned in Phase 1\n\n---\n\n## Priority 3 — Features\n\n### Memory + Reasoning (Phase 3)\n- [x] User-visible memory controls (what Kitty remembers, why, forget/pin controls) — DONE\n- [x] Session vs project vs durable memory scope exposed to user — DONE\n- [x] Reasoning traces → readable explanation surface (not raw internal logs) — DONE\n- [x] Typed, budgeted context assembly (replace additive prompt stuffing) — DONE\n- [x] Correction lifecycle: recency, scope, conflict handling, undo/forget — DONE\n\n### Specialist Improvements\n- [x] Parallel specialist agents (wire specialists as agents, not just Python classes) — DONE\n- [x] Specialist KB training (Implemented domain-isolated LightRAG + Ingestion engine fix + Knowledge Inventory) — DONE\n- [x] MCP memory feedback loop (surface relevant memory entities into conversations automatically) — DONE\n\n### New Features (post-cleanup)\n- [x] AI model digest (daily summary of new models/updates) — exists in ai_dev_monitor.py, wired to /api/ai-dev/items\n- [x] Domain news feed (specialist-relevant news surfaced in chat) — src/services/domain_news_monitor.py, wired into specialist_framework.py context\n\n---\n\n## Gemini/Chat-Log Extraction Review\n\n### From gemini_intake_20260428.md\n\n**Promoted to canon:**\n- Direct, practical, no-fluff interaction preference → docs/USER_PREFS.md\n- Raw-log preservation rule → docs/DECISIONS.md / docs/USER_PREFS.md\n- `mlx_lm` package status corrected → docs/PROJECT_FACTS.md\n\n**Parked (leave open):**\n- Budget Leak Finder skill, privacy-spec required before any runtime work\n- AU-7900 specialist KB candidate, source-grounding required before canonical KB\n\n**Open loops:**\n- Is \"Canadian-first\" assistant persona permanent? → needs user confirmation\n- `$129/month` claim from assistant-authored extraction → ignore as noisy unless reintroduced by explicit business spec (resolved 2026-04-30)\n- Bank transaction analysis → parked behind privacy spec + manual-paste-only boundary (resolved 2026-04-30)\n\n**Rejected as noisy extraction:**\n- Canadian Real Estate Analysis Engine\n- Socket cleanup for stale `sYzrlwrRFthqlGpRAAAI`\n- Generic \"theory-first coaching\" rejection\n- [x] Small model routing fix: differentiate \"small\" slot — DONE\n\n---\n\n## Priority 4 — Eval + Reliability (Phase 4)\n- [x] Define eval domain model: run, scenario, persona, artifact, score, regression — exists src/core/eval_domain.py\n- [x] Targeted pytest eval suite (not swarm-based) — exists evals/smoke_suite.py, 20 tests pass\n- [ ] Browser smoke flows: page load, text chat, voice state transitions\n- [x] Persona scripts with consistent scoring — exists evals/persona_suite.py\n- [ ] Artifact capture (raw outputs) + daily summary generation\n- [ ] Self-improving eval loop: propose → eval → only merge if score improves\n- [ ] Revisit swarm productization only after capability platform + eval system stable
