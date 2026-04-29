# Spec: Wire Phase 3 Modules to API Routes
## Source Request
Phase 3 modules are built and tested. Now wire them to API routes.

## Problem
Morning brief, task tracker, and /stuck command need HTTP endpoints.

## Non-goals
- Do not modify UI
- Do not change existing route signatures

## Files Allowed To Change
- src/api/__init__.py (register new routes)
- src/api/brief.py (add route decorator)
- src/api/commands.py (add route decorator)
- src/api/routes.py or web.py (import and register)
- tests/test_brief_route.py (new)
- tests/test_commands_route.py (new)

## Files Forbidden To Change
- src/core/morning_brief.py (logic unchanged)
- src/core/stuck.py (logic unchanged)
- src/memory/task_repo.py (logic unchanged)
- src/memory/task_tracker.py (logic unchanged)

## Required Behaviour

### GET /api/brief
- Calls `get_brief()` from src.api.brief
- Returns JSON: `{"brief": str, "data": dict}`
- Status 200 on success, 500 on error

### POST /api/command
- Accepts JSON: `{"command": str}`
- For "/stuck": calls `get_stuck_action()` from src.core.stuck
- For "done ...": calls `process_done_command()` from src.memory.task_tracker
- Returns JSON: `{"response": str, ...}`

## Acceptance Tests
- test_brief_route: GET /api/brief returns 200 and brief key
- test_commands_route_stuck: POST /stuck returns next action
- test_commands_route_done: POST "done X" marks task and returns next
- test_commands_route_unknown: POST unknown command returns error

## Smoke Test
Command:
```bash
curl -s http://localhost:5000/api/brief | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'brief' in d else 'FAIL')"
curl -s -X POST http://localhost:5000/api/command -H "Content-Type: application/json" -d '{"command":"/stuck"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','')[:50])"
```
Expected: brief text and stuck response.

## Validation
```bash
python3 -m pytest tests/test_brief_route.py tests/test_commands_route.py -q
bash scripts/run_gates.sh
```

## Completion Report Required
- files read: src/api/brief.py, src/api/commands.py, src/api/__init__.py
- files changed: routes registered, tests added
- tests passed: [count]/[total]
- gates passed: 65+ passed
- docs updated: SESSION_SUMMARY.md
- known risks: none
- next smallest action: Phase 5 — Skills and Quality
