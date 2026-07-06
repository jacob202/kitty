"""Predictive context prefetcher.

Learns which queries you tend to ask under a given *behavioural fingerprint*
(time-of-week + current git branch + recently-touched files), then pre-warms
``memory_graph.unified_context`` for the likely-next queries so the real
request hits a warm cache instead of recomputing.

Ported down from the abandoned ``space_kitty`` prototype — deliberately the
lazy version: the original also captured bluetooth peers and clipboard, kept
its own SQLite + cosine index, and leaned on the dead ``MemoryWeave``. None of
that survives here.

Privacy (D10): fingerprints (time / branch / filenames) never leave the box —
they are appended to a local JSONL and used only to pick queries. The warmed
context flows through ``unified_context``, which already enforces the boundary.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("kitty.prefetcher")

_ROOT = Path(__file__).resolve().parent.parent
_HISTORY = _ROOT / "data" / "prefetch_history.jsonl"

# ponytail: naive in-process TTL cache + last-N history scan. Fine for a
# single-user local gateway; swap for a real store if history outgrows memory.
_HISTORY_SCAN = 500
_CACHE_TTL_S = 300.0
_RECENT_FILES = 5
_cache: dict[str, tuple[float, str]] = {}


@dataclass(frozen=True)
class Fingerprint:
    """Cheap, local signals that correlate with what you're about to ask."""

    time_slot: str
    git_branch: str
    recent_files: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "time_slot": self.time_slot,
            "git_branch": self.git_branch,
            "recent_files": list(self.recent_files),
        }


def _time_slot(now: datetime) -> str:
    """Weekday + 4-hour block — captures a weekly rhythm without over-fitting."""
    return f"{now.weekday()}-{now.hour // 4}"


def _git_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def _recent_files() -> tuple[str, ...]:
    """Basenames of the most recently modified tracked files (no paths — keeps
    the fingerprint portable and avoids leaking directory structure)."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=_ROOT, capture_output=True, text=True, timeout=3
        )
        if out.returncode != 0:
            return ()
        paths = [_ROOT / p for p in out.stdout.splitlines()]
        paths = [p for p in paths if p.exists()]
        paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return tuple(p.name for p in paths[:_RECENT_FILES])
    except (subprocess.SubprocessError, OSError):
        return ()


def capture_fingerprint() -> Fingerprint:
    return Fingerprint(
        time_slot=_time_slot(datetime.now()),
        git_branch=_git_branch(),
        recent_files=_recent_files(),
    )


def record(query: str, fp: Fingerprint | None = None) -> None:
    """Append a (fingerprint, query) observation for future prediction."""
    query = query.strip()
    if not query:
        return
    fp = fp or capture_fingerprint()
    try:
        _HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY.open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), "query": query, "fp": fp.to_dict()}) + "\n")
    except OSError as exc:
        logger.warning("prefetch: could not record history: %s", exc)


def _load_history() -> list[dict]:
    if not _HISTORY.exists():
        return []
    try:
        lines = _HISTORY.read_text().splitlines()[-_HISTORY_SCAN:]
    except OSError:
        return []
    rows: list[dict] = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _similarity(a: Fingerprint, b: dict) -> float:
    """Weighted overlap. Branch is the strongest signal, then time, then files."""
    score = 0.0
    if a.git_branch and a.git_branch == b.get("git_branch"):
        score += 0.5
    if a.time_slot == b.get("time_slot"):
        score += 0.3
    files = set(a.recent_files) & set(b.get("recent_files") or [])
    if a.recent_files:
        score += 0.2 * (len(files) / len(a.recent_files))
    return score


def predict(fp: Fingerprint | None = None, k: int = 3) -> list[str]:
    """Most likely next queries for ``fp``, best-first, deduped."""
    fp = fp or capture_fingerprint()
    scored: dict[str, float] = {}
    for row in _load_history():
        s = _similarity(fp, row.get("fp") or {})
        if s <= 0:
            continue
        q = (row.get("query") or "").strip()
        if q:
            scored[q] = max(scored.get(q, 0.0), s)
    return [q for q, _ in sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:k]]


def get_cached(query: str) -> str | None:
    hit = _cache.get(query)
    if hit is None:
        return None
    expires, value = hit
    if time.time() >= expires:
        _cache.pop(query, None)
        return None
    return value


def put_cached(query: str, context: str) -> None:
    _cache[query] = (time.time() + _CACHE_TTL_S, context)


async def warm(k: int = 3) -> int:
    """Precompute context for the predicted next queries. Returns how many were
    freshly warmed (already-cached predictions are skipped)."""
    from gateway import memory_graph

    warmed = 0
    for query in predict(k=k):
        if get_cached(query) is not None:
            continue
        try:
            # _record=False: a prediction is not a real ask; don't feed it back.
            await memory_graph.unified_context(query, _record=False)
            warmed += 1
        except Exception as exc:  # noqa: BLE001 - warming is best-effort
            logger.warning("prefetch: warm failed for %r: %s", query, exc)
    return warmed
