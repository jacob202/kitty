# KittyBuilder Core — Black-Box Runtime Acceptance Audit

**Verdict:** KITTYBUILDER CORE: **FAIL** — one defect found and fixed in this PR
**Date:** 2026-08-01
**Audit environment:** isolated git worktree `audit-core-runtime-2026-08-01` on branch `docs/kittybuilder-core-runtime-audit-2026-08-01`
**Base (audited) SHA:** `bcae5f28fcb5a11573faeea29862231a9335b7fa` (origin/main at audit start)
**DB:** `<worktree>/data/kittybuilder/builder_queue.db` (repo-relative `data/*` is gitignored, so the worktree is an isolated, supported data location)
**Contact with providers/network/model:** none. Every worker/reviewer/validator is a deterministic local fixture. No spend occurred.

## Scope

Operational, black-box acceptance of the KittyBuilder core execution control plane:
initiative/packet lifecycle, task queue state machine, leases, attempts, worker runs,
validation, review, budgets and operator overrides, crash recovery, status projection,
and CLI doctor checks. Product intent (ADR 0017 boundary), PR #355,
`gateway/kitty-chat`, the Image Agent A3, secrets, and RunPod were out of scope
and were not touched.

## Baseline

- `./kitty builder initiative doctor --json` before any mutation: 13 PASS / 1 WARN / 0 FAIL (WARN cleared by the end of the session).
- `./kitty builder queue doctor --json`: `{"silent_transitions": []}`.

## Scenario matrix

| # | Scenario | Command surface | Result |
| --- | --- | --- | --- |
| S1 | Apply initiative + packet, task created | `initiative validate/apply/list/show/status`, `queue status` | PASS |
| S2 | Full happy path: claim → run → validate → review → close | `initiative run-packet` | PASS |
| S3 | Restart persistence: same DB, fresh processes, full event chain | `queue events/runs/show-run`, artifacts on disk | PASS |
| S4 | Crash recovery — **defect found (S4a), fixed in this PR** | `run-packet` after SIGKILL | FAIL → fixed |
| S5 | Expired claim lease requeued, packet completes | `queue claim --lease-seconds 1`, `queue recover`, events | PASS |
| S6/S7 | Budget exhaustion → blocked; blank grant rejected; reasoned grant durable | `grant-attempt`, `operator-release`, `attempt_granted` event | PASS |
| S8 | Operator-completion flow | `start-attempt`, `run-validation`, `record-implementation`, `record-review`, `close-attempt` | PASS |
| S9 | Status/report/doctor agreement | `initiative status/report`, `queue status/doctor`, `initiative doctor` | PASS |
| S10 | Cancellation, worktree removal (refuse dirty / allow clean), recovery | `operator-cancel`, `clean-worktree` | PASS |

## Detailed evidence

### S1 — initiative and packet application (PASS)

- `initiative apply audit-init-01.json` → `AUDIT-INIT-01` active, packet `P1-OK` → task `kb_msau8lll_4e3d`.
- `initiative list/show/status`, `queue status`, `queue list` all agree: packet_count 1, task state `queued`.

### S2 — happy path (PASS)

`initiative run-packet AUDIT-INIT-01 P1-OK` with `ok_worker.py` + `review_approve.py`:

```
outcome: succeeded | attempt 1 | impl: completed | validation: passed | review: approve
task_state: blocked | worktree_cleanup: kept_no_done_marker
run: run_msau8yjf_3f78 (exited, exit 0)
```

### S3 — restart persistence (PASS)

Fresh CLI invocations against the same DB reproduce the full chain from durable
events alone (no in-memory state): `created → attempt_started →
attempt_artifacts_created → claimed → running → run_started → report_attached →
blocked → lease_cleared → run_exited → attempt_implementation_recorded →
attempt_validation_recorded → attempt_review_recorded → review_evidence_bound →
attempt_closed(succeeded)`.

On-disk artifacts survived across processes:
- `data/kittybuilder/attempts/kb_msau8lll_4e3d/1/{bundle.json,implementation.json,review-context.json,review.json,run-manifest.json}`
- `data/kittybuilder/runs/run_msau8yjf_3f78/{brief.md,combined.log,gh-config/}`
- Task git worktree survives on `kittybuilder/kb_msau8lll_4e3d`.

### S4a — defect: worker self-crash deadlocks the in-process retry (FAIL → FIXED)

**Reproducer (pre-fix):** run-packet with `crash_worker.py` (writes partial work,
then `os.kill(os.getpid(), SIGKILL)`). The worker dies by signal while the
supervisor loop survives, so the attempt closes `failed` and the loop retries
in-process — the same dirty worktree re-enters `ensure_worktree`, which refuses
dirty trees, so attempt 2 closes `crashed` (`infrastructure_failed`, phase
`worker_orchestration`) and the packet deadlocks forever:

```
error: worker orchestration failed: RunnerError: worktree ... is dirty;
refusing to overwrite partial progress. Inspect it, commit/stash, or clean it explicitly.
```

Afterward the task is `queued` with a dirty worktree and **no supported command
recovers it**: `queue recover` reports all zeros, `clean-worktree` refuses dirty
trees, `operator-release` rejects a queued task, `archive` targets terminal
states only. Only manual `git` surgery outside the CLI escapes.

**Root cause:** P027 (#196) added `archive_and_reset_worktree` (evidence
preserved, worktree hard-reset) but wired it only into the dead-supervisor path
(`_reconcile_stale_attempts`). The live-loop retry path — a worker that dies
while the supervisor lives — lacks that step, so it deadlocks on the dirty tree.

**Fix (this PR):** in `run_packet`, the loop decides the next attempt's worktree
disposition from the previous attempt **before** anything is durably opened. Only
an explicitly repairable previous outcome — deterministic validation failure or a
clean reviewer `request_changes` verdict, where the post-worker tree is still
bound to the worker result — keeps its dirty worktree as repair input, which the
next attempt deliberately reuses (`ensure_worktree`/`run_worker` `reuse_dirty`
opt-in, default fail-closed). Anything else — a worker that crashed/was
interrupted mid-execution, or a review execution/mutation/evidence-integrity
failure — archives the tree into the failed attempt's artifact dir
(`crashed-worktree.patch` + `crashed-worktree-status.txt`) and resets so the next
attempt starts clean and inherits nothing. Because the reset runs before the
replacement attempt is claimed, a reset failure cannot strand an attempt or
lease; the real error is recorded durably and the partial work stays inspectable.
`ensure_worktree` treats a nonzero `git status` exit as infrastructure failure
and always raises, accepting a dirty tree only under the explicit reuse flag.

Final review/evidence is cumulative from the packet's durable `base_sha`: the
reviewer is bound (and the successful final-state report records) every path
changed since the packet base — including implementation retained and committed
on an earlier repair attempt — while each attempt's own run record keeps its
retry-local delta separately.

**Regression tests** in `tests/test_builder_loop.py::TestNoStaleArtifactReuse`:
- `test_worker_self_crash_on_first_attempt_recovers_in_loop` — worker SIGKILLs
  itself mid-run on attempt 1, succeeds on the retry. Asserts: outcome
  succeeded; attempt outcomes `[failed, succeeded]`; `crashed-worktree.patch`
  contains the partial file; retry ran on a clean tree.
- `test_validation_failure_retry_preserves_implementation` and
  `test_request_changes_retry_preserves_implementation` — the retry worker only
  succeeds if the prior attempt's implementation is still in the worktree
  (proving no archive/reset); asserts no `crashed-worktree.patch` and no
  `worktree_archived_for_clean_retry` event.
- `test_archival_failure_does_not_strand_attempt_or_lease` — forces the
  clean-retry reset to fail and asserts no second attempt, no stranded lease, a
  durable budget-neutral `infrastructure_failed` event, and the partial work
  still present in the dirty worktree.
- `test_final_review_and_report_are_cumulative_from_base_sha` — attempt 1
  commits file A and fails validation; attempt 2 repairs only file B; the final
  review context and the final report's cumulative evidence include both A and
  B, while attempt 2's own run record keeps just the B delta.
- `test_reviewer_mutation_is_not_passed_to_next_worker` — the reviewer writes
  into an allowed path and exits nonzero; the tainted tree is archived and the
  next worker starts clean (no inherited mutation).
- `test_reuse_dirty_accepts_truthful_dirty` / `test_reuse_dirty_still_raises_on_status_failure`
  (runner) — `reuse_dirty` accepts a truthfully-dirty tree but a failed `git
  status` always raises.

**End-to-end verification (real CLI, post-fix):** fresh packet
`AUDIT-INIT-09/P9-SELFCRASH` with `crash_once_worker.py`:

```
outcome: succeeded
  attempt 1 failed | worker run ended failed        (SIGKILL; partial work archived)
  attempt 2 succeeded |                             (clean retry)
```

Evidence preserved at `data/kittybuilder/attempts/kb_msav48iz_c2bd/16/`:
`crashed-worktree.patch` (contains `audit-artifacts/partial.txt`) and
`crashed-worktree-status.txt`. Retry run `run_msav4d9l_3e2d` `exited` exit 0,
`changed_paths: ['audit-artifacts/ok.txt']` — the crashed attempt's file did not
leak into the retry. Event chain: `run_failed → attempt_closed → attempt_started →
operator_released → ... → run_exited → attempt_closed`.

### S4b — dead-supervisor crash recovery (PASS, cross-checks P027)

Killed both the supervisor process and the worker (SIGKILL) mid-attempt on
`AUDIT-INIT-02/P2-CRASH`. Re-entry reconciled the stale open attempt: events
`run_interrupted(pid_not_running) → blocked → attempt_closed(crashed) →
infrastructure_failed(phase=stale_attempt_reconciliation, counts_toward_budget=false,
worktree=archived_and_reset, patch=…/2/crashed-worktree.patch) → operator_released →
attempt 3 → succeeded`. The interrupted run ends `interrupted`; success is never
fabricated.

### S5 — stale claim lease (PASS)

`queue claim kb_msauh547_f065 --lease-seconds 1` → `claimed` (lease expires in 1s).
After expiry, `queue recover` → `claimed_requeued: 1`; task state `queued`;
event `released` reason `lease_expired`. `run-packet` then completed the packet
(outcome `succeeded`). `initiative doctor` check `runs:stale_leases` PASS.

### S6/S7 — budget exhaustion and operator grant (PASS)

- `run-packet` with `fail_worker.py` on `AUDIT-INIT-03/P3-BUDGET` (max_attempts 1) → task `blocked`, budget exhausted.
- Re-running refused: `blocked without a stale open attempt; operator release is required`.
- `grant-attempt` with blank `--reason ""` → rejected: `a nonblank operator reason is required`.
- `grant-attempt` with a reason → `granted 1 attempt ... : 1 -> 2`.
- Durable `attempt_granted` event (with the reason) visible in fresh processes.
- `operator-release` → queued → `run-packet` → `succeeded` on attempt 2.

### S8 — operator completion flow (PASS)

`AUDIT-INIT-07/P7-OP`: `start-attempt` (attempt 2, id 13) → worker run
(`ok_worker.py`, result recorded) → `record-implementation` → `run-validation`
(`[ok] validate_pass.py (0.1s)`) → `record-review` (approve) → `close-attempt succeeded`.
Final attempt record (fresh process): impl `recorded`, validation `passed`,
review `approve`, outcome `succeeded`. Durable events:
`attempt_started → attempt_implementation_recorded → attempt_validation_recorded →
attempt_review_recorded → attempt_closed`.

### S9 — status/doctor agreement (PASS)

- `initiative doctor --json`: 14/14 PASS (0 WARN, 0 FAIL) — `db:integrity_check`,
  `queue:kill_switch`, `repo:identity`, `runs:stale_leases`, `runs:active`,
  `runner:credential_isolation`, etc.
- `queue doctor --json`: `{"silent_transitions": []}`.
- `queue status` and `initiative status` agree on per-initiative rollups
  (attempts, first-pass-approval, exhausted counts, evidence flags).
- `initiative report` wrote a bounded markdown campaign report to
  `data/kittybuilder/reports/AUDIT-INIT-07-*.md`.

### S10 — cancellation and worktree removal (PASS)

- `operator-cancel kb_msaupo7s_2dfb --reason ...` from `claimed` → `cancelled`,
  durable event `cancelled` with reason; second cancel refused (`illegal transition: cancelled -> cancelled`).
- `clean-worktree` on a dirty task refuses: `worktree ... is dirty; refusing to remove. Commit, stash, or inspect first.`
- After committing the task worktree's artifacts, `clean-worktree` removed the
  registered worktree; task record and queue doctor survived.

## Defect summary

| ID | Description | Severity | Status |
| --- | --- | --- | --- |
| BUG-1 | Live-loop retry after a worker self-crash (SIGKILL) deadlocks on the dirty worktree; no supported recovery command; manual git required | High (recovery of a common failure mode) | **Fixed in this PR** + regression test |

## Files changed in this PR

- `gateway/builder_loop.py` — per-attempt worktree disposition (archive/reset
  only for non-repairable outcomes; preserve `request_changes`/validation repair
  input), reset before the replacement attempt is opened (no stranded
  attempt/lease on failure), repairable-only reuse, and cumulative
  review/final evidence from the packet `base_sha`.
- `gateway/builder_runner.py` — `ensure_worktree`/`run_worker` gain a
  `reuse_dirty` opt-in (default fail-closed) that never masks a failed `git
  status`; `worktree_changed_paths` exposes the packet-cumulative change set.
- `tests/test_builder_loop.py` — regressions for BUG-1, repair preservation
  (validation + `request_changes`), reviewer-mutation non-inheritance, the
  no-strand archival-failure path, and cumulative review/report evidence.
- `tests/test_builder_runner.py` — `reuse_dirty` truthful-dirty acceptance and
  status-failure focus regressions.
- `docs/research/kittybuilder-core-runtime-audit-2026-08-01.md` — this report.

## Verification

- `python3.12 -m pytest tests/test_builder_loop.py tests/test_builder_runner.py -q --tb=short` → **116 passed**.
- Full builder suite `python3.12 -m pytest tests/test_builder_*.py -q --tb=short` → **1000 passed, 29 subtests passed**.
- `ruff check gateway/builder_loop.py gateway/builder_runner.py tests/test_builder_loop.py tests/test_builder_runner.py` → **All checks passed!**
- `mypy gateway/builder_loop.py gateway/builder_runner.py` → **Success: no issues found in 2 source files**.
- `git diff --check` → clean (exit 0).
- Live CLI end-to-end recovery confirmed (S4a post-fix trace above).
- Doctors green at end of session.

## Skipped checks

- Full `tests/` non-builder modules, frontend build/tests: not run (per repo
  rules these are CI gates; this audit changed `builder_loop.py`,
  `builder_runner.py`, and the loop/runners tests). lint/typecheck run locally on
  the changed files (see Verification).
- No UI changes, no screenshots applicable.

## Limitations

- Black-box: conclusions come from the CLI and durable artifacts, not from
  reading the implementation. Root cause was verified against source only to
  size the fix.
- Max-credit/RunPod paths and the publication rail (`publish`, `attach-pr`,
  `reconcile-merges`) were not exercised (boundary).
- Long-running lease/hostile-liveness and multi-worker concurrency were not
  stress-tested.
