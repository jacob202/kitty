# Kitty Codebase Map

**Purpose:** authoritative repository navigation for humans and AI workers. Covers boundaries, structure, entry points, and state ownership. Live Git, runtime probes, and accepted ADRs override this document.

**Materially revalidated:** 2026-09-03 against `main` `8b4550e20f4fa24bb047adb61d18793b859c2707`. Volatile inventory counts are intentionally omitted.

## What is Kitty?

Kitty is Jacob's local-first personal AI companion. It runs on a Mac and provides chat, memory, projects, capture, briefs, Tutor, Image Lab, automations, and tools across interchangeable local and cloud models. It preserves context and makes unfinished work resumable.

## Kitty vs KittyBuilder — the boundary

| | Kitty | KittyBuilder |
|---|---|---|
| **Role** | Principal product agent and intent compiler | Execution control plane |
| **Owns** | Conversation, user intent, memory, personal context, projects, documents, artifacts, provider interaction, tools, Tutor, Image Lab, automations, presentation of Builder results | Accepted Missions, initiatives, packets, queues, dependencies, workers, leases, attempts, retries, worktrees, branches, validation, reviews, PRs, budgets, evidence, durable execution state |
| **Interface to the other** | Submits versioned approved Missions | Returns structured results and evidence references |
| **State** | Application database (`data/kitty/kitty.db`), JSONL stores, vector stores, config | `data/kittybuilder/builder_queue.db` — SQLite, read only through supported CLI/API projections |
| **Workers** | Not applicable | Replaceable coding/review harness adapters; DSH is the current default Builder path, while alternate/legacy adapters may remain. Harnesses never own execution truth. |

The accepted boundary is ADR 0017. Builder owns execution state, not product intent. Never infer Builder state from handoff prose, worker output, or UI emptiness.

## System shape

```text
Native Kitty (`gateway/kitty-chat`, local port 4000) — canonical product surface
  → server-side /proxy → FastAPI Gateway (127.0.0.1:8000)
Replaceable clients/adapters
  → Gateway

Gateway
  → product domains/stores (projects, artifacts, Work, automations, Image Lab, tools, ...)
  → model-backed paths → context_assembler → memory_graph + context_enrichment
                       → llm_client → LiteLLM (127.0.0.1:8001) or direct provider adapter
  → approved Mission → KittyBuilder (durable execution state, workers, reviews, PRs)
```

The native frontend is a projection over Gateway-owned product truth. KittyBuilder is a separate execution control plane, not another application-state store.

## Annotated top-level directory tree

```
kitty/
├── kitty                   # Bash launcher/operator CLI (up, down, status, doctor,
│                           #   context, builder, governor, tutor, project, push, ...)
├── gateway/                # FastAPI product backend — the product boundary
│   ├── app.py              # FastAPI app setup, middleware, lifespan
│   ├── routes/             # Thin API handlers; delegate to domain modules
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
│   │   │   ├── components/ # Product UI components
│   │   │   ├── state/      # React state management (KittyContext)
│   │   │   ├── hooks/      # Custom React hooks
│   │   │   └── lib/        # TypeScript utilities, API clients, types
│   │   ├── tests/          # Vitest + Playwright tests
│   │   └── scripts/        # Visual diff, swarm review, dogfood tests
│   └── tests/              # Gateway-level Python tests
├── tests/                  # Python unit/integration/contract test suite
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
├── .github/workflows/      # Scope-aware CI, policy gates, nightly health, provider workflows
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
| `./kitty` or `./kitty start` | Supported full local start: Gateway + LiteLLM + native UI, then open the browser |
| `./kitty up` | Start Gateway (8000) + LiteLLM (8001) only |
| `./kitty ui` | Start the native UI through `scripts/desktop/start_ui.sh` |
| `./kitty down` | Stop only services proven to belong to this checkout; preserve sibling/external listeners |
| `./kitty status` | Show the current runtime/provenance projection; `KH-RUNTIME-01` tracks known false-current/false-not-running cases |
| `./kitty doctor --json` | Full supported preflight/diagnostic projection; corroborate runtime freshness until `KH-RUNTIME-01` lands |
| `./kitty context --agent` | Deterministic repository/continuity receipt; GAR-aware migration facade |
| `./kitty builder --help` | KittyBuilder CLI surface |
| `./kitty room --help` | Global Agent Room CLI surface |
| `./kitty governor explain <dispatch.json>` | Dry-run compute governor |
| `cd gateway/kitty-chat && npm run dev` | Isolated frontend development server only; not canonical product-runtime evidence |
| `cd gateway/kitty-chat && npm run build` | Frontend production-build validation |
| `./scripts/generate_repo_context.sh` | Generate AI-uploadable repo bundle |

`./kitty ui` currently has a known bind/proxy mismatch: the launcher forces an all-interface UI bind while `/proxy` remains loopback-only. Do not use that mismatch as a Tailnet-access recipe; [`KH-REMOTE-01`](../packets/KH-REMOTE-01.md) owns the authenticated remote-access repair.

## Data flows

1. **Chat/model flow:** Client → `gateway/routes/completions.py` → `context_assembler.py` → `memory_graph.py` → `llm_client.py` → LiteLLM or direct provider adapter
2. **Memory writes:** Domain module → store adapter → SQLite / JSONL / ChromaDB / mem0
3. **Request-context retrieval:** Model/context assembly → `memory_graph.py` (unified adapter fan-in); ordinary domain reads stay with their owning store/module
4. **Builder execution:** Kitty → approved Mission → `builder_queue.py` → worker adapter → coding harness → review → validation → PR → `builder_publish.py`
5. **Context receipt:** `./kitty context --agent` → `context_receipt.py` compatibility facade → repository/Git/Builder evidence, with `workspace_global` as primary interactive continuity when its availability is established

## Authoritative state ownership

| State | Owner | Access |
|---|---|---|
| Product purpose | `docs/NORTH_STAR.md` | Direct read |
| Architecture | `docs/ARCHITECTURE.md` + accepted ADRs | Direct read |
| Delivery sequence | `docs/ROADMAP.md` | Direct read |
| Active mission | `docs/ACTIVE_MISSION.md` | Direct read |
| Shipped capabilities | `docs/PROJECT_STATUS.md` | Direct read |
| Application data | Established Gateway stores (SQLite, JSONL, vector/reference stores, filesystem artifacts) | Gateway APIs/modules; do not bypass store ownership |
| Builder execution | `data/kittybuilder/builder_queue.db` | Supported `./kitty builder ...` / Gateway projections only |
| Live git/branch | Git + worktree | `git status`, `git log` |
| Interactive continuity | `workspace_global` via Global Agent Room | `./kitty room ...`; `.claude/STATE.md` + `.claude/HANDOFF.md` are validated legacy fallback only |
| Engineering doctrine | `AGENTS.md` | Direct read |
| Agent tool config | `CLAUDE.md`, `CODEX.md` | Direct read |

Runtime files under `data/` and `logs/` are local, never committed. Builder state must be read through supported Python/CLI projections, never by joining SQLite tables from prose.

## Testing layers

| Layer | Location | Command |
|---|---|---|
| Python unit/integration | `tests/` | `python3.12 -m pytest tests/ -q --tb=short` |
| Frontend unit (Vitest) | `gateway/kitty-chat/tests/` | `cd gateway/kitty-chat && npm test` |
| Frontend E2E (Playwright) | `gateway/kitty-chat/tests/` | `cd gateway/kitty-chat && npx playwright test` |
| Hermetic frontend E2E | `gateway/kitty-chat/tests/` | `cd gateway/kitty-chat && npm run test:smoke:hermetic` |
| Visual diff | `gateway/kitty-chat/scripts/` | `make visual-diff` |
| Swarm review | `gateway/kitty-chat/scripts/` | `make swarm-review` |

Volatile file/test counts are intentionally omitted. Derive them from the current tree when a count matters; historical counts in prose become stale too quickly to be useful navigation.

## CI workflow overview

`.github/workflows/tests.yml` is scope-aware on pull requests and pushes to `main`. The stable required aggregate is `merge-gate`; individual jobs run only when the changed-path classifier says their evidence applies. A docs-only change may legitimately skip Python/frontend/browser jobs.

| Job | Role |
|---|---|
| `changes` | Canonical changed-path classification |
| `pytest` / `pytest-integration` | Python deterministic evidence when applicable |
| `lint` | Ruff scope gate |
| `typecheck` | mypy evidence when applicable |
| `kitty-chat` | Frontend unit/build evidence when frontend scope applies |
| `browser-smoke` | Browser evidence for applicable frontend changes |
| `merge-gate` | Stable aggregate required result |

`pr-agent-review.yml` supplies `policy-gate` and trusted review policy; `pr-auto-label.yml` labels path scope; `nightly-health.yml` owns broad scheduled hygiene/full-suite evidence. Read live GitHub checks for an exact SHA instead of assuming every job ran because the aggregate is green.

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
| Documentation audit | Doc health and disposition (archived 2026-07-30 snapshot) | `docs/archive/audits-2026-07/DOCUMENTATION_AUDIT.md` |
| Context engineering | Staged context-loading workflow | `docs/reference/CONTEXT_ENGINEERING.md` |

## AI context bundle

Run from repo root:

```bash
./scripts/generate_repo_context.sh
```

Produces uploadable files under `artifacts/repo-context/` using `repomix.config.json`. Generated bundles exclude secrets, runtime state, dependencies, caches, and large binary files. Review before uploading.
