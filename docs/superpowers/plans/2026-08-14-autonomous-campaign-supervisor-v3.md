# Plan: Autonomous Campaign Supervisor v3 Walking Skeleton

## Goal

Create one integrable source-controlled unattended KittyBuilder supervisor and Claude Pro worker/reviewer adapter that run from clean worktrees without manual environment setup or dependency downloads.

## Files

- [MOD] `scripts/kittybuilder_opencode_worker.sh` — propagate the existing root runtime through child `PATH`; never install or create worktree setup files.
- [MOD] `gateway/builder_attempt.py` — apply the same runtime `PATH` policy to declared validation commands; fail clearly when unavailable.
- [MOD] `tests/test_builder_attempt.py`, `tests/test_kittybuilder_opencode_adapters.py` — runtime propagation and no-install coverage.
- [NEW] `gateway/builder_supervisor.py` — stateless tick, one OS lock, deterministic eligible selection, capped parallel canonical runs, diagnostic receipt.
- [MOD] `gateway/builder_cli.py` — fixed supervisor tick and read-only status commands.
- [NEW] `scripts/start_builder_supervisor.sh` — fixed launchd-safe wrapper.
- [MOD] `scripts/kitty_desktop_launchd.py` — 900-second non-KeepAlive service generation.
- [NEW] `tests/test_builder_supervisor.py`; [MOD] `tests/test_builder_cli.py`, `tests/test_desktop_launchd.py` — supervisor contracts.
- [NEW] `scripts/kittybuilder_claude_adapter.py`; [NEW] `tests/test_kittybuilder_claude_adapter.py` — strict Claude worker/reviewer contract.
- [MOD] `docs/KITTYBUILDER_MCP.md`, `docs/CONTINUITY_RECOVERY.md` — authority and operations.

## Steps

- [ ] Implement runtime preflight in `scripts/kittybuilder_opencode_worker.sh` and `gateway/builder_attempt.py`, following existing child-env construction in `gateway/builder_runner.py:1080-1120` and validation execution in `gateway/builder_attempt.py:933-1030`. Use the root runtime only through child `PATH`; no symlink, install, or clean-tree exemption.
- [ ] Implement the supervisor and CLI using existing initiative selection and canonical run APIs (`gateway/builder_run.py:420-480`, `gateway/builder_initiative.py:1441-1468`). Use one OS lock, deterministic ordering, max two concurrent runs, truthful receipts, no paused-work resume, direct task-state writes, arbitrary commands, or publication.
- [ ] Add the fixed launcher and launchd generation following `scripts/kitty_desktop_launchd.py:89-165`: RunAtLoad, StartInterval 900, no KeepAlive, safe PATH, canonical root, fixed logs, and no installation in tests.
- [ ] Mirror the Codex adapter contract for Claude worker/reviewer modes: Sonnet worker, Opus reviewer, strict hashes/results, reviewer immutability, exit 75 on unavailable executable/auth with no fallback, fake CLI only.
- [ ] Document Builder authority, manual publication, provider pause/recovery, and future Discord typed projection-only behavior.

## Verification

Use `python3.12 -m pytest` for this Mac/CI runtime; do not invoke `pip install` or create a worktree venv.

- Runtime/adapter: `python3.12 -m pytest tests/test_builder_attempt.py tests/test_kittybuilder_opencode_adapters.py tests/test_kittybuilder_claude_adapter.py -q`.
- Supervisor/CLI/launchd: `python3.12 -m pytest tests/test_builder_supervisor.py tests/test_builder_run.py tests/test_builder_cli.py tests/test_desktop_launchd.py -q`.
- Continuity: `python3.12 -m pytest tests/test_mcp_builder_server.py tests/test_mcp_builder_commands.py tests/test_mcp_builder_continuity.py -q`.
- Final acceptance: one clean branch contains the complete diff; Builder doctor and status agree; no PR, push, merge, or service installation occurs automatically.

## Rejected alternatives

Separate dependent packets were rejected because Builder's current dependency graph does not provide branch handoff. Worktree symlinks were rejected by the clean-tree guard. Package installation was rejected as wasteful and non-durable. A new queue/database/event bus was rejected because Builder already owns durable execution.
