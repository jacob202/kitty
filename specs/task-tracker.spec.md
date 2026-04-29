# Spec: Task Tracker + Done Handler
## Source Request
Phase 3 — Core Runtime Utility: Build task tracker with SQLite backend.

## Problem
Kitty needs a task system where users can say "done [task]" and the system marks it complete and shows the next task.

## Non-goals
- Do not wire into web.py or chat.py yet
- Do not modify UI

## Files Allowed To Change
- src/memory/task_repo.py
- src/memory/task_tracker.py
- tests/test_task_tracker.py
- specs/task-tracker.spec.md (this file)
- data/kitty.db (table creation only)

## Files Forbidden To Change
- web.py
- src/api/chat.py
- src/memory/db.py (use separate task_repo.py)

## Required Behaviour
- `task_repo.py`: CREATE TABLE tasks, functions: init_task_db, add_task, mark_done, get_open_tasks, get_next_task, get_next_action
- `task_tracker.py`: process_done_command(text) -> dict, get_next_task_brief() -> str
- mark_done returns {found, task, next_open}
- process_done_command parses "done [task]", returns {matched, response, next_task}

## Acceptance Tests
- test_init_creates_table: tasks table exists
- test_add_and_get: add task, retrieve open tasks
- test_mark_done: mark task done, verify status
- test_mark_done_returns_next: returns next open task
- test_mark_done_no_match: handles no match
- test_get_next_action: returns task title
- test_process_done_matched: parses "done X"
- test_process_done_no_match: non-matching text
- test_process_done_no_open_task: no open tasks
- test_get_next_task_brief: returns formatted string
- test_get_next_task_brief_empty: handles empty state

## Smoke Test
Command:
```bash
python3 -c "from src.memory.task_repo import init_task_db, add_task, get_open_tasks; init_task_db(); add_task('test'); print(get_open_tasks())"
```
Expected result: list with one task

## Validation
```bash
python3 -m pytest tests/test_task_tracker.py -q
sqlite3 data/kitty.db ".tables"
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: src/memory/task_repo.py, src/memory/task_tracker.py, tests/test_task_tracker.py
- files changed: new files + data/kitty.db updated
- tests passed: 20/20 Phase 3 tests
- gates passed: 65 passed
- docs updated: SESSION_SUMMARY.md, TASKS.md
- known risks: none
- next smallest action: /stuck command tests, then wire handlers to API
