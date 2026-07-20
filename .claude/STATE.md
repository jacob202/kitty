# Session State — 2026-07-15 (Builder campaign recovery)

- Campaign recovery still lives on `reconcile-builder-campaign` in
  `.worktrees/reconcile-builder-campaign`; the shared root checkout remains
  active on `chore/engineering-leverage-phase-8-9` and must not be used for
  Builder execution.
- Current branch: `codex/reconcile-phase2-p104`.
- The Phase 2 identity hardening is committed as `85ede59`
  (`fix(builder): harden branch lease identity checks`) and the remaining
  lease lifecycle wiring is committed as `b8e0287`
  (`fix(builder): bind attempts to branch leases`).
- The cross-initiative stale-attempt reconciliation packet is committed as
  `bd45539` (`fix(builder): reconcile stale attempts globally`).
- P1-6 is implemented in the isolated worktree: the runner now checks
  `allowed_paths` on each heartbeat, terminates a live worker on in-flight
  scope expansion, and preserves the violating path snapshot in the final
  report.
- Verified on the isolated worktree: `tests/test_builder_runner.py -k scope`
  passed (8 tests), and `ruff check` passed. The broader runner suite did not
  produce a terminal summary in this recovery session; re-run it before
  publication. `mypy` still reports the existing runner test typing noise that
  was already present before this change.
- Branch attempts now claim a packet lease inside the same transaction as the
  attempt row, and terminal/reconciled attempts release that lease again.
- In flight: P1-3 remains blocked on the owner architecture decision.
- `f4a0047` now has independent approval. The allowlist hardening keeps the
  fail-closed behavior explicit if packet scope data is missing, malformed, or
  unsafe.
- The preserved root Phase 2 patch is reference-only. Its broad exception
  swallowing around lease release violates fail-loud and must not be copied.
- P1-01, P1-02, and P1-05 remain as previously recorded; keep the current root
  checkout edits and the active Builder worktree separate from this lane.
- The free-worker path is documented and available on this base via `--free`
  plus the OpenCode adapter scripts. Do not assume any deeper router changes
  until they are verified in the active branch.

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
