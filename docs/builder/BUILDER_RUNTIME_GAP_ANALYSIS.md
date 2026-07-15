---
type: analysis
title: "Builder Runtime Gap Analysis"
status: canonical
owner: jacob
primary_purpose: Compare current Builder runtime against Builder Operating Model — categorize every gap
derives_from:
  - docs/builder/BUILDER_OPERATING_MODEL.md
  - docs/builder/BUILDER_PACKET_LIFECYCLE.md
  - docs/builder/BUILDER_EXECUTION_PIPELINE.md
implements:
  - gateway/builder_loop.py
  - gateway/builder_runner.py
  - gateway/builder_initiative.py
  - gateway/builder_queue.py
review_cycle: quarterly (on significant runtime changes)
---

# Builder Runtime Gap Analysis

Compares the current Builder runtime (`gateway/builder_*.py`) against the Builder Operating Model (`docs/builder/BUILDER_OPERATING_MODEL.md`). Each gap is categorized as Required, Implementation Choice, Future Capability, or Out of Scope.

## Gap Categories

| Category | Meaning |
|---|---|
| **Required by architecture** | Must exist for the Builder to fulfill its contract. Missing now, needs implementation. |
| **Implementation choice** | A design decision not specified by the model. Exists, missing, or different — acceptable. |
| **Future capability** | Defined in model, not yet implemented. Deferred to future initiative. |
| **Out of scope** | Not a Builder concern. Owned by another Office or subsystem. |

## Gap Analysis

### 1. Research Phase

| Model says | Code does | Category |
|---|---|---|
| Builder should research: existing Kitty implementation, ADRs, architecture, standards, previous packets, external systems | No programmatic research phase. Context bundle (`builder_attempt.build_context_bundle()`) includes repo state and task metadata but does not query ADRs or architecture documents. | **Future capability** — Research automation requires Knowledge retrieval infrastructure. |
| Research produces conclusions, not bookmark collections | N/A — no automated research exists. | **Future capability** |

### 2. Contract Validation

| Model says | Code does | Category |
|---|---|---|
| Before touching code, verify: objective clear, success measurable, scope bounded, forbidden changes defined, architectural authority clear | Initiative manifest validates structural schema (fields, packet ordering, dependencies) but does NOT validate: success measurability, forbidden changes, or architectural authority. | **Required by architecture** — Contract validation exists but is incomplete. Missing: success criteria validation, forbidden-change detection, architectural authority check. |
| If not clear: escalate immediately. Never guess. | No programmatic escalation. Invalid manifests are rejected at apply time. | **Required by architecture** — Escalation path is defined in model but not implemented in code. |

### 3. Execution

| Model says | Code does | Category |
|---|---|---|
| Execution follows the implementation contract | Worker executes in shadow mode with context bundle. Result contract validated. Aligned. | ✅ Implemented |
| Never redesign architecture | Worker operates in isolated worktree. Scope violation detection exists (`RUN_SCOPE_VIOLATION`). | ✅ Implemented |
| Never expand scope | No scope expansion detection beyond worktree isolation. | **Implementation choice** — Worktree isolation is the primary scope boundary. |
| Never "fix nearby things" | No lint-like detection of unrelated changes. Rely on reviewer (when configured) or operator. | **Implementation choice** — Future: reviewer could detect scope drift in diff. |
| Never perform unrelated cleanup | Same as above. | **Implementation choice** |

### 4. Verification

| Model says | Code does | Category |
|---|---|---|
| Verification is independent. Assume implementation is wrong until proven otherwise. | Validation runs after worker exit. Optional review stage runs independent review command. | ✅ Partially implemented — independent review is optional and depends on review command configuration. |
| Did we satisfy the contract? | Implementation contract validation checks status, validation verdict. | ✅ Implemented |
| Did we violate architecture? | No architectural compliance check exists. | **Future capability** — Requires architectural rules encoded as validatable checks. |
| Did we introduce unnecessary complexity? | No automated complexity analysis. | **Future capability** — Requires complexity metrics integration. |
| Did we preserve existing guarantees? | No regression test analysis. | **Future capability** — Requires test suite integration with coverage tracking. |
| Passing tests alone is insufficient. | Current validation relies on worker's self-reported status + optional review. | **Implementation choice** — Review command is the extensibility point. |

### 5. Reflection

| Model says | Code does | Category |
|---|---|---|
| Every completed packet should produce reflection: what surprised us, what slowed us down, what doctrine changed, what should become reusable or automated | No automated reflection. Run manifest records raw evidence (exit code, timing, attempts) but does not synthesize into reflection. | **Future capability** — Requires Knowledge Model implementation (Finding, Knowledge, Pattern). |
| Reflection is mandatory. Without reflection the organization cannot improve. | Reflection is entirely manual — operator must review run manifests and extract lessons. | **Future capability** |

### 6. Escalation

| Model says | Code does | Category |
|---|---|---|
| Escalate when: architectural ambiguity, multiple valid designs, doctrine conflicts, contradictory evidence, missing context, implementation exceeds contract | No programmatic escalation. Task transitions to `blocked` with machine-readable reason. Operator decides next action. | **Required by architecture** — Escalation is defined as a model concept but falls to operator discretion. The gap is that escalation is not evented or routed to a specific Office. |
| Escalation is a success condition. Guessing is not. | Blocked tasks are visible in CLI and initiative status. No notification or routing. | **Future capability** — Requires Operations Office notification infrastructure. |

### 7. Knowledge Production

| Model says | Code does | Category |
|---|---|---|
| Every packet should ask: did we create reusable knowledge, a new pattern, doctrine, an ADR, automation, improved standards? | No knowledge production integration. | **Future capability** — Requires Knowledge Model implementation. |
| Not every packet will. Every packet should consider it. | Run manifests are evidence that could feed into Knowledge pipeline. No pipeline exists. | **Future capability** |

### 8. Success Metrics

| Model says | Code does | Category |
|---|---|---|
| Builder is measured by: implementation reliability, review success rate, recovery success, reduced rework, reduced ambiguity, increased organizational capability | Initiative status rolls up evidence (attempts used, worker failures, infrastructure failures, review approved, PR opened, done). This provides raw input for metrics. | **Future capability** — Metrics are computable from existing evidence but not yet surfaced as organizational metrics. |

### 9. Organizational Learning

| Model says | Code does | Category |
|---|---|---|
| Builder should improve over time from: packet reviews, failed implementations, architectural feedback, recurring mistakes, recurring successes | No feedback loop exists between current runs and future runs. No pattern detection. | **Future capability** — Requires Knowledge Model + Historical Recovery infrastructure. |
| Builder should become increasingly predictable. Predictability is a feature. | Predictability is observable from initiative evidence (attempt counts, failure rates) but not systematically tracked. | **Implementation choice** — Predictability metrics could be added to initiative status rollup. |

### 10. Prime Directive

| Model says | Code does | Category |
|---|---|---|
| Builder exists to reliably convert engineering intent into verified implementation while preserving architectural integrity and continuously increasing organizational capability. | Builder loop reliably converts context bundles into verified (or failed) implementation attempts with evidence. Shadow mode preserves integrity. | ✅ Partially implemented — verification exists, architectural integrity preservation exists (worktree isolation, scope violation detection), but organizational capability tracking does not. |
| Whenever implementation and architecture conflict, architecture wins. | Scope violation detection (`RUN_SCOPE_VIOLATION`) enforces this at the worktree boundary. | ✅ Implemented |

## Summary

| Gap Category | Count | Priority |
|---|---|---|
| Required by architecture | 3 | Contract validation completeness, escalation path, escalation routing |
| Implementation choice | 4 | Scope drift detection, review extensibility, verification sufficiency, predictability metrics |
| Future capability | 12 | Research, architectural compliance, complexity analysis, testing guarantees, reflection, knowledge production, success metrics, organizational learning, notification routing |
| Implemented / Aligned | 4 | Execution discipline, contract validation (basic), independent verification (optional), prime directive (scope violation) |

### Immediate Priorities (Required)

1. **Contract validation completeness** — Add success measurability and forbidden-change detection to initiative manifest validation.
2. **Escalation path** — Implement programmatic escalation when contract validation fails or architectural ambiguity is detected.
3. **Escalation routing** — Route escalations to the correct Office (Planning for ambiguity, Knowledge for doctrine conflict, Executive for scope expansion).

### Next Tier (Implementation Choice)

4. Scope drift detection in reviewer
5. Predictability metrics in initiative status
6. Verification sufficiency configuration

### Deferred to Knowledge Model Infrastructure

7. Research automation (requires Knowledge retrieval)
8. Architectural compliance checking (requires encoded rules)
9. Reflection automation (requires Finding/Knowledge/Pattern pipeline)
10. Knowledge production (requires Knowledge Engine)
11. Organizational learning loop (requires Historical Recovery)
