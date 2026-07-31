# Kitty

Kitty is Jacob's local-first personal AI companion. It keeps its own context, memory, projects, permissions, tools, and delivery machinery while routing work across interchangeable local and cloud models.

KittyBuilder is Kitty's controlled execution engine — a separate control plane that organizes coding work through durable queues, workers, reviews, and PRs.

> **Start here:** [`START_HERE.md`](START_HERE.md) — cold-start bootloader for agents and humans.
>
> **Repository navigation:** [`docs/reference/CODEBASE_MAP.md`](docs/reference/CODEBASE_MAP.md) — authoritative codebase map with boundaries, directory tree, entry points, data flows, and state ownership.
>
> **Context engineering:** [`docs/reference/CONTEXT_ENGINEERING.md`](docs/reference/CONTEXT_ENGINEERING.md) — staged context-loading workflow for faster, safer cold starts.
>
> **Current state:** [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — verified shipped capabilities.
>
> **Active work:** [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) — the one approved current mission.

## Kitty and KittyBuilder

| | Kitty | KittyBuilder |
|---|---|---|
| **Role** | Principal product agent and intent compiler | Execution control plane |
| **Owns** | Conversation, user intent, memory, personal context, projects, documents, artifacts, provider interaction, tools, Tutor, Image Studio, automations, presentation of Builder results | Accepted Missions, initiatives, packets, queues, workers, leases, attempts, retries, worktrees, branches, validation, reviews, PRs, budgets, evidence |
| **State** | Application database, JSONL stores, vector stores, config | `data/kittybuilder/builder_queue.db` — read only through supported CLI/API |
| **Workers** | Not applicable | Replaceable coding harnesses (OpenCode, Claude Code, Codex, Oh My Pi) — adapters, never authorities |

The accepted boundary is ADR 0017. Builder owns execution state, not product intent.

## Architecture

```text
Browser / Raycast / Telegram / Siri / iMessage
  → FastAPI Gateway (port 8000)
    → context_assembler → memory_graph + context_enrichment
    → llm_client → LiteLLM (port 8001) → provider chain
    → KittyBuilder (durable queue, workers, reviews, PRs)
    → tools, MCP, image generation, storage
  → Next.js kitty-chat (port 4000)
```

The gateway is the product. Clients are thin views over its API. Product logic belongs in the gateway, not in clients.

## Runtime processes

| Process | Default address | Responsibility |
|---|---|---|
| Gateway | `127.0.0.1:8000` | API, chat, memory, tools, capture, Builder surfaces |
| LiteLLM | `127.0.0.1:8001` | Model proxy, routing, and fallback |
| kitty-chat | `127.0.0.1:4000` | Next.js interface |

## Quick start

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env

./kitty up
./kitty status
./kitty doctor --json

cd gateway/kitty-chat
npm install
npm run dev
```

`./kitty down` stops the stack. `./kitty install` registers launchd services. Ports can be overridden with `GATEWAY_PORT` and `LITELLM_PORT`.

## Everyday verification

```bash
git status --short --branch
./kitty context --agent
./kitty status
./kitty doctor --json
python3.12 -m pytest tests/ -q --tb=short
cd gateway/kitty-chat && npm test && npm run build
```

## Storage

Kitty uses multiple stores behind explicit boundaries:

- SQLite for application and Builder state;
- JSONL for append-oriented records and traces;
- ChromaDB and mem0 for semantic/reference memory;
- JSON for configuration and small state files;
- filesystem artifacts for logs, evidence, and generated outputs.

`memory_graph` is the unified read path for product memory. Runtime state under `data/` is local evidence, never committed, never prose documentation.

## Repository navigation

| Looking for | Go to |
|---|---|
| Codebase map, entry points, data flows | [`docs/reference/CODEBASE_MAP.md`](docs/reference/CODEBASE_MAP.md) |
| Documentation health and stale docs | [`docs/reference/DOCUMENTATION_AUDIT.md`](docs/reference/DOCUMENTATION_AUDIT.md) |
| Where each kind of truth lives | [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) |
| Agent engineering rules | [`AGENTS.md`](AGENTS.md) |
| Current architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Delivery roadmap | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Shipped capabilities | [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) |
| Active mission | [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) |
| Decisions and ADRs | [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Product purpose | [`docs/NORTH_STAR.md`](docs/NORTH_STAR.md) |
| KittyBuilder operator guide | [`docs/KITTYBUILDER_QUICKSTART.md`](docs/KITTYBUILDER_QUICKSTART.md) |
| Documentation index | [`docs/README.md`](docs/README.md) |
| Cold-start bootloader | [`START_HERE.md`](START_HERE.md) |

## Working with agents

Agents must read these in order:

1. [`START_HERE.md`](START_HERE.md) — boot sequence
2. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md) — truth ownership
3. [`AGENTS.md`](AGENTS.md) — engineering doctrine
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system boundaries
5. [`docs/ROADMAP.md`](docs/ROADMAP.md) — delivery sequence
6. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — shipped state
7. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md) — approved work

`CLAUDE.md` and `CODEX.md` add tool-specific instructions. `.claude/STATE.md` and `.claude/HANDOFF.md` are continuation aids only while their recorded Git identity remains valid.

## Documentation rules

- `docs/ROADMAP.md` is the only active delivery sequence.
- `docs/PROJECT_STATUS.md` summarizes verified shipped state at a stated commit.
- `docs/ACTIVE_MISSION.md` contains the one approved current mission.
- `docs/plans/` contains inputs and candidate work, not automatic authority.
- `docs/archive/` contains superseded material and must not be treated as current instructions.
- Git, GitHub, supported runtime probes, and accepted ADRs override stale prose.

## Warnings

- **Generated state:** `data/`, `logs/`, `gateway/kitty-chat/.next/` are generated at runtime. Do not edit or commit them. Do not treat them as documentation.
- **Builder authority:** Builder execution truth lives in `data/kittybuilder/builder_queue.db`. Never infer Builder state from handoff prose, worker output, or UI emptiness. Never join Builder SQLite tables into another state machine.
- **Secrets:** Never commit `.env` or any file with real API keys. Read `.env.example` instead.
- **Model routing:** Unconfigured providers are skipped; an explicitly selected unavailable provider fails loudly.

## AI context bundle

```bash
./scripts/generate_repo_context.sh
```

Produces an AI-uploadable Repomix bundle in `artifacts/repo-context/` using `repomix.config.json`. Generated bundles exclude secrets, runtime state, and build artifacts. Review before uploading.
