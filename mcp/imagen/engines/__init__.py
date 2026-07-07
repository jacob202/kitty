"""Engine registry — maps engine slugs to engine instances.

Adding a new engine: implement the Engine protocol, add an entry here.
The tool layer dispatches by name via ``registry.get(engine_name)``.
"""

from __future__ import annotations

from mcp.imagen.engines.base import Engine
from mcp.imagen.engines.comfyui import ComfyuiEngine
from mcp.imagen.engines.dalle import DalleEngine
from mcp.imagen.engines.drawthings import DrawThingsEngine
from mcp.imagen.engines.imagen4 import Imagen4Engine
from mcp.imagen.engines.nano_banana import NanoBananaEngine

_REGISTRY: dict[str, Engine] = {}


def _register(engine: Engine) -> Engine:
    _REGISTRY[engine.name] = engine
    return engine


# Singleton instances — created once at import.
nano_banana = _register(NanoBananaEngine())
imagen4 = _register(Imagen4Engine())
dalle = _register(DalleEngine())
comfyui = _register(ComfyuiEngine())
drawthings = _register(DrawThingsEngine())


def get(name: str) -> Engine:
    """Return the engine for ``name``, or raise a clear error if unknown."""
    eng = _REGISTRY.get(name)
    if eng is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown engine {name!r}. Available: {available}")
    return eng


def available() -> list[str]:
    """Return the sorted list of registered engine slugs."""
    return sorted(_REGISTRY)
