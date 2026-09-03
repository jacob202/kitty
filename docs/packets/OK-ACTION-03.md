# OK-ACTION-03 — Home as Action Board

## Mission

Migrate Home's actionable items to the shared action grammar from `OK-ACTION-01/02`, so Home stops being a collection of equal-weight informational sections and becomes a prioritized control surface for the user's day.

## Depends on

`OK-ACTION-01` and `OK-ACTION-02` complete and merged. This packet may run in parallel with `OK-ACTION-04`.

## Product acceptance moment

Open Home and immediately see: one best continuation, two things needing attention, one upcoming deadline, and meaningful running work. Every primary control either completes an action, starts a real workflow, or opens the canonical destination. The same object rendered in Chat or Work uses the same action treatment.

## Constraints

- Default section order: 1. Continue 2. Needs you 3. Today / Upcoming 4. Active 5. Kitty noticed. Everything else is subordinate or disclosed.
- Reuse existing next-step, deadline, approval, activity, project, and insight projections. Do not create new stores or projections.
- Do not steal: a generic analytics/dashboard pattern. Home is not an operator console and is not a wall of metrics.
- Render actions through the shared renderer/executor (`OK-ACTION-02`). No surface-local action wiring for grammar domains.
- Remove equal-weight card sections only when their content is represented by a section above or disclosed behind one; deleting information without a destination is not simplification.
- Degraded states stay truthful: a projection that cannot load shows its error/recovery affordance, never a fabricated empty success.
- Preserve current phone rules: 44px minimum touch targets on persistent controls, no horizontal overflow.

## Target locations

- `gateway/kitty-chat/src/state/HomeState.tsx`
- `gateway/kitty-chat/src/components/home/HomeView.tsx` and section components
- `gateway/kitty-chat/src/components/actions/` (shared renderer from `OK-ACTION-02`)
- `gateway/kitty-chat/src/lib/queries.ts` (composition only; no new fetch shapes)

Names may change to fit current conventions.

## Behavior

- Each first-screen card answers why-is-this-here: source label, truthful status, one primary action maximum in compact contexts.
- Continue renders the single best next step from the existing next-step projection; Needs you renders approvals/deadlines that require Jacob, each preserving exact meaningful arguments before approval.
- Kitty noticed keeps its existing intelligence projection semantics (including returned-once insight consumption); it composes last and must not promote itself above Needs you.
- Navigation opens the canonical destination; mutation actions dispatch to the owning authority via the shared executor; approval and execution lifecycle remain distinct states.
- Ask Kitty produces a structured handoff/reference to Chat rather than copying opaque IDs into prose.

## Tests

Prove:
- section composition order matches the default order;
- every primary action renders through the shared renderer and dispatches to the owning authority;
- no decorative buttons: each rendered action has a real dispatch path asserted in tests;
- degraded/unavailable projections render recovery affordances, not empty success;
- keyboard invocation and touch targets survive the migration;
- no horizontal overflow at the phone viewport.

## Non-goals

- Chat surface changes (`OK-CHAT-03/04` own that).
- New backend authorities, projections, or stores.
- Cross-product redesign beyond Home composition.

## Done when

Every first-screen Home card justifies its space with a working next step, and Home needs no domain-specific button wiring for the grammar's proven domains.
