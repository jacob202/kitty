# Session State — Builder reliability, UI alignment, ImagePlan boundary, provider health

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-07-28T19:00:00Z",
  "head_sha": "13aa8cd32d0c6f5e88205f1b69d241054cd28b9f",
  "branch": "jacob202/fix-description",
  "worktree": "amphipod",
  "status": "in_progress",
  "completed_items": [
    "Cancellation truthfulness: LOOP_CANCELLED preserved as distinct durable outcome",
    "Stale attempt liveness fence: recovery requires run-interruption evidence",
    "293 focused Builder tests passing",
    "Builder read-only surface: mutation controls removed, header honest",
    "Command palette button wired",
    "Studio contract: seed/image_count stripped from frontend, reference_ids from backend",
    "ImagePlan boundary: plan dataclass, guidance bank, /studio/plan endpoint, preview card",
    "Studio transport errors surfaced as actionable messages",
    "Provider kind/free_tier annotations with safety-net warnings"
  ],
  "blockers": [],
  "next_action": "Launch worktree on non-conflicting port, capture browser evidence for unified UI",
  "parallel_work": [
    {
      "kind": "pr",
      "ref": "#288",
      "owner": "jacob202",
      "touches": [".env.example", "gateway", "kitty", "tests"],
      "observed_at": "2026-07-28T11:24:56Z"
    },
    {
      "kind": "worktree",
      "ref": "fix/dogfood-provider-chat-shell-2026-07-28",
      "owner": "jacob202",
      "touches": ["config", "gateway/routes"],
      "observed_at": "2026-07-28T19:00:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "launch-worktree-browser-proof",
      "what": "Launch this worktree (port 4001+), serve build SHA, capture screenshots of Builder read-only surface, provider health badges, and ImagePlan preview card",
      "why": "All fixes need visible proof before declaring done",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "align-renderer-list",
      "what": "Reconcile image_backends.py (ComfyUI + Stability) with image_runner.py (ComfyUI + DrawThings) — show only dispatchable engines in the UI",
      "why": "Stability register but not dispatchable; user sees engines that can't be called",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "review-audit-plan-file",
      "what": "Review and either commit or discard docs/plans/kitty-master-architecture-audit.md",
      "why": "Dirty file carrying architecture deepening notes — decide if they belong",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": ["HEAD changes beyond 13aa8cd"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint
`jacob202/fix-description` at `13aa8cd`. 10 commits covering Builder reliability fixes, UI alignment, ImagePlan boundary adaptation from GenEvolve, and provider health annotations. One dirty file: `docs/plans/kitty-master-architecture-audit.md`.

## Lessons applied
- Liveness fence in builder_attempt.py stops premature stale-attempt recovery — synthetic tests must bypass it with `patch.object(ba, "list_all_stale_attempts")` when no run-interruption evidence exists
- GenEvolve adaptation: pin source, map primitives, adapt data shape, reject what violates local invariants — never import the agent wholesale
- ProviderConfig annotations (kind, free_tier) are static truth — no network call needed for the badge, just data on the config table
