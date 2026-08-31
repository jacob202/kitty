# KB payload staged (2026-08-31, ~/kb unavailable)

`~/kb` does not exist in this remote/cloud session (it is Jacob's Mac-only
store). Staging the reusable findings here per the session-end fallback.
Not promoted to `~/kb/wiki/` — do that on a session where `~/kb` is present,
or fold directly into canonical docs if these prove durable.

## Finding 1: CI's ruff lint job does not cover all of `scripts/`

**Source:** interactive session, 2026-08-31, Sonnet 5, closing out PR #722.
**Why it matters:** running `ruff check` (or any linter) against the whole
repo tree during a PR fix will surface dozens of pre-existing violations in
files CI never actually lints, producing a false read that a branch is
dirtier than it is.
**Verified:** `.github/workflows/tests.yml:162` runs exactly
`ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py`
— not `scripts/` as a whole. Confirmed by running both the full-tree command
(47 errors, mostly in unrelated files like `scripts/vibe_session.py`) and the
exact CI-scoped command (0 errors) against the same tree.
**Rule:** when fixing a lint failure for a PR, always read the workflow file
for the exact lint invocation before trusting a broader local run.

## Finding 2: a command containing `--force` anywhere is blocked, not just `git push --force`

**Source:** same session.
**Why it matters:** chaining `git worktree remove --force` after a plain
`git push` in one shell command tripped the harness's force-push guard, even
though the push itself carried no force flag. The guard appears to
string-match the whole command line, not just the git subcommand being run.
**Verified:** `git push origin X:Y && git worktree remove <path> --force`
was blocked with "force push is not allowed"; splitting the two commands let
the identical push succeed immediately.
**Rule:** never combine a `git push` with any other command containing
`--force` in the same shell invocation in this environment — run them
separately.

## Carried recommendation resolved (drop, don't re-carry)

The `.claude/STATE.md` recommendation `dead-eslint-config` (deferred 3x since
2026-08-29, asking to delete `gateway/kitty-chat/eslint.config.mjs` or
restore its dependencies) is now moot: the file was already deleted on
`main` in commit `b2bbe58` ("feat(work): make Work a place you can do
work", 2026-08-29). `test -f gateway/kitty-chat/eslint.config.mjs` now
exits 1. Nothing left to do — drop this recommendation instead of carrying
a 4th deferral.
