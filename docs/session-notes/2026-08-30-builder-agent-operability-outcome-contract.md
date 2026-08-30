# Outcome Contract — Builder Agent Operability

## Identity

- Task: implement the 2026-08-30 AI-agent reliability research recommendations for KittyBuilder
- Execution owner: `interactive`
- Branch/worktree: `feat/builder-agent-operability-20260830` / `.worktrees/builder-agent-operability-20260830`
- Base SHA: `af3f6323d47be79c7f4d890d60ba54a99282d70f`
- Repair-cycle limit: `2`

## User-visible outcome

KittyBuilder has tested primitives for safe recovery of ambiguous side effects, explicit packet execution graphs, evidence-aware model handoffs/harness selection, matched capability evaluation, persistent distilled learning signals, and inspectable routing/spend policy receipts.

## Acceptance criteria

| ID | Observable criterion | Verification command or interaction | Required evidence |
|---|---|---|---|
| AC-1 | A side effect that commits and then loses its response is reconciled after restart without executing twice. | `python -m pytest tests/test_builder_operability.py -q` | Counter/effect remains exactly once; durable status becomes succeeded. |
| AC-2 | Contracts compile to explicit artifact/control-flow steps and reject broken dependencies/control transfers. | `python -m pytest tests/test_builder_contract.py -q` | New workflow-compiler cases pass. |
| AC-3 | Escalation/downshift handoffs and coding/research/review/recovery harness profiles are deterministic and paid route candidates remain fail-closed. | `python -m pytest tests/test_builder_paid_routing.py -q` | New handoff/harness/routing-plan cases pass. |
| AC-4 | Compute receipts preserve a JSON policy snapshot without weakening duplicate-work or budget controls. | `python -m pytest tests/test_compute_governor.py -q` | Migration/round-trip + existing governor tests pass. |
| AC-5 | Matched baseline/candidate evaluation produces measured lift, rejects mismatched tasks, and positive repeated evidence persists/promotes through the existing learning store. | `python -m pytest tests/test_session_learning.py -q` | Paired-eval and two-session promotion cases pass. |
| AC-6 | Existing focused Builder reliability suite remains green and diff is limited to approved seams. | `python -m pytest tests/test_builder_operability.py tests/test_builder_contract.py tests/test_builder_paid_routing.py tests/test_compute_governor.py tests/test_session_learning.py -q --tb=short` plus `git diff --check` | 0 failures; no forbidden paths. |

## Non-goals

- Retrofitting every existing side-effecting Builder command in this packet.
- Modifying Work UI or Builder supervisor semantics owned by PR #677.
- Modifying `builder_attempt.py`, `builder_loop.py`, `builder_runner.py`, or their concurrent retry tests.
- Adding or spending on a provider.

## Prohibited shortcuts

- Unknown external outcome may not be treated as failure or success without verification.
- No retry of an `unknown` at-most-once/reconcilable effect without a postcondition verdict.
- No unmatched baseline/candidate comparison.
- No new learning store.
- No completion claim without fresh focused verification and independent review.

## Context that must survive compaction or handoff

- Approved requirements and decisions: `docs/superpowers/specs/2026-08-30-builder-agent-operability-design.md`
- Current implementation state: this branch only
- Forbidden overlapping files: `gateway/builder_attempt.py`, `gateway/builder_loop.py`, `gateway/builder_runner.py`, `tests/test_builder_loop.py`, `tests/test_builder_runner.py`
- Baseline: 87/87 relevant tests passed before implementation; unrelated builder-publish process-group test is sandbox-blocked.
- Exact next verification action: AC-1 red/green cycle.

## Verifier report

| Criterion | Verdict | Evidence | Required repair |
|---|---|---|---|
| AC-1 | UNVERIFIED | pending | pending |
| AC-2 | UNVERIFIED | pending | pending |
| AC-3 | UNVERIFIED | pending | pending |
| AC-4 | UNVERIFIED | pending | pending |
| AC-5 | UNVERIFIED | pending | pending |
| AC-6 | UNVERIFIED | pending | pending |

## Final state

`implemented, awaiting verification`
