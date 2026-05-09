# Kitty OpenWebUI Advanced Workflows

This is the canonical operator runbook for:
- model routing (LiteLLM)
- code execution (Jupyter)
- tool extensibility (OpenAPI/MCP tool servers)
- terminal extensibility (OpenTerminal server)
- optional public HTTPS (Cloudflare tunnel)

## 1) Architecture (Current)

- OpenWebUI UI: `http://127.0.0.1:3000`
- LiteLLM proxy (model router): `http://127.0.0.1:8001`
- Jupyter code-exec backend: `http://127.0.0.1:8888`
- Open Terminal backend: `http://127.0.0.1:9614`
- Optional Kitty Gateway API (future/default for phase-2 routing): `http://127.0.0.1:8000`

Why `8001` and not `8000`:
- `8001` is the LiteLLM OpenAI-compatible endpoint OpenWebUI currently uses.
- `8000` is reserved for the custom Kitty Gateway service lane, not LiteLLM.

## 2) Daily Commands

From repo root:

```bash
bash kitty_gateway/start_all.sh
bash kitty_gateway/status_all.sh
bash kitty_gateway/diagnose_models.sh
```

Stop:

```bash
bash kitty_gateway/stop_all.sh
```

Smoke-only preflight:

```bash
START_ALL_SMOKE=1 bash kitty_gateway/start_all.sh
```

## 3) Advanced Model Workflow (Pipelines-Compatible)

OpenWebUI supports multiple OpenAI-compatible backends using semicolon-delimited lists.

Configured defaults in `kitty_gateway/openwebui.env`:
- `OPENAI_API_BASE_URLS="http://127.0.0.1:8001/v1"`
- `OPENAI_API_KEYS="kitty-local-key-change-me"`

To add a second backend (example: pipelines service on `9099`), set:

```bash
OPENAI_API_BASE_URLS="http://127.0.0.1:8001/v1;http://127.0.0.1:9099"
OPENAI_API_KEYS="kitty-local-key-change-me;pipelines-local-key"
```

Recommendation:
- Keep LiteLLM first in the list so your stable local routing remains primary.

## 4) MCP / OpenAPI Tool Server Extensibility

`TOOL_SERVER_CONNECTIONS` is pre-wired in env as an empty JSON list.

Use this schema:

```json
[
  {
    "url": "https://your-server.example.com",
    "path": "/mcp",
    "type": "mcp",
    "auth_type": "bearer",
    "key": "replace-me",
    "config": {}
  }
]
```

Env line format (single line, escaped as needed):

```bash
TOOL_SERVER_CONNECTIONS='[{"url":"https://your-server.example.com","path":"/mcp","type":"mcp","auth_type":"bearer","key":"replace-me","config":{}}]'
```

Safety defaults already set:
- `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER="30"`
- `AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA="15"`
- `AIOHTTP_CLIENT_SESSION_TOOL_SERVER_SSL="true"`

## 5) OpenTerminal Extensibility

`TERMINAL_SERVER_CONNECTIONS` is pre-wired as an empty list.

Example:

```bash
TERMINAL_SERVER_CONNECTIONS='[{"id":"open-terminal-local","name":"OpenTerminal Local","enabled":true,"url":"http://127.0.0.1:9614","path":"/openapi.json","auth_type":"bearer","key":"replace-me"}]'
```

Current local default in this repo:
- `OPEN_TERMINAL_URL="http://127.0.0.1:9614"`
- `TERMINAL_SERVER_CONNECTIONS` points to `open-terminal-local` using Bearer auth.

## 6) Code Execution Workflow

Already configured:
- `ENABLE_CODE_EXECUTION=true`
- `CODE_EXECUTION_ENGINE=jupyter`
- `CODE_EXECUTION_JUPYTER_URL=http://127.0.0.1:8888`
- Jupyter token in `CODE_EXECUTION_JUPYTER_AUTH_TOKEN`

Manual restart (if needed):

```bash
bash kitty_gateway/start_jupyter_exec.sh
```

## 7) Cloudflare HTTPS Workflow

Quick tunnel mode (ephemeral URL):

```bash
CF_TUNNEL_MODE=quick bash kitty_gateway/start_cloudflare_https.sh
```

Named tunnel mode:

```bash
CF_TUNNEL_MODE=named CF_TUNNEL_TOKEN="..." bash kitty_gateway/start_cloudflare_https.sh
```

Or token file:

```bash
CF_TUNNEL_MODE=named CF_TUNNEL_TOKEN_FILE="/path/to/token.txt" bash kitty_gateway/start_cloudflare_https.sh
```

Integrated launch:
- set `ENABLE_CLOUDFLARE_HTTPS="1"` in `openwebui.env`
- then run `bash kitty_gateway/start_all.sh`

## 8) Recommended Defaults (Already Applied)

- Remote-first default model alias: `DEFAULT_MODELS="kitty-default"`
- Local Ollama provider disabled in OpenWebUI: `ENABLE_OLLAMA_API="false"`
- Direct unmanaged provider connections disabled: `ENABLE_DIRECT_CONNECTIONS="false"`
- User webhooks disabled by default: `ENABLE_USER_WEBHOOKS="false"`
- Tavily search default: `WEB_SEARCH_ENGINE="tavily"`

## 9) Troubleshooting

1. No models in UI:
- run `bash kitty_gateway/diagnose_models.sh`
- verify LiteLLM health and `OPENAI_API_KEY/LITELLM_MASTER_KEY`

2. Code execution fails:
- run `bash kitty_gateway/status_all.sh`
- verify Jupyter health and token parity in env

3. Tool servers fail:
- validate JSON in `TOOL_SERVER_CONNECTIONS`
- start with one connection and confirm SSL/auth first

4. Tunnel URL not shown:
- check `logs/kitty_gateway/cloudflare.log`
- quick mode only returns `*.trycloudflare.com` URLs
