# Active Mission — Kitty-Wide Frontend + Product-Experience Harvest

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "KFX-001",
  "status": "running",
  "approved_at": "2026-07-20T00:00:00Z",
  "approved_by": "Jacob",
  "base_sha": "082a2e8b3d08ea87a1f4f0d6d150e4e0b8db5739",
  "authority": "docs/ACTIVE_MISSION.md"
}
-->

## Objective

Define one coherent Kitty-wide product experience through a comprehensive
frontend audit of all Kitty surfaces, all feature-adjacent repositories, and
all discovered frontend references. Produce a product-experience plan, code-
harvest register, and bounded KX initiative manifests.

This is NOT an Image-Lab-only audit and NOT a backend architecture audit.
It is a frontend and product-experience harvest covering every product lane.

## Product decision

- Kitty must feel like one product, not nine panels wearing the same CSS variables.
- Every feature lane (chat, image, tutor, memory, builder, automations,
  integrations, evaluation) must go through the same quality process.
- The standard is not "is the feature wired" — it's "does the product feel
  coherent."

## Scope

1. Reconcile repository continuity state, integrate completed image branch.
2. Inventory every Kitty product surface with live inspection.
3. Revisit all feature-adjacent repositories from a frontend perspective.
4. Discover additional mature frontend references.
5. Create a code-harvest register with license disposition.
6. Define one Kitty-wide product experience system.
7. Render a cross-product spike with fixture data.
8. Derive bounded, dependency-aware KX initiative manifests.
9. Define experience acceptance gates.
10. Commit and open the design PR.

## Authority granted

- Read the repository, Builder state, Git history, and public GitHub state.
- Edit documentation and audit deliverables.
- Integrate the approved feat/image-packets-current branch.
- Repair HANDOFF.md and STATE.md with accurate continuity state.
- Create a planning branch, commit deliverables, and open a PR for Jacob's review.
- Run formatting, static checks, tests, and read-only doctors.

The mission does NOT authorize pushing to main, merging without review, starting
Builder KX initiatives, or mutating runtime code.

## Deliverables

- `docs/AUDIT_KITTY_FRONTEND_EXPERIENCE_HARVEST_2026-07-20.md`
- `docs/plans/KITTY_PRODUCT_EXPERIENCE_V1.md`
- Repaired `HANDOFF.md` and `STATE.md`
- Updated `ACTIVE_MISSION.md` (this file)
- PR for Jacob's review of the cross-product experience direction

## Acceptance contract

The mission is complete when:
1. Continuity checks pass (27/27).
2. Image branch is integrated and documented.
3. All Kitty surfaces are inventoried.
4. All feature-adjacent repos are inspected for frontend evidence.
5. Code-harvest register is complete with license disposition.
6. Product-experience plan covers all 10 required domains.
7. KX initiative program is derived with dependencies.
8. PR is open for Jacob's review.
9. The approval command for KX-01 is explicit and actionable.

## Evidence plan

- Continuity check output (27 PASS).
- Git log showing image branch integration + origin/main sync.
- Frontend source code inspection (page.tsx, all 36 components, globals.css).
- Existing audit docs cross-referenced.
- Screenshots and browser evidence for surface inventory (to be added in spike stage).
