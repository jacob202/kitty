# Phase B Stabilization & Integration Plan
**Date:** 2026-04-10
**Goal:** Stabilize the new Expansion Phase B modules (Tutor, AutoResearch, Context Hierarchy) and wire them into the main Supervisor.

## 1. Objectives
- Resolve all Pyright/import errors in the new `src/tutor/`, `src/memory/context_hierarchy.py`, and `cli.py`.
- Integrate `Council`, `ContextHierarchy`, and `TutorBot` into the `Supervisor` in `supervisor.py`.
- Correct Docker paths in `scripts/dev_setup.sh`.
- Verify the full stack (CLI + Tutor + AutoResearch).

## 2. Parallel Agent Strategy (The "Squad")

| Agent Name | Role | Tasks |
|------------|------|-------|
| **tutor-stabilizer** | Specialist | Fix type/import errors in `src/tutor/` (tutorbot.py, quiz.py, session.py). |
| **memory-stabilizer** | Specialist | Fix type/import errors in `src/memory/context_hierarchy.py` and wire it into `LightRAGStore`. |
| **supervisor-integrator** | Architect | Update `supervisor.py` to use `Council` for heavy queries and `ContextHierarchy` for retrieval. |
| **cli-refiner** | Specialist | Finalize `/tutor` command in `cli.py` and fix any UI/Rich rendering issues. |
| **onboarding-finisher** | Specialist | Fix Docker paths in `scripts/dev_setup.sh` and finish `docs/ONBOARDING.md`. |

## 3. Implementation Steps

### Step 1: Research & Triage (Parallel)
- [ ] Run `pyright src/tutor/ src/memory/ scripts/run_autoresearch.py` to get a fresh error list.
- [ ] Inspect `supervisor.py` to plan the integration points for `Council` and `ContextHierarchy`.

### Step 2: Parallel Stabilization (Agents Dispatched)
- [ ] **tutor-stabilizer**: Fix `src/tutor/` diagnostics.
- [ ] **memory-stabilizer**: Fix `src/memory/context_hierarchy.py` diagnostics.
- [ ] **onboarding-finisher**: Fix `scripts/dev_setup.sh` Docker paths.

### Step 3: Core Integration (Architectural)
- [ ] **supervisor-integrator**:
    - Import `Council` from `src.orchestrator.council`.
    - Import `ContextHierarchy` from `src.memory.context_hierarchy`.
    - Modify `Supervisor.run()` to use `Council` if `mode == "council_heavy"`.
    - Modify `Supervisor.search()` to utilize the L0/L1/L2 hierarchy.

### Step 4: Verification & Handoff
- [ ] Run `/tutor quiz sansui` to verify the end-to-end tutor loop.
- [ ] Run `python scripts/run_autoresearch.py --budget-minutes 1 --target src/tutor/quiz.py` to verify the research loop.
- [ ] Update `docs/audit/FEATURE_INVENTORY.md` with the new integrations.

## 4. Acceptance Criteria
- [x] No `ImportError` or `SyntaxError` when running `cli.py`.
- [x] `/tutor quiz` generates questions from ingested content.
- [x] `supervisor.py` correctly routes to `Council`.
- [x] `scripts/dev_setup.sh` starts Docker containers correctly from the root.
