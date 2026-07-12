# Session State — 2026-07-12

## Branch

- `main` @ `2213960`, six local cleanup commits ahead of `origin/main`.
- `origin/docs/fable-context` is already an ancestor of `main`; no merge
  commit was needed.

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
- Reviewed the Fable session commits: final `.claude/launch.json` is relative
  and loopback-only; no secrets or generated browser artifacts are present in
  the final snapshot. One intermediate commit had an absolute worktree path,
  corrected by the Fable tip without rewriting history.

## In flight / preserve

- Active builder worktree:
  `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`, task
  `kb_mrh9ilha_f3d9`, currently modifies `gateway/next_step.py` and
  `tests/test_next_step.py`; do not clean or remove it.
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

- Run merged-main verification, then push `main` with ambient GitHub tokens
  removed from the environment.
- Start `trust-lane-v1` in the established packet order after the push.
- Later plan model usage across ChatGPT's available models by task, cost,
  latency, reliability, and privacy boundary.

## T2 (Jacob/Codex only — do not touch)

- Card A: UI binds 0.0.0.0 in `./kitty` + proxy injects gateway secret; SSRF
  in capture/knowledge routes.
- Card B: `agent_runner.py` / `task_runner.py` can false-complete tasks;
  `stop()` unreliable.
