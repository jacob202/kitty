# Outcome Contract — Builder Agent Operability

## Identity

- Task: implement the 2026-08-30 AI-agent reliability research recommendations for KittyBuilder
- Execution owner: `interactive`
- Branch/worktree: `feat/builder-agent-operability-20260830` / `.worktrees/builder-agent-operability-20260830`
- Initial base SHA: `af3f6323d47be79c7f4d890d60ba54a99282d70f`
- Integrated base SHA: `242c339660197c3174d1bb3cfe37248a649989ff`
- Independently reviewed implementation SHA: `b4a0b601b3b0d191665b456c0c6339cd565fb8a5`
- Published PR: `#704` (`feat/builder-agent-operability-20260830` -> `main`)
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
- Exact next verification action: none; PR #704 remains open and unmerged.

## Verifier report

| Criterion | Verdict | Evidence | Required repair |
|---|---|---|---|
| AC-1 | PASS | Independent reviewer reran `tests/test_builder_operability.py`: 8/8; CAS race, lost-response recovery, confirmed-dead RUNNING reconciliation, and unknown fail-closed cases passed. | none |
| AC-2 | PASS | Independent reviewer reran `tests/test_builder_contract.py`: 17/17; explicit graph/artifact/control validation passed. | none |
| AC-3 | PASS | Independent reviewer reran `tests/test_builder_paid_routing.py`: 19/19; handoff/harness/candidate fail-closed cases passed. | none |
| AC-4 | PASS | Independent reviewer reran `tests/test_compute_governor.py`: 47/47; additive migration and policy receipt checks passed. | none |
| AC-5 | PASS | Independent reviewer reran `tests/test_session_learning.py`: 26/26; matched eval and repeated-evidence promotion passed. | none |
| AC-6 | PASS | Reviewer reran combined focused suite: 117/117, `git diff --check` clean, and confirmed all forbidden overlapping files unchanged. Implementer also ran merged regression: 485 passed + 29 subtests, repo Ruff clean, focused mypy clean. | none |

## Final state

`verified and published as PR #704`


## Independent review receipt

- Reviewer trust boundary: separate detached worktree at the exact implementation SHA.
- Reviewer model/agent: `opencode/nemotron-3-ultra-free` / read-only `free-reviewer`.
- Verdict: **APPROVE**.
- Findings: **none**.
- Reviewer independently reran all 117 acceptance tests and checked the exact diff, forbidden-path boundary, SQLite/additive-state design, retry/recovery semantics, routing policy, and learning-store reuse.

## Publication receipt

- PR: `#704` — `builder: implement agent operability and durable execution primitives`.
- Coordination issue `#490` updated with exact head, verification counts, and PR reference.
- PR remains open and unmerged.
