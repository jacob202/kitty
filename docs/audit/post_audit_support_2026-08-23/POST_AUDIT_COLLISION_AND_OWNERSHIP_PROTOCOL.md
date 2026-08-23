# Kitty Post-Audit Collision + Ownership Protocol

Purpose: prevent duplicate implementation, stale-base work, and agents modifying the wrong Kitty authority after the audit.

This protocol is execution infrastructure only. It does not decide which audit findings are valid or what must be fixed.

## Non-negotiable rule

Before touching a finding, establish CURRENT repository truth. Never implement from remembered state, an old audit snapshot, or a copied prompt alone.

Every implementation lane must classify the target as one of:
- NEW
- ALREADY TRACKED
- IN FLIGHT
- FIXED ON CURRENT MAIN
- STALE / NOT REPRODUCIBLE
- DUPLICATE
- DESIGN QUESTION

If status is not NEW, do not code until the correct disposition is proven.

## Preflight evidence packet

Capture before every implementation chunk:
- exact `git rev-parse HEAD`
- current branch
- `git status --short`
- `git log -8 --oneline --decorate`
- relevant open PRs
- relevant open issues
- recently merged PRs touching the target files/subsystem
- local branches/worktrees touching target files where visible
- audit finding IDs being addressed
- canonical owner subsystem for the behavior
## Ownership check

Before coding, answer in writing:
1. What subsystem is authoritative for this behavior today?
2. Is there a legacy/compatibility implementation of the same behavior?
3. Which public route/UI calls the authoritative path?
4. Does an open PR already touch the same files or state machine?
5. Would this change invalidate another active lane?

If any answer is unclear, inspect before coding. Do not ask the user for repository facts that tools can establish.

## Collision decisions

NEW: proceed only after the audit's implementation order authorizes it.

ALREADY TRACKED: update/close/execute the existing issue rather than creating a duplicate lane.

IN FLIGHT: do not modify overlapping files. Review the active work or choose another authorized finding.

FIXED ON CURRENT MAIN: reproduce the audit failure against current main. If it no longer fails, mark resolved; do not reimplement.

STALE / NOT REPRODUCIBLE: preserve evidence and stop. Do not manufacture a cleanup PR.

DUPLICATE: consolidate under the strongest existing finding/issue and preserve aliases for traceability.

DESIGN QUESTION: require an explicit product/architecture decision before implementation.

## File-overlap gate

For the intended patch, list exact files before editing. Compare them against active branches/PRs. Same-subsystem state-machine changes count as a collision even when exact files differ.
## Patch-size rule

One implementation chunk should normally:
- address one coherent root cause;
- have one rollback story;
- have one acceptance proof;
- avoid unrelated cleanup;
- avoid speculative refactors.

Touching nearby code is not a reason to bundle another finding.

## Rebase / stale-base gate

Immediately before final verification:
- fetch current remote state;
- compare merge base with current main;
- inspect commits added to main since lane start;
- re-run overlap check;
- re-run the original reproduction.

If main has changed the target semantics, stop and reclassify rather than force-merging an obsolete patch.

## Merge readiness evidence

A patch is not merge-ready until it records:
- finding IDs addressed;
- exact failure reproduced before fix where feasible;
- regression test/equivalent proof;
- required focused tests;
- required broader tests;
- lint/type/build gates applicable to touched area;
- post-fix acceptance result;
- current-main collision check;
- rollback path;
- residual known risk.

## Hard stop conditions

Stop rather than code when: active work already owns the same semantics; authority is contradictory; reproduction fails on current main; fix requires broad architecture not approved by Chunk 11; or the change would touch an explicitly reserved lane such as active Image Lab work.
