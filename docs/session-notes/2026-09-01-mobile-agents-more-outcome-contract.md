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
- Current implementation state: production and regression coverage are committed at `dc91e4fe68cf0a6a2dd8bf86964c20c078f67d59`.
- Changed paths and current SHA: `gateway/kitty-chat/src/components/BottomNav.tsx`, `gateway/kitty-chat/tests/BottomNav.test.tsx`, `gateway/kitty-chat/tests/smoke/dogfood-mobile.spec.ts`, and this contract; code SHA `dc91e4fe68cf0a6a2dd8bf86964c20c078f67d59`.
- Known failures/blockers: the initial build with an external `node_modules` symlink was rejected by Turbopack; a local lockfile install resolved the environment issue. No source or acceptance blocker remains.
- Exact next verification action: publish the reviewed branch and confirm the PR receives the required Product Acceptance metadata.

## Verifier report

| Criterion | Verdict (`PASS`, `FAIL`, `UNVERIFIED`) | Evidence | Required repair |
|---|---|---|---|
| AC-1 | PASS | `npm test -- tests/BottomNav.test.tsx` passed 9/9; mobile dogfood passed 5/5 and explicitly selected Agents before observing the `Global Agent Room` heading. Independent reviewer confirmed the route reaches the existing `AgentWorkspacePanel`. | None. |
| AC-2 | PASS | The focused test covers `activeView="agents"`; mobile dogfood asserted More has `aria-current="page"` after selecting Agents. Independent reviewer confirmed the shared `SECONDARY_IDS` predicate. | None. |
| AC-3 | PASS | Mobile dogfood passed 5/5 on the reviewed build, including the all-destinations overflow/nav-clearance sweep with Agents; desktop navigation smoke passed 2/2. Independent reviewer confirmed the degraded Agent Room path is covered. | None. |

## Final state

- `verified`

Evidence-bound summary: Full Vitest passed 95 files / 725 tests; `npm run build` exited 0 with TypeScript completed; mobile dogfood passed 5/5; desktop navigation smoke passed 2/2; `git diff --check` passed. A separate read-only reviewer inspected commit `dc91e4fe68cf0a6a2dd8bf86964c20c078f67d59`, reran the focused and mobile checks, found no Critical, Important, or Minor issues, and returned PASS for all three criteria.
