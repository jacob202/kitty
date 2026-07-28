# Kitty and KittyBuilder Architecture Research Correction — 2026-07-28

**Status:** Corrected research decision record and implementation input  
**Scope:** Updates the prior external-architecture/OpenCode research without discarding verified findings  
**Repository baseline:** `main` at the time this correction was authored  
**Authority:** Current code and accepted ADRs override earlier reports, archived material, project marketing, and assumptions

## 1. Executive correction

The previous report made a major boundary error: it treated Kitty and KittyBuilder as one generalized durable coding orchestrator. That framing is rejected.

The durable product flow is:

```text
Jacob <-> Kitty -> approved Mission and authored packets -> KittyBuilder
KittyBuilder -> verified Result and Evidence -> Kitty <-> Jacob
```

Kitty is the user-facing personal AI assistant and conversational principal. KittyBuilder is the engineering execution control plane and autonomous coder/engineer. They are related parts of one product, but they have separate responsibilities and separate authoritative stores.

This correction preserves useful prior research, but reassigns it to the correct owner and withdraws recommendations that conflict with current repository evidence.

### Conclusions that materially change

1. **Do not replace KittyBuilder with Prefect, Temporal, Hatchet, Dagster, or LangGraph.** KittyBuilder already has durable queues, leases, fencing, attempts, recovery, initiatives, worker/reviewer execution, publication rails, and cost governance. External workflow engines remain design references or bounded proof-of-concept candidates only after a specific current-code gap is proven.
2. **Do not call OpenCode workstation plugins Kitty product features.** A notification, worktree, PTY, session, or redaction plugin belongs to Jacob's workstation unless KittyBuilder deliberately invokes it through a supported worker adapter.
3. **Do not prematurely declare the Kitty frontend decision complete.** The current `kitty-chat` plus `assistant-ui` implementation remains the production baseline, while the existing LibreChat and AnythingLLM spike completes real-product workflow evidence. Bootability is not product fit.
4. **Do not adopt Open WebUI as a fork target under the repository's current legal rule.** It remains a product/design reference. The existing spike excludes it because its current custom licence does not satisfy Kitty's rebrand-and-redistribute requirement.
5. **Paid OpenRouter execution is allowed, but must be explicit.** It requires a separate governed paid worker/reviewer route. The current `free-builder` and `free-reviewer` definitions explicitly prohibit paid models and must not be silently bypassed with a model override.

## 2. Verified architecture snapshot

### 2.1 Kitty

Kitty owns:

- the chat UI and overall product experience;
- conversations, turns, attachments, artifacts, and durable user-facing continuity;
- user intent, clarification, planning, and unresolved architecture judgment;
- personal context, memory, projects, documents, provenance, and correction;
- model/provider interaction as experienced by the user;
- tools, integrations, Tutor, Image Lab, automations, and proactive assistance;
- approval policy for consequential user-facing actions;
- authoring a versioned Mission and implementation packets after Jacob approves intent;
- presenting KittyBuilder progress, blockers, evidence, cost, and approval requests;
- the resume loop: what happened, what needs attention, what is next, and what can continue.

Kitty must remain useful when KittyBuilder is unavailable. Builder outages may remove coding execution, but must not remove chat, memory, projects, documents, Tutor, Image Lab, or ordinary tools.

Current evidence:

- `docs/KITTY_PRODUCT_ARCHITECTURE.md`
- `docs/FEATURE_REALITY_2026-07-28.md`
- `docs/adr/0015-resume-loop-and-builder-boundary.md`
- `docs/adr/0017-kitty-mission-builder-control-plane.md`
- `gateway/kitty-chat/`
- the Gateway conversation, context, memory, capability-manifest, project, Tutor, Image Lab, and automation routes

### 2.2 KittyBuilder

KittyBuilder owns:

- accepted Missions and authored implementation packets;
- engineering task queues and dependency ordering;
- task, attempt, initiative, and publication state machines;
- leases, heartbeats, fencing, retries, exhaustion, reconciliation, and recovery;
- coding workers and independent reviewers;
- provider exhaustion during coding execution;
- repository identity, branches, worktrees, commits, pull requests, and merge gates;
- test execution, deterministic validation, CI, evidence, review, and publication;
- execution budgets, stopping rules, allowed paths, and engineering policy;
- resumable execution after worker, provider, process, or machine failure.

KittyBuilder does not own Jacob's conversation history, personal memory, projects, unresolved product judgment, or the assistant UI.

Current evidence:

- `docs/adr/0017-kitty-mission-builder-control-plane.md`
- `docs/FREE_WORKERS.md`
- `config/compute_governor.json`
- `scripts/kittybuilder_opencode_worker.sh`
- `scripts/kittybuilder_opencode_reviewer.sh`
- Builder queue, run, initiative, identity, lease, recovery, validation, and publication modules
- `data/kittybuilder/` schemas and tests

### 2.3 OpenCode

OpenCode is a coding-agent workstation and a KittyBuilder worker substrate. It is not Kitty and it is not the Builder control plane.

OpenCode may execute a bounded packet inside a Builder-owned worktree. KittyBuilder still owns task truth, attempt truth, identity, leases, budgets, evidence, and publication. A plugin used only during Jacob's interactive development belongs to the workstation lane.

## 3. Reclassification of prior findings

| Prior finding or recommendation | Correct lane | Corrected disposition |
|---|---|---|
| Temporal durable execution | KittyBuilder | Design reference only; reject production migration without a measured gap that current recovery cannot close. |
| Hatchet leases, retries, durable tasks | KittyBuilder | High-value pattern source; compare APIs and reconciliation semantics against current Builder code. No control-plane replacement. |
| Prefect flows and retries | KittyBuilder | Reject as the default implementation plan. It duplicates existing state/retry authority and adds a second workflow truth. |
| Dagster | KittyBuilder | Reject for current product; data-pipeline orientation and migration cost exceed demonstrated benefit. |
| LangGraph | Kitty or KittyBuilder depending use | Pattern source for bounded reasoning graphs; never authoritative for Builder task state or Kitty personal continuity. |
| OpenHands, SWE-agent, Aider | KittyBuilder | Worker/evaluation/reference implementations. Aider repo-map patterns remain useful. Do not replace Builder governance. |
| OpenCode PTY, worktree, shell strategy | OpenCode workstation or KittyBuilder adapter | Workstation by default; Builder only when invoked through a versioned adapter with Builder-owned evidence. |
| GitHub merge queues and PR automation | KittyBuilder | Retain as publication integration; Builder owns readiness and evidence, GitHub owns hosted merge execution. |
| Worker fencing, stale recovery, leases | KittyBuilder | Already core Builder responsibilities. Improve existing code rather than importing a second engine. |
| LibreChat, AnythingLLM, LobeChat/LobeHub | Kitty | Candidate shell or pattern source. Must remain a client of Kitty-owned state and policy. |
| Open WebUI | Kitty | Design reference only under current legal rule; not an eligible fork target. |
| `assistant-ui` | Kitty | Retain current embedded component foundation while the full-app spike is unresolved. |
| AG-UI | Kitty/shared protocol | Evaluate as an interaction protocol or adapter pattern, not as a new source of conversation truth. |
| Pipali and Khoj | Kitty | Product/pattern harvest for projects, automation, proactive UX, and local-first behavior. |
| Letta, Graphiti, mem0 memory patterns | Kitty | Memory provenance, temporal correction, and inspection patterns. Kitty remains authoritative. |
| Home Assistant automation/approval patterns | Kitty | Pattern harvest for schedules, notifications, permissions, degraded operation, and local-first integrations. |
| InvokeAI/ComfyUI image workflows | Kitty | Image Lab provider/workflow references; do not move image orchestration into Builder. |
| LiteLLM/provider abstraction | Shared infrastructure with Kitty authority | Retain current provider abstraction. Kitty owns user-facing policy; Builder consumes an execution projection constrained by Mission policy. |
| Langfuse/OpenTelemetry/Sentry | Shared infrastructure | Correlation and projection layer only; domain records remain in Kitty or Builder stores. |
| notifier, scheduler, goal, session plugins | OpenCode workstation | Do not ship as Kitty product dependencies merely because they improve Jacob's development session. |
| jailoc/Brood Box | KittyBuilder | Sandbox proof-of-concept candidates. Adoption requires Apple Silicon validation, secrets policy, performance evidence, and rollback. |
| vulture, lychee, deptry, uv, mise, vale, ADR tools | OpenCode workstation/shared repository hygiene | Preserve prior findings. These improve repository development and CI, not Kitty's runtime identity. |

## 4. Kitty chat-foundation decision

### Decision now

**Keep the current `kitty-chat` plus `assistant-ui` implementation as the production baseline. Do not yet declare it the permanent winner.**

The repository already contains an evidence-gated foundation spike:

- current Kitty plus `assistant-ui`;
- LibreChat pinned at `a53936d27351e798d320df8f717be3f2272fc49d`;
- AnythingLLM pinned at `30c047e61b9dc96d9fcb93fbb1d3d5f0f1fec22e`.

LibreChat and AnythingLLM have booted against a Kitty-compatible Gateway. The remaining decision is product fit through the shared real-workflow contract in `spikes/foundation-replacement/RESULTS.md`.

### Candidate dispositions

| Candidate | Disposition | Why |
|---|---|---|
| Current Kitty + `assistant-ui` | **Production baseline; retain while evaluating** | Already integrated, narrow upstream dependency, maximum control, no competing app store. Still carries substantial application-plumbing burden. |
| LibreChat | **Continue thin-fork/spike evaluation** | Mature conversations, files, providers, agents, MCP, auth, and artifacts. High infrastructure and competing-authority risk. |
| AnythingLLM | **Continue thin-fork/spike evaluation** | Strong workspaces, documents, memories, routing, agents, flows, and schedules. Its workspace ontology may conflict with Kitty's life-project model. |
| Open WebUI | **Design reference; reject as fork target under current rule** | Historically coherent shell, but current licence does not pass Kitty's legal reuse gate. |
| LobeChat/LobeHub | **Pattern harvest / monitor** | Strong design, mobile/PWA, knowledge and multimodal patterns; no proven lower-risk state boundary than current spike candidates. |
| AG-UI implementations | **Protocol/component study** | Potentially useful event and tool-presentation contracts; must adapt to Kitty's durable turns and approvals. |
| Pipali/Khoj | **Product-pattern harvest** | Useful proactive, project, scheduling, research, and local-assistant patterns; not a drop-in authoritative shell. |

### Foundation acceptance gate

No migration may begin until one candidate wins the same real workflows for:

1. personal continuity and provenance;
2. provider switching and zero-dollar survival;
3. projects, documents, and scoped context;
4. tools and consequential-action approval;
5. mobile interruption/resumption;
6. extension cost for Image Lab, Tutor, proactive work, and Builder evidence;
7. upstream maintenance and rollback.

A candidate is disqualified if it requires a second authoritative memory, routing, permission, project, conversation, or Mission store.

## 5. KittyBuilder foundation decision

### Decision now

**Retain the current KittyBuilder control plane. Harvest patterns; do not migrate execution truth to an external workflow engine.**

Current Builder capability is not hypothetical: the repository already implements durable SQLite-backed task state, leases, fencing, attempts, recovery, initiatives, worker/reviewer contracts, worktree identity, validation, provider-exhaustion handling, cost governance, and publication rails.

### Candidate dispositions

| Candidate | Disposition | Build/buy choice |
|---|---|---|
| Current KittyBuilder | **Retain and harden** | Build and maintain the product-specific control plane. |
| Hatchet | **Design reference and optional isolated benchmark** | Independently implement selected patterns; no runtime dependency yet. |
| Temporal | **Reference for replay, idempotency, and failure semantics** | Reject migration unless future scale makes the server/runtime burden objectively lower risk. |
| Prefect | **Reject current integration plan** | Do not wrap existing missions in `@flow`; this creates duplicate retry and state authority. |
| Dagster | **Reject** | Poor fit and excessive ownership/migration cost. |
| LangGraph | **Narrow reasoning-flow pattern only** | May help a worker reason; must not own Builder execution truth. |
| OpenHands/SWE-agent/Aider/OpenCode | **Workers, benchmarks, and code-pattern sources** | Wrap through Builder adapters; never bypass Builder state/evidence. |
| jailoc | **Sandbox POC** | Wrap narrowly behind a feature flag after host compatibility and credential tests. |
| Brood Box | **High-isolation POC/monitor** | Optional experimental executor; not default until Apple Silicon reliability is proven. |

## 6. Shared ownership map

| Concern | Authoritative owner | Read projection | Allowed commands | Prohibited writes | Failure/reconciliation |
|---|---|---|---|---|---|
| Provider catalogue and health | Kitty provider layer | Builder receives approved execution-capability projection | Builder reports worker/provider health observations | Builder may not redefine user-facing provider identity | Kitty reconciles catalogue; Builder records attempt-local failures. |
| User model-routing policy | Kitty | Builder receives Mission constraints and approved routes | Builder requests/escalates route within policy | Builder may not change Jacob's global preference | Fail closed or degrade visibly; return blocker/evidence. |
| Coding-worker route selection | KittyBuilder | Kitty receives route/cost projection | Builder chooses free/cheap/frontier within Mission and governor | Kitty may not mutate an active attempt's route record | Builder records decision and receipt atomically before execution. |
| Provider credentials | Kitty-owned local secret boundary | Builder receives scoped environment/credential handle | Explicit credential grant to approved adapter | No credential copy into packets, logs, worktrees, or model prompts | Revoke grant; classify failure without exposing secret. |
| Usage and cost records | Domain-local ledgers; Kitty presents consolidated view | Kitty and Builder exchange correlated projections | Append receipts with provider/model/attempt IDs | No rewriting provider invoices or another domain's ledger | Reconcile estimates against provider statements without changing historical receipts. |
| Project identity | Kitty | Builder receives immutable project/repository references in Mission | Resolve repository under approved mapping | Builder may not edit Kitty project records | Reject ambiguous/missing mapping before attempt creation. |
| Mission intent and approval | Kitty | Builder receives accepted immutable Mission version | Submit, supersede, cancel through versioned commands | Builder may not reinterpret unresolved intent | Return clarification request; Kitty authors a new Mission version. |
| Mission execution state | KittyBuilder after acceptance | Kitty receives status projection | Pause, resume, cancel, approve publication via commands | Kitty may not write Builder DB rows | Rebuild projection from Builder events/results. |
| Task/attempt/lease state | KittyBuilder | Kitty receives summarized progress/blockers | Builder-only transitions | No direct Kitty writes | Reconcile stale leases and interrupted attempts in Builder. |
| Result and evidence | KittyBuilder | Kitty renders immutable Result projection | Request repair/new packet; acknowledge result | Kitty may not alter evidence or mark validation passed | Supersede with a new Result version, never mutate history. |
| Personal artifacts/documents | Kitty | Builder receives explicit packet attachments or snapshots | Read only within packet scope | Builder may not crawl Kitty stores | Missing context becomes blocker, not broad access. |
| Code/build artifacts | KittyBuilder/Git | Kitty renders links/diffs/receipts | Publish through Builder rails | Kitty may not create hidden commits/PR state | Git/CI reconciliation plus Result update. |
| Notifications | Kitty | Builder emits notification-worthy events | Kitty schedules/displays/dismisses | Builder may not notify Jacob directly through ad hoc channels | Kitty deduplicates by event ID and preserves attention state. |
| Approval policy | Kitty; Builder enforces engineering gates | Both receive versioned policy projection | Jacob approves through Kitty; Builder validates token | No bypass via UI or worker | Fail closed and return required approval. |
| Audit logs | Domain owner, correlated IDs | Shared read-only observability | Append domain events | No cross-store mutation | Trace correlation may be rebuilt; domain truth remains canonical. |
| Telemetry | Shared instrumentation, domain-owned semantics | Dashboards | Emit correlated metrics/traces | Telemetry cannot transition product state | Loss of telemetry degrades visibility, not correctness. |
| Remote access | Kitty product boundary | Builder status exposed through Kitty projection | Authenticated Kitty commands | No raw Builder DB or secret exposure | Revoke session; preserve local execution truth. |
| Secrets/redaction | Kitty secret policy; Builder executor enforcement | Redaction receipts only | Scoped injection and local restore when approved | Never persist plaintext in packet/evidence | Stop execution and rotate/revoke on leak suspicion. |

## 7. Corrected build-versus-buy decisions

| Area | Decision | Effort / burden | Licence / dependency | Migration / rollback |
|---|---|---|---|---|
| Kitty chat shell | Keep current baseline; complete existing full-app spike | Medium evidence work; avoids premature rewrite | `assistant-ui`, LibreChat, AnythingLLM are MIT in current spike | Candidates remain isolated; rollback is current Kitty. |
| Durable conversation/turn model | Build in Kitty, harvest mature UI/event patterns | Product-specific state and provenance justify ownership | No new authoritative server | Additive schema/projection migration with compatibility readers. |
| Memory evidence/correction | Build in Kitty; borrow Graphiti/Letta/Khoj patterns | High product value, moderate maintenance | Avoid committing to external graph DB before benchmark | Feature flag richer projection; retain raw sources. |
| Builder control plane | Keep/build current | Existing investment and product-specific Git/evidence semantics dominate | Avoid second orchestrator runtime | No migration. External POCs isolated. |
| Paid coding execution | Add governed Builder adapter | Small-to-medium, high leverage | OpenRouter already allowed; model IDs must be config-driven | Feature flag and per-packet route; free lane unchanged. |
| Sandbox | POC jailoc and Brood Box separately | Medium operational burden | External runtime/container or microVM dependencies | Adapter flag; fall back to current worktree executor. |
| Observability | Add correlation using standard telemetry where useful | Low-to-medium; no state authority | OpenTelemetry-compatible instrumentation preferred | Disable exporter without affecting domain records. |
| Workstation plugins | Configure selectively, do not vendor into product | Low | Per-plugin licence review | Remove config/plugin with no product migration. |

## 8. Prioritized recommendations

Scores are 0–5. Priority is weighted toward value, confidence, and architectural leverage, and against complexity, maintenance, and risk.

| Rank | Recommendation | Owner | Value | Confidence | Complexity | Maint. | Risk | Leverage | Priority |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Finish the existing foundation spike with real Kitty workflows before any frontend migration | Kitty | 5 | 5 | 2 | 1 | 1 | 5 | 9.2 |
| 2 | Add explicit governed paid OpenRouter worker/reviewer routes | KittyBuilder | 5 | 5 | 2 | 2 | 2 | 5 | 8.8 |
| 3 | Harden versioned Mission/Result schemas and projection tests | Shared / Builder authority | 5 | 5 | 2 | 1 | 1 | 5 | 9.3 |
| 4 | Complete durable turn/stream interruption and recovery semantics | Kitty | 5 | 4 | 3 | 2 | 2 | 5 | 8.3 |
| 5 | Implement memory provenance, correction, history, and undo UX | Kitty | 5 | 4 | 3 | 3 | 2 | 5 | 8.0 |
| 6 | Make resume-loop attention state a first-class Kitty projection | Kitty | 5 | 4 | 3 | 2 | 2 | 5 | 8.2 |
| 7 | Expose Builder Result/evidence/cost as a stable Kitty projection | Shared | 4 | 5 | 2 | 2 | 1 | 5 | 8.5 |
| 8 | Run isolated sandbox POCs before adopting jailoc or Brood Box | KittyBuilder | 4 | 4 | 3 | 3 | 3 | 4 | 7.0 |
| 9 | Compare current Builder recovery semantics against Hatchet/Temporal test cases | KittyBuilder | 3 | 4 | 2 | 1 | 1 | 4 | 7.6 |
| 10 | Keep OpenCode plugin improvements in a documented workstation profile | OpenCode workstation | 3 | 5 | 1 | 1 | 1 | 2 | 7.0 |

## 9. Packet-ready roadmap

Routing classes:

- `free`: zero-cost Builder worker/reviewer ladder;
- `paid-author`: paid model authors or repairs a packet, but execution remains free where practical;
- `paid-exec-openrouter`: explicit paid OpenRouter Builder worker, governed and receipted;
- `human`: Jacob-only judgment, taste, legal acceptance, or real-world proof.

A packet may escalate from `free` to `paid-exec-openrouter` only through a durable decision with reason, budget, model allowlist, and stopping rule. It may not fall back across partial work.

### Phase 0 — Correct the decision inputs

#### KTY-FND-01 — Complete the shared foundation workflows

- **Owner:** Kitty
- **Route:** `human` for real-workflow evidence; `paid-author` for evidence synthesis; Builder may implement test harness changes as bounded packets
- **Goal:** Fill `spikes/foundation-replacement/RESULTS.md` with comparable evidence for current Kitty, LibreChat, and AnythingLLM.
- **Acceptance:** Each workflow A–F has linked evidence, weighted scores, disqualifiers, extension-file counts, and a signed decision or explicit defer.
- **Rollback:** Spike remains isolated; no production shell changes.

#### SHR-CON-01 — Freeze Mission and Result contract v1 acceptance suite

- **Owner:** Shared contract; Kitty authors Missions, Builder owns accepted execution and Results
- **Route:** `paid-author`, then `free` implementation; `paid-exec-openrouter` if contract migration/reconciliation proves complex
- **Goal:** Machine-check ownership, versioning, idempotency, supersession, evidence, cost, cancellation, and clarification behavior.
- **Acceptance:** Contract fixtures pass from both Kitty and Builder sides; direct cross-store writes are impossible in tests.

### Phase 1 — Add the paid Builder lane safely

#### KTB-PAID-01 — Governed paid OpenRouter worker and reviewer

- **Owner:** KittyBuilder
- **Route:** `paid-exec-openrouter`
- **Likely files:** `opencode.jsonc`, new paid worker/reviewer adapters, Builder CLI/route selection, compute governor config/schema, tests, `docs/FREE_WORKERS.md`
- **Requirements:**
  1. define separate `paid-builder` and `paid-reviewer` agents; do not weaken `free-builder`;
  2. use config-driven OpenRouter model allowlists, not hard-coded user secrets;
  3. require packet route, maximum projected spend, attempt cap, and stopping rule before attempt creation;
  4. write model/provider/cost/route/governor receipts into attempt evidence;
  5. use an independent reviewer model/provider route when review is required;
  6. treat provider exhaustion as non-budget-consuming only under current explicit failure semantics;
  7. prohibit fallback over partial work or a written-but-invalid result;
  8. preserve all current worktree, identity, lease, validation, publication, and permission rails.
- **Acceptance:** Free tests remain unchanged; a paid dry-run explains route/cost without calling a model; an opt-in integration test records one paid receipt; disabling the feature restores the current free-only path.
- **Rollback:** `paid_openrouter_enabled=false`; remove paid agents/adapters without data migration.

#### KTB-ROUTE-02 — Route-selection and spend projection in Mission intake

- **Owner:** KittyBuilder, constrained by Kitty-authored Mission policy
- **Route:** `free` implementation; `paid-author` review
- **Goal:** Make `free`, `cheap`, `frontier`, and explicit human decisions visible before execution.
- **Acceptance:** Every attempt references a route decision and spend ceiling; no paid attempt starts from an unclassified packet.

### Phase 2 — Strengthen Kitty continuity and resume UX

#### KTY-TURN-01 — Durable turn and receipt model

- **Owner:** Kitty
- **Route:** `paid-author`; `free` or `paid-exec-openrouter` implementation based on schema risk
- **Goal:** Persist user input, assistant output, tool calls, approvals, attachments, artifacts, cancellation, retry lineage, provider receipt, and failure truth as durable turn records.
- **Acceptance:** Refresh, restart, interrupted stream, retry, and provider switch preserve truthful conversation state.

#### KTY-RESUME-02 — Resume-loop attention projection

- **Owner:** Kitty
- **Route:** `free` implementation with paid review for architecture-sensitive projection changes
- **Goal:** One surface answers what happened, what needs attention, what is next, and what can continue across Kitty and Builder.
- **Acceptance:** Builder offline state is explicit; non-Builder Kitty work remains usable; no direct Builder DB reads from the UI.

#### KTY-MEM-03 — Memory provenance and correction

- **Owner:** Kitty
- **Route:** `paid-author`; implementation route based on packet size
- **Goal:** Let Jacob inspect why a memory was used, correct it, see history, and undo changes.
- **Acceptance:** Every surfaced memory links to source/provenance and correction history; deletion/correction propagates through supported projections.

#### KTY-ART-04 — Tool, approval, artifact, and Builder-evidence cards

- **Owner:** Kitty
- **Route:** `free` for bounded UI packets; `paid-exec-openrouter` for cross-cutting state integration
- **Goal:** Present tool calls, approvals, generated artifacts, code diffs, validation, blockers, and cost without exposing raw internal stores.

### Phase 3 — Builder hardening by measured gaps

#### KTB-REC-03 — Recovery and failure-taxonomy comparison

- **Owner:** KittyBuilder
- **Route:** `paid-author` study; `free` implementation
- **Goal:** Translate useful Hatchet/Temporal/DBOS failure cases into Builder tests, not dependencies.
- **Acceptance:** A matrix maps crash points to current recovery behavior; only unhandled cases become packets.

#### KTB-SBX-04 — Sandbox bake-off

- **Owner:** KittyBuilder
- **Route:** `paid-exec-openrouter` only for implementation after a human-approved POC plan
- **Goal:** Compare current worktree execution, jailoc, and Brood Box on Apple Silicon for isolation, secrets, network policy, performance, debugging, and cleanup.
- **Acceptance:** Reproducible evidence, licence review, threat model, resource measurements, and adapter rollback.

### Phase 4 — Workstation-only improvements

#### OCW-01 — Curated OpenCode profile

- **Owner:** OpenCode workstation
- **Route:** `free` or human configuration
- **Goal:** Document only the plugins that improve Jacob's interactive development workflow.
- **Rule:** No plugin becomes a Kitty/Builder dependency without a separate product packet and ownership analysis.

## 10. Proof, flags, and rollback requirements

Every production recommendation must include:

- repository state and base SHA;
- allowed and prohibited paths;
- a visible demo contract;
- deterministic validation;
- failure and provider-exhaustion tests where applicable;
- licence and attribution evidence;
- feature flag for a new runtime path;
- rollback that does not require deleting historical truth;
- cost ceiling and receipt for paid execution;
- browser evidence for user-facing behavior.

Suggested flags:

- `paid_openrouter_enabled`
- `paid_openrouter_max_attempt_cad`
- `builder_sandbox_backend=current|jailoc|brood_box`
- `kitty_foundation=current|librechat_spike|anythingllm_spike`
- `durable_turns_v2_enabled`
- `resume_projection_v2_enabled`

## 11. Exact code and upstream evidence worth inspecting

### Kitty repository

- `docs/KITTY_PRODUCT_ARCHITECTURE.md`
- `docs/FEATURE_REALITY_2026-07-28.md`
- `docs/adr/0015-resume-loop-and-builder-boundary.md`
- `docs/adr/0017-kitty-mission-builder-control-plane.md`
- `docs/research/FOUNDATION_REPLACEMENT_STUDY_2026-07-27.md`
- `spikes/foundation-replacement/README.md`
- `spikes/foundation-replacement/RESULTS.md`
- `spikes/foundation-replacement/bootstrap.sh`
- `gateway/kitty-chat/src/components/KittyRuntimeProvider.tsx`
- `gateway/kitty-chat/src/components/KittyThread.tsx`
- `gateway/kitty-chat/src/lib/kitty-runtime.ts`
- `gateway/kitty-chat/package.json`
- `docs/FREE_WORKERS.md`
- `config/compute_governor.json`
- `opencode.jsonc`
- `scripts/kittybuilder_opencode_worker.sh`
- `scripts/kittybuilder_opencode_reviewer.sh`
- Builder run, queue, identity, lease, reconciliation, result, and publication tests

### Pinned foundation candidates

- LibreChat: `danny-avila/LibreChat@a53936d27351e798d320df8f717be3f2272fc49d`
- AnythingLLM: `Mintplex-Labs/anything-llm@30c047e61b9dc96d9fcb93fbb1d3d5f0f1fec22e`
- `assistant-ui`: inspect the exact package-lock resolution currently committed before any upgrade

### Builder references

Inspect exact current commits before a POC and record them in the packet:

- Hatchet: lease, retry, worker heartbeat, cancellation, and event schemas
- Temporal: workflow determinism, activity retry, cancellation, and versioning tests
- DBOS: transaction/workflow recovery patterns
- Aider: repository map generation and Git-native editing patterns
- OpenHands and SWE-agent: worker sandbox/evaluation patterns
- jailoc and Brood Box: isolation adapters, network policy, mount rules, and cleanup

Do not copy code until the relevant licence and attribution requirements are recorded in the packet.

## 12. Licence and attribution rules

- Preserve all upstream licence and copyright notices for copied, vendored, embedded, or modified code.
- Record repository, commit SHA, source paths, licence, modifications, and destination paths.
- Prefer dependency use or independent pattern implementation over copying when maintenance is lower.
- Open WebUI is not an eligible fork target under the current project rule.
- MIT eligibility does not remove attribution obligations.
- Sandbox and OpenCode plugin licences must be verified at the exact adopted commit.

## 13. Previous recommendations that remain correct but move lanes

- Hatchet, Temporal, Prefect, worktree isolation, PTY lifecycle, fencing, retries, stale-worker recovery, CI, PR and merge patterns remain useful research—but belong to KittyBuilder or the OpenCode workstation.
- LibreChat, AnythingLLM, LobeChat, assistant-ui, AG-UI, Pipali, Khoj, memory UX, artifacts, attachments, approvals, and conversation recovery belong to Kitty.
- LiteLLM/provider abstraction, observability, evidence, credentials, cost, and Mission/Result contracts are shared concerns with one authoritative owner per transition.
- Vulture, lychee, deptry, uv, mise, vale, and similar tools remain repository/workstation hygiene recommendations.

## 14. Recommendations withdrawn or materially changed

- Withdraw: migrate KittyBuilder missions to Prefect `@flow`.
- Withdraw: remove current Builder retry/state logic in favor of Prefect.
- Withdraw: immediately adopt jailoc as the default executor.
- Withdraw: use OpenCode notifier as Kitty's product notification system.
- Withdraw: install OpenCode worktree/PTY plugins as substitutes for Builder-owned identity and lifecycle controls.
- Change: `assistant-ui` is already the current component foundation, not a new discovery.
- Change: current Kitty is a baseline, not the final foundation winner; the existing spike must finish.
- Change: LibreChat and AnythingLLM are live evidence candidates, not blanket rejections.
- Change: paid OpenRouter models are a legitimate Builder route when explicitly classified, governed, independently reviewed, and receipted.

## 15. Ready-to-paste implementation prompt — Kitty

```text
Continue Kitty product work from current repository evidence. Do not restart architecture discovery and do not modify KittyBuilder execution internals.

Read first:
- docs/KITTY_PRODUCT_ARCHITECTURE.md
- docs/FEATURE_REALITY_2026-07-28.md
- docs/adr/0015-resume-loop-and-builder-boundary.md
- docs/adr/0017-kitty-mission-builder-control-plane.md
- docs/research/FOUNDATION_REPLACEMENT_STUDY_2026-07-27.md
- spikes/foundation-replacement/RESULTS.md
- docs/research/KITTY_KITTYBUILDER_ARCHITECTURE_CORRECTION_2026-07-28.md

Repository evidence overrides this prompt. Kitty owns the assistant UI, conversations, turns, memory, projects, documents, artifacts, tools, Tutor, Image Lab, automations, planning, Mission authoring, approvals, and resume-loop presentation. KittyBuilder owns engineering execution truth.

Select the highest-priority ready Kitty packet from the corrected roadmap. Preserve current Kitty as the production baseline. Do not migrate to LibreChat or AnythingLLM until the shared real-workflow evidence is complete and accepted. Do not allow any candidate shell to become authoritative for Kitty memory, routing, permissions, projects, conversations, or Mission intent.

Create one bounded packet or implement one already-approved packet. State allowed paths, prohibited paths, demo contract, privacy class, feature flag, validation, browser evidence, rollback, and any KittyBuilder interface required. Communicate with Builder only through versioned commands/projections. Finish with exact evidence and remaining blockers.
```

## 16. Ready-to-paste implementation prompt — KittyBuilder

```text
Continue KittyBuilder engineering work from current repository evidence. Do not restart architecture discovery and do not replace the existing control plane with Prefect, Temporal, Hatchet, Dagster, or LangGraph.

Read first:
- docs/adr/0017-kitty-mission-builder-control-plane.md
- docs/FREE_WORKERS.md
- config/compute_governor.json
- opencode.jsonc
- scripts/kittybuilder_opencode_worker.sh
- scripts/kittybuilder_opencode_reviewer.sh
- docs/research/KITTY_KITTYBUILDER_ARCHITECTURE_CORRECTION_2026-07-28.md

Repository evidence overrides this prompt. KittyBuilder owns accepted Missions, packets, queues, attempts, leases, fencing, retries, recovery, workers/reviewers, worktrees, Git/PR/CI, validation, evidence, publication, budgets, and engineering policy. It does not own Kitty conversations, personal memory, product planning, or UI.

Select the highest-priority ready KittyBuilder packet. Packets may route to free workers or explicit paid OpenRouter workers. Never run a paid model through the existing free-builder/free-reviewer agents, because those agents prohibit paid execution. For paid work, require a separate governed agent/adapter, an OpenRouter allowlist, maximum projected spend, attempt cap, independent review, durable route/cost receipts, provider-exhaustion handling, and no fallback over partial work.

Preserve current task, lease, identity, worktree, validation, evidence, and publication rails. Treat external orchestration and sandbox projects as pattern/POC sources unless an accepted packet explicitly authorizes integration. Create a branch/worktree, implement only allowed paths, run focused and contract tests, publish honest evidence, and stop on any ownership-boundary conflict.
```

## Final corrected position

Kitty should converge toward an excellent local-first personal assistant by improving its durable turns, memory evidence, projects, tools, artifacts, automations, Tutor, Image Lab, and resume loop while completing—not prejudging—the existing mature-foundation spike.

KittyBuilder should converge by hardening the control plane already built, adding an explicit governed paid OpenRouter lane, and harvesting external recovery, isolation, and agent-execution patterns only where current-code evidence proves a gap.

The architecture that must not change is the separation of authority:

```text
Kitty owns human intent and personal continuity.
KittyBuilder owns engineering execution truth.
Versioned Mission and Result contracts connect them.
```
