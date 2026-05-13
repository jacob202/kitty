# Feature Inventory — AgentCompany/Kitty
**Date:** April 9, 2026  
**Author:** Knowledge Audit  
**Purpose:** Comprehensive inventory of planned, implemented, and missing features across Orange Lab → AgentCompany → Kitty consolidation phases.

---

## 1. Core Architecture Decisions

### Identity & Naming Evolution
- **Orange Lab** (April 6-7): First phase focusing on PKA (Personal Knowledge Assistance) with personality engine
- **AgentCompany** (April 8): Brief intermediate naming
- **Kitty** (April 9): Finalized project name. Official autonomous CLI/Web AI assistant with orchestration layer

### Key ADRs (Architecture Decision Records)
1. **ADR-001: Hybrid SQLite-Vec Memory Architecture** ✅
   - Hybrid SQLite + sqlite-vec for semantic search + structured queries
   - Ollama (`nomic-embed-text`) for 768-d embeddings with random fallback
   - File: `/Users/jacobbrizinski/AgentCompany/docs/superpowers/plans/ADR-001-vector-memory.md`

2. **ADR-002: Token Manager for Unattended Execution** ⚠️
   - Token ceiling at 80k tokens; compacts history keeping system prompt + last 4 turns + sentinel
   - 4-char-per-token heuristic (underestimates code ~15%)
   - File: `/Users/jacobbrizinski/AgentCompany/docs/superpowers/plans/ADR-002-token-manager.md`
   - Implementation status: `token_manager.py` recreated at root in ADR but NOT yet at `/Users/jacobbrizinski/AgentCompany/token_manager.py`

3. **ADR-003: Unified Startup Scripts** ✅
   - `start.sh`: Activates venv + execs cli.py
   - `dev.sh`: Launches web.py + kitty-chat dev server with graceful Ctrl+C
   - Files: `/Users/jacobbrizinski/AgentCompany/start.sh`, `/Users/jacobbrizinski/AgentCompany/dev.sh`

### Tiered Model Architecture
- **L4 (Specialists)**: Claude/Gemini (heavy, expensive, for complex reasoning)
- **L3 (Logic/Analysis)**: Qwen 2.5 Coder or DeepSeek (mid-tier logic, cheaper)
- **L2 (Vision)**: Florence-2 local or Mistral OCR (schematic parsing)
- **L1 (Gatekeeper)**: MLX Dolphin-Qwen local (fast intent routing, free)
- **L0 (Shadow)**: Local Ollama models (dev/offline mode)

### Model Defaults (as of April 9)
- Primary fast model: `deepseek/deepseek-chat` via OpenRouter ($0.00014 input / $0.00028 output per 1K)
- Fallback: `google/gemini-2.5-flash`
- Heavy: `anthropic/claude-3-5-sonnet` (when needed)
- OpenRouter Auto-Router for intelligent load-balancing

---

## 2. Implemented Features

### 2.1 Core Infrastructure

#### Orchestration & Task Dispatch
- **tool_dispatcher.py** ✅ 
  - File: `/Users/jacobbrizinski/AgentCompany/src/core/tool_dispatcher.py`
  - Routes tasks to Aider, AutoGPT, Jules, Swarms, or Claude Code
  - Selects optimal tool based on task intent (code modification, research, testing, refactoring, parallelization)

#### Job Queue & Parallel Execution
- **job_queue.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/orchestrator/job_queue.py`
  - SQLite priority queue with WAL mode
  - Methods: `enqueue()`, `dequeue()`, `update_status()`

- **parallel_dispatcher.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/orchestrator/parallel_dispatcher.py`
  - Concurrent subprocess runner with watchdog thread + PID validation
  - Spawns background workers (Aider, AutoGPT) without blocking main thread

#### Event Store
- **event_store.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/core/event_store.py`
  - Append-only event log with SQLite AUTOINCREMENT sequence numbers
  - Enables audit trail and session reconstruction

#### Logging & Observability
- **canonical_logger.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/canonical_logger.py`
  - Updated to write `seq_id` to every log entry for correlation
  - CORRELATION_ID support for tracing background panes to user requests
  - Canonical log: `/Users/jacobbrizinski/AgentCompany/logs/canonical_log.jsonl`

- **project_logger.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/project_logger.py`
  - Logs tool invocations, decisions, and user interactions

#### Health & Reliability
- **health_monitor.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/health_monitor.py`
  - Health checks for Ollama, ChromaDB, SQLite
  - Periodic availability probes

- **circuit_breaker.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/circuit_breaker.py`
  - SQLite-backed circuit breaker decorator
  - Prevents cascading failures when services are down

### 2.2 Memory & Persistence

#### Hybrid Vector Memory
- **journal_db.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/journal_db.py` (root) + `/Users/jacobbrizinski/AgentCompany/src/utils/token_manager.py`
  - SQLite + sqlite-vec (KNN index on 768-d embeddings)
  - Tables: `entries` (metadata), `vec_entries` (embeddings), `learning`, `contacts`
  - Hybrid search with optional type filtering
  - Ollama fallback to random unit-normalized vectors when offline
  - Tested with 26 tests across 6 test classes

#### Context Management
- **context_loader.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/core/context_loader.py`
  - Dynamically loads domain-specific context from `~/Documents/Kitty/contexts/`
  - Keyword matching for context injection
  - Always injects `preferences.json` for user persona/standards

#### Token Management
- **token_manager.py** ⚠️
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/token_manager.py` (in src/)
  - Root-level file NOT yet created per ADR-002
  - Methods: `estimate_tokens()`, `compact_history()`, `should_compact()`
  - Guards on FAST_API + COUNCIL_HEAVY routes in supervisor.py (lines 2117–2140)
  - 12 passing tests cover edge cases

### 2.3 Models & Routing

#### Supervisor (Orchestrator Core)
- **supervisor.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/supervisor.py` (118 KB, core logic)
  - Multi-LLM routing (OpenAI, Anthropic, Google, DeepSeek)
  - Context injection and session persistence
  - Tool execution within autonomous loop
  - Personality state tracking (CALM vs UNHINGED)
  - Council of Five assembly (dynamic expert personas)
  - Token compaction on FAST_API/COUNCIL_HEAVY paths
  - 3 routing paths: LOCAL_PKA, FAST_API, COUNCIL_HEAVY

#### Model Callers
- **model_caller.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/core/model_caller.py`
  - Abstracts LLM API calls (Anthropic, Google, OpenRouter, etc.)
  - Handles streaming, token counting, cost tracking

#### Agent Router
- **agent_router.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/core/agent_router.py`
  - Routes queries to specialized domain agents (electronics, automotive, health, coding)
  - Agent definitions in `/Users/jacobbrizinski/AgentCompany/data/agents/`:
    - `electronics.json` — Sansui amp repair specialist
    - `electronics_repair.json` — Advanced repair techniques
    - `automotive.json` — 2007 Honda Ridgeline specialist
    - `health.json` — ADHD, sleep, wellness context
    - `coder.json` — Python/JS development
    - `general.json` — Default fallback
    - `vision.json` — Vision tasks
    - `market_researcher.json` — Market research

### 2.4 UI & Frontend

#### CLI Interface
- **cli.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/cli.py` (54 KB)
  - Rich-based terminal UI with color-coded help sections
  - Commands: `/help`, `/prep`, `/capture`, `/stuck`, `/brief`, `/bench`, `/vibe`, `/ingest`, `/search`
  - **PENDING**: Dynamic terminal columns (Columns API from rich) — needs update to `print_help()` and `print_banner()`

#### Web Dashboard
- **web.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/web.py` (59 KB)
  - Flask backend on port 5001
  - WebSocket/SSE for real-time state hydration
  - Shared PKAMemoryDB instance with CLI
  - Endpoints: `/api/journal`, `/api/components`, `/tool/analyze_schematic`

#### Next.js Frontend (kitty-chat)
- **CommandPalette.tsx** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/kitty-chat/app/components/CommandPalette.tsx`
  - Dynamic CSS grid: auto-fill with minmax(220px, 1fr)
  - Responsive modal width (mobile to xl screens)
  - 5 color-coded categories: SYSTEM, MODE, ACTION, MEMORY, VIEW
  - Commands: `/ingest`, `/search`, `/vibe`, `/stuck`, etc.

- **kitty-chat/.env.local** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/kitty-chat/.env.local`
  - Points backend to localhost:5001

### 2.5 Data Processing & Analysis

#### Graph Processing
- **hardware_subgraph.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/graphs/hardware_subgraph.py`
  - Schematic extraction, component graph, failure mode analysis
  - Reflexion loop for retry on failed extractions
  - Quarantine log for unresolved items

- **investigative_subgraph.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/graphs/investigative_subgraph.py`
  - Problem-solving & research workflow

- **main_graph.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/graphs/main_graph.py`
  - LangGraph orchestration of subgraphs

#### DuckDB Analytics
- **duckdb_client.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/duckdb_client.py`
  - Fast component queries
  - Supports `/components` endpoint returning DuckDB results

#### SVG & Visualization
- **svg_generator.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/utils/svg_generator.py`
  - Schematic overlay generation
  - Color bounding boxes by confidence (green/yellow/red)

#### Schema Management
- **hardware.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/schemas/hardware.py`
  - Pydantic schemas for component, connection, failure modes

- **investigative.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/schemas/investigative.py`
  - Schemas for research/analysis workflows

#### Prompt Optimization
- **prompt_optimizer.py** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/src/nodes/prompt_optimizer.py`
  - Triggers when quarantine > 5 items
  - Refines extraction prompts based on failure patterns

### 2.6 Development & Operations

#### Docker Orchestration
- **docker-compose.yml** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/docker-compose.yml`
  - Services: ChromaDB, Flask backend, Next.js frontend
  - Health checks configured

#### Startup Scripts
- **start.sh** ✅ (ADR-003)
  - File: `/Users/jacobbrizinski/AgentCompany/start.sh`
  - Activates venv + execs cli.py with forwarded arguments

- **dev.sh** ✅ (ADR-003)
  - File: `/Users/jacobbrizinski/AgentCompany/dev.sh`
  - Launches web.py + kitty-chat with graceful Ctrl+C

- **dev_setup.sh** ✅
  - File: `/Users/jacobbrizinski/AgentCompany/scripts/dev_setup.sh`
  - Native vs Docker setup choice
  - Tmux session management (`gemini-cli`)
  - Preflight checks (venv, node_modules, Ollama)

#### Installation & Dependency Scripts
- **check_deps.py** ✅
  - Verifies sqlite-vec, requests, pytest, etc.

- **install.py** ✅
  - Automated dependency installation

- **batch_ingest.py** ✅
  - Pueue batch ingestion script for document processing

#### Health & Testing
- **health_check.py** ✅
  - Nightly checks for Ollama, ChromaDB, SQLite
  - Runs as background service

- **assess_system.py** ✅
  - System capability profiler

- **audit_databases.py** ✅
  - Database integrity audits

---

## 3. Planned But Not Built

### 3.1 Missing Core Features

#### Token Manager Root File
- **token_manager.py** ❌ NOT AT ROOT
  - ADR-002 specifies recreation at `/Users/jacobbrizinski/AgentCompany/token_manager.py`
  - Exists only in `/Users/jacobbrizinski/AgentCompany/src/utils/token_manager.py`
  - Tests in `tests/test_token_manager.py` import from root path `from token_manager import TokenManager`
  - **ACTION REQUIRED**: Create root-level file with simplified interface

#### CLI Dynamic Terminal Columns
- **print_help() multi-column layout** ❌
  - Handoff-2026-04-09.md (Priority 1) specifies:
    - Use `rich.columns.Columns` for side-by-side panels
    - Width-aware column scaling (console.width)
    - Color-coded section headers (orange/cyan/magenta/green/yellow/blue/gold/white)
    - Remove `/chatbox` section, prune quick-start
  - Current: Fixed single-column layout
  - **BLOCKER**: Prevents responsive help display on wide terminals

#### MCP Server Registration
- **MCP Servers Config** ❌ INCOMPLETE
  - Handoff-2026-04-09.md (Priority 2) specifies manual registration:
    ```bash
    claude mcp add claude-flow -- npx -y @claude-flow/cli@latest
    claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /Users/jacobbrizinski
    claude mcp add github -- npx -y @modelcontextprotocol/server-github
    ```
  - Status: Not in `/~/.claude/claude_desktop_config.json` yet

#### Aider Installation & Configuration
- **Aider Setup** ⚠️ INCOMPLETE
  - Requires: `pip install aider-chat` (if not already in venv)
  - Configuration: `.aider.model.settings.yml` to use `claude-sonnet-4-6` by default
  - Verification: `aider --version` must succeed with venv active

#### API Key Security
- **ANTHROPIC_API_KEY Rotation** ❌ NOT DONE
  - Handoff-2026-04-09.md (Priority 4) specifies:
    - Old key was hardcoded, now removed
    - **ACTION REQUIRED**: 
      1. Rotate at console.anthropic.com
      2. Add to `~/.zshrc`: `export ANTHROPIC_API_KEY="sk-ant-...new-key..."`

### 3.2 Phase 2 Tasks (Planned but not started)

From `docs/handoffs/TODO.md` "Later (Phase 3 – Polish)":
- **Agent Activity Log with SSE Streaming** ❌
- **Lottie Mascot with Expressions** ❌
- **BOM Export as CSV from DuckDB** ❌

From Kitty Orchestration Plan (unfinished tasks 4-6):
- **Task 4: Front-end Experience Workflow** ❌
  - Mount WebSocket events for node_status and thinking_bubble
  - Theme engine adaptive mode switching (Hardware: Orange, Investigative: Green)
  
- **Task 5: Back-end Stress Testing** ❌
  - AutoGPT document injection (1000 pages)
  - VRAM monitoring
  
- **Task 6: Vector Search Web Integration** ❌
  - `/api/journal/search` endpoint with vector search tests

### 3.3 Agent Installation Status

From Preflight Report (2026-04-09_182245):
- **Jules** ❌ Missing
  - Use: Large-scale refactoring, comprehensive unit testing
  - Status: Not in PATH or project
  
- **Swarms** ❌ Missing
  - Use: Parallel task execution across multiple agents
  - Status: Not in PATH or project

---

## 4. User Preferences & Recurring Requests

### User Profile (Jacob)
- **Context**: ADHD, electronics repair enthusiast, automotive DIY
- **Hardware**: Sansui AU-7900 amplifier (primary electronics project), 2007 Honda Ridgeline
- **Health**: NP appointments, sleep/wellness tracking
- **Preferences**: 
  - Direct, unfiltered responses
  - Action-oriented over explanatory
  - Hardware-first (electronics > automotive > general coding)

### Noted But Not Yet Implemented
From `docs/handoffs/CURRENT_STATE.md`:
- **User Steering (Session 2026-04-09)**:
  1. Focus on **operational robustness** over new features
  2. Provide 8-point "Operational Polish" list (now mostly done)
  3. Error recovery & git watchdog still pending
  4. Dispatcher unit testing (dry-run mode) still pending

### CLI Commands User Actually Uses
From Handoff:
- Core daily: `/prep`, `/capture`, `/stuck`, `/brief`
- Hardware: `/bench sansui`, `/bench ridgeline`
- Memory: `/vibe`
- **Commands to remove**: `/chatbox`, `/screen` (from quick-start), `/pattern` (too generic)

---

## 5. Agent & Tool Inventory

### Named Systems & Personas

#### Kitty (Core Orchestrator)
- **Role**: Autonomous CLI/Web AI assistant with task dispatch
- **Architecture**: Gemini (decision-making) + Aider + AutoGPT + Jules + Swarms (execution)
- **Status**: ✅ Implemented, operational as of April 9

#### Orange Lab (Legacy, now Kitty)
- **Original Goal**: Personal Knowledge Assistance with personality engine
- **Components**: PKA database, Council of Five, Token manager
- **Status**: ✅ Core components integrated into Kitty

#### Council of Five
- **Purpose**: Dynamic assembly of 4-5 expert personas for complex questions
- **Implementation**: `supervisor.py` `assemble_council()` method
- **Status**: ✅ Implemented (may need LangGraph refinement per architectural teardown)

#### PKA (Personal Knowledge Assistance)
- **Purpose**: Local semantic memory with journaling + learning + contacts
- **Implementation**: `journal_db.py` (SQLite + sqlite-vec)
- **Status**: ✅ Implemented with hybrid search

### External Agent Tools
- **Aider** ✅ Installed (code writing/debugging)
- **AutoGPT** ✅ Installed (complex reasoning, research)
- **Claude Code** ✅ Available via Claude CLI (coding assistance)
- **Jules** ❌ Missing (refactoring, testing)
- **Swarms** ❌ Missing (parallel execution)

### Domain-Specific Agents
Located in `/Users/jacobbrizinski/AgentCompany/data/agents/`:
- **electronics.json** — Component analysis, failure modes, schematic reading
- **electronics_repair.json** — Advanced repair techniques, troubleshooting
- **automotive.json** — Vehicle repair, maintenance, Ridgeline-specific knowledge
- **health.json** — ADHD, sleep hygiene, wellness coaching
- **coder.json** — Python, JavaScript, architecture review
- **general.json** — Default fallback for open-ended queries
- **vision.json** — Image analysis, OCR, schematic extraction
- **market_researcher.json** — Market research, competitor analysis

### Memory & Knowledge Bases
- **Local PKA Database**: `orange_lab_pka.db` (journal, learning, contacts)
- **Chroma Vector Store**: `vector_store/chroma_db/` (1.4GB global library, manuals, schematics)
- **Canonical Log**: `logs/canonical_log.jsonl` (JSONL event stream of all extracted components/edges)
- **Quarantine Log**: `quarantine_log.jsonl` (unresolved extractions for refinement)

### Tool Availability Matrix

| Tool | Installed | Used | File/Location |
|------|-----------|------|---------------|
| Aider | ✅ Yes | Code modification, debugging | `venv/bin/aider` |
| AutoGPT | ✅ Yes | Complex research, reasoning | `venv/bin/autogpt` |
| Claude Code | ✅ Yes | Coding, architecture review | Via Claude CLI |
| Jules | ❌ No | Refactoring, testing | — |
| Swarms | ❌ No | Parallel execution | — |
| Ollama | ✅ Yes | Local embeddings, gatekeeper | `localhost:11434` |
| ChromaDB | ✅ Yes | Vector search (manuals) | `vector_store/chroma_db/` |
| DuckDB | ✅ Yes | Component analytics | In-memory SQL queries |

---

## 6. Session Metadata

### Sessions Audited
1. **Orange Lab Architecture** (April 6-7, 2026)
   - Source: `docs/superpowers/specs/2026-04-07-architectural-teardown.md`
   - Outcome: PKA system designed, token manager + council of five planned

2. **Kitty Consolidation** (April 9, 2026)
   - Source: `docs/HANDOFF-2026-04-09.md` + `docs/PROJECT_OVERVIEW_AND_AUDIT.md`
   - Outcome: Identity unified as "Kitty", orchestration layer implemented

3. **Operational Polish** (April 9, 2026)
   - Source: `docs/handoffs/HANDOFF_RESUME.md`
   - Outcome: Most safety nets built (vector DB concurrency, SSE sync, token accounting), 2 items pending

### Files Audited (Complete List)
- Documentation: 23 files (plans, specs, handoffs, audit reports)
- Source code: 50+ Python modules across src/, scripts/, root
- Configuration: docker-compose.yml, .env files, agent JSON definitions
- Tests: pytest suite with 12+ test classes, 50+ passing tests

---

## 7. Cross-Reference: What's Lost vs. What's Safe

### Potentially Lost (No Current Implementation)
- Jules agent (unit testing, refactoring automation)
- Swarms agent (parallel task coordination)
- CLI responsive columns (terminal width adaptation)
- Lottie mascot animations
- BOM export features
- API key rotation documentation

### Safely Preserved
- All ADR decisions (ADR-001, ADR-002, ADR-003)
- All domain-specific agent definitions (8 agents)
- All core Python modules (50+ files)
- All handoff documents (CURRENT_STATE, TODO, HANDOFF, HANDOFF_RESUME, GEMINI)
- All planning documents (Orchestration Plan/Design, Orange Lab specs)
- Canonical log of all extracted components (canonical_log.jsonl)
- Session transcripts and audit reports

---

**END OF FEATURE INVENTORY**
