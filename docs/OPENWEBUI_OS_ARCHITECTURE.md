# Open WebUI OS Architecture

**Date:** 2026-08-05
**Status:** Research recommendation — not an ADR. Open WebUI is the primary supported UI with technically replaceable contracts per ADR 0027, ADR 0033, Constitution I.2, and ARCHITECTURE_RATIFICATION_2026-08-06.md Decision 1. This document's architectural decomposition and plugin strategy are valuable inputs; the "permanent UI component" framing is rejected by the ratification.
**Companion document:** `docs/reference/OPENWEBUI_ECOSYSTEM_SURVEY.md`

## Summary

If Kitty were started today knowing everything that already exists:

- We would **adopt** Open WebUI as the permanent user interface layer.
- We would **retain** Kitty Gateway as the intelligence, routing, and truth layer.
- We would **retain** KittyBuilder as the execution engine and evolve it into a general workspace operator.
- We would **delete** `gateway/kitty-chat/` (or demote it to a cold fallback).
- We would **move** Notes, Tasks, Memory, Calendar, and chat orchestration out of Kitty into Open WebUI native features.
- We would **build** ~500-700 lines of custom code: a Home page, a Builder bridge, a morning briefing, and proactive nudges — all as Open WebUI plugins (no fork, no frontend rebuild).

The result: Kitty becomes a few hundred lines of unique code on a platform maintained by thousands. Open WebUI fixes 85% of what we'd otherwise have to build and maintain ourselves forever.

## The architectural principle

```
Open WebUI owns the user experience. Kitty owns intelligence, orchestration, and truth.
```

Every capability assignment in this document is derived from this principle. If a capability is about what the user sees, types into, or touches — it belongs to Open WebUI. If it's about what the system thinks, decides, verifies, or guarantees — it belongs to Kitty.

## The mental model

Think of it like a computer:

| Layer | What it is | In our architecture |
|---|---|---|
| Desktop environment | The surface you see: windows, dock, Finder, apps | Open WebUI |
| Operating system kernel + daemons | What makes decisions: scheduling, memory, truth about what's running | Kitty Gateway |
| Package manager + job scheduler | What installs, maintains, and runs things in the background | KittyBuilder |
| Applications | Purpose-built tools users interact with | Open WebUI plugins, tools, and model presets |
| Drivers / protocol bridges | How things connect to the outside world | MCP servers, OpenAPI endpoints |

This is not a metaphor. It's the literal architecture. Open WebUI is the desktop. Kitty is the OS underneath.

## Permanent responsibility boundaries

### Open WebUI (permanent — never build these in Kitty)

| Responsibility | How it's delivered | Why it stays here |
|---|---|---|
| Chat interface | Built-in core | Commodity. The community maintains this forever. |
| Conversation management (threads, folders, tags, pins, search) | Built-in core | Solved. Would be hundreds of hours to rebuild. |
| Multi-model chat (side-by-side comparison) | Built-in | Zero code. |
| Model picker and model presets | Workspace → Models | Users compose agents here. Kitty exposes presets via Gateway. |
| Notes (rich editor, AI enhance, context injection) | Built-in | Replaces Kitty's note/scratchpad surface. |
| Memory (cross-conversation facts) | Built-in Persistent Memory | Working context for daily use. |
| Tasks (structured checklists with status tracking) | Built-in / Tools | Personal productivity. |
| Calendar (month/week/day, recurring, reminders) | Built-in | Replaces any Kitty calendar surface. |
| Knowledge bases and RAG | Built-in Workspace → Knowledge | Document retrieval surface. |
| Community plugin marketplace | openwebui.com | One-click install for tools, skills, prompts, functions. |
| MCP server connections | Admin → External Tools → MCP | Protocol gateway. Admin adds once, scoped to users. |
| Open Terminal (real code execution) | Built-in | Sandboxed execution visible in chat. |
| Image generation surface | Built-in (DALL-E, Gemini, ComfyUI) + community tools | Kitty's Image Lab contracts route through here. |
| Automations (scheduled prompt runs) | Built-in | Scheduled recurring work with calendar integration. |
| Channels (multi-AI shared spaces) | Built-in | @model tagging, threads, reactions. |
| Desktop app (Spotlight, voice, screenshots) | Official native desktop app | Global hotkey, drag-to-screenshot, push-to-talk. |
| File browser | Built-in sidebar in Open Terminal | Browse, upload, download, edit. |
| Artifact / visualization viewer | Classic298 Inline Visualizer v2 | Charts, dashboards, D3, Plotly inline in chat. |
| Weather display | Community tool (iChristGit/Haervwe) | One-click install. |
| RSS / news reader | Community tool (iChristGit News Reader) | 45 feeds, 11 categories, AI summaries. |
| YouTube / Reddit / Podcast browsing | Community tools (iChristGit) | Native-quality browsing in chat. |
| Email composition | Community tool (Classic298 Email Composer) | AI drafting with rich UI. |
| User authentication / identity | Built-in RBAC, SSO/OIDC | Multi-user if ever needed. |
| Analytics / usage dashboard | Built-in administration | Message volume, token consumption, cost. |

### Kitty (permanent — never delegate these to Open WebUI)

| Responsibility | Why it stays here | Where it lives |
|---|---|---|
| Builder execution engine | Packets, leases, queues, attempts, gates, PRs, worktrees — this is a governance machine, not a chat feature. | `gateway/` + `data/kittybuilder/` |
| Provider routing intelligence | Cost-aware model selection, retry logic, circuit breaking, fail-loud guarantees. Open WebUI sees "Kitty Auto/Fast/Think/Code/Vision" as models. Kitty Gateway decides which actual provider to use. | `gateway/` → LiteLLM proxy → actual providers |
| Cost tracking | Actual token counts and computed dollar cost per request. Kitty writes; Open WebUI displays via read-only projection. | `gateway/` cost tracking module |
| Evidence and verification discipline | File:line proof, runtime evidence, "didn't just claim it." Kitty's fail-loud identity. | `gateway/` verification + Builder evidence |
| Durable KB (~/kb) | Verified, indexed, cross-session learning. Distinct from Open WebUI Memory (working context). KB is truth; Memory is convenience. | `~/kb/` (filesystem + index) |
| Skills library (agent operational procedures) | How agents operate (PR creation, session-end protocol, verification), not how models answer prompts. | `.agents/skills/` |
| Session handoff protocol | STATE.md, HANDOFF.md, context receipts. Kitty's continuity architecture. | `.claude/` |
| ADR / governance records | Architectural decisions. | `docs/adr/` |
| Fail-loud guarantees | No silent fallbacks, no fabricated completeness, no swallowing errors. | All Kitty components |
| Git / worktree / repo-aware execution | KittyBuilder's code change machinery. | Builder + worktrees |
| Tutor curriculum and assessment | What to learn, in what order, and how to verify — not the chat surface for tutoring. | `gateway/` Tutor module |
| Image Lab contracts | Which ComfyUI workflows, which models, parameter boundaries. Surface is Open WebUI; contracts are Kitty. | `gateway/` Image Lab contracts |
| Capture / inbox | The durable inbox (#270 capture → return → respond loop). | `gateway/` capture module |

## What moves out of Kitty into Open WebUI plugins

These are things Kitty currently does that Open WebUI already does better, or that community plugins handle. They should be **removed** from Kitty's codebase and **adopted** from Open WebUI instead.

| Kitty capability | Moves to Open WebUI... | Status |
|---|---|---|
| Chat client UI (kitty-chat/) | Built-in chat interface | Retire kitty-chat as a development-only cold fallback |
| Notes surface | Built-in Notes | Already more capable than Kitty's notes |
| Task management | Built-in Tasks + Automations | Structured checklists, scheduling |
| Calendar surface | Built-in Calendar | Recurring events, reminders |
| Memory (working context) | Built-in Persistent Memory | Already active in current configuration |
| Web search surface | Built-in web search + community pipes (Perplexica) | Already active |
| Image generation UI | Built-in image gen + community ComfyUI tools | Already active |
| Model switching / comparison | Built-in multi-model chat | Already active |
| Conversation organization (folders, tags) | Built-in folders, tags, pins | Already active |

## What becomes standalone services (shared between Kitty and Open WebUI)

| Service | Kitty's role | Open WebUI's role | Protocol |
|---|---|---|---|
| MCP servers (GitHub, Google, Playwright, etc.) | Workers connect to MCP servers during execution | Admin adds MCP servers; chat uses them via tools | MCP Streamable HTTP |
| Cost tracking database | Kitty Gateway writes token counts and computed cost per request | Open WebUI reads via API or displays in analytics | REST API (read-only) |
| Builder state projection | KittyBuilder writes execution truth to its database | Open WebUI reads projectable status (initiatives, packet status, lane links) | REST API (read-only, bounded) |
| Knowledge bases (documents for RAG) | Kitty feeds documents (KB, project docs) into knowledge sync | Open WebUI indexes and retrieves via RAG | oikb for sync; vector DB for retrieval |
| LiteLLM proxy | Kitty Gateway routes through it with policy | Open WebUI connects to Gateway (not directly to LiteLLM) | OpenAI-compatible API |

## What disappears

| Component | What it was | Why it goes | What replaces it |
|---|---|---|---|
| `gateway/kitty-chat/` (Next.js frontend) | Kitty's custom chat UI | Maintenance burden, never matched Open WebUI quality, source of frustration | Open WebUI (built-in chat + configured model presets) |
| Kitty's notes API surface | Notes management endpoints in Gateway | Open WebUI Notes is better | Open WebUI Notes (native) |
| Kitty's task management API | Task CRUD in Gateway | Open WebUI Tasks is better | Open WebUI Tasks (native) |
| Kitty's calendar API | Calendar endpoints in Gateway | Open WebUI Calendar is better | Open WebUI Calendar (native) |
| Kitty's conversation organization | Custom chat folders/tags | Open WebUI does this natively | Open WebUI folders, tags, pins |
| Kitty's model picker | Custom model selection UI | Open WebUI does this better | Open WebUI model picker + Gateway-provided presets |
| Any duplicate of what Open WebUI provides natively | — | Redundant maintenance | Open WebUI |

## Capability-by-capability assignment

For every named capability in the current Kitty product architecture plus the new desired capabilities, here is where it lives in the new architecture:

| Capability | Owner | Implementation | Custom code? |
|---|---|---|---|
| Home / Resume Loop | Open WebUI | Event Function serving route at `/home`: weather tile, tasks, recent notes, memory summary, Builder status, briefing. Clickable tiles deep-link into relevant surfaces. | Yes (~200-400 lines) |
| Morning briefing | Open WebUI | Automation (scheduled prompt) + Filter (context injection). Collects tasks, calendar, memory, weather, RSS into synthesized greeting. | Yes (~100 lines) |
| Dashboard | Open WebUI | The Home page IS the dashboard. | See Home / Resume Loop |
| Weather | Open WebUI | iChristGit/Haervwe community tool (OpenWeatherMap). Data read by Home page. | No (community tool) |
| Tasks | Open WebUI | Built-in Tasks (create_tasks, update_task). Native function calling. | No (built-in) |
| Memory (working) | Open WebUI | Built-in Persistent Memory. Cross-conversation facts. | No (built-in) |
| Memory (durable KB) | Kitty | ~/kb/ filesystem + index. Verified learning. Distinct from working memory. | Existing (Kitty) |
| Notes | Open WebUI | Built-in Notes. Rich editor, AI enhance, context injection. | No (built-in) |
| Projects (tracking) | Open WebUI | Notes + Tasks organized by project. Project knowledge in Knowledge bases. | No (built-in + config) |
| Projects (execution) | Kitty | Builder initiatives, packets, worktrees. Read-only projection into Open WebUI. | Existing (Kitty) |
| Image Studio (surface) | Open WebUI | Built-in image gen + Haervwe/iChristGit ComfyUI tools. | No (built-in + community) |
| Image Studio (contracts) | Kitty | Gateway routing rules: which models/backends for which image requests. | Existing (Kitty) |
| Builder (execution) | Kitty | Packets, leases, attempts, gates, PRs, worktrees. | Existing (Kitty) |
| Builder (bridge to UI) | Open WebUI | Custom Tool: "Submit to Builder" → calls Kitty API, returns lane link. | Yes (~100 lines) |
| Tutor (surface) | Open WebUI | Model preset with Tutor instructions, bound to knowledge bases. | No (config) |
| Tutor (curriculum) | Kitty | What to learn, in what order, how to assess. | Existing (Kitty) |
| Skills (model instructions) | Open WebUI | Workspace → Skills. Markdown instruction sets for models. | No (built-in) |
| Skills (agent procedures) | Kitty | .agents/skills/. How agents operate (PR creation, verification, session-end). | Existing (Kitty) |
| MCP (connection surface) | Open WebUI | Admin → External Tools → MCP. Admin adds servers, scopes to users. | No (built-in) |
| MCP (worker access) | Kitty | Builder workers connect to same MCP servers during execution. | Existing (Kitty) |
| Automations | Open WebUI | Built-in Automations. Scheduled prompts, calendar integration. | No (built-in) |
| Notifications (system) | Open WebUI | Built-in webhooks + Event Functions. | No (built-in) |
| Notifications (proactive surprises) | Open WebUI | Event Function: periodic check for "task X idle 3 days" or "PR Y approved." Scoped to never nag. | Yes (~100 lines) |
| Background agents | Kitty | Builder workers. Long-running agent processes in worktrees. | Existing (Kitty) |
| Artifact viewer | Open WebUI | Classic298 Inline Visualizer v2. Charts, dashboards, D3 in chat. | No (community tool) |
| Provider routing | Kitty | Gateway → LiteLLM → actual providers. Cost-aware, fail-loud. | Existing (Kitty) |
| Cost tracking | Kitty (writes) | Gateway collects token counts + computed cost per call. Stores in DB. | Existing (Kitty) |
| Cost display | Open WebUI (reads) | Built-in analytics or Home page integration via read-only API. | No (built-in) |
| Long-running jobs | Kitty | Builder execution engine. Packet lifecycle management. | Existing (Kitty) |
| Long-running job status | Open WebUI | Read-only projection from Builder into Home page or chat tool. | No (read-only projection exists) |
| Chat / conversations | Open WebUI | Built-in core. | No (built-in) |
| Knowledge bases / RAG | Open WebUI | Built-in Workspace → Knowledge. | No (built-in) |
| Browser automation | MCP server shared | Playwright MCP server. Connected to both Open WebUI (user-facing) and Kitty workers (execution). | No (MCP server) |
| GitHub integration (user-facing) | MCP server + Open WebUI | GitHub MCP server → Open WebUI chat tools. | No (MCP server) |
| GitHub integration (worker-facing) | MCP server + Kitty | Same MCP server → Kitty Builder workers. | Existing (Kitty) |
| Google services (Gmail/Calendar/Drive) | MCP server + Open WebUI | Google MCP server → Open WebUI chat tools. | No (MCP server) |
| RSS | Open WebUI | iChristGit News Reader community tool. | No (community tool) |
| Desktop launcher | Open WebUI | Official desktop app (Spotlight: Shift+Cmd+I, voice, screenshots). | No (built-in) |
| Reddit / YouTube / Podcasts | Open WebUI | iChristGit community tools. | No (community tools) |

## Builder's evolution: from coding execution engine to workspace operator

### Today

Builder executes coding work: take a packet → checkout worktree → run agent → verify → publish PR. This is correct and should remain. But it's narrow.

### Proposed

Builder becomes the general **workspace operator** — it maintains the entire AI workspace, not just the codebase.

This is a natural generalization of existing abstractions. Builder already has:

- Initiatives (what we're trying to accomplish)
- Packets (units of work)
- Queue (what's next)
- Leases (exclusive ownership, no conflicts)
- Attempts (what was tried, succeeded, or failed)
- Gates (review, approval, verification)
- Publication rails (making changes live: PRs today)

These abstractions apply to **any** kind of work. The change is what a packet can contain and how it publishes.

### New packet types

| Type | Example | Execution strategy | Publication mechanism |
|---|---|---|---|
| `code_packet` (existing) | "Fix bug in memory module" | Git worktree → agent → verify → tests | PR (existing) |
| `config_packet` (new) | "Install the weather tool" | Call Open WebUI marketplace API → verify tool appears in workspace | Verification checklist |
| `integration_packet` (new) | "Configure Google MCP server" | Call Open WebUI Admin API → add MCP server → verify connection | Verification checklist |
| `maintenance_packet` (new) | "Prune old conversations and orphaned files" | Run prune tool → verify DB size reduced → report | Health report |
| `improvement_packet` (new) | "Evaluate new community RSS tool, install if better than current" | Install candidate tool → A/B test → keep or rollback | Recommendation + installation evidence |

### What Builder would own as workspace operator

1. **Plugin lifecycle:** install, update, evaluate, and remove Open WebUI community tools, functions, filters, skills, and prompts.
2. **MCP server management:** add, configure, verify, and update MCP server connections via Open WebUI's Admin API.
3. **Integration wiring:** ensure services (Kitty Gateway, LiteLLM, Open WebUI, MCP servers) are correctly connected and healthy.
4. **Workspace maintenance:** periodic pruning, cleanup, backup, and health checks.
5. **Capability improvement:** proactively evaluate new community plugins, suggest upgrades, install if verified better.
6. **Agent coordination:** dispatch specialist agents for non-code tasks (research, planning, review) with the same lease/gate/attempt discipline.

### What does NOT change

- Builder's existing code execution pipeline (packets → worktrees → PRs). That stays exactly as it is.
- The lease/attempt/gate/evidence discipline. That's Builder's core value and applies to all packet types.
- The read-only projection boundary. Open WebUI never writes Builder state.
- The ADR 0017 boundary: Kitty owns intent; Builder owns execution.

### Significance

This evolution means Builder stops being "the coding robot" and becomes "the operator that keeps the entire AI workspace healthy and improving." The user opens Open WebUI every morning to a home that's a little better than yesterday — because Builder worked on it overnight.

It also means Builder can install and configure Open WebUI's extensions itself, which closes the loop: the "starter pack" from the ecosystem survey becomes something Builder can execute, not just something the user follows manually.

## What we'd build from scratch

If Kitty were started today:

| We'd build | Why | Lines |
|---|---|---|
| Kitty Gateway (provider routing, cost tracking, fail-loud, Tutor, Image Lab contracts, capture/inbox) | Open WebUI connects to model providers but doesn't own routing policy, cost awareness, or fail-loud guarantees. This is Kitty's unique intelligence. | Existing |
| KittyBuilder (execution engine: packets, leases, gates, PRs, worktrees) | No existing platform does governed, verifiable, multi-attempt execution with evidence. This is Kitty's unique orchestration. | Existing |
| Durable KB (~/kb) | Verified, indexed, cross-session learning. Distinct from chat memory. No platform provides this. | Existing |
| Agent skills library (.agents/skills/) | Procedural instructions for how agents operate. Distinct from Open WebUI Skills (which teach models how to answer). | Existing |
| Session handoff protocol (STATE.md, HANDOFF.md) | Context continuity across sessions. No platform provides this. | Existing |
| Home page (Open WebUI Event Function) | The welcome-home dashboard. The reason you open it. | ~200-400 new |
| Builder bridge (Open WebUI Tool) | "Submit to Builder" from chat. Returns lane link. | ~100 new |
| Morning briefing (Open WebUI Automation + Filter) | Synthesized good-morning context injection. | ~100 new |
| Proactive nudges (Open WebUI Event Function) | "Task X idle for 3 days" — polite, never nags. | ~100 new |

**We would NOT rebuild:**
- Chat interface → Open WebUI
- Notes → Open WebUI
- Tasks → Open WebUI
- Calendar → Open WebUI
- Memory (working) → Open WebUI
- Knowledge bases / RAG → Open WebUI
- Image generation surface → Open WebUI
- MCP connection surface → Open WebUI
- Plugin marketplace → Open WebUI
- Desktop app / launcher → Open WebUI
- Model picker → Open WebUI
- Conversation management → Open WebUI
- Automations → Open WebUI
- File browser / terminal → Open WebUI
- Analytics → Open WebUI
- Everything else the ecosystem survey shows already exists

## ADR cross-reference

| ADR | Relationship to this architecture |
|---|---|
| 0017 (Mission → Builder control plane) | Unchanged. Kitty owns intent; Builder owns execution. This architecture reinforces that boundary — Builder just gets broader execution types. |
| 0027 (Open WebUI as replaceable shell) | **To be superseded.** This architecture proposes Open WebUI as the *permanent* UI component, not a replaceable shell. The replaceability principle narrows to: "Kitty's contracts must remain independent enough that a future shell replacement is possible without rewriting Kitty." |
| 0015 (Resume loop and Builder boundary) | The Resume Loop moves into Open WebUI (Home page + Continuity preset). Builder stays read-only from the UI surface. |
| 0011 (Privacy boundary in LLM router) | Kitty Gateway remains the routing boundary. Open WebUI never sees raw provider credentials. |
| 0003 (Gateway is the product) | Strengthened. The Gateway is the only product. Open WebUI is the adopted surface. |

## What this architecture is NOT

- **Not a rewrite.** Builder's core abstractions don't change. Gateway doesn't change. Open WebUI doesn't change. We delete things (kitty-chat), move things (notes, tasks, memory), and build ~500-700 lines of new plugin code.
- **Not a coupling decision.** Open WebUI remains externally maintained. Kitty never forks it or embeds business logic in it. The Extension Function/Pipe/Tool boundary is the seam.
- **Not a less-capable Kitty.** Kitty loses no unique capability. It gains a maintained surface, a plugin ecosystem, and a desktop app — all for zero maintenance cost.
- **Not a short-term optimization.** This architecture is designed to be correct five years from now. The principle (Open WebUI = UX, Kitty = intelligence + execution) doesn't depend on any specific community plugin or Open WebUI version.
