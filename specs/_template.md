# Spec: <name>

Date:
Owner:
Worker lane:
Status: draft

## Goal

Describe the user-facing outcome in plain language.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty`

Physical repo move allowed:

No, unless this spec is explicitly approved as a controlled migration spec.

Future `kitty-system` separation:

Pending controlled migration. Do not implement path moves, import rewrites, or launch changes for it in ordinary specs.

## Background

Summarize the relevant context, decisions, and links to intake notes.

## Allowed Files

List exact files and directories this spec may change.

- `<path>`

## Forbidden Files

List exact protected or out-of-scope files.

- `web.py`
- `src/`
- `tests/`
- `scripts/`
- `data/`
- UI files unless explicitly allowed

## Non-Goals

List tempting but out-of-scope work.

## Implementation Plan

1. Step one.
2. Step two.
3. Step three.

## Acceptance Tests

Define the evidence required before the work can be called complete.

- Test:
- Expected result:

## Smoke Test

Define the smallest end-to-end check that proves the touched surface still works.

Command or manual check:

Expected result:

## Validation Commands

List exact commands, expected exit codes, and any skipped validation with the reason.

```bash
# command here
```

Expected:

- Exit code:
- Required output:

## Rollback Plan

Explain how to undo this specific change without reverting unrelated worker edits.

Rollback steps:

1. Identify files changed by this spec.
2. Revert only those files or apply a targeted inverse patch.
3. Re-run the smoke test.

## Risk Notes

Document data-loss, privacy, runtime, cost, UX, migration, or worker-collision risks.

## Completion Report

When done, report:

- Files changed.
- Files intentionally not touched.
- Validation performed.
- Acceptance test results.
- Smoke test result.
- Known gaps.
- Parked follow-ups.
