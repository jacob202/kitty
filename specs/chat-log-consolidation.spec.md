# Spec: Chat Log Consolidation Pipeline
## Source Request
Phase 4 — Consolidation and Cleanup: Build chat log consolidation pipeline.

## Problem
Kitty has raw chat exports in `data/sessions/` that contain decisions, tasks, parked features, etc. Need a dry-run extraction pipeline to structure this data without deleting anything.

## Non-goals
- Do not delete raw chat logs
- Do not wire to web.py
- Do not modify UI

## Files Allowed To Change
- scripts/consolidate_chat_logs.py
- tests/test_consolidate_chat_logs.py
- specs/chat-log-consolidation.spec.md (this file)
- docs/CHAT_LOG_CONSOLIDATION_REPORT.md (template)

## Files Forbidden To Change
- web.py
- data/sessions/ (no deletions)
- src/ core files

## Required Behaviour
- `dry_run(input_dir, output_dir=None) -> dict`: scans logs, extracts categories, returns counts + samples
- `_extract_categories(content) -> dict`: extracts 10 categories (decisions, parked_features, active_tasks, rejected_ideas, corrections, user_preferences, project_facts, file_references, cleanup_candidates, specialst_kb_candidates, skill_candidates, bugs_failures, open_loops)
- `write_reviewed(result, output_path)`: writes report only after review
- Script must NOT delete any files

## Acceptance Tests
- test_scan_empty_dir: returns empty list
- test_scan_with_json: finds .json files
- test_scan_with_md: finds .md files
- test_empty_content: all categories empty
- test_decision_extraction: finds "decision" keyword
- test_parked_feature: finds "parked" keyword
- test_task_extraction: finds "TODO" or "task"
- test_correction_extraction: finds "correction"
- test_user_preference: finds "prefer"
- test_all_categories_present: all 11 categories in output
- test_dry_run_no_logs: zero processed
- test_dry_run_with_logs: processes and returns categories
- test_dry_run_returns_samples: includes sample extractions
- test_write_report: creates report file
- test_write_with_errors: includes errors section

## Smoke Test
Command:
```bash
python3 scripts/consolidate_chat_logs.py --project . --input data/sessions --dry-run
```
Expected result: prints counts by category, no files written.

## Validation
```bash
python3 -m pytest tests/test_consolidate_chat_logs.py -q
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: scripts/consolidate_chat_logs.py, tests/test_consolidate_chat_logs.py
- files changed: new files only
- tests passed: [count]/[total]
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md, TASKS.md
- known risks: none
- next smallest action: extract real sessions, review, write report
