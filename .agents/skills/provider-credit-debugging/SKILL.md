---
name: provider-credit-debugging
description: Debug AgentRouter, OpenRouter, 9router, DeepSeek, LiteLLM, OpenCode providers, API keys, credits, token usage, spend reports, and Kitty routing failures.
---

# Provider credit debugging

Use when a provider shows credits but requests fail, or when routing or spend looks wrong.

## Rules

- Never print full API keys; at most first/last few characters.
- Secrets only in `.env` or private tool config — not in committed files.
- Kitty uses a single public route (`kitty-default`); do not restore tiered `kitty-smart` / `kitty-agent` routing unless the product owner asks.
- Remote-only for models unless the user explicitly wants local inference.

## Kitty checks

From the repo root:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_agentrouter_config.py tests/test_llm_routing.py tests/test_token_spend_report.py -q --tb=short
python3 scripts/spend_report.py --since 2026-05-18
python3 scripts/spend_report.py --provider agentrouter --since 2026-05-18 --credits 150
```

## OpenCode checks

```bash
opencode debug config --pure
opencode debug skill --pure
opencode models fcm-nvidia --pure
```

Use `{env:NVIDIA_API_KEY}` (or the provider’s documented env) in `~/.config/opencode/opencode.json` — not literal keys.

## Order of diagnosis

1. Exact error string and command.
2. Config schema (OpenCode rejects unknown top-level keys like `hooks`).
3. Env var names vs `.env.example`; token freshness for AgentRouter.
4. Model ID exists on `/v1/models` for that key.
