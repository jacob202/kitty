# Kitty Chat UI Redesign — Design Spec
**Date:** 2026-05-21  
**Status:** Approved for implementation  
**Branch:** `feat/kitty-ui-polish` (worktree at `.worktrees/ui-polish`)  
**Reference mockup:** `gateway/kitty-chat/content/full-mockup-v8.html` + brainstorm session

---

## Vision

Replace the current generic dark chat app with a **personal command center** — a dashboard-first interface designed around Jacob's actual brain patterns: rumination loops, decision paralysis, task avoidance. Chat is a utility (docked terminal strip), not the primary surface. The homepage is so useful it becomes the default tab.

Inspired by: v6/v7/v8 mockup series + reference dashboard image. Not a ChatGPT clone.

---

## Layout — 5-Zone Shell

```
┌─────────────────────────────────────────────────────────────────┐
│ TOPBAR: logo · tabs (Chats/Journal/Knowledge/Tasks) · BLUNT ▼  │  40px
├──┬────────────────────────────┬────────────────────┬────────────┤
│  │                            │                    │            │
│R │  SESSION SIDEBAR (220px)   │   CENTER (flex)    │  RIGHT     │
│A │                            │                    │  PANEL     │
│I │  • session list            │   Dashboard home:  │  (220px)   │
│L │  • + new chat              │   - greeting       │            │
│  │  • grouped by today/       │   - brief strip    │  • Kitty   │
│4 │    yesterday/projects      │   - compass        │  • sched   │
│4 │                            │   - loop watch     │  • overdue │
│p │                            │   - prompt toolkit │  • system  │
│x │                            │   - insight feed   │            │
├──┴────────────────────────────┴────────────────────┴────────────┤
│ TERMINAL STRIP (collapsible — 130px default, full-screen when  │
│ expanded): boot log · [KTY]/[USR] messages · $ input bar       │
└─────────────────────────────────────────────────────────────────┘
```

**Sidebar collapse:** clicking the rail icon collapses the session sidebar to icon-only (44px). State persisted in `localStorage`.

**Terminal expand:** drag handle or `⤢` button expands terminal to full viewport height, replacing the dashboard. Chat view is the existing message components. `Esc` collapses back.

---

## Design Tokens

```css
/* Backgrounds */
--bg-base:     #0f0f14;   /* main canvas — warm dark, not blue */
--bg-surface:  #131318;   /* cards, sidebar */
--bg-elevated: #1a1a22;   /* hover states, dropdowns */

/* Borders */
--border:      #222230;
--border-dim:  #1a1a22;

/* Brand */
--primary:     #e07a5f;   /* orange — actions, accents, overdue */
--primary-dim: #e07a5f22;
--teal:        #4ecca3;   /* active/OK states, system health */
--teal-dim:    #4ecca322;
--danger:      #e74c3c;   /* overdue, errors */

/* Text */
--text-1:      #f0f0f0;   /* headings, primary content */
--text-2:      #aaaaaa;   /* secondary content */
--text-3:      #666666;   /* metadata, timestamps */
--text-4:      #444444;   /* muted, disabled */

/* Fonts */
--font-ui:     -apple-system, 'Inter', sans-serif;
--font-mono:   'SF Mono', 'Fira Code', 'Consolas', monospace;
```

---

## Components

### 1. `TopBar`
- Left: kitty emoji logo (🐱) + nav tabs: **Chats** `(n)` · Journal · Knowledge · **Tasks** `(n)`
- Active tab has `--primary` underline
- Right: `● KITTY ACTIVE` teal status + `GENTLE | BALANCED | **BLUNT** | AUTO` mode pill group
- Mode selection calls `PATCH /mood` (existing endpoint); current mode stored in component state + `localStorage`
- Height: 40px, sticky, `--bg-surface` background

### 2. `SessionSidebar`
- Header: "CHATS" label + "+ new" orange button
- Sessions grouped: TODAY / YESTERDAY / LAST 825R / PROJECTS
- Each item: name, metadata line (time ago or status), optional badge (`live`, `4d`, color dot)
- Active session: `--primary` left border + `--bg-elevated` background
- Collapsible via icon rail click — animates to 0px width, rail icons remain
- Width: 220px expanded, 0px collapsed (rail stays at 44px always)

### 3. `DashboardHome` (center — default view)
Shown when terminal is collapsed. Contains:

#### 3a. Greeting row
- Kitty avatar tile (44px, `--primary-dim` background, 🐱)
- `morning/afternoon/evening, jacob :3` — time-of-day aware
- Subtitle: `Thursday, May 21 · gateway nominal · N things need attention`

#### 3b. `BriefStrip` — 4 cards, horizontal grid
Cards: **WEATHER** · **NEXT UP** · **OVERDUE** · **FOCUS**  
Data source: `GET /brief` (existing, cached).  
Each card: 9px label, 15px bold value (colored by type), 11px sub-line.  
Color coding: orange = upcoming action, red = overdue, teal = OK/active.

#### 3c. `TodayCompass` — full width, above 2-col grid
- Single priority action with checkbox (visual only — no backend needed yet)
- Label + sub-line (`4 days overdue · Kitty can draft it now`)
- Kitty nudge line below: italic, pulled from brief or hardcoded heuristic
- Data: top item from `brief.nextUp` or `brief.overdue`
- No backend changes needed — derives from `/brief` response

#### 3d. `LoopWatch` — right half of 2-col grid
- **Phase 1 (ship):** Static/stubbed — shows 2 placeholder loops with "watching for patterns..." state until real data exists
- **Phase 2 (later):** Backend endpoint `GET /loops` that queries memory graph for repeated query patterns
- Each loop item: name, count badge, last conclusion (mono font), "→ decide now" action chip
- DO NOT block shipping on Phase 2

#### 3e. `PromptToolkit` — left half of 2-col grid
- 6 chips: ⚡ I'm stuck · 🛒 Buying something · 🎯 Force a decision · 🪞 Call me out · 🧠 Brain dump · 📊 Triage my tasks
- Each chip: clicks open terminal strip expanded + pre-fills the prompt text
- Chips are hardcoded strings (not fetched) — Jacob edits them directly in the component
- Future: make chips configurable via a settings panel

#### 3f. `InsightFeed` — right half of 2-col grid (below LoopWatch)
- **Phase 1 (ship):** Last 2 insights from `GET /brief` response's `insight` field (if present), else static placeholder
- Each insight: italic text + "→ What makes you say that?" action (pre-fills terminal)
- Honest, specific — not affirmations. Second insight can be orange if it's a pattern/avoidance flag

### 4. `RightPanel` — 220px fixed
Sections (each with `--border` separator):

| Section | Data source |
|---|---|
| **KITTY** status | `GET /mood` (existing, polls every 30s) |
| **SCHEDULE** | `brief.schedule` from `/brief` |
| **OVERDUE** | `brief.overdue` from `/brief` |
| **SYSTEM** | gateway ping + model name from existing health check |

No new endpoints needed.

### 5. `TerminalStrip`
- Default: 130px — shows last 3 log lines + input bar
- Expanded: full viewport height — shows full chat history (existing `ChatMessage` components)
- Drag handle at top edge for resize
- `⤢` button top-right for instant full expand; `✕` to collapse back
- Input bar: `$` sigil · placeholder `Awaiting command or query...` · `/context · N` pill · 📎 attach · 🎤 voice · `send ↑` orange button
- Log line format: `[HH:MM:SS]` `[SYS]`/`[KTY]`/`[USR]` message — monospace
- `[KTY]` lines in `--text-1`; `[SYS]` in `--teal`; `[USR]` in `--text-3`
- Boot sequence on load: pull from actual gateway health check response

---

## What Already Exists (don't rebuild)

| Thing | Location |
|---|---|
| `streamChat()` | `src/lib/openwebui.ts` |
| `fetchGatewayBrief()` | `src/lib/gateway.ts` |
| `fetchGatewayModels()` | `src/lib/gateway.ts` |
| `ChatMessage` component | `src/components/ChatMessage.tsx` |
| `InputBar` component | `src/components/InputBar.tsx` (adapt for terminal) |
| Mood/buddy polling | `TopBar.tsx` (extract the fetch logic) |

---

## What's New (must build)

| Component | Notes |
|---|---|
| `DashboardHome.tsx` | New — the center dashboard view |
| `BriefStrip.tsx` | Extract from existing BriefPanel |
| `TodayCompass.tsx` | New — derives from `/brief` |
| `LoopWatch.tsx` | New — Phase 1 is stubbed |
| `PromptToolkit.tsx` | New — static chips |
| `InsightFeed.tsx` | New — Phase 1 reads from `/brief` |
| `TerminalStrip.tsx` | New — wraps existing chat + new chrome |
| Sidebar collapse logic | Extend `SessionSidebar.tsx` |
| `globals.css` token update | Warm the dark, replace cool blue |

---

## Explicit Non-Goals (this spec)

- Loop Watch backend (`GET /loops`) — Phase 2
- Insight generation endpoint — Phase 2  
- Calendar integration for schedule — Phase 2
- Mobile/responsive layout — Phase 2
- Journal, Knowledge, Tasks tab views — Phase 2 (tabs exist, views are empty stubs)
- Settings panel for prompt chips — Phase 2

---

## Acceptance Criteria

- [ ] App loads to dashboard home (not a blank chat)
- [ ] Brief strip shows live data from `/brief` (or graceful offline fallback)
- [ ] Kitty status card polls `/mood` every 30s
- [ ] Mode selector (GENTLE/BALANCED/BLUNT/AUTO) persists across refresh
- [ ] Terminal strip: collapsed by default, expands to full chat on click/drag
- [ ] Session sidebar collapses to icon rail
- [ ] Prompt chips open terminal + pre-fill text
- [ ] Background is warm dark (#0f0f14), not cool blue
- [ ] TypeScript clean (`tsc --noEmit`)
- [ ] `next build` passes
- [ ] All existing Vitest tests pass
