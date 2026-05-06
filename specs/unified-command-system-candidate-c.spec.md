# Spec: Unified Command System (Candidate C)
## Source Request
Start the next phase through KittyBuilder with effectiveness-first quality gates, then optimize efficiency.

## Goal
Unify fragmented slash-command handling into a single `CommandEngine` path so commands are consistent, testable, and easier to extend without regressions.

## Problem
Command behavior is currently split across multiple surfaces (route handlers and dispatcher logic), which increases drift risk and makes output quality inconsistent with user intent.

## Non-goals
- Do not change model-routing policy.
- Do not add new MCP servers or swarm behavior.
- Do not rewrite UI styling or unrelated frontend surfaces.
- Do not migrate filesystem paths.

## Files Allowed To Change
- `src/api/commands.py`
- `src/api/dispatcher.py`
- `src/api/core_routes.py` (only if needed for command routing surface)
- `src/core/` command-related modules (new `command_engine.py` allowed)
- `tests/test_commands_route.py`
- `tests/test_web_chat_phase1.py` (only if route contract assertions need alignment)
- `CURRENT_FOCUS.md`
- `TASKS.md`
- `docs/TASKS.md`
- `SESSION_SUMMARY.md`
- `docs/OPEN_LOOPS.md`
- `docs/handoffs/HANDOFF-2026-05-06.md`
- `specs/unified-command-system-candidate-c.spec.md`

## Files Forbidden To Change
- `web.py` (unless a follow-up spec explicitly allows app-factory rewiring)
- `src/memory/`
- `garage-ui/`
- `scripts/kitty_builder.py` (except emergency blocker fixes under separate waiver)

## Required Behavior
- One clear command resolution path for slash commands.
- Unknown command behavior remains explicit and non-500.
- `/stuck` and `/brief` continue to work through the unified path.
- Command execution result shape remains stable for existing callers.

## Acceptance Tests
- Command route tests pass (`tests/test_commands_route.py`).
- Chat route tests that cover slash command handling still pass.
- No regression on `/brief` and `/stuck` API behavior.

## Smoke Test
Command:
```bash
venv/bin/python -c "from web import create_app; app,_=create_app(); c=app.test_client(); print(c.post('/api/command', json={'command':'/stuck'}).status_code)"
```
Expected result: `200`.

## Validation
```bash
venv/bin/python -m pytest tests/test_commands_route.py -q --tb=short
venv/bin/python -m pytest tests/test_brief_route.py tests/test_web_chat_phase1.py -q --tb=short
```

## Completion Report Required
- files read
- files changed
- commands run
- tests passed/failed
- known risks
- next smallest action
