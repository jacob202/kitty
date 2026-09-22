---
name: next
description: "Continue the current repo-aware assignment from conversation and verified live state. USE WHEN the user says next, continue, resume, keep going, or do the next thing."
---

# Next — Continue the Current Assignment

A bare continuation resumes only the assignment already established by the
conversation and verified repository/runtime state. It never selects Builder
work, drains a queue, or invents a replacement task.

## 1. Re-establish live state

Read the minimum evidence needed:

```bash
git status --short --branch
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git worktree list --porcelain
python3 scripts/work_claim.py status
```

Inherited prose is a hint only. Current Git/GitHub/runtime evidence wins.
Do not query GAR, STATE.md, HANDOFF.md, or Builder merely to discover work.

## 2. Resolve what to continue

Use this order:

1. the explicit assignment in the current conversation;
2. verified in-flight work on the current branch/worktree that clearly belongs
   to that assignment;
3. a concrete recovery/review action required to finish that assignment;
4. an explicit no-op if no valid assignment exists.

Do not substitute roadmap work, old handoffs, dormant Builder packets, or
another worker's branch because they look useful.

## 3. Own the mutation explicitly

Before editing, acquire or confirm a local claim that covers the intended paths:

```bash
python3 scripts/work_claim.py claim --owner <id> --task <task> --path <scope>
```

If another active claim overlaps, stop that mutation and reconcile ownership.
Non-overlapping claims may proceed in parallel. Never kill, clean, move, or
delete work you did not create.

## 4. Finish the bounded assignment

Implement/investigate/review the requested work, run the narrowest meaningful
verification, and preserve unrelated work. A green test is evidence, not proof
of an unrelated user outcome.

When complete, release the claim if it is safe to do so:

```bash
python3 scripts/work_claim.py release
```

Then report the verified result and stop. No mandatory session-end, GAR post,
KB receipt, STATE/HANDOFF rewrite, or new assignment follows completion.
