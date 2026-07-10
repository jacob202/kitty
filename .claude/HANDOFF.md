# Handoff — 2026-07-10 (runner hardening complete)

## Branch: `feat/kittybuilder-runner-shadow`

### What's done
Phase 1C-alpha runner safety hardening is complete and green. This session
consolidated Sol's partial checkpoint (`3ed6a47`, `6b9af75`) into one
internally coherent, reviewed implementation committed at `87777de`.

### Commits on branch (oldest → newest)
- `156875a` — Phase 1C-alpha runner draft (runner loop, scope checks, timeout, cancellation)
- `3cbf5d3` — Fix: honor requested cancellation when worker exits via cancel signal
- `3ed6a47` — Sol's bulk hardening checkpoint (~1331 lines: process_identity, credential isolation, scope boundary, recovery grace period, PID identity, heartbeat validation, atomic finalization)
- `6b9af75` — Preserve Sol's remaining uncommitted work (Sol ran out of credits)
- **`87777de`** — Complete the hardening (this session)

### What `87777de` adds/changes
- **`gateway/builder_queue.py`**: `finalize_run` gains `runner_owns_claimed_task` — handles edge case where task is CLAIMED but run is STARTING or CANCEL_REQUESTED (launch failure path). Properly releases claim back to QUEUED with `released_after_setup_failure` task_update.
- **`gateway/builder_runner.py`**:
  - `_raise_worker_launch_error` helper — persists failed launches with full report (scope violations, worktree state), then raises `RunnerError`.
  - Prelaunch setup (create_run → brief → worker_transition to RUNNING) wrapped in try/except with two paths: `run is None` (claim release) vs `run exists` (finalize_run as failed).
  - `control_error` tracking through heartbeat loop — handles disappeared runs, missing start SHA, worktree inspection failures. Always terminates worker, always raises `RunnerError` after durable finalization.
  - Credential isolation: pops `GITHUB_TOKEN`/`GH_TOKEN`, redirects `GH_CONFIG_DIR` to empty dir, disables global/system git config, blocks credential helpers via `GIT_CONFIG_COUNT/KEY/VALUE`.
  - Scope checking: `PurePosixPath` with path-boundary prefix check (`path.startswith(f"{prefix}/")`) prevents prefix-confusion attacks.
- **Tests**: 4 new tests (prefix-confusion, recovery idempotency, prelaunch setup failure, monitoring failure); CLI tests for runs filter dispatch, show-run log tail, clean-worktree command.

### Verification
- 297 builder tests pass (`pytest tests/test_builder_*.py`)
- mypy clean (3 source files)
- `git diff --check` clean
- 6 live smoke tests pass in temp git repo (success, failure, timeout, launch failure, scope violation, recovery)

### What's NOT done
- **No PR opened** — branch is local only. Do not push without confirmation.
- **No architecture audit** — the 7 hardening areas are internally consistent but have not been through a formal architecture review.
- **No Phase 1C-beta** — the runner shadow mode works but has not been tested against real LLM providers or GitHub Actions.

### Recommended next step
1. Push branch and open PR for review
2. Consider running `/qg` to gate the PR
3. Decide whether to proceed to Phase 1C-beta (real provider integration) or run architecture audit first
