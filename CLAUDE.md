# Kitty — Claude Code Rules

See `AGENTS.md` for all shared agent rules. This file only has Claude-specific overrides.

---

## Cost Discipline

Conserve usage. Jacob has explicitly said "always conserve your usage" multiple times.

**Routing strategy: cheap-first, free-as-backup, premium-reserved.**

- **Default tier (cheap-and-reliable):** DeepSeek V4 Flash, Gemini 2.5 Flash, Groq paid tier — under $0.01/1K, deterministic, low queue risk. Use for execution work, code generation, file edits, test writing.
- **Backup tier (free):** OpenRouter free models (`qwen/qwen3-coder:free`, `meta-llama/llama-3.3-70b-instruct:free`), Groq free tier. Use when daily budget is hit, primary is down, or task is genuinely simple. Accept rate-limit risk.
- **Premium tier (reserved):** Claude Sonnet for architecture, code review, multi-file synthesis, and Jacob-facing summaries. Claude Opus only for highest-leverage strategic decisions.
- **Why cheap-first not free-first:** free models have rate limits, queues, quality variance, and outage risk. Cheap models like DeepSeek Flash are deterministic. Free is the safety net.
- **Local first when offline or private:** MLX Qwen3.5-4B-4bit, Ollama qwen2.5-coder:7b. Free, private, and avoids any cloud dependency.
- **Cut parallel agents** the moment they stop producing evidence. Don't keep them alive "just in case."
- **Named-tool fidelity:** when Jacob explicitly names a tool (`coderabbit review`, `aider`, `crush run`), use that exact tool. Do not silently substitute.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
