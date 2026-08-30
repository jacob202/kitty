# Session State — Builder diagnosability and Work actionability

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-30T05:50:00Z",
  "head_sha": "fa9a039963c7210dc93f11e021911af89ee7e83a",
  "branch": "main",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "Reconciled local main onto origin/main e2b7a061 after 37 commits behind",
    "Made the running UI's source provable: make ui-build stamps, start_ui.sh treats an unstamped build as stale",
    "Classified and removed the staged deletion of gateway/kitty-chat/eslint.config.mjs as dead config",
    "Exposed GET /builder/supervisor and POST /builder/supervisor/tick",
    "Made every Work row resolve to a real Builder command or a stated reason none is available",
    "Installed com.kitty.builder.supervisor launchd schedule (900s interval) under Jacob's overnight authorization",
    "Set the compute governor weekly ceiling to CAD 6.00 per Jacob",
    "Unified the supervisor's dispatch predicate so the projection cannot disagree with the launcher",
    "Stopped the supervisor dispatching blocked packets the loop refuses with operator release required"
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
  "parallel_work": [
    {
      "kind": "open_pr",
      "ref": "673",
      "owner": "unknown",
      "touches": [
        "gateway/runtime_manifest.py"
      ],
      "observed_at": "2026-08-30T05:50:00Z"
    },
    {
      "kind": "open_pr",
      "ref": "675",
      "owner": "unknown",
      "touches": [
        "gateway/kitty-chat/src"
      ],
      "observed_at": "2026-08-30T05:50:00Z"
    },
    {
      "kind": "local_commit",
      "ref": "ead4d9733ce664e556d84465ff8f2dd15dc3808b",
      "owner": "interactive",
      "touches": [
        "gateway/runtime_manifest.py",
        "tests/test_pr673_completions_budget.py"
      ],
      "observed_at": "2026-08-30T05:50:00Z"
    }
  ],
  "recommendations": []
}
-->

## Current work

Builder is now diagnosable and Work is actionable. Six local commits sit ahead of
`origin/main`; none are pushed, because interactive pushes need Jacob's approval.

The overnight schedule is installed and active. One packet
(`WORK-SPINE-004-LEAD-HARDEN`) is genuinely dispatchable; two more need an
operator release, which is the Try again control in Work; six are parked behind
paused initiatives.

## Unpushed work worth preserving

`.worktrees/pr673-finalize-20260829` holds commit `ead4d973`, one commit beyond
PR #673's pushed head, changing `gateway/runtime_manifest.py` and adding
`tests/test_pr673_completions_budget.py`. It is not on any remote and looks like
the repair for #673's failing pytest/policy/merge gates. Do not rebuild that work
from scratch and do not delete that worktree.

`.worktrees/continue-kitty-power-run-20260829` is fully contained in PR #675 —
nothing there is at risk.
