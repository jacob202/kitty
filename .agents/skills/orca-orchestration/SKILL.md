# Orca Orchestration — Kitty Multi-Agent Workflows

Use when coordinating multiple agents through Orca for Kitty development: handoffs,
worktree handovers, phased/parallel work, or splitting changes into reviewable PRs.

## Preconditions

- Orca running: `orca status --json` returns `runtime: true`
- Kitty repo setup hook configured: `scripts/orca_worktree_setup.sh`
- Approval tiers: T0 auto, T1 separate model review, T2 Jacob (see `docs/KITTYBUILDER_ORCA_SETUP.md`)

---

## Pattern 1 — Hand Off an Active Task

Move ownership of in-progress work to another agent with full context.

```
# Sender: package state and send
orca orchestration send \
  --to @idle \
  --type handoff \
  --priority high \
  --subject "Continuing KX-05 chat polish sweep" \
  --body "$(cat <<CTX
Branch: fix/chat-polish-v2
Worktree: .worktrees/kittybuilder/kb_mrxxx
Current state: 3 of 7 changes committed, lint clean, 2 tests failing (StatusBar flapping)
Next step: fix StatusBar flapping — see gateway/kitty-chat/src/components/StatusBar.tsx:45
Context file: docs/packets/KX-05-chat-polish.md section 3
CTX
)" \
  --payload '{"branch":"fix/chat-polish-v2","head":"abc1234","tests":"2 failing / 19 total"}' \
  --json

# Receiver: read the handoff
orca orchestration check --types handoff --inject --json
```

Why: `--payload` carries machine-readable state. `--body` carries human context. `@idle` targets agents not working.

When a receiving agent picks up a handoff, it should confirm receipt:
```
orca orchestration reply --id <msg_id> --body "Picked up. Running tests now." --json
```

---

## Pattern 2 — Hand Off to Another Worktree

Pass work to an agent already running in a different branch/worktree.

```
# 1. List active terminals and their worktrees
orca terminal list --json

# 2. Target by worktree or handle
orca orchestration send \
  --to @worktree:kb_mrxwv3a0_8a2a \
  --type handoff \
  --priority high \
  --subject "Need code review on PR #229 diff" \
  --body "Branch fix/redact-github-token-trace is ready for T1 review. Diff is 3 files, 12 lines." \
  --json

# 3. Receiver (in target worktree): pull branch and review
git fetch origin fix/redact-github-token-trace
git diff origin/main...origin/fix/redact-github-token-trace
python3.12 -m pytest tests/ -q --tb=short
```

Why: `@worktree:<id>` resolves to all terminals in that worktree. Use for cross-branch coordination without leaving the current worktree.

---

## Pattern 3 — Run a Phased Workflow

Child agents one after another — each phase depends on the last's output.

```
# 1. Create DAG tasks (deps array creates the chain)
orca orchestration task-create \
  --spec "Phase 1: Audit all 7 surfaces for color-token drift against design-system" \
  --json
# → id: task_phase1

orca orchestration task-create \
  --spec "Phase 2: Apply color-token fixes from audit report" \
  --deps '["task_phase1"]' \
  --json
# → id: task_phase2

orca orchestration task-create \
  --spec "Phase 3: Run expert swarm review on fixed surfaces" \
  --deps '["task_phase2"]' \
  --json
# → id: task_phase3

# 2. Create a coordinator terminal
orca terminal create --worktree active --title "coordinator" --json
# → handle: term_coord

# 3. Start coordinator loop (auto-advances the DAG)
orca orchestration run \
  --spec "Kitty audit pipeline: audit → fix → review" \
  --from term_coord \
  --max-concurrent 1 \
  --poll-interval-ms 5000 \
  --json

# 4. Monitor (separate terminal)
orca orchestration task-list --json
orca orchestration check --wait --types worker_done,escalation --timeout-ms 300000 --json
```

Why: `--max-concurrent 1` enforces sequential execution. The coordinator auto-promotes task_phase2 when task_phase1 completes. Tasks stay `blocked` if a decision gate is created.

Insert a decision gate between phases for human oversight:
```
orca orchestration gate-create \
  --task task_phase1 \
  --question "Phase 1 audit found 14 color violations in 5 files. Apply fixes?" \
  --options '["Apply all fixes","Fix P0 only","Skip"]' \
  --json
```

---

## Pattern 4 — Run Independent Work in Parallel

Split non-overlapping tasks across child agents simultaneously.

```
# 1. Create independent tasks (no deps = parallelizable)
orca orchestration task-create --spec "Add tests for gateway/reasoning.py edge cases" --json
# → id: task_t1
orca orchestration task-create --spec "Fix ruff warnings in gateway/routes/" --json
# → id: task_t2
orca orchestration task-create --spec "Update docs/ARCHITECTURE.md for reasoning engine" --json
# → id: task_t3

# 2. Create worker terminals (one per task)
orca terminal create --worktree active --title "worker-1" --json
orca terminal create --worktree active --title "worker-2" --json
orca terminal create --worktree active --title "worker-3" --json

# 3. Dispatch all tasks
orca orchestration dispatch --task task_t1 --to <handle1> --inject --json
orca orchestration dispatch --task task_t2 --to <handle2> --inject --json
orca orchestration dispatch --task task_t3 --to <handle3> --inject --json

# 4. Collect results in a loop
for i in 1 2 3; do
  orca orchestration check --wait --types worker_done,escalation --timeout-ms 300000 --json
done
```

Why: tasks with no `--deps` are immediately `ready`. Dispatch all in parallel, then collect results. After each `worker_done`, mark complete and the terminal is idle for re-dispatch.

---

## Pattern 5 — Split a Large Change into Smaller PRs

Give each child agent its own worktree branch — parallel implementation, isolated review.

```
# 1. Create the worktree-per-task approach: each task gets its own branch
# For the reasoning engine (3 packets), split into 3 parallel PRs:

# Worker A: C1 complexity classifier in branch feat/re-c1-classifier
orca terminal create \
  --worktree "kittybuilder/c1-classifier" \
  --title "c1-worker" \
  --command "opencode run -m openrouter/deepseek/deepseek-v4-flash ..." \
  --json

# Worker B: C2 context budget in branch feat/re-c2-budget
orca terminal create \
  --worktree "kittybuilder/c2-budget" \
  --title "c2-worker" \
  --command "opencode run -m openrouter/deepseek/deepseek-v4-flash ..." \
  --json

# Worker C: C5 receipts in branch feat/re-c5-receipts
orca terminal create \
  --worktree "kittybuilder/c5-receipts" \
  --title "c5-worker" \
  --command "opencode run -m openrouter/deepseek/deepseek-v4-flash ..." \
  --json

# 2. Create and dispatch tasks
orca orchestration task-create \
  --spec "RE-C1: classifier + routing in gateway/reasoning.py" \
  --json
orca orchestration dispatch \
  --task <task_c1> --to <c1-handle> --inject --json
# ... repeat for C2, C5

# 3. After completion: each branch opens its own draft PR
# Never auto-merge. Each PR is independently reviewable.
# When env -u GITHUB_TOKEN gh pr create --draft --base main ...
```

Why: isolated worktrees prevent git conflicts between parallel workers. Each branch produces a small, reviewable PR. The coordinator collects results via `worker_done` messages. The worktree name maps to the branch (KittyBuilder convention: `.worktrees/kittybuilder/<task_id>`).

---

## Kitty-Specific Rules When Orchestrating

1. **Never auto-merge.** All PRs from orchestrated work need Jacob's review (T2).
2. **`env -u GITHUB_TOKEN`** on every `gh` and `git push` call — stale ambient token overrides keyring.
3. **Read `.claude/STATE.md` and `.claude/HANDOFF.md`** fresh before writing — concurrent agents stomp these files (L-CAND-16).
4. **`./kitty builder initiative doctor --json`** before any execution-sensitive work — Builder owns execution state.
5. **No two workers on the same file** without a dependency edge. Parallel workers editing the same file will collision.
6. **Circuit breaker**: after 3 consecutive failures on a task, stop and escalate. No infinite retry loops.
7. **Free workers only**: use the `--free` preset or the free-model ladder. Paid models only for packet authoring or Jacob's review.
8. **T0 work auto-approves.** T1 needs a separate model review. T2 stalls until Jacob resolves.

---

## Quick Reference

```
orca orchestration send     --to <handle> --type <type> --body "..."   # message
orca orchestration check    --wait --types worker_done --timeout-ms N  # block until reply
orca orchestration task-create  --spec "..." [--deps '[...]']           # create task
orca orchestration task-list    --ready --json                          # list dispatchable
orca orchestration dispatch     --task <id> --to <handle> --inject      # assign
orca orchestration gate-create  --task <id> --question "..."            # decision point
orca orchestration run          --spec "..." --max-concurrent N          # start coordinator
orca terminal list              --json                                   # find agents
orca terminal create            --worktree <name> --command "..."       # spawn agent
orca terminal wait              --for tui-idle --timeout-ms N           # wait for agent boot
```
