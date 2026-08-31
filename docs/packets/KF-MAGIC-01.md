# KF-MAGIC-01 — Cross-project connections are visible and actionable from Home

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 appears to implement this outcome and owns gateway/magic_kitty.py plus the Home intelligence UI. Do not duplicate it; release only as a post-merge verification/follow-up packet.

## What Jacob can do after this
Jacob can see a meaningful connection Kitty noticed across projects and act on it without Home secretly spending tokens.

## Why this is the next thing
The original audit found Magic Kitty complete but unreachable; PR #733 now explicitly includes cached Magic connections and a find-connections action.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Verify PR #733 against the original Magic Kitty door before writing new code. The desired result is one selective “Kitty noticed” connection card backed by cached gateway/magic_kitty.py output, with the owning projects visible and an action that moves the connection into Chat or opens the relevant project. The card must never auto-trigger the Magic LLM on Home load; explicit refresh/find-connections remains user-triggered. If #733 already satisfies every criterion, close this packet as superseded instead of changing code. Add a smoke only for any remaining acceptance gap.

## Acceptance criteria
- Cached cross-project connections can appear on Home without an automatic model call.
- The connection opens the relevant project or moves into Chat with a prepared prompt.
- An explicit find-connections action refreshes Magic when the user asks.
- No duplicate Magic card is added if PR #733 already owns the outcome.
- If #733 satisfies all criteria, the correct implementation outcome is verification/closure with no product diff.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeIntelligence.test.tsx tests/HomeState.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/magic-kitty.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/magic-kitty.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
