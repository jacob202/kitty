# Open WebUI Ecosystem Survey — Capability Coverage

**Date:** 2026-08-05
**Mission:** Determine, for every desired Kitty capability, whether it already exists as Open WebUI built-in, community plugin, MCP server, or OpenAPI integration before recommending any custom development.

## Survey methodology

Searched: official docs (docs.openwebui.com), GitHub (topics: open-webui-tools, -functions, -plugins), community marketplace (openwebui.com), Reddit, blog posts, and the four largest community tool repositories.

## Key community repositories

| Repository | Stars | Contents |
|---|---|---|
| Haervwe/open-webui-tools | 781 | 20+ tools, pipes, filters: arXiv, YouTube, weather, ComfyUI image/audio/video, planner agent, semantic router |
| Classic298/open-webui-plugins | 498 | Tools, skills, filters, actions, events: inline visualizer v2 (charts/dashboards), email composer, MCP app bridge, vision bridge, prune, interface defaults |
| iChristGit/OpenWebui-Tools | 134 | 26 tools: weather, news/RSS reader, Reddit, YouTube, Jellyfin, podcasts, radio, sports, Steam, stocks, Wikipedia, QR codes, image/video gen, orchestrator |
| Skyzi000/open-webui-extensions | 65 | Sub Agent (#1 most downloaded, 14K+), parallel tools, multi model council, Graphiti memory, user location |

## Comprehensive capability table

**Maturity:** ✅ Production-ready | 🟡 Functional/pre-release | ⚠️ Partial/incomplete | ❌ Not found
**Burden:** `none` = zero config | `env` = environment vars | `key` = API key | `host` = self-hosted service | `build` = custom code required

| Capability | Existing solution | Maturity | Burden | Notes |
|---|---|---|---|---|
| Chat with any model | Built-in multi-provider support (Ollama, OpenAI, Anthropic, any OpenAI-compatible) | ✅ | `none` | Core platform |
| Morning dashboard / Home page / Launchpad | Event Functions can serve standalone HTML pages at custom routes (documented: "server-rendered pages, not just JSON... without a frontend rebuild") | ⚠️ buildable | `build` | The one genuine gap. No community launchpad found. ~200-400 line Event Function. |
| Weather | iChristGit OpenWeatherMap tool; Haervwe OpenWeatherMap Forecast Tool | ✅ | `key` | Free OpenWeatherMap API key. One-click marketplace install. |
| Notes / scratchpad | Built-in Notes: rich editor, AI enhance, attach to chats, full-context injection, agentic access | ✅ | `none` | Native. |
| Memory (cross-conversation) | Built-in Persistent Memory; Skyzi000 Graphiti Memory (knowledge-graph-based, Zep Graphiti) | ✅ | `none`/`host` | Native memory = zero config. Graphiti = advanced option. |
| Calendar | Built-in Calendar (month/week/day, recurring, reminders, function-calling); Google Calendar via MCP | ✅ | `none`/`key` | Native. GCal via MCP. |
| Tasks / todos / reminders | Built-in Tasks (create_tasks, update_task — structured checklists, native function calling); Automations (scheduled prompts) | ✅ | `none` | Native. |
| Daily briefing / unfinished work | Composability of Automations + Memory + Tasks + Event Functions (system.startup hook) | 🟡 composable | `none`/`build` | No single community "briefing" plugin. Composable from native parts + ~100-line Event/Filter. |
| Notifications | Built-in webhooks; Event Functions (system events); Banners (system-wide announcements) | 🟡 | `none`/`config` | Webhooks exist. No proactive "surprise me" plugin. Buildable. |
| Rich dashboards / artifacts | Classic298 Inline Visualizer v2: Chart.js, D3, Vega-Lite, ECharts, Plotly, vis-network, Tone.js | ✅ | `none` | Tool+Skill pair. Charts/visualizations render inline in chat. |
| RSS | iChristGit News Reader: 45 RSS feeds across 11 categories, expandable cards, AI summaries, keyword search | ✅ | `none` | Zero API key. One-click install. Custom feed sources configurable. |
| Gmail | MCP server (official Google MCP or community email-mcp-server) → admin adds once | ✅ via MCP | `key` (OAuth) | Requires one-time GCP OAuth setup. |
| Google Calendar | Google MCP server covers Calendar | ✅ via MCP | `key` (OAuth) | Same MCP server as Gmail. |
| Google Drive | Google MCP server covers Drive | ✅ via MCP | `key` (OAuth) | Same MCP server. |
| Google Contacts | Google People API via MCP or custom OpenAPI server | 🟡 | `key`/`build` | Verify Google MCP covers People API. |
| GitHub | Official GitHub MCP server (chat-based repo interaction); oikb (Open WebUI's knowledge sync for 45+ sources including GitHub) | ✅ | `key`/OAuth | MCP for tool calls; oikb for continuous Knowledge sync. |
| Builder integration (Kitty) | No community solution. Must be custom. | ❌ | `build` | ~100-line Tool that calls Kitty's builder API. |
| Coding workflows | Built-in Open Terminal (real shell, files, packages); Open WebUI Computer (whole machine); Sub Agent (#1 most downloaded); Multi Model Council | ✅ | `none` | Terminal native. Sub Agent = one-click install. |
| MCP servers | Native support (v0.6.31+, Streamable HTTP, OAuth 2.1, custom headers, admin-gated, scoped per user/group). mcpo proxy bridges stdio/SSE. | ✅ | varies | Core platform feature. Any MCP server works. |
| Browser automation | Playwright MCP server (official, Anthropic-backed) → connect as MCP. No Open WebUI-native browser tool found. | ✅ via MCP | `host` | Run playwright-mcp-server, add as MCP External Tool. |
| File browser | Built-in sidebar file browser (upload/download/edit) in Open Terminal | ✅ | `none` | Native. |
| Terminal | Built-in Open Terminal (code exec, packages, servers, Docker isolation) | ✅ | `none` | Native. |
| Image generation | Built-in (DALL-E, Gemini, ComfyUI, AUTOMATIC1111); Haervwe HuggingFace Gen; iChristGit Qwen Edit, LTX Video | ✅ | varies | Native supports multiple backends. |
| ComfyUI | Haervwe ComfyUI Image-to-Image, Text-to-Video, ACE Step Audio; iChristGit LTX Video, Qwen Edit, RTX Upscaler | ✅ | `host` | Requires running ComfyUI instance. |
| RunPod | Connect as OpenAI-compatible endpoint in Admin Settings → Connections → OpenAI | ✅ | `key` | No special tool needed. |
| LiteLLM | Connect as OpenAI-compatible endpoint | ✅ | `none` | Point at your existing LiteLLM proxy URL. |
| Ollama | Native first-class support; automatic discovery on same host | ✅ | `none` | Built-in. |
| OpenRouter | Connect as OpenAI-compatible endpoint; Haervwe OpenRouter WebSearch Citations filter + Image Pipe | ✅ | `key` | Point at OpenRouter API. Filter preserves citations. |
| Project management / Kanban | No kanban. Built-in Tasks (list-based, not board). Community PM tools not found. | ⚠️ | — | Tasks cover list workflows. Kanban = gap. |
| Desktop launcher / Side panels | Official desktop app (Spotlight chat bar Shift+Cmd+I, drag-to-screenshot, push-to-talk voice, local llama.cpp). Side panels/widgets not natively present. | ⚠️ text-launcher only | `none` | Desktop app = launcher. Spotlight = quick access. Side panels/widgets = gap. |
| Bookmarks | Built-in conversation pinning + folders + tags. No external URL bookmarking tool found. | 🟡 | `none` | Pins/folders cover internal. External URL bookmarking = Notes workaround. |
| Reddit | iChristGit Reddit Explorer: browse, search, comments, profiles, zero API key | ✅ | `none` | One-click marketplace install. |
| Podcasts | iChristGit Podcast Player: iTunes Search API, RSS, waveform player, speed control | ✅ | `none` | One-click marketplace install. |
| YouTube | iChristGit YouTube Player (watch, search, AI summaries, transcripts, no API key); Haervwe YouTube Search & Embed (needs API key) | ✅ | `none`/`key` | iChristGit version = zero API key. |
| Autonomous sub-agents | Skyzi000 Sub Agent (14,000+ downloads, #1 most upvoted): isolated sub-agents, MCP support, parallel execution | ✅ | `none` | One-click. This IS agents-as-a-team. |
| Multi-model council / team | Skyzi000 Multi Model Council (majority vote); Haervwe Multi Model Conversations v2; iChristGit Orchestrator | ✅ | `none` | Multiple approaches. |
| Image editing | Haervwe ComfyUI Qwen Image Edit 2509 (1-3 images, style transfer); iChristGit Qwen Edit + RTX Upscaler | ✅ | `host` | Requires ComfyUI host. |
| Language pronunciation | iChristGit Pronunciation Guide tool | ✅ | `none` | One-click. |
| Wikipedia | iChristGit Wikipedia tool | ✅ | `none` | One-click. |
| Stocks | iChristGit Stock Info tool | ✅ | `none` | One-click. |
| QR codes | iChristGit QR Code Generator | ✅ | `none` | One-click. |
| Email composition | Classic298 Email Composer: AI drafting, rich UI card, To/CC/BCC, download .eml, send via mailto | ✅ | `none` | One-click install. |
| Reasoning model coherence | Classic298 Keep Reasoning Content: preserves chain-of-thought across tool calls | ✅ | `none` | One-click Filter install. |
| Vision for text-only models | Classic298 Vision Bridge: filter strips images, tool lets model call vision on demand | ✅ | `none` | Requires Open WebUI 0.11.0. |
| Interface defaults per instance | Classic298 Interface Defaults: set Settings→Interface defaults from Valves, auto-seed new users | ✅ | `none` | Requires Open WebUI 0.10.0. |
| Workspace pruning/maintenance | Classic298 Prune: throttled DB/storage cleanup, dry-run, Redis-coordinated, admin page at /prune | ✅ | `none` | Requires Open WebUI 0.10.0. |
| MCP app rendering | Classic298 MCP App Bridge: renders MCP Apps (SEP-1865) as Rich UI embeds | ✅ | `none` | One-click Tool install. |
| Semantic model routing | Haervwe Semantic Router filter | ✅ | `none` | Filters/actions installed from repo. |
| Full document processing | Haervwe Full Document filter | ✅ | `none` | Filters/actions installed from repo. |
| Prompt enhancement | Haervwe Prompt Enhancer filter | ✅ | `none` | Filters/actions installed from repo. |
| User location | Skyzi000 User Location tool (browser Geolocation API) | ✅ | `none` | One-click. |
| Parallel tool execution | Skyzi000 Parallel Tools | ✅ | `none` | One-click. Requires strong model. |
| Multi-persona writing | Skyzi000 LLM Review: independent revision and peer feedback, preserves divergent voices | ✅ | `none` | One-click. |
| User info injection | Skyzi000 User Info Injector filter | ✅ | `none` | Filters installed from repo. |
| Full context mode toggle | Skyzi000 Full Context Mode Toggle filter (batch toggle per chat) | ✅ | `none` | Filters installed from repo. |

## Gap summary: what remains without community solution

| Capability | Custom code required | Estimated lines | Priority |
|---|---|---|---|
| Home page / Launchpad dashboard | Event Function serving route, HTML page | ~200-400 | P1 |
| Morning briefing (assembled from native parts) | Event/Filter/Automation combination | ~100 | P2 |
| Kitty Builder bridge (submit work, read status) | Tool (function-callable) | ~100 | P3 |
| Surprise/proactive nudges | Event Function + Automation | ~100 | P4 |
| Kanban board | Not found. Evaluate if Tasks+Notes suffice. | TBD | Evaluate |

**Total custom code to reach 90%+ ideal workspace: ~500-700 lines, all as Open WebUI plugins (no fork, no frontend rebuild).**
