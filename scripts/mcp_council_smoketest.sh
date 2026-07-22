#!/usr/bin/env bash
# Manual smoke test for gateway/mcp_council_server.py (the /mcp-kitty-council skill).
# Sends initialize -> tools/list -> tools/call(consult_council) over stdio JSON-RPC.
# Expect JSON lines on stdout; errors on stderr.
set -euo pipefail
cd "$(dirname "$0")/.."

printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"consult_council","arguments":{"query":"repair an audio amplifier with ML"}}}' \
  | python3 gateway/mcp_council_server.py
