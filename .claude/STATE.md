# Session State — Open WebUI daily driver shipped, James likeness solved

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-08-03T05:30:00Z",
  "head_sha": "015291e7",
  "branch": "feat/image-studio-james",
  "worktree": "main",
  "status": "complete",
  "completed_items": [
    "Open WebUI daily-driver baseline: launch, login, streaming, persistence, diagnostics, backup, restore, rollback (PR #384)",
    "Handoff defects 2, 3 and 4 fixed and regression-tested (PYTHONPATH/cwd shadowing, SSE contract, pending-account trap)",
    "Chat routing restored: AgentRouter token revoked, Kitty runs on OpenRouter",
    "System prompt cut from 447,759 to ~24,200 chars; TTFT 26s to 6.4s",
    "Kitty memory restored; mem0 search had never worked (user_id passed as a filter)",
    "Five-model menu (Auto/Fast/Think/Code/Vision) with distinct upstream models",
    "Eight-tool OpenAPI surface at /tools/v1 and five workspace agents; the model emits real tool calls",
    "Flux hosted image lane at ~2.5c/image, gated behind KITTY_IMAGE_PAID_ENABLED",
    "James identity SOLVED with PuLID-Flux: weight 0.95, identity LoRA off, ~21s/image, consistent across scenes",
    "Jacob's 19 personal photos removed from the tracked tree; repository made private at his instruction"
  ],
  "blockers": [
    "19 personal photos remain in git history; removal needs a history rewrite and force push, which is Jacob's call",
    "AGENT_ROUTER_TOKEN in .env is revoked (unauthorized_client_error); AgentRouter disabled, OpenRouter in use"
  ],
  "next_action": "Item 2 of docs/plans/image-studio-next-four-2026-08-02.md — make characters store the PuLID recipe and drive generation",
  "parallel_work": [
    "Other sessions and Builder workers push to feat/openwebui-tomorrow-ready; this session moved to feat/image-studio-james to stop colliding"
  ],
  "recommendations": [
    "Cancel the Qwen identity retrain (item 3) unless the next batch disappoints — PuLID already delivers the body hair it was meant to unlock",
    "Delete pod c8pwk8tb79d57l to stop paying storage on a now-redundant 50GB volume",
    "A RunPod network volume (~$4/month) would end the model re-download cycle; stopping a pod releases its GPU and it often cannot be restarted"
  ],
  "invalidation_conditions": [
    "HEAD changes beyond 015291e7",
    "config/providers.json active changes away from auto"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": 384
}
-->

## Execution ownership

- this session: interactive
- no Builder bundle, task, or lease
- Builder workers and other sessions own `feat/openwebui-tomorrow-ready`. This
  session began there, collided with their pushes, and moved to
  `feat/image-studio-james` at Jacob's instruction.

## Evidence

| What | Where |
|---|---|
| Open WebUI onboarding | `docs/plans/openwebui-onboarding-progress.md` |
| Machine-readable acceptance | `docs/plans/openwebui-onboarding-checklist.json` |
| James proven settings | `docs/plans/james-workflow-2026-08-02.md` |
| Remaining plan + the PuLID solution | `docs/plans/image-studio-next-four-2026-08-02.md` |
| Runner | `scripts/james_comfy.py` |

## Tests

Last full run: `3739 passed, 10 failed, 1 skipped`. All ten failures reproduce
identically at branch point `e1c175c5` with the same `.env` present — four
continuity-state, one cold-start, five provider tests that leak environment
between tests. None caused by this work.

Touched-suite runs since: `84 passed` across image, tool-server, chat, memory,
Open WebUI, and builder-publish suites.

## Spend

About $2.10 of provider and GPU credit: two OpenRouter test images (~$0.13), one
Flux API image (~$0.03), and roughly $1.90 of RunPod time across four pods, most
of it repeated 17GB model downloads.

## KB effectiveness

- no receipt recorded yet
