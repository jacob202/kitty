# KF-MEMORY-01 — A remembered fact can be pinned, corrected, explained, or forgotten in place

**Initiative:** `kitty-opens-the-doors-20260831-v8`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #731 owns ChatMessage/gateway.ts/queries.ts. Refresh after that stacked Chat PR lands before implementing memory actions.

## What Jacob can do after this
Jacob can inspect a remembered fact and pin it, correct it, understand why Kitty remembers it, or forget it from the same place.

## Why this is the next thing
The backend has pin/correct/explain/delete, but ChatMessage wires only delete; pin/correct/explain have no frontend caller.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Extend the existing memory evidence block in Chat so the same durable memory row exposes Pin, Correct, Explain and Forget. Use the existing /memories/{id}/pin, /correct, /explain and delete contracts; correction is an explicit edit flow, explain shows bounded provenance/reason, and pin state is truthful after reload. Preserve the existing forget grace behavior until the durable undo companion replaces it; do not create a client memory store. Add the smoke file named here.

## Acceptance criteria
- A durable memory row exposes pin, correct, explain and forget actions when it has a memory id.
- Pin reflects durable backend state after reload.
- Correct edits the governed memory through the backend and shows the updated text without inventing a second copy.
- Explain reveals bounded provenance/reason and has an honest unavailable/error state.
- Forget keeps its destructive confirmation/grace behavior and does not silently become permanent on one tap.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/ChatMessage.test.tsx tests/MemoryForget.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/memory-actions.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/memory-actions.spec.ts` at desktop and iPhone-14 widths. Exercise the primary action plus unavailable/degraded truth; no document-level horizontal scroll and no obscured primary control.

**Tier 3 — product acceptance.** An independent reviewer completes the visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the owning stacked PR has not landed, if the required route contract changed, or if implementation would create a second source of truth instead of projecting the existing subsystem.

## Recovery
Frontend projection/state only plus targeted tests and smoke. Revert packet-owned UI edits if the authoritative backend contract cannot be consumed truthfully; do not mutate durable user data to make the smoke pass.
