"""Life awareness routes — calendar, do-not-disturb, evening reflection, proactive."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from gateway import life_awareness

logger = logging.getLogger("kitty.routes.life")

router = APIRouter(tags=["life"])


@router.get("/life/today")
async def get_today_summary() -> dict:
    return life_awareness.today_summary()


@router.get("/life/yesterday")
async def get_yesterday_recap() -> dict:
    return life_awareness.yesterday_recap()


@router.get("/life/dnd")
async def get_do_not_disturb() -> dict:
    return life_awareness.do_not_disturb_status()


@router.get("/life/proactive")
async def get_proactive() -> dict:
    return life_awareness.morning_proactive()


@router.get("/life/reflection")
async def get_evening_reflection() -> dict:
    return life_awareness.evening_reflection()


@router.post("/life/reflection/generate")
async def post_generate_reflection() -> dict:
    text = life_awareness.generate_evening_reflection_text()
    life_awareness.emit_life_signal(
        life_awareness.EVENING_REFLECTION_EMITTED,
        {"reflection": text[:200]},
    )
    return {"reflection": text}


@router.post("/life/proactive/generate")
async def post_generate_proactive() -> dict:
    text = life_awareness.generate_proactive_text()
    life_awareness.emit_life_signal(
        life_awareness.MORNING_BRIEF_EMITTED,
        {"proactive": text[:200]},
    )
    return {"proactive": text}


@router.post("/life/dismiss/{signal_kind}")
async def post_dismiss(signal_kind: str) -> dict:
    life_awareness.emit_life_signal(
        life_awareness.PROACTIVE_DISMISSED,
        {"kind": signal_kind},
    )
    return {"dismissed": signal_kind}


@router.post("/life/cache/invalidate")
async def invalidate_life_cache() -> dict:
    life_awareness.invalidate_caches()
    return {"ok": True}


@router.get("/life/meeting")
async def get_current_meeting() -> dict:
    meeting = life_awareness.current_meeting()
    if meeting:
        return {"in_meeting": True, "meeting": meeting}
    return {"in_meeting": False, "meeting": None}


@router.get("/life/events")
async def list_life_events(limit: int = 20) -> dict:
    from gateway.signal_store import list_recent
    signals = list_recent(limit=limit, source=life_awareness.LIFE_SIGNAL_SOURCE)
    return {"events": signals}


@router.get("/life/check")
async def get_life_check() -> dict:
    dnd = life_awareness.do_not_disturb_status()
    proactive = life_awareness.morning_proactive()
    return {
        "do_not_disturb": dnd["do_not_disturb"],
        "in_meeting": dnd["in_meeting"],
        "current_meeting": dnd.get("current_meeting"),
        "event_count": dnd.get("event_count", 0),
        "life_step_count": len(proactive.get("life_steps", [])),
        "proactive_suggestions": proactive.get("proactive_suggestions", []),
    }