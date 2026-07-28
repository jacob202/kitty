# Handoff — Builder requeue/recovery, Experts, Library/Projects split, Home tile fixes

<!-- kitty-handoff
{
  "schema_version": 2,
  "updated_at": "2026-07-28T19:30:00Z",
  "head_sha": "d23d346517e1e5a3adf7a4e9657530123e7fca1c",
  "base_sha": "0a2a04480ecd555168656de62dfa9a3cc971031f",
  "branch": "jacob202/fix-description",
  "worktree": "amphipod",
  "status": "valid",
  "completed_items": [
    "Builder: requeue + recover_stale actions in backend (2 new action files, builder_control.py updated)",
    "Builder: staleness detection (10min threshold), per-packet requeue, bulk recover, confirmation dialog for cleanup",
    "Builder: staleness indicators on packet cards, BuilderBrain stale section",
    "Experts: Chat model extended with expertId/systemPrompt fields",
    "Experts: handleNewExpertChat in KittyContext with auto-generated expert system prompts",
    "Experts: ExpertStrip wired to create real expert-context chats (was dead no-op)",
    "Library/Projects: ProjectsView.tsx created, ViewRenderer dispatches projects separately",
    "Library/Projects: Rail/BottomNav swap builder → projects, LibraryView simplified to documents-only",
    "Home tiles: ExpertStrip functional, ActiveProjects navigates to ProjectsView, Today todos clickable",
    "Work/Builder: Builder removed from Rail, accessible from WorkView 'Open full Builder' link + command palette"
  ],
  "blockers": [],
  "next_action": "Commit, push, verify CI on PR #289, then merge",
  "parallel_work": [
    {
      "kind": "pr",
      "ref": "#288",
      "owner": "jacob202",
      "touches": [".env.example", "gateway", "kitty", "tests"],
      "observed_at": "2026-07-28T19:30:00Z"
    },
    {
      "kind": "pr",
      "ref": "#290",
      "owner": "jacob202",
      "touches": ["README.md", "docs", "repomix.config.json", "scripts"],
      "observed_at": "2026-07-28T19:30:00Z"
    },
    {
      "kind": "pr",
      "ref": "#291",
      "owner": "jacob202",
      "touches": ["docs"],
      "observed_at": "2026-07-28T19:30:00Z"
    },
    {
      "kind": "pr",
      "ref": "#292",
      "owner": "jacob202",
      "touches": ["docs"],
      "observed_at": "2026-07-28T19:30:00Z"
    },
    {
      "kind": "worktree",
      "ref": "fix/dogfood-provider-chat-shell-2026-07-28",
      "owner": "jacob202",
      "touches": [".env.before-agentrouter", "config", "gateway/routes"],
      "observed_at": "2026-07-28T19:30:00Z"
    }
  ],
  "recommendations": [
    {
      "id": "merge-pr-289",
      "what": "Push the UI enhancement commits, verify CI passes on PR #289, and merge the sweep",
      "why": "Builder recovery, experts, library/projects split, and home tile fixes need to land on main",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "chat-context-visibility",
      "what": "Add system prompt preview and token window visualization to ChatView",
      "why": "Chat is opaque — users can't see what context the model receives or how full the window is",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    },
    {
      "id": "review-doc-prs",
      "what": "Review and close PRs #290-292 before they accumulate merge conflicts",
      "why": "Three docs-only PRs open simultaneously — kitchen-sink risk if left unmerged",
      "class": "code",
      "status": "ready",
      "blocked_by": null,
      "release_check": null,
      "deferred_count": 0,
      "first_deferred": null
    }
  ],
  "invalidation_conditions": ["HEAD advances past d23d346", "PR #289 merges to main"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 289,
    "state": "OPEN",
    "head_sha": "224d7bd4533cd637d861a433499e0acd073fd66b"
  }
}
-->

## What was done
- **Builder queue recovery:** Added `requeue` and `recover_stale` backend actions (`builder_control.py` + 2 new action files). Frontend staleness detection (10min threshold), per-packet requeue buttons, bulk recover scan, confirmation dialog for destructive cleanup, staleness dots on packet cards, stale section in BuilderBrain. `BuilderSurface.tsx` +198 lines.
- **Experts functional:** Extended `Chat` model with `expertId`/`systemPrompt` fields (`types.ts`). Added `handleNewExpertChat` with auto-generated expert system prompts (`KittyContext.tsx`). Wired `ExpertStrip` in `HomeState.tsx` to create real expert-context chats instead of the previous dead no-op. Wired through `HomeView.tsx` and `page.tsx`.
- **Library/Projects split:** Created `ProjectsView.tsx`. Updated `ViewRenderer.tsx` to dispatch `projects` separately. Simplified `LibraryView.tsx` to documents-only. Swapped "builder" → "projects" in `Rail.tsx` and `BottomNav.tsx`. Added Projects to `CommandPalette.tsx`. Added "Open full Builder" link to `WorkView.tsx`.
- **Home tile fixes:** `ExpertStrip` now creates expert chats. `ActiveProjects` navigates to dedicated ProjectsView. `TodayPanel` todos are now clickable buttons that navigate to Work view.

## In-flight / WIP
- None — all items completed for this session

## Other work in flight (not mine)
- **PR #288 (draft):** `fix/runtime-truth-agentrouter-2026-07-28` by jacob202 — runtime lifecycle, provider, tool state truthfulness
- **PRs #290-292:** docs-only PRs (readme refresh, image studio architecture, builder boundary docs)
- **Worktree `fix/dogfood-provider-chat-shell-2026-07-28`:** uncommitted provider work
- **Builder queue:** UNAVAILABLE — DB file not accessible from this worktree

## Blockers
- None

## Next move
Commit, push, verify CI on PR #289, then merge

## Files changed this session
- `gateway/routes/builder_control.py` — added requeue + recover_stale actions
- `gateway/actions/builder_requeue_packet.py` (new) — CLI-backed packet requeue
- `gateway/actions/builder_recover_stale.py` (new) — CLI-backed stale recovery
- `gateway/kitty-chat/src/components/BuilderSurface.tsx` — staleness detection, requeue buttons, confirmation dialog, indicators
- `gateway/kitty-chat/src/lib/types.ts` — Chat.expertId + Chat.systemPrompt
- `gateway/kitty-chat/src/state/KittyContext.tsx` — handleNewExpertChat + buildExpertSystemPrompt
- `gateway/kitty-chat/src/components/HomeState.tsx` — ExpertStrip wiring, TodayPanel clickable todos
- `gateway/kitty-chat/src/components/HomeView.tsx` — onExpertClick prop passthrough
- `gateway/kitty-chat/src/app/page.tsx` — onExpertClick wired to handleNewExpertChat
- `gateway/kitty-chat/src/components/ProjectsView.tsx` (new) — standalone projects view
- `gateway/kitty-chat/src/components/ViewRenderer.tsx` — projects dispatch, ProjectsView import
- `gateway/kitty-chat/src/components/LibraryView.tsx` — simplified to documents-only
- `gateway/kitty-chat/src/components/Rail.tsx` — builder → projects swap
- `gateway/kitty-chat/src/components/BottomNav.tsx` — builder → projects swap
- `gateway/kitty-chat/src/components/CommandPalette.tsx` — projects added
- `gateway/kitty-chat/src/components/WorkView.tsx` — "Open full Builder" link
- `docs/plans/kitty-ui-enhancement-plan.html` (new) — comprehensive execution plan
