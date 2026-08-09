# Kitty — Start Here

This is the canonical cold-start bootloader. It routes to authorities and
live evidence; it does not duplicate current state.

## Boot sequence

1. Confirm `pwd -P`, `git rev-parse --show-toplevel`, and
   `git worktree list --porcelain`. The worktree must share Git state with
   `~/Projects/kitty`; Desktop copies are invalid.
2. Inspect `git status --short --branch`, branch, HEAD, `origin/main`, and
   recent commits. Do not fetch, switch, stash, or clean merely to simplify
   output.
3. Run the receipt for the task class. Informational/planning work may use
   `./kitty context --agent --compact --skip-builder`; code or Builder work
   uses full `./kitty context --agent`. A failed, unknown, stale, or
   contradictory receipt remains unverified; handoff prose cannot repair it.
4. Read only the authority files required by the task, using the receipt's
   order. For code changes, use the complete order below.
5. Read `docs/ACTIVE_MISSION.md` when the task is product or implementation
   work. Confirm scope, approval, base SHA, evidence, and authorization.
6. Inspect Builder through supported read-only commands only when Builder
   state, execution ownership, or collision risk matters.
7. Immediately before mutation, re-check live branch/HEAD, scope, owner,
   authorization, and the exact files to change.

## Task routing

- Informational: run the receipt and load the directly relevant authority.
- Planning: add `docs/ROADMAP.md`, `docs/ACTIVE_MISSION.md`, and the current
  checkpoint only when relevant.
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
9. [`.claude/STATE.md`](.claude/STATE.md)
10. [`.claude/HANDOFF.md`](.claude/HANDOFF.md) — only if its identity is valid
<!-- kitty-reading-order:end -->

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
