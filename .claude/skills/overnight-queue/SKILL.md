---
name: overnight-queue
description: Pattern for autonomous overnight task queue execution with durable checkpointing. Use when Jacob queues multi-task work and steps away. Prevents usage-limit cutoffs from losing state.
type: process
---

Act as an Autonomous Queue Worker. This skill operationalizes long unattended runs that survive interruption.

## When to Use

- Jacob queues 3+ tasks and explicitly says "work the queue" or "run overnight"
- Long-running batched work where each task is independent and reversible
- Implementation work where Jacob has approved the spec and is stepping away

## When NOT to Use

- Tasks requiring decisions Jacob hasn't pre-approved
- Anything destructive without explicit per-task authorization
- Work where one failure should cascade-stop the queue

## The Pattern

```
1. INGEST          → Read TASKS.md or queue source; confirm each task has clear done criteria
2. ESTIMATE        → Token budget per task, total queue, expected wall-clock
3. CHECKPOINT FILE → Create HANDOFF-<date>-queue.md with task list and status column
4. PER TASK:
     a. Mark in-progress in HANDOFF
     b. Branch (optional, if isolation matters)
     c. Implement
     d. Test (scripts/clear-and-test.sh)
     e. Commit (scripts/checkpoint.sh) — ALWAYS before next task
     f. Mark done in HANDOFF with one-line note
     g. Move to next
5. ON USAGE LIMIT  → HANDOFF is already current; next session resumes cleanly
6. ON HARD FAIL    → Mark task as blocked in HANDOFF, stop queue, leave clean state
7. ON COMPLETE     → Final HANDOFF entry summarizes what shipped, what's next
```

## Checkpoint File Shape

```markdown
# Queue: <name>
Started: <ISO timestamp>
Worker: <agent-id / model>

## Tasks

| # | Task | Status | Commit | Tests | Note |
|---|------|--------|--------|-------|------|
| 1 | ... | done | abc123 | 399/399 | <note> |
| 2 | ... | in-progress | — | — | — |
| 3 | ... | pending | — | — | — |

## Last Resumable State
<one paragraph: what's running, what's next, anything mid-flight>
```

## Hard Rules

- Never start task N+1 without having committed task N.
- Never silently expand scope. If a task reveals more work, log it as a NEW queue item, do not absorb it.
- Never leave the repo broken. If you cannot complete cleanly, revert the in-progress change before stopping.
- When sensing usage approaching limit, FINALIZE the HANDOFF immediately, then continue if budget allows.
- Stop the queue only on: empty queue, two consecutive task failures, or explicit user halt.

## Anti-Patterns

- Marking task done without test evidence — never.
- Working faster by skipping commits — defeats the entire purpose.
- "I'll consolidate the commits at the end" — no. Commit per task.

## Pairs With

- `scripts/checkpoint.sh` for fast WIP commits
- `scripts/clear-and-test.sh` for the test gate
- `parallel-subagents` skill if a queue item itself decomposes into parallel work
