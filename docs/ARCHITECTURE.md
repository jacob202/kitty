# Kitty Architecture

**Verified:** 2026-08-04 against repository evidence through `main` `c266b13c0c694929c728a3f3861187f56229dbac`.

## System boundary

```text
Jacob
  ↕
Open WebUI / other replaceable clients
  ↕
Kitty Gateway — product authority
  ├─ context assembly and memory reads
  ├─ projects, documents, Tutor, tools, automations, and image contracts
  ├─ model/provider policy through LiteLLM and direct provider adapters
  └─ approved Mission → KittyBuilder → structured Result/Evidence
```

### Kitty

Kitty is the principal product agent and system. It owns:

- conversation behavior and continuity;
- personal context and memory retrieval;
- projects, documents, artifacts, Tutor, tools, and automations;
- model/provider policy and truthful error presentation;
- turning approved intent into a versioned Mission;
- presenting Builder results, evidence, blockers, and approval requests.

Kitty must remain useful when KittyBuilder is unavailable.

### KittyBuilder

KittyBuilder is the execution organization and engineering control plane. It owns:

- accepted Missions and initiatives;
- packets, queues, workers, leases, attempts, retries, and recovery;
- worktrees, branches, validation, reviews, PR publication, budgets, and evidence;
- durable execution truth through its supported database, API, and CLI.

Models, coding harnesses, GitHub comments, handoff prose, and UIs are adapters or projections—not execution authorities.

### Clients

ADR 0027 authorizes pinned stock Open WebUI as the current replaceable local daily-driver shell. Canonical Kitty state and business logic remain outside it.

The custom Next.js client under `gateway/kitty-chat/` remains a retained fallback and development surface. Its supported commands bind to `127.0.0.1`; unauthenticated LAN/tailnet exposure is not supported.

## Runtime processes

| Process | Default address | Responsibility |
|---|---|---|
| Gateway | `127.0.0.1:8000` | Product APIs, chat boundary, memory, projects, tools, capture, Tutor, Builder projections |
| LiteLLM | `127.0.0.1:8001` | Model proxy, routing, and fallback |
| Open WebUI | `127.0.0.1:3000` | Replaceable daily-driver shell |
| `kitty-chat` | `127.0.0.1:4000` | Retained alternate client and development surface |

`./kitty` is the preferred service entrypoint. `scripts/openwebui_local.py` owns supported Open WebUI bootstrap, verification, backup, restore, and rollback operations.

## Request flow

```text
client request
  → Gateway route
  → domain module
  → context_assembler
  → memory_graph + bounded enrichment
  → llm_client / LiteLLM / provider adapter
  → streamed result with provider/model/error attribution
```

Routes should remain thin. Product logic belongs in domain modules and established boundaries, not in clients or route handlers.

## State ownership

| State | Authority |
|---|---|
| Product data | Kitty application stores behind established storage modules |
| Context reads | `memory_graph` |
| Builder execution | Builder database/API/CLI |
| Architectural decisions | Accepted ADRs |
| Delivery order | `docs/ROADMAP.md` |
| Current approved work | `docs/ACTIVE_MISSION.md` |
| Repository evidence | Git, GitHub, CI, and supported probes |
| Session continuation | `.claude/STATE.md` and `.claude/HANDOFF.md` only while identity metadata remains valid |

Storage is intentionally mixed: SQLite for canonical structured state, JSONL for append-oriented records, JSON for configuration/small state, ChromaDB and mem0 for semantic/reference memory, and filesystem artifacts for logs and evidence. New storage systems require an ADR.

## Non-negotiable invariants

- The Gateway remains the product authority.
- Clients remain replaceable and do not own canonical Kitty business logic.
- Builder state is never duplicated into a second queue or state machine.
- Missing, stale, unavailable, or unverified evidence is reported explicitly.
- Explicit provider selection fails loudly when unavailable; no silent paid fallback.
- Access, retrieval, monitoring, memory, and action permissions remain separate.
- Secrets are never committed, logged, or exposed to unauthenticated clients.
- Custom local clients bind to loopback unless a separately reviewed authentication boundary exists.
- User-facing capability is not called shipped until its real workflow is proven end to end.

## Current proof gaps

Repository CI is green for Python tests, lint, typing, hygiene, Kitty Chat tests/build, and browser smoke. It does not prove:

- Jacob's current local process, launchd, credential, quota, or provider state;
- a clean-start Open WebUI chat/persistence/restart workflow on Jacob's Mac;
- the full real-phone insight return loop in #270;
- paid image quality or likeness outcomes;
- current local Builder queue state.

Those remain runtime verification tasks, not architecture claims.
