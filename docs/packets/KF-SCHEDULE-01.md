# KF-SCHEDULE-01 — Registered cron actions are deliberately scheduled or deliberately left off

**Initiative:** `kitty-opens-the-doors-20260831-v4`
**Owner:** builder (held)
**Builder manifest:** held
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Backend packet intentionally held out of Builder. Hold reason: PR #725 and PR #735 both currently own gateway/app.py, the required action-registration/schedule-seeding seam. Compile the contract now; release it only after those PRs land or close and the base is refreshed.

## What Jacob can do after this
The bounded capability in this packet is implemented and proven without creating a parallel system.

## Why this is the next thing
The action registry contains cron actions that startup never seeds; gateway/app.py is simultaneously owned by active PR #725 and #735, so changing it now would create a guaranteed collision.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
gateway/app.py registers more cron actions than startup actually seeds. Audit the registered actions against existing schedule rows and add startup seeding only for actions that are safe, bounded and useful by default. At minimum decide explicitly for prefetch.warm, nudges.check, memory.consolidate, inbox.triage, mail.poll, github.poll, experts.poll, life.evening_reflection and life.morning_proactive. Credential-dependent pollers must not be scheduled to fail forever when their integration is unavailable, and heavy maintenance must not be enabled merely because it is registered. Preserve idempotent restart behavior and write the decision into tests so an intentionally-off action is distinguishable from forgotten wiring. Do not change the action implementations themselves, provider credentials, or frontend. This packet creates no new files.

## Acceptance criteria
- Every registered-but-unscheduled action named in the packet has a tested startup disposition: seeded with a bounded cadence/condition, or intentionally off with an explicit code/test reason.
- Restarting Kitty does not duplicate any schedule row.
- mail.poll and github.poll are not scheduled into repeated failure when their required integration is unavailable.
- Heavy maintenance such as memory.consolidate is not enabled at an aggressive cadence without an explicit bounded policy.
- Existing deadline and brief schedule seeding remains compatible.
- python -m pytest -q tests/test_app_lifespan_hermetic.py tests/test_life_cron.py passes.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `python -m pytest -q tests/test_app_lifespan_hermetic.py tests/test_life_cron.py`
  - `python -m ruff check gateway/app.py tests/test_app_lifespan_hermetic.py tests/test_life_cron.py`

**Tier 2 — running app.** Not applicable until the hold clears; the eventual interactive companion owns browser smoke proof.

**Tier 3 — product acceptance.** Not applicable until the hold clears and the user-facing companion is ready for independent Product Acceptance.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Do not implement while an active PR owns gateway/app.py; after release, stop again if enabling an action requires guessing credentials, spend, or an unsafe cadence.

## Recovery
Startup schedule declarations and hermetic tests only. Revert packet-owned edits if seeding is not idempotent; never mutate live schedule data by hand.
