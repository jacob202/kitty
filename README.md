# Kitty 🐾

Kitty is Jacob's provider-independent personal AI operating layer. It keeps its own context, memory, projects, permissions, tools, and delivery machinery while routing work across interchangeable local and cloud models.

> **Current state:** substantial working backend and delivery infrastructure; daily-use reliability and product coherence are still being hardened. Kitty is a personal project, not yet packaged for public use.
>
> **Start here:** [`START_HERE.md`](START_HERE.md) is the cold-start entrypoint. For the verified product surface, read [`docs/FEATURE_REALITY_2026-07-28.md`](docs/FEATURE_REALITY_2026-07-28.md). For current repository truth, use [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

## What Kitty is becoming

Kitty is designed around a practical problem: capability is not useful when continuity fails. The system is meant to preserve context, reduce the cost of beginning, make unfinished work resumable, automate repetitive verification, and keep AI assistance grounded in evidence rather than confident narrative.

The gateway is the product. Clients are thin views over its API.

```text
Browser / Raycast / Telegram / Siri / iMessage
  → FastAPI gateway
  → context + memory graph + live enrichment
  → model routing and provider fallback
  → tools, storage, and durable Builder execution
```

## Runtime

| Process | Default address | Responsibility |
|---|---|---|
| Gateway | `127.0.0.1:8000` | API, chat, memory, tools, capture, Builder surfaces |
| LiteLLM | `127.0.0.1:8001` | model proxy, routing, and fallback |
| kitty-chat | `127.0.0.1:4000` | Next.js interface |

New context reads should go through `gateway/memory_graph.py`. Product logic belongs in the gateway, not in clients. Failures must be surfaced truthfully rather than hidden by silent fallback.

## Repository map

```text
kitty
├── kitty/ or ./kitty       # launcher and operator CLI
├── gateway/                # FastAPI product backend and durable execution
│   └── kitty-chat/         # Next.js interface
├── soul/ and config/       # identity, persona, and behavior
├── contracts/              # schemas and boundaries between layers
├── mcp/                    # MCP integrations, including image generation
├── docs/                   # canonical docs, plans, evidence, and archive
├── scripts/                # operator, validation, and maintenance tooling
├── tests/                  # Python and product acceptance coverage
├── data/ and logs/         # local runtime state; not documentation authority
├── AGENTS.md               # shared agent operating contract
└── START_HERE.md           # canonical cold-start route
```

A more detailed, upload-friendly map lives in [`docs/CODEBASE_MAP.md`](docs/CODEBASE_MAP.md). The docs index is [`docs/README.md`](docs/README.md).

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

Kitty deliberately uses multiple stores behind explicit boundaries:

- SQLite for application and Builder state;
- JSONL for append-oriented records and traces;
- ChromaDB and mem0 for semantic/reference memory;
- JSON for small configuration and state;
- filesystem artifacts for logs, evidence, and generated outputs.

`memory_graph` is the unified read path for product memory. Runtime state under `data/` is local evidence, not prose documentation.

## Model routing

Kitty supports LiteLLM plus configured direct providers. Normal chat can use automatic routing/fallback or an explicitly selected provider. Unconfigured providers are skipped; an explicitly selected unavailable provider should fail loudly rather than silently spend elsewhere.

## Working with agents

Read these first:

1. [`START_HERE.md`](START_HERE.md)
2. [`docs/AUTHORITY_MAP.md`](docs/AUTHORITY_MAP.md)
3. [`AGENTS.md`](AGENTS.md)
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
5. [`docs/ROADMAP.md`](docs/ROADMAP.md)
6. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)
7. [`docs/ACTIVE_MISSION.md`](docs/ACTIVE_MISSION.md)

`CLAUDE.md` and `CODEX.md` add tool-specific instructions. `.claude/STATE.md` and `.claude/HANDOFF.md` are continuation aids only while their recorded Git identity remains valid.

## Documentation rules

- `docs/ROADMAP.md` is the only active delivery sequence.
- `docs/PROJECT_STATUS.md` summarizes verified shipped state at a stated commit.
- `docs/ACTIVE_MISSION.md` contains the one approved current mission.
- `docs/plans/` contains inputs and candidate work, not automatic authority.
- `docs/archive/` contains superseded material and must not be treated as current instructions.
- Git, GitHub, supported runtime probes, and accepted ADRs override stale prose.

## Repository context bundle

Run:

```bash
./scripts/generate_repo_context.sh
```

This produces an AI-uploadable Repomix bundle in `artifacts/repo-context/` using the checked-in `repomix.config.json`. Generated bundles are intentionally not committed.
