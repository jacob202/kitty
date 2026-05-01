#!/bin/bash
# Quick live smoke test of Kitty's primary routes.
# Requires server running on port 5001. Use after deploys or major refactors.

set -e

PORT=${KITTY_PORT:-5001}
BASE="http://localhost:$PORT"

echo "→ Checking server status..."
./kitty status || { echo "✗ Server not running on $PORT. Start with ./kitty start"; exit 1; }

echo ""
echo "→ /api/brief..."
curl -sS -w "\n[HTTP %{http_code}]\n" "$BASE/api/brief" | head -10

echo ""
echo "→ /api/command with /stuck..."
curl -sS -w "\n[HTTP %{http_code}]\n" -X POST "$BASE/api/command" \
  -H "Content-Type: application/json" \
  -d '{"command":"/stuck"}' | head -10

echo ""
echo "→ /api/chat..."
curl -sS -w "\n[HTTP %{http_code}]\n" -X POST "$BASE/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"smoke test","domain":"chat"}' | head -10

echo ""
echo "✓ Smoke test complete."
