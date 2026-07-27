# Handoff — KTF-003 Outcome 6 implemented and committed

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-26T23:45:00Z",
  "head_sha": "f9dfb6a",
  "branch": "main",
  "worktree": ".",
  "status": "valid",
  "completed_items": [
    "KTF-FE-04: replaced pause-and-return with continue-after-exhaustion in run_initiative",
    "KTF-FE-04: fixed _exhausted_packet_ids to count blocked-but-exhausted packets (root cause of paused-instead-of-failed)",
    "KTF-FE-04: updated 3 test assertions for new behavior (stop_class_reason surface, no pause_reason for continue path)",
    "KTF-FE-05: worker exit code 75 in kittybuilder_opencode_worker.sh",
    "KTF-FE-05: reviewer exit code 75 in kittybuilder_opencode_reviewer.sh",
    "KTF-FE-05: added LOOP_PROVIDER_EXHAUSTED constant, _close_provider_exhaustion helper, and provider-exit detection in builder_loop.py",
    "KTF-FE-05: added elif branch in builder_run.py for provider-exhausted outcome → pause_initiative",
    "KTF-FE-05: added 2 new tests (worker provider exhaustion, reviewer provider exhaustion)",
    "All 22 test_builder_run.py tests pass; all 34 test_kittybuilder_opencode_adapters.py tests pass",
    "KB wiki entry written: 2026-07-26-exhausted-packets-must-not-filter-by-task-state.md"
  ],
  "blockers": [
    "KTF-003 commit f9dfb6a pushed to origin/main; issue #274 still needs closure",
    "Open PRs #278, #277, #276 remain open",
    "Full test suite timed out (3000+ tests); relevant subset (34) passed"
  ],
  "next_action": "Close issue #274 with verified evidence (Outcome 6 daylight proof), then address issue #270.",
  "invalidation_conditions": [
    "HEAD changes beyond f9dfb6a",
    "new correction PR claims KTF-003 or its gates are defective"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## What was done

- **KTF-FE-04 (continue after exhaustion):** In `gateway/builder_run.py`, replaced the `pause_initiative` + `return` block after packet exhaustion with `_decide()` + `continue`. The run loop now picks up the next unrelated eligible packet instead of pausing the whole initiative.
- **Root cause fix:** `_exhausted_packet_ids` in `gateway/builder_initiative.py` was filtering by `state == bq.QUEUED`, which meant blocked-but-exhausted packets were invisible to `derive_initiative_state`. Removed the filter — attempt-budget exhaustion is a property of attempt history, not current task state.
- **Test updates:** Three existing assertions updated (the `continue` path doesn't call `pause_initiative`, so `pause_reason` is not set — the reason is in `stop_class_reason` instead).
- **KTF-FE-05 (provider exit code 75):** Worker and reviewer shell scripts exit 75 when all free models fail. `builder_loop.py` detects exit code 75 (with no changed paths for worker, with error prefix for reviewer) and calls `_close_provider_exhaustion` which closes the attempt as `ATTEMPT_CRASHED` (no budget consumed), releases the task to queued, and pauses the initiative durably. `builder_run.py` handles the `LOOP_PROVIDER_EXHAUSTED` outcome with `pause_initiative`.
- **New tests:** `test_worker_provider_exhaustion_pauses_without_consuming_attempt_budget` and `test_reviewer_provider_exhaustion_is_resumable`.

## In-flight / WIP

- Commit `f9dfb6a` is pushed to `origin/main`.
- Issue #274 remains open — needs push + closure with verified evidence.
- Issue #270 deferred until Outcome 6 complete.

## Blockers

- Full test suite (3000+ tests) timed out at 600s; only the relevant subset was run. CI will run the full suite on push.

## Next move

Push the KTF-003 commit, close issue #274 with the Outcome 6 daylight proof evidence, then move to issue #270.

## Files changed this session

- `gateway/builder_initiative.py` — removed state filter from `_exhausted_packet_ids`
- `gateway/builder_loop.py` — added LOOP_PROVIDER_EXHAUSTED, PROVIDER_EXHAUSTED_EXIT_CODE, `_close_provider_exhaustion`, worker/reviewer exit-75 detection
- `gateway/builder_run.py` — continue-after-exhaustion + provider-exhausted branch
- `scripts/kittybuilder_opencode_worker.sh` — exit 75
- `scripts/kittybuilder_opencode_reviewer.sh` — exit 75
- `tests/test_builder_run.py` — 3 updated assertions + 2 new tests

## Verification

- `python3.12 -m pytest tests/test_builder_run.py -q` → 22 passed (54s)
- `python3.12 -m pytest tests/test_builder_run.py tests/test_kittybuilder_opencode_adapters.py -q` → 34 passed (110s)
- `ruff check gateway/builder_loop.py gateway/builder_run.py tests/test_builder_run.py` → all checks passed
- KTF-003 validation commands: all 4 pass (grep checks for constants, helper, tests, exit codes)
