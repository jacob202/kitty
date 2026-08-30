# Kitty Feature Reference Map

This document serves as a long-range product research and strategic reference map for Kitty's core feature areas. Kitty is a calm, local-first personal operating layer that decides what matters, shows what changed, and makes the next action obvious.

---

## Reality Check Against Current Repo (Read First)

The codebase is already significantly mature. **Kitty already has:**
- A functioning 8-tab Next.js UI shell (Home, Chats, Projects, Docs, Providers, Agents, Image Lab, Settings).
- A Command Palette using `cmdk` reaching all 8 tabs plus Tasks, Tools, and Terminal.
- Honest chat save-state, Provider Center, and active project/docs panels.
- A `HomeState.tsx` dashboard that already fetches gateway health, What's Next, Needs You, Active Projects, What Changed, Today, and Capture data via `@tanstack/react-query`.
- Tailscale phone-access scripts.

The frontend uses React Query, not SWR. Data fetching is largely wired. The primary UI challenge is now orchestration, ranking, and component cleanliness, not building things from scratch.

## Do Not Rebuild Existing Work

When referencing this document for future development:
1. **Do not rebuild existing panels or routes.** Always check `src/components/` and `gateway/routes/` first.
2. **Do not introduce new state management paradigms.** React Query is the standard; do not rewrite to SWR.
3. **Avoid premature abstraction.** Do not introduce YAML widget configs, heavy feature flags for every endpoint, or Tauri migrations unless specifically required. Feature flags are only for genuinely optional external integrations (Image Lab, GitHub, Gmail, Calendar, cloud models).

---

## 1. Home / Bento Dashboard

*   **Current Kitty state:** Managed by `src/components/HomeState.tsx`. It already includes Health, What’s Next, Needs You, Active Projects, What Changed, Today, and Capture.
*   **Best reference repos:** Homepage, Homarr, Dashy.
*   **Best patterns to steal:** Modular grid layouts, service widgets, instant loading, offline-capable hydration.
*   **What not to copy:** Generic homelab service discovery, over-customizable widget catalogs.
*   **Strategic direction:** Refine Home into a true executive dashboard. Cards should be registered in a thin, typed configuration object (not YAML). Cards should dynamically resize and reorder based on urgency (e.g., if gateway is offline, Status expands; if no approvals, Needs You collapses).

## 2. What’s Next / Decision Engine

*   **Current Kitty state:** Already implemented in `HomeState.tsx` via `useActions`, `useNeedsJacob`, `useProjects`, `useProjectNextSteps`, and `useTodos`.
*   **Best reference repos:** Vikunja, Logseq, Linear (Focus view).
*   **Best patterns to steal:** Clear separation of the single most important next action.
*   **What not to copy:** Priority matrices, Kanban boards.
*   **Strategic direction:** The issue is ranking and clarity, not missing endpoints. Build a shared utility ranking function that chooses the highest priority item across proposed actions, needs-Jacob entries, project next steps, and open todos. Surface *why* this specific action is next.

## 3. Needs You / Approval Queue

*   **Current Kitty state:** Exists within `HomeState.tsx` via `useActions('proposed')` and `useNeedsJacob`.
*   **Best reference repos:** Home Assistant, GitHub Actions manual approvals, Plane.
*   **Best patterns to steal:** Simple accept/reject primitives, clear context injection.
*   **What not to copy:** Notification overload, generic feeds.
*   **Strategic direction:** Refine the presentation. Show the proposed action and two clear buttons (Approve / Reject). Maximize context so the decision is frictionless.

## 4. Status / Gateway Health

*   **Current Kitty state:** `HealthStrip` inside `HomeState.tsx` and `MonitorPanel.tsx` exist.
*   **Best reference repos:** Uptime Kuma.
*   **Best patterns to steal:** Heartbeat tracking, clear green/red/yellow status.
*   **What not to copy:** Distributed tracing, aggressive alerting.
*   **Strategic direction:** Status Impact mapping. Don't just show "Gateway Up"; show what is actually affected (e.g., "Chat works, Docs unavailable").

## 5. Command Palette / Launcher

*   **Current Kitty state:** `CommandPalette.tsx` exists, uses `cmdk`, and routes to all 8 tabs + Tasks, Tools, Terminal.
*   **Best reference repos:** cmdk, Raycast.
*   **Best patterns to steal:** Keyboard-first, fuzzy search, flat hierarchy.
*   **What not to copy:** Cloud search, deep nested menus.
*   **Strategic direction:** Refactor the hardcoded list into a modular command registry. Include dynamic actions like "Toggle Sidebar", "Capture Thought", or "Focus Next Action".

## 6. Docs / Knowledge Library

*   **Current Kitty state:** `DocumentsPanel.tsx` is wired.
*   **Best reference repos:** Logseq, Joplin, AFFiNE.
*   **Best patterns to steal:** Markdown-native storage, fast local search.
*   **What not to copy:** Heavy collaborative features (Notion).
*   **Strategic direction:** Keep it Markdown. Only introduce semantic search (embeddings) later if local flat-file search proves insufficient.

## 7. AI Chat / Providers / Agents

*   **Current Kitty state:** `ChatMessage.tsx`, `AgentPanel.tsx`, `ProviderCenter.tsx` exist; chat persistence is wired.
*   **Best reference repos:** LibreChat, Open WebUI, AnythingLLM.
*   **Best patterns to steal:** Seamless provider switching, local history management.
*   **What not to copy:** Multi-user enterprise RBAC.
*   **Strategic direction:** Keep chat linear. Focus on robust provider fallback and artifact generation over complex agent graph UIs.

## 8. Projects / Coding Cockpit

*   **Current Kitty state:** `ProjectsPanel.tsx` is wired to real data.
*   **Best reference repos:** VS Code, Plane, Vikunja.
*   **Best patterns to steal:** Fast project switching, surfacing READMEs/recent commits.
*   **What not to copy:** Jira-style issue tracking.
*   **Strategic direction:** Maintain as a cockpit for context. Focus on answering "What is the current state of this codebase?"

## 9. Capture / Inbox / Ideas

*   **Current Kitty state:** `CapturePanel.tsx`, `JournalPanel.tsx` are wired.
*   **Best reference repos:** Logseq, iOS Notes.
*   **Best patterns to steal:** Zero-friction text entry, chronological feed.
*   **What not to copy:** Complex tagging.
*   **Strategic direction:** Focus on capture speed. Later, add background auto-categorization via LLM (e.g., suggesting a capture is actually a task).

## 10. Image Lab

*   **Current Kitty state:** `ImageGenPanel.tsx` exists as a placeholder.
*   **Best reference repos:** Fooocus, ComfyUI, Draw Things.
*   **Best patterns to steal:** Fooocus's prompt-first simplicity, history gallery.
*   **What not to copy:** Node editors.
*   **Strategic direction:** Keep it prompt-driven. Optionally integrate Draw Things via MCP for local generation when the feature flag is enabled.

## 11. Desktop / PWA / Local-first Shell

*   **Current Kitty state:** Next.js PWA manifest and install banner exist.
*   **Best reference repos:** Tauri.
*   **Best patterns to steal:** Offline-first caching, native feel.
*   **What not to copy:** Electron footprint.
*   **Strategic direction:** Rely on the PWA. Defer any Tauri migration until the web platform is genuinely restrictive for the required features.

## 12. Visual System / Component Quality

*   **Current Kitty state:** Inline styles and custom CSS across `HomeState.tsx`, `Rail.tsx`, etc.
*   **Best reference repos:** shadcn/ui.
*   **Best patterns to steal:** Copy-paste component ownership, accessible primitives.
*   **What not to copy:** Over-engineering.
*   **Strategic direction:** Extract consistent design primitives (Card, Button, Badge, StatusDot, EmptyState, ActionRow, Skeleton) to clean up large files like `HomeState.tsx`. Maintain the calm, crude Kitty aesthetic.

---

## Next Build Phase: Home & Orchestration

(See the current `implementation_plan.md` for the immediate execution plan.)
