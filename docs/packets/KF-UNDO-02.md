# KF-UNDO-02 — Todo-create undo is durable and partial failure is truthful

**Initiative:** `kitty-opens-the-doors-20260831-v6`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend-only packet. Its visible UI/actionability is owned by a manifest-less interactive companion.

## What Jacob can do after this
Jacob can trust an automatic todo receipt after the response is gone, and a failed undo-journaling step can no longer leave Kitty claiming a mutation did not happen.

## Why this is the next thing
GitHub exact-head review of PR #737 found two real consistency failures: journal failure can leave a created todo behind while the action is marked failed, and the returned undo_journal_id is not persisted on the action row. Its snapshot_todo helper is unnecessary for undoing a create.

## Plan
1. Lock the two #737 review regressions plus an unknown-outcome compensation-failure regression before implementation.
2. Add the nullable action receipt migration and keep _COLUMNS/_finish durable reads and writes aligned.
3. Implement todo-create journal + compensation through existing storage_router seams and restore through the same authority.
4. Run the narrow action/undo tests and Ruff, then independently review the exact resulting head before publication.

## Not in scope
- Merging, rebasing onto, or modifying PR #737 or its Builder worktree.
- A generic transaction framework, second todo store, or direct writes that bypass storage_router.
- Changing action risk tiers, grants, provider routing, frontend behavior, or non-todo undo semantics.

## Objective
Implement the todo.create undo capability from fresh origin/main, superseding the unsafe PR #737 implementation rather than stacking on it. Create exactly one new migration, gateway/migrations/053_action_undo_receipt.sql, extending the existing actions schema with a nullable undo_journal_id receipt and persist it as part of the action finish path so immediate responses and later action reads agree. For todo.create, create through storage_router.add_todo(), record a todo/create undo entry using the real returned todo id, and return the journal id. If journal recording fails after the todo was created, compensate through the existing storage_router.delete_todo() seam before reporting failure. If that compensation cannot be proven, record the action as unknown rather than falsely claiming no side effect. Undoing the create must delete exactly the created todo through the existing storage router and must not require a snapshot_todo helper or a second todo store. Preserve tier/grant/double-execution rules and every non-todo undo entity. Do not bypass storage_router, add a parallel transaction/store, or rewrite existing history.

## Acceptance criteria
- A successful todo.create returns a non-empty undo_journal_id and action_queue.get()/route reads of the same action persist and return that exact receipt after the immediate execute response.
- The undo entry is entity_type todo, operation create, and is bound to the real created todo database id; invoking the existing undo path removes exactly that todo while leaving unrelated todos unchanged.
- If undo_journal.record fails after todo creation and storage_router.delete_todo confirms compensation, the action is failed, the created todo is absent, and no undo_journal_id is persisted.
- If journal recording fails and compensation cannot be confirmed, the action is recorded unknown with an explanatory result instead of failed/executed; Kitty never claims the side effect did not happen.
- Existing actions migrate with undo_journal_id null, migration is idempotent, and _COLUMNS/_finish keep reads and writes schema-consistent.
- No snapshot_todo helper or direct todo_store mutation is introduced in undo_journal; restore uses the existing storage_router deletion authority.
- Existing tier enforcement, approval identity, spend reservation behavior, execution claim fencing, and non-todo undo behavior remain compatible.
- python -m pytest -q tests/test_action_queue.py tests/test_actions_route.py tests/test_undo_restore.py tests/test_undo_route_wiring.py passes.

## Verification
**Tier 1 — mechanical.** Builder-runnable commands:
  - `python -m pytest -q tests/test_action_queue.py tests/test_actions_route.py tests/test_undo_restore.py tests/test_undo_route_wiring.py`
  - `python -m ruff check gateway/action_queue.py gateway/undo_journal.py tests/test_action_queue.py tests/test_actions_route.py tests/test_undo_restore.py`

**Tier 2 — running app.** Not applicable to this backend-only half; its manifest-less interactive companion owns the running-app Playwright smoke.

**Tier 3 — product acceptance.** Not applicable to this backend-only half; independent Product Acceptance is required on the user-facing companion before the door is considered finished.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Do not release while PR #737 remains an active owner of these paths. During implementation, stop if truthful compensation would require bypassing storage_router or broadening into a generic action transaction rewrite.

## Recovery
Schema addition is nullable and backward-compatible. Packet-owned code must leave pre-existing actions readable; no live todo/action rows are mutated manually during implementation.
