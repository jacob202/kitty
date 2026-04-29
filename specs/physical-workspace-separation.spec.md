# Spec: Physical Workspace Separation Preflight

Date: 2026-04-29
Status: draft
Owner: Codex
Worker lane: control / migration planning

## Problem

Kitty still runs from `/Users/jacobbrizinski/Projects/kitty`, while the master plan calls for a future parent workspace:

```text
~/Projects/kitty-system/
  kitty-app/
  kitty-workbench/
  kitty-archives/
```

Moving files before the tree is clean risks breaking imports, losing local state, and committing work from another worker into the wrong lane.

## Current Blocker

The current tree contains uncommitted Phase 6+ MCP / KnowledgeGetter work. The current focus still forbids MCP expansion. That work must be reviewed, parked, or separately checkpointed before a physical split starts.

## Goal

Create a read-only preflight and move map for the future physical split. The preflight must make it obvious what will move into `kitty-app`, `kitty-workbench`, and `kitty-archives`, and what must be excluded as generated or local runtime data.

## Non-goals

- Do not move files.
- Do not rename `/Users/jacobbrizinski/Projects/kitty`.
- Do not rewrite imports or launch commands.
- Do not commit generated databases.
- Do not accept MCP work as complete.
- Do not delete `knowledge_db/`, `data/`, raw logs, eval artifacts, or local caches.

## Files Allowed To Change

- `specs/physical-workspace-separation.spec.md`
- `docs/WORKSPACE_SEPARATION_MOVE_MAP.md`
- `docs/OPEN_LOOPS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_MANIFEST.md`
- `CURRENT_FOCUS.md`
- `TASKS.md`
- `docs/DELEGATION_BOARD.md`
- `.gitignore`
- `scripts/plan_workspace_separation.py`
- `tests/test_workspace_separation_plan.py`
- `scripts/run_gates.sh`

## Files Forbidden To Change

- `web.py`
- `src/core/`
- `src/space_kitty/`
- `src/services/`
- `data/`
- `knowledge_db/`
- `garage-ui/`
- `requirements.txt`
- `src/agents/knowledge_getter.py`
- `src/agents/knowledge_getter_config.json`

## Required Behavior

- Preflight is read-only.
- Preflight reports dirty tree blockers.
- Preflight flags MCP / KnowledgeGetter work as blocked under the current focus.
- Move map separates app, workbench, archive, and excluded/generated paths.
- Generated databases are excluded from source migration.
- Physical move remains parked until the repo is clean or intentionally checkpointed.

## Smoke Test

Command:

```bash
/opt/homebrew/bin/python3.12 scripts/plan_workspace_separation.py --project . --allow-dirty-readonly
```

Expected:

- exits 0
- prints `Physical workspace separation preflight`
- prints `BLOCKED`
- names KnowledgeGetter / MCP as a blocker if present
- writes nothing

## Validation

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_workspace_separation_plan.py -q
bash scripts/run_gates.sh
```

## Rollback Plan

Delete this spec, the preflight script, the move map, and the test file. No runtime or data files are changed by this spec.

## Completion Report Required

- files read
- files changed
- commands run
- tests passed/failed
- remaining blockers
- next smallest action
