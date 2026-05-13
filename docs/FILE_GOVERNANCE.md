# File Governance

Last updated: 2026-04-28

This document defines edit boundaries for Kitty workers.

## Current Rule

Workers may edit only the files explicitly assigned by their task. Dirty files outside the assigned lane may belong to another worker and must not be reverted, formatted, moved, or overwritten.

## Protected Runtime Files

The following are protected unless a spec explicitly names them as allowed:

- `gateway/`
- `tests/`
- `scripts/`
- `data/`
- `evals/artifacts/`
- `logs/`
- Databases, model files, generated caches, and local runtime state.

## File Categories

Use these categories in specs, intake notes, and cleanup reports:

- `canonical_doc`
- `runtime_source`
- `test`
- `script`
- `spec`
- `skill`
- `specialist_config`
- `tool`
- `data`
- `archive`
- `benchmark`
- `scratch`
- `deprecated`

## Lifecycle States

Use these lifecycle states when parking, archiving, or reviewing files:

- `active`
- `candidate`
- `parked`
- `archived`
- `deprecated`
- `delete_pending`
- `protected`

## Control Files

Control files coordinate work and may be edited only by assigned documentation/control workers:

- `CURRENT_FOCUS.md`
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/README.md`
- `docs/BUILDER_INTAKE.md`
- `docs/AGENT_COORDINATION.md`
- `docs/AGENT_HANDOFF_TEMPLATE.md`
- `specs/_template.md`
- `intake/`

## Before Editing

Every worker must:

1. Confirm the working directory is `/Users/jacobbrizinski/Projects/kitty`.
2. Check `git status --short`.
3. Read the assigned spec or intake note.
4. Confirm allowed and forbidden files.
5. Search before adding duplicate frontend IDs, CSS classes, routes, commands, or docs.

## During Editing

- Keep changes inside the assigned lane.
- Do not clean up unrelated files.
- Do not reformat unrelated files.
- Do not fix nearby code unless the spec allows it.
- Do not move the repo or change launch paths.
- If another worker changed a file in your lane, inspect and merge intentionally.

## Completion Report

Every worker should report:

- Files changed.
- Files intentionally not touched.
- Validation commands run.
- Known gaps or blocked validation.
- Any parked follow-up added.

## Validation

```bash
python3 scripts/check_file_governance.py --dry-run
python3 scripts/check_file_governance.py --list
```

Expected:

- Required control files are listed as present.
- Protected paths are listed.
- Generated metadata candidates may be reported, but the checker does not delete anything.
