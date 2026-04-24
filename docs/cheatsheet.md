# Kitty Cheatsheet

## Launch

```bash
./kitty              # start + open browser
./kitty stop         # kill server
./kitty restart      # bounce
./kitty status       # running? + URLs
./kitty logs         # tail live output
```

Phone URL prints on start: `http://172.16.1.161:5001`

---

## Chat Modes

Toggle in the bar above the input field.

| Button | Model | Best for |
|--------|-------|----------|
| ⚡ FAST | OpenRouter free router by default | Everyday chat, responsive |
| ◈ BALANCED | DeepSeek-chat (remote) | Longer reasoning, complex |
| ★ MAX | DeepSeek-R1 (remote) | Hard problems, always thinks |

**THINK toggle** — adds chain-of-thought reasoning to any mode.
Shown as a collapsible blue block above the reply. Tap to expand/collapse.

---

## Slash Commands

```
/brief              morning brief — where you left off
/stuck [task]       ADHD rescue: one concrete next step
/bench sansui       Sansui AU-7900 work mode
/bench ridgeline    Honda Ridgeline work mode
/bench [name]       any custom project context
/bench off          clear work mode
/council <topic>    dynamic expert panel debate
/capture <thought>  quick brain dump (persisted)
/review             show all captures + saved facts
/remember <fact>    save a persistent fact
/deepsearch <q>     web search + synthesis
/screen [q]         screenshot + vision analysis
/status             model, tools, session cost
/clear              clear conversation history
/help               full command list
```

---

## Specialists

Shown in the right panel. Auto-activated by topic.

| Name | Domain |
|------|--------|
| Alex | Audio electronics (Sansui) |
Kelly | Fitness, health |
| Mike | Automotive (Ridgeline) |
| Taylor | Recovery, growth |
| Devin | Code, systems |

---

## Models & Keys (.env)

```bash
OPENROUTER_API_KEY=sk-or-...     # primary remote provider
ANTHROPIC_API_KEY=sk-ant-...     # fallback
KITTY_MODEL=openrouter/free                 # free online default
KITTY_MAX_MODEL=deepseek/deepseek-r1-0528   # max mode
MLX_MODEL=mlx-community/Qwen3.5-4B-4bit     # optional local model
KITTY_ENABLE_LOCAL_MLX=1                    # opt in to local MLX fast mode
```

Fallback order: OpenRouter free router → Anthropic by default; MLX first only when `KITTY_ENABLE_LOCAL_MLX=1`

---

## Easter Eggs

```
meow × 3            cat mode
/pet                purring
/treat              snacks
Konami code         rainbow theme
```

---

## Files

```
web.py              Flask entry point
src/api/
  web_orchestrator.py   LLM routing (edit model defaults here)
  streaming_routes.py   /stream SSE endpoint
  dispatcher.py         slash command router
src/templates/index.html  full UI
.env                API keys (never commit)
.kitty.log          server log (./kitty logs)
```
