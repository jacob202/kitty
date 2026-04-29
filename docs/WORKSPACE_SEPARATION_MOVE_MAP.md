# Workspace Separation Move Map

Last updated: 2026-04-29
Status: copy-first workspace created

The current runnable checkout remains:

`/Users/jacobbrizinski/Projects/kitty`

No destructive move has happened. This document is the reviewed move map used for the copy-first migration into:

`/Users/jacobbrizinski/Projects/kitty-system`

## Current Preflight Result

Status: created, pending launch verification

Reason:

- `/Users/jacobbrizinski/Projects/kitty-system` exists.
- `/Users/jacobbrizinski/Projects/kitty` remains the authoritative runnable checkout.
- Launch commands are not switched yet.

## Target Layout

```text
/Users/jacobbrizinski/Projects/kitty-system/
  kitty-app/
  kitty-workbench/
  kitty-archives/
```

## `kitty-app` Candidates

Runtime app files that should remain together:

- `web.py`
- `kitty`
- `supervisor.py`
- `src/`
- `config/`
- `tests/`
- `evals/` code and fixtures, excluding generated artifacts
- `garage-ui/` source, excluding `.next/` and `node_modules/`
- `requirements.txt`
- `pyproject.toml` if present
- `package.json` / lockfiles where they belong to the active app

## `kitty-workbench` Candidates

Control and build tooling:

- `CURRENT_FOCUS.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`
- `KITTY_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/FILE_MANIFEST.md`
- `docs/DELEGATION_BOARD.md`
- `docs/BUILDER_INTAKE.md`
- `docs/BUILDER_DIRECTIVE.md`
- `docs/GATES.md`
- `docs/WORKSPACE_SEPARATION_MOVE_MAP.md`
- `specs/`
- `intake/`
- `kittyintake`
- `kittybuilder`
- `scripts/builder_intake.py`
- `scripts/context_pack_generator.py`
- `scripts/kitty_builder.py`
- `scripts/check_file_governance.py`
- `scripts/plan_workspace_separation.py`

## `kitty-archives` Candidates

Storage and reviewed historical material:

- `docs/archive/`
- `docs/imports/`
- raw chat exports after review
- processed chat-log reports after review
- tree snapshots
- backups
- benchmark outputs

## Excluded From Source Migration

These are local, generated, bulky, or sensitive:

- `.env`
- `.env.*`
- `.kitty.log`
- `.kitty.pid`
- `.crush/crush.db`
- `.pytest_cache/`
- `.worktrees/`
- `**/__pycache__/`
- `**/*.pyc`
- `**/.DS_Store`
- `garage-ui/.next/`
- `garage-ui/node_modules/`
- `venv/`
- `data/`
- `knowledge_db/`
- `eval_snapshots/`
- `evals/artifacts/*.json`
- `logs/`

## Required Before Physical Move

1. Verify tests from `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`.
2. Verify launch from `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`.
3. Update launch docs only after copied app validation passes.
4. Keep `/Users/jacobbrizinski/Projects/kitty` until Jacob explicitly approves deletion or archival.

## Do Not Do Yet

- Do not rename the active checkout.
- Do not rewrite imports.
- Do not update launch commands to future paths.
- Do not delete the old folder.
- Do not migrate generated local databases as source files.
