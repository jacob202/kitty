# Outcome contract: Discord Command Center Phase 0

## User-visible outcome

From a dedicated Discord Command Center bot, Jacob can run `/vibe <request>` and receive Codex's read-only repository analysis in a task thread without manually opening a coding CLI.

## Acceptance criteria

1. The slash-command handler defers before any planning/execution work.
2. One Codex adapter runs with strict argv, `shell=False` equivalent, `--ephemeral`, `--sandbox read-only`, and a disposable git worktree.
3. The child receives an explicit environment allow-list that excludes `DISCORD_BOT_TOKEN` and unrelated repository secrets.
4. Run time is bounded; cancellation/timeout terminates the child and escalates to kill after a grace period.
5. Progress is chunked safely for Discord and posted to the task thread rather than depending on a long-lived interaction followup.
6. Every run performs a post-run git audit; any mutation during readonly execution fails loudly as `readonly_violation` and preserves the worktree.
7. A clean run removes its disposable worktree.
8. Focused tests pass without live Discord/model calls.
9. A local Codex smoke produces output and a clean diff audit in a disposable worktree.

## Verification

```bash
/Users/jacobbrizinski/Projects/kitty/venv/bin/python -m pytest -q tests/test_discord_command_center_phase0.py
/Users/jacobbrizinski/Projects/kitty/venv/bin/python -m integrations.discord_command_center.smoke --repo .
```

A live Discord acceptance run is separate because the required bot application/token does not yet exist.

## Prohibited shortcuts and non-goals

- Do not touch KittyBuilder model selection, worker/reviewer adapters, retries, publication, queues, or cost routing.
- Do not create Gateway task state or `/builder/proposals` in Phase 0.
- Do not add `/swarm`, dashboard, reactions, approval buttons, or durable task state.
- Do not claim Codex read-only flags are sufficient; the git diff audit is mandatory.
- Do not print or pass the Discord token to worker subprocesses.

## Repair limit

Two focused repair cycles per failing acceptance criterion, then report the exact blocker.