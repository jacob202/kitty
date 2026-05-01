# Intake: Builder Automation Tool

Date: 2026-04-30
Requester: Gemini
Worker lane: kb-002

## Goal
Automate the transition from raw intake classification (via `scripts/builder_intake.py`) to a valid implementation spec. This tool will reduce manual overhead and ensure every task follows the strict "Allowed vs Forbidden" file governance.

## Current App Boundary
Current runtime app: `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`
Legacy rollback path: `/Users/jacobbrizinski/Projects/kitty`

## Allowed Files
- `scripts/automate_builder.py` (new)
- `specs/builder-automation.spec.md` (new)
- `tests/test_builder_automation.py` (new)

## Forbidden Files
- `src/` (core logic)
- `garage-ui/` (frontend)
- Any file not explicitly mentioned in the spec.

## Acceptance Tests
- Tool can take a classified intake record and produce a `specs/*.spec.md` draft.
- Tool enforces that `forbidden_files` from the intake are NOT in the `Allowed Files` section of the generated spec.
- Tool populates the spec template with relevant context (goal, app boundary, validation commands).

## Smoke Test
Command: `python3 scripts/automate_builder.py --intake intake/ready_specs/sample.md`
Expected: A new file `specs/automated-sample.spec.md` exists with correct sections.

## Validation Commands
- `pytest tests/test_builder_automation.py`
- `python3 scripts/automate_builder.py --dry-run`

## Rollback Plan
- Delete created scripts and tests.
- Revert changes to `docs/TASKS.md` if any.

## Completion Report Checklist
- [ ] Script created and executable
- [ ] Spec draft generation verified
- [ ] File boundary enforcement verified
- [ ] Tests passing
