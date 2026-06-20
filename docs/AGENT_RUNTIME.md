# Agent Runtime

**Date:** 2026-06-20

## Entry Protocol

1. Confirm repo: `/Users/jacobbrizinski/Projects/kitty`.
2. Run `git status --short --branch`.
3. Read `START_HERE.md` and `docs/PROJECT_STATUS.md`.
4. If work may touch architecture, read `docs/DECISIONS.md`.
5. If work may repeat a known mistake, read `docs/LEARNINGS.md`.

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

## Hooks And Tools

- `.git/hooks/pre-commit` blocks staged macOS metadata and runs pytest.
- The current pre-commit hook has an unreachable code-review-graph block after `exit 0`; fix in a dedicated tooling pass.
- `.mcp.json` is local and ignored; do not commit absolute MCP paths.
- `.agent/session_logs/` is for generated local wrap-up logs.

## Agent Boundaries

Agents may automate formatting, local tests, and focused bug fixes. Agents must ask before pushing, deleting, force-pushing, touching auth/secrets/env, or adding heavy dependencies.
