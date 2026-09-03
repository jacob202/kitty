# kitty vision gap analysis: 2026-07-24

> **position in the kit**: the strategy document — what kitty should be vs what it is. feeds into `kittybuilder-redesign.md` (autonomous execution plan) and `image-studio-character-system.md` (creative capabilities plan). takes ground truth from `architecture-honesty.md` (what actually exists) and external validation from `repo-landscape.md` (what others built that we haven't).

comparison of docs/north_star.md product vision against actual implementation. includes a strengths section (what's salvageable) to balance the gap analysis — v1 had no strengths and read as uniformly negative.

---

## strengths — what exists and works

these are the foundations the gaps will be built on.

### memory and context — deeper than documented
- **9-store memory graph** (`memory_graph.py`): concurrent fetch across memory (mem0), knowledge (chromadb), journal (sqlite), traces (log files), todos (sqlite), inbox (jsonl), signals (signal store), facts (temporal kg), and optional mempalace. privacy gate filters sensitive items. token-aware budgeting caps context at ~1200 tokens.
- **memory policy** (`memory_policy.py`): 7-class classification with keyword heuristics. pinned/working/preference/creative/sensitive/archived/blocked. sensitive content rewriting turns psych language into support preferences.
- **temporal knowledge graph** (`memory_weave.py`): facts with confidence decay (halves in 30 days), source provenance tracking, conflict detection, correction with deprecation chains.
- **consolidation pipeline** (`memory_consolidation.py`): nightly dream — cluster traces by domain, llm summarize, store as memory facts. session-end consolidation captures immediate takeaways.
- **context assembler** (`context_assembler.py`): single deep entry point. assembles memory + skills + journal + enrichments + domain routing into one system prompt. partial-result contract — individual source failures produce warnings, never crash.

### agent infrastructure — real, not yet wired
- **5 agent presets** (`agent_runner.py`): explorer, planner, coder, reviewer, researcher. each with system prompt, max iterations, temperature. 6-phase reasoning loop (observe→orient→decide→act→verify→learn). runs as background async tasks with persistence.
- **skill registry** (`skill_registry.py`): yaml frontmatter skill discovery from `.agents/skills/`. `USE WHEN / NOT FOR` trigger phrase matching. markdown-based, editable by humans. secure zip bundle import with binary payload rejection.
- **mcp tool bridge** (`mcp_tool_bridge.py`): json-rpc 2.0 tool invocation against mcp servers. tool schema generation for llm consumption.

### execution — seed planted, needs watering
- **mature builder queue** (`builder_queue.py`): 6-state sqlite state machine with repair loop. well-designed queue infrastructure.
- **worktree-based sandbox** (`builder_runner.py`): although pre-alpha, the worktree isolation pattern is correct and ready for expansion.

### reliability — solid
- **llm client** (`llm_client.py`): table-driven provider dispatch, d10 privacy boundary, rate limiting, retry logic. accurately documented.
- **auth** (`auth.py`): bearer token middleware. functional and tested.

---

## north star principles versus reality

### principle: "life-first — kitty adapts to your life, not the other way around"

**ideal**: the companion learns from your schedule, habits, priorities, and context. it proactively offers help based on what you're doing, not just what you ask.

**current reality**:
- no schedule awareness. no calendar integration (despite `routes/calendar.py` existing — may be a stub or incomplete).
- no habit learning. no pattern recognition for recurring activities.
- no proactive suggestions. kitty responds to questions and commands but does not initiate.
- no context awareness beyond assembled memory. no integration with filesystem activity, browser activity, or application state.
- chat is the only interaction mode. no proactive notifications, no scheduled check-ins, no ambient awareness.
- **what does exist**: the consolidation pipeline (`memory_consolidation.py` nightly_dream) is a first step — it clusters activity traces and summarizes them. this is the seed of awareness, just not yet wired to proactive behavior. the signal_store.py + inbox system captures external events but doesn't trigger companion action.

**gap severity**: critical. the core value proposition (life-adaptive companion) is mostly unimplemented. the infrastructure exists (signal store, consolidation, scheduled tasks) but is not connected.

### principle: "single next move — know exactly what to do next"

**ideal**: at any point, kitty has a clear next action that moves toward the user's goals. the system is never idle in a way that wastes time or attention.

**current reality**:
- builder queue handles autonomous execution tasks but is disconnected from the companion chat loop. the companion doesn't know what the builder is doing and vice versa.
- no goal tracking. no mechanism to capture, decompose, or prioritize user goals.
- no next-action inference. the system does not compute "what should happen now."
- the frontend shows a static dashboard. 9 of 16 view slots are PlaceholderView — including work, builder, projects, tasks, and tools.
- **what does exist**: the builder queue IS the task execution infrastructure. agent_runner.py presets (especially planner) CAN break down goals into steps. the missing piece is the orchestration layer that connects goal → plan → queue → execution → notification.

**gap severity**: critical. the entire decision-making and orchestration layer is absent. the pieces exist (queue, agents, presets) but no one has wired them together.

### principle: "companion — kitty is a person, not a tool"

**ideal**: kitty has personality, memory, preferences, and consistent behavior. interactions feel like talking to someone who knows you.

**current reality**:
- **memory exists** — the 9-store graph, policy classification, and consolidation pipeline give kitty durable awareness of past interactions. this is real and working.
- **personality is primitive** — a single system prompt. no modular identity (contrast clawdbot's soul.md / agents.md / identity.md pattern from `repo-landscape.md`). no character evolution over time.
- **no user model** — preferences are detected by keyword heuristics in memory_policy.py but not stored as a structured user profile. no learned behavior adaptation.
- **builder and companion are separate identities** — this is architecturally correct (separation of concerns) but they don't coordinate. the companion should be aware of builder activity and vice versa.
- **no conversation history browsing** — sessions may be stored (migration `022_chat_message_memory.sql` exists) but there's no ui to browse, search, or resume past conversations.
- **what does exist**: skill_registry.py provides a mechanism for injecting behavior instructions based on context. memory_policy.py handles sensitive content appropriately. the infrastructure for a companion identity exists in pieces.

**gap severity**: moderate. memory is real and deep — the companion can remember. the gap is in personality expression (modular identity, voice consistency) and conversation history browsing. existing components solve ~60% of this.

### principle: "autonomous — kitty can execute tasks without hand-holding"

**ideal**: user sets high-level goals, kitty figures out steps, executes, reports results.

**current reality**:
- **builder exists** — state machine, queue, repair loop, worktree sandbox. queue is mature, runner is pre-alpha.
- **agent presets exist** — planner can decompose goals, explorer can research, coder can analyze code. these are api-only — not usable from chat conversations.
- **no chat-time execution** — the companion cannot dispatch builder tasks during conversation. user says "research topic x" and kitty can only reply with text, not spawn an explorer agent.
- **no goal decomposition ui** — no way to see a plan break down, approve steps, and track execution progress.
- **what does exist**: `builder_initiative.py` parses structured task documents. `agent_runner.py` has a planning preset. the pieces for goal → plan → execute exist but are not connected.

**gap severity**: p1 (elevated from p2 in v1 draft — the existing infrastructure is more complete than initially assessed). wiring the pieces is weeks, not months.

### principle: "cheap models — kitty should be affordable to run"

**ideal**: small models by default, large models for complex tasks. cost visible and manageable.

**current reality**:
- `llm_client.py` supports multiple providers and has `route_model()` for context-dependent selection. infrastructure exists.
- no default model tiering (small model for simple queries, large model for complex tasks).
- no cost tracking. no token usage visibility. no budgets or spending limits.
- builder and agent runner use default model with no awareness of task cost.
- **what does exist**: the provider dispatch table in llm_client.py supports model routing. it just needs tier definitions and cost tracking.

**gap severity**: moderate. infrastructure exists, intelligence and tracking don't. low effort to add.

### principle: "local-first — everything runs on your machine"

**ideal**: fully offline operation. cloud dependencies are optional enhancements.

**current reality**:
- llm calls go to remote providers (openai, anthropic, etc.). no ollama or llama.cpp support in llm_client.py.
- image generation requires comfyui (local, good).
- all infrastructure is local (gateway, sqlite, chromadb, files).
- memory embeddings use ollama (nomic-embed-text) in mem0 config — but the config is hardcoded, not user-configurable.
- **what does exist**: the infrastructure pattern is local-first. everything except the llm inference is local. adding ollama as an llm provider in the dispatch table is low-effort.

**gap severity**: moderate. local-first is true for infrastructure, false for core ai. adding local model support is a config change, not an architecture change.

### principle: "creative — kitty can write, draw, and design"

**ideal**: cohesive text and visual generation with character consistency.

**current reality**:
- text generation works (primary mode). quality depends on llm provider.
- image generation works via comfyui (basic text2img). no img2img for consistency, no inpainting, single backend.
- character consistency is prompt-only. v1 character store exists (honestly named) but lacks reference images and face embeddings.
- no cross-modal consistency — the companion personality and generated image characters are unrelated.
- **what does exist**: basic image generation works. v1 character store has the right schema (prompt + lora + negative_prompt) — just needs image references.

**gap severity**: moderate. basic text+image works. character consistency and cross-modal integration are gaps. the v1 store schema is a good foundation.

---

## gap prioritization — corrected with existing infrastructure factored in

| gap | severity | effort | priority | depends on |
|-----|----------|--------|----------|------------|
| no life awareness / proactive behavior | critical | high | p0 | signal store, consolidation pipeline (exists) |
| no next-action orchestration | critical | high | p0 | builder queue (exists), agent presets (exist), planner agent (exists) |
| companion personality is primitive | moderate | medium | p0 | skill registry (exists), memory policy (exists), clawdbot pattern (from landscape) |
| no conversation history browsing ui | moderate | medium | p1 | chat message memory migration (exists) |
| builder → companion wiring | moderate | medium | p1 | builder queue (exists), agent presets (exist) |
| no local llm support | moderate | low | p1 | llm_client.py provider table (exists) |
| no cost tracking | low | low | p1 | llm_client.py (exists) |
| builder runner pre-alpha | moderate | high | p2 | builder queue (exists) |
| character consistency for images | moderate | medium | p2 | v1 character store (exists) |
| frontend is a monolith | moderate | high | **p0** | — |
| no cross-modal integration | low | high | p3 | — |
| no other creative modalities | low | high | p3 | — |

**frontend is elevated to p0** (was unlisted in v1). the 1060-line page.tsx monolith with 9 empty views is the blocker for every user-facing feature. you can't show proactive behavior, next actions, conversation history, or builder progress without ui surface. frontend restructuring must happen before or alongside p0 feature work.

---

## frontend restructuring — critical prerequisite

the current page.tsx monolith blocks all p0-p2 user-facing work. before implementing memory browsing, next-action display, builder progress, or conversation history, the frontend needs:

1. **independent routes** — `/chat`, `/builder`, `/images`, `/memory`, `/goals` each as standalone pages with their own layout and state. next.js app router supports this natively.

2. **lazy view loading** — the VIEWS registry exists in views.tsx. make it dynamic imports so unused views don't load at all.

3. **fill placeholder views** — 9 of 16 views are PlaceholderView. at minimum: builder view (shows queue status, approval prompts), images view (gallery + generation), and memory view (browse/search past conversations).

4. **extract shared state** — websocket, image jobs, session state should live in a shared context provider, not page.tsx. each route accesses what it needs.

this is ~3-4 weeks of work and should be the first thing any implementing agent does. it is more important than any single feature.

---

## p0 action items

1. **restructure frontend** (3-4 weeks) — independent routes, lazy loading, fill builder/images/memory views. this unblocks all other p0 items.

2. **implement modular companion personality** (1-2 weeks) — adopt clawdbot's soul.md / agents.md / identity.md pattern from `repo-landscape.md`. three files in `.agents/companion/` that the context assembler reads. personality becomes editable, version-controlled, and composable without editing the system prompt.

3. **implement next-action orchestration** (2-3 weeks) — wire builder queue + agent presets + companion chat loop:
   - after each conversation turn, run a lightweight llm call: "given the conversation, what's the single most useful next action?"
   - if the action is executable (research, implement, check), spawn a builder initiative
   - companion reports builder activity in chat: "i'm looking into that — i'll let you know what i find"
   - builder_status.py feeds progress into the chat view

4. **implement life awareness** (3-4 weeks) — use the existing signal_store.py + consolidation pipeline:
   - calendar integration via ical/caldav (routes/calendar.py may need work)
   - morning brief: consolidate yesterday's traces, surface today's calendar, suggest one proactive action
   - evening reflection: summarize the day's activity, capture durable learnings
   - "don't interrupt" awareness: if user is in a meeting (calendar), defer proactive messages

## p1-p2 sequence

5. **conversation history browsing** — migration 022 exists. build ui at `/memory` to search, filter, and resume past conversations.
6. **local llm support** — add ollama provider to llm_client.py dispatch table. one config change.
7. **cost tracking** — token counting per request, per-session cost projection, budget alert.
8. **builder runner upgrade** — see `kittybuilder-redesign.md` for full plan.
9. **image character consistency** — see `image-studio-character-system.md` for full plan.

---

## cross-references to other audit documents

- `architecture-honesty.md`: the three "absent" claims from v1 (memory, agent runner, skill registry) were false. they all exist. the corrected audit identifies the actual infrastructure available for each gap.
- `repo-landscape.md`: clawdbot's modular prompt architecture (soul.md/agents.md/identity.md) is the pattern for companion personality. skillopt's rollout→validate→edit loop is the pattern for self-evolving skills. companion-emergence's persistent supervisor is the pattern for always-on awareness.
- `kittybuilder-redesign.md`: addresses the builder runner gap (p2) and autonomous execution wiring.
- `image-studio-character-system.md`: addresses the character consistency gap (p2) and frontend decoupling.