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
