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

## Agent Rules

Before multi-file work, give a short plan. Prefer editing existing files over creating new structure. Use `docs/PROJECT_STATUS.md`, `docs/DECISIONS.md`, `docs/LEARNINGS.md`, and `docs/AGENT_HANDOFF.md` as the current sources of truth.
