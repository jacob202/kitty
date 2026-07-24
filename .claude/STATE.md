# Session State — KX-05/KX-06 + Reasoning Backend + Dogfood — Complete

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-24T01:00:00Z",
  "head_sha": "54784e0",
  "branch": "main",
  "worktree": ".",
  "status": "complete",
  "completed_items": [
    "KX-05 all 5 packets: onboarding gateway persistence + import wizard, self-repairs /repairs endpoint + Home card + chat intent, builder control deck via T0 action queue, experts shelf from books_manifest, chat polish sweep (ActiveTaskCards cap, StatusBar flapping, memory evidence, CLI copy)",
    "KX-06 both packets: /signals endpoint reusing Repairs shape + SignalsCard, PhoneAccessCard plain-English copy fix",
    "Reasoning backend RE-C1/C2/C5 confirmed complete: classify_complexity wired into route_model + completions, tier-aware context budget 300/1200/2400, execution receipts. 105/105 tests pass.",
    "Builder queue: 2 KX-06 packets queued (admin — code shipped), rest done/cancelled",
    "Dogfood: onboarding wizard tested end-to-end (4 steps, name persists), experts strip verified (5 experts, 219 books), system repairs card live, signals feed with 20 items",
    "Import wizard: tested with real export file, --source fix applied",
    "Build: TypeScript clean, frontend tests 36/36 HomeState pass, all integration tests pass",
    "KB: 4 new lessons in kitty-lessons-index.md (items 9-12)",
    "Session hygiene: HANDOFF.md + STATE.md updated, lessons documented"
  ],
  "blockers": [],
  "next_action": "Dogfood the signals card on Home. Then decision: KX-07 (next UX initiative) or ship the current surface.",
  "invalidation_conditions": [
    "HEAD changes beyond 54784e0"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

`main` at `54784e0`, pushed. KX-05/KX-06 code shipped. Reasoning backend confirmed done. Queue: 2 KX-06 admin items queued, everything else done/cancelled.

## Lessons applied

- Builder actions must exist in action_tiers.json AND have executor files in gateway/actions/ — paired contract
- StatusBar flapping is a render-count problem, not a polling problem — use render-side ref counter
- Test assertions on exact user-facing strings are brittle — prefer regex matchers
- Builder worker pipeline has hidden initiative-level gates — manual builds faster
- Launchd gateway processes need full unload/reload, not just ./kitty down/up

## Next actions
1. `make preview` — dogfood the signals card + expert strip + repairs card
2. Decision: KX-07 (next UX surface) or polish/ship the current surface
3. Apply remaining expert swarm P2-P3 findings
