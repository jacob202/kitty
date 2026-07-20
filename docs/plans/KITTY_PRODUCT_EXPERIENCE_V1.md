# Kitty Product Experience v1

**Date:** 2026-07-20
**Status:** Draft for Jacob's review
**Derived from:** `docs/AUDIT_KITTY_FRONTEND_EXPERIENCE_HARVEST_2026-07-20.md`
**Authority:** This document defines the approved product-wide interaction system. All KX initiative manifests must conform to it.

---

## 1. Product Identity

Kitty is a personal AI companion. The product communicates warmth, competence, and honesty. It is not an admin dashboard, developer tool, or infrastructure cockpit. The visual language supports the interaction model; it does not compete with it.

**Core identity principles:**
- One companion, not nine panels
- Visible work, not hidden complexity
- Truthful capability, not aspirational UI
- Content-first, not decoration-first
- Mobile-native, not desktop-first with mobile fallback

---

## 2. Global Information Architecture

### 2.1 Navigation Structure

```
┌─────────────────────────────────────────────────┐
│ [Kitty mark]  Home  Chat  Create  Learn  Memory │
│               Work  Integrations    [avatar ▼]  │
├─────────────────────────────────────────────────┤
│                                                  │
│              MAIN CONTENT AREA                   │
│                                                  │
├─────────────────────────────────────────────────┤
│ [◉ live]  [model: smart]  [project: my project] │
└─────────────────────────────────────────────────┘
```

**Top-level navigation items:**

| Item | Purpose | Primary Content |
|---|---|---|
| Home | Resume loop: what happened, what needs you, what's next | Next steps, deadlines, active work, recent artifacts, builder glance |
| Chat | Conversation with Kitty | Messages, tool activity, approvals, artifacts, attachments |
| Create | Productive creation | Image Lab, documents, automations |
| Learn | Learning and tutor | Active lessons, quiz, term browser, progress |
| Memory | What Kitty knows | Facts, corrections, knowledge, search, provenance |
| Work | Builder and tasks | Initiatives, tasks, runs, outputs, review |
| Integrations | Providers, models, health | Integration status, model list, plugins, diagnostics (progressive disclosure) |

**Bottom status bar (desktop) / context bar (mobile):**
- Runtime health indicator (dot + tooltip)
- Active model (dropdown)
- Active project (dropdown)

### 2.2 Mobile Navigation

On viewports ≤ 767px:

```
┌─────────────────────────────────┐
│          CONTENT AREA           │
│                                 │
├─────────────────────────────────┤
│ 🏠  💬  ✨  📚  🧠  🔧  ⚙     │
└─────────────────────────────────┘
```

5-7 tab bottom bar with icon + short label. The current hamburger + overlay pattern (for sidebar) and desktop rail (for navigation) are replaced.

### 2.3 Theme and Settings

Theme toggle and settings move to an avatar/initials dropdown in the top-right corner. They are not top-level navigation items.

---

## 3. Resume and Attention Model

### 3.1 One State Vocabulary

Every feature that can be in a lifecycle state must use these exact labels and visual treatments:

| State | Label | Visual Treatment | When |
|---|---|---|---|
| `working` | "working" | Pulsing amber dot + current step text | Kitty is actively doing something |
| `needs_user` | "needs you" | Amber badge with count | Kitty needs approval, input, or a decision |
| `scheduled` | "scheduled" | Calendar icon + time | Work is queued for later |
| `paused` | "paused" | Gray dot + reason (if known) | Work is paused |
| `failed` | "failed" | Red dot + error summary + retry action | Work failed |
| `completed` | "done" | Green dot + timestamp | Work completed successfully |
| `unavailable` | "offline" | Red dot with tooltip | Service is unreachable |
| `degraded` | "limited" | Yellow dot with what's missing | Partial availability |
| `canceled` | "canceled" | Strikethrough text | Work was canceled |

### 3.2 Home Screen Structure

```
┌─────────────────────────────────────────────────────┐
│ Good morning, Jacob       [new chat]                │
│                                                      │
│ 👋 What needs you (2)                               │
│ ┌─────────────────────────────────────────────────┐ │
│ │ ○ needs approval — "Build the landing page"     │ │
│ │   Builder initiative · started 2h ago           │ │
│ │ ○ review — Image Lab generated 4 variants       │ │
│ │   Image Lab · completed 1h ago                  │ │
│ └─────────────────────────────────────────────────┘ │
│                                                      │
│ ⚡ Active work (1)                                   │
│ ┌─────────────────────────────────────────────────┐ │
│ │ ● working — Image generation for "sunset"       │ │
│ │   Step 2/4: denoising · ComfyUI                │ │
│ │   [cancel]                                       │ │
│ └─────────────────────────────────────────────────┘ │
│                                                      │
│ 🕐 Today                                             │
│ ┌─────────────────────────────────────────────────┐ │
│ │ ○ scheduled — Morning brief · 8:00 AM           │ │
│ │ ○ scheduled — Backup kitty data · 12:00 PM      │ │
│ └─────────────────────────────────────────────────┘ │
│                                                      │
│ ✨ Recent results                                    │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐          │
│ │ [image]   │ │ [doc]     │ │ [report]  │          │
│ │ sunset    │ │ meeting   │ │ weekly    │          │
│ │ yesterday │ │ notes     │ │ summary   │          │
│ │ view →    │ │ 2h ago    │ │ 5h ago    │          │
│ └───────────┘ └───────────┘ └───────────┘          │
└─────────────────────────────────────────────────────┘
```

### 3.3 Transition Between Home and Chat

From Home, clicking "new chat" or any chat-summary card opens Chat. From Home, clicking a "needs you" item navigates to the relevant surface (Chat for conversation continuations, Work for Builder, Create for Image Lab results).

---

## 4. Work Presentation System

### 4.1 WorkCard Component

Every feature uses this shared component:

```
WorkCard {
  id: string
  type: 'chat' | 'image' | 'tutor' | 'builder' | 'automation'
  title: string
  sourceTitle?: string          // originating conversation title
  sourceChatId?: string         // link back to conversation
  status: WorkStatus            // from the shared vocabulary
  statusDetail?: string         // "Step 2/4: denoising" or error message
  attentionRequired?: boolean   // needs user action
  progress?: number             // 0-100, optional
  artifacts?: ArtifactCard[]    // produced outputs
  actions: WorkAction[]         // retry, resume, cancel, etc.
  createdAt: Date
  updatedAt: Date
}
```

### 4.2 ArtifactCard Component

Shared across all features:

```
ArtifactCard {
  id: string
  type: 'image' | 'document' | 'note' | 'report' | 'quiz' | 'code'
  title: string
  preview?: string              // thumbnail or excerpt
  metadata?: Record<string, string>
  provenance: {
    sourceType: 'chat' | 'tutor' | 'builder' | 'image' | 'automation'
    sourceId: string
    sourceTitle?: string
    sourceChatId?: string
    model?: string
    timestamp: Date
  }
  actions: ('view' | 'download' | 'delete' | 'remix' | 'share')[]
}
```

---

## 5. Chat Execution Experience

### 5.1 Message Composition

- Composer is always visible when Chat is the active view
- Text area auto-expands to 4 lines, then scrolls
- Attachments appear as chips above the input
- Model override available via `/model` command or chip selector
- Voice input available via mic button
- Stop button visible during streaming

### 5.2 Tool Activity Presentation

Tool calls during chat are displayed as collapsible cards:

```
┌─────────────────────────────────────────────┐
│ 🔧 search web                    ● running  │
│ ┌─────────────────────────────────────────┐ │
│ │ Searching for "latest..."               │ │
│ │ Duration: 1.2s                          │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🔧 search web                    ✓ done    │
│ ┌─────────────────────────────────────────┐ │
│ │ Found 3 results                         │ │
│ │ 1. Result title...       [expand →]     │ │
│ │ 2. Result title...       [expand →]     │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 5.3 Approval Experience

When Kitty needs approval:
- An inline card appears: "Kitty wants to [action]. [details]. Approve? [yes] [no]"
- The conversation pauses until approved or declined
- After approval, the action continues inline
- After decline, the conversation resumes with the user's preference recorded

### 5.4 Error and Retry

- Failed tool calls show a red inline card with the error summary and [retry] action
- Interrupted messages show "⚠ generation stopped" with [retry] and [continue] actions
- Gateway connectivity issues show a slim persistent banner (not a blocking modal)
- Every error links to the specific control or area, never a generic toast

---

## 6. Feature Studios

### 6.1 Image Lab Studio

```
┌──────────────────────────────────────────────────────┐
│ Image Lab                           [engine: ComfyUI]│
├───────────────┬──────────────────────────────────────┤
│ Prompt        │                                      │
│ [___________] │  ┌──────┐ ┌──────┐ ┌──────┐        │
│               │  │ img  │ │ img  │ │ img  │        │
│ Style chips   │  │      │ │      │ │      │        │
│ [portrait]    │  └──────┘ └──────┘ └──────┘        │
│ [landscape]   │  ┌──────┐ ┌──────┐ ┌──────┐        │
│ [detailed]    │  │ img  │ │ img  │ │ img  │        │
│               │  │      │ │      │ │      │        │
│ [generate →]  │  └──────┘ └──────┘ └──────┘        │
│               │                                      │
│ Gallery tab   │  Recent · All · Favorites            │
│ Active gen:   │                                      │
│ ● working     │                                      │
│ Step 2/4      │                                      │
│ [cancel]      │                                      │
└───────────────┴──────────────────────────────────────┘
```

Key decisions:
- Left panel: composition (prompt, style chips, engine selector)
- Right panel: gallery (masonry layout using react-photo-album)
- Active generation appears as a WorkCard at the top of the gallery
- Click on image opens lightbox (yet-another-react-lightbox)
- Lightbox supports keyboard navigation, zoom, download, and "remix" (pre-fill prompt)
- Remix fills the composition panel with the original prompt + style chips

### 6.2 Tutor Studio

```
┌──────────────────────────────────────────────────────┐
│ Tutor                                                │
├─────────────────────────┬────────────────────────────┤
│ Active lessons          │ Continue "Spanish basics"  │
│ ┌─────────────────────┐ │                            │
│ │ Spanish basics      │ │ Question 3/10              │
│ │ 40% complete        │ │                            │
│ │ last: 2 days ago    │ │ ¿Cómo se dice "apple"?     │
│ │ [continue]          │ │                            │
│ └─────────────────────┘ │ ○ la manzana               │
│ ┌─────────────────────┐ │ ○ el libro                 │
│ │ Python for data     │ │ ○ la mesa                  │
│ │ 15% complete        │ │                            │
│ │ last: 1 week ago    │ │ [check answer]             │
│ │ [continue]          │ │                            │
│ └─────────────────────┘ │                            │
│ [new lesson]            │ Progress: ███░░░░░░ 30%    │
│                         │                            │
│ Browse terms            │                            │
│ ┌─────────────────────┐ │                            │
│ │ [search terms...]   │ │                            │
│ │ manzana · apple     │ │                            │
│ │ libro · book        │ │                            │
│ └─────────────────────┘ │                            │
└─────────────────────────┴────────────────────────────┘
```

Key decisions:
- Tutor is NOT another chat with a quiz appended
- Two-panel layout: lesson browser (left) + active quiz/content (right)
- Quiz feedback is immediate and explanatory
- Progress is visible per-lesson and overall
- "Continue" resumes exactly where the user left off

### 6.3 Memory Studio

```
┌──────────────────────────────────────────────────────┐
│ Memory                                               │
├──────────────────────────────────────────────────────┤
│ [search what Kitty knows...]                         │
│                                                      │
│ Recent facts                                         │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ✓ confident · learned 2h ago                     │ │
│ │ "Jacob prefers dark mode in all apps"            │ │
│ │ source: chat "app preferences"                   │ │
│ │ [edit] [✕ forget]                                │ │
│ └──────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ○ possible · learned yesterday                   │ │
│ │ "Jacob is working on the landing page redesign"  │ │
│ │ source: chat "project update"                    │ │
│ │ [confirm] [✕ forget]                             │ │
│ └──────────────────────────────────────────────────┘ │
│                                                      │
│ Knowledge bases                                      │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│ │ work docs│ │ reference│ │ learning │              │
│ │ 124 docs │ │ 47 docs  │ │ 12 docs  │              │
│ └──────────┘ └──────────┘ └──────────┘              │
│                                                      │
│ Conversations [view all →]                           │
└──────────────────────────────────────────────────────┘
```

Key decisions:
- Facts are presented with provenance: which conversation, when, confidence level
- "True now" vs "was true then" distinction
- Edit and forget actions are immediate with undo (5s grace period already implemented)
- Knowledge surfacing is a supporting view, not the primary memory interface

### 6.4 Work / Builder Studio

```
┌──────────────────────────────────────────────────────┐
│ Work                                                  │
├──────────────────────────────────────────────────────┤
│ Initiatives                     Queue                 │
│ ┌────────────────────────────┐  3 queued             │
│ │ ○ builder-test-hardening  │  0 running             │
│ │   Test hardening · active │  12 done               │
│ │   2/3 packets · running   │                        │
│ └────────────────────────────┘                        │
│ ┌────────────────────────────┐                        │
│ │ ○ packet-027-builder      │                        │
│ │   Builder recovery · actv │                        │
│ │   0/5 packets · paused    │                        │
│ └────────────────────────────┘                        │
│                                                       │
│ Recent runs                                          │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ○ done · builder-test-hardening · packet 2/3     │ │
│ │   Merge PR #214 · 2h ago                         │ │
│ │   Artifacts: [PR #214] [test results]            │ │
│ └──────────────────────────────────────────────────┘ │
│                                                       │
│ [operator detail →]  (progressive disclosure)         │
└──────────────────────────────────────────────────────┘
```

Key decisions:
- Primary view shows initiatives + recent runs (user-facing summary)
- Queue, attempts, leases, and raw status are under progressive disclosure
- Each run links to its conversation and artifacts
- Builder is not a terminal view — it's a work dashboard

### 6.5 Automations Studio

```
┌──────────────────────────────────────────────────────┐
│ Automations                                          │
├──────────────────────────────────────────────────────┤
│ Active                                               │
│ ┌──────────────────────────────────────────────────┐ │
│ │ morning brief  ·  scheduled · 8:00 AM daily      │ │
│ │ last ran: today 7:58 AM · ✓ done                 │ │
│ │ [pause] [run now] [edit]                         │ │
│ └──────────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────┐ │
│ │ kitty backups  ·  scheduled · 12:00 PM daily     │ │
│ │ last ran: yesterday · ✓ done                     │ │
│ │ [pause] [run now] [edit]                         │ │
│ └──────────────────────────────────────────────────┘ │
│                                                       │
│ Run history                                          │
│ ┌──────────────────────────────────────────────────┐ │
│ │ morning brief · today 7:58 AM · ✓ done           │ │
│ │ Artifacts: [brief] [conversation]                │ │
│ │ morning brief · yesterday 7:59 AM · ✗ failed    │ │
│ │ Error: gateway timeout · [retry]                 │ │
│ └──────────────────────────────────────────────────┘ │
│                                                       │
│ [new automation →]                                    │
└──────────────────────────────────────────────────────┘
```

Key decisions:
- Automation creation uses natural language ("Remind me to... every morning at 8")
- Schedule preview shows in local time
- Each automation's run history links to its results and conversations
- Pause is distinct from cancel

### 6.6 Integrations and Health

```
┌──────────────────────────────────────────────────────┐
│ Integrations                                         │
├──────────────────────────────────────────────────────┤
│ Model routing                                        │
│ ● live · LiteLLM via gateway                         │
│ Active: smart (claude-sonnet-4-20250514)  [change →] │
│ 5 models available       [view all →]                │
│                                                       │
│ Image engines                                        │
│ ● live · ComfyUI          [check again]              │
│ ○ offline · Draw Things   [check again]              │
│                                                       │
│ Plugins                                              │
│ ✓ enabled · memory · search · calendar               │
│ ✗ disabled · weather · news                          │
│                                     [manage →]        │
│                                                       │
│ Diagnostics                     [show details →]      │
└──────────────────────────────────────────────────────┘
```

Key decisions:
- Progressive disclosure: default view shows health summary only
- Individual provider health is visible but does not dominate
- Reconnect, retry, and check-again are one-click actions
- Advanced diagnostics (raw status, trace, terminal) are operator-only under progressive disclosure

---

## 7. Responsive Behavior Matrix

| Feature | 320-374px | 375-767px | 768-1023px | 1024px+ |
|---|---|---|---|---|
| Home | Single column, 3 top cards, rest collapsed | Single column, all sections, vertical | Two columns, priority left | Two columns, priority left |
| Chat | Full screen, auto-hide topbar, compact composer | Full screen, compact composer | Sidebar + chat, collapsible sidebar | Rail + sidebar + chat |
| Image Lab | Composition full-width above gallery | Composition above, gallery below | Two-panel (left: composition, right: gallery) | Two-panel |
| Tutor | Single column, stacked | Single column, stacked | Two-panel (lesson browser + quiz) | Two-panel |
| Memory | Single column, stacked | Single column, stacked | Single column, wider | Single column, wider |
| Work | Single column, stacked | Single column, stacked | Two columns (initiatives + runs) | Two columns |
| Automations | Single column, stacked | Single column, stacked | Single column, wider | Single column, wider |
| Integrations | Single column, sections | Single column, sections | Two columns | Two columns |
| Navigation | Bottom tab bar (5 tabs) | Bottom tab bar (5-7 tabs) | Collapsible sidebar + rail | Rail + sidebar |
| Bottom status | Hidden | Hidden | Visible | Visible |

---

## 8. Accessibility System

### 8.1 Focus Treatment

```css
*:focus-visible {
  outline: 3px solid var(--primary);
  outline-offset: 2px;
  border-radius: 4px;
}
```

### 8.2 Keyboard Navigation

- Tab order follows visual DOM order
- Skip-to-content link at top of page
- Escape closes dialogs, dropdowns, and returns focus
- Enter/Space activates buttons and links
- Arrow keys navigate within galleries, lists, and menus
- Cmd+K always opens command palette
- Cmd+Enter sends message in chat

### 8.3 Live Regions

```html
<div aria-live="polite" aria-atomic="true">
  <!-- Streaming content, status changes -->
</div>
<div aria-live="assertive">
  <!-- Errors, approvals needed -->
</div>
```

### 8.4 Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 8.5 Touch Targets

All interactive elements: minimum 44px × 44px (WCAG 2.1 AAA).

### 8.6 Semantic Structure

- One `<h1>` per view (the view's primary heading)
- Landmark regions: `<nav>`, `<main>`, `<aside>`, `<header>`, `<footer>`
- `aria-label` on all interactive elements without visible text
- `aria-describedby` to link error messages to their controls
- `role="alert"` or `role="status"` on all dynamic content regions

---

## 9. Component Architecture

### 9.1 Shared Component Library

All shared components live in `gateway/kitty-chat/src/components/shared/`:

```
shared/
  WorkCard.tsx           Durable work presentation
  ArtifactCard.tsx        Artifact display by type
  StatusBadge.tsx         One badge for all states
  SectionCard.tsx         Layout wrapper with header
  EmptyState.tsx          One empty state component
  ErrorBanner.tsx         One error presentation
  LoadingSkeleton.tsx     One loading pattern
  CapabilityGate.tsx      Truthful capability display
  ProgressiveDisclosure.tsx  Show/hide advanced content
  Composer.tsx            Chat input (extracted from InputBar)
  AttachmentChip.tsx      File attachment display
  ToolCallCard.tsx        Collapsible tool call display
  ApprovalGate.tsx        Approval request UI
  Gallery.tsx             Image gallery (react-photo-album wrapper)
  Lightbox.tsx            Image viewer (yet-another-react-lightbox wrapper)
  BottomNav.tsx           Mobile bottom tab bar
  ThemeToggle.tsx         Three-theme cycle
  UserMenu.tsx            Avatar + settings dropdown
  HealthIndicator.tsx     Runtime health dot + tooltip
```

### 9.2 Feature Studio Structure

Each feature studio lives in `gateway/kitty-chat/src/studios/`:

```
studios/
  image-lab/
    ImageLabStudio.tsx    Main layout
    CompositionPanel.tsx   Prompt + style chips
    GalleryPanel.tsx      Image gallery
    GenerationCard.tsx    Active generation status
  tutor/
    TutorStudio.tsx       Main layout
    LessonBrowser.tsx     Lesson list + progress
    QuizPanel.tsx         Active quiz
    TermBrowser.tsx       Term search + browse
  memory/
    MemoryStudio.tsx      Main layout
    FactList.tsx          Recent facts with provenance
    KnowledgeBrowser.tsx  Knowledge base view
    ConversationList.tsx  Searchable conversations
  work/
    WorkStudio.tsx        Main layout
    InitiativeList.tsx    Active initiatives
    RunHistory.tsx        Recent + historical runs
    OperatorDetail.tsx    Queue/attempts/leases (progressive disclosure)
  automations/
    AutomationStudio.tsx  Main layout
    AutomationList.tsx    Active automations
    AutomationEditor.tsx  Create/edit automation
    RunHistory.tsx        Automation run history
  integrations/
    IntegrationStudio.tsx Main layout
    ModelRouting.tsx      Model list + selection
    EngineHealth.tsx      Image engine status
    PluginManager.tsx     Plugin enable/disable
    Diagnostics.tsx       Advanced (progressive disclosure)
```

### 9.3 Extracted from Current page.tsx

The 1,387-line `page.tsx` must be decomposed:

| Extracted To | Content |
|---|---|
| `app/providers.tsx` | Already exists — React Query + theme |
| `app/layout.tsx` | Already exists — fonts + metadata |
| `app/page.tsx` | Reduced to: navigation state + view router + shared providers |
| `features/chat/ChatView.tsx` | Chat messages, ThreadGoal, SignalFeed, InputBar |
| `features/home/HomeView.tsx` | Next steps, deadlines, builder glance, state, actions |
| `lib/navigation.tsx` | Navigation state machine, view routing |
| `lib/work-state.ts` | Shared work lifecycle state and transitions |
| `lib/status-vocabulary.ts` | Shared status labels and visual treatments |

---

## 10. Visual Language Refinements

### 10.1 Typography Scale (revised)

| Token | Size | Use |
|---|---|---|
| `--t-hero` | 4rem | Landing/greeting only |
| `--t-display` | 2.5rem | View headings |
| `--t-h1` | 1.75rem | Section headings |
| `--t-h2` | 1.25rem | Card titles |
| `--t-body` | 0.9375rem (15px) | Body text |
| `--t-small` | 0.8125rem (13px) | Secondary text |
| `--t-tiny` | 0.75rem (12px) | Minimum label size |

**No label, chip, or interactive text below 12px.** Monospace reserved for code, timestamps, and technical metadata only.

### 10.2 Spacing Scale (unchanged)

Keep the existing 8px-based system (`--s-1` through `--s-8`).

### 10.3 Border Radius (refined)

| Token | Size | Use |
|---|---|---|
| `--r-surface` | 12px | Cards, panels |
| `--r-control` | 8px | Buttons, inputs |
| `--r-chip` | 999px | Tags, chips |
| `--r-tag` | 4px | Code tags |

### 10.4 Decorative Treatment Limits

- Glass effect (`backdrop-filter: blur`): only on dialogs, sheets, and the settings dropdown
- Starfield background: cosmic theme only, reduced star count (from 10+ to 3 main clusters)
- Paper grain: opacity reduced to 0.03 (day) / 0.025 (night)
- Wob filter: applied to cat marks, section-heading underline paths, and the logo only
- Shadows: standardize to one shadow token per theme (currently 2-3 different shadows)

### 10.5 Status Badge System (unified)

```
StatusBadge {
  state: 'working' | 'needs_user' | 'scheduled' | 'paused' |
         'failed' | 'completed' | 'unavailable' | 'degraded' | 'canceled'
  variant: 'dot' | 'pill' | 'chip'
  animated?: boolean  // pulse for 'working'
  label?: string      // optional text override
  compact?: boolean   // dot-only for tight spaces
}
```

---

## 11. Truthful State Rules

1. **No invented progress.** If progress cannot be determined, show the state without a percentage.
2. **No generic errors.** Every error must include what failed and a specific recovery action.
3. **No silent fallback.** When a provider is unreachable, show it as offline — do not silently switch to a fallback.
4. **No backend identifiers in user-facing text.** `prompt_id`, `session_id`, `lease_ts`, `branch_leases` must never appear in the UI.
5. **No feature-specific state labels.** If work is "paused," it's "paused" everywhere — not "suspended" in Builder and "paused" in Automations.
6. **No permanent visual clutter.** Rarely used actions must live behind progressive disclosure.
7. **No feature disconnected from its conversation.** Every artifact, task, and result must link back to the conversation that produced it.
8. **No core action below 12px.** Primary controls must be at least 14px (body text size).
9. **No mobile horizontal overflow.** All views must render without horizontal scroll at 320px.
10. **No test-only approval for subjective quality.** Screenshots, interaction demos, and before/after comparison are required.

---

## 12. Implementation Order

1. **KX-01** (Resume loop + shared work presentation) — must ship first. Establishes shared vocabulary, WorkCard, ArtifactCard, StatusBadge, new navigation structure, and the Home view.
2. **KX-02** (Chat execution experience) — can start after KX-01's shared components.
3. **KX-04** (Memory, knowledge, projects) — can start after KX-01.
4. **KX-06** (Image Lab studio) — depends on KX-01 + KX-02 for shared components + backend Image Lab (delivered).
5. **KX-07** (Tutor learning experience) — depends on KX-01 + KX-04 for shared memory components.
6. **KX-03** (Work and Builder experience) — depends on KX-01.
7. **KX-05** (Automations) — depends on KX-01 + KX-03.
8. **KX-08** (Integrations, models, health) — can start after KX-01.
9. **KX-09** (Operator evaluation) — lowest priority.

---

*This document is the approved reference for all KX frontend initiatives. No visual change may ship without comparison against this plan.*
