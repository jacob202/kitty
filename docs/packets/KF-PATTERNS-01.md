# KF-PATTERNS-01 — Kitty can show the weekly and annual patterns it actually has evidence for

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns the personal-intelligence Home surface and shared query files. Land it first, then add Patterns as another ranked notice only if it earns space.

## What Jacob can do after this
Jacob can ask for a weekly or annual mirror and see only patterns Kitty has enough history to support.

## Why this is the next thing
gateway/patterns.py and the weekly/annual routes are complete but have no frontend reference.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Surface the existing /patterns/weekly and /patterns/annual projections inside the selective personal-intelligence experience, not as a statistics dashboard. Show the strongest bounded pattern plus evidence period and an explicit “not enough history yet” state when the backend cannot support a claim. Any suggested next action must use an existing action/deep link. Do not infer mood or productivity beyond the backend result. Add the smoke file named here.

## Acceptance criteria
- Weekly and annual views show only patterns returned by the backend.
- Insufficient history renders an explicit warm “not enough history yet” state rather than fake zero/normal.
- Evidence period/source context is visible enough to understand what the pattern is based on.
- A surfaced action uses an existing action/deep link; the UI does not invent behavioral advice.
- The surface stays bounded/selective and does not become a dense analytics dashboard.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeIntelligence.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/patterns.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/patterns.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
