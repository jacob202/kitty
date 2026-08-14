# Discord Command Center Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove one `/vibe` Discord command can invoke local Codex read-only in an audited disposable worktree and return progress in a thread.

**Architecture:** Command Center is an isolated presentation/control integration under `integrations/discord_command_center/`. Phase 0 holds task state only in memory and never calls or modifies KittyBuilder/Gateway coordination state. Codex read-only is advisory; disposable worktree isolation plus post-run git audit is the mutation detector.

**Tech Stack:** Python 3.12, discord.py 2.7.x, asyncio subprocesses, git worktrees, macOS sandbox-exec, pytest.

## Global Constraints

- No Builder queue, routing, review, publication, retries, or cost-governor implementation in Command Center.
- Strict argv only; never `shell=True`.
- Default run timeout: 900 seconds; terminate then kill after 10 seconds.
- Discord plain-message chunks: maximum 1900 characters.
- Worker environment is allow-listed and excludes Discord credentials.
- Readonly mutation => `readonly_violation`, failed run, worktree preserved.
- Full Discord acceptance requires a separately created bot application/token.

---
### Task 1: Audited Codex execution spine

**Files:**
- Create: `integrations/__init__.py`
- Create: `integrations/discord_command_center/__init__.py`
- Create: `integrations/discord_command_center/config.py`
- Create: `integrations/discord_command_center/models.py`
- Create: `integrations/discord_command_center/workspace.py`
- Create: `integrations/discord_command_center/adapters/__init__.py`
- Create: `integrations/discord_command_center/adapters/codex.py`
- Create: `integrations/discord_command_center/runner.py`
- Create: `integrations/discord_command_center/service.py`
- Test: `tests/test_discord_command_center_phase0.py`

**Interfaces:**
- `CommandCenterConfig.from_env()` loads runtime paths/model/timeouts without exposing token values.
- `GitWorktreeManager.create(run_id) -> Path`, `audit(path) -> DiffAudit`, `remove(path) -> None`.
- `CodexAdapter.command(prompt, worktree) -> tuple[str, ...]`.
- `SubprocessRunner.stream(command, cwd, env, timeout) -> AsyncIterator[ProgressEvent]`.
- `VibeService.run(request) -> AsyncIterator[ProgressEvent]` ending in one terminal event.

- [x] Write tests for strict Codex argv, secret-free child env, diff auditing, clean cleanup, and violation preservation.
- [x] Run the focused test file and verify RED failures are caused by missing Command Center modules.
- [x] Implement the minimum core modules to satisfy those tests.
- [x] Re-run the focused tests and keep them green before moving on.

### Task 2: Thin Discord `/vibe` wiring

**Files:**
- Create: `integrations/discord_command_center/bot.py`
- Modify: `tests/test_discord_command_center_phase0.py`

**Interfaces:**
- `VibeController.handle(interaction, request) -> None` defers before invoking `VibeService`.
- `create_bot(config) -> discord.Client` registers one guild-scoped `/vibe` command when a guild ID is configured.

- [x] Add a fake-interaction test proving `defer()` is the first externally visible action and progress goes to the created thread.
- [x] Run the focused test and verify the new test fails for missing Discord wiring.
- [x] Implement the thin controller/bot without putting execution policy in Discord callbacks.
- [x] Re-run focused tests.

### Task 3: Local smoke and operator runbook

**Files:**
- Create: `integrations/discord_command_center/smoke.py`
- Create: `integrations/discord_command_center/README.md`
- Create: `integrations/discord_command_center/requirements.txt`
- Modify: `tests/test_discord_command_center_phase0.py`

**Interfaces:**
- `python -m integrations.discord_command_center.smoke --repo <path>` performs one bounded local Codex readonly run and reports the audit result without requiring Discord.

- [x] Add smoke argument/format tests without a live model call.
- [x] Implement the smoke entry point and concise onboarding/run commands.
- [x] Run focused tests, ruff on new Python files, and mypy on the integration package.
- [x] Run one real local Codex smoke; clean diff audit observed.
- [x] Inspect changed paths and prove no Builder-owned paths changed.
- [x] Commit the Phase 0 implementation on the isolated branch; final independent verification is a separate delivery gate.
