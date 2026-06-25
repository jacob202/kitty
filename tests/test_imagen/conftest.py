"""Path setup for imagen tests.

The local ``mcp/`` directory must be on ``sys.path`` before the installed
``mcp`` SDK so that ``mcp.imagen`` resolves to the local package while
``mcp.server.fastmcp`` still resolves to the installed SDK (via the
namespace package in ``mcp/__init__.py``).
"""

import sys
from pathlib import Path

_worktree_root = Path(__file__).resolve().parents[2]
if str(_worktree_root) not in sys.path:
    sys.path.insert(0, str(_worktree_root))
