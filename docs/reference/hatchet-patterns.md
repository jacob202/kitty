# Hatchet API Pattern Study

**Date:** 2026-07-14
**Status:** Reference — study only, do not adopt Hatchet
**Source:** [hatchet-dev/hatchet](https://github.com/hatchet-dev/hatchet) (7.5k stars, MIT, Go+Python+TS)

## Purpose

Hatchet is the closest mature reference to KittyBuilder's queue subsystem. This
document identifies which Hatchet design patterns KittyBuilder already implements,
which it should adopt, and which it should deliberately diverge from.

## Architecture Comparison

| Concept | KittyBuilder | Hatchet |
|---|---|---|
| **Durability layer** | SQLite via `builder_queue.py` | Postgres |
| **Task creation** | `create_task(title, ...)` | `client.admin.put_workflow()` or `client.task.create()` |
| **Worker claim** | `claim_task(task_id, worker_id)` with lease token | Workers pull from queue; assignment is server-driven |
| **State machine** | QUEUED→CLAIMED→RUNNING→BLOCKED→PR_OPENED→AWAITING_REVIEW→DONE | Workflow steps with built-in retry |
| **Lease fencing** | SHA-256 lease token + claim_version | Postgres row-level locks + heartbeat |
| **Heartbeat** | `renew_lease(task_id, token, version)` | Activity heartbeats with timeout |
| **Retry** | Manual via `builder_loop.py` repair loop | Built-in: max_retries, exponential backoff |
| **Observability** | Events table (append-only) | OpenTelemetry, Prometheus, web UI |
| **Isolation** | Git worktrees | Worker processes (any language) |

## Patterns KittyBuilder Already Implements Correctly

### 1. Append-only event log
KittyBuilder's `events` table with UPDATE/DELETE triggers blocked matches
Hatchet's event-sourcing approach. Both preserve full execution history.

### 2. Lease-based exclusivity
KittyBuilder's `lease_token` + `claim_version` pair provides the same
fencing guarantee as Hatchet's Postgres row locks. A stale worker cannot
mutate the task — enforced at the transition level, not the lock level.

### 3. Shadow mode execution
KittyBuilder's "no push, no PR, no GitHub mutation" shadow mode matches
Hatchet's idempotent workflow model — each attempt is self-contained and
observable.

### 4. Crash safety via heartbeats
KittyBuilder's `renew_lease` + `recover_expired_leases` matches Hatchet's
activity heartbeat pattern. If the runner process dies, the lease expires
and recovery reclaims the task.

## Patterns Worth Adopting

### 1. Exponential backoff for retries
**Current KittyBuilder:** Manual retry via `builder_loop.py` with fixed
`max_attempts`. No backoff between retries.
**Hatchet pattern:** Configurable `retry_policy` with `max_retries`,
`initial_interval`, `max_interval`, and `backoff_coefficient`.
**Recommendation:** Add an optional `retry_delay_seconds` to
`builder_attempt.py` with exponential backoff between attempt starts.
This is a small, low-risk addition that reduces operator intervention.

### 2. Step-level timeouts (vs global timeout)
**Current KittyBuilder:** Global `DEFAULT_TIMEOUT_SECONDS` (3600s)
for the entire worker run.
**Hatchet pattern:** Per-activity timeouts: `timeout_seconds` on each
step, with `schedule_to_close_timeout` and `start_to_close_timeout`.
**Recommendation:** Add per-validation-command timeouts in the
packet contract. A packet could specify `"validation": {"command": "...", "timeout": 120}`
to bound individual validation steps.

### 3. Workflow visualization
**Current KittyBuilder:** Queue status text via `./kitty builder queue status`.
**Hatchet pattern:** Real-time web UI with DAG visualization, log streaming,
and alerting.
**Recommendation:** Low priority for single-user local use. If the Builder
queue grows beyond ~50 concurrent tasks, consider a simple HTML status
page served from the gateway.

## Patterns KittyBuilder Should Deliberately Diverge From

### 1. Server-driven worker pull
Hatchet's server assigns tasks to workers (push model). KittyBuilder's
workers claim tasks (pull model). **Keep the pull model** — it's simpler
for a single-user system and avoids the need for a persistent worker registry.

### 2. Multi-tenant routing
Hatchet supports tenant isolation, user roles, and team-level routing.
KittyBuilder is single-user. **Do not add multi-tenancy** — it would be
premature complexity.

### 3. Separate observability infra
Hatchet runs a separate monitoring stack (Prometheus, web UI). KittyBuilder's
`events` table + `observability.py` JSONL are adequate. **Do not add a
separate observability service** — extend the doctor CLI instead.

## Concrete Queue API Improvements

Based on the Hatchet comparison, three improvements to `builder_queue.py`:

1. **`create_task` should return just the ID**
   Currently returns the full task dict. Most callers only need the ID.
   Add a `create_task_id()` convenience wrapper.

2. **`claim_task` should accept an optional `lease_seconds` per task type**
   Currently hardcoded at 1800s. Short tasks (lint checks) don't need
   30-minute leases. Allow the packet to specify `lease_seconds` in its
   contract.

3. **Add `attempt_delay_seconds` to the attempt policy**
   The attempt record (`builder_attempt.py`) should include a delay
   before the next retry: 0s for first retry, then exponential.

## Verdict

KittyBuilder's queue is well-designed for its use case (single-user,
local-first, SQLite-backed). Hatchet's patterns are most valuable for:

- **Retry policies** — adopt exponential backoff
- **Per-step timeouts** — adopt bounded validation timeouts
- **API ergonomics** — study Hatchet's Python SDK for cleaner function signatures

Do not adopt Hatchet as a dependency. The SQLite queue is simpler, has fewer
moving parts, and better fits Kitty's local-first model. The patterns above
can be implemented incrementally without architectural changes.
