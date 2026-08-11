# KPROOF Retry This Work — Implementation Plan

**Design:** `docs/superpowers/specs/2026-08-10-kproof-retry-this-work-design.md` @ `36ed948d58a4a611a558e3b8d2c82b6f8ede5be1`

**Goal:** Replace the embedded Work → Builder raw requeue control with a confirmed **Retry this work** flow whose progress is derived only from refreshed durable Builder state.

**Allowed files only:**
- `gateway/kitty-chat/src/components/BuilderSurface.tsx`
- `gateway/kitty-chat/src/lib/queries.ts`
- `gateway/kitty-chat/tests/BuilderSurface.test.tsx`
- `gateway/kitty-chat/tests/smoke/retry-work.spec.ts`

If any other path is required, stop with `needs_decision`.

## 1. Confirmation contract — RED first

In `BuilderSurface.test.tsx`, add failed selected-packet tests proving:
- primary recovery button is `Retry this work`, not `requeue`;
- first click opens an inline preview naming the selected packet and performs no mutation;
- Cancel closes preview and performs no mutation;
- Confirm retry sends exactly `{ action:'requeue', initiativeId:<selected>, packetId:<selected> }`;
- preview says existing Builder policy/budget still governs later execution and completion waits for durable evidence.

Run the focused component test during implementation to verify RED/GREEN. The immutable Builder validation gate is the repo-supported `make ui-test`, which includes `BuilderSurface.test.tsx` without depending on an untracked target path.

## 2. Minimal UI implementation

In `BuilderSurface.tsx`, preserve existing `needsAction`, `runAction`, fail/accepted callbacks and `pendingConfirmationRef`. Add only local preview-open state; it is UX, never execution truth. Replace the raw action with `Retry this work`; first click opens preview; Confirm calls existing `runAction('requeue')`; Cancel closes it. Add no API/database/workflow state.

## 3. Durable progress mapping — RED first

Add tests that rerender authoritative packet snapshots and require:
- accepted + unchanged packet => waiting/accepted, never complete;
- queued => queued;
- claimed/running with no later evidence => running;
- latest attempt validation evidence and no review => validation;
- latest attempt review evidence while not done => review;
- done => complete;
- failed/blocked/cancelled => attention, never complete.

Implement a pure helper in `BuilderSurface.tsx` that derives the phase only from current `BuilderPacketStatus`. Local accepted state must never override durable failure.

## 4. Preserve working query truth boundary

Inspect `useBuilderAction()` in `queries.ts`. It already throws on `{ok:false}` and invalidates `['runtime-manifest']`. Do not rewrite it unless a new test exposes a real gap. Any edit must preserve those contracts.

## 5. Launched-app journey

Create `gateway/kitty-chat/tests/smoke/retry-work.spec.ts` using existing smoke fixtures and the real Next app. Stub deterministic Gateway facts only at the browser boundary; do not dispatch real provider work.

The test must navigate to **Work** and use the embedded Builder surface, not `Open full Builder`. Prove:
1. failed packet shows `Retry this work`, not raw `requeue`;
2. first click preview sends zero `/proxy/builder/action` requests;
3. Cancel sends zero;
4. Confirm sends exactly one POST for requeue + selected initiative/packet;
5. `{ok:false}` is visible failure;
6. `{ok:true}` is accepted/waiting, not complete;
7. runtime manifests advance queued → running → validation → review → done and UI follows;
8. unchanged manifest after accepted never claims completion.

During implementation run this new spec directly for RED/GREEN. The immutable runtime validation gate is the repo-supported `make smoke-test`, which runs the complete launched Playwright suite including `retry-work.spec.ts`.

## 6. Exact deterministic validation

The Builder packet validation commands are exactly:

```text
make ui-test
KITTY_KPROOF_RUNTIME=1 make smoke-test
```

`make ui-test` executes the full Vitest suite and therefore the new/updated `BuilderSurface.test.tsx`. The runtime-marked `make smoke-test` executes the launched Playwright suite and therefore the new `tests/smoke/retry-work.spec.ts`. These repo-root gates avoid referencing a not-yet-created path during Mission authoring while remaining strictly deterministic.

Review the diff and reject it if it edits outside the four paths, mutates before confirmation, treats mutation success as completion, derives completion from local state, weakens `{ok:false}`/manifest refresh, routes through the old inspector, or adds backend/orchestration/provider work.

## Acceptance

- `Retry this work` contextual primary action.
- Approval preview before mutation.
- Cancel mutation-free; Confirm exactly one existing requeue action.
- Existing fail-loud and authoritative refresh preserved.
- Accepted response alone never complete.
- Durable facts drive queued/running/validation/review/complete and failure returns to attention.
- Component test green as part of `make ui-test`.
- Runtime Playwright journey green as part of runtime-marked `make smoke-test`.
- No path outside the four-file contract changes.
