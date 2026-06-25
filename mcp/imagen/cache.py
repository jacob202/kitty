"""SHA256-keyed cache for identical (prompt, engine, params) inputs.

Refine loops that come back DONE on round 1 hit the cache for any re-runs.
Identical prompts from different sessions dedup. The cache key is a hash
(not the params blob) to keep filenames short.

Cache invalidation: ``model_name`` is included in the key params, so when
an engine version changes the cache is implicitly invalidated.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from mcp.imagen.config import settings
from mcp.imagen.logging import log


def key_for(prompt: str, engine: str, params: dict[str, Any]) -> str:
    """Return a deterministic SHA256 hex digest for the given inputs.

    ``params`` should include ``model_name`` so engine version changes
    invalidate the cache. ``seed=0`` and ``seed=None`` produce different
    keys (tested explicitly).
    """
    # sorted items ensure dict ordering doesn't affect the hash.
    blob = json.dumps(
        {"prompt": prompt, "engine": engine, "params": sorted(params.items())},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get(key: str) -> Path | None:
    """Return the cached image path if it exists, else None."""
    path = settings.cache_dir / f"{key}.png"
    if path.exists():
        log.debug("cache hit: %s", key[:12])
        return path
    return None


def put(key: str, src: Path) -> Path:
    """Copy ``src`` into the cache as ``{key}.png`` and return the cached path.

    Copy (not symlink) so the cache survives the source being deleted.
    """
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    dst = settings.cache_dir / f"{key}.png"
    shutil.copyfile(src, dst)
    log.debug("cache put: %s", key[:12])
    return dst


def clear() -> int:
    """Remove all cached images, return the count deleted. For manual cleanup."""
    if not settings.cache_dir.exists():
        return 0
    count = 0
    for p in settings.cache_dir.glob("*.png"):
        p.unlink()
        count += 1
    log.info("cache cleared: %d files", count)
    return count
