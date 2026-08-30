# Handoff — Builder diagnosability and Work actionability

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-30T05:50:00Z",
  "head_sha": "fa9a039963c7210dc93f11e021911af89ee7e83a",
  "branch": "main",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "Reconciled local main onto origin/main e2b7a061 after 37 commits behind",
    "Made the running UI's source provable",
    "Exposed the Builder supervisor over HTTP",
    "Made every Work row resolve to a real command or a stated reason",
    "Installed the overnight Builder schedule under Jacob's authorization",
    "Unified the supervisor's dispatch predicate with the launcher's"
  ],
  "blockers": [],
  "next_action": "Restore chat -> packet -> result: prove one bounded proposal, approval, durable packet, and visible outcome through /builder/conversation/propose and approve.",
  "invalidation_conditions": [
    "origin/main advances past e2b7a061 without these six commits being reconciled",
    "the com.kitty.builder.supervisor launchd job is unloaded or its plist is removed",
    "config/compute_governor.json weekly_budget_cad is changed away from 6.0"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "parallel_work": [],
  "recommendations": [],
  "execution_owner": "interactive"
}
-->

## Evidence

- Baseline: local `main` was 37 commits behind `origin/main` and the running UI
  was built from `8201830d`, older than either. Reconciled to `e2b7a061` plus six
  local commits; running build source now equals `kitty status` source sha.
- Root cause of Builder never finishing: no scheduled tick existed (no cron, no
  launchd, no endpoint), and when a tick did run it dispatched blocked packets
  that `builder_loop.run_packet` refuses with "operator release is required",
  logging the refusal to a file and reporting "2 run(s) launched".
- Queue explanation: 161 queued tasks, 160 owned by paused initiatives, newest
  created 2026-08-17. Verified by direct query of `builder_queue.db`.
- Tests: `gateway/kitty-chat` 546 passed (75 files, 21 new in
  `tests/WorkViewActions.test.tsx`); Python 100 passed across
  `test_builder_supervisor.py`, `test_builder_supervisor_api.py`,
  `test_builder_loop.py`, `test_builder_status.py`, `test_builder_routes.py`,
  `test_builder_commands.py`; 18 passed across `test_start_ui_script.py`,
  `test_status_glance.py`, `test_doctor_freshness.py`,
  `test_kitty_desktop_runtime.py`.
- Running-app check at 1280x900 and 390x844: no horizontal overflow, no console
  errors, banner reads the same counts as a direct database query.
- Independent review: none. All verification here is self-authored and should be
  treated as unverified until an independent reviewer repeats it.

## Next action

Restore chat → packet → result. `/builder/conversation/propose` and
`/builder/conversation/approve` already exist; prove one bounded loop end to end
in the running product, plus one interruption/recovery loop.
