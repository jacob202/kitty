# PR Janitor Design

## Goal
Eliminate recurring PR publication/merge failures without making Jacob manually re-coordinate agents or creating a second execution system.

## Chosen approach
KittyBuilder owns a bounded PR Janitor loop. GitHub remains evidence/projection only. The janitor runs around Builder publication and merge using the existing Builder task/worktree, events, worker routing, and approval boundaries.

Two rejected alternatives:
- A write-capable GitHub Action repair bot: easy to trigger, but creates an execution path outside Builder and weakens durable ownership/evidence.
- A separate local PR-watcher daemon: preserves Mac access but creates another scheduler/state machine.

## Flow
1. Before publication, run deterministic safe repairs in the task worktree.
2. Run the same high-signal pre-push checks that currently block publication.
3. If checks still fail, return structured failure evidence to Builder for a bounded repair attempt instead of immediately pausing the initiative.
4. Retry publication after repair, with a hard cap of 3 janitor passes.
5. The direct `queue publish` escape hatch runs deterministic safe repair before push; semantic retries remain owned by the initiative loop.
6. After PR creation/update, record exact PR/head/check evidence and keep review SHA-bound.
6. At merge, keep the existing one-time stale-branch rebase/retry. Never auto-resolve semantic conflicts.
7. Exhaustion produces one durable blocker with attempts, failures, and next action.

## Deterministic repairs v1
Only obviously safe, repository-wide recurring fixes are automatic:
- `ruff check --fix` on the same Python surface as CI/pre-push;
- EOF/newline/style fixes covered by Ruff;
- stale generated review/evidence bindings are invalidated rather than trusted.

The janitor must not silently revert scope, edit secrets/auth/env, delete files, alter dependencies, or resolve content conflicts. Those remain repair-agent or operator decisions.

## Agent repair
When deterministic repair cannot clear a gate, Builder reuses its existing worker/repair machinery with the failing command, output tail, changed files, task contract, and current HEAD. A different reviewer still performs acceptance. The fixer never approves itself.

## State/evidence
Use existing Builder events/task state. Add janitor pass events rather than a new database or queue. Each event records pass number, head before/after, fixes applied, failed gate, and output tail. Maximum 3 passes per publication attempt.

## Acceptance
- A known Ruff-fixable publication failure is repaired and published without operator intervention.
- A non-fixable failure is surfaced as structured janitor evidence, not a generic `git push failed` string.
- No force-push is introduced in publication.
- Merge conflict behavior remains bounded and fail-loud.
- Focused tests prove fixed, unchanged, exhausted, and safety-boundary cases.
