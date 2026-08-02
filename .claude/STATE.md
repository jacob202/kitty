# Session State — B6-cancellation-recovery (attempt 1)

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-02T00:00:00Z",
  "branch": "kittybuilder/kb_msb4yx3n_82f1",
  "worktree": "kittybuilder/kb_msb4yx3n_82f1",
  "status": "in_progress",
  "completed_items": [
    "operator_cancel_task refuses running/pr_opened (no unblock shortcut)",
    "detect_merged_prs / reconcile-merges recovers wrongly-cancelled tasks to done via merged PR",
    "recover_durable_issues combines lease/run recovery + merged-PR reconciliation + done-with-unmerged-PR flagging",
    "CLI operator-cancel and recover wired to new APIs; reconcile_merges cockpit handler added",
    "Tests added for cancellation guard, merge-recovery, recover_durable_issues, B4 projection"
  ],
  "blockers": [],
  "next_action": "Await Builder acceptance; packet status completed.",
  "parallel_work": []
}
-->

## Execution ownership

- this session: builder (packet B6-cancellation-recovery, attempt 1, task kb_msb4yx3n_82f1)

## Implementation summary

- `gateway/builder_queue.py`:
  - `operator_cancel_task()` — operator cancel that refuses `running` / `pr_opened`.
  - `detect_merged_prs()` now also scans `cancelled`; `_promote_merged_task()` drives
    wrongly-cancelled tasks to `done` via `_recover_cancelled_task_due_to_merge()`.
  - `recover_durable_issues()` + `_reconcile_done_unmerged_prs()` — combined recover pass.
- `gateway/builder_cli.py`: `operator-cancel` and `recover` now use the new APIs.
- `gateway/builder_commands.py`: `command_cancel` uses `operator_cancel_task`; added
  `reconcile_merges` handler.
- Tests: cancellation guard, merge-recovery of cancelled tasks, `recover_durable_issues`,
  B4 projection after reconcile.

## Validation

- Exact bundle command passed: 185 passed
  (`pytest tests/test_builder_queue.py tests/test_builder_commands.py -k 'not slow'`).
- Related files: test_builder_cli, test_builder_status, test_builder_routes,
  test_builder_control_actions — 165 passed.

## Environment note

Live gateway runner owns the real `data/kittybuilder/builder_queue.db`; the pre-existing
`TestRequeueMissingTask`/`TestCancelMissingTask` command tests touch that real DB and can
flake under lock contention. All new code/tests are `db_path`-scoped.
