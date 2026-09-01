# KF-WHY-02 — Ask a failed automation or work row why, then act on the answer

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: The active visible-product stack (#729, #731, #732, #733 and #735) currently owns shared gateway.ts/queries.ts and related surfaces. Compile the contract now, but refresh base and exact path fence after the stack lands before implementation. Backend KF-WHY-01 is also still in review as PR #738.

## What Jacob can do after this
Jacob can tap “why?” on work that did not happen, see the evidenced reason, and take the next step without leaving the row.

## Why this is the next thing
The why endpoints exist and the frontend already has automation/work actions, but no row offers the explanation as an in-place user action.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Wire the existing why endpoints into the automation and Work row actions. A row that did not run gets one visible “why?” affordance that opens Status, Reason, Timestamp, bounded Evidence and the backend-provided Next step; when the next step maps to an existing action, render that action on the same card instead of sending Jacob to logs or CLI. Preserve the owning automation/Work state as authority and do not create a client explanation engine. Add the targeted browser smoke file named in this packet.

## Acceptance criteria
- Automation and Work rows that can silently not-happen expose a visible why action.
- The explanation shows status, reason, timestamp, bounded evidence and next step from the Gateway contract.
- A backend-provided executable next step is actionable in place; an unavailable action is stated plainly rather than fabricated.
- Loading, error and unexplained states are distinct and recoverable.
- Existing automation retry/run controls and Work actions keep their current semantics.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/AutomationsView.test.tsx tests/WorkViewActions.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/why-not.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/why-not.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
