"""MemPalace StoreAdapter — optional local-first semantic memory backend.

MemPalace (https://github.com/MemPalace/mempalace) is a local-first semantic
memory system with verbatim storage and a typed knowledge graph (temporal
validity windows). This adapter slots it behind ``memory_graph`` so its
results join the unified context alongside the existing stores — delivering
the "typed relationship graph" capability without a separate always-on
service.

OFF BY DEFAULT. Enable by installing the package and setting the env flag:

    pip install mempalace
    export KITTY_MEMPALACE_ENABLED=1

When disabled, missing, or erroring, ``fetch`` returns ``[]`` — the unified
context is unaffected.

Phase 2 contract: ``fetch`` returns ``list[Item]``. ``format_items`` and
``correlate`` are gone from the adapter contract; the assembler does all
formatting.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess

from gateway.memory_graph import Item, Source, StoreAdapter

logger = logging.getLogger("kitty.mempalace")

_ENV_FLAG = "KITTY_MEMPALACE_ENABLED"
_SEARCH_LIMIT = 5
_TIMEOUT_S = 10


class MemPalaceAdapter(StoreAdapter):
    """Adapter exposing MemPalace semantic memory to the unified memory graph."""

    @property
    def name(self) -> str:
        return Source.MEMORY_PALACE.value

    @staticmethod
    def is_enabled() -> bool:
        """True only when explicitly enabled via env flag."""
        return os.environ.get(_ENV_FLAG, "").strip().lower() in ("1", "true", "yes")

    async def fetch(self, query: str) -> list[Item]:
        if not self.is_enabled() or not query.strip():
            return []
        try:
            return await __import__("asyncio").to_thread(self._search, query)
        except Exception as e:  # never break the unified context
            logger.warning("MemPalace fetch failed: %s", e)
            return []

    def _search(self, query: str) -> list[Item]:
        """Query MemPalace. Isolated so the integration point is easy to verify/swap."""
        exe = shutil.which("mempalace")
        if not exe:
            logger.debug("mempalace CLI not on PATH; skipping")
            return []
        proc = subprocess.run(
            [exe, "search", query, "--limit", str(_SEARCH_LIMIT), "--json"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
        if proc.returncode != 0:
            logger.debug("mempalace search rc=%s: %s", proc.returncode, proc.stderr[:200])
            return []
        return self._parse(proc.stdout)

    @staticmethod
    def _parse(stdout: str) -> list[Item]:
        """Parse CLI JSON into normalized items. Tolerant of shape differences."""
        try:
            data = json.loads(stdout or "[]")
        except json.JSONDecodeError:
            return []
        rows = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            return []
        items: list[Item] = []
        for r in rows[:_SEARCH_LIMIT]:
            if not isinstance(r, dict):
                continue
            text = r.get("text") or r.get("content") or r.get("snippet") or ""
            if not text:
                continue
            items.append(
                Item(
                    text=text,
                    source=Source.MEMORY_PALACE,
                    score=r.get("_score"),
                    ts=None,
                    metadata={
                        k: v
                        for k, v in r.items()
                        if k not in {"text", "content", "snippet", "_score"}
                    },
                )
            )
        return items
