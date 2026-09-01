# KF-GLANCE-02 — Home paints useful content from one response

**Initiative:** `kitty-opens-the-doors-20260831-v1`
**Owner:** interactive
**Depends on:** `KF-GLANCE-01`
**Free or paid:** free
**Base:** `origin/main` `546565246289e6730b518961de64b7f371013b3b`

## Why this has no manifest
This packet changes only the native frontend. Builder has no Node toolchain or `node_modules`, so its gates cannot prove this work. It is deliberately manifest-less and follows the `KT-UI-MOUNT-01` precedent.

## What Jacob can do after this
Open Home and see the daily-priority cards immediately without waiting for a pile of independent gateway requests.

## Why this is the next thing
`HomeState.tsx:1982-1989` renders What's Next, Needs You, Today, Deadlines, and Active Projects as the primary grid. Those children independently mount overlapping reads: What's Next alone mounts actions, needs-Jacob, projects, next steps, todos, and session context at `753-761`; Active Projects repeats projects/next-step data at `984-986`; Needs You repeats actions/inbox at `1494-1499`; Today repeats todos at `1740-1745`; Deadlines adds another request at `1264-1266`.

`KF-GLANCE-01` supplies these primary read sections through `/state/now`. `gateway/kitty-chat/src/lib/gateway.ts:1389-1398` already types the response as a generic `Record<string, GatewayStateSection>`, so this packet does not need a gateway type change.

## Plan
1. In `HomeState.tsx`, mount `useStateNow()` once at the Home root and derive the primary-grid read data from its `actions`, `needs_jacob`, `projects`, `project_next_steps`, `todos`, and `deadlines` sections.
2. Refactor the five primary cards to accept composed read data plus per-section error/loading state instead of mounting their own duplicate GET hooks. Keep their mutation hooks and visible actions intact.
3. A failed section renders only that card's plain-language error/retry state. Other successful sections paint normally; no whole-grid loading guard is allowed.
4. Session context becomes deferred enrichment for What's Next only after the composed primary signal is exhausted; it must never block the first useful primary paint.
5. Leave weather and the always-visible HealthStrip as non-blocking secondary reads; they may fill after the primary grid without gating it. Do not pull them into `state_composer` just to chase a one-request vanity metric.
6. Make the closed `More context` and `System & setup` disclosures lazy: their query-owning children are mounted only when the disclosure is open. `systemOpen` already exists; add equivalent open state for More context. If the root repairs check opens System & setup because attention is needed, its children then mount normally. This is required because children inside a closed HTML `<details>` still mount and currently fire their queries.
7. Add focused frontend tests for section mapping, independent degradation, and proof that closed disclosure children do not issue their gateway reads. PR #723 is merged in this base; its Todo/Monitor/WorkCard/ViewRenderer/Automations changes are complete and are not needed for this packet.
8. Add `gateway/kitty-chat/tests/smoke/home-composed-glance.spec.ts`. Route-stub `/proxy/state/now` plus the minimum app-mount health calls, delay one composed section, and prove the other primary cards still render.
9. In that smoke spec measure from navigation start to visible `home-primary-overview` useful content and require it to be under 1500 ms on the route-stubbed gateway at both CI projects. Record the measured duration in the assertion failure message.

## Not in scope
Changing the state-composer backend, the command palette, design-system/card consolidation, skeleton replacement outside Home, query optimism, the content/behavior of secondary Home disclosures, or the already-landed Todo/Monitor surfaces from PR #723. Lazy mounting closed disclosures is in scope; redesigning them is not.

## Verification
**Tier 1 — mechanical.** Not available to Builder. Interactive lane: `cd gateway/kitty-chat && npx vitest run tests/HomeState.test.tsx --reporter=dot` and `npx tsc --noEmit`. The new composed-response assertions are expected RED against the base because the five primary cards mount their own hooks today; this is asserted from source reading, not an observed pre-change run.

**Tier 2 — running app.** `cd gateway/kitty-chat && npx playwright test tests/smoke/home-composed-glance.spec.ts`. It must run under both desktop 1440×900 and iPhone-14 projects, prove useful primary content within 1500 ms on a route-stubbed gateway, prove one failed/delayed section does not blank siblings, prove closed disclosure routes are not requested before opening, and assert no document-level horizontal overflow.

**Tier 3 — product acceptance.** An independent reviewer opens Home on desktop and iPhone-class widths, confirms What's Next/Needs You/Today/Deadlines/Active Projects are independently useful, exercises at least one primary action, and repeats once with one backing source unavailable.

Standing visible criteria: every primary control completes or is disabled with one plain-language reason; no raw server/status/port/env/path text is the primary error; rejected/failed actions never leave a false success state; neither viewport has horizontal overflow, clipping, or an off-screen primary control.

## Stop condition
If implementing this requires rebuilding the landed Todo/Monitor surfaces or making a secondary/system diagnostic part of the blocking primary response, stop and re-scope rather than growing another frontend state machine.

## Recovery
Frontend-only and cache/read refactoring. If the attempt fails, revert this packet's files and restore the old hook calls; no persisted user data is changed by the read-path refactor.