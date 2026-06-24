# Agent Runtime

**Date:** 2026-06-24

This doc covers the repo-owned agent surface that shapes a session before product code changes: front-door docs, Claude runtime files, hooks, and wrap-up artifacts.

## Entry Protocol

1. Confirm repo: `/Users/jacobbrizinski/Projects/kitty`.
2. Run `git status --short --branch`.
3. Read `START_HERE.md` and `docs/PROJECT_STATUS.md`.
4. If you are touching docs, hooks, or agent workflow, read `.claude/settings.json` and `.claude/profile.md`.
5. Pull in `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/LEARNINGS.md`, and any phase-plan doc only when the task needs them.

## Front-Door Files

- `AGENTS.md` — repo contract and safety gates. Highest priority.
- `START_HERE.md` — single orientation entrypoint.
- `CLAUDE.md` and `CODEX.md` — tool-specific wrappers. They may add nuance, but they must not contradict `AGENTS.md` or `START_HERE.md`.
- `docs/PROJECT_STATUS.md` — live branch truth.
- `docs/AGENT_HANDOFF.md` — latest continuation package.
- `.claude/profile.md` — short Claude session-start context. Keep it durable; branch-specific details belong in `docs/PROJECT_STATUS.md`.
- `.claude/settings.local.example.json` — checked-in shape for optional host-local Claude overrides.
- `.claude/rules/code-quality.md` — concise style and anti-default guardrails.

## Hook Surface

Canonical repo config lives in `.claude/settings.json`.

- `sessionStart` prints `.claude/profile.md`.
- `SessionStart` hooks run `.claude/hooks/session-start.sh` for live git context and `.claude/hooks/suggest-catchup.sh` for recent-handoff nudges.
- `PreToolUse` for `Bash` runs `scan-secrets.sh` and `block-dangerous-commands.sh`.
- `PreToolUse` for `Write|Edit|NotebookEdit` runs `scan-secrets.sh` and `warn-large-files.sh`.
- `PostToolUse` for `Write|Edit|NotebookEdit` runs `notify.sh` plus a quick `ruff` check on edited Python files.
- `PostToolUse` for `Bash` runs `suggest-on-test-fail.sh` for failing test commands.

`.claude/settings.local.json` is now an ignored host-local override. Use `.claude/settings.local.example.json` as the checked-in shape, and keep machine-specific allowances out of canonical repo state.

## Repo-Local Skills

Repo-owned Claude skills currently live in `.claude/skills/`:

- `catchup`
- `debug-fix`
- `second-opinion`
- `tdd-loop`

User-level/global skills may exist, but this doc should only list repo-owned runtime surfaces.

## Exit Protocol

Run:

```bash
make agent-wrap
```

Then fill in the generated session log with:

- branch and commit
- files changed
- tests run and exact result
- unresolved dirty work
- next concrete action

## Other Runtime Artifacts

- `.git/hooks/pre-commit` blocks staged macOS metadata and runs pytest.
- `.mcp.json` is local and ignored; do not commit absolute MCP paths.
- `.agent/session_logs/` is for generated local wrap-up logs (gitignored).
- Codex CLI can run concurrently from the desktop app. If `git status` changes underneath you, pause, re-check, and avoid fighting another agent for the same files.

## Agent Boundaries

Agents may automate formatting, local tests, and focused bug fixes. Agents must ask before pushing, deleting, force-pushing, touching auth/secrets/env, or adding heavy dependencies.
