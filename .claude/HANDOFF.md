# Handoff — repo-wide pre-push gate repair in progress

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-08-12T03:59:16Z",
  "head_sha": "18dc32f4f72d15f3594ebf1f0a0a50269e7cc908",
  "branch": "fix/repo-prepush-gate-repair",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "Reproduced the repo-wide gate failures on current origin/main",
    "Isolated Imagen tests from the user's real face-model cache"
  ],
  "blockers": [],
  "next_action": "Repair the repo-wide pre-push gate, then publish the reviewed Builder process cleanup",
  "invalidation_conditions": [
    "origin/main advances before this gate repair is merged",
    "the repo-wide pre-push gate remains red after the repair"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null,
  "parallel_work": [
    {
      "kind": "local_commit",
      "ref": "e7302fb0deae4397438a67bac268c61e01c1c38f",
      "owner": "interactive",
      "touches": [
        "gateway/builder_publish.py",
        "tests/test_builder_publish.py"
      ],
      "observed_at": "2026-08-12T03:59:16Z"
    }
  ],
  "recommendations": [],
  "execution_owner": "interactive"
}
-->

## Evidence

- Current main reproduced five stale continuity failures and two Imagen isolation failures.
- Builder publication cleanup remains preserved as local reviewed commit `e7302fb0`.

## Next action

Make the repo-wide pre-push gate green, then publish the Builder cleanup and resume KPROOF.

## 2026-08-15 — HOME STRETCH Mac lane (#505 / #490)

Step 1 runtime truth DONE. Receipt: `.claude/RUNTIME_RECEIPT_490.md`,
posted to issue #490 (comment 5304168399).

BLOCKER: this checkout (`feat/builder-action-retirement` @ 01bb5e2d) is 80
commits behind origin/main and does NOT contain PR #498. The live Gateway
(:8000) is serving this stale tree. Steps 2-4 cannot start until the runtime
sits on `c01caddc` (origin/main).

NEXT: decide branch strategy with Jacob — fast-forward the main checkout to
origin/main, or stand up a worktree at c01caddc and repoint the services.
6 local commits on this branch would need somewhere to go first.
