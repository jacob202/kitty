# Kitty Deletion + Convergence Candidate Ledger

Status: PROVISIONAL. This is not an implementation backlog and must not outrank the sequential audit.

Purpose: preserve already-observed simplification opportunities so Chunk 9/10 can prove or disprove them instead of rediscovering them.

Decision preference: DELETE > SIMPLIFY > CONSOLIDATE > FIX > OPTIMIZE > REWRITE.

Every candidate must end as one of:
- CONFIRMED DELETE
- CONSOLIDATE
- KEEP ACTIVE
- COMPATIBILITY SHIM
- DEFER
- DISPROVEN
- IN FLIGHT ELSEWHERE

## CAND-001 — Legacy Gateway task execution surface

Observed evidence before final audit reconciliation:
- `gateway/task_runner.py` remained reachable.
- Gateway task routes called it directly.
- native frontend task queries/components still consumed it.
- Work/Builder exists as a separate durable execution authority.

Potential benefit: remove duplicate execution/state concepts and stop UI from mixing incompatible notions of task/work.

Do not act until Chunk 1/3/7 prove current reachability, migration path, and whether active PRs already converge it.

## CAND-002 — `ImageStudio.tsx`

Observed evidence: large older frontend component appeared to have no active import while `ImageLab.tsx` was the canonical Studio path.

Classification today: LIKELY DEAD, NOT CONFIRMED DEAD.

Do not touch while Image Lab lane is active. Chunk 5/7 must check dynamic imports, routes, tests, history and active work first.
## CAND-003 — OpenWebUI product-authority residue

Observed evidence:
- accepted native-product ADR says Kitty native frontend is canonical;
- older README/Constitution/Architecture/Status/Roadmap language still described OpenWebUI as daily-driver or unresolved authority.

Potential action: reconcile authority docs and retire obsolete product assumptions, not necessarily remove OpenWebUI code.

Chunk 0/7/9 must determine exact current authority hierarchy and whether newer commits already resolved it.

## CAND-004 — Scheduler/background-loop duplication

Observed historical/convergence evidence: cron, web monitor, brief scheduler, inbox watcher and Automation lifecycle have overlapped.

Potential action: converge lifecycle/ownership and delete redundant loop-specific persistence or scheduling logic.

Do not assume duplication remains. Chunk 6 must inventory current registrations, startup paths, persistence, and open work.

## CAND-005 — Dependency ownership cleanup

Previously observed root dependency candidates included packages with no obvious direct production import, plus integration-specific dependencies living at root.

Potential action: remove unused direct deps or move them to owning integration manifests.

Chunk 8 must prove actual imports, dynamic loading, extras, CI/install consumers and transitive needs before any removal.

## CAND-006 — Configuration-loading sprawl

Observed pattern: environment reads and dotenv loading occurred across many modules while only a smaller portion used centralized Settings.

Potential action: consolidate ownership of configuration without a giant rewrite.

This is a convergence candidate only; Chunk 1/2/8/9 must determine whether inconsistency causes real correctness/security/testability problems.
## CAND-007 — Legacy research wrapper

Observed evidence: `gateway/researcher.py` identified itself as a legacy technical-research wrapper being replaced by an engine-backed contract.

Potential action: remove or reduce the legacy path once the replacement is authoritative and all callers migrate.

Chunk 4/9 must verify current callers, issue/PR status, tests and any compatibility obligations.

## CAND-008 — HTTP/client creation duplication

Observed pattern: shared HTTP client exists, while some subsystems still use module-level or direct `httpx`/`requests` clients.

Potential action: consolidate only where it improves lifecycle, timeout, observability, or event-loop correctness.

Do not centralize merely for aesthetics; Chunk 1/4/8 must measure/verify actual failure or maintenance cost.

## CAND-009 — Frontend component size / dead-surface cleanup

Observed: several very large native components and no TypeScript dead-code gate comparable to Python vulture checks.

Potential action: delete genuinely unreachable components and split active components only where testability/change-risk improves.

Do not refactor large components solely because they are large.

## Candidate proof checklist

Before deleting/consolidating any candidate, prove:
1. canonical replacement exists and works;
2. all production callers are known;
3. dynamic/plugin/reflection paths are checked;
4. tests/CLI/scripts/config are checked;
5. open PR/issue ownership is checked;
6. migration/compatibility needs are explicit;
7. rollback is simple;
8. acceptance suite still passes.

No candidate becomes work until Chunk 10/11 explicitly promotes it.
