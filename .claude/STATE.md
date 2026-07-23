# Session State — Stale-Branch Audit + KittyBuilder Planning Handoff Complete

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-22T02:08:00Z",
  "head_sha": "3815dbfedc27c8fff624a1218ec6e3962df3285f",
  "branch": "main",
  "worktree": ".",
  "status": "blocked",
  "completed_items": [
    "audited the 8 stale local branches flagged in the prior session's HANDOFF/STATE",
    "confirmed docs/kitty-frontend-experience-harvest-2026-07-20 and feat/frontend-consolidation-wave fully merged (PR #216) — deleted",
    "confirmed reconcile-builder-campaign is a strict ancestor of codex/campaign-p1-05 (merge-base --is-ancestor) — deleted",
    "confirmed backup/local-main-pre-sync-20260717-190337 is a re-committed subset of codex/campaign-p1-05's content — deleted",
    "confirmed the builder runtime code in codex/campaign-p1-05, feat/campaign-alpha-phase-2-integration, feat/wip-campaign-and-runtime is superseded by main's shipped gateway/builder_*.py (touched as recently as 2026-07-21 via PR #218/#220/#221) — deleted all three after archiving",
    "extracted the 4-doc campaign governance framework (kill switch, escalation thresholds, phased rollout) from codex/campaign-p1-05 verbatim to docs/archive/builder-campaign-framework-2026-07/ before deletion; tagged archive/builder-campaign-framework-2026-07 at the branch tip for full history",
    "left feat/reasoning-engine-current untouched — live WIP (2026-07-20, 38 commits behind main), Jacob resuming it himself",
    "ran a code+docs audit of current KittyBuilder (gateway/builder_*.py, docs/PROJECT_STATUS.md, ARCHITECTURE.md, KITTYBUILDER_QUICKSTART.md, KITTYBUILDER_SELF_BUILDING_MVP.md) to ground a planning prompt: KB-S1A-S4 shipped and shadow-mode-safe, KB-S5 (continuation loop/budgets/pause-resume) partially shipped, no mission ingress/clarification phase/prototype gate/merge automation/artifact delivery yet",
    "delivered a self-contained planning prompt (for Opus 4.8 or Fable 5, run outside this session) covering: campaign lifecycle design (clarify -> prototype gate -> build) attaching to the existing builder_queue/builder_initiative state machine, a packet-sized roadmap to daily use, a test plan for short/long x free/paid campaign shapes, and a light audit of current KittyBuilder design choices",
    "pushed docs/archive commit to origin/main",
    "implemented packet cp08b-filter: added --needs-attention flag to initiative list, filtering by state==paused or stop_class==needs_decision via initiative_status() per item"
  ],
  "blockers": [],
  "next_action": "Packet cp08b-filter completed. The --needs-attention flag is implemented; result JSON written to .kittybuilder-result-23.json. Blocked on Jacob running the delivered KittyBuilder planning prompt in a separate Opus 4.8 / Fable 5 session; the resulting roadmap/packets are the next work item",
  "invalidation_conditions": [
    "HEAD changes beyond 3815dbfedc27c8fff624a1218ec6e3962df3285f",
    "branch or registered worktree changes",
    "origin/main advances beyond 3815dbfedc27c8fff624a1218ec6e3962df3285f"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

`main` = `origin/main` at `3815dbf`, working tree clean. This worktree (`kittybuilder/kb_mrwte23v_1c71`) implements packet `cp08b-filter`: add `--needs-attention` to `initiative list`. Changes to `gateway/builder_cli.py` and `tests/test_builder_cli.py` only. The handler uses `initiative_status()` per initiative to filter by derived state==paused or stop_class==needs_decision. 111/111 tests pass.

## Known follow-up

- Image Studio V1's ComfyUI IPAdapter_FaceID node names are still unverified against a live ComfyUI engine — ComfyUI isn't running locally. Smoke-test (character add → recipe pick → generate → gallery) whenever ComfyUI is up.
- `feat/reasoning-engine-current` (reasoning-tier classification, context budget scaling, privacy-safe execution receipts) is real unmerged WIP, 38 commits behind main — Jacob is resuming this himself, not part of this session's scope.
- KittyBuilder daily-driver roadmap depends on output from the planning prompt Jacob is running externally (see `next_action` above) — nothing to build yet until that comes back.
- A stale `GITHUB_TOKEN` env var keeps shadowing the valid `gh` keyring credential on push (credential helper is already correctly `!gh auth git-credential` — this isn't a config problem, something in Jacob's shell/terminal setup exports `GITHUB_TOKEN` outside any checked dotfile: not in `~/.zshrc`, `~/.zprofile`, `~/.zshenv`, `~/.bash_profile`, `~/.bashrc`, `~/.profile`, `.envrc`, or the Claude Code shell snapshot). Workaround each time: `unset GITHUB_TOKEN` before `git push`/`gh` operations.
