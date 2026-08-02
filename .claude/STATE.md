# Session State — Builder packet B7-detached-execution-durable (attempt 4)

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-02T00:00:00Z",
  "head_sha": "df2d8b83ac3b3337f896949bf58398d0d20a1477",
  "branch": "kittybuilder/kb_msb4yx3n_4099",
  "worktree": "kittybuilder/kb_msb4yx3n_4099",
  "status": "in_progress",
  "completed_items": [
    "Added durable detached worker ownership to gateway/builder_runner.py (run_worker_detached, _supervise_worker, detached_worker_status, reap_detached_workers)",
    "Added focused detached-execution tests in tests/test_builder_runner.py (survival, reconnectable status, crash detection, orphan reaping)",
    "Validation command passes: 121 passed (116 original + 5 new)"
  ],
  "blockers": [],
  "next_action": "Await independent builder review of the detached-execution mechanism.",
  "parallel_work": [],
  "recommendations": [],
  "invalidation_conditions": [
    "HEAD changes beyond df2d8b83ac3b3337f896949bf58398d0d20a1477"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Execution ownership

- this session: builder (packet bundle kb_msb4yx3n_4099, attempt 4)
- task_bundle: `.kittybuilder-bundle-105.json`
- status: implementation complete, tests passing, awaiting independent review

## What was done

Implemented durable detached worker ownership in `gateway/builder_runner.py` so a
terminal disconnect or watcher death cannot strand a live worker:

- `run_worker_detached()` — spawns a detached supervisor process (own session)
  that owns the full `run_worker` lifecycle (claim, worktree, spawn, heartbeat,
  collect, finalize) and outlives the caller. Returns immediately.
- `_supervise_worker()` / `python -m gateway.builder_runner --supervise <spec>`
  — the detached supervisor entrypoint that runs the exact synchronous
  `run_worker` path and writes a durable completion status file.
- `detached_worker_status()` — reconnectable status surface distinguishing
  running / orphaned / crashed / starting / completed from the durable DB record
  + live process identity.
- `reap_detached_workers()` — reclaims orphaned worker process groups whose
  owner died (stale lease, still-alive worker), preventing orphan accumulation.

Added 5 focused tests covering the acceptance criteria.

## KB effectiveness

- no receipt recorded yet
