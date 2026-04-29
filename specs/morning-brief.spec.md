# Spec: Morning Brief Module
## Source Request
Phase 3 — Core Runtime Utility: Build deterministic morning brief generator.

## Problem
Kitty needs a deterministic (no LLM) way to show the user "where am I?" on startup or demand.

## Non-goals
- Do not wire into web.py or Flask yet
- Do not use LLM calls
- Do not modify UI

## Files Allowed To Change
- src/core/morning_brief.py
- src/api/brief.py
- tests/test_morning_brief.py
- specs/morning-brief.spec.md (this file)

## Files Forbidden To Change
- web.py
- src/api/__init__.py
- src/core/orchestrator.py

## Required Behaviour
- `generate_brief(root=None) -> dict` returns: date, active_focus, last_completed, next_action, forbidden_distractions
- `brief_to_text(brief) -> str` formats as plain text
- Reads CURRENT_FOCUS.md, TASKS.md, SESSION_SUMMARY.md, KITTY_CONTEXT.md
- Falls back gracefully when files missing ("unknown", "nothing yet", empty lists)

## Acceptance Tests
- `test_returns_expected_keys`: all 5 keys present
- `test_date_is_today`: matches current date
- `test_brief_to_text_contains_focus`: contains "Active focus:"
- `test_fallback_when_files_missing`: handles missing files
- `test_forbidden_list`: returns list
- `test_brief_structure_all_sections`: all sections in text
- `TestBriefWithFiles`: reads from actual temp files

## Smoke Test
Command:
```bash
python3 -c "from src.core.morning_brief import generate_brief; print(generate_brief())"
```
Expected result: dict with keys date, active_focus, last_completed, next_action, forbidden_distractions

## Validation
```bash
python3 -m pytest tests/test_morning_brief.py -q
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: src/core/morning_brief.py, src/api/brief.py, tests/test_morning_brief.py
- files changed: none (new files only)
- tests passed: 20/20 Phase 3 tests
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md
- known risks: none
- next smallest action: update TASKS.md, log in SESSION_SUMMARY.md
