"""REST endpoints for proactive expert feedback and state management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway import expert_state, signal_store

router = APIRouter(prefix="/experts", tags=["Experts"])


class SnoozeRequest(BaseModel):
    duration_hours: float


@router.get("/signals/unprocessed")
async def get_unprocessed_expert_signals():
    """Fetch all unprocessed signals emitted by proactive experts."""
    # Source must start with expert.
    # signal_store.list_unprocessed doesn't have source filtering directly,
    # but we can filter the result.
    unprocessed = signal_store.list_unprocessed(limit=100)
    expert_signals = [s for s in unprocessed if s.get("source", "").startswith("expert.")]
    return {"signals": expert_signals}

@router.post("/{expert_id}/snooze")
async def snooze_expert(expert_id: str, payload: SnoozeRequest):
    """Temporarily pause an expert's proactive evaluation."""
    duration_sec = payload.duration_hours * 3600
    snooze_until = expert_state.set_snooze(expert_id, duration_sec)
    from gateway.sse import broadcaster
    broadcaster.broadcast("state_updated")
    return {"expert_id": expert_id, "snoozed_until": snooze_until}


@router.delete("/{expert_id}/snooze")
async def unsnooze_expert(expert_id: str):
    """Resume an expert's proactive evaluation immediately."""
    expert_state.clear_snooze(expert_id)
    from gateway.sse import broadcaster
    broadcaster.broadcast("state_updated")
    return {"expert_id": expert_id, "snoozed": False}


@router.post("/pause-all")
async def pause_all_experts():
    """Globally pause all proactive experts."""
    expert_state.set_global_pause(True)
    return {"pause_all": True}


@router.delete("/pause-all")
async def resume_all_experts():
    """Globally resume all proactive experts."""
    expert_state.set_global_pause(False)
    return {"pause_all": False}


@router.post("/signals/{signal_id}/dismiss")
async def dismiss_expert_signal(signal_id: int):
    """Dismiss a signal, suppressing similar future insights from this expert."""
    sig = signal_store.get_signal(signal_id)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")

    source = sig.get("source", "")
    if not source.startswith("expert."):
        raise HTTPException(status_code=400, detail="Not an expert signal")

    expert_id = source.replace("expert.", "", 1)
    topic_hash = sig.get("payload", {}).get("topic_hash")

    if not topic_hash:
        raise HTTPException(status_code=400, detail="Signal missing topic hash")

    new_count = expert_state.increment_dismissed_count(expert_id, topic_hash)

    # Also mark it processed so it clears from the UI
    signal_store.mark_processed(signal_id)
    from gateway.sse import broadcaster
    broadcaster.broadcast("state_updated")

    return {
        "expert_id": expert_id,
        "signal_id": signal_id,
        "topic_hash": topic_hash,
        "dismissed_count": new_count
    }


@router.delete("/signals/{signal_id}")
async def delete_signal(signal_id: int):
    """Delete a signal entirely (for tests/cleanup)."""
    signal_store.delete(signal_id)
    return {"status": "deleted", "id": signal_id}
