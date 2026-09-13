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
3. Prove `workspace_global` access by loading the shared Room Briefing first:
   `./kitty room briefing --as <identity> --session-id <current-session> --json`.
   The briefing is a scoped view of Kitty's shared orientation domain; clients
   must not rebuild assignment, KX, Builder, Git, runtime, presence, or GAR truth
   independently. Participant-wide direct messages are attention only unless
   exact structural correlation independently resolves the assignment. Presence
   is liveness only and never grants assignment or ownership. If the briefing
   resolves or identifies a durable locator for an exact thread or handoff, load
   that exact conversation with `room_thread` or `./kitty room thread <message_id> --json`.
   Use `./kitty room inbox --as <identity> --unread --direct-only --json` only
   to inspect unread direct attention/receipt items after briefing; MCP clients
   use `room_inbox(unread_only=True, direct_only=True)` for that same attention
   surface. Participant-wide directs remain attention, not assignment authority.
   Acknowledge only
   messages actually consumed. If the room or any required source is
   unavailable, keep that state explicit rather than treating it as empty
   success.
4. Use the shared orientation result to choose any additional context receipt:
   - For code work with a valid GAR continuation, use `./kitty context --agent
     --skip-legacy-continuity`; informational/planning work may add `--compact
     --skip-builder`.
   - If Room Briefing cannot resolve a continuation and the legacy checkpoint is
     genuinely required as a temporary fallback, run the strict `./kitty
     context --agent` receipt and use that checkpoint only when validation
     succeeds.
   - If GAR is unavailable, use the strict compatibility receipt and report the
     room as unavailable.
   A failed, unknown, stale, or contradictory required source remains
   unverified; handoff prose cannot repair it. Native cloud ChatGPT cannot know
   local Kitty state before invoking the local bridge, so the first Kitty work
   turn must invoke that bridge and obtain Room Briefing rather than assuming
   repository or room state.
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
- Completion: when a substantial assigned task is genuinely verified complete,
  automatically execute `.agents/skills/session-end/SKILL.md` before the final
  closeout response. Do not wait for the user to say `session end`; explicit
  `session end`, `wrap up`, or equivalent also triggers the same closeout. Do
  not close while work, review, CI, or required acceptance remains pending.

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
./kitty room briefing --as <identity> --session-id <current-session> --json
# If briefing identifies an exact handoff/thread, load it before mutation.
# Then use a legacy-skipping context receipt for a valid GAR continuation:
./kitty context --agent --compact --skip-builder --skip-legacy-continuity
# No GAR locator yet, or GAR unavailable and legacy fallback is required:
./kitty context --agent
```

Use `./kitty builder initiative doctor --json` only for Builder-relevant work.
Use focused tests for focused changes; reserve full quality gates for an
explicit `/qg`, CI, or user request.

Push, merge, deletion, history rewrite, credentials, auth/env changes, paid
execution, and heavy dependencies remain approval-gated.
