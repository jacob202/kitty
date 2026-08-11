# Outcome contract: Discord Command Center Phase 0

## User-visible outcome

From a dedicated Discord Command Center bot, Jacob can run `/vibe <request>` and receive Codex's read-only repository analysis in a task thread without manually opening a coding CLI.

## Acceptance criteria

1. The slash-command handler defers before any planning/execution work.
2. One Codex adapter runs with strict argv, `shell=False` equivalent, `--ephemeral`, an explicit advisory read-only instruction/mode, and a disposable git worktree. On macOS the outer `sandbox-exec` profile is the OS write boundary; Codex's internal sandbox may be disabled when sandbox nesting prevents the runtime from starting. The post-run git audit remains the mutation verifier.
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

## Evidence — 2026-08-11

- Post-review focused suite: `24 passed` (`tests/test_discord_command_center_phase0.py` + existing `tests/test_agent_council.py`); this includes membership-failure, pre-worker and outbound secret-scrubbing, timeout, cancellation, SIGKILL escalation, ignored-file mutation detection, and macOS sandbox behavior coverage.
- Static checks: Ruff clean; mypy clean for `integrations/discord_command_center`.
- macOS sandbox proof: write inside disposable worktree succeeds; `/dev/null` succeeds; write outside is denied.
- Real Codex smoke: rerun after review repairs; completed local repository inspection and ended `read-only diff audit clean` with exit 0.
- Forced-write proof: a real `/usr/bin/touch` inside the run worktree produced terminal `readonly_violation`; dirty worktree preserved with `FORCED_READONLY_VIOLATION.txt`.
- Ignored-write proof: a real sandboxed `/usr/bin/touch ignored.txt` in a disposable repo whose `.gitignore` ignores that path still produced terminal `readonly_violation`; audit evidence was `!! ignored.txt`.
- Collision check: no changes to Builder-owned routing/worker/governor/config paths.
- Full Discord acceptance remains unverified until a Command Center bot token and test guild/channel are configured.
