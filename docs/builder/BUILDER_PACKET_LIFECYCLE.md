---
type: specification
title: "Builder Packet Lifecycle"
status: canonical
owner: jacob
primary_purpose: Complete state machine for Builder packets — states, transitions, invariants, recovery paths
derives_from:
  - docs/builder/BUILDER_OPERATING_MODEL.md
  - docs/architecture/SYSTEM_INTERACTIONS.md
implements:
  - gateway/builder_queue.py
  - gateway/builder_loop.py
  - gateway/builder_initiative.py
review_cycle: quarterly (on state machine changes)
---

# Builder Packet Lifecycle

Canonical state machine for Builder packets. Every packet transitions through these states in order. Transitions are enforced by `gateway/builder_queue.py` `LEGAL_TRANSITIONS`.

## Task State Machine

```
queued ──→ claimed ──→ running ──→ blocked ──→ pr_opened ──→ awaiting_review ──→ done
  │          │           │           │            │                 │              │
  │          │           │           │            │                 │              │
  └──────────┴───────────┴───────────┴────────────┴─────────────────┴──────→ failed
  │          │           │           │            │                 │        │
  └──────────┴───────────┴───────────┴────────────┴─────────────────┴──→ cancelled
```

### States

| State | Meaning | Owner | Terminal |
|---|---|---|---|
| `queued` | Packet is eligible for execution, awaiting a worker claim | Operator | No |
| `claimed` | Worker has claimed the packet (lease held) | Worker | No |
| `running` | Worker is actively executing in isolated worktree | Runner | No |
| `blocked` | Execution paused — worker exited (shadow mode), or infrastructure failure | Operator | No |
| `pr_opened` | Implementation pushed and PR opened (KB-S4) | Operator | No |
| `awaiting_review` | PR open, awaiting external review resolution | Operator | No |
| `done` | Packet succeeded — all criteria met, PR merged or shadow result accepted | System | Yes |
| `failed` | Packet exhausted attempts or unrecoverable error | System | Yes |
| `cancelled` | Packet cancelled by operator | Operator | Yes |

### Legal Transitions

| From | To (allowed) |
|---|---|
| `queued` | `claimed`, `failed`, `cancelled` |
| `claimed` | `running`, `failed`, `cancelled`, `queued` |
| `running` | `blocked`, `pr_opened`, `failed`, `cancelled` |
| `blocked` | `running`, `queued`, `failed`, `cancelled`, `pr_opened` |
| `pr_opened` | `awaiting_review`, `failed`, `cancelled` |
| `awaiting_review` | `done`, `failed`, `cancelled` |
| `done` | - (terminal) |
| `failed` | - (terminal) |
| `cancelled` | - (terminal) |

Enforced by `LEGAL_TRANSITIONS` dict in `gateway/builder_queue.py:69-80`. Illegal transitions raise `IllegalTransitionError`.

## Run Lifecycle

Each execution attempt creates a run row. Runs have their own state machine independent of task state.

### Run States

| State | Meaning |
|---|---|
| `starting` | Run row created, worker process not yet spawned |
| `running` | Worker process active, lease heartbeat renewing |
| `cancel_requested` | Cancellation signal sent to worker |
| `exited` | Worker exited successfully (exit code 0) |
| `failed` | Worker exited with non-zero code |
| `timeout` | Worker exceeded time budget |
| `cancelled` | Worker acknowledged cancellation |
| `interrupted` | Worker process terminated (SIGTERM/SIGKILL or crash) |
| `lease_lost` | Heartbeat lease expired — worker likely dead |
| `scope_violation` | Worker attempted forbidden operation |

Terminal run states: `exited`, `failed`, `timeout`, `cancelled`, `interrupted`, `lease_lost`, `scope_violation`.

### Run Transitions

| From | To (allowed) |
|---|---|
| `starting` | `running`, `cancel_requested`, `exited`, `failed`, `cancelled`, `interrupted`, `lease_lost` |
| `running` | `cancel_requested`, `exited`, `failed`, `timeout`, `cancelled`, `interrupted`, `lease_lost`, `scope_violation` |
| `cancel_requested` | `running`, `cancelled`, `interrupted`, `lease_lost`, `scope_violation` |

Enforced by `RUN_TRANSITIONS` dict in `gateway/builder_queue.py:243-273`.

## Attempt Lifecycle

Each packet may have multiple attempts (KB-S2). Attempts are tracked via the attempts table.

### Attempt States

| State | Meaning | Counts toward budget |
|---|---|---|
| `pending` | Attempt record created, not yet started | No |
| `running` | Worker actively executing this attempt | Yes |
| `completed` | Implementation finished, validation passed, review approved | Yes |
| `failed` | Implementation, validation, or review rejected | Yes |
| `crashed` | Worker process died — infrastructure failure, not code failure | No |

### Attempt Verdict

An attempt succeeds when ALL of:
1. Implementation status is `completed`
2. Validation verdict is not `failed`
3. If review is configured, review verdict is `approve`

Failure triggers retry up to `policy.max_attempts`. Crashed attempts are budget-neutral — they do not count toward exhaustion.

## Invariants

1. A task must be `claimed` before any attempt can start.
2. A task can only be in one of the legal states at any time.
3. Transitioning to a terminal state (`done`, `failed`, `cancelled`) is irreversible.
4. Each run must have exactly one terminal state reachable from its current state.
5. Crashed attempts must never count toward the attempt budget.
6. The worktree and log survive after failure/interruption for inspection.
7. Shadow mode: no push, no PR, no GitHub mutation during attempt execution (KB-S3b).
8. Operator release (`blocked` → `queued`) between retry attempts.

## Recovery Paths

| Scenario | Recovery |
|---|---|
| Worker crash mid-execution | `builder_loop._reconcile_stale_attempts()` detects open attempts, closes as `crashed` |
| Lease lost (heartbeat timeout) | Run transitions to `lease_lost`, task to `blocked(stale_heartbeat)` |
| Attempt exhaustion | Task transitions to `failed` |
| Infrastructure failure | Task transitions to `blocked`. Operator may release → `queued` for retry |
| Interrupted run | Run transitions to `interrupted`. Task → `blocked`. Worktree preserved for inspection |

## Escalation

Current implementation: no programmatic escalation. When a packet fails or an attempt cannot recover:

- Task transitions to `blocked` with a machine-readable reason
- Operator (human or KB-S4) decides next action
- Escalation to architectural decision-making is not automated

Future: the `BUILDER_OPERATING_MODEL.md` defines escalation as "STOP. Collect evidence. Escalate." This maps to a `blocked` task with evidence in the run manifest, awaiting operator judgment.
