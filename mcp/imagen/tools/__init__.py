"""Tool registration — imports all tools so they're registered on the MCP server.

PR 3 collapses the 4 legacy generate_image* tools into:
  - ``generate`` (unified, engine-dispatched, cached)
  - ``edit_image`` (unified, engine-dispatched)
  - ``batch_generate`` (parallel N prompts via asyncio.gather)

The non-generation tools (refine, variations, avatar, reference, gallery)
are unchanged in behavior but now live in their own modules.
"""

from mcp.imagen.tools.batch import batch_generate
from mcp.imagen.tools.gallery import make_gallery
from mcp.imagen.tools.generate import edit_image, generate
from mcp.imagen.tools.generate_until import generate_until
from mcp.imagen.tools.reference import (
    generate_with_avatar,
    generate_with_reference,
    set_avatar,
)
from mcp.imagen.tools.refine import refine_image
from mcp.imagen.tools.variations import variations

__all__ = [
    "generate",
    "edit_image",
    "batch_generate",
    "refine_image",
    "variations",
    "generate_until",
    "generate_with_reference",
    "set_avatar",
    "generate_with_avatar",
    "make_gallery",
]
