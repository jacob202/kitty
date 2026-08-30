# ADR 0018: Evidence-Gated Auto-Merge for Approved Builder Work

- **Status:** Accepted; amended 2026-07-26
- **Date:** 2026-07-21
- **Decision owner:** Jacob
- **Amended by:** ADR 0021

## Context

Stopping every successful Builder packet at a PR and waiting for Jacob to merge
makes him the bottleneck in a system intended to execute approved work
proactively. The correct gate is evidence, not Jacob's continuous presence.

The original decision applied only to campaigns under the Daily-Driver Plan.
ADR 0021 replaces that obsolete plan-specific scope with an approved-packet
policy.

## Decision

An explicitly approved Builder packet may merge automatically only when all of
the following hold:

1. Its declared validation commands passed and were runnable and falsifiable.
2. An independent reviewer approved the exact result SHA and diff.
3. Scope, identity, lease, and authority enforcement reported no violation.
4. The packet is classified low-risk under ADR 0021.
5. The target branch and required checks are current and green.

The publication sequence is:

1. Builder commits and pushes its single-purpose branch.
2. Builder opens or updates the packet PR and may mark it ready when the
   evidence record is complete.
3. The evidence gate is evaluated in operator context; workers do not receive
   GitHub credentials or approve themselves.
4. The PR is merged.
5. The same packet validation runs against fresh `main` in an isolated
   worktree.
6. If post-merge validation fails, the merge commit is reverted immediately.
   Do not hotfix `main`; pause the affected work with `needs_decision`.

## Tripwire

If at least two of the last ten auto-merges were reverted, auto-merge disables
itself and later packets park at `awaiting_review`. It re-enables only after the
reverts age out of the rolling window through clean reviewed merges.

## Stale-branch recovery

On the first merge failure caused by an advanced base, Builder may rebase its
own disposable packet branch onto fresh `main` and force-push with
`--force-with-lease` only when the rebase is clean. A conflict is never
force-pushed; it becomes a visible blocked decision. `main` is never
force-pushed or rewritten.

## Manual escape hatch

An approved run may explicitly use a manual gate. That parks every packet at
`awaiting_review` and performs no merge until an operator approves it.

## Excluded work

Auto-merge is unavailable for the exclusions in ADR 0021, including dependency
or lockfile changes, CI workflows, auth or secrets, security boundaries,
destructive operations, data/schema migrations without separate approval,
human-judgment UI work, path collisions, unverifiable gates, or scope
expansion.

Excluded packets may still be implemented, committed, pushed, and opened as
draft PRs when their approved policy allows it. They stop before merge.

## Consequences

- Jacob approves objectives, scope, risk, and policy rather than every routine
  Git transition.
- A green-but-wrong change remains possible only to the extent the declared
  evidence is incomplete; falsifiable gates, independent review, post-merge
  validation, auto-revert, and the tripwire constrain that risk.
- This is a standing Builder-path authorization, not a general exemption for
  interactive agents or human branches.
- Every automatic decision is durable, attributable, visible in the run report,
  and revertible.

## Revisit trigger

Revisit if the tripwire fires repeatedly, a revert requires a hotfix, or a
low-risk classification permits a change whose consequences were not safely
recoverable.
