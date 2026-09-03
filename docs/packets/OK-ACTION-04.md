# OK-ACTION-04 — Work/Projects Grammar Proof

## Mission

Migrate one non-Home surface (Projects or Work) to the shared action grammar from `OK-ACTION-02`, proving the grammar is genuinely reusable outside the surface it was designed next to.

## Depends on

`OK-ACTION-01` and `OK-ACTION-02` complete and merged. This packet may run in parallel with `OK-ACTION-03`.

## Product acceptance moment

The same Project/Work object rendered in the migrated surface and in Home (or Chat) presents the same product-facing type/title, the same canonical destination, and the same available primary action — and an action taken in the migrated surface executes through the same owning authority with the same truthful lifecycle.

## Constraints

- Pick exactly one surface: the Projects view or the Work view. Do not migrate both, and do not touch Home (`OK-ACTION-03` owns Home).
- Existing authorities remain authoritative. Builder state (initiatives, packets, leases, attempts, reviews) keeps its owning execution path and its approval boundaries; this packet changes presentation and dispatch seams only.
- No new stores, projections, or backend endpoints.
- Navigation actions open the canonical destination from `OK-ACTION-01`; mutation actions keep approval distinct from execution; failure/unknown stays truthful.
- Preserve current keyboard/touch behavior and the phone layout contract of the chosen surface.

## Target locations

- `gateway/kitty-chat/src/components/ProjectsPanel.tsx` and/or the Work view components
- `gateway/kitty-chat/src/components/actions/` (shared renderer from `OK-ACTION-02`)
- Surface-local action wiring removed only where the shared renderer replaces it

Names may change to fit current conventions.

## Behavior

- Object rows/cards render identity, truthful status, and actions through the shared renderer.
- The proof domains from `OK-ACTION-01/02` must appear in the migrated surface with zero domain-specific button wiring.
- Disabled/unavailable actions explain why when non-obvious; loading never resizes the surrounding layout.
- Ask Kitty produces a structured handoff/reference to Chat rather than copying opaque IDs into prose.

## Tests

Prove:
- canonical navigation dispatch from the migrated surface;
- mutation dispatch goes to the owning authority with approval/execution kept distinct;
- rendering parity with Home for the same underlying object (identity, title, status, primary action);
- keyboard invocation works;
- the chosen surface keeps its existing layout contract at desktop and phone viewports.

## Non-goals

- Home migration (`OK-ACTION-03`).
- Chat surface changes.
- Action discovery/palette.
- Any change to Builder execution, lease, or approval mechanics.

## Done when

Dropping the shared renderer into a third surface requires no domain-specific button wiring, demonstrated by the migrated surface plus the Home proof.
