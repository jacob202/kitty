# Session State — Builder reliability, UI alignment, ImagePlan boundary, provider health

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-07-28T13:50:00Z",
  "head_sha": "be8dd1223c91810497391d1c3ef35bd563478d5a",
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
    "Provider kind/free_tier annotations with safety-net warnings",
    "Model routing refactor: RouteDecision and legacy aliases moved to model_routing Module"
  ],
  "blockers": [],
  "next_action": "Fix failing PR #289 checks (typecheck, lint, cold-start, BuilderSurface test), then merge",
  "parallel_work": [
    {
      "kind": "pr",
      "ref": "#288",
      "owner": "jacob202",
      "touches": [".env.example", "gateway", "kitty", "tests"],
      "observed_at": "2026-07-28T13:50:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "merge-pr-289",
      "what": "Fix the five failing checks on PR #289 and merge the 129-commit sweep",
      "why": "The branch carries substantial landed work that is blocked behind failing CI",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "harden-context-receipt",
      "what": "Deepen the context receipt validation Module as the next hardening target",
      "why": "Protects session continuity and stale-handoff detection",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "review-merged-prs",
      "what": "Extended review of recently merged PRs 281-288 for regression risk",
      "why": "Eight PRs merged in rapid succession; cumulative review is owed",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": ["HEAD changes beyond be8dd12"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 289,
    "state": "OPEN",
    "head_sha": "224d7bd4533cd637d861a433499e0acd073fd66b"
  }
}
-->

## Current checkpoint
`jacob202/fix-description` at `13aa8cd`. 10 commits covering Builder reliability fixes, UI alignment, ImagePlan boundary adaptation from GenEvolve, and provider health annotations. One dirty file: `docs/plans/kitty-master-architecture-audit.md`.

## Lessons applied
- Liveness fence in builder_attempt.py stops premature stale-attempt recovery — synthetic tests must bypass it with `patch.object(ba, "list_all_stale_attempts")` when no run-interruption evidence exists
- GenEvolve adaptation: pin source, map primitives, adapt data shape, reject what violates local invariants — never import the agent wholesale
- ProviderConfig annotations (kind, free_tier) are static truth — no network call needed for the badge, just data on the config table
