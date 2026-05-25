"""Dream / memory consolidation routes."""

from __future__ import annotations

import json
import logging
import time
import uuid

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
    if not DREAM_INSIGHTS_FILE.exists():
        return {"insights": []}
    try:
        raw = json.loads(DREAM_INSIGHTS_FILE.read_text())
        insights = [GatewayInsight(**item) for item in raw]
        return {"insights": [i.model_dump() for i in insights]}
    except Exception as e:
        logger.warning("Failed to read dream insights: %s", e)
        return {"insights": []}
