# Architecture Migration Analysis — Kitty → Open Brain / Ringer / Open Engine

**Date:** 2026-08-05
**Status:** Draft analysis. No implementation.
**Scope:** Inventory, responsibility mapping, dependency map, migration plan, risks, recommendation.

## Evidence boundaries

- Code inspection: 252 Python gateway modules, 27 builder_*.py modules, 250 test files, 7 gateway/actions, 3 MCP tools, 14 agent skills.
- Documentation inspection: 26 ADRs, ARCHITECTURE.md, NORTH_STAR.md, ROADMAP.md, AUTHORITY_MAP.md.
- Runtime: Not exercised. Builder execution path not live-verified against running instance. This is a structural analysis, not a runtime observation.
- Open Brain / Ringer / Open Engine: Assumed emerging projects. Exact API surfaces, schema, and maturity are UNKNOWN. Classification is structural — the projects' actual capabilities may differ.

---

## 1. Subsystem inventory

Every major subsystem classified: KEEP, REPLACE, MERGE, DELETE, UNKNOWN.

### Execution control plane

| Subsystem | Files | Classification | Why |
|---|---|---|---|
| **Builder queue + state machine** | `builder_queue_db.py`, `builder_queue.py` (task states, transitions, schema, connection) | **MERGE → Open Engine** | Generic task state machine (queued→claimed→running→pr_opened→awaiting_review→done). Terminal states, legal transition map, error classes. Open Engine provides durable execution with equivalent lifecycle. Evidence: 470 lines, 8 states, concurrent-fetch-friendly. |
| **Builder attempts + evidence** | `builder_attempt.py`, `builder_queue_runs.py` | **MERGE → Open Engine** | Per-task attempt tracking with worker identity, start/end timestamps, exit codes, evidence SHA, cost. Open Engine owns attempt records as part of durable execution. |
| **Builder leases** | `builder_queue_leases.py` | **MERGE → Open Engine** | Lease creation, renewal, release, expiry, and fencing. Heartbeat-based. Generic execution infrastructure. |
| **Builder branch leases + PR** | `builder_queue_branch_leases.py`, `builder_publish.py` | **MERGE → Open Engine** | Branch lease = exclusive claim on a git branch per task. PR open/update/merge. This is a novel pattern that Open Engine would need to support, but it's execution infrastructure, not product logic. |
| **Builder worker session** | `builder_worker_session.py` (289 lines) | **MERGE → Ringer** | Abstract WorkerSession interface, event taxonomy (27 event types), snapshot shape. Backend-neutral contract. This is exactly the Ringer worker-orchestration boundary. Evidence: docs/research/kittybuilder-brain-v1-harvest.md references this as canonical. |
| **Builder loop** | `builder_loop.py` (1539 lines) | **MERGE → Ringer + Open Engine** | Per-packet repair loop: implement→validate→review→repair. Bounded by max_attempts. Provider exhaustion handling. Ringer dispatches workers; Open Engine tracks state. The loop logic itself is orchestration. |
| **Builder runner** | `builder_runner.py` | **MERGE → Ringer** | Worktree preflight, archive/reset, worker subprocess launch, timeouts, heartbeats. Worker management infrastructure. |
| **Builder initiative** | `builder_initiative.py` (1743 lines) | **MERGE → Open Engine** | Manifest validation, persistence, packet materialization into queue tasks. Dependency graph (topological sort). Idempotent apply. Initiative state tracking. This is a project-level execution plan — Open Engine needs to understand "initiative = ordered set of packets with dependencies". |
| **Builder context** | `builder_context.py` | **MERGE split** | Builds context manifests for workers. The manifest format is Kitty-specific (what context to include); the delivery mechanism is Ringer's responsibility. |
| **Builder identity** | `builder_identity.py` | **MERGE → Ringer** | Worker identity (worker_id, backend type). Ringer owns worker identity. |
| **Builder status** | `builder_status.py` | **KEEP as adapter** | Read-only projection over Builder state. Kitty needs to see execution state. Keeps reading Open Engine's projection. |
| **Builder contract** | `builder_contract.py` | **KEEP** | Packet validation, acceptance criteria definition, validation commands. These are Kitty's product-specific contract format — *what* to validate, not *how* to execute. |
| **Builder commands / CLI** | `builder_commands.py`, `builder_cli.py` | **KEEP as adapter** | Operator CLI commands (`kitty builder ...`). Keeps the same interface; adapts to Ringer/Open Engine APIs underneath. |
| **Builder events** | `builder_events.py` | **MERGE → Open Engine** | Audit log of events. Open Engine owns execution audit trail. |
| **Builder ISC** | `builder_isc.py` | **KEEP** | ISA-derived success criteria checking. Product-specific verification. |
| **Builder report** | `builder_report.py` | **KEEP** | Kitty-facing result reporting. |
| **Builder scope** | `builder_scope.py` | **KEEP** | Path restriction enforcement. Product-specific safety rule. |
| **Builder adapters** | `builder_adapters.py` | **DELETE** | Adapter layer between Builder subsystems. Becomes unnecessary when subsystems merge into their new homes. |
| **Builder runtime** | `builder_runtime.py` | **MERGE → Open Engine** | Runtime snapshot for manifest. Open Engine provides its own runtime. |
| **Builder brief** | `builder_brief.py` | **KEEP** | Branch naming convention. Product convention. |
| **Builder doctor** | `builder_doctor.py` | **KEEP as adapter** | Health checks. Reads from Open Engine's health endpoint. |

### Memory + context

| Subsystem | Files | Classification | Why |
|---|---|---|---|
| **Memory Graph** | `memory_graph.py` | **MERGE → Open Brain** | Unified read path with adapters, concurrent fetch, structured results. This is Open Brain's core function. Adapter pattern (StoreAdapter ABC, 18 concrete adapters) is a good design that should be re-implemented as Open Brain backends. |
| **Memory Weave** | `memory_weave.py` | **MERGE → Open Brain** | Fact graph (entity, relation, value, confidence, source, deprecation). Open Brain's knowledge graph layer. 44-line SQLite implementation that should move to a shared store. |
| **Memory Policy** | `memory_policy.py` | **MERGE → Open Brain** | What surfaces vs. what's filtered. Access control for memory retrieval. Shared memory authorisation. |
| **Memory Consolidation** | `memory_consolidation.py` | **MERGE → Open Brain** | Summarising traces into durable facts. Memory lifecycle management. |
| **Context Assembler** | `context_assembler.py` | **KEEP** | 10-step prompt assembly pipeline. Domain classification, system prompt loading, personality injection, memory policy filtering, enrichment orchestration, tier-based token budgets. This is Kitty's unique intelligence — what to assemble and how to present it. Open Brain provides the data; Kitty decides relevance. |
| **Context Enrichment** | `context_enrichment.py` | **KEEP (blocks)** | Calendar, weather, todos, iMessage, health, ambient, patterns, learning, nudges, meetings. These are Jacob-specific integrations Kitty owns. The enrichment framework pattern (`run_enrichments` with concurrent gather and per-source failure isolation) is good and stays. |
| **Context Receipt** | `context_receipt.py` | **KEEP** | Deterministic repository continuity snapshot. Read-side projection over Git + docs + Builder status. Kitty-specific operational tool. |
| **Memory adapters** | Various stores | **KEEP as definitions** | The *what* each store provides (journal entries, todos, chat turns, signals, projects, file metadata, knowledge chunks, memory events, inbox items). These stay as Kitty's data model. The *where* and *how to retrieve* moves to Open Brain. |
| **mem0 integration** | `memory.py`, `memory/` | **MERGE → Open Brain** | Semantic/personal memory provider. Open Brain's memory layer. |
| **ChromaDB integration** | `knowledge.py` ingestion, `mempalace_adapter.py` | **MERGE → Open Brain** | Vector storage for reference knowledge. Open Brain provides vector search. |
| **Memory events** | `memory/` | **MERGE → Open Brain** | Memory event schema. Open Brain owns memory events. |

### Knowledge pipeline

| Subsystem | Files | Classification | Why |
|---|---|---|---|
| **Knowledge pipeline** | `knowledge.py` (616 lines) | **MERGE → Open Brain** | Orchestrates document ingestion (extract→judge→chunk→store) and retrieval. Chunk profiles, collection-scoped search, expert answering. This is a shared knowledge pipeline that Open Brain should own. |
| **Clerk** | `clerk.py` | **KEEP as adapter** | Document extraction (PDF, text). Could become an Open Brain ingestion adapter. |
| **Librarian** | `librarian.py` (158 lines) | **MERGE → Open Brain** | Document type detection, quality assessment, chunk profiling. Content judgment belongs in shared memory layer. |
| **Archivist** | `archivist.py` | **MERGE → Open Brain** | Storage layer for knowledge chunks (currently ChromaDB). Open Brain's persistence. |
| **Knowledge contracts** | `contracts/knowledge_pipeline.py`, `contracts/knowledge_chunk.py` | **MERGE → Open Brain** | Data schema for knowledge pipeline. Open Brain's canonical schema. |

### Product features (KEEP)

| Subsystem | Files | Why |
|---|---|---|
| **Chat system** | `chat_lifecycle.py`, `chats_store.py`, `routes/ask.py`, `routes/completions.py`, `routes/chats.py` | Primary user interface. Conversation lifecycle, durable turns, generation attempts. Stores conversation in Open Brain; logic stays Kitty. |
| **Kitty-chat UI** | `gateway/kitty-chat/` (61 components) | Next.js app. Home, Chat, Builder, Image Studio, Settings, Knowledge Library, Projects, Tutor. Unique product surface. |
| **Home / Dashboard** | `HomeView.tsx`, `HomeState.tsx`, `next_step.py` | Life-first daily dashboard. Product-defining feature. |
| **Image Lab** | `image_agent.py`, `image_plan.py`, `image_plans.py`, `image_jobs.py`, `image_sessions.py`, `image_characters.py`, `image_recipes.py`, `image_quality.py`, `image_guidance.py`, `image_runner.py`, `image_backends.py` | Conversational image agent with character consistency, recipes, sessions, quality tiers, guidance tags. Unique product feature. Worker execution (ComfyUI/RunPod dispatch) could use Ringer; the product logic stays. |
| **Tutor** | `tutor.py`, `tutor_cli.py` | RAG learning scaffold with spaced repetition. Pedagogy and UI stay with Kitty. Uses Open Brain's knowledge store. |
| **Brief** | `brief.py`, `brief_scheduler.py` | Morning brief synthesis. Scheduled via Ringer; uses Open Brain data. |
| **Projects** | `project_store.py`, `project_context.py`, `project_resume.py` | Project tracking, context, resume state. Product feature. |
| **Deadlines** | `deadline_extractor.py`, `deadline_store.py`, `deadline_watch.py`, `deadline_sweep.py` | Deadline extraction from documents, tracking, sweep. Product feature. |
| **Voice** | `voice_pipeline.py`, `voice_gate.py`, `voice_middleware.py`, `voice/`, `stt.py`, `tts.py` | Voice input/output pipeline. Product feature. |
| **Connectors** | `connectors/`, `web_monitor.py`, `web_tracker.py` | Mail, GitHub, web monitor connectors. Product integrations. |
| **Delivery channels** | `telegram_bot.py`, `imessage.py`, `push.py` | Multi-surface message delivery. |
| **Doctor** | `doctor.py`, `doctor.sh` | Preflight health checks for the Kitty stack. |
| **Evals** | `eval_runner.py`, `evals/` | Quality measurement. Product tooling. |
| **Personality** | `personality.py`, `config/SOUL.md`, `soul/`, `personality/` | Kitty's voice and identity. |
| **Prompts** | `prompts.py`, `prompts/soul_v1.md` | System prompts loaded by domain. Kitty's thinking instructions. |
| **Domain Router** | `domain_router.py` | Keyword domain classification for prompt selection. Product logic. |
| **Skills** | `.agents/skills/`, `gateway/skill_registry.py`, `gateway/skill_import.py` | Agent skill definitions and registry. The *what* (skill instructions) stays; Ringer dispatches workers with skill context. |
| **MCP servers** | `mcp/imagen/` | Image generation MCP server. Kitty-specific tool. |
| **Actions** | `gateway/actions/` | Action definitions (repair, cleanup, kb query, etc.). Product-specific operations. |
| **Desktop capture** | `desktop_store.py` | Quick Capture inbox. |

### Infrastructure (mixed)

| Subsystem | Files | Classification | Why |
|---|---|---|---|
| **LLM Client + routing** | `llm_client.py` (946 lines), `model_routing.py` | **KEEP** | Table-driven provider dispatch with 6-provider fallback chain. Cost-conscious routing. Kitty's routing policy is product-specific. LiteLLM is a dependency, not custom code. |
| **Gateway** | `app.py`, routes | **KEEP** | FastAPI app. Product web server. Routes are thin handlers delegating to domain modules. |
| **`./kitty` CLI** | `kitty` (854 line bash script) | **KEEP as adapter** | Operator interface. Adapts to call Ringer/Open Engine APIs instead of direct DB access. |
| **Cron** | `cron.py` (300 lines) | **MERGE → Ringer** | Runtime trigger system. Scheduled execution belongs in Ringer. Kitty's cron actions (what runs when) stay as definitions. |
| **Compute Governor** | `compute_governor.py`, `compute_governor_cli.py` | **MERGE → Open Engine** | Agent-work receipts and cost tracking. Execution cost governance belongs in Open Engine. |
| **Runtime Manifest** | `runtime_manifest.py` (375 lines) | **MERGE → Open Engine** | Runtime snapshot composition. Open Engine provides its own runtime manifest. |
| **Signal Store** | `signal_store.py` | **MERGE → Open Brain** | Append table for connector events. Shared memory for signals. |
| **Storage Router** | `storage_router.py` | **KEEP as seam** | Write-side seam for app-state stores. Keeps the thin write-side abstraction; delegates to Open Brain for actual persistence. |
| **db.py** | `db.py` (124 lines) | **KEEP as reduced** | SQLite foundation for app-owned state. Shrinks dramatically when Open Brain owns most storage. Remaining: Kitty-specific config tables only. |
| **Storage Sync** | `storage_sync.py` | **KEEP** | Export/import snapshot. Backup/restore stays with Kitty. |
| **Agent Runner** | `agent_runner.py` | **MERGE → Ringer** | Background agent loop + Algorithm reasoning phases. Worker lifecycle management belongs in Ringer. |
| **Compute Governor** | Separate DB, receipts | **MERGE → Open Engine** | Cost tracking per task. |
| **Launcher configs** | `com.kitty.*.plist` | **KEEP** | macOS launchd plists for auto-start. |
| **LiteLLM config** | `litellm_config.yaml` | **KEEP** | Model proxy configuration. Dependency, not custom. |

### DELETE candidates

| Subsystem | Why |
|---|---|
| `builder_adapters.py` | Wiring between Builder subsystems. Useless after subsystems merge into new homes. |
| `gateway/builder/` | Builder sub-packages. Gets absorbed into Open Engine/Ringer. |
| Subsystem-owned SQLite DBs (cron, builds, task_queue, ingestion, web_monitors, autonomy, model_digest, signals — 8 separate DBs) | Each module manages its own SQLite connection per ADR 0001. Open Brain provides one unified store. These 8 DBs become migration targets, then DELETE. |
| `task_runner.py`, `task_boundary.py` | Generic task execution. Replaced by Ringer. |
| `web_monitor.py`'s own DB | Signal store → Open Brain. |
| `model_digest.py`'s own DB | Model usage stats → Open Engine cost tracking. |
| `builds.db` | Build tracking. Open Engine tracks build artifacts. |

### UNKNOWN (need evidence before classifying)

| Subsystem | Why unknown |
|---|---|
| Open WebUI integration | `openwebui_routing_guards.py` exists. Integration depth unclear without running Open WebUI. Likely KEEP as external integration. |
| `prefetcher.py` | Prefetching logic. May be a performance optimisation that becomes unnecessary with Open Brain's caching. |
| `autonomy_state.py` | Autonomy state tracking. May overlap with Ringer's worker autonomy. |
| `closure` / `magic_kitty.py` | Cross-project insight. Product feature — KEEP. |
| `team_protocol.py` | Multi-agent coordination. May be replaced by Ringer's multi-worker patterns. |
| `buddy_store.py`, `buddy.py` | Buddy/companion state. Product feature — likely KEEP. |
| `journal_store.py`, `journal.py` | Journal feature. Product feature — KEEP. |
| `draft_store.py` | Draft artifacts. Product feature — KEEP. |

---

## 2. Responsibility mapping

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Open Brain                          │ Ringer                            │
│ (shared memory)                     │ (worker orchestration)            │
├─────────────────────────────────────┼───────────────────────────────────┤
│ • Unified memory graph              │ • Worker lifecycle (start, stop,   │
│ • Knowledge vector store            │   monitor, timeout, kill)         │
│ • Fact/knowledge graph              │ • Task dispatch to workers        │
│ • Memory consolidation              │ • Worktree/workspace isolation    │
│ • Memory policy / access control    │ • Heartbeat + health monitoring   │
│ • Signal/event storage              │ • Model/provider selection        │
│ • Document ingestion pipeline       │   at dispatch time                │
│ • Context data (what exists)        │ • Context delivery to workers     │
│ • Memory adapters/backends          │ • Worker identity management      │
│ • Knowledge chunking profiles       │ • Scheduled/cron execution        │
│ • Knowledge quality assessment      │ • Agent loop lifecycle            │
│ • Data contracts and schemas        │ • Concurrency control             │
│ • Chat history storage              │ • Resource budgets per worker     │
│ • Personal semantic memory          │                                   │
│ • File metadata indexing            │                                   │
└─────────────────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Open Engine                         │ Kitty                             │
│ (durable execution)                 │ (the product)                     │
├─────────────────────────────────────┼───────────────────────────────────┤
│ • Task state machine                │ • North Star / purpose            │
│ • Durable task queue                │ • Personality / voice             │
│ • Attempt tracking (per task)       │ • System prompts                  │
│ • Lease management + expiry         │ • Chat system + UI                │
│ • Evidence/result storage           │ • Context assembly (what matters) │
│ • Branch/PR management per task     │ • Context enrichment blocks       │
│ • Cost tracking per attempt         │ • Product features:               │
│ • Recovery from crashes             │   Home, Image Lab, Tutor,         │
│ • Provider exhaustion handling      │   Brief, Projects, Deadlines,     │
│ • Initiative/project execution      │   Dream, Voice, Magic Kitty       │
│ • Audit trail / event log           │ • Connectors (mail, GH, etc.)     │
│ • Runtime manifest                  │ • Delivery channels (phone etc.)  │
│ • Result/evidence flow              │ • Doctor / health checks          │
│ • Budget enforcement                │ • Evals / quality measurement      │
│ • Compute governor (cost tracking)  │ • Skills definitions              │
│                                     │ • MCP servers                     │
│                                     │ • ./kitty CLI                     │
│                                     │ • Gateway / routes                │
│                                     │ • LiteLLM routing policy          │
│                                     │ • Storage sync / backup           │
└─────────────────────────────────────┴───────────────────────────────────┘
```

**No duplicated responsibility.** Every concern has exactly one owner:

- Memory → Open Brain
- Worker dispatch → Ringer
- Durable execution → Open Engine
- Product intelligence → Kitty

---

## 3. Dependency map

### Current

```
┌──────────┐     ┌───────────────┐     ┌────────────┐
│ ./kitty  │────▶│  Gateway      │────▶│  LiteLLM   │
│ CLI      │     │  (FastAPI)    │     │  (proxy)   │
└──────────┘     └───────┬───────┘     └────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌──────────┐   ┌──────────┐   ┌──────────────┐
   │ context  │   │  llm     │   │  routes      │
   │ assembler│   │  client  │   │  (ask, chat, │
   └────┬─────┘   └──────────┘   │   builder,   │
        │                        │   image, etc.)│
        ▼                        └──────┬───────┘
   ┌──────────┐                         │
   │ memory   │◀── read all ────────────┘
   │ graph    │
   └────┬─────┘
        │ adapters: 18 concrete stores
        ├── knowledge (ChromaDB)
        ├── mem0 (semantic memory)
        ├── memory_weave (SQLite fact graph)
        ├── chats_store (SQLite)
        ├── journal_store (JSONL)
        ├── todo_store (SQLite)
        ├── signal_store (SQLite)
        ├── project_store (SQLite)
        ├── deadline_store (SQLite)
        ├── inbox (JSONL)
        └── ... 8 more adapters

   ┌──────────────────┐
   │  KittyBuilder    │ ◀── owns its own SQLite (builder_queue.db)
   │  ┌────────────┐  │
   │  │ initiative │  │
   │  │ queue DB   │  │
   │  │ attempts   │  │
   │  │ leases     │  │
   │  │ branch     │  │
   │  │ events     │  │
   │  │ runner     │──┼──▶ git worktrees
   │  │ loop       │  │     subprocess workers (OpenCode, Claude, shell)
   │  │ publish    │──┼──▶ git push / gh PR
   │  └────────────┘  │
   └──────────────────┘

   8 subsystem-owned SQLite DBs:
   cron.db, builds.db, task_queue.db, ingestion.db,
   web_monitors.db, autonomy.db, model_digest.db, signals.db
```

### Target

```
┌──────────┐     ┌───────────────┐     ┌────────────┐
│ ./kitty  │────▶│  Gateway      │────▶│  LiteLLM   │
│ CLI      │     │  (FastAPI)    │     │  (proxy)   │
└──────────┘     └───┬───┬───┬───┘     └────────────┘
                     │   │   │
          ┌──────────┘   │   └──────────────┐
          ▼              │                  │
   ┌──────────┐          │          ┌───────┴───────┐
   │ Open     │◀─read────┘          │  Kitty routes │
   │ Brain    │                     │  (product)    │
   │ (memory) │                     └───┬─────┬─────┘
   └──────────┘                         │     │
        ▲                               │     │
        │ write                         │     │
   ┌────┴─────┐                  ┌──────┘     └──────┐
   │ Kitty    │                  ▼                    ▼
   │ connectors│          ┌──────────┐        ┌──────────┐
   │ ingestion │          │  Ringer  │        │  Open    │
   └──────────┘           │(dispatch)│        │  Engine  │
                          └────┬─────┘        │(durable) │
                               │              └────┬─────┘
                               ▼                  │
                          ┌──────────┐            │
                          │ Workers  │◀───────────┘
                          │ (Claude, │  context, task, lease
                          │  OpenCode│
                          │  shell)  │
                          └────┬─────┘
                               │
                               ▼
                          ┌──────────┐
                          │ git      │
                          │ worktrees│
                          │ gh PRs   │
                          └──────────┘
```

**Key boundaries:**

1. Kitty reads all memory through Open Brain's unified API — no direct store access.
2. Kitty schedules work through `Ringer.dispatch(task, context)` — no direct worker launch.
3. Ringer asks Open Engine for lease, task state, and evidence — it does not own these.
4. Open Engine tracks every task, attempt, and result. Kitty reads execution status through Open Engine's projection (replaces `builder_status.py`).
5. Kitty connectors write into Open Brain (signals, ingested data).
6. The `./kitty builder` CLI calls Ringer/Open Engine APIs instead of touching `builder_queue.db` directly.

---

## 4. Migration plan

Each phase is independently shippable. No big bang. Kitty remains usable after every step.

### Phase 1 — Extract shared memory definitions (0 risk, no runtime change)

**Goal:** Define what Open Brain needs to store, without changing where anything is stored.

1. Extract adapter schemas into `contracts/open_brain/` — one schema per current memory adapter.
2. Define Open Brain read API surface (equivalent to `MemoryGraph.search_all()` + `GraphResult`).
3. Define Open Brain write API surface (equivalent to signal append, knowledge ingestion).
4. Write a single integration test proving the current memory graph can be called through the Open Brain API contract.

**Files touched:** New contracts only. Zero behavior change.

**Success:** Open Brain contract exists. Current system unchanged.

### Phase 2 — Move knowledge pipeline to Open Brain (low risk)

**Goal:** Move document ingestion and vector search to Open Brain. ChromaDB replaced.

1. Implement Open Brain knowledge store (vector + metadata).
2. Port `knowledge.py`'s orchestration to call Open Brain APIs.
3. Port `librarian.py`'s document classification to run as an Open Brain plugin.
4. Port `archivist.py`'s chunk storage to write to Open Brain.
5. Migrate existing ChromaDB collections to Open Brain.
6. Delete ChromaDB dependency.

**Files touched:** `knowledge.py`, `librarian.py`, `archivist.py`, `clerk.py`, `mempalace_adapter.py`.
**Rollback:** ChromaDB data stays until migration verified. Revert to Phase 1 code.

### Phase 3 — Move signal store to Open Brain (low risk)

**Goal:** Signal events write to Open Brain instead of the local `signals` SQLite table.

1. Implement Open Brain signal API.
2. Update `signal_store.py`'s adapter to write through Open Brain.
3. Update emitters (`web_monitor.py`, `nudge.py`) — no change needed if adapter is transparent.
4. Migrate existing signals.

**Files touched:** `signal_store.py`, `memory_graph.py` (SignalsAdapter).

### Phase 4 — Unify 8 subsystem-owned SQLite DBs into Open Brain (medium risk)

**Goal:** Eliminate per-module SQLite connections. All app-state in Open Brain.

1. Migrate `cron_schedules` → Open Brain.
2. Migrate `builds` → Open Brain.
3. Migrate `task_queue` → Open Brain.
4. Migrate `ingestion_queue` → Open Brain.
5. Migrate `web_monitors` state → Open Brain.
6. Migrate `autonomy` state → Open Brain.
7. Migrate `model_digest` → Open Brain.
8. Delete subsystem DB files.

**Files touched:** Each module's DB connection code. `db.py` shrinks to Kitty-specific config only.

### Phase 5 — Move task execution to Open Engine + Ringer (high risk, verified carefully)

**Goal:** Builder queue DB becomes a read-only legacy store. Ringer dispatches workers; Open Engine tracks state.

1. Implement Open Engine task state machine (equivalent to current builder_queue_db.py states).
2. Implement Open Engine attempt tracking (replaces builder_attempt.py).
3. Implement Open Engine lease management (replaces builder_queue_leases.py).
4. Implement Ringer worker session (replaces builder_worker_session.py lifecycle).
5. Implement Ringer worktree management (replaces builder_runner.py).
6. Wire `builder_loop.py` to use Ringer dispatch + Open Engine state.
7. Run existing test suite against new backends. Run daylight unattended packet.
8. Declare legacy Builder DB read-only. Delete after verification period.

**Files touched:** All 27 builder_*.py, builder_runner.py, builder_loop.py.
**Rollback:** Switch back to direct SQLite. Ringer/Open Engine are optional dispatch paths.

### Phase 6 — Move compute governor to Open Engine (low risk)

**Goal:** Cost tracking moves to Open Engine's per-attempt accounting.

1. Open Engine tracks costs per task attempt.
2. `compute_governor.py` reads from Open Engine instead of its own DB.
3. Delete `compute_governor/` directory.

### Phase 7 — Move cron to Ringer (medium risk)

**Goal:** Ringer handles scheduled execution.

1. Define cron schedules as Ringer triggers.
2. Ringer dispatches scheduled actions as tasks.
3. Delete `cron.py`'s runtime runner. Keep schedule definitions.

### Phase 8 — Cleanup (safety only, no feature change)

1. Delete `builder_adapters.py` (wiring no longer needed).
2. Delete `builder/` sub-package (absorbed).
3. Delete `task_runner.py`, `task_boundary.py` (replaced by Ringer).
4. Remove ChromaDB from `requirements.txt`.
5. Remove mem0 from `requirements.txt` (Open Brain provides semantic memory).
6. Remove 8 subsystem DB files from `data/`.
7. 27 builder modules shrink to ~8 (contract, status, commands, CLI, ISC, report, scope, brief).

---

## 5. Risks

### Duplicated functionality (already exists)

| What | Where in Kitty | Also in |
|---|---|---|
| Task state machine | `builder_queue_db.py` (8 states, legal transitions) | Open Engine |
| Lease/heartbeat fencing | `builder_queue_leases.py` | Open Engine |
| Worker session lifecycle | `builder_worker_session.py` (27 events) | Ringer |
| Worktree isolation | `builder_runner.py` | Ringer |
| Attempt tracking | `builder_attempt.py` | Open Engine |
| Provider exhaust handling | `builder_loop.py` (provider_exhausted state, exit code 75) | Open Engine |
| Audit trail | `builder_events.py` | Open Engine |
| Cost tracking | `compute_governor.py` (own DB) | Open Engine |
| Scheduled execution | `cron.py` (own runner) | Ringer |
| Vector search | `knowledge.py` → ChromaDB | Open Brain |
| Semantic memory | `memory.py` → mem0 | Open Brain |
| Fact graph | `memory_weave.py` (44-line SQLite) | Open Brain |
| Memory consolidation | `memory_consolidation.py` | Open Brain |
| Signal/event store | `signal_store.py` (own SQLite table) | Open Brain |
| Knowledge ingestion | `knowledge.py` → librarian + archivist | Open Brain |

### Architectural debt

1. **8 subsystem-owned SQLite databases** (ADR 0001). Each module manages its own connection. Schema migrations are scattered. Connection pooling is per-module. This is the primary architectural debt — Phase B declared consolidation but never reached these.

2. **Builder queue DB is a second state machine** (ADR 0017 explicitly forbids joining its tables into another state machine, but the tables exist and the boundary is code convention, not enforced).

3. **`builder_adapters.py`** is a wiring layer that only exists because Builder grew across 27 modules. This is a module-count problem, not a capability problem.

4. **`./kitty` CLI directly queries `builder_queue.db`** via Python subprocess. No API boundary between the operator and execution state.

5. **genEvolve/ComfyUI worker is separate** from the Builder worker system. Two worker execution paths (Builder loop vs. image runner → `workers/comfy_worker/`). Bild workers use shell subprocess; image workers use HTTP to ComfyUI server. Unification target.

### Unnecessary custom code

- **`builder_queue_db.py`**: Full SQLite task state machine (470 lines). This is a solved problem.
- **`builder_queue_leases.py`**: Lease management is a solved problem.
- **`builder_runner.py`**: Worktree isolation and subprocess worker management is a solved problem.
- **`memory_weave.py`**: 44-line SQLite fact graph. Simple, but unnecessary when Open Brain provides this.
- **`cron.py`**: Custom runtime scheduler (300 lines). Launchd does this; Ringer does this better.
- **`compute_governor.py`**: Custom cost tracking DB. Open Engine tracks costs per task.

Total custom code that could be deleted: **~4,000 lines** across builder infrastructure modules + cron + compute governor.

### Vendor lock-in

- **ChromaDB**: Vector store. Replaced by Open Brain. **Low risk** — ChromaDB has no lock-in beyond data format.
- **mem0**: Semantic memory. Replaced by Open Brain. **Low risk** — API-based, migratable.
- **LiteLLM**: Model proxy. **Keep** — it is the correct tool for model routing and Kitty doesn't reimplement it.
- **OpenRouter**: Provider API. **Keep** — it is a model provider, not infrastructure.
- **Orca**: Worktree/terminal/browser automation. **Keep** — it is a worker adapter, not infrastructure.

### Migration risks

1. **Phase 5 (task execution) is the high-risk point.** If Open Engine or Ringer are unstable or incomplete, Builder execution regresses. Mitigation: run both systems in parallel (legacy Builder + new path) until proven.

2. **Data migration.** Moving 8 SQLite DBs + ChromaDB into Open Brain requires schema translation. Mitigation: each phase migrates one store at a time; rollback preserves source data.

3. **Context assembly quality.** Moving memory to Open Brain changes the search path. Context assembly must produce identical or better results. Mitigation: run side-by-side context assembly evaluation before and after each phase.

4. **Test coverage.** 250 test files exist, but Builder execution path tests (`test_builder_loop.py`, `test_builder_runner.py`) may not cover edge cases surfaced by distributed execution. Mitigation: add contract tests before migration.

5. **Unknown API surfaces.** Open Brain, Ringer, and Open Engine are assumed projects. Their actual APIs, data schemas, and maturity are UNKNOWN. This entire analysis is structural — validate API fitness before any implementation.

### Rollback strategy

Every phase must be independently reversible:

- **Phases 1-4:** Keep existing stores. Add Open Brain as a parallel read/write path. Switch a feature flag to use the new path. Rollback = flip flag.
- **Phase 5:** Run legacy Builder and new path in parallel. Compare results for identical packets. Rollback = disable new path.
- **Phases 6-8:** Feature-flagged. Rollback = revert flags.

No phase deletes source data until the next phase is verified.

---

## 6. Final recommendation

> **If we started Kitty today knowing Open Brain, Ringer, and Open Engine existed, what would we still build ourselves?**

**We would build:**

1. **Context assembly.** How Kitty decides what's relevant from the shared memory. Domain classification, system prompt loading, personality injection, enrichment orchestration, tier-based token budgets. Open Brain stores the data; Kitty decides what matters. This is Kitty's core intelligence and no generic tool does it.

2. **Chat system and UI.** The Next.js app, conversation lifecycle, Home dashboard, Image Studio, Tutor UI. These are the product surface. No third-party tool replaces them.

3. **Product features.** Image Lab (conversational character-aware generation), Projects (resume/next-step), Deadlines, Brief synthesis, Voice pipeline, Dream Insights, Magic Kitty. These are Kitty's unique product — they use the infrastructure but are not defined by it.

4. **Personality, prompts, soul.** Kitty's voice, thinking instructions, and identity. These are configuration, not infrastructure.

5. **Connectors and delivery channels.** Mail, GitHub, web monitor, iMessage, Telegram, push. These are product-specific integrations that ingest into shared memory and deliver to Jacob's surfaces.

6. **The `./kitty` CLI.** Operator interface. It becomes thinner (delegates to Ringer/Open Engine) but stays as the single operational surface.

7. **Builder contract format.** Initiatives, packets, acceptance criteria, validation commands, policy definitions. These are Kitty's *what to execute* — Ringer and Open Engine handle the *how*.

8. **LiteLLM routing policy.** Which model to use for which task at which cost. This is product-specific cost/quality tradeoff. The routing mechanism (LiteLLM/OpenRouter) is a dependency; the policy is owned.

9. **Skills and MCP servers.** Agent instructions and tool definitions. Ringer dispatches workers with these skills; Kitty defines what skills exist.

10. **Evals and quality measurement.** Kitty-specific testing for products features.

**We would NOT build:**

- A custom task queue / state machine (use Open Engine)
- Lease management and heartbeat fencing (use Open Engine)
- Worker lifecycle management (use Ringer)
- Worktree isolation logic (use Ringer)
- Document ingestion pipeline (use Open Brain)
- Vector search and knowledge store (use Open Brain)
- Semantic memory (use Open Brain)
- Fact graph (use Open Brain)
- Memory consolidation (use Open Brain)
- Signal/event store (use Open Brain)
- Cost tracking and compute governance (use Open Engine)
- Scheduled execution (use Ringer)
- Subsystem-owned SQLite databases (use Open Brain persistence)
- ChromaDB as a dependency (use Open Brain)
- mem0 as a dependency (use Open Brain)
- `builder_adapters.py` wiring layer (unnecessary when subsystems use shared infrastructure)
- `cron.py` runtime scheduler (use Ringer)

**The total is clear:** Kitty's unique value is approximately 40% of its current codebase — the product surface, intelligence layer, and personal integrations. The remaining ~60% is infrastructure that Open Brain, Ringer, and Open Engine are designed to provide.

### Lines of code impact (estimated from file sizes and module counts)

| Category | Current (est. LOC) | Target (est. LOC) | Delta |
|---|---|---|---|
| Builder infrastructure (queue, leases, attempts, events, runner, loop, runtime, adapters, identity, worker session) | ~8,500 | ~1,500 (contract, status, commands, CLI, ISC, report, scope, brief) | **-7,000** |
| Memory/knowledge infrastructure (memory_graph, memory_weave, memory_consolidation, knowledge, librarian, archivist, clerk, signal_store, ChromaDB adapter, mem0 adapter) | ~3,500 | ~800 (contracts, enrichment blocks, clerk adapter) | **-2,700** |
| Cron | 300 | 0 | **-300** |
| Compute governor | 400 | 0 | **-400** |
| 8 subsystem DB connections | ~500 | 0 | **-500** |
| Product features (chat, image, tutor, brief, projects, deadlines, voice, connectors, routes, UI) | ~18,000 | ~18,000 | 0 |
| Gateway, CLI, routing, prompts, personality | ~6,000 | ~5,500 (CLI delegates to Ringer/Open Engine APIs) | **-500** |
| **Total** | **~37,200** | **~25,800** | **-11,400** |

This is approximately a **30% reduction** in maintained code, while preserving every product feature.

### The one thing to get right

The boundary between Kitty's context assembly and Open Brain's memory graph. If Kitty can't ask "what's relevant from Jacob's memory?" with the same quality after the migration, nothing else matters. This must be the first integration test and the last acceptance test.
