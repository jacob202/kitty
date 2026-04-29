# File Manifest

Last updated: 2026-04-28

This manifest explains the current app boundary and the planned, not-yet-started separation.

## Current Runnable App

Path:

`/Users/jacobbrizinski/Projects/kitty`

This is the active runnable Kitty checkout. Launch, tests, and implementation work should assume this path unless a later migration decision changes it.

## Not The Current Runnable App

`/Users/jacobbrizinski/Documents/Kitty` may contain context, manuals, or copied instructions, but it is not the authoritative runnable app for Phase 0 work.

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

The Phase 0 control surface is:

- `CURRENT_FOCUS.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`
- `KITTY_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/FILE_MANIFEST.md`
- `docs/CLEANUP_CANDIDATES.md`
- `docs/MEMORY_MODEL.md`
- `docs/PROJECT_FACTS.md`
- `docs/USER_PREFS.md`
- `docs/OPEN_LOOPS.md`
- `docs/SKILL_CANDIDATES.md`
- `docs/SOUL_LEARNED_RULES.md`
- `docs/CHAT_LOG_CONSOLIDATION_REPORT.md`
- `docs/GEMINI_CHAT_LOG_INTAKE.md`
- `docs/DELEGATION_BOARD.md`
- `docs/BUILDER_INTAKE.md`
- `docs/BUILDER_DIRECTIVE.md`
- `docs/GATES.md`
- `specs/_template.md`
- `intake/`
- `kittyintake`
- `kittybuilder`
- `scripts/builder_intake.py`
- `scripts/context_pack_generator.py`
- `scripts/kitty_builder.py`
- `scripts/check_file_governance.py`
- `scripts/run_gates.sh`

## Planned Separation

The future `kitty-system` separation is a planned controlled migration. It has not happened.

No worker should:

- Move files into a new physical repo.
- Rename the runnable checkout.
- Rewrite imports or launch commands for a future path.
- Delete docs because they appear to belong to the future system layer.

## Current Control Tools

- `kittyintake`: command wrapper for deterministic builder intake.
- `kittybuilder`: command wrapper for the explicit builder contract.
- `scripts/builder_intake.py`: classifies raw requests into ready, needs verification, park, split, or reject.
- `scripts/context_pack_generator.py`: generates `.cache/kitty_context_pack.md` from canonical docs without calling models or modifying runtime source.
- `scripts/kitty_builder.py`: validates `--project` and `--spec`, defaults to dry-run, and blocks implicit legacy startup.
- `scripts/check_file_governance.py`: read-only file-governance validator and metadata-candidate reporter.
- `scripts/run_gates.sh`: narrow control-layer gate for intake and governance tooling.

Future migration must be driven by a spec that includes:

- Source and destination map.
- Protected files.
- Import and launch impact.
- Data preservation plan.
- Rollback procedure.
- Verification commands.

## Manifest Maintenance

Update this manifest when a new top-level area becomes active, archived, protected, or migrated. Do not use this file as permission to perform the migration itself.
