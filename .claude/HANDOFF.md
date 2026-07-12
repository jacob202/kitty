# Handoff — 2026-07-12

## TL;DR

Workspace cleanup is merged into local `main` at `2213960`. The Fable branch
was already an ancestor of main, so no artificial merge commit was created.
Builder cleanup, temporary-file hygiene, branch rescue, external archiving,
and Nautilus removal are finished. Main is ready for verification and push.

## Resume

1. Preserve the active worktree
   `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`; it is running task
   `kb_mrh9ilha_f3d9` and has modified `gateway/next_step.py` plus
   `tests/test_next_step.py`.
2. Treat `scripts/kittybuilder_opencode_worker.sh` and
   `scripts/kittybuilder_opencode_reviewer.sh` as user work; they are
   intentionally untracked and were not modified by this cleanup.
3. After merged-main verification and push, start `trust-lane-v1` in packet
   order; leave the T2 `0.0.0.0` binding and SSRF work visible and separate.
4. The next planned task is a model-usage map for ChatGPT's available models,
  matching model strengths to Kitty tasks and routing rules.

## Preserved / archived

- `claude/kitty-prototype-sprint-srs5bl` remains because it contains a
  committed `.env.bak`; do not delete or inspect it without an explicit secret-
  handling decision.
- `/Users/jacobbrizinski/Archive/Projects-2026-07-12/` contains the backup
  tarball, extracted projects, Nautilus Git bundle, and Nautilus runtime state.
- PR #151 and all remote branches remain untouched.
- The final Fable launch config is portable and loopback-only. An intermediate
  historical commit contained an absolute worktree path, but the tip fixed it;
  history was not rewritten.

## Verification

- Builder slice: 55 passed.
- Ruff on all touched builder files: passed.
- Active dependencies and runtime data were intentionally retained.

## T2 (Jacob/Codex only)

- Card A: UI binds 0.0.0.0; proxy injects gateway secret; SSRF in
  capture/knowledge.
- Card B: `agent_runner.py` / `task_runner.py` false-complete states;
  `stop()` unreliable.
