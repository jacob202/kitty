# Mobile Agents More Menu — Outcome Contract

## Identity

- Task: Expose the existing Agents workspace from the mobile More menu.
- Execution owner: `interactive`
- Branch/worktree: `fix/mobile-agents-more-20260901` / `/private/tmp/kitty-agents-more-20260901`
- Base SHA: `fe8295e359c2cf7530f455ad170183756c630618`
- Repair-cycle limit: `2`

## User-visible outcome

On a phone-sized Kitty viewport, a user can open More, choose Agents, and reach the existing Agents workspace. The More control remains the current navigation indicator while Agents is active, and the route remains usable without horizontal overflow when the Agent Room is degraded or unavailable.

## Acceptance criteria

| ID | Observable criterion | Verification command or interaction | Required evidence |
|---|---|---|---|
| AC-1 | Mobile More contains an Agents menu item, and selecting it calls the existing `agents` view route. | `npm test -- tests/BottomNav.test.tsx`; on an iPhone-class Playwright viewport, click More then Agents and observe the Agents workspace route. | Focused component test plus mobile browser evidence. |
| AC-2 | More is marked current while the `agents` view is active. | `npm test -- tests/BottomNav.test.tsx`; inspect the mobile navigation state after routing to Agents. | Focused component assertion plus browser assertion. |
| AC-3 | The mobile destination sweep includes Agents and completes without horizontal overflow or fixed-nav overlap in the available/degraded Agent Room state. | `PLAYWRIGHT_REUSE_EXISTING_SERVER=0 PLAYWRIGHT_PORT=<free-port> ./node_modules/.bin/playwright test tests/smoke/dogfood-mobile.spec.ts --project=mobile --workers=1`; rerun the relevant desktop smoke/navigation check if needed. | Playwright result from the reviewed SHA. |

## Non-goals

- Do not change Agent Room APIs, backend behavior, Builder packets, or AgentWorkspacePanel content.
- Do not add Agents to the desktop rail in this lane.
- Do not merge the PR.

## Prohibited shortcuts

- Do not infer runtime success from code inspection alone.
- Do not treat the implementer’s own review as independent acceptance.
- Do not silently weaken a criterion after implementation begins.
- Do not replace unavailable evidence with optimistic language.

## Context that must survive compaction or handoff

- Accepted requirements and decisions: add the existing `agents` view to mobile `SECONDARY_ITEMS`; update the narrow BottomNav and mobile dogfood coverage.
- Current implementation state: production code and tests not yet changed.
- Changed paths and current SHA: contract only at task start; implementation SHA TBD.
- Known failures/blockers: none known; independent review and live browser proof are required.
- Exact next verification action: inspect the isolated worktree, apply the three-file bounded change, then run focused component tests.

## Verifier report

| Criterion | Verdict (`PASS`, `FAIL`, `UNVERIFIED`) | Evidence | Required repair |
|---|---|---|---|
| AC-1 |  |  |  |
| AC-2 |  |  |  |
| AC-3 |  |  |  |

## Final state

Choose exactly one:

- `verified`
- `implemented, awaiting verification`
- `blocked`
- `failed`

Evidence-bound summary:
