# Session State — hardening sweep merged, mypy fixed, queue-doctor merged

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-25T09:45:00Z",
  "head_sha": "16b48a5",
  "branch": "main",
  "worktree": ".",
  "status": "complete",
  "completed_items": [
    "Verified 7 pre-session claims",
    "Step 1: db pragmas (WAL/busy_timeout/foreign_keys/sync)",
    "Step 2: subprocess timeout= (7 calls)",
    "Step 3: asyncio.to_thread (5 builder action handlers)",
    "Step 4: bare-except → logger (5 locations)",
    "Step 5: CI supply-chain (pip-audit, bandit, npm audit, dependabot)",
    "Fixed pre-existing bugs: repairs.py undefined vars, duplicate test",
    "Fixed 22 pre-existing mypy errors across 7 files",
    "Created .kitty_cheatsheet.sh (terminal launch cheatsheet)",
    "Added kitty launch alias to ./kitty script",
    "Fixed gh auth setup-git SSH→HTTPS insteadof config trap",
    "PR #236 (hardening-sweep → main) rebase-merged",
    "PR #235 (feat/builder-queue-doctor → main) rebase-merged",
    "git push succeeded, origin/main stable"
  ],
  "blockers": [
    "CI typecheck still fails — pip install mypy types-requests needs more stubs",
    "CI hygiene fails — vulture/lychee/deptry pre-existing findings",
    "Hardening-sweep branch still local, not deleted"
  ],
  "next_action": "Fix CI typecheck by adding missing stubs to tests.yml, then delete hardening-sweep branch",
  "invalidation_conditions": ["HEAD changes beyond 16b48a5"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint
`main` at `16b48a5` — all 5 hardening steps + mypy fixes + queue doctor merged and pushed to `origin/main`. Working tree clean.

## Lessons applied
- `gh auth setup-git` creates an `insteadof` config that silently rewrites SSH URLs to HTTPS — diagnose push failures by checking `git config --global --list | grep insteadof`
- `BackendRegistry.list` method shadows builtin `list` → mypy `valid-type` error on `list[str]` annotations. Fix: rename method.
- Homebrew mypy (`/opt/homebrew/bin/mypy`) doesn't see venv stubs; always use `venv/bin/mypy` in this project.
- Lazy imports (`from x import y` inside function body) suppress module-level import errors but make them invisible until runtime — tradeoff.
