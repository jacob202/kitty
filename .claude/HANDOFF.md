# Handoff — 2026-07-12

## TL;DR

Workspace cleanup is complete on local branch
`codex/workspace-cleanup-20260712`. Builder cleanup, temporary-file hygiene,
branch rescue, external archiving, and Nautilus removal are finished. Nothing
was pushed.

## Resume

1. Preserve the active worktree
   `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`; it is running task
   `kb_mrh9ilha_f3d9` and has modified `gateway/next_step.py` plus
   `tests/test_next_step.py`.
2. Treat `scripts/kittybuilder_opencode_worker.sh` and
   `scripts/kittybuilder_opencode_reviewer.sh` as user work; they are
   intentionally untracked and were not modified by this cleanup.
3. If publication is requested, review and push the rescue branches separately:
   `codex/recover-kb-s4-merge-tests` and
   `codex/recover-orchestrator-research`.
4. The next planned task is a model-usage map for ChatGPT's available models,
   matching model strengths to Kitty tasks and routing rules.

## Preserved / archived

- `claude/kitty-prototype-sprint-srs5bl` remains because it contains a
  committed `.env.bak`; do not delete or inspect it without an explicit secret-
  handling decision.
- `/Users/jacobbrizinski/Archive/Projects-2026-07-12/` contains the backup
  tarball, extracted projects, Nautilus Git bundle, and Nautilus runtime state.
- PR #151 and all remote branches remain untouched.

## Verification

- Builder slice: 55 passed.
- Ruff on all touched builder files: passed.
- Active dependencies and runtime data were intentionally retained.

## T2 (Jacob/Codex only)

- Card A: UI binds 0.0.0.0; proxy injects gateway secret; SSRF in
  capture/knowledge.
- Card B: `agent_runner.py` / `task_runner.py` false-complete states;
  `stop()` unreliable.
