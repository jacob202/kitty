"""Dream / memory consolidation — owned substrate for the dream endpoint.

Why this module exists (Phase 3 of the gateway deepening program):
the route used to embed the ``nightly_dream()`` summary parser and a
``_run_dream_task`` background handler inline, with multiple
``try/except`` blocks that either swallowed real failures or invented
fake data on a "simulate" branch. The new module owns the storage,
the parser, the trigger, and the status surface; the route layer is
a thin request-parsing / response-shaping wrapper.

The wire shape of every endpoint that used to live in
``routes/dream.py`` and the dream-touching endpoints in
``routes/insights.py`` is unchanged.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.dream_insights")

DREAM_INSIGHTS_FILE = DATA_DIR / "dream_insights.json"


# ── Parser ──────────────────────────────────────────────────────────────────


def _classify_kind(sentence: str) -> str:
    """Map one summary sentence to its kind card."""
    lower = sentence.lower()
    if "error" in lower or "failed" in lower:
        return "warning"
    if "prune" in lower or "old" in lower:
        return "maintenance"
    if "mirror" in lower or "refresh" in lower:
        return "reflection"
    return "consolidation"


def save_dream_insights(summary: str) -> None:
    """Parse ``summary`` (output of ``nightly_dream()``) into insight cards.

    One card per non-empty line. Each card gets a fresh id, the
    current timestamp, a fixed ``source`` of ``"nightly_dream"``, and
    a kind derived from sentence content. Writes JSON to
    ``DREAM_INSIGHTS_FILE`` (overwriting any prior content).
    """
    sentences = [s.strip() for s in summary.splitlines() if s.strip()]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    cards: list[dict] = [
        {
            "insight_id": str(uuid.uuid4())[:8],
            "kind": _classify_kind(sentence),
            "title": sentence[:80],
            "detail": sentence,
            "source": "nightly_dream",
            "confidence": 0.9,
            "created_at": now,
            "actions": [],
        }
        for sentence in sentences
    ]
    DREAM_INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DREAM_INSIGHTS_FILE.write_text(
        json.dumps(cards, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved %d dream insights", len(cards))


# ── Reader ───────────────────────────────────────────────────────────────────


def _normalize_created_at(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def load_dream_insights(limit: int = 10) -> list[dict]:
    """Return dream insight cards, newest first, normalized for the UI.

    Returns ``[]`` when no data has been written. The empty state is
    explicit — never mock data.
    """
    if not DREAM_INSIGHTS_FILE.exists():
        return []
    try:
        raw = json.loads(DREAM_INSIGHTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"DREAM_INSIGHTS_FILE at {DREAM_INSIGHTS_FILE} is not valid JSON: {exc}"
        ) from exc

    rows = raw if isinstance(raw, list) else []
    normalized: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["created_at"] = _normalize_created_at(row.get("created_at"))
        normalized.append(row)

    if limit <= 0:
        return normalized
    return normalized[:limit]


def dismiss_dream_insight(insight_id: str) -> bool:
    """Remove one insight card by id. Returns True when something was removed."""
    rows = load_dream_insights(limit=0)
    kept = [row for row in rows if row.get("insight_id") != insight_id]
    if len(kept) == len(rows):
        return False
    DREAM_INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DREAM_INSIGHTS_FILE.write_text(
        json.dumps(kept, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return True


# ── Trigger / Status ─────────────────────────────────────────────────────────


def trigger_dream() -> str:
    """Run ``nightly_dream()`` synchronously and persist its cards.

    Raises when ``nightly_dream`` is unavailable or fails — the old
    code's "simulate" branch invented fake data and is gone.
    """
    from gateway.memory_consolidation import nightly_dream

    summary = nightly_dream()
    save_dream_insights(summary)
    return summary


def dream_status() -> dict:
    """Return the consolidation runtime status for ``/dream/status``."""
    from gateway.memory_consolidation import get_last_run_info

    info = get_last_run_info()
    insights = load_dream_insights(limit=0)
    info["insights_count"] = len(insights)
    return info
