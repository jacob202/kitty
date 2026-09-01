# KF-TIMELINE-01 — Activity becomes the truthful “what has Kitty actually done?” timeline

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #729 owns the Activity Center/gateway.ts/queries.ts. Let it land first, then extend that surface rather than creating a competing timeline UI.

## What Jacob can do after this
Jacob can open Activity and answer “what has Kitty actually done?” in one chronological place, opening or undoing an entry when the backend truly supports it.

## Why this is the next thing
gateway/activity_timeline.py and /activity/timeline already exist with no frontend caller, while PR #729 independently adds a live Activity Center over a smaller set of authorities.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Use the Activity Center introduced by PR #729 as the UI door for gateway/activity_timeline.py instead of creating a second activity product. Add the unified chronological evidence feed, bounded filters and deep links to the owning surface. Where a timeline entry exposes a real undo journal id/action, offer Undo in place; otherwise only Open is shown. Keep the newer /activity attention projection for live “needs you/in motion” grouping and add timeline as history, not a competing authority. Add the smoke file named here.

## Acceptance criteria
- One Activity surface can show recent chronological evidence across the existing ledgers.
- Timeline entries open the owning object/surface using stable ids.
- Undo is shown only when a real undo action/journal entry exists.
- A failed source degrades the timeline honestly instead of turning the whole feed into fake empty.
- The existing Activity attention groups from PR #729 remain intact.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/ActivityCenter.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/activity-timeline.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/activity-timeline.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
