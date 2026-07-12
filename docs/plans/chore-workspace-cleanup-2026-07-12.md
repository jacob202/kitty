# Workspace cleanup — 2026-07-12

## Goal

Recover unique Kitty work without pushing, remove stale local clutter safely,
archive external project material reversibly, and make KittyBuilder remove a
clean task worktree after a successful `done.txt` run.

## Files

- [NEW] `docs/plans/chore-workspace-cleanup-2026-07-12.md`
- [MOD] `.gitignore`
- [MOD] `gateway/builder_loop.py`
- [MOD] `gateway/builder_runner.py`
- [MOD] `tests/test_builder_loop.py`
- [MOD] `tests/test_builder_runner.py`
- [MOD] `.claude/STATE.md`
- [MOD] `.claude/HANDOFF.md`
- [DEL] tracked `tmp/IMG_0668.png`

External filesystem actions:

- Archive the backup tarball and extracted projects under
  `~/Archive/Projects-2026-07-12/`.
- Preserve Nautilus runtime artifacts under the same archive, then remove the
  stale local worktree and prune Git's worktree registry.
- Remove only approved local superseded branches/worktrees; leave remote refs,
  PR #151, active campaign worktrees, and the credential-bearing prototype
  branch untouched.

## Steps

- [ ] Create local rescue branches containing only the unique KB-S4 tests and
  orchestrator research document.
- [ ] Remove the tracked temporary image and ignore future `tmp/` contents.
- [ ] Archive external clutter and preserve Nautilus generated state before
  removing its stale worktree.
- [ ] Remove only disposable caches and the superseded clean UI branch.
- [ ] Update KittyBuilder so a successful loop removes its clean task worktree,
  while failed, dirty, or interrupted runs remain inspectable.
- [ ] Run targeted tests, lint the touched Python files, verify the staged
  commits, and update session state/handoff.

## Verification

- `python3.12 -m pytest tests/test_builder_loop.py tests/test_builder_runner.py -q`
- `venv/bin/ruff check gateway/builder_loop.py gateway/builder_runner.py tests/test_builder_loop.py tests/test_builder_runner.py`
- `git status --short --branch`
- `git worktree list --porcelain`
- `find ~/Archive/Projects-2026-07-12 -maxdepth 3 -type f -print`

## Guardrails

- No push, remote branch deletion, PR mutation, secret inspection, or deletion
  of the prototype branch containing `.env.bak`.
- Builder cleanup is success-only and must preserve the existing fail-loud
  refusal for dirty worktrees.
- Runtime `data/`, `.env*`, and active worktrees are not disposable caches.
