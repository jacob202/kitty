# Plan: Autonomous Campaign Supervisor

## Goal

Create a source-controlled unattended KittyBuilder supervisor and Claude Pro worker/reviewer adapter that remove Jacob as the message relay while preserving Builder as the sole durable control plane.

## Files

- [NEW] gateway/builder_supervisor.py — stateless tick, lock, capped parallel launch, diagnostic receipt.
- [MOD] gateway/builder_cli.py — builder supervisor tick and read-only status.
- [NEW] scripts/start_builder_supervisor.sh — fixed launchd-safe CLI wrapper.
- [MOD] scripts/kitty_desktop_launchd.py — builder-supervisor timer service.
- [NEW] tests/test_builder_supervisor.py — selection, lock, cap, recovery-delegation tests.
- [MOD] tests/test_builder_cli.py and tests/test_desktop_launchd.py — command/plist contracts.
- [NEW] scripts/kittybuilder_claude_adapter.py — strict Claude worker/reviewer contract adapter.
- [NEW] tests/test_kittybuilder_claude_adapter.py — fake CLI success/failure/immutability coverage.
- [MOD] docs/KITTYBUILDER_MCP.md and docs/CONTINUITY_RECOVERY.md — authority, recovery, operations.

## Steps

- [ ] Build the supervisor core in gateway/builder_supervisor.py.

  Derive eligible active initiatives through existing Builder APIs, sort deterministically, acquire one OS lock, and run at most two canonical run_initiative calls. Never create a table, write task state directly, resume paused work, or choose publication. Return a structured diagnostic receipt only after Builder calls finish.

  Verification: venv/bin/pytest tests/test_builder_supervisor.py tests/test_builder_run.py -q. Expected: duplicate tick is a no-op; only eligible active work launches; cap holds; all outcomes are Builder-derived.

- [ ] Add Builder CLI commands in gateway/builder_cli.py.

  Add:
  ./kitty builder supervisor tick --free --gate manual --max-runtime 5400 --max-parallel 2
  and:
  ./kitty builder supervisor status --json

  Reuse existing worker/reviewer route selection. Do not accept arbitrary worker commands from a scheduler or Discord. Lock contention, no eligible work, and a truthful block are not fabricated success.

  Verification: venv/bin/pytest tests/test_builder_cli.py -q.

- [ ] Add a scheduled launcher through scripts/start_builder_supervisor.sh and scripts/kitty_desktop_launchd.py.

  Generate com.kitty.desktop.builder-supervisor with RunAtLoad true, StartInterval 900, no KeepAlive, canonical working directory, safe PATH, and fixed log files. Preserve linked-worktree refusal. Do not install/bootstrap it in automated verification.

  Verification: venv/bin/pytest tests/test_desktop_launchd.py -q and venv/bin/python scripts/kitty_desktop_launchd.py generate.

- [ ] Mirror the Codex contract in scripts/kittybuilder_claude_adapter.py.

  Support worker/reviewer modes, stage/hash-check Builder artifacts, create strict JSON schemas, invoke local Claude print mode in the isolated worktree, validate the same contracts, commit only completed implementation, and verify reviewer immutability. Auth/executable unavailable with no output/change returns 75; partial work fails loud. Worker model sonnet; independent reviewer model opus; no fallback.

  Verification: venv/bin/pytest tests/test_kittybuilder_claude_adapter.py tests/test_builder_loop.py -q. Fake CLI only; no live Claude request.

- [ ] Document and prove the walking skeleton.

  Document the supervisor as launcher/read projection, not authority. Describe manual publication, provider pause/recovery, and future Discord projection.

  Verification: venv/bin/pytest tests/test_mcp_builder_server.py tests/test_mcp_builder_commands.py tests/test_mcp_builder_continuity.py -q.

## Work decomposition

1. Supervisor/CLI/LaunchAgent share a command contract and are one lane.
2. Claude adapter/tests are a separate disjoint lane after the command contract settles.
3. Documentation and independent review follow both lanes.

## Edge cases

- Scheduled overlap: lock exits without dispatch.
- Path/branch collision: existing Builder guard blocks it.
- Launcher/worker/Orca death: existing Builder recovery applies.
- Provider exhaustion: 75 yields a durable pause; unrelated work continues.
- Claude writes then errors or changes without result: preserve evidence; no fallback.
- Changed base/design/plan/manifest: existing MCP lineage/nonce returns needs decision.

## Final acceptance

- One approved low-risk manual-publication Mission starts without a chat turn and reaches normal Builder review state.
- Two lanes never exceed the cap; repeated ticks duplicate nothing.
- Claude Pro is selectable as worker/reviewer with all failure classifications fake-tested.
- Discord only projects typed Builder truth and has no shell/approval/publication/merge path.
- Builder doctor, work status, and supervisor receipt agree.
