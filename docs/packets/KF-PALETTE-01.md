# KF-PALETTE-01 — Cmd-K opens what it finds and runs safe actions instead of previewing dead rows

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #726 owns CommandPalette and gateway.ts. After it lands, verify which original preview-only search gaps remain and extend that implementation rather than replacing it.

## What Jacob can do after this
Jacob can hit Cmd-K, find a real Kitty object or capability, and open/do the obvious thing instead of landing on “preview only.”

## Why this is the next thing
The old palette found several object kinds but mapped only knowledge hits to a destination; PR #726 now owns CommandPalette and adds live capability launch without necessarily fixing those search dead ends.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Build on the capability-first CommandPalette from PR #726. Preserve its live capability/Skill launch behavior, then make global search results actionable: map each supported hit kind (todo, governed memory, journal, inbox/knowledge) to its existing owning surface and stable id, and expose safe existing actions where the backend already supports them. Do not implement action execution by parsing labels or inventing new authority. Unsupported hits remain visible with a truthful reason rather than disabled “preview only” with no path forward. Add the smoke named here.

## Acceptance criteria
- Todo, governed memory, journal and inbox/knowledge search hits open their owning surface/object when a stable destination exists.
- Safe palette actions call existing backend operations; no action is inferred from free-form result text.
- PR #726 capability and Skill-launch behavior remains intact.
- A hit with no valid destination says why it cannot be opened rather than silently disabling itself.
- Keyboard navigation, Escape and mobile palette behavior remain correct.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/CommandPalette.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/palette-actions.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/palette-actions.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
