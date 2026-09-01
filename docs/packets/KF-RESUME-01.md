# KF-RESUME-01 — Reload during a reply reattaches to the durable turn instead of losing it

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: Backend prerequisite KF-RESUME-BE-01 cannot start until PR #732 lands, and PR #732 also owns KittyContext. Release the UI packet only after the backend resume contract is proven.

## What Jacob can do after this
Jacob can reload in the middle of a long answer and come back to that same answer instead of losing the reply or accidentally sending it twice.

## Why this is the next thing
isStreaming is browser-local state; although the Gateway emits durable turn headers and has lifecycle reads, the client does not capture/reconcile those ids on reload.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Consume the durable lifecycle/turn contract from KF-RESUME-BE-01. Capture X-Kitty-Turn-ID/X-Kitty-Attempt-ID from the chat response, associate them with the active chat, and on mount/reload query the canonical lifecycle for any running/completed turn. Reattach/poll/stream from the backend-supported resume seam until the final assistant result is present; do not synthesize completion from local partial text. If the backend says interrupted or failed, render that terminal truth with Retry. Clear resume metadata only after terminal reconciliation. Add a reload-mid-stream Playwright smoke.

## Acceptance criteria
- Reloading while a reply is running returns to the same durable turn rather than starting a duplicate turn.
- When the server finishes the original turn, the final assistant answer appears exactly once after reload.
- Interrupted/failed turns show their durable state and Retry; the UI never leaves an eternal typing indicator.
- A completed turn clears local resume metadata after canonical reconciliation.
- Normal send/retry/stop behavior remains correct when no reload occurs.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/chatClient.test.ts tests/ResumeStream.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/chat-resume.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/chat-resume.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
