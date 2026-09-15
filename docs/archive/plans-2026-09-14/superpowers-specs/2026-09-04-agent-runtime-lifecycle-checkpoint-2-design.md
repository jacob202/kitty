# Agent Runtime Lifecycle Checkpoint 2 Design

## Goal

Bind every Builder worker launch to one durable run identity that owns its authenticated worktree identity and its complete KX semantic claim set for the lifetime of the run.

A worker must not start unless all of these are true at the same time:

1. the Builder task lease is live and fenced;
2. the run has a creation-time authenticated worktree identity;
3. every allowed mutation path resolves to registered KX semantic resources;
4. the entire required KX resource set is acquired atomically for that run;
5. the worktree still matches the persisted identity immediately before launch.

## Scope

This checkpoint changes the existing Builder execution path. It does not add autonomous dispatch, new scheduling policy, GAR orchestration, a new coordination daemon, or a second claim store.

Primary code surfaces:
- `gateway/builder_runner.py`
- `gateway/run_workspace.py`
- `gateway/agent_coordination.py`
- Builder run persistence/schema modules as needed
- focused tests for run workspace, Builder runner, and KX coordination

The existing queue lease remains scheduling ownership. KX remains semantic mutation ownership. The new run binding coordinates them without merging the two concepts.
## Durable Run Binding

Builder currently creates the queue run only after the task lease and worktree already exist. Checkpoint 2 makes the durable run identity available before worker launch and associates it with:

- task ID, queue lease token/version, worker identity;
- branch and base SHA;
- worktree path;
- persisted `WorktreeIdentity` fields sufficient to verify the same Git metadata later;
- sorted required KX resource IDs;
- KX session ID, equal to or derived deterministically from the durable run ID.

The persisted identity is evidence, not a rediscovery hint. Later verification compares live Git metadata to the persisted creation-time values and fails closed on mismatch.

## Worktree Authentication

`run_workspace` gains a serializable creation/authentication seam for existing Builder worktrees rather than relying on `GitWorktreeManager`'s in-memory `_authenticated` dictionary.

Builder may keep its deterministic task worktree layout. Immediately after `ensure_worktree`, it authenticates that exact worktree against the controlling repository and base commit, persists the identity with the run, and re-verifies it before spawn and during final audit.

Replacing the directory, changing its Git metadata, switching it to a different repository/worktree registration, or moving HEAD outside the recorded base ancestry must stop the run before mutation continues.
## Atomic KX Acquisition

KX gains an atomic multi-resource acquisition operation. It accepts one session/run identity plus the complete sorted resource set and declared path fence, opens one `BEGIN IMMEDIATE` transaction, expires stale claims, verifies every requested mutating resource is available, and inserts all claims or none.

If any resource conflicts, the transaction inserts zero claims and returns the conflicting holder(s). Partial ownership is never externally visible.

Builder resolves `task.allowed_paths` through the tracked registry before launch. A declared mutation path that resolves to no semantic resource is a setup failure. Paths that resolve to multiple resources require all of them.

The Builder worker receives the durable run/KX session identity in runner-owned environment variables. It cannot choose or replace that identity.

## Lease and Claim Lifetime

The existing Builder heartbeat renews both trust domains in one control-loop iteration:

- renew the queue lease;
- renew the KX claims for the same run identity;
- record the run heartbeat only after both renewals succeed.

Failure to renew either ownership stops the worker. KX loss is treated as lost mutation authority, not a recoverable warning.

All terminal and prelaunch failure paths release KX claims deterministically. Release is idempotent so cleanup can be retried safely. Crash recovery still relies on expiry as the final safety net.
## Error Handling

Prelaunch failures occur before `Popen` and must leave no live KX claims. If a durable run row already exists, it is finalized with a machine-readable setup failure and includes the ownership/worktree failure in its report.

If KX ownership is lost after launch, Builder terminates the process group, records a lost-authority outcome, avoids claiming successful completion, and releases whatever ownership remains.

GAR remains projection-only. A GAR post failure must not create or revoke ownership and must not turn a database success into a database failure.

## Acceptance Tests

1. Atomic acquisition: two resources requested while one is owned produces conflict and zero new active claims for the losing run.
2. Atomic acquisition race: independent processes requesting overlapping multi-resource sets cannot both win the shared resource.
3. Unregistered allowed path: Builder fails before worker launch and releases its queue lease/KX state.
4. Identity persistence: Builder records creation-time worktree identity with the run and reuses that exact persisted identity for verification.
5. Worktree replacement/tampering: changing registration or Git identity after authentication prevents worker launch or terminates the live run at the next verification point.
6. Launch ordering: test instrumentation proves `Popen` is unreachable until queue lease, durable run, worktree authentication, resource resolution, and full KX acquisition have succeeded.
7. Heartbeat coupling: KX renewal failure terminates the worker and does not record a successful run heartbeat afterward.
8. Cleanup: normal exit, failure, timeout, cancellation, setup failure, and launch failure leave zero active KX claims for the run.
9. Existing checkpoint-1 containment, Builder-loop, Discord Command Center, and KX acceptance suites remain green.

## Definition of Done

A real Builder run cannot mutate unless its queue lease, persisted worktree identity, and complete KX resource set all name the same durable run and remain live. There is no partial KX acquisition path, no audit-time-only worktree identity fallback on the Builder launch path, and no worker process starts before ownership is established.
