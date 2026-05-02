# Builder Intake

Last updated: 2026-04-30

Builder intake turns ideas into bounded work. If a task is not small, obvious, and already scoped, create an intake note before implementation.

## Intake Location

Use `intake/` for incoming task notes.

Recommended filename:

`intake/YYYY-MM-DD-short-name.md`

## Intake Requirements

Every intake note must include:

- Request summary.
- User-facing goal.
- Current runtime app path.
- Worker lane or owner.
- Allowed files.
- Forbidden files.
- Acceptance tests.
- Smoke test.
- Exact validation commands.
- Rollback plan.
- Completion report checklist.

## Builder Readiness

A task is ready for builder/spec work only when:

- The runtime app path is `/Users/jacobbrizinski/Projects/kitty`.
- No physical repo move is implied unless this is an approved migration spec.
- Allowed files are narrower than forbidden files.
- Protected files from `docs/FILE_GOVERNANCE.md` are not touched casually.
- Parked ideas are separated from current implementation.

## Intake Flow

1. Capture the task in `intake/`.
2. Park unrelated ideas in `docs/PARKED_FEATURES.md`.
3. Convert ready work into a spec using `specs/_template.md`.
4. Run only the validation appropriate for the touched files.
5. Complete with a report listing changed files and evidence.

## Minimal Intake Template

```md
# Intake: <name>

Date:
Requester:
Worker lane:

## Goal

## Current App Boundary

Current runtime app: `/Users/jacobbrizinski/Projects/kitty`
Retired/stale migration path unless explicitly reopened: `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`

Physical migration allowed: no, unless this intake is converted into an approved migration spec.

## Allowed Files

## Forbidden Files

## Acceptance Tests

## Smoke Test

## Validation Commands

Each command must include the expected result or an explicit reason it is skipped.

## Rollback Plan

## Parked Follow-ups

## Completion Report Checklist
```
