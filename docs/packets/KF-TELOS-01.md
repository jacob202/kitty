# KF-TELOS-01 — Mission, goals, and values are editable inside Kitty

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: The active visible-product stack (#729, #731, #732, #733 and #735) currently owns shared gateway.ts/queries.ts and related surfaces. Compile the contract now, but refresh base and exact path fence after the stack lands before implementation.

## What Jacob can do after this
Jacob can fill in and revise Kitty’s mission/goals/values profile in Settings instead of editing config files by hand.

## Why this is the next thing
The Telos interview/routes exist, but there is no frontend caller; today the profile is effectively an internal/config-only capability.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Add a focused Telos editor to the existing Settings/identity area using GET /telos and POST /telos/{section}. Present the interview sections progressively, save each section through the existing backend, and show saved/current state after reload. Never expose config file paths or ask Jacob to hand-edit markdown. Do not create a second profile schema or store. Add the smoke file named here.

## Acceptance criteria
- The current Telos profile loads in Settings without exposing filesystem/config details.
- Jacob can edit each supported Telos section and save through the existing endpoint.
- Saved values survive reload because the UI re-reads the backend authority.
- Missing/empty sections invite completion without pretending the profile is complete.
- Backend validation errors are shown in plain language and preserve the unsaved edit.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/SettingsPanel.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/telos.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/telos.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
