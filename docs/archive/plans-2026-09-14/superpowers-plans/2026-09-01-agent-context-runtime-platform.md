# Agent Context & Runtime Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Kitty's paid/model/harness/context stack into a measured execution platform that minimizes cost per independently accepted outcome while improving context quality, recovery, and agent speed.

**Architecture:** Preserve three authorities: Kitty/Builder databases for operational truth, `~/kb` + OpenViking for durable semantic context, and exact checked-out source with CodeGraph for live code intelligence. DSH is the execution harness and OpenRouter is the inference fabric; versioned Kitty execution profiles compose them without transferring Builder's durable control-plane authority.

**Tech Stack:** Python 3.12, SQLite/JSONL, OpenViking, CodeGraph 1.6+, DeepSeek Harness stable + canary profiles, OpenRouter, pytest, Node 22+, existing KittyBuilder runtime.

**Spec:** `docs/superpowers/specs/2026-09-01-agent-context-runtime-platform-design.md`

## Global Constraints

- Never modify/reset/clean/stash/switch the canonical checkout; use isolated worktrees.
- No force-push or history rewrite.
- Fresh-fetch `origin/main` before merge/push decisions; exact-head verification is mandatory.
- Builder remains the sole execution/control-plane owner for packets, leases, attempts, validation, receipts, budgets, and publication.
- `gateway/memory_graph.py` remains the prompt/search read seam; no route-level OpenViking bypass.
- Exact source at the bound SHA is authoritative; CodeGraph is navigation/context selection, not truth replacement.
- `~/kb` remains preserved and Git-readable during migration; no destructive OpenViking migration.
- Explicit `--free` must never silently spend money.
- Do not touch OpenViking initialization/config until the operator says initialization is complete.
- Production DSH stable remains a rollback lane until the canary lane passes representative workload gates.

---
## Current verified baseline (2026-09-01)

- DSH stable: `0.1.1-rc.2`, default `kitty-forge`, OpenRouter + `deepseek/deepseek-v4-flash` high reasoning.
- Parallel canary launcher exists: `~/bin/dsh-next` with isolated `$DSH_HOME=~/.dsh-next`, runtime `0.1.2-alpha.3`; no production promotion yet.
- PR #749 owns the active Builder→DSH adapter migration. Its head `428a3bbe...` already mounts `kitty-forge` for workers and `kitty-sprint` for read-only review. Treat it as a dependency/collision, not work to recreate.
- CodeGraph production CLI is available; `/opt/homebrew/bin/codegraph` is 1.6.0. A fresh index on this plan worktree contains 1,085 files, 22,066 nodes, and 55,672 edges.
- A stale FNM-path CodeGraph 1.5.0 shim also exists; PATH normalization is required before automation relies on `codegraph` by name.
- CodeGraph telemetry was found enabled and has been disabled.
- `~/kb` exists and contains wiki, corrections, decisions, projects, preferences, metrics, raw evidence, skills, reviews, and workflow signals.
- Kitty's current knowledge vector store is `data/knowledge/chroma/chroma.sqlite3`; ADR 0030 already targets one vector store rather than nine memory stores.
- Direct OpenRouter calls in `gateway/llm_client.py` currently send model/messages/max_tokens/temperature and optional response format, but do not yet attach stable `session_id` or explicit OpenRouter provider-routing policy.

## Delivery structure

This program is intentionally split into independently reviewable slices. A later slice may depend on an earlier interface, but no slice may silently expand another subsystem's authority.

### Task 0: Reconcile active work and freeze the baseline

**Files:**
- Create: `docs/session-notes/2026-09-01-context-runtime-baseline.md`
- Read only: GitHub PRs/branches, `config/model_roles.json`, `config/builder_paid_routes.json`, DSH homes, CodeGraph status, `~/kb`

**Interfaces:**
- Consumes: live GitHub/working-tree state.
- Produces: exact dependency/collision ledger and baseline metrics used by every later task.
- [ ] **Step 1: Record exact active dependencies and collisions**

Run fresh GitHub/worktree inventory. At minimum classify PR #749 and every open DSH/OpenRouter/context-related PR as `dependency`, `superseded`, `reusable-evidence`, or `collision`.

- [ ] **Step 2: Capture cost/context baseline**

Run representative existing Builder/interactive receipts and summarize known model, cost, token, latency, attempts, and KB-use coverage. Preserve `null` for unmeasured fields.

- [ ] **Step 3: Verify current tools without mutation**

Record DSH stable/canary versions, CodeGraph executable paths/version/index status, OpenViking health only after operator initialization is complete, and `~/kb` inventory/digests.

- [ ] **Step 4: Commit baseline note**

```bash
git add docs/session-notes/2026-09-01-context-runtime-baseline.md
git commit -m "docs: baseline agent context runtime stack"
```

### Task 1: Normalize CodeGraph as the repository navigation layer

**Files:**
- Create: `scripts/code_context.py`
- Create: `tests/test_code_context.py`
- Modify: `AGENTS.md`
- Modify: `CODEX.md`
- Modify: Builder/DSH instruction template only after checking PR #749 ownership

**Interfaces:**
- Consumes: repo/worktree path, task text, optional allowed paths, exact HEAD.
- Produces: bounded JSON/Markdown code-context receipt with CodeGraph version, index freshness, workspace SHA, surfaced symbols/files/tests, and fallback-read status.
- [ ] **Step 1: Write failing freshness and bounded-context tests**

Tests must cover: missing index, stale index, wrong worktree/SHA, successful `context` output, and a hard maximum context size. A stale graph must request sync/reindex rather than silently return old context.

```python
def test_stale_codegraph_fails_closed(tmp_path):
    result = build_code_context(repo=tmp_path, task="change call_llm")
    assert result.status == "stale"
    assert result.context == ""
```

- [ ] **Step 2: Implement `scripts/code_context.py` using CodeGraph 1.6+**

Use the explicit `/opt/homebrew/bin/codegraph` resolution or a verified version-aware resolver until the stale FNM shim is removed. Prefer `codegraph context`; expose targeted `explore`, `impact`, and `affected` only as follow-up operations.

- [ ] **Step 3: Add graph-first agent instructions**

Instruction contract: graph first; graph-returned exact source counts as a read; do not repeat equivalent grep/read reconnaissance; targeted raw reads remain allowed for gaps and mutation preconditions.

- [ ] **Step 4: Prove token/read reduction on three real tasks**

Compare existing raw-read workflow versus CodeGraph-first for a surgical fix, cross-module backend change, and frontend change. Record files read, context bytes/tokens, tool calls, elapsed time, accepted outcome.

- [ ] **Step 5: Mount CodeGraph MCP into a DSH canary profile**

Use the local stdio server contract `codegraph serve --mcp`. Do not grant write authority through this integration. Verify `context`, `explore`, `node`, `impact`, and `affected` against an isolated fixture and one Kitty worktree.

- [ ] **Step 6: Commit only after the graph-first contract is independently reviewed**

```bash
pytest -q tests/test_code_context.py
git diff --check
git add scripts/code_context.py tests/test_code_context.py AGENTS.md CODEX.md
git commit -m "feat(context): make CodeGraph the agent navigation layer"
```

### Task 2: Shadow-ingest `~/kb` into OpenViking

**Prerequisite:** Operator explicitly confirms OpenViking initialization is complete.

**Files:**
- Create: `config/openviking/assets.yaml` or the exact supported manifest format discovered from the installed OpenViking version
- Create: `scripts/openviking_sync.py`
- Create: `tests/test_openviking_sync.py`
- Create: `docs/reference/OPENVIKING_CONTEXT_MAP.md`

**Interfaces:**
- Consumes: selected `~/kb` paths plus source digests/mtimes.
- Produces: non-destructive OpenViking resources/memories/skills with a sync receipt and no deletion of `~/kb`.
- [ ] **Step 1: Freeze the source mapping before ingestion**

Classify each `~/kb` path as `resource`, `memory`, `skill`, or `evidence-only`. Explicitly exclude raw implementation/review envelopes and workflow receipts from eager semantic retrieval unless distilled.

- [ ] **Step 2: Write non-destructive sync tests**

Tests must prove source files are never changed/deleted, unchanged inputs are idempotent, changed files update the corresponding OpenViking entry, removed source is reported rather than silently forgotten, and sensitive/private classes keep their intended visibility.

- [ ] **Step 3: Implement manifest-driven shadow sync**

The sync script emits a receipt containing source path, digest, OpenViking URI/id, classification, action, and error. A failed item does not make the whole inventory look synchronized.

- [ ] **Step 4: Run a retrieval benchmark before any cutover**

Use existing MemoryBench plus 20+ real `~/kb` questions spanning corrections, architecture decisions, model quirks, prior Builder failures, and UI/product decisions. Record hit@k, forbidden/stale retrieval, latency, and context size.

- [ ] **Step 5: Commit the shadow layer only**

```bash
pytest -q tests/test_openviking_sync.py
python3 scripts/openviking_sync.py --dry-run
git diff --check
git commit -am "feat(context): shadow Kitty KB into OpenViking"
```

### Task 3: Add OpenViking behind Kitty's governed context seam

**Files:**
- Modify: `gateway/memory_graph.py`
- Modify: `gateway/context_assembler.py` only if adapter metadata requires it
- Create: `gateway/openviking_context.py`
- Create: `tests/test_openviking_context.py`
- Modify: `tests/test_memory_graph.py`

**Interfaces:**
- Consumes: query plus Kitty memory policy/privacy constraints.
- Produces: `memory_graph.Item` rows with OpenViking source URI/id, score, digest/version metadata, and degradation evidence.

- [ ] **Step 1: Write failing adapter tests**

Cover success, timeout, OpenViking unavailable, malformed result, duplicate source IDs, privacy filtering, and shadow-mode disagreement with the incumbent knowledge path.

- [ ] **Step 2: Implement a read-only `OpenVikingAdapter`**

It must satisfy the existing `StoreAdapter` interface. No Gateway route or prompt assembler may call OpenViking directly.

- [ ] **Step 3: Add shadow comparison mode**

During shadow mode, retrieve incumbent + OpenViking results, surface only incumbent behavior to the user, and write comparison telemetry. Do not double-inject both result sets into the prompt.

- [ ] **Step 4: Run MemoryBench and context-assembler suites**

```bash
pytest -q tests/test_openviking_context.py tests/test_memory_graph.py tests/test_context_assembler.py tests/bench/test_memorybench.py
git diff --check
```

- [ ] **Step 5: Promote OpenViking only if parity gates pass**

Promotion requires no critical retrieval regression, acceptable stale/forbidden rate, bounded latency, and verified rollback to the incumbent adapter.

### Task 4: Compile CodeGraph + OpenViking context into Builder attempts

**Files:**
- Modify: `gateway/builder_context.py`
- Modify: `gateway/builder_runner.py`
- Modify: `gateway/models/builder.py` if the typed bundle needs new fields
- Modify: `tests/test_builder_context.py`
- Modify: `tests/test_builder_runner.py`

**Interfaces:**
- Consumes: packet objective, allowed paths, exact worktree SHA, CodeGraph receipt, bounded OpenViking retrieval.
- Produces: one deterministic Builder-owned context bundle plus manifest references; DSH must not eagerly duplicate the same context.

- [ ] **Step 1: Write failing provenance/dedup tests**

Assert every injected item has a source ID/digest, context is deterministically ordered, duplicate material is collapsed, and a mismatched worktree SHA/index fails closed.

- [ ] **Step 2: Add bounded context compilation**

Compile stable instructions, task facts, graph-selected source/test context, and semantic lessons under explicit byte/token budgets. Keep dynamic evidence after the stable prefix.

- [ ] **Step 3: Preserve Builder ownership and replayability**

The attempt manifest records query, source refs/digests, graph version/freshness, OpenViking retrieval metadata, and total context size without copying secrets or private source content into durable logs.
- [ ] **Step 4: Compare against the current static Builder context**

Run matched packets with incumbent context versus compiled context and record tool calls, context tokens, accepted outcome, repairs, and elapsed time.

- [ ] **Step 5: Commit the Builder context compiler**

```bash
pytest -q tests/test_builder_context.py tests/test_builder_runner.py
git diff --check
git commit -am "feat(builder): compile graph and semantic context"
```

### Task 5: Exploit OpenRouter caching, affinity, routing, and usage truth

**Files:**
- Modify: `gateway/llm_client.py`
- Create: `gateway/openrouter_policy.py`
- Create: `tests/test_openrouter_policy.py`
- Modify: `tests/test_llm_client.py`
- Modify: usage/receipt code only where existing telemetry cannot carry cache/provider fields

**Interfaces:**
- Consumes: execution-profile request policy and stable run/session identity.
- Produces: OpenRouter request fields/headers plus normalized usage including cache read/write/discount and resolved route evidence.

- [ ] **Step 1: Write wire-contract tests before changing dispatch**

Assert stable `session_id`/`x-session-id`, provider policy serialization, model fallback order, data-retention constraints, and no OpenRouter-only fields leak to non-OpenRouter providers.
- [ ] **Step 2: Prove DSH's actual OpenRouter wire behavior with a local capture server**

Run `kitty-forge` against a fake OpenRouter-compatible endpoint and record request headers/body across at least two turns. The test must answer whether DSH emits `x-session-id`, cache controls, and any `provider` object; do not infer this from internal types alone.

- [ ] **Step 3: Prefer native DSH/pi-ai support; otherwise expose only the missing knobs**

Current alpha evidence shows `GenerateOptions.sessionId` reaches pi-ai, while pi-ai's OpenRouter affinity and routing capabilities are withheld by `dsh-llm-pi-ai` config. If this remains true at implementation time, create a tiny version-pinned DSH OpenRouter policy plugin/adapter; do not fork pi-ai or replace the Harness LLM service.

- [ ] **Step 4: Add profile-level OpenRouter policies**

At minimum support: stable session affinity, `sort`, `allow_fallbacks`, `only`/`ignore`, `max_price`, throughput/latency preferences, `require_parameters`, `zdr`/data-collection policy, and ordered model fallbacks where safe.

- [ ] **Step 5: Normalize real cache and route telemetry**

Record resolved model/provider where OpenRouter exposes it, prompt/output/reasoning tokens, `cached_tokens`, `cache_write_tokens`, and `cache_discount`. Estimated plugin dashboards may supplement this, but provider-returned receipts are authoritative for spend attribution.

- [ ] **Step 6: Benchmark cache-first versus tool-quality-first routing**

For long tool-heavy Forge runs compare sticky + `provider.sort=price` against OpenRouter's default/Auto Exacto behavior. Cache locality wins only if accepted-outcome cost/time improves; tool-call correctness remains a hard quality gate. OpenRouter explicitly documents that Auto Exacto can reorder providers and reduce cache hits in tool loops.

- [ ] **Step 7: Verify repeated-prefix savings with a real paid canary**

Use one bounded multi-turn V4 Flash canary. Require a stable run/session ID and prove non-zero cache reads after the first eligible request from returned usage. Record actual dollar cost; stop if the provider response cannot prove caching.

- [ ] **Step 8: Commit OpenRouter policy only after exact wire tests and canary evidence pass**

```bash
pytest -q tests/test_openrouter_policy.py tests/test_llm_client.py
git diff --check
git commit -am "feat(routing): exploit OpenRouter affinity and cache policy"
```

### Task 6: Introduce one versioned execution-profile registry

**Files:**
- Modify: `config/model_roles.json`
- Create: `config/execution_profiles.json`
- Create: `gateway/execution_profiles.py`
- Create: `tests/test_execution_profiles.py`
- Modify: Builder/DSH adapter wiring only after PR #749 lands or its interface is rebased cleanly

**Interfaces:**
- Consumes: task/risk class plus current model-role and provider availability truth.
- Produces: immutable resolved profile containing DSH preset, model role/model candidates, reasoning effort, context policy, OpenRouter policy, budgets, and reviewer contract.

- [ ] **Step 1: Write schema/authority tests**

Tests must reject unknown model roles, duplicate model facts, missing reviewer contracts, paid fallback reachable from explicit `--free`, impossible budgets, and profiles that bypass Builder ownership.

- [ ] **Step 2: Implement the initial named profiles**

Add `surgical-fix`, `normal-builder`, `ui-creator`, `architecture`, `reviewer`, `repo-research`, `unattended-builder`, and `harness-evolution`. Profiles reference `model_roles.json`; they do not copy provider/model catalogues into a second registry.

- [ ] **Step 3: Compile profile → DSH/OpenRouter invocation**

One resolver produces the exact preset, provider/model, reasoning level, context budgets, affinity/routing settings, max rounds/cost, subagent policy, and reviewer profile for the run. Persist the resolved profile version/digest in the run receipt.
- [ ] **Step 4: Seed profile candidates without declaring winners**

Start with current measured incumbents: V4 Flash for cheap/surgical coding, the current `think` role for architecture, and a model-family-independent reviewer. Keep MiMo/Qwen/MiniMax/frontier models as benchmark candidates where already configured. Promotion follows receipts, not preference.

- [ ] **Step 5: Preserve explicit free semantics mechanically**

The resolver must make every paid candidate unreachable when `free_only=true`; failure returns exhaustion/blocked truth rather than silently selecting a paid profile.

- [ ] **Step 6: Verify deterministic profile resolution and commit**

```bash
pytest -q tests/test_execution_profiles.py tests/test_model_roles.py tests/test_builder_paid_routing.py
git diff --check
git commit -am "feat(runtime): add governed execution profiles"
```

### Task 7: Build a pinned DSH canary plugin stack

**Files:**
- Create: `docs/reference/DSH_PLUGIN_MATRIX.md`
- Create: `scripts/dsh_canary_verify.py`
- Create: `tests/test_dsh_canary_verify.py`
- Outside repo: isolated `~/.dsh-next` profile only; production `~/.dsh` remains rollback

**Interfaces:**
- Consumes: candidate plugin name/version/source SHA plus DSH version.
- Produces: compatibility/security/runtime verdict with evidence; no plugin promotion by installation alone.

- [ ] **Step 1: Record plugin provenance and compatibility**

For each candidate record source repo, license, release date, DSH peer range, install/build scripts, network/filesystem capabilities, active maintenance, known issues, and pinned version/SHA.
- [ ] **Step 2: Canary the high-value plugins in this order**

1. `@openviking/dsh-memory-plugin` after OpenViking init; start with `captureToolResults: false`, `skipSubagentSessions: true`, a bounded recall budget, and explicit peer-scope tests.
2. CodeGraph through DSH's MCP client using local `codegraph serve --mcp`.
3. `dsh-git-worktree` only after workspace-backed lifecycle acceptance proves create/list/review/recovery.
4. `dsh-session-health` and/or `@dshd/dsh-usage` for cache/token/session visibility; treat displayed cost as advisory unless reconciled to provider receipts.
5. `dsh-continual-evolve` for harness-specific prompt notes, delegation specs, and skills; do not let it become a second general project-memory authority beside OpenViking.
6. `dsh-subagent-model-picker` only after source-pin and model-routing tests; automatic choices must emit an auditable reason.

- [ ] **Step 3: Explicitly classify lower-value/overlapping plugins**

`dsh-routing-suite` is behavioral task-style guidance, not OpenRouter provider routing, so it is low priority beside Kitty's own profiles. `dsh-automation` is rejected by default where it duplicates Kitty Automations/Builder scheduling. Alpha-only agent-team plugins stay experimental until they beat bounded DSH subagents on real Kitty work.

- [ ] **Step 4: Verify each plugin independently before composing them**

For every plugin run boot, one happy path, one unavailable/degraded path, restart/replay where relevant, token/context overhead measurement, and uninstall/rollback. A plugin that cannot fail cleanly does not enter the combined canary.

- [ ] **Step 5: Run composition tests for plugin interactions**

Specifically test OpenViking recall + DSH compaction, OpenViking + continual-evolve duplicate context, CodeGraph + OpenViking retrieval deduplication, worktree plugin + Builder-owned worktrees, and session-health/usage overhead.

- [ ] **Step 6: Commit the plugin matrix and verifier**

```bash
pytest -q tests/test_dsh_canary_verify.py
git diff --check
git add docs/reference/DSH_PLUGIN_MATRIX.md scripts/dsh_canary_verify.py tests/test_dsh_canary_verify.py
git commit -m "docs(runtime): govern DSH plugin canaries"
```

### Task 8: Build a governed Creator/self-evolution loop

**Files:**
- Create: `docs/reference/HARNESS_EVOLUTION_POLICY.md`
- Create: `scripts/runtime_experiment.py`
- Create: `tests/test_runtime_experiment.py`
- Modify: execution-profile registry to add canary/promotion metadata

**Interfaces:**
- Consumes: execution receipts, failed attempts, repair history, cache/context telemetry, reviewer findings, and operator-nominated ideas.
- Produces: a proposed preset/plugin/profile delta plus benchmark evidence; never an unreviewed production mutation.

- [ ] **Step 1: Define the experiment contract**

Every experiment names one hypothesis, one bounded configuration delta, a frozen representative task set, incumbent/candidate profiles, cost ceiling, stopping rule, and promotion metrics.

- [ ] **Step 2: Let Creator propose, never self-promote**

Creator may inspect receipts and generate a new canary DSH preset/plugin/config. It may not modify the production DSH home, production model-role registry, Builder execution policy, or its own promotion rules.

- [ ] **Step 3: Use continual-evolve only inside this governed envelope**

If `dsh-continual-evolve` is adopted, global promotion remains approval-gated and its benchmark result becomes evidence to `runtime_experiment.py`; Kitty's code-owned promotion gate remains final authority.

- [ ] **Step 4: Require independent review of the candidate result**

The reviewer uses a distinct profile/model family where practical and receives exact configuration diff, exact task outputs, tests, cost/cache receipts, and acceptance evidence.
- [ ] **Step 5: Promote only through an explicit versioned change**

Promotion creates a normal reviewed commit changing the relevant preset/profile/plugin pin. Rollback is a previous known-good version, not an LLM-generated reverse patch.

- [ ] **Step 6: Post experiment results to `workspace_global`**

Post a concise result/handoff with hypothesis, incumbent/candidate, measured outcome, exact SHA/profile version, and next decision. The room communicates evidence; it does not schedule the work.

- [ ] **Step 7: Verify and commit**

```bash
pytest -q tests/test_runtime_experiment.py
git diff --check
git add docs/reference/HARNESS_EVOLUTION_POLICY.md scripts/runtime_experiment.py tests/test_runtime_experiment.py config/execution_profiles.json
git commit -m "feat(runtime): govern harness self-evolution"
```

### Task 9: Turn model/provider discovery into continuous value optimization

**Files:**
- Modify: `gateway/model_discovery.py`
- Modify: model evaluation/reporting modules found from CodeGraph at implementation time
- Create: `tests/test_execution_profile_evaluation.py`
- Modify: `config/model_roles.json` only through reviewed promotions

**Interfaces:**
- Consumes: current provider catalogues, prices, model capabilities, representative Kitty tasks, and execution receipts.
- Produces: candidate-vs-incumbent scorecards by execution profile, with no automatic production promotion.

- [ ] **Step 1: Evaluate combinations, not model names alone**

A candidate cell is `(model, reasoning, DSH preset, context policy, OpenRouter provider policy, cache policy, subagent policy)`. Do not attribute a harness/routing improvement solely to the model.
- [ ] **Step 2: Preserve the existing 7-day discovery cadence and no-auto-promotion rule**

Refresh candidates weekly or on operator nomination. Keep `automatic_promotion: false`; a candidate must pass the existing representative-task/repeat-window gates plus cache/context telemetry coverage.

- [ ] **Step 3: Add cost-per-accepted-outcome ranking**

Primary ranking: accepted outcomes per dollar and median time to accepted outcome, with hard floors for tool success, malformed outputs, critical regressions, and independent approval. Raw token price is diagnostic only.

- [ ] **Step 4: Add workload-specific routing experiments**

At minimum compare price-first, throughput-first, latency-first, and default tool-quality routing where meaningful. For long agent loops, include sticky-affinity/cache-first routing as a separate cell.

- [ ] **Step 5: Keep reviewer independence in the optimizer**

The evaluator cannot mark a worker profile superior using only that worker/model's self-review. Store reviewer profile/model in each scorecard and flag same-family review.

- [ ] **Step 6: Commit evaluation changes after fixture and matched-run proof**

```bash
pytest -q tests/test_execution_profile_evaluation.py tests/test_model_discovery.py
git diff --check
git commit -am "feat(models): optimize execution profiles by accepted outcome"
```

### Task 10: Add one unified execution receipt and operator report

**Files:**
- Extend: `scripts/kb_effectiveness.py` or the existing canonical execution-receipt owner after collision review
- Create/modify tests adjacent to that owner
- Create: `docs/reference/EXECUTION_EFFICIENCY_METRICS.md`

**Interfaces:**
- Consumes: Builder/interactive owner, execution-profile digest, DSH session/run id, OpenRouter usage, CodeGraph receipt, OpenViking receipt, reviewer evidence.
- Produces: append-only evidence sufficient to explain where money/time/context went for one accepted or failed outcome.
- [ ] **Step 1: Extend receipts without creating a second telemetry authority**

Prefer the existing KB-effectiveness/governor receipts. Add fields only where necessary: execution-profile id/digest, DSH preset/session, OpenRouter resolved route, cache read/write/discount, CodeGraph context stats, OpenViking context stats, and reviewer profile.

- [ ] **Step 2: Preserve measurement honesty**

Unknown provider cost/cache fields remain `null`; estimates are separately labeled. Never replace unknown with zero. Identical accepted result IDs must not be double-counted across interactive and Builder ownership.

- [ ] **Step 3: Produce a compact efficiency report**

Report by profile/task class: accepted outcome rate, first-pass approval, attempts, regressions, cost/accepted outcome, time/accepted outcome, cache-hit ratio, semantic-context usefulness/staleness, CodeGraph raw-read reduction, and reviewer spend.

- [ ] **Step 4: Add a waste report**

Explicitly surface repeated stable-prefix spend with no cache hit, provider drift, repeated reconnaissance, duplicate semantic context, overqualified model use, reviewer reruns, failed free-model roulette, and contexts retrieved but never used.

- [ ] **Step 5: Verify hash-chain/idempotency invariants still hold**

```bash
pytest -q tests/test_kb_effectiveness.py tests/test_session_end_audit.py
git diff --check
git commit -am "feat(metrics): measure agent execution efficiency"
```

### Task 11: Retire duplicated execution/context paths only after parity

**Files:**
- Exact deletion/cleanup files are determined from live dependency graphs at this phase; no pre-authorized deletion list.
- Update: ADR/status/reference docs that still name retired authorities.

**Interfaces:**
- Consumes: promotion evidence from Tasks 1-10.
- Produces: simplified runtime with explicit rollback artifacts/backups and no duplicate active authority.

- [ ] **Step 1: Retire OpenCode Builder execution after DSH parity**

Require a meaningful sample of real Builder packets through DSH, independent review, recovery/failure cases, explicit-free proof, and no critical regression. Preserve one tagged/committed rollback point; then delete or archive OpenCode-only adapter/config paths proven unused.
