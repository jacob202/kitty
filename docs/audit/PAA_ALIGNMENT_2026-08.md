# Kitty ↔ Personal AI Architecture Alignment Audit

**Date:** 2026-08-03  
**Status:** Repository-evidence baseline; not a conformance claim  
**Kitty baseline:** `287c1947adf9af62ef4f6b3b2754b826b02b939a`  
**PAA baseline:** `Personal-AI-Architecture/the-architecture@c4eb0d475d1200448098729c801964bc8ccce7ec`  
**Source contract:** `docs/in-depth-overview/implementers-reference.md` and its conformance/lock-in documents  
**Tracking:** issue #389

## Scope and terminology

This audit compares Kitty with the **Personal AI Architecture (PAA)** maintained
by `Personal-AI-Architecture/the-architecture`. It is unrelated to Daniel
Miessler's **Personal AI Infrastructure (PAI)**, which was previously evaluated
in `docs/retired/PAI_GAP_ANALYSIS.md`.

This is a repository audit. It does not prove local process health, provider
availability, current credentials, offline operation, data completeness, or
fresh-install recovery. Runtime-only claims remain `UNKNOWN` until exercised.

Statuses:

- **PASS** — repository evidence directly satisfies the requirement.
- **PARTIAL** — the required capability exists in part, but its boundary or
  proof is incomplete.
- **FAIL** — repository evidence contradicts or lacks a required capability.
- **DELIBERATE DEVIATION** — Kitty intentionally makes a different product
  choice; it must be documented rather than called conformant.
- **UNKNOWN** — the claim requires runtime or deeper code evidence not gathered
  in this bounded audit.

## Executive conclusion

Kitty has independently converged on much of PAA's purpose:

- local, owner-controlled deployment;
- durable personal memory behind a unified read boundary;
- multiple replaceable model providers;
- thin external clients over a Gateway API;
- tool and worker adapters;
- explicit local-only defaults;
- export/import and backup/restore work already underway.

Kitty is **not strictly PAA-conformant**, and no document should claim that it
is. The largest deliberate difference is responsibility placement. PAA defines
a content-agnostic Gateway and generic Agent Loop; Kitty's accepted ADR 0003
makes the Gateway the product and places prompt/context assembly, domain logic,
and model routing behind it. Kitty also lacks PAA's complete owner-memory
manifest, independent auth component/tool surface, previous-state history,
versioned cross-component schemas, and executable swap/offline conformance
suite.

The recommended target is a **Kitty PAA profile**:

1. adopt PAA's owner-memory portability, inspectability, contract, adapter,
   swap, offline, localhost, error-safety, and lock-in guarantees;
2. define Kitty's Principal/Application layer explicitly so product behavior is
   not mistaken for a generic Gateway or Agent Loop;
3. preserve KittyBuilder as a Kitty extension outside PAA's four-component
   foundation;
4. record every deliberate deviation and test every adopted guarantee.

## Architecture mapping

| PAA element | Kitty evidence | Status | Finding |
| --- | --- | --- | --- |
| Your Memory | `gateway/memory_graph.py`, `gateway/storage_router.py`, `gateway/storage_sync.py`, SQLite/JSONL/ChromaDB/mem0/files | PARTIAL | Unified reads exist, but there is no complete machine-readable owner-data manifest or proven full export/import. |
| Agent Loop | `gateway/agent_runner.py`, `gateway/llm_client.py`, tool/MCP surfaces | PARTIAL / DELIBERATE DEVIATION | Execution loops exist, but product behavior, context assembly, routing, and policy are not isolated behind a generic loop contract. |
| Auth | typed auth errors, bounded tool surfaces, local permissions and approval policy | FAIL | No verified independent actor/resource/action component or required `auth_whoami`, `auth_check`, `auth_export` surface. |
| Gateway | FastAPI Gateway; kitty-chat, Raycast, Telegram, Siri, iMessage and OpenAI-compatible clients | PASS for client boundary; DELIBERATE DEVIATION for responsibility | Clients are thin, but Gateway intentionally owns product behavior that PAA forbids in a strict Gateway. |
| Gateway API | FastAPI routes and OpenAI-compatible routes | PARTIAL | Real API boundary exists; canonical versioned schema and client-swap equivalence proof are incomplete. |
| Model API | `gateway/llm_client.py`, LiteLLM, provider/model configuration and fallbacks | PARTIAL | Multiple providers are supported, but config-only swap must be proven through an executable test. |
| Tools | Kitty tools, MCP, plugins, connectors, Builder worker adapters | PARTIAL | Rich capability exists; common self-describing contract, add/remove swap proof, and independent authorization are incomplete. |
| Clients | kitty-chat and external channels; PR #384 adds Open WebUI as a replaceable shell | PASS in design; runtime proof pending | Accepted design keeps clients replaceable. Actual Open WebUI removal/client-equivalence proof is pending. |
| Models | local and cloud routes through LiteLLM/provider adapters | PASS in design; runtime proof pending | No single model is architectural authority. Live route/fallback facts require runtime evidence. |
| External services | connectors, MCP, browser/image/provider integrations | PARTIAL | Explicit modules exist; no-silent-outbound inventory and offline profile are incomplete. |

## Requirement matrix

### Your Memory

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Memory has zero outward component dependencies | PARTIAL | Canonical owner data is stored locally, but the logical memory platform is spread across app stores and provider-specific libraries. The exact canonical/derived boundary is not declared. |
| Every component accesses memory through tools | FAIL | `memory_graph` adapters and domain modules import store modules directly. Kitty has an internal adapter seam, not PAA's tool-only memory contract. |
| Inspectable with standard tools while stopped | PARTIAL | SQLite, JSONL, JSON, Markdown, and filesystem artifacts are inspectable. ChromaDB/mem0 data and cross-store meaning are not yet proven owner-readable without Kitty. |
| Full export in open formats | PARTIAL | `gateway/storage_sync.py` exports selected migrated stores only. PR #388 adds archive/restore mechanics, but neither is yet a complete owner-memory export. |
| Reliable version history established at startup | FAIL | No repository evidence shows startup failing when owner-memory history cannot be established. Git history of source is not owner-memory history. |
| History returns change records and previous states | FAIL | No unified owner-memory history contract returning previous content states was found. |
| Core read/write/edit/delete/search/list/history operations | PARTIAL | Reads, writes, deletes, lists, and searches exist across stores; one stable complete operation surface and history contract do not. |
| Skills live in Your Memory | PARTIAL / DEVIATION | Skills and prompts live mainly in the repository/configuration. Some are owner-specific, but portability with owner memory is not established. |

### Agent Loop and Principal/Application behavior

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Generic loop connects models to tools | PARTIAL | Kitty has agent/tool loops, but there is no isolated replaceable loop contract proven across implementations. |
| Agent Loop does not construct prompts or select context | DELIBERATE DEVIATION | Kitty explicitly owns product behavior in `context_assembler` and Gateway domain modules. ADR 0028 defines a Principal/Application layer rather than pretending this is generic-loop behavior. |
| Agent Loop has no personality, approval state, or product scope | PARTIAL / DEVIATION | Kitty's personality and preferences are mostly configuration/memory, but approval, context, routing, and product behavior are not cleanly isolated from the runtime package. |
| Multiple concurrent loops are independent | UNKNOWN | Requires a focused runtime/concurrency test. |
| No default iteration cap imposed by architecture | UNKNOWN | Requires code-path and runtime review across all loops. Deployment-specific safety budgets are allowed, but must not be confused with an architectural hard cap. |
| Text emitted alongside tool calls is preserved on continuation | UNKNOWN | Requires streaming/tool-continuation test evidence. |

### Auth

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Independent Authenticate / Authorize / Manage component | FAIL | Kitty has local safety/permission concepts but no verified independent auth boundary. |
| Actor/resource/action policy | FAIL | No canonical cross-client policy contract was found. |
| Owner, collaborator, system/background/external actors | FAIL | Worker identity exists in Builder, but it is not the product auth model. |
| `auth_whoami`, `auth_check`, `auth_export` | FAIL | Required tool surface not found. |
| Auth independent from Gateway and provider | FAIL | Current controls are distributed across routes, tools, local configuration, and Builder policy. |

Auth implementation is security-sensitive and requires a dedicated threat review
and Jacob's explicit approval. This audit authorizes design and testing work,
not a rushed auth retrofit.

### Gateway and conversations

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Clients connect through one product-owned Gateway API | PASS | Canonical architecture makes clients thin views over FastAPI Gateway APIs. |
| Create/list/resume/history conversations | PARTIAL | Chat persistence and resume surfaces exist; one versioned cross-client conversation contract and fresh-client equivalence test remain to be proven. |
| Conversations stored in Your Memory | PARTIAL | Chats are local application data, but their inclusion in a complete owner-memory export/import is not proven. |
| Gateway is content-agnostic | DELIBERATE DEVIATION | ADR 0003 says "Gateway Is The Product." Kitty interprets context and routes behavior behind the Gateway. |
| Gateway does not inject context or influence model behavior | DELIBERATE DEVIATION | `context_assembler`, `domain_router`, preferences, memory enrichment, and model policy are core Kitty product behavior. |
| Client swap leaves system behavior equivalent | PARTIAL | Multiple clients exist and PR #384 preserves a replaceable-shell boundary. An executable equivalence/removal test is pending. |

### Contracts and adapters

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Versioned Gateway API schema | PARTIAL | FastAPI/Pydantic shapes exist, and `contracts/` exists, but no single pinned canonical client contract was verified. |
| Versioned Gateway/Application → Agent Loop contract | FAIL | Current function/module boundaries are implementation-specific. |
| Stable streamed event schema | PARTIAL | Streaming routes exist; fixed event taxonomy and schema-conformance proof are incomplete. |
| Model provider behavior isolated behind adapters | PARTIAL | `llm_client`/LiteLLM centralize provider behavior, but config-only swap must be tested and provider leakage audited. |
| Tool definitions/results share stable contract | PARTIAL | Multiple tool systems exist; no one complete schema was verified. |
| Adapters are thin/stateless | PARTIAL | Several adapters are thin, but this has not been audited across providers, clients, memory stores, tools, and workers. |

### Errors and safety

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Typed error taxonomy | PARTIAL | `gateway/errors.py` defines typed codes and HTTP status classes. Coverage across streaming/provider/tool paths is incomplete. |
| Safe client-facing streamed errors | PARTIAL | Typed errors exist; PR #384 adds further chat-error hardening. A test must prove no path, stack trace, credential, or raw provider detail leaks into SSE/compatible streams. |
| Pre-stream invalid/auth/unavailable statuses | PARTIAL | FastAPI errors exist; canonical contract and test matrix are incomplete. |
| Tool/action permission separated from model judgment | PARTIAL | Kitty has approval and bounded-tool doctrine, but independent Auth enforcement is missing. |

### Configuration and deployment

| PAA requirement | Status | Kitty evidence and gap |
| --- | --- | --- |
| Owner-controlled local deployment | PASS | Kitty runs locally through `./kitty`; owner state lives under local data paths. |
| Default `127.0.0.1` binding | PASS in documented design; runtime proof pending | Architecture and launcher defaults are loopback. Gate 0 still tracks launcher/listener correctness. |
| Offline operation with local model/tools | UNKNOWN | Architecture supports local providers, but a disconnected end-to-end proof was not found. |
| No silent outbound traffic | PARTIAL | Network-dependent modules are explicit, but no executable egress inventory/test was found. |
| Secrets outside source and owner memory | PASS in doctrine; runtime audit pending | `.env`/secret rules are explicit. Complete export must prove secrets are excluded by construction. |
| Update/restore safety | PARTIAL | Backup/restore work is active in PR #388. Fresh-install semantic parity remains pending. |

## PAA conformance-test disposition

| Test | Initial status | Required Kitty proof |
| --- | --- | --- |
| SWAP-1 Provider swap | PARTIAL | Change adapter/config only; next turn uses new provider; no core edits. |
| SWAP-2 Model swap | PARTIAL | Change preference/config only; next turn uses new model. |
| SWAP-3 Tool swap | PARTIAL | Add/remove one tool through registry/config; no core edits; system remains healthy. |
| ARCH-1 Memory zero dependencies | FAIL / PROFILE DEVIATION | Define Kitty owner-memory substrate and prove stopped-system inspectability; document direct-adapter deviation. |
| ARCH-2 Agent Loop swap | FAIL | Introduce/test a stable Principal/Application → loop boundary before claiming this. |
| ARCH-3 Client swap | PARTIAL | Run the same conversation behavior through two clients; remove Open WebUI without losing Kitty capability. |
| ARCH-4 Schema conformance | FAIL | Publish and validate canonical boundary schemas. |
| ARCH-5 Error taxonomy | PARTIAL | Exercise provider/tool/context failures against fixed codes. |
| ARCH-6 Error sanitization | PARTIAL | Fuzz/assert no secrets, paths, traces, or raw provider errors in client streams. |
| ARCH-7 Memory export | PARTIAL | Complete manifest + open export + fresh-install semantic parity. |
| ARCH-8 Auth tools | FAIL | Implement after threat review. |
| ARCH-9 History reliability | FAIL | Establish required owner-memory history and previous-state retrieval. |
| DEPLOY-1 Offline | UNKNOWN | Disconnect network and run local memory/tool/model loop. |
| DEPLOY-2 Local data | PARTIAL | Owner-data manifest proves canonical data location and explicit external dependencies. |
| DEPLOY-3/5 Localhost default | PASS in design | Fresh-install listener proof on IPv4 and IPv6. |
| DEPLOY-4 No silent outbound | UNKNOWN | Egress test/inventory under offline mode. |
| FS-1 Move Your Memory | PARTIAL | Export → fresh checkout → import; preserve chats, projects, preferences, retrieval, and next move. |
| FS-2 Add capability | PARTIAL | Add a strategy/tool/client/provider without changing owner-memory implementation. |
| FS-3 Run on own hardware | PASS in design | Fresh install and offline proof. |
| FS-4/5 Provider/client swap | PARTIAL | Same as SWAP-1 / ARCH-3. |
| FS-6 Evolve Memory | PARTIAL | Add or replace one search adapter without changing clients/providers/Builder. |
| FS-7 Swap Agent Loop | FAIL | Requires explicit loop contract. |
| FS-8 Expand scope via tools | PARTIAL | Add tool with configuration/registry and unchanged architecture. |

## BrainDrive disposition

BrainDrive is a useful PAA reference implementation and UX/operations harvest
source. It is **not** a replacement base for Kitty.

| Candidate | Disposition | Reason |
| --- | --- | --- |
| Interview → structured spec → action plan → ongoing partnership | ADAPT | Directly supports Kitty's life-first resume loop and project onboarding. |
| Life-area/project surfaces | ADAPT | Useful UX vocabulary; Kitty's project model and life-first ordering remain authoritative. |
| Memory backup configuration and restore UX | ADAPT | Complements PR #388 and PAA FS-1; avoid creating a second backup system. |
| One-command install/update/backup/restore/support bundle | ADAPT | Strong operator experience; must delegate to Kitty's canonical launcher/contracts. |
| Plain-file/Git-only memory substrate | EVALUATE | Valuable portability model, but Kitty has structured state and derived indexes that should not be forced into one storage mechanism. |
| BrainDrive codebase as Kitty replacement | REJECT | Would discard KittyBuilder, existing integrations, life-first behavior, Image Agent work, and verified reliability machinery. |
| BrainDrive/PAA claims as proof Kitty conforms | REJECT | Conformance must be demonstrated against Kitty's implementation and explicit profile. |

## Ordered remediation

The authoritative work breakdown is issue #389.

1. **PAA-0 — Profile and evidence baseline:** accept ADR 0028; keep this matrix
   current; never claim strict conformance.
2. **PAA-1 — Owner-data manifest and complete export:** build on PR #388 and
   `storage_sync`; classify canonical, derived, secret, cache, and execution
   evidence stores.
3. **PAA-2 — Inspectability and history:** prove stopped-system readability and
   previous-state retrieval for canonical owner memory.
4. **PAA-3 — Versioned contracts:** publish client, application/loop, stream,
   provider, tool, and export schemas.
5. **PAA-4 — Executable profile tests:** swap, offline, localhost, no-silent-
   outbound, schema, error-safety, and client-removal proofs.
6. **PAA-5 — Auth boundary:** design and implement only after threat review and
   explicit approval.
7. **PAA-6 — Lock-in gate:** make adopted guarantees executable; do not add
   another ignorable CI check before branch protection is enforced.
8. **PAA-7 — BrainDrive harvest:** disposition UX/operations ideas with actual
   output evidence.

## Non-negotiable guardrails

- Open WebUI is a replaceable shell, never Kitty's authority or canonical
  owner-memory platform.
- KittyBuilder remains the sole durable engineering execution control plane.
- `memory_graph` remains the unified read path until a deliberate ADR changes
  it; PAA work must not create a parallel memory stack.
- Backup/restore work extends PR #388 rather than competing with it.
- No broad rewrite to LangGraph, BrainDrive, the PAA TypeScript template, or any
  other framework without measured evidence that it reduces total complexity.
- `PASS` means verified evidence, not architectural resemblance.
