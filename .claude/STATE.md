# Session State — 2026-07-14 (cloud branch `claude/free-workers-token-efficiency-2m06xb`)

- Free workers are now a first-class launch surface: `./kitty builder
  initiative run[-packet] ... --free` wires the OpenCode adapter scripts as
  worker + reviewer (no hand-typed `--worker-command` JSON).
- Both adapter scripts now walk the zero-cost model ladder inside one
  attempt; fallback happens only on a clean failure (no result, no worktree
  change) so partial work is never built on. `KITTYBUILDER_MODEL(S)` /
  `KITTYBUILDER_REVIEW_MODEL(S)` override.
- New playbook: `docs/FREE_WORKERS.md` (linked from CLAUDE.md, quickstart,
  and the Orca setup doc).
- Verified: 466 builder-slice tests pass (incl. 5 new adapter ladder tests,
  5 new CLI preset tests); ruff clean; both scripts `bash -n` clean.

# Session State — 2026-07-12

## Branch

- `main` @ `1d2183f`, pushed to `origin/main`.
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

- `trust-lane-v1` has started at the queue level in packet order. TL-01
  (`kb_mrgw1v45_019b`) is claimed by `codex-trust-lane-v1-tl01` on its
  isolated Builder branch; implementation is not yet started in this root
  checkout.
- The root checkout has concurrent uncommitted Builder work. Preserve and do
  not stage it: `config/imagen/criteria/hard-gate.json`,
  `config/imagen/criteria/test-char.json`, `gateway/builder_loop.py`,
  `tests/test_builder_loop.py`, plus untracked `gateway/builder_context.py`
  and `tests/test_builder_context.py`.
- Active builder worktree:
  `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`, task
  `kb_mrh9ilha_f3d9`, currently modifies `gateway/next_step.py` and
  `tests/test_next_step.py`; do not clean or remove it.
- Untracked user scripts remain untouched:
  `scripts/kittybuilder_opencode_worker.sh` and
  `scripts/kittybuilder_opencode_reviewer.sh`.
- `fix/search-route-query-param` and all remote branches remain untouched.

## Verification

- Frontend: `npm test -- --run --maxWorkers=1` → 18 files / 129 tests passed;
  `npm run build` → passed.
- Full Python suite: 2,079 passed, 1 skipped, 8 failed. Failures are known
  local environment/dependency or timeout issues (`mem0`, `google.auth`,
  Chroma/runtime, and resume subprocess); this is not a clean green gate.
- Builder slice: 54 passed and 1 shared-queue lease-conflict failure; the
  failed case passed when rerun alone (`1 passed`).
- Browser smoke loaded onboarding and Home successfully. Core gateway routes
  returned 200, while LiteLLM/models, Chroma knowledge, and runtime freshness
  remained visibly degraded in this environment.
- `venv/bin/ruff check gateway/builder_loop.py gateway/builder_runner.py
  tests/test_builder_loop.py tests/test_builder_runner.py` → passed.

## Next actions

- Implement TL-01 in its isolated branch, then continue TL-02, TL-03, TL-04,
  and TL-05 in that order. Do not stage the concurrent root-checkout edits
  above.
- Start `trust-lane-v1` in the established packet order after the push.
- Later plan model usage across ChatGPT's available models by task, cost,
  latency, reliability, and privacy boundary.

## T2 (Jacob/Codex only — do not touch)

- Card A: UI binds 0.0.0.0 in `./kitty` + proxy injects gateway secret; SSRF
  in capture/knowledge routes.
- Card B: `agent_runner.py` / `task_runner.py` can false-complete tasks;
  `stop()` unreliable.
