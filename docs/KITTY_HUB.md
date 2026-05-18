# Kitty Hub v0.2

Status checked: 2026-05-16

Kitty Hub is a local command-center UI for Kitty. It is currently an active
experiment, not archived context.

## Runtime Status

Observed live on 2026-05-16:

```bash
uvicorn kitty_hub.app:app --host 0.0.0.0 --port 5001
```

Local URL:

```text
http://127.0.0.1:5001
```

The page title returned by the running app is:

```text
Kitty Hub v0.2 - Your One True Interface
```

## Files

```text
kitty_hub/
├── app.py
└── launch.sh
```

Generated cache files such as `.DS_Store` and `__pycache__/` were moved out of
the active repo during context cleanup.

## What It Does

- Loads recent session context from `SESSION_HANDOFF.md`.
- Shows active task-boundary records from `data/task_boundaries.jsonl`.
- Persists chat history to `data/kitty_hub_chats.jsonl`.
- Sends chat messages to the Gateway at `http://localhost:8000/ask`.
- Tries knowledge search through the Gateway at `http://localhost:8000/search`.
- Shows service health for Gateway, Open WebUI on `:3000`, and LiteLLM.

## Start

From the Kitty repo:

```bash
cd /Users/jacobbrizinski/Projects/kitty
./kitty_hub/launch.sh
```

The launcher binds to `0.0.0.0:5001` so it can be reached over Tailscale or the
local network when macOS/network permissions allow it.

## Stop

```bash
pkill -f "kitty_hub.app:app"
```

## Verify

```bash
ps -ax | rg "kitty_hub|uvicorn.*5001"
curl -sS http://127.0.0.1:5001 | rg "Kitty Hub v0.2"
```

## Known Limits

- No authentication. Treat it as local/private unless a proper auth gate is
  added.
- Chat depends on the Gateway being healthy.
- Search depends on the Gateway search route and its underlying knowledge stack.
- This is not yet part of the canonical Kitty stack in `docs/ARCHITECTURE.md`.

## Current Decision

Leave `kitty_hub/` in the repo for now because it is running and user-facing.
Review it as implementation work before committing, archiving, or promoting it
to the canonical stack.
