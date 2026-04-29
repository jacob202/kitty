# Workspace Separation Move Map

Last updated: 2026-04-29
Status: preflight only

The current runnable checkout remains:

`/Users/jacobbrizinski/Projects/kitty`

No physical move has happened. This document is the reviewed move map for a future copy-first migration into:

`/Users/jacobbrizinski/Projects/kitty-system`

## Current Preflight Result

Status: blocked

Reason:

- The tree contains uncommitted Phase 6+ MCP / KnowledgeGetter work.
- `CURRENT_FOCUS.md` forbids MCP expansion.
- `knowledge_db/` is generated runtime data and must not be committed or migrated as source.

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

1. Resolve or separately checkpoint the KnowledgeGetter / MCP lane.
2. Run `git status --short` and confirm no unrelated dirty files are mixed into the migration.
3. Run `python3 scripts/plan_workspace_separation.py --project .`.
4. Run `python3 scripts/check_file_governance.py --dry-run`.
5. Run `bash scripts/run_gates.sh`.
6. Create a copy-first backup or archive before any path rewrite.

## Do Not Do Yet

- Do not rename the active checkout.
- Do not rewrite imports.
- Do not update launch commands to future paths.
- Do not delete the old folder.
- Do not migrate generated local databases as source files.
