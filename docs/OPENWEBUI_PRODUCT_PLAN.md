# Open WebUI Product Plan for Kitty

**Date:** 2026-08-05
**Authority:** Architectural. Governed by the Constitution (v1), ADR 0027 (Open WebUI shell boundary), ADR 0028 (commodity precedence).
**Status:** Product plan — no implementation. Defines what we build, what we don't, and the path from stock Open WebUI to Jacob's ideal AI home.

This document answers: *How do we turn stock Open WebUI into Jacob's ideal AI home while owning the absolute minimum custom code?*

---

## Product Design Rule

Every decision in this plan follows two rules:

1. **Open WebUI provides the commodity shell.** Chat, persistence, mobile, auth, file handling, model selection, attachments — these are done. We configure, we don't rebuild.
2. **Kitty Gateway provides the intelligence.** Routing, memory, projects, tools, approval, Builder, context assembly, personality — these are ours. Open WebUI receives them through stable Gateway contracts but never reimplements them.

When in doubt: configure stock Open WebUI before writing a Filter. Write a Filter before writing a Pipe. Write a Pipe before writing a Function. Write a Function before writing an MCP server. And never fork.

---

## 1. Everything Open WebUI Already Provides

These are capabilities we get for free by running stock Open WebUI. None of them require custom code, only configuration.

### Core shell (zero custom code)
- **Chat UI** — message threading, markdown rendering, code blocks with syntax highlighting, streaming response display, message editing, branching, deletion, scroll-to-bottom, typing indicators.
- **Model selection** — model picker dropdown with descriptions, per-conversation model override, system prompt per model, temperature/top-p/context-length sliders.
- **Attachments** — file upload (images, PDFs, documents, code), inline image rendering, file preview, multi-file support per message, drag-and-drop.
- **Persistence** — SQLite-backed chat history, conversation list with search, archive, pin, rename, delete, export.
- **Mobile/PWA** — responsive design, installable PWA, touch-optimized chat, works on phones and tablets.
- **Agents/Assistants** — named assistants with base model, system prompt, allowed tools, per-agent configuration, agent switching mid-conversation.
- **Workspaces** — knowledge base creation, document upload, chunking, embedding, RAG over uploaded documents.
- **Web search** — built-in web search provider integration, results injected as context.
- **Voice** — speech-to-text input, text-to-speech output (Web Speech API).
- **Theming** — dark/light/system theme, customizable accent colors.
- **Settings UI** — general, models, connections, users, admin panels.
- **Admin panel** — user management, model management, connection management, system settings.
- **Keyboard shortcuts** — new chat, settings, search, model switch, etc.
- **Export/import** — chat export to JSON/Markdown, full database backup/restore.
- **Prompt suggestions** — configurable prompt library with quick-access buttons.
- **Response actions** — copy, regenerate, edit, continue, speak, thumbs up/down per message.

### Extension system (configure, don't build)
- **Event Functions** — server-side Python hooks triggered on events: `on_user_message`, `on_assistant_message`, `on_tool_call`, `on_chat_start`, `on_chat_end`, `on_model_change`. Can mutate messages, inject context, call external APIs, log, validate.
- **Filters** — pipeline transforms on incoming user messages or outgoing assistant messages. Can rewrite, augment, sanitize, or block. Chainable.
- **Pipes** — custom model pipelines that intercept model calls. Can redirect to different endpoints, inject system prompts, merge responses, or transform streaming chunks.
- **Actions** — button-triggered workflows on any message. User clicks a button → Action runs server-side code → result appended to chat. Pre-built library + custom authoring.
- **Tools** — OpenAI-compatible function definitions callable by the model during generation. Registered through the OpenAPI/function schema.
- **MCP Integration** — Model Context Protocol tool server connection. Stock Open WebUI connects to external MCP servers; tools from the server appear in the agent's tool palette automatically.
- **Rich UI** — custom React components rendered inline in chat messages. Can display structured data, charts, interactive widgets, or any custom UI without rebuilding the shell.
- **Webhook integration** — HTTP callbacks on events for external system notification.

### Infrastructure we configure once
- OpenAI-compatible API endpoint connection (points to Kitty Gateway `/v1`)
- Single-user local mode (no auth for `127.0.0.1`)
- Automated login service via macOS LaunchAgent
- Version pinning (currently `0.10.2`)
- Isolated Python venv under `~/kitty-services/openwebui`
- Backup/restore via SQLite backup API (already implemented in `scripts/openwebui_local.py`)

---

## 2. Every Plugin We Should Install

Open WebUI's plugin ecosystem extends the shell without custom code. Each plugin is a community-maintained extension installable from the admin panel or via the plugin registry.

### Tier 1 — must install (MVP)

| Plugin | Why | Configuration |
|---|---|---|
| **Web Search** | Already built-in. Gives Kitty live web access for research needs. | Point at SearXNG local or a configured search provider. Rate-limit to prevent runaway queries. |
| **Code Interpreter** | Sandboxed Python execution for code work. Useful for coding agent. | Constrain to temp directories. Disable network in sandbox. |
| **Document Loader** | Ingests PDFs, DOCs, spreadsheets into workspace knowledge bases. | Use stock. No custom pipeline needed — Kitty Gateway handles memory. |

### Tier 2 — install after baseline (Week 2+)

| Plugin | Why | Configuration |
|---|---|---|
| **Canvas** | Visual brainstorming, mind maps, diagrams. Complements Kitty's planning work. | Stock configuration. Links to chat context. |
| **Image Viewer** | Enhanced image display, comparison, lightbox. | Already partially covered by stock attachment rendering. |
| **Prompt Library** | Pre-built curated prompt templates. | Stock prompts filtered for Kitty relevance. |
| **SQL Query** | Run read-only SQL against local databases. | Constrain to read-only. Scope to Kitty data directory. Require approval for any query. |

### Tier 3 — evaluate later (dream version)

| Plugin | Why | Status |
|---|---|---|
| **Calendar integration** | Read/write calendar events. | Evaluate vs Kitty Gateway's existing calendar tool. May conflict — prefer Gateway ownership. |
| **Email assistant** | Draft/read email through chat. | Evaluate privacy boundary. Gmail OAuth already expired — needs re-scoping. |
| **Task management** | Todoist/Things/Linear sync. | Evaluate vs Kitty's existing life-first projects. Don't create two task sources of truth. |
| **Obsidian/VSCode integration** | Direct file read/write from chat. | Safety concern — restrict to explicit user intent. Might overlap with filesystem MCP. |

### Plugin policy

- Install from the official Open WebUI plugin registry only.
- Pin plugin versions alongside the pinned Open WebUI version.
- No plugin receives ambient credentials — each is configured explicitly.
- A plugin that creates a second source of truth for a Kitty-owned concern (memory, projects, routing) is disqualified.
- Plugin installation is part of the `bootstrap` flow, not a manual step.

---

## 3. Every MCP Server We Should Run

MCP servers expose tools to Open WebUI agents through the Model Context Protocol. Stock Open WebUI connects to MCP servers and surfaces their tools in the agent tool palette.

### Already running (Kitty-owned)

| Server | Tools Exposed | Owner |
|---|---|---|
| **Kitty Bounded Tool Server** | memory search, remember, notes search, projects list, next step, calendar today, Tutor answers, Builder read-only status | Kitty Gateway (`scripts/openwebui_tool/service.py`) |

This is the only MCP server the shell connects to today. It is the thin authenticated projection of Kitty's intelligence.

### Tier 1 — must run (MVP)

| Server | Tools Exposed | Why | Configuration |
|---|---|---|---|
| **Filesystem MCP** | `read_file`, `write_file`, `list_directory`, `search_files` | Safe local file access from chat. Essential for coding agent, research, and document work. | Restrict to `~/Projects` and `~/Documents`. Require approval for writes. Deny `.env`, `.git/config`, `data/`, `secrets/`. |
| **Git MCP** | `git_status`, `git_diff`, `git_log`, `git_branch`, `git_show` | Repository awareness from chat. Enables "what changed?" and "what branch am I on?" without leaving the shell. | Read-only. No commit, push, merge, or rebase through this server. |
| **Web Fetch MCP** | `fetch_url`, `search_web` | URL content retrieval for research and fact-checking. | Rate-limited. Timeout per request. Domain allowlist optional. |
| **Shell MCP** | `run_command` | Safe shell command execution. Power-user feature for coding and system management. | Restrict to read-only commands by default (`ls`, `cat`, `stat`, `which`, `ps`, `df`). Write commands require explicit approval. Block `rm`, `sudo`, `chmod`, `curl/wget` to external hosts by default. Working directory scoped to `~/Projects`. |

### Tier 2 — add after baseline (Week 2+)

| Server | Tools Exposed | Why | Configuration |
|---|---|---|---|
| **Browser MCP** | `navigate`, `click`, `screenshot`, `extract` | Browser automation for research, testing, form filling. | Local Playwright instance. Session-scoped. No credential storage. |
| **Image MCP** | `generate_image`, `describe_image`, `edit_image` | Image generation through Kitty's Image Studio pipeline. | Proxy to Kitty Gateway's `image_jobs` endpoint. All generation goes through Gateway for lifecycle, cost tracking, and evidence. |
| **Notes MCP** | `create_note`, `search_notes`, `append_note` | Quick capture from chat. | Routes to Kitty Gateway's Quick Capture endpoint. Not a separate note store. |
| **Notion/Obsidian MCP** | `read_page`, `create_page`, `search` | Connect to Jacob's external knowledge tools. | Read-only by default. Write requires approval. Don't duplicate content already in Kitty memory. |

### Tier 3 — evaluate later (dream version)

| Server | Purpose | Status |
|---|---|---|
| **Slack MCP** | Read/send messages, search conversations. | Privacy evaluation needed. |
| **Health MCP** | Apple Health data, workout history. | Privacy boundary. Personal data must not enter model context without explicit per-use approval. |
| **Finance MCP** | Bank/credit card read-only transactions. | Extreme privacy risk. Never store credentials. Never include in automated context. T2-only. |
| **Home Automation MCP** | Lights, locks, thermostat. | Fun but low-priority. Separate auth boundary. |

### MCP policy

- Every MCP server runs as a separate process with its own environment.
- No MCP server receives Kitty's `.env` or ambient credentials.
- Tool approval classes from the Constitution apply: read-only tools may auto-execute; write tools require notification or approval; destructive tools require explicit approval.
- MCP server connection is part of the `bootstrap` flow. Health is checked during `verify`.
- An MCP server that becomes unavailable renders its tools `unavailable`, not silently hidden.

---

## 4. Every Event Function, Filter, Pipe, Action, and Tool We Should Write

This is the custom code we own. Every item here is an extension point that stock Open WebUI provides; we write the handler, not the framework.

### 4.1 Event Functions

Event Functions are server-side Python hooks. They are the primary mechanism for injecting Kitty intelligence into the shell.

| Function | Trigger | What It Does | Priority |
|---|---|---|---|
| **`kitty_context_injector`** | `on_chat_start` | Queries Kitty Gateway `/state` endpoint. Injects active project, repo branch, current time, Builder status, and available models into system prompt. | **P0 (MVP)** |
| **`kitty_memory_loader`** | `on_chat_start` | Queries Kitty Gateway memory search for relevant context based on conversation title/first message. Injects retrieved memories into system prompt. | **P0 (MVP)** |
| **`kitty_tool_auth`** | `on_tool_call` | Validates that tool calls to Kitty-owned endpoints include the Gateway secret. Strips secrets from logged tool arguments. | **P0 (MVP)** |
| **`kitty_turn_recorder`** | `on_chat_end` | Posts conversation summary/turn metadata to Kitty Gateway for activity tracking. Enables the Resume Loop. | **P1 (Week 2)** |
| **`kitty_project_switcher`** | `on_user_message` | Detects project switch commands (`/project kitty`, `/project job-search`). Updates active project in Kitty Gateway and refreshes context. | **P1 (Week 2)** |
| **`kitty_approval_gate`** | `on_tool_call` | Intercepts tool calls that require approval. Pauses execution, records decision in Kitty Gateway, resumes only after approval. | **P2 (Week 3+)** |
| **`kitty_daily_brief`** | `on_chat_start` (first of day) | On first conversation of the day, queries Kitty Gateway's Brief projection and injects "Here's what happened while you were away" into system prompt. | **P2 (Week 3+)** |
| **`kitty_error_reporter`** | `on_assistant_message` (on error) | Detects Gateway/timeout errors in assistant responses. Formats user-friendly error messages with actionable next steps. | **P1 (Week 2)** |

### 4.2 Filters

Filters are message transformation pipelines. They sanitize, augment, or redirect messages.

| Filter | Position | What It Does | Priority |
|---|---|---|---|
| **`kitty_system_prompt`** | Incoming (user message → model) | Prepends the Kitty Constitution system prompt with personality, capabilities, and honesty rules. Appended to every request. | **P0 (MVP)** |
| **`kitty_routing_annotation`** | Incoming | Adds a hidden annotation with the requested model route (Auto, Fast, Think, Code, Vision) based on user's model selection. Kitty Gateway uses this for domain-aware routing. | **P0 (MVP)** |
| **`kitty_sanitize_input`** | Incoming | Strips PII patterns (SSN, credit card numbers) from user messages before they reach the model. Redacts secrets that accidentally appear in input. | **P1 (Week 2)** |
| **`kitty_response_enrich`** | Outgoing (model → user) | Attaches execution receipts, model attribution, and token/cost metadata to assistant responses as Rich UI cards. | **P1 (Week 2)** |
| **`kitty_tool_call_display`** | Outgoing | Converts raw tool call JSON into user-friendly Rich UI cards showing tool name, arguments summary, and result preview. | **P1 (Week 2)** |
| **`kitty_error_format`** | Outgoing | Detects Gateway error responses in the stream and rewrites them as user-readable error cards with recovery suggestions. | **P1 (Week 2)** |

### 4.3 Pipes

Pipes intercept model calls. They are the most powerful extension point — we should use them sparingly.

| Pipe | Purpose | What It Does | Priority |
|---|---|---|---|
| **`kitty_auto_router`** | Model routing for `Kitty Auto` | Intercepts requests to the Auto model. Sends the message to Kitty Gateway's classification endpoint. Gateway returns the resolved route. Pipe redirects to the right model. | **P0 (MVP)** |
| **`kitty_stream_monitor`** | Streaming health | Wraps all streaming responses. Detects incomplete streams, missing `[DONE]` tokens, and provider errors. Records stream health in Gateway for diagnostics. | **P1 (Week 2)** |

Note: Most model routing should happen in Kitty Gateway, not in Open WebUI Pipes. The Pipe is only the thin redirect layer. The Gateway owns the routing decision.

### 4.4 Actions

Actions are button-triggered server-side code. They appear as buttons on messages.

| Action | Button Label | What It Does | Priority |
|---|---|---|---|
| **`kitty_capture`** | "Capture" | Saves the selected message to Kitty's Quick Capture inbox with the conversation context. | **P0 (MVP)** |
| **`kitty_remember`** | "Remember This" | Extracts key facts from the selected message and writes them to Kitty memory via the Gateway `remember` endpoint. | **P1 (Week 2)** |
| **`kitty_create_task`** | "Make This a Task" | Creates a life-first project task from the selected message content. | **P1 (Week 2)** |
| **`kitty_explain_code`** | "Tutor Me" | Sends the selected code message to Kitty's Tutor agent with "explain this code to me" context. | **P1 (Week 2)** |
| **`kitty_builder_propose`** | "Send to Builder" | Creates a Builder initiative proposal from the selected message (e.g., a coding plan or bug report). Requires approval. | **P2 (Week 3+)** |
| **`kitty_share_brief`** | "Add to Brief" | Adds the selected message content to today's Brief notes. | **P2 (Week 3+)** |
| **`kitty_fact_check`** | "Fact Check" | Sends the selected message to the Research agent for source verification and returns cited results. | **P2 (Week 3+)** |

### 4.5 Tools (OpenAI-compatible function definitions)

These are tools the model can call during generation. They are registered through Kitty Gateway's OpenAPI tool endpoint, which Open WebUI already consumes.

| Tool | What It Does | Approval Class |
|---|---|---|
| `kitty_search_memory` | Search Kitty's memory graph for relevant facts. Returns ranked results with sources. | Auto |
| `kitty_remember` | Store a fact in Kitty's memory with explicit user confirmation context. | Act + notify |
| `kitty_search_notes` | Search Kitty's ingested notes and documents. | Auto |
| `kitty_list_projects` | List active life-first and code projects with status. | Auto |
| `kitty_get_next_step` | Get the next concrete action for a project. | Auto |
| `kitty_get_calendar` | Get today's calendar events. | Auto |
| `kitty_ask_tutor` | Ask Kitty's Tutor for an explanation of a concept or code. | Auto |
| `kitty_builder_status` | Read bounded Builder status (active initiatives, recent runs). | Auto (read-only) |
| `kitty_capture` | Save content to Quick Capture inbox. | Act + notify |
| `kitty_create_task` | Create a life-first task with project, description, and due date. | Act + notify |
| `kitty_builder_propose` | Propose a Builder initiative. Creates a proposal but does not enqueue. | Request approval |

These tools are already partially implemented in `scripts/openwebui_tool/service.py` as the bounded Kitty tool server. The product plan adds the missing ones and ensures every tool follows the Constitution's approval classes.

---

## 5. Every Customization Ranked by ROI

Ranked from highest value per line of custom code to lowest.

### Immediate (highest ROI — one weekend)

| # | Customization | Custom Code | Value |
|---|---|---|---|
| 1 | **Kitty system prompt via Filter** | ~50 lines | Makes every chat feel like Kitty. Single most impactful change. |
| 2 | **Context injection via Event Function** | ~100 lines | Resume Loop comes alive. Chat knows what project, branch, and state you're in. |
| 3 | **Memory loading via Event Function** | ~80 lines | Kitty remembers across conversations. The defining feature. |
| 4 | **Model routing annotation via Filter** | ~40 lines | Auto/Fast/Think/Code/Vision routing works without custom UI. |
| 5 | **Capture Action** | ~30 lines | Quick Capture works from chat. Life-first workflow starts now. |
| 6 | **Error formatting via Filter** | ~50 lines | Gateway errors become readable. No more raw JSON in chat. |
| 7 | **Kitty brand theming** | Configuration only | Cosmic theme, cat mascot, Kitty logo. Zero code. |

### Short-term (Week 2 — builds on MVP)

| # | Customization | Custom Code | Value |
|---|---|---|---|
| 8 | **Tool call Rich UI cards** | ~100 lines | Tool execution becomes visible and trustworthy. |
| 9 | **Response enrichment (model, cost, receipt)** | ~80 lines | Honest state — users see exactly what model ran, what it cost. |
| 10 | **Filesystem MCP server setup** | Configuration + ~50 lines policy | Safe file access from chat. Coding agent becomes useful. |
| 11 | **Git MCP server (read-only)** | Configuration only | "What branch am I on?" from chat. |
| 12 | **"Remember This" Action** | ~40 lines | Memory capture stays one tap away. |
| 13 | **"Make a Task" Action** | ~40 lines | Life-first tasking from chat. |
| 14 | **Turn recorder Event Function** | ~60 lines | Activity tracking feeds the Resume Loop. |
| 15 | **Daily Brief injector Event Function** | ~50 lines | Morning context without switching surfaces. |

### Medium-term (Weeks 3–4)

| # | Customization | Custom Code | Value |
|---|---|---|---|
| 16 | **"Tutor Me" Action** | ~30 lines | Learning workflow integrated. |
| 17 | **Project switcher Event Function** | ~60 lines | `/project` commands work in chat. |
| 18 | **Builder proposal Action** | ~80 lines | Bridge from chat to Builder with approval gate. |
| 19 | **Shell MCP (read-only)** | Configuration + policy | Power-user system access from chat. |
| 20 | **Web Fetch MCP** | Configuration only | Research agent gets real web access. |
| 21 | **Input sanitization Filter** | ~40 lines | PII protection. Peace of mind. |
| 22 | **Stream monitor Pipe** | ~60 lines | Stream health visibility. Debugging superpower. |

### Lower ROI (defer past Week 4)

| # | Customization | Value | Reason to Defer |
|---|---|---|---|
| 23 | Approval gate Event Function | Request-approval flow for tool calls. | Needs policy engine maturity. Build after M3 (Builder → Work). |
| 24 | Image MCP server | Image generation from chat. | Needs Image Studio pipeline stable. Separate initiative. |
| 25 | Browser MCP server | Browser automation from chat. | Powerful but adds complexity. Validate need first. |
| 26 | Notion/Obsidian MCP | External knowledge sync. | Avoid creating two memory sources of truth. |
| 27 | Custom Rich UI components | Inline charts, progress bars, project dashboards. | Each component is bespoke maintenance. Only build when a concrete workflow demands it. |

### Net custom code estimate (Day 1 MVP)

```
Filter: kitty_system_prompt          ~50 lines
Filter: kitty_routing_annotation      ~40 lines
Event:  kitty_context_injector       ~100 lines
Event:  kitty_memory_loader           ~80 lines
Event:  kitty_tool_auth               ~30 lines
Event:  kitty_error_reporter          ~40 lines
Action: kitty_capture                 ~30 lines
Pipe:   kitty_auto_router             ~60 lines
Config: Open WebUI settings          ~0 lines (already done)
Config: MCP connections              ~0 lines (configuration files)
─────────────────────────────────────────
Total:                               ~430 lines
```

That's all the custom code needed for a working MVP. Everything else in the MVP is stock Open WebUI capabilities, already-configured settings, and already-written Kitty Gateway endpoints.

---

## 6. What Should Never Be Built Because Open WebUI Already Solved It

This is the "don't even think about it" list. Building any of these is a violation of ADR 0028 (commodity precedence).

### Chat infrastructure
- **Chat UI** — message list, input box, streaming display, typing indicators, message actions (edit, delete, regenerate, copy). Open WebUI has a polished chat UI with years of community refinement. Kitty's 60+ component `kitty-chat` chat UI is retired in favor of Open WebUI.
- **Message persistence** — chat history database, conversation list, search, archive. Open WebUI's SQLite-backed chat store is complete. Kitty Gateway owns the *enriched* chat model (turns, attempts, receipts) but Open WebUI owns the *display* persistence.
- **Streaming response handling** — SSE parsing, partial rendering, reconnection. Done.
- **Mobile chat** — responsive layout, PWA, touch interactions. Done.
- **File attachments** — upload, preview, multi-file, drag-and-drop, image rendering, PDF/DOC viewing. Done.
- **Markdown rendering** — code blocks with syntax highlighting, tables, LaTeX math, mermaid diagrams. Done.
- **Voice input/output** — Web Speech API integration. Done.
- **Theming** — dark/light/system, accent colors, custom CSS. Done.

### Model and provider management
- **Model picker UI** — dropdown with descriptions, per-conversation model selection. Done.
- **OpenAI-compatible API client** — request/response handling, streaming, error parsing. Done.
- **Model parameter controls** — temperature, top-p, context length, system prompt. Done.
- **Multi-provider connection management** — admin panel for adding/removing API endpoints. Done.

### User and session management
- **User accounts** — single-user or multi-user, admin roles. Done.
- **Session management** — login, logout, token handling. Done (simplified to single-user).
- **Settings persistence** — user preferences, UI state, model defaults. Done.

### Knowledge and retrieval
- **Document upload and chunking** — workspace file management, embedding generation. Done.
- **RAG pipeline** — chunk retrieval, context injection. Done (though Kitty Gateway's memory graph should be the primary retrieval path).
- **Web search integration** — search provider connection, result injection. Done.

### Extensibility framework
- **Plugin system** — install, configure, update plugins. Done.
- **Extension sandboxing** — Functions, Filters, Pipes run in isolated contexts. Done.
- **MCP client** — connecting to MCP servers, tool discovery, invocation. Done.

### Administrative
- **Database backup/restore** — full database backup and restoration. Done (and we've added verification).
- **Logging and monitoring** — application logs, error tracking. Done.
- **Update mechanism** — git pull, pip upgrade. Done.

### The rule

If Open WebUI's GitHub repo has the feature → configure it, don't build it. If a community plugin exists → install it, don't build it. If stock Open WebUI can be configured to do it → write a config patch, not code.

---

## 7. What Should Always Remain Kitty-Owned

These are the capabilities that make Kitty *Kitty*. They live in Kitty Gateway. Open WebUI receives them through Gateway contracts but never reimplements them. Building any of these inside Open WebUI is an architecture violation of the Constitution (Article I).

### Intelligence (Gateway-owned)

| Capability | Why Kitty Owns It |
|---|---|
| **Personality and system prompt** | Kitty's voice, values, honesty rules, and interaction style. The Constitution is the source. Open WebUI receives the system prompt via the `kitty_system_prompt` Filter but never defines it. |
| **Memory policy** | What to remember, when to retrieve, how to rank, what to forget. Kitty's memory graph is authoritative. Open WebUI may display memories but never decides memory policy. |
| **Context assembly** | Selecting relevant memories, project state, calendar, and runtime facts for each turn. The 10-step assembly pipeline lives in `gateway/context_assembler.py`. Open WebUI injects assembled context but never assembles it. |
| **Model routing** | Which model handles which request. Domain classification, cost-conscious routing, auto/think/code/vision dispatch. Open WebUI shows the model menu; Gateway decides the route. |
| **Provider policy** | Which providers to use, fallback chains, rate limits, cost budgets. Gateway owns provider decisions. Open WebUI connects only to Gateway `/v1`. |
| **Tool approval** | Classifying every tool call as auto/notify/approve/refuse. Gateway enforces approval classes. Open WebUI's `kitty_approval_gate` Event Function is the thin adapter. |
| **Project ontology** | What a project is, how projects relate to conversations, tasks, and work. Gateway owns the project model. Open WebUI displays projects as context. |
| **Life-first ordering** | Life projects before code projects. Gateway enforces this in every context and next-step query. |

### Product state (Gateway-owned)

| Capability | Why Kitty Owns It |
|---|---|
| **Resume Loop** | Active project, current work, next action, what changed. The four-spine architecture (runtime truth, product state, artifacts/evidence, policy/initiative) lives in Gateway. |
| **Home/Brief projections** | "What's next," "needs attention," "while you were away." Derived from Gateway's activity events and product state. |
| **Activity events** | What happened, when, who did it, what evidence. Append-only facts. Gateway is the single writer. |
| **Execution receipts** | Proof of what was done, by whom, with what result. Gateway owns the receipt schema and verification rules. |
| **Artifact lifecycle** | Inputs and outputs with identity, provenance, and evidence. Gateway owns the artifact registry. |

### Execution control (Builder-owned, Gateway-projected)

| Capability | Why Kitty/Builer Owns It |
|---|---|
| **Mission authoring** | Intent, constraints, acceptance criteria, allowed paths, forbidden operations. Kitty compiles; Builder executes. |
| **Initiative and packet management** | Decomposition, ordering, dependencies. Builder's queue is the single source of execution truth. |
| **Worker leasing and worktree isolation** | Safe execution in isolated git worktrees. Builder manages workers. Open WebUI may propose but never lease or run. |
| **Validation and review** | Deterministic gates plus independent review. Builder enforces. No packet completes on worker assertion alone. |
| **Publication and merge** | Operator-gated. Builder's merge flow. Never auto-committed from chat. |

### Storage (Gateway-owned)

| Store | Authority |
|---|---|
| **Kitty SQLite (main app DB)** | Authoritative for product state, projects, memory policy, artifacts, receipts. |
| **ChromaDB** | Derived vector index. Accelerates retrieval. Never authors truth. |
| **mem0** | Derived memory store. Mirrors Kitty SQLite memory records. Never authors truth. |
| **Open WebUI SQLite** | Shell-local persistence. Chats, settings, user state. Authoritative for *shell display* only; Kitty Gateway is authoritative for *product truth*. |

### The red line

If a capability appears in the Constitution's ownership table (Article I.6) under "Gateway" or "Builder" → it must **never** be implemented inside Open WebUI. Open WebUI may *display* it, *request* it, or *receive* it through a Gateway contract. It may not *define*, *decide*, or *own* it.

---

## 8. The Complete Startup Experience

From opening the app to handing work to Builder. This is the user journey.

### Cold start (first ever)

```
1. Jacob runs: python3 scripts/openwebui_local.py bootstrap --accept-charges
2. Script:
   a. Verifies Gateway and LiteLLM are healthy (starts them if not)
   b. Installs pinned Open WebUI 0.10.2 in isolated venv
   c. Creates data directory, secret, single-user admin account
   d. Configures Open WebUI to point at Kitty Gateway /v1
   e. Disables Ollama, telemetry, sharing, updates, persistent config overrides
   f. Creates five agents: Daily Kitty, Research, Coding, Tutor, Builder Operator
   g. Connects Kitty bounded MCP tool server
   h. Installs macOS LaunchAgent
   i. Creates ~/Desktop/Kitty Chat.webloc
   j. Opens browser to http://127.0.0.1:3000
3. Jacob sees: Open WebUI chat interface with Daily Kitty selected
4. Jacob types: "Hey Kitty"
5. Kitty Gateway receives the request through Open WebUI → Gateway /v1/chat/completions
6. Event Function: kitty_context_injector fires → adds project, repo, time, Builder status
7. Event Function: kitty_memory_loader fires → adds relevant memories
8. Filter: kitty_system_prompt prepends the Constitution personality
9. Filter: kitty_routing_annotation adds model route (Auto)
10. Pipe: kitty_auto_router classifies the message → routes to appropriate model
11. Response streams back with model attribution, source citations, tool call cards
12. Chat persists in Open WebUI. Activity recorded in Kitty Gateway.
```

### Daily use (warm start)

```
1. Jacob opens Kitty Chat.webloc from Desktop
2. Services already running from LaunchAgent login start
3. Open WebUI loads last conversation (persisted in its SQLite)
4. Jacob sees: daily brief card → "Welcome back. Here's what happened: ..."
5. Jacob asks: "What's next on job search?"
6. Kitty: loads job search project context from Gateway
7. Kitty: retrieves relevant memories, tasks, deadline awareness
8. Kitty: presents one concrete next action with why
9. Jacob: clicks "Got it — add to today's tasks" Action button
10. Action fires → creates task in Kitty Gateway
11. Jacob: switches to coding → selects Coding agent from dropdown
12. Event Function: kitty_project_switcher detects "kitty" project context
13. Context refreshes with repo state, recent commits, open PRs
14. Jacob: "Show me the open PRs"
15. Kitty: Git MCP returns branch/diff/PR status → formatted as Rich UI cards
16. Jacob: "Fix the test in test_openwebui_local.py" → clicks "Send to Builder"
17. Action fires → creates Builder proposal → approval required
18. Jacob approves → Builder queues packet → worktree created → worker leased
19. Kitty: "Builder is working on this. I'll tell you when it's done."
```

### After Builder completes

```
1. Kitty Gateway receives Builder completion receipt with evidence
2. Notification appears in chat: "Builder finished 'Fix PYTHONPATH test'. Review ready."
3. Rich UI card shows:
   - Changed files (diff link)
   - Test results (pass/fail count)
   - Independent review outcome
   - Cost breakdown
4. Jacob: clicks "Review" → opens Console for detailed view
5. Jacob: approves → Builder merges
6. Kitty: "Merged. The fix is live on main."
7. Activity event recorded. Home/Brief updated. Resume Loop ready for tomorrow.
```

### Edge cases handled

| Scenario | Behavior |
|---|---|
| **Gateway down** | Error Event Function detects Gateway health check failure. Chat shows: "Kitty Gateway is unavailable — last checked 14:32. Your chats are saved locally." Open WebUI chats still visible (shell persistence). |
| **Provider exhausted** | Error Filter shows: "All providers are currently unavailable. Your request is saved. I'll retry automatically or you can try again." |
| **Stream interrupted** | Stream monitor Pipe detects missing [DONE]. Response labeled "interrupted — partial response shown." Retry button creates new attempt. |
| **No internet** | Gateway detects offline. Drafts save locally in Open WebUI. "You're offline. Your message is saved and will send when you're back online." |
| **Open WebUI upgrade available** | Checked during `verify`. Reports: "Open WebUI 0.10.3 is available. Run: python3 scripts/openwebui_local.py upgrade" |
| **Database corruption** | `verify` detects it. "Database integrity check failed. Run: python3 scripts/openwebui_local.py restore" |

---

## 9. One Weekend MVP

What can ship by Sunday night with the already-merged PR #384 codebase and ~430 lines of new custom code.

### MVP objective

Jacob opens Kitty Chat, types naturally, gets Kitty-quality responses with project awareness, memory context, honest model routing, and error handling. Quick capture works. It feels like Kitty, not stock Open WebUI.

### MVP scope

**Keep from PR #384 (already done):**
- Bootstrap, verify, backup, restore, rollback
- Five agents (Daily Kitty, Research, Coding, Tutor, Builder Operator)
- Five model routes (Auto, Fast, Think, Code, Vision)
- Bounded tool server (memory, notes, projects, calendar, Tutor, Builder read)
- Lifecycle management (up/down/status/doctor/logs)
- LaunchAgent for login startup
- Environment sanitization
- Hardened settings (no telemetry, no Ollama, no persistent config overrides)

**Add this weekend (the ~430 lines):**
1. `kitty_system_prompt` Filter — Kitty personality in every chat
2. `kitty_routing_annotation` Filter — model route annotation
3. `kitty_context_injector` Event Function — active project, repo, Builder status
4. `kitty_memory_loader` Event Function — relevant memory context
5. `kitty_tool_auth` Event Function — Gateway secret on tool calls
6. `kitty_error_reporter` Event Function — readable error formatting
7. `kitty_capture` Action — save to Quick Capture
8. `kitty_auto_router` Pipe — Auto model classification dispatch

**MCP servers (configuration only):**
- Filesystem MCP (read-only, scoped to ~/Projects)
- Git MCP (read-only)
- Shell MCP (read-only, scoped to ~/Projects)

**Plugins to install (already in stock Open WebUI):**
- Web Search (built-in)
- Code Interpreter (built-in)

### MVP explicit out-of-scope

- Builder write/propose Actions (read-only only; ADR 0027 boundary)
- Rich UI custom components (standard text cards only)
- Approval gate Event Function
- Daily Brief injector
- Turn recorder
- Image generation from chat
- Browser MCP
- Tutor/project-switch commands
- Input sanitization (PII filter)
- Response enrichment cards (model/cost metadata)
- Tool call display cards (raw tool output is fine for MVP)

### MVP acceptance criteria

1. `bootstrap --accept-charges` completes clean on Jacob's Mac
2. Opening Kitty Chat shows the Daily Kitty agent with the Kitty personality
3. A message like "What's next on my job search?" returns a context-aware answer with memory recall
4. Switching to Coding agent and asking about "kitty" project shows repo/branch awareness
5. Selecting Fast/Think/Code/Vision routes works correctly (explicit pins)
6. A Gateway error shows a readable error message, not raw JSON
7. Clicking "Capture" on a message saves it to Quick Capture (verifiable in Gateway logs)
8. Chat persists across browser refresh and service restart
9. `verify --accept-charges` passes all checks
10. `backup` and `restore` produce verifiable, identical database states

### MVP file inventory

```
# New files (all in scripts/openwebui_extensions/)
scripts/openwebui_extensions/
├── filters/
│   ├── kitty_system_prompt.py        (~50 lines)
│   └── kitty_routing_annotation.py   (~40 lines)
├── events/
│   ├── kitty_context_injector.py     (~100 lines)
│   ├── kitty_memory_loader.py        (~80 lines)
│   ├── kitty_tool_auth.py            (~30 lines)
│   └── kitty_error_reporter.py       (~40 lines)
├── actions/
│   └── kitty_capture.py              (~30 lines)
├── pipes/
│   └── kitty_auto_router.py          (~60 lines)
└── mcp/
    ├── filesystem_config.json         (configuration)
    ├── git_config.json                (configuration)
    └── shell_config.json              (configuration)

# Modified files
scripts/openwebui_local.py             (add extension install to bootstrap)
scripts/openwebui_tool/acceptance.py   (add extension verification to verify)
docs/runbooks/OPENWEBUI_TOMORROW.md    (add extension sections)
```

---

## 10. Dream Version

What Open WebUI + Kitty looks like when the full product architecture (Constitution + KITTY_PRODUCT_ARCHITECTURE.md phases) is realized through the shell.

> "I open Kitty every morning and it knows exactly where I left off. It hands me one thing to do — the right thing — with the context of why. When I delegate coding work, Builder handles it and reports back with evidence. When I learn something, Kitty remembers it and brings it back at the right moment. When I'm stuck, it asks clarifying questions instead of guessing. When something breaks, it tells me honestly and helps me fix it. It costs almost nothing to run. It runs on my machine. It's mine."

### Dream feature map

#### Surface 1: Home (the first thing you see)

- **Morning Brief card** — "Good morning, Jacob. Yesterday you applied to 3 jobs and Builder fixed the PYTHONPATH test. Today: follow up on Acme Corp application, and your benefits deadline is Friday."
- **What's Next card** — one concrete action with project, context, and why. Tappable to open the relevant conversation with context pre-loaded.
- **Needs Attention section** — approvals expired, failed Builder runs, credential expirations, deadlines approaching.
- **While You Were Away** — material changes: completed Builder work, new captures, important emails/calendar changes (if integrations are active).
- **Continue Where You Left Off** — active conversations and work, ordered by recency and importance.
- **Life dashboard (ambient)** — job search progress, benefits status, education milestones. Not a project management tool — a calm, honest status view.

All powered by Gateway's Home/Brief projection queries. All rendered in Open WebUI conversation cards. No custom frontend.

#### Surface 2: Chat (the command surface)

- **Kitty personality shines** — warm, direct, honest. Cites sources. Admits uncertainty. Remembers everything relevant.
- **Project-aware** — knows which project you're in, the repo state, recent changes, open PRs, active Builder work.
- **Tool execution is visible** — every tool call shows as a Rich UI card: tool name, arguments summary, result preview, elapsed time. "Kitty searched memory (4 results, 120ms)" — not hidden.
- **Model attribution is honest** — "Answered by Kitty Think (qwen/qwen3-235b-a22b-thinking-2507, 2.3k tokens, ~$0.01)" on every response.
- **Rich response cards** — code diffs with syntax highlighting, file change previews, test result tables, PR status badges, weekly summaries.
- **Quick actions on every message** — Capture, Remember, Make Task, Tutor, Send to Builder, Fact Check. One tap.
- **Seamless model switching** — "Think about this" → switches to Think. "Just do it fast" → switches to Fast. Model stickiness: explicit switch stays, Auto reclassifies.
- **Voice in, voice out** — "Hey Kitty" → speech-to-text. Response → text-to-speech. Works on phone.
- **Image generation in chat** — "Draw me a..." → Image MCP routes through Kitty Gateway's Image Studio → result appears as Rich UI card → variations and edits in-thread.
- **Tutor mode** — "Explain this concept" triggers a pedagogical response with examples, analogies, and check-for-understanding questions.

#### Surface 3: Work (Builder results and plans)

- **Builder results as chat cards** — "Builder finished 'Fix test_openwebui_local.py': 1 file changed, 3 tests added, all passing. Independent review: approved."
- **Work status** — currently running, queued, completed, failed. Filtered by project.
- **Detailed run views** — diff, test results, review outcome, cost, runtime. Accessed from chat cards.
- **Approval flow** — "Builder wants to push to main. 3 files, 12 tests. Review?" → "Approve" or "Reject" from chat.
- **Work history** — what was done, when, by which worker, with what evidence. Searchable.

#### Surface 4: Memory (ambient, not a destination)

- **Memory is ambient** — Kitty remembers without you managing it. Retrieval happens automatically.
- **"What does Kitty know about X?"** — ask and get a cited list. "Forget that" removes it.
- **Memory provenance** — every remembered fact shows: when it was captured, from which conversation, with what confidence.
- **Correction flow** — "That's wrong, actually..." → Kitty updates the memory record with the correction.
- **Memory decay** — old, unused, or contradicted memories surface for review. "I haven't used this in 3 months. Should I forget it?"

#### Surface 5: Brief (daily narrative)

- **Auto-generated daily summary** — conversational tone, not a dashboard. "Today you worked on the Kitty codebase: Builder fixed the test, and you applied to two jobs. Your Acme Corp follow-up is overdue — want to draft it now?"
- **Weekly and monthly retrospectives** — "This week: 3 job applications, 2 Builder completions, 4 things learned, 12 captures processed."
- **Every claim links to evidence** — "You applied to Acme Corp (source: email draft, saved 2:34pm)"
- **Shareable** — export as markdown, send to self, add to journal.

### Infrastructure dream

| Component | Dream State |
|---|---|
| **Open WebUI** | Latest stable version. All extensions auto-update with version pinning. Bootstrap goes from zero to done in under 2 minutes on any Mac. |
| **Kitty Gateway** | Full four-spine architecture operational. Runtime truth manifest, product state projections, artifact registry, policy engine — all live. |
| **Builder** | Full self-building roadmap operational. Proactive packet selection. Budgeted, scoped, recoverable. Independent review always separate from execution. |
| **LiteLLM** | Under the hood. Invisible to the user. Provider fallback is seamless. Cost tracking is accurate. |
| **MCP servers** | Filesystem, git, shell, web fetch, browser, image — all running. Tools appear in agent palette automatically. Health is monitored. |
| **Storage** | Consolidated: one authoritative SQLite store plus one derived ChromaDB index. No duplicate truth paths. Migration completed, verified, soaked. |
| **Console** | The Next.js app is the operator surface for configuration, diagnostics, and advanced Builder control. Not a competing chat shell. |
| **Mobile** | Open WebUI as PWA on phone. Resume Loop works from anywhere at home. Voice-first on mobile. |

### Dream user journey (a real day)

```
08:00 — Jacob opens Kitty on his phone
       "Good morning, Jacob. Your Acme Corp application needs a follow-up today.
        Want me to draft it?" → "Yes" → Kitty drafts the email from chat.

08:30 — Jacob switches to Mac, opens Kitty Chat
       Builder completed overnight: "Merged fix for PYTHONPATH regression test."
       Home shows: "1 thing done, 1 thing needs you, 2 new captures."

09:00 — "What did I learn about React Server Components last week?"
       Kitty retrieves memories from a Tutor session 5 days ago. Cites the conversation.

10:00 — "I need to understand this codebase's auth flow"
       Kitty uses Filesystem MCP to read the code, Git MCP to check history,
       Tutor agent to explain. Returns Rich UI card with architecture diagram.

12:00 — "Fix the streaming smoke test"
       "Here's my diagnosis: the SSE stream terminates correctly but the verifier
        expects [DONE] as a separate event while the Gateway emits it inline.
        Should I send this to Builder?" → "Yes" → Builder queues the packet.

14:00 — "Show me my job search progress"
       "3 applications this week (2 pending, 1 needs follow-up). 12 total since
        July. Average response time: 4 days. Want to see them?" → Rich UI table.

16:00 — Builder finishes. "Test fix ready. Diff: 1 file, 8 lines. Tests: all pass.
        Independent review: approved (no issues). Merge?" → "Merge."

22:00 — Jacob opens Kitty one last time on phone
       "Today: drafted 1 email, learned something, Builder fixed 1 thing,
        applied to 1 job, captured 3 ideas. Tomorrow: follow up on Acme Corp."
       Brief auto-saved. Phone goes dark. Kitty remembers.
```

### Dream constraints

- **No fork of Open WebUI.** Every dream feature runs through stock Open WebUI extension points.
- **No custom frontend.** Rich UI cards are the only custom rendering. The shell is pristine.
- **Gateway owns all intelligence.** The dream adds no new intelligence surface. It makes the existing Gateway intelligence more accessible and more ambient.
- **Honesty is maintained.** Every dream feature obeys the Constitution: evidence before claims, fail-loud, honest state, no fabricated success.
- **Life-first ordering persists.** Job search, benefits, education outrank code projects in every surface.
- **Replaceable shell.** If Open WebUI is abandoned or changes license, the dream migrates to the next shell through the same Gateway contracts. It takes a weekend, not a rewrite.

### What the dream explicitly is not

- Not an "AI operating system" with a custom desktop, window manager, or file system
- Not a multi-user SaaS platform
- Not a cloud service (local-first remains the core principle)
- Not a "do everything" agent with unlimited autonomy
- Not a replacement for human decision-making
- Not a general-purpose tool for anyone other than Jacob

The dream is a quiet, honest, capable companion that shows up every morning, knows where Jacob's life stands, hands him one concrete next move, remembers everything, and never pretends.

---

## Appendix A: Open WebUI Extension Architecture Reference

This is a summary of stock Open WebUI's extension model for product planning purposes. For exact APIs and version-specific behavior, consult the pinned Open WebUI version's documentation.

### Event Functions

```python
# Location: configured in Open WebUI admin panel
# Trigger: automatic on named events

class EventHandler:
    def __init__(self):
        pass

    async def on_chat_start(self, request: dict, user: dict) -> dict:
        """Mutate the request before the first message is sent."""
        return request

    async def on_user_message(self, request: dict, user: dict) -> dict:
        """Mutate each user message before it reaches the model."""
        return request

    async def on_assistant_message(self, request: dict, user: dict) -> dict:
        """Mutate each assistant message before it reaches the user."""
        return request

    async def on_tool_call(self, request: dict, user: dict) -> dict:
        """Intercept tool calls before execution."""
        return request

    async def on_chat_end(self, request: dict, user: dict) -> dict:
        """Cleanup after conversation ends."""
        return request
```

### Filters

```python
# Location: configured in Open WebUI admin panel
# Trigger: pipeline — incoming before model, outgoing before user

class Filter:
    class Valves:
        pass

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, user: dict | None = None) -> dict:
        """Transform incoming message (user → model)."""
        return body

    def outlet(self, body: dict, user: dict | None = None) -> dict:
        """Transform outgoing response (model → user)."""
        return body
```

### Pipes

```python
# Location: configured as a custom model pipe in Open WebUI
# Trigger: model selection matching the pipe's name

class Pipe:
    class Valves:
        pass

    def __init__(self):
        self.valves = self.Valves()

    def pipe(self, body: dict, user: dict | None = None) -> str | dict:
        """
        Intercept model call. Can:
        - Return a string (direct response, no model call)
        - Return a dict (modified request forwarded to model)
        - Return a streaming response
        """
        return body
```

### Actions

```python
# Location: configured in Open WebUI admin panel
# Trigger: user clicks action button on a message

class Action:
    class Valves:
        pass

    def __init__(self):
        self.valves = self.Valves()

    async def action(
        self,
        body: dict,
        user: dict | None = None,
    ) -> dict:
        """
        Execute action. body contains:
        - model_id, messages, chat_id, user_id
        Returns: dict with type, data, or rich UI payload
        """
        return {"type": "text", "data": "Action completed"}
```

### Tools (via OpenAPI endpoint)

Tools are registered through Kitty Gateway's `/v1/tools` endpoint, which Open WebUI already consumes. The Gateway provides OpenAI-compatible function definitions. No additional extension code needed in Open WebUI.

### Rich UI

```python
# Returned from Actions or Event Functions
{
    "type": "rich_ui",
    "data": {
        "type": "card",      # card | table | chart | custom
        "title": "String",
        "content": "Markdown or structured data",
        "actions": [...]     # optional interactive buttons
    }
}
```

### MCP Connection

MCP servers are configured in Open WebUI's admin panel. The shell discovers tools automatically through the MCP protocol. Each server runs as a separate process. No custom code needed — configuration only.

---

## Appendix B: Stock Open WebUI Features We Disable

These features are intentionally disabled because they conflict with Kitty's architecture. Documented here for operator awareness.

| Feature | Why Disabled | Configuration |
|---|---|---|
| **Ollama** | Kitty uses LiteLLM → OpenRouter/Gateway routing. Local Ollama would create a second model truth. | `ENABLE_OLLAMA_API=False` |
| **Telemetry** | Local-first companion. No analytics. | Disabled in settings. |
| **Community sharing** | Personal AI companion. Sharing disabled. | Disabled in settings. |
| **Update checks** | Version is pinned by Kitty bootstrap. Auto-update would break the shell. | Disabled in settings. |
| **Arena models** | Model quality leaderboards. Irrelevant — Kitty Gateway owns model selection. | Disabled in settings. |
| **Persistent config overrides** | Checked-in configuration must remain authoritative. Database overrides would create drift. | `ENABLE_PERSISTENT_CONFIG=False` |
| **Multi-user auth** | Local single-user only. No user management. | `WEBUI_AUTH=False` |
| **External network binding** | Shell is loopback-only (`127.0.0.1:3000`). | Binding configuration. |

---

## Appendix C: What Changes When Open WebUI Upgrades

Open WebUI version is pinned at `0.10.2`. When upgrading:

1. **Read the changelog.** Identify breaking changes to Event Functions, Filters, Pipes, Actions, or MCP connections.
2. **Back up first.** `python3 scripts/openwebui_local.py backup` before any upgrade.
3. **Test in isolation.** Run the new version on a different port with a copy of the database.
4. **Run verify.** `python3 scripts/openwebui_local.py verify --accept-charges` must pass on the new version.
5. **Keep the old version.** The isolated venv and database backup make rollback possible with one script.
6. **Update this document.** Any changed extension APIs, new capabilities, or deprecated features should be reflected here.

---

## Appendix D: Authority and Supersession

This document:
- **Implements:** Constitution (v1), ADR 0027 (Open WebUI shell boundary), ADR 0028 (commodity precedence), KITTY_PRODUCT_ARCHITECTURE.md (four-spine architecture), ROADMAP_V2.md (milestone sequencing).
- **Is superseded by:** A future ADR that explicitly revises the Open WebUI product surface or adopts a different shell.
- **Does not override:** The Constitution, any ratified ADR, or the running Gateway code (live truth beats written plan).
- **Implementation order:** Follows ROADMAP_V2.md milestones. M1 (daily-driver baseline) is the foundation for every extension in this plan.
- **Boundaries:** This plan may be executed by Builder workers only through authorized packets with validation gates and independent review. No autonomous broad-scope shell changes.
