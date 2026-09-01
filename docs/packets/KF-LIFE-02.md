# KF-LIFE-02 — Home shows today, what is coming, and evening reflection as actions

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns HomeIntelligence/HomeState and may already satisfy part of this packet; backend KF-LIFE-01 is also awaiting operator review. After #733 and KF-LIFE-01 resolve, verify first and implement only the remaining acceptance gap.

## What Jacob can do after this
Jacob can see the useful part of today and what is coming on Home, then act on it directly without being shown a calendar dump.

## Why this is the next thing
Life awareness is routed but Home did not expose its full actionable today/upcoming/evening contract; PR #733 now partially surfaces life-aware proactive suggestions.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Finish the Life door on the Home intelligence surface after the current Home stack lands. Project today context, the next meaningful upcoming item and evening reflection only when the backend says the source is available; each visible suggestion carries its existing action id/target and is executable from the card. Healthy empty and source unavailable must render differently. Reuse the selective Home intelligence surface from PR #733 if it lands; do not add another dashboard section. Add the targeted smoke file named here.

## Acceptance criteria
- Today context appears only when it has something meaningful to say.
- Upcoming and evening-reflection notices carry an in-place action when the backend supplies one.
- Calendar/source unavailable is not rendered as a free day or healthy empty state.
- The Home surface remains selective and bounded rather than becoming a life-data dashboard.
- No automatic paid/model call is triggered by merely opening Home.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeState.test.tsx tests/HomeIntelligence.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/life-home.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/life-home.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
