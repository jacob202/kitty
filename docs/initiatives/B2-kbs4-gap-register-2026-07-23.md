# B2: KB-S4 / Builder Closeout Gap Register
*Audited 2026-07-23, based on B1 preflight evidence*

## Landed (No Action)

| Gap | Evidence |
|-----|----------|
| **KX-03 shell decomposition** | View registry, 7-surface rail, mascot state machine — committed e6318cf |
| **KX-04 surface refit** | Shared Button/WorkCard/StatusBadge across 5 surfaces — committed e6318cf |
| **KX-05 companion layer** | Builder actions (5), onboarding, import route, builder control — committed e6318cf |
| **CHAT-RECOVERY (CR 01-05)** | Thread goals, signal cards, memory trailer, memory block UI — all done |
| **BUILDER-TEST-HARDENING** | Fail-loud sweep (TH-01), route contracts (TH-02), CI ratchet (TH-03) — all done |
| **PACKET-027** | Recovery budget, stale artifacts, reconciliation, truthful closeout — all done |
| **CP08 campaign B** | Column, filter, prototype — done; tests-docs pending |

## Needs Jacob (Decision Required)

| Gap | Details |
|-----|---------|
| **reasoning-backend-v1** | 3 packets since Jul 18: complexity classifier, tier context budget, execution receipts. Blocked on: no design spec, no assigned model tier, unclear how this integrates with existing LLM routing. Decision needed: pick one packet to prototype or cancel the lane. |

## Unsafe to Automate

| Gap | Why |
|-----|-----|
| **Auto-merge without human review** | CP-06 tripwire (2 reverts in last 10 merges) has never been tested. Merge rail (L-CAND-15) is documented but the revert drill (§3.3 negative test 4) was never executed. Unattended merge remains unsafe until the tripwire is proven. |
| **Mission ingress (CP-09)** | ADR 0017 runtime: Mission schema, acceptance tests, submission bridge, result projections. This is the "Kitty, build X" loop — 2-3 weeks of work, blocks nothing in daily use. |

## Eligible Follow-up Packets

### 1. B7: Home Run-Next Button
- **Scope**: One POST endpoint + one UI button on the Builder card
- **Allowed paths**: `gateway/routes/builder_control.py`, `gateway/kitty-chat/src/components/BuilderSurface.tsx`, `gateway/kitty-chat/src/lib/gateway.ts`
- **Dependencies**: None (builder_control route exists, BuilderSurface renders)
- **Estimated effort**: L

### 2. B8: Initiative Progress Card
- **Scope**: Read-only card per initiative showing state, progress, blocker, next action
- **Allowed paths**: `gateway/kitty-chat/src/components/BuilderSurface.tsx`, `gateway/kitty-chat/src/components/HomeState.tsx`
- **Dependencies**: Runtime manifest already provides BuilderStatusSnapshot
- **Estimated effort**: M

### 3. CP08-B Tests Documentation
- **Scope**: Verify test suite passes, document test coverage gaps
- **Allowed paths**: `docs/`, `tests/`
- **Dependencies**: None
- **Estimated effort**: S

### 4. Builder Surface Full Refit
- **Scope**: Replace remaining 8 inline buttons in BuilderSurface (965 lines) with shared Button component
- **Status**: Import added, buttons not yet replaced
- **Estimated effort**: M

## Dependency Graph
```
B7 (run-next button) ──┐
                        ├──> Gate: daily use
B8 (progress card) ────┘
                        │
B2 (this doc) ──> B3 (materialize one gap)
```
