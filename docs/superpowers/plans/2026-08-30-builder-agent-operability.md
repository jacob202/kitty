# Builder Agent Operability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe ambiguous-effect recovery, explicit workflow compilation, evidence-aware handoffs/harnesses, paired capability evaluation, persistent learning signals, and routing-policy receipts while reusing Kitty's existing authorities.

**Architecture:** One new `builder_operability` module owns only durable operation receipts and recovery. Existing `builder_contract`, `builder_paid_routing`, `compute_governor`, and `session_learning` gain the other behaviors in their existing domains. No new queue, scheduler, routing registry, or learning store is introduced.

**Tech Stack:** Python 3.12, SQLite, dataclasses, pytest.

**Spec:** `docs/superpowers/specs/2026-08-30-builder-agent-operability-design.md`

## Global Constraints

- Initial base: fresh GitHub main `af3f6323d47be79c7f4d890d60ba54a99282d70f`; integrated with current `origin/main` `242c339660197c3174d1bb3cfe37248a649989ff` before final review.
- Do not touch active PR #677 Work/supervisor implementation.
- Do not touch the concurrent retry-base-fence files named in the outcome contract.
- No paid execution, secrets/env changes, merge, direct-main push, or heavy dependency.
- TDD: every production behavior starts with a failing focused test.

---

### Task 1: Durable operation receipts and ambiguous-effect recovery

**Files:**
- Create: `gateway/builder_operability.py`
- Modify: `gateway/builder_queue_db.py`
- Create: `tests/test_builder_operability.py`

**Interfaces:**
- Produces: `request_invocation(...)`, `get_invocation(...)`, `execute_invocation(...)`, `Verification`, `OutcomeUnknownError`, effect/status constants.
- Storage: additive `operation_receipts` table inside the existing Builder queue DB.

- [x] Write tests proving idempotency-key request conflicts fail, normal success is cached, and commit-then-response-loss is reconciled after reopening SQLite without a second effect.
- [x] Run `python -m pytest tests/test_builder_operability.py -q` and verify RED because module/table/API is absent.
- [x] Add the table and minimal implementation. `unknown` must invoke the verifier before any retry; verifier states are `applied`, `not_applied`, `unknown`.
- [x] Run the focused test and verify GREEN.
- [x] Commit `feat(builder): add durable operable invocation receipts`.

### Task 2: Compile contracts into explicit workflow graphs

**Files:**
- Modify: `gateway/builder_contract.py`
- Modify: `tests/test_builder_contract.py`

**Interfaces:**
- Produces: `compile_workflow(spec: dict[str, Any]) -> dict[str, Any]`.
- Step shape: `id`, `instruction`, `requires`, `produces`, `validation_commands`, `on_success`.

- [x] Write tests for legacy single-step compilation, multi-step artifact/control transfer, unknown successor, duplicate IDs, missing artifact producer, and cycles/unreachable steps.
- [x] Run the focused tests and verify RED on missing `compile_workflow` behavior.
- [x] Implement deterministic normalization/validation; do not invoke an LLM.
- [x] Run focused tests and verify GREEN.
- [x] Commit `feat(builder): compile contracts into explicit workflows`.

### Task 3: Handoff policy, harness profiles, and candidate routing plans

**Files:**
- Modify: `gateway/builder_paid_routing.py`
- Modify: `tests/test_builder_paid_routing.py`

**Interfaces:**
- Produces: `HandoffPlan`, `HarnessProfile`, `ExecutionRoutingPlan`, `plan_handoff(source_tier, target_tier)`, `select_harness_profile(task_class)`, `build_execution_routing_plan(...)`.
- Paid route keeps `worker_model`/`reviewer_model` compatibility and additionally exposes ordered candidate tuples when optional fallback config exists.

- [x] Write tests proving cheap/free→frontier uses artifact-compacted handoff, frontier→cheap/free preserves trajectory, same-tier continues, task classes select the four profiles, and malformed fallback candidates fail closed.
- [x] Run focused tests and verify RED.
- [x] Implement the minimal deterministic policy and optional candidate parsing. No executor fallback is introduced in the concurrently owned loop.
- [x] Run focused tests and verify GREEN.
- [x] Commit `feat(builder): make model handoffs and harness policy explicit`.

### Task 4: Persist routing/spend policy with compute receipts

**Files:**
- Modify: `gateway/compute_governor.py`
- Modify: `tests/test_compute_governor.py`

**Interfaces:**
- `record_receipt(..., policy: Mapping[str, Any] | None = None)` persists canonical JSON in additive `policy_json` column.
- Existing receipt rows remain readable and duplicate-settled-pass behavior is unchanged.

- [x] Write migration/round-trip tests on a pre-column DB and verify duplicate-work protection remains.
- [x] Run focused tests and verify RED.
- [x] Add idempotent column migration and canonical JSON serialization; reject non-serializable policy rather than dropping it.
- [x] Run focused tests and verify GREEN.
- [x] Commit `feat(builder): persist model routing policy receipts`.

### Task 5: ACES-style paired eval and WikiSkill-style distilled learning

**Files:**
- Modify: `scripts/session_learning.py`
- Modify: `tests/test_session_learning.py`

**Interfaces:**
- Produces: `compare_capability_runs(baseline: Mapping[str, float], candidate: Mapping[str, float], *, minimum_lift: float = 0.0) -> dict[str, Any]`.
- Produces: `record_evaluation_signal(...)` which writes only through existing `record_signal`/`Store` and uses category `capability_improvement`.

- [x] Write tests for exact matched pairs, task-set mismatch failure, minimum-lift decision, no signal for non-improvement, and two distinct sessions promoting the same positive lesson.
- [x] Run focused tests and verify RED.
- [x] Implement comparison and translation into the existing workflow-signal store; no skill file is auto-edited.
- [x] Run focused tests and verify GREEN.
- [x] Commit `feat(builder): measure and distill capability improvements`.

### Task 6: Integration verification and review handoff

**Files:**
- Modify only docs/evidence if required by verification.

- [x] Run `git diff --check`.
- [x] Run the exact combined focused suite from AC-6.
- [x] Run narrow lint/type checks for changed Python files if available without widening into unrelated failures.
- [x] Confirm forbidden overlapping files are unchanged relative to base.
- [x] Attempt a genuinely separate free reviewer process with only spec, SHA/diff, tests, and evidence. If unavailable, classify as `implemented, awaiting verification` rather than `verified`.
- [x] Push the non-main branch and open/update a PR only after the verification evidence is fresh. PR #704 opened against `main`; left unmerged.
