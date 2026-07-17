# Kitty — Start Here

This is the stable cold-start bootloader for agents and future Jacob. It routes
to authorities; it does not describe current state itself.

## Boot sequence

1. **Verify the checkout.** Confirm `pwd -P`, `git rev-parse --show-toplevel`,
   and `git worktree list --porcelain`. The worktree must share Git state with
   the canonical checkout at `~/Projects/kitty`; Desktop copies are invalid.
2. **Inspect Git.** Read branch, HEAD, `origin/main`, recent commits, and the
   complete working-tree status. Do not fetch, switch, stash, or clean merely
   to make the state look simpler.
3. **Generate a receipt.** Run `./kitty context --agent`. A failed receipt or
   explicit unknown stays failed/unknown until verified; do not repair it with
   handoff prose.
4. **Read canonical documents in order.** Use the marked list below and the
   authority map carried in the receipt.
5. **Read the active mission.** Confirm approval, scope, base SHA, evidence
   plan, and human authorization boundaries.
6. **Inspect Builder when relevant.** Use supported `./kitty builder ... --json`
   commands or the bounded status projection. An absent DB is unknown/unused,
   not an empty success fabricated by the agent.
7. **Reject stale context.** A mismatched SHA, branch, worktree, PR state,
   completed next action, broken link, or conflicting authority invalidates the
   affected checkpoint.
8. **Verify before acting.** Re-check the live fact, allowed scope, and approval
   boundary immediately before any mutation.

## Canonical reading order

<!-- kitty-reading-order:start -->
1. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) — where each kind of truth lives.
2. [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) — product purpose and life-first outcome.
3. [`AGENTS.md`](AGENTS.md) — engineering doctrine and safety rules.
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — current runnable system and boundaries.
5. [`docs/DECISIONS.md`](docs/DECISIONS.md) — accepted ADR index and supersession.
6. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — shipped state and verified limitations.
7. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) — the one approved active mission.
8. [`.claude/STATE.md`](.claude/STATE.md) — current branch checkpoint and next action.
9. [`.claude/HANDOFF.md`](.claude/HANDOFF.md) — continuation only when marked valid.
<!-- kitty-reading-order:end -->

## Core commands

```bash
git status --short --branch
./kitty context --agent
./kitty doctor --json
./kitty builder initiative doctor --json
python3.12 -m pytest tests/ -q --tb=short
```

Voice/persona remains owned by `config/SOUL.md`. Push, merge, deletion, history
rewrite, secrets/auth/env changes, paid execution, and heavy dependencies still
require Jacob's explicit approval.
