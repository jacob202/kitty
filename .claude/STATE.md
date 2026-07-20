# Session State — Chat Recovery Complete; Heists Wired; Tree Cleaned

<!-- kitty-state
{
  "schema_version": 1,
  "updated_at": "2026-07-20T11:15:08Z",
  "head_sha": "da5fc579bdabf20c6d9595c7e25c28becb36868d",
  "branch": "main",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "audit-refactor work committed: builder_queue split into layered modules, CORS allow-lists, async httpx knowledge download, curation except tightening (c83eb91..33ee509)",
    "feat/memory-evidence-ids merged: typed MemoryEvidence with memory ids in the CR-04 trailer (2a9162d)",
    "CR-06 shipped directly: forget-with-5s-undo-grace on the memory block, DELETE only after grace (78143f6)",
    "CR-07 shipped directly: one-shot model override chip + explicit D10 privacy gate on overrides, forbidden = 400 (9bd57af)",
    "imagen heist finished: feat/imagen-img01-v2 merged (UUID/6-state IMG-01 store per harvest doc), /image/history reads durable store (b9a8a5d)",
    "tutor heist wired: /tutor/quiz|attempt|grade|term routes + TutorPanel in kitty-chat, verified live in browser (033cea0)",
    "fixed latent branch_leases.lease_ts->created_at migration gap breaking builder status on live DB (8a434cc)",
    "chat-recovery-v1 and chat-recovery-continuation-v1 paused with evidence notes: all packets delivered",
    "19 stale branches deleted, 11 stale worktrees removed; kept only branches with unmerged work"
  ],
  "blockers": [],
  "next_action": "Ask Jacob whether to push main (12 local commits); then pick: IMG-02 (ComfyUI cancellation) via builder, or review the kept campaign/reconcile branches",
  "invalidation_conditions": [
    "HEAD changes beyond da5fc579bdabf20c6d9595c7e25c28becb36868d",
    "branch or registered worktree changes",
    "the active Mission changes"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Current checkpoint

- `main` at `da5fc57`, 12 commits ahead of the session start (`221aea6`).
  Nothing pushed — pushing needs Jacob's explicit approval.
- All 7 chat-recovery packets are delivered. CR-01..05 via the Builder loop
  (pre-session); CR-06/CR-07 directly on main this session, superseding the
  CR-06b/CR-07b replacement packets. Both initiatives are paused with
  evidence notes pointing at the commits.
- Verified live in the running app (gateway restarted on current code, UI
  dev server on :4000): tutor quiz loop end-to-end, model-override chip,
  thread-goal strip, builder home tile (was crashing on `l.created_at`).
- `make ui-test && make ui-build` green (233 UI tests). Final full pytest:
  2565 passed; the only failures were the continuity checks reading these
  docs mid-rewrite, and they pass against the final docs (10/10).

## Landed this session (all local commits on main)

| commit  | what |
|---------|------|
| c83eb91 | builder_queue split (audit §2.2) + monkeypatch-safe DB default |
| 1673510 | CORS allow-lists, kitty env fail-loud, github token guard |
| 3613b57 | knowledge URL download requests→httpx async |
| 99d61e4 | curation scripts bare-except tightening |
| 33ee509 | audit doc + PR210 refs + session state |
| 2a9162d | merge feat/memory-evidence-ids (memory ids in trailer) |
| 78143f6 | CR-06 forget with undo grace |
| 9bd57af | CR-07 model override + explicit privacy gate |
| b9a8a5d | merge feat/imagen-img01-v2 + durable /image/history |
| 033cea0 | tutor routes + TutorPanel wiring |
| 8a434cc | branch_leases lease_ts→created_at migration |
| da5fc57 | record continuation manifest (paused) |

## Known follow-ups (named, not built)

- IMG-02..IMG-06 remain unstarted (cancellation, atomic persistence,
  lineage, engine unification, health) — see the imagelab harvest doc.
- Builder projection for CR-06/07 still shows the original tasks as
  eligible-but-paused; a formal operator closeout would need the
  attempt-CLI roundtrip if Jacob wants the ledger spotless.
- reasoning-backend-v1 (3 packets) and builder-test-hardening follow-ups
  untouched.
- Campaign/reconcile branches kept for review: codex/campaign-p1-05 (25
  ahead), codex/reconcile-phase2-p104 (30), reconcile-builder-campaign (23),
  feat/project-control-plane-foundation (14), feat/wip-campaign-and-runtime
  (4), feat/campaign-alpha-phase-2-integration (3), recon/agent-leverage (2),
  kittybuilder/kb_mrpo81ct_9885 (2).
