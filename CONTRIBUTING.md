# Contributing to Kitty

Kitty's operating rules change as the product and agent tooling evolve. Do not
copy an old session checklist forward. Start from the current authorities.

## Before you change the repository

1. Read [`START_HERE.md`](START_HERE.md) and follow its cold-start checks.
2. Read [`AGENTS.md`](AGENTS.md), the authoritative repository change contract.
3. Load only the architecture, roadmap, mission, or reference material required
   by the task.
4. Check `workspace_global`, issue #490, and Builder ownership when the change
   could collide with another lane.
5. Base implementation work on a freshly verified remote `main` SHA in an
   isolated worktree. The canonical checkout is an observation/integration
   point, not the default editing workspace.

`docs/STANDUP.md` is retired. Historical standup material under `docs/archive/`
is not current instruction. Tool-specific files such as `CLAUDE.md` or
`CODEX.md` supplement `AGENTS.md`; they do not replace it.

## Repository map

- `gateway/` — Gateway product authority and backend domain code.
- `gateway/routes/` — FastAPI route projections.
- `gateway/kitty-chat/` — canonical native Kitty frontend.
- `tests/` — Python and repository contract tests.
- `docs/` — product, architecture, operating, and historical documentation.
- `data/` and `logs/` — runtime state/evidence, not source artifacts.

For the fuller current topology, use
[`docs/reference/CODEBASE_MAP.md`](docs/reference/CODEBASE_MAP.md).

## Change and verification rules

Keep one bounded concern per change and preserve established authority
boundaries. Never commit secrets or treat generated runtime files as source.
Run the narrowest deterministic checks that prove the changed behavior; runtime,
UI, launch, and environment claims also require corresponding live evidence.
Repository-wide gates are owned by [`docs/WORKFLOW.md`](docs/WORKFLOW.md) and CI,
not duplicated here.

Use the current model/reviewer policy in `AGENTS.md` and Builder routing docs.
Do not hard-code a preferred model or provider in contribution instructions.

## Publication

Push task branches, not `main`. Before publication or merge decisions, re-check
the exact PR head, current remote `main`, required checks, review evidence, and
unresolved threads. Follow `AGENTS.md` for approval boundaries and irreversible
actions.
