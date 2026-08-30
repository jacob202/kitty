# Kitty Codebase Map

**Purpose:** authoritative repository navigation for humans and AI workers. Covers boundaries, structure, entry points, and state ownership. Live Git, runtime probes, and accepted ADRs override this document.

## What is Kitty?

Kitty is Jacob's local-first personal AI companion. It runs on a Mac and provides chat, memory, projects, capture, briefs, Tutor, Image Studio, automations, and tools across interchangeable local and cloud models. It preserves context and makes unfinished work resumable.

## Kitty vs KittyBuilder — the boundary

| | Kitty | KittyBuilder |
|---|---|---|
| **Role** | Principal product agent and intent compiler | Execution control plane |
| **Owns** | Conversation, user intent, memory, personal context, projects, documents, artifacts, provider interaction, tools, Tutor, Image Studio, automations, presentation of Builder results | Accepted Missions, initiatives, packets, queues, dependencies, workers, leases, attempts, retries, worktrees, branches, validation, reviews, PRs, budgets, evidence, durable execution state |
| **Interface to the other** | Submits versioned approved Missions | Returns structured results and evidence references |
| **State** | Application database (`data/kitty/kitty.db`), JSONL stores, vector stores, config | `data/kittybuilder/builder_queue.db` — SQLite, read only through supported CLI/API projections |
| **Workers** | Not applicable | Replaceable coding harnesses (OpenCode, Claude Code, Codex, Oh My Pi) — adapters, never authorities |

The accepted boundary is ADR 0017. Builder owns execution state, not product intent. Never infer Builder state from handoff prose, worker output, or UI emptiness.

## System shape

```text
Browser / Raycast / Telegram / Siri / iMessage
  → FastAPI Gateway (port 8000)
    → context_assembler → memory_graph + context_enrichment
    → llm_client → LiteLLM (port 8001) → provider chain
    → KittyBuilder (durable queue, workers, reviews, PRs)
    → tools, MCP, image generation, storage
  → Next.js kitty-chat (port 4000) — thin clients, all product logic in gateway
```

## Annotated top-level directory tree

```
kitty/
├── kitty                   # Bash launcher/operator CLI (up, down, status, doctor,
│                           #   context, builder, governor, tutor, project, push, ...)
├── gateway/                # FastAPI product backend — the product boundary
│   ├── app.py              # FastAPI app setup, middleware, lifespan
│   ├── routes/             # 53 route modules — thin handlers, delegate to domain modules
│   ├── context_assembler.py # Deep 10-step prompt/context assembly pipeline
│   ├── memory_graph.py     # Unified read path across all memory stores
│   ├── llm_client.py       # Table-driven provider dispatcher + fallback chain
│   ├── storage_router.py   # Write seam for app-state stores
│   ├── storage_sync.py     # Export/import snapshot
│   ├── paths.py            # Path constants
│   ├── settings.py         # Gateway settings
│   ├── db.py               # Main SQLite database access
│   ├── builder*.py         # KittyBuilder implementation (queue, leases, runs, workers, etc.)
│   ├── image*.py           # Image generation and character system
│   ├── memory*.py          # Memory, consolidation, policy, weave
│   ├── actions/            # Action handlers for UI-initiated operations
│   ├── stores/             # Specialized store modules
│   ├── migrations/         # Database migrations
│   ├── models/             # Data models
│   ├── connectors/         # External service connectors
│   ├── lib/                # Internal library utilities
│   ├── kitty-chat/         # Next.js product interface
│   │   ├── src/
│   │   │   ├── app/        # Next.js App Router pages
│   │   │   ├── components/ # 60 React components (chat, home, builder, tutor, image, ...)
│   │   │   ├── state/      # React state management (KittyContext)
│   │   │   ├── hooks/      # Custom React hooks
│   │   │   └── lib/        # TypeScript utilities, API clients, types
│   │   ├── tests/          # Vitest + Playwright tests
│   │   └── scripts/        # Visual diff, swarm review, dogfood tests
│   └── tests/              # Gateway-level Python tests
├── tests/                  # Python test suite (214 test files)
├── config/                 # Identity, persona, and behavioral configuration
│   ├── SOUL.md             # Kitty's voice and personality
│   ├── PREFERENCES.md      # Jacob's durable preferences
│   └── USER/               # User-specific configuration
├── soul/                   # Personality definition files
│   ├── kitty.md            # Character definition
│   └── specialists/        # Specialist personality definitions
├── contracts/              # Cross-layer schemas and interface contracts
├── mcp/                    # MCP integrations (image generation via Imagen)
├── scripts/                # Operator, validation, migration, and maintenance tooling
├── docs/                   # Documentation (see docs/README.md for navigation)
│   ├── reference/          # Technical references (this file, patterns, studies)
│   ├── adr/                # Architecture Decision Records
│   ├── plans/              # Candidate work and preserved planning inputs
│   ├── archive/            # Superseded documents and historical material
│   ├── audit/              # Bounded findings and evidence
│   ├── retired/            # Retired operating material
│   ├── research/           # Research notes and studies
│   ├── packets/            # Scoped execution contracts
│   └── initiatives/        # Initiative manifests
├── data/                   # Local runtime state (SQLite DBs, JSONL stores) — not committed
├── logs/                   # Runtime and execution evidence — not committed
├── .github/workflows/      # CI: pytest + lint + typecheck + kitty-chat (vitest + build)
├── AGENTS.md               # Agent operating contract and engineering doctrine
├── CLAUDE.md               # Claude Code-specific instructions
├── CODEX.md                # Codex-specific instructions
├── START_HERE.md           # Cold-start bootloader
├── Makefile                # Common dev commands (test, lint, typecheck, ci, ui-*)
├── pyproject.toml          # Tool config (ruff, mypy, coverage) — not a package definition
├── requirements.txt        # Python dependencies
└── repomix.config.json     # AI context bundle configuration
```

## Runtime entry points

| Entry point | What it does |
|---|---|
| `./kitty up` | Start gateway (8000) + LiteLLM (8001) in background |
| `./kitty down` | Stop all services |
| `./kitty status` | Show process health and status |
| `./kitty doctor --json` | Full preflight check (21+ checks) |
| `./kitty context --agent` | Deterministic repository continuity receipt |
| `./kitty builder --help` | KittyBuilder CLI surface |
| `./kitty governor explain <dispatch.json>` | Dry-run compute governor |
| `cd gateway/kitty-chat && npm run dev` | Start Next.js dev server (port 4000) |
| `cd gateway/kitty-chat && npm run build` | Production build |
| `cd gateway/kitty-chat && npm start` | Production server |
| `./scripts/generate_repo_context.sh` | Generate AI-uploadable repo bundle |

## Data flows

1. **Chat flow:** Client → `gateway/routes/completions.py` → `context_assembler.py` → `memory_graph.py` → `llm_client.py` → LiteLLM → providers
2. **Memory writes:** Domain module → store adapter → SQLite / JSONL / ChromaDB / mem0
3. **Memory reads:** All read paths → `memory_graph.py` (unified adapter fan-in)
4. **Builder execution:** Kitty → approved Mission → `builder_queue.py` → worker adapter → coding harness → review → validation → PR → `builder_publish.py`
5. **Context receipt:** `./kitty context --agent` → `context_receipt.py` → reads docs + git + Builder DB → deterministic JSON receipt

## Authoritative state ownership

| State | Owner | Access |
|---|---|---|
| Product purpose | `docs/NORTH_STAR.md` | Direct read |
| Architecture | `docs/ARCHITECTURE.md` + accepted ADRs | Direct read |
| Delivery sequence | `docs/ROADMAP.md` | Direct read |
| Active mission | `docs/ACTIVE_MISSION.md` | Direct read |
| Shipped capabilities | `docs/PROJECT_STATUS.md` | Direct read |
| Application data | `data/kitty/kitty.db` (SQLite) + JSONL stores | Gateway API / CLI |
| Builder execution | `data/kittybuilder/builder_queue.db` | `./kitty builder initiative doctor --json` |
| Live git/branch | Git + worktree | `git status`, `git log` |
| Session checkpoint | `.claude/STATE.md` + `.claude/HANDOFF.md` | Direct read, only when valid |
| Engineering doctrine | `AGENTS.md` | Direct read |
| Agent tool config | `CLAUDE.md`, `CODEX.md` | Direct read |

Runtime files under `data/` and `logs/` are local, never committed. Builder state must be read through supported Python/CLI projections, never by joining SQLite tables from prose.

## Testing layers

| Layer | Location | Command | File count |
|---|---|---|---|
| Python unit/integration | `tests/` | `python3.12 -m pytest tests/ -q --tb=short` | 214 test files |
| Frontend unit (Vitest) | `gateway/kitty-chat/tests/` | `cd gateway/kitty-chat && npm test` | 38 test files, 295 tests |
| Frontend E2E (Playwright) | `gateway/kitty-chat/tests/` | `cd gateway/kitty-chat && npx playwright test` | smoke tests |
| Visual diff | `gateway/kitty-chat/scripts/` | `make visual-diff` | Screenshot comparison |
| Swarm review | `gateway/kitty-chat/scripts/` | `make swarm-review` | Automated UI code review |

## CI workflow overview

`.github/workflows/tests.yml` runs on all PRs and pushes to main:

| Job | What it runs |
|---|---|
| `pytest` | `python -m pytest tests/` with coverage (≥73% threshold) |
| `lint` | `ruff check gateway/ tests/ mcp/` |
| `typecheck` | `mypy gateway/ mcp/` |
| `kitty-chat` | `npm ci` → `npm test` (Vitest) → `npm run build` |

Additional workflows: `pr-agent-review.yml` (automated LLM PR review via OpenRouter), `pr-description-check.yml`.

## Common change locations

| You want to... | Look here |
|---|---|
| Add an API route | `gateway/routes/` (thin handler) + domain module in `gateway/` |
| Change chat behavior | `gateway/context_assembler.py`, `gateway/llm_client.py` |
| Change memory reads | `gateway/memory_graph.py` (do not bypass) |
| Change the UI | `gateway/kitty-chat/src/components/` |
| Fix Builder execution | `gateway/builder_queue*.py`, `gateway/builder_runner*.py` |
| Add a test | `tests/` for backend, `gateway/kitty-chat/tests/` for frontend |
| Change docs/governance | `docs/` — check authority map first |
| Change provider routing | `gateway/llm_client.py`, `gateway/model_routing.py` |
| Change identity/voice | `config/SOUL.md`, `soul/kitty.md` |

## Files never to edit manually

- `data/` — runtime state, generated at runtime
- `logs/` — execution evidence, generated at runtime
- `.env` — local secrets, read `.env.example` instead
- `gateway/kitty-chat/.next/` — Next.js build output
- `gateway/kitty-chat/node_modules/` — npm dependencies
- `gateway/kitty-chat/package-lock.json` — npm lockfile (don't edit directly)
- `*.pyc`, `__pycache__/` — Python bytecode
- `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` — tool caches
- `.codegraph/` — code intelligence index (managed by CodeGraph)
- Generated bundles under `artifacts/` — not committed

## Key repository documents

| Document | Purpose | Path |
|---|---|---|
| Start here | Cold-start bootloader | `START_HERE.md` |
| Authority map | Where each kind of truth lives | `docs/AUTHORITY_MAP.md` |
| North star | Product purpose and life-first outcome | `docs/NORTH_STAR.md` |
| Agent contract | Engineering doctrine and safety rules | `AGENTS.md` |
| Architecture | Current runnable system and boundaries | `docs/ARCHITECTURE.md` |
| Decisions | Accepted ADRs and supersession | `docs/DECISIONS.md` |
| Roadmap | Only active delivery sequence | `docs/ROADMAP.md` |
| Project status | Verified shipped state | `docs/PROJECT_STATUS.md` |
| Active mission | One approved current mission | `docs/ACTIVE_MISSION.md` |
| Feature reality | Product-surface capability check | `docs/FEATURE_REALITY_2026-07-28.md` |
| Alignment map | Kitty/KittyBuilder layering and authority | `docs/ALIGNMENT_MAP.md` |
| Builder docs | Operator quickstart and Orca setup | `docs/KITTYBUILDER_QUICKSTART.md`, `docs/KITTYBUILDER_ORCA_SETUP.md` |
| Learnings | Durable lessons from past work | `docs/LEARNINGS.md` |
| Constitution | Engineering principles | `docs/CONSTITUTION.md` |
| Docs index | Documentation directory navigation | `docs/README.md` |
| Codebase map | This file | `docs/reference/CODEBASE_MAP.md` |
| Documentation audit | Doc health and disposition | `docs/reference/DOCUMENTATION_AUDIT.md` |
| Context engineering | Staged context-loading workflow | `docs/reference/CONTEXT_ENGINEERING.md` |

## AI context bundle

Run from repo root:

```bash
./scripts/generate_repo_context.sh
```

Produces uploadable files under `artifacts/repo-context/` using `repomix.config.json`. Generated bundles exclude secrets, runtime state, dependencies, caches, and large binary files. Review before uploading.
