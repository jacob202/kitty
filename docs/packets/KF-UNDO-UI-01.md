# KF-UNDO-UI-01 — Completed reversible actions expose durable Undo and Undo history

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #731 owns ChatMessage/ActionCard/gateway.ts/queries.ts and the corrective backend Undo owner must settle before UI integration. Release after both settle.

## What Jacob can do after this
Jacob can let Kitty do reversible work, then undo it after it actually happened—not just cancel a timer before the request fires.

## Why this is the next thing
Backend memory delete already returned undo_journal_id while deleteMemory typed Promise<void>, and the backend Undo corrective wave extends undoability; PR #731 now owns Chat action rendering.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Consume the backend undo_journal_id/action contract from mutation results instead of discarding it. Show an Undo affordance on completed reversible action results and expose recent undoable history from the existing journal authority. The current five-second pre-send “undo forgetting” timer is only cancellation-before-delete and must not be presented as durable undo after a mutation commits. Undo success re-reads the owning object; undo failure keeps the journal entry visible with the backend reason. Add the smoke file named here.

## Acceptance criteria
- A committed reversible mutation that returns an undo journal id exposes Undo on its result.
- Undo calls the existing restore authority and refreshes the owning object/state from the server.
- The existing pre-delete grace timer is labelled/treated as cancellation, not durable post-commit undo.
- Recent undoable history is reachable without inventing a client journal.
- Non-undoable actions never show a fake Undo control.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/ChatMessage.test.tsx tests/ActionCard.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/undo.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/undo.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
