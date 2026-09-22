# Builder/GAR Narrow Suspension Decision — 2026-09-22

Status: approved operational experiment

## Decision

Suspend Builder as Kitty's default executor and suspend GAR as mandatory
lifecycle/recall infrastructure. Preserve both systems, their data, and their
history. Replace only the useful concurrency requirement with the smallest
local mechanism that proves sufficient.

This decision does **not** retire Kitty, delete Builder/GAR, adopt Jacob Core,
or ratify a replacement architecture.

## Why

- Builder produced real historical engineering value, but recent accepted
  delivery no longer justifies mandatory default execution machinery.
- GAR solved real coordination problems, but its room became dominated by
  machine-generated lifecycle/coordination traffic.
- direct specialist tools, Git/GitHub, and resumable agent sessions now cover
  much of the recall/execution need that originally justified mandatory use.
- GitHub already enforces PR/check/main protections remotely with no bypass.

## Suspension boundary

Normal Kitty work must:

- start from live Git/GitHub/runtime state;
- avoid automatic Builder scheduling/supervision;
- avoid GAR startup recall, SessionEnd posts, lifecycle receipts, and outboxes;
- avoid the non-safety Build-It Stop completion gate;
- retain secret/dangerous-command/evidence/pre-push protections;
- use a small local path claim for concurrent mutation safety.

Builder/GAR commands remain available for explicit audit, rollback, or
compatibility work.

## Local ownership mechanism

`scripts/work_claim.py` stores claims under the repository's Git common
directory, shared by linked worktrees.

It has no daemon, database, network protocol, or background heartbeat.

An active claim records owner, task, worktree, branch, path scopes, and explicit
expiry. Overlapping active scopes conflict. Non-overlapping claims are allowed.
Expired claims are visibly stale and may be reaped; stale claims do not block
a new owner.

The tracked pre-commit hook verifies that staged paths are covered by the
current worktree's active claim. This replaces the old database-backed
coordination preflight for ordinary commits.

Limitation: claims coordinate linked worktrees sharing one Git common directory.
Separate clones do not share this local state; GitHub remains the publication
collision boundary for those.

## Compatibility state

`.claude/STATE.md` and `.claude/HANDOFF.md` are preserved as historical
compatibility snapshots only. Normal `next`, `catchup`, startup, and closeout
must not use or rewrite them.

The broad retirement experiment remains parked at local commit `21951c5` and is
not part of this suspension.

## Machine-level Builder state

The macOS label `com.kitty.builder.supervisor` is disabled in launchd. The
plist/history are preserved.

Rollback requires an explicit decision. Re-enable the launchd override before
bootstrapping the preserved plist; do not treat Builder-down UI as an outage
while this suspension is active.

## Acceptance tests

The suspension is accepted only if:

1. normal sessions create no GAR lifecycle traffic;
2. Builder does not periodically wake while disabled;
3. ordinary turns finish without Build-It Stop bouncing them;
4. historical Builder/GAR evidence remains intact;
5. two linked worktrees can hold non-overlapping claims concurrently;
6. overlapping path ownership is rejected visibly;
7. expired ownership is recognizable and recoverable without archaeology;
8. staged mutation outside a worktree claim is blocked;
9. existing GitHub default-branch protections remain active.

If the tiny ownership mechanism fails the adversarial concurrency test, add
only the smallest missing behavior demonstrated by that failure. Do not rebuild
GAR by default.

## Out of scope

Constitution changes, Kitty platform retirement, Jacob Core adoption, memory
redesign, Discord cleanup, Mem0/Honcho cleanup, provider changes, UI redesign,
and deep Builder/GAR deletion are separate decisions.

## Verification on the suspension branch

- focused suspension/authority suite: `73 passed`;
- adversarial local-claim suite: overlap blocked, non-overlap allowed, stale
  claim visible/recoverable, staged-scope fence enforced, linked-worktree state
  shared;
- full default backend suite: `6222 passed, 1 skipped, 1 failed`, plus 29
  subtests passed;
- the sole failure is
  `tests/test_kittybuilder_dsh_runtime.py::test_dsh_worker_preserves_builder_result_contract`;
- that same DSH test fails identically on pristine `origin/main` at `ca5e5ac0`,
  so it is a pre-existing baseline failure rather than a suspension regression;
- Ruff: clean across gateway, tests, MCP, workers, standard smoke script, and
  `scripts/work_claim.py`;
- GitHub ruleset `20193076` is active on the default branch, requires PR plus
  `policy-gate` and `merge-gate`, has no bypass actors, and reports
  `current_user_can_bypass: never`;
- macOS launchd reports `com.kitty.builder.supervisor` disabled; the service is
  not loaded and no supervisor process is running;
- supervisor logs have not advanced since 2026-09-21 14:21:51 (stdout) and
  21:06:58 (stderr).
