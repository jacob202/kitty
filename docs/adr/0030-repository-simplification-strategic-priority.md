# ADR 0030: Repository Simplification Is a Strategic Priority

**Date:** 2026-08-05
**Status:** Accepted

## Context

The repository simplification audit (2026-08-05) inventoried the entire Kitty
codebase and found:

- 55,574 lines of gateway Python across 137 top-level modules.
- 54,829 lines of test code across 244 test files.
- 43 dead files (proven zero importers or references) removed in commit
  `4c0bf06b`.
- 9 memory stores accessed through `memory_graph` — complex enough that the
  architecture honesty audit (2026-07-24) called it "the most architecturally
  sophisticated subsystem" but also "heavy for local-first."
- 8 subsystem-owned SQLite databases (per ADR 0001).
- 27 Builder modules in a single namespace with `builder_adapters.py` as an
  unnecessary wiring layer.
- 251 documentation files, 139 of which are already archived.
- 9 stale git worktrees in `.claude/worktrees/`.
- Multiple shell scripts superseded by the `./kitty` launcher but never deleted.

The architecture migration analysis (2026-08-05) estimated that Kitty's unique
product value is approximately 40% of the current codebase, with the remaining
60% being infrastructure that commodity software could provide.

## Decision

Repository simplification is a strategic priority, not a one-time cleanup. The
operating rule is:

> Remove dead code immediately upon proof of disuse. Consolidate when the
> current structure actively impedes understanding or maintenance. Never preserve
> code merely because it shipped.

Three simplification targets are ratified as architectural direction:

1. **9 memory stores → 3**: SQLite (structured state), single vector store
   (embeddings, knowledge), JSONL (capture/log). Remove mem0 and ChromaDB
   dependencies in favor of a single embedding backend. This reduces the
   storage surface by two-thirds.

2. **Builder module consolidation**: 27 modules → internal refactor to
   separate generic execution infrastructure (task state machine, leases,
   worker lifecycle) from Kitty-specific product logic (contracts, scope,
   reporting, ISC). Remove `builder_adapters.py` as unnecessary wiring.

3. **8 subsystem SQLite DBs → 1-3 consolidated DBs**: Each module managing
   its own SQLite connection (ADR 0001) created scattered schemas and
   connection pooling. Consolidate into the main Kitty database with clear
   table ownership.

These targets are independent — each can ship without waiting for the others.

## Alternatives considered

**Leave the codebase as-is, prioritize features:** Rejected. Dead code and
scattered stores create drag on every change. The open-session audit
(2026-08-01) documented multiple orphaned branches with substantial unlanded
work — complexity creates coordination failures.

**Full rewrite into a new architecture:** Rejected. The Product Architecture
explicitly rejected Approach C (new event-sourced core) for high migration
risk and delay before user value. The existing subsystems work; simplification
makes them work better.

**Wait for Open Brain/Ringer/Open Engine before simplifying:** Rejected.
Open Brain, Ringer, and Open Engine are emerging projects with UNKNOWN maturity.
Kitty's simplification is independently valuable; it also makes future migration
to these projects lower-risk if they mature.

## Evidence

- Repository simplification audit (2026-08-05): Complete inventory, dead code
  graph, dependency graph. 43 dead files proven with rg import tracing.
- Architecture migration analysis (2026-08-05): Line-count estimates and
  responsibility maps for Open Brain/Ringer/Open Engine migration.
- Architecture honesty audit (2026-07-24): Identified 9 memory stores, 8
  subsystem DBs, 27 Builder modules.
- Open-session audit (2026-08-01): Documented orphaned branches with
  substantial unlanded work.
- Commit `4c0bf06b`: First simplification pass — 43 dead files removed with
  verified zero breakage.

## Consequences

- **Positive:** Simpler codebase. Faster onboarding for new contributors.
  Lower risk of introducing bugs through dead code paths. Clearer module
  boundaries.
- **Negative:** Migration risk when consolidating stores. Requires
  additive migrations, shadow reads, and per-phase rollback — not a big-bang
  migration.
- **Open question:** Whether to adopt SQLite-vec for embeddings or retain a
  separate vector store. The principle (one store, not nine) is decided; the
  implementation (which single store) is not.

## Risks

- Consolidation introduces data migration bugs: Mitigated by additive
  migrations, preserved originals, shadow reads, and per-phase rollback
  (Product Architecture §17).
- Removal of a module that appeared dead but was reachable through dynamic
  dispatch: Mitigated by requiring zero-importers proof + test suite pass
  before removal. Files recoverable via git history.

## Follow-up work

- Memory store consolidation (3-4 weeks): SQLite + single vector store + JSONL.
- Builder module refactor (2-3 weeks): Separate generic execution from
  product logic.
- Subsystem DB consolidation (3-4 weeks): 8 DBs → main kitty.db.
- Documentation archival pass: Move historical docs to `docs/archive/`.
- Prune stale worktrees in `.claude/worktrees/`.

## Related ADRs

- ADR 0001: DB Scope (established 8 subsystem SQLite DBs — this ADR
  supersedes the per-module connection pattern)
- ADR 0004: memory_graph owns context reads
- ADR 0028: Commodity software precedence
