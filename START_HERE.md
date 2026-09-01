# Kitty — Start Here

This is the canonical cold-start bootloader. It routes to authorities and
live evidence; it does not duplicate current state.

## Boot sequence

1. Confirm `pwd -P`, `git rev-parse --show-toplevel`, and
   `git worktree list --porcelain`. The worktree must share Git state with
   `~/Projects/kitty`; Desktop copies are invalid.
2. Inspect `git status --short --branch`, branch, HEAD, `origin/main`, and
   recent commits. Do not fetch, switch, stash, or clean merely to simplify
   output. Before any substantial implementation, also read
   `docs/reference/MULTI_AGENT_COORDINATION.md`, check its live coordination
   issue, and inspect the relevant Builder/local ownership state before
   claiming an implementation lane.
3. Check `workspace_global` for relevant recent activity and this agent's inbox
   using the Agent Room MCP when configured or the `kitty room` CLI otherwise.
   Acknowledge messages actually received. The room is the primary mutable
   handoff/coordination surface; if it is unavailable, report that rather than
   fabricating room state.
4. Run the receipt for the task class. Informational/planning work may use
   `./kitty context --agent --compact --skip-builder`; code or Builder work
   uses full `./kitty context --agent`. A failed, unknown, stale, or
   contradictory receipt remains unverified; handoff prose cannot repair it.
5. Read only the authority files required by the task, using the receipt's
   order. For code changes, use the complete order below.
6. Read `docs/ACTIVE_MISSION.md` when the task is product or implementation
   work. Confirm scope, approval, base SHA, evidence, and authorization.
7. Inspect Builder through supported read-only commands only when Builder
   state, execution ownership, or collision risk matters.
8. Immediately before mutation, re-check live branch/HEAD, scope, owner,
   authorization, and the exact files to change.

## Task routing

- Informational: run the receipt and load the directly relevant authority.
- Planning: add `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and relevant
  `workspace_global` threads; use legacy checkpoint files only when explicitly
  needed for compatibility.
- Code change: load the full order, then the outcome contract and narrow code or
  test surface. Run focused verification after each coherent change.
- Builder work: use explicit intent (`builder status`, `builder next`,
  `review builder`, or a named task). Bare `next` never selects or runs a
  Builder packet.

## Canonical reading order

<!-- kitty-reading-order:start -->
1. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md)
2. [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md)
3. [`AGENTS.md`](AGENTS.md)
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
5. [`docs/DECISIONS.md`](docs/DECISIONS.md)
6. [`docs/ROADMAP.md`](docs/ROADMAP.md)
7. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
8. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md)
<!-- kitty-reading-order:end -->

`workspace_global` is the primary mutable cross-agent handoff and communication
surface and is checked separately because it is runtime state, not versioned
document authority. `.claude/STATE.md` and `.claude/HANDOFF.md` are legacy
compatibility checkpoints: read them only when a skill/tool explicitly requires
them or the room is unavailable, and validate their identity before use.

`docs/reference/MULTI_AGENT_COORDINATION.md` is an operational coordination
supplement, not another authority file. Its live issue is mutable campaign
state and must be revalidated against current GitHub/Builder/Mac truth.

## Minimal command set

```bash
git status --short --branch
./kitty context --agent --compact --skip-builder  # informational/planning
# ./kitty context --agent                                # code/Builder work
```

Use `./kitty builder initiative doctor --json` only for Builder-relevant work.
Use focused tests for focused changes; reserve full quality gates for an
explicit `/qg`, CI, or user request.

Push, merge, deletion, history rewrite, credentials, auth/env changes, paid
execution, and heavy dependencies remain approval-gated.
