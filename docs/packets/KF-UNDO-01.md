# KF-UNDO-01 — The automatic todo action can be undone

**Initiative:** `kitty-opens-the-doors-20260831-v2`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`

## Outcome boundary
Backend-only packet. Frontend visibility/actionability is owned by its manifest-less interactive companion.

## Current finding
gateway/undo_journal.py ENTITY_TYPES excludes todo; gateway/action_queue.py _exec_todo_create discards the created id into a string.

## Objective
Today todo.create is the only registered T0 action. gateway/action_queue.py creates the todo and returns only a human-readable string, discarding the created todo identity. gateway/undo_journal.py rejects entity_type 'todo', so the mutation cannot be journalled even though /undo/{journal_id} already restores other recorded mutations. Extend the existing undo journal for the todo-create case only: record the created todo using its real database id, make undo of that create remove exactly that todo through the existing storage write seam, and return a non-empty undo_journal_id with the successful action result while preserving the existing status and human-readable result text. Do not create a second action store or generic transaction framework. Do not change T1/T2 approval semantics. This packet creates no new files.

## Acceptance
- Executing a proposed T0 todo.create still records status executed and its existing readable success result, and now also returns a non-empty undo_journal_id.
- POST /undo/{journal_id} for that receipt removes exactly the todo created by that action and leaves unrelated todos unchanged.
- A second undo of the same receipt is refused by the existing already-undone guard rather than silently succeeding.
- The undo history accepts entity_type todo and records before/after evidence without adding a parallel store.
- T1 and T2 action approval/execution behavior is unchanged.
- python -m pytest -q tests/test_undo_restore.py tests/test_undo_route_wiring.py tests/test_action_queue.py tests/test_actions_route.py passes.

## Verification
- `python -m pytest -q tests/test_undo_restore.py tests/test_undo_route_wiring.py tests/test_action_queue.py tests/test_actions_route.py`
- `python -m ruff check gateway/undo_journal.py gateway/action_queue.py tests/test_undo_restore.py tests/test_undo_route_wiring.py tests/test_action_queue.py tests/test_actions_route.py`

Existing green tests are only a baseline; the worker must add a regression for the missing behavior before production edits.

## Stop condition
If making todo.create undoable requires a new database/store or changing action tier semantics, stop and report the missing seam instead.

## Recovery
Source/tests only; no migration or external effect. Revert only packet-owned files on failed implementation.
