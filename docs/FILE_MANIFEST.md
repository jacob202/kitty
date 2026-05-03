# File Manifest

Last updated: 2026-05-02

This manifest describes the **current** app boundary. Historical migration narrative lives in `docs/archive/` and `docs/audits/CONSOLIDATION_REPORT_2026-05-01.md`.

## Canonical Runnable App

Path:

`/Users/jacobbrizinski/Projects/kitty`

This is the **only** authoritative git checkout and daily implementation surface. Agents must not treat sibling folders (`kitty-system`, Desktop copies, `Documents/Kitty`) as the runnable app unless Jacob explicitly reopens a migration spec.

## Not The Runnable App

- `/Users/jacobbrizinski/Documents/Kitty` — manuals, context, or copied notes; not the live codebase for Layer 0 execution.
- `~/Desktop/kitty-system/kitty-app` or any **backup** tree — do not edit or cite as source of truth (see `docs/STANDUP.md`).

## Retired Migration Path

Copy-first daily work against `/Users/jacobbrizinski/Projects/kitty-system/kitty-app` was **reconciled into this repo and removed** (2026-05-01). Older docs, merge-gate reports, and coordination board entries may still mention that path for chronology; treat those references as **historical**, not operational.

## Current App Surface

High-level active areas:

- `web.py`: Flask app entrypoint.
- `src/`: app code and service modules.
- `garage-ui/`: frontend surface when used.
- `tests/`: pytest suite.
- `scripts/`: project scripts.
- `docs/`: project notes, plans, control docs, and handoffs.
- `evals/`: smoke and eval platform files.
- `config/`: specialist and runtime config.
- `data/`: local runtime data, protected from casual edits.

## Phase 0 Control Surface

The Phase 0 control surface includes:

- `CURRENT_FOCUS.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`
- `KITTY_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/FILE_MANIFEST.md` (this file)
- `docs/CLEANUP_CANDIDATES.md`
- `docs/MEMORY_MODEL.md`
- `docs/PROJECT_FACTS.md`
- `docs/USER_PREFS.md`
- `docs/OPEN_LOOPS.md`
- `docs/SKILL_CANDIDATES.md`
- `docs/SOUL_LEARNED_RULES.md`
- `docs/CHAT_LOG_CONSOLIDATION_REPORT.md` (pointer; full export archived)
- `docs/GEMINI_CHAT_LOG_INTAKE.md`
- `docs/DELEGATION_BOARD.md`
- `docs/BUILDER_INTAKE.md`
- `docs/BUILDER_DIRECTIVE.md`
- `docs/GATES.md`
- `docs/WORKSPACE_SEPARATION_MOVE_MAP.md` (pointer; planning artifact archived)
- `specs/_template.md`
- `specs/physical-workspace-separation.spec.md`
- `intake/`
- `kittyintake`
- `kittybuilder`
- `scripts/builder_intake.py`
- `scripts/context_pack_generator.py`
- `scripts/kitty_builder.py`
- `scripts/check_file_governance.py`
- `scripts/plan_workspace_separation.py`
- `scripts/run_gates.sh`

## Current Control Tools

- `kittyintake`: command wrapper for deterministic builder intake.
- `kittybuilder`: command wrapper for the explicit builder contract.
- `scripts/builder_intake.py`: classifies raw requests into ready, needs verification, park, split, or reject.
- `scripts/context_pack_generator.py`: generates `.cache/kitty_context_pack.md` from canonical docs without calling models or modifying runtime source.
- `scripts/kitty_builder.py`: validates `--project` and `--spec`, defaults to dry-run, and blocks implicit legacy startup.
- `scripts/check_file_governance.py`: read-only file-governance validator and metadata-candidate reporter.
- `scripts/plan_workspace_separation.py`: read-only physical split preflight and blocker reporter (legacy planning aid).
- `scripts/run_gates.sh`: narrow control-layer gate for intake and governance tooling.

## Manifest Maintenance

Update this manifest when a top-level area becomes active, archived, protected, or purposefully split. Do not use this file alone as permission to perform path migrations; migrations require an approved spec and `docs/DECISIONS.md` updates.
