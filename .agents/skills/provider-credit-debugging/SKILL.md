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
./scripts/provider_credit_checks.sh --since 2026-05-18
```

## OpenCode checks

```bash
opencode debug config --pure
opencode debug skill --pure
opencode models fcm-nvidia --pure
```

Use `{env:NVIDIA_API_KEY}` or `{file:~/.config/opencode/nvidia_api_key}` in `~/.config/opencode/opencode.json` — not pasted literals in shared logs.

### Orca overlay: ENOENT on `.gitignore`

If OpenCode exits with something like `FileSystem.writeFile (…/Library/Application Support/orca/opencode-hooks/<hash>/.gitignore)` and ENOENT: Orca never created that per-repo directory. Create it, then rerun:

```bash
mkdir -p "$HOME/Library/Application Support/orca/opencode-hooks/<paste-hash-from-error>"
```

## Order of diagnosis

1. Exact error string and command.
2. Config schema (OpenCode rejects unknown top-level keys like `hooks`).
3. Env var names vs `.env.example`; token freshness for AgentRouter.
4. Model ID exists on `/v1/models` for that key.
