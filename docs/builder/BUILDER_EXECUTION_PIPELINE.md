---
type: specification
title: "Builder Execution Pipeline"
status: canonical
owner: jacob
primary_purpose: Canonical execution pipeline — every stage with entry criteria, exit criteria, owner, and contract
derives_from:
  - docs/builder/BUILDER_PACKET_LIFECYCLE.md
  - docs/builder/BUILDER_OPERATING_MODEL.md
implements:
  - gateway/builder_loop.py
  - gateway/builder_runner.py
review_cycle: quarterly
---

# Builder Execution Pipeline

Canonical execution pipeline. Every packet flows through these stages in order. Each stage has entry criteria (what must be true before entering) and exit criteria (what must be true before advancing).

## Pipeline Overview

```
Receive Packet
    │
    ▼
Validate Scope     ← entry: initiative applied, packet eligible
    │
    ▼
Reconcile Stale    ← entry: task QUEUED, build contract valid
    │
    ▼
Create Attempt     ← entry: task CLAIMED, no stale attempts
    │
    ▼
Build Context      ← entry: attempt record exists
    │
    ▼
Execute Worker     ← entry: isolated worktree, context bundle written
    │
    ▼
Validate Output    ← entry: worker exited, result contract exists
    │
    ▼
Review (optional)  ← entry: implementation validated, review command configured
    │
    ▼
Succeed OR Repair  ← entry: verdict computed
    │       │
    ▼       ▼
Complete   Retry (if attempts remain)
           or
           Fail (if exhausted)
```

## Stage Details

### 1. Receive Packet

| Field | Value |
|---|---|
| Owner | Operator / Builder runner |
| Entry criteria | Initiative applied and valid (`builder_initiative.apply()`); packet exists in queue with state `queued` |
| Exit criteria | Packet claimed (`queued` → `claimed`), lease acquired |
| Implements | `gateway/builder_runner.py` `run_packet()` claim logic |
| Inputs | Task ID, lease token |
| Outputs | Claimed task row, lease expiry |

### 2. Validate Scope

| Field | Value |
|---|---|
| Owner | Builder runner |
| Entry criteria | Task claimed, contract available |
| Exit criteria | Contract scope validated — objective clear, success measurable, scope bounded, forbidden changes defined |
| Implements | `gateway/builder_runner.py` pre-run checks |
| Inputs | Build contract, initiative manifest, task metadata |
| Outputs | Validated scope (or rejection with reason) |
| Failure mode | Task → `failed` (Cannot execute without clear scope) |

### 3. Reconcile Stale Attempts

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | Task in `running` state |
| Exit criteria | No open stale attempts from crashed workers |
| Implements | `gateway/builder_loop.py` `_reconcile_stale_attempts()` |
| Inputs | Initiative ID, packet ID, DB path |
| Outputs | Stale attempts closed as `crashed` with run manifests preserved |
| Invariant | Crashed attempts do not count toward attempt budget |

### 4. Create Attempt

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | No budget-exhausting attempts pending; within `policy.max_attempts` |
| Exit criteria | Attempt record created with `pending` state |
| Implements | `gateway/builder_attempt.py` `start_attempt()` |
| Inputs | Initiative ID, packet ID, attempt number |
| Outputs | Attempt ID, attempt directory, context bundle path |

### 5. Build Context

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | Attempt directory exists |
| Exit criteria | Context bundle written to `KB_BUNDLE_PATH`, context manifest at `KB_CONTEXT_MANIFEST_PATH` |
| Implements | `gateway/builder_attempt.py` `build_context_bundle()` |
| Inputs | Task, initiative, build contract, repository state |
| Outputs | JSON context bundle, stable identity hash |

### 6. Execute Worker

| Field | Value |
|---|---|
| Owner | Builder runner (shadow mode) |
| Entry criteria | Isolated git worktree exists, context bundle written |
| Exit criteria | Worker process exited (any code), run manifest written |
| Implements | `gateway/builder_runner.py` `run_worker()` |
| Inputs | Worktree path, worker command, env vars (KB_ATTEMPT_ID, KB_BUNDLE_PATH, KB_RESULT_PATH, KB_CONTEXT_MANIFEST_PATH) |
| Outputs | Implementation result contract at `KB_RESULT_PATH`, run manifest |
| Failure mode | Crash → `interrupted`/`lease_lost`; scope violation → `scope_violation` |
| Invariant | Shadow mode only — no GitHub mutations |

### 7. Validate Output

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | Worker exited, `KB_RESULT_PATH` exists |
| Exit criteria | Implementation contract validated — status is `completed`, validation verdict is not `failed` |
| Implements | `gateway/builder_loop.py` `_validation_evidence()` |
| Inputs | Implementation result contract |
| Outputs | Validation evidence (status, verdict, outputs) |
| Failure mode | Missing or invalid contract → attempt `failed` |

### 8. Review (Conditional)

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | Implementation validated; review command configured |
| Exit criteria | Review result contract written, verdict is `approve` or `reject` |
| Implements | `gateway/builder_loop.py` `_review_evidence()` |
| Inputs | Review command, worktree path, context manifest |
| Outputs | Review evidence (verdict, findings, severity) |
| Failure mode | Missing/invalid review contract → attempt `failed`; reject verdict → attempt `failed` |

### 9. Verdict and Completion

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | Validation complete, review complete (if configured) |
| Exit criteria (Success) | Implementation `completed` AND validation not `failed` AND (no review OR review `approve`) |
| Exit criteria (Failure) | Any condition not met → attempt `failed` |
| Implements | `gateway/builder_loop.py` attempt verdict logic |
| Outcome (Success) | Task → `blocked` (shadow mode exit); run manifest records success evidence |
| Outcome (Failure) | Attempt `failed`; retry if under `max_attempts`; task → `blocked` between retries |

### 10. Repair Loop (Conditional)

| Field | Value |
|---|---|
| Owner | Builder loop |
| Entry criteria | Attempt `failed`, attempts remaining under `max_attempts` |
| Exit criteria | New attempt created and re-executed, OR budget exhausted |
| Implements | `gateway/builder_loop.py` main loop |
| Max attempts | `policy.max_attempts` (enforced by `start_attempt`) |
| Between retries | Task released `blocked` → `queued` to allow queue re-selection |

## Shadow Mode Constraint

Current implementation (KB-S3b) operates entirely in shadow mode:
- No push to remote
- No PR creation
- No GitHub mutations
- Post-`blocked` states (`pr_opened`, `awaiting_review`, `done`) require operator/KB-S4 action

This constraint will be lifted by future KB-S4 (PR reconciliation and merge detection).
