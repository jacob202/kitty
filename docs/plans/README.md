# `docs/plans/` — candidate plans and implementation inputs

This folder holds candidate implementation plans and supporting design inputs.
It is **not** an authority surface: a file here does not authorize work merely by
existing, and it is not a roadmap.

## Live semantics

- **Supporting evidence, not authority.** Treat every file here as supporting
  evidence unless the canonical roadmap explicitly activates it (see
  [`../PLANS.md`](../PLANS.md) and [`../ROADMAP.md`](../ROADMAP.md)).
- **Activation is fail-closed.** A plan, packet, or initiative is inert by
  default. Priority and sequencing belong to [`../ROADMAP.md`](../ROADMAP.md)
  (ADR 0020); the current broad mission to [`../ACTIVE_MISSION.md`](../ACTIVE_MISSION.md).
  Durable architecture decisions live in [`../DECISIONS.md`](../DECISIONS.md) and
  [`../adr/`](../adr/) and override conflicting plan content.
- **Recency and old self-labels are not activation.** A plan cannot become current
  work by being newer, more detailed, or containing historical words such as
  "authorized," "active," "binding," or "ready." Current activation must be
  established from today's roadmap/mission/ownership evidence, not from a dated
  plan's own prose.
- **Superseded plans are archived.** When a plan describes an older repository
  state, it is superseded or moved to [`../archive/`](../archive/) rather than
  left marked "ready to implement."
- **Generated compatibility artifact:** `migration-health.md` remains at this
  legacy path because `scripts/migration-audit.sh` writes it. It is dated
  evidence, not a plan or activation source.

## Relationship to other plan-like surfaces

- [`../superpowers/`](../superpowers/README.md) — skill-driven execution
  artifacts (`specs/` design → `plans/` checkbox task-by-task implementation),
  a distinct protected lane. Not the same as this folder.
- [`../archive/`](../archive/README.md) — superseded plans, handoffs, and
  status snapshots; never current instruction.
- [`../PLANS.md`](../PLANS.md) — the navigation/disposition index that points
  readers to reviewed plans here and prevents older session plans from silently
  regaining authority.
