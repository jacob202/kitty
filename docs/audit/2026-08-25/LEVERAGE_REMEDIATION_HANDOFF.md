# Kitty Leverage Remediation Handoff — 2026-08-25

## Branch

`perf/due-diligence-leverage-pack`

Base: `main` at `129c5468774aba0c4df1bff48763f1b19f2d9cc8`

The branch is intentionally not merged into `main`. Local/runtime verification is still required.

## Completed by this agent

### 1. Durable lifecycle recovery N+1 removed

Target: `gateway/chat_lifecycle.py`

`list_conversation()` previously fetched the conversation and turns, then called `get_turn()` once per turn. Each `get_turn()` opened its own SQLite connection and queried the turn, attempts, and messages.

The implementation now fetches the conversation, all turns, all attempts, and all messages using a bounded set of queries and groups the rows in Python.

Expected query shape changed from approximately O(turns) database round trips to a fixed four-table read pattern.

### 2. Artifact recovery N+1 removed

Targets:
- `gateway/artifact_store.py`
- `gateway/routes/chats.py`

Added `artifact_store.get_artifacts()` with chunks of 500 IDs, then changed chat message recovery to collect artifact IDs first and resolve them with a batched lookup instead of calling `get_artifact()` for every attachment.

### 3. Regression test added

Target: `tests/test_chat_lifecycle.py`

The new test creates two turns, monkeypatches `get_turn()` to fail, and verifies `list_conversation()` still reconstructs both turns, messages, and attempts. This specifically protects against reintroducing the lifecycle N+1 implementation.

### 4. Coverage configuration drift removed

Target: `pyproject.toml`

Changed `[tool.coverage.report] fail_under` from `10` to `73`, matching the CI merge gate. Local and CI coverage now have the same floor.

### 5. Trivial-chat memory fast path implemented

Targets:
- `gateway/context_assembler.py`
- `tests/test_context_assembler_trivial_fast_path.py`

Root cause: the existing `trivial` tier already skipped enrichments, but `assemble_context()` still constructed and queried the full `MemoryGraph` before checking the tier. This meant short/simple chats still paid the memory-store retrieval cost.

Change: `tier == "trivial"` now bypasses `MemoryGraph` construction/query, memory-policy filtering, memory rendering, and enrichments. It retains the normal base prompt/personality/user-context/skill behavior. `standard` and `deep` retain their graph retrieval path.

Regression coverage proves:
- trivial tier does not call the graph;
- trivial tier has no memory/live blocks/injected memory;
- standard tier still uses graph retrieval.

This is expected to reduce latency and failure surface for the class of requests Kitty has already classified as trivial. Exact wall-clock improvement still needs runtime measurement.

## Existing user-visible remediation already implemented in open PRs — do NOT duplicate

These are separate active branches/PRs discovered during handoff review. They should be reviewed/merged or corrected rather than rebuilt on this branch.

### PR #656 — Builder conversation continuity

`feat(chat): teach Kitty when to offer a Builder proposal`

Adds the missing persona/domain trigger for Builder proposals and persists approved Builder mission IDs so a reloaded chat can resume the durable Builder job state.

Review target:
- `gateway/context_assembler.py`
- `gateway/kitty-chat/src/components/ChatMessage.tsx`
- `gateway/kitty-chat/src/components/builder/BuilderProposalCard.tsx`
- `gateway/kitty-chat/src/lib/gateway.ts`
- `gateway/kitty-chat/src/lib/queries.ts`

The underlying conversation -> Builder approval plumbing was already merged in PR #655. PR #656 should be evaluated as the continuity/product layer on top.

### PR #657 — Web-monitor keyword notification transition

`fix(automation): notify web-monitor keyword watches on transition, not every poll`

Fixes false notification on first keyword check and repeated notifications while a keyword remains continuously matched but page content churns.

### PR #658 — Web-monitor disable/delete race

`fix(automation): re-check watch state before dispatching a monitor notify`

Re-checks current watch state immediately before notification dispatch so a watch disabled/deleted during a long-running sweep cannot still fire.

### PR #649 — ActionQueue crash recovery

`fix(automation): reconcile ActionQueue rows stranded in executing at startup`

Moves actions stranded in `executing` at process restart to an explicit terminal `unknown` state rather than silently leaving them ambiguous or blindly retrying a possibly completed external effect.

### PR #651 — Approval to terminal execution outcome

`fix(kitty-chat): drive approval to a real terminal outcome, show payload`

Chains approve -> execute in the native action surface, renders material payload arguments before approval, and displays the actual terminal result/failure rather than leaving the user with an `approved` action that never visibly finishes.

## Verification still required

This agent can modify and inspect the GitHub repository but cannot execute the repository's Python/Node environment on the user's machine from this workflow.

Run from a clean checkout of the branch:

```bash
python -m pytest tests/test_context_assembler_trivial_fast_path.py tests/test_context_assembler.py tests/test_chat_lifecycle.py -q
python -m pytest tests/ -q --tb=short --cov=gateway --cov-report=term-missing --cov-fail-under=73
ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
```

Then:

```bash
git diff --check
git status --short --branch
```

Frontend/browser verification remains:

```bash
cd gateway/kitty-chat
npm ci
./node_modules/.bin/vitest run
node node_modules/next/dist/bin/next build
npx playwright test
```

A draft verification PR for this branch is open as **#659**: `perf(context): skip memory retrieval for trivial chats`.

## Outstanding high-leverage work

### Security/dependency gates — NOT completed

Reason: the repository's `pip-audit`, Bandit, deptry, and frontend `npm audit` checks are currently advisory, and the current nightly workflow documents 65 deptry findings as of 2026-07-15. The actual current findings were not executable from this agent's environment.

Required context:
1. Run `pip-audit` on the current branch.
2. Run `npm audit --audit-level=high` from `gateway/kitty-chat`.
3. Run `deptry .`.
4. Run `bandit -c pyproject.toml -r gateway/`.
5. Classify findings as direct/transitive, production/dev-only, and exploitable/not exploitable.
6. Remediate high/critical production issues first.
7. Only then decide which security levels should become blocking CI gates.

Do NOT blindly flip all advisory jobs to blocking.

### Chat preprocessing latency budget — NOT completed

Targets:
- `gateway/routes/completions.py`
- `gateway/context_assembler.py`
- `gateway/memory_graph.py`
- enrichment modules

Existing instrumentation already records preprocessing and TTFT. The trivial fast path is now implemented; remaining work is to add/standardize per-stage timings and establish observed p95 budgets before imposing thresholds.

Required context:
- representative production/local timing samples;
- current p50/p95 for memory retrieval, enrichment, total preprocessing, and TTFT;
- request volume/typical conversation sizes.

### Structured observability — NOT completed

Targets:
- `gateway/app.py`
- `gateway/routes/completions.py`
- logging configuration

Existing correlation IDs and latency fields should be preserved. The remaining improvement is to emit a consistent machine-readable event schema rather than adding a new observability framework.

Required context:
- actual deployment log sink/collector;
- desired aggregation/dashboard destination;
- representative current logs.

### Health endpoint split/caching — NOT completed

`/health` performs a live LiteLLM readiness request with a short timeout. Before changing it, measure polling frequency and determine whether callers need liveness, readiness, or dependency health semantics.

Required context:
- health endpoint call frequency;
- deployment/orchestrator health-check configuration;
- whether `/health` is consumed by the frontend, launchd, Docker, Kubernetes, or another supervisor.

## Important architectural conclusion

Do not begin a broad rewrite. The current architecture already has useful seams around lifecycle persistence, context assembly, artifacts, and provider dispatch. The highest-leverage work is to make those seams cheaper and measurable while avoiding duplicate implementations of the active PRs listed above.
