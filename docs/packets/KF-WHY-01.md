# KF-WHY-01 — Work can explain why it did not run

**Initiative:** `kitty-opens-the-doors-20260831-v2`
**Owner:** builder
**Free or paid:** free
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend-only packet. Its visible UI/actionability is owned by a manifest-less interactive companion.

## What Jacob can do after this
The bounded capability in this packet is implemented and proven without creating a parallel system.

## Why this is the next thing
why_not already explains schedules/actions; Work already carries blocker/next_action/evidence but has no why endpoint.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
gateway/why_not.py can explain cron schedules and registered automation actions, but Work rows have no equivalent explanation path even though gateway/work_projection.py already projects each Builder initiative with state, blocker, next_action, validation/review evidence and source identity. Add a framework-free work-item explanation function that derives only from the existing Builder status/work projection, then expose it from gateway/routes/work.py as a bounded why endpoint for one initiative id. Use the same Explanation fields already used by why_not: status, reason, relevant_at, action/automation where meaningful, evidence, next_step. Never fabricate a reason: if the durable projection lacks enough evidence, return an explicit unknown/insufficient-evidence explanation. Unknown initiative ids return not-found. Do not create an explanation store or mutate Builder state. This packet creates no new files.

## Acceptance criteria
- A blocked Work item explains the projected blocker in plain language and carries the projected next action when one exists.
- A failed Work item cites durable validation/review/run evidence rather than inferring a cause from UI state.
- A ready, active, paused, waiting, or completed item returns a truthful status-specific explanation without creating any run rows or Builder events.
- When Builder has not recorded enough evidence to answer why, the response says that explicitly instead of inventing a cause.
- An unknown initiative id returns the route's normal not-found response.
- Existing schedule/action why endpoints keep their current contract.
- python -m pytest -q tests/test_why_not.py tests/test_work_routes.py tests/test_work_projection.py passes.

## Verification
**Tier 1 — mechanical.** Builder-runnable commands:
  - `python -m pytest -q tests/test_why_not.py tests/test_work_routes.py tests/test_work_projection.py`
  - `python -m ruff check gateway/why_not.py gateway/routes/work.py tests/test_why_not.py tests/test_work_routes.py tests/test_work_projection.py`

**Tier 2 — running app.** Not applicable to this backend-only half; its manifest-less interactive companion owns the running-app Playwright smoke.

**Tier 3 — product acceptance.** Not applicable to this backend-only half; independent Product Acceptance is required on the user-facing companion before the door is considered finished.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
If answering requires joining or mutating Builder tables directly instead of consuming supported Builder status/work projection, stop.

## Recovery
Read-only projection plus tests; no durable product data changes.
