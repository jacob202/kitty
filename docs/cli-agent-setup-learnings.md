# CLI Agent Setup Learnings

Date: 2026-04-24

This captures what we learned while configuring `crush`, `goose`, and `aider` for Kitty. Keep this handy before changing model/provider config again; several failures look like config bugs at first but are actually quota, auth, sandbox, or local-memory issues.

## Goal

Configure the three coding CLIs for the fastest capable coder currently usable on this machine, with practical fallbacks, skills/MCP enabled where supported, and real smoke tests rather than "config looks plausible" guesses.

Current practical winner:

- `crush`: `openrouter/openai/gpt-5.4-mini`, with `openrouter/openai/gpt-5.4-nano` as the small model.
- `goose`: native `openrouter` provider with `openai/gpt-5.4-mini`.
- `aider`: intended target is `openrouter/openai/gpt-5.4-mini`, but Aider is still blocked by LiteLLM sending `max_tokens=65536` despite our metadata overrides.

## Files Touched

- `crush.json`: project Crush config.
- `.aider.conf.yml`: project Aider config, ignored by `.gitignore`.
- `~/.config/goose/config.yaml`: Goose global config.
- `~/.config/aider/model_settings.yml`: Aider custom model behavior.
- `~/.config/aider/model_metadata.yml`: Aider custom model metadata; must be JSON/JSON5-shaped, not YAML list-shaped.
- `.gitignore`: added `.env.*` while preserving `!.env.example` so `.env.aider` cannot accidentally be committed.

Do not paste API keys into this document. Existing config files may contain live local credentials; treat them as secrets.

## Verified Commands

Crush passed:

```bash
crush update-providers
crush run --quiet "Reply with exactly OK."
```

Observed result:

```text
OK
```

Goose passed with explicit provider override:

```bash
/Users/jacobbrizinski/.local/bin/goose run --provider openrouter --model openai/gpt-5.4-mini --no-session --max-turns 1 --quiet --text "Reply with exactly OK."
```

Goose also passed after saving native OpenRouter config:

```bash
/Users/jacobbrizinski/.local/bin/goose run --no-session --max-turns 1 --quiet --text "Reply with exactly OK."
```

Observed result:

```text
OK
```

Aider starts and reads the intended model config, but live calls fail:

```bash
aider --message "Reply with exactly OK." --no-git --no-auto-commits --no-check-update --yes-always
```

Observed blocker:

```text
OpenRouterException: This request requires more credits, or fewer max_tokens.
You requested up to 65536 tokens...
```

## Crush Details

Original problem shown in the Crush TUI:

```text
Bad Request
"qwen2.5-coder:7b" does not support thinking
```

Root cause:

- Project `crush.json` defaulted both `large` and `small` to local `ollama/qwen2.5-coder:7b`.
- Crush was sending a thinking/reasoning option to that Ollama model.
- Qwen 2.5 Coder via Ollama rejects that request shape.

Remote model tests:

- `openrouter/openai/gpt-5.4`: reachable, but failed because Crush requested up to `64000` output tokens and the OpenRouter account did not have enough credits.
- `openrouter/openai/gpt-5.4-mini`: works when capped lower in project `crush.json`.
- `anthropic/claude-sonnet-4-6`: failed with `401 Unauthorized`, invalid Anthropic API key.
- `gemini/gemini-3.1-pro-preview-customtools`: failed because Gemini free-tier quota was exhausted/zero.
- `deepseek/deepseek-chat`: failed with `Insufficient Balance`.

Current working Crush config strategy:

- Add an `openrouter` provider in project `crush.json`.
- Set large model to `openai/gpt-5.4-mini`, `max_tokens: 1024`, `reasoning_effort: low`.
- Set small model to `openai/gpt-5.4-nano`, `max_tokens: 512`, `reasoning_effort: low`.
- Keep MCP filesystem and memory enabled.
- Keep skills paths enabled:
  `./src/tools/superpowers/skills`, `./consolidated-skills`, `./skills`, `./archive/skills/legacy-skills`.

Important operational note:

- If a Crush TUI was already open before editing `crush.json`, it may keep the old Qwen model in memory. Quit the TUI and reopen it so it reloads project config.

Remaining Crush warnings:

- `.claude/skills/audit/SKILL.md` has no YAML frontmatter, so Crush logs a skill-parse warning. It does not block runs.
- Crush may log analytics delivery warnings when network/sandbox DNS blocks `data.charm.land`; not a model failure.

## Goose Details

Initial issues:

- `goose` was not on PATH, but the real binary exists at `/Users/jacobbrizinski/.local/bin/goose`.
- Home-directory state writes were blocked in the sandbox, causing log/session DB failures during tests.
- `goose doctor` started an interactive Kimi device authorization flow, so it is not the best noninteractive smoke test.

Useful smoke test:

```bash
/Users/jacobbrizinski/.local/bin/goose run --no-session --max-turns 1 --quiet --text "Reply with exactly OK."
```

Provider findings:

- OpenAI-compatible OpenRouter attempt with `OPENAI_HOST=https://openrouter.ai/api/v1` failed with `404`.
- OpenAI-compatible OpenRouter attempt with `OPENAI_HOST=https://openrouter.ai/api` worked only when passed as temporary env vars.
- Best saved config is Goose's native OpenRouter provider:
  `GOOSE_PROVIDER: openrouter`, `GOOSE_MODEL: openai/gpt-5.4-mini`, `GOOSE_MAX_TOKENS: 1024`.

Enabled Goose extensions currently include:

- `developer`
- `skills`
- `analyze`
- `todo`
- `memory`
- `chatrecall`
- `summon`
- `apps`
- `tom`
- `extensionmanager`

Disabled Goose extensions currently include:

- `summarize`
- `orchestrator`
- `code_execution`

## Aider Details

Current intended config:

- Main model: `openrouter/openai/gpt-5.4-mini`
- Weak model: `openrouter/openai/gpt-5.4-nano`
- `reasoning-effort: low`
- Prompt caching enabled.
- Repo map enabled in normal git mode.
- Auto commits disabled.
- Analytics disabled.
- Update checks disabled.

What works:

- `aider --version` returns `aider 0.86.2`.
- Aider reads `.aider.conf.yml`.
- Aider recognizes the configured models and reasoning setting.

Current blocker:

- Aider/LiteLLM still sends `max_tokens=65536` to OpenRouter.
- OpenRouter rejects the request because current credits only allow roughly 2k output tokens.
- Adding `max_tokens` in `~/.config/aider/model_settings.yml` was not enough.
- Converting `~/.config/aider/model_metadata.yml` to JSON/JSON5-shaped metadata with `max_output_tokens` was necessary, but as of the last test Aider still sent `65536`.

Likely next Aider debugging steps:

1. Inspect LiteLLM provider params for OpenRouter in the Aider runtime.
2. Try model aliases that avoid OpenRouter's cached 65k output metadata.
3. Try `extra_params` in `~/.config/aider/model_settings.yml`, for example `max_tokens: 1024` inside `extra_params`, because Aider merges `extra_params` directly into LiteLLM kwargs.
4. Test with `openrouter/openai/gpt-5.4-nano` as the main model to reduce cost pressure.
5. If credits are replenished, retest before overfitting config around a temporary low-balance condition.

## Ollama / Local Model Details

Installed local models:

```text
deepseek-coder-v2:16b
qwen2.5-coder:7b
nomic-embed-text:latest
```

Direct Ollama API health:

- `/api/tags` responds.
- `/api/generate` with `qwen2.5-coder:7b` timed out with zero bytes.

Ollama log finding:

```text
system memory total="8.0 GiB" free="464.4 MiB"
model weights device=CPU size="4.1 GiB"
Load failed ... error="context canceled"
```

Interpretation:

- Ollama itself is running.
- The local model path is currently memory-starved.
- On this 8 GB machine, Qwen 2.5 Coder 7B can fail to load when other apps consume memory.
- Local Ollama should not be the default for these CLIs until direct `/api/generate` returns quickly.

Useful local retest after freeing RAM:

```bash
brew services restart ollama
curl --max-time 30 -s http://127.0.0.1:11434/api/generate \
  -d '{"model":"qwen2.5-coder:7b","prompt":"Reply with exactly OK.","stream":false}'
```

Only re-enable local Crush defaults after that direct command returns real output.

## Provider Status Snapshot

As observed on 2026-04-24:

- OpenRouter key works, but credits are low. GPT-5.4 Mini works when output cap is small enough.
- OpenAI direct key was not found in the environment.
- Anthropic key exists in `.env`, but API returns `401 Unauthorized`.
- Gemini key exists, but Gemini reports quota exhausted/zero for the tested model.
- DeepSeek key exists, but API returns `Insufficient Balance`.
- Ollama is installed and serving metadata, but generation is blocked by local memory pressure.

## Next-Time Checklist

Before changing models:

1. Run `crush models | rg 'gpt-5.4|claude|gemini|qwen|deepseek'`.
2. Verify provider quota/auth with a tiny `Reply exactly OK` call.
3. Keep output caps conservative while OpenRouter credits are low.
4. Do not use local Ollama as a default unless direct `/api/generate` works first.
5. Restart already-open TUIs after config changes.
6. Keep secrets out of docs and commits.

Known good smoke tests:

```bash
crush run --quiet "Reply with exactly OK."
/Users/jacobbrizinski/.local/bin/goose run --no-session --max-turns 1 --quiet --text "Reply with exactly OK."
aider --version
```

Known not-yet-good smoke test:

```bash
aider --message "Reply with exactly OK." --no-git --no-auto-commits --no-check-update --yes-always
```

That Aider command still needs the `max_tokens=65536` issue solved or more OpenRouter credits.
