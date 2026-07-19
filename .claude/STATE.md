# Session State — Lead Run 2026-07-19 (Claude as project lead, one-shot)

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-19T00:00:00Z",
  "head_sha": "92303efbbde0dd91293fd3fd5ad3ef2507597a0b",
  "branch": "main",
  "worktree": ".",
  "status": "running",
  "completed_items": [
    "TH-01 recovered earlier (PR #191, open), TH-02 recovered + validated (PR #192, CI green), scope-gate residue fix (PR #193, CI green)"
  ],
  "blockers": [],
  "next_action": "CP1: merge green PRs (#191 if green, #192, #193), true-up builder DB rows; then CP2: implement TH-03 CI ratchet; then CP3+: P027 packets in queue order",
  "invalidation_conditions": [
    "HEAD changes outside this lead run's own merges/commits",
    "a pull request changes state outside this run"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Lead run plan (checkpoints)

Jacob delegated project lead 2026-07-19: "take us as far as you can go in one
shot" with clear checkpoints. Each CP updates this file when reached. If this
run dies mid-flight, resume at the first unchecked CP.

- [x] CP0 — this plan written
- [x] CP1 — #191/#192/#193 all merged to main (found already merged).
      Fixed live bug found en route: gh >= 2.80 removed `merged` JSON field,
      breaking sync-pr/reconcile-merges → PR #194 (fix/builder-gh-merged-field).
      TH-01 + TH-02 task rows walked to done via transition_task with operator
      payloads (reconcile-merges refuses operator-recovered tasks — gap flagged
      as background-task chip task_897318ac).
- [~] CP2 — TH-03 CI ratchet: in flight. Discrepancy found: the workflow's
      --ignore flags point at tests deleted in d260309 (2026-06-18) — they
      are dead config, remove both. First coverage run was tainted by my own
      STATE.md rewrite (continuity tests) + mid-run branch edits; clean
      measurement now running in a pristine worktree at origin/main
      (scratchpad/th03-measure, bg task bwi2lhngk). Threshold = measured − 3.
- [x] CP3 — P027-stale-attempt-reconciliation: ALREADY IMPLEMENTED on main
      (commits 7a0a167 + 7ceb511, tests in test_builder_loop.py). Verified
      all ACs, validation suites green, task kb_mrpo81g0_16d0 closed done
      with evidence payload.
- [x] CP4 — P027-bounded-recovery-budget: implemented. run_packet stops with
      truthful blocker after 3 consecutive identical infra crashes
      (configurable); recovery_budget_exhausted event; run_exited resets
      window. PR #195. Task row not yet closed (close after merge).
- [ ] CP5 — P027-no-stale-artifact-reuse (kb_mrpo81g1_be1e): reconciliation
      must archive crashed-worktree changes as attempt evidence then reset
      the worktree clean; verify review-binding stale-SHA tests exist.
- [ ] CP6 — P027-recovery-exercise (kb_mrpo81g1_565a): kill-mid-run
      integration test proving reconcile + budget + clean-start end to end.
- [ ] CP7 — P027-truthful-closeout (kb_mrpo81g1_9c41): verify ACs vs main
      (initiative_status rollup after recovery), implement any gap.
- [ ] CP8 — final report to Jacob + this file flipped to completed; close
      merged P027 task rows; merge green PRs (#194, #195, later ones)

## Where I was

TH-02 forensic recovery complete (see
data/kittybuilder/recovery/TH-02-operator-report.json). PRs #192/#193 CI
fully green. google-auth env gap fixed. Full local suite green.

## Where I am

Starting CP1.

## Where I'm going

Priority order = builder queue priority: P027 reliability packets protect the
free-worker train and are queue priority 10; TH-03 closes the test-hardening
initiative first since it is small and its precondition (TH-02 merged) lands
in CP1.
