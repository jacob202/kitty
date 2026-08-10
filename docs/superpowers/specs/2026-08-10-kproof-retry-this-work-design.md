# KPROOF Retry This Work — Product Design

**Parent:** KPROOF-001  
**Observed base:** `68687b50c8f18ef0e422e86614bf65f86f47dd50`  
**Runtime reproduction:** 2026-08-10, launched `kitty-chat` Work view with a disposable browser-bound failed-packet runtime fact; no Gateway/Builder state was mutated.

## Problem proven in the running UI

The embedded Work → Builder surface is the current trustworthy surface. For a failed packet it renders:

- explanatory copy: `This packet is dead — requeue to retry.`
- action button: `requeue`
- no `Retry this work` action;
- no approval/confirmation preview before mutation.

The older **Open full Builder** destination routes to a different inspector/control surface and is not the KPROOF target.

Two defects named by the Aug 4 audit are already repaired on this base and must be preserved, not rebuilt:

- `useBuilderAction()` rejects `{ok:false}` as an error;
- successful mutation invalidates authoritative `['runtime-manifest']`;
- `PacketDetail` already distinguishes request `accepted` from durable-state `confirmed` and never claims completion from the mutation response alone.

## Goal

Turn the existing raw requeue control into a calm, contextual **Retry this work** recovery interaction that asks for one explicit confirmation, reuses the existing action-queue mutation, and narrates progress only from refreshed durable Builder state.

## Exact scope

Only these product paths may change:

1. `gateway/kitty-chat/src/components/BuilderSurface.tsx`
2. `gateway/kitty-chat/src/lib/queries.ts`
3. `gateway/kitty-chat/tests/BuilderSurface.test.tsx`
4. `gateway/kitty-chat/tests/smoke/retry-work.spec.ts`

No backend path is authorized. If the existing `/builder/action` contract proves insufficient, stop and prepare a new Mission version instead of expanding scope.

## Interaction contract

### 1. Contextual entry

For a selected failed/cancelled/stale packet, or one whose attempt budget is exhausted, replace raw control-plane wording with a button labelled **Retry this work**.

The surrounding explanation should use user language. It may retain the exact packet/state evidence elsewhere in the detail view, but the primary action must not require Jacob to know what “requeue” means.

### 2. Approval preview before mutation

First click does **not** call the Gateway. It opens a compact inline confirmation that states, in substance:

- which packet will be retried;
- that Kitty will requeue the existing Builder work rather than create a new unrelated task;
- prior attempt/evidence remains visible;
- subsequent execution remains governed by the existing Builder policy/budget;
- completion will be reported only after durable Builder evidence changes.

Controls: **Confirm retry** and **Cancel**.

### 3. Existing mutation boundary

On **Confirm retry**, call the existing `useBuilderAction()` with:

```json
{
  "action": "requeue",
  "initiativeId": "<selected initiative>",
  "packetId": "<selected packet>"
}
```

Preserve the existing fail-loud contract: `{ok:false}` becomes an error and `runtime-manifest` is invalidated immediately after an accepted action. Do not add a second mutation API.

### 4. Truthful progress language

The mutation response may produce only an **accepted / waiting for Builder state** message.

Use the refreshed packet's durable fields to show the meaningful progression when applicable:

`accepted → queued → running → validation → review → complete`

The phase is derived from `task_state` plus the latest attempt's validation/review evidence. A failed/blocked/cancelled durable state must visibly return to attention instead of advancing to complete.

Do not invent a new workflow state or persist UI-only progress as authority.

### 5. Runtime journey

Create `tests/smoke/retry-work.spec.ts` using the real launched Next app. The test supplies deterministic browser-bound Gateway facts, then proves:

1. failed packet exposes **Retry this work**, not raw `requeue`;
2. first click shows preview and sends no action request;
3. cancel sends no action request;
4. confirm sends exactly one requeue request for the selected packet;
5. `{ok:false}` is shown as failure;
6. `{ok:true}` says accepted but not complete;
7. refreshed manifests drive queued, running, validation, review, then complete presentation;
8. unchanged refreshed state never produces a false completion claim.

This browser test proves the running product behavior and network contract. Builder's real deterministic validation/review state remains the authority for the enclosing KPROOF Mission.

## Acceptance

- No raw `requeue` primary action remains in the selected-packet recovery flow.
- A meaningful confirmation occurs before mutation.
- Existing error and query-refresh semantics remain intact.
- User-visible progress comes from refreshed Builder truth, not callback narration.
- Component tests cover confirmation, no-request-before-confirm, rejection, accepted-not-complete, and durable phase mapping.
- The launched Playwright journey passes.
- Existing `BuilderSurface` tests remain green.
- No backend, provider, routing, memory, dashboard, or orchestration expansion.
