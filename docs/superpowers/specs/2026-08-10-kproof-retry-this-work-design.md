# KPROOF Retry This Work — Product Design

**Parent:** KPROOF-001  
**Execution base:** `7916d78c82738dd523f22ce683b62c56a66d3ef7` (repaired `origin/main`)  
**Runtime reproduction:** 2026-08-10, launched current Work → Builder UI with a disposable browser-bound failed-packet runtime fact; no Gateway/Builder state was mutated.

## Current behavior proven in the running UI

The embedded Work → Builder surface is the current trustworthy recovery surface. For a failed packet it renders `This packet is dead — requeue to retry.`, a primary action `requeue`, no `Retry this work` action, and no approval/confirmation preview before mutation.

`Open full Builder` routes to a separate older inspector/control surface and is not this KPROOF target.

Two older audit defects are already repaired on this base and must be preserved rather than rebuilt: `useBuilderAction()` throws when an action response is `{ok:false}`; accepted actions invalidate authoritative `['runtime-manifest']`; and `PacketDetail` distinguishes mutation `accepted` from durable-state `confirmed` rather than treating callback success as completion.

## Goal

Turn the existing raw requeue control into a calm contextual **Retry this work** interaction that asks for one explicit confirmation, reuses the existing action-queue mutation, and presents progress only from refreshed durable Builder state.

## Exact scope

Only these product paths may change:

1. `gateway/kitty-chat/src/components/BuilderSurface.tsx`
2. `gateway/kitty-chat/src/lib/queries.ts`
3. `gateway/kitty-chat/tests/BuilderSurface.test.tsx`
4. `gateway/kitty-chat/tests/smoke/retry-work.spec.ts`

No backend path is authorized. If `/builder/action` proves insufficient, stop and prepare a new Mission version.

## Interaction contract

For selected failed/cancelled/stale work, or exhausted attempt budget, present **Retry this work** as the primary recovery action. Keep exact packet/state evidence available elsewhere, but do not require Jacob to understand control-plane word `requeue`.

First click performs no mutation. Show an inline preview that identifies the selected packet and explains that the existing Builder packet is requeued rather than replaced by unrelated work, prior evidence remains visible, subsequent execution stays under existing Builder policy/budget, and completion is reported only after refreshed durable evidence changes. Actions: **Confirm retry** and **Cancel**.

Confirm calls the existing `useBuilderAction()` as action `requeue` with the selected initiative/packet IDs. Preserve fail-loud `{ok:false}` handling and immediate `runtime-manifest` invalidation. Add no second API or state machine.

Mutation response can mean only accepted/waiting. Translate refreshed durable facts into meaningful phases when applicable: `accepted → queued → running → validation → review → complete`. Derive the phase from `task_state` plus latest attempt validation/review evidence. Durable failed/blocked/cancelled must visibly return to attention. UI-only state never becomes execution authority.

## Runtime journey

Create `tests/smoke/retry-work.spec.ts` against the real launched Next app. Browser-bound deterministic Gateway responses are allowed so the test can safely prove rendered/network behavior without dispatching paid work. It must prove failed packet shows **Retry this work**, first click sends no action request, cancel sends none, confirm sends exactly one requeue request for the selected packet, `{ok:false}` is visibly failed, `{ok:true}` is accepted but not complete, refreshed manifests drive queued/running/validation/review/complete, and unchanged durable state never produces false complete.

The enclosing Builder Mission—not the browser stub—remains authority for actual implementation/validation/review.

## Acceptance

- **Retry this work** replaces raw `requeue` as the primary recovery action.
- Confirmation occurs before mutation.
- Cancel is mutation-free; Confirm issues exactly one existing requeue request.
- Existing error and authoritative-refresh semantics remain intact.
- Progress copy comes only from refreshed Builder facts.
- Durable failure never displays complete.
- Component tests cover confirmation, rejection, accepted-not-complete, and phase mapping.
- Launched Playwright journey passes.
- No backend/provider/routing/memory/dashboard/orchestration expansion.
