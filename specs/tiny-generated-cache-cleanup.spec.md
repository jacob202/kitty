# Spec: Tiny Generated Cache Cleanup

## Source Request

Original:

> is there a tree cleaning i could delegate inb tbhe meantiume

Scout interpretation:

Only remove ignored/generated cache files that are outside protected runtime trees. Do not remove tracked deletions, raw logs, eval artifacts, `src/` metadata, `data/` metadata, frontend dependency/build caches, or environment directories.

## Problem

The tree contains safe generated cache artifacts mixed with risky tracked deletions and protected-tree metadata. Broad cleanup would be unsafe because generated files, source deletions, skill material, eval history, and protected `src/` files currently appear together in `git status`.

## Non-goals

- Do not delete or restore tracked files.
- Do not clean `src/`, `data/`, `skills/`, `config/`, `evals/`, `kitty-chat/`, `venv/`, `eval_snapshots/`, or `refactor_reports/`.
- Do not remove `Icon\r` files outside the approved cache directories.
- Do not delete raw chat logs, eval artifacts, histories, or benchmark records.

## Files Allowed To Change

- `.DS_Store`
- `__pycache__/`
- `scripts/__pycache__/`
- `tests/__pycache__/`
- `.pytest_cache/`
- `.aider.tags.cache.v4/`
- `docs/CLEANUP_CANDIDATES.md`
- `SESSION_SUMMARY.md`
- `TASKS.md`

## Files Forbidden To Change

- `src/**`
- `data/**`
- `skills/**`
- `config/**`
- `evals/**`
- `kitty-chat/**`
- `venv/**`
- `eval_snapshots/**`
- `refactor_reports/**`
- tracked deleted files

## Existing Context To Read First

- `CURRENT_FOCUS.md`
- `docs/CLEANUP_CANDIDATES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/DELEGATION_BOARD.md`

## Required Behaviour

- Verify all cleanup targets are untracked and ignored before deletion.
- Delete only the allowed generated/cache paths.
- Leave tracked deletions untouched.
- Leave protected-tree `Icon\r` metadata untouched.
- Run gates after cleanup.

## Acceptance Tests

- `git status --short --ignored .DS_Store __pycache__ scripts/__pycache__ tests/__pycache__ .pytest_cache .aider.tags.cache.v4` shows only ignored targets before cleanup.
- After cleanup, those exact paths no longer appear.
- `bash scripts/run_gates.sh` exits 0.

## Smoke Test

Command:

```bash
find .DS_Store __pycache__ scripts/__pycache__ tests/__pycache__ .pytest_cache .aider.tags.cache.v4 -maxdepth 2 -print 2>/dev/null
```

Expected result:

- before cleanup: prints only allowed cache/generated paths
- after cleanup: prints nothing

## Validation

```bash
git status --short --ignored .DS_Store __pycache__ scripts/__pycache__ tests/__pycache__ .pytest_cache .aider.tags.cache.v4
bash scripts/run_gates.sh
```

## Rollback Plan

No rollback is required for ignored generated caches. Python bytecode, pytest cache, Finder metadata, and Aider tag cache are rebuildable.

## Completion Report Required

- paths verified ignored
- paths removed
- commands run
- gates passed/failed
- known risks
- next smallest action
