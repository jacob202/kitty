# Session State — 2026-07-12

## Branch

- `codex/workspace-cleanup-20260712` based on `main` @ `329859b`.
- No remote branch or PR has been created; nothing was pushed.

## Done this session

- `dbee71a`: successful KittyBuilder loop runs remove their worktree when the
  worker leaves exactly the ephemeral untracked `done.txt` marker; failed,
  interrupted, dirty, or marker-less runs remain inspectable.
- `f25e79e`: stopped tracking `tmp/IMG_0668.png` and added `tmp/` to
  `.gitignore`.
- `44c1fdc`: recorded the cleanup plan.
- Preserved unique work locally on:
  - `codex/recover-kb-s4-merge-tests` (`8bf3bab`, 135 tests)
  - `codex/recover-orchestrator-research` (`5901a3a`, research document)
- Retired the stale local KB-S4 and superseded UI branches. The credential-
  bearing `claude/kitty-prototype-sprint-srs5bl` branch remains untouched.
- Archived external project clutter under
  `/Users/jacobbrizinski/Archive/Projects-2026-07-12/` and removed Nautilus
  through Orca after preserving its Git bundle and runtime state.
- Removed disposable root caches and `.next`; kept active dependencies,
  runtime data, secrets, and active worktrees.

## In flight / preserve

- Active builder worktree:
  `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`, task
  `kb_mrh9ilha_f3d9`, currently modifies `gateway/next_step.py`; do not clean
  or remove it.
- Untracked user scripts remain untouched:
  `scripts/kittybuilder_opencode_worker.sh` and
  `scripts/kittybuilder_opencode_reviewer.sh`.
- `fix/search-route-query-param` and all remote branches remain untouched.

## Verification

- `python3.12 -m pytest tests/test_builder_loop.py tests/test_builder_runner.py
  -q` → 55 passed.
- `venv/bin/ruff check gateway/builder_loop.py gateway/builder_runner.py
  tests/test_builder_loop.py tests/test_builder_runner.py` → passed.

## Next actions

- Decide whether to publish the two rescue branches; pushing remains gated.
- Later plan model usage across ChatGPT's available models by task, cost,
  latency, reliability, and privacy boundary.

## T2 (Jacob/Codex only — do not touch)

- Card A: UI binds 0.0.0.0 in `./kitty` + proxy injects gateway secret; SSRF
  in capture/knowledge routes.
- Card B: `agent_runner.py` / `task_runner.py` can false-complete tasks;
  `stop()` unreliable.
