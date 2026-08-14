# Autonomous Campaign Supervisor — Design

**Date:** 2026-08-14
**Status:** proposed
**Base:** 6e49a4e104b3215fa46adc55846b3da6bd465564

## Goal

Advance approved KittyBuilder work unattended and in parallel without making ChatGPT, Discord, Orca, or any model a second execution authority.

## Decision

A thin, stateless supervisor is the missing layer. It is invoked by one source-controlled launchd timer, reads Builder derived initiative state, and calls the existing run_initiative loop. Builder remains the only durable owner of tasks, leases, attempts, worktrees, reviews, evidence, and publication.

~~~
MCP / Kitty / Discord request and show typed state
                    |
                    v
             exact Mission approval
                    |
                    v
launchd -> supervisor tick -> canonical Builder run
                    |
                    v
        Builder DB is the only durable truth
                    |
                    v
       Claude, Codex, Orca are replaceable adapters
~~~

## Evidence

- Existing Builder loop: gateway/builder_run.py and gateway/builder_loop.py.
- Existing but unscheduled locked launcher: scripts/nightly_packet_drain.sh.
- Existing typed bridge: mcp/builder/server.py.
- Existing Codex result-contract adapter: scripts/kittybuilder_codex_adapter.py.
- Local Claude CLI reports signed-in Claude Pro status.
- Existing ADRs 0017, 0018, 0021, 0036, and 0038 require this boundary.

## Rules

- No second task database, retry engine, status store, workflow engine, or agent framework.
- No direct task-table writes by the supervisor.
- No automatic resume of a paused initiative, no hidden provider fallback, no auto merge.
- Discord is read projection and typed control only: no arbitrary shell, approval by ordinary message, publication, merge, or spending.
- Orca may transport workers but never owns recoverable campaign state.
- Logs/receipts are diagnostic only.
- Claude adapter mirrors the Codex adapter: context hashes, strict result schema, worktree fingerprint, clean unavailable returns 75, partial work fails loudly. Default worker sonnet, independent reviewer opus.
- MCP Tasks are deferred; client support is optional. https://modelcontextprotocol.io/extensions/tasks/overview

## Acceptance

1. Repeated tick means no duplicate attempt, lease, or worktree.
2. At most two independent eligible initiatives run; Builder exposes collisions.
3. Worker/supervisor/Orca loss recovers only from Builder.
4. Generated launcher uses 900-second interval, canonical checkout, no KeepAlive, and fixed logs.
5. Claude fake-CLI tests prove success, invalid contract, clean unavailable, partial work, reviewer immutability.
6. An approved low-risk test Mission runs scheduled with manual publication and no GitHub mutation.
