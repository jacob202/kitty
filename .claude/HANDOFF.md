# Recovery Handoff — 2026-07-15

## Current truth

- Use `.worktrees/reconcile-builder-campaign` on
  `reconcile-builder-campaign` for campaign recovery. Do not use the shared
  root checkout while its Engineering Leverage worker is active.
- `docs/roadmap/campaign_state.json` is green. Builder doctor supports linked
  nested worktrees, documentation lint validates the governed foundational
  corpus, repository-relative references resolve correctly, and SYSTEM_MAP is
  current (47 focused tests; real doctor: 13 pass, 1 expected warning, 0 fail).
- P1-01 and P1-02 are integrated and independently approved here. P1-03
  remains blocked on the required owner architecture decision about the
  measurability heuristic boundary; its candidate also mixes an unrelated
  protected-path authority rewrite. Do not integrate it until that policy is
  explicit.
- P1-01 is `790e71c`; P1-02 is `014eeb9`; campaign-state and handoff truth is
  `acdc5b3`. Validation: 131 focused initiative/doctor/docs tests, Ruff,
  documentation lint, system-map freshness, and Builder doctor (13 pass,
  1 expected first-run warning). The broad `tests/test_builder_*.py` slice did
  not finish in this environment, so it is not a green gate yet.
- P1-05 is `2fc061b` on `codex/campaign-p1-05`. It adds optional
  `forbidden_changes` contract validation and rejects overlap with
  `allowed_paths`; runtime mutation detection remains P3-02. Its independent
  review approved the normalized-path implementation; 34 scope/contract tests,
  Ruff, mypy, and docs lint pass.
- `f4a0047` on `codex/reconcile-phase2-p104` cleanly transplants the canonical
  branch-lease and worker-identity primitives; 26 focused identity tests pass,
  but its independent review is pending. P1-04 must not globally reconcile
  every open attempt until attempt creation is atomically bound to a lease and
  every terminal path releases only its own lease.
- `feat/campaign-alpha-phase-2-integration` contains the canonical committed
  branch-lease/identity work. The root checkout's uncommitted Phase 2 lease
  patch is preserved in `stash@{0}` and must be compared with that branch,
  not continued in place.

## Verified evidence

- `tests/bench/` passed 11 tests on the leverage branch before it was committed.
- P1-03 candidate scope tests: `18 passed`.
- `python3 scripts/docs_lint.py`: passed across 45 governed documents.
- `python3 scripts/docs_system_map.py --check`: passed.
- `./kitty builder initiative doctor --json`: 13 pass, 1 expected
  worktree-root warning, 0 fail in the nested recovery worktree.

## Next action

Finish the independent review of `f4a0047`, then implement and test atomic
lease-plus-attempt lifecycle wiring before P1-04 global reconciliation. Do not
mark P1-03 complete without the owner policy decision, and do not mix the root
checkout's Phase 2 patch into P1.

# Handoff — 2026-07-12

## TL;DR

Workspace cleanup is merged into local `main` at `2b77f6b`. The Fable branch
was already an ancestor of main, so no artificial merge commit was created.
Builder cleanup, temporary-file hygiene, branch rescue, external archiving,
and Nautilus removal are finished. Verification is complete with documented
environment failures; main is ready for the authorized push.

## Resume

1. Preserve the active worktree
   `.worktrees/kittybuilder/kb_mrh9ilha_f3d9`; it is running task
   `kb_mrh9ilha_f3d9` and has modified `gateway/next_step.py` plus
   `tests/test_next_step.py`.
2. Treat `scripts/kittybuilder_opencode_worker.sh` and
   `scripts/kittybuilder_opencode_reviewer.sh` as user work; they are
   intentionally untracked and were not modified by this cleanup.
3. `trust-lane-v1` is started at the queue level: TL-01 is claimed on its
   isolated Builder branch. Implement TL-01, then proceed TL-02 → TL-03 →
   TL-04 → TL-05; leave the T2 `0.0.0.0` binding and SSRF work visible and
   separate.
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

- Frontend tests: 18 files / 129 passed; production build passed.
- Full Python suite: 2,079 passed, 1 skipped, 8 failed on local optional
  dependencies, Chroma/runtime, and resume timeout conditions.
- Builder slice: 54 passed, 1 shared-queue lease-conflict failure; isolated
  rerun of that failure passed.
- Browser smoke reached onboarding and Home; core routes returned 200, with
  LiteLLM/models, Chroma knowledge, and runtime freshness visibly degraded.
- Ruff on all touched builder files: passed.
- Active dependencies and runtime data were intentionally retained.

## T2 (Jacob/Codex only)

- Card A: UI binds 0.0.0.0; proxy injects gateway secret; SSRF in
  capture/knowledge.
- Card B: `agent_runner.py` / `task_runner.py` false-complete states;
  `stop()` unreliable.
