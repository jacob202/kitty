# ADR-0013: Phone-First Delivery And The Move-In Bar

**Status:** Accepted; amended 2026-07-26
**Date:** 2026-07-04

## Context

Jacob is phone-first and should not have to remember to open a developer surface
to receive results, approvals, or important life information.

## Decision

1. User-facing delivery is phone-first.
2. Anything requiring Jacob's attention is brought to him. A review step must
   not assume that he opens an app, PR, log directory, or dashboard unprompted.
3. The move-in bar is a truthful daily loop: real life state, deadlines, one
   concrete next step per active project, capture that returns, and auditable
   action history.
4. Job-search execution remains parked until Jacob explicitly activates it.
   Recovery-sensitive surfaces remain opt-in and local-only.

## Amendment — 2026-07-26

The exact transport is an operating preference, not permanent architecture.
iMessage-to-self, Pushover, iOS push, or a later supported channel may satisfy
the decision when verified against current availability and cost.

The durable contract is:

- phone-first delivery;
- push the review to Jacob rather than making him hunt for it;
- transport failure remains visible and never becomes a false delivered state;
- channel and domain priorities live in current preferences and
  `docs/ROADMAP.md`, not frozen inside this ADR.

## Consequences

- User-facing work without a credible phone delivery path does not satisfy the
  move-in bar.
- Builder morning reports must surface outcomes, failures, and decisions needed
  through Kitty's supported delivery path rather than expecting log review.
- No transport choice silently gains broader message, account, or privacy
  authority.
