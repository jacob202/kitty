# Discord Command Center Phase 1: bounded tasks and cancellation

## Outcome

Make the live Command Center safer to operate under repeated use while keeping
Discord as a thin slash-command surface and KittyBuilder as the execution
authority. The first slice adds bounded admission, an in-memory task registry,
and slash-only cancellation/status without enabling `MESSAGE_CONTENT`.

## Approaches considered

### A — Controller-local task registry (recommended)

Keep the existing `VibeService` read-only worker contract and add a small
registry at the Discord controller boundary. Register the current interaction
task after private-thread membership succeeds; cancellation calls
`asyncio.Task.cancel()`, allowing the existing service cleanup path to terminate
the worker and audit/remove its disposable worktree.

This is the smallest safe seam and preserves the already-proven Phase 0
service tests. It is intentionally process-local: a bot restart loses only
in-flight visibility, not repository authority, because every worker remains
disposable and audited.

### B — Durable task queue

Persist requests and task states in SQLite, then resume/reconcile after restart.
This would improve restart recovery, but introduces durable authority, schema
migrations, replay rules, and a second state machine before the Phase 1
control surface needs them.

### C — Builder/Gateway delegation

Hand requests to KittyBuilder immediately and expose Builder status in Discord.
This is the eventual expansion seam, but it would cross the explicit Phase 0
boundary and require an approved Gateway contract, spend policy, and evidence
projection first.

## Architecture

- `CommandCenterConfig` gains positive `max_concurrent_runs` and
  `max_runs_per_user` settings, defaulting to 2 and 1.
- `TaskRegistry` owns short-lived reservations and registered asyncio tasks.
  It indexes tasks by opaque task ID, owner ID, and private thread ID. It never
  stores request text, tokens, or worker output.
- `VibeController.handle` admits before creating a thread, registers the
  current interaction task after membership succeeds, and releases the
  reservation on every exit path.
- `VibeController.cancel` exposes owner-only `/vibe-cancel`; it resolves by
  explicit task ID or current private-thread ID and cancels the registered
  interaction task.
- `VibeController.status` exposes owner-only `/vibe-status`; it reports bounded
  task metadata ephemerally and never includes request text.
- `create_bot` registers the two additional guild-scoped slash commands. The
  bot continues to request only the `guilds` gateway intent.

## Data flow

1. `/vibe request` defers and passes authorization/channel checks.
2. Registry reserves capacity. A full global or per-user limit returns an
   ephemeral rejection before thread creation.
3. The controller creates the private thread, adds the requester, registers
   the current interaction task, and exposes only the opaque task ID.
4. The existing service runs unchanged: isolated worktree, bounded subprocess,
   sandbox, audit, and explicit cleanup.
5. `/vibe-cancel` cancels the registered task. Service cancellation cleanup
   runs first; the controller then writes a visible cancelled terminal card.
6. Normal completion/failure also unregisters the task and releases capacity.

## Error handling and security

- Admission failures are visible and do not create threads or workers.
- Unknown, non-owner, completed, or stale task IDs fail closed with an
  ephemeral message.
- Cancellation is idempotent at the command boundary: a task that is already
  finished is reported as no longer active.
- Registry cleanup is in `finally` blocks; registry metadata is bounded by the
  concurrency limit and contains no secrets.
- Discord messages remain bounded and scrubbed. No message-content listener,
  persistent queue, retry loop, or Builder call is added.
- Cancellation remains best-effort at the Discord UI but strict in the worker:
  the service's existing process-group termination and audit logic remains the
  source of truth.

## Testing

- Configuration accepts valid limits and rejects zero/negative values.
- Registry admits up to the global/per-user limits, releases reservations, and
  resolves owner/thread/task identity correctly.
- Controller rejects saturated admission before `create_thread`.
- Controller cancellation cancels the registered task, posts a cancelled
  terminal state, and releases capacity.
- Status exposes only bounded metadata and is owner-only.
- Existing Phase 0 suite remains green; run Ruff/mypy and a real `/vibe request
  ping` after deployment.

## Grill

- Weakest assumption: in-memory task visibility is acceptable across a single
  bot process. If restarts become common, Phase 2 should add reconciliation,
  but not silently pretend in-flight tasks survive today.
- Main edge case: cancellation racing with a terminal event. The controller
  must make the terminal card update best-effort and release the registry
  exactly once.
- Simpler cut: ship bounded admission plus cancellation first; status is tiny
  because it reuses the same registry and prevents operators from guessing
  whether a task is still consuming a slot.

## Zoom-out decision

GO. This is the smallest shippable hardening/optimization/expansion slice. It
does not change the worker security boundary, enable privileged Discord
intents, or create a parallel Builder authority.
