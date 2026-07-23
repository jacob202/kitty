# Session Handoff

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-23T20:30:00Z",
  "head_sha": "f09d0493012f90624f06cc2bf909ea5f5160958e",
  "branch": "main",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "Builder queue cleanup: backup + recover + cancel 11 zombies (closeout-v1 x5, chat-recovery x4, cp08-a x1, stray test x1). Queue: 11 queued real, 2 blocked (decisions).",
    "Resume judgments: RE-C1 re-queued (kept, unblocked); cp08b-tests-docs re-queued + cp08-campaign-b initiative resumed.",
    "Dogfooded Kitty fresh-profile via agent-browser: identified onboarding-does-nothing, jargon Home, DSML markup leak from chat, Builder read-only, 24-needs-attention projection bug, status-strip flapping, ActiveTaskCards junk, name unused.",
    "Drafted + applied docs/initiatives/kx-05-companion-layer-v1.json (5 packets, validated) with LOCKED DECISIONS embedded: T0 tier rule, conservative import staging, attention-first builder pane layout, ChatGPT export corpus path. Launched all 5 packets in parallel via free ladder (2400s timeout, staggered to avoid git index.lock race).",
    "KB review: fixed /Users/jacobbrizinski/kb/wiki/skill-audit.md Gaps section (SHIPLOG not-yet-built); added cross-tool KB pointer to kitty CLAUDE.md.",
    "Deep harvest: cloned assistant-ui, bolt.diy, anything-llm, OpenHands, home-assistant/frontend (5 repos to /Users/jacobbrizinski/.local/share/opencode/tool-output/). Wrote docs/AUDIT_COMPANION_LAYER_HARVEST_2026-07-23.md (396 lines): 18-entry solved-problems register, 13 adapt candidates, KX-05 packet mapping.",
    "Visual-diff harness: wrote gateway/kitty-chat/scripts/visual-diff.ts (Playwright + pixelmatch + pngjs, hard 120s watchdog, SSE-aware waitUntil: commit). Captured initial baselines at data/visual-baselines/{home-desktop,home-mobile,onboarding-fresh}.png. Added pixelmatch + pngjs to gateway/kitty-chat/package.json.",
    "Wrote docs/UX_RULES.md (6 design rules + 5 cross-cutting disciplines + Jacob's locked decisions).",
    "Wrote docs/initiatives/kx-06-proactive-feed-v1.json (2 packets, validated): signals-feed + deadline-cards reusing the Repairs primitive.",
    "Added Makefile targets: visual-diff, visual-diff-update, healthcheck, preview, diff-pr.",
    "Main HEAD moved forward 4 commits during session: KX-03 shell consolidation, KX-04 work/studio/library refit, KX-04 settings/providers refit, KX-04-06 coherence audit. Workers pulled in some of my work (Makefile, package.json, harvest doc, KX-05 manifest) via their own commits."
  ],
  "blockers": [],
  "next_action": "Poll KX-05 workers. When attempts complete, run make visual-diff against the worker branch and review. Apply KX-06 once KX-05-02 Repairs primitive is in main. Test KX-05-01 against the real ChatGPT export at /Users/jacobbrizinski/Downloads/data-f19e223a-7158-45b7-a76a-22c3d47efd74-1784835442-7c8da282-batch-0000/.",
  "invalidation_conditions": [
    "HEAD changes beyond f09d049",
    "KX-05 worker outcomes (attempts complete or timeout)"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## What's running

5 KX-05 packets on free workers (all attempt 1, 40-min timeout):
- KX-05-01 onboarding-import
- KX-05-02 self-repairs
- KX-05-03 builder-control-deck
- KX-05-04 experts-shelf
- KX-05-05 chat-polish-sweep

Plus KX-03-01 and B1 closeout-v2 still in flight under Jacob's workers.

## What's ready to ship when those land

- `docs/initiatives/kx-06-proactive-feed-v1.json` — apply when KX-05-02 ships
- `make healthcheck` / `make preview` / `make diff-pr` — daily-driver surface
- `data/visual-baselines/` — initial baselines taken; update with `make visual-diff-update` after each intentional visual change

## What's still pending from earlier

- ~/kb SHIPLOG.md (the gap-filler the wiki promises but doesn't yet ship)
- reasoning-backend-v1: RE-C1 re-queued, RE-C2 and RE-C5 still queued

## For the next session

```
# check workers
./kitty builder queue list

# see the visual diff for a worker's branch
ls data/visual-diffs/<branch>/

# quick health
make healthcheck

# open the dev UI with a checklist
make preview
```