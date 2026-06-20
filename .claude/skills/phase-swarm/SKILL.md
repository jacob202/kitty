---
name: phase-swarm
description: Dispatch parallel subagents to build independent Kitty phases concurrently. Triggers on "run phases N M K in parallel", "swarm phases", "parallel phase build".
argument-hint: "<phase-numbers e.g. 12 13 14>"
allowed-tools:
  - Read
  - Bash(git status)
  - Bash(git log *)
  - Bash(git worktree *)
  - Bash(git branch *)
  - Bash(python3* -m pytest*)
  - Bash(cat *)
  - Bash(ls *)
---

# Phase Swarm

Builds multiple independent Kitty phases concurrently using isolated worktrees.
Each phase gets its own agent; a coordinator merges in gate order.

## Prerequisites

Phases must be independent — no phase N+1 depending on N's output unless you
want sequential not parallel. Verify this before launching.

## Protocol

### Coordinator (you)

1. Parse `$ARGUMENTS` into a list of phase numbers
2. For each phase N, create a worktree:
   ```bash
   git worktree add worktrees/phase-$N -b phase-$N-swarm
   ```
3. Write a `.kitty/swarm-status.json`:
   ```json
   {
     "phases": {"12": "pending", "13": "pending", "14": "pending"},
     "started_at": "2026-06-20T...",
     "base_sha": "<current HEAD SHA>"
   }
   ```
4. Dispatch one Agent per phase with this contract:
   - Prompt: "Build Kitty phase $N in worktree `worktrees/phase-$N`. Read `docs/PHASE_B_PLAN.md` for task list. Gate: all tasks done + pytest passes + clean commit. Write your test count to `.kitty/swarm-status.json` at key `phase_$N_tests` when done. Mark your phase `done` in the same file."
   - Working directory: `worktrees/phase-$N`
   - Allowed tools: Read, Edit, Write, Bash(python3* -m pytest*), Bash(git *)
5. Monitor `.kitty/swarm-status.json` — poll after each agent completes
6. When a phase agent finishes:
   - Verify its gate: pytest green, commit clean
   - If red: record the failure, skip it in the merge queue
7. Merge green phases into main **sequentially** (never octopus), in phase number order:
   ```bash
   git merge --no-ff phase-$N-swarm -m "feat(phase-$N): swarm merge"
   ```
8. After each merge: run full pytest on main. If red, revert that merge and stop
9. Clean up merged worktrees:
   ```bash
   git worktree remove worktrees/phase-$N
   git branch -d phase-$N-swarm
   ```
10. Report: phases merged, test delta, any failures left for manual resolution

## Rules

- Never octopus-merge — one phase at a time
- Never merge a phase that didn't pass its gate
- If two phases touch the same file, expect a merge conflict — resolve by intent,
  not by splicing diffs; escalate to user if ambiguous
- Worktrees share the object store but have independent working trees — don't
  `cd` between them, use explicit paths
- Stateful resources (ports, SQLite files, shared `data/`) contend across
  worktrees: prefer separate test databases per worktree
  (`KITTY_DB_FILE=.kitty/test-phase-$N.db pytest ...`)
