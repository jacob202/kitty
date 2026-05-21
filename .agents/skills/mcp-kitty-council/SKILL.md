---
name: mcp-kitty-council
description: Run Kitty's Specialist Council MCP server (consult_council) from the repo root; wires multi-stage routing for agent tools and Kitty MCP tooling.
---

# Skill: mcp-kitty-council

## When to use

- User mentions **MCP council**, **specialist council orchestrator**, or **`consult_council`**
- Debugging **gateway/mcp_council_server.py** or **gateway/council_orchestrator.py**
- Connecting Cursor (or another MCP client) to Kitty's orchestration stub

## What it implements

| Piece | Role |
|--------|------|
| `gateway/council_orchestrator.py` | Keyword librarian → specialist mock RAG → optional consultant → string synthesis (**no LangGraph dependency**). |
| `gateway/mcp_council_server.py` | stdio JSON-RPC: `initialize`, `tools/list`, `tools/call` for `consult_council`. Diagnostics on **stderr** only. |

## Cursor / MCP setup

Use the repo root (`~/Projects/kitty`) so `gateway` resolves. Example block (merge into your MCP config):

```json
"kitty-council": {
  "command": "/opt/homebrew/bin/python3.12",
  "args": ["/ABS/PATH/TO/kitty/gateway/mcp_council_server.py"],
  "cwd": "/ABS/PATH/TO/kitty"
}
```

## Kitty tool bridge (`mcp_tool_bridge.py`)

Uses a **single-line** `tools/call` envelope; this server replies with a MCP-shaped `content` array plus **`response`** (plain text) for backward compatibility.

## Operational checks

Manual smoke:

```bash
cd /ABS/PATH/TO/kitty
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"consult_council","arguments":{"query":"repair an audio amplifier with ML"}}}' \
  | python3 gateway/mcp_council_server.py
```

Expect JSON lines on stdout; errors on stderr.

## Gemini / ingestion / curation (related reliability)

Scripts that hit **`gateway.llm_client.call_llm`** may fall through to **Gemini direct** after LiteLLM / AgentRouter / OpenRouter exhaustion. **`KITTY_GEMINI_MODEL`** must be a **text** model (`gemini-2.5-flash` aligns with **`gateway/litellm_config.yaml`**). **`curation_worker.py`** honors **`KITTY_CURATION_LLM_MODEL`** and **`KITTY_INGEST_LLM_MODEL`** with a higher default HTTP timeout (`KITTY_CURATION_LLM_TIMEOUT`, default **180** seconds).
