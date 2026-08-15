# Plan: Autonomous Campaign Supervisor v2

## Goal

Create a source-controlled unattended KittyBuilder supervisor and Claude Pro worker/reviewer adapter that execute from clean worktrees without manual environment setup or dependency downloads.

## Files

- [MOD] `scripts/kittybuilder_opencode_worker.sh` — prepend the existing repository runtime to child `PATH` when present; never create or install a worktree environment.
- [MOD] `gateway/builder_attempt.py` — apply the same runtime `PATH` policy to operator-authored validation commands and fail clearly when unavailable.
- [MOD] `tests/test_builder_attempt.py`, `tests/test_kittybuilder_opencode_adapters.py` — prove runtime propagation and no-install/no-symlink behavior.
- [NEW] `gateway/builder_supervisor.py` — stateless tick, OS lock, deterministic eligible selection, capped parallel canonical runs, diagnostic receipt.
- [MOD] `gateway/builder_cli.py` — fixed `builder supervisor tick` and read-only status commands.
- [NEW] `scripts/start_builder_supervisor.sh` — fixed launchd-safe wrapper.
- [MOD] `scripts/kitty_desktop_launchd.py` — 900-second non-KeepAlive supervisor service.
- [NEW] `tests/test_builder_supervisor.py`; [MOD] `tests/test_builder_cli.py`, `tests/test_desktop_launchd.py` — supervisor contracts.
- [NEW] `scripts/kittybuilder_claude_adapter.py`; [NEW] `tests/test_kittybuilder_claude_adapter.py` — strict Claude worker/reviewer contract.
- [MOD] `docs/KITTYBUILDER_MCP.md`, `docs/CONTINUITY_RECOVERY.md` — authority and operations.

## Steps

- [ ] Build the runtime preflight in `scripts/kittybuilder_opencode_worker.sh` and `gateway/builder_attempt.py`. Resolve the root runtime from the existing repository installation, prepend it only to child process `PATH`, use portable `python -m` validation commands, and never create a file in the worktree or install dependencies. Verify with focused attempt/adapter tests.
- [ ] Build the supervisor core, CLI, launcher, and launchd projection. Reuse existing `run_initiative`, one OS lock, deterministic selection, max two parallel runs, no direct task-state writes, no paused-work resume, no arbitrary commands, and no publication. Verify supervisor, Builder-run, CLI, and launchd tests.
- [ ] Mirror the Codex adapter for local Claude worker/reviewer modes: Sonnet worker, Opus reviewer, strict hashes/contracts, reviewer immutability, exit 75 on unavailable executable/auth with no output/change, and no fallback. Use fake CLI tests only.
- [ ] Document Builder authority, manual publication, provider pause/recovery, and Discord typed projection-only behavior.

## Approach and rejected alternatives

Use process `PATH` propagation because the root runtime already exists and validation already runs in a Builder-owned process. Reject worktree symlinks because they violate the clean-tree invariant; reject package installation because it wastes resources and changes the worker environment; reject a new runtime database or queue because Builder already owns durable execution.

## Verification

- Runtime preflight: `python -m pytest tests/test_builder_attempt.py tests/test_kittybuilder_opencode_adapters.py -q` — focused tests pass; no worktree setup files are created.
- Supervisor: `python -m pytest tests/test_builder_supervisor.py tests/test_builder_run.py tests/test_builder_cli.py tests/test_desktop_launchd.py -q` — focused suite passes.
- Claude adapter: `python -m pytest tests/test_kittybuilder_claude_adapter.py tests/test_builder_loop.py -q` — fake-CLI and loop tests pass.
- Final: Builder doctor, mission status, and supervisor receipt agree; no PR is pushed or merged automatically; service installation is not performed by tests.
