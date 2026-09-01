# KF-CHRONICLE-01 — Chronicle tips become one-click improvements, not hidden advice

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns the selective intelligence surface and shared query files. Release after that stack lands and confirm Chronicle tips still have an action contract worth surfacing.

## What Jacob can do after this
Jacob can see one useful “you could use Kitty better this way” tip and apply it directly instead of discovering the feature by accident.

## Why this is the next thing
The Chronicle service and /chronicle/tips route are complete, but there is no frontend caller.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Surface /chronicle/tips through the selective personal-intelligence experience. Each tip is bounded plain-language advice about using Kitty better and must carry the concrete existing action/deep link that applies it; tips without an executable destination stay out of the primary card feed. Provide dismiss/acknowledge only if the backend already has durable semantics—do not create a local dismissed-tips registry. Add the smoke file named here.

## Acceptance criteria
- A Chronicle tip can appear as a bounded personal-intelligence card when it has a concrete action.
- The action opens or executes the existing owning capability; no read-only dead-end tip card is introduced.
- No tip is fabricated when Chronicle returns none or is unavailable.
- The UI does not create a second durable dismissal/seen store.
- The surface remains selective and hides when there is nothing useful to say.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeIntelligence.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/chronicle.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/chronicle.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
