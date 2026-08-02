# Handoff — B5-pr-check-review-actionable (recovery actions in builder status)

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-02T00:00:00Z",
  "branch": "kittybuilder/kb_msb4yx3n_124c",
  "worktree": "kittybuilder/kb_msb4yx3n_124c",
  "status": "valid",
  "completed_items": [
    "Extended gh PR advisory capture (mergeable, mergeStateStatus, baseRefOid) in builder_queue._gh_pr_status",
    "Persisted advisory merge/base fields on pr_attached/pr_updated event payload via attach_pr",
    "Added read-only _pr_advisory_projection + _recovery_actions to builder_status packet model",
    "Repaired run projection to expose start_sha for superseded-run detection",
    "Added 6 focused recovery-action tests in test_builder_status.py"
  ],
  "blockers": [],
  "next_action": "Packet reported; await review.",
  "parallel_work": [],
  "recommendations": [],
  "invalidation_conditions": [
    "HEAD changes beyond the current packet lease base"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "head_sha": "734e49e9237fb2093af622ece9c3e62b2e61f19c"
}
-->

## What was done

- `gateway/builder_queue.py`: `_gh_pr_status` now fetches `mergeable`,
  `mergeStateStatus`, `baseRefOid`; `sync_pr_status` forwards them and
  `attach_pr` persists them on the advisory `pr_attached`/`pr_updated` event
  payload (Section 11.4 — never on the task/pr_links row).
- `gateway/builder_status.py`: added `_read_latest_pr_advisories` (bulk query,
  SNAPSHOT_QUERY_COUNT 9 -> 10), `_pr_advisory_projection`, and
  `_recovery_actions`. Each packet now carries `recovery_actions` (and
  `pr_advisory`) with concrete next steps for failing CI, merge conflict,
  waiting review, stale/base-behind rebase, and superseded runs. Run
  projection exposes `start_sha`.
- `tests/test_builder_status.py`: 6 focused tests (31 total pass).

## Next move

Packet result written to `.kittybuilder-result-100.json`; await independent review.
