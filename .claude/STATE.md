# Session State — KB-BRAIN-00 harvest done, dogfood branch fixed, 3 UI fixes reviewed

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-07-28T23:40:00",
  "head_sha": "8ae7b25",
  "branch": "fix/dogfood-provider-chat-shell-2026-07-28",
  "worktree": ".",
  "status": "complete",
  "completed_items": [
    "Reviewed and promoted D15/D16/D17 UI fix tasks to done (PRs #281, #282, #283 already merged)",
    "Completed KB-BRAIN-00 source harvest: 12 repos at immutable SHAs, verified licenses, ranked KB-BRAIN-01→07 map",
    "Created PR #294 for harvest document",
    "Fixed dogfood branch conflict by reverting harvest commit",
    "Extracted KB entry: Builder state machine publish workflow"
  ],
  "blockers": [],
  "next_action": "Merge PR #294 (harvest) then PR #293 (dogfood), then claim KB-BRAIN-01",
  "parallel_work": [
    {
      "kind": "pr",
      "ref": "294",
      "owner": "jacob202",
      "touches": ["docs/research/"],
      "observed_at": "2026-07-28T23:22:00"
    },
    {
      "kind": "pr",
      "ref": "293",
      "owner": "jacob202",
      "touches": [".claude", "gateway"],
      "observed_at": "2026-07-28T23:11:00"
    },
    {
      "kind": "worktree",
      "ref": "contract-first",
      "owner": "unknown",
      "touches": ["docs", "gateway", "scripts"],
      "observed_at": "2026-07-28T23:40:00"
    }
  ],
  "recommendations": [
    {
      "id": "merge-294-harvest",
      "what": "Merge PR #294 (KB-BRAIN-00 harvest) to unblock KB-BRAIN-01",
      "why": "Harvest is the foundation document for all KB-BRAIN packets",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "merge-293-dogfood",
      "what": "Merge PR #293 (dogfood UI sweep)",
      "why": "Mobile nav, chat context, settings — conflict resolved",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "claim-kb-brain-01",
      "what": "Claim and run KB-BRAIN-01 (OpenCode worker session adapter)",
      "why": "Highest pri=10 queued task — harvest unblocks it",
      "class": "code",
      "status": "deferred",
      "blocked_by": "PR #294 (harvest) not yet merged to main",
      "release_check": "git merge-base --is-ancestor d90eea1b origin/main",
      "deferred_count": 0,
      "first_deferred": "2026-07-28"
    }
  ],
  "invalidation_conditions": ["HEAD changes beyond 8ae7b25"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint
On `fix/dogfood-provider-chat-shell-2026-07-28` at `8ae7b25`. Harvest changes live on `kittybuilder/kb_ms1421a8_c470` (PR #294). Dogfood branch clean after revert.

## Lessons applied
- Builder state machine: running → pr_opened → awaiting_review → done (no skip)
- `git revert` when force-push is blocked; cherry-pick to move commits between branches
- `manaflow-ai/cmux` (not `coder/cmux`) is GPL-3.0 — hard REJECT for code
- `ZaxbyHub/opencode-swarm` is the correct org (not `zaxbysauce`)
