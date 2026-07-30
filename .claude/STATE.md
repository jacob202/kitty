# Session State — KTF-001 recovery plan checkpoint

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-07-30T03:10:02Z",
  "head_sha": "23d0af1bb52407fe1dc1ffdb972d7d9279c18dde",
  "branch": "docs/ktf-001-resume-plan",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "PR #295 restored mainline continuity and frontend gates; its post-merge main workflow passed.",
    "PRs #261, #262, and #263 are merged.",
    "PR #293 was closed because its conflicted broad UI scope is outside KTF-001.",
    "Current main contains the KTF-003 Outcome 6 code anchors, while the original immutable Builder task records remain cancelled or failed."
  ],
  "blockers": [
    "Do not rerun the exhausted/cancelled KTF manifests: their literal instructions are stale against current main.",
    "The first required proof is a supported evidence reconciliation, not another feature packet."
  ],
  "next_action": "Run KTF-R1: reconcile current main, GitHub, and canonical Builder evidence into the reliability-delta report before authoring or applying any replacement packet.",
  "parallel_work": [
    {
      "kind": "worktree",
      "ref": "fix/dogfood-provider-chat-shell-2026-07-28",
      "owner": "unknown",
      "touches": ["config", "gateway/routes", "gateway/kitty-chat"],
      "observed_at": "2026-07-30T03:10:02Z"
    },
    {
      "kind": "worktree",
      "ref": "jacob202/fix-description",
      "owner": "unknown",
      "touches": [".claude"],
      "observed_at": "2026-07-30T03:10:02Z"
    },
    {
      "kind": "worktree",
      "ref": "contract-first",
      "owner": "unknown",
      "touches": ["docs", "gateway", "scripts"],
      "observed_at": "2026-07-30T03:10:02Z"
    }
  ],
  "recommendations": [
    {
      "id": "ktf-r1-reconcile-evidence",
      "what": "Run KTF-R1 and write the supported reliability-delta report.",
      "why": "It distinguishes landed code from stale Builder records before any new packet is authored or run.",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "ktf-r2-author-fresh-packets",
      "what": "Author only the replacement manifests R1 proves are still needed.",
      "why": "Fresh contracts avoid replaying immutable packets whose anchors no longer describe main.",
      "class": "code",
      "status": "deferred",
      "blocked_by": "KTF-R1 reliability-delta report is not written.",
      "release_check": "test -f docs/research/ktf-001-reliability-reconciliation-2026-07-30.md",
      "deferred_count": 0,
      "first_deferred": "2026-07-30"
    },
    {
      "id": "ktf-r3-daylight-life-proof",
      "what": "Run the daylight Builder proof and one real life-project resume loop after independent review.",
      "why": "These are the remaining KTF-001 outcomes that turn green code into proven delivery behavior.",
      "class": "code",
      "status": "deferred",
      "blocked_by": "Fresh replacement manifests must be reviewed, validated, and applied.",
      "release_check": "test -f docs/initiatives/ktf-001-daylight-proof-v2.json",
      "deferred_count": 0,
      "first_deferred": "2026-07-30"
    }
  ],
  "invalidation_conditions": [
    "HEAD changes beyond 23d0af1bb52407fe1dc1ffdb972d7d9279c18dde",
    "main, GitHub PR, or canonical Builder task/attempt/lease state changes",
    "KTF-R1 begins or completes"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Checkpoint

The trust-foundation gate repair is merged. The durable next move is evidence
reconciliation, followed by fresh packet authoring and the operator-gated
daylight plus life-project proofs. The plan lives in
`docs/initiatives/ktf-001-resume-proof-v2.json`.
