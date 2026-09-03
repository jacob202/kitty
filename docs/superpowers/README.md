# `docs/superpowers/` — skill-driven execution artifacts

This folder holds design specs and their task-by-task implementation plans,
produced and executed under the superpowers skill system. It is a **distinct,
protected lane** and is not moved or edited by general docs-consolidation work.

## Structure

- `specs/` — design specs. Dated design documents (ideate → options → chosen
  design) that precede and justify a plan.
- `plans/` — implementation plans. Each plan is executed task-by-task under a
  superpowers sub-skill — `subagent-driven-development` (recommended) or
  `executing-plans` — and tracks progress with checkbox (`- [ ]` / `- [x]`)
  steps.

## Live semantics

- **Spec → plan pairing.** A spec owns the design rationale; its sibling plan
  owns the ordered execution steps. A plan without a spec still cites its
  design source inline.
- **Execution is skill-gated, not file-gated.** A plan here is a recipe for a
  superpowers sub-skill, not an independent authority. Existing here does not
  activate work; activation follows the canonical roadmap and the sub-skill's
  own gates.
- **Protected lane.** These artifacts are referenced by gateway modules and
  superpowers skills and are excluded from general archival sweeps. Do not
  move, merge, or rewrite them as part of ordinary docs consolidation; update
  them in their own lane.

## Relationship to other plan-like surfaces

- [`../plans/`](../plans/README.md) — candidate implementation plans and inputs
  gated by the roadmap. These are roadmap-gated candidate plans, not
  skill-driven execution recipes; the two folders are intentionally separate.
- [`../PLANS.md`](../PLANS.md) — the navigation/disposition index for the
  `docs/plans/` surface; it does not index this folder.
- [`../archive/`](../archive/README.md) — historical material; superpowers
  specs/plans are not archived by general consolidation.
