# Open WebUI Extension Backlog — Kitty's Operating System

**Date:** 2026-08-05
**Authority:** Product design. Implements Constitution v1, ADR 0027 (Open WebUI shell boundary), ADR 0028 (commodity precedence).
**Status:** Extension inventory — no implementation. Ranked by delight-per-line-of-code.

Open WebUI is the visual surface and interaction shell. Kitty Gateway is the intelligence
layer, policy engine, and memory. Builder is the execution coordinator. LiteLLM is the
provider abstraction.

Every extension below lives inside Open WebUI's stock extension model:
**Event Functions, Filters, Pipes, Actions, Tools, MCP, Rich UI**.
None fork or modify Open WebUI. All intelligence remains Gateway-owned.

---

## Ranking rule

Delight-per-line-of-code means: *how much would Jacob grin ÷ how much code does it take?*
Code estimates include both the Open WebUI extension handler and any Gateway endpoint
it needs. Extensions that Gateway already has an endpoint for rank higher.
Extensions that need new Gateway intelligence rank lower.

---

## S-Tier — Open Every Morning

These are the homepage. The first thing Jacob sees. The reason to launch the app.

### 1. One Thing

**Rank:** #1 of 38. This is the homepage.

**Problem:** Jacob opens Kitty and sees a chat box. No direction. No continuity.
He has to remember what he was doing, then type a question, then parse the response,
then decide what to do. Every morning is blank-page archaeology.

**User experience:**
```
Kitty Chat opens → First screen is not an empty chat.

┌─────────────────────────────────────────────┐
│  Good morning, Jacob.                        │
│                                              │
│  ┌───────────────────────────────────────┐   │
│  │                                       │   │
│  │   Follow up on Acme Corp application   │   │
│  │   Sent resume July 28 · no reply yet   │   │
│  │   Draft a follow-up email?             │   │
│  │                                       │   │
│  │   [Let's do it]  [Not now]  [Skip]    │   │
│  │                                       │   │
│  └───────────────────────────────────────┘   │
│                                              │
│  Also: Builder finished test fix overnight.  │
│  [See what changed]                          │
└─────────────────────────────────────────────┘

One card. One action. One decision. No menus.
```

**Implementation type:** Event Function (`on_chat_start`) + Rich UI card
**Estimated complexity:** ~60 lines (Event Function queries Gateway `/state/next`, renders Rich UI card)
**Dependencies:** Gateway endpoint `GET /state/next` (already conceptually designed in product architecture as the Resume projection)
**Kitty or Open WebUI:** Open WebUI Event Function renders the card. Gateway owns the next-action decision.
**Why it's #1:** Currently Jacob opens Kitty to a blank chat. This replaces that with the single most valuable byte he'll see all day. The existing Gateway next-step query already knows what project is active, what's due, what's pending. The Event Function is just a thin query + Rich UI card renderer. 60 lines, maximum delight.

---

### 2. Morning Briefing

**Rank:** #2 of 38.

**Problem:** Jacob doesn't know what happened overnight or while he was away. Builder might have finished work. Signals might have fired. Deadlines might have changed. The information exists in Gateway but has no morning surface.

**User experience:**
```
First chat of the day, automatically injected into system prompt:

"Here's what happened since yesterday at 10:42 PM:

• Builder completed: 'Fix test_openwebui_local.py' (1 file, 3 tests passed,
  independent review approved, merged to main)
• Web monitor: 'Rivian R2 news' — 2 new articles matched
• 3 captures from phone are waiting to be reviewed
• Your Acme Corp follow-up deadline is Friday (2 days)
• Benefits paperwork: W-2 verification form is 4 days past deadline

Life-first next: Follow up on Acme Corp application
Code next: Builder is idle — ready for work"

Kitty then asks: "Want to start with the Acme Corp follow-up?"
```

**Implementation type:** Event Function (`on_chat_start`, first-of-day detection) + system prompt injection
**Estimated complexity:** ~50 lines (detects first chat of day, queries Gateway `/state/brief`, injects into system prompt)
**Dependencies:** Gateway endpoint `GET /state/brief` (product architecture already defines this projection)
**Kitty or Open WebUI:** Open WebUI Event Function. Gateway owns the brief narrative. The Event Function is chronology detection + prompt injection.
**Edge case:** If no activity since last visit: "Welcome back. Nothing material changed — last activity was yesterday at 10:42 PM. Your Acme Corp follow-up is still due Friday. Want to pick up where you left off?"

---

### 3. Resume Loop

**Rank:** #3 of 38.

**Problem:** Jacob switches context constantly — job search, coding, life admin, learning.
When he returns to a project, he has to reconstruct where he was, what was done, and what's next.
Chat history helps, but archaeology is expensive.

**User experience:**
```
Jacob: "What were we doing on the job search project?"

Kitty responds, but before the response, a Rich UI card appears:

┌──────────────────────────────────────────────┐
│  📋 Resume: Job Search                        │
│                                               │
│  Last active: Yesterday 3:15 PM               │
│  Last action: Applied to TechCorp (sent       │
│  resume + cover letter via LinkedIn)           │
│                                               │
│  Open items:                                   │
│  • Acme Corp follow-up — no reply in 6 days   │
│  • Update portfolio site with recent projects │
│  • Research: 3 companies saved for outreach   │
│                                               │
│  [Continue where you left off]                │
│  [Show full project status]                   │
│  [Change active project]                      │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_resume_project`) + Rich UI card in response
**Estimated complexity:** ~80 lines (Tool definition + Rich UI card renderer; Gateway already has resume projection)
**Dependencies:** Gateway endpoint `GET /state/resume?project=X` (product architecture defines this)
**Kitty or Open WebUI:** Tool registered in Gateway, invoked by model, rendered as Rich UI card in shell. Gateway owns the resume logic; Open WebUI owns the card presentation.
**Why it's #3:** The building block of continuity. Combined with #1 (One Thing) and #4 (Activity River), resume becomes ambient — Jacob doesn't ask for it, it just IS the experience.

---

### 4. Activity River

**Rank:** #4 of 38.

**Problem:** Kitty does things — Builder executes, captures arrive, memories are formed, signals fire.
None of it is visible as a timeline. Jacob has to dig through chat history or run CLI commands to
know what his AI companion actually did.

**User experience:**
```
A dedicated chat conversation (or a sidebar panel, or a Rich UI widget):

┌──────────────────────────────────────────────┐
│  Activity                                     │
│  ────────────────────────────────────────     │
│                                               │
│  Today                                        │
│                                               │
│  09:42  Builder completed "Fix PYTHONPATH"    │
│         ✓ 1 file · 8 lines · all tests pass   │
│         ✓ Independent review: approved        │
│         ✓ Merged to main                      │
│                                               │
│  08:15  Wake-up: 3 captures from phone        │
│         • "Book dentist appointment"          │
│         • "Research insurance marketplace"    │
│         • "Remind me to call mom"             │
│                                               │
│  Yesterday                                    │
│                                               │
│  22:10  Memory: Kitty remembered 4 facts      │
│         from your coding session              │
│                                               │
│  16:30  Research agent finished:               │
│         "Rivian R2 price comparison"          │
│         • 5 sources · 2 cited facts            │
│                                               │
│  15:15  Applied to TechCorp (job search)      │
│         • Resume sent · LinkedIn application  │
│                                               │
│  [Load earlier]                               │
└──────────────────────────────────────────────┘
```

**Implementation type:** Rich UI widget rendered in a dedicated "Activity" conversation, populated by a Tool (`kitty_get_activity`) that queries Gateway activity events
**Estimated complexity:** ~120 lines (Tool + Rich UI card with polling; Gateway already has activity events)
**Dependencies:** Gateway endpoint `GET /activity?since=<cursor>&project=<id>` (activity events exist in product architecture)
**Kitty or Open WebUI:** Open WebUI Rich UI card + polling. Gateway owns the activity event store and cursor semantics.
**Edge case:** No activity: "Nothing yet today. Builder is idle. No captures pending. Last activity was yesterday at 10:42 PM." Never show an empty timeline — show the honest state of nothing.

---

### 5. Builder Mission Center

**Rank:** #5 of 38.

**Problem:** Builder is the most powerful thing Kitty does — autonomous code execution with
isolated worktrees, independent review, and merge capability. But Jacob can't see it working
without opening a terminal and running `./kitty builder` CLI commands. Builder activity is invisible
during daily use.

**User experience:**
```
A dedicated chat or Rich UI card that shows live Builder state:

┌──────────────────────────────────────────────┐
│  Builder                                      │
│  ────────────────────────────────────────     │
│                                               │
│  ⬤ Active                                     │
│  ┌─────────────────────────────────────────┐  │
│  │ Fix test_openwebui_local.py              │  │
│  │ Packet: ktf-004-py-test-fix              │  │
│  │ Worker: opencode (deepseek-v4-pro)       │  │
│  │ Worktree: /tmp/kitty-builder-ktf004      │  │
│  │ Running: 4m 23s                          │  │
│  │ [View progress]                          │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ◐ Queued (1)                                 │
│  ┌─────────────────────────────────────────┐  │
│  │ Add streaming smoke test                  │  │
│  │ Packet: ktf-005-stream-smoke              │  │
│  │ Waiting for worker availability           │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ✓ Completed today (1)                        │
│  ┌─────────────────────────────────────────┐  │
│  │ Fix PYTHONPATH regression                 │  │
│  │ Merged to main · 09:42 AM                 │  │
│  │ [See diff]  [See review]  [See cost]     │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ✗ Failed (1)                                 │
│  ┌─────────────────────────────────────────┐  │
│  │ Consolidate storage layer                 │  │
│  │ Provider exhaustion · retries exhausted   │  │
│  │ [Retry]  [Cancel]  [Investigate]         │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  [Command Builder...]                         │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_builder_status`) + Rich UI card with configurable auto-refresh
**Estimated complexity:** ~180 lines (Tool + Rich UI card + SSE polling; Gateway `builder_status.py` already exists as bounded read-only projection)
**Dependencies:** Gateway `builder_status.py` (already implemented), Gateway SSE endpoint for live updates (not yet built, but product architecture defines revisioned patches over SSE)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway's `builder_status.py` is the bounded read-only projection. Builder owns all execution state.
**Why it's #5:** This is the bridge between "Kitty is a chat app" and "Kitty is an AI operating system." Seeing Builder work — watching it lease workers, execute packets, pass review, and merge — makes Kitty feel alive. The data already exists in `builder_status.py`.

---

### 6. Capture Inbox Widget

**Rank:** #6 of 38.

**Problem:** Jacob throws things at Kitty constantly — voice memos from phone, quick captures from
Raycast, ideas mid-conversation. They land in the Quick Capture inbox but have no daily surface.
They pile up, unseen, unprocessed.

**User experience:**
```
A rich UI widget embedded in the daily chat or as a conversation card:

┌──────────────────────────────────────────────┐
│  📥 Inbox — 4 unprocessed                      │
│  ────────────────────────────────────────     │
│                                               │
│  ☐ "Book dentist appointment"                  │
│    Captured yesterday 4:15 PM · from phone    │
│    [Make a task]  [Remember]  [Dismiss]       │
│                                               │
│  ☐ "Research health insurance marketplace"    │
│    Captured yesterday 5:30 PM · from Raycast  │
│    [Make a task]  [Remember]  [Dismiss]       │
│                                               │
│  ☐ "Follow up with Sarah about project"       │
│    Captured today 8:00 AM · from phone        │
│    [Make a task]  [Remember]  [Dismiss]       │
│                                               │
│  ☐ "Check R2 vs Ioniq 5 comparison video"     │
│    Captured yesterday 11:00 PM · from phone   │
│    [Research this]  [Remember]  [Dismiss]     │
│                                               │
│  [Process all]                                │
└──────────────────────────────────────────────┘

Each item resolves in-place. Processing feeds memory, tasks, or research.
Dismissed items are marked processed, not deleted.
```

**Implementation type:** Tool (`kitty_get_inbox`) + Rich UI card with inline Action buttons per item
**Estimated complexity:** ~90 lines (Tool queries Gateway inbox endpoint, renders Rich UI card, each item has inline actions)
**Dependencies:** Gateway endpoint `GET /inbox?status=unprocessed` (Quick Capture endpoints exist; needs a listing projection)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns the inbox store.
**Why it's #6:** Closes the capture loop. Inbox zero from chat. Every throwaway thought Jacob captures finds its moment. The Gateway inbox already exists; this is a thin listing card with resolve actions.

---

### 7. Honest State Header

**Rank:** #7 of 38.

**Problem:** When chatting with Kitty, Jacob doesn't know what model is actually responding,
whether the Gateway is healthy, what project is current, or whether Builder is running.
The information exists but has no persistent surface. Trust requires visibility.

**User experience:**
```
A thin persistent bar in every chat conversation (injected by a Filter):

┌──────────────────────────────────────────────┐
│ 🐱 Kitty Auto · GPT-5.4 · Cloud  │ Builder ◉│
│ 📁 Project: kitty · main · 3 open PRs        │
│ 💰 Session: $0.04 (4.2k tokens)              │
└──────────────────────────────────────────────┘

Hover/expand states:
- Model: "Resolved: openai/gpt-5.4 via OpenRouter. Fast pin available."
- Builder: "1 running · 1 queued · 0 failed. [Open Mission Center]"
- Project: "kitty (code) · main branch · 3 open PRs · 2 active Builder packets"
- Cost: "This session: $0.04 · This month: $1.23 · [See breakdown]"

States change honestly:
- Unavailable: "⚠ Gateway unreachable — last seen 14:32"
- Degraded: "⚠ Fast route degraded — DeepSeek V3 unavailable, using Gemini Flash"
- Stale: "⏳ Model info from 12 minutes ago — refresh?"
```

**Implementation type:** Filter (outlet) — injects a state bar prefix into every assistant response as a Rich UI card
**Estimated complexity:** ~60 lines (Filter queries Gateway manifest snapshot, renders compact state bar)
**Dependencies:** Gateway Capability Manifest (product architecture Phase 1 — defined, not yet built)
**Kitty or Open WebUI:** Open WebUI Filter rendering the bar. Gateway Capability Manifest is the source of truth for model/project/connection/cost state.
**Why it's #7:** Honesty is Jacob's #1 value (Constitution prime directive). This bar makes trust ambient. It's always visible, always current, never fabricates. ~60 lines when the Capability Manifest exists.

---

## A-Tier — Daily Workflows

Extensions that power the core daily experience: capturing, remembering, executing.

---

### 8. Project Cockpit

**Rank:** #8 of 38.

**Problem:** Each Kitty project (job-search, benefits, kitty-code, learning) has its own activity,
tasks, memories, Builder work, and deadlines. But in chat, everything is flattened into one
conversation list. Jacob has to mentally reconstruct project context with every conversation switch.

**User experience:**
```
A per-project dashboard as a Rich UI card:

┌──────────────────────────────────────────────┐
│  📁 Project: Job Search                        │
│  ────────────────────────────────────────     │
│                                               │
│  Status: 12 applications · 3 responses (25%)  │
│  Avg response time: 4 days                    │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ ⚠ Acme Corp — 6 days no reply            │  │
│  │   Follow-up draft pending                │  │
│  │   [Draft email]                          │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ ◐ TechCorp — applied yesterday           │  │
│  │   Waiting for response                   │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ ✓ MegaCorp — phone screen scheduled      │  │
│  │   Tomorrow 2:00 PM (calendar)            │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Upcoming deadlines:                          │
│  • Follow up Acme Corp by Friday              │
│  • Register for career fair by Sunday         │
│                                               │
│  Recent activity:                             │
│  • Applied to TechCorp (yesterday)            │
│  • Research: updated target company list      │
│  • Memory: recruiter prefers email, not phone │
│                                               │
│  [Switch to this project]                    │
│  [See full activity]                         │
│  [Add a note]                                │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_project_cockpit`) + Rich UI card
**Estimated complexity:** ~130 lines (Tool + Rich UI card; Gateway needs project projection endpoint — partially exists via project queries)
**Dependencies:** Gateway endpoint `GET /state/project?project=X` (product architecture defines Now/Resume projections per project)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns the project projections.
**Why it's #8:** Project context is the backbone of the Resume Loop. Without it, every chat is disconnected. With it, Jacob switches projects and everything — context, next action, activity, deadlines — switches with him.

---

### 9. Memories — Browse, Search, Correct

**Rank:** #9 of 38.

**Problem:** Kitty remembers things, but Jacob has no way to see what it knows, correct wrong
memories, or prune stale ones. He has to trust that memory retrieval is working. "What does Kitty
know about X?" requires asking in chat and hoping the retrieval surfaces everything.

**User experience:**
```
Tool: "What do you remember about my job search?"

┌──────────────────────────────────────────────┐
│  🧠 Memory: Job Search                         │
│  ────────────────────────────────────────     │
│                                               │
│  24 facts remembered · Last: yesterday        │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ "Applied to Acme Corp on July 28"        │  │
│  │ Source: Chat, July 28 3:15 PM            │  │
│  │ Confidence: High · Used: 4 times         │  │
│  │ [Correct]  [Forget]                      │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ "Recruiters prefer email outreach"       │  │
│  │ Source: Captured insight, July 25        │  │
│  │ Confidence: Medium · Used: 2 times       │  │
│  │ [Correct]  [Forget]                      │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ "MegaCorp phone screen July 30"          │  │
│  │ Source: Calendar event, July 29          │  │
│  │ Confidence: High · Used: 1 time          │  │
│  │ [Correct]  [Forget]                      │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Stale memories (unused > 90 days): 2         │
│  [Review stale memories]                     │
│                                               │
│  [Search memories...]  [Remember something]   │
└──────────────────────────────────────────────┘

"Correct" opens inline editing: "Actually, it was July 29, not July 28."
"Forget" removes with confirmation: "Forget that I applied to Acme Corp?"
"Forget" is reversible for 24 hours: "Restored: 'Applied to Acme Corp on July 28'"
```

**Implementation type:** Tool (`kitty_search_memories`) + Rich UI card with inline Actions for Correct/Forget
**Estimated complexity:** ~150 lines (Tool + Rich UI + Correct/Forget Action handlers; Gateway memory graph already exists with search)
**Dependencies:** Gateway memory search (exists), memory correction endpoint (needs `PATCH /memory/:id`), memory forget endpoint (exists or trivial)
**Kitty or Open WebUI:** Open WebUI Rich UI card renders the browse experience. Gateway owns the memory graph and correction policy. The shell never decides what to remember or forget.
**Edge case:** "Kitty, what do you know about me?" returns everything, paginated. "Kitty, forget everything about my ex" requires approval (destructive).

---

### 10. Deadline Radar

**Rank:** #10 of 38.

**Problem:** Jacob has real deadlines — benefits paperwork, job application follow-ups, bill payments,
project milestones. They live in calendar, captures, memory, and tasks. There's no unified deadline
surface that says "here's what's coming, here's what's late."

**User experience:**
```
A conversational card or morning brief section:

┌──────────────────────────────────────────────┐
│  ⏰ Deadlines                                   │
│  ────────────────────────────────────────     │
│                                               │
│  🔴 Overdue                                    │
│  W-2 verification form — 4 days past          │
│  Source: Benefits tracker · added July 15     │
│  [Deal with this now]                         │
│                                               │
│  🟡 This week                                 │
│  Acme Corp follow-up — Friday (2 days)        │
│  Source: Job search project · July 28         │
│  Phone screen prep — Thursday (1 day)         │
│  Source: Calendar · MegaCorp interview        │
│                                               │
│  🟢 Next week                                 │
│  Update portfolio site — next Monday          │
│  Register for career fair — next Sunday       │
│                                               │
│  [See all deadlines]  [Create a deadline]     │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_get_deadlines`) + Rich UI card, or as a section in the morning briefing Event Function
**Estimated complexity:** ~80 lines (Tool queries Gateway consolidated deadline projection)
**Dependencies:** Gateway deadline projection that scans calendar, tasks, captures, and memory for date-bearing items (does not exist today)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway extracts, deduplicates, and ranks deadlines.
**Why it's #10:** Life-first means deadlines-first. An overdue benefits deadline is more important than any code PR. This radar surfaces what matters in time order, not project order.

---

### 11. Quick Command Bar

**Rank:** #11 of 38.

**Problem:** Switching projects, viewing the brief, capturing a thought, sending work to Builder —
these all require either: remembering the right phrase, typing it, waiting for the model to
interpret it, and hoping it does the right thing. Or they require leaving chat entirely.

**User experience:**
```
Typing "/" in the chat input shows an autocomplete command palette:

/               ← Jacob types this
─────────────────
/project kitty  → Switch to kitty project
/project job    → Switch to job-search project
/brief          → Show today's brief
/brief week     → Show weekly summary
/capture        → Quick capture current thought
/remember       → Remember something important
/builder        → Open Builder Mission Center
/inbox          → Show capture inbox
/memory         → Search/browse memories
/deadlines      → Show deadline radar
/resume         → Resume current project
/one-thing      → Show the One Thing card
/activity       → Show activity river
/cockpit        → Show project cockpit
/status         → Show honest state
/cost           → Show session/month cost
/health         → Show system health
/expert         → Launch expert swarm review
/review         → Start daily review
/judge          → Get independent review of current work

Commands are resolved client-side by the Event Function (fast, deterministic).
They trigger Gateway endpoints, not model interpretation.
```

**Implementation type:** Event Function (`on_user_message`) — detects `/command` syntax, intercepts before model, routes to Gateway endpoint, returns result as Rich UI card
**Estimated complexity:** ~60 lines (Event Function with command routing table + autocomplete is stock Open WebUI behavior)
**Dependencies:** Gateway endpoints for each command (many already exist or are covered by other extensions)
**Kitty or Open WebUI:** Open WebUI Event Function. Gateway endpoints handle the actual work.
**Why it's #11:** The fastest path from intent to result. No model interpretation, no ambiguity, no wasted tokens. Jacob types `/project kitty` and the project switches. Faster than describing what he wants.

---

### 12. Weekly Retrospective

**Rank:** #12 of 38.

**Problem:** Life moves fast. At the end of a week, Jacob has no summary of what he did,
what happened, what was learned, what changed. Reconstructing the week requires archaeology
across chats, Builder logs, captures, and memory.

**User experience:**
```
On Saturday morning (triggered by day-of-week detection in the morning briefing):

┌──────────────────────────────────────────────┐
│  📊 Your Week: July 28 – August 2              │
│  ────────────────────────────────────────     │
│                                               │
│  Job Search                                    │
│  • 4 applications submitted                   │
│  • 2 responses received (TechCorp, MegaCorp)  │
│  • 1 phone screen scheduled                   │
│  • 1 follow-up drafted                        │
│                                               │
│  Builder                                       │
│  • 3 packets completed · 1 merged             │
│  • 2 tests fixed · 1 CI repair                │
│  • Total cost: $0.87                          │
│                                               │
│  Learning                                      │
│  • React Server Components (Tutor session)    │
│  • Open WebUI extension architecture          │
│                                               │
│  Captures & Ideas                              │
│  • 12 captures · 8 processed · 4 pending      │
│  • 3 new memories formed                      │
│                                               │
│  Deadlines This Week                           │
│  ✓ Acme Corp follow-up (completed Friday)     │
│  ⚠ Benefits W-2 form (still overdue)          │
│                                               │
│  [Save to journal]  [Share as markdown]       │
│  [Create next week's focus areas]             │
└──────────────────────────────────────────────┘

Every claim is a link to evidence: the chat where it was captured,
the Builder receipt, the memory record.
```

**Implementation type:** Event Function (`on_chat_start`, day-of-week = Saturday) + Rich UI card
**Estimated complexity:** ~120 lines (Event Function detects Saturday, queries Gateway retrospective projection, renders card)
**Dependencies:** Gateway retrospective projection (aggregates activity events by week — product architecture defines projections)
**Kitty or Open WebUI:** Open WebUI Event Function renders the card. Gateway owns the retrospective aggregation.
**Why it's #12:** Closes the weekly loop. Turns a stream of daily activity into a coherent narrative. Without it, the quiet accomplishments of a week are invisible. With it, Jacob sees progress even when it felt chaotic.

---

### 13. Session Insight Prompt

**Rank:** #13 of 38.

**Problem:** Jacob learns things in chat sessions — architectural insights, debugging discoveries,
life observations. He taught Kitty to use `/remember` but often forgets in the flow of work.
Sessions end without extracting durable knowledge. Valuable insights evaporate.

**User experience:**
```
At the end of a conversation (detected by idle time or explicit session-end):

┌──────────────────────────────────────────────┐
│  💡 Session Wrap                                │
│  ────────────────────────────────────────     │
│                                               │
│  This session: 37 messages · 42 minutes       │
│  Cost: $0.12 · Model: GPT-5.4 via DeepSeek   │
│                                               │
│  Looks like you might have learned:           │
│                                               │
│  • "Open WebUI Filters transform messages     │
│    before they reach the model — the `inlet`  │
│    method runs on incoming, `outlet` on       │
│    outgoing"                                   │
│    [Remember this]                            │
│                                               │
│  • "Builder's bounded read-only projection    │
│    lives in gateway/builder_status.py and     │
│    should never join Builder's SQLite tables  │
│    into another state machine"                │
│    [Remember this]                            │
│                                               │
│  • "The PYTHONPATH regression was caused by   │
│    a stale venv, not a code change"           │
│    [Remember this]                            │
│                                               │
│  [Save all as insights]  [Skip]              │
│                                               │
│  Would you also like to review today?         │
│  [Start daily review]                        │
└──────────────────────────────────────────────┘
```

**Implementation type:** Action (`kitty_session_wrap`) — user clicks, or Event Function detects session idleness
**Estimated complexity:** ~80 lines (Action sends conversation to Gateway's insight extraction endpoint, Gateway returns candidate facts, user confirms)
**Dependencies:** Gateway insight extraction from conversation context (builds on existing memory graph and context assembly)
**Kitty or Open WebUI:** Open WebUI Action button. Gateway extracts candidate insights from conversation context.
**Why it's #13:** The learning loop. Without it, Kitty is a tool. With it, Kitty is a companion that helps Jacob accumulate durable knowledge. Every "aha" moment survives the session.

---

### 14. Daily Review

**Rank:** #14 of 38.

**Problem:** Jacob doesn't have an end-of-day ritual in Kitty. No structured reflection.
No capture of what went well, what didn't, what to carry forward. The journal exists
but requires manual initiation.

**User experience:**
```
Triggered by Action button or end-of-day detection (after 8 PM, first message):

┌──────────────────────────────────────────────┐
│  🌙 Daily Review — August 5                    │
│  ────────────────────────────────────────     │
│                                               │
│  Let's close out today.                        │
│                                               │
│  1. What got done?                             │
│  [Auto-filled from activity:]                 │
│  • Drafted Acme Corp follow-up email          │
│  • Builder merged test fix                    │
│  • 3 captures processed                       │
│  • Researched Open WebUI extensions           │
│  [Edit]                                       │
│                                               │
│  2. What's still open?                        │
│  [Auto-filled from tasks/deadlines:]          │
│  • W-2 benefits verification form             │
│  • Portfolio site update                      │
│  [Edit]                                       │
│                                               │
│  3. What did you learn?                        │
│  [Auto-filled from session insights:]         │
│  • Open WebUI Filter inlet/outlet pattern     │
│  [Add more...]                                │
│                                               │
│  4. What's the vibe?                          │
│  [😤 Frustrated] [😐 Fine] [🙂 Good] [🎉 Great] │
│                                               │
│  5. One thing for tomorrow?                   │
│  [Auto-filled from One Thing projection:]     │
│  • Submit W-2 verification form               │
│  [Choose different...]                        │
│                                               │
│  [Save review]  [Save + set tomorrow's focus] │
└──────────────────────────────────────────────┘

Saved to journal. Tomorrow's One Thing is pre-set.
One week of reviews generates the weekly retrospective.
```

**Implementation type:** Action (`kitty_daily_review`) + Rich UI interactive form
**Estimated complexity:** ~120 lines (Interactive Rich UI form that pre-fills from Gateway activity/state, saves to journal)
**Dependencies:** Gateway journal endpoint (exists), activity projection, One Thing projection
**Kitty or Open WebUI:** Open WebUI Rich UI interactive form. Gateway receives the review, saves to journal, and updates tomorrow's context.
**Why it's #14:** Rounds out the daily loop. Morning briefing opens the day. Daily review closes it. Together they make Kitty the bookends of Jacob's day.

---

### 15. One-Tap Delegate to Builder

**Rank:** #15 of 38.

**Problem:** In chat, Jacob describes a code fix or feature he wants. Kitty diagnoses and plans.
But turning that plan into Builder execution requires leaving chat, opening a terminal, running
Builder CLI commands. The gap between "yes, that's what I want" and "Builder is working on it"
should be zero.

**User experience:**
```
Kitty: "I've diagnosed the issue. The SSE stream terminates correctly but the
verifier expects [DONE] as a separate event while the Gateway emits it inline.
Fix is ~8 lines in gateway/streaming.py. Tests should cover the inline [DONE]
case. Want me to send this to Builder?"

┌──────────────────────────────────────────────┐
│  🔧 Builder Proposal                           │
│  ────────────────────────────────────────     │
│                                               │
│  Fix: Streaming smoke test [DONE] parsing      │
│  Files: gateway/streaming.py (~8 lines)       │
│  Tests: Add inline [DONE] case to smoke test  │
│  Budget: 3 attempts · max $0.50              │
│  Worker: opencode (deepseek-v4-pro)          │
│  Review: Independent model required           │
│                                               │
│  [Send to Builder]  [Edit scope]  [Cancel]   │
└──────────────────────────────────────────────┘

Click "Send to Builder":
- Action creates the packet in Gateway
- Gateway queues it in Builder
- Builder Mission Center updates in real time
- Card shows: "Packet ktf-006 queued. Builder will start when a worker is available."

When Builder completes:
- Notification appears: "Builder finished 'Fix streaming smoke test'. Ready for review."
- Card shows diff, test results, independent review outcome
- [Approve & merge]  [Reject]  [See details]
```

**Implementation type:** Action (`kitty_send_to_builder`) + Rich UI proposal card
**Estimated complexity:** ~100 lines (Action packages chat context into a Builder proposal, Gateway validates and queues; approval gate for merge)
**Dependencies:** Gateway Builder action endpoints (partially exist), approval policy engine
**Kitty or Open WebUI:** Open WebUI Action. Gateway validates proposal against approval policy and queues in Builder.
**Why it's #15:** The bridge from thought to execution. Currently Builder feels like a separate product. With one-tap delegation, it becomes a natural extension of chat. "Fix this" → Builder is working on it.

---

### 16. Image Studio Command

**Rank:** #16 of 38.

**Problem:** Image generation requires opening Image Studio (a separate surface or the old kitty-chat
UI). The authorized Conversational Image Agent lane (issue #336) aims for a character-first
conversational workflow, but there's no chat-native way to generate, view, or iterate on images.

**User experience:**
```
Jacob: "Draw me a cyberpunk cat sitting on a server rack"

Kitty calls Image MCP → Gateway routes to Image Studio pipeline:

┌──────────────────────────────────────────────┐
│  🎨 Image Studio                              │
│  ────────────────────────────────────────     │
│                                               │
│  [        generated image appears here        ]│
│                                               │
│  "Cyberpunk cat on server rack"               │
│  Model: ComfyUI · SDXL · 4.2s                 │
│  Seed: 847291 · Cost: $0.02                    │
│                                               │
│  [Generate variations]  [Refine prompt]       │
│  [Edit: keep cat, change background]          │
│  [Add to favorites]  [Open in Studio]         │
│                                               │
│  ────────────────────────────────────────     │
│  Recent images:                               │
│  [thumb1] [thumb2] [thumb3] [thumb4]          │
│  [Open Image Studio]                          │
└──────────────────────────────────────────────┘

Jacob: "Keep his face, change his build from lean to muscular"

Kitty edits the image (character consistency from the Conversational Image Agent plan).
New card shows the edit with parent lineage: "Edit of 'cyberpunk cat' — changed build"
```

**Implementation type:** MCP server (Image MCP) + Rich UI card for results
**Estimated complexity:** ~150 lines (MCP server proxies to Gateway image endpoints; Rich UI card renders result, variations, lineage)
**Dependencies:** Gateway image pipeline (issue #336 — Conversational Image Agent lane, not yet built), ComfyUI worker, image artifact store
**Kitty or Open WebUI:** Open WebUI MCP server + Rich UI card. Gateway owns the image pipeline, lifecycle, cost tracking, and artifact registry.
**Why it's #16:** The Conversational Image Agent lane is Jacob's authorized P1 product outcome. This extension is the chat-native interface for it. Lower rank because it depends on the image pipeline being built first.

---

### 17. Cost Monitor

**Rank:** #17 of 38.

**Problem:** Jacob is cost-aware (937 messages touch tokens/cost/credits). He needs to know
what Kitty is spending without opening a terminal and running cost queries. He shouldn't discover
a surprise bill at the end of the month.

**User experience:**
```
A thin cost card, or a section in the Honest State Header:

┌──────────────────────────────────────────────┐
│  💰 Cost                                       │
│  ────────────────────────────────────────     │
│                                               │
│  Today: $0.23                                 │
│  ┌─────────────────────────────────────────┐  │
│  │ GPT-5.4   ████████████░░░░░░  $0.18     │  │
│  │ DeepSeek  ████░░░░░░░░░░░░░░  $0.04     │  │
│  │ Qwen3     ██░░░░░░░░░░░░░░░░  $0.01     │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  This month (Aug): $1.47                       │
│  Last month (Jul): $12.83                      │
│  Projected (Aug): ~$11.42                      │
│                                               │
│  Provider balances:                            │
│  • OpenRouter: $8.23 remaining                 │
│  • DeepSeek: $1.47 remaining                   │
│                                               │
│  [Set monthly budget]  [See full breakdown]   │
└──────────────────────────────────────────────┘

Warning states:
- "⚠ On track to exceed monthly budget ($15) by $4"
- "⚠ DeepSeek balance below $2 — consider switching Fast route"
- "⚠ OpenAI credits exhausted — Think route failed over to Qwen3"
```

**Implementation type:** Tool (`kitty_get_cost`) + Rich UI card
**Estimated complexity:** ~80 lines (Tool queries Gateway cost tracking, renders breakdown card)
**Dependencies:** Gateway cost tracking with per-model, per-session, per-month aggregation (cost data exists in attempt records; needs a projection)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns cost truth.
**Why it's #17:** Financial awareness without leaving the shell. Prevents surprise bills. Feeds directly into Jacob's model selection decisions ("use Fast for bulk work, premium for judgment calls").

---

### 18. System Health Dashboard

**Rank:** #18 of 38.

**Problem:** When something breaks, Jacob has to diagnose it manually: `./kitty doctor`, check
processes, read logs. The health information exists in Gateway but has no chat surface.
Breakage is discovered when something fails, not before.

**User experience:**
```
Rich UI card showing live system health:

┌──────────────────────────────────────────────┐
│  ⚡ System Health                              │
│  ────────────────────────────────────────     │
│                                               │
│  Gateway      🟢 Healthy (127.0.0.1:8000)    │
│  LiteLLM      🟢 Healthy (127.0.0.1:8001)    │
│  Open WebUI   🟢 Running (v0.10.2 · 127.0.0.1:3000) │
│  Builder      🟢 Active (2 workers available) │
│  ChromaDB     🟢 Connected (1,247 documents)  │
│  mem0         🟢 Connected                    │
│                                               │
│  MCP Servers                                  │
│  Filesystem   🟢 Connected · ~/Projects       │
│  Git          🟢 Connected · read-only        │
│  Shell        🟢 Connected · read-only        │
│  Image        🟡 Starting...                   │
│                                               │
│  Providers                                    │
│  OpenRouter   🟢 GPT-5.4, DeepSeek V3         │
│  DeepSeek     🟢 Qwen3-235B                   │
│  Gemini       🟡 Rate limited (reset in 12m)  │
│  MLX Local    🔴 Unavailable — model not loaded│
│                                               │
│  Storage                                      │
│  SQLite       🟢 12.4 MB · WAL mode           │
│  Data dir     🟢 847 MB · /Users/jacob/...    │
│  Backups      🟡 Last backup: 3 days ago      │
│                                               │
│  [Run doctor]  [Refresh]  [See logs]          │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_get_health`) + Rich UI card with auto-refresh
**Estimated complexity:** ~100 lines (Tool queries Gateway `/health` + `/doctor` endpoints, renders health grid)
**Dependencies:** Gateway `/health` and repair/doctor endpoints (already exist)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns health probes and owns the truth about what's running.
**Why it's #18:** Runs the doctor from chat. Makes system health ambient. Catches problems before Jacob trips over them.

---

### 19. Signal Feed

**Rank:** #19 of 38.

**Problem:** Kitty has web monitors watching for content changes, keyword matches, and
deadline-bearing documents. The signals fire silently — they log to the signal store but
surfaced nowhere in the daily experience. Jacob misses them.

**User experience:**
```
A signal card in the morning brief or as a standalone widget:

┌──────────────────────────────────────────────┐
│  📡 Signals — 3 new since yesterday            │
│  ────────────────────────────────────────     │
│                                               │
│  🔔 Web monitor: "Rivian R2 news"              │
│  2 new articles matched:                      │
│  • "Rivian R2 Gets 300+ Mile EPA Rating"       │
│    Electrek · 2 hours ago                      │
│    [Read summary]  [Open article]              │
│  • "Production Timeline Update — 2027"         │
│    The Verge · 4 hours ago                     │
│    [Read summary]  [Open article]              │
│                                               │
│  🔔 Nudge: "Weekly job search review"          │
│  Reminder to check your application pipeline  │
│  [Review applications]  [Snooze 1 day]        │
│                                               │
│  [Configure monitors]  [See all signals]      │
└──────────────────────────────────────────────┘
```

**Implementation type:** Event Function (injected into morning brief) or Tool (`kitty_get_signals`) + Rich UI card
**Estimated complexity:** ~70 lines (queries Gateway signal store, renders signal cards with inline actions)
**Dependencies:** Gateway signal store (`gateway/signal_store.py` — already exists), web monitor integration
**Kitty or Open WebUI:** Open WebUI Rich UI card or brief section. Gateway owns the signal store and monitor infrastructure.
**Why it's #19:** Makes the background automations visible. Without it, web monitors and nudges are ghosts — they run but nobody sees them. This is the notification center for automated awareness.

---

### 20. Expert Swarm Panel

**Rank:** #20 of 38.

**Problem:** The Expert Swarm skill launches 8 domain experts to review designs, plans,
or code. Currently it's triggered from a terminal skill. Bringing it into chat makes it
accessible during normal workflows.

**User experience:**
```
Jacob: "Review my product architecture for the Open WebUI migration"

Kitty offers: "Want me to launch an expert swarm review on this?"

┌──────────────────────────────────────────────┐
│  🦉 Expert Swarm Review                        │
│  ────────────────────────────────────────     │
│                                               │
│  Target: Open WebUI migration product plan    │
│  Reviewers: 8 domain experts                  │
│  Model: GPT-5.4 (high-quality judgment)      │
│  Estimated cost: ~$0.30                       │
│                                               │
│  [Launch review]  [Customize panel]           │
└──────────────────────────────────────────────┘

Kitty launches the review (SSE streams progress):

┌──────────────────────────────────────────────┐
│  🦉 Expert Swarm — Review Complete              │
│  ────────────────────────────────────────     │
│                                               │
│  Strong Consensus (8/8):                      │
│  • "The Gateway-first approach is correct —   │
│    don't put routing logic in Open WebUI"     │
│  • "The extension inventory covers the right  │
│    surface area"                              │
│                                               │
│  Concerns Raised (4/8):                       │
│  • "Approval gate Event Function creates a    │
│    second approval surface — ensure it's      │
│    the thin adapter, not a parallel policy"   │
│  • "Rich UI components should be stateless —  │
│    Gateway owns all state"                    │
│                                               │
│  Isolated Concerns (1/8):                     │
│  • Security expert: "Input sanitization Filter│
│    should be P0, not P1"                      │
│                                               │
│  Cost: $0.27 · Duration: 48s                  │
│  [See full report]  [Address concerns]        │
└──────────────────────────────────────────────┘
```

**Implementation type:** Action (`kitty_expert_swarm`) + Rich UI card with SSE progress streaming
**Estimated complexity:** ~120 lines (Action triggers Gateway expert swarm endpoint; Rich UI card renders streaming progress and final report)
**Dependencies:** Gateway expert swarm endpoint (skill exists; needs a Gateway API wrapper), SSE streaming for progress
**Kitty or Open WebUI:** Open WebUI Action + Rich UI card. Gateway runs the expert swarm, streams results. Expert Swarm is a Gateway-owned capability.
**Why it's #20:** Brings an existing superpower into the shell. Currently the expert swarm is a terminal skill. In chat, it's a one-tap review from the design workflow.

---

### 21. Notification Center

**Rank:** #21 of 38.

**Problem:** Things require Jacob's attention — Builder completions need review, deadlines
are approaching, captures are piling up, approvals are pending. Each of these fires independently
but there's no consolidated "needs you" surface.

**User experience:**
```
A dedicated chat or card showing everything requiring Jacob's attention:

┌──────────────────────────────────────────────┐
│  🔔 Needs Your Attention — 5 items             │
│  ────────────────────────────────────────     │
│                                               │
│  🔴 Urgent                                     │
│  • W-2 benefits form — 4 days overdue         │
│    [Deal with this]                           │
│                                               │
│  🟡 Action needed                              │
│  • Builder: "Fix streaming smoke test" ready  │
│    for review (1 file, 3 tests)               │
│    [Review]  [Approve & merge]                │
│                                               │
│  • 4 captures unprocessed in inbox            │
│    [Process inbox]                            │
│                                               │
│  • Expert swarm review complete on            │
│    "Open WebUI migration plan"                │
│    [Read review]                              │
│                                               │
│  🟢 Info                                       │
│  • Open WebUI 0.10.3 is available (pinned at  │
│    0.10.2)                                    │
│    [See changelog]  [Dismiss]                 │
│                                               │
│  [Clear all]                                  │
└──────────────────────────────────────────────┘

This card appears:
- In the morning briefing
- When a chat starts and there are pending items
- On demand with `/needs-attention` command
```

**Implementation type:** Filter (inlet) — injects a notification card at the start of new conversations when there are pending items, or standalone Tool
**Estimated complexity:** ~90 lines (Filter queries Gateway "needs attention" projection, renders card)
**Dependencies:** Gateway "needs attention" projection (product architecture defines this — aggregates approvals, failures, deadlines, unprocessed inbox)
**Kitty or Open WebUI:** Open WebUI Filter/Rich UI card. Gateway owns the needs-attention projection.
**Why it's #21:** The "inbox zero" of Kitty. Consolidated triage. Without it, every attention item is a separate discovery. With it, Jacob opens Kitty and immediately knows what needs him.

---

### 22. Evidence Browser

**Rank:** #22 of 38.

**Problem:** Kitty makes claims. Builder says it merged code. Memory says Jacob applied to a job.
The claims are backed by execution receipts, but Jacob can't inspect the evidence from chat.
Trust requires verifiability — the Constitution requires "a short path from any claim to its proof."

**User experience:**
```
On any claim in chat, Jacob can ask "show me the evidence":

┌──────────────────────────────────────────────┐
│  📋 Evidence: Builder completed "Fix streaming │
│     smoke test"                                │
│  ────────────────────────────────────────     │
│                                               │
│  Execution Receipt                             │
│  ├─ Packet: ktf-006                            │
│  ├─ Worker: opencode (deepseek-v4-pro)        │
│  ├─ Attempt: 1 of 3                            │
│  ├─ Started: 09:15 AM                          │
│  ├─ Completed: 09:18 AM (2m 47s)              │
│  ├─ Cost: $0.04                                │
│  │                                              │
│  ├─ Changed files:                              │
│  │  tests/test_streaming.py (+12, -0)          │
│  │  [View diff]                                │
│  │                                              │
│  ├─ Test results:                               │
│  │  3 passed, 0 failed, 0 skipped              │
│  │  [View test output]                         │
│  │                                              │
│  ├─ Independent review:                         │
│  │  Reviewer: claude-sonnet-4-5                │
│  │  Verdict: Approved (no issues)              │
│  │  [View review]                              │
│  │                                              │
│  └─ Merge:                                     │
│     Merged to main at 09:42 AM                 │
│     Commit: 8c58f52                             │
│     [View on GitHub]                           │
│                                               │
│  [Copy receipt]  [Verify claims]              │
└──────────────────────────────────────────────┘

Every line is independently verifiable:
- Diff: links to GitHub or local git
- Tests: links to test output
- Review: links to review record
- Merge: links to commit on GitHub
```

**Implementation type:** Triggered by Action button ("Show Evidence") on any Builder result card
**Estimated complexity:** ~100 lines (queries Gateway execution receipts, renders evidence chain as Rich UI card)
**Dependencies:** Gateway execution receipt store (product architecture Phase 3 — defined, not yet built)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns receipt store and evidence chain.
**Why it's #22:** Implements the Constitution's "trust presentation" requirement. Without evidence, Kitty's claims are unverifiable. With it, every claim has a one-tap path to proof.

---

### 23. Voice Memo Capture

**Rank:** #23 of 38.

**Problem:** Jacob captures thoughts from his phone — voice memos, quick notes, reminders.
The capture endpoint exists but requires explicit triggering. There's no frictionless voice-to-capture
path from the Open WebUI mobile PWA.

**User experience:**
```
On the phone (Open WebUI PWA), Jacob taps the mic button:

Kitty: (listening...)

Jacob: "Remind me to research health insurance plans for the marketplace deadline"

Kitty processes the audio, confirms:

┌──────────────────────────────────────────────┐
│  🎤 Captured                                  │
│  ────────────────────────────────────────     │
│                                               │
│  "Remind me to research health insurance       │
│   plans for the marketplace deadline"          │
│                                               │
│  Processed as:                                 │
│  • 📥 Quick Capture (inbox)                    │
│  • ⏰ Deadline detected: "marketplace deadline" │
│    → Added to Deadline Radar                   │
│  • 📋 Task suggestion: "Research health        │
│    insurance plans"                            │
│    [Create task]                               │
│                                               │
│  [Capture another]  [Done]                    │
└──────────────────────────────────────────────┘
```

**Implementation type:** Action (`kitty_voice_capture`) — uses stock Open WebUI voice input (Web Speech API), sends transcription to Gateway capture endpoint
**Estimated complexity:** ~70 lines (Action receives transcribed text, sends to Gateway capture endpoint, Gateway processes for deadlines/tasks)
**Dependencies:** Gateway Quick Capture endpoint (exists), Gateway deadline extraction from text, stock Open WebUI voice input (already built in)
**Kitty or Open WebUI:** Open WebUI Action (leverages stock voice input). Gateway processes the capture, extracts deadlines/tasks, saves to inbox.
**Why it's #23:** Phone capture is the life-first workflow. Walking to the car, Jacob remembers something — opens Kitty on phone, speaks it, and it's captured, triaged, and surfaced at the right moment. Builds on stock Open WebUI voice input.

---

### 24. Decision Log

**Rank:** #24 of 38.

**Problem:** Kitty makes decisions — which model to route to, whether to approve a tool call,
when to ask Jacob for approval, when to proceed autonomously. The decisions are recorded
but invisible. Jacob can't audit the decision history.

**User experience:**
```
Tool: "Kitty, what decisions did you make today?"

┌──────────────────────────────────────────────┐
│  ⚖️ Decisions — Today                          │
│  ────────────────────────────────────────     │
│                                               │
│  09:15  Auto: Routed "fix streaming test" to  │
│         DeepSeek V3 (coding task, under $0.05)│
│                                               │
│  09:42  Auto: Merged ktf-006 to main          │
│         (approved packet, independent review  │
│         passed, no conflicts)                  │
│                                               │
│  10:00  Notify: Remembered "Open WebUI        │
│         Filters have inlet/outlet methods"    │
│                                               │
│  10:15  Approval: "Write to ~/Projects/kitty/ │
│         .env" → Denied (secrets file, requires│
│         explicit Jacob authorization per       │
│         approval policy v2.1)                 │
│                                               │
│  10:30  Auto: Selected GPT-5.4 for research   │
│         query (complex, multi-source task)     │
│                                               │
│  [See all decisions]  [Appeal a decision]     │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_get_decisions`) + Rich UI card
**Estimated complexity:** ~80 lines (Tool queries Gateway decision store, renders timeline)
**Dependencies:** Gateway decision log (product architecture defines `Decision` entity — Phase 5)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns every decision and its policy justification.
**Why it's #24:** Audit trail for autonomy. Shows Jacob that Kitty is making good decisions — and surfaces when it's being too cautious or too aggressive. Builds trust through transparency.

---

### 25. Knowledge Graph Browser

**Rank:** #25 of 38.

**Problem:** Kitty's memory is a graph of connected facts, but Jacob can only access it through
text search ("what do you know about X?"). He can't see the connections between memories,
discover unexpected links, or explore the graph visually.

**User experience:**
```
Tool: "Show me how my knowledge about React connects"

┌──────────────────────────────────────────────┐
│  🕸️ Knowledge Graph: React                     │
│  ────────────────────────────────────────     │
│                                               │
│  React                                         │
│  ├─ React Server Components                    │
│  │  ├─ "RSC runs on the server by default"    │
│  │  ├─ "use client marks a Client Component"  │
│  │  └─ "Learned from Tutor session, July 28"  │
│  ├─ Next.js (framework)                        │
│  │  ├─ "App Router uses RSC as default"       │
│  │  └─ "kitty-chat uses Next.js 15"           │
│  ├─ State Management                           │
│  │  ├─ "useState for local state"             │
│  │  └─ "React Context for shared state"       │
│  └─ Performance                                │
│     └─ "React.memo prevents unnecessary        │
│         re-renders"                            │
│                                               │
│  Connected topics:                             │
│  • TypeScript (15 shared facts)                │
│  • Vercel (3 shared facts)                     │
│  • JavaScript ecosystem (8 shared facts)       │
│                                               │
│  [Explore TypeScript connections]             │
│  [Search the graph...]                         │
│  [View as list]                                │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_knowledge_graph`) + Rich UI card with structured tree/network view
**Estimated complexity:** ~180 lines (Tool queries Gateway memory graph with depth/topic parameters; Rich UI renders hierarchical or list view)
**Dependencies:** Gateway memory graph with connected-fact traversal (memory graph exists; needs a graph-traversal endpoint)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns the memory graph traversal.
**Why it's #25:** Memory becomes explorable. Instead of "what do you know about X?" (a question with an answer), this is "show me the territory" (an exploration). Lower rank because it's a power-user feature — daily value is lower than the S-tier and A-tier extensions above it.

---

### 26. Learning Board

**Rank:** #26 of 38.

**Problem:** Jacob's learning is scattered across Tutor sessions, research conversations,
and self-directed study. There's no way to see "what am I studying right now?" as a
coherent board.

**User experience:**
```
Tool: "Show me what I'm learning"

┌──────────────────────────────────────────────┐
│  📚 Learning Board                             │
│  ────────────────────────────────────────     │
│                                               │
│  Currently Studying                            │
│  ┌─────────────────────────────────────────┐  │
│  │ Open WebUI Extension Architecture        │  │
│  │ Progress: ████████░░░░ 80%               │  │
│  │ 4 sessions · 12 facts remembered          │  │
│  │ Last: Today · "Filter inlet/outlet"      │  │
│  │ [Continue learning]                      │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ React Server Components                   │  │
│  │ Progress: ████░░░░░░░░ 40%               │  │
│  │ 2 sessions · 5 facts remembered           │  │
│  │ Last: July 28                             │  │
│  │ [Resume]                                 │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │ TypeScript Advanced Patterns             │  │
│  │ Progress: ██░░░░░░░░░░ 20%               │  │
│  │ Bootstrapped · no sessions yet            │  │
│  │ [Start]                                  │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  Recently Completed                            │
│  • Git worktree isolation patterns (July 25)  │
│  • Builder recovery proof methodology (Jul 24)│
│                                               │
│  [Add a learning goal]  [Tutor me on...]      │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_learning_board`) + Rich UI card
**Estimated complexity:** ~120 lines (Tool queries Gateway for Tutor sessions, memory facts by topic, and learning goals; renders board)
**Dependencies:** Gateway learning/topic aggregation (Tutor sessions exist; needs topic grouping and progress tracking)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns the learning data.
**Why it's #26:** Jacob is a curious generalist who self-educates continuously. A learning board turns scattered study into structured progress. Lower rank because it depends on topic aggregation that doesn't exist yet.

---

### 27. Life Dashboard

**Rank:** #27 of 38.

**Problem:** Jacob's life-first philosophy means job search, benefits, and education are the
top-priority projects. But there's no holistic view of "how's my life going?" The projects exist
separately — this dashboard connects them into one honest picture.

**User experience:**
```
Tool: "Show me my life dashboard"

┌──────────────────────────────────────────────┐
│  🏠 Life Dashboard                             │
│  ────────────────────────────────────────     │
│                                               │
│  Job Search                                    │
│  Applications: 12 total · 3 responses · 25%   │
│  Active: Acme Corp (follow-up due Friday)      │
│  Pipeline: 2 phone screens, 1 pending          │
│  [Open job search cockpit]                    │
│                                               │
│  Benefits & Admin                              │
│  ⚠ W-2 verification: 4 days overdue           │
│  Health insurance marketplace: research due   │
│  [Open benefits tracker]                      │
│                                               │
│  Education                                     │
│  Currently studying: Open WebUI extensions    │
│  2 active learning goals                       │
│  Career fair registration: Sunday             │
│  [Open learning board]                        │
│                                               │
│  Code Projects                                 │
│  Kitty: Builder active · 1 packet queued      │
│  Portfolio site: needs update (task pending)  │
│  [Open project cockpit]                       │
│                                               │
│  Health & Wellness                             │
│  (No health data connected)                    │
│  [Connect health data]                        │
│                                               │
│  This Week's Focus                             │
│  1. Submit W-2 verification form              │
│  2. Follow up on Acme Corp application        │
│  3. Complete Open WebUI extension research    │
│  [Edit focus areas]                           │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_life_dashboard`) + Rich UI card aggregating multiple Gateway projections
**Estimated complexity:** ~150 lines (Tool queries Gateway across all project projections, renders unified dashboard)
**Dependencies:** Gateway project projections for each life domain (now, resume, deadlines per project)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns every data source the dashboard aggregates.
**Why it's #27:** This is the "what would a MacOS desktop widget for my life look like?" extension. It's the highest-altitude view of Jacob's world. Lower rank because it's an aggregation of other extensions' data — build the project cockpits first, then combine them.

---

## B-Tier — Quality of Life

Extensions that make daily use smoother, more trustworthy, or more delightful but aren't the homepage.

---

### 28. Rich Tool Call Display

**Rank:** #28 of 38.

**Problem:** When Kitty calls tools (search memory, list projects, get calendar), the raw
function call JSON is invisible or ugly. Jacob can't tell what tools were used, what arguments
were passed, or what results came back. Tool execution is a black box.

**User experience:**
```
During a response, tool calls appear as inline Rich UI cards:

Kitty: "Let me check your calendar and your active projects..."

┌──────────────────────────────────────────────┐
│  🔧 kitty_get_calendar · 120ms                │
│  ────────────────────────────────────────     │
│  Today: Phone screen with MegaCorp at 2 PM    │
│  Tomorrow: Nothing scheduled                  │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  🔧 kitty_list_projects · 85ms                │
│  ────────────────────────────────────────     │
│  Active: job-search, kitty-code, benefits     │
│  Idle: learning, portfolio-site               │
└──────────────────────────────────────────────┘

Kitty: "You have a phone screen at 2 PM today with MegaCorp. For your
follow-up, the Acme Corp application is the most overdue item."

Footer on every tool card: tool name, elapsed time, result summary.
Click to expand: full arguments (secrets redacted), full result.
Failed tool calls show error with retry option.
```

**Implementation type:** Filter (outlet) — transforms raw tool call objects in the response stream into Rich UI cards
**Estimated complexity:** ~100 lines (Filter intercepts tool call metadata in the response, renders compact cards)
**Dependencies:** None beyond the Filter framework. Tool calls already flow through Open WebUI's response stream.
**Kitty or Open WebUI:** Open WebUI Filter. Gateway provides tool metadata. The shell renders it prettily.
**Why it's #28:** Tool visibility is essential for trust but is incremental polish. The One Thing card is transformative; this is refinement.

---

### 29. Input Sanitizer

**Rank:** #29 of 38.

**Problem:** Jacob might accidentally paste a secret (API key, password, credit card number)
into chat. The message goes to an external model. Once sent, it can't be unsent.

**User experience:**
```
Invisible in normal use. Only activates when PII is detected:

Jacob: (pastes text containing "sk-abc123def456...")

Before the message reaches the model:

┌──────────────────────────────────────────────┐
│  ⚠️ PII Detected                               │
│  ────────────────────────────────────────     │
│                                               │
│  Your message appears to contain an API key.  │
│  It has been redacted before sending.          │
│                                               │
│  Pattern: sk-***...***456                      │
│                                               │
│  [Send redacted]  [Edit message]  [Cancel]    │
└──────────────────────────────────────────────┘

Also detects: credit card numbers, SSNs, AWS keys, GitHub tokens, JWT tokens.
Redaction is irreversible for the model — the model never sees the raw value.
The original message is preserved in local chat history only.
```

**Implementation type:** Filter (inlet) — scans every user message before it reaches the model
**Estimated complexity:** ~60 lines (Filter with regex patterns, redacts matches, warns user)
**Dependencies:** None. Pure client-side regex in the Filter.
**Kitty or Open WebUI:** Open WebUI Filter only. Never touches Gateway. The model never sees raw secrets.
**Why it's #29:** Peace of mind. Never causes delight — only prevents disaster. Essential but not joyful.

---

### 30. Model Routing Card

**Rank:** #30 of 38.

**Problem:** When Jacob selects "Kitty Auto," he doesn't know what model actually responded.
The routing decision happens in Gateway and is invisible in the shell. Without visibility,
he can't build intuition about which routes produce which quality.

**User experience:**
```
After every assistant response, a small metadata card:

┌──────────────────────────────────────────────┐
│  Kitty Auto → openai/gpt-5.4 (Cloud)          │
│  2.3k tokens · $0.04 · 1.2s first token      │
│  Routing: classified as "research" query      │
└──────────────────────────────────────────────┘

Or, when using a specific route:

┌──────────────────────────────────────────────┐
│  Kitty Fast → deepseek/deepseek-v3 (Cloud)    │
│  1.1k tokens · <$0.01 · 0.3s first token     │
│  Routing: explicit pin, no classification     │
└──────────────────────────────────────────────┘

Sticky behavior:
- Selecting "Kitty Fast" → stays on Fast until explicitly changed
- Selecting "Kitty Auto" → reclassifies each request
- Selecting a specific model → stays pinned

The card shows:
- Requested route (what Jacob picked)
- Resolved model (what Gateway actually used)
- Execution location (Cloud or Local)
- Token count and cost
- Time to first token
- Warning if route degraded (e.g., "Fast route fell back to Gemini Flash")
```

**Implementation type:** Filter (outlet) — attaches metadata card to every assistant response
**Estimated complexity:** ~70 lines (Filter extracts model/routing metadata from Gateway response headers, renders compact card)
**Dependencies:** Gateway must include model identity, routing decision, and token/cost metadata in response headers or the response body
**Kitty or Open WebUI:** Open WebUI Filter. Gateway provides metadata. The shell renders the attribution.
**Why it's #30:** Honesty requirement from the Constitution. Essential for cost awareness and model intuition. Included in the product plan's MVP as `kitty_response_enrich` Filter.

---

### 31. Recovery Mode Indicator

**Rank:** #31 of 38.

**Problem:** When Kitty is degraded — Gateway health timeout, provider exhaustion, stale manifest —
Jacob sees an error or poor response but doesn't know why. Without a recovery indicator, he might
retry needlessly or abandon a fixable situation.

**User experience:**
```
When the Gateway is unhealthy, the Honest State Header shows the recovery state:

┌──────────────────────────────────────────────┐
│ ⚠ Gateway recovering — retry 2 of 3 · 4s... │
└──────────────────────────────────────────────┘

When the Gateway is fully unreachable:

┌──────────────────────────────────────────────┐
│ 🔴 Kitty unavailable                           │
│  ────────────────────────────────────────     │
│                                               │
│  Gateway is unreachable. This might be:       │
│  • A temporary startup delay (automatic       │
│    retry in progress)                          │
│  • A process crash (check ./kitty status)     │
│                                               │
│  Your chats are saved locally in Open WebUI.  │
│  Nothing has been lost.                        │
│                                               │
│  [Run ./kitty doctor]  [Retry now]            │
│  [Show health dashboard]                      │
└──────────────────────────────────────────────┘

When provider exhaustion occurs:

┌──────────────────────────────────────────────┐
│ ⚠ All providers temporarily unavailable       │
│  ────────────────────────────────────────     │
│                                               │
│  Your request is saved and will retry         │
│  automatically. You don't need to do          │
│  anything.                                     │
│                                               │
│  Estimated retry: 30 seconds                   │
│  [Force retry now]                            │
└──────────────────────────────────────────────┘
```

**Implementation type:** Filter (outlet) — detects Gateway error responses and renders recovery cards instead of raw error JSON
**Estimated complexity:** ~80 lines (Filter with error detection, recovery state mapping, user-friendly messages)
**Dependencies:** Gateway error response format (standard HTTP status codes + structured error bodies)
**Kitty or Open WebUI:** Open WebUI Filter. Gateway provides structured errors. The shell renders human-readable recovery guidance.
**Why it's #31:** Fail-loud, never mask. The product plan's `kitty_error_format` Filter. Essential for trust but never pleasant — it's what you see when things go wrong.

---

### 32. Memory Staleness Queue

**Rank:** #32 of 38.

**Problem:** Kitty remembers things. Some memories go unused for months. Others are
contradicted by newer evidence. There's no process for Jacob to review and prune the
memory graph. Over time, stale memories degrade retrieval quality.

**User experience:**
```
Periodically (weekly or on-demand), a card surfaces memories for review:

┌──────────────────────────────────────────────┐
│  🧹 Memory Review — 5 items to check           │
│  ────────────────────────────────────────     │
│                                               │
│  Stale (unused > 90 days):                    │
│  • "Preferred IDE is VS Code" —                │
│    Last used: April 12 · Confidence: High     │
│    [Keep]  [Forget]  [Update...]             │
│                                               │
│  • "Learning Spanish on Duolingo" —            │
│    Last used: March 3 · Confidence: Low       │
│    [Keep]  [Forget]                           │
│                                               │
│  Possibly Contradicted:                        │
│  • "Using macOS Ventura" vs                    │
│    "macOS Sequoia 15.6" (newer, July 30)      │
│    [Keep both]  [Forget older]  [Merge]       │
│                                               │
│  Stale by Policy (auto-forget candidates):    │
│  • 2 memories older than 6 months, unused,    │
│    low confidence. Auto-forget unless you     │
│    intervene in 7 days.                       │
│    [Review]  [Let them expire]                │
│                                               │
│  [Review all 5]  [Skip for now]              │
└──────────────────────────────────────────────┘
```

**Implementation type:** Action (`kitty_memory_review`) + Rich UI card
**Estimated complexity:** ~80 lines (Action queries Gateway for stale/contradicted memories, renders review card)
**Dependencies:** Gateway memory staleness detection (memory graph exists; needs staleness query)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns memory lifecycle.
**Why it's #32:** Memory hygiene. Important for long-term quality but not something Jacob wants to do every day. Weekly background task.

---

### 33. Prompt Library Browser

**Rank:** #33 of 38.

**Problem:** Stock Open WebUI has a prompt library, but it's generic. Kitty should have
curated prompts that reflect Jacob's actual workflows: code review, job search outreach,
benefits research, learning sessions, etc.

**User experience:**
```
A curated prompt library specific to Jacob's life:

┌──────────────────────────────────────────────┐
│  📝 Kitty Prompts                              │
│  ────────────────────────────────────────     │
│                                               │
│  Code                                          │
│  • "Review this PR for correctness"           │
│  • "Audit this module for error handling"     │
│  • "Explain this architecture"                │
│  • "Generate test cases for this function"    │
│                                               │
│  Job Search                                    │
│  • "Draft a follow-up email for this job"     │
│  • "Research this company's culture"          │
│  • "Prepare talking points for this phone     │
│    screen"                                     │
│  • "Rewrite my resume for this job description"│
│                                               │
│  Life Admin                                    │
│  • "Summarize this benefits document"         │
│  • "Draft an email to my insurance provider"  │
│  • "Create a checklist for moving apartments" │
│                                               │
│  Learning                                      │
│  • "Explain this concept to me like I'm 5"    │
│  • "Tutor me on [topic] with examples"        │
│  • "Quiz me on what I learned today"          │
│                                               │
│  [Create custom prompt]  [Edit prompts]       │
└──────────────────────────────────────────────┘

Each prompt loads a template into the chat input with the right context.
Kitty routes it to the appropriate model based on the prompt type.
```

**Implementation type:** Stock Open WebUI prompt library + Filter to tag prompts with domain context
**Estimated complexity:** ~40 lines (Filter injects domain annotation based on selected prompt tag)
**Dependencies:** None. Uses stock Open WebUI prompt library. Filter annotates for routing.
**Kitty or Open WebUI:** Stock Open WebUI prompt library. Kitty provides the prompt content and the Filter tagging.
**Why it's #33:** Small code, modest delight. A curated prompt library is nice but Jacob's natural language use is already effective. The main value is discoverability for power-use patterns.

---

### 34. Project Templates

**Rank:** #34 of 38.

**Problem:** Creating a new project in Kitty (e.g., "job-search-spring-2026" or "apartment-hunt")
requires manual setup: creating tasks, setting context, linking knowledge. No reusable template.

**User experience:**
```
Jacob: "Create a new job search project"

┌──────────────────────────────────────────────┐
│  📁 New Project: Job Search                    │
│  ────────────────────────────────────────     │
│                                               │
│  Template: "job-search"                       │
│                                               │
│  Automatically created:                       │
│  • Project scope: job applications, outreach, │
│    interview prep, offers                      │
│  • Suggested tasks:                           │
│    ☐ Set up application tracker               │
│    ☐ Update resume and portfolio              │
│    ☐ Research target companies                │
│    ☐ Set up weekly review nudge               │
│  • Memory scope: career-related facts         │
│  • Calendar link: interview scheduling        │
│                                               │
│  Name: [Spring 2026 Job Search        ]       │
│                                               │
│  [Create project]  [Customize template]       │
└──────────────────────────────────────────────┘

Available templates:
- "job-search": Application tracker, outreach log, interview prep
- "home-project": Checklist, budget, timeline, document tracker
- "learning-topic": Curriculum, resources, practice exercises, quiz log
- "health-track": Metrics, appointments, medication, notes
- "blank": Empty project, no pre-filled tasks
```

**Implementation type:** Action (`kitty_create_project`) + Rich UI form card
**Estimated complexity:** ~60 lines (Action sends template selection to Gateway project creation endpoint)
**Dependencies:** Gateway project creation with template support (project model exists; needs template definitions)
**Kitty or Open WebUI:** Open WebUI Action. Gateway owns the project model and templates.
**Why it's #34:** Bootstrap for new projects. Saves Jacob from recreating the same project structure. Low immediate value since projects are created rarely.

---

### 35. Image Feed

**Rank:** #35 of 38.

**Problem:** Generated images exist in the artifact store but have no browsing surface in Open WebUI.
Jacob can't scroll through recent images, favorite them, or see generations in progress.

**User experience:**
```
Tool: "Show me my recent images"

┌──────────────────────────────────────────────┐
│  🎨 Image Feed — 12 images                     │
│  ────────────────────────────────────────     │
│                                               │
│  [img1] [img2] [img3] [img4]                  │
│  "cyberpunk cat"  "space station"  ...        │
│                                               │
│  [img5] [img6] [img7] [img8]                  │
│  "dragon"  "samurai"  "blue"  "mountain"      │
│                                               │
│  Generating...                                 │
│  ⏳ "wizard tower at sunset" · 45%            │
│                                               │
│  Favorited (3)                                 │
│  [img1] [img5] [img[9]]                        │
│                                               │
│  [Open Image Studio]  [Generate new]          │
└──────────────────────────────────────────────┘

Each thumbnail expands to full view with:
- Full image
- Prompt, seed, model, generation time, cost
- Parent image (for edits)
- Variations button
- Add to favorites / download / share
```

**Implementation type:** Tool (`kitty_image_feed`) + Rich UI image gallery card
**Estimated complexity:** ~100 lines (Tool queries Gateway artifact registry for image artifacts, renders thumbnail grid)
**Dependencies:** Gateway artifact registry with image artifacts (product architecture Phase 3 — defined, not yet built), Image Studio pipeline (issue #336)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns the artifact registry.
**Why it's #35:** Depends on Image Studio being built first (issue #336). After that, this is a thin gallery card. Delightful once images exist.

---

### 36. Search Across Everything

**Rank:** #36 of 38.

**Problem:** Jacob's data is scattered — chats, memories, captures, journal entries, Builder
results, artifacts, project notes. When he wants to find something ("what was that article
about React Server Components?"), he doesn't know which store has the answer.

**User experience:**
```
Jacob: "Search everything for 'React Server Components'"

┌──────────────────────────────────────────────┐
│  🔍 Results for "React Server Components"      │
│  ────────────────────────────────────────     │
│                                               │
│  Memories (2)                                  │
│  • "RSC runs on the server by default"        │
│    from Tutor session, July 28                 │
│    [Open in context]  [See source chat]        │
│  • "Next.js App Router uses RSC as default"   │
│    from code review, July 30                   │
│    [Open in context]  [See source chat]        │
│                                               │
│  Chat History (3)                              │
│  • "Explain React Server Components"           │
│    July 28 · 24 messages · with Tutor         │
│    [Open conversation]                         │
│  • "Fix RSC hydration error in kitty-chat"    │
│    July 30 · 8 messages · with Coding         │
│    [Open conversation]                         │
│                                               │
│  Captures (1)                                  │
│  • "Watch RSC deep dive video"                │
│    Captured July 29 · unprocessed             │
│    [Open capture]                              │
│                                               │
│  Builder Results (0)                           │
│  No Builder packets match.                    │
│                                               │
│  [Search again]  [Filter by type]             │
└──────────────────────────────────────────────┘
```

**Implementation type:** Tool (`kitty_search_everything`) + Rich UI card with result grouping
**Estimated complexity:** ~100 lines (Tool queries Gateway unified search endpoint; Gateway federates across all stores)
**Dependencies:** Gateway unified search across memory, chats, captures, journal, Builder, artifacts (does not exist — each store has its own search)
**Kitty or Open WebUI:** Open WebUI Rich UI card. Gateway owns the federated search.
**Why it's #36:** Useful but complex. Federated search across heterogeneous stores is hard to get right. Build the individual exploration tools first, then unify.

---

### 37. Session Bookmarks

**Rank:** #37 of 38.

**Problem:** Long conversations have important moments — a key insight, a decision, a code
snippet Jacob wants to return to. Finding them later requires scrolling through the entire
conversation history. There's no way to mark a moment.

**User experience:**
```
On any message, Action button: "Bookmark this"

┌──────────────────────────────────────────────┐
│  🔖 Bookmarked                                 │
│  ────────────────────────────────────────     │
│                                               │
│  "The SSE stream terminates correctly but the │
│   verifier expects [DONE] as a separate event  │
│   while the Gateway emits it inline"           │
│                                               │
│  From: Chat "Fix streaming smoke test"        │
│  July 30, 10:15 AM                            │
│  Label: [Streaming fix diagnosis    ]         │
│                                               │
│  [Add note...]  [Done]                        │
└──────────────────────────────────────────────┘

Later, Tool: "Show me my bookmarks"

┌──────────────────────────────────────────────┐
│  🔖 Bookmarks — 7 items                        │
│  ────────────────────────────────────────     │
│                                               │
│  • "Streaming fix diagnosis" · July 30        │
│    [Jump to message in chat]                  │
│  • "ADR 0027 key quote" · July 29             │
│    [Jump to message in chat]                  │
│  • "Kitty architecture four spines" · Jul 28  │
│    [Jump to message in chat]                  │
│                                               │
│  [Remove]  [Export bookmarks]                 │
└──────────────────────────────────────────────┘
```

**Implementation type:** Action (`kitty_bookmark`) on messages + Tool (`kitty_get_bookmarks`) + Rich UI card
**Estimated complexity:** ~70 lines (Action saves message ref to Gateway bookmark store, Tool lists them)
**Dependencies:** Gateway bookmark store (simple key-value or SQLite table — new, small)
**Kitty or Open WebUI:** Open WebUI Action + Rich UI card. Gateway owns the bookmark store.
**Why it's #37:** Nice to have. Saves scrolling. But Jacob's sessions already produce durable insights via the Capture and Remember Actions. Bookmarks are a lighter-weight alternative.

---

### 38. Offline Queue Visibility

**Rank:** #38 of 38.

**Problem:** When offline, messages queue locally. There's no visible indicator of queued state,
no way to see what's pending, no way to cancel a queued message. The queue is invisible and
unmanageable.

**User experience:**
```
When offline, the chat input shows queued state:

┌──────────────────────────────────────────────┐
│  🔴 Offline — 2 messages queued                │
│  ────────────────────────────────────────     │
│                                               │
│  "What's on my calendar today?"                │
│  Queued at 10:15 AM · Will send when online   │
│  [Send now (retry)]  [Cancel]                 │
│                                               │
│  "Show me the open PRs"                        │
│  Queued at 10:16 AM · Will send when online   │
│  [Send now (retry)]  [Cancel]                 │
│                                               │
│  Messages will send automatically when         │
│  Gateway is reachable. Chats are saved         │
│  locally.                                      │
│                                               │
│  [Retry all]  [Cancel all]                    │
│                                               │
│  ────────────────────────────────────────     │
│  [New message...                       ] [▶]  │
└──────────────────────────────────────────────┘

When connectivity returns:
- Queue drains in order
- Each sent message shows a confirmation
- Failed sends surface with retry option
- No message is silently dropped
```

**Implementation type:** Rich UI queue widget overlaid on the chat input area, powered by a client-side queue state
**Estimated complexity:** ~100 lines (Client-side queue state + Rich UI widget; Open WebUI may already have partial offline support)
**Dependencies:** Client-side message queue (Open WebUI may already support this), Gateway reconnection detection
**Kitty or Open WebUI:** Primarily Open WebUI client-side. Gateway provides the health endpoint for connectivity detection.
**Why it's #38:** Important for data integrity (never pretend a message was sent when it wasn't). But offline use is rare when Kitty runs locally on Jacob's machine. Last-ranked because the problem it solves is unlikely.

---

## Extension Type Distribution

| Type | Count | Extensions |
|---|---|---|
| **Event Function** | 6 | One Thing (#1), Morning Briefing (#2), Quick Command Bar (#11), Weekly Retrospective (#12), Signal Feed (#19), Session Insight Prompt (#13) |
| **Filter** | 7 | Honest State Header (#7), Notification Center (#21), Rich Tool Call Display (#28), Input Sanitizer (#29), Model Routing Card (#30), Recovery Mode Indicator (#31), Prompt Library (#33) |
| **Rich UI** | 17 | Activity River (#4), Builder Mission Center (#5), Capture Inbox Widget (#6), Project Cockpit (#8), Memories Browser (#9), Deadline Radar (#10), Daily Review (#14), One-Tap Delegate (#15), Cost Monitor (#17), System Health Dashboard (#18), Evidence Browser (#22), Learning Board (#26), Life Dashboard (#27), Memory Staleness Queue (#32), Image Feed (#35), Search Across Everything (#36), Offline Queue Visibility (#38) |
| **Tool** | 8 | Resume Loop (#3), Expert Swarm Panel (#20), Knowledge Graph Browser (#25), Decision Log (#24), Voice Memo Capture (#23), Image Studio Command (#16), Session Bookmarks (#37), Project Templates (#34) |
| **Action** | 5 | Session Insight Prompt (#13), Daily Review (#14), One-Tap Delegate (#15), Expert Swarm Panel (#20), Session Bookmarks (#37) |
| **MCP** | 1 | Image Studio Command (#16 — MCP server for image generation) |
| **Pipe** | 0 | (All routing logic stays in Gateway — no new Pipes needed beyond the auto-router in the product plan MVP) |

Many extensions use multiple extension types in combination (e.g., a Tool that returns a Rich UI card, or an Action that triggers a Tool). The count above assigns each to its primary type.

---

## Wire Protocol

Every extension follows the same data flow:

```
User action/event → Extension handler → Gateway endpoint → Gateway logic → Response → Rich UI card
```

The extension handler is thin (30–180 lines). It:
1. Receives the trigger (event, message, button click, tool call)
2. Calls the Gateway endpoint with the relevant context
3. Receives the structured response
4. Renders it as a Rich UI card or injects it into the prompt

The Gateway endpoint is the authoritative source. The extension never:
- Makes routing decisions
- Decides what to remember or forget
- Claims success without an execution receipt
- Joins Builder's SQLite tables
- Creates a second truth path for any Kitty-owned concept

---

## Dependency Map

Extensions that Gateway already has endpoints for (rank higher):
- #1 One Thing: `/state/next` projection (product architecture defined, needs implementation)
- #2 Morning Briefing: `/state/brief` projection (product architecture defined)
- #3 Resume Loop: `/state/resume` projection (product architecture defined)
- #4 Activity River: Activity events (already exist in product architecture)
- #5 Builder Mission Center: `builder_status.py` (already implemented, bounded read-only projection)
- #6 Capture Inbox: Quick Capture endpoints (already exist)
- #9 Memories Browse: Memory graph search (already exists)
- #11 Quick Command Bar: Various Gateway endpoints (many exist)
- #18 System Health: `/health` and doctor endpoints (already exist)
- #19 Signal Feed: Signal store (already exists)
- #23 Voice Memo Capture: Quick Capture endpoint (already exists)
- #29 Input Sanitizer: Zero dependencies (pure client-side Filter)
- #30 Model Routing Card: Gateway response metadata (included in product plan MVP)

Extensions that need new Gateway intelligence (rank lower):
- #8 Project Cockpit: Project projection endpoint
- #10 Deadline Radar: Consolidated deadline extraction
- #12 Weekly Retrospective: Retrospective aggregation
- #14 Daily Review: Journal integration with activity pre-fill
- #15 One-Tap Delegate: Builder proposal endpoint + approval policy
- #16 Image Studio Command: Image pipeline (issue #336), artifact registry
- #17 Cost Monitor: Cost aggregation projection
- #20 Expert Swarm Panel: Expert swarm Gateway API
- #22 Evidence Browser: Execution receipt store
- #24 Decision Log: Decision store
- #25 Knowledge Graph Browser: Graph traversal endpoint
- #26 Learning Board: Topic aggregation from Tutor sessions
- #27 Life Dashboard: Unified project projections
- #35 Image Feed: Artifact registry with image artifacts
- #36 Search Across Everything: Federated search

---

## Build Order

### Already possible today (Gateway endpoints exist):
5, 6, 9, 11, 18, 23, 28, 29, 30, 31

### Possible after Capability Manifest (product architecture Phase 1):
1, 2, 3, 4, 7, 15, 17, 19, 21

### Possible after Product State (Phase 4):
8, 10, 12, 13, 14, 24, 25, 26, 27, 32, 33, 34, 36

### Possible after Image Studio (issue #336):
16, 35

### Possible after Builder integration (Phase 5):
20, 22

### Low dependencies, can build anytime:
28, 29, 30, 31, 37, 38

---

## What This Is Not

- **Not a rewrite of Open WebUI.** Every extension uses stock extension points. No fork.
- **Not a new intelligence layer.** Gateway owns all routing, memory, policy, and truth. Extensions are thin adapters.
- **Not the product plan.** The product plan (`OPENWEBUI_PRODUCT_PLAN.md`) defines the MVP extensions. This document defines the dream — everything that comes after the ~430-line MVP.
- **Not a builder of custom frontend.** The only custom UI is Rich UI cards inside conversations. The shell is pristine.
- **Not an AI operating system with custom desktop, window manager, or file system.** Kitty runs inside Open WebUI, which runs inside a browser. The extensions make the browser shell feel like an OS — but it's the browser doing the rendering.
- **Not a replacement for human decision-making.** Every extension with write capability (Builder delegation, memory correction, task creation) requires confirmation or approval. The One Thing card says "Draft a follow-up email?" — it doesn't draft and send without Jacob's input.

---

## The Morning That Justifies It All

```
08:00 — Jacob opens Kitty Chat from his Desktop shortcut.

Not an empty chat box. Not a list of old conversations.

┌──────────────────────────────────────────────────────────┐
│  Good morning, Jacob.                                      │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Follow up on Acme Corp application                  │   │
│  │  Sent resume July 28 · no reply in 6 days           │   │
│  │  [Let's do it]                                      │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  While you were away:                                     │
│  • Builder merged the test fix (1 file, 8 lines, 3 tests)│
│  • 3 captures from phone are in your inbox                │
│  • W-2 benefits form is now 4 days overdue                │
│                                                           │
│  [See all activity]  [Open inbox]  [View Builder]         │
└──────────────────────────────────────────────────────────┘

08:01 — Jacob taps "Let's do it."
Kitty opens the job search project, loads the Acme Corp context,
remembers the recruiter prefers email, drafts the follow-up in the
conversation. Jacob reviews and approves.

08:05 — "Also, show me my inbox."
Three captures appear. "Book dentist" → task. "Research insurance" →
task. "Call mom" → nudge for 6 PM. All processed in 90 seconds.

08:07 — Jacob switches to coding. "/project kitty"
Context switches. Builder Mission Center shows: 1 active packet,
1 queued, the test fix merged overnight. Cost card: $0.04 today.

08:08 — "What's the next thing I should work on in the codebase?"
Kitty checks Builder state, open issues, active PRs, and the
roadmap. "The launcher contract outcome 0.5 is next. Want me to
diagnose the IPv4/IPv6 binding issue?" → "Yes."

09:00 — Jacob leaves for the day.

22:00 — Jacob opens Kitty on his phone.
"Today: drafted 1 email, processed 3 captures, Builder worked on
the launcher fix, 4 things remembered."

"Tomorrow: follow up on TechCorp response. And deal with that W-2 form."

Kitty remembers. Phone goes dark.
```

---

## Authority and Supersession

This document:
- **Implements:** Constitution v1, ADR 0027 (Open WebUI shell boundary), ADR 0028 (commodity precedence), OPENWEBUI_PRODUCT_PLAN.md (extension model), KITTY_PRODUCT_ARCHITECTURE.md (four-spine architecture).
- **Is superseded by:** A future ADR that explicitly revises the Open WebUI extension surface.
- **Does not override:** The Constitution, any ratified ADR, the Gateway code (live truth beats written plan), or the OPENWEBUI_PRODUCT_PLAN.md (which defines the MVP — this document extends to the dream).
- **Implementation:** No extension here may be built before the MVP extensions in the product plan are shipped and verified. After MVP, build in ranked order — S-tier first.

---

## Appendix: Extension Building Blocks

Every Rich UI card shares a common structure:

```json
{
    "type": "rich_ui",
    "data": {
        "type": "card",
        "title": "Card Title",
        "icon": "emoji_or_icon_ref",
        "content": "Markdown body with structured information",
        "sections": [
            {"heading": "Section", "body": "Content", "state": "ok|warning|error|info"}
        ],
        "actions": [
            {"label": "Button text", "action": "action_name", "style": "primary|secondary|danger"}
        ],
        "footer": "Last updated: 2 minutes ago",
        "collapsible": true,
        "auto_refresh": "30s"
    }
}
```

Every extension follows the Constitution's prime directive:
- Fail loud, never mask
- Evidence before claims
- Honest state — `unavailable` is not `unknown`, `stale` is not `current`
- Gateway owns all intelligence; the shell only renders

Every extension respects the approval classes:
- **Auto:** Read-only operations, health probes, context retrieval
- **Notify:** Create reversible items, save artifacts, queue approved-scope work
- **Approve:** Write to secrets, push/merge, delete, spend money, external messages
- **Refuse:** Credential exfiltration, unverifiable authority, unsafe requests

Every extension obeys life-first ordering:
- Job search, benefits, education outrank code projects
- Deadlines involving real-world consequences outrank all Builder packets
- The One Thing card always presents the life-first item first
