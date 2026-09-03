# Kitty Architecture

**Verified:** 2026-09-03 against repository evidence through `main` `8b4550e20f4fa24bb047adb61d18793b859c2707`. Runtime-specific facts still require live probes.

## System boundary

```text
Jacob
  ↕
Native Kitty frontend — canonical product surface
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

ADR 0039 makes the native Next.js client under `gateway/kitty-chat/` the canonical user-facing Kitty product surface. It remains a thin projection over Gateway-owned truth. Its intended security boundary is loopback unless a separately reviewed authenticated remote edge is in place.

Open WebUI remains optional compatibility/reference software under the safety boundaries established by ADR 0027/0033. It does not own Kitty product state, product navigation, or product direction.

## Runtime processes

| Process | Default address | Responsibility |
|---|---|---|
| Gateway | `127.0.0.1:8000` | Product APIs, chat boundary, memory, projects, tools, capture, Tutor, Builder projections |
| LiteLLM | `127.0.0.1:8001` | Model proxy, routing, and fallback |
| `kitty-chat` | local port `4000` | Canonical native Kitty product surface; intended loopback boundary, with the current launcher inconsistency noted below |
| Open WebUI | `127.0.0.1:3000` | Optional compatibility/reference client |

`./kitty` is the supported native Kitty service/product entrypoint. `./kitty up` starts Gateway + LiteLLM; the default `./kitty` / `./kitty start` adds the native UI through the canonical UI bootstrap. `scripts/openwebui_local.py` remains the bounded operator path for optional Open WebUI compatibility, verification, backup, restore, and rollback operations.

**Known runtime-boundary defect:** `./kitty ui` currently forces `KITTY_UI_BIND_ALL=true`, so the Next server may listen on all interfaces even though its server-side `/proxy` rejects non-loopback Hosts and the Gateway/LiteLLM remain loopback-only. That is not supported remote access. [`KH-REMOTE-01`](packets/KH-REMOTE-01.md) owns the authenticated Tailnet repair; documentation must not weaken the proxy boundary to make the current mismatch look intentional.

## Request flows

Ordinary product APIs stay inside their owning Gateway domain and do not require an LLM:

```text
native client
  → Gateway route
  → owning domain/store module
  → authoritative state/result
```

Conversation and other model-backed operations add the context/model path:

```text
model-backed request
  → Gateway route/domain module
  → context_assembler
  → memory_graph + bounded enrichment
  → llm_client
  → LiteLLM or an explicitly selected/direct provider adapter
  → attributed result or explicit provider-chain failure
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
| Interactive/session continuity | `workspace_global` via the Global Agent Room; `.claude/STATE.md` and `.claude/HANDOFF.md` are validated legacy fallback only |

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

## Verification boundary

This document owns durable component and state-ownership boundaries, not a live health dashboard. Current process state, launchd installation, credentials, quotas, provider availability, exact Builder queue contents, paid image outcomes, and release acceptance must be read from supported runtime probes, Git/GitHub evidence, and [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

Runtime probes themselves can have known defects. `KH-RUNTIME-01` currently tracks false-current UI build classification and macOS Gateway freshness detection; until repaired, corroborate `status`/`doctor` provenance claims instead of elevating them to architecture truth.

Repository CI is scope-aware: an exact `main` run can legitimately skip frontend/browser jobs when the merged change did not touch that scope. Do not convert a green aggregate gate into proof that every subsystem was re-exercised on that SHA.
