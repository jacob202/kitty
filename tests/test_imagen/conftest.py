"""Path setup for imagen tests.

The local ``mcp/`` directory must be on ``sys.path`` before the installed
``mcp`` SDK so that ``mcp.imagen`` resolves to the local package while
``mcp.server.fastmcp`` still resolves to the installed SDK (via the
namespace package in ``mcp/__init__.py``).
"""

import sys
import types
from pathlib import Path

_worktree_root = Path(__file__).resolve().parents[2]
if str(_worktree_root) not in sys.path:
    sys.path.insert(0, str(_worktree_root))

# The batch tools import ``mcp.server.fastmcp`` at module level, which fails at
# collection time when the real mcp SDK isn't installed (e.g. CI). Stub it the
# same way test_mcp_imagen.py does — only when the real import is unavailable,
# so local runs with the SDK present are untouched.
try:
    import mcp.server.fastmcp  # noqa: F401
except ModuleNotFoundError:
    class _Image:
        def __init__(self, data: bytes = b"", format: str = "png") -> None:
            self.data = data
            self.format = format

    class _FastMCP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def tool(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def run(self) -> None:
            pass

    _fastmcp = types.ModuleType("mcp.server.fastmcp")
    _fastmcp.Image = _Image  # type: ignore[attr-defined]
    _fastmcp.FastMCP = _FastMCP  # type: ignore[attr-defined]

    _server = sys.modules.get("mcp.server") or types.ModuleType("mcp.server")
    _server.fastmcp = _fastmcp  # type: ignore[attr-defined]

    sys.modules["mcp.server"] = _server
    sys.modules["mcp.server.fastmcp"] = _fastmcp
