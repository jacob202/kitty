# External Architecture & Upstream Adoption — 2026-07-14

**Status:** Permanent engineering reference
**Scope:** External ecosystem only — no Kitty code modifications
**Based on:** Internal audit `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md`

---

## 1. Engineering Landscape

The ecosystem is divided into 14 functional domains, each containing 3–8 serious candidates:

### Domain I — Agent Orchestration & Coding Agents
Projects that schedule, execute, and recover agent work: Temporal, Hatchet, DBOS, Prefect, Inngest, Trigger.dev, Aider, OpenCode, Codex CLI.

### Domain II — Repository Knowledge & Code Intelligence
Projects that index, search, and model codebases: Sourcegraph, tree-sitter, ast-grep, Aider repomap, codegraph, LlamaIndex, LangChain.

### Domain III — Agent Instructions & Skills
Projects and standards for portable agent guidance: SKILL.md convention, MCP (Model Context Protocol), A2A (Agent-to-Agent), OpenAPI tool descriptions.

### Domain IV — Prompt Routing & Context Engineering
Projects that route, assemble, and optimize LLM context: LiteLLM, OpenRouter, Portkey, DSPy, RAG patterns, reranker libraries.

### Domain V — Evaluation & Benchmarking
Projects that measure LLM/code quality: LangSmith, Braintrust, Ragas, DeepEval, SWE-bench, HumanEval, aider polyglot leaderboard.

### Domain VI — Observability, Telemetry & Tracing
Projects that record and surface LLM/system behavior: OpenTelemetry, LangFuse, Helicone, Arize Phoenix, Prometheus, Grafana.

### Domain VII — Sandbox & Command Execution
Projects that isolate agent execution: Docker, Firecracker, gVisor, E2B, Daytona, Modal, Fly Machines.

### Domain VIII — Durable Workflows, Queues & State Machines
Projects that model long-running processes: Temporal (workflows), Hatchet (durable tasks), Celery (task queues), BullMQ, XState, River (Go queue).

### Domain IX — CI, Release & Repository Hygiene
Projects that automate builds, checks, and releases: GitHub Actions, Earthly, Dagger, Nix, vulture, trufflehog, lychee, deptry, pre-commit.

### Domain X — Documentation & ADR Tooling
Projects that validate and maintain documentation: lychee, markdown-link-check, vale, Structurizr, adr-tools, log4brains.

### Domain XI — Development Environments & Reproducibility
Projects that make environments consistent: Nix, devenv, devcontainers, mise, flox, uv, pixi.

### Domain XII — Browser Testing & Accessibility
Projects that test UIs: Playwright, Puppeteer, Cypress, axe-core, Lighthouse, Browserbase.

### Domain XIII — Model Routing & Provider Abstraction
Projects that abstract LLM provider access: LiteLLM, OpenRouter, Portkey, Martian, Helicone gateway, LangChain model I/O.

### Domain XIV — Knowledge Graphs & Semantic Retrieval
Projects that structure and query knowledge: Neo4j, Kuzu, CozoDB, Microsoft graphrag, mem0 (already in Kitty).

---

## 2. Best Repository By Lane

Each lane has ONE best project — the one Kitty should study first. Runner-up listed for comparison.

| Lane | Best | Verdict | Runner-up |
|---|---|---|---|
| Agent orchestration | **Hatchet** (7.5k stars, MIT, Go+Python+TS) | Closest match to KittyBuilder's use case: durable tasks with retries, leasing, and Postgres durability. API design is the most relevant reference. | Temporal (21.7k stars, MIT) — canonical durable execution, but too heavy |
| Coding agents | **Aider** (47.4k stars, Apache 2.0, Python) | Repomap generation, git-native workflow, automated commit messages. KittyBuilder should study their codebase map approach. | OpenCode — Kitty already uses it as a worker |
| Repo knowledge | **tree-sitter** (MIT, C) | Universal incremental parser. Powers ast-grep, Aider repomap, and most modern code tools. The substrate, not the product. | Sourcegraph — too enterprise, too heavy |
| Semantic indexing | **LlamaIndex** (50.9k stars, MIT, Python) | Mature RAG framework. Kitty's memory_graph is a simpler, more opinionated version of the same concept. Worth studying their ingestion pipeline patterns. | ChromaDB — already in Kitty |
| Knowledge graphs | **Kuzu** (MIT, C++) | Embeddable graph DB with Cypher-like queries. Much lighter than Neo4j. Could power a more sophisticated repository knowledge model. | Neo4j — too heavy |
| Agent instructions | **MCP (Model Context Protocol)** | Anthropic's open standard for tool/skill descriptions. `SKILL.md` convention is a lighter-weight de facto standard. Kitty should track MCP vs SKILL.md convergence. | A2A (Google) — cross-agent protocol, different layer |
| Prompt routing | **LiteLLM** (MIT, Python) | Already in Kitty. Industry standard for provider abstraction. No alternative needed. | OpenRouter — used as fallback, complementary |
| Context engineering | **DSPy** (MIT, Python) | Programmatic prompt optimization. Kitty's context_assembler is hand-tuned; DSPy could optimize it automatically. Reference, not replacement. | LangChain — too heavy, too abstract |
| Evaluation | **Braintrust** (MIT, TS/Python) | Eval framework with strong dataset management. Best fit for KittyBench design. | Ragas — RAG-specific, narrower |
| Observability | **LangFuse** (MIT, TS/Python) | Open-source LLM tracing. Kitty's observability.py is a minimal JSONL approach; LangFuse is the mature reference. | Helicone — API-level, cloud-first |
| Sandbox execution | **E2B** (Apache 2.0, TS/Python) | Purpose-built for AI agent code execution. KittyBuilder worktrees + free workers solve this differently. | Docker — universal but heavy |
| Durable workflows | **Hatchet** | (See above — same as orchestration lane) | DBOS — Postgres-native, promising but younger |
| CI/Release | **Dagger** (Apache 2.0, Go) | Programmable CI/CD. Kitty's GitHub Actions workflows are standard; Dagger would make them portable. Reference only — not worth migration. | Earthly — Makefile-compatible build system |
| Dead code detection | **vulture** (MIT, Python) | Zero-config Python dead code scanner. Immediate adoption candidate. | Pylyzer (via ruff) — broader static analysis |
| Secrets detection | **trufflehog** (AGPL, Go) | Most comprehensive open-source secret scanner. Kitty's pre-commit `detect-private-key` is minimal. | gitleaks (MIT, Go) — lighter but less thorough |
| Doc validation | **lychee** (MIT/Apache 2.0, Rust) | Fast link checker. Immediate adoption candidate for Kitty's 37+ docs. | vale — prose linter, complementary |
| ADR tooling | **adr-tools** (MIT, Shell) | Standard ADR CLI. Kitty already has a good ADR practice (16 ADRs). adr-tools would add automated numbering/linking. | log4brains — heavier, more structure |
| Dev environments | **Nix** (MIT, C++) | Reproducible builds and dev shells. Highest engineering quality of any reproducibility tool. Overkill for Kitty's simple requirements.txt + venv setup. | mise — lighter, per-project tool version manager |
| Browser testing | **Playwright** (Apache 2.0, TS) | Already in Kitty's CI. Industry standard. Keep. | Browserbase — cloud Playwright, useful if smoke tests scale |
| Model routing | **LiteLLM** | (See above — same as prompt routing lane) | Portkey — more observability features, but LiteLLM is sufficient |
| Semantic retrieval | **mem0** | Already in Kitty. Memory layer with personalization. | LlamaIndex (for RAG patterns, not adoption) |

---

## 3. Hidden Gems

Technically excellent, underappreciated projects highly relevant to Kitty:

| Project | Stars | What It Is | Why It Matters to Kitty |
|---|---|---|---|
| **Kuzu** | ~4k | Embeddable graph database (C++, Python bindings) | Could replace hand-rolled entity relationships in memory_graph with a proper property graph. Cypher-like queries. Single-file embedded DB — fits Kitty's local-first model perfectly. |
| **DBOS** | ~6k | Durable execution on Postgres — no separate server needed | Simpler than Temporal. Workflows as TypeScript/Python decorators. Postgres-native durability. Worth studying for their "why no separate orchestrator" design. |
| **River** (Go) | ~5k | Fast Postgres-backed job queue for Go | Reference for KittyBuilder's queue design. Clean API: `Client.Insert()`, worker middleware, unique jobs, periodic jobs. The "one queue, no separate broker" philosophy matches Kitty. |
| **Dagger** | ~13k | Programmable CI/CD as code, engine runs anywhere | If Kitty ever needs portable CI beyond GitHub Actions, Dagger is the answer. Containers-as-functions model is elegant. |
| **Earthly** | ~12k | Makefile + Dockerfile combined, reproducible builds | Better than Make for complex build pipelines. Kitty could replace `Makefile` with `Earthfile` for cross-platform CI. |
| **mise** | ~15k | Per-project tool version manager (replaces asdf/pyenv/nvm) | Single `.mise.toml` to pin Python, Node, and tool versions. Would make Kitty's dev setup simpler than current `requirements.txt` + `package.json` + manual tool docs. |
| **uv** | ~45k | Ultra-fast Python package installer and resolver (Rust) | 10-100x faster than pip. Already well-known but underappreciated in project setup docs. Would make Kitty's `pip install -r requirements.txt` nearly instant. |
| **vale** | ~5k | Prose linter with custom style rules | Could enforce Kitty's documentation voice and terminology ("the gateway", "Phase B", etc.) as lint rules. Prevents doc drift. |
| **deptry** | ~1.5k | Dependency checker — finds unused and missing deps | Finds dependencies in `requirements.txt` that are never imported, and imports that are missing from `requirements.txt`. Directly addresses the "dependencies barely used" audit finding. |
| **ast-grep** | ~8k | Structural code search with AST patterns | Already referenced in Kitty's skills. Much more powerful than grep for codebase analysis. The YAML rule format is easy to learn. |

---

## 4. Adoption Candidates

Projects Kitty should *actually adopt* (not just reference). Each has low adoption cost and directly addresses a confirmed weakness:

| # | Project | Lane | What It Replaces | Adoption Cost | Annual Maintenance |
|---|---|---|---|---|---|
| 1 | **vulture** | Dead code detection | Manual dead code hunting | `pip install vulture` + CI job (30min) | Near zero — runs in CI |
| 2 | **lychee** | Doc validation | Broken links in 37+ docs | `brew install lychee` or Docker + CI job (30min) | Near zero |
| 3 | **trufflehog** | Secrets detection | Pre-commit `detect-private-key` only | `brew install trufflehog` + pre-commit hook (30min) | Low — occasional false positives |
| 4 | **deptry** | Dependency analysis | Unknown unused deps | `pip install deptry` + CI job (30min) | Near zero |
| 5 | **vale** | Documentation style | Inconsistent doc terminology | `brew install vale` + `.vale.ini` (1hr, custom rules) | Low — rule maintenance if terminology changes |
| 6 | **uv** | Package management | pip (10-100x slower) | `pip install uv` + update commands (30min) | Near zero — drop-in pip replacement |
| 7 | **mise** | Dev environment | Manual Python/Node version docs | `.mise.toml` file + install docs (1hr) | Low |
| 8 | **adr-tools** | ADR tooling | Hand-numbered ADRs | `brew install adr-tools` (15min) | Near zero |

---

## 5. Prototype Candidates (max 10)

Ranked by expected durable value to Kitty. Each has a clear success metric and rollback strategy.

| # | Candidate | Hypothesis | Installation Effort | Integration Risk | Architectural Overlap | Expected Payoff |
|---|---|---|---|---|---|---|
| 1 | **vulture** | Finds 5+ dead code items in `gateway/` beyond known cases | `pip install` | None — read-only check | None | High — prevents dead code accumulation |
| 2 | **lychee** | Finds 5+ broken links in `docs/` | `brew install` or Docker | None — read-only check | None | High — prevents documentation drift |
| 3 | **deptry** | Finds unused deps in `requirements.txt` | `pip install` | None — read-only check | None | Medium — cleans dependency list |
| 4 | **Aider repomap** (study) | Aider's codebase map generation outperforms handwritten `codemap/` docs for LLM context | Read source only, no install | None — reference only | Overlaps with codegraph + codemap | High — better repo context for agents |
| 5 | **Hatchet** (study) | Hatchet's durable task API model is the closest reference for KittyBuilder's queue improvement | Read docs/source | None — reference only | Overlaps with builder_queue.py | High — concrete API improvement patterns |
| 6 | **vale** | Enforces "the gateway" / "Phase B" / voice terminology in docs | `brew install vale` | Low — custom rules needed | None — doc-only | Medium — documentation consistency |
| 7 | **Kuzu** (study) | Embedded graph DB could simplify memory_graph entity modeling | Read docs, no install | High — could replace memory_graph internals | Overlaps with memory_graph.py | Medium — simpler entity relationships |
| 8 | **DSPy** (study) | Programmatic prompt optimization could improve context_assembler output quality | `pip install dspy-ai` | Medium — changes prompt engineering workflow | Overlaps with context_assembler.py | Medium — better LLM outputs |
| 9 | **Braintrust** (study) | Eval framework is the best fit for KittyBench design | `pip install braintrust` | Low — eval-only, no prod changes | None — eval harness | Medium — regression prevention |
| 10 | **uv** | Replaces pip with 10-100x speedup, zero config | `pip install uv` | Very low — drop-in replacement | None — package management | Low — dev experience improvement |

**Prototypes 1–5 should be run this cycle.** Prototypes 6–10 are lower urgency.

---

## 6. Benchmark Candidates

Projects Kitty should benchmark *against* — not adopt, but measure its own quality against:

| Project | What to Measure | Why |
|---|---|---|
| **Aider polyglot benchmark** | Code editing accuracy on real tasks | KittyBuilder's packet execution success rate on equivalent tasks |
| **SWE-bench Verified** | Bug-fixing capability on real GitHub issues | KittyBuilder's ability to fix bugs from issues |
| **HumanEval / MBPP** | Code generation correctness | Baseline comparison for Builder's code generation |
| **Braintrust eval datasets** | Structured eval methodology | Pattern for KittyBench fixture design |
| **Hatchet vs Temporal benchmark** | Durable execution throughput/latency | Compare KittyBuilder queue performance to mature systems |

---

## 7. Reference Implementations

Projects whose *source code* Kitty engineers should study — not adopt wholesale:

| Project | What to Study | Specific Files/Modules |
|---|---|---|
| **Hatchet** | Task lifecycle, lease management, retry policies, heartbeat pattern | `internal/services/controllers/jobs/`, `pkg/client/` |
| **Aider** | Repomap generation, git integration, code context for LLMs | `aider/repomap.py`, `aider/coders/` |
| **temporalio/temporal** | Workflow determinism, replay, activity heartbeating | `service/history/`, `temporal/` |
| **langfuse** | LLM trace schema, span modeling, OpenTelemetry integration | `packages/tracing/`, `web/src/` |
| **DSPy** | Programmatic prompt optimization, signature-based prompting | `dspy/primitives/`, `dspy/teleprompt/` |
| **River** (Go) | Clean queue API design, unique jobs, periodic jobs, middleware | `river/`, `rivertype/` |
| **Playwright** | Browser automation architecture, selector engine, trace viewer | `packages/playwright-core/` |
| **E2B** | Sandbox lifecycle, file system isolation, process management | `packages/python-sdk/`, `spec/` |
| **Dagger** | Containerized pipeline execution, caching, module system | `core/`, `sdk/python/` |
| **ast-grep** | AST pattern matching, rule-based code search | `crates/core/`, `crates/config/` |

---

## 8. Never Build Again Registry

Systems Kitty should never build from scratch. For each, the mature upstream alternative and the evidence for not building:

| # | System | Why Never Build | Mature Alternative | Evidence |
|---|---|---|---|---|
| 1 | **Dead code detector** | Solved problem with zero-config tools | vulture (Python), deadcode (Go), ts-prune (TS) | Thousands of projects use these; building your own adds maintenance for zero unique value |
| 2 | **Secret scanner** | High-stakes, well-solved, requires constant signature updates | trufflehog (universal), gitleaks (lightweight) | GitHub's secret scanning partnership; trufflehog has 800+ detectors maintained by a dedicated team |
| 3 | **Markdown link checker** | Solved problem, boring infrastructure | lychee (Rust, fast), markdown-link-check (Node) | lychee checks 1000s of links/second; Kitty has 37+ docs — building a checker is wasted engineering |
| 4 | **Tracing standard** | Industry has converged on OpenTelemetry | OpenTelemetry | CNCF graduated project; every major observability vendor supports it; building a custom tracing protocol ensures incompatibility |
| 5 | **Dependency analyzer** | Solved problem, complex edge cases | deptry (Python), cargo-deny (Rust), depcheck (Node) | deptry handles namespace packages, optional deps, dev deps, and type stubs correctly — non-trivial to reimplement |
| 6 | **Container orchestration** | Extremely complex, well-solved by Kubernetes/Nomad | Docker Compose (local), Kubernetes (prod) | Kitty is single-user local; Docker Compose is the right level. Building even a minimal orchestrator is a multi-year project |
| 7 | **Workflow engine** | Durable execution has deep edge cases (replay, determinism, clock synchronization) | Hatchet (light), Temporal (heavy), DBOS (Postgres-native) | KittyBuilder queue is a good lightweight implementation for local use. For anything beyond, adopt — don't build |
| 8 | **Graph database** | Property graph engines have decades of optimization | Kuzu (embedded), Neo4j (server), CozoDB (Datalog) | Building a graph engine is a PhD-level project. Kuzu is embeddable and fits Kitty's local-first model |
| 9 | **Code formatter** | Community has standardized on a few tools | ruff format (Python), prettier (JS/TS), biome (JS/TS) | Formatter wars are over. Adding your own ensures nobody else can contribute formatting rules |
| 10 | **Release automation** | Solved by every CI platform | GitHub Releases + Actions, semantic-release, changesets | Rolling your own release system is a sure path to maintenance hell |

---

## 9. Strategic Ownership Registry

Systems Kitty SHOULD own forever — these are Kitty's unique value and should not be outsourced:

| # | System | Why Kitty Must Own It | Current Implementation | Risk if Outsourced |
|---|---|---|---|---|
| 1 | **Builder packet lifecycle** | The packet format (objective, allowed paths, acceptance criteria, validation) is Kitty's unique delegation contract. No external tool models this. | `docs/packets/TEMPLATE.md`, `builder_initiative.py` | Loss of the packeting contract; delegation becomes generic task execution |
| 2 | **Initiative model** | Initiatives (ordered sequence of packets with shared context) are Kitty's project model. External task systems don't model packet dependencies and initiative-level validation. | `builder_initiative.py`, `docs/initiatives/*.json` | Initiatives become unstructured task lists; packet ordering and dependency tracking is lost |
| 3 | **Reasoning policy engine** | The OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN loop is Kitty's agent reasoning model. No external framework implements this exact loop with phase detection and step recording. | `agent_runner.py:54-83` | Agents lose structured reasoning phases; step recording becomes ad hoc |
| 4 | **Repository knowledge model** | Kitty's knowledge model combines codegraph (structural), codemap (conceptual), ADRs (decisions), and packet context (tasks) into one coherent agent view. This integration is unique. | `memory_graph.py`, codegraph, codemap, ADRs | Each knowledge source becomes siloed; agents can't cross-reference code structure with architectural decisions and active tasks |
| 5 | **Evidence ledger** | Every Builder attempt records SHA-256 proofs, exit codes, and structured contracts. The evidence chain (attempt → review → publish) is Kitty's trust model. | `builder_attempt.py`, `builder_loop.py`, run manifests | Trust model collapses; "reviewed and approved" becomes a boolean flag with no proof |
| 6 | **Durable attempts** | Each attempt is an isolated worktree with its own context bundle, keeping partial work inspectable. The attempt/retry model with explicit budget and evidence is Kitty's. | `builder_attempt.py`, `builder_loop.py` | Retries become blind; inspectability of partial work is lost |
| 7 | **Lease semantics** | KittyBuilder's lease model (claim→heartbeat→expire→recover) with SHA-256 verification and branch lease enforcement. The specific lease fencing rules are Kitty's concurrency model. | `builder_queue.py` lease functions, `builder_runner.py` heartbeat | Concurrency model becomes generic; Kitty-specific lease fencing (branch leases, attempt isolation) is lost |
| 8 | **Privacy boundary** | D10 privacy boundary in `llm_client.py` — content classes that must never leave the local machine. No external router can enforce Kitty's specific privacy classifications. | `llm_client.py:36-59` | Privacy model becomes generic; Kitty-specific content classes (journal, mail_body, health_admin) lose protection |
| 9 | **Soul / voice / persona** | Kitty's personality (four internal parts: Skeptic, Champion, Pragmatist, Observer) is its defining user experience. This must stay in-house. | `config/SOUL.md`, `voice_gate.py`, `self_review.py` | Voice becomes generic AI assistant; the "Kitty feel" that defines the product is lost |
| 10 | **Life-first ordering** | The ordering algorithm that prioritizes life projects over code projects (ADR 0016) is Kitty's product North Star. No external scheduler knows Jacob's priorities. | `next_step.py`, `builder_initiative.py` (life-first-v1) | Prioritization becomes generic; the defining product experience ("one concrete life move every morning") is lost |

---

## 10. External Comparison Matrix

Subsystem-by-subsystem comparison of Kitty vs the best external project:

| Kitty Subsystem | Kitty Implementation | Best External | Kitty Wins On | External Wins On | Verdict |
|---|---|---|---|---|---|
| **Builder queue** | SQLite state machine, lease fencing, branch leases | Hatchet (Postgres, durable tasks) | Zero-dependency, local-first, SHA-256 integrity | Multi-worker, observability, retry policies, web UI | **Keep Kitty, study Hatchet API patterns** |
| **Worker execution** | Isolated git worktrees, heartbeat lease, subprocess | E2B (container sandboxes) | Git-native, no Docker dependency, inspectable worktrees | Process isolation, network control, file system isolation | **Keep Kitty** — worktree model is simpler and git-native |
| **Memory/context** | memory_graph → context_assembler unified read | LlamaIndex (RAG framework) | Unified read path, single Item shape, fail-loud partial results | RAG patterns, advanced retrievers, reranking | **Keep Kitty** — simpler, more opinionated, fit-for-purpose |
| **LLM routing** | LiteLLM proxy + table-driven fallback | LiteLLM (same) | D10 privacy boundary, table-driven extensibility | Built-in observability, caching | **Keep Kitty** — privacy boundary is the differentiator |
| **Prompt assembly** | context_assembler 10-step pipeline | DSPy (programmatic optimization) | Deterministic, traceable, hand-tuned for Jacob | Automatic optimization, few-shot example selection | **Study DSPy** as complement — auto-optimize, don't replace |
| **Agent reasoning** | OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN | No direct equivalent — most agents use simpler loops | Structured phases, phase detection, step recording | — | **Keep Kitty, document for external reference** |
| **Code knowledge** | codegraph + codemap + tree-sitter (ast-grep) | Aider repomap + tree-sitter | Multi-layer (structural + conceptual + decision) | LLM-optimized context generation | **Study Aider repomap** for LLM context optimization |
| **Skills/instructions** | SKILL.md files in multiple locations | SKILL.md (de facto) + MCP (standard) | Rich skill ecosystem (25+ skills) | Portable standard, tool discovery protocol | **Track MCP convergence**, keep SKILL.md |
| **Evaluation** | Test suite (2036 tests) + builder validation | Braintrust (eval framework) | Large test coverage, builder-specific validation | Structured eval datasets, comparison UI, regression tracking | **Study Braintrust** for KittyBench design |
| **Observability** | observability.py (JSONL) + token_usage_log | LangFuse (LLM tracing) | Minimal, zero-dependency, already collecting data | Rich UI, span-level tracing, OpenTelemetry support | **Keep Kitty**, wire JSONL data into `./kitty doctor --spend` |
| **CI** | GitHub Actions (5 jobs) + pre-commit | GitHub Actions (standard) | Comprehensive gates (pytest, lint, typecheck, UI, smoke) | — | **Keep Kitty**, add vulture/lychee/deptry |
| **Documentation** | 37+ docs, 16 ADRs, 23 packets | adr-tools + vale + lychee | Rich content, multi-audience docs | Automated link checking, ADR numbering, prose linting | **Adopt tooling**, keep content |
| **Secrets** | Pre-commit `detect-private-key` | trufflehog (800+ detectors) | Simple, zero-false-positive | Comprehensive, team-maintained detectors | **Adopt trufflehog** |
| **Code quality** | ruff (E/F/W/I rules) | ruff (standard) | Deliberate minimal ruleset (D8) | Broader rule sets available | **Keep Kitty's ruleset** — deliberate decision |

---

## 11. Top 25 Repositories Every Kitty Engineer Should Know

Ranked by relevance to Kitty's architecture. Study them before building anything new.

1. **hatchet-dev/hatchet** — Durable task orchestration (7.5k stars, MIT, Go+Python+TS). Closest reference for KittyBuilder queue improvement.
2. **Aider-AI/aider** — AI pair programming with repomap (47.4k stars, Apache 2.0, Python). Codebase map generation for LLM context.
3. **temporalio/temporal** — Durable execution platform (21.7k stars, MIT, Go). Canonical workflow engine. Study for patterns, not adoption.
4. **tree-sitter/tree-sitter** — Incremental parsing library (MIT, C). Powers all modern code analysis tools.
5. **ast-grep/ast-grep** — Structural code search (8k stars, MIT, Rust). AST-based codebase queries.
6. **BerriAI/litellm** — LLM proxy and router (MIT, Python). Already in Kitty. Study for routing patterns.
7. **langfuse/langfuse** — LLM tracing and observability (MIT, TS+Python). Reference for Kitty's observability surface.
8. **run-llama/llama_index** — RAG framework (50.9k stars, MIT, Python). Reference for memory_graph patterns.
9. **kuzudb/kuzu** — Embeddable graph database (MIT, C++). Potential memory_graph enhancement.
10. **e2b-dev/e2b** — AI agent sandboxes (Apache 2.0, TS+Python). Reference for worker isolation.
11. **dagger/dagger** — Programmable CI/CD (Apache 2.0, Go). Reference if CI becomes portable.
12. **jendrikseipp/vulture** — Dead code detection (MIT, Python). Adoption candidate.
13. **lycheeverse/lychee** — Link checker (MIT/Apache 2.0, Rust). Adoption candidate.
14. **trufflesecurity/trufflehog** — Secret scanning (AGPL, Go). Adoption candidate.
15. **fpgmaas/deptry** — Dependency checker (MIT, Python). Adoption candidate.
16. **microsoft/playwright** — Browser automation (Apache 2.0, TS). Already in Kitty CI.
17. **stanfordnlp/dspy** — Programmatic prompt optimization (MIT, Python). Reference for context assembler.
18. **braintrustdata/braintrust** — Eval framework (MIT, TS+Python). Reference for KittyBench.
19. **dbos-inc/dbos-transact** — Postgres-native durable execution (MIT, TS+Python). Reference for queue design.
20. **riverqueue/river** — Postgres job queue (MIT, Go). Clean queue API reference.
21. **errata-ai/vale** — Prose linter (MIT, Go). Adoption candidate for doc consistency.
22. **joelparkerhenderson/architecture-decision-record** — ADR specification. Reference for ADR practice.
23. **nat-n/poethepoet** — Task runner for Python projects (MIT, Python). Reference for Makefile replacement.
24. **astral-sh/uv** — Fast Python package installer (MIT, Rust). Adoption candidate.
25. **jdx/mise** — Dev tool version manager (MIT, Rust). Adoption candidate.

---

## 12. Five-Year Outlook

### Major architectural themes converging across the ecosystem

1. **Local-first durable execution is becoming mainstream.** Temporal and Hatchet proved durable execution works. The next wave (DBOS, River, Inngest) is making it simpler: Postgres-native, single-binary, fewer concepts. KittyBuilder's SQLite queue is already on this trajectory — ahead of the curve for single-user local use.

2. **Agent instructions are standardizing around SKILL.md and MCP.** The de facto standard is SKILL.md (markdown files with frontmatter). MCP is the formal protocol from Anthropic. Kitty should keep SKILL.md and track MCP. When MCP tooling matures (likely 2026-2027), migrate skill definitions to MCP format for interoperability.

3. **Repository knowledge graphs are the next frontier.** codegraph, Aider repomap, and Sourcegraph Cody all solve the same problem: give agents a structured view of the codebase. The winner will likely be tree-sitter + graph layer (Kuzu-style). Kitty's multi-layer approach (codegraph + codemap + ADRs + packets) is unique and worth preserving.

4. **Prompt engineering is becoming programmatic.** DSPy, TextGrad, and similar frameworks treat prompts as optimizable programs. Hand-tuned prompts (Kitty's current approach) will be supplemented or replaced by auto-optimized prompts. Kitty should not fight this — `context_assembler.py` could use DSPy-style optimization as a post-processing layer.

5. **LLM observability is converging on OpenTelemetry.** LangFuse, Phoenix, and Helicone all support OpenTelemetry traces. Kitty's JSONL approach is fine for now, but emitting OTel spans would enable using any observability backend. This is a "do it when you need it" migration — not urgent.

6. **Agent sandboxing is bifurcating.** Cloud sandboxes (E2B, Daytona, Modal) vs local sandboxes (Docker, Firecracker, gVisor). Kitty is uniquely local-first and should stay local. Git worktrees are a clever lightweight sandbox, but they don't isolate processes or networks. If Builder tasks need stronger isolation, Firecracker (via the `firecracker-containerd` or `firectl` approach) is the right path.

7. **CI/CD is becoming programmable rather than YAML.** Dagger and Earthly let you write CI in code. GitHub Actions YAML is adequate for Kitty's current 5-job pipeline. Do not migrate unless the pipeline becomes complex enough that YAML is painful.

8. **Package management is consolidating around uv and pixi.** uv (Python) and pixi (conda-forge multi-language) are replacing pip and conda. Kitty should adopt uv for speed; mise for tool version management.

### Outdated assumptions in Kitty's current architecture

| Assumption | Status | Correction |
|---|---|---|
| "npm run is broken on this machine" (CLAUDE.md) | **OUTDATED** — fixed via `.npmrc` per PROJECT_STATUS.md | Remove from CLAUDE.md |
| "honcho.py is not properly wired up" (CLAUDE.md) | **OUTDATED** — verified actively imported by kitty_tools and memory_consolidation | Remove from CLAUDE.md |
| "No kitty-chat CI job" (PROJECT_STATUS.md) | **OUTDATED** — CI has kitty-chat job since #51 | Remove from PROJECT_STATUS.md |
| Prompt domain slots exist for repair/health/research/code (prompts.py DOMAIN_TO_FILE) | **OUTDATED** — only soul_v1.md exists | Remove empty mappings |
| pip as the package manager | **OUTDATED** — uv is dramatically faster and a drop-in replacement | Consider migrating pip → uv |
| Makefile as the task runner | **ADEQUATE** — but poethepoet or Earthly would be cleaner | Monitor, migrate if complexity grows |

### Emerging standards Kitty should track

| Standard | Status | Impact on Kitty |
|---|---|---|
| **MCP (Model Context Protocol)** | Anthropic spec, growing adoption | May replace SKILL.md for skill definitions if it adds tool discovery |
| **A2A (Agent-to-Agent Protocol)** | Google spec, early stage | Could standardize how Kitty's agents communicate with external agents |
| **OpenTelemetry for LLMs** | Semantic conventions being drafted | Already supported by LangFuse, Phoenix. Kitty should plan to emit OTel spans from `observability.py` |
| **SKILL.md** | De facto convention, no formal spec | Keep using; track if a formal spec emerges |
| **Nix flakes** | Standard for reproducible builds | Overkill for Kitty's simple dependency set; mise + uv is lighter |

### Opportunities Kitty is uniquely positioned to exploit

1. **Local-first durable execution for single users.** Temporal and Hatchet are designed for multi-tenant cloud deployments. KittyBuilder's SQLite-local queue with worktree isolation is the only durable execution system designed for a single-user laptop. This is a genuine architectural innovation — document it.

2. **Evidence-led delegation.** The Builder packet → attempt → SHA-256 review → publish chain is a trust model that no other agent system implements. Every attempt is independently verifiable. This is Kitty's strongest architectural pattern — formalize it as an "evidence ledger" concept.

3. **Life-first prioritization.** No other AI companion prioritizes life tasks (job search, benefits, education) over engineering tasks. This is Kitty's product differentiator. Protect it in architecture: never let Builder optimization work crowd out life-first packet processing.

4. **Multi-layer repository knowledge.** codegraph (structural) + codemap (conceptual) + ADRs (historical decisions) + packets (active tasks) + memory_graph (runtime state) is a richer knowledge model than any single tool provides. This integration is Kitty's competitive moat for agent effectiveness.

---

## 13. Prioritized Implementation Roadmap

### Now (this week — adopt proven tools, fix stale claims)

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | Fix stale CLAUDE.md claims (npm run, honcho, kitty-chat CI) | 15m | Eliminates misleading agent guidance |
| 2 | Add vulture to CI (dead code check) | 30m | Prevents dead code accumulation |
| 3 | Add lychee to CI (broken link check) | 30m | Prevents documentation drift |
| 4 | Add deptry to CI (dependency check) | 30m | Cleans unused dependencies |
| 5 | Update PROJECT_STATUS.md branch claim and outdated entries | 15m | Single source of truth |

### Next (this month — study references, prototype)

| # | Action | Effort | Impact |
|---|---|---|---|
| 6 | Study Aider repomap for LLM context optimization | 2h (read source) | Better agent code understanding |
| 7 | Study Hatchet API for queue improvement patterns | 2h (read source + docs) | Concrete queue API improvements |
| 8 | Study Braintrust for KittyBench design | 2h (read docs) | Eval framework design |
| 9 | Study DSPy for context assembler optimization | 2h (pip install + experiment) | Better LLM outputs |
| 10 | Design KittyBench skeleton with 2 fixtures | 4h | Regression prevention |
| 11 | Wire observability.py into `./kitty doctor --spend` | 2h | LLM cost visibility |

### Later (Q3 2026 — deeper integration)

| # | Action | Effort | Impact |
|---|---|---|---|
| 12 | Evaluate Kuzu for memory_graph entity modeling | 8h (prototype) | Cleaner graph relationships |
| 13 | Add vale for documentation consistency | 4h (custom rules) | Consistent doc terminology |
| 14 | Adopt uv for package management | 1h | 10-100x faster installs |
| 15 | Formalize evidence ledger as a documented concept | 4h | Architectural clarity |
| 16 | Document local-first durable execution as architectural innovation | 4h | External visibility |

### Reject (do not adopt)

| # | Candidate | Reason |
|---|---|---|
| R1 | Temporal | Too heavy — requires Temporal server, 100MB+ Docker image. KittyBuilder's SQLite queue is simpler and fit-for-purpose. |
| R2 | LangChain | Too abstract, too heavy (700+ dependencies). Kitty's purpose-built modules are clearer. |
| R3 | Neo4j | Requires Java runtime + server. Kuzu is embeddable and fits local-first model. |
| R4 | Kubernetes | Multi-node container orchestration for a single-user local app. Docker Compose is sufficient. |
| R5 | Sourcegraph | Cloud dependency, enterprise pricing, heavy deployment. codegraph + tree-sitter serves local needs. |
| R6 | OpenTelemetry collector | Separate infrastructure for a single-user app. JSONL observability is adequate; add OTel spans when needed, not before. |
| R7 | Nix/NixOS | Powerful but steep learning curve. mise + uv achieves reproducibility with near-zero learning cost. |

---

## 14. Summary

### What Kitty should build
- Evidence ledger (formalize the attempt→review→publish chain)
- KittyBench (eval framework with real packet fixtures)
- `./kitty doctor --spend` (wire existing LLM data to CLI)

### What Kitty should adopt
- vulture, lychee, deptry, trufflehog (CI hygiene tools — zero cost, high payoff)
- uv (faster package management — drop-in pip replacement)
- vale (doc consistency — prevents terminology drift)

### What Kitty should reference
- Hatchet (queue API design — closest to KittyBuilder's model)
- Aider (repomap generation — better repo context for agents)
- DSPy (prompt optimization — complement to hand-tuned context_assembler)
- Braintrust (eval framework — pattern for KittyBench)
- Kuzu (embedded graph DB — future memory_graph enhancement)
- LangFuse (LLM tracing — reference for observability surface)

### What Kitty should benchmark against
- Aider polyglot benchmark (code editing accuracy)
- SWE-bench Verified (bug-fixing capability)

### What Kitty should never build
- Dead code detector (use vulture)
- Secret scanner (use trufflehog)
- Link checker (use lychee)
- Tracing standard (use OpenTelemetry when ready)
- Graph database (use Kuzu when needed)
- Workflow engine (use Hatchet/Temporal if queue becomes insufficient)
- Container orchestrator (use Docker Compose)
- Release system (use GitHub Actions)
- Code formatter (use ruff/prettier)

### What Kitty should own forever
- Builder packet lifecycle and initiative model
- Reasoning policy engine (OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN)
- Repository knowledge model (codegraph + codemap + ADRs + packets + memory)
- Evidence ledger (attempt→review→publish chain with SHA-256 proofs)
- Durable attempts with worktree isolation
- Lease semantics (claim→heartbeat→expire→recover)
- Privacy boundary (D10 content classification)
- Life-first ordering (ADR 0016)

---

*This report is a permanent engineering reference. Revisit quarterly (next: October 2026) to reassess the ecosystem and update adoption decisions.*
