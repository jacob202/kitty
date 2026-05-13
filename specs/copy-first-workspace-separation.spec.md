# Spec: Copy-First Workspace Separation

Date: 2026-04-29
Status: draft
Owner: Codex
Worker lane: control / migration execution

## Problem

The preflight now proves the main branch can be separated without mixing in the parked MCP agent bundle. Kitty still needs a physical `kitty-system` parent workspace, but the old runnable checkout must remain intact.

## Goal

Create a copy-first workspace at `/Users/jacobbrizinski/Projects/kitty-system`:

```text
kitty-system/
  kitty-app/
  kitty-workbench/
  kitty-archives/
```

## Non-goals

- Do not delete or rename `/Users/jacobbrizinski/Projects/kitty`.
- Do not rewrite imports.
- Do not change launch commands yet.
- Do not copy virtualenvs, node_modules, generated databases, local tool installs, or secret env files.

## Required Behavior

- Dry-run is the default.
- `--execute` is required for writes.
- Copy operation is additive and non-destructive.
- Generated/tool-local files are excluded.
- Old checkout remains the authoritative runnable app until a later launch-verification spec says otherwise.

## Smoke Test

```bash
/opt/homebrew/bin/python3.12 scripts/copy_workspace_separation.py --project . --dry-run
```

Expected:

- prints source and target paths
- lists app/workbench/archive copy jobs
- writes nothing

## Execute

```bash
/opt/homebrew/bin/python3.12 scripts/copy_workspace_separation.py --project . --execute
```

Expected:

- creates `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`
- creates `/Users/jacobbrizinski/Projects/kitty-system/kitty-workbench`
- creates `/Users/jacobbrizinski/Projects/kitty-system/kitty-archives`
- does not alter `/Users/jacobbrizinski/Projects/kitty`

## Validation

```bash
test -d /Users/jacobbrizinski/Projects/kitty-system/kitty-app
test -d /Users/jacobbrizinski/Projects/kitty-system/kitty-workbench
test -d /Users/jacobbrizinski/Projects/kitty-system/kitty-archives
test -f /Users/jacobbrizinski/Projects/kitty-system/kitty-app/web.py
test -f /Users/jacobbrizinski/Projects/kitty-system/kitty-workbench/kittyintake
test ! -d /Users/jacobbrizinski/Projects/kitty-system/kitty-app/venv
test ! -d /Users/jacobbrizinski/Projects/kitty-system/kitty-app/kitty-chat/node_modules
```

## Rollback Plan

Remove `/Users/jacobbrizinski/Projects/kitty-system` only if Jacob explicitly approves. The original checkout remains untouched.
