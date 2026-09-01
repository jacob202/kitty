# KF-DEADEND-01 — Every registered view and error either works or points to a concrete fix

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns ViewRenderer and PR #735 owns ViewRenderer/views.tsx. Let the stacked registry changes land, then re-audit reachability against the final tree.

## What Jacob can do after this
Jacob never lands on a fake placeholder or inert error: a view works, redirects truthfully, or gives him the concrete action that fixes the problem.

## Why this is the next thing
The registry still defines many PlaceholderView entries while real routing is split through ViewRenderer; RightPanel has no obvious caller and Terminal reachability is inconsistent. PRs #733 and #735 currently modify ViewRenderer/views.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Reconcile the view registry after the visible-product stack lands. Remove PlaceholderView registrations that are no longer real destinations, wire real components only through the canonical ViewRenderer/views registry, and decide explicitly whether RightPanel and TerminalView remain supported surfaces or are removed from navigation/reachability. Audit primary error states touched by this reconciliation so each offers an existing recovery action/deep link when one exists; do not add generic “try again” buttons that cannot work. Preserve direct links for supported views and a truthful fallback for retired ids. Add a navigation/dead-end smoke.

## Acceptance criteria
- No user-selectable registered view renders PlaceholderView as its final surface.
- Each supported view id resolves to one real owning component; retired ids fail/redirect truthfully rather than showing an empty placeholder.
- RightPanel and TerminalView are either deliberately reachable with a product reason or removed from dead navigation/registry paths.
- Primary reconciled error states expose a concrete working recovery action when one exists.
- Direct navigation and mobile/desktop ViewRenderer behavior remain covered.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/KittyContextViewRecovery.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/view-deadends.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/view-deadends.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
