# Code Sniping Audit — 2026-06-18

## Goal

Find proven open-source assistant patterns Kitty can reuse before writing more custom code. The filter is strict: borrow only what shortens the path to daily use, especially the loop from capture to resurfacing.

## Current Kitty Seam

Kitty already has the right local API seam:

- `gateway/routes/desktop.py` exposes `GET /desktop/status`, `GET /desktop/inbox`, and `POST /desktop/capture`.
- `gateway/desktop_store.py` writes mobile-compatible JSONL entries to `data/inbox.jsonl`.
- Before this audit, `gateway/memory_graph.py` had no inbox adapter, so captures could be written but did not reliably resurface in brief/search/chat context.

This confirms the next product gap is not a new shell. It is: capture instantly, then make Kitty bring the capture back at the right moment.

## Repos Inspected

| Repo | License | What To Steal | What To Avoid |
|---|---:|---|---|
| `memex-lab/memex` | GPL-3.0 | Product model: raw fragments become typed timeline cards, insights, and exportable Markdown. Great vocabulary for capture → card → insight. | Do not paste code unless Kitty accepts GPL obligations. Do not import its mobile app or multi-agent platform. |
| `mblode/raycast-notes` | MIT | Tiny Raycast command shape: one text area, write/append, toast, done. Good stopgap for Quick Capture before Tauri. | Its recursive note search and markdown stripping are not needed for Kitty’s inbox. |
| `agentscope-ai/QwenPaw` | Apache-2.0 | `inbox_events` pattern: status, severity, read/unread, payload, bounded retention. Also useful backup progress and doctor extension patterns. | Its channel/plugin universe is too large for Phase 1. Avoid importing plugin architecture. |
| `Zackriya-Solutions/meetily` | MIT | Tauri tray/onboarding posture: tray state transitions, status menu, persist onboarding only after config succeeds. | Audio subsystem is far beyond Kitty’s current need. |
| `leon-ai/leon` | MIT | Principle: explicit tools, layered memory, grounded context, deterministic workflows before agentic execution. | Large Node/Python runtime and 2.0 transition are not worth adopting. |
| `Mirix-AI/MIRIX` | Apache-2.0 | Memory taxonomy vocabulary: core, episodic, semantic, procedural, resource, knowledge vault. Useful for naming later. | PostgreSQL/vector/multi-agent memory stack is overkill for one-user Kitty right now. |
| `Sylinko/Everywhere` | Business Source License | Learn from desktop/on-screen awareness and shortcut patterns only. | Do not copy code; license is unsuitable for Kitty sniping. |

## Sniping Philosophy

Do not confuse "avoid overbuilding" with "build boring product." Kitty has to feel alive enough that Jacob actually wants to use it. The right strategy is two-lane sniping:

- **Daily-use snipes:** small pieces that close the loop this week.
- **Awesome-Kitty snipes:** bigger product patterns we deliberately prototype once the loop is real.

The constraint is not ambition. The constraint is avoiding half-wired surfaces. A feature earns its place when it makes Kitty more present, more useful, or more emotionally sticky without making the runtime fragile.

## Daily-Use Snipes

### 1. Raycast Quick Capture Stopgap

Build a tiny Raycast script or extension that posts to `POST /desktop/capture`.

Why: this gets one-keystroke capture without waiting for Tauri/Rust. Raycast Notes proves the UX can be extremely small: open command, type, submit, toast. Kitty already has the backend endpoint.

Acceptance:

- Capture works while AI is down.
- Capture writes exactly the existing `data/inbox.jsonl` schema.
- Failure shows a plain toast and does not lose typed text.

### 2. InboxAdapter In `memory_graph.py`

Add a read-only adapter for recent `data/inbox.jsonl` captures.

Why: the hard-critic finding is still correct. A writer without a reader is a dead habit loop. Memex’s strongest product lesson is that fragments must become visible later.

Acceptance:

- `search_all()` includes an `inbox` key.
- `unified_context("morning brief")` can include recent unprocessed captures.
- Existing store failures remain isolated.

### 3. Inbox Events Layer, Not Inbox Mutation

Borrow QwenPaw’s separation between raw events and UI/status events.

Why: keep `data/inbox.jsonl` append-only and mobile-compatible, while adding a separate local status layer later for read/unread, resurfaced/dismissed, severity, and “distress signal handled.”

Phase 1 version:

- Do not build a full event system yet.
- Add only enough metadata in memory/search output to avoid marking raw captures processed too early.

### 4. Memex-Style Capture Classification, But Later

Use Memex’s card taxonomy as inspiration for a future processor:

- task
- event
- note/snippet
- person/place
- metric
- distress signal
- avoidance prompt

Phase 1 version: do not run a classifier. Let raw captures resurface in brief/chat first.

### 5. Tauri Tray Pattern, Only After Stopgap Proves Useful

Meetily’s tray code reinforces the right native shell shape:

- Menu state mirrors real runtime state.
- State changes immediately on user action.
- Errors revert state and log clearly.
- Onboarding/config is marked complete only after durable writes succeed.

Kitty should use this later for tray/status/quick capture, but only after Raycast/Hammerspoon proves capture is used.

## Recommended Next Slice

Build the smallest borrowed loop:

1. Done in this branch: add `InboxAdapter` to `gateway/memory_graph.py`.
2. Done in this branch: add tests proving captures appear in `search_all()` and `unified_context()`.
3. Next: add a tiny Raycast/Hammerspoon capture shim that calls `/desktop/capture`.
4. Next: run one real capture, then ask Kitty for a morning brief/search and confirm the capture resurfaces.

This is the right amount of theft: one UX pattern from Raycast Notes, one product loop from Memex, one status/data separation idea from QwenPaw, all mapped onto Kitty’s existing backend.

## Awesome-Kitty Snipes To Seriously Consider

These are not rejected. They are the features that could make Kitty feel less like a dashboard and more like a companion.

### 1. Memex-Style Timeline Cards

Steal the product pattern, not GPL code. Captures should eventually become beautiful, typed cards: task, event, avoidance, distress, repair note, money note, idea, person, place, metric.

Why it matters: a raw inbox is utilitarian; a timeline of interpreted life fragments feels magical.

Prototype trigger: after `InboxAdapter` proves captures resurface in brief/search.

### 2. Companion Auto-Commentary

Memex’s strongest emotional feature is characters reacting to new timeline cards. Kitty’s version: when a capture resurfaces, Kitty adds a short “I noticed this” comment in her own voice.

Why it matters: this creates the trust loop. Jacob captures more because Kitty visibly pays attention.

Prototype trigger: after three real captures exist in `data/inbox.jsonl`.

### 3. Screen-Aware Context, Carefully Sandboxed

Everywhere and MIRIX point at the same future: desktop assistants become dramatically better when they know what is on screen. Kitty should not start with continuous recording, but it should eventually support an explicit “look at this” or “what am I doing?” snapshot.

Why it matters: it turns Kitty from chatbox into work companion.

Guardrail: user-triggered only, no background screen capture until there is a clear privacy model and visible indicator.

### 4. Proactive Pulse

Leon and QwenPaw both point toward bounded proactivity. Kitty’s version should be tiny: if Jacob is idle, stuck, or has an unresolved distress/avoidance capture, Kitty can surface one gentle prompt.

Why it matters: a companion should occasionally meet Jacob halfway.

Guardrail: no notification spam; only one pending nudge type at a time.

### 5. Memory Taxonomy Upgrade

MIRIX’s taxonomy is too heavy to import, but its names are useful. Kitty can keep the lightweight adapter architecture while labeling memories as core, episodic, semantic, procedural, resource, or capture.

Why it matters: better memory UX without a giant memory rewrite.

Guardrail: labels first, migration later.

### 6. Native Shell That Earns Its Drama

Meetily’s Tauri tray patterns are worth stealing once capture is proven: tray state, quick capture, health, onboarding, and graceful errors.

Why it matters: the Mac should feel like Kitty lives there.

Guardrail: Tauri wraps a working loop; it does not create the loop.

## Rejected For Now

- Full mobile app: still premature.
- Full Tauri shell: useful later, but not before capture proves valuable.
- Background screen-watching assistant: high privacy and complexity cost. User-triggered screen-aware context remains worth prototyping later.
- Multi-agent memory expansion: attractive, but violates the “no new agent expansion” phase rule.
- Cloud sync/auth: explicitly out of phase.

## Source Trail

- Memex: https://github.com/memex-lab/memex
- Raycast Notes: https://github.com/mblode/raycast-notes
- QwenPaw: https://github.com/agentscope-ai/QwenPaw
- Meetily: https://github.com/Zackriya-Solutions/meetily
- Leon: https://github.com/leon-ai/leon
- MIRIX: https://github.com/Mirix-AI/MIRIX
- Everywhere: https://github.com/Sylinko/Everywhere
