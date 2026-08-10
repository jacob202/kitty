# KPROOF Retry This Work — Implementation Plan

**Design:** `docs/superpowers/specs/2026-08-10-kproof-retry-this-work-design.md` @ `203a5e29e198e65c37f28f91be9bf2c7c9f2ceb3`

**Goal:** Replace the embedded Work → Builder packet's raw requeue control with a confirmed, user-facing **Retry this work** flow whose progress is derived only from refreshed durable Builder state.

**Allowed product files only:**

- `gateway/kitty-chat/src/components/BuilderSurface.tsx`
- `gateway/kitty-chat/src/lib/queries.ts`
- `gateway/kitty-chat/tests/BuilderSurface.test.tsx`
- `gateway/kitty-chat/tests/smoke/retry-work.spec.ts`

If implementation requires a backend or any other path, stop with `needs_decision`; do not widen scope.

## Task 1 — Pin the confirmation contract with component tests

In `BuilderSurface.test.tsx`, create a failed selected packet fixture and write RED tests proving:

1. detail view exposes a button named `Retry this work` and no primary button named `requeue`;
2. clicking `Retry this work` opens a preview containing the selected packet identity and sends no mutation;
3. `Cancel` closes preview and still sends no mutation;
4. `Confirm retry` sends exactly:

```ts
{
  action: 'requeue',
  initiativeId: deadPacket.initiative_id,
  packetId: deadPacket.packet_id,
}
```

5. the confirmation copy states that existing Builder policy/budget governs subsequent execution and that completion waits for durable evidence.

Run RED:

```bash
cd gateway/kitty-chat && ./node_modules/.bin/vitest run tests/BuilderSurface.test.tsx
```

Expected: new tests fail because the current UI renders raw `requeue` immediately with no preview.

## Task 2 — Implement the smallest retry control

In `BuilderSurface.tsx`:

- preserve the existing `needsAction` eligibility;
- add local preview-open state only for confirmation UX, never as execution truth;
- replace the primary `requeue` button with `Retry this work`;
- first click opens inline preview and performs no mutation;
- preview offers `Confirm retry` and `Cancel`;
- confirm calls the existing `runAction('requeue')`, closes preview, and uses the existing accepted/failed callback handling;
- preserve `pendingConfirmationRef`: mutation success means accepted, not complete;
- do not add another API, queue, or persistent UI workflow state.

Run component test again and make the new confirmation tests GREEN.

## Task 3 — Pin durable phase mapping

Add RED component tests that rerender the same selected packet through authoritative snapshots and assert user-visible phases:

- mutation accepted while durable packet unchanged → `accepted` / waiting, never complete;
- `task_state='queued'` → `queued`;
- `task_state in {'claimed','running'}` with no later evidence → `running`;
- latest attempt has validation evidence but no review → `validation`;
- latest attempt has review evidence while packet not done → `review`;
- `task_state='done'` → `complete`;
- failed/blocked/cancelled after retry → attention/failure, never complete.

Implement a pure helper in `BuilderSurface.tsx`, e.g. `retryProgress(packet)`, that derives the phase only from current `BuilderPacketStatus` fields. Local accepted state may precede durable confirmation, but must not override a durable failure.

Keep exact control-plane data available in the surrounding inspector; only the primary recovery/progress copy is translated to user language.

## Task 4 — Preserve the existing mutation truth boundary

Inspect `useBuilderAction()` in `queries.ts`. It already:

- throws when `executeBuilderAction()` returns `{ok:false}`;
- invalidates `['runtime-manifest']` on success.

Do not rewrite working behavior. Change `queries.ts` only if the new smoke/component tests expose a concrete gap. Any edit must preserve those two contracts exactly.

Component tests must continue to prove visible failure on `onError` and accepted-not-complete on `onSuccess` with unchanged durable state.

## Task 5 — Add the launched-app retry journey

Create `gateway/kitty-chat/tests/smoke/retry-work.spec.ts` using the existing smoke fixtures and real Next app.

The browser test may provide deterministic Gateway responses at the browser boundary, but it must drive actual rendered Work UI and inspect the actual network request. It must:

1. stub `/proxy/health` through existing smoke fixture;
2. stub `/proxy/runtime/manifest` with one failed packet;
3. navigate to Work and click `View packet <title>` in the embedded Builder surface (do **not** route through the old `Open full Builder` inspector);
4. assert `Retry this work` visible and raw `requeue` primary button absent;
5. click `Retry this work`; assert preview and zero `/proxy/builder/action` requests;
6. cancel once; assert zero requests;
7. reopen and confirm; assert exactly one POST whose body identifies `action:'requeue'`, initiative, and packet;
8. in a rejection case return `{ok:false,error:'...'}` and assert visible failure;
9. in an accepted case return `{ok:true,action_id:'...'}` and assert accepted/waiting text but no complete claim;
10. advance the stubbed runtime-manifest through queued → running → validation → review → done and assert the corresponding user-facing phases;
11. hold the manifest unchanged after acceptance and assert no false complete state.

Do not invoke a real paid/provider action from this browser test.

## Task 6 — Deterministic validation and self-review

Run exactly:

```bash
cd gateway/kitty-chat && ./node_modules/.bin/vitest run tests/BuilderSurface.test.tsx
KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && npx playwright test tests/smoke/retry-work.spec.ts
```

Then run the relevant retained UI gate/build if available without expanding code scope.

Review the diff against the design and reject the implementation if it:

- edits outside the four allowed paths;
- calls mutation before confirmation;
- treats mutation success as completion;
- derives completion from local state rather than Builder facts;
- weakens `{ok:false}` handling or runtime-manifest refresh;
- routes the KPROOF journey through the older full-Builder inspector;
- adds backend/orchestration/provider work.

## Acceptance checklist

- Contextual action is named **Retry this work**.
- Approval preview occurs before the mutation.
- Cancel is mutation-free.
- Confirm sends exactly one existing `requeue` action for the selected packet.
- Existing `{ok:false}` rejection is preserved.
- Existing authoritative `runtime-manifest` invalidation is preserved.
- Accepted response alone never means complete.
- Durable packet/attempt evidence drives queued → running → validation → review → complete.
- Durable failure returns to attention.
- Component test is green.
- Runtime-marked Playwright journey is green.
- No path outside the four-file contract changed.
