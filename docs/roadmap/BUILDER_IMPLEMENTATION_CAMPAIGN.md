---
type: plan
title: "Builder Implementation Campaign"
status: active
owner: jacob
primary_purpose: Complete work graph for all remaining Builder implementation — dependencies, ownership, verification gates, merge order
derives_from:
  - docs/builder/BUILDER_OPERATING_MODEL.md
  - docs/builder/BUILDER_CONFORMANCE_REPORT.md
  - docs/builder/BUILDER_RUNTIME_GAP_ANALYSIS.md
review_cycle: continuous (updated per packet completion)
---

# Builder Implementation Campaign

This document is the single source of truth for all remaining Builder implementation work. Every packet references it. Workers update completion state here. No other planning documents are created — all state lives in this one file.

## Architecture Freeze

The following are frozen unless an implementation contradiction is discovered:

- Governance documents (VISION, CONSTITUTION, GOVERNANCE)
- Knowledge Model (KNOWLEDGE_MODEL.md)
- Builder specifications (OPERATING_MODEL, LIFECYCLE, PIPELINE, EVENT_MODEL, GAP_ANALYSIS, CONFORMANCE_REPORT, SPECIFICATION_INDEX)
- ADRs (0001-0019)
- SYSTEM_MAP

If implementation reveals a spec contradiction, document it. Do NOT modify the spec without owner review.

## Campaign Structure

```
Phase 1: Runtime Conformance            [▢▢▢▢▢▢]  6 packets
    │
Phase 2: Event System Completion        [▢▢▢▢]    4 packets
    │
Phase 3: Semantic Validation            [▢▢▢▢]    4 packets
    │
Phase 4: Initiative Runtime             [▢▢▢]     3 packets
    │
Phase 5: Builder Receipts               [▢▢▢]     3 packets
    │
Phase 6: Knowledge Engine Planning      [▢▢]      2 packets
    │
Phase 7: Builder Maturity               [▢▢]      2 packets
    │
Phase 8: Builder UX                     [▢▢▢]     3 packets
    │
Phase 9: Release Readiness              [▢▢▢▢]    4 packets

Total: 31 packets
```

## Dependency Graph

```
Phase 1 ──────────────────────────┐
    │                              │
    ├── P1.1 (Event spec fix) ─────┤  ← no dependencies
    ├── P1.2 (Initiative events) ──┤  ← no dependencies
    ├── P1.3 (Semantic validation)─┤  ← no dependencies
    ├── P1.4 (Cross-initiative) ───┤  ← no dependencies
    ├── P1.5 (Forbidden changes) ──┤  ← no dependencies
    └── P1.6 (Scope enforcement) ──┘  ← depends on builder_scope.py

Phase 2 ──────────────────────────┐
    │                              │
    ├── P2.1 (Contract event) ─────┤  ← depends on P1.3
    ├── P2.2 (Event consumption) ──┤  ← depends on P1.1
    ├── P2.3 (Event schema docs) ──┤  ← depends on P1.1, P1.2
    └── P2.4 (Initiative events) ──┘  ← depends on P1.2

Phase 3 ──────────────────────────┐
    │                              │
    ├── P3.1 (Measurability) ──────┤  ← depends on P1.3
    ├── P3.2 (Forbidden detection)─┤  ← depends on P1.5
    ├── P3.3 (Arch authority) ─────┤  ← depends on P1.3
    └── P3.4 (ADR cross-ref) ──────┘  ← depends on P3.3

Phase 4 ──────────────────────────┐
    ├── P4.1 (Completion hooks) ───┤  ← depends on P1.2
    ├── P4.2 (Event-driven status)─┤  ← depends on P2.4
    └── P4.3 (Pause/resume) ───────┘  ← depends on P4.1

Phase 5 ──────────────────────────┐
    ├── P5.1 (Receipt model) ──────┤  ← depends on Phase 4
    ├── P5.2 (Receipt → evidence) ─┤  ← depends on P5.1
    └── P5.3 (Receipt verification)┤  ← depends on P5.1

Phase 6 ──────────────────────────┐
    ├── P6.1 (Research phase) ─────┤  ← depends on Phase 3
    └── P6.2 (Reflection auto) ────┘  ← depends on P5.2

Phase 7 ──────────────────────────┐
    ├── P7.1 (Predictability) ─────┤  ← depends on P5.3
    └── P7.2 (Self-building cap) ──┘  ← depends on P6.1

Phase 8 ──────────────────────────┐
    ├── P8.1 (Initiative dash) ────┤  ← depends on P2.2
    ├── P8.2 (Packet status) ──────┤  ← depends on P2.2
    └── P8.3 (Operator surface) ───┘  ← depends on P8.1, P8.2

Phase 9 ──────────────────────────┐
    ├── P9.1 (Test coverage) ──────┤  ← depends on all prior
    ├── P9.2 (Doc consistency) ────┤  ← depends on all prior
    ├── P9.3 (Performance) ────────┤  ← depends on all prior
    └── P9.4 (Migration validation)┤  ← depends on P5.3
```

## Parallelization

Packets within a phase with no inter-dependencies can run concurrently:

| Phase | Parallelizable | Sequential |
|---|---|---|
| Phase 1 | P1.1, P1.2, P1.3, P1.4, P1.5 | P1.6 depends on builder_scope.py being stable |
| Phase 2 | P2.1, P2.4 | P2.2 depends on P1.1; P2.3 depends on P1.1+P1.2 |
| Phase 3 | P3.1, P3.2, P3.3 | P3.4 depends on P3.3 |
| Phase 4 | P4.3 | P4.1 before P4.2 before P4.3 |
| Phase 5 | P5.3 | P5.1 before P5.2 |
| Phase 6 | P6.1, P6.2 | — |
| Phase 7 | P7.1, P7.2 | — |
| Phase 8 | P8.1, P8.2 | P8.3 depends on P8.1+P8.2 |
| Phase 9 | P9.1, P9.2, P9.3 | P9.4 depends on P5.3 |

**Maximum concurrent workers**: 5 (Phase 1)

## Merge Order

1. Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9
2. Within each phase, sequential packets merge in dependency order
3. Parallel packets merge in any order; merge conflicts resolved against latest main
4. Each packet is one PR. One branch per packet. `feat/<phase>/<packet-id>`

## Expected PR Count

Total PRs: 31. Estimated time: 2-3 weeks at 2-3 PRs per day.

## Phase Details

---

### Phase 1: Runtime Conformance

**Objective**: Close all "Required by Architecture" gaps from the conformance report.

**Completion criteria**: No "Required by Architecture" gaps remain.

#### P1.1 — Event Model Specification Fix

| Field | Value |
|---|---|
| Files | `docs/builder/BUILDER_EVENT_MODEL.md` |
| Requirement | Document `attempt_artifacts_created` and `infrastructure_failed` events |
| Worker | Worker 1 |
| Reviewer | Auto (10-min review) |
| Verification | `python3 scripts/docs_lint.py` passes; both events have producer/consumer/payload/ordering |
| Architecture review | Not required |
| Completed | Yes — 2026-07-15 |

#### P1.2 — Initiative Event Emission

| Field | Value |
|---|---|
| Files | `gateway/builder_initiative.py` |
| Requirement | Emit `initiative_applied` on apply, `initiative_status_changed` on status transition |
| Worker | Worker 1 |
| Reviewer | Worker 2 |
| Verification | `python3.12 -m pytest tests/test_builder_initiative.py -v`; both events appear in events table |
| Architecture review | Not required |
| Completed | Yes — 2026-07-15 |

#### P1.3 — Semantic Contract Validation: Measurability

| Field | Value |
|---|---|
| Files | `gateway/builder_scope.py`, `tests/test_builder_scope.py` |
| Requirement | Reject acceptance criteria that are semantically unmeasurable ("make it better" should not pass) |
| Worker | Worker 2 |
| Reviewer | Worker 1 |
| Verification | `python3.12 -m pytest tests/test_builder_scope.py -v`; "make it better" → `incomplete_contract` |
| Architecture review | Required — heuristic boundary needs spec alignment |
| Completed | No |

#### P1.4 — Cross-Initiative Stale Attempt Reconciliation

| Field | Value |
|---|---|
| Files | `gateway/builder_attempt.py`, `gateway/builder_loop.py` |
| Requirement | Reconcile stale attempts across ALL initiatives, not just current |
| Worker | Worker 1 |
| Reviewer | Worker 2 |
| Verification | `python3.12 -m pytest tests/test_builder_loop.py -v -k stale`; query confirms cross-initiative coverage |
| Architecture review | Not required |
| Completed | No |

#### P1.5 — Forbidden Changes Field

| Field | Value |
|---|---|
| Files | `gateway/builder_contract.py`, `gateway/builder_scope.py` |
| Requirement | Add `forbidden_changes` field to contract schema; validate in scope check |
| Worker | Worker 2 |
| Reviewer | Worker 1 |
| Verification | `python3.12 -m pytest tests/test_builder_scope.py -v -k forbidden`; forbidden path detection works |
| Architecture review | Not required (backward-compatible addition) |
| Completed | No |

#### P1.6 — Continuous Scope Enforcement

| Field | Value |
|---|---|
| Files | `gateway/builder_runner.py` |
| Requirement | Detect in-flight scope expansion beyond allowed_paths during worker execution |
| Worker | Worker 1 |
| Reviewer | Worker 2 |
| Verification | `python3.12 -m pytest tests/test_builder_runner.py -v -k scope`; scope violation detected mid-execution |
| Architecture review | Required — impacts runner execution model |
| Completed | No |

---

### Phase 2: Event System Completion

**Completion criteria**: All specified events are emitted. Event consumption surface exists.

#### P2.1 — Contract Validated Event

| Completed | No |
|---|---|
| Files | `gateway/builder_scope.py`, `gateway/builder_queue.py` |
| Requirement | Emit `contract_validated` event when scope validation completes |
| Verification | `python3.12 -m pytest tests/test_builder_scope.py -v -k contract_validated` |
| Depends on | P1.3 |

#### P2.2 — Event Consumption Surface

| Completed | No |
|---|---|
| Files | `gateway/builder_cli.py` (new `--events` view) |
| Requirement | Operator-visible event stream: latest N events across all tasks, filterable by event type, initiative |
| Verification | `python3.12 -m pytest tests/test_builder_cli.py -v -k events` |
| Depends on | P1.1 |

#### P2.3 — Event Schema Documentation

| Completed | No |
|---|---|
| Files | `docs/builder/BUILDER_EVENT_MODEL.md` |
| Requirement | Add JSON schema for every event payload; update Future Events section |
| Verification | `python3 scripts/docs_lint.py` passes |
| Depends on | P1.1, P1.2 |

#### P2.4 — Initiative Status Events (full)

| Completed | No |
|---|---|
| Files | `gateway/builder_initiative.py` |
| Requirement | Event-driven initiative status updates (active/paused/completed/failed) |
| Verification | `python3.12 -m pytest tests/test_builder_initiative.py -v -k status_events` |
| Depends on | P1.2 |

---

### Phase 3: Semantic Validation

**Completion criteria**: Contract validation is semantically meaningful, not just structurally present.

#### P3.1 — Measurability Heuristics

| Completed | No |
|---|---|
| Files | `gateway/builder_scope.py` |
| Requirement | Implement measurability scoring for acceptance criteria |
| Verification | `python3.12 -m pytest tests/test_builder_scope.py -v -k measurability` |
| Depends on | P1.3 |

#### P3.2 — Forbidden Changes Detection

| Completed | No |
|---|---|
| Files | `gateway/builder_scope.py`, `gateway/builder_runner.py` |
| Requirement | Detect when worker modifies forbidden paths during execution |
| Verification | `python3.12 -m pytest tests/test_builder_runner.py -v -k forbidden_change` |
| Depends on | P1.5 |

#### P3.3 — Architectural Authority Verification

| Completed | No |
|---|---|
| Files | `gateway/builder_scope.py` |
| Requirement | Verify ADR references are valid (ADR exists, is accepted, is not superseded) |
| Verification | `python3.12 -m pytest tests/test_builder_scope.py -v -k authority` |
| Depends on | P1.3 |

#### P3.4 — ADR Cross-Referencing

| Completed | No |
|---|---|
| Files | `gateway/builder_scope.py` |
| Requirement | Validate that ADR references in packet contracts point to actual ADR files |
| Verification | `python3.12 -m pytest tests/test_builder_scope.py -v -k adr_crossref` |
| Depends on | P3.3 |

---

### Phase 4: Initiative Runtime

**Completion criteria**: Initiative lifecycle is fully event-driven with completion hooks.

#### P4.1 — Initiative Completion Hooks

| Completed | No |
|---|---|
| Files | `gateway/builder_initiative.py` |
| Requirement | Execute hook when all packets in initiative reach terminal state |
| Verification | `python3.12 -m pytest tests/test_builder_initiative.py -v -k completion_hook` |
| Depends on | P1.2 |

#### P4.2 — Event-Driven Initiative Status

| Completed | No |
|---|---|
| Files | `gateway/builder_initiative.py` |
| Requirement | Status transitions driven by events, not computed on read |
| Verification | `python3.12 -m pytest tests/test_builder_initiative.py -v -k event_driven` |
| Depends on | P2.4 |

#### P4.3 — Initiative Pause/Resume

| Completed | No |
|---|---|
| Files | `gateway/builder_initiative.py`, `gateway/builder_queue.py` |
| Requirement | Operator can pause/resume an initiative; paused initiatives skip queue selection |
| Verification | `python3.12 -m pytest tests/test_builder_initiative.py -v -k pause_resume` |
| Depends on | P4.1 |

---

### Phase 5: Builder Receipts

**Completion criteria**: Every completed packet produces a Knowledge Model Receipt.

#### P5.1 — Receipt Data Model

| Completed | No |
|---|---|
| Files | `gateway/builder_receipt.py` (new) |
| Requirement | Receipt schema: id, packet_id, initiative_id, outcome, evidence_refs, verification, recorded_at |
| Verification | `python3.12 -m pytest tests/test_builder_receipt.py -v` |
| Architecture review | Required — first runtime implementation of Knowledge Model concept |

#### P5.2 — Receipt → Evidence Pipeline

| Completed | No |
|---|---|
| Files | `gateway/builder_receipt.py`, `gateway/builder_loop.py` |
| Requirement | On packet completion, produce Receipt; Receipt feeds into evidence system |
| Verification | `python3.12 -m pytest tests/test_builder_receipt.py -v -k evidence_pipeline` |
| Depends on | P5.1 |

#### P5.3 — Receipt Verification

| Completed | No |
|---|---|
| Files | `gateway/builder_receipt.py`, tests |
| Requirement | Receipts are verifiable: hash chain from evidence to receipt, verification command output included |
| Verification | `python3.12 -m pytest tests/test_builder_receipt.py -v -k verify` |
| Depends on | P5.1 |

---

### Phase 6: Knowledge Engine Planning

**Completion criteria**: Research and reflection stages defined for future implementation.

#### P6.1 — Research Phase Design

| Completed | No |
|---|---|
| Files | `docs/builder/BUILDER_RESEARCH_PHASE.md` (spec) |
| Requirement | Specify research phase: inputs (packet contract, repo state), outputs (research findings), ADR/architecture query API |
| Verification | `python3 scripts/docs_lint.py` passes; spec cross-references Knowledge Model terms correctly |
| Architecture review | Required |
| Implementation | Deferred — this phase produces design, not code |

#### P6.2 — Reflection Automation Design

| Completed | No |
|---|---|
| Files | `docs/builder/BUILDER_REFLECTION_AUTOMATION.md` (spec) |
| Requirement | Specify reflection pipeline: run manifest → evidence extraction → knowledge candidates |
| Verification | `python3 scripts/docs_lint.py` passes; pipeline maps to existing event model and run manifest structure |
| Depends on | P5.2 |
| Architecture review | Required |
| Implementation | Deferred |

---

### Phase 7: Builder Maturity

**Completion criteria**: Builder tracks and improves its own performance.

#### P7.1 — Predictability Metrics

| Completed | No |
|---|---|
| Files | `gateway/builder_metrics.py` (new) |
| Requirement | Track and surface: attempt success rate, review pass rate, recovery success, mean packet time |
| Verification | `python3.12 -m pytest tests/test_builder_metrics.py -v` |
| Depends on | P5.3 |

#### P7.2 — Self-Building Capability Baseline

| Completed | No |
|---|---|
| Files | `gateway/builder_self_build.py` (new), `docs/builder/BUILDER_SELF_BUILD_CAPABILITY.md` |
| Requirement | Baseline measurement: what percentage of Builder packets can Builder execute against itself |
| Verification | `python3.12 -m pytest tests/test_builder_self_build.py -v` |
| Depends on | P6.1 |

---

### Phase 8: Builder UX

**Completion criteria**: Operator can inspect Builder state without SQL.

#### P8.1 — Initiative Dashboard

| Completed | No |
|---|---|
| Files | `gateway/builder_cli.py` |
| Requirement | `builder status` shows all initiatives, their state, packet progress, recent events |
| Verification | `python3.12 -m pytest tests/test_builder_cli.py -v -k dashboard` |
| Depends on | P2.2 |

#### P8.2 — Packet Status Visualization

| Completed | No |
|---|---|
| Files | `gateway/builder_cli.py` |
| Requirement | `builder status --packet <id>` shows full packet lifecycle: attempts, evidence, events, PR links |
| Verification | `python3.12 -m pytest tests/test_builder_cli.py -v -k packet_status` |
| Depends on | P2.2 |

#### P8.3 — Operator Intervention Surface

| Completed | No |
|---|---|
| Files | `gateway/builder_cli.py` |
| Requirement | Pause/resume/cancel/release operations from CLI with confirmation prompts |
| Verification | `python3.12 -m pytest tests/test_builder_cli.py -v -k intervene` |
| Depends on | P8.1, P8.2 |

---

### Phase 9: Release Readiness

**Completion criteria**: Full test coverage, docs consistent, performance measured.

#### P9.1 — Test Coverage

| Completed | No |
|---|---|
| Files | `tests/test_builder_*.py` |
| Requirement | >90% line coverage on all `gateway/builder_*.py` files; integration tests for full packet lifecycle |
| Verification | `python3.12 -m pytest tests/test_builder_*.py --cov=gateway --cov-report=term --cov-fail-under=90 -q` |
| Depends on | All prior phases |

#### P9.2 — Documentation Consistency

| Completed | No |
|---|---|
| Files | `docs/builder/*.md`, `docs/knowledge/KNOWLEDGE_MODEL.md` |
| Requirement | All specs match implementation; no undocumented events; no stale field references |
| Verification | `python3 scripts/docs_lint.py && python3 scripts/docs_system_map.py --check` |
| Depends on | All prior phases |

#### P9.3 — Performance Benchmarks

| Completed | No |
|---|---|
| Files | `tests/test_builder_performance.py` |
| Requirement | Baseline: packet execution time, worktree creation time, review latency |
| Verification | `python3.12 -m pytest tests/test_builder_performance.py -v` |
| Depends on | All prior phases |

#### P9.4 — Migration Path Validation

| Completed | No |
|---|---|
| Files | `gateway/builder_migration.py` |
| Requirement | Existing queue data survives schema migrations; backwards compatibility with old packet contracts |
| Verification | `python3.12 -m pytest tests/test_builder_migration.py -v` |
| Depends on | P5.3 |

---

## Verification Gates

Each PR must pass the gates relevant to its changed paths:

| Gate | Command |
|---|---|
| Unit tests | `python3.12 -m pytest tests/test_builder_*.py -q -x` |
| Docs lint (governed docs touched) | `python3 scripts/docs_lint.py` |
| SYSTEM_MAP (governed docs touched) | `python3 scripts/docs_system_map.py --check` |
| Ruff | `python3 -m ruff check gateway/ tests/` |
| MyPy | `python3 -m mypy gateway/ --ignore-missing-imports` |
| Frontend build (UI touched) | `cd gateway/kitty-chat && npm run build` |
| Frontend tests (UI touched) | `cd gateway/kitty-chat && npm test` |

Architecture review gates: required on packets marked "Architecture review: Required."

## Ownership

| Role | Responsibility |
|---|---|
| Worker 1 | Primary implementer. Owns P1.1, P1.2, P1.4, P1.6, P2.1-P2.4, P4.1-P4.3 |
| Worker 2 | Secondary implementer. Owns P1.3, P1.5, P3.1-P3.4, P8.1-P8.3 |
| Reviewer (opposite worker) | Independent review per packet |
| Architect (Jacob/Codex) | Architecture review gates, ADR amendments, spec modifications |
| Orchestrator | Lease management, worker dispatch, progress tracking |
