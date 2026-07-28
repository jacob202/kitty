# Session State — Builder requeue/recovery, Experts, Library/Projects split, Home tile fixes

<!-- kitty-state
{
  "schema_version": 2,
  "updated_at": "2026-07-28T19:30:00Z",
  "head_sha": "d23d346517e1e5a3adf7a4e9657530123e7fca1c",
  "branch": "jacob202/fix-description",
  "worktree": "amphipod",
  "status": "complete",
  "completed_items": [
    "Builder: requeue + recover_stale backend actions (2 new action files, builder_control.py updated)",
    "Builder: staleness detection (10min), per-packet requeue, bulk recover, confirmation dialog, staleness indicators on cards and BuilderBrain",
    "Experts: Chat.expertId/systemPrompt fields, handleNewExpertChat with auto-generated prompts, ExpertStrip wired to create real expert chats",
    "Library/Projects: ProjectsView.tsx, ViewRenderer dispatch, Rail/BottomNav swap builder→projects, LibraryView simplified",
    "Home tiles: ExpertStrip functional, ActiveProjects targets ProjectsView, Today todos clickable",
    "Work/Builder: Builder removed from Rail, accessible from WorkView + command palette"
  ],
  "blockers": [],
  "next_action": "Commit, push, verify CI, merge PR #289",
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
      "what": "Push the UI enhancement commits, verify CI passes on PR #289",
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
  "invalidation_conditions": ["HEAD changes beyond d23d346"],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": {
    "number": 289,
    "state": "OPEN",
    "head_sha": "224d7bd4533cd637d861a433499e0acd073fd66b"
  }
}
-->

## Current checkpoint
`jacob202/fix-description` at `d23d346`. 17 files modified/created covering Builder queue recovery, expert chat creation, library/projects separation, and home tile clickability. 1 dirty file: `gateway/kitty-chat/package-lock.json`.

## Lessons applied
- CLI-to-UI gap pattern: backend recovery logic existed in `builder_queue_leases.py`/`builder_queue_runs.py` with full CLI support but no web API surface. Fix was 2 action handlers + ~198 lines of frontend.
- ExpertStrip was a dead no-op: `onClick={() => onNavigate('chat')}` created no expert chat. Fix required extending the Chat model, adding context-aware chat creation, and wiring through 4 component layers.
- Rail/BottomNav must match ViewRenderer dispatch — swapping "builder" for "projects" required updates in 6 files (Rail, BottomNav, ViewRenderer, CommandPalette, WorkView, and the new ProjectsView).
