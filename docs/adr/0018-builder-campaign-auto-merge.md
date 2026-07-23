# ADR 0018: Evidence-Gated Auto-Merge for Builder Campaign Work

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owner:** Jacob
- **Supersedes:** the "human merges every PR" default described in
  `docs/PROJECT_STATUS.md` and KB-S4's shadow-mode framing, scoped strictly
  to campaign work executed under
  `docs/plans/KITTYBUILDER_DAILY_DRIVER_PLAN.md`.

## Context

KittyBuilder's `queue publish` opens/updates a PR and stops: a human merges.
For daily-driver campaign use (§0 of the daily-driver plan) this makes Jacob
the bottleneck on every packet in every initiative — the opposite of the
"Jacob reads reports" goal the plan sets out to achieve. The first draft of
the plan argued to keep human merge, reasoning that Jacob is "unreliable at
best" as a live gatekeeper. Jacob overruled that in the 2026-07-21 planning
session: a gate whose gatekeeper routinely doesn't show up isn't a gate, it's
a stall.

## Decision

Campaign packets merge automatically once they clear an evidence gate, with
an automatic safety net if the gate turns out to be wrong:

1. **Evidence gate before merge** (all required): the packet's declared
   `validation_commands` passed, the independent reviewer's verdict was
   `approve`, and scope enforcement reported no violations. This is exactly
   what "packet succeeded" already means in the KB-S3b/S4b pipeline — no new
   judgment is invented here.
2. **Merge**: `gh pr merge` on the packet's PR (`gateway/builder_publish.py`,
   `merge_and_verify`).
3. **Post-merge revalidation**: the same `validation_commands` re-run against
   fresh `main` in an isolated worktree — independent proof, not a re-read of
   the pre-merge claim.
4. **Auto-revert on red**: if revalidation fails, the merge commit is
   reverted on `main` immediately and pushed. The archive's rule, applied
   verbatim: never hotfix on main after a failed post-merge check. The
   initiative pauses `needs_decision`.
5. **Tripwire**: if ≥ 2 of the last 10 auto-merges (globally, not
   per-initiative) reverted, auto-merge disables itself — subsequent packets
   park at `awaiting_review` for a human, same as pre-ADR-0018 behavior. No
   reset command: it is stateless, so it re-enables itself once enough clean
   merges age the old reverts out of the window.
6. **Escape hatch**: `initiative run --gate manual` restores full
   park-and-wait for any campaign Jacob wants to eyeball by hand.
7. **Amendment (2026-07-23, docs/LEARNINGS.md L-CAND-15):** on a first merge
   failure, `merge_and_verify` rebases the packet's own branch onto fresh
   `main` in an isolated worktree and force-pushes (`--force-with-lease`)
   only if the rebase is clean, then retries the merge once. A rebase that
   itself conflicts is never force-pushed — the original merge error
   propagates for a human to resolve. This closes the gap where a sibling
   packet's earlier auto-merge advances `main` and leaves the next packet's
   branch stale, most reliably colliding on `.claude/STATE.md` since every
   worker convention-writes there.

## What did not change

The excluded-operations list stays hard for `main` and any human branch:
secrets/auth/.env, data deletion, and history rewrite remain outside this
path entirely. The one narrow exception (item 7 above) is force-pushing a
Builder-owned packet branch — single-purpose, disposable, never touched
again after merge — and only after a clean rebase; `main` itself is never
force-pushed or rewritten. Shadow workers still never gain GitHub
credentials; only the operator-context merge/publish path
(`gateway/builder_publish.py`) touches `gh`/git remotes, same as
pre-existing publish.

## Consequences

- **Accepted risk:** an evidence gate only proves what the validation
  commands test. A green-but-wrong feature can now land on `main` instead of
  parking in a PR. Mitigations: this is a local-first single-user repo (blast
  radius = Jacob's own checkout, fully revertible), every merge is visible
  same-day in the CP-05 campaign report, and the prototype-gate convention
  (`docs/CAMPAIGN_PLAYBOOK.md`) exists precisely to catch wrong-direction
  work before the full build, not after.
- **Scope:** this ADR authorizes auto-merge only for Builder campaign
  branches under the daily-driver plan's execution contract. It does not
  loosen `CLAUDE.md`'s general push-approval rule for any other work.
- CLAUDE.md's "pushing requires explicit approval" line is updated to note
  this carve-out (see that file's Non-Negotiables §4).

## Revisit trigger

If the tripwire fires more than once in a month of real use, or a reverted
merge ever needed a hotfix instead of a clean revert, re-litigate this
decision with real data before continuing.
