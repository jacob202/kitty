# Kitty-Wide Frontend + Product-Experience Harvest — 2026-07-20

**Scope:** Every Kitty product surface, all feature-adjacent frontend references, and a single cross-product experience plan.
**Status:** Research + planning audit — no Kitty runtime modified beyond document additions.
**Continuity:** Continuity checks all pass (27/27). Image branch integrated at 082a2e8. origin/main synced via PR #215.

This audit replaces the Image-Lab-only frontend scope with a Kitty-wide frontend and product-experience harvest. Image Lab receives proper treatment, but Home, Chat, Builder, Memory, Projects, Automations, Tutor, Integrations, and evaluation surfaces go through the same quality process.

---

## Repository State (integration complete)

| Item | Value |
|---|---|
| Kitty branch | `main` |
| Kitty HEAD SHA | `082a2e8b3d08ea87a1f4f0d6d150e4e0b8db5739` |
| origin/main SHA | `11ce958103867582cf1265701fe4a0fd4de2bf60` |
| Image branch merged | `feat/image-packets-current` (a55a19c..8dd3b21) at 082a2e8 |
| ComfyUI offline | Explicitly recorded validation limitation |
| COMFY_COMMIT | Not invented; ComfyUI cancel (6e495c8) landed on main before image-branch merge |
| Continuity checks | 27 PASS, 0 WARN, 0 FAIL |
| Worktrees registered | 12 (including canonical) |

---

## Stage 2 — Current Kitty Product Surface Inventory

### Application Shell

**Layout:** Rail (94px) → Sidebar (268px, chat only) → Main area with TopBar (58px) → content + InputBar.

**Themes:** `cosmic` (starfield + glass), `day` (manila paper), `night` (chalkboard).
- Cosmic uses `backdrop-filter: blur(14px)` glass treatment
- Day/night use `:root:not([data-theme])` and `[data-theme="day/night"]` selectors
- Paper grain overlay via `PaperGrain` component
- Wob SVG filter via `WobFilters` component

**Fonts:** Bricolage Grotesque (display), Hanken Grotesk (body), JetBrains Mono (mono).

**State management:** Single large `KittyChatInner` component (1,387 lines) in `page.tsx`. React hooks for most state; React Query for gateway data. No context/state library.

**Client-server:** `gateway.ts` + `queries.ts` in `lib/`. Gateway proxy at `/proxy/*`. Runtime manifest from `runtime.py` routes.

### Navigation and Views

**Rail** (4 items): home, chats, builder, settings. SVG icons with wob filter. Active state uses `var(--ginger-fade)` background.

**Views** (activeView state):
- `home` — HomeState (next steps, deadlines, builder glance, states, actions)
- `chat` — Chat messages + ThreadGoal + SignalFeed + InputBar
- `tasks` — TaskPanel + TodoPanel
- `tools` — Grid of ToolCard wrappers: agents, monitors, image gen, tutor, loops, insights, prompts
- `terminal` — TerminalStrip
- `projects` — ProjectsPanel
- `docs` — DocumentsPanel
- `providers` — ProviderCenter
- `agents` — AgentPanel (duplicate of tools:agents)
- `images` — ImageGenPanel (duplicate of tools:image gen)
- `tutor` — TutorPanel (duplicate of tools:tutor)
- `settings` — SettingsPanel
- `builder` — BuilderPanel

### Component Ownership and Purpose

| Component | Route/Placement | Data Source | Purpose | State Coverage |
|---|---|---|---|---|
| TopBar | All views | gateway runtime manifest | Model selector, runtime badge, project selector, cat state | Mobile/desktop variants |
| Rail | Desktop only | none | Primary navigation (4 items) | Active state |
| SessionSidebar | Chat view | localStorage + gateway chats | Chat history, search, new chat | Today/yesterday/earlier sections |
| InputBar | Chat view | local state | Text input, attachments, mic, model override, send/stop | Streaming state, compact mode |
| ChatMessage | Chat view | Message array | Rendered message, memory evidence, tool calls, retry | Streaming, first-in-run, mood |
| HomeState | Home view | 12+ React Query hooks | Next steps, deadlines, builder glance, state changes, actions, inbox | Loading/empty/error per section |
| BuilderSurface | builder view | gateway runtime manifest | Initiative/packet status, queue, attempts, failures | Loading/empty/degraded |
| ImageGenPanel | tools/images views | gateway image routes | Prompt input, style chips, engine selector, history gallery | Checking/offline/generating/done/error |
| TutorPanel | tools/tutor views | gateway tutor routes | Quiz flow, term browser, mastery display | Loading/empty/answered |
| ProviderCenter | providers view | gateway models + plugins + MCP + image | Model routing, plugins, MCP servers/tools, external lanes, image engines | Live/offline/degraded per section |
| SettingsPanel | settings view | localStorage | Theme toggle, preferences | Inline only |
| ProjectsPanel | projects view | gateway projects | Project list, create, select | Loading/empty |
| DocumentsPanel | docs view | gateway knowledge | Document browse | Loading/empty |
| AgentPanel | tools/agents views | gateway agent routes | Agent spawn, monitor, stop | Loading/empty/running |
| MonitorPanel | tools view | gateway monitor routes | Web monitor status | Loading/empty |
| LoopWatch | tools view | gateway loops | Loop toggle | Loading |
| InsightFeed | tools view | gateway insights | Insight cards, dismiss, action | Loading |
| PromptToolkit | tools view | gateway prompts | Prompt templates | Loading |
| OnboardingModal | First visit | localStorage | Name, theme, avatar | Single flow |
| CommandPalette | Global (Cmd+K) | local state | Chat search, new chat, view navigation | Open/closed |
| SignalCard | Chat view | gateway triage | Inbox entries inline in chat | Compact/full |
| ThreadGoal | Chat view | gateway objective | Chat objective display and edit | Saved/editing |
| PwaInstallBanner | All views | PWA install state | Install prompt | Installed/installing/error |
| CrayonCat | Global corner | catState prop | Mascot with idle/working/done/broke states | Animated CSS classes |
| ErrorBoundary | Per-view | React error boundary | Catch render errors | Fallback UI |
| Skeleton | Various | isLoading | Loading placeholder | Inline |
| CronPanel | — | gateway cron | Cron schedule editor | — |
| JournalPanel | — | gateway journal | Journal interview + synthesis | — |
| CapturePanel | Home view | gateway capture | File upload | — |
| TodoPanel | Tasks view | gateway todos | Task list | — |
| TaskPanel | Tasks view | gateway tasks | Background tasks | — |
| WobFilters | Global | SVG filters | Hand-drawn wobble effect | Always present |
| DreamStatus | — | gateway dream | Dream loop status | — |
| PerfDashboard | — | gateway perf | Performance metrics | — |
| TerminalStrip | Terminal view | gateway logs | Tail log | — |

### Critical Experience Issues Found

**Inconsistent control sizing:** Buttons range from 10px to 16px font. Chips are 10px mono. Input bar uses 14px. Save status is 10px mono. No consistent touch target or text sizing.

**Tiny text epidemic:** font-size: 10px found in TopBar (RuntimeBadge, projectStatus), SessionSidebar (section headers), ChatMessage (model label), InputBar, and most utility labels. font-size: 11px in save-status bar, gateway offline banner, and comment captions.

**Excessive monospace styling:** RuntimeBadge, section headers in sidebar, ToolCard titles, model selectors, status badges, chat timestamps, and nearly every label uses `var(--font-mono)`. This gives the product an admin-tool feel rather than a personal companion.

**Panel-within-panel layouts:** Feature panels (ImageGenPanel, TutorPanel, AgentPanel) are wrapped in `ToolCard` components — a card inside a card inside a grid. The result is visual nesting that makes the product feel like a dashboard of mini-apps.

**Unclear navigation:** The Rail has only 4 items (home, chats, builder, settings) but there are 14+ distinct views. Image Lab, Tutor, Projects, Docs, and Providers are reachable only through HomeState links or specific query-anchored navigation. The Tools drawer is a catch-all grid. The Chat view is the only view with a persistent input bar.

**Poor information density:** The Home screen packs many sections (next steps, deadlines, builder glance, states, actions, inbox, tasks) but uses full-width cards with generous padding. On mobile, each section gets a full screen height.

**Overloaded status badges:** The TopBar shows cat state (working/idle/broke), runtime state (live/offline/degraded), streaming label, and model from-gateway indicator simultaneously. Each uses a different visual vocabulary.

**Generic errors:** Image Gen shows "generation failed — is ComfyUI running?" regardless of the actual error cause. The gateway offline banner says "gateway offline" with a retry button. The brief banner says "Brief unavailable (unknown). Chat still works."

**Actions that disappear after refresh:** The image gallery (`_history`) is in-memory and lost on restart. The model override chip disappears after one message. No undo for chat deletion.

**Hidden or ambiguous progress:** No loading indicator for the overall app beyond React Query per-query states. No progress for image generation beyond a binary generating/done. Builder progress is a status summary, not a live view.

**Disconnected artifacts:** Generated images exist only in ComfyUI's output folder. Documents are uploaded but have no preview or inline view. Tutor quiz results have no artifact card.

**Duplicated histories:** Chat history is duplicated — once in React state (chats array), once in SQLite (gateway chats_store). Image history is in-memory only.

**Capabilities that look available when unavailable:** Image Gen shows the prompt input and style chips even when ComfyUI is offline. Model selection shows all models even when gateway is unreachable.

**Desktop layouts stacked on mobile:** Mobile mode (≤900px) simply hides the rail and sidebar, stacks the same desktop content with reduced padding. No bottom navigation, no mobile-optimized layouts.

**Surfaces that feel like internal admin tools:** BuilderSurface (packet/attempt/queue state), ProviderCenter (MCP server listings, plugin toggles), TerminalStrip (raw log tail), LoopWatch (loop toggles), InsightFeed (dismissable metric cards). These are operator interfaces, not personal-companion surfaces.

**Leaked infrastructure vocabulary:** "runtime live," "gateway offline," "fromLiveGateway," "branch_leases," "lease_ts," "packet," "attempt," "tool observation," "context enrichment." These terms appear in the main user interface.

**Important features that are visually buried:** Image Lab is one of 6 grid cards in the Tools view and one of 10+ views. Tutor is similarly buried. Memory inspection has no dedicated surface. Project switching is a small `<select>` in the TopBar.

**Features that visually appear more important than they really are:** The model selector dropdown has prominent placement. The runtime badge is always visible. Brief/offline banners take full-width attention. The wob/paper-grain decorative effects are always-visible filters.

### Mobile Behavior

The `isMobile` flag activates at ≤900px. Mobile changes:
- Rail hidden (replaced by hamburger menu in TopBar)
- SessionSidebar hidden (overlay when open)
- TopBar simplified (hamburger, model selector, project selector)
- Content padding reduced (18px 14px 16px for chat)
- InputBar in "compact" mode
- Safe-area-inset-top added to TopBar
- CatCorner hidden at ≤480px

No bottom navigation bar. No mobile-specific layouts for any feature panel. No gesture support. No pull-to-refresh. Search/command palette available but keyboard shortcut is `Cmd+K` (desktop convention).

### Accessibility Behavior

- No ARIA landmarks beyond a few `aria-label` attributes
- No focus ring styling defined
- No `role="status"` on most live regions
- No keyboard navigation pattern beyond default tab order
- No `aria-live` regions for streaming updates
- No reduced-motion media query
- No `prefers-contrast` media query
- Touch targets often below 44px (Rail buttons are 62px wide but nav items are 46px)
- Text contrast appears adequate in all themes but not systematically verified
- `role="status"` found only on gateway banners and save-state indicator

### Duplicated Components / Patterns

1. **ToolCard** — defined inline in `page.tsx:131-161`, not exported. Feature panels are wrapped in copies of the same pattern.
2. **AgentPanel** — appears in tools grid AND agents view (identical component, different wrapping)
3. **ImageGenPanel** — appears in tools grid AND images view (identical component)
4. **TutorPanel** — appears in tools grid AND tutor view (identical component)
5. **Status dots** — at least 4 different implementations (RuntimeBadge, StateBadge, gateway offline banner dot, TopBar streaming dot)
6. **Chip/button styles** — `chipBtnStyle`, `actionButton`, `itemCard`, `chipStyle` — all similar but separately defined
7. **Section cards** — `SectionCard` in HomeState, `ToolCard` inline, `card` from ui.ts, `itemCard` from ui.ts — overlapping patterns
8. **Empty states** — each component implements its own (some use `emptyState` from ui.ts, some inline)
9. **Error states** — each component handles independently (some show error text, some show nothing)
10. **Loading states** — each component handles independently (some use Skeleton, some show text, some show nothing)

### Backend Improvements Not Reflected in Frontend

- Image Lab has durable job store (IMG-01 v2), but frontend still calls legacy `/image/history` with in-memory fallback
- Image Lab has cancellation support (ComfyUI cancel), but frontend shows no cancel button during generation
- Tutor has mastery gates and quiz generation (DTH-03/04), but frontend shows a minimal quiz flow
- Memory has evidence IDs, forget with undo grace (CR-04/06), but frontend has no dedicated memory surface
- Builder has packet/attempt/lease/review state, but frontend shows only a summary glance
- Runtime manifest has detailed availability per provider, but frontend simplifies to live/offline binary

---

## Stage 3 — External Repository Frontend Inspection

### A. Personal Assistant / Resume Loop

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `khoj-ai/pipali` | a640d44 | Task inbox with priority/status, background-work visibility, deliverable cards, result lineage, schedule-to-result view | Apache-2.0 | **Adapt** task inbox hierarchy, background-work presentation, deliverable cards |
| `khoj-ai/khoj` | 1e30154 | Search-first home, "conversations" separated from "agents," research mode with source display | AGPL-3.0 | **Study only** |
| `open-webui/open-webui` | ecd48e2 | Chat-centered navigation, model selector, knowledge collection, prompt library, admin panel | Custom (branded) | **Study only** |

**What Kitty can use for resume loop:**
- "What happened?" — Pipali's task result lineage (task → conversation → artifact chain)
- "What needs me?" — Pipali's priority + attention-required inbox
- "What is next?" — Pipali's schedule-to-result chaining
- "What can I continue?" — Pipali's active-task persistence across sessions
- "What did Kitty make for me?" — Pipali's deliverable/artifact cards linked to source tasks

### B. Chat / Tools / Approvals / Artifacts

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `assistant-ui/assistant-ui` | 05770ec | Streaming message renderer, tool-call cards with expandable details, approval gates, artifact display | MIT | **Adapt** tool-call cards, approval UX, artifact display patterns |
| `open-webui/open-webui` | ecd48e2 | Message composer, attachment upload, tool status indicators, conversation branching | Custom (branded) | **Study only** |
| `ag-ui-protocol/ag-ui` | 3a7433e | Protocol definition for streaming tool calls, state events, interruption/recovery | MIT | **Study** event contract; not frontend code |
| `khoj-ai/pipali` | a640d44 | Chat with inline tool results, artifact cards, retry/resume | Apache-2.0 | **Adapt** inline tool results, retry patterns |

**Key findings for chat UX:**
- `assistant-ui` has the best tool-call card pattern: collapsible section per tool, status indicator, duration, result preview, full-result expansion
- Approval gate should be a modal or inline card, not a raw prompt
- Retry should be available on every failed tool call, not just the last assistant message
- Artifacts need a shared visual model (image, document, code, report) — not a per-feature card

### C. Memory / Knowledge

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `letta-ai/letta-code` | cd60d62 | Memory inspection, fact provenance, confidence, "true now" vs historical, edit/undo | Apache-2.0 | **Adapt** memory-mutation semantics in UI |
| `getzep/graphiti` | 77a3752 | Temporal/provenance data model | Apache-2.0 | **Study data model only** (no frontend) |
| `open-webui/open-webui` | ecd48e2 | Knowledge collection browser, document upload, chunk view | Custom (branded) | **Study only** |

**Frontend guidance for memory:**
- Graphiti has no meaningful frontend — derive the UI from its temporal/episodic concepts (time windows, fact decay, provenance chains)
- The key UI need: a user should see "what Kitty knows about me," sorted by recency, with confidence indicators, and be able to correct or remove facts
- Letta's memory mutation semantics (edit → version → undo) is the right interaction pattern

### D. Work / Missions / Builder

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `OpenHands/agent-canvas` | 7cf8733 | Task canvas, control center, environment selection, approval gates, output/artifact presentation | MIT | **Adapt** canvas layout, approval UX, output cards |
| `khoj-ai/pipali` | a640d44 | Task inbox, active vs waiting, progress indicators, attention requests | Apache-2.0 | **Adapt** task status vocabulary, progress patterns |
| `openinterpreter/openinterpreter` | a4da0fc | Harness/execution policy contracts, CLI-heavy | Apache-2.0 | **Study** contract patterns only |
| `assistant-ui/assistant-ui` | 05770ec | Rich streaming, tool call rendering, interruption | MIT | **Adapt** interruption and tool rendering |

### E. Automations / Proactive Kitty

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `open-webui/open-webui` | ecd48e2 | Task/schedule UI, automation creation | Custom (branded) | **Study only** |
| `home-assistant/core` | f7cdef1 | Automation editor, schedule preview, run history, YAML/natural-language creation, pause/resume | Apache-2.0 | **Adapt** automation editor patterns, schedule visualization |
| `khoj-ai/khoj` | 1e30154 | Scheduled agent runs, result history | AGPL-3.0 | **Study only** |

### F. Image Lab

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `invoke-ai/InvokeAI` | 82e2681 | Prompt workspace, visual hierarchy, gallery, image viewer, selection, keyboard nav, remix/variations, metadata, responsive layout, queue/cancellation, comparison, progressive controls | Apache-2.0 | **Adapt** gallery layout, image viewer, remix UX, metadata display |
| `Comfy-Org/ComfyUI_frontend` | (latest) | Node editor, workflow canvas, queue management | GPL-3.0 | **Study only** — cannot copy |
| `igordanchenko/react-photo-album` | (latest) | Masonry/justified gallery, responsive image layout | MIT | **Direct-copy** gallery layout component |
| `igordanchenko/yet-another-react-lightbox` | (latest) | Lightbox viewer, keyboard navigation, zoom, slideshow | MIT | **Direct-copy** image lightbox viewer |

### G. Tutor / Learning

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| DeepTutor (HKUDS) | b728354 | Lesson structure, quiz flow, answer feedback, term explanations, progress tracking, source citations, difficulty adjustment, review sessions | Apache-2.0 | **Adapt** quiz flow structure, feedback patterns, progress display |
| `khoj-ai/pipali` | a640d44 | Learning session persistence, resume behavior | Apache-2.0 | **Adapt** session resume |

**Additional references needed:** Anki's spaced-repetition UI, Duolingo-style progressive difficulty. These are study-only for interaction patterns.

### H. Projects / Notes / Artifacts

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `khoj-ai/pipali` | a640d44 | Project context, recent work, related conversations, previews, linking tasks/chats/outputs | Apache-2.0 | **Adapt** project-linking patterns |
| `open-webui/open-webui` | ecd48e2 | Document workspace, knowledge collections | Custom (branded) | **Study only** |

### I. Providers / Integrations / Health / Settings

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `home-assistant/core` | f7cdef1 | Integration discovery, setup flows, capability presentation, auth state, degraded/unavailable state, diagnostics, reconnect, permissions | Apache-2.0 | **Adapt** integration health patterns, capability gating, progressive disclosure |
| `open-webui/open-webui` | ecd48e2 | Admin panel, model configuration | Custom (branded) | **Study only** |
| `openinterpreter/openinterpreter` | a4da0fc | Provider/model selection CLI | Apache-2.0 | **Study** selection contract |

### J. Evaluation / Usage / Reasoning Visibility

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `langfuse/langfuse` | 7e0b0bc | Trace navigation, comparison, scorecards, dataset runs, cost/latency, feedback, failure inspection | MIT core | **Adapt** trace and comparison patterns (operator-only) |

### K. Ambient Context / Privacy

| Repository | SHA | Key Frontend Mechanisms | License | Disposition |
|---|---|---|---|---|
| `screenpipe/screenpipe` | cbdeede | Recording indicators, pause, exclusions, deletion, retention, search, timeline, sensitive-app handling, export | Screenpipe Commercial | **Study only** — no source reuse |

---

## Stage 4 — Additional Frontend References Discovered

| Lane | Repository | Pinned SHA | License | Reason | Disposition |
|---|---|---|---|---|---|
| Gallery | `igordanchenko/react-photo-album` | latest | MIT | Responsive masonry/justified gallery — direct replacement for Kitty's inline image list | **Direct-copy** |
| Lightbox | `igordanchenko/yet-another-react-lightbox` | latest | MIT | Full-featured image viewer with keyboard nav, zoom — replaces inline image display | **Direct-copy** |
| Automations | `home-assistant/frontend` | latest | Apache-2.0 | Automation editor, schedule visualization, natural-language scheduling patterns | **Study/adapt** |
| Tutor | `ankitects/anki` | latest | AGPL-3.0 | Spaced-repetition scheduling patterns (study interaction only) | **Study only** |
| Code Display | `shikijs/shiki` | latest | MIT | Syntax highlighting (already using highlight.js — shiki is more modern, WASM-based) | **Adapt** as replacement |
| Settings | `home-assistant/frontend` | latest | Apache-2.0 | Integration discovery, progressive disclosure of advanced settings | **Study/adapt** |

---

## Stage 5 — Code-Harvest Register

### Direct-Copy Candidates

| Mechanism | Source | Pinned SHA | Path | License | Attribution | Kitty Destination | Size | Risks |
|---|---|---|---|---|---|---|---|---|
| react-photo-album | igordanchenko/react-photo-album | latest | npm package | MIT | npm dependency | `gateway/kitty-chat/package.json` | ~30KB gzipped | Standard React dependency |
| yet-another-react-lightbox | igordanchenko/yet-another-react-lightbox | latest | npm package | MIT | npm dependency | `gateway/kitty-chat/package.json` | ~50KB gzipped | Standard React dependency |

### Adapt Candidates

| Mechanism | Source | License | Kitty Feature Lane | Rationale | Integration Size |
|---|---|---|---|---|---|
| Tool-call cards (collapsible, status, result preview) | `assistant-ui/assistant-ui` | MIT | Chat execution | Best-in-class streaming tool call UX for React | Medium |
| Task inbox hierarchy with priority/status | `khoj-ai/pipali` | Apache-2.0 | Resume loop | Well-tested resume-loop UX for personal AI | Medium |
| Artifact display cards (image, doc, code, report) | `assistant-ui/assistant-ui` + `invoke-ai/InvokeAI` | MIT + Apache-2.0 | Artifacts | Shared visual model per type | Medium |
| Automation editor (schedule preview, run history) | `home-assistant/core` | Apache-2.0 | Automations | Production-hardened schedule UI | Medium |
| Memory inspection (provenance, confidence, edit/undo) | `letta-ai/letta-code` | Apache-2.0 | Memory | Mature memory-mutation UX | Small |
| Approval gates (modal, inline card) | `agent-canvas` + `assistant-ui` | MIT | Work | Pre-built approval patterns | Small |
| Integration health (capability gating, progressive disclosure) | `home-assistant/core` | Apache-2.0 | Integrations | Production-hardened health model | Medium |
| Quiz flow (feedback, progress, citations) | DeepTutor (HKUDS) | Apache-2.0 | Tutor | Proven quiz interaction patterns | Medium |
| Gallery layout (masonry, responsive, keyboard) | `invoke-ai/InvokeAI` | Apache-2.0 | Image Lab | Mature creative-tool gallery | Small |
| Image viewer (lightbox, zoom, nav) | `igordanchenko/yet-another-react-lightbox` | MIT | Image Lab | Direct npm dependency | 0 (dependency) |
| Trace comparison (scorecards, cost, latency) | `langfuse/langfuse` | MIT | Evaluation | Operator-only trace patterns | Small |
| Schedule visualization (next-run, run-now, history) | `home-assistant/core` | Apache-2.0 | Automations | Rich schedule UI | Medium |

### Study-Only Register

| Source | License | Restriction |
|---|---|---|
| `khoj-ai/khoj` | AGPL-3.0 | Copyleft — study patterns, never copy code |
| `open-webui/open-webui` | Custom + branding | Restrictive — study patterns only |
| `screenpipe/screenpipe` | Screenpipe Commercial | Proprietary — study consent/indicator patterns only |
| `Comfy-Org/ComfyUI_frontend` | GPL-3.0 | Copyleft — study workflow patterns, never copy |
| `ankitects/anki` | AGPL-3.0 | Copyleft — study spaced-repetition scheduling |
| `getzep/graphiti` | Apache-2.0 | No meaningful frontend — study data model only |

### Do-Not-Copy Register (hard stop)

- Any GPL-3.0 or AGPL-3.0 source file
- Any file from `open-webui/open-webui` (custom license)
- Any file from `screenpipe/screenpipe` (commercial license)
- Any ComfyUI source file (GPL-3.0)
- Any runtime, queue, scheduler, database, or design system from any external repo
- Any code that would introduce a second authority over tasks, runs, or artifacts

---

## Stage 6 — Kitty-Wide Experience System

The complete product-experience plan lives in `docs/plans/KITTY_PRODUCT_EXPERIENCE_V1.md`. This section summarizes the binding architectural decisions.

### 1. Global Information Architecture

**Proposed navigation (replaces current Rail):**

```
Home          — resume / needs attention / what's new
 Chat          — conversation
 Create        — Image Lab, documents, automations
 Learn         — Tutor
 Memory        — facts, corrections, knowledge
 Work          — Builder, active tasks, outputs
 Integrations  — providers, models, health (progressive disclosure)
```

**Design decisions:**
- The current Rail is insufficient (4 items for 14+ surfaces). The new navigation must provide 7 top-level items.
- On mobile: bottom tab bar, not hamburger + overlay.
- Chat input bar is always visible when chat is the active view; otherwise, a floating action for "ask Kitty."
- The "Tools" catch-all grid is eliminated. Each tool graduates to its own primary navigation item or becomes a contextual control.
- Settings and theme toggle move to a user menu (avatar/initials), not a top-level navigation item.

### 2. Resume and Attention Model

**One visible vocabulary for all work states:**

| State | All Features Use |
|---|---|
| Working | "working" spinner + current step |
| Waiting for you | "needs you" with attention indicator |
| Scheduled | "scheduled" with time |
| Paused | "paused" with pause reason |
| Failed | "failed" with error summary + retry |
| Completed | "done" with timestamp |
| Unavailable | "offline" with which part |
| Degraded | "limited" with what's missing |
| Canceled | "canceled" |

**No feature may invent its own vocabulary for these states.** `attempt`, `packet`, `lease`, `provider job ID`, `execution receipt` are backend terms that must not appear as primary user-facing labels.

### 3. Durable Work Presentation

**One reusable WorkCard component:**

```
┌─────────────────────────────────────┐
│ [icon] Chat title → Task title      │
│ Status: working (with step detail)  │
│ [progress indicator]                │
│ [attention required?]               │
│ Artifacts: [image] [doc] [report]   │
│ [retry] [resume] [cancel]           │
└─────────────────────────────────────┘
```

Every feature (chat, image gen, tutor, builder, automation) must use this same card for its work presentation. The originating conversation is always linked.

### 4. Artifact Presentation

**Shared ArtifactCard per type:**

| Type | Visual Model | Actions |
|---|---|---|
| Image | Thumbnail + prompt + dimensions | View full, Remix, Download, Delete |
| Document | Title + excerpt + source | Open, Edit, Share, Delete |
| Note | Title + excerpt | Edit, Pin, Delete |
| Report | Title + summary + generated-by | View full, Export, Delete |
| Quiz result | Score + summary | Review, Retake |
| Code output | Language + preview | Copy, Download, Open in editor |

All artifacts carry provenance (which conversation, which task, when, which model).

### 5. Capability and Provider Presentation

**Truthful capability gating:**

- Available: normal control, no indicator needed
- Partially available: subtle indicator (not a blocking banner)
- Offline: visual indicator on the specific control, not a global banner
- Missing permission: "needs permission" with one-click grant
- Unsupported action: "not available" with explanation
- Temporarily failed: retry indicator on the specific action
- Reconnecting: animated indicator on the specific provider

Provider machinery (model list, MCP servers, plugins) moves to Integrations under progressive disclosure. The runtime badge in the TopBar is reduced to a single health dot with tooltip.

### 6. Progressive Disclosure

| Always Visible | Contextual | Advanced | Operator-Only |
|---|---|---|---|
| Navigation, chat input, cat state | Model override, project scope, thread goal | Model list, engine selection, plugin toggles | Builder queue, MCP tools, terminal, traces |

### 7. Responsive Behavior

| Breakpoint | Layout | Key Behavior |
|---|---|---|
| 320-374px | Single column, bottom tab bar | Stacked cards, minimal padding, collapsible sections |
| 375-767px | Single column, bottom tab bar | Full-width content, touch-optimized controls |
| 768-1023px | Sidebar + content, optional rail | Sidebar collapsible, two-column grid for home |
| 1024px+ | Rail + sidebar + content | Full three-panel layout, multi-column grids |

Mobile must not be "desktop columns stacked vertically." On mobile:
- Home shows a compact summary with 3 cards, not all 8 sections
- Chat is full-screen with auto-hide topbar on scroll
- Feature studios use a single-column layout designed for mobile
- Bottom tab bar provides primary navigation

### 8. Accessibility

| Requirement | Implementation |
|---|---|
| Focus treatment | 3px primary-color ring with 2px offset on all interactive elements |
| Keyboard navigation | Tab order follows visual order; skip links for main content |
| Live status announcements | `aria-live="polite"` for streaming content, status changes |
| Touch targets | Minimum 44px × 44px (WCAG 2.1 level AAA) |
| Semantic labels | All interactive elements have accessible names |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` disables all animations |
| Contrast | All text ≥ 4.5:1 against background (WCAG AA) |
| Error linkage | Error messages programmatically linked to their controls |
| Dialog behavior | Focus trapped in modal; focus returns to trigger on close |

### 9. Visual Language

**Preserve:** Crayon cat, warm color palette, three-theme system, display typeface (Bricolage Grotesque), hand-drawn character.

**Establish limits on:**
- Glass: Reduce `backdrop-filter` to essential surfaces only (settings, dialogs), not every card
- Borders: Standardize to 1px (currently 1.5px in most places)
- Glow: Remove from non-interactive surfaces; keep only on active/focused elements
- Decorative texture: Paper grain reduced to 0.03 opacity; wob filter limited to cat marks and headings
- Tiny monospace text: Minimum 12px for any label; monospace reserved for code, timestamps, and technical data
- Status badges: Standardize to one badge component with shape variants (dot, pill, chip)
- Nested cards: Maximum one level of nesting (no card-in-card-in-card)
- Animation: Limit to hover/active states; no auto-playing animations on the home screen

**Content remains the visual focus.** The starfield background, paper grain, and wob filters should enhance the atmosphere without competing with content.

### 10. Product Language

| Backend Term | Product Language |
|---|---|
| attempt | "run" or "try" |
| packet | "step" |
| lease | (never shown to user) |
| provider job ID | (never shown to user) |
| execution receipt | "result" |
| tool observation | "Kitty noticed..." or contextual |
| context enrichment | (never shown to user) |
| runtime event | "update" or contextual |
| fromLiveGateway | "live" vs "cached" (in tooltip) |
| branch_leases | (never shown to user) |
| prompt_id | (never shown to user) |
| session_id | (never shown to user) |
| task_run | "task" or "run" |

---

## KX Initiative Program Summary

| Initiative | User-Visible Outcome | Key Harvested Mechanisms | License OK? | Packet Count (est.) |
|---|---|---|---|---|
| KX-01 | Resume loop + shared work presentation | Pipali task inbox, HomeAssistant lifecycle states | Yes (Apache-2.0) | 4-6 |
| KX-02 | Chat execution experience (tools, approvals, artifacts) | assistant-ui tool cards, approval gates, artifact display | Yes (MIT) | 5-7 |
| KX-03 | Work and Builder experience | agent-canvas task canvas, Pipali progress patterns | Yes (MIT, Apache-2.0) | 4-6 |
| KX-04 | Memory, knowledge, projects | Letta memory inspection, facts/provenance UI | Yes (Apache-2.0) | 4-5 |
| KX-05 | Automations + proactive Kitty | HomeAssistant automation editor, schedule visualization | Yes (Apache-2.0) | 3-5 |
| KX-06 | Image Lab studio | react-photo-album, yet-another-react-lightbox, InvokeAI gallery | Yes (MIT, Apache-2.0) | 4-6 |
| KX-07 | Tutor learning experience | DeepTutor quiz structure, Anki spacing patterns (study) | Yes (Apache-2.0) | 3-5 |
| KX-08 | Integrations, models, capabilities, health | HomeAssistant integration health, progressive disclosure | Yes (Apache-2.0) | 3-5 |
| KX-09 | Operator evaluation surfaces | LangFuse trace comparison, scorecards | Yes (MIT) | 2-4 |

**Packet dependencies:** KX-01 must ship first (shared vocabulary + components needed by all lanes). KX-02 and KX-04 can proceed in parallel after KX-01. KX-06 depends on backend Image Lab (already delivered). KX-09 is lowest priority.

---

## Experience Acceptance Gates (all visual packets)

Every visual packet must pass:
1. Unit tests (vitest)
2. Typecheck (`npm run typecheck` in kitty-chat)
3. Production build (`npm run build` in kitty-chat)
4. Browser verification at 320px, 375px, 768px, 1440px
5. Relevant browser smoke tests
6. Screenshot evidence (before + after)
7. Keyboard verification (Tab order, Enter/Space, Escape, arrows)
8. Focus verification (visible ring on all interactive elements)
9. Reduced-motion review (`prefers-reduced-motion: reduce`)
10. Truthful-state review (no invented progress, no generic errors)
11. Comparison against this approved experience plan

Every visual packet must report:
- Before screenshot
- After screenshot
- What now feels easier
- What now feels more coherent
- What code/mechanism was harvested
- License/attribution status
- Remaining friction

**Repository-wide gates:**
- No new design system
- No unrelated component library
- No second task/run/artifact authority
- No silent provider fallback
- No invented progress
- No generic error used for unrelated failure causes
- No core action rendered at <12px
- No mobile horizontal overflow
- No feature disconnected from its originating conversation
- No backend identifier as primary user-facing identity
- No permanent visual clutter for rarely used actions
- No feature-specific status vocabulary when shared lifecycle state applies
- No claim that tests alone prove the UI feels good

---

## Approval Command

```
Apply the approved KX-01 manifest. Run `./kitty builder initiative doctor --json`.
Show initiative status. Start KX-01 through the free worker/reviewer ladder.
Publish implementation PRs. Never auto-merge.
```

This gives Image Lab proper treatment while forcing Home, Chat, Builder, Memory, Projects, Automations, Tutor, Integrations, and evaluation surfaces through the same quality process.
