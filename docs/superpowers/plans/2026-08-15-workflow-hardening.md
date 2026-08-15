# Workflow Hardening Execution Plan

**Goal:** Remove the manual/stale transitions around Builder delivery without creating another execution owner.

## 1. Review freshness
- Re-run the existing PR agent review on every PR head change.
- Replace any old review with a current-head pending marker before the model call.
- Fail the review job if the model cannot produce a current-head verdict; never leave stale approval-looking evidence.

## 2. Local hooks
- Add a real `scripts/hooks/pre-commit` fast safety gate for staged diff errors/conflict markers, private keys, macOS metadata, and TruffleHog secrets.
- Keep the existing CI-parity `pre-push` gate and block direct pushes to `main` unless an explicit emergency override is set.
- Wire the existing Claude catch-up and test-failure hooks that are currently unused.

## 3. Server enforcement
- Consolidate the disabled default-branch rulesets into one active rule requiring the six deterministic checks: pytest, lint, typecheck, hygiene, kitty-chat, browser-smoke.
- Keep model review advisory rather than a required paid check.

## 4. Post-merge continuation
- Reconcile merged PRs at the start of each supervisor tick so merged tasks become done and dependent packets become eligible before selection.
- Dispatch newly eligible work in the same tick; do not add a daemon or second queue.

## 5. Cleanup and docs
- Retire the obsolete issue-#127-as-authoritative-queue language.
- Remove only clean worktrees already merged to main; preserve dirty/unmerged work and the PR-Janitor lane.
- Verify main, hooks, review freshness, Builder reconciliation, and remaining worktree inventory.
