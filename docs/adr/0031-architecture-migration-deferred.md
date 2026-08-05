# ADR 0031: Architecture Migration to Open Brain/Ringer/Open Engine Is Deferred

**Date:** 2026-08-05
**Status:** Accepted

## Context

The architecture migration analysis (2026-08-05) evaluated whether Kitty should
migrate its Builder execution infrastructure, memory storage, and worker
orchestration to three proposed emerging projects:

- **Open Brain**: Shared memory/knowledge infrastructure (vector store, fact
  graph, memory consolidation, signal store, knowledge ingestion).
- **Ringer**: Worker orchestration (worker lifecycle, task dispatch, worktree
  isolation, scheduling).
- **Open Engine**: Durable execution (task state machine, leases, attempts,
  evidence, branch/PR management, cost tracking).

The analysis found that these projects would absorb approximately 60% of
Kitty's current infrastructure code (~11,400 lines), while preserving all
product features. Every current infrastructure concern maps to exactly one
of the three projects with no duplicated responsibility.

However, the analysis explicitly notes: "Open Brain / Ringer / Open Engine:
Assumed emerging projects. Exact API surfaces, schema, and maturity are
UNKNOWN."

The foundation replacement study (2026-07-27), KittyBuilder architecture
correction (2026-07-28), and the architecture honesty audit (2026-07-24) all
reinforce that migrating to unproven external infrastructure risks regressing
working systems.

## Decision

1. **The architecture migration analysis is accepted as a structural target.**
   The responsibility map (Open Brain = memory, Ringer = worker orchestration,
   Open Engine = durable execution, Kitty = product intelligence) is the
   correct architectural decomposition regardless of which implementations
   fill each role.

2. **Migration to Open Brain, Ringer, or Open Engine is deferred until each
   project demonstrates:**
   - Stable API surface with documented contracts.
   - Proven maturity (not alpha/pre-release).
   - Compatibility with Kitty's local-first, single-user, Apple Silicon
     operating environment.
   - Clear license terms compatible with Kitty's use.

3. **Kitty improves independently during the deferral.** The repository
   simplification (ADR 0030) consolidates stores and refactors modules in ways
   that make future migration lower-risk but provide immediate value.

4. **KittyBuilder is not replaced.** The architecture correction (2026-07-28)
   and core runtime audit (2026-08-01) established that KittyBuilder's 1000+
   passing tests, proven crash/stale-lease/budget-exhaustion recovery, and
   Git-specific semantics (worktree isolation, cumulative review from base SHA,
   operator grant-attempt) are not matched by any existing framework. Temporal,
   Prefect, Hatchet, and Dagster migration was explicitly rejected.

## Alternatives considered

**Begin migration immediately:** Rejected. The projects are assumed to exist
but their maturity is unknown. Migrating to vapor would regress working
infrastructure. The migration analysis itself recommends parallel evaluation
before any production switch.

**Reject the decomposition entirely:** Rejected. The three-part separation of
concerns (memory, worker orchestration, durable execution) is architecturally
correct regardless of whether Open Brain/Ringer/Open Engine implement each role
or Kitty retains custom implementations. The map is valuable for code
organization today.

**Adopt Temporal/Hatchet/Prefect instead:** Rejected by the architecture
correction (2026-07-28). These are distributed workflow engines, not
single-machine coding execution with Git semantics. KittyBuilder's
SQLite-backed state machine is purpose-built for Kitty's operating scale.

## Evidence

- Architecture migration analysis (2026-08-05): Full responsibility map,
  dependency diagrams, phase-by-phase migration plan, risk catalog, and
  line-count estimates.
- KittyBuilder architecture correction (2026-07-28): Rejected Prefect, Temporal,
  Hatchet, Dagster, LangGraph as replacements. Reassigned OpenCode plugins to
  workstation lane.
- KittyBuilder core runtime audit (2026-08-01): 1000+ passing tests. Proven
  crash recovery, stale lease handling, budget exhaustion with operator grant,
  operator completion flow, cancellation, worktree removal. One defect found
  and fixed (worker self-crash retry deadlock).
- Foundation replacement study (2026-07-27): Established the boundary between
  commodity shells and Kitty-owned intelligence.

## Consequences

- **Positive:** Architecture direction is clear. Code organization improves
  today. No migration risk while external projects are unproven.
- **Negative:** Kitty bears maintenance burden for infrastructure that
  commodity software may eventually provide (~11,400 lines). This is the cost
  of not speculating on vapor.
- **Open question:** Whether any of the three projects reach maturity before
  Kitty's simplification efforts make migration unnecessary (because the
  simplified infrastructure is trivial to maintain).

## Risks

- Open Brain, Ringer, or Open Engine never materialize: No impact. Kitty's
  infrastructure works independently. The migration analysis still serves as a
  code organization guide.
- Kitty's infrastructure becomes harder to maintain while waiting: Mitigated by
  ADR 0030's independent simplification targets.

## Follow-up work

- Evaluate Open Brain API maturity annually or when a stable release is
  announced.
- Evaluate Ringer worker lifecycle compatibility with Builder's
  worktree/Git-specific semantics.
- Evaluate Open Engine's ability to model initiatives (ordered packet
  collections with dependencies) — identified as a novel pattern in the
  migration analysis.
- Refactor Builder modules along the analysis's responsibility map internally:
  separate generic execution infrastructure from Kitty-specific product logic.

## Related ADRs

- ADR 0017: Kitty → Mission → KittyBuilder control plane
- ADR 0021: Proactive Builder execution and model policy
- ADR 0028: Commodity software precedence
- ADR 0030: Repository simplification is a strategic priority
