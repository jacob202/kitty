# Plan: Autonomous Campaign Supervisor (rebased)

## Goal

Create a source-controlled unattended KittyBuilder supervisor and Claude Pro worker/reviewer adapter that remove Jacob as the message relay while preserving Builder as the sole durable control plane.

## Rebase review

The design and plan are rebased to `main@8bd732f3ef948af2316eadf89ffeaff94849f3e6`. PR #495 is limited to Discord request-size bounds and does not overlap this plan's owned paths.

## Packets

1. **Supervisor command contract** — add `gateway/builder_supervisor.py`, fixed Builder CLI tick/status commands, `scripts/start_builder_supervisor.sh`, and desktop launchd generation. Use one OS lock, cap at two canonical Builder runs, never mutate task state directly, accept arbitrary worker commands, publish automatically, or install the service during verification. Validate focused supervisor, Builder-run, CLI, and launchd tests plus launchd generation.

2. **Claude Pro adapter** — add `scripts/kittybuilder_claude_adapter.py` and fake-CLI tests. Mirror strict staged artifact/result contracts, Sonnet worker and Opus reviewer selection, reviewer immutability, exit 75 for unavailable CLI/auth with no output/change, and no fallback. Do not make a live Claude request in tests.

3. **Operations documentation** — update Builder MCP and continuity/recovery documentation. State manual publication, provider pause/recovery, Builder authority, and future Discord typed projection only.

## Non-goals

No new queue, workflow engine, state database, event bus, autonomous merge/publish path, Discord shell bridge, or LaunchAgent installation.

## Final acceptance

- A manually-approved low-risk Mission starts without a chat turn and reaches normal Builder review state.
- Two concurrent lanes never exceed the cap and repeated ticks duplicate nothing.
- The Claude subscription route is selectable and fake-tested for its strict failure classes.
- Builder doctor, work status, and the supervisor receipt agree.
