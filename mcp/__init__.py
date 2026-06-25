"""Namespace package — extends mcp to include both the pip-installed SDK
and the local ``mcp/imagen/`` server.

This lets ``from mcp.server.fastmcp import FastMCP`` (installed SDK) and
``from mcp.imagen.config import settings`` (local) coexist.
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
