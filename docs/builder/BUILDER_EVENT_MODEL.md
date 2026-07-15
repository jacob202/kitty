---
type: specification
title: "Builder Event Model"
status: canonical
owner: jacob
primary_purpose: Every event produced by the Builder runtime — producer, consumers, payload, ordering, idempotency
derives_from:
  - docs/builder/BUILDER_PACKET_LIFECYCLE.md
  - docs/builder/BUILDER_EXECUTION_PIPELINE.md
implements:
  - gateway/builder_queue.py
review_cycle: quarterly
---

# Builder Event Model

Every event produced by the Builder runtime. Events are stored in the append-only `events` table in `builder_queue.db`. UPDATE and DELETE on the events table are blocked by triggers.

## Event Architecture

- **Storage**: SQLite `events` table in `BUILDER_QUEUE_DB`
- **Schema**: `(id, task_id, run_id, event_type, payload, created_at)`
- **Append-only**: Triggers block UPDATE/DELETE
- **No transport**: Events are queried directly from SQLite. No message queue, no pub/sub.

## Event Reference

### Task Events

#### `created`

| Field | Value |
|---|---|
| Producer | `builder_queue.create_task()` |
| Pipeline stage | Initiative application (pre-pipeline) |
| Trigger | Task row inserted |
| Payload | `{title, description, priority, initiative_id, packet_id, external_id}` |
| Consumers | Operator CLI (`--brief`), initiative status rollup |
| Ordering | Single row insert per task |
| Idempotency | One event per create_task call |
| Persistence | Durable in events table |

#### `claimed`

| Field | Value |
|---|---|
| Producer | `builder_queue.claim_task()` |
| Pipeline stage | Receive Packet (§1) |
| Trigger | Worker claims task via lease |
| Payload | `{lease_owner, lease_expires_at}` |
| Consumers | Operator CLI, lease recovery scan |
| Ordering | Per claim attempt |
| Idempotency | Multiple claims possible over task lifetime |
| Persistence | Durable |

#### `released`

| Field | Value |
|---|---|
| Producer | `builder_queue.release_task()` |
| Pipeline stage | Between repair retries; operator release from blocked |
| Trigger | Worker releases claim (to `queued`) or operator releases blocked task |
| Payload | `{reason}` |
| Consumers | Queue scheduler, initiative status |
| Ordering | Per release |
| Idempotency | Multiple releases possible |
| Persistence | Durable |

#### `operator_released`

| Field | Value |
|---|---|
| Producer | `builder_queue.operator_release_blocked_task()` |
| Pipeline stage | Post-execution operator action |
| Trigger | Operator manually releases `blocked` → `queued` |
| Payload | `{operator, reason}` |
| Consumers | CLI, initiative status |
| Ordering | Per operator action |
| Idempotency | Idempotent per release |
| Persistence | Durable |

#### `report_attached`

| Field | Value |
|---|---|
| Producer | `builder_queue.attach_run_report()` |
| Pipeline stage | Validate Output / Review (§7-8) — after attempt verdict computed |
| Trigger | Run report attached to task (worker exit) |
| Payload | `{attempt_id, attempt_no, exit_code, implementation_status, validation_verdict, review_verdict, failure, evidence}` |
| Consumers | Operator (`--brief`), initiative evidence rollup |
| Ordering | One per attempt completion |
| Idempotency | Idempotent by attempt_no + task_id |
| Persistence | Durable |

#### `pr_attached`

| Field | Value |
|---|---|
| Producer | `builder_queue.upsert_pr_link()` |
| Trigger | PR link attached to task (KB-S4) |
| Payload | `{pr_number, head_branch, base_branch, commit_sha}` |
| Consumers | Operator CLI, PR status sync |
| Ordering | One per PR attachment |
| Idempotency | Upsert by PR number |
| Persistence | Durable |

#### `pr_updated`

| Field | Value |
|---|---|
| Producer | `builder_queue.upsert_pr_link()` |
| Trigger | Existing PR link updated (checks state, review state change) |
| Payload | `{pr_number, checks_state, review_state}` |
| Consumers | Operator CLI |
| Ordering | Per update |
| Idempotency | Idempotent by PR number |
| Persistence | Durable |

### Run Events

Run state transitions are recorded as events with `event_type` equal to the new run state. Run events are produced during pipeline stage §6 (Execute Worker). Each transition appends an event row.

| Event Type | Producer | Trigger |
|---|---|---|
| `starting` | `builder_queue.start_run()` | Run row created |
| `running` | `builder_queue.transition_run()` | Worker process spawned |
| `exited` | `builder_queue.transition_run()` | Worker exit code 0 |
| `failed` | `builder_queue.transition_run()` | Worker exit code non-zero |
| `timeout` | `builder_queue.transition_run()` | Time budget exceeded |
| `cancelled` | `builder_queue.transition_run()` | Cancellation acknowledged |
| `interrupted` | `builder_queue.transition_run()` | Worker terminated by signal |
| `lease_lost` | `builder_queue.transition_run()` | Heartbeat lease expired |
| `scope_violation` | `builder_queue.transition_run()` | Forbidden operation attempted |

Each run event payload includes: `{previous_state, new_state, reason, run_id}`.

### Initiative Events

| Event Type | Producer | Trigger |
|---|---|---|
| `initiative_applied` | `builder_initiative.apply()` | Initiative manifest validated and applied |
| `initiative_status_changed` | `builder_initiative` status roller | Initiative transitions between active/paused/completed/failed |

## Event Consumption

| Consumer | How | Purpose |
|---|---|---|
| `__brief` (CLI) | `builder_brief.render()` reads last 10 events | Operator takeover context |
| `__queue events` (CLI) | `builder_queue.list_events()` | Full event history for a task |
| Initiative status | `builder_initiative` reads events table | Rolls up per-packet evidence into initiative status |
| Operator | CLI read-only commands | Human inspection, debugging, recovery decisions |

## Ordering Guarantees

- Events are ordered by `created_at` within a task.
- No global ordering across tasks — each task's events are independently ordered.
- Run events are interleaved with task events within the same task ID.

## Idempotency

- `created` events: idempotent by task `bridge_external_id` unique index.
- `report_attached`: idempotent by `attempt_no` within task.
- `pr_attached`/`pr_updated`: upsert by PR number.
- Run state transitions: each transition is a new event — successive transitions to the same state are allowed (e.g., `running` → `blocked` → `running`).

## Future Events (Not Implemented)

These events are defined by the architecture but not yet produced by the codebase:

| Event | Defined In | Status |
|---|---|---|
| `knowledge_candidate_created` | Knowledge Model | Future — no Knowledge Engine |
| `doctrine_candidate_raised` | Knowledge Model | Future |
| `packet_reflection_recorded` | Builder Operating Model | Future — reflection not automated |
| `escalation_triggered` | Builder Operating Model | Future — no programmatic escalation |
| `contract_validated` | Builder Execution Pipeline | Future — contract validation not evented |
