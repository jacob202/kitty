"""Proactive signals feed — returns RepairsIssue-shaped records from signal store."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger("kitty.signals")
router = APIRouter(tags=["signals"])


@router.get("/signals")
def list_signals():
    """Return unprocessed signals in the Repairs shape for the Home card."""
    from gateway import signal_store

    try:
        raw_signals = signal_store.list_unprocessed(limit=20)
    except Exception as exc:
        logger.warning("Failed to list signals: %s", exc)
        return {"issues": 0, "repairs": []}

    repairs = []
    for sig in raw_signals:
        source = sig.get("source", "")
        payload = sig.get("payload") or {}
        signal_id = sig.get("id", 0)

        title = payload.get("title") or source.replace("expert.", "").replace(".", " ").capitalize()
        detail = payload.get("text") or payload.get("summary") or "A proactive signal was raised"

        repair = {
            "id": f"signal-{signal_id}",
            "severity": _severity_for(payload),
            "title": title,
            "detail": detail,
        }

        if source.startswith("expert."):
            expert_id = source.replace("expert.", "", 1)
            repair["fix"] = {
                "label": "Snooze for a day",
                "action_kind": "repair.check",
                "check_name": f"snooze:{expert_id}",
            }
        else:
            repair["fix"] = {
                "label": "Dismiss",
                "action_kind": "repair.dismiss",
                "check_name": f"signal-{signal_id}",
            }

        repairs.append(repair)

    return {"issues": len(repairs), "repairs": repairs}


def _severity_for(payload: dict) -> str:
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)):
        if confidence > 0.8:
            return "error"
        if confidence > 0.5:
            return "warn"
    priority = payload.get("priority", "").lower()
    if priority in ("high", "critical"):
        return "error"
    if priority in ("medium",):
        return "warn"
    return "ok"
