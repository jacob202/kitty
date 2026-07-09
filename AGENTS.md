# Repository Guidelines

## Prime Directive

Fail loud, never mask. Raise errors with clear causes; do not swallow exceptions, return fake defaults, or add silent fallbacks. External calls may retry with a visible warning, then must raise the real error with useful context.

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

## Kitty Builder (Layer 1A — coordination only)

Safe, read-only coordination commands. No autonomous loops, agent spawning, or budget enforcement yet.

- `python3.12 -m gateway.builder_cli brief <task>` — print a repo brief (branch, dirty files, task context)
- `python3.12 -m gateway.builder_cli contract validate <path>` — validate a JSON/markdown build contract
- `./kitty builder brief <task>` — alias if installed as a console script
- `./kitty builder contract validate <path>` — alias if installed as a console script

Disabled commands (`run`, `loop`, `repl`, `delegate`) return a clear "not enabled" message.

## Agent Rules

Before multi-file work, give a short plan. Prefer editing existing files over creating new structure.

### Session state (read on start, update before stopping)

- Read `.claude/HANDOFF.md` and `.claude/STATE.md` at the start of every session.
- Update `.claude/STATE.md` before stopping with: current branch, done items, in-flight work, blockers, and next actions.
- Write `.claude/HANDOFF.md` at the end of any session that leaves unfinished work.
