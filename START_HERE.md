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
3. Prove `workspace_global` access. Discover explicit assignments, handoffs,
   and review asks through this agent's unread **direct** inbox first:
   `./kitty room inbox --as <identity> --unread --direct-only --json`. MCP
   clients use `room_inbox(unread_only=True, direct_only=True)` for the same
   assignment discovery; do not treat the broadcast feed as an assignment
   queue. If the assignment
   supplies a durable locator, load that exact conversation with `room_thread`
   or `./kitty room thread <message_id> --json`. Use recent messages only for
   bounded shared situational context; the newest global window is not an
   assignment index. Acknowledge messages actually received. If the room itself
   is unavailable, report that rather than fabricating room state.
4. Choose the receipt mode from the continuation source:
   - GAR available **and** an unread handoff/known durable thread identifies the
     assignment: code work uses `./kitty context --agent
     --skip-legacy-continuity`; informational/planning work may add `--compact
     --skip-builder`.
   - GAR available but there is **no** unread handoff or durable locator and the
     legacy checkpoint is needed as the temporary continuation fallback: run
     the strict `./kitty context --agent` receipt first and use that checkpoint
     only if its validation succeeds.
   - GAR unavailable: use the strict `./kitty context --agent` compatibility
     receipt and report the room as unavailable.
   A failed, unknown, stale, or contradictory required source remains
   unverified; handoff prose cannot repair it.
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
- Planning: add `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and a known
  `workspace_global` thread/handoff when one exists; use legacy checkpoint files
  only through the strict validated compatibility fallback above.
- Code change: load the full order, then the outcome contract and narrow code or
  test surface. Run focused verification after each coherent change.
- Builder work: use explicit intent (`builder status`, `builder next`,
  `review builder`, or a named task). Bare `next` never selects or runs a
  Builder packet.

## Canonical reading order

<!-- kitty-reading-order:start -->
1. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) — concern router
2. [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) — highest design authority
3. [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) — product purpose
4. [`AGENTS.md`](AGENTS.md) — engineering doctrine
5. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current system shape
6. [`docs/DECISIONS.md`](docs/DECISIONS.md) — accepted decisions
7. [`docs/ROADMAP.md`](docs/ROADMAP.md) — active delivery order
8. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — dated shipped evidence
9. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) — one approved mission
<!-- kitty-reading-order:end -->

`workspace_global` is the primary mutable cross-agent handoff and communication
surface and is checked separately because it is runtime state, not versioned
document authority. `.claude/STATE.md` and `.claude/HANDOFF.md` are legacy
compatibility checkpoints: they are not mandatory reading, and they must never
override fresher room, Git, GitHub, Builder, or runtime evidence.

`docs/reference/MULTI_AGENT_COORDINATION.md` is an operational coordination
supplement, not another authority file. Its live issue is mutable campaign
state and must be revalidated against current GitHub/Builder/Mac truth.

`docs/reference/CONTEXT_ENGINEERING.md` provides staged-loading detail by task
type (what to load for informational, planning, and code-change work). This
file owns the cold-start receipt and the canonical reading order only; it does
not duplicate the staged-load procedure.

## Minimal command set

```bash
git status --short --branch
./kitty room inbox --as <identity> --unread --direct-only --json
# Known GAR handoff/thread:
./kitty context --agent --compact --skip-builder --skip-legacy-continuity
# No GAR locator yet, or GAR unavailable and legacy fallback is required:
./kitty context --agent
```

Use `./kitty builder initiative doctor --json` only for Builder-relevant work.
Use focused tests for focused changes; reserve full quality gates for an
explicit `/qg`, CI, or user request.

Push, merge, deletion, history rewrite, credentials, auth/env changes, paid
execution, and heavy dependencies remain approval-gated.
