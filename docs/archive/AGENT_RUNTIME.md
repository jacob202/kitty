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
- `.agent/session_logs/` is for generated local wrap-up logs (gitignored).
- Codex CLI runs concurrently from the desktop app. If `git status` shows files appearing or being modified while you are working, treat that as Codex mid-edit. Stash your work with a descriptive message and `git stash pop` after Codex lands its commit. Do not fight Codex for the same branch.

## Active Skills (as of 2026-06-20)

User-level skills are installed at `~/.claude/skills/` and symlinked to `~/.config/opencode/skills`, `~/.codex/skills`, and `~/.config/crush/skills` so they are available across tools. Single source of truth: `~/.claude/skills/`. New dotclaude skills came from `poshan0126/dotclaude` (cloned at `~/dotclaude`).

### Code review, PR, and merge

- `pr-review` — PR review with structured findings (recommended for new PRs).
- `pr` — PR creation helper.
- `merge` — merge workflow.
- `rebase` — rebase workflow.
- `commit` — commit message helper.
- `qg` — quality gate runner.
- `judge` — comparative judgement of options.

### Audit family (read-only code audits)

- `audit` (root), `audit-comments`, `audit-complexity`, `audit-correctness`, `audit-error-handling`, `audit-logs`, `audit-necessity`, `audit-patterns`, `audit-perf`, `audit-security`, `audit-structure`, `audit-tests`.
- Use the most specific one for the question. `audit` is the entry point.

### Plan, design, prompt

- `plan` — there are two `plan` skills. The repo's own `~/.claude/skills/plan/SKILL.md` is the canonical one for Kitty. The dotclaude one is reachable only via `~/dotclaude/skills/plan/` and is not symlinked to avoid the conflict.
- `design` — design exploration.
- `prompt` — prompt iteration.
- `refiner` — refine a draft.
- `ux` — UX review.
- `color-system` — color tokens.

### Meta and project

- `codemap` — project map.
- `find-skills` — discover other skills.
- `improve-skill` — iterate a skill.
- `seo-geo` — SEO/GEO review.
- `sparring` — adversarial sparring partner.
- `timesheet` — time tracking.
- `transformer` — content transformation.
- `worktree`, `worktree-clean` — git worktree helpers.

### Markdown reference docs (read directly, not a skill)

- `audit-workflow.md` — how to use the audit family.
- `conventional-commits.md` — commit message format.
- `migration-reconciliation.md` — migration planning.

### Plugins (Claude Code)

- `setupdotclaude@dotclaude` from the `poshan0126/dotclaude` marketplace (scope: user). Restart Claude Code to load. Repo-level `make agent-wrap` is the canonical wrap path; this plugin is a supplement, not a replacement.

### Disabled or superseded skills

- None yet. When a skill proves underperforming in this repo, mark it superseded in `docs/archive/` and remove the symlink; do not delete the original.

## Agent Boundaries

Agents may automate formatting, local tests, and focused bug fixes. Agents must ask before pushing, deleting, force-pushing, touching auth/secrets/env, or adding heavy dependencies.

