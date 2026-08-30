# agent prompts — 5 tasks for the next agent

these prompts are for the agent that will implement the work described in the five audit documents. each prompt is a standalone brief. the agent should read the referenced document, critically review it, form its own plan, and ask for clarification before starting.

---

## task 1: frontend restructuring (p0 — do first)

### context — what happened before you

i commissioned a research-and-architecture audit of the kitty codebase. five documents were produced: `docs/recon/repo-landscape-2026-07-24.md`, `docs/audit/architecture-honesty-2026-07-24.md`, `docs/planning/kittybuilder-redesign-2026-07-24.md`, `docs/planning/image-studio-character-system-2026-07-24.md`, `docs/planning/kitty-vision-gap-analysis-2026-07-24.md`.

the audit found: the frontend is a 1060-line monolith (`gateway/kitty-chat/src/app/page.tsx`). 9 out of 16 view slots in the VIEWS registry are `PlaceholderView` components. there is no lazy loading, no independent routing, no view isolation. the page component directly imports the image api client, websocket hooks, and every view component — no presentation layer distinct from application logic.

the vision gap analysis elevated frontend restructuring to **p0** because every user-facing feature (memory browsing, next-action display, builder progress, conversation history) needs ui surface that doesn't exist yet. building features into the monolith guarantees a larger refactor later.

### what you need to read first

1. `docs/planning/kitty-vision-gap-analysis-2026-07-24.md` — the "frontend restructuring — critical prerequisite" section
2. `docs/audit/architecture-honesty-2026-07-24.md` — the frontend subsystem section
3. `gateway/kitty-chat/src/app/page.tsx` — the monolith itself (1060 lines)
4. `gateway/kitty-chat/src/lib/views.tsx` — the VIEWS registry (16 entries, 9 placeholders)
5. `gateway/kitty-chat/src/components/` — the 49-component directory tree
6. the next.js app router structure — understand how routing works in this project
7. the image components (ImageStudio, ImageGenPanel) — understand what needs extracting

### what you need to critically review in the plan

the vision gap document says: independent routes for `/chat`, `/builder`, `/images`, `/memory`, `/goals`, lazy view loading, fill placeholder views, extract shared state to context provider. estimated 3-4 weeks.

**critically review**: is next.js app router the right choice or should we use pages router or a different approach? does the project already have an app router set up? are the 9 placeholder views all needed or should some be removed? is extracting to context providers the right state management choice for next.js server components? does the websocket connection model work with independent routes or does each route navigation tear down and reconnect?

### what you need to form your own plan for

1. the specific route structure (which paths, which components)
2. the state management architecture (context providers, websocket singleton, image job subscription)
3. the order of extraction (which view to extract first to prove the pattern)
4. which placeholder views to delete vs fill vs keep as placeholders
5. how to handle the websocket lifecycle across route navigation
6. how session state (active conversation, user context) moves between routes
7. the testing strategy — how to verify the monolith was correctly decomposed

### what you need to ask me before starting

- does the project currently use next.js app router or pages router? show me the directory structure under `gateway/kitty-chat/src/app/`.
- are there any server-side rendering or static generation requirements i should know about?
- should i preserve the current visual design exactly or can i make layout improvements during restructuring?
- are the 9 placeholder views (link, work, studio, builder, library, tasks, tools, terminal, projects, docs, providers, agents, images, tutor) all intended features or are some abandoned ideas? which should i keep?
- what's the auth model — does each route need auth or is the gateway handling it?
- should i set up storybook or component tests during restructuring or focus on routing/state only?
- do you want me to deploy and test after restructuring, or just verify the build passes?

### deliverables at completion

- independent routes for `/chat`, `/builder`, `/images`, `/memory` at minimum
- lazy-loaded view components
- shared state extracted from page.tsx into context providers
- page.tsx <200 lines (routing only)
- `npm run build` passes
- component tree is navigable and each route renders independently

---

## task 2: builder system upgrade (p2 infrastructure, p1 orchestration wiring)

### context — what happened before you

the audit found the builder system is split: a mature sqlite state machine (builder_queue.py, kb-s1 with 6 states and repair loop) and a pre-alpha runner (builder_runner.py, phase 1c-alpha, single-shot worktree execution with no validation, no retry, no context). additionally, agent_runner.py has 5 presets (explorer, planner, coder, reviewer, researcher) with a 6-phase reasoning loop that are not connected to builder. the vision gap analysis identified "next-action orchestration" as a p0 item that needs builder + agent presets wired to the companion chat loop.

the full redesign is in `docs/planning/kittybuilder-redesign-2026-07-24.md` — 5 phases over 16 weeks. but the document may be too detailed or too abstract.

### what you need to read first

1. `docs/planning/kittybuilder-redesign-2026-07-24.md` — the full redesign
2. `docs/audit/architecture-honesty-2026-07-24.md` — builder, agent runner, and context assembler sections
3. `docs/planning/kitty-vision-gap-analysis-2026-07-24.md` — p0 and p1 items
4. `docs/adr/0017-kitty-mission-builder-control-plane.md` — the builder control plane architecture decision
5. `docs/KITTYBUILDER_QUICKSTART.md` — current builder operations
6. `gateway/builder_queue.py` — the state machine
7. `gateway/builder_runner.py` — the pre-alpha runner
8. `gateway/builder_loop.py` — the repair loop
9. `gateway/builder_initiative.py` — the initiative parser
10. `gateway/builder_status.py` — the status projection
11. `gateway/builderpy.py` — the facade (candidate for deletion)
12. `gateway/agent_runner.py` — the 5 presets with 6-phase reasoning
13. `gateway/context_assembler.py` — the partial-result contract pattern
14. read `./kitty builder --help` and `./kitty builder initiative doctor --json` to understand the cli interface

### what you need to critically review in the plan

**the kb-s2 plan** proposes: pydantic models, state machine tests, context injection, validation step with llm reviewer, iterative refinement with retry, sub-task spawning with parent_id dag, approval gates, initiative validation/templates/scheduling, wiring agent_runner presets to builder. timeline: 16 weeks.

**critically review**:
- is 16 weeks realistic? which phases could be collapsed or reordered?
- the sub-task dag uses `parent_id` in the same `builder_queue` table — is this correct or should there be a separate `subtask` table?
- the validation step uses the agent_runner reviewer preset — but that preset has no tool execution. can it actually validate code output without running tests?
- does the pydantic initiative model capture all fields in the current initiative markdown format or will it lose data?
- the approval gate flow (pause → user approves → continue) assumes the user is watching the builder ui. what happens if the user is offline when an approval gate is hit?
- builderpy.py deletion: verify that no route handler or cli command imports it before deleting.
- the connection between builder and agent_runner presets: are the presets currently usable or do they need upgrading first?

### what you need to form your own plan for

1. the exact schema changes to `builder_queue` table for kb-s2
2. the pydantic model hierarchy (Initiative, Criteria, ApprovalGate, RunnerContext, RunnerResult, ValidationResult)
3. the test suite structure — which transition edges, which repair scenarios, which validation scenarios
4. the order of phases — should pydantic models come before tests? should wiring agent presets come before sub-task spawning?
5. the error model — what errors are transient vs permanent, what gets logged vs surfaced to user
6. how builder status projection feeds into the companion chat loop (for p0 next-action orchestration)
7. whether to keep or delete builderpy.py — and how to verify no callers exist

### what you need to ask me before starting

- the pydantic initiative model in the plan is a sketch. should it match the existing initiative markdown format exactly or can i redesign the initiative format?
- should sub-tasks be a separate sqlite table or stored as rows in the same `builder_queue` table with `parent_id`?
- the plan proposes llm-driven validation using the reviewer agent preset. is that acceptable or should validation be deterministic (script exit code, test pass/fail) first with llm as fallback?
- should i implement phases 1-2 (pydantic + tests + runner upgrade) first and defer phases 3-5 (human-in-the-loop, templates, scheduling) or should i implement the full kb-s2 in one pass?
- what's the priority: builder runner quality (validation, retry, context injection) or builder → companion wiring (making the companion dispatch builder tasks during chat)?
- the plan says 16 weeks. do you want me to scope a faster MVP (say 4-6 weeks) that delivers the highest-leverage changes first?
- should builderpy.py be deleted? if so, should i delete it in this task or should the frontend restructuring agent handle it?

### deliverables at completion

- pydantic models for all builder entities (`gateway/models/builder.py`)
- state machine test suite (20+ tests covering transitions, repair, edge cases)
- upgraded builder_runner with context injection and validation (at minimum)
- builder → companion wiring (companion can dispatch builder initiatives during chat) if p0 orchestration is prioritized
- builderpy.py deleted (if confirmed)
- all existing builder routes and cli commands still work
- `python3.12 -m pytest tests/ -q --tb=short` passes

---

## task 3: image system upgrade (p2 character consistency + frontend decoupling)

### context — what happened before you

the audit found the image system is functional for basic text2img via comfyui but oversold on advanced features. the character store is v1 and honestly named (no reference images, no face embeddings, no versioning). the frontend image components (ImageStudio, ImageGenPanel) are tightly coupled to the 1060-line page.tsx monolith. the full redesign is in `docs/planning/image-studio-character-system-2026-07-24.md` — 6 phases over 10 weeks, with phase 0 (frontend decoupling) ordered first.

**critical dependency**: this task depends on the frontend restructuring agent completing task 1 first. if the monolith isn't decomposed, image components will be built into it and need another refactor later. confirm with me whether task 1 is done before starting implementation. you can do design and planning without task 1, but not code changes to the image components.

### what you need to read first

1. `docs/planning/image-studio-character-system-2026-07-24.md` — the full redesign
2. `docs/audit/architecture-honesty-2026-07-24.md` — image system section
3. `docs/planning/kitty-vision-gap-analysis-2026-07-24.md` — creative capabilities gap
4. `gateway/image_gen.py` — comfyui wrapper
5. `gateway/image_runner.py` — background poller
6. `gateway/image_characters.py` — v1 character store
7. `gateway/image_jobs.py` — job queue
8. `gateway/kitty-chat/src/components/ImageStudio.tsx` — find and read
9. `gateway/kitty-chat/src/components/ImageGenPanel.tsx` — find and read
10. `gateway/kitty-chat/src/lib/gateway.ts` — frontend api client (McpTool and image-related calls)
11. check `gateway/memory_policy.py` — privacy gate pattern to apply to image privacy

### what you need to critically review in the plan

**the v2 plan** proposes: frontend decoupling first (phase 0), then character store v2 (reference images, arcface embeddings, versioning, gallery, tags), multi-backend support (abstract interface, comfyui port to async, stability ai fallback), workflow template validation (pydantic schemas), job queue (priority, retry, scheduling), and cross-system integration (builder, companion consistency, privacy).

**critically review**:
- **arcface vs insightface**: the plan recommends arcface via onnx for simplicity. have you actually tested this on macOS arm64 with python 3.12? insightface has broader community support despite the heavier dependency. which is the right call?
- **async port of comfyui backend**: the current image_runner uses threading. porting to async means rewriting the runner. is this worth it for v2 or should we defer?
- **stability ai backend**: does it support lora? does it support reference images for character consistency? if not, it's a downgrade from comfyui — making the fallback chain less useful than claimed.
- **frontend decoupling as phase 0**: the image plan says "do frontend first" but the frontend restructuring agent (task 1) is doing that. should image components wait for task 1 to complete and then enhance the new `/images` routes? or should the image agent own the `/images` routes from scratch?
- **the plan has no concrete storage design for reference images and embeddings**: should reference images be stored as files on disk with sqlite paths? blob in sqlite? separate object store? what about face embeddings — pickle? numpy npy? sqlite blob?
- **job queue vs builder queue**: the image job queue and builder queue are separate sqlite tables. the plan mentions unification as future work. is that actually desirable given they have different semantics (images: fire-and-forget, builder: stateful with approval)?

### what you need to form your own plan for

1. the exact schema changes for character store v2 (reference_images column type, face_embedding storage format, version table, gallery table, tags column)
2. the backend interface design — is the `ImageBackend` abc correct? what methods are actually needed?
3. the async port strategy — rewrite runner vs wrap threaded runner in asyncio
4. the dependency tree — what new python packages are needed, what node packages
5. the migration path for existing character data — how to preserve v1 characters when upgrading schema
6. the coordination with task 1 (frontend restructuring) — who owns the `/images` routes
7. the coordination with task 2 (builder upgrade) — who owns the builder → image bridge

### what you need to ask me before starting

- **critical**: is task 1 (frontend restructuring) complete yet? if not, should i design and plan now and wait for task 1, or should i own the `/images` routes as part of this task?
- arcface vs insightface for face embeddings — which do you prefer? tradeoffs: arcface is lighter (single onnx file), insightface is more accurate but heavier (onnxruntime + model download).
- should i port image_runner to async now or wrap the existing threaded runner in asyncio?
- stability ai backend — should i use the official stability sdk or the openai-compatible endpoint?
- do you want me to reuse task 2's pydantic patterns (if they exist by then) or define image-specific models independently?
- what's the image storage strategy — files on disk with paths in sqlite, or blobs in sqlite? reference images are small but can accumulate.
- should the image system have its own privacy model or reuse memory_policy.py's privacy gate pattern?

### deliverables at completion

- character store v2 schema with reference images, face embeddings, versioning, gallery, tags
- character store v2 python module with crud operations
- abstract image backend interface with comfyui (ported or wrapped) and stability ai implementations
- workflow template validation with pydantic schemas
- job queue with priority and retry
- all existing image routes still work
- `python3.12 -m pytest tests/ -q --tb=short` passes (new tests for v2 image modules)

---

## task 4: companion personality system (p0 modular identity)

### context — what happened before you

the vision gap analysis found the companion personality is a single system prompt — no modular identity, no persistence, no evolution over time. the repo landscape found clawdbot's modular pattern (soul.md / agents.md / identity.md) and companion-emergence's emotional state model. the architecture honesty audit found the infrastructure is ready: skill_registry.py can load personality files, context_assembler.py can inject them into system prompts, memory_policy.py handles sensitive content classification.

**this is a p0 item** — without personality, kitty is a chat interface not a companion. it's also the lowest-effort p0 item (1-2 weeks estimate) because the infrastructure already exists.

### what you need to read first

1. `docs/planning/kitty-vision-gap-analysis-2026-07-24.md` — companion personality gap and p0 section
2. `docs/recon/repo-landscape-2026-07-24.md` — clawdbot modular pattern section
3. `docs/audit/architecture-honesty-2026-07-24.md` — skill registry and context assembler sections
4. `gateway/skill_registry.py` — how skills are loaded from disk
5. `gateway/context_assembler.py` — how context is assembled into system prompt
6. `gateway/memory_policy.py` — privacy classification and sensitive content handling
7. the current system prompt (find where it's defined — likely in `gateway/prompts.py` or a config file)
8. check `gateway/personality.py` and `gateway/routes/personality.py` — the routes directory has a personality route file
9. read the clawdbot pattern: `soul.md` (personality/voice), `agents.md` (operational rules), `identity.md` (privacy boundaries)

### what you need to critically review in the plan

the vision gap document says: adopt clawdbot's three-file pattern. three markdown files in `.agents/companion/` that the context assembler reads. personality becomes editable, version-controlled, composable.

**critically review**:
- is `soul.md` / `agents.md` / `identity.md` the right split? should there be a fourth file for emotional state or should that be in soul.md?
- should personality be a skill (loaded via skill_registry) or a separate loading path in context_assembler? the skill registry already does yaml frontmatter + markdown content loading — reusing it means personality files get USE WHEN / NOT FOR triggers. is that desirable for companion identity?
- the existing `routes/personality.py` file exists — does it already implement something? shouldn't override it blindly.
- companion-emergence has an emotional state model (16 registers) that changes during conversation. should kitty have a dynamic state vs static personality split?
- memory_policy.py already handles "how to talk about sensitive topics" — should the personality system override or extend the policy?

### what you need to form your own plan for

1. the exact file format for each personality component (yaml frontmatter + markdown body?)
2. where personality files live: `.agents/companion/` or `.agents/personality/` or somewhere else
3. how personality is loaded: on startup, on first message, or on context assembly (per-message)
4. how personality interacts with memory: should the companion's memory of past interactions influence personality expression?
5. how personality changes over time: immutable static files, mutable with version history, or learned from conversation
6. the relationship between companion personality and generated image characters — should they share identity?
7. how to test that personality is being injected correctly into system prompts

### what you need to ask me before starting

- what is the companion's personality? do you have a description or should i infer it from the existing system prompt? show me the current system prompt file.
- should i model kitty's personality after something specific (a known character, a writing style, a set of values)?
- clawdbot's three-tier approval (do without asking / get approval / never do) — should kitty have this? what operations fall in each tier?
- should personality be static (file-based, you edit it) or dynamic (kitty evolves it based on interactions)? both?
- does `routes/personality.py` already do anything i should know about?
- should the companion personality and the image character system share identity (e.g., a visual avatar that matches the personality)?

### deliverables at completion

- three personality files: `soul.md` (voice, tone, personality), `agents.md` (rules, approval tiers, constraints), `identity.md` (privacy boundaries, disclosure rules)
- integration with context_assembler.py — personality is injected into every system prompt
- personality is discoverable and editable (skill_registry pattern or separate path)
- the companion sounds like a person with consistent voice, not a chat interface
- existing behavior (responses, tool use, memory injection) is preserved — personality is additive

---

## task 5: life awareness and proactive behavior (p0 — hardest p0 item)

### context — what happened before you

the vision gap analysis identified "life-first — kitty adapts to your life" as a critical p0 gap with zero implementation. but the architecture audit found the infrastructure exists: signal_store.py captures external events, memory_consolidation.py does nightly consolidation of traces, routes/calendar.py has a calendar route file, the cron action system exists for scheduled tasks. the pieces for awareness exist — they're just not wired to proactive behavior.

this is the hardest p0 item (3-4 weeks) because it requires: calendar integration, activity assessment, proactive decision-making, and notification delivery.

### what you need to read first

1. `docs/planning/kitty-vision-gap-analysis-2026-07-24.md` — life awareness gap and p0 section
2. `docs/audit/architecture-honesty-2026-07-24.md` — memory and consolidation sections
3. `docs/recon/repo-landscape-2026-07-24.md` — companion-emergence section (persistent supervisor pattern), bolly section (heartbeat autonomy)
4. `gateway/signal_store.py` — signal capture (if exists)
5. `gateway/memory_consolidation.py` — nightly dream pipeline
6. `gateway/routes/calendar.py` — calendar route (may be stub)
7. `gateway/routes/cron.py` — cron action system
8. `gateway/routes/brief.py` — brief route (morning/evening briefs?)
9. `gateway/routes/insights.py` — insights route
10. `gateway/context_assembler.py` — how context is built (where awareness would be injected)
11. check for any notification delivery mechanism (desktop notifications, websocket push, email, etc.)

### what you need to critically review in the plan

the vision gap document says: calendar integration via ical/caldav, morning brief (consolidate yesterday + today's calendar + one proactive action), evening reflection (summarize day), "don't interrupt" awareness (meeting → defer messages). 3-4 weeks estimate.

**critically review**:
- **is 3-4 weeks realistic?** calendar integration alone can take 2 weeks if it needs ical parsing, caldav protocol, timezone handling, recurring event support. is this a full caldav client or a simpler ical .ics file reader?
- **companion-emergence uses a persistent supervisor** (launchd/systemd daemon that keeps the brain alive when app is closed). does kitty need this or does the gateway already run as a persistent server?
- **proactive notifications**: how does kitty notify? desktop notifications (electron/notification api)? websocket push to an open browser tab? email? slack? the plan assumes notification exists but doesn't specify the delivery mechanism.
- **"don't interrupt" awareness**: this requires knowing the user's current state (in meeting, focused, asleep). calendar is one signal. could also use: screen idle time, focus mode (macOS), time of day. how many signals are enough for v1?
- **morning brief vs continuous awareness**: the plan describes batch processing (morning brief, evening reflection). should kitty also have continuous awareness (detect events as they happen and react) or is batch sufficient for v1?

### what you need to form your own plan for

1. the calendar integration approach: ical file, caldav server, google calendar api, apple calendar via eventkit — which to support first?
2. the activity assessment model: what signals indicate "busy" vs "available" vs "asleep"?
3. the proactive action model: what actions can kitty take without being asked? morning briefs, deadline reminders, follow-up on unfinished tasks, surfacing relevant memories, suggesting next steps.
4. the notification delivery mechanism: how does kitty reach the user?
5. the scheduling model: cron-based (fixed times) or event-driven (triggered by signals)?
6. how awareness integrates with the companion chat loop: should the companion mention awareness findings during conversation or keep them separate?
7. the relationship between proactive behavior and builder: when kitty decides to take action, does it spawn a builder initiative?
8. the testing strategy — how do you test proactive behavior deterministically?

### what you need to ask me before starting

- **critical**: what calendar system do you use? apple calendar, google calendar, outlook, something else? this determines the integration approach.
- how should kitty notify you? desktop notifications, browser tab updates, email, slack, or a "check-in" model where you open kitty and see what's new?
- do you want kitty to be always-on (persistent supervisor like companion-emergence) or on-demand (you open it, it catches up)?
- what signals should determine "don't interrupt" — just calendar (meetings) or also time of day, screen activity, focus mode?
- should kitty be proactive ("hey, you have a meeting in 10 minutes") or passive-aggregator (you open kitty and see today's brief)?
- what's the scope of "life awareness" for v1 — just calendar + daily briefs, or do you want email triage, task tracking, habit monitoring too?
- do you use a task manager (todoist, things, apple reminders) that kitty should read from?

### deliverables at completion

- calendar integration reading your primary calendar (ical, caldav, or google calendar api)
- morning brief: consolidate yesterday's activity traces + today's calendar + one proactive suggestion
- evening reflection: summarize the day's key moments and decisions
- "don't interrupt" awareness: kitty reads calendar and defers proactive messages during meetings
- proactive behavior is triggered via cron actions or event-driven signals
- all new code is in gateway modules with routes for brief/reflection endpoints
- `python3.12 -m pytest tests/ -q --tb=short` passes