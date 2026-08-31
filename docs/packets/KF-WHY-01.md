# KF-WHY-01 — Work can explain why it did not run

**Initiative:** `kitty-opens-the-doors-20260831-v2`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`

## Outcome boundary
Backend-only packet. Frontend visibility/actionability is owned by its manifest-less interactive companion.

## Current finding
why_not already explains schedules/actions; Work already carries blocker/next_action/evidence but has no why endpoint.

## Objective
gateway/why_not.py can explain cron schedules and registered automation actions, but Work rows have no equivalent explanation path even though gateway/work_projection.py already projects each Builder initiative with state, blocker, next_action, validation/review evidence and source identity. Add a framework-free work-item explanation function that derives only from the existing Builder status/work projection, then expose it from gateway/routes/work.py as a bounded why endpoint for one initiative id. Use the same Explanation fields already used by why_not: status, reason, relevant_at, action/automation where meaningful, evidence, next_step. Never fabricate a reason: if the durable projection lacks enough evidence, return an explicit unknown/insufficient-evidence explanation. Unknown initiative ids return not-found. Do not create an explanation store or mutate Builder state. This packet creates no new files.

## Acceptance
- A blocked Work item explains the projected blocker in plain language and carries the projected next action when one exists.
- A failed Work item cites durable validation/review/run evidence rather than inferring a cause from UI state.
- A ready, active, paused, waiting, or completed item returns a truthful status-specific explanation without creating any run rows or Builder events.
- When Builder has not recorded enough evidence to answer why, the response says that explicitly instead of inventing a cause.
- An unknown initiative id returns the route's normal not-found response.
- Existing schedule/action why endpoints keep their current contract.
- python -m pytest -q tests/test_why_not.py tests/test_work_routes.py tests/test_work_projection.py passes.

## Verification
- `python -m pytest -q tests/test_why_not.py tests/test_work_routes.py tests/test_work_projection.py`
- `python -m ruff check gateway/why_not.py gateway/routes/work.py tests/test_why_not.py tests/test_work_routes.py tests/test_work_projection.py`

Existing green tests are only a baseline; the worker must add a regression for the missing behavior before production edits.

## Stop condition
If answering requires joining or mutating Builder tables directly instead of consuming supported Builder status/work projection, stop.

## Recovery
Read-only projection plus tests; no durable product data changes.
