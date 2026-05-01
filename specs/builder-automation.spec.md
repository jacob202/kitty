# Spec: Full Builder Automation from Intake

## Goal
Implement a script `scripts/automate_builder.py` that processes intake records (classified by `builder_intake.py`) and generates structured, compliant specification files in `specs/`.

## Scope
### Allowed Files
- `scripts/automate_builder.py`
- `tests/test_builder_automation.py`

### Forbidden Files
- `src/`
- `garage-ui/`
- `web.py`

## Requirements
1. **Parser:** Must parse Markdown intake files to extract `Goal`, `Allowed Files`, `Forbidden Files`, and `Validation Commands`.
2. **Template Integration:** Use the core spec template (`specs/_template.md`) or a derived schema.
3. **Safety Enforcement:** 
    - If a file is in `Forbidden Files` but accidentally listed in `Allowed Files`, the automation must flag it or exclude it from the spec.
    - Must verify that the `Current App Boundary` matches the authoritative system path.
4. **Output:** Generate `specs/<timestamp>-<slug>.spec.md`.

## Implementation Plan
1. Create `scripts/automate_builder.py`.
2. Implement Markdown parsing for intake records.
3. Implement spec generation using a template string.
4. Add basic validation to prevent "Forbidden" leak into "Allowed".
5. Create `tests/test_builder_automation.py` to verify parsing and generation.

## Acceptance Criteria
- Running `python3 scripts/automate_builder.py --intake intake/ready_specs/<file>.md` creates a valid spec file.
- The generated spec includes all required sections: Goal, Scope, Plan, Validation.
- Spec files are correctly named and located in `specs/`.

## Validation
- `pytest tests/test_builder_automation.py`
- Manual run on the `2026-04-30-builder-automation.md` intake record.
