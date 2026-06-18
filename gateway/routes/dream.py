"""Dream / memory consolidation routes."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from gateway.paths import DATA_DIR

router = APIRouter(tags=["dream"])

logger = logging.getLogger("kitty.routes.dream")

DREAM_INSIGHTS_FILE = DATA_DIR / "dream_insights.json"


class GatewayInsight(BaseModel):
    insight_id: str
    kind: str
    title: str
    detail: str
    source: str
    confidence: float
    created_at: str
    actions: list[str]


def save_dream_insights(summary: str) -> None:
    """Parse the nightly_dream() summary string into insight cards and persist them."""
    sentences = [s.strip() for s in summary.splitlines() if s.strip()]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    insights: list[dict] = []

    for sentence in sentences:
        # Classify kind from sentence content
        lower = sentence.lower()
        if "error" in lower or "failed" in lower:
            kind = "warning"
        elif "prune" in lower or "old" in lower:
            kind = "maintenance"
        elif "mirror" in lower or "refresh" in lower:
            kind = "reflection"
        else:
            kind = "consolidation"

        insights.append(
            {
                "insight_id": str(uuid.uuid4())[:8],
                "kind": kind,
                "title": sentence[:80],
                "detail": sentence,
                "source": "nightly_dream",
                "confidence": 0.9,
                "created_at": now,
                "actions": [],
            }
        )

    DREAM_INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DREAM_INSIGHTS_FILE.write_text(json.dumps(insights, indent=2))
    logger.info("Saved %d dream insights", len(insights))


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
    """Load dream insights defensively for routes and dashboard tests."""
    if not DREAM_INSIGHTS_FILE.exists():
        return []
    try:
        raw = json.loads(DREAM_INSIGHTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read dream insights: %s", e)
        return []

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
    """Remove one insight card from the local dream insight file."""
    rows = load_dream_insights(limit=0)
    kept = [row for row in rows if row.get("insight_id") != insight_id]
    if len(kept) == len(rows):
        return False
    DREAM_INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DREAM_INSIGHTS_FILE.write_text(json.dumps(kept, indent=2), encoding="utf-8")
    return True


def _run_dream_task() -> None:
    """Background task: run nightly_dream, save insights, ensure cron action registered."""
    try:
        from gateway.memory_consolidation import nightly_dream

        summary = nightly_dream()
        save_dream_insights(summary)
    except Exception as e:
        logger.error("Dream task failed: %s", e)

    # Register memory.consolidate cron action if not already present
    try:
        from gateway.cron import get_actions, register_action
        import asyncio

        if "memory.consolidate" not in get_actions():

            async def _action_memory_consolidate():
                from gateway.memory_consolidation import nightly_dream as _dream
                import asyncio as _asyncio

                await _asyncio.to_thread(_dream)

            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(
                    lambda: register_action(
                        "memory.consolidate", _action_memory_consolidate
                    )
                )
            except RuntimeError:
                register_action("memory.consolidate", _action_memory_consolidate)
    except Exception as e:
        logger.warning("Could not register cron action: %s", e)


@router.get("/dream/status")
async def dream_status():
    from gateway.memory_consolidation import get_last_run_info

    return get_last_run_info()


@router.post("/dream/trigger")
async def dream_trigger(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_dream_task)
    return {"queued": True}


@router.get("/dream/insights")
async def dream_insights():
    return {"insights": load_dream_insights()}
