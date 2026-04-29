# Spec: /stuck Command
## Source Request
Phase 3 — Core Runtime Utility: Build /stuck command so Kitty can tell the user what to do next when they're stuck.

## Problem
Users need a way to ask "what should I do right now?" without getting a long research-style answer.

## Non-goals
- Do not wire into web.py or app factory yet
- Do not modify UI
- Do not use LLM for this

## Files Allowed To Change
- src/core/stuck.py (already exists)
- src/api/commands.py (already exists)
- tests/test_stuck_command.py
- specs/stuck-command.spec.md (this file)

## Files Forbidden To Change
- web.py
- src/api/__init__.py
- src/core/orchestrator.py

## Required Behaviour
- `get_stuck_action() -> dict` returns: current_focus, next_action, do_not (list), report_back
- `next_action` must be concrete, under 30 min, under 200 chars
- `next_action` must NOT be: research, redesign, open a new tool, change architecture
- `report_back` format: "done [task]" or "still stuck: [reason]"
- `handle_command(command) -> dict` in commands.py processes "/stuck"

## Acceptance Tests
- test_returns_expected_keys: all 4 keys present
- test_next_action_under_200_chars: < 200 chars
- test_next_action_is_concrete: no research/redesign/new tool/change architecture
- test_do_not_not_empty_when_focus_has_forbidden: list non-empty
- test_report_back_format: contains "done " or "still stuck:"
- test_fallback_when_files_missing: handles missing files gracefully

## Smoke Test
Command:
```bash
python3 -c "from src.core.stuck import get_stuck_action; print(get_stuck_action())"
```
Expected result: dict with keys current_focus, next_action, do_not, report_back

## Validation
```bash
python3 -m pytest tests/test_stuck_command.py -q
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: src/core/stuck.py, src/api/commands.py, tests/test_stuck_command.py
- files changed: tests/test_stuck_command.py (rewritten)
- tests passed: 6/6
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md, TASKS.md
- known risks: none
- next smallest action: wire /stuck to API route (requires new spec)
