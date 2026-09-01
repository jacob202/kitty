# KF-SYSTEM-02 — Builder’s seven card shapes use the shared work/status primitives

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally omitted from Builder; frontend gates run only in the interactive lane.

## What Jacob can do after this
Jacob sees Builder as part of the same sophisticated Kitty system instead of a separate hand-built dashboard, without losing its deeper evidence controls.

## Why this is the next thing
BuilderSurface still owns many bespoke card renderers while the shared primitives and WorkCard already model the common state/action vocabulary.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Refactor BuilderSurface’s duplicated packet/initiative/status/action card chrome onto shared Card, StatusBadge, AsyncState, Button and WorkCard where semantics fit. Preserve Builder-specific evidence blocks, packet tree and operator controls as specialized content. Consume KF-COPY-01 title_key/placeholders when available, with the existing raw reason only in technical disclosure. Do not change Builder control-plane behavior or queue state. Add the smoke named here.

## Acceptance criteria
- Equivalent Builder cards use shared primitives rather than locally duplicating border/status/action/loading chrome.
- Builder-specific evidence and operator controls remain specialized and retain all current functionality.
- WorkCard is used only where its status/action model matches; Builder control-plane semantics are not squeezed into an incompatible abstraction.
- When title_key/placeholders are present, primary copy resolves through the client catalog and raw reason stays secondary/technical.
- Desktop and iPhone Builder surfaces retain clear hierarchy and no horizontal overflow.

## Verification
**Tier 1 — mechanical.** Interactive validation commands:
  - `cd gateway/kitty-chat && npx vitest run tests/BuilderSurface.test.tsx tests/WorkCard.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/builder-system.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/builder-system.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
