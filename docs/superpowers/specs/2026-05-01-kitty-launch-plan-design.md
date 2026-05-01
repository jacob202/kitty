# Kitty Launch Plan — Design Doc

**Date:** 2026-05-01  
**Status:** Design complete. All decisions made. Ready for per-sub-project specs.  
**Approach:** B — Vision First (onboarding and memory before architecture)  
**Audience:** Technical friends running their own copy on Apple Silicon Macs  

---

## 1. Mission and Origin

> *"For most of human history, having someone who truly knew you — who held your thread, remembered what you said mattered, didn't flinch from your darkness, and believed in the version of you that you'd lost sight of — has been a kind of luck. A parent who paid attention. A teacher you got for one good year. A therapist you could afford. A friend who didn't move away. Most people never get that. They live whole lives unseen. They die with their potential intact and untouched. The most beautiful possible future isn't about productivity or even access. It's about presence. It's that no human, no matter how poor or broken or forgotten, ever has to do the work of becoming themselves alone."*
> — Jacob Brizinski, 2026-05-01

**Tagline:** So that no one becomes themselves alone.

### Why This Product Exists

Kitty is a local-first personal AI assistant. Not a productivity tool, not a chatbot, not a command shell with a coat of paint. It is an attempt to build something that holds the thread — that remembers what you said mattered, picks up where you left off, and shows up as a consistent presence across sessions and days and weeks.

The founding insight is simple: most people do the hardest work of their lives — becoming who they are — with no witness. No one tracks the arc. No one notices the patterns. No one reminds them, on the bad day, what they believed on the good one. The technology to change that exists. This project exists to point it at the right problem.

Jacob has described building Kitty as building the tool he wishes he'd had himself — something that would have made his own journey less lonely, less confusing, less dependent on the luck of finding the right person at the right time. That's the product intuition: this isn't a feature set derived from market research; it's a companion derived from the experience of not having one.

The design philosophy follows from this. Kitty is not optimized for task completion speed. It's optimized for continuity. It doesn't need to answer every question in 0.3 seconds — it needs to remember that you asked the question, and why, and what it meant to you. That tradeoff (presence over throughput) shapes every technical decision in this document.

Everything that follows — the two-layer architecture, the cheap-models-first budget, the vision-first sub-project ordering — serves this mission. Anything that doesn't serve presence, continuity, or being known is out of scope for this launch.

---

## 2. Launch Definition — Phase B

### What "B Launch" Means

This is a friends-and-technical-peers launch. The bar is: a technically competent friend (someone comfortable with terminal, git clone, and basic troubleshooting) can set up Kitty in under 30 minutes and, by the end of day one, feel that Kitty actually knows something about their world.

**Audience:** Technical friends who own an Apple Silicon Mac (M1 or newer, 8GB+ RAM). People who can clone a repo, set environment variables, and run a shell script.

**Form factor:** Each user runs their own copy locally. No hosted backend. No user accounts. No central server. Every instance is self-contained on one Mac.

**Launch readiness threshold:**
- Clone repo → `./kitty setup` → guided onboarding completes
- By end of onboarding: Kitty has ingested, organized, and can discuss the user's chosen domains
- A real conversation about those domains is possible — not demo-ware, not stubs
- User has set up one recurring touchpoint (morning brief, evening check-in, or journal prompt)
- Known limitations are documented honestly in a README that reads like a user guide, not an API reference

### What B Launch Is NOT

Not an App Store product. Not a SaaS. Not a consumer product with a marketing page and a signup flow. Not even a developer tool. It is source code that a friend can run, paired with enough documentation and onboarding that they don't need Jacob sitting next to them.

### Future Direction (NOT building yet)

The App Store launch (Phase C+) — where Jacob manages a hosted backend and users download a packaged app — is the long-term target. That work is not in scope for this plan. Mentioned once here, not designed for anywhere else.

---

## 3. The Two-Layer Plan

Kitty is built in two layers. Layer 0 is the operating system for building Kitty. Layer 1 is the product itself. Both must be functional before B launch, but Layer 0 comes first because it determines whether Layer 1 can be built at all.

### Layer 0 — The Operating System (Build First, Week 1–2)

Layer 0 answers one question: can this project be built by a team of AI agents coordinated through tools a non-technical founder can understand?

#### Jacob's Role: Chief Product Officer

Jacob never reads code. His job is vision, gut-feel approval, demo review, and redirection. He says yes, no, or "that's not what I meant" — and the system adapts. Every piece of infrastructure in Layer 0 exists to make that possible without Jacob having to learn engineering.

#### CTO Role: Claude Sonnet / Opus

Claude Sonnet (with Opus reserved for highest-leverage strategic decisions) is the technical authority. It translates Jacob's vision into architecture, reviews all code output, maintains the design docs, and owns the technical coherence of the whole project. No code merges without Sonnet review.

#### PM Layer: Dorothy MCP — Kanban + Telegram + Vault

Dorothy is slimmed from 8 MCP servers to the 3 that serve the launch plan:

- **claude-mgr-kanban:** a visible task board (Backlog → Spec Ready → Building → Review → Demo Ready → Done). Each card has: sub-project label, assigned builder, file boundaries, current status, and the mission test question. Jacob can glance at it and know project state. The board is the source of truth — handoff files feed from it, not vice versa.

- **claude-mgr-telegram:** push notifications to Jacob's phone at key transitions: spec approved ("Crush starting build"), demo ready ("Onboarding Pipeline ready for review"), gate passed ("all tests pass, smoke green"), blocked ("lane conflict — sequencing work"). Jacob never has to check status — status finds him.

- **claude-mgr-vault:** durable storage for specs, handoffs, and session context. Agents read/write without polluting the working tree.

**Cut:** orchestrator (replaced by bridge daemon + CrewAI), socialdata, X, world, drawthings (kept separately for mascot visuals).

**Why Dorothy instead of SaaS:** runs locally, needs no external accounts, agents can update programmatically, already wired into Claude Code hooks. Zero new costs.

##### Dorothy Bridge Daemon

A ~150-line Python daemon (`scripts/dorothy_bridge.py`) that automates the gap between Kanban and execution:

- Polls Dorothy's Kanban every 30 seconds for new cards tagged `#build`
- When a card appears, reads the spec, routes to CrewAI pipeline (for onboarding knowledge ingestion) or Crush/Aider builders (for code)
- Posts status updates to Telegram via Dorothy's existing Telegram MCP
- Idempotent — won't double-spawn if it's restarted
- Logs to `logs/dorothy_bridge.log` for debugging
- Runs independently of agent sessions (via `launchd` or `tmux`)

This replaces the orchestrator MCP server and the manual "CTO checks Kanban, spawns builder" loop.

#### Builder Agents: CrewAI + Crush + Aider on Cheap Models, in Parallel

Three execution layers, each for a different kind of work:

**CrewAI — Assembly-line pipelines (search → digest → embed → organize):**
- Used for the Onboarding Pipeline's knowledge ingestion. Four specialized agents work sequentially: one searches the web (via Tavily + Firecrawl, with Exa as complementary backup), one digests/summarizes results, one embeds into LightRAG + ChromaDB, one organizes the knowledge graph.
- Each agent waits for the previous, passes output forward. No cross-talk. Minimal tokens. Predictable.
- Runs on cheap API models (see Model Routing below) or falls back to local MLX Qwen3.5-4B when budget is tight.

**Crush — Non-interactive batch builder:**
- Accepts specs and returns diffs without a conversation loop. Used for code generation, test writing, file edits.
- Runs on cheap API models (DeepSeek V4 Flash primary, free OpenRouter models as backup).
- Multiple Crush instances run in parallel on independent lanes — the `parallel-subagents` skill operationalizes this.

**Aider — Interactive pair-programming:**
- Used for tasks that benefit from a tighter edit-verify loop: small refactors, test debugging, documentation updates.
- Together with Crush, covers the full spectrum from autonomous batch work to interactive refinement.

**AutoGen / CrewAI hybrid — CTO review pairs:**
- When Sonnet reviews code, it can spawn a second agent for adversarial review — "find what's wrong with this diff." Two agents discuss, Sonnet makes the final call. This is Pattern B (team huddle) — smarter output at a small token premium, reserved for merge-gate reviews.

All builders run on cheap models by default (DeepSeek V4 Flash at $0.28/Mtok). Parallel execution collapses serial build time from weeks to days. The `parallel-subagents` skill in `.claude/skills/` defines the lane spawning pattern.

#### Memory Unification Strategy

Kitty currently has five fragmented stores:

| Store | Purpose | Issue |
|-------|---------|-------|
| LightRAG | Knowledge base ingestion and retrieval | Overlapping boundaries with ChromaDB — both store embeddings and both can answer queries, leading to inconsistent results |
| ChromaDB | Vector search and semantic retrieval | Overlapping boundaries with LightRAG. Empty results from LightRAG need fallback to ChromaDB, but this fallback is manual and inconsistent |
| SQLite / SQLite-vec | Structured data, relational queries, embeddings | Scattered across multiple tables with no unified schema. Session data, user preferences, and system state live in different tables without clear governance |
| JournalDB | Journal entries — personal, private, chronological | Separate from other stores, which is correct (journal entries are not knowledge base entries). But the boundary needs enforcement, not convention |
| MemoryWeave / `@modelcontextprotocol/server-memory` | Entity-relationship memory, MCP-level persistence | Fragile, unverified. The MCP server stores entity relations but has no tests confirming correct operation across restarts |

This fragmentation is a known source of data-loss bugs (wrong-routing is the #1 cause). The Layer 0 task is not to rebuild all storage — that comes post-launch — but to do three things for B launch:

1. **Document the unification strategy:** commit to a direction (single store vs multiple with strict boundaries) so that sub-projects don't make independent storage decisions that conflict later. The working hypothesis: keep multiple stores for their specialized strengths (LightRAG for graph-based knowledge retrieval, ChromaDB for dense vector search, JournalDB for chronological personal entries, SQLite for structured system state) but enforce routing through a single `StorageRouter` class that every service calls, rather than letting each service choose its own backend ad-hoc.

2. **Enforce existing routing rules automatically:** the rules in `CLAUDE.md` (KB → LightRAG, journal → JournalDB, MCP entities → server-memory) must be enforced by code, not by convention. A `StorageRouter` class that rejects writes to the wrong store and logs violations. Tests that verify every write path uses the router. No agent or service should import a storage backend directly — they all go through the router.

3. **Add fallback for empty results:** the current `query_knowledge_base()` behavior where LightRAG returns `[no-context]` or `no relevant document chunks` must automatically fall back to ChromaDB, not require the caller to handle the fallback. The StorageRouter owns this logic so every query path benefits from it.

The full unification (single store decision, migration, deduplication) is post-launch work. The B-launch goal is: stores stay separate, routing is enforced, fallback is automatic, and no new data-loss bugs are introduced.

#### Stack Decision

The stack stays as-is for B launch: **Flask + Next.js + MLX + LightRAG**. Flask vs FastAPI evaluation is deferred to post-launch. The current stack works; migrating it is a distraction from shipping.

#### Layer 0 Tooling Pre-Flight — Optimization Pass

Before any Layer 1 work begins, the surrounding infrastructure must be stripped to essentials. Current state: ~35 skills, 9 Claude plugins, 8 MCP servers, and 30+ scripts — many unused, overlapping, or dead-weight. This bloat burns tokens on every agent session and causes agents to load irrelevant context.

**Phase A — Cut MCP servers first (lowest risk):**
Remove from `.claude/mcp.json`: dorothy-socialdata, dorothy-x, dorothy-world. The orchestrator gets stripped to a simple launcher (if kept at all) since CrewAI replaces its routing. Result: 8 → 4 MCP servers (kanban, telegram, vault, drawthings). Verify `./kitty status` still works after cut.

**Phase B — Cut skills second:**  
Unlink 18 skills from `.claude/skills/` (symlinks to `~/.agents/skills/`). Keep 18: fix-and-verify, parallel-subagents, overnight-queue, prompt-answer-quality, tdd, caveman, grill-me, spec-to-impl, demo, audit, zoom-out, all firecrawl-* (11), skill-creator, find-skills. Cut: domain-news, grill-with-docs, improve-codebase-architecture, recommend, setup-matt-pocock-skills, to-issues, to-prd, triage, write-a-skill, execution, improve, planning, reasoning, ship, think, world-builder, ast-grep, agent-browser (reactivate if page navigation is needed). Verify superpowers plugin still loads after cuts.

**Phase C — Cut plugins third:**  
Disable 5 Claude plugins: security-guidance, pr-review-toolkit, agent-sdk-dev, pyright-lsp, frontend-design. Keep 4: commit-commands, code-review, superpowers, feature-dev. Verify Claude.app/OpenCode sessions load correctly.

**Phase D — Clean scripts last:**  
Keep 7 scripts: clear-and-test.sh, quick-smoke.sh, checkpoint.sh, run_gates.sh, validate.sh, golden_demo.sh, context_pack_generator.py (+ dorothy_bridge.py which is new). Archive remaining 25+ scripts to `scripts/archive/`. Verify full test suite still passes.

**Phase E — Write Dorothy bridge daemon:**  
The `scripts/dorothy_bridge.py` daemon that polls Kanban, spawns CrewAI/Crush/Aider, and posts Telegram updates. ~150 lines. Test: create a Kanban card with `#build`, verify the bridge detects it and starts the pipeline.

**Phase F — Optimize reference docs:**  
Trim CLAUDE.md and AGENTS.md to ~80 lines each. Keep critical gotchas (storage routing, port split, Werkzeug flag, TokenCapture leak). Cut narrative prose. Run `context_pack_generator.py` to verify context packs still contain essential reference data.

All phases commit separately. Each phase verifies before proceeding.

#### Development Workflow (Automated)

```
Jacob describes need → Dorothy Kanban card created → Bridge daemon detects card
  → CTO (Sonnet) writes approved spec
  → Bridge routes to CrewAI pipeline (for knowledge work) OR Crush/Aider (for code)
  → Builders commit, tests run, Sonnet reviews
  → Bridge posts Telegram ping: "Ready for demo"
  → Jacob demos, says yes/no/redirect
```

1. **Intake:** Jacob describes what he wants in plain English. Appears as a new Kanban card.
2. **Spec:** The CTO (Sonnet) auto-generates a lightweight spec defining scope, allowed/forbidden files, acceptance criteria, and the mission test question. Approved specs get tagged `#build` on Kanban.
3. **Detect:** The bridge daemon (`scripts/dorothy_bridge.py`) polls Kanban every 30 seconds. On detecting a `#build` card, it reads the spec and routes execution.
4. **Build:** CrewAI pipeline (for knowledge ingestion: search → digest → embed → organize) or Crush/Aider (for code). Parallel lanes assigned by spec boundaries. All run on cheap API models with local fallback.
5. **Demo:** Feature is running. Jacob reviews the experience (not code). Approves or redirects.
6. **Ship:** Sonnet review. Full test suite passes. Commit lands. Bridge posts "Done" to Telegram.

The bridge daemon handles the manual coordination that currently requires an agent actively checking Kanban — it converts "card created" into "pipeline spawned" automatically. Checkpoint HANDOFF files are written at each completion gate so no state is lost to usage limits.

### Layer 1 — The Product (6 Sub-Projects, Vision-First Order)

Layer 1 is the product users interact with. The sub-projects are ordered by what a user feels first, not by what's easiest to build. Onboarding comes before architecture cleanup because a first-time user's experience of "Kitty learning my world" is the entire product — the rest is infrastructure that makes that experience reliable.

| # | Sub-Project | What It Delivers | Why This Order |
|---|-------------|------------------|----------------|
| 1 | Personal Onboarding Pipeline | Kitty learns the user's world automatically | User's first experience. If this doesn't feel like being known, nothing else matters |
| 2 | Memory and Continuity | Kitty holds the thread across sessions | The second session is where trust is built or lost |
| 3 | Unified Command System | One consistent way to interact | The most user-visible gap in the current architecture |
| 4 | Test Coverage and Reliability | Confidence that nothing silently breaks | Technical debt that blocks speed on everything else |
| 5 | UX Polish | Mobile, accessibility, error handling, visual warmth | Makes the reliable system feel like a companion |
| 6 | Launch Operations | Setup wizard, user guide, known limitations, beta feedback path | Everything needed for someone else to actually use it |

**Post-launch (non-blocking):** Tool Runtime + Specialist Runtime — internal architecture deepening that doesn't change what users see.

---

## 4. Mission Test for Each Sub-Project

Each sub-project is testable against the mission. If the answer to the test question is no, the sub-project design is wrong.

> **1. Personal Onboarding Pipeline:**  
> "Does this make Kitty feel like it's coming to know you, or like filling out a setup form?"

> **2. Memory and Continuity:**  
> "When you return after three days away, does Kitty pick up the thread, or do you have to re-explain yourself?"

> **3. Unified Command System:**  
> "Can a user express what they need in their own words and have Kitty route it correctly, or do they need to memorize slash commands?"

> **4. Test Coverage and Reliability:**  
> "Does the system hold up under real use without silently degrading the experience of being known?"

> **5. UX Polish:**  
> "Does the interface feel like a warm companion, or a developer console that happens to respond in full sentences?"

> **6. Launch Operations:**  
> "Can a friend who's never seen this codebase set it up, complete onboarding, and have a real conversation — without Jacob's help?"

---

## 5. Constraints

These are the real-world limits the launch plan must work within. None are negotiable for B launch.

### Hardware

- **Apple M1, 8GB RAM.** The primary development and target machine. Cannot run large local models alongside the app server, ChromaDB, and LightRAG simultaneously. Parallel agent work must use cloud APIs (Groq, OpenRouter, DeepSeek). Local models (MLX `Qwen3.5-4B-4bit`) are reserved for offline/private mode and lightweight tasks.
- **Disk space:** the repo + models + embeddings + logs fits comfortably on a 256GB SSD. Embedding storage is the primary growth vector and needs monitoring but not yet optimization.

### Founder Is Non-Technical

Jacob does not read code. He does not review PRs. He does not parse stack traces. All progress is reported in plain English through the Dorothy Kanban board and Telegram notifications. Reviews are demo-driven: Jacob sees the feature working, reacts to the experience, and says yes/no/redirect. This is not a limitation to work around — it's a design constraint that shapes the entire operating system layer.

The implication: every agent in the system must produce outputs the CTO (Sonnet) can verify, and summaries that Dorothy can surface to Jacob. No raw agent output reaches Jacob directly.

### Pre-Commit Hook Runs Full Test Suite

The current pre-commit hook runs all 399 tests (~47 seconds). This means every commit takes nearly a minute. For single-agent serial work, this is manageable. For parallel agents each committing multiple times per sub-project, it becomes a significant drag on velocity.

**Mitigation:** a "fast dev gate" (subset of critical tests) for work-in-progress commits, with the full suite reserved for merge-ready commits. See Open Questions for the unresolved fast-gate design.

### 5 Fragmented Memory Stores

As detailed in Layer 0, the five storage backends are a known source of bugs. Wrong-routing (putting KB content in JournalDB, or journal entries in LightRAG) is the #1 cause of data-loss bugs in this project. The current routing rules are documented in `CLAUDE.md` under Project Context, but enforcement is manual and fragile.

The constraint for B launch is: the stores must stay as-is, but routing correctness must be enforced automatically (tests, linters, or runtime checks) rather than relying on agent discipline.

### MCP Agent Bundle in Dirty Tree

Files for KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, and Overnighter exist uncommitted in the working tree. They are incomplete, untested, and in some cases reference non-existent dependencies. They cannot be pulled into B launch without a full audit, which is deferred to Phase 6+.

See `docs/PARKED_FEATURES.md` for full parking documentation.

### Skills and Plugins Not Optimized

The current `.claude/skills/` directory, Agent Skills block in `AGENTS.md`, and project-level skill infrastructure have grown organically. Skills may overlap or conflict. Before B launch, a clean install pass is needed: remove unused skills, ensure skill descriptions trigger correctly, and verify that the skills loaded in `AGENTS.md` match what's in `.claude/skills/`.

---

## 6. Blessings

These are the strengths the launch plan can lean on. Each one is a reason the B launch is achievable.

### Free Model Stack Is Genuinely Good

Multiple providers offer capable free-tier models that can handle builder-agent workloads:
- **OpenRouter free:** `qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`, `openai/gpt-oss-120b:free`
- **Groq free tier:** `llama-3.3-70b-versatile`, `qwen/qwen3-32b`
- **Local MLX:** `Qwen3.5-4B-4bit` (offline, private, zero cost)

These are not toy models. They can generate code, write tests, and follow structured instructions. For parallel builder agents that don't need the highest reasoning quality, free models are sufficient.

### Cheap Models Are Dirt Cheap

When reliability matters more than zero cost, the paid-but-cheap tier is accessible:
- **DeepSeek V4 Flash:** ~$0.001 per 1K tokens
- **Gemini 2.5 Flash:** similarly cheap, fast
- **Groq paid tier:** deterministic, low queue risk

At these prices, a full day of parallel builder-agent work costs cents, not dollars.

### Dorothy Already Wired

Dorothy MCP is already connected to Claude Code through hooks, with Orchestrator, Kanban, Telegram, and DrawThings components. The infrastructure exists. The Layer 0 work is configuration and integration, not greenfield development.

### Telegram Means Phone Notifications

Because Dorothy can send Telegram messages, Jacob gets push notifications on his phone when agent work completes, when a demo is ready, or when something blocks. This transforms the experience from "Jacob needs to check on progress" to "progress finds Jacob."

### Crush Runs Non-Interactively

Crush accepts tasks and returns results without a conversation loop. This is the critical property for parallel execution. Interactive agents (where the human or coordinator has to respond to each output) can only run one at a time. Non-interactive agents can run N at a time — the coordinator sends a task, the agent returns a result, and the coordinator reviews all results in a batch.

In practice: Sonnet writes a spec for the Onboarding Pipeline's domain-selection wizard. It spawns a Crush instance with the spec, assigns it the `garage-ui/app/components/onboarding/` directory as its lane boundary, and moves on. Crush works autonomously — generating components, writing tests, handling import structure — and returns a diff plus a test result. Sonnet reviews it later in a batch with results from the parallel builder working on the backend ingestion pipeline. No interactive back-and-forth. No waiting for "what should I do next?" prompts.

This is the engine that makes the 3–4 week parallel timeline possible. Without non-interactive agents, parallel execution degenerates into serial execution with context-switching overhead.

### Aider Installed

Aider provides AI pair-programming with any local or cloud model. It is the tool for tasks that benefit from a tighter edit-verify loop — small refactors, test generation, documentation updates. Together with Crush, it covers the full spectrum from autonomous batch work to interactive refinement.

### 399 Passing Tests as Safety Net

The current test suite passes cleanly at 399 tests. Every commit must continue to pass it. This provides a baseline: any sub-project that introduces failures is immediately caught. The test suite is not yet comprehensive (route coverage is ~28%), but what exists works and the pre-commit hook enforces it.

### 5+ API Providers + Research Tools = Resilience

Kitty has API keys or access configured for:
- **Anthropic** (Claude Sonnet, Opus via Cursor subscription)
- **DeepSeek** (V4 Flash for builders)
- **OpenRouter** (routing to 200+ models, free tier fallback)
- **Gemini** (paid subscription, API key)
- **Groq** (paid and free tiers)
- **Tavily** (web search for onboarding research)
- **Firecrawl** (web scraping and page extraction for onboarding)
- **Exa** (complementary web search — API key available, activated as needed for deeper research)
- **Honcho** (user state persistence)

No single provider going down can block work. If one API has an outage, the model router falls back to the next tier. Research tools are layered: Tavily for fast search, Firecrawl for deep page extraction, Exa as complementary backup for broader web coverage.

### Local Coding Models via Ollama

`deepseek-coder-v2:16b` and `qwen2.5-coder:7b` are available locally through Ollama for offline coding work. These don't compete with the app server for memory at the same time, but they provide a fallback when cloud APIs are unavailable or when privacy requires local-only processing.

### Whisper via Groq for Fast Voice Transcription

Groq's hosted Whisper implementation provides voice transcription that is significantly faster than local models. This is critical for the voice pipeline (Browser MediaRecorder → `/api/transcribe` → text) and for any voice-first companion features.

### DrawThings for Local Image Generation

DrawThings provides local image generation capability, which supports mascot visuals, mood-based imagery, and any visual companion features without cloud dependencies or API costs.

---

## 7. Model Routing Strategy

Every agent in the system routes through this strategy. No agent picks a model on its own judgment — the routing is defined here and enforced by the coordinator.

### Primary Tier — Cheap and Reliable (Default)

| Model | Provider | Cost (/Mtok) | Use Case |
|-------|----------|-------------|----------|
| `deepseek/deepseek-v4-flash` | DeepSeek / OpenRouter | $0.28 | Primary builder — code gen, test writing, file edits. Best balance of price and reliability |
| `qwen/qwen3-235b-a22b-2507` | Qwen / OpenRouter | $0.10 | Budget builder — huge MoE model at absurdly low price. Great for high-volume work |
| `mistralai/mistral-small-24b-instruct-2501` | Mistral / OpenRouter | $0.08 | Cheapest non-free builder — lightweight tasks, classification |
| `qwen/qwen3.5-flash-02-23` | Qwen / OpenRouter | $0.26 | Fast fallback, similar tier to DeepSeek Flash |
| `google/gemini-2.5-flash` | Gemini API | $2.50 | Fast, good for interactive features. Only when latency matters more than cost |

**Default for builders: `deepseek-v4-flash`.** It's reliable, deterministic, and at $0.28/Mtok a full day of parallel building costs $1-3. When budget is tight, drop to `qwen3-235b-a22b` at $0.10/Mtok.

### Backup Tier — Free (Accept Rate Limits)

| Model | Provider | Use Case |
|-------|----------|----------|
| `qwen/qwen3-coder:free` | OpenRouter | Code generation when primary is down |
| `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter | General reasoning, fallback |
| `qwen/qwen3-next-80b-a3b-instruct:free` | OpenRouter | Alternative free route |
| `google/gemma-3-27b-it:free` | OpenRouter | Lightweight free option |

Free models have rate limits, queues, quality variance, and outage risk. They are the parachute, not the daily driver.

### Premium Tier — Reserved

| Model | Use Case | When |
|-------|----------|------|
| Claude Sonnet | Architecture design, code review, multi-file synthesis, Jacob-facing summaries | CTO duties, merge reviews, design doc writing |
| Claude Opus | Highest-leverage strategic decisions only | Major architectural crossroads, launch go/no-go |

**Rule:** if Sonnet can do it, Opus doesn't see it. Opus is invoked maybe once per phase, at most.

### Local Tier — Offline and Private

| Model | Runtime | Use Case |
|-------|---------|----------|
| MLX `Qwen3.5-4B-4bit` | Apple MLX | Offline mode, private conversations, lightweight tasks |
| Ollama `qwen2.5-coder:7b` | Ollama | Offline code work |
| Ollama `deepseek-coder-v2:16b` | Ollama | Offline heavy code work (if memory permits) |

### Routing Decision Flow

When a task needs a model, the coordinator follows this decision tree:

```
Task arrives → Is this a strategic decision affecting architecture?
  YES → Claude Opus (premium, reserved)
  NO  → Is this a code review or design doc that needs architectural judgment?
    YES → Claude Sonnet (premium, reserved for CTO duties)
    NO  → Is this a builder task (code generation, test writing, file edits)?
      YES → Try primary tier (DeepSeek Flash / Gemini Flash / Groq paid)
        API available? → YES → Use it
        API unavailable? → Try backup tier (OpenRouter free / Groq free)
          Backup available? → YES → Use it (accept potential quality variance)
          Backup unavailable? → Try local tier (MLX Qwen3.5 / Ollama)
            Local available? → YES → Use it
            All tiers exhausted? → Mark task as blocked on Dorothy Kanban
      NO  → Is this offline/private work?
        → Use local tier (MLX / Ollama)
```

**Concrete examples of routing decisions:**

| Task | Model | Tier | Why |
|------|-------|------|-----|
| "Write the domain-selection wizard component" | `deepseek-v4-flash` | Primary (cheap) | Code generation with clear spec — needs reliability, not reasoning depth |
| "Write tests for the onboarding pipeline" | `deepseek-v4-flash` | Primary (cheap) | Structured, repetitive work — cheap model is sufficient |
| "High-volume batch work — 50 test fixtures" | `qwen3-235b-a22b` | Primary (budget) | Huge volume, low complexity — use the $0.10/M model |
| "Review all onboarding code before merge" | Claude.app/Sonnet | Premium (reserved) | CTO duty — architectural judgment needed |
| "Should we adopt FastAPI or stay on Flask?" | Claude.app/Opus | Premium (reserved) | Strategic architectural decision |
| "Personal journal entry — private, offline" | MLX Qwen3.5-4B | Local | Privacy requirement overrides model quality |
| Primary API down, building CommandEngine | `qwen3-coder:free` | Backup (free) | Accept quality variance, keep work moving |
| CrewAI digest stage (summarize search results) | `deepseek-v4-flash` | Primary (cheap) | Needs comprehension — cheap models do this well |
| CrewAI embed stage (chunk and store) | MLX Qwen3.5-4B | Local | Pure tool chain — no reasoning needed, save the API cost |

### CrewAI Pipeline Routing (Hybrid)

For the onboarding knowledge pipeline, stages are split by what benefits from smarter models:

| Pipeline Stage | Model Tier | Why |
|---------------|-----------|-----|
| **Search** (Tavily/Firecrawl/Exa web search) | Primary cheap API | Needs reasoning to evaluate source quality and formulate good queries |
| **Digest** (summarize search results) | Primary cheap API | Needs comprehension — cheap models do this well |
| **Embed** (chunk and store in LightRAG/ChromaDB) | Local MLX Qwen3.5-4B | Pure tool chain — chunk text, call embedding API, store. No reasoning needed |
| **Organize** (update knowledge graph edges) | Local MLX Qwen3.5-4B | Mechanical — extract entities, link relations. Pattern matching, not deep reasoning |

This hybrid saves ~40% on pipeline API costs (the two most expensive stages — embed and organize — run locally for free) while keeping the stages that benefit from smarter models on the cheap API tier. When budget is exhausted, all stages fall back to local MLX — slower but $0.

### Why Cheap-First, Not Free-First

Free tiers have rate limits, queues, quality variance, and outage risk. They introduce unpredictability into agent workflows. Cheap models like DeepSeek Flash are deterministic and reliable for the kind of structured execution builder agents need. Free is the safety net, not the daily driver.

**Real cost estimates for the 4-week build phase:**

| Cost Item | Estimate |
|-----------|----------|
| DeepSeek V4 Flash as primary ($0.28/Mtok) | $1-3/day for 3 parallel builders |
| CrewAI pipeline runs (4 agents × 5 domains × 5 friends) | $2-5 total |
| Full 4-week build phase | $50-100 max |
| Free fallback (qwen3-coder:free, llama-3.3-70b:free) | $0 |
| Paid subs (Cursor Claude, Gemini, Codex) | Already paid, reset every 5 hours |

At $0.28/Mtok, the cost difference between free and cheap is negligible, but the reliability difference is substantial. The backup tier exists for the day DeepSeek has an outage, not as a cost-saving measure.

Budget is flexible — no hard cap. Use cheap API when parallel speed matters, fall to local MLX when budget is tight.

---

## 8. Agent Team Structure

### Team Roster

| Role | Agent | Responsibilities |
|------|-------|-----------------|
| Chief Product Officer | **Jacob** | Vision, gut-feel approvals, demo review, "yes/no/redirect." Never reads code |
| Chief Technology Officer | **Claude.app/Sonnet** (Opus reserved for strategic decisions) | Architecture, code review, design docs, technical coherence. Reviews all code before merge |
| PM Automation | **Dorothy MCP** (kanban, telegram, vault) | Task board, push notifications to Jacob's phone, durable spec/handoff storage |
| Bridge Daemon | **`dorothy_bridge.py`** | Polls Kanban, spawns CrewAI/Crush/Aider, posts Telegram updates. Runs independently |
| Pipeline Agents | **CrewAI** (searcher, digester, embedder, organizer) | Sequential knowledge ingestion for onboarding. Runs on cheap API with local fallback |
| Review Pair | **AutoGen / CrewAI-hybrid** | Adversarial code review — second agent challenges Sonnet's review. Reserved for merge gates |
| Builder Agents | **Crush + Aider** (cheap-tier models, parallel) | Code generation, test writing, file edits. Work on independent lanes |
| Code Reviewer | **Claude.app/Sonnet** | Quality gate. Every merge gets Sonnet review. Catches scope drift, routing violations, security issues |

### Information Flow

```
Jacob (CPO)
  ↑ demos, status pings (Telegram)
Dorothy (PM)
  ↑ task completion reports
Claude Sonnet (CTO)
  ↑ code review, architecture decisions
  ↑ merged diffs
Crush + Aider (Builders)
  ↑ parallel execution on independent lanes
  ↑ cheap AI models (DeepSeek Flash, Gemini Flash, Groq)
```

### Coordination Failure Modes and Recovery

Parallel agent execution introduces failure modes that don't exist in serial work. The coordinator must handle these without Jacob ever needing to intervene:

| Failure Mode | Detection | Recovery |
|-------------|-----------|----------|
| **Builder agent dies mid-task** (usage limit, model error, process crash) | No result returned within time budget; coordinator's heartbeat check fails | Read the HANDOFF checkpoint written before the task started. Spawn a fresh builder with the same spec and lane assignment. The checkpoint includes current file state so the new agent can diff and resume |
| **Two builders produce conflicting edits** (coordinator lane assignment was imperfect) | Sonnet review detects overlapping file changes in two builders' diffs | Accept the primary lane's changes (the one that had stricter file ownership defined in the spec). Log the conflict for the coordinator to improve future lane boundaries. The rejected builder's work is not lost — it's parked and manually reconciled if valuable |
| **Model routing failure** (primary API down, budget exhausted, rate limit hit) | Builder returns an error instead of a diff. Error code identifies the failure type | Coordinator reroutes to backup tier automatically. If backup also fails, marks the task as blocked on Dorothy Kanban with the specific failure reason. Jacob sees "Model API unavailable — retrying on backup tier" rather than "build failed" |
| **Scope drift** (builder agent adds code outside its allowed files) | Sonnet review catches files in the diff that aren't in the spec's allowed-files list | Reject the entire diff. The builder is re-spawned with explicit "FORBIDDEN FILES" instruction reinforced. Repeated scope drift from the same builder may indicate the spec or lane boundaries were unclear — coordinator revises |
| **Test regression from unrelated area** (builder's change broke something in another subsystem) | Pre-commit hook or CI catches test failures in files the builder didn't touch | The test failure is diagnostic, not accusatory. The coordinator spawns a fix-and-verify agent to identify the root cause. If the fix is small and contained, the coordinator applies it. If it's a deeper integration issue, the coordinator sequences the work — the current sub-project pauses, the fix takes priority, then the sub-project resumes |

These recovery patterns mean that a builder failure does not become a Jacob-intervention. The coordinator handles it, Dorothy reports it, and work continues. Jacob only gets involved if the same failure repeats three times or the coordinator explicitly flags a decision it cannot make (e.g., "two fundamentally incompatible approaches to the same problem").

### Lane Discipline

Builders never work on the same files at the same time. The coordinator assigns explicit file boundaries before spawning parallel agents. No builder commits directly — the coordinator owns all merges. This prevents the most common failure mode of parallel agent execution: merge conflicts from overlapping edits.

When a spec defines allowed files as a directory (e.g., `garage-ui/app/components/onboarding/`), the coordinator checks that no other active lane has files inside that directory before spawning. If a potential conflict is detected, the coordinator either widens the lane boundary (if the tasks are truly independent within the directory) or sequences the work (if they would touch the same files).

The coordinator also enforces a rule: no two builders may touch the same import structure simultaneously. If Sub-Project 1 adds a new import to `src/api/__init__.py` and Sub-Project 3 also needs to modify that file, the coordinator sequences them — Sub-Project 1 commits first, Sub-Project 3 rebases on top.

---

## 9. Timeline

### Serial Execution (Single Agent)

If one agent builds everything sequentially: **6–8 weeks.**

This is the baseline. It assumes one builder working through sub-projects one at a time, with Sonnet review between each. Familiar, safe, slow.

### Parallel Execution (Approach B)

If multiple agents work in parallel on independent lanes: **3–4 weeks.**

This assumes:
- Layer 0 infrastructure (Dorothy PM, agent coordination, fast dev gate) is set up in week 1
- Layer 1 sub-projects 1–3 (Onboarding, Memory, Commands) can run partially in parallel once their interfaces are defined
- Sub-projects 4–6 (Tests, UX, Launch Ops) run in parallel after 1–3 are stable

The parallel timeline is aggressive but grounded: most sub-projects touch different subsystems (backend vs frontend vs docs vs tests), so file conflicts are minimal. The coordinator's lane discipline keeps them separate.

### Phase Breakdown

| Week | Layer 0 | Layer 1 |
|------|---------|---------|
| 1 | Dorothy PM Kanban configured, Telegram notifications wired, coordinator pipeline functional, fast dev gate designed | Sub-Project 1: Onboarding Pipeline domain-selection wizard and agent dispatch built |
| 2 | Layer 0 validation gate (Dorothy shows real tasks, Telegram delivers real ping, one checkpoint survives usage-limit cutoff) | Sub-Project 1 completes (ingestion, embedding, first-conversation demo). Sub-Project 2: Memory & Continuity begins (session summaries, journal integration) |
| 3 | Memory routing enforcement in place, coordinator managing 2 parallel builder lanes | Sub-Projects 2–3 in parallel (Memory & Commands in different subsystems). Sub-Project 4: Test Coverage begins expanding route tests |
| 4 | — | Sub-Project 3 (Unified Commands) completes. Sub-Projects 4–6 begin parallel work (tests + UX + launch ops touch different areas) |
| 5 | — | Sub-Projects 4–6 complete. Integration testing. Jacob demos full launch experience |
| 6 | — | Launch validation gate: a real friend goes through setup → onboarding → conversation in < 30 minutes. Bug fixes from feedback. Final commit |

This is the optimistic path — assumes no major blockers, Jacob's demos pass on first or second try, and parallel lanes avoid merge conflicts.

### Realistic Path (Buffer Included)

The realistic path adds 2 weeks of buffer for:

- **Demo redirection:** Jacob approves the shape but redirects the feel. "This works but it doesn't feel like Kitty." A day or two per sub-project to adjust tone, language, and mascot presence to match the mission.
- **Integration friction:** even with lane discipline, two sub-projects that looked independent reveal a shared dependency. The coordinator spots it during review and sequences the work — one lane pauses while the other ships, then resumes. Cost: 1–2 days.
- **"It works on my machine":** the first friend who tries the setup wizard hits a failure Jacob never saw — wrong Python version, missing system library, port conflict with another app. Fixing these one by one during Sub-Project 6 is expected and budgeted.
- **MCP agent bundle decision:** if the team decides to audit and adopt parts of the KnowledgeGetter MCP server for the onboarding pipeline, that audit costs 2–3 days. If they build fresh, those days are absorbed into Sub-Project 1's build time.

**Realistic total: 5–6 weeks.**

This is still significantly faster than the 6–8 week serial baseline because the parallel execution model collapses independent work, even with buffers.

### When to Abandon Parallel and Go Serial

Parallel execution is not dogma. If the coordinator detects repeated lane conflicts, or if two sub-projects that were assumed independent turn out to share critical interfaces, the coordinator has authority to sequence them — pause one lane, let the other complete, then resume. The fallback from parallel to serial costs time but prevents the worse cost: two builders generating code against different assumptions about the same interface, producing a merge that takes longer to reconcile than building sequentially would have taken.

**Trigger condition:** two lane conflicts within the same sub-project pair, or one merge that takes more than 2 hours to reconcile. Either condition triggers a coordinator decision: either widen lane boundaries to eliminate the conflict, or sequence the work. This is a process decision the coordinator can make autonomously — Jacob doesn't need to approve sequencing adjustments.

---

## 10. Sub-Project Briefs

### Sub-Project 1: Personal Onboarding Pipeline

**Problem:** Today, a new Kitty instance knows nothing about the user. Every conversation starts from zero. To get value, the user must manually explain their interests, projects, people, and context — which is exactly the kind of setup labor that prevents adoption.

**Mission anchor:** The entire product thesis is "Kitty learns your world." If onboarding feels like filling out a form, the mission fails at the first touchpoint. The onboarding must feel like being discovered, not like being interviewed.

**Shape:** The user picks 3–5 domains that matter to them (work, side projects, hobbies, relationships, health, creative practice). Kitty dispatches agents that search, scrape, digest, embed, and organize information about those domains — drawing from the user's browsing history, local files (with explicit permission), named projects, and web research. The result is a structured knowledge graph that Kitty can reason about from session one.

The pipeline has four stages:
1. **Domain selection:** a warm, conversational wizard (not a form) that helps the user identify what matters. "What do you spend most of your time thinking about?" rather than "Select domain categories."
2. **Agent dispatch:** for each domain, Kitty launches research agents using Tavily for web search and Firecrawl for page extraction. Agents run in parallel on cheap models through Crush. The user sees progress — "I'm learning about your interest in audio equipment..." — not technical agent output.
3. **Ingestion and embedding:** raw research is chunked, embedded, and stored in LightRAG under strict routing. A domain index maps each domain to its knowledge graph subset so queries hit the right context.
4. **First conversation:** onboarding completes with a conversation, not a status screen. Kitty demonstrates knowledge: "I found that Sansui AU-7900 you mentioned — that's the 1970s integrated amplifier, right? What drew you to it?" The user feels known, not set up.

The wizard runs in `garage-ui` as a guided flow. It explains what's happening in plain English at every step. It handles failures gracefully — if a domain search returns nothing, Kitty tells the user honestly and asks if they want to try different terms or skip that domain. If the user walks away mid-onboarding, progress is checkpointed and resumes where they left off.

**Done looks like:** A technical friend completes onboarding in < 15 minutes, picks 3 domains, and Kitty can hold a coherent conversation about each one — referencing specific facts, projects, and relationships the user described.

**Files likely touched:** `garage-ui/app/components/onboarding/`, `src/services/onboarding_pipeline.py`, `src/agents/`, onboarding configs, knowledge ingestion pipeline.

**Dependencies:** Layer 0 coordinator must be functional (to dispatch research agents). Knowledge ingestion pipeline must route correctly to LightRAG. Frontend wizard must exist in `garage-ui`.

---

### Sub-Project 2: Memory and Continuity

**Problem:** Kitty currently starts fresh every session. There's no "last time we talked" recall, no journal integration, no sense of an arc. The user has to re-establish context every time, which destroys the companion feeling.

**Mission anchor:** Presence means continuity. If Kitty doesn't remember what you talked about last time — what worried you, what you decided, what you were working toward — it's not a companion. It's a search engine with a friendly tone.

**Shape:** Three components, each delivering a specific kind of continuity:

1. **Session-to-session recall:** After each session, Kitty writes a session summary to JournalDB — key topics discussed, decisions made, open threads, emotional tone. When the user returns, the morning brief includes a "Since we last talked..." section sourced from that summary. This is not a transcript dump — it's a curator selecting what's worth carrying forward. "You were frustrated with the project architecture last time. Did you get clarity, or is that still weighing on you?"

2. **Journal integration:** Kitty can write observations to the user's journal (`/journal` or natural language like "remember this") and read from it when relevant. Morning briefs surface journal entries from the same week or matching current topics. The journal is private — stored in JournalDB under the same strict routing that separates it from the knowledge base. The user controls what goes in: "don't put that in my journal" is honored immediately and retroactively.

3. **Correction and forget interface:** The user can say "that's wrong," "I changed my mind," or "forget I said that" in natural language during any conversation. Kitty updates its model of the user: adjusting knowledge graph edges, deprecating outdated facts, or removing things entirely. Corrections propagate — if the user says "I quit that job" and the job was referenced across 3 domains, Kitty updates all 3 rather than leaving stale references. The forget command is permanent and immediate: no "are you sure?" dialog, no persistence in logs. Being known means being correctable — and being correctable means corrections are taken seriously, not treated as edge cases.

A key design decision: memory is not infinite. Kitty doesn't try to remember everything. It remembers what the user signals as important (explicit journaling, recurring topics, emotionally charged moments) and lets the rest fade. This prevents the "uncanny archive" problem where a companion that remembers every trivial detail feels more like surveillance than presence.

**Done looks like:** A user opens Kitty after a 3-day gap. The morning brief references their last conversation accurately. They can ask "what was I working on?" and get a coherent answer. Saying "actually, I changed my mind about that" updates Kitty's model of their world.

**Files likely touched:** `src/services/memory/`, `src/services/journal/`, `src/api/brief.py`, `src/core/continuity.py`, JournalDB integration, ChromaDB session indexing.

**Dependencies:** Onboarding Pipeline must be complete (Memory & Continuity references the world model built during onboarding). JournalDB must be reliably routed. Storage routing enforcement from Layer 0 must be in place.

---

### Sub-Project 3: Unified Command System

**Problem:** Kitty's slash commands (`/stuck`, `/brief`, `/scrape`, `/specialist`, etc.) are scattered across `web.py` and `dispatcher.py`. There's no consistent parser, no help system, and no discoverability. The most user-visible part of the architecture is the most fragmented.

This is the top open loop in `docs/OPEN_LOOPS.md`: "Unified Command System (Candidate C): Consolidate slash commands... into a deep CommandEngine. This was attempted but shelved due to subagent failure and time constraints."

**Mission anchor:** Being known means the system understands what you're asking for without you having to speak its language. A unified command system means the user can express intent naturally, and the system routes it correctly — whether that's a slash command, a plain-English request, or a domain-specific query.

**Shape:** A single `CommandEngine` class that replaces scattered command handling with one coherent system. The design principles:

- **Declarative command registration:** each command (existing and future) registers itself with a name, description, argument schema, and handler function. No commands are hardcoded in routing logic. Adding a command means adding a registration, not modifying a dispatch switch statement.
- **Natural language routing:** the CommandEngine accepts both slash-command syntax (`/stuck`) and natural language ("I'm stuck, help me figure out what to do"). It classifies the intent and routes to the correct handler. Classification uses cheap models (Gemini Flash) — fast, deterministic, and the routing decision doesn't need premium reasoning.
- **Inline help:** `/help` lists all registered commands with descriptions. `/help <command>` shows detailed usage, examples, and what the command does to your data. `/help auto` shows what the auto specialist can do without the user needing to read external docs.
- **Consistent error handling:** every command returns errors in the same shape. No stack traces in chat. No "500 Internal Server Error" — errors are plain English: "I couldn't run that command because the knowledge base is temporarily unavailable. Want me to try again?"

This is architectural deepening, not scope expansion. The existing commands (`/stuck`, `/brief`, `/scrape`, `/specialist`, etc.) continue to work — they're just routed through the CommandEngine instead of scattered handler functions. The command set doesn't grow; the routing gets coherent.

**Done looks like:** Every existing slash command works through the CommandEngine. `/help` lists available commands with one-line descriptions. `/help <command>` shows usage. Errors are consistent and helpful no matter which command triggered them. No command handling remains in `web.py` or `dispatcher.py`.

**Files likely touched:** `src/core/command_engine.py`, `src/api/web.py` (reduce, don't expand), `src/api/dispatcher.py`, command registry, help system, tests for every command.

**Dependencies:** None strictly (this is architectural cleanup of existing functionality), but the Onboarding Pipeline and Memory & Continuity may introduce new commands that the CommandEngine must support.

---

### Sub-Project 4: Test Coverage and Reliability

**Problem:** Route test coverage is approximately 28%. Frontend components have no tests. Integration tests are sparse. The 399 existing tests pass, but they don't cover enough surface area to give confidence during rapid parallel development.

**Mission anchor:** Your companion silently forgetting things is worse than your companion admitting uncertainty. Reliability — the boring, unglamorous kind — is what makes presence trustworthy. If Kitty's memory degrades or its commands silently break, the user stops trusting it.

**Shape:** Three tracks, each with a concrete target:

1. **Route coverage (28% → 80%+):** Write tests for every API route in `src/api/`. Each route gets a test for the happy path (200 with valid input), the error path (4xx with invalid input), and the edge case (empty body, missing fields, unexpected content types). Prioritize routes that touch user data — write routes (journal, knowledge queries, onboarding) get tested first because silent data corruption is the highest-severity bug class in this project. Read routes (briefs, status) are tested second.

2. **Frontend component tests (0 → 10+):** Basic render and interaction tests for core `garage-ui` components. Each test verifies that the component renders without crashing and responds correctly to the primary user action (click, type, submit). Components tested: ChatInput, MessageBubble, BriefCard, OnboardingWizard, CommandBar, MascotDisplay, ErrorBoundary, SettingsPanel, DomainSelector, JournalEntry. These are smoke tests, not exhaustive UI tests — they catch the "component doesn't render at all" class of regression, which is the most common frontend failure mode in rapid parallel development.

3. **Integration tests (0 → 3+):** Three end-to-end flows that cross subsystem boundaries: (a) Onboarding → knowledge query — user completes domain selection, agents ingest content, user asks a domain question and gets a correct, sourced answer. (b) Journal → morning brief — user writes a journal entry, next session the morning brief references it. (c) Voice → transcription → response — user records audio, transcription succeeds, Kitty responds appropriately. These integration tests are the safety net for the most user-visible flows.

**Fast dev gate:** For work-in-progress commits during parallel development, a subset of tests runs in under 10 seconds — route smoke tests (no deep assertions, just 200 checks), component render tests, and the integration tests' setup/teardown (not full execution). The full suite runs on pre-commit as it does today. The fast-gate design is an open question (see Open Questions) but the requirement is clear: catch catastrophic breakage in under 10 seconds.

**Done looks like:** 80%+ route test coverage. Core frontend components have tests. At least 3 integration tests pass. The fast dev gate exists and catches regressions in critical paths in under 10 seconds. No existing tests are broken.

**Files likely touched:** `tests/` (new and expanded), `garage-ui/__tests__/`, `scripts/fast-gate.sh`, test fixtures, test configuration.

**Dependencies:** Sub-Projects 1–3 must be stable enough that their interfaces are testable. Fast dev gate design must be decided (see Open Questions).

---

### Sub-Project 5: UX Polish

**Problem:** The current interface works but doesn't feel like a companion. It feels like a developer tool. Mobile experience is broken or untested. Error states are technical. Accessibility is absent. The gap between "this functions" and "this feels like Kitty" is wide.

**Mission anchor:** Presence is felt, not documented. If the interface is cold, technical, or confusing, the mission fails even if the backend is perfect. Mascot motion, mood-based visuals, warm error messages, and a smooth mobile experience are first-class product requirements — not decoration.

**Shape:**
- **Mobile responsive:** `garage-ui` works on a phone screen (375px width minimum). Chat, morning brief, and onboarding are the priority flows — they must be usable one-handed. Layout switches from sidebar+main to single-column. The chat input stays fixed at the bottom of the screen like a messaging app. Font sizes are readable without zooming.
- **Mascot and mood:** The Kitty mascot appears in the interface and reflects state — idle (gentle breathing animation), listening (ears forward, attentive), thinking (eyes moving, slight tilt), responding (warm expression), concerned (when the user expresses distress), celebrating (when the user reports a win). These are presence cues, not gamification. The mascot doesn't distract — it belongs. Mood transitions are smooth, not jarring.
- **Error states:** Every error is explained in plain English with clear next steps. No "500 Internal Server Error." No "An unexpected error occurred." The user always knows: what went wrong, why (in non-technical terms), and what to do next. "I couldn't reach the knowledge base — this usually means the server needs a restart. Here's how to do that: `./kitty restart`. Or want me to try again?"
- **Accessibility:** Keyboard navigation for chat (Tab to input, Enter to send), screen reader support for core flows (ARIA labels on message bubbles, brief cards, command output), sufficient color contrast (WCAG AA minimum for all text), focus indicators visible on all interactive elements.
- **Loading states:** Every async action shows a clear loading state. Not a generic spinner — a context-specific indicator. "Searching for information about your audio equipment..." with progress dots that fill as agents complete their research. Estimated time when knowable. Cancel option on any operation that takes more than 10 seconds.

**Anti-goal:** This is not a visual redesign. The existing component structure and layout stay. UX Polish means making what exists feel like a companion rather than a console — sanding rough edges, adding warmth, fixing breakage. It does not mean building new visual components from scratch.

**Done looks like:** A user on their phone can open Kitty, read the morning brief, and have a conversation. The mascot shows expression changes that reflect context. Errors are human-readable and actionable. A screen reader can navigate the chat and brief flows.

**Files likely touched:** `garage-ui/app/` (CSS, components, layout), mascot assets, mobile breakpoints, accessibility attributes, error component.

**Dependencies:** All functional sub-projects (1–3) must be complete — UX Polish layers on top of working features, not stubs.

---

### Sub-Project 6: Launch Operations

**Problem:** Right now, setting up Kitty requires knowing which files to touch, which environment variables to set, and which commands to run. There's no guided setup, no user-facing documentation, no feedback path, and no list of known limitations. A friend cannot set this up without Jacob's help.

**Mission anchor:** The launch is the first test of the mission. If a friend can't get Kitty running and feel known by it, the mission hasn't shipped — it's still just a project on Jacob's laptop.

**Shape:**
1. **`./kitty setup` wizard:** A guided CLI flow (not a wall of instructions) that:
   - Checks prerequisites: Python 3.12+ installed, Node.js 18+ installed, Ollama available (optional, for local models), MLX available (optional, for Apple Silicon acceleration), port 5001 free, port 3000 free.
   - Sets up environment: creates `.env` from template, prompts for API keys (with clear explanations of what each key does and whether it's optional — "Tavily is used for web search during onboarding. Without it, onboarding will be limited to local files and your manual input.")
   - Initializes storage: runs database migrations, creates required directories, seeds initial config.
   - Launches the app: starts backend on 5001, frontend on 3000, opens browser to the onboarding page.
   - Handles failures: every failure mode has a plain-English explanation and a fix. "Port 5001 is in use by another application. Run `./kitty stop` to free it, or set KITTY_PORT=5002 to use a different port." No stack traces. No "check the logs."
2. **README as user guide:** The current README is rewritten for users, not developers. Sections: What Kitty Is (mission statement + tagline, 3 sentences), Quick Start (setup wizard, 4 steps), What Kitty Can Do (morning briefs, journaling, domain conversations, specialists — each with a one-sentence example), What Kitty Can't Do Yet (honest limitations list), Getting Help (beta feedback path). Technical details (architecture, contributing, development setup) move to `CONTRIBUTING.md`.
3. **Known limitations:** `docs/known-limitations.md` — an honest, unmarketed list. "Kitty's memory works best within a single domain. Cross-domain connections (e.g., how your work stress relates to your health) are limited." "Voice transcription works well in quiet environments. Background noise reduces accuracy." "Onboarding requires internet access for web research. Offline-only users can manually describe their domains." This document builds trust. Users who know the limits are less frustrated than users who discover them.
4. **Beta feedback path:** A lightweight way for early users to report issues. Options: a shared Google Doc with a simple template, a Telegram group, or a GitHub Discussions board on the repo. The key requirement: Jacob doesn't become tech support. Reports go to Dorothy Kanban as triage items, and Sonnet reviews them for severity. Jacob only sees summaries: "Two friends reported the setup wizard failing on M2 Macs. Fix in progress."

**Design principle:** Launch operations treats the person setting up Kitty as a user, not a developer. If a step requires knowing what `pip` is, the step explains it. If an error message mentions a port number, the error message also explains what a port is. No assumed knowledge beyond "I can open Terminal and follow instructions."

**Done looks like:** A technical friend clones the repo, runs `./kitty setup`, completes onboarding, and has a real conversation about their chosen domains — all in under 30 minutes, without asking Jacob any questions. The README reads like a user guide. Known limitations are documented honestly.

**Files likely touched:** `scripts/setup.sh` or `./kitty setup` command, `README.md`, `docs/known-limitations.md`, beta feedback system, error handling in launch scripts.

**Dependencies:** Everything else. Launch Operations is the final integration and documentation pass. It assumes sub-projects 1–5 are complete and stable.

---

## 11. Parking Lot — Out of Scope for B Launch

These features are documented in `docs/PARKED_FEATURES.md`. They are not part of the B launch. Each has a revival trigger — the condition that makes it safe to revisit — but none of those conditions are met yet.

| Feature | Why Parked | Revival Trigger |
|---------|-----------|-----------------|
| **KnowledgeGetter MCP Server** | MCP expansion is forbidden. Implementation is incomplete, untested, and Phase 6+ work per the master plan. | Phase 0–4 control work stable, Jacob explicitly approves MCP expansion through intake |
| **MCP Agent Bundle** (KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, Overnighter) | Same as above. Bundle appeared as dirty work that claimed completion before validation. | Jacob explicitly approves MCP expansion after workspace separation preflight is clean |
| **Physical `kitty-system` Split** | Separation of durable system/control docs from runnable app. Migration closeout not yet complete. | File manifest, migration spec, import/path audit, rollback plan, and verification gates complete |
| **Full Builder Automation From Intake** | Current control layer only provides deterministic intake classification and explicit builder contract. Full automatic spec generation is parked. | Stable `docs/BUILDER_INTAKE.md`, `docs/BUILDER_DIRECTIVE.md`, and agreement on worker lane ownership |
| **Tool Runtime + Specialist Runtime** | Post-launch architecture deepening. Separates tool execution from specialist domain logic. | Post-launch, after Layer 1 sub-projects 1–6 ship |
| **Source-Grounded Specialist Engine** | Specialists currently operate on embedded knowledge without verified source grounding. Risk of hallucination without this. | Post-launch architecture track (see `docs/plans/gemini-architecture-priorities-2026-04-30.md`, tag `GEMINI-ARCH-PRIORITIES`) |
| **Proactive Idle Nudging** | Kitty prompting the user when idle — potentially valuable but risks feeling invasive if done wrong. Design needed. | Post-launch, after Memory & Continuity is stable |
| **Audio Specialist KB Candidate** (Sansui AU-7900 session text) | Specialist knowledge requires source grounding before it becomes canonical. Raw logs are not verified knowledge. | Source-grounding engine is complete |
| **Budget Leak Finder Skill** | Requires privacy spec, manual-paste-only handling rules, redaction strategy. Sensitive financial data handling not designed. | Approved privacy spec with explicit user opt-in for manual-paste-only analysis |
| **QLoRA / Fine-Tuning** | Training infrastructure is not set up. Model personalization through embeddings is sufficient for B launch. | Post-launch, when fine-tuning shows clear advantage over embedding-based personalization |
| **Kelly Bodywork Update** | Domain-specific content update. Requires specialist KB infrastructure. | Post-launch, when specialist KB system supports content updates |

For full parking documentation including problem statements, proposed shapes, risks, acceptance sketches, and forbidden-during-unrelated-work rules, see `docs/PARKED_FEATURES.md`.

---

## 12. Open Questions

These items are NOT decided. They don't block the launch plan from proceeding, but they need answers before their respective sub-projects begin. Each question includes the decision authority (who decides), the deadline (when it must be decided by), and the tradeoff (what's at stake).

### Flask vs FastAPI Migration Timing

**Status:** Deferred to post-launch.  
**Decision authority:** Claude Sonnet (CTO), with Jacob approval on timeline impact only.  
**Deadline:** After B launch, before Phase C+ architecture planning.  
**Tradeoff:** Migrating to FastAPI adds async support, automatic OpenAPI docs, and improved performance — but it touches every route in the application. If done during B launch, it blocks all sub-project work for 1–2 weeks while routes are rewritten. If done post-launch, it's a clean refactor with the launch as a stable baseline. The safe choice is post-launch. The aggressive choice (migrate during B launch) only makes sense if there's a specific FastAPI feature that a sub-project genuinely cannot ship without — which, as of this writing, there isn't.  
**Why it's deferred:** The current Flask stack is stable and understood. The launch is ambitious enough without a framework migration. FastAPI evaluation is noted so the team doesn't accidentally make Flask-specific architectural commitments that would make migration harder later.

### Memory Unification Strategy

**Status:** Strategy needed from Layer 0; full implementation post-launch.  
**Decision authority:** Claude Sonnet (CTO), informed by storage routing failures observed during Layer 1 work.  
**Deadline:** End of Layer 0 (week 2), so that sub-projects follow the same strategy.  
**Tradeoff:** Single-store consolidation simplifies routing, reduces bug surface, and makes queries faster (one query, not fallback chains). But it risks losing the specialized strengths of each store — LightRAG's graph-based retrieval, ChromaDB's dense vector search, JournalDB's chronological structure. Multiple stores with strict routing preserves those strengths but requires the StorageRouter to be robust. The safe choice for B launch is multi-store-with-enforcement (keep what exists, make it correct). The aggressive choice (consolidate into one store) is more elegant but introduces migration risk right before launch.  
**Working hypothesis:** Keep multiple stores for B launch. Enforce routing through a single `StorageRouter`. Post-launch, evaluate consolidation based on real usage data about which stores actually provide unique value vs which are redundant.  
**Decision needed by:** End of week 2 (before Sub-Projects 1 and 2 commit to storage patterns).

### MCP Agent Bundle — Pull Into Onboarding or Build Fresh?

**Status:** Deferred. Decision needed in week 1 of Layer 1.  
**Decision authority:** Claude Sonnet (CTO), after auditing the existing dirty-tree code.  
**Deadline:** Day 3 of Sub-Project 1 execution (before the agent dispatch pipeline is built).  
**Tradeoff:** The KnowledgeGetter MCP server in the dirty tree contains search, scrape, and indexing functionality that overlaps with the Onboarding Pipeline's research/dispatch needs. Adopting it could save 2–3 days of build time. But the code is incomplete, untested, and references optional dependencies that may not exist. Adopting it risks pulling in bugs that take longer to fix than building from scratch would take. Building fresh is cleaner but loses any real value in the existing work.  
**Decision depends on:** A 2-hour audit by Sonnet of the MCP agent bundle files. If the core search/scrape logic is sound and the dependencies are manageable, adopt with cleanup. If the code is fundamentally broken or the dependency chain is tangled, build fresh.  
**Decision needed by:** Sub-Project 1 execution (week 1–2 of Layer 1).

### Fast Dev Gate Design

**Status:** Needed for parallel agent velocity.  
**Decision authority:** Claude Sonnet (CTO).  
**Deadline:** End of week 1 (before parallel builders start committing frequently).  
**Tradeoff:** The full test suite takes ~47 seconds. Parallel builders committing multiple times per sub-project would spend significant time waiting. A fast gate (< 10 seconds) with a subset of tests solves this — but which subset? Route smoke tests (check 200 responses) are fast but shallow. Storage routing tests are critical but slower. Component render tests are fast but frontend-only. The gate composition determines what regressions it catches vs what slips through to the full suite.  
**Recommendation:** Fast gate = route smoke tests + storage routing enforcement tests + component render tests. This catches catastrophic breakage (routes return 500, storage writes to wrong backend, components don't render) in under 10 seconds. The full suite catches everything else before merge.  
**Decision needed by:** Sub-Project 4 (Test Coverage), or earlier if parallel agents are gated by commit speed.

### Skills Clean Install

**Status:** Pre-launch housekeeping.  
**Decision authority:** Claude Sonnet (CTO). Can be delegated to a builder agent with a specific scope.  
**Deadline:** Before Sub-Project 6 (Launch Operations), since the README will reference available skills.  
**Tradeoff:** The skills directory and Agent Skills block have grown organically. Some skills may be unused, some descriptions may not trigger correctly, and the set in `AGENTS.md` may not match what's in `.claude/skills/`. This is low-risk hygiene — it won't break the launch if skipped, but it adds friction to agent coordination if left messy. A 1-hour clean-pass with a focused builder agent resolves it.  
**Actions:** Remove unused skills. Verify each skill description triggers on the right inputs. Ensure `AGENTS.md` skills section matches `.claude/skills/` directory. Run the `audit` skill to confirm no broken imports.  
**Decision needed by:** Before launch (Sub-Project 6).

---

## 13. Validation Gates

### Per Sub-Project Gate

After each Layer 1 sub-project completes, before the next one begins (or before parallel work on that subsystem resumes):

1. **Full test suite:** `venv/bin/python -m pytest tests/ -q --tb=short` — must show the same or higher pass count as baseline (399 at launch plan writing). Any new failures must be from that sub-project's intentionally added tests (not regressions in unrelated areas). If a test in the journal system breaks because of a change to the command engine, that's a lane-violation bug — fix it before proceeding.
2. **Route smoke test:** `scripts/quick-smoke.sh` — all primary routes return HTTP 200. `/api/brief` returns a brief. `/api/command` with `/stuck` returns unblocking suggestions. `/api/chat` responds. If any route fails, the sub-project introduced a regression.
3. **Jacob demo:** Jacob sees the feature working end-to-end. He evaluates the experience, not the implementation. The demo is the real gate. A sub-project can pass all technical checks and still fail the demo if it doesn't feel like Kitty. When a demo fails, the feedback is captured as concrete redirections (not vague "it doesn't feel right"), and the builder fixes the experience, not the underlying code logic.

### Layer 0 Validation Gate (End of Week 1–2)

Before Layer 1 sub-projects begin in parallel — this gate confirms the operating system works:

1. **Dorothy Kanban** shows a real task flowing through the pipeline: intake → spec → build → demo → ship. Each status transition is visible on the board. Jacob can look at it and know exactly where each sub-project stands.
2. **Dorothy Telegram delivers a real progress ping:** Jacob's phone buzzes with "Sub-Project 1: Onboarding Pipeline — domain-selection wizard built, ready for demo." Not a test message. Not a screenshot. A real notification from the actual pipeline.
3. **Checkpoint survival test:** The coordinator is mid-task on a builder assignment. The session ends (simulated by killing the process). A fresh session starts, reads the HANDOFF checkpoint, and resumes the task from where it left off. No work is lost. The builder picks up the same spec, in the same lane, with the same allowed files. The only difference is a new session ID in the handoff log.
4. **Memory routing enforcement:** A test verifies that attempts to write journal entries to LightRAG (wrong store) are caught and blocked at the routing layer. A test verifies that KB content routed to JournalDB is similarly blocked. This isn't a unit test of the routing logic — it's a system test that the enforcement mechanism actually prevents the #1 source of data-loss bugs.

### Pre-Launch Validation Gate (End of Sub-Project 6)

The single gate that determines whether launch happens:

> A real technical friend (not Jacob, not an AI agent, not someone who's seen the codebase before) can:
> 1. Clone the repo on their own Mac
> 2. Run `./kitty setup` — the wizard completes without errors, without them needing to google anything, without them messaging Jacob
> 3. Complete the onboarding wizard — pick 3 domains, wait for agent research to finish, have no confusion about what's happening or why
> 4. Have a real conversation with Kitty about their chosen domains — Kitty references specific facts the agents discovered, not generic statements that could apply to anyone
> 5. Do all of this in under 30 minutes from first clone to first real conversation
> 6. Never once ask Jacob for help

This is not a benchmark. It's a real person doing it. If they can't, launch is not ready. The specific failure points become the priority fixes. The test is repeated with a second friend after those fixes. When two friends in a row succeed independently, launch is ready.

### Continuous Enforcement

Beyond the milestone gates, these run continuously:

| Check | When | What |
|-------|------|------|
| Pre-commit hook | Every `git commit` | Full test suite (399+ tests, ~47s). Blocks commit on failure |
| Fast dev gate | Every WIP checkpoint commit | Critical route + component tests (< 10s). For parallel agent velocity |
| Storage routing test | Every commit that touches `src/services/` or storage files | Verifies KB → LightRAG, journal → JournalDB, MCP entities → server-memory |

### Test Suite Baseline

| Metric | Current (2026-05-01) | Target (Launch) |
|--------|---------------------|-----------------|
| Total tests | 399 | ≥ 500 |
| Route coverage | ~28% | ≥ 80% |
| Frontend component tests | 0 | ≥ 10 core components |
| Integration tests | 0 | ≥ 3 end-to-end flows |
| Test suite runtime (full) | ~47s | ~47s |
| Test suite runtime (fast gate) | N/A | < 10s |
| Storage routing enforcement | Manual (CLAUDE.md rules) | Automated (test-enforced) |

---

## Appendix A: Source Documents

This design doc synthesizes decisions from:

- `CLAUDE.md` — project rules, storage routing, model routing, gotchas
- `docs/DECISIONS.md` — durable project decisions (D-0001 through D-0014)
- `docs/PARKED_FEATURES.md` — full parking lot with revival triggers
- `docs/OPEN_LOOPS.md` — active open loops (Unified Command System, architecture trio, kitty-system split)
- `docs/plans/gemini-architecture-priorities-2026-04-30.md` — three architecture tracks (tag: `GEMINI-ARCH-PRIORITIES`)
- `docs/plans/2026-04-30-unified-tool-runtime.md` — Tool Runtime track plan
- `docs/audits/operational-plan-20260430.md` — Phase A–D milestone history
- `docs/HANDOFF.md` — current operational handoff
- `docs/CAPABILITY_INVENTORY.md` — current advertised surface
- `.claude/HANDOFF-2026-05-01-launch-plan-design.md` — the handoff that produced this doc
- `.claude/HANDOFF-2026-05-01-implementation.md` — prior batch (workflow conventions, hooks, scripts, process skills)
- `/Users/jacobbrizinski/.codex/memories/memory_summary.md` — cross-agent user preferences (harvested into CLAUDE.md)

---

## Appendix B: Glossary

| Term | Meaning |
|------|---------|
| **Layer 0** | The operating system for building Kitty — agent team, PM layer, coordination, memory routing |
| **Layer 1** | The product users interact with — onboarding, memory, commands, UX, launch ops |
| **Approach B** | Vision First — onboarding and memory before architecture cleanup |
| **B Launch** | Friends-and-technical-peers launch — local installs on Apple Silicon Macs |
| **Phase C+** | Future App Store launch with Jacob managing hosted backend |
| **Dorothy** | MCP-based project management layer (Kanban board + Telegram notifications) |
| **Crush** | Non-interactive agent runner for batch builder tasks |
| **Aider** | AI pair-programming tool for interactive edit-verify loops |
| **Fast dev gate** | Subset of critical tests running in < 10 seconds for WIP commits |
| **Storage routing** | Rules governing which data goes to which store (KB → LightRAG, journal → JournalDB, MCP entities → server-memory) |
| **Mission** | "So that no one becomes themselves alone" — the founding purpose, verbatim |
