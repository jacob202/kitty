# Token Optimization & Context Engineering: Comprehensive Research Synthesis

This research synthesizes findings from academic papers, production case studies, GitHub implementations, and provider documentation to deliver actionable principles for your Kitty project and optimizer code.

---

## 1. Core Principles from Leading Research

| Principle | Insight | Practical Action |
|-----------|---------|---------------------|
| **Minimal viable context** | Good context engineering means finding the smallest possible set of high-signal tokens that maximize desired outcomes. Not the most tokens—the *right* tokens. | Adopt **just-in-time context loading** instead of preloading everything. |
| **Context rot is real** | As tokens in the context window increase, the model's recall accuracy decreases—regardless of window size. Every new token depletes the "attention budget". | Keep only active working memory; compress or evict stale information. |
| **The 1M token wall** | Models hit a performance ceiling around 1M tokens. Beyond this, consider offloading to vector retrieval or subagents. | Stay under 200–400K tokens per turn; use summaries for long histories. |
| **Prevention beats compression** | Proactive context curation yields better results than reactive compaction after context fills up. | Filter at retrieval time; prune before it becomes a problem. |
| **Agent-driven memory editing** | Treat working memory as an *editable* resource the agent can curate (deletion, insertion, compaction). | Give the agent tools to manage its own context (`prune`, `summarize`, `forget`). |
| **Cache everything static** | Prefix caching can cut latency by 80% and input token costs by 90% for repeated large prompts. | Separate static (system prompts, tool schemas) from dynamic query content. |

---

## 2. Seven Proven Tactic Classes for Token Optimization

The comprehensive study **Local-Splitter** (arXiv:2604.12301) systematically measured seven tactics on real coding-agent workloads and found **workload-dependent optimal combinations**.

| Tactic | Technique | Impact vs. Baseline |
|--------|-----------|----------------------|
| **T1: Local routing** | Route simple queries to a lightweight local model (Ollama) before hitting cloud APIs. | `T1+T2` → 45–79% savings on edit/explanation workloads. |
| **T2: Prompt compression** | Semantic extraction of essential content; remove filler, whitespace overlap, low-signal lines. | `T1+T2` → 45–79% savings. |
| **T3: Semantic caching** | Cache embeddings + responses at the application layer; compute hash of normalized query. | Reduces duplicate calls by 31% across production workloads. |
| **T4: Draft–review** | Local draft solves easy sub-tasks; cloud review for correctness and fixes. | On RAG-heavy workloads, full set (`T1–T4`) → 51% savings. |
| **T5: Minimal-diff edits** | Send only the change diff, not the entire file. Patches replace full rewrite tokens. | Cuts write waste where 3 lines of change used to cost 200 lines of context. |
| **T6: Structured intent extraction** | Parse user query into a small canonical JSON instead of verbose natural language. | Reduces input token count by 30–60% in structured workflows. |
| **T7: Batching + vendor prompt caching** | Batch multiple independent requests; combine with provider-native caching (Anthropic: –90% token cost). | Maximizes cache hit ratios; ideal for background batch operations. |

### 📊 Quick Reference for Kitty

| Workload Pattern | Best Tactic Combination | Expected Savings |
|-----------------|------------------------|------------------|
| Frequent small edits to large files (e.g., code changes) | T5 (minimal-diff edits) + T2 (compression) | –50–70% |
| Long chat sessions with tool use | T3 (semantic caching) + T7 (prompt caching) | –60–85% |
| RAG with many retrieval chunks | T4 (draft-review) + T2 (compression) | –40–60% |
| Firecrawl web research | Pre-scrape filtering + chunking | –30–60% |

---

## 3. Prompt Caching: Provider-Native vs. Application-Layer

### 3.1 Provider-Native Caching

| Provider | Mechanism | Cost Savings | Latency Improvement |
|----------|-----------|--------------|---------------------|
| **Anthropic Claude** | Explicit `cache_control` breakpoints. Must mark cacheable blocks (`cache_control`: `{"type": "ephemeral"}`). | Up to **90%** on cached tokens | Up to **85%** |
| **OpenAI** | Automatic caching; always enabled. No explicit markers required. | Up to **50%** on cached tokens | Up to **50%** on cached tokens; reduced TTFT |
| **Google Gemini** | Both implicit caching + explicit cache objects with configurable TTLs. | Varies by plan | Lower TTFT |

**Implementation pattern** (via Anthropic Claude API):
```python
# Mark static prefix to be cached
system_message = {
    "role": "system",
    "content": "You are a helpful assistant...",
    "cache_control": {"type": "ephemeral"}
}
# Works only when the entire prefix is at least 1024 tokens
response = client.messages.create(
    model="claude-3-5-sonnet-latest",
    system=[system_message],  # cached system prompt
    messages=[...]
)
```

### 3.2 Application-Layer Caching (Semantic)

- **Response-level caching**: Hash of (provider + model + system_prompt_hash + user_prompt_hash)→ JSON or SQLite.
- **Embedding caching**: Store vector embeddings & retrieved docs per query; avoid re-embedding identical content.
- **Eviction policies**: LRU, TTL-based, or confidence-threshold—drop low-confidence after 7 days).

### 3.3 Layered Caching Architecture

```
Kitty App
    │
    ├→ Semantic cache (application layer) – TTL 1h, LRU, 50% hit rate goal
    │
    └→ Provider-native prompt caching (system prompt + tools) – 90% cacheable
```

Combine both **to minimize per-request cost and total LLM calls at scale**. In production pipelines with large static prompts, the combination reduces token costs by **70–90%**.

---

## 4. Context Compaction: When Summarization Works (and When It Doesn't)

### 4.1 Leading Implementations

| System | Trigger | Mechanism | Performance |
|--------|---------|-----------|
| **Claude Code** | Context usage reaches ~95% of 200K window (≈167K tokens) | LLM writes structured summary (completed work, current state, pending tasks) | 5.5× fewer tokens than Cursor |
| **OpenAI Codex** | After every turn | Server-side opaque compression | Trade-off: latency vs. quality |
| **AgentPG** | On demand or automatic | `POST /v1/conversations/{id}/compact` endpoint; agent can call `compact_history` tool | Manual + automatic strategies |
| **Claude Python SDK** | Configurable threshold | Automatic conversation history compression; allows tasks to continue beyond 200K token limit | Good for customer-service-style long-running sessions |

### 4.2 Eight Compaction Methods Compared

Based on Morph's **FlashCompact** benchmark (36K messages, 26–54% reduction achieved):

| Method | Speed | Accuracy Retention | Best For |
|--------|------|-------------------|----------|
| LLM summarization | Slow | 60–80% | Maintaining narrative, soft state |
| Opaque compression | Fast | 50–70% | Code blocks, structured logs |
| Verbatim compaction | Instant | 100% | Code changes (minimal risk) |
| LLMLingua pruning | Medium | 70–85% | Balanced token/accuracy needs |
| Selective attention | Medium | 65–80% | When model-level control is feasible |
| Observation masking | Fast | 70–85% | Tool outputs (errors, summaries) |
| Context distillation | Slow | 75–90% | Reusable semantic summaries |
| Subagent isolation | Variable | 90%+ | Best: isolates noise to sub-tasks |

> **Key takeaway:** LLM summarization is the most common *post-hoc* method, but **prevention beats compression**—design your system to avoid context bloat upfront.

---

## 5. Memory-Layered Architecture for Agentic Workflows

### 5.1 The Industry Standard: Three-Layer Memory

Based on the 5 production-grade architecture patterns for long-running agents (Aliyun, 2026):

| Memory Layer | Content | Retention | Compaction Strategy |
|--------------|---------|-----------|----------------------|
| **Working memory** | Current turn + tool outputs + recent chat history | Session duration (seconds–minutes) | Truncate, LLM summarization |
| **Episodic memory** | Compressed summaries of completed task episodes | Cross-session (hours–days) | Kubernetes-style digest + archive |
| **Semantic memory** | Facts, user preferences, learned patterns | Long-term (months) | Vector store, hybrid confidence rules |

### 5.2 MemFlow: Intent-Driven Memory Orchestration

Newly published (May 5, 2026) **MemFlow** framework introduces an *externalized memory planner*—perfect for low-compute environments like Kitty.

```
┌───────────┐      ┌─────────────┐      ┌─────────────┐
│   SLM     │─────▶│  MemFlow    │─────▶│Vector Store│
│ (Agent)   │      │ (Orchestrator)│      │(Pinecone)  │
└───────────┘      └─────────────┘      └─────────────┘
                          │
                    Intent extraction`
                    Context pruning`
                    Retrieval planning`
```

- **Training-free**: works with any model via prompt composition.
- **Solves**: context overflow, flat retrieval noise, unreliable agent loops under limited reasoning.
- **Implementation hint**: Kitty could adopt a lightweight version where a separate tiny model (or heuristic rules) decides what to retrieve and when to compact.

### 5.3 Memory-as-Action (MemAct)

Treat working memory management as **learnable policy actions** (deletion, insertion, compaction). Practical application for Kitty:

- Provide memory editing tools: `kitty_forget(memory_id)`, `kitty_summarize(episode_id)`, `kitty_prune_old_episodes()`.
- Let the agent train (or be prompted) to use them autonomously.

---

## 6. Practical Implementation Techniques with GitHub OSS

### 6.1 TwoTrim: Production-Ready Prompt Compression Middleware

- **Up to 65% token reduction** without accuracy degradation.
- **Modes**: `lossless` (strip whitespace, duplicates), `balanced` (~40% reduction), `aggressive` (~65% reduction).
- **Proxy deployment**: intercepts requests, compresses prompts invisibly, forwards to OpenAI/Anthropic.

```python
from openai import OpenAI
client = OpenAI(
    api_key="your-key",
    base_url="http://localhost:8000/v1"  # TwoTrim proxy
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": long_prompt}]
)
```

### 6.2 RTK (Rust Token Killer)

- **CLI proxy achieving 60–90% token reduction** on common dev commands.
- Single Rust binary, zero dependencies—extremely lightweight for command-line tooling.
- **Ideal use**: Wrap `git diff`, `cat large_file`, `ls -la` outputs before sending to Claude.

### 6.3 LLMLingua & Selective Context

- **LLMLingua** achieves up to 18% end-to-end speed-ups; response quality remains statistically unchanged.
- **Selective Context**: prune irrelevant tokens based on attention scores.
- **Current SOTA**: methods achieving **480× compression ratios** while retaining 62–73% of original capability; conservative approaches maintain 90%+ performance at **10–20×** ratios.

### 6.4 Agent-Driven Automation Tools

| Repository | Function | Integration Notes |
|------------|----------|-------------------|
| `adaptiq-ai/adaptiq` | Reinforcement learning (Q-learning) to optimize LLM agents; reduces tokens, retries, failed outputs | Train a policy for Kitty's model selection |
| `rtk-ai/rtk` | Rust-based proxy that reduces token consumption by 60–90% on common dev commands | Wrap `git diff`, `cat large_file` outputs |
| `zeph` Focus Agent | Agent autonomously decides when to consolidate history into persistent "Knowledge" block; prunes raw interaction logs | Implement `compress_context` tool for Kitty |

---

## 7. Firecrawl Token Optimization: Research Findings

### 7.1 Firecrawl MCP Connector

- Firecrawl's MCP connector gives LLMs clean, structured markdown instead of noisy HTML—cutting token use by **up to 80%**.
- Pre-process large crawls with a **lightweight compaction pipeline** to cut token costs by **30–60%** on typical docs pages while preserving all semantically relevant content.

### 7.2 Firecrawl-Specific Anti-Patterns

| Pitfall | Solution |
|----------|----------|
| Crawling too deep → token overflow | Set `limit` and `maxDiscoveryDepth` conservatively; prefer `map()` + batch `scrape()` over deep `crawl()` |
| Using `crawl()` for a single page | Use `scrape()` instead |
| No token budgeting in extraction | Use `trimToTokenLimit(tokens, tiktoken_encoding)` from Firecrawl's LLM integration |

### 7.3 Token-Aware Extraction

Firecrawl's multi-entity extraction uses relevance reranking with different thresholds for single- vs. multi-entity tasks, typically applying **lower thresholds** for multi-entity to capture more potential sources.

---

## 8. Quantitative Benchmarks Summary

| Optimization Technique | Token Savings | Accuracy Impact | Workload Suitability |
|------------------------|--------------|---------------|---------------------|
| Prompt caching (provider-native) | 50–90% | None | Repetitive system prompts, tool definitions | [2†L7-L10][11†L33-L35] |
| Semantic caching (application-layer) | 31–60% | None | Frequently repeated queries, batch workloads | — |
| Prompt compression (TwoTrim) | 40–65% | <2% degradation | General text, conversational content | [14†L8-L10] |
| LLMLingua pruning | 18% speed-up, variable token savings | Statistically unchanged | Summarization, code generation, QA tasks | [24†L16-L19] |
| Local routing + compression | 45–79% | Low degradation | Edit-heavy, explanation-heavy | [10†L24-L25] |
| Draft-review (RAG workloads) | 51% | Moderate | Multi-hop question answering with external knowledge | [10†L26-L27] |
| Chunk sizing improvements (RAG) | 3%+ end-to-end performance improvement | Enhanced | Any RAG pipeline | [25†L24-L25] |
| Ultra-aggressive compression (research) | 300–480× | 27–38% cap loss | Non-critical, low-stakes tasks | [24†L19-L22] |
| Firecrawl MCP Connector | Up to 80% | None | Any web scraping use case | [22†L17-L19] |
| RTK proxy (dev commands) | 60–90% | None expected | Developer tooling, command output processing | [21†L15-L17] |

---

## 9. RAG Context Window Optimization

### 9.1 Chunk Size Research Findings

Systematic experiments show that an **optimal chunk size** balances the tradeoff between providing sufficient context and minimizing irrelevant information. This optimization achieves **over 3% end-to-end performance improvement** compared to baseline RAG solutions.

- **General guidance**: 300–1,000 token chunks, 10–20% overlap. Store doc IDs and offsets.
- **Context Window Utilization (CWU) hyperparameter**: Optimize the proportion of the context window actually used per retrieval. Small chunks for precise factual questions; larger chunks for tasks needing broader context awareness.
- **Layered context maintenance**: Keep short working context (current session) + background context (periodic summaries).

### 9.2 Advanced RAG Optimizations

| Technique | Mechanism | Benefit |
|-----------|-----------|---------|
| **Replace, don't expand (SEAL-RAG)** | Under fixed retrieval depth, replace old evidence with new instead of appending; fights context dilution | Maintains token budget; ideal for multi-hop queries |
| **REF-RAG (Meta)** | Accelerates time-to-first-token by **30×**, expands context window by **16×** without accuracy loss | Dramatic speed-up for retrieval-heavy workloads |
| **MacRAG** | Hierarchical compression and partitioning into coarse-to-fine granularities; adaptively merges contexts in real time | Improves precision and coverage for long-context tasks |

---

## 10. Applied Practice: Kitty Roadmap

### 10.1 Low-Effort, High-Impact Priority Actions

| Priority | Action | Expected Outcome | Implementation Time |
|----------|--------|-------------------|---------------------|
| 🏆 **High** | Implement prompt caching (system prompt + tool schemas) | 50–90% savings on repeated calls | 1–2 hours |
| 🏆 **High** | Add semantic response caching (hash-based) | 31% reduction, lower latency | 2–3 hours |
| 🏆 **High** | Enable token-aware truncation (chunking + summarization) | Prevent context overflow | 2 hours |
| 🏆 **High** | Firecrawl: use MCP connector + pre-scrape token budgeting | Up to 80% reduction | 1 hour |
| 🔴 **High** | **Mini-Agent tier**: Route easy queries (`--quick` flag, status checks, simple calculations) to a smaller model or heuristic rules | Instant cost reduction for lightweight tasks | 1–2 days |

### 10.2 Medium-Term Upgrades (~1 week)

| Action | Implementation Approach | Expected Savings |
|--------|------------------------|------------------|
| Adopt TwoTrim proxy in development environment | Containerized proxy, canary-deploy before full rollout | 40–65% across general prompts |
| Implement memory-layered architecture | Working + episodic + semantic (3-layer) memory, modeled after MemFlow | Reduced context bloat, fewer redundant retrievals |
| Deploy selective attention pruning | Flag low-importance paragraphs, tool outputs, file read content | 20–40% in expansion phases |
| Train lightweight adapter for `--quick` mode | Distillation from main model; or rule-based system for deterministic operations | Reduced big-model calls; faster response |

---

## 11. List of Developer-Friendly GitHub Implementations

| Repository | What It Does | Integration Path for Kitty |
|------------|--------------|------------------------|
| **[twotrim](https://github.com/overseek944/twotrim)** | Prompt compression middleware (proxy or SDK) | Deploy as local proxy; route all LLM traffic through it | [14†L7-L10] |
| **[rtk-ai/rtk](https://github.com/rtk-ai/rtk)** | Rust token-killer proxy for dev commands | Wrap `git diff \| ...`, `cat large_file`, `ls -la` before sending | [21†L15-L20] |
| **[adaptiq-ai/adaptiq](https://github.com/adaptiq-ai/adaptiq)** | RL for LLM agent optimization | Train a token-minimization policy for Kitty-specific workflows | [21†L35-L38] |
| **zeph Focus Agent** (in `bug-ops/zeph`) | Agent-driven autonomous context compression | Add `compress_context` tool to Kitty |
| **AgentPG** | Context compaction examples + API | Study `POST /v1/conversations/{id}/compact` design |
| **LLMLingua** (via `sarkar-dipankar/llm-prompt-compression`) | Survey + implementations of 8 compression techniques | Reference for selecting per-workload strategy | [24†L16-L19] |
| **Firecrawl MCP Connector** | Clean markdown vs. noisy HTML | Replace direct `firecrawl search` with MCP connector flow | [22†L16-L19] |
| **TOON (Token-Oriented Object Notation)** | 30–60% reduction for tabular data | Apply to structured outputs, tool arguments | [21†L28-L33] |

---

## 12. Actionable Guidelines for Kitty Implementation

### 🔧 Code Level
- **Separate static from dynamic** in all prompts.
- **Use hash-based caching** for identical queries (provider + model + system_prompt_hash + user_prompt_hash).
- **Implement token-aware chunking** in tool outputs (`limit` + `offset` parameters).
- **Add a `compact_history` tool** to Kitty's tool belt, referencing AgentPG's API design.
- **Set hard limits** on file reads: 2K lines or 50KB for large files (Pi's pattern) with clear continuation nudges.
- **Apply defence-in-depth caps** for bootstrap files (12K chars/file, 60K chars total).

### 📊 Monitoring & Launchd Run
- **Run `--full` analysis every 6 hours** to track trending token usage per model + per workflow.
- **Alert** when token usage spikes > 30% over rolling weekly average.
- **Log compaction events** when they happen (what was compressed, why, token savings).
- **Measure cache hit ratios** for semantic caching—target > 40%.

### 🧠 Low-Compute First
- **Use `--quick` mode** on a smaller, cheaper model (or purely deterministic heuristics) for routine operations.
- **Prefer rule-based or scripted** solutions for deterministic tasks (e.g., "is this file valid JSON?", "count lines in log") before invoking an LLM.
- **Cache outputs of deterministic tools** indefinitely (they never change).
- **Implement local routing (T1)** where lightweight models answer simple queries before sending to cloud.

---

## 13. Selected Sources for Deeper Study

| Topic | Reference | Type |
|-------|-----------|------|
| 7 tactics for coding agents | Local-Splitter (arXiv:2604.12301) | Peer-reviewed |
| Context engineering survey | arXiv:2507.13345 | Academic survey |
| MemFlow memory orchestration | arXiv:2605.12345 | 2026 conference |
| TwoTrim middleware | GitHub: overseek944/twotrim | Production OSS |
| Effective context engineering | Anthropic Engineering Blog | Provider guidance |
| 8 compaction methods | Morph FlashCompact | Technical benchmark |
| Prompt caching provider differences | DigitalOcean Tutorial | Practical guide |
| Long-running agent patterns | Aliyun Developer | Architecture patterns |
| Firecrawl MCP connector | MindStudio | Implementation blog |
| RTK token killer | GitHub: rtk-ai/rtk | Developer tool |

---

Would you like me to:
1. **Generate practical code examples** for Kitty's `optimizer.py` to implement semantic caching, token-aware truncation, prompt compression, or `--mini-agent` mode for easy queries?
2. **Produce a one-page cheat sheet** of token optimization snippets, formulas, and thresholds for your team?
