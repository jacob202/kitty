# KF-SESSION-01 — Home’s headline “what’s next” uses Jacob’s product session, not coding-agent handoff files

**Initiative:** `kitty-opens-the-doors-20260831-v7`
**Owner:** interactive (held)
**Builder manifest:** none
**Base:** `origin/main` `f5b2f38c098dcdd7f46d1d58abb672ef15b75c5f`
**Dependencies:** none

Interactive/UI packet intentionally held out of execution. Hold reason: PR #733 owns HomeState and may change the headline inputs. Let it land, then verify this bug against the final Home tree before editing.

## What Jacob can do after this
Jacob’s Home headline reflects his actual Kitty work/life context and can never show Claude Code’s branch notes as his “last session.”

## Why this is the next thing
Home’s headline calls useSessionContext, whose Gateway route parses the coding agent’s .claude/HANDOFF.md and .claude/STATE.md, so developer scratchpad can be presented as Jacob’s day.

## Plan
1. Add or update the narrow regression that proves the current finding.
2. Implement the objective strictly inside the declared allowed-path fence.
3. Run the packet gates and inspect the final diff for scope drift.

## Not in scope
- Work outside the declared allowed paths or beyond the stop condition.
- A parallel queue, state machine, registry, provider path, or persistence layer.
- Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.

## Objective
Remove the product Home dependency on /session/context when that endpoint is sourced from .claude/HANDOFF.md/.claude/STATE.md. Replace the hero input with product-owned truths already available to Home (life awareness, Work/Activity, projects, deadlines, returned insights, or a dedicated product session projection if one already exists after the stack lands). The headline must never label developer branch/handoff notes as Jacob’s last session/next action. Preserve an honest empty state when no product next step is known. Add a smoke that seeds developer handoff text and proves it never appears on Home.

## Acceptance criteria
- Home never renders .claude handoff/state content as Jacob’s last session or next action.
- The headline is driven only by product-owned user/session/work context.
- When no product next step exists, Home says so honestly instead of falling back to developer notes.
- Developer handoff files may continue serving coding agents; this packet does not repurpose or delete them.
- The primary Home card remains actionable when a real product next step exists.

## Verification
**Tier 1 — mechanical.** Not run while held. After the hold clears, run:
  - `cd gateway/kitty-chat && npx vitest run tests/HomeState.test.tsx --reporter=dot`
  - `cd gateway/kitty-chat && npx playwright test tests/smoke/home-session-truth.spec.ts`

**Tier 2 — running app.** Run `gateway/kitty-chat/tests/smoke/home-session-truth.spec.ts` at desktop and iPhone-14 widths. Exercise the primary happy path, reload where relevant, and one degraded/error path; primary controls must remain visible and unobscured.

**Tier 3 — product acceptance.** An independent reviewer completes the user-visible workflow in the running product at desktop and iPhone-14 widths and records Product Acceptance before merge.

Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.

## Stop condition
Stop if the named owning PR/dependency has not landed, if the backend contract is not truthful enough to support the UI, or if the change would create a parallel source of truth.

## Recovery
Frontend state/projection plus tests only. Revert packet-owned UI edits if the authoritative backend cannot support the acceptance contract; never alter durable product data to make the smoke pass.
