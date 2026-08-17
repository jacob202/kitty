---
name: campaign-resume
description: Re-derive position in a killed campaign, prove the ledger isn't lying, then continue
---

# Campaign resume

Campaign: `$ARGUMENTS` (slug; omit to use `current`, or run `list` first)

The last session was killed — usage limit, crash, or API error. Do not
reconstruct context by re-reading the conversation or re-investigating the
codebase. The ledger already knows. Trust it only after it proves itself.

## 1. Prove the ledger before believing it — do this first, always

```bash
venv/bin/python3.12 scripts/campaign.py list
venv/bin/python3.12 scripts/campaign.py --slug <slug> resume
```

`resume` prints the 10-line where-we-are summary, then:

- re-runs the **last verified phase's own command** to confirm the ledger is
  still true right now,
- checks every `verified` row against real git objects,
- reports uncommitted WIP and the worktree count.

**Exit 0** — the ledger is honest. Continue at the phase shown as `NEXT`.

**Exit 1** — NOT DONE. Something is wrong, and it is one of three things:

| Printed | Means | Do this |
|---|---|---|
| `LEDGER LIES — ... command fails now` | A phase claims verified but no longer passes; someone else changed the tree, or it was never true | Treat that phase as `in-progress` and redo it. Tell Jacob which phase and why. |
| `LEDGER LIES — verified phases with no such commit` | A status was hand-edited, or its commit was lost to a rebase/reset | Redo the phase. Do not re-add the SHA by hand. |
| `UNCOMMITTED WIP` | The previous session died mid-phase | See step 2. |

## 2. Handle mid-phase WIP before anything else

Uncommitted changes from a killed session are the highest-risk state in the
repo — the next agent's `git checkout` or another lane's reset destroys them.

1. `git status --short` and `git diff` to see what is actually there.
2. Decide, and say which you chose: the WIP is either **worth keeping** (commit
   it on the campaign branch with a `wip:` scoped message, then continue the
   phase) or **garbage** (state that plainly and `git stash` it — never
   `checkout --` it away; stash is reversible, discard is not).
3. Re-run `resume` and confirm exit 0 before starting new work.

## 3. Check nobody else is in this checkout

```bash
git worktree list
git log --oneline -8
```

If commits appeared that this campaign did not make, another lane or session is
writing to the same branch. Say so in one line before continuing — that
collision is how ledgers become false.

## 4. Then continue

Pick up at `NEXT`. Same loop as `/campaign-start` step 3: work, commit, then
`verify <n>`. Ledger committed after every phase, never batched.

If a limit looks close, `campaign.py --slug <slug> handoff` and stop. Finishing
the handoff beats starting a phase you cannot finish.
