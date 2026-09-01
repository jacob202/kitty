# KF-SYSTEM-01 — Home’s bespoke cards collapse onto the shared visual/work primitives

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 and PR #725 own HomeState. Let both land, then refactor the resulting current card set rather than the stale pre-stack version.

## What Jacob can do after this
Jacob sees one coherent visual language on Home without losing the distinctions between work, context, health and actions.

## Why this is the next thing
Home contains multiple bespoke card renderers despite a mature token system and existing shared primitives; PR #733/#725 currently modify the same Home surface.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Refactor Home’s repeated card/status/loading/action shells to the existing shared UI primitives and WorkCard model where semantics match. Preserve the selective hierarchy and all current actions; this is not a redesign and must not flatten genuinely different content types into one generic card. Replace local status/loading/error chrome with Card, StatusBadge, AsyncState and Button where applicable, then delete only styles/renderers made redundant by the refactor. Add the smoke file named here.

## Acceptance criteria
- Home uses shared Card/StatusBadge/AsyncState/Button primitives for equivalent states instead of maintaining duplicate chrome.
- Work-like items use shared WorkCard where its status/action contract fits.
- All existing Home actions, degraded states and selective hierarchy remain functionally equivalent.
- No new generic abstraction is introduced merely to reduce line count.
- Desktop and iPhone layouts retain clear delineation and no horizontal overflow.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeState.test.tsx tests/WorkCard.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/home-system.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/home-system.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
