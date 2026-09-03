# Worktree Cleanup Report

Generated: 2026-09-01

## Scope

This report covers worktrees under `.worktrees/` in the canonical checkout.
Worktrees under `/private/tmp/`, `/private/var/.../opencode/`,
`/Users/jacobbrizinnski/orca/`, `/Users/jacobbrizinnski/Kitty-Audit-Sidecars/`,
and sibling project directories are excluded — they belong to other agents.

## Locked Worktrees

| Worktree | Branch | Lock Reason | Last Commit |
|----------|--------|-------------|-------------|
| `.worktrees/kitty-reliability-enhancements-20260830` | `feat/kitty-reliability-enhancements-20260830` | ChatGPT lane note | 2026-08-31 00:18 |
| `.worktrees/kittybuilder/kb_mtg5kau7_dfa1` | `kittybuilder/kb_mtg5kau7_dfa1` | initializing | 2026-08-30 14:03 |

## Top Cleanup Candidates

These meet multiple criteria: no upstream tracking, merged into main, 20+ hours stale.

| Worktree | Branch | Last Commit | Hours |
|----------|--------|-------------|-------|
| a2/builder-queue-deep-module | a2/builder-queue-deep-module | 2026-08-31 04:36 | ~20 |
| a3/builder-status-pure-read | a3/builder-status-pure-read | 2026-08-31 05:02 | ~19 |
| a5-image-module-rename | a5/image-module-rename | 2026-08-31 06:54 | ~17 |
| a6-memory-graph-one-entry | refactor/memory-graph-one-entry | 2026-08-31 03:35 | ~21 |
| agent-coordination-registry-20260831 | feat/agent-coordination-registry-20260831 | 2026-08-31 01:50 | ~22 |
| builder-validation-env-20260830 | fix/builder-validation-env-20260830 | 2026-08-30 15:04 | ~33 |
| builder-worker-python-runtime-20260830 | fix/builder-worker-python-runtime-20260830 | 2026-08-30 14:17 | ~34 |
| direct-builder-preflight-20260830 | fix/direct-builder-preflight-20260830 | 2026-08-30 17:25 | ~31 |
| fix-conversation-current-head-20260830 | fix/conversation-current-head-20260830 | 2026-08-30 19:15 | ~29 |
| kt-restore-01-20260831 | fix/kt-restore-replace-not-append-20260831 | 2026-08-31 01:59 | ~22 |
| reconcile-builder-recovery-main-20260830 | reconcile/builder-recovery-main-20260830 | 2026-08-31 00:37 | ~23 |
| chat-to-work-handoff-20260901 | feat/chat-to-work-handoff-20260901 | 2026-09-01 15:25 | ~8 (still recent) |
| context-platform-plan-20260901 | plan/context-platform-20260901 | 2026-09-01 04:44 | ~19 |
| dsh-execution-profiles-20260901 | feat/dsh-execution-profiles-20260901 | 2026-09-01 05:36 | ~18 |
| gar-lifecycle-hooks-20260901 | fix/gar-lifecycle-hooks-20260901 | 2026-09-01 08:00 | ~16 |
| gar-scope-retrieval-20260901 | feat/gar-scope-retrieval-20260901 | 2026-09-01 08:18 | ~16 |
| openviking-shadow-20260901 | feat/openviking-kb-sync | 2026-09-01 07:59 | ~16 |

## Builder-Managed Worktrees (a2-a6)

These are managed by the build system's `.worktrees/` convention. They have
no remote tracking and are purely local refactoring branches. Before removing:

- Check that `a2/`, `a3/`, `a4/`, `a5/`, `refactor/memory-graph-one-entry`
  branches have been fully merged into main and no Builder packet references them.

## KittyBuilder Worktrees

These 16 worktrees are managed by Builder itself. Some have `origin` tracking,
some are merged into main, some have no upstream. Builder manages the lifecycle.

| Worktree | Branch | Upstream | Merged into main | Last Commit |
|----------|--------|----------|------------------|-------------|
| kb_mtg5kau7_dfa1 | kittybuilder/... | origin | ✗ (LOCKED) | 2026-08-30 |
| kb_mtg94d5b_beb0 | kittybuilder/... | origin | ✗ | 2026-08-31 |
| kb_mtg9vdvk_afef | kittybuilder/... | origin | ✗ | 2026-08-30 |
| kb_mtgatvyi_340e | kittybuilder/... | NONE | ✗ | 2026-08-30 |
| kb_mth2nezq_9339 | kittybuilder/... | NONE | ✓ | 2026-08-31 |
| kb_mth5wuo2_a5f0 | kittybuilder/... | NONE | ✗ | 2026-08-31 |
| kb_mth5wuo3_c235 | kittybuilder/... | NONE | ✗ | 2026-08-31 |
| kb_mthq0n1f_6a36 | kittybuilder/... | NONE | ✓ | 2026-08-31 |
| kb_mthqaf98_2e38 | kittybuilder/... | origin | ✗ | 2026-08-31 |
| kb_mthv50ch_94f9 | kittybuilder/... | NONE | ✓ | 2026-08-31 |
| kb_mthv7qa8_a9bd | kittybuilder/... | NONE | ✗ | 2026-09-01 |
| kb_mthviknn_c2b2 | kittybuilder/... | origin [behind 60] | ✗ | 2026-09-01 |
| kb_mtiwmpcz_fe93 | kittybuilder/... | NONE | ✓ | 2026-09-01 |
| kb_mtiwmpd0_2a6c | kittybuilder/... | NONE | ✓ | 2026-09-01 |
| kb_mtiwmpd0_9a31 | kittybuilder/... | NONE | ✓ | 2026-09-01 |
| kb_mtiwmpd0_d968 | kittybuilder/... | NONE | ✓ | 2026-09-01 |

## Summary

- **2 locked worktrees** — one ChatGPT-owned, one Builder-initializing
- **~15 stale worktrees** (>15h, no upstream, mostly merged) in `.worktrees/`
- **16 Builder worktrees** — let Builder manage its own lifecycle
- **10 WOW worktrees** — have origin tracking, some [gone]; leave for now

## Next Steps

1. Confirm deletion on a case-by-case basis for the stale candidates above.
2. For a2-a6 worktrees, verify no Builder packet references them before removal.
3. For Builder-managed kittybuilder/* worktrees, do not touch.
4. For locked worktree `kitty-reliability-enhancements-20260830`, check if the
   ChatGPT lane is still active before removing.

