#!/usr/bin/env python3
"""MCP server (stdio) — Specialist Council ``consult_council`` tool.

Open WebUI is not required for this server; stderr is used for diagnostics so
stdout stays JSON-RPC-clean.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gateway.council_orchestrator import build_council_graph  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("kitty.mcp_council")

_council_graph = None


def _get_council_graph():
    global _council_graph
    if _council_graph is None:
        _council_graph = build_council_graph()
    return _council_graph


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kitty-specialist-council"
SERVER_VERSION = "0.2.0"

_TOOL_CONSULT = {
    "name": "consult_council",
    "description": (
        "Routes a query through Kitty's Specialist Council orchestration stub "
        "(keyword routing → mock retrieval → synthesized answer)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "User question for the council.",
            }
        },
        "required": ["query"],
    },
}


def _jsonrpc_success(req_id: int | None, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_err(req_id: int | None, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _tool_result_payload(text: str) -> dict:
    """Structured tool result compatible with MCP + bridge consumers."""
    return {
        "content": [{"type": "text", "text": text}],
        "response": text,
        "isError": False,
    }


def dispatch(req: dict) -> dict | None:
    """Handle one MCP JSON-RPC object. Notifications (no ``id``) return None."""
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params")

    try:
        if method == "initialize":
            return _jsonrpc_success(
                req_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            )

        # Cursor / MCP clients send this notification after initialize
        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            return _jsonrpc_success(req_id, {"tools": [_TOOL_CONSULT]})

        if method == "tools/call":
            if not isinstance(params, dict):
                return _jsonrpc_err(req_id, -32602, "Invalid params for tools/call")
            tool_name = params.get("name")
            args = params.get("arguments") or {}
            if tool_name != "consult_council":
                return _jsonrpc_err(req_id, -32601, f"Unknown tool: {tool_name}")
            query = (args.get("query") or "").strip()
            if not query:
                return _jsonrpc_err(req_id, -32602, "Missing arguments.query")

            graph = _get_council_graph()
            final_state = graph.invoke({"query": query, "messages": []})
            reply = str(final_state.get("final_response") or "").strip()

            if not reply:
                messages = final_state.get("messages") or []
                tail = messages[-1] if messages else None
                reply = getattr(tail, "content", str(tail) if tail is not None else "")
                reply = reply.strip()

            return _jsonrpc_success(req_id, _tool_result_payload(reply))

        if method == "ping":
            return _jsonrpc_success(req_id, {"ok": True})

        return _jsonrpc_err(req_id, -32601, f"Method not found: {method}")

    except Exception as e:
        logger.exception("Unhandled error serving MCP request")
        return _jsonrpc_err(req_id, -32603, str(e))


def main() -> None:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": str(exc)},
                    }
                ),
                flush=True,
            )
            continue

        if not isinstance(req, dict):
            continue

        if "method" not in req:
            continue

        out = dispatch(req)
        if out is not None:
            print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
