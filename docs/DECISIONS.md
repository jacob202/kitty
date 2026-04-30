# Decisions

Last updated: 2026-04-29

This file records durable project decisions. New work should follow these rules unless a later dated decision explicitly supersedes them.

## D-0001: Current App Stays Put

Status: accepted

`/Users/jacobbrizinski/Projects/kitty` is the current runnable app. Do not move it, rename it, split it, or physically migrate files during Phase 0.

Rationale: the app is actively changing, and uncontrolled moves would make it hard to distinguish real regressions from path and import breakage.

## D-0002: `kitty-system` Separation Is Planned, Not Started

Status: accepted

The future architecture may separate stable system/control material from the runnable app, using a future `kitty-system` boundary. That separation is pending controlled migration.

Required before migration:

- Approved migration spec.
- Full file inventory.
- Explicit move map.
- Rollback plan.
- Verification commands.
- Completion report.

## D-0003: Intake Before Builder Work

Status: accepted

Builder tasks must enter through `docs/BUILDER_INTAKE.md` and `intake/`. A task is not ready for implementation until it has:

- A named owner or worker lane.
- Scope summary.
- Allowed files.
- Forbidden files.
- Acceptance tests.
- Smoke test.
- Rollback plan.

## D-0004: Separate Control Docs From Product Code

Status: accepted

Control documents describe how work is allowed to proceed. They do not authorize product behavior changes by themselves.

Control-doc changes may update:

- `CURRENT_FOCUS.md`
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/FILE_MANIFEST.md`
- `docs/BUILDER_INTAKE.md`
- `specs/_template.md`
- `intake/`

Product changes require a separate spec.

## D-0005: Park, Do Not Opportunistically Build

Status: accepted

Interesting ideas discovered during focused work must go to `docs/PARKED_FEATURES.md` or an intake note. They must not be implemented inside an unrelated task.

## D-0006: Protected Files Require Explicit Permission

Status: accepted

Protected files and directories are listed in `docs/FILE_GOVERNANCE.md`. Workers must check that file before editing and must not touch protected runtime paths unless their assigned spec explicitly allows it.

## D-0007: Builder Requires Explicit Project And Spec

Status: accepted

`kittybuilder` must not start an open-ended interactive builder by default. It requires:

- `--project`
- `--spec`
- dry-run by default
- `--execute` before any future write-capable builder path

The spec must live inside the project, and every run must end with a completion-report checklist.

Rationale:
Raw builder launch is too easy to confuse with runtime Kitty startup and can lead to uncontrolled edits.

## D-0008: Canadian-First Assistant Persona Candidate

Status: needs_user_confirmation (confidence: low)

Do not treat the Canadian-first assistant persona as accepted canon yet.

Rationale:
The evidence in `docs/imports/gemini_intake_20260428.md` comes primarily from assistant-authored session text. It is useful as a candidate preference, but not strong enough to become a durable project decision without Jacob confirming it.

Consequences:
Kitty should keep the accepted direct/practical/no-fluff style, but Canadian sourcing and budget-first behavior should be used only when the user asks for it or confirms this as a permanent preference.

Review trigger:
Jacob confirms whether Canadian-first sourcing/budget behavior is a permanent assistant preference.

## D-0009: Preserve Raw Logs

Status: accepted (confidence: high)

Preserve raw logs until reviewed extraction exists.

Rationale:
This is already a project safety rule and matches the master plan. It prevents accidental deletion of unmodified data and forces humans/agents to perform an explicit review.
