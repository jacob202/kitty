# Session State — Branch Cleanup + KX Shell/Surfaces + Builder Queue Complete

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-23T23:45:00Z",
  "head_sha": "72f0e85",
  "branch": "main",
  "worktree": ".",
  "status": "complete",
  "completed_items": [
    "Closed 4 stale PRs, deleted all 132 remote branches — only origin/main remains",
    "Merged 10 branches, reverted 1 (img01-reconcile-job-contract — broken API)",
    "KX-03: View registry, 14→7 surface collapse, design cleanup, SVG mascot with useKittyState hook",
    "KX-04: Shared primitives refit — WorkCard/Button/StatusBadge across Work/Studio/Library/Settings",
    "KX-05: All 5 packets implemented — onboarding with gateway persistence + ChatGPT import, self-repairs endpoint + Home card + chat intent, builder control deck with run/pause/resume/cancel/cleanup through T0 action queue, experts shelf from books_manifest, chat polish sweep (ActiveTaskCards cap + test-data filter, StatusBar flapping prevention, memory evidence smalltalk suppression, session resume heading fix, CLI copy purge)",
    "Builder queue: 15 initiatives, 11 completed, 4 failed — 0 pending tasks",
    "B1 preflight evidence, B2 KB-S4 gap register, B8 initiative progress cards",
    "Expert swarm: 8-identity review panel, 22 issues identified, P0-P1 fixes built",
    "Self-repairs endpoint + Home card surfacing",
    "Cross-tool kb: skill audit, add-new-resource, improve-system, verification language",
    "Mobile bottom nav, personalized Home greeting, a11y landmarks, cat animations",
    "19/19 BuilderSurface tests pass, TypeScript clean, 130/132 backend tests pass"
  ],
  "blockers": [],
  "next_action": "Dogfood: Open localhost:4000, verify 7-surface rail, send a chat message, check Builder progress cards. Then decide: build reasoning-backend from scratch, or move to KX-06 (proactive feed).",
  "invalidation_conditions": [
    "HEAD changes beyond 72f0e85"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

`main` at `72f0e85`, pushed. All branches deleted. All initiatives resolved. Queue clean.

## Lessons applied

- Builder free workers hit infra errors consistently — manual builds are faster
- Builder actions were stubs (logged, didn't execute) — fixed by wiring to CLI via subprocess
- Test fixtures: ensure new components don't duplicate existing text that tests assert
- Expert swarm reviews are worth doing before building — surfaced consensus issues we'd miss
- **OpenCode session session hygiene (2026-07-23):** read HANDOFF.md + STATE.md at start, verify current git state against what the files claim, then work. The files already had accurate completion markers — no duplication.
- **Builder worker pipeline:** 5 KX-05 packets previously stuck in `[blocked]` — building them manually in OpenCode was faster and produced working code that the workers later committed + tested
- **BuilderSurface attention bug:** cancelled tasks counted as "needs attention", making the counter spike after cleanup — fixed by removing `cancelled` from `packetNeedsAttention`
- **UI flapping:** single failed poll → "gateway offline" banner — replaced with 3-consecutive-fail threshold using a render-side ref counter

## Next actions
1. Dogfood the UI at localhost:4000
2. Decide: build reasoning-backend fresh, or move to KX-06 proactive feed
3. Apply remaining expert swarm P2-P3 findings
4. Test the ChatGPT import wizard against the real export at /Users/jacobbrizinski/Downloads/data-...
