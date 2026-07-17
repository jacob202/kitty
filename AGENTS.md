# Repository Guidelines

## Prime Directive

Fail loud, never mask. Raise errors with clear causes; do not swallow exceptions, return fake defaults, or add silent fallbacks. External calls may retry with a visible warning, then must raise the real error with useful context.

## Cold-start bootloader

Before acting, execute the bootloader in `START_HERE.md`. At minimum:

1. verify this worktree belongs to the canonical `~/Projects/kitty` checkout;
2. inspect live Git state;
3. run `./kitty context --agent` and reject any stale or contradictory receipt;
4. follow the receipt's canonical reading order and authority map;
5. read `docs/ACTIVE_MISSION.md` and the current session checkpoint;
6. inspect Builder through supported interfaces when execution state matters;
7. treat handoffs and prose as invalid when live evidence disagrees; and
8. verify relevant facts and authorization before mutation.

## Project Structure

Kitty is a local-first personal AI companion. Backend code lives in `gateway/`, with FastAPI routes under `gateway/routes/` and path constants in `gateway/paths.py`. The main UI is `gateway/kitty-chat/` (Next.js). Tests live in `tests/`. Product, architecture, and planning docs live in `docs/`. Runtime data and logs live in `data/` and `logs/` and must not be committed.

## Commands

- `./kitty up`: start Gateway and LiteLLM locally.
- `./kitty down`: stop local services.
- `./kitty status`: show process and health status.
- `./kitty doctor --json`: run preflight checks.
- `python3.12 -m pytest tests/ -q --tb=short`: run the default Python suite.
- `cd gateway/kitty-chat && npm run build`: verify the production UI build.
- `cd gateway/kitty-chat && npm test`: run frontend tests.
- `make agent-wrap`: write a session wrap-up template to `.agent/session_logs/`.

## Style

Match the existing file before introducing new patterns. Python uses 4-space indentation, explicit errors, and small readable functions. TypeScript/React uses functional components and clear prop names. Comment the why, not the obvious what. Keep diffs focused; do not reformat unrelated code.

## Testing

Use targeted tests while developing, then run the relevant full slice before claiming completion. UI changes need `npm test` and `npm run build` in `gateway/kitty-chat/`. Launch, auth, port, or env changes also need `./kitty status` and `./kitty doctor --json`.

## Git and PRs

Use small Conventional Commit messages such as `fix(auth): fail closed`. Never push, force-push, rewrite history, delete files, touch secrets/auth/payments/env, or add heavy dependencies without explicit confirmation. PRs should state user-facing impact, verification, skipped checks, and screenshots for visible UI changes.

Before any `gh` command or `git push`, check whether `GITHUB_TOKEN` is set. If `env -u GITHUB_TOKEN gh auth status` succeeds, run GitHub commands with `env -u GITHUB_TOKEN` so a stale ambient token cannot override keyring authentication. Never print token values.

Before merging a PR, read the Actions **check runs** and confirm each required job is `success` — not just the combined commit `status`. They are different GitHub surfaces; a green `status` (e.g. a review bot) can hide failing lint/typecheck/pytest check runs. A broken file reached `main` this way once (see `docs/LEARNINGS.md` L-CAND-6). After any non-trivial merge, compile/import the touched files before declaring done.

## KittyBuilder execution control plane

KittyBuilder has durable initiatives, packets, queue state, leases, attempts,
isolated worker runs, validation/review, recovery, budgets, publication rails,
and a bounded read-only status projection. Use `./kitty builder --help` and
`docs/KITTYBUILDER_QUICKSTART.md` for the supported surface; use
`./kitty builder initiative doctor --json` before execution-sensitive work.

Builder owns execution state, not product intent. The accepted boundary is the
versioned, authorized Mission in ADR 0017. This repository does not yet permit
Kitty to submit that Mission autonomously. Never infer Builder state from
handoff prose, worker output, or UI emptiness, and never join its SQLite tables
into another state machine.

### Orca/OpenCode Build Train

Use Orca worktrees for isolated KittyBuilder work. Run
`scripts/orca_worktree_setup.sh` as the Orca setup hook for this repo, and keep
`docs/KITTYBUILDER_ORCA_SETUP.md` as the operating guide.

Default to OpenCode for planning, implementation, packaging, and normal scoped
review. Reserve Codex for high-risk safety reviews involving queue state,
concurrency, auth/secrets/env, destructive operations, or blocked escalation.

Do not let the same worker approve its own work. T0 work may proceed
automatically, T1 work needs a separate model approval, and T2 work still needs
Jacob: push, merge, deletes, auth/secrets/env, paid or heavy dependencies, and
broad scope changes.

## Agent Rules

Before multi-file work, give a short plan. Prefer editing existing files over creating new structure.

### Session state (read on start, update before stopping)

- Read `.claude/HANDOFF.md` and `.claude/STATE.md` at the start of every session.
- Update `.claude/STATE.md` before stopping with: current branch, done items, in-flight work, blockers, and next actions.
- Write `.claude/HANDOFF.md` at the end of any session that leaves unfinished work.
