# KF-NOSPIN-01 — Loading preserves layout and intent prefetch removes avoidable waits

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns HomeState and PRs #729/#731/#733/#735 own queries.ts. Release after that stack lands and recount remaining bare-loading cases instead of blindly fixing stale line numbers.

## What Jacob can do after this
Jacob can move through Kitty without cards collapsing into spinners or waiting again for data Kitty could safely fetch on intent.

## Why this is the next thing
The audit found multiple bare Loading strings and zero prefetching, while the current stack is actively changing Home and shared queries.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Replace bare loading strings on the primary Home/Work/Automations/Library transitions with skeletons that match final card geometry, and prefetch bounded read-only data on clear intent (hover/focus/touch-start/navigation intent) using the existing query keys. Never prefetch mutations, paid work, or large unbounded payloads. Keep degraded/error states distinct from loading. Add a smoke that asserts stable geometry and that intent prefetch avoids a duplicate visible wait.

## Acceptance criteria
- Primary transitions use layout-matching skeletons instead of bare Loading text.
- Skeletons reserve approximately the final geometry so content arrival does not cause disruptive layout jumps.
- Intent prefetch uses existing query keys and only bounded read-only endpoints.
- Prefetch failure is silent until the user actually opens the surface, where normal error truth applies.
- No mutation, paid model call or unbounded dataset is prefetched.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeState.test.tsx tests/WorkViewProjection.test.tsx tests/AutomationsView.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/no-spin.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/no-spin.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
