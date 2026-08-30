"""KittyBuilder MCP bridge.

The package is deliberately transport-agnostic. Importing :mod:`mcp.builder`
never starts an MCP server or touches Builder state; ``server.py`` is the thin
registration/transport entry point.
"""

from .schemas import MCP_ARTIFACT_MARKER

__all__ = ["MCP_ARTIFACT_MARKER"]
