# Work Surface Convergence — Design

Date: 2026-08-20
Status: Approved in chat; implementation pending
Parent: ADR 0039 / `feat/product-surface-convergence-20260817`
Branch: `feat/work-surface-convergence-20260820`

## Problem

Kitty currently exposes two overlapping user-facing views of Builder execution:

- `WorkView`, backed by the Gateway-owned `/work` projection of durable Builder state.
- `BuilderSurface` / `BuilderCockpit`, reached from Home and other Builder-oriented links.

This splits product ownership. A user can enter two different execution UIs that describe related state at different levels, while ADR 0039 calls for one coherent Kitty surface with progressive disclosure.

The current Work rows also lead with implementation details such as packet and run identifiers instead of the questions a user normally has: what needs me, what is happening, what finished, and what can I inspect as proof?

## Decision

`Work` becomes Kitty's canonical normal-user execution surface.

Normal navigation must converge on Work. Existing deep Builder diagnostics may remain temporarily available as an internal/advanced implementation surface, but they are not a peer product destination and must not be the path Home or ordinary navigation sends users into.

## User-facing information hierarchy

Work presents durable Gateway projection truth in three primary groups:

1. **Needs you** — blocked, failed, paused, or approval-dependent work where the user can materially unblock progress.
2. **In progress** — active, ready, or waiting work that does not currently require user intervention.
3. **Completed** — recently completed work and its result/evidence summary.

Within each item, the default visible hierarchy is:

- title
- plain-language state
- blocker or next action when relevant
- result/evidence summary when available
- freshness/source warning when truth is degraded or stale

Packet IDs, run IDs, task IDs, raw evidence payloads, and other implementation detail remain inspectable through progressive disclosure rather than occupying the primary row.

## Navigation convergence

- Home's Builder glance opens `work`.
- Normal `builder` navigation resolves to `work`.
- Rail and mobile navigation continue to expose Work as the execution destination.
- No new top-level navigation item is added.
- Deep Builder cockpit code is not deleted in this slice; deletion/retirement requires separate evidence that no diagnostic workflow still depends on it.

## Data ownership and flow

Builder durable records remain source truth.

`Builder state -> Gateway build_status_snapshot -> Gateway project_work_snapshot -> GET /work -> frontend useWorkSnapshot -> WorkView`

The frontend does not invent a second execution state machine. Refresh/reload must reconstruct the visible Work state from `/work`.

This slice should prefer presentation changes over widening the projection contract. If existing projection fields are insufficient for a useful result/evidence summary, add only the smallest deterministic projection field derived from existing Builder truth and cover it at the Gateway boundary.

## Error and stale-state behavior

- `/work` unavailable: keep the current explicit unavailable state and retry action; do not silently fall back to a different Builder UI.
- stale snapshot: visibly mark stale data while preserving the last known projection.
- degraded source: preserve source-quality disclosure.
- missing optional evidence/result: omit the absent detail rather than fabricating a summary.
- unknown state/invalid payload: fail closed through the existing frontend contract validation.

## Implementation scope

Expected frontend touch points:

- `gateway/kitty-chat/src/components/HomeState.tsx`
- `gateway/kitty-chat/src/components/ViewRenderer.tsx`
- `gateway/kitty-chat/src/lib/views.tsx`
- `gateway/kitty-chat/src/components/WorkView.tsx`
- focused Work/navigation tests

Possible backend touch points only if evidence proves they are required:

- `gateway/work_projection.py` and its focused projection helpers/tests

No Image Lab files are part of this slice.

## Testing strategy

Use test-first changes for each behavior:

1. Home Builder glance navigates to Work.
2. Ordinary `builder` navigation renders/resolves Work instead of the Builder cockpit.
3. Work groups items into Needs you / In progress / Completed using existing durable states.
4. Primary rows do not expose raw packet/run IDs by default.
5. Evidence/details remain available through progressive disclosure where present.
6. stale/degraded/unavailable states remain truthful.
7. reload/refetch behavior continues to use `/work`; no local execution truth is introduced.

Run the focused frontend Work/navigation tests first, then the full kitty-chat unit/build gate. Run focused Gateway projection tests if the projection contract changes.

## Non-goals

- Rewriting Builder execution or Builder's durable state model.
- Deleting Builder diagnostic components in the same change.
- Adding execution controls merely because the old cockpit had them.
- Building a new dashboard framework.
- Changing Image Lab.
- Expanding the Work projection with speculative telemetry.

## Success criteria

A user opening Kitty has one obvious place to answer:

- What needs me?
- What is Kitty doing?
- What finished?
- What happened / what is the proof?

Home and ordinary navigation agree on that destination. A browser reload reconstructs the same answer from Gateway/Builder truth, and deep implementation identifiers are available only when deliberately inspected.