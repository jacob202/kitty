# OK-CONTINUITY-01 — Cross-Surface Object Continuity

## Mission

Prove that one Kitty-owned object can move through multiple product surfaces without losing identity, status truth, ownership, or result relationships.

## Depends on

- accepted/integrated WOW stack;
- `OK-ACTION-01` canonical object/action contract;
- `OK-ACTION-02` shared action execution/rendering;
- relevant Artifact/Activity/Project/Chat foundations.

## Product acceptance scenario

Use one concrete end-to-end workflow, ideally Builder -> Artifact -> Project -> Chat:

1. Start or open a real Work/Builder item.
2. Observe it in Work and, when relevant, Home/Activity.
3. Complete it or use an already completed fixture with a canonical produced result.
4. Open the produced Artifact through the object's result relationship.
5. Attach/associate the Artifact to a Project through existing authority.
6. Ask Chat about the Project/Artifact using canonical context reference.
7. Chat can identify the same underlying objects and offer real actions back to their canonical destinations.

No step may require copying an opaque internal ID into another surface.

## Continuity contract

For every object crossing surfaces preserve:
- canonical type/id;
- product-facing title;
- owner/authority;
- canonical destination;
- current truth state;
- parent/project relationship where authoritative;
- produced/result relationships;
- action availability derived from current state.

Do not force unrelated domain metadata into one generic schema.

## Key failure cases to cover

### Result exists but secondary registration fails
The user must not lose recoverability of a generated/produced result merely because Artifact registration or a downstream projection fails.

### Source unavailable
A surface must not turn `could not read source` into `object does not exist`.

### Stale projection
Refetch/reconciliation must converge to the owning authority. Do not let a Home/Chat cached projection become authoritative.

### Object renamed/updated
References should continue using stable canonical identity while displaying current product-facing fields after refresh.

### Action changes after state transition
An action offered while `waiting_for_user` must disappear/change when the object moves to `running`/`succeeded`/etc.

## Implementation approach

Do not create a new universal-object database.

Prefer:
- reference adapters;
- explicit result/relationship fields in existing projections where missing;
- canonical navigation helpers;
- query invalidation/reconciliation;
- shared object/action rendering.

## Tests

Add one cross-surface integration/acceptance fixture that exercises the full chain. Unit tests alone are insufficient.

Prove:
- identity survives across four surfaces;
- result link resolves to the canonical Artifact/object;
- project association is visible from both Project and referenced object where intended;
- stale status reconciles;
- failed source is distinguishable from missing object;
- no copy/paste ID step exists in the running product flow.

## Non-goals

- Universal graph database.
- Global event-sourcing rewrite.
- Replacing domain authorities.
- Cross-surface support for every object type in the first packet.

## Done when

One real workflow demonstrates that Kitty behaves like one product rather than a collection of disconnected pages.
