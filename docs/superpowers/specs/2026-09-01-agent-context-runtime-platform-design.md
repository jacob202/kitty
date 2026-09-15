# Kitty Agent Context & Runtime Platform Design

**Date:** 2026-09-01
**Status:** Approved for phased implementation
**Owner:** Kitty architecture / operator
**Scope:** Agent context, code intelligence, DSH execution, model routing, and measured learning

## Problem

Kitty has strong individual subsystems but agents still pay repeatedly to rediscover the same facts. Repository navigation is often raw search/read churn; durable engineering knowledge lives in `~/kb`; Kitty has several memory/knowledge stores behind `memory_graph`; Builder compiles its own context bundles; and the execution layer is moving from OpenCode to DeepSeek Harness (DSH).

The desired system is not one giant database or one giant prompt. It is a small set of authoritative planes with explicit ownership, progressive retrieval, and evidence showing whether each layer improves accepted outcomes.

## Goals

1. Make `~/kb` durable human-auditable knowledge and OpenViking its semantic/context engine.
2. Make CodeGraph the default repository navigation/topology layer for coding agents.
3. Keep exact source files authoritative for edits and exact-code claims.
4. Keep Kitty/Builder databases authoritative for operational state.
5. Make DSH the standard worker harness while Builder remains the control plane.
6. Define reusable execution profiles instead of ad-hoc model/preset/router combinations.
7. Measure retrieval usefulness, cache behavior, cost, latency, attempts, and independent acceptance.
8. Migrate additively with shadow reads and rollback; do not destroy existing context stores until parity is proven.

## Non-goals and authority boundaries

- OpenViking does **not** own Builder queue state, leases, attempt state, publication state, provider balances, or secrets.
- CodeGraph does **not** become source authority. It selects/narrows source; the checked-out file at the bound SHA remains authoritative.
- DSH does **not** own execution durability. Builder owns queueing, worktrees, budgets, retries, validation, evidence, review binding, and publication.
- OpenRouter does **not** own Kitty's product/model policy. Remote presets may be used for experiments, but versioned Kitty config is production authority.
- Creator/self-evolution may propose or canary configuration changes; it never silently promotes its own production configuration.
- Existing memory/KB stores are not deleted until shadow-read parity, provenance, rollback, and retrieval-quality gates pass.

## The four planes

### 1. Operational truth plane

SQLite/JSONL stores owned by Kitty and KittyBuilder remain exact truth for mutable state. Reads that answer "what is true now?" come from the owner, not from semantic memory.

Examples: Builder leases, packet state, PR/review SHA binding, project records, explicit-memory corrections, provider enablement, spend receipts.

### 2. Durable semantic context plane

`~/kb` remains the Git-backed, human-readable engineering knowledge source. OpenViking ingests selected KB material and becomes the shared semantic retrieval substrate for Kitty, DSH, and Builder.

OpenViking namespaces must distinguish resources, memories, and skills. Raw receipts/signals are not dumped indiscriminately into retrieval; they are compiled into useful lessons or kept as evidence.

### 3. Live code intelligence plane

CodeGraph indexes each exact working tree. Agents ask the graph for relevant symbols, callers/callees, blast radius, affected tests, and task context before broad filesystem reconnaissance.

Graph results are navigation evidence. Before mutation, the worker must bind to an exact workspace/SHA and use current source returned by CodeGraph or a targeted exact-file read. A stale graph fails closed to sync/reindex, never to confident guessing.

### 4. Execution/inference plane

DSH supplies composable agent behavior. OpenRouter supplies model/provider inference. Kitty supplies versioned execution policy. Builder supplies durable orchestration and acceptance.

## Cost and leverage objective

The platform optimizes **cost per independently accepted outcome**, not token count or cheapest-model percentage in isolation.

The cost model must account for:

- stable-prefix tokens sent repeatedly;
- prompt-cache write/read cost and actual cache-hit rate;
- provider endpoint drift that destroys cache locality;
- model/provider price and throughput;
- number of agent turns and tool calls;
- failed attempts, repair attempts, and reviewer reruns;
- context retrieval volume and irrelevant-context rate;
- independent-review spend;
- latency to accepted outcome.

A cheaper call that increases retries is not automatically cheaper. A larger stable prompt that is read at 0.1x after the first turn may be cheaper than repeatedly rebuilding context. Every profile therefore needs measured workload-specific evidence.

## OpenRouter exploitation policy

Production requests should deliberately use supported OpenRouter capabilities rather than relying on opaque defaults:

- stable `session_id` for multi-turn/agent-run sticky routing;
- prompt-cache telemetry (`cached_tokens`, `cache_write_tokens`, `cache_discount`);
- explicit provider policy: `sort`, `order`, `only`, `ignore`, `allow_fallbacks`, `max_price`, throughput/latency preferences, parameter support, and data-retention constraints;
- model fallback arrays where fallback semantics are safe;
- explicit reasoning effort/budget per workload;
- stable prompt prefixes and tool schemas to maximize reusable cache regions;
- evaluate Auto Exacto versus cache locality for tool-heavy runs instead of accepting one global default;
- use deferred/tool-search style mechanisms where supported when large tool schemas dominate the prefix;
- capture actual resolved model/provider and usage for every governed run.

OpenRouter presets may mirror or experiment with Kitty profiles, but hidden dashboard state must not become the only production source of truth.

## Execution profile model

Kitty needs named, versioned execution profiles that compose policy across layers instead of scattering decisions across shell scripts, DSH presets, OpenRouter defaults, and model-role files.

Each profile must declare:

- task class and risk class;
- DSH profile/preset and permission mode;
- model role plus allowed concrete models/fallbacks;
- reasoning effort;
- OpenRouter provider routing policy;
- sticky-session/cache policy;
- CodeGraph policy and freshness requirement;
- OpenViking namespaces and retrieval budget;
- maximum steps/turns and projected/actual cost ceilings;
- subagent policy and subagent model selection;
- reviewer profile and model-family independence requirement;
- verification/acceptance contract;
- telemetry fields required before promotion.

Initial profiles:

1. `surgical-fix` — Sprint, narrow graph context, minimal semantic retrieval, low turn budget, price-first routing.
2. `normal-builder` — Forge, graph-first navigation, bounded OpenViking retrieval, sticky session, independent reviewer.
3. `ui-creator` — Creator/Forge composition, screenshot/product context, stronger iteration budget, mandatory running-product acceptance.
4. `architecture` — high-reasoning model, broader OpenViking context, read-only until decision artifact is accepted.
5. `reviewer` — read-only, independent model family where practical, exact diff/SHA and acceptance evidence.
6. `repo-research` — read-only parallel exploration, CodeGraph + OpenViking, no mutation authority.
7. `unattended-builder` — Forge plus durable Builder ownership, managed worktree, health/recovery, hard spend/step limits.
8. `harness-evolution` — isolated Creator/canary profile allowed to propose DSH/plugin/profile changes but never self-promote.

Existing `config/model_roles.json` remains the model-role/evaluation ontology. The implementation should extend it or introduce one thin execution-profile registry that references it; model/provider facts must not be duplicated across several independent config files.

## DSH plugin strategy

DSH is developer-preview software with compatibility-breaking changes expected. Production and experimentation therefore use separate homes/profiles.

- Keep the known-working stable `~/.dsh` lane as rollback until the replacement lane proves parity.
- Use `~/.dsh-next` / `dsh-next` for newer DSH/plugin compatibility experiments.
- Promote a plugin only after source/maintenance/license/version review plus a runtime fixture.
- Prefer plugin capabilities that replace repeated prompt work or increase observability/recovery; reject decorative overlap.

Priority plugin candidates to evaluate:

- `openviking-dsh-plugin` — direct semantic context/memory bridge after OpenViking initialization is complete.
- `dsh-git-worktree` — managed worktree lifecycle; acceptance must finish before it becomes preferred.
- `dsh-continual-evolve` — candidate for governed harness-specific learned rules/skills.
- `dsh-session-health` — unattended/session health and recovery visibility.
- `dsh-subagent-model-picker` — heterogeneous model selection for delegated jobs.
- `dsh-automation` — only where it adds harness-runtime orchestration rather than duplicating Kitty Automations.
- agent-team plugins — experimental only while they require alpha DSH; no production promotion without measured advantage.
- usage/cost/cache telemetry plugins — high priority because optimization without receipts is guesswork.

Creator Mode is an optimization laboratory, not an autonomous production administrator. It may analyze receipts, propose profile/plugin/prompt changes, generate canary configuration, and run bounded benchmarks. Promotion still requires deterministic gates plus an independent reviewer.

## CodeGraph policy

CodeGraph is the default code-navigation surface for repository agents.

For code tasks, the expected order is:

1. verify/sync the graph for the exact worktree;
2. use `context`/`explore`/`node`/`impact`/`affected` to identify the minimal source/test set;
3. consume source blocks returned by the graph rather than repeating equivalent raw reads;
4. perform targeted exact-file reads only for gaps, generated/dynamic content, or a mutation precondition not represented by the graph;
5. after edits, sync/reindex before relying on graph relationships again.

CodeGraph must never hide repository SHA/worktree identity. Context receipts record graph version, index freshness, workspace path/SHA, nodes surfaced, and whether raw fallback reads were required.

## OpenViking / `~/kb` consolidation

`~/kb` remains durable source material. OpenViking becomes the retrieval and progressive-context layer over it.

Initial mapping:

- `~/kb/wiki`, `corrections`, `decisions`, `projects` → OpenViking resources;
- stable operator/project preferences and durable lessons → governed memories where appropriate;
- `~/kb/skills` and selected repo skills → OpenViking skills, preserving original files;
- `raw`, review envelopes, implementation JSON, metrics, and workflow signals → evidence/archive by default, not automatically retrieved context;
- distilled lessons from evidence may be promoted into resources/memories/skills through a governed compaction step.

Kitty's accepted ADR boundary remains intact: `memory_graph` owns prompt/search context reads, while storage behind its adapters is replaceable. OpenViking should first appear as a new adapter/shadow source, not as a route-level bypass.

Builder continues generating a deterministic context manifest. OpenViking and CodeGraph references added to Builder context must be bound by query, source URI/path, source digest/version where available, retrieval timestamp, and bounded token/byte budget so an attempt remains auditable.

## Measurement and promotion gates

Every candidate change must be evaluated on representative Kitty work, not a synthetic single prompt alone.

Required measurements include:

- accepted outcome rate and independent first-pass approval;
- total cost and cost per accepted outcome;
- elapsed time to accepted outcome;
- model/provider/endpoint actually used;
- prompt/completion/reasoning tokens;
- cached tokens, cache-write tokens, cache discount, and cache-hit ratio;
- DSH steps/rounds/tool calls and failed tool calls;
- CodeGraph context calls, raw-read fallbacks, and stale-index incidents;
- OpenViking entries consulted/used/stale or wrong and context tokens loaded;
- attempts, repair commits, regressions, duplicate work prevented;
- reviewer spend and reviewer disagreement.

Promotion requires no critical regression and must improve quality, cost, or latency by the thresholds already governed in `config/model_roles.json`, unless the operator records a specific exception.

## Migration order

1. Inventory and baseline current spend/context behavior.
2. Finish the already-active DSH Builder adapter lane; do not duplicate it here.
3. Make CodeGraph graph-first navigation available to DSH and Builder workers.
4. Shadow-ingest `~/kb` into OpenViking after operator initialization completes.
5. Add OpenViking behind `memory_graph` and Builder context boundaries in shadow mode.
6. Add OpenRouter sticky-session/cache/provider-routing controls and full usage receipts.
7. Introduce versioned execution profiles and route DSH/Builder through them.
8. Add plugin canaries for health, model picking, continual evolution, and managed worktrees.
9. Run paired benchmark campaigns and promote winners only.
10. Retire duplicate OpenCode/context/vector paths only after parity and rollback gates pass.

## Context deduplication rule

Each run has exactly one primary owner for initial context compilation.

- Interactive DSH sessions may let the DSH/OpenViking integration perform progressive retrieval directly.
- Builder-owned runs compile and bind initial CodeGraph/OpenViking context through Builder's context bundle/manifest so the attempt is reproducible.
- A DSH plugin may remain available for explicit follow-up retrieval, but it must not eagerly inject the same material a Builder bundle already supplied.
- Context items carry stable source IDs/digests so duplicate content can be detected before prompt assembly.
- Prompt-prefix ordering is deterministic: stable policy/instructions first, then stable tool schema, then bound task context, then changing conversation/tool results. This deliberately protects provider prompt-cache locality.

## Verified DSH/OpenRouter leverage seam

The current `dsh-next` alpha stack already carries a stable `GenerateOptions.sessionId` through `@deepseek-ai/dsh-llm` into `@deepseek-ai/dsh-llm-pi-ai`, which forwards it to pi-ai. DSH also records cache-read and cache-write token buckets in trajectory/session telemetry.

The underlying `@earendil-works/pi-ai` OpenAI-compatible adapter already implements:

- OpenRouter `x-session-id` session-affinity formatting;
- the OpenRouter `provider` routing object (`order`, `only`, `ignore`, `sort`, `allow_fallbacks`, `max_price`, throughput/latency preferences, ZDR/data-collection, etc.);
- cache-retention and prompt-cache plumbing;
- cache read/write usage accounting.

However, pi-ai defaults `sendSessionAffinityHeaders` to false, and DSH's current `llm-pi-ai` configuration gate intentionally withholds `sendSessionAffinityHeaders`, `sessionAffinityFormat`, and `openRouterRouting`. Therefore the preferred implementation order is:

1. check each DSH release for newly exposed native configuration;
2. use native configuration immediately if available;
3. otherwise add one tiny, version-pinned OpenRouter policy adapter/plugin that exposes the already-existing pi-ai capabilities;
4. do not reimplement the OpenRouter wire protocol or fork pi-ai.

This is a high-value target because DeepSeek cache reads through OpenRouter can cost roughly one tenth of ordinary input while agent loops repeatedly resend stable instructions/tools/context. Actual savings must be verified from usage receipts, not assumed.

## Durable communication plane

`workspace_global` is Kitty's canonical Global Agent Room. Jacob, ChatGPT, Claude, Codex, and Kitty use it for durable handoffs, questions, plans, reviews, results, status updates, and direct messages.

The room is communication, never execution authority. KittyBuilder remains authoritative for engineering tasks/leases; GitHub issue #490 remains authoritative for interactive ownership/collision control; Git/GitHub remain publication evidence. Agents check the room when starting/resuming relevant work, acknowledge received messages, reply in thread, and post meaningful handoffs/results there.
