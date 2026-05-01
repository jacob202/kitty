# Spec: Builder Automation Tool

## Goal
Automate the transition from raw intake classification (via `scripts/builder_intake.py`) to a valid implementation spec. This tool will reduce manual overhead and ensure every task follows the strict "Allowed vs Forbidden" file governance.

## Scope
### Allowed Files
- `scripts/automate_builder.py` (new)
- `specs/builder-automation.spec.md` (new)
- `tests/test_builder_automation.py` (new)

### Forbidden Files
- `src/` (core logic)
- `garage-ui/` (frontend)
- Any file not explicitly mentioned in the spec.

## Implementation Plan
1. [AUTOMATED] Implementation logic based on intake goals.
2. Ensure file boundaries are respected.
3. Validate changes with identified commands.

## Acceptance Criteria
- [AUTOMATED] Derived from intake goals and tests.

## Validation
- `pytest tests/test_builder_automation.py`
- `python3 scripts/automate_builder.py --dry-run`
