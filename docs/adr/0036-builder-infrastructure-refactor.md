# ADR 0036: Builder Infrastructure Preserved — Refactored for Extraction Readiness

**Date:** 2026-08-05
**Status:** Accepted

## Context

The KittyBuilder architecture correction (2026-07-28), core runtime audit
(2026-08-01), and architecture migration analysis (2026-08-05) converged on
the same conclusion: KittyBuilder's infrastructure is working, tested, and
product-specific, but it mixes generic execution concerns with Kitty-specific
product logic.

The 27 Builder modules at `gateway/builder_*.py` include:
- Generic execution infrastructure: task state machine, lease management,
  attempt tracking, audit trail, worker lifecycle, worktree isolation.
- Kitty-specific product logic: contract format, scope enforcement, ISC
  checking, reporting, operator commands, CLI, brief conventions.
- Unnecessary wiring: `builder_adapters.py` — an adapter layer that exists
  only because the modules grew without internal boundaries.

The architecture migration analysis (2026-08-05) proposed that Open Engine
would absorb the generic execution infrastructure and Ringer would absorb
worker orchestration. Whether those projects mature or not, the internal
separation is independently valuable.

## Decision

1. **Builder infrastructure is preserved.** No migration to external workflow
   engines (Prefect, Temporal, Hatchet, Dagster) is planned. The core runtime
   audit proved KittyBuilder's recovery semantics are production-quality:
   crash recovery (worker self-crash + dead supervisor), stale lease handling,
   budget exhaustion with operator grant, operator completion flow,
   cancellation, worktree removal with dirty-tree refusal.

2. **Builder modules are refactored internally** along the responsibility map
   from the migration analysis:
   - **Execution infrastructure** (candidate for future extraction): task
     state machine, leases, attempts, events, runtime, worker session,
     runner, loop.
   - **Product logic** (permanently Kitty): contract format, scope, ISC,
     reporting, operator commands, CLI, brief conventions.
   - **Remove** `builder_adapters.py` as unnecessary wiring.

3. **`gateway/builder/` subpackage is the target location** for execution
   infrastructure modules. The directory currently contains only `__pycache__`
   — a placeholder for this refactor.

4. **The CLI surface (`builder_cli.py`, `builder_commands.py`) remains
   unchanged** during refactoring. Operator commands are the stable interface.

## Alternatives considered

**Migrate to Temporal/Hatchet/Prefect:** Rejected per the architecture
correction (2026-07-28). These are distributed workflow engines for
multi-node systems. Kitty runs on a single Mac. KittyBuilder's SQLite-backed
queue with Git-specific semantics (worktree isolation, cumulative review
from base SHA, branch leases) is purpose-built and tested.

**Leave 27 modules as-is:** Rejected. The flat namespace makes it impossible
to distinguish generic infrastructure from product logic. `builder_adapters.py`
is pure indirection. The migration analysis provides a clear decomposition.

**Wait for Open Engine/Ringer before refactoring:** Rejected. The internal
separation is valuable today for code organization. It also makes migration
lower-risk if those projects mature.

## Evidence

- KittyBuilder core runtime audit (2026-08-01): 10 scenarios, 1 defect found
  and fixed. 1000+ passing tests. Proven: crash recovery (S4a, S4b), stale
  lease requeue (S5), budget exhaustion + operator grant (S6, S7), operator
  completion (S8), status/doctor agreement (S9), cancellation + worktree
  removal (S10).
- Architecture migration analysis (2026-08-05): Responsibility map with
  per-module classification (KEEP, MERGE, DELETE). Builder modules classified
  into execution infrastructure (MERGE) and product logic (KEEP).
- KittyBuilder architecture correction (2026-07-28): Exhaustive build-vs-buy
  decision table. Rejected Prefect, Temporal, Hatchet, Dagster, LangGraph.
  Accepted Hatchet/Temporal as pattern sources only.
- Repository simplification audit (2026-08-05): Identified 27 Builder modules
  with `builder_adapters.py` as unnecessary wiring.

## Consequences

- **Positive:** Clear internal boundaries. Generic execution code separated
  from product logic. Easier to understand, test, and potentially extract.
- **Negative:** Module moves require import path updates. Test files need
  corresponding reorganization. CI must verify no regressions.
- **Open question:** Whether `gateway/builder/` becomes a true subpackage
  with its own `__init__.py` or a flat directory of modules referenced by
  explicit imports. The target is a subpackage to enable future extraction.

## Risks

- Refactoring breaks subtle import dependencies: Mitigated by running the
  full 1000+ test Builder suite before and after each move. The `builder_cli.py`
  surface is the integration test boundary.

## Follow-up work

- Create `gateway/builder/__init__.py`.
- Move execution infrastructure modules: `builder_queue_db.py`,
  `builder_queue.py`, `builder_queue_leases.py`, `builder_queue_runs.py`,
  `builder_queue_branch_leases.py`, `builder_attempt.py`, `builder_events.py`,
  `builder_runtime.py`, `builder_worker_session.py`, `builder_runner.py`,
  `builder_loop.py`, `builder_publish.py`, `builder_identity.py`.
- Keep product logic at top level: `builder_contract.py`, `builder_scope.py`,
  `builder_isc.py`, `builder_report.py`, `builder_brief.py`,
  `builder_initiative.py`, `builder_doctor.py`, `builder_status.py`,
  `builder_cli.py`, `builder_commands.py`.
- Delete `builder_adapters.py`.
- Update all imports. Run full Builder test suite.

## Related ADRs

- ADR 0017: Kitty → Mission → KittyBuilder control plane
- ADR 0021: Proactive Builder execution and model policy
- ADR 0030: Repository simplification is a strategic priority
- ADR 0031: Architecture migration deferred
