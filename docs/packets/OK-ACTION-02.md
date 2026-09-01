# OK-ACTION-02 — Shared Action Renderer + Executor

## Mission

Render and execute canonical Kitty actions consistently across surfaces using the shared contract from `OK-ACTION-01`, while preserving each owning authority's real mutation path.

## Depends on

`OK-ACTION-01` complete and merged or available as the exact base for this packet.

## Product acceptance moment

A Project/Deadline/Work/Artifact object rendered in two different surfaces presents the same primary action treatment and the same execution lifecycle. If an action starts work, the UI visibly progresses through the truthful states instead of replacing the action with a premature success message.

## Constraints

- The renderer does not own business logic.
- Do not introduce a generic backend mutation endpoint unless existing authority routes genuinely cannot be dispatched safely.
- Existing approval boundaries remain intact.
- Exact arguments that matter to approval must remain inspectable before approval.
- A navigation action and a mutation action are distinct concepts.
- Optimistic UI is allowed only for safely reversible local state and must reconcile with backend truth.

## Target locations

Expected frontend area:

- `gateway/kitty-chat/src/components/actions/KittyActionBar.tsx`
- `gateway/kitty-chat/src/components/actions/KittyActionButton.tsx`
- `gateway/kitty-chat/src/components/actions/useKittyAction.ts`
- `gateway/kitty-chat/src/lib/gateway.ts`
- `gateway/kitty-chat/src/lib/queries.ts`

Use existing shared Button/Dialog/Sheet primitives rather than inventing parallel controls.

Names may change to fit current conventions.

## Behavior

The renderer must support at least:

### Navigation
Examples: `Open project`, `Open work`, `Open artifact`.

- deterministic canonical destination;
- keyboard/touch accessible;
- no fake loading state for pure client navigation;
- preserve relevant project/object selection when current architecture supports it.

### Immediate safe mutation
Only where the existing authority already defines a safe direct mutation.

- pressed/loading state immediately visible;
- backend response/refetch controls final state;
- errors preserve context and show recovery.

### Approval-required mutation
Examples may include action execution or consequential operations.

- show what is being approved;
- preserve exact meaningful arguments;
- approval is not success;
- after approval, show execution lifecycle separately;
- failure/unknown stays truthful.

### Ask Kitty
Produce a structured handoff/reference to Chat rather than copying opaque IDs into prose.

If the shared object-reference-to-chat mechanism does not yet exist, implement the smallest seam needed and leave full concierge context to `OK-CHAT-01/02`.

## Visual grammar

- one primary action maximum in compact card contexts unless domain UX proves otherwise;
- secondary actions visually quieter;
- destructive treatment reserved for destructive effects;
- disabled/unavailable actions explain why when non-obvious;
- loading does not resize the surrounding layout;
- 44px minimum touch target on persistent phone controls;
- status color never carries meaning alone.

## Proof integration

Use the two domains implemented by `OK-ACTION-01` and render them through the shared action component in at least two different contexts/components.

Avoid broad Home migration here; `OK-ACTION-03` owns that.

## Tests

Prove:
- canonical navigation dispatch;
- mutation dispatch goes to the owning authority;
- approval and execution remain distinct;
- pending state is visible and stable;
- failed/unknown outcome is not rendered as success;
- disabled action is inaccessible and has explanatory copy where expected;
- keyboard invocation works;
- touch target/layout contract is preserved where component tests support it.

## Non-goals

- Action discovery/palette.
- Full Chat concierge.
- Cross-product redesign.
- New backend action authority.

## Done when

The shared renderer can be dropped into Home or Chat without those surfaces needing domain-specific button wiring for the proof domains.
