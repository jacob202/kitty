"""Route-contract test — every (method, path) must be registered once.

Codex audit blocker #3: cron/monitor/dream routes were duplicated across
modules, and FastAPI registration order silently picked the winner with
inconsistent response shapes. This test fails loudly if any (method, path)
is registered by more than one route module, so the contract stays
single-source.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from fastapi import APIRouter

from gateway import routes as routes_pkg

ROUTES_DIR = Path(routes_pkg.__file__).parent


def _normalized(path: str) -> str:
    """Collapse path params so /monitor/{a} and /monitor/{b} collide."""
    import re

    return re.sub(r"\{[^}]+\}", "{}", path)


def _collect() -> dict[tuple[str, str], list[str]]:
    """Map (method, normalized_path) -> list of owning module names."""
    seen: dict[tuple[str, str], list[str]] = {}
    for mod_info in pkgutil.iter_modules([str(ROUTES_DIR)]):
        module = importlib.import_module(f"gateway.routes.{mod_info.name}")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            continue
        for route in router.routes:
            methods = getattr(route, "methods", None) or {"*"}
            for method in methods:
                key = (method, _normalized(route.path))
                seen.setdefault(key, []).append(mod_info.name)
    return seen


def test_no_duplicate_route_contracts() -> None:
    seen = _collect()
    collisions = {
        f"{method} {path}": owners
        for (method, path), owners in seen.items()
        if len(owners) > 1
    }
    assert not collisions, f"duplicate route registrations: {collisions}"
