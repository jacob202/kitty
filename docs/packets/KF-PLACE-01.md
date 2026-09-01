# KF-PLACE-01 — Draft, scroll position, filters, and model choice survive a reload

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #732 owns KittyContext/InputBar and changes durable composer context. Let it land before adding persistence so the saved draft/context format matches the final composer contract.

## What Jacob can do after this
Jacob can reload Kitty and continue typing, reading and filtering from where he left off instead of reconstructing his place.

## Why this is the next thing
Kitty persists navigation/theme/session ids but not the draft, scroll, filters or model choice that define where Jacob actually was in a workflow.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Persist only the user’s resumable UI place: per-chat draft text, conversation scroll anchor/position, durable surface filters and the selected model override/default needed to continue where they were. Use small versioned local/session storage records keyed by stable chat/view identity; do not duplicate server-owned messages, actions, projects or query data. Restore defensively when a referenced chat/view/model no longer exists. Clear ephemeral state at the correct lifecycle boundary (for example a sent draft). Add reload-focused component and Playwright coverage.

## Acceptance criteria
- An unsent draft in a chat survives reload and is scoped to that chat.
- The active conversation restores near the prior scroll position without fighting new-message auto-scroll.
- Supported Work/Library/Activity filters survive reload and invalid values fall back safely.
- The selected valid model/default survives reload; unavailable models fail back to Kitty Auto/default truthfully.
- Sending/clearing a draft removes stale persisted draft state and no server-owned conversation content is copied into localStorage.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/KittyContextViewRecovery.test.tsx tests/PlacePersistence.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/place-persistence.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/place-persistence.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
