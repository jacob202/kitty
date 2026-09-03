# OK-WORK-01 — Work Becomes a Complete Operating Surface

**Status:** draft candidate; not activated
**Roadmap phase:** 2 — primary surfaces
**Owner at activation:** interactive or Builder after fresh fence/toolchain check

## Mission
Make Work the one place Jacob can understand and control meaningful execution without dropping into Builder internals or a terminal.

## Depends on
- `OK-ACTION-01/02` shared object/action grammar.
- Runtime truth (`KH-RUNTIME-01`) before final Product Acceptance.
- Existing Work/Builder projection and action authority remain canonical.

## Product acceptance moment
Open Work with a mix of runnable, running, waiting-for-user, failed, completed, and unavailable work. From that screen Jacob can start what is actually startable, inspect what is happening, approve only when approval is genuinely required, retry/unblock where supported, stop/cancel where supported, open evidence/results, and ask why an item cannot proceed.

## Required behavior
- `Create/plan/start` uses the existing owning workflow; Work does not invent a second queue.
- Each row/card has one truthful state, a product-facing title, and a canonical destination/reference.
- Waiting for Jacob is distinct from Builder review, provider wait, queued, blocked, and failed.
- `Retry`, `unblock`, `resume`, `cancel/stop`, and `open result/evidence` appear only when the owner supports them.
- Failure preserves the failed context and offers the real recovery path, not a generic no-op Try again.
- `Why didn't this run?` consumes the existing why-not/explanation path (`KF-WHY-01/02`) when available.
- Completed work keeps its result/evidence discoverable after reload.
- Builder unavailable/degraded never turns into an empty-success Work screen.
- Operator-only queue/lease/packet details stay behind disclosure; normal rows use product language.

## Integration points to inspect
- `gateway/kitty-chat/src/components/WorkView.tsx` and Work subcomponents.
- Existing work/action clients in `gateway/kitty-chat/src/lib/work.ts`, `gateway.ts`, queries and Builder projections.
- `OK-ACTION-*`, `KF-WHY-*`, Activity/evidence/result relationships.

## Verification
**Tier 1:** focused Work/action tests, TypeScript, and any changed Gateway tests. Add regressions for every newly enabled action/state.

**Tier 2:** desktop + iPhone-class running-app scenario covering: one runnable item, one waiting-for-user item, one failure/retry path, one completed result/evidence path, and Builder unavailable. Reload during/after an active item.

**Tier 3:** independent reviewer completes the scenario without using Builder CLI, packet IDs, ports, or terminal commands.

## Non-goals
- Rewriting KittyBuilder.
- Exposing every Builder field.
- A second Work database/state machine.
- Making every historical packet runnable.

## Done when
Work is sufficient for the normal execution lifecycle and there is no prominent state that requires Jacob to leave the product merely to perform the obvious next action.
