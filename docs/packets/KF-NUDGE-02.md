# KF-NUDGE-02 — Nudges appear as dismissible action cards, not ambient prose

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns the intended Home surface and KF-NUDGE-01 is queued. Release only after both contracts stabilize, then reuse them rather than adding a new nudge store/surface.

## What Jacob can do after this
Jacob can see a useful nudge, do the suggested thing or dismiss it, and the card stays truthful about whether its sources worked.

## Why this is the next thing
The nudge engine is complete but had no UI caller; PR #733 creates the selective Home surface that should own this kind of notice.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Project pending nudges into the selective Home intelligence surface as bounded action cards. Each card shows the nudge’s reason and concrete action, can be dismissed using the existing dismissal authority, and never claims successful delivery if the source/detector is degraded. Reuse the Home intelligence card shape from PR #733 if present; do not create a separate Nudge page or local dismissal store. Add the smoke file named here.

## Acceptance criteria
- A pending nudge renders as one bounded Home action card with a concrete next action.
- Dismiss removes the nudge through the existing backend contract and remains gone after reload.
- Detector/source degradation is visible and never represented as “no nudges”.
- Duplicate nudges do not render twice.
- Opening Home alone does not trigger a model call or duplicate push delivery.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeIntelligence.test.tsx tests/HomeState.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/nudges.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/nudges.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
