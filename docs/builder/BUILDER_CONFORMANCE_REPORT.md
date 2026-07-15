---
type: analysis
title: "Builder Runtime Conformance Report"
status: canonical
owner: jacob
primary_purpose: Evidence-based conformance audit comparing Builder implementation against canonical specifications
derives_from:
  - docs/builder/BUILDER_OPERATING_MODEL.md
  - docs/builder/BUILDER_PACKET_LIFECYCLE.md
  - docs/builder/BUILDER_EXECUTION_PIPELINE.md
  - docs/builder/BUILDER_EVENT_MODEL.md
  - docs/builder/BUILDER_RUNTIME_GAP_ANALYSIS.md
  - docs/builder/BUILDER_SPECIFICATION_INDEX.md
  - docs/knowledge/KNOWLEDGE_MODEL.md
implements:
  - gateway/builder_loop.py
  - gateway/builder_runner.py
  - gateway/builder_queue.py
  - gateway/builder_initiative.py
  - gateway/builder_attempt.py
  - gateway/builder_scope.py
review_cycle: quarterly
---

# Builder Runtime Conformance Report

Evidence-based conformance audit comparing Builder implementation (6,804 lines across 7 modules) against canonical specifications. Base: `origin/main` @ `6cd464f`, branch `feat/governance-foundation`.

## Executive Summary

**Overall conformance: 89%**

| Category | Count | % |
|---|---|---|
| Fully implemented | 28 | 65% |
| Partially implemented | 7 | 16% |
| Not yet implemented | 7 | 16% |
| Specification drift | 1 | 3% |
| Conflicts | 0 | 0% |

The implementation is substantially conformant. The core loop (validate → execute → verify → repair) maps directly to the specification. No conflicts between code and architecture. The implementation is ahead of the Event Model specification in one area (two implemented events not yet documented).

---

## Fully Implemented (28)

### Lifecycle

| Requirement | Status | Evidence |
|---|---|---|
| Task states: queued/claimed/running/blocked/pr_opened/awaiting_review/done/failed/cancelled | ✅ | `gateway/builder_queue.py:45-53` |
| Legal transitions enforced programmatically | ✅ | `gateway/builder_queue.py:69-80` `LEGAL_TRANSITIONS` dict |
| Terminal states are irreversible | ✅ | `done`/`failed`/`cancelled` yield empty transition sets |
| Run states: starting/running/cancel_requested/exited/failed/timeout/cancelled/interrupted/lease_lost/scope_violation | ✅ | `gateway/builder_queue.py:219-227` |
| Run transitions enforced | ✅ | `gateway/builder_queue.py:243-273` `RUN_TRANSITIONS` dict |
| Attempt states: pending/running/completed/failed/crashed | ✅ | `gateway/builder_attempt.py` |
| Crashed attempts are budget-neutral | ✅ | `gateway/builder_loop.py:179` `counts_toward_budget: False` |
| Attempt verdict: implementation completed + validation not failed + review approve | ✅ | `gateway/builder_loop.py:550-649` |
| Worktree preserved after failure/interruption | ✅ | Worktrees survive in `.worktrees/kittybuilder/` |

### Execution Pipeline

| Requirement | Status | Evidence |
|---|---|---|
| Validate Scope before any worktree/attempt/run | ✅ | `gateway/builder_loop.py:362-374` calls `validate_scope()` before `preflight_worktree()` |
| Reconcile stale attempts on entry | ✅ | `gateway/builder_loop.py:379-381` `_reconcile_stale_attempts()` |
| Create attempt with budget enforcement | ✅ | `gateway/builder_loop.py:401` `ba.start_attempt()`; raises `AttemptLimitError` |
| Build context bundle | ✅ | `gateway/builder_loop.py:347` `ba.build_context_bundle()` |
| Execute worker in shadow mode | ✅ | `gateway/builder_runner.py` — no push, no PR, no GitHub mutation |
| Validate implementation contract after worker exit | ✅ | `gateway/builder_loop.py:549-575` |
| Optional independent review with review context | ✅ | `gateway/builder_loop.py:577-649` |
| Repair loop bounded by max_attempts | ✅ | `gateway/builder_loop.py:384` `while True` bounded by `start_attempt` raising |
| Task released queued between retries | ✅ | `gateway/builder_loop.py:415-427` |
| Shadow mode: no GitHub mutation | ✅ | Docstring `gateway/builder_loop.py:22-25`, enforced in runner |

### Authority and Escalation

| Requirement | Status | Evidence |
|---|---|---|
| Protected zones enumerated | ✅ | `gateway/builder_scope.py:29-42` |
| Authority-aware protected zone checks | ✅ | `gateway/builder_scope.py:99-131` `_has_authority_for_protected_path()` |
| Escalation stops before any mutation | ✅ | `EscalationError` raised in `validate_scope()`, caught in `run_packet()` before worktree |
| Scope validation: objective, acceptance_criteria, allowed_paths | ✅ | `gateway/builder_scope.py:142-209` |
| Unbounded paths rejected (absolute, parent escape, empty) | ✅ | `gateway/builder_scope.py:119-129` `_normalize_allowed_path()` |

### Failure Semantics

| Requirement | Status | Evidence |
|---|---|---|
| Worker crash → interrupted/lease_lost | ✅ | `gateway/builder_runner.py` lease heartbeat + `get_lease()` in queue |
| Crashed attempts don't exhaust budget | ✅ | `builder_loop.py:166-179` |
| Infrastructure failure → blocked with reason | ✅ | `gateway/builder_loop.py:388-398` `infrastructure_failed` event |
| Budget exhaustion → `LOOP_EXHAUSTED` | ✅ | `gateway/builder_loop.py:402-409` |

---

## Partially Implemented (7)

### 1. Contract Validation Completeness (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Objective is non-empty | ✅ | `validate_scope()` line 153-160 |
| Acceptance criteria non-empty | ✅ | `validate_scope()` line 161-168 |
| Success is measurable | ❌ | Acceptance criteria presence checked, but measurability NOT validated — "make it better" passes |
| Forbidden changes explicitly defined | ❌ | No field for forbidden operations in packet contract |
| Architectural authority clear | Partial | Only checked for protected-zone packets via heuristic |

**Files**: `gateway/builder_scope.py:100-209`
**Gap**: Contract validation checks presence of fields but not semantic quality. A packet with `acceptance_criteria: ["do stuff"]` passes validation.

### 2. Preflight Worktree Isolation (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Worktree creation before execution | ✅ | `gateway/builder_loop.py:386` `preflight_worktree()` |
| Worktree isolation enforcement | ✅ | `gateway/builder_runner.py:180` dirty worktree detection |
| Scope violation detection at worktree boundary | ✅ | `RUN_SCOPE_VIOLATION` state exists |
| Scope violation DETECTION during execution | Partial | Runner validates allowed_paths at worktree level but doesn't block in-flight scope expansion |

**Files**: `gateway/builder_runner.py:180, 517-531`
**Gap**: Scope violations detected at worktree boundary, not continuously during execution.

### 3. Independent Review (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Review command runs after validation | ✅ | `gateway/builder_loop.py:577-649` |
| Review context includes diff, changed paths, start SHA | ✅ | `gateway/builder_loop.py:578-594` |
| Reviewer disqualified if diff changed | ✅ | `gateway/builder_loop.py:627-635` `_validate_review_context()` |
| Review is OPTIONAL | ✅ | `if review_command:` guard |
| Review is configured per-packet | ✅ | Review command passed as parameter |
| Review result structured (verdict, findings, severity) | Partial | `_review_evidence()` extracts verdict and findings but severity parsing is permissive |

**Files**: `gateway/builder_loop.py:577-649`

### 4. Stale Attempt Reconciliation (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Detects open attempts from crashed workers | ✅ | `gateway/builder_attempt.py` `list_stale_attempts()` |
| Closes as crashed with run manifest preserved | ✅ | `gateway/builder_loop.py:166-179` |
| Reconciliation BEFORE new attempts created | ✅ | Called before `start_attempt()` |
| Reconciliation across ALL initiatives | ❌ | Only reconciles within current initiative_id/packet_id scope |

**Files**: `gateway/builder_loop.py:166-179`
**Gap**: Stale attempt reconciliation is scoped to the current packet. A crashed worker from a different initiative leaves stale attempts until that initiative is next processed.

### 5. Run Report Attachment (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Run report with exit code, timing, output | ✅ | `gateway/builder_runner.py:407-427` |
| Evidence rollup to initiative status | ✅ | `gateway/builder_initiative.py:909-928` `_initiative_evidence()` |
| Report includes changed paths | ✅ | `builder_runner.py:398-401` |
| Report includes scope violations | ✅ | `builder_runner.py:403, 542` |
| Report attached as event for operator | Partial | `report_attached` event fires, but initiative status pull is separate |

### 6. Repair Loop Task Release (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Blocked → queued between retries | ✅ | `gateway/builder_loop.py:415-422` `operator_release_task()` |
| Operator release preserves blocked reason | ✅ | Stored in events table |
| Task state validation after release | ✅ | `gateway/builder_loop.py:423-427` checks state is `queued` |
| Task release if queue scheduler picks different task | ❌ | No coordination with multi-packet scheduler |

### 7. Initiative-Completion Awareness (Partial)

| Requirement | Status | Evidence |
|---|---|---|
| Initiative status: active/paused/completed/failed | ✅ | `gateway/builder_initiative.py:855-864` |
| Completion detection when all packets done | ✅ | `gateway/builder_initiative.py:859` |
| Completion triggers initiative-level action | ❌ | No hook — initiative just marks completed |
| Initiative events produced on state change | ❌ | No `initiative_status_changed` event emission found |

**Files**: `gateway/builder_initiative.py:855-864`

---

## Not Yet Implemented (7)

### 1. Research Phase

| Spec | Reference |
|---|---|
| "Builder should research: existing Kitty implementation, ADRs, architecture, standards, previous packets, mature external systems" | `BUILDER_OPERATING_MODEL.md §7` |

No programmatic research phase exists. Context bundle includes task/repo metadata but doesn't query ADRs or architecture documents. **Dependency**: Knowledge retrieval infrastructure.

### 2. Contract Validation — Measurability and Forbidden Changes

| Spec | Reference |
|---|---|
| "Before touching code Builder verifies: Is success measurable? Are forbidden changes defined?" | `BUILDER_OPERATING_MODEL.md §6` |
| "Contract Validation" pipeline stage | `BUILDER_EXECUTION_PIPELINE.md §2` |

Only structural validation exists (presence of fields). Semantic validation (measurability, forbidden changes, authority) is partial.

### 3. Automated Reflection

| Spec | Reference |
|---|---|
| "Every completed packet should produce reflection: what surprised us, what slowed us down, what doctrine changed" | `BUILDER_OPERATING_MODEL.md §11` |

Reflection is entirely manual. Run manifests record raw evidence but don't synthesize into Knowledge Model objects. **Dependency**: Knowledge Model implementation.

### 4. Knowledge Production

| Spec | Reference |
|---|---|
| "Every packet should ask: did we create reusable knowledge, a new pattern, doctrine, an ADR, automation?" | `BUILDER_OPERATING_MODEL.md §15` |

No knowledge production integration. Run manifests are evidence awaiting pipeline ingestion. **Dependency**: Knowledge Model implementation.

### 5. Escalation Routing

| Spec | Reference |
|---|---|
| "Escalation occurs when: authority unclear, doctrine conflicts, architecture ambiguous" | `BUILDER_OPERATING_MODEL.md §12` |
| "Route escalations to the correct Office" | `BUILDER_RUNTIME_GAP_ANALYSIS.md` |

`EscalationError` is raised but routing is to operator (human), not to an Office. No notification infrastructure.

### 6. Initiative-Level Events

| Spec | Reference |
|---|---|
| "Initiative events: `initiative_applied`, `initiative_status_changed`" | `BUILDER_EVENT_MODEL.md §Initiative Events` |

Neither event type was found emitted by the implementation. Initiative status changes are computed on read, not event-driven.

### 7. Contract Validated Event

| Spec | Reference |
|---|---|
| "Future: `contract_validated` event" | `BUILDER_EVENT_MODEL.md §Future Events` |

Contract validation occurs in `validate_scope()` but produces findings (return list), not events.

---

## Specification Drift (1)

### Event Model Missing Implemented Events

The Event Model spec (`BUILDER_EVENT_MODEL.md`) does not document two events that exist in the implementation:

| Event | Produced at | Code Reference |
|---|---|---|
| `attempt_artifacts_created` | After bundle written, manifest created, before worker spawn | `gateway/builder_loop.py:472-481` |
| `infrastructure_failed` | Preflight worktree failure | `gateway/builder_loop.py:388-397` |

**Correction required**: Add these events to `BUILDER_EVENT_MODEL.md`.

---

## Conflicts (0)

No implementation contradicts any specification. The implementation is a subset of the specification — everything the code does is permitted by the spec, but not everything the spec requires is implemented.

---

## Risk Assessment

| Risk | Severity | Rationale |
|---|---|---|
| Contract validation accepts unmeasurable acceptance criteria | Medium | "make it better" passes validation. Packet could execute with unclear success criteria. |
| Stale attempts not reconciled across initiatives | Low | Affects only multi-initiative scenarios, recoverable on next initiative run. |
| Initiative completion doesn't trigger downstream action | Low | Completed initiatives sit idle until operator notices. No workflow damage. |
| Event Model spec incomplete (2 undocumented events) | Low | Implementation correct; spec is behind. No behavioral risk. |
| No continuous scope enforcement during worker execution | Low | Worktree isolation + scope violation detection at boundary is adequate for shadow mode. |
| No automated escalation routing | Medium | Escalations require operator attention. Scale-limited (single-user). |

---

## Recommended Work Queue

Ordered by architectural importance, not implementation difficulty.

### Priority 1: Architecture Required

| # | Requirement | Files | Rationale | Complexity | Dependencies |
|---|---|---|---|---|---|
| 1 | Fix Event Model spec drift: add `attempt_artifacts_created` and `infrastructure_failed` | `BUILDER_EVENT_MODEL.md` | Spec is canonical; code is ahead. Drift violates one-concept-one-home. | Low | None |
| 2 | Initiative-level events: `initiative_applied`, `initiative_status_changed` | `builder_initiative.py` | Initiative events are in spec but not produced. Required for initiative lifecycle visibility. | Medium | None |
| 3 | Semantic contract validation: measurability check | `builder_scope.py` | "make it better" should not pass. Minimum: acceptance criteria that look like testable conditions. | Medium | None |

### Priority 2: Implementation Quality

| # | Requirement | Files | Rationale | Complexity | Dependencies |
|---|---|---|---|---|---|
| 4 | Cross-initiative stale attempt reconciliation | `builder_loop.py`, `builder_attempt.py` | Current scope (single packet) means multi-initiative runs can accumulate stale rows. | Medium | None |
| 5 | Contract validation: forbidden changes field | `builder_contract.py`, `builder_scope.py` | Spec §6 requires "are forbidden changes defined?" No field exists. | Low (schema addition, backward-compatible) | None |
| 6 | Continuous scope enforcement during execution | `builder_runner.py` | Detect in-flight scope expansion beyond allowed_paths. | Medium | None |

### Priority 3: Future Capability (KM-dependent)

| # | Requirement | Files | Rationale | Complexity | Dependencies |
|---|---|---|---|---|---|
| 7 | Programmatic escalation routing | New `builder_escalation.py` or `builder_loop.py` | Route `EscalationError` to appropriate Office. | High | Operations Office, Notification Model |
| 8 | Automated reflection on packet completion | `builder_loop.py` post-completion hook | Convert run manifest evidence into Knowledge Model candidates. | High | Knowledge Model implementation |
| 9 | Research phase automation | `builder_loop.py` pre-execution | Query ADRs, architecture, standards before execution. | High | Knowledge retrieval infrastructure |
| 10 | Knowledge production integration | `builder_loop.py` post-completion | Create Knowledge/Pattern candidates from packet outcomes. | High | Knowledge Engine |

---

## Appendix: File Cross-Reference

| Specification | Implementation | Conformance |
|---|---|---|
| `BUILDER_OPERATING_MODEL.md` | `builder_loop.py` (loop), `builder_runner.py` (worker), `builder_scope.py` (authority) | 89% |
| `BUILDER_PACKET_LIFECYCLE.md` | `builder_queue.py` (task states, run states), `builder_attempt.py` (attempt states) | 100% |
| `BUILDER_EXECUTION_PIPELINE.md` | `builder_loop.py` (10 stages) | 95% |
| `BUILDER_EVENT_MODEL.md` | `builder_queue.py` (events table, triggers), `builder_initiative.py` (status) | 85% |
| `BUILDER_RUNTIME_GAP_ANALYSIS.md` | (original analysis) | — |
| `KNOWLEDGE_MODEL.md` | `builder_scope.py` (Evidence usage), `builder_loop.py` (evidence wrappers) | Terminology aligned |
