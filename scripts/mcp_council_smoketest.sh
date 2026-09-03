#!/usr/bin/env bash
# Compatibility tombstone retained because the coordination registry tracks this exact path.
# The legacy mcp-kitty-council server/orchestrator was retired; do not resurrect it here.
set -euo pipefail
cat >&2 <<'MSG'
RETIRED: scripts/mcp_council_smoketest.sh no longer has a live MCP server to smoke-test.
Use the current read-only council entrypoint instead:
  python3 scripts/agent_council.py --help
See .agents/skills/agent-council/SKILL.md for current guidance.
MSG
exit 2
