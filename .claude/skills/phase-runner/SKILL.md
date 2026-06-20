---
name: phase-runner
description: Run a Kitty phase with checkpoint/resume so context cutoffs don't lose progress. Triggers on "run phase N", "start phase N", "continue phase".
argument-hint: "<phase-number>"
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash(python3* -m pytest*)
  - Bash(git status)
  - Bash(git diff *)
  - Bash(git add *)
  - Bash(git commit *)
  - Bash(git log *)
  - Bash(git push *)
  - Bash(mkdir *)
  - Bash(touch *)
---

# Phase Runner

Wraps Kitty phase execution with checkpointing so any session can resume
exactly where the last one stopped. No re-work, no re-acquaintance overhead.

## Checkpoint format

Stored at `.kitty/checkpoints/phase-$N.json`:
```json
{
  "phase": 3,
  "started_at": "2026-06-20T10:00:00Z",
  "git_sha": "abc1234",
  "test_count_at_start": 167,
  "tasks": [
    {"id": "B1", "title": "SQLite seam", "status": "done", "sha": "def5678"},
    {"id": "B2", "title": "Plugin settings", "status": "in_progress"},
    {"id": "B3", "title": "Todos table", "status": "pending"}
  ],
  "notes": "B2 hit sqlite3.OperationalError on double-migrate; fixed with IF NOT EXISTS"
}
```

## Execution protocol

### On first run (`/phase-runner <N>`)

1. Read `docs/PHASE_B_PLAN.md` (or the relevant phase doc) to build task list
2. Read `docs/AGENT_HANDOFF.md` for any existing context
3. Create `.kitty/checkpoints/phase-$N.json` with all tasks as `pending` and current git SHA
4. Execute tasks in order. After each task completes:
   - Mark it `done` with the commit SHA
   - Update the checkpoint file immediately
   - Run `python3.12 -m pytest tests/ -q --tb=line 2>/dev/null | tail -5` and record test count
5. When all tasks are done: update `docs/AGENT_HANDOFF.md`, commit checkpoint, report summary

### On resume (`/phase-runner <N>` with existing checkpoint)

1. Read `.kitty/checkpoints/phase-$N.json`
2. Skip all `done` tasks — do NOT re-run them
3. Pick up at the first `in_progress` or `pending` task
4. If an `in_progress` task has a partial SHA, verify the commit is clean before continuing
5. Continue the same protocol as first run from step 4

### Budget awareness

After every task completion, if context feels near the limit (you're being
asked to write this down, that's the signal), write the checkpoint and
HANDOFF.md immediately and stop. The next `/phase-runner <N>` will resume.

Target: write checkpoint at ~80% budget, not at the end.

## Gate

Before marking a phase complete:
- All tasks must be `done`
- `pytest` must show ≥ the test count at phase start (no regressions)
- No uncommitted changes (`git status` clean)

## Rules

- Never re-run a `done` task — trust the checkpoint
- Never mark a task done without a verifiable commit SHA
- If a migration fails idempotency (executescript commits early), note it in checkpoint `notes` and stop for user input
- Keep `.kitty/checkpoints/` in git (it's documentation, not build output)
