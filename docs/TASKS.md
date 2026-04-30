# Kitty Task Backlog

---

## Dev Infrastructure
<!-- Things wired in, things still needing verification, and how to actually use them -->

### Ready to use now
- [ ] **`bash scripts/verify_setup.sh`** — run at start of any session to check Ollama, ChromaDB, LightRAG, Python deps, project files
- [ ] **`/audit` skill** — type `/audit` in Claude Code; runs structured health check (dir structure, ChromaDB/LightRAG access, broken imports, eval pass rate)
- [ ] **postToolUse hook** — fires automatically on every `.py` Edit/Write; runs `py_compile` and prints errors inline. No action needed, just know it's there.
- [ ] **`refactor_reports/`** — output dir for parallel agent runs. Use when doing multi-system work (backend + frontend + config simultaneously); each agent writes its report here

### Ready to use now
- [x] **`bash scripts/verify_setup.sh`** — run at start of any session to check Ollama, ChromaDB, LightRAG, Python deps, project files
- [x] **`/audit` skill** — type `/audit` in Claude Code; runs structured health check (dir structure, ChromaDB/LightRAG access, broken imports, eval pass rate)
- [ ] **postToolUse hook** — fires automatically on every `.py` Edit/Write; runs `py_compile` and prints errors inline. No action needed, just know it's there.
- [ ] **`refactor_reports/`** — output dir for parallel agent runs. Use when doing multi-system work (backend + frontend + config simultaneously); each agent writes its report here

### Now usable (Phase 4 complete)
- [x] **`eval_snapshots/`** — eval runner exists; `POST /api/eval/run {"suite":"smoke"}` writes artifacts here
- [x] **`evals/smoke_suite.py`** — 5-check smoke suite, append-only artifacts, baseline enforcement
- [x] **`evals/compare_runs.py`** — `detect_regression()` compares against most recent artifact
- [x] **`evals/persona_suite.py`** + `evals/personas/basic.json` — 3-persona fixture suite + daily summary
- [x] **`src/core/eval_domain.py`** — `EvalRun`, `EvalCheck`, `EvalScore`, `EvalResult` domain types
- [x] Wire eval-gated iteration loop: `scripts/eval_loop.py` now automates pytest → eval route → regression detection — DONE

### Overnight queue pattern (when to use)
<!-- Hand Claude your tasks.md and this prompt — then walk away: -->
<!-- "Work through every TODO in tasks.md. For each: attempt it, mark DONE + write one line to data/checkpoints/overnight.log, or mark BLOCKED (Retries: N/3) and move on. Never stop on a single failure. After 3 retries mark NEEDS_HUMAN. Spend max 5 min per task." -->
- [ ] Add retry ceiling logic to BLOCKED items format: `(Retries: 0/3 — Error: reason)` → after 3 retries → `NEEDS_HUMAN`

---

## Priority 1.5 — Phase 3 Bugs (fixed)

### High
- [x] **Reasoning routes use wrong object in web mode** (`src/api/reasoning_routes.py`) — DONE
- [x] **Context budgeting is positional, not semantic** (`src/core/context_manager.py`) — DONE

### Medium
- [x] **`/api/memory/corrections` accepts requests with no `item_id`** (`src/api/memory_product_routes.py`) — DONE (validated /api/memory/forget)

---

## Done (for reference)
- [x] Phase 1: Web chat foundation (dispatcher, fallback LLM, streaming) — 2026-04-23
- [x] Phase 4: Voice input (MediaRecorder → /api/transcribe → faster-whisper) — 2026-04-23
- [x] Global skills: think, ship, debug, improve, kitty-arch — 2026-04-23
- [x] crush.json: consolidated-skills path, legacy-skills path, LSP Python 3.12 — 2026-04-23
- [x] Project CLAUDE.md — 2026-04-23
- [x] MCP memory layer (57 entities, 47 relations) — 2026-04-23 (`src/memory/lightrag_store.py`, `docs/imports/gemini_intake_20260428.md`)
- [x] Sequential thinking MCP wired — 2026-04-23
- [x] Phase 4: Eval platform — EvalDomain, smoke suite, regression detection, POST /api/eval/run, persona fixtures — 2026-04-24 (23 tests, 100%)

---

## Priority 1 — Foundation (unblocks everything else)

### Phase 1: Prune MCP + Dead Surfaces
- [x] Audit all capability surfaces: classify each as keep / hide / remove / investigate
  - /api/swarm/* — returns 503, hide from UX until stable
  - scorecard/health endpoints — downgrade to internal/dev-only
  - crush.json MCP servers: keep only filesystem + memory (sequential-thinking: evaluate)
- [x] Create `docs/CAPABILITY_INVENTORY.md` — stable vs experimental vs environment-only
- [x] Hide or 404 any route that is not production-safe

### Phase 2: Capability Registry
- [x] Design canonical capability metadata schema (name, tier, routing, status)
- [x] Define tiers: core / beta / internal / disabled
- [x] Create registry that drives slash-command discovery, UI chips, and routing
- [x] Add routing telemetry: suggested / selected / auto-invoked / succeeded / failed
- [x] Add dry-run/explain mode: "here's what I would invoke and why"

---

## Priority 2 — Phase B Stabilization (from 2026-04-10 plan)
- [x] Fix type/import errors in `src/tutor/` (tutorbot.py, quiz.py, session.py) — Stale: Pruned in Phase 1
- [x] Fix type/import errors in `src/memory/context_hierarchy.py` — DONE
- [x] Wire `ContextHierarchy` into `LightRAGStore` — DONE
- [x] Update `supervisor.py`: route to `Council` when `mode == "council_heavy"` — Stale: Pruned in Phase 1
- [x] Update `supervisor.py`: use L0/L1/L2 hierarchy for `Supervisor.search()` — Stale: Pruned in Phase 1
- [x] Fix `/tutor` command in `cli.py` (Rich rendering issues) — Stale: Pruned in Phase 1
- [x] Fix Docker paths in `scripts/dev_setup.sh` — Stale: Pruned in Phase 1

---

## Priority 3 — Features

### Memory + Reasoning (Phase 3)
- [x] User-visible memory controls (what Kitty remembers, why, forget/pin controls) — DONE
- [x] Session vs project vs durable memory scope exposed to user — DONE
- [x] Reasoning traces → readable explanation surface (not raw internal logs) — DONE
- [x] Typed, budgeted context assembly (replace additive prompt stuffing) — DONE
- [x] Correction lifecycle: recency, scope, conflict handling, undo/forget — DONE

### Specialist Improvements
- [x] Parallel specialist agents (wire specialists as agents, not just Python classes) — DONE
- [x] Specialist KB training (Implemented domain-isolated LightRAG + Ingestion engine fix + Knowledge Inventory) — DONE
- [x] MCP memory feedback loop (surface relevant memory entities into conversations automatically) — DONE

### New Features (post-cleanup)
- [x] AI model digest (daily summary of new models/updates) — exists in ai_dev_monitor.py, wired to /api/ai-dev/items
- [ ] Domain news feed (specialist-relevant news surfaced in chat)

---

## Gemini/Chat-Log Extraction Review

### From gemini_intake_20260428.md

**Promoted to canon:**
- Direct, practical, no-fluff interaction preference → docs/USER_PREFS.md
- Raw-log preservation rule → docs/DECISIONS.md / docs/USER_PREFS.md
- `mlx_lm` package status corrected → docs/PROJECT_FACTS.md

**Parked (leave open):**
- Budget Leak Finder skill, privacy-spec required before any runtime work
- AU-7900 specialist KB candidate, source-grounding required before canonical KB

**Open loops:**
- Is "Canadian-first" assistant persona permanent? → needs user confirmation
- `$129/month` claim from assistant-authored extraction → ignore as noisy unless reintroduced by explicit business spec (resolved 2026-04-30)
- Bank transaction analysis → parked behind privacy spec + manual-paste-only boundary (resolved 2026-04-30)

**Rejected as noisy extraction:**
- Canadian Real Estate Analysis Engine
- Socket cleanup for stale `sYzrlwrRFthqlGpRAAAI`
- Generic "theory-first coaching" rejection
- [x] Small model routing fix: differentiate "small" slot — DONE

---

## Priority 4 — Eval + Reliability (Phase 4)
- [x] Define eval domain model: run, scenario, persona, artifact, score, regression — exists src/core/eval_domain.py
- [x] Targeted pytest eval suite (not swarm-based) — exists evals/smoke_suite.py, 20 tests pass
- [x] Browser smoke flows: page load, text chat, voice state transitions
- [x] Persona scripts with consistent scoring — exists evals/persona_suite.py
- [x] Artifact capture (raw outputs) + daily summary generation
- [x] Self-improving eval loop: propose → eval → only merge if score improves
- [x] Revisit swarm productization only after capability platform + eval system stable
